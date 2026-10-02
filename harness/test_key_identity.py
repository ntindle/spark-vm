#!/usr/bin/env python3
"""Tests for harness/key_identity.py — SSH-key-as-account identity (GH #446, S1).

The fingerprint vectors below are baked from real ``ssh-keygen -lf`` output
(keys generated 2026-09-26; see the run's working notes), so the
``SHA256:`` encoding is pinned to OpenSSH behavior without depending on
ssh-keygen at test time.
"""
import base64
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import key_identity
from key_identity import (
    KNOWN_KEY_TYPES,
    KeyIdentityError,
    PublicKey,
    account_id_for,
    fingerprint,
    first_connect_manifest,
    parse_authorized_keys,
    parse_public_key,
)

ED25519_LINE = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIMLPKSGVS4GNm00i/S4BebZ+whw9lGn5GReUs0en5e69 "
    "s1-test-key"
)
ED25519_FP = "SHA256:WhVCxQzbxruL4xmoksmRPBJna6BQ5vRa9XG1Yi+hniA"

RSA_LINE = (
    "ssh-rsa "
    "AAAAB3NzaC1yc2EAAAADAQABAAABAQCuMHxSC/JnYF5VrpAtV1q6GpLViUYSauTMtosQLCWNCuHnien5sZK2fBs6AzD9F6KcRqysX4WT+O91aj6nCGlNACWBo7NxQmyPS1x51pi0k1IvlKJLxjWb2OkosRalBnNmbV8Nw+LdiKtZfwUc5edCgIwvx+SldpQskye13qa7l8Y4oMuCRPEwsD4ikr6frIqc2EEevSLbNHTGZ6/8Sw1w+LjW+YAWgxly0xkDzU4VClEgwJRUMd5kRN6/ZU2PSLUSh85R+25f7bTIDQLwLX5H2KwaArMkbNiOD7/5lvzMUgyauHeQ1YNHEmbG3RiqIevi4vgHcw4a9Ey03qSbEO8n "
    "s1-test-key-rsa"
)
RSA_FP = "SHA256:4wfQsyAlwrPnCaxOrZD6qSU59RmKacqwTlRwXcwLuZo"


def test_parse_ed25519_fields():
    key = parse_public_key(ED25519_LINE)
    assert key.key_type == "ssh-ed25519"
    assert key.comment == "s1-test-key"
    assert len(key.blob) == 51


def test_parse_without_comment():
    line = ED25519_LINE.rsplit(" ", 1)[0]
    key = parse_public_key(line)
    assert key.comment == ""


def test_parse_normalizes_crlf_and_whitespace():
    key = parse_public_key("  " + ED25519_LINE.replace(" ", "\t") + "\r\n")
    assert key.key_type == "ssh-ed25519"
    assert fingerprint(key) == ED25519_FP


def test_fingerprint_matches_ssh_keygen_ed25519():
    assert fingerprint(parse_public_key(ED25519_LINE)) == ED25519_FP


def test_fingerprint_matches_ssh_keygen_rsa():
    assert fingerprint(parse_public_key(RSA_LINE)) == RSA_FP


def test_fingerprint_encoding_shape():
    # Unpadded base64 of a 32-byte digest, prefixed SHA256: — the exact
    # ssh-keygen -lf rendering.
    key = parse_public_key(ED25519_LINE)
    fp = fingerprint(key)
    assert fp.startswith("SHA256:")
    raw = base64.b64decode(fp[len("SHA256:") :] + "==")
    assert raw == hashlib.sha256(key.blob).digest()


def test_account_id_stable_and_distinct():
    fp1, fp2 = ED25519_FP, RSA_FP
    assert account_id_for(fp1) == account_id_for(fp1)
    assert account_id_for(fp1) != account_id_for(fp2)
    assert account_id_for(fp1).startswith("acct_")
    assert len(account_id_for(fp1)) == len("acct_") + 16


def test_account_id_derivation_documented():
    # The derivation is public and one-way; pin the exact domain separation
    # so an accidental change is a loud test failure, not silent drift.
    expected = "acct_" + hashlib.sha256(
        ("spark-vm:key-identity:v1:" + ED25519_FP).encode("ascii")
    ).hexdigest()[:16]
    assert account_id_for(ED25519_FP) == expected


def test_account_id_rejects_non_fingerprint():
    for bad in ("", "md5:aa:bb", "SHA256", "acct_deadbeef"):
        with pytest.raises(KeyIdentityError):
            account_id_for(bad)


