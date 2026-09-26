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
  CONFIRM_VAPID_KEYS  VAPID keypair JSON for push notifications, generated
                      with `confirm/push.py --gen-keys` (default
                      /home/swapd/confirmd/vapid.json). Unset/missing =>
                      push disabled; the page works without it.
  CONFIRM_PUSH_SUBS   push subscription store path (default
                      $CONFIRM_DIR/push-subscriptions.json)
  CONFIRM_VAPID_SUB   VAPID subject contact, e.g. mailto:owner@example.com
                      (default mailto:confirmd@localhost)

Re-open (H20): a denied approval can be re-filed from its answered-history
card (POST /reopen) — the recovery story for a mis-tapped Deny. The
re-filed item gets a NEW approval id (aids never come back — see
_evict_aid_lock), the original request fields, the requester's original
deadline kept verbatim (expired requests are refused with 410), and
`reopened_from`/`original_requester` lineage; the owner is re-pushed
through the H14 queue. Re-open is idempotent per denied item: a repeat
POST while the re-filed item is still pending redirects to it instead
of filing a duplicate. Pre-H10 this is
single-tenant by confirmd's design; the lineage fields make tenant
scoping additive later.
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
import threading
import time
import urllib.parse
from collections import defaultdict
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
except Exception:
    # Best-effort stamp (SyntaxError included): a broken reader or VERSION
    # must never break the component's startup.
    SPARKVM_VERSION = "0.0.0-unknown"
# --- end version stamping ---

PORT = int(os.environ.get("CONFIRM_PORT", "8443"))
CERT = os.environ.get("CONFIRM_CERT", "/home/swapd/confirmd/cert.crt")
KEY = os.environ.get("CONFIRM_KEY", "/home/swapd/confirmd/key.pem")
OWNER = os.environ.get("CONFIRM_OWNER", "ntindle@github")
APPROVALS = os.environ.get("CONFIRM_DIR", "/home/swapd/approvals")
AUDIT = os.environ.get("CONFIRM_AUDIT", "/home/swapd/confirmd/audit.log")

# H2 (GitHub #2): VAPID push notifications via confirm/push.py. Optional
# and fail-closed: enabled only when CONFIRM_VAPID_KEYS names a readable
# operator-generated keypair file AND the `cryptography` package imports.
# Disabled => /api/push/config reports enabled=false, the subscribe
# endpoints 503, and no push ever fires. The approvals page is unaffected.
try:
    import push as _push_mod  # noqa: F401 (sibling file, installed next to this one)
    _PUSH = _push_mod.PushSender.default()
    PUSH_ENABLED = _PUSH.enabled
    # Product review: surface WHY push is disabled, not just that it is.
    PUSH_DISABLED_REASON = _PUSH.disabled_reason
    if not PUSH_ENABLED:
        _PUSH = None
except Exception as _push_import_err:
    _push_mod = None
    _PUSH = None
    PUSH_ENABLED = False
    PUSH_DISABLED_REASON = "import-failed: %s" % _push_import_err

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

# Issue #75: a small ring of valid CSRF nonces per approval. The old code
# kept a single `_csrf` slot and rewrote it on every GET, so a second tab
# (or back-button + resubmit) 403'd the first tab's form AND audit-logged
# it as a CSRF violation — false positives that desensitized review of
# real violations. Ring entries are {nonce, ts}; only the newest few are
# accepted. Tradeoff (arch review R1): a larger ring keeps more tabs alive
# but widens the concurrent-live-nonce window for the /answer race (#71) —
# hence the conservative defaults, and env knobs for the operator.
def _env_int(name, default, minimum):
    try:
        v = int(os.environ.get(name, str(default)))
    except ValueError:
        v = default
    return max(v, minimum)

_CSRF_RING_SIZE = _env_int("CONFIRM_CSRF_RING_SIZE", 3, 1)
_CSRF_RING_TTL = _env_int("CONFIRM_CSRF_RING_TTL", 15 * 60, 60)  # seconds


# Arch review B2/B3: per-approval in-process lock. ThreadingHTTPServer runs
# one thread per request, so the GET load->mint->write-back sequence and
# the POST check->mint->consume sequence must serialize per approval id —
# otherwise concurrent GETs lose a minted nonce (last-writer-wins) and
# concurrent POSTs race into the grant path (#71). Single-instance scope is
# honest here (confirmd runs as one service); a multi-replica confirmd
# would need the atomicity story redone (flock on the item file) — tracked
# as a #69 child issue.
# Lifecycle: the entry is evicted whenever the item leaves pending —
# answered, expired-reaped under the per-aid lock (GET/POST paths and —
# since issue #233 — load_pending()'s Finding-58 render reap). Without
# eviction the dict would grow by one entry per approval for the
# daemon's whole lifetime.
_aid_locks = defaultdict(threading.Lock)


def _aid_lock(aid):
    return _aid_locks[aid]


def _evict_aid_lock(aid):
    """Drop the per-aid lock once its item has left pending. Safe to call
    while holding the lock: a thread that grabbed the object before
    eviction still serializes on it and then sees the file gone (404);
    threads arriving later get a fresh lock. Assumes an aid's item never
    comes back — aids are 64-bit random (`uuid.uuid4().hex[:16]` in
    confirm/confirm-request), so reuse is a 2^-64 event. If it ever
    happened, an evicted entry could alias a live item's lock, and
    `_sweep_answered`'s `os.replace` could clobber `consumed/<aid>.json`
    history — the invariant has teeth, stated once here."""
    _aid_locks.pop(aid, None)


# H20: re-open nonces. A denied approval's answered-history card carries a
# "Re-open" form; its POST to /reopen needs the same per-item CSRF
# discipline as /answer (finding 48). The nonce cannot live in the item
# file: the item is consumed history, and mutating history files for live
# nonces would corrupt the audit trail. So it lives in this in-memory
# ring keyed by the ORIGINAL (denied) aid — minted when a deny item's
# card renders, evicted on successful re-open (one-shot). Single-instance
# scope is honest here: the same caveat as _aid_locks (a multi-replica
# confirmd would need a shared store — tracked under #69).
_reopen_nonces = {}
_REOPEN_NONCE_TTL = 15 * 60
_REOPEN_NONCE_CAP = 4096


def _mint_reopen_nonce(aid):
    """Mint (or re-issue the live) re-open nonce for a denied aid. The
    nonce is stable across renders until it expires or is used, so the
    5 s answered-feed poller never invalidates a form it already built.
    One-shot: a successful re-open evicts it (_evict_reopen_nonce).
    Concurrent renders can last-writer-wins the slot (same shape as
    _mint_csrf_nonce) — the stranded form 403s and self-heals on the
    next poll; single-tenant, rare, benign."""
    now = time.time()
    e = _reopen_nonces.get(aid)
    if e and now - e["ts"] <= _REOPEN_NONCE_TTL:
        return e["nonce"]
    nonce = secrets.token_urlsafe(24)
    _reopen_nonces[aid] = {"nonce": nonce, "ts": now}
    # Issue #77 (L10) hygiene: keep the ring bounded like the whois cache.
    while len(_reopen_nonces) > _REOPEN_NONCE_CAP:
        _reopen_nonces.pop(next(iter(_reopen_nonces)))
    return nonce


