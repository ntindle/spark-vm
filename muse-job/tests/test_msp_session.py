"""Hermetic tests for muse-job/bin/msp_session.py (issue #222).

No `muse` binary is needed: every test drives a fake `muse serve` fixture
that speaks NDJSON JSON-RPC 2.0 over stdio and implements the session
plane (session/start|resume|list|read) with the wire shapes the module
documents -- UUIDv7 commandId, absolute workspaceRoot, the wire
approval-mode enum, the published 1..=200 session/list bound, the
no-attach session/read record. The fixture keeps its session store in a
--store-dir JSON file so a *second* fixture process sees the first one's
sessions (sessions are durable server-side), which is how the
resume-after-host-restart test works.
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import time
import uuid

import pytest

BIN_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "msp_session.py")


def load_mod(name="msp_session_under_test"):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, BIN_PATH)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


msps = load_mod()

# ---------------------------------------------------------------------------
# Fake `muse serve` with a session plane. Session store persists to
# <store-dir>/sessions.json (write-through on start) so a second fixture
# process re-attaches to the first one's sessions. Resume marks
# <store-dir>/loaded.json -- read never does (the no-attach pin).
# ---------------------------------------------------------------------------
FAKE_SESSION_SERVE = (
    "#!/usr/bin/env python3\n"
    + r'''
import argparse, json, os, sys, uuid

ap = argparse.ArgumentParser()
ap.add_argument("--record", default=None)
ap.add_argument("--store-dir", required=True)
args = ap.parse_args()

os.makedirs(args.store_dir, exist_ok=True)
store_path = os.path.join(args.store_dir, "sessions.json")
loaded_path = os.path.join(args.store_dir, "loaded.json")

def load_store():
    try:
        with open(store_path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def save_store(store):
    tmp = store_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f)
    os.replace(tmp, store_path)

def mark_loaded(sid):
    try:
        with open(loaded_path) as f:
            loaded = json.load(f)
    except (OSError, ValueError):
        loaded = []
    if sid not in loaded:
        loaded.append(sid)
    with open(loaded_path, "w") as f:
        json.dump(loaded, f)

UUID7_RE = __import__("re").compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

rec = open(args.record, "a") if args.record else None
initialized = False

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
    store = load_store()
    if method == "session/start":
        cid = params.get("commandId")
        if not isinstance(cid, str) or not UUID7_RE.match(cid):
            err(rid, -32602,
                "invalid session/start commandId: expected UUIDv7",
                {"kind": "invalidParams"})
            continue
        ws = params.get("workspaceRoot")
        if not isinstance(ws, str) or not os.path.isabs(ws):
            err(rid, -32602, "workspaceRoot must be an absolute path",
                {"kind": "invalidParams"})
            continue
        if params.get("sessionId") == "conflict-uuid":
            # Fixture sentinel: the wire never lets sessionId select an
            # existing session; a retained/reserved id is rejected.
            err(rid, -32030, "commandRejected",
                {"kind": "commandRejected",
                 "reason": "session_id_conflict"})
            continue
        sid = "sess-" + uuid.uuid4().hex[:12]
        now = "2026-09-29T15:00:00Z"
        recd = {
            "sessionId": sid,
            "path": os.path.join(args.store_dir, "sessions", sid + ".jsonl"),
            "status": "idle",
            "activeTurnId": None,
            "createdAt": now,
            "updatedAt": now,
            "workspaceRoot": ws,
            "providerId": params.get("providerId", "muse"),
            "modelId": params.get("modelId"),
            "turnCount": 0,
            "forkedFrom": None,
        }
        store[sid] = recd
        save_store(store)
        mark_loaded(sid)
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"session": recd, "viewCursor": "v:%s:1" % sid}})
        if "approvalMode" in params:
            # The wire fires session/approvalModeChanged immediately when
            # the mode is set on start.
            send({"jsonrpc": "2.0", "method": "session/approvalModeChanged",
                  "params": {"sessionId": sid,
                             "mode": params["approvalMode"],
                             "source": "approvalReconfigure"}})
    elif method == "session/resume":
        sid = params.get("sessionId")
        recd = store.get(sid) if isinstance(sid, str) else None
        if recd is None:
            err(rid, -32602, "unknown session", {"kind": "unknownSession"})
            continue
        mark_loaded(sid)
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"session": recd,
                         "history": [{"type": "resumed",
                                      "sessionId": sid}]}})
    elif method == "session/list":
        limit = params.get("limit")
        if (isinstance(limit, bool) or not isinstance(limit, int)
                or not 1 <= limit <= 200):
            err(rid, -32602,
                "invalid session/list limit: expected 1..=200",
                {"kind": "invalidParams"})
            continue
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"sessions": list(store.values())[:limit],
                         "nextCursor": None}})
    elif method == "session/read":
        sid = params.get("sessionId")
        recd = store.get(sid) if isinstance(sid, str) else None
        if recd is None:
            recd = {"sessionId": sid, "status": "notLoaded",
                    "pendingRequests": []}
        # read never marks loaded: no attach, no lease, no subscription.
        send({"jsonrpc": "2.0", "id": rid, "result": {"session": recd}})
    else:
        err(rid, -32601, "unknown method")
''')


@pytest.fixture()
def session_serve(tmp_path):
    """Write the session-plane fixture; return (argv, record, store_dir)."""
    path = tmp_path / "fake_session_serve.py"
    path.write_text(FAKE_SESSION_SERVE)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    record = tmp_path / "record.jsonl"
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    argv = [sys.executable, str(path), "--record", str(record),
            "--store-dir", str(store_dir)]
    return argv, record, store_dir


def read_record(record):
    if not os.path.exists(str(record)):
        return []
    return [json.loads(l) for l in open(str(record)) if l.strip()]


def make_host(argv, **kw):
    kw.setdefault("client_name", "test_client")
    kw.setdefault("request_timeout", 5.0)
    return msps.MSPHost(argv, **kw)


def wait_until(pred, timeout=10.0, step=0.05):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(step)
    return False


def start_params(record):
    return [m for m in read_record(record) if m.get("method") == "session/start"]


UUID7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


# -- session/start ----------------------------------------------------------

def test_start_minimal_wire_shape(session_serve):
    argv, record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        session, cursor = msps.start_session(host, "/tmp/ws")
        assert session["sessionId"].startswith("sess-")
        assert session["workspaceRoot"] == "/tmp/ws"
        assert session["providerId"] == "muse"  # server-side default
        assert session["modelId"] is None
        assert session["status"] == "idle"
        assert session["turnCount"] == 0
        assert cursor == "v:%s:1" % session["sessionId"]
        params = start_params(record)[0]["params"]
        assert UUID7_RE.match(params["commandId"])
        assert params["workspaceRoot"] == "/tmp/ws"
        # v1 config is an empty struct: the client never sends it.
        assert "config" not in params
        # Unset optionals are omitted, not sent as null.
        assert "approvalMode" not in params
        assert "providerId" not in params
        assert "modelId" not in params
        assert "sessionId" not in params
    finally:
        host.close()


def test_start_with_options_and_approval_event(session_serve):
    argv, record, _store = session_serve
    host = make_host(argv)
    seen = []
    host.subscribe("session", seen.append)
    try:
        host.open()
        session, _cursor = msps.start_session(
            host, "/w", approval_mode="allowAll",
            provider_id="custom", model_id="m1")
        params = start_params(record)[0]["params"]
        assert params["approvalMode"] == "allowAll"
        assert params["providerId"] == "custom"
        assert params["modelId"] == "m1"
        assert session["providerId"] == "custom"
        # Setting approvalMode fires session/approvalModeChanged at once.
        assert wait_until(lambda: any(
            m["method"] == "session/approvalModeChanged"
            and m["params"]["mode"] == "allowAll"
            and m["params"]["sessionId"] == session["sessionId"]
            for m in seen))
    finally:
        host.close()


def test_start_rejects_bad_workspace_root(session_serve):
    argv, _record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        for bad in ("relative/path", "", None, 123):
            with pytest.raises(ValueError):
                msps.start_session(host, bad)
    finally:
        host.close()


def test_start_rejects_bad_approval_mode(session_serve):
    argv, _record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        # Wire spelling only: the CLI's "yolo" is not a wire value.
        for bad in ("yolo", "allowall", "", None.__class__):
            with pytest.raises(ValueError):
                msps.start_session(host, "/w", approval_mode=bad)
    finally:
        host.close()


def test_start_rejects_bad_command_id(session_serve):
    argv, _record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        # uuid4 has the wrong version nibble: the host would reject it.
        with pytest.raises(ValueError):
            msps.start_session(host, "/w", command_id=str(uuid.uuid4()))
        with pytest.raises(ValueError):
            msps.start_session(host, "/w", command_id="not-a-uuid")
    finally:
        host.close()


def test_start_caller_command_id_is_used_verbatim(session_serve):
    argv, record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        cid = msps.new_command_id()
        msps.start_session(host, "/w", command_id=cid)
        assert start_params(record)[0]["params"]["commandId"] == cid
    finally:
        host.close()


def test_start_session_id_conflict(session_serve):
    argv, _record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        # sessionId never selects an existing session: the retained id is
        # rejected, and the client surfaces it as a distinct error.
        with pytest.raises(msps.SessionIdConflictError):
            msps.start_session(host, "/w", session_id="conflict-uuid")
    finally:
        host.close()


def test_new_command_id_is_uuid7():
    for _ in range(20):
        cid = msps.new_command_id()
        assert UUID7_RE.match(cid), cid
        assert len({msps.new_command_id() for _ in range(5)}) == 5


# -- session/list -----------------------------------------------------------

def test_list_pagination_and_cursor(session_serve):
    argv, _record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        for _ in range(3):
            msps.start_session(host, "/w")
        sessions, cursor = msps.list_sessions(host)
        assert len(sessions) == 3
        assert cursor is None
        sessions, _cursor = msps.list_sessions(host, limit=2)
        assert len(sessions) == 2
    finally:
        host.close()


def test_list_limit_bounds(session_serve):
    argv, _record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        for bad in (0, -1, 201, 10**9, True, "10", None):
            with pytest.raises(ValueError):
                msps.list_sessions(host, limit=bad)
        # The fixture mirrors the real published bound server-side too.
        with pytest.raises(msps.ServerError) as ei:
            host.call("session/list", {"limit": 201})
        assert ei.value.code == -32602
    finally:
        host.close()


def test_list_limit_boundary_values_pass(session_serve):
    # FOLLOW-msp1: the 1..=200 bound's valid edges must actually work --
    # test_list_limit_bounds above pins only the rejections.
    argv, _record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        for _ in range(3):
            msps.start_session(host, "/w")
        # client-level: limit=1 returns exactly one; limit=200 (the cap)
        # returns everything when the store is smaller than the cap.
        sessions, cursor = msps.list_sessions(host, limit=1)
        assert len(sessions) == 1
        assert cursor is None
        sessions, cursor = msps.list_sessions(host, limit=200)
        assert len(sessions) == 3
        assert cursor is None
        # wire-level: the fixture mirrors the real bound server-side too.
        for good in (1, 200):
            result = host.call("session/list", {"limit": good})
            assert isinstance(result["sessions"], list)
    finally:
        host.close()


# -- session/resume ---------------------------------------------------------

def test_resume_returns_history(session_serve):
    argv, _record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        session, _cursor = msps.start_session(host, "/w")
        result = msps.resume_session(host, session["sessionId"])
        assert result["session"]["sessionId"] == session["sessionId"]
        assert result["history"], "resume must return render history"
    finally:
        host.close()


def test_resume_unknown_session_surfaces_server_error(session_serve):
    argv, _record, _store = session_serve
    host = make_host(argv)
    try:
        host.open()
        with pytest.raises(msps.ServerError):
            msps.resume_session(host, "sess-does-not-exist")
        with pytest.raises(ValueError):
            msps.resume_session(host, "")
    finally:
        host.close()


def test_resume_after_host_restart(session_serve):
    # Acceptance, hermetically: kill the local client, re-open against a
    # NEW fixture process over the same session store, resume the session.
    argv, _record, store_dir = session_serve
    host = make_host(argv)
    try:
        host.open()
        session, _cursor = msps.start_session(host, "/w")
        sid = session["sessionId"]
    finally:
        host.close()  # the local client dies; the session is durable
    host2 = make_host(argv)
    try:
        host2.open()
        result = msps.resume_session(host2, sid)
        assert result["session"]["sessionId"] == sid
        assert result["session"]["workspaceRoot"] == "/w"
    finally:
        host2.close()


# -- session/read -----------------------------------------------------------

def test_read_no_attach(session_serve):
    argv, _record, store_dir = session_serve
    host = make_host(argv)
    try:
        host.open()
        # Unknown id: notLoaded record, not an error.
        recd = msps.read_session(host, "sess-never-existed")
        assert recd["status"] == "notLoaded"
        assert recd["pendingRequests"] == []
        # Known id: the record, and read leaves the loaded set alone.
        session, _cursor = msps.start_session(host, "/w")
        loaded_before = json.loads(
            open(os.path.join(str(store_dir), "loaded.json")).read())
        recd = msps.read_session(host, session["sessionId"])
        assert recd["sessionId"] == session["sessionId"]
        assert recd["status"] == "idle"
        loaded_after = json.loads(
            open(os.path.join(str(store_dir), "loaded.json")).read())
        assert loaded_after == loaded_before  # read attached nothing
    finally:
        host.close()


# -- shape drift ------------------------------------------------------------

def test_require_session_fails_loud_on_drift():
    for bad in (None, "x", [], {}, {"session": None}, {"session": {}},
                {"session": {"noId": 1}}, {"result": {}}):
        with pytest.raises(msps.MSPSessionError):
            msps._require_session(bad, "session/read")


# -- smoke CLI --------------------------------------------------------------

def test_smoke_cli_start_and_list(session_serve, tmp_path):
    argv, _record, _store = session_serve
    p = subprocess.run(
        [sys.executable, str(BIN_PATH), "start",
         "--workspace-root", "/w", "--approval-mode", "allowAll",
         "--", *argv],
        capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    doc = json.loads(p.stdout)
    assert doc["session"]["workspaceRoot"] == "/w"
    assert doc["viewCursor"].startswith("v:")
    p = subprocess.run(
        [sys.executable, str(BIN_PATH), "list", "--limit", "5",
         "--", *argv],
        capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    doc = json.loads(p.stdout)
    assert isinstance(doc["sessions"], list)
    assert "nextCursor" in doc


def test_smoke_cli_warns_not_redacted_on_stderr(session_serve, tmp_path):
    # The smoke CLI's stdout is never redacted: the warning must appear
    # on stderr on EVERY invocation, not just in --help, while stdout
    # stays clean parseable JSON.
    argv, _record, _store = session_serve
    p = subprocess.run(
        [sys.executable, str(BIN_PATH), "list", "--limit", "5",
         "--", *argv],
        capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert "NOT redacted" in p.stderr
    assert "agents can read it" in p.stderr
    doc = json.loads(p.stdout)  # stdout carries no warning text
    assert isinstance(doc["sessions"], list)
