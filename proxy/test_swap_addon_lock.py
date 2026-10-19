"""Symlink-plant hardening for proxy/swap_addon.py's `_summons_locked`
(issue #1755).

The lock sidecar opens with O_NOFOLLOW: a pre-planted symlink at
`<path>.lock` fails loud as OSError (ELOOP) instead of silently moving
the flock onto the plant target (lock-desync / lock-DoS). The mechanics
are deliberately identical to confirm/push.py's `_locked` (see that
module's docstring); this file pins the addon copy independently.

Run from the repo root: python3 -m pytest proxy/test_swap_addon_lock.py -q
"""
import errno
import fcntl
import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swap_addon as sa


def test_summons_locked_rejects_planted_symlink(tmp_path):
    target = tmp_path / "plant-target.txt"
    target.write_text("not the lock")
    os.symlink(target, tmp_path / "journal.json.lock")
    try:
        with sa._summons_locked(str(tmp_path / "journal.json")):
            pass
    except OSError as exc:
        assert exc.errno == errno.ELOOP, exc
    else:
        raise AssertionError("planted symlink at the lock path did not "
                             "fail loud (expected ELOOP)")
    assert target.read_text() == "not the lock"


def test_summons_locked_normal_path_excludes_and_creates_0600(tmp_path):
    journal = tmp_path / "journal.json"
    journal.write_text("[]")
    with sa._summons_locked(str(journal)):
        lock_path = tmp_path / "journal.json.lock"
        assert not os.path.islink(lock_path)
        assert stat.S_IMODE(os.stat(lock_path).st_mode) == 0o600
        probe = os.open(str(lock_path), os.O_RDWR)
        try:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError("second exclusive flock succeeded "
                                     "while _summons_locked holds the lock")
        finally:
            os.close(probe)
    probe = os.open(str(tmp_path / "journal.json.lock"), os.O_RDWR)
    try:
        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(probe, fcntl.LOCK_UN)
    finally:
        os.close(probe)
