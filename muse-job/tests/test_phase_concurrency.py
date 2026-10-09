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
    return load_script("muse_job_cli_phase804", CLI_PATH)


@pytest.fixture(autouse=True)
def _preserve_no_auto_update():
    # _msp_host_for sets MUSE_NO_AUTO_UPDATE=1 process-wide (issue #212
    # policy); the close-on-missing-dir tests exercise the real
    # _msp_close_runtime path, so keep it from leaking into sibling test
    # modules -- test_tui_update_policy asserts the variable's absence
    # (issue #1153 review).
    had = os.environ.get("MUSE_NO_AUTO_UPDATE")
    yield
    if had is None:
        os.environ.pop("MUSE_NO_AUTO_UPDATE", None)
    else:
        os.environ["MUSE_NO_AUTO_UPDATE"] = had


def _make_job(cli, slug, **fields):
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    os.makedirs(cli.METADATA_DIR, exist_ok=True)
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

# The deferred detail string is pinned in the module (watchers grep for it,
# issue #804 hot-patch contract); the tests below assert against
# cli._PHASE_DEFERRED_DETAIL so code and contract cannot drift apart.


def test_deferred_detail_string_pinned(cli):
    # The exact hot-patch wording watchers grep for.
    assert cli._PHASE_DEFERRED_DETAIL == (
        "tmux dead; auto-resume deferred — another phase-* job is live "
        "(one-at-a-time rule)")


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
    assert by_job["phase-dead"]["detail"] == cli._PHASE_DEFERRED_DETAIL
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
    # The pinned detail string is reused verbatim (watchers grep for it),
    # with a suffix naming the re-check.
    assert by_job["phase-dead"]["detail"] == (
        cli._PHASE_DEFERRED_DETAIL +
        " (re-check inside cmd_resume fired; next pass retries)")


def test_watch_recheck_fires_on_midpass_sibling_start(cli, monkeypatch, capsys):
    # Issue #1131, the actual race, end to end through the REAL cmd_watch
    # + REAL cmd_resume (faking only tmux_alive as a flip-flop, plus run,
    # trust-prompt, sleep, and the path/uuid helpers): the watch pre-check
    # sees no live sibling, the sibling goes live in the check-then-act
    # window, and the re-check defers instead of over-admitting -- no tmux
    # session is created.
    _make_job(cli, "phase-dead", session_uuid="uuid-1")
    _bare_dir(cli, "phase-live")
    calls = {"n": 0}

    def flip_flop(slug):
        # First scan (the watch pre-check): nobody live. Every scan after:
        # the sibling went live in the window.
        calls["n"] += 1
        return slug == "phase-live" and calls["n"] > 1

    monkeypatch.setattr(cli, "tmux_alive", flip_flop)
    monkeypatch.setattr(cli, "job_status",
                        lambda job, slug: {"tmux_alive": False})
    ran = []
    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: ran.append(a) or
                        types.SimpleNamespace(stdout=b"pane"))
    monkeypatch.setattr(cli, "_answer_trust_prompt", lambda s: None)
    monkeypatch.setattr(cli, "trusted_job_paths",
                        lambda s, j: ("/tmp/w", "/repos/x", "job/s"))
    monkeypatch.setattr(cli, "session_bound_to_workdir", lambda u, w: True)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    events = _watch_events(cli, capsys)
    by_job = {e["job"]: e for e in events}
    assert by_job["phase-dead"]["signal"] == "deferred"
    assert by_job["phase-dead"]["detail"].startswith(cli._PHASE_DEFERRED_DETAIL)
    assert ran == []  # the re-check fired before any tmux session existed


# --- issue #1132: MSP-side phase occupancy ------------------------------------
# The #804 bar only probed tmux sessions, so a phase-* job live on the MSP
# transport (the default since #979) was invisible in both directions. The
# watch pass now stamps a manager-side occupancy record whenever it polls a
# live phase-* MSP session; the bar bars on fresh stamps. TTL is 3x the
# 15-minute watch cadence; stale/missing/malformed records fail open.


