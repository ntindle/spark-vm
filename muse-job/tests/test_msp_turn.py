"""Hermetic tests for muse-job/bin/msp_turn.py (issue #223).

No `muse` binary is needed: every test drives a fake `muse serve`
fixture that speaks NDJSON JSON-RPC 2.0 over stdio and implements the
turn plane (turn/start|steer|interrupt|cancel) with the wire shapes the
module documents -- UUIDv7 command ids, verbatim prompts, queued turns,
not-live refusals, turn events.

Fixture-invented behavior (documented in the module, NOT wire-verified):
a second turn/start while one runs queues; turn records carry
{turnId, sessionId, state, promptEcho}; view events
turn/started|steered|interrupted|cancelled fire on the plain method
names; not-turn-capable refusals use reasons turn_not_live /
no_active_turn / no_queued_turn; session ids starting "dead-" are
model-dead sessions that refuse every turn call.
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import threading
import time
import uuid

import pytest

BIN_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "msp_turn.py")


def load_mod(name="msp_turn_under_test"):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, BIN_PATH)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


mspt = load_mod()

# ---------------------------------------------------------------------------
# Fake `muse serve` with a turn plane. Per-session state is kept in memory
# (sessions auto-vivify on first turn call; the session plane itself is
# #222's fixture -- here only the turn plane matters).
# ---------------------------------------------------------------------------
FAKE_TURN_SERVE = (
    "#!/usr/bin/env python3\n"
    + r'''
import argparse, json, os, sys, uuid

ap = argparse.ArgumentParser()
ap.add_argument("--record", default=None)
args = ap.parse_args()

rec = open(args.record, "a") if args.record else None
initialized = False

# sid -> {"active": turnId|None, "queued": [turnId], "turns": {turnId: rec}}
sessions = {}

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

UUID7_RE = __import__("re").compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

def sess(sid):
    return sessions.setdefault(
        sid, {"active": None, "queued": [], "turns": {}})

def not_live(rid, reason, msg):
    err(rid, -32030, msg, {"kind": "commandRejected", "reason": reason})

def check_drift(rid, params):
    # Test-only: a "drift:<case>" sessionId makes the fixture answer with
    # a malformed result so the client's fail-loud handling is exercised
    # end to end. The real wire never sees these ids.
    sid = params.get("sessionId")
    if not (isinstance(sid, str) and sid.startswith("drift:")):
        return False
    case = sid[len("drift:"):]
    if case == "notdict":
        send({"jsonrpc": "2.0", "id": rid, "result": "not-a-dict"})
    elif case == "no-turn":
        send({"jsonrpc": "2.0", "id": rid, "result": {"ok": True}})
    elif case == "no-turnid":
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"turn": {"state": "running"}}})
    else:
        return False
    return True

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
    sid = params.get("sessionId")
    if isinstance(sid, str) and sid.startswith("dead-"):
        # Fixture sentinel: a session whose model died on a stream idle
        # timeout (the #223 open-question state) -- the fake wire refuses
        # every turn call rather than pretending.
        not_live(rid, "turn_not_live",
                 "session has no live turn (model dead)")
        continue
    if isinstance(sid, str) and sid.startswith("err-weird-"):
        # Fixture sentinel: a refusal with a reason the client does not
        # map -- must surface as plain MSPTurnError, not TurnNotLiveError.
        err(rid, -32000, "boom", {"reason": "something_else"})
        continue
    if method == "turn/start":
        if check_drift(rid, params):
            continue
        cid = params.get("commandId")
        if not isinstance(cid, str) or not UUID7_RE.match(cid):
            err(rid, -32602,
                "invalid turn/start commandId: expected UUIDv7",
                {"kind": "invalidParams"})
            continue
        inp = params.get("input")
        if not isinstance(inp, list) or not inp:
            err(rid, -32602,
                "invalid turn/start params: missing field `input`",
                {"kind": "invalidParams"})
            continue
        s = sess(sid)
        tid = "turn-" + uuid.uuid4().hex[:12]
        state = "running" if s["active"] is None else "queued"
        trec = {"turnId": tid, "sessionId": sid, "state": state,
                "promptEcho": (inp[0].get("text") if isinstance(inp[0], dict)
                               else None)}
        s["turns"][tid] = trec
        if state == "running":
            s["active"] = tid
        else:
            s["queued"].append(tid)
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"commandId": cid, "disposition": "started",
                         "startedNewTurn": True, "status": state,
                         "turnId": tid}})
        notify("turn/started", {"sessionId": sid, "turnId": tid})
    elif method == "turn/steer":
        if check_drift(rid, params):
            continue
        cid = params.get("commandId")
        if not isinstance(cid, str) or not UUID7_RE.match(cid):
            err(rid, -32602,
                "invalid turn/steer commandId: expected UUIDv7",
                {"kind": "invalidParams"})
            continue
        inp = params.get("input")
        if not isinstance(inp, list) or not inp:
            err(rid, -32602,
                "invalid turn/steer params: missing field `input`",
                {"kind": "invalidParams"})
            continue
        if not params.get("expectedTurnId"):
            err(rid, -32602,
                "invalid turn/steer params: missing field `expectedTurnId`",
                {"kind": "invalidParams"})
            continue
        s = sess(sid)
        tid = s["active"]
        if tid is None:
            not_live(rid, "no_active_turn",
                     "no active turn to steer into")
            continue
        trec = s["turns"][tid]
        trec.setdefault("injected", []).append(
            inp[0].get("text") if isinstance(inp[0], dict) else None)
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"commandId": cid, "status": trec["state"],
                         "turnId": tid}})
        notify("turn/steered", {"sessionId": sid, "turnId": tid})
    elif method == "turn/interrupt":
        if check_drift(rid, params):
            continue
        s = sess(sid)
        tid = params.get("turnId") or s["active"]
        if tid is None or s["turns"].get(tid) is None \
                or s["turns"][tid]["state"] != "running":
            not_live(rid, "no_active_turn",
                     "no active turn to interrupt")
            continue
        trec = s["turns"][tid]
        trec["state"] = "interrupted"
        s["active"] = None
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"commandId": cid, "status": "interrupted",
                         "turnId": tid}})
        notify("turn/interrupted", {"sessionId": sid, "turnId": tid})
        if s["queued"]:
            promoted = s["queued"].pop(0)
            s["turns"][promoted]["state"] = "running"
            s["active"] = promoted
            notify("turn/started",
                   {"sessionId": sid, "turnId": promoted})
    elif method == "turn/cancel":
        if check_drift(rid, params):
            continue
        s = sess(sid)
        tid = params.get("turnId")
        if tid is not None and tid not in s["queued"]:
            not_live(rid, "no_queued_turn",
                     "no such queued turn")
            continue
        if tid is None:
            if not s["queued"]:
                not_live(rid, "no_queued_turn",
                         "no queued turn to cancel")
                continue
            tid = s["queued"].pop(0)
        else:
            s["queued"].remove(tid)
        trec = s["turns"][tid]
        trec["state"] = "cancelled"
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"commandId": cid, "status": "cancelled",
                         "turnId": tid}})
        notify("turn/cancelled", {"sessionId": sid, "turnId": tid})
    else:
        err(rid, -32601, "unknown method")
''')


def _write_turn_serve(tmp_path):
    """Write the turn-plane fixture; return (argv, record)."""
    path = tmp_path / "fake_turn_serve.py"
    path.write_text(FAKE_TURN_SERVE)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    record = tmp_path / "record.jsonl"
    argv = [sys.executable, str(path), "--record", str(record)]
    return argv, record


@pytest.fixture()
def turn_serve(tmp_path):
    """Write the turn-plane fixture; return (argv, record)."""
    return _write_turn_serve(tmp_path)


def read_record(record):
    if not os.path.exists(str(record)):
        return []
    return [json.loads(l) for l in open(str(record)) if l.strip()]


def make_host(argv, **kw):
    kw.setdefault("client_name", "test_client")
    kw.setdefault("request_timeout", 5.0)
    return mspt.MSPHost(argv, **kw)


def wait_until(pred, timeout=10.0, step=0.05):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(step)
    return False


def method_calls(record, method):
    return [m for m in read_record(record) if m.get("method") == method]


UUID7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


# -- turn/start -------------------------------------------------------------

def test_start_minimal_wire_shape(turn_serve):
    argv, record = turn_serve
    with make_host(argv) as host:
        turn, result = mspt.start_turn(host, "sess-a", "run the tests")
    calls = method_calls(record, "turn/start")
    assert len(calls) == 1
    params = calls[0]["params"]
    assert params["sessionId"] == "sess-a"
    # prompt-as-argv: the prompt travels as one opaque text part in the
    # input array (serve schema 1.4.x; the old `prompt` string field is
    # rejected with invalid params).
    assert params["input"] == [{"type": "text", "text": "run the tests"}]
    assert UUID7_RE.match(params["commandId"])
    assert turn["turnId"]
    assert turn["status"] == "running"
    assert result["turnId"] == turn["turnId"]


PROMPT_WITH_METACHARS = (
    "  leading spaces\nline two with $(command substitution) and `backticks`\n"
    "; rm -rf / # \"quoted\" 'single' \\ backslash\n"
    "\ttab-indented\ntrailing spaces  \n"
)


def test_start_prompt_verbatim_metachars(turn_serve):
    """The #211-killer property: no shell ever sees the prompt."""
    argv, record = turn_serve
    with make_host(argv) as host:
        turn, _ = mspt.start_turn(host, "sess-meta", PROMPT_WITH_METACHARS)
    params = method_calls(record, "turn/start")[0]["params"]
    assert params["input"] == [{"type": "text", "text": PROMPT_WITH_METACHARS}]


