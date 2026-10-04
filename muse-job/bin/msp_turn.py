#!/usr/bin/env python3
"""msp_turn.py -- MSP turn-plane client for muse-job v2 (#223).

Turn-steering methods on top of bin/msp_host.py's transport (issue #221),
the third slice of the #228 muse-job v2 migration (drive jobs over MSP
instead of scraping a tmux TUI):

- ``turn/start``      -- begin a new turn on a live session with a prompt
  (the spawn prompt-as-argv equivalent).
- ``turn/steer``      -- inject a follow-up message into a live session's
  current turn (the tmux send-keys replacement).
- ``turn/interrupt``  -- stop the session's active turn.
- ``turn/cancel``     -- drop a queued turn that has not started yet.

This kills the whole #211 bug class: no Enter swallowing, no separate
send-keys text/Enter dance, no input-box-clear verification, no
pasted-text safety checks. The prompt/message travels as one opaque JSON
string in the request body -- the client never touches a shell, never
fragments the text, and never interprets it. That is the prompt-as-argv
equivalence #223's acceptance demands: whatever lands on the wire is
byte-identical to what the operator passed.

Steer vs. start, in this client's contract: ``start_turn`` begins a new
turn (a fresh model invocation); ``steer_turn`` injects a message into
the session's current turn. The fixture below models them distinctly;
the real wire's exact distinction is unverified -- see the provenance
section.

Wire-shape provenance
---------------------
The method names (``turn/start``, ``turn/steer``, ``turn/interrupt``,
``turn/cancel``) come from the #223 issue and the #228 plan. EVERYTHING
else on the turn plane -- params, result shapes, turn records, events,
error reasons -- is fixture-invented, NOT verified against the
deployment binary this turn (there is no turn-plane transcript corpus
yet). The module validates what it sends, parses results defensively,
and fails loud (MSPTurnError) on shape drift instead of guessing.
MSPHost's schema-fingerprint pin (``verify_schema_on_open``) is the
drift tripwire -- pass ``expected_schema_fingerprint`` from the
deployment binary when opening the host. A future live-verification
turn (the #226 slot owns the dead-model path) should replace this
section with the transcript-sourced shapes, as #222's module did.

The dead-idle question (#223's open question) is NOT answered live
here: whether ``turn/steer`` wakes a session whose model died on a
stream idle timeout (``activeTurnId: null`` -- the trackball-base-
schematic parked state) was not tested against a real session this
turn. This client's contract is honest about it: a steer/interrupt
against a session the server reports as not turn-capable surfaces as
TurnNotLiveError, never as a silent success, and the client never
pretends to resurrect a dead turn. The dead-model recovery behavior
belongs to #226; its turn will define what steer means there.

Fixture provenance (what the hermetic test fixture invents)
----------------------------------------------------------
The fake ``muse serve`` in ``muse-job/tests/test_msp_turn.py`` stands
in for wire shapes that do not exist in any transcript yet. Its
invented details:
- the turn record (``turnId``, ``state`` running|queued|completed|
  interrupted|cancelled, ``promptEcho``);
- ``turn/started``, ``turn/steered``, ``turn/interrupted``,
  ``turn/cancelled`` view events (fixture emits them on the plain
  method names);
- the not-turn-capable error reasons ``turn_not_live``,
  ``no_active_turn``, ``no_queued_turn`` (the client maps all three to
  TurnNotLiveError; a different real-wire reason would land as the
  parent MSPTurnError, which is still fail-loud);
- a second ``turn/start`` while one is running queueing a new turn
  (the ``cancel`` half of interrupt-vs-cancel).
The client only asserts the parts it documents (the turn record's
presence and turnId, the not-live error mapping), so the invented
details can be wrong without the client misbehaving.

Security and trust
------------------
Same posture as msp_session.py, which this module does not weaken:
steered prompts and turn transcripts may contain real secret values.
Results are NEVER redacted, never logged, never printed by the library
functions. The smoke CLI below prints results to stdout -- do not paste
that output where agents can read it. The prompt path has one
deliberate anti-property worth stating: the text is never executed --
no shell, no eval, no template expansion -- on the way to the wire.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msp_host import MSPError, MSPHost, ServerError  # noqa: E402  (sibling module)
from msp_session import check_command_id, new_command_id  # noqa: E402  (#222 layer)

# Server-reported reasons that mean "this session is not turn-capable
# right now". Fixture-invented; mapped to TurnNotLiveError. Anything
# else stays a plain MSPTurnError (fail-loud, not mislabeled).
_NOT_LIVE_REASONS = ("turn_not_live", "no_active_turn", "no_queued_turn")


class MSPTurnError(MSPError):
    """A turn-plane call failed or its result drifted off the wire shape."""


class TurnNotLiveError(MSPTurnError):
    """The server reports no live turn to steer/interrupt/cancel.

    The client refuses to pretend the operation landed. If the session's
    model died (stream idle timeout, the #223 open-question state), the
    dead-model recovery path is issue #226's territory -- this module
    never attempts a resurrection.
    """


def _check_session_id(session_id):
    if not isinstance(session_id, str) or not session_id:
        raise ValueError(
            f"session_id must be a non-empty string, got {session_id!r}"
        )
    return session_id


def _check_text(text, what):
    """Validate a prompt/message: a real string, non-blank, passed VERBATIM.

    The verbatim property is load-bearing for #223's acceptance (the
    prompt-as-argv equivalent): shell metacharacters, backticks, newlines
    and $(...) sequences travel byte-identical to the wire. The only
    client-side rejection is a blank message -- steering an empty string
    into a live turn is always a caller bug, and the wire has no honest
    reading of it.
    """
    # No special case for bool: bool is not a subclass of str, so this
    # isinstance check already rejects True/False.
    if not isinstance(text, str):
        raise ValueError(f"{what} must be a string, got {text!r}")
    if not text.strip():
        raise ValueError(f"{what} must not be blank (whitespace-only)")
    return text


def _check_turn_id(turn_id):
    if not isinstance(turn_id, str) or not turn_id:
        raise ValueError(f"turn_id must be a non-empty string, got {turn_id!r}")
    return turn_id


def _require_turn(result, method):
    """Pull the turn record out of a call result; fail loud on drift.

    The serve schema (muse 1.4.x) returns the turn id flat on the result
    (``TurnStartResult.turnId`` etc.); older shapes nested it under a
    ``turn`` object. Accept both, normalizing to a dict carrying at
    least ``turnId``.
    """
    if not isinstance(result, dict):
        raise MSPTurnError(
            f"{method} returned a non-dict result: {type(result).__name__}"
        )
    turn = result.get("turn")
    if isinstance(turn, dict):
        pass
    elif isinstance(result.get("turnId"), str) and result["turnId"]:
        turn = {"turnId": result["turnId"]}
        # Carry the sibling fields callers read, when present.
        for key in ("sessionId", "state", "status", "disposition"):
            if key in result:
                turn[key] = result[key]
    else:
        raise MSPTurnError(
            f"{method} result has no turn id "
            f"(keys: {sorted(result)[:8]})"
        )
    if not turn.get("turnId"):
        raise MSPTurnError(
            f"{method} result 'turn' has no turnId "
            f"(keys: {sorted(turn)[:8]})"
        )
    return turn


def _raise_for_not_live(server_error, session_id, method):
    """Map the fixture's not-turn-capable reasons to TurnNotLiveError."""
    data = server_error.data
    if isinstance(data, dict) and data.get("reason") in _NOT_LIVE_REASONS:
        raise TurnNotLiveError(
            f"{method} on session {session_id!r}: the server reports no "
            f"live turn ({data.get('reason')}); the operation did not land. "
            f"Dead-model recovery (steer waking a session whose model died "
            f"on stream idle timeout) is issue #226's territory -- this "
            f"client never resurrects a dead turn."
        ) from server_error
    raise server_error


