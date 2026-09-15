"""Transparent credential-swapping addon for mitmdump (runs as swapd).

Replaces hsurr:<name> and hsurr:<name>:<entry> placeholders in request
headers, URL query string, URL path, and text bodies with real secrets
from the secrets dir, but ONLY for hosts listed in the hosts file AND
bound to that credential in the registry (an "allowed_hosts" list per
credential, managed with `cred register <name> --host <h>`). A
credential with no host binding never swaps: fail closed. Everything
else passes through untouched.

Body handling by content type:
- application/json: substituted values are JSON-escaped so quotes and
  backslashes in a secret can't break the document.
- application/x-www-form-urlencoded: the body is parsed as a form,
  placeholder values are swapped, and the form is re-encoded, so
  reserved characters (&, =, %) in a secret can't corrupt the fields.
  Browser-encoded placeholders (hsurr%3A<name>) are decoded by the parse
  and handled identically; literal colons (curl/requests style) work too.
- anything else text: plain substitution.

Headers: Authorization (including HTTP Basic, which is base64-decoded
first) and other headers are swapped, except Referer and Origin, which
are never touched (a swapped Referer would hand the real value to the
server's access log on later requests), and Cookie, which is only
swapped for credentials whose registry placement explicitly names the
Cookie header ({"custom_header": "Cookie"}).

URL path: swapped per path segment. Segments whose decoded form did not
change are left byte-identical, so existing percent-escapes (%25, %2F)
and characters like :/@/~ in unchanged segments survive untouched, and
a substituted value can't break out of its segment.

An entry named "totp" is treated as a base32 seed: the swap inserts the
current RFC 6238 six-digit code (30s step, SHA-1), never the seed.

Secret files: one file per credential name. The "#hsurr:multi" marker
as the file's first non-blank line is the SOLE source of file layout
(finding 35): registry entries describe placements, never file format,
so running `cred register` on a bare-value file can never silently
break its swaps. A marked file holds "entry=value" lines (one per
line); lines that do not match k=v are dropped with a warning. For a
single-value secret an entry suffix matches when absent, when it is
"access_token", or when it is the one entry the registry declares for
that credential; anything else (e.g. hsurr:github:8080) is left alone.

Response scrubbing: for responses from allowlisted hosts, known secret
values in text bodies are replaced with their placeholders, so a
"review your details" page or a key-echoing API can't hand the value
back through the driver's text/screenshot reads. Values under 8
characters are never scrubbed (finding 36: a one-character password
turns "Next" into "Nehsurr:acme:passwordt"); a load-time warning names
the credential, never the value. Registry entries may set
"scrub": false for usernames and emails. TOTP codes are matched as
whole tokens only, so a six-digit code collides with neither prices
nor IDs. Residual, stated not solved: images and binary bodies.

Egress guard: the `server_connect` hook resolves the request host
BEFORE the upstream TCP connect (finding 38), so a refused host never
gets even a SYN — the old `request`-hook check ran after mitmproxy had
already connected. Refused ranges (RFC 1918, loopback, link-local,
CGNAT/tailnet space, 0.0.0.0/8, IETF/benchmark/reserved space,
ULA/link-local/multicast v6; finding 37 adds IPv4-mapped unwrapping)
are killed via data.server.error unless the host is explicitly
allowlisted in the SSRF allow file (hostnames or CIDR literals).
Fresh installs default to deny. On allow, the server address is pinned
to the resolved IP, so the check and the connect use the same answer:
no DNS-rebind race. DNS failure fails open (the connect fails on its
own anyway).

Inference mode (SWAP_INFERENCE_MODE=1): a second mitmdump instance for
obox's LLM calls, with its own secrets dir holding only the provider
key, its own hosts file holding only the provider, its own registry
(populated through cred-registry-set-inference), header-only
placement, and a separate audit log. The provider is never in the main
proxy's hosts file.

Grant scoping (approved half): registry `allowed_methods` and
`allowed_paths` are checked before swapping. Absent means unrestricted
(for migration); an explicit empty list fails closed (finding 41).
Paths are percent-decoded to a fixpoint and dot-segment-normalized
before a segment-aligned prefix match, so /repos/../admin cannot pass
an /repos/ prefix and /repository does not match /repos/. A path that
still contains %, ; or \\ after fixpoint decoding is refused outright
(finding 42): those only reach a path-bound credential as smuggling
tricks for lenient servers (double decoding, path parameters,
backslash separators). This is defense in depth — the server's own
parser has the last word on what a path means. Methods are uppercased.
A path/method-bound credential never swaps where the method or path
can't be verified (CONNECT tunnels, websocket messages).

Audit: every swap is appended to the log file as
    ts=<utc> host=<host> swapped=<matched placeholder>
Refused swaps are logged too:
    ts=<utc> host=<host> refused=hsurr:<name> reason=<why>
Refused egress is logged as:
    ts=<utc> host=<host> refused=egress reason=private-range ip=<ip>
Values are NEVER logged. A placeholder seen for a non-allowlisted host
(including inside base64'd Basic-auth headers) is logged as a warning
AND as a refused= audit line: it is the only signal that a
placeholder went somewhere it should not.
"""

