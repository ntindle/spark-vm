# Credential-vend lane: vision vs state at main `a368262` (2026-10-16)

**Lane-state refresh.** Statuses pinned to this repo at main `a368262`
(PR #1552, 2026-10-16). This doc supersedes the state rows of
`docs/CREDENTIAL_VENDING_GAP_ANALYSIS.md` (pinned 2026-10-02, pre-S1/S2
contract) and continues
`docs/CREDENTIAL_VEND_S3S4_DESIGN_AHEAD.md` (pinned 2026-10-15, F-V1–F-V10)
— which declined to file new S5/S6 slices. The findings below are what
the design-ahead left unowned.

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below
is **current state and work to do**, not promises. The hosted product is
not live. The plane (`sparkvm-control`) lives outside this repo; the
contract is the plane's build spec, not a description of what it does
today (`docs/CONTROL_PLANE_API_REFERENCE.md`: "no vend endpoint, no box
fetch path — the self-hosted swap-proxy half is the only half that
exists").

## 1. The vision (#850), restated

Secrets never reach the agent or the box disk. A hosted box holds no
long-lived secrets on its filesystem: on first boot after pairing it
presents its box Bearer <redacted> at the plane's vend endpoint, receives
narrow short-lived credentials (minutes-to-hours TTLs), and swaps
against a RAM-only cache with refresh-before-expiry and hard
delete-on-expiry. The plane keeps manifests (names, TTLs, per-secret
host allowlists) and ciphertexts only — values are AES-128-GCM under a
per-tenant-plane Worker-secret data key, write-only after set, owner
keys manage metadata but can never read plaintext values through the
API. Every mint, refresh, revocation, and manifest write/read is
server-side audited. The self-hosted no-plane configuration works
exactly as today (the §6 dual-mode seam).

## 2. Slice state (contract §11, at `a368262`)

| Slice | State | Owner |
|---|---|---|
| S1 tenant-scoping (#280) | **Shipped** — decision C (per-tenant box) + D-MT1 amendment (2026-10-09: one plane per tenant; the contract's older "box_id 1:1 with tenant" claim is retired, per-box manifest boundary kept) | — |
| S2 vend contract | **Shipped** — `docs/CREDENTIAL_VEND_CONTRACT.md` (PR #931); §2.1b token-state gate added post-#1402 (mint requires `current` token; `grace` mints nothing) | — |
| S3 plane vend endpoint (#890) | **Open, p2** — not built. Body predates #1178: no reference to the tenant-attribution gate (F-VR-3) | build lane |
| S4 box-side swapd fetch (#891) | **Open, p2** — not built. Must land inside #948's seam (F-V8/D-V5) | build lane |
| S5 H19 reconcile → vend bootstrap | **Open** — rides #906 per design-ahead F-V9 (manifest PUT at provisioning; orchestrator is the first client of the owner-auth surface); this turn records the dependency with a pointer comment on #906 (D-VR-4) | #906 (pointer comment this turn) |
| S6 acceptance (contract §10, 13 items) | **Open** — F-VR-1 → #1553 (filed this turn) | — |
| Vend data key D-VD3 | **Open** — F-VR-2 → #1554 (filed this turn) | operator |
| #1178 vend D1 retention pin (+ closed attribution/erasure halves) | **Open, p2** — retention pin only (D-VD1 re-scope: attribution decided — no tenant column; erasure decided — plane-instance destruction per D-MT1 F-MT5); the retention pin gates #890's D1 migration | design lane |
| #1179 `credential_kill` kind / #1269 registry pin | **Closed** | — |
| #1401 no-oracle 401 / #1402 mint token-state gate / #1403 AES-128-GCM vendor | **Closed** (contract pins landed) | — |
| #1404 placement vocabulary | **Open, p2** — pre-build gate on #890 (contract half landed via #1453) | build lane |
| #1406 manifest-write atomicity | **Open, p3** — contract half landed (#1545); build half gates #890 | build lane |
| #1500 `vend_audit.actor` free-text / #1405 no rate limiter / #1407 key-rotation re-encryption | **Open, p3** — contract-adjacent hardening, owned | — |

## 3. The findings (genuinely new — no duplicates among open issues)

- **F-VR-1 — S6 acceptance has no owning issue.** The contract's §10
  is a 13-item checklist (two boxes distinct universes; revoke→stop
  within `max(300 s, ttl/3)`; unreachable-plane TTL-bounded stale
  swaps; RAM-only cache; full audit; self-hosted parity; owner GET
  metadata-only; revoked-bearer semantics; 401-no-oracle per #1401;
  grace-token 401 per #1402; `alg = aes-128-gcm` per #1403; atomic
  manifest writes per #1406). S3 (#890) and S4 (#891) are build
  issues; neither owns running the checklist, and a build issue's
  acceptance naturally narrows to its own slice. The design-ahead
  named S6 but declined to file it. Without an owning slice, the
  checklist is prose the builds can silently under-run. → filed
  (this turn, #1553): vend S6 acceptance slice, p2, tracked against
  the contract's §10 verbatim (all 13 items — two boxes distinct
  universes; revoke→stop within `max(300 s, ttl/3)`; unreachable-plane
  TTL-bounded stale swaps; RAM-only cache; full audit; self-hosted
  parity; owner GET metadata-only; revoked-bearer semantics; box
  bearer at owner endpoints → 401 (auth-class namespace separation,
  §2.1); 401-no-oracle per #1401; grace-token 401 per #1402;
  `alg = aes-128-gcm` per #1403; atomic manifest writes + tombstone
  semantics per #1406).
- **F-VR-2 — The vend data key (D-VD3) has no tracking issue.** Contract
  §3: the data key lives as a Cloudflare Worker secret — **one per
  tenant plane**, provisioned at plane deploy time — never in D1,
  never in the repo, never in logs, never in an audit row. Rotation is
  an operator procedure (re-encrypt `vend_values` under the new key;
  old key retained only for the rotation window). Today this exists
  only as prose in `NEEDS_USER.md` ("credential-vend / push-subscription
  data key", operator-owned) — there is no GitHub issue the loop or
  the operator can point at, unlike the R2 bucket (#1191) and the
  per-signup VAPID issuance (#1475). A secret-provisioning step with no
  tracker is a step that silently never happens. → filed (this turn,
  #1554): operator-owned data-key provisioning, p2.
- **F-VR-3 — #890's sequencing gate needed a restatement, not a
  first record.** #1178's gate "#890 must not ship its migration
  before this closes" survives, but D-VD1 (2026-10-12, recorded on
  #1178) closed the tenant-attribution half — no tenant column, the
  #1160 pattern — and decided the erasure half per D-MT1 F-MT5; the
  surviving gate content is the retention pin. The gate was previously
  recorded only as point (3) of the 2026-10-08 design-ahead pointer
  comment on #890 (id 6068733052). This turn's pointer comment
  (id 6209621809) restated it with the fail-closed posture and the
  named tables so the migration requirement is explicit where the
  builder looks — and the follow-up correction (id 6209698172)
  re-scopes it to the retention pin per D-VD1. No new issue — the gate
  belongs on the build issue, not in a third tracker.

## 4. The decisions

- **D-VR-1 — #1178's retention pin is a build-gate for #890's D1
  migration, recorded on #890.** The gate's content was re-scoped by
  D-VD1 (2026-10-12) — the attribution half is decided, the erasure
  half is decided, only the retention pin remains open. This turn
  puts the surviving gate where the builder looks (pointer comment
  on #890, with the D-VD1 correction).
- **D-VR-2 — S6 is a verification slice, not a build slice.** It is
  filed separately (not folded into #890/#891) so the 13-item
  checklist cannot be absorbed into per-slice acceptance and
  partially run.
- **D-VR-3 — The data key is operator-owned, like #1191 and #1475.**
  The loop provisions nothing; the issue tracks the operator step
  (provision per plane at deploy time; rotation procedure), and the
  goal-workspace NEEDS_USER.md data-key entry now points at #1554.
- **D-VR-4 — S5's manifest-PUT gets a tracking signal on #906.** The
  manifest write at provisioning (via the plane owner-auth surface, no
  lease before pairing per contract §8/G51.4) is the first vend
  interaction; by the F-VR-1/F-VR-2 rule an untracked step silently
  never happens. This turn leaves a pointer comment on #906 (id
  6209716463) naming the S5 requirement (mirroring D-VR-1: put it
  where the builder looks), so "rides #906" is a recorded dependency,
  not prose.

## 5. What this doc does not claim

- No plane-side facts beyond the API reference's pinned view; the
  contract is a spec, not a deployment description.
- S5's routing ("rides #906") is inherited from the design-ahead's
  F-V9; this turn adds the missing tracking signal (pointer comment on
  #906, D-VR-4) rather than re-deciding the routing.
- #1500/#1405/#1407 stay owned p3 hardening; this turn files nothing
  for them.
