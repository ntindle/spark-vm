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
    def __init__(self, host, path="/", headers=(), content=b""):
        self.pretty_host = host
        self.path = path
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


class _FakeMPHTTP:
    class Response:
        @staticmethod
        def make(status, content, headers):
            return _FakeMPResponse(status, content, headers)


def fake_mp_module():
    """Stand in for mitmproxy.http so _refuse takes its prod path."""
    real = sa._mp_http
    sa._mp_http = _FakeMPHTTP()
    return real


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
        """REVIEW item 25: single-vs-multi comes from the registry or the
        #hsurr:multi marker, never from sniffing the content — a
        single-value secret that looks like 'k=v' stays a single value."""
        a = make_addon()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x"
            p.write_text("token=abc=def\n")
            self.assertEqual(a._load_secret_file(p, []), "token=abc=def")
            self.assertEqual(a._load_secret_file(p, ["token"]),
                             {"token": "abc=def"})
            p.write_text("#hsurr:multi\nuser=jdoe\npassword=x\n")
            self.assertEqual(a._load_secret_file(p, []),
                             {"user": "jdoe", "password": "x"})
            # registry declaration is enough without the marker
            p.write_text("user=jdoe\npassword=x\n")
            self.assertEqual(a._load_secret_file(p, ["user", "password"]),
                             {"user": "jdoe", "password": "x"})

    def test_bug_private_range_refused(self):
        """REVIEW item 29: private-range egress is refused by default,
        allowed only via the ssrf allow file; DNS failure fails open."""
        real = fake_mp_module()
        self.addCleanup(setattr, sa, "_mp_http", real)
        now = time.time()

        def box(private=True, **kw):
            a = make_addon(hosts=["box.local"],
                           registry={"box": {"allowed_hosts": ["box.local"]}},
                           secrets={"box": "box-SECRET"})
            ip = "192.168.1.1" if private else "93.184.216.34"
            a._dns_cache["box.local"] = (now + 3600, [ip])
            for k, v in kw.items():
                setattr(a, k, v)
            return a

        # refused by default
        a = box()
        flow = Flow(Request("box.local", "/"))
        a.request(flow)
        self.assertEqual(flow.response.status_code, 403)
        # hostname allowlist admits it
        a = box(ssrf_hosts=["box.local"])
        flow = Flow(Request("box.local", "/"))
        a.request(flow)
        self.assertIsNone(flow.response)
        # CIDR allowlist admits it
        a = box(ssrf_nets=[ipaddress.ip_network("192.168.0.0/16")])
        flow = Flow(Request("box.local", "/"))
        a.request(flow)
        self.assertIsNone(flow.response)
        # public IPs are unaffected
        a = box(private=False)
        flow = Flow(Request("box.local", "/"))
        a.request(flow)
        self.assertIsNone(flow.response)
        # DNS failure fails open (the request can't complete upstream anyway)
        a = box()
        a._dns_cache["box.local"] = (now + 3600, None)
        flow = Flow(Request("box.local", "/"))
        a.request(flow)
        self.assertIsNone(flow.response)

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
