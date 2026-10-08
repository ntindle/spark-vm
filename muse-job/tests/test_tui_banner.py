"""Tests for the dead-TUI watchdog path (resume-banner detection/recovery).

Observed failure mode: the model stream dies ("model failed: model stream
idle timeout"), no Stop/SessionEnd hook fires, the tmux session stays up,
and the pane parks at the TUI's session-picker banner
("/resume reopens a past session ..."). `muse-job watch` must detect this
(dead pane inside live tmux) and attempt the gentle `/resume --last`
recovery the banner advertises.

The fix fails closed around the same two-signal shape as the steer guard:
the pane must show the TUI's own banner text AND the foreground process
must still be the muse binary. A dead pane that dropped to a shell is never
pasted into (issue #4) -- and the pasted text is a fixed literal with no
shell metacharacters, so even a misclassified paste is inert.
"""
import importlib
import importlib.machinery
import importlib.util
import os
import re
import sys

import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job")


def load_script(name, path):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


@pytest.fixture()
def cli(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_banner", CLI_PATH)


# Pane text captured from the real dead job (trackball-base-schematic,
# 2026-09-21): model stream idle timeout, TUI at the resume banner.
BANNER_PANE = """\
  Read 4 files · ctrl+o

◆ Ran 6 commands · Search rules for pin and USB assignments · +4 ✓ · 0.7s · ctrl+o

◆ model failed: model stream idle timeout after 180000ms

────────────────────────────────────────────────────────────────────────
❯ /resume reopens a past session (--last for the latest)
────────────────────────────────────────────────────────────────────────
  muse-spark-1.3-contributor · max · ~/muse-jobs/trackball-base-schematic/work · YOLO
"""

LIVE_PANE = """\
◆ Ran 2 commands · Probe rotation transform direction · ✓ · 3.1s · ctrl+o

  Thinking…

❯ """


def test_resume_banner_recognized(cli):
    assert cli._pane_shows_resume_banner(BANNER_PANE, "muse-bin-1.3.0-R3233.1")


def test_resume_banner_recognized_plain_muse(cli):
    assert cli._pane_shows_resume_banner(BANNER_PANE, "muse")


def test_live_pane_is_not_banner(cli):
    assert not cli._pane_shows_resume_banner(LIVE_PANE, "muse")
    assert not cli._pane_shows_resume_banner(LIVE_PANE, "node")


def test_banner_text_under_shell_process_rejected(cli):
    # Content alone is spoofable: a shell pane echoing the banner text must
    # not qualify (nothing is ever pasted into a non-muse process).
    assert not cli._pane_shows_resume_banner(BANNER_PANE, "bash")
    assert not cli._pane_shows_resume_banner(BANNER_PANE, "zsh")


def test_empty_pane_not_banner(cli):
    assert not cli._pane_shows_resume_banner("", "muse")
    assert not cli._pane_shows_resume_banner(BANNER_PANE, "")


def test_recovery_literal_is_shell_inert(cli):
    # The watchdog pastes this into the pane; it must be a fixed literal
    # with no shell metacharacters, so a misclassified paste is a
    # command-not-found no-op, never code execution.
    assert cli._RESUME_BANNER_CMD == "/resume --last"
    assert not re.search(r"[`$;|&<>(){}\"']", cli._RESUME_BANNER_CMD)


def test_banner_cleared_predicate(cli):
    assert cli._pane_banner_cleared("some output\n❯ ", "muse")
    # Our own unsubmitted echo of the recovery command (the TUI swallowed
    # the Enter) is not a cleared banner: the banner screen is still up.
    assert not cli._pane_banner_cleared("❯ /resume --last", "muse")
    assert not cli._pane_banner_cleared(BANNER_PANE, "muse")
    assert not cli._pane_banner_cleared("", "muse")
    # Banner gone but no input box yet (TUI still booting) is not cleared.
    assert not cli._pane_banner_cleared("  Thinking…\n", "muse")


def test_banner_cleared_into_shell_pane_is_not_cleared(cli):
    # The TUI died after a failed recovery: the banner scrolled out of the
    # tail and the pane dropped to a shell whose prompt starts with ❯
    # (issue #4). Content alone would read this as cleared and the watchdog
    # would log a false tui-recovered.
    pane = "muse exited: stream error\n❯ "
    assert not cli._pane_banner_cleared(pane, "bash")
    assert not cli._pane_banner_cleared(pane, "zsh")


# The TUI swallowed the Enter on our own /resume --last: the banner screen
# is still up, with our unsubmitted command sitting in the input box.
SWALLOWED_ENTER_PANE = (
    "◆ model failed: model stream idle timeout after 180000ms\n"
    + "─" * 40 + "\n"
    + "❯ /resume --last\n"
    + "─" * 40 + "\n"
    + "  muse-spark-1.3-contributor · max · ~/work · YOLO\n"
)


def test_swallowed_enter_echo_is_neither_cleared_nor_live(cli):
    # The recovery echo is not a cleared banner, and the dead banner screen
    # must not classify as a live TUI -- both predicates used to say yes.
    assert not cli._pane_banner_cleared(SWALLOWED_ENTER_PANE, "muse")
    assert not cli._pane_shows_live_tui(SWALLOWED_ENTER_PANE, "muse")
    assert not cli._pane_shows_live_tui(
        SWALLOWED_ENTER_PANE, "muse-bin-1.3.0-R3401.1")
    assert not cli._pane_shows_resume_banner(SWALLOWED_ENTER_PANE, "muse")


def test_live_idle_with_footer_below_input_box(cli):
    # The TUI's idle state renders the model footer BELOW the ❯ line --
    # the input box is live even though it is not the last viewport line.
    pane = ("◆ model failed: model stream idle timeout after 180000ms\n"
            "  warning: resumed cleanly.\n"
            "─" * 40 + "\n"
            "❯ \n"
            "─" * 40 + "\n"
            "  muse-spark-1.3-contributor · max · ~/work · YOLO\n")
    assert cli._pane_shows_live_tui(pane, "muse-bin-1.3.0-R3401.1")
    assert not cli._pane_shows_resume_banner(pane, "muse-bin-1.3.0-R3401.1")


def test_stale_input_box_with_shell_prompt_below_rejected(cli):
    # Stale ❯ line from the dead TUI, shell prompt underneath: the lines
    # below the box are not TUI chrome, so this is not a live TUI.
    pane = "some model output\n❯ previous question\nntindle@spark-vm:~/work$ "
    assert not cli._pane_shows_live_tui(pane, "muse")
    assert not cli._pane_shows_live_tui(pane, "muse-bin-1.3.0-R3401.1")


def test_stale_banner_in_scrollback_does_not_block_live_tui(cli):
    # After a successful /resume, the old banner text stays visible in the
    # upper viewport -- only the tail counts as current state.
    live_tail = ("◆ resumed cleanly.\n" + "─" * 40 + "\n❯ \n" + "─" * 40
                 + "\n  muse-spark-1.3-contributor · max · ~/work · YOLO\n")
    pane = BANNER_PANE + "\n" * 30 + live_tail
    assert cli._pane_shows_live_tui(pane, "muse-bin-1.3.0-R3401.1")
    assert not cli._pane_shows_resume_banner(pane, "muse-bin-1.3.0-R3401.1")
    assert cli._pane_banner_cleared(pane, "muse-bin-1.3.0-R3401.1")


def test_trust_prompt_blocks_live_predicate(cli):
    # A live-looking input box is also in the tail, so the fixture
    # discriminates the trust check itself: the old last-line-only code
    # accepted this pane.
    pane = ("cd '/home/ntindle/muse-jobs/demo/work' && muse resume 'x'\n"
            "Do you trust this workspace?\n"
            "Workspace: /home/ntindle/muse-jobs/demo/work\n"
            "> 1  Trust and continue\n"
            "  2  Quit\n"
            "❯ \n")
    assert not cli._pane_shows_live_tui(pane, "muse")
    # ...but once answered and scrolled past, the TUI is live again.
    assert cli._pane_shows_live_tui(pane + "\n" * 20 + "❯ \n", "muse")


# ---------------------------------------------------------------------------
# Issue #961: trust-gate substring matching can misfire on a live TUI's own
# conversation. The classifier must require the gate's full observed shape
# (question + option line) -- a mere mention of the phrase in a working
# session's conversation must not read as a gate, or the watch loop's
# auto-answer types "1"+Enter into the live input box.
# ---------------------------------------------------------------------------

# A live TUI whose own conversation mentions the trust question (question
# text present, no option line anywhere in the tail).
CONVERSATION_MENTION_PANE = (
    "◆ The trust gate asks \"Do you trust this workspace?\" on first\n"
    "  resume -- answering 1 once unblocks the TUI.\n"
    + "─" * 40 + "\n❯ \n" + "─" * 40 + "\n"
    + "  muse-spark-1.3-contributor · max · ~/work · YOLO\n")


def test_trust_gate_requires_question_and_option(cli):
    # Issue #961: the gate is the question AND its option line co-occurring
    # in the tail. Either half alone is not the gate.
    assert cli._pane_shows_trust_gate(TRUST_GATE_PANE)
    assert not cli._pane_shows_trust_gate(
        "The agent asked: Do you trust this workspace?\n❯ \n")
    assert not cli._pane_shows_trust_gate("> 1  Trust and continue\n❯ \n")
    assert not cli._pane_shows_trust_gate("❯ \n")
    assert not cli._pane_shows_trust_gate("")


# ---------------------------------------------------------------------------
# Issue #972: the two halves of the gate must sit on SEPARATE lines with the
# option line after the question line within a small window. The #961
# tail-substring check is order-insensitive and position-insensitive, so a
# live TUI's conversation containing BOTH phrases still misfires.
# ---------------------------------------------------------------------------

# A single line containing both halves (the agent pasting a gate transcript,
# or a one-line summary of its choice) -- not the gate.
SINGLE_LINE_BOTH_HALVES = (
    'I chose "Trust and continue" when it asked '
    '"Do you trust this workspace?"\n'
    "❯ \n")

# Both halves present but the option line is beyond the line window.
DISTANT_OPTION_PANE = (
    "Do you trust this workspace?\n"
    "filler line one\n"
    "filler line two\n"
    "filler line three\n"
    "filler line four\n"
    "> 1  Trust and continue\n"
    "❯ \n")

# Both halves present but in the wrong order (option line before question).
REVERSED_ORDER_PANE = (
    "> 1  Trust and continue\n"
    "Do you trust this workspace?\n"
    "❯ \n")

# The real gate shape with one extra line of slack (option 3 lines after the
# question) -- still the gate.
GATE_WITH_SLACK_PANE = (
    "Do you trust this workspace?\n"
    "Workspace: /home/ntindle/muse-jobs/demo/work\n"
    "(a plugin banner took a line)\n"
    "> 1  Trust and continue\n"
    "  2  Quit\n")

# Both halves present but the option line sits exactly one line beyond the
# window (4 lines after the question) -- not the gate. Pins
# _TRUST_GATE_LINE_WINDOW == 3 exactly: DISTANT_OPTION_PANE alone only
# pins the window to <= 4.
OPTION_JUST_OUTSIDE_WINDOW_PANE = (
    "Do you trust this workspace?\n"
    "Workspace: /home/ntindle/muse-jobs/demo/work\n"
    "filler line one\n"
    "filler line two\n"
    "> 1  Trust and continue\n"
    "  2  Quit\n")


def test_trust_gate_requires_separate_lines_in_window(cli):
    # Issue #972: same-line co-occurrence of both phrases is a misfire, not
    # a gate; so is an option line beyond the window or before the question.
    assert not cli._pane_shows_trust_gate(SINGLE_LINE_BOTH_HALVES)
    assert not cli._pane_shows_trust_gate(DISTANT_OPTION_PANE)
    assert not cli._pane_shows_trust_gate(OPTION_JUST_OUTSIDE_WINDOW_PANE)
    assert not cli._pane_shows_trust_gate(REVERSED_ORDER_PANE)
    # The real shape (option ~2 lines after the question) still matches.
    assert cli._pane_shows_trust_gate(TRUST_GATE_PANE)
    assert cli._pane_shows_trust_gate(GATE_WITH_SLACK_PANE)


# ---------------------------------------------------------------------------
# Issue #993: the two-line prose misfire. A live TUI whose own conversation
# narrates the trust choice carries both phrases on ADJACENT lines with no
# selector marker:
#   The TUI asked 'Do you trust this workspace?'
#   I chose 'Trust and continue'
# The #972 two-signal check matches it (question line + option-substring
# line within the window) and the watch loop types "1"+Enter into a working
# session. The classifier must match the real selector marker (`> 1`) on
# the option line, not the bare option text.
# ---------------------------------------------------------------------------

# The #993 misfire: both phrases present on separate adjacent lines, but
# the option line carries no selector marker -- not the gate.
TWO_LINE_PROSE_MISFIRE_PANE = (
    "The TUI asked 'Do you trust this workspace?'\n"
    "I chose 'Trust and continue'\n"
    "❯ \n")

# Option text with a quote-style marker but no selector (`> N`) -- prose
# quoting the option, not the gate's selector list.
MARKERLESS_OPTION_PANE = (
    "Do you trust this workspace?\n"
    "> Trust and continue\n"
    "❯ \n")


def test_trust_gate_requires_selector_marker(cli):
    # Issue #993: prose mentioning both phrases on separate lines must not
    # match -- the option line needs the gate's `> N` selector marker.
    assert not cli._pane_shows_trust_gate(TWO_LINE_PROSE_MISFIRE_PANE)
    assert not cli._pane_shows_trust_gate(MARKERLESS_OPTION_PANE)
    # The real gate (marker `> 1`) still matches, including with slack
    # and tight spacing variants of the marker.
    assert cli._pane_shows_trust_gate(TRUST_GATE_PANE)
    assert cli._pane_shows_trust_gate(GATE_WITH_SLACK_PANE)
    assert cli._pane_shows_trust_gate(
        "Do you trust this workspace?\n"
        "Workspace: /home/ntindle/muse-jobs/demo/work\n"
        ">1 Trust and continue\n"
        "  2  Quit\n")
    assert cli._pane_shows_trust_gate(
        "Do you trust this workspace?\n"
        ">   10   Trust and continue\n"
        "❯ \n")


def test_trust_phrase_in_live_conversation_still_reads_live(cli):
    # Issue #961: the old bare-substring veto in _pane_shows_live_tui would
    # read this pane as gated. The TUI must keep reading as live.
    assert cli._pane_shows_live_tui(CONVERSATION_MENTION_PANE, "muse")


def test_pane_trust_prompt_clear_when_conversation_mentions_gate(
        cli, monkeypatch):
    # Issue #961: end-to-end through job_status -- the live TUI discussing
    # the gate must not raise pane_trust_prompt (the watch loop would answer
    # it into the live input box).
    _job_status_harness(cli, monkeypatch, CONVERSATION_MENTION_PANE, "muse")
    job = {"slug": "demo", "session_uuid": None, "state": "active",
           "started_at": _time.time()}
    st = cli.job_status(job, "demo")
    assert st["pane_trust_prompt"] is False
    assert st["pane_trust_unverified"] is False
    assert st["pane_live_tui"] is True


def test_answer_trust_prompt_ignores_conversation_mention(cli, monkeypatch):
    # Issue #961: the auto-answer must not fire on a mere mention of the
    # phrase in a live session -- zero keys sent.
    calls = []

    def fake_run(*argv, **kw):
        calls.append(list(argv))

        class P:
            returncode = 0
            stderr = b""
            if "capture-pane" in argv:
                stdout = CONVERSATION_MENTION_PANE.encode()
            elif "display-message" in argv:
                stdout = b"muse"
            else:
                stdout = b""
        return P()

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    assert cli._answer_trust_prompt("demo", timeout=0.01) is False
    assert [c for c in calls if "send-keys" in c] == []


def test_tui_process_predicate(cli):
    # Version-tolerant: the TUI presents as muse-bin-<version> as well as
    # the plain launcher names. Shells are never the TUI (issue #4).
    assert cli._is_tui_process("muse")
    assert cli._is_tui_process("node")
    assert cli._is_tui_process("muse-bin-1.3.0-R3233.1")
    assert cli._is_tui_process("muse-bin-1.3.0-R3401.1")
    assert not cli._is_tui_process("bash")
    assert not cli._is_tui_process("zsh")
    assert not cli._is_tui_process("")


def test_resume_gone_pattern_matches_observed_tui_wording(cli):
    # 2026-09-21: after a model-stream death, `muse resume <uuid>` printed
    # "no retained sessions found for this workspace" -- the old pattern
    # missed it and reported a successful resume of a dead session.
    assert cli._RESUME_GONE_RE.search(
        "◆ no retained sessions found for this workspace")
    assert cli._RESUME_GONE_RE.search("Error: session not found")
    # A healthy resumed TUI must not trip the fallback.
    assert not cli._RESUME_GONE_RE.search(
        "◆ Ran 2 commands · done · 3.1s\n❯ ")
    assert not cli._RESUME_GONE_RE.search("0 errors, 3 warnings")


def test_answer_trust_prompt_answers_and_returns_true(cli, monkeypatch):
    panes = ["Do you trust this workspace?\n> 1  Trust and continue\n  2  Quit"]
    calls = []

    def fake_run(*argv, **kw):
        calls.append(list(argv))

        class P:
            returncode = 0
            stderr = b""
            if "capture-pane" in argv:
                stdout = panes[0].encode()
            elif "display-message" in argv:
                # Security B1 (PR #816 review): the gate fires only while the
                # foreground process is the TUI -- a dead pane is never sent
                # keystrokes, even with the prompt text in its scrollback.
                stdout = b"muse"
            else:
                stdout = b""
        return P()

    monkeypatch.setattr(cli, "run", fake_run)
    assert cli._answer_trust_prompt("demo") is True
    sent = [" ".join(c) for c in calls if "send-keys" in c]
    assert any(c.endswith(" 1") for c in sent)
    assert any(c.endswith(" Enter") for c in sent)


def test_answer_trust_prompt_refuses_dead_pane_with_stale_text(cli, monkeypatch):
    # Security B1 (PR #816 review, issue #791): a dead pane whose scrollback
    # tail still shows the gate text must NOT be answered -- typing "1"+Enter
    # into that shell is a false answer (issue #4). Zero keys sent.
    pane = "Do you trust this workspace?\n> 1  Trust and continue\n  2  Quit\n$ "
    calls = []

    def fake_run(*argv, **kw):
        calls.append(list(argv))

        class P:
            returncode = 0
            stderr = b""
            if "capture-pane" in argv:
                stdout = pane.encode()
            elif "display-message" in argv:
                stdout = b"bash"
            else:
                stdout = b""
        return P()

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    assert cli._answer_trust_prompt("demo", timeout=0.01) is False
    assert [c for c in calls if "send-keys" in c] == []


def test_answer_trust_prompt_no_prompt_returns_false(cli, monkeypatch):
    def fake_run(*argv, **kw):
        class P:
            returncode = 0
            stderr = b""
            stdout = b"bash" if "display-message" in argv else "❯ ".encode()
        return P()

    monkeypatch.setattr(cli, "run", fake_run)
    # Live TUI at a ❯ prompt under bash fg... _pane_shows_live_tui is False
    # (bash), so it polls to timeout. Keep the timeout tiny via monkeypatch.
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    orig = cli._answer_trust_prompt

    def fast(slug, timeout=0.01):
        return orig(slug, timeout=timeout)

    assert fast("demo") is False


class FakeClock:
    """Deterministic clock so _recover_resume_banner's poll finishes
    instantly (same pattern as test_steer_tui_guard.py)."""

    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    def sleep(self, s):
        self.now += s


class FakeRun:
    """Fake tmux runner. `panes` is the capture-pane script: successive
    capture-pane calls pop from the list, and the last entry repeats.
    `pane_cmd` is the foreground process display-message reports."""

    def __init__(self, panes, pane_cmd="muse"):
        self.panes = list(panes)
        self.pane_cmd = pane_cmd
        self.calls = []

    def __call__(self, *argv, **kw):
        self.calls.append(argv)
        if argv[1] == "capture-pane":
            out = self.panes.pop(0) if len(self.panes) > 1 else self.panes[0]

            class P:
                returncode = 0
                stdout = out.encode()
                stderr = b""

            return P()
        if argv[1] == "display-message":

            class P:
                returncode = 0
                stderr = b""

            P.stdout = self.pane_cmd.encode()
            return P()

        class P:
            returncode = 0
            stdout = b""
            stderr = b""

        return P()

    def sent_keys(self):
        return [c for c in self.calls if c[1] == "send-keys"]


LIVE_RECOVERED_PANE = (
    "◆ resumed cleanly.\n"
    + "─" * 40 + "\n"
    + "❯ \n"
    + "─" * 40 + "\n"
    + "  muse-spark-1.3-contributor · max · ~/work · YOLO\n"
)


def _recover_harness(cli, monkeypatch, panes, pane_cmd="muse"):
    fr = FakeRun(panes, pane_cmd=pane_cmd)
    monkeypatch.setattr(cli, "run", fr)
    monkeypatch.setattr(cli, "time", FakeClock())
    return fr


def test_recover_resume_banner_success(cli, monkeypatch):
    # Banner clears into a live TUI: True, with text and Enter as
    # SEPARATE send-keys calls (the project's tmux input rule).
    fr = _recover_harness(cli, monkeypatch,
                          [BANNER_PANE, LIVE_RECOVERED_PANE])
    assert cli._recover_resume_banner("demo") is True
    sent = fr.sent_keys()
    assert sent[0][1:] == ("send-keys", "-t", "mjob-demo", "-l",
                           cli._RESUME_BANNER_CMD)
    assert sent[1][1:] == ("send-keys", "-t", "mjob-demo", "Enter")


def test_recover_resume_banner_timeout_returns_false(cli, monkeypatch):
    # Banner never clears: polls to the deadline, returns False -- the
    # watchdog then logs a loud tui-unrecovered, never a silent stall.
    fr = _recover_harness(cli, monkeypatch, [BANNER_PANE])
    assert cli._recover_resume_banner("demo", timeout=60) is False
    assert fr.sent_keys()  # the /resume --last attempt did go out


def test_recover_resume_banner_requires_tui_process(cli, monkeypatch):
    # The banner scrolled out of the tail and the pane dropped to a shell
    # with a ❯ prompt (issue #4): content alone would read this as cleared.
    # Recovery must report False, not a false tui-recovered.
    shell_pane = "muse exited: stream error\n❯ "
    fr = _recover_harness(cli, monkeypatch, [shell_pane], pane_cmd="bash")
    assert cli._recover_resume_banner("demo", timeout=60) is False
    assert fr.sent_keys()


# ---------------------------------------------------------------------------
# Issue #791: trust prompts kill jobs despite --yolo.
#
# _spawn launched the TUI with --yolo in a brand-new workdir but never
# answered the workspace-trust gate (only cmd_resume and the fallback-fresh
# path did). The unanswered TUI session ends, the pane drops to a shell, and
# the job strands until a human intervenes. Fix: _spawn answers the gate
# post-launch; the watchdog exposes a trust-prompt pane as its own signal
# (pane_trust_prompt) and recovers it via _recover_trust_prompt.
# ---------------------------------------------------------------------------
import argparse as _argparse
import json as _json
import subprocess as _subprocess
import time as _time

TRUST_GATE_PANE = ("Do you trust this workspace?\n"
                   "Workspace: /home/ntindle/muse-jobs/demo/work\n"
                   "> 1  Trust and continue\n"
                   "  2  Quit\n")


def _trust_status(**kw):
    st = {
        "slug": "demo", "job_state": "active", "tmux_alive": True,
        "pane_live_tui": False, "pane_resume_banner": False,
        "pane_trust_prompt": True, "pane_trust_unverified": False,
        "pane_cmd": "muse",
        "session_created": _time.time(), "session_uuid": None,
        "session_status": None, "bytes_total": 0, "bytes_delta": 0,
        "last_hook_event": None, "progress_age_s": None,
        "dir_bytes": 0, "elapsed_h": 0.1, "budget_hours": 8,
    }
    st.update(kw)
    return st


def _job_status_harness(cli, monkeypatch, pane, pane_cmd):
    # job_status's subprocess/OS surface, faked at the helper boundary.
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: True)
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: (pane, pane_cmd))
    monkeypatch.setattr(cli, "head_info", lambda uuid: (None, 0))
    monkeypatch.setattr(cli, "last_event", lambda uuid: None)
    monkeypatch.setattr(cli, "_tmux_session_created",
                        lambda slug: _time.time())
    monkeypatch.setattr(cli, "_cached_dir_bytes", lambda job, slug: 0)


