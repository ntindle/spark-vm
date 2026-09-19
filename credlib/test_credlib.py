"""Tests for credlib name validation (security sweep 2026-09-19).

Credential and entry names reach filesystem paths in fill_secret.py
(/home/swapd/secrets/<name>), so dynamic_credential_entry validates
them at the choke point. An unvalidated name ("../../etc/passwd",
"../.mitmproxy/mitmproxy-ca-key.pem") was a path-traversal read as
swapd. Run with:
    python3 -m unittest credlib.test_credlib -v   (from the repo root)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dynamic_credentials import (
    DynamicCredentialError,
    dynamic_credential_entry,
)
import fill_secret


class NameValidationTests(unittest.TestCase):

    def test_traversal_names_rejected(self):
        """Path-traversal names must never reach the filesystem."""
        for bad in ("../etc/passwd",
                    "../../etc/shadow",
                    "../.mitmproxy/mitmproxy-ca-key.pem",
                    "a/b",
                    "..",
                    ".",
                    "name;rm",
                    "name\ninjected",
                    "",
                    "x" * 65):
            with self.assertRaises(DynamicCredentialError, msg=bad):
                dynamic_credential_entry(bad)
            with self.assertRaises(DynamicCredentialError, msg=bad):
                dynamic_credential_entry("ok-name", entry_name=bad)

    def test_valid_names_still_resolve(self):
        """Legitimate names are unaffected; surrogate format unchanged."""
        e = dynamic_credential_entry("github", entry_name="access_token")
        self.assertEqual(e["surrogate"], "hsurr:github:access_token")
        e = dynamic_credential_entry("openai-api_key-2")
        self.assertEqual(e["surrogate"], "hsurr:openai-api_key-2:access_token")
        e = dynamic_credential_entry("a")
        self.assertEqual(e["surrogate"], "hsurr:a:access_token")

    def test_non_string_names_rejected(self):
        for bad in (None, 123, ["x"], {"n": "x"}):
            with self.assertRaises(DynamicCredentialError, msg=repr(bad)):
                dynamic_credential_entry(bad)


class ReadValueVerbatimTests(unittest.TestCase):
    """#88: _read_value must return the stored bytes exactly — no strip().

    Every supported store path chomps one trailing newline at write time,
    so the file contents ARE the intended value. Stubs subprocess.run (the
    sudo cat); no real secrets, no sudo needed."""

    def _read(self, stored: bytes) -> str:
        class Proc:
            returncode = 0
            stdout = stored
        real_run = fill_secret.subprocess.run
        fill_secret.subprocess.run = lambda *a, **k: Proc()
        try:
            return fill_secret._read_value("gh", "access_token")
        finally:
            fill_secret.subprocess.run = real_run

    def test_trailing_newlines_preserved(self):
        self.assertEqual(self._read(b"tok\n\n"), "tok\n\n")

    def test_whitespace_only_value_preserved(self):
        self.assertEqual(self._read(b"  \n"), "  \n")

    def test_leading_and_trailing_spaces_preserved(self):
        self.assertEqual(self._read(b" tok "), " tok ")

    def test_plain_value_unchanged(self):
        self.assertEqual(self._read(b"tok"), "tok")

    def test_missing_credential_raises(self):
        class Proc:
            returncode = 1
            stdout = b""
        real_run = fill_secret.subprocess.run
        fill_secret.subprocess.run = lambda *a, **k: Proc()
        try:
            with self.assertRaises(DynamicCredentialError):
                fill_secret._read_value("gh", "access_token")
        finally:
            fill_secret.subprocess.run = real_run


if __name__ == "__main__":
    unittest.main()
