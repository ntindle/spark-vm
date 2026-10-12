# Fleet-consumption lane, part 2: G25 sentinel feed + G26 metering S4 after D-MT1

**Date:** 2026-10-11 (build-loop gap turn, slot 20261011-2159).
**Pinned to:** main `fa0fd28b1ba2a257b5e0edf3846fa1e50e3b9dc0` for all
in-repo claims. Issue/PR numbers are GitHub references as of
2026-10-11. Doc-first; honesty rules apply (`docs/POSITIONING.md`):
everything below is **current state and work to do**, not promises.
No sentinel exists, no meter daemon exists, no envelopes have been
emitted.

**Non-overlap map (what this doc is not):**
- `docs/FLEET_OBSERVABILITY_CONSUMPTION_GAP_ANALYSIS.md` (2026-10-01,
  gap turn 20261001-0559) — the G21–G26 decomposition. This doc
  consumes it and re-analyzes nothing that still holds; it adds what
  D-MT1 and the operator-plane build-path analysis changed for G25
  and G26. G21–G24's state is untouched here.
- `docs/MULTI_TENANT_PLANE_MODEL_DECISION.md` (2026-10-09, D-MT1–D-MT5)
  — one plane per tenant, the operator plane (D-MT4), meter envelopes,
  the revisit trigger. This doc consumes it; the model decision stands.
- `docs/OPERATOR_PLANE_BUILD_PATH_GAP_ANALYSIS.md` (2026-10-10,
  F-OP1–F-OP8, D-OP1–D-OP7) — the operator plane's build pins and
  #1257–#1261. This doc consumes it; its filings are not re-filed.
- `docs/SENTINEL_TELEMETRY_SURFACES.md` (2026-09-24) — the four-surface
  census (A1–A6, #353–#357, #360) and H5 prerequisites. This doc
  consumes it; the census is not re-done.
- `docs/USAGE_METERING_DESIGN.md` (H12) — the billable-unit taxonomy
  and S1/S2/S3 sources. This doc names what S4 needs; the taxonomy
  stands.

## 1. The vision (verbatim from the 2026-10-01 decomposition)

**G25 — sentinel feed:** "The human watches a *signed* audit log
*shipped to the sentinel*" (`docs/HOSTED_GAP_ANALYSIS.md` vision).

**G26 — metering S4:** "Usage metering consumes the fleet's event
streams where they are the ground truth" — the fleet event journal
becomes metering's fourth source (after confirmd audit.log, swap.log,
muse-job JSONL), feeding suspend/update-minute accounting from
maintenance-window events.

Both slices were "queued for future gap/feature turns" on 2026-10-01
(#799 and #800, both open, zero comments). They are analyzed now
because D-MT1 and the operator-plane analysis changed their answers:
the sentinel has a placement it didn't have, and the meter feed has a
transport it didn't have.

## 2. What moved since 2026-10-01

- **D-MT1 (2026-10-09): one plane per tenant.** Every hosted signup
  provisions a dedicated `sparkvm-control` instance (Worker + D1 +
  VAPID identity). "Tenant planes emit meter envelopes" to the
  operator plane (D-MT4). The H12 honest limit: meter envelopes
  should carry the per-tenant-plane infra cost (Worker + D1 per
  tenant) so tenant pricing can reflect it.
- **Operator-plane build path (2026-10-10):** F-OP2/D-OP2 pinned
  envelope auth (operator-minted, per-tenant-plane,
  provisioner-installed, verify-only voice material; tenant field
  stamped by the operator-declared mapping, never inferred from
  plane/box-controlled bytes) — filed as #1258. D-OP6 defaulted the
  #908 spend ledger onto the operator plane's D1. #1257 (the design
  spec) is closed.
- **Sentinel census unchanged:** #353 (A1 no shared envelope), #354
  (A2 no sequencing/auth), #355 (A3 second-resolution collisions),
  #356 (A4 trust tiers unstated), #357 (A5 fail-visible write — fixed
  to stderr) all open; #360 (A6 rotation bound) closed. H5
  prerequisites 1–4 all still owed.
- **Metering prerequisites unchanged:** #376 (bounded spool rotation),
  #377 (idle-heartbeat semantics), #378 (unknown-tenant quarantine)
  all open. The metering design doc carries zero "fleet" mentions —
  the S4 mapping from the 2026-10-01 analysis was never written into
  the design, so it remains a design note, not a consumer.
- **#999 S4b-4 journal sink (shipped):** the tenant-plane D1 gains
  `phone_home_events` — phone-home session events now have a
  plane-side journal. Under one-plane-per-tenant, that journal lives
  on the tenant's plane, not on a shared plane.
- **#1348 (plane update-event reporting, #1288 S5) shipped 2026-10-11:**
  plane-side event journal + `read_plane_events` reader — G25's "gate
  decisions" ingested-record class has a concrete source. (#1261
  itself remains open; the S5 slice landed under #1288/#1348, not as
  a #1261 close-out.)

## 3. G25 — sentinel feed: vision vs state

### Findings

