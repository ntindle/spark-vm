# Rollout-controller convergence, 2026-10-11: the #1261 tenant-plane lane

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `fc1614f6` (2026-10-11 ~04:5x CDT),
with a 2026-10-11 evening refresh (§8, verified against main `4f816a9`)
that re-pinned §2's state table after S4/S2/S5 shipped. Issue/PR numbers
are GitHub references as of 2026-10-11 (not
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
| A template change rolls out to N tenant planes in stages: canary, then waves, each wave health-gated | **SHIPPED 2026-10-11 (evening refresh):** S4's driver (`fleet/plane_deploy.py`, #1287 / PR #1330) performs the per-plane deploy; S2's wave machine (`fleet/plane_waves.py`, #1285 / PR #1344) assigns waves (D-RC-3 canary-tenant canary; deterministic otherwise), gates promotion on operator-observed state (D-RC-4, S2's `promote` consumes S5's event journal as bad-signal), halts on a bad wave signal, and answers F-RC-9's channel axis (D-RC-7: the security channel rides the release record's `channel` field). |
| The template version is a verifiable thing, not a free-form operator string | **SHIPPED (S3, #1286 / PR #1303):** `fleet/plane_inventory.py` `release`/`release-show`/`releases` — each template version pins exactly one `(deployment_id, worker_sha256)`; re-release fails closed even with an identical artifact ("mint a new template version to change the pin" — verified in the tree at `fc1614f6`: `release` exit 0, re-release exit 2, `release-show` fail-closed on unknown templates). Releases ride the same snapshot + journal-as-truth divergence discipline as the planes snapshot. D-RC-2 picked option (b): the controller consumes the out-of-repo pinned manifest, not an in-repo worker source. |
| A bad template rolls back per plane | **SHIPPED 2026-10-11 (S4):** `rollback` redeploys the plane's `last_known_good` pin (release-record verified, per the carried #1303 advisory); S2's promotion step writes the pin on healthy wave landing (pin shape validated at write time, per the carried #1303 advisory). |
| A per-plane deploy record answers "which artifact landed on this plane" | **SHIPPED 2026-10-11 (S4):** the deploy record now carries `(plane_id, deployment_id, worker_sha256)` plus the observed `worker_sha256_observed` (record schema `plane-inventory-record/3`) — "which bytes landed on plane #k" is answerable. F-RC-10 closed. |
| The operator can answer "what % of the fleet of planes is on template X?" | SHIPPED: S1's `census`/`stale` — unchanged. `stale --expected V` keys on `template_version` alone (see F-RC-9). |
| Update attempts are visible in one place for the plane layer | **SHIPPED 2026-10-11 (S5, #1288 / PR #1348):** operator-observed update-event journal (`<store>/plane_events.jsonl`, kinds deploy-started/landed/deferred/failed + rolled-back); the operator entry path, the S4 driver lifecycle emission, and the S1 `deploy` land emission are the three named producers; `plane-inventory events` is the read path; S2's `promote` consumes unresolved deploy-failed events as bad-signal (D-RC-4). Plane-signed health events stay named later scope (S5's written trust story). |
| The controller has hands | **SHIPPED 2026-10-11 (S4, #1287 / PR #1330):** per-plane deploy driver `fleet/plane_deploy.py` (F-RC-2 closed — deploys and rollbacks through the Cloudflare tooling behind a wired deployer). |
| The freeze has an enforcement point | **SHIPPED 2026-10-11 (S4 + S2):** the freeze lives in the controller's store (`<store>/freeze.json`, one definition shared by both); while frozen the driver refuses all deploys and rollbacks, and the wave machine refuses promotion and new rollouts (D-RC-5, honestly bounded — the propagation bound is the operator's next command). F-RC-3 answered. |
| Per-plane provision/update cost is measured (the D-MT5 input) | **SHIPPED 2026-10-11 (S4):** every deploy and rollback the driver performs appends a cost event (D-RC-6) — the driver is the D-MT5 ledger's first writer (F-RC-7 closed). Dry-run writes nothing and emits no cost event (the acceptance path at N=0). |
| There are planes | Still N=0 (F-RC-8; the provisioning lane is build-in-progress). The lane's accepted N=0 acceptance path is S4's `--dry-run`: it prints the deploy plan and exercises the full gate path (freeze, wave, pin) without touching the Cloudflare tooling. |

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

> **Superseded by §8** (2026-10-11 evening refresh — S4/S2/S5 have all
> shipped; the items below are historical).

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

> **Superseded by §8** (2026-10-11 evening refresh — S4/S2/S5 have all
> shipped; the summary below is historical).

S3 answered the first question the lane needed — what a template
version *is*: a pinned `(deployment_id, worker_sha256)` pair, not a
free-form string — and gave planes a `last_known_good` schema to grow
into. Everything else the 2026-10-10 analysis named is still true:
nothing can deploy a template to a plane, nothing assigns waves, the
freeze has no enforcement point, and the cost ledger has no writer. The
S2 ship gate is cleared, and the build order is S4 → S2 → S5. The next
slice the lane needs is the hands: #1287.

## 8. 2026-10-11 evening refresh — the #1261 Stage-1 build path is complete

Movement since the ~04:5x pin (verified against main `4f816a9`, the
tree at this turn's branch point):

- **S4 — the hands (#1287) SHIPPED 2026-10-11 13:12 CDT** (PR #1330, merged
  `8f366540`): `fleet/plane_deploy.py` — per-plane deploy + `rollback`
  (redeploys the `last_known_good` pin, release-record verified, per the
  carried #1303 advisory), D-RC-5 freeze refusal (shared
  `<store>/freeze.json`), D-RC-6 cost-event emission (the D-MT5
  ledger's first writer), dry-run acceptance path at N=0, and the
  F-RC-10 join — deploy records carry
  `(plane_id, deployment_id, worker_sha256)` +
  `worker_sha256_observed` (record schema `plane-inventory-record/3`).
- **S2 — the brain (#1285) SHIPPED 2026-10-11 21:20 CDT** (PR #1344, merged
  `45adc7de`): `fleet/plane_waves.py` — wave assignment (D-RC-3
  canary-tenant canary, F-RC-5 answered), `stale`-gated promotion
  (D-RC-4 — operator-observed state only, consuming S5's event journal
  as bad-signal), halt on bad wave signal, freeze refusal, D-RC-7
  (F-RC-9 answered: the security channel rides the release record's
  `channel` field), and the `last_known_good` promotion write with the
  pin validated at write time (per the carried #1303 advisory).
- **S5 — the reporting (#1288) SHIPPED 2026-10-11 22:26 CDT** (PR #1348,
  merged `fa0fd28b`): the operator-observed update-event journal with
  the three named producers, the `events` read path, and the S2
  promote bad-signal gate. Plane-signed health events remain named
  later scope (the written trust story, no code).

The #1261 lane's full build path is now shipped: S1 (inventory/census,
#1284), S3 (releases/pins, #1303), S4 (driver, #1330), S2 (waves,
#1344), S5 (events, #1348). **#1261 stays OPEN** as the vision
tracker; its acceptance reads as met on the Stage-1 scope
(operator-observed everything).

Findings disposition: F-RC-2 (hands), F-RC-3 (freeze enforcement),
F-RC-5 (tenant consent), F-RC-7 (ledger writer), F-RC-8 (N=0 —
dry-run acceptance path), F-RC-9 (channel axis — D-RC-7), F-RC-10
(deploy-record artifact identity) are all closed. F-RC-4 (promotion
trust — operator-observed only) stands as the settled design, not a
gap: D-RC-4 pins operator-observed-only gates, and plane-signed health
is S5's named later scope. The two carried #1303 advisories were
honored in the shipped code (verified in the tree): promotion-write
pin validation (`fleet/plane_waves.py`, advisory #1285/6107294719)
and rollback-target trust (`fleet/plane_deploy.py`, advisory
#1287/6107295238). §4's issue-body staleness notes are moot —
#1285/#1287/#1288 are all closed, and the #1294 bullet is retired by
#1316's 2026-10-11 fix (see the disposition below).

§2's state table is re-pinned to the post-S5 state; §6 ("Remaining
gaps") and §7 ("Honest summary") are superseded by this refresh.
Disposition of the pre-refresh tracked items: #1294 (p2 — the G18
gate-freeze decision owed by S2/S4) closed completed 2026-10-11
07:19 CDT via #1316 ("gate-guard the extra-inputs forced deploy") —
the owed decision landed, before this refresh. Remaining tracked
items: the p3 lane follow-ups #1342, #1343, #1346.
