#!/usr/bin/env python3
"""muse-job Stop hook: classify each turn end and append a machine-readable
event to the session's event log. Purely observational: never blocks the turn,
always exits 0, emits no decision JSON."""
import json
import os
import re
import stat
import sys
import time

# Matches the sanitizer in bin/muse-job (_clean_text): ANSI/OSC escapes and
# C0 controls. `detail` lands in the event log and is printed verbatim by
# `muse-job status` and the watch pages -- a raw \x1b[2K could erase the
# security label on the very next line (issue #3 review). Issue #23 B6:
# also strip CR (\x0d) and bare ESC sequences (\x1bc reset, \x1b7/\x1b8,
# \x1bM, \x1b(X) -- "\r" + padding overwrites the rendered status line and
# displays a fake verified-done label. Bare-\x1b is ordered AFTER CSI/OSC.
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"          # CSI sequences
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC ... BEL | ST
    r"|\x1b"                               # bare ESC (reset, save/restore, RI, charset)
    r"|[\x00-\x08\x0b\x0c\r\x0e-\x1f\x7f\x80-\x9f]"  # C0 controls + CR + C1
)

# Session ids come from the hook payload. The same-user job agent knows its
# own sid and could pre-create events/<sid>.jsonl as a symlink into another
# job's job.json, so every hook append corrupts that job and the manager
# silently stops monitoring it (issue #3 review). Whitelist the id and never
# write through a symlink.
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

# Issue #8: quoted markers. Fenced code blocks are never the agent's own
# terminal marker (preamble quotes, example output, instructed shapes like
# "BLOCKED: <question>") — remove them before classification. The fence
# match is non-greedy so a single unclosed fence only eats to the next
# closing fence, and an unmatched ``` is left alone (classification then
# falls back to the last-line rule below).
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
# Markdown blockquote detection: any leading ">" prefix means the line is
# quoted text, never the agent's own marker — the marker check disqualifies
# such lines entirely (see classify()).
_QUOTE_RE = re.compile(r"^(?:>\s*)+")


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
        # Issue #23 H5: O_NONBLOCK. A pre-created FIFO at events/<sid>.jsonl
        # used to make O_WRONLY block indefinitely (ENXIO-free) -- the
        # "never blocks the turn" guarantee was violated. With O_NONBLOCK,
        # open() on a reader-less FIFO fails fast with ENXIO and we bail
        # cleanly. Regular files are unaffected (nonblock is a no-op there).
        fd = os.open(os.path.join(evdir, sid + ".jsonl"),
                     os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
                     | os.O_NONBLOCK,
                     0o644)
        # Final review (eng): fstat the opened descriptor and refuse
        # non-regular files. O_NONBLOCK only fails on a reader-less FIFO; a
        # FIFO WITH a reader would otherwise receive the event bytes. Refuse
        # to write anywhere but a real file. See session-end.py.
        try:
            opened_regular = stat.S_ISREG(os.fstat(fd).st_mode)
        except OSError:
            opened_regular = False
        if not opened_regular:
            os.close(fd)
            return
    except OSError:
        return  # ELOOP on a symlinked file, or any other fs problem
    try:
        os.write(fd, (json.dumps(evt) + "\n").encode())
    except OSError:
        pass
    finally:
        os.close(fd)


def classify(message):
    """Return (state, detail) from the assistant's final message.

    Issue #8: the marker is the protocol's FINAL line ("end turn with
    `BLOCKED: <question>` / `DONE: <summary>` — TOOL_INTERFACE.md), so only
    the last non-empty line may carry it. Quoted or example markers earlier
    in the message (preamble literals, fenced code blocks) no longer flip
    the job's state. A genuine marker wrapped in a fenced code block is
    also ignored — the protocol wants the bare marker as the final line,
    so fence only examples, not the marker. Residual, stated plainly: an
    agent that buries a genuine BLOCKED: mid-message and ends on prose is
    classified idle — deliberate, since the fix for a missing marker is the
    same as before (the preamble's explicit instruction), while a phantom
    done closes a live job.
    """
    state, detail = "idle", ""
    if not message:
        return state, detail
    body = _FENCE_RE.sub("", message)
    # Split on \n only: \r is a content byte (the sanitizer strips it from
    # the detail), not a protocol line break. splitlines() would let a \r
    # injection re-cut the message and detach a genuine final-line marker
    # from the classifier (issue #23 B6 pinning test).
    lines = [l.strip() for l in body.split("\n") if l.strip()]
    if not lines:
        return state, detail
    # Issue #8: a line the agent merely quoted (markdown blockquote) is
    # never its own marker. Any leading ">" prefix disqualifies the line
    # from marker matching — including nested quotes like ">> DONE:",
    # which unquoting to the bare marker would otherwise misclassify.
    # (Quoted lines still feed the question tail below; that predates
    # this fix and question state never closes a job.)
    last_raw = lines[-1]
    if _QUOTE_RE.sub("", last_raw) != last_raw:
        last = None
    else:
        last = last_raw
    if last is not None and last.startswith("BLOCKED:"):
        return "blocked", _clean(last[len("BLOCKED:"):].strip())[:500]
    if last is not None and last.startswith("DONE:"):
        return "done", _clean(last[len("DONE:"):].strip())[:500]
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
    sid = d.get("session_id")
    if not sid:
        return  # no session id: nothing records it and no manager path ever
                # reads it back, so appending to events/unknown.jsonl would be
                # write-only garbage (session-start.py already skips these).
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
