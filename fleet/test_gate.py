"""Tests for the G18 S1a release-gating channel (issue #777).

fleet/gate_publish.py (controller: registry + manifest + freeze -> signed
gate.json), fleet/gate_query.py (box: verify + self-evaluated answer), the
freeze-drill acceptance test (§4: publish a freeze, assert every box in a
2-box fixture reports state=frozen within sync_cadence + ε), and the
pending_range() gate cap in deploy/auto-deploy.sh.

Run from the repo root: python3 -m pytest fleet/test_gate.py -q
"""

import binascii
import hashlib
import hmac
import json
import os
import stat
import subprocess
import sys
import time

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLISH = os.path.join(REPO, "fleet", "gate_publish.py")
QUERY = os.path.join(REPO, "fleet", "gate_query.py")
AUTO_DEPLOY = os.path.join(REPO, "deploy", "auto-deploy.sh")

KEY_ID = "ctl-2026-09"


def run(*argv, env_extra=None, check=False):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(argv, env=env, capture_output=True, text=True,
                          timeout=60, cwd=REPO)


@pytest.fixture()
def keyfile(tmp_path):
    p = tmp_path / "ctl.key"
    # Hex-encoded: no whitespace bytes, so no newline-strip ambiguity.
    p.write_bytes(binascii.hexlify(os.urandom(32)))
    os.chmod(p, 0o600)
    return str(p)


@pytest.fixture()
def keyfile2(tmp_path):
    p = tmp_path / "ctl-next.key"
    p.write_bytes(binascii.hexlify(os.urandom(32)))
    os.chmod(p, 0o600)
    return str(p)


@pytest.fixture()
def registry(tmp_path):
    reg = {
        "repo": {"max_permitted_commit": "a" * 40, "channel": "stable"},
        "toolset": {"max_permitted_pin": "2026.09.27", "channel": "stable"},
        "image": {"max_permitted_image_version": "2026.09.29-0",
                  "channel": "stable"},
    }
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(reg))
    return str(p)


@pytest.fixture()
def manifest(tmp_path):
    man = {
        comp: {"live": 2, "state": "wave-2",
               "assignments": {"box-07": 1}, "default": "hash_mod_4"}
        for comp in ("repo", "toolset", "image")
    }
    p = tmp_path / "waves.json"
    p.write_text(json.dumps(man))
    return str(p)


def publish(tmp_path, keyfile, registry, manifest, freeze=False, key_id=KEY_ID):
    out = str(tmp_path / "gate.json")
    r = run(sys.executable, PUBLISH, "--registry", registry,
            "--manifest", manifest,
            * (["--freeze"] if freeze else []),
            "--key-id", key_id, "--key-file", keyfile, "--out", out)
    assert r.returncode == 0, r.stderr
    return out


def query_state(gate, box_id, keys):
    r = run(sys.executable, QUERY, "--box-id", box_id, "--keys", keys,
            "--gate", gate, "state")
    assert r.returncode == 0, r.stderr
    return dict(line.split("=", 1) for line in r.stdout.strip().splitlines()
                if "=" in line)


def keys_spec(keyfile, key_id=KEY_ID):
    return f"{key_id}={keyfile}"


# --- publish ---------------------------------------------------------------

