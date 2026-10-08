"""Regression tests for issue #5 (kill must be terminal-ish).

cmd_kill used to leave `state: "active"` untouched, so the next `watch`
pass saw the dead tmux as a crash and auto-resumed the job -- the
operator's deliberate kill was undone within one cron period. The fix:
kill records state "killed" (watch only acts on active/blocked, so it
leaves a killed job alone), and `resume` is the deliberate re-activation
that returns the job to "active". Unknown slugs keep the old permissive
kill behavior (no job.json to mark).
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
    return load_script("muse_job_cli_killstate", CLI_PATH)


def _make_job(cli, slug, **fields):
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    os.makedirs(cli.METADATA_DIR, exist_ok=True)
    job = {"slug": slug, "state": "active", "started_at": time.time()}
    job.update(fields)
    with open(cli.job_json_path(slug), "w") as f:
        json.dump(job, f)
    return jd


def _read_job(cli, slug):
    with open(cli.job_json_path(slug)) as f:
        return json.load(f)


def test_kill_marks_job_killed(cli, monkeypatch, capsys):
    slug = "killme"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "_kill_process_tree", lambda s: [])
    rc = cli.cmd_kill(argparse.Namespace(slug=slug))
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["state"] == "killed"
    assert _read_job(cli, slug)["state"] == "killed"


def test_kill_marks_job_killed_even_with_leaks(cli, monkeypatch, capsys):
    # Leaked PIDs are the honest signal; the terminal-ish state must not
    # depend on a clean reap.
    slug = "killleaky"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "_kill_process_tree", lambda s: [424242])
    rc = cli.cmd_kill(argparse.Namespace(slug=slug))
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["state"] == "killed"
    assert out["leaked_pids"] == [424242]
    assert _read_job(cli, slug)["state"] == "killed"


def test_kill_unknown_slug_stays_permissive(cli, monkeypatch, capsys):
    # No job.json: kill's tmux/process semantics are unchanged, and the
    # output carries no state key rather than a fabricated one.
    monkeypatch.setattr(cli, "_kill_process_tree", lambda s: [])
    rc = cli.cmd_kill(argparse.Namespace(slug="nosuchjob"))
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert "state" not in out


def test_watch_leaves_killed_job_alone(cli, monkeypatch, capsys):
    # The #5 resurrection path: watch must not attempt recovery of a
    # killed job (no tmux probe needed -- watch_one gates on state first).
    slug = "killedjob"
    _make_job(cli, slug, state="killed")
    called = []
    monkeypatch.setattr(cli, "cmd_resume", lambda a: called.append(a) or 0)
    rc = cli.cmd_watch(argparse.Namespace())
    assert rc == 0
    assert called == []
    assert capsys.readouterr().out.strip() == ""


def test_resume_reactivates_killed_job(cli, monkeypatch, capsys):
    slug = "reactivate"
    _make_job(cli, slug, state="killed", session_uuid="sess-uuid-1")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    monkeypatch.setattr(cli, "_session_uuid_ok",
                        lambda job: ("sess-uuid-1", False))
    monkeypatch.setattr(cli, "trusted_job_paths",
                        lambda s, j: (cli.job_dir(s), "/tmp/pristine",
                                      "job/" + s))
    monkeypatch.setattr(cli, "session_bound_to_workdir", lambda u, w: True)

    class _R:
        def __init__(self, out=b""):
            self.stdout = out
            self.returncode = 0

    # Pane text must not match the gone-session wordings, or resume takes
    # the fallback-fresh branch.
    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: _R(b"Muse TUI live -- input box"))
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda s, timeout=20: False)
    faketime = types.SimpleNamespace(time=time.time,
                                     sleep=lambda s: None)
    monkeypatch.setattr(cli, "time", faketime)

    rc = cli.cmd_resume(argparse.Namespace(slug=slug))
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["resumed"] == "sess-uuid-1"
    assert _read_job(cli, slug)["state"] == "active"


def test_resume_keeps_active_job_active(cli, monkeypatch, capsys):    # No-op state write for the normal path: resume of an active job must
    # not downgrade or churn anything.
    slug = "stillactive"
    _make_job(cli, slug, state="active", session_uuid="sess-uuid-2")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    monkeypatch.setattr(cli, "_session_uuid_ok",
                        lambda job: ("sess-uuid-2", False))
    monkeypatch.setattr(cli, "trusted_job_paths",
                        lambda s, j: (cli.job_dir(s), "/tmp/pristine",
                                      "job/" + s))
    monkeypatch.setattr(cli, "session_bound_to_workdir", lambda u, w: True)

    class _R:
        def __init__(self, out=b""):
            self.stdout = out
            self.returncode = 0

    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: _R(b"Muse TUI live -- input box"))
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda s, timeout=20: False)
    faketime = types.SimpleNamespace(time=time.time,
                                     sleep=lambda s: None)
    monkeypatch.setattr(cli, "time", faketime)

    rc = cli.cmd_resume(argparse.Namespace(slug=slug))
    assert rc == 0
    assert _read_job(cli, slug)["state"] == "active"


def test_watch_resume_refuses_mid_recovery_kill(cli, monkeypatch, capsys):
    # Engineering review: a watch pass already inside watch_one when the
    # operator kills the job must not auto-revive it. Simulate the flip:
    # load_job returns "active" at resume start, "killed" at the
    # pre-activation re-read. The auto path must tear down the recovery
    # session and leave the job alone (raising, so watch_one pages
    # needs-attention instead of "recovered").
    slug = "midrecovery"
    _make_job(cli, slug, state="active", session_uuid="sess-uuid-3")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    monkeypatch.setattr(cli, "_session_uuid_ok",
                        lambda job: ("sess-uuid-3", False))
    monkeypatch.setattr(cli, "trusted_job_paths",
                        lambda s, j: (cli.job_dir(s), "/tmp/pristine",
                                      "job/" + s))
    monkeypatch.setattr(cli, "session_bound_to_workdir", lambda u, w: True)

    real_load = cli.load_job
    real_save = cli.save_job
    calls = {"n": 0}

    def flipping_load(s):
        calls["n"] += 1
        job = real_load(s)
        if calls["n"] > 1 and job.get("state") == "active":
            # The operator's kill lands mid-recovery: persisted to disk,
            # exactly as cmd_kill would write it.
            job["state"] = "killed"
            real_save(job, s)
        return job

    monkeypatch.setattr(cli, "load_job", flipping_load)

    killed_sessions = []

    class _R:
        def __init__(self, out=b""):
            self.stdout = out
            self.returncode = 0

    def fake_run(*a, **k):
        if a[:3] == ("tmux", "kill-session", "-t"):
            killed_sessions.append(a[3])
        return _R(b"Muse TUI live -- input box")

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda s, timeout=20: False)
    faketime = types.SimpleNamespace(time=time.time,
                                     sleep=lambda s: None)
    monkeypatch.setattr(cli, "time", faketime)

    with pytest.raises(RuntimeError, match="left the monitored states"):
        cli.cmd_resume(argparse.Namespace(slug=slug), _from_watch=True)
    assert killed_sessions == [f"mjob-{slug}"]
    assert _read_job(cli, slug)["state"] == "killed"


def test_resume_fallback_fresh_reactivates(cli, monkeypatch, capsys):
    # The fallback-fresh path shares the same re-activation write site as
    # the primary path; prove it re-activates too and adopts the new uuid.
    slug = "fallback"
    _make_job(cli, slug, state="killed", session_uuid="old-uuid")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: False)
    monkeypatch.setattr(cli, "_session_uuid_ok",
                        lambda job: ("old-uuid", False))
    monkeypatch.setattr(cli, "trusted_job_paths",
                        lambda s, j: (cli.job_dir(s), "/tmp/pristine",
                                      "job/" + s))
    monkeypatch.setattr(cli, "session_bound_to_workdir", lambda u, w: True)

    class _R:
        def __init__(self, out=b""):
            self.stdout = out
            self.returncode = 0

    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: _R(
                            b"no retained sessions found for this workspace"))
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda s, timeout=20: False)
    monkeypatch.setattr(cli, "_steer", lambda *a, **k: True)
    monkeypatch.setattr(cli, "find_session",
                        lambda work, since, exclude=None: "new-uuid-9")
    faketime = types.SimpleNamespace(time=time.time,
                                     sleep=lambda s: None)
    monkeypatch.setattr(cli, "time", faketime)

    rc = cli.cmd_resume(argparse.Namespace(slug=slug))
    assert rc == 0
    d = _read_job(cli, slug)
    assert d["state"] == "active"
    assert d["session_uuid"] == "new-uuid-9"


def test_kill_corrupt_job_json_stays_permissive(cli, monkeypatch, capsys):
    # QA B1: kill's process/tree semantics are never-raises. A corrupt
    # job.json must not turn the state-marking into a crash -- warn on
    # stderr, keep rc=0, carry no fabricated state key.
    slug = "corruptjob"
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    os.makedirs(cli.METADATA_DIR, exist_ok=True)
    with open(cli.job_json_path(slug), "w") as f:
        f.write("{not valid json")
    monkeypatch.setattr(cli, "_kill_process_tree", lambda s: [])
    rc = cli.cmd_kill(argparse.Namespace(slug=slug))
    assert rc == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out.strip())
    assert "state" not in out
    assert "could not record killed state" in captured.err


def test_resume_heals_killed_with_live_tmux(cli, monkeypatch, capsys):
    # QA B2: a stale "killed" record with a live session is a dead end
    # (watch skips it; resume refuses). A live session means the job is
    # running: heal the record to active, then refuse as before.
    slug = "healme"
    _make_job(cli, slug, state="killed", session_uuid="sess-uuid-4")
    monkeypatch.setattr(cli, "tmux_alive", lambda s: True)
    with pytest.raises(RuntimeError, match="tmux session already alive"):
        cli.cmd_resume(argparse.Namespace(slug=slug))
    assert _read_job(cli, slug)["state"] == "active"


def test_kill_on_blocked_marks_killed(cli, monkeypatch, capsys):
    slug = "blockedjob"
    _make_job(cli, slug, state="blocked")
    monkeypatch.setattr(cli, "_kill_process_tree", lambda s: [])
    rc = cli.cmd_kill(argparse.Namespace(slug=slug))
    assert rc == 0
    assert _read_job(cli, slug)["state"] == "killed"


def test_kill_twice_is_idempotent(cli, monkeypatch, capsys):
    slug = "twicejob"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "_kill_process_tree", lambda s: [])
    assert cli.cmd_kill(argparse.Namespace(slug=slug)) == 0
    capsys.readouterr()
    assert cli.cmd_kill(argparse.Namespace(slug=slug)) == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["state"] == "killed"
    assert _read_job(cli, slug)["state"] == "killed"
