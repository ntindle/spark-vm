# Provisioning + metering convergence (2026-10-06)

**Vision vs state for the metered, capped, provisioned box** — pinned to
main `645e814` (v0.6.0) for all in-repo claims. This is the convergence
pass over `docs/BOX_PROVISIONING_GAP_ANALYSIS.md` (2026-10-03, main
`74f3e76`), `docs/SPEND_CAP_ENFORCEMENT_GAP_ANALYSIS.md`,
`docs/METERING_BILLING_GAP_ANALYSIS.md` (2026-10-05), and
`docs/USAGE_METERING_DESIGN.md` (H12). Plane claims inherit the pinned
reads those docs record (2026-10-02 provisioning read; 2026-10-05 metering
read of the `sparkvm-dev-website-v2-cloudflare-management-infra`
workspace's `control-plane/worker.py`) — no fresh plane read this turn;
per the repo honesty convention, plane state is pinned to documented
reads, not to a repo commit. This turn additionally verified in-repo that
`docs/CONTROL_PLANE_API_REFERENCE.md` carries **zero** `provision` or
`meter` mentions — the plane still has no provisioning or metering
surface in its own API reference.

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below
is **current state and work to do**, not promises. The hosted product is
not live.

## 1. The vision, restated in one paragraph

An invite claim becomes a running, paired, metered box with no operator
steps: the orchestrator consumes the claim, the Fly driver provisions a
machine from the golden image, first-boot identity seeding binds the box
to the plane, plane-attested pairing enrolls it, the box meters its own
resource use, the spend ledger attributes burn to the tenant lineage,
pre-provision cap checks refuse over-budget claims, and the destroy
worker ends breaching boxes with notice. Tracked on #851 (provisioning),
#908 (spend caps), #1047/#1048 (metering).

## 2. What the lane gained since 2026-10-03

The 2026-10-03 analysis filed #905–#908 and stopped there. Since then:

- **Spend-cap lane decomposed** (SPEND_CAP_ENFORCEMENT_GAP_ANALYSIS.md):
  #1074 (spend-ledger D1 schema + provision-record ingestion), #1075
  (pre-provision cap-check hook + projected-cost function), #1076
  (destroy-on-breach worker + pre-destroy notice), #1077 ([POLICY] cap
  catalog). The D-C6 gate (user-set 2026-10-03) is satisfied for the
  operator-side slice — the balance source is the #1074 ledger; it stays
  binding on the tenant-side credit-pack extension.
- **Metering lane decomposed**: USAGE_METERING_DESIGN.md (H12, §4
  `meter_agent` producer: `resource_window` every 5 min, `idle_heartbeat`
  every 60 s) → #1047 (box-local producer; gated on #376 rotation bound
  and #377 idle semantics), #1048 (plane authenticated meter-batch
  endpoint + dedupe + quarantine per #378).
- **The pairing bootstrap vocabulary the attestation design consumes is
  now shipped**: #844's typed `approved_by='bootstrap'`
  (`pairing/README.md` First-owner-key bootstrap), #846 token rotation,
  #864 heartbeat, #845/#954 dashboard. #907's design no longer has to
  invent the approval-record shape — it consumes it.
- **v0.6.0 released** (`645e814`, 2026-10-06): the golden image now has a
  release to pin against.
- **H4 live-API clearance is actionable**: `custom.flyio` token verified
  (2026-09-20, re-verified in FLY_DRIVER_RESEARCH F6); user-set caps
  $5/run / $25/month with auto-destroy at slot end (2026-09-24). Nothing
  has exercised the live API yet.

## 3. Findings: genuinely-new gaps (F-P series)

