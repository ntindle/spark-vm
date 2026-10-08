"""Tests for proxy/enforce_pending_dir.py (issue #1167).

All hermetic: scratch tmpdirs only, no root, no /home/swapd. fchown to
the *current* uid/gid is unprivileged-legal, so owner/group are
monkeypatched to the running user via pwd.getpwnam / grp.getgrnam.
"""
import contextlib
import grp
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
import enforce_pending_dir as epd


def _self_ids():
    me = pwd.getpwuid(os.getuid())
    g = grp.getgrgid(os.getgid())
    user = mock.Mock()
    user.pw_uid = me.pw_uid
    user.pw_gid = me.pw_gid
    group = mock.Mock()
    group.gr_gid = g.gr_gid
    group.gr_name = g.gr_name
    return me.pw_name, g.gr_name, user, group


class TestEnforcePendingDir(unittest.TestCase):
    def _run(self, path, create=False, mode="2770"):
        name, gname, fake_user, fake_group = _self_ids()
        with mock.patch.object(pwd, "getpwnam", return_value=fake_user), \
             mock.patch.object(grp, "getgrnam", return_value=fake_group), \
             mock.patch.object(grp, "getgrgid", return_value=fake_group):
            return epd.enforce(str(path), owner=name, group=gname,
                               mode=mode, create=create)

    def test_create_missing_leaf_and_ancestors(self):
        with tempfile.TemporaryDirectory() as d:
            leaf = Path(d) / "approvals" / "pending"
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                before, after = self._run(leaf, create=True)
            st = os.stat(leaf)
            self.assertTrue(stat.S_ISDIR(st.st_mode))
            # Non-vacuous: the setgid bit must actually be set (mkdir
            # drops S_ISGID — the whole point of the deploy step).
            self.assertEqual(stat.S_IMODE(st.st_mode), 0o2770)
            self.assertEqual((st.st_uid, st.st_gid),
                             (os.getuid(), os.getgid()))
            self.assertIn("repaired", buf.getvalue())

    def test_repairs_wrong_mode_to_2770_and_warns(self):
        with tempfile.TemporaryDirectory() as d:
            leaf = Path(d) / "pending"
            leaf.mkdir()
            os.chmod(leaf, 0o755)
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                before, after = self._run(leaf)
            self.assertEqual(stat.S_IMODE(os.stat(leaf).st_mode), 0o2770)
            self.assertIn("repaired", buf.getvalue())

    def test_already_correct_is_silent(self):
        with tempfile.TemporaryDirectory() as d:
            leaf = Path(d) / "pending"
            leaf.mkdir()
            os.chmod(leaf, 0o2770)  # mkdir() is umask-masked; pin exactly
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                before, after = self._run(leaf)
            self.assertEqual(before, after)
            self.assertEqual(buf.getvalue(), "")

    def test_idempotent_second_run(self):
        with tempfile.TemporaryDirectory() as d:
            leaf = Path(d) / "pending"
            self._run(leaf, create=True)
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                before, after = self._run(leaf)
            self.assertEqual(before, after)
            self.assertEqual(buf.getvalue(), "")
            self.assertEqual(stat.S_IMODE(os.stat(leaf).st_mode), 0o2770)

    def test_symlink_leaf_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "real"
            target.mkdir()
            os.chmod(target, 0o755)
            link = Path(d) / "pending"
            link.symlink_to(target)
            with self.assertRaises(SystemExit) as cm:
                self._run(link)
            self.assertEqual(cm.exception.code, 1)
            # Target untouched: the refusal must not chown/chmod through.
            self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o755)

    def test_symlink_ancestor_is_refused(self):
        with tempfile.TemporaryDirectory() as d, \
                tempfile.TemporaryDirectory() as outside:
            link = Path(d) / "approvals"
            link.symlink_to(outside)
            leaf = link / "pending"
            with self.assertRaises(SystemExit) as cm:
                self._run(leaf, create=True)
            self.assertEqual(cm.exception.code, 1)
            # Nothing created through the symlinked ancestor.
            self.assertFalse((Path(outside) / "pending").exists())

    def test_missing_leaf_without_create_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as cm:
                self._run(Path(d) / "pending")
            self.assertEqual(cm.exception.code, 1)

    def test_non_absolute_path_is_refused(self):
        with self.assertRaises(SystemExit):
            self._run("relative/pending", create=True)

    def test_file_at_leaf_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            leaf = Path(d) / "pending"
            leaf.write_text("not a dir")
            with self.assertRaises(SystemExit):
                self._run(leaf, create=True)

    def test_unknown_group_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            leaf = Path(d) / "pending"
            leaf.mkdir()
            name, _, fake_user, _ = _self_ids()
            with mock.patch.object(pwd, "getpwnam",
                                   return_value=fake_user), \
                 mock.patch.object(grp, "getgrnam",
                                   side_effect=KeyError("nope")):
                with self.assertRaises(SystemExit) as cm:
                    epd.enforce(str(leaf), owner=name, group="nope",
                                mode="2770", create=False)
            self.assertEqual(cm.exception.code, 1)

    def test_bad_mode_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            leaf = Path(d) / "pending"
            leaf.mkdir()
            with self.assertRaises(SystemExit):
                self._run(leaf, mode="banana")


if __name__ == "__main__":
    unittest.main()
