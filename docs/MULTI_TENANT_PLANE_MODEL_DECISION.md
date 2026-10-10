# Multi-tenant plane model — decision record

**Date:** 2026-10-09 (build-loop gap turn, slot 20261009-2329).
**Pinned:** main `88bef5e`. **Issue:** #1159 (T3 of
`docs/PLANE_TENANT_IDENTITY_GAP_ANALYSIS.md`).

## Summary

**Decided: (a) one plane per tenant.** Each hosted signup gets its own
`sparkvm-control` instance (Worker + D1 database + VAPID identity), and
the shipped single-owner auth model — one-shot bootstrap, owner keys,
box Bearer <redacted>, the last-active-key guard — is kept verbatim on
every instance. No tenant layer is built on a shared plane; the
super-owner class the tenant layer would require is never created.
The tenant-layer option (b) is documented below with its exact
revisit trigger, so a future scale-out has a migration sketch instead
of a re-litigation.

This unblocks the gated slices (#1158, #1160, #1161, #798, #968):
their specs are amended in §6 to the per-tenant-plane reading.

## The question

The signup design (`docs/HOSTED_SIGNUP_ONBOARDING.md` §4) says the
control plane creates a tenant record (`tenant_id` + enrollment token)
and later binds the tenant Muse's ed25519 key to it. The shipped plane
(`docs/CONTROL_PLANE_API_REFERENCE.md`, pinned 2026-10-06) is a
single-owner appliance: `POST /v1/owner/bootstrap` is one-shot ("a
box-token holder bootstrapping *is* the owner"), the last-active-key
guard keeps at least one owner key alive, and the endpoint
table contains the word "tenant" zero times. Serving N tenants needs
either (a) one plane per tenant, or (b) a tenant layer on one plane.
Every other tenant-layer slice assumes one of these, and they are not
compatible retrofits — hence the decision before more slices ship.

## Findings

- **F-MT1 — H11 already answered the same question one layer down.**
  The multi-tenancy audit (`docs/MULTI_TENANCY_AUDIT.md` §4) decided
  **per-tenant box** for mutually-untrusted tenants (Fly Sprites is
  the decided provider): on a shared host, A1 (host-wide proxy grants)
  + A2 (one shared credential universe) make any shared substrate a
  shared secret dispenser. The plane is the same argument one layer
  up, with one qualification: A1's premise was *no unforgeable
  identity* on the proxy, while the plane authenticates every request
  with credential-derived identity — so what transfers is the
  missing-predicate bug class (whose cost is F-MT2's per-change review
  burden), not the full A1 premise. Under (b), one D1 database holds
  *every* tenant's credential material — owner key hashes, box token
  hashes, push-subscription secrets (the VAPID private key is a
  per-plane worker secret per D3, never in D1 — under (b) the shared
  worker would need per-tenant VAPID key selection, which is part of
  (b)'s cost, not the D1's; and the push lane is unbuilt today, so
  this is the forward shape) — and every query needs a tenant
  predicate.
  One missed predicate on any credential path is a cross-tenant
  credential leak: the plane-analog of A1/A2.
- **F-MT2 — Security-review economics favor (a) permanently.**
  This project's method is adversarial review of every change. Under
  (b), every future plane change becomes a cross-tenant scoping
  question — a compounding, permanent review burden, and the exact
  bug class (missing tenant predicate) that no test suite catches
  reliably. Under (a), the plane stays single-owner forever; the
  per-tenant dimension lives in *provisioning* (deployment-shaped),
  which is audited once, not per change. Deployment boundaries beat
  code boundaries for mutually-untrusted tenants — the same lesson
  the isolation research states for the compute layer: never present
  the jail as a hardware boundary.
- **F-MT3 — (b) creates a super-owner; (a) narrows the residual
  privilege to deploy-time.**
  A shared plane needs someone to provision tenants, read metering,
  and handle billing — a cross-tenant privileged class the shipped
  model deliberately avoids. That super-owner's endpoints would need
  their own scoping audit (the issue body names this). Under (a)
  the residual cross-tenant privilege is deploy-time, not
  request-time: the operator plane + provisioner hold Cloudflare
  deploy credentials with create/destroy authority over every
  tenant's Worker and D1 — named here as the residual privileged
  component, not hand-waved away. The honest claim is narrower than
  "never": (a) keeps that privilege inherent to the pre-existing
  operator role, unreachable from tenant request traffic and audited
  once, whereas (b)'s super-owner would be a new request-serving API
  class needing a per-endpoint scoping audit forever.
- **F-MT4 — Cost is not the decider at this scale.**
  A Worker + D1 per tenant is genuinely cheap at the scale this
  product will see first (tens of tenants; Workers pricing is
  per-request, and the free tier covers 100k requests/day). The
  real cost of (a) is operational: provisioning must instantiate a
  plane per signup, and updates must roll out to N planes. That
  work is *automation*, not a security redesign — but it is not
  built: the claim→provision orchestrator (#906) is open and
  unassigned, and per-tenant planes add per-signup D1 creation,
  per-plane VAPID/secrets issuance, per-plane deploys, and N-plane
  update rollout on top of box provisioning. (b)'s cost is a security
  redesign of every endpoint: strictly more expensive in the currency
  this project spends (adversarial review hours).
- **F-MT5 — Erasure (T7, #1162) is trivial under (a), a project
  under (b).** Tenant records will hold PII (email, `muse_id`,
  display name, public key). Under (a), tenant erasure = delete
  the tenant's D1 database (and Worker) — auditable in one step.
  Under (b), erasure = row-level deletes across every table with
  a verifiable-completeness story — the exact class of work #1162
  would have to design from scratch. The one-step story covers the
  tenant-plane half only. Erasure is complete only when the operator
  plane's provision, meter-envelope, and billing records for that
  tenant are also deleted; #1162's design must cover both halves.
- **F-MT6 — The 404-vs-403 enumeration discipline (T6) stays
  cheap under (a).** In a single-owner namespace the discipline
  costs nothing and protects nothing; under (b) it becomes the
  whole isolation story at the status surface, load-bearing on
  every new endpoint. (a) keeps it a contract nicety rather than
  a security boundary.
- **F-MT7 — The signup §4 spec maps onto (a) with one
  substitution.** §4's "the control plane creates a tenant
  record" becomes "the orchestrator provisions the tenant's
  plane instance"; the tenant's identity on their plane is the
  **owner**. A signup-issued enrollment token (single-use, 15-min TTL,
  shown once after magic-link auth — separate from the Muse's §4
  link-request token) becomes the bootstrap authority
  for that plane's one-shot `POST /v1/owner/bootstrap` — see
  D-MT2. The tenant-Muse key binding (§4 steps 2–3, human
  approves the fingerprint) is unchanged in shape: it records the
  Muse's ed25519 public key as a tenant-plane credential (not an
  `svm_` owner key), gated on the same recorded human approval.

## Decisions

- **D-MT1 — One plane per tenant (option (a)).** Every hosted
  signup provisions a dedicated `sparkvm-control` instance:
  its own Worker, its own D1 database, its own VAPID identity
  (D3 custody stays one identity per plane — unchanged). The
  shipped auth model is kept verbatim (except the bootstrap
  authority, D-MT2): one-shot bootstrap,
  owner keys (`svm_` + 43 urlsafe chars), 24 h box Bearer
  tokens with 15-min previous-token grace, the
  last-active-key guard, undifferentiated 401s. No endpoint
  gains a tenant dimension; no super-owner class is created.
  The both-supported default is preserved: self-hosted stays
  exactly what it is today — a single-owner appliance — and
  the hosted product is N independent appliances.
- **D-MT2 — The signup-issued enrollment token is the bootstrap
  authority (signup-provisioned planes only).** The one-shot
  `POST /v1/owner/bootstrap` keeps its shape — after bootstrap
  completes, the endpoint closes (`403 "bootstrap closed"`). The
  token is minted by the signup surface on the operator plane
  (D-MT4, amended below) and validated by the tenant plane against
  the token hash the provisioner installs in the fresh plane's D1
  at deploy time (alternative: an operator-signed token verified
  against the operator public key pinned in the plane template —
  the #906 build picks one). The bootstrap call itself is made by
  the human's browser, direct to the fresh tenant plane, inside
  the magic-link session: the minted owner key is returned only to
  that browser session and never transits a server, per the signup
  invariant (`docs/HOSTED_SIGNUP_ONBOARDING.md` §2). The §4 token
  is single-use and cannot double as the link-request bearer —
  the signup surface mints separate single-use tokens for
  bootstrap and for the Muse's §4 link request (the #1158 build
  may collapse them only if the ordering is pinned). This is
  additive, not a replacement: on self-hosted planes the
  box-token bootstrap authority is unchanged.
  First-claim race, restated honestly: whoever presents the token
  to bootstrap first mints the plane's first owner key — and unlike
  §4's link request, no second human approval covers the owner key
  (D-MT3 gates the Muse's key, not the owner key). The race is
  therefore closed by the call path, not by countersignature: only
  the magic-link session holder's browser presents the token for
  bootstrap, so the residual race is magic-link session hijack —
  the same trust the rest of signup already rests on. The pairing
  flow's CLI-only first-approval mitigation does not transfer;
  this paragraph replaces it. The Muse MUST NOT be given the
  bootstrap token (it gets only the link-request token); a
  Muse-presented bootstrap token is rejected.
- **D-MT3 — The tenant-Muse key binding keeps §4's shape.**
  The Muse generates its own ed25519 keypair, submits the
  signed link request, the human approves that fingerprint;
  the plane then binds the key as a tenant-plane credential
  (an ed25519-verifier credential class, not an `svm_` owner key)
  on the tenant's plane. Revocation (human rotates the key
  or revokes the tenant) stops issuance for the old key and
  signals the privileged box helper to kill sessions — §4's
  revocation leg, unchanged. Nothing in this decision alters
  the approval-gating: link acceptance is gated on recorded
  human approval of *that key*, never on token possession.
  Concretely: the plane records the Muse's ed25519 public key as a
  tenant-plane credential that authorizes §4's signed requests; no `svm_`
  owner key is issued to the Muse. The human's own plane access remains
  via magic-link sessions, not owner keys.
- **D-MT4 — Cross-tenant administration lives on a separate
  operator plane, never on tenant planes.** Metering/billing
  (H12), the provisioner, and fleet health aggregate on an
  operator-only service (the host-side sibling is #464,
  operator-plane retirement). Tenant planes emit meter
  envelopes to it; it holds no tenant credentials and serves
  no tenant-Muse API. This is what the super-owner would have been
  under (b) — scoped down to envelopes and provision records.
  The signup surface also lives here: magic-link auth,
  enrollment-token issuance, and the link-request approval UI.
- **D-MT5 — Revisit trigger (not a re-litigation).** Revisit
  (b) only when one of these is true: the tenant count
  approaches Cloudflare per-account limits on Workers/D1
  databases, or measured per-tenant-plane operational cost
  (provision + update rollout) exceeds the amortized cost of
  the tenant-layer security redesign. The migration sketch:
  export each tenant D1 → import into a shared D1 with a
  `tenant_id` column backfilled from the source database
  identity; add the tenant predicate to every query, with the T6
  404-vs-403 enumeration discipline enforced on the read paths;
  run the full H11-style
  scoping audit on the result before serving the second
  tenant on it. Pre-merge collision audit: all planes share one
  template, so natural keys (`owner_principal`, owner-key ids,
  `added_by`) may collide across planes — the sketch includes a
  key-namespacing/collision-audit step before any import, not just
  the `tenant_id` backfill. VAPID identity collapse: D3's per-plane
  VAPID keypair becomes one shared identity, invalidating every
  existing push subscription (bound to the per-plane
  applicationServerKey) — migration includes client
  re-subscription. The last-active-key guard is re-scoped from
  plane-wide to per-`tenant_id`. Until the trigger fires, (b) is
  not built.

## Consequences for the gated slices

- **#1158 (T1+T2 — tenant record + tenant-Muse identity):**
  "tenant record" is re-read as the tenant's plane instance +
  its owner bootstrap (D-MT1/D-MT2); the tenant-Muse identity
  work is D-MT3. Two records, two homes: the plane-side identity
  record (the tenant-status backing store on the tenant's plane)
  vs the operator-side account/provision record (D-MT4) — #1158
  builds the plane-side one; the operator-side one belongs to
  the #851 provisioning lane. The issue's acceptance criteria
  need this amendment, not a rewrite — the build is the per-plane
  bootstrap-authority change plus the key-binding endpoints,
  both single-owner shaped.
- **#1160 (T4 — approval-record attribution):** box-originated
  rows carry `owner_id` NULL today. Under (a) the attribution
  answer is deployment-shaped: the record's plane *is* the
  tenant, so `owner_id` NULL on a tenant plane means "this
  tenant's owner" unambiguously — no cross-tenant ambiguity
  exists to resolve *within* the tenant plane. On the D-MT4
  operator aggregation feed, which ingests records from N
  planes, a NULL `owner_id` is ambiguous unless the meter
  envelope stamps source-plane identity — the feed must carry
  it. The remaining work is the proxy/confirmd audit-line half
  (#14), unchanged.
- **#1161 (T5 — /tenant/status plane auth):** the contract's
  two-sided auth (magic-link cookie for the signup page,
  tenant-Muse signed requests) is unchanged; the plane side
  now authenticates against a single-owner namespace, so the
  "Muse polls with its key" half verifies against D-MT3's
  binding with no tenant selector anywhere. The 404-vs-403
  discipline stays in the contract (T6) as cheap hygiene.
- **#798 (tenant-scoped fleet stream):** the shared-plane-stream
  framing is retired, but S1 and S2 survive as operator-plane
  ingest work (D-MT4) — meter envelopes arriving from N planes
  carry the tenant field stamped at record time by the
  operator-declared mapping (never inferred from
  plane/box-controlled bytes), and per-tenant alert fan-out
  evaluates within a tenant's series on the operator plane.
  S3 (#778 G19 read-path dependency) is unchanged.
- **#968 (push subscriptions):** subscriptions stay owner-keyed
  on the tenant's plane (D3: one VAPID identity per plane —
  unchanged). No tenant dimension is added to the subscription
  schema; the #988 contract stands as written.

## What this does not decide

- The per-tenant-plane provisioning mechanics (wrangler
  template instantiation, per-signup deploy, N-plane update
  rollout) belong to the #851 provisioning lane (#905/#906) —
  this record is the requirement they build against.
- D-MT1 splits the singular "plane" that F-D5/F-D6
  (`docs/FLY_DRIVER_DESIGN_AHEAD.md`) and the signup actor table
  (`docs/HOSTED_SIGNUP_ONBOARDING.md` §2) assume. Resolved: the
  provision-record store and attestation-token minting live on the
  operator plane (it exists before the tenant plane is provisioned
  and serves the #906 orchestrator); the signup surface lives on
  the operator plane per D-MT4 (amended, B1). Tenant-SSH relay
  placement (tenant plane vs operator plane) is decided by the
  #851 lane — until then no slice may assume either.
- The operator plane's own design (D-MT4) is named, not
  specified — it is #464's sibling and a future gap turn's
  subject.
- Per-tenant box (H11) is assumed and unaffected; the box
  pairs to its tenant's plane, and the pairing flow is
  unchanged (the plane it pairs to is simply the tenant's).

## Honest limits

- This decision trades a security-redesign cost for an
  operations-automation cost. If the provisioning lane
  (#851) stalls, per-tenant planes stall with it — the
  decision is only as good as the orchestrator behind it.
- The cost analysis (F-MT4) is order-of-magnitude, not a
  quote: Cloudflare pricing at tens of tenants is noise
  against one engineer's week. The revisit trigger (D-MT5)
  is the honest bound, not a promise that (a) scales forever.
  Per-plane infra cost (Worker + D1 per tenant) is a metering
  input: H12's meter envelopes should carry it so tenant pricing
  can reflect it — the order-of-magnitude claim is not a pricing
  decision.
- Under (a), a tenant's plane is still a single point of
  failure for that tenant (one Worker, one D1) — same as
  self-hosted today. Multi-region tenant planes are out of
  scope for this decision.
