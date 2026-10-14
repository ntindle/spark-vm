"""Regression tests for issue #41 (watch recovery outside the per-job lock).

`muse-job watch` used to run the multi-minute recovery (tmux `cmd_resume`:
sleeps, pane probes, up to 90s of session re-discovery; the MSP recovery
ladder) INSIDE the per-job lock, so `steer` -- which takes the same lock --
blocked for minutes behind a dead job. The pass is now two phases:
monitoring under the lock queues a recovery request, and phase 2 runs the
recovery after the lock is released. These tests pin the split:

- the lock is FREE while a recovery runs (tmux + MSP),
- the lock is HELD while monitoring runs,
- phase 2 re-checks state (tmux) and the #804 bar (MSP) before acting,
- recovery events print after ALL monitoring events,
- a monitoring-phase exception for one job does not cancel another job's
  queued recovery.
"""
import argparse
import fcntl
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


@pytest.fixture()
def cli(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_watch41", CLI_PATH)


def _make_job(cli, slug, **fields):
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    os.makedirs(cli.METADATA_DIR, exist_ok=True)
    job = {"slug": slug, "state": "active", "started_at": time.time()}
    job.update(fields)
    with open(cli.job_json_path(slug), "w") as f:
        json.dump(job, f)
    return jd


def _watch_events(cli, capsys):
    rc = cli.cmd_watch(argparse.Namespace())
    assert rc == 0
    return [json.loads(l) for l in capsys.readouterr().out.splitlines()
            if l.strip()]


def _lock_is_free(cli, slug):
    """Non-blocking flock probe: True iff no one holds the job lock."""
    p = os.path.join(cli.JOBS_DIR, f".{slug}.lock")
    fd = os.open(p, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def test_tmux_recovery_runs_without_the_lock(cli, monkeypatch, capsys):
    slug = "dead-tmux"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "job_status", lambda job, s: {"tmux_alive": False})
    monkeypatch.setattr(cli, "_phase_concurrency_bars_resume",
                        lambda s: False)
    probe = {}

    def fake_resume(args, _from_watch=False):
        probe["free"] = _lock_is_free(cli, slug)
        return 0

    monkeypatch.setattr(cli, "cmd_resume", fake_resume)
    events = _watch_events(cli, capsys)
    assert probe == {"free": True}
    assert [e["signal"] for e in events] == ["recovered"]
    assert events[0]["detail"] == "tmux was dead; resumed session"


def test_monitoring_runs_with_the_lock(cli, monkeypatch, capsys):
    slug = "probe-monitor"
    _make_job(cli, slug)
    probe = {}

    def fake_status(job, s):
        probe["free"] = _lock_is_free(cli, slug)
        return {"tmux_alive": False}

    monkeypatch.setattr(cli, "job_status", fake_status)
    # Barred in phase 1: no recovery is queued, the pass emits deferred.
    monkeypatch.setattr(cli, "_phase_concurrency_bars_resume",
                        lambda s: True)
    events = _watch_events(cli, capsys)
    assert probe == {"free": False}
    assert [e["signal"] for e in events] == ["deferred"]


def test_phase2_state_recheck_refuses_killed_job(cli, monkeypatch):
    slug = "killed-between"
    _make_job(cli, slug, state="killed")
    called = []
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda args, _from_watch=False: called.append(True))
    events = []
    cli._run_watch_recovery("tmux-resume", slug, events)
    assert called == []
    assert len(events) == 1
    assert events[0]["signal"] == "needs-attention"
    assert "left the monitored states" in events[0]["detail"]


def test_phase2_unknown_kind_pages(cli):
    slug = "weird-kind"
    _make_job(cli, slug)
    events = []
    cli._run_watch_recovery("no-such-kind", slug, events)
    assert len(events) == 1
    assert events[0]["signal"] == "needs-attention"
    assert "unknown watch recovery kind" in events[0]["detail"]


def test_tmux_phase2_deferred_maps_cmd_resume_recheck(cli, monkeypatch, capsys):
    slug = "deferred-phase2"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "job_status", lambda job, s: {"tmux_alive": False})
    monkeypatch.setattr(cli, "_phase_concurrency_bars_resume",
                        lambda s: False)

    def fake_resume(args, _from_watch=False):
        raise cli._PhaseConcurrencyDeferred("sibling went live")

    monkeypatch.setattr(cli, "cmd_resume", fake_resume)
    events = _watch_events(cli, capsys)
    assert [e["signal"] for e in events] == ["deferred"]
    assert "re-check inside cmd_resume fired" in events[0]["detail"]


