"""Tests for the G18 S1a release-gating channel (issue #777).

fleet/gate_publish.py (controller: registry + manifest + freeze -> signed
gate.json), fleet/gate_query.py (box: verify + self-evaluated answer), the
freeze-drill acceptance test (§4: publish a freeze, assert every box in a
2-box fixture reports state=frozen within sync_cadence + ε), and the
pending_range() gate cap in deploy/auto-deploy.sh.

Run from the repo root: python3 -m pytest fleet/test_gate.py -q
"""

import binascii
import errno
import fcntl
import hashlib
import hmac
import json
import os
import stat
import subprocess
import sys
import threading
import time
import uuid

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


def _publish_with_manifest(tmp_path, keyfile, registry, waves):
    p = tmp_path / "waves.json"
    p.write_text(json.dumps(waves))
    out = str(tmp_path / "gate.json")
    return run(sys.executable, PUBLISH, "--registry", registry,
               "--manifest", str(p), "--key-id", KEY_ID,
               "--key-file", keyfile, "--out", out)


def _waves(live, assignments=None):
    return {comp: {"live": live, "state": "wave-2",
                   "assignments": assignments or {}, "default": "hash_mod_4"}
            for comp in ("repo", "toolset", "image")}


def test_publish_refuses_bool_live(tmp_path, keyfile, registry):
    # bool is an int subclass: `live: true` must not silently become 1 (#1324).
    r = _publish_with_manifest(tmp_path, keyfile, registry, _waves(True))
    assert r.returncode != 0
    assert ".live" in r.stderr


def test_publish_refuses_live_above_4(tmp_path, keyfile, registry):
    # The wave model is closed at 0..4; a ceiling above 4 can only permit
    # pins outside the wave model, never a real cohort (#1324).
    r = _publish_with_manifest(tmp_path, keyfile, registry, _waves(99))
    assert r.returncode != 0
    assert ".live" in r.stderr


def test_publish_refuses_negative_assignment(tmp_path, keyfile, registry):
    # A negative pin is <= every live ceiling: an undocumented always-live
    # pin in the fail-unsafe direction (#1324).
    r = _publish_with_manifest(tmp_path, keyfile, registry,
                               _waves(2, {"box-07": -1}))
    assert r.returncode != 0
    assert "assignments" in r.stderr


def test_publish_refuses_assignment_above_4(tmp_path, keyfile, registry):
    # A pin above 4 names a cohort outside the closed wave model: no valid
    # ceiling can ever permit it, so the manifest's meaning is undefined
    # (a typo for pin 1? an undocumented permanent hold?) — refused (#1324).
    r = _publish_with_manifest(tmp_path, keyfile, registry,
                               _waves(2, {"box-07": 99}))
    assert r.returncode != 0
    assert "assignments" in r.stderr


def test_publish_accepts_wave_numbers_0_to_4(tmp_path, keyfile, registry):
    # Boundary control: the full closed range still publishes.
    for live in (0, 1, 2, 3, 4):
        r = _publish_with_manifest(tmp_path, keyfile, registry, _waves(live))
        assert r.returncode == 0, (live, r.stderr)


def test_publish_freeze_flag(tmp_path, keyfile, registry, manifest):
    out = publish(tmp_path, keyfile, registry, manifest, freeze=True)
    assert json.loads(open(out).read())["freeze"] is True


# --- G18 date-pin enforcement (#1647) --------------------------------------

def _registry_with_pin(tmp_path, pin):
    reg = {
        "repo": {"max_permitted_commit": "a" * 40, "channel": "stable"},
        "toolset": {"max_permitted_pin": pin, "channel": "stable"},
        "image": {"max_permitted_image_version": "2026.09.29-0",
                  "channel": "stable"},
    }
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(reg))
    return str(p)


def test_publish_refuses_semver_toolset_pin(tmp_path, keyfile, manifest):
    # The fleet compares pins lexicographically, which misfires on
    # semver (min("1.10.0","1.9.5") == "1.10.0"): a semver max silently
    # ignores the hold. Refused fail-closed at publish (#1647).
    reg = _registry_with_pin(tmp_path, "1.10.0")
    r = run(sys.executable, PUBLISH, "--registry", reg,
            "--manifest", manifest, "--key-id", KEY_ID,
            "--key-file", keyfile, "--out", str(tmp_path / "gate.json"))
    assert r.returncode != 0
    assert "max_permitted_pin" in r.stderr


@pytest.mark.parametrize("pin", ["2026.9.27", "2026.13.01", "2026.00.10",
                                 "2026.09.32", "not-a-pin", "", "2026/09/27",
                                 "2026.09.27\n", " 2026.09.27"])
def test_publish_refuses_malformed_date_pins(tmp_path, keyfile, manifest, pin):
    # Non-zero-padded, out-of-range, or wrongly-shaped pins are all
    # rejected: lexicographic == chronological only for YYYY.MM.DD.
    reg = _registry_with_pin(tmp_path, pin)
    r = run(sys.executable, PUBLISH, "--registry", reg,
            "--manifest", manifest, "--key-id", KEY_ID,
            "--key-file", keyfile, "--out", str(tmp_path / "gate.json"))
    assert r.returncode != 0, pin
    assert "max_permitted_pin" in r.stderr