def test_publish_emits_signed_document(tmp_path, keyfile, registry, manifest):
    out = publish(tmp_path, keyfile, registry, manifest)
    doc = json.loads(open(out).read())
    assert doc["schema_version"] == 1
    assert doc["freeze"] is False
    assert doc["key_id"] == KEY_ID
    assert doc["ttl_seconds"] == 600
    assert set(doc["releases"]) == {"repo", "toolset", "image"}
    # The MAC covers the canonical body and verifies with the controller key.
    body = {k: v for k, v in doc.items() if k != "hmac"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode()
    expect = hmac.new(open(keyfile, "rb").read().rstrip(b"\r\n"), canonical,
                      hashlib.sha256).hexdigest()
    assert hmac.compare_digest(expect, doc["hmac"])
    # Published documents are never world-readable (§4 transit).
    assert stat.S_IMODE(os.stat(out).st_mode) == 0o600


def test_publish_refuses_group_readable_key(tmp_path, registry, manifest):
    p = tmp_path / "bad.key"
    p.write_bytes(os.urandom(32))
    os.chmod(p, 0o640)
    out = str(tmp_path / "gate.json")
    r = run(sys.executable, PUBLISH, "--registry", registry,
            "--manifest", manifest, "--key-id", KEY_ID,
            "--key-file", str(p), "--out", out)
    assert r.returncode != 0
    assert "0600" in r.stderr
    assert not os.path.exists(out)


def test_publish_refuses_bad_commit(tmp_path, keyfile, manifest):
    reg = {"repo": {"max_permitted_commit": "zzz", "channel": "stable"},
           "toolset": {"max_permitted_pin": "2026.09.27", "channel": "stable"},
           "image": {"max_permitted_image_version": "2026.09.29-0",
                     "channel": "stable"}}
    p = tmp_path / "bad-reg.json"
    p.write_text(json.dumps(reg))
    out = str(tmp_path / "gate.json")
    r = run(sys.executable, PUBLISH, "--registry", str(p),
            "--manifest", manifest, "--key-id", KEY_ID,
            "--key-file", keyfile, "--out", out)
    assert r.returncode != 0
    assert "max_permitted_commit" in r.stderr


def test_publish_freeze_flag(tmp_path, keyfile, registry, manifest):
    out = publish(tmp_path, keyfile, registry, manifest, freeze=True)
    assert json.loads(open(out).read())["freeze"] is True


# --- query: verify + fail-closed -------------------------------------------

def test_query_live_gate(tmp_path, keyfile, registry, manifest):
    out = publish(tmp_path, keyfile, registry, manifest)
    ans = query_state(out, "box-01", keys_spec(keyfile))
    assert ans["state"] == "live"
    assert ans["freeze"] == "false"
    assert ans["key_id"] == KEY_ID
    assert ans["repo_max"] == "a" * 40
    assert ans["repo_permitted"] in ("true", "false")  # wave-dependent


def test_query_missing_document_is_frozen(tmp_path, keyfile):
    ans = query_state(str(tmp_path / "nope.json"), "box-01", keys_spec(keyfile))
    assert ans["state"] == "frozen"
    assert "no-signal" in ans["reason"]


def test_query_bad_mac_is_frozen(tmp_path, keyfile, registry, manifest):
    out = publish(tmp_path, keyfile, registry, manifest)
    doc = json.loads(open(out).read())
    doc["freeze"] = True  # tamper after signing
    open(out, "w").write(json.dumps(doc))
    ans = query_state(out, "box-01", keys_spec(keyfile))
    assert ans["state"] == "frozen"
    assert "MAC" in ans["reason"]


def test_query_wrong_key_is_frozen(tmp_path, keyfile, keyfile2, registry,
                                  manifest):
    out = publish(tmp_path, keyfile, registry, manifest)
    ans = query_state(out, "box-01", keys_spec(keyfile2))
    assert ans["state"] == "frozen"


def test_query_expired_is_frozen(tmp_path, keyfile, registry, manifest):
    out = str(tmp_path / "gate.json")
    r = run(sys.executable, PUBLISH, "--registry", registry,
            "--manifest", manifest, "--key-id", KEY_ID,
            "--key-file", keyfile, "--out", out, "--ttl-seconds", "1")
    assert r.returncode == 0, r.stderr
    time.sleep(1.2)
    ans = query_state(out, "box-01", keys_spec(keyfile))
    assert ans["state"] == "frozen"
    assert "expired" in ans["reason"]


def test_query_freeze_flag_is_frozen(tmp_path, keyfile, registry, manifest):
    out = publish(tmp_path, keyfile, registry, manifest, freeze=True)
    ans = query_state(out, "box-01", keys_spec(keyfile))
    assert ans["state"] == "frozen"
    assert ans["freeze"] == "true"


def test_query_rotation_window_accepts_either_key(tmp_path, keyfile, keyfile2,
                                                 registry, manifest):
    out = publish(tmp_path, keyfile, registry, manifest)
    both = f"{KEY_ID}={keyfile},ctl-2026-10={keyfile2}"
    assert query_state(out, "box-01", both)["state"] == "live"
    out2 = publish(tmp_path, keyfile2, registry, manifest,
                   key_id="ctl-2026-10")
    # old key alone no longer verifies the new document...
    assert query_state(out2, "box-01", keys_spec(keyfile))["state"] == "frozen"
    # ...but the rotation window (both) does, logging the new key_id.
    ans = query_state(out2, "box-01", both)
    assert ans["state"] == "live"
    assert ans["key_id"] == "ctl-2026-10"


# --- query: wave self-evaluation -------------------------------------------

def wave_manifest(tmp_path, state, live, assignments):
    man = {comp: {"live": live, "state": state, "assignments": assignments,
                  "default": "hash_mod_4"}
           for comp in ("repo", "toolset", "image")}
    p = tmp_path / "waves.json"
    p.write_text(json.dumps(man))
    return str(p)


def test_wave_assignment_pin_beats_default(tmp_path, keyfile, registry):
    man = wave_manifest(tmp_path, "wave-2", 2, {"box-07": 1})
    out = publish(tmp_path, keyfile, registry, man)
    ans = query_state(out, "box-07", keys_spec(keyfile))
    assert ans["repo_my_wave"] == "1"
    assert ans["repo_permitted"] == "true"


def test_wave_default_hash_mod_4(tmp_path, keyfile, registry):
    man = wave_manifest(tmp_path, "wave-4", 4, {})
    out = publish(tmp_path, keyfile, registry, man)
    # Golden values: the formula sha256(box_id) % 4 is pinned here, not
    # recomputed — a formula change must fail this test, not follow it.
    for box, wave in (("some-box-99", 0), ("box-01", 1), ("box-07", 3)):
        ans = query_state(out, box, keys_spec(keyfile))
        assert ans["repo_my_wave"] == str(wave), box
    # live=4: every wave 0..3 is at or before the live wave.
    ans = query_state(out, "some-box-99", keys_spec(keyfile))
    assert ans["repo_permitted"] == "true"


def test_wave_not_yet_live_is_not_permitted(tmp_path, keyfile, registry):
    man = wave_manifest(tmp_path, "wave-2", 1, {})
    out = publish(tmp_path, keyfile, registry, man)
    # some-box-99 is wave 0 (golden, see test_wave_default_hash_mod_4).
    ans = query_state(out, "some-box-99", keys_spec(keyfile))
    assert ans["repo_permitted"] == "true"  # wave 0 <= live 1
    ans = query_state(out, "box-07", keys_spec(keyfile))
    assert ans["repo_permitted"] == "false"  # wave 3 > live 1


def test_canary_is_pin_only(tmp_path, keyfile, registry):
    man = wave_manifest(tmp_path, "canary", 1, {"box-07": 1})
    out = publish(tmp_path, keyfile, registry, man)
    assert query_state(out, "box-07", keys_spec(keyfile))["repo_permitted"] == "true"
    assert query_state(out, "other-box", keys_spec(keyfile))["repo_permitted"] == "false"


def test_halted_is_never_permitted(tmp_path, keyfile, registry):
    man = wave_manifest(tmp_path, "halted", 2, {"box-07": 1})
    out = publish(tmp_path, keyfile, registry, man)
    assert query_state(out, "box-07", keys_spec(keyfile))["repo_permitted"] == "false"


def test_permitted_exit_codes(tmp_path, keyfile, registry, manifest):
    out = publish(tmp_path, keyfile, registry, manifest)
    env = {"SPARKVM_GATE_JSON": out}
    r = run(sys.executable, QUERY, "--box-id", "box-07",
            "--keys", keys_spec(keyfile), "permitted", "repo", env_extra=env)
    assert r.returncode == 0
    frozen = publish(tmp_path, keyfile, registry, manifest, freeze=True)
    r = run(sys.executable, QUERY, "--box-id", "box-07",
            "--keys", keys_spec(keyfile), "--gate", frozen,
            "permitted", "repo")
    assert r.returncode == 2
    man = wave_manifest(tmp_path, "halted", 2, {})
    halted = publish(tmp_path, keyfile, registry, man)
    r = run(sys.executable, QUERY, "--box-id", "box-07",
            "--keys", keys_spec(keyfile), "--gate", halted,
            "permitted", "repo")
    assert r.returncode == 1


# --- freeze drill (§4 acceptance) -------------------------------------------

def test_freeze_drill_two_boxes(tmp_path, sync_harness, keyfile, registry,
                              manifest):
    """§4 acceptance: publish a freeze; every box reports state=frozen within
    sync_cadence + ε. Delivery runs through the real gate_sync.sh (hermetic
    ssh/scp stand-ins), and each box is asserted live BEFORE the freeze —
    the drill proves a live→frozen transition, not a permanently-frozen
    fixture."""
    sync_cadence, eps = 2.0, 5.0
    boxes = ["box-01", "box-02"]
    estate = tmp_path / "estate"
    fakeroot = tmp_path / "fakeroot"
    for box in boxes:
        (estate / box).mkdir(parents=True)
        (fakeroot / box / "var" / "lib" / "sparkvm" / "gate").mkdir(
            parents=True)
    env = sync_env(tmp_path, sync_harness, estate)

    def sync(gate):
        e = dict(env)
        e["GATE"] = gate
        r = run("bash", SYNC, env_extra=e)
        assert r.returncode == 0, r.stderr

    def states():
        return {box: query_state(
            str(fakeroot / box / "var" / "lib" / "sparkvm" / "gate"
                / "gate.json"),
            box, keys_spec(keyfile))["state"] for box in boxes}

    # Baseline: a live gate delivers through the sync loop and every box
    # reports live. Without this, "frozen" afterwards proves nothing.
    sync(publish(tmp_path, keyfile, registry, manifest))
    assert states() == {box: "live" for box in boxes}

    # The freeze: publish, deliver, measure wall-clock until all frozen.
    t0 = time.monotonic()
    sync(publish(tmp_path, keyfile, registry, manifest, freeze=True))
    deadline = t0 + sync_cadence + eps
    while time.monotonic() < deadline:
        if all(s == "frozen" for s in states().values()):
            break
        time.sleep(0.2)
    elapsed = time.monotonic() - t0
    assert all(s == "frozen" for s in states().values()), \
        "not all boxes reported frozen before the deadline"
    assert elapsed <= sync_cadence + eps, f"freeze took {elapsed:.1f}s"


# --- pending_range() gate cap (deploy/auto-deploy.sh) -----------------------

def bash_source(code, env_extra=None, cwd=REPO):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        ["bash", "-c",
         "export AUTO_DEPLOY_NO_MAIN=1; source ./deploy/auto-deploy.sh; " + code],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=60)


