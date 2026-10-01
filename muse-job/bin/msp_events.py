#!/usr/bin/env python3
"""msp_events.py -- MSP view-plane client: event stream -> job state (#224).

The fourth slice of the #228 muse-job v2 migration (drive jobs over MSP
instead of scraping a tmux TUI). On top of bin/msp_host.py's transport
(#221) this module replaces the pane-scraping liveness layer built for
#211 with the MSP event stream:

- ``view/subscribe`` at an explicit cursor: replays ``(after, head]``
  before any live event, so a poll never misses a turn boundary.
- Notification -> job-signal classification (``classify_notification``):
  ``item/started|delta|updated`` -> working; ``turn/completed`` ->
  turn terminal; ``approval/requested`` -> blocked on approval;
  ``session/statusChanged`` -> authoritative status/attention flip;
  ``session/tokenUsage|contextUsage|modelChanged`` -> telemetry;
  ``session/closed`` -> closed.
- Job-state derivation (``JobView``): working / blocked_approval /
  blocked_input / stalled / idle / turn_failed / turn_cancelled /
  session_closed. "No events + no active turn for N minutes -> stalled"
  per #224; the stream-idle-timeout recovery policy itself is #226.
- Cursor persistence per job dir (``load_cursor``/``save_cursor``) so
  successive polls form one gapless sequence.

What this module deliberately does NOT do
----------------------------------------
- Server->client *requests* (``userInput/request``, ``approval/request``)
  arrive via ``MSPHost.set_request_handler``, not the notification
  stream; answering them is #225 (``msp_approval.py``). The notification
  side still sees them corroborated as ``session/statusChanged`` with
  ``attention=["inputPending"|"approvalPending"]``.
- Turn steering (``turn/start|steer|interrupt|cancel``) is #223
  (``msp_turn.py``); session lifecycle is #222 (``msp_session.py``).
- Dead-model recovery (detect + recover a stream-idle-timeout death) is
  #226; this module only *detects* the stalled shape.

Wire-shape provenance
---------------------
Notification/param shapes come from the exported MSP JSON schema
(``muse schema generate-json-schema``, muse 1.4.2, 2026-10-01):
``Session.status`` in {notLoaded, idle, running}, ``attention`` flags in
{approvalPending, inputPending}, ``turn/completed.terminal`` in
{completed, failed, cancelled}, every view notification carrying a
strictly monotonic ``viewCursor`` in params. Classification keys only on
the documented fields above and fails soft (``unknown`` signal) on
anything else -- a new notification method must never break polling.

Security and trust
------------------
Same posture as msp_host.py: notification payloads (item text, prompts,
approval details) may contain real secret values. They are NEVER logged,
NEVER printed by the library functions, and NEVER persisted except the
opaque ``viewCursor`` string (which carries no content). The smoke CLI
below prints only signal kinds, state names, and redacted summaries --
never raw params.
"""

import argparse
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msp_host import MSPError  # noqa: E402  (sibling module)


class MSPEventsError(MSPError):
    """The view-plane call failed or its result drifted off the wire shape."""


# -- signal kinds (classify_notification output) --------------------------
# Working: the model is producing.
SIG_WORKING = "working"
# A view item reached its terminal state (not necessarily the turn).
SIG_ITEM_DONE = "item_done"
# Turn terminal signals (from turn/completed).
SIG_TURN_DONE = "turn_done"
SIG_TURN_FAILED = "turn_failed"
SIG_TURN_CANCELLED = "turn_cancelled"
# A retry was scheduled for a failed turn (still in play).
SIG_TURN_RETRY = "turn_retry"
# A turn was retracted (pulled back by the runtime).
SIG_TURN_RETRACTED = "turn_retracted"
# Blocked: the session needs the operator.
SIG_BLOCKED_APPROVAL = "blocked_approval"
SIG_BLOCKED_INPUT = "blocked_input"
# Approval lifecycle (informational; blocked state comes from the flags).
SIG_APPROVAL_UPDATE = "approval_update"
# Authoritative status/attention flip.
SIG_STATUS = "status"
# Telemetry: token usage, context usage, model changes.
SIG_TELEMETRY = "telemetry"
# A user-input prompt settled (answered/cancelled/expired).
SIG_INPUT_SETTLED = "input_settled"
# The server dropped events: (after, next] was not delivered.
SIG_GAP = "gap"
# Session lifecycle.
SIG_SESSION_CLOSED = "session_closed"
SIG_INFO = "info"
# Anything we do not recognize: never fatal to polling.
SIG_UNKNOWN = "unknown"

