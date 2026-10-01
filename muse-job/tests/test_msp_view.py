"""Hermetic tests for muse-job/bin/msp_view.py (issue #224).

No `muse` binary is needed: every test drives a fake `muse serve`
fixture that speaks NDJSON JSON-RPC 2.0 over stdio and implements the
view plane (view/subscribe with (after, head] replay, then live
notifications) with the wire shapes the module documents.

Fixture-invented behavior (documented in the module, NOT wire-verified):
cursors are "c<n>"; replay is the events strictly after the `after`
cursor; an unknown session answers an empty replay with head "c0";
live events arrive on the plain method names (item/started|delta|
completed, userInput/request, approval/requested,
session/modelChanged, session/contextUsage, turn/started|completed|
interrupted|cancelled); a test-only view/__emit method injects
notifications; drift sentinels make view/subscribe answer malformed
results.
"""
import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
import sys
import threading
import time

import pytest

BIN_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "msp_view.py")
HOST_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "msp_host.py")


def load_mod(path, name):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


mspv = load_mod(BIN_PATH, "msp_view_under_test")
msph = load_mod(HOST_PATH, "msp_host_for_view_tests")

# ---------------------------------------------------------------------------
# Fake `muse serve` with a view plane. Per-session event logs live in
# memory; cursors are "c<n>" (the log length at that point).
# ---------------------------------------------------------------------------
FAKE_VIEW_SERVE = (
    "#!/usr/bin/env python3\n"
    + r'''
import argparse, json, sys

ap = argparse.ArgumentParser()
ap.add_argument("--record", default=None)
args = ap.parse_args()

rec = open(args.record, "a") if args.record else None
initialized = False

# sid -> [notification dicts]
logs = {}

def record(msg):
    if rec:
        rec.write(json.dumps(msg) + "\n")
        rec.flush()

def send(o):
    sys.stdout.write(json.dumps(o) + "\n")
    sys.stdout.flush()

def err(rid, code, message, data=None):
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    send({"jsonrpc": "2.0", "id": rid, "error": e})

def notify(method, params):
    send({"jsonrpc": "2.0", "method": method, "params": params})

def log_for(sid):
    return logs.setdefault(sid, [])

def emit(sid, method, params):
    note = {"jsonrpc": "2.0", "method": method, "params": params}
    log_for(sid).append(note)
    notify(method, params)

def cursor_of(sid):
    return "c%d" % len(log_for(sid))

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    record(msg)
    method, rid = msg.get("method"), msg.get("id")
    params = msg.get("params") or {}
    if method is None:
        continue
    if method == "initialized":
        initialized = True
        continue
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"protocolVersion": "1",
                         "serverInfo": {"name": "fake-muse-serve",
                                        "version": "0"}}})
        continue
    if not initialized:
        err(rid, -32099, "Not initialized")
        continue
    if method == "view/subscribe":
        after = params.get("after")
        # Test-only drift sentinels: the real wire never sees these.
        if after == "drift:notdict":
            send({"jsonrpc": "2.0", "id": rid, "result": "not-a-dict"})
            continue
        if after == "drift:noevents":
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"head": "c0"}})
            continue
        if after == "drift:badhead":
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"head": 42, "events": []}})
            continue
        sid = params.get("sessionId")
        log = log_for(sid)
        start = 0
        if after is not None:
            try:
                start = int(str(after)[1:])
            except (ValueError, IndexError):
                start = 0
        replay = log[start:]
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"head": cursor_of(sid),
                         "events": [dict(e) for e in replay]}})
        continue
    if method == "view/__emit":
        # Test-only control plane: append to the session log AND deliver
        # the notification live to subscribers.
        emit(params.get("sessionId"), params.get("method"),
             params.get("params"))
        send({"jsonrpc": "2.0", "id": rid, "result": {"ok": True}})
        continue
    err(rid, -32601, "unknown method")
''')


def _write_view_serve(tmp_path):
    path = tmp_path / "fake_view_serve.py"
    path.write_text(FAKE_VIEW_SERVE)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return [sys.executable, str(path)]


@pytest.fixture()
def view_serve(tmp_path):
    return _write_view_serve(tmp_path)


def open_host(argv):
    host = msph.MSPHost(argv, client_name="msp_view_test")
    host.open()
    return host


