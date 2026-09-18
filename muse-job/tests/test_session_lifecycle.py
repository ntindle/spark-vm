"""Session-lifecycle trust tests for muse-job (arch deep-read 2026-09-18).

job.json lives in the job dir, which the job agent can rewrite (issue #11):
every field in it is attacker-influenced. These tests pin the manager-side
consequences:

  1. `trusted_job_paths` re-derives destructive inputs from the slug and
     containment-checks the pristine repo -- a recorded `branch: "main"`,
     a `worktree` pointing at another job's tree, or a pristine repo that
     does not have this job's worktree registered, fails closed with an
     explicit message instead of reaching `git branch -D` /
     `worktree remove --force` (close) or choosing the resume tmux's
     working directory. The derived layout is the canonical contract;
     divergence is tampering-or-migration, never silently overridden.
  2. `cmd_list` must not silently drop a job whose `started_at` is garbage
     (residual of the issue #3 `_num` fix: job_status/watch were sanitized,
     cmd_list was missed).
  3. `watch` lazily adopts a session uuid when spawn's 90s discovery missed
     it -- otherwise the job stays half-blind (no liveness/done/tamper
     signals) and un-resumable forever.
  4. A failed `spawn` (worktree add blows up) removes its job dir, so the
     next spawn with the same slug doesn't fail "job dir exists".
  5. The Stop/SessionEnd hooks skip events with no session id instead of
     appending them to a write-only events/unknown.jsonl.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import sys
import time

import pytest

HOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "plugin", "hooks")
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
    """Import bin/muse-job with HOME pointed at an isolated tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_lifecycle", CLI_PATH)


def make_job_dir(cli, slug="demo", **overrides):
    jd = os.path.join(cli.JOBS_DIR, slug)
    os.makedirs(jd, exist_ok=True)
    pristine = os.path.join(cli.REPOS_DIR, "demo-repo")
    os.makedirs(pristine, exist_ok=True)
    job = {
        "slug": slug,
        "repo": "https://example.com/demo.git",
        "pristine": pristine,
        "worktree": os.path.join(jd, "work"),
        "branch": f"job/{slug}",
        "state": "active",
        "budget_hours": 8,
        "started_at": time.time() - 60,
    }
    job.update(overrides)
    with open(os.path.join(jd, "job.json"), "w") as f:
        json.dump(job, f)
    return jd, job


# --- trusted_job_paths -------------------------------------------------------

def test_trusted_paths_derive_from_slug(cli, monkeypatch):
    """A legit record yields the slug-derived worktree/branch; the
    registration check binds the recorded pristine repo to this job."""
    jd, job = make_job_dir(cli)
    work = os.path.join(jd, "work")
    _git_fake_with_worktree(monkeypatch, cli, work)
    got_work, pristine, branch = cli.trusted_job_paths("demo", job)
    assert (got_work, branch) == (work, "job/demo")
    assert pristine == job["pristine"]


def test_trusted_paths_reject_pristine_outside_repos(cli):
    _jd, job = make_job_dir(cli, pristine="/tmp/evil")
    with pytest.raises(RuntimeError, match="outside"):
        cli.trusted_job_paths("demo", job)


def test_trusted_paths_reject_missing_pristine(cli):
    _jd, job = make_job_dir(cli)
    del job["pristine"]
    with pytest.raises(RuntimeError, match="no recorded pristine"):
        cli.trusted_job_paths("demo", job)


def test_close_never_runs_forged_destructive_git(cli, monkeypatch):
    """cmd_close with a tampered job.json (branch=main, pristine outside
    ~/repos) must fail closed BEFORE any git command runs."""
    calls = []

    def fake_run(*argv, **kw):
        calls.append(list(argv))
        if kw.get("check", True):
            return None
        class P:
            returncode = 0
            stdout = b""
            stderr = b""
        return P()

    monkeypatch.setattr(cli, "run", fake_run)
    make_job_dir(cli, branch="main", pristine="/tmp/evil",
                 worktree="/home/ntindle/muse-jobs/victim/work")
    with pytest.raises(RuntimeError, match="outside"):
        cli.cmd_close(argparse.Namespace(slug="demo"))
    git_calls = [c for c in calls if c[0] == "git"]
    assert git_calls == [], f"no git may run on a tampered record: {git_calls}"


def test_trusted_paths_reject_diverged_branch(cli):
    _jd, job = make_job_dir(cli, branch="main")
    with pytest.raises(RuntimeError, match="diverged"):
        cli.trusted_job_paths("demo", job)


def test_trusted_paths_reject_diverged_worktree(cli):
    _jd, job = make_job_dir(cli, worktree="/home/ntindle/muse-jobs/victim/work")
    with pytest.raises(RuntimeError, match="diverged"):
        cli.trusted_job_paths("demo", job)


def _git_fake_with_worktree(monkeypatch, cli, work):
    """Fake cli.run: answers `git worktree list --porcelain` with the given
    work path registered, everything else succeeds silently."""
    calls = []

    def fake_run(*argv, **kw):
        calls.append(list(argv))
        class P:
            returncode = 0
            stdout = b""
            stderr = b""
        if "worktree" in argv and "list" in argv:
            P.stdout = f"worktree {work}\n\nbranch refs/heads/job/demo\n".encode()
        return P()

    monkeypatch.setattr(cli, "run", fake_run)
    return calls