def _call_turn(host, method, params, session_id):
    try:
        return host.call(method, params)
    except ServerError as e:
        _raise_for_not_live(e, session_id, method)


def _text_part(text):
    """Wrap a plain prompt/message string as a turn input part.

    The serve schema (muse 1.4.x) takes ``input`` -- an ordered array of
    content parts -- instead of the older opaque ``prompt``/``message``
    string fields. A text part needs only its type discriminator.
    """
    return {"type": "text", "text": text}


def start_turn(host, session_id, prompt, *, command_id=None):
    """Begin a new turn on a live session; return (turn_dict, result_dict).

    ``turn/start`` is the spawn prompt-as-argv equivalent: the prompt is
    one opaque string in the request body, never fragmented, never
    shell-parsed. command_id defaults to a fresh UUIDv7 per call (an
    applied command id may not be reused -- pass your own only for
    retry-after-unacknowledged semantics).

    Raises ValueError for client-side validation failures,
    TurnNotLiveError when the server reports no live session to start
    on, ServerError for other host errors, MSPTurnError when the result
    drifts off the wire shape.
    """
    _check_session_id(session_id)
    _check_text(prompt, "prompt")
    cid = check_command_id(command_id) if command_id is not None else new_command_id()
    params = {
        "commandId": cid,
        "sessionId": session_id,
        "input": [_text_part(prompt)],
    }
    result = _call_turn(host, "turn/start", params, session_id)
    return _require_turn(result, "turn/start"), result