def wait_for(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def emit(host, sid, method, params):
    """Drive the fixture's test-only injection; wait for live delivery."""
    host.call("view/__emit",
              {"sessionId": sid, "method": method, "params": params})


# ---------------------------------------------------------------------------
# subscribe_view: the (after, head] replay contract
# ---------------------------------------------------------------------------

def test_subscribe_replay_window(view_serve):
    host = open_host(view_serve)
    try:
        emit(host, "s1", "item/started",
             {"sessionId": "s1", "itemId": "i1"})
        emit(host, "s1", "item/delta",
             {"sessionId": "s1", "itemId": "i1"})
        emit(host, "s1", "item/completed",
             {"sessionId": "s1", "itemId": "i1"})
        head, events = mspv.subscribe_view(host, "s1")
        assert head == "c3"
        assert [e["method"] for e in events] == [
            "item/started", "item/delta", "item/completed"]
        # Resume at the head: only newer events replay.
        emit(host, "s1", "turn/completed",
             {"sessionId": "s1", "turnId": "t1"})
        head2, events2 = mspv.subscribe_view(host, "s1", after=head)
        assert head2 == "c4"
        assert [e["method"] for e in events2] == ["turn/completed"]
        # Mid-log cursor replays the tail.
        _, events3 = mspv.subscribe_view(host, "s1", after="c1")
        assert [e["method"] for e in events3] == [
            "item/delta", "item/completed", "turn/completed"]
    finally:
        host.close()


def test_subscribe_unknown_session_empty_replay(view_serve):
    host = open_host(view_serve)
    try:
        head, events = mspv.subscribe_view(host, "nope")
        assert head == "c0"
        assert events == []
    finally:
        host.close()


def test_subscribe_drift_fails_loud(view_serve):
    host = open_host(view_serve)
    try:
        with pytest.raises(mspv.MSPViewError):
            mspv.subscribe_view(host, "s1", after="drift:notdict")
        with pytest.raises(mspv.MSPViewError):
            mspv.subscribe_view(host, "s1", after="drift:noevents")
        with pytest.raises(ValueError):
            mspv.subscribe_view(host, "s1", after="drift:badhead")
    finally:
        host.close()


def test_subscribe_client_validation(view_serve):
    host = open_host(view_serve)
    try:
        with pytest.raises(ValueError):
            mspv.subscribe_view(host, "")
        with pytest.raises(ValueError):
            mspv.subscribe_view(host, "s1", after=42)
        with pytest.raises(ValueError):
            mspv.subscribe_view(host, "s1", after="")
    finally:
        host.close()


# ---------------------------------------------------------------------------
# JobStateTracker: the notification -> state mapping
# ---------------------------------------------------------------------------

def live_tracker(host, sid, **kw):
    """open_view against the fixture; return (tracker, head, unsub)."""
    return mspv.open_view(host, sid, **kw)


def test_working_transitions(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            assert tracker.state == "idle"
            emit(host, "s1", "item/started",
                 {"sessionId": "s1", "itemId": "i1", "turnId": "t1"})
            assert wait_for(lambda: tracker.state == "working")
            emit(host, "s1", "item/delta",
                 {"sessionId": "s1", "itemId": "i1", "turnId": "t1"})
            assert wait_for(lambda: tracker.state == "working")
            # Item boundary inside a live turn stays working (the issue
            # groups completed with the working signals).
            emit(host, "s1", "item/completed",
                 {"sessionId": "s1", "itemId": "i1", "turnId": "t1"})
            assert wait_for(lambda: tracker.events_seen == 3)
            assert tracker.state == "working"
            # The turn ending demotes to idle.
            emit(host, "s1", "turn/completed",
                 {"sessionId": "s1", "turnId": "t1"})
            assert wait_for(lambda: tracker.state == "idle")
        finally:
            unsub()
    finally:
        host.close()


def test_completed_without_turn_goes_idle(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            emit(host, "s1", "item/started",
                 {"sessionId": "s1", "itemId": "i1"})
            assert wait_for(lambda: tracker.state == "working")
            emit(host, "s1", "item/completed",
                 {"sessionId": "s1", "itemId": "i1"})
            assert wait_for(lambda: tracker.state == "idle")
        finally:
            unsub()
    finally:
        host.close()


def test_turn_started_alone_is_working(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            emit(host, "s1", "turn/started",
                 {"sessionId": "s1", "turnId": "t9"})
            assert wait_for(lambda: tracker.state == "working")
        finally:
            unsub()
    finally:
        host.close()


def test_blocked_and_question_surfaced(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            emit(host, "s1", "item/started",
                 {"sessionId": "s1", "itemId": "i1", "turnId": "t1"})
            assert wait_for(lambda: tracker.state == "working")
            emit(host, "s1", "userInput/request",
                 {"sessionId": "s1",
                  "question": "Which region should I deploy to?"})
            assert wait_for(lambda: tracker.state == "blocked")
            assert tracker.blocked_question == \
                "Which region should I deploy to?"
            # The turn moving on means the question was answered.
            emit(host, "s1", "item/started",
                 {"sessionId": "s1", "itemId": "i2", "turnId": "t1"})
            assert wait_for(lambda: tracker.state == "working")
            assert tracker.blocked_question is None
        finally:
            unsub()
    finally:
        host.close()


def test_blocked_by_approval_request(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            emit(host, "s1", "approval/requested",
                 {"sessionId": "s1",
                  "description": "Run rm -rf /tmp/scratch?"})
            assert wait_for(lambda: tracker.state == "blocked")
            assert tracker.blocked_question == "Run rm -rf /tmp/scratch?"
            assert tracker.blocked_event["method"] == "approval/requested"
        finally:
            unsub()
    finally:
        host.close()


def test_blocked_cleared_by_terminal_turn(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            emit(host, "s1", "userInput/request",
                 {"sessionId": "s1", "question": "Continue?"})
            assert wait_for(lambda: tracker.state == "blocked")
            # The question belonged to a turn that no longer exists.
            emit(host, "s1", "turn/interrupted",
                 {"sessionId": "s1", "turnId": "t1"})
            assert wait_for(lambda: tracker.state == "idle")
            assert tracker.blocked_question is None
        finally:
            unsub()
    finally:
        host.close()


def test_telemetry_does_not_move_state(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            emit(host, "s1", "session/contextUsage",
                 {"sessionId": "s1", "pct": 42})
            assert wait_for(lambda: tracker.events_seen == 1)
            assert tracker.state == "idle"
            assert tracker.telemetry == [
                ("session/contextUsage", {"sessionId": "s1", "pct": 42})]
            emit(host, "s1", "session/modelChanged",
                 {"sessionId": "s1", "model": "m2"})
            assert wait_for(lambda: tracker.events_seen == 2)
            assert tracker.state == "idle"
            assert len(tracker.telemetry) == 2
        finally:
            unsub()
    finally:
        host.close()


def test_unknown_methods_are_liveness_only(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            # session/approvalModeChanged is #222's fixture vocabulary:
            # unknown to this tracker, must not move the state.
            emit(host, "s1", "session/approvalModeChanged",
                 {"sessionId": "s1", "mode": "allowAll"})
            assert wait_for(lambda: tracker.events_seen == 1)
            assert tracker.state == "idle"
            assert tracker.telemetry == []
        finally:
            unsub()
    finally:
        host.close()


def test_malformed_notification_ignored(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            # params=None: the reader thread must survive it. Delivery
            # takes a beat; after it lands the event must be ignored.
            emit(host, "s1", "item/started", None)
            time.sleep(0.3)
            assert tracker.state == "idle"
            assert tracker.events_seen == 0
        finally:
            unsub()
    finally:
        host.close()


def test_cross_session_isolation(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            emit(host, "s2", "item/started",
                 {"sessionId": "s2", "itemId": "i9"})
            time.sleep(0.3)
            assert tracker.state == "idle"
            assert tracker.events_seen == 0
        finally:
            unsub()
    finally:
        host.close()


def test_stalled_after_silence_without_turn(view_serve):
    t = [1000.0]
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(
            host, "s1", stall_after=600.0, now=lambda: t[0])
        try:
            emit(host, "s1", "item/completed",
                 {"sessionId": "s1", "itemId": "i1"})
            assert wait_for(lambda: tracker.events_seen == 1)
            assert tracker.state == "idle"
            t[0] += 599.0
            assert tracker.state == "idle"
            t[0] += 1.0  # 600s of silence, no active turn
            assert tracker.state == "stalled"
            # Any event revives the clock.
            emit(host, "s1", "session/contextUsage",
                 {"sessionId": "s1", "pct": 1})
            assert wait_for(lambda: tracker.state == "idle")
        finally:
            unsub()
    finally:
        host.close()


def test_active_turn_never_stalls(view_serve):
    t = [2000.0]
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(
            host, "s1", stall_after=600.0, now=lambda: t[0])
        try:
            emit(host, "s1", "turn/started",
                 {"sessionId": "s1", "turnId": "t1"})
            assert wait_for(lambda: tracker.state == "working")
            t[0] += 3600.0  # an hour of silence, turn still active
            assert tracker.state == "working"
        finally:
            unsub()
    finally:
        host.close()


def test_tracker_validation():
    with pytest.raises(ValueError):
        mspv.JobStateTracker("")
    with pytest.raises(ValueError):
        mspv.JobStateTracker("s1", stall_after=0)
    with pytest.raises(ValueError):
        mspv.JobStateTracker("s1", stall_after=-5)
    with pytest.raises(ValueError):
        mspv.JobStateTracker("s1", now=42)
    # Pushing garbage never raises.
    tr = mspv.JobStateTracker("s1")
    tr.push(None)
    tr.push("not-a-dict")
    tr.push({"method": 42, "params": {}})
    assert tr.state == "idle"


def test_telemetry_ring_bounded(view_serve):
    host = open_host(view_serve)
    try:
        tracker, head, unsub = live_tracker(host, "s1")
        try:
            for i in range(150):
                emit(host, "s1", "session/contextUsage",
                     {"sessionId": "s1", "pct": i})
            assert wait_for(lambda: tracker.events_seen == 150)
            assert len(tracker.telemetry) == 100
            assert tracker.telemetry[-1][1]["pct"] == 149
        finally:
            unsub()
    finally:
        host.close()
