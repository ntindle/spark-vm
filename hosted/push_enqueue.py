"""Push enqueue boundary: the trust boundary between a hostile box's filing
storm and the owner's phone (issue #990, GP1/GP3 sub-slice of #967/#969).

The observation points exist — the #952 filing endpoint, the #873 decision
enqueue, #846 rotation, the revoke path, heartbeat-stale derivation, the D9
cron sweep — but none has an enqueue call. This module is the missing
interface: it decides, per plane-observed event, whether a page may be
enqueued, takes the D10 budget reservation atomically, and writes the
outbox work item (or the digest-coalesced audit row) to D1.

This is the push lane's trust boundary, and it is written as one:

- Only plane-originated events enqueue (D2). The event-kind whitelist is
  loud and fail-closed: `decided` / `expired` are explicitly no-page
  (D6/D11) and attempting to enqueue them is a `ValueError`, not a silent
  drop — a caller asking for a no-page event has a bug. The caller
  resolves `box_id → owner_principal` from the plane's enrollment
  registry; the module never accepts a box-asserted owner (D2).
- The D10 bound is the anti-DoS bound, not a quota: a hostile box filing
  at the endpoint's admission rate must not convert filings into pages at
  the same rate. The reservation is one atomic *statement* over both
  scopes (D52) — check-then-increment in two steps lets two racing
  enqueues both read under-bound and both pass, overshooting with no
  violation recorded. The statement form (not an interactive
  BEGIN/COMMIT) is what makes the primitive portable to D1's
  non-interactive batch model.
- Page-once is enforced at the DB layer (D57), not just by a pre-check:
  a partial unique index on `(box_id, event_kind, event_key)` for
  work-item outcomes makes the double-enqueue race structurally
  impossible — the loser's INSERT fails and it is converted to
  `duplicate` with its reservation released.
- Box-controlled strings never reach this module unscrubbed: the payload
  is built at *send* time from the re-read approval record (gate-2,
  D12/D56) via `hosted.push_payload.build_push_payload` — the D4 aid-only
  rule holds on every row this module writes, and the #970 scrub is the
  sender loop's call, owned by this boundary's contract.

Decisions (continuing the global D-series at D50; D45–D49 are the #988
schema contract):

- **D50. Inline vs outbox: outbox.** The #952 filing request path never
  sends synchronously. Backpressure argument, with #989's latency input:
  `hosted/push_sender.py` returns `retry_after_s` up to 600 s (the 429
  `Retry-After` clamp) and retries 5xx on a backoff schedule — on the
  filing leg that wedges the box's filing POST for minutes per page; even
  the fast path spends connect + TLS + send on the filing leg, and #989
  measures `latency_ms` per attempt precisely because real push-service
  RTT is unknown (the ~38 ms crypto-only figure is *not* send latency),
  so the decision is structural, not tuned to a number. The outbox
  decouples the legs, and it makes D12's gate-2 load-bearing: the owner
  can decide between enqueue and send, so every send re-reads the
  record's terminal state (D56). Outbox shape: `push_send_results` rows
  with outcome `'queued'` — a third enqueue-boundary extension alongside
  the contract's `suppressed_budget` / `suppressed_terminal` (the
  contract's "two" needs a follow-up amendment; filed). The row is the
  work item: the sender loop (later slice) selects `'queued'` rows,
  attempts via `hosted/push_sender.py`, INSERTs one row per attempt (the
  contract: "every send attempt lands exactly one row"), and on the
  terminal attempt DELETEs the queued work-item row — so the "three
  retries then accepted lands four rows" accounting holds verbatim.
- **D51. Enqueue API shape.** `enqueue_page(conn, *, event_kind,
  owner_principal, box_id, key_material, now=None)` — one call per
  plane-observed event. The module owns the §1.3a event-key encoding
  (scope + U+0000 + key_material); callers never assemble keys, so a
  mis-encoded key is impossible by construction. `key_material` is the
  kind's second component (aid / token_hash / revoked_at / stale_epoch;
  window_start for `digest`, where `box_id` is None and the scope is the
  owner). Enqueue-time rows carry `device=''` — device is unknown until
  fanout at send (D3), and the D10 budget counts pages, not device
  deliveries, so one queued row per event is the correct granularity.
  Returns an `EnqueueResult` (`queued` | `duplicate` |
  `suppressed_budget`).
- **D52. Atomic reservation primitive.** `reserve_budget(conn, box_id,
  owner_principal, window_start, box_bound=3, owner_bound=10)` performs
  the reservation as **one atomic statement** — no BEGIN/COMMIT text, no
  interactive rowcount-then-commit decision, so the primitive ports
  verbatim to D1's non-interactive batch model (the batch is
  [ensure-box, ensure-owner, guarded-UPDATE]; success = the UPDATE
  touched 2 rows):

      UPDATE push_budget_counters SET count = count + 1
      WHERE window_start = ?
        AND ((scope_type = 'box' AND scope_id = ?)
          OR (scope_type = 'owner' AND scope_id = ?))
        AND 2 = (SELECT COUNT(*) FROM push_budget_counters
                 WHERE window_start = ?
                   AND ((scope_type = 'box' AND scope_id = ? AND count < ?)
                     OR (scope_type = 'owner' AND scope_id = ? AND count < ?)))

  The scalar subquery (not a CTE — CTE-wrapped UPDATEs report
  `rowcount = -1` in Python's sqlite3, so success would be
  undetectable) gates the increment: unless *both* scopes are under
  bound at execution time, zero rows are touched. A page consumes one
  unit of each scope; the two scopes are never incremented
  independently. Bounds default to the D10 pins (3 / 10) and are
  parameters so the harness can prove the atomicity at bound=1.
  `box_id=None` (the digest, which has no box) reserves the owner
  scope only — one conditional UPDATE, success = 1 row.
- **D53. Dedup rule.** Page-once per D13 key is enforced at the DB
  layer (D57): the pre-check SELECT is the fast path, but the partial
  unique index is the guarantee — two concurrent enqueues for one key
  cannot both INSERT. The loser releases its just-taken reservation
  and returns `duplicate`. `suppressed_budget` rows also block
  re-enqueue (a replayed filing coalesced into the digest stays
  coalesced — callers are expected to dedup upstream too, e.g. the
  #952 endpoint on `(box_id, aid)`, but the boundary does not rely on
  it) — with one exception (D77): the *digest's own* suppression
  audit uses a suffixed key, so a budget-suppressed digest stays
  retryable. A digest suppressed into oblivion would wedge its
  window's digest permanently: the digest is the delivery vehicle
  for every coalesced page, so unlike a filing it must be allowed
  to retry once budget frees.
- **D54. Digest-enqueue split.** On budget exhaustion the page does not
  send — it coalesces: INSERT the `suppressed_budget` audit row
  (http_status/latency_ms NULL — nothing was sent) and increment
  `push_digest_state.count` for `(owner_principal, window_start)`.
  The D9 slice's digest "send" *is* its `enqueue_page("digest",
  owner_principal, None, window_start)` call when
  `push_digest_state.count > 0` — dedup (D53/D57) makes it idempotent,
  the sender loop POSTs the queued digest row like any page, and the
  reservation happens at *enqueue* time (the D9 slice's enqueue call
  is its send decision). The digest row carries a count, never an aid
  (contract §1.4 — not cancellable per-aid, by design); writing
  `push_digest_state.enqueued_at` when the digest page is accepted is
  the D9/sender slice's obligation, not this one's.
- **D55. VAPID `sub`.** `mailto:hosted@sparkvm.dev` (D48e). The plane
  operator owns this contact; if the mailbox does not exist the pin
  moves with the operator's correction, recorded here. Deploy
  checklist: the mailbox must exist and be monitored — push-service
  abuse complaints go there.
- **D56. Sender-loop contract (later slice).** The loop is the only
  writer of terminal outcomes. It MUST:
  a) *Claiming*: run exactly one instance per D1 store; process
     `'queued'` rows in `id ASC`. Two workers SELECTing the same rows
     double-sends.
  b) *Terminal transaction*: `{INSERT the terminal attempt row, DELETE
     the queued work-item row, release the reservation if the outcome
     releases it}` as **one** transaction. A crash between INSERT and
     DELETE leaves a stale work item → redelivery of a terminal page.
     The release inside that transaction inlines the two UPDATEs from
     `release_reservation` — `release_reservation()` itself commits and
     must not be called mid-transaction.
  c) *Fanout multiplicity*: one row per (device × attempt). The
     enqueue row has `device=''`; each device delivery attempt is its
     own row carrying the real device label (D48d's compromise audit
     joins on the row's `vapid_key_id`). The D10 reservation stays per
     page, not per device-row.
  d) *gate-2 scope*: the terminal-state re-read applies to aid-keyed
     kinds (`approval_filed`, `reminder`) — the approval record
     exists to re-read. `token_expiry_warning` / `box_revoked` /
     `heartbeat_stale` / `digest` are point-in-time facts with no
     approval record (`box_revoked` is itself terminal); gate-2 is
     vacuous for them.
  e) *`suppressed_terminal` shape*: mirrors `suppressed_budget`
     (`device=''`, `http_status`/`latency_ms`/`sent_at`/`vapid_key_id`
     NULL) — the sentinel leg's consumer contract.
  f) *Retry state*: the #989 backoff attempt number is derived from
     `COUNT` of existing `'retry'` rows for the work item's key — no
     new column; the schema stays frozen per the #988 contract. Crash
     posture: INSERT the attempt row immediately after the POST
     returns; a crash in that window under-counts (documented,
     accepted).
  Terminal outcomes resolve the D52 reservation: `accepted` keeps it
  (budget consumed); `tombstone`, `dead-letter`, and
  `suppressed_terminal` release it via `release_reservation`;
  `retry` holds it across attempts; `suppressed_budget` never took
  one.
- **D57. Page-once is a DB invariant.** Partial unique index (to be
  added to `migrate_967_push.sql` and the #988 contract §1.3 by
  follow-up — the contract's "two extensions" text predates the
  `'queued'` third):

      CREATE UNIQUE INDEX IF NOT EXISTS idx_push_send_results_page_once
        ON push_send_results(box_id, event_kind, event_key)
        WHERE outcome IN ('queued', 'suppressed_budget',
                          'suppressed_terminal');

  The predicate excludes the sender loop's per-attempt rows (D50:
  "every send attempt lands exactly one row" — those share the event
  key and must not collide). Attempt rows for a dead subscription
  (`tombstone`) likewise never collide. `suppressed_terminal` is
  covered because the D61 audit key is the page key + a U+0000
  "superseded" suffix — distinct from every page and attempt key, so
  the audit's exactly-once holds under overlapping sweeps (D69) with
  no false collisions. Forward-migration note for the operator (the
  migration lives in the control-plane workspace per the D49 anchor):
  SQLite cannot ALTER an index predicate — `DROP INDEX IF EXISTS
  idx_push_send_results_page_once` then CREATE with the new predicate,
  before deploying any build that writes these tables.

Schema note (D49): this build carries `migrate_967_push.sql` as a
pre-deploy step per the #988 contract. **Pre-deploy instruction for
the operator**: the migration file lives in the control-plane
workspace next to `migrate_958_s4b.sql` (the plane lives outside this
repo); DDL source of truth is `docs/PUSH_SENDER_SCHEMA_CONTRACT.md`
§§1.2–1.4 **plus** the D57 partial unique index above (the contract
text predates it — follow-up filed); apply statement-by-statement
against live D1 *before* deploying any build that writes these
tables; verify with `PRAGMA table_info(push_send_results)` and
`PRAGMA index_list(push_send_results)` after apply, per
`docs/PRODUCTION_DEPLOY_CONTRACT.md` §Schema migrations. The test
fixture DDL below is verbatim from the contract §§1.2–1.4 plus the
D57 index (marked).
"""

