#!/usr/bin/env python3
"""muse-job session-start hook (fires on PreLLMCall): record first-seen
session metadata so the manager can discover session UUIDs without the
laggy session index. Writes once per session; observational only."""
import json
import os
import re
import sys
import time


# Whitelist the session id (used in the registry filename): the same-user
# job agent could otherwise plant a registration symlink that redirects the
# manager's session discovery (issue #3 review). See stop.py.
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def main():
    try:
        raw = sys.stdin.read()
        d = json.loads(raw) if raw.strip() else {}
    except Exception:
        d = {}
    sid = d.get("session_id")
    if not sid or not _SID_RE.match(sid):
        return
    # SECURITY (issue #3): hardcoded like the events dir -- a job agent can
    # export env vars mid-session, so nothing from os.environ is trusted here.
    regdir = os.path.expanduser("~/.local/share/muse-job/sessions")
    try:
        if os.path.islink(regdir):
            return
        os.makedirs(regdir, exist_ok=True)
        if os.path.islink(regdir):
            return
        path = os.path.join(regdir, sid + ".json")
        if os.path.exists(path) or os.path.islink(path):
            return
        # Store only what the manager reads: session id, cwd, model, and tool
        # names (for main-session detection). The full PreLLMCall payload
        # can contain message text previews and must not be persisted.
        tools = d.get("tools") or []
        rec = {
            "session_id": sid,
            "cwd": d.get("cwd"),
            "model": d.get("model"),
            "first_seen": time.time(),
            "tools": [{"name": t.get("name")} for t in tools
                      if isinstance(t, dict)],
        }
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(rec, f)
        os.replace(tmp, path)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
