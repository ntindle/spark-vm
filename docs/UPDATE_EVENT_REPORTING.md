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
  box-local `$UPDATER_STATE_DIR/audit.log`
  (`{"ts":"…","event":"check"|"deploy"|"rollback",…}` — fifteen (event,
  result) shapes, §3), bounded at 12k lines / 10k newest. Nobody reads it
  off-box.
- The toolset updater (SELF_UPDATE.md S2) plans the same audit format at
  `/var/log/sparkvm-self-update/` — the same who/what/when/version shape
  auto-deploy uses; its result vocabulary is still undefined. Same fate.
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
| `event_id` | string | UUIDv7 for box-emitted events; deterministic UUIDv5 for fleet-canonicalized legacy lines — the dedup key in both cases (see §4 S1). The S1 synthesis is UUIDv5 over `box_id|ts|event|result|from|to`, with a per-subcomponent suffix for the plural-`components` success line |
| `box_id` | string | Stable box identity (G15 §8: must survive reimage); the S1 canonicalizer sources it from the collector's per-box pull context (the estate dir name / G16's operator-maintained mapping) |
| `session_epoch` | int \| null | Reimage counter from the provisioner's box record; S1 canonicalizer emits `null` (OQ3 tracks the record that makes it non-null); soak/aggregation keying degrades to (box, build) while null |
| `emitted_at` | string | Box clock, ISO-8601 UTC |
| `received_at` | string | Collector/plane clock, ISO-8601 UTC; box clocks are never trusted for ordering — consumers order by `(emitted_at, event_id)` so re-collection never reorders history |
| `source` | enum | `auto-deploy` \| `toolset-update` \| `manual` \| `controller` |
| `component` | enum | `repo` \| `toolset-cua-driver` \| `image` (reimage, later) — which updater, not which part: an audit line's own `component` (`proxy`, `confirm`, `cred_ui`, …) is sub-component granularity and becomes the additive `subcomponent`/`subcomponents` field, never this enum |
| `subcomponent` | string \| null | Audit-line component granularity (`proxy`, `confirm`, `cred_ui`, … — the values `deploy/components.conf` actually carries); null on lines that carry none |
| `subcomponents` | string \| null | The plural `components` value verbatim (space-joined, from the `ok` line) for readers that need the un-fanned form; the canonical S1 fan-out emits one event per component in `subcomponent` instead |
| `kind` | enum | `check` \| `deploy` \| `rollback` \| `gate-answer` \| `freeze-hold` — `freeze-hold` is emitted only by the controller on freeze flip/clear into the fleet journal (S3; owner: G15 controller work) |
| `outcome` | enum | `started` \| `noop` \| `precheck-fail` \| `deferred-arc` \| `skipped-frozen` \| `succeeded` \| `failed` \| `rolled-back` \| `rollback-failed` \| `superseded` — `started`, `superseded`, `deferred-arc`, `skipped-frozen` are S2/S3-forward outcomes with no legacy producer (the `gate-answer`/`freeze-hold` producer kinds are defined under `kind`); the `freeze`/`gate` triggers are reserved for S2 emitters; S1 delivers `succeeded`/`failed`/`rolled-back`/`rollback-failed` (and `precheck-fail`) only (`noop` stays local-only per the S1 noise discipline) |
| `from` / `to` | string | Commit (repo) or pin version (toolset); absent on pure checks |
| `from_version` / `to_version` | string | Human versions where they exist (auto-deploy's `from_version`/`to_version`) |
| `phase` | string | Box-side failure phase where known (auto-deploy's `phase`) |
| `window` | string \| null | `"maintenance"` when the event was emitted inside a G14 maintenance window (UPDATE_IDLE_SUSPEND_CLOCK.md D1/D6: maintenance events never feed the stall detector) |
| `rollout` | object | `{release_id, wave}` — null until G15 S2 assigns waves |
| `trigger` | enum | `scheduled` \| `manual` \| `freeze` \| `gate` \| `extra-inputs` — absent `trigger` on a legacy line means `scheduled` (the timer path); `extra-inputs` is emitted only on the range-synthesized forced path (`deploy/auto-deploy.sh`, the `trig` variable); `freeze`/`gate` are reserved for S2 emitters |
| `attested` | bool | S1/S2: `false`. S3: `true` when the event rode G13's attested box→plane channel |
| `note` | string | Human/alert text — at S1 synthesized from the audit line itself (the box-side alert reason lives in `$LAST_FAILURE`, which the collector does not pull), never a debug dump |

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
{"event_id":"0196c4a2-…","box_id":"tower","session_epoch":3,"emitted_at":"2026-09-29T22:04:11Z","received_at":"2026-09-29T22:04:13Z","source":"auto-deploy","component":"repo","kind":"deploy","outcome":"rolled-back","from":"e54dc03c","to":"dbc7b206","phase":"reload","rollout":{"release_id":"stable-20260929-2","wave":"canary"},"trigger":"scheduled","attested":false,"note":"daemon-reload failed after install; restored snapshot"}
```

(S2-era example — the `rollout` envelope is null until G15 S2 assigns
waves.)

## 3. Emitters: what the boxes already emit

S1 requires **no new box-side artifact**. The fleet-side canonicalizer
translates the existing audit lines into the standard shape at collect
time. The translation is defined against the actual `audit()` calls in
`deploy/auto-deploy.sh` — all fifteen (event, result) shapes the script
emits (audit lines without a `trigger` field canonicalize to
`trigger: scheduled`; only the range-synthesized forced path emits
`trigger: extra-inputs`):

| Audit line | Standard event (`kind`, `outcome`) |
|---|---|
| `{"event":"check","result":"noop"}` | `check`, `noop` |
| `{"event":"check","result":"precheck-fail"}` | `check`, `precheck-fail` |
| `{"event":"deploy","result":"precheck-fail","from","to"}` | `deploy`, `precheck-fail` |
| `{"event":"deploy","result":"gate-fail","from","to","component"}` | `deploy`, `precheck-fail` (pre-deploy gates refused before any mutation) |
| `{"event":"deploy","result":"snapshot-fail","from","to"}` | `deploy`, `precheck-fail` (pre-mutation; no mutation occurred) |
| `{"event":"deploy","result":"checkout-dirty","from","to","component"}` | `deploy`, `precheck-fail` (**retired** — no longer emitted; the checkout-sync mechanism it guarded was removed outright. Historical audit lines only: aborted, any partial mutation rolled back.) |
| `{"event":"deploy","result":"deploy-fail","from","to","phase"}` | `deploy`, `failed` |
| `{"event":"deploy","result":"reload-fail","from","to"}` | `deploy`, `failed` — mutation occurred, rollback follows; the line carries no `component` or `phase`, so `phase` is synthesized as `"reload"` (noted as synthesized, not box-emitted) |
| `{"event":"deploy","result":"rollback-failed","from","to","phase"}` | `deploy`, `rollback-failed` |
| `{"event":"deploy","result":"rolled-back","from","to","to_version"}` | `deploy`, `rolled-back` |
| `{"event":"deploy","result":"pull-only","from","to","from_version","to_version"}` | `deploy`, `succeeded` |
| `{"event":"deploy","result":"ok","from","to","components",…}` | `deploy`, `succeeded` — the normal success path (components installed, health checks passed); the `components` value is space-joined plural, so this yields **one event per component**, with `event_id` derived per (line, component) |
| `{"event":"rollback","result":"rollback-failed","snapshot"}` | `rollback`, `rollback-failed` |
| `{"event":"rollback","result":"manual-rollback","to","to_version",…}` | `rollback`, `rolled-back` (`from` = `rolled_back_from`) — the operator's own recovery path is in the stream |
| `{"event":"rollback","result":"rollback-unhealthy","to",…}` | `rollback`, `rolled-back`, with `note`: "restored but post-restore health failed" — not a clean restore |

The optional `,"trigger":"extra-inputs"` fragment appears only on forced
extra-input runs; absent `trigger` canonicalizes to `scheduled`.

The audit line's `component` (and the plural `components` on the `ok`
line) becomes the additive `subcomponent`/`subcomponents` field — one
event per subcomponent for the plural success line; standard `component`
is `repo` for every `auto-deploy` line. For the toolset
updater, only the promise is known — SELF_UPDATE.md S2 commits to "the
same format auto-deploy already uses" for who/what/when/versions, but its
result vocabulary is undefined, so the toolset half of this table is
planned-not-known until the updater ships.

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
  collect clock. Event dedup is on `(box_id, event_id)`, and for S1
  canonicalization `event_id` is synthesized deterministically — UUIDv5
  over `box_id|ts|event|result|from|to`, with a per-subcomponent suffix
  for the plural-`components` success line (one event per component) — so
  a re-pulled tail re-canonicalizes to identical ids and
  double-collection is a no-op (box-emitted S2 journal lines carry native
  UUIDv7 instead).
- **Read:** `fleet events` shows the per-box outcome series;
  `fleet events --wave` filters by the rollout envelope (null until G15 S2).
- **Alert — the promptness ask.** The issue's core requirement is that a
  failed fleet update is *noticed*, not discovered. Four fleet-side rules,
  evaluated on every collect:
  1. **Any `rollback-failed`** → immediate alert (a box stuck on a
     known-bad build).
  2. **Correlated failure:** ≥2 boxes reporting `failed`/`rolled-back` for
     the same (`subcomponent`, `to`) within a 30-minute window → fleet
     alert (this is the bad-release shape). Audit lines that carry no
     component (`reload-fail`, the deploy-side `rollback-failed`) are
     correlated on (`to`) alone, labeled `subcomponent: unknown`.
  3. **Silent wave (live at G15 S2):** boxes with a non-null `rollout`
     envelope and zero non-noop events over the armed max-wait window →
     operator alert (feeds G15 §4's max-wait page). At S1 the envelope is
     null on every event and no max-wait is armed, so this rule cannot
     fire — the collector records silence as missing-evidence in the
     journal without paging. (A literal S1 reading would page every
     healthy idle estate, since check-`noop`s stay local-only by design.)
  4. **Stuck precheck:** ≥N `precheck-fail` events on one box inside the
     window → operator alert. The precheck class (gate-fail,
     snapshot-fail, and the retired checkout-dirty) emits non-noop events forever, so no
     other rule catches a box stuck failing pre-deployment — and a
     perpetually un-updated box is #608's pain in a quieter key.
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
  - `skipped-frozen` box-side events and controller-emitted `freeze-hold`
    events explain quiet waves — a wave
    with no events during a freeze is a *frozen* wave, not a failed one,
    and never passes the gate on a window with a frozen gap (G15 §4's
    toll rule consumes these events);
  - `deferred-arc` events feed the eligible-box computation (an arc-busy
    box is not a failing box).
- **Retention:** the event journal gets a real policy — 90 days of
  per-event records per box, compacted after 30 days into per-day
  outcome histograms keyed (box, component, build). This is the fleet
  journal discipline G16 S1's README owed no later than S2 (its design
  doc's OQ2 names S3 — this doc's S2 slice delivers it, and both get
  updated to match). **Delivered:** `fleet events prune` compacts
  30–90d rows into `events_histograms.jsonl` and drops ≥90d rows
  (age on `emitted_at`; undatable/future rows kept; only acked alerts
  ≥90d old are dropped, unacked never); `fleet inventory prune` drops
  ≥90d inventory rows by `observed_at` and rebuilds the snapshot. Both
  hold the store's journal lock and rewrite atomically.

### S3 — control-plane endpoint with attestation (hosted)

- **Sink:** boxes push events to the control plane (or the plane pulls —
  S2's transport decision); the push endpoint is built on the provisioned
  trust root (`ROLLOUT_CONTROLLER_DESIGN.md` §5: the box learns the
  controller's identity at install/provision time, pinned in
  operator-deployed config). The signed box→plane channel itself is S3
  design work owned by the G13 residual — until it exists, tenant-fleet
  gates stay operator-promote-only per G15 §4 (never automatic).
- **Trust:** the attested-admission rule is G13's standing decision —
  tenant-fleet gates consume only box-identity-attested G17 events;
  unattested events may be logged, never gate-consumed
  (TENANT_UPDATE_TRUST_MODEL.md §3, T2). The signed box→plane channel
  mechanism itself is S3 design work — until it exists, tenant-fleet
  gates stay operator-promote-only per G15 §4 (never automatic).
  Forged events are the G15 §6 attack: fake `succeeded` promotes a bad
  release, fake `failed` halts a good one. The `(box_id, event_id)` dedup
  key makes exact resends of a captured event a no-op — nothing more: a
  shell-holding tenant can mint fresh UUIDv7s with forged outcomes that
  sail past dedup untouched. Only attestation stops that. Attestation
  binds (box_id, event_id, outcome, …) to the box identity via the
  provisioned trust root, and the signing key MUST be tenant-inaccessible
  (open question 5: key custody under G13 §3's tenant-with-shell model).
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
  `kind: gate-answer` with outcomes `succeeded` (permitted commit X —
  the outcome vocabulary stretches here: `succeeded` reads as
  "permitted", not "deployed") and `skipped-frozen` (fleet frozen). The
  freeze propagation proof G18 must
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
  the auto-deploy audit shape (the toolset half is planned-not-known);
  event journal in the fleet store with (box_id, event_id) dedup;
  `fleet events` CLI; the four alert rules with interim journal+exit-code
  transport; noop-stays-local noise discipline.
  No box-side change. #608's acceptance sketch is this slice.
- **S2 — box-side journal + gate aggregation:** `update-events.jsonl`
  emitted in-shape by both updaters; per-wave outcome census, failure-rate
  baseline inputs, per-(box,session,build) soak windows;
  event↔inventory cross-checks (**shipped** — `fleet events crosscheck`
  evaluates each box's `deploy`/`succeeded` claims against the inventory
  journal: confirmed / violation (flagged, not convicted) / inconclusive;
  rolled-back/restored claims remain a follow-up; PR (#809));
  the 90-day/30-day journal discipline shared with G16.
- **S3 — hosted endpoint:** control-plane push endpoint on G13's signed
  box→plane channel; `attested` admission rule for gate quorum;
  per-tenant attribution and slicing (H11); tenant-fleet alert routing.

## Open questions

1. **Noop shipping:** S1 keeps check-noops local. If a future gate wants
   tick-heartbeat evidence (a wave of silent boxes is ambiguous), the
   heartbeat may need to travel — or the silence rule (alert rule 3, scoped to G15 S2) may suffice. Revisit when a consumer proves need.
2. **Tenant-box alert ownership:** when a tenant box's update
   `rollback-fail`s, who gets the alert — the tenant, the operator, or
   both? Tenant-visible is G12's surface; the routing rule belongs to the
   H14/push story, not this doc. S1/S2 alert to the operator only.
3. **Session-epoch provenance:** the provisioner must maintain the
   reimage counter (§2, §4). Today no box record carries it. G15 §8's
   box_id-stability requirement gets a sibling: the provisioner's per-box
   record owns `session_epoch`, incremented at reimage. Until then the
   schema's `session_epoch` stays `null` and keying degrades to
   (box, build).
4. **Cross-component correlation:** a bad repo build and a toolset pin
   failure on the same box in the same window look correlated but aren't.
   The census gates are per (subcomponent, build); lines that carry no
   component (`reload-fail`, the deploy-side `rollback-failed`) correlate
   on (`to`) alone, labeled `subcomponent: unknown`. The fleet alert rule
   (S1 rule 2) keys (subcomponent or unknown, `to`).
5. **Attestation key custody:** under G13 §3's tenant-with-shell model, a
   box-resident signing key the tenant can read collapses the S3 trust
   story — attestation that the tenant can sign for is not attestation.
   Where the key lives (and how the updater reaches it without the tenant
   being able to) is S3 design work alongside the signed channel itself.

---
*Design for G17 (#608), from the 2026-09-28 fleet-rollout gap analysis
(`FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md`). Implementation (S1–S3) remains —
tracked on #779 (the fleet inventory/event-reporting implementation issue; #608 closed on the design). Related: G15 (#606, `ROLLOUT_CONTROLLER_DESIGN.md`), G16
(#607, `FLEET_VERSION_INVENTORY_DESIGN.md` + `fleet/`), G18 (#609),
G11/G12 (`UPDATE_CHANNEL_POLICY.md`), G13 (#555,
`TENANT_UPDATE_TRUST_MODEL.md`), G14 (#556, `UPDATE_IDLE_SUSPEND_CLOCK.md`),
H11, P7.*
