"""Tests for hosted/push_enqueue.py (#990 — enqueue boundary + backpressure).

The fixture DDL is verbatim from docs/PUSH_SENDER_SCHEMA_CONTRACT.md
§§1.2–1.4 (the #988 contract) **plus** the D57 partial unique index
(marked below) — the contract text predates it; a follow-up amends the
contract §1.3 and migrate_967_push.sql.
"""

import os
import sqlite3
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import push_enqueue

# --- Fixture DDL: verbatim from docs/PUSH_SENDER_SCHEMA_CONTRACT.md ---

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
CREATE INDEX IF NOT EXISTS idx_push_send_results_dedup
  ON push_send_results(box_id, event_kind, event_key);
CREATE INDEX IF NOT EXISTS idx_push_send_results_tenant
  ON push_send_results(owner_principal, at);
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

# D57 — page-once as a DB invariant. NOT in the #988 contract text
# (predates it); follow-up amends the contract §1.3 + migration.
# The predicate covers 'suppressed_terminal' too (D61 audit
# exactly-once under overlapping sweeps, #1063): the audit key is
# the page key + a U+0000 suffix, so it never collides with page
# or attempt rows. The contract amendment (#1061) must carry this.
DDL_PAGE_ONCE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_push_send_results_page_once
  ON push_send_results(box_id, event_kind, event_key)
  WHERE outcome IN ('queued', 'suppressed_budget', 'suppressed_terminal');
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.executescript(DDL_BUDGET_COUNTERS + DDL_SEND_RESULTS
                    + DDL_DIGEST_STATE + DDL_PAGE_ONCE_INDEX)
    yield c
    c.close()


@pytest.fixture
def dbfile(tmp_path):
    p = str(tmp_path / "enqueue.db")
    c = sqlite3.connect(p)
    c.executescript(DDL_BUDGET_COUNTERS + DDL_SEND_RESULTS
                    + DDL_DIGEST_STATE + DDL_PAGE_ONCE_INDEX)
    c.close()
    yield p


def _row(conn, outcome):
    return conn.execute(
        "SELECT owner_principal, box_id, device, event_kind, event_key,"
        " outcome, http_status, latency_ms FROM push_send_results"
        " WHERE outcome = ?", (outcome,)).fetchall()


# --- Happy path -----------------------------------------------------------

def test_enqueue_happy_path(conn):
    r = push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-1", key_material="aid-1")
    assert r.disposition == "queued"
    assert r.event_key == "box-1\x00aid-1"
    assert r.row_id is not None
    rows = _row(conn, "queued")
    assert len(rows) == 1
    owner, box, device, kind, key, outcome, http_status, latency = rows[0]
    assert (owner, box, device, kind) == ("owner-1", "box-1", "", "approval_filed")
    assert key == "box-1\x00aid-1"
    assert http_status is None and latency is None
    # D52 — one unit on each scope.
    ws = push_enqueue.hour_bucket()
    assert push_enqueue.get_counter(conn, "box", "box-1", ws) == 1
    assert push_enqueue.get_counter(conn, "owner", "owner-1", ws) == 1


def test_digest_event_is_owner_scoped(conn):
    r = push_enqueue.enqueue_page(
        conn, event_kind="digest", owner_principal="owner-1",
        box_id=None, key_material="2026-10-05T16")
    assert r.disposition == "queued"
    assert r.event_key == "owner-1\x002026-10-05T16"
    ws = push_enqueue.hour_bucket()
    # Owner-only reservation (D52): the owner scope is consumed, and no
    # ("box","") shared counter is ever created (no cross-owner bleed).
    assert push_enqueue.get_counter(conn, "owner", "owner-1", ws) == 1
    assert push_enqueue.get_counter(conn, "box", "", ws) == 0
    assert push_enqueue.get_counter(conn, "box", "owner-1", ws) == 0


def test_digest_cross_owner_no_starvation(conn):
    ws = push_enqueue.hour_bucket()
    for i in range(3):
        r = push_enqueue.enqueue_page(
            conn, event_kind="digest", owner_principal="owner-A",
            box_id=None, key_material="2026-10-05T%d" % i)
        assert r.disposition == "queued"
    # Owner B's digest still queues: no shared ("box","") scope to exhaust.
    r = push_enqueue.enqueue_page(
        conn, event_kind="digest", owner_principal="owner-B",
        box_id=None, key_material="2026-10-05T16")
    assert r.disposition == "queued"
    assert push_enqueue.get_counter(conn, "owner", "owner-B", ws) == 1


