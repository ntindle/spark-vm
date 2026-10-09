"""Tests for deploy/golden-image/identity-seed-hook.sh (#1203).

The hook is exercised as a real subprocess against a stub pairing client
(SPARKVM_PAIR_CLIENT): every skip path must exit 0 without invoking the
client, the first-enroll path must invoke init-then-request with the
attestation token in the environment only (never on argv, never in logs),
and failures must be loud and nonzero.
"""
import configparser
import json
import os
import re
import stat
import subprocess

import pytest

GOLDEN_DIR = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(GOLDEN_DIR, "identity-seed-hook.sh")
SUPERVISORD_CONF = os.path.join(GOLDEN_DIR, "supervisord.conf")
DOCKERFILE = os.path.join(GOLDEN_DIR, "Dockerfile")

TOKEN = "test-attestation-token-abc123"
BOX_ID = "box-test-001"
PLANE_URL = "https://control.test"

STUB = """#!/usr/bin/env python3
import os, sys
logdir = os.environ["STUB_LOG"]
argv = sys.argv[1:]
sub = "init" if "init" in argv else ("request" if "request" in argv else None)
with open(os.path.join(logdir, "argv"), "a") as f:
    f.write(" ".join(argv) + "\\n")
tok = os.environ.get("SPARKVM_ATTESTATION_TOKEN")
if tok:
    with open(os.path.join(logdir, "env"), "a") as f:
        f.write("token-env-present:%s\\n" % sub)
    with open(os.path.join(logdir, "token_value"), "w") as f:
        f.write(tok)
sys.exit(int(os.environ.get("STUB_INIT_EXIT" if sub == "init"
                            else "STUB_REQUEST_EXIT", "0"))
         if sub else 99)
"""


@pytest.fixture()
def harness(tmp_path):
    """Build a stub client + env; return a run() helper and paths."""
    logdir = tmp_path / "log"
    logdir.mkdir()
    stub = tmp_path / "stub_pair.py"
    stub.write_text(STUB)
    stub.chmod(0o755)
    state = tmp_path / "state"
    state.mkdir()

    base_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path),
        "SPARKVM_PAIR_CLIENT": str(stub),
        "SVM_PAIR_DIR": str(state),
        "STUB_LOG": str(logdir),
    }

    def run(env_extra=None, env_remove=()):
        env = dict(base_env)
        env.update(env_extra or {})
        for k in env_remove:
            env.pop(k, None)
        return subprocess.run(
            ["bash", HOOK], env=env, capture_output=True, text=True,
            timeout=30)

    return {"run": run, "logdir": logdir, "state": state}


def _full_env():
    return {"SPARKVM_BOX_ID": BOX_ID, "SPARKVM_PLANE_URL": PLANE_URL,
            "SPARKVM_ATTESTATION_TOKEN": TOKEN}


def _argv_lines(harness):
    p = harness["logdir"] / "argv"
    return p.read_text().splitlines() if p.exists() else []


def test_absent_env_skips_without_invoking_client(harness):
    r = harness["run"]()
    assert r.returncode == 0, r.stderr
    assert _argv_lines(harness) == []
    assert "not enrolling" in r.stderr


def test_partial_env_skips_without_invoking_client(harness):
    r = harness["run"]({"SPARKVM_BOX_ID": BOX_ID,
                        "SPARKVM_PLANE_URL": PLANE_URL})
    assert r.returncode == 0, r.stderr
    assert _argv_lines(harness) == []
    assert "not enrolling" in r.stderr


def test_enrolled_state_skips_and_never_represents(harness):
    (harness["state"] / "enrollment.json").write_text(
        json.dumps({"box_id": BOX_ID, "token": "t"}))
    r = harness["run"](_full_env())
    assert r.returncode == 0, r.stderr
    assert _argv_lines(harness) == []
    assert "already enrolled" in r.stderr


def test_inflight_pairing_skips_and_names_redeem(harness):
    (harness["state"] / "pairing.json").write_text(
        json.dumps({"pairing_id": "pair_x"}))
    r = harness["run"](_full_env())
    assert r.returncode == 0, r.stderr
    assert _argv_lines(harness) == []
    assert "redeem" in r.stderr


