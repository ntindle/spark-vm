"""Tests for harness/proxy_match.py (R2 provision-time injector support).

Issue #261: proxy_match.py no longer mirrors the proxy's matching functions
-- it imports them from the stdlib-only shared module proxy/host_match.py
(which proxy/swap_addon.py imports too). The old drift tripwire
(mirror-vs-real agreement on a fixed corpus) is gone: divergence is
impossible by construction. What remains is a much smaller contract test --
the wiring identities plus the behavior corpora pinning the SHARED module's
documented behavior with explicit expected outcomes (so a future edit to
host_match.py fails loudly instead of silently changing enforcement and
injector semantics) -- alongside the unchanged echo-detection and
injector-CLI suites.

The behavior corpora encode issue #257 (IP-literal normalization), the
finding-47 trailing-dot-after-port-strip ordering, the leading-dot
subdomain rule, and the ssrf allow-file parse contract (finding 29).
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
import host_match as hm  # noqa: E402 -- the shared module both sides import

import logging  # noqa: E402
sa.log.propagate = False
sa.log.addHandler(logging.NullHandler())


# --- Shared-matcher behavior corpora --------------------------------------
# (host, entries, expected): the documented semantics of host_match.py,
# pinned with explicit outcomes. A failure here means host_match.py itself
# changed -- reconcile deliberately (issue #261: this is the contract
# both the proxy and the injector run on).

HOST_CASES = [
    # (host, entries, expected)
    ("api.anthropic.com", ["api.anthropic.com"], True),
    ("API.ANTHROPIC.COM", ["api.anthropic.com"], True),
    ("api.anthropic.com.", ["api.anthropic.com"], True),
    ("api.anthropic.com", ["api.anthropic.com."], True),
    ("foo.api.anthropic.com", [".api.anthropic.com"], True),
    ("api.anthropic.com.evil.com", [".api.anthropic.com"], False),
    ("api.anthropic.com", [".api.anthropic.com"], False),  # bare host vs dot entry
    ("127.0.0.1", ["127.0.0.1"], True),
    ("127.0.0.1:8080", ["127.0.0.1"], True),
    ("127.0.0.1", ["127.0.0.1:8080"], False),
    ("localhost", ["localhost"], True),
    ("LOCALHOST", ["127.0.0.1", "localhost"], True),
    ("::1", ["::1"], True),            # issue #257: IP literals match
    ("::1", ["127.0.0.1"], False),
    ("[::1]", ["::1"], True),            # bracketed literal, normalized
    ("[::1]:8080", ["::1"], True),      # bracketed literal with port
    ("::1", ["[::1]"], True),           # bracketed entry, normalized
    ("::1.", ["::1"], True),            # trailing dot on a literal
    ("fe80::1", ["fe80::1"], True),     # non-loopback v6 literal
    ("0:0:0:0:0:0:0:1", ["::1"], True),  # normalized spelling of ::1
    ("::1", ["::2"], False),             # different literal
    ("::1", ["localhost"], False),       # hostname entry never matches a literal
    ("127.0.0.1", ["::1"], False),       # literal entry never matches a v4 host
    ("::ffff:127.0.0.1", ["::ffff:127.0.0.1"], True),  # v4-mapped v6
    ("example.com", [], False),
    ("example.com", None, False),
    (None, ["example.com"], False),
    ("", ["example.com"], False),
    ("example.com", ["EXAMPLE.COM"], True),
    ("sub.example.com", [".example.com"], True),
    ("example.com.", [".EXAMPLE.com."], False),
    ("a.b.c.d", ["b.c.d"], False),
    ("xn--nxasmq6b.example", ["xn--nxasmq6b.example"], True),
    ("127.1", ["127.0.0.1"], False),    # not a match, no normalization
    ("123", [123], True),              # non-string registry entries are str()'d
    ("127.0.0.1", [" 127.0.0.1 "], False),  # entries are NOT whitespace-stripped
    ("127.0.0.1", [".0.0.1"], False),  # issue #257: IP literals never take the
    # leading-dot subdomain rule (the old string-suffix accident) -- a
    # partial-IP entry matches nothing at enforcement, so the injector
    # must not flag it as an echo exemption either
    ("127.0.0.1:8080", [".0.0.1"], False),  # port strips before the literal
    # parse: a port-suffixed literal takes the IP path too
    ("example.com.:8080", ["example.com"], True),  # Security: the dot-strip
    # runs AFTER the port strip -- a trailing-dot host:port must still
    # match (fail-closed ssrf.deny name entries); regressed once in
    # e9ff2c7 and pinned here
]

# (text, expected hosts, expected nets as strings)
SSRF_CASES = [
    ("", [], []),
    ("# just a comment\n", [], []),
    ("api.example.com\n", ["api.example.com"], []),
    ("API.EXAMPLE.COM\n", ["api.example.com"], []),
    (".example.com\n", [".example.com"], []),
    ("  api.example.com  \n", ["api.example.com"], []),
    ("api.example.com\n127.0.0.1\n# comment\n\nlocalhost\n",
     ["api.example.com", "localhost"], ["127.0.0.1/32"]),
    ("10.0.0.0/8\n", [], ["10.0.0.0/8"]),
    ("127.0.0.0/8\n", [], ["127.0.0.0/8"]),
    ("127.0.0.1/32\n", [], ["127.0.0.1/32"]),
    ("::1/128\n", [], ["::1/128"]),
    ("fe80::/10\n", [], ["fe80::/10"]),
    ("2001:db8::/32\n", [], ["2001:db8::/32"]),
    ("999.999.0.0/16\n", ["999.999.0.0/16"], []),      # invalid CIDR -> hostname
    ("example.com:8080\n", ["example.com:8080"], []),    # not an IP -> hostname
    ("2001:db8::1\n", [], ["2001:db8::1/128"]),         # bare IPv6 -> /128
    ("127.0.0.1\n", [], ["127.0.0.1/32"]),
    ("::1\n", [], ["::1/128"]),
    ("1.2.3.4\n", [], ["1.2.3.4/32"]),
]


class TestSharedMatcherContract(unittest.TestCase):
    """Issue #261: the matcher is shared by construction -- proxy_match.py
    and swap_addon.py import the same proxy/host_match.py functions. The
    contract pins (1) the wiring identities, so no mirror can silently
    drift back in, and (2) the shared module's documented behavior with
    explicit expected outcomes, so a future edit to host_match.py fails
    loudly instead of silently changing enforcement and injector
    semantics. Do not "fix" a behavior failure by editing the corpus:
    reconcile the change deliberately in host_match.py."""

    def test_matcher_imports_are_the_shared_module(self):
        # Divergence-by-construction, proven by identity: the names every
        # consumer calls are the host_match.py function objects.
        self.assertIs(pm.host_in_list, hm.host_in_list)
        self.assertIs(pm.parse_ssrf_allow, hm.parse_ssrf_allow)
        self.assertIs(sa._host_in_list, hm.host_in_list)
        self.assertIs(sa._parse_ssrf_allow, hm.parse_ssrf_allow)

    def test_corpus_discriminates(self):
        # The behavior pin is vacuous if the corpus never exercises both
        # outcomes.
        results = {expected for _, _, expected in HOST_CASES}
        self.assertEqual(results, {True, False})

    def test_host_in_list_behavior(self):
        for host, entries, expected in HOST_CASES:
            with self.subTest(host=host, entries=entries):
                self.assertEqual(hm.host_in_list(host, entries), expected)

    def test_parse_ssrf_allow_behavior(self):
        for text, exp_hosts, exp_nets in SSRF_CASES:
            with self.subTest(text=text):
                hosts, nets = hm.parse_ssrf_allow(text)
                self.assertEqual(hosts, exp_hosts)
                self.assertEqual([str(n) for n in nets], exp_nets)

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
        # ...and a trailing-dot host:port still matches a bare entry:
        # the dot-strip runs AFTER the port strip (Security blocker
        # fix -- this regressed to False once; pinned against relapse).
        self.assertTrue(pm.host_in_list("example.com.:8080", ["example.com"]))
        self.assertTrue(sa._host_in_list("example.com.:8080", ["example.com"]))

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

    def test_is_echo_entry_noncanonical_loopback_spellings(self):
        # Issue #259: non-canonical IPv4 spellings exact-match at
        # enforcement and resolve to loopback on the box, so a binding or
        # allowlist line using one is a live echo exemption the teardown
        # must flag. inet_aton accepts the short/octal/hex/decimal forms
        # ipaddress rejects.
        for h in ("127.1", "127.0.0.2", "0x7f.0.0.1", "2130706433",
                  "0177.0.0.1", "0x7f000001", "0X7F.0.0.1", "0x7f.0.0.01",
                  "127.1.", "  0x7f.0.0.1  ", "2130706432", "0x7f000000"):
            self.assertTrue(pm.is_echo_entry(h), h)
        # Non-loopback spellings of the same classes stay clean, and the
        # entry-side-port rule still holds (ports are inert at enforcement,
        # pinned by test_is_echo_entry_entry_side_ports_are_inert): an
        # entry carrying a port is never a live exemption, loopback or not.
        # Null bytes must reject cleanly, not crash the gate (Security
        # round-1 blocker: inet_aton raises ValueError on embedded NUL).
        for h in ("8.8.8.8", "0x8.8.8.8", "134744072", "0x80000001",
                  "0200.0.0.1", "0.0.0.0", "127.1:8080", "127.1.evil.com",
                  "\x00127.0.0.1", "127.0.0.1\x00", "126.1", "128.0.0.1"):
            self.assertFalse(pm.is_echo_entry(h), h)
        # Issue #269 (fixed): IPv4-mapped IPv6 loopback spellings
        # exact-match at enforcement since #257 and route to loopback on
        # the box, so they are flagged on the hosts side now.
        self.assertTrue(pm.is_echo_entry("::ffff:127.0.0.1"))
        # The ssrf path inherits the fix for bare-IP spellings via the
        # is_echo_entry fallback (hostname treatment of non-ipaddress
        # lines): "0x7f.0.0.1/8" is a different story -- the real
        # _parse_ssrf_allow treats it as an (inert) hostname too, so the
        # tripwire side and this side stay in agreement.
        self.assertTrue(pm.ssrf_line_is_echo("0x7f.0.0.1"))
        self.assertTrue(pm.ssrf_line_is_echo("127.1"))
        self.assertFalse(pm.ssrf_line_is_echo("0x8.8.8.8"))
        # A CIDR-shaped non-canonical spelling is dead on both sides: the
        # real _parse_ssrf_allow treats it as an (inert) hostname too.
        self.assertFalse(pm.ssrf_line_is_echo("0x7f.0.0.1/8"))

    def test_is_echo_entry_mapped_loopback(self):
        # Issue #269: IPv4-mapped IPv6 spellings whose embedded address is
        # in 127.0.0.0/8 exact-match at enforcement (host_in_list
        # normalizes IP literals since #257 -- pinned by the drift
        # tripwire) and route to loopback on the box (RFC 4291 mapped
        # semantics; the proxy's own SSRF layer already judges them as
        # 127.0.0.1 -- finding 37), so each is a live echo exemption the
        # teardown must flag.
        for h in ("::ffff:127.0.0.1", "::FFFF:127.0.0.1",
                  "[::ffff:127.0.0.1]", "[::ffff:127.0.0.1]:8080",
                  "::ffff:7f00:1", "::ffff:127.0.0.1.",
                  "  ::ffff:127.0.0.1  ", "::ffff:127.0.0.1%eth0"):
            self.assertTrue(pm.is_echo_entry(h), h)
        # Non-loopback mapped addresses stay clean. An unbracketed
        # port-carrying form never parses as an address and is inert at
        # enforcement (pinned by
        # test_is_echo_entry_entry_side_ports_are_inert), so it is
        # correctly not flagged -- but the bracketed literal-with-port
        # form IS stripped to the literal at enforcement (host_in_list),
        # so it rides the True list above, as does the zone-id form
        # (exact-matches a same-zone host at enforcement).
        for h in ("::ffff:8.8.8.8", "::ffff:192.168.1.1",
                  "::ffff:127.0.0.1:8080"):
            self.assertFalse(pm.is_echo_entry(h), h)
        # Narrowed-alias overrides cannot shrink the mapped set
        # (fail-closed, like the 127/8 and .localhost sets).
        self.assertTrue(pm.is_echo_entry("::ffff:127.0.0.1", aliases=()))

    def test_ssrf_line_is_echo_mapped_loopback(self):
        # Issue #269, ssrf side: mapped-loopback lines are flagged
        # fail-closed (they read as loopback-directed; no legitimate
        # allowlist entry is an IPv4-mapped net). Bare literals promote to
        # /128 under the proxy's own parsing.
        for line in ("::ffff:127.0.0.1", "::ffff:127.0.0.1/128",
                     "::ffff:127.0.0.0/104", "::ffff:0.0.0.0/96"):
            self.assertTrue(pm.ssrf_line_is_echo(line), line)
        self.assertFalse(pm.ssrf_line_is_echo("::ffff:8.8.8.8"))
        self.assertFalse(pm.ssrf_line_is_echo("::ffff:10.0.0.0/104"))

    def test_is_echo_entry_non_echo(self):
        # NB: "127.0.0.2" is NOT here -- since issue #259 it normalizes to
        # 127.0.0.0/8 and is flagged as echo (pinned above).
        for h in ("api.anthropic.com", "10.0.0.1", "example.com",
                  "localhos", "1.2.3.4"):
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
        self.assertEqual(p.returncode, 2)  # unverifiable != clean, same
        # exit-2 discipline as the bad-registry refusal above

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
        # Flake investigation (2026-09-26 dx turn): a one-off failure of
        # this test was observed once (2026-09-25) with no reproduction in
        # 150 isolated + 40 class-iteration runs. The code path is fully
        # deterministic (empty registry -> "no registry entry" -> exit 1),
        # so pin the stderr diagnostic too: if it ever fails again, the
        # failure output distinguishes a CLI misbehavior from a harness
        # problem (crash, env loss) instead of reporting a bare exit code.
        self.assertIn("llm-api has no registry entry", p.stderr)

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
