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

This also makes the tool both-supported (D-RC-1): on self-hosted
estates the "operator" is the human running the repo CLI; on the
hosted product the operator plane runs the same component as the
source for rollout waves. Same binary, same contract.

## The operator's contract: exit codes, JSON, one-line errors

- **Exit 0** on a printed result (JSON to stdout).
- **Exit 1** from `stale` only: at least one eligible plane is not
  converged on the expected template. The rollout controller reads
  this before promoting a wave — 1 means "do not promote".
- **Exit 2** on bad input, unusable `--store`, a fail-closed trust
  check, or an internal failure. The message is one line on stderr,
  `plane_inventory: error: ...` — never a bare traceback.
- `--store` is required on every command.

Identifiers (`--plane-id`, `--tenant-id`, `--channel`) match
`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; template versions are non-empty
strings without whitespace or control characters (up to 128 chars).

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
heals itself: the journal is the truth, and every read replays it.

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
percentages and `stale` evaluation.

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
census over 1 of 50 planes is honest.

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

- Exit 1 when anything is not converged; exit 0 when all eligible
  planes run the expected template.
- Non-convergence reasons: `version-mismatch` (eligible plane on the
  wrong version), `stale` (record older than the window), `retired`
  (retired planes are listed with their exclusion reason rather than
  silently passing). Rows for planes with no current version carry
  `template_version: null`.
- `--stale-hours` (default 24) tunes the freshness window on both
  `census` and `stale`. It must be a positive number — `NaN` is
  rejected at the boundary (it would otherwise silently mark every
  record stale).

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
- Cost events are refused for unregistered planes.

### `cost-summary` — the D-MT5 measurement

```
python3 fleet/plane_inventory.py --store ~/var/plane-store cost-summary
```

Aggregates per plane and globally: per-event counts, total cost, how
many events reported a cost, and median durations. The keyed output
is `recurring_cost_usd_total` (update + rollback): D-MT5's trigger
compares **recurring** update cost across template versions, not
all-time totals — provision cost is one-time and would hide a
regression. Add `--plane-id` to scope the summary to one plane.

## Failure catalog

| Situation | Exit | Message (stderr) |
| --- | --- | --- |
| `register` on an already-registered plane | 2 | `plane 'x' is already registered (use deploy to change state)` |
| `deploy`/`cost` on an unregistered plane | 2 | `plane 'x' is not registered (register first)` |
| Snapshot and journal disagree | 2 | `snapshot/journal divergence for plane 'x': field <f> differs ...` |
| `null`/non-object planes document | 2 | `planes snapshot is corrupt: ...` |
| Non-finite or negative cost/duration | 2 | `--duration-s must be a finite number >= 0, got 'inf'` |
| Bad `--stale-hours` (≤ 0, NaN) | 2 | `--stale-hours must be a positive number` |
| `--store` missing or unwritable | 2 | `--store is not a usable directory: ...` |
| `stale` finds unconverged planes | 1 | (JSON on stdout names them; nothing on stderr) |

## What this doc deliberately does not cover

- The controller build path (S2–S5): see
  [TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md](TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md).
- The multi-tenant plane model decision (D-MT1–D-MT5): see
  [MULTI_TENANT_PLANE_MODEL_DECISION.md](MULTI_TENANT_PLANE_MODEL_DECISION.md).
- Box-layer fleet inventory and the release-gating channel (G16/G18):
  see `fleet/README.md`.
