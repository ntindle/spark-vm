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

def test_spawn_msp_records_transport_and_session(cli, fakes, monkeypatch):
    slug = "mspjob"
    jd = os.path.join(cli.job_dir(slug), "")
    captured = {}

    def fake_prepare(slug, args, preamble, tmux_name):
        captured["preamble"] = preamble
        captured["tmux_name"] = tmux_name
        os.makedirs(os.path.join(cli.job_dir(slug), "tmp"), exist_ok=True)
        # the real _spawn_prepare writes preamble + body into prompt.md
        with open(os.path.join(cli.job_dir(slug), "prompt.md"), "w") as f:
            f.write(preamble.format(jobdir=cli.job_dir(slug)) + "PROMPT-BODY")
        return ({"slug": slug}, os.path.join(cli.job_dir(slug), "work"),
                cli.job_dir(slug))

    monkeypatch.setattr(cli, "_spawn_prepare", fake_prepare)
    rc = cli._spawn_msp(slug, argparse.Namespace(slug=slug))
    assert rc == 0
    assert captured["preamble"] is cli.PREAMBLE_MSP
    assert "tmux" not in captured["preamble"]
    assert captured["tmux_name"] is None
    job = _read_job(cli, slug)
    assert job["transport"] == "msp"
    assert job["session_uuid"] == "sess-1"
    # serve got the yolo approval mode and the workdir as workspace root
    assert fakes.modules["msp_session"].started["approval_mode"] == "allowAll"
    assert fakes.modules["msp_session"].started["workspace_root"].endswith(
        os.path.join(slug, "work"))
    # the first turn carries the full prompt (preamble + body)
    sid, prompt = fakes.modules["msp_turn"].started_turns[0]
    assert sid == "sess-1"
    assert "over the Muse Session Protocol" in prompt
    assert "PROMPT-BODY" in prompt
    # serve child opened and closed around the spawn
    host = FakeHost.instances[-1]
    assert host.serve_argv == ["muse", "serve"]
    assert host.client_name == "muse_job"
    assert host.closed


def test_spawn_msp_stillborn_dead_first_turn(cli, fakes, monkeypatch):
    # Issue #994: a first turn that dies before engaging must fail the
    # spawn loudly -- the job is marked blocked (never active), the
    # stillborn record is persisted, and TurnStillbornError carries the
    # remediation. This pins the spawn-wiring contract; the unit tests
    # only cover the engagement gate in isolation.
    slug = "mspstill"
    fakes.engagement = {"status": "dead", "terminal": "cancelled",
                        "journal": ["turn/started", "turn/completed"],
                        "elapsed_s": 0.1}

    def fake_prepare(slug, args, preamble, tmux_name):
        os.makedirs(os.path.join(cli.job_dir(slug), "tmp"), exist_ok=True)
        with open(os.path.join(cli.job_dir(slug), "prompt.md"), "w") as f:
            f.write("PROMPT-BODY")
        return ({"slug": slug}, os.path.join(cli.job_dir(slug), "work"),
                cli.job_dir(slug))

    monkeypatch.setattr(cli, "_spawn_prepare", fake_prepare)
    m_turn = fakes.modules["msp_turn"]
    with pytest.raises(m_turn.TurnStillbornError) as excinfo:
        cli._spawn_msp(slug, argparse.Namespace(slug=slug))
    # the watch was subscribed before turn/start (the subscribe-gap fix)
    assert m_turn.watch_calls, "begin_first_turn_watch was not called"
    assert m_turn.awaited[0][1] == "turn-1"
    job = _read_job(cli, slug)
    assert job["state"] == "blocked"
    assert job["stillborn"]["turn_id"] == "turn-1"
    assert job["stillborn"]["terminal"] == "cancelled"
    assert job["stillborn"]["journal"] == ["turn/started", "turn/completed"]
    # the error names the real retry steps: the blocked job dir is kept,
    # so "retry with --tmux" alone would hit "job dir exists"
    msg = str(excinfo.value)
    assert "--tmux" in msg
    assert "new slug" in msg
    # #1026: the two retry paths are pinned with close-first ordering --
    # new-slug (keeps the diagnosis, close archives the blocked record)
    # and same-slug (close tears down worktree+branch, THEN remove dir).
    close_cmd = f"muse-job close {slug}"
    assert msg.count(close_cmd) == 2, f"expected two close paths in: {msg}"
    same_slug_tail = msg.split("same slug")[1]
    assert same_slug_tail.index(close_cmd) < same_slug_tail.index(
        f"remove {cli.job_dir(slug)}"), "same-slug path must close before removing the dir"
    assert "issue #994" in msg
    assert excinfo.value.turn_id == "turn-1"
    assert excinfo.value.terminal == "cancelled"


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


def test_steer_no_active_turn_starts_turn(cli, fakes):
    slug = "mspsteer2"
    _make_job(cli, slug)
    fakes.view = FakeView(state="idle", active_turn_id=None)
    job = _read_job(cli, slug)
    cli._msp_steer(job, argparse.Namespace(slug=slug, message="go",
                                           allow_secrets=False))
    assert fakes.modules["msp_turn"].steered == []
    assert fakes.modules["msp_turn"].started_turns == [("sess-1", "go")]


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
    with open(cli._msp_journal_path(slug), "w") as f:
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
    rc = cli.cmd_resume(argparse.Namespace(slug=slug))
    assert rc == 0
    # fresh session started, re-anchor turn carries the PROGRESS tail
    sid, prompt = fakes.modules["msp_turn"].started_turns[0]
    assert "did the thing" in prompt
    assert "Do NOT repeat" in prompt
    job = _read_job(cli, slug)
    assert job["session_uuid"] == "sess-1"


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
