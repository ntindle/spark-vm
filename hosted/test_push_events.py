"""Tests for hosted/push_events.py (#969 — GP3 event-to-push mapping).

The fixture DDL is verbatim from docs/PUSH_SENDER_SCHEMA_CONTRACT.md
§§1.2–1.4 (the #988 contract) **plus** the D57 partial unique index
(marked below) — identical to test_push_enqueue.py's fixture, since
this module is tested against the real enqueue boundary (#990):
page-once, the D10 budget, and digest coalescing are proved here, not
mocked.
"""

import os
import sqlite3
import sys
import threading
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import push_enqueue, push_events

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


def _outcomes(conn, event_kind=None):
    q = "SELECT event_kind, outcome FROM push_send_results"
    args = ()
    if event_kind is not None:
        q += " WHERE event_kind = ?"
        args = (event_kind,)
    return conn.execute(q, args).fetchall()


def _record(created_at, ttl_seconds=3600, terminal=False):
    return {"aid": "aid-1",
            "created_at": created_at.isoformat(),
            "ttl_seconds": ttl_seconds,
            "terminal": terminal}


def _utcnow():
    return datetime.now(timezone.utc)


# --- approval_filed ------------------------------------------------------

def test_approval_filed_queued_then_page_once(conn):
    r1 = push_events.on_approval_filed(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1")
    assert r1.disposition == "queued"
    assert r1.detail.event_key == "box-1\x00aid-1"
    r2 = push_events.on_approval_filed(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1")
    assert r2.disposition == "duplicate"
    assert r2.detail is not None
    rows = _outcomes(conn, "approval_filed")
    assert rows == [("approval_filed", "queued")]


def test_approval_filed_flooding_is_budget_bounded(conn):
    # #969 acceptance: a hostile box filing at the endpoint's admission
    # rate must not convert filings into pages at the same rate.
    results = [push_events.on_approval_filed(
        conn, box_id="box-1", owner_principal="owner-1",
        aid="aid-%d" % i) for i in range(6)]
    dispositions = [r.disposition for r in results]
    assert dispositions.count("queued") == 3          # D10 box bound
    assert dispositions.count("suppressed_budget") == 3
    # The overflow coalesced into the digest (D54), not dropped.
    assert push_enqueue.get_digest_count(
        conn, "owner-1", push_enqueue.hour_bucket()) == 3
    # ...but the owner's own other box still has budget (per-box scope).
    r = push_events.on_approval_filed(
        conn, box_id="box-2", owner_principal="owner-1", aid="aid-x")
    assert r.disposition == "queued"


# --- token_expiry_warning --------------------------------------------------

def test_token_warning_once_per_generation(conn):
    r1 = push_events.on_token_expiry_warning(
        conn, box_id="box-1", owner_principal="owner-1",
        token_hash="hash-a")
    assert r1.disposition == "queued"
    r2 = push_events.on_token_expiry_warning(
        conn, box_id="box-1", owner_principal="owner-1",
        token_hash="hash-a")
    assert r2.disposition == "duplicate"
    # Rotation (hash change) is definitionally a new generation (D13):
    # the warning key resets.
    r3 = push_events.on_token_expiry_warning(
        conn, box_id="box-1", owner_principal="owner-1",
        token_hash="hash-b")
    assert r3.disposition == "queued"


# --- box_revoked -----------------------------------------------------------

def test_box_revoked_pages_once(conn):
    r1 = push_events.on_box_revoked(
        conn, box_id="box-1", owner_principal="owner-1",
        revoked_at="2026-10-05T17:00:00+00:00")
    assert r1.disposition == "queued"
    r2 = push_events.on_box_revoked(
        conn, box_id="box-1", owner_principal="owner-1",
        revoked_at="2026-10-05T17:00:00+00:00")
    assert r2.disposition == "duplicate"


@pytest.mark.parametrize("bad_ts", [
    "not-a-timestamp",
    "2026-10-05",          # bare date: no time component, could repeat
    "1699999999",          # epoch int as string is not ISO-8601
    "2026-10-05T",         # T with no time
    "",
])
def test_box_revoked_rejects_non_timestamp(conn, bad_ts):
    # The module's identity claim ("a timestamp never repeats") is
    # enforced: a constant or date-only string would silently collapse
    # distinct revocations into one page.
    with pytest.raises(ValueError):
        push_events.on_box_revoked(
            conn, box_id="box-1", owner_principal="owner-1",
            revoked_at=bad_ts)
    assert _outcomes(conn, "box_revoked") == []


# --- heartbeat_stale ---------------------------------------------------------

def test_heartbeat_stale_quiet_period(conn):
    t0 = _utcnow()
    r1 = push_events.on_heartbeat_stale(
        conn, box_id="box-1", owner_principal="owner-1",
        stale_epoch="epoch-1", now=t0)
    assert r1.disposition == "queued"
    # Same epoch replays dedup (page-once per stale-epoch).
    r2 = push_events.on_heartbeat_stale(
        conn, box_id="box-1", owner_principal="owner-1",
        stale_epoch="epoch-1", now=t0 + timedelta(minutes=5))
    assert r2.disposition == "duplicate"
    # A new epoch inside the 4h quiet window is suppressed — no row,
    # no budget consumed (D62).
    before = push_enqueue.get_counter(
        conn, "box", "box-1", push_enqueue.hour_bucket(t0))
    r3 = push_events.on_heartbeat_stale(
        conn, box_id="box-1", owner_principal="owner-1",
        stale_epoch="epoch-2", now=t0 + timedelta(hours=1))
    assert r3.disposition == "suppressed_quiet_period"
    assert r3.detail is None
    assert _outcomes(conn, "heartbeat_stale") == [
        ("heartbeat_stale", "queued")]
    after = push_enqueue.get_counter(
        conn, "box", "box-1", push_enqueue.hour_bucket(t0))
    assert after == before
    # After the quiet window, a new epoch pages again — including at
    # exactly the 4h boundary ("do not page *for* 4 hours").
    r4 = push_events.on_heartbeat_stale(
        conn, box_id="box-1", owner_principal="owner-1",
        stale_epoch="epoch-3", now=t0 + timedelta(hours=4))
    assert r4.disposition == "queued"


def test_heartbeat_stale_suppressed_budget_does_not_arm_quiet(conn):
    # Exhaust the box budget with approvals, then derive staleness:
    # the stale page is suppressed into the digest (never buzzed)...
    for i in range(3):
        push_events.on_approval_filed(
            conn, box_id="box-1", owner_principal="owner-1",
            aid="aid-%d" % i)
    r = push_events.on_heartbeat_stale(
        conn, box_id="box-1", owner_principal="owner-1",
        stale_epoch="epoch-1")
    assert r.disposition == "suppressed_budget"
    # ...so the quiet clock never started (D62): no queued/accepted
    # stale page.
    assert push_events.last_heartbeat_stale_page_at(conn, "box-1") is None


def test_heartbeat_stale_quiet_survives_delivery(conn):
    # Architecture B1: the sender loop DELETEs the queued work-item row
    # on the terminal attempt (D50) — the F7 quiet window must be
    # armed by the `accepted` row, not evaporate on delivery.
    t0 = _utcnow()
    r1 = push_events.on_heartbeat_stale(
        conn, box_id="box-1", owner_principal="owner-1",
        stale_epoch="epoch-1", now=t0)
    assert r1.disposition == "queued"
    # Simulate the sender loop's terminal transaction: one `accepted`
    # attempt row per device, then DELETE the queued work-item row.
    with conn:
        conn.execute(
            "INSERT INTO push_send_results (at, owner_principal, box_id,"
            " device, event_kind, event_key, outcome, http_status,"
            " latency_ms, sent_at, vapid_key_id)"
            " VALUES (?, ?, ?, 'dev-1', ?, ?, 'accepted', 201, 42.0,"
            " ?, 'key-1')",
            (t0.isoformat(), "owner-1", "box-1", "heartbeat_stale",
             r1.detail.event_key, t0.timestamp()))
        conn.execute("DELETE FROM push_send_results WHERE id = ?",
                     (r1.detail.row_id,))
    assert push_events.last_heartbeat_stale_page_at(conn, "box-1") == t0
    # A flap-derived new epoch 1h after delivery is still suppressed.
    r2 = push_events.on_heartbeat_stale(
        conn, box_id="box-1", owner_principal="owner-1",
        stale_epoch="epoch-2", now=t0 + timedelta(hours=1))
    assert r2.disposition == "suppressed_quiet_period"


# --- reminder ------------------------------------------------------------------

def test_reminder_ttl_floor(conn):
    now = _utcnow()
    rec = lambda ttl: _record(now - timedelta(hours=2), ttl_seconds=ttl)
    r = push_events.maybe_enqueue_reminder(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
        get_record=lambda aid: rec(299), now=now)
    assert r.disposition == "no_reminder_ttl"
    # The 300s floor itself qualifies (due: created+150s < now).
    r2 = push_events.maybe_enqueue_reminder(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
        get_record=lambda aid: rec(300), now=now)
    assert r2.disposition == "queued"


def test_reminder_not_due_yet(conn):
    now = _utcnow()
    rec = _record(now - timedelta(minutes=10), ttl_seconds=3600)
    r = push_events.maybe_enqueue_reminder(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
        get_record=lambda aid: rec, now=now)
    assert r.disposition == "reminder_not_due"
    assert _outcomes(conn, "reminder") == []


def test_reminder_due_pages_once(conn):
    now = _utcnow()
    rec = _record(now - timedelta(minutes=40), ttl_seconds=3600)
    get = lambda aid: rec
    r1 = push_events.maybe_enqueue_reminder(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
        get_record=get, now=now)
    assert r1.disposition == "queued"
    # A second gate-1 pass for the same approval dedups (D60).
    r2 = push_events.maybe_enqueue_reminder(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
        get_record=get, now=now)
    assert r2.disposition == "duplicate"


def test_reminder_terminal_record_is_superseded_with_audit(conn):
    # #969 acceptance: a decided approval never gets a post-decision
    # reminder — and the lease loss is audited (D61), not silent.
    t0 = _utcnow()
    r0 = push_events.on_approval_filed(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
        now=t0)
    assert r0.disposition == "queued"
    rec = _record(t0 - timedelta(minutes=40), ttl_seconds=3600,
                  terminal=True)
    r = push_events.maybe_enqueue_reminder(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
        get_record=lambda aid: rec, now=t0 + timedelta(minutes=5))
    assert r.disposition == "superseded_terminal"
    rows = conn.execute(
        "SELECT event_kind, outcome, device, http_status, latency_ms,"
        " sent_at, vapid_key_id FROM push_send_results"
        " WHERE event_kind = 'reminder'").fetchall()
    # Exactly one reminder row: the D56e-shaped audit row — no page.
    assert len(rows) == 1
    kind, outcome, device, http_status, latency, sent_at, vapid = rows[0]
    assert outcome == "suppressed_terminal"
    assert device == ""
    assert http_status is None and latency is None
    assert sent_at is None and vapid is None
    # The audit row carries its own key (page key + U+0000 suffix), so
    # the boundary's outcome-blind dedup can never mistake a later
    # page attempt for a duplicate of this audit row.
    key = conn.execute(
        "SELECT event_key FROM push_send_results"
        " WHERE event_kind = 'reminder'").fetchone()[0]
    assert key == "box-1\x00aid-1\x00superseded"


def test_reminder_terminal_audit_is_idempotent(conn):
    # The D9 sweep is periodic: a terminal approval must accrue exactly
    # one audit row no matter how many passes observe it.
    t0 = _utcnow()
    rec = _record(t0 - timedelta(minutes=40), ttl_seconds=3600,
                  terminal=True)
    get = lambda aid: rec
    for _ in range(3):
        r = push_events.maybe_enqueue_reminder(
            conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
            get_record=get, now=t0)
        assert r.disposition == "superseded_terminal"
    rows = _outcomes(conn, "reminder")
    assert rows == [("reminder", "suppressed_terminal")]


@pytest.mark.parametrize("terminal,expected", [
    (False, "queued"),
    (True, "superseded_terminal"),
    (0, "queued"),                  # SQLite boolean-expression form
    (1, "superseded_terminal"),     # (Security B2)
])
def test_reminder_terminal_coercion(conn, terminal, expected):
    now = _utcnow()
    rec = _record(now - timedelta(minutes=40), ttl_seconds=3600)
    rec["terminal"] = terminal
    r = push_events.maybe_enqueue_reminder(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
        get_record=lambda aid: rec, now=now)
    assert r.disposition == expected


@pytest.mark.parametrize("bad_terminal", [2, -1, "1", "true", None, 1.0])
def test_reminder_terminal_rejects_non_bool_int(conn, bad_terminal):
    now = _utcnow()
    rec = _record(now - timedelta(minutes=40), ttl_seconds=3600)
    rec["terminal"] = bad_terminal
    with pytest.raises(ValueError):
        push_events.maybe_enqueue_reminder(
            conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
            get_record=lambda aid: rec, now=now)


def test_reminder_naive_created_at_assumed_utc(conn):
    # Security N4: the naive=UTC convention is pinned by this test —
    # a naive-local writer would silently shift reminder_at.
    now = _utcnow()
    naive = (now - timedelta(minutes=40)).replace(tzinfo=None)
    rec = {"aid": "aid-1", "created_at": naive.isoformat(),
           "ttl_seconds": 3600, "terminal": False}
    r = push_events.maybe_enqueue_reminder(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
        get_record=lambda aid: rec, now=now)
    assert r.disposition == "queued"


def test_reminder_no_record(conn):
    r = push_events.maybe_enqueue_reminder(
        conn, box_id="box-1", owner_principal="owner-1", aid="aid-9",
        get_record=lambda aid: None)
    assert r.disposition == "no_record"
    assert _outcomes(conn, "reminder") == []


@pytest.mark.parametrize("make_bad", [
    lambda aid: {"aid": aid, "created_at": "not-a-time",
                 "ttl_seconds": 3600, "terminal": False},
    lambda aid: {"aid": aid, "created_at": "2026-10-05",
                 "ttl_seconds": 3600, "terminal": False},
    lambda aid: {"aid": aid,
                 "created_at": datetime.now(timezone.utc).isoformat(),
                 "ttl_seconds": "3600", "terminal": False},
    lambda aid: {"aid": aid,
                 "created_at": datetime.now(timezone.utc).isoformat(),
                 "ttl_seconds": 0, "terminal": False},
    lambda aid: {"aid": aid,
                 "created_at": datetime.now(timezone.utc).isoformat(),
                 "ttl_seconds": 3600},
    lambda aid: {"aid": aid,
                 "created_at": datetime.now(timezone.utc).isoformat(),
                 "ttl_seconds": 3600, "terminal": "no"},
    lambda aid: "not-a-dict",
])
def test_reminder_corrupt_record_fail_loud(conn, make_bad):
    # D59: a reminder must never fire on a record whose timing cannot
    # be trusted, and the sweep must not silently skip corruption.
    with pytest.raises(ValueError):
        push_events.maybe_enqueue_reminder(
            conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
            get_record=make_bad)
    assert _outcomes(conn, "reminder") == []


def test_superseded_audit_exactly_once_under_overlap(tmp_path):
    """Overlapping gate-1 observations of one terminal approval:
    exactly one `suppressed_terminal` audit row.

    The D61 write is SELECT-then-INSERT; the D57 partial unique index
    (whose predicate covers `suppressed_terminal`) is the enforcement,
    and the writer tolerates the loser's IntegrityError. Verified
    non-vacuous: dropping 'suppressed_terminal' from the index
    predicate lets all six threads insert (six rows).
    """
    dbfile = str(tmp_path / "audit_race.db")
    c = sqlite3.connect(dbfile)
    c.executescript(DDL_BUDGET_COUNTERS + DDL_SEND_RESULTS
                    + DDL_DIGEST_STATE + DDL_PAGE_ONCE_INDEX)
    c.close()
    now = _utcnow()
    rec = _record(now - timedelta(minutes=40), ttl_seconds=600,
                  terminal=True)
    barrier = threading.Barrier(6)
    results = []

    def worker():
        cc = sqlite3.connect(dbfile, timeout=10.0)
        barrier.wait()
        try:
            results.append(push_events.maybe_enqueue_reminder(
                cc, box_id="box-1", owner_principal="owner-1",
                aid="aid-1", get_record=lambda a: rec, now=now))
        finally:
            cc.close()

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 6
    assert all(r.disposition == "superseded_terminal" for r in results)
    c = sqlite3.connect(dbfile)
    try:
        n = c.execute(
            "SELECT COUNT(*) FROM push_send_results"
            " WHERE outcome = 'suppressed_terminal'").fetchone()[0]
        assert n == 1
    finally:
        c.close()


# --- digest ----------------------------------------------------------------------

def test_digest_trigger(conn):
    now = _utcnow()
    r = push_events.maybe_enqueue_digest(
        conn, owner_principal="owner-1", now=now)
    assert r.disposition == "no_digest_due"
    # Coalesce pages into the digest with distinct aids (budget 3/box),
    # then trigger.
    for i in range(4):
        push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box-9", key_material="aid-%d" % i, now=now)
    # box-9's budget is 3: first three queued, the fourth over budget.
    assert push_enqueue.get_digest_count(
        conn, "owner-1", push_enqueue.hour_bucket(now)) == 1
    d1 = push_events.maybe_enqueue_digest(
        conn, owner_principal="owner-1", now=now)
    assert d1.disposition == "queued"
    assert d1.detail.event_key == "owner-1\x00" + push_enqueue.hour_bucket(
        now)
    # The trigger itself is page-once per window (D64).
    d2 = push_events.maybe_enqueue_digest(
        conn, owner_principal="owner-1", now=now)
    assert d2.disposition == "duplicate"


def _digest_state(conn, owner, window):
    return conn.execute(
        "SELECT count, enqueued_at FROM push_digest_state"
        " WHERE owner_principal = ? AND window_start = ?",
        (owner, window)).fetchone()


def test_digest_fire_stamps_enqueued_at(conn):
    # D76: the D54 obligation — enqueued_at is stamped when the digest
    # page is accepted; a duplicate refire does not touch the stamp.
    now = _utcnow()
    ws = push_enqueue.hour_bucket(now)
    for i in range(4):
        push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box-9", key_material="aid-%d" % i, now=now)
    assert _digest_state(conn, "owner-1", ws)[1] is None
    d1 = push_events.maybe_enqueue_digest(
        conn, owner_principal="owner-1", now=now)
    assert d1.disposition == "queued"
    count, stamp = _digest_state(conn, "owner-1", ws)
    assert count == 1 and stamp is not None
    d2 = push_events.maybe_enqueue_digest(
        conn, owner_principal="owner-1", now=now)
    assert d2.disposition == "duplicate"
    assert _digest_state(conn, "owner-1", ws)[1] == stamp


def test_digest_crash_gap_heals_on_duplicate_refire(conn):
    # #1096: a crash between enqueue_page's commit (the `queued` row)
    # and the enqueued_at stamp leaves a live page row with
    # enqueued_at NULL. The next sweep's refire reports `duplicate` —
    # and the stamp now heals instead of stranding the window.
    now = _utcnow()
    ws = push_enqueue.hour_bucket(now)
    for i in range(4):
        push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box-9", key_material="aid-%d" % i, now=now)
    # Simulate the crash: the digest page row is committed (first
    # commit) but the enqueued_at stamp (second commit) never ran.
    r = push_enqueue.enqueue_page(
        conn, event_kind="digest", owner_principal="owner-1",
        box_id=None, key_material=ws, now=now)
    assert r.disposition == "queued"
    assert _digest_state(conn, "owner-1", ws)[1] is None
    # The next sweep refires, dedups, and stamps the window.
    d = push_events.maybe_enqueue_digest(
        conn, owner_principal="owner-1", now=now)
    assert d.disposition == "duplicate"
    count, stamp = _digest_state(conn, "owner-1", ws)
    assert count == 1 and stamp is not None


def test_digest_duplicate_without_page_row_leaves_stamp_unset(conn):
    # #1096, the careful point: a `duplicate` from the D57 race path
    # with no page row present must NOT stamp. A digest suppressed
    # twice in a row produces exactly this: the second refire dedups
    # against the first sweep's suffixed suppression audit (D77), so
    # no exact-key page row exists — the stamp stays NULL and a later
    # sweep retries.
    now = _utcnow()
    ws = push_enqueue.hour_bucket(now)
    # Exhaust the owner's D10 budget (10 approvals across 10 boxes).
    for i in range(10):
        r = push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box-%d" % i, key_material="aid-%d" % i, now=now)
        assert r.disposition == "queued"
    assert push_enqueue.get_digest_count(conn, "owner-1", ws) == 0
    # One more filing coalesces (count > 0) so the digest fires.
    push_enqueue.enqueue_page(
        conn, event_kind="approval_filed", owner_principal="owner-1",
        box_id="box-10", key_material="aid-10", now=now)
    assert push_enqueue.get_digest_count(conn, "owner-1", ws) == 1
    d1 = push_events.maybe_enqueue_digest(
        conn, owner_principal="owner-1", now=now)
    assert d1.disposition == "suppressed_budget"
    assert _digest_state(conn, "owner-1", ws)[1] is None
    d2 = push_events.maybe_enqueue_digest(
        conn, owner_principal="owner-1", now=now)
    assert d2.disposition == "duplicate"
    # No exact-key page row exists (only the suffixed audit) —
    # the stamp stays unset for a later sweep.
    assert _digest_state(conn, "owner-1", ws)[1] is None


def test_digest_window_start_fail_closed(conn):
    # D76: the explicit window is key material — empty or
    # separator-injected windows are ValueError, never a weird key.
    with pytest.raises(ValueError):
        push_events.maybe_enqueue_digest(
            conn, owner_principal="owner-1", window_start="")
    with pytest.raises(ValueError):
        push_events.maybe_enqueue_digest(
            conn, owner_principal="owner-1",
            window_start="2026-10-05T10\x00x")


# --- fail-closed surface -----------------------------------------------------------

def test_no_page_kinds_are_unrepresentable():
    # D58: decided/expired have no mapping function — the public
    # surface is exactly the taxonomy's paging rows.
    public = {n for n in dir(push_events)
              if (n.startswith("on_") or n.startswith("maybe_"))
              and callable(getattr(push_events, n))}
    assert public == {"on_approval_filed", "on_token_expiry_warning",
                      "on_box_revoked", "on_heartbeat_stale",
                      "maybe_enqueue_reminder", "maybe_enqueue_digest"}


@pytest.mark.parametrize("kwargs", [
    {"box_id": "", "owner_principal": "owner-1"},
    {"box_id": "box-1", "owner_principal": ""},
])
def test_fail_closed_identities(conn, kwargs):
    with pytest.raises(ValueError):
        push_events.on_approval_filed(conn, aid="aid-1", **kwargs)


def test_fail_closed_key_material(conn):
    with pytest.raises(ValueError):
        push_events.on_approval_filed(
            conn, box_id="box-1", owner_principal="owner-1",
            aid="aid\x001")
    with pytest.raises(ValueError):
        push_events.maybe_enqueue_reminder(
            conn, box_id="box-1", owner_principal="owner-1", aid="aid-1",
            get_record="not-callable")
