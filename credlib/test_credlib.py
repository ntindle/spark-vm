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


if __name__ == "__main__":
    unittest.main()
