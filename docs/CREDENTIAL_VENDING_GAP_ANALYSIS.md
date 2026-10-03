# Credential-vending gap analysis: localhost proxy, secrets stay off-box (#850)

**Vision vs current state.** Statuses pinned to this repo at merge `165b67e`
(PR #889), and to the `sparkvm-control` Cloudflare Worker — the plane lives
outside this repo, so plane-side facts below are pinned to the loop's
2026-10-02 reads of it (see RUNLOG), not to a repo commit. Doc-first;
honesty rules apply (`docs/POSITIONING.md`): everything below is **current
state and work to do**, not promises.

## 1. The vision (#850)

> Secrets never reach the agent or the box disk. Agent writes `hsurr:`
> placeholders; a localhost credential proxy swaps them for real values at
> the last moment, on allowlisted hosts only, with every swap audited.
> Control plane vends narrow, short-lived credentials.

Acceptance (from the issue): no real secret material on the box filesystem
or in agent-visible config; swaps only for allowlisted hosts; full audit log
of swaps.

## 2. Current state

| Vision element | Current state |
|---|---|
| `hsurr:` placeholders + localhost swap proxy | **EXISTS, self-hosted shape, hardened.** `proxy/swap_addon.py` (mitmdump, as `swapd`, 127.0.0.1:18080) swaps `hsurr:<name>` in headers/query/path/text bodies for hosts listed in `hosts.allow` **and** bound to the credential in the registry (`cred register --host`); unbound credentials fail closed. Placement restrictions (`bearer_header`, `custom_header`, `query_param`, `url_path_segment`), every swap audited to `swap.log`, systemd sandboxing, privileged-read discipline (`proxy/privileged_read.py`). |
| Secrets on the box disk | **Long-lived, operator-filled — the exact thing the vision forbids for hosted.** `SECRETS_DIR` (`/home/swapd/secrets`) holds real secret bytes, filled by `cred set` / localhost-only cred-ui. **No expiry/TTL anywhere in the store** (verified: no TTL on the secrets dir or registry); rotation is human-driven. |
| Control plane vends narrow, short-lived credentials | **Nothing.** The plane exposes pairing/register, `/v1/boxes/token/rotate`, `/v1/boxes/{id}/revoke`, `/v1/boxes/{id}/heartbeat`, owner-key bootstrap/revoke, health — no credential-vend endpoint, no vend contract, no D1 schema for per-box secret manifests. |
| Box identity for the vend call | **Exists as a foundation.** Box Bearer <redacted> (#844) + 24h rotation with 15-min grace (#846, plane half live). The vend endpoint's auth primitive is sitting there; the endpoint is not. |
| Tenant dimension in the cred stack | **Absent (#280).** Flat `/home/swapd/secrets/<name>`, flat `/home/swapd/credentials.json`, zero `tenant` mentions in `cred`, `cred-ui`, `credlib`, `cred-registry-set`, `cred-store-set`. A tenant Muse with any cred path reads every credential. #339 (swap-proxy per-tenant request auth) is the proxy-side twin, also open. |
| Plane-side management of credentials | **Absent.** cred-ui is localhost-only with zero user auth (#281; #86 for the management API) — coherent on a single-owner box, a liability the moment credentials are managed through the plane. The plane's owner keys (#843) are the management identity this needs. |
| Agent-side fetch path | **Absent.** Agents can only *spend* placeholders through the proxy; there is no fetch-on-use path and no box-side refresh loop. |
| H11's privilege-domain answer | **Settled (docs/MULTI_TENANCY_AUDIT.md, §2 finding 2 — the Proxy finding, as reconciled):** broker-outside-the-guest **ADOPTED**; endgame stated verbatim as **"workload identity with short-lived tokens"**. H19's (#134) provision-time install packet was explicitly gated on this answer — "if the audit keeps secrets out-of-guest, the install packet becomes an operator-side/control-plane mechanism, not tenant sudoers." The gate is now open in principle: the install packet's credential half converts to a plane-side bootstrap, which is #850's lane. |

## 3. Gaps

- **`[BLOCKER]` G50.1 — plane has no credential-vend endpoint.** No
  `/v1/boxes/{id}/credentials` (or equivalent), no D1 schema for
  per-box/tenant secret manifests (which secret names, TTLs, per-secret
  allowlists), no mint path, no revocation propagation to the box. This is
  plane-workspace work; the contract gets pinned here like #846's.
- **`[BLOCKER]` G50.2 — swapd has no plane-fetch path.** `swap_addon.py`
  reads only the secrets dir. A hosted box needs: a vend-aware fetcher
  (box-bearer auth per #844, RAM cache option, TTL refresh before expiry).
  **Outage rule, reconciled with the control-plane-outage principle
  (`MULTI_TENANCY_AUDIT.md` — design for stale authorization, never assume
  an outage degrades into bypassed identity):** fail closed on initial
  fetch and after lease expiry (no lease → no swap); within a live lease,
  TTL-bounded stale authorization is allowed — refusing to swap while a
  lease is still valid would turn every plane blip into a full credential
  outage. The reconciled rule, not the first draft's "never a
  post-revocation stale value," is what S4 implements.
  **Dual-mode seam (the self-hosted path keeps working):** source selection
  is a config-time decision, not a runtime assumption. Plane configured →
  vend path (outage rule above). Plane not configured → secrets dir as
  today — "plane unreachable" is the self-hosted box's permanent state,
  and Q4 keeps human-filled secrets on the box disk by design. S4 must
  name both modes; the vend path never becomes the only path.
- **`[BLOCKER]` G50.3 — no tenant dimension (#280).** Vended credentials
  through today's flat store multiplex every tenant into one secret
  universe. The vend design is unbuildable without the tenant-scoping
  decision (per-tenant dirs vs registry tenant field vs per-tenant swapd);
  land that decision with the vend contract, not after it.
- **`[DESIGN]` G50.4 — swap request identity (#339 twin).** The audit's A1
  finding stands: the proxy trusts any local process; grants are host-wide.
  The vend story needs per-tenant request identity as much as #339 does —
  decide the two together or the proxy keeps dispensing to the wrong
  principal.
- **`[DESIGN]` G50.5 — short-lived semantics.** TTL shape (minutes-to-hours,
  STS-style); refresh-before-expiry vs fetch-on-use (the research notes'
  two poles: Vault Agent cache vs no-cached-credential fetch-on-use); hard
  delete-on-expiry so nothing stale survives revocation; the outage rule is
  G50.2's reconciled one (fail closed with no lease, TTL-bounded stale
  authorization within a live lease). This is the slice that turns
  "short-lived" from an adjective into a mechanism.
- **`[DESIGN]` G50.6 — plane-side vend audit.** `swap.log` keeps auditing
  box-side swaps, but the audit a tenant can't tamper with is the
  server-side one: every vend, refresh, and revocation logged on the plane
  (the q5 research's anomaly-detection point). The audit row must carry the
  tenant/box identity #339/#280 introduce.
- **`[DESIGN]` G50.7 — H19's three elements route three ways.** #134 is not
  a single credential-delivery shape, so "folds into vending" whole is
  wrong. Its three elements: (a) scoped sudoers for the tenant agent user —
  a privilege-domain question now governed by Q4's runtime-cell answer
  (tenant gets contained root-equivalent inside the cell; the operator
  never co-resides with a passwordless-sudo domain) — reconcile against Q4
  (likely closed as superseded), not folded into vending; (b) smoke-test
  credential install — routes to the vend bootstrap (S5); (c) echo endpoint
  allowlist entry — a smoke-bootstrap decision with (b). "Do not build two
  credential-delivery shapes" stands; the routing is per-element, not
  wholesale.
- **`[HONESTY]` G50.8 — root-compromised box.** State the limit plainly
  (q5 research): nothing fully protects against root on the box. The
  defense is blast-radius control: short TTLs, narrow per-box scoping,
  audience-bound tokens where the upstream supports them, injection at the
  proxy so workload process memory holds placeholders. No marketing
  claim of operator blindness — the trust story is already explicit in
  the H11 audit.
- **`[DESIGN]` G50.9 — plane-side secret-value custody.** The vision moves
  secret material off the box and onto the plane, but G50.1's D1 manifest
  lists names, TTLs, and allowlists — conspicuously not *values*. Unasked
  in this inventory so far: where do vended secret values live at rest on
  the plane — plaintext in D1 vs an encrypted store, which plane
  identities can read them, and what a D1-reading attacker gets. Without
  this answer the hosted design may be a trust relocation, not a trust
  improvement. An S2 contract question, not a later surprise.

## 4. Slice plan (dependency order)

- **S1 — #280 tenant-scoping decision** (design): per-tenant dirs vs
  registry tenant field vs per-tenant swapd. #339's request-identity
  decision rides with it (G50.4). Nothing hosted-multitenant builds
  before this; the vend design references its answer.
- **S2 — vend contract spec** (this repo, docs): endpoint, auth (box
  bearer from #844, owner keys from #843 for management), mint/TTL/revoke,
  per-box secret manifest, server-side audit rows, the G50.2 reconciled
  outage rule (fail closed with no lease; TTL-bounded stale authorization
  within a live lease), the G50.9 custody question (where secret values
  rest on the plane). Contract pinned here, like #846's server-contract
  checklist.
- **S3 — plane vend endpoint** (plane workspace): D1 schema, mint/revoke,
  owner-gated management, server-side audit (G50.1, G50.6). #890.
- **S4 — box-side swapd fetch path** (this repo): RAM cache, TTL refresh,
  the G50.2 dual-mode seam (plane configured → vend path with the
  reconciled outage rule; plane not configured → secrets dir as today —
  the self-hosted default must not break), box-bearer auth (G50.2, G50.5).
  Parallelizable with S3 once S2 pins the contract. #891.
- **S5 — H19 reconcile** (#134): the credential-install half routes to the
  vend bootstrap (first mint at provisioning, then vending takes over);
  the sudoers-scope half reconciles against Q4's runtime-cell answer;
  the echo-allowlist half rides the smoke-bootstrap decision (G50.7).
- **S6 — acceptance verification**: two tenants, distinct secret universes
  (S1); revoke mid-lease → box stops swapping at lease end (S3/S4);
  unreachable plane with a live lease → TTL-bounded stale swap then stop,
  loud (S4); no-lease/no-plane box → no swap, loud; no secret bytes on the
  box filesystem (RAM-only cache); plane audit shows every vend; the
  self-hosted no-plane configuration still works exactly as today.

## 5. New backlog items filed by this analysis

- **New issue #890: plane-side credential-vend endpoint** (G50.1/S3) — endpoint,
  D1 manifest schema, mint/revoke, owner-gated management, server-side
  vend audit. The contract spec (S2) is a docs slice pinned here; it must
  answer the G50.9 custody question (where secret values rest on the
  plane) before the endpoint ships.
- **New issue #891: box-side swapd plane-fetch path** (G50.2/S4) — vend-aware
  fetcher with RAM cache, TTL refresh-before-expiry, the G50.2 reconciled
  outage rule (fail closed with no lease; TTL-bounded stale authorization
  within a live lease), box-bearer auth, and the config-time dual-mode
  seam (no plane → secrets dir as today).
- #850 stays the vision tracker; a pointer comment on #850 carries the §4
  slice plan. #134 keeps H19 with a pointer note: H11's answer is now
  available, and the three elements route three ways per G50.7. #280 and
  #339 remain the S1 blockers — no new issues for what already exists.

## 6. Honest summary

The self-hosted half of #850 exists and is genuinely hardened: the
localhost swap proxy, placeholders, allowlists, placement rules, and the
audit log are real and tested. The hosted half — *"control plane vends
narrow, short-lived credentials"* — does not exist in any form: no plane
endpoint, no box fetch path, no tenant dimension, no short-lived
semantics, no plane-side audit, and no answer to where vended secret
values rest on the plane (G50.9). The dependency order is S1 → S2 →
S3/S4 → S5 → S6; building the plane endpoint (S3) before the
tenant-scoping decision (S1) would vend credentials into a shared secret
universe. The vendor precedent for the design is the q5 research: STS-style
short-lived vending as the gold standard, the izba/Vault-Agent localhost
injection-proxy shape for the box side, and honest blast-radius control
instead of a root-proof claim.
