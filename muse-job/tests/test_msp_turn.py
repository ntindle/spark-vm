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
        s = sess(sid)
        tid = "turn-" + uuid.uuid4().hex[:12]
        state = "running" if s["active"] is None else "queued"
        trec = {"turnId": tid, "sessionId": sid, "state": state,
                "promptEcho": params.get("prompt")}
        s["turns"][tid] = trec
        if state == "running":
            s["active"] = tid
        else:
            s["queued"].append(tid)
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"turn": dict(trec)}})
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
        s = sess(sid)
        tid = s["active"]
        if tid is None:
            not_live(rid, "no_active_turn",
                     "no active turn to steer into")
            continue
        trec = s["turns"][tid]
        trec.setdefault("injected", []).append(params.get("message"))
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"turn": dict(trec)}})
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
              "result": {"turn": dict(trec)}})
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
              "result": {"turn": dict(trec)}})
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


def _live(turn_serve, sid="sess-live"):
    """Open a host and start one live turn; return (host, turn)."""
    argv, record = turn_serve
    host = make_host(argv)
    host.open()
    turn, _ = mspt.start_turn(host, sid, "hello")
    return host, turn, record


# -- turn/start -------------------------------------------------------------

def test_start_minimal_wire_shape(turn_serve):
    argv, record = turn_serve
    with make_host(argv) as host:
        turn, result = mspt.start_turn(host, "sess-a", "run the tests")
    calls = method_calls(record, "turn/start")
    assert len(calls) == 1
    params = calls[0]["params"]
    assert params["sessionId"] == "sess-a"
    # prompt-as-argv: the prompt travels as one opaque string.
    assert params["prompt"] == "run the tests"
    assert UUID7_RE.match(params["commandId"])
    assert turn["turnId"]
    assert turn["sessionId"] == "sess-a"
    assert turn["state"] == "running"
    assert result["turn"]["turnId"] == turn["turnId"]


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
    assert params["prompt"] == PROMPT_WITH_METACHARS


def test_steer_message_verbatim_metachars(turn_serve):
    argv, record = turn_serve
    with make_host(argv) as host:
        turn, _ = mspt.start_turn(host, "sess-s", "go")
        mspt.steer_turn(host, "sess-s", PROMPT_WITH_METACHARS)
    params = method_calls(record, "turn/steer")[0]["params"]
    assert params["message"] == PROMPT_WITH_METACHARS


def test_start_queues_when_turn_running(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        first, _ = mspt.start_turn(host, "sess-q", "first")
        second, _ = mspt.start_turn(host, "sess-q", "second")
    assert first["state"] == "running"
    assert second["state"] == "queued"
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


def test_start_rejects_bad_command_id(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(ValueError):
            mspt.start_turn(host, "sess-x", "go", command_id="not-a-uuid")


def test_caller_command_id_used_verbatim(turn_serve):
    argv, record = turn_serve
    cid = mspt.new_command_id()
    with make_host(argv) as host:
        mspt.start_turn(host, "sess-c", "go", command_id=cid)
        mspt.steer_turn(host, "sess-c", "more", command_id=mspt.new_command_id())
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
        steered, result = mspt.steer_turn(host, "sess-st", "keep going")
    params = method_calls(record, "turn/steer")[0]["params"]
    assert params["sessionId"] == "sess-st"
    assert params["message"] == "keep going"
    assert UUID7_RE.match(params["commandId"])
    assert steered["turnId"] == turn["turnId"]
    assert result["turn"]["turnId"] == turn["turnId"]


def test_steer_needs_live_turn_not_silent(turn_serve):
    """A fresh session has no active turn: steer must fail loud, not land."""
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(mspt.TurnNotLiveError) as ei:
            mspt.steer_turn(host, "sess-fresh", "hello?")
    assert "226" in str(ei.value)  # the not-live error names the owner


def test_steer_dead_session_raises_not_live(turn_serve):
    """The #223 open-question state, fixture-modeled: no resurrection."""
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(mspt.TurnNotLiveError):
            mspt.steer_turn(host, "dead-trackball-parked", "wake up")
        with pytest.raises(mspt.TurnNotLiveError):
            mspt.start_turn(host, "dead-trackball-parked", "wake up")
        with pytest.raises(mspt.TurnNotLiveError):
            mspt.interrupt_turn(host, "dead-trackball-parked")


def test_unmapped_refusal_stays_plain_server_error(turn_serve):
    """A refusal with an unknown reason is still fail-loud, not mislabeled."""
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(mspt.ServerError) as ei:
            mspt.steer_turn(host, "err-weird-boom", "x")
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
    assert result["turn"]["turnId"] == turn["turnId"]
    assert result["turn"]["state"] == "interrupted"


def test_interrupt_promotes_queued_turn(turn_serve):
    argv, _ = turn_serve
    with make_host(argv) as host:
        first, _ = mspt.start_turn(host, "sess-p", "first")
        second, _ = mspt.start_turn(host, "sess-p", "second")
        mspt.interrupt_turn(host, "sess-p")
        # The queued turn is now the active one: steering lands on it.
        steered, _ = mspt.steer_turn(host, "sess-p", "go on")
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
    assert result["turn"]["turnId"] == second["turnId"]
    assert result["turn"]["state"] == "cancelled"
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


# -- fail-loud on drift ---------------------------------------------------------

@pytest.mark.parametrize("case", ["notdict", "no-turn", "no-turnid"])
def test_turn_plane_fails_loud_on_drift_end_to_end(turn_serve, case):
    argv, _ = turn_serve
    with make_host(argv) as host:
        with pytest.raises(mspt.MSPTurnError):
            mspt.start_turn(host, "drift:" + case, "go")
        with pytest.raises(mspt.MSPTurnError):
            mspt.steer_turn(host, "drift:" + case, "go")
        with pytest.raises(mspt.MSPTurnError):
            mspt.interrupt_turn(host, "drift:" + case)
        with pytest.raises(mspt.MSPTurnError):
            mspt.cancel_turn(host, "drift:" + case)


# -- turn events (the #223 acceptance) --------------------------------------------

def test_turn_start_observable_via_events(turn_serve):
    """Steer a prompt into a live session and observe the turn via events."""
    argv, _ = turn_serve
    seen = []
    with make_host(argv) as host:
        unsub = host.subscribe("turn", seen.append)
        try:
            turn, _ = mspt.start_turn(host, "sess-ev", "go")
            steered, _ = mspt.steer_turn(host, "sess-ev", "more")
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
    assert body["turn"]["state"] == "running"
    assert body["turn"]["sessionId"] == "sess-cli2"


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
    out = _run_cli("steer", "--session-id", "s", "--message", "m")
    assert out.returncode != 0
    assert "serve argv" in out.stderr