def fixture_repo(tmp_path):
    repo = tmp_path / "updater-repo"
    repo.mkdir()
    run = lambda *a: subprocess.run(a, cwd=repo, check=True,
                                   capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    run("git", "config", "commit.gpgsign", "false")
    (repo / "f").write_text("1")
    run("git", "add", ".")
    run("git", "commit", "-qm", "one")
    one = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                         capture_output=True, text=True).stdout.strip()
    (repo / "f").write_text("2")
    run("git", "add", ".")
    run("git", "commit", "-qm", "two")
    two = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                         capture_output=True, text=True).stdout.strip()
    (repo / "f").write_text("3")
    run("git", "add", ".")
    run("git", "commit", "-qm", "three")
    three = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True).stdout.strip()
    return str(repo), one, two, three


def gate_env(tmp_path, repo, permitted_commit, box="box-01", freeze=False,
             keys=True, wave_state="complete", wave_live=4,
             wave_assignments=None):
    """Publish a gate whose repo max is `permitted_commit`; return env."""
    key = tmp_path / "ctl.key"
    key.write_bytes(binascii.hexlify(os.urandom(32)))
    os.chmod(key, 0o600)
    reg = {"repo": {"max_permitted_commit": permitted_commit,
                    "channel": "stable"},
           "toolset": {"max_permitted_pin": "2026.09.27", "channel": "stable"},
           "image": {"max_permitted_image_version": "2026.09.29-0",
                     "channel": "stable"}}
    rp = tmp_path / "registry.json"
    rp.write_text(json.dumps(reg))
    man = {c: {"live": wave_live, "state": wave_state,
               "assignments": wave_assignments or {},
               "default": "hash_mod_4"} for c in ("repo", "toolset", "image")}
    mp = tmp_path / "waves.json"
    mp.write_text(json.dumps(man))
    gate = tmp_path / "gate.json"
    r = run(sys.executable, PUBLISH, "--registry", str(rp),
            "--manifest", str(mp), *(["--freeze"] if freeze else []),
            "--key-id", KEY_ID, "--key-file", str(key), "--out", str(gate))
    assert r.returncode == 0, r.stderr
    env = {"UPDATER_REPO": repo,
           "GATE_QUERY": QUERY,
           "SPARKVM_GATE_JSON": str(gate),
           "SPARKVM_BOX_ID": box}
    if keys:
        env["SPARKVM_GATE_KEYS"] = f"{KEY_ID}={key}"
    return env


