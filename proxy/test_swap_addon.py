"""Conformance tests for proxy/swap_addon.py.

Run from the repo root:
    python3 -m unittest proxy/test_swap_addon.py

No mitmproxy needed: the addon is stdlib-only, and these tests use a
minimal fake flow exposing only the attributes request() reads. If
mitmproxy is installed, mitmproxy.test.tflow can replace the fake.

Tests named test_bug_* encode the expected behaviour from
browser-driver/REVIEW.md and FAIL at a006f6e on purpose. Tests named
test_holds_* pass today and guard against regressions. Nothing here
touches /home/swapd: reload and audit are stubbed out.
"""

import base64
import hashlib
import hmac
import json
import os
import struct
import sys
import time
import unittest
import urllib.parse

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


SECRETS = {
    "github": "ghp_TOKEN",
    "openai": "sk-OPENAI",
    "pw": 'p&ss=w"o\\rd%7d',
    "acme": {"username": "jdoe", "password": "correct horse",
             "totp": "JBSWY3DPEHPK3PXP"},
}
HOSTS = ["github.com", "api.github.com", "acme.example.com"]


def make_addon(secrets=SECRETS, hosts=HOSTS):
    a = sa.SwapAddon.__new__(sa.SwapAddon)
    a.secrets = dict(secrets)
    a.hosts = list(hosts)
    a._store_mtime = a._hosts_mtime = None
    a._maybe_reload = lambda: None      # never touch /home/swapd here
    a._audit = lambda host, matched: None
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

    @unittest.skip("REVIEW item 1 needs a per-credential allowed_hosts "
                   "list in the registry first; then assert that "
                   "hsurr:openai is NOT swapped for github.com even though "
                   "github.com is in hosts.allow.")
    def test_bug_credential_bound_to_its_own_hosts(self):
        pass


if __name__ == "__main__":
    unittest.main()