def test_close_uses_derived_branch_on_legit_record(cli, monkeypatch):
    """On a legit record the destructive branch is job/<slug> even when the
    record carries no branch field at all (derivation, not record)."""
    jd, job = make_job_dir(cli)
    del job["branch"]
    with open(os.path.join(jd, "job.json"), "w") as f:
        json.dump(job, f)
    work = os.path.join(jd, "work")
    calls = _git_fake_with_worktree(monkeypatch, cli, work)
    cli.cmd_close(argparse.Namespace(slug="demo"))
    branch_deletes = [c for c in calls if "branch" in c and "-D" in c]
    assert branch_deletes, "expected a branch -D call"
    assert branch_deletes[0][-1] == "job/demo"


def test_close_refuses_unregistered_worktree(cli, monkeypatch):
    """A pristine repo that does not have the derived worktree registered
    (forged pristine pointing at another repo under ~/repos) fails closed
    before any destructive git runs."""
    jd, job = make_job_dir(cli)
    work = os.path.join(jd, "work")
    calls = []

    def fake_run(*argv, **kw):
        calls.append(list(argv))
        class P:
            returncode = 0
            stdout = b"worktree /somewhere/else/work\n"
            stderr = b""
        return P()

    monkeypatch.setattr(cli, "run", fake_run)
    with pytest.raises(RuntimeError, match="not a registered worktree"):
        cli.cmd_close(argparse.Namespace(slug="demo"))
    destructive = [c for c in calls
                   if "branch" in c and "-D" in c
                   or ("worktree" in c and "remove" in c)]
    assert destructive == []


# --- cmd_list started_at -----------------------------------------------------

def test_list_keeps_job_with_corrupt_started_at(cli, capsys):
    make_job_dir(cli, started_at="not-a-number")
    cli.cmd_list(argparse.Namespace(json=True))
    out = json.loads(capsys.readouterr().out)
    assert [j["slug"] for j in out] == ["demo"]


# --- watch late uuid adoption ------------------------------------------------

def test_watch_adopts_late_session_uuid(cli, monkeypatch, capsys):
    """A job whose spawn missed uuid discovery gets it adopted on the next
    watch pass, and the adoption is paged."""
    jd, job = make_job_dir(cli)
    assert job.get("session_uuid") is None
    work = os.path.join(jd, "work")
    os.makedirs(work, exist_ok=True)
    # The hook registration appears late (slow first model call).
    os.makedirs(cli.SESSIONS_DIR, exist_ok=True)
    with open(os.path.join(cli.SESSIONS_DIR, "late-sid.json"), "w") as f:
        json.dump({"session_id": "late-sid", "cwd": work,
                   "first_seen": time.time(), "tools": []}, f)
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: True)
    cli.cmd_watch(argparse.Namespace())
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines()
             if l.strip()]
    adopted = [e for e in lines if e.get("signal") == "session-adopted"]
    assert adopted and adopted[0]["job"] == "demo"
    with open(os.path.join(jd, "job.json")) as f:
        assert json.load(f)["session_uuid"] == "late-sid"


# --- failed spawn cleanup ----------------------------------------------------

def test_failed_spawn_removes_job_dir(cli, monkeypatch, tmp_path):
    """If `git worktree add` fails, spawn removes the job dir (and the
    half-added branch) so the slug can be retried."""
    calls = []

    def fake_run(*argv, **kw):
        calls.append(list(argv))
        if "worktree" in argv and "add" in argv:
            raise RuntimeError("boom: worktree add failed")
        class P:
            returncode = 0
            stdout = b"deadbeef"
            stderr = b""
        return P()

    monkeypatch.setattr(cli, "run", fake_run)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do the thing")
    with pytest.raises(RuntimeError, match="boom"):
        cli.cmd_spawn(argparse.Namespace(
            slug="demo", repo="https://example.com/demo.git",
            prompt_file=str(prompt), base=None, budget_hours=8))
    assert not os.path.exists(os.path.join(cli.JOBS_DIR, "demo"))
    branch_deletes = [c for c in calls if "branch" in c and "-D" in c]
    assert branch_deletes and branch_deletes[0][-1] == "job/demo"


# --- hooks skip unknown session ids ------------------------------------------

def _run_hook(name, payload, home):
    import subprocess
    env = dict(os.environ, HOME=str(home))
    proc = subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, name)],
        input=json.dumps(payload), capture_output=True, text=True,
        env=env, timeout=30)
    assert proc.returncode == 0, proc.stderr


def test_stop_hook_skips_missing_session_id(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _run_hook("stop.py",
              {"last_assistant_message": "DONE: all good", "cwd": "/tmp/x"},
              home)
    events = home / ".local" / "share" / "muse-job" / "events"
    assert not events.exists() or list(events.iterdir()) == []


def test_session_end_hook_skips_missing_session_id(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _run_hook("session-end.py", {"reason": "exit", "cwd": "/tmp/x"}, home)
    events = home / ".local" / "share" / "muse-job" / "events"
    assert not events.exists() or list(events.iterdir()) == []
