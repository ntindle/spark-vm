# Credential-vend S3/S4 design-ahead: vision vs state at main `014772c6`

**Vision vs current state for the vend-lane builds** — pinned to main
`014772c6` for all in-repo claims. This is the design-ahead pass over
`docs/CREDENTIAL_VEND_CONTRACT.md` (pinned 2026-10-03, PR #930, merge
`35485f1`): what moved in the five days since the S1/S2 contract pin,
what the S3 (#890 — plane vend endpoint) and S4 (#891 — box-side swapd
fetch path) builds still need pinned before they are built, and the two
genuinely-new gaps those builds uncovered. S5 (vend bootstrap, H19) and
S6 (acceptance) are unchanged since the contract — this doc does not
re-open them.

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below
is **current state and work to do**, not promises. The hosted product is
not live. The plane lives outside this repo, so plane-side rows below are
the contract the plane must implement, not a description of what it does
today.

## 1. The vision, restated for S3/S4

A hosted box holds no long-lived secrets on its filesystem. On first
boot after pairing it presents its box Bearer <redacted> bearer
(current+grace classes per §2/D-V2) at the plane's vend endpoint,
receives narrow short-lived credentials (minutes-to-hours TTLs), and
keeps swapping against a RAM-only cache with refresh-before-expiry
and hard delete-on-expiry. Revocation propagates within one refresh
cadence (`max(300 s, ttl/3)`); the server-side `vend_audit` records
every mint, refresh, revoke, and manifest write/read with no values.
The self-hosted no-plane configuration works exactly as today (the §6
dual-mode seam). Acceptance is the contract's §10 ten-item checklist.

## 2. What moved since the contract pin (2026-10-03 `35485f1`)