def _reopen_nonce_ok(aid, csrf):
    """True if csrf is the live re-open nonce for aid. Well-formed but
    unknown/expired nonces are False — the caller audits them under the
    same separable "csrf:stale-nonce" event as /answer (issue #75)."""
    if not NONCE_RE.match(csrf or ""):
        return False
    e = _reopen_nonces.get(aid)
    return bool(e and time.time() - e["ts"] <= _REOPEN_NONCE_TTL
                and secrets.compare_digest(e["nonce"], csrf))


def _evict_reopen_nonce(aid):
    """Drop the re-open nonce once its item is re-filed. One-shot: the
    loser of a re-open race must see stale-nonce, not a second filing."""
    _reopen_nonces.pop(aid, None)


def _pending_reopened_aid(aid):
    """H20: idempotent re-open. If this denied aid was already re-filed
    and the new item is still pending (and unexpired), return its aid so
    a repeat POST redirects to it instead of filing a duplicate. The
    deny card re-mints a fresh nonce on every render, so a second POST
    for the same deny is normal (double-tap, deliberate repeat) — not
    an attack. Returns None when no live re-opened item exists."""
    try:
        names = os.listdir(pending_dir())
    except OSError:
        return None
    now = datetime.now(timezone.utc)
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(pending_dir(), name)) as f:
                it = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(it, dict) or it.get("reopened_from") != aid:
            continue
        exp = _parse_expiry(it.get("expires"))
        if exp is not None and now >= exp:
            # The earlier re-open already expired; a repeat now is a new
            # request, not a duplicate.
            continue
        new_aid = it.get("id") or name[:-5]
        if isinstance(new_aid, str) and new_aid:
            return new_aid
    return None


def _push_enqueue_reopen(new_aid, summary):
    """H20: re-push the owner when a denied approval is re-opened, via
    the H14 push queue. Fail-open and off the hot path — exactly the H2
    filing guarantee: a queue failure must never lose the re-opened
    approval (the page itself is the fallback; the queue only
    accelerates the summons)."""
    mod = _push_mod  # None when the push import failed; page still works
    if mod is None:
        return

    def _run():
        try:
            res = mod.PushQueue.default().enqueue(
                {"id": new_aid, "summary": summary})
            if res not in ("queued", "duplicate", "notified"):
                print("confirmd WARNING: push enqueue returned %s for "
                      "re-opened %s" % (res, new_aid), flush=True)
        except Exception:
            print("confirmd WARNING: push enqueue failed for re-opened %s"
                  % new_aid, flush=True)
    threading.Thread(target=_run, name="confirmd-reopen-push",
                     daemon=True).start()


def _mint_csrf_nonce(it):
    """Mint a fresh CSRF nonce for an approval item, keeping a small ring
    of recent nonces. Migrates the legacy single `_csrf` slot into the
    ring on first use."""
    now = time.time()
    ring = [e for e in (it.get("_csrf_nonces") or [])
            if isinstance(e, dict) and isinstance(e.get("ts"), (int, float))
            and now - e["ts"] <= _CSRF_RING_TTL]
    legacy = it.pop("_csrf", None)
    if legacy and legacy not in {e.get("nonce") for e in ring}:
        ring.append({"nonce": legacy, "ts": now})
    nonce = secrets.token_urlsafe(24)
    ring.append({"nonce": nonce, "ts": now})
    it["_csrf_nonces"] = ring[-_CSRF_RING_SIZE:]
    return nonce


def _csrf_nonce_ok(it, csrf):
    """True if `csrf` is a well-formed, unexpired nonce in the item's ring
    (or its legacy single slot). The TTL is enforced at verification time
    too, not only at mint (security review): a clock-jump-backward or a
    never-re-GET'd item cannot keep a nonce valid past the TTL."""
    if not NONCE_RE.match(csrf or ""):
        return False
    now = time.time()

    def _fresh(e):
        ts = e.get("ts")
        return (isinstance(ts, (int, float))
                and now - ts <= _CSRF_RING_TTL)

    ring = it.get("_csrf_nonces") or []
    candidates = {e.get("nonce") for e in ring
                  if isinstance(e, dict) and _fresh(e)}
    if it.get("_csrf"):
        candidates.add(it["_csrf"])
    return csrf in candidates

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
    # Issue #77 (L10): hygiene cap on the otherwise-unbounded whois cache.
    # Keyed by peer IP so it is tailnet-bounded, but a leak is a leak —
    # evict oldest-inserted past the cap. Eviction cannot cause staleness
    # beyond the existing 60s TTL: a miss just re-runs whois (arch R3).
    while len(_whois_cache) > 4096:
        _whois_cache.pop(next(iter(_whois_cache)))
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
    """Finding 47/53(e): every refusal leaves a trail with peer and login.
    Event policy: malformed/missing CSRF nonces are logged as violations
    ("csrf: bad nonce"); well-formed but stale/unknown nonces are logged
    under the separable "csrf:stale-nonce" event (issue #75) so reviewer
    signal stays clean without dropping the trail. Issue #233: a pending
    file that vanishes between grant mint and consumption is logged as
    the distinct "answer-raced-expiry" event — never as "answer/approve"
    — so the trail cannot self-contradict. Arch finding (sentinel
    deep-read, 2026-09-24): the audit write used to swallow OSError
    silently while the swap proxy fails the operation closed when its
    audit log cannot be written (finding 198) — a full disk ate the
    approvals trail without a signal. confirmd cannot fail the request
    the same way (the audit call happens after the decision), so the
    except path emits to stderr (naming the lost event), which lands in
    the journal under systemd — the trail gap is operator-visible."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with open(AUDIT, "a", encoding="utf-8") as f:
            f.write("ts=%s event=%s peer=%s login=%s %s\n"
                    % (ts, event, peer, login or "-", detail))
    except OSError as e:
        print("confirmd: cannot write audit log: %s (lost event=%s peer=%s login=%s)"
              % (e, event, peer, login or "-"), file=sys.stderr)


def pending_dir():
    d = os.path.join(APPROVALS, "pending")
    os.makedirs(d, exist_ok=True)
    return d


def answered_dir():
    d = os.path.join(APPROVALS, "answered")
    # Issue #77 (L5): create at the use site too, so a runtime-deleted
    # answered/ cannot raise uncaught FileNotFoundError in /answer.
    os.makedirs(d, exist_ok=True)
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
                # Issue #233: the render reap mutates pending/ while the
                # answer critical section holds this same per-aid lock
                # for the whole check->mint->consume window (grant
                # subprocess included). Reaping outside the lock let the
                # reap remove the file mid-mint, leaving _answer_locked's
                # bare os.remove(src) to raise an uncaught
                # FileNotFoundError into the owner's connection — and let
                # GET's nonce write-back recreate a file the reap had
                # just removed (os.replace resurrects it). Serializing
                # the reap on the per-aid lock closes both. Deadlock
                # audit: the reap holds at most this one aid lock and
                # never nests; GET/POST each hold exactly one; the grant
                # subprocess acquires no locks — no lock-ordering hazard.
                aid = fn[:-len(".json")]
                with _aid_lock(aid):
                    try:
                        os.remove(p)
                    except OSError:
                        # Lost the race with the answer path, which
                        # consumed the item while we waited on the lock —
                        # the expected case is FileNotFoundError. Any
                        # other OSError is fail-safe here too: the item is
                        # skipped from this render and the remove is
                        # retried on the next one.
                        pass
                    # Arch 2026-09-21: keep the per-aid lock registry
                    # bounded — the item left pending here too. Evicting
                    # unconditionally is safe: aids are never reused and
                    # an expired item stays expired.
                    _evict_aid_lock(aid)
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
    # Issue #240 trivia: load_pending()'s Finding-58 reap uses
    # `now >= exp`; the `>` here is unified to the same boundary so an
    # item is expired exactly at its instant everywhere.
    exp = _parse_expiry(item.get("expires"))
    return exp is not None and datetime.now(timezone.utc) >= exp


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
/* H20: the re-open action is a neutral secondary button — neither an
approval (green) nor a denial (red). */
.btn-neutral{background:transparent;color:#1a73e8;border-color:#1a73e8}
.btn-neutral:active{background:#e8f0fe}
@media(prefers-color-scheme:dark){
.btn-neutral{color:#8ab4f8;border-color:#8ab4f8}
.btn-neutral:active{background:#1f2a3a}}
.reopen{margin:10px 0 2px}
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
  // H20: re-open form for denied items (mirrors the server-rendered card).
  if(dec==="deny"&&validId(id)&&it.reopen_csrf){
    var f=document.createElement("form");
    f.method="post";f.action="/reopen";f.className="reopen";
    [["id",id],["csrf",String(it.reopen_csrf)]].forEach(function(p){
      var inp=document.createElement("input");
      inp.type="hidden";inp.name=p[0];inp.value=p[1];f.appendChild(inp);
    });
    var b=document.createElement("button");
    b.type="submit";b.className="btn btn-neutral";
    b.setAttribute("aria-label","Re-open this request "+id);
    b.textContent="Re-open this request";f.appendChild(b);
    c.appendChild(f);
  }
  return c;
}
function renderAnswered(list,items){
  // H20: don't rebuild while the owner is mid-click on a re-open form —
  // a DOM swap between mousedown and mouseup would swallow the submit.
  // The next 5 s poll picks up the change instead.
  if(list.querySelector("form.reopen:hover,form.reopen:focus-within"))
    return;
  keyedUpdate(list,items,answeredCard,function(it){return String(it.id||"?");},
    "No answered approvals yet.");
}
</script>"""


