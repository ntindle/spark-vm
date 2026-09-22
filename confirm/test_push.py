"""Tests for confirm/push.py (H2 / GitHub #2: VAPID push notifications).

Run with:
    python3 -m pytest confirm/test_push.py -q

No network is touched: urlopen is mocked. The decrypt side of the
RFC 8291 round-trip is implemented independently in the test.
"""
import base64
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import push
from push import b64url_decode

import pytest
# The VAPID round-trip tests below need the cryptography package. Skip
# explicitly instead of erroring collection on boxes without it, so the
# single-command `python3 -m pytest` degrades gracefully.
pytest.importorskip("cryptography",
                    reason="cryptography not installed — push-notification tests need it")

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature, encode_dss_signature)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat)


def _decrypt_aes128gcm(receiver_priv_b64u, auth_b64u, body: bytes) -> bytes:
    """Independent RFC 8291 aes128gcm decrypt (test oracle)."""
    priv = ec.derive_private_key(
        int.from_bytes(b64url_decode(receiver_priv_b64u), "big"),
        ec.SECP256R1())
    auth = b64url_decode(auth_b64u)
    salt, rs, idlen = body[:16], struct.unpack(">L", body[16:20])[0], body[20]
    eph_raw = body[21:21 + idlen]
    ct = body[21 + idlen:]
    assert rs == 4096 and len(eph_raw) == 65 and eph_raw[0] == 0x04
    eph_pub = ec.EllipticCurvePublicNumbers(
        int.from_bytes(eph_raw[1:33], "big"),
        int.from_bytes(eph_raw[33:65], "big"), ec.SECP256R1()).public_key()
    receiver_pub_raw = priv.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint)
    shared = priv.exchange(ec.ECDH(), eph_pub)
    info = b"WebPush: info\x00" + receiver_pub_raw + eph_raw
    prk = HKDF(algorithm=hashes.SHA256(), length=32, salt=auth,
               info=info).derive(shared)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt,
               info=b"Content-Encoding: aes128gcm\x00").derive(prk)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt,
                 info=b"Content-Encoding: nonce\x00").derive(prk)
    pt = AESGCM(cek).decrypt(nonce, ct, b"")
    assert pt.endswith(b"\x02"), "missing last-record delimiter"
    return pt[:-1]


def _make_sub(endpoint="https://push.example.com/p/token123"):
    priv, pub = push.gen_keypair()
    auth = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()
    return {"endpoint": endpoint,
            "keys": {"p256dh": pub, "auth": auth},
            "_priv": priv}


