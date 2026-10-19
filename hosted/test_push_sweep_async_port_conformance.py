"""D-PP-2 conformance tripwire for the async sweep PORT (#1566 S2-b1).

Arch finding (20261019-0559): `hosted/push_sweep_async.py`'s docstring
promises "the port must reproduce every
`hosted/push_sweep_port/recorded/` output" (D-PP-2), but
`hosted/test_push_sweep_port_conformance.py` only runs the SYNC sweep
against the records — the async port was held to zero CI-verified
conformance. A drift in the async hint SQL, pass order, isolation
handling, or truncation reporting would reach the plane silently (the
async module is what the plane workspace derives its sweep section
from). This test closes the gap: every recorded scenario also runs
through `push_sweep_async_tick`, and the serialized summary + DB state
must match the records exactly.

What this pins vs what it cannot pin (honest scope):

- PINNED: the async sweep's structure — the D68 hint query (candidate
  predicate, D75 anti-join, keyset pagination pinned by the
  `reminders_poisoned_multi_page` scenario; half-TTL exclusion pinned
  by `d68_half_ttl_boundary`), the D76/D1383 digest scan + truncation
  probe, pass order (reminders → digests → watchers), D78
  per-candidate isolation (poisoned dispositions, derivation-abort
  shape), D103 budget stops, D8 hint/gate agreement — and the async
  `make_record_adapter_async` SQL + full terminal derivation (decision,
  status, and clock branches; missing-row→None; corrupt-row→ValueError —
  pinned by the dedicated unit tests below).
  Disclosure: the `poisoned_candidate` conformance scenario exercises
  the sweep's D78 isolation through a sync-adapter wrapper (the
  fixture's poison adapter is a sync two-arg fn), not
  `make_record_adapter_async` — its pin is the sweep's poison handling,
  not the adapter.
- NOT pinned: the async policy port itself (the four async policy
  methods are shimmed here by awaiting the sweep's get_record, then
  calling the sync `hosted/push_events` functions against the same
  fixture database — the real async policy port is a later slice).
  A future async-policy bug is out of this test's scope; the sweep
  structure is in.

The `sweep_module_sha256` provenance pin in the recorded files is the
SYNC module's hash and is deliberately NOT asserted here — the port
reproducing the recorded *outputs* is the D-PP-2 requirement, not a
byte-identical module. If the sync module changes and the records are
re-recorded (`hosted/push_sweep_port/record.py`), this test re-pins
the port against the new records automatically.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from hosted import push_events, push_sweep_async
from hosted.push_sweep_port import conformance, scenarios


class _AsyncD1Statement:
    """One prepared statement against a sqlite3 connection.

    Enough of the worker's async `_D1` idiom for the sweep reads:
    `db.prepare(sql).bind(*params)` → `.all()` (list of dicts) /
    `.first()` (dict or None) / `.run()` (writes; the caller owns the
    commit — nothing in the sweep writes via `db`, so `.run()` is
    unexercised scaffolding, kept for the worker-idiom shape). Rows are
    dicts, mirroring the worker shape the port's `_to_py` already
    handles.
    """

    def __init__(self, conn, sql):
        self._conn = conn
        self._sql = sql
        self._params = ()

    def bind(self, *params):
        self._params = params
        return self

    def _dict_rows(self):
        cur = self._conn.execute(self._sql, self._params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    async def all(self):
        return self._dict_rows()

    async def first(self):
        rows = self._dict_rows()
        return rows[0] if rows else None

    async def run(self):
        cur = self._conn.execute(self._sql, self._params)
        return {"changes": cur.rowcount, "last_row_id": cur.lastrowid}


class _AsyncD1:
    """Async `_D1` shim over a sync sqlite3 connection (test harness).

    The plane's real `_D1` is async-only; the fixture database is the
    same sqlite the scenario builders use, so reads see the scenario
    state and the shim policy's sync writes land in the same
    transaction scope as the sync conformance run.
    """

    def __init__(self, conn):
        self._conn = conn

    def prepare(self, sql):
        return _AsyncD1Statement(self._conn, sql)


class _SyncShimPolicy:
    """The async policy boundary, shimmed over the sync policy (#1566 S2).

    The real async policy port is a later slice; this shim awaits the
    sweep's async `get_record` (exercising `make_record_adapter_async`
    per candidate), then calls the sync `hosted/push_events` policy
    functions against the same fixture connection. The sweep's
    structure — candidate selection, pass order, isolation, truncation,
    budget — is what's held to the records.
    """

    reminder_min_ttl_seconds = push_events.REMINDER_MIN_TTL_SECONDS

    def __init__(self, conn):
        self._conn = conn

    async def maybe_enqueue_reminder(self, db, *, box_id,
                                     owner_principal, aid, get_record,
                                     now):
        record = await get_record(aid)
        return push_events.maybe_enqueue_reminder(
            self._conn, box_id=box_id,
            owner_principal=owner_principal, aid=aid,
            get_record=lambda _a: record, now=now)

    async def maybe_enqueue_digest(self, db, *, owner_principal, now,
                                   window_start):
        return push_events.maybe_enqueue_digest(
            self._conn, owner_principal=owner_principal, now=now,
            window_start=window_start)

    async def on_heartbeat_stale(self, db, *, box_id, owner_principal,
                                 stale_epoch, now):
        return push_events.on_heartbeat_stale(
            self._conn, box_id=box_id, owner_principal=owner_principal,
            stale_epoch=stale_epoch, now=now)

    async def on_token_expiry_warning(self, db, *, box_id,
                                      owner_principal, token_hash,
                                      now):
        return push_events.on_token_expiry_warning(
            self._conn, box_id=box_id, owner_principal=owner_principal,
            token_hash=token_hash, now=now)


def _diff_paths(actual, expected, path):
    """Yield (path, actual, expected) for every divergence, list-ordered."""
    if type(actual) is not type(expected):
        yield (path, repr(actual), repr(expected))
        return
    if isinstance(actual, dict):
        for key in sorted(set(actual) | set(expected)):
            yield from _diff_paths(actual.get(key), expected.get(key),
                                   "%s[%r]" % (path, key))
    elif isinstance(actual, (list, tuple)):
        if len(actual) != len(expected):
            yield (path, "len=%d" % len(actual),
                   "len=%d" % len(expected))
            return
        for i, (a, e) in enumerate(zip(actual, expected)):
            yield from _diff_paths(a, e, "%s[%d]" % (path, i))
    elif actual != expected:
        yield (path, repr(actual), repr(expected))


def _run_async_scenario(scenario):
    """Build the fixture DB, run the ASYNC sweep, return the record dict."""
    conn = scenarios.new_db()
    try:
        spec = scenario["build"](conn)
        db = _AsyncD1(conn)
        policy = _SyncShimPolicy(conn)
        kwargs = dict(spec["sweep_kwargs"])
        kwargs["now"] = spec["now_epoch"]
        kwargs["resolve_owner"] = scenarios.registry(spec["registry"])
        kwargs["policy"] = policy
        if spec["derive_stale"] is not None:
            kwargs["derive_stale"] = scenarios.derive(
                spec["derive_stale"])
        elif spec.get("derive_stale_raiser"):
            def _raises(db, moment):
                raise RuntimeError(
                    "fixture poison: stale derivation failed at call time")

            kwargs["derive_stale"] = _raises
        if spec["derive_token_warnings"] is not None:
            kwargs["derive_token_warnings"] = scenarios.derive(
                spec["derive_token_warnings"])
        if spec["record_adapter"] is not None:
            sync_adapter = spec["record_adapter"]

            async def _adapter(db, box_id, aid,
                               _sync=sync_adapter):
                return _sync(box_id, aid)

            kwargs["record_adapter"] = _adapter
        summary = asyncio.run(
            push_sweep_async.push_sweep_async_tick(db, **kwargs))
        conn.commit()
        return {
            "summary": conformance.serialize_summary(summary),
            "db": conformance.serialize_db(conn),
        }
    finally:
        conn.close()


RECORDED_NAMES = {f[:-5] for f in os.listdir(conformance.RECORDED_DIR)
                  if f.endswith(".json")}


@pytest.mark.parametrize("scenario", scenarios.SCENARIOS,
                         ids=lambda s: s["name"])
def test_async_port_matches_recorded(scenario):
    """The async sweep reproduces the recorded outputs (D-PP-2, port half)."""
    name = scenario["name"]
    assert name in RECORDED_NAMES, (
        "scenario %r has no recorded outputs — run "
        "hosted/push_sweep_port/record.py first" % name)
    recorded = conformance.load_recorded(name)
    actual = _run_async_scenario(scenario)
    diffs = list(_diff_paths(actual["summary"], recorded["summary"],
                             "summary"))
    diffs += list(_diff_paths(actual["db"], recorded["db"], "db"))
    assert not diffs, (
        "async port diverged from recorded outputs for %r:\n%s" % (
            name, "\n".join("  %s: actual=%s expected=%s" % d
                            for d in diffs[:20])))


def test_recorded_names_match_scenarios():
    """No orphan or missing recorded files — the set is the source of truth."""
    assert RECORDED_NAMES == set(scenarios.scenario_names()), (
        "recorded/scenarios mismatch: extra=%s missing=%s"
        % (sorted(RECORDED_NAMES - set(scenarios.scenario_names())),
           sorted(set(scenarios.scenario_names()) - RECORDED_NAMES)))


def _adapter_db():
    """Fixture approvals DB for the async record-adapter unit tests."""
    conn = scenarios.new_db()
    # Live pending approval: ttl=600, age=400 → not clock-terminal.
    scenarios.file_approval(conn, "box-a", "live", ttl=600, age=400)
    # Decision-terminal: decided while still pending by the clock.
    scenarios.file_approval(conn, "box-a", "decided", ttl=600, age=400,
                            decision="approve")
    # Status-terminal: approved status, no decision text.
    scenarios.file_approval(conn, "box-a", "statusdone", ttl=600,
                            age=400, status="approved")
    # Clock-terminal: pending but past expires_at.
    scenarios.file_approval(conn, "box-a", "clockdone", ttl=600,
                            age=700)
    # Corrupt: non-int epoch.
    scenarios.file_approval(conn, "box-a", "corrupt", ttl=600, age=400)
    conn.execute("UPDATE approvals SET created_at = 'not-an-int'"
                 " WHERE box_id = 'box-a' AND aid = 'corrupt'")
    conn.commit()
    return _AsyncD1(conn)


def _read(db, box_id, aid):
    adapter = push_sweep_async.make_record_adapter_async(
        db, scenarios.EPOCH_T0)
    return asyncio.run(adapter(db, box_id, aid))


def test_record_adapter_async_live():
    rec = _read(_adapter_db(), "box-a", "live")
    assert rec["ttl_seconds"] == 600
    assert rec["terminal"] is False
    created = scenarios.EPOCH_T0 - 400
    assert rec["created_at"] == datetime.fromtimestamp(
        created, tz=timezone.utc).isoformat()


def test_record_adapter_async_decision_terminal():
    rec = _read(_adapter_db(), "box-a", "decided")
    assert rec["terminal"] is True


def test_record_adapter_async_status_terminal():
    rec = _read(_adapter_db(), "box-a", "statusdone")
    assert rec["terminal"] is True


def test_record_adapter_async_clock_terminal():
    rec = _read(_adapter_db(), "box-a", "clockdone")
    assert rec["terminal"] is True


def test_record_adapter_async_missing_row():
    assert _read(_adapter_db(), "box-a", "nope") is None


def test_record_adapter_async_corrupt_row():
    db = _adapter_db()
    adapter = push_sweep_async.make_record_adapter_async(
        db, scenarios.EPOCH_T0)
    with pytest.raises(ValueError):
        asyncio.run(adapter(db, "box-a", "corrupt"))
