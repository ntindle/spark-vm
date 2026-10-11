# Rollout-controller convergence, 2026-10-11: the #1261 tenant-plane lane

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `fc1614f6` (2026-10-11 ~04:5x CDT).
Issue/PR numbers are GitHub references as of 2026-10-11 (not
code-verifiable from the tree). Honesty rules apply (`docs/POSITIONING.md`):
this describes current state and work to do, not promises. No controller
code ships in this analysis; nothing here deploys anything.

This document is a post-S3 pin of the #1261 lane. It supersedes the §2
state table and the "Honest summary" of
`docs/TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md` (2026-10-10, pinned
to main `8ac2f54`) — S3 (#1286, PR #1303, merged `fc1614f6`) landed *after*
that analysis pinned its state. Findings F-RC-1–F-RC-8 and decisions
D-RC-1–D-RC-6 stand except where noted below. It files no new issues:
every remaining gap below is already tracked by an open issue.

**Non-overlap map (what this doc is not):**
- `docs/TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md` — the 2026-10-10
  build-path analysis (F-RC-1–F-RC-8, D-RC-1–D-RC-6, files #1285–#1288).
  Consumed and state-superseded, not replaced.
- `docs/OPERATOR_PLANE_BUILD_PATH_GAP_ANALYSIS.md` — the parent
  (2026-10-10, #1257): F-OP7/D-OP7 named the rollout controller as #1261's
  scope. This doc consumes that pin.
- `docs/PRODUCTION_DEPLOY_CONTRACT.md` — the deploy record discipline
  (deployment id + SHA-256 of deployed bytes) the D-RC-2 pick (b)
  inherits. Unchanged.
- The box-layer fleet doc (`docs/FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md`,
  G15–G18) — vocabulary donor, enforcement points do not transfer.
- The provisioning lane (#851 → #905/#906/#907/#908) — creates the planes
  the controller will roll out to (F-RC-8, N=0 today); the controller does
  not absorb it.

## 1. The vision (#1261)

The rollout controller: staged rollout of the tenant-plane worker
template across N tenant planes (canary → waves), per-plane version
inventory, update event reporting.

Acceptance (#1261, verbatim): *a tenant-plane template change can roll out
across N planes in stages with inventory and rollback; per-plane
operational cost is measurable.*

## 2. Vision vs state (pinned 2026-10-11)

| Vision | Current state |
|---|---|
| A template change rolls out to N tenant planes in stages: canary, then waves, each wave health-gated | Nothing new since 2026-10-10. No wave assignment, no promotion, no halt in `fleet/`; the only wave/freeze/canary machinery in the repo is the box-layer G15/G18 lane. S2 (#1285) is the build slice — its ship gate (S3's D-RC-2 pick) is now **cleared**. |
| The template version is a verifiable thing, not a free-form operator string | **SHIPPED (S3, #1286 / PR #1303):** `fleet/plane_inventory.py` `release`/`release-show`/`releases` — each template version pins exactly one `(deployment_id, worker_sha256)`; re-release fails closed even with an identical artifact ("mint a new template version to change the pin" — verified in the tree at `fc1614f6`: `release` exit 0, re-release exit 2, `release-show` fail-closed on unknown templates). Releases ride the same snapshot + journal-as-truth divergence discipline as the planes snapshot. D-RC-2 picked option (b): the controller consumes the out-of-repo pinned manifest, not an in-repo worker source. |
| A bad template rolls back per plane | **Schema shipped, writer not built.** S3 added per-plane `last_known_good` (schema `plane-inventory-record/2`; `None` until the S2 promotion step writes it; `deploy`/`retire` preserve it, `/1`-era records normalize to it). The writer is pinned, not executed: the S2 promotion step writes the pin on healthy wave landing (F-RC-6) — the pin is superseded-only, never cleared. No plane can roll back yet. |
| A per-plane deploy record answers "which artifact landed on this plane" | **Not yet.** `deploy` records `{template_version, status, observed_at, reporter}` per plane — the artifact identity lives only in the release record. S4's driver must join them (per its scope: "record the deployment id + SHA-256 of the deployed bytes per the deploy contract's existing record discipline"). Until then, a plane record can name a template but cannot identify the bytes. |
| The operator can answer "what % of the fleet of planes is on template X?" | SHIPPED: S1's `census`/`stale` — unchanged. `stale --expected V` keys on `template_version` alone (see F-RC-9). |
| Update attempts are visible in one place for the plane layer | Nothing. No plane-layer event journal exists (S5's scope). |
| The controller has hands | Nothing. No per-plane deploy driver in `fleet/` (F-RC-2; S4's scope). |
| The freeze has an enforcement point | Nothing (F-RC-3; S2's halt + S4's refusal are the design). |
| Per-plane provision/update cost is measured (the D-MT5 input) | Nothing feeds it (F-RC-7; the S4 driver is the pinned first writer per D-RC-6). |
| There are planes | Still N=0 (F-RC-8; the provisioning lane is build-in-progress). |

## 3. Closed since the 2026-10-10 analysis

- **F-RC-1 closed:** the D-RC-2 pick (b) shipped — template versions are
  content-addressed by `(deployment_id, worker_sha256)` in release
  records. The analysis's "the template artifact has no repo home"
  finding is answered by an out-of-repo pinned manifest, not a repo
  artifact. The release pin grammars are `\A...\Z`-anchored (no trailing
  junk accepted) — the round-1 QA/Engineering blockers on the S3 PR fixed
  the anchoring, `/1`-era record stamping, and missing-snapshot journal
  bypass *for the releases store*.
- **F-RC-6 schema closed:** `last_known_good` exists per plane
  (`plane-inventory-record/2`). The writer (S2's promotion step) and the
  reader (S4's rollback command) are both pinned and both unbuilt.
- The gap analysis's own **D-RC-2 entry was amended in place** by the S3
  turn (the "PICKED by S3 (#1286, 2026-10-11): (b)" paragraph), and the
  **fleet README** documents the releases subcommands. Those two are the
  only parts of the 2026-10-10 analysis that absorbed S3; the §2 table
  and "Honest summary" are superseded by §2 above.

## 4. What's stale in the previous analysis's issue bodies

- **#1285 (S2)** still says "BLOCKED on S3's D-RC-2 template-identity pick"
  and its dependency block reads "Blocked by: S3 (D-RC-2 template
  identity)". The block is **cleared** — S3 merged. Its acceptance ("a
  release record can be promoted canary → waves with `stale` gating")
  predates the two #1303 review advisories, which are now part of the
  build path (see below): the promotion write must validate the pin
  against the release record (no invented pins), and the pin's
  `recorded_at` needs an ISO-8601 grammar because S3 deliberately pins
  none (no writer existed in S3).
- **#1287 (S4)** is accurate but its scope now overlaps the carried
  advisory: refuse `last_known_good` pins with no matching release
  record, and read pins through fail-closed `release-show`.
- **#1288 (S5)** is accurate as written (operator-observed journal first,
  plane-signed health events as named later scope).
- **#1294** (p2, the G18 gate-freeze decision for the extra-inputs-forced
  deploy path) is still owed to the S2/S4 slices — it names the freeze
  enforcement question F-RC-3 left open and has no home yet.

## 5. New findings

- **F-RC-9 — S3 added a channel axis the convergence identity doesn't
  use.** Releases carry `channel` (default `stable`); plane records
  carry `channel`; `releases` can filter by channel. But the D-RC-2 pick
  and S1's `stale --expected V` key convergence on `template_version`
  alone. The S2 wave machine must decide whether a wave converges planes
  to a *template* or a *(template, channel)* pair — and whether
  `stale`'s "expected template" needs a channel parameter. Note the
  collision: S2's own scope promises an "expedited security channel"
  (compressed waves for security releases). That phrase now shares a
  name with the `channel` field on the record — S2 should say explicitly
  whether the expedited path rides the `channel` field or is a separate
  flag, before anyone ships a "security channel" that means two things.
- **F-RC-10 — The per-plane deploy record cannot identify the artifact.**
  `deploy` writes `{template_version, status, observed_at, reporter}` —
  the `(deployment_id, worker_sha256)` identity lives only in the
  release record. "What % of the fleet is on template X" works; "which
  bytes landed on plane #k" does not. S4's driver must write the join
  (its scope already says so); until then the inventory answers version
  strings, not deployments.
- **Build order vs issue numbers.** The analysis's ordering sentence —
  "what is a template version (S3), how does it reach a plane (S4), when
  may the next wave go (S2), and what did the waves report (S5)" — is
  the build order: **S4 → S2 → S5**. The issue numbers do not encode
  it (#1285 = S2, #1287 = S4, #1288 = S5). F-RC-2 is the reason: a wave
  state machine without the deploy driver is a spreadsheet — S2's
  acceptance can be exercised hermetically against the S1 store, but the
  first wave that *lands* needs S4's hands.
- **Carried advisories are now build-path constraints.** From the #1303
  adversarial review (Engineering/QA/Security, merged): (a) the S2
  promotion write must validate `last_known_good` fields against the
  release record and pin an ISO-8601 `recorded_at` grammar (comment
  6107294719 on #1285); (b) the S4 rollback must refuse pins with no
  matching release record and read through fail-closed `release-show`
  (comment 6107295238 on #1287). These are not new findings — they are
  recorded here so the next build turn treats them as acceptance, not
  footnotes.

## 6. Remaining gaps (all tracked, none filed this turn)

- **S4 — the hands (#1287, p2):** per-plane template deploy through the
  Cloudflare tooling, rollback from `last_known_good`, freeze/out-of-wave
  refusal per D-RC-5, cost-event emission per D-RC-6 (making the driver
  the D-MT5 ledger's first writer, F-RC-7). Next in build order.
- **S2 — the brain (#1285, p2):** wave assignment + `stale`-gated
  promotion per D-RC-4, halt, freeze refusal, expedited security channel,
  `last_known_good` promotion writes. Blocked-by S3 now cleared; F-RC-9
  (the channel axis) is S2's scope to answer.
- **S5 — the reporting (#1288, p2):** operator-observed event journal for
  plane update attempts; plane-signed health events as named later
  scope (with the G13/G17 forgery question answered for planes, not
  inherited by analogy).
- **Still true:** F-RC-2 (no driver), F-RC-3 (freeze enforcement point),
  F-RC-4 (promotion trust — operator-observed only), F-RC-5 (tenant
  consent in wave assignment), F-RC-7 (ledger writer), F-RC-8 (N=0).
- **Adjacent, already tracked:** #1302 (p3 — the missing-snapshot journal
  bypass class S3 fixed *on the releases store*, pre-existing on the
  planes store; kept out of the S3 slice); #1294 (p2 — the G18 gate-freeze
  decision owed to S2/S4).

## 7. Honest summary

S3 answered the first question the lane needed — what a template
version *is*: a pinned `(deployment_id, worker_sha256)` pair, not a
free-form string — and gave planes a `last_known_good` schema to grow
into. Everything else the 2026-10-10 analysis named is still true:
nothing can deploy a template to a plane, nothing assigns waves, the
freeze has no enforcement point, and the cost ledger has no writer. The
S2 ship gate is cleared, and the build order is S4 → S2 → S5. The next
slice the lane needs is the hands: #1287.
