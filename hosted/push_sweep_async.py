"""The D9 sweep's async plane port (#1566 S2-b1).

The canonical async rewrite of `hosted/push_sweep.py` against the plane
worker's async `_D1` (F-PP-2: the worker exposes no synchronous D1, so
the port is a rewrite, not a copy). The in-repo sync module stays the
harness and test truth (D-PP-1); this module is what the plane
workspace's `control-plane/worker.py` derives its
`# --- BEGIN push_sweep_async (#1566 S2) ---` section from at deploy
time (D-PP-5 order — the deploy itself is S2-b2/S2-c, not this slice).

Entry point (per `deploy/plane-cron/CRON_TRIGGER_CONTRACT.md` §2):

    async def push_sweep_async_tick(db, *, now, resolve_owner, policy,
                                    reminders_enabled=True, ...)

`db` is the worker's async `_D1`: `db.prepare(sql)` → `.bind(*params)`
→ `await .all()` / `await .first()` / `await .run()`. Rows arrive as
dicts (or None from `.first()` on no match) after `_to_py` — the same
shape the worker's `_D1` wrapper produces.

`policy` is the async policy boundary — an object with four async
methods mirroring `hosted/push_events` minus the sync `conn`, plus the
D8 constant:

- `await policy.maybe_enqueue_reminder(db, *, box_id, owner_principal,
  aid, get_record, now)` → object with `.disposition`
- `await policy.maybe_enqueue_digest(db, *, owner_principal, now,
  window_start)` → object with `.disposition`
- `await policy.on_heartbeat_stale(db, *, box_id, owner_principal,
  stale_epoch, now)` → object with `.disposition`
- `await policy.on_token_expiry_warning(db, *, box_id,
  owner_principal, token_hash, now)` → object with `.disposition`
- `policy.reminder_min_ttl_seconds` — the D8 bound, single-sourced
  with the policy's gate by construction (#1507: the sweep's hint
  predicate must agree with the policy's gate, so it reads the
  policy's value — never a second local definition).

The async policy port itself is the next slice; this slice pins the
sweep's async structure. `get_record` passed to the policy is an async
one-arg `(aid)` reader; the sweep's two-arg `(db, box_id, aid)`
`record_adapter` (default `make_record_adapter_async`) is bridged
per-candidate, exactly like the sync sweep.

Derivations (`derive_stale`, `derive_token_warnings`) may return a
sync iterable (tests) or an async iterable (the worker's async
generators) — the watcher driver handles both, with the same D78
isolation and D103 abandonment contract either way.

Conformance (D-PP-2): the port must reproduce every
`hosted/push_sweep_port/recorded/` output. The port returns the same
`SweepSummary` field set as the sync sweep — `conformance.py`'s
`serialize_summary` asserts the field set, so a drifted summary fails
the tripwire instead of silently passing.

Pure-compute helpers are inlined with source citations (the ed25519
precedent): `_hour_bucket` ← `push_enqueue.hour_bucket`;
`_to_py` mirrors the worker's `_to_py` (JsNull → None, `.to_py()`
duck-type) so this file is droppable into `worker.py` verbatim.
"""

from __future__ import annotations

import math
import sys
import time
from collections import namedtuple
from datetime import datetime, timezone

# D69 — bounded work per sweep (mirrors the sync sweep's defaults).
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 100

# D1383 — bounded work per sweep, digest pass (mirrors the sync sweep).
DEFAULT_MAX_DIGEST_WINDOWS = 1000

SweepSummary = namedtuple(
    "SweepSummary",
    ["reminders", "digests", "stale_watchers", "token_warnings",
     "candidates_seen", "pages_truncated", "reminders_enabled", "notes",
     "budget_truncated", "digests_truncated"],
    defaults=[(), False, False])
# Field set MUST stay identical to hosted/push_sweep.py's SweepSummary —
# hosted/push_sweep_port/conformance.py's serialize_summary asserts the
# set, which is the anti-drift for this duplication.

