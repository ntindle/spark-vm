"""Async plane-port of the push enqueue boundary (#1614 — the async-boundary
port slice of the endpoint-wiring gap analysis).

`hosted/push_enqueue.py` ships the sync boundary: gate order, the D10
atomic budget reservation, the D57 page-once DB invariant, the D54 digest
coalescing. This module is its async counterpart against the plane
worker's async `_D1` (F-PP-2: `await db.prepare(...).bind(...).run()`;
no synchronous D1 exists). Like `hosted/push_sweep_async.py`, this file
is droppable into `worker.py` verbatim: stdlib-only, no imports from the
sync modules, pure-compute helpers inlined with source citations (the
ed25519 precedent), and the DB seam as awaited `_D1` calls.

Entry point (the contract named by #1492's module docstring —
`await enqueue_page(db, *, event_kind, owner_principal, box_id,
key_material, now=None) -> result with .disposition`):

    await enqueue_page_async(db, *, event_kind, owner_principal, box_id,
                             key_material, now=None) -> EnqueueResult

`db` is the worker's async `_D1`; `now` is an aware UTC datetime or None
(the boundary defaults it, exactly like the sync version). The name
carries the `_async` suffix because this file shares the in-repo
namespace with the sync module (the `push_sweep_async` naming
precedent) — in the worker's marked section it IS the contract's
`enqueue_page`.

The sync module stays the harness and test truth (D-PP-1): the boundary
reuses the sync decision table verbatim (D-EW-2) — D10 budget, D57
page-once dedup, D54 digest coalescing. Policy is not re-decided, only
the DB-API boundary is ported.

D1 durability model (read this before the code): the `_D1` contract
exposes no interactive transaction across awaits, so the port cannot
spell the sync's `with conn:` groups. Every `.run()` is individually
durable on the worker; the port orders statements so every crash window
is either idempotent under retry or a documented under-count (the D56(f)
posture):

- The D52 guarded UPDATE is the single atomic gate, unchanged in shape —
  it is one statement, so it stays one atomic step on D1.
- The ensure INSERTs are `INSERT OR IGNORE` (idempotent); the D54 filing
  path's audit INSERT is idempotent under retry via the D57 page-once
  index (a retried filing hits the boundary's own dedup fast-path and
  returns `duplicate` before reserving); a crash between the audit INSERT
  and the `push_digest_state` increment under-counts the digest — the
  digest still goes out (the retry renders the true count), the audit row
  still records the suppression. Documented, accepted.
- The digest-suppressed path (#1423/D77) writes only the suffixed
  suppression audit — one statement, no window at all.

Conflict handling (the D53 lost-race path): on the worker, a D57
page-once violation rejects the INSERT's promise; the port cannot name
the worker's exception class from a stdlib-only module. The rule is
therefore exception-type-agnostic but outcome-gated: any failure from
the outbox INSERT is followed by a re-read for a same-key row carrying
a D57-covered outcome (`'queued'`, `'suppressed_budget'`,
`'suppressed_terminal'`). Only such a row could have rejected the
INSERT through the page-once index, so only then is the lost race
declared (`_DedupLost` → `duplicate`, the reservation released if one
was taken — one event, one page, one budget unit). A same-key row with
any other outcome (e.g. a sender-loop `'retry'` attempt row, which
shares the event key but sits outside the index predicate) cannot be
the conflict: the original error is re-raised, loud. Residual: an
INSERT that fails for a non-uniqueness reason while a covered row
happens to exist still reports `duplicate` — narrow, not
attacker-triggerable, and the budget-safe direction for an anti-DoS
bound.

Trust posture (D2): this boundary never accepts a box-asserted owner.
The caller resolves `box_id → owner_principal` from the plane's
enrollment registry and passes the resolved principal in; a hostile
box that supplies its own owner string must be rejected upstream —
this module cannot distinguish it. The obligation travels with this
file because it drops into `worker.py` verbatim, ahead of the
endpoint wiring (D-EW-3).

STACKING: this slice resolves the STACKING NOTE in
`hosted/push_events_async.py` for the boundary half — the async mappings
now have an async boundary to inject. The two endpoint call sites (the
#952 filing endpoint, the revoke endpoint — deployed-worker code) are
the plane's wiring half, tracked on #1614 with the live tick (D-EW-3).
"""

