"""Hermetic tests for muse-job/bin/msp_recovery.py (issue #226).

No `muse` binary is needed: every test drives a fake `muse serve`
fixture that speaks NDJSON JSON-RPC 2.0 over stdio and implements the
view + turn + session planes the recovery ladder needs.

Fixture-invented behavior (documented in the module, NOT wire-verified):
the fake answers turn/start with {"turn": {"turnId": ...}} (the shape
msp_turn._require_turn demands); a script with "turn_start": "not_live"
answers turn/start with data.reason "turn_not_live" (one of
msp_turn._NOT_LIVE_REASONS) so the client raises TurnNotLiveError;
"not_live_then_ok" refuses the first turn/start and accepts later ones
(to exercise the resume rung); session/resume always succeeds.
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import time

import pytest

BIN_PATH = os.path.join(os.path.dirname(__file__), "..", "bin",
                         "msp_recovery.py")


def load_mod(name="msp_recovery_under_test"):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, BIN_PATH)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


mspr = load_mod()

import msp_events as mspe  # noqa: E402  (real sibling, via sys.path)


FAKE_RECOVERY_SERVE = (
    "#!/usr/bin/env python3\n"
    + r'''
import json, sys

script_path = sys.argv[sys.argv.index("--script") + 1]
with open(script_path) as fh:
    script = json.load(fh)

session = script.get("session", {})
events = script.get("events", [])
turn_start_mode = script.get("turn_start", "ok")
turn_start_calls = 0

def send(o):
    sys.stdout.write(json.dumps(o) + "\n")
    sys.stdout.flush()

def err(rid, code, message, data=None):
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    send({"jsonrpc": "2.0", "id": rid, "error": e})

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
        for i, ev in enumerate(events):
            p = dict(ev.get("params", {}))
            p.setdefault("viewCursor", "c%d" % (i + 1))
            send({"jsonrpc": "2.0", "method": ev["method"],
                  "params": p})
        head = "c%d" % len(events) if events else "c0"
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"viewCursor": head}})
    elif method == "turn/interrupt":
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"turn": {"turnId": params.get("turnId",
                                                       "turn-old")}}})
    elif method == "turn/start":
        turn_start_calls += 1
        refuse = (turn_start_mode == "not_live" or
                  (turn_start_mode == "not_live_then_ok"
                   and turn_start_calls == 1))
        if refuse:
            err(rid, -32030, "no live turn",
                {"kind": "commandRejected", "reason": "turn_not_live"})
        else:
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"turn": {"turnId": "turn-new-%d"
                                               % turn_start_calls}}})
    elif method == "session/resume":
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"session": session, "history": []}})
    elif rid is not None:
        send({"jsonrpc": "2.0", "id": rid,
              "error": {"code": -32601, "message": "no such method"}})
'''
)


@pytest.fixture()
def serve_bin(tmp_path):
    p = tmp_path / "fake-serve"
    p.write_text(FAKE_RECOVERY_SERVE)
    p.chmod(0o755)
    return str(p)


def write_script(tmp_path, name, session, events, turn_start="ok"):
    p = tmp_path / (name + ".json")
    p.write_text(json.dumps({
        "session": session,
        "events": events,
        "turn_start": turn_start,
    }))
    return str(p)


def open_host(serve_bin, script):
    from msp_host import MSPHost
    host = MSPHost([serve_bin, "--script", script],
                   client_name="msp_recovery_test")
    host.open()
    return host


def old_running_session(**kw):
    s = {
        "sessionId": "sess-1",
        "status": "running",
        "activeTurnId": "turn-old",
        "attention": [],
        # Long ago: the quiet clock reads stale without fresh events.
        "lastActivityAt": "2026-01-01T00:00:00Z",
    }
    s.update(kw)
    return s


def stalled_view(**kw):
    """A JobView folded into the stalled shape without a host."""
    view = mspe.JobView("sess-1")
    view.session_status = "running"
    view.active_turn_id = kw.get("active_turn_id", "turn-old")
    view.last_event_at = time.time() - 3600
    view.state = mspe.STATE_STALLED
    return view


# -- detect_dead_turn --------------------------------------------------------

def test_detect_quiet_running():
    dead = mspr.detect_dead_turn(stalled_view())
    assert dead is not None
    assert dead.reason == mspr.REASON_QUIET_RUNNING
    assert dead.turn_id == "turn-old"


def test_detect_parked():
    dead = mspr.detect_dead_turn(stalled_view(active_turn_id=None))
    assert dead is not None
    assert dead.reason == mspr.REASON_PARKED


def test_detect_turn_failed():
    view = mspe.JobView("sess-1")
    view.state = mspe.STATE_TURN_FAILED
    view.last_terminal = "failed"
    view.last_turn_id = "turn-old"
    dead = mspr.detect_dead_turn(view)
    assert dead is not None
    assert dead.reason == mspr.REASON_TURN_FAILED


def test_detect_never_flags_blocked_or_working():
    for state in (mspe.STATE_BLOCKED_APPROVAL, mspe.STATE_BLOCKED_INPUT,
                  mspe.STATE_WORKING, mspe.STATE_IDLE):
        view = mspe.JobView("sess-1")
        view.state = state
        view.session_status = "running"
        view.last_event_at = time.time()
        assert mspr.detect_dead_turn(view) is None, state


# -- build_reanchor_prompt ---------------------------------------------------

def test_reanchor_prompt_uses_progress_tail(tmp_path):
    (tmp_path / "PROGRESS.md").write_text(
        "2026-10-01: did the thing\n2026-10-01: doing the other thing\n")
    dead = mspr.DeadTurn("s", "t", mspr.REASON_PARKED, "stalled")
    prompt = mspr.build_reanchor_prompt(str(tmp_path), dead)
    assert "parked" in prompt
    assert "doing the other thing" in prompt
    assert "PROGRESS.md" in prompt


def test_reanchor_prompt_without_progress(tmp_path):
    dead = mspr.DeadTurn("s", None, mspr.REASON_QUIET_RUNNING, "stalled")
    prompt = mspr.build_reanchor_prompt(str(tmp_path), dead)
    assert "quiet_running" in prompt
    assert "Do not repeat completed work" in prompt


# -- recover_dead_turn -------------------------------------------------------

def test_recover_nothing_dead(serve_bin, tmp_path):
    script = write_script(tmp_path, "s1", old_running_session(), [
        {"method": "item/delta", "params": {}},
    ])
    (tmp_path / "PROGRESS.md").write_text("did stuff\n")
    host = open_host(serve_bin, script)
    try:
        report = mspr.recover_dead_turn(
            host, "sess-1", str(tmp_path), stale_after=3600.0)
    finally:
        host.close()
    assert report.action == mspr.ACTION_NONE


def test_recover_continued_happy_path(serve_bin, tmp_path):
    script = write_script(tmp_path, "s2", old_running_session(), [])
    (tmp_path / "PROGRESS.md").write_text("half done\n")
    host = open_host(serve_bin, script)
    try:
        report = mspr.recover_dead_turn(
            host, "sess-1", str(tmp_path), stale_after=60.0)
    finally:
        host.close()
    assert report.action == mspr.ACTION_CONTINUED
    assert report.new_turn_id == "turn-new-1"
    assert any("interrupt" in a for a in report.attempts)


def test_recover_resume_rung(serve_bin, tmp_path):
    script = write_script(tmp_path, "s3", old_running_session(), [],
                          turn_start="not_live_then_ok")
    (tmp_path / "PROGRESS.md").write_text("half done\n")
    host = open_host(serve_bin, script)
    try:
        report = mspr.recover_dead_turn(
            host, "sess-1", str(tmp_path), stale_after=60.0)
    finally:
        host.close()
    assert report.action == mspr.ACTION_RESUMED
    assert report.new_turn_id == "turn-new-2"
    assert any("resume" in a for a in report.attempts)


def test_recover_give_up(serve_bin, tmp_path):
    script = write_script(tmp_path, "s4", old_running_session(), [],
                          turn_start="not_live")
    (tmp_path / "PROGRESS.md").write_text("half done\n")
    host = open_host(serve_bin, script)
    try:
        report = mspr.recover_dead_turn(
            host, "sess-1", str(tmp_path), stale_after=60.0)
    finally:
        host.close()
    assert report.action == mspr.ACTION_GIVE_UP
    assert report.new_turn_id is None
    assert "operator" in report.detail
