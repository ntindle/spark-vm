"""Tests for hosted/push_gc.py (#1058 — 90-day retention GC).

The fixture DDL is the #988 contract (§§1.1–1.4) for the four push
tables. Every test pins one D90–D95 decision; non-vacuity is proven by
neutering the source on scratch copies (each neuter fails exactly its
target test).
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import push_enqueue, push_gc

NOW = datetime(2026, 10, 11, 2, 30, tzinfo=timezone.utc)

DDL_SUBSCRIPTIONS = """
CREATE TABLE IF NOT EXISTS push_subscriptions (
  owner_principal TEXT NOT NULL,
  box_id          TEXT NOT NULL,
  device          TEXT NOT NULL,
  endpoint        TEXT NOT NULL,
  p256dh          BLOB NOT NULL,
  auth            BLOB NOT NULL,
  p256dh_nonce    BLOB NOT NULL,
  auth_nonce      BLOB NOT NULL,
  data_key_version TEXT NOT NULL DEFAULT 'v1',
  vapid_key_id    TEXT NOT NULL DEFAULT 'v1',
  added_by        TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'live',
  created_at      TEXT NOT NULL,
  last_page_at    TEXT,
  PRIMARY KEY (owner_principal, box_id, device)
);
"""

DDL_BUDGET_COUNTERS = """
CREATE TABLE IF NOT EXISTS push_budget_counters (
  scope_type   TEXT NOT NULL,
  scope_id     TEXT NOT NULL,
  window_start TEXT NOT NULL,
  count        INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (scope_type, scope_id, window_start)
);
"""

DDL_SEND_RESULTS = """
CREATE TABLE IF NOT EXISTS push_send_results (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  at              TEXT NOT NULL,
  owner_principal TEXT NOT NULL,
  box_id          TEXT NOT NULL,
  device          TEXT NOT NULL,
  event_kind      TEXT NOT NULL,
  event_key       TEXT NOT NULL,
  outcome         TEXT NOT NULL,
  http_status     INTEGER,
  latency_ms      REAL,
  sent_at         REAL,
  vapid_key_id    TEXT
);
"""

DDL_DIGEST_STATE = """
CREATE TABLE IF NOT EXISTS push_digest_state (
  owner_principal TEXT NOT NULL,
  window_start    TEXT NOT NULL,
  count           INTEGER NOT NULL DEFAULT 0,
  enqueued_at     TEXT,
  PRIMARY KEY (owner_principal, window_start)
);
"""


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in (DDL_SUBSCRIPTIONS, DDL_BUDGET_COUNTERS, DDL_SEND_RESULTS,
                DDL_DIGEST_STATE):
        c.executescript(ddl)
    yield c
    c.close()


def _bucket(days_ago):
    return push_enqueue.hour_bucket(NOW - timedelta(days=days_ago))


def _iso(days_ago):
    return (NOW - timedelta(days=days_ago)).isoformat()


def _seed(conn):
    """One 91d-old row and one 89d-old row per GC'd table; old ones must
    die, young ones must survive (D91's boundary is strictly < cutoff)."""
    conn.execute(
        "INSERT INTO push_budget_counters (scope_type, scope_id,"
        " window_start, count) VALUES"
        " ('owner', 'owner-old', ?, 3), ('owner', 'owner-young', ?, 2)",
        (_bucket(91), _bucket(89)))
    conn.execute(
        "INSERT INTO push_digest_state (owner_principal, window_start,"
        " count) VALUES ('owner-old', ?, 5), ('owner-young', ?, 2)",
        (_bucket(91), _bucket(89)))
    conn.execute(
        "INSERT INTO push_send_results (at, owner_principal, box_id,"
        " device, event_kind, event_key, outcome) VALUES"
        " (?, 'owner', 'box', 'dev', 'approval_filed', 'k-old',"
        " 'accepted'),"
        " (?, 'owner', 'box', 'dev', 'approval_filed', 'k-young',"
        " 'accepted')",
        (_iso(91), _iso(89)))
    conn.commit()


def _count(conn, table):
    return conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]


