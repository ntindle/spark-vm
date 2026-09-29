#!/usr/bin/env python3
"""msp_session.py -- MSP session-lifecycle client for muse-job v2 (#222).

Session-plane methods on top of bin/msp_host.py's transport (issue #221),
the second slice of the #228 muse-job v2 migration (drive jobs over MSP
instead of scraping a tmux TUI):

- ``session/start``  -- create a brand-new session, load it on this host,
  auto-subscribe this connection.
- ``session/resume`` -- load a stored session on this host; returns the
  history needed to render it.
- ``session/list``   -- page stored sessions (read-only; never touches
  leases) for history/picker UIs.
- ``session/read``   -- read one stored session without attaching: no
  lease, no load, no subscription, no resume record.

Cutover decision (from #222, adopted by this slice): serve-hosted only --
no tmux pane is kept for human peeking. ``muse-job log`` reads the event
stream instead. The CLI spawn/resume rewire itself is the #227 cutover
slice; this module is the session-lifecycle primitive it builds on.

Wire-shape provenance
---------------------
#221 verified the transport live against muse 1.3.0 on spark-vm
(2026-09-21): NDJSON stdio, initialize/initialized gating,
clientInfo.name ``^[a-z0-9_]+$``. The session-plane param/result shapes
below come from community live-verified ``muse serve`` transcripts
(Sept 2026, muse 1.0.1-1.3.0: session/start's commandId/workspaceRoot
params and full session-record result, the 1..=200 session/list bound,
the no-attach session/read record, the wire approval-mode enum) --
cross-checked against #221's handshake findings, NOT from Meta's docs
and NOT re-verified against the deployment binary this turn. Treat them
as verified-once: the module validates what it sends, parses results
defensively, and fails loud (MSPSessionError) on shape drift instead of
guessing. MSPHost's schema-fingerprint pin (``verify_schema_on_open``)
is the drift tripwire -- pass ``expected_schema_fingerprint`` from the
deployment binary when opening the host.

Approval modes spell differently on the wire than on the CLI:
``allowAll | promptUnmatched | onRequest | denyUnmatched``. ``--yolo``
(the standing muse-job posture) is ``allowAll`` on the wire
(YOLO_APPROVAL_MODE). A mode may not exceed the one the host's startup
posture sealed -- the host rejects it; this client passes the requested
mode through and lets the host fail loud.

``session/start`` takes ``commandId`` (UUIDv7, required -- the binary
rejects anything else) and ``workspaceRoot`` (absolute, as the host sees
it). Optional: ``providerId`` (defaults server-side to ``"muse"``),
``modelId``, ``approvalMode``, ``sessionId``. The ``sessionId`` param
NEVER selects an existing session: a retained/reserved id that collides
is rejected ``commandRejected`` with reason ``session_id_conflict``
(raised here as SessionIdConflictError). ``config`` is an empty struct
in v1 -- this client never sends it. Setting ``approvalMode`` fires a
``session/approvalModeChanged`` view event immediately; subscribe to
``"session"`` (or the full method) to see it.

Security and trust
------------------
Same posture as msp_host.py, which this module does not weaken:
``session/read`` transcripts and ``session/resume`` history may contain
real secret values. Results are NEVER redacted, never logged, never
printed by the library functions. The smoke CLI below prints results to
stdout -- do not paste that output where agents can read it.
"""

import argparse
import json
import os
import re
import secrets
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msp_host import MSPError, MSPHost, ServerError  # noqa: E402  (sibling module)

# Wire approval-mode enum (verified on the wire; CLI spells differ).
APPROVAL_MODES = (
    "allowAll",
    "promptUnmatched",
    "onRequest",
    "denyUnmatched",
)
# --yolo, the standing muse-job posture, on the wire (#222).
YOLO_APPROVAL_MODE = "allowAll"
# session/list pagination bound, published and enforced server-side.
SESSION_LIST_LIMIT_MAX = 200

_UUID7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class MSPSessionError(MSPError):
    """A session-plane call failed or its result drifted off the wire shape."""


class SessionIdConflictError(MSPSessionError):
    """The requested session/start sessionId collided (never selects)."""


