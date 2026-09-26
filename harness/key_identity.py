#!/usr/bin/env python3
"""SSH-key-as-account identity primitives (GitHub #446, slice S1).

A public SSH key *is* the account for agent-created accounts: the first SSH
connect with a public key implicitly creates (or resumes) the account bound
to that key's fingerprint; reconnecting with the same key resumes the same
account. This module provides the stateless identity half of that contract:

- parse an OpenSSH public-key line (authorized_keys format),
- compute the OpenSSH ``SHA256:`` fingerprint of the key blob,
- derive a stable, opaque account id from the fingerprint,
- emit the first-connect agent manifest (account id, key fingerprint,
  expiry, claim link, policy) as JSON.

Persistence — the fingerprint -> account registry, "same key resumes the
same box" state, key rotation, and the claim/upgrade escape hatch — is a
later slice (see #446). This module deliberately keeps no state: no disk
writes, no network, no subprocesses, stdlib only, so it can run unchanged on
the self-hosted box, the hosted control plane, and the operator laptop.

The functions raise :class:`KeyIdentityError` (a ``ValueError``) on malformed
input, loudly, never silently misidentifying a key. Key parsing is
structural, not regex-shaped: the base64 blob is decoded, the type string
embedded in the blob is asserted equal to the outer key type, and the
per-type payload length is checked where the format pins it down.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import datetime
import hashlib
import json
import sys
from dataclasses import dataclass

MANIFEST_VERSION = 1
# Namespaced derivation: changing this string changes every account id, so
# it is versioned alongside the manifest. Key rotation (a new key) always
# yields a new account id — identity is the key, by design.
_ACCOUNT_ID_DOMAIN = "spark-vm:key-identity:v1:"

# OpenSSH public-key types this module parses. Deliberately excludes cert
# types (``ssh-ed25519-cert-v01@openssh.com`` et al.): certificates carry an
# expiry and a CA signature, and identity-from-cert is a different feature
# (filed separately if needed).
KNOWN_KEY_TYPES = frozenset(
    {
        "ssh-ed25519",
        "ssh-rsa",
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "sk-ssh-ed25519@openssh.com",
        "sk-ecdsa-sha2-nistp256@openssh.com",
    }
)


class KeyIdentityError(ValueError):
    """A public-key line (or a derived value) failed validation."""


@dataclass(frozen=True)
class PublicKey:
    """A parsed OpenSSH public key line.

    ``key_type`` is the outer type token (e.g. ``ssh-ed25519``), ``blob`` is
    the decoded key bytes, and ``comment`` is the optional trailing comment
    (present in authorized_keys lines; never echoed into the manifest).

    Obtain instances via :func:`parse_public_key`, which enforces the
    structural checks; constructing one directly skips them.
    """

    key_type: str
    blob: bytes
    comment: str = ""


def _read_ssh_string(buf: bytes, offset: int) -> tuple[bytes, int]:
    """Read one ``string`` field (u32 length prefix) from an SSH wire blob."""
    if offset + 4 > len(buf):
        raise KeyIdentityError("key blob truncated: missing length prefix")
    length = int.from_bytes(buf[offset : offset + 4], "big")
    offset += 4
    if offset + length > len(buf):
        raise KeyIdentityError(
            f"key blob truncated: field claims {length} bytes, "
            f"{len(buf) - offset} remain"
        )
    return buf[offset : offset + length], offset + length


def _check_blob_structure(key_type: str, blob: bytes) -> None:
    """Assert the blob is a structurally plausible key of ``key_type``.

    Reads the embedded algorithm string and requires it to equal the outer
    key type (rejects type-confusion lines), then checks the payload shapes
    the SSH formats pin down exactly (ed25519/sk-ed25519: the first field
    must be a 32-byte public-key string; trailing bytes, if any, are not
    shape-checked but still feed the fingerprint).
    """
    inner_type, offset = _read_ssh_string(blob, 0)
    try:
        inner_name = inner_type.decode("ascii")
    except UnicodeDecodeError as exc:
        raise KeyIdentityError("key blob holds a non-ASCII algorithm name") from exc
    if inner_name != key_type:
        raise KeyIdentityError(
            f"key type mismatch: line says {key_type!r}, "
            f"key blob says {inner_name!r}"
        )
    if key_type in ("ssh-ed25519", "sk-ssh-ed25519@openssh.com"):
        # The format pins down exactly one 32-byte public-key string after
        # the algorithm name. Trailing bytes (sk-* application/flags
        # fields, or future extensions) are NOT shape-checked here — they
        # remain part of the key blob, so they still feed the fingerprint
        # and identity. The check that matters for "loudly, never silently
        # misidentifying a key" is the inner/outer type equality above.
        pubkey, _ = _read_ssh_string(blob, offset)
        if len(pubkey) != 32:
            raise KeyIdentityError(
                f"{key_type} public-key field must be 32 bytes, "
                f"got {len(pubkey)}"
            )


def parse_public_key(line: str) -> PublicKey:
    """Parse one authorized_keys-style public-key line.

    Accepts ``<type> <base64-blob> [comment]``; fields may be separated by
    spaces or tabs. Raises :class:`KeyIdentityError` on anything else:
    empty lines, unknown key types, malformed base64, or blobs whose
    structure fails :func:`_check_blob_structure`.

    Lines with ssh(1) *options* before the key type (``command="..."`` etc.)
    are rejected, not silently half-parsed — the onboarding contract writes
    clean key lines; option parsing is a different module's job.
    """
    text = line.replace("\r", "").strip()
    if not text:
        raise KeyIdentityError("empty key line")
    fields = text.split()
    if len(fields) < 2:
        raise KeyIdentityError(
            "key line needs at least a type and a base64 blob"
        )
    key_type, blob_b64 = fields[0], fields[1]
    if "=" in key_type or key_type.startswith('"'):
        raise KeyIdentityError(
            "key line appears to start with ssh options, "
            "which this module does not parse"
        )
    if key_type not in KNOWN_KEY_TYPES:
        raise KeyIdentityError(f"unsupported key type: {key_type!r}")
    try:
        blob = base64.b64decode(blob_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise KeyIdentityError(f"key blob is not valid base64: {exc}") from exc
    _check_blob_structure(key_type, blob)
    comment = " ".join(fields[2:]) if len(fields) > 2 else ""
    return PublicKey(key_type=key_type, blob=blob, comment=comment)


def parse_authorized_keys(text: str) -> list[PublicKey]:
    """Parse a whole authorized_keys file into :class:`PublicKey` list.

    Blank lines and ``#`` comments are skipped; every other line must parse
    via :func:`parse_public_key` or the whole call raises. The onboarding
    contract writes one key per line and nothing else.
    """
    keys: list[PublicKey] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            keys.append(parse_public_key(raw))
        except KeyIdentityError as exc:
            raise KeyIdentityError(f"line {lineno}: {exc}") from exc
    return keys


def fingerprint(key: PublicKey) -> str:
    """Return the OpenSSH ``SHA256:`` fingerprint of the key.

    Byte-identical to ``ssh-keygen -lf`` for the same key: base64 of
    SHA-256(key blob), unpadded, prefixed ``SHA256:``.
    """
    digest = hashlib.sha256(key.blob).digest()
    b64 = base64.b64encode(digest).decode("ascii").rstrip("=")
    return f"SHA256:{b64}"


def account_id_for(key_fingerprint: str) -> str:
    """Derive the stable, opaque account id bound to a key fingerprint.

    The derivation is ``acct_`` + the first 16 hex chars of
    SHA-256(domain-separation || fingerprint); 64 bits is ample for account
    ids at this scale, and the derivation is one-way: the fingerprint (and
    the key) cannot be recovered from the id. Same key always yields the
    same id; a new key yields a new account — rotation-as-new-identity is
    the documented #446 policy until the claim story ships.
    """
    if not key_fingerprint.startswith("SHA256:") or len(key_fingerprint) < 8:
        raise KeyIdentityError(
            f"not an OpenSSH SHA256 fingerprint: {key_fingerprint!r}"
        )
    try:
        domain_bytes = (_ACCOUNT_ID_DOMAIN + key_fingerprint).encode("ascii")
    except UnicodeEncodeError as exc:
        raise KeyIdentityError(
            f"not an OpenSSH SHA256 fingerprint: {key_fingerprint!r}"
        ) from exc
    digest = hashlib.sha256(domain_bytes).hexdigest()
    return f"acct_{digest[:16]}"


def first_connect_manifest(
    key: PublicKey,
    *,
    claim_url: str | None = None,
    vm_endpoint: str | None = None,
    box_id: str | None = None,
    expires_at: datetime.datetime | None = None,
    issued_at: datetime.datetime | None = None,
) -> dict:
    """Build the first-connect agent manifest for a key.

    The manifest is what the onboarding path hands the agent on first
    connect (per the #446 proposal): account id, key fingerprint, the
    claim-link escape hatch, and the policy the agent must report back to
    its operator. ``issued_at`` defaults to now (UTC); pass it explicitly
    in tests for determinism.

    ``expires_at`` is an optional UTC timestamp for when the manifest (or
    the claim link inside it) stops being honored. S1 semantics: ``None``
    — key-identity accounts do not expire, and claim-link validity is set
    by the claim/upgrade slice, not here.
    """
    fp = fingerprint(key)
    now = issued_at or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    def _iso(dt: datetime.datetime | None) -> str | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        try:
            return dt.astimezone(datetime.timezone.utc).isoformat()
        except (OverflowError, ValueError, OSError) as exc:
            # e.g. datetime(9999, 12, 31, tzinfo=-14:00) cannot be
            # represented in UTC — fail loud with the module's error type,
            # never let a bare exception escape the caller's contract.
            raise KeyIdentityError(
                f"expiry timestamp out of representable range: {dt!r}"
            ) from exc

    return {
        "manifest_version": MANIFEST_VERSION,
        "account_id": account_id_for(fp),
        "key_fingerprint": fp,
        "key_type": key.key_type,
        "issued_at": _iso(now),
        "expires_at": _iso(expires_at),
        "vm_endpoint": vm_endpoint,
        "box_id": box_id,
        "claim_url": claim_url,
        "policy": {
            # One key = one identity. Rotating the key creates a NEW
            # account; there is no linking yet — the claim/upgrade escape
            # hatch (later slice) is the answer to key loss / rotation.
            "rotation": "not-implemented: a new key is a new account",
            # Multiple keys = multiple identities. Accepted for
            # self-hosted and agent-created accounts; the hosted sybil
            # policy is an open question (see #446).
            "sybil": (
                "accepted for self-hosted: each key is its own identity; "
                "hosted policy TBD"
            ),
        },
    }


def _cmd(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="key_identity",
        description=(
            "SSH-key-as-account identity primitives (#446, slice S1): "
            "fingerprint a public key and emit its first-connect manifest."
        ),
    )
    parser.add_argument(
        "pubkey_file",
        help="path to a file holding one OpenSSH public-key line",
    )
    parser.add_argument(
        "--claim-url",
        default=None,
        help="claim/upgrade URL to embed in the manifest",
    )
    parser.add_argument(
        "--vm-endpoint",
        default=None,
        help="VM endpoint (host:port) to embed in the manifest",
    )
    parser.add_argument(
        "--expires-at",
        default=None,
        metavar="ISO-8601",
        help="manifest expiry timestamp (UTC ISO-8601) to embed",
    )
    args = parser.parse_args(argv)
    try:
        with open(args.pubkey_file, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"ERROR: cannot read {args.pubkey_file}: {exc}", file=sys.stderr)
        return 2
    try:
        keys = parse_authorized_keys(text)
    except KeyIdentityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if len(keys) != 1:
        print(
            f"ERROR: expected exactly one key, found {len(keys)}",
            file=sys.stderr,
        )
        return 1
    expires_at = None
    if args.expires_at is not None:
        try:
            expires_at = datetime.datetime.fromisoformat(args.expires_at)
        except ValueError as exc:
            print(f"ERROR: bad --expires-at: {exc}", file=sys.stderr)
            return 1
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
    manifest = first_connect_manifest(
        keys[0],
        claim_url=args.claim_url,
        vm_endpoint=args.vm_endpoint,
        expires_at=expires_at,
    )
    json.dump(manifest, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(_cmd())
