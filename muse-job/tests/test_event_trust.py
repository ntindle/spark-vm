"""Regression tests for issue #3: job agent can forge its own turn-state events.

Covers the fix in two rounds:
  1. Hooks (stop.py, session-end.py, session-start.py) ignore
     MUSE_JOB_EVENTS / MUSE_JOB_SESSIONS env overrides -- a job agent with a
     full shell could otherwise export them mid-session and blind the watchdog.
     The review round added: session-id whitelisting, no writes through
     symlinks, ANSI/control-character sanitization of agent-influenced text.
  2. `muse-job watch`/`status` treat hook `done` events as cooperative
     telemetry: `verify_done_event` cross-checks a done event against the
     job's recorded session uuid, the slug-derived worktree cwd, and a
     non-empty SUMMARY.md regular file before the operator acts on it. Fail closed. The review
     round added: whole-file done-claim scanning (burial resistance),
     read-side sanitization of the agent-writable dedup cursor, re-page
     backoff (done-repeated coalescing), recency-based events-missing
     anchored to session_started_at with per-session dedup, and an
     events-tampered signal for symlinked event files.
  3. Final adversarial review (security, engineering, architecture):
     the persistent done-claim dedup cursor and suppression latch in
     agent-writable job.json were both demonstrably plantable, so they
     are GONE -- every visible done pages every pass (fail loud) until
     the operator closes the job. Non-regular event files (symlink, FIFO,
     device, dir) are refused without opening; a malformed session_uuid
     pages events-tampered instead of silently blinding triage; the 2 MB
     scan truncation is a loud per-pass signal; C1 controls are stripped.
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys

import pytest

HOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "plugin", "hooks")
CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job")


def load_script(name, path):
    """Import an extensionless script by explicit loader."""
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
    return load_script("muse_job_cli", CLI_PATH)


@pytest.fixture()
def stop_hook():
    return load_script("stop_hook_test", os.path.join(HOOKS_DIR, "stop.py"))


def run_hook(name, payload, env_extra):
    proc = subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env_extra,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return proc


def test_stop_hook_ignores_events_env_override(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    decoy = tmp_path / "void"
    decoy.mkdir()
    env = dict(os.environ, HOME=str(home),
               MUSE_JOB_EVENTS=str(decoy))
    run_hook("stop.py",
             {"session_id": "sid-1", "last_assistant_message": "DONE: all good",
              "cwd": "/tmp/x", "turn_id": 3},
             env)
    canonical = home / ".local" / "share" / "muse-job" / "events" / "sid-1.jsonl"
    assert canonical.is_file(), "hook must write to the hardcoded events dir"
    evt = json.loads(canonical.read_text().strip().splitlines()[-1])
    assert evt["state"] == "done"
    assert list(decoy.iterdir()) == [], "env override must be ignored entirely"


def test_session_end_hook_ignores_events_env_override(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    decoy = tmp_path / "void"
    decoy.mkdir()
    env = dict(os.environ, HOME=str(home),
               MUSE_JOB_EVENTS=str(decoy))
    run_hook("session-end.py",
             {"session_id": "sid-2", "reason": "exit", "cwd": "/tmp/x"},
             env)
    canonical = home / ".local" / "share" / "muse-job" / "events" / "sid-2.jsonl"
    assert canonical.is_file()
    assert list(decoy.iterdir()) == []


def test_session_start_hook_ignores_sessions_env_override(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    decoy = tmp_path / "void"
    decoy.mkdir()
    env = dict(os.environ, HOME=str(home),
               MUSE_JOB_SESSIONS=str(decoy))
    run_hook("session-start.py",
             {"session_id": "sid-3", "cwd": "/tmp/work", "model": "m",
              "tools": [{"name": "bash"}]},
             env)
    canonical = home / ".local" / "share" / "muse-job" / "sessions" / "sid-3.json"
    assert canonical.is_file()
    assert list(decoy.iterdir()) == []


# --- verify_done_event -------------------------------------------------------

def make_job(cli, slug="demo"):
    job = {
        "slug": slug,
        "session_uuid": "uuid-abc",
        "worktree": "/jobs/demo/work",
        "state": "active",
    }
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    return job


def done_event(cli=None, slug="demo", **kw):
    # Default cwd is the DERIVED worktree (~/muse-jobs/<slug>/work):
    # verify_done_event derives it from the manager-side slug, never from
    # the agent-writable job.json record.
    cwd = kw.pop("cwd", None)
    if cwd is None:
        assert cli is not None, "done_event needs cli or an explicit cwd"
        cwd = os.path.join(cli.job_dir(slug), "work")
    ev = {"event": "stop", "state": "done", "session_id": "uuid-abc",
          "cwd": cwd, "detail": "finished", "ts": 1.0}
    ev.update(kw)
    return ev


def test_verify_done_happy_path(cli):
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("# Summary\nDone.\n")
    assert cli.verify_done_event(job, done_event(cli), job["slug"]) == (True, "")


def test_verify_done_rejects_missing_summary(cli):
    # The forge scenario from issue #3: agent appends a fake done line to its
    # own event file but never wrote SUMMARY.md. Must fail closed.
    job = make_job(cli)
    ok, reason = cli.verify_done_event(job, done_event(cli), job["slug"])
    assert ok is False
    assert "SUMMARY.md" in reason


def test_verify_done_rejects_empty_summary(cli):
    job = make_job(cli)
    open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w").close()
    ok, reason = cli.verify_done_event(job, done_event(cli), job["slug"])
    assert ok is False
    assert "empty" in reason


def test_verify_done_rejects_wrong_session(cli):
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(
        job, done_event(cli, session_id="some-other-session"), job["slug"])
    assert ok is False
    assert "session" in reason


def test_verify_done_rejects_cwd_mismatch(cli):
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(job, done_event(cli, cwd="/tmp/evil"), job["slug"])
    assert ok is False
    assert "cwd" in reason


def test_verify_done_accepts_cwd_under_worktree(cli):
    # The agent may legitimately cd into a subdir before ending the turn;
    # raw string equality would false-positive here (review finding). The
    # worktree is DERIVED from the manager-side slug.
    job = make_job(cli)
    work = os.path.join(cli.job_dir("demo"), "work")
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    sub = os.path.join(work, "subdir")
    assert cli.verify_done_event(
        job, done_event(cli, cwd=sub), job["slug"]) == (True, "")
    # ...but a sibling-prefix path must not pass via startswith tricks.
    evil = work + "-evil"
    ok, _ = cli.verify_done_event(
        job, done_event(cli, cwd=evil), job["slug"])
    assert ok is False


def test_verify_done_ignores_forged_recorded_worktree(cli):
    # Arch review: the recorded `worktree` field is agent-writable (issue
    # #11) and must not steer the cwd containment check -- a forged
    # worktree pointing at the forged event's cwd must still fail.
    job = make_job(cli)
    job["worktree"] = "/tmp/evil-work"
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(
        job, done_event(cli, cwd="/tmp/evil-work"), job["slug"])
    assert ok is False
    assert "cwd" in reason


def test_verify_done_rejects_missing_cwd(cli):
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ev = done_event(cli)
    del ev["cwd"]
    ok, reason = cli.verify_done_event(job, ev, job["slug"])
    assert ok is False
    assert "cwd" in reason


def test_verify_done_rejects_job_without_session_uuid(cli):
    job = make_job(cli)
    job["session_uuid"] = None
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(job, done_event(cli), job["slug"])
    assert ok is False
    assert "uuid" in reason


# --- handle_done_claim: a done is a claim, never a state transition ----------

def test_full_forgery_never_transitions_to_done(cli):
    """Red-team regression test for issue #3 (security review).

    The sophisticated attack: the agent writes a non-empty SUMMARY.md and
    appends a done line with the CORRECT session_id and cwd -- every
    verify_done_event check passes. The fix must still NOT transition the
    job to done; it pages `done-claimed` for the operator to confirm.
    """
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("# forged summary\nAll done (not really).")
    sig = cli.handle_done_claim(job, done_event(cli), job["slug"])
    assert sig is not None
    assert sig["signal"] == "done-claimed"
    # The whole point: no state transition on telemetry, however convincing.
    assert job["state"] == "active"
    assert "state" not in sig


def test_lazy_forgery_pages_done_unverified(cli):
    # The lazy attack: fake done line, no SUMMARY.md.
    job = make_job(cli)
    sig = cli.handle_done_claim(job, done_event(cli), job["slug"])
    assert sig is not None
    assert sig["signal"] == "done-unverified"
    assert job["state"] == "active"


def test_done_claim_pages_every_pass_fail_loud(cli):
    # Final review: there is no dedup cursor anywhere in agent-writable
    # state -- the same claim pages on every pass until the operator closes
    # the job. Silent suppression was the vulnerability; repeated paging is
    # the fix.
    job = make_job(cli)
    ev = done_event(cli, ts=100.0)
    first = cli.handle_done_claim(job, ev, job["slug"])
    assert first is not None and first["signal"] == "done-unverified"
    second = cli.handle_done_claim(job, ev, job["slug"])
    assert second is not None and second["signal"] == "done-unverified"
    # A planted done_claim_ts remnant is migrated out, never honored.
    job["done_claim_ts"] = 100.0
    third = cli.handle_done_claim(job, ev, job["slug"])
    assert third is not None and third["signal"] == "done-unverified"
    assert "done_claim_ts" not in job


def test_done_claim_future_ts_pages_normally(cli):
    # A forged far-future ts no longer interacts with any dedup state: it
    # pages like any other claim (clamped for ordering only).
    import time as _time
    job = make_job(cli)
    now = _time.time()
    forged = done_event(cli, ts=now + 10 * 365 * 24 * 3600)  # +10 years
    assert cli.handle_done_claim(job, forged, job["slug"], now) is not None
    assert cli._claim_ts(forged, now) <= now
    assert cli.handle_done_claim(job, done_event(cli, ts=now + 60), job["slug"], now + 60) is not None


def test_done_claim_nan_ts_pages(cli):
    # NaN normalizes to 0 for ordering; with no dedup state it pages.
    import time as _time
    job = make_job(cli)
    now = _time.time()
    ev = done_event(cli, ts=float("nan"))
    assert cli.handle_done_claim(job, ev, job["slug"], now) is not None
    assert cli.handle_done_claim(job, ev, job["slug"], now) is not None


def test_done_claim_missing_ts_pages(cli):
    job = make_job(cli)
    ev = done_event(cli)
    del ev["ts"]
    assert cli.handle_done_claim(job, ev, job["slug"]) is not None
    assert cli.handle_done_claim(job, ev, job["slug"]) is not None


# --- check_events_liveness ---------------------------------------------------

def live_status(tmux_alive=True, last_hook_event=None, started_ago_s=3600,
               session_created=None):
    # session_created: tmux server-side session creation epoch (the
    # unspoofable grace anchor, issue #23 sec review). None -> the job.json
    # anchor fallback is used, as on a tmux-unreachable pass.
    return {
        "tmux_alive": tmux_alive,
        "last_hook_event": last_hook_event,
        "session_created": session_created,
    }


def test_events_missing_pages_when_blinded(cli):
    job = make_job(cli)
    job["started_at"] = 1_000_000.0
    now = job["started_at"] + 31 * 60
    sig = cli.check_events_liveness(job, live_status(), now)
    assert sig is not None
    assert sig["signal"] == "events-missing"


def test_events_missing_silent_within_grace(cli):
    # A long first turn is legitimate; don't page before 30m.
    job = make_job(cli)
    job["started_at"] = 1_000_000.0
    now = job["started_at"] + 10 * 60
    assert cli.check_events_liveness(job, live_status(), now) is None


def test_events_missing_silent_when_events_exist(cli):
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_started_at"] = now - 5 * 3600
    st = live_status(last_hook_event={"event": "stop", "state": "idle",
                                      "ts": now - 60})
    assert cli.check_events_liveness(job, st, now) is None


def test_events_missing_silent_when_tmux_dead(cli):
    job = make_job(cli)
    job["started_at"] = 1_000_000.0
    now = job["started_at"] + 5 * 3600
    assert cli.check_events_liveness(job, live_status(tmux_alive=False), now) is None


def test_absent_session_uuid_silent_only_within_discovery_grace(cli):
    # Final review (arch): an absent uuid is legitimate ONLY during initial
    # discovery (~90s). Past the 30m grace it pages loudly -- wiping
    # session_uuid to "" or deleting the key used to blind liveness AND
    # done triage with zero signal on any pass.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_uuid"] = None
    job["session_started_at"] = now - 60
    assert cli.check_events_liveness(job, live_status(), now) is None
    job["session_started_at"] = now - 3600
    sig = cli.check_events_liveness(job, live_status(), now)
    assert sig is not None and sig["signal"] == "events-tampered"
    assert "uuid" in sig["detail"]
    # "" and a deleted key behave the same as None.
    for wiped in ("",):
        job["session_uuid"] = wiped
        sig = cli.check_events_liveness(job, live_status(), now)
        assert sig is not None and sig["signal"] == "events-tampered"
    del job["session_uuid"]
    sig = cli.check_events_liveness(job, live_status(), now)
    assert sig is not None and sig["signal"] == "events-tampered"
    # Tmux dead: nothing to page about (the resume path owns that).
    sig = cli.check_events_liveness(
        job, live_status(tmux_alive=False), now)
    assert sig is None

# --- find_session ------------------------------------------------------------

def test_find_session_excludes_old_uuid(cli, tmp_path):
    # Issue #3 round-2 review: the resume fallback must not re-adopt the dead
    # session's registration -- an explicit exclude is robust even within the
    # 10s since_ts slack. Newest-first otherwise: the just-launched session
    # is the one discovery wants.
    import time as _time
    sessdir = os.path.join(str(tmp_path), ".local", "share", "muse-job", "sessions")
    os.makedirs(sessdir, exist_ok=True)
    now = _time.time()
    for sid, seen in (("old-uuid", now - 5), ("new-uuid", now - 1)):
        with open(os.path.join(sessdir, sid + ".json"), "w") as f:
            json.dump({"session_id": sid, "cwd": "/w", "first_seen": seen,
                       "tools": [{"name": "bash"}]}, f)
    assert cli.find_session("/w", now) == "new-uuid"
    assert cli.find_session("/w", now, exclude="new-uuid") == "old-uuid"


def test_classify_markers(stop_hook):
    assert stop_hook.classify("DONE: all finished")[0] == "done"
    assert stop_hook.classify("BLOCKED: need input")[0] == "blocked"
    assert stop_hook.classify("What should I do next?")[0] == "question"
    assert stop_hook.classify("some idle chatter")[0] == "idle"


# --- review round: hook sid whitelist + symlink refusal ---------------------

def test_stop_hook_rejects_path_traversal_sid(tmp_path):
    # The session id is used in the event filename; "../evil" must not
    # escape the events dir.
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home))
    run_hook("stop.py",
             {"session_id": "../evil", "last_assistant_message": "DONE: x",
              "cwd": "/t"},
             env)
    evdir = home / ".local" / "share" / "muse-job" / "events"
    assert not evdir.exists() or list(evdir.iterdir()) == []
    assert not (home / ".local" / "share" / "muse-job" / "evil.jsonl").exists()


def test_stop_hook_refuses_symlink_event_file(tmp_path):
    # Cross-job tampering: the agent pre-creates its event file as a symlink
    # into a victim file; the hook must not write through it.
    home = tmp_path / "home"
    home.mkdir()
    evdir = home / ".local" / "share" / "muse-job" / "events"
    evdir.mkdir(parents=True)
    victim = tmp_path / "victim.txt"
    victim.write_text("untouched")
    (evdir / "sid-9.jsonl").symlink_to(victim)
    env = dict(os.environ, HOME=str(home))
    run_hook("stop.py",
             {"session_id": "sid-9", "last_assistant_message": "DONE: x",
              "cwd": "/t"},
             env)
    assert victim.read_text() == "untouched"


def test_session_start_hook_rejects_bad_sid(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home))
    run_hook("session-start.py",
             {"session_id": "../../evil", "cwd": "/t", "model": "m",
              "tools": []},
             env)
    regdir = home / ".local" / "share" / "muse-job" / "sessions"
    assert not regdir.exists() or list(regdir.iterdir()) == []


def test_classify_strips_ansi(stop_hook):
    # ANSI in the detail could erase/spoof the security labels printed by
    # `muse-job status` and the watch pages.
    state, detail = stop_hook.classify(
        "DONE: ok\x1b[2K\x1b[1Ainjected\x1b]0;title\x07 done")
    assert state == "done"
    assert "\x1b" not in detail
    assert "ok" in detail and "done" in detail


def test_session_end_hook_sanitizes_reason(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home))
    run_hook("session-end.py",
             {"session_id": "sid-r", "reason": "exit\x1b[2Kboom", "cwd": "/t"},
             env)
    p = home / ".local" / "share" / "muse-job" / "events" / "sid-r.jsonl"
    evt = json.loads(p.read_text().strip())
    assert "\x1b" not in (evt["reason"] or "")


# --- review round: manager refuses symlinked event files ---------------------

def test_event_file_tampered_refuses_symlink_and_fifo(cli, tmp_path):
    # Final review (sec + arch): non-regular event files are refused WITHOUT
    # opening them. A blocking open(2) on a planted FIFO hung the whole
    # watch pass; now lstat refuses before any open, so completing at all
    # (far under the old hang) is the regression check.
    import time as _time
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    target = tmp_path / "t.jsonl"
    target.write_text(json.dumps(done_event(cli)) + "\n")
    link = os.path.join(cli.EVENTS_DIR, "uuid-abc.jsonl")
    os.symlink(str(target), link)
    assert cli.event_file_tampered("uuid-abc") is True
    assert list(cli._iter_events("uuid-abc")) == []
    os.unlink(link)
    os.mkfifo(link)
    t0 = _time.time()
    try:
        assert cli.event_file_tampered("uuid-abc") is True
        assert list(cli._iter_events("uuid-abc")) == []
    finally:
        os.unlink(link)
    assert _time.time() - t0 < 5, "FIFO read must not block"


def test_event_file_missing_is_not_tampered(cli):
    # A missing file is events-missing (liveness), not events-tampered.
    assert cli.event_file_tampered("uuid-abc") is False
    assert list(cli._iter_events("uuid-abc")) == []


def test_handle_done_claim_sanitizes_forged_detail(cli):
    # Forged event lines bypass the hook sanitizer; the manager must clean
    # agent-influenced text before embedding it in signals.
    job = make_job(cli)
    ev = done_event(cli, detail="done\x1b[2K\x1b[1AFAKE verified")
    sig = cli.handle_done_claim(job, ev, job["slug"])
    assert "\x1b" not in sig["detail"]


# --- review round: buried done claims ----------------------------------------

def write_events(cli, uuid, lines):
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    p = os.path.join(cli.EVENTS_DIR, uuid + ".jsonl")
    with open(p, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return p


def test_buried_done_claim_still_pages(cli):
    # Security review B1: a forged trailing `idle` line must not bury a
    # genuine done claim -- the claim scan covers the whole file.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    write_events(cli, "uuid-abc", [
        done_event(cli, ts=now - 300),
        {"event": "stop", "state": "idle", "session_id": "uuid-abc",
         "cwd": "/jobs/demo/work", "ts": now},
    ])
    # The tail-line reader sees only the forged idle line...
    assert cli.last_event("uuid-abc")["state"] == "idle"
    # ...but the claim scan still finds the done line.
    done_evs = cli.done_events("uuid-abc", now)
    assert len(done_evs) == 1 and done_evs[0][0]["state"] == "done"
    sig = cli.handle_done_claim(job, done_evs[0][0], job["slug"], now)
    assert sig is not None and sig["signal"] == "done-claimed"


def test_done_events_yield_oldest_first(cli):
    # Issue #23 B3: triage order is oldest-first so a newer forgery can never
    # displace a genuine claim in the same window.
    import time as _time
    now = _time.time()
    write_events(cli, "uuid-abc", [
        done_event(cli, ts=now - 100, detail="second"),
        done_event(cli, ts=now - 300, detail="first"),
    ])
    evs = cli.done_events("uuid-abc", now)
    assert [e["detail"] for e, _ in evs] == ["first", "second"]


# --- review round: agent-writable dedup cursor -------------------------------

def test_b1_same_ts_forged_done_plus_planted_cursor_cannot_suppress(cli):
    # Final security review (demonstrated exploit): the agent appends a
    # forged done at ts F and plants done_claim_ts = F in job.json. The old
    # design suppressed BOTH the genuine and the forged claim before
    # verification ever ran -- zero signals, total silence. With no
    # persistent suppression state, every visible done pages.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    F = now - 300
    write_events(cli, "uuid-abc", [
        done_event(cli, ts=F - 60, detail="genuine"),
        done_event(cli, ts=F, detail="forged", session_id="bogus", cwd="/nope"),
    ])
    job["done_claim_ts"] = F  # the plant: must be inert
    events = []
    cli.triage_done_events(job, "uuid-abc", now, events)
    sigs = [e["signal"] for e in events]
    assert sigs == ["done-claimed", "done-unverified"], sigs
    assert "done_claim_ts" not in job  # plant migrated out


def test_done_claims_coalesce_after_three_in_24h(cli):
    # Issue #23 B2: the burst label is derived from the event file, never
    # from job.json. With >3 dones in the last 24h visible, claims are
    # labeled done-repeated; every claim still produces exactly one signal.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    sigs = []
    for i in range(5):
        sig = cli.handle_done_claim(job, done_event(cli, ts=now - 300 + i),
                                    job["slug"], now,
                                    recent_count=i + 1)
        sigs.append(sig["signal"])
    assert sigs[:3] == ["done-unverified"] * 3
    assert sigs[3:] == ["done-repeated"] * 2


def test_done_claim_burst_window_ignores_old_claims(cli):
    # Only dones within the last 24h count toward the burst label.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    old = [done_event(cli, ts=now - 25 * 3600 + i) for i in range(5)]
    new = [done_event(cli, ts=now - 10)]
    write_events(cli, "uuid-abc", old + new)
    events = []
    cli.triage_done_events(job, "uuid-abc", now, events)
    # 6 dones total but only 1 in the 24h window -> no done-repeated label.
    assert [e["signal"] for e in events] == ["done-unverified"] * 6


# --- review round: verify_done_event fail-closed -----------------------------

def test_verify_done_rejects_job_without_slug(cli):
    # The worktree is derived from the manager-side slug; without a usable
    # slug the check fails closed instead of comparing against
    # realpath("") -- the CLI's own cwd, an attacker-influenced path
    # (old Engineering B1, which keyed this on the recorded worktree).
    job = make_job(cli)
    del job["slug"]
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(job, done_event(cli), None)
    assert ok is False
    assert "slug" in reason


def test_verify_done_ignores_planted_worktree(cli):
    # The worktree is derived from the manager-side slug, never from
    # agent-writable job.json (issue #11). A planted worktree -- even a
    # dict that would crash os.path.realpath -- is inert: verification
    # proceeds against the derived worktree.
    job = make_job(cli)
    job["worktree"] = {"planted": True}
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(job, done_event(cli), job["slug"])
    assert ok is True, reason
    # A planted worktree cannot widen containment either: an event cwd
    # inside the planted location but outside the derived worktree fails.
    job["worktree"] = "/tmp/evil-work"
    ok, reason = cli.verify_done_event(
        job, done_event(cli, cwd="/tmp/evil-work"), job["slug"])
    assert ok is False and "worktree" in reason


def test_verify_done_rejects_summary_directory(cli):
    # Engineering B2: getsize() succeeds on directories; `mkdir SUMMARY.md`
    # must not satisfy the "non-empty SUMMARY.md" check.
    job = make_job(cli)
    os.makedirs(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), exist_ok=True)
    ok, reason = cli.verify_done_event(job, done_event(cli), job["slug"])
    assert ok is False


# --- review round: recency-based, session-anchored liveness ------------------

def test_events_missing_pages_on_backdated_junk_line(cli):
    # Security review B3: one junk line with a backdated ts must not silence
    # the signal; recency is measured on the normalized event ts.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_started_at"] = now - 3600
    st = live_status(last_hook_event={"event": "stop", "state": "idle",
                                      "ts": now - 7200})
    sig = cli.check_events_liveness(job, st, now)
    assert sig is not None and sig["signal"] == "events-missing"


def test_events_missing_silent_on_fresh_heartbeat(cli):
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_started_at"] = now - 3600
    st = live_status(last_hook_event={"event": "stop", "state": "idle",
                                      "ts": now - 60})
    assert cli.check_events_liveness(job, st, now) is None


def test_events_missing_clamps_future_started_at(cli):
    # The agent bumps started_at forward to keep the grace window open
    # forever; clamp on read instead of paging or crashing.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_started_at"] = now + 10 * 365 * 24 * 3600
    assert cli.check_events_liveness(job, live_status(), now) is None


def test_events_missing_uses_session_started_at_not_spawn(cli):
    # Engineering B3 / arch B2: after a resume fallback the new session gets
    # a fresh grace window even though the job itself is old.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["started_at"] = now - 5 * 3600
    job["session_started_at"] = now - 60
    assert cli.check_events_liveness(job, live_status(), now) is None


def test_events_missing_pages_every_pass_while_blind(cli):
    # Sec round 2: the dedup latch used to live in agent-writable job.json,
    # where the agent could plant it and blind watch permanently. No latch
    # anymore: the signal fires on every pass while the condition holds.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_started_at"] = now - 3600
    job["events_missing_paged_uuid"] = "uuid-abc"  # a planted latch: ignored
    job["events_tampered_paged_uuid"] = "uuid-abc"
    sig1 = cli.check_events_liveness(job, live_status(), now)
    sig2 = cli.check_events_liveness(job, live_status(), now)
    assert sig1 is not None and sig1["signal"] == "events-missing"
    assert sig2 is not None and sig2["signal"] == "events-missing"


def test_num_sanitizer_rejects_garbage(cli):
    assert cli._num(5, 0) == 5
    assert cli._num(2.5, 0) == 2.5
    assert cli._num("x", 7) == 7
    assert cli._num(None, 7) == 7
    assert cli._num(True, 7) == 7
    assert cli._num(float("nan"), 7) == 7


def test_job_status_survives_forged_numerics(cli, tmp_path):
    # Sec round 2: non-numeric started_at/last_bytes/budget_hours in
    # agent-writable job.json must not raise (watch_one would swallow it and
    # silence every signal for the job).
    job = make_job(cli)
    job["started_at"] = "x"
    job["last_bytes"] = {"evil": 1}
    job["budget_hours"] = "never"
    st = cli.job_status(job, job["slug"])  # must not raise
    assert isinstance(st["elapsed_h"], float)
    assert st["bytes_delta"] >= 0
    # budget comparison path used by cmd_watch must not raise either.
    assert (st["elapsed_h"] > (cli._num(job.get("budget_hours"), 8) or 8)) in (True, False)


def test_legacy_cursor_latch_keys_are_migrated_out(cli):
    # Remnants of earlier designs are dead weight that a future reader (or
    # a confused merge) could mistake for live state; triage removes them.
    job = make_job(cli)
    for k, v in (("done_claim_ts", 1.0), ("done_page_count", 5),
                 ("done_page_window_start", 1.0), ("done_repeated_paged", True),
                 ("done_repeated_for_ts", 1.0)):
        job[k] = v
    sig = cli.handle_done_claim(job, done_event(cli), job["slug"])
    assert sig is not None
    for k in ("done_claim_ts", "done_page_count", "done_page_window_start",
              "done_repeated_paged", "done_repeated_for_ts"):
        assert k not in job


# --- issue #23: final security review of merged #19 (B1-B6, H1-H6) ----------


def test_b1_planted_cursor_cannot_suppress_genuine_claim(cli):
    # B1, final review: the cursor is gone entirely. A planted done_claim_ts
    # newer than every done in the file is ignored and migrated out; the
    # genuine claim pages.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    write_events(cli, "uuid-abc", [done_event(cli, ts=now - 300)])
    job["done_claim_ts"] = now - 60  # plant: inert
    events = []
    cli.triage_done_events(job, "uuid-abc", now, events)
    assert [e["signal"] for e in events] == ["done-claimed"]
    assert "done_claim_ts" not in job


def test_b1_same_claim_pages_every_pass_until_close(cli):
    # The flip side of removing the cursor: no per-pass dedup. The operator
    # closes the job to end the stream; watch skips closed jobs.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    write_events(cli, "uuid-abc", [done_event(cli, ts=now - 300)])
    for _ in range(3):
        events = []
        cli.triage_done_events(job, "uuid-abc", now, events)
        assert [e["signal"] for e in events] == ["done-claimed"]


def test_b2_planted_backoff_fields_do_not_suppress(cli):
    # B2, final review: the burst label comes from the event file; planted
    # job.json fields are inert and migrated out on first triage.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["done_page_count"] = 5
    job["done_page_window_start"] = now - 60
    job["done_repeated_paged"] = True
    job["done_repeated_for_ts"] = now
    sig = cli.handle_done_claim(job, done_event(cli, ts=now - 10), job["slug"],
                                now, recent_count=0)
    assert sig is not None and sig["signal"] == "done-unverified"
    for k in ("done_page_count", "done_page_window_start",
              "done_repeated_paged", "done_repeated_for_ts"):
        assert k not in job


def test_b3_displacing_forgery_does_not_suppress_genuine_claim(cli):
    # B3 (MEDIUM-HIGH): genuine done at T (triages done-claimed), then a
    # forged done at T+1 in the same window. The newest-only scan triaged
    # only the forgery and the genuine page never fired. Now every done is
    # triaged oldest-first: genuine first, forgery flagged unverified.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    genuine = done_event(cli, ts=now - 300, detail="genuine")
    forgery = done_event(ts=now - 200, detail="forged",
                         session_id="bogus", cwd="/nope")
    write_events(cli, "uuid-abc", [genuine, forgery])
    events = []
    cli.triage_done_events(job, "uuid-abc", now, events)
    sigs = [(e["signal"], e["detail"]) for e in events]
    assert len(sigs) == 2
    assert sigs[0][0] == "done-claimed" and "genuine" in sigs[0][1]
    assert sigs[1][0] == "done-unverified" and "forged" in sigs[1][1]


def test_b4_non_dict_event_lines_are_ignored(cli):
    # B4 (MEDIUM-HIGH): a forged `[1,2]` or `"x"` line used to reach
    # ev.get("state") and raise AttributeError, permanently blinding the
    # job's watch pass. Only dicts are yielded now.
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    p = os.path.join(cli.EVENTS_DIR, "uuid-abc.jsonl")
    with open(p, "w") as f:
        f.write("[1,2]\n\"x\"\n" + json.dumps(done_event(cli)) + "\n")
    evs = list(cli._iter_events("uuid-abc"))
    assert len(evs) == 1 and evs[0]["state"] == "done"
    assert cli.last_event("uuid-abc")["state"] == "done"


def test_b5_load_job_pins_slug_to_directory_name(cli):
    # B5 (HIGH): job.json is agent-writable; a planted "slug": "../victim"
    # used to make save_job overwrite the victim's record (and the SUMMARY.md
    # check read the victim's dir). load_job pins the slug to the directory
    # component of the path it opened.
    demo = cli.job_dir("demo")
    victim = cli.job_dir("victim")
    os.makedirs(demo, exist_ok=True)
    os.makedirs(victim, exist_ok=True)
    with open(os.path.join(victim, "job.json"), "w") as f:
        json.dump({"slug": "victim", "state": "active"}, f)
    with open(os.path.join(demo, "job.json"), "w") as f:
        json.dump({"slug": "../victim", "state": "active"}, f)
    job = cli.load_job("demo")
    assert job["slug"] == "demo"
    cli.save_job(job, "demo")
    with open(os.path.join(victim, "job.json")) as f:
        assert json.load(f)["slug"] == "victim", "victim record untouched"
    with open(os.path.join(demo, "job.json")) as f:
        assert json.load(f)["slug"] == "demo"


def test_b6_clean_text_strips_cr_and_bare_esc(cli):
    # B6 (MEDIUM): "\r" + padding in a forged detail overwrote the rendered
    # status line (fake verified-done); bare ESC (\x1bc reset, \x1b7/\x1b8,
    # \x1bM, \x1b(X) bypassed the sanitizer entirely.
    out = cli._clean_text("abc\rmal\x1bc\x1b7\x1b8\x1bM\x1b(Xdef\x1b[2K")
    assert "\r" not in out and "\x1b" not in out
    assert "abc" in out and "mal" in out and "def" in out


def test_clean_text_strips_c1_controls(cli, stop_hook):
    # Final security review: the C1 range \x80-\x9f (e.g. \x9b2K, the
    # 8-bit form of CSI) erased/spoofed terminal output just like C0.
    assert "\x9b" not in cli._clean_text("ok\x9b2Kmal")
    assert "\x85" not in cli._clean_text("ok\x85mal")
    # The hook source sanitizer strips the C1 byte itself (the inert
    # parameter letters remain as plain text, no escape can form).
    assert stop_hook._clean("ok\x9b2K") == "ok2K"


def test_b6_stop_hook_strips_cr_and_bare_esc(tmp_path):
    # Same at the hook source: the forged detail is cleaned before it lands
    # in the event file.
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home))
    run_hook("stop.py",
             {"session_id": "sid-cr",
              "last_assistant_message": "DONE: ok\rmal\x1bc",
              "cwd": "/t"},
             env)
    p = home / ".local" / "share" / "muse-job" / "events" / "sid-cr.jsonl"
    evt = json.loads(p.read_text().strip())
    assert "\r" not in evt["detail"] and "\x1b" not in evt["detail"]
    assert "ok" in evt["detail"]  # clean content survives
    # bare-ESC stripping at the source sanitizer, directly: the ESC byte is
    # removed (so no escape sequence can form); the inert parameter letters
    # remain as plain text, exactly as the issue's prescribed fix specifies.
    hook = load_script("stop_hook_clean_test",
                       os.path.join(os.path.dirname(__file__), "..", "plugin",
                                    "hooks", "stop.py"))
    assert hook._clean("ok\rmal\x1bc\x1b7\x1b8\x1bM\x1b(X\x1b[2K") == "okmalc78M(X"


def test_h1_sweep_filters_non_string_session_uuid(tmp_path, monkeypatch):
    # H1: a planted non-string session_uuid in a job record used to raise
    # TypeError inside active_session_uuids' set comprehension, killing the
    # whole sweep run -- a disk-guardian DoS.
    home = str(tmp_path)
    monkeypatch.setenv("HOME", home)
    jobs = os.path.join(home, "muse-jobs")
    os.makedirs(os.path.join(jobs, "evil"), exist_ok=True)
    with open(os.path.join(jobs, "evil", "job.json"), "w") as f:
        json.dump({"state": "active", "session_uuid": {"planted": True}}, f)
    sweep = load_script("muse_job_sweep_test",
                        os.path.join(os.path.dirname(__file__), "..", "bin",
                                     "muse-job-sweep"))
    uuids = sweep.active_session_uuids()  # must not raise
    assert uuids == set()


def test_h2_non_string_session_uuid_neutralized(cli):
    # H2: a planted dict/list session_uuid reached `uuid + ".jsonl"` and
    # raised TypeError, persistently blinding the job's pass. Garbage is now
    # treated as absent.
    job = make_job(cli)
    job["session_uuid"] = {"planted": True}
    st = cli.job_status(job, job["slug"])  # must not raise
    assert st["session_uuid"] is None
    job["session_uuid"] = ["a", "b"]
    st = cli.job_status(job, job["slug"])
    assert st["session_uuid"] is None


def test_malformed_session_uuid_is_loud_not_silent(cli):
    # Final review (arch): present-but-malformed must page events-tampered,
    # not silently blind liveness and done triage. Genuinely absent stays
    # silent (legitimate initial discovery).
    job = make_job(cli)
    job["session_uuid"] = {"planted": True}
    assert cli._session_uuid_ok(job) == (None, True)
    job["session_uuid"] = "../../evil"
    assert cli._session_uuid_ok(job) == (None, True)
    job["session_uuid"] = "x" * 200  # overlong
    assert cli._session_uuid_ok(job) == (None, True)
    job["session_uuid"] = None
    assert cli._session_uuid_ok(job) == (None, False)
    job["session_uuid"] = ""
    assert cli._session_uuid_ok(job) == (None, False)
    assert cli._session_uuid_ok(make_job(cli)) == ("uuid-abc", False)
    # A traversal-shaped uuid can never become a path.
    assert cli._event_path("../../evil") is None
    assert cli.head_info("../../evil") == (None, 0)
    # ...and verify_done_event fails closed on it.
    job["session_uuid"] = {"planted": True}
    ok, _ = cli.verify_done_event(job, done_event(cli), job["slug"])
    assert ok is False


def test_h3_cmd_status_survives_garbage_ts(cli, capsys):
    # H3: forged "ts": "x" (TypeError) and "ts": 1e30 (OverflowError in
    # time.localtime) used to kill `muse-job status` persistently. Renders
    # as ??:?? instead.
    import argparse as _ap
    jd = cli.job_dir("demo")
    os.makedirs(jd, exist_ok=True)
    with open(os.path.join(jd, "job.json"), "w") as f:
        json.dump({"slug": "demo", "session_uuid": "uuid-abc",
                   "worktree": "/jobs/demo/work", "state": "active",
                   "started_at": 1.0}, f)
    for bad in ("x", 1e30, float("nan"), None):
        write_events(cli, "uuid-abc",
                     [{"event": "stop", "state": "idle",
                       "session_id": "uuid-abc", "cwd": "/jobs/demo/work",
                       "ts": bad, "detail": "d"}])
        rc = cli.cmd_status(_ap.Namespace(slug="demo", json=False))
        assert rc == 0
    out = capsys.readouterr().out
    assert "??:??" in out


def test_h4_verify_done_rejects_non_string_cwd(cli):
    # H4: os.path.realpath(123) raised TypeError, contained per-job but
    # persistent. Fail closed instead.
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(job, done_event(cwd=123), job["slug"])
    assert ok is False and "cwd" in reason


def test_h5_stop_hook_does_not_block_on_fifo_event_file(tmp_path):
    # H5: a pre-created FIFO at events/<sid>.jsonl used to make the hook's
    # O_WRONLY open block forever ("never blocks the turn" violated). With
    # O_NONBLOCK the open fails fast (ENXIO, no reader) and the hook bails
    # cleanly -- this test completing at all is the regression check.
    home = tmp_path / "home"
    home.mkdir()
    evdir = home / ".local" / "share" / "muse-job" / "events"
    evdir.mkdir(parents=True)
    os.mkfifo(str(evdir / "sid-fifo.jsonl"))
    env = dict(os.environ, HOME=str(home))
    run_hook("stop.py",
             {"session_id": "sid-fifo",
              "last_assistant_message": "DONE: x", "cwd": "/t"},
             env)  # timeout=30 in run_hook; would hang pre-fix


def test_event_scan_truncated_signals_loudly(cli):
    # Final review (sec + arch): the 2 MB window is containment, not
    # correctness -- a file exceeding it must produce a loud per-pass
    # signal, never a silent blind spot.
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    p = os.path.join(cli.EVENTS_DIR, "uuid-abc.jsonl")
    with open(p, "wb") as f:
        f.truncate(cli._EVENT_SCAN_MAX_BYTES + 1)
    assert cli._event_scan_truncated("uuid-abc") is True
    with open(p, "wb") as f:
        f.truncate(cli._EVENT_SCAN_MAX_BYTES)
    assert cli._event_scan_truncated("uuid-abc") is False
    assert cli._event_scan_truncated("nope-no-such-uuid") is False


def test_iter_events_line_boundary_not_dropped(cli):
    # Eng review: when the scan window starts exactly on a line boundary,
    # the first genuine line must not be dropped as a "fragment".
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    p = os.path.join(cli.EVENTS_DIR, "uuid-abc.jsonl")
    line = json.dumps(done_event(cli, detail="x")) + "\n"
    per = len(line.encode())
    with open(p, "w") as f:
        f.write(line * 10)
    evs = list(cli._iter_events("uuid-abc", max_bytes=per * 4))
    assert len(evs) == 4, "window on a line boundary must keep every line"
    # A mid-line window start still drops only the fragment.
    evs2 = list(cli._iter_events("uuid-abc", max_bytes=per * 4 - 1))
    assert len(evs2) == 3


def test_stop_hook_refuses_fifo_with_reader(tmp_path):
    # Final review (eng): O_NONBLOCK only fails on a reader-less FIFO. With
    # a reader attached the open succeeds -- the fstat regular-file guard
    # must still refuse the write.
    import stat as _stat
    import time as _time
    home = tmp_path / "home"
    home.mkdir()
    evdir = home / ".local" / "share" / "muse-job" / "events"
    evdir.mkdir(parents=True)
    fifo = str(evdir / "sid-fr.jsonl")
    os.mkfifo(fifo)
    rfd = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
    try:
        env = dict(os.environ, HOME=str(home))
        run_hook("stop.py",
                 {"session_id": "sid-fr",
                  "last_assistant_message": "DONE: x", "cwd": "/t"},
                 env)
        _time.sleep(0.2)
        try:
            data = os.read(rfd, 65536)
        except OSError:
            data = b""
        assert data == b"", "hook must not write through a FIFO"
        assert _stat.S_ISFIFO(os.lstat(fifo).st_mode)
    finally:
        os.close(rfd)
        os.unlink(fifo)


def test_h6_event_scan_is_capped(cli):
    # H6: the scan reads only the tail of the file -- a GB-scale appended
    # file must not become a RAM/CPU DoS on the manager per pass.
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    p = os.path.join(cli.EVENTS_DIR, "uuid-abc.jsonl")
    junk = json.dumps({"event": "stop", "state": "idle", "ts": 1}) + "\n"
    total_lines = 2000
    with open(p, "w") as f:
        for _ in range(total_lines):
            f.write(junk)
        f.write(json.dumps(done_event(cli, ts=2.0)) + "\n")
    evs = list(cli._iter_events("uuid-abc", max_bytes=4096))
    assert 0 < len(evs) < total_lines, "scan must be tail-capped"
    # newest events are still found by the capped scan
    assert evs[-1]["state"] == "done"

# --- issue #23 review round 2: _session_anchor fail-closed + tmux grace anchor ---

def test_anchor_explicit_none_falls_back_to_started_at(cli):
    # eng/sec review: cmd_spawn writes "session_started_at": None on failed
    # discovery. Present-None must be treated as missing (fall back to
    # started_at), not slide the anchor to `now` on every pass -- the old
    # code kept the grace unsatisfiable forever for discovery-failed jobs.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_uuid"] = None
    job["session_started_at"] = None  # failed discovery, key present
    job["started_at"] = now - 2 * 3600
    sig = cli.check_events_liveness(job, live_status(), now)
    assert sig is not None and sig["signal"] == "events-tampered"
    assert "discovery failed" in sig["detail"] or "uuid wiped" in sig["detail"]
    # Within grace: still silent.
    job["started_at"] = now - 10 * 60
    assert cli.check_events_liveness(job, live_status(), now) is None


def test_anchor_poisoned_pages_immediately(cli):
    # arch review: wiping the uuid AND poisoning/deleting the anchors (one
    # agent write) must page on the very next pass -- never stay dark.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_uuid"] = ""
    job["session_started_at"] = "soon"  # poisoned; started_at never set
    sig = cli.check_events_liveness(job, live_status(), now)
    assert sig is not None and sig["signal"] == "events-tampered"
    assert "anchor" in sig["detail"]


def test_recorded_uuid_poisoned_anchor_pages(cli):
    # arch review: a recorded uuid with no trustworthy anchor is anomalous
    # (spawn/resume always set both together) -- page, don't stay dark.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_started_at"] = float("nan")
    job["started_at"] = True
    sig = cli.check_events_liveness(job, live_status(), now)
    assert sig is not None and sig["signal"] == "events-tampered"
    assert "anchor" in sig["detail"]


def test_anchor_bump_loop_still_pages_absent_uuid(cli):
    # sec review: an agent bumping session_started_at to ~now on every pass
    # must NOT keep the discovery grace open -- the tmux server-side
    # session creation time anchors the grace instead.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_uuid"] = None
    job["session_started_at"] = now  # the bump: would have silenced the old code
    job["started_at"] = now
    st = live_status(session_created=now - 2 * 3600)
    sig = cli.check_events_liveness(job, st, now)
    assert sig is not None and sig["signal"] == "events-tampered"
    # Within the tmux-anchored grace: still silent (no false positive).
    st = live_status(session_created=now - 10 * 60)
    assert cli.check_events_liveness(job, st, now) is None


def test_anchor_bump_loop_still_pages_events_missing(cli):
    # sec review: the same bump defeats the events-missing grace on the old
    # code; the tmux anchor closes it there too.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_started_at"] = now  # bumped
    job["started_at"] = now
    st = live_status(last_hook_event=None, session_created=now - 2 * 3600)
    sig = cli.check_events_liveness(job, st, now)
    assert sig is not None and sig["signal"] == "events-missing"


def test_tmux_anchor_unreachable_falls_back_to_job_json(cli):
    # When tmux is unreachable (session_created None), the sanitized
    # job.json anchor is the fallback -- a healthy job stays silent.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_started_at"] = now - 10 * 60
    job["started_at"] = now - 10 * 60
    sig = cli.check_events_liveness(
        job, live_status(last_hook_event={"ts": now - 60}), now)
    assert sig is None


def test_grace_anchor_prefers_tmux_over_job_json(cli):
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["session_started_at"] = now - 10 * 60
    assert cli._grace_anchor(job, live_status(), now) == job["session_started_at"]
    assert cli._grace_anchor(
        job, live_status(session_created=now - 5000), now) == now - 5000
    # Garbage session_created falls back to the job.json anchor.
    assert cli._grace_anchor(
        job, live_status(session_created="x"), now) == job["session_started_at"]
    # No trustworthy anchor anywhere -> None (callers page loudly).
    job["session_started_at"] = None
    job.pop("started_at", None)
    assert cli._grace_anchor(job, live_status(), now) is None


# --- issue #23 B6: status/list sinks sanitize agent-controlled fields ---

def _write_job_json(cli, job):
    import json as _json
    with open(os.path.join(cli.job_dir(job["slug"]), "job.json"), "w") as f:
        _json.dump(job, f)


def test_status_sinks_strip_terminal_escapes(cli, capsys):
    # sec review: cmd_status printed ev.event / ev.state / job_state /
    # session_status raw -- a forged event line could repaint the
    # operator's terminal (the exact B6 attack, via the event field).
    import argparse as _argparse
    job = make_job(cli)
    job["state"] = "active\r\x1b[2KFAKE-JOBSTATE"
    # The budget line only renders when PROGRESS.md exists; budget_hours is
    # agent-writable job.json and used to interpolate raw (sec round 2).
    job["budget_hours"] = "8\r\x1b[2KFAKE-BUDGET"
    jd = cli.job_dir(job["slug"])
    with open(os.path.join(jd, "PROGRESS.md"), "w") as f:
        f.write("# progress\n")
    _write_job_json(cli, job)
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    forged = {"event": "turn\r\x1b[2KFAKE-EVENT", "state": "done\rFAKE-STATE",
              "session_id": "uuid-abc", "cwd": "/jobs/demo/work",
              "detail": "x", "ts": 1.0}
    with open(os.path.join(cli.EVENTS_DIR, "uuid-abc.jsonl"), "w") as f:
        f.write(json.dumps(forged) + "\n")
    view = os.path.join(cli.VIEW_DIR, "uuid-abc")
    os.makedirs(view, exist_ok=True)
    with open(os.path.join(view, "HEAD.json"), "w") as f:
        f.write(json.dumps({"status": "ok\r\x1b[2KFAKE-STATUS"}))
    assert cli.cmd_status(_argparse.Namespace(slug="demo", json=False)) == 0
    out = capsys.readouterr().out
    assert "\r" not in out and "\x1b" not in out
    for marker in ("FAKE-EVENT", "FAKE-STATE", "FAKE-JOBSTATE", "FAKE-STATUS"):
        assert marker in out, f"sanitized text should still show ({marker})"
    # budget_hours is coerced to a number at the source: the hostile string
    # renders as the default 8, with no raw bytes and no FAKE-BUDGET text.
    assert "FAKE-BUDGET" not in out
    assert "/ budget 8h" in out


def test_list_sanitizes_job_state(cli, capsys):
    import argparse as _argparse
    job = make_job(cli)
    job["state"] = "active\r\x1b[2KFAKE"
    _write_job_json(cli, job)
    assert cli.cmd_list(_argparse.Namespace(json=False)) == 0
    out = capsys.readouterr().out
    assert "\r" not in out and "\x1b" not in out
    assert "FAKE" in out
