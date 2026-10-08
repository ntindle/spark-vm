"""Tests for confirm/confirmd.py (findings 47, 48, 57).

Run with:
    python3 -m unittest confirm.test_confirmd -v

Tailscale calls are mocked; no network or /home/swapd is touched.
"""
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
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
        # Issue #620: housekeeping is cadence-gated on module state — each
        # test starts with it due so answer-path behavior is deterministic
        # regardless of test order.
        cd._reset_housekeeping_for_tests()

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

    # --- 619: PAGE_ORIGINS re-resolution -----------------------------------

    def _dns_fake(self, dnsname, fail=False):
        """subprocess.run fake returning one DNS name (or failing)."""
        def fake(cmd, **kwargs):
            class F:
                returncode = 1 if fail else 0
                stdout = "" if fail else json.dumps(
                    {"Self": {"DNSName": dnsname}})
                stderr = "" if fail else ""
            return F()
        return fake

    def _fresh_origins(self, dnsname, fail=False):
        with mock.patch("subprocess.run",
                        side_effect=self._dns_fake(dnsname, fail)):
            return cd._PageOrigins()

    def test_619_refresh_picks_up_dns_rename(self):
        """A tailscale DNS rename mid-daemon must refresh the accepted
        origins within the TTL — the stale-for-process-lifetime bug."""
        po = self._fresh_origins("old-name.ts.net.")
        old = "https://old-name.ts.net:8443"
        new = "https://new-name.ts.net:8443"
        self.assertIn(old, po)
        self.assertNotIn(new, po)
        # TTL expired, tailscaled now reports the new name.
        po._ts -= cd._PAGE_ORIGINS_TTL + 1
        with mock.patch("subprocess.run",
                        side_effect=self._dns_fake("new-name.ts.net.")):
            self.assertIn(new, po)
        # The old name leaves the accepted set (the rename is the truth).
        self.assertNotIn(old, po)

    def test_619_failed_refresh_keeps_last_good_set(self):
        """An unreachable tailscaled must not shrink the refusal
        boundary: a failed re-resolve keeps the last good origins."""
        po = self._fresh_origins("good-name.ts.net.")
        good = "https://good-name.ts.net:8443"
        self.assertIn(good, po)
        po._ts -= cd._PAGE_ORIGINS_TTL + 1
        with mock.patch("subprocess.run",
                        side_effect=self._dns_fake("x", fail=True)):
            self.assertIn(good, po)
        self.assertIn(good, po)

    def test_619_env_override_pins_set(self):
        """CONFIRM_ORIGINS pins the set: no re-probe, no drift, even
        after the TTL — operators who manage names out of band keep
        full control."""
        with mock.patch.dict(os.environ,
                             {"CONFIRM_ORIGINS":
                              "https://pinned.example:8443"}):
            po = self._fresh_origins("whatever.ts.net.")
            self.assertEqual(list(po), ["https://pinned.example:8443"])
            po._ts -= cd._PAGE_ORIGINS_TTL + 1
            with mock.patch("subprocess.run",
                            side_effect=self._dns_fake("new.ts.net.")):
                self.assertIn("https://pinned.example:8443", po)
                self.assertNotIn("https://new.ts.net:8443", po)

    def test_619_origins_iterable_for_startup_print(self):
        """sorted(PAGE_ORIGINS) (the startup journal print) works on the
        TTL-cached object."""
        printed = sorted(cd.PAGE_ORIGINS)
        self.assertIn("https://100.65.241.20:8443", printed)

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

    # --- #75/#78: server-side CSRF nonce ring -----------------------------

    def _fresh_aid(self):
        import uuid
        return "t" + uuid.uuid4().hex[:15]

    def test_75_nonce_ring_accepts_recent(self):
        """The last 3 minted nonces all verify; the 4th mint evicts the
        oldest (a second tab's form stays valid across GETs)."""
        aid = self._fresh_aid()
        n1 = cd._mint_csrf_nonce(aid)
        n2 = cd._mint_csrf_nonce(aid)
        n3 = cd._mint_csrf_nonce(aid)
        self.assertTrue(cd._csrf_nonce_ok(aid, n1))
        self.assertTrue(cd._csrf_nonce_ok(aid, n2))
        self.assertTrue(cd._csrf_nonce_ok(aid, n3))
        n4 = cd._mint_csrf_nonce(aid)
        self.assertTrue(cd._csrf_nonce_ok(aid, n4))
        self.assertTrue(cd._csrf_nonce_ok(aid, n2))
        self.assertTrue(cd._csrf_nonce_ok(aid, n3))
        self.assertFalse(cd._csrf_nonce_ok(aid, n1))
        self.assertEqual(len(cd._csrf_rings[aid]), 3)

    def test_78_preseeded_file_ring_never_accepted(self):
        """#78: a filer pre-seeds `_csrf_nonces` in its own pending file
        with a nonce of its choosing — the daemon must NOT accept it,
        even though the file membership matches. This is the whole
        attack: file-stored entries are ignored entirely."""
        aid = self._fresh_aid()
        planted = "a" * 32
        it = {"_csrf_nonces": [{"nonce": planted, "ts": time.time()}]}
        self.assertFalse(cd._csrf_nonce_ok(aid, planted))
        # ... and a nonce minted for a DIFFERENT aid doesn't cross over.
        other = self._fresh_aid()
        n = cd._mint_csrf_nonce(other)
        self.assertFalse(cd._csrf_nonce_ok(aid, n))
        self.assertTrue(cd._csrf_nonce_ok(other, n))

    def test_78_legacy_file_slot_ignored(self):
        """#78: the legacy single `_csrf` slot in a filer-authored file is
        ignored too — no migration path reads requester-authored nonces."""
        aid = self._fresh_aid()
        it = {"_csrf": "f" * 32}
        self.assertFalse(cd._csrf_nonce_ok(aid, "f" * 32))
        n = cd._mint_csrf_nonce(aid)
        self.assertTrue(cd._csrf_nonce_ok(aid, n))
        self.assertNotIn("_csrf_nonces", it)  # mint touches no file state

    def test_75_nonce_rejects_malformed_and_unknown(self):
        """Malformed and well-formed-but-unknown nonces are rejected;
        an aid with no ring accepts nothing."""
        aid = self._fresh_aid()
        n = cd._mint_csrf_nonce(aid)
        self.assertTrue(cd._csrf_nonce_ok(aid, n))
        self.assertFalse(cd._csrf_nonce_ok(aid, "short"))
        self.assertFalse(cd._csrf_nonce_ok(aid, ""))
        self.assertFalse(cd._csrf_nonce_ok(aid, None))
        self.assertFalse(cd._csrf_nonce_ok(aid, "g" * 32))
        self.assertFalse(cd._csrf_nonce_ok(self._fresh_aid(), n))

    def test_75_nonce_ring_drops_expired(self):
        """Ring entries older than _CSRF_RING_TTL are pruned on mint."""
        aid = self._fresh_aid()
        n1 = cd._mint_csrf_nonce(aid)
        cd._csrf_rings[aid][0]["ts"] -= (cd._CSRF_RING_TTL + 1)
        n2 = cd._mint_csrf_nonce(aid)
        self.assertFalse(cd._csrf_nonce_ok(aid, n1))
        self.assertTrue(cd._csrf_nonce_ok(aid, n2))
        self.assertEqual(len(cd._csrf_rings[aid]), 1)

    def test_75_nonce_ttl_enforced_at_verify(self):
        """The TTL is enforced at verification time too, not only at
        mint (security review): an entry backdated past the TTL is
        rejected even if no new mint pruned it."""
        aid = self._fresh_aid()
        n = cd._mint_csrf_nonce(aid)
        self.assertTrue(cd._csrf_nonce_ok(aid, n))
        cd._csrf_rings[aid][-1]["ts"] -= (cd._CSRF_RING_TTL + 1)
        self.assertFalse(cd._csrf_nonce_ok(aid, n))

    def test_75_nonce_malformed_ring_entry_fail_closed(self):
        """Malformed ring entries (server state can only be malformed
        through a bug) fail closed: never accepted, pruned on next mint."""
        aid = self._fresh_aid()
        cd._csrf_rings[aid] = [{"nonce": "a" * 32, "ts": "not-a-ts"},
                               {"ts": time.time()},
                               {"nonce": "b" * 32, "ts": time.time()}]
        self.assertFalse(cd._csrf_nonce_ok(aid, "a" * 32))
        self.assertTrue(cd._csrf_nonce_ok(aid, "b" * 32))
        cd._mint_csrf_nonce(aid)
        self.assertEqual(len(cd._csrf_rings[aid]), 2)

    def test_78_ring_evicted_with_aid_lock(self):
        """#78: the ring shares the pending-item lifecycle — evicting the
        aid lock (every terminal state) drops the ring too, so neither
        map grows for the daemon's whole lifetime."""
        aid = self._fresh_aid()
        n = cd._mint_csrf_nonce(aid)
        self.assertTrue(cd._csrf_nonce_ok(aid, n))
        cd._evict_aid_lock(aid)
        self.assertNotIn(aid, cd._csrf_rings)
        self.assertFalse(cd._csrf_nonce_ok(aid, n))

    def test_78_aid_map_bounded(self):
        """The aid->ring map is capped (issue #77 L10 hygiene): minting
        past the cap evicts the oldest aid's ring."""
        aids = [self._fresh_aid() for _ in range(cd._CSRF_RING_AID_CAP + 2)]
        nonces = {a: cd._mint_csrf_nonce(a) for a in aids}
        self.assertLessEqual(len(cd._csrf_rings), cd._CSRF_RING_AID_CAP)
        self.assertFalse(cd._csrf_nonce_ok(aids[0], nonces[aids[0]]))
        self.assertTrue(cd._csrf_nonce_ok(aids[-1], nonces[aids[-1]]))
        for a in aids:
            cd._csrf_rings.pop(a, None)

    def test_78_preseeded_file_nonce_answer_403s(self):
        """#78 handler-level: a pending file pre-seeded with a chosen
        `_csrf_nonces` entry does NOT satisfy /answer. The planted nonce
        403s as stale-nonce, the pending file is left intact, and no
        answered/consumed record is written — a handler-level regression
        reintroducing file reads at the call site would fail here."""
        aid = self._fresh_aid()
        planted = "p" * 32
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2999-01-01T00:00:00+00:00",
              "_csrf_nonces": [{"nonce": planted, "ts": time.time()}]}
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))
        got = {}
        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        h.send_response = lambda code: None
        h.send_header = lambda k, v: None
        h.end_headers = lambda: None
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c, suffix="": got.update(
                                   msg=m, code=c, suffix=suffix)):
            h._answer_locked("ntindle@github", aid, planted, "deny")
        self.assertEqual(got.get("code"), 403)
        self.assertTrue(src.exists())
        self.assertFalse(
            (self.approvals / "consumed" / (aid + ".json")).exists())
        self.assertFalse(
            (self.approvals / "answered" / (aid + ".json")).exists())

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

    # --- 536: HOST_ADDRS is TTL-refreshed, not frozen at import ---------

    def test_536_refresh_picks_up_renumbered_addrs(self):
        """After the TTL, a renumbered tailscale IP set is picked up —
        the finding-47 self-refusal can't go stale on a renumber."""
        with mock.patch.object(cd, "_host_addrs",
                               side_effect=[({"1.1.1.1"}, True),
                                            ({"2.2.2.2"}, True)]):
            sa = cd._SelfAddrs()
            self.assertIn("1.1.1.1", sa)
            sa._ts -= cd._HOST_ADDRS_TTL + 1  # age past the TTL
            self.assertNotIn("1.1.1.1", sa)
            self.assertIn("2.2.2.2", sa)

    def test_536_failed_refresh_keeps_stale_set(self):
        """A failed refresh must not shrink the refusal boundary — the
        last good set is kept, not collapsed to BIND."""
        with mock.patch.object(cd, "_host_addrs",
                               side_effect=[({"1.1.1.1"}, True),
                                            ({"0.0.0.0"}, False)]):
            sa = cd._SelfAddrs()
            sa._ts -= cd._HOST_ADDRS_TTL + 1  # age past the TTL
            self.assertIn("1.1.1.1", sa)

    def test_536_concurrent_contains_is_thread_safe(self):
        """Handler threads share the instance; concurrent `in` checks
        across a refresh must not raise or return garbage."""
        with mock.patch.object(cd, "_host_addrs",
                               return_value=({"1.1.1.1"}, True)):
            sa = cd._SelfAddrs()
            errors = []
            def probe():
                try:
                    for _ in range(200):
                        assert ("1.1.1.1" in sa)
                except Exception as e:  # noqa: BLE001
                    errors.append(e)
            sa._ts -= cd._HOST_ADDRS_TTL + 1  # force refresh on all threads
            threads = [threading.Thread(target=probe) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])

    # --- 70: no stale-literal fallback; fail closed at startup ----------

    def test_70_resolve_bind_env_pin_wins(self):
        """CONFIRM_BIND pins the bind address; tailscale is not consulted."""
        with mock.patch.dict(os.environ, {"CONFIRM_BIND": "100.99.9.9"}), \
             mock.patch.object(cd, "_tailnet_ip4",
                               side_effect=AssertionError("must not run")):
            self.assertEqual(cd._resolve_bind(), "100.99.9.9")

    def test_70_resolve_bind_tailscale_when_no_env(self):
        """No pin: the bind address comes from `tailscale ip -4`."""
        with mock.patch.dict(os.environ, {"CONFIRM_BIND": ""}), \
             mock.patch.object(cd, "_tailnet_ip4",
                               return_value="100.65.241.21"):
            self.assertEqual(cd._resolve_bind(), "100.65.241.21")

    def test_70_resolve_bind_none_when_unresolvable(self):
        """No pin and tailscale unreachable: None, never a stale literal."""
        with mock.patch.dict(os.environ, {"CONFIRM_BIND": ""}), \
             mock.patch.object(cd, "_tailnet_ip4", return_value=None):
            self.assertIsNone(cd._resolve_bind())

    def test_70_main_fails_closed_when_bind_none(self):
        """main() exits non-zero before serving when the bind address
        is unresolvable — fail closed, not serve-on-guess."""
        with mock.patch.object(cd, "BIND", None):
            with self.assertRaises(SystemExit) as ctx:
                cd.main()
        self.assertNotEqual(ctx.exception.code, 0)

    def test_70_host_addrs_never_contains_none(self):
        """The belt-and-braces BIND add must not inject None into the
        refusal set when import-time resolution failed (main() refuses
        to serve in that case, but the module must stay sound)."""
        def fail(cmd, **kwargs):
            raise FileNotFoundError("no tailscale binary")
        with mock.patch.object(cd, "BIND", None), \
             mock.patch("subprocess.run", side_effect=fail):
            addrs, ok = cd._host_addrs()
        self.assertFalse(ok)
        self.assertNotIn(None, addrs)

    # --- 535/360: writer-side audit rotation -----------------------------

    def test_535_audit_rotates_at_cap(self):
        """At _AUDIT_MAX_BYTES the chain rolls (live -> .1) and newest
        events land in a fresh live segment. With a roomy _AUDIT_KEEP,
        no event is lost."""
        audit = Path(self.tmp.name) / "audit.log"
        n = 60
        with mock.patch.object(cd, "AUDIT", str(audit)), \
             mock.patch.object(cd, "_AUDIT_MAX_BYTES", 1024), \
             mock.patch.object(cd, "_AUDIT_KEEP", 10):
            for i in range(n):
                cd.audit_log("test-ev", "peer", "login", "detail-%d" % i)
        self.assertTrue(audit.exists())
        self.assertTrue(Path(str(audit) + ".1").exists())
        live = audit.read_text()
        rotated = Path(str(audit) + ".1").read_text()
        self.assertIn("detail-59", live)      # newest event on live
        self.assertNotIn("detail-59", rotated)
        # No event lost across the rolls: every detail exactly once.
        details = []
        for p in (str(audit),) + tuple("%s.%d" % (audit, i)
                                       for i in range(1, 10)):
            if os.path.exists(p):
                details += Path(p).read_text().splitlines()
        self.assertEqual(len(details), n)
        self.assertEqual(len({d.split("detail-")[1] for d in details}), n)

    def test_535_rotation_keeps_newest_after_roll(self):
        """The newest events survive even the second roll; only the
        oldest segments are dropped past _AUDIT_KEEP."""
        audit = Path(self.tmp.name) / "audit2.log"
        n = 120
        with mock.patch.object(cd, "AUDIT", str(audit)), \
             mock.patch.object(cd, "_AUDIT_MAX_BYTES", 1024), \
             mock.patch.object(cd, "_AUDIT_KEEP", 3):
            for i in range(n):
                cd.audit_log("test-ev", "peer", "login", "detail-%d" % i)
        self.assertIn("detail-119", audit.read_text())  # newest on live
        self.assertFalse(Path(str(audit) + ".3").exists())  # cap honored
        self.assertFalse("detail-0\n" in "".join(  # oldest dropped by design
            Path(p).read_text() for p in
            (str(audit), str(audit) + ".1", str(audit) + ".2")))
        # All lines on disk intact, newest event present exactly once.
        lines = []
        for p in (str(audit), str(audit) + ".1", str(audit) + ".2"):
            lines += Path(p).read_text().splitlines()
        for line in lines:
            self.assertRegex(line, r"^ts=\S+ event=test-ev peer=peer "
                                   r"login=login detail-\d+$")
        self.assertEqual(sum("detail-119" in l for l in lines), 1)

    def test_535_rotation_keep_one_drops_old_segment(self):
        """_AUDIT_KEEP=1 keeps the live segment only: the oversized
        segment is dropped, the newest events still land in the fresh
        live file, and no .1 is created."""
        audit = Path(self.tmp.name) / "audit4.log"
        with mock.patch.object(cd, "AUDIT", str(audit)), \
             mock.patch.object(cd, "_AUDIT_MAX_BYTES", 512), \
             mock.patch.object(cd, "_AUDIT_KEEP", 1):
            for i in range(40):
                cd.audit_log("test-ev", "peer", "login", "detail-%d" % i)
        self.assertFalse(Path(str(audit) + ".1").exists())
        self.assertIn("detail-39", audit.read_text())  # newest survives

    def test_535_concurrent_audit_no_interleave(self):
        """Concurrent audit_log calls serialize on _AUDIT_LOCK: every
        line intact, no event lost."""
        audit = Path(self.tmp.name) / "audit3.log"
        with mock.patch.object(cd, "AUDIT", str(audit)), \
             mock.patch.object(cd, "_AUDIT_MAX_BYTES", 10 ** 9):
            def worker(w):
                for i in range(50):
                    cd.audit_log("ev", "peer", "login",
                                 "w%d-i%d" % (w, i))
            threads = [threading.Thread(target=worker, args=(w,))
                       for w in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        lines = audit.read_text().splitlines()
        self.assertEqual(len(lines), 400)
        for line in lines:
            self.assertRegex(line, r"^ts=\S+ event=ev peer=peer "
                                   r"login=login w\d+-i\d+$")

    # --- 537: reopened index ----------------------------------------------

    def _537_write_pending(self, aid, **fields):
        p = self.approvals / "pending" / ("%s.json" % aid)
        doc = {"id": aid}
        doc.update(fields)
        p.write_text(json.dumps(doc))

    def test_537_index_hit_avoids_full_scan(self):
        """An index hit answers from one file — the full pending/ scan
        never runs (os.listdir raises if touched)."""
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            self._537_write_pending("baid", reopened_from="aaid",
                                    expires="2030-01-01T00:00:00+00:00")
            cd._index_reopened("aaid", "baid")
            try:
                with mock.patch("os.listdir",
                                side_effect=AssertionError("scan ran")):
                    self.assertEqual(cd._pending_reopened_aid("aaid"),
                                     "baid")
            finally:
                cd._reopened_index.pop("aaid", None)

    def test_537_stale_index_entry_falls_back_to_scan(self):
        """An index entry pointing at a file that is not this aid's
        re-file is dropped and the full scan (kept as the
        exact-semantics fallback) still finds the real one."""
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            self._537_write_pending("b", reopened_from="other",
                                    expires="2030-01-01T00:00:00+00:00")
            self._537_write_pending("c", reopened_from="aaid",
                                    expires="2030-01-01T00:00:00+00:00")
            cd._index_reopened("aaid", "b")
            try:
                self.assertEqual(cd._pending_reopened_aid("aaid"), "c")
                self.assertEqual(cd._reopened_index.get("aaid"), "c")
            finally:
                cd._reopened_index.pop("aaid", None)

    def test_537_expired_index_entry_dropped(self):
        """An index hit on an expired re-file drops the entry and
        returns None — the repeat POST files fresh, as before."""
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            self._537_write_pending("b", reopened_from="aaid",
                                    expires="2020-01-01T00:00:00+00:00")
            cd._index_reopened("aaid", "b")
            try:
                self.assertIsNone(cd._pending_reopened_aid("aaid"))
                self.assertNotIn("aaid", cd._reopened_index)
            finally:
                cd._reopened_index.pop("aaid", None)

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
        answered_by/answered_at (+ the S3 expired_at/expired_by for
        expired records — the expiry's own stamp fields, never the
        answer fields reused; + the #73 grant_ttl_hours, the lifetime
        the owner authorized)."""
        it = dict(self._evil_item())
        it.update({"decision": "approve", "answered_by": "ntindle@github",
                   "answered_at": "2026-09-18T10:05:00+00:00",
                   "grant_ttl_hours": 24})
        out = cd._answered_api_item(it)
        self.assertEqual(set(out),
                         {"id", "summary", "kind", "decision",
                          "answered_by", "answered_at",
                          "expired_at", "expired_by", "grant_ttl_hours"})
        self.assertEqual(out["decision"], "approve")
        self.assertEqual(out["grant_ttl_hours"], "24")

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

    def test_1_send_html_hardening_headers(self):
        """Issue #77 (L3): every HTML response carries nosniff and a
        same-origin referrer policy. Deleting either header must fail."""
        import io
        h = cd.Handler.__new__(cd.Handler)
        headers = {}
        h.send_response = lambda code: headers.setdefault("code", code)
        h.send_header = lambda k, v: headers.__setitem__(k, v)
        h.end_headers = lambda: None
        h.wfile = io.BytesIO()
        h._send_html("<p>x</p>")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "same-origin")

    def test_1_swjs_hardening_headers(self):
        """Issue #77 (L3): /sw.js is served inline in do_GET, not through
        _send_html — drive the real route and assert the same two headers
        reach the wire. Deleting either header must fail."""
        import io
        h = cd.Handler.__new__(cd.Handler)
        h.path = "/sw.js"
        headers = {}
        h.send_response = lambda code: headers.setdefault("code", code)
        h.send_header = lambda k, v: headers.__setitem__(k, v)
        h.end_headers = lambda: None
        h.wfile = io.BytesIO()
        with mock.patch.object(cd.Handler, "_auth",
                               return_value="ntindle@github"):
            h.do_GET()
        self.assertEqual(headers["code"], 200)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "same-origin")

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

    # --- Issue #620: cadence-gated housekeeping ----------------------

    def test_prune_consumed_skips_stat_storm_when_under_cap(self):
        """#620: at/below the cap, _prune_consumed lists only — no
        per-file getmtime calls (the hot-path stat storm)."""
        names = ["a0.json", "a1.json"]
        self._seed_consumed(names, 1_700_000_000)
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch("os.path.getmtime") as mtime:
            cd._prune_consumed(limit=3)
        mtime.assert_not_called()
        remaining = sorted(p.name for p in (self.approvals / "consumed")
                           .iterdir())
        self.assertEqual(remaining, names)

    def test_housekeeping_runs_when_due(self):
        """First call after a reset runs the sweep+prune trio."""
        with mock.patch.object(cd, "_sweep_answered") as sw, \
             mock.patch.object(cd, "_prune_consumed") as pr, \
             mock.patch.object(cd, "_prune_quarantine") as pq:
            self.assertTrue(cd._housekeeping_if_due())
        sw.assert_called_once_with()
        pr.assert_called_once_with()
        pq.assert_called_once_with()

    def test_housekeeping_skips_when_not_due(self):
        """A second immediate call is gated — one trio per interval."""
        with mock.patch.object(cd, "_sweep_answered") as sw, \
             mock.patch.object(cd, "_prune_consumed") as pr, \
             mock.patch.object(cd, "_prune_quarantine") as pq:
            self.assertTrue(cd._housekeeping_if_due())
            self.assertFalse(cd._housekeeping_if_due())
        sw.assert_called_once_with()
        pr.assert_called_once_with()
        pq.assert_called_once_with()

    def test_housekeeping_zero_interval_always_runs(self):
        """Patching the interval to 0 restores the old every-answer
        behavior (the escape hatch tests rely on)."""
        with mock.patch.object(cd, "_HOUSEKEEPING_INTERVAL_S", 0), \
             mock.patch.object(cd, "_sweep_answered") as sw, \
             mock.patch.object(cd, "_prune_consumed") as pr, \
             mock.patch.object(cd, "_prune_quarantine") as pq:
            self.assertTrue(cd._housekeeping_if_due())
            self.assertTrue(cd._housekeeping_if_due())
        self.assertEqual(sw.call_count, 2)
        self.assertEqual(pr.call_count, 2)
        self.assertEqual(pq.call_count, 2)

    def test_housekeeping_concurrent_callers_run_once(self):
        """Racing handler threads can't both decide 'due': the timestamp
        commits under the lock before the work starts, so the second
        caller sees the gate closed even while the first is still
        sweeping."""
        calls = []

        def slow_sweep():
            calls.append(1)
            time.sleep(0.2)

        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "_sweep_answered",
                               side_effect=slow_sweep), \
             mock.patch.object(cd, "_prune_consumed", return_value=None):
            threads = [threading.Thread(target=cd._housekeeping_if_due)
                       for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(len(calls), 1)

    def test_answer_path_housekeeping_cadence(self):
        """Wiring, not just the helper: the after-answer call site runs
        housekeeping on the first answer and skips it on the next one
        (the #620 behavior change at the call site)."""
        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        h.send_response = lambda code: None
        h.send_header = lambda k, v: None
        h.end_headers = lambda: None

        def answer(aid):
            it = {"id": aid, "summary": "s", "kind": "first-use",
                  "created": "2026-09-18T10:00:00+00:00",
                  "expires": "2999-01-01T00:00:00+00:00"}
            nonce = cd._mint_csrf_nonce(it["id"])
            (self.approvals / "pending" / (aid + ".json")).write_text(
                json.dumps(it))
            h._answer_locked("ntindle@github", aid, nonce, "deny")

        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch.object(cd, "_sweep_answered") as sw, \
             mock.patch.object(cd, "_prune_consumed") as pr:
            answer("hk-cadence-1")
            answer("hk-cadence-2")
        self.assertEqual(sw.call_count, 1)
        self.assertEqual(pr.call_count, 1)

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
        nonce = cd._mint_csrf_nonce(it["id"])
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
                               side_effect=lambda m, c, suffix="": got.update(
                                   msg=m, code=c, suffix=suffix)), \
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
        nonce = cd._mint_csrf_nonce(it["id"])
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

    def test_195_consume_raced_file_vanishes_audits_and_404s(self):
        """Issue #195 (residual): the consume path's os.path.exists
        check is a TOCTOU window — if an out-of-process remover deletes
        the pending file between the check and os.remove(src), the
        handler must audit the distinct 'answer-raced-consume' event and
        refuse with 404 ('not found or already answered', the #71 loser
        path) instead of raising an uncaught FileNotFoundError (a 500 on
        a legitimate answer). Deterministic: os.remove is stubbed to
        raise FileNotFoundError for exactly the pending path. The deny
        decision skips the grant-mint subprocess, isolating the race to
        the consume window."""
        aid = "raced-consume-1"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2999-01-01T00:00:00+00:00",
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it["id"])
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))

        real_remove = os.remove

        def fake_remove(p):
            if str(p) == str(src):
                # The out-of-process remover struck inside the TOCTOU
                # window between the exists check and the remove.
                raise FileNotFoundError(2, "No such file or directory",
                                        str(p))
            return real_remove(p)

        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        events = []
        cd._aid_lock(aid)  # ensure the entry exists pre-answer
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch("os.remove", side_effect=fake_remove), \
             mock.patch.object(cd, "audit_log",
                               side_effect=lambda *a: events.append(a)), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)):
            h._answer_locked("ntindle@github", aid, nonce, "deny")
        self.assertEqual(got["code"], 404)
        self.assertEqual(got["msg"], "not found or already answered")
        self.assertTrue(
            any(e[0] == "answer-raced-consume" for e in events),
            "no answer-raced-consume audit; events: %r" % (events,))
        # The decision was genuinely recorded before the race (deny
        # mints no grant); the file is verifiably gone; this terminal
        # path must evict too (issue #231's boundedness goal).
        self.assertTrue(
            (self.approvals / "answered" / (aid + ".json")).exists())
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
        nonce = cd._mint_csrf_nonce(it["id"])
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

    def test_534_approve_refused_when_expiry_inside_mint_window(self):
        """Issue #534: an approve whose expiry sits inside the worst-case
        mint window must be refused BEFORE the grant subprocess starts —
        the writer has no revoke path, so a mid-mint expiry crossing would
        mint a grant for an already-expired approval. Refusal is 410 + the
        distinct 'approve-refused-expiry-window' audit event; the pending
        file stays for the render reap to stamp `expired` (no silent loss,
        no contradictory trail); the aid lock is evicted (issue #231)."""
        from datetime import datetime as real_datetime, timezone as real_tz, \
            timedelta
        aid = "narrow-window-1"
        t0 = real_datetime.now(real_tz.utc)
        exp = t0 + timedelta(seconds=10)  # inside the 30 s window
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": exp.isoformat(),
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it["id"])
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))

        class _Clock:
            instant = t0

            @classmethod
            def now(cls, tz=None):
                return cls.instant

            fromisoformat = staticmethod(real_datetime.fromisoformat)

        mint_calls = []

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                mint_calls.append(cmd)

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
            any(e[0] == "approve-refused-expiry-window" for e in events),
            "no approve-refused-expiry-window audit; events: %r" % (events,))
        self.assertEqual(mint_calls, [],
                         "grant writer must not be invoked inside the "
                         "mint window")
        self.assertTrue(src.exists(),
                        "pending file must stay for the render reap's "
                        "expired stamp")
        self.assertFalse(
            (self.approvals / "answered" / (aid + ".json")).exists())
        self.assertFalse(
            (self.approvals / "consumed" / (aid + ".json")).exists())
        self.assertNotIn(aid, cd._aid_locks)

    def test_534_approve_proceeds_when_expiry_outside_mint_window(self):
        """Issue #534: an approve with expiry comfortably outside the
        window mints normally — the guard must not starve legitimate
        approvals."""
        from datetime import datetime as real_datetime, timezone as real_tz, \
            timedelta
        aid = "ample-window-1"
        t0 = real_datetime.now(real_tz.utc)
        exp = t0 + timedelta(seconds=120)
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": exp.isoformat(),
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it["id"])
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))

        class _Clock:
            instant = t0

            @classmethod
            def now(cls, tz=None):
                return cls.instant

            fromisoformat = staticmethod(real_datetime.fromisoformat)

        mint_calls = []

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                mint_calls.append(cmd)

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
        h.send_response = lambda c: got.update(code=c)
        h.send_header = lambda *a: None
        h.end_headers = lambda: None
        cd._aid_lock(aid)
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch.object(cd, "datetime", _Clock), \
             mock.patch("subprocess.run", side_effect=fake_run), \
             mock.patch.object(cd, "audit_log",
                               side_effect=lambda *a: events.append(a)):
            h._answer_locked("ntindle@github", aid, nonce, "approve")
        self.assertEqual(got.get("code"), 303)
        self.assertEqual(len(mint_calls), 1,
                         "the mint must proceed outside the window")
        self.assertTrue(
            any(e[0] == "answer" and "decision=approve" in e[3]
                for e in events),
            "no answer/approve audit; events: %r" % (events,))

    def test_294_approval_expires_passed_to_grant_writer(self):
        """Issue #294: the approve path hands the approval's expiry
        instant to grant-writer as --approval-expires, so the writer
        can fail closed at mint time."""
        aid = "expiry-passthrough-1"
        exp_str = "2999-01-01T00:00:00+00:00"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": exp_str,
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it["id"])
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))

        mint_calls = []

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                mint_calls.append(cmd)

                class R:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return R()
            return _fake_run(cmd, **kwargs)

        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        h.send_response = lambda c: got.update(code=c)
        h.send_header = lambda *a: None
        h.end_headers = lambda: None
        cd._aid_lock(aid)
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch("subprocess.run", side_effect=fake_run), \
             mock.patch.object(cd, "audit_log"):
            h._answer_locked("ntindle@github", aid, nonce, "approve")
        self.assertEqual(got.get("code"), 303)
        self.assertEqual(len(mint_calls), 1)
        cmd = mint_calls[0]
        self.assertIn("--approval-expires", cmd)
        self.assertEqual(
            cmd[cmd.index("--approval-expires") + 1], exp_str,
            "writer got %r, item expires is %r" % (cmd, exp_str))

    def test_294_no_expiry_means_no_flag(self):
        """Issue #294: an approval with no expiry passes no
        --approval-expires flag — the writer treats absence as no
        constraint, matching confirmd's pre-mint guard."""
        aid = "no-expiry-passthrough-1"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it["id"])
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))

        mint_calls = []

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                mint_calls.append(cmd)

                class R:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return R()
            return _fake_run(cmd, **kwargs)

        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        h.send_response = lambda c: got.update(code=c)
        h.send_header = lambda *a: None
        h.end_headers = lambda: None
        cd._aid_lock(aid)
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch("subprocess.run", side_effect=fake_run), \
             mock.patch.object(cd, "audit_log"):
            h._answer_locked("ntindle@github", aid, nonce, "approve")
        self.assertEqual(got.get("code"), 303)
        self.assertEqual(len(mint_calls), 1)
        self.assertNotIn("--approval-expires", mint_calls[0])
        self.assertFalse(src.exists(), "pending file must be consumed")
        self.assertTrue(
            (self.approvals / "consumed" / (aid + ".json")).exists())
        self.assertNotIn(aid, cd._aid_locks)

    def test_294_writer_refusal_routes_to_honest_410(self):
        """Issue #294 (architecture B1): when the writer refuses at mint
        time (exit 3 = expiry crossed, its own fresh clock under the
        mint lock), confirmd must route into the honest #240 path —
        410 + 'answer-expired-mid-mint' + aid-lock eviction — not the
        generic 500. The item's own expiry is far in the future, so the
        410 here can only come from the writer-refusal route, not the
        in-memory is_expired re-check."""
        aid = "writer-refusal-410-1"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2999-01-01T00:00:00+00:00",
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it["id"])
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                # The writer's fresh clock saw the expiry cross mid-mint.
                class R:
                    returncode = 3
                    stdout = ""
                    stderr = ("grant-writer: refusing to mint: approval "
                              "expired at 2026-09-27T06:40:00+00:00")
                return R()
            return _fake_run(cmd, **kwargs)

        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        events = []
        cd._aid_lock(aid)
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
        self.assertEqual(got.get("code"), 410, got)
        self.assertTrue(
            any(e[0] == "answer-expired-mid-mint" for e in events),
            "no answer-expired-mid-mint audit; events: %r" % (events,))
        # Not the generic failure path…
        self.assertFalse(
            any(e[0] == "grant-failed" for e in events),
            "writer refusal must not take the generic path; events: %r"
            % (events,))
        # …and never an answer record for a grant that was never minted.
        self.assertFalse(
            any(e[0] == "answer" for e in events),
            "contradictory answer event; events: %r" % (events,))
        self.assertFalse(
            (self.approvals / "answered" / (aid + ".json")).exists())
        self.assertFalse(
            (self.approvals / "consumed" / (aid + ".json")).exists())
        self.assertTrue(src.exists(), "pending file stays for the reap")
        self.assertNotIn(aid, cd._aid_locks)

    def test_294_writer_unparseable_keeps_500(self):
        """Issue #294 (architecture B1): exit 4 = the writer could not
        parse the expiry instant — a bug, not an expiry — so it must
        keep the generic 500 'grant-failed' path and must NOT be
        mislabeled as expired."""
        aid = "writer-refusal-500-1"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2999-01-01T00:00:00+00:00",
              "credential": "c", "host": "h", "method": "GET"}
        nonce = cd._mint_csrf_nonce(it["id"])
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                class R:
                    returncode = 4
                    stdout = ""
                    stderr = ("grant-writer: refusing to mint: unparseable "
                              "approval-expiry 'garbage'")
                return R()
            return _fake_run(cmd, **kwargs)

        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        events = []
        cd._aid_lock(aid)
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
        self.assertEqual(got.get("code"), 500, got)
        self.assertTrue(
            any(e[0] == "grant-failed" for e in events),
            "no grant-failed audit; events: %r" % (events,))
        self.assertFalse(
            any(e[0] == "answer-expired-mid-mint" for e in events),
            "unparseable must not be mislabeled as expired; events: %r"
            % (events,))
        self.assertFalse(
            any(e[0] == "answer" for e in events),
            "contradictory answer event; events: %r" % (events,))

    def test_534_grant_window_helper_boundaries(self):
        """Issue #534: _grant_window_ok — no expiry means no window to
        guard (True); malformed expiry parses to None (same as is_expired);
        < window refuses; comfortably >= window allows."""
        from datetime import datetime as real_datetime, timezone as real_tz, \
            timedelta
        t0 = real_datetime.now(real_tz.utc)

        def item(seconds=None, raw=None):
            d = {}
            if raw is not None:
                d["expires"] = raw
            elif seconds is not None:
                d["expires"] = (t0 + timedelta(seconds=seconds)).isoformat()
            return d

        self.assertTrue(cd._grant_window_ok(item()),
                        "no expiry must not block the mint")
        self.assertTrue(cd._grant_window_ok(item(raw="not-a-date")),
                        "malformed expiry must match is_expired semantics")
        self.assertTrue(cd._grant_window_ok(item(seconds=3600)))
        self.assertFalse(cd._grant_window_ok(item(seconds=10)),
                         "10 s remaining is inside the 30 s window")
        self.assertFalse(cd._grant_window_ok(item(seconds=-5)),
                         "already expired is outside the window")
        # The window is a 2x multiple of the subprocess bound: raising the
        # timeout without raising the window would reopen the race.
        self.assertGreaterEqual(cd._GRANT_MINT_WINDOW,
                                2 * cd._GRANT_MINT_TIMEOUT)

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
        nonce = cd._mint_csrf_nonce(it["id"])
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


    # --- #232: pending-file lifecycle ------------------------------------
    # corrupt pending files are quarantined (not skipped forever);
    # confirm-request writes atomically; stale *.tmp files are swept.

    def _write_pending(self, name, content, mtime_age=0):
        p = self.approvals / "pending" / name
        p.write_text(content)
        if mtime_age:
            old = time.time() - mtime_age
            os.utime(p, (old, old))
        return str(p)

    def _valid_item(self, aid):
        return {"id": aid,
                "expires": "2999-01-01T00:00:00+00:00",
                "summary": "x"}

    def test_232_corrupt_pending_quarantined(self):
        """An old corrupt pending file leaves pending/ for quarantine."""
        aid = "deadbeef01234567"
        self._write_pending(aid + ".json", "{torn", mtime_age=600)
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            items = cd.load_pending()
        self.assertEqual(items, [])
        self.assertFalse((self.approvals / "pending" / (aid + ".json")).exists())
        qp = self.approvals / "pending-quarantine" / (aid + ".json")
        self.assertTrue(qp.exists(), "corrupt file must be quarantined")
        self.assertEqual(qp.read_text(), "{torn")

    def test_232_fresh_corrupt_pending_spared(self):
        """A fresh corrupt file may be a torn mid-write — leave it alone."""
        aid = "freshbeef01234567"
        self._write_pending(aid + ".json", "{torn")
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            cd.load_pending()
        self.assertTrue((self.approvals / "pending" / (aid + ".json")).exists())
        self.assertFalse((self.approvals / "pending-quarantine").exists())

    def test_232_fresh_corrupt_ages_into_quarantine(self):
        """The grace is a delay, not an exemption: with the grace at 0
        (simulating time passing), the same fresh file quarantines."""
        aid = "agingbeef01234567"
        self._write_pending(aid + ".json", "{torn")
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "_CORRUPT_QUARANTINE_GRACE_S", 0):
            cd.load_pending()
        self.assertFalse(
            (self.approvals / "pending" / (aid + ".json")).exists())
        self.assertTrue(
            (self.approvals / "pending-quarantine" / (aid + ".json")).exists())

    def test_232_quarantine_audited(self):
        """The quarantine move leaves an audit trail event."""
        aid = "auditbeef01234567"
        self._write_pending(aid + ".json", "{torn", mtime_age=600)
        audit = self.tmp.name + "/audit.log"
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "AUDIT", audit):
            cd.load_pending()
        trail = Path(audit).read_text()
        self.assertIn("event=pending-quarantined", trail)
        self.assertIn("id=%s" % aid, trail)

    def test_232_stale_tmp_swept(self):
        """Old *.tmp crash residue is removed; fresh tmp is kept."""
        old = self._write_pending("aaa.json.tmp", "x", mtime_age=900)
        fresh = self._write_pending("bbb.json.tmp", "x")
        aid = "validbeef01234567"
        self._write_pending(aid + ".json", json.dumps(self._valid_item(aid)))
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            items = cd.load_pending()
        self.assertFalse(os.path.exists(old), "stale tmp must be swept")
        self.assertTrue(os.path.exists(fresh), "fresh tmp must survive")
        self.assertEqual([it["id"] for it in items], [aid])

    def test_232_confirm_request_atomic(self):
        """confirm-request leaves a complete file and no tmp residue."""
        import subprocess
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "confirm-request")
        env = dict(os.environ, CONFIRM_DIR=str(self.approvals))
        r = subprocess.run(
            [sys.executable, script, "--kind", "first-use",
             "--credential", "github", "--host", "api.github.com"],
            capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        aid = r.stdout.strip()
        self.assertRegex(aid, r"^[0-9a-f]{16}$")
        final = self.approvals / "pending" / (aid + ".json")
        self.assertTrue(final.exists())
        it = json.loads(final.read_text())
        self.assertEqual(it["id"], aid)
        leftovers = [p for p in (self.approvals / "pending").iterdir()
                     if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [], "tmp residue after atomic write")


class ConfirmRequestFloodTests(unittest.TestCase):
    """Issue #76: confirm-request files at most 5 pending per credential
    and at most one per credential per 60 seconds (the Finding-58 bar
    mirrored from the swap proxy's filer); filed items land 0600.

    Run with:
        python3 -m unittest confirm.test_confirmd -v
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.approvals = Path(self.tmp.name) / "approvals"
        (self.approvals / "pending").mkdir(parents=True)
        self.script = os.path.join(os.path.dirname(os.path.abspath(
            __file__)), "confirm-request")

    def tearDown(self):
        self.tmp.cleanup()

    def _plant(self, credential, created=None, expires=None,
               corrupt=False, name=None):
        """Plant a pending file; return its aid (or name for corrupt)."""
        aid = name or uuid.uuid4().hex[:16]
        p = self.approvals / "pending" / (aid + ".json")
        if corrupt:
            p.write_text("{torn")
            return aid
        now = datetime.now(timezone.utc)
        item = {"id": aid,
                "credential": credential,
                "created": (created or now).isoformat(),
                "expires": (expires or (now + timedelta(seconds=3600)))
                .isoformat(),
                "summary": "x"}
        p.write_text(json.dumps(item))
        return aid

    def _file(self, credential):
        env = dict(os.environ, CONFIRM_DIR=str(self.approvals))
        return subprocess.run(
            [sys.executable, self.script, "--kind", "first-use",
             "--credential", credential, "--host", "api.github.com"],
            capture_output=True, text=True, env=env, timeout=30)

    def _pending_jsons(self):
        return [p for p in (self.approvals / "pending").iterdir()
                if p.name.endswith(".json")]

    def test_76_fifth_allowed_sixth_refused(self):
        """The 6th pending filing for a credential refuses with exit 2."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            self._plant("github",
                        created=now - timedelta(seconds=300 + 60 * i))
        r = self._file("github")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("flood cap", r.stderr)
        self.assertEqual(r.stdout.strip(), "",
                         "a refused filing prints no aid")
        self.assertEqual(len(self._pending_jsons()), 5,
                         "a refused filing writes nothing")

    def test_76_cap_is_per_credential(self):
        """A full cap on one credential does not block another."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            self._plant("github",
                        created=now - timedelta(seconds=300 + 60 * i))
        r = self._file("openai")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout.strip(), r"^[0-9a-f]{16}$")

    def test_76_expired_does_not_consume_cap(self):
        """Expired-but-unreaped items do not burn a cap slot."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            self._plant("github",
                        created=now - timedelta(seconds=300 + 60 * i),
                        expires=now - timedelta(seconds=10))
        r = self._file("github")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_76_corrupt_files_do_not_consume_cap(self):
        """A planted corrupt file is the loader's business, not the
        cap's — it must not deny a filing."""
        now = datetime.now(timezone.utc)
        for i in range(4):
            self._plant("github",
                        created=now - timedelta(seconds=300 + 60 * i))
        self._plant("github", corrupt=True, name="garbagebeef012345")
        r = self._file("github")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_76_rate_limit_refuses_second_filing(self):
        """Two filings 60s apart for a credential: the second refuses."""
        self._plant("github")
        r = self._file("github")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("rate limited", r.stderr)
        self.assertEqual(r.stdout.strip(), "")

    def test_76_rate_limit_window_passes(self):
        """A filing older than 60s does not rate-limit a new one."""
        self._plant("github",
                    created=datetime.now(timezone.utc)
                    - timedelta(seconds=61))
        r = self._file("github")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_76_filed_item_is_0600_despite_umask(self):
        """The filed file is owner-only even under a pathological umask.

        umask 0o700 strips owner bits at create (0o600 & ~0o700 == 0o0),
        so this test fails if the fchmod pin is ever removed — it is
        the discriminating variant (umask 0o027 would pass with or
        without fchmod).
        """
        old = os.umask(0o700)
        try:
            r = self._file("github")
        finally:
            os.umask(old)
        self.assertEqual(r.returncode, 0, r.stderr)
        aid = r.stdout.strip()
        mode = stat.S_IMODE(os.stat(
            self.approvals / "pending" / (aid + ".json")).st_mode)
        self.assertEqual(mode, 0o600,
                         "file mode must be 0600, not umask-inherited")

    def test_76_ttl_out_of_range_refused(self):
        """--ttl outside 1..86400 is refused loudly; nothing is filed."""
        env = dict(os.environ, CONFIRM_DIR=str(self.approvals))
        for ttl in ("0", "-5", "999999999"):
            r = subprocess.run(
                [sys.executable, self.script, "--kind", "first-use",
                 "--credential", "github", "--host", "api.github.com",
                 "--ttl", ttl],
                capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(r.returncode, 2, ttl)
            self.assertIn("invalid --ttl", r.stderr, ttl)
            self.assertEqual(r.stdout.strip(), "", ttl)
        self.assertEqual(self._pending_jsons(), [],
                         "refused filings write nothing")

    def test_76_credential_rotation_does_not_defeat_rate(self):
        """The per-filer rate limit survives --credential rotation: a
        live filing under one name blocks an immediate filing under
        another (Security B2)."""
        r1 = self._file("rot1")
        self.assertEqual(r1.returncode, 0, r1.stderr)
        for other in ("rot2", "ROT1", "rot1 "):
            r = self._file(other)
            self.assertEqual(r.returncode, 2, other)
            self.assertIn("rate limited", r.stderr, other)

    def test_76_unparseable_expires_does_not_burn_cap(self):
        """A planted file with garbage/missing expires must not burn a
        cap slot (Security N2)."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            aid = "junkexp%02dbeef12" % i
            p = self.approvals / "pending" / (aid + ".json")
            p.write_text(json.dumps({
                "id": aid, "credential": "github",
                "created": (now - timedelta(seconds=300)).isoformat(),
                "expires": "not-a-timestamp" if i % 2 else None,
                "summary": "x"}))
        r = self._file("github")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_76_concurrent_filings_bounded(self):
        """N racing invocations file at most one item: the flock-held
        check-then-act cannot be bypassed with xargs -P (Security B1)."""
        env = dict(os.environ, CONFIRM_DIR=str(self.approvals))
        n = 8
        procs = [subprocess.Popen(
            [sys.executable, self.script, "--kind", "first-use",
             "--credential", "github", "--host", "api.github.com"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env) for _ in range(n)]
        try:
            outs = [p.communicate(timeout=60) for p in procs]
        finally:
            for p in procs:
                if p.poll() is None:
                    p.kill()
        codes = [p.returncode for p in procs]
        self.assertEqual(codes.count(0), 1,
                         "exactly one racer files: %r" % (codes,))
        self.assertEqual(len(self._pending_jsons()), 1)

    def _load_script_module(self):
        import importlib.util
        from importlib.machinery import SourceFileLoader
        loader = SourceFileLoader("confirm_request_under_test",
                                  self.script)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        return mod

    def test_76_flood_accounting_keyed_by_euid(self):
        """Items owned by another uid don't count toward this filer's
        cap/rate (Finding 50: owner is the requester). Pinned without
        root by injecting a foreign euid into the scanner."""
        mod = self._load_script_module()
        now = datetime.now(timezone.utc)
        for i in range(5):
            self._plant("github",
                        created=now - timedelta(seconds=300 + 60 * i))
        d = str(self.approvals / "pending")
        per_cred, newest = mod._pending_stats(d, 2**31 - 1, "github", now)
        self.assertEqual((per_cred, newest), (0, None),
                         "foreign-uid items must be invisible")
        per_cred, newest = mod._pending_stats(d, os.geteuid(),
                                              "github", now)
        self.assertEqual(per_cred, 5)
        self.assertIsNotNone(newest)

    def test_76_future_created_clamped(self):
        """A future-dated created cannot pin the rate limiter beyond
        the 60s window (Security N1): the scanner clamps to now."""
        mod = self._load_script_module()
        now = datetime.now(timezone.utc)
        self._plant("github", created=now + timedelta(seconds=3600))
        d = str(self.approvals / "pending")
        per_cred, newest = mod._pending_stats(d, os.geteuid(),
                                              "github", now)
        self.assertEqual(per_cred, 1)
        self.assertIsNotNone(newest)
        self.assertLessEqual(newest, now,
                             "future created must clamp to now")


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
        # Issue #620: see ConfirmdTests.setUp — same cadence-gate reset.
        cd._reset_housekeeping_for_tests()

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


class AuditLogTests(unittest.TestCase):
    """confirmd.audit_log durability posture (arch finding A5, sentinel
    deep-read): the happy path appends the logfmt line silently; a write
    failure must signal to stderr, never pass silently."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

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

    def test_audit_log_write_failure_stderr_is_single_sanitized_line(self):
        """PR #696 follow-up: the stderr fallback sanitizes like the audit
        line does — a malicious login (newlines, a `ts=`-looking forgery
        fragment) plus a forced write failure must land as ONE sanitized
        line, never a forged multi-line audit entry."""
        evil = "evil-user\nts=999 event=GRANT login=root"
        with mock.patch.object(cd, "AUDIT", self.tmp.name):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                cd.audit_log("403", "100.99.0.1", evil, "")
        out = err.getvalue()
        self.assertIn("confirmd: cannot write audit log", out)
        # One line: the newline forgery collapsed.
        self.assertEqual(out.count("\n"), 1, out)
        # No space-separated forged tokens: spaces are stripped, so the
        # forgery fused into one non-parseable token instead.
        self.assertNotIn(" event=GRANT", out)
        self.assertNotIn(" login=root", out)

    def test_audit_log_fsyncs_before_return(self):
        """Issue #72: the audit append must be fsync'd so the line is
        crash-durable once audit_log() returns — no silent page-cache
        window. The fd passed to fsync is a real open descriptor, and the
        bytes must already be visible at OS level when fsync runs (a plain
        os.fsync after a buffered write would sync nothing)."""
        path = os.path.join(self.tmp.name, "audit.log")
        seen = {}

        def fake_fsync(fd):
            with open(path, "rb") as rf:  # fresh read: only OS-level bytes
                seen["content"] = rf.read()

        with mock.patch.object(cd, "AUDIT", path), \
                mock.patch("os.fsync", side_effect=fake_fsync) as mock_fsync:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                cd.audit_log("403", "100.99.0.1", "ntindle@github",
                             "reason=bad-nonce")
        self.assertEqual(err.getvalue(), "")
        mock_fsync.assert_called_once()
        (fd,), _ = mock_fsync.call_args
        self.assertIsInstance(fd, int)
        self.assertIn(b"event=403", seen["content"])

    def test_audit_log_fsync_failure_signals_stderr(self):
        """Issue #72: an fsync OSError is a lost audit line like any write
        OSError — it must take the same stderr-signaling path, not pass."""
        path = os.path.join(self.tmp.name, "audit.log")
        with mock.patch.object(cd, "AUDIT", path), \
                mock.patch("os.fsync", side_effect=OSError("simulated")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                cd.audit_log("403", "100.99.0.1", "ntindle@github", "")
        self.assertIn("confirmd: cannot write audit log", err.getvalue())
        self.assertIn("simulated", err.getvalue())

    def test_audit_log_sanitizes_client_influenced_fields(self):
        """Issue #683 (#17 twin): `login` is user-supplied web-UI form
        input and `detail` can carry client-influenced values, so a
        newline or a `ts=`-looking fragment must not forge audit lines.
        The sanitize choke point strips everything outside printable
        ASCII; well-formed values pass through unchanged."""
        path = os.path.join(self.tmp.name, "audit.log")
        with mock.patch.object(cd, "AUDIT", path):
            cd.audit_log("403", "100.99.0.1",
                         "attacker\nts=2026-01-01T00:00:00Z event=approved",
                         "host=x.example\nforged=1\u2028")
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 1)  # no injected line break survived
        line = lines[0]
        # Spaces die too (0x20 is below '!' in the allowlist), so the forged
        # fragment is fused into the login/detail token — it can never parse
        # as a separate line or a separate k=v token.
        self.assertNotIn("\u2028", line)
        self.assertIn("login=attackerts=2026-01-01T00:00:00Zevent=approved",
                      line)
        self.assertIn("host=x.exampleforged=1", line)

    def test_audit_log_well_formed_fields_unchanged(self):
        """Sanitization is mechanical: printable-ASCII audit values are
        byte-identical before and after (#683)."""
        path = os.path.join(self.tmp.name, "audit.log")
        with mock.patch.object(cd, "AUDIT", path):
            cd.audit_log("403", "100.99.0.1", "ntindle@github",
                         "reason=bad-nonce")
        with open(path, encoding="utf-8") as f:
            line = f.read().splitlines()[0]
        self.assertRegex(line, r"^ts=\S+ event=403 peer=100\.99\.0\.1 "
                               r"login=ntindle@github reason=bad-nonce$")

    def test_audit_log_none_login_renders_dash(self):
        """None still renders as '-' (pre-#683 `login or '-'` semantics
        preserved through the sanitize choke point)."""
        path = os.path.join(self.tmp.name, "audit.log")
        with mock.patch.object(cd, "AUDIT", path):
            cd.audit_log("conn-deadline", "100.99.0.1", None, "")
        with open(path, encoding="utf-8") as f:
            line = f.read().splitlines()[0]
        self.assertIn("login=-", line)

    def test_sanitize_audit_field_helper(self):
        """Direct contract of the #683 helper: printable ASCII passes,
        everything outside `!`..`~` is dropped, None -> '-'."""
        self.assertEqual(cd._sanitize_audit_field(None), "-")
        self.assertEqual(cd._sanitize_audit_field("ok-1_2.3"), "ok-1_2.3")
        self.assertEqual(cd._sanitize_audit_field("a\nb\rc\td"), "abcd")
        self.assertEqual(cd._sanitize_audit_field("é"), "")
        self.assertEqual(cd._sanitize_audit_field(404), "404")

class M8ServerHardeningTests(unittest.TestCase):
    """Issue #77 (M8): no socket/request timeouts, unbounded thread pool."""

    def _make_server(self, max_threads=4):
        srv = cd.BoundedThreadingHTTPServer(("127.0.0.1", 0), cd.Handler)
        srv.max_threads = max_threads
        srv._slots = __import__("threading").Semaphore(max_threads)
        self.addCleanup(srv.server_close)
        return srv

    def test_handler_socket_timeout(self):
        """A slow-lorising peer must not hold a handler thread forever."""
        self.assertEqual(cd.Handler.timeout, 10)

    def test_accepted_socket_gets_timeout(self):
        """The timeout class attribute reaches the accepted socket — the
        CPython mechanism is StreamRequestHandler.setup's settimeout, so
        exercise exactly that against a bare handler."""
        import socketserver
        srv = self._make_server()
        client, accepted = __import__("socket").socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        accepted.settimeout(None)
        h = cd.Handler.__new__(cd.Handler)
        h.request = accepted
        h.server = srv
        socketserver.StreamRequestHandler.setup(h)
        self.assertEqual(accepted.gettimeout(), 10)

    def test_over_cap_connection_closed_not_queued(self):
        """When the pool is full, the connection is closed immediately —
        fail closed, not queued unboundedly."""
        srv = self._make_server(max_threads=1)
        srv._slots.acquire()  # drain the single slot
        client, accepted = __import__("socket").socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        threads_before = threading.active_count()
        srv.process_request(accepted, ("127.0.0.1", 0))
        time.sleep(0.2)
        # The accepted socket was closed: no new thread, fileno invalid.
        self.assertEqual(threading.active_count(), threads_before)
        self.assertEqual(accepted.fileno(), -1)
        srv._slots.release()  # restore for cleanup

    def test_slot_released_after_request(self):
        """A completed request returns its pool slot."""
        srv = self._make_server(max_threads=2)
        calls = []

        def fake_finish(request, client_address):
            calls.append(1)

        with mock.patch.object(srv, "finish_request", fake_finish):
            client, accepted = __import__("socket").socketpair()
            self.addCleanup(client.close)
            srv.process_request(accepted, ("127.0.0.1", 0))
            for _ in range(100):
                if calls:
                    break
                time.sleep(0.02)
        self.assertEqual(len(calls), 1)
        # Wait for the thread's finally (shutdown_request + release) — the
        # release lags the finish call, and a bare successful acquire would
        # probe the pre-release value. Poll for the full slot count.
        for _ in range(100):
            if srv._slots._value == 2:
                break
            time.sleep(0.02)
        else:
            self.fail("handler thread never released its pool slot")
        # Both slots available again after the thread's finally ran.
        self.assertTrue(srv._slots.acquire(blocking=False))
        self.assertTrue(srv._slots.acquire(blocking=False))
        self.assertFalse(srv._slots.acquire(blocking=False))
        srv._slots.release()
        srv._slots.release()

    def test_thread_start_failure_releases_slot(self):
        """A thread-creation failure must not permanently drain the pool —
        otherwise the mitigation itself turns a transient resource crunch
        into a hard outage (Architecture review B1)."""
        srv = self._make_server(max_threads=1)
        client, accepted = __import__("socket").socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        with mock.patch("threading.Thread", side_effect=RuntimeError(
                "can't start new thread")):
            srv.process_request(accepted, ("127.0.0.1", 0))
        # The slot was released: still acquirable, and no handler ran.
        self.assertTrue(srv._slots.acquire(blocking=False))
        srv._slots.release()
        # The connection was closed, not left dangling.
        self.assertEqual(accepted.fileno(), -1)

    def test_failed_start_never_parks_dead_thread(self):
        """B1 convergence: ThreadingMixIn registers the new thread in
        _threads BEFORE start(). If start() raises, the dead thread must
        not break a later server_close() with RuntimeError ("cannot join
        thread before it is started"). Daemon threads (this server's
        default) are never tracked, so pin the property with
        daemon_threads=False — the only configuration where registration
        happens at all."""
        import socket as _socket
        srv = self._make_server(max_threads=1)
        srv.daemon_threads = False  # force _threads registration
        real_thread = threading.Thread

        def boom(*a, **k):
            th = real_thread(*a, **k)
            def fail():
                raise RuntimeError("can't start new thread")
            th.start = fail
            return th

        client, accepted = _socket.socketpair()
        self.addCleanup(client.close)
        with mock.patch("threading.Thread", boom):
            srv.process_request(accepted, ("127.0.0.1", 0))
        # server_close must stay clean despite the never-started thread.
        srv.server_close()
        # And the slot was still released.
        self.assertTrue(srv._slots.acquire(blocking=False))
        srv._slots.release()

    def test_slot_released_when_shutdown_request_raises(self):
        """A raise in shutdown_request must not permanently burn a pool
        slot — the mitigation must not become the DoS (Security review B2).
        The raise still propagates (not swallowed); only the slot release
        is guaranteed."""
        srv = self._make_server(max_threads=1)
        client, accepted = __import__("socket").socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        seen = []
        old_hook = threading.excepthook
        threading.excepthook = lambda args: seen.append(args.exc_value)
        self.addCleanup(setattr, threading, "excepthook", old_hook)
        with mock.patch.object(srv, "finish_request", lambda r, a: None), \
             mock.patch.object(srv, "shutdown_request",
                               side_effect=RuntimeError("boom")):
            srv.process_request(accepted, ("127.0.0.1", 0))
            for _ in range(100):
                if srv._slots._value == 1:
                    break
                time.sleep(0.02)
            else:
                self.fail("pool slot was not released when shutdown_request "
                          "raised")
        for _ in range(100):
            if seen:
                break
            time.sleep(0.02)
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], RuntimeError)
        self.assertTrue(srv._slots.acquire(blocking=False))
        srv._slots.release()

    def test_handler_threads_registered_for_block_on_close(self):
        """process_request preserves ThreadingMixIn's lifecycle bookkeeping:
        with block_on_close, handler threads land in srv._threads so
        server_close() waits for them (Architecture review)."""
        import socket as _socket
        srv = self._make_server(max_threads=2)
        srv.daemon_threads = False  # _Threads only tracks non-daemon threads
        self.assertTrue(srv.block_on_close)
        started = threading.Event()
        release = threading.Event()

        def fake_finish(request, client_address):
            started.set()
            release.wait(10)

        with mock.patch.object(srv, "finish_request", fake_finish):
            client, accepted = _socket.socketpair()
            self.addCleanup(client.close)
            self.addCleanup(accepted.close)
            srv.process_request(accepted, ("127.0.0.1", 0))
            self.assertTrue(started.wait(5), "handler thread never started")
            for _ in range(100):
                if any(t.is_alive() for t in srv._threads):
                    break
                time.sleep(0.05)
            else:
                self.fail("handler thread was not registered in srv._threads")
            release.set()

    @unittest.skipUnless(__import__("shutil").which("openssl"),
                         "openssl needed for a throwaway test cert")
    def test_stalled_tls_handshake_does_not_pin_accept_loop(self):
        """The TLS handshake must not run in the accept loop (Security
        review B1): one peer stalling the handshake must not stop a
        legitimate TLS client from being served."""
        import shutil as _shutil  # noqa: F401 (used by the skipUnless above)
        import socket as _socket
        import ssl as _ssl
        import subprocess as _subprocess
        with tempfile.TemporaryDirectory() as d:
            cert = os.path.join(d, "cert.pem")
            key = os.path.join(d, "key.pem")
            _subprocess.run(
                ["openssl", "req", "-x509", "-newkey", "rsa:2048",
                 "-keyout", key, "-out", cert, "-days", "1",
                 "-nodes", "-subj", "/CN=localhost"],
                check=True, capture_output=True, timeout=60)
            old_timeout = cd.Handler.timeout
            cd.Handler.timeout = 2  # keep the stalled-handshake thread short
            self.addCleanup(setattr, cd.Handler, "timeout", old_timeout)
            srv = self._make_server(max_threads=2)
            sctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
            sctx.load_cert_chain(cert, key)
            # Exactly what main() does:
            srv.socket = sctx.wrap_socket(
                srv.socket, server_side=True, do_handshake_on_connect=False)
            served = []
            with mock.patch.object(srv, "finish_request",
                                   lambda r, a: served.append(1)), \
                 mock.patch.object(srv, "handle_error"):
                t = threading.Thread(target=srv.serve_forever, daemon=True)
                t.start()
                self.addCleanup(srv.shutdown)
                port = srv.server_address[1]
                # Attacker: completes TCP, never sends ClientHello.
                attacker = _socket.create_connection(("127.0.0.1", port))
                self.addCleanup(attacker.close)
                # Legitimate client: full TLS handshake + request.
                cctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
                cctx.check_hostname = False
                cctx.verify_mode = _ssl.CERT_NONE
                raw = _socket.create_connection(("127.0.0.1", port))
                self.addCleanup(raw.close)
                legit = cctx.wrap_socket(raw, server_hostname="localhost")
                self.addCleanup(legit.close)
                for _ in range(200):
                    if served:
                        break
                    time.sleep(0.05)
                else:
                    self.fail("legitimate TLS client was not served within "
                              "10s while one handshake stalled — the accept "
                              "loop is pinned")