def test_gate_cap_unmanaged_without_keys(tmp_path):
    repo, one, two, three = fixture_repo(tmp_path)
    env = gate_env(tmp_path, repo, one, keys=False)
    r = bash_source(f'gate_cap "{one}" "{three}"', env_extra=env)
    assert r.returncode == 0
    assert r.stdout.strip() == three  # uncapped
    assert "unmanaged" in r.stderr


def test_gate_cap_caps_at_permitted(tmp_path):
    repo, one, two, three = fixture_repo(tmp_path)
    env = gate_env(tmp_path, repo, two)
    r = bash_source(f'gate_cap "{one}" "{three}"', env_extra=env)
    assert r.returncode == 0
    assert r.stdout.strip() == two  # capped at the permitted commit
    assert "capping" in r.stderr


def test_gate_cap_permitted_already_deployed(tmp_path):
    repo, one, two, three = fixture_repo(tmp_path)
    env = gate_env(tmp_path, repo, two)
    r = bash_source(f'gate_cap "{two}" "{three}"', env_extra=env)
    assert r.returncode == 1  # already at the permitted max: nothing to do


def test_gate_cap_frozen_refuses(tmp_path):
    repo, one, two, three = fixture_repo(tmp_path)
    env = gate_env(tmp_path, repo, two, freeze=True)
    r = bash_source(f'gate_cap "{one}" "{three}"', env_extra=env)
    assert r.returncode == 2
    assert "frozen" in r.stderr


