#!/usr/bin/env python3
"""waitlistd — the waitlist-era control-plane service (H15 build, slice 2).

Implements the waitlist-era half of docs/HOSTED_SIGNUP_WEB_UI.md §7's
endpoint surface:

    POST /waitlist/form      path-B form intake (§4.2)
    GET  /waitlist/confirm   renders only — never changes state (§4.3)
    POST /waitlist/confirm   token as form field, not query string (§4.3)
    GET  /waitlist/forget    renders only — never changes state (slice 3c)
    POST /waitlist/forget    token as form field; deletes the row (slice 3c)
    GET  /go/selfhost        logs cta_click, 302s to the self-host docs (slice 3c)
    GET  /waitlist/claim     renders only — never changes state (claim slice)
    POST /waitlist/claim     invite token as form field; records the claim,
                             emits the `claimed` funnel event (claim slice)

The path-A email parser (WAITLIST_OPERATIONS.md §2) and the invite
sender (§7) landed in a later slice — they extend this module (submit_email,
mint_invite_token, send_invite_wave, rollover_expired_invites) plus the
operator CLIs site/waitlist_patha.py and site/waitlist_invites.py. Per
docs/WAITLIST_OPERATIONS.md §10 + site/README.md, the page is still NOT
deployable — the dead-form rule holds until every §10 item is live
(deployed endpoint, reminder/drop cron, inbox). The claim route the
invite email links to IS served by this daemon (the claim slice:
waitlist-era scope — token validation, the claim screen, the recorded
claim, the `claimed` funnel event; tenant-shell provisioning after the
claim belongs to the signup-era surface — WAITLIST_OPERATIONS.md §8).

Design decisions (all per the cited specs, no improvisation):

- Token: HMAC-SHA256 over "{entry_id}.{issued_at}.{nonce}.{normalized_email}",
  payload {owner_email, entry_id, issued_at} plus a per-mint nonce (a
  re-submit's fresh token never equals the consumed one, even within the
  same second), single-use, 14-day expiry (WAITLIST_OPERATIONS.md §4). The operator key comes from the
  WAITLIST_HMAC_KEY env var and NEVER appears in the repo, logs, or
  error pages.
- GET /waitlist/confirm never changes state: no row writes, no token
  consumption, no funnel events, no spool writes (FUNNEL_MEASUREMENT.md
  §4 — the mail-scanner threat model).
- Confirm-page copy is verbatim from docs/FUNNEL_MEASUREMENT.md §§4.2–4.3
  (the button page shape — headline, masked line, "Yes, hold my place." —
  and the four states' copy). Short-local-part masking renders fully
  (•••) per §4.2; the mask never discloses the full local part.
- The confirm-email body is the WAITLIST_OPERATIONS.md §4 DRAFT with
  the path-split opener: path-B rows get the form opener, path-A rows the
  "your agent asked" opener.
- Honeypot trips are accepted SILENTLY: HTTP 200 with the same rendering
  as a success, nothing written, nothing
  emitted — the spam learns nothing (HOSTED_SIGNUP_WEB_UI.md §4.2).
- Time-trap failures and per-IP rate-limit trips are silent for the same
  reason (a service-local anti-abuse choice; §4.2's silence mandate covers
  honeypot trips).
- Email normalization: lowercase + strip everything after "+" in the
  local part; one pending entry per normalized address — re-submits
  refresh the timestamp and re-send the confirm email with a fresh
  token, counting toward the 3/24h transactional-email cap
  (WAITLIST_OPERATIONS.md §§4/6).
- funnel_events per docs/FUNNEL_MEASUREMENT.md §3.4: exactly the
  (event, at, ref, attrs) 4-tuples this slice can emit —
  `waitlist_submitted` (attrs path=form), `confirm_sent` (no attrs),
  `confirmed` (attrs via=original|reminder — via follows which email
  carried the live token), `reminder_sent` (no attrs, +7d job),
  `dropped` (no attrs, 14d job), `purged` (no attrs, 30d job),
  `forgot` (no attrs — signed footer-link deletion), `cta_click`
  (attrs src — the /go/selfhost shim). `scripts/funnel_metrics.py`
  (PR #141) is the consumer; the emitted JSONL must stay parseable by it.
- No unauthenticated position lookup exists anywhere in this service:
  queue position is disclosed only inside signed emails
  (WAITLIST_OPERATIONS.md §6). The "check your inbox" page echoes the
  full SELF-SUBMITTED owner address — it came from the reader's own
  form, so there is no privacy cost (HOSTED_SIGNUP_WEB_UI.md §4.2).

Config (env):
    WAITLIST_HMAC_KEY    operator HMAC key (hex or raw string) — REQUIRED,
                         fail loud at startup if unset. Placeholders only.
    WAITLIST_DATA        operator-owned data dir (rows.jsonl,
                         funnel_events.jsonl, consumed_tokens.txt, spool/) —
                         REQUIRED, fail loud if unset or unwritable. Never
                         the repo, never a path the loop can see
                         (WAITLIST_OPERATIONS.md §5).
    WAITLIST_PUBLIC_HOST public origin for links in queued email,
                         e.g. https://waitlist.example.com
                         (default https://waitlist.example.invalid —
                         the RFC placeholder; the operator substitutes
                         the real host at deploy per site/README.md).
    WAITLIST_BIND        bind address (default 127.0.0.1).
    WAITLIST_PORT        port (default 8765).

Anti-abuse constants (operator-tunable; the final verification levels
feed NEEDS_USER.md's Abuse-controls item — LANDING_PAGE_COPY.md §4):
    TIME_TRAP_MIN_SECONDS = 3   — submissions faster than this after the
                                 page render are treated as automated.
    IP_RATE_LIMIT = 10          — max form submissions per client IP per
    IP_RATE_WINDOW = 3600         hour (sliding window, in-process).
    EMAIL_SEND_CAP = 3          — max transactional sends per address per
    EMAIL_SEND_WINDOW = 86400     24h, all reply types counted together
                                  (WAITLIST_OPERATIONS.md §4).
    TOKEN_TTL_SECONDS = 14*86400 — confirm-link lifetime.
    FORGET_TTL_SECONDS = 7*86400 — the §5 forget-link lifetime ("signed
        footer link honored ≤7d"). Forget tokens are domain-separated
        from confirm tokens by wire format (forget tokens are
        `forget.`-prefixed 5-part; confirm tokens keep the pre-slice-3c
        4-part format), so a confirm token can never validate at
        /waitlist/forget and a forget token can never validate at
        /waitlist/confirm.
    REMINDER_LEAD_SECONDS = 7*86400 — the +7d reminder fires when
        now >= drop_at - REMINDER_LEAD_SECONDS.
    DROP_TTL_SECONDS = 14*86400 — drop_at is set once at row creation
        (= submitted_at + DROP_TTL_SECONDS) and is NEVER refreshed by a
        re-submit: WAITLIST_OPERATIONS.md §4 drops "unconfirmed 14 days
        after submission", and a re-submit must not postpone the drop.
    PURGE_TTL_SECONDS = 30*86400 — a dropped row is deleted
        PURGE_TTL_SECONDS after dropped_at (WAITLIST_OPERATIONS.md §5:
        "row deleted 30d after drop"). The funnel events stay: `dropped`
        and `purged` events in funnel_events.jsonl are the audit trail —
        the PII leaves with the row.

stdlib only. Tested by scripts/test_waitlistd.py.
"""

import base64
import contextlib
import fcntl
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIME_TRAP_MIN_SECONDS = 3
IP_RATE_LIMIT = 10
IP_RATE_WINDOW = 3600
# #390: bound on distinct client IPs kept in the in-process abuse-rate
# state — the dict itself is never pruned, so without this it grows one
# key per distinct submitter IP for the life of the process.
IP_HITS_MAX_KEYS = 10000
# #390: minimum seconds between _ip_hits bound sweeps — a flood of unique
# IPs must not turn every request into an O(dict) rebuild.
IP_HITS_SWEEP_COOLDOWN = 60
EMAIL_SEND_CAP = 3
EMAIL_SEND_WINDOW = 86400
TOKEN_TTL_SECONDS = 14 * 86400
FORGET_TTL_SECONDS = 7 * 86400
INVITE_TTL_SECONDS = 14 * 86400  # invite claim window (WAITLIST_OPERATIONS §7)
REMINDER_LEAD_SECONDS = 7 * 86400
DROP_TTL_SECONDS = 14 * 86400
PURGE_TTL_SECONDS = 30 * 86400

# Path-A (email) intake: max submissions per sender address per 24h
# (WAITLIST_OPERATIONS.md §6 — "a Muse fleet *can* spray"; the confirm
# gate is what makes spraying worthless).
PATHA_INTAKE_LIMIT = 3
PATHA_INTAKE_WINDOW = 86400

# /go/selfhost — where the marketing page's self-host CTA lands
# (site/index.html, docs/FUNNEL_MEASUREMENT.md §3.2's `selfhost` CTA
# source). The repo README's "Try it" section is the self-host surface.
SELFHOST_URL = "https://github.com/ntindle/spark-vm#try-it"

# The canonical CTA section sources the page build wires
# (docs/FUNNEL_MEASUREMENT.md §3.2). A src outside this set is logged
# with no src attr — the daemon never emits unknown src values, so no
# typoed ?src= can silently open a new rollup bucket. Mirrors KNOWN_SRCS
# in scripts/funnel_metrics.py — keep the two in sync.
CTA_SRCS = {"hero", "trust", "faq", "final", "selfhost"}

EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,}$"
)
MAX_EMAIL_LEN = 254

# Confirm-page copy, verbatim from docs/FUNNEL_MEASUREMENT.md §4.3.
COPY_PENDING_LINE = "Invites go out in waitlist order — each invite holds for 14 days."
COPY_CONFIRMED = (
    "You\u2019re on the list — invites go out in waitlist order. "
    "Watch your inbox."
)
COPY_EXPIRED = "This link expired — waitlist links last 14 days."
COPY_REJOIN = "Join the waitlist again"

# Claim-page copy. Verbatim from docs/WAITLIST_OPERATIONS.md §7's invite
# "What happens next" block (identity linking, tailnet, card on file) —
# the what-happens-next the claim page shows is the invite email's, so
# the two never diverge. The page makes no pricing promise (the exact
# numbers were in the invite email) and no box-provisioning promise
# (tenant-shell provisioning is the signup-era surface — §8).
COPY_CLAIM_NEXT = (
    "What happens next: you\u2019ll link your agent\u2019s identity (it proves "
    "itself with a key, you approve the fingerprint), bring your Tailscale "
    "tailnet, and put a card on file. Your box is a real computer \u2014 files, "
    "jobs, and the desktop persist. The exact pricing was in your invite "
    "email."
)
COPY_CLAIM_EXPIRY = (
    "This invite expires 14 days after it was sent \u2014 after that the slot "
    "rolls to the next entry. Nothing happens until you click the button."
)
COPY_CLAIM_INACTIVE = (
    "This invite link is no longer live \u2014 invite links expire 14 days "
    "after the wave, and a superseded link lands here too. After expiry "
    "the slot rolls to the next entry, you rejoin the line at the back, "
    "and you\u2019ll be invited again in a later wave, when one runs."
)
CONFIRM_SUBJECT = "Confirm your spark-vm waitlist spot"
REMINDER_SUBJECT = "Reminder: your spark-vm waitlist spot is waiting on one click"

# Every transactional email's footer carries the §5 signed forget link.
# {forget_link} is the one-click forget URL for that row's signed token
# (7-day lifetime, single-use). Kept as one paragraph of plain text so it
# survives every mail client. Defined once and appended to every body —
# never duplicated inline.
FORGET_FOOTER = """\

Forget this entirely? [ Delete your waitlist entry ]: {forget_link}
This deletion link lasts 7 days — a fresh one arrives with every email.
"""

# Reminder email, verbatim from docs/WAITLIST_OPERATIONS.md §4 DRAFT
# (opener split by submission path). The {position} line is the queue
# position per §7 ("You're #N in line"); {confirm_link} follows the
# prominent-action pattern and carries the same (or a fresh) token.
REMINDER_OPENERS = {
    "email": "Your agent put this address on the spark-vm hosted waitlist.",
    "form": "You asked to join the spark-vm hosted waitlist with this address.",
}

REMINDER_BODY = """\
{opener}

[ Confirm this address ]: {confirm_link}

You're #{position} in line — we don't estimate dates. Confirm it so we
can email you when hosted boxes open up. No card, no commitment.

This is the last reminder; unconfirmed spots are dropped automatically.
""" + FORGET_FOOTER

FORGET_SUBJECT = "Your spark-vm waitlist entry has been deleted"

# Deletion confirmation, sent after the row is actually deleted
# (WAITLIST_OPERATIONS.md §5: "the row is deleted only after the link is
# clicked (proving inbox access), within 7 days, with a confirmation
# sent"). Plain text, no links — there is nothing left to link to.
FORGET_CONFIRM_BODY = """\
Your spark-vm waitlist entry for {owner_email} has been deleted.

All of its data is gone from the waitlist store. If you rejoin later,
you'll start at the back of the line — waitlist order follows the
confirmation date.

Nothing else to do.
"""

CONFIRM_BODY_PATH_B = """\
You joined the spark-vm hosted waitlist — one click confirms this address.

[ Confirm this address ]: {confirm_link}

What this means: we'll email you when hosted boxes open up — with real
pricing before we ask for anything else.

No card is required for the waitlist, and this confirmation doesn't
commit you to anything.

What this doesn't mean: this confirms we can reach you. It doesn't
verify your agent's identity — linking your agent's identity happens
when you claim your box.

Didn't ask for this? Ignore this email — unconfirmed addresses are
dropped automatically.
""" + FORGET_FOOTER

