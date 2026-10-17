# Plane cron-trigger contract (D9 push sweep + push retention GC)

(#1069, #1298 — the deploy half D72 pins in the plane workspace.)

The in-repo build slices are only the sweep functions
(`hosted/push_sweep.py`, `hosted/push_gc.py`): portable, stdlib +
DB-API, no Worker secret in scope. **Nothing in this repo runs them on
a schedule.** This document is the exact contract the plane
workspace's `deploy_worker.py` (operator-side, not in this repo)
implements — the trigger declaration, the scheduled-handler dispatch,
the manual ops triggers, and the post-deploy verification that proves
the trigger itself is registered. The silently-unwired failure mode —
handler deployed, trigger never registered, nothing ever ticks — is
what #1069 exists to kill.

## 1. The trigger declaration

Paste into the plane workspace's `wrangler.toml` (single source of
truth; the verifier below asserts against what is *registered*, not
what is pasted — see §5):

```toml
[triggers]
crons = [
  "* * * * *",   # D9 push sweep: reminders, digests, watchers (#1069)
  "30 3 * * *",  # push retention GC, daily 03:30 UTC (#1298)
]
```

- `* * * * *` — the D9 sweep, per minute (D66). The sweep is bounded
  per tick (D69) and idempotent under overlap; no locking, no leader
  election — overlap is safe, not prevented.
- `30 3 * * *` — the 90-day retention sweeper, daily 03:30 UTC. The
  bound is 90 days and the sweep is idempotent (D95), so daily is
  plenty; the off-hour minute dodges cron-stampede on shared Workers
  cron infrastructure.