- **Box tokens now rotate (#846).** The contract's "box Bearer <redacted>
  are three bearer classes: `current`, `grace` (15-min
  previous-token grace), and everything-else → 401, with the ±300 s
  clock window. The #890 issue body predates this — its "presents its
  box Bearer <redacted> one bearer class, not two.
- **The box-authenticated endpoint pattern exists (#952).**
  `POST /v1/boxes/{box_id}/approvals/file` shipped with a
  current+grace gate and a live-first forward D1 migration
  (table-rebuild, rows preserved). S3 is no longer the first
  box-authenticated write endpoint — it inherits a working gate shape
  and a migration discipline instead of inventing both.
- **The D1 schema discipline is now pinned (#988/#1061/#990).** The
  contract's §2.4 D1 schema was written before the loop's schema-contract
  practice existed: D49 pre-deploy anchor, D50 outbox lifecycle, D57
  page-once partial-unique-index, D61 audit-key non-collision
  (`PUSH_SENDER_SCHEMA_CONTRACT.md` §1.3), and D1-batch-portable atomic
  statements (#990). S3's three tables should be written in that
  discipline, not the contract's raw `CREATE TABLE` sketch.
- **The plane is now a command producer (#873).** `approval_decision` is
  the first plane-produced kind in `docs/DURABLE_COMMANDS.md`'s
  registry, with the rule that a new plane-produced kind needs a
  registry row before the plane may enqueue it. The contract's §4
  "SHOULD route `credential_kill` through the durable-command queue"
  now has a registry to land in — and a naming/addressing precedent to
  follow.
- **The tenant model is an open decision (T3, #1159).** The contract's
  §1 S1 decision ("tenant = box_id, 1:1; `tenant_id` reserved NULL in
  `vend_audit`") was written under the single-owner plane. Today's
  tenant-identity analysis asks one-plane-per-tenant vs tenant layer —
  unmade. The vend D1 tables are the next tables the plane will add to;
  their tenant attribution posture is unpinned (finding F-V1).
- **Audit retention/erasure is an open design (T7, #1162).** The
  contract's §2.5 makes `vend_audit` a tamper-proof server-side record
  with no values. Tenant erasure collides with audit immutability —
  and the retention window is unpinned (finding F-V2).
- **The dual-mode seam has an open build issue (#948).** "Vend-mode
  boxes must not mint local grants on plane-approve" (p2, open). The
  contract's §6 seam predates it; S4 must respect it (finding F-V8).
- **Enrolled boxes stand down local channels (#1135).** On a
  plane-enrolled box the box-local push queue stands down in favor of
  the plane. S4's plane-fetch path is the same shape: plane-driven,
  nothing local to fall back to — consistent, and a reminder that S4's
  outage rule (§4) is the *only* degradation story.

## 3. The findings

- **F-V1 — The S1 "tenant = box_id" assumption needs a T3 decision
  before S3 ships its D1 schema.** If #1159 lands tenant-layer, the
  contract's `tenant_id`-reserved-NULL posture is a silent retrofit
  debt: `vend_manifest`/`vend_values`/`vend_audit` would gain their
  tenant attribution after rows exist. T4 (#1160) pins the
  same rule for approval records (stamp tenant/box→tenant attribution
  at record time, fail-closed). The vend tables deserve the same pin
  *before* S3's migration ships. → filed (this turn).
- **F-V2 — `vend_audit` retention and erasure are unpinned.** §2.5's
  audit is forever-by-default: every mint/refresh/revoke lands, never
  a value. Under T7 (#1162) a tenant's erasure request collides with
  the audit's immutability story — and "forever" is also an unbounded
  D1 growth story (cf. #1058's 90-day retention+GC for the push
  tables). S3 should ship the write path; the retention pin is a
  design decision that gates S6, not an implementation detail the
  builder can improvise. → filed (this turn, same issue as F-V1 —
  one schema-review conversation).
- **F-V3 — `credential_kill` is named but unowned.** The contract's §4
  says "#891 SHOULD route an owner-issued `credential_kill` through
  the durable-command queue (#848) so a live box wipes its RAM cache
  within one command-fetch cycle; until that ships, the TTL cap is the
  kill bound." Five days later: no registry row (the registry rule
  now *requires* one before the plane may enqueue), no wire shape, no
  owner endpoint, no box-side wipe+ack semantics, no issue. It is the
  symmetric kind to `approval_decision` — plane-produced,
  owner-originated, box-executed — and the revocation story's only
  fast path (pull stays bounded at one refresh cadence per §5).
  → filed (this turn).
- **F-V4 — The contract's D1 sketch predates the schema-contract
  discipline.** §2.4's raw `CREATE TABLE`s carry no pre-deploy anchor
  (D49), no outbox-lifecycle thinking (D50), no audit-key
  non-collision rationale (D61), and the `revoked_at` tombstone has no
  stated interplay with D57-style page-once pins. S3 should not
  re-derive these from first principles. → decision D-V1, no issue.
- **F-V5 — The vend endpoint's bearer story predates rotation.**
  #890's body says "presents its box Bearer <redacted> singular.
  Current+grace must both vend; an unknown/expired/revoked token
  401s; the ±300 s clock window applies. The #952 gate is the
  in-repo precedent for exactly this shape. → decision D-V2; pointer
  comment on #890.
- **F-V6 — §7's #339 twin stands, but #339 itself is p1-open.**
  The contract decided the hosted shape (per-tenant request auth
  unnecessary under per-tenant box); #339 stays open for the
  cooperative same-box shape. S3/S4 change nothing here — but the S4
  build must not accidentally weaken the cooperative shape's
  documented limits. Status note; no new gap.
- **F-V7 — The mlock/swapless fork is unpinned.** Contract §5: "#891
  must `mlock(2)` the cache pages (or platform equivalent) and
  suppress core dumps for the fetcher process, or the hosted box
  image must run swapless; otherwise acceptance item 4 (§10) fails."
  Five days later the golden-image lane (#1087 family, #1111, #1176)
  is the natural home for swapless, and it has not said so. S6 item 4
  ("no secret bytes on the box filesystem") needs one of the two
  pinned. → decision D-V4.
- **F-V8 — S4 must land inside #948's seam.** #948 (p2, open):
  vend-mode boxes must not mint local grants on plane-approve. S4's
  fetch path and #874's ingest both touch the grant-minting box-side
  stack; the seam rule is that vend mode and local-mint mode never
  mix. → decision D-V5; pointer comment on #948.
- **F-V9 — The S5 manifest bootstrap rides #906.** Contract §8 routes
  H19's credential install to S5 (manifest PUT at provisioning, no
  lease before pairing per G51.4). The manifest write path is the
  plane's owner-auth surface; the orchestrator (#906, open) is its
  first client. S3's manifest endpoints and #906's record-writing
  posture (D-O4: orchestrator never writes D1, records via the plane
  owner-auth endpoint) must agree. Status note for the S3 builder.
- **F-V10 — The vend-audit read path is owner-only by construction.**
  §2.5's `GET /v1/owner/boxes/{box_id}/credentials/audit` stays on
  the owner side of the auth-class boundary — consistent with T6's
  advisory (404-vs-403 moot until T3). No gap.

## 4. The decisions

- **D-V1 — S3 adopts the loop's D1 schema discipline.** New vend
  tables ship with a D49-style pre-deploy anchor, a D61-style
  audit-key non-collision rationale, D1-batch-portable atomic
  statements (the #990 precedent), and the live-first forward
  migration (#952 precedent). The contract's §2.4 sketch is the
  logical shape, not the migration.
- **D-V2 — The vend endpoint honors current+grace bearer classes.**
  Unknown/expired/revoked → 401; the #846 ±300 s window applies to
  token expiry checks. (The #952 gate is the precedent; the vend
  endpoint is its second application.)
- **D-V3 — `credential_kill` is a plane-produced durable-command
  kind.** Until it ships, the contract's TTL cap remains the kill
  bound — honest sequencing, no silent upgrade of the revocation
  claim. Sketch for the filed issue: kind `credential_kill`,
  payload `(name, revoked_at, idempotency_key:
  credential_kill:<box_id>:<name>:<revoked_at>)`, owner-issued revoke
  enqueues, box hard-deletes the name from the RAM cache on receipt
  and acks; unknown-client behavior: **fail-closed per the
  registry's security-effects rule** — a kind that revokes grants
  MUST declare "not acked, run stops loudly," and an old box that
  does not know it must never silently skip it (the reference
  implementation's ack-and-log is a liveness choice, not a universal
  policy). Mitigations, named by the registry itself: the plane must
  not enqueue the kind for an executor that doesn't list it
  (plane-side capability gating), and the dead-letter hook is the
  designed backpressure until that gating lands.
- **D-V4 — S6 item 4 pins one of mlock or swapless.** Recommendation:
  the golden-image lane owns swapless as the operator decision; #891
  carries `mlock(2)` + no-core-dump as the in-repo defense so the
  acceptance holds on images that aren't swapless. The S4 build
  records which it pins — the claim "no secret bytes on disk" is
  conditional on the pin.
- **D-V5 — S4 lands inside #948's seam.** Vend-mode boxes never mint
  local grants on plane-approve; the S4 fetch path and the #874
  ingest share that invariant. The S4 build verifies the seam, it
  does not re-decide it.
- **D-V6 — Retention is designed in the filed issue, not in S3.**
  S3 ships the `vend_audit` write path; the retention/erasure pin
  gates S6 acceptance, so the filed issue must close before the S6
  verification runs.

## 5. Build notes for the S3/S4 builders

- #890 (S3): implement against the contract's §2 (+ D-V1/D-V2);
  owner read path per §2.5; F-V1/F-V2's issue closes before the D1
  migration ships, not after.
- #891 (S4): implement against the contract's §4–§6 (+ D-V4/D-V5);
  bearer grace per F-V5; `credential_kill` handling when the filed
  issue lands (D-V3).

## 6. Issues filed

- #1178 — Vend D1 tables: tenant attribution + audit retention/erasure
  (F-V1/F-V2 — T3/T7 interplay, S3 build input), p2.
- #1179 — `credential_kill` durable command kind for fast revocation
  (F-V3), p2.

Pointer comments on #850 (vision tracker), #890, #891, and #948
carry this doc's location. #339's hosted-shape decision (§7) is
unchanged; #134's S5 routing (§8) is unchanged.