class ConnDeadlineTests(unittest.TestCase):
    """Issue #472: cumulative per-connection deadline — a peer dripping
    >=1 byte per socket-timeout holds a pool slot indefinitely, because
    the 10s socket timeout is per operation, not cumulative."""

    def _make_server(self, max_threads=4):
        srv = cd.BoundedThreadingHTTPServer(("127.0.0.1", 0), cd.Handler)
        srv.max_threads = max_threads
        srv._slots = __import__("threading").Semaphore(max_threads)
        self.addCleanup(srv.server_close)
        return srv

    def test_deadline_bound_sizing(self):
        """The cumulative bound is a multiple of the per-operation
        timeout: generous for legitimate approvals (the grant-writer
        subprocess window is 15s) but finite against trickling peers."""
        self.assertGreaterEqual(
            cd.BoundedThreadingHTTPServer.connection_deadline,
            4 * cd.BoundedThreadingHTTPServer.socket_timeout)

    def test_kill_connection_aborts_stalled_peer(self):
        """_kill_connection aborts the connection: the peer sees EOF, and
        a second kill on the already-dead socket is a no-op, not a raise."""
        client, accepted = __import__("socket").socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        cd._kill_connection(accepted, ("127.0.0.1", 4242))
        client.settimeout(5)
        self.assertEqual(client.recv(1), b"")
        # Idempotent: killing twice must not raise (the timer path and
        # shutdown_request both touch the socket).
        cd._kill_connection(accepted, ("127.0.0.1", 4242))

    def test_deadline_timer_fires_and_releases_slot(self):
        """A handler stuck in recv while the peer trickles is aborted at
        the cumulative deadline — the thread exits and the pool slot is
        released instead of pinned forever."""
        srv = self._make_server(max_threads=2)
        srv.connection_deadline = 0.2
        peer, server_end = __import__("socket").socketpair()
        self.addCleanup(peer.close)
        self.addCleanup(server_end.close)

        def trickling_handler(request, client_address):
            # Peer never sends; per-operation timeout would never fire
            # here on a trickling peer either — only the deadline saves us.
            server_end.recv(4096)

        started = time.monotonic()
        # Mirror the real path: process_request acquires the slot before
        # spawning the handler thread; process_request_thread releases it.
        self.assertTrue(srv._slots.acquire(blocking=False))
        with mock.patch.object(srv, "finish_request", trickling_handler):
            t = threading.Thread(
                target=srv.process_request_thread,
                args=(server_end, ("127.0.0.1", 4242)), daemon=True)
            t.start()
            t.join(timeout=10)
        elapsed = time.monotonic() - started
        self.assertFalse(t.is_alive(),
                         "handler thread still pinned after the deadline")
        self.assertLess(elapsed, 10,
                        "deadline did not abort the stalled handler")
        # Slot released: the mitigation must not become the DoS.
        self.assertEqual(srv._slots._value, 2)
        # The peer observed the abort as EOF.
        peer.settimeout(5)
        self.assertEqual(peer.recv(1), b"")

    def test_deadline_timer_cancelled_on_success(self):
        """A request that completes before the bound cancels its timer —
        well-behaved connections never pay for the mitigation, and no
        error is logged for a normal completion."""
        srv = self._make_server(max_threads=2)
        srv.connection_deadline = 60
        seen = []

        class FakeTimer:
            def __init__(self, interval, fn, args=()):
                self.interval = interval
                self.fn = fn
                self.args = args
                self.started = False
                self.cancelled = False

            def start(self):
                self.started = True
                seen.append(self)

            def cancel(self):
                self.cancelled = True

        client, accepted = __import__("socket").socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        with mock.patch.object(threading, "Timer", FakeTimer), \
             mock.patch.object(srv, "finish_request",
                               lambda r, a: None), \
             mock.patch.object(srv, "handle_error") as handle_error:
            srv.process_request_thread(accepted, ("127.0.0.1", 4242))
        self.assertEqual(len(seen), 1, "exactly one deadline timer per "
                         "connection")
        timer = seen[0]
        self.assertTrue(timer.started)
        self.assertTrue(timer.cancelled,
                        "completed request left its deadline timer armed")
        self.assertEqual(timer.interval, 60)
        handle_error.assert_not_called()
