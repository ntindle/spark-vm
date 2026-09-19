#!/usr/bin/env python3
"""muse-job SessionEnd hook: record session termination. Observational only."""
import json
import os
import re
import sys
import time

# Same rationale as stop.py (issue #3 review): ANSI/OSC escapes and C0
# controls in `reason` would be stored and echoed into operator-visible
# output, so strip them at the source.
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)

# Whitelist the session id (used in the event filename) and never write
# through a symlink -- see stop.py for the cross-job tampering scenario.
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _clean(s):
    return _ANSI_RE.sub("", s or "")


def _append_event(evdir, sid, evt):
    """Append one event line, refusing untrusted paths. Never raises."""
    if not _SID_RE.match(sid or ""):
        return
    try:
        if os.path.islink(evdir):
            return
        os.makedirs(evdir, exist_ok=True)
        if os.path.islink(evdir):
            return
        fd = os.open(os.path.join(evdir, sid + ".jsonl"),
                     os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                     0o644)
    except OSError:
        return
    try:
        os.write(fd, (json.dumps(evt) + "\n").encode())
    except OSError:
        pass
    finally:
        os.close(fd)


def main():
    try:
        raw = sys.stdin.read()
        d = json.loads(raw) if raw.strip() else {}
    except Exception:
        d = {}
    sid = d.get("session_id")
    if not sid:
        return  # see stop.py: events for an unknown session id are
                # write-only garbage; skip them.
    # SECURITY (issue #3): hardcoded, never from the environment. See stop.py.
    evdir = os.path.expanduser("~/.local/share/muse-job/events")
    try:
        evt = {
            "ts": time.time(),
            "event": "session-end",
            "session_id": sid,
            "reason": _clean(d.get("reason")),
            "cwd": d.get("cwd"),
        }
        _append_event(evdir, sid, evt)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
