"""Decoupled watch recovery: the `muse-job recover` worker (issue #41).

Before this change, `watch_one` called `cmd_resume` inline inside the
per-job lock: the 15s sleep plus the up-to-~2min fallback (probe sleeps,
90s session re-discovery, steer) stretched the serial watchdog pass by
minutes per dead job and blocked steer/status for that job.

Now the watch pass only runs the fast gates (the #5 state re-check, the
#804 one-phase-job bar) and dispatches a detached `muse-job recover
<slug>` worker, which performs the exact old inline body under a global
recovery lock (taken before the per-job lock). The global lock is what
keeps the #804 anti-stampede property the old serial pass provided for
free: without it, two workers from the same pass could both clear the
bar before either session goes live and resurrect two phase-* jobs
concurrently.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import queue
import sys
import threading
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
    return load_script("muse_job_cli_recover41", CLI_PATH)


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
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    return jd


def _dead_tmux(cli, monkeypatch, live_slugs=()):
    monkeypatch.setattr(cli, "job_status",
                        lambda job, slug: {"tmux_alive": False})
    monkeypatch.setattr(cli, "tmux_alive", lambda s: s in live_slugs)


def _events(capsys):
    return [json.loads(l) for l in capsys.readouterr().out.splitlines()
            if l.strip()]


# --- watch side: dispatch, never inline recovery ------------------------------


def test_watch_emits_needs_recovery_and_dispatches(cli, monkeypatch, capsys):
    _make_job(cli, "dead-1")
    _dead_tmux(cli, monkeypatch)
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda a, **k: resumed.append(a) or 0)
    dispatched = []
    monkeypatch.setattr(cli, "_dispatch_recover_worker",
                        lambda s: dispatched.append(s) or True)
    rc = cli.cmd_watch(argparse.Namespace())
    assert rc == 0
    by_job = {e["job"]: e for e in _events(capsys)}
    assert by_job["dead-1"]["signal"] == "needs-recovery"
    assert dispatched == ["dead-1"]
    assert resumed == []  # the #41 fix: no inline resume inside the pass


def test_watch_dispatch_failure_is_loud(cli, monkeypatch, capsys):
    _make_job(cli, "dead-1")
    _dead_tmux(cli, monkeypatch)
    monkeypatch.setattr(cli, "_dispatch_recover_worker", lambda s: False)
    rc = cli.cmd_watch(argparse.Namespace())
    assert rc == 0
    by_job = {e["job"]: e for e in _events(capsys)}
    assert by_job["dead-1"]["signal"] == "needs-attention"
    assert "failed to spawn" in by_job["dead-1"]["detail"]


def test_watch_gates_still_run_before_dispatch(cli, monkeypatch, capsys):
    # The #5 state gate and the #804 bar stay in the pass (fast,
    # synchronous). A job killed mid-pass reports needs-attention (never
    # dispatches); a barred phase job reports deferred (never dispatches).
    _make_job(cli, "dead-killed")
    _make_job(cli, "phase-dead")
    _bare_dir(cli, "phase-live")
    _dead_tmux(cli, monkeypatch, live_slugs=("phase-live",))
    real_load_job = cli.load_job
    calls = []

    def load_job_twice(s):
        calls.append(s)
        job = real_load_job(s)
        if s == "dead-killed" and len(calls) > 1:
            job = dict(job, state="killed")  # operator kill lands mid-pass
        return job

    monkeypatch.setattr(cli, "load_job", load_job_twice)
    dispatched = []
    monkeypatch.setattr(cli, "_dispatch_recover_worker",
                        lambda s: dispatched.append(s) or True)
    rc = cli.cmd_watch(argparse.Namespace())
    assert rc == 0
    by_job = {e["job"]: e for e in _events(capsys)}
    assert by_job["dead-killed"]["signal"] == "needs-attention"
    assert by_job["phase-dead"]["signal"] == "deferred"
    assert dispatched == []


# --- recover worker -----------------------------------------------------------


def test_recover_recovers_dead_job(cli, monkeypatch, capsys):
    _make_job(cli, "dead-1")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda a, _from_watch=False:
                        resumed.append((a.slug, _from_watch)) or 0)
    rc = cli.cmd_recover(argparse.Namespace(slug="dead-1"))
    assert rc == 0
    assert resumed == [("dead-1", True)]  # the watch auto-path provenance
    out = _events(capsys)
    assert out == [{"job": "dead-1", "signal": "recovered",
                    "detail": "tmux was dead; resumed session"}]


def test_recover_quiet_when_session_already_alive(cli, monkeypatch, capsys):
    # Dedup: a sibling worker or a manual `muse-job resume` won the race
    # while this worker waited on the locks -- exit quietly, no noise.
    _make_job(cli, "live-1")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: True)
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda a, **k: resumed.append(a) or 0)
    rc = cli.cmd_recover(argparse.Namespace(slug="live-1"))
    assert rc == 0
    assert resumed == []
    assert capsys.readouterr().out == ""


def test_recover_refuses_msp_job(cli, monkeypatch, capsys):
    _make_job(cli, "msp-1", transport="msp")
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda a, **k: resumed.append(a) or 0)
    rc = cli.cmd_recover(argparse.Namespace(slug="msp-1"))
    assert rc == 1
    out = _events(capsys)
    assert out[0]["signal"] == "needs-attention"
    assert "MSP" in out[0]["detail"]
    assert resumed == []


def test_recover_defers_barred_phase_job(cli, monkeypatch, capsys):
    _make_job(cli, "phase-dead")
    _bare_dir(cli, "phase-live")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: s == "phase-live")
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda a, **k: resumed.append(a) or 0)
    rc = cli.cmd_recover(argparse.Namespace(slug="phase-dead"))
    assert rc == 0
    out = _events(capsys)
    assert out[0]["signal"] == "deferred"
    assert out[0]["detail"] == cli._PHASE_DEFERRED_DETAIL
    assert resumed == []


def test_recover_killed_before_lock_not_recovered(cli, monkeypatch, capsys):
    # The #5 gate moved into the worker with the body: a kill landing
    # between the watch's dispatch and the worker's lock acquisition must
    # not revive the job.
    _make_job(cli, "dead-1")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    real_load = cli.load_job

    def killing_load(s):
        return dict(real_load(s), state="killed")

    monkeypatch.setattr(cli, "load_job", killing_load)
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda a, **k: resumed.append(a) or 0)
    rc = cli.cmd_recover(argparse.Namespace(slug="dead-1"))
    assert rc == 0
    out = _events(capsys)
    assert out[0]["signal"] == "needs-attention"
    assert "killed or closed" in out[0]["detail"]
    assert resumed == []


def test_recover_maps_resume_failure_to_needs_attention(cli, monkeypatch,
                                                        capsys):
    _make_job(cli, "dead-1")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)

    def boom(a, **k):
        raise RuntimeError("tmux exploded")

    monkeypatch.setattr(cli, "cmd_resume", boom)
    rc = cli.cmd_recover(argparse.Namespace(slug="dead-1"))
    assert rc == 0
    out = _events(capsys)
    assert out[0]["signal"] == "needs-attention"
    assert "tmux exploded" in out[0]["detail"]


def test_recover_maps_recheck_deferral(cli, monkeypatch, capsys):
    # Issue #1131's re-check moved with the body into the worker: the
    # worker's pre-check passed, cmd_resume's re-check fired.
    _make_job(cli, "phase-dead")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)

    def boom(a, **k):
        raise cli._PhaseConcurrencyDeferred("race fired")

    monkeypatch.setattr(cli, "cmd_resume", boom)
    rc = cli.cmd_recover(argparse.Namespace(slug="phase-dead"))
    assert rc == 0
    out = _events(capsys)
    assert out[0]["signal"] == "deferred"
    assert out[0]["detail"] == (
        cli._PHASE_DEFERRED_DETAIL +
        " (re-check inside cmd_resume fired; next pass retries)")


def test_recover_recheck_fires_on_worker_race(cli, monkeypatch, capsys):
    # Issue #1131 end to end through the REAL cmd_recover + REAL
    # cmd_resume (faking only tmux_alive as a flip-flop, plus run,
    # trust-prompt, sleep, and the path/uuid helpers): the worker's bar
    # pre-check sees no live sibling, the sibling goes live in the
    # check-then-act window, and cmd_resume's re-check defers instead of
    # over-admitting -- no tmux session is created.
    _make_job(cli, "phase-dead", session_uuid="uuid-1")
    _bare_dir(cli, "phase-live")
    calls = {"n": 0}

    def flip_flop(slug):
        # Call order in the worker path: 1 = the worker's liveness
        # re-check (own slug, always dead); 2 = the worker's bar
        # pre-check (sibling not yet live); 3 = cmd_resume's own
        # tmux_alive(slug) (own slug); 4 = cmd_resume's bar re-check
        # (the sibling went live in the window).
        calls["n"] += 1
        return slug == "phase-live" and calls["n"] > 3

    monkeypatch.setattr(cli, "tmux_alive", flip_flop)
    ran = []
    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: ran.append(a) or
                        types.SimpleNamespace(stdout=b"pane"))
    monkeypatch.setattr(cli, "_answer_trust_prompt", lambda s: None)
    monkeypatch.setattr(cli, "trusted_job_paths",
                        lambda s, j: ("/tmp/w", "/repos/x", "job/s"))
    monkeypatch.setattr(cli, "session_bound_to_workdir", lambda u, w: True)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    rc = cli.cmd_recover(argparse.Namespace(slug="phase-dead"))
    assert rc == 0
    out = _events(capsys)
    assert out[0]["signal"] == "deferred"
    assert out[0]["detail"].startswith(cli._PHASE_DEFERRED_DETAIL)
    assert ran == []  # the re-check fired before any tmux session existed


# --- the global recovery lock --------------------------------------------------


def test_concurrent_recover_workers_serialize_phase_bar(cli, monkeypatch):
    # The #804 anti-stampede property across the async boundary: two
    # workers dispatched in the same pass race; the global recovery lock
    # serializes them, so exactly one clears the bar and resumes while
    # the other defers. Either worker may win -- the invariant is "at
    # most one live phase-* job from auto-recovery", not which one.
    _make_job(cli, "phase-a")
    _make_job(cli, "phase-b")
    live = set()
    live_lock = threading.Lock()

    def alive(s):
        with live_lock:
            return s in live

    monkeypatch.setattr(cli, "tmux_alive", alive)
    calls = []

    def fake_resume(a, **k):
        calls.append(a.slug)
        with live_lock:
            live.add(a.slug)  # resume brings the tmux session up
        return 0

    monkeypatch.setattr(cli, "cmd_resume", fake_resume)
    t1 = threading.Thread(target=cli.cmd_recover,
                          args=(argparse.Namespace(slug="phase-a"),))
    t2 = threading.Thread(target=cli.cmd_recover,
                          args=(argparse.Namespace(slug="phase-b"),))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert len(calls) == 1  # exactly one resume; the loser deferred
    assert len(live) == 1


def test_recover_global_lock_is_mutual_exclusion(cli):
    held = []

    def hold():
        with cli._recover_global_lock():
            held.append("in")
            time.sleep(0.2)
            held.append("out")

    t1 = threading.Thread(target=hold)
    t2 = threading.Thread(target=hold)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert held == ["in", "out", "in", "out"]


def test_recover_holds_global_lock_around_body(cli, monkeypatch, capsys):
    # The worker body (bar check + resume) runs inside the global lock:
    # this is the serialization the #804 anti-stampede property rests on.
    _make_job(cli, "dead-1")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    order = []
    real_lock = cli._recover_global_lock

    class SpyLock(real_lock):
        def __enter__(self):
            order.append("global-enter")
            return super().__enter__()

        def __exit__(self, *exc):
            order.append("global-exit")
            return super().__exit__(*exc)

    monkeypatch.setattr(cli, "_recover_global_lock", SpyLock)
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda a, **k: order.append("resume") or 0)
    rc = cli.cmd_recover(argparse.Namespace(slug="dead-1"))
    assert rc == 0
    assert order == ["global-enter", "resume", "global-exit"]
    capsys.readouterr()  # drain


# --- the dispatch --------------------------------------------------------------


def test_dispatch_spawns_detached_worker(cli, monkeypatch):
    spawned = {}

    class FakePopen:
        def __init__(self, argv, **kw):
            spawned["argv"] = argv
            spawned["kw"] = kw

    monkeypatch.setattr(cli.subprocess, "Popen", FakePopen)
    assert cli._dispatch_recover_worker("my-job") is True
    argv, kw = spawned["argv"], spawned["kw"]
    assert argv[:3] == [sys.executable, os.path.abspath(cli.__file__),
                        "recover"]
    assert argv[3] == "my-job"
    assert kw["start_new_session"] is True
    assert kw["stdin"] == cli.subprocess.DEVNULL
    assert kw["stderr"] == cli.subprocess.STDOUT
    assert kw["stdout"].name.endswith(os.path.join("recoveries",
                                                    "my-job.log"))
    kw["stdout"].close()


def test_dispatch_never_raises(cli, monkeypatch):
    def boom(*a, **k):
        raise OSError("nope")

    monkeypatch.setattr(cli.subprocess, "Popen", boom)
    assert cli._dispatch_recover_worker("my-job") is False


# --- O_NOFOLLOW hardening (Security review carry-over, #1801) ------------------


def test_recover_global_lock_refuses_symlink(cli, monkeypatch, capsys):
    # A symlinked lock path must fail the open (ELOOP) instead of
    # serializing on someone else's file: the worker fails closed and
    # loud -- a machine-readable needs-attention, no resume attempted.
    _make_job(cli, "dead-1")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda a, **k: resumed.append(a.slug) or 0)
    os.makedirs(cli.JOBS_DIR, exist_ok=True)
    decoy = os.path.join(cli.JOBS_DIR, "decoy.lock")
    with open(decoy, "w") as f:
        f.write("not the lock")
    os.symlink(decoy, cli._recover_global_lock_path())
    rc = cli.cmd_recover(argparse.Namespace(slug="dead-1"))
    assert rc == 1
    assert resumed == []
    events = _events(capsys)
    assert len(events) == 1
    assert events[0]["signal"] == "needs-attention"
    assert "lock acquisition failed" in events[0]["detail"]


def test_recover_per_slug_lock_refuses_symlink(cli, monkeypatch, capsys):
    # The per-slug lock `with_lock` takes inside the global lock is
    # hardened too: a planted `.<slug>.lock` symlink must fail the open
    # (ELOOP) instead of being followed -- "w" would have truncated the
    # link target. The worker fails closed and loud: needs-attention,
    # no resume attempted, decoy bytes untouched.
    _make_job(cli, "dead-1")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    resumed = []
    monkeypatch.setattr(cli, "cmd_resume",
                        lambda a, **k: resumed.append(a.slug) or 0)
    os.makedirs(cli.JOBS_DIR, exist_ok=True)
    decoy = os.path.join(cli.JOBS_DIR, "precious.txt")
    with open(decoy, "w") as f:
        f.write("precious data")
    os.symlink(decoy, os.path.join(cli.JOBS_DIR, ".dead-1.lock"))
    rc = cli.cmd_recover(argparse.Namespace(slug="dead-1"))
    assert rc == 1
    assert resumed == []
    assert open(decoy).read() == "precious data"  # never truncated
    events = _events(capsys)
    assert len(events) == 1
    assert events[0]["signal"] == "needs-attention"
    assert "lock acquisition failed" in events[0]["detail"]


def test_dispatch_refuses_symlinked_log(cli, monkeypatch):
    # A symlinked recovery log must fail the open (ELOOP) instead of
    # letting a planted link steer the worker's stdout/stderr elsewhere:
    # the dispatch fails closed like any other dispatch failure, and the
    # watch pass reports needs-attention (no worker spawned).
    spawned = []
    monkeypatch.setattr(cli.subprocess, "Popen",
                        lambda *a, **k: spawned.append(a) or None)
    logp = cli._recover_log_path("my-job")
    os.makedirs(os.path.dirname(logp), exist_ok=True)
    decoy = os.path.join(os.path.dirname(logp), "decoy.log")
    with open(decoy, "w") as f:
        f.write("not the log")
    os.symlink(decoy, logp)
    assert cli._dispatch_recover_worker("my-job") is False
    assert spawned == []
    assert open(decoy).read() == "not the log"  # never written through


# --- O_NONBLOCK + regular-file hardening (#1804) ------------------------------


def _run_open_guarded(fn, timeout_s=10):
    """Run an open-path callable in a daemon thread with a timeout.

    Pristine (pre-#1804) code blocks forever opening a reader-less FIFO
    at the lock/log path; the guard turns that hang into a test failure
    instead of wedging the suite. Fixed code fails the open fast, so
    the thread always finishes well inside the timeout.
    """
    q = queue.Queue()

    def _target():
        try:
            q.put(("ok", fn()))
        except BaseException as e:  # noqa: BLE001 -- re-raised below
            q.put(("err", e))

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    try:
        kind, value = q.get(timeout=timeout_s)
    except queue.Empty:
        pytest.fail("open hung on a planted FIFO: the #1804 fail-fast "
                    "open did not refuse it")
    if kind == "err":
        raise value
    return value


def test_recover_global_lock_refuses_fifo(cli):
    # A planted FIFO at the global lock path must fail the open fast
    # (ENXIO from O_NONBLOCK, or the fstat regular-file check for a
    # reader-bearing FIFO) instead of hanging the detached recover
    # worker with no timeout.
    os.makedirs(cli.JOBS_DIR, exist_ok=True)
    os.mkfifo(cli._recover_global_lock_path())
    with pytest.raises(OSError):
        _run_open_guarded(lambda: cli._recover_global_lock().__enter__())


def test_recover_per_slug_lock_refuses_fifo(cli):
    # Same plant at the per-slug `with_lock` path.
    os.makedirs(cli.JOBS_DIR, exist_ok=True)
    os.mkfifo(os.path.join(cli.JOBS_DIR, ".dead-1.lock"))
    with pytest.raises(OSError):
        _run_open_guarded(lambda: cli.with_lock("dead-1", lambda: "ran"))


def test_dispatch_refuses_fifo_log(cli, monkeypatch):
    # A planted FIFO at the recovery log path must fail the dispatch
    # fast (False) instead of wedging the whole 15-minute watchdog pass
    # on the log open; the pass reports needs-attention, no worker
    # spawned.
    spawned = []
    monkeypatch.setattr(cli.subprocess, "Popen",
                        lambda *a, **k: spawned.append(a) or None)
    logp = cli._recover_log_path("my-job")
    os.makedirs(os.path.dirname(logp), exist_ok=True)
    os.mkfifo(logp)
    assert _run_open_guarded(
        lambda: cli._dispatch_recover_worker("my-job")) is False
    assert spawned == []


def test_recover_global_lock_refuses_reader_bearing_fifo(cli):
    # fstat branch of _nofollow_regular_opener (#1804): O_NONBLOCK
    # alone does NOT refuse a FIFO with a reader, so hold one open and
    # require the regular-file check to fail the open fast. The
    # match="non-regular" pins that it is the fstat branch refusing,
    # not the ENXIO path. Deterministic: with a reader held, even
    # unhardened code opens without hanging, so a regression fails
    # cleanly instead of wedging the suite.
    os.makedirs(cli.JOBS_DIR, exist_ok=True)
    path = cli._recover_global_lock_path()
    os.mkfifo(path)
    rfd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        with pytest.raises(OSError, match="non-regular"):
            _run_open_guarded(lambda: cli._recover_global_lock().__enter__())
    finally:
        os.close(rfd)


def test_recover_per_slug_lock_refuses_reader_bearing_fifo(cli):
    # Same reader-bearing plant at the per-slug `with_lock` path.
    os.makedirs(cli.JOBS_DIR, exist_ok=True)
    path = os.path.join(cli.JOBS_DIR, ".dead-1.lock")
    os.mkfifo(path)
    rfd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        with pytest.raises(OSError, match="non-regular"):
            _run_open_guarded(lambda: cli.with_lock("dead-1", lambda: "ran"))
    finally:
        os.close(rfd)


def test_dispatch_refuses_reader_bearing_fifo_log(cli, monkeypatch):
    # A reader-bearing FIFO at the recovery log path must fail the
    # dispatch (False), not silently serialize on / spawn through it.
    spawned = []
    monkeypatch.setattr(cli.subprocess, "Popen",
                        lambda *a, **k: spawned.append(a) or None)
    logp = cli._recover_log_path("my-job")
    os.makedirs(os.path.dirname(logp), exist_ok=True)
    os.mkfifo(logp)
    rfd = os.open(logp, os.O_RDONLY | os.O_NONBLOCK)
    try:
        assert _run_open_guarded(
            lambda: cli._dispatch_recover_worker("my-job")) is False
        assert spawned == []
    finally:
        os.close(rfd)