ReminderPassResult = namedtuple(
    "ReminderPassResult",
    ["dispositions", "candidates_seen", "pages_truncated",
     "budget_truncated"],
    defaults=[False])

DigestPassResult = namedtuple(
    "DigestPassResult",
    ["dispositions", "windows_seen", "windows_truncated",
     "budget_truncated"],
    defaults=[False])


def _to_py(value):
    """Mirror of the worker's `_to_py` (control-plane/worker.py).

    `.first()` with no match returns a JsNull proxy, not None; objects
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


async def _rows(db, sql, params=()):
    """Run a SELECT and return the rows as a list of dicts (worker shape).

    Mirrors the worker's consumption idiom:
    `_to_py(getattr(await db.prepare(sql).bind(*params).all(),
    "results", ...)) or []`.
    """
    raw = await db.prepare(sql).bind(*params).all()
    return list(_to_py(getattr(raw, "results", raw)) or [])


async def _first(db, sql, params=()):
    """Run a SELECT and return the first row as a dict, or None."""
    return _to_py(await db.prepare(sql).bind(*params).first())


def _hour_bucket(moment):
    """UTC hour bucket, the contract's `window_start` format (YYYY-MM-DDTHH).

    Inlined copy of `hosted/push_enqueue.hour_bucket` (pure compute —
    the ed25519 precedent): the worker's marked section cannot import
    the repo's hosted package, so the port carries the function. Any
    change to the source must be mirrored here (and vice versa).
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def _utcnow(now=None):
    """Normalize the sweep's single clock reading (D73).

    Same contract as the sync sweep's `_utcnow`: aware/naive datetime
    (naive assumed UTC) or epoch seconds; anything else is a
    ValueError; non-finite or out-of-range epochs are ValueError.
    """
    if now is None:
        return datetime.now(timezone.utc)
    if isinstance(now, bool):
        raise ValueError("now must be a datetime or epoch seconds")
    if isinstance(now, (int, float)):
        if isinstance(now, float) and not math.isfinite(now):
            raise ValueError("now must be a finite datetime or epoch "
                             "seconds, not %r" % (now,))
        try:
            return datetime.fromtimestamp(now, tz=timezone.utc)
        except (OverflowError, OSError) as exc:
            raise ValueError("epoch seconds out of range: %r"
                             % (now,)) from exc
    if isinstance(now, datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)
    raise ValueError("now must be a datetime or epoch seconds, not %r"
                     % (type(now).__name__,))


def _require_resolve_owner(resolve_owner):
    if not callable(resolve_owner):
        raise ValueError(
            "resolve_owner must be callable (D2: owner identity comes from"
            " the enrollment registry, never from a box assertion)")


def _require_policy(policy):
    for name in ("maybe_enqueue_reminder", "maybe_enqueue_digest",
                 "on_heartbeat_stale", "on_token_expiry_warning"):
        if not callable(getattr(policy, name, None)):
            raise ValueError(
                "policy.%s must be callable (the async policy boundary)"
                % name)
    ttl = getattr(policy, "reminder_min_ttl_seconds", None)
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)):
        raise ValueError(
            "policy.reminder_min_ttl_seconds must be a number "
            "(D8 single-source, #1507)")


def _validate_budget_arg(name, value):
    """Fail-closed validation for the D103 tick-bound args (the D96 discipline)."""
    if value is not None and (isinstance(value, bool)
                              or not isinstance(value, (int, float))
                              or not math.isfinite(value)
                              or value < 0):
        raise ValueError(
            "%s must be a finite non-negative number or None" % name)


def _validate_positive_int(name, value):
    """Fail-closed validation for the per-pass work-cap args."""
    if not isinstance(value, int) or isinstance(value, bool) \
            or value <= 0:
        raise ValueError("%s must be a positive int" % name)