from __future__ import annotations

from collections import namedtuple
from datetime import datetime, timezone

# --- carried constants (source: hosted/push_enqueue.py) -------------------
# Duplicated, not imported: the worker's marked section cannot import
# the repo's hosted package (the ed25519 precedent). Any change to the
# source must be mirrored here (and vice versa).

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

# D57 — page-once as a DB invariant (see hosted/push_enqueue.py). The
# test fixture DDL must carry this statement verbatim.
PAGE_ONCE_INDEX_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_push_send_results_page_once"
    " ON push_send_results(box_id, event_kind, event_key)"
    " WHERE outcome IN ('queued', 'suppressed_budget',"
    " 'suppressed_terminal')"
)

EnqueueResult = namedtuple("EnqueueResult",
                           ["disposition", "event_key", "row_id"])
# disposition ∈ {"queued", "duplicate", "suppressed_budget"} — the same
# vocabulary the sync boundary returns, so the async mappings'
# `.disposition` passthrough is unchanged.


class _DedupLost(Exception):
    """Internal signal: the outbox INSERT conflicted with an existing
    row, i.e. this enqueue lost the D53 dedup race."""


# --- inlined pure-compute helpers ------------------------------------------
# Source: hosted/push_enqueue.py (hour_bucket, utc_iso, event_key_for)
# and hosted/push_events.py (the _require_* shape). Inlined with source
# citations so this file stays droppable into worker.py verbatim (the
# ed25519 precedent). Any behavioral change to the sync helpers must be
# mirrored here, and vice versa.

def hour_bucket(now=None):
    """UTC hour bucket, the contract's `window_start` format (YYYY-MM-DDTHH).

    ← hosted/push_enqueue.hour_bucket. Naive datetimes are assumed UTC
    (same convention as the sync boundary).
    """
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def utc_iso(now=None):
    """Render one UTC instant in the retention-shape contract's byte shape.

    ← hosted/push_enqueue.utc_iso. The push lane's TEXT timestamp
    comparisons are lexicographic, so they are chronological only while
    every writer of `push_send_results.at` emits this exact shape; this
    helper single-sources the render step. Naive datetimes are assumed
    UTC (the lane's convention).
    """
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


