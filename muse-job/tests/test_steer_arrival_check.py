"""Regression tests for issue #12 item L9.

The steer delivery check declared "delivered" when the input box no longer
held the steer needle -- but a box the paste never reached is equally clear
of it, so a silently failed paste read as a delivery that never happened.
The fix verifies arrival (the needle must be seen in the box at least once)
before the box going clear can count as delivered.
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
    mod = load_script("muse_job_cli_steertest", CLI_PATH)
    monkeypatch.setattr(mod, "job_dir", lambda slug: str(tmp_path))
    monkeypatch.setattr(mod, "time", _NoSleepTime(mod.time))
    monkeypatch.setattr(mod, "_wait_live_tui",
                        lambda slug, timeout=30: ("pane0", "muse"))
    monkeypatch.setattr(mod, "tmux_alive", lambda slug: True)
    monkeypatch.setattr(mod, "_pane_shows_live_tui", lambda pane, cmd: True)
    return mod


class _NoSleepTime:
    """time module facade with sleep() neutralized (speeds the retry loop)."""

    def __init__(self, real_time):
        self._t = real_time

    def __getattr__(self, name):
        if name == "sleep":
            return lambda s: None
        return getattr(self._t, name)


class _RunResult:
    stdout = b""


def _box_pane(text):
    # A live-TUI pane whose input box holds `text` (last ❯ line).
    return "transcript line one\ntranscript line two\n❯ %s\n" % text


@pytest.fixture()
def run_calls():
    return []


def _install(cli, monkeypatch, run_calls, captures):
    """Script _capture_pane_state from a queue; record every run() call."""
    it = iter(captures)

    def fake_capture(target):
        try:
            return next(it)
        except StopIteration:
            return captures[-1]

    monkeypatch.setattr(cli, "_capture_pane_state", fake_capture)

    def fake_run(*a, **k):
        run_calls.append(a)
        return _RunResult()

    monkeypatch.setattr(cli, "run", fake_run)


def _enter_sent(run_calls):
    return any("send-keys" in a and "Enter" in a for a in run_calls)


def test_never_arrived_fails_closed(cli, monkeypatch, run_calls):
    # The paste never lands in the box: an empty box must NOT read as
    # delivered -- and no Enter may go out for text that never arrived.
    empty = (_box_pane(""), "muse")
    _install(cli, monkeypatch, run_calls, [empty, empty])
    assert cli._steer("s", "hello world", verify=True) is False
    assert not _enter_sent(run_calls), "Enter sent for un-arrived text"


def test_arrival_then_clearance_reports_delivered(cli, monkeypatch, run_calls):
    # Normal path: needle seen in the box, then the box clears -> delivered.
    # (The first capture is _steer's pre-paste TOCTOU re-check.)
    full = (_box_pane("hello world"), "muse")
    clear = (_box_pane(""), "muse")
    _install(cli, monkeypatch, run_calls, [full, full, clear])
    assert cli._steer("s", "hello world", verify=True) is True
    assert _enter_sent(run_calls)


def test_late_arrival_still_counts(cli, monkeypatch, run_calls):
    # The TUI can still be rendering the paste on the first post-paste
    # capture: one more look before failing closed.
    empty = (_box_pane(""), "muse")
    full = (_box_pane("hello world"), "muse")
    clear = (_box_pane(""), "muse")
    _install(cli, monkeypatch, run_calls, [empty, empty, full, clear])
    assert cli._steer("s", "hello world", verify=True) is True


def test_verify_false_skips_arrival_check(cli, monkeypatch, run_calls):
    # Unverified steers keep the old behavior: Enter goes out, no check.
    empty = (_box_pane(""), "muse")
    _install(cli, monkeypatch, run_calls, [empty])
    assert cli._steer("s", "hello world", verify=False) is True
    assert _enter_sent(run_calls)
