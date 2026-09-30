#!/usr/bin/env python3
"""Tests for harness/key_registry.py — SSH-key-as-account registry (GH #446, S2).

Every test runs against a fresh tmp_path registry root: the module never
touches the real $XDG_STATE_HOME store in tests. Time is frozen via
monkeypatching key_registry._utcnow for last_seen assertions.
"""
import datetime
import hashlib
import json
import os
import stat
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import key_registry
from key_registry import KeyIdentityError, KeyRegistry, RegistryError, normalize_fingerprint

ED25519_LINE = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIMLPKSGVS4GNm00i/S4BebZ+whw9lGn5GReUs0en5e69 "
    "s2-test-key"
)
ED25519_FP = "SHA256:WhVCxQzbxruL4xmoksmRPBJna6BQ5vRa9XG1Yi+hniA"

RSA_LINE = (
    "ssh-rsa "
    "AAAAB3NzaC1yc2EAAAADAQABAAABAQC7vK9f4sZ9d1qF3mH6kL0pR8tV2wX4yZ6aB8cD0eF2gH4jK6lM8nO0pQ2rS4tU6vW8xY0zA1bC3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zB7dF9hJ1lN3pR5tV7xZ9bD1fH3jL5nP7rT9vX1zC3eG5iK7mO9qS1uW3yA5cE7gI9kM1oQ3sU5wY7aC9eG1iK3mO5qS7uW9yB1dF3hJ5lN7pR9tV1xZ3bD5fH7jL9nP1rT3vX5zD7fH9jL1nP3rT5vX7zE8gI0kM2oQ4sU6wY8aC0eG2iK4mO6qS8uW0yC2eG4iK6mO8qS0uW2yD3fH5jL7nP9rT1vX3zF4gH6jL8nP0rT2vX4zG5hI7jK9lM1nO3pQ5rS7tU9vW1xY3zH6iJ8kL0mN2oP4qR6sT8tU0vV2wX4yZ6 "
    "s2-test-rsa"
)
# The RSA fingerprint is computed via S1's fingerprint() — keeps the test honest.
def _rsa_fp():
    return key_registry.fingerprint(key_registry.key_identity.parse_public_key(RSA_LINE))


@pytest.fixture()
def reg(tmp_path):
    return KeyRegistry(root=tmp_path / "registry")


def _frozen(monkeypatch, iso):
    dt = datetime.datetime.fromisoformat(iso)
    monkeypatch.setattr(key_registry, "_utcnow", lambda: dt)


# -- normalize_fingerprint ----------------------------------------------------
def test_normalize_accepts_s1_fingerprint():
    assert normalize_fingerprint(ED25519_FP) == ED25519_FP


def test_normalize_rejects_garbage():
    padded = ED25519_FP + "="  # S1 never emits padding; a padded twin would
    short = ED25519_FP[:-1]  # canonical form is exactly 43 base64 chars
    for bad in ("", "md5:aa:bb", "SHA256:", "SHA256:not base64!!!", padded,
                short, ED25519_FP + "X", None, 42):
        with pytest.raises(KeyIdentityError):
            normalize_fingerprint(bad)


def test_padded_fingerprint_derives_different_account_id():
    # The regression this guards: padded input must never reach the store,
    # because padded and unpadded forms derive DIFFERENT acct_ ids for the
    # same key (would mint a second identity for one key).
    from key_identity import account_id_for

    assert account_id_for(ED25519_FP) != account_id_for(ED25519_FP + "=")


# -- register / lookup ----------------------------------------------------------
def test_register_creates_record_with_derived_account_id(reg):
    rec = reg.register(key_line=ED25519_LINE, box_ref="box-1")
    assert rec["fingerprint"] == ED25519_FP
    assert rec["account_id"] == key_registry.account_id_for(ED25519_FP)
    assert rec["key_type"] == "ssh-ed25519"
    assert rec["box_ref"] == "box-1"
    # claim is a later slice (S3); S2 records no claim state
    assert "claimed" not in rec and "claimed_at" not in rec
    assert rec["created_at"] == rec["last_seen_at"]


def test_register_is_idempotent(reg):
    first = reg.register(key_line=ED25519_LINE)
    second = reg.register(key_line=ED25519_LINE)
    assert second["account_id"] == first["account_id"]
    assert second["created_at"] == first["created_at"]
    assert len(reg.accounts()) == 1


def test_register_refreshes_last_seen(reg, monkeypatch):
    _frozen(monkeypatch, "2026-09-27T10:00:00+00:00")
    reg.register(key_line=ED25519_LINE)
    _frozen(monkeypatch, "2026-09-27T12:00:00+00:00")
    rec = reg.register(key_line=ED25519_LINE)
    assert rec["last_seen_at"] == "2026-09-27T12:00:00+00:00"


def test_register_by_fingerprint_needs_key_type(reg):
    with pytest.raises(RegistryError):
        reg.register(fingerprint_str=ED25519_FP)
    rec = reg.register(fingerprint_str=ED25519_FP, key_type="ssh-ed25519")
    assert rec["account_id"] == key_registry.account_id_for(ED25519_FP)


