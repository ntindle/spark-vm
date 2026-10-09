"""Tests for issue #227: muse-job v2 CLI wiring over MSP.

The msp_* sibling modules are faked in sys.modules (the CLI imports them
lazily through _msp_imports, so pre-inserted fakes win over the real
files). The fake serve host records every call, pinning the CLI<->MSP
contract without a live `muse serve`. No tmux, no git, no network.
"""
import argparse
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


class FakeHost:
    """Fake MSPHost: records constructor env + every call()."""
    instances = []

    def __init__(self, serve_argv, *, client_name, log_path=None, **kw):
        self.serve_argv = serve_argv
        self.client_name = client_name
        self.log_path = log_path
        self.calls = []
        self.handlers = {}
        self.opened = False
        self.closed = False
        FakeHost.instances.append(self)

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True

    def call(self, method, params):
        self.calls.append((method, params))
        h = self.handlers.get(method)
        if h is None:
            raise AssertionError(f"no fake handler for {method}")
        return h(params)


@pytest.fixture(autouse=True)
def _preserve_no_auto_update():
    # _msp_host_for sets MUSE_NO_AUTO_UPDATE=1 process-wide (issue #212
    # policy); keep it from leaking into sibling test modules --
    # test_tui_update_policy asserts the variable's absence.
    had = os.environ.get("MUSE_NO_AUTO_UPDATE")
    yield
    if had is None:
        os.environ.pop("MUSE_NO_AUTO_UPDATE", None)
    else:
        os.environ["MUSE_NO_AUTO_UPDATE"] = had


@pytest.fixture()
def fakes(monkeypatch):
    """Install fake msp_* modules; return the namespace holding them."""
    FakeHost.instances.clear()
    ns = types.SimpleNamespace(calls=[])

    m_host = types.ModuleType("msp_host")
    m_host.MSPHost = FakeHost

    m_session = types.ModuleType("msp_session")
    m_session.YOLO_APPROVAL_MODE = "allowAll"
    m_session.new_command_id = lambda: "cmd-1"
    started = {}

    def start_session(host, workspace_root, *, approval_mode=None,
                      session_id=None, **kw):
        started["workspace_root"] = workspace_root
        started["approval_mode"] = approval_mode
        return ({"sessionId": "sess-1"}, None)

    m_session.start_session = start_session
    m_session.started = started

    def resume_session(host, sid):
        ns.resume_calls.append(sid)
        return ns.resume_result

    m_session.resume_session = resume_session
    ns.resume_calls = []

    m_turn = types.ModuleType("msp_turn")
    m_turn.started_turns = []
    m_turn.steered = []

    def start_turn(host, session_id, prompt, *, command_id=None):
        m_turn.started_turns.append((session_id, prompt))
        return ({"turnId": "turn-1"}, {})

    def steer_turn(host, session_id, message, *, command_id=None,
                   expected_turn_id=None):
        m_turn.steered.append((session_id, message, expected_turn_id))
        return {}

    m_turn.start_turn = start_turn
    m_turn.steer_turn = steer_turn
    m_turn.interrupt_turn = lambda host, sid, **kw: {}

    # Mirror the REAL msp_turn engagement-gate API shape: the spawn
    # path subscribes BEFORE turn/start (begin_first_turn_watch) and
    # binds the turn id after (await_first_turn_engagement) -- a fake
    # with a different shape would hide call-site/mock drift, the same
    # class that broke the stalled-recovery ladder once before.
    def begin_first_turn_watch(host, session_id):
        m_turn.watch_calls.append((host, session_id))
        return {"fake": "watch"}

    def await_first_turn_engagement(watch, turn_id, *, timeout=None):
        m_turn.awaited.append((watch, turn_id, timeout))
        return ns.engagement

    def close_first_turn_watch(watch):
        m_turn.closed_watches.append(watch)

    class TurnStillbornError(Exception):
        def __init__(self, message, *, turn_id, terminal, journal):
            super().__init__(message)
            self.turn_id = turn_id
            self.terminal = terminal
            self.journal = tuple(journal)

    m_turn.begin_first_turn_watch = begin_first_turn_watch
    m_turn.await_first_turn_engagement = await_first_turn_engagement
    m_turn.close_first_turn_watch = close_first_turn_watch
    m_turn.TurnStillbornError = TurnStillbornError
    # Mirror the REAL terminal-classification API shape: the supervisor
    # loop classifies through _turn_terminal (both wire shapes: the
    # fixture's method-level turn/cancelled and the real serve host's
    # turn/completed + params.terminal -- issue #994) and persists via
    # the vocabulary-gated _terminal_label.
    def _turn_terminal(note, turn_id):
        if not isinstance(note, dict):
            return None
        params = note.get("params")
        if not isinstance(params, dict) or params.get("turnId") != turn_id:
            return None
        method = note.get("method")
        if method == "turn/completed":
            terminal = params.get("terminal")
            if isinstance(terminal, str) and terminal:
                return terminal
            return "completed"
        if method == "turn/cancelled":
            return "cancelled"
        if method == "turn/interrupted":
            return "interrupted"
        return None

    m_turn._turn_terminal = _turn_terminal
    m_turn._terminal_label = lambda t: (
        t if t in ("cancelled", "interrupted", "failed", "completed")
        else "unknown")
    m_turn.watch_calls = []
    m_turn.awaited = []
    m_turn.closed_watches = []
    ns.engagement = {"status": "engaged", "terminal": None, "journal": [],
                     "elapsed_s": 0.0}

    m_events = types.ModuleType("msp_events")
    m_events.polled = []

    def poll_session_view(host, session_id, job_dir, *, replay_wait=2.0,
                          sink=None, **kw):
        m_events.polled.append((session_id, job_dir))
        if sink is not None:
            sink(FakeSignal())
        return ns.view

    m_events.poll_session_view = poll_session_view

    m_recovery = types.ModuleType("msp_recovery")
    # Mirror the REAL msp_recovery API shape (positional (host,
    # session_id, job_dir), RecoveryReport return). A mock with a
    # different shape silently decouples the call site from the module
    # it actually calls in production -- that drift is exactly what
    # broke the stalled-recovery ladder once before.
    m_recovery.ACTION_NONE = "none"
    m_recovery.ACTION_CONTINUED = "continued"
    m_recovery.ACTION_RESUMED = "resumed"
    m_recovery.ACTION_GIVE_UP = "give_up"
    m_recovery.detect_dead_turn = lambda view, **kw: ns.diagnosis
    def fake_recover(host, sid, jd, **kw):
        # Record the positional call shape: the production call site
        # must pass (host, session_id, job_dir) positionally, matching
        # the real recover_dead_turn signature. A mock that accepts
        # anything would hide call-site/mock drift.
        ns.recover_calls.append((host, sid, jd))
        return ns.outcome
    ns.recover_calls = []
    m_recovery.recover_dead_turn = fake_recover

    for name, mod in (("msp_host", m_host), ("msp_session", m_session),
                      ("msp_turn", m_turn), ("msp_events", m_events),
                      ("msp_recovery", m_recovery)):
        monkeypatch.setitem(sys.modules, name, mod)

    ns.view = FakeView()
    ns.resume_result = {"session": {"status": "idle"}}
    ns.diagnosis = None
    ns.outcome = types.SimpleNamespace(action="continued", detail="re-anchored",
                                       attempts=["detected quiet_running"])
    ns.modules = {"msp_turn": m_turn, "msp_session": m_session,
                  "m_events": m_events}
    return ns