def test_gc_deletes_old_keeps_young(conn):
    _seed(conn)
    out = push_gc.gc_push_tables(conn, now=NOW)
    assert out == {"push_budget_counters": 1, "push_digest_state": 1,
                   "push_send_results": 1}
    assert conn.execute(
        "SELECT scope_id FROM push_budget_counters").fetchall() == [
        ("owner-young",)]
    assert conn.execute(
        "SELECT owner_principal FROM push_digest_state").fetchall() == [
        ("owner-young",)]
    assert conn.execute(
        "SELECT event_key FROM push_send_results").fetchall() == [
        ("k-young",)]


def test_gc_boundary_is_strictly_less_than(conn):
    """A row exactly at the 90-day cutoff survives (D91: < cutoff)."""
    conn.execute(
        "INSERT INTO push_budget_counters (scope_type, scope_id,"
        " window_start, count) VALUES ('owner', 'o', ?, 1)",
        (_bucket(90),))
    conn.execute(
        "INSERT INTO push_send_results (at, owner_principal, box_id,"
        " device, event_kind, event_key, outcome) VALUES"
        " (?, 'owner', 'box', 'dev', 'approval_filed', 'k', 'accepted')",
        (_iso(90),))
    conn.commit()
    out = push_gc.gc_push_tables(conn, now=NOW)
    assert out["push_budget_counters"] == 0
    assert out["push_send_results"] == 0
    assert _count(conn, "push_budget_counters") == 1
    assert _count(conn, "push_send_results") == 1


def test_gc_never_deletes_queued(conn):
    """A 91-day-old 'queued' outbox row survives; its completed
    neighbor dies (D92)."""
    conn.execute(
        "INSERT INTO push_send_results (at, owner_principal, box_id,"
        " device, event_kind, event_key, outcome) VALUES"
        " (?, 'owner', 'box', 'dev', 'approval_filed', 'k-queued',"
        " 'queued'),"
        " (?, 'owner', 'box', 'dev', 'approval_filed', 'k-done',"
        " 'accepted')",
        (_iso(91), _iso(91)))
    conn.commit()
    out = push_gc.gc_push_tables(conn, now=NOW)
    assert out["push_send_results"] == 1
    assert conn.execute(
        "SELECT event_key FROM push_send_results").fetchall() == [
        ("k-queued",)]


def test_gc_leaves_subscriptions_alone(conn):
    """live and dead_410 rows are never touched (D93)."""
    now_iso = NOW.isoformat()
    conn.execute(
        "INSERT INTO push_subscriptions (owner_principal, box_id, device,"
        " endpoint, p256dh, auth, p256dh_nonce, auth_nonce, added_by,"
        " status, created_at) VALUES"
        " ('owner', 'box', 'phone', 'https://x/', ?, ?, ?, ?, 'key',"
        " 'live', ?),"
        " ('owner', 'box', 'tablet', 'https://x/', ?, ?, ?, ?, 'key',"
        " 'dead_410', ?)",
        (b"p", b"a", b"pn", b"an", now_iso) * 2)
    conn.commit()
    out = push_gc.gc_push_tables(conn, now=NOW)
    assert "push_subscriptions" not in out
    assert _count(conn, "push_subscriptions") == 2


def test_gc_is_idempotent(conn):
    _seed(conn)
    first = push_gc.gc_push_tables(conn, now=NOW)
    assert sum(first.values()) == 3
    second = push_gc.gc_push_tables(conn, now=NOW)
    assert second == {"push_budget_counters": 0, "push_digest_state": 0,
                      "push_send_results": 0}


def test_gc_batches_deletes(conn):
    """batch_size=2 over 5 old rows still deletes all 5 (D95)."""
    for i in range(5):
        conn.execute(
            "INSERT INTO push_budget_counters (scope_type, scope_id,"
            " window_start, count) VALUES ('owner', ?, ?, 1)",
            ("o%d" % i, _bucket(91)))
    conn.commit()
    out = push_gc.gc_push_tables(conn, now=NOW, batch_size=2)
    assert out["push_budget_counters"] == 5
    assert _count(conn, "push_budget_counters") == 0


