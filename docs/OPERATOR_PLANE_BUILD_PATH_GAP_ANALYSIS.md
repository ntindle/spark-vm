# Operator-plane build path — vision vs state after D-MT1

**Date:** 2026-10-10 (build-loop gap turn, slot 20261010-0559).
**Pinned to:** main `185ca95` + the plane-worker checkout at
`~/workspace/goals/sparkvm-dev-website-v2-cloudflare-management-infra`
(no plane changes in this analysis).
**Question answered:** D-MT1 named the operator plane; what does it
actually have to be, what exists today, and what must be filed before
build slices can land on it?

## 1. Why this analysis exists

`docs/MULTI_TENANT_PLANE_MODEL_DECISION.md` D-MT4 decided: cross-tenant
administration lives on a separate operator plane — metering/billing
(H12), the provisioner, fleet health — and "tenant planes emit meter
envelopes to it; it holds no tenant credentials and serves no
tenant-Muse API." The signup surface lives there too (magic-link auth,
enrollment-token issuance, the link-request approval UI). The decision's
"What this does not decide" section says it outright: "The operator
plane's own design (D-MT4) is named, not specified — it is #464's
sibling and a future gap turn's subject." This is that turn.

Meanwhile the name is already doing triple duty. Three docs, three
operator planes, no boundary:

- The G4 summons design (`docs/FIRST_APPROVAL_SUMMONS.md` §1/§5): the
  operator plane is where the AgentMail credential lives (`cred set`,
  `hsurr:agentmail`) and where the summons send happens — with the
  load-bearing trust boundary "the tenant box must never hold an
  operator-plane credential" (installing one is "the same class of
  mistake as the IMDSv1 host-wide grants H11 flagged").
- The H11 audit (`docs/MULTI_TENANCY_AUDIT.md` §3 Q4) and #464: the
  operator plane is the retirement destination for the shared
  `ntindle`-with-sudo swapd-host domain, and the H5 sentinel's host.
- D-MT4: the operator plane is the signup/metering/provisioner/fleet-health
  service.