@pytest.fixture()
def cli(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_msp", CLI_PATH)


def _make_job(cli, slug, **fields):
    jd = cli.job_dir(slug)
    os.makedirs(os.path.join(jd, "tmp"), exist_ok=True)
    os.makedirs(cli.METADATA_DIR, exist_ok=True)
    job = {"slug": slug, "state": "active", "started_at": time.time(),
           "transport": "msp", "session_uuid": "sess-1"}
    job.update(fields)
    with open(cli.job_json_path(slug), "w") as f:
        json.dump(job, f)
    with open(os.path.join(jd, "prompt.md"), "w") as f:
        f.write("do the thing")
    return jd


def _read_job(cli, slug):
    with open(cli.job_json_path(slug)) as f:
        return json.load(f)


# -- spawn ---------------------------------------------------------------

def test_spawn_msp_records_transport_and_session(cli, fakes, monkeypatch,
                                                 capsys):
    # Issue #1129: spawn no longer drives session/turn itself -- a
    # detached supervisor owns the serve host (the old path SIGTERMed the
    # turn at host.close()). This pins the spawn-wiring contract: the
    # supervisor is launched, its recorded session_uuid is re-read, and
    # the spawn reports the supervised turn id as active.
    slug = "mspjob"
    launched = []

    def fake_prepare(slug, args, preamble, tmux_name):
        os.makedirs(os.path.join(cli.job_dir(slug), "tmp"), exist_ok=True)
        with open(os.path.join(cli.job_dir(slug), "prompt.md"), "w") as f:
            f.write(preamble.format(jobdir=cli.job_dir(slug)) + "PROMPT-BODY")
        return ({"slug": slug}, os.path.join(cli.job_dir(slug), "work"),
                cli.job_dir(slug))

    def fake_launch(slug, prompt=None):
        launched.append((slug, prompt))
        # the supervisor's contract: it records session_uuid itself
        job = cli.load_job(slug)
        job["session_uuid"] = "sess-1"
        cli.save_job(job, slug)
        return {"session_id": "sess-1", "turn_id": "turn-1"}

    monkeypatch.setattr(cli, "_spawn_prepare", fake_prepare)
    monkeypatch.setattr(cli, "_msp_launch_supervisor", fake_launch)
    rc = cli._spawn_msp(slug, argparse.Namespace(slug=slug))
    assert rc == 0
    assert launched == [(slug, None)], "supervisor must be launched once"
    job = _read_job(cli, slug)
    assert job["transport"] == "msp"
    assert job["session_uuid"] == "sess-1"
    out = json.loads(capsys.readouterr().out)
    assert out["slug"] == slug
    assert out["transport"] == "msp"
    assert out["session_id"] == "sess-1"
    assert out["turn_id"] == "turn-1"
    assert out["state"] == "active"
    # no serve host is opened by the spawn path itself anymore
    assert not FakeHost.instances


def test_spawn_reports_blocked_when_supervisor_marked_stillborn(
        cli, fakes, monkeypatch, capsys):
    # Product B4: spawn prints the re-read job state, never a hardcoded
    # "active" -- the supervisor may already have marked a stillborn
    # first turn blocked before spawn's final read.
    slug = "mspblocked"

    def fake_prepare(slug, args, preamble, tmux_name):
        os.makedirs(os.path.join(cli.job_dir(slug), "tmp"), exist_ok=True)
        with open(os.path.join(cli.job_dir(slug), "prompt.md"), "w") as f:
            f.write("PROMPT-BODY")
        return ({"slug": slug}, os.path.join(cli.job_dir(slug), "work"),
                cli.job_dir(slug))

    def fake_launch(slug, prompt=None):
        job = cli.load_job(slug)
        job["session_uuid"] = "sess-1"
        job["state"] = "blocked"
        job["stillborn"] = {"turn_id": "turn-1", "terminal": "cancelled",
                            "journal": ["turn/cancelled"]}
        cli.save_job(job, slug)
        return {"session_id": "sess-1", "turn_id": "turn-1"}

    monkeypatch.setattr(cli, "_spawn_prepare", fake_prepare)
    monkeypatch.setattr(cli, "_msp_launch_supervisor", fake_launch)
    rc = cli._spawn_msp(slug, argparse.Namespace(slug=slug))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["state"] == "blocked"


def test_spawn_msp_supervisor_launch_failure_kills_supervisor(
        cli, fakes, monkeypatch):
    # A supervisor that dies during startup must not leave a half-spawn:
    # spawn kills any supervisor residue and re-raises loudly.
    slug = "mspfail"
    killed = []

    def fake_prepare(slug, args, preamble, tmux_name):
        os.makedirs(os.path.join(cli.job_dir(slug), "tmp"), exist_ok=True)
        with open(os.path.join(cli.job_dir(slug), "prompt.md"), "w") as f:
            f.write("PROMPT-BODY")
        return ({"slug": slug}, os.path.join(cli.job_dir(slug), "work"),
                cli.job_dir(slug))

    def fake_launch(slug, prompt=None):
        raise RuntimeError("supervisor exited during startup")

    monkeypatch.setattr(cli, "_spawn_prepare", fake_prepare)
    monkeypatch.setattr(cli, "_msp_launch_supervisor", fake_launch)
    monkeypatch.setattr(cli, "_msp_kill_supervisor",
                        lambda s: killed.append(s) or True)
    with pytest.raises(RuntimeError, match="exited during startup"):
        cli._spawn_msp(slug, argparse.Namespace(slug=slug))
    assert killed == [slug]


def test_msp_is_held_elsewhere(cli):
    # -32021 is the single-attach refusal (session held by a supervisor).
    class Coded(Exception):
        def __init__(self, code):
            self.code = code
    assert cli._msp_is_held_elsewhere(Coded(-32021))
    assert cli._msp_is_held_elsewhere(Exception("session already in use"))
    assert not cli._msp_is_held_elsewhere(Exception("boom"))
    assert not cli._msp_is_held_elsewhere(Coded(-32600))


def test_enqueue_steer_writes_turn_tagged_entry(cli, fakes):
    # Steer queue entries are tagged with the turn they were queued
    # against so a supervisor never delivers a stale steer to a later
    # turn (flock-guarded append).
    slug = "mspq"
    _make_job(cli, slug)
    cli._msp_enqueue_steer(slug, "nudge the agent", turn_id="turn-9")
    # The steer queue lives in the operator-owned supervisor state dir
    # (issue #1145), not the agent-visible job dir.
    path = cli._msp_supervisor_files(slug)["queue"]
    with open(path) as f:
        entry = json.loads(f.read().strip())
    assert entry["message"] == "nudge the agent"
    assert entry["turn_id"] == "turn-9"
    assert entry["ts"] > 0


def test_supervise_loop_breaks_on_terminal(cli, fakes, monkeypatch):
    # The supervisor loop exits when the turn reaches a terminal state;
    # it heartbeats and snapshots the view on the way out.
    slug = "mspsup"
    jd = _make_job(cli, slug)
    m_turn = fakes.modules["msp_turn"]
    m_turn.watch_turn_events = (
        lambda host, sid, tid, timeout=None:
        [{"method": "turn/completed", "params": {"turnId": tid}}])
    view = FakeView(state="working", active_turn_id="turn-1")
    monkeypatch.setattr(cli, "_msp_poll", lambda host, s, job: view)
    host = FakeHost(["muse", "serve"], client_name="muse_job")
    stop = {"flag": False}
    cli._msp_supervise_loop(slug, {"slug": slug}, host, "sess-1", "turn-1",
                            stop)
    files = cli._msp_supervisor_files(slug)
    assert os.path.exists(files["heartbeat"])
    with open(files["view"]) as f:
        snap = json.load(f)
    assert snap["msp_state"] == "working"
    assert snap["active_turn_id"] == "turn-1"


def test_supervise_loop_marks_stillborn_on_instant_death(cli, fakes,
                                                        monkeypatch):
    # Issue #994's contract under the supervisor design: a first turn
    # that dies before engaging must never sit "active" -- the
    # supervisor marks the job blocked with the stillborn record the
    # watchdog already pages on (same vocabulary as the old spawn path).
    slug = "mspsup2"
    _make_job(cli, slug)
    m_turn = fakes.modules["msp_turn"]
    m_turn.watch_turn_events = (
        lambda host, sid, tid, timeout=None:
        [{"method": "turn/cancelled", "params": {"turnId": tid}}])
    monkeypatch.setattr(cli, "_msp_poll",
                        lambda host, s, job: FakeView(state="working",
                                                     active_turn_id=None))
    host = FakeHost(["muse", "serve"], client_name="muse_job")
    cli._msp_supervise_loop(slug, _read_job(cli, slug), host, "sess-1",
                            "turn-1", {"flag": False})
    job = _read_job(cli, slug)
    assert job["state"] == "blocked"
    assert job["stillborn"]["turn_id"] == "turn-1"
    assert job["stillborn"]["terminal"] == "cancelled"
    assert "turn/cancelled" in job["stillborn"]["journal"]


def test_supervise_loop_leaves_instant_completion_alone(cli, fakes,
                                                       monkeypatch):
    # A turn that *completed* instantly is not stillborn: the done-claim
    # path (SUMMARY.md) owns that outcome, so the supervisor must not
    # mark it blocked.
    slug = "mspsup3"
    _make_job(cli, slug)
    m_turn = fakes.modules["msp_turn"]
    m_turn.watch_turn_events = (
        lambda host, sid, tid, timeout=None:
        [{"method": "turn/completed", "params": {"turnId": tid}}])
    monkeypatch.setattr(cli, "_msp_poll",
                        lambda host, s, job: FakeView(state="working",
                                                     active_turn_id=None))
    host = FakeHost(["muse", "serve"], client_name="muse_job")
    cli._msp_supervise_loop(slug, _read_job(cli, slug), host, "sess-1",
                            "turn-1", {"flag": False})
    job = _read_job(cli, slug)
    assert job["state"] == "active"
    assert "stillborn" not in job


def test_supervise_loop_params_level_cancelled_is_stillborn(
        cli, fakes, monkeypatch):
    # QA B1: the real serve host emits turn/completed with
    # params.terminal="cancelled" (issue #994's journal) -- the loop
    # must classify through _turn_terminal, not raw method matching,
    # or the #994 contract is void against the real server.
    slug = "mspsup5"
    _make_job(cli, slug)
    m_turn = fakes.modules["msp_turn"]
    m_turn.watch_turn_events = (
        lambda host, sid, tid, timeout=None:
        [{"method": "turn/completed",
          "params": {"turnId": tid, "terminal": "cancelled"}}])
    monkeypatch.setattr(cli, "_msp_poll",
                        lambda host, s, job: FakeView(state="working",
                                                     active_turn_id=None))
    host = FakeHost(["muse", "serve"], client_name="muse_job")
    cli._msp_supervise_loop(slug, _read_job(cli, slug), host, "sess-1",
                            "turn-1", {"flag": False})
    job = _read_job(cli, slug)
    assert job["state"] == "blocked"
    assert job["stillborn"]["turn_id"] == "turn-1"
    assert job["stillborn"]["terminal"] == "cancelled"


def test_supervise_loop_no_mark_when_turn_was_active(cli, fakes, monkeypatch):
    # Vacuity pin for the `not saw_active` gate: a turn that engaged
    # and later died is a mid-turn death (recovery ladder territory),
    # not a stillborn first turn.
    slug = "mspsup6"
    _make_job(cli, slug)
    m_turn = fakes.modules["msp_turn"]
    m_turn.watch_turn_events = (
        lambda host, sid, tid, timeout=None:
        [{"method": "turn/cancelled", "params": {"turnId": tid}}])
    monkeypatch.setattr(cli, "_msp_poll",
                        lambda host, s, job: FakeView(state="working",
                                                     active_turn_id="turn-1"))
    host = FakeHost(["muse", "serve"], client_name="muse_job")
    cli._msp_supervise_loop(slug, _read_job(cli, slug), host, "sess-1",
                            "turn-1", {"flag": False})
    job = _read_job(cli, slug)
    assert job["state"] == "active"
    assert "stillborn" not in job


def test_supervise_loop_no_mark_when_stopped(cli, fakes, monkeypatch):
    # Vacuity pin for the `not stop["flag"]` gate: a supervisor torn
    # down by kill/close must not mark stillborn+blocked on its way out
    # (kill's own "killed" save would be followed by a stillborn record
    # the watchdog pages on forever).
    slug = "mspsup7"
    _make_job(cli, slug)
    m_turn = fakes.modules["msp_turn"]
    m_turn.watch_turn_events = (
        lambda host, sid, tid, timeout=None:
        [{"method": "turn/cancelled", "params": {"turnId": tid}}])
    monkeypatch.setattr(cli, "_msp_poll",
                        lambda host, s, job: FakeView(state="working",
                                                     active_turn_id=None))
    host = FakeHost(["muse", "serve"], client_name="muse_job")
    cli._msp_supervise_loop(slug, _read_job(cli, slug), host, "sess-1",
                            "turn-1", {"flag": True})
    job = _read_job(cli, slug)
    assert job["state"] == "active"
    assert "stillborn" not in job


def test_supervise_loop_no_event_death_marks_unknown(cli, fakes, monkeypatch):
    # The polls>=3 no-event break: a turn that vanishes with no
    # terminal event and never engages is still a stillborn, labeled
    # "unknown" via the shared _terminal_label gate.
    slug = "mspsup8"
    _make_job(cli, slug)
    m_turn = fakes.modules["msp_turn"]
    m_turn.watch_turn_events = lambda host, sid, tid, timeout=None: []
    monkeypatch.setattr(cli, "_msp_poll",
                        lambda host, s, job: FakeView(state="working",
                                                     active_turn_id=None))
    host = FakeHost(["muse", "serve"], client_name="muse_job")
    cli._msp_supervise_loop(slug, _read_job(cli, slug), host, "sess-1",
                            "turn-1", {"flag": False})
    job = _read_job(cli, slug)
    assert job["state"] == "blocked"
    assert job["stillborn"]["terminal"] == "unknown"


def test_supervise_loop_exits_on_sustained_poll_failure(
        cli, fakes, monkeypatch):
    # QA B2: the anti-livelock guard counts poll failures -- a dead host
    # (watch returns [], poll raises every time) must exit the loop
    # after 5 consecutive failures instead of heartbeating forever. The
    # loop runs in a daemon thread with a bounded join: on a B2
    # regression the test FAILS loudly instead of hanging the suite
    # (the pre-QA-round shape spun forever here).
    import threading
    slug = "mspsup9"
    _make_job(cli, slug)
    m_turn = fakes.modules["msp_turn"]
    m_turn.watch_turn_events = lambda host, sid, tid, timeout=None: []
    polls = []
    def bad_poll(host, s, job):
        polls.append(1)
        raise RuntimeError("transport dead")
    monkeypatch.setattr(cli, "_msp_poll", bad_poll)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    host = FakeHost(["muse", "serve"], client_name="muse_job")
    t = threading.Thread(
        target=cli._msp_supervise_loop,
        args=(slug, _read_job(cli, slug), host, "sess-1", "turn-1",
              {"flag": False}),
        daemon=True)
    t.start()
    t.join(timeout=15)
    assert not t.is_alive(), \
        "supervisor loop did not exit on sustained poll failure"
    assert len(polls) == 5, f"expected 5 poll attempts, got {len(polls)}"
    # the dead host is released, not heartbeated forever; the never-
    # engaged turn is stillborn (no terminal seen -> unknown)
    job = _read_job(cli, slug)
    assert job["state"] == "blocked"
    assert job["stillborn"]["terminal"] == "unknown"


def test_supervise_loop_stillborn_save_rereads_job(cli, fakes, monkeypatch):
    # QA B4 (first re-read): the stillborn save re-reads the job before
    # writing -- a kill landing mid-turn must not be clobbered back to
    # "active" by the loop's fork-time dict. Pin: a stale marker on the
    # passed-in dict must NOT reach the saved record.
    slug = "mspsup10"
    _make_job(cli, slug)
    m_turn = fakes.modules["msp_turn"]
    m_turn.watch_turn_events = (
        lambda host, sid, tid, timeout=None:
        [{"method": "turn/cancelled", "params": {"turnId": tid}}])
    monkeypatch.setattr(cli, "_msp_poll",
                        lambda host, s, job: FakeView(state="working",
                                                     active_turn_id=None))
    host = FakeHost(["muse", "serve"], client_name="muse_job")
    saved = []
    real_save = cli.save_job
    def spy(job, s):
        saved.append(dict(job))
        return real_save(job, s)
    monkeypatch.setattr(cli, "save_job", spy)
    stale = _read_job(cli, slug)
    stale["_qa_stale_marker"] = True  # fork-time dict; disk lacks it
    cli._msp_supervise_loop(slug, stale, host, "sess-1", "turn-1",
                            {"flag": False})
    stillborn_saves = [j for j in saved if "stillborn" in j]
    assert stillborn_saves, "expected the stillborn save to fire"
    fresh = stillborn_saves[-1]
    assert "_qa_stale_marker" not in fresh, \
        "stillborn save wrote the stale fork-time dict, not a re-read"
    assert fresh["state"] == "blocked"
    assert fresh["stillborn"]["turn_id"] == "turn-1"


def test_supervise_cmd_session_save_rereads_job(cli, fakes, monkeypatch):
    # QA B4 (second re-read): _msp_supervise_cmd re-reads the job before
    # the session save -- an operator kill landing during session/turn
    # startup must not be clobbered back to "active". Pin: the kill's
    # marker, written to disk mid-startup, must reach the saved record.
    slug = "mspsup11"
    _make_job(cli, slug)
    m_turn = fakes.modules["msp_turn"]
    m_turn.watch_turn_events = (
        lambda host, sid, tid, timeout=None:
        [{"method": "turn/completed", "params": {"turnId": tid}}])
    monkeypatch.setattr(cli, "_msp_poll",
                        lambda host, s, job: FakeView(state="working",
                                                     active_turn_id="turn-1"))
    # trusted_job_paths is orthogonal to the re-read; stub it so this
    # test stays about the save, not git-worktree plumbing.
    monkeypatch.setattr(cli, "trusted_job_paths",
                        lambda s, j: (os.path.join(cli.job_dir(s), "work"),
                                      "qa-repo", "job/" + s))
    orig_start = m_turn.start_turn
    def start_turn_with_kill(host, sid, prompt, *, command_id=None, **kw):
        # The operator's kill lands during session/turn startup: the
        # on-disk job is now newer than the cmd's fork-time dict.
        job = cli.load_job(slug)
        job["state"] = "killed"
        job["_qa_kill_marker"] = True
        cli.save_job(job, slug)
        return orig_start(host, sid, prompt, command_id=command_id, **kw)
    monkeypatch.setattr(m_turn, "start_turn", start_turn_with_kill)
    saved = []
    real_save = cli.save_job
    def spy(job, s):
        saved.append(dict(job))
        return real_save(job, s)
    monkeypatch.setattr(cli, "save_job", spy)
    cli._msp_supervise_cmd(argparse.Namespace(slug=slug))
    session_saves = [j for j in saved if "session_started_at" in j]
    assert session_saves, "expected the supervisor session save to fire"
    fresh = session_saves[-1]
    assert fresh["state"] == "killed", \
        "session save clobbered the operator kill back to active"
    assert fresh.get("_qa_kill_marker") is True, \
        "session save wrote the stale fork-time dict, not a re-read"


def test_msp_turn_terminal_classification_real_module(cli, fakes,
                                                      monkeypatch):
    # QA B3: the suite fakes msp_turn, so the B1 regression test only
    # exercised a hand-written mirror of _turn_terminal. Pin the REAL
    # module (same SourceFileLoader mechanism as the CLI) so
    # classifier drift breaks CI, not production.
    monkeypatch.delitem(sys.modules, "msp_turn", raising=False)
    monkeypatch.delitem(sys.modules, "msp_session", raising=False)
    monkeypatch.delitem(sys.modules, "msp_host", raising=False)
    bin_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "bin"))
    monkeypatch.syspath_prepend(bin_dir)
    real = load_script("msp_turn_real_qa_b3",
                       os.path.join(bin_dir, "msp_turn.py"))
    t = real._turn_terminal
    # params-level shape (real serve host -- issue #994's journal)
    assert t({"method": "turn/completed",
              "params": {"turnId": "x", "terminal": "cancelled"}},
             "x") == "cancelled"
    assert t({"method": "turn/completed",
              "params": {"turnId": "x", "terminal": "failed"}},
             "x") == "failed"
    assert t({"method": "turn/completed",
              "params": {"turnId": "x", "terminal": "weird-new-shape"}},
             "x") == "weird-new-shape"
    assert t({"method": "turn/completed", "params": {"turnId": "x"}},
             "x") == "completed"
    assert t({"method": "turn/completed",
              "params": {"turnId": "x", "terminal": ""}},
             "x") == "completed"
    # method-level shape (fixture)
    assert t({"method": "turn/cancelled", "params": {"turnId": "x"}},
             "x") == "cancelled"
    assert t({"method": "turn/interrupted", "params": {"turnId": "x"}},
             "x") == "interrupted"
    # turnId filtering + malformed shapes classify None
    assert t({"method": "turn/cancelled", "params": {"turnId": "y"}},
             "x") is None
    assert t({"method": "turn/cancelled"}, "x") is None
    assert t("not-a-dict", "x") is None
    assert t({"method": "turn/completed", "params": "nope"}, "x") is None
    assert t({"method": "turn/evaporated", "params": {"turnId": "x"}},
             "x") is None
    # _terminal_label vocabulary gate
    lab = real._terminal_label
    for ok in ("cancelled", "interrupted", "failed", "completed"):
        assert lab(ok) == ok
    assert lab("bogus") == "unknown"
    assert lab(None) == "unknown"
    assert lab("") == "unknown"