def test_register_rejects_key_type_mismatch(reg):
    reg.register(key_line=ED25519_LINE)
    with pytest.raises(RegistryError):
        reg.register(fingerprint_str=ED25519_FP, key_type="ssh-rsa")


def test_register_rejects_empty_box_ref(reg):
    with pytest.raises(RegistryError):
        reg.register(key_line=ED25519_LINE, box_ref="")


def test_bind_box_rejects_empty_box_ref(reg):
    reg.register(key_line=ED25519_LINE)
    with pytest.raises(RegistryError):
        reg.bind_box(ED25519_FP, "")


def test_register_rebinds_box_only_when_provided(reg):
    reg.register(key_line=ED25519_LINE, box_ref="box-1")
    rec = reg.register(key_line=ED25519_LINE)  # no box_ref: binding untouched
    assert rec["box_ref"] == "box-1"
    rec = reg.register(key_line=ED25519_LINE, box_ref="box-2")
    assert rec["box_ref"] == "box-2"


def test_register_rejects_bad_key_line(reg):
    with pytest.raises(KeyIdentityError):
        reg.register(key_line="not a key")


def test_register_needs_exactly_one_input(reg):
    with pytest.raises(RegistryError):
        reg.register()
    with pytest.raises(RegistryError):
        reg.register(key_line=ED25519_LINE, fingerprint_str=ED25519_FP)


def test_lookup_unknown_returns_none(reg):
    assert reg.lookup(ED25519_FP) is None


def test_lookup_round_trip(reg):
    reg.register(key_line=ED25519_LINE, box_ref="box-9")
    rec = reg.lookup(ED25519_FP)
    assert rec["box_ref"] == "box-9"
    assert rec["account_id"].startswith("acct_")


def test_lookup_returns_copy(reg):
    reg.register(key_line=ED25519_LINE)
    rec = reg.lookup(ED25519_FP)
    rec["box_ref"] = "mutated"
    assert reg.lookup(ED25519_FP).get("box_ref") is None  # store untouched


# -- touch / claim / bind / remove -------------------------------------------------
def test_touch(reg, monkeypatch):
    assert reg.touch(ED25519_FP) is False
    _frozen(monkeypatch, "2026-09-27T10:00:00+00:00")
    reg.register(key_line=ED25519_LINE)
    _frozen(monkeypatch, "2026-09-27T11:00:00+00:00")
    assert reg.touch(ED25519_FP) is True
    assert reg.lookup(ED25519_FP)["last_seen_at"] == "2026-09-27T11:00:00+00:00"


def test_bind_box(reg):
    assert reg.bind_box(ED25519_FP, "box-x") is False
    reg.register(key_line=ED25519_LINE)
    assert reg.bind_box(ED25519_FP, "box-x") is True
    assert reg.lookup(ED25519_FP)["box_ref"] == "box-x"


def test_remove(reg):
    assert reg.remove(ED25519_FP) is False
    reg.register(key_line=ED25519_LINE)
    assert reg.remove(ED25519_FP) is True
    assert reg.lookup(ED25519_FP) is None


def test_accounts_sorted_oldest_first(reg, monkeypatch):
    _frozen(monkeypatch, "2026-09-27T10:00:00+00:00")
    reg.register(key_line=ED25519_LINE)
    _frozen(monkeypatch, "2026-09-27T09:00:00+00:00")
    fp2 = _rsa_fp()
    reg.register(fingerprint_str=fp2, key_type="ssh-rsa")
    fps = [r["fingerprint"] for r in reg.accounts()]
    assert fps == [fp2, ED25519_FP]


# -- durability --------------------------------------------------------------------
def test_file_perms(reg):
    reg.register(key_line=ED25519_LINE)
    st = reg.store_path.stat()
    assert stat.S_IMODE(st.st_mode) == 0o600
    assert stat.S_IMODE(reg.root.stat().st_mode) == 0o700


def test_corrupt_registry_fails_closed(reg):
    reg.root.mkdir(parents=True, exist_ok=True)
    reg.store_path.write_text("{not json")
    with pytest.raises(RegistryError):
        reg.lookup(ED25519_FP)


def test_wrong_shape_registry_fails_closed(reg):
    reg.root.mkdir(parents=True, exist_ok=True)
    reg.store_path.write_text('["a list, not an object"]')
    with pytest.raises(RegistryError):
        reg.accounts()


def test_bad_record_shape_fails_closed(reg):
    reg.root.mkdir(parents=True, exist_ok=True)
    reg.store_path.write_text(
        json.dumps({"schema_version": 1, "accounts": {ED25519_FP: "not-a-dict"}})
    )
    with pytest.raises(RegistryError):
        reg.lookup(ED25519_FP)


def test_wrong_schema_version_fails_closed(reg):
    reg.root.mkdir(parents=True, exist_ok=True)
    reg.store_path.write_text(
        json.dumps({"schema_version": 999, "accounts": {}})
    )
    with pytest.raises(RegistryError):
        reg.accounts()


def test_leftover_tmp_file_does_not_break_fresh_register(reg):
    reg.root.mkdir(parents=True, exist_ok=True)
    (reg.root / "registry.json.tmp.99999").write_text("{half")
    rec = reg.register(key_line=ED25519_LINE)
    assert rec["fingerprint"] == ED25519_FP
    assert reg.lookup(ED25519_FP)["account_id"] == rec["account_id"]


