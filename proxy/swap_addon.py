"""Transparent credential-swapping addon for mitmdump (runs as swapd).

Replaces hsurr:<name> and hsurr:<name>:<entry> placeholders in request
headers, URL query string, URL path, and text bodies with real secrets
from /home/swapd/secrets/, but ONLY for hosts listed in
/home/swapd/hosts.allow AND bound to that credential in the registry
(/home/swapd/credentials.json, an "allowed_hosts" list per credential,
managed with `cred register <name> --host <h>`). A credential with no
host binding never swaps: fail closed. Everything else passes through
untouched.

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

URL path: swapped per path segment and re-quoted with safe="", so
existing percent-escapes (%25, %2F) survive untouched and a substituted
value can't break out of its segment. The path is left byte-identical
when no segment changed.

An entry named "totp" is treated as a base32 seed: the swap inserts the
current RFC 6238 six-digit code (30s step, SHA-1), never the seed.

Secret files: one file per credential name. Either the whole file is the
single value, or the file holds "entry=value" lines (one per line) for
multi-entry credentials — entry-aware, mirroring fill_secret. For a
single-value secret an entry suffix only matches when it is absent or
"access_token"; anything else (e.g. hsurr:github:8080) is left alone.

Audit: every swap is appended to /home/swapd/swap.log as
    ts=<utc> host=<host> swapped=<matched placeholder>
Values are NEVER logged. Refused swaps (credential not bound to the
request host) are logged as warnings, also without values.
"""

import base64
import binascii
import hashlib
import hmac
import json
import logging
import re
import struct
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SECRETS_DIR = Path("/home/swapd/secrets")
HOSTS_FILE = Path("/home/swapd/hosts.allow")
REGISTRY_FILE = Path("/home/swapd/credentials.json")
LOG_FILE = Path("/home/swapd/swap.log")
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


class SwapAddon:
    def __init__(self):
        self.secrets = {}
        self.hosts = []
        self.registry = {}
        self._store_mtime = None
        self._hosts_mtime = None
        self._registry_mtime = None
        self._load()

    def _swap_basic_auth(self, value, host):
        """Swap placeholders inside an HTTP Basic Authorization header.

        Clients (git, curl -u) base64 the whole "user:password" pair, so a
        placeholder used as the password is invisible to plain text
        matching. Decode, swap, re-encode. Returns the original value if
        there is nothing to do or the value isn't valid Basic auth.
        """
        scheme, _, b64 = value.partition(" ")
        if scheme.lower() != "basic" or not b64.strip():
            return value
        try:
            decoded = base64.b64decode(b64.strip(), validate=True).decode("utf-8")
        except (binascii.Error, ValueError, UnicodeDecodeError):
            return value
        new_decoded = self._swap_text(decoded, host)
        if new_decoded == decoded:
            return value
        return "Basic " + base64.b64encode(
            new_decoded.encode("utf-8")).decode("ascii")

    # ------------------------------------------------------------------
    def _load_secret_file(self, path):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            log.warning("swap: cannot read secret %s: %s", path.name, e)
            return None
        lines = [l for l in text.splitlines() if l.strip()]
        if lines and all(ENTRY_LINE_RE.match(l) for l in lines):
            return {m.group(1): m.group(2)
                    for m in (ENTRY_LINE_RE.match(l) for l in lines)}
        return text.strip()

    def _load(self):
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
        hosts = []
        try:
            if HOSTS_FILE.is_file():
                for line in HOSTS_FILE.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        hosts.append(line.lower())
        except OSError as e:
            log.warning("swap: cannot read hosts.allow: %s", e)
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
        self.secrets = secrets
        self.hosts = hosts
        self.registry = registry
        self._store_mtime = self._mtime(SECRETS_DIR)
        self._hosts_mtime = self._mtime(HOSTS_FILE)
        self._registry_mtime = self._mtime(REGISTRY_FILE)

    @staticmethod
    def _mtime(p):
        try:
            return p.stat().st_mtime_ns
        except OSError:
            return None

    def _maybe_reload(self):
        # Pick up newly installed secrets / host / registry changes
        # without a restart.
        if (self._mtime(SECRETS_DIR) != self._store_mtime
                or self._mtime(HOSTS_FILE) != self._hosts_mtime
                or self._mtime(REGISTRY_FILE) != self._registry_mtime):
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
        hay = b"hsurr:"
        hay_enc = b"hsurr%3a"  # urlencoded forms percent-encode the colon
        body = (flow.request.content or b"").lower()
        in_body = hay in body or hay_enc in body
        in_headers = any(
            hay in v.encode("utf-8", "ignore")
            for k in flow.request.headers.keys()
            for v in flow.request.headers.get_all(k)
        )
        in_url = hay in flow.request.path.encode("utf-8", "ignore")
        if in_body or in_headers or in_url:
            log.warning(
                "swap: placeholder seen for non-allowlisted host %s; "
                "passing through unchanged", host)

    def request(self, flow):
        self._maybe_reload()
        req = flow.request
        host = req.pretty_host
        if not self._host_allowed(host):
            self._warn_if_placeholder(flow, host)
            return
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
        # query string (percent-decoded values; re-encoded on assignment)
        q_items = list(req.query.items(multi=True))
        if q_items:
            new_q = [(k, self._swap_text(v, host)) for k, v in q_items]
            query_changed = new_q != q_items
        else:
            new_q, query_changed = q_items, False
        # path: swap per segment and re-quote with safe="" so existing
        # escapes (%25, %2F) survive and a value can't leave its segment.
        # The path is left byte-identical when no segment changed.
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


addons = [SwapAddon()]
