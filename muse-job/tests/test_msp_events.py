"""Hermetic tests for muse-job/bin/msp_events.py (issue #224).

No `muse` binary is needed: every test drives a fake `muse serve`
fixture that speaks NDJSON JSON-RPC 2.0 over stdio and implements the
view plane (session/read, view/subscribe with (after, head] replay).

Fixture-invented behavior (documented in the module, NOT wire-verified):
cursors are "c1".."cN" strings compared by their numeric suffix; the
replay is delivered synchronously inside the view/subscribe handler
before the result is sent (the real server streams them as ordinary
notifications -- the client only relies on arrival order, which both
shapes preserve); session/read returns the script's session record
verbatim.
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import threading
import time

import pytest

BIN_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "msp_events.py")


def load_mod(name="msp_events_under_test"):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, BIN_PATH)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


mspe = load_mod()

# ---------------------------------------------------------------------------
# Fake `muse serve` with a view plane. The test writes a JSON script:
# {"session": {...}, "events": [{"method":..., "params": {...}}, ...],
#  "live": [{"method":..., "params": {...}}, ...]}
# Events are replayed with cursors c1..cN on view/subscribe (after, head];
# "live" events are emitted 0.3s after the subscribe returns.
# ---------------------------------------------------------------------------
FAKE_VIEW_SERVE = (
    "#!/usr/bin/env python3\n"
    + r'''
import json, sys, threading, time

script_path = sys.argv[sys.argv.index("--script") + 1]
with open(script_path) as fh:
    script = json.load(fh)

session = script.get("session", {})
events = script.get("events", [])
live = script.get("live", [])

def send(o):
    sys.stdout.write(json.dumps(o) + "\n")
    sys.stdout.flush()

def cursor_of(i):
    return "c%d" % (i + 1)

def emit_live():
    for ev in live:
        params = dict(ev.get("params", {}))
        params.setdefault("viewCursor", "cL")
        send({"jsonrpc": "2.0", "method": ev["method"],
              "params": params})

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    method = msg.get("method")
    rid = msg.get("id")
    params = msg.get("params") or {}
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"serverInfo": {"name": "fake-serve"}}})
    elif method == "session/read":
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"session": session}})
    elif method == "view/subscribe":
        after = params.get("after")
        after_n = int(after[1:]) if isinstance(after, str) and after.startswith("c") and after[1:].isdigit() else 0
        for i, ev in enumerate(events):
            if i + 1 > after_n:
                p = dict(ev.get("params", {}))
                p["viewCursor"] = cursor_of(i)
                send({"jsonrpc": "2.0", "method": ev["method"],
                      "params": p})
        head = cursor_of(len(events) - 1) if events else "c0"
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"viewCursor": head}})
        if live:
            threading.Timer(0.3, emit_live).start()
    elif rid is not None:
        send({"jsonrpc": "2.0", "id": rid,
              "error": {"code": -32601, "message": "no such method"}})
'''
)


@pytest.fixture()
def serve_bin(tmp_path):
    p = tmp_path / "fake-serve"
    p.write_text(FAKE_VIEW_SERVE)
    p.chmod(0o755)
    return str(p)


def write_script(tmp_path, session, events, live=None):
    p = tmp_path / "script.json"
    p.write_text(json.dumps({
        "session": session,
        "events": events,
        "live": live or [],
    }))
    return str(p)


def open_host(serve_bin, script):
    from msp_host import MSPHost
    # Import the sibling the same way the module does.
    host = MSPHost(
        [serve_bin, "--script", script],
        client_name="msp_events_test",
    )
    host.open()
    return host


def running_session(**kw):
    s = {
        "sessionId": "sess-1",
        "status": "running",
        "activeTurnId": "turn-1",
        "attention": [],
        "modelId": "m",
        "providerId": "p",
        "path": "/tmp/x",
        "workspaceRoot": "/tmp",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        # lastActivityAt is "now" at script-write time: the fake's record
        # is static, so stalled tests pass an explicit future `now`.
        "lastActivityAt": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "forkedFrom": None,
        "turnCount": 1,
    }
    s.update(kw)
    return s


def note(method, **params):
    return {"jsonrpc": "2.0", "method": method, "params": params}


# -- classify_notification: pure unit tests ---------------------------------

def test_classify_working_methods():
    for m in ("item/started", "item/delta", "item/updated"):
        s = mspe.classify_notification(note(m, viewCursor="c1"))
        assert s.kind == mspe.SIG_WORKING, m
        assert s.view_cursor == "c1"


def test_classify_turn_completed_terminals():
    s = mspe.classify_notification(
        note("turn/completed", terminal="completed", turnId="t1"))
    assert s.kind == mspe.SIG_TURN_DONE
    s = mspe.classify_notification(
        note("turn/completed", terminal="failed", turnId="t1"))
    assert s.kind == mspe.SIG_TURN_FAILED
    s = mspe.classify_notification(
        note("turn/completed", terminal="cancelled", turnId="t1"))
    assert s.kind == mspe.SIG_TURN_CANCELLED
    # Unknown terminal: fail-soft to turn_done (the turn ended).
    s = mspe.classify_notification(
        note("turn/completed", terminal="weird", turnId="t1"))
    assert s.kind == mspe.SIG_TURN_DONE


def test_classify_blocked_and_telemetry():
    s = mspe.classify_notification(note("approval/requested"))
    assert s.kind == mspe.SIG_BLOCKED_APPROVAL
    s = mspe.classify_notification(
        note("session/statusChanged", status="running",
             attention=["approvalPending"], viewCursor="c9"))
    assert s.kind == mspe.SIG_BLOCKED_APPROVAL
    s = mspe.classify_notification(
        note("session/statusChanged", status="running",
             attention=["inputPending"]))
    assert s.kind == mspe.SIG_BLOCKED_INPUT
    s = mspe.classify_notification(
        note("session/statusChanged", status="running", attention=[]))
    assert s.kind == mspe.SIG_STATUS
    for m in ("session/tokenUsage", "session/contextUsage",
              "session/modelChanged"):
        assert mspe.classify_notification(note(m)).kind == mspe.SIG_TELEMETRY
    assert (mspe.classify_notification(note("session/closed")).kind
            == mspe.SIG_SESSION_CLOSED)


def test_classify_malformed_never_raises():
    assert mspe.classify_notification({}).kind == mspe.SIG_UNKNOWN
    assert mspe.classify_notification({"method": 42}).kind == mspe.SIG_UNKNOWN
    assert mspe.classify_notification("nope").kind == mspe.SIG_UNKNOWN
    assert (mspe.classify_notification(
        note("something/entirely-new")).kind == mspe.SIG_UNKNOWN)


def test_redacted_summary_has_no_free_text():
    s = mspe.classify_notification(note(
        "approval/requested", viewCursor="c1",
        detail="the operator password is hunter2, approve?",
        approvalId="a1"))
    assert s.detail is None or "hunter2" not in (s.detail or "")


# -- cursor persistence ------------------------------------------------------

def test_cursor_round_trip(tmp_path):
    assert mspe.load_cursor(str(tmp_path)) is None
    before = time.time()
    mspe.save_cursor(str(tmp_path), "c42")
    assert mspe.load_cursor(str(tmp_path)) == "c42"
    cursor, at = mspe._load_cursor_record(str(tmp_path))
    assert cursor == "c42"
    assert at is not None and at >= before
    # Empty/invalid values are never persisted.
    mspe.save_cursor(str(tmp_path), "")
    assert mspe.load_cursor(str(tmp_path)) == "c42"


def test_cursor_bare_string_backward_compat(tmp_path):
    # Pre-#224 format: a bare cursor string, no timestamp.
    (tmp_path / mspe.CURSOR_FILENAME).write_text("c7\n")
    assert mspe.load_cursor(str(tmp_path)) == "c7"
    cursor, at = mspe._load_cursor_record(str(tmp_path))
    assert cursor == "c7" and at is None


# -- poll_session_view -------------------------------------------------------

def test_poll_working_state_and_cursor(serve_bin, tmp_path):
    script = write_script(tmp_path, running_session(), [
        {"method": "item/started", "params": {}},
        {"method": "item/delta", "params": {}},
    ])
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.5)
    finally:
        host.close()
    assert view.state == mspe.STATE_WORKING
    assert view.signals_seen == 2
    assert view.active_turn_id == "turn-1"  # seeded from session/read
    assert mspe.load_cursor(str(tmp_path)) == "c2"


def test_poll_replay_is_gapless(serve_bin, tmp_path):
    script = write_script(tmp_path, running_session(), [
        {"method": "item/started", "params": {}},
        {"method": "item/delta", "params": {}},
        {"method": "turn/completed",
         "params": {"terminal": "completed", "turnId": "turn-1"}},
    ])
    host = open_host(serve_bin, script)
    try:
        v1 = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.5)
        assert v1.signals_seen == 3
        assert v1.state == mspe.STATE_IDLE
        # Second poll replays nothing new (cursor at head). The fake's
        # session record is static (still "running"), so the honest
        # derived state is working -- a live server would report idle
        # after the completed turn.
        v2 = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.5)
        assert v2.signals_seen == 0
        assert v2.state == mspe.STATE_WORKING
        assert v2.active_turn_id == "turn-1"  # re-seeded from session/read
    finally:
        host.close()


def test_poll_blocked_on_attention(serve_bin, tmp_path):
    script = write_script(
        tmp_path,
        running_session(attention=["approvalPending"]),
        [{"method": "session/statusChanged",
          "params": {"status": "running",
                     "attention": ["approvalPending"]}}],
    )
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.5)
    finally:
        host.close()
    assert view.state == mspe.STATE_BLOCKED_APPROVAL


def test_poll_turn_failed(serve_bin, tmp_path):
    script = write_script(tmp_path, running_session(), [
        {"method": "turn/completed",
         "params": {"terminal": "failed", "turnId": "turn-1",
                    "reason": "model stream idle timeout after 180000ms"}},
    ])
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.5)
    finally:
        host.close()
    assert view.state == mspe.STATE_TURN_FAILED
    assert view.last_terminal == "failed"
    assert view.active_turn_id is None


def test_poll_stalled_quiet_running(serve_bin, tmp_path):
    script = write_script(tmp_path, running_session(), [])
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.3,
            stale_after=60.0, now=time.time() + 3600)
    finally:
        host.close()
    assert view.state == mspe.STATE_STALLED


def test_poll_stalled_parked_active_turn_null(serve_bin, tmp_path):
    # The #226 recap-parked shape: status running, activeTurnId null.
    script = write_script(
        tmp_path, running_session(activeTurnId=None), [])
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.3,
            stale_after=60.0, now=time.time() + 3600)
    finally:
        host.close()
    assert view.state == mspe.STATE_STALLED


def test_poll_unknown_session_is_fail_soft(serve_bin, tmp_path):
    script = write_script(tmp_path, {}, [])
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "nope", str(tmp_path), replay_wait=0.3)
    finally:
        host.close()
    assert view.state == mspe.STATE_UNKNOWN


def test_poll_session_closed(serve_bin, tmp_path):
    script = write_script(tmp_path, running_session(), [
        {"method": "session/closed", "params": {}},
    ])
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.5)
    finally:
        host.close()
    assert view.state == mspe.STATE_SESSION_CLOSED


# -- tail_session_view -------------------------------------------------------

def test_tail_yields_live_signals(serve_bin, tmp_path):
    script = write_script(
        tmp_path, running_session(), [],
        live=[{"method": "item/delta", "params": {}}],
    )
    host = open_host(serve_bin, script)
    try:
        seen = []
        for signal, view in mspe.tail_session_view(
                host, "sess-1", str(tmp_path), duration=2.0,
                poll_interval=0.2):
            seen.append((signal.kind, view.state))
        kinds = [k for k, _ in seen]
        assert mspe.SIG_WORKING in kinds
    finally:
        host.close()


# -- derive() unit tests -----------------------------------------------------

def test_derive_blocked_beats_stalled():
    view = mspe.JobView("s")
    view.state = mspe.STATE_BLOCKED_INPUT
    view.session_status = "running"
    view.last_event_at = time.time() - 99999
    assert view.derive(stale_after=60.0) == mspe.STATE_BLOCKED_INPUT


def test_derive_idle_when_quiet_but_not_running():
    view = mspe.JobView("s")
    view.state = mspe.STATE_IDLE
    view.session_status = "idle"
    view.last_event_at = time.time() - 99999
    assert view.derive(stale_after=60.0) == mspe.STATE_IDLE


def test_derive_no_baseline_never_claims_stalled():
    # No events, no lastActivityAt, no cursor: stalled is unprovable.
    view = mspe.JobView("s")
    view.state = mspe.STATE_WORKING
    view.session_status = "running"
    view.last_event_at = None
    assert view.derive(stale_after=60.0) == mspe.STATE_WORKING


def test_seed_last_activity_at_drives_quiet_clock(serve_bin, tmp_path):
    # lastActivityAt 2h ago, session running, empty replay -> stalled,
    # without needing an explicit `now` override.
    script = write_script(
        tmp_path,
        running_session(lastActivityAt="2026-01-01T00:00:00Z"),
        [],
    )
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.3,
            stale_after=60.0)
    finally:
        host.close()
    assert view.state == mspe.STATE_STALLED


# -- turn lifecycle tracking -------------------------------------------------

def test_turn_started_tracks_active_turn(serve_bin, tmp_path):
    script = write_script(tmp_path, running_session(activeTurnId=None), [
        {"method": "turn/started",
         "params": {"turnId": "turn-9", "sessionId": "sess-1"}},
        {"method": "item/delta", "params": {}},
    ])
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.5)
    finally:
        host.close()
    assert view.state == mspe.STATE_WORKING
    assert view.active_turn_id == "turn-9"


def test_turn_completed_clears_only_matching_turn(serve_bin, tmp_path):
    view = mspe.JobView("sess-1")
    view.active_turn_id = "turn-9"
    view.fold(mspe.classify_notification(
        note("turn/completed", terminal="completed", turnId="turn-OTHER")))
    # A completion for a different turn must not clear the active one.
    assert view.active_turn_id == "turn-9"
    view.fold(mspe.classify_notification(
        note("turn/completed", terminal="completed", turnId="turn-9")))
    assert view.active_turn_id is None
    assert view.state == mspe.STATE_IDLE


# -- userInput notification side ---------------------------------------------

def test_user_input_requested_blocks(serve_bin, tmp_path):
    script = write_script(tmp_path, running_session(), [
        {"method": "userInput/requested",
         "params": {"userInputId": "ui-1", "sessionId": "sess-1"}},
    ])
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.5)
    finally:
        host.close()
    assert view.state == mspe.STATE_BLOCKED_INPUT


def test_user_input_settled_clears_block():
    view = mspe.JobView("sess-1")
    view.fold(mspe.classify_notification(note("userInput/requested")))
    assert view.state == mspe.STATE_BLOCKED_INPUT
    view.fold(mspe.classify_notification(
        note("userInput/settled", outcome="answered")))
    assert view.state == mspe.STATE_WORKING
    assert mspe._ATTENTION_INPUT not in view.attention


# -- view/gap -----------------------------------------------------------------

def test_view_gap_reseeds_from_session_read(serve_bin, tmp_path):
    script = write_script(tmp_path, running_session(), [
        {"method": "view/gap",
         "params": {"after": "c0", "next": "c2", "sessionId": "sess-1"}},
        {"method": "item/delta", "params": {}},
    ])
    host = open_host(serve_bin, script)
    try:
        view = mspe.poll_session_view(
            host, "sess-1", str(tmp_path), replay_wait=0.5)
    finally:
        host.close()
    # Gap was absorbed by the re-seed; the post-gap event still folds.
    assert view.had_gap is False
    assert view.state == mspe.STATE_WORKING