@pytest.mark.parametrize("pin", ["2026.09.27", "2000.01.01", "2099.12.31"])
def test_publish_accepts_valid_date_pins(tmp_path, keyfile, manifest, pin):
    # Boundary control: well-formed date pins still publish.
    reg = _registry_with_pin(tmp_path, pin)
    r = run(sys.executable, PUBLISH, "--registry", reg,
            "--manifest", manifest, "--key-id", KEY_ID,
            "--key-file", keyfile, "--out", str(tmp_path / "gate.json"))
    assert r.returncode == 0, (pin, r.stderr)


def test_publish_refuses_nonstr_toolset_pin(tmp_path, keyfile, manifest):
    reg = _registry_with_pin(tmp_path, 20260927)
    r = run(sys.executable, PUBLISH, "--registry", reg,
            "--manifest", manifest, "--key-id", KEY_ID,
            "--key-file", keyfile, "--out", str(tmp_path / "gate.json"))
    assert r.returncode != 0
    assert "max_permitted_pin" in r.stderr


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
# per-host directory under FAKE_SSH_ROOT and emulate exactly the remote
# commands gate_sync.sh sends (test -d probe, trap + install -m 600
# delivery, best-effort rm -f cleanup).
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
    # The real remote command is:
    #   trap "rm -f '<tmp>'" EXIT; install -m 600 '<tmp>' '<dst>'
    # shlex collapses the quoting, so install lands at parts[3:6].
    # The EXIT trap is modeled HONESTLY (QA): the tmp is removed on
    # failure only when the command actually installed an EXIT trap
    # naming the tmp. A trap-less command leaves litter on failure —
    # exactly the pre-fix behavior the test must catch.
    if parts[3:6] == ["install", "-m", "600"]:
        src, dst = parts[6], parts[7]
        trap_body = parts[1] if parts[0] == "trap" else ""
        trap_cleans_tmp = ("EXIT" in parts[2] and "rm" in trap_body
                           and src in trap_body)
        fail = os.environ.get("FAKE_SSH_INSTALL_FAIL") == "1"
        try:
            if fail:
                raise subprocess.CalledProcessError(1, "install")
            subprocess.run(["install", "-m", "600", "-D", R(src), R(dst)],
                           check=True)
            # Success path: the old &&-chained rm and the new EXIT trap
            # both remove the tmp.
            os.remove(R(src))
            sys.exit(0)
        except (subprocess.CalledProcessError, OSError):
            if trap_cleans_tmp:
                try:
                    os.remove(R(src))
                except OSError:
                    pass
            sys.exit(1)
    if parts[:2] == ["rm", "-f"]:
        # Best-effort post-scp-failure cleanup: idempotent, always exits 0.
        try:
            os.remove(R(parts[2]))
        except (OSError, IndexError):
            pass
        sys.exit(0)
except (OSError, subprocess.CalledProcessError, IndexError):
    sys.exit(1)
# An unrecognized remote command is a harness bug, not a success: fail
# loudly so future script changes that alter the remote command shape
# break tests instead of silently "succeeding".
sys.stderr.write("FAKE_SSH: unrecognized remote command: "
                 + " ".join(cmd) + "\\n")
sys.exit(99)
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
if os.environ.get("FAKE_SCP_FAIL") == "1":
    # A failed transfer may leave a partial remote file, like real scp.
    with open(full, "wb") as fh:
        fh.write(open(src, "rb").read(8))
    sys.exit(1)
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