def event_key_for(event_kind, owner_principal, box_id, key_material):
    """Build the §1.3a event key: scope + U+0000 + key_material.

    ← hosted/push_enqueue.event_key_for. `key_material` is the kind's
    second component (aid / token_hash / revoked_at / stale_epoch;
    window_start for `digest`, where `box_id` is None and the scope is
    the owner). Fail-closed: empty components and embedded U+0000
    (separator injection) are ValueError.
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


def _to_py(value):
    """Mirror of the worker's `_to_py` (control-plane/worker.py).

    ← hosted/push_sweep_async._to_py, identical: `.first()` with no match
    returns a JsNull proxy, not None, in the worker; objects with
    `.to_py()` convert. In-repo the shim already yields plain
    dicts/None, so this is a passthrough there — in the worker it does
    the real conversion. Kept identical so this module drops into the
    worker's marked section verbatim.
    """
    if value is None:
        return None
    if type(value).__name__ == "JsNull":
        return None
    to_py = getattr(value, "to_py", None)
    if callable(to_py):
        return to_py()
    return value


async def _first(db, sql, params=()):
    """Run a SELECT and return the first row as a dict, or None.

    Mirrors the worker's consumption idiom, like
    hosted/push_sweep_async._first.
    """
    return _to_py(await db.prepare(sql).bind(*params).first())


async def _run(db, sql, params=()):
    """Run a write and return the raw result (worker shape: success +
    meta with `changes` / `last_row_id`)."""
    return await db.prepare(sql).bind(*params).run()


def _run_changes(raw):
    """Extract the touched-row count from a `.run()` result."""
    meta = _to_py(getattr(raw, "meta", None)) or {}
    return meta.get("changes", 0)


def _run_last_row_id(raw):
    """Extract the INSERT row id from a `.run()` result (D1 `meta`).

    Returns None when the backend does not report one — the sync
    boundary's `row_id` is a diagnostic, never a correctness input.
    """
    meta = _to_py(getattr(raw, "meta", None)) or {}
    return meta.get("last_row_id")


# D52 — one atomic statement over both scopes. ←
# hosted/push_enqueue._RESERVE_BOTH_SQL, verbatim: the scalar subquery
# (not a CTE) gates the increment, so unless both scopes are under bound
# at execution time, zero rows are touched. Single-statement atomicity
# holds on every SQLite, including D1.
_RESERVE_BOTH_SQL = """\
UPDATE push_budget_counters SET count = count + 1
WHERE window_start = ?
  AND ((scope_type = 'box' AND scope_id = ?)
    OR (scope_type = 'owner' AND scope_id = ?))
  AND 2 = (SELECT COUNT(*) FROM push_budget_counters
           WHERE window_start = ?
             AND ((scope_type = 'box' AND scope_id = ? AND count < ?)
               OR (scope_type = 'owner' AND scope_id = ? AND count < ?)))"""

# Owner-only variant (digest: no box scope exists). ←
# hosted/push_enqueue._RESERVE_OWNER_SQL.
_RESERVE_OWNER_SQL = """\
UPDATE push_budget_counters SET count = count + 1
WHERE scope_type = 'owner' AND scope_id = ? AND window_start = ?
  AND count < ?"""

_ENSURE_COUNTER_SQL = (
    "INSERT OR IGNORE INTO push_budget_counters"
    " (scope_type, scope_id, window_start, count)"
    " VALUES (?, ?, ?, 0)")

_INSERT_RESULT_SQL = (
    "INSERT INTO push_send_results"
    " (at, owner_principal, box_id, device, event_kind, event_key,"
    "  outcome, http_status, latency_ms, sent_at, vapid_key_id)"
    " VALUES (?, ?, ?, '', ?, ?, ?, NULL, NULL, NULL, NULL)")

_RELEASE_BOX_SQL = (
    "UPDATE push_budget_counters SET count ="
    " CASE WHEN count > 0 THEN count - 1 ELSE 0 END"
    " WHERE scope_type = 'box' AND scope_id = ? AND window_start = ?")

_RELEASE_OWNER_SQL = (
    "UPDATE push_budget_counters SET count ="
    " CASE WHEN count > 0 THEN count - 1 ELSE 0 END"
    " WHERE scope_type = 'owner' AND scope_id = ? AND window_start = ?")


async def reserve_budget_async(db, box_id, owner_principal, window_start,
                               box_bound=BOX_BOUND_DEFAULT,
                               owner_bound=OWNER_BOUND_DEFAULT):
    """Atomically reserve one D10 budget unit (D52, async port).

    Async counterpart of `hosted/push_enqueue.reserve_budget`.
    `box_id=None` (the digest) reserves the owner scope only. Success =
    the guarded UPDATE touched all its target rows (2, or 1 for
    owner-only); anything else took nothing. `meta.changes` counts
    changed rows and the guarded UPDATE always mutates (`count =
    count + 1`), so matched == changed here; a backend that reports no
    `meta` fails closed (changes=0 → reservation refused → the page
    coalesces into the digest, the budget-safe direction). The ensure
    INSERTs are `INSERT OR IGNORE` (idempotent across awaits); the
    UPDATE is the single atomic step.
    """
    if not isinstance(box_bound, int) or isinstance(box_bound, bool) \
            or box_bound < 1:
        raise ValueError("box_bound must be a positive int")
    if not isinstance(owner_bound, int) or isinstance(owner_bound, bool) \
            or owner_bound < 1:
        raise ValueError("owner_bound must be a positive int")
    if box_id is not None:
        await _run(db, _ENSURE_COUNTER_SQL, ("box", box_id, window_start))
    await _run(db, _ENSURE_COUNTER_SQL,
               ("owner", owner_principal, window_start))
    if box_id is not None:
        raw = await _run(
            db, _RESERVE_BOTH_SQL,
            (window_start, box_id, owner_principal,
             window_start, box_id, box_bound, owner_principal, owner_bound))
        return _run_changes(raw) == 2
    raw = await _run(db, _RESERVE_OWNER_SQL,
                     (owner_principal, window_start, owner_bound))
    return _run_changes(raw) == 1


async def release_reservation_async(db, box_id, owner_principal,
                                    window_start):
    """Release one D10 reservation (D56, async port).

    Async counterpart of `hosted/push_enqueue.release_reservation`.
    Each scope floored at zero — a double-release (bug) must not drive
    a counter negative and mint phantom budget. `box_id=None` releases
    the owner scope only. The two UPDATEs are individually durable on
    D1; no commit primitive exists on the worker's `_D1`.
    """
    if box_id is not None:
        await _run(db, _RELEASE_BOX_SQL, (box_id, window_start))
    await _run(db, _RELEASE_OWNER_SQL, (owner_principal, window_start))


async def _insert_result_row(db, at, owner_principal, box_col, event_kind,
                             event_key, outcome):
    """INSERT one outbox/audit row; return its row id.

    A D57 page-once violation rejects the statement. The port cannot
    name the worker's exception class from a stdlib-only module, so the
    rule is exception-type-agnostic but outcome-gated: any failure is
    followed by a re-read for a same-key row with a D57-covered outcome
    (`'queued'`, `'suppressed_budget'`, `'suppressed_terminal'`) — only
    such a row could have rejected the INSERT through the page-once
    index, so only then is the D53 lost race declared (`_DedupLost`).
    A same-key row with any other outcome (e.g. a sender-loop `'retry'`
    attempt row) cannot be the conflict, and no row at all means the
    failure was operational: in both cases the original error is
    re-raised, loud.
    """
    try:
        raw = await _run(db, _INSERT_RESULT_SQL,
                         (at, owner_principal, box_col, event_kind,
                          event_key, outcome))
    except Exception as exc:
        row = await _first(
            db,
            "SELECT 1 FROM push_send_results"
            " WHERE box_id = ? AND event_kind = ? AND event_key = ?"
            " AND outcome IN ('queued', 'suppressed_budget',"
            " 'suppressed_terminal') LIMIT 1",
            (box_col, event_kind, event_key))
        if row is not None:
            raise _DedupLost(event_key) from exc
        raise
    return _run_last_row_id(raw)


async def _digest_suppressed(db, at, owner_principal, box_col, event_kind,
                             event_key, window_start):
    """Coalesce an over-budget event into the digest (D54, async port).

    Filing kinds: audit row on the exact event key + increment
    `push_digest_state.count` for `(owner_principal, window_start)`. The
    digest kind itself (#1423/D77): the suppression audit carries the
    suffixed key and never touches the count — the digest is retryable
    by design and its retry renders the window's true coalesced count.
    """
    if event_kind == "digest":
        # The suffixed suppression audit is the record of the
        # suppression (one statement, no crash window); a repeated
        # suppression of the same digest is `duplicate` — nothing was
        # reserved on this path, nothing to release.
        audit_key = event_key + "\x00suppressed"
        try:
            row_id = await _insert_result_row(
                db, at, owner_principal, box_col, event_kind, audit_key,
                OUTCOME_SUPPRESSED_BUDGET)
        except _DedupLost:
            return EnqueueResult("duplicate", event_key, None)
        return EnqueueResult("suppressed_budget", event_key, row_id)
    audit_key = event_key
    try:
        row_id = await _insert_result_row(
            db, at, owner_principal, box_col, event_kind, audit_key,
            OUTCOME_SUPPRESSED_BUDGET)
    except _DedupLost:
        # Lost the race: another path coalesced this key first.
        # Nothing was reserved on this path, nothing to release.
        return EnqueueResult("duplicate", event_key, None)
    # INSERT OR IGNORE keeps the counter row's creation idempotent
    # across awaits; the UPDATE then folds this page into the digest.
    await _run(
        db,
        "INSERT OR IGNORE INTO push_digest_state"
        " (owner_principal, window_start, count) VALUES (?, ?, 0)",
        (owner_principal, window_start))
    await _run(
        db,
        "UPDATE push_digest_state SET count = count + 1"
        " WHERE owner_principal = ? AND window_start = ?",
        (owner_principal, window_start))
    return EnqueueResult("suppressed_budget", event_key, row_id)


async def enqueue_page_async(db, *, event_kind, owner_principal, box_id,
                             key_material, now=None):
    """Enqueue one plane-observed paging event (D51, async port).

    Async counterpart of `hosted/push_enqueue.enqueue_page`, reusing
    the sync decision table verbatim (D-EW-2): kind whitelist
    (fail-closed) → key encoding → dedup fast-path (D53; the D57 index
    is the enforcement) → atomic budget reservation (D52) → outbox
    write (D50) or digest coalescing (D54). A lost dedup race surfaces
    as a D57 conflict on the INSERT: the loser releases its reservation
    and returns `duplicate`. Returns an EnqueueResult.

    This is the contract's `enqueue_page` (the async-boundary port
    slice's deliverable, named by #1492's module docstring): the
    `_async` suffix is the in-repo naming precedent (`push_sweep_async`
    style), keeping it distinct from the sync module it ports.

    D2: `owner_principal` must be resolved by the caller from the
    plane's enrollment registry — never a box-asserted value (see the
    module docstring's trust posture).
    """
    if not isinstance(owner_principal, str) or not owner_principal:
        raise ValueError("owner_principal must be a non-empty str")
    event_key = event_key_for(event_kind, owner_principal, box_id,
                              key_material)
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    at = utc_iso(moment)
    window_start = hour_bucket(moment)
    # Digest rows store box_id='' (stable dedup key); the reservation
    # for a digest is owner-only (D52) — no ("box","") shared counter.
    box_col = box_id if box_id is not None else ""

    # D53 — dedup fast path before the budget gate: a replay consumes
    # no budget. (The D57 index enforces it under concurrency.)
    dup = await _first(
        db,
        "SELECT 1 FROM push_send_results"
        " WHERE box_id = ? AND event_kind = ? AND event_key = ? LIMIT 1",
        (box_col, event_kind, event_key))
    if dup is not None:
        return EnqueueResult("duplicate", event_key, None)

    # D52 — one atomic reservation over the applicable scopes.
    if not await reserve_budget_async(db, box_id, owner_principal,
                                      window_start):
        return await _digest_suppressed(
            db, at, owner_principal, box_col, event_kind, event_key,
            window_start)

    # D50 — the outbox work item. device='' until fanout at send (D51).
    try:
        row_id = await _insert_result_row(
            db, at, owner_principal, box_col, event_kind, event_key,
            OUTCOME_QUEUED)
    except _DedupLost:
        # Lost the dedup race (D57): release the just-taken unit and
        # report duplicate — one event, one page, one budget unit.
        await release_reservation_async(db, box_id, owner_principal,
                                        window_start)
        return EnqueueResult("duplicate", event_key, None)
    return EnqueueResult("queued", event_key, row_id)


async def get_counter_async(db, scope_type, scope_id, window_start):
    """Read a budget counter (harness/testing aid, async port)."""
    row = await _first(
        db,
        "SELECT count FROM push_budget_counters"
        " WHERE scope_type = ? AND scope_id = ? AND window_start = ?",
        (scope_type, scope_id, window_start))
    return row["count"] if row else 0


async def get_digest_count_async(db, owner_principal, window_start):
    """Read the digest coalesced-page count (harness/testing aid, async port)."""
    row = await _first(
        db,
        "SELECT count FROM push_digest_state"
        " WHERE owner_principal = ? AND window_start = ?",
        (owner_principal, window_start))
    return row["count"] if row else 0
