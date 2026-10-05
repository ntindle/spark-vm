"""GP3 event-to-push mapping: which plane-observed events may page (#969).

This module is the push lane's paging *policy*. It sits above the enqueue
boundary (`hosted/push_enqueue.py`, #990): every page decision here ends
in exactly one `enqueue_page` call (or an explicit no-page disposition),
so the D10 budget, the D57 page-once invariant, and the outbox shape are
enforced for every event kind without re-implementation.

The mapping is `docs/PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md` §2 as code.
Every row of that table is a plane-originated event (D2); "Page" is the
enqueue verdict; nothing else may enqueue:

| Event                | Page verdict in this module                              |
|----------------------|----------------------------------------------------------|
| approval filed       | `on_approval_filed` -> enqueue once, key = aid            |
| reminder (T-minus)   | `maybe_enqueue_reminder` -> enqueue once per approval,   |
|                      |   at created_at + TTL/2 and only when TTL >= 300s (D8)   |
| decided (#873)       | **no page** — no function exists; unrepresentable (D6)   |
| expired (server-side)| **no page** — no function exists; unrepresentable (D11)  |
| token-expiry warning | `on_token_expiry_warning` -> once per token generation, |
|                      |   key = current token_hash (D13)                          |
| box revoked          | `on_box_revoked` -> once, key = revoked_at               |
| heartbeat-stale      | `on_heartbeat_stale` -> once per stale-epoch, with the  |
|                      |   F7 quiet period                                         |
| digest               | `maybe_enqueue_digest` -> the D54 digest trigger         |

Decisions (continuing the push lane's D-series; D50-D57 are #990's):

- **D58. No-page events are unrepresentable.** `decided` and `expired`
  have no mapping function. A caller asking to page a decided/expired
  approval has no call path — stronger than the boundary's ValueError,
  which remains the backstop for the kinds that do exist.
- **D59. Reminder gate-1 re-read.** `maybe_enqueue_reminder` re-reads
  the #872 approval record through an injected `get_record(aid)` and
  pages only when the record is still pending (D12 gate-1). The reader
  contract: returns `None` when the record does not exist, else a dict
  with `created_at` (full ISO-8601 timestamp with a time component —
  a bare date carries no time and fails loud, per the #988 TEXT
  timestamp convention), `ttl_seconds` (int), and `terminal` (bool — an owner decision exists
  or server-side expiry fired, derived plane-side). A corrupt record
  (unparseable timestamp, non-int TTL, missing keys, wrong types) is a
  `ValueError`, not a silent skip: a sweep that quietly drops corrupt
  records hides data corruption, and a reminder must never fire on a
  record whose timing cannot be trusted.
- **D60. Reminder timing (D8).** `ttl_seconds < 300` -> disposition
  `no_reminder_ttl` (the approval never qualified; not a suppression).
  `reminder_at = created_at + ttl_seconds / 2`; `now < reminder_at` ->
  `reminder_not_due`. One reminder per approval is enforced by the
  boundary's dedup on `(box_id, "reminder", aid-key)` — a second
  gate-1 pass returns `duplicate`, never a second page.
- **D61. Gate-1 superseded audit.** A due reminder whose re-read finds
  the record terminal writes a `suppressed_terminal` row (the D56e
  shape: `device=''`, `http_status`/`latency_ms`/`sent_at`/`vapid_key_id`
  NULL) and returns `superseded_terminal`. The audit row feeds the
  sentinel leg (#798-#800), not the phone — a decided/expired approval
  is operator-visible, never owner-paged. This is what makes "a decided
  approval never gets a post-decision reminder" (#969 acceptance)
  auditable rather than aspirational. Two properties the periodic D9
  sweep demands: the write is idempotent (a SELECT on the audit key
  precedes the INSERT, so a terminal approval accrues exactly one audit
  row no matter how many sweep passes observe it), and the audit row
  carries its own key (the page key + a U+0000 "superseded" suffix) —
  sharing the page's exact key would let the boundary's outcome-blind
  dedup fast-path misreport a later page attempt as "duplicate" though
  no page ever went out.
- **D62. Heartbeat-stale quiet period (F7).** After a heartbeat-stale
  page for a box, further stale epochs for the same box do not page for
  **4 hours**, returning `suppressed_quiet_period` with no row written
  and no budget consumed. Rationale (recorded per F7, the build's call):
  the #864 heartbeat cadence is 1/min, so 4h = 240 missed heartbeats —
  long enough to cover flap clusters (reboot, brief network loss) that
  re-derive fresh stale epochs, short enough that a genuinely re-staled
  box re-pages the same evening. Only `queued` rows arm the window: a
  `suppressed_budget` row never buzzed, so it must not start the quiet
  clock. Same-epoch replays never reach the quiet check — the
  boundary's dedup returns `duplicate` first (page-once per
  stale-epoch, taxonomy §2).
- **D63. Token-warning timing belongs to the caller.** The 2h lead and
  F6's "only if no rotation since the last window" are the rotation
  watcher's timing decision — it owns the boxes-row read. This module
  enforces once-per-generation structurally: `key_material` is the
  current `token_hash` (D13), so a rotation (hash change) is
  definitionally a new generation and resets the warning key.
- **D64. Digest trigger (D54).** `maybe_enqueue_digest` fires the
  digest enqueue when `push_digest_state.count > 0` for the owner's
  current hour window. The digest page consumes owner budget like any
  page (D10) — the boundary's owner-only reservation handles it; this
  module only decides *whether* the trigger fires.
- **D65. Revocation pages; grandfathering does not.** The taxonomy's
  note is a caller obligation: `on_box_revoked` must only be called
  for real revocation events, never for the pre-#844 keyless-
  grandfathered path. Documented here so the obligation survives the
  call-site.

D2 (caller obligations, restated at each function): `owner_principal`
must be resolved from the plane's enrollment registry, never taken from
a box assertion. The stale-epoch derivation (missed-heartbeat counting
per the #864 cadence) and the token-warning timing are plane-side
caller logic; this module validates the values it is given
(fail-closed) but does not derive them.

Pre-deploy wiring (D49-style anchor for the operator): the D9 sweep /
plane worker calls these functions with `conn` on the live D1 database
(the fixture DDL here is the #988 contract §§1.2-1.4 plus the D57
index, identical to `test_push_enqueue.py`'s). `get_record` is wired to
`SELECT created_at, ttl_seconds, (decision IS NOT NULL OR expired)`
from the #872 approvals table for the aid. No new tables, no worker
route changes in this slice — the sweep scheduler itself (D9) is the
named follow-up.
"""

