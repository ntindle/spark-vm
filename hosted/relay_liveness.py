#!/usr/bin/env python3
"""Relay session-liveness journal — R1 passive instrument (GitHub #486).

Implements the §2 session-frame journal and the
``relay_session_liveness(vm_id)`` query from
``docs/RELAY_LIVENESS_DESIGN.md``. The relay daemon (the only honest
emitter — it owns the splice point) calls :func:`emit_frame` for every
tenant↔VM SSH session; the control plane's tenant layer (R3) reads
:func:`relay_session_liveness`.

Design decisions (all per the design doc, no improvisation):

- Frames are metadata only — timing and counters, never payload
  (metering doc's counters-over-content rule). ``validate_frame``
  rejects any key outside the §2 schema, so a future payload-bearing
  field cannot slip in silently; contract changes go through this
  module, not around it.
- Rotation is the journal's own contract, not a later fix (#376).
  The journal is bounded by bytes, with a fixed number of rotated
  generations — the total on-disk footprint is capped regardless of
  session volume. Unbounded = design defect, so the bound is a module
  constant, not a tuneable the daemon can forget.
- Prober exclusion is enforced at the journal, not trusted from the
  caller: a frame carrying the prober identity marker (R2's
  discriminator) is dropped, never journaled. A probe evidencing
  itself would collapse channels A and B into one.
- Cross-process locking: the relay daemon (writer) and the
  control-plane query (reader) run in different processes. Appends
  take an exclusive ``flock`` on a sidecar lock; rotation happens
  under the same lock; queries take the shared lock. Torn trailing
  lines are skipped by the reader, never fatal.
- Timestamps are epoch-seconds floats (``time.time()``) — stdlib
  only, so this module runs unchanged on the relay host, the hosted
  control plane, and the operator laptop, like ``tenant_status.py``.
  The idle threshold is 5 minutes without bytes (design §2: a real
  cadence-friendly number, not a product promise).

Slice boundaries: R2 wires the dial prober (active instrument, hands
this journal the identity-marker discriminator it already enforces);
R3 wires ``relay_session_liveness`` into the tenant-status producer;
R4 consumes it in the stuck-detector conjunct.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import time

# ---------------------------------------------------------------------------
# §2 — the frame schema (verbatim; metadata only, never payload)

FRAME_FIELDS = frozenset(
    {
        "session_id",  # opaque, control-plane-minted per SSH session
        "vm_id",  # ownership, per-box (§9 Q2)
        "tenant_id",  # optional ownership hint (G7 follow-up)
        "opened_at",  # SSH transport handshake completed through the relay
        "last_bytes_at",  # last observed byte, either direction
        "closed_at",  # session end, or None while open
        "close_cause",  # one of CLOSE_CAUSES when closed_at is set
        "hostkey_verified",  # pinned fingerprint matched at handshake
        "bytes_in",  # counters only
        "bytes_out",  # counters only
        "prober",  # identity-marker discriminator (R2); dropped, never journaled
    }
)

REQUIRED_FIELDS = frozenset(
    {
        "session_id",
        "vm_id",
        "opened_at",
        "last_bytes_at",
        "hostkey_verified",
        "bytes_in",
        "bytes_out",
    }
)

CLOSE_CAUSES = frozenset(
    {
        "client_closed",
        "relay_closed",
        "idle_timeout",
        "box_leg_lost",
        "handshake_failed",
    }
)

# Idle threshold: 5 minutes without bytes → state "idle" (§2).
IDLE_THRESHOLD_S = 300.0

# Rotation bound — the journal's own contract (#376). Worst-case total
# footprint: (MAX_ROTATED + 1) generations × (MAX_JOURNAL_BYTES + one
# row), since a generation can exceed the byte bound by the single row
# appended after the last rotation check.
MAX_JOURNAL_BYTES = 64 * 1024 * 1024
MAX_ROTATED = 3

DEFAULT_JOURNAL = "/var/lib/sparkvm/relay-session-journal.jsonl"


# ---------------------------------------------------------------------------
# Journal path


def journal_path():
    """Local journal path: ``$RELAY_SESSION_JOURNAL`` (tests/operator), else
    the control-plane default. The parent directory must exist — the
    control plane deploys it; a missing dir fails loud (OSError), never
    silently created somewhere the operator didn't choose."""
    return os.environ.get("RELAY_SESSION_JOURNAL") or DEFAULT_JOURNAL