from __future__ import annotations

import sqlite3
from collections import namedtuple
from datetime import datetime, timezone

# D55 — the VAPID `sub` contact (D48e). The plane operator owns it.
VAPID_SUB = "mailto:hosted@sparkvm.dev"

# D10 bounds (defaults; the harness drives them to 1).
BOX_BOUND_DEFAULT = 3
OWNER_BOUND_DEFAULT = 10

# The six paging event kinds (taxonomy §2). `decided` and `expired` are
# explicitly no-page (D6/D11) — not members; attempting them is a bug.
PAGING_EVENT_KINDS = frozenset({
    "approval_filed",
    "reminder",
    "token_expiry_warning",
    "box_revoked",
    "heartbeat_stale",
    "digest",
})

# Enqueue-boundary outcome extensions (contract §1.3 vocabulary, plus D50).
OUTCOME_QUEUED = "queued"
OUTCOME_SUPPRESSED_BUDGET = "suppressed_budget"

# D57 — page-once as a DB invariant (see module docstring). The
# predicate covers 'suppressed_terminal' too: the D61 audit key is the
# page key + a U+0000 "superseded" suffix, distinct from every page and
# attempt key, so the audit's exactly-once holds under overlapping
# sweeps with no false collisions.
PAGE_ONCE_INDEX_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_push_send_results_page_once"
    " ON push_send_results(box_id, event_kind, event_key)"
    " WHERE outcome IN ('queued', 'suppressed_budget',"
    " 'suppressed_terminal')"
)

