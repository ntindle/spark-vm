#!/usr/bin/env python3
"""proxy_match.py -- the injector's model of proxy/swap_addon.py matching.

harness/inject-provision-state.sh must decide, at provision time, whether a
credential binding or an allowlist entry is an *effective* echo-host exemption
under the inference proxy's own matching semantics. The proxy enforces with
proxy/swap_addon.py::_host_in_list (exact/leading-dot host entries, also used
for registry allowed_hosts and hosts.allow) and _parse_ssrf_allow (hostname or
CIDR entries). This module is the single shared mirror of those two functions
plus the echo-alias layer the injector needs.

It exists because the injector previously embedded three hand-copied mirrors
of the proxy logic in bash heredocs with nothing pinning them to the real
functions: a proxy matcher change would have silently voided the injector's
fail-closed teardown model (in either direction -- a missed exemption lets a
real key coexist with a live gate bypass; an over-strict mirror refuses
healthy images). harness/test_proxy_match.py is the drift tripwire: it
asserts this module agrees with the real swap_addon functions on a fixed
corpus, so either side can only change deliberately.

RESOLVED DIVERGENCE (2026-09-22, issue #257): sa._host_in_list used to
fumble the "::1" literal ("::1".split(":")[0] is ""), so a "::1" binding
or hosts.allow entry never matched at enforcement while the injector's
echo detection treated "::1" as a live echo alias anyway -- a documented
fail-closed superset. The proxy matcher now compares IP literals as
normalized addresses (issue #257), so the two sides agree on "::1"
again; the injector's echo layer needs no special case and this module
documents the resolution, not the divergence.

LOAD-BEARING ASSUMPTION: the echo set is exactly 127.0.0.1 / localhost /
::1 plus the .localhost subtree, PLUS every IPv4 spelling that normalizes
to 127.0.0.0/8 (127.1, 127.0.0.2, 0x7f.0.0.1, 2130706433, 0177.0.0.1,
0x7f000001 -- issue #259), PLUS every IPv4-mapped IPv6 spelling whose
embedded address is in 127.0.0.0/8 (::ffff:127.0.0.1, ::ffff:7f00:1 --
issue #269). These spellings exact-match at enforcement and resolve to
loopback on the box, so an echo detector that misses them leaves live
exemptions the teardown never flags.

Stdlib only. Deployed next to inject-provision-state.sh on the tenant box;
the injector calls it as ``python3 "$HERE/proxy_match.py" <subcommand>``.
"""

import ipaddress
import json
import os
import socket
import sys

# --- Mirrors of proxy/swap_addon.py (kept byte-faithful; the tripwire pins) --

def host_in_list(host, entries):
    """Mirror of proxy/swap_addon.py::_host_in_list: match host against exact
    names or leading-dot subdomain entries. Trailing dots are stripped on
    both sides. IP literals (v4 and v6) are compared as normalized addresses
    (issue #257): a single bracket pair is stripped first, hostname entries
    never match an IP-literal host, and CIDR entries never match here."""
    h = (host or "").lower()
    if h.startswith("["):
        end = h.find("]")
        if end != -1 and (end == len(h) - 1 or h[end + 1] == ":"):
            h = h[1:end]
    if h.count(":") == 1:
        # Single-colon host: a :port suffix, never an IPv6 literal.
        # Strip it BEFORE the literal parse so "127.0.0.1:8080" takes
        # the IP path like "127.0.0.1" does (multi-colon strings such
        # as "::1:8080" are parsed as addresses, not host:port).
        h = h.split(":")[0]
    # Dot-strip AFTER the port strip: "example.com.:8080" -> "example.com"
    # (before, it reintroduced a trailing-dot bypass of ssrf.deny name
    # entries for the host:port form).
    h = h.rstrip(".")
    try:
        h_ip = ipaddress.ip_address(h)
    except ValueError:
        h_ip = None
    if h_ip is None:
        # Hostname path: an IPv6 literal that failed parsing has no
        # port to strip and simply falls through to a (non-)match
        # below. (Single-colon hosts were already stripped above.)
        h = h.split(":")[0]
    for entry in entries or []:
        e = str(entry).lower()
        if e.startswith("["):
            end = e.find("]")
            if end != -1 and (end == len(e) - 1 or e[end + 1] == ":"):
                e = e[1:end]
        e = e.rstrip(".")
        if h_ip is not None:
            try:
                e_ip = ipaddress.ip_address(e)
            except ValueError:
                continue
            if h_ip == e_ip:
                return True
            continue
        if h == e or (e.startswith(".") and h.endswith(e)):
            return True
    return False