# ---------------------------------------------------------------------------
# Frame validation


def _require(cond, msg):
    if not cond:
        raise ValueError(msg)


def validate_frame(frame):
    """Validate one §2 session frame. Raises ValueError on any contract
    violation. Unknown keys are rejected (never-payload enforcement);
    ``close_cause`` must be one of the five §2 causes exactly when the
    session is closed."""
    _require(isinstance(frame, dict), "frame must be a dict")
    unknown = set(frame) - FRAME_FIELDS
    _require(not unknown, "frame has non-schema fields: %s" % sorted(unknown))
    missing = REQUIRED_FIELDS - set(frame)
    _require(not missing, "frame missing required fields: %s" % sorted(missing))
    _require(
        isinstance(frame["session_id"], str) and frame["session_id"],
        "session_id must be a non-empty string",
    )
    _require(
        isinstance(frame["vm_id"], str) and frame["vm_id"],
        "vm_id must be a non-empty string",
    )
    if "tenant_id" in frame and frame["tenant_id"] is not None:
        _require(
            isinstance(frame["tenant_id"], str) and frame["tenant_id"],
            "tenant_id must be a non-empty string when present",
        )
    for ts in ("opened_at", "last_bytes_at"):
        _require(
            isinstance(frame[ts], (int, float)) and frame[ts] >= 0,
            "%s must be a non-negative epoch timestamp" % ts,
        )
    _require(
        frame["last_bytes_at"] >= frame["opened_at"],
        "last_bytes_at must not precede opened_at",
    )
    _require(
        isinstance(frame["hostkey_verified"], bool),
        "hostkey_verified must be a bool",
    )
    for counter in ("bytes_in", "bytes_out"):
        _require(
            isinstance(frame[counter], int)
            and not isinstance(frame[counter], bool)
            and frame[counter] >= 0,
            "%s must be a non-negative int counter" % counter,
        )
    closed = frame.get("closed_at")
    _require(
        closed is None or (isinstance(closed, (int, float)) and closed >= 0),
        "closed_at must be None or a non-negative epoch timestamp",
    )
    if closed is not None:
        _require(
            closed >= frame["last_bytes_at"],
            "closed_at must not precede last_bytes_at",
        )
    if closed is not None:
        _require(
            frame.get("close_cause") in CLOSE_CAUSES,
            "closed frame must carry one of the §2 close_cause values",
        )
    else:
        _require(
            frame.get("close_cause") is None,
            "open frame must not carry close_cause",
        )


# ---------------------------------------------------------------------------
# Bounded journal — append, rotate, read


