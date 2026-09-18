"""Regression tests for issue #3: job agent can forge its own turn-state events.

Covers the fix in two rounds:
  1. Hooks (stop.py, session-end.py, session-start.py) ignore
     MUSE_JOB_EVENTS / MUSE_JOB_SESSIONS env overrides -- a job agent with a
     full shell could otherwise export them mid-session and blind the watchdog.
     The review round added: session-id whitelisting, no writes through
     symlinks, ANSI/control-character sanitization of agent-influenced text.
  2. `muse-job watch`/`status` treat hook `done` events as cooperative
     telemetry: `verify_done_event` cross-checks a done event against the
     job's recorded session uuid, worktree cwd, and a non-empty SUMMARY.md
     regular file before the operator acts on it. Fail closed. The review
     round added: whole-file done-claim scanning (burial resistance),
     read-side sanitization of the agent-writable dedup cursor, re-page
     backoff (done-repeated coalescing), recency-based events-missing
     anchored to session_started_at with per-session dedup, and an
     events-tampered signal for symlinked event files.
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


def done_event(**kw):
    ev = {"event": "stop", "state": "done", "session_id": "uuid-abc",
          "cwd": "/jobs/demo/work", "detail": "finished", "ts": 1.0}
    ev.update(kw)
    return ev


def test_verify_done_happy_path(cli):
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("# Summary\nDone.\n")
    assert cli.verify_done_event(job, done_event()) == (True, "")


def test_verify_done_rejects_missing_summary(cli):
    # The forge scenario from issue #3: agent appends a fake done line to its
    # own event file but never wrote SUMMARY.md. Must fail closed.
    job = make_job(cli)
    ok, reason = cli.verify_done_event(job, done_event())
    assert ok is False
    assert "SUMMARY.md" in reason


def test_verify_done_rejects_empty_summary(cli):
    job = make_job(cli)
    open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w").close()
    ok, reason = cli.verify_done_event(job, done_event())
    assert ok is False
    assert "empty" in reason


def test_verify_done_rejects_wrong_session(cli):
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(
        job, done_event(session_id="some-other-session"))
    assert ok is False
    assert "session" in reason


def test_verify_done_rejects_cwd_mismatch(cli):
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(job, done_event(cwd="/tmp/evil"))
    assert ok is False
    assert "cwd" in reason


def test_verify_done_accepts_cwd_under_worktree(cli, tmp_path):
    # The agent may legitimately cd into a subdir before ending the turn;
    # raw string equality would false-positive here (review finding).
    job = make_job(cli)
    work = tmp_path / "jobs" / "demo" / "work"
    work.mkdir(parents=True)
    job["worktree"] = str(work)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    sub = str(work / "subdir")
    assert cli.verify_done_event(job, done_event(cwd=sub)) == (True, "")
    # ...but a sibling-prefix path must not pass via startswith tricks.
    evil = str(work) + "-evil"
    ok, _ = cli.verify_done_event(job, done_event(cwd=evil))
    assert ok is False


def test_verify_done_rejects_missing_cwd(cli):
    job = make_job(cli)
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ev = done_event()
    del ev["cwd"]
    ok, reason = cli.verify_done_event(job, ev)
    assert ok is False
    assert "cwd" in reason


def test_verify_done_rejects_job_without_session_uuid(cli):
    job = make_job(cli)
    job["session_uuid"] = None
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(job, done_event())
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
    sig = cli.handle_done_claim(job, done_event())
    assert sig is not None
    assert sig["signal"] == "done-claimed"
    # The whole point: no state transition on telemetry, however convincing.
    assert job["state"] == "active"
    assert "state" not in sig


def test_lazy_forgery_pages_done_unverified(cli):
    # The lazy attack: fake done line, no SUMMARY.md.
    job = make_job(cli)
    sig = cli.handle_done_claim(job, done_event())
    assert sig is not None
    assert sig["signal"] == "done-unverified"
    assert job["state"] == "active"


def test_done_claim_dedupes_on_event_ts(cli):
    # One claim pages once; without dedup every 15-minute watch pass would
    # re-page the same stale done line forever (engineering review).
    job = make_job(cli)
    ev = done_event(ts=100.0)
    first = cli.handle_done_claim(job, ev)
    assert first is not None and first["signal"] == "done-unverified"
    job["done_claim_ts"] = 100.0  # what watch_one records after emitting
    assert cli.handle_done_claim(job, ev) is None
    # A NEWER done event (agent genuinely finished later) pages again.
    assert cli.handle_done_claim(job, done_event(ts=200.0)) is not None


def test_done_claim_future_ts_cannot_suppress_later_claim(cli):
    # Round-2 security review: a forged done with a far-future ts must not
    # poison dedup and permanently blind the operator to genuine completions.
    import time as _time
    job = make_job(cli)
    now = _time.time()
    forged = done_event(ts=now + 10 * 365 * 24 * 3600)  # +10 years
    assert cli.handle_done_claim(job, forged, now) is not None
    job["done_claim_ts"] = cli._claim_ts(forged, now)
    assert job["done_claim_ts"] <= now  # clamped, not 10y out
    genuine = done_event(ts=now + 60)
    assert cli.handle_done_claim(job, genuine, now + 60) is not None


def test_done_claim_nan_ts_dedupes(cli):
    # NaN never compares <= , so without normalization it would page forever.
    import time as _time
    job = make_job(cli)
    now = _time.time()
    ev = done_event(ts=float("nan"))
    assert cli.handle_done_claim(job, ev, now) is not None
    job["done_claim_ts"] = cli._claim_ts(ev, now)
    assert cli.handle_done_claim(job, ev, now) is None


def test_done_claim_missing_ts_dedupes(cli):
    job = make_job(cli)
    ev = done_event()
    del ev["ts"]
    assert cli.handle_done_claim(job, ev) is not None
    job["done_claim_ts"] = 0  # watch_one records 0 for ts-less events
    assert cli.handle_done_claim(job, ev) is None


# --- check_events_liveness ---------------------------------------------------

def live_status(tmux_alive=True, last_hook_event=None, started_ago_s=3600):
    return {
        "tmux_alive": tmux_alive,
        "last_hook_event": last_hook_event,
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


def test_events_missing_silent_without_session_uuid(cli):
    job = make_job(cli)
    job["session_uuid"] = None
    job["started_at"] = 1_000_000.0
    now = job["started_at"] + 5 * 3600
    assert cli.check_events_liveness(job, live_status(), now) is None

# --- find_session ------------------------------------------------------------

def test_find_session_excludes_old_uuid(cli, tmp_path):
    # Issue #3 round-2 review: the resume fallback must not re-adopt the dead
    # session's registration. Within the 10s since_ts slack the old record
    # still qualifies and sorts first -- only an explicit exclude is robust.
    import time as _time
    sessdir = os.path.join(str(tmp_path), ".local", "share", "muse-job", "sessions")
    os.makedirs(sessdir, exist_ok=True)
    now = _time.time()
    for sid, seen in (("old-uuid", now - 5), ("new-uuid", now - 1)):
        with open(os.path.join(sessdir, sid + ".json"), "w") as f:
            json.dump({"session_id": sid, "cwd": "/w", "first_seen": seen,
                       "tools": [{"name": "bash"}]}, f)
    assert cli.find_session("/w", now) == "old-uuid"  # the trap, documented
    assert cli.find_session("/w", now, exclude="old-uuid") == "new-uuid"


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

def test_last_event_refuses_symlink(cli, tmp_path):
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    target = tmp_path / "t.jsonl"
    target.write_text(json.dumps(done_event()) + "\n")
    os.symlink(str(target), os.path.join(cli.EVENTS_DIR, "uuid-abc.jsonl"))
    assert cli.last_event("uuid-abc") is None
    assert cli.event_file_symlinked("uuid-abc") is True


def test_handle_done_claim_sanitizes_forged_detail(cli):
    # Forged event lines bypass the hook sanitizer; the manager must clean
    # agent-influenced text before embedding it in signals.
    job = make_job(cli)
    ev = done_event(detail="done\x1b[2K\x1b[1AFAKE verified")
    sig = cli.handle_done_claim(job, ev)
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
        done_event(ts=now - 300),
        {"event": "stop", "state": "idle", "session_id": "uuid-abc",
         "cwd": "/jobs/demo/work", "ts": now},
    ])
    # The tail-line reader sees only the forged idle line...
    assert cli.last_event("uuid-abc")["state"] == "idle"
    # ...but the claim scan still finds the done line.
    done_ev, _ts = cli.latest_done_event("uuid-abc", now)
    assert done_ev is not None and done_ev["state"] == "done"
    sig = cli.handle_done_claim(job, done_ev, now)
    assert sig is not None and sig["signal"] == "done-claimed"


def test_latest_done_event_picks_newest(cli):
    import time as _time
    now = _time.time()
    write_events(cli, "uuid-abc", [
        done_event(ts=now - 300, detail="first"),
        done_event(ts=now - 100, detail="second"),
    ])
    done_ev, ts = cli.latest_done_event("uuid-abc", now)
    assert done_ev["detail"] == "second"
    assert ts == now - 100


# --- review round: agent-writable dedup cursor -------------------------------

def test_stored_done_claim_ts_future_forgery_ignored(cli):
    # Security review B2 / arch B3: the agent plants a far-future
    # done_claim_ts in job.json to suppress all future done pages.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["done_claim_ts"] = now + 10 * 365 * 24 * 3600
    sig = cli.handle_done_claim(job, done_event(ts=now - 10), now)
    assert sig is not None, "forged future cursor must not suppress paging"


def test_stored_done_claim_ts_garbage_ignored(cli):
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["done_claim_ts"] = "soon"
    assert cli.handle_done_claim(job, done_event(ts=now - 10), now) is not None


def test_done_claims_coalesce_after_three_pages(cli):
    # Security review B7: unbounded re-paging trains the operator to ignore
    # the signal; after 3 pages in 24h, coalesce into one done-repeated.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    sigs = []
    for i in range(5):
        sig = cli.handle_done_claim(job, done_event(ts=now - 300 + i), now)
        sigs.append(sig["signal"] if sig else None)
    assert sigs[:3] == ["done-unverified"] * 3
    assert sigs[3] == "done-repeated"
    assert sigs[4] is None


def test_done_claim_window_resets_after_24h(cli):
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["done_page_window_start"] = now - 25 * 3600
    job["done_page_count"] = 3
    sig = cli.handle_done_claim(job, done_event(ts=now - 10), now)
    assert sig is not None and sig["signal"] == "done-unverified"
    assert job["done_page_count"] == 1


# --- review round: verify_done_event fail-closed -----------------------------

def test_verify_done_rejects_missing_worktree(cli):
    # Engineering B1: realpath("") is the CLI's own cwd -- the check must
    # fail closed, not compare against an attacker-influenced path.
    job = make_job(cli)
    job["worktree"] = ""
    with open(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), "w") as f:
        f.write("summary")
    ok, reason = cli.verify_done_event(job, done_event())
    assert ok is False
    assert "worktree" in reason


def test_verify_done_rejects_summary_directory(cli):
    # Engineering B2: getsize() succeeds on directories; `mkdir SUMMARY.md`
    # must not satisfy the "non-empty SUMMARY.md" check.
    job = make_job(cli)
    os.makedirs(os.path.join(cli.job_dir("demo"), "SUMMARY.md"), exist_ok=True)
    ok, reason = cli.verify_done_event(job, done_event())
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
    st = cli.job_status(job)  # must not raise
    assert isinstance(st["elapsed_h"], float)
    assert st["bytes_delta"] >= 0
    # budget comparison path used by cmd_watch must not raise either.
    assert (st["elapsed_h"] > (cli._num(job.get("budget_hours"), 8) or 8)) in (True, False)


def test_done_repeated_flag_plant_does_not_suppress_notice(cli):
    # Arch review: a pre-planted done_repeated_paged=True with count<3 is
    # stale or forged and must not suppress the coalescing notice.
    import time as _time
    now = _time.time()
    job = make_job(cli)
    job["done_repeated_paged"] = True
    job["done_page_window_start"] = now - 60
    job["done_page_count"] = 0
    sigs = []
    for i in range(4):
        sig = cli.handle_done_claim(job, done_event(ts=now - 300 + i), now)
        sigs.append(sig["signal"] if sig else None)
    assert sigs[:3] == ["done-unverified"] * 3
    assert sigs[3] == "done-repeated"
