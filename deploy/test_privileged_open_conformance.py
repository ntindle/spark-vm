"""Discipline-conformance test for the privileged-read pair (issue #453).

Convergence decision (2026-09-26, security turn): JUSTIFY the duplicate,
pin it with this test. proxy/privileged_read.py (fail-closed refusal) and
deploy/extra_inputs_hash_read.py (always-exit-0 digest states) deliberately
do NOT share an import:

1. Protocol divergence: privileged_read refuses (SystemExit 2) on symlink /
   hardlink / non-regular / oversize. The hash reader must never abort the
   deploy tick -- every one of those is a legitimate digest *state*
   (nonregular/unreadable/missing), and a >cap file hashes a size-folded
   capped prefix so post-cap growth still flips the digest (issue #302's
   whole purpose: rotation detection). Routing the reader through
   privileged_read would either abort ticks on refused states or need
   SystemExit-catching that re-implements the policy anyway.
2. Deployment divergence: the hash reader is installed standalone into
   $UPDATER_STATE_DIR/bin next to auto-deploy.sh (0644), with a fail-loud
   stale-install check on that one file. proxy/privileged_read.py is not
   installed there; making the reader import it would add a second
   installed file, a second stale-check, and import-resolution surface in
   a root-run file -- for ~12 shared lines of os.open/fstat gates.

What IS shared -- the atomic-open discipline (O_RDONLY | O_NOFOLLOW |
O_NONBLOCK, fstat-before-read, S_ISREG gate, nlink>1 refusal) -- is pinned
here: both implementations classify the hostile-fixture matrix identically
on the shared subset, and the two deliberate divergences (oversize,
unreadable-EACCES) are asserted as contracts below, not as drift.
"""
import contextlib
import io
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROXY_DIR = Path(__file__).resolve().parent.parent / "proxy"
DEPLOY_DIR = Path(__file__).resolve().parent
HASH_READ = DEPLOY_DIR / "extra_inputs_hash_read.py"

sys.path.insert(0, str(PROXY_DIR))
import privileged_read as pr  # noqa: E402

CAP = 4096
_HEX64 = re.compile(r"[0-9a-f]{64}")


class _MissingSentinel(Exception):
    pass


def _classify_privileged_read(path):
    """Run pr.privileged_read and return (outcome, detail).

    outcome is one of: ok / refuse / missing / reraise.
    """
    try:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            data = pr.privileged_read(
                str(path),
                lambda: (_ for _ in ()).throw(_MissingSentinel()),
                max_bytes=CAP)
    except _MissingSentinel:
        return ("missing", None)
    except SystemExit as e:
        return ("refuse", (e.code, err.getvalue()))
    except OSError as e:
        return ("reraise", e)
    return ("ok", data)


def _run_hash_reader(path):
    """Invoke extra_inputs_hash_read.py; return (rc, stdout_line)."""
    r = subprocess.run(
        [sys.executable, str(HASH_READ), str(path), str(CAP)],
        capture_output=True, text=True, timeout=30)
    return (r.returncode, r.stdout)