EnqueueResult = namedtuple("EnqueueResult",
                           ["disposition", "event_key", "row_id"])
# disposition ∈ {"queued", "duplicate", "suppressed_budget"}.


def hour_bucket(now=None):
    """UTC hour bucket, the contract's `window_start` format (YYYY-MM-DDTHH).

    Naive datetimes are assumed UTC (same convention as `enqueue_page`).
    """
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def event_key_for(event_kind, owner_principal, box_id, key_material):
    """Build the §1.3a event key: scope + U+0000 + key_material.

    `key_material` is the kind's second component (aid / token_hash /
    revoked_at / stale_epoch; window_start for `digest`, where `box_id`
    is None and the scope is the owner). Fail-closed: empty components
    and embedded U+0000 (separator injection — forging key structure to
    collide with another event's key) are ValueError.
    """
    if event_kind not in PAGING_EVENT_KINDS:
        raise ValueError("not a paging event kind: %r" % (event_kind,))
    if not isinstance(owner_principal, str) or not owner_principal:
        raise ValueError("owner_principal must be a non-empty str")
    if event_kind == "digest":
        scope = owner_principal
        if box_id is not None:
            raise ValueError("digest keys scope to the owner, not a box")
    else:
        scope = box_id
    for name, value in (("scope", scope), ("key_material", key_material)):
        if not isinstance(value, str) or not value:
            raise ValueError("%s must be a non-empty str" % name)
        if "\x00" in value:
            raise ValueError("%s must not contain U+0000" % name)
    return scope + "\x00" + key_material


