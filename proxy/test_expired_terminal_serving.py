"""Tests for the S2 (#511) expired-approval terminal record serving in
proxy/swap_addon.py: _terminal_expiry reads the stamped consumed/
records deterministically (newest expired_at wins, same TTL window
and path scoping as the deny lookup) and _approval_signal_for_refusal
appends the expired leg to the filing signals without ever suppressing
the filing — replacing the retired best-effort filing-scan
observation leg.

Run with:
    python3 -m pytest proxy/test_expired_terminal_serving.py -q

Nothing touches /home/swapd; all approvals state lives in a tmp dir.
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
import swap_addon as sa  # noqa: E402

AID = "b1c2d3e4f5061728"
AID2 = "c2d3e4f5061728b1"


def _expired_record(aid=AID, expired_at=None, by="proxy", **kw):
    """A consumed/ record as S1's _stamp_expired_consumed writes it:
    the pending item's tuple fields plus the expiry stamp."""
    now = datetime.now(timezone.utc)
    rec = {
        "id": aid,
        "created": (now - timedelta(hours=2)).isoformat(),
        "expires": (now - timedelta(hours=1)).isoformat(),
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
        "decision": "expired",
        "expired_by": by,
        "requester": "swapd",
        "tenant_id": None,
    }
    rec.update(kw)
    if expired_at is None:
        rec["expired_at"] = now.isoformat()
    elif isinstance(expired_at, datetime):
        rec["expired_at"] = expired_at.isoformat()
    else:
        # Raw string passthrough — lets malformed-record tests plant
        # an unparseable expired_at verbatim.
        rec["expired_at"] = expired_at
    return rec


def _deny_record(aid=AID):
    now = datetime.now(timezone.utc)
    return {
        "id": aid,
        "credential": "github",
        "host": "github.com",
        "method": "POST",
        "path_prefix": "/gists",
        "decision": "deny",
        "answered_at": now.isoformat(),
    }