def test_gate_sync_probe_failure_warns_and_marks_stale(tmp_path, sync_harness,
                                                       keyfile, registry,
                                                       manifest):
    # #1326: a failed gate-dir probe (box down, or dir genuinely
    # unprovisioned — the loop cannot tell them apart) is the transient
    # class, not the loud-fail class. The run warns, marks per-box
    # staleness, keeps the estate moving, and exits 0 — one down box no
    # longer keeps the operator's cron permanently red.
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    gate = publish(tmp_path, keyfile, registry, manifest)
    fakeroot = tmp_path / "fakeroot"
    (fakeroot / "box-01").mkdir(parents=True)  # no gate dir underneath
    env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
    r = run("bash", SYNC, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "WARNING" in r.stderr
    stale = estate / ".gate_sync_state" / "box-01"
    assert stale.exists(), "per-box staleness record must be written"
    epoch, phase = stale.read_text().strip().split()
    assert epoch.isdigit() and phase == "probe-failed"


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


def test_gate_sync_failed_install_leaves_no_tmp(tmp_path, sync_harness,
                                                keyfile, registry, manifest):
    # #1009(1): an install failure must still clean the remote tmp via the
    # EXIT trap — repeated failures must not accumulate
    # .gate.json.tmp.<pid> litter in the gate dir.
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    gate = publish(tmp_path, keyfile, registry, manifest)
    fakeroot = tmp_path / "fakeroot"
    gatedir = fakeroot / "box-01" / "var" / "lib" / "sparkvm" / "gate"
    gatedir.mkdir(parents=True)
    env = sync_env(tmp_path, sync_harness, estate,
                   {"GATE": gate, "FAKE_SSH_INSTALL_FAIL": "1"})
    r = run("bash", SYNC, env_extra=env)
    # #1326: install failure is transient — warn, mark stale, exit 0.
    assert r.returncode == 0, r.stderr
    assert "WARNING" in r.stderr
    assert "atomic install failed" in r.stderr
    stale = estate / ".gate_sync_state" / "box-01"
    assert stale.exists()
    assert stale.read_text().strip().split()[1] == "install-failed"
    leftovers = [p for p in gatedir.iterdir()
                 if p.name.startswith(".gate.json.tmp.")]
    assert leftovers == []


def test_gate_sync_failed_scp_cleans_partial_tmp(tmp_path, sync_harness,
                                                 keyfile, registry, manifest):
    # #1009(1): a failed scp can leave a partial remote tmp — the script
    # must best-effort remove it (same litter class as a failed install).
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    gate = publish(tmp_path, keyfile, registry, manifest)
    fakeroot = tmp_path / "fakeroot"
    gatedir = fakeroot / "box-01" / "var" / "lib" / "sparkvm" / "gate"
    gatedir.mkdir(parents=True)
    env = sync_env(tmp_path, sync_harness, estate,
                   {"GATE": gate, "FAKE_SCP_FAIL": "1"})
    r = run("bash", SYNC, env_extra=env)
    # #1326: scp failure is transient — warn, mark stale, exit 0.
    assert r.returncode == 0, r.stderr
    assert "WARNING" in r.stderr
    assert "scp failed" in r.stderr
    stale = estate / ".gate_sync_state" / "box-01"
    assert stale.exists()
    assert stale.read_text().strip().split()[1] == "scp-failed"
    leftovers = [p for p in gatedir.iterdir()
                 if p.name.startswith(".gate.json.tmp.")]
    assert leftovers == []
    # The best-effort cleanup ssh actually ran.
    assert "rm -f" in open(tmp_path / "ssh.log").read()


def test_gate_sync_staleness_cleared_on_success(tmp_path, sync_harness, keyfile,
                                               registry, manifest):
    # #1326: transient outages self-heal out of the estate state — a box
    # marked stale by a failed run has its record cleared by the next
    # successful sync.
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    gate = publish(tmp_path, keyfile, registry, manifest)
    fakeroot = tmp_path / "fakeroot"
    gatedir = fakeroot / "box-01" / "var" / "lib" / "sparkvm" / "gate"
    gatedir.mkdir(parents=True)
    env = sync_env(tmp_path, sync_harness, estate,
                   {"GATE": gate, "FAKE_SCP_FAIL": "1"})
    r = run("bash", SYNC, env_extra=env)
    assert r.returncode == 0
    stale = estate / ".gate_sync_state" / "box-01"
    assert stale.exists()
    env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
    r = run("bash", SYNC, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "synced box-01" in r.stdout
    assert not stale.exists(), "staleness record must clear on success"


def test_gate_sync_misconfigured_fails_loud_no_state(tmp_path, sync_harness,
                                                     keyfile, registry,
                                                     manifest):
    # #1326: the misconfigured class stays loud — an invalid ssh-target is
    # operator data under local control, so it exits 1 and writes no
    # staleness record (nothing remote was even attempted).
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    (estate / "box-01" / "ssh-target").write_text("-oProxyCommand=evil\n")
    gate = publish(tmp_path, keyfile, registry, manifest)
    env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
    r = run("bash", SYNC, env_extra=env)
    assert r.returncode == 1
    assert "invalid ssh-target" in r.stderr
    assert not (estate / ".gate_sync_state").exists()


def test_gate_sync_dry_run_writes_no_state(tmp_path, sync_harness, keyfile,
                                           registry, manifest):
    # #1326: --dry-run is a read of intent — it must not create or touch
    # the staleness state.
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    gate = publish(tmp_path, keyfile, registry, manifest)
    env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
    r = run("bash", SYNC, "--dry-run", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert not (estate / ".gate_sync_state").exists()


def test_gate_sync_success_survives_broken_state_dir(tmp_path, sync_harness,
                                                     keyfile, registry,
                                                     manifest):
    # #1326 (QA B3): _clear_stale is best-effort on the success path — a
    # state-dir pathology (here: a directory where the box's staleness
    # record should be — rm -f fails "Is a directory") must not turn a
    # successful sync into a red cron under set -e.
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    gate = publish(tmp_path, keyfile, registry, manifest)
    fakeroot = tmp_path / "fakeroot"
    (fakeroot / "box-01" / "var" / "lib" / "sparkvm" / "gate").mkdir(
        parents=True)
    (estate / ".gate_sync_state" / "box-01").mkdir(parents=True)
    env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
    r = run("bash", SYNC, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "synced box-01" in r.stdout


def test_gate_sync_stale_write_failure_degrades_to_warning(
        tmp_path, sync_harness, keyfile, registry, manifest):
    # #1326: _mark_stale is advisory telemetry — when the state write
    # itself fails, the loop degrades to a warning, never to a red cron.
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    gate = publish(tmp_path, keyfile, registry, manifest)
    fakeroot = tmp_path / "fakeroot"
    (fakeroot / "box-01" / "var" / "lib" / "sparkvm" / "gate").mkdir(
        parents=True)
    (estate / ".gate_sync_state").write_text("not a directory\n")
    env = sync_env(tmp_path, sync_harness, estate,
                   {"GATE": gate, "FAKE_SCP_FAIL": "1"})
    r = run("bash", SYNC, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "could not record staleness" in r.stderr


def test_gate_sync_overlapping_run_exits_loud(tmp_path, sync_harness, keyfile,
                                              registry, manifest):
    # #1009(2): a second overlapping run must exit loudly (exit 2) instead
    # of racing the first. The flock is per-process: killing the holder
    # releases it, so this can never wedge future runs.
    import fcntl
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    lockfile = str(estate / ".gate_sync.lock")
    fd = os.open(lockfile, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        gate = publish(tmp_path, keyfile, registry, manifest)
        env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
        r = run("bash", SYNC, "--dry-run", env_extra=env)
        assert r.returncode == 2
        assert "already" in r.stderr
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def test_gate_sync_lock_releases_between_runs(tmp_path, sync_harness, keyfile,
                                              registry, manifest):
    # The lock is held only for the run's lifetime: sequential runs each
    # acquire it, and the lockfile itself (a dotfile) never glob-matches a
    # box dir, so it can't be mistaken for a box.
    estate = tmp_path / "estate"
    (estate / "box-01").mkdir(parents=True)
    gate = publish(tmp_path, keyfile, registry, manifest)
    env = sync_env(tmp_path, sync_harness, estate, {"GATE": gate})
    for _ in range(2):
        r = run("bash", SYNC, "--dry-run", env_extra=env)
        assert r.returncode == 0, r.stderr
        assert r.stdout.count("would sync") == 1


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


# --- rotation reminders (issue #1008 option (b)) ---------------------------

def publish_with_log(tmp_path, keyfile, registry, manifest, key_id,
                     extra=(), rotation_log=None):
    out = str(tmp_path / "gate.json")
    rlog = rotation_log or str(tmp_path / "rotation_log.json")
    r = run(sys.executable, PUBLISH, "--registry", registry,
            "--manifest", manifest,
            "--key-id", key_id, "--key-file", keyfile, "--out", out,
            "--rotation-log", rlog, *extra)
    assert r.returncode == 0, r.stderr
    return out, rlog, r


def test_rotation_first_publish_is_quiet_baseline(tmp_path, keyfile, registry,
                                                  manifest):
    out, rlog, r = publish_with_log(tmp_path, keyfile, registry, manifest,
                                    KEY_ID)
    assert "ROTATION OPEN" not in r.stderr
    log = json.loads(open(rlog).read())
    assert len(log["rotations"]) == 1
    ev = log["rotations"][0]
    assert ev["from_key_id"] is None and ev["to_key_id"] == KEY_ID
    assert ev["closed_at"] is not None  # baseline: not an open window


def test_rotation_new_key_opens_window(tmp_path, keyfile, registry, manifest):
    _, rlog, _ = publish_with_log(tmp_path, keyfile, registry, manifest,
                                  KEY_ID)
    _, _, r = publish_with_log(tmp_path, keyfile, registry, manifest,
                               "ctl-2026-10")
    assert "ROTATION OPEN" in r.stderr
    assert "ctl-2026-09" in r.stderr  # the old key is named
    assert "runbook step 4" in r.stderr
    log = json.loads(open(rlog).read())
    open_evs = [e for e in log["rotations"] if e["closed_at"] is None]
    assert len(open_evs) == 1
    assert open_evs[0]["from_key_id"] == KEY_ID
    assert open_evs[0]["to_key_id"] == "ctl-2026-10"


def test_rotation_open_window_noted_on_later_publish(tmp_path, keyfile,
                                                     registry, manifest):
    _, rlog, _ = publish_with_log(tmp_path, keyfile, registry, manifest,
                                  KEY_ID)
    publish_with_log(tmp_path, keyfile, registry, manifest, "ctl-2026-10")
    _, _, r = publish_with_log(tmp_path, keyfile, registry, manifest,
                               "ctl-2026-10")
    assert "rotation" in r.stderr and "open" in r.stderr
    assert "WARNING" not in r.stderr  # fresh window: note, not warning


def test_rotation_stale_window_warns(tmp_path, keyfile, registry, manifest):
    _, rlog, _ = publish_with_log(tmp_path, keyfile, registry, manifest,
                                  KEY_ID)
    publish_with_log(tmp_path, keyfile, registry, manifest, "ctl-2026-10")
    # Age the open window past the stale threshold.
    log = json.loads(open(rlog).read())
    log["rotations"][-1]["opened_at"] = "2026-01-01T00:00:00Z"
    open(rlog, "w").write(json.dumps(log))
    _, _, r = publish_with_log(tmp_path, keyfile, registry, manifest,
                               "ctl-2026-10")
    assert "WARNING" in r.stderr
    assert "ctl-2026-09" in r.stderr  # un-retired key named
    assert "--rotation-complete" in r.stderr


def test_rotation_complete_closes_window(tmp_path, keyfile, registry,
                                         manifest):
    _, rlog, _ = publish_with_log(tmp_path, keyfile, registry, manifest,
                                  KEY_ID)
    publish_with_log(tmp_path, keyfile, registry, manifest, "ctl-2026-10")
    r = run(sys.executable, PUBLISH, "--rotation-complete", KEY_ID,
            "--rotation-log", rlog)
    assert r.returncode == 0, r.stderr
    assert "closed" in r.stdout
    log = json.loads(open(rlog).read())
    assert all(e["closed_at"] is not None for e in log["rotations"])
    # Later publishes stay quiet about the closed window.
    _, _, r2 = publish_with_log(tmp_path, keyfile, registry, manifest,
                                "ctl-2026-10")
    assert "WARNING" not in r2.stderr
    assert "rotation" not in r2.stderr


def test_rotation_complete_unknown_key_fails(tmp_path):
    rlog = str(tmp_path / "rotation_log.json")
    r = run(sys.executable, PUBLISH, "--rotation-complete", "ctl-nope",
            "--rotation-log", rlog)
    assert r.returncode != 0
    assert "no open rotation" in r.stderr


def test_rotation_corrupt_ledger_does_not_block_publish(tmp_path, keyfile,
                                                        registry, manifest):
    rlog = str(tmp_path / "rotation_log.json")
    open(rlog, "w").write("{not json")
    _, rlog2, r = publish_with_log(tmp_path, keyfile, registry, manifest,
                                   KEY_ID, rotation_log=rlog)
    assert r.returncode == 0
    assert "WARNING" in r.stderr  # ledger problem is loud...
    assert os.path.exists(rlog2)  # ...but the document still publishes


def test_rotation_chained_windows_all_reported(tmp_path, keyfile, registry,
                                               manifest):
    _, rlog, _ = publish_with_log(tmp_path, keyfile, registry, manifest,
                                  KEY_ID)
    publish_with_log(tmp_path, keyfile, registry, manifest, "ctl-2026-10")
    _, _, r = publish_with_log(tmp_path, keyfile, registry, manifest,
                               "ctl-2026-11")
    assert "STILL" in r.stderr  # the K1->K2 window never closed
    log = json.loads(open(rlog).read())
    open_evs = [e for e in log["rotations"] if e["closed_at"] is None]
    assert len(open_evs) == 2
    # Each open window is reported with its own from -> to pair (not the
    # current publish key attributed to every window).
    _, _, r2 = publish_with_log(tmp_path, keyfile, registry, manifest,
                                "ctl-2026-11")
    assert f"{KEY_ID} -> ctl-2026-10" in r2.stderr
    assert "ctl-2026-10 -> ctl-2026-11" in r2.stderr


def test_rotation_malformed_event_does_not_block_publish(tmp_path, keyfile,
                                                         registry, manifest):
    rlog = str(tmp_path / "rotation_log.json")
    open(rlog, "w").write(json.dumps({
        "ledger_version": 1,
        "rotations": [
            {"from_key_id": "ctl-2026-09", "to_key_id": "ctl-2026-10",
             "opened_at": "not-a-timestamp", "closed_at": None},
            {"to_key_id": "ctl-2026-10"},  # missing opened_at
        ],
    }))
    _, rlog2, r = publish_with_log(tmp_path, keyfile, registry, manifest,
                                   "ctl-2026-10", rotation_log=rlog)
    assert r.returncode == 0
    assert "WARNING" in r.stderr  # malformed events are loud...
    assert "malformed" in r.stderr
    assert os.path.exists(rlog2)  # ...but the document still publishes
    log = json.loads(open(rlog2).read())
    # Malformed events were dropped; the new publish recorded its own event.
    assert all(e.get("opened_at") != "not-a-timestamp"
               for e in log["rotations"])


def test_rotation_unwritable_ledger_does_not_block_publish(tmp_path, keyfile,
                                                           registry, manifest):
    # B1: the release channel never depends on advisory state. A ledger path
    # that cannot be written (here: a directory) is loud on stderr, and the
    # gate document still publishes.
    r = run(sys.executable, PUBLISH, "--registry", registry,
            "--manifest", manifest,
            "--key-id", KEY_ID, "--key-file", keyfile,
            "--out", str(tmp_path / "gate.json"),
            "--rotation-log", str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "WARNING" in r.stderr
    assert "rotation ledger" in r.stderr
    assert os.path.exists(str(tmp_path / "gate.json"))


def test_rotation_complete_chained_is_honest(tmp_path, keyfile, registry,
                                             manifest):
    # B3: closing one window of a chained rotation must not claim the new
    # key is the sole signing key while another window is still open.
    _, rlog, _ = publish_with_log(tmp_path, keyfile, registry, manifest,
                                  KEY_ID)
    publish_with_log(tmp_path, keyfile, registry, manifest, "ctl-2026-10")
    publish_with_log(tmp_path, keyfile, registry, manifest, "ctl-2026-11")
    r = run(sys.executable, PUBLISH, "--rotation-complete", KEY_ID,
            "--rotation-log", rlog)
    assert r.returncode == 0, r.stderr
    assert "STILL OPEN" in r.stdout
    assert "ctl-2026-10->ctl-2026-11" in r.stdout
    assert "sole signing key" not in r.stdout
    # Closing the last window earns the sole-key claim.
    r2 = run(sys.executable, PUBLISH, "--rotation-complete", "ctl-2026-10",
             "--rotation-log", rlog)
    assert r2.returncode == 0, r2.stderr
    assert "sole signing key" in r2.stdout


# --- freeze-hold emitter (G15 S3, issue #1543) ---


def _publish_gate(tmp_path, keyfile, registry, manifest, freeze=False,
                  journal=None):
    out = tmp_path / "gate.json"
    argv = [sys.executable, PUBLISH,
            "--registry", registry, "--manifest", manifest,
            "--key-id", KEY_ID, "--key-file", keyfile,
            "--out", str(out)]
    if freeze:
        argv.append("--freeze")
    if journal is not None:
        argv += ["--journal", str(journal)]
    return run(*argv), out


def _read_journal(path):
    if not os.path.exists(str(path)):
        return []
    with open(str(path), "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _assert_freeze_hold_shape(event, direction):
    assert event["schema"] == "fleet-event/1"
    assert event["kind"] == "freeze-hold"
    assert event["source"] == "controller"
    assert event["outcome"] == "succeeded"
    assert event["trigger"] == "manual"
    assert event["box_id"] is None          # fleet-scoped, not a box
    assert event["component"] is None       # governs all updaters
    assert event["session_epoch"] is None
    assert event["attested"] is False
    assert event["subcomponent"] is None
    assert event["subcomponents"] is None
    assert event["from"] is None and event["to"] is None
    assert event["from_version"] is None and event["to_version"] is None
    assert event["phase"] is None and event["window"] is None
    assert event["rollout"] is None
    # Controller clock IS the collector clock: no clock split to keep.
    assert event["emitted_at"] == event["received_at"]
    assert event["received_at"].endswith("Z")
    assert event["note"] == \
        "fleet freeze %s by the controller (gate_publish.py)" % direction
    parsed = uuid.UUID(event["event_id"])
    assert parsed.version == 5              # deterministic dedup id


def test_freeze_flip_off_to_on_emits_event(tmp_path, keyfile, registry,
                                           manifest):
    journal = tmp_path / "events.jsonl"
    r, _ = _publish_gate(tmp_path, keyfile, registry, manifest,
                         freeze=False, journal=journal)
    assert r.returncode == 0, r.stderr
    assert _read_journal(journal) == []     # no flip: no event
    r, _ = _publish_gate(tmp_path, keyfile, registry, manifest,
                         freeze=True, journal=journal)
    assert r.returncode == 0, r.stderr
    events = _read_journal(journal)
    assert len(events) == 1
    _assert_freeze_hold_shape(events[0], "set")
    assert stat.S_IMODE(os.stat(str(journal)).st_mode) == 0o600


def test_freeze_clear_emits_event(tmp_path, keyfile, registry, manifest):
    journal = tmp_path / "events.jsonl"
    _publish_gate(tmp_path, keyfile, registry, manifest,
                  freeze=True, journal=journal)
    r, _ = _publish_gate(tmp_path, keyfile, registry, manifest,
                         freeze=False, journal=journal)
    assert r.returncode == 0, r.stderr
    events = _read_journal(journal)
    assert len(events) == 1
    _assert_freeze_hold_shape(events[0], "cleared")


def test_no_flip_republish_emits_no_event(tmp_path, keyfile, registry,
                                          manifest):
    journal = tmp_path / "events.jsonl"
    _publish_gate(tmp_path, keyfile, registry, manifest,
                  freeze=True, journal=journal)
    r, _ = _publish_gate(tmp_path, keyfile, registry, manifest,
                         freeze=True, journal=journal)
    assert r.returncode == 0, r.stderr
    assert len(_read_journal(journal)) == 0


def test_default_journal_sits_next_to_out(tmp_path, keyfile, registry,
                                          manifest):
    # No --journal: the flip lands in events.jsonl next to gate.json.
    _publish_gate(tmp_path, keyfile, registry, manifest, freeze=False)
    r, _ = _publish_gate(tmp_path, keyfile, registry, manifest, freeze=True)
    assert r.returncode == 0, r.stderr
    default = tmp_path / "events.jsonl"
    events = _read_journal(default)
    assert len(events) == 1
    assert events[0]["kind"] == "freeze-hold"


def test_corrupt_previous_doc_warns_and_publishes(tmp_path, keyfile, registry,
                                                  manifest):
    journal = tmp_path / "events.jsonl"
    out = tmp_path / "gate.json"
    out.write_text("not json at all {{{")
    r, _ = _publish_gate(tmp_path, keyfile, registry, manifest,
                         freeze=True, journal=journal)
    assert r.returncode == 0, r.stderr
    assert "WARNING" in r.stderr
    assert "freeze-flip detection skipped" in r.stderr
    assert os.path.exists(str(out))         # the publish still landed
    assert _read_journal(journal) == []     # no blind flip event


def test_unwritable_journal_does_not_block_publish(tmp_path, keyfile,
                                                   registry, manifest):
    # The journal is visibility, not enforcement: a journal the tool cannot
    # write is loud on stderr but the gate document still publishes (the
    # rotation-ledger B1 precedent, #1008).
    journal = tmp_path / "events.jsonl"
    _publish_gate(tmp_path, keyfile, registry, manifest,
                  freeze=False, journal=journal)
    if os.path.exists(str(journal)):
        os.remove(str(journal))
    os.mkdir(str(journal))                  # a directory: not appendable
    r, _ = _publish_gate(tmp_path, keyfile, registry, manifest,
                         freeze=True, journal=journal)
    assert r.returncode == 0, r.stderr
    assert "WARNING" in r.stderr
    assert "freeze-hold journal append failed" in r.stderr
    doc = json.loads((tmp_path / "gate.json").read_text())
    assert doc["freeze"] is True


def test_freeze_hold_event_ids_unique_per_emission():
    # Same-second flip pairs must not share an event_id: a future
    # deduping consumer would drop a genuine re-freeze. The per-publish
    # nonce in the UUIDv5 preimage buys uniqueness; exactly-once across
    # retries comes from the prev-state gate, not the id.
    sys.path.insert(0, REPO)
    try:
        from fleet import gate_publish
        ts = "2026-10-18T16:05:55Z"
        e1 = gate_publish.build_freeze_hold_event(False, True, ts, "nonce-a")
        e2 = gate_publish.build_freeze_hold_event(False, True, ts, "nonce-b")
        e3 = gate_publish.build_freeze_hold_event(True, False, ts, "nonce-a")
        assert e1["event_id"] != e2["event_id"]
        assert e1["event_id"] != e3["event_id"]
        assert uuid.UUID(e1["event_id"]).version == 5
    finally:
        sys.path.remove(REPO)


def test_non_utf8_previous_doc_warns_and_publishes(tmp_path, keyfile,
                                                   registry, manifest):
    # Engineering B1 (#1543 review): UnicodeDecodeError is a ValueError
    # sibling, not an OSError — the flip detector's "never exits" contract
    # must cover non-UTF-8 bytes, not just JSON syntax errors.
    journal = tmp_path / "events.jsonl"
    out = tmp_path / "gate.json"
    out.write_bytes(b"\xff\xfe{\"freeze\": true}")
    r, _ = _publish_gate(tmp_path, keyfile, registry, manifest,
                         freeze=True, journal=journal)
    assert r.returncode == 0, r.stderr
    assert "WARNING" in r.stderr
    assert "freeze-flip detection skipped" in r.stderr
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["freeze"] is True
    assert _read_journal(journal) == []


def test_event_schema_matches_collector():
    # gate_publish.py pins EVENT_SCHEMA with a "must match" comment against
    # fleet/events.py; this test makes the comment load-bearing so a schema
    # bump in one module can't silently leave the controller emitting stale
    # schema (Engineering nit, #1543 review).
    sys.path.insert(0, REPO)
    try:
        from fleet import gate_publish
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fleet_events_mod",
            os.path.join(REPO, "fleet", "events.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert gate_publish.EVENT_SCHEMA == mod.EVENT_SCHEMA
    finally:
        sys.path.remove(REPO)


# --- key-file open discipline (security sweep 20261018-1559) ----------------
# O_NOFOLLOW + fstat-on-fd for key reads (the MSP FOLLOW-msp6/msp7
# discipline); the rotation ledger lock taken by close_rotation too; the
# published gate.json 0600 from its first byte.

def test_publish_refuses_symlinked_key(tmp_path, keyfile, registry, manifest):
    link = tmp_path / "link.key"
    os.symlink(keyfile, link)
    out = str(tmp_path / "gate.json")
    r = run(sys.executable, PUBLISH, "--registry", registry,
            "--manifest", manifest,
            "--key-id", KEY_ID, "--key-file", str(link), "--out", out)
    assert r.returncode != 0
    assert "symlink" in r.stderr


def test_query_symlinked_key_is_frozen(tmp_path, keyfile, registry, manifest):
    gate = publish(tmp_path, keyfile, registry, manifest)
    link = tmp_path / "link.key"
    os.symlink(keyfile, link)
    ans = query_state(gate, "box-07", keys_spec(str(link)))
    assert ans["state"] == "frozen"
    assert "symlink" in ans["reason"]


def test_publish_gate_json_created_0600(tmp_path, keyfile, registry, manifest):
    out = publish(tmp_path, keyfile, registry, manifest)
    assert stat.S_IMODE(os.stat(out).st_mode) == 0o600
    assert not os.path.exists(out + ".tmp")  # no publish litter left behind


def _import_gate_publish():
    sys.path.insert(0, REPO)
    try:
        from fleet import gate_publish as gp
    finally:
        sys.path.remove(REPO)
    return gp


def test_rotation_log_symlink_plant_never_redirected(tmp_path):
    # #1719: a pre-planted symlink at <ledger>.tmp must not redirect the
    # ledger write. O_EXCL creation refuses to follow the link; the helper
    # unlinks the plant (retry-once) and the write lands in a real file —
    # the decoy is never touched.
    gp = _import_gate_publish()
    log = str(tmp_path / "ledger.json")
    decoy = str(tmp_path / "decoy")
    with open(decoy, "w") as fh:
        fh.write("planted")
    os.symlink(decoy, log + ".tmp")
    gp._save_rotation_log(log, {"rotations": []})
    assert open(decoy).read() == "planted"  # never written through the link
    assert not os.path.islink(log + ".tmp")  # the plant itself is gone
    assert json.loads(open(log).read()) == {"rotations": []}
    assert stat.S_IMODE(os.stat(log).st_mode) == 0o600  # 0600 from first byte


def test_rotation_log_tmp_directory_fails_loud(tmp_path):
    # #1719: when the tmp path is occupied by something that cannot be
    # unlinked for a retry (a directory), the helper fails LOUD with
    # OSError instead of writing anywhere — the plant can only DoS the
    # write, never redirect it. process_rotation's B1 handler turns this
    # into a loud non-blocking warning; close_rotation lets it propagate.
    gp = _import_gate_publish()
    log = str(tmp_path / "ledger.json")
    os.mkdir(log + ".tmp")
    with pytest.raises(OSError):
        gp._save_rotation_log(log, {"rotations": []})
    assert not os.path.exists(log)  # nothing written, nowhere


def test_atomic_write_stale_tmp_unlinked_and_retried(tmp_path):
    # #1719: a stale REGULAR tmp file from a crashed earlier write is
    # unlinked and retried once — the write proceeds instead of failing.
    gp = _import_gate_publish()
    log = str(tmp_path / "ledger.json")
    with open(log + ".tmp", "w") as fh:
        fh.write("stale litter")
    gp._save_rotation_log(log, {"rotations": []})
    assert json.loads(open(log).read()) == {"rotations": []}
    assert not os.path.exists(log + ".tmp")  # no litter left behind


def test_close_rotation_serializes_on_ledger_lock(tmp_path):
    # close_rotation must take the same ledger lock as process_rotation: a
    # manual close racing a cron publish serializes instead of silently
    # losing the close (the lost update would keep a retired key "open").
    sys.path.insert(0, REPO)
    try:
        from fleet import gate_publish as gp
    finally:
        sys.path.remove(REPO)
    log = str(tmp_path / "gate_rotation_log.json")
    gp.process_rotation("ctl-a", log, 14)  # baseline
    gp.process_rotation("ctl-b", log, 14)  # opens window ctl-a -> ctl-b
    lock_path = log + ".lock"
    assert os.path.exists(lock_path)  # the publish path created the lockfile
    lf = open(lock_path, "w")
    fcntl.flock(lf.fileno(), fcntl.LOCK_EX)  # hold the lock in this thread
    done = []

    def closer():
        t0 = time.monotonic()
        gp.close_rotation("ctl-a", log)
        done.append(time.monotonic() - t0)

    th = threading.Thread(target=closer)
    th.start()
    time.sleep(0.4)
    try:
        assert not done, "close_rotation proceeded without the ledger lock"
    finally:
        # Release; the close may proceed.
        fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
        lf.close()
    th.join(timeout=10)
    assert done, "close_rotation never completed after lock release"
    assert done[0] >= 0.35, "close_rotation did not wait for the lock"
    data = json.loads(open(log).read())
    closed = [e for e in data["rotations"]
              if e.get("from_key_id") == "ctl-a" and e.get("closed_at")]
    assert len(closed) == 1, "the close must land exactly once"


def test_close_rotation_lock_open_failure_is_loud(tmp_path):
    # A ledger path whose lockfile cannot be created (a path component is
    # a regular file — ENOTDIR, fails even as root) refuses LOUDLY: no
    # traceback, non-zero exit, the advertised refusal message.
    blocker = tmp_path / "afile"
    blocker.write_text("x")
    log = str(blocker / "gate_rotation_log.json")
    r = run(sys.executable, PUBLISH, "--rotation-complete", "ctl-old",
            "--rotation-log", log)
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
    assert "cannot lock rotation ledger" in r.stderr


def test_publish_lock_open_failure_warns_but_publishes(tmp_path, keyfile,
                                                       registry, manifest):
    # The ledger is advisory (B1): a lock the publisher cannot take skips
    # the reminders loudly but never blocks the gate document.
    blocker = tmp_path / "afile"
    blocker.write_text("x")
    log = str(blocker / "gate_rotation_log.json")
    out = str(tmp_path / "gate.json")
    r = run(sys.executable, PUBLISH, "--registry", registry,
            "--manifest", manifest,
            "--key-id", KEY_ID, "--key-file", keyfile, "--out", out,
            "--rotation-log", log)
    assert r.returncode == 0, r.stderr
    assert "cannot lock rotation ledger" in r.stderr
    assert os.path.exists(out)


def test_ledger_lock_rejects_planted_symlink(tmp_path):
    """#1755: a pre-planted symlink at the ledger lock path fails loud as
    OSError (ELOOP) at _LedgerLock construction — the flock never moves
    onto the plant target (lock-desync / lock-DoS)."""
    sys.path.insert(0, REPO)
    try:
        from fleet import gate_publish as gp
    finally:
        sys.path.remove(REPO)
    target = tmp_path / "plant-target.txt"
    target.write_text("not the lock")
    log = str(tmp_path / "gate_rotation_log.json")
    os.symlink(target, log + ".lock")
    try:
        gp._LedgerLock(log)
    except OSError as exc:
        assert exc.errno == errno.ELOOP, exc
    else:
        raise AssertionError("planted symlink at the ledger lock path did "
                             "not fail loud (expected ELOOP)")
    assert target.read_text() == "not the lock"