def _deadline_reached(deadline):
    """True once the sweep's wall-clock budget is spent (D103)."""
    return deadline is not None and time.monotonic() >= deadline


def _resolve_owner(resolve_owner, box_id):
    _require_key_material("box_id", box_id)
    owner = resolve_owner(box_id)
    _require_key_material("owner_principal", owner)
    return owner


def _require_key_material(name, value):
    if isinstance(value, bool) or not isinstance(value, str) or not value:
        raise ValueError("%s must be a non-empty str" % name)
    if "\x00" in value:
        raise ValueError("%s must not contain U+0000" % name)


def _loud(msg):
    """Emit a loud operator-visible line (D78). Never raises."""
    try:
        print("[push_sweep_async] " + msg, file=sys.stderr, flush=True)
    except Exception:
        pass


async def _isolate_candidate_async(counts, pass_name, identity, fn):
    """Run one candidate's sweep body with per-candidate isolation (D78).

    Async mirror of the sync sweep's `_isolate_candidate`: a raising
    candidate is counted `poisoned`, logged loudly with its identity,
    and skipped — the pass continues. Only `Exception` is caught.
    """
    try:
        await fn()
    except Exception as exc:  # noqa: BLE001 — per-candidate isolation is the point
        counts["poisoned"] = counts.get("poisoned", 0) + 1
        _loud("%s: poisoned candidate %s: %r — pass continues"
              % (pass_name, identity, exc))


async def _close_abandoned_async(abandon, label):
    """Run the derivation's abandonment hook; never fatal (D103)."""
    try:
        await abandon()
    except Exception as exc:  # noqa: BLE001 — cleanup must not kill the sweep
        _loud("%s: derivation abandon raised: %r — continuing"
              % (label, exc))


async def _drive_watcher_async(counts, label, derive, db, moment, on_item,
                               deadline=None):
    """Drive one watcher derivation with per-candidate isolation (D78).

    Async mirror of the sync sweep's `_drive_watcher`. `derive` is
    called as `derive(db, moment)` and may return a sync iterable (the
    in-repo derivations, tests) or an async iterable (the worker's
    async generators — DB reads inside derivations). Either way: each
    yielded item is an isolated candidate; a derivation that raises
    mid-iteration is one loud `poisoned` count and *that watcher*
    stops; the D103 deadline is checked before every item and the
    derivation is abandoned deterministically on exhaustion
    (`aclose()` for async iterables — GeneratorExit delivery —
    `close()` for sync ones, mirroring the sync sweep's
    `_close_abandoned` contract: derivations must tolerate abandonment
    at any yield, no open transactions across yields).
    """
    if _deadline_reached(deadline):
        counts["budget_exhausted"] = True
        _loud("%s: time budget already exhausted — watcher skipped; "
              "items stay due for the next tick" % label)
        return
    try:
        produced = derive(db, moment)
        if not hasattr(produced, "__aiter__"):
            produced = iter(produced)
    except Exception as exc:  # noqa: BLE001 — see _isolate_candidate_async
        counts["poisoned"] = counts.get("poisoned", 0) + 1
        _loud("%s: poisoned derivation (failed at call time): %r — "
              "watcher stops, other watchers continue"
              % (label, exc))
        return
    if hasattr(produced, "__aiter__"):
        aiterator = produced.__aiter__()

        async def _next():
            try:
                return (True, await aiterator.__anext__())
            except StopAsyncIteration:
                return (False, None)

        async def _abandon():
            aclose = getattr(produced, "aclose", None)
            if aclose is not None:
                await _close_abandoned_async(aclose, label)
    else:
        iterator = produced

        async def _next():
            try:
                return (True, next(iterator))
            except StopIteration:
                return (False, None)

        async def _abandon():
            close = getattr(iterator, "close", None)
            if close is not None:
                await _close_abandoned_async(
                    _async_close(close), label)

    while True:
        if _deadline_reached(deadline):
            counts["budget_exhausted"] = True
            await _abandon()
            _loud("%s: time budget exhausted — watcher stops; "
                  "unreached items stay due for the next tick"
                  % label)
            return
        try:
            ok, item = await _next()
        except Exception as exc:  # noqa: BLE001 — see _isolate_candidate_async
            counts["poisoned"] = counts.get("poisoned", 0) + 1
            _loud("%s: poisoned derivation (raised mid-iteration): %r — "
                  "watcher stops, other watchers continue"
                  % (label, exc))
            return
        if not ok:
            return
        await _isolate_candidate_async(counts, label, repr(item),
                                       lambda _it=item: on_item(_it))


