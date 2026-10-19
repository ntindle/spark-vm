# Tenant-plane version inventory — operator guide

The S1 slice of the tenant-plane rollout controller
([#1261](https://github.com/ntindle/spark-vm/issues/1261)): the
`fleet/plane_inventory.py` CLI that answers, for the *plane layer*, the
two questions the box inventory answers for boxes — which template
version each tenant plane runs, and which planes have not converged —
plus the per-plane operational-cost journal that feeds the D-MT5
revisit trigger. Shipped as PR #1284. The controller build path that
consumes this (S2–S5) is pinned in
[docs/TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md](TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md);
this guide is the operator's contract for the S1 tool itself.

## The one thing to internalize: S1 is operator-recorded, not plane-reported

There is no daemon, no inbound port, no plane heartbeat. The operator
records observations — register/deploy/cost events — from wherever
they act (the provisioner, the deploy runbook, the billing export).
`observed_at`/`at` are the operator's clock; nothing plane-reported is
trusted for ordering, because nothing plane-reported exists at this
slice. A future slice may accept plane-signed heartbeats; they must
not backfill `at` — same discipline as the box inventory.

This keeps the tool both-supported (D-RC-1): on self-hosted
estates the "operator" is the human running the repo CLI — that half
is shipped and documented here. The hosted product's consumption is
the S2+ design intent: the future operator plane reuses this same
CLI and exit-code contract as its wave source, but the operator plane
itself is not built yet (zero code — see the operator-plane build-path
gap analysis) — today the hosted operator runs this tool the same way
the self-hosted human does. Same binary, same contract.

All examples run from the repo root (`python3 fleet/plane_inventory.py`).
A missing `--store` directory is created automatically as an empty
store — there is no init step.

## The operator's contract: exit codes, JSON, one-line errors

- **Exit 0** on a printed result (JSON to stdout).
- **Exit 1** from `stale` only: the `not_converged` list is
  non-empty — an eligible plane on the wrong template, a
  record-stale plane, *or a retired plane* (listed with reason
  `retired`). This is the estate-wide convergence report, not the
  promotion gate: 1 means "the estate is not converged on the expected
  template". The actual promotion gate is `promote`'s D-RC-4 check,
  which never promotes into a retired plane (a retired plane in the
  live wave fails closed — reassign the rollout) and is not blocked by
  store-wide retired planes. Exit 0 only when no plane is
  listed at all.
- **Exit 2** on bad input, unwritable `--store`, a fail-closed trust
  check, or an internal failure. Operational errors print one line
  on stderr, `plane_inventory: error: ...`; internal failures print
  `plane_inventory: internal error: ...`; argparse usage errors print
  `plane_inventory.py: error: ...`. All exit 2; none print a bare
  traceback.
- `--store` is required on every command.

Identifiers (`--plane-id`, `--tenant-id`, `--channel`) match
`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; template versions match
`^[A-Za-z0-9][A-Za-z0-9._:+~@-]{0,127}$` — start alphanumeric, up to
128 chars, charset `[A-Za-z0-9._:+~@-]` (no `/`, `!`, or parens).

## Store layout and journal discipline

Three files in the `--store` directory:

| File | Role |
| --- | --- |
| `planes.json` | **Derived snapshot**: latest record per `plane_id`. Never trusted alone. |
| `planes_journal.jsonl` | **Source of truth**: append-only observation records. |
| `costs.jsonl` | **Append-only** operational-cost events. |

Writes serialize on the store-scoped journal lock (`fleet/events.py`).
Journal appends are single `O_APPEND` `write()` calls; the snapshot is
published via process-unique tmp file + `os.replace()`; both are
`fsync`'d. A crash between the journal append and the snapshot publish
does **not** heal itself: the next read fails closed (exit 2,
`snapshot/journal divergence` — the journal is the truth and every
read replays it, so a journal-ahead snapshot is a divergence). The
observation is not lost — the journal has it — but recovery is manual:
remove the stale `planes.json`. Note that a *missing* snapshot reads
as an empty store (the journal is not replayed to rebuild it), so the
planes must then be re-registered, minting duplicate journal records.
There is no `verify`/repair subcommand in S1. The snapshot tmp file
is `fsync`'d but the store directory is not `fsync`'d after
`os.replace()`, so the happy path carries a similar crash window
landing in the same fail-closed state.

### Trust model

The trust root is the **operator's own box filesystem**. Neither
journal has hash chaining and the snapshot is unsigned — the store is
the operator's own memory, never evidence *against* the operator.
Against that honest-operator baseline, the tool still refuses to
present a false green: **every read replays the planes journal's
latest-per-plane records and fails closed (exit 2) on any divergence**
with the snapshot. A tampered or stale-restored snapshot cannot tell
the `stale` pre-promotion gate "all converged". A `null` planes
document is structural corruption, not an empty store — it exits 2,
never reads as "no planes".

A later slice may add journal hash-chaining plus a `verify`
subcommand; S1 has neither.

## Lifecycle commands

### `register` — introduce a plane

```
python3 fleet/plane_inventory.py --store ~/var/plane-store \
  register --plane-id plane-a --tenant-id tenant-1 \
           --template sparkvm-control@abc123 --channel stable
```

- New planes start in status `provisioning`.
- Fail-closed when the plane is already registered: `register` never
  overwrites; use `deploy` to change state.
- `--template` may be omitted at registration (a plane exists before
  it is deployed); `--channel` defaults to `stable`.

### `deploy` — record a template landing

```
python3 fleet/plane_inventory.py --store ~/var/plane-store \
  deploy --plane-id plane-a --template sparkvm-control@def456 \
         --status healthy --notes "wave 1 canary"
```

- Recording a wave landing is `deploy`, not a new `register`.
- Fail-closed against an **unregistered** plane (exit 2): the
  controller must never silently create a plane row mid-rollout.
- `--status` is `healthy` (default) or `degraded`.
- Deploying on a **retired** plane resurrects it — intentional: a
  retired `plane_id` may be re-provisioned and rejoin the fleet.

### `retire` — take a plane out of the denominator

```
python3 fleet/plane_inventory.py --store ~/var/plane-store \
  retire --plane-id plane-a --notes "tenant churned 2026-10-10"
```

The plane is kept for cost history but excluded from census
percentages. Note the asymmetry: `stale` still lists retired planes
in `not_converged` (reason `retired`, `template_version: null`), so
a retired plane keeps the estate convergence report non-empty —
retirements are operator-visible to the rollout, not silently
dropped. It does not block promotion: the promotion gate (`promote`,
D-RC-4) ignores store-wide retired planes and refuses only a retired
plane sitting in the live wave (fail-closed: reassign the rollout).
Retiring an already-retired plane succeeds (it refreshes
`observed_at`).

## Observation commands

### `census` — the version table

```
python3 fleet/plane_inventory.py --store ~/var/plane-store census
```

```json
{
  "eligible": 3,
  "excluded": [{"plane_id": "plane-x", "reason": "retired"}],
  "census": [
    {"template_version": "sparkvm-control@def456", "planes": 2, "pct": 66.7},
    {"template_version": "sparkvm-control@abc123", "planes": 1, "pct": 33.3}
  ]
}
```

The denominator is **eligible planes only**: non-retired planes whose
latest record is fresher than the staleness window (default 24h).
Excluded planes are printed alongside the percentage, so a 100%
census over 1 of 50 planes is honest. Planes registered without
`--template` appear with `template_version: null`.

### `stale` — the pre-promotion gate

```
python3 fleet/plane_inventory.py --store ~/var/plane-store \
  stale --expected sparkvm-control@def456
```

```json
{
  "expected": "sparkvm-control@def456",
  "not_converged": [
    {"plane_id": "plane-b", "reason": "version-mismatch",
     "template_version": "sparkvm-control@abc123"}
  ],
  "count": 1
}
```

- Exit 1 whenever any plane is listed in `not_converged` — a
  version-mismatch, a record-stale plane, or a retired plane.
  Exit 0 only when the list is empty.
- Non-convergence reasons: `version-mismatch` (eligible plane on the
  wrong version), `stale` (record older than the window), `retired`
  (retired planes are listed with their exclusion reason rather than
  silently passing). Rows for planes with no current version carry
  `template_version: null` — including eligible planes registered
  without `--template`, which `stale` reports as `version-mismatch`.
- `--stale-hours` (default 24) tunes the freshness window on both
  `census` and `stale`. It must be a positive number — `NaN` is
  rejected at the boundary (it would otherwise silently mark every
  record stale); note `inf` passes the check and makes every record
  fresh forever.
- A typo'd `--store` path silently becomes a fresh empty store, and
  `stale` on it exits 0 with `count: 0` — a false green for the
  pre-promotion gate. The controller must pin and verify the store
  path rather than rely on fail-closed behavior here.

## A rollout wave, end to end

```
$ python3 fleet/plane_inventory.py --store ~/var/plane-store census
$ python3 fleet/plane_inventory.py --store ~/var/plane-store stale --expected sparkvm-control@def456
# exit 1: plane-b is still on sparkvm-control@abc123 — do not promote
$ python3 fleet/plane_inventory.py --store ~/var/plane-store deploy --plane-id plane-b --template sparkvm-control@def456 --notes "wave 1"
$ python3 fleet/plane_inventory.py --store ~/var/plane-store stale --expected sparkvm-control@def456
# exit 0: converged — the wave may proceed
$ python3 fleet/plane_inventory.py --store ~/var/plane-store cost --plane-id plane-b --event update --duration-s 75 --cost-usd 0.09
```

## Cost commands

### `cost` — append one cost event

```
python3 fleet/plane_inventory.py --store ~/var/plane-store \
  cost --plane-id plane-a --event update --duration-s 90 --cost-usd 0.11
```

- Events: `provision` (one-time), `update` and `rollback`
  (recurring). S4 (deploy driver) is the ledger's first writer; until
  then the operator appends manually.
- `--duration-s` and `--cost-usd` are optional but must be finite
  numbers ≥ 0 when given — `inf`/`nan` are rejected (JSON would emit
  `Infinity`, poisoning the recurring total).
- Cost events are refused for never-registered planes, but accepted
  on retired ones (cost history keeps accruing after retirement).
- `--notes` is *replaced* per event, not appended; the default is the
  empty string.

### `cost-summary` — the D-MT5 measurement

```
python3 fleet/plane_inventory.py --store ~/var/plane-store cost-summary
```

Aggregates per plane and globally: per-event counts, total cost,
how many events reported a cost, and median durations
(`duration_s_median` is `null` when no durations were reported).
The keyed output is `recurring_cost_usd_total` (update + rollback),
alongside the provision totals: D-MT5's measurement is **measured
per-tenant-plane operational cost — provision + update rollout** —
compared against the amortized cost of the tenant-layer security
redesign. Provision is one-time but it counts in the predicate;
rollback costs are tracked as recurring operational cost. D-MT5's
other predicate (tenant count approaching Cloudflare per-account
Worker/D1 limits) is not measured by this tool. Add `--plane-id`
to scope the summary to one plane.

## Failure catalog

| Situation | Exit | Message (stderr) |
| --- | --- | --- |
| `register` on an already-registered plane | 2 | `plane 'x' is already registered (use deploy to change state)` |
| `deploy`/`cost` on an unregistered plane | 2 | `plane 'x' is not registered (register first)` |
| `retire` on an unregistered plane | 2 | `plane 'x' is not registered` (no "register first" suffix) |
| Snapshot and journal disagree on a field | 2 | `snapshot/journal divergence for plane 'x': field <f> differs ...` |
| Snapshot and journal disagree on plane sets | 2 | `snapshot/journal divergence: plane sets differ (journal=[...], snapshot=[...])` |
| `null`/non-object planes document | 2 | `planes snapshot is corrupt: ...` |
| Non-finite or negative cost/duration | 2 | `--duration-s must be a finite number >= 0, got 'inf'` |
| Bad `--stale-hours` (≤ 0, NaN) | 2 | `--stale-hours must be a positive number` (note: `inf` is accepted and makes every record fresh) |
| `--store` directory missing | — | auto-created as an empty store (exit 0); a typo'd path is a fresh empty store — `stale` on it exits 0 with `count: 0` |
| `--store` unwritable | 2 | `--store is not a usable directory: ...` |
| `stale` finds unconverged planes | 1 | (JSON on stdout names them; nothing on stderr) |

## What this doc deliberately does not cover

- The controller build path (S2–S5): see
  [TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md](TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md).
- The multi-tenant plane model decision (D-MT1–D-MT5): see
  [MULTI_TENANT_PLANE_MODEL_DECISION.md](MULTI_TENANT_PLANE_MODEL_DECISION.md).
- Box-layer fleet inventory and the release-gating channel (G16/G18):
  see `fleet/README.md`.