Gaps already filed (#905, #906, #907, #908, #1074–#1077, #1047, #1048) are
not re-filed. These are new:

- **F-P1 — the golden image has a gate but no producer.** `docs/GOLDEN_IMAGE_GATE_PROCEDURE.md`
  gates *an image* per build (round-trip: file → answer → grant →
  verify, via the harness gate-fixture tooling). Nothing builds the
  image: no Dockerfile/packer/Fly-image recipe, no CI job, no pin of
  v0.6.0 as the base. FLY_DRIVER_RESEARCH recommends the golden-image
  path over exec-install, but the image is an artifact with no producer
  and no owner. Scope note: G51.1's state list named "no golden-image
  build" inside the #905 filing, and #905's body cites the golden image
  as the driver's recommended path — this gap explicitly re-scopes that
  overlap: **#905 narrows to the driver + exec-install path; the
  golden-image producer moves to #1087** (no two-owner conflict).
  Filed as a new issue (see §6). The image producer is shared
  infrastructure: it serves the provision path (#905) and the rollout
  reimage waves (G11, `ROLLOUT_CONTROLLER_DESIGN.md`), not the driver
  alone.
- **F-P2 — the meter envelope has a producer and an ingestion endpoint,
  but no emission worker.** #1047 scopes the box-local `meter_agent`
  (spool under the #376 rotation bound); #1048 scopes the plane's
  authenticated batch endpoint + dedupe. Neither owns the box-side
  **emission worker** that ships spooled envelopes to the plane (retry,
  backoff, plane-down degradation — the same transport discipline the
  #953 upload-filings scan and #864 heartbeat already demonstrate).
  USAGE_METERING_DESIGN.md §6 names the emission pattern; no issue owns
  it. Filed as a new issue (see §6).
- **F-P3 — G51.3's attestation token needs a plane-readable provision
  record, which pins the provision-record store.** G51.3's mechanism
  ("validated against and consumed from the provision record") runs at
  the **plane's** pairing endpoint — so the provision record must be
  readable by the plane Worker at approve time. That rules out an
  orchestrator-local or in-repo-filesystem provision store for the
  attestation half: the provision record's home is D1 (the plane's
  database), whether the orchestrator itself runs in-repo or on the
  plane. Why not an orchestrator-side validation callback instead: the
  callback alternative fails on availability, not trust — the plane must
  validate tokens while the in-repo cron isn't running, and a synchronous
  plane→orchestrator round trip makes every pairing approval depend on
  the orchestrator's liveness. The unexamined dependency D-P2 names
  honestly: **who authenticates the orchestrator's D1 writes** — the
  orchestrator writes operator-trusted records consumed by both G51.3
  validation and the #1074 spend ledger, so the write credential (and
  its custody) is the actual trust root, not the store choice. That
  credential design rides with #1089's schema contract. Filed as the
  separate issue #1089 (see §6); #907 consumes its contract.

## 4. Decisions pinned (D-P series)

- **D-P1 — image base: v0.6.0.** The golden-image build pins
  `645e814` (v0.6.0); the image manifest records the commit and the
  release tag. Rebuilds pin forward, never silently.
- **D-P2 — provision-record store: plane D1.** Follows F-P3: the
  attestation-token validation runs plane-side, so the provision record
  (claim id, invite, box id, attestation-token hash, tenant binding)
  lives in D1. The #1074 spend ledger consumes provision records from
  the same store — one record, two consumers (G51.3 validation, #1074
  ingestion).
- **D-P3 — emission is the MeterQueue's worker half; reuse the
  #953/#864 transport discipline.** Reconciliation with D-M4
  (`METERING_BILLING_GAP_ANALYSIS.md`): the dedicated `MeterQueue`
  (box-local spool + worker, copied from the PushQueue pattern) remains
  the design's emission path — D-P3's worker is that worker, not a
  competing transport. The #953 upload-filings scan / #864 heartbeat
  discipline (periodic, flock-serialized, loud failure, plane-down
  degradation) is the concrete shape the §6 worker takes for the
  5-minute `resource_window` / 60-second `idle_heartbeat` cadence, with
  the design's `(source, epoch, seq)` dedupe as the at-least-once
  integrity story. "Loud failure" is pinned as **fail-open**, never
  fail-closed: per `USAGE_METERING_DESIGN.md` §6, a full spool, a dead
  worker, or a plane outage never blocks the box, never fails a swap,
  never loses an approval — gaps are detectable (`seq`
  discontinuities), breakage is not. This is also not the "two emission
  paths" question #1049 framed and the metering analysis closed as
  invalid premise (F-M7: the fleet journal is a meter-daemon *source*,
  upstream of the same MeterQueue) — no second spool system is proposed.
- **D-P4 — build order for the lane.** #905 (driver) and the F-P1 image
  producer are the integration critical path — nothing downstream can
  be exercised end-to-end without a machine that boots the stack — but
  the design/schema/policy work proceeds in parallel: #907 (attestation
  design) and #1074 (ledger schema) and #1077 ([POLICY]) do not wait for
  the driver. Order within the wired sequence: #1089 (provision-record
  schema contract) lands before #906's record-store wiring and before
  #1074's provision-record ingestion, since both consume the schema;
  #907 consumes #1089's contract for the token-validation half. Then
  #906 (orchestrator) with the D-P2 record store. Sub-orders:
  #1074 → #1075 → #1076 (spend-cap), #1047 → F-P2/#1088 → #1048
  (metering). #1077 proceeds on operator-set defaults meanwhile.

## 5. Explicitly NOT new gaps (already owned)

- Fly driver build (#905 — narrowed to the driver + exec-install path
  per F-P1; the golden-image producer moved to #1087), orchestrator
  (#906), attested-pairing design (#907, consuming #1089's contract),
  (#1047), plane metering endpoint (#1048), exec-install alternative
  (F1b, rides #905), golden-image *gate* (exists), first-boot hook
  (rides #905/G51.4), H4 live-API clearance (granted; the first smoke
  provision is #905's first slice, not a new issue).

## 6. Gaps filed

- F-P1 → new issue: golden-image build pipeline (producer for the gated
  image, pins v0.6.0).
- F-P2 → new issue: meter-envelope emission worker (spool → plane) —
  the MeterQueue's worker half per D-M4, fail-open per §6.
- F-P3 → new issue: provision-record store pin (D1, plane-readable for
  G51.3 token validation) — deliverable is an in-repo schema-contract
  amendment carrying the pinned DDL (`IF NOT EXISTS`, named migration
  file), following the #1061 contract-doc vehicle; names the
  orchestrator write credential as the trust root.
