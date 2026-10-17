"""D-PP-2 sweep-structure conformance for the async plane port (#1566 S2-b1).

Replays every `hosted/push_sweep_port` scenario through
`hosted/push_sweep_async.push_sweep_async_tick` and diffs the summary +
database state against the checked-in recorded outputs — the same
records the sync sweep produced. A green run proves the async sweep's
structure (pass order, candidate selection, D75 anti-join, pagination,
D103 budget, D78 isolation, owner resolution, summary shape) drives
the policy identically to the sync sweep.

What this proves and what it does not: the policy calls go through an
async test shim that delegates to the SYNC in-repo policy
(`hosted/push_events`) over the same sqlite3 connection — so this test
pins the sweep's async structure, not the async policy port. The async
policy port is the next slice; when it lands, the same fixtures replay
through the full-async stack. The delegation is honest about its
scope: any divergence the async policy later introduces will fail this
same diff.

The async D1 shim (`AsyncD1Shim`) emulates the worker's `_D1`
semantics: `prepare(sql).bind(*params)` → `await .all()` gives
`.results` (list of dicts), `await .first()` gives a dict or None,
`await .run()` gives success/meta. D1 and sqlite3 share the `?`
placeholder dialect and SQLite itself, so the SQL is unchanged.
"""

import asyncio
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import push_events, push_sweep, push_sweep_async
from hosted.push_sweep_port import conformance, scenarios


class _AllResult:
    def __init__(self, results):
        self.results = results


class _RunResult:
    def __init__(self, changes):
        self.success = True
        self.meta = {"changes": changes}


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
        return _RunResult(cur.rowcount)


class _Stmt:
    def __init__(self, conn, sql):
        self._conn = conn
        self._sql = sql

    def bind(self, *params):
        return _Bound(self._conn, self._sql, params)


class AsyncD1Shim:
    """Worker-faithful async _D1 over a sqlite3 connection (test-only).

    `.all()` → `.results` list of dicts; `.first()` → dict or None
    (the worker's JsNull-no-match); `.run()` → success/meta. The
    port's `_to_py` passes these through unchanged, exactly as the
    worker's `_to_py` passes already-converted values.
    """

    def __init__(self, conn):
        conn.row_factory = sqlite3.Row
        self._conn = conn

    def prepare(self, sql):
        return _Stmt(self._conn, sql)

    def commit(self):
        self._conn.commit()


class AsyncTestPolicy:
    """Async policy boundary delegating to the sync in-repo policy.

    The sweep under test is the async port; the policy it drives is the
    real sync policy over the same connection — this pins the sweep's
    async structure. `record_adapter` is the scenario's two-arg sync
    adapter (or None for the built-in); the async bridge the port
    passes is unwrapped back to the sync reader the sync policy takes.
    """

    reminder_min_ttl_seconds = push_events.REMINDER_MIN_TTL_SECONDS

    def __init__(self, conn, record_adapter=None, now=None):
        self._conn = conn
        self._sync_adapter = record_adapter
        self._now = now

    def _reader(self, box_id):
        adapter = self._sync_adapter
        if adapter is None:
            adapter = push_sweep.make_record_adapter(
                self._conn, self._now)

        def sync_get(aid):
            return adapter(box_id, aid)

        return sync_get

    async def maybe_enqueue_reminder(self, db, *, box_id,
                                     owner_principal, aid, get_record,
                                     now=None):
        # get_record is the port's async bridge; the sync policy takes
        # the sync reader over the same data — both read the same rows.
        return push_events.maybe_enqueue_reminder(
            self._conn, box_id=box_id, owner_principal=owner_principal,
            aid=aid, get_record=self._reader(box_id), now=now)

    async def maybe_enqueue_digest(self, db, *, owner_principal,
                                   now=None, window_start=None):
        return push_events.maybe_enqueue_digest(
            self._conn, owner_principal=owner_principal, now=now,
            window_start=window_start)

    async def on_heartbeat_stale(self, db, *, box_id, owner_principal,
                                 stale_epoch, now=None):
        return push_events.on_heartbeat_stale(
            self._conn, box_id=box_id, owner_principal=owner_principal,
            stale_epoch=stale_epoch, now=now)

    async def on_token_expiry_warning(self, db, *, box_id,
                                      owner_principal, token_hash,
                                      now=None):
        return push_events.on_token_expiry_warning(
            self._conn, box_id=box_id, owner_principal=owner_principal,
            token_hash=token_hash, now=now)


def _scenario_derive_kwargs(spec):
    """Mirror conformance.py's derivation wiring for the async replay."""
    kwargs = {}
    if spec["derive_stale"] is not None:
        kwargs["derive_stale"] = scenarios.derive(spec["derive_stale"])
    elif spec.get("derive_stale_raiser"):
        def _raises(db, moment):
            raise RuntimeError(
                "fixture poison: stale derivation failed at call time")
        kwargs["derive_stale"] = _raises
    if spec["derive_token_warnings"] is not None:
        kwargs["derive_token_warnings"] = scenarios.derive(
            spec["derive_token_warnings"])
    return kwargs


