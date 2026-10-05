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
  drop — a caller asking for a no-page event has a bug.
- The D10 bound is the anti-DoS bound, not a quota: a hostile box filing
  at the endpoint's admission rate must not convert filings into pages at
  the same rate. The reservation is one atomic step over both scopes
  (D52) — check-then-increment in two steps lets two racing enqueues both
  read under-bound and both pass, overshooting with no violation
  recorded.
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
  the contract's `suppressed_budget` / `suppressed_terminal`. The row is
  the work item: the sender loop (later slice) selects `'queued'` rows,
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
  one atomic step over both scopes: `BEGIN IMMEDIATE`, `INSERT OR
  IGNORE` both counter rows, then one conditional `UPDATE ... WHERE
  count < bound` per scope — both must affect exactly one row or the
  transaction rolls back. A page consumes one unit of each scope; the
  two scopes are never incremented independently (a box-scope success
  with an owner-scope failure would leak a reservation the owner scope
  never granted). Bounds default to the D10 pins (3 / 10) and are
  parameters so the harness can prove the atomicity at bound=1.
- **D53. Dedup rule.** Before the budget gate: if any row already
  exists for `(box_id, event_kind, event_key)` the enqueue is a replay
  — return `duplicate`, write nothing, consume no budget. This is the
  page-once-per-D13-key enforcement; `suppressed_budget` rows also
  block re-enqueue (a replayed filing coalesced into the digest stays
  coalesced — the #952 endpoint dedups filings on `(box_id, aid)`
  anyway, so a second enqueue for the same key is never legitimate).