# Path-A confirm email: the §4 DRAFT with the path-A opener ("Your agent
# asked to join the spark-vm hosted waitlist with this address as the
# owner contact."). Landed with the email parser (slice 3 remainder) —
# before that only the path-B body existed. The rest of the body is
# identical to path B: the funnel confirms the right human, not the Muse.
CONFIRM_BODY_PATH_A = """\
Your agent asked to join the spark-vm hosted waitlist with this address
as the owner contact.

[ Confirm this address ]: {confirm_link}

What this means: we'll email you when hosted boxes open up — with real
pricing before we ask for anything else.

No card is required for the waitlist, and this confirmation doesn't
commit you to anything.

What this doesn't mean: this confirms we can reach you. It doesn't
verify your agent's identity — linking your agent's identity happens
when you claim your box.

Didn't ask for this? Ignore this email — unconfirmed addresses are
dropped automatically.
""" + FORGET_FOOTER

# Path-A clarification reply. First paragraph verbatim from
# docs/WAITLIST_OPERATIONS.md §2 DRAFT; the `Owner:`-line example below
# it teaches the parser's documented override syntax (it is an addition,
# not spec text). Sent only when the inbound message passes SPF/DKIM/DMARC
# alignment on the From domain; unauthenticated mail goes to the silent
# operator triage queue instead (no backscatter — §6).
#
# Deliberately NO forget footer: the clarification is a reply about
# intake, not about a row — nothing is waitlisted yet, so a deletion
# link would be dishonest, and a signed token to an unverified sender
# would be a deletion oracle aimed at the wrong inbox. §5's "every
# email footer" rule covers emails about a live row; once the owner
# address is confirmed, every email after that carries the link.
CLARIFY_SUBJECT = "Which address should we use for the spark-vm waitlist?"

CLARIFY_BODY = """\
We couldn't tell which address is the owner. Please reply with exactly
one owner email address — the human who'll approve spend and receive
the invite.

If you meant to give it in your first email, put it on its own line
like this: Owner: you@example.com

Nothing is waitlisted yet, so there's no deletion link in this email —
reply with the owner address and every email after that carries a deletion link.
"""

# Reply-"forget me" confirmation email (WAITLIST_OPERATIONS.md §5): a
# reply saying "forget me" is NOT honored on its own (Reply From is
# forgeable — a deletion oracle) — it triggers this confirmation email
# containing the signed forget link, and the row is deleted only after
# the link is clicked (proving inbox access), within 7 days, with a
# confirmation sent. Sent to the sender's address — only when it matches
# a row's owner email, so a forget reply can never touch someone else's
# row.
FORGET_REQUEST_SUBJECT = "Confirm deleting your spark-vm waitlist entry"

FORGET_REQUEST_BODY = """\
We got your "forget me" reply for {owner_email}.

Click this link to confirm the deletion:

[ Delete your waitlist entry ]: {forget_link}

The link lasts 7 days. Deleting removes everything we stored for this
address; if you rejoin later, you'll start at the back of the line —
waitlist order follows the confirmation date.

If you didn't send that reply, ignore this email — nothing is deleted
unless you click the link.
"""

# Invite email, verbatim from docs/WAITLIST_OPERATIONS.md §7 DRAFT. The
# pricing lines and trial terms are filled at send time from the decided
# pricing — the template never contains numbers (compliance: pricing
# appears exactly once before any card ask — here, in the invite email;
# no "free tier" wording; no launch-date promises). {position} is the
# invitee's signed position line ("You held #N in line"). The claim link
# points at the claim route — GET /waitlist/claim is served by waitlistd
# (the claim slice: renders-only GET, claim-recording POST, `claimed`
# funnel event); the email's honesty posture holds because the route
# exists in the deployed daemon this email is sent from, and the claim
# expiry clock is real: the invite expires in 14 days and the slot rolls
# to the next entry in line.
INVITE_SUBJECT = "You're off the waitlist — claim your box"

INVITE_BODY = """\
You're off the waitlist — hosted boxes are open.

[ Claim your box ]: {claim_link}

Pricing first — the exact numbers, before we ask for anything:
{pricing_lines}

{trial_terms}

What happens next: you'll link your agent's identity (it proves itself
with a key, you approve the fingerprint), bring your Tailscale tailnet,
and put a card on file. Your box is a real computer — files, jobs, and
the desktop persist.

You held #{position} in line — this invite expires in 14 days. After
that it rolls to the next entry in line.
""" + FORGET_FOOTER


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def utcnow():
    return datetime.now(timezone.utc)


def iso_z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def normalize_email(addr: str):
    """Lowercase + strip plus-tag; return None if not a plausible email."""
    addr = addr.strip()
    if len(addr) > MAX_EMAIL_LEN or not EMAIL_RE.match(addr):
        return None
    local, domain = addr.rsplit("@", 1)
    local = local.split("+", 1)[0].lower()
    if not local:
        # "+tag@example.com" passes the regex but strips to nothing — there
        # is no local part to deliver to.
        return None
    domain = domain.lower()
    return f"{local}@{domain}"


def masked_owner(normalized: str) -> str:
    """First 3 chars of the local part + ellipsis — except a local part of
    3 chars or fewer, which renders fully masked (FUNNEL_MEASUREMENT.md
    §4.2: the mask never discloses the full local part at any length —
    'sam' + '…' IS the full local part)."""
    local = normalized.split("@", 1)[0]
    if len(local) <= 3:
        return "•••"
    return f"{local[:3]}…"


