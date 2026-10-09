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
  CONFIRM_BIND  tailnet address to bind (default: from `tailscale ip -4`;
                unresolvable => fail closed, exit 1, issue #70)
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

import contextlib
import fcntl
import grp
import html
import json
import os
import pwd
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

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

# Issue #471: the bounded pool + handshake-deferral server promoted out of
# confirmd (#77 M8) into scripts/bounded_http.py — scripts/ is on sys.path
# via the version-stamping block above. The import is unconditional: a
# missing helper is a broken checkout and must fail loud, not silently
# fall back to the unbounded server. confirmd subclasses it below to set
# the #472 cumulative-deadline switch and audit the kill; the shared
# mechanism stays one implementation for all three daemons
# (confirmd, cred-ui, waitlistd).
from bounded_http import BoundedThreadingHTTPServer as _BoundedHTTPServer

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


# Issue #70: explicit operator pin wins; otherwise resolve from tailscale.
# There is deliberately NO stale-literal fallback: serving on a guessed
# address would invalidate finding 47's self-peer refusal (a wrong self
# set authenticates a local process as the owner). A None return means
# "cannot determine the bind address" and main() fails closed (exit 1)
# instead of serving — systemd Restart=on-failure retries once tailscaled
# is back, per confirmd.service.
def _resolve_bind():
    return os.environ.get("CONFIRM_BIND") or _tailnet_ip4()


BIND = _resolve_bind()

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
    """Exact set of origins the page is served at (finding 57).

    Returns (origins, dns_ok): dns_ok is False when the ts.net DNS name
    could not be resolved, so a refresh keeps the last good set instead
    of committing an IP-literal-only shrink (the refusal boundary must
    never silently shrink). The IP-literal half comes from import-time
    BIND — a tailscale IP renumber mid-daemon still needs a restart."""
    # Explicit override wins (deploy.sh sets both IP and ts.net name).
    env = os.environ.get("CONFIRM_ORIGINS", "")
    if env.strip():
        return {o.strip() for o in env.split(",") if o.strip()}, True
    origins = set()
    # Issue #70: when BIND is None the IP-literal origin is skipped — a
    # "https://None:8443" origin must never exist, even inertly, or a
    # future import-and-serve path could exact-match it. main() refuses
    # to serve in this state anyway; this makes the fail-closed total.
    if BIND:
        origins.add("https://%s:%d" % (BIND, PORT))
    dns = _tailnet_dnsname()
    if dns:
        origins.add("https://%s:%d" % (dns, PORT))
        return origins, True
    # Finding 67: import-time fallback — DNS unresolvable at startup, the
    # set holds the IP literal only so every real browser POST doesn't 403.
    return origins, False


# Issue #619: PAGE_ORIGINS was frozen at import — a tailscale DNS rename
# mid-daemon (machine rename, tailnet domain change) left finding 57's
# Origin exact-match check stale for the process lifetime: the owner's
# real browser POSTs from the new ts.net origin would 403 until restart.
# Same treatment as #536's _SelfAddrs: re-resolve on a slow cadence (60 s,
# mirroring the whois cache). A failed refresh keeps the last good set —
# a refusal boundary must never silently shrink (an unreachable
# tailscaled must not collapse the set to the IP literal alone) — and the
# CONFIRM_ORIGINS env override pins the set (no re-probe) for operators
# who manage names out of band.
_PAGE_ORIGINS_TTL = 60


class _PageOrigins:
    """TTL-cached origin set for finding 57's exact-match Origin check.

    Keeps the module-level ``PAGE_ORIGINS`` name and its ``in`` /
    ``sorted()`` shapes, so callers and tests are unchanged. Thread-safe:
    handler threads share the one instance.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._pinned = bool(os.environ.get("CONFIRM_ORIGINS", "").strip())
        self._origins, _ = _page_origins()
        self._ts = time.monotonic()

    def _refresh(self):
        now = time.monotonic()
        with self._lock:
            if now - self._ts < _PAGE_ORIGINS_TTL:
                return
            if not self._pinned:
                origins, ok = _page_origins()
                if ok:
                    self._origins = origins
                # else: keep the last good set — the refusal boundary must
                # never silently shrink.
            self._ts = now

    def _snapshot(self):
        if time.monotonic() - self._ts >= _PAGE_ORIGINS_TTL:
            self._refresh()
        return self._origins

    def __contains__(self, origin):
        return origin in self._snapshot()

    def __iter__(self):
        return iter(self._snapshot())


PAGE_ORIGINS = _PageOrigins()

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
#
# Issue #78: the ring lives SERVER-SIDE, keyed by approval id, in the
# `_csrf_rings` map below — never in the requester-authored pending file.
# The old code persisted the ring into the pending item's JSON, and the
# check was a plain membership test, so a future lower-trust filer could
# pre-seed `_csrf_nonces` with nonces of its own choosing and then drive
# /answer from its own browser session with a matching nonce — a
# CSRF-shaped bypass of the approval-origin binding. File-stored
# `_csrf_nonces` / `_csrf` entries are now IGNORED ENTIRELY (never read,
# not even the legacy slot); only the server-minted in-memory ring counts.
# Stale `_csrf_nonces` keys may linger in old pending files — harmless, and
# still stripped before items reach answered/ (see _stamp_expired_consumed).
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
    history — the invariant has teeth, stated once here.

    Issue #78: the aid's server-side CSRF ring is evicted here too — the
    ring shares the pending-item lifecycle: eviction runs on every path
    where the item leaves pending (answered, expired-reaped, gone), and
    the ring is recreated on demand by the next GET mint, so one
    eviction point keeps both maps bounded with no drift between them.
    (Two non-terminal paths keep the file — the grant-window refusal
    and the failed expiry stamp — and both stay correct: the ring is
    simply re-minted by the next GET if the item is still live.)"""
    _aid_locks.pop(aid, None)
    _csrf_rings.pop(aid, None)


def stamp_lock_dir():
    """Issue #945: home of the per-aid cross-process stamp locks.

    Same makedirs-on-demand discipline as pending_dir(): created by
    whichever party (confirmd or the box ingest) needs it first, as the
    box-service user that owns the approvals store. The lockfiles are
    never removed — one tiny file per approval id, and unlinking a
    lockfile a peer is about to open would break mutual exclusion, so
    no pruning (unlike the aid-keyed in-process registry above, which
    is safe to evict because it is never shared across processes).
    """
    d = os.path.join(APPROVALS, "stamp-locks")
    os.makedirs(d, exist_ok=True)
    return d


@contextlib.contextmanager
def _stamp_lock(aid):
    """Issue #945: cross-process mutual exclusion for one approval id.

    confirmd's _aid_lock serializes threads inside this one process, but
    the box ingest (spark-pair.py, a separate cron process) is outside
    it. The residual race: the ingest can mint a grant while confirmd's
    answer path or a reaper records a terminal state (or vice versa),
    leaving a live grant under a deny/expired record for up to the grant
    TTL — both decisions owner-authentic, the window tiny, no
    non-owner injection, but a real fail-open the proxy would honor.

    The lock is an flock(2) on ``stamp-locks/<aid>.lock``, held across
    the whole check->mint->stamp window by _answer_locked (approve),
    both reaper stamp sites, and the ingest's approve path (the twin
    helper there is ``_ingest_stamp_lock`` in pairing/spark_pair.py —
    same mechanism, same fail-closed contract, kept in sync by hand).

    Deadlock audit: lock order is _aid_lock -> stamp lock at every
    confirmd site; the ingest never takes _aid_lock, so no inversion
    exists. The stamp lock is never held while acquiring _aid_lock, and
    no site re-acquires the same aid's stamp lock while holding it
    (flock locks are per open-file-description — a second LOCK_EX on a
    second fd for the same file blocks even in the same process — so
    _stamp_expired_consumed stays lock-free and every caller takes the
    lock exactly once). The grant subprocess acquires no locks of its
    own that any stamp-lock holder waits on. The kernel releases the
    flock if a holder dies mid-window, so a crashed minter cannot wedge
    the aid.

    Fail-closed: an unopenable or unlockable lockfile raises instead of
    degrading to unlocked — silently proceeding would reintroduce the
    exact race this lock closes. The aid is validated against ID_RE so
    a hostile aid cannot escape the lock dir via path traversal.
    """
    if not ID_RE.match(aid or ""):
        raise ValueError("bad aid for stamp lock: %r" % (aid,))
    path = os.path.join(stamp_lock_dir(), aid + ".lock")
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as e:
        raise RuntimeError("stamp lock: cannot open %s: %s" % (path, e))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError as e:
        os.close(fd)
        raise RuntimeError("stamp lock: cannot lock %s: %s" % (path, e))
    try:
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


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

# Issue #537: the re-open idempotency check (_pending_reopened_aid) used
# to os.listdir + json.load EVERY pending file on every /reopen POST —
# O(n) JSON parses in the request hot path. The index below answers the
# hot path from one entry: original (denied) aid -> newest re-filed aid.
# Bounded like _reopen_nonces; invalidation is by validation, not TTL:
# on a hit, the single candidate file is opened and checked (exists, is
# the re-file of this aid, unexpired) — any mismatch drops the entry and
# falls through to the full scan, which is kept as the exact-semantics
# fallback and repopulates the index on a hit. Worst case is a duplicate
# filing, exactly as before the index — it can only make the check
# cheaper, never wronger.
_reopened_index = {}
_REOPENED_INDEX_CAP = 4096

# Issue #534: the grant-mint subprocess bound and the pre-mint validity
# window. The approve path refuses to START a mint when the remaining
# validity is under the worst-case mint duration + margin: an expiry that
# crosses mid-mint would land a grant for an already-expired approval,
# and the grant writer has no revoke path — so the window must be closed
# before the subprocess starts. The #240 post-mint check can only refuse
# the *recording*, never the mint. The subprocess timeout below is the
# same constant, so the bound is a single source of truth.
_GRANT_MINT_TIMEOUT = 15
_GRANT_MINT_WINDOW = 30  # seconds of remaining validity required


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


def _reopened_index_ok(aid, new_aid):
    """Validate a single index hit: the candidate file must exist, be
    the re-file of `aid`, and be unexpired. A cheap single-file check —
    the index is never trusted alone."""
    p = os.path.join(pending_dir(), new_aid + ".json")
    try:
        with open(p) as f:
            it = json.load(f)
    except (OSError, ValueError):
        return False
    if not isinstance(it, dict) or it.get("reopened_from") != aid:
        return False
    return not is_expired(it)


def _index_reopened(aid, new_aid):
    """Record a re-file in the index, keeping the map bounded."""
    _reopened_index[aid] = new_aid
    while len(_reopened_index) > _REOPENED_INDEX_CAP:
        _reopened_index.pop(next(iter(_reopened_index)))


def _pending_reopened_aid(aid):
    """H20: idempotent re-open. If this denied aid was already re-filed
    and the new item is still pending (and unexpired), return its aid so
    a repeat POST redirects to it instead of filing a duplicate. The
    deny card re-mints a fresh nonce on every render, so a second POST
    for the same deny is normal (double-tap, deliberate repeat) — not
    an attack. Returns None when no live re-opened item exists."""
    # Issue #537: consult the in-memory index first — the hot path opens
    # one file instead of parsing the whole pending/ dir. A stale entry
    # (the re-filed item left pending since) is dropped and the full
    # scan below runs as the exact-semantics fallback.
    hit = _reopened_index.get(aid)
    if hit and _reopened_index_ok(aid, hit):
        return hit
    if hit:
        _reopened_index.pop(aid, None)
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
            _index_reopened(aid, new_aid)
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
            if res not in _PUSH_REOPEN_OK:
                print("confirmd WARNING: push enqueue returned %s for "
                      "re-opened %s" % (res, new_aid), flush=True)
        except Exception:
            print("confirmd WARNING: push enqueue failed for re-opened %s"
                  % new_aid, flush=True)
    threading.Thread(target=_run, name="confirmd-reopen-push",
                     daemon=True).start()


# H20 enqueue results that are NOT warnings. "plane-owned" (#1135) is the
# hosted-mode stand-down — the box-local channel could never page on a
# plane-enrolled box — not a failure.
_PUSH_REOPEN_OK = ("queued", "duplicate", "notified", "plane-owned")


# Issue #78: server-side CSRF nonce rings, keyed by approval id. The map
# shares the pending-item lifecycle: an entry is created on the first GET
# that mints a nonce for the aid and evicted when the item leaves pending
# (see _evict_aid_lock). Single-instance scope is honest here — the same
# caveat as _aid_locks and _reopen_nonces (a multi-replica confirmd would
# need a shared store — tracked under #69).
# Map-level cap mirrors _reopen_nonces/_reopened_index (issue #77 L10
# hygiene); the per-aid ring itself is bounded by _CSRF_RING_SIZE.
# A daemon restart empties the map: pre-restart forms 403 as
# stale-nonce and self-heal on manual reload (the 403 message says so),
# exactly like _reopen_nonces.
_csrf_rings = {}
_CSRF_RING_AID_CAP = 4096


def _prune_csrf_ring(ring, now):
    """Drop expired or malformed entries from a ring in place. A well-
    formed entry is {"nonce": str, "ts": number}; anything else is never
    legitimate (the ring is server-minted) and is dropped fail-closed —
    verify-time still double-checks shape before comparing digests."""
    ring[:] = [e for e in ring
               if isinstance(e, dict)
               and isinstance(e.get("nonce"), str)
               and isinstance(e.get("ts"), (int, float))
               and now - e["ts"] <= _CSRF_RING_TTL]


def _mint_csrf_nonce(aid):
    """Mint a fresh CSRF nonce for an approval id, keeping a small ring
    of recent nonces SERVER-SIDE (issue #78) — nothing is written to the
    requester-authored pending file. The per-aid lock (held by the GET
    path) serializes concurrent mints; eviction of the whole ring rides
    _evict_aid_lock."""
    now = time.time()
    ring = _csrf_rings.get(aid)
    if ring is None:
        ring = []
        _csrf_rings[aid] = ring
        # Issue #77 (L10) hygiene: keep the aid map bounded like
        # _reopen_nonces — evict the oldest aid's ring first.
        while len(_csrf_rings) > _CSRF_RING_AID_CAP:
            _csrf_rings.pop(next(iter(_csrf_rings)))
    else:
        _prune_csrf_ring(ring, now)
    nonce = secrets.token_urlsafe(24)
    ring.append({"nonce": nonce, "ts": now})
    del ring[:-_CSRF_RING_SIZE]
    return nonce


def _csrf_nonce_ok(aid, csrf):
    """True if `csrf` is a well-formed, unexpired nonce in the aid's
    SERVER-SIDE ring (issue #78). The requester-authored pending file is
    never consulted — file-stored `_csrf_nonces` / `_csrf` entries are
    ignored entirely, so a lower-trust filer cannot mint acceptable
    entries. The TTL is enforced at verification time too, not only at
    mint (security review): a clock-jump-backward cannot keep a nonce
    valid past the TTL."""
    if not NONCE_RE.match(csrf or ""):
        return False
    now = time.time()
    ring = _csrf_rings.get(aid) or []
    return any(isinstance(e, dict)
               and isinstance(e.get("nonce"), str)
               and isinstance(e.get("ts"), (int, float))
               and now - e["ts"] <= _CSRF_RING_TTL
               and secrets.compare_digest(e["nonce"], csrf)
               for e in ring)

# Finding 47: the host's own tailnet addresses. A peer presenting one
# of these is the host itself (e.g. the swap proxy connecting out) —
# never the human on a remote node.
def _host_addrs():
    """Finding 63(b): try sudo first (same narrow rule as whois). If
    tailscaled is unreachable, warn - the set collapses to BIND only.
    Returns (addrs, ok); ok is False exactly when no tailscale query
    succeeded. Issue #70: when BIND itself is None (no pin, no resolve),
    the set is BIND-less here and main() refuses to serve entirely."""
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
    # Belt and braces: the bind address is always self (issue #70: BIND is
    # None only when no address resolved at import, and main() refuses to
    # serve in that case — a None must never land in the refusal set).
    if BIND:
        addrs.add(BIND)
    return addrs, ok


# Issue #536: the self-peer address set was frozen at import — a tailscaled
# renumber mid-daemon left finding 47's self-refusal stale for the process
# lifetime. Re-resolve on a slow cadence (60 s, mirroring the whois cache).
_HOST_ADDRS_TTL = 60


class _SelfAddrs:
    """TTL-cached self-address set for finding 47's self-peer refusal.

    Keeps the module-level ``HOST_ADDRS`` name and its ``in`` shape, so
    callers and tests are unchanged. A failed refresh keeps the last good
    set (the refusal boundary must never silently shrink); the import-time
    resolve keeps finding 63(b)'s warn-and-collapse-to-BIND semantics
    (issue #70's exception: no bind address resolved at import means
    main() refuses to serve at all, fail closed).
    Thread-safe: handler threads share the one instance.
    """
    def __init__(self):
        self._lock = threading.Lock()
        addrs, _ = _host_addrs()
        self._addrs = addrs
        self._ts = time.monotonic()

    def _refresh(self):
        now = time.monotonic()
        with self._lock:
            if now - self._ts < _HOST_ADDRS_TTL:
                return
            addrs, ok = _host_addrs()
            if ok:
                self._addrs = addrs
            # else: keep the stale set — a refusal boundary must not
            # shrink because tailscaled was momentarily unreachable.
            self._ts = now

    def __contains__(self, peer):
        if time.monotonic() - self._ts >= _HOST_ADDRS_TTL:
            self._refresh()
        return peer in self._addrs


HOST_ADDRS = _SelfAddrs()

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
    """Return the Tailscale LoginName of the whois subject, or None.

    Issue #1166: anchored to ``UserProfile.LoginName``. The recursive
    descent this replaced returned the first string-valued "LoginName"
    key anywhere in the tree, descending Node before UserProfile — a
    "LoginName" nested inside Node (a future tailscale schema addition
    or nested metadata) would have silently taken precedence over the
    owner's profile, flipping the finding-47 owner check. Anything
    absent, non-string, or empty fails closed: None means the peer is
    refused (an empty login is not an identity — the recursive form
    never returned one either, its truthiness check skipped it).

    Architecture review (this PR's Architecture round, blocking): the fail-closed path must not
    be silent — a whois schema change would otherwise hard-lock the
    single approver out of the page with zero trail. The warnings below
    name only the failure mode and top-level field names (never values —
    the doc carries node addresses); they fire only on the refusal path,
    so a healthy daemon never logs them.
    """
    if not isinstance(obj, dict):
        print("confirmd WARNING: _find_login: whois doc is not a dict "
              "(type=%s); refusing peer" % type(obj).__name__, flush=True)
        return None
    profile = obj.get("UserProfile")
    if not isinstance(profile, dict):
        print("confirmd WARNING: _find_login: no UserProfile dict in "
              "whois doc (top-level keys=%s); refusing peer"
              % sorted(map(str, obj.keys())), flush=True)
        return None
    login = profile.get("LoginName")
    if not isinstance(login, str) or not login:
        print("confirmd WARNING: _find_login: UserProfile.LoginName "
              "absent/empty/non-string (type=%s); refusing peer"
              % type(login).__name__, flush=True)
        return None
    return login


# Issue #535 (open-source) / #360 (hosted S1): the audit trail is
# append-only with no cap — answered/consumed are pruned but the refusal
# trail grows unbounded, accelerating the disk-full condition the A5
# stderr signal handles. Writer-side rotation: when the live segment
# reaches _AUDIT_MAX_BYTES, the segment chain rolls (audit.log -> .1 ->
# .2 ..., oldest dropped past _AUDIT_KEEP). Never drops the newest
# events: rotation keeps the newest _AUDIT_KEEP segments and always
# appends to a fresh live file. Crash-safe: renames are ordered
# oldest-first with the live segment renamed last — a crash between
# renames loses at most old segments, never creates a gap in the newest
# trail; a crash before the live file is recreated just leaves the next
# append to create it (the open is "a"). The check+rotate+append is
# serialized on _AUDIT_LOCK: handler threads must not interleave a
# rotation between another thread's size check and its write.
_AUDIT_MAX_BYTES = _env_int("CONFIRM_AUDIT_MAX_BYTES", 10 * 1024 * 1024,
                            1024)
_AUDIT_KEEP = _env_int("CONFIRM_AUDIT_KEEP", 4, 1)  # live + (KEEP-1) rotated
_AUDIT_LOCK = threading.Lock()

_AUDIT_FIELD_ALLOW_RE = re.compile(r"[^!-~]")


def _sanitize_audit_field(value):
    """Keep printable-ASCII only in one audit-log field (#683, #17 twin).

    Audit lines are `k=v` tokens separated by spaces; `login` is
    user-supplied web-UI form input and `detail` can carry
    client-influenced values (e.g. hosts), so a newline, a Unicode line
    separator, or a `ts=`-looking fragment in one forges audit lines.
    Same shape as the swap-proxy fix for #17 (PR #682,
    `proxy/swap_addon.py::_sanitize_audit_field`) — sanitize on write,
    one choke point every interpolated field routes through. Well-formed
    values pass through unchanged except that spaces are stripped too
    (necessarily: spaces are the `k=v` token separator, so a space is a
    forgery vector). None renders as "-"; other non-str values are coerced.
    """
    if value is None:
        return "-"
    return _AUDIT_FIELD_ALLOW_RE.sub("", str(value))


def _rotate_audit():
    """Roll the audit segment chain (caller holds _AUDIT_LOCK).

    Oldest-first renames; the live segment is renamed last. KEEP=1 (live
    only): the oversized live segment is dropped outright — the newest
    events still land in the fresh live file. Any OSError aborts the
    roll (the oversized file stays, the failure is journaled, and the
    next audit event retries) — the trail is never truncated by a
    half-rolled chain.
    """
    try:
        if _AUDIT_KEEP <= 1:
            os.remove(AUDIT)  # may already be gone; the append recreates
        else:
            # i = KEEP-2 .. 1: .(KEEP-2)->.(KEEP-1) drops the oldest kept
            # segment, ..., .1->.2, then live->.1.
            for i in range(_AUDIT_KEEP - 2, 0, -1):
                src = "%s.%d" % (AUDIT, i)
                if os.path.exists(src):
                    os.replace(src, "%s.%d" % (AUDIT, i + 1))
            os.replace(AUDIT, "%s.1" % AUDIT)
    except OSError as e:
        print("confirmd WARNING: audit rotation failed: %s" % e,
              flush=True)


def _maybe_rotate_audit():
    """Rotate the audit chain when the live segment reached the cap
    (caller holds _AUDIT_LOCK). A stat failure is a miss, not an abort:
    the append below still runs, and its own OSError path names the lost
    event."""
    try:
        if os.path.getsize(AUDIT) < _AUDIT_MAX_BYTES:
            return
    except OSError:
        return
    _rotate_audit()


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
    the journal under systemd — the trail gap is operator-visible. Crash
    durability (issue #72): the append is fsync'd before the fd closes, so
    once audit_log() returns the line is durable against a crash — without
    the fsync, a crash loses the whole page-cache window, silently erasing
    recent refusals from the trail. An fsync OSError takes the same stderr
    path (the event is treated as lost). Remaining window, documented not
    closed: if AUDIT did not exist and was just created, the directory
    entry is not fsync'd here — a crash at that exact instant can lose the
    file. The file is created once and persists afterwards, so this is not
    a steady-state exposure. Writer-side rotation (issues #535/#360):
    before each append the live segment's size is checked under
    _AUDIT_LOCK; at _AUDIT_MAX_BYTES the chain rolls, keeping the newest
    _AUDIT_KEEP segments. The newest events are never dropped (they land
    in a fresh live segment), and the oldest-first rename order keeps a
    crash from creating a gap in the newest trail."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = ("ts=%s event=%s peer=%s login=%s %s\n"
            % (ts,
               _sanitize_audit_field(event),
               _sanitize_audit_field(peer),
               _sanitize_audit_field(login),
               _sanitize_audit_field(detail)))
    try:
        with _AUDIT_LOCK:
            _maybe_rotate_audit()
            with open(AUDIT, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()  # user-space buffer -> OS; fsync below only reaches
                # the kernel page cache, so without the flush it would sync
                # nothing (the line is still in CPython's buffer).
                os.fsync(f.fileno())
    except OSError as e:
        print("confirmd: cannot write audit log: %s (lost event=%s peer=%s login=%s)"
              % (e, _sanitize_audit_field(event),
                 _sanitize_audit_field(peer),
                 _sanitize_audit_field(login)), file=sys.stderr)


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

# Issue #73: the grant lifetime is the owner's per-approval choice, not a
# hidden 24h default. The approval page offers a bounded radio — 1 hour
# (default, the shortest) or 24 hours — and the choice is passed to
# grant-writer as --ttl-hours. The allowlist is the authority: a value
# outside the offered choices is refused by the caller, never coerced
# into something the owner didn't pick, so the minted grant can only
# ever match what the page displayed.
GRANT_TTL_CHOICES = (1, 24)
GRANT_TTL_DEFAULT = 1


def _parse_grant_ttl(value):
    """Issue #73: parse the owner-chosen grant TTL into validated hours.

    Missing/empty means the default (shortest). Anything outside the
    offered choices raises ValueError — the caller refuses it, never
    clamps it into a lifetime the page never showed."""
    if value is None or (isinstance(value, str) and value == ""):
        return GRANT_TTL_DEFAULT
    try:
        ttl = int(value)
    except (TypeError, ValueError):
        raise ValueError("bad ttl: %r" % (value,))
    if ttl not in GRANT_TTL_CHOICES:
        raise ValueError("bad ttl: %r" % (value,))
    return ttl


# Issue #232: grace periods for the pending-file lifecycle fix. A corrupt
# file younger than the quarantine grace may be a torn mid-write from the
# pre-#232 non-atomic confirm-request filer — it looks exactly like
# corruption, so it is left alone; the render reap catches it on a later
# pass if it never completes. Same reasoning for stray *.tmp files:
# atomic writers hold the tmp name for milliseconds, so anything older
# than the sweep grace is crash residue, never an in-flight write.
_CORRUPT_QUARANTINE_GRACE_S = _env_int("CONFIRM_CORRUPT_GRACE_S", 120, 0)
_TMP_SWEEP_GRACE_S = _env_int("CONFIRM_TMP_SWEEP_GRACE_S", 300, 0)


def _quarantine_dir():
    d = os.path.join(APPROVALS, "pending-quarantine")
    os.makedirs(d, exist_ok=True)
    return d


def _quarantine_corrupt_pending(aid, src):
    """Issue #232: move an unparsable pending/<aid>.json out of pending/.

    A corrupt file is unanswerable — every GET/POST 404s on it — and the
    old render reap silently skipped it, so it sat in pending/ for the
    daemon's lifetime. The quarantine dir is never scanned by
    load_pending, so the move takes the file out of the hot path; the
    file itself is preserved for forensics and an audit event records
    the move. Returns True when the file was quarantined.

    Crash-residue guard: files newer than _CORRUPT_QUARANTINE_GRACE_S are
    left in place (a torn mid-write from the old non-atomic filer is
    indistinguishable from corruption). A mid-sweep race with the answer
    path is benign: the answer path 404s on corrupt files without
    mutating them, and aids are never reused, so nothing can
    legitimately recreate this name afterwards."""
    try:
        age = time.time() - os.path.getmtime(src)
    except OSError:
        return False
    if age < _CORRUPT_QUARANTINE_GRACE_S:
        return False
    qd = _quarantine_dir()
    # `aid` comes from a listdir entry minus the ".json" suffix — it
    # cannot contain a path separator, so the join cannot escape qd.
    dst = os.path.join(qd, aid + ".json")
    try:
        os.replace(src, dst)
    except OSError:
        return False
    audit_log("pending-quarantined", "confirmd", "",
              # Security hardening: `aid` derives from a listdir filename,
              # which may contain newlines — sanitize before interpolating
              # into the line-based audit log (defense in depth; a pending/
              # writer could already plant worse directly).
              "id=%s reason=unparsable"
              % re.sub(r"[^A-Za-z0-9._-]", "_", aid))
    return True


def _sweep_stale_tmp(d):
    """Issue #232: remove crash-residue *.tmp files from pending/.

    Atomic writers (confirm-request, swap_addon.py's filer) hold the tmp
    name only for the write+replace window, so a *.tmp older than
    _TMP_SWEEP_GRACE_S is residue from a crashed writer, never an
    in-flight one. (Issue #78 retired the GET path's nonce write-back —
    the GET render no longer rewrites the pending file at all.) Best-effort: races are fail-silent,
    the next render retries."""
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".tmp"):
            continue
        p = os.path.join(d, fn)
        try:
            if time.time() - os.path.getmtime(p) < _TMP_SWEEP_GRACE_S:
                continue
            os.remove(p)
        except OSError:
            pass


def load_pending():
    """Finding 58: reap expired items when the list is rendered."""
    items = []
    d = pending_dir()
    now = datetime.now(timezone.utc)
    # Issue #232: sweep crash-residue tmp files on every render — the
    # grace period keeps this from ever touching an in-flight writer.
    _sweep_stale_tmp(d)
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(d, fn)
        try:
            with open(p) as f:
                it = json.load(f)
        except Exception:
            # Issue #232: a corrupt/torn pending file is unanswerable
            # (every GET/POST 404s on it) — quarantine it (grace-gated,
            # so a torn mid-write from the old non-atomic filer is not
            # misclassified) instead of silently skipping it forever.
            _quarantine_corrupt_pending(fn[:-len(".json")], p)
            continue
        try:
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
                    # Issue #945: take the cross-process stamp lock so the
                    # stamp+delete serializes against the box ingest's
                    # approve path and the answer path in other processes
                    # (lock order _aid_lock -> stamp lock, as at /answer).
                    # A malformed aid skips the lock: every legitimate
                    # stamper validates the aid before locking, so no peer
                    # can be stamping it — and _stamp_expired_consumed
                    # refuses to stamp it below anyway (pre-existing
                    # malformed-aid path: reap without stamping).
                    #
                    # S1 (#511): stamp the expired terminal record BEFORE
                    # the pending file is deleted (stamp-then-delete: a
                    # crash between the two self-heals on the next reap —
                    # the stamp is EEXIST-skipped, the delete retried —
                    # while the reverse order could lose the expiry with
                    # no record at all). If the answer path already
                    # consumed this aid while we waited on the lock, its
                    # terminal record exists and our O_EXCL create fails
                    # -> False: the human answer wins, and we must not
                    # resurrect the pending file.
                    lock = (_stamp_lock(aid) if ID_RE.match(aid)
                            else contextlib.nullcontext())
                    try:
                        with lock:
                            _stamp_expired_consumed(aid, it, p, "confirmd")
                    except ValueError:
                        # Malformed aid: refuse to touch consumed/, but
                        # still reap the expired file below.
                        pass
                    except RuntimeError:
                        # Issue #945: fail-closed stamp lock — keep the
                        # pending file so the next render retries the
                        # stamp (same as the OSError arm below). The
                        # breakage is loud elsewhere: the answer path
                        # 500s with answer-lock-failed and the ingest
                        # refuses to stamp without the lock.
                        _evict_aid_lock(aid)
                        continue
                    except OSError:
                        # Stamp failed (e.g. ENOSPC): keep the pending
                        # file so the next render retries the stamp.
                        _evict_aid_lock(aid)
                        continue
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


def _grant_window_ok(it):
    """Issue #534: True when a grant mint may start — the item has no
    expiry, or its remaining validity covers the worst-case mint window.
    Called on the approve path before the grant subprocess: an expiry
    crossing mid-mint mints an un-revokable grant, so a narrow window is
    refused honestly (410 + distinct audit event) instead of minting
    into it. The pending file is left in place; the render reap stamps
    `expired` when the clock crosses — the honest outcome label for a
    request whose window lapsed."""
    exp = _parse_expiry(it.get("expires"))
    if exp is None:
        return True
    remaining = (exp - datetime.now(timezone.utc)).total_seconds()
    return remaining >= _GRANT_MINT_WINDOW


def file_owner_name(path):
    """Finding 50: the requester is the file's owner, never an argument."""
    try:
        st = os.stat(path)
        return pwd.getpwuid(st.st_uid).pw_name
    except (OSError, KeyError):
        return None


def _stamp_expired_consumed(aid, it, pending_path, expired_by):
    """S1 (#511): stamp the expired-approval terminal record.

    Write-if-absent via O_EXCL: the winner of the confirmd-render-reap /
    proxy-filing-scan race creates consumed/<aid>.json; the loser gets
    FileExistsError and must move on without resurrecting anything.
    Returns True when this call created the record, False when one
    already existed (the other reaper — or the answer path — won).

    Raises ValueError for an aid that fails ID_RE: an unvalidated aid
    must never touch consumed/ (design §10 to-verify). Raises OSError
    when the record cannot be written (the caller keeps the pending
    file so the next reap retries — deleting it now would lose the
    expiry with no record, the hazard stamp-then-delete avoids).
    """
    if not ID_RE.match(aid):
        raise ValueError("refusing to stamp consumed/ for bad aid %r"
                         % (aid,))
    rec = dict(it)
    rec.pop("_csrf", None)
    rec.pop("_csrf_nonces", None)
    rec["decision"] = "expired"
    rec["expired_at"] = datetime.now(timezone.utc).isoformat()
    rec["expired_by"] = expired_by
    # Finding 50: the requester is the filing file's owner, never an
    # argument — the same mechanism the answer path uses.
    rec["requester"] = file_owner_name(pending_path)
    # Reserved for H10 (multi-tenant confirmd): null means "unscoped,
    # single-tenant host" — today's exact semantic. No tenant filter
    # is invented before H10.
    rec["tenant_id"] = None
    path = os.path.join(consumed_dir(), aid + ".json")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return False
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(rec, f, indent=2)
    except BaseException:
        # A torn record must not stand: the loser mistakes presence
        # for a win. Best-effort unlink, then re-raise as OSError so
        # callers keep the pending file for the next reap's retry.
        try:
            os.unlink(path)
        except OSError:
            pass
        raise OSError("expired stamp write failed for %s" % aid)
    return True


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
.badge-expired{background:#fdf0d5;color:#8a5a00}
@media(prefers-color-scheme:dark){
.badge-deny{background:#3a1f1f;color:#f2a9a2}
.badge-approve{background:#173a24;color:#9fe0b4}
.badge-expired{background:#43300a;color:#f5c86e}}
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
/* Issue #73: the grant-lifetime choice is the most
security-consequential control on the page — it gets 52px tap rows
like the decision buttons, so the owner's actual tap target matches
the page's thumb convention. */
.ttl{border:1px solid #dcdfe3;border-radius:10px;padding:6px 14px 10px;margin:16px 0}
.ttl legend{font-size:.85rem;font-weight:700;color:#555;padding:0 8px}
.ttl label{display:flex;align-items:center;gap:12px;min-height:52px;font-size:1.05rem;cursor:pointer}
.ttl input[type=radio]{width:24px;height:24px;accent-color:#1a7f37;flex:none}
.ttl input[type=radio]:focus-visible{outline:3px solid #1a73e8;outline-offset:2px}
@media(prefers-color-scheme:dark){
.ttl{border-color:#3a3d42}
.ttl legend{color:#aaa}}
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
  // S3 (#546): expired is the third terminal decision — its badge is
  // distinct (amber) from approve (green) / deny (red).
  if(dec==="approve"||dec==="deny"||dec==="expired"){
    d.className="badge "+(dec==="approve"?"badge-approve":
      dec==="deny"?"badge-deny":"badge-expired");
    d.textContent=dec==="approve"||dec==="deny"?dec:"expired";h.appendChild(d);
  }
  var s=document.createElement("div");s.className="summary";
  s.textContent=String(it.summary||"");c.appendChild(s);
  // Design §5: never reuse the answer fields for an expiry — expired
  // records carry no answered_by/answered_at, so the meta line reads
  // "expired by <reaper> · <expired_at>" instead.
  if(dec==="expired"){
    metaLine(c,[it.expired_by?("expired by "+String(it.expired_by)):"expired",
      it.expired_at?fmtTime(it.expired_at):"",
      String(it.kind||"")]);
  }else{
    metaLine(c,[it.answered_by?("by "+String(it.answered_by)):"",
      it.answered_at?fmtTime(it.answered_at):"",
      String(it.kind||""),
      // Issue #73: the answered history shows the grant lifetime the
      // owner authorized on the approval page.
      (dec==="approve"&&it.grant_ttl_hours)?
        ("grant "+String(it.grant_ttl_hours)+"h"):""]);
  }
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

    S3 (#546): expired terminal records carry no answered_at (design §2:
    the answer fields must never be reused for an expiry), so they sort
    on expired_at — the record's own stamp. Both keys mean "when this
    aid reached its terminal state", so one ordering covers the whole
    answered history.

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
    items.sort(key=lambda it: _parse_expiry(
        it.get("answered_at") or it.get("expired_at")) or
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


# Issue #1168: the #232 corruption quarantine had no bound — every other
# confirmd store is capped (audit log rolls at _AUDIT_MAX_BYTES, consumed/
# keeps _CONSUMED_KEEP, the in-memory rings are capped), but
# pending-quarantine/ accumulated one file per corrupt filing for the
# daemon's whole lifetime, and any pending/ writer can plant unparsable
# files. Keep the newest N on disk; the audit log stays the durable
# trail (each quarantine move is journaled via the pending-quarantined
# event). mtime-ordered, oldest-only deletes, like _prune_consumed.
_QUARANTINE_KEEP = _env_int("CONFIRM_QUARANTINE_KEEP", 200, 10)


def _prune_quarantine(limit=None):
    """Delete pending-quarantine/ history beyond the newest `limit` files.

    Called by _housekeeping_if_due() (cadence-gated), after
    _prune_consumed(). Mirrors _prune_consumed's race-benign shape: only
    the oldest files are ever deletion candidates, all OSError paths
    tolerated, and the count gate skips the mtime stat storm when the
    dir is within the cap. Quarantine moves never collide with the prune
    by name (aids are never reused), and a lost race surfaces as
    FileNotFoundError, which is tolerated. Strays can't land here
    (Architecture review): `_quarantine_corrupt_pending` moves the
    existing `<aid>.json` pending file into place via `os.replace` — no
    temp intermediates ever enter the dir — so the `.json` filter sees
    every file the writer path can create. CI-found (PR #1169): the
    prune never creates the dir — `_quarantine_dir()` makedirs, which a
    prune must not do (PermissionError on a read-only approvals root
    would crash housekeeping instead of no-op'ing). A missing dir just
    means nothing to prune.
    """
    if limit is None:
        limit = _QUARANTINE_KEEP
    # Deliberately NOT _quarantine_dir(): that helper makedirs, and a
    # prune must never create the thing it prunes. Missing/unreadable
    # dir => nothing to do.
    d = os.path.join(APPROVALS, "pending-quarantine")
    try:
        names = [fn for fn in os.listdir(d) if fn.endswith(".json")]
    except OSError:
        return
    if len(names) <= limit:
        return
    entries = []
    for fn in names:
        try:
            entries.append((os.path.getmtime(os.path.join(d, fn)), fn))
        except OSError:
            continue
    entries.sort()
    for _, fn in entries[:max(0, len(entries) - limit)]:
        try:
            os.remove(os.path.join(d, fn))
        except OSError:
            pass


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

    Called by _housekeeping_if_due() (cadence-gated), after _sweep_answered().
    Pruning is mtime-ordered on purpose: it never parses file contents, so the
    prune itself stays cheap even as history grows. A count gate skips the
    mtime stat storm entirely when the dir is within the cap (issue #620).
    Races with a concurrent answer are benign — only the oldest files are
    ever deletion candidates, and a lost race surfaces as FileNotFoundError,
    which is tolerated."""
    if limit is None:
        limit = _CONSUMED_KEEP
    d = consumed_dir()
    try:
        names = [fn for fn in os.listdir(d) if fn.endswith(".json")]
    except OSError:
        return
    # Issue #620: skip the mtime stat storm when nothing is over the cap —
    # the prune only has work to do when the dir actually grew past it.
    if len(names) <= limit:
        return
    entries = []
    for fn in names:
        try:
            entries.append((os.path.getmtime(os.path.join(d, fn)), fn))
        except OSError:
            continue
    entries.sort()
    for _, fn in entries[:max(0, len(entries) - limit)]:
        try:
            os.remove(os.path.join(d, fn))
        except OSError:
            pass


# Issue #620: _sweep_answered() + _prune_consumed() ran after EVERY answer —
# a full answered/ listing and a consumed/ listdir + getmtime-per-file +
# sort in the request hot path. Strays only age into sweep eligibility on
# the grace cadence (default a day) and the prune cap is already soft, so
# the pair now runs at most once per _HOUSEKEEPING_INTERVAL_S (default one
# housekeeping runs at most once per _HOUSEKEEPING_INTERVAL_S (default one
# hour) via _housekeeping_if_due(); the first call in a process always runs
# (None sentinel: never ran). Read at call time so tests can force
# always-run by patching the module attribute to 0.
_HOUSEKEEPING_INTERVAL_S = _env_int("CONFIRM_HOUSEKEEPING_INTERVAL_S", 3600, 60)
_housekeeping_lock = threading.Lock()
_last_housekeeping_mono = None


def _reset_housekeeping_for_tests():
    """Test hook: make the next _housekeeping_if_due() call run."""
    global _last_housekeeping_mono
    with _housekeeping_lock:
        _last_housekeeping_mono = None


def _housekeeping_if_due():
    """Run the answered-sweep + consumed-prune + quarantine-prune at most
    once per interval.

    Returns True when the trio ran. Benign under handler concurrency: the
    timestamp commits under _housekeeping_lock before the work starts, so
    two threads can't both decide "due"; the sweep and both prunes are
    individually race-tolerant (unique filenames — aids are never reused —
    oldest-only deletes, all OSError paths tolerated). Note the quarantine
    prune's mtime snapshot can go stale: a quarantine move replaces in
    place via os.replace, refreshing mtime, so a stale snapshot can evict
    a recently-refreshed file early — the eviction itself stays safe and
    every quarantine move is journaled in the audit log."""
    with _housekeeping_lock:
        global _last_housekeeping_mono
        now = time.monotonic()
        if (_last_housekeeping_mono is not None
                and now - _last_housekeeping_mono < _HOUSEKEEPING_INTERVAL_S):
            return False
        _last_housekeeping_mono = now
    _sweep_answered()
    _prune_consumed()
    _prune_quarantine()
    return True


def _answered_api_item(it):
    """Issue #1: JSON surface for the answered-history poller.
    Allowlisted fields only. H20: a denied item additionally carries its
    re-open CSRF nonce so the answered card can offer the re-open form —
    non-deny items carry no nonce. S3 (#546): an expired item carries
    its expired_at/expired_by so the answered card can render the Expired
    badge — the answer fields are never reused for an expiry (design §2),
    so both families ride the feed with their own stamp fields."""
    out = {
        "id": str(it.get("id", "")),
        "summary": str(it.get("summary", "")),
        "kind": str(it.get("kind", "")),
        "decision": str(it.get("decision", "")),
        "answered_by": str(it.get("answered_by", "")),
        "answered_at": str(it.get("answered_at", "")),
        "expired_at": str(it.get("expired_at", "")),
        "expired_by": str(it.get("expired_by", "")),
        # Issue #73: the answered history shows the grant lifetime the
        # owner authorized on the approval page (1h default, 24h chosen).
        "grant_ttl_hours": str(it.get("grant_ttl_hours", "")),
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
        elif dec == "expired":
            # S3 (#546): the third terminal decision gets a badge too —
            # distinct style (amber), never approve green / deny red.
            badge = '<span class="badge badge-expired">expired</span>'
        if dec == "expired":
            # Design §2: the answer fields are never reused for an expiry —
            # the meta line shows the record's own expired_at/expired_by.
            meta = _meta_line([
                ("expired by %s" % it.get("expired_by"))
                if it.get("expired_by") else "expired",
                it.get("expired_at") or "",
                it.get("kind") or ""])
        else:
            meta = _meta_line([
                ("by %s" % it.get("answered_by"))
                if it.get("answered_by") else "",
                it.get("answered_at") or "",
                it.get("kind") or "",
                # Issue #73: the grant lifetime the owner authorized,
                # in the JS card's vocabulary — pre-#73 records carry
                # no grant_ttl_hours and render exactly as before.
                ("grant %sh" % it.get("grant_ttl_hours"))
                if dec == "approve" and it.get("grant_ttl_hours") else ""])
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


def _expired_record_link_html(aid):
    """S3 (#546): for the expired 410 pages. When a terminal expired
    record already exists for this aid in consumed/ (stamped by one of
    the reapers before the synchronous path reaped the pending file),
    return the answered-history link — the human can see the Expired
    badge card instead of a dead end. Otherwise "" — no record, no
    history to point at, and the bare 410 stands honest. Never raises:
    a corrupt or foreign consumed/ file must not 500 an error page."""
    if not ID_RE.match(aid):
        return ""
    try:
        with open(os.path.join(consumed_dir(), aid + ".json")) as f:
            rec = json.load(f)
    except (OSError, ValueError):
        return ""
    if isinstance(rec, dict) and rec.get("decision") == "expired":
        return ('<p class="nav"><a href="/answered">'
                "see it in the answered history</a></p>")
    return ""


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

    def _err(self, msg, code, suffix=""):
        # S3 (#546): `suffix` carries pre-rendered HTML inserted before
        # the back-nav (the expired 410s use it for the answered-history
        # link). It is the caller's responsibility to build it from
        # trusted fragments only — msg stays escaped, suffix is markup.
        self._send_html('<div class="card"><p>%s</p></div>%s'
                        '<p class="nav"><a href="/">back to pending</a></p>'
                        % (html.escape(msg), suffix), code, title="Approvals")

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
                    # S3 (#546): when a terminal expired record already
                    # exists for the aid, the 410 links the human to the
                    # answered history where the Expired badge card
                    # renders — otherwise the bare 410 stands.
                    # #539: stamp the S1 expired-approval terminal record
                    # BEFORE removing the pending file (stamp-then-delete:
                    # a crash between the two self-heals on the next reap
                    # — the stamp is EEXIST-skipped, the delete retried —
                    # while the reverse order could lose the expiry with
                    # no record at all). If the stamp fails (e.g. ENOSPC),
                    # keep the pending file so a later reap retries.
                    # Issue #945: the expired stamp serializes against the
                    # ingest's approve path and the answer path in other
                    # processes (aid is ID_RE-validated above, so the lock
                    # never sees a hostile aid).
                    try:
                        with _stamp_lock(aid):
                            _stamp_expired_consumed(aid, it, p, "confirmd")
                    except ValueError:
                        # Malformed aid: refuse to touch consumed/, but
                        # still reap the expired file below.
                        pass
                    except RuntimeError as e:
                        # The stamp lock is fail-closed: keep the pending
                        # file for a later reap and audit the distinct
                        # event instead of stamping without the lock.
                        _evict_aid_lock(aid)
                        audit_log("expired-reap-lock-failed",
                                  self.client_address[0], login,
                                  "id=%s err=%s" % (aid, e))
                        self._err("This approval expired and was removed.",
                                  410,
                                  suffix=_expired_record_link_html(aid))
                        return
                    except OSError:
                        _evict_aid_lock(aid)
                        audit_log("expired-reaped", self.client_address[0],
                                  login, "id=%s" % aid)
                        self._err("This approval expired and was removed.",
                                  410,
                                  suffix=_expired_record_link_html(aid))
                        return
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                    _evict_aid_lock(aid)
                    audit_log("expired-reaped", self.client_address[0], login,
                              "id=%s" % aid)
                    self._err("This approval expired and was removed.", 410,
                              suffix=_expired_record_link_html(aid))
                    return
                # Finding 48 + issue #75: mint a CSRF nonce into the
                # SERVER-SIDE ring (issue #78 — the ring is keyed by aid
                # and never written to the requester-authored file, so the
                # old tmp+replace write-back of the ring is gone; a fresh
                # GET in a second tab must not invalidate the first tab's
                # form).
                nonce = _mint_csrf_nonce(aid)
            body = ("<h1>Approval %s</h1>%s"
                    '<p class="sub">Approving mints a credential grant for '
                    'this request. Denying discards it.</p>'
                    '<form method="post" action="/answer">'
                    '<input type="hidden" name="id" value="%s">'
                    '<input type="hidden" name="csrf" value="%s">'
                    # Issue #73: the grant lifetime is the owner's
                    # per-approval choice, not a hidden default — the
                    # radio makes the minted grant's lifetime visible at
                    # decision time. Default shortest (1h); the server
                    # refuses any value outside the offered choices.
                    # Design B1: 52px tap rows like the decision buttons;
                    # B3: the hint states what the lifetime governs.
                    '<fieldset class="ttl">'
                    '<legend>Grant lifetime</legend>'
                    '<p class="sub">How long the minted credential grant '
                    'stays valid (approve only).</p>'
                    '<label><input type="radio" name="ttl" value="1" '
                    'checked> 1 hour (default)</label>'
                    '<label><input type="radio" name="ttl" value="24"> '
                    '24 hours</label>'
                    '</fieldset>'
                    '<div class="btnrow">'
                    '<button class="btn btn-approve" id="approveBtn" '
                    'name="decision" value="approve">Approve</button>'
                    '<button class="btn btn-deny" name="decision" '
                    'value="deny">Deny</button>'
                    "</div></form>"
                    '<p class="nav"><a href="/">back to pending</a></p>'
                    # Design review #4: a single large tap must not mint a
                    # credential grant. First tap arms, second confirms.
                    # Issue #73 (Design B4): the armed text restates the
                    # chosen lifetime, so the confirm step shows exactly
                    # what the owner is minting even if the fieldset has
                    # scrolled off-view.
                    '<script>'
                    '"use strict";'
                    'var b=document.getElementById("approveBtn");'
                    'b.addEventListener("click",function(e){'
                    'if(!b.dataset.armed){'
                    'e.preventDefault();'
                    'b.dataset.armed="1";'
                    'b.classList.add("armed");'
                    'var t=(document.querySelector(\'input[name="ttl"]:checked\')'
                    '||{}).value||"1";'
                    'b.textContent="Tap again to confirm approval ("+t+'
                    '"h grant)";'
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
        # Issue #73: the grant lifetime is the owner's per-approval
        # choice. The value is refused (400), never coerced, when it
        # falls outside the page's offered choices — a crafted value
        # must not widen the mint beyond what the page displayed.
        try:
            ttl_hours = _parse_grant_ttl(form.get("ttl", [""])[0])
        except ValueError:
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
            # Issue #945: the cross-process stamp lock serializes the
            # whole check->mint->consume window against the box ingest
            # (a separate process, outside _aid_lock) and the reapers —
            # without it the ingest can mint a grant while this path
            # records a terminal state, leaving a live grant under a
            # deny/expired record. Lock order _aid_lock -> stamp lock
            # matches the reaper sites below; _answer_locked documents
            # the contract. Fail-closed: an untakeable lock is a 500
            # with a distinct audit event, never a silent proceed —
            # the pending file stays and the owner retries.
            try:
                lock = _stamp_lock(aid)
            except RuntimeError as e:
                audit_log("answer-lock-failed", self.client_address[0],
                          login, "id=%s err=%s" % (aid, e))
                self._err("Could not record the answer — try again.", 500)
                return
            with lock:
                return self._answer_locked(login, aid, csrf, decision,
                                           ttl_hours)

    def _answer_locked(self, login, aid, csrf, decision,
                       ttl_hours=GRANT_TTL_DEFAULT):
        """POST /answer body. The caller holds _aid_lock(aid) and the
        cross-process stamp lock (issue #945); every early return inside
        is a normal handler response."""
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
        # and belong to the aid's SERVER-SIDE nonce ring (issue #78) — the
        # requester-authored file is never consulted. Malformed/missing nonces are
        # audited as CSRF violations; a well-formed but stale/unknown nonce
        # (second tab, back-button resubmit) is audited under its own event
        # (arch review B1): attacker-shaped probes are exactly
        # "well-formed but unknown," so the trail stays distinguishable
        # without desensitizing review of real violations.
        if not csrf or not NONCE_RE.match(csrf):
            self._deny(self.client_address[0], login, "csrf: bad nonce")
            return
        if not _csrf_nonce_ok(aid, csrf):
            audit_log("csrf:stale-nonce", self.client_address[0], login,
                      "id=%s" % aid)
            self._err("This form is stale — reload the page and try "
                      "again.", 403)
            return
        # Issue #73: re-validate the owner-chosen grant TTL here (do_POST
        # validates the form first, but this method is the unit under
        # test and may be reached with any value). A bad value is
        # refused, never coerced into a lifetime the page never offered.
        try:
            ttl_hours = _parse_grant_ttl(ttl_hours)
        except ValueError:
            self._err("bad request", 400)
            return
        # Finding 53(a): expired items are refused, not silently denied.
        # S3 (#546): link to the answered history when a terminal expired
        # record already exists (see the GET detail reap above).
        # #539: stamp the S1 expired-approval terminal record BEFORE
        # removing the pending file (stamp-then-delete: a crash between
        # the two self-heals on the next reap — the stamp is EEXIST-skipped,
        # the delete retried — while the reverse order could lose the
        # expiry with no record at all). If the stamp fails (e.g. ENOSPC),
        # keep the pending file so a later reap retries, and still refuse
        # honestly with 410.
        if is_expired(it):
            try:
                _stamp_expired_consumed(aid, it, src, "confirmd")
            except ValueError:
                # Malformed aid: refuse to touch consumed/, but still
                # remove the expired pending file below.
                pass
            except OSError:
                _evict_aid_lock(aid)
                audit_log("expired-reaped", self.client_address[0], login,
                          "id=%s" % aid)
                self._err("This approval expired and was removed.", 410,
                          suffix=_expired_record_link_html(aid))
                return
            try:
                os.remove(src)
            except OSError:
                pass
            _evict_aid_lock(aid)
            audit_log("expired-reaped", self.client_address[0], login,
                      "id=%s" % aid)
            self._err("This approval expired and was removed.", 410,
                      suffix=_expired_record_link_html(aid))
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
        if decision == "deny":
            # Issue #73: belt-and-braces — a requester-planted
            # grant_ttl_hours must not survive into the answered
            # record of a denial (deny mints nothing, so the record
            # must not claim a lifetime).
            it.pop("grant_ttl_hours", None)
        # Finding 60: on approve, mint the grant via the single writer
        # BEFORE moving to consumed/. Finding 64: validate the tuple.
        # Issue #294: whether the writer refused at mint time for a
        # crossed expiry (exit 3) — routed into the honest #240 block
        # below. Defaults False; only the mint path can set it.
        writer_refused_expired = False
        if decision == "approve":
            # Issue #534: refuse to START the mint when the remaining
            # validity is under the worst-case mint window — an expiry
            # crossing mid-mint would land a grant for an already-expired
            # approval, and there is no revoke path. The pending file is
            # left in place: the render reap stamps `expired` when the
            # clock crosses (the honest outcome label for a request whose
            # window lapsed), and the 410 tells the owner to file a fresh
            # request.
            if not _grant_window_ok(it):
                exp = _parse_expiry(it.get("expires"))
                remaining = (0 if exp is None else
                             max(0, int((exp - datetime.now(
                                 timezone.utc)).total_seconds())))
                audit_log("approve-refused-expiry-window",
                          self.client_address[0], login,
                          "id=%s remaining=%ds" % (aid, remaining))
                _evict_aid_lock(aid)
                self._err("This approval is too close to expiry to grant "
                          "safely — wait for it to expire, or ask the agent "
                          "to file a fresh request.", 410)
                return
            name = it.get("credential")
            host = it.get("host")
            method = (it.get("method") or "").upper()
            if not name or not host or not method:
                audit_log("grant-refused", self.client_address[0], login,
                          "id=%s reason=missing credential/host/method" % aid)
                self._err("Cannot mint grant: missing fields.", 400)
                return
            # Call the single writer (finding 60). Issue #294: hand the
            # approval's expiry instant to the writer so it can fail
            # closed at mint time (its own fresh clock, under the mint
            # lock) if the instant crossed while confirmd was working —
            # the second layer behind the #534 pre-mint guard above and
            # the #240 post-mint re-check below.
            mint_argv = [GRANT_WRITER, "add",
                         "--credential", name,
                         "--host", host,
                         "--method", method,
                         "--path-prefix", it.get("path_prefix") or "/",
                         "--approval-id", aid,
                         "--scope", it.get("scope") or "",
                         "--job", it.get("job") or "",
                         "--ttl-hours", str(ttl_hours)]
            # Issue #73: record the lifetime the owner chose, so the
            # answered history and the audit trail show the exact grant
            # lifetime that was authorized (not the writer's default).
            it["grant_ttl_hours"] = ttl_hours
            approval_expires = it.get("expires")
            if approval_expires:
                mint_argv += ["--approval-expires", str(approval_expires)]
            # Issue #294: the writer's distinct exit codes let confirmd
            # route a mint-time expiry refusal into the honest #240 path
            # below instead of the generic 500. Exit 3 = the approval's
            # expiry crossed (honest 410); anything else non-zero —
            # including 4 = unparseable instant, a bug rather than an
            # expiry — keeps the generic failure (it must not be
            # mislabeled as expired).
            try:
                out = subprocess.run(
                    mint_argv,
                    capture_output=True, text=True,
                    timeout=_GRANT_MINT_TIMEOUT)
                if out.returncode != 0:
                    if out.returncode == 3:
                        writer_refused_expired = True
                    else:
                        audit_log("grant-failed", self.client_address[0],
                                  login,
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
        # un-minted (no per-approval-id revoke path in the grant-writer
        # interface — `revoke` is by job), so
        # the fix is the refusal + the distinct trail event, not
        # retroactive revocation. Issue #294 adds the writer-side layer:
        # the approval's expiry is passed to grant-writer above, which
        # refuses at mint time (its own fresh clock, under the mint lock)
        # when the instant has crossed — so no live grant can exist for
        # an approval whose expiry crossed before mint completion. A
        # writer refusal (exit 3) routes into this same honest block, so
        # the 410 + distinct trail event is the outcome in both cases.
        # This refusal + distinct trail event remains the confirmd-side
        # backstop either way.
        if writer_refused_expired or is_expired(it):
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
        try:
            os.remove(src)
        except FileNotFoundError:
            # Issue #195 (residual): the pre-consume exists check is a
            # TOCTOU window — an out-of-process remover (a second
            # confirmd, an operator, a reaper racing the check) can
            # delete the pending file after the check above. The answer
            # record above is already truthfully written (the grant
            # mint, if any, really happened), but the pending file is
            # verifiably gone, so say so honestly instead of raising an
            # uncaught FileNotFoundError (a 500 on a legitimate answer).
            # FileNotFoundError only, deliberately not bare OSError: an
            # EACCES-style failure leaves the pending file in place and
            # "not found or already answered" would be a lie for it.
            audit_log("answer-raced-consume", self.client_address[0],
                      login, "id=%s decision=%s" % (aid, decision))
            _evict_aid_lock(aid)
            self._err("not found or already answered", 404)
            return
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
        # Issue #620: sweep+prune no longer run on every answer — the pair
        # is cadence-gated (_housekeeping_if_due, default one hour) so the
        # hot path skips the full directory scans; strays age into sweep
        # eligibility on the grace cadence anyway, and the prune's count
        # gate keeps the cap without the per-answer stat storm.
        _housekeeping_if_due()
        # Issue #73: the answer audit carries the granted lifetime, so
        # the trail shows exactly what the owner authorized.
        detail = "id=%s decision=%s requester=%s" % (aid, decision,
                                                     requester)
        if decision == "approve":
            detail += " ttl=%dh" % ttl_hours
        audit_log("answer", self.client_address[0], login, detail)
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
        # Issue #537: the new item is pending — index it so the next
        # idempotency check opens one file instead of scanning pending/.
        _index_reopened(aid, new_aid)
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


def _kill_connection(request, client_address):
    """Issue #472: fail-closed abort of a connection that exceeded the
    cumulative per-connection deadline. shutdown() unblocks the handler
    thread's in-flight recv/send, so the pool slot is released even while
    the peer is actively trickling; the kill is audited so the trail shows
    the mitigation, not silence."""
    try:
        request.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass  # already closed / peer gone — that's the goal state anyway
    audit_log("conn-deadline", client_address[0], None,
              "cumulative per-connection deadline exceeded; "
              "connection aborted")



class BoundedThreadingHTTPServer(_BoundedHTTPServer):
    # Issue #472 (kept from PR #476): confirmd keeps the cumulative
    # per-connection deadline — a peer dripping >=1 byte per socket-timeout
    # can no longer pin a pool slot indefinitely. The timer + slot-release
    # mechanism lives in the shared scripts/bounded_http.py helper
    # (issue #471) behind its connection_deadline switch; confirmd sets
    # the switch to 60 and audits the kill here because audit_log is
    # confirmd-specific. cred-ui and waitlistd leave the switch off, so
    # their behavior is unchanged from the #471 adoption.
    connection_deadline = 60

    def kill_connection(self, request, client_address):
        # Audit is confirmd-specific, so it lives here: the shared helper's
        # base kill_connection performs the fail-closed abort, and this
        # override routes through confirmd's own _kill_connection (abort +
        # audit), which is also the unit-tested abort primitive.
        _kill_connection(request, client_address)

def main():
    # Issue #70: fail closed at startup. No stale-literal fallback exists
    # anymore: if the bind address cannot be determined (no CONFIRM_BIND
    # pin and `tailscale ip -4` failed), serving would run finding 47's
    # self-peer refusal on a guessed address — so refuse to serve.
    # systemd's Restart=on-failure retries once tailscaled is back.
    if BIND is None:
        print("confirmd FATAL: cannot determine the tailnet bind address "
              "(no usable CONFIRM_BIND pin and `tailscale ip -4` failed); "
              "refusing to serve", flush=True)
        sys.exit(1)
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
