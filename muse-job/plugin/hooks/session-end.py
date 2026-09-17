#!/usr/bin/env python3
"""muse-job SessionEnd hook: record session termination. Observational only."""
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
    sid = d.get("session_id") or "unknown"
    evdir = os.environ.get(
        "MUSE_JOB_EVENTS",
        os.path.expanduser("~/.local/share/muse-job/events"),
    )
    try:
        os.makedirs(evdir, exist_ok=True)
        evt = {
            "ts": time.time(),
            "event": "session-end",
            "session_id": sid,
            "reason": d.get("reason"),
            "cwd": d.get("cwd"),
        }
        with open(os.path.join(evdir, sid + ".jsonl"), "a") as f:
            f.write(json.dumps(evt) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
