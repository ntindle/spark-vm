"""Tests for `cred-registry-set set-with-hosts` (#146, #116).

Atomic register + host binding: every argument is validated before any
mutation, and the whole operation lands in one locked read-modify-write,
so a mid-loop writer failure can never leave a credential registered
with only a prefix of its intended hosts.

All hermetic: the writer's CRED_REGISTRY_FILE / CRED_REGISTRY_LOCK env
overrides point it at a scratch tmpdir. No sudo, no swapd, no real store.
"""
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

WRITER = str(Path(__file__).resolve().parent / "cred-registry-set")


class SetWithHostsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = os.path.join(self.tmp.name, "credentials.json")
        self.lock = os.path.join(self.tmp.name, "credentials.json.lock")
        self.env = dict(os.environ, CRED_REGISTRY_FILE=self.reg,
                        CRED_REGISTRY_LOCK=self.lock)

    def tearDown(self):
        self.tmp.cleanup()

    def run_writer(self, *argv):
        return subprocess.run([WRITER] + list(argv), env=self.env,
                              capture_output=True, text=True, timeout=30)

    def read_reg(self):
        with open(self.reg, encoding="utf-8") as f:
            return json.load(f)

    def test_happy_path_registers_and_binds_all_hosts(self):
        p = self.run_writer("set-with-hosts", "gh", "access_token",
                            '"bearer_header"', "api.github.com",
                            ".example.com")
        self.assertEqual(p.returncode, 0, p.stderr)
        reg = self.read_reg()
        self.assertEqual(reg["gh"]["access_token"],
                         {"placement": "bearer_header"})
        self.assertEqual(reg["gh"]["allowed_hosts"],
                         ["api.github.com", ".example.com"])

    def test_dict_placement_and_host_union_are_idempotent(self):
        pjson = json.dumps({"custom_header": "X-Api-Key"})
        self.assertEqual(self.run_writer(
            "set-with-hosts", "gh", "access_token", pjson,
            "API.GITHUB.COM", "api.github.com").returncode, 0)
        reg = self.read_reg()
        # writer lowercases; the union dedupes after lowercasing
        self.assertEqual(reg["gh"]["allowed_hosts"], ["api.github.com"])
        self.assertEqual(reg["gh"]["access_token"]["placement"],
                         {"custom_header": "X-Api-Key"})
        # second call merges into the existing binding, no duplicates
        self.assertEqual(self.run_writer(
            "set-with-hosts", "gh", "access_token", pjson,
            "api.github.com", "other.io").returncode, 0)
        reg = self.read_reg()
        self.assertEqual(reg["gh"]["allowed_hosts"],
                         ["api.github.com", "other.io"])

    def test_zero_hosts_is_plain_register(self):
        p = self.run_writer("set-with-hosts", "gh", "access_token",
                            '"bearer_header"')
        self.assertEqual(p.returncode, 0, p.stderr)
        reg = self.read_reg()
        self.assertEqual(reg["gh"]["access_token"],
                         {"placement": "bearer_header"})
        self.assertEqual(reg["gh"]["allowed_hosts"], [])

    def test_invalid_host_leaves_registry_untouched(self):
        self.assertEqual(self.run_writer(
            "set", "gh", "access_token", '"bearer_header"').returncode, 0)
        before = self.read_reg()
        p = self.run_writer("set-with-hosts", "gh", "other_entry",
                            '"bearer_header"', "good.io", "bad_host!")
        self.assertNotEqual(p.returncode, 0)
        # atomicity: the failed call wrote nothing, not even the entry
        self.assertEqual(self.read_reg(), before)

    def test_invalid_placement_leaves_registry_untouched(self):
        self.assertEqual(self.run_writer(
            "set", "gh", "access_token", '"bearer_header"').returncode, 0)
        before = self.read_reg()
        p = self.run_writer("set-with-hosts", "gh", "access_token",
                            '{"evil": 1}', "good.io")
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(self.read_reg(), before)

    def test_reserved_entry_is_refused(self):
        p = self.run_writer("set-with-hosts", "gh", "allowed_hosts",
                            '"bearer_header"', "good.io")
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(os.path.exists(self.reg))

    def test_bad_name_is_refused(self):
        p = self.run_writer("set-with-hosts", "../x", "access_token",
                            '"bearer_header"', "good.io")
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(os.path.exists(self.reg))

    def test_concurrent_calls_do_not_lose_updates(self):
        # The single flock must serialize whole operations: N threads
        # each binding a distinct host must all land.
        def bind(i):
            return self.run_writer(
                "set-with-hosts", "gh", "access_token", '"bearer_header"',
                "host%d.io" % i).returncode

        results = []
        threads = [threading.Thread(target=lambda i=i: results.append(bind(i)))
                   for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results, [0] * 8)
        reg = self.read_reg()
        self.assertEqual(sorted(reg["gh"]["allowed_hosts"]),
                         sorted("host%d.io" % i for i in range(8)))

    def test_set_action_still_accepts_same_placement_grammar(self):
        # set and set-with-hosts share parse_placement: identical grammar.
        pjson = json.dumps({"query_param": "api_key"})
        self.assertEqual(self.run_writer(
            "set", "a", "e", pjson).returncode, 0)
        self.assertEqual(self.run_writer(
            "set-with-hosts", "b", "e", pjson).returncode, 0)
        self.assertEqual(self.read_reg()["a"]["e"]["placement"],
                         self.read_reg()["b"]["e"]["placement"])
        bad = self.run_writer("set", "c", "e", '"bogus"')
        bad2 = self.run_writer("set-with-hosts", "d", "e", '"bogus"')
        self.assertNotEqual(bad.returncode, 0)
        self.assertNotEqual(bad2.returncode, 0)


if __name__ == "__main__":
    unittest.main()
