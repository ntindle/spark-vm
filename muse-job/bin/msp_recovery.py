#!/usr/bin/env python3
"""msp_recovery.py -- dead-model recovery over MSP (issue #226).

The sixth slice of the #228 muse-job v2 migration. Where msp_events.py
(#224) *detects* the stalled shape, this module *recovers* it: the model
stream died mid-turn (the trackball-base-schematic job died twice on
``model stream idle timeout after 180000ms``), and over MSP the symptom
surfaces as events rather than a dead TUI -- but the job still needs a
recovery path.

Detection
---------
``detect_dead_turn`` takes a ``JobView`` (from ``msp_events``) and
reports a ``DeadTurn`` when the view says STALLED without a terminal
event, or TURN_FAILED with a failed terminal:

- ``quiet_running``: session reports running, no events for longer than
  the threshold, no completion event -- the stream died silently.
- ``parked``: status running AND activeTurnId null (the recap-rendered,
  empty-prompt shape from the trackball incident) -- treated as stalled,
  never as healthy, per #226.
- ``turn_failed``: the last turn terminal was ``failed`` (the timeout
  surfaces here as ``turn/completed`` with an error object when the
  server manages to fold it).

Recovery ladder (``recover_dead_turn``)
--------------------------------------
1. If a turn id is still active (or recently was), ``turn/interrupt``
   it best-effort -- a zombie turn must not absorb the continuation.
2. ``turn/start`` a continuation prompt built by
   ``build_reanchor_prompt``: it tells the model its previous turn died,
   points it at the job's PROGRESS.md, and forbids repeating completed
   work.
3. If the session will not take a turn (``TurnNotLiveError`` -- the
   #223 open question answered "no" for this shape), ``session/resume``
   the session fresh on this host and ``turn/start`` again.
4. If that fails too, report ``give_up`` with operator-facing detail --
   the watchdog pages; a human decides.

What this module does NOT do
---------------------------
- It never answers prompts or approvals itself; a dead turn that died
  *blocked* (attention flags set) is not a dead model and is left alone
  for #225's machinery / the operator.
- #212 (auto-update mid-turn): the v1 schema has no update event, so an
  update restart is indistinguishable from a stream death at this layer
  and recovers the same way. The #212 policy carries over unchanged --
  the serve host's environment must set ``MUSE_NO_AUTO_UPDATE=1`` so a
  job's host never stages an update mid-turn; that is enforced in the
  #227 CLI wiring, recorded here as the decision.

Security and trust
------------------
Same posture as msp_host.py: the re-anchor prompt embeds the job dir
path and the PROGRESS.md contents are model-visible by design (the job
already works in that directory). Recovery never logs or prints turn
content; the RecoveryReport carries only ids, action names, and
redacted detail.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msp_host import MSPError, MSPHost  # noqa: E402  (sibling module)
from msp_events import (  # noqa: E402  (sibling module)
    JobView,
    STATE_BLOCKED_APPROVAL,
    STATE_BLOCKED_INPUT,
    STATE_IDLE,
    STATE_SESSION_CLOSED,
    STATE_STALLED,
    STATE_TURN_CANCELLED,
    STATE_TURN_FAILED,
    STATE_WORKING,
    poll_session_view,
)
from msp_turn import TurnNotLiveError, interrupt_turn, start_turn  # noqa: E402
from msp_session import resume_session  # noqa: E402  (sibling module)


class MSPRecoveryError(MSPError):
    """Recovery itself failed (as opposed to reporting give_up)."""


# DeadTurn.reason values.
REASON_QUIET_RUNNING = "quiet_running"
REASON_PARKED = "parked"
REASON_TURN_FAILED = "turn_failed"

# RecoveryReport.action values.
ACTION_NONE = "none"  # nothing dead; no action taken
ACTION_CONTINUED = "continued"  # turn/start accepted the re-anchor
ACTION_RESUMED = "resumed"  # session/resume + turn/start worked
ACTION_GIVE_UP = "give_up"  # needs the operator

PROGRESS_FILENAME = "PROGRESS.md"
# Bound the re-anchor prompt's PROGRESS.md excerpt: the model needs the
# tail (latest state), not the whole log.
PROGRESS_TAIL_CHARS = 4000


class DeadTurn:
    """A detected dead-model shape, ready for the recovery ladder."""

    __slots__ = ("session_id", "turn_id", "reason", "detected_at",
                 "last_state", "detail")

    def __init__(self, session_id, turn_id, reason, last_state,
                 detail=None):
        self.session_id = session_id
        self.turn_id = turn_id
        self.reason = reason
        self.detected_at = time.time()
        self.last_state = last_state
        self.detail = detail

    def __repr__(self):
        return (
            f"DeadTurn(session_id={self.session_id!r}, "
            f"turn_id={self.turn_id!r}, reason={self.reason!r})"
        )


class RecoveryReport:
    """The outcome of one recover_dead_turn() run."""

    __slots__ = ("action", "session_id", "new_turn_id", "detail",
                 "attempts")

    def __init__(self, action, session_id, new_turn_id=None, detail=None):
        self.action = action
        self.session_id = session_id
        self.new_turn_id = new_turn_id
        self.detail = detail
        self.attempts = []

    def note(self, text):
        self.attempts.append(text)

    def __repr__(self):
        return (
            f"RecoveryReport(action={self.action!r}, "
            f"session_id={self.session_id!r}, "
            f"new_turn_id={self.new_turn_id!r})"
        )


def detect_dead_turn(view, *, stale_after=900.0, now=None):
    """Detect a dead model stream from a folded JobView.

    Returns a DeadTurn, or None when the view is not a dead shape.
    Blocked sessions (waiting on the operator) are never dead -- that is
    #225's territory.
    """
    if now is None:
        now = time.time()
    state = view.derive(now=now, stale_after=stale_after)
    if state in (
        STATE_BLOCKED_APPROVAL, STATE_BLOCKED_INPUT,
        STATE_SESSION_CLOSED, STATE_IDLE, STATE_WORKING,
        STATE_TURN_CANCELLED,
    ):
        return None
    if state == STATE_TURN_FAILED:
        return DeadTurn(
            view.session_id, view.last_turn_id, REASON_TURN_FAILED, state,
            detail=f"last_terminal={view.last_terminal}",
        )
    if state == STATE_STALLED:
        if view.active_turn_id is None and view.session_status == "running":
            reason = REASON_PARKED
        else:
            reason = REASON_QUIET_RUNNING
        return DeadTurn(
            view.session_id, view.active_turn_id or view.last_turn_id,
            reason, state,
            detail=f"quiet_for>{stale_after}s",
        )
    return None


def _read_progress_tail(job_dir, max_chars=PROGRESS_TAIL_CHARS):
    """Return the tail of the job's PROGRESS.md, or None."""
    path = os.path.join(job_dir, PROGRESS_FILENAME)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - max_chars))
            return fh.read().strip() or None
    except OSError:
        return None


