"""Per-box mint rate limiter for the credential-vend plane endpoint (#1405).

`docs/CREDENTIAL_VEND_CONTRACT.md` §2.2 claims the plane "additionally
rate-limits mints per box (`429` — precedent: the pairing 50-pending
cap)". The cited precedent is a *count* cap (`MAX_PENDING_PAIRINGS`),
not a rate limit, and no rate-limiting mechanism existed anywhere in
the worker — a compromised box minting in a tight loop gets a
`vend_audit` row and a decrypt op per mint, with no bound on the D1
write amplification. This module is the mechanism (D105):

- **D1-backed token bucket, per `(box_id)`.** Capacity
  ``RATE_LIMIT_CAPACITY`` mints per ``RATE_LIMIT_WINDOW_S`` seconds;
  the take is one atomic single-statement UPDATE (the #990 lesson —
  CTE-wrapped UPDATEs report ``rowcount=-1`` under Python's sqlite3,
  so no CTE), refill computed inline from ``updated_at``.
- **D105 — vend mint rate limit.** Capacity 10 mints / 300 s / box.
  The §2.3 minimum TTL is 300 s, so the legitimate cadence is already
  ~1 mint request per 300 s per box (all due names batched per the
  contract §5 discipline, D-VC15) — the bucket never touches
  legitimate traffic; it only bounds a compromised box's tight loop
  (the D1 write-amplification bound is the point, not throttling
  tenants).
  The 429 + ``Retry-After`` shape is the contract §2.2 sentence; the
  endpoint that emits it is #890's scope (this module answers
  allowed/denied + the advisory ``retry_after_s``).
- **D106 — first-mint race.** The take UPDATE misses on a fresh box;
  the follow-up ``INSERT OR IGNORE`` + re-UPDATE keeps a concurrent
  double-first-mint from double-spending: at most one INSERT wins, the
  loser re-takes the atomic UPDATE. Every take from an existing row is
  one atomic decrement-or-refill under the ``>= 1.0`` gate (the D106
  INSERT grant is the one exception: a fresh full bucket, no gate —
  the spend is still exactly one token), so no interleaving can spend
  more than capacity per window, whatever the concurrency.
- **Fail-closed typing:** a non-``str`` ``box_id`` raises ``TypeError``
  immediately (the module never lets a mistyped identity reach the
  WHERE clause). ``now`` is integer seconds; float dust from the
  fractional refill is snapped with ``ROUND(..., 6)`` inside the
  statement so a microscopically-short refill never denies a take a
  full window owed.
- **``retry_after_s`` is advisory**, not a second atomic gate: it is
  computed from a SELECT after the denied take, so a concurrent
  consumer can move the bucket between the two statements. The
  denial itself is airtight (the single UPDATE); the hint tells the
  endpoint what ``Retry-After`` to name.
- **Trust posture (D2).** This module never accepts a box-asserted
  identity it can verify: the caller resolves the bearer token to
  ``box_id`` (the #844 box-bearer gate) and passes the resolved id in;
  a hostile box that supplies its own ``box_id`` string must be
  rejected upstream — this module cannot distinguish it. The module
  grants no identity, only decrements buckets keyed by the given id.
- **No-DELETE invariant.** Rows in ``vend_rate_limit`` are never
  deleted: a deleted row resurrects as a full bucket on the next take
  (fail-open). Any future retention/GC work must age rows out, never
  drop them.

This module is the in-repo sync test truth (the D-PP-1 pattern):
`hosted/vend_rate_limit_async.py` is its async plane port, droppable
into `worker.py` verbatim.
"""

import math
import time
from typing import NamedTuple, Optional


# D105 — the bucket. 10 mints per 300 s per box: at the §2.3 minimum
# TTL the legitimate cadence is ~1 mint request / 300 s / box (all due
# names batched per the contract §5 discipline, D-VC15), so this only
# ever fires on abuse loops.
RATE_LIMIT_CAPACITY = 10
RATE_LIMIT_WINDOW_S = 300


class RateLimitResult(NamedTuple):
    allowed: bool
    # Advisory seconds until the next take should succeed (None when
    # allowed). The #890 endpoint maps denied -> 429 + Retry-After.
    retry_after_s: Optional[int]


def ensure_schema(conn) -> None:
    """Create the ``vend_rate_limit`` table (idempotent).

    ``tokens`` is REAL (fractional refill); ``updated_at`` is integer
    unix seconds. One row per box; the contract's §2.4 D1 schema names
    this table.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS vend_rate_limit ("
        " box_id TEXT PRIMARY KEY,"
        " tokens REAL NOT NULL,"
        " updated_at INTEGER NOT NULL)"
    )


_TAKE_SQL = (
    "UPDATE vend_rate_limit"
    " SET tokens = MIN(?, ROUND(tokens + (? - updated_at) * ?, 6)) - 1.0,"
    "     updated_at = ?"
    " WHERE box_id = ?"
    "   AND ROUND(tokens + (? - updated_at) * ?, 6) >= 1.0"
)


def try_take(conn, *, box_id, now=None,
             capacity=RATE_LIMIT_CAPACITY,
             window_s=RATE_LIMIT_WINDOW_S) -> RateLimitResult:
    """Take one mint token for ``box_id``; return allowed/denied.

    Atomic: the single UPDATE both refills (capped at ``capacity``)
    and spends under the ``>= 1.0`` gate — concurrent takers serialize
    in the writer, so the bucket can never over-spend.
    """
    if not isinstance(box_id, str):
        raise TypeError("box_id must be str, got %s" % type(box_id).__name__)
    if not box_id:
        raise ValueError("box_id must be non-empty")
    if now is None:
        now = int(time.time())
    now = int(now)
    rate = capacity / window_s

    cur = conn.execute(
        _TAKE_SQL, (capacity, now, rate, now, box_id, now, rate))
    if cur.rowcount == 1:
        return RateLimitResult(True, None)

    # D106 — fresh box (or lost the atomic take): INSERT OR IGNORE a
    # full bucket minus the one token this mint spends. The loser of a
    # concurrent double-first-mint falls through to the re-take below.
    cur = conn.execute(
        "INSERT OR IGNORE INTO vend_rate_limit (box_id, tokens, updated_at)"
        " VALUES (?, ?, ?)",
        (box_id, float(capacity) - 1.0, now))
    if cur.rowcount == 1:
        return RateLimitResult(True, None)

    # The bucket exists but is empty (or a concurrent taker just won
    # the INSERT race — re-take once through the atomic gate before
    # declaring the denial, so the race loser is not denied a token
    # the bucket actually holds).
    cur = conn.execute(
        _TAKE_SQL, (capacity, now, rate, now, box_id, now, rate))
    if cur.rowcount == 1:
        return RateLimitResult(True, None)

    row = conn.execute(
        "SELECT tokens, updated_at FROM vend_rate_limit WHERE box_id = ?",
        (box_id,)).fetchone()
    if row is None:  # pragma: no cover — the row was INSERTed above.
        return RateLimitResult(False, window_s)
    tokens, updated_at = row[0], row[1]
    refilled = min(float(capacity),
                   round(float(tokens) + (now - int(updated_at)) * rate, 6))
    retry_after_s = max(1, int(math.ceil((1.0 - refilled) / rate)))
    return RateLimitResult(False, retry_after_s)