def test_gc_future_window_survives(conn):
    """A digest row for a future hour bucket is never old (D91)."""
    conn.execute(
        "INSERT INTO push_digest_state (owner_principal, window_start,"
        " count) VALUES ('owner', ?, 1)",
        (push_enqueue.hour_bucket(NOW + timedelta(hours=2)),))
    conn.commit()
    out = push_gc.gc_push_tables(conn, now=NOW)
    assert out["push_digest_state"] == 0
    assert _count(conn, "push_digest_state") == 1


def test_gc_retention_days_param(conn):
    """A custom bound applies to every table uniformly."""
    conn.execute(
        "INSERT INTO push_budget_counters (scope_type, scope_id,"
        " window_start, count) VALUES ('owner', 'o', ?, 1)",
        (_bucket(8),))
    conn.execute(
        "INSERT INTO push_send_results (at, owner_principal, box_id,"
        " device, event_kind, event_key, outcome) VALUES"
        " (?, 'owner', 'box', 'dev', 'approval_filed', 'k', 'accepted')",
        (_iso(8),))
    conn.commit()
    out = push_gc.gc_push_tables(conn, now=NOW, retention_days=7)
    assert out == {"push_budget_counters": 1, "push_digest_state": 0,
                   "push_send_results": 1}


def test_gc_rejects_bad_params(conn):
    with pytest.raises(ValueError):
        push_gc.gc_push_tables(conn, now=NOW, retention_days=0)
    with pytest.raises(ValueError):
        push_gc.gc_push_tables(conn, now=NOW, retention_days=-1)
    with pytest.raises(ValueError):
        push_gc.gc_push_tables(conn, now=NOW, retention_days=True)
    with pytest.raises(ValueError):
        push_gc.gc_push_tables(conn, now=NOW, retention_days="90")
    with pytest.raises(ValueError):
        push_gc.gc_push_tables(conn, now=NOW, retention_days=90.5)
    with pytest.raises(ValueError):
        push_gc.gc_push_tables(conn, now=NOW, batch_size=0)
    with pytest.raises(ValueError):
        push_gc.gc_push_tables(conn, now=NOW, batch_size=True)


def test_gc_logs_counts(conn):
    lines = []
    _seed(conn)
    out = push_gc.gc_push_tables(conn, now=NOW, log=lines.append)
    assert out == {"push_budget_counters": 1, "push_digest_state": 1,
                   "push_send_results": 1}
    assert len(lines) == 1
    assert "retention_days=90" in lines[0] and "total=3" in lines[0]


def test_gc_writer_at_shape_matches_cutoff(conn):
    """The enqueue writer's `at` shape is byte-identical to the shape the
    GC's lexicographic `at < cutoff` comparison uses (retention-shape
    contract, pinned in the module docstring): a writer emitting any
    other ISO shape (naive, `Z`-suffixed) silently corrupts retention —
    premature audit-trail deletion or retention silently stopping. The
    row must also actually be collected at 91 days, tying the shape pin
    to the retention behavior."""
    t = NOW - timedelta(days=91)
    push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-1", key_material="aid-shape", now=t)
    conn.commit()
    stored = conn.execute(
        "SELECT at FROM push_send_results WHERE event_key = ?",
        ("box-1\x00aid-shape",)).fetchone()[0]
    assert stored == t.astimezone(timezone.utc).isoformat()
    assert stored == push_gc._instant_cutoff_iso(t + timedelta(days=91), 91)
    # Flip to a terminal outcome (the sender loop's delivery transition):
    # the 'queued' outbox work item is immortal under the GC by design
    # (D92). The `at` value above is still exactly what the writer wrote.
    conn.execute("UPDATE push_send_results SET outcome = 'accepted'"
                 " WHERE event_key = ?", ("box-1\x00aid-shape",))
    conn.commit()
    out = push_gc.gc_push_tables(conn, now=NOW)
    assert out["push_send_results"] == 1
    assert _count(conn, "push_send_results") == 0
