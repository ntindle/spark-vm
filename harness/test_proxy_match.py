"""Tests for harness/proxy_match.py (R2 provision-time injector support).

Two halves:

1. Unit tests for the echo-detection layer (is_echo_entry,
   ssrf_line_is_echo, allow_text_echo_entries) and the three injector
   CLI subcommands.

2. THE DRIFT TRIPWIRE: harness/inject-provision-state.sh decides, at
   provision time, whether a binding or allowlist entry is an *effective*
   echo exemption under the proxy's own matching semantics. proxy_match.py
   is the single shared mirror of proxy/swap_addon.py::_host_in_list and
   _parse_ssrf_allow. These tests assert the mirror agrees with the REAL
   proxy functions on a fixed corpus. If a proxy change (or a mirror
   change) breaks the agreement, the tripwire fails LOUDLY -- that is the
   point. Do not "fix" it by editing the corpus: reconcile the two sides
   deliberately and update both together.

The injector's echo detection treats "::1" as live; since issue #257 the
proxy agrees, so the two sides match on it again. test_ipv6_literals_match
pins the fixed behavior on both sides.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROXY_MATCH = os.path.join(HERE, "proxy_match.py")

sys.path.insert(0, HERE)
import proxy_match as pm  # noqa: E402

sys.path.insert(0, os.path.join(HERE, "..", "proxy"))
import swap_addon as sa  # noqa: E402

import logging  # noqa: E402
sa.log.propagate = False
sa.log.addHandler(logging.NullHandler())


# --- Drift tripwire corpora ------------------------------------------------

HOST_CORPUS = [
    # (host, entries)
    ("api.anthropic.com", ["api.anthropic.com"]),
    ("API.ANTHROPIC.COM", ["api.anthropic.com"]),
    ("api.anthropic.com.", ["api.anthropic.com"]),
    ("api.anthropic.com", ["api.anthropic.com."]),
    ("foo.api.anthropic.com", [".api.anthropic.com"]),
    ("api.anthropic.com.evil.com", [".api.anthropic.com"]),
    ("api.anthropic.com", [".api.anthropic.com"]),  # bare host vs dot entry
    ("127.0.0.1", ["127.0.0.1"]),
    ("127.0.0.1:8080", ["127.0.0.1"]),
    ("127.0.0.1", ["127.0.0.1:8080"]),
    ("localhost", ["localhost"]),
    ("LOCALHOST", ["127.0.0.1", "localhost"]),
    ("::1", ["::1"]),            # issue #257: IP literals match (True)
    ("::1", ["127.0.0.1"]),
    ("[::1]", ["::1"]),            # bracketed literal, normalized (True)
    ("[::1]:8080", ["::1"]),      # bracketed literal with port (True)
    ("::1", ["[::1]"]),           # bracketed entry, normalized (True)
    ("::1.", ["::1"]),            # trailing dot on a literal (True)
    ("fe80::1", ["fe80::1"]),     # non-loopback v6 literal (True)
    ("0:0:0:0:0:0:0:1", ["::1"]),  # normalized spelling of ::1 (True)
    ("::1", ["::2"]),             # different literal (False)
    ("::1", ["localhost"]),       # hostname entry never matches a literal (False)
    ("127.0.0.1", ["::1"]),       # literal entry never matches a v4 host (False)
    ("::ffff:127.0.0.1", ["::ffff:127.0.0.1"]),  # v4-mapped v6 (True)
    ("example.com", []),
    ("example.com", None),
    (None, ["example.com"]),
    ("", ["example.com"]),
    ("example.com", ["EXAMPLE.COM"]),
    ("sub.example.com", [".example.com"]),
    ("example.com.", [".EXAMPLE.com."]),
    ("a.b.c.d", ["b.c.d"]),
    ("xn--nxasmq6b.example", ["xn--nxasmq6b.example"]),
    ("127.1", ["127.0.0.1"]),    # not a match, no normalization
    ("123", [123]),              # non-string registry entries are str()'d
    ("127.0.0.1", [" 127.0.0.1 "]),  # entries are NOT whitespace-stripped
    ("127.0.0.1", [".0.0.1"]),  # issue #257: IP literals never take the
    # leading-dot subdomain rule (the old string-suffix accident) -- a
    # partial-IP entry matches nothing at enforcement, so the injector
    # must not flag it as an echo exemption either (False, both sides)
]

SSRF_CORPUS = [
    "",
    "# just a comment\n",
    "api.example.com\n",
    "API.EXAMPLE.COM\n",
    ".example.com\n",
    "  api.example.com  \n",
    "api.example.com\n127.0.0.1\n# comment\n\nlocalhost\n",
    "10.0.0.0/8\n",
    "127.0.0.0/8\n",
    "127.0.0.1/32\n",
    "::1/128\n",
    "fe80::/10\n",
    "2001:db8::/32\n",
    "999.999.0.0/16\n",      # invalid CIDR -> hostname treatment
    "example.com:8080\n",    # not an IP -> hostname treatment
    "2001:db8::1\n",         # bare IPv6 -> /128
    "127.0.0.1\n",
    "::1\n",
    "1.2.3.4\n",
]


class TestDriftTripwire(unittest.TestCase):
    """proxy_match.py must agree with the real proxy functions. A failure
    here means one side changed: reconcile deliberately, never by
    weakening the corpus."""

    def test_corpus_discriminates(self):
        # The tripwire is vacuous if the corpus never exercises both
        # outcomes on the real function.
        results = {sa._host_in_list(h, e) for h, e in HOST_CORPUS}
        self.assertEqual(results, {True, False})

    def test_host_in_list_agrees_with_proxy(self):
        for host, entries in HOST_CORPUS:
            with self.subTest(host=host, entries=entries):
                self.assertEqual(pm.host_in_list(host, entries),
                                 sa._host_in_list(host, entries))

    def test_parse_ssrf_allow_agrees_with_proxy(self):
        for text in SSRF_CORPUS:
            with self.subTest(text=text):
                ph, pn = pm.parse_ssrf_allow(text)
                sh, sn = sa._parse_ssrf_allow(text)
                self.assertEqual(ph, sh)
                self.assertEqual([str(n) for n in pn],
                                 [str(n) for n in sn])

    def test_ipv6_literals_match(self):
        # Issue #257: the proxy used to fumble "::1" (split(":")[0] == ""),
        # so a "::1" binding never matched at enforcement. The matcher now
        # compares IP literals as normalized addresses; the injector's
        # echo layer agrees with no special case. Both facts pinned here.
        self.assertTrue(sa._host_in_list("::1", ["::1"]))
        self.assertTrue(pm.host_in_list("::1", ["::1"]))
        self.assertTrue(pm.is_echo_entry("::1"))
        self.assertTrue(pm.is_echo_entry("::1."))


class TestEchoLayer(unittest.TestCase):
    def test_is_echo_entry_aliases(self):
        for a in ("127.0.0.1", "localhost", "::1"):
            self.assertTrue(pm.is_echo_entry(a), a)
            self.assertTrue(pm.is_echo_entry(a.upper()), a)
        # Whitespace-padded registry entries: the injector strips before
        # matching (fail-closed superset; the proxy itself strips
        # nothing, so these are inert at enforcement but echo-intended).
        self.assertTrue(pm.is_echo_entry("  127.0.0.1  "))

    def test_is_echo_entry_entry_side_ports_are_inert(self):
        # The proxy strips ports on the REQUEST-host side only
        # (host.split(":")[0]); an entry WITH a port never matches at
        # enforcement, so it is not an echo exemption. Pinned so nobody
        # "fixes" the echo layer into flagging dead config as live.
        self.assertFalse(pm.host_in_list("127.0.0.1", ["127.0.0.1:8080"]))
        self.assertFalse(pm.is_echo_entry("127.0.0.1:8080"))
        # ...while a port on the request side still matches a bare entry.
        self.assertTrue(pm.host_in_list("127.0.0.1:8080", ["127.0.0.1"]))

    def test_is_echo_entry_leading_dot_subdomains(self):
        # Leading-dot entries match *.alias (loopback) at enforcement, so
        # they are live echo exemptions -- the gap the old inline logic
        # missed (a ".localhost" binding survived teardown as "clean").
        # Any depth under .localhost counts (RFC 6761): ".sub.localhost"
        # matches x.sub.localhost at enforcement, and bare
        # "sub.localhost" matches that exact name.
        self.assertTrue(pm.is_echo_entry(".localhost"))
        self.assertTrue(pm.is_echo_entry(".LOCALHOST."))
        self.assertTrue(pm.is_echo_entry(".127.0.0.1"))
        self.assertTrue(pm.is_echo_entry(".sub.localhost"))
        self.assertTrue(pm.is_echo_entry("sub.localhost"))
        self.assertTrue(pm.is_echo_entry("a.b.localhost"))
        self.assertTrue(pm.is_echo_entry("127.0.0.1."))   # trailing dot
        # But a bare host is NOT matched by a leading-dot entry, a
        # leading-dot entry for a non-echo domain is not an exemption,
        # and merely containing "localhost" is not enough.
        self.assertFalse(pm.host_in_list("localhost", [".localhost"]))
        self.assertFalse(pm.is_echo_entry(".example.com"))
        self.assertFalse(pm.is_echo_entry("notlocalhost"))
        self.assertFalse(pm.is_echo_entry("localhost.evil.com"))

    def test_is_echo_entry_non_echo(self):
        for h in ("api.anthropic.com", "10.0.0.1", "example.com",
                  "127.0.0.2", "localhos", "1.2.3.4"):
            self.assertFalse(pm.is_echo_entry(h), h)

    def test_ssrf_line_is_echo_cidr(self):
        self.assertTrue(pm.ssrf_line_is_echo("127.0.0.0/8"))
        self.assertTrue(pm.ssrf_line_is_echo("127.0.0.1/32"))
        self.assertTrue(pm.ssrf_line_is_echo("::1/128"))
        self.assertFalse(pm.ssrf_line_is_echo("10.0.0.0/8"))
        self.assertFalse(pm.ssrf_line_is_echo("2001:db8::/32"))
        self.assertFalse(pm.ssrf_line_is_echo("fe80::/10"))

    def test_ssrf_line_is_echo_bare_ip(self):
        # Bare IPs are promoted to /32 or /128 by the proxy's own parsing.
        self.assertTrue(pm.ssrf_line_is_echo("127.0.0.1"))
        self.assertTrue(pm.ssrf_line_is_echo("::1"))
        self.assertFalse(pm.ssrf_line_is_echo("10.0.0.1"))

    def test_ssrf_line_is_echo_hostname(self):
        self.assertTrue(pm.ssrf_line_is_echo("localhost"))
        self.assertTrue(pm.ssrf_line_is_echo("LOCALHOST"))
        self.assertFalse(pm.ssrf_line_is_echo("api.anthropic.com"))
        self.assertFalse(pm.ssrf_line_is_echo("999.999.0.0/16"))

    def test_allow_text_echo_entries_hosts(self):
        text = "api.example.com\n127.0.0.1  \n# comment\n\nLOCALHOST\n"
        self.assertEqual(pm.allow_text_echo_entries("hosts", text),
                         ["127.0.0.1  ", "LOCALHOST"])

    def test_allow_text_echo_entries_ssrf(self):
        text = "10.0.0.0/8\n127.0.0.0/8\napi.example.com\n::1\n"
        self.assertEqual(pm.allow_text_echo_entries("ssrf", text),
                         ["127.0.0.0/8", "::1"])

    def test_allow_text_echo_entries_clean(self):
        self.assertEqual(pm.allow_text_echo_entries("hosts", "api.example.com\n"), [])
        self.assertEqual(pm.allow_text_echo_entries("ssrf", "10.0.0.0/8\n"), [])


def run_cli(args, stdin_text, env_extra=None):
    env = dict(os.environ)
    env.update({"KEY_NAME": "llm-api",
                "ECHO_ALIASES": "127.0.0.1 localhost ::1"})
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, PROXY_MATCH] + args,
                          input=stdin_text, capture_output=True, text=True,
                          env=env, timeout=30)


def registry(hosts, placement="bearer_header"):
    return json.dumps({"llm-api": {"allowed_hosts": hosts,
                                   "access_token": {"placement": placement}}})


class TestInjectorCli(unittest.TestCase):
    """Behavior preservation for the three injector call sites."""

    def test_echo_bound_hosts_lists_echo(self):
        p = run_cli(["echo-bound-hosts"],
                    registry(["127.0.0.1", "api.anthropic.com"]))
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "127.0.0.1\n")

    def test_echo_bound_hosts_clean(self):
        p = run_cli(["echo-bound-hosts"], registry(["api.anthropic.com"]))
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "")

    def test_echo_bound_hosts_ipv6_literal(self):
        p = run_cli(["echo-bound-hosts"], registry(["::1"]))
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "::1\n")

    def test_echo_bound_hosts_subdomain_entry(self):
        # ".localhost" matches *.localhost (loopback) at enforcement: a
        # live echo exemption the old direction missed.
        p = run_cli(["echo-bound-hosts"], registry([".localhost"]))
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, ".localhost\n")

    def test_missing_key_name_refuses(self):
        # Security N1: a caller that forgets KEY_NAME must refuse, not
        # silently check the wrong key.
        env = dict(os.environ)
        env.pop("KEY_NAME", None)
        env["ECHO_ALIASES"] = "127.0.0.1 localhost ::1"
        p = subprocess.run([sys.executable, PROXY_MATCH, "echo-bound-hosts"],
                           input=registry(["api.anthropic.com"]),
                           capture_output=True, text=True,
                           env=env, timeout=30)
        self.assertNotEqual(p.returncode, 0)

    def test_echo_bound_hosts_bad_registry(self):
        p = run_cli(["echo-bound-hosts"], "not json")
        self.assertEqual(p.returncode, 2)  # unverifiable != clean

    def test_assert_key_binding_ok(self):
        p = run_cli(["assert-key-binding"], registry(["api.anthropic.com"]))
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_assert_key_binding_refuses_echo(self):
        p = run_cli(["assert-key-binding"],
                    registry(["api.anthropic.com", "localhost"]))
        self.assertEqual(p.returncode, 1)
        self.assertIn("echo host", p.stderr)

    def test_assert_key_binding_refuses_missing(self):
        p = run_cli(["assert-key-binding"], json.dumps({}))
        self.assertEqual(p.returncode, 1)

    def test_assert_key_binding_refuses_bad_placement(self):
        p = run_cli(["assert-key-binding"],
                    registry(["api.anthropic.com"], placement="query_param"))
        self.assertEqual(p.returncode, 1)
        self.assertIn("bearer_header", p.stderr)

    def test_assert_key_binding_refuses_no_hosts(self):
        p = run_cli(["assert-key-binding"], registry([]))
        self.assertEqual(p.returncode, 1)

    def test_allowlist_echo_entries_hosts(self):
        with tempfile.NamedTemporaryFile("w", suffix=".allow",
                                         delete=False) as f:
            f.write("api.example.com\n127.0.0.1\n# c\n")
            path = f.name
        try:
            p = run_cli(["allowlist-echo-entries", "hosts", path], "")
            self.assertEqual(p.returncode, 0)
            self.assertEqual(p.stdout, "127.0.0.1\n")
        finally:
            os.unlink(path)

    def test_allowlist_echo_entries_ssrf(self):
        with tempfile.NamedTemporaryFile("w", suffix=".allow",
                                         delete=False) as f:
            f.write("10.0.0.0/8\n::1/128\n")
            path = f.name
        try:
            p = run_cli(["allowlist-echo-entries", "ssrf", path], "")
            self.assertEqual(p.returncode, 0)
            self.assertEqual(p.stdout, "::1/128\n")
        finally:
            os.unlink(path)

    def test_allowlist_echo_entries_missing_file(self):
        p = run_cli(["allowlist-echo-entries", "hosts",
                     "/nonexistent/allow.file"], "")
        self.assertEqual(p.returncode, 1)  # unverifiable, never "clean"


if __name__ == "__main__":
    unittest.main()
