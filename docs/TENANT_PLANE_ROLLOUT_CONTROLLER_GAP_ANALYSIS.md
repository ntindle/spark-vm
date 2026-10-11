# Tenant-plane rollout controller — vision vs state (gap analysis, 2026-10-10)

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `8ac2f54` (2026-10-10 ~22:2x CDT).
Issue/PR numbers are GitHub references as of 2026-10-10 (not
code-verifiable from the tree). Honesty rules apply (`docs/POSITIONING.md`):
this describes current state and work to do, not promises. No controller
code ships in this analysis; nothing here deploys anything.

This analysis is the build-path pin for #1261's remaining scope: the
staged rollout controller itself. Slice 1 (S1) shipped 2026-10-10 as PR
#1284 (`fleet/plane_inventory.py` — per-tenant-plane version inventory +
the D-MT5 operational-cost ledger); this doc decomposes what S1 left
unbuilt. It files no change to S1.

**Non-overlap map (what this doc is not):**
- `docs/OPERATOR_PLANE_BUILD_PATH_GAP_ANALYSIS.md` — the parent analysis
  (2026-10-10, #1257): F-OP7/D-OP7 named the rollout controller as #1261's
  scope. This doc consumes that pin, it does not re-analyze the operator
  plane.
- `docs/FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md` (2026-09-28) — the box-layer
  fleet doc (G15–G18). D-OP7 keeps #1261 on the plane layer above it; the
  box rollout stays the per-box updaters' job. The box-layer primitives
  (wave assignment, health-gated promotion, freeze) are borrowed as
  concepts, not re-litigated as mechanics.
- `docs/ROLLOUT_CONTROLLER_DESIGN.md` — the box-layer controller design
  (G15 / #606): a rollout state machine for *boxes*. Its §1 primitives
  (wave assignment, health-gated promotion, freeze, expedited security
  channel, one answer) are the right vocabulary; §5's hands (the per-box
  updaters as the enforcement point) do not transfer — planes are
  request-driven Workers with no pull loop and no per-plane updater.
- `docs/RELEASE_GATE_CHANNEL_DESIGN.md` — the box freeze/gate channel
  (G18 / #609): a published signed `gate.json` the boxes pull before each
  timer tick. Planes pull nothing, so this mechanism has no plane analog;
  the plane freeze must live elsewhere (D-RC-5).
- `docs/MULTI_TENANT_PLANE_MODEL_DECISION.md` — D-MT1 (one plane per
  tenant), D-MT4 (operator plane), D-MT5 (the revisit trigger gated on
  *measured* per-plane operational cost). This doc consumes all three.
- `docs/PRODUCTION_DEPLOY_CONTRACT.md` — how the loop deploys the plane
  today: the deployed Worker code is **not in the spark-vm repo** (it lives
  in a separate non-version-controlled workspace directory), each deploy
  produces a Cloudflare deployment id, and rollback is redeploying the
  previous deployment id. This is the single-plane, operator-run reality
  the controller must grow out of.

## 1. The vision (#1261)

From the issue body (F-OP7/D-OP7's child):

- The rollout controller: staged rollout of the tenant-plane worker
  template across N tenant planes (canary → waves), per-plane version
  inventory, update event reporting.
- Interaction with the 2026-09-28 fleet doc: the box rollout stays the
  per-box updaters' job; this is the plane layer above it.
- The D-MT5 cost input: the controller records per-plane provision/update
  cost so the revisit trigger has a measurement, not an estimate.

Acceptance (#1261, verbatim): *a tenant-plane template change can roll out
across N planes in stages with inventory and rollback; per-plane
operational cost is measurable.*

## 2. Vision vs state

| Vision | Current state |
|---|---|
| A template change rolls out to N tenant planes in stages: canary, then waves, each wave health-gated | Nothing. S1's `fleet/plane_inventory.py` *references* "the rollout controller" as a future consumer of its `stale` pre-promotion gate (module docstring; `stale` help text) — the controller itself does not exist. No wave assignment, no promotion, no halt anywhere in `fleet/`; the only wave/freeze/canary machinery in `fleet/` is the box-layer G15/G18 lane (`gate_publish.py`, `gate_sync.sh`) |
| A bad template is halted before it reaches the whole fleet; an emergency freeze stops pending updates | No halt, no freeze, and — critically — no enforcement point for one. The box-layer freeze is a published `gate.json` pulled before each 10-minute updater tick (`RELEASE_GATE_CHANNEL_DESIGN.md`); planes are request-driven Workers that pull nothing, so a plane freeze cannot ride that channel. The only plane deploy path is operator-run (the production deploy contract), which no freeze can reach today |
| The operator can answer "what % of the fleet of planes is on template X?" | S1 shipped: `fleet/plane_inventory.py` (`register`/`deploy`/`retire`/`census`/`stale`) answers exactly this — operator-recorded, with the census-denominator honesty rule shared with the box inventory. The *producer* of the observations (the thing that deploys a wave and records it) does not exist; S1 is a ledger with no writer |
| Update attempts (started/deferred/succeeded/failed/rolled-back) are visible in one place for the plane layer | Per-plane, nowhere. The production deploy contract requires a deploy *record* (deployment id + SHA-256 of the deployed `worker.py` bytes) in the loop's run log — a record per deploy, not an event stream; and it covers the single `sparkvm-control` worker, not N tenant planes. No plane-layer event journal exists |
| A bad template rolls back per plane | No path. The deploy contract's rollback ("redeploy the previous deployment id") is single-plane and operator-run; the inventory records a plane's *current* template version, not the previous one, so "last known good" is not recoverable from the store. Rollback across waves is unowned |
| Per-plane provision/update cost is measured (the D-MT5 input) | S1 shipped the ledger (`cost` / `cost-summary`: provision vs update vs rollback events with duration and cost). The ledger has no writer: the only events it can record are the ones an operator types in by hand. The D-MT5 query reads a store that nothing feeds |

## 3. Findings

- **F-RC-1 — The template artifact has no repo home.** The controller's
  first dependency is a versioned thing to roll out, and it does not
  exist: `PRODUCTION_DEPLOY_CONTRACT.md` pins that the deployed Worker
  code lives *outside* the spark-vm repo in a non-version-controlled
  workspace directory. S1's `--template V` is a free-form operator string
  with no producer — any operator can record any string, and no string
  means anything verifiable. A controller cannot converge N planes to a
  template that has no identity. D-RC-2 requires the slice to pick the
  artifact home before wave code ships: the worker source moves into the
  repo (versioned by repo commit), or the controller consumes an out-of-repo
  pinned manifest (deployment id + SHA-256, the deploy contract's existing
  pin discipline) — but it cannot be both, and it cannot be neither.
- **F-RC-2 — The controller's hands don't exist.** The loop's plane deploy
  path is single-plane and operator-run (production deploy contract:
  gate → deploy → verify → record). Nothing can deploy template V to plane
  #k; nothing can deploy it to N planes. The wave state machine (S2) is
  useless without the per-plane deploy driver (S4) — this is the plane
  analog of the fleet doc's G18 dependency ("a wave assignment that never
  reaches the box is a spreadsheet"), except the plane has no pull loop to
  reach at all: the driver must *push* each plane's deploy through the
  Cloudflare tooling.
- **F-RC-3 — The freeze has no enforcement point.** On the box layer the
  freeze is a signed document the updater reads before each tick; on the
  plane layer the only thing that deploys planes will be the S4 driver.
  Therefore the freeze must be the driver refusing to deploy — and the
  controller refusing to advance. Both commands live in the same CLI (D-RC-5),
  so a freeze is a local operator action, not a propagated signal. The
  honest propagation bound is "the operator's next command," not the box
  layer's sub-10-minute guarantee; this doc says so explicitly rather than
  selling the box-layer story to the plane layer.
- **F-RC-4 — Health-gated promotion needs a signal the S1 discipline
  explicitly declines.** S1's docstring is unambiguous: "nothing
  plane-reported is trusted for ordering, because S1 is operator-recorded.
  A future slice may accept plane-signed heartbeats." The canary gate is
  exactly the place that needs plane-reported health — *did the deploy
  land, and is the plane healthy on the new template?* — so the controller
  design must make the trust call now: D-RC-4 makes it conservatively
  (operator-observed health only; plane-signed health events are the
  named later upgrade in S5), because a canary gate that trusts
  self-reported plane health inherits the G13/G17 forgery problem the
  fleet doc already litigated for boxes.
- **F-RC-5 — Wave assignment for planes carries tenant consent, not just
  blast radius.** The box controller assigns by `hash(box_id) mod buckets`;
  the same mechanical rule transfers to planes — but planes carry tenants
  (D-MT1: one plane per tenant; D-OP4: the three-record model). A canary
  wave containing a production tenant's plane is a consent problem, not a
  blast-radius problem. D-RC-3 pins the tenant-affinity rule: the canary
  wave holds only planes whose tenants are explicitly designated canary
  tenants; single-plane estates promote by explicit operator command with
  an audit record, never automatically.
- **F-RC-6 — No "last known good" is recoverable.** S1 records the current
  template per plane; the journal is append-only, so the previous template
  is technically recoverable by replay — but nothing records *which*
  previous template was the last healthy one, and the deploy contract's
  deployment-id rollback is single-plane. The S3 slice must add an
  explicit `last_known_good` pin per plane (superseded-only, never
  cleared) — and its *writer* is pinned here, not left to the slices:
  the S2 promotion step writes the pin when it promotes the next wave,
  because promotion *is* the certification that the landed wave was
  healthy per D-RC-4's gate ("written on healthy wave landing" is literal).
  The S4 slice's rollback command then redeploys the pin; S3 only owns the
  schema. Without the pin, "rollback" is an operator remembering a
  deployment id — which is what the contract has today.
- **F-RC-7 — The D-MT5 cost ledger has no writer.** S1's `cost` subcommand
  and `cost-summary` exist; nothing calls them. The only component that
  *knows* a provision/update/rollback happened, with its duration, is the
  thing that performed it — the S4 deploy driver. D-RC-6 makes the driver
  the ledger's first writer: every deploy/rollback appends a cost event.
  Missing cost events do not block promotion (the controller must stay
  operable for estates that don't meter), but `cost-summary` reports
  coverage so the D-MT5 query never mistakes an empty ledger for a cheap
  fleet.
- **F-RC-8 — N=0 is the current state.** Zero tenant planes are
  provisioned — the #851 provisioning lane (#905 driver, #906
  orchestrator, #907 plane-attested pairing, #908 caps) is the
  precondition and is still build-in-progress. The controller's first
  real fleet is N=1. The S2 slice must define the degenerate behavior
  (D-RC-3's explicit-command promotion for single-plane estates) rather
  than discovering it the first time an operator has exactly one tenant.

## 4. Decisions

- **D-RC-1 — The controller governs tenant-plane template convergence
  only.** Operator-plane self-updates stay operator-owned manual deploys
  under the production deploy contract. This prevents the controller
  growing into a second operator-plane updater and keeps the blast radius
  of a controller bug off the plane that hosts the controller's own
  operator (the both-supported note: on self-hosted estates the
  "operator" is the human; the controller is a repo CLI they run).
- **D-RC-2 — The template artifact gets a home before wave code ships.**
  Two options, one required: (a) the tenant-plane worker source moves into
  the spark-vm repo and the template version is the repo commit; (b) the
  controller consumes an out-of-repo pinned manifest (deployment id +
  SHA-256 per deploy, the deploy contract's existing pin discipline). The
  S3 slice picks one; S2's wave code is blocked on the pick. Not both —
  a controller that accepts two identity schemes for the same artifact
  inherits an ambiguity a freeze cannot resolve.
  **PICKED by S3 (#1286, 2026-10-11): (b).** The tenant-plane worker source
  lives outside the repo today (PRODUCTION_DEPLOY_CONTRACT pins the
  deployed Worker code to the operator's workspace); moving operator plane
  source into the public repo is a product/security decision this lane
  does not own, and the tenant planes themselves do not exist yet (N=0,
  the provisioning lane creates them) — an in-repo artifact home would be
  scaffolding around nothing. The manifest keeps S1's operator-recorded
  trust discipline intact: nothing plane-reported enters the pin, and the
  content address (SHA-256 of the deployed bytes) is a stronger
  convergence identity than a repo commit because it pins what IS
  deployed. Shipped: `release`/`release-show`/`releases` in
  `fleet/plane_inventory.py` (pin immutability — a template version binds
  exactly one (deployment_id, worker_sha256), re-release fails closed;
  releases snapshot + journal with the same divergence discipline as the
  planes snapshot), plus the per-plane `last_known_good` schema
  ({template_version, deployment_id, worker_sha256, recorded_at}, None
  until the S2 promotion step writes it; deploy/retire preserve it).
- **D-RC-3 — Wave assignment is deterministic plus tenant-aware.**
  Mechanical rule: `hash(plane_id) mod buckets` (the box controller's
  rule, transferred). Tenant rule: the canary wave holds only planes
  whose tenants are explicitly designated canary tenants; planes with no
  tenant designation sit out of the canary. Single-plane estates: no
  automatic canary — promotion is an explicit operator command with an
  audit record.
- **D-RC-4 — Promotion gates read operator-observed state only.**
  "Did the wave land" reads S1's `stale` (the inventory's operator-recorded
  observation). "Is the plane healthy on the new template" is
  operator-observed for now — a plane-signed health-event upgrade is S5's
  named scope, not S2's. The controller never trusts self-reported plane
  health for promotion in the shipped slices.
- **D-RC-5 — Freeze is a local refusal, honestly bounded.** The freeze
  state lives in the controller's store; the controller refuses promotion
  and the S4 deploy driver refuses out-of-wave deploys while frozen. Both
  are the same CLI, effective within one store dir (S1's `--store DIR`
  is per-invocation — a freeze set against one store dir does not bind
  a driver run against another; the operator's store dir IS the fleet
  scope). The documented propagation bound is "the operator's
  next command" — there is no pull loop to beat, so no sub-tick guarantee
  is claimed.
- **D-RC-6 — The deploy driver is the D-MT5 ledger's first writer.**
  Every deploy and rollback the driver performs appends a cost event
  (provision/update/rollback, duration, optional cost). Missing events do
  not block promotion; `cost-summary` reports event coverage alongside
  the totals so the D-MT5 revisit query stays honest about its inputs.

## 5. Deliberately not gaps

- **Operator-plane self-updates** (D-RC-1): manual, contract-governed,
  out of this lane.
- **Box-layer rollout mechanics** (G15–G18, #606–#609): the vocabulary is
  borrowed; the enforcement points do not transfer and are not
  re-litigated here.
- **The provisioning lane** (#851 → #905/#906/#907/#908): creates the
  planes the controller will roll out to; F-RC-8 records the dependency,
  the controller does not absorb it.
- **The envelope/session/account records** (#1258/#1259/#1260): the
  operator plane's own identity surface; the controller reads
  `plane_id`/`tenant_id` from the S1 store, it does not mint identity.

## 6. Gaps filed this turn

- **#1285 — S2 — Wave assignment + promotion state machine** (depends on S1,
  ship-gated on S3's D-RC-2 pick for version identity — the wave machine
  treats V as an opaque comparable token and is buildable against S1's
  string-equality `stale` today, but it must not ship waves under a
  version scheme S3 then throws away): canary → waves per
  D-RC-3, `stale`-gated promotion per D-RC-4, halt, freeze per D-RC-5,
  expedited security channel (compressed waves, never ungated — the G15
  tradeoff, transferred), all hermetic against the S1 store. The promotion
  step writes each landed plane's `last_known_good` pin (F-RC-6's writer).
  Freeze is refusal, not propagation.
- **#1286 — S3 — Template artifact + versioning + last-known-good schema**
  (D-RC-2's home decision; blocks S2's ship and S4's deploy target):
  the artifact-home pick, the release record (template identity →
  channel), and the per-plane `last_known_good` schema per F-RC-6
  (S3 owns the schema; the S2 promotion step is the pinned writer).
- **#1287 — S4 — Deploy driver + rollback + freeze refusal + cost emission**
  (depends on S3; the controller's hands per F-RC-2): per-plane template
  deploy through the Cloudflare tooling, the rollback command (redeploy
  the `last_known_good`), freeze/out-of-wave refusal per D-RC-5, and
  cost-event emission per D-RC-6.
- **#1288 — S5 — Plane update-event reporting** (operator-observed events as the
  wave-health signal per D-RC-4; the plane-signed health-event upgrade as
  named later scope): extends the S1 journal schema, never backfills
  `observed_at` (S1's collector-side discipline holds). Stage-1 event
  producers: the operator's own entry, or the S4 driver emitting them at
  the operator's command — either way operator-attributed, inheriting
  S1's operator-recorded discipline; nothing plane-self-reported enters
  the journal in the shipped slices.

## Honest summary

S1 shipped the ledger; nothing else in the controller lane exists. The
tenant-plane worker template has no versioned artifact (the deployed code
isn't even in the repo), no driver can deploy it to a plane, the freeze
has no enforcement point because planes pull nothing, health-gated
promotion needs a signal the S1 trust discipline explicitly declines, and
the D-MT5 cost ledger has no writer. The four slices above are ordered so
each answers the question the next one needs: what is a template version
(S3), how does it reach a plane (S4), when may the next wave go (S2),
and what did the waves report (S5).