def steer_turn(host, session_id, message, *, command_id=None,
               expected_turn_id=None):
    """Inject a follow-up message into the session's current turn.

    ``turn/steer`` is the tmux send-keys replacement: no Enter
    swallowing, no text/Enter dance, no paste verification. The message
    travels verbatim (see _check_text). expected_turn_id is the turn the
    caller polled as active -- the server rejects the steer when another
    turn has taken over (the anti-cross-turn guard). Returns
    (turn_dict, result_dict); raises as start_turn does.
    """
    _check_session_id(session_id)
    _check_text(message, "message")
    cid = check_command_id(command_id) if command_id is not None else new_command_id()
    params = {
        "commandId": cid,
        "sessionId": session_id,
        "expectedTurnId": _check_turn_id(expected_turn_id),
        "input": [_text_part(message)],
    }
    result = _call_turn(host, "turn/steer", params, session_id)
    return _require_turn(result, "turn/steer"), result


def interrupt_turn(host, session_id, *, turn_id=None):
    """Stop the session's active turn; return the result dict.

    turn_id scopes the interrupt when supplied; omitted, the server acts
    on the active turn. A completed/never-started turn is a
    TurnNotLiveError, not a silent no-op.
    """
    _check_session_id(session_id)
    params = {"sessionId": session_id}
    if turn_id is not None:
        params["turnId"] = _check_turn_id(turn_id)
    result = _call_turn(host, "turn/interrupt", params, session_id)
    _require_turn(result, "turn/interrupt")
    return result


def cancel_turn(host, session_id, *, turn_id=None):
    """Drop a queued turn that has not started yet; return the result dict.

    Interrupt stops the model's current output; cancel removes a queued
    turn (see the fixture: a second turn/start while one runs queues).
    turn_id scopes the cancel when supplied; omitted, the server acts on
    the queued turn. No queued turn is a TurnNotLiveError.
    """
    _check_session_id(session_id)
    params = {"sessionId": session_id}
    if turn_id is not None:
        params["turnId"] = _check_turn_id(turn_id)
    result = _call_turn(host, "turn/cancel", params, session_id)
    _require_turn(result, "turn/cancel")
    return result


def watch_turn_events(host, session_id, turn_id, timeout=30.0):
    """Subscribe to the turn prefix and collect this turn's events.

    Returns the list of notification dicts seen until a terminal
    ``turn/<completed|interrupted|cancelled>`` event for turn_id, or
    until timeout seconds elapse (returns what was seen). Events are
    filtered to session_id when given. This is the #223 acceptance made
    concrete: "steer a prompt into a live session and observe the turn
    start via events". The callback runs on the transport's reader
    thread -- it appends and returns; callers must not call
    call()/notify() from it (see MSPHost.subscribe).

    Malformed notifications (params missing or not a dict) are ignored, not
    raised: one bad event must not kill the watcher on the reader thread.
    """
    seen = []
    done = {"hit": False}
    terminal = {"turn/completed", "turn/interrupted", "turn/cancelled"}

    def on_note(note):
        params = note.get("params")
        if not isinstance(params, dict):
            # Missing or non-dict params carry nothing to filter on. Ignore
            # the event rather than raising AttributeError here: the host
            # records subscriber exceptions and drops the event, which
            # would silently lose a terminal event and turn the watch into
            # a full-timeout wait.
            params = {}
        if session_id is not None and params.get("sessionId") != session_id:
            return
        seen.append(note)
        if note.get("method") in terminal and params.get("turnId") == turn_id:
            done["hit"] = True

    unsub = host.subscribe("turn", on_note)
    try:
        end = time.time() + timeout
        while time.time() < end and not done["hit"]:
            time.sleep(0.05)
    finally:
        unsub()
    return seen