def test_pane_trust_prompt_set_when_tui_blocked_at_gate(cli, monkeypatch):
    _job_status_harness(cli, monkeypatch, TRUST_GATE_PANE, "muse")
    job = {"slug": "demo", "session_uuid": None, "state": "active",
           "started_at": _time.time()}
    st = cli.job_status(job, "demo")
    assert st["pane_trust_prompt"] is True
    # The gate implies not-live (the trust text vetoes the live check).
    assert st["pane_live_tui"] is False
    assert st["pane_resume_banner"] is False


def test_pane_trust_prompt_clear_when_shell_holds_stale_text(cli, monkeypatch):
    # The TUI died at the gate and the pane dropped to a shell; the prompt
    # text lingers in the scrollback tail. Issue #4: a dead pane must never
    # be sent keystrokes, so the signal stays clear.
    _job_status_harness(cli, monkeypatch, TRUST_GATE_PANE + "\n$ ", "bash")
    job = {"slug": "demo", "session_uuid": None, "state": "active",
           "started_at": _time.time()}
    st = cli.job_status(job, "demo")
    assert st["pane_trust_prompt"] is False
    assert st["pane_live_tui"] is False


def test_pane_trust_prompt_clear_on_live_tui(cli, monkeypatch):
    _job_status_harness(cli, monkeypatch, LIVE_PANE, "muse")
    job = {"slug": "demo", "session_uuid": None, "state": "active",
           "started_at": _time.time()}
    st = cli.job_status(job, "demo")
    assert st["pane_trust_prompt"] is False
    assert st["pane_live_tui"] is True