def test_gate_cap_unrelated_max_refuses(tmp_path):
    repo, one, two, three = fixture_repo(tmp_path)
    env = gate_env(tmp_path, repo, "b" * 40)  # not in the repo at all
    r = bash_source(f'gate_cap "{one}" "{three}"', env_extra=env)
    assert r.returncode == 2
    assert "not a commit" in r.stderr


def test_gate_cap_wave_not_live_returns_nothing_to_do(tmp_path):
    # Security B1: the wave permit bit is the rollout control — a box whose
    # wave is not live must not deploy up to the ceiling. Pinned to wave 3
    # while only wave 1 is live: gate_cap returns 1, not a capped range.
    repo, one, two, three = fixture_repo(tmp_path)
    env = gate_env(tmp_path, repo, two, box="pinned-box", wave_state="wave-2",
                   wave_live=1, wave_assignments={"pinned-box": 3})
    r = bash_source(f'gate_cap "{one}" "{three}"', env_extra=env)
    assert r.returncode == 1
    assert "not live" in r.stderr


def test_gate_cap_rollback_refuses_downgrade(tmp_path):
    # Security B2: the gate is a ceiling, not a downgrade order. A
    # max_permitted_commit at or behind the deployed watermark must not
    # rewind the mirror — gate_cap returns 1 (nothing to do), never a
    # backwards range.
    repo, one, two, three = fixture_repo(tmp_path)
    env = gate_env(tmp_path, repo, two)
    r = bash_source(f'gate_cap "{three}" "{three}"', env_extra=env)
    assert r.returncode == 1
    assert "downgrade" in r.stderr
    env = gate_env(tmp_path, repo, one)
    r = bash_source(f'gate_cap "{three}" "{three}"', env_extra=env)
    assert r.returncode == 1
    assert "downgrade" in r.stderr