class TurnStillbornError(MSPTurnError):
    """The first turn of a spawn died before the agent could engage.

    Raised (via await_first_turn_engagement) when the turn reaches a
    dead terminal -- cancelled, interrupted, or failed -- inside the
    engagement window. At spawn time no user exists to cancel or
    interrupt a turn, so a dead first turn means the spawn never
    engaged: the caller must fail the spawn loudly rather than leave
    the job behind as "active" (issue #994). The redacted event-method
    journal rides on .journal for diagnostics; note params are never
    attached (prompts may carry real secret values).
    """

    def __init__(self, message, *, turn_id, terminal, journal):
        super().__init__(message)
        self.turn_id = turn_id
        self.terminal = terminal
        self.journal = tuple(journal)


# Terminals that mean "the turn died before the agent engaged". At
# spawn time a completed turn is fine (a fast prompt that finished);
# anything else reaching terminal inside the engagement window is a
# stillborn spawn.
_FIRST_TURN_DEAD_TERMINALS = ("cancelled", "interrupted", "failed")

# How long spawn waits for the first turn to prove it is alive. The
# #994 cancellation landed ~1ms after turn start; ten seconds is
# generous for a healthy turn to emit its first event while keeping a
# silent-but-dead server from stalling spawn badly.
FIRST_TURN_ENGAGEMENT_TIMEOUT = 10.0


def _turn_terminal(note, turn_id):
    """Classify a notification's terminal state for turn_id, or None.

    Two wire shapes exist (the fixture emits method-level
    ``turn/cancelled``; the real serve host emits ``turn/completed``
    with a ``terminal`` param -- issue #994's journal): both are
    honored, mirroring msp_events' classification. A ``turn/completed``
    with no terminal param reads as completed. Unknown non-empty
    terminal strings pass through verbatim so callers see the drift
    instead of a guess.
    """
    if not isinstance(note, dict):
        return None
    params = note.get("params")
    if not isinstance(params, dict) or params.get("turnId") != turn_id:
        return None
    method = note.get("method")
    if method == "turn/completed":
        terminal = params.get("terminal")
        if isinstance(terminal, str) and terminal:
            return terminal
        return "completed"
    if method == "turn/cancelled":
        return "cancelled"
    if method == "turn/interrupted":
        return "interrupted"
    return None


def await_first_turn_engagement(host, session_id, turn_id, *,
                                timeout=FIRST_TURN_ENGAGEMENT_TIMEOUT):
    """Watch the first turn of a spawn until it engages or dies.

    Returns a dict {"status", "terminal", "journal", "elapsed_s"}:

    - ``"engaged"`` -- no terminal event inside the window; the turn is
      (presumably) still running. This is the normal case.
    - ``"done"`` -- the turn completed inside the window (a fast prompt
      that finished); terminal is "completed".
    - ``"dead"`` -- the turn reached a dead terminal (cancelled /
      interrupted / failed) inside the window, before the agent could
      engage. The caller must treat the spawn as failed
      (TurnStillbornError), never as a live job.

    ``journal`` is the method-name sequence seen (methods only, no
    params -- safe to log; prompts may carry secrets). Malformed
    notifications are ignored, never raised: the callback runs on the
    transport's reader thread (same rule as watch_turn_events).

    This is the issue-#994 acceptance made concrete: "verify the first
    turn actually engages, not just that the session started".
    """
    _check_session_id(session_id)
    _check_turn_id(turn_id)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError(
            f"timeout must be a positive number of seconds, got {timeout!r}")
    seen = []
    terminal = {"value": None}
    t0 = time.time()

    def on_note(note):
        params = note.get("params") if isinstance(note, dict) else None
        if not isinstance(params, dict):
            # Missing or non-dict params carry nothing to filter on.
            # Ignore rather than raising: subscriber exceptions drop the
            # event silently, which would lose a terminal and turn the
            # watch into a full-timeout wait.
            return
        if params.get("sessionId") != session_id:
            return
        method = note.get("method")
        if isinstance(method, str):
            seen.append(method)
        term = _turn_terminal(note, turn_id)
        if term is not None and terminal["value"] is None:
            terminal["value"] = term

    unsub = host.subscribe("turn", on_note)
    try:
        end = t0 + timeout
        while time.time() < end and terminal["value"] is None:
            time.sleep(0.05)
    finally:
        unsub()
    elapsed = time.time() - t0
    term = terminal["value"]
    if term is None:
        status = "engaged"
    elif term in _FIRST_TURN_DEAD_TERMINALS:
        status = "dead"
    else:
        status = "done"
    return {"status": status, "terminal": term, "journal": list(seen),
            "elapsed_s": elapsed}


