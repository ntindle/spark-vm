#!/usr/bin/env python3
"""Tests for harness/key_registry.py — SSH-key-as-account registry (GH #446, S2).

Every test runs against a fresh tmp_path registry root: the module never
touches the real $XDG_STATE_HOME store in tests. Time is frozen via
monkeypatching key_registry._utcnow for last_seen assertions.
"""
import datetime
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
RSA_FP = None  # computed below, via S1 — keeps the test honest


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
    for bad in ("", "md5:aa:bb", "SHA256:", "SHA256:not base64!!!", None, 42):
        with pytest.raises(KeyIdentityError):
            normalize_fingerprint(bad)


# -- register / lookup ----------------------------------------------------------
def test_register_creates_record_with_derived_account_id(reg):
    rec = reg.register(key_line=ED25519_LINE, box_ref="box-1")
    assert rec["fingerprint"] == ED25519_FP
    assert rec["account_id"] == key_registry.account_id_for(ED25519_FP)
    assert rec["key_type"] == "ssh-ed25519"
    assert rec["box_ref"] == "box-1"
    assert rec["claimed"] is False
    assert rec["claimed_at"] is None
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


def test_mark_claimed(reg, monkeypatch):
    assert reg.mark_claimed(ED25519_FP) is False
    _frozen(monkeypatch, "2026-09-27T10:00:00+00:00")
    reg.register(key_line=ED25519_LINE)
    _frozen(monkeypatch, "2026-09-27T13:00:00+00:00")
    assert reg.mark_claimed(ED25519_FP) is True
    rec = reg.lookup(ED25519_FP)
    assert rec["claimed"] is True
    assert rec["claimed_at"] == "2026-09-27T13:00:00+00:00"


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
    # Global flags (e.g. --registry-root) must precede the subcommand.
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
    rec = json.loads(r.stdout)
    assert rec["fingerprint"] == ED25519_FP
    r = _cli("lookup", ED25519_FP, root=root)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["account_id"] == rec["account_id"]


def test_cli_lookup_unknown_exits_1(tmp_path):
    r = _cli("lookup", ED25519_FP, root=str(tmp_path / "x"))
    assert r.returncode == 1


def test_cli_status_lists_accounts(tmp_path):
    root = str(tmp_path / "st")
    _cli("register", "--key-line", ED25519_LINE, root=root)
    r = _cli("status", root=root)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)[0]["fingerprint"] == ED25519_FP


def test_cli_claim_and_remove(tmp_path):
    root = str(tmp_path / "cr")
    _cli("register", "--key-line", ED25519_LINE, root=root)
    r = _cli("claim", ED25519_FP, root=root)
    assert r.returncode == 0, r.stderr
    r = _cli("lookup", ED25519_FP, root=root)
    assert json.loads(r.stdout)["claimed"] is True
    r = _cli("remove", ED25519_FP, root=root)
    assert r.returncode == 0, r.stderr
    r = _cli("lookup", ED25519_FP, root=root)
    assert r.returncode == 1


def test_default_root_honors_xdg_state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    reg2 = KeyRegistry()
    assert reg2.root == tmp_path / "xdg" / "spark-vm" / "key-registry"