def test_msp_occupancy_bars_sibling(cli, monkeypatch):
    _make_job(cli, "phase-dead")
    cli._phase_msp_occupancy_note("phase-live", True)
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    assert cli._phase_concurrency_bars_resume("phase-dead") is True


def test_msp_occupancy_stale_fails_open(cli, monkeypatch, tmp_path):
    _make_job(cli, "phase-dead")
    path = cli._PHASE_MSP_OCCUPANCY_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"phase-live": time.time() - cli._PHASE_MSP_OCCUPANCY_TTL_S - 1}, f)
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    assert cli._phase_concurrency_bars_resume("phase-dead") is False


def _write_occupancy_raw(cli, mapping):
    path = cli._PHASE_MSP_OCCUPANCY_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(mapping, f)


def test_msp_occupancy_ttl_boundary_is_inclusive(cli, monkeypatch):
    # The `<=` edge: a stamp exactly TTL old still bars. Freeze the
    # module's clock so the write/read gap cannot push it over the edge.
    _make_job(cli, "phase-dead")
    now = time.time()
    _write_occupancy_raw(cli, {"phase-live": now - cli._PHASE_MSP_OCCUPANCY_TTL_S})

    class _FrozenTime:
        def time(self):
            return now

    monkeypatch.setattr(cli, "time", _FrozenTime())
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    assert cli._phase_concurrency_bars_resume("phase-dead") is True


def test_msp_occupancy_future_stamp_fails_open(cli, monkeypatch):
    # Clock-skew guard: a future timestamp is rejected, not trusted.
    _make_job(cli, "phase-dead")
    _write_occupancy_raw(cli, {"phase-live": time.time() + 60})
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    assert cli._phase_concurrency_bars_resume("phase-dead") is False


@pytest.mark.parametrize("bad_ts", [True, False, "12345", None, [1]])
def test_msp_occupancy_bad_timestamp_shape_fails_open(cli, monkeypatch, bad_ts):
    _make_job(cli, "phase-dead")
    _write_occupancy_raw(cli, {"phase-live": bad_ts})
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    assert cli._phase_concurrency_bars_resume("phase-dead") is False


def test_msp_occupancy_self_not_counted(cli, monkeypatch):
    _make_job(cli, "phase-only")
    cli._phase_msp_occupancy_note("phase-only", True)
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    assert cli._phase_concurrency_bars_resume("phase-only") is False


def test_msp_occupancy_malformed_fails_open(cli, monkeypatch):
    _make_job(cli, "phase-dead")
    path = cli._PHASE_MSP_OCCUPANCY_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("not json{{{")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    # No raise, no bar: a record the bar cannot trust must not block recovery.
    assert cli._phase_concurrency_bars_resume("phase-dead") is False


def test_msp_occupancy_note_non_phase_noop(cli):
    cli._phase_msp_occupancy_note("worker-1", True)
    assert not os.path.exists(cli._PHASE_MSP_OCCUPANCY_PATH)
    assert cli._phase_msp_occupancy_live() == {}


def test_msp_occupancy_note_and_clear(cli):
    cli._phase_msp_occupancy_note("phase-a", True)
    assert "phase-a" in cli._phase_msp_occupancy_live()
    cli._phase_msp_occupancy_note("phase-a", False)
    assert cli._phase_msp_occupancy_live() == {}


def test_msp_occupancy_note_oserror_is_best_effort(cli, tmp_path):
    # If the manager-side dir cannot be created (here: a regular file
    # squats at ~/.local/share/muse-job), the stamp fails silently and
    # the reader fails open -- the watch pass never breaks on this.
    squat = tmp_path / ".local" / "share" / "muse-job"
    squat.parent.mkdir(parents=True, exist_ok=True)
    squat.write_text("squat")
    cli._phase_msp_occupancy_note("phase-live", True)  # must not raise
    assert cli._phase_msp_occupancy_live() == {}


def _fake_msp_view(state):
    return types.SimpleNamespace(
        state=state, active_turn_id="turn-1" if state == "working" else None,
        pending_summary="", last_event_at=time.time(), last_terminal=None)