import asyncio
import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import posixpath
import re
import socket
import struct
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path


def _env_path(name, default):
    v = os.environ.get(name)
    return Path(v) if v else Path(default)


# All paths are env-overridable so a second mitmdump instance can run
# as the inference-only proxy (finding 31) with its own secrets dir,
# hosts file, registry, and audit log.
SECRETS_DIR = _env_path("SWAP_SECRETS_DIR", "/home/swapd/secrets")
HOSTS_FILE = _env_path("SWAP_HOSTS_FILE", "/home/swapd/hosts.allow")
REGISTRY_FILE = _env_path("SWAP_REGISTRY_FILE", "/home/swapd/credentials.json")
LOG_FILE = _env_path("SWAP_LOG_FILE", "/home/swapd/swap.log")
SSRF_ALLOW_FILE = _env_path("SWAP_SSRF_FILE", "/home/swapd/ssrf.allow")
# Inference mode (finding 31): swap headers only, never bodies, query,
# paths, or websocket messages — page content in obox's prompts must
# never traverse credential insertion.
INFERENCE_MODE = os.environ.get("SWAP_INFERENCE_MODE") == "1"
# Registry keys with structural meaning; never entry names (finding 34b,
# and the grant-scoping proposal reserves allowed_methods/allowed_paths;
# finding 44 reserves grants before the deferred grant machinery lands).
RESERVED_KEYS = frozenset({"allowed_hosts", "allowed_methods",
                           "allowed_paths", "grants"})
# Explicit marker: a secret file whose first non-blank line is this is
# multi-entry, even when the registry declares no entries (finding 25).
MULTI_MARKER = "#hsurr:multi"
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ENTRY_LINE_RE = re.compile(r"^([A-Za-z0-9_-]+)=(.*)$", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"hsurr:([A-Za-z0-9_-]+)(?::([A-Za-z0-9_-]+))?")
# Percent-encoded form, as sent in application/x-www-form-urlencoded bodies
# (browsers encode ':' as %3A). Case-insensitive on the hex digits.
ENCODED_PLACEHOLDER_RE = re.compile(
    r"hsurr%3A([A-Za-z0-9_-]+)(?:%3A([A-Za-z0-9_-]+))?", re.IGNORECASE)
# Headers that must never be swapped: a substituted Referer/Origin would
# hand the real value to the server's logs on every later request.
NEVER_SWAP_HEADERS = frozenset({"referer", "origin"})

log = logging.getLogger(__name__)


def _totp_code(seed, at=None):
    """Current RFC 6238 TOTP code for a base32 seed: 6 digits, 30s step,
    SHA-1. Raises ValueError/binascii.Error on a bad seed."""
    if at is None:
        at = time.time()
    s = seed.strip()
    key = base64.b32decode(s.upper() + "=" * (-len(s) % 8))
    counter = struct.pack(">Q", int(at) // 30)
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % 1000000).zfill(6)


def _host_in_list(host, entries):
    """Match host against exact names or leading-dot subdomain entries,
    the same shape dynamic_credentials.ensure_allowed_url takes."""
    h = (host or "").lower().split(":")[0]
    for entry in entries or []:
        e = str(entry).lower()
        if h == e or (e.startswith(".") and h.endswith(e)):
            return True
    return False


def _normalize_path(raw):
    """Percent-decode to a fixpoint, then dot-segment-normalize a
    request path (grant scoping, finding 42): /repos/../admin must not
    pass an /repos/ prefix, %2e%2e encodings must not smuggle dot
    segments past the check, and %252e%252e (double-encoded) must not
    survive as %2e%2e for a server that decodes twice."""
    try:
        p = urllib.parse.urlsplit(raw).path
    except Exception:
        p = raw or ""
    prev = None
    while p != prev:
        prev, p = p, urllib.parse.unquote(p)
    if not p.startswith("/"):
        p = "/" + p
    return posixpath.normpath(p) or "/"


def _path_allowed(norm_path, prefixes):
    """Segment-aligned prefix match: /repos/ matches /repos and
    /repos/x but not /repository."""
    for pre in prefixes or []:
        pp = _normalize_path(str(pre))
        if norm_path == pp or norm_path.startswith(pp.rstrip("/") + "/"):
            return True
    return False


