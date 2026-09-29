"""Hermetic tests for muse-job/bin/msp_host.py (issue #221).

No `muse` binary is needed: every test (except the explicitly-marked live
smoke) drives a fake `muse serve` fixture that speaks NDJSON JSON-RPC 2.0
over stdio. The fixture enforces the handshake ordering the real binary
taught us -- any method before the `initialized` notification answers
`Not initialized` -- so the tests pin the behavior, not just the API.
"""
import importlib.machinery
import importlib.util
import io
import json
import os
import select
import shutil
import stat
import sys
import threading
import time

import pytest

BIN_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "msp_host.py")


def load_mod(name="msp_host_under_test"):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, BIN_PATH)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


msp = load_mod()

# ---------------------------------------------------------------------------
# Fake `muse serve`. Speaks enough of the protocol to exercise the client:
# initialize -> result, initialized -> flag + one notification + one
# server->client request, method gating on the flag, canned method answers,
# chaos methods (boom/never/die/badframe/unknownid), and a --fail-init mode.
# Every client message is appended to --record for ordering assertions.
# ---------------------------------------------------------------------------
# The bundle the fixture prints for `... schema generate-json-schema`
# (B1: exercises the schema-pin enforcement path in open()).
SCHEMA_BUNDLE = '{"methods":["initialize","session/list"],"title":"fake-muse-schema"}'

FAKE_SERVE = (
    "#!/usr/bin/env python3\n"
    "import sys as _sys\n"
    "if 'generate-json-schema' in _sys.argv[1:]:\n"
    "    _sys.stdout.write(" + repr(SCHEMA_BUNDLE) + " + chr(10))\n"
    "    _sys.exit(0)\n"
    + r'''
import argparse, json, os, sys

ap = argparse.ArgumentParser()
ap.add_argument("--record", default=None)
ap.add_argument("--fail-init", action="store_true")
ap.add_argument("--grandchild-pidfile", default=None)
args = ap.parse_args()

if args.grandchild_pidfile:
    # Spawn a grandchild that inherits our stdout pipe and sleeps: when the
    # test kills us, the pipe stays open (no EOF) until the test kills the
    # grandchild too. Exercises the straggler-reader path in reconnect().
    import subprocess as _sp
    _gc = _sp.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                    stdout=sys.stdout, stderr=sys.stderr, stdin=_sp.DEVNULL,
                    start_new_session=True)
    with open(args.grandchild_pidfile, "a") as _f:
        _f.write(str(_gc.pid) + "\n")

rec = open(args.record, "a") if args.record else None
initialized = False

def send(o):
    sys.stdout.write(json.dumps(o) + "\n")
    sys.stdout.flush()

def record(msg):
    if rec:
        rec.write(json.dumps(msg) + "\n")
        rec.flush()

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
    if method is None:
        continue  # a response to our own server->client request: not a call
    if method == "initialized":
        initialized = True
        send({"jsonrpc": "2.0", "method": "session/changed",
              "params": {"uuid": "sess-1"}})
        send({"jsonrpc": "2.0", "id": "srv-1", "method": "userInput/request",
              "params": {"prompt": "trust this workspace?"}})
        continue
    if method == "initialize":
        if args.fail_init:
            send({"jsonrpc": "2.0", "id": rid,
                  "error": {"code": -32002, "message": "init refused"}})
        else:
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"protocolVersion": "1",
                             "serverInfo": {"name": "fake-muse-serve",
                                            "version": "0"}}})
        continue
    if not initialized:
        send({"jsonrpc": "2.0", "id": rid,
              "error": {"code": -32099, "message": "Not initialized"}})
        continue
    if method == "session/list":
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"sessions": [{"uuid": "sess-1", "name": "tui-job"}]}})
    elif method == "boom":
        send({"jsonrpc": "2.0", "id": rid,
              "error": {"code": -32000, "message": "kablam"}})
    elif method == "never":
        pass  # never answer: exercises the client timeout
    elif method == "die":
        send({"jsonrpc": "2.0", "id": rid, "result": {"ok": True}})
        sys.stdout.flush()
        sys.stderr.write("dying\n")
        sys.stderr.flush()
        os._exit(3)
    elif method == "badframe":
        sys.stdout.write("NOT JSON{{{\n")
        sys.stdout.flush()
        send({"jsonrpc": "2.0", "id": rid, "result": {"ok": True}})
    elif method == "unknownid":
        send({"jsonrpc": "2.0", "id": rid, "result": {"ok": True}})
        send({"jsonrpc": "2.0", "id": 999999,
              "result": {"stray": True}})
    else:
        send({"jsonrpc": "2.0", "id": rid,
              "error": {"code": -32601, "message": "unknown method"}})
''')