def test_manifest_shape_and_fields():
    issued = datetime.datetime(2026, 9, 26, 16, 0, tzinfo=datetime.timezone.utc)
    expiry = datetime.datetime(2026, 10, 26, 16, 0, tzinfo=datetime.timezone.utc)
    m = first_connect_manifest(
        parse_public_key(ED25519_LINE),
        claim_url="https://example.invalid/claim/abc",
        vm_endpoint="10.0.0.7:22",
        box_id="box-1",
        expires_at=expiry,
        issued_at=issued,
    )
    assert m["manifest_version"] == 1
    assert m["account_id"] == account_id_for(ED25519_FP)
    assert m["key_fingerprint"] == ED25519_FP
    assert m["key_type"] == "ssh-ed25519"
    assert m["issued_at"] == "2026-09-26T16:00:00+00:00"
    assert m["expires_at"] == "2026-10-26T16:00:00+00:00"
    assert m["claim_url"] == "https://example.invalid/claim/abc"
    assert m["vm_endpoint"] == "10.0.0.7:22"
    assert m["box_id"] == "box-1"
    assert "comment" not in json.dumps(m)  # operator comments never leak in
    # #826: the policy map describes the SHIPPED mechanics (rotation
    # lineage-recorded, claim protocol live) — "not-implemented" was the
    # pre-S2.5/S3 truth.
    assert "not-implemented" not in m["policy"]["rotation"]
    assert "lineage" in m["policy"]["rotation"]
    assert "claim" in m["policy"]
    assert "single-use" in m["policy"]["claim"]


def test_manifest_expiry_defaults_to_none():
    # S1 semantics: key-identity accounts do not expire; the claim/upgrade
    # slice sets claim-link validity, not this one.
    m = first_connect_manifest(parse_public_key(ED25519_LINE))
    assert "expires_at" in m
    assert m["expires_at"] is None


def test_manifest_expiry_naive_is_treated_as_utc():
    naive = datetime.datetime(2026, 10, 26, 16, 0)
    m = first_connect_manifest(parse_public_key(ED25519_LINE), expires_at=naive)
    assert m["expires_at"] == "2026-10-26T16:00:00+00:00"


def test_manifest_expiry_out_of_range_fails_loud():
    # datetime(9999,12,31) with a -14:00 offset cannot exist in UTC —
    # the module's error type must surface, not a bare OverflowError.
    dt = datetime.datetime(
        9999, 12, 31, 23, 59, 59,
        tzinfo=datetime.timezone(datetime.timedelta(hours=-14)),
    )
    with pytest.raises(KeyIdentityError):
        first_connect_manifest(parse_public_key(ED25519_LINE), expires_at=dt)


def test_manifest_defaults_are_null_and_now():
    m = first_connect_manifest(parse_public_key(ED25519_LINE))
    assert m["claim_url"] is None and m["vm_endpoint"] is None
    issued = datetime.datetime.fromisoformat(m["issued_at"])
    delta = datetime.datetime.now(datetime.timezone.utc) - issued
    assert datetime.timedelta(0) <= delta < datetime.timedelta(minutes=1)


def test_parse_authorized_keys_skips_blanks_and_comments():
    text = "# comment\n\n" + ED25519_LINE + "\n\n"
    keys = parse_authorized_keys(text)
    assert len(keys) == 1 and keys[0].comment == "s1-test-key"


def test_parse_authorized_keys_line_numbers_on_error():
    with pytest.raises(KeyIdentityError, match="line 4"):
        parse_authorized_keys(ED25519_LINE + "\n\n# ok\nnot-a-key")


@pytest.mark.parametrize(
    "bad",
    [
        "",  # empty
        "   ",  # whitespace only
        "ssh-ed25519",  # missing blob
        "ssh-unknown AAAAC3NzaC1lZDI1NTE5AAAAIHRlc3Q= x",  # unknown type
        "ssh-ed25519 !!!not-base64!!! x",  # bad base64
        "ssh-ed25519 QUJD x",  # truncated blob (3 bytes)
        # ed25519 with a short pubkey field (not 32 bytes):
        "ssh-ed25519 "
        + base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x04abcd").decode()
        + " x",
        # leading ssh options must not be silently half-parsed:
        'command="echo hi" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHRlc3Q= x',
        # cert key types are out of scope:
        "ssh-ed25519-cert-v01@openssh.com AAAAC3NzaC1lZDI1NTE5AAAAIHRlc3Q= x",
    ],
)
def test_parse_rejects_malformed(bad):
    with pytest.raises(KeyIdentityError):
        parse_public_key(bad)