def test_steer_message_verbatim_metachars(turn_serve):
    argv, record = turn_serve
    with make_host(argv) as host:
        turn, _ = mspt.start_turn(host, "sess-s", "go")
        mspt.steer_turn(host, "sess-s", PROMPT_WITH_METACHARS,
                        expected_turn_id=turn["turnId"])
    params = method_calls(record, "turn/steer")[0]["params"]
    assert params["input"] == [{"type": "text", "text": PROMPT_WITH_METACHARS}]
    assert params["expectedTurnId"] == turn["turnId"]


def test_start_queues_when_turn_running(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        first, _ = mspt.start_turn(host, "sess-q", "first")
        second, _ = mspt.start_turn(host, "sess-q", "second")
    assert first["status"] == "running"
    assert second["status"] == "queued"
    assert first["turnId"] != second["turnId"]


def test_start_rejects_blank_prompt(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(ValueError):
            mspt.start_turn(host, "sess-x", "   ")
        with pytest.raises(ValueError):
            mspt.start_turn(host, "sess-x", "")
        with pytest.raises(ValueError):
            mspt.start_turn(host, "", "go")
        with pytest.raises(ValueError):
            mspt.start_turn(host, "sess-x", 42)


def test_start_rejects_bool_prompt(turn_serve):
    # True/False are rejected by the isinstance check itself (bool is not a
    # str subclass) -- no special case needed. Pins the behavior the removed
    # unreachable `isinstance(text, bool)` branch used to claim.
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(ValueError):
            mspt.start_turn(host, "sess-x", True)
        with pytest.raises(ValueError):
            mspt.steer_turn(host, "sess-x", False)


def test_start_rejects_bad_command_id(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(ValueError):
            mspt.start_turn(host, "sess-x", "go", command_id="not-a-uuid")


def test_caller_command_id_used_verbatim(turn_serve):
    argv, record = turn_serve
    cid = mspt.new_command_id()
    with make_host(argv) as host:
        turn_c, _ = mspt.start_turn(host, "sess-c", "go", command_id=cid)
        mspt.steer_turn(host, "sess-c", "more", command_id=mspt.new_command_id(),
                        expected_turn_id=turn_c["turnId"])
    calls = method_calls(record, "turn/start") + method_calls(record, "turn/steer")
    assert calls[0]["params"]["commandId"] == cid
    assert calls[1]["params"]["commandId"] != cid


def test_new_command_id_is_uuid7():
    a, b = mspt.new_command_id(), mspt.new_command_id()
    assert UUID7_RE.match(a) and UUID7_RE.match(b) and a != b


# -- turn/steer ---------------------------------------------------------------

def test_steer_injects_into_active_turn(turn_serve):
    argv, record = turn_serve
    with make_host(argv) as host:
        turn, _ = mspt.start_turn(host, "sess-st", "go")
        steered, result = mspt.steer_turn(host, "sess-st", "keep going",
                                          expected_turn_id=turn["turnId"])
    params = method_calls(record, "turn/steer")[0]["params"]
    assert params["sessionId"] == "sess-st"
    assert params["input"] == [{"type": "text", "text": "keep going"}]
    assert params["expectedTurnId"] == turn["turnId"]
    assert UUID7_RE.match(params["commandId"])
    assert steered["turnId"] == turn["turnId"]
    assert result["turnId"] == turn["turnId"]


def test_steer_needs_live_turn_not_silent(turn_serve):
    """A fresh session has no active turn: steer must fail loud, not land."""
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(mspt.TurnNotLiveError) as ei:
            mspt.steer_turn(host, "sess-fresh", "hello?",
                            expected_turn_id="turn-missing")
    assert "226" in str(ei.value)  # the not-live error names the owner


def test_steer_dead_session_raises_not_live(turn_serve):
    """The #223 open-question state, fixture-modeled: no resurrection."""
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(mspt.TurnNotLiveError):
            mspt.steer_turn(host, "dead-trackball-parked", "wake up",
                            expected_turn_id="turn-gone")
        with pytest.raises(mspt.TurnNotLiveError):
            mspt.start_turn(host, "dead-trackball-parked", "wake up")
        with pytest.raises(mspt.TurnNotLiveError):
            mspt.interrupt_turn(host, "dead-trackball-parked")


def test_unmapped_refusal_stays_plain_server_error(turn_serve):
    """A refusal with an unknown reason is still fail-loud, not mislabeled."""
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(mspt.ServerError) as ei:
            mspt.steer_turn(host, "err-weird-boom", "x",
                            expected_turn_id="turn-x")
    assert not isinstance(ei.value, mspt.TurnNotLiveError)
    assert ei.value.data.get("reason") == "something_else"


# -- turn/interrupt -----------------------------------------------------------

def test_interrupt_stops_active_turn(turn_serve):
    argv, record = turn_serve
    with make_host(argv) as host:
        turn, _ = mspt.start_turn(host, "sess-i", "long task")
        result = mspt.interrupt_turn(host, "sess-i")
    params = method_calls(record, "turn/interrupt")[0]["params"]
    assert params["sessionId"] == "sess-i"
    assert "turnId" not in params  # omitted: act on the active turn
    assert result["turnId"] == turn["turnId"]
    assert result["status"] == "interrupted"


def test_interrupt_promotes_queued_turn(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        first, _ = mspt.start_turn(host, "sess-p", "first")
        second, _ = mspt.start_turn(host, "sess-p", "second")
        mspt.interrupt_turn(host, "sess-p")
        # The queued turn is now the active one: steering lands on it.
        steered, _ = mspt.steer_turn(host, "sess-p", "go on",
                                     expected_turn_id=second["turnId"])
    assert steered["turnId"] == second["turnId"]


def test_interrupt_no_active_turn_raises_not_live(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(mspt.TurnNotLiveError):
            mspt.interrupt_turn(host, "sess-empty")


def test_interrupt_scoped_turn_id(turn_serve):
    argv, record = turn_serve
    with make_host(argv) as host:
        turn, _ = mspt.start_turn(host, "sess-is", "go")
        mspt.interrupt_turn(host, "sess-is", turn_id=turn["turnId"])
    params = method_calls(record, "turn/interrupt")[0]["params"]
    assert params["turnId"] == turn["turnId"]


def test_interrupt_bad_turn_id_rejected_client_side(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(ValueError):
            mspt.interrupt_turn(host, "sess-x", turn_id="")


# -- turn/cancel ----------------------------------------------------------------

def test_cancel_queued_turn(turn_serve):
    argv, record = turn_serve
    with make_host(argv) as host:
        first, _ = mspt.start_turn(host, "sess-cx", "first")
        second, _ = mspt.start_turn(host, "sess-cx", "second")
        result = mspt.cancel_turn(host, "sess-cx")
    assert result["turnId"] == second["turnId"]
    assert result["status"] == "cancelled"
    # The running turn is untouched.
    params = method_calls(record, "turn/cancel")[0]["params"]
    assert params["sessionId"] == "sess-cx"


def test_cancel_scoped_turn_id(turn_serve):
    argv, record = turn_serve
    with make_host(argv) as host:
        _, _ = mspt.start_turn(host, "sess-cs", "first")
        second, _ = mspt.start_turn(host, "sess-cs", "second")
        mspt.cancel_turn(host, "sess-cs", turn_id=second["turnId"])
    params = method_calls(record, "turn/cancel")[0]["params"]
    assert params["turnId"] == second["turnId"]


def test_cancel_no_queued_turn_raises_not_live(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        turn, _ = mspt.start_turn(host, "sess-cq", "only")
        with pytest.raises(mspt.TurnNotLiveError):
            mspt.cancel_turn(host, "sess-cq")  # nothing queued
        with pytest.raises(mspt.TurnNotLiveError):
            mspt.cancel_turn(host, "sess-cq", turn_id="turn-nope")


def test_cancel_running_turn_id_raises_not_live(turn_serve):
    # cancel only drops QUEUED turns: cancelling the running turn's id is a
    # not-live refusal, not a silent success.
    argv, _ = turn_serve
    with make_host(argv) as host:
        turn, _ = mspt.start_turn(host, "sess-cr", "go")
        with pytest.raises(mspt.TurnNotLiveError):
            mspt.cancel_turn(host, "sess-cr", turn_id=turn["turnId"])


# -- fail-loud on drift ---------------------------------------------------------

@pytest.mark.parametrize("case", ["notdict", "no-turn", "no-turnid"])
def test_turn_plane_fails_loud_on_drift_end_to_end(turn_serve, case):
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(mspt.MSPTurnError):
            mspt.start_turn(host, "drift:" + case, "go")
        with pytest.raises(mspt.MSPTurnError):
            mspt.steer_turn(host, "drift:" + case, "go",
                            expected_turn_id="turn-x")
        with pytest.raises(mspt.MSPTurnError):
            mspt.interrupt_turn(host, "drift:" + case)
        with pytest.raises(mspt.MSPTurnError):
            mspt.cancel_turn(host, "drift:" + case)


# -- _raise_for_not_live mapping pins --------------------------------------------

def test_raise_for_not_live_none_data_reraises_original():
    # A server error with data=None is not a not-live reason: the original
    # error must surface unchanged, never relabeled TurnNotLiveError.
    orig = mspt.ServerError(-32000, "boom", None)
    with pytest.raises(mspt.ServerError) as excinfo:
        mspt._raise_for_not_live(orig, "sess-x", "turn/steer")
    assert excinfo.value is orig


def test_raise_for_not_live_unmapped_data_reraises_original():
    for data in ({}, {"kind": "x"}, {"reason": "something_else"},
                 "not-a-dict", ["reason"]):
        orig = mspt.ServerError(-32000, "boom", data)
        with pytest.raises(mspt.ServerError) as excinfo:
            mspt._raise_for_not_live(orig, "sess-x", "turn/steer")
        assert excinfo.value is orig
        assert not isinstance(excinfo.value, mspt.TurnNotLiveError)


@pytest.mark.parametrize("reason", ["turn_not_live", "no_active_turn",
                                    "no_queued_turn"])
def test_raise_for_not_live_mapped_reasons(reason):
    err = mspt.ServerError(-32030, "nope",
                           {"kind": "commandRejected", "reason": reason})
    with pytest.raises(mspt.TurnNotLiveError):
        mspt._raise_for_not_live(err, "sess-x", "turn/steer")


# -- turn events (the #223 acceptance) --------------------------------------------

def test_turn_start_observable_via_events(turn_serve):
    """Steer a prompt into a live session and observe the turn via events."""
    argv, _ = turn_serve
    seen = []
    with make_host(argv) as host:
        unsub = host.subscribe("turn", seen.append)
        try:
            turn, _ = mspt.start_turn(host, "sess-ev", "go")
            steered, _ = mspt.steer_turn(host, "sess-ev", "more",
                                         expected_turn_id=turn["turnId"])
            assert wait_until(
                lambda: sum(1 for n in seen
                            if n.get("method") == "turn/steered") >= 1)
        finally:
            unsub()
    methods = [n.get("method") for n in seen]
    assert "turn/started" in methods
    assert "turn/steered" in methods
    for n in seen:
        assert (n.get("params") or {}).get("sessionId") == "sess-ev"
    assert steered["turnId"] == turn["turnId"]


def test_watch_turn_events_collects_until_terminal(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        turn, _ = mspt.start_turn(host, "sess-w", "go")
        tid = turn["turnId"]

        def interrupt_later():
            time.sleep(0.3)
            mspt.interrupt_turn(host, "sess-w")

        t = threading.Thread(target=interrupt_later, daemon=True)
        t.start()
        events = mspt.watch_turn_events(host, "sess-w", tid, timeout=10.0)
        t.join()
    terminal = [n for n in events
                if n.get("method") in ("turn/completed",
                                       "turn/interrupted",
                                       "turn/cancelled")]
    assert terminal, f"no terminal event in {[n.get('method') for n in events]}"
    assert terminal[0]["method"] == "turn/interrupted"
    assert terminal[0]["params"]["turnId"] == tid


# -- turn events: filter branches (stub host, deterministic) -------------------

class _StubWatchHost:
    """Minimal host double for watch_turn_events: captures the subscriber.

    Feeding notifications straight to the captured callback pins the
    filter branches deterministically, without transport timing.
    """
    def __init__(self):
        self.callback = None

    def subscribe(self, prefix, callback):
        assert prefix == "turn"
        self.callback = callback
        return lambda: None


def _watch_with_notes(notes, terminal_note, session_id="sess-x",
                      turn_id="turn-x", timeout=5.0):
    """Run watch_turn_events against the stub host, feed it `notes` then the
    terminal note (or none), and return the collected events."""
    host = _StubWatchHost()
    box = {}

    def run():
        box["events"] = mspt.watch_turn_events(
            host, session_id, turn_id, timeout=timeout)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    assert wait_until(lambda: host.callback is not None), \
        "watch_turn_events never subscribed"
    for note in notes:
        host.callback(note)
    if terminal_note is not None:
        host.callback(terminal_note)
    t.join(timeout + 10)
    assert not t.is_alive(), "watch_turn_events did not return"
    return box["events"]


def _note(method, params):
    return {"jsonrpc": "2.0", "method": method, "params": params}


def test_watch_filters_other_session_events():
    notes = [
        _note("turn/started", {"sessionId": "sess-other", "turnId": "turn-x"}),
        _note("turn/started", {"sessionId": "sess-x", "turnId": "turn-x"}),
    ]
    term = _note("turn/completed", {"sessionId": "sess-x", "turnId": "turn-x"})
    events = _watch_with_notes(notes, term)
    got = [(n["method"], n["params"]["sessionId"]) for n in events]
    assert ("turn/started", "sess-other") not in got
    assert ("turn/started", "sess-x") in got
    assert got[-1] == ("turn/completed", "sess-x")


def test_watch_without_session_filter_collects_all():
    # session_id=None disables filtering: every notification is collected.
    notes = [
        _note("turn/started", {"sessionId": "sess-a", "turnId": "turn-x"}),
        _note("turn/steered", {"sessionId": "sess-b", "turnId": "turn-x"}),
    ]
    term = _note("turn/cancelled", {"sessionId": "sess-b", "turnId": "turn-x"})
    events = _watch_with_notes(notes, term, session_id=None)
    assert [n["method"] for n in events] == [
        "turn/started", "turn/steered", "turn/cancelled"]


def test_watch_ignores_malformed_notification_params():
    # Missing, null, and non-dict params must not raise on the reader
    # thread. (Non-vacuous: the old `note.get("params") or {}` idiom raised
    # AttributeError on the non-dict cases inside the host's dispatcher.)
    notes = [
        {"jsonrpc": "2.0", "method": "turn/started"},      # params missing
        _note("turn/steered", None),                      # params null
        _note("turn/steered", "oops"),                    # non-dict params
        _note("turn/steered", ["x"]),                     # non-dict params
        _note("turn/started", {"sessionId": "sess-x", "turnId": "turn-x"}),
    ]
    term = _note("turn/interrupted",
                {"sessionId": "sess-x", "turnId": "turn-x"})
    events = _watch_with_notes(notes, term)
    # The four malformed notes carried no sessionId, so the session filter
    # dropped them; the point is they were dropped, not raised.
    assert [n["method"] for n in events] == [
        "turn/started", "turn/interrupted"]
    # And with filtering off, malformed notes are collected, still unraised:
    events = _watch_with_notes(notes, term, session_id=None)
    assert len(events) == 6


def test_watch_ignores_terminal_event_for_other_turn():
    # A terminal event for a different turnId must not end the watch: the
    # watch runs to its timeout instead of stopping early.
    notes = [_note("turn/interrupted",
                   {"sessionId": "sess-x", "turnId": "turn-other"})]
    t0 = time.time()
    events = _watch_with_notes(notes, None, timeout=0.6)
    elapsed = time.time() - t0
    assert [n["method"] for n in events] == ["turn/interrupted"]
    assert elapsed >= 0.5, "watch returned early: %.2fs" % elapsed


# -- smoke CLI --------------------------------------------------------------------

def _run_cli(*args):
    return subprocess.run(
        [sys.executable, BIN_PATH, *args],
        capture_output=True, text=True, timeout=30)


def test_smoke_cli_start(turn_serve):
    argv, _ = turn_serve
    out = _run_cli("start", "--session-id", "sess-cli2",
                   "--prompt", "hello", "--", *argv)
    assert out.returncode == 0, out.stderr
    body = json.loads(out.stdout)
    assert body["turn"]["status"] == "running"
    assert body["turn"]["turnId"]


def test_smoke_cli_warns_not_redacted_on_stderr(turn_serve):
    argv, _ = turn_serve
    out = _run_cli("start", "--session-id", "sess-w2",
                   "--prompt", "x", "--", *argv)
    assert out.returncode == 0, out.stderr
    assert "NOT redacted" in out.stderr


def test_smoke_cli_watch_observes_events(turn_serve):
    argv, _ = turn_serve
    # --watch is a main-parser flag: it goes before the subcommand (the
    # subparser's REMAINDER swallows everything after it).
    out = _run_cli("--watch", "--watch-timeout", "1.0",
                   "start", "--session-id", "sess-w3",
                   "--prompt", "x", "--", *argv)
    assert out.returncode == 0, out.stderr
    body = json.loads(out.stdout)
    assert "watchedEvents" in body
    methods = [n.get("method") for n in body["watchedEvents"]]
    # The fixture emits turn/started for our own call; the subscriber
    # attaches after the call, so this pins the mechanism, not the race.
    assert isinstance(methods, list)


def test_smoke_cli_needs_serve_argv():
    out = _run_cli("steer", "--session-id", "s", "--message", "m",
                   "--turn-id", "t")
    assert out.returncode != 0
    assert "serve argv" in out.stderr


# -- smoke CLI: --watch plumbing (MSPHost doubled) ---------------------------------
#
# These two pin main()'s --watch plumbing, which the hermetic fixture cannot
# reach: interrupt/cancel against the fixture always fail (no pre-existing
# session survives across fixture processes), so a doubled host stands in
# for the transport while the real main()/watch_turn_events run.


class _NoSubscribeHost:
    """MSPHost double: interrupt succeeds without a live serve host;
    subscribe must never be called (no turn id to watch)."""

    def __init__(self, serve, client_name="msp_turn"):
        self.serve = serve

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def call(self, method, params):
        assert method == "turn/interrupt"
        return {"turnId": "t-9", "status": "interrupted"}

    def subscribe(self, prefix, callback):
        raise AssertionError("subscribe called without a turn id to watch")


def test_smoke_cli_watch_without_turn_id_warns(monkeypatch, capsys):
    # --watch with interrupt/cancel and no --turn-id: the CLI warns on
    # stderr instead of watching nothing (or hanging).
    monkeypatch.setattr(mspt, "MSPHost", _NoSubscribeHost)
    rc = mspt.main(["--watch", "interrupt", "--session-id", "sess-x",
                    "--", "true"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "require --turn-id to watch" in captured.err
    assert "watchedEvents" not in captured.out


class _SilentWatchHost(_NoSubscribeHost):
    """Same, but subscribe captures the callback and never fires: the watch
    must return at its timeout, not hang."""

    def subscribe(self, prefix, callback):
        assert prefix == "turn"
        return lambda: None


def test_smoke_cli_watch_interrupt_with_turn_id_is_bounded(monkeypatch,
                                                           capsys):
    # interrupt --watch --turn-id: the terminal event fired during the call,
    # before the watcher subscribed, so the watch observes nothing -- but it
    # must return at the timeout rather than hang. (Pinning the current
    # honest behavior; see --watch help. Subscribing before the call is a
    # future #223 follow-up, not this change.)
    monkeypatch.setattr(mspt, "MSPHost", _SilentWatchHost)
    t0 = time.time()
    rc = mspt.main(["--watch", "--watch-timeout", "0.5", "interrupt",
                    "--session-id", "sess-x", "--turn-id", "t-9",
                    "--", "true"])
    elapsed = time.time() - t0
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["watchedEvents"] == []
    assert elapsed < 5, "watch did not return at its timeout: %.1fs" % elapsed


# -- await_first_turn_engagement (#994) ---------------------------------------

def _engage_with_notes(notes, *, session_id="sess-x", turn_id="turn-x",
                       timeout=5.0, pre_notes=()):
    """Run begin_first_turn_watch + await_first_turn_engagement against
    the stub host. `pre_notes` are fed after subscribing but before the
    turn id is bound -- the subscribe gap that #994's ~1ms cancellation
    falls into. `notes` are fed while the await runs."""
    host = _StubWatchHost()
    watch = mspt.begin_first_turn_watch(host, session_id)
    assert host.callback is not None, "begin_first_turn_watch never subscribed"
    for note in pre_notes:
        host.callback(note)
    box = {}

    def run():
        box["eng"] = mspt.await_first_turn_engagement(
            watch, turn_id, timeout=timeout)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    for note in notes:
        host.callback(note)
    t.join(timeout + 10)
    assert not t.is_alive(), "await_first_turn_engagement did not return"
    return box["eng"]


def _stillborn_journal():
    # The real #994 signal journal: the serve host emits turn/completed
    # with a terminal param (NOT the fixture's method-level
    # turn/cancelled).
    return [
        _note("turn/started", {"sessionId": "sess-x", "turnId": "turn-x"}),
        _note("item/completed", {"sessionId": "sess-x", "turnId": "turn-x",
                                 "item": "userMessage"}),
        _note("item/started", {"sessionId": "sess-x", "turnId": "turn-x",
                               "item": "reminderChild"}),
        _note("item/completed", {"sessionId": "sess-x", "turnId": "turn-x",
                                 "item": "reminderChild"}),
        _note("turn/completed", {"sessionId": "sess-x", "turnId": "turn-x",
                                 "terminal": "cancelled"}),
    ]


def test_engagement_detects_stillborn_via_terminal_param():
    eng = _engage_with_notes(_stillborn_journal())
    assert eng["status"] == "dead"
    assert eng["terminal"] == "cancelled"
    assert eng["journal"] == ["turn/started", "item/completed",
                              "item/started", "item/completed",
                              "turn/completed"]
    assert eng["elapsed_s"] < 5.0


def test_engagement_detects_stillborn_via_method_level_cancel():
    notes = [_note("turn/cancelled",
                   {"sessionId": "sess-x", "turnId": "turn-x"})]
    eng = _engage_with_notes(notes)
    assert eng["status"] == "dead"
    assert eng["terminal"] == "cancelled"


def test_engagement_detects_stillborn_interrupt_and_failed():
    for method, params, terminal in (
            ("turn/interrupted", {"sessionId": "sess-x", "turnId": "turn-x"},
             "interrupted"),
            ("turn/completed", {"sessionId": "sess-x", "turnId": "turn-x",
                                "terminal": "failed"}, "failed")):
        eng = _engage_with_notes([_note(method, params)])
        assert eng["status"] == "dead", method
        assert eng["terminal"] == terminal, method


def test_engagement_completed_turn_is_done_not_dead():
    for params in ({"sessionId": "sess-x", "turnId": "turn-x",
                   "terminal": "completed"},
                  {"sessionId": "sess-x", "turnId": "turn-x"}):
        eng = _engage_with_notes([_note("turn/completed", params)])
        assert eng["status"] == "done", params
        assert eng["terminal"] == "completed", params


def test_engagement_running_turn_reports_engaged_at_timeout():
    notes = [_note("turn/started", {"sessionId": "sess-x", "turnId": "turn-x"})]
    t0 = time.time()
    eng = _engage_with_notes(notes, timeout=0.4)
    elapsed = time.time() - t0
    assert eng["status"] == "engaged"
    assert eng["terminal"] is None
    assert eng["journal"] == ["turn/started"]
    assert elapsed >= 0.3, "returned before the timeout: %.2fs" % elapsed


def test_engagement_ignores_other_turn_and_malformed_notes():
    notes = [
        {"jsonrpc": "2.0", "method": "turn/started"},       # params missing
        _note("turn/steered", None),                        # params null
        _note("turn/steered", "oops"),                      # non-dict params
        _note("turn/started", {"sessionId": "sess-other",   # other session
                               "turnId": "turn-x"}),
        _note("turn/cancelled", {"sessionId": "sess-x",     # other turn
                                 "turnId": "turn-other"}),
        _note("turn/started", {"sessionId": "sess-x", "turnId": "turn-x"}),
    ]
    t0 = time.time()
    eng = _engage_with_notes(notes, timeout=0.4)
    assert eng["status"] == "engaged"
    assert eng["journal"] == ["turn/cancelled", "turn/started"]
    assert time.time() - t0 >= 0.3


def test_engagement_rejects_bad_arguments():
    host = _StubWatchHost()
    watch = mspt.begin_first_turn_watch(host, "sess-x")
    with pytest.raises(ValueError):
        mspt.begin_first_turn_watch(host, "")
    with pytest.raises(ValueError):
        mspt.await_first_turn_engagement(watch, "")
    with pytest.raises(ValueError):
        mspt.await_first_turn_engagement(watch, "turn-x", timeout=0)
    with pytest.raises(ValueError):
        mspt.await_first_turn_engagement({}, "turn-x")
    mspt.close_first_turn_watch(watch)


def test_begin_watch_closes_subscribe_gap():
    # The #994 timeline: the server cancels ~1ms after turn/start --
    # before the caller could possibly hold the turn id. The terminal
    # arrives while only the pre-start subscription exists; the await
    # binds the turn id later and must still catch it via replay.
    host = _StubWatchHost()
    watch = mspt.begin_first_turn_watch(host, "sess-x")
    host.callback(_note("turn/completed", {"sessionId": "sess-x",
                                           "turnId": "turn-x",
                                           "terminal": "cancelled"}))
    eng = mspt.await_first_turn_engagement(watch, "turn-x", timeout=5.0)
    assert eng["status"] == "dead"
    assert eng["terminal"] == "cancelled"
    assert eng["journal"] == ["turn/completed"]


def test_close_first_turn_watch_releases_subscriber():
    host = _StubWatchHost()
    released = []
    real_subscribe = host.subscribe

    def tracking_subscribe(prefix, callback):
        unsub = real_subscribe(prefix, callback)

        def tracking_unsub():
            released.append(True)
            return unsub()

        return tracking_unsub

    host.subscribe = tracking_subscribe
    watch = mspt.begin_first_turn_watch(host, "sess-x")
    mspt.close_first_turn_watch(watch)
    assert released == [True]
    with pytest.raises(ValueError):
        mspt.close_first_turn_watch({"nope": True})


def test_turn_stillborn_error_carries_diagnostics():
    err = mspt.TurnStillbornError("boom", turn_id="turn-x",
                                  terminal="cancelled",
                                  journal=["turn/started", "turn/completed"])
    assert isinstance(err, mspt.MSPTurnError)
    assert err.turn_id == "turn-x"
    assert err.terminal == "cancelled"
    assert err.journal == ("turn/started", "turn/completed")
    assert "boom" in str(err)


def test_engagement_unknown_terminal_fails_closed():
    # An unrecognized terminal means the turn ended in a way the
    # client doesn't understand: fail closed (dead), never guess it
    # was a successful engagement. The raw string is preserved
    # in-memory for debugging; emission boundaries gate it via
    # _terminal_label.
    eng = _engage_with_notes([_note(
        "turn/completed", {"sessionId": "sess-x", "turnId": "turn-x",
                           "terminal": "evaporated"})])
    assert eng["status"] == "dead"
    assert eng["terminal"] == "evaporated"
    assert mspt._terminal_label(eng["terminal"]) == "unknown"


def test_terminal_label_vocabulary_gate():
    # Server-controlled terminal strings must never reach logs or
    # job.json verbatim: log injection (embedded newlines) and
    # unbounded input are gated to "unknown" at the emission boundary.
    assert mspt._terminal_label("cancelled") == "cancelled"
    assert mspt._terminal_label("interrupted") == "interrupted"
    assert mspt._terminal_label("failed") == "failed"
    assert mspt._terminal_label("completed") == "completed"
    assert mspt._terminal_label("cancelled\nINJECTED: pwned") == "unknown"
    assert mspt._terminal_label("x" * 1000000) == "unknown"
    assert mspt._terminal_label("") == "unknown"
    assert mspt._terminal_label(None) == "unknown"