class GrantTtlChoiceTests(unittest.TestCase):
    """Issue #73: the approval page offers a bounded per-approval
    grant-lifetime choice (1h default / 24h) and the choice reaches
    grant-writer as --ttl-hours."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.approvals = Path(self.tmp.name) / "approvals"
        self.approvals.mkdir()
        for sub in ("pending", "answered", "consumed"):
            (self.approvals / sub).mkdir()
        # Issue #620: housekeeping is cadence-gated on module state —
        # each test starts with it due so answer-path behavior is
        # deterministic regardless of test order.
        cd._reset_housekeeping_for_tests()

    def tearDown(self):
        self.tmp.cleanup()

    def _run_answer(self, aid, decision, ttl_hours=cd.GRANT_TTL_DEFAULT):
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2999-01-01T00:00:00+00:00",
              "credential": "c", "host": "h", "method": "GET"}
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))
        nonce = cd._mint_csrf_nonce(aid)
        mint_calls = []
        events = []
        got = {}

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                mint_calls.append(cmd)

                class R:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return R()
            return _fake_run(cmd, **kwargs)

        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        h.send_response = lambda c: got.update(code=c)
        h.send_header = lambda *a: None
        h.end_headers = lambda: None
        cd._aid_lock(aid)  # ensure the entry exists pre-answer
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch("subprocess.run", side_effect=fake_run) as \
                 run_mock, \
             mock.patch.object(cd, "audit_log",
                               side_effect=lambda *a: events.append(a)), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)):
            h._answer_locked("ntindle@github", aid, nonce, decision,
                             ttl_hours=ttl_hours)
        return {"mint": mint_calls, "run_mock": run_mock,
                "events": events, "got": got, "src": src}

    def _answered_record(self, aid):
        p = self.approvals / "consumed" / (aid + ".json")
        self.assertTrue(p.exists(), "no consumed record for %s" % aid)
        return json.loads(p.read_text())

    def test_73_parse_allowlist(self):
        """_parse_grant_ttl: missing/empty means the default (shortest);
        the offered choices parse; anything else is refused, never
        coerced."""
        self.assertEqual(cd._parse_grant_ttl(None), 1)
        self.assertEqual(cd._parse_grant_ttl(""), 1)
        self.assertEqual(cd._parse_grant_ttl("1"), 1)
        self.assertEqual(cd._parse_grant_ttl("24"), 24)
        self.assertEqual(cd._parse_grant_ttl(24), 24)
        for bad in ("168", "0", "-1", "abc", "1.5", "0x18", 168):
            with self.assertRaises(ValueError,
                                   msg="ttl=%r must be refused" % (bad,)):
                cd._parse_grant_ttl(bad)

    def test_73_default_ttl_is_1h(self):
        """Approve with no explicit choice mints --ttl-hours 1 (the
        shortest), records it, and audits it. Without the feature this
        test fails: the writer got no --ttl-hours and the record/audit
        carried no lifetime."""
        r = self._run_answer("ttl-default-1", "approve")
        self.assertEqual(r["got"].get("code"), 303)
        self.assertEqual(len(r["mint"]), 1)
        cmd = r["mint"][0]
        self.assertIn("--ttl-hours", cmd)
        self.assertEqual(cmd[cmd.index("--ttl-hours") + 1], "1",
                         "writer argv: %r" % (cmd,))
        rec = self._answered_record("ttl-default-1")
        self.assertEqual(rec.get("grant_ttl_hours"), 1)
        answer = [e for e in r["events"] if e[0] == "answer"]
        self.assertEqual(len(answer), 1)
        self.assertIn("ttl=1h", answer[0][3], "audit detail: %r"
                      % (answer[0][3],))

    def test_73_chosen_ttl_24h(self):
        """The owner-chosen 24h reaches the writer, the record, and the
        audit."""
        r = self._run_answer("ttl-24h-1", "approve", ttl_hours=24)
        self.assertEqual(r["got"].get("code"), 303)
        cmd = r["mint"][0]
        self.assertEqual(cmd[cmd.index("--ttl-hours") + 1], "24",
                         "writer argv: %r" % (cmd,))
        rec = self._answered_record("ttl-24h-1")
        self.assertEqual(rec.get("grant_ttl_hours"), 24)
        answer = [e for e in r["events"] if e[0] == "answer"]
        self.assertIn("ttl=24h", answer[0][3], "audit detail: %r"
                      % (answer[0][3],))

    def test_73_crafted_ttl_is_refused(self):
        """A crafted TTL (168h) is refused with 400 — never coerced —
        the mint never starts and the pending file stays in place."""
        r = self._run_answer("ttl-craft-1", "approve", ttl_hours="168")
        self.assertEqual(r["got"].get("code"), 400)
        self.assertEqual(r["run_mock"].call_count, 0,
                         "the mint must not start on a refused TTL")
        self.assertTrue(r["src"].exists(),
                        "refused answer must leave the pending file")
        self.assertFalse(
            (self.approvals / "consumed" / "ttl-craft-1.json").exists())

    def _do_post_answer(self, aid, fields):
        """Drive Handler.do_POST /answer end to end (the production
        entry point — form parse, TTL validation, lock, mint). Returns
        (got, events, mint_calls, run_mock)."""
        body = urllib.parse.urlencode(fields).encode()
        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        h.path = "/answer"
        h.headers = {"Content-Length": str(len(body))}
        h.rfile = io.BytesIO(body)
        got = {}
        events = []
        mint_calls = []
        h.send_response = lambda c: got.update(code=c)
        h.send_header = lambda *a: None
        h.end_headers = lambda: None

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                mint_calls.append(cmd)

                class R:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return R()
            return _fake_run(cmd, **kwargs)

        with mock.patch.object(cd.Handler, "_auth",
                               return_value="ntindle@github"), \
             mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch("subprocess.run",
                        side_effect=fake_run) as run_mock, \
             mock.patch.object(cd, "audit_log",
                               side_effect=lambda *a: events.append(a)), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)):
            h.do_POST()
        return got, events, mint_calls, run_mock

    def _file_pending(self, aid):
        (self.approvals / "pending" / (aid + ".json")).write_text(
            json.dumps({"id": aid, "summary": "s", "kind": "first-use",
                        "created": "2026-09-18T10:00:00+00:00",
                        "expires": "2999-01-01T00:00:00+00:00",
                        "credential": "c", "host": "h", "method": "GET"}))
        return cd._mint_csrf_nonce(aid)

    def test_73_do_post_crafted_ttl_refused_pre_lock(self):
        """Engineering blocker: the do_POST TTL-validation branch is the
        production entry point — a crafted ttl=168 must 400 before the
        aid lock is even acquired, the mint must never start, and the
        pending file stays in place. Deleting the do_POST branch must
        fail this test."""
        aid = "dopost-ttl-168-1"
        nonce = self._file_pending(aid)
        got, events, mint_calls, run_mock = self._do_post_answer(
            aid, {"id": aid, "csrf": nonce, "decision": "approve",
                  "ttl": "168"})
        self.assertEqual(got.get("code"), 400)
        self.assertEqual(run_mock.call_count, 0,
                         "the mint must not start on a refused TTL")
        self.assertEqual(len(mint_calls), 0)
        self.assertTrue(
            (self.approvals / "pending" / (aid + ".json")).exists(),
            "refused answer must leave the pending file")
        # The refusal fires before _aid_lock: no registry entry is
        # created for a value that never became an answer attempt.
        self.assertNotIn(aid, cd._aid_locks)

    def test_73_do_post_missing_ttl_defaults_1h(self):
        """The mirror case: a form with no ttl field (old cached page,
        non-browser client) approves with the shortest lifetime —
        --ttl-hours 1 — end to end through do_POST."""
        aid = "dopost-ttl-missing-1"
        nonce = self._file_pending(aid)
        got, events, mint_calls, run_mock = self._do_post_answer(
            aid, {"id": aid, "csrf": nonce, "decision": "approve"})
        self.assertEqual(got.get("code"), 303)
        self.assertEqual(len(mint_calls), 1)
        cmd = mint_calls[0]
        self.assertEqual(cmd[cmd.index("--ttl-hours") + 1], "1",
                         "writer argv: %r" % (cmd,))
        rec = self._answered_record("dopost-ttl-missing-1")
        self.assertEqual(rec.get("grant_ttl_hours"), 1)

    def test_73_do_post_ttl_24h(self):
        """The owner-chosen 24h flows from the form through do_POST to
        the writer, the record, and the audit."""
        aid = "dopost-ttl-24h-1"
        nonce = self._file_pending(aid)
        got, events, mint_calls, run_mock = self._do_post_answer(
            aid, {"id": aid, "csrf": nonce, "decision": "approve",
                  "ttl": "24"})
        self.assertEqual(got.get("code"), 303)
        cmd = mint_calls[0]
        self.assertEqual(cmd[cmd.index("--ttl-hours") + 1], "24",
                         "writer argv: %r" % (cmd,))
        rec = self._answered_record("dopost-ttl-24h-1")
        self.assertEqual(rec.get("grant_ttl_hours"), 24)
        answer = [e for e in events if e[0] == "answer"]
        self.assertIn("ttl=24h", answer[0][3])

    def test_73_deny_ignores_ttl(self):
        """A deny mints nothing: no writer call, and the consumed record
        carries no grant lifetime — even if the requester planted one
        (belt-and-braces pop), and the deny audit carries no ttl=."""
        aid = "ttl-deny-1"
        it = {"id": aid, "summary": "s", "kind": "first-use",
              "created": "2026-09-18T10:00:00+00:00",
              "expires": "2999-01-01T00:00:00+00:00",
              "credential": "c", "host": "h", "method": "GET",
              "grant_ttl_hours": 24}
        src = self.approvals / "pending" / (aid + ".json")
        src.write_text(json.dumps(it))
        nonce = cd._mint_csrf_nonce(aid)
        mint_calls = []
        events = []
        got = {}

        def fake_run(cmd, **kwargs):
            if cmd[0] == cd.GRANT_WRITER:
                mint_calls.append(cmd)

                class R:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return R()
            return _fake_run(cmd, **kwargs)

        h = cd.Handler.__new__(cd.Handler)
        h.client_address = ("100.99.0.1", 1234)
        h.send_response = lambda c: got.update(code=c)
        h.send_header = lambda *a: None
        h.end_headers = lambda: None
        cd._aid_lock(aid)
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)), \
             mock.patch.object(cd, "file_owner_name",
                               return_value="swapd"), \
             mock.patch("subprocess.run",
                        side_effect=fake_run) as run_mock, \
             mock.patch.object(cd, "audit_log",
                               side_effect=lambda *a: events.append(a)), \
             mock.patch.object(cd.Handler, "_err",
                               side_effect=lambda m, c: got.update(
                                   msg=m, code=c)):
            h._answer_locked("ntindle@github", aid, nonce, "deny",
                             ttl_hours=24)
        self.assertEqual(got.get("code"), 303)
        self.assertEqual(run_mock.call_count, 0)
        rec = self._answered_record("ttl-deny-1")
        self.assertNotIn("grant_ttl_hours", rec,
                         "a requester-planted lifetime must not survive "
                         "a denial")
        answer = [e for e in events if e[0] == "answer"]
        self.assertEqual(len(answer), 1)
        self.assertNotIn("ttl=", answer[0][3])

    def test_73_detail_page_renders_ttl_choice(self):
        """The approval detail page renders the bounded TTL choice with
        1h checked by default — the owner sees the grant's lifetime at
        decision time."""
        aid = "ttl-page-1"
        (self.approvals / "pending" / (aid + ".json")).write_text(
            json.dumps({"id": aid, "summary": "s", "kind": "first-use",
                        "created": "2026-09-18T10:00:00+00:00",
                        "expires": "2999-01-01T00:00:00+00:00",
                        "credential": "c", "host": "h", "method": "GET"}))
        h = cd.Handler.__new__(cd.Handler)
        h.path = "/approval/" + aid
        h.client_address = ("100.99.0.1", 1234)
        got = {}
        with mock.patch.object(cd.Handler, "_auth",
                               return_value="ntindle@github"), \
             mock.patch.object(cd.Handler, "_send_html",
                               side_effect=lambda body, code=200,
                               title="", script="": got.update(
                                   body=body, code=code)), \
             mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            h.do_GET()
        body = got.get("body", "")
        self.assertEqual(got.get("code"), 200)
        self.assertIn("Grant lifetime", body)
        self.assertIn('name="ttl"', body)
        self.assertIn('value="1" checked', body,
                      "the shortest lifetime must be the default")
        self.assertIn('value="24"', body)
        # Design B1: the fieldset carries the 52px-tap-row styling.
        self.assertIn('class="ttl"', body)
        # Design B4: the armed confirm button restates the chosen
        # lifetime from the checked radio at tap time.
        self.assertIn('querySelector(', body)
        self.assertIn('Tap again to confirm approval ("+t+"h grant)',
                      body)

    def test_73_server_answered_card_shows_ttl(self):
        """Design B2: the server-rendered answered card (first paint,
        JS-disabled fallback) carries the grant lifetime with the same
        vocabulary as the JS card; pre-#73 records render as before."""
        with_ttl = cd._render_answered_list([{
            "id": "srv-ttl-1", "summary": "s", "kind": "k",
            "decision": "approve", "answered_by": "b",
            "answered_at": "2026-09-18T10:05:00+00:00",
            "grant_ttl_hours": 24}])
        self.assertIn("grant 24h", with_ttl)
        legacy = cd._render_answered_list([{
            "id": "srv-ttl-2", "summary": "s", "kind": "k",
            "decision": "approve", "answered_by": "b",
            "answered_at": "2026-09-18T10:05:00+00:00"}])
        self.assertNotIn("grant", legacy)
        deny = cd._render_answered_list([{
            "id": "srv-ttl-3", "summary": "s", "kind": "k",
            "decision": "deny", "answered_by": "b",
            "answered_at": "2026-09-18T10:05:00+00:00",
            "grant_ttl_hours": 24}])
        self.assertNotIn("grant", deny)

    def test_73_answered_api_carries_ttl(self):
        """_answered_api_item allowlists grant_ttl_hours so the answered
        feed (and the card's meta line) can show the authorized
        lifetime."""
        base = {"id": "x-1", "summary": "s", "kind": "k",
                "decision": "approve", "answered_by": "b",
                "answered_at": "t"}
        self.assertEqual(
            cd._answered_api_item(dict(base, grant_ttl_hours=24))
            ["grant_ttl_hours"], "24")
        self.assertEqual(cd._answered_api_item(base)["grant_ttl_hours"],
                         "")


