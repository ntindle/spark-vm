#!/usr/bin/env python3
"""confirmd — tailnet-only confirmation page (owner decision 3).

Serves pending approvals to the human over the tailnet, authenticated
by Tailscale identity. Runs as the swapd user. Nothing routes through
obox or the orchestrator.

Findings 47/48 (round 5) are the trust boundary:
- 47: refuses peers that are the host itself or not remote tailnet
  nodes; the swap proxy hard-denies the page's name/port and the
  host's own addresses; every 403 is logged with peer and login.
- 48: per-item CSRF nonce + Sec-Fetch-Site/Origin check on POST.

Config (env):
  CONFIRM_BIND  tailnet address to bind (default: from `tailscale ip -4`)
  CONFIRM_PORT  port (default 8443)
  CONFIRM_CERT  TLS cert file (tailscale cert for the machine name)
  CONFIRM_KEY   TLS key file
  CONFIRM_OWNER expected Tailscale LoginName, e.g. ntindle@github
  CONFIRM_DIR   approvals dir (default /home/swapd/approvals)
  CONFIRM_AUDIT audit log for refusals (default /home/swapd/confirmd/audit.log)
"""

import grp
import html
import json
import os
import pwd
import re
import secrets
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("CONFIRM_PORT", "8443"))
CERT = os.environ.get("CONFIRM_CERT", "/home/swapd/confirmd/cert.crt")
KEY = os.environ.get("CONFIRM_KEY", "/home/swapd/confirmd/key.pem")
OWNER = os.environ.get("CONFIRM_OWNER", "ntindle@github")
APPROVALS = os.environ.get("CONFIRM_DIR", "/home/swapd/approvals")
AUDIT = os.environ.get("CONFIRM_AUDIT", "/home/swapd/confirmd/audit.log")