# -- derived job states (JobView.state) -----------------------------------
STATE_WORKING = "working"
STATE_BLOCKED_APPROVAL = "blocked_approval"
STATE_BLOCKED_INPUT = "blocked_input"
STATE_STALLED = "stalled"
STATE_IDLE = "idle"
STATE_TURN_FAILED = "turn_failed"
STATE_TURN_CANCELLED = "turn_cancelled"
STATE_SESSION_CLOSED = "session_closed"
STATE_UNKNOWN = "unknown"

# Notification methods that mean the model is producing output.
_WORKING_METHODS = frozenset(
    {
        "item/started",
        "item/delta",
        "item/updated",
        "turn/started",
        "turn/unqueued",
        "turn/retracted",
    }
)
# Pure telemetry methods: recorded, never state-changing.
_TELEMETRY_METHODS = frozenset(
    {"session/tokenUsage", "session/contextUsage", "session/modelChanged"}
)
# Session attention flags (wire enum, schema-verified).
_ATTENTION_APPROVAL = "approvalPending"
_ATTENTION_INPUT = "inputPending"

CURSOR_FILENAME = "msp_view_cursor"
# Event families the view plane cares about. MSPHost.subscribe takes one
# prefix per registration (no wildcard), so a poll registers each family;
# an unknown future family is simply not replayed (fail-soft: the
# session/read seed still seeds status/activeTurnId).
_SUBSCRIBE_PREFIXES = (
    "item", "turn", "session", "approval", "userInput", "view",
    "usage", "skill",
)


def _subscribe_all(host, callback):
    """Subscribe to every view event family; return an unsubscribe-all."""
    unsubs = [host.subscribe(prefix, callback)
              for prefix in _SUBSCRIBE_PREFIXES]

    def unsubscribe_all():
        for unsub in unsubs:
            unsub()

    return unsubscribe_all
# How long a cursor file may be trusted after a failed save/read: not
# applicable -- cursor IO is best-effort; a missing cursor just replays
# from "now" (view/subscribe without `after`).


class JobSignal:
    """One classified view notification."""

    __slots__ = ("kind", "method", "view_cursor", "received_at", "detail",
                 "turn_id")

    def __init__(self, kind, method, view_cursor=None, detail=None,
                 turn_id=None):
        self.kind = kind
        self.method = method
        self.view_cursor = view_cursor
        # time.time() at classification; drives stalled detection.
        self.received_at = time.time()
        # Short human-readable note (redacted); never raw params.
        self.detail = detail
        # The turn this signal belongs to (turn/* methods), if known.
        self.turn_id = turn_id

    def __repr__(self):
        return (
            f"JobSignal(kind={self.kind!r}, method={self.method!r}, "
            f"detail={self.detail!r})"
        )


def _redacted_summary(params, max_len=200):
    """Build a short human-readable summary without secret content.

    Only structural facts (ids, enums, counts) go in; free-text fields
    (prompts, item text, approval detail) are summarized by kind, never
    quoted, because they may carry secrets.
    """
    if not isinstance(params, dict):
        return None
    bits = []
    for key in ("turnId", "sessionId", "terminal", "status"):
        val = params.get(key)
        if isinstance(val, (str, int)):
            bits.append(f"{key}={val}")
    attention = params.get("attention")
    if isinstance(attention, list) and attention:
        bits.append("attention=" + ",".join(str(a) for a in attention))
    item = params.get("item")
    if isinstance(item, dict):
        kind = item.get("kind") or item.get("type")
        if kind:
            bits.append(f"item={kind}")
    text = " ".join(bits)
    return text[:max_len] if text else None