def _spawn_harness(cli, monkeypatch, tmp_path):
    calls = []

    def fake_run(*argv, **kwargs):
        calls.append(argv)
        return _subprocess.CompletedProcess(
            args=list(argv), returncode=0, stdout=b"deadbeef\n", stderr=b"")

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: False)
    # Skip the 90s session-uuid discovery poll: the uuid path is not what
    # these tests pin.
    monkeypatch.setattr(cli, "find_session",
                        lambda work, started: "fake-uuid")
    prompt = tmp_path / "p.md"
    prompt.write_text("a perfectly innocent prompt with no secrets in it")
    args = cli.argparse.Namespace(
        slug="trustjob", repo="https://example.com/SomeOrg/SomeRepo.git",
        prompt_file=str(prompt), base=None, budget_hours=8,
        allow_secrets=False)
    return args


def test_spawn_answers_trust_prompt_post_launch(cli, monkeypatch, tmp_path):
    # Issue #791: the root fix -- _spawn answers the workspace-trust gate
    # after launching the TUI, exactly like the resume path already did.
    answered = []
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda slug, timeout=20: answered.append(slug) or True)
    args = _spawn_harness(cli, monkeypatch, tmp_path)
    cli._spawn(args.slug, args)  # returns None on success; would raise first
    assert answered == ["trustjob"]


