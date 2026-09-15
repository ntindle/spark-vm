"""Tests for confirm/confirmd.py (findings 47, 48, 57).

Run with:
    python3 -m unittest confirm.test_confirmd -v

Tailscale calls are mocked; no network or /home/swapd is touched.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Mock tailscale before importing confirmd.
def _fake_run(cmd, **kwargs):
    class R:
        returncode = 0
        stdout = ""
        stderr = ""
    cmd_str = " ".join(cmd)
    # Strip sudo prefix for matching.
    bare = cmd_str.replace("sudo -n ", "")
    if bare == "tailscale ip -4":
        R.stdout = "100.65.241.20\n"
    elif bare == "tailscale ip":
        R.stdout = "100.65.241.20\nfd7a:115c:a1e0::ee39:f116\n"
    elif "tailscale status --json" in cmd_str:
        R.stdout = json.dumps({
            "Self": {"DNSName": "spark-vm.axolotl-sirius.ts.net."}
        })
    elif "whois" in cmd_str:
        # Default: owner. Tests override per-case.
        R.stdout = json.dumps({
            "Node": {"Name": "owner-node"},
            "UserProfile": {"LoginName": "ntindle@github"},
        })
    return R

with mock.patch("subprocess.run", side_effect=_fake_run):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import confirmd as cd

# Silence logs.
cd.AUDIT = os.devnull


class ConfirmdTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.approvals = Path(self.tmp.name) / "approvals"
        self.approvals.mkdir()
        for sub in ("pending", "answered", "consumed"):
            (self.approvals / sub).mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    # --- 57: Origin exact-match -----------------------------------------

    def test_57_origin_ts_net_accepted(self):
        """The ts.net origin (with port) is in PAGE_ORIGINS."""
        # PAGE_ORIGINS was built at import with mocked tailscale.
        self.assertIn("https://spark-vm.axolotl-sirius.ts.net:8443",
                      cd.PAGE_ORIGINS)

    def test_57_origin_ip_literal_accepted(self):
        """The IP literal origin (with port) is in PAGE_ORIGINS."""
        self.assertIn("https://100.65.241.20:8443", cd.PAGE_ORIGINS)

    def test_57_origin_prefix_attack_rejected(self):
        """100.65.241.200 must NOT match (old startswith bug)."""
        evil = "https://100.65.241.200:8443"
        self.assertNotIn(evil, cd.PAGE_ORIGINS)
        # Also without port.
        self.assertNotIn("https://100.65.241.200", cd.PAGE_ORIGINS)

    def test_57_origin_wrong_port_rejected(self):
        """Port must match exactly."""
        self.assertNotIn("https://spark-vm.axolotl-sirius.ts.net:9999",
                         cd.PAGE_ORIGINS)

    # --- 48: nonce -------------------------------------------------------

    def test_48_nonce_format(self):
        """NONCE_RE matches 32-char urlsafe tokens."""
        import secrets as py_secrets
        token = py_secrets.token_urlsafe(24)[:32]
        # token_urlsafe may include -_; pad/truncate to 32.
        token = (token + "A" * 32)[:32]
        self.assertTrue(cd.NONCE_RE.match(token))
        self.assertFalse(cd.NONCE_RE.match("short"))
        self.assertFalse(cd.NONCE_RE.match("x" * 33))

    # --- 47: self-peer refusal -------------------------------------------

    def test_47_host_addrs_include_tailscale_ips(self):
        """HOST_ADDRS includes the mocked tailscale IPs."""
        self.assertIn("100.65.241.20", cd.HOST_ADDRS)
        self.assertIn("fd7a:115c:a1e0::ee39:f116", cd.HOST_ADDRS)

    # --- 50: requester from file owner ------------------------------------

    def test_50_file_owner_name(self):
        """file_owner_name returns the file's owner username."""
        p = self.approvals / "pending" / "test.json"
        p.write_text("{}")
        # In the test env, the file is owned by the current user.
        import pwd
        expected = pwd.getpwuid(os.stat(p).st_uid).pw_name
        self.assertEqual(cd.file_owner_name(str(p)), expected)


if __name__ == "__main__":
    unittest.main()