def classify_notification(msg):
    """Classify one server->client view notification into a JobSignal.

    ``msg`` is the full JSON-RPC notification dict as delivered to
    ``MSPHost.subscribe`` callbacks (``{"jsonrpc","method","params"}``).
    Pure function: no IO, never raises on malformed input (returns
    SIG_UNKNOWN).
    """
    try:
        method = msg.get("method")
        params = msg.get("params") or {}
    except AttributeError:
        return JobSignal(SIG_UNKNOWN, None, detail="non-dict message")
    if not isinstance(method, str):
        return JobSignal(SIG_UNKNOWN, method, detail="missing method")
    if not isinstance(params, dict):
        params = {}
    cursor = params.get("viewCursor")
    if not isinstance(cursor, str):
        cursor = None
    detail = _redacted_summary(params)
    turn_id = params.get("turnId")
    if not isinstance(turn_id, str):
        turn_id = None

    if method in _WORKING_METHODS:
        return JobSignal(SIG_WORKING, method, cursor, detail,
                         turn_id=turn_id)
    if method == "item/completed":
        return JobSignal(SIG_ITEM_DONE, method, cursor, detail,
                         turn_id=turn_id)
    if method == "turn/completed":
        terminal = params.get("terminal")
        if terminal == "failed":
            return JobSignal(SIG_TURN_FAILED, method, cursor, detail,
                             turn_id=turn_id)
        if terminal == "cancelled":
            return JobSignal(SIG_TURN_CANCELLED, method, cursor, detail,
                             turn_id=turn_id)
        return JobSignal(SIG_TURN_DONE, method, cursor, detail,
                         turn_id=turn_id)
    if method == "turn/retryScheduled":
        return JobSignal(SIG_TURN_RETRY, method, cursor, detail,
                         turn_id=turn_id)
    if method in ("approval/requested",):
        return JobSignal(SIG_BLOCKED_APPROVAL, method, cursor, detail)
    if method in ("approval/resolved", "approval/updated"):
        return JobSignal(SIG_APPROVAL_UPDATE, method, cursor, detail)
    if method == "userInput/requested":
        return JobSignal(SIG_BLOCKED_INPUT, method, cursor, detail,
                         turn_id=turn_id)
    if method == "userInput/settled":
        return JobSignal(SIG_INPUT_SETTLED, method, cursor, detail)
    if method == "view/gap":
        return JobSignal(SIG_GAP, method, cursor, detail)
    if method == "session/statusChanged":
        attention = params.get("attention") or []
        if _ATTENTION_APPROVAL in attention:
            return JobSignal(SIG_BLOCKED_APPROVAL, method, cursor, detail)
        if _ATTENTION_INPUT in attention:
            return JobSignal(SIG_BLOCKED_INPUT, method, cursor, detail)
        return JobSignal(SIG_STATUS, method, cursor, detail)
    if method in _TELEMETRY_METHODS:
        return JobSignal(SIG_TELEMETRY, method, cursor, detail)
    if method == "session/closed":
        return JobSignal(SIG_SESSION_CLOSED, method, cursor, detail)
    return JobSignal(SIG_UNKNOWN, method, cursor, detail)