def _async_close(close):
    """Adapt a sync close() callable to the async abandon hook shape."""
    async def _run():
        close()
    return _run


def make_record_adapter_async(db, now):
    """Build the D49-style D59 reader adapter for the async sweep.

    Async mirror of the sync sweep's `make_record_adapter`: runs the
    documented SELECT against the async `_D1` and builds the D59 dict
    `{"created_at": <full ISO-8601>, "ttl_seconds": <int>,
    "terminal": <bool>}`. Signature is `(db, box_id, aid)` — the
    sweep's adapter shape; the sweep bridges it per-candidate into the
    policy's async one-arg D59 reader. Missing row → None; corrupt
    row → ValueError (D59 fail-loud).
    """
    moment = _utcnow(now)
    moment_epoch = moment.timestamp()

    async def get_record(db, box_id, aid):
        _require_key_material("box_id", box_id)
        _require_key_material("aid", aid)
        row = await _first(
            db,
            "SELECT created_at, expires_at, decision, status FROM approvals"
            " WHERE box_id = ? AND aid = ?", (box_id, aid))
        if row is None:
            return None
        created_at, expires_at = row["created_at"], row["expires_at"]
        decision, status = row["decision"], row["status"]
        for name, value in (("created_at", created_at),
                            ("expires_at", expires_at)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    "approvals %s for (%r, %r) must be an epoch int, not %r"
                    % (name, box_id, aid, value))
        if decision is not None and not isinstance(decision, str):
            raise ValueError(
                "approvals decision for (%r, %r) must be a str or null"
                % (box_id, aid))
        if status not in ("pending", "approved", "denied", "expired"):
            raise ValueError(
                "approvals status for (%r, %r) must be pending|approved|"
                "denied|expired, not %r" % (box_id, aid, status))
        ttl = expires_at - created_at
        terminal = (
            decision is not None
            or status in ("approved", "denied", "expired")
            or (status == "pending" and moment_epoch >= expires_at))
        return {
            "created_at": datetime.fromtimestamp(
                created_at, tz=timezone.utc).isoformat(),
            "ttl_seconds": ttl,
            "terminal": terminal,
        }

    return get_record


