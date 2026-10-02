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

The claim/upgrade escape hatch is slice S3 (this module, #446): single-use
claim codes for the key-loss path S2.5 deferred. Issuing
(``KeyRegistry.issue_claim``) mints a 144-bit random code shown once to
the operator — the registry stores ONLY its SHA-256 hash — with an
expiry (default 7 days); redeeming (``KeyRegistry.redeem_claim``) is
single-use and expiry-enforced under one lock, stamping the record
``claimed_at``/``claimed_by``. Per S1's policy, a new key is still a new
account; claim is the upgrade path, not a registration path (issue
never implicitly registers).

Key rotation is slice S2.5 (this module, :meth:`KeyRegistry.rotate`): the
operator-facing path for a key the operator still holds — "I generated a
new key and want this box to know it's me". Rotation registers the new key
as a NEW account (the S1 policy stands: identity is the key), marks the
old record with ``rotated_to``/``rotated_at``, inherits the box binding,
and appends an entry to the bounded ``rotations`` journal — the audit
trail ``remove`` lacked before #825 (which gave deletions their own
bounded journal), so this one stays scoped to rotation. Lost-key rotation
(no old key to attest with) is NOT this slice; it needs the claim
protocol (S3).
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import hmac
import json
import math
import os
import secrets
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
# Sane range: 1..2**31 — 0 would silently empty the journal on every
# rotate (degenerate config, not guarded against by design).
ROTATIONS_CAP = 1000
# Bounded deletion journal (#825): the same #376 lesson as ROTATIONS_CAP —
# unbounded = fail. `remove()` is the most identity-destructive operation
# the registry offers; before S2.5's journal landed it was also the only
# one with no audit trail at all. The journal bounds audit history, never
# lineage: a deleted record's lineage context (rotated_to/rotated_at,
# claimed_at/claimed_by) is copied into the deletion entry, so "never
# registered" and "registered and deleted" stay distinguishable.
DELETIONS_CAP = 1000
# Stale-tmp sweep (#824, the #716 class): _save() publishes via mkstemp +
# os.replace, and a writer killed between the two leaves a
# registry.json.tmp.* orphan no code path ever swept (verified on main).
# Tmps younger than this are assumed live (a writer mid-publish is always
# younger); older ones are crash litter. Fleet's #716 fix uses the same
# 1h rule — one shared convention across the journal stores.
STALE_TMP_AGE_S = 3600.0
# Claim protocol (slice S3, #446): single-use claim codes. 144 bits of
# entropy (18 bytes -> 24 base64url chars) keeps brute force infeasible
# even at bot scale. Default TTL 7 days: long enough for a human to
# redeem at their own pace, short enough that a leaked code dies on its
# own. Only SHA-256 hashes are ever stored — a stolen registry.json
# yields no live claim codes.
CLAIM_CODE_ENTROPY_BYTES = 18
CLAIM_DEFAULT_TTL_HOURS = 24 * 7


def _claim_code_hash(code: str) -> str:
    """SHA-256 hash of a claim code, ``"sha256:<hex>"``.

    Only hashes are ever stored; the plaintext code is shown once at
    issue time. Garbage (non-ASCII) input is a loud RegistryError, never
    a traceback — the CLI's error path catches RegistryError only.
    """
    if not isinstance(code, str) or not code:
        raise RegistryError("claim code must be a non-empty string")
    try:
        digest = hashlib.sha256(code.encode("ascii")).hexdigest()
    except UnicodeEncodeError as exc:
        raise RegistryError("claim code is not ASCII") from exc
    return "sha256:" + digest


