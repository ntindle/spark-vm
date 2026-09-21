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
                stdout = b"bash"
            else:
                stdout = b""
        return P()

    monkeypatch.setattr(cli, "run", fake_run)
    assert cli._answer_trust_prompt("demo") is True
    sent = [" ".join(c) for c in calls if "send-keys" in c]
    assert any(c.endswith(" 1") for c in sent)
    assert any(c.endswith(" Enter") for c in sent)


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
