"""Issue #8: the stop hook's classifier matched BLOCKED:/DONE: on ANY
non-empty line of the assistant's final message. Quoted or example markers
(the prompt preamble's literals, fenced code blocks, blockquoted quotes)
flipped the job's state: a quoted DONE: closed a live job, a quoted
BLOCKED: paged the operator on a phantom.

The fix: only the protocol's FINAL line carries the marker ("end turn
with `BLOCKED: <question>` / `DONE: <summary>` — TOOL_INTERFACE.md),
fenced code blocks are stripped before classification, and blockquote
prefixes never count. The six false-positive tests fail against the old
any-line classifier (verified by running this file against the pre-fix
hook on a scratch copy — 6 failed, the 4 regression tests below pass on
both, pinning the preserved behavior).
"""
import importlib.machinery
import importlib.util
import os
import sys

import pytest


def load_stop_hook():
    path = os.path.join(os.path.dirname(__file__), "..", "plugin", "hooks",
                        "stop.py")
    name = "stop_hook_8"
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


@pytest.fixture()
def hook():
    return load_stop_hook()


def test_fenced_preamble_quote_not_classified(hook):
    # The preamble itself contains the marker literals inside a fence.
    msg = ("When stuck, quote the protocol:\n"
           "```\n"
           "BLOCKED: <question>\n"
           "```\n"
           "I am now running the build.")
    assert hook.classify(msg)[0] == "idle"


def test_mid_message_blocked_not_classified(hook):
    # A genuine-looking marker buried mid-message no longer flips state.
    msg = ("BLOCKED: waiting on user review\n"
           "Update: the review landed, resuming work.\n"
           "All tests pass now.")
    assert hook.classify(msg)[0] == "idle"


def test_final_marker_still_classified(hook):
    state, detail = hook.classify("Finished the build.\nDONE: shipped v2")
    assert state == "done"
    assert detail == "shipped v2"


def test_final_blocked_still_classified(hook):
    state, detail = hook.classify("Tried twice.\nBLOCKED: need approval")
    assert state == "blocked"
    assert detail == "need approval"


def test_final_marker_with_trailing_blanks(hook):
    assert hook.classify("Done.\nDONE: x\n\n  \n")[0] == "done"


def test_blockquoted_final_line_not_classified(hook):
    # "> DONE: x" is a quotation of the protocol, not the agent's marker —
    # including nested quotes, which must not unquote down to the marker.
    assert hook.classify("Quoting the docs:\n> DONE: <summary>")[0] == "idle"
    assert hook.classify(">> BLOCKED: <question>")[0] == "idle"
    # But a quoted marker plus the agent's own final marker still binds.
    assert hook.classify("> DONE: quoted\nDONE: real")[0] == "done"


def test_fenced_marker_at_end_not_classified(hook):
    # An example block is the whole final content.
    msg = "Example of the protocol:\n```\nDONE: example\n```"
    assert hook.classify(msg)[0] == "idle"


def test_unclosed_fence_falls_back_to_last_line(hook):
    # No closing fence: the non-greedy match leaves the text alone and the
    # last-line rule decides (documented, not silently classifying).
    msg = "```\nDONE: example\nmore text\nfinal prose"
    assert hook.classify(msg)[0] == "idle"
    assert hook.classify(msg)[1] == ""


def test_question_detection_preserved(hook):
    assert hook.classify("Some work.\nWhat should I do next?")[0] == "question"
    # A mid-message marker plus a trailing question: question wins, no
    # phantom blocked state.
    assert hook.classify("BLOCKED: earlier note\nIs this the right approach?")[0] \
        == "question"


def test_detail_from_final_line_only(hook):
    # The detail comes from the marker line, not from an earlier decoy.
    state, detail = hook.classify(
        "DONE: decoy in the middle\nMore prose.\nDONE: the real one")
    assert state == "done"
    assert detail == "the real one"
