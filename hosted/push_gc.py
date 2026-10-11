"""90-day retention GC for the push-sender D1 tables (#1058).

Three of the four push tables (``push_budget_counters``,
``push_send_results``, ``push_digest_state`` — the #988 schema contract
§§1.2–1.4) accumulate rows forever: budget buckets are never read after
their hour, digest rows never after 90 days, send-result rows are an
audit trail. (``push_subscriptions`` is the fourth table; it is
deliberately excluded — D93.) Without a bound this is unbounded D1
growth on the plane.

``gc_push_tables`` is the in-repo build slice: a portable, idempotent,
batched sweeper the plane worker's scheduled handler calls (the plane
workspace owns the cron trigger + a manual ops trigger on the #1013
pattern — the deploy half, not this module).

Decisions (continuing the push lane's D-series; D89 was the last pin):

- **D90. GC is a runtime sweeper, not a migration.** The 90-day bound is
  enforced by a recurring sweep, not a one-shot DELETE — the tables
  refill every hour. No schema change (DDL frozen per #988): the
  sweeper only deletes.
- **D91. What the GC deletes.** ``push_budget_counters`` and
  ``push_digest_state`` rows whose ``window_start`` (hour bucket,
  ``YYYY-MM-DDTHH`` UTC) is older than 90 days; ``push_send_results``
  rows whose ``at`` (ISO UTC) is older than 90 days. The comparison is
  strictly ``< cutoff``: a row exactly at the 90-day boundary stays.
- **D92. ``queued`` rows are immortal under the GC.** A ``'queued'``
  outcome is the D50 outbox work item — it holds a live D10
  reservation and a page the owner never got. Deleting it would
  silently drop a page, violating the lane's "never a lost page"
  posture (D56f). The outbox work item's lifetime is the sender
  loop's and #968's problem (the D81 follow-up: bound or expire
  parked pages), not retention's — so the GC predicate is
  ``outcome != 'queued'``. An audit row for a 91-day-old *completed*
  page may go while its outbox row, had it still existed, would
  stay; that asymmetry is the D81 follow-up's to resolve.
- **D93. ``push_subscriptions`` is not GC'd at all.** Unsubscribe
  deletes the row outright (§1.1), so the only accumulating rows are
  ``dead_410`` tombstones — bounded by device churn (owner-actioned),
  not by page volume, which is what makes the other three tables
  unbounded. The tombstone's whole purpose is the dashboard's
  "died vs never subscribed" distinction and #968's re-subscribe
  prompt; deleting it would race the dashboard, and a re-subscribe
  is a fresh row with fresh key material anyway. Persisting dead
  tombstones is the answer to the issue's question.
- **D94. Replay-after-retention.** Deleting ``suppressed_budget`` /
  ``suppressed_terminal`` rows after 90 days re-opens the D53 dedup
  window for very old replays: a filing replayed after its rows aged
  out can re-page. Accepted — retention is a bounded-memory dedup,
  and the #1013 precedent has the same property. The D57 index only
  ever covered the live window anyway.
- **D95. Batched, committed per batch, idempotent.** One
  ``DELETE ... LIMIT <batch_size>`` per table per round, committed
  after each batch (D1 write limits); a second run deletes nothing
  new. Termination and the returned counts are derived from row
  existence (before/after COUNT), never from ``cursor.rowcount`` — a
  D1 wrapper reporting -1 for DELETEs can neither spin the loop
  nor corrupt the ops-log counts. Returns per-table deleted counts
  so the plane logs the sweep where the ops console can see it.

- **Retention-shape contract (pinned).** The ``at < cutoff`` comparison
  is lexicographic TEXT, so it is chronological only while every writer
  of ``push_send_results.at`` emits the same string shape —
  ``moment.astimezone(timezone.utc).isoformat()`` (``+00:00``-suffixed).
  The render step is single-sourced in ``push_enqueue.utc_iso``: every
  in-repo ``at`` writer (``push_enqueue.enqueue_page``; ``push_events``
  reminder/suppressed-terminal writes; ``push_send_loop`` attempt rows
  (``_insert_attempt_row``) and suppressed_terminal/dead-letter audit
  rows (``_insert_audit_row``), both sharing the one helper-rendered
  ``at``) and this module's own cutoff render go through it, so the
  shape can never drift by independent edits; ``push_events._quiet_window_start``
  pins the same assumption for its ``MAX(at)``. A writer bypassing the
  helper with a different shape (naive ISO, ``Z`` suffix, epoch) silently
  corrupts retention in either direction: premature deletion of the
  audit trail (which also re-opens the D94 replay window early), or
  retention silently stopping and unbounded D1 growth (which delays
  D94's re-opening). New writers must use ``utc_iso``;
  ``test_utc_iso_byte_shape`` and
  ``test_gc_writer_at_shape_matches_cutoff`` enforce it.

Plane seams (injected — this module never sees a Worker secret, a data
key, or a box token):

- ``conn`` — a DB-API connection on the live D1 database (the fixture
  DDL in the test module is the #988 contract §§1.2–1.4 verbatim).
  Commits happen per batch inside this module; the caller must not
  hold an open transaction across the call. Termination and the
  returned counts never depend on ``cursor.rowcount`` (D95), so the
  driver needs no rowcount guarantees.
- ``log`` — optional ``callable(str)``; defaults to a module logger.
  One line per sweep with the per-table deleted counts.
- ``now`` — optional aware datetime (the sweep's clock); naive values
  are assumed UTC, the same convention as ``push_enqueue.hour_bucket``.
"""