async def _reminder_candidates_async(db, now_epoch, page_size, max_pages,
                                     reminder_min_ttl_seconds):
    """Yield (box_id, aid) candidate pages per the D68 hint query.

    Async mirror of the sync sweep's `_reminder_candidates`: the same
    keyset-paginated SELECT with the same D75 anti-join (the
    exclusion is precise — only candidates the policy would certainly
    `duplicate`), the same `page_size`/`max_pages` D69 discipline, and
    the same trailing `{"__meta__": {"truncated": ...}}` marker.
    `reminder_min_ttl_seconds` is the policy's D8 bound (the hint must
    agree with the gate it feeds — #1507).
    """
    last_box, last_aid = None, None
    pages = 0
    truncated = False
    while True:
        if pages >= max_pages:
            truncated = True
            break
        where = (
            "WHERE status = 'pending' AND decision_seq IS NULL"
            " AND created_at + (expires_at - created_at) / 2 <= ?"
            " AND (expires_at - created_at) >= ?"
            " AND NOT EXISTS ("
            "  SELECT 1 FROM push_send_results r"
            "  WHERE r.box_id = approvals.box_id"
            "    AND r.event_kind = 'reminder'"
            "    AND r.event_key ="
            "        approvals.box_id || char(0) || approvals.aid"
            "    AND approvals.decision IS NULL"
            "    AND approvals.expires_at > ?"
            "    AND typeof(approvals.created_at) = 'integer'"
            "    AND typeof(approvals.expires_at) = 'integer'"
            ")")
        params = [now_epoch, reminder_min_ttl_seconds, now_epoch]
        if last_box is not None:
            where += " AND (box_id > ? OR (box_id = ? AND aid > ?))"
            params += [last_box, last_box, last_aid]
        rows = await _rows(
            db,
            "SELECT box_id, aid FROM approvals " + where +
            " ORDER BY box_id, aid LIMIT ?", params + [page_size])
        pages += 1
        if not rows:
            break
        last_box, last_aid = rows[-1]["box_id"], rows[-1]["aid"]
        yield [(r["box_id"], r["aid"]) for r in rows]
        if len(rows) < page_size:
            break
    yield {"__meta__": {"truncated": truncated}}


async def sweep_reminders_async(db, *, now=None, resolve_owner, policy,
                                record_adapter=None,
                                page_size=DEFAULT_PAGE_SIZE,
                                max_pages=DEFAULT_MAX_PAGES,
                                reminders_enabled=True, deadline=None):
    """Pass 1: due reminders — async mirror of the sync sweep's pass 1.

    For every candidate the sweep calls the policy's async
    `maybe_enqueue_reminder` with the D59 dict bridge — the sweep never
    re-implements timing, dedup, or budget (D70). Each candidate is
    isolated (D78); the D103 deadline stops the pass with
    `budget_truncated` (not `pages_truncated` — different stop,
    different remediation).
    """
    if not reminders_enabled:
        return ReminderPassResult({"skipped": True}, 0, False)
    _require_resolve_owner(resolve_owner)
    _require_policy(policy)
    _validate_positive_int("page_size", page_size)
    _validate_positive_int("max_pages", max_pages)
    moment = _utcnow(now)
    now_epoch = moment.timestamp()
    adapter = record_adapter if record_adapter is not None else \
        make_record_adapter_async(db, moment)
    counts = {}
    if _deadline_reached(deadline):
        counts["budget_exhausted"] = True
        _loud("reminders: time budget already exhausted — pass skipped;"
              " candidates stay due for the next tick")
        return ReminderPassResult(counts, 0, False, True)
    seen, truncated = 0, False
    agen = _reminder_candidates_async(
        db, now_epoch, page_size, max_pages,
        policy.reminder_min_ttl_seconds)
    async for page in agen:
        if isinstance(page, dict):
            truncated = page["__meta__"]["truncated"]
            break
        for box_id, aid in page:
            if _deadline_reached(deadline):
                counts["budget_exhausted"] = True
                _loud("reminders: time budget exhausted — pass stops;"
                      " unreached candidates stay due for the next tick")
                return ReminderPassResult(counts, seen, False, True)

            async def _one(_box=box_id, _aid=aid):
                owner_principal = _resolve_owner(resolve_owner, _box)

                async def get_record(_aid2, _b=_box):
                    return await adapter(db, _b, _aid2)

                r = await policy.maybe_enqueue_reminder(
                    db, box_id=_box, owner_principal=owner_principal,
                    aid=_aid, get_record=get_record, now=moment)
                counts[r.disposition] = counts.get(r.disposition, 0) + 1
            seen += 1
            await _isolate_candidate_async(
                counts, "reminders",
                "box_id=%r aid=%r" % (box_id, aid), _one)
    return ReminderPassResult(counts, seen, truncated)