def test_concurrent_registers_stay_consistent(reg):
    fps = []
    for i in range(8):
        line = f"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI{i:02d}" + "A" * 40 + f" key-{i}"
        # NOTE: these blobs are not valid ed25519 keys; register via fingerprint
        # path instead, deriving the fp from a hash of the line.
        import hashlib, base64

        digest = hashlib.sha256(line.encode()).digest()
        fps.append("SHA256:" + base64.b64encode(digest).decode().rstrip("="))
    errors = []

    def work(fp):
        try:
            for _ in range(5):
                KeyRegistry(root=reg.root).register(
                    fingerprint_str=fp, key_type="ssh-ed25519"
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(fp,)) for fp in fps for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors[:3]
    got = {r["fingerprint"] for r in reg.accounts()}
    assert got == set(fps)


def test_stale_lock_is_reclaimed(reg):
    reg.root.mkdir(parents=True, exist_ok=True)
    reg.lock_path.mkdir()
    (reg.lock_path / "pid").write_text("999999999")  # certainly dead
    rec = reg.register(key_line=ED25519_LINE)
    assert rec["fingerprint"] == ED25519_FP
    assert not reg.lock_path.exists()


def test_live_lock_times_out_loud(reg, monkeypatch):
    monkeypatch.setattr(key_registry, "LOCK_TIMEOUT_S", 0.2)
    monkeypatch.setattr(key_registry, "_LOCK_POLL_S", 0.05)
    reg.root.mkdir(parents=True, exist_ok=True)
    reg.lock_path.mkdir()
    (reg.lock_path / "pid").write_text(str(os.getpid()))  # our own pid: alive
    with pytest.raises(RegistryError):
        reg.register(key_line=ED25519_LINE)


# -- CLI ---------------------------------------------------------------------------
def _cli(subcommand, *args, root=None, env=None):
    # --registry-root works in either position (before or after the
    # subcommand); this helper passes it before, and
    # test_cli_registry_root_accepted_after_subcommand covers after.
    cmd = [sys.executable, "key_registry.py"]
    if root is not None:
        cmd += ["--registry-root", root]
    cmd += [subcommand, *args]
    return subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_register_lookup_round_trip(tmp_path):
    root = str(tmp_path / "cli-reg")
    r = _cli("register", "--key-line", ED25519_LINE, root=root)
    assert r.returncode == 0, r.stderr
    # Pin the location: --registry-root before the subcommand must actually
    # select the root (a subparser-default clobber once sent these writes
    # to the default root while every CLI test still passed, because
    # register and lookup resolved to the same wrong place).
    assert (tmp_path / "cli-reg" / "registry.json").is_file()
    rec = json.loads(r.stdout)
    assert rec["fingerprint"] == ED25519_FP
    r = _cli("lookup", ED25519_FP, root=root)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["account_id"] == rec["account_id"]


def test_cli_registry_root_before_subcommand_selects_root(tmp_path):
    # The exact QA delta-round regression: --registry-root in the global
    # position must not be silently clobbered by the subparser default.
    root = tmp_path / "before"
    cmd = [sys.executable, "key_registry.py", "--registry-root", str(root),
           "register", "--key-line", ED25519_LINE, "--box-ref", "box-b"]
    r = subprocess.run(
        cmd, cwd=Path(__file__).resolve().parent,
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    store = root / "registry.json"
    assert store.is_file(), "register did not write to the --registry-root dir"
    rec = json.loads(store.read_text())["accounts"][ED25519_FP]
    assert rec["box_ref"] == "box-b"


def test_cli_registry_root_accepted_after_subcommand(tmp_path):
    # Regression: --registry-root is a per-command flag too, not only global.
    root = str(tmp_path / "after")
    cmd = [sys.executable, "key_registry.py", "register",
           "--key-line", ED25519_LINE, "--registry-root", root]
    r = subprocess.run(
        cmd, cwd=Path(__file__).resolve().parent,
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["fingerprint"] == ED25519_FP
    assert (tmp_path / "after" / "registry.json").is_file()


def test_cli_manifest_and_remove(tmp_path):
    root = str(tmp_path / "cr")
    r = _cli("register", "--key-line", ED25519_LINE, "--box-ref", "box-9",
             root=root)
    assert r.returncode == 0, r.stderr
    r = _cli("manifest", ED25519_FP, root=root)
    assert r.returncode == 0, r.stderr
    m = json.loads(r.stdout)
    assert m["registry_issued"] is True
    assert m["box_id"] == "box-9"
    assert m["account_id"] == json.loads(
        _cli("lookup", ED25519_FP, root=root).stdout)["account_id"]
    assert m["vm_endpoint"] is None and m["claim_url"] is None
    r = _cli("manifest", _rsa_fp(), root=root)
    assert r.returncode == 1
    r = _cli("remove", ED25519_FP, root=root)
    assert r.returncode == 0, r.stderr
    r = _cli("lookup", ED25519_FP, root=root)
    assert r.returncode == 1


def test_default_root_honors_xdg_state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    reg2 = KeyRegistry()
    assert reg2.root == tmp_path / "xdg" / "spark-vm" / "key-registry"


# -- rotate (slice S2.5: key rotation with lineage, GH #446) --------------------
# Five real ed25519 keys (ssh-keygen, comments rot-test-key-N). Fingerprints
# are computed through the module (the RSA pattern), never hand-copied, so
# a drift between line and fingerprint fails loudly.
ROT_LINE_1 = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIBqZgPvZlLJBHCs1vZ+FLOXh6wIVkJEMV/6fYZKTNsyk "
    "rot-test-key-1"
)
ROT_LINE_2 = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIDKqI1gdbmLmAo4OHLsQ3+mE0sx44XCiJsbvotBqhusY "
    "rot-test-key-2"
)
ROT_LINE_3 = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIPTNuffNdBD/uFzxLr+LghWTAForqSvmrv0yQ7ItN3SI "
    "rot-test-key-3"
)
ROT_LINE_4 = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIBobeRpKQ/cptC58h8sTnZsDwDdDaOOndO+g1QnRKFwY "
    "rot-test-key-4"
)
ROT_LINE_5 = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIPiHsysmEftD4DKjkEQ8r2F1Kii7A5Y9SqsTmlPifAct "
    "rot-test-key-5"
)
_ROT_LINES = (ROT_LINE_1, ROT_LINE_2, ROT_LINE_3, ROT_LINE_4, ROT_LINE_5)