# ------------------------------------------------------------------ SSRF

# Ranges refused by default (findings 29, 37): RFC 1918 private,
# loopback, link-local, CGNAT and other carrier space, 0.0.0.0/8,
# IETF protocol assignments, benchmarking space, reserved space, and
# ULA/link-local/multicast v6.
_PRIVATE_NETS = tuple(ipaddress.ip_network(c) for c in (
    "0.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
    "192.0.0.0/24", "198.18.0.0/15", "224.0.0.0/4", "240.0.0.0/4",
    "::1/128", "fc00::/7", "fe80::/10", "ff00::/8",
))
_DNS_TTL = 60
# Response scrubbing floor (finding 36): values under this length are
# never scrubbed, because short secrets mangle pages.
_MIN_SCRUB_LEN = 8


def _normalize_ip(ip):
    """Parse an IP literal, unwrapping IPv4-mapped IPv6 (finding 37):
    ::ffff:127.0.0.1 reaches localhost on Linux and must be judged as
    127.0.0.1, not as a global unicast v6 address. Returns None for
    garbage."""
    try:
        addr = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return None
    mapped = getattr(addr, "ipv4_mapped", None)
    return mapped if mapped is not None else addr


def _is_private_ip(ip):
    addr = _normalize_ip(ip)
    if addr is None:
        return False
    return bool(addr.is_unspecified
                or any(addr in net for net in _PRIVATE_NETS))


