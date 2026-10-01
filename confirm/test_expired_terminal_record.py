"""Tests for the S1 (#511) expired-approval terminal record stamp in
confirm/confirmd.py: confirmd's Finding-58 render reap stamps
consumed/<aid>.json write-if-absent before deleting the expired pending
file.

Run with:
    python3 -m pytest confirm/test_expired_terminal_record.py -q

Tailscale calls are mocked; no network or /home/swapd is touched.
"""
import json
import os
import pwd
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


def _fake_run(cmd, **kwargs):
    class R:
        returncode = 0
        stdout = ""
        stderr = ""
    cmd_str = " ".join(cmd)
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
        R.stdout = json.dumps({
            "Node": {"Name": "owner-node"},
            "UserProfile": {"LoginName": "ntindle@github"},
        })
    return R


with mock.patch("subprocess.run", side_effect=_fake_run):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import confirmd as cd

cd.AUDIT = os.devnull

AID = "a1b2c3d4e5f60718"


def _pending_item(aid=AID, expired=True):
    now = datetime.now(timezone.utc)
    exp = now - timedelta(seconds=5) if expired else now + timedelta(hours=1)
    return {
        "id": aid,
        "created": (now - timedelta(hours=2)).isoformat(),
        "expires": exp.isoformat(),
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
        "_csrf": "should-be-stripped",
        "_csrf_nonces": [{"nonce": "x", "ts": 1}],
    }


class ExpiredTerminalRecordTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.approvals = Path(self.tmp.name) / "approvals"
        self.approvals.mkdir()
        for sub in ("pending", "answered", "consumed"):
            (self.approvals / sub).mkdir()
        # Issue #620: housekeeping is cadence-gated on module state —
        # reset per test so answer-path behavior is order-independent.
        cd._reset_housekeeping_for_tests()

    def tearDown(self):
        self.tmp.cleanup()

    def _ctx(self):
        return mock.patch.object(cd, "APPROVALS", str(self.approvals))

    def _plant_pending(self, item):
        p = self.approvals / "pending" / (item["id"] + ".json")
        p.write_text(json.dumps(item))
        return str(p)

    # --- contract ---

    def test_stamp_contract(self):
        """The stamped record carries the design §2 schema: the pending
        item's fields plus decision=expired / expired_at / expired_by /
        requester / tenant_id=null, and no answered_* fields."""
        item = _pending_item()
        p = self._plant_pending(item)
        with self._ctx():
            self.assertTrue(cd._stamp_expired_consumed(AID, item, p,
                                                       "confirmd"))
            rec = json.loads(
                (self.approvals / "consumed" / (AID + ".json")).read_text())
        self.assertEqual(rec["id"], AID)
        self.assertEqual(rec["decision"], "expired")
        self.assertEqual(rec["expired_by"], "confirmd")
        self.assertIn("expired_at", rec)
        datetime.fromisoformat(rec["expired_at"])  # parses as ISO8601
        self.assertEqual(rec["requester"],
                         pwd.getpwuid(os.getuid()).pw_name)
        self.assertIsNone(rec["tenant_id"])
        # Pending-item fields ride along (same shape as answered records).
        for k in ("created", "expires", "kind", "credential", "host",
                  "method", "path_prefix", "summary"):
            self.assertEqual(rec[k], item[k])
        # Internal CSRF state is never stamped; answered_* fields are
        # never stamped on an expiry (that would redefine them — v2).
        self.assertNotIn("_csrf", rec)
        self.assertNotIn("_csrf_nonces", rec)
        self.assertNotIn("answered_at", rec)
        self.assertNotIn("answered_by", rec)

    def test_stamp_bad_aid_refused(self):
        """An aid that fails ID_RE raises ValueError and touches nothing
        under consumed/ (design §10 to-verify)."""
        item = _pending_item(aid="../evil")
        p = self._plant_pending(item)
        with self._ctx():
            with self.assertRaises(ValueError):
                cd._stamp_expired_consumed("../evil", item, p, "confirmd")
            self.assertEqual(list((self.approvals / "consumed").glob("*")),
                             [])
            # The planted pending file (landed at approvals/evil.json
            # via the ../ in its id) is untouched; nothing was stamped
            # anywhere outside consumed/.
            self.assertTrue((self.approvals / "evil.json").exists())

    def test_stamp_exactly_once_under_race(self):
        """Eight threads racing the same aid produce exactly one record:
        one winner (True), seven losers (False), one file on disk."""
        item = _pending_item()
        p = self._plant_pending(item)
        results = []
        with self._ctx():
            def racer():
                results.append(
                    cd._stamp_expired_consumed(AID, item, p, "confirmd"))
            threads = [threading.Thread(target=racer) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            files = list((self.approvals / "consumed").glob("*.json"))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 7)
        self.assertEqual(len(files), 1)
        rec = json.loads(files[0].read_text())
        self.assertEqual(rec["decision"], "expired")

    # --- precedence: the human answer always wins ---

    def test_answer_replace_wins_over_racing_stamp(self):
        """The design's precedence contract: if an expiry stamp lands
        first and the answer path then runs its UNCONDITIONAL os.replace,
        the approve/deny record is the terminal state. This test drives
        the REAL _answer_locked — not a hand-simulated os.replace — so
        an implementer "fixing" the answer path's answered->consumed
        move to write-if-absent fails here. (QA mutation review
        2026-09-26: the hand-simulated version of this test was
        vacuous — converting _answer_locked to write-if-absent broke
        nothing. This version pins the actual path.)

        Scenario: the proxy's filing-scan reap won the race mid-flight
        and stamped an expiry record; the human's deny then lands and
        must overwrite it."""
        item = _pending_item(expired=False)  # answerable: not expired
        nonce = cd._mint_csrf_nonce(AID)    # mint BEFORE planting
        p = self._plant_pending(item)
        with self._ctx():
            # The proxy won the race mid-flight: expiry record stamped.
            self.assertTrue(
                cd._stamp_expired_consumed(AID, item, p, "proxy"))
            h = cd.Handler.__new__(cd.Handler)  # real answer path
            h.client_address = ("100.99.0.1", 1234)
            h.send_response = lambda code: None
            h.send_header = lambda k, v: None
            h.end_headers = lambda: None
            with mock.patch.object(cd, "file_owner_name",
                                   return_value="swapd"):
                h._answer_locked("ntindle@github", AID, nonce, "deny")
            final = json.loads(
                (self.approvals / "consumed" / (AID + ".json")).read_text())
        self.assertEqual(final["decision"], "deny")
        self.assertIn("answered_at", final)
        self.assertIn("answered_by", final)
        self.assertNotIn("expired_at", final)

    def test_stamp_loses_when_answer_record_exists(self):
        """If the answer path already wrote the terminal record, the
        reaper's O_EXCL create fails -> False: the answer wins, nothing
        is clobbered."""
        item = _pending_item()
        p = self._plant_pending(item)
        with self._ctx():
            denied = dict(item)
            denied["decision"] = "deny"
            denied["answered_at"] = datetime.now(timezone.utc).isoformat()
            (self.approvals / "consumed" / (AID + ".json")).write_text(
                json.dumps(denied))
            self.assertFalse(cd._stamp_expired_consumed(AID, item, p,
                                                        "confirmd"))
            final = json.loads(
                (self.approvals / "consumed" / (AID + ".json")).read_text())
        self.assertEqual(final["decision"], "deny")

    # --- render-reap integration (load_pending) ---

    def test_render_reap_stamps_then_deletes(self):
        """load_pending()'s Finding-58 reap stamps the terminal record
        (expired_by=confirmd) and deletes the pending file."""
        item = _pending_item()
        self._plant_pending(item)
        with self._ctx():
            remaining = cd.load_pending()
            self.assertEqual(remaining, [])
            self.assertFalse(
                (self.approvals / "pending" / (AID + ".json")).exists())
            rec = json.loads(
                (self.approvals / "consumed" / (AID + ".json")).read_text())
        self.assertEqual(rec["decision"], "expired")
        self.assertEqual(rec["expired_by"], "confirmd")

    def test_render_reap_keeps_answer_when_it_won(self):
        """If the answer path consumed the aid while the reap waited on
        the per-aid lock, the reap must not stamp over the answer record
        and must not resurrect the pending file."""
        item = _pending_item()
        self._plant_pending(item)
        with self._ctx():
            denied = dict(item)
            denied["decision"] = "deny"
            (self.approvals / "consumed" / (AID + ".json")).write_text(
                json.dumps(denied))
            remaining = cd.load_pending()
            self.assertEqual(remaining, [])
            final = json.loads(
                (self.approvals / "consumed" / (AID + ".json")).read_text())
        self.assertEqual(final["decision"], "deny")
        self.assertNotIn("expired_at", final)

    def test_render_reap_leaves_unexpired_items(self):
        """A non-expired pending item is listed, not stamped or deleted."""
        item = _pending_item(expired=False)
        self._plant_pending(item)
        with self._ctx():
            remaining = cd.load_pending()
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0]["id"], AID)
            self.assertEqual(list((self.approvals / "consumed").glob("*")),
                             [])

    # --- reader fail-closed (versioning amendment) ---

    def test_answered_feed_renders_expired_badge(self):
        """S3 (#546): the interim badgeless render is over — an expired
        record renders an Expired badge (distinct from approve/deny)
        showing expired_at + expired_by, with no re-open form."""
        rec = {"id": AID, "summary": "s", "kind": "grant-request",
               "decision": "expired", "expired_at": "2026-09-27T12:00:00+00:00",
               "expired_by": "confirmd"}
        html = cd._render_answered_list([rec])
        self.assertIn(AID, html)
        self.assertIn("badge-expired", html)
        self.assertNotIn("badge-approve", html)
        self.assertNotIn("badge-deny", html)
        self.assertIn("expired by confirmd", html)
        self.assertIn("2026-09-27T12:00:00+00:00", html)
        self.assertNotIn("/reopen", html)
        # Escaping discipline holds on the new fields: a hostile
        # expired_by must not break out of the card markup.
        evil = dict(rec, expired_by='"><script>alert(1)</script>')
        evil_html = cd._render_answered_list([evil])
        self.assertNotIn("<script>", evil_html)
        self.assertIn("badge-expired", evil_html)

    def test_answered_api_item_expired_carries_no_nonce(self):
        """_answered_api_item allowlists fields; an expired record mints
        no re-open nonce and surfaces empty answered_by/at."""
        rec = {"id": AID, "summary": "s", "kind": "grant-request",
               "decision": "expired"}
        out = cd._answered_api_item(rec)
        self.assertEqual(out["decision"], "expired")
        self.assertEqual(out["answered_by"], "")
        self.assertEqual(out["answered_at"], "")
        self.assertNotIn("reopen_csrf", out)