class B64Tests(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(b64url_decode(push.b64url_encode(b"\x00\xff abc")),
                         b"\x00\xff abc")

    def test_rejects_bad_chars(self):
        with self.assertRaises(ValueError):
            b64url_decode("not valid!!")
        with self.assertRaises(ValueError):
            b64url_decode(123)


class KeypairTests(unittest.TestCase):
    def test_lengths(self):
        priv, pub = push.gen_keypair()
        self.assertEqual(len(b64url_decode(priv)), 32)
        raw = b64url_decode(pub)
        self.assertEqual(len(raw), 65)
        self.assertEqual(raw[0], 0x04)

    def test_jwt_verifies_with_public_key(self):
        priv, pub = push.gen_keypair()
        jwt = push.vapid_jwt("https://push.example.com", priv,
                             "mailto:test@example.com")
        header_b64, claims_b64, sig_b64 = jwt.split(".")
        header = json.loads(b64url_decode(header_b64))
        claims = json.loads(b64url_decode(claims_b64))
        self.assertEqual(header, {"typ": "JWT", "alg": "ES256"})
        self.assertEqual(claims["aud"], "https://push.example.com")
        self.assertEqual(claims["sub"], "mailto:test@example.com")
        import time as _time
        skew = claims["exp"] - int(_time.time())
        self.assertTrue(0 < skew <= 12 * 3600 + 5,
                        "exp should be ~12h in the future, got skew %s" % skew)
        raw = b64url_decode(pub)
        pubkey = ec.EllipticCurvePublicNumbers(
            int.from_bytes(raw[1:33], "big"),
            int.from_bytes(raw[33:65], "big"), ec.SECP256R1()).public_key()
        sig = b64url_decode(sig_b64)
        r = int.from_bytes(sig[:32], "big")
        s = int.from_bytes(sig[32:], "big")
        pubkey.verify(encode_dss_signature(r, s),
                      (header_b64 + "." + claims_b64).encode(),
                      ec.ECDSA(hashes.SHA256()))

    def test_jwt_wrong_key_fails(self):
        priv, _ = push.gen_keypair()
        _, pub2 = push.gen_keypair()
        jwt = push.vapid_jwt("https://push.example.com", priv, "mailto:x")
        header_b64, claims_b64, sig_b64 = jwt.split(".")
        raw = b64url_decode(pub2)
        pubkey = ec.EllipticCurvePublicNumbers(
            int.from_bytes(raw[1:33], "big"),
            int.from_bytes(raw[33:65], "big"), ec.SECP256R1()).public_key()
        sig = b64url_decode(sig_b64)
        with self.assertRaises(Exception):
            pubkey.verify(
                encode_dss_signature(int.from_bytes(sig[:32], "big"),
                                     int.from_bytes(sig[32:], "big")),
                (header_b64 + "." + claims_b64).encode(),
                ec.ECDSA(hashes.SHA256()))


class EncryptTests(unittest.TestCase):
    def test_roundtrip(self):
        sub = _make_sub()
        pt = b'{"title":"hi"}'
        body = push.encrypt_message(sub["keys"]["p256dh"],
                                    sub["keys"]["auth"], pt)
        self.assertEqual(_decrypt_aes128gcm(sub["_priv"],
                                            sub["keys"]["auth"], body), pt)

    def test_roundtrip_empty(self):
        sub = _make_sub()
        body = push.encrypt_message(sub["keys"]["p256dh"],
                                    sub["keys"]["auth"], b"")
        self.assertEqual(_decrypt_aes128gcm(sub["_priv"],
                                            sub["keys"]["auth"], body), b"")

    def test_rejects_bad_keys(self):
        sub = _make_sub()
        with self.assertRaises(ValueError):
            push.encrypt_message("AAAA", sub["keys"]["auth"], b"x")
        with self.assertRaises(ValueError):
            push.encrypt_message(sub["keys"]["p256dh"], "AAAA", b"x")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "subs.json")
        self.store = push.SubscriptionStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_list_remove(self):
        sub = _make_sub()
        self.store.add(sub["endpoint"], sub["keys"]["p256dh"],
                       sub["keys"]["auth"])
        all_subs = self.store.all()
        self.assertEqual(len(all_subs), 1)
        self.assertEqual(all_subs[0]["endpoint"], sub["endpoint"])
        self.assertTrue(self.store.remove(sub["endpoint"]))
        self.assertEqual(self.store.all(), [])
        self.assertFalse(self.store.remove(sub["endpoint"]))

    def test_add_replaces_same_endpoint(self):
        sub = _make_sub()
        self.store.add(sub["endpoint"], sub["keys"]["p256dh"],
                       sub["keys"]["auth"])
        sub2 = _make_sub(endpoint=sub["endpoint"])
        self.store.add(sub2["endpoint"], sub2["keys"]["p256dh"],
                       sub2["keys"]["auth"])
        self.assertEqual(len(self.store.all()), 1)

    def test_rejects_non_https(self):
        sub = _make_sub()
        with self.assertRaises(ValueError):
            self.store.add("http://push.example.com/x",
                           sub["keys"]["p256dh"], sub["keys"]["auth"])

    def test_rejects_bad_key_material(self):
        sub = _make_sub()
        with self.assertRaises(ValueError):
            self.store.add(sub["endpoint"], "AAAA", sub["keys"]["auth"])
        with self.assertRaises(ValueError):
            self.store.add(sub["endpoint"], sub["keys"]["p256dh"], "AAAA")

    def test_file_is_0600(self):
        sub = _make_sub()
        self.store.add(sub["endpoint"], sub["keys"]["p256dh"],
                       sub["keys"]["auth"])
        self.assertEqual(oct(os.stat(self.path).st_mode & 0o777), "0o600")

    def test_survives_corrupt_file(self):
        Path(self.path).write_text("{not json")
        self.assertEqual(self.store.all(), [])


