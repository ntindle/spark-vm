# Vend-lane D-MT1 consequence sweep (#850)

**Status: analysis, not a commitment.** Code-state claims verified
against the repo tree at main `16910545` (2026-10-12 ~03:1x CDT).
Issue/PR numbers are GitHub references as of 2026-10-12 (not
code-verifiable from the tree). Honesty rules apply
(`docs/POSITIONING.md`): this describes current state and work to do,
not promises. Nothing here vends a credential.

This document sweeps the #850 credential-vending lane's open items
against the decided multi-tenant plane model
(`docs/MULTI_TENANT_PLANE_MODEL_DECISION.md`, D-MT1: one plane per
tenant, landed 2026-10-09 as `a96e9e6`). The lane's last vision-vs-state
(`docs/CREDENTIAL_VEND_S3S4_DESIGN_AHEAD.md`, merged 2026-10-08 as
`422fa18`) predates D-MT1 — it contains zero mentions of the decided
D-MT1 model (its one tenancy mention is the T3 question as unmade) — and one of its two filed issues (#1178) carries the
"T3 UNDECIDED" premise D-MT1 has since settled. This sweep re-derives
what D-MT1 changes, what it answers outright, and what still needs a
build decision. It changes no code and amends no contract; amendments
are filed as follow-ups.

**Non-overlap map (what this doc is not):**
- `docs/CREDENTIAL_VEND_CONTRACT.md` — the S1+S2 contract (2026-10-03,
  PR #930). Amended by reference here (§4); the amendment itself is a
  filed follow-up, not landed in this turn.
- `docs/CREDENTIAL_VEND_S3S4_DESIGN_AHEAD.md` — the S3/S4 build-input
  design-ahead (2026-10-08, PR #1180). Its build notes (§5) and F-V3/D-V3
  (`credential_kill`, now #1179, closed) stand; only its D-MT1-blind
  spots are re-derived here.
- `docs/CREDENTIAL_VENDING_GAP_ANALYSIS.md` — the original G50-series
  decomposition (2026-10-02). G50.1–G50.9 stand except where §4 says
  otherwise.
- `docs/MULTI_TENANT_PLANE_MODEL_DECISION.md` — the D-MT1 record
  (2026-10-09). Its "Consequences for the gated slices" section covers
  #1158/#1160/#1161/#798/#968; the vend lane was not among them, which
  is why this sweep exists.
- The sibling lane: slot 20261012-0229's in-flight #1219/#1220
  golden-image pairing-wiring build and its filed #1363
  (ingest/upload-filings store access) — noted at F-VD7, not re-derived.

## 1. The vision (#850, verbatim acceptance)

- No real secret material on the box filesystem or in agent-visible config.
- Swaps only for allowlisted hosts; everything else refused.
- Full audit log of swaps.

## 2. What moved since the S3/S4 design-ahead (`422fa18`)

- **D-MT1 decided** (`a96e9e6`, 2026-10-09): one plane per tenant —
  each hosted signup gets a dedicated `sparkvm-control` instance with
  its own Worker, its own D1 database, its own VAPID identity. No
  endpoint gains a tenant dimension; no super-owner class.
  Cross-tenant administration lives on a separate operator plane
  (D-MT4): metering/billing, the provisioner, fleet health — envelopes
  only, no tenant credentials.
- **#1179 closed**: `credential_kill` durable-command kind (F-V3/D-V3)
  shipped — the fast-revocation path the S2 contract §4 named is now
  owned and built.
- **#1363 filed** (p2, by the live #1219/#1220 sibling): the
  ingest/upload-filings store-access design on the golden image
  (group surgery vs credential bridge vs narrow sudo) — adjacent to
  F-VD7, owned there.
- **Unchanged:** #890 (plane vend endpoint) and #891 (box swapd fetch
  path) open with 2026-10-02 bodies; #948 (dual-mode seam) open; the
  credential-vend data key still operator-owned (NEEDS_USER.md, standing
  since 2026-10-05); #1178 open with the stale T3 premise.

## 3. Findings (F-VD series)

- **F-VD1 — #1178's premise is stale: T3 is decided.** #1178's body
  says "Since then #1159 (T3) asked the multi-tenant plane model — one
  plane per tenant vs tenant layer — and it is UNDECIDED." D-MT1 decided
  it 2026-10-09: one plane per tenant. The issue's first scope bullet
  ("Decide tenant attribution on the vend tables before #890 ships its
  D1 migration — stamp at record time, fail-closed ... or carry
  reserved-NULL with a named migration") is therefore answered, not
  open: the vend tables (`vend_manifest`, `vend_values`, `vend_audit`)
  live in the tenant's own D1; `box_id` keying is unambiguous within
  the plane — the exact #1160 pattern ("the record's plane *is* the
  tenant, so `owner_id` NULL on a tenant plane means 'this tenant's
  owner' unambiguously"). No tenant column is added to the vend
  tables; the S2 contract §2.5 `tenant_id`-reserved-NULL posture is
  retired, not migrated. The issue's second scope bullet is re-scoped
  by F-VD6: the erasure half is already decided (D-MT1 F-MT5), the
  retention pin survives — and its "#890 must not ship its
  migration before this closes" gate stands on the retention pin.
- **F-VD2 — S2 contract §1 "tenant = box_id, 1:1" is stale.**
  `docs/CREDENTIAL_VEND_CONTRACT.md` §1 decides "The vend contract's
  tenant dimension is `box_id`, 1:1 with the tenant in the hosted
  shape." Under D-MT1 the tenant is the plane — #1261 rolls the
  tenant-plane worker template across N tenant planes, i.e. the plane
  (not the box) is the per-tenant deploy unit — and a tenant's plane
  can serve multiple boxes (`docs/TENANT_STATUS_ENDPOINT.md` §7: "a
  tenant with two boxes has two onboarding arcs"; G-T2: "An owner
  with N boxes"). The relation is 1:N, not 1:1 — and the error is in
  the safe direction: the per-box manifest boundary is *finer* than
  the tenant boundary, so isolation strengthens. Two strengthenings:
  "Two tenants never share a manifest," which §1 calls "an operator
  provisioning invariant, not a schema guarantee," is now enforced by
  D1 separation (different databases, not just provisioning
  discipline); and the S1-rejected options A/B stay rejected —
  per-tenant box was decided before D-MT1 and D-MT1 does not reopen it.
- **F-VD3 — S2 contract §3 "one data key protects all tenants" is
  stale, in the good direction.** §3 states: "one data key protects
  all tenants' values, so one key compromise exposes every vended
  value." Under D-MT1 each tenant plane is its own Worker with its
  own secrets: one data key per tenant plane, each protecting only
  that tenant's `vend_values.ciphertext`. The blast radius shrinks
  from "every tenant" to "one tenant" by construction. Consequence
  for the standing NEEDS_USER entry: the "Credential-vend /
  push-subscription data key (Worker secret)" item must be amended —
  it is no longer one operator-provisioned global key but a
  per-tenant-plane secret provisioned at plane deploy time
  (orchestrator-owned, #906/#905 territory). The key-rotation bound
  (§3: old key destroyed ≤ 24 h, dual-key read during the window)
  applies per plane, unchanged in shape.
- **F-VD4 — #890/#891 bodies point at neither the S2 contract nor
  the S3/S4 design-ahead.** Both issues' bodies are verbatim from the
  2026-10-02 #850 gap analysis ("From the #850 gap analysis
  (docs/CREDENTIAL_VENDING_GAP_ANALYSIS.md, G50.1/G50.2, slice
  S3/S4)"). The S2 contract (PR #930, 2026-10-03) and the S3/S4
  design-ahead (PR #1180, 2026-10-08) — the issues' actual build
  inputs — are referenced nowhere in either body. A builder opening
  #890 today starts from the pre-contract text. This is issue
  maintenance for a repo turn (pointer refresh), not a new gap: no
  new issue filed here.
- **F-VD5 — D-MT4 operator aggregation: vend_audit does not flow to
  the operator plane in v1 (recorded non-goal).** D-MT4 scopes the
  operator plane to "envelopes and provision records" — metering/
  billing, the provisioner, fleet health. No established consumer
  needs cross-tenant vend-audit aggregation (the audit's consumers —
  the owner, incident response — are tenant-scoped). If that ever
  changes, the envelope stamps source-plane identity at record time,
  never inferred from plane/box-controlled bytes — the #798/#1160
  pattern. Recorded here so no future turn re-derives it as an open
  question.
- **F-VD6 — #1178's retention half survives D-MT1 and still gates
  #890; the erasure half is already decided.** The S2 contract §2.5
  makes `vend_audit` a tamper-proof server-side record that is
  forever-by-default; #1058 set the 90-day retention+GC precedent on
  the push tables. Under D-MT1 the growth is per-tenant (the tenant's
  own D1 quota), but the retention pin is still owed: "forever" is
  unbounded D1 growth, and the migration/GC shape is unknown until
  the window is pinned. On erasure: D-MT1's F-MT5 already decided the
  tenant-plane half — "tenant erasure = delete the tenant's D1
  database (and Worker) — auditable in one step" — so the posited
  "audit-vs-erasure collision" does not exist on the tenant plane;
  the audit trail is destroyed with the plane. What remains for
  #1162 is the operator-plane half (provision, meter-envelope, and
  billing records) plus identity-record design — neither of which
  can constrain #890's tenant-plane D1 migration. #1178 stays open
  on the retention pin only; its "#890 must not ship its migration
  before this closes" gate is scoped to the retention pin.
- **F-VD7 — #948 ∩ #1363 intersection (recorded, not re-derived).**
  #948 (dual-mode seam: vend-mode boxes must not mint local grants)
  is owned by the ingest lane. The live sibling's #1363 decides which
  uid owns the ingest/upload-filings stores on the golden image —
  which determines *where* the #948 seam check executes and which
  stores it guards. The #948 build must consume #1363's outcome;
  both issues are tracked, no new issue filed here.
- **F-VD8 — the S2 contract's §4/S5 bootstrap leg has no actor under
  D-MT1 (open question, routed not decided).** The contract's §4
  Bootstrap says "at provisioning, the owner-side tooling writes the
  box's secret manifest (`PUT` manifest, §2.1a)" — the plane-side half
  of the first mint, and H19's credential half (§8). Under D-MT1 that
  sentence is unexecutable as written: the #906 orchestrator **holds
  no tenant credentials** (D-MT4: "it holds no tenant credentials and
  serves no tenant-Muse API"), and the D-MT2 owner key "never transits
  a server" — it is minted to the human's browser session inside the
  magic-link session. So who performs the first manifest write on a
  signup-provisioned tenant plane? Candidates: (a) the human, via the
  bootstrap/magic-link session — D-MT2's call path already puts a
  browser in front of the fresh plane, so the manifest PUT could ride
  the same session before any owner key exists; (b) the D-MT3
  tenant-Muse ed25519 credential — but the contract's §2.1 auth
  classes admit only box-bearer and owner-key principals, so the Muse
  credential's standing at the vend endpoints is unaddressed. The
  orchestrator is excluded by D-MT4. Filed as a new issue (§6); the
  §5 completeness claim below is softened accordingly.
- **F-VD9 — D-MT5 collision-audit note (one line).** D-VD1 retires the
  tenant column "while D-MT1 stands"; if D-MT5's revisit trigger ever
  fires, its pre-merge collision audit (which names `owner_principal`,
  owner-key ids, `added_by`) must be extended to the vend tables'
  `PRIMARY KEY (box_id, name)` — box_ids minted from one plane
  template could collide across N planes on import.

## 4. Decisions (D-VD series)

- **D-VD1 — #1178 re-scoped: attribution half CLOSED, erasure half
  DECIDED (D-MT1 F-MT5), retention pin OPEN.** Tenant attribution on
  the vend tables is decided: no tenant column (F-VD1, the #1160
  pattern). Tenant-plane erasure is decided: plane-instance
  destruction (F-MT5), so no audit-vs-erasure collision exists on
  the tenant plane. A pointer comment on #1178 records this; the
  issue stays open for the retention pin only (F-VD6), and its "#890
  must not ship its migration before this closes" gate is scoped to
  the retention pin.
- **D-VD2 — S1 amended: tenant = plane; box_id is a finer-than-tenant
  boundary.** The per-box manifest boundary is kept (it is the safe
  direction under 1:N), but the contract's "1:1 with the tenant"
  claim is retired. Filed as the S2-contract amendment follow-up
  (new issue, §6) — the amendment itself is not landed in this
  analysis turn. **[2026-10-12 convergence note: LANDED 2026-10-12
  ~06:29 CDT as #1364 (PR #1371, main `f9aca52`) — see
  docs/VEND_LANE_CONVERGENCE_2026-10-12.md §3.]**
- **D-VD3 — Custody amended: one data key per tenant plane.**
  G50.9's "one key protects all tenants" becomes one key per plane;
  the NEEDS_USER data-key entry is amended to per-plane provisioning
  at plane deploy time (this turn, §6). Rotation bound unchanged in
  shape, per-plane in scope. N-plane rotation coordination (dual-key
  windows across the fleet) is an explicit #906 orchestrator
  requirement — recorded here so it doesn't evaporate.
- **D-VD4 — No vend_audit flow to the operator plane in v1**
  (F-VD5). If a consumer ever appears, the envelope-stamping rule
  applies; until then it is a recorded non-goal.
- **D-VD5 — #890's migration gate stands, scoped to the retention
  pin** (F-VD6). Unchanged from the S3/S4 design-ahead's filing in
  force; narrowed in scope per the F-MT5 erasure decision.
- **D-VD6 — the bootstrap-leg actor question is routed, not decided
  (F-VD8).** Filed as a new issue (§6): the decision names who
  performs the first manifest write on a signup-provisioned tenant
  plane (human-via-bootstrap-session vs D-MT3 Muse credential); the
  #890 build then admits that principal (§2.1 auth classes may need
  a third class), and the #1158 tenant-Muse binding build owns the
  credential half if the Muse is named.

## 5. What this does not change

- The S3/S4 build inputs stand: the S2 contract's endpoints, auth
  classes, TTL bounds, outage rule, dual-mode seam, and the S3/S4
  design-ahead's build notes (§5) are unaffected by D-MT1 except via
  D-VD1–D-VD6 above — D-VD6 explicitly excepts the §4 bootstrap leg,
  whose actor is an open routed question (F-VD8), not a settled
  input.
- #1179 (credential_kill) is closed; #948, #890, #891 stay open with
  their current scopes.
- #339 (per-tenant request auth, cooperative same-box shape) and #134
  (H19 routing) are untouched by this sweep.
- The honest limits (§9 of the contract: no operator blindness, no
  defense against root on the box) are unchanged — D-MT1 shrinks the
  data-key blast radius but does not blind the operator.

## 6. Follow-ups from this turn

- **New issue** (p3, docs): S2-contract D-MT1 amendment — retire the
  §1 "tenant = box_id, 1:1" claim and the §3 "one data key protects
  all tenants" claim per D-VD2/D-VD3. Filed as **#1364** by this turn
  (P42 fill). **[2026-10-12 convergence note: #1364 LANDED 2026-10-12
  ~06:29 CDT (PR #1371, main `f9aca52`); issue closed via Closes
  keyword — see docs/VEND_LANE_CONVERGENCE_2026-10-12.md §3.]**
- **New issue** (p2): first-manifest-write actor on signup-provisioned
  tenant planes (F-VD8/D-VD6) — the S2 contract §4 bootstrap leg has
  no actor under D-MT1. Filed as **#1365** by this turn (P42 fill).
- **Pointer comment on #1178**: D-VD1 re-scope (attribution half
  decided, erasure half decided per D-MT1 F-MT5, retention pin remains,
  migration gate scoped to the retention pin).
- **NEEDS_USER.md**: data-key entry amended to per-tenant-plane
  provisioning (D-VD3) — goal-workspace edit, this turn.
- **Repo-turn maintenance note** (not filed): #890/#891 bodies need
  pointer refreshes to the S2 contract + S3/S4 design-ahead (F-VD4).