def build_reanchor_prompt(job_dir, dead):
    """Build the continuation prompt that re-anchors a recovered session.

    The model is told its previous turn died, where the progress log is,
    and what not to redo. PROGRESS.md is the job's own file -- the model
    already works in that directory, so quoting its tail is not a new
    disclosure.
    """
    tail = _read_progress_tail(job_dir)
    lines = [
        "Your previous turn died unexpectedly "
        f"({dead.reason}; no completion event).",
        "Do NOT start over. Read the progress log below -- it is the "
        "authoritative record of what is done -- and continue from the "
        "last incomplete step. Do not repeat completed work.",
    ]
    if tail:
        lines.append("")
        lines.append(f"--- tail of {PROGRESS_FILENAME} ---")
        lines.append(tail)
    return "\n".join(lines)


def _try_start(host, session_id, prompt):
    """turn/start, returning the new turn id; raises on failure."""
    turn, _result = start_turn(host, session_id, prompt)
    turn_id = turn.get("turnId") if isinstance(turn, dict) else None
    if not turn_id:
        raise MSPRecoveryError(
            "turn/start returned no turnId (shape drift)")
    return turn_id


def recover_dead_turn(host, session_id, job_dir, *,
                      stale_after=900.0,
                      continuation_prompt=None,
                      now=None):
    """Run the recovery ladder for one session.

    Polls the view (gapless via the persisted cursor), detects the dead
    shape, and climbs: interrupt zombie turn -> turn/start re-anchor ->
    session/resume + turn/start -> give_up. Returns a RecoveryReport;
    never raises for a session that simply will not recover (that is
    ACTION_GIVE_UP, not an exception). Transport/wire failures raise
    MSPRecoveryError.
    """
    report = RecoveryReport(ACTION_NONE, session_id)
    try:
        view = poll_session_view(
            host, session_id, job_dir, stale_after=stale_after, now=now)
    except MSPError as e:
        raise MSPRecoveryError(f"view poll failed: {e}") from e

    dead = detect_dead_turn(view, stale_after=stale_after, now=now)
    if dead is None:
        report.detail = f"no dead shape (state={view.state})"
        return report

    report.note(f"detected {dead.reason} (state={dead.last_state})")
    prompt = continuation_prompt or build_reanchor_prompt(job_dir, dead)

    # 1. A zombie turn must not absorb the continuation: interrupt it
    # best-effort. Failure here is non-fatal -- start may still work.
    if dead.turn_id:
        try:
            interrupt_turn(host, session_id, turn_id=dead.turn_id)
            report.note(f"interrupted zombie turn {dead.turn_id[:8]}…")
        except MSPError as e:
            report.note(f"interrupt best-effort failed: {e}")

    # 2. Re-anchor with a fresh turn.
    try:
        new_turn = _try_start(host, session_id, prompt)
        report.action = ACTION_CONTINUED
        report.new_turn_id = new_turn
        report.detail = f"re-anchored on {dead.reason}"
        return report
    except TurnNotLiveError as e:
        report.note(f"turn/start refused (not live): {e}")
    except MSPError as e:
        raise MSPRecoveryError(f"turn/start failed: {e}") from e

    # 3. The session will not take a turn on this host connection:
    # resume it fresh and try once more.
    try:
        resume_session(host, session_id)
        report.note("session/resume ok")
    except MSPError as e:
        raise MSPRecoveryError(f"session/resume failed: {e}") from e
    try:
        new_turn = _try_start(host, session_id, prompt)
        report.action = ACTION_RESUMED
        report.new_turn_id = new_turn
        report.detail = f"resumed + re-anchored on {dead.reason}"
        return report
    except TurnNotLiveError as e:
        report.note(f"post-resume turn/start refused: {e}")
    except MSPError as e:
        raise MSPRecoveryError(f"post-resume turn/start failed: {e}") from e

    # 4. Out of ladder: the operator decides.
    report.action = ACTION_GIVE_UP
    report.detail = (
        f"session would not take a turn after interrupt + resume "
        f"(reason={dead.reason}); needs operator")
    return report