def _confused_line(outer: str, inner: str) -> str:
    """A key line whose blob embeds ``inner`` while the line says ``outer``.

    The blob is otherwise well-formed (valid 32-byte field), so the ONLY
    check that can reject it is the inner/outer type-equality check —
    isolating that check from the payload-shape checks.
    """
    blob = (
        len(inner).to_bytes(4, "big")
        + inner.encode("ascii")
        + b"\x00\x00\x00\x20"
        + b"\x00" * 32
    )
    return outer + " " + base64.b64encode(blob).decode() + " x"


@pytest.mark.parametrize(
    "outer,inner",
    [
        ("ssh-ed25519", "ssh-rsa"),
        # rsa gets NO payload-shape check at all — the type-equality check
        # is its entire structural net; pin it on that side too.
        ("ssh-rsa", "ssh-ed25519"),
    ],
)
def test_parse_rejects_type_confusion(outer, inner):
    with pytest.raises(KeyIdentityError, match="key type mismatch"):
        parse_public_key(_confused_line(outer, inner))


def test_stdlib_only():
    # The module must import with zero third-party dependencies.
    src = Path(__file__).resolve().parent.joinpath("key_identity.py").read_text()
    assert "import key_identity" not in src  # no self-import games
    forbidden = {"requests", "cryptography", "paramiko", "nacl"}
    imported = {
        line.split()[1].split(".")[0]
        for line in src.splitlines()
        if line.startswith(("import ", "from "))
        and not line.startswith("from __future__")
    }
    assert not (imported & forbidden)


def test_cli_emits_manifest_json(tmp_path):
    pub = tmp_path / "key.pub"
    pub.write_text(ED25519_LINE + "\n")
    out = subprocess.run(
        [sys.executable, "key_identity.py", str(pub)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent,
    )
    assert out.returncode == 0, out.stderr
    manifest = json.loads(out.stdout)
    assert manifest["account_id"] == account_id_for(ED25519_FP)
    assert manifest["key_fingerprint"] == ED25519_FP


def test_cli_rejects_bad_key_file(tmp_path):
    bad = tmp_path / "bad.pub"
    bad.write_text("not a key\n")
    out = subprocess.run(
        [sys.executable, "key_identity.py", str(bad)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent,
    )
    assert out.returncode != 0
    assert "ERROR" in out.stderr


def test_cli_rejects_out_of_range_expires_at_cleanly(tmp_path):
    # year-9999 with a western offset cannot exist in UTC — the CLI must
    # fail loud with its ERROR path, not an unhandled traceback.
    pub = tmp_path / "key.pub"
    pub.write_text(ED25519_LINE + "\n")
    out = subprocess.run(
        [sys.executable, "key_identity.py", str(pub),
         "--expires-at", "9999-12-31T23:59:59-14:00"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent,
    )
    assert out.returncode == 1
    assert "ERROR" in out.stderr
    assert "Traceback" not in out.stderr


def test_account_id_for_rejects_non_ascii_fingerprint():
    # must raise the module's loud error type, not a bare UnicodeEncodeError
    with pytest.raises(KeyIdentityError):
        account_id_for("SHA256:☃☃☃☃☃☃☃☃")


def test_cli_expires_at_round_trips(tmp_path):
    pub = tmp_path / "key.pub"
    pub.write_text(ED25519_LINE + "\n")
    out = subprocess.run(
        [sys.executable, "key_identity.py", str(pub),
         "--expires-at", "2026-10-26T16:00:00+00:00"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent,
    )
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["expires_at"] == "2026-10-26T16:00:00+00:00"


def test_cli_rejects_bad_expires_at(tmp_path):
    pub = tmp_path / "key.pub"
    pub.write_text(ED25519_LINE + "\n")
    out = subprocess.run(
        [sys.executable, "key_identity.py", str(pub),
         "--expires-at", "not-a-date"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent,
    )
    assert out.returncode != 0
    assert "ERROR" in out.stderr


def test_known_key_types_documents_scope():
    assert "ssh-ed25519" in KNOWN_KEY_TYPES
    assert "ssh-rsa" in KNOWN_KEY_TYPES
    assert not any("cert" in t for t in KNOWN_KEY_TYPES)