class JobView:
    """The derived view of one session: state + supporting facts.

    Folded from a ``session/read`` seed plus a classified notification
    sequence. ``state`` is one of the STATE_* constants. ``pending_summary``
    carries the redacted question/approval text when blocked; ``telemetry``
    accumulates per-method raw payloads (fail-soft: recorded, never
    state-changing, never logged).
    """

    def __init__(self, session_id):
        self.session_id = session_id
        self.state = STATE_UNKNOWN
        self.active_turn_id = None
        self.session_status = None  # notLoaded | idle | running
        self.attention = []
        self.last_event_at = None
        self.last_cursor = None
        self.pending_summary = None
        self.last_terminal = None  # completed | failed | cancelled
        self.last_turn_id = None
        self.telemetry = {}
        self.signals_seen = 0
        # True when a view/gap notification arrived: (after, next] was
        # dropped by push delivery and the folded transitions may be
        # incomplete. poll_session_view re-seeds from session/read when
        # this is set.
        self.had_gap = False

    # -- folding --------------------------------------------------------

    def seed_from_session(self, session):
        """Seed from a ``session/read`` (or start/resume) Session record.

        Defensive: every field is optional; a missing field leaves the
        current value in place. ``lastActivityAt`` seeds the quiet clock
        so the stalled rule works even when the replay is empty.
        """
        if not isinstance(session, dict):
            return
        status = session.get("status")
        if status in ("notLoaded", "idle", "running"):
            self.session_status = status
        active = session.get("activeTurnId")
        # activeTurnId is null when no turn runs; only adopt real ids.
        if isinstance(active, str) and active:
            self.active_turn_id = active
        elif active is None:
            self.active_turn_id = None
        attention = session.get("attention")
        if isinstance(attention, list):
            self.attention = [str(a) for a in attention]
        last_activity = session.get("lastActivityAt")
        if isinstance(last_activity, str):
            parsed = _parse_rfc3339(last_activity)
            if parsed is not None:
                # Seed the quiet clock; fresher replay events overwrite.
                if self.last_event_at is None or parsed > self.last_event_at:
                    self.last_event_at = parsed
        # A fresh seed with no signals yet: the server's status is the
        # honest default (fold() refines it as events arrive).
        if self.state == STATE_UNKNOWN:
            if self.session_status == "running":
                self.state = STATE_WORKING
            elif self.session_status == "idle":
                self.state = STATE_IDLE

    def fold(self, signal):
        """Fold one classified JobSignal into the view."""
        self.signals_seen += 1
        if signal.view_cursor:
            self.last_cursor = signal.view_cursor

        kind = signal.kind
        # Any recognized event proves the session is alive -- including
        # telemetry (a tokenUsage event means the model is producing).
        # Only SIG_UNKNOWN (shape drift / future methods) is excluded:
        # it must never reset the quiet clock, or a chatty unknown
        # method would mask a real stall.
        if kind != SIG_UNKNOWN:
            self.last_event_at = signal.received_at

        if kind == SIG_WORKING:
            self.state = STATE_WORKING
            self.pending_summary = None
            if signal.turn_id:
                self.active_turn_id = signal.turn_id
                self.last_turn_id = signal.turn_id
        elif kind == SIG_BLOCKED_APPROVAL:
            self.state = STATE_BLOCKED_APPROVAL
            self.attention = [_ATTENTION_APPROVAL]
            if signal.detail:
                self.pending_summary = signal.detail
        elif kind == SIG_BLOCKED_INPUT:
            self.state = STATE_BLOCKED_INPUT
            self.attention = [_ATTENTION_INPUT]
            if signal.detail:
                self.pending_summary = signal.detail
        elif kind == SIG_APPROVAL_UPDATE:
            # Resolved/updated: drop the approval flag; the next
            # statusChanged (or continued item events) sets the state.
            self.attention = [
                a for a in self.attention if a != _ATTENTION_APPROVAL
            ]
            if self.state == STATE_BLOCKED_APPROVAL:
                self.state = STATE_WORKING
        elif kind == SIG_INPUT_SETTLED:
            # Answered/cancelled/expired: drop the input flag the same way.
            self.attention = [
                a for a in self.attention if a != _ATTENTION_INPUT
            ]
            if self.state == STATE_BLOCKED_INPUT:
                self.state = STATE_WORKING
        elif kind == SIG_GAP:
            self.had_gap = True
        elif kind == SIG_TURN_DONE:
            self.last_terminal = "completed"
            if signal.turn_id:
                self.last_turn_id = signal.turn_id
            if not signal.turn_id or signal.turn_id == self.active_turn_id:
                self.active_turn_id = None
            self.state = STATE_IDLE
        elif kind == SIG_TURN_FAILED:
            self.last_terminal = "failed"
            if signal.turn_id:
                self.last_turn_id = signal.turn_id
            if not signal.turn_id or signal.turn_id == self.active_turn_id:
                self.active_turn_id = None
            self.state = STATE_TURN_FAILED
        elif kind == SIG_TURN_CANCELLED:
            self.last_terminal = "cancelled"
            if signal.turn_id:
                self.last_turn_id = signal.turn_id
            if not signal.turn_id or signal.turn_id == self.active_turn_id:
                self.active_turn_id = None
            self.state = STATE_TURN_CANCELLED
        elif kind == SIG_TURN_RETRY:
            self.state = STATE_WORKING
        elif kind == SIG_STATUS:
            # session/statusChanged params are re-read by the poller via
            # fold_status(); here we only note that a flip happened.
            pass
        elif kind == SIG_TELEMETRY:
            self.telemetry[signal.method] = True
        elif kind == SIG_SESSION_CLOSED:
            self.state = STATE_SESSION_CLOSED
            self.active_turn_id = None
        # SIG_ITEM_DONE / SIG_INFO / SIG_UNKNOWN: no state change.

    def fold_status(self, status, attention):
        """Fold an authoritative (status, attention) pair.

        From ``session/statusChanged`` params or a fresh ``session/read``.
        Attention flags take precedence over everything: a session the
        server flags approvalPending/inputPending is blocked even if item
        events are still arriving.
        """
        if status in ("notLoaded", "idle", "running"):
            self.session_status = status
        if isinstance(attention, list):
            self.attention = [str(a) for a in attention]
        if _ATTENTION_APPROVAL in self.attention:
            self.state = STATE_BLOCKED_APPROVAL
        elif _ATTENTION_INPUT in self.attention:
            self.state = STATE_BLOCKED_INPUT
        elif self.session_status == "running":
            if self.state not in (STATE_WORKING,):
                # A running session with no recent working signal is at
                # least not provably blocked; stalled is derived below.
                self.state = STATE_WORKING
        elif self.session_status == "idle" and self.state in (
            STATE_UNKNOWN,
            STATE_WORKING,
        ):
            self.state = STATE_IDLE

    def derive(self, now=None, stale_after=900.0):
        """Apply the stalled rule and return the final state string.

        Stalled per #224: the session reports ``running`` but nothing has
        happened for ``stale_after`` seconds -- the silent-stream shape
        and the recap-parked shape (status running, activeTurnId null,
        which #226 recovers) both land here. Never overrides an explicit
        blocked/terminal state -- a session waiting on the operator is
        blocked, not stalled. Without any recency baseline stalled is
        not claimed.
        """
        if now is None:
            now = time.time()
        if self.state in (
            STATE_BLOCKED_APPROVAL,
            STATE_BLOCKED_INPUT,
            STATE_SESSION_CLOSED,
            STATE_TURN_FAILED,
            STATE_TURN_CANCELLED,
        ):
            return self.state
        last = self.last_event_at
        if last is None:
            # No recency baseline (no events, no lastActivityAt, no prior
            # cursor): stalled cannot be proven, so it is not claimed.
            return self.state
        quiet_for = now - last
        # Running with no events for longer than the threshold is stalled.
        # This covers both the silent-stream shape and the recap-parked
        # shape (status running, activeTurnId null -- #226 recovers it).
        if self.session_status == "running" and quiet_for > stale_after:
            return STATE_STALLED
        return self.state

    def summary(self):
        """One-line redacted summary for status output."""
        parts = [f"state={self.state}"]
        if self.active_turn_id:
            parts.append(f"turn={self.active_turn_id[:8]}…")
        if self.last_terminal:
            parts.append(f"last_terminal={self.last_terminal}")
        if self.pending_summary:
            parts.append(f"pending={self.pending_summary[:80]}")
        if self.last_cursor:
            parts.append(f"cursor={self.last_cursor[:16]}…")
        return " ".join(parts)