def _ensure_counter(conn, scope_type, scope_id, window_start):
    conn.execute(
        "INSERT OR IGNORE INTO push_budget_counters"
        " (scope_type, scope_id, window_start, count)"
        " VALUES (?, ?, ?, 0)",
        (scope_type, scope_id, window_start))


# D52 — one atomic statement over both scopes. The scalar subquery (not
# a CTE: CTE-wrapped UPDATEs report rowcount = -1 in Python's sqlite3)
# gates the increment: unless both scopes are under bound at execution
# time, zero rows are touched. Single-statement atomicity holds on every
# SQLite, including D1's non-interactive batch model.
_RESERVE_BOTH_SQL = """\
UPDATE push_budget_counters SET count = count + 1
WHERE window_start = ?
  AND ((scope_type = 'box' AND scope_id = ?)
    OR (scope_type = 'owner' AND scope_id = ?))
  AND 2 = (SELECT COUNT(*) FROM push_budget_counters
           WHERE window_start = ?
             AND ((scope_type = 'box' AND scope_id = ? AND count < ?)
               OR (scope_type = 'owner' AND scope_id = ? AND count < ?)))"""

# Owner-only variant (digest: no box scope exists).
_RESERVE_OWNER_SQL = """\
UPDATE push_budget_counters SET count = count + 1
WHERE scope_type = 'owner' AND scope_id = ? AND window_start = ?
  AND count < ?"""


