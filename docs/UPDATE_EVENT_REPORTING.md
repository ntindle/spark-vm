# Update event reporting — standard shape, configurable sink (G17 / #608)

`deploy/auto-deploy.sh` knows exactly how its last run went, and tells no
one. Every run is appended to the box-local audit log; the toolset updater's
S2 logging does the same. A failed fleet update is discovered on the next
manual SSH session, not noticed. And G15's health-gated promotion needs a
signal source — "did the canary wave's updates succeed?" is unanswerable
without update events. This doc designs the event stream: the standard shape
each updater emits, the sink(s) it flows to, and the alert + gate
consumption built on it.

Scope note (both-supported default, per PLAYBOOK): the operator's own
estate is already a fleet, and the first instantiation is the operator's —
pull from the estate artifacts that already exist. The hosted tenant-fleet
instantiation waits on G13 box-identity attestation and H11's isolation
story; §6 names the tenant constraints so nobody wires this up early.

## 1. What the fleet layer must learn

Today:

- `auto-deploy.sh`'s `audit()` appends one JSON line per event to the
  box-local `$UPDATER_STATE_DIR/audit.log` (`{"ts":"…","event":"check"|"deploy",…}`),
  bounded at 12k lines / 10k newest. Nobody reads it off-box.
- The toolset updater (SELF_UPDATE.md S2) plans the same audit format at
  `/var/log/sparkvm-self-update/`. Same fate.
- The fleet collector (G16 S1) already pulls per-box `audit-tail.jsonl`
  into its estate dir — but treats the tail as cross-check evidence for
  *version claims*, not as an event stream. Outcomes are incidental.

The fleet layer needs, per rollout and per wave: *what happened in the
last window* — started, deferred, succeeded, failed, rolled back — with
enough identity and context to aggregate. Events say what happened;
G16 inventory says what is installed now; together they are G15's eyes.

## 2. The standard event shape

One JSON line per event, in emission order. Field names are fixed;
unknown fields are ignored by readers (versioning: additive fields only).