class ExpiredTerminalServingTests(unittest.TestCase):
    """S2 (#511), proxy side. The addon instance only needs _audit;
    the _approval_signal_for_refusal path's filing (summons/push) is
    mocked out."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.approvals = Path(self.tmp.name)
        (self.approvals / "pending").mkdir(parents=True)
        self.addon = sa.SwapAddon.__new__(sa.SwapAddon)
        self.addon._audit = lambda *a: True
        self.addon._denial_cache = {}  # #307: per-tuple consumed/ scan cache
        self.addon._expiry_cache = {}  # S2 (#511): same shape, expiry lookup
        self.addon._pending_cache = {}  # #563: per-tuple pending/ scan cache

    def tearDown(self):
        self.tmp.cleanup()

    def _ctx(self):
        return (mock.patch.object(sa, "APPROVALS_DIR", self.approvals),
                mock.patch.object(sa, "APPROVALS_ENABLED", True),
                mock.patch.object(sa, "_summons_append", lambda *a: None),
                mock.patch.object(sa, "_push_notify", lambda *a: None))

    def _plant_consumed(self, rec):
        cdir = self.approvals / "consumed"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / (rec["id"] + ".json")).write_text(json.dumps(rec))

    # --- newest-expired-wins ---

    def test_newest_expired_wins(self):
        """Two expired records for the same tuple: the leg names the
        aid with the newest expired_at (the record's own timestamp),
        not the newest mtime."""
        now = datetime.now(timezone.utc)
        with self._ctx()[0], self._ctx()[1]:
            # Older expired_at but FRESHER mtime must still lose: the
            # winner is keyed on expired_at, not mtime. (Real stamps
            # always have mtime >= expired_at; this synthetic case pins
            # the ordering key.)
            self._plant_consumed(_expired_record(
                aid=AID2, expired_at=now - timedelta(minutes=10)))
            self._plant_consumed(_expired_record(
                aid=AID, expired_at=now - timedelta(minutes=5)))
            p = self.approvals / "consumed" / (AID2 + ".json")
            os.utime(p, None)  # AID2 now has the freshest mtime in the dir
            self.assertEqual(
                self.addon._terminal_expiry(
                    "github", "github.com", "POST", "/gists"),
                AID)

    def test_ttl_expiry_of_leg(self):
        """A record whose expired_at is older than APPROVAL_SIGNAL_TTL
        serves no leg — even with a fresh mtime (pins the expired_at
        TTL branch, not just the mtime pre-filter)."""
        now = datetime.now(timezone.utc)
        with self._ctx()[0], self._ctx()[1]:
            self._plant_consumed(_expired_record(
                expired_at=now - timedelta(hours=2)))
            p = self.approvals / "consumed" / (AID + ".json")
            os.utime(p, None)  # fresh mtime: mtime pre-filter passes
            self.assertIsNone(
                self.addon._terminal_expiry(
                    "github", "github.com", "POST", "/gists"))

    # --- path-scoping parity with the deny lookup ---

    def test_path_scoping_ignores_other_path(self):
        """An expired record for a different normalized path is not
        served for this path — one planted expiry cannot black out
        approvals for other paths on the same tuple."""
        with self._ctx()[0], self._ctx()[1]:
            self._plant_consumed(_expired_record(path_prefix="/other"))
            self.assertIsNone(
                self.addon._terminal_expiry(
                    "github", "github.com", "POST", "/gists"))

    def test_path_scoping_serves_matching_path(self):
        """Among records for several paths, the matching one is
        served."""
        with self._ctx()[0], self._ctx()[1]:
            self._plant_consumed(_expired_record(
                aid=AID2, path_prefix="/other"))
            self._plant_consumed(_expired_record(aid=AID))
            self.assertEqual(
                self.addon._terminal_expiry(
                    "github", "github.com", "POST", "/gists"),
                AID)

    # --- decision filtering ---

    def test_ignores_deny_records(self):
        """A deny record is never served as an expired leg (and a
        deny stays the deny lookup's job) — even when the record
        carries a fresh expired_at, so only the decision filter
        stands between a denial and a false expired leg."""
        with self._ctx()[0], self._ctx()[1]:
            rec = _deny_record()
            rec["expired_at"] = datetime.now(timezone.utc).isoformat()
            self._plant_consumed(rec)
            self.assertIsNone(
                self.addon._terminal_expiry(
                    "github", "github.com", "POST", "/gists"))

    def test_malformed_records_ignored(self):
        """Unparseable expired_at, bad aid, and non-tuple records
        degrade to no leg — never a wrong leg."""
        with self._ctx()[0], self._ctx()[1]:
            self._plant_consumed(_expired_record(expired_at="not-a-time"))
            self._plant_consumed(_expired_record(aid="bogus!!"))
            self._plant_consumed(_expired_record(
                aid=AID2, credential="other-cred"))
            self.assertIsNone(
                self.addon._terminal_expiry(
                    "github", "github.com", "POST", "/gists"))

    # --- composition: never suppresses, deny supersedes ---

    def test_expired_never_suppresses_filing(self):
        """An in-window expired record for the tuple does not veto the
        replacement: a fresh approval is still filed (pending signal
        present) and the expired leg rides alongside it."""
        with self._ctx()[0], self._ctx()[1], self._ctx()[2], self._ctx()[3]:
            self._plant_consumed(_expired_record())
            signals = self.addon._approval_signal_for_refusal(
                "github", "github.com", "POST", "/gists",
                "method-not-allowed")
            states = [s for _, s in signals]
            self.assertIn("pending", states)
            self.assertIn("expired", states)
            self.assertEqual(
                [aid for aid, s in signals if s == "expired"], [AID])
            # The fresh filing actually landed in pending/.
            new_aids = [aid for aid, s in signals if s == "pending"]
            self.assertEqual(len(new_aids), 1)
            self.assertTrue(
                (self.approvals / "pending"
                 / (new_aids[0] + ".json")).exists())

    def test_deny_supersedes_expiry(self):
        """A terminal denial for the tuple wins: only the denied leg
        is delivered, no expired leg rides alongside."""
        with self._ctx()[0], self._ctx()[1], self._ctx()[2], self._ctx()[3]:
            self._plant_consumed(_expired_record(aid=AID2))
            self._plant_consumed(_deny_record(aid=AID))
            signals = self.addon._approval_signal_for_refusal(
                "github", "github.com", "POST", "/gists",
                "method-not-allowed")
            self.assertEqual(signals, [(AID, "denied")])
            # No fresh filing under a terminal denial.
            self.assertEqual(
                list((self.approvals / "pending").glob("*.json")), [])

    def test_fresh_filing_terminal_deny_no_expired_leg(self):
        """The #306 fresh-recheck path: a deny landing between the
        initial check and the filing write aborts the filing and
        delivers only the denied leg — expiry never rides with it."""
        now = datetime.now(timezone.utc)
        with self._ctx()[0], self._ctx()[1], self._ctx()[2], self._ctx()[3]:
            self._plant_consumed(_expired_record(aid=AID2))
            real_denial = self.addon._terminal_denial
            calls = []

            def racing_denial(name, host, method, path, fresh=False):
                calls.append(fresh)
                if fresh:
                    return AID  # the owner's deny lands mid-filing
                return real_denial(name, host, method, path, fresh=fresh)

            with mock.patch.object(self.addon, "_terminal_denial",
                                   racing_denial):
                signals = self.addon._approval_signal_for_refusal(
                    "github", "github.com", "POST", "/gists",
                    "method-not-allowed")
            self.assertTrue(calls)
            self.assertEqual(signals, [(AID, "denied")])

    # --- cache discipline (mirrors #307) ---

    def test_cache_invalidates_on_new_stamp(self):
        """A new expired stamp (consumed/ dir-mtime changes) invalidates
        the cached negative/positive — the newest record wins."""
        now = datetime.now(timezone.utc)
        with self._ctx()[0], self._ctx()[1]:
            self._plant_consumed(_expired_record(
                aid=AID2, expired_at=now - timedelta(minutes=10)))
            self.assertEqual(
                self.addon._terminal_expiry(
                    "github", "github.com", "POST", "/gists"),
                AID2)  # populates the cache
            self._plant_consumed(_expired_record(
                aid=AID, expired_at=now - timedelta(minutes=1)))
            self.assertEqual(
                self.addon._terminal_expiry(
                    "github", "github.com", "POST", "/gists"),
                AID)  # dir-mtime moved: rescan, newest wins

    def test_missing_consumed_dir_is_no_leg(self):
        """No consumed/ dir at all (approvals enabled, nothing stamped)
        is a clean no-leg, not an error."""
        with self._ctx()[0], self._ctx()[1]:
            self.assertIsNone(
                self.addon._terminal_expiry(
                    "github", "github.com", "POST", "/gists"))


if __name__ == "__main__":
    unittest.main()