def parse_ssrf_allow(text):
    """Mirror of proxy/swap_addon.py::_parse_ssrf_allow: split the ssrf allow
    file into (hosts, nets). Lines are hostnames (exact or leading-dot,
    lowercased) or CIDR literals (bare IPs promoted to /32 or /128)."""
    hosts, nets = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "/" in line:
            try:
                nets.append(ipaddress.ip_network(line, strict=False))
                continue
            except ValueError:
                pass  # fall through to hostname treatment below
        try:
            ipaddress.ip_address(line)
            nets.append(ipaddress.ip_network(line + "/32"
                                             if ":" not in line
                                             else line + "/128"))
            continue
        except ValueError:
            pass
        hosts.append(line.lower())
    return hosts, nets


# --- Echo-alias layer (the injector's question, not the proxy's) -------------

ECHO_ALIASES = ("127.0.0.1", "localhost", "::1")
ECHO_NETS = (ipaddress.ip_network("127.0.0.0/8"),
             ipaddress.ip_network("::1/128"))
# The IPv4-mapped rendering of 127.0.0.0/8, for the ssrf allow-file side
# (issue #269). Enforcement unwraps mapped addresses before the net check
# (finding 37), so a mapped net is inert there -- but the exemption still
# reads as loopback-directed, so the echo layer flags the whole
# mapped-loopback space (fail-closed; no legitimate allowlist entry is an
# IPv4-mapped net).
ECHO_MAPPED_LOOPBACK_NET = ipaddress.ip_network("::ffff:127.0.0.0/104")


def _is_loopback_ipv4(text):
    """True when text normalizes to an address in 127.0.0.0/8 (issue #259).

    socket.inet_aton accepts the non-canonical IPv4 spellings ipaddress
    rejects -- short forms (127.1), octal (0177.0.0.1), hex (0x7f.0.0.1,
    0x7f000001), decimal (2130706433) -- and all of them exact-match at
    enforcement AND resolve to loopback on the box, so each is a live echo
    exemption the teardown must flag. ipaddress covers the canonical forms
    (and any canonical form inet_aton also accepts). Anything that is not
    an IP literal at all rejects cleanly down both paths -- including
    embedded null bytes (inet_aton raises ValueError there, so the except
    covers both OSError and ValueError). The trailing-dot/case
    normalization mirrors host_in_list's own rules and is applied here so
    the helper is self-sufficient for any direct caller (idempotent for
    the is_echo_entry call site, which normalizes already)."""
    if not text:
        return False
    t = text.lower().rstrip(".")
    if not t:
        return False
    try:
        addr = ipaddress.IPv4Address(
            int.from_bytes(socket.inet_aton(t), "big"))
    except (OSError, ValueError):
        # ValueError: inet_aton raises it (not OSError) on embedded null
        # bytes -- a crash here would turn a weird registry/allowlist entry
        # into a provisioning refusal, so fall through to the ipaddress
        # path, which rejects the same inputs cleanly.
        try:
            addr = ipaddress.ip_address(t)
        except ValueError:
            return False
        if not isinstance(addr, ipaddress.IPv4Address):
            return False
    return addr in ECHO_NETS[0]


def _is_mapped_loopback(text):
    """True when text is an IPv4-mapped IPv6 literal whose embedded IPv4
    address is in 127.0.0.0/8 (issue #269).

    Normalization mirrors host_in_list (lowercase, bracket strip,
    trailing-dot strip) so this flags exactly the spellings that
    exact-match at enforcement.
    The proxy's own SSRF layer already judges these as their embedded
    IPv4 (swap_addon._normalize_ip, finding 37: "::ffff:127.0.0.1 reaches
    localhost on Linux and must be judged as 127.0.0.1"); the echo layer
    was the one that missed them. On-box verification (2026-09-26): an
    IPv4-mapped destination IS the embedded IPv4 address at the IP layer
    (RFC 4291 s2.5.5.2 -- the kernel translates before routing, so a client
    connecting to ::ffff:127.0.0.1 reaches the echo fixture bound to
    127.0.0.1); ipaddress pins ipv4_mapped -> 127.0.0.1. A live-socket
    check on the loop box was inconclusive (the runtime's transparent
    egress proxy answered the AF_INET6 SYN -- getpeername showed the proxy,
    the local listener never accepted), an environment artifact, not a
    routing fact; the fix direction is fail-closed per the issue, so it
    does not gate on that test.

    An unbracketed port-carrying form ("::ffff:127.0.0.1:8080") never
    parses as an address and stays inert -- entry-side ports never match
    at enforcement (test pins), so it is correctly not flagged. The
    bracketed literal-with-port form ("[::ffff:127.0.0.1]:8080") IS
    stripped to the literal at enforcement (host_in_list), so it flags,
    as does a zone-id form (exact-matches a same-zone host)."""
    if not text:
        return False
    t = str(text).strip().lower()
    if t.startswith("["):
        end = t.find("]")
        if end != -1 and (end == len(t) - 1 or t[end + 1] == ":"):
            t = t[1:end]
    t = t.rstrip(".")
    try:
        addr = ipaddress.ip_address(t)
    except ValueError:
        return False
    mapped = getattr(addr, "ipv4_mapped", None)
    return mapped is not None and mapped in ECHO_NETS[0]