- **F-25-1 — The feed's transport was unspecified on 2026-10-01 and
  is now pinned by the plane boundary.** The 2026-10-01 analysis
  decomposed the vision into three unbuilt pieces: (a) the signing
  story, (b) the transport, (c) the sentinel-side consumption
  contract. Since then, the operator-plane build-path analysis
  placed the sentinel role on the operator plane ("Sentinel (H5, via
  #464): the sentinel role runs on the operator plane" — §2, resting
  on D-MT4), and D-OP1's trust boundary generalizes the summons
  rule: tenant-adjacent compute never holds operator-plane
  credentials. The transport leg (b) is therefore tenant-plane →
  operator-plane shipment — the box never ships to the operator
  plane directly
  (that would be a new box-side channel contradicting the G18
  no-new-inbound-listener posture); the tenant plane aggregates
  box-local telemetry and ships it. The #799 issue body predates
  D-MT1 and does not say this.
- **F-25-2 — The ingested record set is split across the plane
  boundary.** confirmd `audit.log` lives on tenant boxes; fleet
  events live on operator estates (box/operator-side JSONL) AND on
  tenant-plane D1 (`phone_home_events`, #999); gate decisions have
  a reader after #1261. The sentinel's "what it ingests" question
  has two halves: estate-side records the operator plane can read
  from the estate dir (the G21 read-API pattern), and tenant-plane
  records that must be *shipped*. No slice owns the second half.
- **F-25-3 — The signing story has not moved.** A2's prescription
  (per-surface monotonic counters with restart epochs; no global
  ordering required) is still the ship-detection story, and none of
  the four surfaces implements it. The G13 attested box→plane
  channel is still S3 design work. "Signed audit log" remains the
  G13 channel's promise, not a shipped property — and the interim
  truth is A4's: surfaces are unlabeled claims until the trust
  tiers land.
- **F-25-4 — "Operator-attested" got a sharper meaning under D-MT1.**
  G25's S2 (unattested interim feed) labels the interim view
  "operator-attested-only". Under one-plane-per-tenant the operator
  *provisions* the plane (and its journals), so "operator-attested"
  means "the plane's journal as the operator observed it" — but only
  if the shipment is tamper-evident. A seq counter without
  tamper-evidence on an operator-provisioned plane is exactly what
  the operator already trusts; the open question is what a gap
  means, not whether gaps are detectable. The transport issue pins
  this.

### Decisions (D-25 series, continuing the 2026-10-01 D-series)

- **D-25-1 — Operator-provisioned = operator-attested.** On the
  operator plane, the interim feed's trust label is the
  provisioner's: the tenant plane's journals arrive as
  operator-observed records, tamper-evident-not-tamper-proof (the
  D-OP2 credential proves the voice, not the bytes). The label stops
  at tamper-evident because a tenant with owner access to their own
  plane can forge the journal the operator observes — the signing
  half of the vision stays with the G13 channel. This replaces the
  vaguer "operator-attested-only" with the mechanism.
- **D-25-2 — One shipment channel, `kind`-discriminated.** The
  tenant-plane→operator-plane shipment rides the D-OP2 envelope
  channel: one credential class to review (F-MT2's economics apply),
  one intake, with a `kind` discriminator (`meter` | `event`) in the
  record. A second channel would double the review surface for no
  trust gain — the envelope credential is already verify-only voice
  material for exactly this direction. Replay protection and
  fail-closed-on-seq-regression live in #1349's intake scope, not in
  the channel: the intake refuses a record whose `seq` regresses
  within its `epoch`.
- **D-25-3 — Seq gaps are fail-visible, always.** Per-surface
  monotonic counters with restart epochs (A2's prescription) on the
  shipper; the operator-plane intake raises a seq-gap alert on any
  discontinuity and on epoch resets it cannot account for — the same
  posture as A5's stderr signal. The sentinel's first rule is
  "the trail has a hole", not a signature check.

## 4. G26 — metering S4: vision vs state

### Findings

- **F-26-1 — The envelope record schema does not exist.** D-MT1 names
  envelopes, D-OP2 pins their auth, #1048 covers plane-side
  ingestion — but no issue covers the envelope *record* itself: its
  fields, its tenant-stamping rule, its seq/ts, its batching and
  retention bounds. #1258 has nothing to authenticate and #1048 has
  nothing to ingest until the schema exists. The metering design's
  S1/S2/S3 mappers each emit `tenant: unknown` until H10 lands; the
  envelope schema is where that rule and the quarantine rule
  (#378) are stated for the plane-emitted half.
- **F-26-2 — No maintenance-window producer exists.** `fleet/events.py`
  pins `"window": None  # G14 maintenance windows are future` — no
  maintenance enter/exit event kinds exist in any journal. G26's S1
  ("the maintenance-minute question answered as design — billable /
  not / operator-declared") is unanswerable from the fleet stream
  because the stream has no maintenance events to map. This is a
  G14 producer contract, not a G26 mapping question.
- **F-26-3 — Prerequisites still open, mapping still a note.** #376,
  #377, #378 are all open, unchanged since 2026-10-01. The metering
  design doc carries zero fleet mentions, so the 2026-10-01 "design
  note, not a consumer" status is unchanged — the fleet stream is
  still unmapped, and #800's gate on the prerequisites still holds.
- **F-26-4 — The quarantine policy is now decided.** The operator-plane
  analysis pinned it: `tenant: unknown` envelopes are unbillable and
  quarantined into an audit-visible holding set, never silently
  dropped, never folded into a tenant's aggregates (#378 keeps the
  policy issue; this doc does not re-file it). G26's S2 detection
  surface is therefore the envelope stream itself — unknown-tenant
  events are visible at ingest, not discovered later.

### Decisions (D-26 series)

- **D-26-1 — The envelope schema is its own spec issue.** It is not
  folded into #1048's ingestion slice: the record contract must
  exist before the reader, and #1258's auth must bind to a named
  schema version. #1048's acceptance criteria reference the schema
  instead of inventing their own fields. **Lineage:** #1350's schema
  EXTENDS the metering doc's canonical envelope grammar (`v`, `seq`,
  `epoch`, `ts_ns`, `tenant`, `source`, `event`, `trust`, allowlisted
  `attrs`, `mac` reserved — `docs/USAGE_METERING_DESIGN.md` §3) —
  adopting, not re-deriving, it — adding the tenant-stamping rule
  (#798 S1), plane identity, the D-MT1 infra-cost line,
  batching/TTL/retention bounds, and the `kind` (`meter`|`event`)
  discriminator story with #1349's event records. #1349's event
  records ride the same extended envelope with `kind: event` (not a
  parallel envelope) — one channel, one grammar, per D-25-2; the
  metering consumer reads `kind: meter` records, the sentinel intake
  reads `kind: event` records.
- **D-26-2 — Maintenance-minute accounting waits on G14 events.**
  Until the maintenance enter/exit kinds exist, G26's S1 answers the
  maintenance-minute question as "unmappable — no producer", not as a
  guess. No meter dimension ships on an event kind nobody emits.
- **D-26-3 — The envelope schema carries the D-MT1 infra-cost line.**
  The H12 honest limit ("meter envelopes should carry the
  per-tenant-plane infra cost") becomes a schema field, not a billing
  afterthought — pricing reflects what the record already measures.

## 5. Composition with the sibling lanes

- **#1349's transport spec** is the G25 build half of this doc's
  D-25 series; **#799 stays the spec home** (S1 record set +
  verification contract + S2 interim + S3 attested).
- **#1350's schema** is the G26 build half of D-26-1/D-26-3; **#1048
  stays the ingestion home**, **#1258 stays the auth home**.
- **#1351's event kinds** are the G14 producer contract G26's S1
  consumes; **#800 stays the S1–S3 mapping home**.
- **#1257 (design spec)** owns the operator-plane intake placement
  for #1349's shipped records and #1350's schema placement; #1257 is
  closed — these issues are filed against its shipped pins.
- **The sentinel's rule engine** remains a later #799 slice, after
  the feed spec — the same ordering the 2026-10-01 analysis set.

## 6. Gaps filed this turn

- **#1349 — Sentinel feed transport: tenant-plane to operator-plane
  event shipment (G25 transport leg, F-25-1).** The shipper, the
  envelope-channel record kind (D-25-2), the operator-plane intake,
  the seq-gap alert, the tamper-evidence story (D-25-1) — the build
  inputs #799's S1 spec consumes. Explicit non-goal: the
  sentinel-side rule engine (a later #799 slice).
- **#1350 — Meter-envelope record schema (G26/H12, F-26-1).** Fields
  (tenant, plane identity, per-plane infra cost, S1/S2/S3 meter
  dimensions), per-plane seq + ts, batching/TTL/retention bounds, the
  `kind` discriminator story with #1349's event records. The record
  contract #1258 and #1048 both reference.
- **#1351 — G14 maintenance-window event kinds on the fleet journal
  (G26 S4 producer, F-26-2).** The enter/exit event kinds, their
  producers, their fields — the producer contract G26's S1 mapping
  consumes.

#799 and #800 stay OPEN (analysis-only homes for the slices); #799's
and #800's bodies are amended by pointer comment with the D-25/D-26
decisions and the new issue numbers.

## 7. Honest limits

- D-25-2's one-channel call is a review-economics judgment (F-MT2),
  not a security proof: if the #1349 transport spec (filed against
  #1257's shipped pins) finds a reason the event records need a
  separate channel (e.g., different retention or a different failure
  mode than metering), it overturns D-25-2 with the reasoning
  recorded.
- D-25-1's "operator-attested" label is only as strong as the
  provisioning story: a tenant who can write their plane's journal
  directly (owner access) can forge what the operator observes. The
  label is documented as tamper-evident, not tamper-proof — the
  signing half of the vision stays with the G13 channel.
- D-26-2 means the fleet stream is not a complete metering source
  until G14 ships — the "ground truth" claim in the vision is scoped
  to what the stream actually contains, not what it will contain.
- Nothing here emits, ships, meters, or bills anything.
