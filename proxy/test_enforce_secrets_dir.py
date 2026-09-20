"""Tests for proxy/enforce_secrets_dir.py (issue #91).

All hermetic: scratch tmpdirs only, no root, no /home/swapd. fchown to the
*current* uid/gid is unprivileged-legal, so the owner is monkeypatched to
the running user via pwd.getpwnam.
"""
import contextlib
import io
import os
import pwd
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import enforce_secrets_dir as esd


def _self_user():
    me = pwd.getpwuid(os.getuid())
    fake = mock.Mock()
    fake.pw_uid = me.pw_uid
    fake.pw_gid = me.pw_gid
    return me.pw_name, fake


class TestEnforceSecretsDir(unittest.TestCase):
    def _run(self, path, owner=None, mode=0o700):
        name, fake = _self_user()
        if owner is None:
            owner = name
        with mock.patch.object(pwd, "getpwnam", return_value=fake):
            return esd.enforce(str(path), owner=owner, mode=mode)

    def test_repairs_0755_to_0700_and_warns(self):
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o755)
            name, _ = _self_user()
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                before, after = self._run(d)
            self.assertEqual(before, "%s:755" % name)
            self.assertEqual(after, "%s:700" % name)
            self.assertEqual(stat.S_IMODE(os.stat(d).st_mode), 0o700)
            self.assertIn("repaired", buf.getvalue())

    def test_already_correct_is_silent(self):
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o700)
            name, _ = _self_user()
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                before, after = self._run(d)
            self.assertEqual((before, after), ("%s:700" % name,) * 2)
            self.assertEqual(buf.getvalue(), "")

    def test_symlink_to_dir_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "real"
            target.mkdir()
            os.chmod(target, 0o755)
            link = Path(d) / "link"
            link.symlink_to(target)
            with self.assertRaises(SystemExit) as cm:
                self._run(link)
            self.assertEqual(cm.exception.code, 1)
            # Target untouched: the refusal must not chown/chmod through.
            self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o755)

    def test_symlink_to_outside_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as d, \
                tempfile.TemporaryDirectory() as outside:
            os.chmod(outside, 0o755)
            link = Path(d) / "link"
            link.symlink_to(outside)
            with self.assertRaises(SystemExit):
                self._run(link)
            self.assertEqual(stat.S_IMODE(os.stat(outside).st_mode), 0o755)

    def test_regular_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "not-a-dir"
            f.write_text("x")
            with self.assertRaises(SystemExit) as cm:
                self._run(f)
            self.assertEqual(cm.exception.code, 1)

    def test_dangling_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            link = Path(d) / "dangling"
            link.symlink_to(Path(d) / "no-such-target")
            with self.assertRaises(SystemExit):
                self._run(link)


if __name__ == "__main__":
    unittest.main()