def is_echo_entry(entry, aliases=ECHO_ALIASES):
    """True when a single host-list entry (registry allowed_hosts item or
    hosts.allow line, already stripped) is an effective echo exemption
    under proxy semantics.

    Besides the bare aliases this covers leading-dot subdomain entries:
    ".localhost" matches every *.localhost name at enforcement
    (host_in_list's leading-dot rule); RFC 6761 reserves .localhost for
    loopback and stub resolvers commonly map *.localhost to
    127.0.0.1/::1, so any depth under .localhost -- ".sub.localhost",
    bare "sub.localhost" -- is treated as a live echo exemption.
    Fail-closed superset: no legitimate provider binding ends in
    .localhost. Without this, such a binding would survive the fixture
    teardown as "clean" while the proxy still swapped toward loopback
    names.

    Non-canonical IPv4 loopback spellings (issue #259: 127.1, 127.0.0.2,
    0x7f.0.0.1, 2130706433, 0177.0.0.1, 0x7f000001) are likewise treated
    as echo: they exact-match at enforcement and resolve to loopback on
    the box. This normalization runs unconditionally: a narrowed
    ECHO_ALIASES override can only shrink the exact-alias and leading-dot
    checks -- the 127/8 and .localhost sets are always covered
    (fail-closed). (::1 and localhost themselves ride the alias set, so
    narrowing ECHO_ALIASES unflags them too.)
    IPv4-mapped IPv6 loopback spellings (issue #269: ::ffff:127.0.0.1,
    ::ffff:7f00:1, bracketed forms) are likewise always flagged: they
    exact-match at enforcement since #257 and the kernel routes them to
    loopback, matching the proxy's own finding-37 judgment.
    Entry-side ports stay inert (test pins): a registry entry
    carrying a port never matches at enforcement, so nothing strips the
    port before normalization."""
    s = str(entry).strip()
    if any(host_in_list(a, [s]) for a in aliases):
        return True
    # ("::1" needs no literal special case anymore: host_in_list matches
    # IP literals as normalized addresses since issue #257, so the alias
    # loop above already covers it.)
    # Issue #259: non-canonical IPv4 loopback spellings exact-match at
    # enforcement and resolve to loopback on the box. Normalize on the
    # dot-stripped form, mirroring host_in_list's trailing-dot rule; ports
    # are deliberately NOT stripped (entry-side ports are inert at
    # enforcement -- the mirror check above already covers canonical
    # spellings, so this path only ever widens the fail-closed set).
    if _is_loopback_ipv4(s.lower().rstrip(".")):
        return True
    # Issue #269: IPv4-mapped IPv6 loopback spellings exact-match at
    # enforcement (host_in_list normalizes IP literals since #257) and
    # route to loopback on the box, so a binding like ::ffff:127.0.0.1 is
    # a live echo exemption the teardown must flag.
    if _is_mapped_loopback(s):
        return True
    low = s.lower().rstrip(".")
    if low.startswith(".") and low[1:] in tuple(a.lower() for a in aliases):
        return True
    if low.endswith(".localhost"):
        return True
    return False


def ssrf_line_is_echo(line):
    """True when a single ssrf.allow line (stripped, non-blank, non-comment)
    is an effective echo exemption: a CIDR covering 127.0.0.0/8 or ::1/128,
    a CIDR overlapping the IPv4-mapped loopback space (issue #269 -- inert at
    enforcement because the proxy unwraps mapped addresses before the net
    check, but loopback-directed, so flagged fail-closed), or an echo
    hostname under the proxy's own parsing."""
    net = None
    if "/" in line:
        try:
            net = ipaddress.ip_network(line, strict=False)
        except ValueError:
            pass  # falls through to hostname treatment
    if net is None:
        try:
            ipaddress.ip_address(line)
            net = ipaddress.ip_network("%s/%s"
                                       % (line, "128" if ":" in line else "32"))
        except ValueError:
            pass
    if net is not None:
        return (any(net.overlaps(e) for e in ECHO_NETS)
                or net.overlaps(ECHO_MAPPED_LOOPBACK_NET))
    return is_echo_entry(line)


