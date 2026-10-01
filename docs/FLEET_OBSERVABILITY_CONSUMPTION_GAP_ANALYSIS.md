# Fleet observability consumption: vision vs repo state

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below is
**current state and work to do**, not promises. Statuses are pinned to the
repo as of this commit.

## The producers exist; the consumers don't

Two fleet-side producer stacks have shipped:

- **G16 S1** — `fleet/inventory.py`: estate-dir pull collector, JSONL journal +
  rebuildable snapshot store, box-side snapshot emitter, `fleet inventory` /
  `inventory --box` / `drift` / `rebuild` CLI (PR #715, issue #779-family
  tracking S2/S3).
- **G17 S1** — `fleet/events.py`: update-event canonicalizer, deduped event
  journal, four fleet-side alert rules, `alerts.jsonl`, `fleet events`
  (incl. `watch` exiting nonzero on unacknowledged alerts, `ack`)
  (PR #794, `docs/UPDATE_EVENT_REPORTING.md` §4 S1).

Both read surfaces stop at **journals on the operator's disk plus a CLI**.
Every consumer the hosted vision names is either named-but-unfunded or
absent. This doc names the six consumption gaps (C1–C6), each with vision,
current state, decision, and build slices. Nothing here re-litigates the
G11–G20 update-channel series (PR #780 close-out) — these gaps are what sits
*downstream* of it.

Framing rule (both-supported default): every consumer below ships for the
self-hosted operator's N-box estate first where the primitive is
layer-identical; hosted-only layers are marked `[HOSTED]` and never block
the OSS path.

## C1 — Operator fleet console (no designed surface)

| Vision | Current state |
|---|---|
| An operator runs a rollout and *sees* it: wave membership, per-wave outcome census, frozen vs failed waves, acked vs firing alerts — beyond one terminal | `fleet events` / `fleet inventory` CLI reads the journals; nothing else |

The G15 rollout controller design reads its gates from §4 of the rollout design (which consumes G17 events);
the operator reads the same information through a CLI. A rollout with a
correlated-failure fleet alert (G17 rule 2) currently requires the operator
to run `fleet events watch` themselves (or page themselves — C3). The
dashboard era (H15, `docs/HOSTED_SIGNUP_WEB_UI.md`) has a **Boxes panel**,
but it is per-box and human-dashboard-scoped; the fleet view — waves,
soak evidence, toll/freeze state — is a different surface and is
undesigned.

**Decision:** the fleet console is the G16/G17 read-path elevated to a
service surface: read-only API over the estate store (journals, not live
box calls — a box-side listener is exactly what G18 rejected), plus a
minimal console. OSS-first: the same surface serves the self-hosted N-box
operator; the hosted control plane reuses it.

**Slices (tracked on issue #795):**
- S1 — read-only fleet API (`GET /fleet/boxes`, `GET /fleet/events`,
  `GET /fleet/alerts`, `GET /fleet/waves`) over the existing estate dir;
  no new producer, no box-side change. Acceptance: every `fleet` CLI
  command has an API equivalent returning byte-equivalent content.
- S2 — console: wave board (membership, outcome census, frozen/failed),
  alert board (firing/acked). Read-only.
- S3 — wave drill-down consuming G15 S2's wave assignments when they land
  (events' `rollout` envelope is null until then; the console shows
  un-waved boxes honestly).

## C2 — P7 status page (named, never designed)

| Vision | Current state |
|---|---|
| Tenants and the public see fleet status: ongoing waves, incident alerts, tenant-scoped history | Nothing |

`docs/UPDATE_EVENT_REPORTING.md` §4 S1 is explicit: *"The P7 status page's
alert feed is the formal home when it exists; **nothing in S1 pretends the
feed exists before it does**."* The P7 read-only ops archetype is framed
around the status page, but the page itself has no design doc, no issue,
and no feed. The H15 dashboard is owner-facing; the status page is
tenant/public-facing and is a separate surface.

**Decision:** `[HOSTED]` the status page is a designed tenant/public
surface fed by the alert journal and the tenant-scoped read paths
(C4), with an explicit "no fiction" contract: every row it shows is
traceable to a journaled event (no synthesized availability, no
marketing uptime). Until the feed exists, the page does not ship — the
G17 S1 honesty rule extends to the page itself.

**Slices (tracked on issue #796):**
- S1 — status-page feed spec: which journal records become feed rows,
  the dedup/idempotency rule, the ack→resolve lifecycle, what stays
  operator-only (raw notes, box ids in the OSS sense → tenant-visible
  surrogates in hosted).
- S2 — page: wave/incident feed + tenant-scoped history (consumes C4's
  tenant read path; until then, operator-only rows).
- S3 — the incident-comms question (#368): what notifies users when the
  status page is the paid surface — the page is the feed, not the
  pager; who pages the operator is C3.

## C3 — Alert fan-out into the H14 push plane

| Vision | Current state |
|---|---|
| A firing fleet alert reaches the operator's phone | Alerts die at `alerts.jsonl` + `fleet events watch`'s exit code |

The G17 S1 alert transport is "a cron or the operator's existing paging
consumes it" — i.e., the operator brings their own paging. The H14 push
plane (`docs/PUSH_NOTIFICATIONS.md`) exists for confirmd approvals:
`PushQueue`, daemon-thread enqueue, VAPID web push, subscribe endpoints —
but its only producer is `swap_addon._file_approval`. There is **no
designed path** from a fleet alert to a push enqueue.

**Decision:** alerts become push-eligible through a designed intake, not
by bolting fleet code onto confirmd's queue. The alert's consumer set is
the operator, not the tenant — so this is operator push, which the H14
design does not currently model (its subscriptions are human/tenant
approval flows). `[HOSTED]`-leaning but OSS-usable: the self-hosted
operator is the same consumer class.

**Slices (tracked on issue #797):**
- S1 — alert→push intake spec: which rules page (rule 1 rollback-failed:
  yes; rule 3 silent-wave: after max-wait, not on every tick), dedup
  (alert_id already UUIDv5-stable), ack semantics (ack in the journal
  suppresses the page), operator subscription surface.
- S2 — enqueue path from the alert journal; the `watch` exit-code path
  stays as the cron fallback, not the primary.
- S3 — tenant-visible incidents (C2's feed) get a tenant push variant —
  gated on C4's tenant read path, never before.

## C4 — Tenant-scoped fleet consumption (no tenant field on the stream)

| Vision | Current state |
|---|---|
| A tenant sees *their* boxes' update history and state; one tenant's alert never fires another tenant's view | G19 tenant read path **designed** (`docs/UPDATE_AUDIT_RETENTION_AND_ACCESS.md` — `GET /tenant/update-history`, tenant-visible seq stream, privacy boundary: *a tenant's history never names another tenant*); **unimplemented** (issue #778). The event and inventory journals carry **no tenant field** — `docs/USAGE_METERING_DESIGN.md` is explicit: "[HOSTED] until H10 lands: the S1/S2/S4 surfaces carry no tenant field today." |

G17 §4 S3 already slices the future: *"H11 per-tenant waves consume
per-tenant event series; one tenant's correlated-failure alert never fires
another tenant's."* That slicing **presupposes a tenant field on events
that does not exist yet**. G19's design made the same presumption for
audit records. The tenant field is the missing join key for all three.

**Decision:** `[HOSTED]` the tenant field lands on the fleet streams
(events + inventory + alerts) as part of H10/H11's tenant dimension —
not as a separate fleet-side invention — and the G19 read path consumes
it. Until then, tenant-scoped consumption stays designed-not-built, and
no tenant-facing surface ships on unattributed data.

**Slices (tracked on issue #798):**
- S1 — tenant field on fleet event + inventory records: provenance rule
  (operator-declared mapping, G16's interim box_id rule extended),
  tenant-inaccessible to other tenants at read time, never inferred from
  box-controlled bytes.
- S2 — per-tenant alert fan-out: correlated-failure and silent-wave
  rules evaluate within a tenant's series only.
- S3 — G19 `GET /tenant/update-history` implementation consumes the
  field (issue #778 stays the build home; this issue is the
  fleet-side dependency).

## C5 — Sentinel feed (the signed audit log has no ship path)

| Vision | Current state |
|---|---|
| The human watches a signed audit log shipped to the sentinel (`docs/HOSTED_GAP_ANALYSIS.md` vision) | confirmd writes an audit log (`docs/SENTINEL_TELEMETRY_SURFACES.md` inventories the four telemetry surfaces as H5 input — surface inventory exists, ingestion/verification contract does not); fleet journals are unsigned; G17 `attested: false` at S1/S2; the G13 attested box→plane channel is S3 design work; **no sentinel feed spec exists** |

The vision's last clause — "the human watches a **signed** audit log
**shipped to the sentinel**" — decomposes into three unbuilt pieces:
(a) the signing story (G13's provisioned trust root, attested-admission
rule; G17 §4 S3 names the open key-custody question under the
tenant-with-shell model), (b) the transport (the S3 control-plane
endpoint is the same unbuilt channel the rollout gates wait on), and
(c) the sentinel-side consumption contract (what the sentinel ingests,
how it verifies, what a verification failure means for the human's
view). Piece (c) has no design home at all — there is no issue filed
for it (verified 2026-10-01: no open issue covers a sentinel feed spec).

**Decision:** `[HOSTED]` the sentinel feed is spec'd as a consumer
contract *before* the attested channel ships, so the channel has a
defined reader. The spec states what is verifiable at each slice and
never claims attested coverage before the keys exist.

**Slices (tracked on issue #799):**
- S1 — sentinel feed spec: the ingested record set (confirmd audit +
  fleet events + gate decisions), the verification contract
  (signature presence, not just parseability), the
  verification-failure behavior (fail-visible, never silent).
- S2 — unattested interim feed: what the sentinel shows while
  `attested: false` — labeled as operator-attested-only, never as
  box-attested.
- S3 — attested feed on the G13 channel; the key-custody open question
  (G17 §4 S3 OQ5) is this slice's entry ticket, not a deferrable.

## C6 — The fleet event stream as a metering source

| Vision | Current state |
|---|---|
| Usage metering consumes the fleet's event streams where they are the ground truth | `docs/USAGE_METERING_DESIGN.md` maps S1 confirmd audit.log, S2 swap.log, S3 muse-job JSONL — the fleet stream is unmapped |

The metering design's sources are per-box local logs; the fleet's
canonicalized event journal is the one place where update outcomes are
already normalized, deduped, and alert-evaluated. Two overlaps are
currently unowned: (a) **update-window / maintenance minutes** — a box in
`maintenance` (G12) is not serving the tenant; whether maintenance
minutes meter is a pricing input with no source-of-truth; (b) the
metering prerequisites themselves — bounded spool rotation (#376,
"required before any meter daemon ships"), the mapper's
tenant=unknown quarantine (#378), and idle-heartbeat semantics (#377)
are all open, and the fleet stream is exactly where unknown-tenant
events would first be visible.

**Decision:** the fleet event journal becomes metering's S4 source —
`maintenance-window` events feed the suspend/update-minute accounting —
**after** the prerequisites land (#376 rotation bound, #378 quarantine
policy, #377 idle semantics). Until then the mapping stays a design
note, not a consumer.

**Slices (tracked on issue #800):**
- S1 — source mapping: which fleet event kinds feed which meter
  dimensions; the maintenance-minute question answered as design
  (billable / not / operator-declared).
- S2 — unknown-tenant quarantine consumption: the fleet stream as the
  detection surface for #378's policy.
- S3 — meter-daemon read contract against the journal (bounded reads,
  retention-aligned — the S2 retention policy from G17 §4 S2 is the
  ceiling).

## Composition with the sibling designs

- **G15/G17/G18:** the consumers read what these designs produce; no
  consumer here changes a producer contract. C1's API is byte-equivalent
  to the CLI; C3's intake reads `alerts.jsonl`, never the alert
  evaluation path.
- **G13/G19:** C4 is the fleet-side dependency of the G19 read path;
  C5's attested slice rides G13's channel. Neither invents a second
  trust story.
- **H14 push:** C3 extends the push plane to a new producer class
  (operator paging) — the intake is the design, not a confirmd patch.
- **H15 dashboard:** C1's console is the fleet-era surface; the H15
  Boxes panel stays per-box. The two compose, not compete.
- **H12 metering:** C6 is metering's fourth source, gated on the
  existing prerequisites (#376–#378).
- **P7 ops:** C2's status page is the page the read-only ops archetype
  is framed around — the archetype monitors; this doc designs what it
  monitors.

## Open questions

- OQ1 — Does the operator console (C1) belong in the repo's OSS
  surface, or does a read-only API plus third-party consoles serve
  self-hosted estates better? (Both-supported says API first; the
  console is S2, revisitable.)
- OQ2 — Status-page "no fiction" contract: is tenant-visible incident
  history a launch requirement, or does operator-only alerting (C3)
  carry the hosted launch and the page follows? (P3's marketing gate
  constrains launch *copy*, not this — but the page is user-visible,
  so its honesty contract is launch-relevant.)
- OQ3 — C5's sentinel feed: is the sentinel a distinct service with
  its own ingestion API, or a view over the control-plane journal?
  (The vision says "shipped to the sentinel" — shipment implies a
  boundary; the spec must name it.)
- OQ4 — C4's tenant field: operator-declared mapping (G16 interim)
  vs provisioner-authoritative (G13). The interim rule exists; the
  question is when the fleet stops trusting the interim.

## Gap inventory

| ID | Gap | State | Track |
|---|---|---|---|
| C1 | Operator fleet console (read API + console) — #795 | Undesigned | open-source |
| C2 | P7 status page (alert feed formal home) — #796 | Named, undesigned | hosted-product |
| C3 | Alert fan-out into H14 push plane — #797 | Undesigned | hosted-product |
| C4 | Tenant-scoped fleet consumption (tenant field + per-tenant alerts) — #798 | Partial design (G19), unimplemented | hosted-product |
| C5 | Sentinel feed spec + attested channel consumption — #799 | Unspec'd | hosted-product |
| C6 | Fleet event stream as metering source (S4) — #800 | Unmapped | hosted-product |