def _parse_ssrf_allow(text):
    """Parse the ssrf allow file (finding 29). Lines are hostnames
    (exact or leading-dot subdomain entries, matched with
    _host_in_list) or CIDR literals (matched against resolved IPs).
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


class SwapAddon:
    def __init__(self):
        self.inference_mode = INFERENCE_MODE
        self.secrets = {}
        self.hosts = []
        self.registry = {}
        self.ssrf_hosts = []
        self.ssrf_nets = []
        self._store_mtime = None
        self._hosts_mtime = None
        self._registry_mtime = None
        self._ssrf_mtime = None
        self._dns_cache = {}
        self._load()

    @staticmethod
    def _basic_decoded(value):
        """Decode an HTTP Basic Authorization header to "user:password".

        Returns None if the value is not valid Basic auth.
        """
        scheme, _, b64 = value.partition(" ")
        if scheme.lower() != "basic" or not b64.strip():
            return None
        try:
            return base64.b64decode(b64.strip(), validate=True).decode("utf-8")
        except (binascii.Error, ValueError, UnicodeDecodeError):
            return None

    def _swap_basic_auth(self, value, host, method=None, path=None):
        """Swap placeholders inside an HTTP Basic Authorization header.

        Clients (git, curl -u) base64 the whole "user:password" pair, so a
        placeholder used as the password is invisible to plain text
        matching. Decode, swap, re-encode. Returns the original value if
        there is nothing to do or the value isn't valid Basic auth.
        """
        decoded = self._basic_decoded(value)
        if decoded is None:
            return value
        new_decoded = self._swap_text(decoded, host, method, path)
        if new_decoded == decoded:
            return value
        return "Basic " + base64.b64encode(
            new_decoded.encode("utf-8")).decode("ascii")

    # ------------------------------------------------------------------
    def _declared_entries(self, name):
        """Entry names the registry declares for a credential (finding 25).

        Reserved structural keys (allowed_hosts, ...) are never entries.
        """
        spec = self.registry.get(name)
        if not isinstance(spec, dict):
            return []
        return [k for k in spec if k not in RESERVED_KEYS]

    def _load_secret_file(self, path):
        """Read one secret file (finding 35).

        The #hsurr:multi marker as the file's first non-blank line is
        the SOLE source of file layout. Registry entries describe
        placements, never file format: a bare-value file stays a single
        value even when the registry declares entries (e.g. the default
        access_token entry `cred register` writes), so registering a
        host binding can never silently break a credential's swaps.
        Lines that do not match k=v are dropped with a warning
        (finding 40b), naming the line number but never the content.
        """
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            log.warning("swap: cannot read secret %s: %s", path.name, e)
            return None
        lines = [l for l in text.splitlines() if l.strip()]
        if not lines or lines[0].strip() != MULTI_MARKER:
            return text.strip()
        values = {}
        for lineno, line in enumerate(lines[1:], start=2):
            m = ENTRY_LINE_RE.match(line)
            if m:
                values[m.group(1)] = m.group(2)
            else:
                log.warning("swap: secret %s line %d is not k=v; dropped",
                            path.name, lineno)
        return values

    def _load(self):
        registry = {}
        try:
            if REGISTRY_FILE.is_file():
                data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    registry = data
                else:
                    log.warning("swap: registry is not a JSON object; ignoring")
        except (OSError, ValueError) as e:
            log.warning("swap: cannot read registry: %s", e)
        self.registry = registry
        secrets = {}
        try:
            if SECRETS_DIR.is_dir():
                for p in SECRETS_DIR.iterdir():
                    if p.is_file() and NAME_RE.match(p.name):
                        v = self._load_secret_file(p)
                        if v is not None:
                            secrets[p.name] = v
        except OSError as e:
            log.warning("swap: cannot list secrets dir: %s", e)
        # Finding 36: values under _MIN_SCRUB_LEN are never scrubbed
        # from responses. Warn here (naming the credential, never the
        # value) so a short secret is a visible configuration problem,
        # not a silent gap. Entries opted out with "scrub": false are
        # skipped — the warning is about scrubbing, which is already
        # off for them (nit, round 4).
        for name, val in secrets.items():
            entries = (val.items() if isinstance(val, dict)
                       else ((None, val),))
            if any(v and len(v) < _MIN_SCRUB_LEN
                   and not self._scrub_opted_out(name, e)
                   for e, v in entries):
                log.warning(
                    "swap: secret %r has a value shorter than %d chars; "
                    "response scrubbing is disabled for it", name,
                    _MIN_SCRUB_LEN)
        hosts = []
        try:
            if HOSTS_FILE.is_file():
                for line in HOSTS_FILE.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        hosts.append(line.lower())
        except OSError as e:
            log.warning("swap: cannot read hosts.allow: %s", e)
        ssrf_hosts, ssrf_nets = [], []
        try:
            if SSRF_ALLOW_FILE.is_file():
                ssrf_hosts, ssrf_nets = _parse_ssrf_allow(
                    SSRF_ALLOW_FILE.read_text(encoding="utf-8"))
        except OSError as e:
            log.warning("swap: cannot read ssrf.allow: %s (default deny)",
                        e)
        self.secrets = secrets
        self.hosts = hosts
        self.ssrf_hosts = ssrf_hosts
        self.ssrf_nets = ssrf_nets
        self._store_mtime = self._mtime(SECRETS_DIR)
        self._hosts_mtime = self._mtime(HOSTS_FILE)
        self._registry_mtime = self._mtime(REGISTRY_FILE)
        self._ssrf_mtime = self._mtime(SSRF_ALLOW_FILE)

    @staticmethod
    def _mtime(p):
        try:
            return p.stat().st_mtime_ns
        except OSError:
            return None

    def _maybe_reload(self):
        # Pick up newly installed secrets / host / registry / ssrf changes
        # without a restart.
        if (self._mtime(SECRETS_DIR) != self._store_mtime
                or self._mtime(HOSTS_FILE) != self._hosts_mtime
                or self._mtime(REGISTRY_FILE) != self._registry_mtime
                or self._mtime(SSRF_ALLOW_FILE) != self._ssrf_mtime):
            self._load()

    # ------------------------------------------------------------------
    def _host_allowed(self, host):
        return _host_in_list(host, self.hosts)

    def _credential_allows_request(self, name, host, method, path):
        """Registry binding check for one request (grant scoping, approved
        half). Host binding is fail closed. allowed_methods and
        allowed_paths are static limits: absent means unrestricted (for
        migration), but an explicit empty list fails closed (finding
        41) — removing the last method must not silently unlimit the
        credential. Returns (ok, reason)."""
        reg = getattr(self, "registry", None) or {}
        spec = reg.get(name)
        if not isinstance(spec, dict):
            return False, "unbound-host"
        if not _host_in_list(host, spec.get("allowed_hosts")):
            return False, "unbound-host"
        methods = spec.get("allowed_methods")
        if methods is not None:
            allowed = {str(m).upper() for m in methods}
            if (method or "").upper() not in allowed:
                return False, "method-not-allowed"
        prefixes = spec.get("allowed_paths")
        if prefixes is not None:
            if (method or "").upper() == "CONNECT":
                # the proxy cannot see inside the tunnel, so a
                # path-bound credential never swaps on a CONNECT
                return False, "path-not-verifiable"
            norm = _normalize_path(path or "/")
            if "%" in norm or ";" in norm or "\\" in norm:
                # Finding 42: after fixpoint decoding these can only be
                # smuggling tricks for lenient servers (double-decode
                # residue, path parameters, backslash separators).
                return False, "path-not-allowed"
            if not _path_allowed(norm, prefixes):
                return False, "path-not-allowed"
        return True, ""

    def _cookie_swap_names(self):
        """Credential names whose registry placement explicitly targets the
        Cookie header ({"custom_header": "Cookie"}). Only these may swap
        inside Cookie headers."""
        names = set()
        reg = getattr(self, "registry", None) or {}
        for name, spec in reg.items():
            if not isinstance(spec, dict):
                continue
            for entry_spec in spec.values():
                if not isinstance(entry_spec, dict):
                    continue  # e.g. the allowed_hosts list
                placement = entry_spec.get("placement")
                if (isinstance(placement, dict)
                        and str(placement.get("custom_header", "")).lower()
                        == "cookie"):
                    names.add(name)
                    break
        return names

    def _resolve(self, name, entry, host, method=None, path=None):
        """Return the secret value for name/entry on this request, or None
        to leave the placeholder untouched."""
        val = self.secrets.get(name)
        if val is None:
            return None
        ok, reason = self._credential_allows_request(name, host, method,
                                                     path)
        if not ok:
            log.warning("swap: refusing swap of %r for %s %s: %s", name,
                        method or "?", host, reason)
            self._audit_refused(host, name, reason)
            return None
        if isinstance(val, dict):
            e = entry or "access_token"
            if e == "totp":
                seed = val.get("totp")
                if seed is None:
                    return None
                try:
                    return _totp_code(seed)
                except (ValueError, binascii.Error) as ex:
                    log.warning("swap: bad totp seed for %r: %s", name, ex)
                    return None
            return val.get(e)
        # single-value secret (finding 35): the whole file is the value.
        # An entry suffix matches when absent, when "access_token"
        # (hsurr:github:8080 must keep its :8080), or when it is the one
        # entry the registry declares for this credential.
        if entry is None or entry == "access_token":
            return val
        declared = self._declared_entries(name)
        if len(declared) == 1 and declared[0] == entry:
            return val
        self._audit_refused(host, name, "unknown-entry")
        return None

    def _audit(self, host, matched):
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write("ts=%s host=%s swapped=%s\n" % (ts, host, matched))
        except OSError as e:
            log.warning("swap: cannot write audit log: %s", e)

    def _audit_refused(self, host, name, reason):
        """Record a placeholder that was deliberately NOT swapped (finding
        22): the binding verdict leaves a trail even when nothing leaks."""
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write("ts=%s host=%s refused=hsurr:%s reason=%s\n"
                        % (ts, host, name, reason))
        except OSError as e:
            log.warning("swap: cannot write audit log: %s", e)

    def _swap_text(self, text, host, method=None, path=None, encode=None,
                   allow=None):
        """Substitute placeholders in text.

        method/path: the request's method and path, for the registry's
            allowed_methods / allowed_paths checks (grant scoping).
        encode: optional transform applied to each substituted value only
            (e.g. JSON-escaping), never to the surrounding text.
        allow: optional set of credential names permitted to swap; other
            names' placeholders are left untouched (the Cookie policy).
        """
        def repl(m):
            name, entry = m.group(1), m.group(2) or "access_token"
            if allow is not None and name not in allow:
                return m.group(0)
            v = self._resolve(name, entry, host, method, path)
            if v is None:
                return m.group(0)  # unknown name/entry or refused request
            self._audit(host, m.group(0))
            return encode(v) if encode else v
        return PLACEHOLDER_RE.sub(repl, text)

    def _swap_json_text(self, text, host, method=None, path=None):
        """Substitute placeholders in a JSON body, JSON-escaping each value
        so quotes/backslashes in a secret can't break the document."""
        return self._swap_text(
            text, host, method, path, encode=lambda v: json.dumps(v)[1:-1])

    def _swap_urlencoded(self, text, host, method=None, path=None):
        """Swap percent-encoded placeholders (hsurr%3A<name>) found in
        application/x-www-form-urlencoded bodies. Substituted values are
        re-encoded so reserved characters can't corrupt the form. Used as
        the fallback for bodies with no parseable fields; the normal path
        is _swap_form_body."""
        def repl(m):
            name, entry = m.group(1), m.group(2) or "access_token"
            v = self._resolve(name, entry, host, method, path)
            if v is None:
                return m.group(0)  # unknown name/entry: leave untouched
            self._audit(host, "hsurr:%s%s"
                        % (name, (":" + entry) if m.group(2) else ""))
            return urllib.parse.quote(v, safe="")
        return ENCODED_PLACEHOLDER_RE.sub(repl, text)

    def _swap_form_body(self, text, host, method=None, path=None):
        """Swap placeholders in an application/x-www-form-urlencoded body.

        The body is parsed as a form, placeholder values are swapped, and
        the form is re-encoded, so reserved characters in a secret can't
        corrupt the fields. Browser-encoded placeholders (hsurr%3A<name>)
        are decoded by the parse and handled identically; literal colons
        (curl/requests style) work too. Bodies with no swappable fields
        fall back to the encoded-placeholder regex."""
        pairs = urllib.parse.parse_qsl(text, keep_blank_values=True)
        new_pairs = [(k, self._swap_text(v, host, method, path))
                     for k, v in pairs]
        if new_pairs != pairs:
            return urllib.parse.urlencode(new_pairs)
        return self._swap_urlencoded(text, host, method, path)

    # ------------------------------------------------------------------
    def _warn_if_placeholder(self, flow, host):
        """Warn (and audit) when a placeholder is seen for a host that may
        not swap it (findings 22, 40a).

        The old version only matched the literal bytes b"hsurr:" in the
        body, so a placeholder inside a base64'd Basic-auth header — the
        exact case git uses — never triggered it. This version also
        inspects decoded Basic auth (the same helper the swap path
        uses), the percent-encoded form in the body, and the URL path.
        Every distinct placeholder name becomes a refused= audit line:
        a journal warning alone is too easy to miss, and this is the
        only signal that a placeholder went somewhere it should not.
        """
        hay = b"hsurr:"
        hay_enc = b"hsurr%3a"  # urlencoded forms percent-encode the colon
        chunks = [(flow.request.content or b"").lower()]
        for k in flow.request.headers.keys():
            for v in flow.request.headers.get_all(k):
                chunks.append(v.encode("utf-8", "ignore"))
                if k.lower() == "authorization":
                    decoded = self._basic_decoded(v)
                    if decoded:
                        chunks.append(decoded.encode("utf-8", "ignore"))
        chunks.append(flow.request.path.encode("utf-8", "ignore"))
        blob = b"\n".join(chunks).lower()
        if hay not in blob and hay_enc not in blob:
            return
        log.warning(
            "swap: placeholder seen for non-allowlisted host %s; "
            "passing through unchanged", host)
        seen = set()
        text = blob.decode("utf-8", "ignore")
        for rx in (PLACEHOLDER_RE, ENCODED_PLACEHOLDER_RE):
            for m in rx.finditer(text):
                if m.group(1) not in seen:
                    seen.add(m.group(1))
                    self._audit_refused(host, m.group(1),
                                        "host-not-allowlisted")

    # ------------------------------------------------------------------ SSRF

    async def _resolve_ips(self, host):
        """Resolve host to IPs with a small TTL cache (finding 29).

        Finding 45: the lookup runs through the event loop's resolver
        instead of blocking getaddrinfo — server_connect runs on
        mitmproxy's asyncio loop, and a slow resolver must not stall
        every connection through both proxies.

        Returns None on DNS failure: fail open, since the request cannot
        complete upstream anyway.
        """
        now = time.time()
        cached = self._dns_cache.get(host)
        if cached and cached[0] > now:
            return cached[1]
        try:
            loop = asyncio.get_running_loop()
            infos = await loop.getaddrinfo(host, None,
                                           type=socket.SOCK_STREAM)
        except socket.gaierror:
            ips = None
        except Exception:
            ips = None
        else:
            ips = []
            for info in infos:
                ip = info[4][0]
                if ip not in ips:
                    ips.append(ip)
        self._dns_cache[host] = (now + _DNS_TTL, ips)
        # keep the cache small: it is only a latency optimization
        if len(self._dns_cache) > 1024:
            self._dns_cache.clear()
        return ips

    def _ip_refused(self, host, parsed):
        """True if this resolved IP must not be connected to (findings 29,
        37): refused ranges by default, unless the ssrf allow file names
        the host or a CIDR covering the IP."""
        if not (parsed.is_unspecified
                or any(parsed in net for net in _PRIVATE_NETS)):
            return False
        if _host_in_list(host, self.ssrf_hosts):
            return False
        return not any(parsed in net for net in self.ssrf_nets)

    def _audit_ssrf_refused(self, host, ip, reason):
        """Record refused egress (finding 38): like a refused swap, the
        verdict leaves a trail even though nothing was sent."""
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write("ts=%s host=%s refused=egress reason=%s ip=%s\n"
                        % (ts, host, reason, ip))
        except OSError as e:
            log.warning("swap: cannot write audit log: %s", e)

    async def server_connect(self, data):
        """Egress guard (findings 29, 37, 38).

        Runs BEFORE the upstream TCP connect — the old `request`-hook
        check ran after mitmproxy had already connected, which was
        enough to port-scan the tailnet. The host is resolved here;
        refused IPs kill the connection via data.server.error, and on
        allow the server address is pinned to the resolved IP so the
        check and the connect use the same answer (no DNS-rebind race).
        SNI is unaffected: tlsconfig sets it from the client's hello,
        not from the pinned address.

        A coroutine hook (finding 45): mitmproxy awaits it, so the DNS
        lookup below never blocks the event loop.

        Hook signature verified against the mitmproxy in the deploy
        venv (12.2.3): server_connect(data: ServerConnectionHookData).
        """
        self._maybe_reload()
        server = getattr(data, "server", None)
        addr = getattr(server, "address", None)
        if not addr:
            return
        host = addr[0]
        ips = await self._resolve_ips(host)
        if ips is None:
            return  # DNS failure fails open; the connect fails on its own
        allowed_ip, refused_ip = None, None
        for ip in ips:
            parsed = _normalize_ip(ip)
            if parsed is None:
                continue
            if self._ip_refused(host, parsed):
                if refused_ip is None:
                    refused_ip = str(parsed)
                continue
            allowed_ip = str(parsed)
            break
        if allowed_ip is None:
            log.warning("swap: refusing egress to %s: private-range (ip=%s)",
                        host, refused_ip)
            self._audit_ssrf_refused(host, refused_ip, "private-range")
            server.error = "swap-proxy: egress refused (private-range)"
            return
        try:
            server.address = (allowed_ip, addr[1])
        except Exception as e:
            log.warning("swap: could not pin server address for %s: %s",
                        host, e)

    def _swap_headers(self, req, host, method=None, path=None):
        # headers: never swap Referer/Origin; Cookie only when a registry
        # placement explicitly names the Cookie header
        for key in list(req.headers.keys()):
            kl = key.lower()
            if kl in NEVER_SWAP_HEADERS:
                continue
            vals = req.headers.get_all(key)
            if kl == "authorization":
                new_vals = [self._swap_basic_auth(v, host, method, path)
                            for v in vals]
                # fall back to plain-text swap (e.g. Bearer <placeholder>)
                new_vals = [self._swap_text(v, host, method, path)
                            if nv == v else nv
                            for v, nv in zip(vals, new_vals)]
            elif kl == "cookie":
                allowed = self._cookie_swap_names()
                new_vals = [self._swap_text(v, host, method, path,
                                            allow=allowed)
                            for v in vals]
            else:
                new_vals = [self._swap_text(v, host, method, path)
                            for v in vals]
            if new_vals != vals:
                req.headers.set_all(key, new_vals)

    def _request_inference(self, req, host, method=None, path=None):
        """Inference proxy request path (finding 31): headers only.

        obox's prompts can contain whole pages; they must never traverse
        credential insertion in bodies, query strings, paths, or
        websocket messages. The inference registry's placement is
        header-only anyway — this makes the guarantee structural.
        """
        self._swap_headers(req, host, method, path)

    def request(self, flow):
        self._maybe_reload()
        req = flow.request
        host = req.pretty_host
        # Egress is guarded in server_connect (before the TCP connect);
        # here we only gate swapping on the hosts file.
        if not self._host_allowed(host):
            self._warn_if_placeholder(flow, host)
            return
        method = getattr(req, "method", None)
        path = getattr(req, "path", "/")
        if self.inference_mode:
            self._request_inference(req, host, method, path)
            return
        self._swap_headers(req, host, method, path)
        # query string (percent-decoded values; re-encoded on assignment)
        q_items = list(req.query.items(multi=True))
        if q_items:
            new_q = [(k, self._swap_text(v, host, method, path))
                     for k, v in q_items]
            query_changed = new_q != q_items
        else:
            new_q, query_changed = q_items, False
        # path: swap per segment. Segments whose decoded form did not
        # change are left byte-identical (finding 34a), so existing
        # escapes and characters like :/@/~ in unchanged segments survive
        # untouched, and a substituted value can't leave its segment.
        raw_path, _, _ = req.path.partition("?")
        segments = raw_path.split("/")
        new_segments = []
        path_changed = False
        for seg in segments:
            dec = urllib.parse.unquote(seg)
            new_dec = self._swap_text(dec, host, method, path)
            if new_dec != dec:
                path_changed = True
                new_segments.append(urllib.parse.quote(new_dec, safe=""))
            else:
                new_segments.append(seg)
        if path_changed or query_changed:
            new_path = "/".join(new_segments) if path_changed else raw_path
            if new_q:
                req.path = new_path + "?" + urllib.parse.urlencode(new_q)
            else:
                req.path = new_path
        # body (text only), handled per content type
        if req.content:
            try:
                text = req.content.decode("utf-8")
            except UnicodeDecodeError:
                return  # binary body: headers/query/path already handled
            ctype = req.headers.get("content-type", "")
            if "application/json" in ctype:
                new_text = self._swap_json_text(text, host, method, path)
            elif "application/x-www-form-urlencoded" in ctype:
                new_text = self._swap_form_body(text, host, method, path)
            else:
                new_text = self._swap_text(text, host, method, path)
            if new_text != text:
                req.content = new_text.encode("utf-8")

    def websocket_message(self, flow):
        self._maybe_reload()
        host = flow.request.pretty_host if flow.request else ""
        if not self._host_allowed(host):
            return
        if self.inference_mode:
            return  # never: page content must not traverse insertion
        msgs = flow.websocket.messages if flow.websocket else None
        if not msgs:
            return
        msg = msgs[-1]
        if msg.is_binary:
            return
        try:
            text = msg.content.decode("utf-8")
        except UnicodeDecodeError:
            return
        new_text = self._swap_text(text, host)
        if new_text != text:
            msg.content = new_text.encode("utf-8")

    # ---------------------------------------------------------------- response

    _SCRUBBABLE_TYPES = ("text/", "application/json",
                         "application/javascript", "application/xml",
                         "application/x-www-form-urlencoded")
    _MAX_SCRUB_BYTES = 5 * 1024 * 1024

    def _is_scrubbable_content_type(self, ctype):
        c = (ctype or "").split(";")[0].strip().lower()
        if not c:
            return True  # unknown: try decoding, skip on failure
        if c.startswith(self._SCRUBBABLE_TYPES):
            return True
        return c.endswith(("+json", "+xml"))

    def _scrub_opted_out(self, name, entry):
        """True when the registry sets "scrub": false for this entry
        (finding 36). Single-value secrets carry the opt-out on the
        "access_token" entry spec — there is no entry None (finding
        43)."""
        spec = (getattr(self, "registry", None) or {}).get(name)
        if not isinstance(spec, dict):
            return False
        entry_spec = spec.get(entry if entry is not None else "access_token")
        return (isinstance(entry_spec, dict)
                and entry_spec.get("scrub") is False)

    def _scrubbable_entry(self, name, entry, value):
        """Whether one entry's value may be scrubbed from responses
        (finding 36): values under _MIN_SCRUB_LEN are never scrubbed,
        and the registry may set "scrub": false for usernames/emails."""
        if not value or len(value) < _MIN_SCRUB_LEN:
            return False
        return not self._scrub_opted_out(name, entry)

    def _secret_replacements(self):
        """(value, placeholder, whole_token) triples for response
        scrubbing (findings 4, 36), longest value first so overlapping
        secrets replace correctly.

        totp seeds are never returned; the current code is included
        because the agent typed that placeholder into the page and a
        "review your details" screen may echo it back. Codes are
        whole_token: a six-digit code collides with prices and IDs, so
        it is only replaced as a standalone token."""
        triples = []
        for name, val in (self.secrets or {}).items():
            if isinstance(val, dict):
                for entry, v in val.items():
                    if entry == "totp":
                        try:
                            code = _totp_code(v)
                        except (ValueError, binascii.Error):
                            continue
                        triples.append((code, "hsurr:%s:totp" % name, True))
                        continue
                    if self._scrubbable_entry(name, entry, v):
                        triples.append((v, "hsurr:%s:%s" % (name, entry),
                                        False))
            elif self._scrubbable_entry(name, None, val):
                triples.append((val, "hsurr:%s" % name, False))
        triples.sort(key=lambda t: len(t[0]), reverse=True)
        return triples

    def response(self, flow):
        """Scrub known secret values out of text responses from allowlisted
        hosts (finding 4), replacing each with its placeholder. Images and
        binary bodies are a stated residual risk, not a solved one.

        The hook buffers the whole body (finding 40d): obox must not
        depend on streamed provider responses through this proxy."""
        self._maybe_reload()
        req = flow.request
        host = req.pretty_host if req else ""
        if not self._host_allowed(host):
            return
        resp = flow.response
        if resp is None:
            return
        if not self._is_scrubbable_content_type(
                resp.headers.get("content-type", "")):
            return
        # finding 40c: check the byte size BEFORE decoding the body
        if len(resp.content or b"") > self._MAX_SCRUB_BYTES:
            return
        try:
            text = resp.text
        except Exception:
            return  # undecodable: skip
        new_text = text
        for value, placeholder, whole_token in self._secret_replacements():
            if whole_token:
                new_text = re.sub(r"(?<!\d)" + re.escape(value) + r"(?!\d)",
                                  placeholder, new_text)
            elif value in new_text:
                new_text = new_text.replace(value, placeholder)
        if new_text != text:
            resp.text = new_text
            try:
                if "content-length" in resp.headers:
                    resp.headers["content-length"] = str(len(resp.content))
            except Exception:
                pass


addons = [SwapAddon()]