def _rot_fp(line):
    return key_registry.fingerprint(key_registry.key_identity.parse_public_key(line))


def _rot_fp_of(n):
    return _rot_fp(_ROT_LINES[n - 1])


def test_rotations_journal_empty_initially(reg):
    assert reg.rotations() == []


def test_rotate_happy_path(reg, monkeypatch):
    _frozen(monkeypatch, "2026-09-27T10:00:00+00:00")
    old_fp = _rot_fp_of(1)
    reg.register(key_line=ROT_LINE_1, box_ref="box-1")
    _frozen(monkeypatch, "2026-09-27T12:00:00+00:00")
    new_fp = _rot_fp_of(2)
    out = reg.rotate(old_fp, key_line=ROT_LINE_2)

    new = out["new"]
    old = out["old"]
    entry = out["rotation"]
    # S1 policy: a new key is a NEW account — rotation links, never preserves.
    assert new["fingerprint"] == new_fp
    assert new["account_id"] == key_registry.account_id_for(new_fp)
    assert new["account_id"] != key_registry.account_id_for(old_fp)
    assert new["key_type"] == "ssh-ed25519"
    # box continuity survives the rotation
    assert new["box_ref"] == "box-1"
    assert new["created_at"] == "2026-09-27T12:00:00+00:00"
    # old record is stamped, not deleted
    assert old["fingerprint"] == old_fp
    assert old["rotated_to"] == new_fp
    assert old["rotated_at"] == "2026-09-27T12:00:00+00:00"
    # rotation itself does not advance the record's last_seen_at — the
    # rotation is recorded in rotated_at (liveness via touch/re-register
    # still updates last_seen_at afterwards)
    assert old["last_seen_at"] == "2026-09-27T10:00:00+00:00"
    assert "rotated_to" not in new and "rotated_at" not in new
    # the journal is the audit trail
    assert entry == {
        "old_fingerprint": old_fp,
        "old_account_id": key_registry.account_id_for(old_fp),
        "new_fingerprint": new_fp,
        "new_account_id": new["account_id"],
        "key_type": "ssh-ed25519",
        "box_ref": "box-1",
        "rotated_at": "2026-09-27T12:00:00+00:00",
    }
    assert reg.rotations() == [entry]


def test_rotate_unknown_old_fingerprint_raises(reg):
    with pytest.raises(RegistryError):
        reg.rotate(_rot_fp_of(1), key_line=ROT_LINE_2)
    # nothing minted: rotation never implicitly registers
    assert reg.accounts() == [] and reg.rotations() == []


def test_rotate_already_registered_new_key_raises(reg):
    old_fp = _rot_fp_of(1)
    new_fp = _rot_fp_of(2)
    reg.register(key_line=ROT_LINE_1)
    reg.register(key_line=ROT_LINE_2)
    with pytest.raises(RegistryError):
        reg.rotate(old_fp, key_line=ROT_LINE_2)
    # old record untouched — no silent account merge happened
    assert "rotated_to" not in reg.lookup(old_fp)
    assert reg.rotations() == []


def test_rotate_same_key_raises(reg):
    old_fp = _rot_fp_of(1)
    reg.register(key_line=ROT_LINE_1)
    with pytest.raises(RegistryError):
        reg.rotate(old_fp, key_line=ROT_LINE_1)
    assert "rotated_to" not in reg.lookup(old_fp)


def test_rotate_rejects_malformed_input(reg):
    reg.register(key_line=ROT_LINE_1)
    with pytest.raises(KeyIdentityError):
        reg.rotate("SHA256:not base64!!!", key_line=ROT_LINE_2)
    with pytest.raises(KeyIdentityError):
        reg.rotate(_rot_fp_of(1), key_line="ssh-ed25519 not-base64 rot-test")


