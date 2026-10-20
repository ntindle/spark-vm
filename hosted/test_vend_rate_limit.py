"""Tests for hosted/vend_rate_limit.py — the #1405 per-box mint token bucket.

Every behavioral test below is neuter-checked: the neuters that must
fail each test are listed in the test docstring (verified on scratch
copies, never on this tree).
"""

import os
import sqlite3
import threading

import pytest

from hosted import vend_rate_limit
from hosted.vend_rate_limit import (
    RATE_LIMIT_CAPACITY,
    RATE_LIMIT_WINDOW_S,
    RateLimitResult,
    ensure_schema,
    try_take,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    return conn


def test_first_mint_allowed():
    """A fresh box holds a full bucket: the first mint is allowed."""
    conn = _conn()
    res = try_take(conn, box_id="box-1", now=1_000_000)
    assert res == RateLimitResult(True, None)
    # Neuters: skipping the INSERT OR IGNORE denies the fresh box.


def test_capacity_exhaustion_denies_with_retry_after():
    """capacity takes succeed; the next is denied with an advisory hint."""
    conn = _conn()
    # Even parameters so the retry-after math is hand-computable:
    # rate = 6/60 = 0.1/s; a drained bucket needs 10 s per token.
    for _ in range(6):
        assert try_take(conn, box_id="b", now=100, capacity=6,
                        window_s=60).allowed
    denied = try_take(conn, box_id="b", now=100, capacity=6, window_s=60)
    assert denied.allowed is False
    assert denied.retry_after_s == 10
    # Neuters: WHERE ">= 1.0" -> ">= 0.0" lets the 7th take through.


def test_refill_over_time():
    """Elapsed time refills the bucket; idle never over-accumulates."""
    conn = _conn()
    for _ in range(6):
        assert try_take(conn, box_id="b", now=100, capacity=6,
                        window_s=60).allowed
    assert not try_take(conn, box_id="b", now=100, capacity=6,
                        window_s=60).allowed
    # 10 s -> exactly one token (6/60 per s); the ROUND(...,6) snap
    # absorbs the float dust (10 * 0.1 == 1.0 in the statement).
    assert try_take(conn, box_id="b", now=110, capacity=6,
                    window_s=60).allowed
    assert not try_take(conn, box_id="b", now=110, capacity=6,
                        window_s=60).allowed
    # A long idleness restores the whole bucket — and no more: 200 s at
    # 0.1/s would refill 20 tokens uncapped, but the MIN(capacity, ...)
    # gate holds it at 6.
    allowed = sum(
        try_take(conn, box_id="b", now=310, capacity=6,
                 window_s=60).allowed
        for _ in range(7))
    assert allowed == 6
    # Neuters: dropping the MIN(capacity, ...) cap lets the idle box
    # spend all 7 (uncapped refill = 20); removing the refill term keeps
    # the bucket drained forever.


def test_default_parameters_shape():
    """The D105 defaults: 10 mints / 300 s per box."""
    assert RATE_LIMIT_CAPACITY == 10
    assert RATE_LIMIT_WINDOW_S == 300
    conn = _conn()
    allowed = sum(
        try_take(conn, box_id="b", now=500).allowed for _ in range(11))
    assert allowed == 10
    denied = try_take(conn, box_id="b", now=500)
    assert denied.allowed is False
    # ~30 s per token at defaults; assert the magnitude, not float dust.
    assert 29 <= denied.retry_after_s <= 31


def test_per_box_isolation():
    """One box's takes never spend another box's bucket.

    Interleaved-budget shape: box-b's take must be served from its own
    fresh bucket and must not touch box-a's remaining tokens.
    Neuters: removing the box_id predicate from the take's WHERE clause
    lets box-b spend box-a's bucket — box-a then has 2 tokens left, not
    3, and this test fails. (The earlier exhaust-then-probe shape was
    blind to this: box-b's take was *allowed* via its fresh-bucket
    INSERT, so the theft never surfaced — QA round-1 BLOCKING.)
    """
    conn = _conn()
    for _ in range(3):
        assert try_take(conn, box_id="box-a", now=100, capacity=6,
                        window_s=60).allowed
    # box-b's take must be served from box-b's own fresh bucket ...
    assert try_take(conn, box_id="box-b", now=100, capacity=6,
                    window_s=60).allowed
    # ... and must not have touched box-a's remaining 3 tokens.
    allowed_a = sum(
        try_take(conn, box_id="box-a", now=100, capacity=6,
                 window_s=60).allowed
        for _ in range(4))
    assert allowed_a == 3


def test_concurrent_takes_never_overspend(tmp_path):
    """20 racing takers on a 10-token bucket: exactly 10 allowed.

    Each thread opens its own connection (the worker's D1 serializes
    writers the same way); the single-statement atomic take is the
    only synchronization. Neuters: two-statement read-then-write take
    lets >10 through.
    """
    db_path = str(tmp_path / "ratelimit.db")
    setup = sqlite3.connect(db_path)
    ensure_schema(setup)
    setup.close()

    results = []
    lock = threading.Lock()

    def worker():
        conn = sqlite3.connect(db_path, check_same_thread=False,
                               timeout=10.0)
        res = try_take(conn, box_id="box-race", now=999)
        # The worker's D1 has no commit primitive: every `.run()` is
        # individually durable. Without this commit each thread's take
        # rolls back on close and every thread sees a fresh bucket
        # (the test then vacuously passes 20/20).
        conn.commit()
        with lock:
            results.append(res.allowed)
        conn.close()

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 20
    assert sum(results) == 10


def test_fail_closed_typing():
    """Non-str box_id never reaches the WHERE clause; empty is refused."""
    conn = _conn()
    with pytest.raises(TypeError):
        try_take(conn, box_id=123, now=100)
    with pytest.raises(TypeError):
        try_take(conn, box_id=None, now=100)
    with pytest.raises(ValueError):
        try_take(conn, box_id="", now=100)
    # The refused takes created no bucket row.
    assert conn.execute(
        "SELECT COUNT(*) FROM vend_rate_limit").fetchone()[0] == 0
    # Neuters: deleting the isinstance guard lets 123 reach the SQL —
    # sqlite coerces and the row COUNT becomes 1.


def test_ensure_schema_idempotent():
    """ensure_schema is safe to call on every take path (worker boot)."""
    conn = _conn()
    ensure_schema(conn)
    ensure_schema(conn)
    try_take(conn, box_id="b", now=1)
    ensure_schema(conn)
    assert conn.execute(
        "SELECT tokens FROM vend_rate_limit WHERE box_id='b'"
    ).fetchone()[0] == float(RATE_LIMIT_CAPACITY) - 1.0


def test_retry_after_rounds_up():
    """retry_after_s uses ceil, not floor: a denial at a non-integral
    quotient names the longer wait (QA round-1 observation)."""
    conn = _conn()
    for _ in range(6):
        assert try_take(conn, box_id="b", now=100, capacity=6,
                        window_s=60).allowed
    # 3 s later the bucket holds 0.3 tokens; the next token needs
    # ceil(7.0) = 7 s, not floor = 6.
    denied = try_take(conn, box_id="b", now=103, capacity=6, window_s=60)
    assert denied.allowed is False
    assert denied.retry_after_s == 7


def test_retry_after_advisory_not_gate():
    """A denied take's retry_after is a hint: it shrinks as time passes."""
    conn = _conn()
    for _ in range(6):
        try_take(conn, box_id="b", now=100, capacity=6, window_s=60)
    r1 = try_take(conn, box_id="b", now=100, capacity=6, window_s=60)
    r2 = try_take(conn, box_id="b", now=105, capacity=6, window_s=60)
    assert not r1.allowed and not r2.allowed
    assert r2.retry_after_s < r1.retry_after_s
    # At the refill point the take succeeds again — the hint was right.
    assert try_take(conn, box_id="b", now=110, capacity=6,
                    window_s=60).allowed
