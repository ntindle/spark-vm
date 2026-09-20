#!/usr/bin/env python3
"""waitlistd — the waitlist-era control-plane service (H15 build, slice 2).

Implements the waitlist-era half of docs/HOSTED_SIGNUP_WEB_UI.md §7's
endpoint surface:

    POST /waitlist/form      path-B form intake (§4.2)
    GET  /waitlist/confirm   renders only — never changes state (§4.3)
    POST /waitlist/confirm   token as form field, not query string (§4.3)

Deliberately NOT in this slice (H15 PR 1 remainder → slice 3): the +7d
reminder / 14d drop jobs, the path-A email parser, the invite sender, the
forget-me handler, and the /go/selfhost redirect shim. Per
docs/WAITLIST_OPERATIONS.md §10 + site/README.md, the page is still NOT
deployable — the dead-form rule holds until every §10 item is live.

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
- The confirm-email body is the WAITLIST_OPERATIONS.md §4 DRAFT for
  path B (the form path; path A lands with the email parser).
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
  `dropped` (no attrs, 14d job). `scripts/funnel_metrics.py` (PR #141)
  is the consumer; the emitted JSONL must stay parseable by it.
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
    REMINDER_LEAD_SECONDS = 7*86400 — the +7d reminder fires when
        now >= drop_at - REMINDER_LEAD_SECONDS.
    DROP_TTL_SECONDS = 14*86400 — drop_at is set once at row creation
        (= submitted_at + DROP_TTL_SECONDS) and is NEVER refreshed by a
        re-submit: WAITLIST_OPERATIONS.md §4 drops "unconfirmed 14 days
        after submission", and a re-submit must not postpone the drop.

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
EMAIL_SEND_CAP = 3
EMAIL_SEND_WINDOW = 86400
TOKEN_TTL_SECONDS = 14 * 86400
REMINDER_LEAD_SECONDS = 7 * 86400
DROP_TTL_SECONDS = 14 * 86400

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
CONFIRM_SUBJECT = "Confirm your spark-vm waitlist spot"
REMINDER_SUBJECT = "Reminder: your spark-vm waitlist spot is waiting on one click"

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
"""


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
        self.rows = {}
        self.by_email = {}
        self.consumed = set()
        self._load()
        self._ip_hits = ip_hits

    def _save_row(self, row):
        self._append("rows.jsonl", row)
        self.rows[row["entry_id"]] = row
        if row["status"] in ("pending", "confirmed"):
            self.by_email[row["owner_email"]] = row["entry_id"]
        else:
            self.by_email.pop(row["owner_email"], None)

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

    def mint_token(self, entry_id, normalized_email, issued_at=None):
        issued = int((issued_at or self.clock()).timestamp())
        nonce = secrets.token_urlsafe(6)  # distinct tokens per mint, even
        # within the same second — a re-submit's fresh token never equals
        # the consumed one
        payload = f"{entry_id}.{issued}.{nonce}.{normalized_email}".encode()
        sig = b64url_encode(
            hmac.new(self.hmac_key, payload, hashlib.sha256).digest()
        )
        return f"{entry_id}.{issued}.{nonce}.{sig}"

    def _lookup_token_row(self, token):
        """Parse + HMAC-verify a token and return its row.

        Returns (row, status) where status is one of:
          "ok"        — live, unexpired, unconsumed token for a live row
          "consumed"  — token was used or invalidated (single-use)
          "expired"   — issued more than TOKEN_TTL_SECONDS ago
          "invalid"   — malformed, bad HMAC, or unknown/gone row
        The caller maps these to the §4.3 page states.
        """
        try:
            entry_id, issued_s, nonce, sig = token.split(".", 3)
            issued = int(issued_s)
            b64url_decode(sig)  # structural check
        except (ValueError, Exception):
            return None, "invalid"
        row = self.rows.get(entry_id)
        if row is None or row.get("status") not in ("pending", "confirmed"):
            return None, "invalid"
        payload = (f"{entry_id}.{issued}.{nonce}."
                   f"{row['owner_email']}").encode()
        expected_sig = b64url_encode(
            hmac.new(self.hmac_key, payload, hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected_sig, sig):
            return None, "invalid"
        if token in self.consumed:
            return row, "consumed"
        if self.clock().timestamp() - issued > TOKEN_TTL_SECONDS:
            return row, "expired"
        return row, "ok"

    def validate_token(self, token):
        """Return (row, ok) — ok only for a live, unexpired, unconsumed
        token. Kept for callers that only need the boolean."""
        row, status = self._lookup_token_row(token)
        return (row, True) if status == "ok" else (None, False)

    # -- abuse guards -----------------------------------------------------

    def _ip_limited(self, ip):
        now = time.time()
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

    def _queue_confirm_email(self, row):
        """Spool the confirm email; the operator's sender drains the spool.
        Returns False when the 3/24h cap suppressed the send."""
        if not self._email_send_allowed(row):
            return False
        token = self.mint_token(row["entry_id"], row["owner_email"])
        link = f"{self.public_host}/waitlist/confirm?token={token}"
        row["active_token"] = token  # the one live token for this row
        # Which email carried the live token — drives the `via` attr on
        # the `confirmed` event (FUNNEL_MEASUREMENT.md §3.4: original |
        # reminder). The reminder overwrites this when it sends.
        row["active_token_kind"] = "confirm"
        doc = {
            "to": row["owner_email"],
            "subject": CONFIRM_SUBJECT,
            "body": CONFIRM_BODY_PATH_B.format(confirm_link=link),
            "queued_at": iso_z(self.clock()),
            "entry_id": row["entry_id"],
        }
        name = (f"{row['entry_id']}-{int(self.clock().timestamp())}-"
                f"{secrets.token_hex(4)}.json")  # unique per send: two
        # sends in the same second for one row must not share a filename
        with open(os.path.join(self.spool_dir, name), "w",
                  encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True)
        row["email_sends"] = row.get("email_sends", []) + [
            self.clock().timestamp()
        ]
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
        re-minted by a late re-submit stays). Counts toward the 3/24h cap
        like every other transactional send. Returns True when the email
        went out; False when the cap deferred it (the job retries on the
        next cron run — the old token stays live, nothing is marked)."""
        if not self._email_send_allowed(row):
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
        opener = REMINDER_OPENERS.get(row.get("source"), REMINDER_OPENERS["form"])
        position = self.queue_position(row["entry_id"])
        doc = {
            "to": row["owner_email"],
            "subject": REMINDER_SUBJECT,
            "kind": "reminder",
            "body": REMINDER_BODY.format(
                opener=opener,
                confirm_link=link,
                position=position if position is not None else "?",
            ),
            "queued_at": iso_z(self.clock()),
            "entry_id": row["entry_id"],
        }
        name = (f"{row['entry_id']}-{int(self.clock().timestamp())}-"
                f"{secrets.token_hex(4)}.json")
        with open(os.path.join(self.spool_dir, name), "w",
                  encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True)
        row["email_sends"] = row.get("email_sends", []) + [
            self.clock().timestamp()
        ]
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
        §5 retention rule, then purged by a separate operator pass."""
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
            return self._create_row(owner, owner_raw, muse_contact)

    def _resubmit(self, row, owner_raw, muse_contact):
        """Pending re-submit: refresh, re-send a fresh token (counts toward
        the 3/24h cap). The old token dies only when the replacement email
        actually goes out — a cap-suppressed re-send must never strand the
        user with zero live tokens."""
        if row["status"] == "confirmed":
            # Idempotent: already on the list. No new event, no email.
            return 200, page_confirmed()
        row["submitted_at"] = iso_z(self.clock())
        if muse_contact:
            row["muse_contact"] = muse_contact
        old_token = row.get("active_token")
        self._save_row(row)
        if self._queue_confirm_email(row):
            if old_token:
                self._consume_token(old_token)
            return 200, page_check_inbox(owner_raw)
        # Capped: the earlier link still works — say so honestly instead of
        # claiming an email was sent.
        return 200, page_already_sent(owner_raw)

    def _create_row(self, owner, owner_raw, muse_contact):
        entry_id = secrets.token_urlsafe(12)
        submitted = self.clock()
        row = {
            "entry_id": entry_id,
            "owner_email": owner,
            "muse_contact": muse_contact,
            "path": "form",
            "source": "form",
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
        self._save_row(row)
        self._emit("waitlist_submitted", entry_id, {"path": "form"})
        self._queue_confirm_email(row)  # first send is always under the cap
        return 200, page_check_inbox(owner_raw)

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

    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        fields = self._fields() if path in (
            "/waitlist/form", "/waitlist/confirm") else {}
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