def test_gate_cap_silent_when_fully_unmanaged(tmp_path):
    # Product B3: a box that was never enrolled gets no per-tick nag — the
    # unmanaged warning fires only on partial provisioning (a gate document
    # present but no keys), which the previous test covers.
    repo, one, two, three = fixture_repo(tmp_path)
    env = gate_env(tmp_path, repo, one, keys=False)
    env["SPARKVM_GATE_JSON"] = str(tmp_path / "nope.json")  # no doc either
    r = bash_source(f'gate_cap "{one}" "{three}"', env_extra=env)
    assert r.returncode == 0
    assert r.stdout.strip() == three  # uncapped
    assert "unmanaged" not in r.stderr


def test_query_rejects_group_readable_key(tmp_path, keyfile, registry,
                                         manifest):
    # Security B4: the MAC is symmetric — every box holds the fleet signing
    # key — so a group/other-readable key file is a minting-capability leak,
    # refused loudly (fail-closed) like the publish side.
    out = publish(tmp_path, keyfile, registry, manifest)
    p = tmp_path / "loose.key"
    p.write_bytes(binascii.hexlify(os.urandom(32)))
    os.chmod(p, 0o640)
    ans = query_state(out, "box-01", f"{KEY_ID}={p}")
    assert ans["state"] == "frozen"
    assert "0600" in ans["reason"]


# --- gate_sync.sh: the operator loop actually executes -----------------------

SYNC = os.path.join(REPO, "fleet", "gate_sync.sh")

# Hermetic ssh/scp stand-ins: they map the remote absolute path into a
# per-host directory under FAKE_SSH_ROOT and emulate exactly the two remote
# commands gate_sync.sh sends (test -d probe, install -m 600 delivery).
FAKE_SSH = """#!/usr/bin/env python3
import os, shlex, subprocess, sys
root = os.environ["FAKE_SSH_ROOT"]
log = os.environ.get("FAKE_SSH_LOG")
args = sys.argv[1:]
tgt = next(a for a in args if "@" in a)
host = tgt.split("@", 1)[1]
cmd = args[args.index(tgt) + 1:]
if log:
    with open(log, "a") as fh:
        fh.write(tgt + " :: " + " ".join(cmd) + "\\n")
def R(p):
    return os.path.join(root, host, p.lstrip("/"))
parts = shlex.split(" ".join(cmd))
try:
    if parts[:2] == ["test", "-d"]:
        sys.exit(0 if os.path.isdir(R(parts[2])) else 1)
    if parts[:3] == ["install", "-m", "600"] and "&&" in parts:
        src, dst = parts[3], parts[4]
        subprocess.run(["install", "-m", "600", "-D", R(src), R(dst)],
                       check=True)
        os.remove(R(src))
        sys.exit(0)
except (OSError, subprocess.CalledProcessError, IndexError):
    sys.exit(1)
sys.exit(0)
"""

FAKE_SCP = """#!/usr/bin/env python3
import os, shutil, sys
root = os.environ["FAKE_SSH_ROOT"]
args = [a for a in sys.argv[1:] if not a.startswith("-")]
src, dest = args[-2], args[-1]
host, path = dest.split(":", 1)
host = host.split("@", 1)[1]
full = os.path.join(root, host, path.lstrip("/"))
os.makedirs(os.path.dirname(full), exist_ok=True)
shutil.copyfile(src, full)
"""


@pytest.fixture()
def sync_harness(tmp_path):
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    (bindir / "ssh").write_text(FAKE_SSH)
    (bindir / "scp").write_text(FAKE_SCP)
    os.chmod(bindir / "ssh", 0o755)
    os.chmod(bindir / "scp", 0o755)
    return str(bindir)


