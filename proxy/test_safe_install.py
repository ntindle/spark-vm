"""Tests for proxy/safe_install.py (deploy.sh symlink-following writes).

All hermetic: scratch tmpdirs only, no root, no /home/swapd. fchown to the
*current* uid/gid is unprivileged-legal, so the owner is monkeypatched to
the running user via pwd.getpwnam (same trick as test_enforce_secrets_dir.py).
"""
import io
import os
import pwd
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import safe_install as si

SCRIPT = str(Path(__file__).resolve().parent / "safe_install.py")


def _self_user():
    me = pwd.getpwuid(os.getuid())
    fake = mock.Mock()
    fake.pw_uid = me.pw_uid
    fake.pw_gid = me.pw_gid
    return me.pw_name, fake


class TestSafeInstall(unittest.TestCase):
    def _run(self, *args, **kwargs):
        name, fake = _self_user()
        kwargs.setdefault("owner", name)
        with mock.patch.object(pwd, "getpwnam", return_value=fake):
            return si.safe_install(*args, **kwargs)

    def test_write_creates_with_content_mode(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "new.txt"
            self._run(str(dest), content=b"hello\n", mode=0o640)
            self.assertEqual(dest.read_bytes(), b"hello\n")
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o640)

    def test_write_truncates_existing(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "f.txt"
            dest.write_text("old content that is longer")
            self._run(str(dest), content=b"new\n", mode=0o600)
            self.assertEqual(dest.read_bytes(), b"new\n")
            self.assertTrue(dest.is_file() and not dest.is_symlink())

    def test_symlink_is_refused_and_target_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "target.txt"
            target.write_text("precious\n")
            os.chmod(target, 0o644)
            link = Path(d) / "link.txt"
            link.symlink_to(target)
            with self.assertRaises(SystemExit) as cm:
                self._run(str(link), content=b"evil\n", mode=0o600)
            self.assertEqual(cm.exception.code, 2)
            # The write must not have gone through to the target.
            self.assertEqual(target.read_bytes(), b"precious\n")
            self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o644)
            self.assertTrue(link.is_symlink())

    def test_dangling_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            link = Path(d) / "dangling"
            link.symlink_to(Path(d) / "no-such-target")
            with self.assertRaises(SystemExit):
                self._run(str(link), content=b"x\n", mode=0o600)

    def test_create_only_does_not_clobber(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "grants.json"
            dest.write_text('{"grants": ["real"]}\n')
            os.chmod(dest, 0o644)
            result = self._run(str(dest), content=b'{"grants": []}\n',
                               create_only=True, mode=0o600)
            self.assertEqual(result, "enforced")
            # Content preserved, mode still enforced.
            self.assertEqual(dest.read_bytes(), b'{"grants": ["real"]}\n')
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o600)

    def test_create_only_creates_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "grants.json"
            result = self._run(str(dest), content=b'{"grants": []}\n',
                               create_only=True, mode=0o600)
            self.assertEqual(result, "created")
            self.assertEqual(dest.read_bytes(), b'{"grants": []}\n')
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o600)

    def test_enforce_only_mode(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "swap.log"
            dest.write_text("log line\n")
            os.chmod(dest, 0o644)
            result = self._run(str(dest), mode=0o600)
            self.assertEqual(result, "enforced")
            self.assertEqual(dest.read_bytes(), b"log line\n")
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o600)

    def test_enforce_only_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "target.log"
            target.write_text("log\n")
            os.chmod(target, 0o644)
            link = Path(d) / "link.log"
            link.symlink_to(target)
            with self.assertRaises(SystemExit):
                self._run(str(link), mode=0o600)
            self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o644)

    def test_cli_stdin_and_src(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "out.txt"
            r = subprocess.run(
                [sys.executable, SCRIPT, "--stdin", "--mode", "0600",
                 str(dest)],
                input=b"via stdin\n", capture_output=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            self.assertEqual(dest.read_bytes(), b"via stdin\n")

            src = Path(d) / "src.txt"
            src.write_text("via src\n")
            dest2 = Path(d) / "out2.txt"
            r = subprocess.run(
                [sys.executable, SCRIPT, "--src", str(src), "--mode", "0644",
                 str(dest2)], capture_output=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            self.assertEqual(dest2.read_bytes(), b"via src\n")
            self.assertEqual(stat.S_IMODE(os.stat(dest2).st_mode), 0o644)

    def test_cli_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "target.txt"
            target.write_text("precious\n")
            link = Path(d) / "link.txt"
            link.symlink_to(target)
            r = subprocess.run(
                [sys.executable, SCRIPT, "--stdin", str(link)],
                input=b"evil\n", capture_output=True, timeout=30)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(target.read_bytes(), b"precious\n")

    def test_cli_create_only(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "n.txt"
            r = subprocess.run(
                [sys.executable, SCRIPT, "--stdin", "--create-only",
                 "--mode", "0600", str(dest)],
                input=b"first\n", capture_output=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            r = subprocess.run(
                [sys.executable, SCRIPT, "--stdin", "--create-only",
                 "--mode", "0600", str(dest)],
                input=b"second\n", capture_output=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            self.assertEqual(dest.read_bytes(), b"first\n")


if __name__ == "__main__":
    unittest.main()
