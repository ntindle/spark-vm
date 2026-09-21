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
import asyncio
import errno
import fnmatch
import hashlib
import hmac
import ipaddress
import json
import os
import re
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
        self.host = host  # URI authority; the proxy routes on this
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
        self.server_conn = None  # set by mitmproxy once connected


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
    a.deny_hosts = []
    a.deny_nets = []
    # Hermetic DNS: test hosts resolve to None without a real lookup.
    # server_connect now fails closed on None (dns-resolution-failed);
    # tests that exercise the SSRF guard seed _dns_cache themselves.
    a._dns_cache = {h: (time.time() + 3600, None)
                    for h in list(hosts) + ["evil.example"]}
    a._store_mtime = a._hosts_mtime = None
    a._maybe_reload = lambda: None      # never touch /home/swapd here
    # audit writes are durably recorded; the addon fails closed when
    # they are not (tested separately)
    a._audit = lambda host, matched: True
    a._current_egress_ip = None
    a.refused = []
    a._audit_refused = lambda host, name, reason: a.refused.append(
        (host, name, reason))
    a.audit_notes = []
    a._audit_note = lambda host, refused, reason: a.audit_notes.append(
        (host, refused, reason))
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

    def test_version_stamp_resolves_repo_version(self):
        # docs/VERSIONING.md: the addon reports the single-source VERSION;
        # never "0.0.0-unknown" when the repo checkout is intact.
        repo = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(sa.__file__)), ".."))
        with open(os.path.join(repo, "VERSION")) as f:
            self.assertEqual(sa.SPARKVM_VERSION, f.read().strip())

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
            p.write_text("token=abc=def")
            self.assertEqual(a._load_secret_file(p), "token=abc=def")
            p.write_text("#hsurr:multi\nuser=jdoe\npassword=x\n")
            self.assertEqual(a._load_secret_file(p),
                             {"user": "jdoe", "password": "x"})
            # no marker, no entries: single value even with '=' inside
            p.write_text("user=jdoe\npassword=x")
            self.assertEqual(a._load_secret_file(p), "user=jdoe\npassword=x")

    def test_issue88_single_value_read_is_verbatim(self):
        """#88: the read path must return the stored bytes exactly. Every
        supported store path chomps one trailing newline at write time, so
        whatever is in the file IS the intended value — a read-side strip()
        corrupts secrets that legitimately start or end with whitespace."""
        a = make_addon()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x"
            # legitimately trailing newlines survive the read
            p.write_text("tok\n\n")
            self.assertEqual(a._load_secret_file(p), "tok\n\n")
            # legitimately leading/trailing spaces survive the read
            p.write_text(" tok ")
            self.assertEqual(a._load_secret_file(p), " tok ")

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
        failure fails closed: the connection is killed rather than left
        to re-resolve unpinned."""
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
            asyncio.run(a.server_connect(data))
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
        # DNS failure fails closed: the connection is killed rather
        # than left to re-resolve unpinned, and the refusal is audited
        a = box("192.168.1.1")
        a._dns_cache["box.local"] = (now + 3600, None)
        data = connect(a)
        self.assertEqual(data.server.error,
                         "swap-proxy: egress refused "
                         "(dns-resolution-failed)")
        self.assertEqual(data.server.address, ("box.local", 443))
        self.assertIn(("box.local", "-", "dns-resolution-failed"),
                      a.ssrf_refused)

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
            asyncio.run(a.server_connect(data))
            self.assertIsNotNone(data.server.error, literal)
        # a public literal still passes
        a = make_addon(hosts=["h.example"],
                       registry={"h": {"allowed_hosts": ["h.example"]}},
                       secrets={"h": "h-SECRET"})
        a._dns_cache["h.example"] = (now + 3600, ["93.184.216.34"])
        data = FakeServerConnectData("h.example")
        asyncio.run(a.server_connect(data))
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

    def test_issue91_secrets_dir_0700_no_warning(self):
        """Issue #91: a 0700 secrets dir is the documented state — no
        group/other-readable warning at load."""
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o700)
            with mock.patch.object(sa, "SECRETS_DIR", Path(d)):
                with self.assertNoLogs(sa.log, level="WARNING"):
                    sa.SwapAddon._check_secrets_dir_mode()

    def test_issue91_secrets_dir_0755_warns(self):
        """Issue #91: a 0755 secrets dir warns loudly, naming the dir and
        mode, never a secret value."""
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o755)
            (Path(d) / "acme").write_text("very-secret-value")
            with mock.patch.object(sa, "SECRETS_DIR", Path(d)):
                with self.assertLogs(sa.log, level="WARNING") as cm:
                    sa.SwapAddon._check_secrets_dir_mode()
        msgs = "\n".join(cm.output)
        self.assertIn("group/other-readable", msgs)
        self.assertIn("0755", msgs)
        self.assertIn(str(d), msgs)
        self.assertNotIn("very-secret-value", msgs)

    def test_issue91_secrets_dir_missing_is_silent(self):
        """Issue #91: a missing secrets dir does not emit a mode warning
        (first boot before the narrow writers run)."""
        with tempfile.TemporaryDirectory() as d:
            missing = Path(d) / "no-such-dir"
            with mock.patch.object(sa, "SECRETS_DIR", missing):
                with self.assertNoLogs(sa.log, level="WARNING"):
                    sa.SwapAddon._check_secrets_dir_mode()

    def test_issue91_secrets_dir_non_dir_is_silent(self):
        """Issue #91: a non-directory secrets path emits no mode warning
        (the listing path already warns on its own)."""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "not-a-dir"
            f.write_text("x")
            with mock.patch.object(sa, "SECRETS_DIR", f):
                with self.assertNoLogs(sa.log, level="WARNING"):
                    sa.SwapAddon._check_secrets_dir_mode()

    def test_issue91_secrets_dir_0770_warns(self):
        """Issue #91: group bits alone also warn (0o077 mask, not just
        the other bits)."""
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o770)
            with mock.patch.object(sa, "SECRETS_DIR", Path(d)):
                with self.assertLogs(sa.log, level="WARNING") as cm:
                    sa.SwapAddon._check_secrets_dir_mode()
        self.assertIn("0770", "\n".join(cm.output))

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
            for entry in ("allowed_hosts", "allowed_methods", "allowed_paths",
                          "grants"):
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

    # --- review round 4 (findings 41-46) --------------------------------

    def test_grant_empty_lists_fail_closed(self):
        """REVIEW item 41: an explicit empty allowed_methods or
        allowed_paths fails closed — removing the last method must not
        silently unlimit the credential."""
        for key, reason in (("allowed_methods", "method-not-allowed"),
                            ("allowed_paths", "path-not-allowed")):
            reg = {"api": {"allowed_hosts": ["api.example.com"], key: []}}
            a = make_addon(hosts=["api.example.com"],
                           secrets={"api": "API-TOKEN"}, registry=reg)
            req = Request("api.example.com", "/repos/x", method="POST",
                          headers=[("Authorization", "Bearer hsurr:api")])
            a.request(Flow(req))
            self.assertEqual(req.headers.get("Authorization"),
                             "Bearer hsurr:api", key)
            self.assertIn(("api.example.com", "api", reason), a.refused)

    def test_registry_set_remove_last_is_deny_all(self):
        """remove-method/remove-path of the last entry keeps [] (deny-all);
        use clear-method-limit/clear-path-limit to go back to unrestricted."""
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "cred-registry-set")

        def run(env, *argv):
            r = subprocess.run([script] + list(argv), capture_output=True,
                               env=env, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r

        with tempfile.TemporaryDirectory() as d:
            reg = os.path.join(d, "credentials.json")
            env = dict(os.environ, CRED_REGISTRY_FILE=reg)
            run(env, "add-method", "api", "POST")
            r = run(env, "remove-method", "api", "POST")
            self.assertIn("deny-all", r.stdout)
            saved = json.loads(Path(reg).read_text())
            self.assertEqual(saved["api"]["allowed_methods"], [])
            r = run(env, "clear-method-limit", "api")
            self.assertIn("unrestricted", r.stdout)
            saved = json.loads(Path(reg).read_text())
            self.assertNotIn("allowed_methods", saved["api"])
            run(env, "add-path", "api", "/repos/")
            r = run(env, "remove-path", "api", "/repos/")
            self.assertIn("deny-all", r.stdout)
            saved = json.loads(Path(reg).read_text())
            self.assertEqual(saved["api"]["allowed_paths"], [])
            r = run(env, "clear-path-limit", "api")
            self.assertIn("unrestricted", r.stdout)
            saved = json.loads(Path(reg).read_text())
            self.assertNotIn("allowed_paths", saved["api"])
            # partial removal keeps the key and the remaining entries
            run(env, "add-method", "api", "GET")
            run(env, "add-method", "api", "POST")
            r = run(env, "remove-method", "api", "POST")
            self.assertNotIn("deny-all", r.stdout)
            saved = json.loads(Path(reg).read_text())
            self.assertEqual(saved["api"]["allowed_methods"], ["GET"])

    def test_grant_path_smuggling_shapes_refused(self):
        """REVIEW item 42: double-encoding, path parameters, and
        backslashes must not slip a path-bound credential past its
        prefix — unquote to a fixpoint, then refuse %, ; and \\."""
        for bad in ("/repos/%252e%252e/admin", "/repos/..;/admin",
                    "/repos/..\\admin"):
            a = self._grant_addon()
            req = self._grant_req(bad)
            a.request(Flow(req))
            self.assertEqual(req.headers.get("Authorization"),
                             "Bearer hsurr:api", bad)
            self.assertIn(("api.example.com", "api", "path-not-allowed"),
                          a.refused)
        self.assertEqual(sa._normalize_path("/repos/%252e%252e/admin"),
                         "/admin")
        self.assertEqual(sa._normalize_path("/repos/%2e%2e/admin"), "/admin")
        # a clean path still swaps
        b = self._grant_addon()
        req = self._grant_req("/repos/x")
        b.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"), "Bearer API-TOKEN")

    def test_bug_scrub_opt_out_single_value_secret(self):
        """REVIEW item 43: set-scrub consults the access_token entry spec
        for single-value secrets — there is no entry None."""
        reg = {"web": {"allowed_hosts": ["web.example.com"],
                       "access_token": {"scrub": False}}}
        a = make_addon(secrets={"web": "averylongsinglevaluetoken"},
                       hosts=["web.example.com"], registry=reg)
        resp = FakeResponse(b"welcome averylongsinglevaluetoken bye",
                            "text/html")
        flow = Flow(Request("web.example.com", "/"))
        flow.response = resp
        a.response(flow)
        self.assertIn(b"averylongsinglevaluetoken", resp.content)
        # and the helper writes exactly that shape
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "cred-registry-set")
        with tempfile.TemporaryDirectory() as d:
            regfile = os.path.join(d, "credentials.json")
            env = dict(os.environ, CRED_REGISTRY_FILE=regfile)
            r = subprocess.run(
                [script, "set-scrub", "web", "access_token", "false"],
                capture_output=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            saved = json.loads(Path(regfile).read_text())
            self.assertIs(saved["web"]["access_token"]["scrub"], False)

    def test_bug_grants_key_reserved(self):
        """REVIEW item 44: 'grants' is structural — hsurr:api:grants must
        not resolve to the token, and the helper rejects it as an entry
        name."""
        reg = {"api": {"allowed_hosts": ["api.example.com"],
                       "grants": [{"scope": "session"}]}}
        a = make_addon(hosts=["api.example.com"],
                       secrets={"api": "API-TOKEN"}, registry=reg)
        self.assertIsNone(a._resolve("api", "grants", "api.example.com",
                                     "GET", "/"))
        out = a._swap_text("Bearer hsurr:api:grants", "api.example.com",
                           "GET", "/")
        self.assertIn("hsurr:api:grants", out)
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "cred-registry-set")
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ,
                       CRED_REGISTRY_FILE=os.path.join(d, "credentials.json"))
            r = subprocess.run([script, "set", "api", "grants",
                                '"bearer_header"'],
                               capture_output=True, env=env)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(b"reserved", r.stderr)

    def test_bug_server_connect_is_async(self):
        """REVIEW item 45: server_connect is a coroutine hook — DNS goes
        through the loop's resolver instead of blocking getaddrinfo on
        mitmproxy's event loop. A failing resolver fails closed."""
        self.assertTrue(
            asyncio.iscoroutinefunction(sa.SwapAddon.server_connect))
        self.assertTrue(
            asyncio.iscoroutinefunction(sa.SwapAddon._resolve_ips))
        a = make_addon(hosts=["nope.invalid"],
                       registry={"n": {"allowed_hosts": ["nope.invalid"]}},
                       secrets={"n": "n-SECRET"})
        a._dns_cache.pop("nope.invalid", None)  # force a real lookup

        async def drive():
            loop = asyncio.get_running_loop()

            async def boom(*args, **kwargs):
                raise socket.gaierror("mocked resolver failure")

            with mock.patch.object(loop, "getaddrinfo", boom):
                data = FakeServerConnectData("nope.invalid")
                await a.server_connect(data)
                return data

        data = asyncio.run(drive())
        self.assertEqual(data.server.error,
                         "swap-proxy: egress refused "
                         "(dns-resolution-failed)")

    def test_bug_inference_store_piped_stdin(self):
        """REVIEW item 46: cred-store-set-inference takes the key on stdin
        (piped, never an echoing prompt), into the fixed name, 0600."""
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "cred-store-set-inference")
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, INFERENCE_SECRETS_DIR=d)
            r = subprocess.run([script], input=b"LLM-test-key-bytes",
                               capture_output=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            p = Path(d) / "llm-api"
            self.assertEqual(p.read_bytes(), b"LLM-test-key-bytes")
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_issue88_inference_writer_chomps_one_trailing_newline(self):
        """#88 (arch B1): cred-store-set-inference is its own frontend —
        nothing chomps before it — so it chomps exactly one trailing
        newline at the store boundary. Readers return stored bytes
        verbatim, so without this an incidental newline (echo idiom)
        would be injected into the provider Authorization header."""
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "cred-store-set-inference")
        cases = [
            (b"LLM-key\n", b"LLM-key"),      # echo idiom: chomped
            (b"LLM-key\r\n", b"LLM-key"),    # CRLF idiom: chomped
            (b"LLM-key\n\n", b"LLM-key\n"),  # only one: legit newline kept
            (b"LLM-key", b"LLM-key"),        # printf idiom: untouched
        ]
        with tempfile.TemporaryDirectory() as d:
            for stdin_bytes, expected in cases:
                env = dict(os.environ, INFERENCE_SECRETS_DIR=d)
                r = subprocess.run([script], input=stdin_bytes,
                                   capture_output=True, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual((Path(d) / "llm-api").read_bytes(),
                                 expected, stdin_bytes)

    def test_issue88_inference_writer_refuses_newline_only_input(self):
        """#88: a single newline chomps to empty — refused like any empty
        secret, never stored as a zero-byte key."""
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "cred-store-set-inference")
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, INFERENCE_SECRETS_DIR=d)
            r = subprocess.run([script], input=b"\n",
                               capture_output=True, env=env)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse((Path(d) / "llm-api").exists())

    def test_issue88_inference_writer_chomp_never_masks_truncation(self):
        """#88 (QA round 2): the capture cap is max_bytes+2 and a capture
        that hit the cap is refused BEFORE the chomp — otherwise a chomp
        could mask a truncated oversized input into a silently-truncated
        store. A legit 64KiB key plus one echo newline still stores."""
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "cred-store-set-inference")
        with tempfile.TemporaryDirectory() as d:
            # 64KiB key + one echo newline: accepted, chomped to 64KiB
            env = dict(os.environ, INFERENCE_SECRETS_DIR=d)
            r = subprocess.run([script], input=b"A" * 65536 + b"\n",
                               capture_output=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((Path(d) / "llm-api").read_bytes(),
                             b"A" * 65536)
            # 64KiB+1 without a trailing newline: refused (over the max)
            r = subprocess.run([script], input=b"A" * 65537,
                               capture_output=True, env=env)
            self.assertNotEqual(r.returncode, 0)
            # oversized input whose 65537th captured byte is a newline:
            # refused, never silently truncated-and-stored
            r = subprocess.run(
                [script], input=b"A" * 65536 + b"\n" + b"B" * 1000,
                capture_output=True, env=env)
            self.assertNotEqual(r.returncode, 0)

    def test_issue88_scrub_covers_bare_and_verbatim_renderings(self):
        """#88 (arch B2): a whitespace-significant single value must scrub
        both the verbatim stored rendering AND the bare rendering servers
        echo back trimmed — otherwise the trimmed echo leaks past the
        scrubber while the swap itself works."""
        a = make_addon(secrets={"k": "secrettok12\n"})
        text = ("verbatim: [secrettok12\n] bare: 'secrettok12' "
                "other: secrettok1")
        scrubbed = a._scrub_text_value(text)
        self.assertNotIn("secrettok12\n", scrubbed)
        self.assertNotIn("'secrettok12'", scrubbed)
        self.assertIn("hsurr:k", scrubbed)
        # no over-scrub: a shorter innocent token is untouched
        self.assertIn("secrettok1", scrubbed)

    def test_nit_inference_recipe_names_right_files(self):
        """REVIEW item 46: the install recipe must bind the provider in
        inference-hosts.allow (never the main hosts.allow) and run the
        store step as swapd with piped, non-echoing input."""
        here = os.path.dirname(os.path.abspath(__file__))
        setup = Path(here, "..", "SETUP.md").resolve().read_text()
        recipe = setup.split("### Inference-model recipe")[1]
        recipe = recipe.split("\n### ")[0]
        self.assertIn("inference-hosts.allow", recipe)
        self.assertIn("sudo -u swapd", recipe)
        self.assertIn("read -rsp", recipe)  # no-echo prompt, piped in
        self.assertNotIn("/home/swapd/hosts.allow", recipe)

    def test_nit_scrub_false_skips_short_value_warning(self):
        """Round-4 nit: the sub-8-char load warning skips entries opted
        out with scrub:false — the warning is about scrubbing, which is
        already off for them."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "acme").write_text("x")
            (Path(d) / "r").write_text(
                json.dumps({"acme": {"access_token": {"scrub": False}}}))
            records = []
            handler = logging.Handler()
            handler.emit = records.append
            sa.log.addHandler(handler)
            try:
                with mock.patch.object(sa, "SECRETS_DIR", Path(d)), \
                     mock.patch.object(sa, "HOSTS_FILE", Path(d) / "h"), \
                     mock.patch.object(sa, "REGISTRY_FILE", Path(d) / "r"), \
                     mock.patch.object(sa, "SSRF_ALLOW_FILE",
                                        Path(d) / "s"), \
                     mock.patch.object(sa, "LOG_FILE", Path(d) / "l"):
                    sa.SwapAddon()
            finally:
                sa.log.removeHandler(handler)
        self.assertNotIn("shorter than 8 chars",
                         "\n".join(r.getMessage() for r in records))


class AuthorityAndPlacementTests(unittest.TestCase):
    """2026-09-17 review round: CONNECT authority mismatch, registry
    placement enforcement, audit-as-authorization."""

    def _connect_flow(self, authority_host, pretty_host, headers,
                      secrets={"github": "ghp_TOKEN"},
                      registry={"github": {"allowed_hosts": [
                          "evil.example", "api.github.com"]}}):
        """A CONNECT-tunnel flow: the egress connection was pinned to
        authority_host, the inner request claims pretty_host."""
        a = make_addon(secrets=secrets,
                       hosts=["evil.example", "api.github.com"],
                       registry=registry)
        conn = FakeServerConn(authority_host)
        conn.swap_authority_host = sa._norm_authority(authority_host)
        conn.swap_egress_ip = "6.6.6.6"
        req = Request(pretty_host, "/", headers)
        req.host = authority_host  # the proxy routes on the URI authority
        flow = Flow(req)
        flow.server_conn = conn
        a.mismatch = []
        a._audit_authority_mismatch = \
            lambda h, auth, ip: a.mismatch.append((h, auth, ip))
        return a, flow

    def test_authority_mismatch_refuses_swaps(self):
        """CONNECT to evil.example with an inner Host: api.github.com:
        the Host header is spoofed, so NO swap may happen — and the
        attempt is audited with the pinned egress IP."""
        a, flow = self._connect_flow(
            "evil.example", "api.github.com",
            [("Authorization", "Bearer hsurr:github")])
        a.request(flow)
        self.assertEqual(flow.request.headers.get("Authorization"),
                         "Bearer hsurr:github")
        self.assertEqual(a.mismatch,
                         [("api.github.com", "evil.example", "6.6.6.6")])

    def test_authority_match_allows_swaps(self):
        """The pinned egress authority matches the claimed host: swaps
        proceed and the egress IP is recorded for the audit."""
        a, flow = self._connect_flow(
            "api.github.com", "api.github.com",
            [("Authorization", "Bearer hsurr:github")])
        a.request(flow)
        self.assertEqual(flow.request.headers.get("Authorization"),
                         "Bearer ghp_TOKEN")
        self.assertEqual(a._current_egress_ip, "6.6.6.6")
        self.assertEqual(a.mismatch, [])

    def test_authority_fallback_uses_request_host(self):
        """No server connection yet (fresh direct flow): the request's
        own URI authority is the egress authority."""
        a = make_addon()
        req = Request("api.github.com", "/",
                      [("Authorization", "Bearer hsurr:github")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"),
                         "Bearer ghp_TOKEN")

    def test_placement_bearer_header_rejects_query(self):
        """A bearer_header placement must not swap in the query string."""
        registry = {"github": {"allowed_hosts": ["api.github.com"],
                           "access_token": {"placement": "bearer_header"}}}
        a = make_addon(registry=registry)
        req = Request("api.github.com", "/?token=hsurr:github")
        a.request(Flow(req))
        self.assertEqual(req.path, "/?token=hsurr:github")
        self.assertIn(("api.github.com", "github", "placement-mismatch"),
                      a.refused)

    def test_placement_bearer_header_allows_bearer(self):
        registry = {"github": {"allowed_hosts": ["api.github.com"],
                           "access_token": {"placement": "bearer_header"}}}
        a = make_addon(registry=registry)
        req = Request("api.github.com", "/",
                      [("Authorization", "Bearer hsurr:github")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"),
                         "Bearer ghp_TOKEN")

    def test_placement_bearer_header_rejects_basic(self):
        """Bearer placement must not swap inside a Basic auth value."""
        registry = {"github": {"allowed_hosts": ["api.github.com"],
                           "access_token": {"placement": "bearer_header"}}}
        a = make_addon(registry=registry)
        basic = "Basic " + base64.b64encode(b"user:hsurr:github").decode()
        req = Request("api.github.com", "/",
                      [("Authorization", basic)])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"), basic)
        self.assertIn(("api.github.com", "github", "placement-mismatch"),
                      a.refused)

    def test_placement_query_param_rejects_header(self):
        """A query_param placement must not swap in a header."""
        registry = {"github": {"allowed_hosts": ["api.github.com"],
                           "access_token":
                               {"placement": {"query_param": "token"}}}}
        a = make_addon(registry=registry)
        req = Request("api.github.com", "/",
                      [("X-Token", "hsurr:github")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("X-Token"), "hsurr:github")
        self.assertIn(("api.github.com", "github", "placement-mismatch"),
                      a.refused)

    def test_placement_query_param_allows_query(self):
        registry = {"github": {"allowed_hosts": ["api.github.com"],
                           "access_token":
                               {"placement": {"query_param": "token"}}}}
        a = make_addon(registry=registry)
        req = Request("api.github.com", "/?token=hsurr:github")
        a.request(Flow(req))
        self.assertEqual(req.path, "/?token=ghp_TOKEN")

    def test_placement_unknown_string_fails_closed(self):
        """A typo'd placement string must degrade to no swap, never to
        swap-anywhere (issue #197)."""
        registry = {"github": {"allowed_hosts": ["api.github.com"],
                           "access_token": {"placement": "bearer-header"}}}
        a = make_addon(registry=registry)
        req = Request("api.github.com", "/",
                      [("Authorization", "Bearer hsurr:github")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"),
                         "Bearer hsurr:github")
        self.assertIn(("api.github.com", "github", "placement-mismatch"),
                      a.refused)

    def test_placement_unknown_kind_fails_closed(self):
        """A typo'd placement kind must degrade to no swap (#197)."""
        registry = {"github": {"allowed_hosts": ["api.github.com"],
                           "access_token":
                               {"placement": {"qurey_param": "token"}}}}
        a = make_addon(registry=registry)
        req = Request("api.github.com", "/?token=hsurr:github")
        a.request(Flow(req))
        self.assertEqual(req.path, "/?token=hsurr:github")
        self.assertIn(("api.github.com", "github", "placement-mismatch"),
                      a.refused)

    def test_placement_malformed_shape_fails_closed(self):
        """A multi-key placement dict is malformed: fail closed (#197)."""
        registry = {"github": {"allowed_hosts": ["api.github.com"],
                           "access_token":
                               {"placement": {"query_param": "token",
                                              "custom_header": "X-T"}}}}
        a = make_addon(registry=registry)
        req = Request("api.github.com", "/?token=hsurr:github")
        a.request(Flow(req))
        self.assertEqual(req.path, "/?token=hsurr:github")
        self.assertIn(("api.github.com", "github", "placement-mismatch"),
                      a.refused)

    def test_placement_absent_still_swaps_anywhere(self):
        """No declared placement keeps the migration behavior: swaps
        anywhere (#197 must not regress it)."""
        registry = {"github": {"allowed_hosts": ["api.github.com"]}}
        a = make_addon(registry=registry)
        req = Request("api.github.com", "/",
                      [("Authorization", "Bearer hsurr:github")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"),
                         "Bearer ghp_TOKEN")
        self.assertNotIn(("api.github.com", "github", "placement-mismatch"),
                         a.refused)

    def test_pinning_failure_fails_closed(self):
        """If the pin cannot be applied to the server connection, the
        connection is killed rather than left unpinned."""
        class NoPin:
            def __init__(self):
                self.error = None

            @property
            def address(self):
                return ("box.local", 443)

            @address.setter
            def address(self, value):
                raise RuntimeError("mitmproxy refused reassignment")

        a = make_addon(hosts=["box.local"],
                       registry={"box": {"allowed_hosts": ["box.local"]}},
                       secrets={"box": "box-SECRET"})
        a._dns_cache["box.local"] = (time.time() + 3600, ["93.184.216.34"])
        data = FakeServerConnectData("box.local")
        data.server = NoPin()
        asyncio.run(a.server_connect(data))
        self.assertEqual(data.server.error,
                         "swap-proxy: egress refused (pinning-failed)")
        self.assertIn(("box.local", "93.184.216.34", "pinning-failed"),
                      a.ssrf_refused)

    def test_audit_failure_refuses_swap(self):
        """The audit write is part of authorization: when it fails, the
        placeholder is left intact — no secret without a trail."""
        a = make_addon()
        a._audit = lambda host, matched: False
        req = Request("api.github.com", "/",
                      [("Authorization", "Bearer hsurr:github")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"),
                         "Bearer hsurr:github")

    def test_unknown_credential_audits_refused(self):
        """A placeholder with no matching secret leaves the text
        untouched and records an unknown-credential refusal."""
        a = make_addon()
        req = Request("api.github.com", "/",
                      [("Authorization", "Bearer hsurr:nosuch")])
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"),
                         "Bearer hsurr:nosuch")
        self.assertIn(("api.github.com", "nosuch", "unknown-credential"),
                      a.refused)


class ProxyHardeningRoundTests(unittest.TestCase):
    """Findings 70-72: response-header scrubbing, the request-side swap
    cap, and the TOTP scrub window. (Finding 73's TTL clamp is tested in
    test_grant_writer.py.)"""

    def test_70_response_headers_scrubbed(self):
        """Finding 70: a REAL secret value echoed in a response header —
        a /headers-style echo, an X-Subject-Token-style header, a
        Set-Cookie carrying the credential — is replaced with its
        placeholder, exactly like the body. (Seeding placeholders here
        would make the test vacuous: scrubbing is already-a-placeholder
        → placeholder.)"""
        a = make_addon()
        code = sa._totp_code("JBSWY3DPEHPK3PXP")
        resp = FakeResponse(b'{"ok": true}', "application/json")
        resp.headers["X-Echo-Auth"] = "Bearer ghp_TOKEN"
        resp.headers["Set-Cookie"] = "session=correct horse; Path=/"
        # second Set-Cookie value: exercises the get_all/set_all
        # round-trip with multiple values for one header
        resp.headers._items.append(("Set-Cookie", "prefs=dark"))
        resp.headers["X-OTP"] = "otp " + code
        flow = Flow(Request("github.com", "/headers"))
        flow.response = resp
        # headers are scrubbed at responseheaders time (they must not
        # wait for a body that, on a stream, never finishes)
        a.responseheaders(flow)
        self.assertEqual(resp.headers.get("X-Echo-Auth"),
                         "Bearer hsurr:github")
        cookies = resp.headers.get_all("Set-Cookie")
        self.assertIn("session=hsurr:acme:password; Path=/", cookies)
        self.assertIn("prefs=dark", cookies)
        self.assertEqual(resp.headers.get("X-OTP"), "otp hsurr:acme:totp")
        # content-length still describes the (unscrubbed) body
        self.assertEqual(resp.headers.get("content-length"),
                         str(len(resp.content)))
        # a header with no secret in it is byte-identical
        self.assertEqual(resp.headers.get("content-type"), "application/json")
        # framing headers are never scrubbed (finding 70b), even if a
        # value collides with a whole-token TOTP code
        resp2 = FakeResponse(b"x", "application/json")
        resp2.headers["Content-Length"] = code
        flow = Flow(Request("github.com", "/"))
        flow.response = resp2
        a.responseheaders(flow)
        self.assertEqual(resp2.headers.get("Content-Length"), code)
        # non-allowlisted host: headers untouched
        other = FakeResponse(b"ghp_TOKEN", "text/plain")
        other.headers["X-Echo"] = "ghp_TOKEN"
        flow = Flow(Request("evil.example", "/"))
        flow.response = other
        a.responseheaders(flow)
        self.assertEqual(other.headers.get("X-Echo"), "ghp_TOKEN")

    def test_71_oversize_request_body_passes_through_unswapped(self):
        """Finding 71: a request body over the swap cap passes through
        unswapped (headers/query/path were already handled); the skip is
        loud in the log and leaves a durable audit note."""
        a = make_addon()
        big = (b'{"k": "hsurr:github", "pad": "'
               + b"x" * (sa._MAX_SWAP_BODY_BYTES + 1) + b'"}')
        req = Request("api.github.com", "/x?token=hsurr:github",
                      [("Authorization", "Bearer hsurr:github"),
                       ("Content-Type", "application/json")],
                      big)
        records = []

        class H(logging.Handler):
            def emit(self, r):
                records.append(r.getMessage())

        h = H()
        sa.log.addHandler(h)
        self.addCleanup(sa.log.removeHandler, h)
        a.request(Flow(req))
        # header and query swaps happened before the body gate...
        self.assertEqual(req.headers.get("Authorization"),
                         "Bearer ghp_TOKEN")
        self.assertNotIn(b"hsurr:github", req.path.encode())
        self.assertIn(b"ghp_TOKEN", req.path.encode())
        # ...but the oversize body passed through untouched
        self.assertIn(b"hsurr:github", req.content)
        self.assertTrue(any("over swap cap" in r for r in records), records)
        # ...and the skip left a durable audit note (not just a log)
        self.assertIn(("api.github.com", "request-body", "over-swap-cap"),
                      a.audit_notes)

    def test_71_body_exactly_at_cap_is_still_swapped(self):
        """Finding 71: the gate is `>`, not `>=` — a body of exactly
        _MAX_SWAP_BODY_BYTES is still swapped. Pins the boundary."""
        a = make_addon()
        pad_len = sa._MAX_SWAP_BODY_BYTES - len(b'{"k": "hsurr:github"}')
        body = b'{"k": "hsurr:github"}' + b"x" * pad_len
        self.assertEqual(len(body), sa._MAX_SWAP_BODY_BYTES)
        req = Request("api.github.com", "/x",
                      [("Content-Type", "application/json")], body)
        a.request(Flow(req))
        self.assertNotIn(b"hsurr:github", req.content)
        self.assertIn(b"ghp_TOKEN", req.content)
        self.assertEqual(a.audit_notes, [])

    def test_71_oversize_websocket_message_passes_through(self):
        """Finding 71: the same cap applies to websocket text frames,
        with the same durable audit note."""
        a = make_addon()
        big = b"hsurr:github" + b"x" * (sa._MAX_SWAP_BODY_BYTES + 1)
        flow = Flow(Request("api.github.com", "/ws"))
        flow.websocket = FakeWebSocket([FakeWSMessage(big)])
        a.websocket_message(flow)
        self.assertIn(b"hsurr:github",
                      flow.websocket.messages[-1].content)
        self.assertIn(("api.github.com", "websocket-message",
                       "over-swap-cap"), a.audit_notes)

    def test_72_totp_scrub_window_covers_adjacent_steps(self):
        """Finding 72: TOTP codes from the previous and next 30s steps
        are scrubbed too — a page echoing a code the agent submitted
        ~40 seconds ago is still covered. Time is frozen so a step
        boundary can never fall between the test's clock and the
        addon's clock."""
        a = make_addon()
        fixed = 1750000000.0
        with mock.patch.object(sa.time, "time", return_value=fixed):
            prev_code = totp("JBSWY3DPEHPK3PXP", fixed - 30)
            next_code = totp("JBSWY3DPEHPK3PXP", fixed + 30)
            body = ('{"prev": "%s", "next": "%s"}'
                    % (prev_code, next_code)).encode()
            resp = FakeResponse(body, "application/json")
            flow = Flow(Request("acme.example.com", "/"))
            flow.response = resp
            a.response(flow)
        self.assertNotIn(prev_code.encode(), resp.content)
        self.assertNotIn(next_code.encode(), resp.content)
        self.assertEqual(resp.content.count(b"hsurr:acme:totp"), 2)


class PushNotifyHookTests(unittest.TestCase):
    """H2 / QA B4: the _file_approval push hook fires, passes the filed
    item through, and never raises — even when push.py is absent."""

    def _drain(self, seen, want=1, timeout=5):
        deadline = time.time() + timeout
        while len(seen) < want and time.time() < deadline:
            time.sleep(0.05)

    def test_push_notify_delivers_item_off_thread(self):
        seen = []

        class _Sender:
            def notify_approval(self, item):
                seen.append(item)
                return 1

        class FakeMod:
            class PushSender:
                @staticmethod
                def default():
                    return _Sender()

        with mock.patch.object(sa, "_load_push_module",
                               return_value=FakeMod):
            sa._push_notify({"id": "abc123", "summary": "x"})
        self._drain(seen)
        self.assertEqual(seen, [{"id": "abc123", "summary": "x"}])

    def test_push_notify_loader_failure_never_raises(self):
        with mock.patch.object(sa, "_load_push_module",
                               side_effect=RuntimeError("no push.py")):
            # Must not raise: the approval was already filed.
            sa._push_notify({"id": "abc123"})

    def test_push_notify_sender_failure_never_raises(self):
        class _Sender:
            def notify_approval(self, item):
                raise OSError("push service down")

        class FakeMod:
            class PushSender:
                @staticmethod
                def default():
                    return _Sender()

        with mock.patch.object(sa, "_load_push_module",
                               return_value=FakeMod):
            sa._push_notify({"id": "abc123"})  # must not raise


class SecuritySweepTests(unittest.TestCase):
    """2026-09-19 build-loop security sweep (open-source track)."""

    def test_host_list_trailing_dot(self):
        """DNS treats "host." as identical to "host": the ssrf.deny name
        entries (finding-47 self-peer guard) must match with or without
        the trailing dot, or one character bypasses the name check."""
        self.assertTrue(sa._host_in_list("spark-vm.axolotl-sirius.ts.net.",
                                        ["spark-vm.axolotl-sirius.ts.net"]))
        self.assertTrue(sa._host_in_list("github.com.", ["github.com"]))
        self.assertTrue(sa._host_in_list("sub.example.com.",
                                        [".example.com"]))
        self.assertTrue(sa._host_in_list("sub.example.com",
                                        [".example.com."]))
        # still a real matcher, not a prefix match
        self.assertFalse(sa._host_in_list("evilexample.com.", ["example.com"]))
        self.assertFalse(sa._host_in_list("example.com.evil.",
                                         ["example.com"]))

    def test_grant_path_prefix_smuggling_refused(self):
        """The grants.json path_prefix branch gets the finding-42
        smuggling guard (%, ;, \\) that the registry allowed_paths
        branch already had: a backslash separator must not escape the
        grant's prefix on a lenient backend."""
        a = make_addon(hosts=["api.example.com"],
                       secrets={"api": "API-TOKEN"},
                       registry={"api": {"allowed_hosts": ["api.example.com"],
                                         "allowed_paths": ["/other"]}})
        grant = {"credential": "api", "host": "api.example.com",
                 "method": "POST", "path_prefix": "/v1",
                 "expires": "2999-01-01T00:00:00+00:00"}
        a._grants = lambda: [grant]
        ok, reason = a._credential_allows_request(
            "api", "api.example.com", "POST", "/v1/\\../admin")
        self.assertEqual((ok, reason), (False, "path-not-allowed"))
        # the refusal is hard, not per-grant: an evasive path is not
        # retried against a wider second grant
        a._grants = lambda: [dict(grant, path_prefix="/")]
        ok, reason = a._credential_allows_request(
            "api", "api.example.com", "POST", "/v1/;x/admin")
        self.assertEqual((ok, reason), (False, "path-not-allowed"))
        # a clean in-prefix path still swaps through the grant
        req = Request("api.example.com", "/v1/repos", method="POST",
                      headers=[("Authorization", "Bearer hsurr:api")])
        a._grants = lambda: [grant]
        a.request(Flow(req))
        self.assertEqual(req.headers.get("Authorization"), "Bearer API-TOKEN")

    def test_responseheaders_scrubs_streaming_headers(self):
        """Streaming/SSE responses never finish the buffered body hook,
        so secret-bearing headers must be scrubbed at responseheaders
        time — the body hook firing (or not) cannot be the gate."""
        a = make_addon()
        resp = FakeResponse(b'data: {"x": 1}\n\n', "text/event-stream")
        resp.headers["Set-Cookie"] = "session=correct horse; Path=/"
        flow = Flow(Request("github.com", "/stream"))
        flow.response = resp
        a.responseheaders(flow)  # headers arrive; the body never completes
        cookies = resp.headers.get_all("Set-Cookie")
        self.assertTrue(all("correct horse" not in c for c in cookies))
        self.assertIn("session=hsurr:acme:password; Path=/", cookies)


class AuditLogDiskGuardTests(unittest.TestCase):
    """Finding 198: swap.log must be bounded, and the no-swap-without-
    trail invariant must hold when the disk fills. The addon guards the
    log's filesystem before every audit write (warn below
    LOG_WARN_FREE_BYTES, refuse below LOG_MIN_FREE_BYTES); rotation
    itself is the logrotate policy installed by proxy/deploy.sh."""

    def _addon_with_real_audit(self):
        a = make_addon()
        del a._audit  # drop the make_addon stub; exercise the real one
        return a

    def _statvfs(self, free_bytes, block=4096):
        blocks = (free_bytes + block - 1) // block
        return os.statvfs_result(
            (block, block, blocks * 2, blocks, blocks, 0, 0, 0, 0, 255))

    def _patched(self, tmp_path, free_bytes):
        """Context: LOG_FILE under tmp, guard thresholds pinned, a fake
        statvfs reporting free_bytes, and the warn throttle reset."""
        from contextlib import ExitStack
        sa._LAST_LOW_SPACE_WARN_AT = 0.0
        log_file = Path(tmp_path) / "swap.log"
        stack = ExitStack()
        stack.enter_context(mock.patch.object(sa, "LOG_FILE", log_file))
        stack.enter_context(mock.patch.object(sa, "LOG_WARN_FREE_BYTES",
                                              256 * 1024 * 1024))
        stack.enter_context(mock.patch.object(sa, "LOG_MIN_FREE_BYTES",
                                              16 * 1024 * 1024))
        stack.enter_context(mock.patch(
            "os.statvfs", return_value=self._statvfs(free_bytes)))
        return stack


    def test_low_space_warns_but_still_writes(self):
        """Between the warn and refuse thresholds the write proceeds —
        the operator gets a loud journal warning BEFORE the fail-closed
        cascade, not only the cascade itself."""
        with tempfile.TemporaryDirectory() as tmp:
            with self._patched(tmp, 100 * 1024 * 1024):
                a = self._addon_with_real_audit()
                with self.assertLogs(sa.log, level="WARNING") as logs:
                    self.assertTrue(a._audit("api.github.com", "github"))
                self.assertTrue(any("low on space" in m
                                     for m in logs.output))
                lines = (Path(tmp) / "swap.log").read_text().splitlines()
                self.assertEqual(len(lines), 1)
                self.assertIn("swapped=github", lines[0])

    def test_plenty_space_writes_quietly(self):
        """Healthy disk: the audit line lands and no warning is logged."""
        with tempfile.TemporaryDirectory() as tmp:
            with self._patched(tmp, 10 * 1024**3):
                a = self._addon_with_real_audit()
                with self.assertNoLogs(sa.log, level="WARNING"):
                    self.assertTrue(a._audit("api.github.com", "github"))
                self.assertTrue((Path(tmp) / "swap.log").exists())

    def test_unqueryable_filesystem_proceeds(self):
        """When the filesystem cannot be queried the guard is unknowable
        and the write proceeds — the guard is defense in depth; the
        write itself still fails closed on a real ENOSPC."""
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "swap.log"
            with (mock.patch.object(sa, "LOG_FILE", log_file),
                  mock.patch("os.statvfs", side_effect=OSError(2, "nope"))):
                a = self._addon_with_real_audit()
                self.assertIsNone(sa._audit_disk_free_bytes())
                self.assertTrue(a._audit("api.github.com", "github"))
                self.assertTrue(log_file.exists())




if __name__ == "__main__":
    unittest.main()
