"""Tests for deploy/golden-image/pair-tick-wrapper.sh (D-RW5, #1274, B1).

The wrapper is the D-RW5 unenrolled-skip gate for the golden-image pairing
programs: `loop` mode skips the client while enrollment.json is absent
(once-loud-then-quiet, re-checking every tick so redeem re-arms the loop
without a restart); `daemon` mode sleep-polls (with backoff) until
enrollment.json exists and then execs the daemon, so D-RW3's exit-code
mapping applies to the daemon proper, never to the pre-enrollment gate.

Tests exercise the real script as a subprocess against a stub client, with
a fake HOME per test. PAIR_WRAPPER_MAX_TICKS / PAIR_WRAPPER_BACKOFF_BASE
are the wrapper's documented test seams.
"""
import os
import stat
import subprocess
import threading
import time

import pytest

GOLDEN_DIR = os.path.dirname(os.path.abspath(__file__))
WRAPPER = os.path.join(GOLDEN_DIR, "pair-tick-wrapper.sh")
DOCKERFILE = os.path.join(GOLDEN_DIR, "Dockerfile")

STUB_CLIENT = """#!/usr/bin/env python3
import os, sys
logdir = os.environ["STUB_LOG"]
with open(os.path.join(logdir, "argv"), "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
open(os.path.join(logdir, "marker"), "w").write("ran\\n")
sys.exit(int(os.environ.get("STUB_EXIT", "0")))
"""


@pytest.fixture()
def harness(tmp_path):
    """Stub client + env factory; returns (run, paths)."""
    logdir = tmp_path / "log"
    logdir.mkdir()
    stub = tmp_path / "stub_client.py"
    stub.write_text(STUB_CLIENT)
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    home = tmp_path / "home"
    home.mkdir()

    def run(*argv, extra_env=None, timeout=30):
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["STUB_LOG"] = str(logdir)
        env.pop("SVM_PAIR_DIR", None)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["/bin/bash", WRAPPER, *argv],
            env=env, capture_output=True, text=True, timeout=timeout,
        )

    def invocations():
        p = logdir / "argv"
        return p.read_text().splitlines() if p.exists() else []

    return run, home, logdir, invocations


def _enroll(home):
    d = home / ".config" / "spark-pair"
    d.mkdir(parents=True, exist_ok=True)
    (d / "enrollment.json").write_text("{}")


def test_loop_skips_client_pre_redeem_quietly_after_one_loud_line(harness):
    """Unenrolled: one loud block naming the redeem step, client never runs."""
    run, home, logdir, invocations = harness
    r = run("loop", "0.1", "/usr/bin/env", "true",
            extra_env={"PAIR_WRAPPER_MAX_TICKS": "3"})
    assert r.returncode == 0
    assert invocations() == []
    assert r.stdout.count("no enrollment.json") == 1
    assert "redeem" in r.stdout


def test_loop_invokes_client_when_enrolled(harness):
    """Enrolled: the client runs every tick, no loud line."""
    run, home, logdir, invocations = harness
    _enroll(home)
    r = run("loop", "0.1", str(logdir.parent / "stub_client.py"),
            extra_env={"PAIR_WRAPPER_MAX_TICKS": "2"})
    assert r.returncode == 0
    assert len(invocations()) == 2
    assert "no enrollment.json" not in r.stdout


def test_loop_rearms_when_enrollment_lands_mid_run(harness):
    """Redeem mid-run re-arms the loop: ticks start without a restart (B1)."""
    run, home, logdir, invocations = harness
    stub = str(logdir.parent / "stub_client.py")
    timer = threading.Timer(0.15, lambda: _enroll(home))
    timer.start()
    try:
        r = run("loop", "0.1", stub,
                extra_env={"PAIR_WRAPPER_MAX_TICKS": "6"}, timeout=30)
    finally:
        timer.cancel()
    assert r.returncode == 0
    # Late enrollment must flip later ticks on: generous lower bound.
    assert len(invocations()) >= 2
    assert r.stdout.count("no enrollment.json") == 1


def test_loop_tick_failure_does_not_kill_the_loop(harness):
    """Cron semantics: a failing tick exits the one-shot, never the loop."""
    run, home, logdir, invocations = harness
    _enroll(home)
    r = run("loop", "0.1", str(logdir.parent / "stub_client.py"),
            extra_env={"PAIR_WRAPPER_MAX_TICKS": "3", "STUB_EXIT": "1"})
    assert r.returncode == 0
    assert len(invocations()) == 3


def test_daemon_waits_then_execs_post_redeem(harness):
    """Daemon mode: quiet poll until enrollment.json lands, then exec (B1)."""
    run, home, logdir, invocations = harness
    stub = str(logdir.parent / "stub_client.py")
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["STUB_LOG"] = str(logdir)
    env["PAIR_WRAPPER_BACKOFF_BASE"] = "0.1"
    env.pop("SVM_PAIR_DIR", None)
    proc = subprocess.Popen(
        ["/bin/bash", WRAPPER, "daemon", stub],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        time.sleep(0.4)
        # Still polling: the daemon must not have run yet.
        assert not (logdir / "marker").exists()
        _enroll(home)
        stdout, _ = proc.communicate(timeout=15)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    assert proc.returncode == 0
    assert (logdir / "marker").exists()
    assert invocations() != []
    assert stdout.count("no enrollment.json") == 1
    assert "redeem" in stdout


def test_daemon_execs_immediately_when_enrolled(harness):
    """Enrolled: the daemon gate execs at once, no loud line."""
    run, home, logdir, invocations = harness
    _enroll(home)
    r = run("daemon", str(logdir.parent / "stub_client.py"),
            extra_env={"PAIR_WRAPPER_BACKOFF_BASE": "0.1"})
    assert r.returncode == 0
    assert (logdir / "marker").exists()
    assert "no enrollment.json" not in r.stdout


def test_state_dir_resolution_prefers_svm_pair_dir(harness, tmp_path):
    """The wrapper mirrors the client's state-dir resolution (SVM_PAIR_DIR)."""
    run, home, logdir, invocations = harness
    alt = tmp_path / "alt"
    (alt / ".config").mkdir(parents=True)
    statedir = alt / "pair-state"
    statedir.mkdir()
    (statedir / "enrollment.json").write_text("{}")
    r = run("loop", "0.1", str(logdir.parent / "stub_client.py"),
            extra_env={"PAIR_WRAPPER_MAX_TICKS": "1",
                       "SVM_PAIR_DIR": str(statedir)})
    assert r.returncode == 0
    # The env dir was used (client ran); HOME's dir was never created.
    assert len(invocations()) == 1
    assert not (home / ".config").exists()


def test_usage_errors(harness):
    """Bad invocations fail loud with exit 2."""
    run, *_ = harness
    assert run("loop").returncode == 2
    assert run("daemon").returncode == 2
    assert run("bogus").returncode == 2
    assert run().returncode == 2


def test_dockerfile_installs_wrapper():
    """The recipe must install the wrapper the three programs now invoke."""
    with open(DOCKERFILE, encoding="utf-8") as f:
        text = f.read()
    assert "COPY deploy/golden-image/pair-tick-wrapper.sh /usr/local/bin/pair-tick-wrapper.sh" in text
    assert "/usr/local/bin/pair-tick-wrapper.sh" in text
    assert "0755" in text
