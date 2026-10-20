"""Async plane-port of the vend mint rate limiter (#1405).

`hosted/vend_rate_limit.py` ships the sync boundary: the D105 token
bucket, the D106 first-mint race, the atomic single-statement take.
This module is its async counterpart against the plane worker's async
`_D1` (F-PP-2: `await db.prepare(...).bind(...).run()`; no synchronous
D1 exists). Like `hosted/push_enqueue_async.py`, this file is droppable
into `worker.py` verbatim: stdlib-only, no imports from the sync
module, pure-compute helpers inlined with source citations (the ed25519
precedent), and the DB seam as awaited `_D1` calls.

Entry point:

    await try_take_async(db, *, box_id, now=None,
                         capacity=10, window_s=300) -> RateLimitResult

`db` is the worker's async `_D1`; `now` is integer unix seconds or None
(the boundary defaults it, exactly like the sync version). The name
carries the `_async` suffix because this file shares the in-repo
namespace with the sync module (the `push_enqueue_async` naming
precedent) — in the worker's marked section it IS `try_take`.

The sync module stays the harness and test truth (D-PP-1): the bucket
shape, the gate order (atomic UPDATE → INSERT OR IGNORE → re-UPDATE →
denied), and the D105/D106 pins are reused verbatim — policy is not
re-decided, only the DB-API boundary is ported.

D1 durability model (read this before the code): the `_D1` contract
exposes no interactive transaction across awaits, so the port cannot
spell the sync's statement groups. Every `.run()` is individually
durable on the worker; the port orders statements so every crash
window is either idempotent under retry or fail-safe:

- The take UPDATE is the single atomic gate, unchanged in shape — it
  is one statement, so it stays one atomic step on D1. A crash after
  it is a spent token with no mint: fail-safe (the bucket under-spends,
  never over-spends; the endpoint retries the mint and spends another
  token — the honest bound for a stateless take).
- The ensure INSERT is `INSERT OR IGNORE` (idempotent); the loser of
  the first-mint race re-takes the atomic gate (D106), so a crash
  between INSERT and re-UPDATE leaves a full bucket the next take
  refills from — never a stuck box.
- The denial-path SELECT is advisory (the sync module documents the
  window): `retry_after_s` is a hint for the 429's `Retry-After`, not
  a gate.

Trust posture (D2): this boundary never accepts a box-asserted
identity it cannot verify. The caller resolves the bearer token to
`box_id` via the #844 box-bearer gate and passes the resolved id in;
a hostile box that supplies its own `box_id` string must be rejected
upstream — this module cannot distinguish it. The `TypeError` on
non-`str` `box_id` travels with this file because it drops into
`worker.py` verbatim, ahead of the #890 endpoint wiring.
"""

import math
import time
from typing import NamedTuple, Optional


# D105 — vendored from hosted/vend_rate_limit.py (the sync module is
# the source of truth; these values are pinned here so the file drops
# into worker.py with no imports).
RATE_LIMIT_CAPACITY = 10
RATE_LIMIT_WINDOW_S = 300


class RateLimitResult(NamedTuple):
    allowed: bool
    retry_after_s: Optional[int]


def _to_py(value):
    """Mirror of the worker's `_to_py` (control-plane/worker.py).

    ← hosted/push_enqueue_async._to_py, identical: `.first()` with no
    match returns a JsNull proxy, not None, in the worker; objects
    with `.to_py()` convert. In-repo the shim already yields plain
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


async def _run(db, sql, params=()):
    """Run a write and return the raw result (worker shape: success +
    meta with `changes` / `last_row_id`)."""
    return await db.prepare(sql).bind(*params).run()


def _run_changes(raw):
    """Extract the touched-row count from a `.run()` result."""
    meta = _to_py(getattr(raw, "meta", None)) or {}
    return meta.get("changes", 0)


async def _first(db, sql, params=()):
    """Run a SELECT and return the first row as a dict, or None.

    Mirrors the worker's consumption idiom, like
    hosted/push_enqueue_async._first.
    """
    return _to_py(await db.prepare(sql).bind(*params).first())


_TAKE_SQL = (
    "UPDATE vend_rate_limit"
    " SET tokens = MIN(?, ROUND(tokens + (? - updated_at) * ?, 6)) - 1.0,"
    "     updated_at = ?"
    " WHERE box_id = ?"
    "   AND ROUND(tokens + (? - updated_at) * ?, 6) >= 1.0"
)


async def try_take_async(db, *, box_id, now=None,
                         capacity=RATE_LIMIT_CAPACITY,
                         window_s=RATE_LIMIT_WINDOW_S) -> RateLimitResult:
    """Take one mint token for ``box_id`` against the async `_D1`."""
    if not isinstance(box_id, str):
        raise TypeError("box_id must be str, got %s" % type(box_id).__name__)
    if not box_id:
        raise ValueError("box_id must be non-empty")
    if now is None:
        now = int(time.time())
    now = int(now)
    rate = capacity / window_s
    take_params = (capacity, now, rate, now, box_id, now, rate)

    if _run_changes(await _run(db, _TAKE_SQL, take_params)) == 1:
        return RateLimitResult(True, None)

    # D106 — fresh box (or lost the atomic take): INSERT OR IGNORE a
    # full bucket minus the one token this mint spends.
    if _run_changes(await _run(
            db,
            "INSERT OR IGNORE INTO vend_rate_limit"
            " (box_id, tokens, updated_at) VALUES (?, ?, ?)",
            (box_id, float(capacity) - 1.0, now))) == 1:
        return RateLimitResult(True, None)

    # Re-take once through the atomic gate before declaring the
    # denial (D106 race-loser path).
    if _run_changes(await _run(db, _TAKE_SQL, take_params)) == 1:
        return RateLimitResult(True, None)

    row = await _first(
        db, "SELECT tokens, updated_at FROM vend_rate_limit WHERE box_id = ?",
        (box_id,))
    if row is None:  # pragma: no cover — the row was INSERTed above.
        return RateLimitResult(False, window_s)
    refilled = min(float(capacity),
                   round(float(row["tokens"])
                         + (now - int(row["updated_at"])) * rate, 6))
    retry_after_s = max(1, int(math.ceil((1.0 - refilled) / rate)))
    return RateLimitResult(False, retry_after_s)
