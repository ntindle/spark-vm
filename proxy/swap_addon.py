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

Secret files: one file per credential name. Either the whole file is the
single value, or the file holds "entry=value" lines (one per line) for
multi-entry credentials. Single-vs-multi is decided by the registry's
entry list for that credential, or by a "#hsurr:multi" marker as the
file's first line — never by sniffing the content, so a single-value
secret whose value looks like "k=v" is never misread. For a
single-value secret an entry suffix only matches when it is absent or
"access_token"; anything else (e.g. hsurr:github:8080) is left alone.

Response scrubbing: for responses from allowlisted hosts, known secret
values in text bodies are replaced with their placeholders, so a
"review your details" page or a key-echoing API can't hand the value
back through the driver's text/screenshot reads. Residual, stated not
solved: images and binary bodies.

Egress guard: the request host is resolved and requests to private
ranges (RFC 1918, loopback, link-local, CGNAT/tailnet space) are
refused with 403 unless the host is explicitly allowlisted in the SSRF
allow file (hostnames or CIDR literals). Fresh installs default to
deny. DNS failure fails open (the request can't complete upstream
anyway); DNS-rebind races between the check and the upstream connect
are a stated residual.

Inference mode (SWAP_INFERENCE_MODE=1): a second mitmdump instance for
obox's LLM calls, with its own secrets dir holding only the provider
key, its own hosts file holding only the provider, header-only
placement, and a separate audit log. The provider is never in the main
proxy's hosts file.

Audit: every swap is appended to the log file as
    ts=<utc> host=<host> swapped=<matched placeholder>
Refused swaps are logged too:
    ts=<utc> host=<host> refused=hsurr:<name> reason=<why>