def main(argv):
    """Smoke CLI: exercise the turn plane against a real serve host.

    Usage: msp_turn.py [--client-name N] [--watch] <start|steer|interrupt|cancel>
    [options] -- <serve argv...>, e.g.
    msp_turn.py --watch steer --session-id sess-abc --message "go on" -- muse serve

    WARNING: results (prompts, transcripts) are NOT redacted -- do not
    paste this output where agents can read it.
    """
    ap = argparse.ArgumentParser(
        description="MSP turn-plane smoke CLI (#223)",
        epilog="WARNING: printed results (prompts, transcripts) are NOT "
               "redacted and may contain real secret values -- do not paste "
               "this output where agents can read it.",
    )
    ap.add_argument("--client-name", default="msp_turn")
    ap.add_argument("--watch", action="store_true",
                    help="after the call, observe the turn's events until "
                         "it terminates (the #223 acceptance). Caveat: for "
                         "interrupt/cancel the terminal event fires during "
                         "the call itself -- before the watcher subscribes "
                         "-- so --watch usually observes nothing there; it "
                         "is meant for start/steer of still-running turns.")
    ap.add_argument("--watch-timeout", type=float, default=30.0)
    sub = ap.add_subparsers(dest="action", required=True)

    def add_serve(p):
        # REMAINDER inside a subparser keeps optionals parseable; the
        # literal "--" separator lands in the list and is stripped below.
        p.add_argument("serve", nargs=argparse.REMAINDER,
                       help="serve argv after --, e.g. -- muse serve")

    def add_common(p):
        p.add_argument("--session-id", required=True)
        p.add_argument("--command-id", default=None)
        add_serve(p)

    def add_interruptible(p):
        p.add_argument("--session-id", required=True)
        p.add_argument("--turn-id", default=None)
        add_serve(p)

    p_start = sub.add_parser("start", help="turn/start a new turn")
    p_start.add_argument("--prompt", required=True)
    add_common(p_start)

    p_steer = sub.add_parser("steer", help="turn/steer a follow-up message")
    p_steer.add_argument("--message", required=True)
    p_steer.add_argument("--turn-id", required=True,
                         help="expected active turn id (server-required "
                         "anti-cross-turn guard)")
    add_common(p_steer)

    p_int = sub.add_parser("interrupt", help="turn/interrupt the active turn")
    add_interruptible(p_int)

    p_can = sub.add_parser("cancel", help="turn/cancel a queued turn")
    add_interruptible(p_can)

    args = ap.parse_args(argv)
    serve = list(args.serve)
    if serve and serve[0] == "--":
        serve = serve[1:]
    if not serve:
        ap.error("need serve argv after --")

    host = MSPHost(serve, client_name=args.client_name)
    with host:
        turn_id = None
        if args.action == "start":
            turn, result = start_turn(host, args.session_id, args.prompt,
                                      command_id=args.command_id)
            turn_id = turn["turnId"]
            out = {"turn": turn, "result": result}
        elif args.action == "steer":
            turn, result = steer_turn(host, args.session_id, args.message,
                                      command_id=args.command_id,
                                      expected_turn_id=args.turn_id)
            turn_id = turn["turnId"]
            out = {"turn": turn, "result": result}
        elif args.action == "interrupt":
            out = interrupt_turn(host, args.session_id, turn_id=args.turn_id)
            turn_id = args.turn_id
        else:  # cancel
            out = cancel_turn(host, args.session_id, turn_id=args.turn_id)
            turn_id = args.turn_id
        if args.watch and turn_id:
            out["watchedEvents"] = watch_turn_events(
                host, args.session_id, turn_id, timeout=args.watch_timeout)
        elif args.watch:
            print("WARNING: --watch needs a turn id; interrupt/cancel "
                  "require --turn-id to watch", file=sys.stderr)
    # NOT redacted: see the module's Security and trust section. Say it on
    # stderr on EVERY invocation, not just in --help: this output lands on
    # stdout, where it is one pipe or paste away from somewhere an agent
    # can read it.
    print(
        "WARNING: this output is NOT redacted and may contain real secret "
        "values (prompts, turn transcripts) -- do not paste it where "
        "agents can read it.",
        file=sys.stderr,
    )
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
