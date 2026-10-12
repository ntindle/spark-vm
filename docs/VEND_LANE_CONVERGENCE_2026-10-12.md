# Vend-lane convergence, 2026-10-12: post-#1364 vision-vs-state (#850)

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `8219976` (2026-10-12 ~10:05 CDT).
Issue/PR numbers are GitHub references as of 2026-10-12 (not
code-verifiable from the tree). Honesty rules apply
(`docs/POSITIONING.md`): this describes current state and work to do,
not promises. Nothing here vends a credential.

This document pins the #850 credential-vending lane's state after this
morning's two turns: the 0259 gap turn's D-MT1 consequence sweep
(`docs/VEND_LANE_DMT1_CONSEQUENCE_SWEEP.md`, PR #1366, main `0fa65a7`)
and the 0559 fix turn's S2-contract D-MT1 amendment
(#1364, PR #1371, main `f9aca52`). The sweep filed #1364 as its
follow-up with the amendment explicitly *not landed in the analysis
turn*; #1364 has since landed, so the sweep's §4 (D-VD2) and §6
follow-up lines are stale — §3 below records the correction. This doc
files one genuinely-new gap and changes no code.

**Non-overlap map (what this doc is not):**
- `docs/VEND_LANE_DMT1_CONSEQUENCE_SWEEP.md` — the 0259 sweep
  (findings F-VD1–F-VD7, decisions D-VD1–D-VD6). State-superseded only
  for the two stale lines §3 corrects; its findings and decisions
  stand.
- `docs/CREDENTIAL_VEND_CONTRACT.md` — the S1+S2 contract (2026-10-03,
  PR #930), as amended by #1364 (PR #1371). The contract is the
  authority on the vend design; this doc reads it, it does not amend
  it.
- `docs/CREDENTIAL_VEND_S3S4_DESIGN_AHEAD.md` — the S3/S4 build inputs
  (2026-10-08, PR #1180). Its build notes (§5) and F-V3/D-V3 stand.
- `docs/CREDENTIAL_VENDING_GAP_ANALYSIS.md` — the original G50-series
  decomposition (2026-10-02). G50.1–G50.9 stand except where the sweep
  or #1364 say otherwise.
- `docs/MULTI_TENANT_PLANE_MODEL_DECISION.md` — the D-MT1 record
  (2026-10-09, PR #1245). Its D-MT2 bootstrap-leg decision and F-MT5
  erasure decision are vend-lane inputs, not this doc's subjects.
- The push lane's schema contract (`docs/PUSH_SENDER_SCHEMA_CONTRACT.md`,
  #988) — read for the F-VC1 comparison only; the push lane's own
  convergence record is `docs/PUSH_LANE_CONVERGENCE_2026-10-10.md`.

## 1. The vision (#850, verbatim acceptance)

- No real secret material on the box filesystem or in agent-visible config.
- Swaps only for allowlisted hosts; everything else refused.
- Full audit log of swaps.

## 2. What moved since the sweep (`0fa65a7`, ~03:1x CDT)

- **#1364 landed** (PR #1371, squash `f9aca52`, 2026-10-12 ~06:29 CDT;
  issue closed via Closes keyword): the S2-contract D-MT1 amendment
  the sweep filed as its follow-up. The contract now reads, verbatim
  in the relevant clauses: the record-level key is `box_id` *within
  the tenant plane's own D1* (the "1:1 with the tenant" claim retired
  with a D-MT1 citation); "two tenants never share a manifest" is D1
  separation, not an operator provisioning invariant; the data key is
  *one per tenant plane*, provisioned per plane at plane deploy time
  (D-VD3); the key-rotation bound applies per plane, unchanged in
  shape; blast radius shrinks from every tenant to one tenant by
  construction — with the honest limit stated plainly: per-plane keys
  protect only while the operator provisions genuinely distinct keys
  per plane.
- **#1179 stayed closed**: `credential_kill` durable-command kind —
  the fast-revocation path the S2 contract §4 names. No change since
  the sweep.
- **No other vend-lane state moved**: #890 (plane vend endpoint), #891
  (box swapd fetch path), #948 (dual-mode seam), #1178 (retention
  pin), and #1365 (first-manifest-write actor, the sweep's D-VD6)
  are all still open; the credential-vend data key is still
  operator-owned (NEEDS_USER.md, standing since 2026-10-05, D-VD3
  amendment recorded 2026-10-12 ~03:3x).

## 3. Stale-line corrections to the sweep doc

Two lines in `docs/VEND_LANE_DMT1_CONSEQUENCE_SWEEP.md` describe a
world that no longer holds; they are annotated in place (surgical
edits, this turn):

- §4 **D-VD2**: "Filed as the S2-contract amendment follow-up (new
  issue, §6) — the amendment itself is not landed in this analysis
  turn." → annotated: landed 2026-10-12 ~06:29 CDT as #1364
  (PR #1371, main `f9aca52`).
- §6 follow-ups: "New issue (p3, docs): S2-contract D-MT1 amendment
  ... Filed as **#1364** by this turn (P42 fill)." → annotated: #1364
  closed 2026-10-12 via Closes keyword (PR #1371).

Everything else in the sweep stands: F-VD1–F-VD7 and D-VD1/D-VD4–D-VD6
are unaffected by #1364's landing (D-VD2/D-VD3 were the two the
amendment consumed).

## 4. Genuinely-new findings

- **F-VC1 — the push lane's schema contract carries the identical
  stale claim #1364 just retired.** `docs/PUSH_SENDER_SCHEMA_CONTRACT.md`
  D45 (the #988 contract, untouched by the push lane's 2026-10-10
  convergence refresh, which asserted the contract "stands as
  written"): *"Stated plainly, as the vend contract states it: one data
  key protects all tenants' subscription secrets, so one key compromise
  exposes every `p256dh`/`auth`."* Under D-MT1 the push
  subscriptions live on the tenant plane (the 2026-10-10 push
  convergence: "subscriptions stay owner-keyed on the tenant's
  plane"), the sender/sweep run against the tenant plane, and the data
  key is a Worker secret — one per tenant plane's Worker, exactly the
  D-VD3 shape. The claim is false in the same way the vend
  contract's was: one key now protects one tenant's subscription
  secrets, and the blast-radius sentence overstates the compromise
  case. This is a docs-amendment follow-up in the #1364 class, scoped
  to the push lane. Filed as **#1375** by this turn (p3,
  track:hosted-product); the push lane's convergence record gets a
  pointer, not a rewrite.

No other new gaps: the remaining vend-lane work is already tracked
(#890, #891, #948, #1178, #1365, and the operator data key in
NEEDS_USER.md).

## 5. What is still unbuilt (the honest list)

1. **The plane endpoint** (#890, p2) — the S3 vend endpoint build,
   gated on #1178's retention pin for its D1 migration (D-VD5).
2. **The box fetch path** (#891, p2) — swapd's plane-fetch path for
   vended credentials.
3. **The dual-mode seam** (#948) — vend-mode boxes must not mint
   local grants on plane-application paths.
4. **The retention pin** (#1178) — audit retention/erasure on the
   tenant plane; tenant attribution half is decided (no tenant
   column, F-VD1).
5. **The first-manifest-write actor** (#1365, p2) — D-VD6's routed
   question: who performs the first manifest write on a
   signup-provisioned tenant plane.
6. **The operator data key** (NEEDS_USER.md) — per-plane AES data keys
   as Worker secrets, provisioned at plane deploy time (D-VD3); the
   loop must not generate or handle them. Until set: #890's value
   path and #968's subscription-secrets storage cannot ship.
7. **The push D45 amendment** (F-VC1, #1375 filed this turn) — same
   class as #1364, for the push-subscription data key.
