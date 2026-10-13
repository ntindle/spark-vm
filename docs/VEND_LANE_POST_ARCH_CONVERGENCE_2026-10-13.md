# Vend-lane post-arch convergence, 2026-10-13: the #1401–#1407 findings vs state (#850)

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `0dd9e9e` (2026-10-13). Issue/PR
numbers are GitHub references as of 2026-10-13 (not code-verifiable from
the tree). Honesty rules apply (`docs/POSITIONING.md`): this describes
current state and work to do, not promises. Nothing here vends a
credential.

This document pins the #850 credential-vending lane's state after the
2026-10-12 convergence pin (`docs/VEND_LANE_CONVERGENCE_2026-10-12.md`,
at main `8219976`). Three things moved since that pin, all in the last
~31 hours:

1. **PR #1408 merged** (`850a8aa`) — "vend contract 401 + AES-128-GCM
   (#1396, #1401, #1403)": the S2 contract's §2.1 now pins the no-oracle
   `401` (the #1401 ask) and §3 now pins AES-128-GCM with the
   vendored-`push_crypto.py` rationale (the #1403 ask). #1408's body says
   "companion docs for #1401 and #1403" — both issues stay OPEN.
2. **PR #1409 merged** — "dual-mode credential-source seam for the
   ingest (#948)", Closes #948: `SVM_CRED_MODE` (`local` default /
   `vend`), latched per-run via `credential_mode.json` in the state dir.
3. **#1401–#1407 filed** 2026-10-13 ~01:39 CDT (arch deep-read of the
   vend contract): seven pre-build gates on the #890 S3 endpoint build.

**Non-overlap map (what this doc is not):** not the S3/S4 build notes
(`docs/CREDENTIAL_VEND_S3S4_DESIGN_AHEAD.md` §5 still owns those); not a
re-verification of the 2026-10-12 pin's D-VD2/D-VD3 claims (unchanged);
not #890's build. This doc's job is narrow: verify the seven arch
findings against current main, pin which halves of #1401/#1403 landed,
retire #948 from the honest list, and refresh the remaining-build list.

## 1. The vision (#850, verbatim acceptance)

Boxes authenticate with their box Bearer <redacted> and receive narrow,
short-lived credentials from the plane; revocation propagates; every
vend is server-side audited. Unchanged.

## 2. Findings

### F-VC2 — #1401's contract half is resolved on main; the build half is #890's

Verified at `docs/CREDENTIAL_VEND_CONTRACT.md` §2.1 (post-#1408): "Auth
failures collapse to a plain `401` on the whole box surface — `{box_id}`
in the path must equal the token's box, but a wrong-box token reads the
same unattributed `401` as an unknown token (the plane's no-oracle
convention: a stolen box token presented against other box ids must not
learn which ids are enrolled)." The `403` the issue quoted is gone from
the contract. #1401 stays OPEN — correctly: its slice is "resolve the
auth-failure status-code contract for the #890 vend endpoint **before it
builds**", and the endpoint does not exist yet.

### F-VC3 — #1403's contract half is resolved on main; the build half is #890's

Verified at `docs/CREDENTIAL_VEND_CONTRACT.md` §3 (post-#1408):
"`vend_values.ciphertext` is AES-128-GCM with a random nonce per value
(issue #1403: the plane worker is stdlib-only with no AES, so the
contract names the vendored AES-128-GCM from `hosted/push_crypto.py` —
vendored the way the worker already vendors its Ed25519/P-256 code —
rather than an AES-256 the platform cannot currently implement)"; the
§2.4 DDL comment reads `alg TEXT /* 'aes-128-gcm' (issue #1403: ...` —
consistent. #1403 stays OPEN — correctly: the actual vendoring into the
plane worker and the data-key custody are #890's build scope.

### F-VC4 — #948 is closed-for-real; the 2026-10-12 pin's §5 item 3 is stale

PR #1409 ("Closes #948") is merged. Verified on main:
`pairing/spark_pair.py` carries `_CRED_MODE_ENV = "SVM_CRED_MODE"`
(L1321) and `_CRED_MODE_PIN_FILE = "credential_mode.json"` (L1356) —
the env signal (`local` default / `vend`), the first-run pinning, and
the loud drift failure the PR body describes. The convergence pin's
honest-list item 3 ("The dual-mode seam (#948)") is retired here; #891's
box-side build consumes `SVM_CRED_MODE` rather than re-deciding the seam.

### F-VC5 — #1402 (grace-token mint gate) is a conflict-resolution gate, not open ground

The contract carries zero "grace" mentions, and the issue's security
concern stands on its own terms: the box-route convention accepts
`current` **and** `grace` token states, so a rotated-out token's
15-minute grace window would extend its secret-issuing power past the
rotation that was supposed to revoke it. But the lane's S3/S4 build
guidance already prescribes the **opposite**: the design-ahead §1 has
the box present "its box Bearer <redacted> bearer (current+grace classes per
§2/D-V2) at the plane's vend endpoint", and §2 notes the shipped
`POST /v1/boxes/{box_id}/approvals/file` "current+grace gate" as the
shape S3 inherits ("it inherits a working gate shape and a migration
discipline instead of inventing both"). The operative decision is
D-V2 — "The vend endpoint honors current+grace bearer classes"
(F-V5: "Current+grace must both vend"). So the S3 builder would not
guess — they would inherit current+grace — and #1402 disagrees with
that inheritance. This is a genuine conflict between a deliberate
consistency choice (design-ahead, 2026-10-08) and a genuine security
cost (arch finding, 2026-10-13). D-VD11 resolves it below.

### F-VC6 — #1404 (placement parameterization) is unaddressed

Contract §2.1a still defines `placement` as a "non-empty subset of
`bearer_header | custom_header | query_param | url_path_segment`" —
bare keywords. `proxy/swap_addon.py` (L28–36) enforces **parameterized**
placements (`{"custom_header": name}` etc.). A manifest the contract
accepts and a proxy that cannot consume it is the live mismatch the
issue names. Pre-build gate on #890 (validation) and #891
(enforcement); zero comments, zero linked progress.

### F-VC7 — #1405 (the 429 with no mechanism) is unaddressed

Contract §2.2 still claims per-box mint rate limiting ("`429` —
precedent: the pairing 50-pending cap"). The cited precedent is a count
cap, not a rate limit, and no rate-limiting mechanism exists anywhere in
the plane worker. A compromised box minting in a tight loop gets a
`vend_audit` row and a decrypt op per mint: D1 write amplification with
no backstop. The contract must gain a real mechanism or drop the claim
before #890 builds against it. Zero comments, zero linked progress.

### F-VC8 — #1406 is a contract-text amendment gate; the mechanism is already prescribed

Contract-scoped, the issue stands: §2.1a says "Write/replace is per-box
and **atomic**: the posted array becomes the box's entire manifest —
names absent from the array have their values deleted", while the write
spans `vend_manifest` **and** `vend_values` with no D1-batch mechanism
pinned — partial failure leaves exactly the state the contract forbids
(metadata with no value, or value with no metadata). But the mechanism
answer already exists in the lane's build guidance: the design-ahead §2
prescribes "D1-batch-portable atomic statements (#990)" for S3's tables
("S3's three tables should be written in that discipline, not the
contract's raw `CREATE TABLE` sketch"). So #1406 is not an unanswered
design question — it is a contract-text amendment gate: pin the
two-table atomicity unit **and** the batch mechanism in the contract
text before #890 builds against it. Zero comments, zero linked
progress.

### F-VC9 — #1407 (key-rotation code path) is unaddressed

Contract §3 still says "Key rotation is an operator procedure
(re-encrypt `vend_values` under the new key; the old key is retained
only for the rotation window)." "Operator procedure" without code means
manual D1 surgery with the data key in a human's hands — the procedure
the contract's own custody section exists to avoid. The
decrypt-with-old / encrypt-with-new sweep needs an execution path
before the first rotation is ever needed. Zero comments, zero linked
progress.

### F-VC10 — the seven are pristine

#1401–#1407 carry zero comments and zero linked PRs/commits between
filing (2026-10-13 ~01:39 CDT) and this pin. No other turn has started
on them; nothing here double-counts in-flight work.

## 3. Decisions

- **D-VD7.** The seven arch issues are **pre-build gates, primarily on
  #890 (S3)** — with #1404's enforcement half on #891 (S4) — not
  post-build polish. Each names a contract ambiguity the S3 builder
  would otherwise guess at under schedule pressure — the placement
  value shape (#1404), the 429 mechanism (#1405), the two-table
  atomicity unit (#1406, mechanism already prescribed — F-VC8), the
  rotation execution path (#1407) — plus the two contract halves
  already landed (#1401, #1403). #1402's direction is resolved by
  D-VD11 below; its remaining work is implementation, not decision.
  The issues stay open until #890's build resolves them in code.
- **D-VD8.** #1401 and #1403 stay open **deliberately**. "Companion
  docs" is not "Fixes": a contract amendment does not retire an issue
  whose acceptance is build behavior. (Anti-overclaim discipline: the
  doc half landing early is the intended sequence, not a premature
  closure.)
- **D-VD9.** #948 retires from the honest list — the seam shipped
  (#1409) with the latching discipline; the 2026-10-12 pin's §5 item 3
  is corrected here, in place.
- **D-VD10.** **No new issues filed this turn.** The seven already
  exist, are well-scoped, and are pristine (F-VC10); the value here is
  the verified convergence pin, not more issues.
- **D-VD11.** #1402 is resolved **in the issue's favor, narrowly**:
  the vend endpoint reuses the shared box-auth gate (the design-ahead's
  "inherit the gate shape" stands — no new mechanism), but its
  **mint path requires `current` token state**; `grace` stays accepted
  on the non-secret-issuing box routes per the #952 precedent. Rationale:
  rotation's purpose is revoking the old token's powers, and a
  secret-issuing endpoint is exactly where the grace extension hurts;
  the availability cost is nil — the box holds the current token after
  rotating, and grace exists for in-flight requests, not new mints.
  This **supersedes** the design-ahead's §1 "current+grace ... at the
  plane's vend endpoint" line **and decision D-V2 ("The vend endpoint
  honors current+grace bearer classes", F-V5) on the mint path**;
  D-V2's 401 / ±300 s window remainder stands. #1402's remaining work is
  implementation in #890, not a further decision.

## 4. The honest remaining-build list (refreshes the 2026-10-12 pin's §5)

1. **The plane endpoint** (#890, p2) — the S3 vend endpoint build.
   Pre-build gates, in dependency order: #1178's retention pin for the
   D1 migration (D-VD5, unchanged); then #1404 (placement shape),
   #1405 (429 mechanism), #1406 (atomicity unit — mechanism prescribed,
   contract text still to amend), #1407 (rotation path); the #1401/#1403
   contract halves are landed, their build halves ride this build;
   #1402's direction is decided (D-VD11: mint requires `current`),
   implementation rides this build.
2. **The box fetch path** (#891, p2) — swapd's plane-fetch path;
   consumes #1409's `SVM_CRED_MODE` (D-VD9); #1404's placement shape
   gates its enforcement half.
3. **The retention pin** (#1178, p2) — audit retention/erasure on the
   tenant plane; gates #890's D1 migration.
4. **The first-manifest-write actor** (#1365, p2) — D-VD6's routed
   question, unchanged.
5. **The operator data key** (NEEDS_USER.md) — per-plane AES data keys
   as Worker secrets (D-VD3); the loop must not generate or handle
   them. Until set: #890's value path and #1392's subscription-secrets
   storage cannot ship.
6. **The push D45 amendment** (#1375, p3) — F-VC1's follow-up, unchanged.

## 5. Issues filed

None (D-VD10). Pointer comment on #850 (the lane vision tracker) carries
this doc's location.