- **D54. Digest-enqueue split.** On budget exhaustion the page does not
  send — it coalesces: INSERT the `suppressed_budget` audit row
  (http_status/latency_ms NULL — nothing was sent) and increment
  `push_digest_state.count` for `(owner_principal, window_start)`.
  This slice owns the *coalescing write*; the digest *send* ("N
  approvals need you") is the D9/reminder slice's — which reserves one
  owner-budget unit at send time (D10: the digest is a buzz, not
  silence). The digest row carries a count, never an aid (contract
  §1.4 — not cancellable per-aid, by design).
- **D55. VAPID `sub`.** `mailto:hosted@sparkvm.dev` (D48e). The plane
  operator owns this contact; if the mailbox does not exist the pin
  moves with the operator's correction, recorded here.
- **D56. Gate-2 and the reservation lifecycle belong to the sender
  loop.** Terminal outcomes resolve the D52 reservation: `accepted`
  keeps it (budget consumed); `tombstone`, `dead-letter`, and
  `suppressed_terminal` release it via `release_reservation` (this
  module — decrement both scopes, floored at zero); `retry` holds it
  across attempts; `suppressed_budget` never took one. Gate-2 (D12):
  the sender loop re-reads the approval record's terminal state before
  every send; decided/expired → drop silently, write the
  `suppressed_terminal` audit row (the D12 audit row the sentinel leg
  consumes), release the reservation. The loop is a later slice; the
  primitives it needs are here.

Schema note (D49): this build carries `migrate_967_push.sql` as a
pre-deploy step per the #988 contract — the four tables this module
writes (`push_budget_counters`, `push_send_results`,
`push_digest_state`; `push_subscriptions` is #968's). The plane lives
outside this repo, so the migration file lives in the control-plane
workspace next to `migrate_958_s4b.sql`; the DDL below (test fixture)
is verbatim from `docs/PUSH_SENDER_SCHEMA_CONTRACT.md` §§1.2–1.4.

`mailto:hosted@sparkvm.dev`
"""

from __future__ import annotations

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

EnqueueResult = namedtuple("EnqueueResult",
                           ["disposition", "event_key", "row_id"])
# disposition ∈ {"queued", "duplicate", "suppressed_budget"}.


def hour_bucket(now=None):
    """UTC hour bucket, the contract's `window_start` format (YYYY-MM-DDTHH)."""
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def event_key_for(event_kind, owner_principal, box_id, key_material):
    """Build the §1.3a event key: scope + U+0000 + key_material.

    `key_material` is the kind's second component (aid / token_hash /
    revoked_at / stale_epoch; window_start for `digest`, where `box_id`
    is None and the scope is the owner). Fail-closed: empty components
    and embedded U+0000 (separator injection — a hostile box forging key
    structure to collide with another event's key) are ValueError.
    """
    if event_kind not in PAGING_EVENT_KINDS:
        raise ValueError("not a paging event kind: %r" % (event_kind,))
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


def reserve_budget(conn, box_id, owner_principal, window_start,
                   box_bound=BOX_BOUND_DEFAULT, owner_bound=OWNER_BOUND_DEFAULT):
    """Atomically reserve one D10 budget unit on both scopes (D52).

    One atomic step: BEGIN IMMEDIATE, ensure both counter rows, then one
    conditional UPDATE per scope — both must affect exactly one row, or
    the transaction rolls back and False is returned. Never increments
    one scope without the other.
    """
    if not isinstance(box_bound, int) or box_bound < 1:
        raise ValueError("box_bound must be a positive int")
    if not isinstance(owner_bound, int) or owner_bound < 1:
        raise ValueError("owner_bound must be a positive int")
    if conn.in_transaction:
        # Fail closed: BEGIN IMMEDIATE inside a caller-held transaction
        # would join it, and our ROLLBACK could then nuke the caller's
        # work. The reservation must be its own atomic step.
        raise ValueError("reserve_budget requires no open transaction")
    conn.execute("BEGIN IMMEDIATE")
    try:
        _ensure_counter(conn, "box", box_id, window_start)
        _ensure_counter(conn, "owner", owner_principal, window_start)
        box_rows = conn.execute(
            "UPDATE push_budget_counters SET count = count + 1"
            " WHERE scope_type = 'box' AND scope_id = ?"
            " AND window_start = ? AND count < ?",
            (box_id, window_start, box_bound)).rowcount
        owner_rows = conn.execute(
            "UPDATE push_budget_counters SET count = count + 1"
            " WHERE scope_type = 'owner' AND scope_id = ?"
            " AND window_start = ? AND count < ?",
            (owner_principal, window_start, owner_bound)).rowcount
        if box_rows == 1 and owner_rows == 1:
            conn.execute("COMMIT")
            return True
        conn.execute("ROLLBACK")
        return False
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def release_reservation(conn, box_id, owner_principal, window_start):
    """Release one D10 reservation on both scopes (D56). Floored at zero —
    a double-release (bug) must not drive a counter negative and mint
    phantom budget."""
    with conn:
        conn.execute(
            "UPDATE push_budget_counters SET count ="
            " CASE WHEN count > 0 THEN count - 1 ELSE 0 END"
            " WHERE scope_type = 'box' AND scope_id = ? AND window_start = ?",
            (box_id, window_start))
        conn.execute(
            "UPDATE push_budget_counters SET count ="
            " CASE WHEN count > 0 THEN count - 1 ELSE 0 END"
            " WHERE scope_type = 'owner' AND scope_id = ? AND window_start = ?",
            (owner_principal, window_start))


def _insert_result_row(conn, at, owner_principal, box_id, event_kind,
                       event_key, outcome):
    cur = conn.execute(
        "INSERT INTO push_send_results"
        " (at, owner_principal, box_id, device, event_kind, event_key,"
        "  outcome, http_status, latency_ms, sent_at, vapid_key_id)"
        " VALUES (?, ?, ?, '', ?, ?, ?, NULL, NULL, NULL, NULL)",
        (at, owner_principal, box_id if box_id is not None else "",
         event_kind, event_key, outcome))
    return cur.lastrowid


def enqueue_page(conn, *, event_kind, owner_principal, box_id,
                 key_material, now=None):
    """Enqueue one plane-observed paging event (D51).

    Gate order: kind whitelist (fail-closed) → key encoding → dedup
    (D53) → atomic budget reservation (D52) → outbox write (D50) or
    digest coalescing (D54). Returns an EnqueueResult.
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
    box_scope = box_id if box_id is not None else ""

    # D53 — dedup before the budget gate: a replay consumes no budget.
    dup = conn.execute(
        "SELECT 1 FROM push_send_results"
        " WHERE box_id = ? AND event_kind = ? AND event_key = ? LIMIT 1",
        (box_scope, event_kind, event_key)).fetchone()
    if dup is not None:
        return EnqueueResult("duplicate", event_key, None)

    # D52 — one atomic reservation over both scopes.
    if not reserve_budget(conn, box_scope, owner_principal, window_start):
        # D54 — over budget: audit row + digest coalescing, no send.
        with conn:
            row_id = _insert_result_row(conn, at, owner_principal, box_scope,
                                        event_kind, event_key,
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
        return EnqueueResult("suppressed_budget", event_key, row_id)

    # D50 — the outbox work item. device='' until fanout at send (D51).
    with conn:
        row_id = _insert_result_row(conn, at, owner_principal, box_scope,
                                    event_kind, event_key, OUTCOME_QUEUED)
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