def test_recover_trust_prompt_reports_answered_when_live(cli, monkeypatch):
    answered = []
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda slug, timeout=20: answered.append(slug) or True)
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: ("❯ \n", "muse"))
    ev = cli._recover_trust_prompt("demo")
    assert answered == ["demo"]  # the answer attempt is the point
    assert ev["job"] == "demo"
    assert ev["signal"] == "trust-answered"


def test_recover_trust_prompt_pages_when_still_blocked(cli, monkeypatch):
    # The gate is still showing (or the capture failed): loud, actionable,
    # with the exact operator remedy -- never lumped into tui-dead.
    monkeypatch.setattr(cli, "_answer_trust_prompt", lambda slug, timeout=20: False)
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: ("", "bash"))
    ev = cli._recover_trust_prompt("demo")
    assert ev["signal"] == "blocked-trust"
    assert "muse-job log" in ev["detail"]


def _make_watch_job(cli, slug):
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    os.makedirs(cli.METADATA_DIR, exist_ok=True)
    job = {"slug": slug, "state": "active", "started_at": _time.time(),
           "session_uuid": None}
    with open(cli.job_json_path(slug), "w") as f:
        _json.dump(job, f)


def _watch_events(cli, capsys):
    rc = cli.cmd_watch(_argparse.Namespace())
    assert rc == 0
    return [_json.loads(l) for l in capsys.readouterr().out.splitlines()
            if l.strip()]


