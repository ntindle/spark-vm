# Plane-side tenant identity — vision vs state

**Pinned:** main `2aa014f` (v0.7.0, 2026-10-08). The control plane itself
deploys from a separate checkout; this analysis uses the repo's pinned
view of it (`docs/CONTROL_PLANE_API_REFERENCE.md`, pinned main
`888f875`, 2026-10-06) and the signup/onboarding specs.

## Summary

The hosted vision speaks **tenant**; the shipped plane speaks
**owner**. The signup design says the control plane creates a tenant
record (`tenant_id` + enrollment token), binds the tenant Muse's
ed25519 key to it after human fingerprint approval, and that all later
tenant-scoped API calls are signed with that key
(`docs/HOSTED_SIGNUP_ONBOARDING.md` §4). The plane implements none of
that: its endpoint table has exactly two credential classes (owner
API key, box Bearer <redacted>) plus the pairing flow, zero tenant
endpoints, and a one-shot owner bootstrap that makes it a single-owner
appliance. The mapping between the two vocabularies is unspecified —
which means every tenant-layer slice (tenant status, tenant-scoped
fleet stream, tenant attribution) is currently specified against a
plane that has no tenant dimension.

## The vision (as designed)

- **Goal:** a hosted product other Muses can sign up for and use.
- **Identity linking** (`docs/HOSTED_SIGNUP_ONBOARDING.md` §4): at
  signup the control plane creates a tenant record — `tenant_id` plus
  an enrollment token (single-use, 15-minute TTL), shown once in the
  signup UI after the human's magic-link auth. The Muse generates its
  own ed25519 keypair (private key never leaves the Muse's machine)
  and submits a *link request* (`tenant_id`, enrollment token,
  `muse_id`, display name) signed by the new keypair. The human
  approves that specific key fingerprint in the signup UI; only then
  does the plane bind `tenant_id ↔ muse public key ↔ muse_id`.
  "All later tenant-scoped API calls (cert issuance, status polling,
  approval acks) are signed with this key." Revocation: the human
  rotates the Muse key or revokes the tenant; the plane stops issuing
  certs for the old key and signals a privileged VM helper to kill
  existing sessions.
- **First ten minutes** (`docs/FIRST_TEN_MINUTES_SPEC.md`): the
  minute-by-minute script a tenant Muse follows from signup; the
  tenant-status poll carries the 13 machine codes + `approvals_url`
  in the tenant record (§2, minute 4–5), and the 10-minute clock
  starts at box-live — the moment the poll says so.
- **Tenant-status poll auth** (`docs/TENANT_STATUS_ENDPOINT.md` §1):
  two-sided, no unauthenticated access. The signup page polls with the
  human's magic-link session cookie (the page never holds a
  credential); the tenant Muse polls with its linked (approved)
  ed25519 key, signing requests per the §4 link-signing scheme. A
  caller whose tenant identity cannot be established gets `401`; a
  valid credential with no servable tenant record gets `404` — never
  `403`, so the endpoint must not confirm the existence of other
  tenants (the same enumeration-oracle discipline the waitlist
  surface follows in `docs/HOSTED_SIGNUP_WEB_UI.md` §7). Identity is
  credential-derived; there is no tenant selector.