def sync_env(tmp_path, sync_harness, estate, extra=None):
    env = {"GATE": "", "ESTATE": str(estate),
           "FAKE_SSH_ROOT": str(tmp_path / "fakeroot"),
           "FAKE_SSH_LOG": str(tmp_path / "ssh.log"),
           "PATH": sync_harness + os.pathsep + os.environ["PATH"]}
    env.update(extra or {})
    return env


def test_shell_scripts_parse():
    # Engineering: gate_sync.sh shipped with a parse error (an apostrophe
    # inside ${ESTATE:?...}) that no test caught — smoke every shipped .sh.
    for sh in ("fleet/gate_sync.sh", "deploy/auto-deploy.sh"):
        r = run("bash", "-n", os.path.join(REPO, sh))
        assert r.returncode == 0, r.stderr


def test_gate_sync_dry_run(tmp_path, sync_harness, keyfile, registry,
                           manifest):
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    (estate / "box-01" / "ssh-target").write_text("box-01\n")
    (estate / "box-02").mkdir(parents=True)  # no ssh-target: dir name
    gate = publish(tmp_path, keyfile, registry, manifest)
    env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
    r = run("bash", SYNC, "--dry-run", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("would sync") == 2
    assert "root@box-01:" in r.stdout and "root@box-02:" in r.stdout


def test_gate_sync_delivers_atomically_mode_600(tmp_path, sync_harness,
                                                keyfile, registry, manifest):
    # The publisher's 0600 must survive the trip (Security B3): plain scp
    # would land the file at the remote umask. Delivery is via temp name +
    # install -m 600, so a concurrent gate_query never sees a half-written
    # document either.
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    gate = publish(tmp_path, keyfile, registry, manifest)
    fakeroot = tmp_path / "fakeroot"
    (fakeroot / "box-01" / "var" / "lib" / "sparkvm" / "gate").mkdir(
        parents=True)
    env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
    r = run("bash", SYNC, env_extra=env)
    assert r.returncode == 0, r.stderr
    landed = (fakeroot / "box-01" / "var" / "lib" / "sparkvm" / "gate"
              / "gate.json")
    assert landed.exists()
    assert stat.S_IMODE(os.stat(landed).st_mode) == 0o600
    assert landed.read_bytes() == open(gate, "rb").read()
    assert "install -m 600" in open(tmp_path / "ssh.log").read()
    assert "synced box-01" in r.stdout


def test_gate_sync_provisioning_gap_fails_loud(tmp_path, sync_harness, keyfile,
                                              registry, manifest):
    # A missing remote gate dir is a provisioning gap, not a sync gap:
    # loud failure (exit 1), and no other box is affected.
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    gate = publish(tmp_path, keyfile, registry, manifest)
    fakeroot = tmp_path / "fakeroot"
    (fakeroot / "box-01").mkdir(parents=True)  # no gate dir underneath
    env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
    r = run("bash", SYNC, env_extra=env)
    assert r.returncode == 1
    assert "provision it first" in r.stderr


def test_gate_sync_rejects_option_injection(tmp_path, sync_harness, keyfile,
                                           registry, manifest):
    # Estate data becomes a command line: an ssh-target smuggling ssh/scp
    # options (e.g. -oProxyCommand=...) must be refused, not interpolated.
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    (estate / "box-01" / "ssh-target").write_text("-oProxyCommand=evil\n")
    gate = publish(tmp_path, keyfile, registry, manifest)
    env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
    r = run("bash", SYNC, env_extra=env)
    assert r.returncode == 1
    assert "invalid ssh-target" in r.stderr


def test_gate_cap_nonancestor_divergence_refuses(tmp_path):
    # QA M3: a max_permitted_commit that exists in the repo but is not an
    # ancestor of the deploy head (registry disagrees with upstream) must
    # refuse — silently deploying it would converge on a foreign history.
    repo, one, two, three = fixture_repo(tmp_path)
    base = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                          cwd=repo, capture_output=True, text=True,
                          check=True).stdout.strip()
    run = lambda *a: subprocess.run(a, cwd=repo, check=True,
                                   capture_output=True)
    run("git", "checkout", "-qb", "div", one)
    with open(os.path.join(repo, "g"), "w") as fh:
        fh.write("diverged")
    run("git", "add", ".")
    run("git", "commit", "-qm", "diverged")
    div = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                         capture_output=True, text=True,
                         check=True).stdout.strip()
    run("git", "checkout", "-q", base)
    env = gate_env(tmp_path, repo, div)
    r = bash_source(f'gate_cap "{one}" "{three}"', env_extra=env)
    assert r.returncode == 2
    assert "not an ancestor" in r.stderr