# -- smoke CLI ---------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="msp_recovery smoke CLI (issue #226): detect a dead "
        "model stream and run the recovery ladder. Prints actions and "
        "redacted detail only.")
    ap.add_argument("--muse-bin", default="muse")
    ap.add_argument("--serve-log", default=None)
    ap.add_argument("--job-dir", default=".")
    ap.add_argument("--stale-after", type=float, default=900.0)
    ap.add_argument("--prompt", default=None,
                    help="override the re-anchor prompt")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect", help="poll and report the dead shape")
    d.add_argument("session_id")
    r = sub.add_parser("recover", help="run the recovery ladder")
    r.add_argument("session_id")
    args = ap.parse_args(argv)

    host = MSPHost([args.muse_bin, "serve"],
                   client_name="msp_recovery_smoke",
                   log_path=args.serve_log)
    host.open()
    try:
        if args.cmd == "detect":
            view = poll_session_view(
                host, args.session_id, args.job_dir,
                stale_after=args.stale_after)
            dead = detect_dead_turn(view, stale_after=args.stale_after)
            print(f"state={view.state}")
            print(f"dead={dead!r}")
        else:
            report = recover_dead_turn(
                host, args.session_id, args.job_dir,
                stale_after=args.stale_after,
                continuation_prompt=args.prompt)
            print(f"action={report.action}")
            print(f"new_turn_id={report.new_turn_id}")
            print(f"detail={report.detail}")
            for attempt in report.attempts:
                print(f"  - {attempt}")
    finally:
        host.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
