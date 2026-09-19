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
  6. `load_job` pins the slug to the manager-side value -- a recorded
     "slug": "victim" / "../../x" cannot steer save_job / job_status /
     verify_done_event paths (review round 2, security blocker 1).
  7. `cmd_resume` re-validates the uuid->workdir binding against the hook
     registry and fails closed when the recorded uuid is not bound to the
     slug-derived workdir (review round 2, security blocker 2).
  8. Watch's late uuid adoption fails closed on a garbage `started_at`
     (no epoch-zero search adopting the oldest-ever registration) and
     prefers the newest registration (review round 2, engineering B2/N2).
  9. `cmd_spawn` / `cmd_close` run under the per-slug lock, so a
     concurrent same-slug spawn cannot pass the exists check mid-clone and
     have its cleanup destroy the winner's state (review round 2,
     engineering B1).
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


# --- review round 2: slug pinning (security blocker 1) -----------------------

# --- arch review round 3: session_uuid whitelist (path-steering) ----------------

def test_event_paths_refuse_malformed_uuid(cli, tmp_path):
    """A forged job['session_uuid'] must never steer manager-side event/view
    reads outside EVENTS_DIR / VIEW_DIR (arch round-3 blocker)."""
    jd, job = make_job_dir(cli)
    # A decoy "event file" outside the events dir a traversal could reach.
    outside = tmp_path / "evil.jsonl"
    outside.write_text(json.dumps({"event": "stop", "state": "done"}) + "\n")
    job["session_uuid"] = "../evil"
    assert cli.head_info(job["session_uuid"]) == (None, 0)
    assert list(cli._iter_events(job["session_uuid"])) == []
    assert cli.event_file_tampered(job["session_uuid"]) is False
    assert cli.last_event(job["session_uuid"]) is None
    job["session_uuid"] = "a/b"
    assert list(cli._iter_events(job["session_uuid"])) == []
    assert cli.head_info(job["session_uuid"]) == (None, 0)
    # Legit uuids still read normally.
    good = "abcDEF_-0123"
    evf = os.path.join(cli.EVENTS_DIR, good + ".jsonl")
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    with open(evf, "w") as f:
        f.write(json.dumps({"event": "stop", "state": "idle"}) + "\n")
    assert cli.last_event(good)["state"] == "idle"


def test_watch_flags_malformed_uuid(cli, monkeypatch, capsys):
    """watch_one pages events-tampered (every pass) on a malformed recorded
    uuid instead of feeding it to event-path reads (arch round-3 blocker;
    final review reclasses malformed uuid as the tamper class)."""
    jd, job = make_job_dir(cli)
    job["session_uuid"] = "../../x"
    job["state"] = "active"
    job["session_started_at"] = time.time() - 7200
    cli.save_job(job, "demo")
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: True)
    cli.cmd_watch(argparse.Namespace())
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines()
             if l.strip()]
    malformed = [e for e in lines
                 if e.get("signal") == "events-tampered"
                 and "malformed" in e.get("detail", "")]
    assert malformed and malformed[0]["job"] == "demo", lines


def test_load_job_pins_slug(cli):
    """A forged "slug" in job.json is pinned to the manager-side slug on
    load, so save_job / job_status / verify_done_event can never write to
    or report on another job's paths."""
    jd, job = make_job_dir(cli)
    job["slug"] = "victim"
    with open(os.path.join(jd, "job.json"), "w") as f:
        json.dump(job, f)
    loaded = cli.load_job("demo")
    assert loaded["slug"] == "demo"
    loaded["state"] = "closed"
    cli.save_job(loaded, "demo")
    assert os.path.exists(os.path.join(jd, "job.json"))
    assert not os.path.exists(os.path.join(cli.JOBS_DIR, "victim"))
    with open(os.path.join(jd, "job.json")) as f:
        assert json.load(f)["slug"] == "demo"


def test_save_job_write_path_uses_manager_slug(cli):
    """save_job(job, slug) writes to the MANAGER slug's path even when the
    record carries a forged slug -- the write path never comes from the
    agent-writable dict (round-2 security blocker, write-path steering)."""
    jd, job = make_job_dir(cli)
    job["slug"] = "victim"
    cli.save_job(job, "demo")
    assert os.path.exists(os.path.join(jd, "job.json"))
    assert not os.path.exists(os.path.join(cli.JOBS_DIR, "victim", "job.json"))
    job["slug"] = "../../x"
    cli.save_job(job, "demo")
    assert not os.path.exists(os.path.join(cli.HOME, "x", "job.json"))


def test_load_job_pins_traversal_slug(cli):
    jd, job = make_job_dir(cli)
    job["slug"] = "../../x"
    with open(os.path.join(jd, "job.json"), "w") as f:
        json.dump(job, f)
    loaded = cli.load_job("demo")
    cli.save_job(loaded, "demo")
    assert os.path.exists(os.path.join(jd, "job.json"))
    assert not os.path.exists(os.path.join(cli.HOME, "x", "job.json"))


