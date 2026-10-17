"""Tests for hosted/push_enqueue_async.py (#1614 — async-boundary port slice).

The async `_D1` shim below is worker-faithful: `prepare(sql)` →
`.bind(*params)` → `await .all()` / `await .first()` / `await .run()`,
rows as dicts, `.run()` reporting `meta.changes` / `meta.last_row_id`.
The sqlite3 connection runs in **autocommit** (`isolation_level=None`)
so every statement is individually durable — the worker's D1 has no
interactive transaction across awaits, and the port never calls a
commit primitive (there is none on the worker's `_D1`).

The fixture DDL is verbatim from docs/PUSH_SENDER_SCHEMA_CONTRACT.md
§§1.2–1.4 (the #988 contract) **plus** the D57 partial unique index
(marked below) — the same fixture as hosted/test_push_enqueue.py, so
the conformance tests below diff the async port against the sync
harness truth on identical schema.

What this proves and what it does not: the D-EW-2 conformance tests
replay the same event sequences through the sync boundary
(`hosted/push_enqueue`) and the async port and diff dispositions +
database state — a green run proves the async port reuses the sync
decision table verbatim. The `_RaceDb` tests pin the D53 lost-race
path deterministically. The `_ObligationHarness` tests pin the
CALLER-SIDE contract for the plane endpoints (terminal-aid upstream
check; D65 grandfathered exclusion): the mappings themselves do not
re-read terminality by design, so the harness — the shape the #952
filing endpoint and the revoke endpoint must implement — asserts the
boundary is never invoked for those inputs. The live tick (D-EW-3)
stays on #1614.
"""

import asyncio
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import push_enqueue, push_enqueue_async, push_events_async

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
DDL_PAGE_ONCE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_push_send_results_page_once
  ON push_send_results(box_id, event_kind, event_key)
  WHERE outcome IN ('queued', 'suppressed_budget', 'suppressed_terminal');