class FakeHTTPResponse:
    def __init__(self, code):
        self._code = code

    def getcode(self):
        return self._code

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.keys = str(Path(self.tmp.name) / "vapid.json")
        self.subs = str(Path(self.tmp.name) / "subs.json")
        priv, pub = push.gen_keypair()
        Path(self.keys).write_text(json.dumps({"private": priv,
                                               "public": pub}))
        self.sender = push.PushSender(self.keys, self.subs,
                                      "mailto:test@example.com")
        self.sent_requests = []

    def tearDown(self):
        self.tmp.cleanup()

    def _urlopen_ok(self, req, timeout=None):
        self.sent_requests.append(req)
        return FakeHTTPResponse(201)

    def test_disabled_without_keys(self):
        s = push.PushSender(str(Path(self.tmp.name) / "missing.json"),
                            self.subs, "mailto:x")
        self.assertFalse(s.enabled)
        self.assertEqual(s.notify_approval({"id": "abc"}), 0)

    def test_world_readable_keys_warn(self):
        """Issue #77 (L2): a group/world-readable vapid.json logs a
        loud warning; the keys still load (availability), the operator
        is told to chmod 600."""
        os.chmod(self.keys, 0o644)
        with self.assertLogs(push.log, level="WARNING") as cm:
            s = push.PushSender(self.keys, self.subs, "mailto:x")
        self.assertTrue(s.enabled)
        self.assertTrue(any("chmod 600" in m for m in cm.output))

    def test_owner_only_keys_no_warn(self):
        """A 0600 keys file loads silently."""
        os.chmod(self.keys, 0o600)
        with self.assertNoLogs(push.log, level="WARNING"):
            s = push.PushSender(self.keys, self.subs, "mailto:x")
        self.assertTrue(s.enabled)

    def test_public_key_exposed(self):
        self.assertEqual(len(b64url_decode(self.sender.public_key_b64u)), 65)

    def test_notify_sends_encrypted_push(self):
        sub = _make_sub()
        self.sender.subs.add(sub["endpoint"], sub["keys"]["p256dh"],
                             sub["keys"]["auth"])
        with mock.patch("urllib.request.urlopen", self._urlopen_ok):
            sent = self.sender.notify_approval(
                {"id": "abc123", "summary": "POST https://api.x/ for cred"})
        self.assertEqual(sent, 1)
        self.assertEqual(len(self.sent_requests), 1)
        req = self.sent_requests[0]
        self.assertEqual(req.full_url, sub["endpoint"])
        self.assertEqual(req.get_header("Content-encoding"), "aes128gcm")
        self.assertEqual(req.get_header("Ttl"), "3600")
        authz = req.get_header("Authorization")
        self.assertTrue(authz.startswith("vapid t="))
        self.assertIn(", k=", authz)
        # The VAPID public key in the header matches the configured one.
        self.assertTrue(authz.endswith(self.sender.public_key_b64u))
        # The payload decrypts to our notification JSON.
        pt = _decrypt_aes128gcm(sub["_priv"], sub["keys"]["auth"],
                                req.data)
        doc = json.loads(pt)
        self.assertEqual(doc["title"], "Approval needed")
        self.assertEqual(doc["approval_id"], "abc123")
        self.assertIn("cred", doc["body"])

    def test_notify_is_idempotent(self):
        sub = _make_sub()
        self.sender.subs.add(sub["endpoint"], sub["keys"]["p256dh"],
                             sub["keys"]["auth"])
        with mock.patch("urllib.request.urlopen", self._urlopen_ok):
            self.assertEqual(
                self.sender.notify_approval({"id": "abc123"}), 1)
            self.assertEqual(
                self.sender.notify_approval({"id": "abc123"}), 0)
        self.assertEqual(len(self.sent_requests), 1)

    def test_notify_prunes_dead_subscriptions(self):
        sub = _make_sub()
        self.sender.subs.add(sub["endpoint"], sub["keys"]["p256dh"],
                             sub["keys"]["auth"])

        def gone(req, timeout=None):
            return FakeHTTPResponse(410)

        with mock.patch("urllib.request.urlopen", gone):
            self.assertEqual(
                self.sender.notify_approval({"id": "abc123"}), 0)
        self.assertEqual(self.sender.subs.all(), [])

    def test_notify_rejects_bad_id(self):
        sub = _make_sub()
        self.sender.subs.add(sub["endpoint"], sub["keys"]["p256dh"],
                             sub["keys"]["auth"])
        with mock.patch("urllib.request.urlopen", self._urlopen_ok):
            self.assertEqual(
                self.sender.notify_approval({"id": "../../evil"}), 0)
        self.assertEqual(self.sent_requests, [])

    def test_notify_never_raises(self):
        sub = _make_sub()
        self.sender.subs.add(sub["endpoint"], sub["keys"]["p256dh"],
                             sub["keys"]["auth"])

        def boom(req, timeout=None):
            raise OSError("network down")

        with mock.patch("urllib.request.urlopen", boom):
            self.assertEqual(
                self.sender.notify_approval({"id": "abc123"}), 0)

    def test_notified_log_caps(self):
        log_path = self.subs + ".notified.json"
        nl = push.NotifiedLog(log_path)
        for i in range(1100):
            nl.mark("id-%d" % i)
        noted = nl._load()
        self.assertLessEqual(len(noted), 1000)
        self.assertTrue(nl.seen("id-1099"))