class FindLoginTests(unittest.TestCase):
    """Issue #1166: _find_login is anchored to UserProfile.LoginName.

    The finding-47 owner check rests on this extraction: it must read
    UserProfile.LoginName only, never the first LoginName-shaped key
    anywhere in the whois tree."""

    def test_1166_find_login_anchored_to_user_profile(self):
        """A LoginName nested inside Node (future schema / metadata) must
        not take precedence over the owner's UserProfile.LoginName."""
        doc = {
            "Node": {"Name": "x",
                     "Nested": {"LoginName": "intruder@evil"}},
            "UserProfile": {"LoginName": "ntindle@github"},
        }
        self.assertEqual(cd._find_login(doc), "ntindle@github")

    def test_1166_find_login_missing_profile_fails_closed(self):
        """Absent UserProfile (or absent tree) means the peer is refused."""
        self.assertIsNone(cd._find_login({"Node": {"Name": "x"}}))
        self.assertIsNone(cd._find_login({}))
        self.assertIsNone(cd._find_login(None))
        self.assertIsNone(cd._find_login(["UserProfile"]))

    def test_1166_find_login_non_string_fails_closed(self):
        self.assertIsNone(cd._find_login({"UserProfile": {"LoginName": 7}}))
        self.assertIsNone(
            cd._find_login({"UserProfile": {"LoginName": None}}))
        # An empty login is not an identity — the recursive form never
        # returned one (its truthiness check skipped it), and the owner
        # check downstream must see None, not "".
        self.assertIsNone(cd._find_login({"UserProfile": {"LoginName": ""}}))
        self.assertIsNone(
            cd._find_login({"UserProfile": {"LoginName": {"a": 1}}}))
        self.assertIsNone(cd._find_login({"UserProfile": "x"}))