@contextlib.contextmanager
def _journal_locked(path, exclusive=True):
    """Cross-process lock for journal writes/reads.

    The relay daemon (writer) and the control-plane query (reader) are
    different processes. Writers take LOCK_EX; readers take LOCK_SH so a
    read can never interleave with a rotation. Lock lives in a sidecar
    so the journal path itself is never opened read-write by the reader.
    """
    lock_path = path + ".lock"
    with open(lock_path, "a+b") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def _rotate_if_needed(path):
    """Rotate the journal when it would exceed its byte bound. Must be
    called with the exclusive lock held. Generation ``.1`` is newest;
    older generations shift up and ``.<MAX_ROTATED>`` is discarded, so
    total footprint is capped at (MAX_ROTATED + 1) × (MAX_JOURNAL_BYTES
    + one row). The bound is bytes, not rows — stated plainly so no
    reader assumes a row count the code doesn't enforce."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return
    if st.st_size < MAX_JOURNAL_BYTES:
        return
    oldest = "%s.%d" % (path, MAX_ROTATED)
    try:
        os.unlink(oldest)
    except FileNotFoundError:
        pass
    for gen in range(MAX_ROTATED - 1, 0, -1):
        src = "%s.%d" % (path, gen)
        dst = "%s.%d" % (path, gen + 1)
        try:
            os.rename(src, dst)
        except FileNotFoundError:
            pass
    os.rename(path, "%s.1" % path)


def _append_locked(path, frame):
    _rotate_if_needed(path)
    row = json.dumps(frame, separators=(",", ":"), sort_keys=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        f = os.fdopen(fd, "w", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with f:
        f.write(row)
        f.flush()
        os.fsync(f.fileno())


def emit_frame(**fields):
    """Emit one §2 session frame from the relay daemon.

    Returns ``"journaled"`` normally, or ``"dropped"`` when the frame
    carries the prober identity marker — R2's dial prober is
    control-plane traffic, and a probe evidencing itself would collapse
    channels A and B (design §2). The marker is enforced here, at the
    journal, not trusted from the caller path. Precedence note: the
    drop happens *before* schema validation — a malformed prober-marked
    frame returns ``"dropped"`` rather than raising. That is deliberate
    (prober traffic is never journaled, period), but it means a broken
    R2 discriminator would hide as drops instead of surfacing as a
    validation error; the prober's own tests must cover the marker shape.

    Raises ValueError on schema violations; raises OSError when the
    journal cannot be written (fail loud — the daemon operator must
    know the instrument is dark).
    """
    frame = dict(fields)
    if frame.pop("prober", False):
        return "dropped"
    validate_frame(frame)
    path = journal_path()
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        raise OSError("journal directory does not exist: %s" % parent)
    with _journal_locked(path, exclusive=True):
        _append_locked(path, frame)
    return "journaled"


def _iter_frames(path):
    """Yield (frame, generation) newest-first across the journal and its
    rotated generations. Each file is read newest-row-first so the first
    match for a vm is its latest frame. Tolerates torn trailing lines
    (a reader can race the writer's fsync); corrupt lines are skipped,
    never fatal — the query degrades, it does not crash. Undecodable
    bytes decode as replacement characters (a hand-edit or disk-level
    corruption can't crash the query; such a line never parses as JSON
    and is skipped like any other corrupt line)."""
    gens = [""] + [".%d" % g for g in range(1, MAX_ROTATED + 1)]
    for gen in gens:
        fname = path + gen
        try:
            f = open(fname, "r", encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
        with f:
            for line in reversed(f.readlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line), gen
                except (json.JSONDecodeError, ValueError):
                    continue


# ---------------------------------------------------------------------------
# §8 R1 — the control-plane query surface


def relay_session_liveness(vm_id, now=None):
    """``relay_session_liveness(vm_id)`` — the passive liveness instrument.

    Returns the newest frame for ``vm_id`` as
    ``{"session_id", "state", "last_bytes_at", "hostkey_verified"}``
    where state is one of ``active`` | ``idle`` | ``closed``:

    - ``closed`` — the session has ``closed_at`` (with a §2 cause).
    - ``idle`` — open, but no bytes for over ``IDLE_THRESHOLD_S``
      (5 minutes).
    - ``active`` — open with bytes inside the idle threshold:
      positive evidence the path is working right now.

    Returns None when the journal holds no frame for the vm — the
    instrument is dark for that box, and the caller (R3/R4) must treat
    darkness as insufficient-observability, never as ``ok``. A missing
    journal *directory* is also darkness (None), not an error: the
    module is designed to run on machines where the control-plane
    journal was never deployed (operator laptop, fresh plane). Only the
    writer fails loud.
    """
    if now is None:
        now = time.time()
    path = journal_path()
    latest = None
    try:
        with _journal_locked(path, exclusive=False):
            for frame, _gen in _iter_frames(path):
                if frame.get("vm_id") != vm_id:
                    continue
                latest = frame
                break  # newest-first: the first match wins
    except FileNotFoundError:
        # The lock sidecar's parent dir is missing — no journal can
        # exist here. Darkness, not an error.
        return None
    if latest is None:
        return None
    if latest.get("closed_at") is not None:
        state = "closed"
    elif now - latest["last_bytes_at"] > IDLE_THRESHOLD_S:
        state = "idle"
    else:
        state = "active"
    return {
        "session_id": latest["session_id"],
        "state": state,
        "last_bytes_at": latest["last_bytes_at"],
        "hostkey_verified": latest["hostkey_verified"],
    }


# ---------------------------------------------------------------------------
# Operator CLI — query surface smoke test

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="relay session-liveness journal (R1 passive instrument)"
    )
    ap.add_argument("--journal", default=None, help="journal path override")
    ap.add_argument(
        "--query", metavar="VM_ID", help="print liveness for VM_ID as JSON"
    )
    args = ap.parse_args()
    if args.journal:
        os.environ["RELAY_SESSION_JOURNAL"] = args.journal
    if args.query:
        print(json.dumps(relay_session_liveness(args.query), indent=2))
    else:
        ap.print_help()
