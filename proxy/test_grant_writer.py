"""Tests for proxy/grant-writer (finding 60, 64).

The single writer for grants.json. Run with:
    python3 -m unittest proxy.test_grant_writer -v
"""
import json
import os
import subprocess
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
