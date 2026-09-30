#!/usr/bin/env python3
"""host_match.py -- the single source of truth for proxy host matching.

Issue #261. The enforcement matcher (exact/leading-dot host entries,
IP-literal normalization) and the ssrf allow-file parser used to live in
two places: proxy/swap_addon.py (the enforcing mitmproxy addon) and a
byte-faithful mirror in harness/proxy_match.py (the provision-time
injector's echo-detection layer), with a drift tripwire asserting the two
sides agreed. Mirror + tripwire is second-best to divergence-by-
construction: both sides now import these two functions from this module.

Stdlib only (ipaddress). No import-time side effects: the module top level
is constants plus these two function definitions, so it is safe to import
from the mitmproxy addon, the injector, and the test suites alike.

Deployment: the file sits next to its importers. In the repo checkout
that is proxy/ next to proxy/swap_addon.py; proxy/deploy.sh installs it
to /home/swapd/ next to the standalone swap_addon.py (the standalone
deploy adds the script's own directory to sys.path, exactly like the
VERSION-reader helper); the provision bundle ships it as
proxy/host_match.py, a sibling of the harness/ tree the injector's
require_proxy_match check verifies.
"""

import ipaddress


def host_in_list(host, entries):
    """Match host against exact names or leading-dot subdomain entries,
    the same shape dynamic_credentials.ensure_allowed_url takes.

    Trailing dots are stripped on both sides: DNS treats
    "example.com." as identical to "example.com", so without this a
    one-character suffix bypassed the ssrf.deny name entries (the
    finding-47 self-peer guard).

    IP literals (v4 and v6) are compared as normalized addresses, never
    run through the hostname rules: splitting "::1" on ":" yields ""
    and made every IPv6 literal unmatchable (issue #257 -- a "::1"
    allowed_hosts entry was dead config, and enforcement checks built
    on this function were blind to ::1). A single bracket pair is
    stripped first ("[::1]", "[::1]:8080"); a trailing dot is stripped
    too, so "::1." matches "::1". Hostname entries never match an IP
    literal host, and CIDR entries never match here (they are
    parse_ssrf_allow's nets, not host_in_list's entries)."""
    h = (host or "").lower()
    # Bracketed IPv6 literal, optionally with a :port (urllib's
    # .hostname already strips these, but the matcher is also called
    # directly with raw URL hosts).
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
    # Dot-strip AFTER the port strip: "example.com.:8080" -> "example.com".
    # (Doing it before reintroduced a trailing-dot bypass of ssrf.deny
    # name entries for the host:port form -- see the finding-47 note
    # above.)
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
    """Parse the ssrf allow file (finding 29). Lines are hostnames
    (exact or leading-dot subdomain entries, matched with
    host_in_list) or CIDR literals (matched against resolved IPs).
    A fresh install ships this file empty: default deny."""
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