# --- review round 2: resume uuid binding (security blocker 2) -----------------

def _write_session_record(cli, sid, cwd, first_seen=None):
    os.makedirs(cli.SESSIONS_DIR, exist_ok=True)
    with open(os.path.join(cli.SESSIONS_DIR, sid + ".json"), "w") as f:
        json.dump({"session_id": sid, "cwd": cwd,
                   "first_seen": first_seen if first_seen is not None else time.time(),
                   "tools": [{"name": "bash"}]}, f)


def test_session_bound_to_workdir(cli):
    jd, _job = make_job_dir(cli)
    work = os.path.join(jd, "work")
    os.makedirs(work, exist_ok=True)
    _write_session_record(cli, "sid-a", work)
    _write_session_record(cli, "sid-b", "/other/work")
    assert cli.session_bound_to_workdir("sid-a", work) is True
    assert cli.session_bound_to_workdir("sid-b", work) is False  # bound elsewhere
    assert cli.session_bound_to_workdir("nope", work) is False   # unknown


def _resume_harness(cli, monkeypatch, uuid):
    """Fake tmux/git for cmd_resume; returns the recorded run() calls."""
    jd, job = make_job_dir(cli, session_uuid=uuid)
    work = os.path.join(jd, "work")
    os.makedirs(work, exist_ok=True)
    calls = []

    def fake_run(*argv, **kw):
        calls.append(list(argv))

        class P:
            returncode = 0
            stdout = b""
            stderr = b""

        if "worktree" in argv and "list" in argv:
            P.stdout = (f"worktree {work}\n\n"
                        f"branch refs/heads/job/demo\n").encode()
        if "capture-pane" in argv:
            P.stdout = b"Muse TUI running -- some output"
        return P()

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: False)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    return calls


def test_resume_refuses_unbound_uuid(cli, monkeypatch, capsys):
    """A forged session_uuid with no hook-registry binding to this job's
    workdir fails closed BEFORE any tmux session is created."""
    calls = _resume_harness(cli, monkeypatch, "forged-sid")
    with pytest.raises(RuntimeError, match="not bound"):
        cli.cmd_resume(argparse.Namespace(slug="demo"))
    assert not [c for c in calls if "new-session" in c]


def test_resume_accepts_bound_uuid(cli, monkeypatch, capsys):
    """The legit path still works: bound uuid -> tmux resumes it."""
    calls = _resume_harness(cli, monkeypatch, "real-sid")
    jd = os.path.join(cli.JOBS_DIR, "demo")
    work = os.path.join(jd, "work")
    _write_session_record(cli, "real-sid", work)
    assert cli.cmd_resume(argparse.Namespace(slug="demo")) == 0
    steer = [c for c in calls if "send-keys" in c]
    assert steer and "muse resume 'real-sid'" in " ".join(steer[0])
    out = capsys.readouterr().out
    assert json.loads(out.strip())["resumed"] == "real-sid"


# --- review round 2: adoption fail-closed + newest-first (engineering B2/N2) --

def test_adoption_refuses_garbage_started_at(cli):
    """A garbage started_at must not trigger an epoch-zero search adopting
    the oldest-ever registration -- fail closed with an attention detail."""
    _jd, job = make_job_dir(cli, started_at="not-a-number")
    found, attention = cli.maybe_adopt_session(job, "demo")
    assert found is None
    assert attention and "started_at" in attention


def test_adoption_prefers_newest_registration(cli):
    jd, job = make_job_dir(cli, started_at=time.time() - 60)
    work = os.path.join(jd, "work")
    os.makedirs(work, exist_ok=True)
    now = time.time()
    _write_session_record(cli, "old-sid", work, first_seen=now - 50)
    _write_session_record(cli, "new-sid", work, first_seen=now - 5)
    found, attention = cli.maybe_adopt_session(job, "demo")
    assert (found, attention) == ("new-sid", None)


def test_spawn_holds_per_slug_lock(cli, monkeypatch, tmp_path):
    """cmd_spawn serializes on the per-slug lock: the exists check and the
    whole setup run inside with_lock, so a concurrent same-slug spawn fails
    fast instead of racing the clone."""
    held = []

    def fake_lock(slug, fn):
        held.append(slug)
        return fn()

    monkeypatch.setattr(cli, "with_lock", fake_lock)

    def boom(*argv, **kw):
        if "worktree" in argv and "add" in argv:
            raise RuntimeError("worktree add failed")

        class P:
            returncode = 0
            stdout = b"deadbeef"
            stderr = b""

        return P()

    monkeypatch.setattr(cli, "run", boom)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do the thing")
    with pytest.raises(RuntimeError, match="worktree add failed"):
        cli.cmd_spawn(argparse.Namespace(
            slug="demo", repo="https://example.com/demo.git",
            prompt_file=str(prompt), base=None, budget_hours=8))
    assert held == ["demo"]