class GenKeysCLITests(unittest.TestCase):
    def test_gen_keys_writes_0600_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "vapid.json")
            rc = push.main(["--gen-keys", path])
            self.assertEqual(rc, 0)
            doc = json.loads(Path(path).read_text())
            self.assertEqual(len(b64url_decode(doc["private"])), 32)
            self.assertEqual(len(b64url_decode(doc["public"])), 65)
            self.assertEqual(oct(os.stat(path).st_mode & 0o777), "0o600")

    def test_gen_keys_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "vapid.json")
            Path(path).write_text("{}")
            with self.assertRaises(FileExistsError):
                push.main(["--gen-keys", path])
            # Existing file untouched.
            self.assertEqual(Path(path).read_text(), "{}")


# --------------------------------------------------------------------------
# confirmd push-endpoint integration (handler level, sockets stubbed)
# --------------------------------------------------------------------------

import io as _io

def _fake_ts_run(cmd, **kwargs):
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

with mock.patch("subprocess.run", side_effect=_fake_ts_run):
    import confirmd as cd

cd.AUDIT = os.devnull  # silence audit log in tests


class _StubHandler:
    """Drives cd.Handler methods without a socket."""

    def __init__(self, tc, path, body=b"", headers=None):
        h = cd.Handler.__new__(cd.Handler)
        h.path = path
        hdrs = {"Content-Length": str(len(body))}
        hdrs.update(headers or {})
        h.headers = hdrs
        h.rfile = _io.BytesIO(body)
        self.wfile_bytes = _io.BytesIO()
        h.wfile = self.wfile_bytes
        h.client_address = ("100.99.99.99", 1234)
        h._auth = lambda: "ntindle@github"
        self.captured = {}
        h.send_response = lambda code: self.captured.setdefault(
            "code", code)
        h.send_header = lambda k, v: self.captured.setdefault(
            "headers", {}).__setitem__(k, v)
        h.end_headers = lambda: self.captured.setdefault("headers_done",
                                                         True)
        h._send_json = lambda obj, code=200: self.captured.update(
            json=obj, code=code)
        h._deny = lambda peer, login, why: self.captured.update(denied=why)
        h._err = lambda msg, code: self.captured.update(err=(msg, code))
        self.h = h

    def do_get(self):
        self.h.do_GET()
        return self.captured

    def do_post(self):
        self.h.do_POST()
        return self.captured


class ConfirmdPushEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Issue #80: GET / drives do_GET() -> _render_pending_list() ->
        # pending_dir() -> os.makedirs(APPROVALS/pending); point APPROVALS
        # at tmp like test_confirmd.py does, so the suite is hermetic on
        # machines where /home/swapd is not writable (e.g. spark-vm).
        self._appr = tempfile.TemporaryDirectory()
        self._appr_patch = mock.patch.object(
            cd, "APPROVALS", self._appr.name)
        self._appr_patch.start()
        # QA follow-up: a tripwire — if a future edit breaks the #80
        # patch above, fail loudly instead of silently re-polluting the
        # host /home/swapd (on root runners tests still pass while the
        # literal dir gets created).
        assert cd.APPROVALS == self._appr.name
        self.addCleanup(self._appr.cleanup)
        self.addCleanup(self._appr_patch.stop)
        self.keys = str(Path(self.tmp.name) / "vapid.json")
        self.subs = str(Path(self.tmp.name) / "subs.json")
        priv, pub = push.gen_keypair()
        Path(self.keys).write_text(json.dumps({"private": priv,
                                               "public": pub}))
        self.sender = push.PushSender(self.keys, self.subs, "mailto:t")
        self._orig = (cd._PUSH, cd.PUSH_ENABLED)
        cd._PUSH = self.sender
        cd.PUSH_ENABLED = True

    def tearDown(self):
        cd._PUSH, cd.PUSH_ENABLED = self._orig
        self.tmp.cleanup()

    def _sub_body(self, endpoint="https://push.example.com/p/abc"):
        sub = _make_sub(endpoint=endpoint)
        return (json.dumps({"endpoint": sub["endpoint"],
                            "keys": sub["keys"]}).encode(), sub)

    def test_config_reports_enabled_and_public_key(self):
        c = _StubHandler(self, "/api/push/config").do_get()
        self.assertTrue(c["json"]["enabled"])
        self.assertEqual(len(b64url_decode(c["json"]["public_key"])), 65)

    def test_config_disabled_without_keys(self):
        cd._PUSH, cd.PUSH_ENABLED = None, False
        cd.PUSH_DISABLED_REASON = "no-keys: /none (No such file)"
        c = _StubHandler(self, "/api/push/config").do_get()
        self.assertFalse(c["json"]["enabled"])
        self.assertIsNone(c["json"]["public_key"])
        self.assertIn("no-keys", c["json"]["disabled_reason"])

    def test_sw_js_served(self):
        stub = _StubHandler(self, "/sw.js")
        c = stub.do_get()
        self.assertEqual(c["code"], 200)
        self.assertEqual(c["headers"]["Content-Type"],
                         "application/javascript")
        body = stub.wfile_bytes.getvalue()
        self.assertIn(b"showNotification", body)
        self.assertIn(b"/approval/", body)

    def test_subscribe_stores_subscription(self):
        body, sub = self._sub_body()
        c = _StubHandler(self, "/api/push/subscribe", body,
                         {"Content-Type": "application/json"}).do_post()
        self.assertEqual(c["json"], {"ok": True})
        stored = self.sender.subs.all()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["endpoint"], sub["endpoint"])

    def test_subscribe_rejects_http_endpoint(self):
        body, _ = self._sub_body(endpoint="http://push.example.com/x")
        c = _StubHandler(self, "/api/push/subscribe", body,
                         {"Content-Type": "application/json"}).do_post()
        self.assertEqual(c["code"], 400)
        self.assertFalse(c["json"]["ok"])
        self.assertEqual(self.sender.subs.all(), [])

    def test_subscribe_rejects_bad_json(self):
        c = _StubHandler(self, "/api/push/subscribe", b"{nope",
                         {"Content-Type": "application/json"}).do_post()
        self.assertEqual(c["code"], 400)

    def test_subscribe_503_when_disabled(self):
        cd._PUSH, cd.PUSH_ENABLED = None, False
        body, _ = self._sub_body()
        c = _StubHandler(self, "/api/push/subscribe", body,
                         {"Content-Type": "application/json"}).do_post()
        self.assertEqual(c["code"], 503)

    def test_unsubscribe_removes(self):
        body, sub = self._sub_body()
        _StubHandler(self, "/api/push/subscribe", body,
                     {"Content-Type": "application/json"}).do_post()
        ubody = json.dumps({"endpoint": sub["endpoint"]}).encode()
        c = _StubHandler(self, "/api/push/unsubscribe", ubody,
                         {"Content-Type": "application/json"}).do_post()
        self.assertEqual(c["json"], {"ok": True})
        self.assertEqual(self.sender.subs.all(), [])

    def test_cross_site_post_denied(self):
        body, _ = self._sub_body()
        c = _StubHandler(self, "/api/push/subscribe", body,
                         {"Content-Type": "application/json",
                          "Sec-Fetch-Site": "cross-site"}).do_post()
        self.assertIn("denied", c)
        self.assertEqual(self.sender.subs.all(), [])

    def test_bad_origin_denied(self):
        body, _ = self._sub_body()
        c = _StubHandler(self, "/api/push/subscribe", body,
                         {"Content-Type": "application/json",
                          "Origin": "https://evil.example.com:8443"}
                         ).do_post()
        self.assertIn("denied", c)
        self.assertEqual(self.sender.subs.all(), [])

    def test_unknown_post_path_404(self):
        c = _StubHandler(self, "/api/nope", b"x").do_post()
        self.assertEqual(c["code"], 404)

    def test_pending_page_has_push_button(self):
        stub = _StubHandler(self, "/")
        c = stub.do_get()
        self.assertEqual(c["code"], 200)
        page = stub.wfile_bytes.getvalue().decode()
        self.assertIn('id="pushBtn"', page)
        self.assertIn('id="pushStatus"', page)
        self.assertIn("/api/push/subscribe", page)