@pytest.fixture()
def fake_serve(tmp_path):
    """Write the fixture; return (argv_for_host, record_path)."""
    path = tmp_path / "fake_muse_serve.py"
    path.write_text(FAKE_SERVE)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    record = tmp_path / "record.jsonl"
    return [sys.executable, str(path), "--record", str(record)], record


@pytest.fixture()
def fake_serve_direct(tmp_path):
    """Executable fixture (shebang): argv[0] alone answers
    `schema generate-json-schema`, so the open() pin path works."""
    path = tmp_path / "fake_muse_serve.py"
    path.write_text(FAKE_SERVE)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    record = tmp_path / "record.jsonl"
    return [str(path), "--record", str(record)], record


def read_record(record):
    if not os.path.exists(str(record)):
        return []
    return [json.loads(l) for l in open(str(record)) if l.strip()]


def make_host(argv, **kw):
    kw.setdefault("client_name", "test_client")
    kw.setdefault("request_timeout", 5.0)
    return msp.MSPHost(argv, **kw)


def wait_until(pred, timeout=10.0, step=0.05):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(step)
    return False


# -- handshake & basic calls ------------------------------------------------

def test_open_handshake_and_session_list(fake_serve):
    argv, record = fake_serve
    host = make_host(argv)
    try:
        result = host.open()
        assert result["serverInfo"]["name"] == "fake-muse-serve"
        sessions = host.call("session/list")
        assert sessions["sessions"][0]["uuid"] == "sess-1"
        # Handshake ordering pinned: initialized before any other method.
        methods = [m.get("method") for m in read_record(record)
                   if m.get("method")]
        assert methods[0] == "initialize"
        assert methods[1] == "initialized"
        assert methods.index("initialized") < methods.index("session/list")
    finally:
        host.close()


def test_fixture_rejects_method_before_initialized(tmp_path):
    # The fixture mirrors the real binary: any method before the
    # `initialized` notification answers `Not initialized`. If our client
    # ever regressed its handshake order, session/list would fail loudly.
    import subprocess
    path = tmp_path / "fake_muse_serve.py"
    path.write_text(FAKE_SERVE)
    p = subprocess.Popen([sys.executable, str(path)],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         text=True)
    try:
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1,
                                  "method": "session/list",
                                  "params": {}}) + "\n")
        p.stdin.flush()
        resp = json.loads(p.stdout.readline())
        assert resp["error"]["message"] == "Not initialized"
    finally:
        p.kill()
        p.wait()


