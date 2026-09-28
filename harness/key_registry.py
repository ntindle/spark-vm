#!/usr/bin/env python3
"""SSH-key-as-account registry (GitHub #446, slice S2: storage + lookup).

Slice S1 (``harness/key_identity.py``) is the stateless half: parse a public
key, fingerprint it, derive the stable opaque account id. This module is the
stateful half: a per-host registry mapping SSH key fingerprints to account
records — ``created_at``, ``last_seen_at``, key type, box binding, and claim
state. "Same key -> same box" resume state lives here.

Storage and lookup choices (the design half of #446's acceptance criteria):
- Single JSON file (``<root>/registry.json``) keyed by the OpenSSH
  ``SHA256:`` fingerprint string. Chose flat JSON over sqlite on purpose:
  no schema migrations at this scale, human-inspectable on the box, and
  the whole store is stdlib ``json`` — the module keeps S1's stdlib-only
  discipline (runs unchanged on the self-hosted box, the hosted control
  plane, and the operator laptop).
- Interprocess mutual exclusion is a lockdir (``<root>/registry.lock.d``)
  created with ``os.mkdir`` (atomic on POSIX). fcntl locks are not portable
  (the operator laptop may be macOS, the box is Linux); the lockdir works
  on both, and across threads in one process too.
- Writes are atomic: temp file (``O_EXCL``) + ``os.replace``. A crashed
  writer can never leave a half-written registry behind.
- Corrupt ``registry.json`` fails closed (``RegistryError``), never silently
  reset: identity misbinding is worse than downtime. The operator recovery
  path is documented in ``docs/KEY_IDENTITY_REGISTRY.md``.

No secrets: records hold only public fingerprints, one-way derived account
ids, and operator-visible metadata. The store is ``0o600`` / root dir
``0o700`` anyway — the account ids map to whoever's keys, and defense in
depth costs nothing.

Key rotation and the claim/upgrade escape hatch are LATER slices (see
#446): here a new key is a new account (same policy as S1), and
``mark_claimed`` only records the operator's claim decision — it does not
implement the claim protocol.
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

    Raises KeyIdentityError: fingerprints are identity, and a malformed one
    must never silently become a different record key.
    """
    if not isinstance(fp, str) or not fp.startswith("SHA256:"):
        raise KeyIdentityError(f"not an OpenSSH SHA256 fingerprint: {fp!r}")
    b64 = fp[len("SHA256:") :]
    if not b64 or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in b64):
        raise KeyIdentityError(f"not an OpenSSH SHA256 fingerprint: {fp!r}")
    # account_id_for re-validates length/shape; keep the derivation and the
    # registry on the same acceptance rule.
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
            try:
                os.mkdir(self.lock_path)
                break
            except FileExistsError:
                if not self._lock_holder_alive():
                    # Stale lock: the holder died mid-write. Reclaim by
                    # removing and re-creating. (Pid-reuse race: a recycled
                    # pid would make us wait instead of reclaim — a
                    # liveness miss, never a corruption.)
                    try:
                        (self.lock_path / "pid").unlink(missing_ok=True)
                        os.rmdir(self.lock_path)
                    except OSError:
                        pass  # lost the race to another reclaimer; retry
                    continue
                if time.monotonic() >= deadline:
                    raise RegistryError(
                        f"registry lock not acquired within {LOCK_TIMEOUT_S}s: "
                        f"{self.lock_path}"
                    )
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
            return {"schema_version": SCHEMA_VERSION, "accounts": {}}
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
                "claimed": False,
                "claimed_at": None,
                "schema_version": SCHEMA_VERSION,
            }
            accounts[fp] = record

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
        with self._locked():
            data = self._load()
            rec = data["accounts"].get(fp)
            if rec is None:
                return False
            rec["box_ref"] = box_ref
            self._save(data)
            return True

    def mark_claimed(self, fp: str) -> bool:
        """Record the operator's claim decision. Returns False when unknown.

        This only records the decision (the claim protocol itself is a later
        slice per #446); ``claimed_at`` is the audit timestamp.
        """
        fp = normalize_fingerprint(fp)
        now = _iso(_utcnow())
        found = False

        def _do(data: dict) -> None:
            nonlocal found
            rec = data["accounts"].get(fp)
            if rec is not None:
                rec["claimed"] = True
                rec["claimed_at"] = now
                rec["last_seen_at"] = now
                found = True

        self._mutate(_do)
        return found

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


# -- CLI ---------------------------------------------------------------------
def _cmd(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="key_registry",
        description=(
            "SSH-key-as-account registry (#446, slice S2): remember "
            "first-connect keys on this box so the same key resumes the "
            "same account."
        ),
    )
    parser.add_argument(
        "--registry-root",
        default=None,
        help="registry directory (default: $XDG_STATE_HOME/spark-vm/key-registry)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="register a key (idempotent)")
    p_reg.add_argument("--key-line", help="one OpenSSH public-key line")
    p_reg.add_argument("--fingerprint", help="SHA256: fingerprint (needs --key-type)")
    p_reg.add_argument("--key-type", help="key type, with --fingerprint")
    p_reg.add_argument("--box-ref", default=None, help="box this account binds to")

    p_lookup = sub.add_parser("lookup", help="show the record for a fingerprint")
    p_lookup.add_argument("fingerprint")

    p_touch = sub.add_parser("touch", help="refresh last_seen_at")
    p_touch.add_argument("fingerprint")

    p_claim = sub.add_parser("claim", help="record the operator's claim decision")
    p_claim.add_argument("fingerprint")

    p_bind = sub.add_parser("bind", help="bind a fingerprint to a box")
    p_bind.add_argument("fingerprint")
    p_bind.add_argument("box_ref")

    p_remove = sub.add_parser("remove", help="delete an account record")
    p_remove.add_argument("fingerprint")

    sub.add_parser("status", help="list all registered accounts")

    args = parser.parse_args(argv)
    reg = KeyRegistry(root=args.registry_root)

    def _out(obj: dict | list) -> int:
        # Data commands are JSON-first: the registry is an agent-operations
        # tool, and JSON is the contract (human-readable enough anyway).
        print(json.dumps(obj, indent=2, sort_keys=True))
        return 0

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
        if args.command == "claim":
            if not reg.mark_claimed(args.fingerprint):
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
        if args.command == "status":
            return _out(reg.accounts())
    except (RegistryError, KeyIdentityError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError("unreachable")  # pragma: no cover


if __name__ == "__main__":
    sys.exit(_cmd())