async def sweep_digests_async(db, *, now=None, deadline=None,
                              policy=None,
                              max_windows=DEFAULT_MAX_DIGEST_WINDOWS):
    """Pass 2: the D54 digest trigger — async mirror of the sync sweep's pass 2.

    Fires the policy's async `maybe_enqueue_digest` for every pending
    digest window (`count > 0`, `enqueued_at IS NULL`), oldest first
    (D76, D1383). Runs after the reminder pass (D67). Each window is
    isolated (D78); the D103 deadline stops the pass with
    `budget_exhausted`; the D1383 window cap reports
    `windows_truncated`.
    """
    _validate_positive_int("max_windows", max_windows)
    _require_policy(policy)
    moment = _utcnow(now)
    if _deadline_reached(deadline):
        _loud("digests: time budget already exhausted — pass skipped;"
              " windows stay pending for the next tick")
        return DigestPassResult({"budget_exhausted": True}, 0, False, True)
    current = _hour_bucket(moment)
    # D1383: read one row past the cap — fetching exactly max_windows
    # rows cannot distinguish "exactly full" from "truncated".
    rows = await _rows(
        db,
        "SELECT owner_principal, window_start FROM push_digest_state"
        " WHERE count > 0 AND enqueued_at IS NULL"
        " AND window_start <= ?"
        " ORDER BY window_start, owner_principal"
        " LIMIT ?", (current, max_windows + 1))
    truncated = len(rows) > max_windows
    if truncated:
        _loud("digests: pending-window scan truncated at %d windows —"
              " remainder stays pending for the next tick"
              % max_windows)
    counts = {}
    seen = 0
    for row in rows[:max_windows]:
        if _deadline_reached(deadline):
            counts["budget_exhausted"] = True
            _loud("digests: time budget exhausted — pass stops;"
                  " unfired windows stay pending for the next tick")
            break

        async def _one(_owner=row["owner_principal"],
                       _window=row["window_start"]):
            r = await policy.maybe_enqueue_digest(
                db, owner_principal=_owner, now=moment,
                window_start=_window)
            counts[r.disposition] = counts.get(r.disposition, 0) + 1
        await _isolate_candidate_async(
            counts, "digests",
            "owner=%r window=%r" % (row["owner_principal"],
                                    row["window_start"]), _one)
        seen += 1
    return DigestPassResult(counts, seen, truncated,
                            "budget_exhausted" in counts)


async def sweep_watchers_async(db, *, now=None, resolve_owner=None,
                               policy=None, derive_stale=None,
                               derive_token_warnings=None, deadline=None):
    """Pass 3: the cadence-driven watchers — async mirror of pass 3.

    `derive_stale(db, moment)` yields `(box_id, stale_epoch)`;
    `derive_token_warnings(db, moment)` yields `(box_id, token_hash)`.
    Both stay plane-side caller logic; the sweep only supplies the
    cadence and resolves owners from the registry (D2). A None
    derivation means the watcher is not wired — the pass reports
    "skipped". Each yielded item is an isolated candidate (D78); a
    derivation that raises stops only its own watcher.
    """
    _require_policy(policy)
    moment = _utcnow(now)
    stale_counts = {}
    if derive_stale is not None:
        _require_resolve_owner(resolve_owner)

        async def _stale(item, _resolve=resolve_owner):
            box_id, stale_epoch = item
            owner_principal = _resolve_owner(_resolve, box_id)
            r = await policy.on_heartbeat_stale(
                db, box_id=box_id, owner_principal=owner_principal,
                stale_epoch=stale_epoch, now=moment)
            stale_counts[r.disposition] = \
                stale_counts.get(r.disposition, 0) + 1
        await _drive_watcher_async(stale_counts, "stale_watchers",
                                   derive_stale, db, moment, _stale,
                                   deadline=deadline)
    else:
        stale_counts = {"skipped": True}
    warning_counts = {}
    if derive_token_warnings is not None:
        _require_resolve_owner(resolve_owner)

        async def _warn(item, _resolve=resolve_owner):
            box_id, token_hash = item
            owner_principal = _resolve_owner(_resolve, box_id)
            r = await policy.on_token_expiry_warning(
                db, box_id=box_id, owner_principal=owner_principal,
                token_hash=token_hash, now=moment)
            warning_counts[r.disposition] = \
                warning_counts.get(r.disposition, 0) + 1
        await _drive_watcher_async(warning_counts, "token_warnings",
                                   derive_token_warnings, db, moment,
                                   _warn, deadline=deadline)
    else:
        warning_counts = {"skipped": True}
    return {"stale": stale_counts, "token_warnings": warning_counts}