def test_spawn_msp_stillborn_contract_superseded_note(cli, fakes, monkeypatch):
    # Issue #1129 supersedes the #994 spawn-time engagement gate: the
    # supervisor -- not the spawn CLI -- owns turn/start, so there is no
    # begin_first_turn_watch / await_first_turn_engagement /
    # TurnStillbornError on the spawn path anymore. A turn that dies
    # instantly is observed by the supervisor loop (instant-death break),
    # and the engagement gate stays unit-tested in test_msp_turn.py.
    # This test pins that the old spawn-time stillborn machinery is NOT
    # invoked: spawn must not touch the watch API at all.
    slug = "mspstill"
    m_turn = fakes.modules["msp_turn"]

    def fake_prepare(slug, args, preamble, tmux_name):
        os.makedirs(os.path.join(cli.job_dir(slug), "tmp"), exist_ok=True)
        with open(os.path.join(cli.job_dir(slug), "prompt.md"), "w") as f:
            f.write("PROMPT-BODY")
        return ({"slug": slug}, os.path.join(cli.job_dir(slug), "work"),
                cli.job_dir(slug))

    def fake_launch(slug, prompt=None):
        job = cli.load_job(slug)
        job["session_uuid"] = "sess-1"
        cli.save_job(job, slug)
        return {"session_id": "sess-1", "turn_id": "turn-1"}

    monkeypatch.setattr(cli, "_spawn_prepare", fake_prepare)
    monkeypatch.setattr(cli, "_msp_launch_supervisor", fake_launch)
    rc = cli._spawn_msp(slug, argparse.Namespace(slug=slug))
    assert rc == 0
    assert not m_turn.watch_calls, "spawn must not use the first-turn watch"
    assert not m_turn.awaited, "spawn must not await engagement"
    job = _read_job(cli, slug)
    assert "stillborn" not in job