def test_watch_emits_trust_answered_for_blocked_pane(cli, monkeypatch, capsys):
    # End to end through cmd_watch: a live tmux whose TUI sits at the trust
    # gate yields the distinct trust-answered signal, not generic tui-dead.
    _make_watch_job(cli, "trustjob")
    monkeypatch.setattr(cli, "job_status",
                        lambda job, slug: _trust_status(slug=slug))
    answered = []
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda slug, timeout=20: answered.append(slug) or True)
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: ("❯ \n", "muse"))
    monkeypatch.setattr(cli, "_emit_tui_swap_event",
                        lambda job, slug, pane_cmd, events: None)
    monkeypatch.setattr(cli, "maybe_adopt_session",
                        lambda job, slug: (None, None))
    monkeypatch.setattr(cli, "git_diffstat", lambda path: "")
    events = _watch_events(cli, capsys)
    by_sig = {}
    for e in events:
        by_sig.setdefault(e["signal"], []).append(e)
    assert answered == ["trustjob"]
    assert "trust-answered" in by_sig
    assert by_sig["trust-answered"][0]["job"] == "trustjob"
    assert "tui-dead" not in by_sig  # distinct signal, not the generic lump


def test_watch_emits_blocked_trust_when_gate_persists(cli, monkeypatch, capsys):
    # The answer attempt did not clear the gate: the loud blocked-trust
    # page fires instead of a silent strand.
    _make_watch_job(cli, "trustjob")
    monkeypatch.setattr(cli, "job_status",
                        lambda job, slug: _trust_status(slug=slug))
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda slug, timeout=20: False)
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: (TRUST_GATE_PANE, "muse"))
    monkeypatch.setattr(cli, "_emit_tui_swap_event",
                        lambda job, slug, pane_cmd, events: None)
    monkeypatch.setattr(cli, "maybe_adopt_session",
                        lambda job, slug: (None, None))
    monkeypatch.setattr(cli, "git_diffstat", lambda path: "")
    events = _watch_events(cli, capsys)
    sigs = [e["signal"] for e in events if e["job"] == "trustjob"]
    assert "blocked-trust" in sigs