class TestPrivilegedOpenConformance(unittest.TestCase):
    def _fixture_dir(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return Path(d.name)

    def _hash_line(self, path):
        rc, out = _run_hash_reader(path)
        self.assertEqual(rc, 0, "hash reader must always exit 0")
        # Protocol: one line on stdout, always.
        self.assertEqual(out.count("\n"), 1)
        return out.rstrip("\n")

    def test_regular_file(self):
        d = self._fixture_dir()
        p = d / "ok.txt"
        p.write_bytes(b"payload\n")
        outcome, detail = _classify_privileged_read(p)
        self.assertEqual(outcome, "ok")
        self.assertEqual(detail, b"payload\n")
        line = self._hash_line(p)
        self.assertTrue(_HEX64.fullmatch(line),
                        "regular file must hash to a 64-hex digest")

    def test_live_symlink(self):
        d = self._fixture_dir()
        target = d / "target.txt"
        target.write_text("precious\n")
        link = d / "link.txt"
        link.symlink_to(target)
        outcome, (code, err) = _classify_privileged_read(link)
        self.assertEqual(outcome, "refuse")
        self.assertEqual(code, 2)
        self.assertIn("symlink", err)
        self.assertEqual(self._hash_line(link), "nonregular")

    def test_dangling_symlink(self):
        d = self._fixture_dir()
        link = d / "dangling.txt"
        link.symlink_to(d / "absent.txt")
        outcome, (code, err) = _classify_privileged_read(link)
        self.assertEqual(outcome, "refuse")
        self.assertEqual(code, 2)
        self.assertIn("symlink", err)
        self.assertEqual(self._hash_line(link), "nonregular")

    def test_fifo(self):
        d = self._fixture_dir()
        fifo = d / "pipe"
        os.mkfifo(fifo)
        outcome, (code, err) = _classify_privileged_read(fifo)
        self.assertEqual(outcome, "refuse")
        self.assertEqual(code, 2)
        self.assertIn("not a regular file", err)
        self.assertEqual(self._hash_line(fifo), "nonregular")

    def test_directory(self):
        d = self._fixture_dir()
        sub = d / "subdir"
        sub.mkdir()
        outcome, (code, err) = _classify_privileged_read(sub)
        self.assertEqual(outcome, "refuse")
        self.assertEqual(code, 2)
        self.assertIn("not a regular file", err)
        self.assertEqual(self._hash_line(sub), "nonregular")

    def test_hardlink(self):
        d = self._fixture_dir()
        src = d / "src.txt"
        src.write_bytes(b"hardlink target\n")
        link = d / "hard.txt"
        os.link(src, link)
        outcome, (code, err) = _classify_privileged_read(link)
        self.assertEqual(outcome, "refuse")
        self.assertEqual(code, 2)
        self.assertIn("hardlink", err)
        self.assertEqual(self._hash_line(link), "nonregular")

    def test_missing(self):
        d = self._fixture_dir()
        p = d / "absent.txt"
        outcome, _ = _classify_privileged_read(p)
        self.assertEqual(outcome, "missing")
        self.assertEqual(self._hash_line(p), "missing")

    def test_oversize_is_documented_divergence(self):
        # Deliberate divergence, NOT drift: privileged_read refuses
        # (>cap into a privileged process); the hash reader must never
        # abort the tick, so it digests a size-folded capped prefix.
        d = self._fixture_dir()
        big = d / "big.bin"
        big.write_bytes(b"x" * (CAP + 100))
        outcome, (code, err) = _classify_privileged_read(big)
        self.assertEqual(outcome, "refuse")
        self.assertEqual(code, 2)
        self.assertIn("cap", err)
        line = self._hash_line(big)
        self.assertTrue(_HEX64.fullmatch(line),
                        "oversize file must still hash as a digest state")
        # Growth past the cap must flip the digest (rotation detection,
        # issue #302) even though only a prefix is read.
        prefix_only = d / "prefix.bin"
        prefix_only.write_bytes(b"x" * CAP)
        self.assertNotEqual(line, self._hash_line(prefix_only))

    def test_unreadable_is_documented_divergence(self):
        # Deliberate divergence, NOT drift: privileged_read re-raises the
        # OSError (fail loud in a privileged process); the hash reader
        # folds it into the "unreadable" digest state.
        if os.geteuid() == 0:
            self.skipTest("chmod-000 is readable by root")
        d = self._fixture_dir()
        p = d / "locked.txt"
        p.write_bytes(b"secret\n")
        os.chmod(p, 0)
        self.addCleanup(os.chmod, p, 0o644)
        outcome, detail = _classify_privileged_read(p)
        self.assertEqual(outcome, "reraise")
        self.assertIsInstance(detail, OSError)
        self.assertEqual(self._hash_line(p), "unreadable")


if __name__ == "__main__":
    unittest.main()