def reserve_budget(conn, box_id, owner_principal, window_start,
                   box_bound=BOX_BOUND_DEFAULT, owner_bound=OWNER_BOUND_DEFAULT):
    """Atomically reserve one D10 budget unit (D52).

    `box_id=None` (the digest) reserves the owner scope only. Success =
    the guarded UPDATE touched all its target rows (2, or 1 for
    owner-only); anything else took nothing. The ensure INSERTs are
    idempotent; the UPDATE is the single atomic step.
    """
    if not isinstance(box_bound, int) or isinstance(box_bound, bool) \
            or box_bound < 1:
        raise ValueError("box_bound must be a positive int")
    if not isinstance(owner_bound, int) or isinstance(owner_bound, bool) \
            or owner_bound < 1:
        raise ValueError("owner_bound must be a positive int")
    if box_id is not None:
        _ensure_counter(conn, "box", box_id, window_start)
    _ensure_counter(conn, "owner", owner_principal, window_start)
    conn.commit()
    if box_id is not None:
        cur = conn.execute(
            _RESERVE_BOTH_SQL,
            (window_start, box_id, owner_principal,
             window_start, box_id, box_bound, owner_principal, owner_bound))
        conn.commit()
        return cur.rowcount == 2
    cur = conn.execute(
        _RESERVE_OWNER_SQL, (owner_principal, window_start, owner_bound))
    conn.commit()
    return cur.rowcount == 1


def release_reservation(conn, box_id, owner_principal, window_start):
    """Release one D10 reservation (D56). Each scope floored at zero — a
    double-release (bug) must not drive a counter negative and mint
    phantom budget. `box_id=None` releases the owner scope only.

    Standalone form (commits). The sender loop's terminal transaction
    inlines the two UPDATEs instead — do not call this mid-transaction.
    """
    with conn:
        if box_id is not None:
            conn.execute(
                "UPDATE push_budget_counters SET count ="
                " CASE WHEN count > 0 THEN count - 1 ELSE 0 END"
                " WHERE scope_type = 'box' AND scope_id = ?"
                " AND window_start = ?",
                (box_id, window_start))
        conn.execute(
            "UPDATE push_budget_counters SET count ="
            " CASE WHEN count > 0 THEN count - 1 ELSE 0 END"
            " WHERE scope_type = 'owner' AND scope_id = ? AND window_start = ?",
            (owner_principal, window_start))


def _insert_result_row(conn, at, owner_principal, box_col, event_kind,
                       event_key, outcome):
    cur = conn.execute(
        "INSERT INTO push_send_results"
        " (at, owner_principal, box_id, device, event_kind, event_key,"
        "  outcome, http_status, latency_ms, sent_at, vapid_key_id)"
        " VALUES (?, ?, ?, '', ?, ?, ?, NULL, NULL, NULL, NULL)",
        (at, owner_principal, box_col, event_kind, event_key, outcome))
    return cur.lastrowid