class _FakeRecovery:
    ACTION_NONE = "none"
    ACTION_CONTINUED = "continued"
    ACTION_RESUMED = "resumed"

    def __init__(self):
        self.calls = []

    def recover_dead_turn(self, host, session_id, job_dir):
        self.calls.append((host, session_id, job_dir))
        return types.SimpleNamespace(
            action=self.ACTION_CONTINUED, detail="re-anchored", attempts=[])


def _msp_watch_fakes(cli, monkeypatch, view_state):
    """Drive _watch_msp_job hermetically: fake the serve call + poll, and
    the recovery module behind the _MSP_IMPORTS cache."""
    recovery = _FakeRecovery()
    monkeypatch.setattr(cli, "_MSP_IMPORTS",
                        (None, None, None, None, recovery))
    monkeypatch.setattr(cli, "_msp_call",
                        lambda slug, job, fn, pre_resume=True: fn(None))
    monkeypatch.setattr(cli, "_msp_poll",
                        lambda host, slug, job: _fake_msp_view(view_state))
    return recovery


def _make_msp_job(cli, slug):
    return _make_job(cli, slug, transport="msp", session_uuid="sid-" + slug)


def test_watch_msp_stalled_defers_on_live_sibling(cli, monkeypatch, capsys):
    # Direction 2 of #1132: an MSP phase job's recovery ladder is the MSP
    # analog of the tmux "one recovery attempt" -- it must emit the same
    # deferred signal while another phase-* job is live on MSP.
    _make_msp_job(cli, "phase-dead")
    cli._phase_msp_occupancy_note("phase-live", True)
    recovery = _msp_watch_fakes(cli, monkeypatch, "stalled")
    events = _watch_events(cli, capsys)
    by_job = {e["job"]: e for e in events}
    assert by_job["phase-dead"]["signal"] == "deferred"
    assert by_job["phase-dead"]["detail"] == (
        cli._PHASE_DEFERRED_DETAIL +
        " (msp stalled-turn recovery; next pass retries)")
    assert recovery.calls == []  # no resurrection attempt


def test_watch_msp_stalled_recovers_when_unbarred(cli, monkeypatch, capsys):
    _make_msp_job(cli, "phase-dead")
    recovery = _msp_watch_fakes(cli, monkeypatch, "stalled")
    events = _watch_events(cli, capsys)
    by_job = {e["job"]: e for e in events}
    assert by_job["phase-dead"]["signal"] == "recovered"
    assert len(recovery.calls) == 1


@pytest.mark.parametrize("state", ["working", "idle", "stalled",
                                   "turn_cancelled", "blocked_approval",
                                   "blocked_input"])
def test_watch_msp_stamps_occupancy_on_live_poll(cli, monkeypatch, capsys,
                                                 state):
    # Direction 1 of #1132: the tmux-side bar consults these stamps, so a
    # tmux phase job cannot auto-resume next to a live MSP phase job.
    # Every live state in _MSP_PHASE_LIVE_STATES must stamp.
    _make_msp_job(cli, "phase-live")
    _msp_watch_fakes(cli, monkeypatch, state)
    _watch_events(cli, capsys)
    assert "phase-live" in cli._phase_msp_occupancy_live()


@pytest.mark.parametrize("state", ["turn_failed", "session_closed"])
def test_watch_msp_clears_occupancy_on_dead_poll(cli, monkeypatch, capsys,
                                                 state):
    # Both _MSP_PHASE_DEAD_STATES clear the stamp: the session is gone.
    _make_msp_job(cli, "phase-gone")
    cli._phase_msp_occupancy_note("phase-gone", True)
    _msp_watch_fakes(cli, monkeypatch, state)
    events = _watch_events(cli, capsys)
    assert "phase-gone" not in cli._phase_msp_occupancy_live()
    by_job = {e["job"]: e for e in events}
    assert by_job["phase-gone"]["signal"] == "needs-attention"