def test_rotate_lookup_old_shows_forward_link(reg):
    old_fp = _rot_fp_of(1)
    new_fp = _rot_fp_of(2)
    reg.register(key_line=ROT_LINE_1)
    reg.rotate(old_fp, key_line=ROT_LINE_2)
    # the link is followed, never silently dereferenced
    assert reg.lookup(old_fp)["rotated_to"] == new_fp
    assert reg.lookup(new_fp)["account_id"] != reg.lookup(old_fp)["account_id"]


def test_rotate_reregistering_old_key_keeps_lineage(reg, monkeypatch):
    old_fp = _rot_fp_of(1)
    new_fp = _rot_fp_of(2)
    _frozen(monkeypatch, "2026-09-27T10:00:00+00:00")
    reg.register(key_line=ROT_LINE_1)
    reg.rotate(old_fp, key_line=ROT_LINE_2)
    _frozen(monkeypatch, "2026-09-27T14:00:00+00:00")
    # rotation is lineage, not a ban: the old key can still check in
    rec = reg.register(key_line=ROT_LINE_1)
    assert rec["rotated_to"] == new_fp
    assert rec["last_seen_at"] == "2026-09-27T14:00:00+00:00"


def test_rotate_touch_after_rotation_still_works(reg):
    old_fp = _rot_fp_of(1)
    reg.register(key_line=ROT_LINE_1)
    reg.rotate(old_fp, key_line=ROT_LINE_2)
    assert reg.touch(old_fp) is True


def test_rotate_persists_across_reload(reg, tmp_path):
    old_fp = _rot_fp_of(1)
    new_fp = _rot_fp_of(2)
    reg.register(key_line=ROT_LINE_1, box_ref="box-9")
    entry = reg.rotate(old_fp, key_line=ROT_LINE_2)["rotation"]
    reloaded = KeyRegistry(root=tmp_path / "registry")
    assert reloaded.lookup(old_fp)["rotated_to"] == new_fp
    assert reloaded.lookup(new_fp)["box_ref"] == "box-9"
    assert reloaded.rotations() == [entry]


def test_rotate_chains_and_journal_is_bounded(reg, monkeypatch):
    # monkeypatch the cap small: the bound must be enforced by the code,
    # not by the size of the fixture set.
    monkeypatch.setattr(key_registry, "ROTATIONS_CAP", 3)
    monkeypatch.setattr(key_registry, "_utcnow",
                        lambda: datetime.datetime.now(datetime.timezone.utc))
    fps = [_rot_fp_of(n) for n in range(1, 6)]
    reg.register(key_line=ROT_LINE_1, box_ref="box-chain")
    for n in range(2, 6):
        reg.rotate(fps[n - 2], key_line=_ROT_LINES[n - 1])
    journal = reg.rotations()
    # 4 rotations happened; the journal keeps the newest 3, oldest first
    assert len(journal) == 3
    assert [e["old_fingerprint"] for e in journal] == fps[1:4]
    assert [e["new_fingerprint"] for e in journal] == fps[2:5]
    assert all(e["box_ref"] == "box-chain" for e in journal)
    # lineage chains forward on the records themselves (never journal-capped)
    assert reg.lookup(fps[0])["rotated_to"] == fps[1]
    assert reg.lookup(fps[3])["rotated_to"] == fps[4]
    assert "rotated_to" not in reg.lookup(fps[4])


def test_rotate_cli_round_trip(tmp_path):
    root = str(tmp_path / "cli-rot")
    old_fp = _rot_fp_of(1)
    r = _cli("register", "--key-line", ROT_LINE_1, "--box-ref", "box-cli", root=root)
    assert r.returncode == 0, r.stderr
    r = _cli("rotate", old_fp, "--key-line", ROT_LINE_2, root=root)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["old"]["rotated_to"] == _rot_fp_of(2)
    assert out["new"]["box_ref"] == "box-cli"
    assert out["rotation"]["old_fingerprint"] == old_fp
    r = _cli("lookup", old_fp, root=root)
    assert json.loads(r.stdout)["rotated_to"] == _rot_fp_of(2)


def test_rotate_cli_unknown_old_fails_loud(tmp_path):
    root = str(tmp_path / "cli-rot-err")
    r = _cli("rotate", _rot_fp_of(1), "--key-line", ROT_LINE_2, root=root)
    assert r.returncode == 2
    assert "unknown old fingerprint" in r.stderr


def test_rotate_on_corrupt_store_fails_closed(reg):
    # rotate() is the first mutating path to hit the new _load rotations
    # validation: a corrupt store must refuse, not reset or mint.
    reg.register(key_line=ROT_LINE_1)
    reg.store_path.write_text("{not json")
    with pytest.raises(RegistryError):
        reg.rotate(_rot_fp_of(1), key_line=ROT_LINE_2)
    # the failed write minted nothing and touched nothing
    assert reg.store_path.read_text() == "{not json"


def test_junk_rotations_journal_fails_closed(reg):
    reg.register(key_line=ROT_LINE_1)
    reg.store_path.write_text(
        json.dumps({"schema_version": 1, "accounts": {}, "rotations": "junk"})
    )
    with pytest.raises(RegistryError):
        reg.rotations()
    with pytest.raises(RegistryError):
        reg.rotate(_rot_fp_of(1), key_line=ROT_LINE_2)


