"""Tests for issue #1129: the detached per-turn MSP supervisor.

The supervisor holds one `muse serve` host for one turn so a host close
can never kill the turn. These tests pin the supervisor's file protocol
(heartbeat / view snapshot / steer queue / pid file), the -32021
held-session translation in `_msp_call`, and the anti-spoof guards --
without a live `muse serve`.
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import time
import types

import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job")


def load_script(name, path):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


class FakeSignal:
    def __init__(self, kind="item", method="item/added", detail="2 added"):
        self.kind = kind
        self.method = method
        self.detail = detail


class FakeView:
    def __init__(self, state="working", active_turn_id="turn-1",
                 pending_summary="", last_terminal=None):
        self.state = state
        self.active_turn_id = active_turn_id
        self.pending_summary = pending_summary
        self.last_event_at = time.time()
        self.last_terminal = last_terminal


class FakeServerError(Exception):
    def __init__(self, code, message):
        super().__init__(f"serve host error {code}: {message}")
        self.code = code
        self.message = message


class FakeHost:
    def __init__(self, serve_argv, *, client_name, log_path=None, **kw):
        self.opened = False
        self.closed = False

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True


class FakeTurn:
    def __init__(self):
        self.steered = []
        self.started = []

    def steer_turn(self, host, sid, message, expected_turn_id=None):
        self.steered.append((sid, message, expected_turn_id))

    def start_turn(self, host, sid, message):
        self.started.append((sid, message))
        return ({"turnId": "turn-new"}, None)


@pytest.fixture()
def fakes(monkeypatch):
    m_host = types.ModuleType("msp_host")
    m_host.MSPHost = FakeHost
    m_host.ServerError = FakeServerError
    m_session = types.ModuleType("msp_session")
    m_session.YOLO_APPROVAL_MODE = "yolo"
    m_turn = types.ModuleType("msp_turn")
    m_events = types.ModuleType("msp_events")
    m_events.STATE_IDLE = "idle"
    m_events.STATE_TURN_FAILED = "turn_failed"
    m_events.STATE_TURN_CANCELLED = "turn_cancelled"
    m_events.STATE_SESSION_CLOSED = "session_closed"
    m_recovery = types.ModuleType("msp_recovery")
    for name, mod in (("msp_host", m_host), ("msp_session", m_session),
                      ("msp_turn", m_turn), ("msp_events", m_events),
                      ("msp_recovery", m_recovery)):
        monkeypatch.setitem(sys.modules, name, mod)
    return {"msp_host": m_host, "msp_session": m_session,
            "msp_turn": m_turn, "msp_events": m_events,
            "msp_recovery": m_recovery}


@pytest.fixture()
def cli(monkeypatch, tmp_path, fakes):
    monkeypatch.setenv("HOME", str(tmp_path))
    mod = load_script("muse_job_supervisor_test", CLI_PATH)
    slug = "sup-job"
    os.makedirs(mod.job_dir(slug), exist_ok=True)
    return mod, slug


def paths_of(cli_mod, slug):
    return cli_mod._supervisor_paths(slug)


# -- liveness --------------------------------------------------------

def test_supervisor_not_alive_without_pid_file(cli):
    mod, slug = cli
    assert mod._supervisor_alive(slug) is False


def test_supervisor_alive_with_fresh_heartbeat(cli, monkeypatch):
    mod, slug = cli
    paths = paths_of(mod, slug)
    with open(paths["pid"], "w") as f:
        f.write("12345")
    mod._supervisor_beat(paths)
    monkeypatch.setattr(mod, "_supervisor_pid_alive", lambda p, s: True)
    assert mod._supervisor_alive(slug) is True


def test_supervisor_not_alive_with_stale_heartbeat_and_claim(cli, monkeypatch):
    mod, slug = cli
    paths = paths_of(mod, slug)
    with open(paths["pid"], "w") as f:
        f.write("12345")
    mod._supervisor_beat(paths)
    with open(paths["claim"], "w") as f:
        f.write("0")
    old = time.time() - 1000
    os.utime(paths["heartbeat"], (old, old))
    os.utime(paths["claim"], (old, old))
    monkeypatch.setattr(mod, "_supervisor_pid_alive", lambda p, s: True)
    assert mod._supervisor_alive(slug) is False


def test_supervisor_alive_during_boot_claim_window(cli, monkeypatch):
    mod, slug = cli
    paths = paths_of(mod, slug)
    with open(paths["pid"], "w") as f:
        f.write("12345")
    with open(paths["claim"], "w") as f:
        f.write(f"{time.time():.3f}")
    monkeypatch.setattr(mod, "_supervisor_pid_alive", lambda p, s: True)
    assert mod._supervisor_alive(slug) is True


def test_pid_alive_rejects_garbage_pid_file(cli):
    mod, slug = cli
    paths = paths_of(mod, slug)
    with open(paths["pid"], "w") as f:
        f.write("not-a-pid")
    assert mod._supervisor_pid_alive(paths, slug) is False


# -- snapshot --------------------------------------------------------

def test_snapshot_round_trip(cli):
    mod, slug = cli
    paths = paths_of(mod, slug)
    view = FakeView(state="working", active_turn_id="turn-9",
                    pending_summary="waiting on tool")
    mod._supervisor_write_snapshot(paths, view)
    snap = mod._supervisor_read_snapshot(slug)
    assert snap["state"] == "working"
    assert snap["active_turn_id"] == "turn-9"
    assert snap["pending_summary"] == "waiting on tool"
    assert snap["snapshot_at"] <= time.time()


def test_read_snapshot_malformed(cli):
    mod, slug = cli
    paths = paths_of(mod, slug)
    with open(paths["view"], "w") as f:
        f.write("not json{{{")
    assert mod._supervisor_read_snapshot(slug) is None
    with open(paths["view"], "w") as f:
        f.write("[1, 2]")
    assert mod._supervisor_read_snapshot(slug) is None
    assert mod._supervisor_read_snapshot("no-such-slug") is None


def test_snapshot_view_shim(cli):
    mod, slug = cli
    view = mod._SnapshotView({"state": "blocked_approval",
                              "active_turn_id": "t1",
                              "pending_summary": "p",
                              "last_terminal": None,
                              "last_event_at": 1.5})
    assert view.state == "blocked_approval"
    assert view.active_turn_id == "t1"
    assert view.pending_summary == "p"
    assert view.last_terminal is None
    assert view.last_event_at == 1.5


# -- steer queue ------------------------------------------------------

def test_enqueue_validates(cli):
    mod, slug = cli
    with pytest.raises(RuntimeError):
        mod._supervisor_enqueue_steer(slug, "")
    with pytest.raises(RuntimeError):
        mod._supervisor_enqueue_steer(slug, None)
    with pytest.raises(RuntimeError):
        mod._supervisor_enqueue_steer(slug, "msg", turn_id=123)


def test_drain_steers_matching_live_turn(cli):
    mod, slug = cli
    paths = paths_of(mod, slug)
    turn = FakeTurn()
    host = FakeHost([], client_name="x")
    mod._supervisor_enqueue_steer(slug, "do the thing", turn_id="turn-1")
    view = FakeView(state="working", active_turn_id="turn-1")
    delivered = mod._supervisor_drain_queue(paths, host, "sid-1", turn, view)
    assert delivered == 1
    assert turn.steered == [("sid-1", "do the thing", "turn-1")]
    assert turn.started == []
    with open(paths["queue"]) as f:
        assert f.read() == ""


def test_drain_drops_stale_turn_id(cli):
    mod, slug = cli
    paths = paths_of(mod, slug)
    turn = FakeTurn()
    host = FakeHost([], client_name="x")
    mod._supervisor_enqueue_steer(slug, "wrong turn", turn_id="turn-old")
    view = FakeView(state="working", active_turn_id="turn-1")
    delivered = mod._supervisor_drain_queue(paths, host, "sid-1", turn, view)
    assert delivered == 0
    assert turn.steered == []
    with open(paths["log"]) as f:
        assert "stale steer entry" in f.read()


def test_drain_starts_turn_when_no_live_turn(cli):
    mod, slug = cli
    paths = paths_of(mod, slug)
    turn = FakeTurn()
    host = FakeHost([], client_name="x")
    mod._supervisor_enqueue_steer(slug, "fresh work")
    view = FakeView(state="idle", active_turn_id=None)
    delivered = mod._supervisor_drain_queue(paths, host, "sid-1", turn, view)
    assert delivered == 1
    assert turn.started == [("sid-1", "fresh work")]
    assert view.active_turn_id == "turn-new"


def test_drain_drops_malformed_entries(cli):
    mod, slug = cli
    paths = paths_of(mod, slug)
    with open(paths["queue"], "w") as f:
        f.write("garbage{{{\n")
        f.write(json.dumps({"message": ""}) + "\n")
        f.write(json.dumps({"turn_id": "t", "message": "ok"}) + "\n")
    turn = FakeTurn()
    host = FakeHost([], client_name="x")
    view = FakeView(state="working", active_turn_id="t")
    delivered = mod._supervisor_drain_queue(paths, host, "sid-1", turn, view)
    assert delivered == 1
    assert turn.steered == [("sid-1", "ok", "t")]
    with open(paths["log"]) as f:
        assert f.read().count("malformed steer-queue entry") == 2


# -- held-session translation ----------------------------------------

def test_msp_session_held_error(cli):
    mod, _ = cli
    assert mod._msp_session_held_error(FakeServerError(-32021, "x")) is True
    # Message-only match is deliberately NOT enough: the text also matches
    # unrelated errors (e.g. "address already in use"); only the -32021
    # code routes into the held path.
    assert mod._msp_session_held_error(
        RuntimeError("session already in use by another host")) is False
    assert mod._msp_session_held_error(RuntimeError("boom")) is False
    assert mod._msp_session_held_error(FakeServerError(-32600, "x")) is False


def _held_resume(host, sid):
    raise FakeServerError(-32021, "session already in use")


def test_msp_call_translates_held_when_supervisor_alive(cli, monkeypatch, fakes):
    mod, slug = cli
    fakes["msp_session"].resume_session = _held_resume
    monkeypatch.setattr(mod, "_msp_host_for", lambda s: FakeHost([], client_name="x"))
    monkeypatch.setattr(mod, "_supervisor_alive", lambda s: True)
    job = {"session_uuid": "sid-1"}
    with pytest.raises(mod._MSPSessionHeldElsewhere):
        mod._msp_call(slug, job, lambda host: None)


def test_msp_call_keeps_original_error_without_supervisor(cli, monkeypatch, fakes):
    mod, slug = cli
    fakes["msp_session"].resume_session = _held_resume
    monkeypatch.setattr(mod, "_msp_host_for", lambda s: FakeHost([], client_name="x"))
    monkeypatch.setattr(mod, "_supervisor_alive", lambda s: False)
    job = {"session_uuid": "sid-1"}
    with pytest.raises(FakeServerError):
        mod._msp_call(slug, job, lambda host: None)


# -- terminate --------------------------------------------------------

def test_terminate_refuses_planted_pid(cli):
    mod, slug = cli
    paths = paths_of(mod, slug)
    me = os.getpid()
    with open(paths["pid"], "w") as f:
        f.write(str(me))
    # Our own cmdline is pytest, not `_msp_supervise`: the guard must refuse
    # to signal it.
    assert mod._supervisor_cmdline_matches(paths, me, slug) is False
    mod._supervisor_terminate(slug)
    # Still alive (not SIGTERMed), pid file cleaned up.
    os.kill(me, 0)
    assert not os.path.exists(paths["pid"])


def test_terminate_missing_pid_file_no_raise(cli):
    mod, slug = cli
    mod._supervisor_terminate(slug)


def test_terminate_ignores_garbage_pid(cli):
    mod, slug = cli
    paths = paths_of(mod, slug)
    with open(paths["pid"], "w") as f:
        f.write("999999999")
    mod._supervisor_terminate(slug)
    assert not os.path.exists(paths["pid"])


# -- held-session adapters --------------------------------------------

def _write_job(mod, slug):
    job = {"slug": slug, "state": "active", "started_at": time.time(),
           "transport": "msp", "session_uuid": "sess-1"}
    with open(mod.job_json_path(slug), "w") as f:
        json.dump(job, f)
    return job


def _hold_session(cli_mod, monkeypatch, fakes):
    """Make every attach fail with -32021 and a live supervisor."""
    fakes["msp_session"].resume_session = _held_resume
    monkeypatch.setattr(cli_mod, "_msp_host_for",
                        lambda s: FakeHost([], client_name="x"))
    monkeypatch.setattr(cli_mod, "_supervisor_alive", lambda s: True)


def test_steer_queues_when_held(cli, monkeypatch, fakes, capsys):
    mod, slug = cli
    job = _write_job(mod, slug)
    _hold_session(mod, monkeypatch, fakes)
    paths = paths_of(mod, slug)
    mod._supervisor_write_snapshot(
        paths, FakeView(state="working", active_turn_id="turn-7"))
    import argparse
    rc = mod._msp_steer(job, argparse.Namespace(slug=slug, message="nudge",
                                               allow_secrets=False))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["steered"] == "queued"
    assert out["turn_id"] == "turn-7"
    with open(paths["queue"]) as f:
        entry = json.loads(f.readline())
    assert entry["message"] == "nudge"
    assert entry["turn_id"] == "turn-7"


def test_status_reads_snapshot_when_held(cli, monkeypatch, fakes, capsys):
    mod, slug = cli
    job = _write_job(mod, slug)
    _hold_session(mod, monkeypatch, fakes)
    paths = paths_of(mod, slug)
    mod._supervisor_beat(paths)
    mod._supervisor_write_snapshot(
        paths, FakeView(state="blocked_approval", active_turn_id="turn-7",
                        pending_summary="approve?"))
    import argparse
    rc = mod._msp_status(job, slug, argparse.Namespace(slug=slug, json=True))
    assert rc == 0
    st = json.loads(capsys.readouterr().out)
    assert st["supervisor_held"] is True
    assert st["msp_state"] == "blocked_approval"
    assert st["job_state"] == "blocked"
    assert st["active_turn_id"] == "turn-7"
    assert st["pending"] == "approve?"


def test_watch_held_skips_recovery_ladder(cli, monkeypatch, fakes):
    mod, slug = cli
    job = _write_job(mod, slug)
    _hold_session(mod, monkeypatch, fakes)
    paths = paths_of(mod, slug)
    mod._supervisor_write_snapshot(
        paths, FakeView(state="working", active_turn_id="turn-7"))
    events = []
    mod._watch_msp_job(slug, job, events, time.time())
    assert events == []


def test_watch_held_stalled_needs_attention_not_recovery(cli, monkeypatch, fakes):
    mod, slug = cli
    job = _write_job(mod, slug)
    _hold_session(mod, monkeypatch, fakes)
    paths = paths_of(mod, slug)
    mod._supervisor_write_snapshot(
        paths, FakeView(state="stalled", active_turn_id="turn-7"))
    recover_calls = []
    fakes["msp_recovery"].recover_dead_turn = lambda *a: recover_calls.append(a)
    events = []
    mod._watch_msp_job(slug, job, events, time.time())
    assert len(events) == 1
    assert events[0]["signal"] == "needs-attention"
    assert "supervisor" in events[0]["detail"]
    assert recover_calls == []


def test_resume_reports_supervisor_alive_when_held(cli, monkeypatch, fakes, capsys):
    mod, slug = cli
    _write_job(mod, slug)
    _hold_session(mod, monkeypatch, fakes)
    paths = paths_of(mod, slug)
    mod._supervisor_beat(paths)
    import argparse
    rc = mod._msp_resume(argparse.Namespace(slug=slug))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["resumed"] == "supervisor-alive"
    assert out["supervisor_heartbeat_age_s"] is not None