"""


# --- Worker-faithful async _D1 shim -------------------------------------

class _AllResult:
    def __init__(self, results):
        self.results = results


class _RunResult:
    def __init__(self, changes, last_row_id=None):
        self.success = True
        self.meta = {"changes": changes, "last_row_id": last_row_id}


class _Bound:
    """One bound statement: async .all()/.first()/.run() over sqlite3."""

    def __init__(self, conn, sql, params):
        self._conn = conn
        self._sql = sql
        self._params = params

    async def all(self):
        cur = self._conn.execute(self._sql, self._params)
        return _AllResult([dict(r) for r in cur.fetchall()])

    async def first(self):
        cur = self._conn.execute(self._sql, self._params)
        row = cur.fetchone()
        return dict(row) if row is not None else None

    async def run(self):
        cur = self._conn.execute(self._sql, self._params)
        return _RunResult(cur.rowcount, cur.lastrowid)


class _Stmt:
    def __init__(self, conn, sql):
        self._conn = conn
        self._sql = sql

    def bind(self, *params):
        return _Bound(self._conn, self._sql, params)


class _AsyncD1:
    """Worker-faithful async _D1 over a sqlite3 connection (test-only).

    `.all()` → `.results` list of dicts; `.first()` → dict or None;
    `.run()` → success/meta with `changes` and `last_row_id`. The
    connection is the caller's (autocommit); the shim never commits —
    the worker's `_D1` has no commit primitive.
    """

    def __init__(self, conn):
        conn.row_factory = sqlite3.Row
        self._conn = conn

    def prepare(self, sql):
        return _Stmt(self._conn, sql)


class _RaceDb:
    """Force the D53 lost-dedup-race path deterministically.

    Wraps an _AsyncD1: when armed for an event key, the next
    `push_send_results` INSERT for that key first writes the
    conflicting row directly (simulating the concurrent winner), so the
    port's own INSERT violates the D57 page-once index.
    """

    def __init__(self, inner, conn):
        self._inner = inner
        self._conn = conn
        self._armed = None

    def arm(self, box_id, event_kind, event_key):
        self._armed = (box_id, event_kind, event_key)

    def prepare(self, sql):
        armed = self._armed
        if armed is not None and sql.lstrip().upper().startswith(
                "INSERT INTO PUSH_SEND_RESULTS"):
            box_id, event_kind, event_key = armed
            self._armed = None
            self._conn.execute(
                "INSERT INTO push_send_results"
                " (at, owner_principal, box_id, device, event_kind,"
                "  event_key, outcome, http_status, latency_ms, sent_at,"
                "  vapid_key_id)"
                " VALUES (?, 'owner-1', ?, '', ?, ?, 'queued',"
                "  NULL, NULL, NULL, NULL)",
                ("2026-10-17T00:00:00+00:00", box_id, event_kind,
                 event_key))
        return self._inner.prepare(sql)


class _FailingDb:
    """INSERTs raise a non-conflict error; no conflicting row exists."""

    def __init__(self, inner, error):
        self._inner = inner
        self._error = error

    def prepare(self, sql):
        stmt = self._inner.prepare(sql)
        error = self._error

        class _FailingBound:
            def __init__(self, params):
                self._params = params

            async def all(self):
                return await stmt.bind(*self._params).all()

            async def first(self):
                return await stmt.bind(*self._params).first()

            async def run(self):
                raise error

        class _FailingStmt:
            def bind(self, *params):
                return _FailingBound(params)

        return _FailingStmt()


@pytest.fixture
def conn():
    # Autocommit: every statement individually durable, like the
    # worker's D1 (the port has no commit primitive to call).
    c = sqlite3.connect(":memory:", isolation_level=None)
    c.executescript(DDL_BUDGET_COUNTERS + DDL_SEND_RESULTS
                    + DDL_DIGEST_STATE + DDL_PAGE_ONCE_INDEX)
    yield c
    c.close()


@pytest.fixture
def db(conn):
    return _AsyncD1(conn)


def _run(coro):
    return asyncio.run(coro)


def _enq(db, **kw):
    return _run(push_enqueue_async.enqueue_page_async(db, **kw))


# --- Happy path + key shape ----------------------------------------------

def test_enqueue_async_happy_path(conn, db):
    r = _enq(db, event_kind="approval_filed", owner_principal="owner-1",
             box_id="box-1", key_material="aid-1")
    assert r.disposition == "queued"
    assert r.event_key == "box-1\x00aid-1"
    assert r.row_id is not None
    row = conn.execute(
        "SELECT owner_principal, box_id, device, event_kind, event_key,"
        " outcome, http_status, latency_ms FROM push_send_results").fetchone()
    # tuple(): the shim sets sqlite3.Row as the shared connection's
    # row_factory (rows arrive as dicts on the async path).
    assert tuple(row) == ("owner-1", "box-1", "", "approval_filed",
                          "box-1\x00aid-1", "queued", None, None)
    # D52 — one unit on each scope.
    ws = push_enqueue_async.hour_bucket()
    assert _run(push_enqueue_async.get_counter_async(
        db, "box", "box-1", ws)) == 1
    assert _run(push_enqueue_async.get_counter_async(
        db, "owner", "owner-1", ws)) == 1


def test_at_shape_matches_sync_utc_iso(conn, db):
    from datetime import datetime, timezone
    now = datetime(2026, 10, 17, 5, 30, 15, tzinfo=timezone.utc)
    _enq(db, event_kind="approval_filed", owner_principal="owner-1",
         box_id="box-1", key_material="aid-9", now=now)
    at = conn.execute(
        "SELECT at FROM push_send_results").fetchone()[0]
    # The async writer must emit the exact sync byte shape or the
    # lane's lexicographic TEXT comparisons stop being chronological.
    assert at == push_enqueue.utc_iso(now)


def test_duplicate_fast_path_consumes_no_budget(conn, db):
    kw = dict(event_kind="approval_filed", owner_principal="owner-1",
              box_id="box-1", key_material="aid-2")
    r1 = _enq(db, **kw)
    r2 = _enq(db, **kw)
    assert (r1.disposition, r2.disposition) == ("queued", "duplicate")
    assert r2.row_id is None
    ws = push_enqueue_async.hour_bucket()
    assert _run(push_enqueue_async.get_counter_async(
        db, "box", "box-1", ws)) == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM push_send_results").fetchone()[0] == 1


# --- Budget exhaustion + digest coalescing (D10/D52/D54) ------------------

def test_budget_exhaustion_coalesces_into_digest(conn, db):
    ws = push_enqueue_async.hour_bucket()
    # Fill the box scope to the default bound (3) so the enqueue path
    # itself overflows.
    for _ in range(push_enqueue_async.BOX_BOUND_DEFAULT):
        assert _run(push_enqueue_async.reserve_budget_async(
            db, "box-1", "owner-1", ws)) is True
    assert _run(push_enqueue_async.reserve_budget_async(
        db, "box-1", "owner-1", ws)) is False
    r = _enq(db, event_kind="approval_filed", owner_principal="owner-1",
             box_id="box-1", key_material="aid-3")
    assert r.disposition == "suppressed_budget"
    assert r.row_id is not None
    # D54 — the suppressed filing is counted into the digest.
    assert _run(push_enqueue_async.get_digest_count_async(
        db, "owner-1", ws)) == 1
    row = conn.execute(
        "SELECT event_key, outcome, http_status FROM push_send_results"
        " WHERE outcome = 'suppressed_budget'").fetchone()
    assert tuple(row) == ("box-1\x00aid-3", "suppressed_budget", None)
    # A replayed filing coalesced into the digest stays coalesced.
    r2 = _enq(db, event_kind="approval_filed", owner_principal="owner-1",
              box_id="box-1", key_material="aid-3")
    assert r2.disposition == "duplicate"
    assert _run(push_enqueue_async.get_digest_count_async(
        db, "owner-1", ws)) == 1


def test_digest_kind_suppression_never_touches_digest_count(conn, db):
    # #1423/D77: a budget-suppressed digest writes only the suffixed
    # suppression audit — the digest is retryable and its retry renders
    # the window's true coalesced count.
    ws = push_enqueue_async.hour_bucket()
    # Exhaust the owner bound via digest-scoped reservations.
    for _ in range(push_enqueue_async.OWNER_BOUND_DEFAULT):
        assert _run(push_enqueue_async.reserve_budget_async(
            db, None, "owner-1", ws)) is True
    assert _run(push_enqueue_async.reserve_budget_async(
        db, None, "owner-1", ws)) is False
    r = _enq(db, event_kind="digest", owner_principal="owner-1",
             box_id=None, key_material=ws)
    assert r.disposition == "suppressed_budget"
    assert _run(push_enqueue_async.get_digest_count_async(
        db, "owner-1", ws)) == 0
    keys = [row[0] for row in conn.execute(
        "SELECT event_key FROM push_send_results"
        " WHERE outcome = 'suppressed_budget'")]
    assert keys == ["owner-1\x00" + ws + "\x00suppressed"]
    # Re-suppressing the same digest is duplicate, not a second audit.
    r2 = _enq(db, event_kind="digest", owner_principal="owner-1",
              box_id=None, key_material=ws)
    assert r2.disposition == "duplicate"
    assert conn.execute(
        "SELECT COUNT(*) FROM push_send_results").fetchone()[0] == 1


def test_digest_reservation_is_owner_only(conn, db):
    ws = push_enqueue_async.hour_bucket()
    _enq(db, event_kind="digest", owner_principal="owner-1",
         box_id=None, key_material=ws)
    assert _run(push_enqueue_async.get_counter_async(
        db, "owner", "owner-1", ws)) == 1
    # No ("box","") shared counter was created for the digest.
    assert conn.execute(
        "SELECT COUNT(*) FROM push_budget_counters"
        " WHERE scope_type = 'box'").fetchone()[0] == 0
    row = conn.execute(
        "SELECT box_id FROM push_send_results").fetchone()
    assert row[0] == ""


def test_release_is_floored_at_zero(db):
    ws = push_enqueue_async.hour_bucket()
    _run(push_enqueue_async.release_reservation_async(
        db, "box-9", "owner-9", ws))
    _run(push_enqueue_async.release_reservation_async(
        db, "box-9", "owner-9", ws))
    assert _run(push_enqueue_async.get_counter_async(
        db, "box", "box-9", ws)) == 0
    assert _run(push_enqueue_async.get_counter_async(
        db, "owner", "owner-9", ws)) == 0


# --- D53 lost race + conflict-handler discipline -------------------------

def test_lost_dedup_race_returns_duplicate_and_releases(conn, db):
    ws = push_enqueue_async.hour_bucket()
    race = _RaceDb(db, conn)
    race.arm("box-1", "approval_filed", "box-1\x00aid-race")
    r = _enq(race, event_kind="approval_filed", owner_principal="owner-1",
             box_id="box-1", key_material="aid-race")
    assert r.disposition == "duplicate"
    # One event, one page, one budget unit: the just-taken reservation
    # was released.
    assert _run(push_enqueue_async.get_counter_async(
        db, "box", "box-1", ws)) == 0
    assert _run(push_enqueue_async.get_counter_async(
        db, "owner", "owner-1", ws)) == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM push_send_results").fetchone()[0] == 1


def test_insert_failure_without_conflicting_row_reraises(db):
    boom = RuntimeError("simulated D1 write failure")
    failing = _FailingDb(db, boom)
    with pytest.raises(RuntimeError) as ei:
        _enq(failing, event_kind="approval_filed",
             owner_principal="owner-1", box_id="box-1",
             key_material="aid-boom")
    assert ei.value is boom


# --- Validation (fail-closed) --------------------------------------------

def test_no_page_kinds_are_value_errors(db):
    for kind in ("decided", "expired"):
        with pytest.raises(ValueError):
            _enq(db, event_kind=kind, owner_principal="owner-1",
                 box_id="box-1", key_material="aid-1")


def test_bad_inputs_are_value_errors(db):
    base = dict(event_kind="approval_filed", owner_principal="owner-1",
                box_id="box-1", key_material="aid-1")
    for mutate in (
            lambda kw: kw.update(owner_principal=""),
            lambda kw: kw.update(owner_principal=None),
            lambda kw: kw.update(box_id=""),
            lambda kw: kw.update(key_material=""),
            lambda kw: kw.update(key_material="a\x00b"),
            lambda kw: kw.update(box_id="b\x00x"),
    ):
        kw = dict(base)
        mutate(kw)
        with pytest.raises(ValueError):
            _enq(db, **kw)
    # digest keys scope to the owner, never a box.
    with pytest.raises(ValueError):
        _enq(db, event_kind="digest", owner_principal="owner-1",
             box_id="box-1", key_material="w")
    for bad in (0, True):
        with pytest.raises(ValueError):
            _run(push_enqueue_async.reserve_budget_async(
                db, "box-1", "owner-1", "w", box_bound=bad))


# --- D-EW-2 conformance: async port vs sync harness truth ----------------

def _dump(conn):
    """Canonical DB state for the sync/async diff."""
    out = []
    for table, order in (
            ("push_send_results",
             "id, at, owner_principal, box_id, device, event_kind,"
             " event_key, outcome"),
            ("push_budget_counters",
             "scope_type, scope_id, window_start, count"),
            ("push_digest_state",
             "owner_principal, window_start, count")):
        rows = conn.execute(
            "SELECT %s FROM %s ORDER BY %s" % (order, table, order)
        ).fetchall()
        out.append((table, [tuple(r) for r in rows]))
    return out


def _scenario_events():
    # A mixed sequence: happy pages, replays, two kinds, one digest,
    # and a budget overflow at bound=1 to force the coalesce path.
    return [
        ("approval_filed", "box-1", "aid-1"),
        ("approval_filed", "box-1", "aid-1"),  # replay → duplicate
        ("box_revoked", "box-1", "2026-10-17T05:30:00+00:00"),
        ("token_expiry_warning", "box-2", "tokhash-1"),
        ("approval_filed", "box-2", "aid-2"),
    ]


def test_conformance_matches_sync_dispositions_and_state(db):
    from datetime import datetime, timezone
    now = datetime(2026, 10, 17, 5, 30, tzinfo=timezone.utc)
    # Sync run.
    sync_conn = sqlite3.connect(":memory:")
    sync_conn.executescript(DDL_BUDGET_COUNTERS + DDL_SEND_RESULTS
                            + DDL_DIGEST_STATE + DDL_PAGE_ONCE_INDEX)
    sync_dispositions = []
    for kind, box, key in _scenario_events():
        r = push_enqueue.enqueue_page(
            sync_conn, event_kind=kind, owner_principal="owner-1",
            box_id=box, key_material=key, now=now)
        sync_dispositions.append((r.disposition, r.event_key))
    sync_state = _dump(sync_conn)
    sync_conn.close()
    # Async run over an identical starting schema.
    async_dispositions = []

    async def drive():
        for kind, box, key in _scenario_events():
            r = await push_enqueue_async.enqueue_page_async(
                db, event_kind=kind, owner_principal="owner-1",
                box_id=box, key_material=key, now=now)
            async_dispositions.append((r.disposition, r.event_key))

    _run(drive())
    assert async_dispositions == sync_dispositions
    assert _dump(db._conn) == sync_state


def test_conformance_budget_overflow_matches_sync():
    from datetime import datetime, timezone
    now = datetime(2026, 10, 17, 5, 30, tzinfo=timezone.utc)
    events = [("approval_filed", "box-1", "aid-%d" % i) for i in range(5)]

    def drive_sync():
        c = sqlite3.connect(":memory:")
        c.executescript(DDL_BUDGET_COUNTERS + DDL_SEND_RESULTS
                        + DDL_DIGEST_STATE + DDL_PAGE_ONCE_INDEX)
        ws = push_enqueue.hour_bucket(now)
        assert push_enqueue.reserve_budget(
            c, "box-1", "owner-1", ws, box_bound=1)
        out = [push_enqueue.enqueue_page(
            c, event_kind=k, owner_principal="owner-1", box_id=b,
            key_material=m, now=now).disposition for k, b, m in events]
        state = _dump(c)
        c.close()
        return out, state

    async def drive_async():
        # Fresh autocommit connection per drive (like drive_sync's):
        # the budget counters are per-database state.
        c = sqlite3.connect(":memory:", isolation_level=None)
        c.executescript(DDL_BUDGET_COUNTERS + DDL_SEND_RESULTS
                        + DDL_DIGEST_STATE + DDL_PAGE_ONCE_INDEX)
        adb = _AsyncD1(c)
        ws = push_enqueue_async.hour_bucket(now)
        assert await push_enqueue_async.reserve_budget_async(
            adb, "box-1", "owner-1", ws, box_bound=1)
        out = []
        for k, b, m in events:
            r = await push_enqueue_async.enqueue_page_async(
                adb, event_kind=k, owner_principal="owner-1", box_id=b,
                key_material=m, now=now)
            out.append(r.disposition)
        state = _dump(c)
        c.close()
        return out, state

    assert drive_sync()[0] == _run(drive_async())[0]
    assert drive_sync()[1] == _run(drive_async())[1]


# --- The STACKING NOTE's consumer: async mappings + async boundary ------

def test_async_mappings_compose_with_async_boundary(db):
    """`on_approval_filed` / `on_box_revoked` (push_events_async) inject
    the new async boundary — the boundary half of the STACKING NOTE."""
    async def drive():
        r1 = await push_events_async.on_approval_filed(
            db, box_id="box-1", owner_principal="owner-1", aid="aid-7",
            enqueue_page=push_enqueue_async.enqueue_page_async)
        r2 = await push_events_async.on_box_revoked(
            db, box_id="box-1", owner_principal="owner-1",
            revoked_at="2026-10-17T05:30:00+00:00",
            enqueue_page=push_enqueue_async.enqueue_page_async)
        return r1, r2

    r1, r2 = _run(drive())
    assert (r1.disposition, r2.disposition) == ("queued", "queued")
    assert r1.detail.event_key == "box-1\x00aid-7"
    assert r2.detail.event_key == "box-1\x002026-10-17T05:30:00+00:00"


class _ObligationHarness:
    """The caller-side contract the plane endpoints must implement.

    The mappings do not re-read terminality by design (filing IS the
    plane's own write; revocation IS the terminal event) — so the
    endpoint performs the obligation upstream and only then calls the
    mapping. This harness is that endpoint shape, in-repo, so the
    negative assertions #1614 demands are pinned where the contract is
    documented. `terminal_aids` / `grandfathered` stand in for the
    #872 record read and the D65 keyless-grandfathered check.
    """

    def __init__(self, db):
        self.db = db
        self.boundary_calls = []
        self.terminal_aids = set()
        self.grandfathered_boxes = set()

    async def _boundary(self, db, **kw):
        self.boundary_calls.append(kw)
        return await push_enqueue_async.enqueue_page_async(db, **kw)

    async def file_approval(self, box_id, owner_principal, aid):
        # Caller obligation: NEVER emit a filing event for an aid
        # whose #872 record is already terminal — the check is upstream
        # of the write (no gate-1 re-read on this path by design).
        if aid in self.terminal_aids:
            return ("not_paged", "terminal aid: obligation blocks")
        r = await push_events_async.on_approval_filed(
            self.db, box_id=box_id, owner_principal=owner_principal,
            aid=aid, enqueue_page=self._boundary)
        return (r.disposition, r.detail)

    async def revoke_box(self, box_id, owner_principal, revoked_at,
                         keyless_grandfathered=False):
        # Caller obligation (D65): never for the keyless-grandfathered
        # path — only real revocation events page.
        if keyless_grandfathered or box_id in self.grandfathered_boxes:
            return ("not_paged", "D65: grandfathered revocation")
        r = await push_events_async.on_box_revoked(
            self.db, box_id=box_id, owner_principal=owner_principal,
            revoked_at=revoked_at, enqueue_page=self._boundary)
        return (r.disposition, r.detail)


def test_terminal_aid_never_reaches_the_boundary(db):
    h = _ObligationHarness(db)
    h.terminal_aids.add("aid-dead")

    async def drive():
        live = await h.file_approval("box-1", "owner-1", "aid-live")
        dead = await h.file_approval("box-1", "owner-1", "aid-dead")
        return live, dead

    live, dead = _run(drive())
    assert live[0] == "queued"
    assert dead == ("not_paged", "terminal aid: obligation blocks")
    # The terminal aid never touched the boundary: one call total.
    assert [c["key_material"] for c in h.boundary_calls] == ["aid-live"]


def test_grandfathered_revoke_never_reaches_the_boundary(db):
    h = _ObligationHarness(db)

    async def drive():
        real = await h.revoke_box("box-1", "owner-1",
                                  "2026-10-17T05:30:00+00:00")
        grand = await h.revoke_box("box-2", "owner-1",
                                   "2026-10-17T05:31:00+00:00",
                                   keyless_grandfathered=True)
        return real, grand

    real, grand = _run(drive())
    assert real[0] == "queued"
    assert grand == ("not_paged", "D65: grandfathered revocation")
    assert [c["key_material"] for c in h.boundary_calls] == [
        "2026-10-17T05:30:00+00:00"]
