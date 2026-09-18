#!/usr/bin/env python3
"""muse_job.py — Muse Code as a tool with the same shape as subagents.

    from muse_job import spawn, steer, interrupt, status, list_jobs, log, \
                          wait_for_turn, pending_question, kill, resume, close

Maps the subagent/browser interaction pattern (async dispatch, steer
channel, question channel, introspection, lifecycle) onto today's reality:
tmux TUI sessions + the muse-job plugin's hook events on spark-vm.

All box I/O goes through ~/workspace/bin/box.sh (SSH as ntindle).
"""
import json
import os
import re
import shlex
import subprocess
import time

BOX = os.path.expanduser("~/workspace/bin/box.sh")
REMOTE_JOB = "/home/ntindle/bin/muse-job"
REMOTE_TMUX = "tmux"


class MuseJobError(RuntimeError):
    pass


def slug_ok(slug):
    """Same charset rule as the CLI (bin/muse-job). Anything else never
    reaches the box command line."""
    return isinstance(slug, str) and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", slug) is not None


def check_slug(slug):
    if not slug_ok(slug):
        raise MuseJobError(f"bad slug: {slug!r}")
    return slug


def check_uuid(uuid):
    if not isinstance(uuid, str) or re.fullmatch(r"[a-f0-9-]+", uuid) is None:
        raise MuseJobError(f"bad session uuid: {uuid!r}")
    return uuid


def _box(cmd, timeout=120):
    """Run a shell command on spark-vm; return stdout text."""
    p = subprocess.run([BOX, cmd], capture_output=True, text=True,
                       timeout=timeout)
    if p.returncode != 0:
        raise MuseJobError(f"box command failed ({p.returncode}): "
                           f"{cmd[:120]}\n{p.stderr.strip()[:500]}")
    return p.stdout


def _job(*args, timeout=180):
    """Run muse-job on the box; parse its JSON stdout.

    Every arg is shlex-quoted: the command runs through ssh's remote shell,
    so an unquoted arg with spaces or metacharacters would break or inject.
    """
    out = _box(f"{REMOTE_JOB} " + " ".join(shlex.quote(str(a)) for a in args),
               timeout=timeout)
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise MuseJobError(f"muse-job printed non-JSON: {out[:300]}")


# --- dispatch / steer --------------------------------------------------------

def spawn(slug, repo, prompt_file, budget_hours=8, branch=None, base=None):
    """Start a job. Returns {"slug","session_uuid","worktree"}.

    Note: prompt_file must be a path ON THE BOX (the CLI reads it there).
    """
    check_slug(slug)
    args = ["spawn", slug, "--repo", repo, "--prompt-file", prompt_file,
            "--budget-hours", str(budget_hours)]
    if branch:
        args += ["--branch", branch]
    if base:
        args += ["--base", base]
    return _job(*args, timeout=300)


def steer(slug, message):
    """Send a message into the job (queues if mid-turn). Returns delivered."""
    check_slug(slug)
    return _job("steer", slug, message, timeout=120)


def interrupt(slug):
    """Ctrl-C the agent's terminal (like subagent.send interrupt=True)."""
    check_slug(slug)
    _box(f"{REMOTE_TMUX} send-keys -t {shlex.quote('mjob-' + slug)} C-c")
    return {"slug": slug, "interrupted": True}


# --- introspection -------------------------------------------------------------

def status(slug):
    """Full status dict for one job (like subagent.list, scoped)."""
    check_slug(slug)
    return _job("status", slug, "--json")


def list_jobs():
    """Every job: [{"slug","state","tmux_alive","session_uuid","elapsed_h"}]."""
    return _job("list", "--json")


def _events_path(session_uuid):
    return f"~/.local/share/muse-job/events/{session_uuid}.jsonl"


def log(slug, n=50):
    """Last n turn-end hook events for the job's session."""
    check_slug(slug)
    st = status(slug)
    uuid = st.get("session_uuid")
    if not uuid:
        return []
    check_uuid(uuid)
    n = max(1, int(n))
    out = _box(f"tail -n {n} {shlex.quote(_events_path(uuid))} 2>/dev/null || true")
    events = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


# --- the push-emulation and question channel -----------------------------------

def wait_for_turn(slug, since_ts=None, timeout=3600, poll=15):
    """Block until the next turn-end hook event after since_ts.

    Emulates the runtime's pushed handoff in a synchronous context.
    Returns the event dict. Raises TimeoutError on timeout.
    """
    check_slug(slug)
    st = status(slug)
    uuid = st.get("session_uuid")
    if not uuid:
        raise MuseJobError(f"job {slug} has no session uuid yet")
    check_uuid(uuid)
    if since_ts is None:
        evs = log(slug, n=1)
        since_ts = evs[-1]["ts"] if evs else 0
    deadline = time.time() + timeout
    wait = poll
    while time.time() < deadline:
        evs = log(slug, n=5)
        for e in evs:
            if e.get("ts", 0) > since_ts:
                return e
        time.sleep(wait)
        wait = min(wait * 1.5, 60)
    raise TimeoutError(f"no turn-end event for {slug} within {timeout}s")


def pending_question(slug):
    """The ask_for_information equivalent.

    Returns None, or {"kind": "blocked"|"question", "detail": str}.
    Answer via steer(slug, ...) like browser.steer_task answers.
    """
    check_slug(slug)
    evs = log(slug, n=1)
    if not evs:
        return None
    e = evs[-1]
    if e.get("event") == "stop" and e.get("state") in ("blocked", "question"):
        return {"kind": e["state"], "detail": e.get("detail", ""),
                "turn_id": e.get("turn_id"), "ts": e.get("ts")}
    return None


# --- lifecycle -----------------------------------------------------------------

def kill(slug):
    """Stop the agent's process tree (like subagent.close)."""
    check_slug(slug)
    return _job("kill", slug)


def resume(slug):
    """Resume the recorded session in place (like subagent.resume)."""
    check_slug(slug)
    return _job("resume", slug, timeout=180)


def close(slug):
    """Kill, remove worktree, delete branch, archive (terminal)."""
    check_slug(slug)
    return _job("close", slug, timeout=120)


if __name__ == "__main__":
    import sys
    print(json.dumps(list_jobs(), indent=2))
    sys.exit(0)
