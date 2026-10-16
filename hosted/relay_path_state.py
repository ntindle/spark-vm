"""R2b — the ``relay_path_state`` producer contract (issue #1415).

The relay-liveness lane's second build unit
(``docs/RELAY_LIVENESS_REMAINING_BUILDS_GAP_ANALYSIS.md`` §4, slice #1415):
it turns #1414's probe outcomes (``hosted/relay_dial_prober.py`` §3
taxonomy) into the §5 producer contract the R3/R4 consumers build
against — ``relay_path_state(vm_id) → ok | degraded | down``, with the
§3 sub-code (``relay`` | ``cert`` | ``box-leg``) on ``down`` readings —
plus the probe cadence driver and an operator-visible query surface.

The §5 value mapping, pinned in code (not doc-only):

- ``path_ok`` → ``ok`` — but only with passive corroboration: the
  journal's newest frame for the box must be ``active``. ``path_ok``
  against an ``idle``/``closed``/missing journal reads ``degraded``
  (no passive corroboration — the pinned "stale past the §2 idle
  threshold while the prober still reports ok" case; darkness counts as
  stale for this purpose, since any non-active journal reading means
  the passive channel has nothing fresh).
- ``relay_defect`` / ``cert_defect`` / ``box_leg_defect`` → ``down``
  with the matching sub-code. A defect is positive evidence of a
  broken path — it is never softened by the journal.
- ``provider_not_running`` → ``degraded``, no sub-code. The prober
  stands down when the provider is not ``running`` (design §3: provider
  state is the authority, probing is not a liveness question), so the
  reading is insufficient-observability, never evidence. ``degraded``
  never fires transition rule 6 (the rule fires on ``down`` only,
  D-RL2-4).
- Flapping — the last two *liveness-bearing* probe outcomes disagree —
  reads ``degraded`` regardless of the latest outcome. A liveness-bearing
  outcome is ``path_ok`` or one of the three defects;
  ``provider_not_running`` is not liveness-bearing and never counts
  toward flapping. (A lone defect reading with no predecessor still
  reads ``down``: one defect is evidence; two identical defect
  outcomes are confirmation; any disagreement — including on the
  sub-code — is suspicion, and a suspect reading must never fire
  transition rule 6.)
- Never probed → ``degraded`` ("no probe data"), never ``ok``:
  insufficient-observability is never assumed-``ok`` (design §5).

Cadence (F-RL2-3): probe while a post-``live`` arc exists on the box;
stand down when the H4 provider state reads ``suspended``/``destroyed``.
Default cadence 5 minutes, tunable (constructor/param, or the
``RELAY_PROBE_CADENCE_S`` env override) — the default is a shipped
detection-budget fit, explicitly not the §9 Q1 product call.

Multi-box tenants (D-RL2-6): the reading is per ``vm_id``. The
live-anchor box's reading is the tenant-driving one; other boxes'
readings stay on the operator surface. Anchor selection is the tenant
layer's knowledge (R3's wiring) — this module does not wire the
tenant layer (§5 interim honesty, same discipline as R1's journal).

D-RL2-3 (re-pin per session): probe bundles (relay host/port + pinned
fingerprint) are caller-supplied per probe and are never persisted —
the probe-history store records outcomes only, never fingerprints.

Stdlib only, like ``relay_liveness.py`` — this module must run
unchanged on the control plane without extra dependencies.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import json
import math
import os
import sys
import time

from hosted import relay_dial_prober
from hosted import relay_liveness

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

STATE_OK = "ok"
STATE_DEGRADED = "degraded"
STATE_DOWN = "down"

STATES = frozenset({STATE_OK, STATE_DEGRADED, STATE_DOWN})

SUB_RELAY = "relay"
SUB_CERT = "cert"
SUB_BOX_LEG = "box-leg"

SUBCODES = frozenset({SUB_RELAY, SUB_CERT, SUB_BOX_LEG})

_DEFECT_SUBCODES = {
    relay_dial_prober.RELAY_DEFECT: SUB_RELAY,
    relay_dial_prober.CERT_DEFECT: SUB_CERT,
    relay_dial_prober.BOX_LEG_DEFECT: SUB_BOX_LEG,
}

# Outcomes that carry liveness evidence. provider_not_running is a
# stand-down report, not a liveness reading (design §3).
_LIVENESS_OUTCOMES = frozenset(
    {
        relay_dial_prober.PATH_OK,
        relay_dial_prober.RELAY_DEFECT,
        relay_dial_prober.CERT_DEFECT,
        relay_dial_prober.BOX_LEG_DEFECT,
    }
)

# ---------------------------------------------------------------------------
# Cadence
# ---------------------------------------------------------------------------

# D-RL2-2 — 5-minute probe cadence default, tunable, not the Q1 product call.
DEFAULT_CADENCE_S = 300.0

# The cadence driver stands down on exactly these H4 provider states
# (issue #1415: "stand down when the H4 provider state reads
# suspended/destroyed"). Other non-running states are the prober's
# problem: probe() itself stands down on anything != "running" and
# reports provider_not_running, which this module maps to degraded.
_STAND_DOWN_STATES = frozenset({"suspended", "destroyed"})


def cadence_s():
    """Effective probe cadence in seconds.

    ``RELAY_PROBE_CADENCE_S`` overrides the default; unparseable values
    fail closed to the default rather than to a surprising cadence.
    """
    raw = os.environ.get("RELAY_PROBE_CADENCE_S")
    if raw is None:
        return DEFAULT_CADENCE_S
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_CADENCE_S
    if not math.isfinite(value) or not (value > 0):
        return DEFAULT_CADENCE_S
    return value


def cadence_decision(
    *,
    provider_state,
    has_post_live_arc,
    now=None,
    last_probe_at=None,
    cadence=None,
):
    """Decide whether the box should be probed right now.

    Returns ``(should_probe, reason)``. The provider state is a plain
    string read through the H4 interface by the caller ("read the
    interface, not the driver", F-RL2-4); ``has_post_live_arc`` is the
    tenant layer's answer to "does a post-``live`` arc exist on this
    box" (the prober's job starts at ``live``). ``last_probe_at`` is an
    epoch timestamp of the previous probe; ``cadence`` overrides the
    default cadence in seconds.

    A future-dated ``last_probe_at`` (clock skew) is clamped to ``now``
    — the fail-safe choice is to probe, not to delay silently.
    """
    if now is None:
        now = time.time()
    if cadence is None:
        cadence = cadence_s()
    if provider_state in _STAND_DOWN_STATES:
        return False, "stand-down: provider state is %r" % (provider_state,)
    if not has_post_live_arc:
        return (
            False,
            "stand-down: no post-live arc on the box — "
            "the prober's job starts at live",
        )
    if last_probe_at is None:
        return True, "due: never probed"
    if last_probe_at > now:
        # Clock skew (or a bogus future timestamp): the fail-safe
        # choice is to probe, not to delay silently.
        return True, "due: last probe timestamp is in the future"
    wait = cadence - (now - last_probe_at)
    if wait <= 0:
        return True, "due: cadence elapsed"
    return False, "next probe in %.0fs" % (wait,)


# ---------------------------------------------------------------------------
# Probe-history store
# ---------------------------------------------------------------------------

# Outcomes only — never fingerprints (D-RL2-3). One JSON object per
# line; corrupt lines are skipped by readers, never fatal. The store is
# created 0o600 in a 0o700 parent and opened with O_NOFOLLOW: a symlink at
# the final path component fails loud instead of redirecting appends
# (#1537).
_HISTORY_MAX_BYTES = 4 * 1024 * 1024  # 4 MiB, then rotate
_HISTORY_MAX_ROTATED = 2
# Unbounded liveness-outcome scan bound: the flapping check must see
# past arbitrarily long stand-down runs (Engineering B1). The file is
# 4 MiB-bounded, so this is O(file), not O(infinity).
_HISTORY_SCAN_LIMIT = 1 << 62


# ---------------------------------------------------------------------------
# Probe-history cross-process lock (#1540)
# ---------------------------------------------------------------------------

# Same bounded-wait discipline as relay_liveness._journal_locked (#1082):
# LOCK_NB in a retry loop up to a deadline, then a loud HistoryLockError
# naming the lock file and pointing the operator at the stopped/wedged
# holder. Kept in this module (not imported from relay_liveness) on
# purpose: the helper's contract text names the instrument it guards,
# and a HistoryLockError caught around a relay-journal call (or vice
# versa) must never silently pass as the other instrument's failure —
# the discipline is shared by documentation and review, not by import.
#
# Deliberate divergences from relay_liveness._journal_locked (same list
# style as that helper's own divergence notes against
# fleet/events.py::journal_lock):
#   1. HistoryLockError is module-local here and NOT interchangeable
#      with relay_liveness.JournalLockError — each names its own
#      instrument in its failure text; catching one around the other's
#      call misses the wedge.
#   2. The default wait is 60 s (the journal's is 300 s): a
#      probe-history critical section is a sub-millisecond append and
#      the cadence is periodic, so a genuinely wedged holder should
#      fail loud well before the journal's daemon-scale deadline.
#   3. FileNotFoundError on the sidecar is NOT wrapped here either —
#      but the reader maps it to "no records" (see _iter_history),
#      where the journal reader maps it to darkness (None). An absent
#      history is advisory-state absence in both cases; a wedge is a
#      broken instrument in both cases. They must not share an error
#      shape.
_HISTORY_LOCK_WAIT_TIMEOUT_S = 60.0
_HISTORY_LOCK_POLL_INTERVAL_S = 0.1


class HistoryLockError(OSError):
    """The probe-history lock could not be acquired within the deadline.

    Subclasses OSError so the write path's "fail loud on OSError"
    contract is preserved while the failure class stays nameable —
    tests, the operator CLI, and the query path's deliberate raise (a
    wedged instrument is an error, not advisory absence) all key on
    the name.
    """


@contextlib.contextmanager
def _history_locked(path, exclusive=True, timeout_s=None):
    """Cross-process lock for probe-history writes/reads, with a bounded
    wait.

    The cadence driver (writer) and the operator query / the
    flapping-memory scan (readers) can be different processes.
    Writers take LOCK_EX; readers take LOCK_SH so a read can never
    interleave with a rotation. The lock lives in a sidecar so the
    history path itself is never opened read-write by the reader.

    Bounded wait (#1540, same discipline as #1082): the lock is
    attempted with LOCK_NB in a retry loop for up to timeout_s
    seconds (default _HISTORY_LOCK_WAIT_TIMEOUT_S), then raises
    HistoryLockError naming the lock file and the likely cause,
    instead of blocking forever behind a stopped (SIGSTOP) or wedged
    holder. Waiting callers still serialize — only the pathological
    wait becomes a loud failure.

    A missing lock sidecar (FileNotFoundError) is NOT wrapped: the
    reader maps it to no-records and the writer already creates the
    parent directory before locking. Absence is an absent instrument;
    a wedge is a broken one — they must not share an error shape.
    """
    if timeout_s is None:
        timeout_s = _HISTORY_LOCK_WAIT_TIMEOUT_S
    if not (timeout_s >= 0):
        raise HistoryLockError(
            "history lock timeout must be a non-negative number of "
            "seconds, got %r" % (timeout_s,))
    lock_path = path + ".lock"
    try:
        lf = open(lock_path, "a+b")
    except FileNotFoundError:
        raise
    with lf:
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                fcntl.flock(lf.fileno(),
                            (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
                            | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                # Held by another process; retry until the deadline.
                pass
            except OSError as exc:
                raise HistoryLockError(
                    "cannot lock probe history %s: %s" % (lock_path, exc))
            if time.monotonic() >= deadline:
                raise HistoryLockError(
                    "probe history lock %s is still held after %.0f "
                    "seconds; the holder may be stopped (SIGSTOP) or "
                    "wedged on a stuck filesystem — find it (fuser/lsof "
                    "%s) and revive or kill it; do not delete %s "
                    "(deleting the path does not release the holder's "
                    "flock)" % (lock_path, timeout_s, lock_path,
                                lock_path))
            time.sleep(_HISTORY_LOCK_POLL_INTERVAL_S)
        try:
            yield
        finally:
            try:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def history_path():
    """Probe-history path: ``$RELAY_PROBE_HISTORY`` (tests/operator), else
    the control-plane default next to the session journal."""
    return os.environ.get("RELAY_PROBE_HISTORY") or os.path.join(
        os.path.dirname(relay_liveness.journal_path()),
        "relay-probe-history.jsonl",
    )


def _record_outcome(path, vm_id, outcome, detail, now=None):
    """Append one probe outcome to the history store. Fail-loud on I/O
    errors (a history the operator cannot read is a broken instrument);
    callers that must not raise (the cadence hot path) catch.

    #1537: the store is hardened at creation — the parent is created
    with mode 0o700 (the umask can only remove bits, never add them)
    and the file is opened with O_NOFOLLOW|O_CREAT|O_APPEND at 0o600,
    so a symlink at the history path fails loud (ELOOP) instead of
    redirecting appends into an arbitrary file. Creation-only: files
    and dirs that already existed with weaker permissions are NOT
    re-chmodded (we do not silently rewrite operator-owned
    permissions); the O_NOFOLLOW refusal applies at every open, not
    just creation. O_NOFOLLOW covers the final path component only —
    RELAY_PROBE_HISTORY must live under an operator-owned path
    (intermediate-component symlinks are still followed).
    #1540: writes serialize on the cross-process history lock, and
    rotation happens inside the same exclusive hold — two concurrent
    writers can no longer interleave records across a rotation
    boundary (the flapping-memory scan never mixes two drivers'
    histories) or race ``os.rename`` (the loser's FileNotFoundError
    is gone, because only one writer is ever inside the critical
    section). A wedged holder fails loud as HistoryLockError (an
    OSError) after _HISTORY_LOCK_WAIT_TIMEOUT_S — the cadence hot
    path already catches OSError.
    Divergence note (PR #1538 review): relay_liveness's session
    journal keeps plain O_CREAT|O_APPEND 0o600 without O_NOFOLLOW —
    that path is daemon-fixed (/var/lib/sparkvm/) and daemon-owned,
    while the history path is operator-configurable, so the symlink
    risk profiles genuinely differ. Revisit if the journal path ever
    becomes operator-configurable.
    """
    if now is None:
        now = time.time()
    record = {
        "ts": now,
        "vm_id": vm_id,
        "outcome": outcome,
        "elapsed_ms": detail.get("elapsed_ms"),
    }
    # D-RL2-3: the fingerprint never crosses a session boundary. The
    # store keeps the outcome and timing only.
    line = json.dumps(record, separators=(",", ":"))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, mode=0o700, exist_ok=True)
    with _history_locked(path, exclusive=True):
        _rotate_history_if_needed(path)
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _rotate_history_if_needed(path):
    # Must be called with the exclusive history lock held (#1540): two
    # concurrent rotators would race os.rename (the loser's
    # FileNotFoundError is unhandled) and interleave records across a
    # rotation boundary, mixing two drivers' histories in the
    # flapping-memory scan.
    # Rotation deliberately uses os.stat (symlink-following), not
    # os.lstat (PR #1538 review): if a symlink sits at the path and
    # its target is under the rotation threshold, the write path
    # ELOOP-fails loud anyway; if the target is over the threshold,
    # the rename moves the link itself to path.1 and the write
    # creates a fresh regular file at path — no append is ever
    # redirected into the symlink's target (verified empirically).
    # Failing rotation loud too would buy nothing over the write-side
    # refusal, and would break the deliberate read-path symlink
    # tolerance documented above.
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return
    if st.st_size < _HISTORY_MAX_BYTES:
        return
    oldest = "%s.%d" % (path, _HISTORY_MAX_ROTATED)
    try:
        os.unlink(oldest)
    except FileNotFoundError:
        pass
    for gen in range(_HISTORY_MAX_ROTATED - 1, 0, -1):
        try:
            os.rename("%s.%d" % (path, gen), "%s.%d" % (path, gen + 1))
        except FileNotFoundError:
            pass
    os.rename(path, "%s.1" % path)


def _iter_history(path, vm_id, limit, timeout_s=None):
    """Newest-first probe records for ``vm_id``. Corrupt lines are
    skipped (a wedged writer's garbage must not wedge the reader);
    unknown outcomes and records missing a numeric ``ts`` are skipped,
    never mapped. An unreadable store (missing file, directory as
    path, permissions) reads as no records — the history is advisory
    state; its absence degrades the reading (no flapping memory,
    "never probed"), never the reading itself. The write path
    (``_record_outcome``) stays fail-loud so a broken store is never
    silent.

    #1540: reads take the shared history lock so a read can never
    interleave with a rotation (which renames under the exclusive
    hold). A missing lock sidecar (never-written history) is NOT an
    error — it maps to no records, like a missing store. A wedged
    holder raises HistoryLockError instead: a broken instrument is
    loud, never advisory absence. ``timeout_s`` bounds the lock wait
    (default _HISTORY_LOCK_WAIT_TIMEOUT_S); public readers use the
    default.

    Reads follow symlinks deliberately (PR #1538 review): a
    symlinked history path is a sane operator setup, and exploiting
    it requires write access to the history parent — the same
    capability as forging records directly — so there is no attacker
    capability gain. Corrupt-line skipping bounds what a followed
    symlink can inject. Do not "fix" this to O_NOFOLLOW without
    revisiting the analysis.
    """
    try:
        with _history_locked(path, exclusive=False, timeout_s=timeout_s):
            try:
                fh = open(path, encoding="utf-8")
            except OSError:
                # A missing store (or an unreadable one at open time)
                # reads as no records — advisory absence, not a wedge.
                return
            with fh:
                # Mid-read I/O errors stay LOUD (pre-#1540 behavior):
                # a file that dies during the read is a broken
                # instrument, not an absent one. Only the open itself
                # is mapped to no-records.
                lines = fh.readlines()
    except HistoryLockError:
        raise
    except FileNotFoundError:
        # Never-written history (no store, no lock sidecar): an
        # absent instrument reads as no records — same as a missing
        # store at open time.
        return
    count = 0
    for line in reversed(lines):
        if count >= limit:
            break
        try:
            record = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(record, dict):
            continue
        if record.get("vm_id") != vm_id:
            continue
        outcome = record.get("outcome")
        if outcome not in relay_dial_prober.OUTCOMES:
            continue
        if not isinstance(record.get("ts"), (int, float)):
            continue
        count += 1
        yield record


def recent_liveness_outcomes(vm_id, n=2, path=None):
    """The last ``n`` liveness-bearing probe outcomes for ``vm_id``,
    newest first. Stand-down reports are skipped — they carry no
    liveness evidence and never count toward flapping.

    The scan is unbounded (whole file): a long stand-down run must
    never push the older liveness outcome out of the flapping window
    (Engineering B1 — a fixed window turned flapping into a rule-6
    ``down``). The history file is byte-bounded and already fully
    loaded, so this is O(file) with no new memory cost.
    """
    if path is None:
        path = history_path()
    outcomes = []
    for record in _iter_history(path, vm_id, limit=_HISTORY_SCAN_LIMIT):
        outcome = record["outcome"]
        if outcome in _LIVENESS_OUTCOMES:
            outcomes.append(outcome)
        if len(outcomes) >= n:
            break
    return outcomes


def latest_probe(vm_id, path=None):
    """The newest probe record for ``vm_id`` (any outcome), or None."""
    if path is None:
        path = history_path()
    for record in _iter_history(path, vm_id, limit=1):
        return record
    return None


# ---------------------------------------------------------------------------
# The §5 mapping
# ---------------------------------------------------------------------------


def map_reading(*, probe_outcome, journal_state):
    """Pin the §5 producer contract in code.

    ``probe_outcome`` is the latest liveness-bearing probe outcome (or
    ``"provider_not_running"``, or None when never probed);
    ``journal_state`` is the R1 passive reading — ``"active"``,
    ``"idle"``, ``"closed"``, or None (darkness).

    Returns ``(state, sub_code, reason)`` with ``state`` in
    ``ok | degraded | down`` and ``sub_code`` in
    ``relay | cert | box-leg`` (``down`` readings) or None.
    """
    if probe_outcome is None:
        return (
            STATE_DEGRADED,
            None,
            "no probe data — insufficient-observability, never assumed-ok",
        )
    if probe_outcome == relay_dial_prober.PROVIDER_NOT_RUNNING:
        return (
            STATE_DEGRADED,
            None,
            "provider stand-down — not a liveness question; "
            "provider state is the authority",
        )
    if probe_outcome in _DEFECT_SUBCODES:
        sub = _DEFECT_SUBCODES[probe_outcome]
        return (
            STATE_DOWN,
            sub,
            "prober defect %r — positive evidence of a broken path" % (sub,),
        )
    if probe_outcome == relay_dial_prober.PATH_OK:
        if journal_state == "active":
            return (
                STATE_OK,
                None,
                "prober path_ok with passive corroboration (journal active)",
            )
        return (
            STATE_DEGRADED,
            None,
            "prober path_ok but the passive journal has nothing fresh "
            "(journal %s) — no passive corroboration"
            % ("dark" if journal_state is None else journal_state),
        )
    # Unknown outcome strings cannot reach here (the history reader
    # filters to OUTCOMES), but a direct caller could pass one:
    # fail closed to degraded, never to ok or down.
    return (
        STATE_DEGRADED,
        None,
        "unrecognized probe outcome %r — fail-closed degraded" % (probe_outcome,),
    )


def relay_path_state(vm_id, *, now=None, history=None, journal_timeout_s=None):
    """``relay_path_state(vm_id)`` — the §5 producer reading.

    Composes the probe history (flapping check) with the passive
    journal. Returns a JSON-serializable dict::

        {"vm_id", "state", "sub_code", "reason", "probe", "journal"}

    where ``probe`` is the latest probe outcome (or None) and
    ``journal`` is the R1 journal state (``active`` | ``idle`` |
    ``closed``) or None (darkness). ``history`` overrides the history
    path (tests); ``journal_timeout_s`` bounds the journal-lock wait
    (a wedged lock raises ``JournalLockError`` — a broken instrument,
    never darkness; plane-facing callers pass a request-scoped budget).
    The probe-history read takes the shared history lock with the
    module-default bounded wait (#1540): a wedged history holder
    raises ``HistoryLockError`` here too — also a broken instrument,
    never advisory absence.

    Flapping (the last two liveness-bearing outcomes disagree) reads
    ``degraded`` before the §5 mapping runs.
    """
    if now is None:
        now = time.time()
    path = history if history is not None else history_path()

    probe_record = latest_probe(vm_id, path=path)
    probe_outcome = probe_record["outcome"] if probe_record else None

    journal_state = None
    journal = relay_liveness.relay_session_liveness(
        vm_id, now=now, timeout_s=journal_timeout_s
    )
    if journal is not None:
        journal_state = journal["state"]

    if probe_outcome in _LIVENESS_OUTCOMES:
        liveness = recent_liveness_outcomes(vm_id, n=2, path=path)
        if len(liveness) == 2 and liveness[0] != liveness[1]:
            state = STATE_DEGRADED
            sub_code = None
            reason = (
                "flapping — the prober disagrees with itself across "
                "consecutive probes (%r then %r); suspect, never down"
                % (liveness[1], liveness[0])
            )
            return {
                "vm_id": vm_id,
                "state": state,
                "sub_code": sub_code,
                "reason": reason,
                "probe": probe_outcome,
                "journal": journal_state,
            }

    state, sub_code, reason = map_reading(
        probe_outcome=probe_outcome, journal_state=journal_state
    )
    return {
        "vm_id": vm_id,
        "state": state,
        "sub_code": sub_code,
        "reason": reason,
        "probe": probe_outcome,
        "journal": journal_state,
    }


# ---------------------------------------------------------------------------
# Probe execution (cadence-driven)
# ---------------------------------------------------------------------------


def maybe_probe(
    vm_id,
    *,
    provider_state_fn,
    has_post_live_arc,
    bundle=None,
    now=None,
    cadence=None,
    history=None,
    journal_timeout_s=None,
):
    """Run one cadence-driven probe when due and return the reading.

    ``provider_state_fn`` returns the H4 provider state string;
    ``has_post_live_arc`` is the tenant layer's post-``live`` answer;
    ``bundle`` is ``{"relay_host", "relay_port", "pinned_fingerprint"}``
    or None — R2b never fetches bundles itself (interim honesty; the
    wiring is R3's). ``history`` overrides the history path.

    Returns ``{"probed": bool, "reason": str, "reading": dict|None}``.
    A provider_state_fn that raises propagates as a caller bug (the
    prober's contract). A history-write failure after a successful
    probe is caught, not raised — the cadence hot path must not raise
    (the failure is recorded in ``reason`` so the operator sees it);
    the outcome is recorded before the reading is composed so a later
    query sees this probe.
    """
    if now is None:
        now = time.time()
    if cadence is None:
        cadence = cadence_s()
    path = history if history is not None else history_path()

    probe_record = latest_probe(vm_id, path=path)
    last_probe_at = probe_record["ts"] if probe_record else None
    provider_state = provider_state_fn()
    should, why = cadence_decision(
        provider_state=provider_state,
        has_post_live_arc=has_post_live_arc,
        now=now,
        last_probe_at=last_probe_at,
        cadence=cadence,
    )
    if not should:
        return {
            "probed": False,
            "reason": why,
            "reading": relay_path_state(
                vm_id, now=now, history=path, journal_timeout_s=journal_timeout_s
            ),
        }
    if bundle is None:
        return {
            "probed": False,
            "reason": "due but no connection bundle supplied — "
            "R2b never fetches bundles (interim honesty)",
            "reading": relay_path_state(
                vm_id, now=now, history=path, journal_timeout_s=journal_timeout_s
            ),
        }
    result = relay_dial_prober.probe(
        vm_id,
        relay_host=bundle["relay_host"],
        relay_port=bundle["relay_port"],
        pinned_fingerprint=bundle["pinned_fingerprint"],
        provider_state_fn=provider_state_fn,
    )
    try:
        _record_outcome(path, vm_id, result.outcome, result.detail, now=now)
    except OSError as exc:
        # Security N2: ELOOP is an active-integrity signal (something
        # planted a symlink at the history path), distinct from ENOSPC —
        # say so so the operator can tell attack from disk-full.
        hint = (
            "; possible symlink planted at the history path (ELOOP)"
            if getattr(exc, "errno", None) == errno.ELOOP
            else ""
        )
        why = "%s; WARNING: probe history unwritable (%s)%s — this probe " \
            "will not inform flapping" % (why, exc, hint)
    return {
        "probed": True,
        "reason": why,
        "reading": relay_path_state(
            vm_id, now=now, history=path, journal_timeout_s=journal_timeout_s
        ),
    }


# ---------------------------------------------------------------------------
# Operator CLI — query surface
#
# Mirrors relay_liveness's CLI discipline: JSON out, loud errors, no
# tracebacks for operator-actionable failures. --probe-now takes the
# connection bundle from stdin as JSON (never from argv: #1536 — key
# material on the command line is visible in the process listing and
# persists in shell history — and never from a config file: D-RL2-3).

_BUNDLE_FIELDS = ("relay_host", "relay_port", "pinned_fingerprint")


class _BundleError(ValueError):
    """The stdin-supplied probe bundle is missing or malformed."""


def _read_bundle_stdin():
    """Read the probe bundle for --probe-now from stdin as JSON.

    Returns ``{"relay_host", "relay_port", "pinned_fingerprint"}``.
    Raises ``_BundleError`` with an operator-actionable message on
    empty stdin, invalid JSON, non-object JSON, or missing/empty
    required fields. The caller turns these into exit 2.

    Validation is deliberately strict (B1/B2/B3, PR #1538 review):
    ports are accepted only as ints or plain digit strings (no bool,
    float, or underscore coercion — a validator must not silently
    rewrite its input), and the string fields must actually be
    strings, so a malformed operator-supplied bundle can never
    escape into an uncaught traceback.
    """
    if sys.stdin.isatty():
        raise _BundleError(
            "--probe-now reads the probe bundle from stdin as JSON "
            "but stdin is a terminal — pipe the bundle, e.g. "
            "echo '{\"relay_host\": ..., \"relay_port\": ..., "
            "\"pinned_fingerprint\": ...}' | relay_path_state "
            "--query VM --probe-now"
        )
    raw = sys.stdin.read()
    if not raw.strip():
        raise _BundleError(
            "--probe-now needs the probe bundle on stdin as JSON "
            '({"relay_host", "relay_port", "pinned_fingerprint"}); '
            "got empty stdin"
        )
    try:
        bundle = json.loads(raw)
    except (ValueError, RecursionError):
        raise _BundleError("--probe-now bundle on stdin is not valid JSON")
    if not isinstance(bundle, dict):
        raise _BundleError("--probe-now bundle must be a JSON object")
    missing = [f for f in _BUNDLE_FIELDS if not bundle.get(f)]
    if missing:
        raise _BundleError(
            "--probe-now bundle missing required fields: %s" % ", ".join(missing)
        )
    for field in ("relay_host", "pinned_fingerprint"):
        if not isinstance(bundle[field], str):
            raise _BundleError(
                "--probe-now bundle %s must be a string" % field
            )
    raw_port = bundle["relay_port"]
    if isinstance(raw_port, bool):
        raise _BundleError("--probe-now bundle relay_port must be an integer")
    if isinstance(raw_port, int):
        port = raw_port
    elif isinstance(raw_port, str):
        text = raw_port.strip()
        sign, digits = (
            (text[0], text[1:]) if text[:1] in ("+", "-") else ("", text)
        )
        if not digits or not (digits.isascii() and digits.isdigit()):
            raise _BundleError("--probe-now bundle relay_port must be an integer")
        try:
            # Python 3.11+ int() refuses >4300-digit strings (ValueError):
            # keep it inside the validator so pathological input still
            # fails loud with exit 2 (PR #1538 review B4).
            port = int(sign + digits, 10)
        except ValueError:
            raise _BundleError("--probe-now bundle relay_port must be an integer")
    else:
        raise _BundleError("--probe-now bundle relay_port must be an integer")
    if not 0 < port < 65536:
        raise _BundleError("--probe-now bundle relay_port out of range")
    return {
        "relay_host": bundle["relay_host"],
        "relay_port": port,
        "pinned_fingerprint": bundle["pinned_fingerprint"],
    }

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="relay path-state producer (R2b, #1415): "
        "ok | degraded | down + sub-code per vm_id"
    )
    ap.add_argument("--history", default=None, help="probe-history path override")
    ap.add_argument("--journal", default=None, help="session-journal path override")
    ap.add_argument("--query", metavar="VM_ID", help="print relay_path_state as JSON")
    ap.add_argument(
        "--probe-now",
        action="store_true",
        help="run one probe now (reads the probe bundle "
        '{"relay_host", "relay_port", "pinned_fingerprint"} from stdin '
        "as JSON; provider state defaults to running)",
    )
    ap.add_argument(
        "--provider-state",
        default="running",
        help="H4 provider state string (default: running)",
    )
    args = ap.parse_args()
    if args.history:
        os.environ["RELAY_PROBE_HISTORY"] = args.history
    if args.journal:
        os.environ["RELAY_SESSION_JOURNAL"] = args.journal
    if args.probe_now:
        if not args.query:
            print(
                "error: --probe-now needs --query VM_ID and the probe "
                "bundle on stdin as JSON",
                file=sys.stderr,
            )
            raise SystemExit(2)
        try:
            bundle = _read_bundle_stdin()
        except _BundleError as exc:
            print("error: %s" % exc, file=sys.stderr)
            raise SystemExit(2)
        out = maybe_probe(
            args.query,
            provider_state_fn=lambda: args.provider_state,
            has_post_live_arc=True,
            bundle=bundle,
        )
        print(json.dumps(out, indent=2))
    elif args.query:
        try:
            reading = relay_path_state(args.query)
        except (relay_liveness.JournalLockError, HistoryLockError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            raise SystemExit(1)
        print(json.dumps(reading, indent=2))
    else:
        ap.print_help()
