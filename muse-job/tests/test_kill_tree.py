"""Regression tests for issue #12 item L4.

cmd_kill used to be a bare `tmux kill-session`: detached grandchildren
(nohup'd, backgrounded builds) survived, so runaway jobs persisted past
kill while the client contract (`muse_job.kill`: "Stop the agent's
process tree") promised a tree kill. The fix snapshots the pane subtree
first, kills the session, then SIGTERM -> (grace) -> SIGKILLs the
survivors with a /proc-starttime PID-reuse guard, and reports leaks.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import subprocess
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
    return load_script("muse_job_cli_killtest", CLI_PATH)


def _spawn_tree(cli=None):
    """A 'pane' (python sleeper) with a backgrounded grandchild.

    The grandchild is still a child of the pane at snapshot time — the
    runaway class L4 fixes: tmux kill-session kills the pane, the
    backgrounded build survives reparented to init.
    """
    root = subprocess.Popen(
        [sys.executable, "-c",
         "import subprocess, time; "
         "subprocess.Popen(['sleep', '60']); time.sleep(60)"])
    if cli is not None:
        # The sleeper needs a moment to fork the grandchild.
        deadline = 5.0
        import time as _t
        end = _t.time() + deadline
        while _t.time() < end:
            if len(cli._descendant_pids([root.pid])) >= 2:
                break
            _t.sleep(0.05)
    return root


def test_descendant_pids_finds_subtree(cli):
    root = _spawn_tree(cli)
    try:
        tree = cli._descendant_pids([root.pid])
        assert root.pid in tree
        # The backgrounded `sleep 60` must be in the snapshot.
        assert len(tree) >= 2, "grandchild missing from subtree snapshot"
    finally:
        root.kill()
        root.wait()


def test_proc_starttime_stable_and_none_for_missing(cli):
    p = subprocess.Popen(["sleep", "5"])
    try:
        st1 = cli._proc_starttime(p.pid)
        st2 = cli._proc_starttime(p.pid)
        assert st1 is not None and st1 == st2
        assert cli._proc_starttime(2 ** 31 - 1) is None
    finally:
        p.kill()
        p.wait()


def test_proc_starttime_is_starttime_not_vsize(cli):
    # Security B1: the value must be field 22 (starttime), not field 23
    # (vsize). A sleeping process's vsize is stable, so the stability
    # test above passes either way — pin the semantics: start epoch must
    # fall between boot and now.
    p = subprocess.Popen(["sleep", "5"])
    try:
        st = cli._proc_starttime(p.pid)
        assert st is not None
        btime = None
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("btime "):
                    btime = int(line.split()[1])
                    break
        assert btime is not None
        clk_tck = os.sysconf("SC_CLK_TCK")
        start_epoch = btime + st / clk_tck
        now = time.time()
        assert btime < start_epoch <= now, \
            "starttime derives an implausible epoch %r (btime=%r, now=%r)" \
            % (start_epoch, btime, now)
    finally:
        p.kill()
        p.wait()


def test_proc_starttime_stable_under_memory_growth(cli):
    # Security B1: deterministic pin for the field-22 semantics. vsize
    # (field 23, the old token[20]) grows when the process allocates;
    # starttime (field 22) must not. The btime-plausibility test above
    # cannot discriminate on long-uptime boxes (vsize/CLK_TCK falls
    # inside (btime, now] there) — this one fails on the old code in
    # every environment.
    p = subprocess.Popen([sys.executable, "-c",
                          "import time\n"
                          "time.sleep(2.0)\n"
                          "a=[0]*(12*10**6)\n"
                          "time.sleep(4)"])
    try:
        time.sleep(1.0)
        before = cli._proc_starttime(p.pid)
        time.sleep(3.0)
        after = cli._proc_starttime(p.pid)
        assert before is not None and after == before, \
            "starttime changed across a ~96MB allocation: %r -> %r" \
            % (before, after)
    finally:
        p.kill()
        p.wait()


def test_tmux_pane_pids_excludes_dead_panes(cli, monkeypatch):
    # Security B2: a dead pane's PID may already be recycled by an
    # unrelated process — it must never become a kill root.
    class R:
        stdout = b"1234 0\n5678 1\n9012 0\n"
    monkeypatch.setattr(cli, "run", lambda *a, **k: R())
    assert cli._tmux_pane_pids("x") == [1234, 9012]


def test_kill_process_tree_never_raises_without_tmux(cli, monkeypatch):
    # The "never raises" guarantee covers a missing tmux binary.
    def boom(*a, **k):
        raise FileNotFoundError("tmux")
    monkeypatch.setattr(cli, "run", boom)
    assert cli._kill_process_tree("x") == []


def test_kill_process_tree_reaps_backgrounded_grandchild(cli, monkeypatch):
    # Anti-vacuity: a bare `tmux kill-session` (the old code) leaves the
    # backgrounded sleep alive — this test fails unless the tree walk
    # signals the survivors.
    root = _spawn_tree(cli)
    try:
        tree_before = cli._descendant_pids([root.pid])
        grandchild = [p for p in tree_before if p != root.pid]
        assert grandchild, "no grandchild to reap"

        def fake_run(*argv, **kwargs):
            if argv and argv[0] == "tmux":
                # kill-session: kill the pane root only, like tmux does.
                root.kill()

                class R:
                    returncode = 0
                    stdout = b""
                    stderr = b""
                return R()
            return subprocess.run(list(argv), capture_output=True,
                                  timeout=kwargs.get("timeout", 15))

        monkeypatch.setattr(cli, "run", fake_run)
        monkeypatch.setattr(cli, "_tmux_pane_pids", lambda slug: [root.pid])
        leaked = cli._kill_process_tree("testslug")
        assert leaked == [], "pids survived the tree kill: %r" % (leaked,)
        assert root.poll() is not None
        for p in grandchild:
            assert cli._proc_starttime(p) is None, \
                "grandchild %d survived" % p
    finally:
        for p in (root,):
            try:
                p.kill()
                p.wait()
            except Exception:
                pass
        # Belt and braces: anything left from the tree gets reaped.
        for p in grandchild:
            try:
                os.kill(p, 9)
            except Exception:
                pass


def test_cmd_kill_reports_leaked_pids(cli, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_kill_process_tree", lambda slug: [424242])
    assert cli.cmd_kill(argparse.Namespace(slug="x")) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["slug"] == "x"
    assert out["leaked_pids"] == [424242]
    # Engineering review: tree_killed must not claim success with leaks.
    assert out["tree_killed"] is False


def test_cmd_kill_clean_tree(cli, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_kill_process_tree", lambda slug: [])
    assert cli.cmd_kill(argparse.Namespace(slug="x")) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["leaked_pids"] == []
