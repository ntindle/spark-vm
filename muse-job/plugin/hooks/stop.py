#!/usr/bin/env python3
"""muse-job Stop hook: classify each turn end and append a machine-readable
event to the session's event log. Purely observational: never blocks the turn,
always exits 0, emits no decision JSON."""
import json
import os
import re
import sys
import time

# Matches the sanitizer in bin/muse-job (_clean_text): ANSI/OSC escapes and
# C0 controls. `detail` lands in the event log and is printed verbatim by
# `muse-job status` and the watch pages -- a raw \x1b[2K could erase the
# security label on the very next line (issue #3 review).
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"          # CSI sequences
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC ... BEL | ST
    r"|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"   # C0 controls
)

# Session ids come from the hook payload. The same-user job agent knows its
# own sid and could pre-create events/<sid>.jsonl as a symlink into another
# job's job.json, so every hook append corrupts that job and the manager
# silently stops monitoring it (issue #3 review). Whitelist the id and never
# write through a symlink.
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _clean(s):
    return _ANSI_RE.sub("", s or "")


def _append_event(evdir, sid, evt):
    """Append one event line, refusing untrusted paths. Never raises."""
    if not _SID_RE.match(sid or ""):
        return
    try:
        # The dir itself must not be a symlink: the agent could replace the
        # events dir with a link into a void, blinding the watchdog. Bail
        # (write nothing) rather than write somewhere untrusted.
        if os.path.islink(evdir):
            return
        os.makedirs(evdir, exist_ok=True)
        if os.path.islink(evdir):  # re-check after makedirs (best effort)
            return
        fd = os.open(os.path.join(evdir, sid + ".jsonl"),
                     os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                     0o644)
    except OSError:
        return  # ELOOP on a symlinked file, or any other fs problem
    try:
        os.write(fd, (json.dumps(evt) + "\n").encode())
    except OSError:
        pass
    finally:
        os.close(fd)


def classify(message):
    """Return (state, detail) from the assistant's final message."""
    state, detail = "idle", ""
    if not message:
        return state, detail
    lines = [l.strip() for l in message.splitlines() if l.strip()]
    for line in lines:
        if line.startswith("BLOCKED:"):
            return "blocked", _clean(line[len("BLOCKED:"):].strip())[:500]
        if line.startswith("DONE:"):
            return "done", _clean(line[len("DONE:"):].strip())[:500]
    tail = lines[-3:]
    # Return the actual question line, not just the last tail line.
    for t in reversed(tail):
        if t.endswith("?"):
            return "question", _clean(t)[:500]
    return state, detail


def main():
    try:
        raw = sys.stdin.read()
        d = json.loads(raw) if raw.strip() else {}
    except Exception:
        d = {}
    sid = d.get("session_id") or "unknown"
    state, detail = classify(d.get("last_assistant_message") or "")
    # SECURITY (issue #3): the event sink path is hardcoded, NEVER taken from
    # the environment. Hooks run as children of the job's `muse` process, so a
    # job agent with a full shell could `export MUSE_JOB_EVENTS=/tmp/void`
    # mid-session and blind the watchdog. No legitimate caller overrides this
    # (the vars were never documented); keep it unconditional. _append_event
    # additionally whitelists the session id and refuses symlinked targets.
    evdir = os.path.expanduser("~/.local/share/muse-job/events")
    try:
        evt = {
            "ts": time.time(),
            "event": "stop",
            "session_id": sid,
            "state": state,
            "detail": detail,
            "cwd": d.get("cwd"),
            "turn_id": d.get("turn_id"),
        }
        _append_event(evdir, sid, evt)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