def new_command_id():
    """Generate a UUIDv7 command id (RFC 9562 §5.7), as session/start needs.

    uuid.uuid7 exists only on 3.14+; the deployment floor is older, so the
    128-bit layout is built by hand: 48-bit unix_ts_ms | ver 0111 |
    12-bit rand_a | var 10 | 62-bit rand_b.
    """
    unix_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (unix_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    return str(uuid.UUID(int=value))


def check_command_id(value, what="command_id"):
    """Validate a caller-supplied command id is UUIDv7; return the string."""
    if not isinstance(value, str) or not _UUID7_RE.match(value):
        raise ValueError(
            f"{what} must be a UUIDv7 string (the serve host rejects "
            f"anything else), got {value!r}"
        )
    return value


def _check_session_id(session_id):
    if not isinstance(session_id, str) or not session_id:
        raise ValueError(
            f"session_id must be a non-empty string, got {session_id!r}"
        )
    return session_id


def _require_session(result, method):
    """Pull the session record out of a call result; fail loud on drift."""
    if not isinstance(result, dict):
        raise MSPSessionError(
            f"{method} returned a non-dict result: {type(result).__name__}"
        )
    session = result.get("session")
    if not isinstance(session, dict):
        raise MSPSessionError(
            f"{method} result has no 'session' object "
            f"(keys: {sorted(result)[:8]})"
        )
    if not session.get("sessionId"):
        raise MSPSessionError(
            f"{method} result 'session' has no sessionId "
            f"(keys: {sorted(session)[:8]})"
        )
    return session


def _raise_for_conflict(server_error, session_id):
    data = server_error.data
    if isinstance(data, dict) and data.get("reason") == "session_id_conflict":
        raise SessionIdConflictError(
            f"session/start sessionId {session_id!r} conflicts with a "
            f"retained/reserved id (the param never selects an existing "
            f"session): {server_error}"
        ) from server_error
    raise server_error


def start_session(
    host,
    workspace_root,
    *,
    approval_mode=None,
    provider_id=None,
    model_id=None,
    session_id=None,
    command_id=None,
):
    """Create a brand-new session on the serve host; return (session, view_cursor).

    workspace_root must be absolute as the host sees it. approval_mode is
    one of APPROVAL_MODES (wire spelling); YOLO_APPROVAL_MODE is the --yolo
    equivalent. command_id defaults to a fresh UUIDv7 per call (an applied
    command id may not be reused -- pass your own only for retry-after-
    unacknowledged semantics, #223's territory).

    Returns (session_dict, view_cursor_or_None). Raises ValueError for
    client-side validation failures, SessionIdConflictError when the
    requested session_id collides, ServerError for other host errors,
    MSPSessionError when the result drifts off the wire shape.
    """
    if not isinstance(workspace_root, str) or not os.path.isabs(workspace_root):
        raise ValueError(
            "workspace_root must be an absolute path as the serve host "
            f"sees it, got {workspace_root!r}"
        )
    if approval_mode is not None and approval_mode not in APPROVAL_MODES:
        raise ValueError(
            f"approval_mode must be one of {APPROVAL_MODES} (wire "
            f"spelling; --yolo is {YOLO_APPROVAL_MODE!r}), "
            f"got {approval_mode!r}"
        )
    cid = check_command_id(command_id) if command_id is not None else new_command_id()
    params = {"commandId": cid, "workspaceRoot": workspace_root}
    if provider_id is not None:
        if not isinstance(provider_id, str) or not provider_id:
            raise ValueError(f"provider_id must be a non-empty string, got {provider_id!r}")
        params["providerId"] = provider_id
    if model_id is not None:
        if not isinstance(model_id, str) or not model_id:
            raise ValueError(f"model_id must be a non-empty string, got {model_id!r}")
        params["modelId"] = model_id
    if approval_mode is not None:
        params["approvalMode"] = approval_mode
    if session_id is not None:
        params["sessionId"] = _check_session_id(session_id)
    # config is an empty struct in v1: never sent.
    try:
        result = host.call("session/start", params)
    except ServerError as e:
        _raise_for_conflict(e, session_id)
    session = _require_session(result, "session/start")
    view_cursor = result.get("viewCursor")
    return session, view_cursor


def resume_session(host, session_id):
    """Load a stored session on this host; return the full result dict.

    Auto-subscribes this connection and returns the history needed to
    render the session (history shape is not pinned -- only the session
    record's presence is asserted; fail loud on drift).
    """
    _check_session_id(session_id)
    result = host.call("session/resume", {"sessionId": session_id})
    _require_session(result, "session/resume")
    return result


def list_sessions(host, limit=100):
    """Page stored sessions; return (sessions, next_cursor).

    Read-only: never touches leases. limit is client-validated to the
    server-enforced 1..=SESSION_LIST_LIMIT_MAX bound.
    """
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= SESSION_LIST_LIMIT_MAX
    ):
        raise ValueError(
            f"limit must be an int in 1..={SESSION_LIST_LIMIT_MAX}, "
            f"got {limit!r}"
        )
    result = host.call("session/list", {"limit": limit})
    if not isinstance(result, dict) or not isinstance(result.get("sessions"), list):
        raise MSPSessionError(
            "session/list result has no 'sessions' list "
            f"(keys: {sorted(result)[:8] if isinstance(result, dict) else 'n/a'})"
        )
    return result["sessions"], result.get("nextCursor")


