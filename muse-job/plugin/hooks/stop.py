#!/usr/bin/env python3
"""muse-job Stop hook: classify each turn end and append a machine-readable
event to the session's event log. Purely observational: never blocks the turn,
always exits 0, emits no decision JSON."""
import json
import os
import sys
import time


def classify(message):
    """Return (state, detail) from the assistant's final message."""
    state, detail = "idle", ""
    if not message:
        return state, detail
    lines = [l.strip() for l in message.splitlines() if l.strip()]
    for line in lines:
        if line.startswith("BLOCKED:"):
            return "blocked", line[len("BLOCKED:"):].strip()[:500]
        if line.startswith("DONE:"):
            return "done", line[len("DONE:"):].strip()[:500]
    tail = lines[-3:]
    # Return the actual question line, not just the last tail line.
    for t in reversed(tail):
        if t.endswith("?"):
            return "question", t[:500]
    return state, detail


def main():
    try:
        raw = sys.stdin.read()
        d = json.loads(raw) if raw.strip() else {}
    except Exception:
        d = {}
    sid = d.get("session_id") or "unknown"
    state, detail = classify(d.get("last_assistant_message") or "")
    evdir = os.environ.get(
        "MUSE_JOB_EVENTS",
        os.path.expanduser("~/.local/share/muse-job/events"),
    )
    try:
        os.makedirs(evdir, exist_ok=True)
        evt = {
            "ts": time.time(),
            "event": "stop",
            "session_id": sid,
            "state": state,
            "detail": detail,
            "cwd": d.get("cwd"),
            "turn_id": d.get("turn_id"),
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
