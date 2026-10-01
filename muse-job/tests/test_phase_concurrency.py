"""Regression tests for issue #804 (watch auto-resume vs the one-phase-job rule).

On 2026-10-01 `muse-job watch` resurrected three operator-killed phase-*
jobs -- the "one recovery attempt" resumed every dead active job
unconditionally -- landing four concurrent ultra-reasoning Muse sessions on
the user's pay-as-you-go bill. The operator hot-patched the deployed copy
(`_phase_concurrency_bars_resume` + a guard in cmd_watch emitting
`deferred`); this file pins the repo version of that policy.

The repo fix matches the hot-patch semantics verbatim: phase-* slugs only,
barred while any *other* phase-* job has a live tmux session, OSError on
the job-dir scan fails open (pre-hot-patch behavior), and the deferred
signal keeps the hot-patch's exact detail string (watchers grep for it).
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import sys
import time

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
    return load_script("muse_job_cli_phase804", CLI_PATH)


def _make_job(cli, slug, **fields):
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    job = {"slug": slug, "state": "active", "started_at": time.time()}
    job.update(fields)
    with open(cli.job_json_path(slug), "w") as f:
        json.dump(job, f)
    return jd


def _bare_dir(cli, slug):
    # A JOBS_DIR entry with no job.json: watch_one skips it, but the
    # concurrency helper still sees the sibling name (as on a real box).
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    return jd


def _watch_events(cli, capsys):
    rc = cli.cmd_watch(argparse.Namespace())
    assert rc == 0
    return [json.loads(l) for l in capsys.readouterr().out.splitlines()
            if l.strip()]


# --- _phase_concurrency_bars_resume ------------------------------------------

def test_non_phase_slug_never_barred(cli, monkeypatch):
    _bare_dir(cli, "phase-live")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: True)
    assert cli._phase_concurrency_bars_resume("worker-1") is False


def test_phase_slug_without_live_sibling_not_barred(cli, monkeypatch):
    _make_job(cli, "phase-dead")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    assert cli._phase_concurrency_bars_resume("phase-dead") is False


def test_phase_slug_with_live_sibling_barred(cli, monkeypatch):
    _make_job(cli, "phase-dead")
    _bare_dir(cli, "phase-live")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: s == "phase-live")
    assert cli._phase_concurrency_bars_resume("phase-dead") is True


def test_self_not_counted_as_sibling(cli, monkeypatch):
    # Only this job is a live phase-* job: its own session must not bar it.
    _make_job(cli, "phase-only")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: s == "phase-only")
    assert cli._phase_concurrency_bars_resume("phase-only") is False


def test_dotfiles_not_counted_as_siblings(cli, monkeypatch):
    _make_job(cli, "phase-dead")
    _bare_dir(cli, ".phase-hidden")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: True)
    assert cli._phase_concurrency_bars_resume("phase-dead") is False


def test_listdir_oserror_fails_open(cli, monkeypatch, tmp_path):
    # An unreadable JOBS_DIR must not newly block recovery: fail open to
    # the pre-hot-patch behavior (resume attempt proceeds). Pointing
    # JOBS_DIR at a regular file makes os.listdir raise OSError.
    not_a_dir = tmp_path / "notadir"
    not_a_dir.write_text("x")
    monkeypatch.setattr(cli, "JOBS_DIR", str(not_a_dir))
    monkeypatch.setattr(cli, "tmux_alive", lambda s: True)
    assert cli._phase_concurrency_bars_resume("phase-dead") is False


# --- cmd_watch guard ----------------------------------------------------------

DEFERRED_DETAIL = ("tmux dead; auto-resume deferred — another phase-* job "
                   "is live (one-at-a-time rule)")


def _dead_tmux_watch(cli, monkeypatch, live_slugs=()):
    # job_status reports tmux down for every job; the module-level
    # tmux_alive (used by the concurrency helper) is live exactly for
    # live_slugs.
    monkeypatch.setattr(cli, "job_status", lambda job, slug: {"tmux_alive": False})
    monkeypatch.setattr(cli, "tmux_alive", lambda s: s in live_slugs)


def test_watch_defers_barred_phase_job(cli, monkeypatch, capsys):
    _make_job(cli, "phase-dead")
    _bare_dir(cli, "phase-live")
    _dead_tmux_watch(cli, monkeypatch, live_slugs=("phase-live",))
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume", lambda a, **k: resumed.append(a) or 0)
    events = _watch_events(cli, capsys)
    by_job = {e["job"]: e for e in events}
    assert by_job["phase-dead"]["signal"] == "deferred"
    assert by_job["phase-dead"]["detail"] == DEFERRED_DETAIL
    assert resumed == []  # no resurrection attempt


def test_watch_recovers_unbarred_phase_job(cli, monkeypatch, capsys):
    _make_job(cli, "phase-dead")
    _dead_tmux_watch(cli, monkeypatch, live_slugs=())
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume", lambda a, **k: resumed.append(a) or 0)
    events = _watch_events(cli, capsys)
    by_job = {e["job"]: e for e in events}
    assert by_job["phase-dead"]["signal"] == "recovered"
    assert len(resumed) == 1


def test_watch_still_recovers_non_phase_job(cli, monkeypatch, capsys):
    # The policy is phase-only: other jobs recover even while a phase-*
    # job is live.
    _make_job(cli, "worker-1")
    _bare_dir(cli, "phase-live")
    _dead_tmux_watch(cli, monkeypatch, live_slugs=("phase-live",))
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume", lambda a, **k: resumed.append(a) or 0)
    events = _watch_events(cli, capsys)
    by_job = {e["job"]: e for e in events}
    assert by_job["worker-1"]["signal"] == "recovered"
    assert len(resumed) == 1