def test_msp_kill_clears_occupancy(cli, monkeypatch):
    # A deliberate kill must not defer a sibling's auto-recovery for a TTL.
    _make_msp_job(cli, "phase-killed")
    cli._phase_msp_occupancy_note("phase-killed", True)
    monkeypatch.setattr(cli, "_msp_call",
                        lambda slug, job, fn, pre_resume=True: None)
    rc = cli._msp_kill(argparse.Namespace(slug="phase-killed"))
    assert rc == 0
    assert "phase-killed" not in cli._phase_msp_occupancy_live()


def test_close_clears_occupancy(cli, tmp_path):
    _make_closable_job(cli, "phase-done", tmp_path)
    cli._phase_msp_occupancy_note("phase-done", True)
    rc = cli.cmd_close(argparse.Namespace(slug="phase-done"))
    assert rc == 0
    assert "phase-done" not in cli._phase_msp_occupancy_live()


# --- issue #1153: close must not crash on a manually-removed job dir --------

def _make_closable_job(cli, slug, tmp_path, **fields):
    # close's trusted_job_paths demands a pristine repo under ~/repos with
    # the derived worktree registered (defense in depth, issue #11).
    import subprocess
    jd = _make_job(cli, slug, **fields)
    repo = os.path.join(str(tmp_path), "repos", "r")
    os.makedirs(repo, exist_ok=True)
    subprocess.run(["git", "init", "-q", repo], check=True)
    subprocess.run(["git", "-C", repo, "-c", "user.email=t@t", "-c",
                    "user.name=t", "commit", "-q", "--allow-empty",
                    "-m", "init"], check=True)
    work = os.path.join(jd, "work")
    subprocess.run(["git", "-C", repo, "worktree", "add", "-q",
                    "-b", "job/" + slug, work], check=True)
    job = cli.load_job(slug)
    job["pristine"] = repo
    cli.save_job(job, slug)
    return jd


def test_close_missing_job_dir_closes_record(cli, tmp_path):
    import shutil
    _make_closable_job(cli, "gone-job", tmp_path)
    shutil.rmtree(cli.job_dir("gone-job"))
    rc = cli.cmd_close(argparse.Namespace(slug="gone-job"))
    assert rc == 0
    assert cli.load_job("gone-job")["state"] == "closed"


def test_close_missing_job_dir_msp_closes_record(cli, tmp_path, capsys):
    # The MSP close path runs _msp_close_runtime first; with the job dir
    # gone the serve-log open fails closed (warning, no spawn) and the
    # record still closes.
    import shutil
    _make_closable_job(cli, "gone-msp", tmp_path,
                       transport="msp", session_uuid="sid-gone-msp")
    shutil.rmtree(cli.job_dir("gone-msp"))
    rc = cli.cmd_close(argparse.Namespace(slug="gone-msp"))
    assert rc == 0
    assert cli.load_job("gone-msp")["state"] == "closed"


# --- issue #1172: close must not crash on an unreadable job dir --------------

def _fail_listdir_on(cli, monkeypatch, path):
    # listdir raises PermissionError while isdir succeeds (stat needs no
    # read permission). chmod 0 would be the real trigger, but the suite
    # can run as root (permission checks bypassed), so force the failure
    # path deterministically instead.
    real_listdir = os.listdir
    target = os.path.abspath(path)

    def _boom(p):
        if os.path.abspath(p) == target:
            raise PermissionError(13, "Permission denied", p)
        return real_listdir(p)

    monkeypatch.setattr(os, "listdir", _boom)


def test_close_unreadable_job_dir_closes_record(cli, tmp_path, monkeypatch):
    jd = _make_closable_job(cli, "noread-job", tmp_path)
    _fail_listdir_on(cli, monkeypatch, jd)
    rc = cli.cmd_close(argparse.Namespace(slug="noread-job"))
    assert rc == 0
    assert cli.load_job("noread-job")["state"] == "closed"


def test_close_unreadable_job_dir_msp_closes_record(cli, tmp_path, monkeypatch):
    jd = _make_closable_job(cli, "noread-msp", tmp_path,
                            transport="msp", session_uuid="sid-noread-msp")
    _fail_listdir_on(cli, monkeypatch, jd)
    rc = cli.cmd_close(argparse.Namespace(slug="noread-msp"))
    assert rc == 0
    assert cli.load_job("noread-msp")["state"] == "closed"