from __future__ import annotations

import sqlite3
from collections import namedtuple
from datetime import datetime, timedelta, timezone

from hosted import push_enqueue

# F7 — the heartbeat-stale quiet period, the #969 build's call (D62).
HEARTBEAT_STALE_QUIET_PERIOD = timedelta(hours=4)

# D8 — approvals with a shorter TTL never qualify for a reminder.
REMINDER_MIN_TTL_SECONDS = 300

MapResult = namedtuple("MapResult", ["disposition", "detail"])
# disposition ∈ {"queued", "duplicate", "suppressed_budget",  # the boundary's
#                "no_reminder_ttl", "reminder_not_due", "no_record",
#                "superseded_terminal", "suppressed_quiet_period",
#                "no_digest_due"}.
# detail carries the boundary's EnqueueResult for the first three, else None.

_OUTCOME_SUPPRESSED_TERMINAL = "suppressed_terminal"


def _utcnow(now=None):
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _require_owner_box(owner_principal, box_id):
    # D2 restated: the caller resolves these from the enrollment
    # registry; the module fail-closes on anything else.
    if not isinstance(owner_principal, str) or not owner_principal:
        raise ValueError("owner_principal must be a non-empty str")
    if not isinstance(box_id, str) or not box_id:
        raise ValueError("box_id must be a non-empty str")


def _require_key_material(name, value):
    if not isinstance(value, str) or not value:
        raise ValueError("%s must be a non-empty str" % name)
    if "\x00" in value:
        raise ValueError("%s must not contain U+0000" % name)