def test_first_enroll_runs_init_then_request(harness):
    r = harness["run"](_full_env())
    assert r.returncode == 0, r.stderr
    argv = _argv_lines(harness)
    assert len(argv) == 2, argv
    assert " init " in f" {argv[0]} " or argv[0].endswith(" init")
    assert " request " in f" {argv[1]} "
    assert f"--name {BOX_ID}" in argv[1]
    assert f"--control {PLANE_URL}" in argv[1]
    # The token travels in the child env only — never on argv.
    assert TOKEN not in argv[0] and TOKEN not in argv[1]
    env_lines = (harness["logdir"] / "env").read_text().splitlines()
    # request carries it explicitly; init inherits it from the hook's env.
    assert "token-env-present:request" in env_lines
    assert (harness["logdir"] / "token_value").read_text() == TOKEN


def test_init_skipped_when_keypair_exists(harness):
    (harness["state"] / "box.key").write_bytes(b"fake-key")
    r = harness["run"](_full_env())
    assert r.returncode == 0, r.stderr
    argv = _argv_lines(harness)
    assert len(argv) == 1, argv
    assert " request " in f" {argv[0]} "


def test_request_failure_exits_nonzero_and_loud(harness):
    r = harness["run"]({**_full_env(), "STUB_REQUEST_EXIT": "1"})
    assert r.returncode != 0
    assert "not enrolled" in r.stderr


def test_token_never_in_hook_output(harness):
    # Success path and every skip/failure path: the token must not appear
    # in anything the hook prints (supervisord captures it to disk).
    r = harness["run"](_full_env())
    assert TOKEN not in r.stdout + r.stderr
    r = harness["run"]()
    assert TOKEN not in r.stdout + r.stderr
    (harness["state"] / "enrollment.json").write_text("{}")
    r = harness["run"](_full_env())
    assert TOKEN not in r.stdout + r.stderr
    (harness["state"] / "enrollment.json").unlink()
    r = harness["run"]({**_full_env(), "STUB_REQUEST_EXIT": "1"})
    assert TOKEN not in r.stdout + r.stderr


def test_no_home_falls_back_to_root_default(harness):
    # supervisord children are not guaranteed a HOME; under `set -u` the
    # hook must not die on the unbound variable.
    r = harness["run"](_full_env(), env_remove=("HOME", "SVM_PAIR_DIR"))
    assert r.returncode == 0, r.stderr
    argv = _argv_lines(harness)
    assert len(argv) == 2, argv
    assert "--dir /root/.config/spark-pair" in argv[0]


def test_hook_is_executable_bash():
    assert os.access(HOOK, os.X_OK)
    mode = stat.S_IMODE(os.stat(HOOK).st_mode)
    assert mode & 0o111, "hook must be executable"
    with open(HOOK, encoding="utf-8") as f:
        first = f.readline().strip()
    assert first == "#!/bin/bash"


def _supervisord():
    cfg = configparser.ConfigParser()
    cfg.read(SUPERVISORD_CONF)
    return cfg


def test_supervisord_identity_seed_is_oneshot_first():
    cfg = _supervisord()
    section = "program:identity-seed"
    assert section in cfg.sections(), cfg.sections()
    prog = cfg[section]
    assert prog["command"] == "/usr/local/bin/identity-seed-hook.sh"
    assert prog.get("autorestart", "").lower() == "false"
    assert int(prog.get("priority", "999")) < 999
    assert int(prog.get("startsecs", "1")) == 0
    assert prog.get("user", "") == "root"


def test_dockerfile_installs_and_chmods_hook():
    with open(DOCKERFILE, encoding="utf-8") as f:
        text = f.read()
    assert re.search(
        r"^COPY deploy/golden-image/identity-seed-hook\.sh "
        r"/usr/local/bin/identity-seed-hook\.sh$",
        text, re.M), "hook must be COPYed to /usr/local/bin like the firstboot wrapper"
    m = re.search(r"RUN chmod 0755 /usr/local/bin/sparkvm-sshd-firstboot\.sh \\\n"
                  r"((?:.*\\\n)*?.*identity-seed-hook\.sh.*)",
                  text)
    assert m, "the chmod RUN must cover the hook script"
