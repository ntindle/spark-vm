"""Async-port conformance for hosted/vend_rate_limit_async.py (#1405).

The sync module is the test truth (D-PP-1). Every scenario below runs
the take sequence against BOTH the sync `try_take` and the async
`try_take_async` (over a worker-faithful `_D1` shim: `.prepare().bind()
.run()` -> success + meta.changes, `.first()` -> dict/None) and
asserts identical outcomes plus the hand-computed expectations.

This is what catches port-shape mistakes (e.g. reading `.changes`
instead of `meta["changes"]` — the worker's `_D1` shape): the shim
mirrors the worker, not the sync module.
"""

import asyncio
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import vend_rate_limit, vend_rate_limit_async


class _RunResult:
    def __init__(self, changes, last_row_id=None):
        self.success = True
        self.meta = {"changes": changes, "last_row_id": last_row_id}


class _Bound:
    def __init__(self, conn, sql, params):
        self._conn = conn
        self._sql = sql
        self._params = params

    async def run(self):
        cur = self._conn.execute(self._sql, self._params)
        return _RunResult(cur.rowcount, cur.lastrowid)

    async def first(self):
        cur = self._conn.execute(self._sql, self._params)
        row = cur.fetchone()
        return dict(row) if row is not None else None


class _Stmt:
    def __init__(self, conn, sql):
        self._conn = conn
        self._sql = sql

    def bind(self, *params):
        return _Bound(self._conn, self._sql, params)


class _AsyncD1:
    """Worker-faithful async _D1 over a sqlite3 connection (test-only)."""

    def __init__(self, conn):
        conn.row_factory = sqlite3.Row
        self._conn = conn

    def prepare(self, sql):
        return _Stmt(self._conn, sql)


def _run_both(scenario):
    """Run a take-sequence scenario against sync and async; return both
    outcome lists. The scenario is a list of (box_id, now) takes plus
    optional (capacity, window_s) overrides as a 4-tuple's tail."""
    sync_conn = sqlite3.connect(":memory:")
    vend_rate_limit.ensure_schema(sync_conn)
    async_conn = sqlite3.connect(":memory:")
    vend_rate_limit.ensure_schema(async_conn)
    db = _AsyncD1(async_conn)

    async def run_async():
        out = []
        for step in scenario:
            box_id, now = step[0], step[1]
            kw = {}
            if len(step) > 2:
                kw["capacity"] = step[2]
            if len(step) > 3:
                kw["window_s"] = step[3]
            out.append(await vend_rate_limit_async.try_take_async(
                db, box_id=box_id, now=now, **kw))
        return out

    sync_out = [
        vend_rate_limit.try_take(
            sync_conn, box_id=step[0], now=step[1],
            **({"capacity": step[2]} if len(step) > 2 else {}),
            **({"window_s": step[3]} if len(step) > 3 else {}))
        for step in scenario
    ]
    async_out = asyncio.run(run_async())
    return sync_out, async_out


def _assert_conform(scenario, expect_allowed):
    sync_out, async_out = _run_both(scenario)
    assert [r.allowed for r in sync_out] == expect_allowed
    assert [r.allowed for r in async_out] == expect_allowed
    assert [(r.allowed, r.retry_after_s) for r in sync_out] == \
        [(r.allowed, r.retry_after_s) for r in async_out]


def test_conform_fresh_box_and_exhaustion():
    scenario = [("b", 100, 6, 60)] * 7
    _assert_conform(scenario, [True] * 6 + [False])
    sync_out, _ = _run_both(scenario)
    # Hand-computed: rate = 0.1/s; drained bucket needs 10 s per token.
    assert sync_out[-1].retry_after_s == 10


def test_conform_refill():
    scenario = [("b", 100, 6, 60)] * 6 + [("b", 110, 6, 60)] * 2
    _assert_conform(scenario, [True] * 6 + [True, False])


def test_conform_isolation():
    # Interleaved-budget shape (mirrors test_per_box_isolation): box-b's
    # take must be served from its own fresh bucket and must not spend
    # box-a's remaining tokens.
    scenario = ([("a", 50, 6, 60)] * 3) + [("b", 50, 6, 60)] + \
        ([("a", 50, 6, 60)] * 4)
    _assert_conform(scenario, [True] * 3 + [True] + [True] * 3 + [False])


def test_conform_defaults():
    scenario = ([("a", 50)] * 11) + [("b", 50)]
    _assert_conform(scenario, [True] * 10 + [False, True])


def test_conform_fail_closed_typing():
    db = _AsyncD1(sqlite3.connect(":memory:"))
    with pytest.raises(TypeError):
        asyncio.run(vend_rate_limit_async.try_take_async(db, box_id=7))
    with pytest.raises(TypeError):
        vend_rate_limit.try_take(sqlite3.connect(":memory:"), box_id=7)
    with pytest.raises(ValueError):
        asyncio.run(vend_rate_limit_async.try_take_async(db, box_id=""))