def enqueue_page(conn, *, event_kind, owner_principal, box_id,
                 key_material, now=None):
    """Enqueue one plane-observed paging event (D51).

    Gate order: kind whitelist (fail-closed) → key encoding → dedup
    fast-path (D53; the D57 index is the enforcement) → atomic budget
    reservation (D52) → outbox write (D50) or digest coalescing (D54).
    A lost dedup race surfaces as IntegrityError on the INSERT: the
    loser releases its reservation and returns `duplicate`.
    Returns an EnqueueResult.
    """
    if not isinstance(owner_principal, str) or not owner_principal:
        raise ValueError("owner_principal must be a non-empty str")
    event_key = event_key_for(event_kind, owner_principal, box_id,
                              key_material)
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    at = moment.astimezone(timezone.utc).isoformat()
    window_start = hour_bucket(moment)
    # Digest rows store box_id='' (stable dedup key); the reservation
    # for a digest is owner-only (D52) — no ("box","") shared counter.
    box_col = box_id if box_id is not None else ""

    # D53 — dedup fast path before the budget gate: a replay consumes
    # no budget. (The D57 index enforces it under concurrency.)
    dup = conn.execute(
        "SELECT 1 FROM push_send_results"
        " WHERE box_id = ? AND event_kind = ? AND event_key = ? LIMIT 1",
        (box_col, event_kind, event_key)).fetchone()
    if dup is not None:
        return EnqueueResult("duplicate", event_key, None)

    # D52 — one atomic reservation over the applicable scopes.
    if not reserve_budget(conn, box_id, owner_principal, window_start):
        # D54 — over budget: audit row + digest coalescing, no send.
        # D77 — the digest's suppression audit carries its own key
        # (the page key + a "\x00suppressed" suffix): sharing the
        # page's exact key would let the boundary's outcome-blind
        # dedup fast-path report a later retry as "duplicate" even
        # though no digest ever went out — one over-budget hour would
        # wedge that window's digest permanently. Filing events keep
        # the exact key: a replayed filing coalesced into the digest
        # must stay coalesced (D53). (The D61 pattern, applied to the
        # digest: suppressed_terminal audits already suffix for the
        # same reason.)
        if event_kind == "digest":
            audit_key = event_key + "\x00suppressed"
        else:
            audit_key = event_key
        try:
            with conn:
                row_id = _insert_result_row(conn, at, owner_principal,
                                            box_col, event_kind, audit_key,
                                            OUTCOME_SUPPRESSED_BUDGET)
                conn.execute(
                    "INSERT OR IGNORE INTO push_digest_state"
                    " (owner_principal, window_start, count)"
                    " VALUES (?, ?, 0)",
                    (owner_principal, window_start))
                conn.execute(
                    "UPDATE push_digest_state SET count = count + 1"
                    " WHERE owner_principal = ? AND window_start = ?",
                    (owner_principal, window_start))
        except sqlite3.IntegrityError:
            # Lost the race: another thread coalesced this key first
            # (filings), or this window's suppression is already
            # recorded (digest — the retry then just re-reads the
            # same pending row). Nothing was reserved on this path,
            # nothing to release.
            return EnqueueResult("duplicate", event_key, None)
        return EnqueueResult("suppressed_budget", event_key, row_id)

    # D50 — the outbox work item. device='' until fanout at send (D51).
    try:
        with conn:
            row_id = _insert_result_row(conn, at, owner_principal, box_col,
                                        event_kind, event_key, OUTCOME_QUEUED)
    except sqlite3.IntegrityError:
        # Lost the dedup race (D57): release the just-taken unit and
        # report duplicate — one event, one page, one budget unit.
        release_reservation(conn, box_id, owner_principal, window_start)
        return EnqueueResult("duplicate", event_key, None)
    return EnqueueResult("queued", event_key, row_id)


def get_counter(conn, scope_type, scope_id, window_start):
    """Read a budget counter (harness/testing aid)."""
    row = conn.execute(
        "SELECT count FROM push_budget_counters"
        " WHERE scope_type = ? AND scope_id = ? AND window_start = ?",
        (scope_type, scope_id, window_start)).fetchone()
    return row[0] if row else 0


def get_digest_count(conn, owner_principal, window_start):
    """Read the digest coalesced-page count (harness/testing aid)."""
    row = conn.execute(
        "SELECT count FROM push_digest_state"
        " WHERE owner_principal = ? AND window_start = ?",
        (owner_principal, window_start)).fetchone()
    return row[0] if row else 0