def _require_iso_timestamp(name, value):
    """Fail-closed ISO-8601 timestamp with a real time component.

    `datetime.fromisoformat` alone accepts date-only strings
    ('2026-10-05' -> midnight): a date carries no time, so a value
    whose timing matters must name its time explicitly. The #988
    contract's convention is full ISO-UTC timestamps.
    """
    _require_key_material(name, value)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("%s must be ISO-8601: %r" % (name, value))
    if "T" not in value and " " not in value:
        raise ValueError(
            "%s must carry a time component, not a bare date: %r"
            % (name, value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_reminder_record(record, aid):
    """Validate the gate-1 record (D59). Returns (created_at, ttl, terminal).

    Fail-loud ValueError on anything unparseable: a reminder must never
    fire on a record whose timing cannot be trusted, and a sweep must
    never silently skip a corrupt record.
    """
    if not isinstance(record, dict):
        raise ValueError("record for aid %r must be a dict" % (aid,))
    try:
        created_raw = record["created_at"]
        ttl_raw = record["ttl_seconds"]
        terminal_raw = record["terminal"]
    except KeyError as e:
        raise ValueError(
            "record for aid %r missing key %s" % (aid, e.args[0]))
    if not isinstance(created_raw, str) or not created_raw:
        raise ValueError(
            "record created_at for aid %r must be a non-empty str" % (aid,))
    created_at = _require_iso_timestamp(
        "record created_at for aid %r" % (aid,), created_raw)
    if isinstance(ttl_raw, bool) or not isinstance(ttl_raw, int):
        raise ValueError(
            "record ttl_seconds for aid %r must be an int" % (aid,))
    if ttl_raw <= 0:
        raise ValueError(
            "record ttl_seconds for aid %r must be positive" % (aid,))
    if not isinstance(terminal_raw, bool):
        raise ValueError(
            "record terminal for aid %r must be a bool" % (aid,))
    return created_at.astimezone(timezone.utc), ttl_raw, terminal_raw


def _write_suppressed_terminal(conn, at, owner_principal, box_id,
                               event_kind, event_key):
    """Gate-1 superseded audit row (D61, D56e shape)."""
    with conn:
        conn.execute(
            "INSERT INTO push_send_results"
            " (at, owner_principal, box_id, device, event_kind, event_key,"
            "  outcome, http_status, latency_ms, sent_at, vapid_key_id)"
            " VALUES (?, ?, ?, '', ?, ?, ?, NULL, NULL, NULL, NULL)",
            (at, owner_principal, box_id, event_kind, event_key,
             _OUTCOME_SUPPRESSED_TERMINAL))


def on_approval_filed(conn, *, box_id, owner_principal, aid, now=None):
    """Map the approval-filed event to one page (taxonomy §2).

    Page-once per (box_id, aid): the boundary's dedup makes replays
    return `duplicate`. Callers are expected to dedup upstream too
    (the #952 endpoint already dedups filings on (box_id, aid)), but
    the boundary does not rely on it.
    """
    _require_owner_box(owner_principal, box_id)
    _require_key_material("aid", aid)
    r = push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal=owner_principal,
        box_id=box_id, key_material=aid, now=now)
    return MapResult(r.disposition, r)


def on_token_expiry_warning(conn, *, box_id, owner_principal, token_hash,
                            now=None):
    """Map the token-expiry warning (taxonomy §2, D13, D63).

    `token_hash` is the boxes row's current token_hash — the generation
    (D13). A rotation changes the hash, which resets the warning key by
    construction. The 2h lead and the F6 no-rotation-since-last-window
    check are the caller's timing decision.
    """
    _require_owner_box(owner_principal, box_id)
    _require_key_material("token_hash", token_hash)
    r = push_enqueue.enqueue_page(
        conn, event_kind="token_expiry_warning",
        owner_principal=owner_principal, box_id=box_id,
        key_material=token_hash, now=now)
    return MapResult(r.disposition, r)


def on_box_revoked(conn, *, box_id, owner_principal, revoked_at, now=None):
    """Map the box-revoked event (taxonomy §2, D65).

    `revoked_at` is the revocation event's identity — a timestamp never
    repeats, so this is identity, not collision-prone dedup. It must be
    a full ISO-8601 timestamp (a bare date could repeat across same-day
    revocations and silently collapse them into one page). Caller
    obligation (D65): never call this for the keyless-grandfathered
    path.
    """
    _require_owner_box(owner_principal, box_id)
    _require_iso_timestamp("revoked_at", revoked_at)
    r = push_enqueue.enqueue_page(
        conn, event_kind="box_revoked", owner_principal=owner_principal,
        box_id=box_id, key_material=revoked_at, now=now)
    return MapResult(r.disposition, r)


def last_heartbeat_stale_page_at(conn, box_id):
    """Newest `queued` heartbeat-stale page for the box (D62 helper).

    Only `queued` rows arm the quiet window — a `suppressed_budget` row
    never buzzed, so it must not start the quiet clock. Returns an
    aware UTC datetime, or None when the box never paged stale.
    """
    row = conn.execute(
        "SELECT MAX(at) FROM push_send_results"
        " WHERE box_id = ? AND event_kind = 'heartbeat_stale'"
        " AND outcome = 'queued'", (box_id,)).fetchone()
    if row is None or row[0] is None:
        return None
    at = datetime.fromisoformat(row[0])
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at.astimezone(timezone.utc)


def on_heartbeat_stale(conn, *, box_id, owner_principal, stale_epoch,
                       now=None):
    """Map the heartbeat-stale event (taxonomy §2, F7, D62).

    `stale_epoch` is the caller's derived staleness identity (opaque
    non-empty string — e.g. when staleness was first derived). Page-once
    per epoch comes from the boundary's dedup; the F7 quiet period
    suppresses *new* epochs for the same box within 4h of the last
    stale page, returning `suppressed_quiet_period` with no row and no
    budget consumed.
    """
    _require_owner_box(owner_principal, box_id)
    _require_key_material("stale_epoch", stale_epoch)
    moment = _utcnow(now)
    event_key = push_enqueue.event_key_for(
        "heartbeat_stale", owner_principal, box_id, stale_epoch)
    # Page-once per stale-epoch (taxonomy §2): the boundary's dedup
    # fast-path, mirrored here so the quiet check below only ever sees
    # genuinely new pages. (The boundary re-checks under the D57 index;
    # this SELECT is the same no-budget fast path it uses — the index
    # remains the enforcement under concurrency.)
    dup = conn.execute(
        "SELECT 1 FROM push_send_results"
        " WHERE box_id = ? AND event_kind = 'heartbeat_stale'"
        " AND event_key = ? LIMIT 1",
        (box_id, event_key)).fetchone()
    if dup is not None:
        return MapResult(
            "duplicate",
            push_enqueue.EnqueueResult("duplicate", event_key, None))
    last_page = last_heartbeat_stale_page_at(conn, box_id)
    if last_page is not None \
            and moment - last_page < HEARTBEAT_STALE_QUIET_PERIOD:
        return MapResult("suppressed_quiet_period", None)
    r = push_enqueue.enqueue_page(
        conn, event_kind="heartbeat_stale", owner_principal=owner_principal,
        box_id=box_id, key_material=stale_epoch, now=moment)
    return MapResult(r.disposition, r)


def maybe_enqueue_reminder(conn, *, box_id, owner_principal, aid,
                           get_record, now=None):
    """Gate-1 reminder decision for one approval (D8, D12, D59-D61).

    `get_record(aid)` is the D59 reader contract (None, or a dict with
    created_at / ttl_seconds / terminal). Returns a MapResult; only the
    due-and-pending path enqueues.
    """
    _require_owner_box(owner_principal, box_id)
    _require_key_material("aid", aid)
    if not callable(get_record):
        raise ValueError("get_record must be callable")
    moment = _utcnow(now)

    record = get_record(aid)
    if record is None:
        return MapResult("no_record", None)
    created_at, ttl_seconds, terminal = _parse_reminder_record(record, aid)

    if ttl_seconds < REMINDER_MIN_TTL_SECONDS:
        return MapResult("no_reminder_ttl", None)
    reminder_at = created_at + timedelta(seconds=ttl_seconds) / 2
    if moment < reminder_at:
        return MapResult("reminder_not_due", None)

    if terminal:
        # D61 — the lease vested (due) but the re-read finds the record
        # terminal: no page, ever. The audit row is the sentinel-leg
        # record of the lease loss. The audit row carries its own key
        # (the page key + a "\x00superseded" suffix): sharing the page's
        # exact key would let the boundary's outcome-blind dedup
        # fast-path report a later page attempt as "duplicate" even
        # though no page ever went out. The write is idempotent — the
        # periodic sweep must not accrue one audit row per pass.
        event_key = push_enqueue.event_key_for(
            "reminder", owner_principal, box_id, aid)
        audit_key = event_key + "\x00superseded"
        dup = conn.execute(
            "SELECT 1 FROM push_send_results"
            " WHERE box_id = ? AND event_kind = 'reminder'"
            " AND event_key = ? LIMIT 1",
            (box_id, audit_key)).fetchone()
        if dup is None:
            _write_suppressed_terminal(
                conn, moment.isoformat(), owner_principal, box_id,
                "reminder", audit_key)
        return MapResult("superseded_terminal", None)

    r = push_enqueue.enqueue_page(
        conn, event_kind="reminder", owner_principal=owner_principal,
        box_id=box_id, key_material=aid, now=moment)
    return MapResult(r.disposition, r)


def maybe_enqueue_digest(conn, *, owner_principal, now=None):
    """Fire the D54 digest trigger when coalesced pages exist (D64).

    When `push_digest_state.count > 0` for the owner's current hour
    window, enqueues the digest page (key = window_start). The digest
    consumes owner budget like any page (D10) — enforced by the
    boundary, not here. Returns `no_digest_due` when nothing coalesced.
    """
    if not isinstance(owner_principal, str) or not owner_principal:
        raise ValueError("owner_principal must be a non-empty str")
    moment = _utcnow(now)
    window_start = push_enqueue.hour_bucket(moment)
    if push_enqueue.get_digest_count(conn, owner_principal,
                                     window_start) <= 0:
        return MapResult("no_digest_due", None)
    r = push_enqueue.enqueue_page(
        conn, event_kind="digest", owner_principal=owner_principal,
        box_id=None, key_material=window_start, now=moment)
    return MapResult(r.disposition, r)