def _parse_rfc3339(value):
    """Parse an RFC3339 timestamp to epoch seconds; None on failure."""
    try:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        from datetime import datetime

        return datetime.fromisoformat(text).timestamp()
    except (ValueError, OverflowError):
        return None


# -- cursor persistence ----------------------------------------------------

def _cursor_path(job_dir):
    return os.path.join(job_dir, CURSOR_FILENAME)


def _load_cursor_record(job_dir):
    """Return (cursor, at) from the cursor file.

    The file holds JSON ``{"cursor": ..., "at": <epoch>}``; a bare
    cursor string (the pre-#224 format) is accepted with ``at=None``.
    """
    try:
        with open(_cursor_path(job_dir), "r", encoding="utf-8") as fh:
            raw = fh.read().strip()
    except OSError:
        return None, None
    if not raw:
        return None, None
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
        except ValueError:
            return None, None
        cursor = obj.get("cursor")
        at = obj.get("at")
        if not isinstance(cursor, str) or not cursor:
            return None, None
        if not isinstance(at, (int, float)):
            at = None
        return cursor, at
    return raw, None


def load_cursor(job_dir):
    """Return the persisted view cursor, or None (subscribe from now)."""
    cursor, _at = _load_cursor_record(job_dir)
    return cursor


def save_cursor(job_dir, cursor, at=None):
    """Persist the view cursor (and its observation time) atomically."""
    if not cursor or not isinstance(cursor, str):
        return
    if at is None:
        at = time.time()
    path = _cursor_path(job_dir)
    tmp = path + ".tmp"
    payload = json.dumps({"cursor": cursor, "at": at})
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# -- polling ---------------------------------------------------------------

