"""Tests for the S1 (#511) expired-approval terminal record stamp in
proxy/swap_addon.py: the filing-scan reap stamps consumed/<aid>.json
write-if-absent (expired_by=proxy) before deleting the expired pending
file, and _terminal_denial keeps ignoring expired records (fail-closed
on pre-S2 proxies).

Run with:
    python3 -m pytest proxy/test_expired_terminal_stamp.py -q

Nothing touches /home/swapd; all approvals state lives in a tmp dir.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swap_addon as sa  # noqa: E402

AID = "b1c2d3e4f5061728"


def _expired_pending(aid=AID):
    now = datetime.now(timezone.utc)
    return {
        "id": aid,
        "created": (now - timedelta(hours=2)).isoformat(),
        "expires": (now - timedelta(seconds=5)).isoformat(),
        "kind": "grant-request",
        "credential": "github",
        "host": "github.com",
        "method": "POST",
        "path_prefix": "/gists",
        "scope": "",
        "amount": "",
        "job": "",
        "detail": "",
        "summary": "POST github.com/gists for github (refused: test)",
    }


class ExpiredTerminalStampTests(unittest.TestCase):
    """S1 (#511), proxy side. The addon instance only needs _audit;
    _file_approval's filing path (summons/push) is mocked out."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.approvals = Path(self.tmp.name)
        (self.approvals / "pending").mkdir(parents=True)
        self.addon = sa.SwapAddon.__new__(sa.SwapAddon)
        self.addon._audit = lambda *a: True
        self.addon._denial_cache = {}  # #307: per-tuple consumed/ scan cache
        self.addon._expiry_cache = {}  # S2 (#511): expiry-lookup cache
        self.addon._pending_cache = {}  # #563: per-tuple pending/ scan cache

    def tearDown(self):
        self.tmp.cleanup()

    def _ctx(self):
        return (mock.patch.object(sa, "APPROVALS_DIR", self.approvals),
                mock.patch.object(sa, "APPROVALS_ENABLED", True),
                mock.patch.object(sa, "_summons_append", lambda *a: None),
                mock.patch.object(sa, "_push_notify", lambda *a: None))

    def _plant_pending(self, item):
        p = self.approvals / "pending" / (item["id"] + ".json")
        p.write_text(json.dumps(item))
        return str(p)

    def _consumed(self, aid):
        p = self.approvals / "consumed" / (aid + ".json")
        return json.loads(p.read_text()) if p.exists() else None

    # --- stamp contract ---

    def test_stamp_contract(self):
        item = _expired_pending()
        p = self._plant_pending(item)
        with self._ctx()[0]:
            self.assertTrue(sa._stamp_expired_consumed(AID, item, p,
                                                       "proxy"))
            rec = self._consumed(AID)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["decision"], "expired")
        self.assertEqual(rec["expired_by"], "proxy")
        datetime.fromisoformat(rec["expired_at"])
        self.assertIsNone(rec["tenant_id"])
        self.assertNotIn("answered_at", rec)
        self.assertNotIn("answered_by", rec)
        self.assertNotIn("_csrf", rec)

    def test_stamp_bad_aid_refused(self):
        item = _expired_pending(aid="../evil")
        p = self._plant_pending(item)
        with self._ctx()[0]:
            with self.assertRaises(ValueError):
                sa._stamp_expired_consumed("../evil", item, p, "proxy")
            self.assertIsNone(self._consumed("../evil"))
            self.assertEqual(
                list((self.approvals / "consumed").glob("*"))
                if (self.approvals / "consumed").exists() else [], [])

    def test_stamp_exactly_once(self):
        item = _expired_pending()
        p = self._plant_pending(item)
        with self._ctx()[0]:
            self.assertTrue(sa._stamp_expired_consumed(AID, item, p,
                                                      "proxy"))
            self.assertFalse(sa._stamp_expired_consumed(AID, item, p,
                                                        "proxy"))
            rec = self._consumed(AID)
        self.assertEqual(rec["expired_by"], "proxy")

    def test_stamp_consumed_record_mode_0600(self):
        """#1211: the stamped consumed/<aid>.json is 0600, not 0644. It
        carries credential names, hosts, methods, and path prefixes —
        the data class _open_audit_log() keeps 0600 (finding 198) —
        and consumed/ has no directory-level restriction."""
        item = _expired_pending()
        p = self._plant_pending(item)
        with self._ctx()[0]:
            self.assertTrue(sa._stamp_expired_consumed(AID, item, p,
                                                       "proxy"))
        mode = stat.S_IMODE(os.stat(
            self.approvals / "consumed" / (AID + ".json")).st_mode)
        self.assertEqual(mode, 0o600)

    # --- filing-scan reap integration ---

    def test_filing_scan_reap_stamps_and_signals(self):
        """S2 (#511): an expired tuple-matching pending item is reaped —
        the consumed/ record is stamped (expired_by=proxy) and the
        pending file deleted. _file_approval itself no longer emits the
        expired leg (the retired scan-time observation leg); the leg is
        served deterministically from consumed/ via
        _approval_signal_for_refusal's _terminal_expiry append."""
        self._plant_pending(_expired_pending())
        pdir, pen, summons, push = self._ctx()
        with pdir, pen, summons, push:
            filing_signals = self.addon._file_approval(
                "github", "github.com", "POST", "/gists", "test")
        # Retired leg: _file_approval emits only the replacement filing.
        self.assertNotIn((AID, "expired"), filing_signals)
        self.assertIn("pending", [s[1] for s in filing_signals])
        self.assertFalse((self.approvals / "pending" / (AID + ".json"))
                         .exists())
        rec = self._consumed(AID)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["decision"], "expired")
        self.assertEqual(rec["expired_by"], "proxy")
        # The composition point serves the deterministic leg alongside
        # the coalesced pending signal.
        with pdir, pen, summons, push:
            signals = self.addon._approval_signal_for_refusal(
                "github", "github.com", "POST", "/gists", "test")
        self.assertIn((AID, "expired"), signals)
        self.assertIn("pending", [s[1] for s in signals])
        # The replacement filing is a distinct, live approval.
        new_aids = [s[0] for s in signals if s[1] == "pending"]
        self.assertEqual(len(new_aids), 1)
        self.assertNotEqual(new_aids[0], AID)

    def test_filing_scan_reap_stamps_nonmatching_expired(self):
        """Expired items for OTHER tuples are reaped (and stamped) too —
        the stamp is per-aid, not per-tuple — but carry no expired
        signal for this request's tuple."""
        other = _expired_pending(aid="c3d4e5f60718293a")
        other["credential"] = "openai"
        other["host"] = "api.openai.com"
        self._plant_pending(other)
        pdir, pen, summons, push = self._ctx()
        with pdir, pen, summons, push:
            signals = self.addon._file_approval("github", "github.com",
                                                "POST", "/gists", "test")
        self.assertNotIn(("c3d4e5f60718293a", "expired"), signals)
        rec = self._consumed("c3d4e5f60718293a")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["decision"], "expired")
        self.assertFalse(
            (self.approvals / "pending" / "c3d4e5f60718293a.json").exists())

    # --- fail-closed regression: pre-S2 proxies ignore expired records ---

    def test_terminal_denial_ignores_expired_records(self):
        """_terminal_denial requires decision == deny (and a parseable
        answered_at); an expired record for the same tuple yields None —
        the client keeps polling, exactly the v1 drift clause."""
        item = _expired_pending()
        rec = dict(item)
        rec.update({"decision": "expired",
                    "expired_at": datetime.now(timezone.utc).isoformat(),
                    "expired_by": "proxy",
                    "tenant_id": None})
        consumed = self.approvals / "consumed"
        consumed.mkdir(exist_ok=True)
        (consumed / (AID + ".json")).write_text(json.dumps(rec))
        pdir, pen, summons, push = self._ctx()
        with pdir, pen, summons, push:
            self.assertIsNone(
                self.addon._terminal_denial("github", "github.com",
                                           "POST", "/gists"))
            # Control: a deny record for the same tuple IS delivered.
            deny = dict(item)
            deny.update({"id": "d" * 16, "decision": "deny",
                         "answered_at":
                             datetime.now(timezone.utc).isoformat()})
            (consumed / ("d" * 16 + ".json")).write_text(json.dumps(deny))
            self.assertEqual(
                self.addon._terminal_denial("github", "github.com",
                                           "POST", "/gists"),
                "d" * 16)


if __name__ == "__main__":
    unittest.main()
