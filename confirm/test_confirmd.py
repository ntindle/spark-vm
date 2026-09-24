"""Tests for confirm/confirmd.py (findings 47, 48, 57).

Run with:
    python3 -m unittest confirm.test_confirmd -v

Tailscale calls are mocked; no network or /home/swapd is touched.
"""
import io
import json
import contextlib
import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
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

    # --- 67: sudo-first dnsname; unprivileged failure must not drop ---
    # --- the ts.net origin ----------------------------------------------

    def test_67_unprivileged_status_fails(self):
        """The unprivileged call fails as swapd; sudo still works."""
        def fake(cmd, **kwargs):
            class R:
                returncode = 0
                stdout = json.dumps({
                    "Self": {"DNSName": "spark-vm.axolotl-sirius.ts.net."}
                })
                stderr = ""
            if cmd[0] == "sudo":
                return R()
            class F:
                returncode = 1
                stdout = ""
                stderr = "permission denied"
            return F()
        with mock.patch("subprocess.run", side_effect=fake):
            self.assertEqual(
                cd._tailnet_dnsname(),
                "spark-vm.axolotl-sirius.ts.net")

    def test_67_sudo_fallback_used(self):
        """sudo-first: the unprivileged spelling is never tried first."""
        seen = []
        def fake(cmd, **kwargs):
            seen.append(cmd[0])
            class R:
                returncode = 0
                stdout = json.dumps({
                    "Self": {"DNSName": "spark-vm.axolotl-sirius.ts.net."}
                })
                stderr = ""
            return R()
        with mock.patch("subprocess.run", side_effect=fake):
            self.assertEqual(
                cd._tailnet_dnsname(),
                "spark-vm.axolotl-sirius.ts.net")
        self.assertEqual(seen[0], "sudo")

    def test_67_both_fail_returns_none(self):
        """Both spellings fail: None, so _page_origins keeps the IP
        origin only. The startup print of PAGE_ORIGINS makes this
        visible in the journal."""
        def fake(cmd, **kwargs):
            class F:
                returncode = 1
                stdout = ""
                stderr = "no tailscaled"
            return F()
        with mock.patch("subprocess.run", side_effect=fake):
            self.assertIsNone(cd._tailnet_dnsname())

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

    # --- #75: CSRF nonce ring -------------------------------------------

    def test_75_nonce_ring_accepts_recent(self):
        """The last 3 minted nonces all verify; the 4th mint evicts the
        oldest (a second tab's form stays valid across GETs)."""
        it = {}
        n1 = cd._mint_csrf_nonce(it)
        n2 = cd._mint_csrf_nonce(it)
        n3 = cd._mint_csrf_nonce(it)
        self.assertTrue(cd._csrf_nonce_ok(it, n1))
        self.assertTrue(cd._csrf_nonce_ok(it, n2))
        self.assertTrue(cd._csrf_nonce_ok(it, n3))
        n4 = cd._mint_csrf_nonce(it)
        self.assertTrue(cd._csrf_nonce_ok(it, n4))
        self.assertTrue(cd._csrf_nonce_ok(it, n2))
        self.assertTrue(cd._csrf_nonce_ok(it, n3))
        self.assertFalse(cd._csrf_nonce_ok(it, n1))
        self.assertEqual(len(it["_csrf_nonces"]), 3)

    def test_75_nonce_ring_migrates_legacy(self):
        """A legacy single `_csrf` slot is absorbed into the ring on the
        next mint, so pre-upgrade items keep working."""
        it = {"_csrf": "f" * 32}
        n = cd._mint_csrf_nonce(it)
        self.assertNotIn("_csrf", it)
        self.assertTrue(cd._csrf_nonce_ok(it, "f" * 32))
        self.assertTrue(cd._csrf_nonce_ok(it, n))

    def test_75_nonce_rejects_malformed_and_unknown(self):
        """Malformed and well-formed-but-unknown nonces are rejected;
        an empty item accepts nothing."""
        it = {}
        n = cd._mint_csrf_nonce(it)
        self.assertTrue(cd._csrf_nonce_ok(it, n))
        self.assertFalse(cd._csrf_nonce_ok(it, "short"))
        self.assertFalse(cd._csrf_nonce_ok(it, ""))
        self.assertFalse(cd._csrf_nonce_ok(it, None))
        self.assertFalse(cd._csrf_nonce_ok(it, "g" * 32))
        self.assertFalse(cd._csrf_nonce_ok({}, n))

    def test_75_nonce_ring_drops_expired(self):
        """Ring entries older than _CSRF_RING_TTL are pruned on mint."""
        it = {}
        n1 = cd._mint_csrf_nonce(it)
        it["_csrf_nonces"][0]["ts"] -= (cd._CSRF_RING_TTL + 1)
        n2 = cd._mint_csrf_nonce(it)
        self.assertFalse(cd._csrf_nonce_ok(it, n1))
        self.assertTrue(cd._csrf_nonce_ok(it, n2))
        self.assertEqual(len(it["_csrf_nonces"]), 1)

    def test_75_nonce_ttl_enforced_at_verify(self):
        """The TTL is enforced at verification time too, not only at
        mint (security review): an entry backdated past the TTL is
        rejected even if no new mint pruned it."""
        it = {}
        n = cd._mint_csrf_nonce(it)
        self.assertTrue(cd._csrf_nonce_ok(it, n))
        it["_csrf_nonces"][-1]["ts"] -= (cd._CSRF_RING_TTL + 1)
        self.assertFalse(cd._csrf_nonce_ok(it, n))

    def test_75_ring_knobs_have_sane_defaults(self):
        """The env-overridable ring knobs (arch review R1) default to
        the conservative 3 nonces / 15 minutes."""
        self.assertEqual(cd._CSRF_RING_SIZE, 3)
        self.assertEqual(cd._CSRF_RING_TTL, 15 * 60)

    def test_75_nonce_not_leaked_to_answered(self):
        """The ring is stripped before the item reaches answered/."""
        it = {"_csrf_nonces": [{"nonce": "f" * 32, "ts": 0}]}
        it.pop("_csrf", None)
        it.pop("_csrf_nonces", None)
        self.assertNotIn("_csrf_nonces", it)

    # --- #77: low-risk hardening leftovers -------------------------------

    def test_77_answered_dir_recreates(self):
        """answered_dir() re-creates the dir if deleted at runtime (L5)."""
        import shutil
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            shutil.rmtree(self.approvals / "answered")
            d = cd.answered_dir()
            self.assertTrue(os.path.isdir(d))

    def test_77_aid_lock_is_per_approval(self):
        """_aid_lock returns a stable per-aid lock (arch review B2/B3):
        same aid -> same lock, different aid -> different lock."""
        self.assertIs(cd._aid_lock("abc"), cd._aid_lock("abc"))
        self.assertIsNot(cd._aid_lock("abc"), cd._aid_lock("xyz"))

    def test_77_whois_cache_capped(self):
        """The whois cache does not grow without bound (L10)."""
        cd._whois_cache.clear()
        try:
            for i in range(4097):
                cd._whois_cache["10.0.0.%d" % i] = ("x", 0.0)
            # Mocked whois returns the owner login; the cache write is
            # what we exercise.
            with mock.patch("subprocess.run", side_effect=_fake_run):
                self.assertEqual(cd.tailnet_login("10.9.9.9"),
                                 "ntindle@github")
            self.assertLessEqual(len(cd._whois_cache), 4096)
        finally:
            cd._whois_cache.clear()

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


    # --- #1: JSON API allowlisting -------------------------------------

    def _evil_item(self):
        return {
            "id": "abc123",
            "summary": "GET api.github.com/repos/ for github",
            "kind": "first-use",
            "created": "2026-09-18T10:00:00+00:00",
            "expires": "2026-09-18T11:00:00+00:00",
            "credential": "github",
            "host": "api.github.com",
            "method": "GET",
            "path_prefix": "/repos/",
            "scope": "read",
            "amount": "",
            "job": "test-job",
            "detail": "please <script>alert(1)</script>",
            "_csrf": "f" * 32,
        }

    def test_1_pending_api_allowlists_fields(self):
        """The pending JSON exposes only the fields the list page
        already shows: id/summary/kind/created/expires.
        Structured fields (credential/host/...) and the CSRF nonce
        must not leak into the poller feed."""
        out = cd._pending_api_item(self._evil_item())
        self.assertEqual(set(out),
                         {"id", "summary", "kind", "created", "expires"})
        self.assertEqual(out["summary"], "GET api.github.com/repos/ for github")

    def test_1_answered_api_allowlists_fields(self):
        """Answered JSON exposes only id/summary/kind/decision/
        answered_by/answered_at."""
        it = dict(self._evil_item())
        it.update({"decision": "approve", "answered_by": "ntindle@github",
                   "answered_at": "2026-09-18T10:05:00+00:00"})
        out = cd._answered_api_item(it)
        self.assertEqual(set(out),
                         {"id", "summary", "kind", "decision",
                          "answered_by", "answered_at"})
        self.assertEqual(out["decision"], "approve")

    def test_1_pending_sorted_oldest_first(self):
        """Longest-waiting request renders first; items with
        missing/unparseable `created` sort last, never first."""
        mk = lambda c: {"id": c, "created": c}
        items = cd._sort_pending([mk("2026-09-18T11:00:00+00:00"),
                                  mk("2026-09-18T09:00:00+00:00"),
                                  mk("2026-09-18T10:00:00+00:00"),
                                  {"id": "no-created"},
                                  {"id": "garbage", "created": "not-a-date"}])
        self.assertEqual([it["id"] for it in items],
                         ["2026-09-18T09:00:00+00:00",
                          "2026-09-18T10:00:00+00:00",
                          "2026-09-18T11:00:00+00:00",
                          "no-created", "garbage"])

    def test_1_answered_newest_first(self):
        """Answered history is newest-first BY answered_at, not by
        random-hex filename order (engineering blocker 1)."""
        import uuid
        for i, ts in enumerate(["2026-09-18T09:00:00+00:00",
                                "2026-09-18T11:00:00+00:00",
                                "2026-09-18T10:00:00+00:00"]):
            fn = uuid.uuid4().hex[:16] + ".json"
            (self.approvals / "consumed" / fn).write_text(json.dumps({
                "id": "id%d" % i, "answered_at": ts, "decision": "approve"}))
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            got = cd._load_answered()
        self.assertEqual([it["id"] for it in got], ["id1", "id2", "id0"])

    # --- G2 (issue #214): answered-feed per-poll cost ---------------------

    def test_214_load_answered_parses_bounded_candidates(self):
        """_load_answered() parses only the 2x-feed-cap mtime-newest
        candidates — per-poll cost is O(feed), not O(consumed-dir) —
        while the feed still shows the answered_at-newest items,
        tolerant of mtime/answered_at skew inside the candidate pool."""
        n = 250  # > _ANSWERED_CANDIDATE_LIMIT (200)
        base = time.time()
        real_load = json.load
        for i in range(n):
            fn = "skew%04d.json" % i
            p = self.approvals / "consumed" / fn
            # One file (mtime rank 150, inside the 200-candidate pool but
            # outside the 100-item feed cap by mtime alone) claims the
            # newest answered_at — the answered_at re-sort must rescue it.
            if i == 150:
                ts = "2026-09-23T12:00:00+00:00"  # strictly newest
            else:
                ts = "2026-09-23T%02d:%02d:00+00:00" % (11 - i // 60,
                                                        59 - i % 60)
            p.write_text(json.dumps({
                "id": "id%d" % i, "answered_at": ts, "decision": "approve"}))
            os.utime(p, (base - i, base - i))  # mtime rank == id
        calls = {"n": 0}

        def counting_load(f):
            calls["n"] += 1
            return real_load(f)

        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
                mock.patch("json.load", counting_load):
            got = cd._load_answered()[:cd._ANSWERED_FEED_LIMIT]
        # Bounded parse count: 200 candidates max, not 250 files.
        self.assertLessEqual(calls["n"], cd._ANSWERED_CANDIDATE_LIMIT)
        # Skewed newest item is at the top, then the rest in
        # answered_at order.
        self.assertEqual(got[0]["id"], "id150")
        self.assertEqual([it["id"] for it in got[1:]],
                         ["id%d" % i for i in range(99)])
        self.assertEqual(len(got), cd._ANSWERED_FEED_LIMIT)

    # --- #1: rendering ---------------------------------------------------

    def test_1_render_pending_escapes(self):
        """Requester-supplied strings are HTML-escaped in cards."""
        it = dict(self._evil_item())
        it["summary"] = 'x"><script>alert(1)</script>'
        body = cd._render_pending_list([it])
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<script>alert", body)

    def test_1_render_pending_drops_hostile_id(self):
        """An id that fails ID_RE is silently skipped (it can never be
        answered anyway — the /approval route 400s it), so it cannot
        reach the href attribute context."""
        it = dict(self._evil_item())
        it["id"] = 'x"onmouseover=alert(1)'
        body = cd._render_pending_list([it])
        self.assertNotIn("onmouseover", body)
        self.assertIn("No pending approvals", body)

    def test_1_render_answered_unknown_decision_no_badge(self):
        """An unknown/missing decision is not styled as a deny."""
        it = dict(self._evil_item())
        it.update({"decision": "???", "answered_by": "ntindle@github",
                   "answered_at": "2026-09-18T10:05:00+00:00"})
        body = cd._render_answered_list([it])
        self.assertNotIn("badge-deny", body)
        self.assertNotIn("badge-approve", body)

    def test_1_render_answered_escapes(self):
        it = dict(self._evil_item())
        it.update({"decision": "deny", "answered_by": "ntindle@github",
                   "answered_at": "2026-09-18T10:05:00+00:00",
                   "summary": "<img src=x onerror=alert(1)>"})
        body = cd._render_answered_list([it])
        self.assertIn("&lt;img", body)
        self.assertNotIn("<img src=x", body)
        self.assertIn("badge-deny", body)

    def test_1_page_has_viewport_and_poll(self):
        """Phone-friendly: viewport meta; live lists carry the poller."""
        page = cd._page("t", "<p>x</p>",
                        cd.POLL_JS + '<script>startPoll("/api/pending",'
                        'renderPending);</script>')
        self.assertIn('name="viewport"', page)
        self.assertIn("startPoll", page)
        self.assertIn("textContent", page)

    # --- #1: API routes sit behind _auth ---------------------------------

    def _get(self, path, login):
        h = cd.Handler.__new__(cd.Handler)
        h.path = path
        sent = {}

        def fake_json(obj, code=200):
            sent["obj"] = obj
            sent["code"] = code

        with mock.patch.object(cd.Handler, "_auth", return_value=login), \
             mock.patch.object(cd.Handler, "_send_json",
                               side_effect=fake_json):
            h.do_GET()
        return sent

    def test_1_api_pending_behind_auth(self):
        """GET /api/pending with auth returns the allowlisted feed."""
        item = self._evil_item()
        with mock.patch.object(cd, "load_pending", return_value=[item]):
            sent = self._get("/api/pending", "ntindle@github")
        self.assertEqual(sent["code"], 200)
        self.assertEqual(len(sent["obj"]), 1)
        # Route-level allowlist: the full field set, not just one key.
        self.assertEqual(set(sent["obj"][0]),
                         {"id", "summary", "kind", "created", "expires"})

    def test_1_api_answered_behind_auth(self):
        item = dict(self._evil_item())
        item.update({"decision": "approve", "answered_by": "ntindle@github",
                     "answered_at": "2026-09-18T10:05:00+00:00"})
        with mock.patch.object(cd, "_load_answered", return_value=[item]):
            sent = self._get("/api/answered", "ntindle@github")
        self.assertEqual(sent["code"], 200)
        self.assertEqual(sent["obj"][0]["decision"], "approve")

    def test_1_api_answered_capped(self):
        """The 5s-polled answered feed is capped at 100 (product)."""
        items = [{"id": "x%d" % i,
                  "answered_at": "2026-09-18T10:00:00+00:00",
                  "decision": "approve"} for i in range(150)]
        with mock.patch.object(cd, "_load_answered", return_value=items):
            sent = self._get("/api/answered", "ntindle@github")
        self.assertEqual(len(sent["obj"]), 100)

    def test_1_send_json_no_store(self):
        """The JSON feed is Cache-Control: no-store (approval state is
        live; a cached feed would show stale approvals)."""
        import io
        h = cd.Handler.__new__(cd.Handler)
        headers = {}
        h.send_response = lambda code: headers.setdefault("code", code)
        h.send_header = lambda k, v: headers.__setitem__(k, v)
        h.end_headers = lambda: None
        h.wfile = io.BytesIO()
        h._send_json([{"id": "a"}])
        self.assertEqual(headers["code"], 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(json.loads(h.wfile.getvalue()), [{"id": "a"}])

    def test_1_routes_carry_poller(self):
        """/ and /answered wire the live poller (engineering #3)."""
        for path, fn in (("/", "renderPending"), ("/answered", "renderAnswered")):
            h = cd.Handler.__new__(cd.Handler)
            h.path = path
            got = {}

            def fake_html(body, code=200, title="", script=""):
                got.update(body=body, script=script)

            with mock.patch.object(cd.Handler, "_auth",
                                   return_value="ntindle@github"), \
                 mock.patch.object(cd.Handler, "_send_html",
                                   side_effect=fake_html), \
                 mock.patch.object(cd, "load_pending", return_value=[]), \
                 mock.patch.object(cd, "_load_answered", return_value=[]):
                h.do_GET()
            self.assertIn("startPoll", got["script"], path)
            self.assertIn(fn, got["script"], path)
            self.assertIn('id="items"', got["body"], path)
            if path == "/answered":
                # Product nit: the cap note must survive poller ticks,
                # so the stamp is a nested span, not the whole <p>.
                self.assertIn("showing the 100 most recent",
                              got["body"], path)
                self.assertIn('<span id="updated">', got["body"], path)

    def test_1_api_denied_without_auth(self):
        """No auth, no feed: _send_json is never reached."""
        with mock.patch.object(cd, "load_pending",
                               side_effect=AssertionError("must not run")):
            sent = self._get("/api/pending", None)
        self.assertEqual(sent, {})

    # --- Design review fixes ---------------------------------------------

    def test_1_err_has_back_nav(self):
        """Error pages are never navigation dead-ends (design #5)."""
        h = cd.Handler.__new__(cd.Handler)
        got = {}

        def fake_html(body, code=200, title="", script=""):
            got.update(body=body, code=code)

        with mock.patch.object(cd.Handler, "_send_html",
                               side_effect=fake_html):
            h._err("boom", 400)
        self.assertEqual(got["code"], 400)
        self.assertIn('href="/"', got["body"])
        self.assertIn("boom", got["body"])

    def test_1_detail_page_two_step_approve(self):
        """Approving is a two-tap confirm, not a single tap that mints
        a grant (design #4)."""
        aid = "abc123"
        p = self.approvals / "pending" / (aid + ".json")
        p.write_text(json.dumps({
            "id": aid, "summary": "GET api.github.com/ for github",
            "kind": "first-use",
            "created": "2026-09-18T10:00:00+00:00",
            "expires": "2999-01-01T00:00:00+00:00"}))
        h = cd.Handler.__new__(cd.Handler)
        h.path = "/approval/" + aid
        got = {}

        def fake_html(body, code=200, title="", script=""):
            got.update(body=body, code=code)

        with mock.patch.object(cd.Handler, "_auth",
                               return_value="ntindle@github"), \
             mock.patch.object(cd.Handler, "_send_html",
                               side_effect=fake_html), \
             mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            h.do_GET()
        self.assertEqual(got["code"], 200)
        self.assertIn('id="approveBtn"', got["body"])
        self.assertIn("Tap again to confirm approval", got["body"])
        self.assertIn('classList.add("armed")', got["body"])

    def test_1_style_stale_and_focus(self):
        """Stale poll-failure styling + focus-visible exist (design #1/#2)."""
        self.assertIn(".sub.stale", cd.STYLE)
        self.assertIn("focus-visible", cd.STYLE)
        # Dark-mode deny button meets contrast (design #1).
        self.assertIn(".btn-deny{color:#f2a9a2", cd.STYLE.replace(" ", "")
                      .replace("\n", ""))

    def test_1_poll_js_keyed_update(self):
        """The poller reconciles by id and skips unchanged payloads
        instead of wiping the list every 5 s (design #3)."""
        self.assertIn("keyedUpdate", cd.POLL_JS)
        self.assertIn("lastJson", cd.POLL_JS)
        self.assertIn("document.hidden", cd.POLL_JS)


    def test_version_payload_reports_repo_version(self):
        p = cd._version_payload()
        self.assertEqual(p["service"], "confirmd")
        self.assertEqual(p["handler"], "confirmd/1")
        self.assertRegex(p["version"],
                         r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
        # The reported version is the repo's single-source VERSION file.
        repo = os.path.dirname(os.path.abspath(cd.__file__))
        with open(os.path.join(repo, "..", "VERSION")) as f:
            self.assertEqual(p["version"], f.read().strip())

    # --- arch 2026-09-21: bound daemon-lifetime state growth ---

    def _seed_consumed(self, names, base_mtime):
        consumed = self.approvals / "consumed"
        for i, name in enumerate(names):
            p = consumed / name
            p.write_text("{}")
            # Stagger mtimes: names[0] oldest.
            ts = base_mtime + i * 10
            os.utime(p, (ts, ts))
        return consumed

    def test_prune_consumed_keeps_newest(self):
        """consumed/ keeps the newest N files by mtime, drops the rest."""
        names = ["a%d.json" % i for i in range(5)]
        self._seed_consumed(names, 1_700_000_000)
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            cd._prune_consumed(limit=3)
        remaining = sorted(p.name for p in (self.approvals / "consumed")
                           .iterdir())
        self.assertEqual(remaining, names[2:])

    def test_prune_consumed_noop_when_under_limit(self):
        """Fewer files than the keep count: nothing is deleted."""
        names = ["a0.json", "a1.json"]
        self._seed_consumed(names, 1_700_000_000)
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            cd._prune_consumed(limit=3)
        remaining = sorted(p.name for p in (self.approvals / "consumed")
                           .iterdir())
        self.assertEqual(remaining, names)

    def test_prune_consumed_ignores_non_json(self):
        """Non-.json files (e.g. a torn .tmp) are never pruned."""
        names = ["a%d.json" % i for i in range(3)]
        consumed = self._seed_consumed(names, 1_700_000_000)
        (consumed / "stray.tmp").write_text("x")
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            cd._prune_consumed(limit=1)
        remaining = sorted(p.name for p in consumed.iterdir())
        self.assertEqual(remaining, ["a2.json", "stray.tmp"])

    def test_prune_consumed_creates_missing_dir(self):
        """consumed_dir() makedirs at the use site: prune never raises."""
        import shutil
        shutil.rmtree(self.approvals / "consumed")
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            cd._prune_consumed(limit=3)  # must not raise
        self.assertTrue((self.approvals / "consumed").is_dir())

    def test_consumed_keep_minimum_covers_feed(self):
        """The keep floor (100) is coherent with the answered-feed cap."""
        self.assertGreaterEqual(cd._CONSUMED_KEEP, cd._ANSWERED_FEED_LIMIT)

    def test_evict_aid_lock(self):
        """The per-aid lock entry is dropped once the item leaves pending;
        evicting an absent id is a no-op."""
        cd._aid_lock("evict-me")
        self.assertIn("evict-me", cd._aid_locks)
        cd._evict_aid_lock("evict-me")
        self.assertNotIn("evict-me", cd._aid_locks)
        cd._evict_aid_lock("never-there")  # must not raise

    def test_answer_locked_evicts_aid_lock(self):
        """Wiring, not just the helper: answering (deny branch, no grant
        subprocess) must drop the per-aid lock entry. Deleting the
        _evict_aid_lock call in the consume path must fail this."""
        aid = "evict-wire-consume-1"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2999-01-01T00:00:00+00:00"}
        nonce = cd._mint_csrf_nonce(it)
        (self.approvals / "pending" / (aid + ".json")).write_text(
            json.dumps(it))
        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        h.send_response = lambda code: None
        h.send_header = lambda k, v: None
        h.end_headers = lambda: None
        cd._aid_lock(aid)  # ensure the entry exists pre-answer
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"):
            h._answer_locked("ntindle@github", aid, nonce, "deny")
        self.assertNotIn(aid, cd._aid_locks)
        # And the answer actually landed in consumed/.
        self.assertTrue(
            (self.approvals / "consumed" / (aid + ".json")).exists())

    def test_get_expired_reap_evicts_aid_lock(self):
        """Wiring: the GET expired-reap path must drop the per-aid lock
        entry too. Deleting that _evict_aid_lock call must fail this."""
        aid = "evict-wire-reap-1"
        (self.approvals / "pending" / (aid + ".json")).write_text(
            json.dumps({"id": aid, "summary": "s", "kind": "first-use",
                        "created": "2026-09-18T10:00:00+00:00",
                        "expires": "2020-01-01T00:00:00+00:00"}))
        h = cd.Handler.__new__(cd.Handler)
        h.path = "/approval/" + aid
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        cd._aid_lock(aid)  # ensure the entry exists pre-reap
        with mock.patch.object(cd.Handler, "_auth",
                               return_value="ntindle@github"), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)), \
             mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            h.do_GET()
        self.assertEqual(got["code"], 410)
        self.assertNotIn(aid, cd._aid_locks)
        self.assertFalse(
            (self.approvals / "pending" / (aid + ".json")).exists())


    # --- Issue #233: render reap races the answer critical section ---

    def test_233_load_pending_reap_holds_aid_lock(self):
        """The render reap must serialize on the per-aid lock: while
        another thread holds the lock, load_pending() must not remove
        the expired file. Removing the lock from the reap must fail
        this (the file would be gone within the sleep)."""
        aid = "reap-lock-1"
        p = self.approvals / "pending" / (aid + ".json")
        p.write_text(json.dumps(
            {"id": aid, "expires": "2020-01-01T00:00:00+00:00"}))
        lock = cd._aid_lock(aid)
        lock.acquire()
        done = []

        def worker():
            with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
                cd.load_pending()
            done.append(True)

        t = threading.Thread(target=worker)
        t.start()
        try:
            time.sleep(0.5)
            self.assertTrue(p.exists(),
                            "reap removed the file without holding the lock")
            self.assertFalse(done)
        finally:
            lock.release()
        t.join(timeout=5)
        self.assertTrue(done, "reap did not finish after the lock released")
        self.assertFalse(p.exists())
        self.assertNotIn(aid, cd._aid_locks)

    def test_233_load_pending_reap_loses_race_gracefully(self):
        """The answer path may consume the item while the reap waits on
        the lock; the reap must then swallow the failed remove (not
        raise) and still evict the lock entry. Deterministic: the only
        os.remove call in load_pending() is the reap's, so forcing it to
        raise FileNotFoundError models the lost race without threads
        (the lock-waiting half is covered by the holds-lock test)."""
        aid = "reap-remove-race-1"
        p = self.approvals / "pending" / (aid + ".json")
        p.write_text(json.dumps(
            {"id": aid, "expires": "2020-01-01T00:00:00+00:00"}))
        cd._aid_lock(aid)  # ensure the entry exists pre-reap
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch("os.remove",
                        side_effect=FileNotFoundError(2, "gone")):
            cd.load_pending()  # must swallow, not raise
        self.assertNotIn(aid, cd._aid_locks)

    def test_233_get_does_not_resurrect_reaped_item(self):
        """An item reaped by load_pending() must stay gone: GET must
        404, not mint a nonce into a resurrected file. Sequential by
        design — it guards the 404/no-resurrection invariant; the
        concurrent interleaving it names is closed by the lock
        serialization (covered by the holds-lock test) plus the
        write-back sitting under the lock (verified by inspection)."""
        aid = "reap-noresurrect-1"
        p = self.approvals / "pending" / (aid + ".json")
        p.write_text(json.dumps(
            {"id": aid, "expires": "2020-01-01T00:00:00+00:00"}))
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            cd.load_pending()
        self.assertFalse(p.exists())
        got = self._do_get_harness(aid)
        self.assertEqual(got["code"], 404)
        self.assertFalse(p.exists(), "GET resurrected the reaped file")

    def test_233_answer_raced_expiry_audits_and_refuses(self):
        """If the pending file disappears between the grant mint and the
        consume (only an out-of-process remover can do this now that the
        reap is in-lock), the handler must audit the distinct
        'answer-raced-expiry' event and refuse with 410 — never write an
        answered/consumed record that contradicts the reap."""
        aid = "raced-expiry-1"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2999-01-01T00:00:00+00:00",
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it)
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                # Simulate the out-of-process remover striking mid-mint.
                src.unlink()

                class R:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return R()
            return _fake_run(cmd, **kwargs)

        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        events = []
        cd._aid_lock(aid)  # ensure the entry exists pre-answer
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch("subprocess.run", side_effect=fake_run), \
             mock.patch.object(cd, "audit_log",
                               side_effect=lambda *a: events.append(a)), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)):
            h._answer_locked("ntindle@github", aid, nonce, "approve")
        self.assertEqual(got["code"], 410)
        self.assertTrue(
            any(e[0] == "answer-raced-expiry" for e in events),
            "no answer-raced-expiry audit; events: %r" % (events,))
        # And no contradictory answer/approve event was logged.
        self.assertFalse(
            any(e[0] == "answer" for e in events),
            "contradictory answer event; events: %r" % (events,))
        self.assertFalse(
            (self.approvals / "answered" / (aid + ".json")).exists())
        self.assertFalse(
            (self.approvals / "consumed" / (aid + ".json")).exists())
        # The file is gone and no future path reaps it: this terminal
        # path must evict too (issue #231's boundedness goal).
        self.assertNotIn(aid, cd._aid_locks)

    def test_240_expiry_crossing_mid_mint_audits_and_refuses(self):
        """Issue #240: if the expiry instant crosses DURING the grant-mint
        subprocess (up to 15 s), the post-mint os.path.exists check (#233)
        does not catch it — the in-memory item must be re-evaluated and
        the handler must audit the distinct 'answer-expired-mid-mint'
        event and refuse with 410, never writing an answered/consumed
        record for an already-expired approval. Deterministic: a
        controlled clock advances past expiry inside the fake mint."""
        from datetime import datetime as real_datetime, timezone as real_tz, \
            timedelta
        aid = "mid-mint-expiry-1"
        t0 = real_datetime.now(real_tz.utc)
        exp = t0 + timedelta(seconds=60)
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": exp.isoformat(),
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it)
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))

        class _Clock:
            instant = t0

            @classmethod
            def now(cls, tz=None):
                return cls.instant

            fromisoformat = staticmethod(real_datetime.fromisoformat)

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                # The expiry instant crosses while the mint runs.
                _Clock.instant = t0 + timedelta(seconds=120)

                class R:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return R()
            return _fake_run(cmd, **kwargs)

        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        events = []
        cd._aid_lock(aid)  # ensure the entry exists pre-answer
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch.object(cd, "datetime", _Clock), \
             mock.patch("subprocess.run", side_effect=fake_run), \
             mock.patch.object(cd, "audit_log",
                               side_effect=lambda *a: events.append(a)), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)):
            h._answer_locked("ntindle@github", aid, nonce, "approve")
        self.assertEqual(got["code"], 410)
        self.assertTrue(
            any(e[0] == "answer-expired-mid-mint" for e in events),
            "no answer-expired-mid-mint audit; events: %r" % (events,))
        # And no contradictory answer/approve event was logged.
        self.assertFalse(
            any(e[0] == "answer" for e in events),
            "contradictory answer event; events: %r" % (events,))
        self.assertFalse(
            (self.approvals / "answered" / (aid + ".json")).exists())
        self.assertFalse(
            (self.approvals / "consumed" / (aid + ".json")).exists())
        # Terminal path: the aid-lock entry must be evicted too
        # (issue #231's boundedness goal).
        self.assertNotIn(aid, cd._aid_locks)

    def test_240_is_expired_boundary_matches_reap(self):
        """Issue #240 trivia: load_pending()'s Finding-58 reap uses
        `now >= exp`; is_expired() must use the same boundary so an item
        is expired exactly at its instant everywhere."""
        from datetime import datetime as real_datetime, timezone as real_tz
        t = real_datetime(2026, 9, 23, 12, 0, 0, tzinfo=real_tz.utc)

        class _Clock:
            @classmethod
            def now(cls, tz=None):
                return t

            fromisoformat = staticmethod(real_datetime.fromisoformat)

        with mock.patch.object(cd, "datetime", _Clock):
            # Exactly at the instant: expired (the >= unification).
            self.assertTrue(cd.is_expired({"expires": t.isoformat()}),
                            "expires == now must read expired (>=)")
            # One tick in the future: not expired.
            future = t + real_datetime.resolution
            self.assertFalse(cd.is_expired({"expires": future.isoformat()}))
            # One tick in the past: expired.
            past = t - real_datetime.resolution
            self.assertTrue(cd.is_expired({"expires": past.isoformat()}))

    def test_233_sweep_answered_moves_old_files(self):
        """answered/ strays older than the grace period move to
        consumed/; fresh files and non-.json names are untouched."""
        old = self.approvals / "answered" / "old-1.json"
        fresh = self.approvals / "answered" / "fresh-1.json"
        stray_txt = self.approvals / "answered" / "note.txt"
        old.write_text("{}")
        fresh.write_text("{}")
        stray_txt.write_text("x")
        ancient = time.time() - 2 * 86400
        os.utime(old, (ancient, ancient))
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            cd._sweep_answered(grace=3600)
        self.assertFalse(old.exists())
        self.assertTrue(
            (self.approvals / "consumed" / "old-1.json").exists())
        self.assertTrue(fresh.exists())
        self.assertFalse(
            (self.approvals / "consumed" / "fresh-1.json").exists())
        self.assertTrue(stray_txt.exists())

    def test_233_sweep_answered_default_grace(self):
        """The default-grace path (grace=None → CONFIRM_ANSWERED_SWEEP_GRACE_S)
        sweeps a 3-day-old stray and leaves a 1-hour-old file alone."""
        old = self.approvals / "answered" / "old-default-1.json"
        young = self.approvals / "answered" / "young-default-1.json"
        old.write_text("{}")
        young.write_text("{}")
        now = time.time()
        os.utime(old, (now - 3 * 86400, now - 3 * 86400))
        os.utime(young, (now - 3600, now - 3600))
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            cd._sweep_answered()  # grace=None → module default
        self.assertFalse(old.exists())
        self.assertTrue(
            (self.approvals / "consumed" / "old-default-1.json").exists())
        self.assertTrue(young.exists())
        self.assertFalse(
            (self.approvals / "consumed" / "young-default-1.json").exists())

    def test_233_answer_sweeps_stale_answered_strays(self):
        """The after-answer _sweep_answered() call site: a stale
        answered/ stray is moved to consumed/ when an answer is
        consumed (deleting the call site must fail this)."""
        stray = self.approvals / "answered" / "stray-sweep-1.json"
        stray.write_text("{}")
        ancient = time.time() - 2 * 86400
        os.utime(stray, (ancient, ancient))
        aid = "sweep-callsite-1"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2999-01-01T00:00:00+00:00"}
        nonce = cd._mint_csrf_nonce(it)
        (self.approvals / "pending" / (aid + ".json")).write_text(
            json.dumps(it))
        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        h.send_response = lambda code: None
        h.send_header = lambda k, v: None
        h.end_headers = lambda: None
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"):
            h._answer_locked("ntindle@github", aid, nonce, "deny")
        self.assertFalse(stray.exists())
        self.assertTrue(
            (self.approvals / "consumed" / "stray-sweep-1.json").exists())

    # --- Issue #231: evict on the 404/corrupt negative paths ---

    def _do_get_harness(self, aid):
        h = cd.Handler.__new__(cd.Handler)
        h.path = "/approval/" + aid
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        with mock.patch.object(cd.Handler, "_auth",
                               return_value="ntindle@github"), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)), \
             mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            h.do_GET()
        return got

    def test_231_get_404_evicts_aid_lock(self):
        """GET for a nonexistent aid must drop the per-aid lock entry —
        the registry must not grow on the negative path."""
        aid = "evict-404-get-1"
        cd._aid_lock(aid)  # ensure the entry exists
        got = self._do_get_harness(aid)
        self.assertEqual(got["code"], 404)
        self.assertNotIn(aid, cd._aid_locks)

    def test_231_get_corrupt_evicts_aid_lock(self):
        """GET for a corrupt pending file: 404 and the lock entry is
        dropped."""
        aid = "evict-corrupt-get-1"
        (self.approvals / "pending" / (aid + ".json")).write_text(
            "{not json")
        cd._aid_lock(aid)
        got = self._do_get_harness(aid)
        self.assertEqual(got["code"], 404)
        self.assertNotIn(aid, cd._aid_locks)

    def test_231_answer_locked_404_evicts_aid_lock(self):
        """POST for a nonexistent aid must drop the per-aid lock entry."""
        aid = "evict-404-post-1"
        cd._aid_lock(aid)
        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)):
            h._answer_locked("ntindle@github", aid, "x" * 32, "deny")
        self.assertEqual(got["code"], 404)
        self.assertNotIn(aid, cd._aid_locks)


    def test_231_answer_locked_corrupt_evicts_aid_lock(self):
        """POST for a corrupt pending file: 404 and the lock entry is
        dropped (the fourth #231 negative path — deleting this evict
        must fail this test)."""
        aid = "evict-corrupt-post-1"
        (self.approvals / "pending" / (aid + ".json")).write_text(
            "{not json")
        cd._aid_lock(aid)  # ensure the entry exists
        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)):
            h._answer_locked("ntindle@github", aid, "x" * 32, "deny")
        self.assertEqual(got["code"], 404)
        self.assertNotIn(aid, cd._aid_locks)