def test_spawn_msp_sets_no_auto_update(cli, fakes, monkeypatch):
    # Issue #212: the serve host must not self-update mid-job.
    monkeypatch.delenv("MUSE_NO_AUTO_UPDATE", raising=False)
    cli._msp_host_for("anyslug").close()
    assert os.environ.get("MUSE_NO_AUTO_UPDATE") == "1"


def test_cmd_spawn_dispatches_on_tmux_flag(cli, monkeypatch):
    # MSP is the default transport (issue #228); --tmux opts back into
    # the legacy TUI-pane path.
    monkeypatch.setattr(cli, "with_lock", lambda slug, fn: fn())
    seen = {}
    monkeypatch.setattr(cli, "_spawn", lambda s, a: seen.setdefault("tmux", s))
    monkeypatch.setattr(cli, "_spawn_msp",
                        lambda s, a: seen.setdefault("msp", s))
    cli.cmd_spawn(argparse.Namespace(slug="a", tmux=True,
                                     repo="https://example.com/r.git"))
    assert seen == {"tmux": "a"}
    seen.clear()
    cli.cmd_spawn(argparse.Namespace(slug="b", tmux=False,
                                     repo="https://example.com/r.git"))
    assert seen == {"msp": "b"}
    seen.clear()
    # Older callers build the Namespace without the flag: still MSP.
    cli.cmd_spawn(argparse.Namespace(slug="c",
                                     repo="https://example.com/r.git"))
    assert seen == {"msp": "c"}