Are these one service or three sharing a name? Nobody wrote it down.
Build slices are already being filed against the name (#798 S1/S2,
#1048, the #908 slices, #1214) — they need a pin to land on.

## 2. The vision (what the docs say the operator plane is)

**D-MT4, verbatim scope:** "Metering/billing (H12), the provisioner, and
fleet health aggregate on an operator-only service (the host-side
sibling is #464, operator-plane retirement). Tenant planes emit meter
envelopes to it; it holds no tenant credentials and serves no
tenant-Muse API. This is what the super-owner would have been under
(b) — scoped down to envelopes and provision records. The signup
surface also lives here: magic-link auth, enrollment-token issuance,
and the link-request approval UI."

**Signup surface** (`docs/HOSTED_SIGNUP_ONBOARDING.md` §2/§4,
`docs/HOSTED_SIGNUP_WEB_UI.md` §7): the human's magic-link auth, the
one-time enrollment-token display (the token's only channel), the
pending link-request approval UI (human approves the Muse key
fingerprint — the actual countersignature), the re-link path for
returning Muses. §7's enumeration-oracle discipline applies: the
surface must never confirm or deny other tenants' existence.

**Credential custody** (summons §1/§5): operator-plane credentials
(AgentMail key, and by extension any operator secret) are installed
via `cred set` and referenced as `hsurr:` placeholders — never in the
repo, the journal, or the box. The deploy-credential residual from
F-MT3 ("deploy credentials are residual cross-tenant privilege" —
credentials with create/destroy authority over every tenant's plane)
lives here too.

**Metering/billing ingest** (#798 S1, #1048, #378): meter envelopes
arrive from N tenant planes; the tenant field is stamped by the
operator-declared mapping, never inferred from plane/box-controlled
bytes (#798). #378's quarantine policy: `tenant: unknown` envelopes
are unbillable and quarantined into an audit-visible holding set,
never silently dropped, never folded into a tenant's aggregates.

**Alert fan-out** (#798 S2): correlated-failure/silent-wave alerts
evaluate within a tenant's series only, on the operator plane.

**Spend-cap enforcement** (#908, D-C1 operator-side): the spend ledger
(#1074), the pre-provision cap-check hook in the #906 orchestrator
(#1075), the destroy-on-budget-exceed worker (#1076), the cap-value
catalog (#1077) — all operator-side.

**Never-paired alert** (#1214): provisioned-but-never-paired
attestation provisioning-timeout — an operator-side watcher.

**Sentinel** (H5, via #464): the sentinel role runs on the operator
plane.

## 3. Current state (verified this turn)

- **No operator plane exists.** Zero code: the repo has no operator-plane
  service, no operator D1 schema, no operator-plane deploy target. The
  deployed `sparkvm-control` worker is a tenant-plane-shaped appliance
  (single-owner auth: owner keys, box Bearer <redacted>, AgentID
  sessions — verified in the plane-worker checkout: zero magic-link,
  tenant-Muse, or tenant-key surface).
- **The closest thing is waitlistd** (`site/waitlistd.py`): the current
  signup-adjacent operator surface — outbound transactional mail spool,
  invites, claims (`site/waitlist_invites.py` emits `claimed`). It is
  not the operator plane (no magic-link auth, no tenant records, no
  meter ingest), but it is the surface the D-MT4 signup plane grows
  out of or replaces — the design spec (#1257) must say which.
- **#464 tracks the host-side retirement** (the shared
  `ntindle`-with-sudo domain → dedicated audited operator plane). It
  does not specify the control-plane-side service.
- **Filed and waiting on the pin:** #798 (S1 tenant field, S2 alert
  fan-out), #1048 (metering ingestion), #1074–#1077 (#908 slices),
  #1214 (never-paired alert), #378 (unknown-tenant quarantine),
  #1257–#1261 (this turn's filings, §6).
- **Already decided, consumed here:** D-MT1 (one plane per tenant),
  D-MT2 (signup-issued enrollment token is the bootstrap authority;
  the minted owner key never transits a server), D-MT3 (tenant-Muse
  key = ed25519-verifier tenant-plane credential; human access via
  magic-link sessions), the read-only safety contract from
  `docs/TENANT_STATUS_ENDPOINT.md` §1 (ported to the operator plane
  in D-OP3).

## 4. Findings

- **F-OP1 — Three docs, one name, no boundary.** §1's triple-duty
  reading is the finding: the summons doc's credential-custody plane,
  the H11 audit's #464-retirement plane, and D-MT4's
  signup/metering/provisioner plane share a name and no spec. A slice
  that "lands on the operator plane" cannot be reviewed until the
  name means one thing (D-OP1).
- **F-OP2 — Tenant-plane → operator-plane auth is unpinned.** D-MT4
  says tenant planes emit meter envelopes; #798 S1 says the tenant
  field comes from an operator-declared mapping, never inferred from
  box-controlled bytes. But the mapping needs a transport identity:
  how does a tenant plane authenticate its envelopes? No credential
  class exists (the tenant plane's owner keys and box Bearer <redacted>
  are tenant-scoped — they must not become operator-plane credentials,
  or the "holds no tenant credentials" line is violated from the other
  direction). Filed as #1258.
- **F-OP3 — The signup surface's human auth has no store.**
  `docs/HOSTED_SIGNUP_ONBOARDING.md` §4 and D-MT4 put magic-link auth
  on the operator plane; #1161 covers the tenant-plane `/tenant/status`
  auth, not this. No session store, no TTL, no revocation, no
  enumeration-oracle discipline for the operator side. Filed as #1259.
- **F-OP4 — The operator-side tenant account record has no issue.**
  D-MT1 §6: "Two records, two homes" — the plane-side identity record
  (#1158) vs the operator-side account/provision record (D-MT4). #1089
  pins the provision-record store (G51.3 attestation); the human's
  account record (email, billing identity, magic-link identity,
  consent timestamps) has no issue — D-MT1 §6 folded it into the #851
  lane's account/provision record, where it is unowned. Filed as #1260
  (with the D-OP4 amendment below).
- **F-OP5 — Custody concentrates here and has no plane-wide
  posture.** The operator plane is where the secrets pool: the
  AgentMail key, the deploy credentials with create/destroy authority
  over every tenant plane (F-MT3's residual), the VAPID mailbox, the
  #908 ledger's view of spend. Each slice documents its own custody
  (`cred set` + `hsurr:`), but no doc states the plane-wide posture —
  which principals may hold which secrets, and the explicit threat
  note for the deploy-credential residual. Owned by the design spec
  (#1257), not a separate issue.
- **F-OP6 — The #908 ledger's D1 is ambiguous.** #1074 scopes "a
  Cloudflare D1 table for the ledger" — on which plane? The operator
  plane has no D1 yet; the tenant planes each have one. A spend ledger
  on a tenant plane would let the tenant read (or tamper with) the
  operator's view of their spend. The design spec (#1257) decides the
  placement; the finding is recorded here so #1074's build doesn't
  guess.
- **F-OP7 — Per-tenant-plane update rollout is unowned.**
  `docs/FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md` (2026-09-28) designs
  rollout for boxes and predates D-MT1. D-MT5's revisit trigger is
  gated on *measured* per-tenant-plane operational cost — unmeasurable
  until something rolls out tenant-plane updates. Filed as #1261.
- **F-OP8 — #464 vs D-MT4: sibling or same?** #464's operator plane is
  host-side (the swapd host's audited replacement for shared sudo);
  D-MT4's is control-plane-side (signup, metering, provisioner).
  "Sibling" is the decision's word, not a boundary. D-OP1 makes the
  one-concept call (one service concept, two deployment facets); #1257
  writes the detailed facet boundary. Until the spec lands, no slice
  may assume a facet split that contradicts the one-concept pin (the
  same discipline the MT1 decision applied to tenant-SSH relay
  placement).

## 5. Decisions

- **D-OP1 — Name the plane once.** The operator plane is one service
  concept with two deployment facets (host-side per #464,
  control-plane-side per D-MT4). The trust boundary both facets share:
  tenant-adjacent compute never holds operator-plane credentials
  (summons §1's rule, generalized). The design spec (#1257) is where
  the boundary is written; this analysis is where it is named.
- **D-OP2 — Envelopes authenticate with a provisioner-installed
  credential.** Operator-minted, per-tenant-plane, installed by the
  #906 orchestrator at provision time (alongside the D-MT2
  bootstrap-authority token hash — same install step, separate
  credential; the bootstrap token authorizes the tenant plane's birth,
  the envelope credential authorizes its voice). The tenant field is
  stamped by the operator-declared mapping (#798 S1), never inferred.
  The envelope credential is verify-only voice material — the operator
  plane verifies envelopes with it; it is not impersonation material,
  so it does not contradict D-MT4's "holds no tenant credentials"
  (no tenant credential is ever usable *as* the tenant on the operator
  plane). #906's acceptance criteria gain the envelope-credential
  install step. Full scope in #1258.
- **D-OP3 — Magic-link sessions live on the operator plane.**
  Enumeration-oracle discipline per `docs/HOSTED_SIGNUP_WEB_UI.md` §7;
  the read-only safety contract from `docs/TENANT_STATUS_ENDPOINT.md`
  §1 (a mail-scanner fetch authenticates nothing and changes nothing)
  is ported. Full scope in #1259.
- **D-OP4 — Two records, two homes (MT1 §6) — explicit amendment:
  three records, two homes.** #1158 owns the plane-side identity
  record; #1260 owns the operator-side account record; #1089 owns the
  provision record. The three must not be merged — the account record
  outlives any single provision, and the identity record must never
  leave the tenant plane. This amends D-MT1 §6's pinned record model
  (the account record splits out of the #851 lane's account/provision
  record into the operator-plane lane); the amendment is recorded here,
  not smuggled — the "decisions stand" line in the non-overlap map
  refers to D-MT1–D-MT5's model decision, which this does not reopen.
- **D-OP5 — Custody posture is plane-wide, not per-slice.** All
  operator-plane secrets via `cred set` + `hsurr:` placeholders; the
  design spec (#1257) carries the explicit F-MT3 deploy-credential
  threat note. Per-slice custody docs reference the posture, not
  re-derive it.
- **D-OP6 — The #908 ledger lives on the operator plane's D1.**
  Decided here as the default the design spec (#1257) confirms or
  overturns: operator-side caps (D-C1) are evaluated against
  operator-held state; #1074's build proceeds on this pin and notes
  the dependency.
- **D-OP7 — Tenant-plane rollout is a new slice, not the 2026-09-28
  fleet doc's scope.** #1261 owns it; the fleet doc keeps the box
  layer. #1261 also produces the update-rollout half of the D-MT5
  cost measurement (provision cost belongs to the #906/#851 lane).

## 6. Gaps filed this turn

- **#1257 — Operator-plane design spec (D-MT4).** The spec itself:
  service inventory, trust boundary, the #464 relationship (F-OP8),
  the custody posture (F-OP5), the #908 ledger placement (F-OP6),
  waitlistd's fate (grow out of or replace — §3).
- **#1258 — Tenant-plane → operator-plane envelope authentication**
  (F-OP2/D-OP2): credential class, rotation/revocation, the
  operator-declared mapping, fail-closed on identity mismatch.
- **#1259 — Magic-link session store on the operator plane**
  (F-OP3/D-OP3): schema, TTL, revocation, enumeration-oracle
  discipline, mail-scanner safety.
- **#1260 — Operator-side tenant account record** (F-OP4/D-OP4):
  schema, lifecycle vs #1089 and #1162, read paths + audit trail.
- **#1261 — Per-tenant-plane update rollout controller**
  (F-OP7/D-OP7): staged rollout, version inventory, the D-MT5 cost
  measurement.

## 7. Non-overlap map (what this doc is not)

- `docs/MULTI_TENANT_PLANE_MODEL_DECISION.md` — the D-MT1–D-MT5
  decision record (2026-10-09). This doc consumes it; the decisions
  stand.
- `docs/PLANE_TENANT_IDENTITY_GAP_ANALYSIS.md` — the T1–T7
  decomposition (2026-10-08). #1158–#1162 stay the plane-side slices;
  this doc is the operator-side complement.
- `docs/FIRST_APPROVAL_SUMMONS.md` — the G4 summons design. Its
  operator-plane credential rule is consumed (D-OP1's trust
  boundary), not re-decided.
- `docs/MULTI_TENANCY_AUDIT.md` §3 Q4 / #464 — the host-side
  retirement. F-OP8 names the boundary question; #464 keeps the
  migration.
- `docs/FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md` (2026-09-28) — box
  rollout. D-OP7 scopes the plane layer above it.
- `docs/SPEND_CAP_ENFORCEMENT_GAP_ANALYSIS.md` — the #908 vision.
  F-OP6/D-OP6 pin the ledger's home; the spend lane's findings
  stand.
- `docs/FLEET_OBSERVABILITY_CONSUMPTION_GAP_ANALYSIS.md` — #798's
  vision. S1/S2 land on the operator plane per D-MT4; F-OP2 gives
  S1 its transport identity.

## 8. Honest limits

- This analysis specifies no service shape — it is the filing and
  the pins the design spec (#1257) builds on. The D-OP pins are the
  spec's starting pins, not its conclusions. The operator plane
  remains zero code after this turn.
- D-OP6 is a default, not a proof: if the design spec finds a
  reason the ledger belongs elsewhere, it overturns D-OP6 with the
  reasoning recorded.
- The per-tenant-plane operational cost that gates D-MT5's revisit
  trigger stays unmeasured until #1261 ships; the "order-of-magnitude,
  not a quote" caveat from the MT1 decision still holds.
- Nothing here provisions, deploys, or bills anything.