# H2 (GitHub #2): the service worker that shows push notifications.
# Served at /sw.js under the same owner auth as the page (the fetch
# comes from the owner's browser, so _auth passes). Registered with
# scope = this origin, so notification taps open /approval/<id> on the
# same origin the page was served from (IP or ts.net name — no origin
# confusion in the push payload).
_SW_JS = """"use strict";
self.addEventListener("push", function(event) {
  var data = {};
  try { data = event.data.json(); } catch (e) { /* unencrypted/no body */ }
  var title = data.title || "Approval needed";
  var aid = data.approval_id || "";
  // Per-approval tag: multiple pending approvals stack as separate
  // notifications. (No renotify: each tag is pushed exactly once — the
  // notified log makes re-alerts impossible, so claiming it would lie.)
  var options = {
    body: data.body || "Open confirmd to review.",
    tag: aid ? ("approval-" + aid) : "approval",
    data: { url: aid ? ("/approval/" + aid) : "/" }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});
self.addEventListener("notificationclick", function(event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(clients.openWindow(url));
});
"""


# H2: page-side push subscription UX. The button starts hidden and is
# revealed only when the browser supports push AND the server reports
# push enabled. Subscribing POSTs the PushSubscription to
# /api/push/subscribe; disabling removes it server-side too.
_PUSH_JS = """<script>
"use strict";
(function(){
  var btn=document.getElementById("pushBtn");
  var st=document.getElementById("pushStatus");
  function say(t){ if(st) st.textContent=t; }
  function b64ToU8(s){
    s=String(s).replace(/-/g, "+").replace(/_/g, "/");
    while(s.length%4) s+="=";
    var b=atob(s), a=new Uint8Array(b.length);
    for(var i=0;i<b.length;i++) a[i]=b.charCodeAt(i);
    return a;
  }
  if(!("serviceWorker" in navigator) || !("PushManager" in window)){
    // Design review: on iOS, Web Push exists but requires the page to be
    // added to the home screen first — PushManager is absent otherwise.
    // Say that instead of the misleading "not supported".
    var ua = navigator.userAgent || "";
    if(/iPhone|iPad|iPod/.test(ua)){
      say("on iPhone/iPad: add this page to your home screen, then open " +
          "it from there to enable notifications");
    } else {
      say("push not supported in this browser");
    }
    return;
  }
  fetch("/api/push/config",{credentials:"same-origin"})
    .then(function(r){ return r.json(); })
    .then(function(cfg){
      if(!cfg.enabled || !cfg.public_key){
        // Product review: name the reason and the doc so the
        // human-who-is-also-the-operator can fix it.
        say("push not configured on this box" +
            (cfg.disabled_reason ? (": " + cfg.disabled_reason) : "") +
            " — see docs/PUSH_NOTIFICATIONS.md");
        return;
      }
      btn.hidden=false;
      return navigator.serviceWorker.register("/sw.js").then(function(reg){
        return reg.pushManager.getSubscription().then(function(sub){
          if(sub){
            say("notifications on");
            btn.textContent="Disable notifications";
            btn.onclick=function(){
              sub.unsubscribe().then(function(){
                return fetch("/api/push/unsubscribe",{method:"POST",
                  headers:{"Content-Type":"application/json"},
                  body:JSON.stringify({endpoint:sub.endpoint})});
              }).then(function(){ say("notifications off"); location.reload(); })
                .catch(function(e){ say("could not disable: "+e.message); });
            };
            return;
          }
          btn.onclick=function(){
            say("subscribing\\u2026");
            reg.pushManager.subscribe({userVisibleOnly:true,
                applicationServerKey:b64ToU8(cfg.public_key)})
              .then(function(sub){
                var j=sub.toJSON();
                return fetch("/api/push/subscribe",{method:"POST",
                  headers:{"Content-Type":"application/json"},
                  body:JSON.stringify({endpoint:sub.endpoint,keys:j.keys})});
              })
              .then(function(r){
                if(!r.ok) throw new Error("server refused ("+r.status+")");
                say("notifications on"); location.reload();
              })
              .catch(function(e){
                // Design review: the permission-denied path needs a
                // recovery hint, not just the raw DOMException.
                var msg = String((e && e.message) || e);
                if(e && e.name === "NotAllowedError"){
                  msg += " \u2014 allow notifications for this site in " +
                         "the browser\u2019s site settings, then retry";
                }
                say("could not enable: " + msg);
              });
          };
        });
      });
    })
    .catch(function(){
      say("push unavailable \u2014 the page itself may be unreachable, " +
          "try reloading");
    });
})();
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
    random hex, so filename order is NOT chronological (engineering).

    Perf (issue #214 / G2): the 5 s /api/answered poll used to list,
    parse, and sort EVERY consumed/ file (up to _CONSUMED_KEEP = 1000),
    so per-poll parse cost was O(consumed-dir). Directory entries are
    now ordered by mtime and only the 2x-feed-cap newest candidates are
    parsed and re-sorted by answered_at — answered_at is stamped in
    memory just before the answered file is written (up to ~15 s of
    grant minting may intervene) and rename(2) preserves mtime, so
    mtime lags answer time by seconds at most. The listdir + getmtime
    stat pass is still O(dir) but cheap (<=1000 stats); only file
    reads and JSON parses are constant-bounded. A pathological
    mtime/answered_at skew spanning the whole 200-file candidate pool
    could push a live feed item out — in practice the two orders
    coincide."""
    d = consumed_dir()
    entries = []
    for fn in os.listdir(d):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(d, fn)
        try:
            entries.append((os.path.getmtime(p), p))
        except OSError:
            continue
    entries.sort(key=lambda t: t[0], reverse=True)
    items = []
    for _, p in entries[:_ANSWERED_CANDIDATE_LIMIT]:
        try:
            with open(p) as f:
                items.append(json.load(f))
        except Exception:
            continue
    items.sort(key=lambda it: _parse_expiry(it.get("answered_at")) or
               datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items


# Product review (blocker 2): the answered feed is re-polled every 5 s,
# so it is capped — history on disk stays complete.
_ANSWERED_FEED_LIMIT = 100


# Gap G2 (issue #214): _load_answered() parses only this many mtime-newest
# candidates instead of every consumed/ file. 2x the feed cap so an
# mtime/answered_at ordering skew would have to span the whole pool to
# change what the feed shows; the feed still truncates to the cap.
_ANSWERED_CANDIDATE_LIMIT = 2 * _ANSWERED_FEED_LIMIT


# Arch 2026-09-21: the answered feed shows the 100 most recent, but
# consumed/ grew without bound — one file per approval for the daemon's
# whole lifetime — while every 5 s /api/answered poll (and every
# /answered render) re-listed, re-parsed, and re-sorted ALL of them.
# Keep the newest N on disk; the audit log stays the durable trail.
# Minimum 100 keeps the on-disk history coherent with the feed cap.
_CONSUMED_KEEP = _env_int("CONFIRM_CONSUMED_KEEP", 1000, 100)


# Issue #233 hygiene: answered/*.json files stranded by a failed
# answered->consumed move (the OSError path journals a warning and moves
# on, with no retry — or a crash between the two) never enter consumed/,
# so _load_answered() never sees them and they grow unbounded. Sweep
# files older than the grace period into consumed/. The grace period
# keeps an in-flight answer (seconds) far away from the sweep (a day by
# default), and an aid's answered file is written exactly once, so no
# concurrent answer can collide on the same name.
_ANSWERED_SWEEP_GRACE_S = _env_int("CONFIRM_ANSWERED_SWEEP_GRACE_S",
                                   86400, 3600)


def _sweep_answered(grace=None):
    """Move answered/ strays older than `grace` seconds to consumed/."""
    if grace is None:
        grace = _ANSWERED_SWEEP_GRACE_S
    cutoff = time.time() - grace
    src_d = answered_dir()
    dst_d = consumed_dir()
    try:
        names = os.listdir(src_d)
    except OSError:
        return
    for fn in names:
        if not fn.endswith(".json"):
            continue
        p = os.path.join(src_d, fn)
        try:
            if os.path.getmtime(p) > cutoff:
                continue
            os.replace(p, os.path.join(dst_d, fn))
        except OSError:
            continue


def _prune_consumed(limit=None):
    """Delete consumed/ history beyond the newest `limit` files (by mtime).

    Called after each answer is consumed. Pruning is mtime-ordered on
    purpose: it never parses file contents, so the prune itself stays
    cheap even as history grows. Races with a concurrent answer are
    benign — only the oldest files are ever deletion candidates, and a
    lost race surfaces as FileNotFoundError, which is tolerated."""
    if limit is None:
        limit = _CONSUMED_KEEP
    d = consumed_dir()
    try:
        entries = []
        for fn in os.listdir(d):
            if not fn.endswith(".json"):
                continue
            try:
                entries.append((os.path.getmtime(os.path.join(d, fn)), fn))
            except OSError:
                continue
        entries.sort()
    except OSError:
        return
    for _, fn in entries[:max(0, len(entries) - limit)]:
        try:
            os.remove(os.path.join(d, fn))
        except OSError:
            pass


def _answered_api_item(it):
    """Issue #1: JSON surface for the answered-history poller.
    Allowlisted fields only. H20: a denied item additionally carries its
    re-open CSRF nonce so the answered card can offer the re-open form —
    non-deny items carry no nonce."""
    out = {
        "id": str(it.get("id", "")),
        "summary": str(it.get("summary", "")),
        "kind": str(it.get("kind", "")),
        "decision": str(it.get("decision", "")),
        "answered_by": str(it.get("answered_by", "")),
        "answered_at": str(it.get("answered_at", "")),
    }
    if out["decision"] == "deny" and ID_RE.match(out["id"]):
        out["reopen_csrf"] = _mint_reopen_nonce(out["id"])
    return out


def _meta_line_html(parts):
    """Like _meta_line, but parts are already-escaped HTML (e.g. from
    _fmt_time). The escape discipline still lives in one place."""
    parts = [p for p in parts if p]
    if not parts:
        return ""
    return '<div class="meta">%s</div>' % " · ".join(parts)


def _meta_line(parts):
    """Engineering review: one named helper for the "kind · filed ·
    expires" line, so the escape ordering is reviewable in one place."""
    return _meta_line_html([html.escape(str(p)) for p in parts])


def _fmt_time(iso):
    """Design review: the detail page shows filed/expires in the same short
    local style as the pending card (which formats them client-side with
    fmtTime). The server cannot know the viewer's timezone, so the ISO
    value is emitted into a span and formatted by a small script on the
    page — never rendered raw. The raw ISO stays as the span's text so
    no-JS approvers still see the values (the consent form works without
    JS, so no-JS is a supported path)."""
    esc = html.escape(str(iso), quote=True)
    return '<span data-iso="%s">%s</span>' % (esc, esc)


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
        # H20: a denied approval can be re-filed from its card (the
        # mis-tapped-Deny recovery). The nonce is minted per deny item
        # and verified one-shot on POST /reopen.
        reopen = ""
        aid = str(it.get("id", ""))
        if dec == "deny" and ID_RE.match(aid):
            reopen = ('<form method="post" action="/reopen" class="reopen">'
                      '<input type="hidden" name="id" value="%s">'
                      '<input type="hidden" name="csrf" value="%s">'
                      '<button class="btn btn-neutral" type="submit" '
                      'aria-label="Re-open this request %s">'
                      'Re-open this request</button></form>' % (
                          html.escape(aid),
                          html.escape(_mint_reopen_nonce(aid)),
                          html.escape(aid)))
        cards.append(
            '<div class="card"><h2>%s%s</h2>'
            '<div class="summary">%s</div>%s%s</div>' % (
                html.escape(str(it.get("id", "?"))), badge,
                html.escape(str(it.get("summary", ""))), meta, reopen))
    return "".join(cards)


class Handler(BaseHTTPRequestHandler):
    server_version = "confirmd/1"

    # Issue #77 (M8): per-socket timeout — a tailnet peer slow-lorising a
    # request body must not hold a handler thread forever. StreamRequestHandler
    # applies this to every accepted socket in setup().
    timeout = 10

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
        # Issue #77 (L3): hardening headers on HTML responses — nosniff
        # so a content-type confusion cannot turn an approval page into
        # an executed script; same-origin referrer so pending-approval
        # URLs never leak to third parties via the Referer header.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
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
            filed.append("filed %s" % _fmt_time(it["created"]))
        if it.get("expires"):
            filed.append("expires %s" % _fmt_time(it["expires"]))
        reopened = ""
        if it.get("reopened_from"):
            # H20: provenance at decision time — the owner must see that
            # this pending item is a re-filed denial, not a fresh
            # request. Reuses the callout style; the lineage itself is
            # system-recorded, not requester-supplied.
            reopened = ('<div class="untrusted"><b>Re-opened from a denied '
                        'request:</b> this is a new pending approval for '
                        'the same request (denied approval '
                        '<code>%s</code>).</div>'
                        % html.escape(str(it["reopened_from"])))
        return reopened + _meta_line_html(filed) + table + untrusted

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
        # H2 (GitHub #2): push subscription surface. The public key is
        # public by design (the browser needs it to subscribe); the
        # endpoint stays owner-authenticated like the rest of the page.
        if self.path == "/api/push/config":
            self._send_json({"enabled": PUSH_ENABLED,
                             "public_key": (_PUSH.public_key_b64u
                                            if _PUSH else None),
                             "disabled_reason": PUSH_DISABLED_REASON})
            return
        if self.path == "/sw.js":
            # The service worker is fetched by the owner's browser from
            # the same origin, so _auth (already run) passes. Served
            # with no-store: a stale worker would show stale copy.
            data = _SW_JS.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            # Issue #77 (L3): same hardening headers as the HTML pages —
            # nosniff for the fetched worker, same-origin referrer.
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/":
            body = ('<h1>Pending approvals</h1>'
                    '<p class="sub" id="updated" role="status">live — checking every 5 s</p>'
                    '<div id="items">%s</div>'
                    # H2: push subscription UX. The button stays hidden
                    # until _PUSH_JS confirms browser support and the
                    # server reports push enabled.
                    '<p class="pushrow"><button class="btn" id="pushBtn" '
                    'type="button" hidden>Enable notifications</button> '
                    '<span id="pushStatus" class="sub" '
                    'role="status"></span></p>'
                    '<p class="nav"><a href="/answered">answered history</a></p>'
                    % _render_pending_list(load_pending()))
            self._send_html(body, title="Pending approvals",
                            script=POLL_JS + _PUSH_JS
                            + '<script>startPoll("/api/pending",'
                            'renderPending);</script>')
        elif self.path == "/answered":
            body = ('<h1>Answered approvals</h1>'
                    '<p class="sub" role="status">showing the 100 most recent'
                    ' · <span id="updated">live — checking every 5 s</span></p>'
                    '<p class="sub">A request denied by mistake can be '
                    're-opened from its card — it is re-filed as a new '
                    'pending approval. After re-opening, approve the new '
                    'request, then tell the agent to retry.</p>'
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
            # Arch review B3: the load->mint->write-back sequence runs under
            # the per-aid lock — concurrent GETs must not lose each other's
            # minted nonce (last-writer-wins).
            with _aid_lock(aid):
                p = os.path.join(pending_dir(), aid + ".json")
                if not os.path.exists(p):
                    # Issue #231: the item left pending (or never
                    # existed) — don't let the lock registry grow on the
                    # negative path either.
                    _evict_aid_lock(aid)
                    self._err("not found or already answered", 404)
                    return
                try:
                    with open(p) as f:
                        it = json.load(f)
                except (OSError, ValueError):
                    # Issue #77 (L5): a corrupt/torn pending file must not
                    # raise an uncaught exception into the page.
                    # Issue #231: evict here too.
                    _evict_aid_lock(aid)
                    self._err("not found or already answered", 404)
                    return
                if is_expired(it):
                    # Finding 53(a): refuse with a message, and reap.
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                    _evict_aid_lock(aid)
                    audit_log("expired-reaped", self.client_address[0], login,
                              "id=%s" % aid)
                    self._err("This approval expired and was removed.", 410)
                    return
                # Finding 48 + issue #75: mint a CSRF nonce, keeping a small
                # ring of recent nonces in the pending file (a fresh GET in a
                # second tab must not invalidate the first tab's form).
                nonce = _mint_csrf_nonce(it)
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
                    "</script>"
                    # Design review: format filed/expires in the same short
                    # local style as the pending card's fmtTime. The server
                    # cannot know the viewer's timezone, so _fmt_time emits
                    # the ISO into a span and this formats it client-side.
                    # IIFE on purpose: no JS globals (cf. the `var b`
                    # collision the demo capture script works around).
                    "<script>"
                    "(function(){"
                    "document.querySelectorAll('span[data-iso]').forEach("
                    "function(s){"
                    "var d=new Date(s.getAttribute('data-iso'));"
                    "s.textContent=isNaN(d)?s.getAttribute('data-iso'):"
                    "d.toLocaleString();});"
                    "})();"
                    "</script>"
                    # Design B1: dismiss this approval's notification when
                    # the owner answers — otherwise a dead notification
                    # lingers and taps through to a 404 ("already
                    # answered"). Best-effort: the POST still answers even
                    # if the service worker is unreachable.
                    "<script>"
                    '"use strict";'
                    '(function(){'
                    'var f=document.querySelector(\'form[action="/answer"]\');'
                    'var i=document.querySelector(\'input[name="id"]\');'
                    'if(!f||!i||!("serviceWorker" in navigator))return;'
                    'var aid=i.value;'
                    'f.addEventListener("submit",function(){'
                    'try{'
                    'navigator.serviceWorker.ready.then(function(r){'
                    'return r.getNotifications({tag:"approval-"+aid});'
                    '}).then(function(ns){'
                    'ns.forEach(function(n){n.close();});'
                    '}).catch(function(){});'
                    '}catch(e){}'
                    '});'
                    '})();'
                    "</script>"
                    # Product nit: the deep-link target is where
                    # notification taps land, so the push controls live
                    # here too — not only on the pending page.
                    '<p class="pushrow"><button class="btn" id="pushBtn" '
                    'type="button" hidden>Enable notifications</button> '
                    '<span id="pushStatus" class="sub" '
                    'role="status"></span></p>') % (
                        html.escape(aid), self._render_item(it),
                        html.escape(aid), html.escape(nonce))
            self._send_html(body, title="Approval %s" % aid,
                            script=_PUSH_JS)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        login = self._auth()
        if login is None:
            return
        if self.path not in ("/answer", "/reopen", "/api/push/subscribe",
                             "/api/push/unsubscribe"):
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
        # H2: push subscription management (owner-auth + CSRF checks
        # above apply identically).
        if self.path in ("/api/push/subscribe", "/api/push/unsubscribe"):
            return self._push_endpoint(login, length)
        form = urllib.parse.parse_qs(
            self.rfile.read(length).decode(errors="replace"))
        aid = form.get("id", [""])[0]
        csrf = form.get("csrf", [""])[0]
        # H20: re-opening a denied approval re-files it as a new pending
        # item — there is no decision to validate, and the nonce lives in
        # the re-open ring (the item is consumed history, not pending).
        # The per-aid lock on the ORIGINAL aid serializes concurrent
        # re-opens of the same denied item (one-shot nonce; the loser
        # sees stale-nonce).
        if self.path == "/reopen":
            if not ID_RE.match(aid):
                self._err("bad request", 400)
                return
            with _aid_lock(aid):
                return self._reopen_locked(login, aid, csrf)
        decision = form.get("decision", [""])[0]
        if not ID_RE.match(aid) or decision not in ("approve", "deny"):
            self._err("bad request", 400)
            return
        # Arch review B2: serialize the whole check->mint->consume
        # section per approval id. Concurrent POSTs with two valid ring
        # nonces must not both enter the grant path (#71); the loser of
        # the race now sees a clean 404 ("not found or already
        # answered") instead of an uncaught FileNotFoundError from
        # os.remove(src). Issue #233: the protection domain covers the
        # Finding-58 render reap too — load_pending()'s expiry sweep
        # serializes on this same lock, so a mid-mint reap can no longer
        # delete the pending file out from under _answer_locked, and
        # GET's nonce write-back can no longer resurrect a reaped file.
        with _aid_lock(aid):
            return self._answer_locked(login, aid, csrf, decision)

    def _answer_locked(self, login, aid, csrf, decision):
        """POST /answer body. The caller holds _aid_lock(aid); every
        early return inside is a normal handler response."""
        src = os.path.join(pending_dir(), aid + ".json")
        if not os.path.exists(src):
            # Issue #231: same evict-on-negative-path as the GET side.
            _evict_aid_lock(aid)
            self._err("not found or already answered", 404)
            return
        try:
            with open(src) as f:
                it = json.load(f)
        except (OSError, ValueError):
            # Issue #77 (L5): a corrupt/torn pending file must not raise
            # an uncaught exception into the POST path either.
            # Issue #231: evict here too.
            _evict_aid_lock(aid)
            self._err("not found or already answered", 404)
            return
        # Finding 48 + issue #75: the nonce must be well-formed, unexpired,
        # and belong to the item's nonce ring. Malformed/missing nonces are
        # audited as CSRF violations; a well-formed but stale/unknown nonce
        # (second tab, back-button resubmit) is audited under its own event
        # (arch review B1): attacker-shaped probes are exactly
        # "well-formed but unknown," so the trail stays distinguishable
        # without desensitizing review of real violations.
        if not csrf or not NONCE_RE.match(csrf):
            self._deny(self.client_address[0], login, "csrf: bad nonce")
            return
        if not _csrf_nonce_ok(it, csrf):
            audit_log("csrf:stale-nonce", self.client_address[0], login,
                      "id=%s" % aid)
            self._err("This form is stale — reload the page and try "
                      "again.", 403)
            return
        # Finding 53(a): expired items are refused, not silently denied.
        if is_expired(it):
            try:
                os.remove(src)
            except OSError:
                pass
            _evict_aid_lock(aid)
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
        it.pop("_csrf_nonces", None)
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
        # Issue #240: the expiry instant may have crossed DURING the grant
        # subprocess above (up to 15 s). The #233 os.path.exists check
        # catches removal, not the passage of the expiry instant — so
        # re-evaluate on the in-memory item and refuse honestly rather
        # than recording an answered/ record for an already-expired
        # approval (which would show answer/approve for an item whose
        # expiry had passed at mint time). The grant itself cannot be
        # un-minted (no revoke path in the grant-writer interface), so
        # the fix is the refusal + the distinct trail event, not
        # retroactive revocation.
        if is_expired(it):
            audit_log("answer-expired-mid-mint", self.client_address[0],
                      login, "id=%s decision=%s" % (aid, decision))
            _evict_aid_lock(aid)
            self._err("This approval expired before the grant was "
                      "recorded.", 410)
            return
        # Issue #233 (belt and braces): the render reap now serializes
        # on the same per-aid lock, so it cannot have reaped the file
        # mid-mint — but an operator or another process could still have
        # removed it. If the pending file is gone here, say so honestly:
        # audit the distinct event and refuse, instead of writing an
        # answered/ record for a file we never consumed (which would
        # emit a self-contradictory expired-reaped + answer pair on the
        # credential-grant trust anchor).
        if not os.path.exists(src):
            audit_log("answer-raced-expiry", self.client_address[0],
                      login, "id=%s decision=%s" % (aid, decision))
            # Security review nit: this branch is a terminal path like
            # all the others — evict, don't leak one registry entry per
            # occurrence.
            _evict_aid_lock(aid)
            self._err("This approval was removed before it could be "
                      "recorded.", 410)
            return
        # Finding 56: one-way. Write to answered/, then move to consumed/.
        # The proxy never re-derives grants from these files.
        # (answered_dir() re-creates the dir if it was deleted at
        # runtime — issue #77 (L5).)
        dst = os.path.join(answered_dir(), aid + ".json")
        tmp = dst + ".tmp"
        with open(tmp, "w") as f:
            json.dump(it, f, indent=2)
        os.replace(tmp, dst)
        os.remove(src)
        _evict_aid_lock(aid)
        try:
            os.replace(dst, os.path.join(consumed_dir(), aid + ".json"))
        except OSError as e:
            # Issue #77 (L4): the old code swallowed a failed
            # answered->consumed move silently, losing history. Journal
            # it loudly instead — and when #72 designs the unified
            # audit-failure mechanism, route this through it rather than
            # leaving a second alerting channel (arch review R2).
            print("confirmd WARNING: answered->consumed move failed for "
                  "%s: %s" % (aid, e), flush=True)
        # Arch 2026-09-21: bound the answered-history directory (see
        # _prune_consumed); the audit log stays the durable trail.
        # Issue #233: also sweep answered/ strays into consumed/ so a
        # failed move doesn't leave them invisible forever. No lock
        # needed here: answered files are write-once, and concurrent
        # sweeps race benignly (os.replace + OSError caught). Effective
        # semantics: this sweeps yesterday's strays — a same-run failed
        # move waits out the grace period (journaled loudly via the
        # stdout WARNING), biased toward never sweeping an in-flight
        # file.
        _sweep_answered()
        _prune_consumed()
        audit_log("answer", self.client_address[0], login,
                  "id=%s decision=%s requester=%s"
                  % (aid, decision, requester))
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def _reopen_locked(self, login, aid, csrf):
        """H20: POST /reopen — re-file a denied approval as a new pending
        item and re-push the owner. The caller holds _aid_lock(aid) on the
        ORIGINAL aid, so two concurrent re-opens of the same denied item
        serialize; re-open is idempotent (a repeat POST while the re-filed
        item is still pending 303-redirects to it).

        Design notes:
        - The re-filed item gets a NEW aid. The per-aid lock registry (and
          the push notified-log) assume an aid never comes back — reusing
          the old aid would alias a live item to dead history.
        - The new pending file is written by confirmd itself (owner
          swapd), so Finding 50 sees requester=swapd — a legitimate
          filer. The original requester is preserved in
          `original_requester`, and `reopened_from` carries the lineage;
          the audit log ties old aid to new.
        - Expiry preserves the requester's original deadline, verbatim.
          If that deadline has already passed, the re-open is refused
          (410) — silently granting a fresh window would lie about the
          requester's intent. The owner re-files through the agent for a
          genuinely new request.
        - The denied record is history and stays untouched: the answered
          feed keeps showing the deny honestly, alongside the new pending
          item.
        """
        peer = self.client_address[0]
        # Nonce discipline mirrors /answer (finding 48 + issue #75):
        # malformed is a CSRF violation; well-formed but unknown is the
        # separable stale-nonce event.
        if not csrf or not NONCE_RE.match(csrf):
            self._deny(peer, login, "csrf: bad nonce")
            _evict_aid_lock(aid)
            return
        # The denied record lives in consumed/ (the answer path moves it
        # there immediately) or, for a previous run's failed move, still
        # in answered/ until _sweep_answered() collects it.
        src = os.path.join(consumed_dir(), aid + ".json")
        if not os.path.exists(src):
            src = os.path.join(answered_dir(), aid + ".json")
        try:
            with open(src) as f:
                old = json.load(f)
        except (OSError, ValueError):
            _evict_aid_lock(aid)
            self._err("not found or already answered", 404)
            return
        if not isinstance(old, dict) or ("id" in old
                                         and old["id"] != aid):
            # Defense in depth: a history file whose record disagrees
            # with its filename (or isn't a record at all) must not be
            # re-filed — treat it as corrupt.
            _evict_aid_lock(aid)
            self._err("not found or already answered", 404)
            return
        if old.get("decision") != "deny":
            # An approval, an expiry, or anything else that is not a
            # denial.
            _evict_aid_lock(aid)
            self._err("Only denied approvals can be re-opened.", 400)
            return
        # NOTE: the nonce is deliberately NOT evicted on the 404/400/410
        # paths above — those are terminal for this aid (or the record
        # was never there), so a live nonce is harmless and a retry
        # after a failed sweep still works.
        #
        # Idempotent re-open (Product/QA review): the deny card re-mints
        # a fresh nonce on every render, so a second POST for the same
        # deny is normal — double-tap, or a deliberate repeat. If the
        # earlier re-open is still pending, redirect to it instead of
        # filing a duplicate. This runs before nonce validation on
        # purpose: the double-tap's second POST carries the now-evicted
        # nonce, and this path changes no state, so there is nothing to
        # forge.
        existing = _pending_reopened_aid(aid)
        if existing is not None:
            _evict_reopen_nonce(aid)
            _evict_aid_lock(aid)
            audit_log("reopen-idempotent", peer, login,
                      "id=%s new_id=%s" % (aid, existing))
            self.send_response(303)
            self.send_header("Location", "/approval/" + existing)
            self.end_headers()
            return
        if not _reopen_nonce_ok(aid, csrf):
            audit_log("csrf:stale-nonce", peer, login, "id=%s" % aid)
            _evict_aid_lock(aid)
            self._err("This form is stale — reload the page and try "
                      "again.", 403)
            return
        # Build the re-filed item: the requester's fields, fresh timing,
        # none of the answer's terminal state (_csrf rings, decision,
        # answered_at/by are dropped by omission).
        now = datetime.now(timezone.utc)
        new_aid = secrets.token_hex(8)
        new = {"id": new_aid}
        for key in ("credential", "host", "method", "path_prefix",
                    "scope", "amount", "job", "detail", "summary",
                    "kind"):
            if old.get(key) is not None:
                new[key] = old[key]
        new["created"] = now.isoformat()
        # Expiry preserves the requester's original deadline, verbatim:
        # re-opening must not silently extend a window the requester set.
        # If that deadline has already passed, the request itself has
        # expired — refuse honestly (410).
        old_exp = _parse_expiry(old.get("expires"))
        if old_exp is not None:
            if now >= old_exp:
                _evict_aid_lock(aid)
                audit_log("reopen-expired", peer, login, "id=%s" % aid)
                self._err("The original decision window has already "
                          "passed — this request has expired. Ask the agent "
                          "to file a fresh request.", 410)
                return
            new["expires"] = old["expires"]
        new["reopened_from"] = aid
        new["original_requester"] = old.get("requester") or "unknown"
        dst = os.path.join(pending_dir(), new_aid + ".json")
        tmp = dst + ".tmp"
        with open(tmp, "w") as f:
            json.dump(new, f, indent=2)
        os.replace(tmp, dst)
        # One-shot nonce: the loser of a re-open race sees stale-nonce.
        # Evict the per-aid lock entry too (issue #231 hygiene — the old
        # aid's item never comes back, so the lock must not linger).
        _evict_reopen_nonce(aid)
        _evict_aid_lock(aid)
        audit_log("reopen", peer, login,
                  "id=%s new_id=%s requester=%s"
                  % (aid, new_aid, new["original_requester"]))
        # Fail-open, off the hot path: the page itself is the fallback.
        _push_enqueue_reopen(new_aid, str(new.get("summary") or ""))
        self.send_response(303)
        self.send_header("Location", "/approval/" + new_aid)
        self.end_headers()

    def _push_endpoint(self, login, length):
        """H2 (GitHub #2): subscribe/unsubscribe this browser for Web Push.

        Owner-authenticated via _auth (caller) with the same CSRF
        defenses as /answer. Stores only the push-service endpoint plus
        the browser-generated p256dh/auth keys — never secrets.
        """
        if not PUSH_ENABLED or _PUSH is None:
            self._send_json({"ok": False, "error": "push not configured"},
                            503)
            return
        try:
            doc = json.loads(self.rfile.read(length).decode())
        except (ValueError, UnicodeDecodeError):
            self._send_json({"ok": False, "error": "bad JSON"}, 400)
            return
        endpoint = doc.get("endpoint") if isinstance(doc, dict) else None
        if not isinstance(endpoint, str) or not endpoint:
            self._send_json({"ok": False, "error": "endpoint required"},
                            400)
            return
        peer = self.client_address[0]
        if self.path == "/api/push/subscribe":
            keys = doc.get("keys") if isinstance(doc.get("keys"), dict) else {}
            try:
                _PUSH.subs.add(endpoint, keys.get("p256dh"),
                               keys.get("auth"))
            except (ValueError, AttributeError, TypeError) as e:
                audit_log("push-subscribe-rejected", peer, login,
                          "err=%s" % e)
                self._send_json({"ok": False, "error": str(e)}, 400)
                return
            # Log only the endpoint host: the full URL carries an opaque
            # push-service token.
            audit_log("push-subscribe", peer, login, "host=%s"
                      % urllib.parse.urlparse(endpoint).netloc)
            self._send_json({"ok": True})
        else:
            removed = _PUSH.subs.remove(endpoint)
            audit_log("push-unsubscribe", peer, login,
                      "removed=%s" % removed)
            self._send_json({"ok": True})

    def log_message(self, *args):
        pass  # refusals go to the audit log; answers are in answered/


def _version_payload():
    """Unit-testable /api/version payload (docs/VERSIONING.md)."""
    return {"service": "confirmd", "version": SPARKVM_VERSION,
            "handler": Handler.server_version}


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    # Issue #77 (M8): bound the accept->thread fan-out (see main()).
    # Capacity model: confirmd's client classes are the owner's browser and
    # the agent proxy — expected peak ~4 concurrent requests. 64 threads is
    # ~16x headroom. The 10s socket timeout reclaims idle stalls; a peer
    # actively dripping >=1 byte/10s can still pin a slot, so 64 dripping
    # connections saturate the pool — shedding stays fail closed (connection
    # dropped, state stays file-backed so a retry succeeds) rather than
    # queued unboundedly. A cumulative per-connection deadline is the
    # long-term answer (follow-up).
    max_threads = 64

    # Backstop socket timeout for the deferred TLS handshake
    # (process_request_thread): the handler class's own `timeout` is
    # preferred when present; this covers handlers that don't set it.
    # Kept equal to Handler.timeout (10).
    socket_timeout = 10

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._slots = threading.Semaphore(self.max_threads)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.close_request(request)
            return
        try:
            # Architecture review B1: delegate thread creation, the
            # daemon flag, and the _threads/block_on_close lifecycle
            # bookkeeping to ThreadingMixIn — so future CPython changes
            # to the mixin propagate instead of silently diverging from
            # a copied body, and no socketserver-private import is
            # needed. self.process_request_thread below is still this
            # class's override (handshake deferral + slot release).
            super().process_request(request, client_address)
        except Exception:
            # Thread creation can fail under the same resource exhaustion
            # this pool guards against — log it, release the slot, and
            # close the request so a transient crunch can't drain the pool
            # permanently. Not re-raised: _handle_request_noblock would
            # log it a second time via handle_error.
            self.handle_error(request, client_address)
            self._slots.release()
            self.close_request(request)

    def process_request_thread(self, request, client_address):
        try:
            # Issue #77 (M8): the TLS handshake runs here, in the bounded
            # handler thread — never in the accept loop. main() wraps the
            # listening socket with do_handshake_on_connect=False, so a peer
            # that completes TCP and stalls the handshake burns one pool
            # slot (subject to fail-closed shedding) instead of pinning the
            # single serve_forever thread for every client. do_handshake()
            # honors the socket timeout, so a stalled handshake raises
            # socket.timeout and the slot is released below. Non-TLS
            # requests (plain-socket tests) have no do_handshake and skip
            # this.
            do_handshake = getattr(request, "do_handshake", None)
            if do_handshake is not None:
                # Architecture review B2: the same attribute
                # StreamRequestHandler.setup() honors, read off the
                # configured handler class — not a module global — so
                # this server stays reusable across daemons (#471). An
                # explicit None check (not `or`): a handler could set
                # timeout = 0 (non-blocking) and that must be honored.
                # socket_timeout (10) is the backstop for handlers that
                # don't set the attribute.
                timeout = getattr(self.RequestHandlerClass, "timeout", None)
                request.settimeout(
                    timeout if timeout is not None else self.socket_timeout)
                do_handshake()
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            try:
                self.shutdown_request(request)
            finally:
                # Release the pool slot even if shutdown_request raises: a
                # raise here must never permanently burn one of the 64 slots
                # (the mitigation must not become the DoS).
                self._slots.release()


def main():
    # Finding 67: print the resolved origins at startup so the journal
    # shows them; a missing ts.net name must be visible, not silent.
    print("confirmd PAGE_ORIGINS=%s" % sorted(PAGE_ORIGINS), flush=True)
    # H2: push state must be visible, not silent — including the reason
    # when disabled (Product review: "push not configured" alone is
    # undiagnosable).
    print("confirmd PUSH_ENABLED=%s" % PUSH_ENABLED, flush=True)
    if not PUSH_ENABLED:
        print("confirmd PUSH_DISABLED_REASON=%s" % PUSH_DISABLED_REASON,
              flush=True)
    print("confirmd version=%s" % SPARKVM_VERSION, flush=True)
    for d in (pending_dir(), answered_dir(), consumed_dir()):
        os.makedirs(d, exist_ok=True)
    # Issue #233: sweep any answered/ strays left by a previous run's
    # failed answered->consumed move before serving.
    _sweep_answered()
    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    # Finding 53(c): threaded, so a slow whois never blocks the page.
    # Issue #77 (M8): bounded thread pool — ThreadingHTTPServer spawns one
    # thread per connection, so a tailnet peer opening connections and
    # slow-reading could grow the pool without bound. The semaphore caps
    # in-flight handler threads; over-cap connections are closed
    # immediately (fail closed) rather than queued unboundedly.
    srv = BoundedThreadingHTTPServer((BIND, PORT), Handler)
    # Issue #77 (M8): defer the TLS handshake out of the accept loop.
    # wrap_socket's default do_handshake_on_connect=True runs the handshake
    # inside accept() on the single serve_forever thread — one tailnet peer
    # completing TCP and stalling ClientHello would pin ALL new connections
    # while the 64-slot pool sat idle (and Handler.timeout never applies
    # there: accepted sockets do not inherit the listener's timeout).
    # Deferred, a stalled handshake burns one bounded pool slot, is cut off
    # by the socket timeout in process_request_thread, and stays subject to
    # fail-closed over-cap shedding. Side benefit: shedding now happens
    # before any TLS work is paid.
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True,
                                 do_handshake_on_connect=False)
    print("confirmd on https://%s:%d/ as %s" % (BIND, PORT, OWNER), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