# Finding 53(f): bind address comes from tailscale, not a literal.
def _tailnet_ip4():
    try:
        out = subprocess.run(["tailscale", "ip", "-4"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            ip = out.stdout.strip().split()[0]
            if ip:
                return ip
    except Exception:
        pass
    return None

BIND = os.environ.get("CONFIRM_BIND") or _tailnet_ip4() or "100.65.241.20"

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{32}$")

# Finding 47: the host's own tailnet addresses. A peer presenting one
# of these is the host itself (e.g. the swap proxy connecting out) —
# never the human on a remote node.
def _host_addrs():
    addrs = set()
    try:
        out = subprocess.run(["tailscale", "ip"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            for line in out.stdout.splitlines():
                ip = line.strip()
                if ip:
                    addrs.add(ip)
    except Exception:
        pass
    # Belt and braces: the bind address is always self.
    addrs.add(BIND)
    return addrs

HOST_ADDRS = _host_addrs()

# Small whois cache: identity checks are per-request, tailscaled is local.
_whois_cache = {}

# Finding 53(g): swapd must not get tailscale operator (that grants
# full tailscaled control). Use a narrow sudoers rule for whois only.
def _whois_cmd(peer_ip):
    return ["sudo", "-n", "tailscale", "whois", "--json", peer_ip]


def tailnet_login(peer_ip):
    """Return the Tailscale LoginName for peer_ip, or None if the peer
    is not a remote tailnet node (finding 47)."""
    now = time.time()
    hit = _whois_cache.get(peer_ip)
    if hit and now - hit[1] < 60:
        return hit[0]
    login = None
    try:
        out = subprocess.run(_whois_cmd(peer_ip),
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            data = json.loads(out.stdout)
            login = _find_login(data)
    except Exception:
        pass
    _whois_cache[peer_ip] = (login, now)
    return login


def _find_login(obj):
    if isinstance(obj, dict):
        if "LoginName" in obj and isinstance(obj["LoginName"], str):
            return obj["LoginName"]
        for v in obj.values():
            found = _find_login(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_login(v)
            if found:
                return found
    return None


def audit_log(event, peer, login, detail=""):
    """Finding 47/53(e): every refusal leaves a trail with peer and login."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with open(AUDIT, "a", encoding="utf-8") as f:
            f.write("ts=%s event=%s peer=%s login=%s %s\n"
                    % (ts, event, peer, login or "-", detail))
    except OSError:
        pass


def pending_dir():
    d = os.path.join(APPROVALS, "pending")
    os.makedirs(d, exist_ok=True)
    return d


def answered_dir():
    d = os.path.join(APPROVALS, "answered")
    os.makedirs(d, exist_ok=True)
    return d


def load_pending():
    items = []
    d = pending_dir()
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, fn)) as f:
                items.append(json.load(f))
        except Exception:
            continue
    return items


def _parse_expiry(exp):
    """Finding 53(b): compare datetimes, not ISO strings."""
    if not exp:
        return None
    try:
        dt = datetime.fromisoformat(exp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def is_expired(item):
    exp = _parse_expiry(item.get("expires"))
    return exp is not None and datetime.now(timezone.utc) > exp


def file_owner_name(path):
    """Finding 50: the requester is the file's owner, never an argument."""
    try:
        st = os.stat(path)
        return pwd.getpwuid(st.st_uid).pw_name
    except (OSError, KeyError):
        return None


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Approvals</title></head><body>
<h1>Pending approvals</h1>
{body}
<p><a href="/answered">answered history</a></p>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "confirmd/1"

    def _deny(self, peer, login, reason):
        audit_log("403", peer, login, reason)
        self.send_response(403)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(("forbidden: %s\n" % reason).encode())

    def _auth(self):
        """Finding 47: the peer must be a remote tailnet node whose
        Tailscale login is the owner's. The host itself (proxy egress
        carries the host's own address) is refused even if whois maps
        it to the owner."""
        peer = self.client_address[0]
        if peer in HOST_ADDRS:
            self._deny(peer, None, "self-peer")
            return None
        login = tailnet_login(peer)
        if login is None:
            self._deny(peer, None, "not-a-tailnet-node")
            return None
        if login != OWNER:
            self._deny(peer, login, "unknown-identity")
            return None
        return login

    def _send_html(self, body, code=200):
        data = PAGE.format(body=body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _render_item(self, it):
        """Finding 49: structured fields render as a table; any
        free-text purpose is labeled untrusted."""
        rows = []
        for key in ("credential", "host", "method", "path_prefix",
                    "scope", "amount", "job"):
            val = it.get(key)
            if val is not None:
                rows.append("<tr><th>%s</th><td>%s</td></tr>" % (
                    html.escape(key), html.escape(str(val))))
        table = "<table>%s</table>" % "".join(rows) if rows else ""
        purpose = it.get("detail") or it.get("summary") or ""
        untrusted = ""
        if purpose:
            untrusted = ("<p><b>Requester-supplied purpose "
                         "(untrusted):</b> %s</p>" % html.escape(str(purpose)))
        return table + untrusted

    def do_GET(self):
        login = self._auth()
        if login is None:
            return
        if self.path == "/":
            items = load_pending()
            if not items:
                body = "<p>No pending approvals.</p>"
            else:
                rows = []
                for it in items:
                    aid = html.escape(str(it.get("id", "?")))
                    # Finding 53(a): expired items show as expired.
                    expired = " <b>(expired)</b>" if is_expired(it) else ""
                    rows.append(
                        '<li><a href="/approval/%s">%s</a> — %s '
                        '<small>(%s)</small>%s</li>' % (
                            aid, aid,
                            html.escape(str(it.get("summary", ""))),
                            html.escape(str(it.get("kind", ""))), expired))
                body = "<ul>%s</ul>" % "".join(rows)
            self._send_html(body)
        elif self.path == "/answered":
            items = []
            d = answered_dir()
            for fn in sorted(os.listdir(d), reverse=True):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(d, fn)) as f:
                        items.append(json.load(f))
                except Exception:
                    continue
            rows = []
            for it in items:
                rows.append("<li>%s — <b>%s</b> by %s <small>%s</small></li>" % (
                    html.escape(str(it.get("id", "?"))),
                    html.escape(str(it.get("decision", "?"))),
                    html.escape(str(it.get("answered_by", "?"))),
                    html.escape(str(it.get("answered_at", "")))))
            self._send_html("<ul>%s</ul>" % "".join(rows) or "<p>None.</p>")
        elif self.path.startswith("/approval/"):
            aid = self.path[len("/approval/"):]
            if not ID_RE.match(aid):
                self._send_html("<p>bad id</p>", 400)
                return
            p = os.path.join(pending_dir(), aid + ".json")
            if not os.path.exists(p):
                self._send_html("<p>not found or already answered</p>", 404)
                return
            with open(p) as f:
                it = json.load(f)
            if is_expired(it):
                # Finding 53(a): refuse with a message, and reap.
                try:
                    os.remove(p)
                except OSError:
                    pass
                audit_log("expired-reaped", self.client_address[0], login,
                          "id=%s" % aid)
                self._send_html("<p>This approval expired and was "
                                "removed.</p>", 410)
                return
            # Finding 48: mint a CSRF nonce, store it in the pending file.
            nonce = secrets.token_urlsafe(24)
            it["_csrf"] = nonce
            tmp = p + ".tmp"
            with open(tmp, "w") as f:
                json.dump(it, f, indent=2)
            os.replace(tmp, p)
            body = ("<h2>%s</h2>%s"
                    '<form method="post" action="/answer">'
                    '<input type="hidden" name="id" value="%s">'
                    '<input type="hidden" name="csrf" value="%s">'
                    '<button name="decision" value="approve">Approve</button> '
                    '<button name="decision" value="deny">Deny</button>'
                    "</form>") % (
                        html.escape(aid), self._render_item(it),
                        html.escape(aid), html.escape(nonce))
            self._send_html(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        login = self._auth()
        if login is None:
            return
        if self.path != "/answer":
            self.send_response(404)
            self.end_headers()
            return
        # Finding 48: reject non-same-origin POSTs.
        fetch_site = self.headers.get("Sec-Fetch-Site", "")
        origin = self.headers.get("Origin", "")
        if fetch_site and fetch_site != "same-origin":
            self._deny(self.client_address[0], login,
                       "csrf: Sec-Fetch-Site=%s" % fetch_site)
            return
        if origin and not origin.startswith("https://%s" % BIND):
            # Allow the tailnet DNS name too (same cert, same host).
            self._deny(self.client_address[0], login,
                       "csrf: Origin=%s" % origin)
            return
        # Finding 53(d): cap the body.
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0 or length > 4096:
            self._send_html("<p>bad request</p>", 400)
            return
        form = urllib.parse.parse_qs(
            self.rfile.read(length).decode(errors="replace"))
        aid = form.get("id", [""])[0]
        csrf = form.get("csrf", [""])[0]
        decision = form.get("decision", [""])[0]
        if not ID_RE.match(aid) or decision not in ("approve", "deny"):
            self._send_html("<p>bad request</p>", 400)
            return
        src = os.path.join(pending_dir(), aid + ".json")
        if not os.path.exists(src):
            self._send_html("<p>not found or already answered</p>", 404)
            return
        with open(src) as f:
            it = json.load(f)
        # Finding 48: the nonce must match the one minted on GET.
        if not NONCE_RE.match(csrf) or it.get("_csrf") != csrf:
            self._deny(self.client_address[0], login, "csrf: bad nonce")
            return
        # Finding 53(a): expired items are refused, not silently denied.
        if is_expired(it):
            try:
                os.remove(src)
            except OSError:
                pass
            audit_log("expired-reaped", self.client_address[0], login,
                      "id=%s" % aid)
            self._send_html("<p>This approval expired and was removed.</p>",
                            410)
            return
        # Finding 50: the requester is the file owner, and only
        # bdrive/swapd may file.
        requester = file_owner_name(src)
        if requester not in ("bdrive", "swapd"):
            self._deny(self.client_address[0], login,
                       "bad requester: %s" % requester)
            return
        it.pop("_csrf", None)
        it["decision"] = decision
        it["answered_at"] = datetime.now(timezone.utc).isoformat()
        it["answered_by"] = login
        it["requester"] = requester
        dst = os.path.join(answered_dir(), aid + ".json")
        tmp = dst + ".tmp"
        with open(tmp, "w") as f:
            json.dump(it, f, indent=2)
        os.replace(tmp, dst)
        os.remove(src)
        audit_log("answer", self.client_address[0], login,
                  "id=%s decision=%s requester=%s"
                  % (aid, decision, requester))
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *args):
        pass  # refusals go to the audit log; answers are in answered/


def main():
    for d in (pending_dir(), answered_dir()):
        os.makedirs(d, exist_ok=True)
    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    # Finding 53(c): threaded, so a slow whois never blocks the page.
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    print("confirmd on https://%s:%d/ as %s" % (BIND, PORT, OWNER), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
