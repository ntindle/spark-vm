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
    box = "some-box-99"
    expect = int(hashlib.sha256(box.encode()).hexdigest(), 16) % 4
    ans = query_state(out, box, keys_spec(keyfile))
    assert ans["repo_my_wave"] == str(expect)
    # live=4: every wave 0..3 is at or before the live wave.
    assert ans["repo_permitted"] == "true"


def test_wave_not_yet_live_is_not_permitted(tmp_path, keyfile, registry):
    man = wave_manifest(tmp_path, "wave-2", 1, {})
    out = publish(tmp_path, keyfile, registry, man)
    box = "some-box-99"
    my_wave = int(hashlib.sha256(box.encode()).hexdigest(), 16) % 4
    ans = query_state(out, box, keys_spec(keyfile))
    assert ans["repo_permitted"] == ("true" if my_wave <= 1 else "false")


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

def test_freeze_drill_two_boxes(tmp_path, keyfile, registry, manifest):
    """Publish a freeze; every box reports state=frozen within
    sync_cadence + ε. The drill tests *delivery*; effectuation is bounded
    by §4's contract (sync_cadence + tick_interval), not by the drill."""
    sync_cadence, eps = 2.0, 5.0
    boxes = ["box-01", "box-02"]
    box_dirs = {}
    for box in boxes:
        d = tmp_path / box / "gate"
        d.mkdir(parents=True)
        box_dirs[box] = str(d / "gate.json")

    t0 = time.monotonic()
    gate = publish(tmp_path, keyfile, registry, manifest, freeze=True)
    # Simulated delivery: the operator sync loop copies the document to
    # each box. The copy itself is fast; the bound under test is the
    # delivery latency (here: immediate) plus the query cadence.
    time.sleep(0.5)  # delivery latency < sync_cadence
    for box in boxes:
        with open(gate, "rb") as fh:
            data = fh.read()
        with open(box_dirs[box], "wb") as fh:
            fh.write(data)

    deadline = t0 + sync_cadence + eps
    frozen = set()
    while time.monotonic() < deadline and len(frozen) < len(boxes):
        for box in boxes:
            if box in frozen:
                continue
            ans = query_state(box_dirs[box], box, keys_spec(keyfile))
            if ans["state"] == "frozen":
                frozen.add(box)
        time.sleep(0.2)
    elapsed = time.monotonic() - t0
    assert frozen == set(boxes), f"only {frozen} froze before the deadline"
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
             keys=True):
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
    man = {c: {"live": 4, "state": "complete", "assignments": {},
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