def read_session(host, session_id):
    """Read one stored session WITHOUT attaching; return the session record.

    No lease, no load, no subscription, no resume record -- safe for
    status polling and picker UIs. An unknown id answers a notLoaded
    record, not an error.
    """
    _check_session_id(session_id)
    result = host.call("session/read", {"sessionId": session_id})
    return _require_session(result, "session/read")


def main(argv):
    """Smoke CLI: exercise the session plane against a real serve host.

    Usage: msp_session.py [--client-name N] <start|resume|list|read>
    [options] -- <serve argv...>, e.g.
    msp_session.py start --workspace-root /home/ntindle/work -- muse serve

    WARNING: results (transcripts, history) are NOT redacted -- do not
    paste this output where agents can read it.
    """
    ap = argparse.ArgumentParser(
        description="MSP session-lifecycle smoke CLI",
        epilog="WARNING: printed results (transcripts, history) are NOT "
               "redacted and may contain real secret values -- do not paste "
               "this output where agents can read it.",
    )
    ap.add_argument("--client-name", default="msp_session")
    sub = ap.add_subparsers(dest="action", required=True)

    def add_serve(p):
        # REMAINDER inside a subparser keeps optionals parseable; the
        # literal "--" separator lands in the list and is stripped below.
        p.add_argument("serve", nargs=argparse.REMAINDER,
                       help="serve argv after --, e.g. -- muse serve")

    p_start = sub.add_parser("start", help="session/start a new session")
    p_start.add_argument("--workspace-root", required=True)
    p_start.add_argument("--approval-mode", default=None,
                         choices=list(APPROVAL_MODES))
    p_start.add_argument("--provider-id", default=None)
    p_start.add_argument("--model-id", default=None)
    p_start.add_argument("--session-id", default=None)
    p_start.add_argument("--command-id", default=None)
    add_serve(p_start)

    p_resume = sub.add_parser("resume", help="session/resume a stored session")
    p_resume.add_argument("--session-id", required=True)
    add_serve(p_resume)

    p_list = sub.add_parser("list", help="session/list stored sessions")
    p_list.add_argument("--limit", type=int, default=100)
    add_serve(p_list)

    p_read = sub.add_parser("read", help="session/read without attaching")
    p_read.add_argument("--session-id", required=True)
    add_serve(p_read)

    args = ap.parse_args(argv)
    serve = list(args.serve)
    if serve and serve[0] == "--":
        serve = serve[1:]
    if not serve:
        ap.error("need serve argv after --")

    host = MSPHost(serve, client_name=args.client_name)
    with host:
        if args.action == "start":
            session, cursor = start_session(
                host,
                args.workspace_root,
                approval_mode=args.approval_mode,
                provider_id=args.provider_id,
                model_id=args.model_id,
                session_id=args.session_id,
                command_id=args.command_id,
            )
            out = {"session": session, "viewCursor": cursor}
        elif args.action == "resume":
            out = resume_session(host, args.session_id)
        elif args.action == "list":
            sessions, cursor = list_sessions(host, limit=args.limit)
            out = {"sessions": sessions, "nextCursor": cursor}
        else:  # read
            out = {"session": read_session(host, args.session_id)}
    # NOT redacted: see the module's Security and trust section. Say it on
    # stderr on EVERY invocation, not just in --help: this output lands on
    # stdout, where it is one pipe or paste away from somewhere an agent
    # can read it.
    print(
        "WARNING: this output is NOT redacted and may contain real secret "
        "values (session transcripts, history) -- do not paste it where "
        "agents can read it.",
        file=sys.stderr,
    )
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