def _check_session_id(session_id):
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("session_id must be a non-empty string")


def poll_session_view(
    host,
    session_id,
    job_dir,
    *,
    replay_wait=2.0,
    stale_after=900.0,
    now=None,
    sink=None,
):
    """One poll: seed from session/read, replay (after, head], derive state.

    - Loads the persisted cursor and subscribes with ``after`` when one
      exists (gapless replay); without a cursor subscribes from now.
    - Collects replayed notifications for ``replay_wait`` seconds on the
      calling thread (the subscriber callback only appends to a list --
      it never calls back into the host, so no reader-thread deadlock).
    - Folds the ``session/read`` seed first, then the replay in arrival
      order, persists the newest cursor, and returns the JobView.

    ``sink`` (optional) is called with each classified JobSignal in
    arrival order -- the CLI uses it to journal the redacted signal
    stream for `muse-job log`.

    Raises MSPEventsError on transport/wire failures; a session the
    server does not know surfaces as STATE_UNKNOWN (fail-soft: polling a
    dead session id must not crash the watchdog).
    """
    _check_session_id(session_id)
    view = JobView(session_id)

    # The persisted cursor time is a recency baseline: it marks when we
    # last observed the head. seed_from_session() keeps the fresher of
    # this and the server's lastActivityAt.
    persisted_cursor, persisted_at = _load_cursor_record(job_dir)
    if persisted_at is not None:
        view.last_event_at = persisted_at

    # Seed: session/read is attach-free (no lease, no load, no resume
    # record) -- the cheap way to learn status/activeTurnId/attention.
    try:
        result = host.call("session/read", {"sessionId": session_id})
    except MSPError as e:
        raise MSPEventsError(f"session/read failed: {e}") from e
    if isinstance(result, dict):
        view.seed_from_session(result.get("session", result))

    collected = []
    lock = threading.Lock()

    def on_note(msg):
        # Runs on the reader thread: append only, never touch the host.
        with lock:
            collected.append(msg)

    unsub = _subscribe_all(host, on_note)
    try:
        params = {"sessionId": session_id}
        if persisted_cursor:
            params["after"] = persisted_cursor
        try:
            sub_result = host.call("view/subscribe", params)
        except MSPError as e:
            raise MSPEventsError(f"view/subscribe failed: {e}") from e
        head = None
        if isinstance(sub_result, dict):
            head = sub_result.get("viewCursor")
        # The replay arrives as ordinary notifications on this
        # connection; wait for the server to flush (after, head].
        deadline = time.time() + max(0.0, replay_wait)
        while time.time() < deadline:
            time.sleep(0.05)
    finally:
        unsub()

    with lock:
        notes = list(collected)
    for msg in notes:
        signal = classify_notification(msg)
        if sink is not None:
            # Issue #227: the muse-job CLI journals every replayed signal
            # (redacted JobSignal) for `muse-job log`. The sink runs on the
            # calling thread after unsubscribe; it must not raise.
            try:
                sink(signal)
            except Exception:
                pass
        if signal.kind == SIG_STATUS:
            params = msg.get("params") or {}
            view.fold_status(params.get("status"), params.get("attention"))
        view.fold(signal)

    if view.had_gap:
        # Push delivery dropped (after, next]: the folded transitions may
        # be incomplete (a turn/completed could have been lost). Re-seed
        # from session/read -- the Session record is the authoritative
        # current truth for status/activeTurnId/attention.
        try:
            result = host.call("session/read", {"sessionId": session_id})
        except MSPError:
            pass
        else:
            if isinstance(result, dict):
                view.seed_from_session(result.get("session", result))
        view.had_gap = False  # re-seed absorbed the gap

    # Newest cursor wins: prefer the subscribe head (authoritative), fall
    # back to the max cursor seen on notifications.
    new_cursor = head or view.last_cursor
    if new_cursor:
        try:
            save_cursor(job_dir, new_cursor)
        except MSPError:
            pass
        view.last_cursor = new_cursor

    view.state = view.derive(now=now, stale_after=stale_after)
    return view


