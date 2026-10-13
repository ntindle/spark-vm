"""Tests for the session-exited watch signal (issue #42).

Issue #42: when the `muse` process inside a job tmux pane exits (crash,
OOM, operator `q`), the tmux session usually survives -- the pane drops
back to a shell prompt. The content-based dead-TUI check lumps this
state into the generic `tui-dead` signal; the issue proposes a
process-based probe (walk the pane's process tree) and a prompt,
precise `session-exited` signal.

`_pane_tree_has_tui` walks /proc (read-only, stat files only -- no
cmdlines, so no secrets) for a muse-family process in the pane's tree,
using the same identity rule as `_is_tui_process`. It never raises:
an unreadable tree yields None (inconclusive), and the caller keeps
the generic tui-dead in that case -- the probe only ever REFINES the
dead-pane diagnosis, never suppresses a signal.
"""
import importlib.machinery
import importlib.util
import json as _json
import os
import sys
import time as _time

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
    return load_script("muse_job_cli_session_exited", CLI_PATH)


def _write_stat(proc_root, pid, comm, ppid):
    # /proc/<pid>/stat shape: pid (comm) state ppid ...
    d = os.path.join(proc_root, str(pid))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "stat"), "w") as f:
        f.write("%d (%s) S %d 100 0 0 0\n" % (pid, comm, ppid))


def _tree(proc_root, spec):
    # spec: {pid: (comm, ppid)}
    for pid, (comm, ppid) in spec.items():
        _write_stat(proc_root, pid, comm, ppid)


# ---------------------------------------------------------------------------
# _pane_tree_has_tui against a fake /proc