# -- steer ---------------------------------------------------------------

def test_steer_active_turn(cli, fakes):
    slug = "mspsteer"
    _make_job(cli, slug)
    fakes.view = FakeView(state="working", active_turn_id="turn-9")
    job = _read_job(cli, slug)
    rc = cli._msp_steer(job, argparse.Namespace(slug=slug, message="faster",
                                                allow_secrets=False))
    assert rc == 0
    assert fakes.modules["msp_turn"].steered == [("sess-1", "faster", "turn-9")]
    assert fakes.modules["msp_turn"].started_turns == []


def test_steer_no_active_turn_launches_supervisor(cli, fakes, monkeypatch,
                                                  capsys):
    # Issue #1129: with no supervisor and no live turn, steer launches a
    # FRESH supervised turn carrying the message as its prompt -- starting
    # the turn on the ephemeral steer host would reintroduce the old
    # spawn bug (the turn dies at host.close()).
    slug = "mspsteer2"
    _make_job(cli, slug)
    fakes.view = FakeView(state="idle", active_turn_id=None)
    launched = []
    monkeypatch.setattr(cli, "_msp_launch_supervisor",
                        lambda s, prompt=None: launched.append((s, prompt))
                        or {"turn_id": "turn-9"})
    job = _read_job(cli, slug)
    rc = cli._msp_steer(job, argparse.Namespace(slug=slug, message="go",
                                               allow_secrets=False))
    assert rc == 0
    assert fakes.modules["msp_turn"].steered == []
    assert fakes.modules["msp_turn"].started_turns == [], \
        "no turn may start on the ephemeral steer host"
    assert launched == [(slug, "go")]
    out = json.loads(capsys.readouterr().out)
    assert out["started_turn"] == "turn-9"