def test_gate_cap_query_invocation_failure_refuses(tmp_path):
    # QA M5: gate_query failing to execute is not a gate verdict — the cap
    # must refuse (fail closed), never deploy blind.
    repo, one, two, three = fixture_repo(tmp_path)
    bad = tmp_path / "bad-query.py"
    bad.write_text("#!/usr/bin/env python3\nimport sys; sys.exit(1)\n")
    os.chmod(bad, 0o755)
    env = gate_env(tmp_path, repo, two)
    env["GATE_QUERY"] = str(bad)
    r = bash_source(f'gate_cap "{one}" "{three}"', env_extra=env)
    assert r.returncode == 2
    assert "failed to run" in r.stderr


def test_gate_cap_missing_query_file_unmanaged(tmp_path):
    # QA M4: no installed gate_query.py means the box predates G18 gating —
    # warn and proceed uncapped (pre-G18 behavior), not refuse.
    repo, one, two, three = fixture_repo(tmp_path)
    env = gate_env(tmp_path, repo, two)
    env["GATE_QUERY"] = str(tmp_path / "nope.py")
    r = bash_source(f'gate_cap "{one}" "{three}"', env_extra=env)
    assert r.returncode == 0
    assert r.stdout.strip() == three  # uncapped
    assert "unmanaged" in r.stderr


def test_gate_cap_permitted_equals_new(tmp_path):
    repo, one, two, three = fixture_repo(tmp_path)
    env = gate_env(tmp_path, repo, three)
    r = bash_source(f'gate_cap "{two}" "{three}"', env_extra=env)
    assert r.returncode == 0
    assert r.stdout.strip() == three


def test_permitted_bad_component_is_usage_error(tmp_path, keyfile, registry,
                                               manifest):
    out = publish(tmp_path, keyfile, registry, manifest)
    r = run(sys.executable, QUERY, "--box-id", "box-07",
            "--keys", keys_spec(keyfile), "--gate", out,
            "permitted", "nope")
    assert r.returncode == 2


def pending_range_env(tmp_path, repo, permitted_commit, freeze=False):
    """Hermetic pending_range env: a local 'origin' so fetch_main needs no
    network, and an isolated state dir so no real watermark is read."""
    run = lambda *a: subprocess.run(a, cwd=repo, check=True,
                                   capture_output=True)
    run("git", "remote", "add", "origin", repo)
    run("git", "branch", "-f", "main", "HEAD")  # origin needs a main ref
    env = gate_env(tmp_path, repo, permitted_commit, freeze=freeze)
    env["PINNED_UPSTREAM"] = repo
    env["UPDATER_STATE_DIR"] = str(tmp_path / "state")
    return env


def test_pending_range_first_run_capped_by_gate(tmp_path):
    # Integration: with no watermark, pending_range deploys from the empty
    # tree — but the gate caps the target at max_permitted_commit, so the
    # first run converges on the permitted commit, not origin/main's head.
    repo, one, two, three = fixture_repo(tmp_path)
    env = pending_range_env(tmp_path, repo, two)
    r = bash_source("pending_range", env_extra=env)
    assert r.returncode == 0, r.stderr
    old, new = r.stdout.strip().split()
    assert old == "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    assert new == two


def test_pending_range_first_run_frozen_refuses(tmp_path):
    repo, one, two, three = fixture_repo(tmp_path)
    env = pending_range_env(tmp_path, repo, two, freeze=True)
    r = bash_source("pending_range", env_extra=env)
    assert r.returncode == 2
    assert "frozen" in r.stderr