# ---------------------------------------------------------------------------
# Cross-process data lock
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def data_lock(data_dir):
    """Advisory exclusive lock on the data dir, shared by the daemon and
    the lifecycle-job CLI (site/waitlist_jobs.py).

    waitlistd serializes its own threads with self._lock, but the jobs
    run as a SEPARATE process — the check-then-act sections (dedup on
    submit, token consume on confirm, reminder/drop scans) must not race
    across processes. Every mutating entry point takes this lock with the
    thread lock nested INSIDE it (lock order: data lock first, thread lock
    second — the jobs never take the thread lock, so there is no cycle).

    fcntl is POSIX-only, but the operator surface is Linux; the service
    already refuses to run without an operator-owned data dir, and the
    lock file lives inside it (never the repo)."""
    path = os.path.join(data_dir, "waitlist.lock")
    with open(path, "a", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class WaitlistService:
    """All waitlist logic; socket-free and directly testable."""

    def __init__(self, data_dir, hmac_key: bytes, public_host: str,
                 clock=None):
        self.data_dir = data_dir
        self.hmac_key = hmac_key
        self.public_host = public_host.rstrip("/")
        self.clock = clock or utcnow
        os.makedirs(data_dir, exist_ok=True)
        self.spool_dir = os.path.join(data_dir, "spool")
        os.makedirs(self.spool_dir, exist_ok=True)
        self.rows = {}          # entry_id -> row dict
        self.by_email = {}      # normalized owner_email -> entry_id
        self.consumed = set()   # consumed/invalidated token strings
        self._ip_hits = {}      # client ip -> [epoch ...] (in-process)
        self._ip_hits_last_sweep = 0.0  # epoch of last bound sweep (#390)
        # Serializes the check-then-act sections (dedup on submit, consume
        # on confirm) — the handler runs on ThreadingHTTPServer threads.
        self._lock = threading.Lock()
        self._load()

    # -- persistence ------------------------------------------------------

    def _append(self, name, obj):
        path = os.path.join(self.data_dir, name)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, sort_keys=True) + "\n")

    def _load(self):
        rows_path = os.path.join(self.data_dir, "rows.jsonl")
        if os.path.exists(rows_path):
            with open(rows_path, encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    # A kill -9 can tear the last append mid-line; a single
                    # torn line must never brick a restart — skip it loudly
                    # and load everything else.
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        sys.stderr.write(
                            "waitlistd: skipping torn rows.jsonl line "
                            f"{lineno}\n")
                        continue
                    if not isinstance(row, dict) or not row.get("entry_id"):
                        sys.stderr.write(
                            "waitlistd: skipping malformed rows.jsonl line "
                            f"{lineno}\n")
                        continue
                    if "drop_at" not in row and row.get("submitted_at"):
                        # Rows written before the lifecycle jobs existed have
                        # no drop_at. Backfill from submitted_at (the best
                        # available stand-in; new rows always set drop_at at
                        # creation, so this path fades as rows churn).
                        try:
                            first = datetime.fromisoformat(
                                row["submitted_at"].replace("Z", "+00:00"))
                        except ValueError:
                            first = self.clock()
                        row["drop_at"] = iso_z(first + timedelta(
                            seconds=DROP_TTL_SECONDS))
                    self.rows[row["entry_id"]] = row
                    if row.get("status") in ("pending", "confirmed"):
                        self.by_email[row["owner_email"]] = row["entry_id"]
                    else:
                        # Same invariant as _save_row: invited/dropped rows
                        # are never index-resolved. Without this, a
                        # post-restart _load would phantom-index invited
                        # rows that _save_row had popped — making
                        # invited-row handling depend on process age
                        # (resubmission could "resubmit" an invited row
                        # with a dead confirm link, or duplicate it).
                        # Invited rows are found by _live_row_by_email.
                        self.by_email.pop(row["owner_email"], None)
        consumed_path = os.path.join(self.data_dir, "consumed_tokens.txt")
        if os.path.exists(consumed_path):
            with open(consumed_path, encoding="utf-8") as fh:
                self.consumed = {ln.strip() for ln in fh if ln.strip()}

    def reload(self):
        """Re-read the data dir from disk. The lifecycle-job CLI runs as a
        separate process: it calls reload() under data_lock() before
        scanning, so a scan never works from a view the live daemon has
        already moved past."""
        self.rows = {}
        self.by_email = {}
        self.consumed = set()
        self._ip_hits = {}
        self._ip_hits_last_sweep = 0.0  # epoch of last bound sweep (#390)
        self._load()

    def _refresh_under_lock(self):
        """Re-read persistent rows/tokens under data_lock()+self._lock.

        The lifecycle-job CLI mutates rows.jsonl/consumed_tokens.txt in a
        separate process between daemon requests; without this, the
        check-then-act sections would run against a stale in-memory view
        (e.g. a job drops a row the daemon still thinks is pending, or a
        reminder minted a token the daemon's view doesn't know). Callers
        hold both locks already. _ip_hits is in-process abuse-rate state
        that has no on-disk representation — refreshing it would reset
        every request's rate window, so it is deliberately preserved."""
        ip_hits = self._ip_hits
        ip_hits_last_sweep = self._ip_hits_last_sweep
        self.rows = {}
        self.by_email = {}
        self.consumed = set()
        self._load()
        self._ip_hits = ip_hits
        self._ip_hits_last_sweep = ip_hits_last_sweep

    def _save_row(self, row):
        self._append("rows.jsonl", row)
        self.rows[row["entry_id"]] = row
        if row["status"] in ("pending", "confirmed"):
            self.by_email[row["owner_email"]] = row["entry_id"]
        else:
            self.by_email.pop(row["owner_email"], None)

    def _live_row_by_email(self, owner):
        """Find a live row for the normalized owner address, whatever its
        status — pending, confirmed, or invited. by_email only resolves
        pending/confirmed (the resubmission-relevant states), so invited
        rows need this explicit scan: forget replies must find them, and
        the submit paths must no-op on them, without resubmission ever
        treating an invited row as pending. Dropped/purged rows are not
        live — a re-submit after a drop starts a fresh row."""
        for row in self.rows.values():
            if (row.get("owner_email") == owner and
                    row.get("status") in ("pending", "confirmed",
                                          "invited")):
                return row
        return None

    def _claimed_row_by_email(self, owner):
        """Find a claimed (signed_up) row for the normalized owner
        address. signed_up is TERMINAL in the spec's state machine
        (WAITLIST_OPERATIONS.md §5: pending → confirmed → invited →
        signed_up — no transition back), so the submit paths must no-op
        on it exactly like they do on invited rows: a re-submit after a
        claim must not spawn a second pending row for the same address
        (which a later wave would invite again — a duplicate
        invite/claim cycle for one email, and double-counted funnel
        events). Kept separate from _live_row_by_email on purpose:
        the forget flow must NOT resolve claimed rows (the §5 forget
        link validates only for pending/confirmed/invited — extending
        that is a spec decision, not a code fix)."""
        for row in self.rows.values():
            if (row.get("owner_email") == owner and
                    row.get("status") == "signed_up"):
                return row
        return None

    def _emit(self, event, ref, attrs=None):
        self._append(
            "funnel_events.jsonl",
            {
                "event": event,
                "at": iso_z(self.clock()),
                "ref": ref,
                "attrs": attrs or {},
            },
        )

    def _consume_token(self, token):
        if token not in self.consumed:
            self.consumed.add(token)
            path = os.path.join(self.data_dir, "consumed_tokens.txt")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(token + "\n")

    # -- tokens -----------------------------------------------------------

    def mint_token(self, entry_id, normalized_email, issued_at=None,
                   kind="confirm"):
        """Mint an HMAC token. `kind` is "confirm" or "forget".

        Confirm tokens keep the exact pre-slice-3c wire format AND HMAC
        payload (`{entry_id}.{issued}.{nonce}` / payload including the
        owner email only), so confirm links issued before this slice keep
        validating. Forget tokens are kind-prefixed on the wire
        (`forget.{entry_id}.{issued}.{nonce}.{sig}`) with "forget" in the
        HMAC payload — the format difference alone makes cross-kind
        validation structurally impossible (a 4-part token never parses
        as 5-part and vice versa).
        """
        issued = int((issued_at or self.clock()).timestamp())
        nonce = secrets.token_urlsafe(6)  # distinct tokens per mint, even
        # within the same second — a re-submit's fresh token never equals
        # the consumed one
        if kind == "forget":
            payload = (f"forget.{entry_id}.{issued}.{nonce}."
                       f"{normalized_email}").encode()
            sig = b64url_encode(
                hmac.new(self.hmac_key, payload, hashlib.sha256).digest()
            )
            return f"forget.{entry_id}.{issued}.{nonce}.{sig}"
        payload = f"{entry_id}.{issued}.{nonce}.{normalized_email}".encode()
        sig = b64url_encode(
            hmac.new(self.hmac_key, payload, hashlib.sha256).digest()
        )
        return f"{entry_id}.{issued}.{nonce}.{sig}"

    def mint_forget_token(self, entry_id, normalized_email):
        return self.mint_token(entry_id, normalized_email, kind="forget")

    def _lookup_token_row(self, token, kind="confirm"):
        """Parse + HMAC-verify a token of the given kind and return its row.

        Returns (row, status) where status is one of:
          "ok"        — live, unexpired, unconsumed token for a live row
          "consumed"  — token was used or invalidated (single-use)
          "expired"   — issued more than the kind's TTL ago
          "invalid"   — malformed, wrong kind, bad HMAC, or unknown/gone row
        The caller maps these to the page states. TTL: 14d for confirm
        (WAITLIST_OPERATIONS.md §4), 7d for forget (§5 "honored ≤7d").
        The kind prefix makes cross-kind tokens unparseable: a confirm
        token (4 parts) can never be a forget token (5 parts, "forget"
        prefix) and vice versa.
        """
        try:
            if kind == "forget":
                tkind, entry_id, issued_s, nonce, sig = token.split(".", 4)
                if tkind != "forget":
                    return None, "invalid"
            else:
                entry_id, issued_s, nonce, sig = token.split(".", 3)
            issued = int(issued_s)
            b64url_decode(sig)  # structural check
        except (ValueError, AttributeError, TypeError):
            return None, "invalid"
        row = self.rows.get(entry_id)
        if row is None:
            return None, "invalid"
        # The forget link ships in every email footer (§5) — including
        # the invite email — so it must validate for invited rows.
        # Confirm tokens stay restricted to pending/confirmed.
        live = ("pending", "confirmed", "invited") if kind == "forget" \
            else ("pending", "confirmed")
        if row.get("status") not in live:
            return None, "invalid"
        if kind == "forget":
            payload = (f"forget.{entry_id}.{issued}.{nonce}."
                       f"{row['owner_email']}").encode()
        else:
            payload = (f"{entry_id}.{issued}.{nonce}."
                       f"{row['owner_email']}").encode()
        expected_sig = b64url_encode(
            hmac.new(self.hmac_key, payload, hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected_sig, sig):
            return None, "invalid"
        if token in self.consumed:
            return row, "consumed"
        ttl = FORGET_TTL_SECONDS if kind == "forget" else TOKEN_TTL_SECONDS
        if self.clock().timestamp() - issued > ttl:
            return row, "expired"
        return row, "ok"

    def validate_token(self, token):
        """Return (row, ok) — ok only for a live, unexpired, unconsumed
        token. Kept for callers that only need the boolean."""
        row, status = self._lookup_token_row(token)
        return (row, True) if status == "ok" else (None, False)

    # -- abuse guards -----------------------------------------------------

    def _ip_limited(self, ip):
        # Lock-free before the #390 sweep: _refresh_under_lock() and the
        # caller's data_lock+_lock sections all run AFTER this call, so
        # this is the only touchpoint. The sweep iterates the dict, and
        # ThreadingHTTPServer can insert a key concurrently (a flood of
        # distinct IPs — the exact attack #390 defends against) → CPython
        # raises "dictionary changed size during iteration" and the
        # submitter's connection dies. Serialize the whole body under the
        # thread lock: deadlock-safe (the single call site holds no lock,
        # never nested inside data_lock), and the sweep cost (~10k keys,
        # once per cooldown max) under the lock is negligible.
        with self._lock:
            now = time.time()
            if (len(self._ip_hits) > IP_HITS_MAX_KEYS
                    and now - self._ip_hits_last_sweep >= IP_HITS_SWEEP_COOLDOWN):
                # Bound the in-process abuse-rate state (#390): the dict keys
                # one entry per distinct client IP forever, so once over the
                # bound, re-prune every key's hits and drop keys with no
                # in-window activity. The cooldown rate-limits the sweep so a
                # flood of unique IPs cannot turn every request into an
                # O(dict) rebuild.
                self._ip_hits = {
                    k: [t for t in v if now - t < IP_RATE_WINDOW]
                    for k, v in self._ip_hits.items()
                }
                self._ip_hits = {k: v for k, v in self._ip_hits.items() if v}
                self._ip_hits_last_sweep = now
            hits = [t for t in self._ip_hits.get(ip, []) if now - t < IP_RATE_WINDOW]
            if len(hits) >= IP_RATE_LIMIT:
                self._ip_hits[ip] = hits
                return True
            hits.append(now)
            self._ip_hits[ip] = hits
            return False

    def _email_send_allowed(self, row):
        cutoff = self.clock().timestamp() - EMAIL_SEND_WINDOW
        recent = [t for t in row.get("email_sends", []) if t > cutoff]
        row["email_sends"] = recent
        return len(recent) < EMAIL_SEND_CAP

    def _unified_send_allowed(self, row):
        """The §4 3/24h cap as a union: BOTH the row's email_sends
        ledger and the path-A "email" ledger must allow the send.
        Every transactional send is checked against both and recorded
        in both, so confirm + reminder + invite + clarification +
        forget-request sends to one address count together, per the
        normative §4 text. (The path-A ledger sees every send; the row
        ledger sees only sends to an address with a live row.)"""
        return (self._email_send_allowed(row)
                and self._patha_send_allowed(row["owner_email"]))

    def _write_spool(self, name, doc):
        """Atomically write one spool doc — closes #389.

        Spool files are drained by the operator's sender as JSON; a torn
        partial file (crash/full disk mid-write) would leave a committed
        row claiming an email was queued alongside a half-written file
        the sender could choke on or send half of. Write to a unique tmp
        name in spool/ + flush + fsync + os.replace() (the same
        discipline as _rewrite_rows): a kill -9 mid-write leaves either
        the old file (never — spool names are unique per send) or the
        new one, never a torn one. The tmp is removed on failure so no
        partial file is ever left behind for the sender. OSError
        propagates — the caller's contract is unchanged: the invite path
        catches it and commits nothing; the other paths treat it as
        fatal.
        """
        path = os.path.join(self.spool_dir, name)
        tmp = f"{path}.tmp-{secrets.token_hex(4)}"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            # Never leave a partial tmp behind for the sender to choke on.
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _queue_confirm_email(self, row):
        """Spool the confirm email; the operator's sender drains the spool.
        Returns False when the unified 3/24h cap suppressed the send.

        The §4 cap is enforced as the UNION of the row's email_sends
        ledger and the path-A "email" ledger (see _unified_send_allowed):
        every send is checked against both and recorded in both, so
        confirm + reminder + invite + clarification + forget-request
        sends to one address count together, per the normative §4 text.
        """
        if not self._unified_send_allowed(row):
            return False
        token = self.mint_token(row["entry_id"], row["owner_email"])
        link = f"{self.public_host}/waitlist/confirm?token={token}"
        forget_link = (
            f"{self.public_host}/waitlist/forget?token="
            f"{self.mint_forget_token(row['entry_id'], row['owner_email'])}"
        )
        row["active_token"] = token  # the one live token for this row
        # Which email carried the live token — drives the `via` attr on
        # the `confirmed` event (FUNNEL_MEASUREMENT.md §3.4: original |
        # reminder). The reminder overwrites this when it sends.
        row["active_token_kind"] = "confirm"
        # The §4 DRAFT splits the confirm opener by submission path:
        # path-A rows get the "your agent asked" opener, path-B the form one.
        body_tpl = (CONFIRM_BODY_PATH_A if row.get("path") == "email"
                    else CONFIRM_BODY_PATH_B)
        doc = {
            "to": row["owner_email"],
            "subject": CONFIRM_SUBJECT,
            "body": body_tpl.format(
                confirm_link=link, forget_link=forget_link),
            "queued_at": iso_z(self.clock()),
            "entry_id": row["entry_id"],
        }
        name = (f"{row['entry_id']}-{int(self.clock().timestamp())}-"
                f"{secrets.token_hex(4)}.json")  # unique per send: two
        # sends in the same second for one row must not share a filename
        self._write_spool(name, doc)  # atomic — #389
        row["email_sends"] = row.get("email_sends", []) + [
            self.clock().timestamp()
        ]
        # Union half #2: the path-A ledger sees row-bound sends too, so a
        # later clarification/forget-request to this address counts them.
        self._record_patha_event(row["owner_email"], "email")
        self._save_row(row)
        self._emit("confirm_sent", row["entry_id"])
        return True

    def queue_position(self, entry_id):
        """1-based place in the invite queue, for the reminder's "#N in
        line" line (WAITLIST_OPERATIONS.md §4 draft, §7 order).

        §7 orders the queue FIFO by confirmed_at — confirmed entries are
        ahead of every pending entry (they will be invited first), and
        within each group the order is first-submitted-first. A pending
        entry's position is the place it holds the moment it confirms.
        entry_id breaks ties so the order is total and deterministic."""
        def rank_key(row):
            if row["status"] == "confirmed":
                return (0, row.get("confirmed_at") or "", row["entry_id"])
            return (1, row.get("submitted_at") or "", row["entry_id"])

        queued = [r for r in self.rows.values()
                  if r["status"] in ("pending", "confirmed")]
        queued.sort(key=rank_key)
        for i, row in enumerate(queued, 1):
            if row["entry_id"] == entry_id:
                return i
        return None

    def reminder_due(self, row):
        """True for a pending row that has reached the +7d reminder point
        and has never been reminded."""
        if row.get("status") != "pending" or row.get("reminder_sent_at"):
            return False
        try:
            drop_at = datetime.fromisoformat(
                row["drop_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError, AttributeError):
            return False
        now = self.clock()
        if now >= drop_at:
            # A row past its drop deadline is drop_expired()'s job, never
            # send_reminders()' — no reminder goes out after the row should
            # already have been dropped.
            return False
        return now >= drop_at - timedelta(
            seconds=REMINDER_LEAD_SECONDS)

    def drop_due(self, row):
        """True for a pending row whose 14-day drop deadline has passed."""
        if row.get("status") != "pending":
            return False
        try:
            drop_at = datetime.fromisoformat(
                row["drop_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError, AttributeError):
            return False
        return self.clock() >= drop_at

    def _queue_reminder_email(self, row):
        """Spool the +7d reminder per WAITLIST_OPERATIONS.md §4 DRAFT.

        Same link as the confirm email (fresh token only if the live token
        is within 7 days of expiry — at the +7d point a submit-minted token
        has exactly ~7 days left, so the normal case re-mints; a token
        re-minted by a late re-submit stays). Counts toward the unified
        §4 3/24h cap like every other transactional send (union of the
        row ledger and the path-A ledger — see _unified_send_allowed).
        Returns True when the email went out; False when the cap deferred it (the job retries on the
        next cron run — the old token stays live, nothing is marked)."""
        if not self._unified_send_allowed(row):
            return False
        old_token = row.get("active_token")
        use_token = None
        if old_token:
            try:
                issued = int(old_token.split(".", 3)[1])
                remaining = TOKEN_TTL_SECONDS - (
                    self.clock().timestamp() - issued)
                # "within 7 days of expiry" — the §4 draft's freshness rule.
                if remaining > REMINDER_LEAD_SECONDS:
                    use_token = old_token
            except (ValueError, IndexError):
                use_token = None
        if use_token is None:
            use_token = self.mint_token(row["entry_id"], row["owner_email"])
            row["active_token"] = use_token
        # Even when the reminder reuses the live confirm token, the human
        # clicked the REMINDER email — the `confirmed` event must say so.
        row["active_token_kind"] = "reminder"
        link = f"{self.public_host}/waitlist/confirm?token={use_token}"
        forget_link = (
            f"{self.public_host}/waitlist/forget?token="
            f"{self.mint_forget_token(row['entry_id'], row['owner_email'])}"
        )
        opener = REMINDER_OPENERS.get(row.get("source"), REMINDER_OPENERS["form"])
        position = self.queue_position(row["entry_id"])
        doc = {
            "to": row["owner_email"],
            "subject": REMINDER_SUBJECT,
            "kind": "reminder",
            "body": REMINDER_BODY.format(
                opener=opener,
                confirm_link=link,
                forget_link=forget_link,
                position=position if position is not None else "?",
            ),
            "queued_at": iso_z(self.clock()),
            "entry_id": row["entry_id"],
        }
        name = (f"{row['entry_id']}-{int(self.clock().timestamp())}-"
                f"{secrets.token_hex(4)}.json")
        self._write_spool(name, doc)  # atomic — #389
        row["email_sends"] = row.get("email_sends", []) + [
            self.clock().timestamp()
        ]
        # Union half #2 (see _unified_send_allowed).
        self._record_patha_event(row["owner_email"], "email")
        row["reminder_sent_at"] = iso_z(self.clock())
        self._save_row(row)
        if use_token != old_token and old_token:
            self._consume_token(old_token)
        self._emit("reminder_sent", row["entry_id"])
        return True

    def send_reminders(self):
        """+7d job: remind every due row. Returns the reminder count."""
        sent = 0
        for row in sorted(self.rows.values(),
                          key=lambda r: r.get("submitted_at") or ""):
            if self.reminder_due(row) and self._queue_reminder_email(row):
                sent += 1
        return sent

    def drop_expired(self):
        """14d job: drop every unconfirmed row past its deadline. Returns
        the dropped entry_ids. Status `dropped` is terminal
        (WAITLIST_OPERATIONS.md §5); the row is retained 30 days for the
        §5 retention rule, then purged by the --purge job
        (purge_dropped)."""
        dropped = []
        for row in sorted(self.rows.values(),
                          key=lambda r: r.get("submitted_at") or ""):
            if not self.drop_due(row):
                continue
            token = row.get("active_token")
            if token:
                self._consume_token(token)
                row["active_token"] = None
            row["status"] = "dropped"
            row["dropped_at"] = iso_z(self.clock())
            self._save_row(row)
            self._emit("dropped", row["entry_id"])
            dropped.append(row["entry_id"])
        return dropped

    def purge_due(self, row):
        """A dropped row is due for purge once PURGE_TTL_SECONDS have
        passed since it was dropped (WAITLIST_OPERATIONS.md §5: "row
        deleted 30d after drop").

        A dropped row with no dropped_at is NEVER purge-due: without a
        date we cannot prove the 30 days elapsed, and deleting early
        would break the retention promise. drop_expired always stamps
        dropped_at, so in practice this path only covers hand-edited
        stores — the operator deletes those by hand. A timezone-naive
        dropped_at is treated the same way (a hand edit we cannot anchor
        to the retention clock), NOT normalized to UTC: normalizing could
        delete up to 14h early against the §5 promise."""
        if row.get("status") != "dropped":
            return False
        dropped_at = row.get("dropped_at")
        if not dropped_at:
            return False
        try:
            dropped = datetime.fromisoformat(
                dropped_at.replace("Z", "+00:00"))
            return self.clock() >= dropped + timedelta(
                seconds=PURGE_TTL_SECONDS)
        except (ValueError, AttributeError, TypeError):
            # Garbled date (ValueError), non-string (AttributeError), or
            # naive datetime vs the aware clock (TypeError): none of these
            # prove the 30 days elapsed, so none is ever purge-due. The
            # TypeError case matters — an uncaught one would crash the
            # whole --purge run and every retry until hand-fixed.
            return False

    def _rewrite_rows(self):
        """Atomically rewrite rows.jsonl from the in-memory rows — the
        purge path (this is the rewrite slice 3a's docstring deferred for
        its own lock-discipline review; the --purge cron owns it now).

        Contract: the caller holds data_lock() across reload() + scan +
        rewrite, so no live daemon thread is mid-append (every daemon
        mutation takes the data lock too). The temp file lands in the
        data dir — same filesystem, so os.replace() is atomic: a kill -9
        mid-write leaves either the old rows.jsonl or the new one, never
        a torn one, and the loader's torn-line skip is the backstop.
        Rows are written sorted by entry_id with one line per entry
        (self.rows is already deduped — appends merge by entry_id on
        load), so operator diffs are deterministic. funnel_events.jsonl
        and consumed_tokens.txt are append-only and untouched — the
        `dropped`/`purged` events are the audit trail; the PII leaves
        with the row."""
        path = os.path.join(self.data_dir, "rows.jsonl")
        tmp = path + ".purge-tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for entry_id in sorted(self.rows):
                fh.write(
                    json.dumps(self.rows[entry_id], sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def purge_dropped(self):
        """30d job: permanently delete every purge-due dropped row.
        Returns the purged entry_ids. Emits a `purged` funnel event per
        row BEFORE the rewrite so the counts survive the deletion —
        emit-before is deliberate and at-least-once: a kill between the
        emit and the rewrite duplicates the event on retry, which is
        inert (no §7 metric counts purges; only the rows_read hygiene
        counter ticks).
        Idempotent: a second run finds nothing due."""
        due = [row for row in sorted(
            self.rows.values(), key=lambda r: r.get("submitted_at") or "")
            if self.purge_due(row)]
        for row in due:
            self._emit("purged", row["entry_id"])
            del self.rows[row["entry_id"]]
            if self.by_email.get(row.get("owner_email")) == row["entry_id"]:
                del self.by_email[row["owner_email"]]
        if due:
            self._rewrite_rows()
        return [row["entry_id"] for row in due]

    # -- the form ----------------------------------------------------------

    def submit_form(self, fields, client_ip):
        """Handle POST /waitlist/form.

        Returns (status, html). Honeypot/time-trap/rate-limit trips are
        silent accepts: 200 with the same rendering as a real success
        (HOSTED_SIGNUP_WEB_UI.md §4.2 — the spam learns nothing), nothing
        written. The §4.2 silence mandate covers honeypot trips; time-trap
        and IP-rate-limit trips share the same rendering as a service-local
        anti-abuse choice.
        """
        honeypot = (fields.get("website") or "").strip()
        rendered_at = (fields.get("rendered_at") or "").strip()
        owner_raw = (fields.get("owner_email") or "").strip()
        silent = False
        if honeypot:
            silent = True
        elif rendered_at:
            # The static form stamps nothing (no serving layer under Pages),
            # so a missing stamp is the form's legitimate state and proceeds.
            # A present-but-unparseable stamp, or a stamp showing a sub-3s
            # fill, is bot-shaped.
            try:
                if time.time() - float(rendered_at) < TIME_TRAP_MIN_SECONDS:
                    silent = True
            except (TypeError, ValueError):
                silent = True
        if silent or self._ip_limited(client_ip):
            return 200, page_check_inbox(owner_raw)

        owner = normalize_email(owner_raw)
        if owner is None:
            return 400, page_invalid_email()
        muse_raw = (fields.get("muse_email") or "").strip()
        muse_contact = normalize_email(muse_raw) if muse_raw else None

        # The dedup check and everything downstream of it are check-then-act
        # — serialize them so a racing double-submit can't create two rows
        # for one address. The thread lock covers the daemon's own threads;
        # the data lock covers the lifecycle-job process too (lock order:
        # data lock outside, thread lock inside).
        with data_lock(self.data_dir), self._lock:
            # The lifecycle-job CLI mutates rows on disk between daemon
            # requests — refresh the persistent view before the check,
            # or dedup could act on rows a job already dropped/confirmed.
            self._refresh_under_lock()
            existing_id = self.by_email.get(owner)
            if existing_id:
                return self._resubmit(self.rows[existing_id], owner_raw,
                                      muse_contact)
            live = self._live_row_by_email(owner)
            if live is not None and live.get("status") == "invited":
                # Already invited: no new row, no email, nothing
                # refreshed — the claim email already went out. Say so
                # honestly instead of "check your inbox" for a confirm
                # link that would be dead on arrival.
                return 200, page_already_invited(owner_raw)
            if self._claimed_row_by_email(owner) is not None:
                # Already claimed: signed_up is terminal — a re-submit
                # must not spawn a second pending row (a later wave
                # would invite the duplicate and double-count the
                # funnel). No new row, no email, nothing refreshed.
                return 200, page_already_claimed(owner_raw)
            return self._create_row(owner, owner_raw, muse_contact)

    def _resubmit_core(self, row, muse_contact):
        """Pending re-submit core, shared by both intake paths (form and
        email). Refresh, re-send a fresh token (counts toward the 3/24h
        cap). The old token dies only when the replacement email actually
        goes out — a cap-suppressed re-send must never strand the user
        with zero live tokens.

        Returns one of "confirmed" | "resubmitted" | "confirm_capped";
        the caller renders that outcome for its own channel.
        """
        if row["status"] == "confirmed":
            # Idempotent: already on the list. No new event, no email.
            return "confirmed"
        row["submitted_at"] = iso_z(self.clock())
        if muse_contact:
            row["muse_contact"] = muse_contact
        old_token = row.get("active_token")
        self._save_row(row)
        if self._queue_confirm_email(row):
            if old_token:
                self._consume_token(old_token)
            return "resubmitted"
        # Capped: the earlier link still works — the caller says so
        # honestly instead of claiming an email was sent.
        return "confirm_capped"

    def _resubmit(self, row, owner_raw, muse_contact):
        """Form-path pending re-submit: _resubmit_core, rendered as the
        form's pages."""
        outcome = self._resubmit_core(row, muse_contact)
        return 200, {
            "confirmed": page_confirmed(),
            "resubmitted": page_check_inbox(owner_raw),
            "confirm_capped": page_already_sent(owner_raw),
        }[outcome]

    def _create_row(self, owner, owner_raw, muse_contact, *, path="form",
                    inbound_auth=None, pubkey=None, usecase=None):
        entry_id = secrets.token_urlsafe(12)
        submitted = self.clock()
        row = {
            "entry_id": entry_id,
            "owner_email": owner,
            "muse_contact": muse_contact,
            "path": path,
            "source": path,
            "submitted_at": iso_z(submitted),
            # The drop deadline is fixed at first submission and NEVER
            # refreshed by re-submits (drop-date semantics: a re-submit
            # refreshes submitted_at, the confirm link, and the token —
            # not the 14-day drop clock).
            "drop_at": iso_z(submitted + timedelta(
                seconds=DROP_TTL_SECONDS)),
            "reminder_sent_at": None,
            "confirmed_at": None,
            "status": "pending",
            "email_sends": [],
            "active_token": None,
        }
        if path == "email":
            # The §5 data model: inbound_auth records the SPF/DKIM/DMARC
            # result for path A (it gates the clarification reply); the
            # §3.4 funnel event carries path + inbound_auth for email rows.
            row["inbound_auth"] = bool(inbound_auth)
        if pubkey:
            row["muse_pubkey"] = pubkey  # pre-registration hint only (§2)
        if usecase:
            row["use_case"] = usecase  # ≤280 chars, verbatim (§2)
        self._save_row(row)
        attrs = {"path": path}
        if path == "email":
            attrs["inbound_auth"] = bool(inbound_auth)
        self._emit("waitlist_submitted", entry_id, attrs)
        self._queue_confirm_email(row)  # first send is always under the cap
        return 200, page_check_inbox(owner_raw)


    # -- path-A email intake -------------------------------------------------

    def _record_patha_event(self, address, kind):
        """Append a path-A ledger event and prune entries older than 48h.

        The ledger (patha_events.jsonl, operator data dir) carries two
        event kinds, both keyed by address:
          "submission" — one email intake attempt (the §6 per-sender
            3/day limit counts these);
          "email"      — one path-A transactional send TO that address
            (clarification / forget-request replies — the §4 3/24h cap
            counts these, alongside the row-bound sends the cap targets).
        Appends are single-line O_APPEND writes; pruning rewrites under
        the caller's data lock.
        """
        now = self.clock().timestamp()
        self._append("patha_events.jsonl",
                     {"address": address, "kind": kind,
                      "at": iso_z(self.clock())})
        cutoff = now - 2 * 86400
        path = os.path.join(self.data_dir, "patha_events.jsonl")
        kept = []
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                        ts = datetime.fromisoformat(
                            obj["at"].replace("Z", "+00:00")).timestamp()
                    except (KeyError, ValueError, TypeError):
                        continue  # garbled ledger line: drop on prune
                    if ts > cutoff:
                        kept.append(line)
        except OSError:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(kept)

    def _count_patha_events(self, address, kind, window):
        cutoff = self.clock().timestamp() - window
        path = os.path.join(self.data_dir, "patha_events.jsonl")
        count = 0
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    if obj.get("address") != address or \
                            obj.get("kind") != kind:
                        continue
                    try:
                        ts = datetime.fromisoformat(
                            obj["at"].replace("Z", "+00:00")).timestamp()
                    except (KeyError, ValueError, TypeError):
                        continue
                    if ts > cutoff:
                        count += 1
        except OSError:
            return 0
        return count

    def patha_intake_limited(self, sender):
        """True when the sender already submitted PATHA_INTAKE_LIMIT times
        in PATHA_INTAKE_WINDOW (§6 — 3 submissions / sender / day)."""
        return (self._count_patha_events(sender, "submission",
                                         PATHA_INTAKE_WINDOW)
                >= PATHA_INTAKE_LIMIT)

    def _patha_send_allowed(self, recipient):
        """The §4 3/24h transactional-email cap, path-A-ledger half of the
        union (see _unified_send_allowed). Row-bound sends consult this
        ledger too, and path-A sends consult the row ledger when the
        recipient owns a live row — all reply types counted together,
        per the normative §4 text."""
        return (self._count_patha_events(recipient, "email",
                                         EMAIL_SEND_WINDOW)
                < EMAIL_SEND_CAP)

    def triage_inbound(self, raw, reason):
        """Silent triage for unauthenticated or otherwise unprocessable
        inbound mail (§2/§6 — no *reply* to an unauthenticated sender,
        ever, so the parser can never become a backscatter reflector).
        The raw message plus the loop-generated reason land in the
        operator data dir's triage/ subdir for the operator to eyeball.
        Returns the triage filename.

        "No reply" is about replies to the sender (the clarification
        path). The signup confirm email and the §5 forget-confirmation
        email are owner-bound double-opt-in / proof-of-inbox challenges,
        not replies — explicitly spec'd in §2/§4/§5, and bounded by the
        unified §4 3/24h per-address cap. Accepts bytes or str; bytes
        are decoded lossily so undecodable input can never crash the
        write with surrogate escapes.
        """
        triage_dir = os.path.join(self.data_dir, "triage")
        os.makedirs(triage_dir, exist_ok=True)
        name = (f"{int(self.clock().timestamp())}-"
                f"{secrets.token_hex(4)}.eml")
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        elif isinstance(raw, str):
            text = raw
        else:
            text = ""
        # Never let a lone surrogate (PEP 383 from a str-stdin read, or
        # any other caller) crash the write: sanitize to U+FFFD first.
        text = text.encode("utf-8", errors="replace").decode("utf-8")
        with open(os.path.join(triage_dir, name), "w",
                  encoding="utf-8") as fh:
            fh.write(f"X-Waitlist-Triage-Reason: {reason}\n\n")
            fh.write(text)
        return name

    def _spool_patha_email(self, to, subject, body, kind, entry_id=None):
        """Spool a path-A transactional email (clarification reply or
        forget-request confirmation) to the sender's address. The §4
        3/24h cap is enforced as the UNION of the path-A ledger and the
        row's email_sends ledger (see _unified_send_allowed): the send is
        checked against both and recorded in both, so path-A replies
        count together with confirms/reminders/invites to the same
        address. Returns True when the email went out, False when the
        cap suppressed it."""
        if not self._patha_send_allowed(to):
            return False
        # Union half #1: when the recipient owns a live row, the row's
        # ledger must allow the send too — otherwise 3 clarifications +
        # 3 confirms could reach one address inside 24h.
        row = self._live_row_by_email(to)
        if row is not None and not self._email_send_allowed(row):
            return False
        doc = {
            "to": to,
            "subject": subject,
            "kind": kind,
            "body": body,
            "queued_at": iso_z(self.clock()),
            "entry_id": entry_id,
        }
        name = (f"patha-{int(self.clock().timestamp())}-"
                f"{secrets.token_hex(4)}.json")
        self._write_spool(name, doc)  # atomic — #389
        self._record_patha_event(to, "email")
        if row is not None:
            # Union half #2: the row ledger sees path-A sends too.
            row["email_sends"] = row.get("email_sends", []) + [
                self.clock().timestamp()
            ]
            self._save_row(row)
        return True

    def spool_clarification(self, sender):
        """Spool the §2 clarification reply ("we couldn't tell which
        address is the owner"). The caller guarantees the inbound message
        passed DMARC alignment — never call this for unauthenticated
        mail (silent triage instead).

        Takes the data + thread locks: the ledger read (cap check) and
        the append+prune rewrite must be atomic against racing
        invocations, and this method's only caller holds no lock."""
        with data_lock(self.data_dir), self._lock:
            return self._spool_patha_email(sender, CLARIFY_SUBJECT,
                                           CLARIFY_BODY, "clarification")

    def handle_forget_reply(self, sender):
        """A reply saying "forget me" (WAITLIST_OPERATIONS.md §5).

        Never deletes directly: Reply From is forgeable, so honoring it
        would be a deletion oracle. Only when the sender's normalized
        address matches a live row's owner email, spool the confirmation
        email containing the signed forget link — the row is deleted only
        after that link is clicked (proving inbox access), within 7 days,
        with a confirmation sent (the existing /waitlist/forget POST).

        Returns (outcome, row-or-None). Outcomes:
          "forget_request_sent"   — confirmation email spooled
          "forget_request_capped" — the 3/24h cap suppressed the resend
          "no_row"                — sender owns no row; caller triages

        Forget tokens are intentionally NOT rotated on re-mint (unlike
        confirm tokens): every issued forget link — including the footer
        links in confirm/reminder/invite emails — must keep validating
        until used or expired, because forget_get renders a consumed
        token as "already deleted" and the §5 footer contract promises
        any received email's link works. Residual is low: tokens are
        single-use, bound to the owner's inbox, and row deletion kills
        them all (forget_post consumes the used token; the row lookup
        fails for the rest).
        """
        with data_lock(self.data_dir), self._lock:
            self._refresh_under_lock()
            # The explicit live-row scan (not by_email): invited owners
            # must find their row here — by_email deliberately excludes
            # invited rows so resubmission never treats them as pending.
            row = self._live_row_by_email(sender)
            if row is None:
                return "no_row", None
            token = self.mint_forget_token(row["entry_id"],
                                               row["owner_email"])
            forget_link = f"{self.public_host}/waitlist/forget?token={token}"
            sent = self._spool_patha_email(
                sender, FORGET_REQUEST_SUBJECT,
                FORGET_REQUEST_BODY.format(owner_email=row["owner_email"],
                                           forget_link=forget_link),
                "forget_request", row["entry_id"])
            return ("forget_request_sent" if sent
                    else "forget_request_capped"), row

    def submit_email(self, *, owner, sender, inbound_auth, pubkey=None,
                     usecase=None):
        """Path-A intake for one validated email submission
        (WAITLIST_OPERATIONS.md §2), the email half of H15's intake.

        Carries the email path's defenses instead of the form's: no
        honeypot/time-trap/IP-limit (there is no page). The per-sender
        intake limit (§6) is enforced HERE, inside the lock, before
        dedup — the limit belongs to the sender, and dedup may resolve
        to a different row, so checking after dedup would let a fleet
        rotate owners past the cap; checking outside the lock would let
        a racing second invocation slip past before the first records.

        Returns (outcome, row) where outcome is one of:
          "created"        — new row; confirm email queued (path-A opener)
          "resubmitted"    — existing pending row refreshed + fresh
                             confirm email
          "confirmed"      — row already confirmed; idempotent, no email
          "confirm_capped" — accepted but the 3/24h cap suppressed the
                             re-send; the earlier link still works.
          "already_invited" — the owner was already invited off the
                             waitlist; no new row, no email, nothing
                             refreshed. The submission ledger event is
                             still recorded (the §6 budget counts
                             attempts).
          "already_claimed"  — the owner already claimed the invite
                             (signed_up is terminal — WAITLIST_OPERATIONS
                             §5); no new row, no email, nothing refreshed.
                             The submission ledger event is still recorded.
          "intake_limited" — per-sender 3/day tripped; nothing written
                             except the triage the caller performs.

        The check-then-act section (dedup on submit) is serialized under
        the data lock + thread lock, like every other mutating path.
        """
        with data_lock(self.data_dir), self._lock:
            self._refresh_under_lock()
            if self.patha_intake_limited(sender):
                return "intake_limited", None
            self._record_patha_event(sender, "submission")
            existing_id = self.by_email.get(owner)
            if existing_id:
                outcome = self._resubmit_core(self.rows[existing_id],
                                              sender)
                return outcome, self.rows[existing_id]
            live = self._live_row_by_email(owner)
            if live is not None and live.get("status") == "invited":
                # The owner already holds a claim email — re-submitting
                # must not duplicate the row, refresh anything, or queue
                # a confirm email whose link would be dead on arrival.
                return "already_invited", live
            claimed = self._claimed_row_by_email(owner)
            if claimed is not None:
                # signed_up is terminal (see submit_form): no new row,
                # no email, nothing refreshed — the duplicate would be
                # invited again by a later wave.
                return "already_claimed", claimed
            _, _page = self._create_row(
                owner, owner, sender, path="email",
                inbound_auth=inbound_auth, pubkey=pubkey, usecase=usecase)
            return "created", self.rows[self.by_email[owner]]

    # -- confirm -----------------------------------------------------------

    def confirm_get(self, token):
        """GET /waitlist/confirm — renders only. Never changes state.

        A consumed token whose row is confirmed renders the
        already-confirmed state (WAITLIST_OPERATIONS.md §4: a re-click is
        never an error); a token invalidated by a re-submit renders the
        expired state — that link genuinely no longer works.

        Read-only, but rendered under the data lock with a fresh view:
        a job (or racing POST) may have consumed/re-minted the token or
        dropped the row since the daemon's view was loaded, and this page
        is what the user actually judges the link by.
        """
        with data_lock(self.data_dir), self._lock:
            self._refresh_under_lock()
            row, status = self._lookup_token_row(token or "")
        if status == "invalid":
            return 200, page_expired()
        if row["status"] == "confirmed":
            return 200, page_confirmed()
        if status != "ok":
            return 200, page_expired()
        return 200, page_pending_button(token, masked_owner(row["owner_email"]))

    def confirm_post(self, token):
        """POST /waitlist/confirm — token as form field. Confirms.

        The lookup-then-consume is check-then-act — serialized so two
        racing POSTs of one fresh token can't double-emit `confirmed`.
        (Thread lock inside the data lock — same order as submit_form.)"""
        with data_lock(self.data_dir), self._lock:
            # Same staleness concern as submit_form: a job may have
            # consumed this token (reminder re-mint) or dropped the row
            # since the daemon's view was loaded.
            self._refresh_under_lock()
            row, status = self._lookup_token_row(token or "")
            if status == "invalid":
                return 200, page_expired()
            if row["status"] == "confirmed":
                # Idempotent re-POST: same rendering as a fresh confirmation,
                # verbatim — never an error (WAITLIST_OPERATIONS.md §4).
                return 200, page_confirmed()
            if status != "ok":
                return 200, page_expired()
            row["status"] = "confirmed"
            row["confirmed_at"] = iso_z(self.clock())
            self._save_row(row)
            self._consume_token(token)  # single-use: this token can never confirm again
            via = ("reminder" if row.get("active_token_kind") == "reminder"
                   else "original")
            self._emit("confirmed", row["entry_id"], {"via": via})
            # POST-success renders exactly like already-confirmed, verbatim.
            return 200, page_confirmed()

    # -- forget ----------------------------------------------------------

    def forget_get(self, token):
        """GET /waitlist/forget — renders only. Never changes state.

        A fresh token renders the delete-confirmation page (the token
        travels as a form field to the POST — the §4.3 GET-never-changes-
        state rule holds here too). A consumed token renders the
        already-deleted page (the consumed set is checked before the row
        lookup: the row is gone by the time the token is consumed, so a
        row-first lookup would misreport it as merely invalid); an
        expired token, or a token for a gone row, renders the expired
        page. Read-only, but rendered under the data lock with a fresh
        view for the same reasons as confirm_get.
        """
        with data_lock(self.data_dir), self._lock:
            self._refresh_under_lock()
            if token and token.startswith("forget.") and token in self.consumed:
                return 200, page_already_deleted()
            row, status = self._lookup_token_row(token or "", kind="forget")
        if status == "invalid":
            return 200, page_forget_expired()
        if status == "consumed":
            return 200, page_already_deleted()
        if status != "ok":
            return 200, page_forget_expired()
        return 200, page_forget_button(
            token, masked_owner(row["owner_email"]))

    def forget_post(self, token):
        """POST /waitlist/forget — token as form field. Deletes the row.

        Per WAITLIST_OPERATIONS.md §5 the row is deleted only after the
        signed link is clicked (proving inbox access), within 7 days,
        with a confirmation sent. The row leaves rows.jsonl via an atomic
        rewrite (the purge path's _rewrite_rows); the PII is gone and the
        `forgot` funnel event (FUNNEL_MEASUREMENT.md §3.4) keeps the
        counts. The deletion confirmation email is spooled unconditionally —
        the forget token is single-use and consumed before the spool, so
        one row can produce at most one deletion notice (no mail-cannon
        shape for the 3/24h cap to defend).

        The lookup-then-delete is check-then-act — serialized under the
        data lock + thread lock, like every other mutating path.
        """
        with data_lock(self.data_dir), self._lock:
            self._refresh_under_lock()
            if token and token.startswith("forget.") and token in self.consumed:
                # The token already ran once — the row is gone (deletion
                # is single-use by construction). Say so honestly.
                return 200, page_already_deleted()
            row, status = self._lookup_token_row(token or "", kind="forget")
            if status == "invalid":
                return 200, page_forget_expired()
            if status == "consumed":
                # Unreachable in practice (the fast path above catches
                # every consumed forget token), kept as a belt-and-braces
                # rendering if the consumed set ever diverges.
                return 200, page_already_deleted()
            if status != "ok":
                return 200, page_forget_expired()
            entry_id = row["entry_id"]
            owner = row["owner_email"]
            live_token = row.get("active_token")
            # Kill the confirm token too — the row is gone, so its entry_id
            # lookup would fail anyway, but mark it consumed explicitly.
            if live_token:
                self._consume_token(live_token)
            # Same for a live invite token (invited rows can be
            # forget-deleted now that the forget link validates for
            # them) — a deleted row's claim link must die with it.
            live_invite = row.get("active_invite_token")
            if live_invite:
                self._consume_token(live_invite)
            self._consume_token(token)
            del self.rows[entry_id]
            if self.by_email.get(owner) == entry_id:
                del self.by_email[owner]
            self._rewrite_rows()
            self._emit("forgot", entry_id)
            self._queue_deleted_email(owner, entry_id)
            return 200, page_deleted()

    def _queue_deleted_email(self, owner_email, entry_id):
        """Spool the deletion confirmation. No 3/24h cap ledger: the forget
        token is single-use and consumed before this runs, so one row can
        produce at most one deletion email — there is no mail-cannon shape
        for the cap to defend (WAITLIST_OPERATIONS.md §6's cap targets the
        re-sendable confirm/reminder/clarification loop)."""
        doc = {
            "to": owner_email,
            "subject": FORGET_SUBJECT,
            "kind": "deleted",
            "body": FORGET_CONFIRM_BODY.format(owner_email=owner_email),
            "queued_at": iso_z(self.clock()),
            "entry_id": entry_id,
        }
        name = (f"{entry_id}-deleted-{int(self.clock().timestamp())}-"
                f"{secrets.token_hex(4)}.json")
        self._write_spool(name, doc)  # atomic — #389
        return True


    # -- invites -----------------------------------------------------------

    def mint_invite_token(self, entry_id, normalized_email):
        """Mint an invite token: HMAC-signed, single-use, 14-day expiry
        (WAITLIST_OPERATIONS.md §7). Wire format `invite.{entry_id}.
        {issued}.{nonce}.{sig}` with "invite" in the HMAC payload — the
        `invite.` prefix makes cross-kind validation structurally
        impossible (a confirm/forget token never parses as invite and
        vice versa), mirroring the confirm/forget domain separation."""
        issued = int(self.clock().timestamp())
        nonce = secrets.token_urlsafe(6)
        payload = (f"invite.{entry_id}.{issued}.{nonce}."
                   f"{normalized_email}").encode()
        sig = b64url_encode(
            hmac.new(self.hmac_key, payload, hashlib.sha256).digest())
        return f"invite.{entry_id}.{issued}.{nonce}.{sig}"

    def lookup_invite_token(self, token):
        """Parse + HMAC-verify an invite token and return its row.

        Returns (row, status) where status is one of:
          "ok"       — live, unexpired invite on a live invited row
          "consumed" — used, superseded, or otherwise retired
          "expired"  — issued at least INVITE_TTL_SECONDS (14d) ago
          "invalid"  — malformed, wrong kind, bad HMAC, or the row is
                       not in `invited` status
        """
        try:
            tkind, entry_id, issued_s, nonce, sig = token.split(".", 4)
            if tkind != "invite":
                return None, "invalid"
            issued = int(issued_s)
            b64url_decode(sig)  # structural check
        except Exception:
            return None, "invalid"
        row = self.rows.get(entry_id)
        if row is None:
            return None, "invalid"
        payload = (f"invite.{entry_id}.{issued}.{nonce}."
                   f"{row['owner_email']}").encode()
        expected_sig = b64url_encode(
            hmac.new(self.hmac_key, payload, hashlib.sha256).digest())
        if not hmac.compare_digest(expected_sig, sig):
            return None, "invalid"
        if token in self.consumed or token != row.get("active_invite_token"):
            # Consumed, or superseded by a newer wave's token — either
            # way this token no longer claims anything. Checked before
            # the status gate so a retired token stays "consumed" after
            # the row rolls back to confirmed.
            return None, "consumed"
        if row.get("status") != "invited":
            return None, "invalid"
        if self.clock().timestamp() - issued >= INVITE_TTL_SECONDS:
            # Boundary matches rollover_expired_invites (expired when
            # expiry <= now): at exactly 14d the token is expired and
            # the row rolls — never "ok" in one and expired in the other.
            return row, "expired"
        return row, "ok"

    # -- claim ------------------------------------------------------------

    def _claimed_row_for_retired_token(self, entry_id):
        """Row for a retired (consumed/superseded) invite token.

        The caller must pass the entry_id of a token whose HMAC has
        already been verified — in practice, a token that
        lookup_invite_token returned ("consumed") for. The wire-format
        entry_id is inside the HMAC payload, so it cannot be swapped
        without invalidating the signature; the value is used only for
        a store lookup plus a status check, never for authorization.
        """
        return self.rows.get(entry_id)

    def claim_get(self, token):
        """GET /waitlist/claim — renders only. Never changes state.

        The invite email's claim link is fetched by mail scanners and
        unfurlers before the human clicks (the §4.3 scanner threat model
        applies verbatim to claim links). A live invite renders the
        claim screen; an already-claimed row (consumed token, status
        signed_up) renders the claimed page idempotently — never an
        error; a dead link (expired, superseded, invalid, or a rolled-back
        row) renders the inactive page. Read under the data lock with a
        fresh view: a wave, the rollover cron, or a racing POST may have
        retired this token since the daemon's view was loaded.
        """
        with data_lock(self.data_dir), self._lock:
            self._refresh_under_lock()
            row, status = self.lookup_invite_token(token or "")
            if status == "invalid" or status == "expired":
                return 200, page_claim_inactive()
            if status == "consumed":
                # The HMAC verified (a forged token lands on "invalid"),
                # so the wire-format entry_id is trustworthy for lookup.
                retired = self._claimed_row_for_retired_token(
                    token.split(".", 4)[1])
                if (retired is not None
                        and retired.get("status") == "signed_up"):
                    # Idempotent re-click after the single-use token ran:
                    # the claim is recorded — say so, never an error.
                    return 200, page_claimed(
                        masked_owner(retired["owner_email"]))
                return 200, page_claim_inactive()
            return 200, page_claim_button(
                token, masked_owner(row["owner_email"]))

    def claim_post(self, token):
        """POST /waitlist/claim — invite token as form field. Records the
        claim (waitlist-era scope: marks the row signed_up, emits the
        `claimed` funnel event with ref = the waitlist row id; tenant-shell
        provisioning belongs to the signup-era surface —
        WAITLIST_OPERATIONS.md §8).

        The lookup-then-consume is check-then-act — serialized so two
        racing POSTs of one fresh token can't double-emit `claimed`.
        (Thread lock inside the data lock — same order as confirm_post.)
        """
        with data_lock(self.data_dir), self._lock:
            # Same staleness concern as confirm_post: a wave, the rollover
            # cron, or a racing POST may have retired this token since the
            # daemon's view was loaded.
            self._refresh_under_lock()
            row, status = self.lookup_invite_token(token or "")
            if status == "invalid" or status == "expired":
                return 200, page_claim_inactive()
            if status == "consumed":
                # The HMAC verified (a forged token lands on "invalid"),
                # so the wire-format entry_id is trustworthy for lookup.
                retired = self._claimed_row_for_retired_token(
                    token.split(".", 4)[1])
                if (retired is not None
                        and retired.get("status") == "signed_up"):
                    # Idempotent re-POST: same rendering as a fresh claim,
                    # verbatim — never an error, never a second event.
                    return 200, page_claimed(
                        masked_owner(retired["owner_email"]))
                return 200, page_claim_inactive()
            row["status"] = "signed_up"
            row["signed_up_at"] = iso_z(self.clock())
            self._save_row(row)
            self._consume_token(token)  # single-use: this token can never claim again
            self._emit("claimed", row["entry_id"])
            # POST-success renders exactly like already-claimed, verbatim.
            return 200, page_claimed(masked_owner(row["owner_email"]))

    def _queue_invite_email(self, row, position, pricing_lines, trial_terms,
                            wave, now):
        """Spool the §7 invite email: pricing + trial terms filled at send
        time from the decided pricing (the template never contains
        pricing numbers), the invitee's signed position line ("You held
        #N in line"), and the claim link. Counts toward the unified §4
        3/24h cap like every other transactional send. Returns True when
        the email went out; False when the cap suppressed it or the
        spool write failed — the row is then untouched (still confirmed,
        no token consumed), so the next wave retries it cleanly.

        Spool-then-single-commit: once the spool write succeeds, every
        ROW mutation happens in memory first (new token recorded, send
        ledgers, the invited mark) and commits with ONE _save_row
        append — no intermediate on-disk row state. The old-token
        consume and path-A ledger event are idempotent file appends
        that land before the commit; their extra state is benign on
        retry (re-consume is a no-op, the ledger counts delivered
        emails). Failure modes, in order:
        - spool write fails or the §4 cap suppresses → nothing committed;
          the row stays confirmed and the next wave retries it cleanly
          (same as before).
        - crash after the spool write but before the single commit → the
          row stays confirmed on disk with one stray email in the spool.
          The retry mints a FRESH token; the stray email's claim link
          never validates (its token was never recorded as the row's
          active token), so the failure mode is "duplicate email on
          retry" — never "invited row with no email" (m2 reorder).
        - crash after the commit → perfect: invited row, email spooled.
        The `invite_sent` funnel event follows the commit, not the
        spool: a crash in that last window leaves an invited row the
        operator can re-derive from rows.jsonl (status=invited) rather
        than an event claiming an invite that never committed — the
        metrics read conservatively and never claim what rows.jsonl
        doesn't show."""
        if not self._unified_send_allowed(row):
            return False
        token = self.mint_invite_token(row["entry_id"], row["owner_email"])
        old = row.get("active_invite_token")
        claim_link = f"{self.public_host}/waitlist/claim?token={token}"
        forget_link = (
            f"{self.public_host}/waitlist/forget?token="
            f"{self.mint_forget_token(row['entry_id'], row['owner_email'])}"
        )
        doc = {
            "to": row["owner_email"],
            "subject": INVITE_SUBJECT,
            "kind": "invite",
            "body": INVITE_BODY.format(
                claim_link=claim_link,
                pricing_lines=pricing_lines,
                trial_terms=trial_terms,
                position=position if position is not None else "?",
                forget_link=forget_link,
            ),
            "queued_at": iso_z(self.clock()),
            "entry_id": row["entry_id"],
        }
        name = (f"{row['entry_id']}-invite-{int(self.clock().timestamp())}-"
                f"{secrets.token_hex(4)}.json")
        try:
            self._write_spool(name, doc)  # atomic — #389
        except OSError:
            # Spool failed: commit nothing. The old token (if any) stays
            # live, the minted token is never referenced, and the row is
            # still confirmed — the next wave retries it cleanly.
            return False
        if old:
            self._consume_token(old)
        row["active_invite_token"] = token
        row["email_sends"] = row.get("email_sends", []) + [
            self.clock().timestamp()
        ]
        # Union half #2 (see _unified_send_allowed).
        self._record_patha_event(row["owner_email"], "email")
        # The invited mark lands in the SAME commit as the token record:
        # one _save_row append, no intermediate on-disk row state.
        row["status"] = "invited"
        row["invited_at"] = iso_z(now)
        row["invite_expires_at"] = iso_z(
            now + timedelta(seconds=INVITE_TTL_SECONDS))
        row["invite_wave"] = wave
        self._save_row(row)
        self._emit("invite_sent", row["entry_id"])
        return True

    def send_invite_wave(self, *, pricing_lines, trial_terms, wave, count):
        """Operator-driven invite wave (WAITLIST_OPERATIONS.md §7).

        Invites up to `count` confirmed rows, FIFO by confirmed_at,
        scanning past cap-suppressed rows so a capped head-of-line
        row never eats a wave slot. The §7 invite email goes out with
        the pricing/trial terms filled at send time, and each mailed row
        commits with ONE rows.jsonl append AFTER the spool write succeeds
        — token record + invited mark (status, invited_at,
        invite_expires_at = now + 14d, invite_wave = wave) land together,
        so no crash window can strand a row as invited-without-email.
        The residual crash window (spool written, commit not yet) fails
        as "duplicate email on retry": the retry mints a fresh token and
        the stray email's claim link never validates. Emits `invite_sent`
        (FUNNEL_MEASUREMENT.md §3.4) per mailed row, after the commit.

        Rows past the 3/24h email cap are NOT invited this wave — they
        stay confirmed for a later wave (their slot is not consumed).
        A spool-write failure likewise leaves the row confirmed and
        unconsumed; the wave continues and the CLI's invited count
        shows fewer than requested — re-running the wave retries those
        rows cleanly. Returns the invited entry_ids in wave order.

        Caller must hold data_lock (the operator CLI does) — like the
        lifecycle jobs' send_reminders/drop_unconfirmed, this method
        mutates the store and spools without taking the lock itself.
        A large wave holds that lock for the whole run (N spool writes);
        the documented wave sizes (tens of rows) keep this fine.
        """
        now = self.clock()
        eligible = [r for r in self.rows.values()
                    if r.get("status") == "confirmed"]
        # §7 order: waitlist order, FIFO by confirmed_at.
        eligible.sort(key=lambda r: (r.get("confirmed_at") or "",
                                     r["entry_id"]))
        # Position is the invitee's confirmed-queue rank. eligible is
        # already in the FIFO order queue_position uses for confirmed
        # rows, so the enumerate index + 1 IS the rank — snapshot it
        # BEFORE the loop. (queue_position() called inside the loop
        # would shrink as earlier rows flip to invited, since invited
        # rows are not ranked — every later invite would read "#1".)
        rank = {r["entry_id"]: i + 1 for i, r in enumerate(eligible)}
        invited = []
        for row in eligible:
            if len(invited) >= count:
                break
            position = rank[row["entry_id"]]
            # The cap check, the spool write, and the invited commit all
            # happen inside _queue_invite_email in spool-then-single-commit
            # order: a capped row — or a row whose spool write failed —
            # stays confirmed and keeps its slot for the next wave. (The
            # old mark-then-unmark dance is gone: nothing is marked before
            # the email exists, and nothing is committed twice.)
            if not self._queue_invite_email(row, position, pricing_lines,
                                            trial_terms, wave, now):
                continue
            invited.append(row["entry_id"])
        return invited

    def rollover_expired_invites(self):
        """§7 expiry rollover: an unclaimed invite expires 14 days after
        the wave. The slot rolls to the next confirmed entry (the next
        wave invites it) and the expired entry rejoins `confirmed` at the
        back of the queue — confirmed_at is reset to the EXPIRY time
        (§5), not to now, and no re-confirmation is needed (the address
        is already verified). The invite token is consumed. Emits no
        funnel event (the §3.4 taxonomy has none for this; the metrics
        queries are constrained to the taxonomy).

        Returns the rolled entry_ids. Idempotent.

        Caller must hold data_lock (the operator CLI does) — same
        convention as send_invite_wave.
        """
        rolled = []
        for row in self.rows.values():
            if row.get("status") != "invited":
                continue
            try:
                expiry = datetime.fromisoformat(
                    row["invite_expires_at"].replace("Z", "+00:00"))
            except (KeyError, ValueError, TypeError, AttributeError):
                continue  # undated invite: the operator handles it by hand
            if expiry > self.clock():
                continue
            token = row.get("active_invite_token")
            if token:
                self._consume_token(token)
            row["status"] = "confirmed"
            row["confirmed_at"] = iso_z(expiry)  # §5: back of the queue
            for key in ("invited_at", "invite_expires_at",
                        "invite_wave", "active_invite_token"):
                row.pop(key, None)
            self._save_row(row)
            rolled.append(row["entry_id"])
        return rolled

    def _invite_token_state(self, row):
        """Token state for an invited row: one of "ok" (live), "expired",
        "consumed", "invalid", or "missing" (no invite token recorded —
        hand-damaged or pre-feature row). Same lookup semantics as
        lookup_invite_token, except a cross-wired token (one whose
        embedded entry_id resolves to a DIFFERENT row — a hand-damaged
        row carrying another entry's token) reads "invalid", never that
        other entry's state: force-repairing this row must never retire
        someone else's live claim link."""
        token = row.get("active_invite_token")
        if not token:
            return "missing"
        found, status = self.lookup_invite_token(token)
        if found is not None and found.get("entry_id") != row.get("entry_id"):
            return "invalid"
        return status

    def reinstate_confirmed(self, entry_ids, *, reason, force=False,
                            dry_run=False):
        """Issue #235: flip stranded invited rows back to confirmed, in
        the append-only posture — the repair the fault-injection tests
        perform by hand (test_reinvite_crash_between_consume_and_commit
        calls it "manual today").

        Stranded states this repairs:
        - the `_consume_token(old)` -> row-commit crash window: the old
          token's consume landed on disk but the row commit did not, so
          the on-disk row is still invited with a consumed token;
        - an operator-initiated re-wave (invite email bounced/lost,
          operator error): the row is invited but the invite should die
          and the entry rejoin the confirmed queue.

        For each entry_id, exactly one new rows.jsonl revision is
        appended: status flips to confirmed, the four invite keys are
        popped (same convention as rollover_expired_invites — the prior
        invited revisions and the `invite_sent` funnel event keep the
        full audit trail), confirmed_at is KEPT (this is a crash repair,
        not an expiry: the entry rejoins at its original queue position;
        expiry still goes to the back via --rollover), and the revision
        records `reinstate_at` + `reinstate_reason`. No funnel event —
        the §3.4 taxonomy has none for this (same as rollover).

        Gates, all fail-loud before ANY row is mutated (validate, then
        commit — no partial application):
        - every entry_id must exist and have status == "invited";
        - duplicate entry_ids are collapsed (one revision per row);
        - `reason` must be non-empty (it is the audit trail);
        - an EXPIRED invite is refused outright: reinstating would keep
          the original queue position and silently skip the disclosed
          14-day expiry → back-of-queue rule — run --rollover instead
          (not foldable into --force: force means "retire a live claim
          link explicitly", and no legitimate expired-reinstate exists);
        - a row whose invite token is still LIVE ("ok") is refused
          unless force=True: reinstating kills the claim link, so the
          operator must say so explicitly. With force, the live token is
          consumed at reinstate time so the trail reads "consumed", not
          "invalid".

        The next wave re-invites the reinstated row with a FRESH token
        (re-consume of the old token is a no-op; `_queue_invite_email`
        mints anew). Note the crashed wave's stray email counted against
        the §4 3/24h cap when it went out — if the cap is still full the
        re-wave leaves the row confirmed for a later wave.

        Returns the reinstated entry_ids (or, with dry_run=True, the
        per-entry plan with no mutation). Caller must hold data_lock
        (the operator CLI does) — same convention as send_invite_wave
        and rollover_expired_invites.
        """
        if not reason or not str(reason).strip():
            raise ValueError(
                "reinstate_confirmed: reason is required — it is recorded "
                "on the row as the audit trail")
        entry_ids = list(dict.fromkeys(entry_ids))  # E1: one revision/row
        plans = []
        for entry_id in entry_ids:
            row = self.rows.get(entry_id)
            if row is None:
                raise ValueError(
                    f"reinstate_confirmed: no such entry {entry_id!r}")
            if row.get("status") != "invited":
                raise ValueError(
                    f"reinstate_confirmed: entry {entry_id!r} has status "
                    f"{row.get('status')!r}, not 'invited' — nothing to "
                    "reinstate")
            token_state = self._invite_token_state(row)
            if token_state == "expired":
                raise ValueError(
                    f"reinstate_confirmed: entry {entry_id!r}'s invite "
                    "has EXPIRED — reinstating would keep its original "
                    "queue position and silently skip the disclosed "
                    "14-day expiry -> back-of-queue rule; run --rollover "
                    "instead")
            if token_state == "ok" and not force:
                raise ValueError(
                    f"reinstate_confirmed: entry {entry_id!r}'s invite "
                    "token is still LIVE — reinstating would kill the "
                    "claim link; re-run with --force to retire it "
                    "explicitly")
            plans.append((row, row.get("active_invite_token"), token_state))
        if dry_run:
            return [{"entry_id": row["entry_id"],
                     "token_state": token_state,
                     "would": ("consume the live invite token, then flip "
                               "to confirmed (forced)" if token_state == "ok"
                               else "flip to confirmed, keeping "
                               "confirmed_at (original queue position)")}
                    for row, _, token_state in plans]
        reinstated = []
        for row, token, token_state in plans:
            consumed_live = False
            if token_state == "ok" and force:
                self._consume_token(token)
                consumed_live = True
            row["status"] = "confirmed"
            for key in ("invited_at", "invite_expires_at",
                        "invite_wave", "active_invite_token"):
                row.pop(key, None)
            row["reinstate_at"] = iso_z(self.clock())
            row["reinstate_reason"] = reason
            if consumed_live:
                row["reinstate_consumed_live_token"] = True
            self._save_row(row)
            reinstated.append(row["entry_id"])
        return reinstated

    def diagnose_invites(self):
        """Issue #235 item 3: read-only diagnosis of every invited row's
        token state, so the operator can tell which stranded state each
        row is in without grepping rows.jsonl by hand.

        Buckets:
        - "ok"       — live invite, healthy; nothing to do.
        - "expired"  — past the 14d TTL; run --rollover (idempotent).
        - "consumed" — crash-suspect: the token died but the row never
                       rolled back; --reinstate-confirmed candidate.
        - "invalid"/"missing" — hand-damaged row; inspect by hand
                       before any repair (an explicit --reinstate-confirmed
                       --reason ... is the inspection + decision).
        Returns a list of dicts (entry_id, masked owner, token_state,
        recommendation). No mutation; no lock needed beyond the caller's
        read consistency.
        """
        recommendations = {
            "ok": "healthy — nothing to do",
            "expired": "expired — run --rollover",
            "consumed": ("crash-suspect — reinstate candidate "
                         "(--reinstate-confirmed --reason ...)"),
            "invalid": "hand-damaged — inspect rows.jsonl by hand",
            "missing": ("hand-damaged — no invite token recorded; "
                        "inspect rows.jsonl by hand"),
        }
        out = []
        for row in self.rows.values():
            if row.get("status") != "invited":
                continue
            state = self._invite_token_state(row)
            out.append({
                "entry_id": row["entry_id"],
                "owner": masked_owner(row["owner_email"]),
                "token_state": state,
                "recommendation": recommendations[state],
            })
        return out

    def _terminate_partial_tail(self, path):
        """Quarantine a kill -9-torn tail before appending.

        A kill -9 mid-append leaves a partial line with no trailing
        newline at EOF; appending directly after it would glue the next
        event onto the torn bytes, producing one physical line no
        line-oriented reader can parse (and a second reconcile pass
        would then re-emit, since the glued line never counts as
        covering). If the file doesn't end with a newline, terminate
        the partial line first so the next append starts on its own
        parseable line. The torn line itself stays unparseable and is
        skipped loudly, never trusted as covering.
        """
        with open(path, "ab+") as fh:  # "ab+" creates if missing
            fh.seek(0, os.SEEK_END)
            if fh.tell():
                fh.seek(-1, os.SEEK_END)
                if fh.read(1) != b"\n":
                    fh.seek(0, os.SEEK_END)
                    fh.write(b"\n")

    def reconcile_invite_events(self, dry_run=False):
        """Issue #234: re-derive `invite_sent` events lost to the
        commit -> emit crash window, in the append-only posture.

        `_queue_invite_email` spools the email, then commits the invited
        row, then emits `invite_sent` — a crash in that last window
        leaves an invited row whose invite email went out but whose
        funnel event never fired (the funnel reads conservatively, so
        invite_sent/claim ratios under-report until repaired). Rows are
        the source of truth here: hand-editing funnel_events.jsonl is
        off-posture, so this pass re-derives the missing events from
        rows.jsonl instead of rewriting history.

        For every row that is (a) status == "invited", (b) carrying a
        LIVE invite token (lookup validates "ok" — not consumed, not
        expired), and (c) has no invite_sent event with at >= its
        invited_at, it appends one `invite_sent` (ref = entry_id) with
        attrs marking the reconciliation:

            {"reconciled": True, "via": "reconcile_invite_events",
             "wave": <invite_wave>, "reason": "commit-crash window: the
             invited-row commit landed but the emit did not; the invite
             email is spooled and the claim token is live"}

        Guard notes, each deliberate:
        - A row whose invite already rolled back to confirmed is skipped:
          its (dead) invite can't convert, and the next wave's fresh
          invite carries its own event. Backfilling for a dead invite
          would claim what the funnel can never see claimed — the same
          conservatism that skips the emit in the first place. Recovery
          of such rows is operator tooling (issue #235), not this pass.
        - A row whose token was consumed (superseded by a reinvite) is
          skipped: either its current invite already emitted (check (c)
          with the fresh invited_at), or it rolled back (previous rule).
        - Check (c) compares at >= invited_at rather than mere event
          presence: a re-invited row legitimately has an older
          invite_sent for a previous invite; only the current invite's
          event counts. invited_at is reset on every invite, and
          funnel_metrics counts the last emission per ref — a reconciled
          event appended after the real one is read as the same
          emission, never a double-count.
        - Torn funnel_events lines (kill -9 can tear the last append)
          are skipped loudly like _load does; they never count as
          covering, so a torn emit line is re-derived, not trusted.
          Before each append the torn tail is terminated
          (_terminate_partial_tail) so the re-derived event starts on
          its own parseable line instead of gluing onto the torn
          partial — without this, one physical line would be
          unparseable and a second pass would re-emit.
        - Idempotent and crash-safe: check-then-append with no other
          mutation; re-running (or dying mid-pass) emits each missing
          event exactly once. Deterministic order (entry_id).

        Returns the entry_ids whose events were re-derived (or would
        be, under dry_run).

        Caller must hold data_lock (the operator CLI does) — same
        convention as send_invite_wave. No WAITLIST_CLAIM_LIVE gate:
        this pass sends nothing; it repairs funnel events for emails
        the wave already sent.
        """
        covered = set()  # (ref, at) pairs of invite_sent events
        events_path = os.path.join(self.data_dir, "funnel_events.jsonl")
        if os.path.exists(events_path):
            with open(events_path, encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        sys.stderr.write(
                            "waitlistd: reconcile skipping torn "
                            f"funnel_events.jsonl line {lineno}\n")
                        continue
                    if (isinstance(obj, dict) and
                            obj.get("event") == "invite_sent"):
                        covered.add((obj.get("ref"), obj.get("at")))
        reconciled = []
        for entry_id in sorted(self.rows):
            row = self.rows[entry_id]
            if row.get("status") != "invited":
                continue
            token = row.get("active_invite_token")
            if not token:
                continue
            _, status = self.lookup_invite_token(token)
            if status != "ok":
                # Consumed/superseded or expired — the current invite is
                # not live, so there is no event this pass may claim.
                continue
            invited_at = row.get("invited_at") or ""
            if any(ref == entry_id and (at or "") >= invited_at
                   for ref, at in covered):
                continue
            if not dry_run:
                # Quarantine a kill -9-torn tail FIRST: without this,
                # the append below would glue the re-derived event onto
                # the torn partial line, producing one unparseable
                # physical line (and a second pass would re-emit, since
                # the glued line never counts as covering).
                self._terminate_partial_tail(events_path)
                self._emit("invite_sent", entry_id, {
                    "reconciled": True,
                    "via": "reconcile_invite_events",
                    "wave": row.get("invite_wave"),
                    "reason": ("commit-crash window: the invited-row "
                               "commit landed but the invite_sent emit "
                               "did not; the invite email is spooled "
                               "and the claim token is live"),
                })
                covered.add((entry_id, row.get("invited_at")))
            reconciled.append(entry_id)
        return reconciled

    # -- self-host CTA -----------------------------------------------------

    def cta_selfhost(self, src):
        """Log the self-host CTA click and return the redirect target.

        Emits a `cta_click` funnel event (docs/FUNNEL_MEASUREMENT.md §3.4)
        with the src attr when it is one of the canonical CTA section
        sources — otherwise the event ships without a src attr. The
        daemon never emits an unknown src value, so a typoed ?src= can
        never silently open a new rollup bucket. CTA_SRCS mirrors
        KNOWN_SRCS in scripts/funnel_metrics.py — keep the two in sync."""
        attrs = {"src": src} if src in CTA_SRCS else {}
        self._emit("cta_click", "selfhost", attrs)
        return SELFHOST_URL


# ---------------------------------------------------------------------------
# Pages (no page JS anywhere; all user content html-escaped)
# ---------------------------------------------------------------------------

PAGE_SHELL = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{title} — spark-vm waitlist</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:40rem;margin:0 auto;padding:2rem 1.25rem;color:#1a1a1a;line-height:1.6}}
.card{{border:1px solid #ddd;border-radius:12px;padding:1.75rem}}
.muted{{color:#666}}
button{{font:inherit;padding:.7rem 1.4rem;border-radius:8px;border:1px solid #1a1a1a;background:#1a1a1a;color:#fff;cursor:pointer}}
</style>
</head>
<body>
<main class="card">
{body}
</main>
</body>
</html>
"""


def page_already_sent(owner_raw):
    """Honest rendering for a cap-suppressed re-send: the earlier confirm
    link still works — never claim an email went out when it didn't."""
    addr = html.escape(owner_raw.strip(), quote=True)
    return PAGE_SHELL.format(
        title="Check your inbox",
        body=(
            "<h1>Check your inbox</h1>"
            "<p>You\u2019re one click away from the spark-vm hosted waitlist.</p>"
            f"<p>We already sent a confirmation email to <strong>{addr}</strong> "
            "— your earlier link still works. New emails are limited to keep "
            "inboxes quiet, so give it a little time, then check spam.</p>"
            '<p class="muted">Wrong address? <a href="/waitlist">Go back</a> '
            "and re-enter it.</p>"
            "<p class=\"muted\">Unconfirmed addresses are dropped automatically "
            "after 14 days.</p>"
        ),
    )


def page_already_invited(owner_raw):
    """Honest rendering for a re-submit on an already-invited address:
    no new row, no new email — the claim email already went out."""
    addr = html.escape(owner_raw.strip(), quote=True)
    return PAGE_SHELL.format(
        title="Already invited",
        body=(
            "<h1>Already invited</h1>"
            f"<p><strong>{addr}</strong> has already been invited off the "
            "waitlist — the claim email went to that address.</p>"
            "<p>Check your inbox (and spam) for the invite.</p>"
            '<p class="muted">Lost the email? The invite expires 14 days '
            "after it was sent — after that the slot rolls to the next "
            "entry and you rejoin the line at the back, and you&#x2019;ll "
            "be invited again in a later wave, when one runs. Re-entering "
            "the address here won&#x2019;t speed that up.</p>"
        ),
    )


def page_already_claimed(owner_raw):
    """Honest rendering for a re-submit on an already-claimed address:
    no new row, no new email — the invite was already claimed
    (signed_up is terminal; re-entering the address must never open a
    second invite/claim cycle for it)."""
    addr = html.escape(owner_raw.strip(), quote=True)
    return PAGE_SHELL.format(
        title="Already claimed",
        body=(
            "<h1>Already claimed</h1>"
            f"<p><strong>{addr}</strong> already claimed its invite — "
            "the claim is recorded and there&#x2019;s nothing else to do.</p>"
            '<p class="muted">Re-entering the address here won&#x2019;t '
            "create a new spot — each address claims exactly once.</p>"
        ),
    )


def page_check_inbox(owner_raw):
    if owner_raw:
        addr = html.escape(owner_raw.strip(), quote=True)
        echo = (
            f"<p>We sent a confirmation email to <strong>{addr}</strong>.</p>"
            '<p class="muted">Wrong address? <a href="/waitlist">Go back</a> '
            "and re-enter it.</p>"
        )
    else:
        echo = ""
    return PAGE_SHELL.format(
        title="Check your inbox",
        body=(
            "<h1>Check your inbox</h1>"
            "<p>You\u2019re one click away from the spark-vm hosted waitlist.</p>"
            + echo
            + "<p class=\"muted\">Unconfirmed addresses are dropped automatically "
            "after 14 days.</p>"
        ),
    )


def page_invalid_email():
    return PAGE_SHELL.format(
        title="That address doesn\u2019t look right",
        body=(
            "<h1>That address doesn\u2019t look right</h1>"
            "<p>Check the email address and try again.</p>"
            '<p><a href="/waitlist">Back to the waitlist page</a></p>'
        ),
    )


def page_pending_button(token, masked):
    tok = html.escape(token, quote=True)
    who = html.escape(masked, quote=True)
    return PAGE_SHELL.format(
        title="Confirm your spot",
        body=(
            # Headline + button verbatim from docs/FUNNEL_MEASUREMENT.md §4.2:
            # "Confirm your spot — you're joining as `<masked>`", one button
            # "Yes, hold my place."
            "<h1>Confirm your spot — you\u2019re joining as "
            f"<strong>{who}</strong></h1>"
            "<p>" + html.escape(COPY_PENDING_LINE) + "</p>"
            '<form action="/waitlist/confirm" method="post">'
            f'<input type="hidden" name="token" value="{tok}">'
            '<button type="submit">Yes, hold my place.</button>'
            "</form>"
            "<p class=\"muted\">No card is required for the waitlist, and this "
            "confirmation doesn\u2019t commit you to anything.</p>"
        ),
    )


def page_confirmed():
    # The one rendering for "confirmed": POST-success and already-confirmed
    # are verbatim identical (docs/FUNNEL_MEASUREMENT.md §4.3).
    return PAGE_SHELL.format(
        title="You\u2019re on the list",
        body=(
            "<h1>You\u2019re on the list</h1>"
            "<p>" + html.escape(COPY_CONFIRMED) + "</p>"
        ),
    )


def page_expired():
    return PAGE_SHELL.format(
        title="Link expired",
        body=(
            "<h1>Link expired</h1>"
            "<p>" + html.escape(COPY_EXPIRED) + "</p>"
            '<p><a href="/waitlist">' + html.escape(COPY_REJOIN) + "</a></p>"
        ),
    )


def page_forget_button(token, masked):
    tok = html.escape(token, quote=True)
    who = html.escape(masked, quote=True)
    return PAGE_SHELL.format(
        title="Delete your waitlist entry",
        body=(
            # One button, plain form POST — deletion needs no JavaScript,
            # and the §4.3 GET-never-changes-state rule holds: this page
            # only renders.
            "<h1>Delete your waitlist entry</h1>"
            f"<p>This permanently deletes the waitlist entry for "
            f"<strong>{who}</strong> — all of its data is gone, and "
            "rejoining starts you at the back of the line. This can't be "
            "undone.</p>"
            '<form action="/waitlist/forget" method="post">'
            f'<input type="hidden" name="token" value="{tok}">'
            '<button type="submit">Yes, delete my entry.</button>'
            "</form>"
            '<p class="muted">Changed your mind? Just close this page — '
            "nothing happens until you click the button.</p>"
        ),
    )


def page_forget_expired():
    # §5: the forget link is honored ≤7d. A token past that, or a token for
    # a row that no longer exists, lands here — never an error dump.
    return PAGE_SHELL.format(
        title="Link expired",
        body=(
            "<h1>Link expired</h1>"
            "<p>This deletion link is invalid or expired — deletion links "
            "last 7 days, and a fresh one arrives with every waitlist "
            "email.</p>"
        ),
    )


def page_deleted():
    return PAGE_SHELL.format(
        title="Deleted",
        body=(
            "<h1>Deleted</h1>"
            "<p>Your waitlist entry is gone — all of its data has been "
            "deleted. We sent a confirmation email as well.</p>"
        ),
    )


def page_already_deleted():
    # Idempotent re-click after the single-use token ran: the entry is
    # already gone — say so honestly, verbatim with page_deleted's body
    # minus the email line.
    return PAGE_SHELL.format(
        title="Deleted",
        body=(
            "<h1>Deleted</h1>"
            "<p>Your waitlist entry is gone — it was already deleted.</p>"
        ),
    )


def page_claim_button(token, masked):
    tok = html.escape(token, quote=True)
    who = html.escape(masked, quote=True)
    return PAGE_SHELL.format(
        title="Claim your box",
        body=(
            # One button, plain form POST — claiming needs no JavaScript,
            # and the §4.3 GET-never-changes-state rule holds for claim
            # links too: this page only renders. The what-happens-next
            # lines are COPY_CLAIM_NEXT verbatim, so the claim screen never
            # diverges from the invite email.
            "<h1>You\u2019re off the waitlist \u2014 claim your box</h1>"
            f"<p>You\u2019re claiming as <strong>{who}</strong>.</p>"
            "<p>" + html.escape(COPY_CLAIM_NEXT) + "</p>"
            '<form action="/waitlist/claim" method="post">'
            f'<input type="hidden" name="token" value="{tok}">'
            '<button type="submit">Claim my box</button>'
            "</form>"
            '<p class="muted">' + html.escape(COPY_CLAIM_EXPIRY) + "</p>"
        ),
    )


def page_claimed(masked):
    # The one rendering for "claimed": POST-success and already-claimed
    # are verbatim identical (the confirm/forget idempotency contract,
    # applied to claim).
    who = html.escape(masked, quote=True)
    return PAGE_SHELL.format(
        title="Claim recorded",
        body=(
            "<h1>Claim recorded</h1>"
            f"<p>Your invite is claimed for <strong>{who}</strong>. "
            + html.escape(COPY_CLAIM_NEXT)
            + "</p>"
        ),
    )


def page_claim_inactive():
    # A token past its 14d life, superseded by a newer wave, structurally
    # invalid, or retired by the rollover cron — never an error dump.
    return PAGE_SHELL.format(
        title="Invite no longer live",
        body=(
            "<h1>This invite link is no longer live</h1>"
            "<p>" + html.escape(COPY_CLAIM_INACTIVE) + "</p>"
            '<p><a href="/waitlist">' + html.escape(COPY_REJOIN) + "</a></p>"
        ),
    )


# ---------------------------------------------------------------------------
# HTTP wiring
# ---------------------------------------------------------------------------

# Largest form body we'll parse; the form has three short fields.
MAX_BODY_BYTES = 65536

_OVERSIZED = object()  # _fields sentinel: body over MAX_BODY_BYTES


class _Handler(BaseHTTPRequestHandler):
    service = None  # set by serve()
    server_version = "waitlistd/1"

    def _send(self, status, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        # FUNNEL_MEASUREMENT.md §4.2: the confirm page is fetched by scanners
        # and unfurlers — strip preview metadata and the referrer at the
        # HTTP layer (the meta robots tag alone does not reach them).
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.end_headers()
        self.wfile.write(data)

    def _fields(self):
        """Parse the form body. Returns the fields dict, None for a
        malformed body, or the _OVERSIZED sentinel when the body exceeds
        MAX_BODY_BYTES (never buffer unbounded input)."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            return None
        if length < 0:
            return None
        if length > MAX_BODY_BYTES:
            return _OVERSIZED
        raw = self.rfile.read(length) if length > 0 else b""
        parsed = urllib.parse.parse_qs(
            raw.decode("utf-8", "replace"), keep_blank_values=True
        )
        return {k: v[0] for k, v in parsed.items() if v}

    def _bad_request(self, status, title):
        self._send(status, PAGE_SHELL.format(
            title=title, body=f"<h1>{title}</h1>"))

    def _redirect(self, url):
        """302 with no body. Referrer stripped — the self-host CTA must not
        leak the waitlist path's query into the README."""
        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Content-Length", "0")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.end_headers()

    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        fields = self._fields() if path in (
            "/waitlist/form", "/waitlist/confirm", "/waitlist/forget",
            "/waitlist/claim") else {}
        if fields is _OVERSIZED:
            # Engineering deferred blocker (PR #165): on keep-alive
            # connections the unread remainder of an oversized body would
            # desync the next request — close instead of persisting.
            self.close_connection = True
            self._bad_request(413, "Request too large")
            return
        if fields is None:
            self._bad_request(400, "Bad request")
            return
        if path == "/waitlist/form":
            status, body = self.service.submit_form(
                fields, self.client_address[0]
            )
            self._send(status, body)
        elif path == "/waitlist/confirm":
            status, body = self.service.confirm_post(
                fields.get("token")
            )
            self._send(status, body)
        elif path == "/waitlist/forget":
            status, body = self.service.forget_post(
                fields.get("token")
            )
            self._send(status, body)
        elif path == "/waitlist/claim":
            status, body = self.service.claim_post(
                fields.get("token")
            )
            self._send(status, body)
        else:
            self._send(404, PAGE_SHELL.format(
                title="Not found",
                body="<h1>Not found</h1>",
            ))

    def do_GET(self):  # noqa: N802
        parts = urllib.parse.urlsplit(self.path)
        if parts.path == "/waitlist/confirm":
            token = urllib.parse.parse_qs(parts.query).get("token", [None])[0]
            status, body = self.service.confirm_get(token)
            self._send(status, body)
        elif parts.path == "/waitlist/forget":
            token = urllib.parse.parse_qs(parts.query).get("token", [None])[0]
            status, body = self.service.forget_get(token)
            self._send(status, body)
        elif parts.path == "/waitlist/claim":
            token = urllib.parse.parse_qs(parts.query).get("token", [None])[0]
            status, body = self.service.claim_get(token)
            self._send(status, body)
        elif parts.path == "/go/selfhost":
            src = urllib.parse.parse_qs(parts.query).get("src", [None])[0]
            self._redirect(self.service.cta_selfhost(src))
        else:
            self._send(404, PAGE_SHELL.format(
                title="Not found",
                body="<h1>Not found</h1>",
            ))

    def log_message(self, fmt, *args):  # keep logs free of request content
        sys.stderr.write("waitlistd: %s\n" % (self.address_string(),))


def load_config(argv):
    if "--help" in argv or "-h" in argv:
        sys.stdout.write(__doc__ + "\n")
        raise SystemExit(0)
    key_raw = os.environ.get("WAITLIST_HMAC_KEY")
    if not key_raw:
        sys.stderr.write(
            "waitlistd: WAITLIST_HMAC_KEY is not set — refusing to start "
            "without an operator HMAC key.\n"
        )
        raise SystemExit(2)
    try:
        key = bytes.fromhex(key_raw)
    except ValueError:
        key = key_raw.encode("utf-8")
    if len(key) < 16:
        sys.stderr.write(
            "waitlistd: WAITLIST_HMAC_KEY is too short (need >= 16 bytes).\n"
        )
        raise SystemExit(2)
    data_dir = os.environ.get("WAITLIST_DATA")
    if not data_dir:
        sys.stderr.write(
            "waitlistd: WAITLIST_DATA is not set — refusing to start "
            "without an operator-owned data dir.\n"
        )
        raise SystemExit(2)
    if not os.path.isdir(data_dir) or not os.access(data_dir, os.W_OK):
        sys.stderr.write(
            f"waitlistd: WAITLIST_DATA={data_dir!r} is not a writable "
            "directory.\n"
        )
        raise SystemExit(2)
    host = os.environ.get("WAITLIST_PUBLIC_HOST",
                           "https://waitlist.example.invalid")
    bind = os.environ.get("WAITLIST_BIND", "127.0.0.1")
    try:
        port = int(os.environ.get("WAITLIST_PORT", "8765"))
    except (TypeError, ValueError):
        sys.stderr.write(
            "waitlistd: WAITLIST_PORT is not an integer.\n")
        raise SystemExit(2)
    return key, data_dir, host, bind, port


def main(argv):
    key, data_dir, host, bind, port = load_config(argv)
    if "--check" in argv:
        sys.stdout.write("waitlistd: config ok\n")
        return 0
    service = WaitlistService(data_dir, key, host)
    _Handler.service = service
    httpd = ThreadingHTTPServer((bind, port), _Handler)
    sys.stderr.write(f"waitlistd: listening on {bind}:{port}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
