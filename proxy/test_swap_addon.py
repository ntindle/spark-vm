"""Conformance tests for proxy/swap_addon.py.

Run from the repo root:
    python3 -m unittest proxy/test_swap_addon.py

No mitmproxy needed: the addon is stdlib-only, and these tests use a
minimal fake flow exposing only the attributes request() reads. If
mitmproxy is installed, mitmproxy.test.tflow can replace the fake.

Tests named test_bug_* encode the expected behaviour from
browser-driver/REVIEW.md. Tests named test_holds_* pass today and guard
against regressions. Nothing here touches /home/swapd: reload and audit
are stubbed out, and make_addon injects the registry (per-credential
allowed_hosts) directly.
"""

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swap_addon as sa  # noqa: E402

import logging  # noqa: E402
sa.log.propagate = False            # keep addon warnings out of test output
sa.log.addHandler(logging.NullHandler())


# ---------------------------------------------------------------- fakes

class Headers:
    def __init__(self, items=()):
        self._items = list(items)

    def keys(self):
        seen = []
        for k, _ in self._items:
            if k not in seen:
                seen.append(k)
        return seen

    def get_all(self, key):
        return [v for k, v in self._items if k.lower() == key.lower()]

    def set_all(self, key, values):
        self._items = [(k, v) for k, v in self._items
                       if k.lower() != key.lower()]
        self._items += [(key, v) for v in values]

    def get(self, key, default=""):
        vals = self.get_all(key)
        return vals[0] if vals else default

    def __contains__(self, key):
        return any(k.lower() == key.lower() for k, _ in self._items)

    def __setitem__(self, key, value):
        self.set_all(key, [value])


class Query:
    def __init__(self, path):
        _, _, q = path.partition("?")
        self._items = urllib.parse.parse_qsl(q, keep_blank_values=True)

    def items(self, multi=False):
        return list(self._items)


class Request:
    def __init__(self, host, path="/", headers=(), content=b"", method="GET"):
        self.pretty_host = host
        self.path = path
        self.method = method
        self.headers = Headers(headers)
        self.content = content

    @property
    def query(self):
        return Query(self.path)


class Flow:
    def __init__(self, request):
        self.request = request
        self.response = None
        self.websocket = None


class FakeServerConn:
    """Minimal mitmproxy Server for the server_connect hook."""
    def __init__(self, host, port=443):
        self.address = (host, port)
        self.error = None


class FakeServerConnectData:
    def __init__(self, host, port=443):
        self.server = FakeServerConn(host, port)
        self.client = None


class FakeResponse:
    """Minimal mitmproxy response: text property, content, headers."""
    def __init__(self, content, content_type):
        self.content = content
        self.headers = Headers([("content-type", content_type),
                                ("content-length", str(len(content)))])

    @property
    def text(self):
        return self.content.decode("utf-8")

    @text.setter
    def text(self, value):
        self.content = value.encode("utf-8")


class FakeWSMessage:
    def __init__(self, content, is_binary=False):
        self.content = content
        self.is_binary = is_binary


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = messages


class _FakeMPResponse:
    def __init__(self, status, content, headers):
        self.status_code = status
        self.content = content
        self.headers = headers


SECRETS = {
    "github": "ghp_TOKEN",
    "openai": "sk-OPENAI",
    "pw": 'p&ss=w"o\\rd%7d',
    "sess": "sess-SECRET",
    "acme": {"username": "jdoe", "password": "correct horse",
             "totp": "JBSWY3DPEHPK3PXP"},
}
HOSTS = ["github.com", "api.github.com", "acme.example.com"]
# Per-credential host bindings (REVIEW item 1). hosts.allow stays the outer
# gate; a credential swaps only where BOTH allow it.
REGISTRY = {
    "github": {"allowed_hosts": ["github.com", "api.github.com"]},
    "openai": {"allowed_hosts": ["api.openai.com"]},
    "pw": {"allowed_hosts": ["github.com", "api.github.com"]},
    "sess": {"allowed_hosts": ["github.com"],
             "access_token": {"placement": {"custom_header": "Cookie"}}},
    "acme": {"allowed_hosts": ["acme.example.com"]},
}


