"""Regression test for issue #12 item L3 (residual).

cmd_log printed raw `tmux capture-pane` output straight to the operator's
terminal: pane content is agent-influenced, so a crafted line could inject
terminal escape sequences (OSC title set, line-erase, bare ESC) into the
operator's terminal. The fix routes cmd_log's print through the same
_clean_text sanitizer already used for event `detail` fields and `status`
output.
"""
import argparse
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
    return load_script("muse_job_cli_logtest", CLI_PATH)


def test_cmd_log_sanitizes_capture_pane_output(cli, monkeypatch, capsys):
    # A pane carrying an OSC title-set sequence, a bare ESC, and a CSI
    # erase-line must come out as plain text — no escape bytes reach the
    # operator's terminal — while the legit content survives.
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: True)
    evil = ("legit line one\n"
            "\x1b]0;pwned title\x07second line\n"
            "third \x1b[2K line\n"
            "\x1bc reset attempt")

    class _Result:
        stdout = evil.encode()

    monkeypatch.setattr(cli, "run", lambda *a, **k: _Result())
    assert cli.cmd_log(argparse.Namespace(slug="x", n=10)) == 0
    out = capsys.readouterr().out
    assert "\x1b" not in out, "escape byte leaked into operator terminal"
    assert "pwned title" not in out
    assert "legit line one" in out
    assert "second line" in out


def test_cmd_log_preserves_last_n_lines(cli, monkeypatch, capsys):
    # Sanitization must not change cmd_log's tail behavior.
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: True)

    class _Result:
        stdout = b"one\ntwo\nthree\nfour\n"

    monkeypatch.setattr(cli, "run", lambda *a, **k: _Result())
    cli.cmd_log(argparse.Namespace(slug="x", n=2))
    out = capsys.readouterr().out
    assert out.splitlines() == ["three", "four"]


def test_dead_tui_refusal_sanitizes_pane_tail(cli, monkeypatch):
    # Security round-1 B1: the steer refusal error embeds up to 8 lines of
    # agent-influenced pane content via _dead_tui_msg; it reached the
    # operator's stderr raw. It goes through _clean_text now.
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: True)
    evil = "line1\n\x1b]0;pwned\x07line2\n\x1b[2Kline3"
    monkeypatch.setattr(
        cli, "_wait_live_tui", lambda slug, timeout=30: (evil, "bash"))
    with pytest.raises(RuntimeError) as excinfo:
        cli._steer("x", "hello")
    msg = str(excinfo.value)
    assert "\x1b" not in msg, "escape byte leaked into operator-facing error"
    assert "pwned" not in msg
    assert "line2" in msg  # legit content survives sanitization