# --- D53 dedup ------------------------------------------------------------

def test_dedup_replay_consumes_no_budget(conn):
    first = push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-1", key_material="aid-1")
    assert first.disposition == "queued"
    second = push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-1", key_material="aid-1")
    assert second.disposition == "duplicate"
    assert second.row_id is None
    assert len(_row(conn, "queued")) == 1
    assert push_enqueue.get_counter(conn, "box", "box-1", push_enqueue.hour_bucket()) == 1


def test_dedup_is_per_event_key(conn):
    push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-1", key_material="aid-1")
    r = push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-1", key_material="aid-2")
    assert r.disposition == "queued"
    assert push_enqueue.get_counter(conn, "box", "box-1", push_enqueue.hour_bucket()) == 2


# --- D53/D57 dedup race ----------------------------------------------------

def test_dedup_race_same_key_single_page(dbfile):
    """Two concurrent enqueues of the SAME event: exactly one pages.

    The D53 dedup SELECT is only a fast path; the D57 partial unique
    index is the enforcement. The loser must observe `duplicate` and its
    just-taken budget unit must be released — one event, one page, one
    budget unit. Verified non-vacuous: dropping the D57 index lets both
    threads queue (2 rows, 2 units).
    """
    barrier = threading.Barrier(2)
    results = []

    def worker():
        c = sqlite3.connect(dbfile, timeout=10.0)
        barrier.wait()
        try:
            results.append(push_enqueue.enqueue_page(
                c, event_kind="approval_filed", owner_principal="owner-1",
                box_id="box-1", key_material="aid-race"))
        finally:
            c.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    dispositions = sorted(r.disposition for r in results)
    assert dispositions == ["duplicate", "queued"]
    c = sqlite3.connect(dbfile)
    try:
        queued = c.execute(
            "SELECT COUNT(*) FROM push_send_results"
            " WHERE outcome = 'queued'").fetchone()[0]
        assert queued == 1
        ws = push_enqueue.hour_bucket()
        assert push_enqueue.get_counter(c, "box", "box-1", ws) == 1
        assert push_enqueue.get_counter(c, "owner", "owner-1", ws) == 1
    finally:
        c.close()


# --- D52 atomicity: the harness proof -------------------------------------

def test_atomicity_race_bound_1(dbfile):
    """Two concurrent enqueues against a bound of 1: exactly one wins.

    This is the #990 acceptance's explicit harness proof — a
    check-then-increment in two steps lets both threads read under-bound
    and both pass. The counter rows are pre-created so the test exercises
    the pure reservation path (no ensure-INSERT to accidentally serialize
    the threads); verified non-vacuous by neutering reserve_budget to
    check-then-increment without BEGIN IMMEDIATE (both threads then win).
    """
    c0 = sqlite3.connect(dbfile)
    c0.execute("INSERT INTO push_budget_counters VALUES ('box','box-r','2026-10-05T16',0)")
    c0.execute("INSERT INTO push_budget_counters VALUES ('owner','owner-r','2026-10-05T16',0)")
    c0.commit(); c0.close()
    barrier = threading.Barrier(2)
    results = []

    def worker():
        c = sqlite3.connect(dbfile, timeout=10.0)
        barrier.wait()
        try:
            results.append(push_enqueue.reserve_budget(
                c, "box-r", "owner-r", "2026-10-05T16",
                box_bound=1, owner_bound=10))
        finally:
            c.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [False, True]
    c = sqlite3.connect(dbfile)
    try:
        assert push_enqueue.get_counter(c, "box", "box-r", "2026-10-05T16") == 1
    finally:
        c.close()