def test_steer_queues_with_turn_id_when_supervisor_alive(
        cli, fakes, monkeypatch, capsys):
    # Product B3: the queued output names the turn the steer was queued
    # against, so the operator can confirm the target.
    slug = "mspsteer3"
    _make_job(cli, slug)
    enqueued = []
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    monkeypatch.setattr(cli, "_msp_read_snapshot",
                        lambda s: {"active_turn_id": "turn-7", "t": 0})
    monkeypatch.setattr(cli, "_msp_enqueue_steer",
                        lambda s, m, turn_id=None: enqueued.append(
                            (s, m, turn_id)))
    job = _read_job(cli, slug)
    rc = cli._msp_steer(job, argparse.Namespace(slug=slug, message="go",
                                               allow_secrets=False))
    assert rc == 0
    assert enqueued == [(slug, "go", "turn-7")]
    out = json.loads(capsys.readouterr().out)
    assert out == {"slug": slug, "steer": "queued", "turn_id": "turn-7"}


def test_supervisor_forget_only_unlinks_own_pidfile(cli, fakes):
    # Security B1: a supervisor exiting without ever writing its pidfile
    # (failed startup, hand-invoked duplicate) must not delete the live
    # supervisor's pidfile on its way out.
    slug = "mspforget"
    _make_job(cli, slug)
    pidfile = cli._msp_supervisor_files(slug)["pid"]
    with open(pidfile, "w") as f:
        f.write("99999")
    cli._msp_supervisor_forget(slug, pid=os.getpid())
    assert os.path.exists(pidfile), "another supervisor's pidfile unlinked!"
    cli._msp_supervisor_forget(slug, pid=99999)
    assert not os.path.exists(pidfile)


def test_supervisor_files_live_in_metadata_dir_not_job_dir(cli, fakes):
    # Issue #1145: supervisor state must never live in the agent-visible
    # job dir -- _msp_supervisor_dir is the single source of truth, and
    # a regression here silently re-exposes the pidfile/started-record/
    # heartbeat attack surface the B1/B2/B3 tests don't pin.
    slug = "msploc"
    _make_job(cli, slug)
    md = os.path.abspath(cli.METADATA_DIR)
    jd = os.path.abspath(cli.job_dir(slug))
    for name, path in cli._msp_supervisor_files(slug).items():
        ap = os.path.abspath(path)
        assert ap.startswith(md + os.sep), f"{name} outside METADATA_DIR"
        assert not ap.startswith(jd + os.sep), \
            f"{name} in agent-visible job dir"


def test_supervisor_alive_rejects_non_supervisor_pid(cli, fakes):
    # Security B2: a pidfile naming a live non-supervisor pid (stale pid
    # reuse or planted) must not read as alive -- and must not authorize
    # a signal. The pidfile is dropped as bogus.
    slug = "mspalive"
    _make_job(cli, slug)
    pidfile = cli._msp_supervisor_files(slug)["pid"]
    with open(pidfile, "w") as f:
        f.write(str(os.getpid()))  # live, but not a supervisor
    assert not cli._msp_supervisor_alive(slug)
    assert not os.path.exists(pidfile), "bogus pidfile not dropped"


def test_launch_join_instead_of_fork(cli, fakes, monkeypatch):
    # Security B3: a concurrent launcher that loses the race joins the
    # winner's turn instead of forking a duplicate supervisor; a prompt
    # it carries is delivered as a steer so it isn't silently dropped.
    # (Aliveness is a separate guard, pinned by the tests below; here
    # the winner is alive.)
    slug = "mspjoin"
    _make_job(cli, slug)
    files = cli._msp_supervisor_files(slug)
    with open(files["started"], "w") as f:
        json.dump({"session_id": "sess-9", "turn_id": "turn-9"}, f)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    forks = []
    monkeypatch.setattr(cli.subprocess, "Popen",
                        lambda *a, **k: forks.append(a) or None)
    enqueued = []
    monkeypatch.setattr(cli, "_msp_enqueue_steer",
                        lambda s, m, turn_id=None: enqueued.append(
                            (s, m, turn_id)))
    started = cli._msp_launch_supervisor(slug, prompt="late steer")
    assert started == {"session_id": "sess-9", "turn_id": "turn-9"}
    assert forks == [], "duplicate supervisor forked!"
    assert enqueued == [(slug, "late steer", "turn-9")]


def test_launch_join_requires_alive_supervisor(cli, fakes, monkeypatch):
    # Security B2 (phantom join): a fresh started record from a crashed
    # winner authorizes nothing -- the loser must fork instead of
    # joining a turn that doesn't exist.
    slug = "mspjoin2"
    _make_job(cli, slug)
    files = cli._msp_supervisor_files(slug)
    with open(files["started"], "w") as f:
        json.dump({"session_id": "sess-9", "turn_id": "turn-9"}, f)
    with open(files["pid"], "w") as f:
        f.write("999999999")  # dead pid: no supervisor alive
    forks = []
    def fake_popen(*a, **k):
        forks.append(a)
        with open(files["started"], "w") as f:
            json.dump({"session_id": "sess-new", "turn_id": "turn-new"}, f)
        return types.SimpleNamespace(terminate=lambda: None, poll=lambda: 0)
    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)
    enqueued = []
    monkeypatch.setattr(cli, "_msp_enqueue_steer",
                        lambda s, m, turn_id=None: enqueued.append(
                            (s, m, turn_id)))
    started = cli._msp_launch_supervisor(slug, prompt="late steer")
    assert len(forks) == 1, "phantom join: loser must fork, not join"
    assert started == {"session_id": "sess-new", "turn_id": "turn-new"}
    assert enqueued == [], "carried prompt must not enqueue on fork"


def test_launch_join_rejects_malformed_started_record(cli, fakes,
                                                      monkeypatch):
    # Security B2 (cross-turn steer leak): the job dir is agent-writable
    # (issue #11), so a started record without a turn_id must never
    # authorize a join -- the carried prompt would enqueue with
    # turn_id=None and the drain would deliver it to a LATER turn.
    # (The winner is alive here: this is the actual attack shape -- an
    # agent plants a malformed record while a real supervisor runs.)
    slug = "mspjoin3"
    _make_job(cli, slug)
    files = cli._msp_supervisor_files(slug)
    with open(files["started"], "w") as f:
        json.dump({"session_id": "sess-9"}, f)  # turn_id missing
    with open(files["pid"], "w") as f:
        f.write(str(os.getpid()))
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    forks = []
    def fake_popen(*a, **k):
        forks.append(a)
        with open(files["started"], "w") as f:
            json.dump({"session_id": "sess-new", "turn_id": "turn-new"}, f)
        return types.SimpleNamespace(terminate=lambda: None, poll=lambda: 0)
    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)
    enqueued = []
    monkeypatch.setattr(cli, "_msp_enqueue_steer",
                        lambda s, m, turn_id=None: enqueued.append(
                            (s, m, turn_id)))
    started = cli._msp_launch_supervisor(slug, prompt="late steer")
    assert len(forks) == 1, "malformed record must not authorize a join"
    assert started == {"session_id": "sess-new", "turn_id": "turn-new"}
    assert enqueued == [], "no None-tagged steer may enqueue"