def _new_claim_code() -> str:
    """Mint a fresh claim code whose first character is never ``-``.

    ``secrets.token_urlsafe`` draws from the base64url alphabet, which
    includes ``-`` — a code starting with ``-`` breaks the CLI's
    positional ``claim-redeem <code>`` form (argparse reads the token as
    an option flag; GH CI run 36692398265 failed
    ``test_claim_cli_round_trip`` exactly this way, ~1/64 of runs).
    Regenerating on a leading ``-`` keeps the positional form working
    for every issued code; ``--code-stdin`` remains the
    /proc-visibility-safe path. Entropy cost is one extra draw with
    probability 1/64 — negligible against 144 bits.
    """
    code = secrets.token_urlsafe(CLAIM_CODE_ENTROPY_BYTES)
    while code.startswith("-"):
        code = secrets.token_urlsafe(CLAIM_CODE_ENTROPY_BYTES)
    return code


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
        self._sweep_stale_tmps()
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
    def _sweep_stale_tmps(self) -> None:
        """Unlink crash-orphaned ``registry.json.tmp.*`` files older than
        ``STALE_TMP_AGE_S`` (#824, the #716 class).

        Called at lock entry (from ``_locked``, before the lock is
        acquired): the 1h age threshold is what makes this safe without
        holding the lock — a live writer's tmp is always younger than
        the threshold, so a tmp this sweep touches can belong to no
        running writer. Concurrent sweepers race safely —
        ``missing_ok`` absorbs the lost race. A tmp that cannot be
        stat'ed or unlinked is left alone; the sweep is best-effort
        litter control, never a correctness gate.
        """
        prefix = STORE_NAME + ".tmp."
        now = time.time()
        try:
            names = os.listdir(self.root)
        except OSError:
            return
        for name in names:
            if not name.startswith(prefix):
                continue
            path = self.root / name
            try:
                if now - path.stat().st_mtime < STALE_TMP_AGE_S:
                    continue
                path.unlink(missing_ok=True)
            except OSError:
                continue

    def _load(self) -> dict:
        """Read the store. Missing file -> empty store. Corrupt -> raise."""
        try:
            text = self.store_path.read_text()
        except FileNotFoundError:
            return {
                "schema_version": SCHEMA_VERSION,
                "accounts": {},
                "rotations": [],
                "deletions": [],
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
        deletions = data.get("deletions", [])
        if not isinstance(deletions, list) or not all(
            isinstance(entry, dict) for entry in deletions
        ):
            raise RegistryError(
                f"registry deletions journal has unexpected shape, "
                f"refusing to proceed: {self.store_path}"
            )
        data["deletions"] = deletions  # normalize: missing key -> empty journal
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
        ``rotated_to``/``rotated_at`` (rotation itself does not advance the
        record's ``last_seen_at`` — the rotation is recorded in
        ``rotated_at``; liveness via ``touch()`` or re-``register()`` still
        updates ``last_seen_at`` afterwards, rotation is lineage not a ban),
        the new key registers as a NEW account (new ``acct_`` id per S1),
        the box binding is inherited so "same box" continuity survives the
        rotation, and a lineage entry lands in the bounded ``rotations``
        journal (the audit trail ``remove`` lacked before #825 gave it its
        own bounded ``deletions`` journal, so this one stays scoped to
        rotation; capped at ``ROTATIONS_CAP``, oldest-first eviction).

        Trust boundary: ``rotate()`` performs NO cryptographic proof that
        the caller holds the old key — attestation is assumed from the
        caller (the local operator rotating their own key). A network
        caller must prove possession before calling; the claim protocol
        (S3, #446) owns that decision, not this slice.

        Returns ``{"old": old_record, "new": new_record,
        "rotation": journal_entry}``. ``lookup(old_fp)`` keeps returning the
        old record (with ``rotated_to``) — the link is followed, never
        silently dereferenced, because identity is still the key. Rotating an
        already-rotated key is refused (RegistryError: rotate the LATEST key)
        — the record pointer and the journal must never diverge on who the
        current key is. Chains are built by rotating forward: rotate(old)
        then rotate(new), each hop journaled.
        """
        old_fp = normalize_fingerprint(old_fingerprint)
        if not isinstance(key_line, str) or not key_line.strip():
            raise RegistryError("rotate needs the new key's public-key line")
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
            if old.get("rotated_to") is not None:
                raise RegistryError(
                    f"rotate: {old_fp} already rotated to {old['rotated_to']} "
                    "(rotate the latest key — the record pointer and the "
                    "journal must never diverge)"
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

    def issue_claim(
        self, fp: str, *, ttl_hours: int | float = CLAIM_DEFAULT_TTL_HOURS
    ) -> dict:
        """Issue a single-use claim code for a registered account (slice S3).

        The claim code is the key-loss escape hatch #446 promised: an
        operator who no longer holds the old key upgrades a key-only
        account to a claimed account by redeeming the code the operator
        was shown at issue time. One live code per account — issuing a
        new code revokes the old one. The registry stores ONLY the
        SHA-256 hash of the code (``"sha256:<hex>"``); the plaintext is
        returned once in the result and must be shown to the operator
        then, because it cannot be recovered later.

        ``ttl_hours`` must be positive. Expiry is checked on redeem
        against the registry's own clock (``_utcnow``); expired codes are
        refused and removed. Issue requires a REGISTERED fingerprint —
        like rotate, issuing never implicitly registers (a typo must not
        mint an account).

        Returns ``{"account_id", "claim_code", "expires_at",
        "ttl_hours"}``. ``claim_code`` is the plaintext code — shown once.
        """
        fp = normalize_fingerprint(fp)
        # bool is a subclass of int — True would mean a 1-hour TTL, which
        # is never what the caller meant; nan/inf sail past `<= 0` and
        # then die as ValueError/OverflowError inside timedelta (raw
        # traceback, not RegistryError). Finite and positive, or refuse.
        if (
            not isinstance(ttl_hours, (int, float))
            or isinstance(ttl_hours, bool)
            or not math.isfinite(ttl_hours)
            or ttl_hours <= 0
        ):
            raise RegistryError("issue_claim needs ttl_hours > 0 (finite)")
        now_dt = _utcnow()
        now = _iso(now_dt)
        code = _new_claim_code()
        code_hash = _claim_code_hash(code)
        expires_at = _iso(now_dt + datetime.timedelta(hours=ttl_hours))
        issued: dict = {}

        def _do(data: dict) -> None:
            nonlocal issued
            accounts = data["accounts"]
            rec = accounts.get(fp)
            if rec is None:
                raise RegistryError(
                    f"issue_claim: unknown fingerprint {fp} "
                    "(register it first — issuing never implicitly registers)"
                )
            if rec.get("rotated_to") is not None:
                # A rotated-out record is superseded lineage, not a live
                # identity — claiming it would stamp a dead record. Same
                # fail-loud rule as rotate's "rotate the latest key".
                raise RegistryError(
                    f"issue_claim: {fp} was rotated to {rec['rotated_to']} "
                    "(claim the latest key, not a rotated-out record)"
                )
            rec["claim"] = {
                "code_hash": code_hash,
                "issued_at": now,
                "expires_at": expires_at,
                "ttl_hours": ttl_hours,
            }
            issued = {
                "account_id": rec["account_id"],
                "claim_code": code,
                "expires_at": expires_at,
                "ttl_hours": ttl_hours,
            }

        self._mutate(_do)
        return issued

    def redeem_claim(self, code: str, *, claimed_by: str | None = None) -> dict:
        """Redeem a claim code, upgrading the account to claimed (slice S3).

        Single-use and expiry-enforced, atomically under the lock: the
        first successful redeem consumes the code (the ``claim`` entry is
        deleted) and stamps the record ``claimed_at``/``claimed_by``; a
        racing second redeem finds no live code and fails. An expired
        code is refused AND removed (self-cleaning — the holder proved
        knowledge of the code, which is the credential, so nothing an
        attacker could have learned is destroyed). Unknown codes fail
        loudly. Hash comparison is constant-time (``hmac.compare_digest``)
        — not because timing matters at these code sizes, but because
        non-constant comparison is a habit the security half of this file
        does not want to teach.

        Re-claiming an already-claimed account is allowed: a fresh
        ``issue_claim`` mints a new code, and redeeming it restamps
        ``claimed_at``/``claimed_by`` (label change is a feature, not an
        error). The ``claim`` entry on a record always describes the ONE
        currently-live code; the ``claimed_*`` stamps describe the most
        recent successful redemption.
        """
        presented = _claim_code_hash(code)
        now = _iso(_utcnow())
        redeemed: dict = {}
        # _mutate persists whatever fn leaves behind and ABORTS the save
        # when fn raises — so the expired-code self-clean must persist
        # FIRST and raise AFTER, never raise from inside fn.
        expired: dict | None = None

        def _do(data: dict) -> None:
            nonlocal redeemed, expired
            for fp, rec in data["accounts"].items():
                claim = rec.get("claim")
                if not isinstance(claim, dict):
                    continue
                if hmac.compare_digest(claim.get("code_hash", ""), presented):
                    if claim.get("expires_at", "") <= now:
                        del rec["claim"]  # expired: self-clean on disk...
                        expired = {
                            "account_id": rec.get("account_id"),
                            "expires_at": claim.get("expires_at"),
                        }
                        return  # ...then refuse below, after the save
                    del rec["claim"]  # single-use: consumed on success
                    rec["claimed_at"] = now
                    rec["claimed_by"] = claimed_by
                    redeemed = {
                        "account_id": rec["account_id"],
                        "claimed_at": now,
                        "claimed_by": claimed_by,
                    }
                    return

        self._mutate(_do)
        if expired is not None:
            raise RegistryError(
                f"claim code for {expired['account_id']} expired "
                f"(expired_at={expired['expires_at']})"
            )
        if not redeemed:
            raise RegistryError("unknown or already-redeemed claim code")
        return redeemed

    def remove(self, fp: str) -> bool:
        """Delete an account record. Returns False when unknown.

        The deletion is journaled (#825): the most identity-destructive
        operation the registry offers used to be the only one with no
        audit trail. The entry copies the deleted record's lineage
        context (rotated_to/rotated_at, claimed_at/claimed_by) so a
        deleted account stays distinguishable from a never-registered
        one. The journal is bounded at ``DELETIONS_CAP`` (oldest-first
        eviction), like ``rotations``.
        """
        fp = normalize_fingerprint(fp)
        found = False

        def _do(data: dict) -> None:
            nonlocal found
            accounts = data["accounts"]
            rec = accounts.get(fp)
            if rec is None:
                return
            now = _iso(_utcnow())
            journal = data["deletions"]
            journal.append(
                {
                    "fingerprint": fp,
                    "account_id": rec.get("account_id"),
                    "key_type": rec.get("key_type"),
                    "box_ref": rec.get("box_ref"),
                    "created_at": rec.get("created_at"),
                    "last_seen_at": rec.get("last_seen_at"),
                    "rotated_to": rec.get("rotated_to"),
                    "rotated_at": rec.get("rotated_at"),
                    "claimed_at": rec.get("claimed_at"),
                    "claimed_by": rec.get("claimed_by"),
                    "deleted_at": now,
                }
            )
            del journal[: max(0, len(journal) - DELETIONS_CAP)]
            del accounts[fp]
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

    def deletions(self) -> list[dict]:
        """Deletion audit journal, oldest first (bounded at DELETIONS_CAP).

        Each entry carries the deleted record's lineage context
        (rotated_to/rotated_at, claimed_at/claimed_by) plus deleted_at,
        so "registered and deleted" is never confusable with
        "never registered" (#825).
        """
        with self._locked():
            data = self._load()
            return [dict(e) for e in data["deletions"]]


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

    p_claim_issue = sub.add_parser(
        "claim-issue",
        parents=[common],
        help=(
            "issue a single-use claim code for a registered fingerprint "
            "(the code prints once — the registry stores only its hash)"
        ),
    )
    p_claim_issue.add_argument("fingerprint")
    p_claim_issue.add_argument(
        "--ttl-hours",
        type=float,
        default=CLAIM_DEFAULT_TTL_HOURS,
        help=f"code lifetime in hours (default {CLAIM_DEFAULT_TTL_HOURS}, must be > 0)",
    )

    p_claim_redeem = sub.add_parser(
        "claim-redeem",
        parents=[common],
        help="redeem a claim code, stamping the account claimed",
    )
    p_claim_redeem.add_argument(
        "code",
        nargs="?",
        default=None,
        help=(
            "claim code (WARNING: a positional code is visible in the "
            "process list and shell history — on a multi-user host use "
            "--code-stdin instead)"
        ),
    )
    p_claim_redeem.add_argument(
        "--code-stdin",
        action="store_true",
        help="read the claim code from stdin instead of argv",
    )
    p_claim_redeem.add_argument(
        "--claimed-by",
        default=None,
        help="operator label/email recorded as the claimer",
    )

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
        if args.command == "claim-issue":
            return _out(
                reg.issue_claim(args.fingerprint, ttl_hours=args.ttl_hours)
            )
        if args.command == "claim-redeem":
            # The code is a bearer credential: argv exposes it in the
            # process list (/proc/<pid>/cmdline, ps) and shell history,
            # so --code-stdin is the safe path on multi-user hosts.
            if args.code_stdin and args.code is not None:
                print(
                    "error: pass the claim code via stdin or argv, not both",
                    file=sys.stderr,
                )
                return 2
            code = sys.stdin.read().strip() if args.code_stdin else args.code
            if not code:
                print(
                    "error: claim-redeem needs a code "
                    "(positional, or --code-stdin)",
                    file=sys.stderr,
                )
                return 2
            return _out(reg.redeem_claim(code, claimed_by=args.claimed_by))
        if args.command == "status":
            return _out(reg.accounts())
    except (RegistryError, KeyIdentityError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError("unreachable")  # pragma: no cover


if __name__ == "__main__":
    sys.exit(_cmd())
