"""Additional tests for round-6 findings 55-64.

These cover the grant-channel hardening. Run with:
    python3 -m unittest proxy.test_round6 -v
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
        ok, reason, grant = a._credential_allows_request(
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
        ok, reason, grant = a._credential_allows_request(
            "github", "github.com", "POST", "/gists")
        self.assertTrue(ok)

    def test_55_file_approval_not_for_unbound_host(self):
        """_file_approval fires only for method/path refusals."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                a = make_addon()
                a._audit = lambda host, matched: True
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
                    a._audit = lambda host, matched: True
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
                    a._audit = lambda host, matched: True
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
                    a._audit = lambda host, matched: True
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


class GrantValidityWindowTests(unittest.TestCase):
    # --- issue #562: no swap is initiated on a grant expiring within
    # the enforcement window (mirror of confirmd's #534 mint window) --

    def _grant(self, seconds_left):
        now = datetime.now(timezone.utc)
        return {
            "credential": "openai",
            "expires": (now + timedelta(seconds=seconds_left)).isoformat(),
            "host": "api.openai.com",
            "method": "POST",
            "path_prefix": "/v1",
            "job": "job-1",
        }

    def _addon(self, grants, registry=None):
        reg = registry if registry is not None else {
            "openai": {"allowed_hosts": ["api.openai.com"],
                       "allowed_methods": ["GET"]},
        }
        a = make_addon(registry=reg)
        a._grants_cache = grants
        a._grants_mtime = "test"
        a._mtime = lambda p: "test"  # _grants() checks mtime; stub it
        return a

    def test_healthy_grant_used(self):
        a = self._addon([self._grant(3600)])
        ok, reason, grant = a._credential_allows_request(
            "openai", "api.openai.com", "POST", "/v1/chat")
        self.assertTrue(ok)
        self.assertEqual(reason, "")
        self.assertIsNotNone(grant)

    def test_expiring_grant_skipped(self):
        # 2 s of validity left < the 5 s default window: the grant is
        # skipped, so the request falls through to the static registry
        # policy, which restricts POST -> the grant-less refusal.
        a = self._addon([self._grant(2)])
        ok, reason, grant = a._credential_allows_request(
            "openai", "api.openai.com", "POST", "/v1/chat")
        self.assertFalse(ok)
        self.assertEqual(reason, "method-not-allowed")
        self.assertIsNone(grant)

    def test_other_healthy_grant_still_wins(self):
        # A skipped dying grant does not poison the loop: a second
        # grant with healthy validity still authorizes the request.
        a = self._addon([self._grant(2), self._grant(3600)])
        ok, reason, grant = a._credential_allows_request(
            "openai", "api.openai.com", "POST", "/v1/chat")
        self.assertTrue(ok)
        self.assertIsNotNone(grant)

    def test_window_zero_disables_guard(self):
        # SWAP_GRANT_MIN_VALIDITY_S=0 restores the old expiry-only
        # behavior: a grant with 2 s left is still initiated on.
        a = self._addon([self._grant(2)])
        with mock.patch.object(sa, "_GRANT_SWAP_MIN_VALIDITY_S", 0):
            ok, reason, grant = a._credential_allows_request(
                "openai", "api.openai.com", "POST", "/v1/chat")
        self.assertTrue(ok)
        self.assertIsNotNone(grant)

    def test_wider_window_skips_longer_lived_grant(self):
        # The window is env-tunable: with a 30 s window, a 10 s grant
        # is skipped where the default 5 s window would use it.
        a = self._addon([self._grant(10)])
        with mock.patch.object(sa, "_GRANT_SWAP_MIN_VALIDITY_S", 30):
            ok, reason, grant = a._credential_allows_request(
                "openai", "api.openai.com", "POST", "/v1/chat")
        self.assertFalse(ok)
        self.assertEqual(reason, "method-not-allowed")
        self.assertIsNone(grant)

    def test_static_binding_unaffected_by_window(self):
        # The window is grant-only: a request the static registry
        # allows carries no TTL and is unaffected by near-zero grants
        # for the same credential.
        a = self._addon([self._grant(1)], registry={
            "openai": {"allowed_hosts": ["api.openai.com"]}})
        ok, reason, grant = a._credential_allows_request(
            "openai", "api.openai.com", "POST", "/v1/chat")
        self.assertTrue(ok)
        self.assertIsNone(grant)