def run_scenario_async(scenario):
    """Replay one scenario through the async port; return the record dict."""
    conn = scenarios.new_db()
    try:
        db = AsyncD1Shim(conn)
        spec = scenario["build"](conn)
        kwargs = dict(spec["sweep_kwargs"])
        kwargs["now"] = spec["now_epoch"]
        kwargs["resolve_owner"] = scenarios.registry(spec["registry"])
        kwargs["policy"] = AsyncTestPolicy(
            conn, record_adapter=spec["record_adapter"],
            now=spec["now_epoch"])
        if spec["record_adapter"] is not None:
            sync_adapter = spec["record_adapter"]

            async def record_adapter(db, box_id, aid,
                                     _s=sync_adapter):
                return _s(box_id, aid)

            kwargs["record_adapter"] = record_adapter
        kwargs.update(_scenario_derive_kwargs(spec))
        summary = asyncio.run(
            push_sweep_async.push_sweep_async_tick(db, **kwargs))
        conn.commit()
        return {
            "summary": conformance.serialize_summary(summary),
            "db": conformance.serialize_db(conn),
        }
    finally:
        conn.close()


def _diff_paths(actual, expected, path=""):
    if type(actual) is not type(expected):
        yield "%s: type %s != %s" % (
            path or "<root>", type(actual).__name__,
            type(expected).__name__)
        return
    if isinstance(actual, dict):
        for key in sorted(set(actual) | set(expected)):
            sub = "%s.%s" % (path, key) if path else str(key)
            if key not in actual:
                yield "%s: missing in actual" % sub
            elif key not in expected:
                yield "%s: unexpected in actual" % sub
            else:
                yield from _diff_paths(actual[key], expected[key], sub)
    elif isinstance(actual, list):
        if len(actual) != len(expected):
            yield "%s: len %d != %d" % (path or "<root>", len(actual),
                                       len(expected))
        for i, (a, e) in enumerate(zip(actual, expected)):
            yield from _diff_paths(a, e, "%s[%d]" % (path, i))
    elif actual != expected:
        yield "%s: %r != %r" % (path or "<root>", actual, expected)


@pytest.mark.parametrize("scenario", scenarios.SCENARIOS,
                         ids=scenarios.scenario_names())
def test_async_port_matches_recorded(scenario):
    """The async port reproduces the recorded outputs for every scenario."""
    recorded = conformance.load_recorded(scenario["name"])
    actual = run_scenario_async(scenario)
    diffs = list(_diff_paths(actual["summary"], recorded["summary"],
                             "summary")) + list(
        _diff_paths(actual["db"], recorded["db"], "db"))
    assert not diffs, (
        "async port diverged from recorded outputs for %r:\n%s" % (
            scenario["name"], "\n".join(diffs[:25])))


def test_record_adapter_parity_with_sync():
    """make_record_adapter_async agrees with the sync adapter, row for row."""
    conn = scenarios.new_db()
    try:
        spec = scenarios.build_reminder_due(conn)
        moment = spec["now_epoch"]
        sync_adapter = push_sweep.make_record_adapter(conn, moment)
        db = AsyncD1Shim(conn)
        async_adapter = push_sweep_async.make_record_adapter_async(
            db, moment)

        async def _run():
            out = {}
            for box_id, aid in (("box-a", "r1"), ("box-a", "missing")):
                out[(box_id, aid)] = (
                    sync_adapter(box_id, aid),
                    await async_adapter(db, box_id, aid))
            # Corrupt row: both adapters must fail loud (D59).
            conn.execute(
                "INSERT INTO approvals (box_id, aid, owner_id, summary,"
                " status, created_at, expires_at) VALUES"
                " ('box-a', 'bad', 'o', 's', 'pending', 'not-an-int', 1)")
            errors = []
            try:
                sync_adapter("box-a", "bad")
                errors.append(("sync", None))
            except ValueError as exc:
                errors.append(("sync", str(exc)))
            try:
                await async_adapter(db, "box-a", "bad")
                errors.append(("async", None))
            except ValueError as exc:
                errors.append(("async", str(exc)))
            return out, errors

        out, errors = asyncio.run(_run())
        for key, (sync_val, async_val) in out.items():
            assert sync_val == async_val, key
        assert errors[0][0] == "sync" and errors[0][1] is not None
        assert errors[1][0] == "async" and errors[1][1] is not None
    finally:
        conn.close()


def test_policy_boundary_validated():
    """The async tick fails closed on a bad policy (never a guessed policy)."""
    conn = scenarios.new_db()
    try:
        db = AsyncD1Shim(conn)

        class BadPolicy:
            reminder_min_ttl_seconds = 300

        with pytest.raises(ValueError):
            asyncio.run(push_sweep_async.push_sweep_async_tick(
                db, now=0, resolve_owner=lambda b: "o",
                policy=BadPolicy()))

        class BadTtl:
            reminder_min_ttl_seconds = "300"
            maybe_enqueue_reminder = None

        with pytest.raises(ValueError):
            asyncio.run(push_sweep_async.push_sweep_async_tick(
                db, now=0, resolve_owner=lambda b: "o",
                policy=BadTtl()))
    finally:
        conn.close()


def test_async_derivation_supported():
    """Worker-shaped async-generator derivations drive the watchers."""

    async def _agen():
        yield ("box-a", "epoch-5")

    async def _agen_warn():
        yield ("box-a", "tokhash")

    conn = scenarios.new_db()
    try:
        scenarios.build_watchers_wired(conn)
        db = AsyncD1Shim(conn)
        policy = AsyncTestPolicy(conn, now=scenarios.EPOCH_T0)
        summary = asyncio.run(
            push_sweep_async.push_sweep_async_tick(
                db, now=scenarios.EPOCH_T0,
                resolve_owner=scenarios.registry({"box-a": "owner-1"}),
                policy=policy,
                derive_stale=lambda db, moment: _agen(),
                derive_token_warnings=lambda db, moment: _agen_warn()))
        assert summary.stale_watchers.get("queued") == 1
        assert summary.token_warnings.get("queued") == 1
    finally:
        conn.close()
