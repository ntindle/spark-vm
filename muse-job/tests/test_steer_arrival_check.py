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


def _echo_pane(first60):
    # A pane whose last ❯ line holds only the message's first-line
    # prefix: a stale agent echo of an earlier steer sharing that
    # prefix, NOT the new message in the input box.
    return "agent transcript line\n❯ %s\n" % first60


def test_stale_echo_of_first_line_does_not_count_as_arrival(
        cli, monkeypatch, run_calls):
    # Issue #12 L9: the old 60-char first-line needle read a stale echo
    # as arrival. The new needle also requires the last-line suffix, so
    # an echo of only the first line must NOT count -- and no Enter may
    # go out for text that never arrived.
    message = "x" * 60 + "\nthe real last line"
    echo = (_echo_pane("x" * 60), "muse")
    _install(cli, monkeypatch, run_calls, [echo, echo])
    assert cli._steer("s", message, verify=True) is False
    assert not _enter_sent(run_calls), "Enter sent for echoed-not-arrived text"


def test_mid_transcript_echo_does_not_spoof(cli, monkeypatch, run_calls):
    # An echo sitting mid-transcript (above the real, empty box) is not
    # in the box region, so it cannot satisfy the arrival check even when
    # it reproduces the whole first line.
    message = "do the thing"
    pane = ("transcript\n❯ do the thing\n❯ \n", "muse")
    _install(cli, monkeypatch, run_calls, [pane, pane])
    assert cli._steer("s", message, verify=True) is False
    assert not _enter_sent(run_calls)


def _wrapped_box_pane(first, continuation):
    # Input box with a wrapped continuation row (no ❯ prefix on it).
    return "transcript\n❯ %s\n%s\n" % (first, continuation)


def test_multiline_message_matches_across_wrapped_rows(
        cli, monkeypatch, run_calls):
    # The last-line suffix may live on a wrapped continuation row: both
    # needle parts must be found across the box region for arrival to
    # count, and clearance afterwards still reports delivered.
    message = "first line here\nsecond row wrapped text"
    full = (_wrapped_box_pane("first line here", "second row wrapped text"),
            "muse")
    clear = (_box_pane(""), "muse")
    _install(cli, monkeypatch, run_calls, [full, full, clear])
    assert cli._steer("s", message, verify=True) is True
    assert _enter_sent(run_calls)


def test_single_line_needle_still_two_sided(cli, monkeypatch, run_calls):
    # Single-line messages: first and last parts are the same line, so
    # the old behavior is preserved end to end.
    full = (_box_pane("hello world"), "muse")
    clear = (_box_pane(""), "muse")
    _install(cli, monkeypatch, run_calls, [full, full, clear])
    assert cli._steer("s", "hello world", verify=True) is True
    assert _enter_sent(run_calls)


def test_blank_message_skips_arrival_check(cli, monkeypatch, run_calls):
    # ("", "") needle: the arrival check is skipped and the steer flows,
    # exactly as the old empty-string needle behaved.
    empty = (_box_pane(""), "muse")
    _install(cli, monkeypatch, run_calls, [empty, empty])
    assert cli._steer("s", "   \n  ", verify=True) is True
    assert _enter_sent(run_calls)


_ALPHABET62 = ("abcdefghijklmnopqrstuvwxyz"
               "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
               "0123456789")


def _distinct(n, seed=7):
    # 62-char-cycle string: no 60-char window repeats within a single
    # physical row, so a wrap-spanning needle part provably cannot hide
    # inside one row (a 26-char cycle would alias across the boundary).
    return "".join(_ALPHABET62[(seed + i) % 62] for i in range(n))


def test_long_last_line_split_across_wrap_still_matches(
        cli, monkeypatch, run_calls):
    # Engineering round-1 blocker: capture-pane -p splits a long pasted
    # line across physical rows. A needle part straddling the wrap
    # boundary must still count as present — matching runs on the
    # de-wrapped box region. (80-col pane: the 90-char last line wraps
    # after 78 chars; the 60-char suffix provably spans the boundary
    # because the chars are distinct.)
    last = _distinct(90)
    message = "short first\n" + last
    wrapped = "❯ short first\n" + last[:78] + "\n" + last[78:] + "\n"
    full = ("transcript\n" + wrapped, "muse")
    clear = (_box_pane(""), "muse")
    _install(cli, monkeypatch, run_calls, [full, full, clear])
    assert cli._steer("s", message, verify=True) is True
    assert _enter_sent(run_calls)


def test_long_single_line_split_across_wrap_still_matches(
        cli, monkeypatch, run_calls):
    # Same wrap case for a single long line: both needle parts straddle
    # the boundary and must still match.
    message = _distinct(100, seed=13)
    wrapped = "❯ " + message[:76] + "\n" + message[76:] + "\n"
    full = ("transcript\n" + wrapped, "muse")
    clear = (_box_pane(""), "muse")
    _install(cli, monkeypatch, run_calls, [full, full, clear])
    assert cli._steer("s", message, verify=True) is True
    assert _enter_sent(run_calls)
