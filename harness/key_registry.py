#!/usr/bin/env python3
"""SSH-key-as-account registry (GitHub #446, slice S2: storage + lookup).

Slice S1 (``harness/key_identity.py``) is the stateless half: parse a public
key, fingerprint it, derive the stable opaque account id. This module is the
stateful half: a per-host registry mapping SSH key fingerprints to account
records — ``created_at``, ``last_seen_at``, key type, and box binding.
"Same key -> same box" resume state lives here.

Storage and lookup choices (the design half of #446's acceptance criteria):
- Single JSON file (``<root>/registry.json``) keyed by the OpenSSH
  ``SHA256:`` fingerprint string. Chose flat JSON over sqlite on purpose:
  no schema migrations at this scale, human-inspectable on the box, and
  the whole store is stdlib ``json`` — the module keeps S1's stdlib-only
  discipline (runs unchanged on the self-hosted box, the hosted control
  plane, and the operator laptop).
- Interprocess mutual exclusion is a lockdir (``<root>/registry.lock.d``)
  created with ``os.mkdir`` (atomic on POSIX). A lockdir also serializes
  threads inside one process, which fcntl locks do not; portability across
  the box and the operator laptop comes free.
- Writes are atomic: temp file (``O_EXCL``) + ``os.replace``. A crashed
  writer can never leave a half-written registry behind.
- Corrupt ``registry.json`` fails closed (``RegistryError``), never silently
  reset: identity misbinding is worse than downtime. The operator recovery
  path is documented in ``docs/KEY_IDENTITY_REGISTRY.md``.

No secrets: records hold only public fingerprints, one-way derived account
ids, and operator-visible metadata. The store is ``0o600`` / root dir
``0o700`` anyway — the account ids map to whoever's keys, and defense in
depth costs nothing.

The claim/upgrade escape hatch is a LATER slice (see #446): this module
records no claim state at all, so S2 cannot preempt S3's claim-protocol
decisions. Per S1's policy, a new key is a new account.

Key rotation is slice S2.5 (this module, :meth:`KeyRegistry.rotate`): the
operator-facing path for a key the operator still holds — "I generated a
new key and want this box to know it's me". Rotation registers the new key
as a NEW account (the S1 policy stands: identity is the key), marks the
old record with ``rotated_to``/``rotated_at``, inherits the box binding,
and appends an entry to the bounded ``rotations`` journal — the audit
trail S2 noted ``remove`` lacks, scoped to rotation. Lost-key rotation
(no old key to attest with) is NOT this slice; it needs the claim
protocol (S3).
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import os
import sys
import tempfile
import time
from pathlib import Path

try:
    import key_identity
    from key_identity import KeyIdentityError, account_id_for, fingerprint
except ImportError:  # pragma: no cover - defensive; both live in harness/
    import importlib.util

    _here = Path(__file__).resolve().parent
    _spec = importlib.util.spec_from_file_location(
        "key_identity", _here / "key_identity.py"
    )
    key_identity = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(key_identity)
    KeyIdentityError = key_identity.KeyIdentityError
    account_id_for = key_identity.account_id_for
    fingerprint = key_identity.fingerprint

SCHEMA_VERSION = 1
STORE_NAME = "registry.json"
LOCK_DIR_NAME = "registry.lock.d"
LOCK_TIMEOUT_S = 10.0
_LOCK_POLL_S = 0.05
# Bounded journal: the #376 lesson (unbounded = fail). The per-record
# rotated_to pointer is never dropped, so capping the journal only bounds
# the window of operator-visible audit history, never lineage.
ROTATIONS_CAP = 1000


class RegistryError(Exception):
    """The registry cannot be read or written safely. Fail loud."""


def _utcnow() -> datetime.datetime:
    """Now in UTC. Module-level hook so tests can freeze time."""
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt: datetime.datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).isoformat()


def default_registry_root() -> Path:
    """Default registry root: $XDG_STATE_HOME or ~/.local/state."""
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "spark-vm" / "key-registry"


def normalize_fingerprint(fp: str) -> str:
    """Validate an OpenSSH SHA256 fingerprint string, return it unchanged.

    Enforces the exact canonical shape S1 emits: ``SHA256:`` + 43 chars of
    unpadded base64 (SHA-256 is 32 bytes; 32 bytes base64-encode to 43
    unpadded chars). Padding is never legitimate — S1's ``fingerprint()``
    always strips it — and accepting a padded twin would mint a second
    account id for the same key (QA blocker, round 1: padded and unpadded
    forms derive different ``acct_`` ids). A malformed fingerprint raises
    ``KeyIdentityError`` loudly rather than silently becoming a different
    record key.
    """
    if not isinstance(fp, str) or not fp.startswith("SHA256:"):
        raise KeyIdentityError(f"not an OpenSSH SHA256 fingerprint: {fp!r}")
    b64 = fp[len("SHA256:") :]
    if len(b64) != 43 or any(
        c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        for c in b64
    ):
        raise KeyIdentityError(f"not an OpenSSH SHA256 fingerprint: {fp!r}")
    # account_id_for re-checks the SHA256: prefix and ASCII-ness; the shape
    # check above is this module's stricter canonical rule.
    account_id_for(fp)
    return fp


class KeyRegistry:
    """Fingerprint -> account record store. Thread- and process-safe."""

    def __init__(self, root: str | os.PathLike | None = None):
        self.root = Path(root) if root is not None else default_registry_root()
        self.store_path = self.root / STORE_NAME
        self.lock_path = self.root / LOCK_DIR_NAME

    # -- locking ---------------------------------------------------------
    def _lock_holder_alive(self) -> bool:
        """True if the process holding the lockdir still exists."""
        pid_file = self.lock_path / "pid"
        try:
            pid = int(pid_file.read_text().strip())
        except (OSError, ValueError):
            return True  # unparseable pid: someone is mid-write; wait it out
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # a process exists that we cannot signal
        return True

    @contextlib.contextmanager
    def _locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass  # best effort; perms verified by tests on fresh dirs
        deadline = time.monotonic() + LOCK_TIMEOUT_S
        while True:
            if time.monotonic() >= deadline:
                raise RegistryError(
                    f"registry lock not acquired within {LOCK_TIMEOUT_S}s: "
                    f"{self.lock_path}"
                )
            try:
                os.mkdir(self.lock_path)
                break
            except FileExistsError:
                if not self._lock_holder_alive():
                    # Stale lock: the holder died mid-write. Reclaim by
                    # removing and re-creating. (Pid-reuse race: a recycled
                    # pid would make us wait instead of reclaim — a
                    # liveness miss, never a corruption.) The deadline is
                    # checked at the top of the loop, so pathological
                    # stale-lock churn cannot spin forever.
                    try:
                        (self.lock_path / "pid").unlink(missing_ok=True)
                        os.rmdir(self.lock_path)
                    except OSError:
                        pass  # lost the race to another reclaimer; retry
                    continue
                time.sleep(_LOCK_POLL_S)
        try:
            (self.lock_path / "pid").write_text(str(os.getpid()))
            yield
        finally:
            try:
                (self.lock_path / "pid").unlink(missing_ok=True)
                os.rmdir(self.lock_path)
            except OSError:
                pass  # another reclaimer got there first; lock is free anyway

    # -- store IO ----------------------------------------------------------
    def _load(self) -> dict:
        """Read the store. Missing file -> empty store. Corrupt -> raise."""
        try:
            text = self.store_path.read_text()
        except FileNotFoundError:
            return {
                "schema_version": SCHEMA_VERSION,
                "accounts": {},
                "rotations": [],
            }
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RegistryError(
                f"registry is corrupt, refusing to proceed: {self.store_path}"
            ) from exc
        if not isinstance(data, dict) or not isinstance(data.get("accounts"), dict):
            raise RegistryError(
                f"registry has unexpected shape, refusing to proceed: {self.store_path}"
            )
        if data.get("schema_version") != SCHEMA_VERSION:
            raise RegistryError(
                f"registry schema v{data.get('schema_version')}, "
                f"this code reads v{SCHEMA_VERSION}: {self.store_path}"
            )
        for fp, rec in data["accounts"].items():
            if not isinstance(rec, dict):
                raise RegistryError(
                    f"registry record for {fp} is not an object, "
                    f"refusing to proceed: {self.store_path}"
                )
        rotations = data.get("rotations", [])
        if not isinstance(rotations, list) or not all(
            isinstance(entry, dict) for entry in rotations
        ):
            raise RegistryError(
                f"registry rotations journal has unexpected shape, "
                f"refusing to proceed: {self.store_path}"
            )
        data["rotations"] = rotations  # normalize: missing key -> empty journal
        return data

    def _save(self, data: dict) -> None:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.root, prefix=STORE_NAME + ".tmp.", suffix=f".{os.getpid()}"
        )
        try:
            with os.fdopen(tmp_fd, "w") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.store_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _mutate(self, fn) -> None:
        """Run fn(data) under the lock and persist. fn may raise to abort."""
        with self._locked():
            data = self._load()
            fn(data)
            self._save(data)

    # -- public API ----------------------------------------------------------
    def register(
        self,
        *,
        key_line: str | None = None,
        fingerprint_str: str | None = None,
        key_type: str | None = None,
        box_ref: str | None = None,
    ) -> dict:
        """Register a key, returning its account record (idempotent).

        Exactly one of ``key_line`` (an OpenSSH public-key line, parsed via
        S1) or ``fingerprint_str`` (+ ``key_type``) must be given. Registering
        an already-known fingerprint refreshes ``last_seen_at`` and, when
        ``box_ref`` is provided, rebinds the box — "same key -> same box" is
        the registry's core promise, and an explicit rebind wins over the
        stored binding. ``box_ref=None`` leaves the stored binding untouched
        (absence of evidence is not evidence of unbinding).
        """
        if (key_line is None) == (fingerprint_str is None):
            raise RegistryError("register needs exactly one of key_line / fingerprint_str")
        if box_ref == "":
            # An empty string is provided-but-meaningless: it would silently
            # clear a binding while nothing downstream distinguishes "unbound"
            # (None) from "bound to empty". Reject loudly instead.
            raise RegistryError("box_ref must not be empty")
        if key_line is not None:
            key = key_identity.parse_public_key(key_line)
            fp = fingerprint(key)
            key_type = key.key_type
        else:
            fp = normalize_fingerprint(fingerprint_str)
            if not key_type:
                raise RegistryError("fingerprint_str registration needs key_type")
        now = _iso(_utcnow())
        record: dict = {}

        def _do(data: dict) -> None:
            nonlocal record
            accounts = data["accounts"]
            existing = accounts.get(fp)
            if existing is not None:
                if existing.get("key_type") != key_type:
                    raise RegistryError(
                        f"fingerprint {fp} already registered with a different "
                        f"key type ({existing.get('key_type')} != {key_type})"
                    )
                existing["last_seen_at"] = now
                if box_ref is not None:
                    existing["box_ref"] = box_ref
                record = dict(existing)
                return
            record = {
                "fingerprint": fp,
                "account_id": account_id_for(fp),
                "key_type": key_type,
                "created_at": now,
                "last_seen_at": now,
                "box_ref": box_ref,
                "schema_version": SCHEMA_VERSION,
            }
            accounts[fp] = record
            record = dict(record)  # return a copy, like the existing-record path

        self._mutate(_do)
        return record

    def lookup(self, fp: str) -> dict | None:
        """Return the account record for a fingerprint, or None."""
        fp = normalize_fingerprint(fp)
        with self._locked():
            data = self._load()
            rec = data["accounts"].get(fp)
            return dict(rec) if rec is not None else None

    def touch(self, fp: str) -> bool:
        """Refresh last_seen_at. Returns False when the fingerprint is unknown."""
        fp = normalize_fingerprint(fp)
        now = _iso(_utcnow())
        found = False

        def _do(data: dict) -> None:
            nonlocal found
            rec = data["accounts"].get(fp)
            if rec is not None:
                rec["last_seen_at"] = now
                found = True

        self._mutate(_do)
        return found

    def bind_box(self, fp: str, box_ref: str) -> bool:
        """Bind a fingerprint to a box. Returns False when unknown."""
        fp = normalize_fingerprint(fp)
        if box_ref == "":
            raise RegistryError("box_ref must not be empty")
        with self._locked():
            data = self._load()
            rec = data["accounts"].get(fp)
            if rec is None:
                return False
            rec["box_ref"] = box_ref
            self._save(data)
            return True

    def rotate(self, old_fingerprint: str, *, key_line: str) -> dict:
        """Rotate to a new key, keeping the S1 policy: a new key is a new account.

        ``old_fingerprint`` must already be registered — rotation never
        implicitly registers (a typo'd old fingerprint must not mint an
        account), and the new key must NOT already be registered — merging
        two existing accounts under one rotation would silently misbind
        identities. The new key's public-key line is required (parsed via
        S1); a bare fingerprint is refused because rotate must verify the
        new key parses, not just the fingerprint's shape.

        Atomically (one lock, one store write): the old record is stamped
        ``rotated_to``/``rotated_at`` (its ``last_seen_at`` freezes — the
        rotation is the last lifecycle event), the new key registers as a
        NEW account (new ``acct_`` id per S1), the box binding is inherited
        so "same box" continuity survives the rotation, and a lineage entry
        lands in the bounded ``rotations`` journal (the audit trail S2
        noted ``remove`` lacks, scoped to rotation; capped at
        ``ROTATIONS_CAP``, oldest-first eviction).

        Returns ``{"old": old_record, "new": new_record,
        "rotation": journal_entry}``. ``lookup(old_fp)`` keeps returning the
        old record (with ``rotated_to``) — the link is followed, never
        silently dereferenced, because identity is still the key. Rotating
        an already-rotated key re-links forward (chains are legal; the
        journal records every hop).
        """
        old_fp = normalize_fingerprint(old_fingerprint)
        key = key_identity.parse_public_key(key_line)
        new_fp = fingerprint(key)
        if new_fp == old_fp:
            raise RegistryError("rotate needs a different key (old == new)")
        now = _iso(_utcnow())
        result: dict = {}

        def _do(data: dict) -> None:
            nonlocal result
            accounts = data["accounts"]
            old = accounts.get(old_fp)
            if old is None:
                raise RegistryError(
                    f"rotate: unknown old fingerprint {old_fp} "
                    "(register it first — rotation never implicitly registers)"
                )
            if new_fp in accounts:
                raise RegistryError(
                    f"rotate: new key {new_fp} is already registered "
                    "(rotation never merges two existing accounts)"
                )
            old["rotated_to"] = new_fp
            old["rotated_at"] = now
            new_rec = {
                "fingerprint": new_fp,
                "account_id": account_id_for(new_fp),
                "key_type": key.key_type,
                "created_at": now,
                "last_seen_at": now,
                "box_ref": old.get("box_ref"),
                "schema_version": SCHEMA_VERSION,
            }
            accounts[new_fp] = new_rec
            entry = {
                "old_fingerprint": old_fp,
                "old_account_id": old["account_id"],
                "new_fingerprint": new_fp,
                "new_account_id": new_rec["account_id"],
                "key_type": key.key_type,
                "box_ref": old.get("box_ref"),
                "rotated_at": now,
            }
            journal = data["rotations"]
            journal.append(entry)
            del journal[: max(0, len(journal) - ROTATIONS_CAP)]
            result = {
                "old": dict(old),
                "new": dict(new_rec),
                "rotation": dict(entry),
            }

        self._mutate(_do)
        return result

    def remove(self, fp: str) -> bool:
        """Delete an account record. Returns False when unknown."""
        fp = normalize_fingerprint(fp)
        found = False

        def _do(data: dict) -> None:
            nonlocal found
            if fp in data["accounts"]:
                del data["accounts"][fp]
                found = True

        self._mutate(_do)
        return found

    def accounts(self) -> list[dict]:
        """All account records, oldest first."""
        with self._locked():
            data = self._load()
            recs = [dict(r) for r in data["accounts"].values()]
        recs.sort(key=lambda r: (r.get("created_at", ""), r.get("fingerprint", "")))
        return recs

    def rotations(self) -> list[dict]:
        """Rotation lineage journal, oldest first (bounded at ROTATIONS_CAP)."""
        with self._locked():
            data = self._load()
            return [dict(e) for e in data["rotations"]]


# -- CLI ---------------------------------------------------------------------
def _cmd(argv: list[str] | None = None) -> int:
    # --registry-root lives on a shared parent parser so it is accepted
    # both before the subcommand (global position) and after it — an agent
    # or operator typing the subcommand first must not hit an argparse error
    # (Product blocker, round 1). The default is SUPPRESS, not None: a
    # subparser parses into a FRESH namespace and copies every key back
    # onto the main namespace, so a plain None default would silently
    # clobber a --registry-root given in the global position (QA blocker,
    # delta round: the flag resolved to the default root). With SUPPRESS
    # the subparser only sets the attribute when the flag is actually
    # present after the subcommand; given in both positions, the later
    # (subcommand) value wins.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--registry-root",
        default=argparse.SUPPRESS,
        help="registry directory (default: $XDG_STATE_HOME/spark-vm/key-registry)",
    )
    parser = argparse.ArgumentParser(
        prog="key_registry",
        parents=[common],
        description=(
            "SSH-key-as-account registry (#446, slice S2): remember "
            "first-connect keys on this box so the same key resumes the "
            "same account."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser(
        "register", parents=[common], help="register a key (idempotent)"
    )
    p_reg.add_argument("--key-line", help="one OpenSSH public-key line")
    p_reg.add_argument("--fingerprint", help="SHA256: fingerprint (needs --key-type)")
    p_reg.add_argument("--key-type", help="key type, with --fingerprint")
    p_reg.add_argument("--box-ref", default=None, help="box this account binds to")

    p_lookup = sub.add_parser(
        "lookup", parents=[common], help="show the record for a fingerprint"
    )
    p_lookup.add_argument("fingerprint")

    p_touch = sub.add_parser(
        "touch", parents=[common], help="refresh last_seen_at"
    )
    p_touch.add_argument("fingerprint")

    p_bind = sub.add_parser(
        "bind", parents=[common], help="bind a fingerprint to a box"
    )
    p_bind.add_argument("fingerprint")
    p_bind.add_argument("box_ref")

    p_remove = sub.add_parser(
        "remove", parents=[common], help="delete an account record"
    )
    p_remove.add_argument("fingerprint")

    p_rotate = sub.add_parser(
        "rotate",
        parents=[common],
        help=(
            "rotate to a new key (lineage-recorded re-registration; "
            "the new key becomes a new account per S1 policy)"
        ),
    )
    p_rotate.add_argument("old_fingerprint", help="already-registered old key")
    p_rotate.add_argument(
        "--key-line", required=True, help="one OpenSSH public-key line (the new key)"
    )

    p_manifest = sub.add_parser(
        "manifest",
        parents=[common],
        help="emit the resume manifest for a fingerprint (registry-issued)",
    )
    p_manifest.add_argument("fingerprint")

    sub.add_parser(
        "status", parents=[common], help="list all registered accounts"
    )

    args = parser.parse_args(argv)
    # getattr: with the SUPPRESS default the attribute is absent unless the
    # flag was given in either position.
    reg = KeyRegistry(root=getattr(args, "registry_root", None))

    def _out(obj: dict | list) -> int:
        # Data commands are JSON-first: the registry is an agent-operations
        # tool, and JSON is the contract (human-readable enough anyway).
        print(json.dumps(obj, indent=2, sort_keys=True))
        return 0

    def _resume_manifest(rec: dict) -> dict:
        # The registry-issued resume manifest: the same field vocabulary as
        # S1's first-connect manifest (harness/key_identity.py), with the
        # box_id slot filled from the registry's box binding — the slot S1's
        # README promised this slice would fill. vm_endpoint and claim_url
        # stay null: the endpoint is connect-time knowledge (a later wiring
        # slice) and the claim protocol is S3 (#446). "registry_issued"
        # distinguishes this document from S1's connect-time manifest.
        now = _iso(_utcnow())
        return {
            "manifest_version": key_identity.MANIFEST_VERSION,
            "account_id": rec["account_id"],
            "key_fingerprint": rec["fingerprint"],
            "key_type": rec["key_type"],
            "issued_at": now,
            "expires_at": None,
            "vm_endpoint": None,
            "box_id": rec["box_ref"],
            "claim_url": None,
            "registry_issued": True,
        }

    try:
        if args.command == "register":
            rec = reg.register(
                key_line=args.key_line,
                fingerprint_str=args.fingerprint,
                key_type=args.key_type,
                box_ref=args.box_ref,
            )
            return _out(rec)
        if args.command == "lookup":
            rec = reg.lookup(args.fingerprint)
            if rec is None:
                print(f"unknown fingerprint: {args.fingerprint}", file=sys.stderr)
                return 1
            return _out(rec)
        if args.command == "touch":
            if not reg.touch(args.fingerprint):
                print(f"unknown fingerprint: {args.fingerprint}", file=sys.stderr)
                return 1
            print("ok")
            return 0
        if args.command == "bind":
            if not reg.bind_box(args.fingerprint, args.box_ref):
                print(f"unknown fingerprint: {args.fingerprint}", file=sys.stderr)
                return 1
            print("ok")
            return 0
        if args.command == "remove":
            if not reg.remove(args.fingerprint):
                print(f"unknown fingerprint: {args.fingerprint}", file=sys.stderr)
                return 1
            print("ok")
            return 0
        if args.command == "rotate":
            return _out(reg.rotate(args.old_fingerprint, key_line=args.key_line))
        if args.command == "manifest":
            rec = reg.lookup(args.fingerprint)
            if rec is None:
                print(f"unknown fingerprint: {args.fingerprint}", file=sys.stderr)
                return 1
            return _out(_resume_manifest(rec))
        if args.command == "status":
            return _out(reg.accounts())
    except (RegistryError, KeyIdentityError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError("unreachable")  # pragma: no cover


if __name__ == "__main__":
    sys.exit(_cmd())
