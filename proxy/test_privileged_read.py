"""Tests for proxy/privileged_read.py (issues #144/#299/#300/#372/#413).

All hermetic: scratch tmpdirs only, no root, no /home/swapd. Exercises the
shared open discipline that build_ca_bundle.py (issue #372) and
safe_install.py --src (issue #413) both route through.
"""
import contextlib
import io
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import privileged_read as pr


class TestPrivilegedRead(unittest.TestCase):
    def _read(self, path, **kw):
        missing = kw.pop("on_missing",
                         lambda: (_ for _ in ()).throw(
                             SystemExit(99)))  # pragma: no cover
        return pr.privileged_read(str(path), missing, **kw)

    def test_happy_path_returns_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ok.txt"
            p.write_bytes(b"payload\n")
            self.assertEqual(self._read(p), b"payload\n")

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "target.txt"
            target.write_text("precious\n")
            link = Path(d) / "link.txt"
            link.symlink_to(target)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as cm:
                    self._read(link)
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("symlink", err.getvalue())

    def test_dangling_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            link = Path(d) / "dangling.txt"
            link.symlink_to(Path(d) / "absent.txt")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as cm:
                    self._read(link)
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("symlink", err.getvalue())

    def test_hardlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.txt"
            src.write_bytes(b"hardlink target\n")
            link = Path(d) / "hard.txt"
            os.link(src, link)
            self.assertEqual(os.stat(link).st_nlink, 2)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as cm:
                    self._read(link)
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("hardlink", err.getvalue())

    def test_fifo_refused_without_blocking(self):
        # O_NONBLOCK is the point: this must refuse, not hang forever.
        with tempfile.TemporaryDirectory() as d:
            fifo = Path(d) / "pipe"
            os.mkfifo(fifo)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as cm:
                    self._read(fifo)
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("not a regular file", err.getvalue())

    def test_directory_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as cm:
                    self._read(Path(d))
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("not a regular file", err.getvalue())

    def test_oversize_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "big.bin"
            p.write_bytes(b"x" * 64)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as cm:
                    pr.privileged_read(
                        str(p), lambda: None, max_bytes=63)
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("cap", err.getvalue())

    def test_missing_invokes_on_missing(self):
        seen = []
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as cm:
                pr.privileged_read(
                    str(Path(d) / "absent.txt"),
                    lambda: (seen.append(True),
                             (_ for _ in ()).throw(SystemExit(3)))[1])
        self.assertEqual(cm.exception.code, 3)
        self.assertTrue(seen)

    def test_non_raising_on_missing_fails_closed(self):
        # A non-raising on_missing is a caller bug: the discipline must not
        # fall through to an unbound-fd NameError.
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    pr.privileged_read(
                        str(Path(d) / "absent.txt"), lambda: None)
            self.assertEqual(cm.exception.code, 1)

    def test_exact_cap_size_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "exact.bin"
            p.write_bytes(b"y" * 64)
            self.assertEqual(
                pr.privileged_read(str(p), lambda: None, max_bytes=64),
                b"y" * 64)


if __name__ == "__main__":
    unittest.main()