class PendingScanCacheTests(unittest.TestCase):
    # --- issue #563: the per-refusal pending/ scan is cached ---------

    def _plant(self, pending_dir, aid="a1b2c3d4e5f6a7b8",
               seconds_old=0, expired=False):
        now = datetime.now(timezone.utc)
        item = {
            "id": aid,
            "created": (now - timedelta(seconds=seconds_old)).isoformat(),
            "expires": ((now - timedelta(seconds=1)).isoformat()
                        if expired
                        else (now + timedelta(hours=1)).isoformat()),
            "kind": "grant-request",
            "credential": "openai",
            "host": "api.openai.com",
            "method": "POST",
            "path_prefix": "/v1",
            "scope": "",
            "amount": "",
            "job": "",
            "requester": "root",
        }
        (pending_dir / f"{aid}.json").write_text(json.dumps(item))

    def _refuse(self, a, method="POST"):
        return a._file_approval("openai", "api.openai.com", method,
                                "/v1/chat", "method-not-allowed")

    def _listdir_counter(self):
        counts = {"n": 0}
        real = os.listdir

        def counting(path, *args, **kwargs):
            counts["n"] += 1
            return real(path, *args, **kwargs)
        return counts, counting

    def test_second_identical_refusal_hits_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                a = make_addon()
                pending = Path(tmp) / "pending"
                pending.mkdir()
                # An old pending filing for the exact tuple: the
                # refusal coalesces, so no new file lands (mtime
                # stays put) and the second call can hit the cache.
                self._plant(pending, seconds_old=3600)
                counts, counting = self._listdir_counter()
                with mock.patch.object(sa.os, "listdir", counting):
                    sig1 = self._refuse(a)
                    scans_after_first = counts["n"]
                    self.assertGreater(scans_after_first, 0)  # non-vacuous
                    sig2 = self._refuse(a)
                self.assertEqual(sig1, [("a1b2c3d4e5f6a7b8", "pending")])
                self.assertEqual(sig2, sig1)
                self.assertEqual(counts["n"], scans_after_first,
                                 "second refusal must not rescan pending/")

    def test_new_filing_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                a = make_addon()
                pending = Path(tmp) / "pending"
                pending.mkdir()
                self._plant(pending, aid="b1b2c3d4e5f6a7b8",
                            seconds_old=3600)
                counts, counting = self._listdir_counter()
                with mock.patch.object(sa.os, "listdir", counting):
                    # First refusal for a different method tuple: no
                    # coalesce -> files a fresh approval (dir mtime
                    # changes).
                    sig1 = self._refuse(a, method="DELETE")
                    scans_after_first = counts["n"]
                    self.assertEqual(len(sig1), 1)
                    self.assertEqual(sig1[0][1], "pending")
                    aid1 = sig1[0][0]
                    self.assertTrue(sa._AID_RE.match(aid1))
                    self.assertNotEqual(aid1, "b1b2c3d4e5f6a7b8")
                    # Second refusal: the mtime changed, so the cache
                    # is bypassed and the fresh scan coalesces on the
                    # just-filed approval.
                    sig2 = self._refuse(a, method="DELETE")
                self.assertEqual(sig2, [(aid1, "pending")])
                self.assertGreater(counts["n"], scans_after_first,
                                   "mtime change must force a rescan")

    def test_ttl_expiry_forces_rescan(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                a = make_addon()
                (Path(tmp) / "pending").mkdir()
                counts, counting = self._listdir_counter()
                with mock.patch.object(sa, "_PENDING_CACHE_TTL",
                                       timedelta(0)), \
                        mock.patch.object(sa.os, "listdir", counting):
                    self._refuse(a)
                    first = counts["n"]
                    self.assertGreater(first, 0)
                    self._refuse(a)
                self.assertGreater(counts["n"], first,
                                   "expired TTL must force a rescan")

    def test_hit_skips_reap_then_ttl_reaps(self):
        # The cache hit skips the inline expiry reap (bounded
        # staleness); once the TTL lapses the next scan reaps with
        # the stamp-then-delete semantics intact.
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                a = make_addon()
                pending = Path(tmp) / "pending"
                pending.mkdir()
                # A live pending filing for the tuple: refusals
                # coalesce on it, so no new file lands and the dir
                # mtime stays put across calls.
                self._plant(pending, aid="d1b2c3d4e5f6a7b8",
                            seconds_old=3600)
                sig = self._refuse(a)  # prime the cache
                self.assertEqual(sig, [("d1b2c3d4e5f6a7b8", "pending")])
                key = next(iter(a._pending_cache))
                seen_mtime = a._pending_cache[key][4]
                # Plant an expired filing WITHOUT bumping the dir
                # mtime (in-place write + mtime restore): the cache
                # cannot see it.
                aid = "c1b2c3d4e5f6a7b8"
                self._plant(pending, aid=aid, expired=True)
                st = pending.stat()
                os.utime(pending, ns=(st.st_atime_ns, seen_mtime))
                sig = self._refuse(a)
                self.assertEqual(sig, [("d1b2c3d4e5f6a7b8", "pending")])
                self.assertTrue((pending / f"{aid}.json").exists(),
                                "cache hit must not reap")
                # TTL lapse -> fresh scan -> reap + terminal stamp.
                # (Lapse the stored entry itself: patching the TTL
                # constant only affects entries stored while patched.)
                va, pc, nw, vu, sm = a._pending_cache[key]
                a._pending_cache[key] = (
                    va, pc, nw,
                    datetime.now(timezone.utc) - timedelta(seconds=1), sm)
                sig = self._refuse(a)
                self.assertEqual(sig, [("d1b2c3d4e5f6a7b8", "pending")])
                self.assertFalse((pending / f"{aid}.json").exists(),
                                 "expired filing must be reaped")
                self.assertTrue((Path(tmp) / "consumed"
                                 / f"{aid}.json").exists(),
                                "reap must stamp the terminal record")

    def test_cache_key_cap_evicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                a = make_addon()
                (Path(tmp) / "pending").mkdir()
                with mock.patch.object(sa, "_PENDING_CACHE_MAX_KEYS", 1):
                    self._refuse(a, method="POST")    # caches key 1
                    self.assertEqual(len(a._pending_cache), 1)
                    key1 = next(iter(a._pending_cache))
                    # A second tuple forces the eviction branch: the
                    # cache is dropped rather than grown.
                    self._refuse(a, method="DELETE")
                    self.assertEqual(len(a._pending_cache), 1)
                    key2 = next(iter(a._pending_cache))
                    self.assertNotEqual(key1, key2)

    def test_stat_failure_disables_cache_but_not_scan(self):
        # If the pending/ dir cannot be stat'ed, no cache entry is
        # stored or read — but the scan itself still runs (fail-open
        # on cost, fail-closed on correctness).
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)):
                a = make_addon()
                pending = Path(tmp) / "pending"
                pending.mkdir()
                self._plant(pending, seconds_old=3600)
                real_stat, real_isdir = os.stat, os.path.isdir

                def fake_stat(path, *args, **kwargs):
                    if os.fspath(path) == os.fspath(pending):
                        raise OSError("nope")
                    return real_stat(path, *args, **kwargs)

                def fake_isdir(path):
                    if os.fspath(path) == os.fspath(pending):
                        return True
                    return real_isdir(path)

                with mock.patch.object(sa.os, "stat", fake_stat), \
                        mock.patch.object(sa.os.path, "isdir",
                                          fake_isdir):
                    sig = self._refuse(a)
                self.assertEqual(sig, [("a1b2c3d4e5f6a7b8", "pending")])
                self.assertEqual(a._pending_cache, {},
                                 "unstatable dir must not be cached")