def tail_session_view(
    host,
    session_id,
    job_dir,
    duration,
    *,
    stale_after=900.0,
    poll_interval=1.0,
):
    """Yield (JobSignal, JobView) live for ``duration`` seconds.

    Used by ``muse-job watch``: subscribes from the persisted cursor,
    classifies each arriving notification, folds it into a running
    JobView, and yields the pair. The cursor is persisted as it advances.
    """
    _check_session_id(session_id)
    view = JobView(session_id)
    try:
        result = host.call("session/read", {"sessionId": session_id})
    except MSPError as e:
        raise MSPEventsError(f"session/read failed: {e}") from e
    if isinstance(result, dict):
        view.seed_from_session(result.get("session", result))

    queue = []
    lock = threading.Lock()

    def on_note(msg):
        with lock:
            queue.append(msg)

    unsub = _subscribe_all(host, on_note)
    try:
        params = {"sessionId": session_id}
        cursor = load_cursor(job_dir)
        if cursor:
            params["after"] = cursor
        try:
            host.call("view/subscribe", params)
        except MSPError as e:
            raise MSPEventsError(f"view/subscribe failed: {e}") from e
        end = time.time() + max(0.0, duration)
        while time.time() < end:
            time.sleep(poll_interval)
            with lock:
                batch, queue[:] = queue[:], []
            for msg in batch:
                signal = classify_notification(msg)
                if signal.kind == SIG_STATUS:
                    p = msg.get("params") or {}
                    view.fold_status(p.get("status"), p.get("attention"))
                view.fold(signal)
                if signal.view_cursor:
                    save_cursor(job_dir, signal.view_cursor)
                view.state = view.derive(stale_after=stale_after)
                yield signal, view
    finally:
        unsub()

# -- smoke CLI ---------------------------------------------------------------

def _open_host(args):
    # Local import: the smoke CLI is the only path that needs MSPHost at
    # import time; the library surface above stays light.
    from msp_host import MSPHost  # noqa: E402

    host = MSPHost(
        [args.muse_bin, "serve"],
        client_name="msp_events_smoke",
        log_path=args.serve_log,
    )
    host.open()
    return host


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="msp_events smoke CLI (issue #224): poll/tail a "
        "session's view and derive its job state. Prints signal kinds, "
        "state names, and redacted summaries only -- never raw params."
    )
    ap.add_argument("--muse-bin", default="muse",
                    help="muse binary to serve from")
    ap.add_argument("--serve-log", default=None,
                    help="serve stderr log path (0o600)")
    ap.add_argument("--job-dir", default=".",
                    help="job dir holding the view cursor")
    ap.add_argument("--stale-after", type=float, default=900.0,
                    help="seconds of event quiet before stalled")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("poll", help="one poll: seed + replay + state")
    p.add_argument("session_id")
    p.add_argument("--replay-wait", type=float, default=2.0)

    t = sub.add_parser("tail", help="live-tail signals for N seconds")
    t.add_argument("session_id")
    t.add_argument("--duration", type=float, default=30.0)

    c = sub.add_parser("classify",
                       help="classify one notification JSON from stdin")
    args = ap.parse_args(argv)

    if args.cmd == "classify":
        msg = json.load(sys.stdin)
        signal = classify_notification(msg)
        print(f"kind={signal.kind} method={signal.method} "
              f"detail={signal.detail}")
        return 0

    host = _open_host(args)
    try:
        if args.cmd == "poll":
            view = poll_session_view(
                host, args.session_id, args.job_dir,
                replay_wait=args.replay_wait,
                stale_after=args.stale_after,
            )
            print(f"session={view.session_id}")
            print(f"state={view.state}")
            print(f"signals_seen={view.signals_seen}")
            print(f"summary: {view.summary()}")
        elif args.cmd == "tail":
            for signal, view in tail_session_view(
                host, args.session_id, args.job_dir,
                args.duration, stale_after=args.stale_after,
            ):
                print(f"[{signal.kind}] {view.state} :: "
                      f"{signal.detail or signal.method}")
    finally:
        host.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
