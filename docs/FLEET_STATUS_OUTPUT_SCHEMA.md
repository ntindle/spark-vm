# Fleet rollout `status` output schema

Reference for the JSON that `fleet/plane_waves.py status` prints — the
operator's at-a-glance view of a rollout. Pinned to main `d60d703d`
(`cmd_status` in `fleet/plane_waves.py`); every claim below is traceable
to that implementation, not to intent.

## Contract

```
python3 fleet/plane_waves.py --store DIR status
```

prints a single JSON object to stdout and exits 0. **Read-only**: no
store file is created or touched, no lock is taken, no journal record
is emitted — the shared `ensure_store` guard creates the store
*directory* when absent, and nothing else is written. `status` never
blocks a rollout and never advances one; the promotion gate (`promote`) is the authoritative reader
of the same signals. If the store is corrupt or a fail-closed precondition
fails, `status` refuses loudly (non-zero exit) rather than printing a
reassuring partial view — a corrupt record must never present as a
routine "wait and re-run" refusal.

## Top-level fields

| Field            | Shape                          | Meaning |
|------------------|--------------------------------|---------|
| `frozen`         | boolean                        | The controller store's freeze flag (D-RC-5): `true` refuses all mutations. Missing file = `false` (fresh store); an unreadable file, wrong schema, or non-boolean `frozen` fails closed instead of silently unfreezing. |
| `canary_tenants` | sorted list of strings         | Tenants explicitly designated for the canary wave (D-RC-3's tenant rule). |
| `rollout`        | object, or `null`              | The rollout state. `null` means no waves file exists. A completed rollout still prints the full object with `live_wave: null` — completion is read from the object, not from `null`. |

## `rollout` fields

| Field              | Shape                                   | Meaning |
|--------------------|-----------------------------------------|---------|
| `template_version` | string                                  | The pinned template release this rollout is deploying. |
| `channel`          | string                                  | Release channel (e.g. `security` — expedited releases travel compressed waves, canary + one wave, never ungated, per D-RC-7). `status` echoes the field; it does not branch on it. |
| `buckets`          | positive integer                      | The bucket count the wave assignments were computed from (fail-closed on anything else — a non-positive-int `buckets` refuses to load the waves file). |
| `live_wave`        | int or `null`                           | The wave currently soaking. `null` = nothing soaking; read `halted` to distinguish — `halted: null` means the rollout completed, a set `halted` means it was halted (terminal). |
| `halted`           | `null` or `{reason, ...}`               | `null` = not halted. A halted rollout is terminal: already-landed waves stay, nothing advances. |
| `waves`            | `{<wave as string>: <per-wave object>}` | Per-wave detail, keyed by the wave number rendered as a string. |
| `updated_at`       | ISO-8601 string                         | `waves.json`'s stamp — **the baseline of the journal window** (see `bad_signal` below). Events older than it belong to an earlier rollout and never block a fresh wave. |

## Per-wave fields

| Field        | Shape                    | Meaning |
|--------------|--------------------------|---------|
| `planes`     | sorted list of strings   | The planes assigned to this wave. |
| `landed`     | boolean                  | **The convergence half only.** `true` when every member plane's record reports the rollout's `template_version`, a `healthy` status, and a record refreshed within the staleness window (24h — the S1 rule shared with the promotion gate). A wave can be fully `landed` while the gate still refuses it — that is the disagreement `bad_signal` exists to explain. |
| `bad_signal` | sorted list of strings   | **The journal half.** The planes whose latest update-event *since `updated_at`* is an unresolved `deploy-failed` — latest event per plane; an event older than the rollout's `updated_at` belongs to a previous rollout and is excluded. A missing journal yields no signal (D-RC-6: missing events do not block promotion — an honest gap, not a clean bill). An unparseable `updated_at` or `observed_at` fails closed: `status` refuses to evaluate rather than print a view that could disagree with the gate. |
| `live`       | boolean                  | `true` for the wave that equals `live_wave`. |

## The `landed`/`bad_signal` split

The two halves deliberately mirror the promotion gate's two reads, so
`status` and `promote` can no longer disagree silently about a live wave:

- `landed` mirrors the gate's **convergence read** (records converged on
  the template).
- `bad_signal` mirrors the gate's **journal read** (D-RC-4): the same
  helper and the same `updated_at`-bounded window the gate consumes, so a
  live wave carrying an unresolved deploy-failed is refused by `promote`
  **and** visible in `status`.

The mirror holds exactly for the **live wave**. For not-yet-live waves
`bad_signal` is prospective — the gate re-baselines the window on every
`promote` advance, so a future wave's signal is an early warning, not a
verdict.

**Clearing a signal.** A plane leaves `bad_signal` when a fresh landing
is recorded for it (S4 deploy, S1 `deploy`, or an explicit
`event --kind deploy-landed`) — its latest event is no longer
`deploy-failed` — or when the rollout is reassigned, which writes a fresh
`updated_at` and re-baselines the window.

## Reading a refusal

When `promote` refuses with the journal-half `bad-signal`, the matching
row in `status` shows exactly which planes the gate saw (wrapped for
display — the real refusal is one stderr line prefixed
`plane_waves: error: promotion refused: `):

```
bad_signal: ["plane-3"]          # status wave row
bad-signal: planes with unresolved deploy-failed events
since wave 2 went live: plane-3 (failed 2026-10-17T13:02:11+00:00)
  — promotion refused; record a fresh landing or reassign the rollout
```

The `(failed <at>)` timestamp in the refusal is the same
`observed_at` the journal half read — one number, two renderings.

This mapping covers only the journal refusal. The gate's *other*
`bad-signal:` refusal — degraded planes ("promotion refused; halt the
rollout") — has no JSON mirror: it surfaces in `status` as
`landed: false` with an empty `bad_signal`.

## Known limits

- The JSON schema is a CLI surface, not a versioned API: fields are added
  (as `bad_signal` was) without a schema-version bump. Consumers should
  ignore unknown fields, not reject them.
- Per-box gate-stale surfacing folds into the `fleet events watch`
  alert board (#1632, acceptance amended per D-GA-2 — no new
  `fleet status` command is owed). This document covers the CLI's
  JSON; the P7 status-page projection is separate.

## Pointers

- `docs/ROLLOUT_CONTROLLER_DESIGN.md` — the rollout controller design
  (G15 / #606): state machine, health gates, deliberately-out-of-scope.
- `fleet/README.md` — fleet layer components (`plane_waves.py` is the
  controller's brain, S2 #1285).
- `docs/UPDATE_EVENT_REPORTING.md` — the update-event vocabulary and
  journal the `bad_signal` half reads.
- Issue #1638 (bad_signal field, PR #1659) and #1632 (open: per-box
  gate-stale folds into the `fleet events watch` alert board per the
  D-GA-2 amended acceptance).