# --- issue #836: trust gate visible while the foreground process is not a
# recognized TUI process -----------------------------------------------
# The #791 fix answered the gate only when the pane's foreground process
# was a known TUI process (issue #4 anti-spoofing gate). #836 showed the
# hole: a gate with an unrecognized fg process (new binary name after an
# in-place auto-update, a wrapper launcher, a capture hiccup) kept
# pane_trust_prompt clear, and the watchdog lumped it into generic
# tui-dead -- the job stranded with no recovery attempt. The gate is now
# its own loud signal (blocked-trust-unverified), still never auto-answered.


def test_pane_trust_unverified_set_when_process_not_tui(cli, monkeypatch):
    # Trust text in the tail, but the fg process is bash: the gate is
    # observably showing, yet the auto-answer is refused (issue #4).
    _job_status_harness(cli, monkeypatch, TRUST_GATE_PANE, "bash")
    job = {"slug": "demo", "session_uuid": None, "state": "active",
           "started_at": _time.time()}
    st = cli.job_status(job, "demo")
    assert st["pane_trust_prompt"] is False
    assert st["pane_trust_unverified"] is True
    assert st["pane_live_tui"] is False


def test_pane_trust_unverified_set_when_process_unknown(cli, monkeypatch):
    # Capture hiccup: empty process name with the trust text in the tail.
    _job_status_harness(cli, monkeypatch, TRUST_GATE_PANE, "")
    job = {"slug": "demo", "session_uuid": None, "state": "active",
           "started_at": _time.time()}
    st = cli.job_status(job, "demo")
    assert st["pane_trust_prompt"] is False
    assert st["pane_trust_unverified"] is True