def test_tmux_phase2_bar_recheck_defers(cli, monkeypatch, capsys):
    # Same-pass serialization: phase 1 queues while no sibling is live;
    # a sibling goes live during the monitoring phase, so phase 2 must
    # defer instead of over-admitting -- without waiting for cmd_resume's
    # inner #1131 re-check.
    slug = "tmux-barred-late"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "job_status", lambda job, s: {"tmux_alive": False})
    answers = iter([False, True])
    monkeypatch.setattr(cli, "_phase_concurrency_bars_resume",
                        lambda s: next(answers))
    called = []
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda args, _from_watch=False: called.append(True))
    events = _watch_events(cli, capsys)
    assert called == []
    assert [e["signal"] for e in events] == ["deferred"]
    assert "phase-2 bar re-check fired" in events[0]["detail"]


def test_recovery_events_print_after_monitoring_events(cli, monkeypatch, capsys):
    # aaa is barred in phase 1 (monitoring event); bbb queues a recovery
    # that runs in phase 2. The deferred event must precede the recovered
    # event even though bbb sorts after aaa.
    _make_job(cli, "aaa-monitor")
    _make_job(cli, "bbb-recover")
    monkeypatch.setattr(cli, "job_status", lambda job, s: {"tmux_alive": False})
    monkeypatch.setattr(cli, "_phase_concurrency_bars_resume",
                        lambda s: s == "aaa-monitor")
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda args, _from_watch=False: 0)
    events = _watch_events(cli, capsys)
    assert [(e["job"], e["signal"]) for e in events] == [
        ("aaa-monitor", "deferred"),
        ("bbb-recover", "recovered"),
    ]


def test_phase1_exception_does_not_cancel_queued_recovery(cli, monkeypatch,
                                                           capsys):
    _make_job(cli, "aaa-explodes")
    _make_job(cli, "bbb-recover")

    def fake_status(job, s):
        if job["slug"] == "aaa-explodes":
            raise RuntimeError("probe blew up")
        return {"tmux_alive": False}

    monkeypatch.setattr(cli, "job_status", fake_status)
    monkeypatch.setattr(cli, "_phase_concurrency_bars_resume",
                        lambda s: False)
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda args, _from_watch=False: 0)
    events = _watch_events(cli, capsys)
    assert [(e["job"], e["signal"]) for e in events] == [
        ("bbb-recover", "recovered"),
    ]


class _FakeRecovery:
    ACTION_NONE = "none"
    ACTION_CONTINUED = "continued"
    ACTION_RESUMED = "resumed"

    def __init__(self, probe=None):
        self.calls = []
        self.probe = probe

    def recover_dead_turn(self, host, session_id, job_dir):
        self.calls.append((host, session_id, job_dir))
        if self.probe is not None:
            self.probe()
        return types.SimpleNamespace(action=self.ACTION_CONTINUED,
                                     detail="re-anchored", attempts=[])


def _fake_msp_view(state):
    return types.SimpleNamespace(state=state, last_terminal=None,
                                 pending_summary="", active_turn_id="turn-1")


def _msp_stalled_setup(cli, monkeypatch, slug, recovery):
    _make_job(cli, slug, transport="msp", session_uuid="sid-" + slug)
    monkeypatch.setattr(cli, "_MSP_IMPORTS",
                        (None, None, None, None, recovery))
    monkeypatch.setattr(cli, "_msp_call",
                        lambda s, job, fn, pre_resume=True: fn(None))
    monkeypatch.setattr(cli, "_msp_poll",
                        lambda host, s, job: _fake_msp_view("stalled"))


def test_msp_ladder_runs_without_the_lock(cli, monkeypatch, capsys):
    slug = "msp-dead"
    probe = {}

    def check_lock():
        probe["free"] = _lock_is_free(cli, slug)

    recovery = _FakeRecovery(probe=check_lock)
    _msp_stalled_setup(cli, monkeypatch, slug, recovery)
    monkeypatch.setattr(cli, "_phase_concurrency_bars_resume",
                        lambda s: False)
    events = _watch_events(cli, capsys)
    assert probe == {"free": True}
    assert len(recovery.calls) == 1
    assert [(e["job"], e["signal"]) for e in events] == [(slug, "recovered")]
    assert "continued" in events[0]["detail"]


def test_msp_phase2_bar_recheck_defers(cli, monkeypatch, capsys):
    slug = "msp-barred-late"
    recovery = _FakeRecovery()
    _msp_stalled_setup(cli, monkeypatch, slug, recovery)
    # Free in phase 1 (recovery queues), barred in phase 2 (sibling went
    # live during the monitoring phase): the ladder must not run.
    answers = iter([False, True])
    monkeypatch.setattr(cli, "_phase_concurrency_bars_resume",
                        lambda s: next(answers))
    events = _watch_events(cli, capsys)
    assert recovery.calls == []
    assert [(e["job"], e["signal"]) for e in events] == [(slug, "deferred")]
    assert "msp stalled-turn recovery" in events[0]["detail"]