def allow_text_echo_entries(kind, text):
    """The allow file's effective echo exemptions, one raw line each (raw
    lines preserved for refusal diagnostics). kind is "hosts" (hosts.allow
    semantics) or "ssrf" (ssrf.allow semantics)."""
    bad = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entry = raw.rstrip("\n")
        if kind == "ssrf":
            hit = ssrf_line_is_echo(line)
        else:
            hit = is_echo_entry(line)
        if hit:
            bad.append(entry)
    return bad


# --- Injector call sites (registry JSON on stdin, like the old heredocs) -----

def _env_aliases():
    return os.environ.get("ECHO_ALIASES", " ".join(ECHO_ALIASES)).split()


def _load_registry():
    try:
        return json.load(sys.stdin)
    except Exception as e:
        print("registry unreadable or invalid JSON: %s" % (e,), file=sys.stderr)
        sys.exit(2)


def _require_key_name():
    """The injector always exports KEY_NAME; a caller that forgets it must
    refuse, not silently check the wrong key (the old heredocs KeyError'd,
    which also refused)."""
    try:
        return os.environ["KEY_NAME"]
    except KeyError:
        print("KEY_NAME is not set -- refusing", file=sys.stderr)
        sys.exit(2)


def cmd_echo_bound_hosts():
    """Print the KEY_NAME registry entry's allowed_hosts items that are
    effective echo exemptions, one per line. Exit 2 when the registry
    cannot be read -- an unverifiable teardown is not a clean teardown."""
    key_name = _require_key_name()
    aliases = _env_aliases()
    reg = _load_registry()
    entry = reg.get(key_name)
    hosts = entry.get("allowed_hosts") if isinstance(entry, dict) else None
    if not isinstance(hosts, list):
        hosts = []
    strs = [str(h) for h in hosts]
    bad = [s for s in strs if is_echo_entry(s, aliases)]
    for s in bad:
        print(s)


def cmd_allowlist_echo_entries(kind, path):
    """Print the allow file's effective echo exemptions, one raw line each.
    Exit 1 on parse failure -- the caller treats an unverifiable file as a
    refusal, never as "no exemptions"."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print("cannot read %s: %s" % (path, e), file=sys.stderr)
        sys.exit(1)
    for b in allow_text_echo_entries(kind, text):
        print(b)


def cmd_assert_key_binding():
    """Assert the KEY_NAME registry entry binds a real inference credential:
    entry present, bearer_header placement, at least one allowed host, none
    of them an echo alias. Exit 1 with a diagnostic otherwise."""
    key_name = _require_key_name()
    aliases = _env_aliases()
    try:
        reg = json.load(sys.stdin)
    except Exception:
        print("registry unreadable or invalid JSON", file=sys.stderr)
        sys.exit(1)
    entry = reg.get(key_name)
    if not isinstance(entry, dict):
        print("%s has no registry entry" % key_name, file=sys.stderr)
        sys.exit(1)
    if entry.get("access_token", {}).get("placement") != "bearer_header":
        print("%s placement is not bearer_header" % key_name, file=sys.stderr)
        sys.exit(1)
    hosts = entry.get("allowed_hosts")
    if not isinstance(hosts, list) or not hosts:
        print("%s is bound to no hosts" % key_name, file=sys.stderr)
        sys.exit(1)
    strs = [str(h) for h in hosts]
    bad = [s for s in strs if is_echo_entry(s, aliases)]
    if bad:
        print("%s still bound to echo host(s): %s" % (key_name, ",".join(bad)),
              file=sys.stderr)
        sys.exit(1)


def main(argv):
    if len(argv) < 2:
        print("usage: proxy_match.py {echo-bound-hosts|allowlist-echo-entries|assert-key-binding}",
              file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "echo-bound-hosts":
        cmd_echo_bound_hosts()
    elif cmd == "allowlist-echo-entries":
        if len(argv) != 4:
            print("usage: proxy_match.py allowlist-echo-entries <hosts|ssrf> <file>",
                  file=sys.stderr)
            return 2
        if argv[2] not in ("hosts", "ssrf"):
            print("kind must be hosts or ssrf", file=sys.stderr)
            return 2
        cmd_allowlist_echo_entries(argv[2], argv[3])
    elif cmd == "assert-key-binding":
        cmd_assert_key_binding()
    else:
        print("unknown subcommand: %s" % cmd, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