def test_pane_trust_unverified_clear_when_process_recognized(cli, monkeypatch):
    # The verified path still classifies the same pane as the answerable
    # gate -- the new signal must not steal it.
    _job_status_harness(cli, monkeypatch, TRUST_GATE_PANE, "muse")
    job = {"slug": "demo", "session_uuid": None, "state": "active",
           "started_at": _time.time()}
    st = cli.job_status(job, "demo")
    assert st["pane_trust_prompt"] is True
    assert st["pane_trust_unverified"] is False


def test_pane_trust_unverified_clear_on_live_tui(cli, monkeypatch):
    _job_status_harness(cli, monkeypatch, LIVE_PANE, "muse")
    job = {"slug": "demo", "session_uuid": None, "state": "active",
           "started_at": _time.time()}
    st = cli.job_status(job, "demo")
    assert st["pane_trust_prompt"] is False
    assert st["pane_trust_unverified"] is False


def test_pane_trust_unverified_clear_when_no_trust_text(cli, monkeypatch):
    # A plain dead shell with no trust text in the tail: no trust signal
    # of any kind -- still generic tui-dead.
    _job_status_harness(cli, monkeypatch, "last login\n$ ", "bash")
    job = {"slug": "demo", "session_uuid": None, "state": "active",
           "started_at": _time.time()}
    st = cli.job_status(job, "demo")
    assert st["pane_trust_prompt"] is False
    assert st["pane_trust_unverified"] is False


