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
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --- spark-vm version stamping (docs/VERSIONING.md) ---
# Single-source repo VERSION: reported at startup and on /api/version.
# Import is best-effort — a missing/invalid VERSION must never break startup.
_SV_HERE = os.path.dirname(os.path.abspath(__file__))
_SV_CAND = os.path.normpath(os.path.join(_SV_HERE, "..", "scripts"))
if os.path.isfile(os.path.join(_SV_CAND, "sparkvm_version.py")):
    if _SV_CAND not in sys.path:
        sys.path.insert(0, _SV_CAND)
elif _SV_HERE not in sys.path:
    # Deployed standalone (e.g. /home/swapd): helper + VERSION sit next to us.
    sys.path.insert(0, _SV_HERE)
try:
    from sparkvm_version import sparkvm_version as _sv_fn
    SPARKVM_VERSION = _sv_fn(start=_SV_HERE)
except (ImportError, OSError, ValueError):
    SPARKVM_VERSION = "0.0.0-unknown"
# --- end version stamping ---

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

# Finding 57: the page's own origins, exact-matched with port.
# Served at the tailnet IP (BIND) and the ts.net DNS name.
def _tailnet_dnsname():
    """Finding 67: sudo-first, like _host_addrs. A narrow sudoers rule
    for `tailscale status --json` exists; use it. If unprivileged
    status fails as swapd, PAGE_ORIGINS would hold only the IP origin
    and every real browser POST would 403 (finding 57 again)."""
    for cmd in (["sudo", "-n", "tailscale", "status", "--json"],
                ["tailscale", "status", "--json"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=10)
            if out.returncode == 0:
                import json as _json
                data = _json.loads(out.stdout)
                name = data.get("Self", {}).get("DNSName", "")
                # "spark-vm.axolotl-sirius.ts.net." -> strip trailing dot
                name = name.rstrip(".")
                if name:
                    return name
        except Exception:
            continue
    return None

def _page_origins():
    """Exact set of origins the page is served at (finding 57)."""
    # Explicit override wins (deploy.sh sets both IP and ts.net name).
    env = os.environ.get("CONFIRM_ORIGINS", "")
    if env.strip():
        return {o.strip() for o in env.split(",") if o.strip()}
    origins = {"https://%s:%d" % (BIND, PORT)}
    dns = _tailnet_dnsname()
    if dns:
        origins.add("https://%s:%d" % (dns, PORT))
    return origins

PAGE_ORIGINS = _page_origins()

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{32}$")

# Finding 47: the host's own tailnet addresses. A peer presenting one
# of these is the host itself (e.g. the swap proxy connecting out) —
# never the human on a remote node.
def _host_addrs():
    """Finding 63(b): try sudo first (same narrow rule as whois). If
    tailscaled is unreachable, warn - the set collapses to BIND only."""
    addrs = set()
    ok = False
    for cmd in (["sudo", "-n", "tailscale", "ip"], ["tailscale", "ip"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=10)
            if out.returncode == 0:
                for line in out.stdout.splitlines():
                    ip = line.strip()
                    if ip:
                        addrs.add(ip)
                ok = True
                break
        except Exception:
            continue
    if not ok:
        # Finding 63(b): do not silently collapse. This is a security
        # boundary (finding 47); log it loudly.
        print("confirmd WARNING: cannot get tailscale IPs; self-peer "
              "set is BIND only", flush=True)
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
    return d


def consumed_dir():
    # Finding 56: one-way consumption. Answered files move here after
    # the grant is minted (or denied).
    d = os.path.join(APPROVALS, "consumed")
    os.makedirs(d, exist_ok=True)
    return d


# Finding 60: the single writer for grants.json.
GRANT_WRITER = os.environ.get("GRANT_WRITER", "/home/swapd/grant-writer")


def load_pending():
    """Finding 58: reap expired items when the list is rendered."""
    items = []
    d = pending_dir()
    now = datetime.now(timezone.utc)
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(d, fn)
        try:
            with open(p) as f:
                it = json.load(f)
            exp = _parse_expiry(it.get("expires"))
            if exp is not None and now >= exp:
                os.remove(p)
                continue
            items.append(it)
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


STYLE = """<style>
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
margin:0;padding:16px;line-height:1.45;color:#1a1a1a;background:#f6f7f9}
@media(prefers-color-scheme:dark){body{color:#e8e8e8;background:#111214}}
main{max-width:720px;margin:0 auto}
h1{font-size:1.4rem;margin:0 0 4px}
.sub{color:#666;font-size:.85rem;margin:0 0 16px}
@media(prefers-color-scheme:dark){.sub{color:#999}}
.card{background:#fff;border:1px solid #dcdfe3;border-radius:10px;
padding:14px;margin:0 0 12px}
@media(prefers-color-scheme:dark){.card{background:#1c1e21;border-color:#333}}
a.card{display:block;color:inherit;text-decoration:none}
a.card:active{background:#f0f2f5}
@media(prefers-color-scheme:dark){a.card:active{background:#24272b}}
.card h2{font-size:1.05rem;margin:0 0 6px;word-break:break-all}
.summary{font-size:.95rem;margin:4px 0}
.meta{font-size:.8rem;color:#666;margin:4px 0 0}
@media(prefers-color-scheme:dark){.meta{color:#999}}
.badge{display:inline-block;font-size:.75rem;font-weight:700;
padding:2px 10px;border-radius:999px;margin-left:6px;vertical-align:middle}
.badge-approve{background:#dff3e4;color:#1a7f37}
.badge-deny{background:#fde8e8;color:#b3261e}
@media(prefers-color-scheme:dark){
.badge-deny{background:#3a1f1f;color:#f2a9a2}
.badge-approve{background:#173a24;color:#9fe0b4}}
table.detail{width:100%;border-collapse:collapse;margin:12px 0;font-size:.95rem}
table.detail th{text-align:left;padding:8px 10px;background:#f0f2f5;
width:34%;border-radius:6px 0 0 6px}
table.detail td{padding:8px 10px;word-break:break-word}
@media(prefers-color-scheme:dark){table.detail th{background:#24272b}}
.untrusted{font-size:.9rem;background:#fff8e1;border:1px solid #f0e0a0;
border-radius:8px;padding:10px 12px;margin:12px 0}
@media(prefers-color-scheme:dark){.untrusted{background:#2b2517;border-color:#4d4426}}
.btnrow{display:flex;gap:12px;margin:16px 0;flex-wrap:wrap}
.btn{display:inline-block;min-height:52px;min-width:140px;flex:1;
padding:14px 20px;font-size:1.05rem;font-weight:700;border-radius:12px;
border:2px solid transparent;cursor:pointer;text-align:center;
font-family:inherit}
.btn-approve{background:#1a7f37;color:#fff}
.btn-approve:active{background:#146c2e}
.btn-deny{background:transparent;color:#c0392b;border-color:#c0392b}
.btn-deny:active{background:#fde8e8}
@media(prefers-color-scheme:dark){
.btn-deny{color:#f2a9a2;border-color:#f2a9a2}
.btn-deny:active{background:#3a1f1f}}
/* Design review #4: armed confirm state for the approve button. */
.btn-approve.armed{background:#8a5200}
/* Design review: visible keyboard focus; language-appropriate link. */
a.card:focus-visible,.btn:focus-visible{outline:3px solid #1a73e8;outline-offset:2px}
@media(prefers-color-scheme:dark){
a.card:focus-visible,.btn:focus-visible{outline-color:#8ab4f8}}
/* Design review #2: poll-failure is visually distinct from live. */
.sub.stale{color:#b3261e;font-weight:700}
@media(prefers-color-scheme:dark){.sub.stale{color:#f2a9a2}}
.nav{margin:20px 0 8px;font-size:.9rem}
.nav a{color:#1a73e8}
@media(prefers-color-scheme:dark){.nav a{color:#8ab4f8}}
.empty{color:#666;font-size:1rem;padding:24px 0;text-align:center}
@media(prefers-color-scheme:dark){.empty{color:#999}}
</style>"""

# Issue #1: live-update the list pages. The JS polls the JSON API every
# 5 s and rebuilds the list with textContent only (never innerHTML from
# data), so requester-supplied strings cannot inject markup. No-JS
# clients still get the server-rendered static list.
POLL_JS = """<script>
"use strict";
function fmtTime(iso){
  if(!iso) return "";
  var d=new Date(iso);
  return isNaN(d) ? String(iso) : d.toLocaleString();
}
function startPoll(api,render){
  var list=document.getElementById("items");
  var stamp=document.getElementById("updated");
  var lastJson="";
  async function tick(){
    // Design review: don't drain a phone battery on a hidden tab.
    if(document.hidden) return;
    try{
      var r=await fetch(api,{credentials:"same-origin",cache:"no-store"});
      if(!r.ok) throw new Error("http "+r.status);
      var text=await r.text();
      // Design review #3: skip re-render when the payload is
      // byte-identical, so a 5s tick never destroys :active press
      // feedback or shifts cards under a tapping finger.
      if(text!==lastJson){
        lastJson=text;
        render(list,JSON.parse(text));
      }
      stamp.textContent="updated "+new Date().toLocaleString();
      stamp.classList.remove("stale");
    }catch(e){
      // Design review #2: failure is visually distinct from live.
      stamp.textContent="update failed \\u2014 showing last known state";
      stamp.classList.add("stale");
    }
  }
  setInterval(tick,5000);tick();
}
// Design review #3: keyed reconciliation. Cards are matched by id and
// only touched when their payload actually changed, so answering one
// request elsewhere doesn't shift or rebuild the others.
function keyedUpdate(list,items,makeNode,keyOf,emptyText){
  if(!items.length){
    list.textContent="";
    var p=document.createElement("p");p.className="empty";
    p.textContent=emptyText;list.appendChild(p);return;
  }
  var seen={},order=[];
  items.forEach(function(it){
    var key=keyOf(it),sig=JSON.stringify(it),node=null;
    seen[key]=1;
    for(var i=0;i<list.children.length;i++){
      if(list.children[i].getAttribute("data-k")===key){
        node=list.children[i];break;
      }
    }
    if(node&&node.getAttribute("data-s")===sig){
      order.push(node);return;
    }
    var fresh=makeNode(it);
    if(!fresh) return;
    fresh.setAttribute("data-k",key);
    fresh.setAttribute("data-s",sig);
    if(node) list.replaceChild(fresh,node);
    order.push(fresh);
  });
  for(var j=list.children.length-1;j>=0;j--){
    if(!seen[list.children[j].getAttribute("data-k")])
      list.removeChild(list.children[j]);
  }
  order.forEach(function(n){list.appendChild(n);});
}
function validId(id){return /^[A-Za-z0-9_-]{1,64}$/.test(id);}
function card(id){
  var a=document.createElement("a");
  a.className="card";a.href="/approval/"+encodeURIComponent(id);
  var h=document.createElement("h2");h.textContent=id;a.appendChild(h);
  return a;
}
function metaLine(el,parts){
  var m=document.createElement("div");m.className="meta";
  m.textContent=parts.filter(Boolean).join(" \\u00b7 ");el.appendChild(m);
}
function pendingCard(it){
  var id=String(it.id||"");
  if(!validId(id)) return null;
  var a=card(id);
  var s=document.createElement("div");s.className="summary";
  s.textContent=String(it.summary||"");a.appendChild(s);
  metaLine(a,[String(it.kind||""),
    it.created?("filed "+fmtTime(it.created)):"",
    it.expires?("expires "+fmtTime(it.expires)):""]);
  return a;
}
function renderPending(list,items){
  keyedUpdate(list,items,pendingCard,function(it){return String(it.id||"");},
    "No pending approvals.");
}
function answeredCard(it){
  var id=String(it.id||"?");
  if(!validId(id)&&id!=="?") return null;
  var c=document.createElement("div");c.className="card";
  var h=document.createElement("h2");
  h.textContent=id;c.appendChild(h);
  var d=document.createElement("span");
  var dec=String(it.decision||"?");
  if(dec==="approve"||dec==="deny"){
    d.className="badge "+(dec==="approve"?"badge-approve":"badge-deny");
    d.textContent=dec;h.appendChild(d);
  }
  var s=document.createElement("div");s.className="summary";
  s.textContent=String(it.summary||"");c.appendChild(s);
  metaLine(c,[it.answered_by?("by "+String(it.answered_by)):"",
    it.answered_at?fmtTime(it.answered_at):"",
    String(it.kind||"")]);
  return c;
}
function renderAnswered(list,items){
  keyedUpdate(list,items,answeredCard,function(it){return String(it.id||"?");},
    "No answered approvals yet.");
}
</script>"""


def _page(title, body, script=""):
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>%s</title>%s</head><body><main>%s</main>%s"
            "</body></html>") % (html.escape(title), STYLE, body, script)


def _sort_pending(items):
    """Oldest filed first: the longest-waiting request is most urgent.
    Engineering review: items with missing/unparseable `created` sort
    LAST, never first ("" < any ISO string was a lie about urgency)."""
    return sorted(items,
                  key=lambda it: _parse_expiry(it.get("created")) or _MAX_DT)


def _pending_api_item(it):
    """Issue #1: the JSON surface for the poller. Allowlisted fields
    only — the same data the list page already shows, never secrets."""
    return {
        "id": str(it.get("id", "")),
        "summary": str(it.get("summary", "")),
        "kind": str(it.get("kind", "")),
        "created": str(it.get("created", "")),
        "expires": str(it.get("expires", "")),
    }


# Engineering review (blocker 2): load_pending() reaps expired files
# BEFORE the list is built, so an "expired" badge can never render in
# production — the badge was dead code with a misleading test. It is
# removed rather than kept as false belt-and-braces.
_MAX_DT = datetime.max.replace(tzinfo=timezone.utc)


def _load_answered():
    """Newest answered first (issue #1), by answered_at — filenames are
    random hex, so filename order is NOT chronological (engineering)."""
    items = []
    d = consumed_dir()
    for fn in os.listdir(d):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, fn)) as f:
                items.append(json.load(f))
        except Exception:
            continue
    items.sort(key=lambda it: _parse_expiry(it.get("answered_at")) or
               datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items


# Product review (blocker 2): the answered feed is re-polled every 5 s,
# so it is capped — history on disk stays complete.
_ANSWERED_FEED_LIMIT = 100


def _answered_api_item(it):
    """Issue #1: JSON surface for the answered-history poller.
    Allowlisted fields only."""
    return {
        "id": str(it.get("id", "")),
        "summary": str(it.get("summary", "")),
        "kind": str(it.get("kind", "")),
        "decision": str(it.get("decision", "")),
        "answered_by": str(it.get("answered_by", "")),
        "answered_at": str(it.get("answered_at", "")),
    }


def _meta_line(parts):
    """Engineering review: one named helper for the "kind · filed ·
    expires" line, so the escape ordering is reviewable in one place."""
    parts = [p for p in parts if p]
    if not parts:
        return ""
    return '<div class="meta">%s</div>' % " · ".join(
        html.escape(str(p)) for p in parts)


def _render_pending_list(items):
    """Server-rendered static list (no-JS fallback); the poller
    replaces #items with the same cards built from JSON."""
    if not items:
        return '<p class="empty">No pending approvals.</p>'
    cards = []
    for it in _sort_pending(items):
        aid = str(it.get("id", "?"))
        if not ID_RE.match(aid):
            continue
        meta = _meta_line([
            it.get("kind") or "",
            ("filed %s" % it["created"]) if it.get("created") else "",
            ("expires %s" % it["expires"]) if it.get("expires") else ""])
        cards.append(
            '<a class="card" href="/approval/%s"><h2>%s</h2>'
            '<div class="summary">%s</div>%s</a>' % (
                html.escape(aid), html.escape(aid),
                html.escape(str(it.get("summary", ""))), meta))
    return "".join(cards) or '<p class="empty">No pending approvals.</p>'


def _render_answered_list(items):
    if not items:
        return '<p class="empty">No answered approvals yet.</p>'
    cards = []
    for it in items:
        dec = str(it.get("decision", "?"))
        badge = ""
        if dec in ("approve", "deny"):
            badge = ('<span class="badge %s">%s</span>' % (
                "badge-approve" if dec == "approve" else "badge-deny",
                html.escape(dec)))
        meta = _meta_line([
            ("by %s" % it.get("answered_by")) if it.get("answered_by") else "",
            it.get("answered_at") or "",
            it.get("kind") or ""])
        cards.append(
            '<div class="card"><h2>%s%s</h2>'
            '<div class="summary">%s</div>%s</div>' % (
                html.escape(str(it.get("id", "?"))), badge,
                html.escape(str(it.get("summary", ""))), meta))
    return "".join(cards)


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

    def _send_html(self, body, code=200, title="Approvals", script=""):
        data = _page(title, body, script).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _err(self, msg, code):
        self._send_html('<div class="card"><p>%s</p></div>'
                        '<p class="nav"><a href="/">back to pending</a></p>'
                        % html.escape(msg), code, title="Approvals")

    def _send_json(self, obj, code=200):
        """Issue #1: JSON surface for the list pollers. Authenticated
        exactly like the pages (the caller runs _auth first); no
        caching — approval state is live."""
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
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
        table = ('<table class="detail">%s</table>' % "".join(rows)
                 if rows else "")
        purpose = it.get("detail") or it.get("summary") or ""
        untrusted = ""
        if purpose:
            untrusted = ('<div class="untrusted"><b>Requester-supplied purpose '
                         '(untrusted):</b><br>%s</div>'
                         % html.escape(str(purpose)))
        filed = []
        if it.get("created"):
            filed.append("filed %s" % it["created"])
        if it.get("expires"):
            filed.append("expires %s" % it["expires"])
        return _meta_line(filed) + table + untrusted

    def do_GET(self):
        login = self._auth()
        if login is None:
            return
        # Issue #1: JSON feeds for the live list pollers. Same auth
        # gate as the pages; allowlisted fields only (see the helpers).
        if self.path == "/api/version":
            self._send_json(_version_payload())
            return
        if self.path == "/api/pending":
            items = _sort_pending(load_pending())
            self._send_json([_pending_api_item(it) for it in items])
            return
        if self.path == "/api/answered":
            # Product review: cap the 5s-polled feed; on-disk history
            # stays complete.
            self._send_json([_answered_api_item(it) for it in
                             _load_answered()[:_ANSWERED_FEED_LIMIT]])
            return
        if self.path == "/":
            body = ('<h1>Pending approvals</h1>'
                    '<p class="sub" id="updated" role="status">live — checking every 5 s</p>'
                    '<div id="items">%s</div>'
                    '<p class="nav"><a href="/answered">answered history</a></p>'
                    % _render_pending_list(load_pending()))
            self._send_html(body, title="Pending approvals",
                            script=POLL_JS + '<script>startPoll("/api/pending",'
                            'renderPending);</script>')
        elif self.path == "/answered":
            body = ('<h1>Answered approvals</h1>'
                    '<p class="sub" role="status">showing the 100 most recent'
                    ' · <span id="updated">live — checking every 5 s</span></p>'
                    '<div id="items">%s</div>'
                    '<p class="nav"><a href="/">back to pending</a></p>'
                    % _render_answered_list(
                        _load_answered()[:_ANSWERED_FEED_LIMIT]))
            self._send_html(body, title="Answered approvals",
                            script=POLL_JS + '<script>startPoll("/api/answered",'
                            'renderAnswered);</script>')
        elif self.path.startswith("/approval/"):
            aid = self.path[len("/approval/"):]
            if not ID_RE.match(aid):
                self._err("bad id", 400)
                return
            p = os.path.join(pending_dir(), aid + ".json")
            if not os.path.exists(p):
                self._err("not found or already answered", 404)
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
                self._err("This approval expired and was removed.", 410)
                return
            # Finding 48: mint a CSRF nonce, store it in the pending file.
            nonce = secrets.token_urlsafe(24)
            it["_csrf"] = nonce
            tmp = p + ".tmp"
            with open(tmp, "w") as f:
                json.dump(it, f, indent=2)
            os.replace(tmp, p)
            body = ("<h1>Approval %s</h1>%s"
                    '<p class="sub">Approving mints a credential grant for '
                    'this request. Denying discards it.</p>'
                    '<form method="post" action="/answer">'
                    '<input type="hidden" name="id" value="%s">'
                    '<input type="hidden" name="csrf" value="%s">'
                    '<div class="btnrow">'
                    '<button class="btn btn-approve" id="approveBtn" '
                    'name="decision" value="approve">Approve</button>'
                    '<button class="btn btn-deny" name="decision" '
                    'value="deny">Deny</button>'
                    "</div></form>"
                    '<p class="nav"><a href="/">back to pending</a></p>'
                    # Design review #4: a single large tap must not mint a
                    # credential grant. First tap arms, second confirms.
                    '<script>'
                    '"use strict";'
                    'var b=document.getElementById("approveBtn");'
                    'b.addEventListener("click",function(e){'
                    'if(!b.dataset.armed){'
                    'e.preventDefault();'
                    'b.dataset.armed="1";'
                    'b.classList.add("armed");'
                    'b.textContent="Tap again to confirm approval";'
                    '}});'
                    "</script>") % (
                        html.escape(aid), self._render_item(it),
                        html.escape(aid), html.escape(nonce))
            self._send_html(body, title="Approval %s" % aid)
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
        # Finding 63(d): Sec-Fetch-Site is enforced only when present.
        # The per-item CSRF nonce (minted on GET, required on POST) is
        # the real protection; Sec-Fetch-Site is defense in depth for
        # browsers that send it. Non-browser clients (curl) omit it.
        fetch_site = self.headers.get("Sec-Fetch-Site", "")
        origin = self.headers.get("Origin", "")
        if fetch_site and fetch_site != "same-origin":
            self._deny(self.client_address[0], login,
                       "csrf: Sec-Fetch-Site=%s" % fetch_site)
            return
        # Finding 57: exact-match Origin against the page's own
        # origins, port included. The old startswith accepted only the
        # IP literal (breaking real approvals) and also matched
        # 100.65.241.200 (prefix without port).
        if origin and origin not in PAGE_ORIGINS:
            self._deny(self.client_address[0], login,
                       "csrf: Origin=%s" % origin)
            return
        # Finding 53(d): cap the body.
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0 or length > 4096:
            self._err("bad request", 400)
            return
        form = urllib.parse.parse_qs(
            self.rfile.read(length).decode(errors="replace"))
        aid = form.get("id", [""])[0]
        csrf = form.get("csrf", [""])[0]
        decision = form.get("decision", [""])[0]
        if not ID_RE.match(aid) or decision not in ("approve", "deny"):
            self._err("bad request", 400)
            return
        src = os.path.join(pending_dir(), aid + ".json")
        if not os.path.exists(src):
            self._err("not found or already answered", 404)
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
            self._err("This approval expired and was removed.", 410)
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
        # Finding 60: on approve, mint the grant via the single writer
        # BEFORE moving to consumed/. Finding 64: validate the tuple.
        if decision == "approve":
            name = it.get("credential")
            host = it.get("host")
            method = (it.get("method") or "").upper()
            if not name or not host or not method:
                audit_log("grant-refused", self.client_address[0], login,
                          "id=%s reason=missing credential/host/method" % aid)
                self._err("Cannot mint grant: missing fields.", 400)
                return
            # Call the single writer (finding 60).
            try:
                out = subprocess.run(
                    [GRANT_WRITER, "add",
                     "--credential", name,
                     "--host", host,
                     "--method", method,
                     "--path-prefix", it.get("path_prefix") or "/",
                     "--approval-id", aid,
                     "--scope", it.get("scope") or "",
                     "--job", it.get("job") or ""],
                    capture_output=True, text=True, timeout=15)
                if out.returncode != 0:
                    audit_log("grant-failed", self.client_address[0], login,
                              "id=%s err=%s" % (aid, out.stderr.strip()))
                    self._err("Grant minting failed.", 500)
                    return
            except Exception as e:
                audit_log("grant-failed", self.client_address[0], login,
                          "id=%s err=%s" % (aid, e))
                self._err("Grant minting failed.", 500)
                return
        # Finding 56: one-way. Write to answered/, then move to consumed/.
        # The proxy never re-derives grants from these files.
        dst = os.path.join(answered_dir(), aid + ".json")
        tmp = dst + ".tmp"
        with open(tmp, "w") as f:
            json.dump(it, f, indent=2)
        os.replace(tmp, dst)
        os.remove(src)
        try:
            os.replace(dst, os.path.join(consumed_dir(), aid + ".json"))
        except OSError:
            pass
        audit_log("answer", self.client_address[0], login,
                  "id=%s decision=%s requester=%s"
                  % (aid, decision, requester))
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *args):
        pass  # refusals go to the audit log; answers are in answered/


def _version_payload():
    """Unit-testable /api/version payload (docs/VERSIONING.md)."""
    return {"service": "confirmd", "version": SPARKVM_VERSION,
            "handler": Handler.server_version}


def main():
    # Finding 67: print the resolved origins at startup so the journal
    # shows them; a missing ts.net name must be visible, not silent.
    print("confirmd PAGE_ORIGINS=%s" % sorted(PAGE_ORIGINS), flush=True)
    print("confirmd version=%s" % SPARKVM_VERSION, flush=True)
    for d in (pending_dir(), answered_dir(), consumed_dir()):
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