| Field | Type | Meaning |
|---|---|---|
| `event_id` | string | UUIDv7 — unique, sortable; the dedup key |
| `box_id` | string | Stable box identity (G15 §8: must survive reimage) |
| `session_epoch` | int | Reimage counter from the provisioner's box record; soak and event windows are keyed (box, session, build) — see §3 |
| `emitted_at` | string | Box clock, ISO-8601 UTC |
| `received_at` | string | Collector/plane clock, ISO-8601 UTC; box clocks are never trusted for ordering |
| `source` | enum | `auto-deploy` \| `toolset-update` \| `manual` \| `controller` |
| `component` | enum | `repo` \| `toolset-cua-driver` \| `image` (reimage, later) |
| `kind` | enum | `check` \| `deploy` \| `rollback` \| `gate-answer` \| `freeze-hold` |
| `outcome` | enum | `started` \| `noop` \| `precheck-fail` \| `deferred-arc` \| `skipped-frozen` \| `succeeded` \| `failed` \| `rolled-back` \| `rollback-failed` \| `superseded` |
| `from` / `to` | string | Commit (repo) or pin version (toolset); absent on pure checks |
| `from_version` / `to_version` | string | Human versions where they exist (auto-deploy's `from_version`/`to_version`) |
| `phase` | string | Box-side failure phase where known (auto-deploy's `phase`) |
| `rollout` | object | `{release_id, wave}` — null until G15 S2 assigns waves |
| `trigger` | enum | `scheduled` \| `manual` \| `freeze` \| `gate` \| `extra-inputs` |
| `attested` | bool | S1/S2: `false`. S3: `true` when the event rode G13's attested box→plane channel |
| `note` | string | Human/alert text (the box-side alert reason, not a debug dump) |

The outcome vocabulary is closed by design: `noop` (check, nothing to do),
`precheck-fail` (gates refused before any mutation), `deferred-arc`
(never-interrupt-an-arc held: an active arc pushed this update's wave slot
past this tick — **not** a failure), `skipped-frozen` (the G18 gate said
frozen — **not** a failure either), `succeeded`, `failed`, `rolled-back`,
`rollback-failed` (the worst outcome: the box is on a known-bad build with
no way home — always an alert), `superseded` (a started update whose target
was withdrawn mid-run: fleet halt or freeze landed between check and
deploy — the local equivalent of G15's blocked-commit marker).

A `deploy` with outcome `succeeded` is a *claim* about what is running.
The event stream is self-reported; G16's cross-check discipline applies:
a `succeeded`-to-X event where no box later inventories at X is an
event↔inventory violation (the suspect-flag analog — flagged, not
convicted, and the inventory always wins: point-in-time read beats a
history of claims).

Example:

```json
{"event_id":"0196c4a2-…","box_id":"tower","session_epoch":3,"emitted_at":"2026-09-29T22:04:11Z","received_at":"2026-09-29T22:04:13Z","source":"auto-deploy","component":"repo","kind":"deploy","outcome":"rolled-back","from":"e54dc03c","to":"dbc7b206","phase":"post-deploy-health","rollout":{"release_id":"stable-20260929-2","wave":"canary"},"trigger":"scheduled","attested":false,"note":"post-deploy health check failed; restored snapshot"}
```

## 3. Emitters: what the boxes already emit

S1 requires **no new box-side artifact**. The fleet-side canonicalizer
translates the existing audit lines into the standard shape at collect
time. The mapping is exact because the audit shapes are known
(`deploy/auto-deploy.sh`, the `audit()` calls):

| Audit line | Standard event (`kind`, `outcome`) |
|---|---|
| `{"event":"check","result":"noop"}` | `check`, `noop` |
| `{"event":"check","result":"precheck-fail"}` | `check`, `precheck-fail` |
| `{"event":"deploy","result":"precheck-fail","from","to"}` | `deploy`, `precheck-fail` |
| `{"event":"deploy","result":"deploy-fail","from","to","phase"}` | `deploy`, `failed` |
| `{"event":"deploy","result":"rollback-failed","from","to","phase"}` | `deploy`, `rollback-failed` |
| `{"event":"deploy","result":"rolled-back","from","to","to_version"}` | `deploy`, `rolled-back` |
| `{"event":"deploy","result":"pull-only","from","to","from_version","to_version"}` | `deploy`, `succeeded` |
| `trigger` field (`extra-inputs`, …) | → `trigger` |

The canonicalizer is fail-closed on malformed lines: box-side `audit()`
interpolates raw variables into JSON, so the collector parses with a
forgiving reader and records unparseable lines as a collector note, never
as events. A gap in the audit tail (rotation, log loss) is *missing
evidence*, not evidence of success — the collector never infers `noop`
from silence.

Noise discipline: check-`noop` events stay **local-only** at S1. A 10-minute
check cadence × N boxes is the event stream's largest volume component and
carries zero fleet signal (tick health is G16's freshness eligibility, not
an event). Only non-noop outcomes travel in S1; the noop cutoff is revisited
when a consumer proves it needs tick-heartbeat evidence (open question 1).

## 4. Sinks, in slices

### S1 — canonicalize at collect; alert on the fleet side (ship first)

- **Sink:** the estate dir the G16 S1 collector already pulls. No new
  box-side file, no new port. The canonicalizer runs inside
  `fleet/inventory.py` (or a sibling `fleet/events.py`) and appends
  standard-shape events to the store's event journal; `received_at` is the
  collect clock. Event dedup is on `(box_id, event_id)` — a re-pulled tail
  re-canonicalizes to the same ids, so double-collection is a no-op.
- **Read:** `fleet events` shows the per-box outcome series;
  `fleet events --wave` filters by the rollout envelope (null until G15 S2).
- **Alert — the promptness ask.** The issue's core requirement is that a
  failed fleet update is *noticed*, not discovered. Three fleet-side rules,
  evaluated on every collect:
  1. **Any `rollback-failed`** → immediate alert (a box stuck on a
     known-bad build).
  2. **Correlated failure:** ≥2 boxes reporting `failed`/`rolled-back` for
     the same component+`to` within a 30-minute window → fleet alert (this
     is the bad-release shape).
  3. **Silent wave:** wave-eligible boxes with zero non-noop events over
     the max-wait window → operator alert (feeds G15 §4's max-wait page;
     silence is missing evidence, not health).
  Alert transport, honestly staged: S1 writes the alert into the
  operator's fleet journal and `fleet events watch` exits nonzero on
  unacknowledged alerts — a cron or the operator's existing paging consumes
  it. The P7 status page's alert feed is the formal home when it exists;
  nothing in S1 pretends the feed exists before it does.

### S2 — box-side event journal; gate-ready aggregation

- **Sink:** a dedicated box-side journal both updaters append directly in
  the standard shape (`update-events.jsonl`, same bounded 12k/10k discipline
  as the audit log — audit.log keeps the raw box-side record; the event
  journal is the fleet-facing translation). The collector reads
  `update-events.jsonl` instead of translating audit tails.
- **Aggregation for G15's gates** (what §5 of the controller design reads):
  - per-wave outcome census over the soak window (the zero
    failed/rolled-back gate);
  - failure-rate baseline inputs: failed ÷ deploy-attempts per wave per
    (box, session, build) — the session epoch keying is why reimage
    resets soak (G15 §4): old-session events for build X never count
    toward the new session's soak on X;
  - `skipped-frozen`/`freeze-hold` events explain quiet waves — a wave
    with no events during a freeze is a *frozen* wave, not a failed one,
    and never passes the gate on a window with a frozen gap (G15 §4's
    toll rule consumes these events);
  - `deferred-arc` events feed the eligible-box computation (an arc-busy
    box is not a failing box).
- **Retention:** the event journal gets a real policy — 90 days of
  per-event records per box, compacted after 30 days into per-day
  outcome histograms keyed (box, component, build). This is the fleet
  journal discipline G16 S1's README owed as an open question; the
  inventory and event journals share it.

### S3 — control-plane endpoint with attestation (hosted)

- **Sink:** boxes push events to the control plane (or the plane pulls —
  S2's transport decision); the push endpoint rides G13's signed
  box→plane channel (TENANT_UPDATE_TRUST_MODEL.md §10), with per-tenant
  attribution into the control-plane journal.
- **Trust:** gate-consumed events must be `attested: true`. Unattested
  self-reported events are *informational only* — visible to the operator,
  never admitted to a gate quorum. The operator estate keeps its trusted
  pull model; the tenant fleet gets attestation or it gets no gates.
  Forged events are the G15 §6 attack: fake `succeeded` promotes a bad
  release, fake `failed` halts a good one. `event_id` is bound to
  `box_id`, so replays never double-count; attestation binds the box
  identity to the event content.
- **Slicing:** H11 per-tenant waves consume per-tenant event series;
  one tenant's correlated-failure alert never fires another tenant's.

## 5. Composition with the sibling designs

- **G15 (§4 gates):** the gate's three reads are §4 here — per-wave
  outcome census, failure-rate baseline inputs, per-(box,session,build)
  soak evidence. Gate-consumed events are attested-only in the
  tenant instantiation.
- **G16:** events are claims; inventory is ground truth. The
  event↔inventory cross-check (§2) is the deliverable the G16 S1 README
  named "G17 event cross-checks" as S2 work — this doc is its spec.
- **G14:** events emitted during a `maintenance` window carry the window;
  the 30-minute trusted quiet-clock means `noop`-in-maintenance is
  expected, and maintenance-window events never feed the stall detector
  (UPDATE_IDLE_SUSPEND_CLOCK.md D1/D6).
- **G18:** the box-side gate query answer is itself an event source —
  `kind: gate-answer` with outcomes `succeeded` (permitted commit X) and
  `skipped-frozen` (fleet frozen). The freeze propagation proof G18 must
  deliver is *observable* in this stream: a freeze flipped at T0 must show
  `skipped-frozen` events on fleet-managed boxes within the G18 latency
  bound, or the bound is theater with evidence.
- **G12:** tenant-visible update state is *not* this. This stream is the
  operator/control-plane side; G12 renders for the tenant. The two never
  share a sink — a tenant must not read the operator's fleet-wide failure
  series.

## 6. Tenant-fleet constraints (why S3 waits)

The operator estate can run S1/S2 today: trusted boxes, one operator,
pull over the estate dir. The tenant-fleet instantiation additionally
waits on:

- **G13 attestation** — without box-identity attestation, tenant-fleet
  gates are forgeable (§5, G15 §6). S1/S2's `attested: false` events must
  never be admitted to a tenant gate quorum, even by operator override
  (the override path is `fleet promote`, G15 §2 — human, attributed,
  never automatic).
- **H11 isolation** — per-tenant event series, per-tenant alerts, one
  tenant's halt never pins another's rollout.
- **Never-interrupt-an-arc** — `deferred-arc` is the event vocabulary
  for it; the S2 eligible-box computation must treat a `deferred-arc`
  series as scheduled-around, never as failing.

## 7. Deliberately out of scope

- **What a tenant-box update is** (G11–G14): this decides *how outcomes
  travel*, not what they are.
- **Gate mechanics** (G15): this supplies the signal; the controller
  decides.
- **The wave/freeze transport** (G18): the `skipped-frozen` events
  observe it; G18 builds it.
- **Provisioning mid-rollout** (G15 §9): a new box's first events are
  bootstrap noise, not soak evidence — the collector tags events before
  the box's first completed release as `trigger: scheduled` with
  `rollout: null` and the gate ignores them.
- **Tenant-visible rendering** (G12): operator side only.

## Build slices

- **S1 — canonicalize + alert (ship first):** fleet-side canonicalizer for
  the two known audit shapes; event journal in the fleet store with
  (box_id, event_id) dedup; `fleet events` CLI; the three alert rules with
  interim journal+exit-code transport; noop-stays-local noise discipline.
  No box-side change. #608's acceptance sketch is this slice.
- **S2 — box-side journal + gate aggregation:** `update-events.jsonl`
  emitted in-shape by both updaters; per-wave outcome census, failure-rate
  baseline inputs, per-(box,session,build) soak windows; event↔inventory
  cross-checks; the 90-day/30-day journal discipline shared with G16.
- **S3 — hosted endpoint:** control-plane push endpoint on G13's signed
  box→plane channel; `attested` admission rule for gate quorum;
  per-tenant attribution and slicing (H11); tenant-fleet alert routing.

## Open questions

1. **Noop shipping:** S1 keeps check-noops local. If a future gate wants
   tick-heartbeat evidence (a wave of silent boxes is ambiguous), the
   heartbeat may need to travel — or the silence rule (S1 alert 3) may
   suffice. Revisit when a consumer proves need.
2. **Tenant-box alert ownership:** when a tenant box's update
   `rollback-fail`s, who gets the alert — the tenant, the operator, or
   both? Tenant-visible is G12's surface; the routing rule belongs to the
   H14/push story, not this doc. S1/S2 alert to the operator only.
3. **Session-epoch provenance:** the provisioner must maintain the
   reimage counter (§2, §4). Today no box record carries it. G15 §8's
   box_id-stability requirement gets a sibling: the provisioner's per-box
   record owns `session_epoch`, incremented at reimage.
4. **Cross-component correlation:** a bad repo build and a toolset pin
   failure on the same box in the same window look correlated but aren't.
   The census gates are per (component, build); the fleet alert rule (S1
   rule 2) should probably key the same way. S1 keys (component, to).

---
*Design for G17 (#608), from the 2026-09-28 fleet-rollout gap analysis
(`FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md`). Implementation (S1–S3) remains —
tracked on #608. Related: G15 (#606, `ROLLOUT_CONTROLLER_DESIGN.md`), G16
(#607, `FLEET_VERSION_INVENTORY_DESIGN.md` + `fleet/`), G18 (#609),
G11/G12 (`UPDATE_CHANNEL_POLICY.md`), G13 (#555,
`TENANT_UPDATE_TRUST_MODEL.md`), G14 (#556, `UPDATE_IDLE_SUSPEND_CLOCK.md`),
H11, P7.*