def test_rotate_already_rotated_key_refuses(reg):
    # record pointer and journal must never diverge on who the current key
    # is: rotate the LATEST key, never an ancestor.
    old_fp = _rot_fp_of(1)
    mid_fp = _rot_fp_of(2)
    reg.register(key_line=ROT_LINE_1)
    reg.rotate(old_fp, key_line=ROT_LINE_2)
    with pytest.raises(RegistryError):
        reg.rotate(old_fp, key_line=ROT_LINE_3)
    # nothing changed: the pointer still names the first hop, the journal
    # holds exactly one entry
    assert reg.lookup(old_fp)["rotated_to"] == mid_fp
    assert len(reg.rotations()) == 1
    # the forward path still works
    out = reg.rotate(mid_fp, key_line=ROT_LINE_3)
    assert out["new"]["fingerprint"] == _rot_fp_of(3)
    assert len(reg.rotations()) == 2


def test_rotate_rejects_missing_key_line(reg):
    reg.register(key_line=ROT_LINE_1)
    with pytest.raises(RegistryError):
        reg.rotate(_rot_fp_of(1), key_line=None)
    with pytest.raises(RegistryError):
        reg.rotate(_rot_fp_of(1), key_line="   ")


def test_rotate_inherits_absent_box_binding(reg):
    # box_ref=None is not "unbound": rotate propagates it, never invents one.
    new_fp = _rot_fp_of(2)
    reg.register(key_line=ROT_LINE_1)
    out = reg.rotate(_rot_fp_of(1), key_line=ROT_LINE_2)
    assert out["new"]["box_ref"] is None
    assert out["rotation"]["box_ref"] is None
    assert reg.lookup(new_fp)["box_ref"] is None


def test_rotate_chain_journal_timestamps_ordered(reg, monkeypatch):
    # per-hop frozen times: the journal's "oldest first" claim holds on
    # timestamps as well as on fingerprints.
    fps = [_rot_fp_of(n) for n in range(1, 4)]
    times = [
        "2026-09-27T10:00:00+00:00",
        "2026-09-27T11:00:00+00:00",
        "2026-09-27T12:00:00+00:00",
    ]
    for t in times:
        _frozen(monkeypatch, t)
        if t == times[0]:
            reg.register(key_line=ROT_LINE_1)
        else:
            reg.rotate(fps[times.index(t) - 1], key_line=_ROT_LINES[times.index(t)])
    journal = reg.rotations()
    assert [e["rotated_at"] for e in journal] == times[1:]
    assert journal == sorted(journal, key=lambda e: e["rotated_at"])


def test_rotate_cli_malformed_key_line_fails_clean(tmp_path):
    root = str(tmp_path / "cli-rot-bad")
    old_fp = _rot_fp_of(1)
    r = _cli("register", "--key-line", ROT_LINE_1, root=root)
    assert r.returncode == 0, r.stderr
    r = _cli("rotate", old_fp, "--key-line", "ssh-ed25519 not-base64 rot-test", root=root)
    assert r.returncode == 2
    assert "error:" in r.stderr
    assert "Traceback" not in r.stderr


# -- claim protocol (slice S3, #446) ----------------------------------------------
def _registered(reg, monkeypatch=None):
    # Register the ed25519 test key; returns its fingerprint.
    reg.register(key_line=ED25519_LINE)
    return ED25519_FP


def test_issue_claim_happy_path(reg, monkeypatch):
    _frozen(monkeypatch, "2026-09-29T00:30:00+00:00")
    _registered(reg)
    out = reg.issue_claim(ED25519_FP, ttl_hours=24)
    assert out["account_id"] == key_registry.account_id_for(ED25519_FP)
    assert len(out["claim_code"]) == 24  # 18 bytes -> 24 base64url chars
    assert out["expires_at"] == "2026-09-30T00:30:00+00:00"
    rec = reg.lookup(ED25519_FP)
    claim = rec["claim"]
    assert claim["code_hash"] == key_registry._claim_code_hash(out["claim_code"])
    assert claim["issued_at"] == "2026-09-29T00:30:00+00:00"
    assert claim["ttl_hours"] == 24


def test_issue_claim_store_holds_hash_only(reg):
    # The security invariant, pinned: the plaintext code never lands in
    # the store. If this test goes quiet (no code minted), the issue call
    # above fails first — the test is not vacuous on its own.
    _registered(reg)
    out = reg.issue_claim(ED25519_FP)
    store_text = reg.store_path.read_text()
    assert out["claim_code"] not in store_text
    assert key_registry._claim_code_hash(out["claim_code"])[len("sha256:"):] in store_text
    # QA M12b: the module's own helper is a circular oracle — pin the
    # algorithm independently so a silent hash swap fails loudly.
    assert (
        key_registry._claim_code_hash(out["claim_code"])
        == "sha256:" + hashlib.sha256(out["claim_code"].encode("ascii")).hexdigest()
    )


def test_issue_claim_unknown_fingerprint_fails_and_mints_nothing(reg):
    with pytest.raises(RegistryError):
        reg.issue_claim(ED25519_FP)
    assert reg.lookup(ED25519_FP) is None


