"""Tests for proxy/grant-writer (finding 60, 64).

The single writer for grants.json. Run with:
    python3 -m unittest proxy.test_grant_writer -v
"""
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

WRITER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "grant-writer")


class GrantWriterTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.grants_file = str(Path(self.tmp.name) / "grants.json")
        self.env = dict(os.environ)
        self.env["SWAP_GRANTS_FILE"] = self.grants_file
        # Audit log to temp file to avoid touching /home/swapd.
        self.env["SWAP_LOG_FILE"] = str(Path(self.tmp.name) / "audit.log")

    def tearDown(self):
        self.tmp.cleanup()

    def run_writer(self, *args):
        return subprocess.run(
            [sys.executable, WRITER] + list(args),
            capture_output=True, text=True, timeout=15, env=self.env)

    def read_grants(self):
        with open(self.grants_file) as f:
            return json.load(f).get("grants", [])

    def test_add_and_list(self):
        """grant-writer add mints a grant; list shows it."""
        r = self.run_writer(
            "add", "--credential", "github", "--host", "github.com",
            "--method", "POST", "--path-prefix", "/gists",
            "--approval-id", "test123", "--job", "job1")
        self.assertEqual(r.returncode, 0, r.stderr)
        grants = self.read_grants()
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0]["credential"], "github")
        self.assertEqual(grants[0]["approval_id"], "test123")

    def test_64_reject_null_tuple(self):
        """Finding 64: refuse to mint unless credential, host, method
        are present. This is the null-grant from the box."""
        # Missing credential.
        r = self.run_writer(
            "add", "--credential", "", "--host", "github.com",
            "--method", "POST", "--approval-id", "null1")
        self.assertNotEqual(r.returncode, 0)
        # Missing host.
        r = self.run_writer(
            "add", "--credential", "github", "--host", "",
            "--method", "POST", "--approval-id", "null2")
        self.assertNotEqual(r.returncode, 0)
        # Missing method.
        r = self.run_writer(
            "add", "--credential", "github", "--host", "github.com",
            "--method", "", "--approval-id", "null3")
        self.assertNotEqual(r.returncode, 0)
        # No grants should have been minted.
        # (File may not exist if no successful writes.)
        if os.path.exists(self.grants_file):
            self.assertEqual(self.read_grants(), [])

    def test_revoke_by_job(self):
        """grant-writer revoke removes grants for a job."""
        self.run_writer(
            "add", "--credential", "github", "--host", "github.com",
            "--method", "POST", "--approval-id", "r1", "--job", "jobA")
        self.run_writer(
            "add", "--credential", "github", "--host", "github.com",
            "--method", "GET", "--approval-id", "r2", "--job", "jobB")
        r = self.run_writer("revoke", "--job", "jobA")
        self.assertEqual(r.returncode, 0, r.stderr)
        grants = self.read_grants()
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0]["job"], "jobB")

    def test_reaped_grants_do_not_resurrect(self):
        """Finding 56: expired grants are reaped and do not come back."""
        # Add a grant with a very short TTL, then wait for expiry.
        # Instead of waiting, we write an expired grant directly and
        # verify the writer reaps it on the next write.
        expired = {
            "credential": "github",
            "host": "github.com",
            "method": "POST",
            "path_prefix": "/",
            "scope": "",
            "expires": "2020-01-01T00:00:00+00:00",
            "approval_id": "expired1",
            "job": "",
        }
        with open(self.grants_file, "w") as f:
            json.dump({"grants": [expired]}, f)
        # A new add should reap the expired one.
        self.run_writer(
            "add", "--credential", "github", "--host", "github.com",
            "--method", "GET", "--approval-id", "fresh1")
        grants = self.read_grants()
        ids = [g["approval_id"] for g in grants]
        self.assertNotIn("expired1", ids)
        self.assertIn("fresh1", ids)

    def test_duplicate_approval_id_not_double_minted(self):
        """Same approval_id twice does not create two grants."""
        for _ in range(2):
            self.run_writer(
                "add", "--credential", "github", "--host", "github.com",
                "--method", "POST", "--approval-id", "dup1")
        grants = self.read_grants()
        self.assertEqual(len(grants), 1)

    # --- 68: dedicated lock file ---------------------------------------

    def _lock_path(self):
        return self.grants_file + ".lock"

    def _add_args(self, aid):
        return ("add", "--credential", "github", "--host", "github.com",
                "--method", "POST", "--approval-id", aid)

    def test_68_lock_blocks_second_writer(self):
        """Finding 68: the lock is a dedicated file that is never
        replaced. Hold it artificially in this process; a second writer
        must block until it is released. With the old inode-replaced
        lock the second writer would proceed (it locked a different
        inode) and this test would fail."""
        fd = os.open(self._lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        results = []
        try:
            t = threading.Thread(
                target=lambda: results.append(
                    self.run_writer(*self._add_args("locked1"))))
            t.start()
            t.join(timeout=5)
            self.assertTrue(t.is_alive(),
                            "second writer did not block on the lock file")
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        t.join(timeout=15)
        self.assertFalse(t.is_alive(), "second writer never finished")
        self.assertEqual(results[0].returncode, 0, results[0].stderr)
        grants = self.read_grants()
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0]["approval_id"], "locked1")

    def test_68_two_writers_no_loss(self):
        """Finding 68: two writers racing adds — both grants survive.
        This is the lost-grant scenario from the finding: one writer's
        rename discarding the other's grant."""
        start = threading.Barrier(2)
        codes = [None, None]

        def writer(i, aid):
            start.wait()
            r = self.run_writer(*self._add_args(aid))
            codes[i] = r.returncode

        threads = [threading.Thread(target=writer, args=(i, aid))
                   for i, aid in enumerate(("race1", "race2"))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual(codes, [0, 0])
        ids = sorted(g["approval_id"] for g in self.read_grants())
        self.assertEqual(ids, ["race1", "race2"])


if __name__ == "__main__":
    unittest.main()
