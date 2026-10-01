# Status-page feed spec (G22 S1)

Doc-first; the honesty rule is G17 S1's (quoted in §1, from
`docs/UPDATE_EVENT_REPORTING.md` §4), extended to the page itself by the
G21–G26 analysis's no-fiction contract: everything below is
**current state and work to do**, not promises. Statuses are pinned to the
repo as of this commit. This doc is the S1 slice of G22 (tracked on issue
#796): the feed contract for the P7 status page — which journal records
become feed rows, the dedup/idempotency rule, the ack→resolve lifecycle,
and what stays operator-only. It designs nothing else: S2 builds the page,
S3 answers the incident-comms question.

## 1. What the earlier designs already decide (bounds, not repeated)

- **G16 S1** (`fleet/inventory.py`): the estate-dir collector keeps a
  JSONL inventory journal + rebuildable snapshot store. The collector's
  `received_at` on every ingested record is the collector clock — box
  clocks are never trusted (see the 20261001-1029 distribution turn's
  S2 cross-check).
- **G17 S1** (`fleet/events.py` + `docs/UPDATE_EVENT_REPORTING.md` §4):
  the fleet event journal (canonical shape: `event_id`, `box_id`,
  `session_epoch`, `emitted_at`, `received_at`, `source`, `component`,
  `subcomponent`, `subcomponents`, `kind`, `outcome`, `from`, `to`, `phase`, `rollout`, `trigger`,
  `attested`, `note`) and the alert journal (`alerts.jsonl`), with four
  alert rules evaluated on every collect: (1) any `rollback-failed` →
  immediate alert; (2) correlated failure (≥2 boxes, same
  `(subcomponent, to)` or `(to)`-alone for audit lines without a
  component, 30-minute window); (3) silent wave — **not live until
  G15 S2** (the `rollout` envelope is null on every event today, so this
  rule cannot fire); (4) stuck precheck (≥N `precheck-fail` on one box
  inside the window). Alert transport S1: the alert is journaled and
  `fleet events watch` exits nonzero on unacknowledged alerts.
- **The G17 S1 honesty rule**, quoted, not paraphrased: *"The P7 status
  page's alert feed is the formal home when it exists; **nothing in S1
  pretends the feed exists before it does**."* This spec extends that
  rule to the page itself.
- **The G21–G26 analysis** (`docs/FLEET_OBSERVABILITY_CONSUMPTION_GAP_ANALYSIS.md`,
  PR #801) decided G22 is `[HOSTED]`: the status page is a
  tenant/public-facing surface fed by the alert journal and the
  tenant-scoped read paths (G24), with an explicit "no fiction"
  contract — every row traceable to a journaled event. Until the feed
  exists, the page does not ship.
- **Not landed:** G24 (no `tenant` field on the stream, no tenant-scoped
  read path), G25 (the sentinel signed audit log has no ship path),
  G15 S2 (wave assignments; the `rollout` envelope is null). This spec
  names what the feed may honestly show *before* each lands, and what
  must wait.

## 2. The feed contract

The status-page feed is a **derived projection of the three fleet
journals** (events, alerts, inventory) — read-only, computed at read
time from the estate dir, no mutable feed-local state. The journals are
the single source of truth; the feed keeps no copy and no memory.

1. **Row keys are journal keys.** An alert row is keyed by `alert_id`;
   an event row by `(box_id, event_id)`. A feed read renders each key
   exactly once; repeated reads are idempotent by construction.
2. **Every row cites its journal source.** A row the reader cannot trace
   to a journaled record does not exist — no synthesized availability,
   no marketing uptime, no "estimated" rows.
3. **The feed shows its own freshness.** Each render carries
   `data_current_as_of` = the newest `received_at` across the event and
   alert journals (collector clocks only; the alert journal can lag
   independently, so the freshness stamp must cover both). Absence of alerts is rendered as
   "no journaled alerts in the window", never as "all systems
   operational".
4. **Silence is missing-evidence, not health.** A store with no journal
   rows shows "no data" — it must never be mistaken for a clean fleet.
   (Same discipline as the 20261001-1029 cross-check: missing evidence
   never convicts, and here it never acquits either.)

## 3. Which journal records become feed rows

### 3.1 Alert rows (all four rules)

Every alert in `alerts.jsonl` becomes a row, with its journaled fields:
`schema`, `alert_id`, `rule`, `fired_at`, `box_id`, `subcomponent`, `to`,
`detail`, `acked`. The row's lifecycle state (§5) is rendered alongside; the
state is derived, the fields are journaled.

- Rule 1 (rollback-failed): a box stuck on a known-bad build. Row is a
  per-box row.
- Rule 2 (correlated failure): the fleet-shape row. Note its
  `subcomponent: unknown` convention for component-less audit lines —
  the feed renders the label verbatim, not a prettier fiction.
- Rule 3 (silent wave): **no rows until G15 S2.** The rule cannot fire
  while the `rollout` envelope is null; the page must not pretend the
  fleet is wave-monitored before wave assignments exist.
- Rule 4 (stuck precheck): per-box row. A perpetually precheck-failing
  box is #608's quieter pain and the page should name it as such.

### 3.2 Rollout rows

Rollout rows come from two journaled sources only:

- The `rollout` envelope on event records (`release_id`, `wave`): while
  the envelope is null on every event (today), the page shows "no
  active rollout" — honestly, not as a gap in the page.
- `kind: freeze-hold` events (G15 S3 producer, tracked on #777): the
  freeze flip/clear records, rendered as "fleet frozen / freeze cleared
  at <received_at>". No freeze-hold rows until G15 S3 ships the
  controller producer — read-time derivation means nothing appears
  before it lands, and the prose must not imply the source exists
  today.

Until G15 S2 lands, there are no per-wave census rows. The page does not
invent waves.

### 3.3 What never becomes a row

- Nothing synthesized from absence: no "uptime" percentage, no
  "healthy" rollup, no green banners derived from silence.
- `noop`-local check outcomes stay local-only (the G17 S1 noise
  discipline); they were never journaled and the feed cannot see them.
- Raw `note`/`detail` strings pass through the `_clean_text` discipline
  at synthesis (`fleet/events.py`); the feed must not re-interpret
  them.

## 4. Dedup and idempotency

The rules are already in the producers; the feed must not invent new
ones:

1. **Alert identity is `alert_id`** — `uuid5(rule|box_id|subcomponent|
   to|dedup_key)` — stable across collector re-runs. The collector
   already dedups appends on `alert_id` (re-firing the same alert
   appends nothing). The feed renders each `alert_id` once; it never
   holds its own dedup set.
2. **Event identity is `(box_id, event_id)`** — the collector dedups
   ingests on this pair. Feed rollup rows (e.g. "correlated failure
   involves N boxes") count distinct journaled keys, not rows.
3. **Ack is a journal rewrite, not a feed action.** `fleet events ack`
   sets `acked: True` by atomic rewrite (tmp + `os.replace`). The feed
   reads the current journal; an ack takes effect on the next render.
   There is no feed-side ack cache.
4. **No feed writes.** The S1 feed has no write path — acking stays in
   the operator CLI until S2. A tenant-visible page (S2) shows acked
   state but never acks through the feed; ack remains an operator
   action (tenant ack is an S3 question at earliest).

## 5. The ack→resolve lifecycle

Two distinct transitions; conflating them is the design's central
trap.

- **Acknowledged** is operator-declared: `fleet events ack --alert-id
  <id>` flips `acked` in the journal. It means "a human saw this" —
  nothing more.
- **Resolved** is journal-derived, never declared: a row counts as
  resolved when a *later journaled record* shows the condition cleared.
  Resolution is a pure function of journal state computed at read
  time; there is no "resolved" flag in the journal and no feed-local
  resolution state.

The lifecycle states are `firing → acknowledged → resolved`, but the
path is not a pipeline: an alert may resolve without ever being acked,
and — critically — **an acknowledged alert that has not resolved stays
listed**. Ack does not silence the row; only journaled evidence does.
A firing alert with no follow-up evidence stays firing forever — the
page never auto-clears what it cannot disprove.

Resolution conditions, per rule (derivation contract; the exact
window arithmetic is implementation detail):

| Rule | Resolves when the journal shows… |
|---|---|
| 1 — rollback-failed | a later same-`(box_id, subcomponent)` event with outcome `succeeded` or `rolled-back` (the box is off the known-bad build) |
| 2 — correlated failure | every correlated box has a subsequent same-`(box_id, subcomponent)` deploy whose `to` differs from the flagged build's `to` (recovery), or a newer `release_id` covers those boxes (the bad release is superseded — not evaluable until G15 S2 assigns waves; the S2 design pins the "covers" semantics) |
| 3 — silent wave | the box emits non-noop events inside the window again (not live until G15 S2) |
| 4 — stuck precheck | a later same-`box_id` event with a non-`precheck-fail` outcome (the box proceeded past pre-deployment) — per-`box_id`, matching rule 4's own box-keyed grouping (the alert's `dedup_key` is the window anchor, `subcomponent` unset) |

Resolution never requires the ack; resolution never follows from it.
When journals disagree with each other (event journal claims success,
inventory shows otherwise), the G17 S2 event↔inventory cross-check owns
the verdict — the feed renders journaled rows and, once that slice
lands, surfaces cross-check violations as rows. It never synthesizes a
reconciliation.

**Derivation discipline (the scan bound).** Resolution scans are
forward-only: only records with `received_at` ≥ the alert's
`fired_at` can resolve it — no earlier record can clear a later alert,
and the collector journals are append-ordered in `received_at` (the
collector stamps it at ingest). A feed read therefore scans forward
from the alert's journal position, never the whole journal from its
head. Tractability rests on that append order. If a journal
rotation/pruning design lands later (G19's retention design is
per-record with chain-safe deletion), it must preserve per-alert
resolution evidence — or this contract re-scopes with it. Window
arithmetic stays implementation detail; the scan bound is contract.

## 6. What stays operator-only (the S2a page is an operator page)

S1 pins the feed contract; the operator page ships as the first build
of S2 (§9). Until S2's tenant stage lands there are no tenant-visible
rows, and the page says so.

What is operator-only, and why:

- **Raw `detail`/`note` text.** Fields are `_clean_text`-stripped at
  synthesis but may still carry box-local paths, internal topology, or
  operator-sensitive context. Tenant rows (S2) get a curated summary
  ("release X failed rollout on N boxes"), never the raw journal text.
- **`box_id` in the OSS sense.** In a hosted estate, box ids are
  internal topology. Tenant-visible rows name tenant-visible
  surrogates (region/pool rollups or per-tenant affected-box counts),
  never raw box ids. The surrogate vocabulary is an S2/G24 decision;
  S1 must not invent it.
- **Inventory detail.** The inventory journal carries per-box estate
  facts; the feed's rows expose only what the alert/rollout semantics
  need.

The framing rule holds: the same feed surface serves the self-hosted
N-box operator first (their page shows their own box ids — no
surrogate needed); the hosted control plane reuses it behind the
tenant read path.

## 7. Cross-lane ordering (no re-litigation)

- **G23 (alert fan-out into the H14 push plane):** the page is the feed,
  not the pager. Who pages the operator is G23's intake spec; this
  feed must not become a paging substitute. A feed that goes un-read is
  a G23 gap, not a G22 bug.
- **G24 (tenant-scoped consumption):** S2's page consumes G24's tenant
  read path. Until then the page is operator-only (§6) — no
  tenant-scoped history rows, no tenant surrogate naming.
- **G25 (sentinel feed):** the S2a operator page consumes the collector
  journals directly. The S2 tenant-visible surface should consume the
  sentinel-signed feed when it exists — tenant-visible rows need
  tamper-evidence the operator journal cannot offer. This is a
  sequencing note, not a G25 design.
- **G26 (metering):** the feed is not metering's source; G26 reads the
  event stream directly. No coupling.

## 8. Open questions

- **Q1 — Should resolution persist, or always re-derive?** This spec
  says re-derive at read time (no mutable feed state, journal is the
  source). A persisted resolved-row would be a second journal and would
  need its own audit discipline — deferred unless a feed consumer
  needs history the journals cannot answer.
- **Q2 — Does the tenant-visible S2 page need the sentinel-signed feed,
  or is the operator journal enough?** This spec's position: operator
  journal suffices for S1; S2 should wait on the G24 read path *and*
  prefer the G25 signed feed, because a tenant disputing a row needs a
  tamper-evident record, not the operator's word. Argue the other way
  in the S2 design.
- **Q3 — Public page or tenant-scoped only?** S2 delivers
  tenant-scoped. A fully public feed reads as marketing uptime and
  collides with the P3 marketing gate's no-commitment posture — a
  public row is a promise, and this design refuses to make promises
  the journals cannot keep. Public visibility is a separate decision
  with its own doc, not a default.
- **Q4 — Should the page show "all systems operational"?** No. The
  no-fiction contract forbids it; the honest render of an empty window
  is "no journaled alerts in the window". If a stakeholder wants a
  green banner, that requirement arrives as a named change to §2.3
  with the evidence bar it must meet.

## 9. Build slices (for the feature/distribution track, not this doc)

- **S1 — this spec.** Issue #796 stays open for S2/S3.
- **S2 — the page.** Two stages; #796 stays open across both.
  - **S2a — the operator page.** Wave/incident feed from the collector
    journals, operator-only rows, no G24 required. The self-hosted
    N-box operator sees their own box ids — no surrogates needed. This
    is the P7 read-only ops surface, the formal home the G17 S1
    honesty rule names.
  - **S2b — tenant-scoped history.** Layered on G24's tenant read path;
    prefers the G25 signed feed for tenant-visible rows; tenant rows
    get curated summaries and box-id surrogates per §6. Until S2b
    lands there are no tenant-visible rows, and the page says so.
  - Ack stays an operator action throughout; no tenant ack through the
    feed.
- **S3 — the incident-comms question (#368).** What notifies users when
  the status page is the paid surface: the page is the feed, the pager
  is G23 — but #368's "who tells the user, and in what words" is
  unanswered and belongs here, not in G23.