def test_issue_claim_rejects_nonpositive_ttl(reg):
    _registered(reg)
    for bad in (0, -1, -2.5):
        with pytest.raises(RegistryError):
            reg.issue_claim(ED25519_FP, ttl_hours=bad)
    assert "claim" not in reg.lookup(ED25519_FP)


def test_redeem_claim_happy_path(reg, monkeypatch):
    _frozen(monkeypatch, "2026-09-29T00:30:00+00:00")
    _registered(reg)
    code = reg.issue_claim(ED25519_FP)["claim_code"]
    out = reg.redeem_claim(code, claimed_by="op@example.test")
    assert out["account_id"] == key_registry.account_id_for(ED25519_FP)
    assert out["claimed_at"] == "2026-09-29T00:30:00+00:00"
    assert out["claimed_by"] == "op@example.test"
    rec = reg.lookup(ED25519_FP)
    assert "claim" not in rec  # single-use: consumed
    assert rec["claimed_at"] == "2026-09-29T00:30:00+00:00"
    assert rec["claimed_by"] == "op@example.test"


def test_redeem_claim_single_use(reg):
    _registered(reg)
    code = reg.issue_claim(ED25519_FP)["claim_code"]
    reg.redeem_claim(code)
    with pytest.raises(RegistryError):
        reg.redeem_claim(code)  # consumed: no longer live


def test_redeem_claim_unknown_code_fails(reg):
    _registered(reg)
    reg.issue_claim(ED25519_FP)
    with pytest.raises(RegistryError):
        reg.redeem_claim("x" * 24)  # well-formed, but not the live code


def test_redeem_claim_expired_fails_and_self_cleans(reg, monkeypatch):
    _frozen(monkeypatch, "2026-09-29T00:30:00+00:00")
    _registered(reg)
    code = reg.issue_claim(ED25519_FP, ttl_hours=1)["claim_code"]
    _frozen(monkeypatch, "2026-09-29T02:30:01+00:00")  # past expiry
    with pytest.raises(RegistryError, match="expired"):
        reg.redeem_claim(code)
    rec = reg.lookup(ED25519_FP)
    assert "claim" not in rec  # expired code self-cleans
    assert "claimed_at" not in rec  # refused, not stamped


def test_issue_claim_reissue_revokes_old(reg):
    _registered(reg)
    old_code = reg.issue_claim(ED25519_FP)["claim_code"]
    new_code = reg.issue_claim(ED25519_FP)["claim_code"]
    assert old_code != new_code
    with pytest.raises(RegistryError):
        reg.redeem_claim(old_code)  # revoked
    out = reg.redeem_claim(new_code)
    assert out["account_id"] == key_registry.account_id_for(ED25519_FP)


def test_redeem_claim_reclaim_restamps(reg, monkeypatch):
    # Re-claiming an already-claimed account is a label change, not an error.
    _frozen(monkeypatch, "2026-09-29T00:30:00+00:00")
    _registered(reg)
    reg.redeem_claim(reg.issue_claim(ED25519_FP)["claim_code"], claimed_by="first")
    _frozen(monkeypatch, "2026-09-30T00:30:00+00:00")
    out = reg.redeem_claim(
        reg.issue_claim(ED25519_FP)["claim_code"], claimed_by="second"
    )
    assert out["claimed_at"] == "2026-09-30T00:30:00+00:00"
    assert out["claimed_by"] == "second"
    # QA M8: the returned dict is built from call args — pin the
    # PERSISTED record too, or a refactor dropping the record write
    # would stay green.
    rec = reg.lookup(ED25519_FP)
    assert rec["claimed_at"] == "2026-09-30T00:30:00+00:00"
    assert rec["claimed_by"] == "second"


def test_new_claim_code_never_starts_with_dash(monkeypatch):
    # Regression: GH CI run 36692398265 — token_urlsafe drew a leading
    # '-', argparse read the positional as an option flag, and
    # test_claim_cli_round_trip failed (~1/64 of runs). _new_claim_code
    # must skip leading-dash draws so every ISSUED code survives the
    # positional claim-redeem form.
    draws = iter(["-Lf3QulEWD54O3lf3F8ksJFv", "ok" + "A" * 22])
    monkeypatch.setattr(
        key_registry.secrets, "token_urlsafe", lambda n: next(draws)
    )
    assert key_registry._new_claim_code() == "ok" + "A" * 22


def test_new_claim_code_shape_bulk():
    # 256 draws: no leading dash, 24 chars each (the full entropy +
    # shape contract the CLI positional form relies on).
    for _ in range(256):
        code = key_registry._new_claim_code()
        assert len(code) == 24
        assert not code.startswith("-")


def test_claim_cli_round_trip(tmp_path):
    root = str(tmp_path / "cli-claim")
    r = _cli("register", "--key-line", ED25519_LINE, root=root)
    assert r.returncode == 0, r.stderr
    r = _cli("claim-issue", ED25519_FP, "--ttl-hours", "24", root=root)
    assert r.returncode == 0, r.stderr
    issued = json.loads(r.stdout)
    assert len(issued["claim_code"]) == 24
    r = _cli("claim-redeem", issued["claim_code"], "--claimed-by", "op", root=root)
    assert r.returncode == 0, r.stderr
    redeemed = json.loads(r.stdout)
    assert redeemed["claimed_by"] == "op"
    assert redeemed["account_id"] == issued["account_id"]
    r = _cli("claim-redeem", issued["claim_code"], root=root)  # consumed
    assert r.returncode == 2
    assert "error:" in r.stderr
    assert "Traceback" not in r.stderr