def test_read_started_rejects_bad_records(cli, fakes):
    # _msp_read_started fails closed on every malformed shape: missing
    # session_id, missing turn_id, non-dict JSON, unparseable JSON,
    # stale mtime. Absent file was already covered (returns None).
    slug = "mspjoin4"
    _make_job(cli, slug)
    files = cli._msp_supervisor_files(slug)
    cases = [
        {"session_id": "s"},                        # no turn_id
        {"turn_id": "t"},                           # no session_id
        {"session_id": "", "turn_id": "t"},         # empty session_id
        {"session_id": "s", "turn_id": ""},         # empty turn_id
        ["not", "a", "dict"],                       # non-dict JSON
        "just a string",
    ]
    for i, record in enumerate(cases):
        with open(files["started"], "w") as f:
            json.dump(record, f)
        assert cli._msp_read_started(slug, 10) is None, f"case {i}: {record}"
    with open(files["started"], "w") as f:
        f.write("{not json")
    assert cli._msp_read_started(slug, 10) is None
    # stale mtime: valid shape, 0s window
    with open(files["started"], "w") as f:
        json.dump({"session_id": "s", "turn_id": "t"}, f)
    old = time.time() - 100
    os.utime(files["started"], (old, old))
    assert cli._msp_read_started(slug, 10) is None
    # and the happy path still reads
    with open(files["started"], "w") as f:
        json.dump({"session_id": "s", "turn_id": "t"}, f)
    assert cli._msp_read_started(slug, 10) == {"session_id": "s",
                                              "turn_id": "t"}


def test_supervisor_forget_keeps_replaced_pidfile(cli, fakes):
    # Security B1: forget(pid) unlinks only while the pidfile still
    # names that pid -- a pidfile replaced (concurrent supervisor)
    # between observation and forget must survive.
    slug = "mspforget"
    _make_job(cli, slug)
    files = cli._msp_supervisor_files(slug)
    dead = 999999999
    with open(files["pid"], "w") as f:
        f.write(str(dead))
    cli._msp_supervisor_forget(slug, dead)
    assert not os.path.exists(files["pid"])
    # replaced between observation and forget: survives
    with open(files["pid"], "w") as f:
        f.write(str(dead))
    with open(files["pid"], "w") as f:
        f.write(str(os.getpid()))
    cli._msp_supervisor_forget(slug, dead)
    with open(files["pid"]) as f:
        assert f.read().strip() == str(os.getpid())


def test_kill_supervisor_stale_path_passes_observed_pid(cli, fakes,
                                                        monkeypatch):
    # Security B1 (3599 path): the stale-forget re-reads the pidfile and
    # passes the observed pid instead of blindly unlinking; garbage
    # falls back to unconditional (it can name nothing alive). Pin the
    # argument, not just the outcome -- the old unconditional shape
    # passes pid=None.
    slug = "mspkill3"
    _make_job(cli, slug)
    files = cli._msp_supervisor_files(slug)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: False)
    calls = []
    real_forget = cli._msp_supervisor_forget
    def spy(s, pid=None):
        calls.append(pid)
        return real_forget(s, pid)
    monkeypatch.setattr(cli, "_msp_supervisor_forget", spy)
    with open(files["pid"], "w") as f:
        f.write("999999999")
    assert cli._msp_kill_supervisor(slug) is False
    assert calls == [999999999], f"expected forget(pid=observed), got {calls}"
    assert not os.path.exists(files["pid"])
    with open(files["pid"], "w") as f:
        f.write("garbage")
    assert cli._msp_kill_supervisor(slug) is False
    assert calls == [999999999, None], \
        f"garbage must fall back to unconditional, got {calls}"
    assert not os.path.exists(files["pid"])


# -- status / log ----------------------------------------------------------