class NotifyFailureSemanticsTests(unittest.TestCase):
    """QA B2 / Engineering B1: the idempotency mark must not fire on
    total transient failure — otherwise an outage silently drops the
    notification with no retry path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.keys = str(Path(self.tmp.name) / "vapid.json")
        self.subs = str(Path(self.tmp.name) / "subs.json")
        priv, pub = push.gen_keypair()
        Path(self.keys).write_text(json.dumps({"private": priv,
                                               "public": pub}))
        self.sender = push.PushSender(self.keys, self.subs, "mailto:t")
        sub = _make_sub()
        self.sender.subs.add(sub["endpoint"], sub["keys"]["p256dh"],
                             sub["keys"]["auth"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_sends_fail_not_marked(self):
        def boom(req, timeout=None):
            raise OSError("push service down")

        with mock.patch("urllib.request.urlopen", boom):
            self.assertEqual(
                self.sender.notify_approval({"id": "aid1"}), 0)
        # Not marked: a later attempt still delivers.
        self.assertFalse(self.sender.notified.seen("aid1"))

    def test_retry_after_failure_delivers(self):
        def boom(req, timeout=None):
            raise OSError("push service down")

        with mock.patch("urllib.request.urlopen", boom):
            self.sender.notify_approval({"id": "aid1"})
        calls = []

        def ok(req, timeout=None):
            calls.append(req)
            return FakeHTTPResponse(201)

        with mock.patch("urllib.request.urlopen", ok):
            self.assertEqual(
                self.sender.notify_approval({"id": "aid1"}), 1)
        self.assertEqual(len(calls), 1)
        self.assertTrue(self.sender.notified.seen("aid1"))

    def test_partial_failure_not_marked(self):
        sub2 = _make_sub(endpoint="https://push.example.com/p/other")
        self.sender.subs.add(sub2["endpoint"], sub2["keys"]["p256dh"],
                             sub2["keys"]["auth"])

        def flaky(req, timeout=None):
            if "other" in req.full_url:
                raise OSError("one endpoint down")
            return FakeHTTPResponse(201)

        with mock.patch("urllib.request.urlopen", flaky):
            self.assertEqual(
                self.sender.notify_approval({"id": "aid2"}), 1)
        # One sub failed transiently: not marked, so the failed one can
        # still be retried later.
        self.assertFalse(self.sender.notified.seen("aid2"))

    def test_disabled_reason_no_keys(self):
        s = push.PushSender(str(Path(self.tmp.name) / "missing.json"),
                            self.subs, "mailto:x")
        self.assertFalse(s.enabled)
        self.assertIn("no-keys", s.disabled_reason)

    def test_test_push_cli(self):
        calls = []

        def ok(req, timeout=None):
            calls.append(req)
            return FakeHTTPResponse(201)

        with mock.patch.dict("os.environ",
                             {"CONFIRM_VAPID_KEYS": self.keys,
                              "CONFIRM_PUSH_SUBS": self.subs}):
            with mock.patch("urllib.request.urlopen", ok):
                rc = push.main(["--test-push"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1)

    def test_test_push_cli_disabled(self):
        with mock.patch.dict("os.environ",
                             {"CONFIRM_VAPID_KEYS": "/nonexistent.json",
                              "CONFIRM_PUSH_SUBS": self.subs}):
            rc = push.main(["--test-push"])
        self.assertEqual(rc, 1)


class PushServerPipelineTests(unittest.TestCase):
    """QA B5, closest available to E2E without a real device: a real
    browser-style keypair subscribes through the real confirmd handler,
    then the server's own sender emits the approval push — the captured
    wire POST decrypts with the browser key, and the served /sw.js maps
    the notification tag to the approval deep link. The one unverifiable
    mile is the browser rendering the notification; that needs a real
    device and is an operator step via `push.py --test-push`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.keys = str(Path(self.tmp.name) / "vapid.json")
        self.subs = str(Path(self.tmp.name) / "subs.json")
        priv, pub = push.gen_keypair()
        Path(self.keys).write_text(json.dumps({"private": priv,
                                               "public": pub}))
        self.sender = push.PushSender(self.keys, self.subs, "mailto:t")
        self._orig = (cd._PUSH, cd.PUSH_ENABLED)
        cd._PUSH = self.sender
        cd.PUSH_ENABLED = True

    def tearDown(self):
        cd._PUSH, cd.PUSH_ENABLED = self._orig
        self.tmp.cleanup()

    def test_subscribe_then_notify_then_decrypt_pipeline(self):
        sub = _make_sub()
        body = json.dumps({"endpoint": sub["endpoint"],
                           "keys": sub["keys"]}).encode()
        c = _StubHandler(self, "/api/push/subscribe", body=body).do_post()
        self.assertEqual(c["code"], 200)

        captured = []

        def fake_urlopen(req, timeout=None):
            captured.append(req)
            return FakeHTTPResponse(201)

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            sent = cd._PUSH.notify_approval({"id": "e2e9",
                                             "summary": "pipeline test"})
        self.assertEqual(sent, 1)
        self.assertEqual(len(captured), 1)
        pt = _decrypt_aes128gcm(sub["_priv"], sub["keys"]["auth"],
                                captured[0].data)
        doc = json.loads(pt)
        self.assertEqual(doc["approval_id"], "e2e9")
        self.assertEqual(doc["title"], "Approval needed")

        # /sw.js deep-link contract: notification tag "approval-<id>"
        # taps through to "/approval/<id>".
        stub = _StubHandler(self, "/sw.js")
        stub.do_get()
        sw = stub.wfile_bytes.getvalue().decode()
        self.assertIn('"approval-" + aid', sw)
        self.assertIn('"/approval/" + aid', sw)


if __name__ == "__main__":
    unittest.main()