def test_watch_emits_blocked_trust_unverified_and_never_answers(
        cli, monkeypatch, capsys):
    # End to end through cmd_watch: trust text visible but the fg process
    # is unverified -- the distinct blocked-trust-unverified signal fires,
    # NO answer attempt is made (issue #4: never send keystrokes into an
    # unverified pane), and generic tui-dead stays out of the events.
    _make_watch_job(cli, "trustjob")
    monkeypatch.setattr(cli, "job_status",
                        lambda job, slug: _trust_status(
                            slug=slug, pane_trust_prompt=False,
                            pane_trust_unverified=True, pane_cmd="bash"))
    answered = []
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda slug, timeout=20: answered.append(slug) or True)
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: (TRUST_GATE_PANE, "bash"))
    monkeypatch.setattr(cli, "_emit_tui_swap_event",
                        lambda job, slug, pane_cmd, events: None)
    monkeypatch.setattr(cli, "maybe_adopt_session",
                        lambda job, slug: (None, None))
    monkeypatch.setattr(cli, "git_diffstat", lambda path: "")
    events = _watch_events(cli, capsys)
    by_sig = {}
    for e in events:
        by_sig.setdefault(e["signal"], []).append(e)
    assert answered == [], "issue #4: no keystrokes into an unverified pane"
    assert "blocked-trust-unverified" in by_sig
    ev = by_sig["blocked-trust-unverified"][0]
    assert ev["job"] == "trustjob"
    assert "muse-job log" in ev["detail"]
    assert "tui-dead" not in by_sig
    assert "trust-answered" not in by_sig
    assert "blocked-trust" not in by_sig


def test_watch_integration_unverified_gate_end_to_end(
        cli, monkeypatch, capsys):
    # QA AC5 (review round-1): no stub between job_status and cmd_watch --
    # the REAL detection feeds the REAL dispatch. Trust text in the tail
    # with an unverified fg process must yield blocked-trust-unverified
    # from the live pipeline, with no answer attempt. Pre-fix this emitted
    # generic tui-dead (the #836 complaint).
    _make_watch_job(cli, "trustjob")
    _job_status_harness(cli, monkeypatch, TRUST_GATE_PANE, "bash")
    answered = []
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda slug, timeout=20: answered.append(slug) or True)
    monkeypatch.setattr(cli, "_emit_tui_swap_event",
                        lambda job, slug, pane_cmd, events: None)
    monkeypatch.setattr(cli, "maybe_adopt_session",
                        lambda job, slug: (None, None))
    monkeypatch.setattr(cli, "git_diffstat", lambda path: "")
    events = _watch_events(cli, capsys)
    by_sig = {}
    for e in events:
        by_sig.setdefault(e["signal"], []).append(e)
    assert answered == [], "issue #4: no keystrokes into an unverified pane"
    assert "blocked-trust-unverified" in by_sig
    assert by_sig["blocked-trust-unverified"][0]["job"] == "trustjob"
    assert "tui-dead" not in by_sig
