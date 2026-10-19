"""Symlink-plant hardening for confirm/push.py's `_locked` (issue #1755).

The lock sidecar opens with O_NOFOLLOW: a pre-planted symlink at
`<path>.lock` fails loud as OSError (ELOOP) instead of silently moving
the flock onto the plant target (lock-desync / lock-DoS).

Run from the repo root: python3 -m pytest confirm/test_push_lock.py -q
"""
import errno
import fcntl
import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import push


def test_locked_rejects_planted_symlink(tmp_path):
    target = tmp_path / "plant-target.txt"
    target.write_text("not the lock")
    os.symlink(target, tmp_path / "store.json.lock")
    try:
        with push._locked(str(tmp_path / "store.json")):
            pass
    except OSError as exc:
        assert exc.errno == errno.ELOOP, exc
    else:
        raise AssertionError("planted symlink at the lock path did not "
                             "fail loud (expected ELOOP)")
    # The plant target is untouched: no flock was ever taken on it.
    assert target.read_text() == "not the lock"


def test_locked_normal_path_excludes_and_creates_0600(tmp_path):
    store = tmp_path / "store.json"
    store.write_text("{}")
    with push._locked(str(store)):
        lock_path = tmp_path / "store.json.lock"
        assert not os.path.islink(lock_path)
        assert stat.S_IMODE(os.stat(lock_path).st_mode) == 0o600
        # A second exclusive holder must not get in while we hold it.
        probe = os.open(str(lock_path), os.O_RDWR)
        try:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError("second exclusive flock succeeded "
                                     "while _locked holds the lock")
        finally:
            os.close(probe)
    # Lock released on exit: a fresh exclusive flock now succeeds.
    probe = os.open(str(tmp_path / "store.json.lock"), os.O_RDWR)
    try:
        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(probe, fcntl.LOCK_UN)
    finally:
        os.close(probe)