class ExpiredHumanSurfaceTests(unittest.TestCase):
    """S3 (#546) tests: the human surface for expired terminal records —
    the answered-history Expired badge, the expired-410 → answered-history
    link, and the answered-feed sort key."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.approvals = Path(self.tmp.name) / "approvals"
        self.approvals.mkdir()
        for sub in ("pending", "answered", "consumed"):
            (self.approvals / sub).mkdir()
        # Issue #620: same cadence-gate reset as above.
        cd._reset_housekeeping_for_tests()

    def tearDown(self):
        self.tmp.cleanup()

    def _ctx(self):
        return mock.patch.object(cd, "APPROVALS", str(self.approvals))

    # --- /api/answered carries the expiry stamps ---

    def test_api_item_carries_expiry_fields(self):
        """The poller feed exposes expired_at/expired_by for expired
        records (the JS badge card reads them); answered records get
        empty strings — the answer fields are never reused (design §2)."""
        rec = {"id": AID, "summary": "s", "kind": "grant-request",
               "decision": "expired",
               "expired_at": "2026-09-27T12:00:00+00:00",
               "expired_by": "proxy"}
        out = cd._answered_api_item(rec)
        self.assertEqual(out["expired_at"], "2026-09-27T12:00:00+00:00")
        self.assertEqual(out["expired_by"], "proxy")
        self.assertEqual(out["answered_at"], "")
        self.assertEqual(out["answered_by"], "")
        answered = {"id": AID, "summary": "s", "kind": "grant-request",
                    "decision": "approve", "answered_at": "x", "answered_by": "y"}
        out2 = cd._answered_api_item(answered)
        self.assertEqual(out2["expired_at"], "")
        self.assertEqual(out2["expired_by"], "")

    # --- the answered feed sorts expired records on expired_at ---

    def test_load_answered_sorts_expired_on_expired_at(self):
        """Expired records have no answered_at, so _load_answered sorts
        them on their own expired_at stamp — not by mtime. The expired
        record here is deliberately the OLDEST file on disk."""
        now = datetime.now(timezone.utc)
        old_answered = {
            "id": "a1b2c3d4e5f60711", "summary": "s", "decision": "approve",
            "answered_at": (now - timedelta(hours=2)).isoformat(),
            "answered_by": "ntindle@github"}
        new_expired = {
            "id": "a1b2c3d4e5f60712", "summary": "s", "decision": "expired",
            "expired_at": now.isoformat(), "expired_by": "confirmd"}
        cdir = self.approvals / "consumed"
        (cdir / (old_answered["id"] + ".json")).write_text(
            json.dumps(old_answered))
        p = cdir / (new_expired["id"] + ".json")
        p.write_text(json.dumps(new_expired))
        # Backdate the expired record's mtime below the answered one's:
        # a mtime-sorted feed would put it last; stamp order must win.
        ancient = (now - timedelta(days=3)).timestamp()
        os.utime(p, (ancient, ancient))
        with self._ctx():
            items = cd._load_answered()
        self.assertEqual([it["id"] for it in items],
                         [new_expired["id"], old_answered["id"]])

    # --- the 410 link ---

    def test_expired_record_link_present_when_record_exists(self):
        """A terminal expired record in consumed/ yields the
        answered-history link."""
        (self.approvals / "consumed" / (AID + ".json")).write_text(
            json.dumps({"id": AID, "decision": "expired",
                        "expired_at": "2026-09-27T12:00:00+00:00",
                        "expired_by": "proxy"}))
        with self._ctx():
            link = cd._expired_record_link_html(AID)
        self.assertIn('href="/answered"', link)
        self.assertIn("answered history", link)

    def test_expired_record_link_absent_cases(self):
        """No record, a non-expired record, a corrupt record, or a bad
        aid all yield no link — the bare 410 stands, and the error page
        never raises."""
        cases = []
        # no consumed file at all
        cases.append(("missing", None))
        # an approve record for the same aid (human answer won the race)
        def plant_approve():
            (self.approvals / "consumed" / (AID + ".json")).write_text(
                json.dumps({"id": AID, "decision": "approve"}))
        cases.append(("non-expired", plant_approve))
        # corrupt JSON
        def plant_corrupt():
            (self.approvals / "consumed" / (AID + ".json")).write_text(
                "{not json")
        cases.append(("corrupt", plant_corrupt))
        for name, plant in cases:
            if plant:
                plant()
            with self._ctx():
                link = cd._expired_record_link_html(AID)
            self.assertEqual(link, "", "link for %s case" % name)
            if plant:
                (self.approvals / "consumed" / (AID + ".json")).unlink()
        with self._ctx():
            self.assertEqual(cd._expired_record_link_html("../evil"), "")

    # --- wiring: the synchronous expired 410s carry the link ---

    def _do_get_expired_detail(self, aid):
        h = cd.Handler.__new__(cd.Handler)
        h.path = "/approval/" + aid
        h.client_address = ("100.99.0.1", 1234)
        got = {}

        def fake_send_html(self, body, code=200, title="Approvals",
                           script=""):
            got.update(body=body, code=code)

        cd._aid_lock(aid)  # ensure the entry exists pre-reap
        with mock.patch.object(cd.Handler, "_auth",
                               return_value="ntindle@github"), \
             mock.patch.object(cd.Handler, "_send_html", fake_send_html), \
             mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            h.do_GET()
        return got

    def _plant_expired_pending(self, aid):
        (self.approvals / "pending" / (aid + ".json")).write_text(
            json.dumps({"id": aid, "summary": "s", "kind": "first-use",
                        "created": "2026-09-18T10:00:00+00:00",
                        "expires": "2020-01-01T00:00:00+00:00"}))

    def test_get_expired_410_links_history_when_record_exists(self):
        """GET /approval/<aid> on an expired item: with a terminal expired
        record already stamped (a reaper won the race), the 410 page
        links the human to the answered history."""
        aid = "expiredlink1"
        self._plant_expired_pending(aid)
        (self.approvals / "consumed" / (aid + ".json")).write_text(
            json.dumps({"id": aid, "decision": "expired",
                        "expired_at": "2026-09-27T12:00:00+00:00",
                        "expired_by": "proxy"}))
        got = self._do_get_expired_detail(aid)
        self.assertEqual(got["code"], 410)
        self.assertIn('href="/answered"', got["body"])

    def test_post_answer_expired_410_stamps_terminal_record(self):
        """#539: POST /answer on an already-expired item (Finding 53(a))
        stamps the S1 expired-approval terminal record BEFORE removing
        the pending file — the "expired between render and answer" case
        no longer leaves the expiry with no terminal record."""
        aid = "expiredlink4"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2020-01-01T00:00:00+00:00",
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it["id"])
        (self.approvals / "pending" / (aid + ".json")).write_text(
            json.dumps(it))
        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}

        def fake_send_html(self, body, code=200, title="Approvals",
                           script=""):
            got.update(body=body, code=code)

        cd._aid_lock(aid)
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch.object(cd.Handler, "_send_html", fake_send_html):
            h._answer_locked("ntindle@github", aid, nonce, "deny")
        self.assertEqual(got["code"], 410)
        rec_path = self.approvals / "consumed" / (aid + ".json")
        self.assertTrue(rec_path.exists(), "no terminal record stamped")
        rec = json.loads(rec_path.read_text())
        self.assertEqual(rec["decision"], "expired")
        self.assertEqual(rec["expired_by"], "confirmd")
        self.assertFalse(
            (self.approvals / "pending" / (aid + ".json")).exists(),
            "pending file not reaped")
        self.assertIn('href="/answered"', got["body"])
        self.assertIn("answered history", got["body"])

    def test_get_expired_410_stamps_record_and_links_history(self):
        """#539: GET /approval/<aid> on an expired item stamps the S1
        expired-approval terminal record BEFORE removing the pending file
        (stamp-then-delete), so the 410 now links to the answered history —
        the bare 410 only stands when a record cannot be stamped."""
        aid = "expiredlink2"
        self._plant_expired_pending(aid)
        got = self._do_get_expired_detail(aid)
        self.assertEqual(got["code"], 410)
        self.assertIn('href="/answered"', got["body"])
        self.assertIn("answered history", got["body"])
        rec_path = self.approvals / "consumed" / (aid + ".json")
        self.assertTrue(rec_path.exists(), "no terminal record stamped")
        rec = json.loads(rec_path.read_text())
        self.assertEqual(rec["decision"], "expired")
        self.assertEqual(rec["expired_by"], "confirmd")
        self.assertFalse(
            (self.approvals / "pending" / (aid + ".json")).exists(),
            "pending file not reaped")

    def test_post_answer_expired_410_links_history(self):
        """POST /answer on an expired item: same link behavior as the GET
        path (the synchronous is_expired reap)."""
        aid = "expiredlink3"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2020-01-01T00:00:00+00:00",
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it["id"])
        (self.approvals / "pending" / (aid + ".json")).write_text(
            json.dumps(it))
        (self.approvals / "consumed" / (aid + ".json")).write_text(
            json.dumps({"id": aid, "decision": "expired",
                        "expired_at": "2026-09-27T12:00:00+00:00",
                        "expired_by": "confirmd"}))
        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}

        def fake_send_html(self, body, code=200, title="Approvals",
                           script=""):
            got.update(body=body, code=code)

        cd._aid_lock(aid)
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch.object(cd.Handler, "_send_html", fake_send_html):
            h._answer_locked("ntindle@github", aid, nonce, "deny")
        self.assertEqual(got["code"], 410)
        self.assertIn('href="/answered"', got["body"])


if __name__ == "__main__":
    unittest.main()
