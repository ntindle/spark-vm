# Relay-liveness wiring tick — operator reference

The tenant-status relay-liveness wiring never self-drives: rule-6
relay/cert suspensions, the recovery pair, live-anchor selection, and the
stale-reachability resync run only when something ticks `drive_tenant`.
Today that something is the operator, via the `--tick` CLI on
`hosted/relay_tenant_wiring.py` (D-RL34-7, #1711 acceptance option 2).
This doc is the operator's reference for invoking it and reading what it
prints. The wiring's design lives in `docs/RELAY_LIVENESS_DESIGN.md`; the
auto-cadence driver that would replace the manual tick is tracked in
`docs/RELAY_LIVENESS_AUTO_CADENCE_GAP_ANALYSIS.md` (#1711 stays open).

## Invocation

From the repo root:

```bash
python3 -m hosted.relay_tenant_wiring --store <tenants.json> --tick <TENANT_ID>
```

| Flag | Required | Meaning |
|---|---|---|
| `--store PATH` | yes | Tenant-record JSON store path |
| `--tick TENANT_ID` | yes | Run one wiring tick for `TENANT_ID` and print the report as JSON |
| `--history PATH` | no | Probe-history path override (sets `RELAY_PROBE_HISTORY` for the tick) |
| `--journal PATH` | no | Session-journal path override (sets `RELAY_SESSION_JOURNAL` for the tick) |
| `--journal-timeout-s SECONDS` | no | Journal-lock wait seconds for the producer read (float) |

The `--history` / `--journal` overrides let an operator point one tick at
an alternate probe history or session journal without changing the
process environment; they take effect only for that tick's producer
reads. The timeout bounds how long the anchor's producer read waits on
the session journal's lock before the read fails loudly (see §4).

## The tick report

On success (exit 0) the CLI prints the `drive_tenant` report as JSON on
stdout, keys sorted:

```json
{
  "tenant_id": "tnt_test",
  "anchor_box_id": "box-a",
  "boxes": [
    {
      "box_id": "box-a",
      "vm_id": "box-a",
      "reading": {
        "state": "ok",
        "sub_code": null,
        "reason": null,
        "probe": "path_ok",
        "journal": "active"
      },
      "events": [],
      "notes": []
    }
  ]
}
```

**Top level:** `tenant_id` echoes the ticked tenant; `anchor_box_id` is
the read-phase live anchor — the box whose reading drove the tick
(`null` when no box held a candidate arc, in which case nothing was
applied anywhere); `boxes` carries one report per box arc on the record.

**Per box:** `box_id` is the arc id, `vm_id` the instrument's box→vm
mapping (identity today). `reading` is the operator-safe slice of the
producer reading — `state` (`ok` | `degraded` | `down`), `sub_code` (on
`down` only: `relay` | `cert` | `box-leg`), `reason`, `probe`, `journal`.
The full reading is never bundled into the report: `relay_path_state`
results carry outcome strings only (D-RL2-3), so no connection material
can leak through the tick output. `events` lists the emitted tenant
events in order — names with kwargs rendered (`relay-down(...)`,
`relay-reachable`, `relay-recovered`; the wiring never emits
`relay-failure`). `notes` carries operator-surface explanations.

## Reading the report

Only the anchor's reading is ever applied to a tenant arc. Every other
box's reading is observed for the operator surface and never touches the
record — their slots report `events: []` with a note. Four notes you
will see, verbatim:

- Non-anchor box (healthy read):
  `"non-anchor box: reading observed for the operator surface, never applied to the arc"`.
- Non-anchor box (broken instrument):
  `"non-anchor instrument read failed (<ExcType>: <detail>) — operator surface only; the anchor tick continued"` — the tick survives a dead non-anchor instrument; only the anchor's instrument can fail it.
- No live anchor at all:
  `"no live-anchor box: reading observed for the operator surface, never applied to the arc"`.
- Anchor moved between read and apply:
  `"anchor moved between read and apply (read <old>, fresh <new>) — reading not applied; next tick re-selects and converges"` — the apply phase re-selects the anchor
  from the fresh record under the store lock, and a stale anchor is
  skipped, never applied to the wrong box. The read/apply pair is
  idempotent, so a skipped tick is never a lost tick; the next tick
  converges.

A healthy tick against a healthy tenant prints a report with `events:
[]` on every slot — a surfaced no-op, not silence.

## Exit codes and failure semantics

| Exit | Meaning |
|---|---|
| 0 | Tick completed; the JSON report is on stdout |
| 1 | Tick failed; the reason is on stderr, nothing on stdout (no report) — unknown tenant, or a broken anchor instrument |
| 2 | Usage error (argparse; missing `--store`/`--tick`) |

A broken anchor instrument is loud, never darkness: the probe-history or
journal lock error propagates from the read phase, the CLI prints
`error: broken relay instrument: <detail>` on stderr, exits 1, and the
tenant record is untouched — the apply phase never ran. A crash
mid-pair loses the whole tick (the pair is written atomically), and the
next tick re-drives from the fresh record. `_emit` failures propagate
fail-loud rather than skipping: a `TransitionError` there is a wiring
bug or a corrupt arc, not an operator decision.

## Operating discipline

- **One tick per box at a time.** The single-driver-per-box discipline
  (D-RL34-3a) binds any driver — a human run, a cron entry, or a
  supervisor loop. The anchor tick converges with itself on re-drive,
  but two concurrent ticks for the same box are not supported.
- **No scheduled driver runs in production yet.** Manual `--tick` remains the
  production drive path — if you stop ticking, the wiring stops suspending,
  and a `down` reading sits un-acted-on until the next tick. The auto-cadence
  slices are tracked in #1711 (S1–S5 filed as #1721, #1722, #1723, #1724,
  #1725): the S1 driver module (#1721), the S3 systemd packaging (#1723), and
  the S5 probe-loop module (#1725) have shipped — but the timer stays
  disabled until the S4 staleness alert (#1724) lands (the enablement gate in
  `docs/RELAY_AUTO_DRIVER_OPERATIONS.md`; enabling it earlier would re-create
  the #1711 death mode), the probe loop still needs a schedule and a bundle
  supplier, and the S2 plane async port + cron trigger (#1722) is still open.
- **Tick reports are print-only today.** The report goes to whoever
  invoked the CLI; there is no durable, queryable tick history
  (F-AC-4 in the gap analysis). Manual `--tick` writes no watermark (D-AC-6);
  watermark + journal observability ride the driver path
  (`docs/RELAY_AUTO_DRIVER_OPERATIONS.md`), which is not yet scheduled.
  Keep the tick output if you want an audit trail.
- Probe cadence while post-`live` arcs are active is a cost-vs-detection
  tradeoff (design §9 Q1), not this doc's call — but the tick is the
  second half of that budget: detection time is the probe cadence plus
  however long since the last tick.