def test_notification_dispatch(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    seen = []
    host.subscribe("session", seen.append)
    try:
        host.open()
        assert wait_until(lambda: len(seen) >= 1)
        assert seen[0]["method"] == "session/changed"
        assert seen[0]["params"]["uuid"] == "sess-1"
    finally:
        host.close()


def test_subscribe_prefix_matching_and_unsubscribe(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    exact, other = [], []
    unsub = host.subscribe("session/changed", exact.append)
    host.subscribe("approval", other.append)
    try:
        host.open()
        assert wait_until(lambda: len(exact) >= 1)
        unsub()
        host._handle_notification(
            {"jsonrpc": "2.0", "method": "session/changed",
             "params": {}}, "session/changed")
        assert len(exact) == 1  # unsubscribed: no second delivery
    finally:
        host.close()


def test_subscribe_prefix_boundary(fake_serve):
    # The boundary is prefix + "/": "widgetal/changed" must NOT route to
    # a "widget" subscriber (a bare startswith regression would misroute).
    # Prefixes are fixture-silent: the live session/changed notification
    # from open() cannot pollute the assertion (that race flaked ~1/20).
    argv, _record = fake_serve
    host = make_host(argv)
    got, gadget_got = [], []
    host.subscribe("widget", lambda m: got.append(m["method"]))
    host.subscribe("gadget", lambda m: gadget_got.append(m["method"]))
    try:
        host.open()
        for method in ("widget/changed", "widgetal/changed", "widget",
                       "gadget/x"):
            host._handle_notification(
                {"jsonrpc": "2.0", "method": method, "params": {}}, method)
        assert got == ["widget/changed", "widget"]
        assert gadget_got == ["gadget/x"]
    finally:
        host.close()


def test_subscriber_exception_does_not_kill_reader(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)

    def bad(msg):
        raise RuntimeError("subscriber blew up")

    host.subscribe("session", bad)
    try:
        host.open()
        assert wait_until(lambda: len(host.subscriber_errors) >= 1)
        # Reader survived: the transport still works.
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        host.close()


# -- server->client requests -------------------------------------------------

def test_server_request_routed_to_handler(fake_serve):
    argv, record = fake_serve
    host = make_host(argv)
    host.set_request_handler("userInput/request",
                             lambda req: {"answer": "yes"})
    try:
        host.open()
        assert wait_until(
            lambda: any(m.get("id") == "srv-1" for m in read_record(record)))
        answers = [m for m in read_record(record) if m.get("id") == "srv-1"]
        assert answers[0]["result"] == {"answer": "yes"}
    finally:
        host.close()


def test_server_request_without_handler_gets_method_not_found(fake_serve):
    argv, record = fake_serve
    host = make_host(argv)
    try:
        host.open()
        assert wait_until(
            lambda: any(m.get("id") == "srv-1" for m in read_record(record)))
        answers = [m for m in read_record(record) if m.get("id") == "srv-1"]
        assert answers[0]["error"]["code"] == -32601
    finally:
        host.close()


def test_handler_exception_becomes_error_response(fake_serve):
    argv, record = fake_serve
    host = make_host(argv)

    def bad(req):
        raise RuntimeError("handler blew up")

    host.set_request_handler("userInput/request", bad)
    try:
        host.open()
        assert wait_until(
            lambda: any(m.get("id") == "srv-1" for m in read_record(record)))
        answers = [m for m in read_record(record) if m.get("id") == "srv-1"]
        assert answers[0]["error"]["code"] == -32000
    finally:
        host.close()


# -- errors, timeouts, malformed frames --------------------------------------

def test_call_error_response_raises_server_error(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    try:
        host.open()
        with pytest.raises(msp.ServerError) as ei:
            host.call("boom")
        assert ei.value.code == -32000
        assert "kablam" in str(ei.value)
    finally:
        host.close()


def test_call_timeout(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv, request_timeout=5.0)
    try:
        host.open()
        with pytest.raises(msp.RequestTimeoutError):
            host.call("never", timeout=0.4)
        # A timed-out call doesn't poison the connection.
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        host.close()


def test_malformed_frame_does_not_kill_reader(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    try:
        host.open()
        assert host.call("badframe") == {"ok": True}
        assert host.stats["malformed"] == 1
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        host.close()


def test_unknown_response_id_ignored(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    try:
        host.open()
        assert host.call("unknownid") == {"ok": True}
        assert wait_until(
            lambda: host.stats["unknown_id_responses"] == 1)
    finally:
        host.close()


def test_call_before_open_raises(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    with pytest.raises(msp.HostDiedError):
        host.call("session/list")


def test_bad_client_name_rejected(fake_serve):
    argv, _record = fake_serve
    with pytest.raises(ValueError):
        msp.MSPHost(argv, client_name="Bad Name!")
    with pytest.raises(ValueError):
        msp.MSPHost(argv, client_name="has-dash")
    # Valid names pass construction.
    msp.MSPHost(argv, client_name="ok_name_1").close()


def test_handshake_failure_reaps_process(tmp_path, monkeypatch):
    path = tmp_path / "fake_muse_serve.py"
    path.write_text(FAKE_SERVE)
    argv = [sys.executable, str(path), "--fail-init"]
    spawned = []
    real_popen = msp.subprocess.Popen

    def spy_popen(*a, **k):
        proc = real_popen(*a, **k)
        spawned.append(proc)
        return proc

    monkeypatch.setattr(msp.subprocess, "Popen", spy_popen)
    host = make_host(argv)
    with pytest.raises(msp.HandshakeError):
        host.open()
    # The old assertion (host._proc is None or poll() is not None) was
    # vacuous: close() always nulls _proc. Assert on the real child.
    assert spawned, "open() never spawned the serve process"
    assert spawned[0].poll() is not None, "serve child was not reaped"
    assert host._proc is None


def test_double_open_raises(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    try:
        host.open()
        with pytest.raises(msp.MSPError):
            host.open()
    finally:
        host.close()


def test_call_and_notify_after_close_raise(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    host.open()
    host.close()
    with pytest.raises(msp.HostDiedError):
        host.call("session/list")
    with pytest.raises(msp.HostDiedError):
        host.notify("session/ping", {})


def test_unspawnable_binary_fails_loud():
    host = make_host(["/nonexistent/muse-serve-binary-xyz"],
                     client_name="x")
    with pytest.raises(msp.MSPError):
        host.open()


# -- reconnect / close -------------------------------------------------------

def test_concurrent_calls_no_crosstalk(fake_serve):
    # Id correlation under threads is the core of this transport. Workers
    # alternate two distinguishable methods so a crossed response (wrong
    # call getting another call's answer) fails fast instead of passing
    # silently behind byte-identical payloads.
    argv, _record = fake_serve
    host = make_host(argv)
    try:
        host.open()
        errors = []

        def worker(seed):
            try:
                for j in range(10):
                    if (seed + j) % 2 == 0:
                        r = host.call("session/list", timeout=10.0)
                        assert r["sessions"][0]["uuid"] == "sess-1"
                    else:
                        with pytest.raises(msp.ServerError) as ei:
                            host.call("boom", timeout=10.0)
                        assert ei.value.code == -32000
            except Exception as e:  # noqa: BLE001 -- collected, not swallowed
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not any(t.is_alive() for t in threads), "worker hung"
        assert not errors, errors[0] if errors else None
    finally:
        host.close()


def test_close_fails_blocked_call(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    try:
        host.open()
        outcome = []

        def blocked():
            try:
                host.call("never", timeout=30.0)
                outcome.append("no-raise")
            except msp.HostDiedError:
                outcome.append("host-died")
            except Exception as e:  # noqa: BLE001 -- recorded for the assert
                outcome.append(f"wrong: {e!r}")

        t = threading.Thread(target=blocked)
        t.start()
        assert wait_until(lambda: len(host._pending) == 1)
        host.close()
        t.join(timeout=15)
        assert outcome == ["host-died"], outcome
    finally:
        host.close()


def test_reconnect_after_host_death(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    try:
        host.open()
        assert host.call("die") == {"ok": True}
        assert wait_until(lambda: not host.is_alive())
        with pytest.raises(msp.HostDiedError):
            host.call("session/list")
        host.reconnect()  # fresh process, same argv; handlers survive
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        host.close()


def test_straggler_reader_does_not_poison_new_generation(tmp_path):
    # The old reader can survive reconnect(): when the dead child's stdout
    # pipe is inherited by a grandchild, close()'s reader join times out
    # (no EOF ever arrives) and the straggler outlives the generation bump.
    # When the grandchild later exits, the straggler's finally must not set
    # _dead / drain pending on the healthy new host. (Engineering
    # reproduced the unguarded version bricking the new host end-to-end.)
    import signal

    path = tmp_path / "fake_muse_serve.py"
    path.write_text(FAKE_SERVE)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    pidfile = tmp_path / "grandchildren"
    argv = [sys.executable, str(path), "--grandchild-pidfile", str(pidfile)]
    host = make_host(argv, kill_grace=1.0)
    try:
        host.open()
        assert host.is_alive()
        old_pids = [int(p) for p in pidfile.read_text().split()]
        assert len(old_pids) == 1
        old_reader = host._reader
        host.reconnect()  # join (1s+5s) times out on the straggler
        assert host.is_alive()
        assert host._reader is not old_reader
        # Let the straggler observe EOF now.
        os.kill(old_pids[0], signal.SIGKILL)
        assert wait_until(lambda: not old_reader.is_alive(), timeout=10.0)
        # The new generation must still be healthy: the straggler's
        # finally must not have poisoned it.
        assert host.is_alive()
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        for pid in [int(p) for p in pidfile.read_text().split()]:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        host.close()


def test_reconnect_preserves_handlers_and_subscribers(fake_serve):
    # The fresh generation re-sends srv-1 + session/changed after its
    # handshake, so survival is directly assertable.
    argv, record = fake_serve
    host = make_host(argv)
    seen = []
    host.subscribe("session", seen.append)
    host.set_request_handler("userInput/request",
                             lambda req: {"answer": "yes"})
    try:
        host.open()
        assert wait_until(lambda: len(seen) >= 1)
        assert host.call("die") == {"ok": True}
        assert wait_until(lambda: not host.is_alive())
        open(record, "w").close()  # generation boundary in the record
        seen.clear()
        host.reconnect()
        assert wait_until(
            lambda: any(m.get("id") == "srv-1" for m in read_record(record)))
        answers = [m for m in read_record(record) if m.get("id") == "srv-1"]
        assert answers[0]["result"] == {"answer": "yes"}
        assert wait_until(lambda: len(seen) >= 1)
        assert seen[0]["method"] == "session/changed"
    finally:
        host.close()


def test_reentrant_call_from_handler_fails_loud(fake_serve):
    # A handler that calls back into the host must get a loud MSPError,
    # not a silent dispatch deadlock; the reader must survive it.
    argv, _record = fake_serve
    host = make_host(argv)
    seen_exc = []

    def handler(req):
        try:
            host.call("session/list")
        except msp.MSPError as e:
            seen_exc.append(e)
        return {"answer": "yes"}

    def subscriber(msg):
        try:
            host.notify("session/ping", {})
        except msp.MSPError as e:
            seen_exc.append(e)

    host.set_request_handler("userInput/request", handler)
    host.subscribe("session", subscriber)
    try:
        host.open()
        assert wait_until(lambda: len(seen_exc) >= 2)
        assert all(isinstance(e, msp.MSPError) for e in seen_exc)
        # Reader survived: the transport still works.
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        host.close()


def test_close_is_idempotent_and_reaps(fake_serve):
    argv, _record = fake_serve
    host = make_host(argv)
    host.open()
    proc = host._proc
    host.close()
    host.close()
    assert proc.poll() is not None


def test_stderr_goes_to_job_log(fake_serve, tmp_path):
    argv, _record = fake_serve
    log = tmp_path / "job.log"
    host = make_host(argv, log_path=str(log))
    try:
        host.open()
        host.call("die")
        assert wait_until(lambda: not host.is_alive())
    finally:
        host.close()
    assert b"dying" in log.read_bytes()


def test_context_manager(fake_serve):
    argv, _record = fake_serve
    with make_host(argv) as host:
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    assert not host.is_alive()


# -- schema fingerprint ------------------------------------------------------

def test_schema_fingerprint_is_canonical():
    a = b'{"b": 1, "a": [1, 2]}'
    b = b'{\n  "a": [1, 2],\n  "b": 1\n}'
    assert msp.schema_fingerprint(a) == msp.schema_fingerprint(b)
    assert msp.schema_fingerprint(a).startswith("sha256:")
    assert msp.schema_fingerprint(b'{"a": 1}') != msp.schema_fingerprint(
        b'{"a": 2}')


def test_schema_fingerprint_rejects_bad_json():
    with pytest.raises(ValueError):
        msp.schema_fingerprint(b"not json")


def test_verify_schema_fingerprint():
    schema = b'{"methods": ["initialize"]}'
    pin = msp.schema_fingerprint(schema)
    assert msp.verify_schema_fingerprint(schema, pin) == pin
    with pytest.raises(msp.SchemaMismatchError):
        msp.verify_schema_fingerprint(b'{"methods": []}', pin)


def test_schema_pin_enforced_on_open(fake_serve_direct):
    # The pin path is a headline #221 bullet ("fail loud on mismatch"):
    # argv[0] alone must answer `schema generate-json-schema`.
    argv, _record = fake_serve_direct
    pin = msp.schema_fingerprint(SCHEMA_BUNDLE.encode())
    host = msp.MSPHost(argv, client_name="pin_client",
                       expected_schema_fingerprint=pin,
                       verify_schema_on_open=True)
    try:
        host.open()
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        host.close()


def test_schema_pin_mismatch_fails_loud_before_spawn(fake_serve_direct):
    argv, _record = fake_serve_direct
    host = msp.MSPHost(argv, client_name="pin_client",
                       expected_schema_fingerprint="sha256:" + "0" * 64,
                       verify_schema_on_open=True)
    with pytest.raises(msp.SchemaMismatchError):
        host.open()
    assert host._proc is None  # no serve process was spawned


def test_schema_exporter_failure_fails_loud():
    # `python schema generate-json-schema` exits nonzero ("can't open
    # file 'schema'") -> MSPError, never a handshake attempt.
    argv = [sys.executable, "-c", "import sys; sys.exit(3)"]
    host = msp.MSPHost(argv, client_name="pin_client",
                       expected_schema_fingerprint="sha256:" + "0" * 64,
                       verify_schema_on_open=True)
    with pytest.raises(msp.MSPError):
        host.open()
    assert host._proc is None


# -- review-round fixes (QA + Security + Engineering, 2026-09-28) -------------

def test_reconnect_never_opened_behaves_like_open(fake_serve):
    # Documented contract: reconnect() on a never-opened host == open().
    argv, _record = fake_serve
    host = make_host(argv)
    try:
        result = host.reconnect()
        assert result["serverInfo"]["name"] == "fake-muse-serve"
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        host.close()


def test_schema_pin_with_absent_binary_fails_loud():
    # The pin path's OSError branch: no serve process is spawned.
    host = msp.MSPHost(["/nonexistent/muse-xyz"], client_name="pin_client",
                       expected_schema_fingerprint="sha256:" + "0" * 64,
                       verify_schema_on_open=True)
    with pytest.raises(msp.MSPError):
        host.open()
    assert host._proc is None


def test_verify_schema_on_open_without_pin_fails_loud():
    # verify_schema_on_open with no pin is a configuration bug: fail
    # before spawning anything.
    host = msp.MSPHost(["true"], client_name="pin_client",
                       verify_schema_on_open=True)
    # match= pins the guard itself: without it, the handshake fails on EOF
    # and HandshakeError (an MSPError subclass) would satisfy a bare
    # pytest.raises(MSPError), making this test vacuous.
    with pytest.raises(msp.MSPError,
                       match="verify_schema_on_open needs expected_schema_fingerprint"):
        host.open()
    assert host._proc is None


def test_send_frame_cap_refused_before_lock(fake_serve):
    # A caller-supplied params over _MAX_SEND_FRAME_BYTES is refused
    # before the write lock is taken: the host stays usable and no
    # bytes hit the pipe.
    argv, _record = fake_serve
    host = make_host(argv)
    try:
        host.open()
        big = "x" * (msp._MAX_SEND_FRAME_BYTES + 1)
        with pytest.raises(ValueError):
            host.call("session/list", {"pad": big})
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        host.close()


def test_stderr_log_created_mode_0600(fake_serve, tmp_path):
    # Serve stderr can carry secrets: the job log is 0o600, never umask.
    argv, _record = fake_serve
    log = tmp_path / "job.log"
    host = make_host(argv, log_path=str(log))
    try:
        host.open()
        assert log.exists()
        assert stat.S_IMODE(os.stat(str(log)).st_mode) == 0o600
    finally:
        host.close()


def test_stderr_log_tightens_preexisting_mode(fake_serve, tmp_path):
    # os.open's mode applies only at creation: a pre-existing 0644 log
    # would otherwise keep leaking new secret bytes to group/other, so
    # open() tightens it to 0o600 before the serve host spawns.
    argv, _record = fake_serve
    log = tmp_path / "job.log"
    log.write_bytes(b"old\n")
    os.chmod(str(log), 0o644)
    host = make_host(argv, log_path=str(log))
    try:
        host.open()
        assert stat.S_IMODE(os.stat(str(log)).st_mode) == 0o600
        assert b"old" in log.read_bytes()  # content preserved, not truncated
    finally:
        host.close()


def test_stderr_log_never_loosens_stricter_mode(fake_serve, tmp_path):
    # Permissions are only revoked, never granted. A 0400 log is
    # unopenable-for-write by a non-root operator: the open fails with
    # EACCES -> MSPError, still fail-closed (no spawn). As root the open
    # succeeds and the mode must stay 0400 -- never loosened to 0600.
    argv, _record = fake_serve
    log = tmp_path / "job.log"
    log.write_bytes(b"old\n")
    os.chmod(str(log), 0o400)
    host = make_host(argv, log_path=str(log))
    if os.geteuid() == 0:
        try:
            host.open()
            assert stat.S_IMODE(os.stat(str(log)).st_mode) == 0o400
        finally:
            host.close()
    else:
        with pytest.raises(msp.MSPError):
            host.open()
        assert not host.is_alive()
        assert host._proc is None
        assert stat.S_IMODE(os.stat(str(log)).st_mode) == 0o400


def test_stderr_log_rejects_symlink(fake_serve, tmp_path):
    # A symlink at log_path is refused fail-closed: the serve host is
    # never spawned and no bytes are written through the link.
    argv, _record = fake_serve
    target = tmp_path / "real.log"
    link = tmp_path / "job.log"
    link.symlink_to(target)
    host = make_host(argv, log_path=str(link))
    with pytest.raises(msp.MSPError, match="symlink"):
        host.open()
    assert not host.is_alive()
    assert host._proc is None
    assert not target.exists()


def test_stderr_log_readerless_fifo_fails_fast(tmp_path):
    # A pre-planted FIFO must not hang open(): O_NONBLOCK makes the
    # reader-less open fail fast with ENXIO -> MSPError (the #23 H5 class
    # the muse-job hooks already defend against). Unit-level on the
    # helper so a regression fails the test instead of hanging the suite:
    # the thread join bounds the wait.
    import threading
    fifo = tmp_path / "job.log"
    os.mkfifo(str(fifo))
    outcome = []

    def attempt():
        try:
            msp._open_secret_log(str(fifo))
        except Exception as e:  # noqa: BLE001 -- recorded for assertion
            outcome.append(e)

    t = threading.Thread(target=attempt, daemon=True)
    t.start()
    t.join(timeout=10)
    assert not t.is_alive(), "open() hung on a reader-less FIFO"
    assert len(outcome) == 1
    assert isinstance(outcome[0], msp.MSPError)


def test_stderr_log_nonregular_target_allowed(fake_serve):
    # Non-regular log targets (e.g. /dev/null) keep working: only regular
    # files get the 0o600 treatment.
    argv, _record = fake_serve
    host = make_host(argv, log_path="/dev/null")
    try:
        host.open()
        assert host.is_alive()
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        host.close()


def test_read_frame_respects_byte_budget():
    # Unit-level: _read_frame caps one frame at max_frame_bytes (the
    # anti-OOM path for a wedged serve host emitting a giant line).
    host = make_host(["true"], max_frame_bytes=16)

    class _P:  # minimal proc stub: only .stdout is read
        pass

    p = _P()
    buf = bytearray()
    p.stdout = io.BytesIO(b'{"a": 1}\nrest')
    assert host._read_frame(p, buf) == b'{"a": 1}'
    # Leftover bytes stay buffered for the next frame.
    p.stdout = io.BytesIO(b'')
    assert host._read_frame(p, buf) == b'rest'
    p.stdout = io.BytesIO(b"x" * 64 + b"\n")
    assert host._read_frame(p, bytearray()) is msp._FRAME_OVERRUN
    p.stdout = io.BytesIO(b"")
    assert host._read_frame(p, bytearray()) is None
    # A short final line with no trailing newline still parses.
    p.stdout = io.BytesIO(b'{"b": 2}')
    assert host._read_frame(p, bytearray()) == b'{"b": 2}'


def test_stale_generation_write_refused_after_reconnect(fake_serve):
    # A write stamped with the dead generation must never address the
    # new process: _send raises HostDiedError("superseded by reconnect")
    # and the new host keeps working.
    argv, _record = fake_serve
    host = make_host(argv)
    try:
        host.open()
        stale_gen = host._generation
        host.reconnect()
        assert host._generation == stale_gen + 1
        with pytest.raises(msp.HostDiedError):
            host._send({"jsonrpc": "2.0", "method": "x", "params": {}},
                       expected_gen=stale_gen)
        assert host.call("session/list")["sessions"][0]["uuid"] == "sess-1"
    finally:
        host.close()


# A serve host that answers the handshake, then never reads stdin again:
# the exact wedged-child shape the send-timeout path exists for.
WEDGED_SERVE = (
    "#!/usr/bin/env python3\n"
    "import json as _j, sys as _s, time as _t\n"
    "_req = _j.loads(_s.stdin.readline())\n"
    "_s.stdout.write(_j.dumps({\"jsonrpc\": \"2.0\", \"id\": _req[\"id\"],\n"
    "    \"result\": {\"serverInfo\": {\"name\": \"wedged\", "
    "\"version\": \"0\"}}}) + \"\\n\")\n"
    "_s.stdout.flush()\n"
    "_s.stdin.close()\n"
    "_t.sleep(300)\n"
)


def test_send_timeout_on_wedged_child(tmp_path):
    # A 2 MiB frame to a child that never drains stdin must fail loud
    # within send_timeout -- never hang _send (and thereby close()) on
    # the write lock forever.
    path = tmp_path / "wedged_serve.py"
    path.write_text(WEDGED_SERVE)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    host = make_host([sys.executable, str(path)], send_timeout=2.0)
    try:
        host.open()
        start = time.time()
        with pytest.raises(msp.HostDiedError):
            host.call("session/list", {"pad": "x" * (2 * 1024 * 1024)})
        elapsed = time.time() - start
        assert elapsed < 20.0, f"send took {elapsed:.1f}s; lock was wedged"
        # close() itself must still terminate cleanly after the wedge.
        host.close()
        assert not host.is_alive()
    finally:
        host.close()


# -- live binary smoke (issue #221 acceptance; runs on spark-vm) -------------

@pytest.mark.skipif(shutil.which("muse") is None,
                    reason="no muse binary on this box")
def test_live_muse_serve_smoke():
    """Acceptance for #221 against the real binary. Skipped in CI; runs
    on spark-vm post-ship."""
    import subprocess as sp
    # Pin the 2026-09-17 discovery against the REAL binary (not just the
    # fake): a method call before the initialized notification must fail
    # with "Not initialized".
    p = sp.Popen(["muse", "serve"], stdin=sp.PIPE, stdout=sp.PIPE,
                 text=True)
    try:
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1,
                                  "method": "session/list",
                                  "params": {}}) + "\n")
        p.stdin.flush()
        ready, _, _ = select.select([p.stdout], [], [], 10.0)
        assert ready, "real serve gave no answer to pre-initialized call"
        resp = json.loads(p.stdout.readline())
        assert resp.get("error", {}).get("message") == "Not initialized", resp
    finally:
        p.kill()
        p.wait()
    # Two hosts against the same store must see the same session store --
    # the minimal honest encoding of "sees the same store the TUI sees".
    hosts = [msp.MSPHost(["muse", "serve"], client_name="msp_smoke_test",
                         request_timeout=15.0) for _ in range(2)]
    try:
        for h in hosts:
            h.open()
        results = [h.call("session/list", timeout=15.0) for h in hosts]
        for result in results:
            assert isinstance(result, dict)
            assert isinstance(result.get("sessions"), list), result
            for s in result["sessions"]:
                assert s.get("uuid"), s
        uuid_lists = [sorted(s["uuid"] for s in r["sessions"])
                      for r in results]
        assert uuid_lists[0] == uuid_lists[1], \
            "two serve hosts disagree on the session store"
    finally:
        for h in hosts:
            h.close()