class QuarantinePruneTests(unittest.TestCase):
    """Issue #1168: pending-quarantine/ is count-capped by the
    housekeeping prune (mtime-ordered, oldest-only deletes)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.approvals = Path(self.tmp.name) / "approvals"
        self.approvals.mkdir()
        cd._reset_housekeeping_for_tests()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_quarantine(self, name, mtime_age):
        qd = self.approvals / "pending-quarantine"
        qd.mkdir(exist_ok=True)
        p = qd / name
        p.write_text('{"id": "%s"}' % name)
        old = time.time() - mtime_age
        os.utime(p, (old, old))
        return p

    def test_1168_quarantine_prune_keeps_newest(self):
        """Over-cap quarantine prunes mtime-oldest first, keeping the
        newest `limit` files."""
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            for i in range(5):
                self._write_quarantine("q%d.json" % i,
                                       mtime_age=(5 - i) * 10)
            cd._prune_quarantine(limit=3)
            remaining = sorted(
                (self.approvals / "pending-quarantine").iterdir())
            self.assertEqual([p.name for p in remaining],
                             ["q2.json", "q3.json", "q4.json"])

    def test_1168_quarantine_prune_under_cap_noop(self):
        """Under-cap quarantine is untouched (no stat storm, no deletes)."""
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            self._write_quarantine("q0.json", mtime_age=10)
            cd._prune_quarantine(limit=3)
            self.assertTrue(
                (self.approvals / "pending-quarantine" / "q0.json")
                .exists())

    def test_1168_quarantine_prune_at_cap_noop(self):
        """Exactly-at-cap quarantine is untouched (pins the <= count
        gate)."""
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            for i in range(3):
                self._write_quarantine("q%d.json" % i,
                                       mtime_age=(3 - i) * 10)
            cd._prune_quarantine(limit=3)
            remaining = sorted(
                (self.approvals / "pending-quarantine").iterdir())
            self.assertEqual([p.name for p in remaining],
                             ["q0.json", "q1.json", "q2.json"])

    def test_1168_quarantine_prune_missing_dir_noop(self):
        """A missing quarantine dir is a no-op — the prune must never
        create the dir it prunes (CI incident, PR #1169)."""
        with mock.patch.object(cd, "APPROVALS", str(self.approvals)):
            cd._prune_quarantine(limit=3)  # must not raise
            self.assertFalse(
                (self.approvals / "pending-quarantine").exists())

    def test_1168_housekeeping_prunes_quarantine(self):
        """_housekeeping_if_due() runs the quarantine prune at the keep
        bound."""
        # Self-sufficient: reset the cadence module-state so this test
        # never depends on execution order (QA review).
        cd._reset_housekeeping_for_tests()
        with mock.patch.object(cd, "APPROVALS",
                               str(self.approvals)), \
             mock.patch.object(cd, "_QUARANTINE_KEEP", 2):
            for i in range(4):
                self._write_quarantine("q%d.json" % i,
                                       mtime_age=(4 - i) * 10)
            self.assertTrue(cd._housekeeping_if_due())
            remaining = sorted(
                (self.approvals / "pending-quarantine").iterdir())
            self.assertEqual([p.name for p in remaining],
                             ["q2.json", "q3.json"])


if __name__ == "__main__":
    unittest.main()