def test_direct_child_tui_found(cli, tmp_path):
    proc = str(tmp_path / "proc")
    _tree(proc, {100: ("bash", 1), 101: ("muse", 100), 102: ("sh", 1)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is True


def test_grandchild_tui_found(cli, tmp_path):
    # The walk is a real tree walk, not a direct-children check: a
    # direct-children-only implementation fails this test.
    proc = str(tmp_path / "proc")
    _tree(proc, {100: ("bash", 1), 101: ("sh", 100), 102: ("node", 101)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is True


def test_truncated_versioned_binary_matches(cli, tmp_path):
    # /proc comm truncates to 15 chars; muse-bin-1.3.0-R3233.1 presents
    # as muse-bin-1.3.0- -- the muse-bin- prefix rule still matches.
    proc = str(tmp_path / "proc")
    _tree(proc, {100: ("bash", 1), 101: ("muse-bin-1.3.0-", 100)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is True


def test_no_tui_in_tree(cli, tmp_path):
    proc = str(tmp_path / "proc")
    _tree(proc, {100: ("bash", 1), 101: ("vim", 100), 102: ("python3", 101)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is False


def test_substring_name_is_not_a_match(cli, tmp_path):
    # The identity rule is exact/prefix, not substring: "my-muse-tool"
    # must not count as the TUI.
    proc = str(tmp_path / "proc")
    _tree(proc, {100: ("bash", 1), 101: ("my-muse-tool", 100)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is False


def test_parens_and_spaces_in_comm_parse(cli, tmp_path):
    # comm may contain spaces and parens; the parse must still recover
    # the right comm and ppid (first '(' to last ')').
    proc = str(tmp_path / "proc")
    _tree(proc, {100: ("bash", 1),
                 101: ("my (weird) proc", 100),
                 102: ("muse", 101)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is True


def test_unrelated_subtree_ignored(cli, tmp_path):
    # A muse process in ANOTHER tree must not satisfy this pane's probe.
    proc = str(tmp_path / "proc")
    _tree(proc, {100: ("bash", 1), 200: ("bash", 1), 201: ("muse", 200)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is False


def test_unknown_pane_pid_is_inconclusive(cli, tmp_path):
    proc = str(tmp_path / "proc")
    _tree(proc, {100: ("bash", 1)})
    assert cli._pane_tree_has_tui(999, proc_root=proc) is None


def test_unreadable_proc_root_is_inconclusive(cli, tmp_path):
    assert cli._pane_tree_has_tui(100, proc_root=str(tmp_path / "nope")) is None


def test_malformed_stat_skipped_not_fatal(cli, tmp_path):
    proc = str(tmp_path / "proc")
    d = os.path.join(proc, "101")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "stat"), "w") as f:
        f.write("garbage with no parens at all\n")
    _tree(proc, {100: ("bash", 1), 102: ("muse", 100)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is True


def test_non_digit_entries_ignored(cli, tmp_path):
    proc = str(tmp_path / "proc")
    os.makedirs(os.path.join(proc, "self"), exist_ok=True)
    _tree(proc, {100: ("bash", 1)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is False


def test_pane_pid_itself_may_be_the_tui(cli, tmp_path):
    proc = str(tmp_path / "proc")
    _tree(proc, {100: ("muse", 1)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is True


def test_non_utf8_comm_does_not_raise(cli, tmp_path):
    # A process can set arbitrary bytes in its comm (prctl PR_SET_NAME).
    # The probe's "never raises" contract requires the read to survive
    # undecodable bytes -- errors="replace", not a locale-decode crash
    # that would kill the whole watch pass.
    proc = str(tmp_path / "proc")
    d = os.path.join(proc, "101")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "stat"), "wb") as f:
        f.write(b"101 (\xff\xfe-not-utf8) S 100 100 0 0 0\n")
    _tree(proc, {100: ("bash", 1), 102: ("muse", 100)})
    assert cli._pane_tree_has_tui(100, proc_root=proc) is True


def test_pane_pid_rejects_garbage(cli, monkeypatch):
    # tmux display-message output is untrusted: non-numeric, zero, and
    # negative values all read as inconclusive (None), never as a pid.
    import subprocess as _subprocess

    def fake_run(stdout):
        def _run(*argv, **kwargs):
            return _subprocess.CompletedProcess(
                args=list(argv), returncode=0,
                stdout=stdout.encode(), stderr=b"")
        return _run

    for bad in ("abc\n", "\n", "0\n", "-3\n", "12x\n"):
        monkeypatch.setattr(cli, "run", fake_run(bad))
        assert cli._pane_pid("mjob-demo") is None
    # A tmux failure is inconclusive too, not a crash.
    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: (_ for _ in ()).throw(
                            _subprocess.CalledProcessError(1, "tmux")))
    assert cli._pane_pid("mjob-demo") is None
    # And a well-formed pid passes through.
    monkeypatch.setattr(cli, "run", fake_run("4321\n"))
    assert cli._pane_pid("mjob-demo") == 4321


# ---------------------------------------------------------------------------
# job_status wires the probe


def _status_harness(cli, monkeypatch, pane, pane_cmd):
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: True)
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: (pane, pane_cmd))
    monkeypatch.setattr(cli, "head_info", lambda uuid: (None, 0))
    monkeypatch.setattr(cli, "last_event", lambda uuid: None)
    monkeypatch.setattr(cli, "_tmux_session_created",
                        lambda slug: _time.time())
    monkeypatch.setattr(cli, "_cached_dir_bytes", lambda job, slug: 0)


def _job(slug="demo"):
    return {"slug": slug, "session_uuid": None, "state": "active",
            "started_at": _time.time()}


def test_status_sets_proc_exited_when_probe_conclusive(cli, monkeypatch):
    _status_harness(cli, monkeypatch, "$ \n", "bash")
    monkeypatch.setattr(cli, "_pane_pid", lambda target: 4321)
    monkeypatch.setattr(cli, "_pane_tree_has_tui", lambda pid: False)
    st = cli.job_status(_job(), "demo")
    assert st["pane_live_tui"] is False
    assert st["pane_proc_exited"] is True


def test_status_clears_proc_exited_when_probe_inconclusive(cli, monkeypatch):
    # tmux hiccup, unreadable /proc, raced pane pid: the probe says None
    # and the status keeps the generic diagnosis (tui-dead downstream).
    _status_harness(cli, monkeypatch, "$ \n", "bash")
    monkeypatch.setattr(cli, "_pane_pid", lambda target: None)
    calls = []
    monkeypatch.setattr(cli, "_pane_tree_has_tui",
                        lambda pid: calls.append(pid) or None)
    st = cli.job_status(_job(), "demo")
    assert st["pane_proc_exited"] is False
    assert calls == []  # no pane pid: the walk never runs


def test_status_never_probes_a_live_pane(cli, monkeypatch):
    # A live pane trivially has the process; the /proc walk is skipped.
    # (Pane content mirrors tests/test_tui_banner.py's LIVE_PANE.)
    live = ("◆ Ran 2 commands · Probe rotation transform direction · ✓ · "
            "3.1s · ctrl+o\n\n  Thinking…\n\n❯ ")
    _status_harness(cli, monkeypatch, live, "muse")
    calls = []
    monkeypatch.setattr(cli, "_pane_pid",
                        lambda target: calls.append(target) or 4321)
    st = cli.job_status(_job(), "demo")
    assert st["pane_live_tui"] is True
    assert st["pane_proc_exited"] is False
    assert calls == []


# ---------------------------------------------------------------------------
# cmd_watch emission contract


def _make_watch_job(cli, slug):
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    os.makedirs(cli.METADATA_DIR, exist_ok=True)
    job = {"slug": slug, "state": "active", "started_at": _time.time(),
           "session_uuid": None}
    with open(cli.job_json_path(slug), "w") as f:
        _json.dump(job, f)


def _dead_shell_status(**kw):
    st = {
        "slug": "demo", "job_state": "active", "tmux_alive": True,
        "pane_live_tui": False, "pane_resume_banner": False,
        "pane_trust_prompt": False, "pane_trust_unverified": False,
        "pane_cmd": "bash", "pane_proc_exited": False,
        "session_created": _time.time(), "session_uuid": None,
        "session_status": None, "bytes_total": 0, "bytes_delta": 0,
        "last_hook_event": None, "progress_age_s": None,
        "dir_bytes": 0, "elapsed_h": 0.1, "budget_hours": 8,
    }
    st.update(kw)
    return st


def _watch_events(cli, capsys):
    import argparse
    rc = cli.cmd_watch(argparse.Namespace())
    assert rc == 0
    return [_json.loads(l) for l in capsys.readouterr().out.splitlines()
            if l.strip()]


def _watch_harness(cli, monkeypatch, status):
    _make_watch_job(cli, "exitjob")
    monkeypatch.setattr(cli, "job_status", lambda job, slug: status)
    monkeypatch.setattr(cli, "_emit_tui_swap_event",
                        lambda job, slug, pane_cmd, events: None)
    monkeypatch.setattr(cli, "maybe_adopt_session",
                        lambda job, slug: (None, None))
    monkeypatch.setattr(cli, "git_diffstat", lambda path: "")


def test_watch_emits_session_exited_for_dead_process(cli, monkeypatch, capsys):
    # End to end through cmd_watch: tmux alive, pane a shell, and the
    # process probe conclusively found no muse-family process -- the
    # prompt session-exited signal fires, not generic tui-dead.
    status = _dead_shell_status(slug="exitjob", pane_proc_exited=True)
    _watch_harness(cli, monkeypatch, status)
    events = _watch_events(cli, capsys)
    by_sig = {}
    for e in events:
        by_sig.setdefault(e["signal"], []).append(e)
    assert "session-exited" in by_sig
    ev = by_sig["session-exited"][0]
    assert ev["job"] == "exitjob"
    assert "muse-job kill" in ev["detail"]  # the operator remedy
    assert "tui-dead" not in by_sig  # distinct signal, not the generic lump


def test_watch_keeps_tui_dead_when_probe_inconclusive(cli, monkeypatch, capsys):
    # The probe could not run (or found a lingering process): fail-loud
    # toward the generic tui-dead, never silent, never session-exited.
    status = _dead_shell_status(slug="exitjob", pane_proc_exited=False)
    _watch_harness(cli, monkeypatch, status)
    events = _watch_events(cli, capsys)
    by_sig = {}
    for e in events:
        by_sig.setdefault(e["signal"], []).append(e)
    assert "tui-dead" in by_sig
    assert "session-exited" not in by_sig


def test_watch_tolerates_missing_proc_exited_key(cli, monkeypatch, capsys):
    # Older/dict-built status shapes lack the key; the .get default keeps
    # the generic tui-dead path (no KeyError, no new signal).
    status = _dead_shell_status(slug="exitjob")
    del status["pane_proc_exited"]
    _watch_harness(cli, monkeypatch, status)
    events = _watch_events(cli, capsys)
    by_sig = {}
    for e in events:
        by_sig.setdefault(e["signal"], []).append(e)
    assert "tui-dead" in by_sig
    assert "session-exited" not in by_sig