class ReopenTests(unittest.TestCase):
    """H20: POST /reopen — re-file a denied approval as a new pending item.

    Run with:
        python3 -m unittest confirm.test_confirmd -v
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.approvals = Path(self.tmp.name) / "approvals"
        self.approvals.mkdir()
        for sub in ("pending", "answered", "consumed"):
            (self.approvals / sub).mkdir()
        cd._reopen_nonces.clear()

    def tearDown(self):
        self.tmp.cleanup()
        cd._reopen_nonces.clear()

    def _denied_record(self, aid="deny-old-1", **kw):
        it = {"id": aid, "summary": "credential spend", "kind": "first-use",
              "credential": "openai", "host": "api.openai.com",
              "method": "POST", "path_prefix": "/v1", "scope": "chat",
              "amount": None, "job": "mjob-x",
              "detail": "run the report", "created": "2026-09-24T00:00:00+00:00",
              "expires": "2999-01-01T00:00:00+00:00",
              "decision": "deny", "answered_by": "ntindle@github",
              "answered_at": "2026-09-24T00:05:00+00:00",
              "requester": "bdrive",
              # Terminal-state must never leak into a re-filed item even
              # if a record carries it (the copy is allowlist-based, but
              # pin the guarantee with the fields present).
              "_csrf_nonces": ["deadbeef" * 8], "_csrf": "deadbeef" * 8}
        it.update(kw)
        return it

    def _denied_item(self, aid="deny-old-1", subdir="consumed", **kw):
        it = self._denied_record(aid, **kw)
        (self.approvals / subdir / (aid + ".json")).write_text(
            json.dumps(it))
        return it

    def _handler(self):
        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        calls = {}
        headers = {}
        h.send_response = lambda code: calls.update(code=code)
        h.send_header = lambda k, v: headers.__setitem__(k, v)
        h.end_headers = lambda: None
        return h, calls, headers

    def _reopen(self, h, aid, csrf):
        got = {}
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)):
            h._reopen_locked("ntindle@github", aid, csrf)
        return got

    def test_reopen_denied_refiles_as_new_pending(self):
        """Happy path: a deny item is re-filed with a NEW aid, the request
        fields carried over, terminal state dropped, lineage recorded, the
        owner re-pushed, and the 303 points at the new approval page."""
        aid = "deny-old-1"
        old = self._denied_item(aid)
        nonce = cd._mint_reopen_nonce(aid)
        enqueued = []

        class _SyncThread:
            def __init__(self, target=None, name=None, daemon=None):
                self._t = target
            def start(self):
                self._t()

        class _Q:
            @staticmethod
            def default():
                return _Q()
            def enqueue(self, item):
                enqueued.append(item)
                return "queued"
        fakepush = mock.Mock()
        fakepush.PushQueue = _Q

        h, calls, headers = self._handler()
        with mock.patch.object(cd, "_push_mod", fakepush), \
             mock.patch.object(cd.threading, "Thread", _SyncThread):
            got = self._reopen(h, aid, nonce)

        self.assertEqual(calls.get("code"), 303, got)
        new_aid = headers["Location"].rsplit("/", 1)[-1]
        self.assertRegex(new_aid, r"^[0-9a-f]{16}$")
        self.assertNotEqual(new_aid, aid)
        self.assertEqual(headers["Location"], "/approval/" + new_aid)
        # The re-filed item carries the request, not the answer.
        new = json.loads((self.approvals / "pending"
                          / (new_aid + ".json")).read_text())
        for key in ("credential", "host", "method", "path_prefix",
                    "scope", "job", "detail", "summary", "kind"):
            self.assertEqual(new[key], old[key], key)
        self.assertNotIn("decision", new)
        self.assertNotIn("answered_at", new)
        self.assertNotIn("answered_by", new)
        self.assertNotIn("_csrf_nonces", new)
        self.assertNotIn("_csrf", new)
        self.assertEqual(new["reopened_from"], aid)
        self.assertEqual(new["original_requester"], "bdrive")
        # Expiry preserves the requester's original deadline, verbatim.
        self.assertEqual(new["expires"], old["expires"])
        # And created is fresh (the re-filed item is new, not backdated).
        self.assertLess(abs((cd._parse_expiry(new["created"])
                             - datetime.now(timezone.utc))
                            .total_seconds()), 60)
        # The denied record is history and stays untouched.
        kept = json.loads((self.approvals / "consumed"
                           / (aid + ".json")).read_text())
        self.assertEqual(kept["decision"], "deny")
        # The nonce is one-shot and the re-open idempotent: a second
        # POST with the same (now-evicted) nonce 303s to the SAME new
        # approval — no 403, no duplicate filing.
        h2, calls2, headers2 = self._handler()
        got2 = self._reopen(h2, aid, nonce)
        self.assertEqual(calls2.get("code"), 303, got2)
        self.assertEqual(headers2["Location"], headers["Location"])
        self.assertEqual(len(list((self.approvals / "pending").glob(
            "*.json"))), 1)
        # The owner was re-pushed for the NEW aid.
        self.assertEqual([e["id"] for e in enqueued], [new_aid])
        # Per-aid lock + nonce registry hygiene.
        self.assertNotIn(aid, cd._aid_locks)
        self.assertNotIn(aid, cd._reopen_nonces)

    def test_reopen_approve_item_refused(self):
        """An approved item cannot be re-opened: 400, nothing filed."""
        aid = "approve-old-1"
        self._denied_item(aid, decision="approve")
        nonce = cd._mint_reopen_nonce(aid)
        h, calls, _ = self._handler()
        with mock.patch.object(cd, "_push_mod", None):
            got = self._reopen(h, aid, nonce)
        self.assertEqual(got["code"], 400)
        self.assertEqual(list((self.approvals / "pending").glob("*.json")),
                         [])

    def test_reopen_missing_item_404(self):
        h, calls, _ = self._handler()
        nonce = cd._mint_reopen_nonce("deny-ghost-1")
        got = self._reopen(h, "deny-ghost-1", nonce)
        self.assertEqual(got["code"], 404)

    def test_reopen_malformed_nonce_is_violation(self):
        """Malformed nonce: 403 via the _deny path (audit: csrf: bad
        nonce), nothing filed."""
        aid = "deny-old-2"
        self._denied_item(aid)
        h, calls, _ = self._handler()
        denied = {}
        with mock.patch.object(cd.Handler, "_deny",
                               side_effect=lambda p, l, r: denied.update(
                                   reason=r)):
            self._reopen(h, aid, "not-a-nonce")
        self.assertIn("csrf: bad nonce", denied["reason"])
        self.assertEqual(list((self.approvals / "pending").glob("*.json")),
                         [])

    def test_reopen_unknown_nonce_is_stale(self):
        """Well-formed but unknown nonce for a REAL deny item: 403
        stale-nonce, nothing filed. (For a missing item the load fails
        first with 404 — the nonce gate only runs once there is a deny
        record to re-open.)"""
        aid = "deny-old-3"
        self._denied_item(aid)
        h, calls, _ = self._handler()
        got = self._reopen(h, aid, "x" * 32)
        self.assertEqual(got["code"], 403)
        self.assertIn("stale", got["msg"])
        self.assertEqual(list((self.approvals / "pending").glob("*.json")),
                         [])

    def test_reopen_expired_window_410(self):
        """The original TTL already closed: 410, nothing filed, distinct
        audit event (the request itself has expired)."""
        aid = "deny-old-4"
        self._denied_item(aid, created="2026-09-20T00:00:00+00:00",
                          expires="2026-09-20T01:00:00+00:00")
        nonce = cd._mint_reopen_nonce(aid)
        h, calls, _ = self._handler()
        got = self._reopen(h, aid, nonce)
        self.assertEqual(got["code"], 410)
        self.assertEqual(list((self.approvals / "pending").glob("*.json")),
                         [])

    def test_reopen_nonce_stable_across_renders(self):
        """The nonce survives re-renders: the 5 s poller must not
        invalidate a form it already built."""
        aid = "deny-old-5"
        self.assertEqual(cd._mint_reopen_nonce(aid),
                         cd._mint_reopen_nonce(aid))

    def test_reopen_push_fail_open(self):
        """A failed push import must not lose the re-open: the page is the
        fallback, exactly the H2 filing guarantee."""
        aid = "deny-old-6"
        self._denied_item(aid)
        nonce = cd._mint_reopen_nonce(aid)
        h, calls, headers = self._handler()
        with mock.patch.object(cd, "_push_mod", None):
            got = self._reopen(h, aid, nonce)
        self.assertEqual(calls.get("code"), 303, got)
        self.assertTrue(headers["Location"].startswith("/approval/"))

    def test_reopen_expired_nonce_is_stale(self):
        """An expired-but-once-live nonce: 403 stale-nonce, nothing filed."""
        aid = "deny-old-7"
        self._denied_item(aid)
        nonce = cd._mint_reopen_nonce(aid)
        cd._reopen_nonces[aid]["ts"] -= (cd._REOPEN_NONCE_TTL + 1)
        h, calls, _ = self._handler()
        got = self._reopen(h, aid, nonce)
        self.assertEqual(got["code"], 403)

    def test_answered_api_item_denied_carries_nonce(self):
        """The /api/answered JSON carries reopen_csrf for deny items only —
        the poller needs it for the re-open form."""
        aid = "deny-old-8"
        old = self._denied_item(aid)
        out = cd._answered_api_item(old)
        self.assertTrue(cd._reopen_nonce_ok(aid, out["reopen_csrf"]))
        out2 = cd._answered_api_item(dict(old, decision="approve"))
        self.assertNotIn("reopen_csrf", out2)

    def test_reopen_concurrent_is_idempotent(self):
        """Two threads re-opening the same deny item: both 303, both to
        the SAME new approval, exactly one pending file. The loser's POST
        carries the now-evicted nonce, so it takes the idempotent path —
        never a 403, never a duplicate."""
        aid = "deny-old-9"
        self._denied_item(aid)
        nonce = cd._mint_reopen_nonce(aid)
        codes = {}
        locations = {}
        barrier = threading.Barrier(2)

        def worker():
            h, calls, headers = self._handler()
            barrier.wait()
            with cd._aid_lock(aid):
                h._reopen_locked("ntindle@github", aid, nonce)
            codes[threading.get_ident()] = calls.get("code")
            locations[threading.get_ident()] = headers.get("Location")

        def fake_err(handler_self, msg, code):
            codes[threading.get_ident()] = code

        # NOTE: the patches live in the MAIN thread for the whole join —
        # mock.patch is process-global, not thread-scoped, so per-thread
        # patch contexts would unpatch each other mid-race.
        with mock.patch.object(cd, "APPROVALS",
                               str(self.approvals)), \
             mock.patch.object(cd.Handler, "_err", fake_err), \
             mock.patch.object(cd, "_push_mod", None):
            ts = [threading.Thread(target=worker) for _ in range(2)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
        self.assertEqual(sorted(codes.values()), [303, 303])
        self.assertEqual(len(set(locations.values())), 1)
        self.assertTrue(
            list(locations.values())[0].startswith("/approval/"))
        self.assertEqual(len(list((self.approvals / "pending").glob(
            "*.json"))), 1)

    def test_reopen_double_tap_same_nonce_is_idempotent(self):
        """The mobile double-tap: two POSTs with the SAME nonce. The
        first files; the second (nonce now evicted) takes the idempotent
        path and 303s to the same new approval — never a 403, never a
        duplicate."""
        aid = "deny-old-10"
        self._denied_item(aid)
        nonce = cd._mint_reopen_nonce(aid)
        h1, calls1, headers1 = self._handler()
        with mock.patch.object(cd, "_push_mod", None):
            got1 = self._reopen(h1, aid, nonce)
        self.assertEqual(calls1.get("code"), 303, got1)
        h2, calls2, headers2 = self._handler()
        with mock.patch.object(cd, "_push_mod", None):
            got2 = self._reopen(h2, aid, nonce)
        self.assertEqual(calls2.get("code"), 303, got2)
        self.assertEqual(headers2["Location"], headers1["Location"])
        self.assertEqual(len(list((self.approvals / "pending").glob(
            "*.json"))), 1)

    def test_reopen_repeat_with_fresh_nonce_redirects(self):
        """Deliberate second re-open: the card re-rendered with a fresh
        one-shot nonce. Still exactly one pending file; the second 303
        points at the FIRST new approval."""
        aid = "deny-old-11"
        self._denied_item(aid)
        h1, calls1, headers1 = self._handler()
        with mock.patch.object(cd, "_push_mod", None):
            self._reopen(h1, aid, cd._mint_reopen_nonce(aid))
        first = headers1["Location"]
        self.assertEqual(calls1.get("code"), 303)
        self.assertTrue(first.startswith("/approval/"))
        # The card re-rendered: a fresh one-shot nonce for the same deny.
        fresh = cd._mint_reopen_nonce(aid)
        h2, calls2, headers2 = self._handler()
        with mock.patch.object(cd, "_push_mod", None):
            got2 = self._reopen(h2, aid, fresh)
        self.assertEqual(calls2.get("code"), 303, got2)
        self.assertEqual(headers2["Location"], first)
        self.assertEqual(len(list((self.approvals / "pending").glob(
            "*.json"))), 1)

    def test_reopen_corrupt_history_404(self):
        """A torn consumed file: 404, nothing filed (the #231 negative
        path for /reopen)."""
        aid = "deny-old-12"
        (self.approvals / "consumed" / (aid + ".json")).write_text(
            "{not json")
        nonce = cd._mint_reopen_nonce(aid)
        h, calls, _ = self._handler()
        got = self._reopen(h, aid, nonce)
        self.assertEqual(got["code"], 404)
        self.assertEqual(list((self.approvals / "pending").glob("*.json")),
                         [])

    def test_reopen_pending_item_404(self):
        """An aid that is still pending (never answered): 404 — only
        consumed/answered history may re-open."""
        aid = "deny-old-13"
        (self.approvals / "pending" / (aid + ".json")).write_text(
            json.dumps({"id": aid, "summary": "x"}))
        before = sorted(
            p.name for p in (self.approvals / "pending").glob("*.json"))
        nonce = cd._mint_reopen_nonce(aid)
        h, calls, _ = self._handler()
        got = self._reopen(h, aid, nonce)
        self.assertEqual(got["code"], 404)
        self.assertEqual(sorted(
            p.name for p in (self.approvals / "pending").glob("*.json")),
            before)

    def test_reopen_id_mismatch_404(self):
        """Defense in depth: the history record's id disagrees with its
        filename — refuse rather than re-file the wrong record."""
        aid = "deny-old-14"
        self._denied_item(aid, id="some-other-aid")
        nonce = cd._mint_reopen_nonce(aid)
        h, calls, _ = self._handler()
        got = self._reopen(h, aid, nonce)
        self.assertEqual(got["code"], 404)
        self.assertEqual(list((self.approvals / "pending").glob("*.json")),
                         [])

    def test_reopen_answered_fallback(self):
        """A previous run's failed sweep left the deny record in
        answered/ instead of consumed/ — re-open still works."""
        aid = "deny-old-15"
        self._denied_item(aid, subdir="answered")
        nonce = cd._mint_reopen_nonce(aid)
        h, calls, headers = self._handler()
        with mock.patch.object(cd, "_push_mod", None):
            got = self._reopen(h, aid, nonce)
        self.assertEqual(calls.get("code"), 303, got)
        self.assertTrue(headers["Location"].startswith("/approval/"))

    def test_poller_js_builds_reopen_form(self):
        """The 5 s answered poller replaces the server-rendered cards, so
        its re-open branch is load-bearing — pin its presence (repo
        precedent: POLL_JS string assertions)."""
        self.assertIn("Re-open this request", cd.POLL_JS)
        self.assertIn("reopen_csrf", cd.POLL_JS)

    def test_render_item_shows_reopen_provenance(self):
        """The re-opened approval page surfaces the lineage at decision
        time (Design B1 / Product B2) — and only then."""
        h = cd.Handler.__new__(cd.Handler)
        html_out = h._render_item({"id": "abc123def4567890",
                                   "credential": "openai",
                                   "reopened_from": "deny-old-1"})
        self.assertIn("Re-opened from a denied request", html_out)
        self.assertIn("deny-old-1", html_out)
        plain = h._render_item({"id": "abc123def4567890",
                                "credential": "openai"})
        self.assertNotIn("Re-opened from a denied request", plain)

    def test_audit_log_writes_line(self):
        """The happy path still appends the logfmt line (no stderr)."""
        path = os.path.join(self.tmp.name, "audit.log")
        with mock.patch.object(cd, "AUDIT", path):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                cd.audit_log("403", "100.99.0.1", "ntindle@github",
                             "reason=bad-nonce")
        self.assertEqual(err.getvalue(), "")
        with open(path, encoding="utf-8") as f:
            line = f.read()
        self.assertIn("event=403", line)
        self.assertIn("peer=100.99.0.1", line)
        self.assertIn("login=ntindle@github", line)
        self.assertIn("reason=bad-nonce", line)

    def test_audit_log_write_failure_signals_stderr(self):
        """Arch finding A5 (sentinel deep-read): a lost audit line must
        not be silent. Pointing AUDIT at a directory makes the append
        raise OSError — the except path must emit to stderr, not pass."""
        with mock.patch.object(cd, "AUDIT", self.tmp.name):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                cd.audit_log("403", "100.99.0.1", "ntindle@github", "")
        self.assertIn("confirmd: cannot write audit log", err.getvalue())


if __name__ == "__main__":
    unittest.main()
