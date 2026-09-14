"""Transparent credential-swapping addon for mitmdump (runs as swapd).

Replaces hsurr:<name> and hsurr:<name>:<entry> placeholders in request
headers, URL query string, URL path, and text bodies with real secrets
from /home/swapd/secrets/, but ONLY for hosts listed in
/home/swapd/hosts.allow. Everything else passes through untouched.
HTML form posts (application/x-www-form-urlencoded) percent-encode the
colon, so hsurr%3A<name> is swapped there too, with values re-encoded.

Secret files: one file per credential name. Either the whole file is the
single value, or the file holds "entry=value" lines (one per line) for
multi-entry credentials — entry-aware, mirroring fill_secret.

Audit: every swap is appended to /home/swapd/swap.log as
    ts=<utc> host=<host> swapped=<matched placeholder>
Values are NEVER logged.
"""

import logging
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SECRETS_DIR = Path("/home/swapd/secrets")
HOSTS_FILE = Path("/home/swapd/hosts.allow")
LOG_FILE = Path("/home/swapd/swap.log")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ENTRY_LINE_RE = re.compile(r"^([A-Za-z0-9_-]+)=(.*)$", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"hsurr:([A-Za-z0-9_-]+)(?::([A-Za-z0-9_-]+))?")
# Percent-encoded form, as sent in application/x-www-form-urlencoded bodies
# (browsers encode ':' as %3A). Case-insensitive on the hex digits.
ENCODED_PLACEHOLDER_RE = re.compile(
    r"hsurr%3A([A-Za-z0-9_-]+)(?:%3A([A-Za-z0-9_-]+))?", re.IGNORECASE)

log = logging.getLogger(__name__)


class SwapAddon:
    def __init__(self):
        self.secrets = {}
        self.hosts = []
        self._store_mtime = None
        self._hosts_mtime = None
        self._load()

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
        self.secrets = secrets
        self.hosts = hosts
        self._store_mtime = self._mtime(SECRETS_DIR)
        self._hosts_mtime = self._mtime(HOSTS_FILE)

    @staticmethod
    def _mtime(p):
        try:
            return p.stat().st_mtime_ns
        except OSError:
            return None

    def _maybe_reload(self):
        # Pick up newly installed secrets / host changes without a restart.
        if (self._mtime(SECRETS_DIR) != self._store_mtime
                or self._mtime(HOSTS_FILE) != self._hosts_mtime):
            self._load()

    # ------------------------------------------------------------------
    def _host_allowed(self, host):
        h = (host or "").lower().split(":")[0]
        for entry in self.hosts:
            if h == entry or (entry.startswith(".") and h.endswith(entry)):
                return True
        return False

    def _resolve(self, name, entry):
        """Return the secret value for name/entry, or None to leave untouched."""
        val = self.secrets.get(name)
        if val is None:
            return None
        if isinstance(val, dict):
            return val.get(entry or "access_token")
        return val

    def _audit(self, host, matched):
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write("ts=%s host=%s swapped=%s\n" % (ts, host, matched))
        except OSError as e:
            log.warning("swap: cannot write audit log: %s", e)

    def _swap_text(self, text, host):
        def repl(m):
            name, entry = m.group(1), m.group(2) or "access_token"
            v = self._resolve(name, entry)
            if v is None:
                return m.group(0)  # unknown name/entry: leave untouched
            self._audit(host, m.group(0))
            return v
        return PLACEHOLDER_RE.sub(repl, text)

    def _swap_urlencoded(self, text, host):
        """Swap percent-encoded placeholders (hsurr%3A<name>) found in
        application/x-www-form-urlencoded bodies. Substituted values are
        re-encoded so reserved characters can't corrupt the form."""
        def repl(m):
            name, entry = m.group(1), m.group(2) or "access_token"
            v = self._resolve(name, entry)
            if v is None:
                return m.group(0)  # unknown name/entry: leave untouched
            self._audit(host, "hsurr:%s%s"
                        % (name, (":" + entry) if m.group(2) else ""))
            return urllib.parse.quote(v, safe="")
        return ENCODED_PLACEHOLDER_RE.sub(repl, text)

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
        # headers
        for key in list(req.headers.keys()):
            vals = req.headers.get_all(key)
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
        # path (percent-decoded, then re-encoded)
        raw_path, _, _ = req.path.partition("?")
        dec_path = urllib.parse.unquote(raw_path)
        new_dec_path = self._swap_text(dec_path, host)
        path_changed = new_dec_path != dec_path
        if path_changed or query_changed:
            new_path = urllib.parse.quote(new_dec_path, safe="/%:@")
            if new_q:
                req.path = new_path + "?" + urllib.parse.urlencode(new_q)
            else:
                req.path = new_path
        # body (text only)
        if req.content:
            try:
                text = req.content.decode("utf-8")
            except UnicodeDecodeError:
                return  # binary body: headers/query/path already handled
            new_text = self._swap_text(text, host)
            ctype = req.headers.get("content-type", "")
            if "application/x-www-form-urlencoded" in ctype:
                new_text = self._swap_urlencoded(new_text, host)
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