- **Host-side tenancy** (`docs/MULTI_TENANCY_AUDIT.md`, H11): the
  mutually-untrusted-tenant inventory for a shared host (A1–A12). The
  relay posture is decided — each box lives on its own tailnet, never
  a shared tenant-to-tenant network — with "tenant isolation on the
  relay path is the H11 audit's call." A1–A3 (shared swap proxy, no
  tenant dimension in the credential stack, cred-ui as localhost-only
  on a shared host) gate any second tenant on the same host; the
  operator-plane retirement is tracked separately (#464).

## The state (as shipped)

- **The plane fronts one owner's fleet.** The API reference opens:
  "`sparkvm-control`, the Worker that fronts an owner's fleet." The
  auth table lists exactly two credential classes — owner API key
  (`svm_` + 43 urlsafe chars, long-lived, rotate by mint+revoke) and
  box Bearer <redacted> (24 h, 15-min previous-token grace) — plus the
  unauthenticated pairing flow (8-char code, 15-min TTL, ed25519
  proof-of-possession for *boxes*). The 29-row endpoint table contains
  the word "tenant" zero times. The only tenant-shaped word in the
  table is `POST /v1/owner/bootstrap`: one-shot, mint the FIRST owner
  key using a box token as authority — "a box-token holder
  bootstrapping *is* the owner"; after any active owner key exists,
  `403 "bootstrap closed"`, and the last-active-key guard keeps the
  plane from ever having zero active owner keys. The plane is a
  single-owner appliance with no second namespace.
- **Box-originated provenance is ownerless.** Plane-side approval
  records filed from a box carry `owner_id` NULL
  (`docs/FILING_UPLOAD_GAP_ANALYSIS.md` S2) — honest today, since the
  plane has one owner, but unattributable under any tenant model.
- **The tenant layer exists as a library, not as plane state.**
  `hosted/tenant_status.py` (G3 S1) ships the tenant-status
  transition engine plus a `TenantStore`: a JSON-file record store
  with fcntl-locked write-if-absent + re-read and mint-once
  `approvals_url`, runnable as a daemon
  (`python3 -m hosted.tenant_status --store …`). It is a local
  daemon, not plane state — no D1 table, no plane endpoint, no
  plane-side auth wiring. The design doc still says "design; not
  implemented" (stale status line — corrected in this turn).
- **Everything else tenant-shaped is open:** per-tenant approval
  routing (#69), tenant-attributed audit lines (#14), cred tenant
  dimension (#280), swap-proxy per-tenant request auth (#339),
  tenant field on the fleet stream (#798), tenant record for the
  push-subscription lane (#968, subscriptions are owner-keyed),
  operator-plane retirement (#464).

## The gaps

- **T1 — No tenant record on the plane.** §4 says the plane creates
  `tenant_id` + enrollment token at signup. No endpoint does this;
  no D1 tenant table exists. The tenant-status contract's tenant
  record (§2 minute 4–5, `approvals_url`) has no backing store on
  the plane. → #1158
- **T2 — No tenant-Muse credential on the plane.** §4's
  tenant-signed API calls have no plane-side verifier. Pairing's
  proof-of-possession covers *boxes* (fingerprint, first token);
  there is no binding of a *Muse's* key to a tenant, and no plane
  path for an off-box tenant Muse to authenticate at all. The
  tenant-status poll's "Muse polls with its key" half (§1) is
  unauthenticated-able on the plane. → #1158
- **T3 — Single-owner bootstrap gates every tenant slice.**
  One-shot bootstrap + last-active-key guard = one-owner
  appliance. Serving a second tenant needs either (a) one plane
  per tenant (deployment-shaped isolation; the owner model stays
  single-owner) or (b) a tenant layer on one plane (tenant
  records, tenant-scoped keys, per-tenant bootstrap — and then a
  super-owner question with its own scoping audit). **Decide and
  record before more tenant-layer slices ship** — every slice
  assumes one of these, and they are not compatible retrofits. →
  #1159
- **T4 — Plane-side approval records need tenant attribution.**
  Box-originated rows are `owner_id` NULL. Under a tenant model,
  each needs tenant (or box→tenant) attribution stamped at record
  time, fail-closed. The proxy/confirmd audit-line half is #14;
  this is the plane-record half. → #1160
- **T5 — The /tenant/status plane auth is unspecified.** §1
  requires magic-link session cookies and tenant-Muse signed
  requests; the plane knows neither credential type. G3 S1's
  daemon has its own store and no auth — the plane port of this
  endpoint needs its credential model decided (which rides on
  T2 and T3). Keep the read-only contract (`Cache-Control:
  no-store`, GET never changes state) through the port. → #1161
- **T6 — The 404-vs-403 discipline is moot until T3 lands**
  (advisory, no issue). In a single-owner namespace the
  enumeration discipline costs nothing and protects nothing;
  the moment a second tenant is servable it becomes the whole
  isolation story at the status surface. Keep it in the contract
  now so it doesn't need a security review later.
- **T7 — Tenant-record retention + erasure is undesigned.**
  Tenant records will hold PII (email, `muse_id`, display name,
  public key, approvals URL). No TTL, no human export/delete,
  no revocation-vs-retention interplay. The waitlist rows have
  the same class of problem (#399). → #1162
- **T8 — Doc debt (fixed this turn).**
  `docs/TENANT_STATUS_ENDPOINT.md` still said "design; not
  implemented" while G3 S1 ships the engine + daemon; the status
  line now reflects reality.

## Relationship to the H11 host-side audit

This analysis is the plane-side counterpart, not a re-do. The H11
audit inventories mutually-untrusted tenants on one **host**
(A1–A12, gate release, open verifications); this doc inventories
mutually-untrusted tenants on one **plane** (T1–T7). The two share
a rule: never add a second tenant without the identity and
attribution layer resolved — on the host that's A1–A3 and #464;
on the plane that's T1–T3.

## Issues filed

#1158 (T1+T2 — tenant record + tenant-Muse identity), #1159 (T3 —
plane tenancy model decision), #1160 (T4 — approval-record
attribution), #1161 (T5 — /tenant/status plane auth), #1162 (T7 —
tenant-record retention/erasure).