import logging
from datetime import datetime, timedelta, timezone

from hosted import push_enqueue

_LOG = logging.getLogger("sparkvm.push_gc")

DEFAULT_RETENTION_DAYS = 90
DEFAULT_BATCH_SIZE = 1000

# Tables the GC owns, in the contract's § order. push_subscriptions is
# deliberately absent (D93).
_GC_TABLES = ("push_budget_counters", "push_digest_state",
              "push_send_results")


def _window_cutoff(now, retention_days):
    """Hour-bucket cutoff: window_start < this is older than retention."""
    return push_enqueue.hour_bucket(now - timedelta(days=retention_days))


def _instant_cutoff_iso(now, retention_days):
    """ISO-UTC instant cutoff for push_send_results.at."""
    return push_enqueue.utc_iso(now - timedelta(days=retention_days))


def _delete_batches(conn, table, predicate, params, batch_size):
    """DELETE in LIMIT-bounded batches until no rows match.

    Returns the total deleted. One commit per batch (``with conn``).
    Termination and counts are derived from row existence, never from
    ``cursor.rowcount`` — a D1 DB-API wrapper that reports -1 for
    DELETEs must not be able to spin this loop forever, and the
    returned counts must stay honest. Concurrent inserts cannot
    corrupt the count: the predicates are time-based, so a fresh
    insert never matches an old-row predicate.
    """
    total = 0
    while True:
        with conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM %s WHERE %s" % (table, predicate),
                params).fetchone()[0]
            if before == 0:
                break
            conn.execute(
                "DELETE FROM %s WHERE %s LIMIT ?" % (table, predicate),
                params + (batch_size,))
            after = conn.execute(
                "SELECT COUNT(*) FROM %s WHERE %s" % (table, predicate),
                params).fetchone()[0]
        total += before - after
    return total


def gc_push_tables(conn, *, now=None, retention_days=DEFAULT_RETENTION_DAYS,
                   batch_size=DEFAULT_BATCH_SIZE, log=None):
    """Run one 90-day retention sweep over the push tables (D90–D95).

    Deletes budget buckets and digest-state rows older than
    ``retention_days`` (D91), and send-result rows older than
    ``retention_days`` except the ``'queued'`` outbox work items (D92).
    ``push_subscriptions`` is untouched (D93). Batched (D95),
    idempotent, and safe to re-run.

    Returns ``{table: deleted_count}`` for the ops log.
    """
    if not isinstance(retention_days, int) or isinstance(
            retention_days, bool) or retention_days <= 0:
        raise ValueError(
            "retention_days must be a positive int, not %r"
            % (retention_days,))
    if not isinstance(batch_size, int) or isinstance(
            batch_size, bool) or batch_size <= 0:
        raise ValueError(
            "batch_size must be a positive int, not %r" % (batch_size,))
    emit = log if log is not None else _LOG.info
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    window_cutoff = _window_cutoff(moment, retention_days)
    instant_cutoff = _instant_cutoff_iso(moment, retention_days)

    # Per-table age predicates, in the contract's § order (D91/D92).
    predicates = {
        "push_budget_counters": ("window_start < ?", (window_cutoff,)),
        "push_digest_state": ("window_start < ?", (window_cutoff,)),
        "push_send_results": (
            "at < ? AND outcome != 'queued'", (instant_cutoff,)),
    }
    deleted = {}
    for table in _GC_TABLES:
        predicate, params = predicates[table]
        deleted[table] = _delete_batches(conn, table, predicate, params,
                                         batch_size)

    total = sum(deleted.values())
    emit("push_gc: retention_days=%d deleted=%s total=%d"
         % (retention_days, deleted, total))
    return deleted