async def push_sweep_async_tick(db, *, now=None, resolve_owner, policy,
                                record_adapter=None,
                                page_size=DEFAULT_PAGE_SIZE,
                                max_pages=DEFAULT_MAX_PAGES,
                                reminders_enabled=True, derive_stale=None,
                                derive_token_warnings=None,
                                time_budget_s=None, tick_interval_s=None,
                                max_windows=DEFAULT_MAX_DIGEST_WINDOWS):
    """Run one full async D9 sweep: reminders, then digests, then watchers.

    The plane port's entry point (per the §2 async amendment):
    `push_sweep_async_tick(db, *, now, resolve_owner, reminders_enabled=True)`
    — `db` is the worker's async `_D1`, `now` is taken once and
    threaded through every pass (D73), `resolve_owner(box_id)` is the
    D2 enrollment-registry resolver, `policy` is the async policy
    boundary (required — never guessed).

    D103 — `time_budget_s` / `tick_interval_s` mirror the sync sweep
    (fail-closed validation; wall-clock via `time.monotonic()`).
    D1383 — `max_windows` bounds the digest pass's pending-window
    scan, oldest first.

    Returns a SweepSummary with the same field set as the sync sweep
    (the D-PP-2 serializer pins it).
    """
    _validate_budget_arg("time_budget_s", time_budget_s)
    _validate_budget_arg("tick_interval_s", tick_interval_s)
    _validate_positive_int("max_windows", max_windows)
    _require_policy(policy)
    moment = _utcnow(now)
    tick_start = time.monotonic()
    deadline = (tick_start + time_budget_s
                if time_budget_s is not None else None)
    rem = await sweep_reminders_async(
        db, now=moment, resolve_owner=resolve_owner, policy=policy,
        record_adapter=record_adapter, page_size=page_size,
        max_pages=max_pages, reminders_enabled=reminders_enabled,
        deadline=deadline)
    dig = await sweep_digests_async(db, now=moment, deadline=deadline,
                                    policy=policy,
                                    max_windows=max_windows)
    watchers = await sweep_watchers_async(
        db, now=moment, resolve_owner=resolve_owner, policy=policy,
        derive_stale=derive_stale,
        derive_token_warnings=derive_token_warnings,
        deadline=deadline)
    notes = []
    duration_s = time.monotonic() - tick_start
    if tick_interval_s is not None and duration_s > tick_interval_s:
        msg = ("sweep ran %.1fs, exceeding the %.1fs schedule interval"
               " — the next tick may have overlapped"
               % (duration_s, tick_interval_s))
        _loud("push_sweep_async_tick: tick_overrun — " + msg)
        notes.append(("tick_overrun", msg))
    budget_truncated = (
        rem.budget_truncated
        or "budget_exhausted" in dig.dispositions
        or "budget_exhausted" in watchers["stale"]
        or "budget_exhausted" in watchers["token_warnings"])
    return SweepSummary(
        reminders=rem.dispositions,
        digests=dig.dispositions,
        stale_watchers=watchers["stale"],
        token_warnings=watchers["token_warnings"],
        candidates_seen=rem.candidates_seen,
        pages_truncated=rem.pages_truncated,
        reminders_enabled=reminders_enabled,
        notes=tuple(notes),
        budget_truncated=budget_truncated,
        digests_truncated=dig.windows_truncated)
