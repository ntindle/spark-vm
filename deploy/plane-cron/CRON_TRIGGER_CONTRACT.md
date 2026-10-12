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
calls the in-repo entry points with the plane-side seams injected. The
in-repo modules never see a Worker secret, a data key, or a box token.

### Per-minute tick (`* * * * *`)

Call, in this order, with the seams the modules' docstrings name:

1. `hosted.push_sweep.sweep_once(conn, resolve_owner=resolve_owner)`
   — the D9 sweep: reminders, then digests, then watchers (D67).
   `resolve_owner(box_id)` is **required** (D2): owner identity from
   the enrollment registry, never from a box assertion. Thread one
   `now` through the sweep (D73).
2. `hosted.push_send_loop.send_loop(...)` — drains the `queued`
   outbox the sweep just wrote (#1094 owns this trigger pairing; the
   sweep alone enqueues, it never sends).

Structured-log the `SweepSummary` where the ops console can see it
(D75: `pages_truncated` is the operator alert for repeated truncation;
the sweep surfaces it for exactly this).

**Retirement rule (D71):** when #958's per-approval Durable Object
alarms land, the same change retires the cron sweep's *reminder* pass
— delete the pass or flip `PUSH_SWEEP_REMINDERS_ENABLED` (the
`sweep_once(..., reminders_enabled=...)` flag) to false. The digest
pass is unaffected: DO alarms replace reminders, not the D54 digest
trigger. Enabling alarms with the reminder sweep on must not
double-fire.

### Daily tick (`30 3 * * *`)

Call `hosted.push_gc.gc_push_tables(conn)` with the contract's
defaults (90-day retention, batch size 1000). Log the returned
per-table counts; the module already emits one line per sweep
(`push_gc: retention_days=90 deleted={...} total=M`). Batch size and
retention window are positive-int validated before any DELETE — a
misconfigured trigger fails loud, not silent.

## 3. Manual ops triggers (the #1013 pattern)

Same convention as the #1013 precedent
(`POST /v1/ops/phone_home/gc`): owner-key only, a box token is
explicitly refused, and the response returns the run's counts.

| Endpoint | Runs | Returns |
|---|---|---|
| `POST /v1/ops/push/sweep` | one `sweep_once` | the `SweepSummary` |
| `POST /v1/ops/push/gc` | one `gc_push_tables` | the deleted-row counts |

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
