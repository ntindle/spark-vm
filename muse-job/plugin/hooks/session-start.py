#!/usr/bin/env python3
"""muse-job session-start hook (fires on PreLLMCall): record first-seen
session metadata so the manager can discover session UUIDs without the
laggy session index. Writes once per session; observational only."""
import json
import os
import sys
import time


def main():
    try:
        raw = sys.stdin.read()
        d = json.loads(raw) if raw.strip() else {}
    except Exception:
        d = {}
    sid = d.get("session_id")
    if not sid:
        return
    regdir = os.environ.get(
        "MUSE_JOB_SESSIONS",
        os.path.expanduser("~/.local/share/muse-job/sessions"),
    )
    try:
        os.makedirs(regdir, exist_ok=True)
        path = os.path.join(regdir, sid + ".json")
        if os.path.exists(path):
            return
        rec = {
            "session_id": sid,
            "cwd": d.get("cwd"),
            "model": d.get("model"),
            "first_seen": time.time(),
            "payload": d,
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