The exact cron strings are also the expected set in
`verify_plane_cron.py`'s `EXPECTED_TRIGGERS` — one table, two
renderings; if you change a cadence here, change it there (the
`test_expected_table_is_single_sourced` test pins the table's shape).

## 2. The scheduled-handler dispatch contract

The plane's `scheduled` handler dispatches on the cron that fired and
calls the plane's async ports — never the in-repo sync entry points
(the worker's D1 is async-only; the sync/async seam is F-PP-2, and a
literal "call `sweep_once(conn)` with the worker's `_D1`" fails on the
first `conn.execute`). The in-repo modules stay the harness and test
truth (D-PP-1); they never see a Worker secret, a data key, or a box
token.

### Async amendment (#1566 S2-a — the dispatch truth)

This amendment is authoritative over the older step list below it and
over §3's endpoint table: the older text named the in-repo sync entry
points (`sweep_once`, `gc_push_tables`) and a direct `send_loop(...)`
call; all three are superseded. The sync modules named there remain
the conformance harness, not the dispatch targets.

**Concrete async port entry points** (plane-workspace module paths):

- The async sweep port lives in `control-plane/worker.py` under the
  marker `# --- BEGIN push_sweep_async (#1566 S2) ---`, following the
  #844 ed25519 inline precedent (F-PP-4). Its entry point is
  `async def push_sweep_async_tick(db, *, now, resolve_owner,
  reminders_enabled=True)` against the worker's async `_D1`
  (`await db.prepare(...).bind(...).run()` — the worker exposes no
  synchronous D1).
- The `scheduled` handler's per-minute branch (D-PP-3) calls it; the
  `POST /v1/ops/push/sweep` fetch route (§3) calls it for the D72
  manual probe.

**The D-PP-2 fixture set is the dispatch truth:**
`hosted/push_sweep_port/` — the scenario fixtures in `scenarios.py`
plus the recorded outputs in `recorded/`, held by
`hosted/test_push_sweep_port_conformance.py`. The handler's sweep
passes must reproduce the recorded outputs for every scenario. A port
that reproduces them is conformant; the CI test is what keeps it
conformant.

**Step 2 is the C2 handoff, not a direct `send_loop(...)` call.** After
the sweep passes, the handler POSTs `{now}` to the `PushSenderDO`
stub's `/drain` (`env.PUSH_SENDER_DO.idFromName("push-sender")`) and
awaits the summary — the sweep enqueues, the DO drains. The drain
build is #1571's; until it lands, the per-minute trigger does not
register (D-PP-3's stranding rule: a tick that enqueues without
draining strands pages in the outbox). The C2 fail-safe: if the
handler's POST to a gate-held `/drain` times out caller-side, the DO
continues independently and the next tick re-scans — the orphaned tick
is harmless, never retried into a double-drain.

**The D-PP-3 multiplex.** One `scheduled` handler, branched on
`controller.cron`: per-minute → the sweep passes, then the C2
handoff; `30 3 * * *` → the push retention-GC branch (reserved for
#1568 — the branch exists, the port does not); `17 3 * * *` → the
existing #1013 phone-home GC, unchanged (no cadence change, no
behavior change). Unknown cron values log loud and no-op (fail-soft —
the #1013 handler's existing discipline). The handler carries the
`reminders_enabled` flag from day one (D71 retirement rule, D-PP-7),
so the future #958 DO-alarm change flips it off without a second
port.

### Per-minute tick (`* * * * *`) — superseded step list

Retained for the record; the async amendment above is authoritative:

1. ~~`hosted.push_sweep.sweep_once(conn, resolve_owner=resolve_owner)`~~
   → the async port's `push_sweep_async_tick` (§2 async amendment).
   The D67 pass order (reminders, then digests, then watchers), the D2
   registry resolver, and the single threaded `now` (D73) are
   unchanged — they are what the D-PP-2 fixtures pin.
2. ~~`hosted.push_send_loop.send_loop(...)`~~ → the C2 handoff
   (§2 async amendment): POST `{now}` to the `PushSenderDO` stub's
   `/drain`, await the summary (#1571's build).

Structured-log the `SweepSummary` where the ops console can see it
(D75: `pages_truncated` is the operator alert for repeated
page-cap truncation; D103: `budget_truncated` is the separate alert
for repeated time-budget truncation — different cause, different
remediation; the sweep surfaces both for exactly this).

**Retirement rule (D71):** when #958's per-approval Durable Object
alarms land, the same change retires the cron sweep's *reminder* pass
— delete the pass or flip `PUSH_SWEEP_REMINDERS_ENABLED` (the
`sweep_once(..., reminders_enabled=...)` flag) to false. The digest
pass is unaffected: DO alarms replace reminders, not the D54 digest
trigger. Enabling alarms with the reminder sweep on must not
double-fire.

### Daily tick (`30 3 * * *`) — superseded step

Retained for the record; the async amendment's D-PP-3 multiplex is
authoritative: the `30 3 * * *` branch is reserved for #1568's async
retention-GC port — the branch exists, the port does not, and nothing
on this cron runs until it lands.

~~Call `hosted.push_gc.gc_push_tables(conn)` with the contract's
defaults (90-day retention, batch size 1000).~~ The in-repo sync
module is the conformance harness, not the dispatch target (F-PP-2):
the daily branch calls the #1568 async port with the contract's
defaults (90-day retention, batch size 1000), positive-int validated
before any DELETE — a misconfigured trigger fails loud, not silent.
Log the returned per-table counts; the sync module already emits one
line per sweep, and the port reproduces that line.

## 3. Manual ops triggers (the #1013 pattern)

Same convention as the #1013 precedent
(`POST /v1/ops/phone_home/gc`): owner-key only, a box token is
explicitly refused, and the response returns the run's counts.

| Endpoint | Runs | Returns |
|---|---|---|
| `POST /v1/ops/push/sweep` | one `push_sweep_async_tick` (the §2 async port — never the in-repo sync `sweep_once`; F-PP-2) | the `SweepSummary` |
| `POST /v1/ops/push/gc` | one async retention-GC port call (#1568's build — never the in-repo sync `gc_push_tables`; F-PP-2) | the deleted-row counts |

Use these for verification runs and catch-up after trigger outages —
the manual trigger is how the operator proves the scheduled one was
missed, not how the schedule normally fires.

## 4. API surface pin

The manual triggers follow the existing plane conventions (see
`docs/CONTROL_PLANE_API_REFERENCE.md`): owner-key auth, box token
refused, `200` with the result payload. Add both rows to that
reference when the plane workspace implements them.

## 5. Post-deploy verification (the #1063 acceptance criterion)

After every plane deploy that touches triggers, the operator runs:

```bash
CF_API_TOKEN=... CF_ACCOUNT_ID=... \
  python3 deploy/plane-cron/verify_plane_cron.py --script-name sparkvm-control
```

The script lists the worker's registered cron triggers via the
Cloudflare Workers API and asserts every contract cron is present. A
handler that runs proves nothing about the trigger registration —
this check is the proof. Exit 0 = all present; exit 1 = names the
missing cron(s). Extra schedules (e.g. the #1013 phone-home GC) are
listed, not failed.

**CI/offline mode:** `--fixture schedules.json` asserts against a
saved payload (the test suite pins the comparison logic; capture the
fixture with the API call above). A fixture pass asserts against a
saved snapshot only — it does not prove the triggers are registered on
the worker; only the live API call is deploy proof. The script labels
fixture runs explicitly in its output (`NOT the live Workers API` /
`ok (fixture):` / `FAIL (fixture):`) so a transcript can never be
mistaken for live verification.

Then, once, per deploy: invoke one `scheduled` event in staging and
assert a clean no-op sweep, or observe one live cron tick enqueuing a
due reminder with no human driving it — that tick is #1063's
acceptance criterion, and it is the operator's, not this repo's, to
record.
