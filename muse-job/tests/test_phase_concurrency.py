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


def test_watch_killed_midpass_reports_needs_attention(cli, monkeypatch, capsys):
    # The #5 state gate runs BEFORE the #804 bar: a job the operator kills
    # mid-pass reports needs-attention, never deferred -- even with a live
    # phase sibling that would otherwise bar recovery.
    slug = "phase-dead"
    _make_job(cli, slug)
    _bare_dir(cli, "phase-live")
    _dead_tmux_watch(cli, monkeypatch, live_slugs=("phase-live",))
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume", lambda a, **k: resumed.append(a) or 0)
    real_load_job = cli.load_job
    calls = []
    def load_job_twice(s):
        calls.append(s)
        job = real_load_job(s)
        if len(calls) > 1:
            job = dict(job, state="killed")  # operator kill lands mid-pass
        return job
    monkeypatch.setattr(cli, "load_job", load_job_twice)
    events = _watch_events(cli, capsys)
    by_job = {e["job"]: e for e in events}
    assert by_job[slug]["signal"] == "needs-attention"
    assert "killed or closed" in by_job[slug]["detail"]
    assert resumed == []


def test_watch_two_dead_phase_jobs_serialize(cli, monkeypatch, capsys):
    # No live sibling at pass start: the first dead phase job (sorted
    # order) recovers, and its fresh session bars the second -- the bar
    # serializes same-pass recovery instead of stampeding.
    _make_job(cli, "phase-a")
    _make_job(cli, "phase-b")
    monkeypatch.setattr(cli, "job_status", lambda job, slug: {"tmux_alive": False})
    live = set()
    monkeypatch.setattr(cli, "tmux_alive", lambda s: s in live)
    resumed = []
    def fake_resume(a, **k):
        resumed.append(a.slug)
        live.add(a.slug)  # resume brings the tmux session up synchronously
        return 0
    monkeypatch.setattr(cli, "cmd_resume", fake_resume)
    events = _watch_events(cli, capsys)
    by_job = {e["job"]: e for e in events}
    assert by_job["phase-a"]["signal"] == "recovered"
    assert by_job["phase-b"]["signal"] == "deferred"
    assert resumed == ["phase-a"]


# --- issue #1131: re-check inside cmd_resume ---------------------------------

def _resume_fakes(cli, monkeypatch, live_slugs):
    # Drive cmd_resume's tmux path to the re-check without touching tmux.
    monkeypatch.setattr(cli, "tmux_alive", lambda s: s in live_slugs)
    monkeypatch.setattr(cli, "trusted_job_paths",
                        lambda s, j: ("/tmp/w", "/repos/x", "job/s"))
    monkeypatch.setattr(cli, "session_bound_to_workdir", lambda u, w: True)
    ran = []
    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: ran.append(a) or
                        __import__("types").SimpleNamespace(stdout=b"pane"))
    return ran


def test_cmd_resume_rechecks_bar_on_watch_path(cli, monkeypatch):
    # Issue #1131: the watch's bar check passed, then a sibling phase-*
    # job went live before cmd_resume ran. The re-check defers instead of
    # over-admitting, and no tmux session is created.
    _make_job(cli, "phase-dead", session_uuid="uuid-1")
    _bare_dir(cli, "phase-live")
    ran = _resume_fakes(cli, monkeypatch, live_slugs=("phase-live",))
    with pytest.raises(cli._PhaseConcurrencyDeferred):
        cli.cmd_resume(argparse.Namespace(slug="phase-dead"), _from_watch=True)
    assert ran == []


def test_cmd_resume_manual_bypass_unaffected(cli, monkeypatch, capsys):
    # The manual escape hatch is by design: _from_watch=False never hits
    # the re-check, even with a live sibling.
    _make_job(cli, "phase-dead", session_uuid="uuid-1")
    _bare_dir(cli, "phase-live")
    ran = _resume_fakes(cli, monkeypatch, live_slugs=("phase-live",))
    monkeypatch.setattr(cli, "_answer_trust_prompt", lambda s: None)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    rc = cli.cmd_resume(argparse.Namespace(slug="phase-dead"), _from_watch=False)
    assert rc == 0
    assert ran and ran[0][:2] == ("tmux", "new-session")
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["resumed"] == "uuid-1"


def test_cmd_resume_watch_path_recovers_when_unbarred(cli, monkeypatch, capsys):
    # No live sibling at re-check time: the resume proceeds normally.
    _make_job(cli, "phase-dead", session_uuid="uuid-1")
    ran = _resume_fakes(cli, monkeypatch, live_slugs=())
    monkeypatch.setattr(cli, "_answer_trust_prompt", lambda s: None)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    rc = cli.cmd_resume(argparse.Namespace(slug="phase-dead"), _from_watch=True)
    assert rc == 0
    assert ran and ran[0][:2] == ("tmux", "new-session")


def test_watch_maps_recheck_deferral_to_deferred_signal(cli, monkeypatch, capsys):
    # The watch's pre-check passed; cmd_resume's re-check fired. The watch
    # emits `deferred` (retry on a later pass), not `needs-attention`.
    _make_job(cli, "phase-dead")
    _dead_tmux_watch(cli, monkeypatch, live_slugs=())

    def boom(a, **k):
        raise cli._PhaseConcurrencyDeferred("race fired")

    monkeypatch.setattr(cli, "cmd_resume", boom)
    events = _watch_events(cli, capsys)
    by_job = {e["job"]: e for e in events}
    assert by_job["phase-dead"]["signal"] == "deferred"
    assert "race fired" in by_job["phase-dead"]["detail"]
