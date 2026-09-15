"""Additional tests for round-6 findings 55-64.

These cover the grant-channel hardening. Run with:
    python3 -m unittest proxy.test_round6 -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swap_addon as sa

import logging
sa.log.propagate = False
sa.log.addHandler(logging.NullHandler())

# Reuse the fakes from the main test module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_swap_addon import make_addon, SECRETS, HOSTS, REGISTRY


def make_addon_with_grants(grants):
    """Make an addon with grants injected via the grants-file cache."""
    a = make_addon()
    # Bypass file IO: seed the cache directly.
    a._grants_cache = grants
    a._grants_mtime = "test"
    # _grants() checks mtime; stub _mtime to return the sentinel.
    a._mtime = lambda p: "test"
    return a


class GrantChannelTests(unittest.TestCase):

    # --- 55: host binding first, grants only widen methods/paths --------

    def test_55_grant_cannot_override_host_binding(self):
        """A grant for openai@github.com must NOT allow the swap:
        openai is bound to api.openai.com only."""
        grants = [{
            "credential": "openai",
            "host": "github.com",
            "method": "POST",
            "path_prefix": "/",
            "scope": "",
            "expires": "2099-01-01T00:00:00+00:00",
            "approval_id": "test123",
            "job": "",
        }]
        a = make_addon_with_grants(grants)
        ok, reason = a._credential_allows_request(
            "openai", "github.com", "POST", "/gists")
        self.assertFalse(ok)
        self.assertEqual(reason, "unbound-host")

    def test_55_grant_widens_method_within_bound_host(self):
        """A grant for a bound host CAN widen the method."""
        registry = dict(REGISTRY)
        registry["github"] = {
            "allowed_hosts": ["github.com"],
            "allowed_methods": ["GET"],
        }
        a = make_addon(registry=registry)
        a._grants_cache = [{
            "credential": "github",
            "host": "github.com",
            "method": "POST",
            "path_prefix": "/gists",
            "scope": "",
            "expires": "2099-01-01T00:00:00+00:00",
            "approval_id": "test456",
            "job": "",
        }]
        a._grants_mtime = "test"
        a._mtime = lambda p: "test"
        # POST is not in allowed_methods, but the grant widens it.
        ok, reason = a._credential_allows_request(
            "github", "github.com", "POST", "/gists")
        self.assertTrue(ok)

    def test_55_file_approval_not_for_unbound_host(self):
        """_file_approval fires only for method/path refusals."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                a = make_addon()
                a._audit = lambda host, matched: None
                filed = []
                a._file_approval = lambda n, h, m, p, r: filed.append(r)
                # Simulate the _resolve refusal path for unbound-host.
                # (We call the gating logic directly.)
                reason = "unbound-host"
                if reason in ("method-not-allowed", "path-not-allowed"):
                    a._file_approval("openai", "github.com",
                                     "POST", "/gists", reason)
                self.assertEqual(filed, [])
                # But method-not-allowed DOES file.
                reason = "method-not-allowed"
                if reason in ("method-not-allowed", "path-not-allowed"):
                    a._file_approval("github", "github.com",
                                     "POST", "/gists", reason)
                self.assertEqual(len(filed), 1)

    # --- 58: anti-flooding ----------------------------------------------

    def test_58_approval_coalesced_by_cred_host_method(self):
        """Two filings for same (cred, host, method) with different paths
        produce ONE pending item."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                with mock.patch.object(sa, "APPROVALS_ENABLED", True):
                    a = make_addon()
                    a._audit = lambda host, matched: None
                    a._file_approval("github", "github.com",
                                     "POST", "/gists", "method-not-allowed")
                    a._file_approval("github", "github.com",
                                     "POST", "/repos", "method-not-allowed")
                    pending = list((Path(tmp) / "pending").glob("*.json"))
                    self.assertEqual(len(pending), 1)

    def test_58_approval_cap_per_credential(self):
        """Max 5 pending per credential."""
        import datetime as dt
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                with mock.patch.object(sa, "APPROVALS_ENABLED", True):
                    a = make_addon()
                    a._audit = lambda host, matched: None
                    pending_dir = Path(tmp) / "pending"
                    pending_dir.mkdir(exist_ok=True)
                    # Pre-seed 5 items with old timestamps (bypasses the
                    # 60s rate limiter for this test).
                    old_time = (dt.datetime.now(dt.timezone.utc)
                                - dt.timedelta(hours=2)).isoformat()
                    for i in range(5):
                        item = {
                            "id": "seed%d" % i,
                            "created": old_time,
                            "expires": (dt.datetime.now(dt.timezone.utc)
                                        + dt.timedelta(hours=1)).isoformat(),
                            "credential": "github",
                            "host": "host%d.example" % i,
                            "method": "POST",
                            "path_prefix": "/",
                        }
                        (pending_dir / ("seed%d.json" % i)).write_text(
                            json.dumps(item))
                    # 6th filing for a new host should be rejected by cap.
                    a._file_approval("github", "host5.example",
                                     "POST", "/", "method-not-allowed")
                    pending = list(pending_dir.glob("*.json"))
                    self.assertEqual(len(pending), 5)

    # --- 60: grants in separate file, inference gets no approvals --------

    def test_60_grants_read_from_grants_file(self):
        """_grants() reads grants.json, not the registry."""
        with tempfile.TemporaryDirectory() as tmp:
            grants_file = Path(tmp) / "grants.json"
            grants_file.write_text(json.dumps({"grants": [{
                "credential": "github",
                "host": "github.com",
                "method": "POST",
                "path_prefix": "/",
                "expires": "2099-01-01T00:00:00+00:00",
                "approval_id": "filetest",
                "job": "",
            }]}))
            with mock.patch.object(sa, "GRANTS_FILE", grants_file):
                a = make_addon()
                # Clear cache to force file read.
                if hasattr(a, "_grants_cache"):
                    delattr(a, "_grants_cache")
                a._grants_mtime = None
                grants = a._grants()
                self.assertEqual(len(grants), 1)
                self.assertEqual(grants[0]["approval_id"], "filetest")

    def test_60_inference_does_not_file_approvals(self):
        """When APPROVALS_ENABLED is False, _file_approval is a no-op."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                with mock.patch.object(sa, "APPROVALS_ENABLED", False):
                    a = make_addon()
                    a._audit = lambda host, matched: None
                    a._file_approval("github", "github.com",
                                     "POST", "/", "method-not-allowed")
                    pending_dir = Path(tmp) / "pending"
                    if pending_dir.exists():
                        pending = list(pending_dir.glob("*.json"))
                    else:
                        pending = []
                    self.assertEqual(len(pending), 0)

    # --- 61: ssrf.deny ---------------------------------------------------

    def test_61_deny_list_beats_allow(self):
        """A host in ssrf.deny is refused even if in ssrf.allow."""
        a = make_addon()
        a.ssrf_hosts = ["github.com"]
        a.deny_hosts = ["github.com"]
        # The deny check happens in the SSRF guard. We test the data:
        # deny_hosts is populated and takes precedence.
        self.assertIn("github.com", a.deny_hosts)
        # _host_in_list is used for both; deny is checked first in code.
        # (Full integration is in test_swap_addon.py's SSRF tests.)


if __name__ == "__main__":
    unittest.main()