def test_status_maps_blocked_and_renders_pending(cli, fakes, capsys):
    slug = "mspstatus"
    _make_job(cli, slug)
    fakes.view = FakeView(state="blocked_approval",
                          pending_summary="approve: rm -rf /tmp/x")
    job = _read_job(cli, slug)
    rc = cli.cmd_status(argparse.Namespace(slug=slug, json=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert "transport=msp" in out
    assert "blocked_approval" in out
    assert "approve: rm -rf /tmp/x" in out
    assert _read_job(cli, slug)["state"] == "blocked"


def test_log_renders_redacted_journal(cli, fakes):
    slug = "msplog"
    _make_job(cli, slug)
    jp = cli._msp_journal_path(slug)
    os.makedirs(os.path.dirname(jp), exist_ok=True)
    with open(jp, "w") as f:
        f.write(json.dumps({"t": 1700000000, "kind": "approval",
                            "method": "approval/requested",
                            "detail": "1 pending"}) + "\n")
    rc = cli.cmd_log(argparse.Namespace(slug=slug, n=10))
    assert rc == 0


def test_tmux_path_unchanged_without_transport(cli, fakes, monkeypatch):
    # A legacy record (no transport) keeps the tmux status path.
    slug = "legacyj"
    _make_job(cli, slug, transport=None)
    job = _read_job(cli, slug)
    del job["transport"]
    with open(cli.job_json_path(slug), "w") as f:
        json.dump(job, f)
    seen = {}
    monkeypatch.setattr(cli, "job_status",
                        lambda j, s: seen.setdefault("tmux", s) or {})
    # job_status stub returns {} -> cmd_status would crash on the tmux
    # render; the point is only which branch was taken.
    try:
        cli.cmd_status(argparse.Namespace(slug=slug, json=True))
    except Exception:
        pass
    assert seen == {"tmux": slug}
    assert fakes.modules["m_events"].polled == []


# -- kill / resume ---------------------------------------------------------

def test_kill_deletes_session_and_marks_killed(cli, fakes, capsys):
    slug = "mspkill"
    _make_job(cli, slug)
    rc = cli.cmd_kill(argparse.Namespace(slug=slug))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["state"] == "killed"
    assert out["transport"] == "msp"
    host = FakeHost.instances[-1]
    deletes = [c for c in host.calls if c[0] == "session/delete"]
    assert len(deletes) == 1
    assert deletes[0][1]["sessionId"] == "sess-1"
    assert deletes[0][1]["commandId"] == "cmd-1"
    assert _read_job(cli, slug)["state"] == "killed"


def test_resume_resumes_session(cli, fakes, capsys):
    slug = "mspresume"
    _make_job(cli, slug)
    rc = cli.cmd_resume(argparse.Namespace(slug=slug))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["resumed"] == "sess-1"
    assert _read_job(cli, slug)["state"] == "active"
    # The resume command manages the session lifecycle itself: exactly one
    # resume_session call (no double-resume from _msp_call's pre_resume).
    assert fakes.resume_calls == ["sess-1"]


def test_msp_call_pre_resumes_session(cli, fakes, monkeypatch):
    """_msp_call resumes the recorded session on the fresh host before fn."""
    slug = "msppreresume"
    _make_job(cli, slug)
    job = _read_job(cli, slug)
    seen = []

    def go(host):
        seen.append("go")
        return "ok"

    assert cli._msp_call(slug, job, go) == "ok"
    assert fakes.resume_calls == ["sess-1"]
    assert seen == ["go"]


def test_resume_fallback_fresh_on_gone_session(cli, fakes, monkeypatch):
    # Issue #1129: a gone session relaunches under a supervisor -- the
    # re-anchor turn must be held by the supervisor, never by the
    # ephemeral resume host (which would die at close, the old bug).
    slug = "mspresume2"
    _make_job(cli, slug)

    def gone(host, sid):
        raise RuntimeError("session not found: sess-1")

    monkeypatch.setattr(sys.modules["msp_session"], "resume_session", gone)
    work = os.path.join(cli.job_dir(slug), "work")
    monkeypatch.setattr(cli, "trusted_job_paths",
                        lambda s, j: (work, "/repos/x", f"job/{s}"))
    with open(os.path.join(cli.job_dir(slug), "PROGRESS.md"), "w") as f:
        f.write("did the thing\n")
    launched = []

    def fake_launch(slug, prompt=None):
        launched.append((slug, prompt))
        # the supervisor's contract: it records the new session itself
        job = cli.load_job(slug)
        job["session_uuid"] = "sess-2"
        cli.save_job(job, slug)
        return {"session_id": "sess-2", "turn_id": "turn-2"}

    monkeypatch.setattr(cli, "_msp_launch_supervisor", fake_launch)
    rc = cli.cmd_resume(argparse.Namespace(slug=slug))
    assert rc == 0
    # the re-anchor prompt carries the PROGRESS tail, delivered via the
    # supervisor -- nothing starts on the ephemeral host
    assert len(launched) == 1
    assert launched[0][0] == slug
    assert "did the thing" in launched[0][1]
    assert "Do NOT repeat" in launched[0][1]
    assert fakes.modules["msp_turn"].started_turns == []
    job = _read_job(cli, slug)
    assert job["session_uuid"] == "sess-2"


# -- watch -----------------------------------------------------------------

def test_watch_stalled_runs_recovery_ladder(cli, fakes):
    slug = "mspwatch"
    _make_job(cli, slug)
    fakes.view = FakeView(state="stalled", active_turn_id="turn-1")
    fakes.outcome = types.SimpleNamespace(action="continued",
                                          detail="interrupted zombie, re-anchored",
                                          attempts=["detected quiet_running"])
    events = []
    cli._watch_msp_job(slug, _read_job(cli, slug), events, time.time())
    assert len(events) == 1
    assert events[0]["signal"] == "recovered"
    assert "continued" in events[0]["detail"]
    # The call site must invoke the real positional signature
    # (host, session_id, job_dir) -- the draft-API bug passed a
    # diagnosis object positionally instead.
    assert len(fakes.recover_calls) == 1
    host_arg, sid_arg, jd_arg = fakes.recover_calls[0]
    assert jd_arg == cli.job_dir(slug)
    assert sid_arg == _read_job(cli, slug)["session_uuid"]


def test_watch_stalled_recovery_none_is_silent(cli, fakes):
    # recover_dead_turn returning ACTION_NONE ("nothing dead; no action
    # taken") must emit no event -- the ladder ran and found nothing.
    slug = "mspwatch4"
    _make_job(cli, slug)
    fakes.view = FakeView(state="stalled", active_turn_id="turn-1")
    fakes.outcome = types.SimpleNamespace(action="none", detail="",
                                          attempts=[])
    events = []
    cli._watch_msp_job(slug, _read_job(cli, slug), events, time.time())
    assert events == []


def test_watch_stalled_recovery_give_up_pages(cli, fakes):
    # An unrecoverable stall must page the operator, not claim recovery.
    slug = "mspwatch5"
    _make_job(cli, slug)
    fakes.view = FakeView(state="stalled", active_turn_id="turn-1")
    fakes.outcome = types.SimpleNamespace(action="give_up",
                                          detail="ladder exhausted",
                                          attempts=["detected turn_failed"])
    events = []
    cli._watch_msp_job(slug, _read_job(cli, slug), events, time.time())
    assert len(events) == 1
    assert events[0]["signal"] == "needs-attention"
    assert "give_up" in events[0]["detail"]


def test_watch_blocked_approval_pages(cli, fakes):
    slug = "mspwatch2"
    _make_job(cli, slug)
    fakes.view = FakeView(state="blocked_approval",
                          pending_summary="approve: deploy")
    events = []
    cli._watch_msp_job(slug, _read_job(cli, slug), events, time.time())
    assert events[0]["signal"] == "blocked"
    assert "deploy" in events[0]["detail"]
    assert _read_job(cli, slug)["state"] == "blocked"


def test_watch_done_claim_on_completed_turn(cli, fakes):
    slug = "mspwatch3"
    _make_job(cli, slug)
    with open(os.path.join(cli.job_dir(slug), "SUMMARY.md"), "w") as f:
        f.write("all done")
    fakes.view = FakeView(state="idle", active_turn_id=None,
                          last_terminal="completed")
    events = []
    cli._watch_msp_job(slug, _read_job(cli, slug), events, time.time())
    assert events[0]["signal"] == "done"


def test_watch_stillborn_carries_two_path_retry_advice(cli, fakes):
    # Issue #1029: the stillborn short-circuit's needs-attention signal
    # must carry the same two-path retry as the TurnStillbornError and
    # the README stillborn-spawn section -- a bare "retry spawn with
    # --tmux" is actively wrong on the same slug, because _spawn_prepare
    # refuses a slug whose job dir still exists.
    slug = "stillbornretry"
    _make_job(cli, slug, state="blocked",
              stillborn={"turn_id": "turn-1", "terminal": "cancelled",
                         "journal": ["turn/started", "turn/completed"]})
    events = []
    cli._watch_msp_job(slug, _read_job(cli, slug), events, time.time())
    assert len(events) == 1
    assert events[0]["signal"] == "needs-attention"
    detail = events[0]["detail"]
    assert "'cancelled'" in detail
    # New-slug path (keeps the diagnosis record).
    assert "`muse-job spawn <new-slug> --tmux`" in detail
    assert f"`muse-job close {slug}`" in detail
    # Same-slug path: close first, then remove the job dir, then spawn.
    assert f"`muse-job close {slug}` first" in detail
    assert "remove the job dir" in detail
    assert f"`muse-job spawn {slug} --tmux`" in detail
    # The advice must never pretend a same-dir same-slug spawn works.
    assert "retry spawn with --tmux or" not in detail
    # The job must stay blocked, untouched by the poll machinery.
    assert _read_job(cli, slug)["state"] == "blocked"
    assert _read_job(cli, slug)["stillborn"]["terminal"] == "cancelled"


def test_watch_stillborn_gates_unknown_terminal(cli, fakes):
    # The vocabulary gate on the signal detail must survive the #1029
    # rewording: a hostile terminal string never reaches the detail.
    slug = "stillbornweird"
    _make_job(cli, slug, state="blocked",
              stillborn={"turn_id": "turn-1", "terminal": "EVIL\nline",
                         "journal": ["turn/started"]})
    events = []
    cli._watch_msp_job(slug, _read_job(cli, slug), events, time.time())
    assert len(events) == 1
    assert "EVIL" not in events[0]["detail"]
    assert "'unknown'" in events[0]["detail"]