def test_failed_reservation_leaks_no_budget(conn):
    # Fill the box scope; the owner scope still has room.
    for i in range(3):
        r = push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box-1", key_material="aid-%d" % i)
        assert r.disposition == "queued"
    assert push_enqueue.get_counter(conn, "owner", "owner-1", push_enqueue.hour_bucket()) == 3
    # Direct primitive: box over bound, owner under → False, owner untouched.
    assert push_enqueue.reserve_budget(
        conn, "box-1", "owner-1", push_enqueue.hour_bucket(),
        box_bound=3, owner_bound=10) is False
    assert push_enqueue.get_counter(conn, "box", "box-1", push_enqueue.hour_bucket()) == 3
    assert push_enqueue.get_counter(conn, "owner", "owner-1", push_enqueue.hour_bucket()) == 3


# --- D54 digest coalescing -------------------------------------------------

def test_budget_overflow_coalesces_to_digest(conn):
    for i in range(3):
        r = push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box-1", key_material="aid-%d" % i)
        assert r.disposition == "queued"
    over = push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-1", key_material="aid-3")
    assert over.disposition == "suppressed_budget"
    assert over.event_key == "box-1\x00aid-3"
    # Audit row: suppressed_budget, nothing sent.
    rows = _row(conn, "suppressed_budget")
    assert len(rows) == 1
    assert rows[0][6] is None and rows[0][7] is None  # http_status, latency_ms
    # Digest coalesced; budget counters unchanged (suppressed never took).
    assert push_enqueue.get_digest_count(conn, "owner-1", push_enqueue.hour_bucket()) == 1
    assert push_enqueue.get_counter(conn, "box", "box-1", push_enqueue.hour_bucket()) == 3
    assert push_enqueue.get_counter(conn, "owner", "owner-1", push_enqueue.hour_bucket()) == 3


def test_owner_budget_binds_across_boxes(conn):
    for i in range(10):
        r = push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box-%d" % i, key_material="aid-0")
        assert r.disposition == "queued"
    over = push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-10", key_material="aid-0")
    assert over.disposition == "suppressed_budget"
    assert push_enqueue.get_digest_count(conn, "owner-1", push_enqueue.hour_bucket()) == 1


def test_suppressed_replay_stays_suppressed(conn):
    for i in range(3):
        push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box-1", key_material="aid-%d" % i)
    first = push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-1", key_material="aid-3")
    assert first.disposition == "suppressed_budget"
    replay = push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-1", key_material="aid-3")
    assert replay.disposition == "duplicate"
    assert push_enqueue.get_digest_count(conn, "owner-1", push_enqueue.hour_bucket()) == 1


# --- D56 reservation lifecycle ---------------------------------------------

def test_release_reservation(conn):
    ws = push_enqueue.hour_bucket()
    assert push_enqueue.reserve_budget(conn, "box-1", "owner-1", ws) is True
    push_enqueue.release_reservation(conn, "box-1", "owner-1", ws)
    assert push_enqueue.get_counter(conn, "box", "box-1", ws) == 0
    assert push_enqueue.get_counter(conn, "owner", "owner-1", ws) == 0


def test_release_never_goes_negative(conn):
    ws = push_enqueue.hour_bucket()
    push_enqueue.release_reservation(conn, "box-1", "owner-1", ws)
    push_enqueue.release_reservation(conn, "box-1", "owner-1", ws)
    assert push_enqueue.get_counter(conn, "box", "box-1", ws) == 0
    assert push_enqueue.get_counter(conn, "owner", "owner-1", ws) == 0


# --- Fail-closed gates -----------------------------------------------------

def test_no_page_kinds_are_rejected_loudly(conn):
    for kind in ("decided", "expired", "", "approval_filed "):
        with pytest.raises(ValueError):
            push_enqueue.enqueue_page(
                conn, event_kind=kind, owner_principal="owner-1",
                box_id="box-1", key_material="aid-1")


def test_key_separator_injection_rejected(conn):
    with pytest.raises(ValueError):
        push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box-1", key_material="aid\x00forged")
    with pytest.raises(ValueError):
        push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box\x00evil", key_material="aid-1")
    with pytest.raises(ValueError):
        push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="",
            box_id="box-1", key_material="aid-1")


def test_vapid_sub_pinned():
    assert push_enqueue.VAPID_SUB == "mailto:hosted@sparkvm.dev"


def test_hour_bucket_format():
    from datetime import datetime, timezone
    assert push_enqueue.hour_bucket(
        datetime(2026, 10, 5, 16, 29, tzinfo=timezone.utc)) == "2026-10-05T16"