def test_claim_cli_non_ascii_code_fails_clean(tmp_path):
    root = str(tmp_path / "cli-claim-bad")
    r = _cli("register", "--key-line", ED25519_LINE, root=root)
    assert r.returncode == 0, r.stderr
    _cli("claim-issue", ED25519_FP, root=root)  # code exists; input is garbage
    r = _cli("claim-redeem", "not-ascii-→", root=root)
    assert r.returncode == 2
    assert "error:" in r.stderr
    assert "Traceback" not in r.stderr


def _cli_stdin(subcommand, *args, root=None, stdin_text=""):
    # claim-redeem --code-stdin: the code arrives on stdin, never argv
    # (Security B1: a bearer credential must not sit in /proc/<pid>/cmdline).
    cmd = [sys.executable, "key_registry.py"]
    if root is not None:
        cmd += ["--registry-root", root]
    cmd += [subcommand, *args]
    return subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        input=stdin_text,
    )


def test_claim_redeem_stdin_round_trip(tmp_path):
    root = str(tmp_path / "cli-claim-stdin")
    r = _cli("register", "--key-line", ED25519_LINE, root=root)
    assert r.returncode == 0, r.stderr
    r = _cli("claim-issue", ED25519_FP, root=root)
    assert r.returncode == 0, r.stderr
    code = json.loads(r.stdout)["claim_code"]
    r = _cli_stdin("claim-redeem", "--code-stdin", root=root, stdin_text=code + "\n")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["account_id"] == key_registry.account_id_for(ED25519_FP)


def test_claim_redeem_stdin_and_argv_rejected(tmp_path):
    root = str(tmp_path / "cli-claim-both")
    r = _cli("register", "--key-line", ED25519_LINE, root=root)
    assert r.returncode == 0, r.stderr
    code = json.loads(_cli("claim-issue", ED25519_FP, root=root).stdout)["claim_code"]
    r = _cli_stdin("claim-redeem", code, "--code-stdin", root=root, stdin_text=code)
    assert r.returncode == 2
    assert "not both" in r.stderr
    assert "Traceback" not in r.stderr


def test_claim_redeem_no_code_fails_clean(tmp_path):
    root = str(tmp_path / "cli-claim-nocode")
    r = _cli("register", "--key-line", ED25519_LINE, root=root)
    assert r.returncode == 0, r.stderr
    r = _cli("claim-redeem", root=root)  # neither positional nor --code-stdin
    assert r.returncode == 2
    assert "error:" in r.stderr
    assert "Traceback" not in r.stderr


def test_claim_redeem_empty_stdin_fails_clean(tmp_path):
    root = str(tmp_path / "cli-claim-emptystdin")
    r = _cli("register", "--key-line", ED25519_LINE, root=root)
    assert r.returncode == 0, r.stderr
    _cli("claim-issue", ED25519_FP, root=root)
    r = _cli_stdin("claim-redeem", "--code-stdin", root=root, stdin_text="  \n")
    assert r.returncode == 2
    assert "error:" in r.stderr
    assert "Traceback" not in r.stderr


def test_issue_claim_rejects_nonfinite_ttl(reg):
    # nan/inf sail past `<= 0` and die as ValueError/OverflowError inside
    # timedelta — raw tracebacks, not RegistryError (Engineering B1).
    _registered(reg)
    for bad in (float("nan"), float("inf"), float("-inf"), True, False):
        with pytest.raises(RegistryError):
            reg.issue_claim(ED25519_FP, ttl_hours=bad)
    assert "claim" not in reg.lookup(ED25519_FP)


def test_claim_issue_cli_nonfinite_ttl_fails_clean(tmp_path):
    root = str(tmp_path / "cli-claim-nan")
    r = _cli("register", "--key-line", ED25519_LINE, root=root)
    assert r.returncode == 0, r.stderr
    for bad in ("nan", "inf", "-inf"):
        r = _cli("claim-issue", ED25519_FP, "--ttl-hours", bad, root=root)
        assert r.returncode == 2, bad
        assert "error:" in r.stderr, bad
        assert "Traceback" not in r.stderr, bad


def test_issue_claim_refuses_rotated_out_record(reg):
    # A rotated-out record is superseded lineage — claiming it would
    # stamp a dead record. Fail loud, like rotate's "latest key" rule.
    reg.register(key_line=ED25519_LINE)
    reg.rotate(ED25519_FP, key_line=ROT_LINE_1)
    with pytest.raises(RegistryError, match="rotated"):
        reg.issue_claim(ED25519_FP)


def test_claim_issue_cli_unknown_fingerprint_fails_clean(tmp_path):
    root = str(tmp_path / "cli-claim-unknown")
    r = _cli("claim-issue", ED25519_FP, root=root)  # never registered
    assert r.returncode == 2
    assert "error:" in r.stderr
    assert "Traceback" not in r.stderr