def make_addon(secrets=SECRETS, hosts=HOSTS, registry=REGISTRY):
    a = sa.SwapAddon.__new__(sa.SwapAddon)
    a.secrets = dict(secrets)
    a.hosts = list(hosts)
    a.registry = {k: (dict(v) if isinstance(v, dict) else v)
                  for k, v in registry.items()}
    a.inference_mode = False
    a.ssrf_hosts = []
    a.ssrf_nets = []
    # Hermetic DNS: test hosts fail open without a real lookup. Tests that
    # exercise the SSRF guard seed _dns_cache themselves.
    a._dns_cache = {h: (time.time() + 3600, None)
                    for h in list(hosts) + ["evil.example"]}
    a._store_mtime = a._hosts_mtime = None
    a._maybe_reload = lambda: None      # never touch /home/swapd here
    a._audit = lambda host, matched: None
    a.refused = []
    a._audit_refused = lambda host, name, reason: a.refused.append(
        (host, name, reason))
    a.ssrf_refused = []
    a._audit_ssrf_refused = lambda host, ip, reason: a.ssrf_refused.append(
        (host, ip, reason))
    return a


def totp(seed_b32, at, step=30, digits=6):
    key = base64.b32decode(seed_b32.upper() + "=" * (-len(seed_b32) % 8))
    counter = struct.pack(">Q", int(at) // step)
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


# ---------------------------------------------------------------- tests

class SwapAddonTests(unittest.TestCase):

    # --- holds today ------------------------------------------------

    def test_holds_browser_form_reencodes_value(self):
        a = make_addon()
        req = Request("github.com", "/login",
                      [("Content-Type", "application/x-www-form-urlencoded")],
                      b"user=x&password=hsurr%3Apw")
        a.request(Flow(req))
        fields = urllib.parse.parse_qs(req.content.decode())
        self.assertEqual(fields["password"], [SECRETS["pw"]])
        self.assertEqual(fields["user"], ["x"])

    def test_holds_bearer_header(self):
        a = make_addon()
        req = Request("api.github.com", "/user",
                      [("Authorization", "Bearer hsurr:github")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"), "Bearer ghp_TOKEN")

    def test_holds_basic_auth_decoded_and_reencoded(self):
        a = make_addon()
        b64 = base64.b64encode(b"x-access-token:hsurr:github").decode()
        req = Request("github.com", "/ntindle/spark-vm.git/info/refs",
                      [("Authorization", "Basic " + b64)])
        a.request(Flow(req))
        got = base64.b64decode(req.headers.get("Authorization").split()[1])
        self.assertEqual(got, b"x-access-token:ghp_TOKEN")

    def test_holds_non_allowlisted_host_passes_through(self):
        a = make_addon()
        req = Request("evil.example", "/collect?t=hsurr:github",
                      [("Authorization", "Bearer hsurr:github")],
                      b'{"k":"hsurr:github"}')
        a.request(Flow(req))
        self.assertEqual(req.path, "/collect?t=hsurr:github")
        self.assertEqual(req.headers.get("Authorization"), "Bearer hsurr:github")
        self.assertEqual(req.content, b'{"k":"hsurr:github"}')

    def test_holds_unknown_entry_on_multi_entry_secret_untouched(self):
        a = make_addon()
        self.assertEqual(a._swap_text("hsurr:acme:nope", "acme.example.com"),
                         "hsurr:acme:nope")

    # --- bugs: expected to fail at a006f6e -------------------------

    def test_bug_literal_colon_form_body_is_encoded(self):
        """REVIEW item 6: curl/requests send 'hsurr:' unencoded in forms;
        the swapped value must still be form-encoded."""
        a = make_addon()
        req = Request("github.com", "/login",
                      [("Content-Type", "application/x-www-form-urlencoded")],
                      b"user=x&password=hsurr:pw")
        a.request(Flow(req))
        fields = urllib.parse.parse_qs(req.content.decode())
        self.assertEqual(fields.get("password"), [SECRETS["pw"]])
        self.assertEqual(sorted(fields), ["password", "user"])

    def test_bug_json_body_value_is_escaped(self):
        """REVIEW item 5: a value with quotes/backslashes must not break JSON."""
        a = make_addon()
        req = Request("api.github.com", "/login",
                      [("Content-Type", "application/json")],
                      b'{"password":"hsurr:pw"}')
        a.request(Flow(req))
        try:
            body = json.loads(req.content.decode())
        except ValueError as e:
            self.fail("swapped body is not valid JSON: %s" % e)
        self.assertEqual(body["password"], SECRETS["pw"])

    def test_bug_entry_suffix_not_swallowed_on_single_value_secret(self):
        """REVIEW item 7: 'hsurr:github:8080' must not eat ':8080'."""
        a = make_addon()
        out = a._swap_text("hsurr:github:8080", "github.com")
        self.assertIn(":8080", out)

    def test_bug_referer_is_not_swapped(self):
        """REVIEW item 8: swapping Referer sends the real token to the
        server's access log."""
        a = make_addon()
        req = Request("github.com", "/next",
                      [("Referer", "https://github.com/cb?token=hsurr:github"),
                       ("Authorization", "Bearer hsurr:github")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"), "Bearer ghp_TOKEN")
        self.assertEqual(req.headers.get("Referer"),
                         "https://github.com/cb?token=hsurr:github")

    def test_bug_path_swap_preserves_encoded_percent(self):
        """REVIEW item 9: re-quoting must not turn %25 into a bare %."""
        a = make_addon()
        req = Request("api.github.com", "/v1/100%25/hsurr:github/x")
        a.request(Flow(req))
        self.assertEqual(req.path, "/v1/100%25/ghp_TOKEN/x")

    def test_bug_totp_entry_yields_code_not_seed(self):
        """REVIEW item 23: hsurr:<name>:totp must become the current
        6-digit code, never the base32 seed."""
        a = make_addon()
        now = time.time()
        out = a._swap_text("code=hsurr:acme:totp", "acme.example.com")
        code = out.partition("=")[2]
        self.assertNotIn("JBSWY3DPEHPK3PXP", out)
        self.assertRegex(code, r"^\d{6}$")
        self.assertIn(code, {totp("JBSWY3DPEHPK3PXP", now),
                             totp("JBSWY3DPEHPK3PXP", now - 30)})

    def test_bug_credential_bound_to_its_own_hosts(self):
        """REVIEW item 1: a credential swaps only on its bound hosts, even
        when the request host is in hosts.allow."""
        a = make_addon()
        # openai is bound to api.openai.com only: github.com is allowlisted
        # but the swap must be refused there.
        self.assertEqual(a._swap_text("body=hsurr:openai", "github.com"),
                         "body=hsurr:openai")
        req = Request("github.com", "/v1/chat",
                      [("Authorization", "Bearer hsurr:openai")],
                      b'{"model":"x"}')
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"),
                         "Bearer hsurr:openai")
        self.assertEqual(req.content, b'{"model":"x"}')
        # ... while the bound host swaps fine (outer gate also allows it).
        b = make_addon(hosts=HOSTS + ["api.openai.com"])
        req = Request("api.openai.com", "/v1/chat",
                      [("Authorization", "Bearer hsurr:openai")])
        b.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"),
                         "Bearer sk-OPENAI")
        # Fail closed: a credential with no registry entry never swaps,
        # even on an allowlisted host.
        c = make_addon(registry={})
        self.assertEqual(c._swap_text("body=hsurr:github", "github.com"),
                         "body=hsurr:github")

    def test_bug_origin_is_not_swapped(self):
        """REVIEW item 8: Origin, like Referer, must never be swapped."""
        a = make_addon()
        req = Request("github.com", "/x",
                      [("Origin", "https://github.com/hsurr:github")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Origin"),
                         "https://github.com/hsurr:github")

    def test_bug_cookie_swapped_only_with_cookie_placement(self):
        """REVIEW item 8: Cookie swaps only for credentials whose registry
        placement explicitly names the Cookie header."""
        a = make_addon()
        # 'sess' has {"custom_header": "Cookie"}: swapped.
        req = Request("github.com", "/x", [("Cookie", "sess=hsurr:sess")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Cookie"), "sess=sess-SECRET")
        # 'github' has no Cookie placement: untouched, even mixed with one
        # that does.
        req = Request("github.com", "/x",
                      [("Cookie", "t=hsurr:github; sess=hsurr:sess")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Cookie"),
                         "t=hsurr:github; sess=sess-SECRET")

    def test_bug_subdomain_binding_matches(self):
        """Item 1: a leading-dot allowed_hosts entry matches subdomains,
        the same shape ensure_allowed_url takes."""
        reg = {"openai": {"allowed_hosts": [".example.com"]}}
        a = make_addon(hosts=["api.example.com"], registry=reg)
        self.assertEqual(
            a._swap_text("k=hsurr:openai", "api.example.com"), "k=sk-OPENAI")
        self.assertEqual(
            a._swap_text("k=hsurr:openai", "other.com"), "k=hsurr:openai")

    # --- review round 2 -------------------------------------------------

    def test_bug_response_scrubs_secret_values(self):
        """REVIEW item 4: a 'review your details' response must not hand
        secret values back through the driver's text reads."""
        a = make_addon()
        code = sa._totp_code("JBSWY3DPEHPK3PXP")
        body = ('{"token":"ghp_TOKEN","pw":"correct horse",'
                '"otp":"%s"}' % code).encode()
        resp = FakeResponse(body, "application/json")
        flow = Flow(Request("github.com", "/"))
        flow.response = resp
        a.response(flow)
        self.assertNotIn(b"ghp_TOKEN", resp.content)
        self.assertNotIn(b"correct horse", resp.content)
        self.assertNotIn(code.encode(), resp.content)
        self.assertIn(b"hsurr:github", resp.content)
        self.assertIn(b"hsurr:acme:password", resp.content)
        self.assertIn(b"hsurr:acme:totp", resp.content)
        # content-length stays honest
        self.assertEqual(resp.headers.get("content-length"),
                         str(len(resp.content)))
        # binary bodies are a stated residual: untouched
        img = FakeResponse(b"\x89PNGghp_TOKEN", "image/png")
        flow = Flow(Request("github.com", "/logo.png"))
        flow.response = img
        a.response(flow)
        self.assertIn(b"ghp_TOKEN", img.content)
        # non-allowlisted hosts: no scrub
        other = FakeResponse(b"ghp_TOKEN", "text/plain")
        flow = Flow(Request("evil.example", "/"))
        flow.response = other
        a.response(flow)
        self.assertIn(b"ghp_TOKEN", other.content)

    def test_bug_refused_swap_warns_and_audits(self):
        """REVIEW item 22: the placeholder warning must fire for
        placeholders hidden inside base64'd Basic auth, and refused
        swaps must reach the audit trail."""
        a = make_addon()
        records = []

        class H(logging.Handler):
            def emit(self, r):
                records.append(r.getMessage())

        h = H()
        sa.log.addHandler(h)
        self.addCleanup(sa.log.removeHandler, h)
        b64 = base64.b64encode(b"x-access-token:hsurr:github").decode()
        req = Request("evil.example", "/",
                      [("Authorization", "Basic " + b64)])
        a.request(Flow(req))
        self.assertTrue(
            any("placeholder" in r and "evil.example" in r for r in records),
            records)
        self.assertEqual(req.headers.get("Authorization"), "Basic " + b64)
        # refused swap (credential not bound to the request host) is
        # recorded even though nothing leaks
        b = make_addon()
        req = Request("github.com", "/x", [("X-T", "hsurr:openai")])
        b.request(Flow(req))
        self.assertEqual(req.headers.get("X-T"), "hsurr:openai")
        self.assertEqual(b.refused, [("github.com", "openai", "unbound-host")])

    def test_bug_single_value_kv_secret_not_split(self):
        """REVIEW items 25, 35: the #hsurr:multi marker is the SOLE source
        of file layout. Registry entries describe placements, never file
        format — a single-value secret that looks like 'k=v' stays a
        single value, and a registry entry never flips it to multi."""
        a = make_addon()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x"
            p.write_text("token=abc=def\n")
            self.assertEqual(a._load_secret_file(p), "token=abc=def")
            p.write_text("#hsurr:multi\nuser=jdoe\npassword=x\n")
            self.assertEqual(a._load_secret_file(p),
                             {"user": "jdoe", "password": "x"})
            # no marker, no entries: single value even with '=' inside
            p.write_text("user=jdoe\npassword=x\n")
            self.assertEqual(a._load_secret_file(p), "user=jdoe\npassword=x")

    def test_bug_register_does_not_break_single_value_secret(self):
        """REVIEW item 35 (regression): `cred register <name> --host <h>`
        writes a default access_token entry. A bare-value file plus such
        a registry must still load as the single value and swap — for the
        bare placeholder and for the lone declared entry."""
        a = make_addon(
            secrets={"acme": "bare-TOKEN-value"},
            hosts=["acme.example.com"],
            registry={"acme": {"allowed_hosts": ["acme.example.com"],
                               "access_token": {"placement": "bearer_header"}}})
        self.assertEqual(a._resolve("acme", None, "acme.example.com",
                                    "GET", "/"), "bare-TOKEN-value")
        self.assertEqual(a._resolve("acme", "access_token",
                                    "acme.example.com", "GET", "/"),
                         "bare-TOKEN-value")
        out = a._swap_text("Authorization: Bearer hsurr:acme",
                           "acme.example.com", "GET", "/")
        self.assertEqual(out, "Authorization: Bearer bare-TOKEN-value")
        # a genuinely different entry still does not match
        self.assertIsNone(a._resolve("acme", "password", "acme.example.com",
                                     "GET", "/"))
        self.assertEqual(a._swap_text("hsurr:acme:password",
                                      "acme.example.com"),
                         "hsurr:acme:password")

    def test_bug_private_range_refused(self):
        """REVIEW items 29, 37, 38: the server_connect hook refuses
        private-range egress BEFORE the upstream TCP connect (no SYN ever
        leaves), and pins the server address to the resolved IP on
        allow, so the check and the connect use the same answer. DNS
        failure fails open."""
        now = time.time()

        def box(ip, **kw):
            a = make_addon(hosts=["box.local"],
                           registry={"box": {"allowed_hosts": ["box.local"]}},
                           secrets={"box": "box-SECRET"})
            a._dns_cache["box.local"] = (now + 3600, [ip])
            for k, v in kw.items():
                setattr(a, k, v)
            return a

        def connect(a, host="box.local"):
            data = FakeServerConnectData(host)
            a.server_connect(data)
            return data

        # refused by default: connection killed, audited, never connected
        a = box("192.168.1.1")
        data = connect(a)
        self.assertEqual(data.server.error,
                         "swap-proxy: egress refused (private-range)")
        self.assertEqual(data.server.address, ("box.local", 443))  # unpinned
        self.assertEqual(a.ssrf_refused,
                         [("box.local", "192.168.1.1", "private-range")])
        # hostname allowlist admits it and pins the resolved IP
        a = box("192.168.1.1", ssrf_hosts=["box.local"])
        data = connect(a)
        self.assertIsNone(data.server.error)
        self.assertEqual(data.server.address, ("192.168.1.1", 443))
        # CIDR allowlist admits it
        a = box("192.168.1.1",
                ssrf_nets=[ipaddress.ip_network("192.168.0.0/16")])
        data = connect(a)
        self.assertIsNone(data.server.error)
        self.assertEqual(data.server.address, ("192.168.1.1", 443))
        # public IPs are unaffected
        a = box("93.184.216.34")
        data = connect(a)
        self.assertIsNone(data.server.error)
        self.assertEqual(data.server.address, ("93.184.216.34", 443))
        # DNS failure fails open (the connect fails on its own upstream)
        a = box("192.168.1.1")
        a._dns_cache["box.local"] = (now + 3600, None)
        data = connect(a)
        self.assertIsNone(data.server.error)

    def test_bug_private_range_literals(self):
        """REVIEW item 37: 0.0.0.0, IPv4-mapped IPv6 localhost, and the
        newly refused ranges are all judged before connecting."""
        now = time.time()
        for literal in ("0.0.0.0", "::ffff:127.0.0.1", "127.0.0.1",
                        "10.9.9.9", "192.0.0.7", "198.18.0.1",
                        "240.0.0.1", "::1"):
            a = make_addon(hosts=["h.example"],
                           registry={"h": {"allowed_hosts": ["h.example"]}},
                           secrets={"h": "h-SECRET"})
            a._dns_cache["h.example"] = (now + 3600, [literal])
            data = FakeServerConnectData("h.example")
            a.server_connect(data)
            self.assertIsNotNone(data.server.error, literal)
        # a public literal still passes
        a = make_addon(hosts=["h.example"],
                       registry={"h": {"allowed_hosts": ["h.example"]}},
                       secrets={"h": "h-SECRET"})
        a._dns_cache["h.example"] = (now + 3600, ["93.184.216.34"])
        data = FakeServerConnectData("h.example")
        a.server_connect(data)
        self.assertIsNone(data.server.error)
        self.assertEqual(data.server.address, ("93.184.216.34", 443))

    def test_bug_inference_mode_header_only(self):
        """REVIEW item 31: the inference proxy swaps headers only — a page
        blob in obox's prompt must never traverse credential insertion."""
        def llm(inference):
            a = make_addon(hosts=["api.llm.example"],
                           registry={"llm": {"allowed_hosts": ["api.llm.example"]}},
                           secrets={"llm": "sk-LLM"})
            a.inference_mode = inference
            return a

        def req():
            return Request("api.llm.example", "/v1/chat?k=hsurr:llm",
                           [("Authorization", "Bearer hsurr:llm")],
                           b'{"model":"x","key":"hsurr:llm"}')

        a = llm(True)
        r = req()
        a.request(Flow(r))
        self.assertEqual(r.headers.get("Authorization"), "Bearer sk-LLM")
        self.assertIn(b"hsurr:llm", r.content)          # body untouched
        self.assertIn("hsurr:llm", r.path)              # path/query untouched
        flow = Flow(req())
        flow.websocket = FakeWebSocket([FakeWSMessage(b"key=hsurr:llm")])
        a.websocket_message(flow)
        self.assertEqual(flow.websocket.messages[0].content, b"key=hsurr:llm")

        b = llm(False)
        r = req()
        b.request(Flow(r))
        self.assertNotIn(b"hsurr:llm", r.content)       # normal mode swaps
        flow = Flow(req())
        flow.websocket = FakeWebSocket([FakeWSMessage(b"key=hsurr:llm")])
        b.websocket_message(flow)
        self.assertEqual(flow.websocket.messages[0].content, b"key=sk-LLM")

    # --- review round 3 (findings 35-40) --------------------------------

    def test_bug_scrub_minimum_length(self):
        """REVIEW item 36: values under 8 chars are never scrubbed — a
        one-character password must not rewrite 'Next' into
        'Nehsurr:acme:passwordt'."""
        a = make_addon(
            secrets={"acme": {"password": "e",
                              "username": "averylongusername1"}},
            hosts=["acme.example.com"],
            registry={"acme": {"allowed_hosts": ["acme.example.com"]}})
        resp = FakeResponse(b"<p>Next, averylongusername1</p>", "text/html")
        flow = Flow(Request("acme.example.com", "/"))
        flow.response = resp
        a.response(flow)
        self.assertIn(b"Next,", resp.content)
        self.assertNotIn(b"averylongusername1", resp.content)
        self.assertIn(b"hsurr:acme:username", resp.content)

    def test_bug_scrub_short_value_warns_at_load(self):
        """REVIEW item 36: loading a secret with a sub-8-char value warns,
        naming the credential but never the value."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "acme").write_text("x")
            with mock.patch.object(sa, "SECRETS_DIR", Path(d)), \
                 mock.patch.object(sa, "HOSTS_FILE", Path(d) / "h"), \
                 mock.patch.object(sa, "REGISTRY_FILE", Path(d) / "r"), \
                 mock.patch.object(sa, "SSRF_ALLOW_FILE", Path(d) / "s"), \
                 mock.patch.object(sa, "LOG_FILE", Path(d) / "l"):
                with self.assertLogs(sa.log, level="WARNING") as cm:
                    sa.SwapAddon()
        msgs = "\n".join(cm.output)
        self.assertIn("acme", msgs)
        self.assertIn("shorter than 8 chars", msgs)
        self.assertNotIn("secret value 'x'", msgs)

    def test_bug_scrub_opt_out_and_totp_whole_token(self):
        """REVIEW item 36: an entry with scrub:false (usernames, emails)
        is never scrubbed; TOTP codes match as whole tokens only, so a
        six-digit code collides with neither prices nor IDs."""
        reg = {"acme": {"allowed_hosts": ["acme.example.com"],
                        "username": {"scrub": False}}}
        a = make_addon(
            secrets={"acme": {"username": "averylongusername1",
                              "totp": "JBSWY3DPEHPK3PXP"}},
            hosts=["acme.example.com"], registry=reg)
        code = sa._totp_code("JBSWY3DPEHPK3PXP").encode()
        body = (b"welcome averylongusername1, price 1" + code + b"2, "
                b"code " + code + b" ok")
        resp = FakeResponse(body, "text/html")
        flow = Flow(Request("acme.example.com", "/"))
        flow.response = resp
        a.response(flow)
        self.assertIn(b"averylongusername1", resp.content)   # opted out
        self.assertIn(b"1" + code + b"2", resp.content)      # not a token
        self.assertNotIn(b"code " + code + b" ok", resp.content)
        self.assertIn(b"hsurr:acme:totp", resp.content)

    def test_bug_inference_install_steps_swap(self):
        """REVIEW item 39: after the documented install steps — store the
        key, write the registry through cred-registry-set-inference,
        bind the host — the inference instance swaps headers only."""
        here = os.path.dirname(os.path.abspath(__file__))
        wrapper = os.path.join(here, "cred-registry-set-inference")
        tool = os.path.join(here, "cred-registry-set")
        with tempfile.TemporaryDirectory() as d:
            reg = os.path.join(d, "inference-registry.json")
            env = dict(os.environ, CRED_REGISTRY_FILE=reg,
                       CRED_REGISTRY_SET=tool)
            (Path(d) / "llm-api").write_text("sk-LLM-KEY")
            for argv in (["set", "llm-api", "access_token",
                          '"bearer_header"'],
                         ["add-host", "llm-api", "api.llm.example"]):
                r = subprocess.run([wrapper] + argv, capture_output=True,
                                   env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
            (Path(d) / "hosts.allow").write_text("api.llm.example\n")
            (Path(d) / "ssrf.allow").write_text("")
            with mock.patch.object(sa, "SECRETS_DIR", Path(d)), \
                 mock.patch.object(sa, "HOSTS_FILE",
                                   Path(d) / "hosts.allow"), \
                 mock.patch.object(sa, "REGISTRY_FILE", Path(reg)), \
                 mock.patch.object(sa, "SSRF_ALLOW_FILE",
                                   Path(d) / "ssrf.allow"), \
                 mock.patch.object(sa, "LOG_FILE", Path(d) / "swap.log"):
                a = sa.SwapAddon()
                a.inference_mode = True
                a._dns_cache["api.llm.example"] = (time.time() + 3600,
                                                   ["93.184.216.34"])
                req = Request("api.llm.example", "/v1/chat",
                              [("Authorization", "Bearer hsurr:llm-api")],
                              b'{"key":"hsurr:llm-api"}')
                a.request(Flow(req))
            self.assertEqual(req.headers.get("Authorization"),
                             "Bearer sk-LLM-KEY")
            self.assertIn(b"hsurr:llm-api", req.content)  # body untouched

    def test_nit_nonallowlisted_placeholder_audits_refused(self):
        """REVIEW item 40a: a placeholder seen for a non-allowlisted host
        is a refused= audit line, not just a journal warning."""
        a = make_addon()
        b64 = base64.b64encode(b"x-access-token:hsurr:github").decode()
        req = Request("evil.example", "/",
                      [("Authorization", "Basic " + b64)])
        a.request(Flow(req))
        self.assertIn(("evil.example", "github", "host-not-allowlisted"),
                      a.refused)

    def test_nit_multi_entry_bad_line_warns(self):
        """REVIEW item 40b: a non-k=v line in a multi file is dropped with
        a warning naming the line number, never the content."""
        a = make_addon()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x"
            p.write_text("#hsurr:multi\nuser=jdoe\nnot a pair\npw=x\n")
            with self.assertLogs(sa.log, level="WARNING") as cm:
                vals = a._load_secret_file(p)
        self.assertEqual(vals, {"user": "jdoe", "pw": "x"})
        msgs = "\n".join(cm.output)
        self.assertIn("line 3", msgs)
        self.assertNotIn("not a pair", msgs)

    def test_nit_oversized_body_skipped_before_decode(self):
        """REVIEW item 40c: the scrub size cap is checked on the raw bytes
        before decoding — an undecodable oversized body must not even be
        attempted."""
        class ExplodingResponse(FakeResponse):
            @property
            def text(self):
                raise AssertionError("decoded an oversized body")

        a = make_addon()
        big = b"\xff" * (sa.SwapAddon._MAX_SCRUB_BYTES + 1)
        resp = ExplodingResponse(big, "text/plain")
        flow = Flow(Request("github.com", "/big"))
        flow.response = resp
        a.response(flow)  # must not raise
        self.assertEqual(resp.content, big)

    # --- grant scoping (approved half) --------------------------------

    def _grant_addon(self, **over):
        reg = {"api": {"allowed_hosts": ["api.example.com"],
                       "allowed_methods": ["post"],
                       "allowed_paths": ["/repos/"]}}
        kw = dict(hosts=["api.example.com"], secrets={"api": "API-TOKEN"},
                  registry=reg)
        kw.update(over)
        return make_addon(**kw)

    def _grant_req(self, path, method="POST"):
        return Request("api.example.com", path, method=method,
                       headers=[("Authorization", "Bearer hsurr:api")])

    def test_grant_method_limit(self):
        """allowed_methods is checked before swapping; the stored method
        is uppercased and the request method compared case-insensitively.
        Absent limits mean unrestricted (migration)."""
        a = self._grant_addon()
        req = self._grant_req("/repos/x", method="GET")
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"), "Bearer hsurr:api")
        self.assertIn(("api.example.com", "api", "method-not-allowed"),
                      a.refused)
        # no limits at all: swaps freely
        b = make_addon()
        req = Request("github.com", "/anything", method="DELETE",
                      headers=[("Authorization", "Bearer hsurr:github")])
        b.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"), "Bearer ghp_TOKEN")

    def test_grant_path_prefix(self):
        """allowed_paths: segment-aligned prefix match on the
        percent-decoded, dot-segment-normalized path; the query string
        is ignored."""
        a = self._grant_addon()
        req = self._grant_req("/repos/x?page=2")
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"), "Bearer API-TOKEN")

        for bad in ("/admin", "/repository", "/repos/../admin",
                    "/repos/%2e%2e/admin"):
            b = self._grant_addon()
            req = self._grant_req(bad)
            b.request(Flow(req))
            self.assertEqual(req.headers.get("Authorization"),
                             "Bearer hsurr:api", bad)
            self.assertIn(("api.example.com", "api", "path-not-allowed"),
                          b.refused)

    def test_grant_normalize_path(self):
        self.assertEqual(sa._normalize_path("/repos/%2e%2e/admin"), "/admin")
        self.assertEqual(sa._normalize_path("/repos//x"), "/repos/x")
        self.assertEqual(sa._normalize_path("/repos/x?y=1"), "/repos/x")
        self.assertTrue(sa._path_allowed("/repos/x", ["/repos/"]))
        self.assertTrue(sa._path_allowed("/repos", ["/repos/"]))
        self.assertFalse(sa._path_allowed("/repository", ["/repos/"]))

    def test_nit_path_unchanged_segments_byte_identical(self):
        """REVIEW nit 34a: re-quoting must not mangle : ~ or escapes in
        segments that had no placeholder."""
        a = make_addon()
        req = Request("github.com", "/repos/a~b/c:d/hsurr:github/e%2Ff")
        a.request(Flow(req))
        self.assertEqual(req.path, "/repos/a~b/c:d/ghp_TOKEN/e%2Ff")

    def test_nit_registry_set_rejects_reserved_entry_names(self):
        """REVIEW nit 34b: an entry named 'allowed_hosts' would clobber
        the host binding with a placement object — reject it (and the
        grant-scoping reservations)."""
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "cred-registry-set")
        with tempfile.TemporaryDirectory() as d:
            reg = os.path.join(d, "credentials.json")
            env = dict(os.environ, CRED_REGISTRY_FILE=reg)
            # a normal entry works and lands in the registry file
            r = subprocess.run(
                [script, "set", "acme", "username", '"bearer_header"'],
                capture_output=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            saved = json.loads(Path(reg).read_text())
            self.assertEqual(saved["acme"]["username"]["placement"],
                             "bearer_header")
            self.assertNotIn("allowed_hosts", saved["acme"])
            # reserved names are rejected on both set and remove
            for entry in ("allowed_hosts", "allowed_methods", "allowed_paths"):
                r = subprocess.run(
                    [script, "set", "acme", entry, '"bearer_header"'],
                    capture_output=True, env=env)
                self.assertNotEqual(r.returncode, 0, entry)
                self.assertIn(b"reserved", r.stderr)
            r = subprocess.run([script, "remove", "acme", "allowed_hosts"],
                               capture_output=True, env=env)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(b"reserved", r.stderr)
            saved = json.loads(Path(reg).read_text())
            self.assertNotIn("allowed_hosts", saved["acme"])


if __name__ == "__main__":
    unittest.main()
