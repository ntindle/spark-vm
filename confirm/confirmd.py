#!/usr/bin/env python3
"""confirmd — tailnet-only confirmation page (owner decision 3).

Serves pending approvals to the human over the tailnet, authenticated
by Tailscale identity. Runs as the swapd user. Nothing routes through
obox or the orchestrator.

v1 boundary: answers are recorded to answered/ but NOT consumed as
grants. The answer->grant channel is designed in jail/confirm-page.md
and stops for owner review before implementation.

Config (env):
  CONFIRM_BIND  tailnet address to bind (default 100.65.241.20)
  CONFIRM_PORT  port (default 8443)
  CONFIRM_CERT  TLS cert file (tailscale cert for the machine name)
  CONFIRM_KEY   TLS key file
  CONFIRM_OWNER expected Tailscale LoginName, e.g. ntindle@github
  CONFIRM_DIR   approvals dir (default /home/swapd/approvals)
"""

import html
import json
import os
import re
import subprocess
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone

BIND = os.environ.get("CONFIRM_BIND", "100.65.241.20")
PORT = int(os.environ.get("CONFIRM_PORT", "8443"))
CERT = os.environ.get("CONFIRM_CERT", "/home/swapd/confirmd/cert.crt")
KEY = os.environ.get("CONFIRM_KEY", "/home/swapd/confirmd/key.pem")
OWNER = os.environ.get("CONFIRM_OWNER", "ntindle@github")
APPROVALS = os.environ.get("CONFIRM_DIR", "/home/swapd/approvals")

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Small whois cache: identity checks are per-request, tailscaled is local.
_whois_cache = {}


def tailnet_login(peer_ip):
    """Return the Tailscale LoginName for peer_ip, or None."""
    now = time.time()
    hit = _whois_cache.get(peer_ip)
    if hit and now - hit[1] < 60:
        return hit[0]
    try:
        out = subprocess.run(
            ["tailscale", "whois", "--json", peer_ip],
            capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout)
        # whois --json nests the user profile under several possible keys
        # across versions; walk for the first LoginName found.
        login = _find_login(data)
        _whois_cache[peer_ip] = (login, now)
        return login
    except Exception:
        return None


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


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Approvals</title></head><body>
<h1>Pending approvals</h1>
{body}
<p><a href="/answered">answered history</a></p>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "confirmd/1"

    def _auth(self):
        peer = self.client_address[0]
        login = tailnet_login(peer)
        if login != OWNER:
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"forbidden: unknown tailnet identity\n")
            return None
        return login

    def _send_html(self, body, code=200):
        data = PAGE.format(body=body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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
                    rows.append(
                        '<li><a href="/approval/%s">%s</a> — %s '
                        '<small>(%s)</small></li>' % (
                            aid, aid,
                            html.escape(str(it.get("summary", ""))),
                            html.escape(str(it.get("kind", "")))))
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
            body = ("<h2>%s</h2><p><b>kind:</b> %s</p>"
                    "<p><b>requester:</b> %s</p><p>%s</p>"
                    '<form method="post" action="/answer">'
                    '<input type="hidden" name="id" value="%s">'
                    '<button name="decision" value="approve">Approve</button> '
                    '<button name="decision" value="deny">Deny</button>'
                    "</form>") % (
                        html.escape(aid),
                        html.escape(str(it.get("kind", ""))),
                        html.escape(str(it.get("requester", ""))),
                        html.escape(str(it.get("detail", ""))),
                        html.escape(aid))
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
        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        aid = form.get("id", [""])[0]
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
        # Expiry is enforced at answer time.
        exp = it.get("expires")
        if exp and datetime.now(timezone.utc).isoformat() > exp:
            decision = "deny"  # expired: record as deny, never approve
        it["decision"] = decision
        it["answered_at"] = datetime.now(timezone.utc).isoformat()
        it["answered_by"] = login
        dst = os.path.join(answered_dir(), aid + ".json")
        # Atomic move: write then rename, then remove pending.
        tmp = dst + ".tmp"
        with open(tmp, "w") as f:
            json.dump(it, f, indent=2)
        os.replace(tmp, dst)
        os.remove(src)
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *args):
        pass  # keep the journal quiet; answers are in answered/


def main():
    for d in (pending_dir(), answered_dir()):
        os.makedirs(d, exist_ok=True)
    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    srv = HTTPServer((BIND, PORT), Handler)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    print("confirmd on https://%s:%d/ as %s" % (BIND, PORT, OWNER), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
