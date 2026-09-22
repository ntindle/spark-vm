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
::1 plus the .localhost subtree. Other loopback forms (127.0.0.2,
::ffff:127.0.0.1) are NOT flagged on the hosts side (the ssrf side does
cover 127.0.0.0/8); this is safe only because the gate fixture's echo
server binds the aliases, never those forms -- a fixture that binds one
would need the set extended here.

Stdlib only. Deployed next to inject-provision-state.sh on the tenant box;
the injector calls it as ``python3 "$HERE/proxy_match.py" <subcommand>``.
"""

import ipaddress
import json
import os
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
        if end != -1:
            h = h[1:end]
    h = h.rstrip(".")
    try:
        h_ip = ipaddress.ip_address(h)
    except ValueError:
        h_ip = None
    if h_ip is None:
        h = h.split(":")[0]
    for entry in entries or []:
        e = str(entry).lower()
        if e.startswith("["):
            end = e.find("]")
            if end != -1:
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
    names."""
    s = str(entry).strip()
    if any(host_in_list(a, [s]) for a in aliases):
        return True
    # ("::1" needs no literal special case anymore: host_in_list matches
    # IP literals as normalized addresses since issue #257, so the alias
    # loop above already covers it.)
    low = s.lower().rstrip(".")
    if low.startswith(".") and low[1:] in tuple(a.lower() for a in aliases):
        return True
    if low.endswith(".localhost"):
        return True
    return False


def ssrf_line_is_echo(line):
    """True when a single ssrf.allow line (stripped, non-blank, non-comment)
    is an effective echo exemption: a CIDR covering 127.0.0.0/8 or ::1/128,
    or an echo hostname under the proxy's own parsing."""
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
        return any(net.overlaps(e) for e in ECHO_NETS)
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