Values are NEVER logged. A placeholder seen for a non-allowlisted host
(including inside base64'd Basic-auth headers) is logged as a warning:
it is the only signal that a placeholder went somewhere it should not.
"""

import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import socket
import struct
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

try:
    from mitmproxy import http as _mp_http
except Exception:  # unit tests run without mitmproxy installed
    _mp_http = None


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
# and the grant-scoping proposal reserves allowed_methods/allowed_paths).
RESERVED_KEYS = frozenset({"allowed_hosts", "allowed_methods", "allowed_paths"})
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


# ------------------------------------------------------------------ SSRF

# Ranges refused by default (finding 29): RFC 1918 private, loopback,
# link-local, CGNAT and other carrier space, and ULA/link-local v6.
_PRIVATE_NETS = tuple(ipaddress.ip_network(c) for c in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10",
    "127.0.0.0/8", "169.254.0.0/16", "224.0.0.0/4",
    "::1/128", "fc00::/7", "fe80::/10", "ff00::/8",
))
_DNS_TTL = 60


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


def _is_private_ip(ip):
    try:
        addr = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    return any(addr in net for net in _PRIVATE_NETS)


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

    def _swap_basic_auth(self, value, host):
        """Swap placeholders inside an HTTP Basic Authorization header.

        Clients (git, curl -u) base64 the whole "user:password" pair, so a
        placeholder used as the password is invisible to plain text
        matching. Decode, swap, re-encode. Returns the original value if
        there is nothing to do or the value isn't valid Basic auth.
        """
        decoded = self._basic_decoded(value)
        if decoded is None:
            return value
        new_decoded = self._swap_text(decoded, host)
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

    def _load_secret_file(self, path, entries):
        """Read one secret file (finding 25).

        Single value unless the registry declares entries for this
        credential or the file's first non-blank line is the
        #hsurr:multi marker. Content is never sniffed for "k=v": a
        single-value secret whose value happens to contain "=" stays a
        single value.
        """
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            log.warning("swap: cannot read secret %s: %s", path.name, e)
            return None
        lines = [l for l in text.splitlines() if l.strip()]
        multi = bool(entries) or (lines and lines[0].strip() == MULTI_MARKER)
        if multi:
            if lines and lines[0].strip() == MULTI_MARKER:
                lines = lines[1:]
            return {m.group(1): m.group(2)
                    for m in (ENTRY_LINE_RE.match(l) for l in lines) if m}
        return text.strip()

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
                        v = self._load_secret_file(p,
                                                   self._declared_entries(p.name))
                        if v is not None:
                            secrets[p.name] = v
        except OSError as e:
            log.warning("swap: cannot list secrets dir: %s", e)
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

    def _credential_allows_host(self, name, host):
        """Per-credential host binding from the registry. Fail closed: a
        credential with no allowed_hosts entry never swaps."""
        reg = getattr(self, "registry", None) or {}
        spec = reg.get(name)
        if not isinstance(spec, dict):
            return False
        return _host_in_list(host, spec.get("allowed_hosts"))

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

    def _resolve(self, name, entry, host):
        """Return the secret value for name/entry on this host, or None to
        leave the placeholder untouched."""
        val = self.secrets.get(name)
        if val is None:
            return None
        if not self._credential_allows_host(name, host):
            log.warning("swap: credential %r is not bound to host %r; "
                        "leaving placeholder", name, host)
            self._audit_refused(host, name, "unbound-host")
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
        # single-value secret: an entry suffix only matches when absent
        # or "access_token" (hsurr:github:8080 must keep its :8080)
        if entry and entry != "access_token":
            return None
        return val

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

    def _swap_text(self, text, host, encode=None, allow=None):
        """Substitute placeholders in text.

        encode: optional transform applied to each substituted value only
            (e.g. JSON-escaping), never to the surrounding text.
        allow: optional set of credential names permitted to swap; other
            names' placeholders are left untouched (the Cookie policy).
        """
        def repl(m):
            name, entry = m.group(1), m.group(2) or "access_token"
            if allow is not None and name not in allow:
                return m.group(0)
            v = self._resolve(name, entry, host)
            if v is None:
                return m.group(0)  # unknown name/entry or unbound host
            self._audit(host, m.group(0))
            return encode(v) if encode else v
        return PLACEHOLDER_RE.sub(repl, text)

    def _swap_json_text(self, text, host):
        """Substitute placeholders in a JSON body, JSON-escaping each value
        so quotes/backslashes in a secret can't break the document."""
        return self._swap_text(
            text, host, encode=lambda v: json.dumps(v)[1:-1])

    def _swap_urlencoded(self, text, host):
        """Swap percent-encoded placeholders (hsurr%3A<name>) found in
        application/x-www-form-urlencoded bodies. Substituted values are
        re-encoded so reserved characters can't corrupt the form. Used as
        the fallback for bodies with no parseable fields; the normal path
        is _swap_form_body."""
        def repl(m):
            name, entry = m.group(1), m.group(2) or "access_token"
            v = self._resolve(name, entry, host)
            if v is None:
                return m.group(0)  # unknown name/entry: leave untouched
            self._audit(host, "hsurr:%s%s"
                        % (name, (":" + entry) if m.group(2) else ""))
            return urllib.parse.quote(v, safe="")
        return ENCODED_PLACEHOLDER_RE.sub(repl, text)

    def _swap_form_body(self, text, host):
        """Swap placeholders in an application/x-www-form-urlencoded body.

        The body is parsed as a form, placeholder values are swapped, and
        the form is re-encoded, so reserved characters in a secret can't
        corrupt the fields. Browser-encoded placeholders (hsurr%3A<name>)
        are decoded by the parse and handled identically; literal colons
        (curl/requests style) work too. Bodies with no swappable fields
        fall back to the encoded-placeholder regex."""
        pairs = urllib.parse.parse_qsl(text, keep_blank_values=True)
        new_pairs = [(k, self._swap_text(v, host)) for k, v in pairs]
        if new_pairs != pairs:
            return urllib.parse.urlencode(new_pairs)
        return self._swap_urlencoded(text, host)

    # ------------------------------------------------------------------
    def _warn_if_placeholder(self, flow, host):
        """Warn when a placeholder is seen for a host that may not swap it
        (finding 22).

        The old version only matched the literal bytes b"hsurr:" in the
        body, so a placeholder inside a base64'd Basic-auth header — the
        exact case git uses — never triggered it. This version also
        inspects decoded Basic auth (the same helper the swap path
        uses), the percent-encoded form in the body, and the URL path.
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
        if hay in blob or hay_enc in blob:
            log.warning(
                "swap: placeholder seen for non-allowlisted host %s; "
                "passing through unchanged", host)

    # ------------------------------------------------------------------ SSRF

    def _resolve_ips(self, host):
        """Resolve host to IPs with a small TTL cache (finding 29).

        Returns None on DNS failure: fail open, since the request cannot
        complete upstream anyway.
        """
        now = time.time()
        cached = self._dns_cache.get(host)
        if cached and cached[0] > now:
            return cached[1]
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
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

    def _ssrf_refusal(self, host):
        """Return a reason string if the request must be refused (finding
        29), else None.

        Private ranges (RFC 1918, loopback, link-local, CGNAT/tailnet
        space) are refused by default; a host explicitly allowlisted in
        the ssrf file — by hostname or by CIDR covering a resolved IP —
        may proceed. DNS failure fails open. Residual: DNS-rebind races
        between this check and the upstream connect.
        """
        ips = self._resolve_ips(host)
        if ips is None:
            return None
        if not any(_is_private_ip(ip) for ip in ips):
            return None
        if _host_in_list(host, self.ssrf_hosts):
            return None
        for ip in ips:
            try:
                addr = ipaddress.ip_address(ip.split("%")[0])
            except ValueError:
                continue
            if _is_private_ip(ip) and any(addr in net
                                         for net in self.ssrf_nets):
                return None
        return "private-range"

    def _refuse(self, flow, reason):
        """Short-circuit a flow with a 403 (finding 29)."""
        if _mp_http is not None:
            flow.response = _mp_http.Response.make(
                403, b"swap-proxy: egress refused (%s)\n" % reason.encode(),
                {"Content-Type": "text/plain"})
        elif hasattr(flow, "kill"):
            flow.kill()

    def _swap_headers(self, req, host):
        # headers: never swap Referer/Origin; Cookie only when a registry
        # placement explicitly names the Cookie header
        for key in list(req.headers.keys()):
            kl = key.lower()
            if kl in NEVER_SWAP_HEADERS:
                continue
            vals = req.headers.get_all(key)
            if kl == "authorization":
                new_vals = [self._swap_basic_auth(v, host) for v in vals]
                # fall back to plain-text swap (e.g. Bearer <placeholder>)
                new_vals = [self._swap_text(v, host)
                            if nv == v else nv
                            for v, nv in zip(vals, new_vals)]
            elif kl == "cookie":
                allowed = self._cookie_swap_names()
                new_vals = [self._swap_text(v, host, allow=allowed)
                            for v in vals]
            else:
                new_vals = [self._swap_text(v, host) for v in vals]
            if new_vals != vals:
                req.headers.set_all(key, new_vals)

    def _request_inference(self, req, host):
        """Inference proxy request path (finding 31): headers only.

        obox's prompts can contain whole pages; they must never traverse
        credential insertion in bodies, query strings, paths, or
        websocket messages. The inference registry's placement is
        header-only anyway — this makes the guarantee structural.
        """
        self._swap_headers(req, host)

    def request(self, flow):
        self._maybe_reload()
        req = flow.request
        host = req.pretty_host
        refusal = self._ssrf_refusal(host)
        if refusal:
            log.warning("swap: refusing egress to %s: %s", host, refusal)
            self._refuse(flow, refusal)
            return
        if not self._host_allowed(host):
            self._warn_if_placeholder(flow, host)
            return
        if self.inference_mode:
            self._request_inference(req, host)
            return
        self._swap_headers(req, host)
        # query string (percent-decoded values; re-encoded on assignment)
        q_items = list(req.query.items(multi=True))
        if q_items:
            new_q = [(k, self._swap_text(v, host)) for k, v in q_items]
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
            new_dec = self._swap_text(dec, host)
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
                new_text = self._swap_json_text(text, host)
            elif "application/x-www-form-urlencoded" in ctype:
                new_text = self._swap_form_body(text, host)
            else:
                new_text = self._swap_text(text, host)
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

    def _secret_replacements(self):
        """(value, placeholder) pairs for response scrubbing (finding 4),
        longest value first so overlapping secrets replace correctly.
        totp seeds are never returned; the current code is included
        because the agent typed that placeholder into the page and a
        "review your details" screen may echo it back."""
        pairs = []
        for name, val in (self.secrets or {}).items():
            if isinstance(val, dict):
                for entry, v in val.items():
                    if entry == "totp":
                        try:
                            code = _totp_code(v)
                        except (ValueError, binascii.Error):
                            continue
                        pairs.append((code, "hsurr:%s:totp" % name))
                        continue
                    if v:
                        pairs.append((v, "hsurr:%s:%s" % (name, entry)))
            elif val:
                pairs.append((val, "hsurr:%s" % name))
        pairs.sort(key=lambda p: len(p[0]), reverse=True)
        return pairs

    def response(self, flow):
        """Scrub known secret values out of text responses from allowlisted
        hosts (finding 4), replacing each with its placeholder. Images and
        binary bodies are a stated residual risk, not a solved one."""
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
        try:
            text = resp.text
        except Exception:
            return  # undecodable: skip
        if len(resp.content or b"") > self._MAX_SCRUB_BYTES:
            return
        new_text = text
        for value, placeholder in self._secret_replacements():
            if value in new_text:
                new_text = new_text.replace(value, placeholder)
        if new_text != text:
            resp.text = new_text
            try:
                if "content-length" in resp.headers:
                    resp.headers["content-length"] = str(len(resp.content))
            except Exception:
                pass


addons = [SwapAddon()]
