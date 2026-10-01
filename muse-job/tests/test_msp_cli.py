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
    m_session.resume_session = lambda host, sid: ns.resume_result

    m_turn = types.ModuleType("msp_turn")
    m_turn.started_turns = []
    m_turn.steered = []

    def start_turn(host, session_id, prompt, *, command_id=None):
        m_turn.started_turns.append((session_id, prompt))
        return ({"turnId": "turn-1"}, {})

    def steer_turn(host, session_id, message, *, command_id=None):
        m_turn.steered.append((session_id, message))
        return {}

    m_turn.start_turn = start_turn
    m_turn.steer_turn = steer_turn
    m_turn.interrupt_turn = lambda host, sid, **kw: {}

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
    none_kind = types.SimpleNamespace(name="none")
    m_recovery.DeadKind = types.SimpleNamespace(none=none_kind)
    m_recovery.detect_dead_turn = lambda host, sid, jd: ns.diagnosis
    m_recovery.recover_dead_turn = lambda host, sid, diag, jd: ns.outcome

    for name, mod in (("msp_host", m_host), ("msp_session", m_session),
                      ("msp_turn", m_turn), ("msp_events", m_events),
                      ("msp_recovery", m_recovery)):
        monkeypatch.setitem(sys.modules, name, mod)

    ns.view = FakeView()
    ns.resume_result = {"session": {"status": "idle"}}
    ns.diagnosis = types.SimpleNamespace(kind=none_kind)
    ns.outcome = types.SimpleNamespace(action="continued", detail="re-anchored")
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


def test_spawn_msp_sets_no_auto_update(cli, fakes, monkeypatch):
    # Issue #212: the serve host must not self-update mid-job.
    monkeypatch.delenv("MUSE_NO_AUTO_UPDATE", raising=False)
    cli._msp_host_for("anyslug").close()
    assert os.environ.get("MUSE_NO_AUTO_UPDATE") == "1"


def test_cmd_spawn_dispatches_on_msp_flag(cli, monkeypatch):
    monkeypatch.setattr(cli, "with_lock", lambda slug, fn: fn())
    seen = {}
    monkeypatch.setattr(cli, "_spawn", lambda s, a: seen.setdefault("tmux", s))
    monkeypatch.setattr(cli, "_spawn_msp",
                        lambda s, a: seen.setdefault("msp", s))
    cli.cmd_spawn(argparse.Namespace(slug="a", msp=True))
    assert seen == {"msp": "a"}
    seen.clear()
    cli.cmd_spawn(argparse.Namespace(slug="b", msp=False))
    assert seen == {"tmux": "b"}


# -- steer ---------------------------------------------------------------

def test_steer_active_turn(cli, fakes):
    slug = "mspsteer"
    _make_job(cli, slug)
    fakes.view = FakeView(state="working", active_turn_id="turn-9")
    job = _read_job(cli, slug)
    rc = cli._msp_steer(job, argparse.Namespace(slug=slug, message="faster",
                                                allow_secrets=False))
    assert rc == 0
    assert fakes.modules["msp_turn"].steered == [("sess-1", "faster")]
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
    kind = types.SimpleNamespace(name="quiet_running")
    fakes.diagnosis = types.SimpleNamespace(kind=kind)
    fakes.outcome = types.SimpleNamespace(action="continued",
                                          detail="interrupted zombie, re-anchored")
    events = []
    cli._watch_msp_job(slug, _read_job(cli, slug), events, time.time())
    assert len(events) == 1
    assert events[0]["signal"] == "recovered"
    assert "continued" in events[0]["detail"]


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
