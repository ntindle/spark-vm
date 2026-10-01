#!/usr/bin/env python3
"""msp_view.py -- MSP view-plane client for muse-job v2 (#224).

Liveness and job state from the session event stream, on top of
bin/msp_host.py's transport (issue #221), the fourth slice of the #228
muse-job v2 migration (drive jobs over MSP instead of scraping a tmux
TUI):

- ``view/subscribe``  -- subscribe to a session's view at a cursor:
  replay the events in ``(after, head]``, then live notifications.

- Notification -> job-state mapping (the #224 contract):
  ``item/started|delta|completed`` -> working;
  ``userInput/request``, ``approval/requested`` -> blocked, with the
  actual question surfaced;
  ``session/modelChanged``, ``session/contextUsage`` -> telemetry;
  no events + no active turn for N minutes -> stalled.

``muse-job status`` reads this state and ``muse-job watch`` tails the
stream -- that rewire is the #227 cutover slice; this module is the
view-plane primitive it builds on. The TUI probe layer built for #211
(foreground-process detection, resume-banner matching, viewport-tail
prompt matching) is NOT retired here: #222's cutover decision is
serve-hosted only, but retiring the probes before the #227 rewire would
break ``muse-job status``/``watch`` today. Retirement belongs to #227.

Wire-shape provenance
---------------------
The method names (``view/subscribe``, ``item/started|delta|completed``,
``userInput/request``, ``approval/requested``,
``session/modelChanged``, ``session/contextUsage``) come from the #224
issue. EVERYTHING else on the view plane -- the subscribe params
(``sessionId``, ``after``), the result shape (``head`` cursor,
``events`` replay list), the notification payload fields (``itemId``,
``turnId``, ``question``, ``description``), the blocked-clear rule, the
10-minute stall default, the turn-event interplay -- is
fixture-invented, NOT verified against the deployment binary this turn
(there is no view-plane transcript corpus yet, and no ``muse`` binary
on this box). The module validates what it sends, parses results
defensively, and fails loud (MSPViewError) on shape drift instead of
guessing. MSPHost's schema-fingerprint pin
(``verify_schema_on_open``) is the drift tripwire -- pass
``expected_schema_fingerprint`` from the deployment binary when
opening the host. The live acceptance ("status transitions observed on
a real job without any tmux interaction") stays open for a future live
turn; the dead-model path belongs to #226.

Fixture provenance (what the hermetic test fixture invents)
----------------------------------------------------------
The fake ``muse serve`` in ``muse-job/tests/test_msp_view.py`` stands
in for wire shapes that do not exist in any transcript yet. Its
invented details:
- ``view/subscribe`` answers ``{"head": <cursor>, "events": [...]}``
  where cursors are ``"c0"``, ``"c1"``, ... and the replay is the
  events strictly after the ``after`` cursor;
- an unknown session id answers an empty replay with head ``"c0"``
  (the client treats an empty stream as idle, never as an error);
- live events arrive on the plain method names (``item/started`` etc.,
  as #223's fixture did for turn events);
- a test-only ``view/__emit`` method injects a notification into the
  stream (never on the real wire);
- item payloads carry ``{"itemId", "sessionId", "turnId"}``;
  ``userInput/request`` carries ``{"question", "sessionId"}``;
  ``approval/requested`` carries ``{"description", "sessionId"}``;
  telemetry payloads carry ``{"sessionId", ...}``;
  turn events carry ``{"turnId", "sessionId"}``.
The client only asserts the parts it documents (the replay window, the
state mapping, the question surfacing), so the invented details can be
wrong without the client misbehaving.

Security and trust
------------------
Same posture as msp_host.py, which this module does not weaken:
notification payloads -- including the surfaced blocked question and
any transcript-adjacent text -- may contain real secret values.
Results are NEVER redacted, never logged, never printed by the library
functions. The smoke CLI below prints the blocked question to stdout --
do not paste that output where agents can read it.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msp_host import MSPError, MSPHost  # noqa: E402  (sibling module)

# Job states derived from the view stream (#224's vocabulary, plus an
# explicit neutral state the issue leaves unnamed).
STATE_WORKING = "working"
STATE_BLOCKED = "blocked"
STATE_IDLE = "idle"
STATE_STALLED = "stalled"

# "no events + no active turn for N minutes -> stalled". N is
# fixture-invented (the issue names no value); ten minutes is long
# enough that a quiet-but-live turn (no item deltas while the model
# thinks) does not false-stall, short enough that a dead job is noticed
# within one watch cycle.
STALL_AFTER_SECONDS = 10 * 60.0

# Telemetry ring bound: a long session emits many contextUsage events;
# keep the recent slice, not the whole history (same 100-entry bound as
# MSPHost.subscriber_errors).
_TELEMETRY_CAP = 100


class MSPViewError(MSPError):
    """A view-plane call failed or its result drifted off the wire shape."""


def _check_session_id(session_id):
    if not isinstance(session_id, str) or not session_id:
        raise ValueError(
            f"session_id must be a non-empty string, got {session_id!r}"
        )
    return session_id


def _check_cursor(cursor, what="cursor"):
    if cursor is not None and (not isinstance(cursor, str) or not cursor):
        raise ValueError(
            f"{what} must be a non-empty string or None, got {cursor!r}"
        )
    return cursor


class JobStateTracker:
    """Derives a job state from view-plane notifications.

    Push notification dicts (as delivered by MSPHost.subscribe) into
    ``push``; read ``state``. The state is DERIVED from tracked facts
    (blocked question, active item/turn, last event time), never stored
    as a transition machine -- so a missed or reordered event degrades
    to a stale reading, never to an impossible state.

    Mapping (#224, fixture-invented details documented in the module
    docstring):
    - ``item/started`` / ``item/delta`` -> working (active item tracked).
    - ``item/completed`` -> the in-flight item is done; working while the
      turn is still active (item boundaries inside a live turn are
      normal -- the issue groups ``completed`` with the working
      signals), idle once no turn is active.
    - ``userInput/request`` / ``approval/requested`` -> blocked, with
      the question surfaced via ``blocked_question``. Blocked clears on
      any subsequent ``item/*`` event (the turn moved on, so the
      question was answered) or on a terminal turn event (the question
      belonged to a turn that no longer exists).
    - ``session/modelChanged`` / ``session/contextUsage`` -> telemetry
      (appended to ``telemetry``, state unchanged).
    - ``turn/started`` -> working (active turn tracked; the #223
      turn-plane client emits these on the plain method names).
    - ``turn/completed`` / ``turn/interrupted`` / ``turn/cancelled`` ->
      active turn, active item, and blocked question all cleared; idle.
    - stalled: no blocked question, no active item, no active turn, and
      the last observed event is older than ``stall_after`` seconds.

    Liveness: EVERY notification attributed to this session refreshes
    the stall clock, mapped or not -- "no events" in the issue means
    literally no events. Malformed notifications (params missing or not
    a dict) are ignored, never raised: the callback runs on the
    transport's reader thread (see msp_turn.watch_turn_events for the
    same rule).

    Attribution: a notification whose ``params.sessionId`` differs from
    this tracker's session id is ignored. One without a sessionId is
    accepted -- the subscription that feeds this tracker was made for
    this session.
    """

    def __init__(self, session_id=None, *, stall_after=STALL_AFTER_SECONDS,
                 now=time.monotonic):
        if session_id is not None:
            _check_session_id(session_id)
        if not isinstance(stall_after, (int, float)) or stall_after <= 0:
            raise ValueError(
                f"stall_after must be a positive number of seconds, "
                f"got {stall_after!r}"
            )
        if not callable(now):
            raise ValueError("now must be a callable returning seconds")
        self.session_id = session_id
        self.stall_after = float(stall_after)
        self._now = now
        self._blocked = None  # the blocking notification dict, or None
        self._active_item = None
        self._active_turn = None
        self._last_event_at = None
        self._telemetry = []  # [(method, params), ...], newest last
        self._seen = 0  # notifications attributed (mapped or not)

    @property
    def state(self):
        """The current job state: working|blocked|idle|stalled."""
        if self._blocked is not None:
            return STATE_BLOCKED
        if self._active_item is not None or self._active_turn is not None:
            return STATE_WORKING
        if self._last_event_at is None:
            return STATE_IDLE
        if self._now() - self._last_event_at >= self.stall_after:
            return STATE_STALLED
        return STATE_IDLE

    @property
    def blocked_question(self):
        """The surfaced question while blocked, else None.

        Best-effort text: ``userInput/request`` carries ``question``,
        ``approval/requested`` carries ``description``; anything else
        falls back to the raw params dict. NOT redacted -- may contain
        real secret values (see Security and trust).
        """
        if self._blocked is None:
            return None
        params = self._blocked.get("params") or {}
        for key in ("question", "description", "prompt"):
            value = params.get(key)
            if isinstance(value, str) and value:
                return value
        return params

    @property
    def blocked_event(self):
        """The full blocking notification dict, or None."""
        return self._blocked

    @property
    def telemetry(self):
        """Recent telemetry notifications: [(method, params), ...]."""
        return list(self._telemetry)

    @property
    def events_seen(self):
        """Count of attributed notifications (mapped or not)."""
        return self._seen

    def _attributed(self, params):
        if not isinstance(params, dict):
            return False
        other = params.get("sessionId")
        return (
            self.session_id is None
            or not isinstance(other, str)
            or other == self.session_id
        )

    def push(self, note):
        """Feed one notification dict (as MSPHost delivers it)."""
        if not isinstance(note, dict):
            return
        params = note.get("params")
        if not self._attributed(params):
            return
        method = note.get("method")
        if not isinstance(method, str):
            return
        self._seen += 1
        self._last_event_at = self._now()

        if method in ("item/started", "item/delta"):
            self._blocked = None
            item_id = params.get("itemId")
            self._active_item = item_id if isinstance(item_id, str) else True
            turn_id = params.get("turnId")
            if isinstance(turn_id, str) and turn_id:
                self._active_turn = turn_id
        elif method == "item/completed":
            self._blocked = None
            self._active_item = None
            # The turn continuing past an item boundary is still working
            # (the issue groups completed with the working signals); only
            # a turn-less completion demotes to idle, via the derived
            # state (no active item + no active turn -> idle).
        elif method in ("userInput/request", "approval/requested"):
            self._blocked = note
        elif method in ("session/modelChanged", "session/contextUsage"):
            self._telemetry.append((method, dict(params)))
            del self._telemetry[:-_TELEMETRY_CAP]
        elif method == "turn/started":
            turn_id = params.get("turnId")
            if isinstance(turn_id, str) and turn_id:
                self._active_turn = turn_id
            else:
                self._active_turn = True
        elif method in ("turn/completed", "turn/interrupted",
                        "turn/cancelled"):
            self._active_turn = None
            self._active_item = None
            self._blocked = None
        # Anything else: liveness only (clock refreshed above, state
        # unchanged). Unknown view methods must not move the state --
        # fail-quiet on the unknown, fail-loud was the subscribe call's
        # job.

    def attach(self, host):
        """Subscribe to the view-plane prefixes on host; return unsubscribe.

        Prefixes ("item", "userInput", "approval", "session", "turn")
        match the plain method names the fixture emits (MSPHost
        prefix-matches "prefix" and "prefix/..."). The callback only
        appends to this tracker -- safe on the reader thread.
        """
        unsubs = [
            host.subscribe(prefix, self.push)
            for prefix in ("item", "userInput", "approval", "session",
                            "turn")
        ]

        def unsubscribe():
            for unsub in unsubs:
                unsub()

        return unsubscribe


def subscribe_view(host, session_id, after=None):
    """Call ``view/subscribe``; return ``(head_cursor, events)``.

    ``after`` is the cursor to resume from (None = from the beginning);
    the server replays the events in ``(after, head]`` and ``head`` is
    the cursor to pass as ``after`` next time. ``events`` is the replay
    list of notification dicts, in order. Raises ValueError for
    client-side validation failures, MSPViewError when the result
    drifts off the wire shape (fail loud, never guess).
    """
    _check_session_id(session_id)
    _check_cursor(after, "after")
    params = {"sessionId": session_id}
    if after is not None:
        params["after"] = after
    result = host.call("view/subscribe", params)
    if not isinstance(result, dict):
        raise MSPViewError(
            "view/subscribe returned a non-dict result: "
            f"{type(result).__name__}"
        )
    events = result.get("events")
    if not isinstance(events, list):
        raise MSPViewError(
            "view/subscribe result has no 'events' list "
            f"(keys: {sorted(result)[:8]})"
        )
    head = result.get("head")
    _check_cursor(head, "result head")
    return head, events


def open_view(host, session_id, after=None, *, stall_after=STALL_AFTER_SECONDS,
              now=time.monotonic):
    """Subscribe at a cursor and attach a live tracker.

    Replays ``(after, head]`` through the tracker, then attaches the
    live prefixes. Returns ``(tracker, head, unsubscribe)``.

    Known race (documented, not fixed this slice): events that land
    between the replay and the attach are missed. Re-subscribing at the
    returned ``head`` recovers them -- the next slice's resync owns
    closing this window.
    """
    tracker = JobStateTracker(session_id, stall_after=stall_after, now=now)
    head, events = subscribe_view(host, session_id, after)
    for event in events:
        tracker.push(event)
    unsubscribe = tracker.attach(host)
    return tracker, head, unsubscribe


def main(argv):
    """Smoke CLI: subscribe to a session's view and tail its state.

    Usage: msp_view.py [--client-name N] [--after CURSOR]
    [--watch-timeout S] --session-id SID -- <serve argv...>, e.g.
    msp_view.py --session-id sess-abc -- muse serve

    Prints the replayed events' methods, the derived state after the
    replay, then tails live events for --watch-timeout seconds printing
    (method, state) transitions. The blocked question IS printed (that
    is the point of surfacing it).

    WARNING: printed output (the blocked question, telemetry payloads)
    is NOT redacted and may contain real secret values -- do not paste
    this output where agents can read it.
    """
    ap = argparse.ArgumentParser(
        description="MSP view-plane smoke CLI (#224)",
        epilog="WARNING: printed output is NOT redacted and may contain "
               "real secret values -- do not paste this output where "
               "agents can read it.",
    )
    ap.add_argument("--client-name", default="msp_view")
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--after", default=None,
                    help="cursor to resume from (default: from the beginning)")
    ap.add_argument("--watch-timeout", type=float, default=30.0,
                    help="seconds to tail live events after the replay")
    ap.add_argument("serve", nargs=argparse.REMAINDER,
                    help="serve argv after --, e.g. -- muse serve")
    args = ap.parse_args(argv)
    serve = list(args.serve)
    if serve and serve[0] == "--":
        serve = serve[1:]
    if not serve:
        ap.error("need serve argv after --")

    out = {"sessionId": args.session_id, "transitions": []}
    host = MSPHost(serve, client_name=args.client_name)
    with host:
        tracker, head, unsubscribe = open_view(host, args.session_id,
                                               args.after)
        try:
            out["head"] = head
            out["stateAfterReplay"] = tracker.state
            last = tracker.state
            end = time.time() + args.watch_timeout
            seen_at_tail = tracker.events_seen
            while time.time() < end:
                time.sleep(0.1)
                if tracker.events_seen != seen_at_tail:
                    seen_at_tail = tracker.events_seen
                    if tracker.state != last:
                        out["transitions"].append(
                            {"state": tracker.state,
                             "question": tracker.blocked_question})
                        last = tracker.state
            out["finalState"] = tracker.state
            out["finalQuestion"] = tracker.blocked_question
        finally:
            unsubscribe()
    # NOT redacted: see the module's Security and trust section. Say it
    # on stderr on EVERY invocation: this output lands on stdout, where
    # it is one pipe or paste away from somewhere an agent can read it.
    print(
        "WARNING: this output is NOT redacted and may contain real secret "
        "values (the blocked question, telemetry payloads) -- do not paste "
        "it where agents can read it.",
        file=sys.stderr,
    )
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
