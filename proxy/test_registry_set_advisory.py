"""Tests for the #87 advisory: loosening registry scoping is self-service.

Issue #87: host bindings, method/path limits, and scrub flags in the
credential registry are advisory for the same-uid operator (who holds
NOPASSWD cred-registry-set), not constraints. The verbs that LOOSEN
those controls -- clear-method-limit, clear-path-limit, set-scrub false
-- print a one-line stderr advisory. Tightening verbs stay quiet.

The advisory is informational only: exit codes, stdout confirmations,
and the registry writes are unchanged.

All hermetic: the writer's CRED_REGISTRY_FILE / CRED_REGISTRY_LOCK env
overrides point it at a scratch tmpdir. No sudo, no swapd, no real store.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

WRITER = str(Path(__file__).resolve().parent / "cred-registry-set")
ADVISORY_MARKER = "advisory:"


class AdvisoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = os.path.join(self.tmp.name, "credentials.json")
        self.lock = os.path.join(self.tmp.name, "credentials.json.lock")
        self.env = dict(os.environ, CRED_REGISTRY_FILE=self.reg,
                        CRED_REGISTRY_LOCK=self.lock)
        # set-scrub never creates: seed a credential with an entry first.
        p = self.run_writer("set", "gh", "access_token", '"bearer_header"')
        self.assertEqual(p.returncode, 0, p.stderr)

    def tearDown(self):
        self.tmp.cleanup()

    def run_writer(self, *argv):
        return subprocess.run([WRITER] + list(argv), env=self.env,
                              capture_output=True, text=True, timeout=30)

    def read_reg(self):
        with open(self.reg, encoding="utf-8") as f:
            return json.load(f)

    def test_clear_method_limit_advises_and_clears(self):
        self.assertEqual(
            self.run_writer("add-method", "gh", "GET").returncode, 0)
        p = self.run_writer("clear-method-limit", "gh")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(ADVISORY_MARKER, p.stderr)
        # behavior unchanged: limit gone, normal stdout confirmation
        self.assertNotIn("allowed_methods", self.read_reg()["gh"])
        self.assertIn("now unrestricted", p.stdout)

    def test_clear_path_limit_advises_and_clears(self):
        self.assertEqual(
            self.run_writer("add-path", "gh", "/repos").returncode, 0)
        p = self.run_writer("clear-path-limit", "gh")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(ADVISORY_MARKER, p.stderr)
        self.assertNotIn("allowed_paths", self.read_reg()["gh"])
        self.assertIn("now unrestricted", p.stdout)

    def test_set_scrub_false_advises_and_writes(self):
        p = self.run_writer("set-scrub", "gh", "access_token", "false")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(ADVISORY_MARKER, p.stderr)
        self.assertFalse(self.read_reg()["gh"]["access_token"]["scrub"])

    def test_tightening_verbs_stay_quiet(self):
        # add/remove-host, add/remove-method, add/remove-path, set-scrub
        # true all tighten (or are neutral) -- no advisory on stderr.
        quiet = [
            ("add-host", "gh", "api.github.com"),
            ("add-method", "gh", "GET"),
            ("remove-method", "gh", "GET"),
            ("add-path", "gh", "/repos"),
            ("remove-path", "gh", "/repos"),
            ("remove-host", "gh", "api.github.com"),
            ("set-scrub", "gh", "access_token", "true"),
        ]
        for argv in quiet:
            with self.subTest(argv=argv):
                p = self.run_writer(*argv)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertNotIn(ADVISORY_MARKER, p.stderr)

    def test_loosening_verbs_fail_quiet_on_missing_targets(self):
        # FOLLOW-adv4: the advisory fires only when the loosening actually
        # happened. On the fail-path (no such credential/entry) the writer
        # must fail WITHOUT the advisory -- an advisory on a no-op would be
        # noise that trains operators to ignore it.
        for argv in [
            ("clear-method-limit", "no-such-credential"),
            ("clear-path-limit", "no-such-credential"),
            ("set-scrub", "no-such-credential", "access_token", "false"),
            # Existing credential, missing entry: same contract.
            ("set-scrub", "gh", "no_such_entry", "false"),
        ]:
            with self.subTest(argv=argv):
                p = self.run_writer(*argv)
                self.assertNotEqual(p.returncode, 0, p.stderr)
                self.assertNotIn(ADVISORY_MARKER, p.stderr)

    def test_advisory_never_leaks_values(self):
        # The advisory is a fixed string; no credential/entry names or
        # values may appear in it.
        p = self.run_writer("clear-method-limit", "gh")
        for line in p.stderr.splitlines():
            if ADVISORY_MARKER in line:
                self.assertNotIn("gh", line)


if __name__ == "__main__":
    unittest.main()
