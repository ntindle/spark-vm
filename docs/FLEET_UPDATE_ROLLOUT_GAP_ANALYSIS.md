# Fleet update rollout — vision vs state (gap analysis, 2026-09-28)

The per-box updaters just landed: `deploy/auto-deploy.sh` (repo components,
per-box timer, pre-deploy gates, per-box rollback) and #532's toolset
self-updater (per-box pins, per-box systemd timer, S2 "never disrupts running
work"). Every box now knows how to update *itself*. Nothing knows how to
update the *fleet*.

This analysis covers the fleet layer only: staged rollout, fleet version
inventory, and update event reporting. It complements — and does not re-litigate —
§13's tenant-box update *policy* (G11–G14, #553–#556: in-place vs reimage,
trust model, tenant-visible state, suspend interplay), which decides *what* an
update is. This decides *how* an update reaches many boxes.

Scope note (both-supported default): the operator's own estate is already a
fleet (dev box, home machines, this VM's siblings). The rollout primitive
designed here is a repo component any self-hosted operator with N boxes can
run; the hosted product reuses the same controller for tenant fleets. The
per-box updaters stay the enforcement point — the fleet layer tells them
*when*, which requires a box-side hook neither updater has today (both are
autonomous timer loops: auto-deploy fires every 10 min, the toolset updater
weekly per design). G18 names that missing channel; without it the fleet
layer has no hands.

Gap-class legend (from `HOSTED_GAP_ANALYSIS.md`): `[BLOCKER]` nothing exists
and the vision cannot function without it; `[PARTIAL]` exists but incomplete
or wrong layer.

## Vision vs state

| Vision | Current state |
|---|---|
| A release rolls out to the fleet in stages: canary, then waves, each wave health-gated | Nothing. Every box updates on its own timer; a bad merge-to-main reaches the whole fleet within one timer period. Zero fleet/rollout/canary mentions in product code |
| A bad release is halted before it reaches the whole fleet; an emergency freeze stops all pending updates | No halt, no freeze. `auto-deploy.sh` rolls back *per box, after the fact* — correlated failure is repaired one box at a time. Worse: there is no channel for a halt/freeze to reach a box at all — both updaters are autonomous timer loops (auto-deploy every 10 min per `deploy/auto-deploy.timer`; toolset updater weekly per SELF_UPDATE.md S3), so a freeze that cannot propagate faster than the 10-minute tick is theater |
| The operator can answer "what % of the fleet is on build X?" | Per-box inventory exists (`self_update.py status --json` is machine-readable; auto-deploy keeps a per-box audit log) — nothing collects it. `status --json` has no consumer anywhere in the repo |
| Update attempts (started/deferred/succeeded/failed/rolled-back) are visible in one place | Per-box logs only. A failed fleet update is discovered on the next manual SSH session, not noticed |
| Tenant boxes report update state the tenant can see | Open: G12 (#554) — 12 tenant-status codes have no maintenance/updating code |

## Gaps

- **`[BLOCKER]` G15 — fleet rollout orchestration** (#606): no staged rollout,
  no canary, no waves, no soak, no promote/halt, no freeze switch. The
  correlated-failure blast radius of any bad release is the entire fleet.
  Needs: a rollout controller (repo component) that assigns boxes to waves,
  soaks the canary behind health gates, promotes or halts, and exposes a
  freeze switch. G16's inventory and G17's events are its eyes; G18's gating
  channel is its hands. Tradeoff the design must handle: staged rollout
  delays security patches to later waves — expedited waves for security
  releases are part of the design, not an afterthought.
- **`[PARTIAL]` G16 — fleet version inventory** (#607): per-box inventory
  exists, fleet-side aggregation does not. Without it, rollout waves cannot
  be observed and a bad release cannot be scoped ("how many boxes got the
  bad build before the halt?"). The image dimension depends on G11 (#553);
  the repo-component and toolset-pin dimensions are collectable today.
- **`[PARTIAL]` G17 — update event reporting** (#608): per-box outcomes go
  nowhere central. Events (what happened in the last window) complement
  G16's state (what is installed now); together they are the signal source
  for G15's health gates. Standard event shape → configurable sink (local
  JSONL first, control-plane endpoint when the hosted plane exists).
  Design constraint for tenant fleets: canary gates consume self-reported
  events, and G13's threat model is "a tenant Muse with shell on the box" —
  forged events could promote a bad release or halt a good one. Event
  authenticity / box-identity attestation is a requirement for the tenant
  instantiation (see G13, H11); the operator estate can start without it.
- **`[BLOCKER]` G18 — fleet→box release-gating channel** (#609): the
  mechanism by which wave assignment and release/freeze state *reach the
  box* and gate the per-box timers. Nothing exists — both updaters are
  autonomous loops with no external gate, and the only "freeze" anywhere is
  SELF_UPDATE.md's per-box, local, still-unbuilt "freeze on repeated
  failure" (S2). A wave assignment that never reaches the box is a
  spreadsheet. The design must state the propagation-latency bound (the gate
  must beat auto-deploy's 10-minute tick for a freeze to be meaningful) and
  pick the transport: boxes pull controller-published release state before
  each tick, the controller pushes/invokes updates, or the controller
  manages per-box timer enablement — each with different trust/transport
  implications for the both-supported story. Dependency order for the fleet
  layer: **G17 events + G18 gating → G16 inventory → G15 controller**
  (the controller needs eyes and hands before it can think).

## Deliberately not gaps

- **Tenant-box update policy** (G11–G14, §13): decided *what*; this is *how*.
  No overlap.
- **Per-box updater mechanics** (#532 slices, `auto-deploy.sh` gates): the
  enforcement half is built; this analysis assumes it.
- **Multi-tenancy** (H11): the rollout controller must respect whatever
  isolation story H11 picks (per-tenant waves are a natural fit), but the
  fleet layer is designable before H11 lands — waves work on box identity
  alone. Sequencing: the operator-estate instantiation needs only G15–G18;
  the tenant-fleet instantiation additionally waits on G13 (update
  authority) and H11 (isolation story).
- **Single-box operators**: with N=1 the per-box updaters suffice; the fleet
  layer only pays off at N>1. That is exactly the hosted product's shape.

## New backlog items filed by this analysis

- #606 — G15: fleet update rollout (staged waves, health-gated promotion, freeze)
- #607 — G16: fleet version inventory (aggregate per-box status)
- #608 — G17: update event reporting (standard shape, configurable sink)
- #609 — G18: fleet→box release-gating channel (how wave/freeze state reaches the box)

## Honest summary

The per-box updater chassis is in place: boxes update themselves safely and
never mid-job (S2's per-tool updaters and S3's acceptance are still pending —
the chassis, not the finished system). The fleet half does not exist: no
staging, no inventory, no events, no halt, and no channel for any of those
to reach a box. For one box that is fine; for the hosted vision — a fleet of
tenant boxes — a bad release currently has a blast radius of *everything,
within one timer period*, and no freeze can stop it because no freeze can
reach the boxes. G15/G16/G17/G18 are the four missing pieces, in dependency
order: events + gating → inventory → rollout controller.
