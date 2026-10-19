# Fleet update-rollout lane — vision vs state (convergence pin, 2026-10-19)

Pinned to main `021bf92e` (2026-10-19). This document converges the
2026-09-28 `FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md` vision — as reframed by
the D-MT pivot (#1261) — against what the rollout-controller lane has
shipped since. It is the answer to the two open lane trackers: the vision
issue **#1261** and the design question **#1292**.

## Vision lineage

The September vision designed fleet rollout for *boxes* (G15–G18). #1261
recorded the pivot: fleet rollout for boxes was the wrong layer — the
hosted product rolls out *tenant planes*, so the rollout controller targets
tenant-plane template changes across N planes, with the box-layer
updaters staying the enforcement point. #1261's acceptance:

> a tenant-plane template change can roll out across N planes in stages
> with inventory and rollback; per-plane operational cost is measurable.

The D-MT5 revisit trigger was explicitly gated on *measured*
per-tenant-plane operational cost — "nothing measures it because nothing
rolls out tenant-plane updates."

## What shipped (the lane's build ledger)

| Slice | Shipped as | Evidence |
|---|---|---|
| S1 per-plane version inventory + D-MT5 cost ledger | `8ac2f549` (#1284) | `fleet/plane_inventory.py`: `census`, cost events, `cost-summary` |
| S3 template artifact + versioning + last-known-good | `fc1614f6` (#1303) | release records pinned, immutable pins |
| S2 wave assignment + promotion | `45adc7de` (#1344, #1285) | `fleet/plane_waves.py`: `assign`, `promote`, `halt`, `status`; D-RC-4 gate, D-RC-5 freeze, D-RC-7 expedited security waves |
| S4 deploy driver + rollback | `8f366540` (#1330, #1287) | `fleet/plane_deploy.py`: `deploy`, `rollback` (redeploys the plane's `last_known_good` pin), `freeze` |
| S5 update-event reporting | `fa0fd28b` (#1348, #1288) | `fleet/update_journal.py`; S5 folded into fleet status (`d5166209`) |
| Cross-component E2E | `ff2ece42` (#1628) | `fleet/test_plane_rollout_e2e.py`: full rollout, bad-signal refusal, rollback-to-pin |
| Hardening | #1342/#1343/#1346, #1627, #1636 | in-lock pin writes and wave assignment, freeze-mid-promote refusal, dry-run gate honesty, journal crash-completeness |

D-RC-6 closes the D-MT5 instrument gap the #1261 body named: every deploy
and rollback the S4 driver completes appends a cost event (update/rollback,
duration, optional cost) — the driver is the measurement instrument, so
the trigger's input is fed, not estimated. A push that fails closed
records a `deploy-failed` journal event but no cost event, and dry-runs
record nothing: failed rollouts' cost stays unmeasured, the honest bound
of the trigger's input.

## #1261 acceptance — re-verified leg by leg

- **Roll out in stages:** `assign` computes wave assignments (canary →
  waves, D-RC-1), `promote` advances the live wave behind the D-RC-4 gate,
  `halt` stops on a bad wave signal; security releases ride compressed
  waves (D-RC-7).
- **Inventory:** `census` answers "what % of the estate is on build X?"
  (eligible planes only; exclusions listed with reasons).
- **Rollback:** `rollback` redeploys the plane's `last_known_good` pin; a
  rollback target without a pinned manifest fails closed.
- **Per-plane operational cost measurable:** cost ledger (S1) +
  driver-appended events (D-RC-6) + `cost-summary` — for *completed*
  deploys/rollbacks only; a failed push records a `deploy-failed`
  journal event but no cost event, and dry-runs record nothing, so the
  ledger measures completed work, not burned attempts.

The acceptance is met at the instrument level and E2E-verified
(`test_plane_rollout_e2e.py`). **Honest residual:** no live tenant-plane
rollout has exercised it — tenant planes are the hosted instantiation,
not yet live — so the D-MT5 trigger's first *real* input arrives with the
first live rollout, not before. That is an operational milestone, not a
build slice; it does not keep #1261 open.

**Decision D-FC-1:** #1261 closes with this convergence pin. The lane's
remaining open items are the box-estate remainders (#1630, #1632, #1633
— owned by the 2026-10-17 `GATE_CHANNEL_ROLLOUT_GAP_ANALYSIS.md`;
#1649 — filed by `docs/ROLLOUT_ALERT_STACK_GAP_2026-10-17.md`, split
#1634 hosted), which never belonged to this vision.

## #1292 — design question answered: keep the current behavior

#1292 observed that `stale --expected V` lists retired planes in
`not_converged` (exit 1), asking whether that is the intended
pre-promotion gate contract.

**The issue's premise is stale.** S2 (#1285) shipped its *own* promotion
gate — `_wave_gate` (`fleet/plane_waves.py`, D-RC-4) — and `promote`
never consumed `cmd_stale`. The two gates treat retired planes
differently, and both are correct for their job:

- `cmd_stale` is an **estate-wide convergence report**: retirements stay
  operator-visible there by design (the operator guide documents it).
- `_wave_gate` is the **promotion gate**: a retired plane *assigned to the
  live wave* fails closed ("reassign the rollout — the controller never
  promotes into retired planes"); store-wide retired planes are invisible
  to it, so a churned estate still promotes.

**Decision D-FC-2:** option (a) — keep the current behavior, no code
change. The operator guide's prose ("The rollout controller reads this
before promoting a wave — 1 means do not promote") overclaimed `stale`'s
role; this turn corrects the guide to name the D-RC-4 gate as the
promotion gate and `stale` as the estate report where retirements stay
visible by design. #1292 closes on this decision.

## The plane layer's G18 answer (pinned, not a gap)

The September analysis demanded a fleet→box release-gating channel. At the
plane layer the answer is D-RC-5: freeze is a local refusal with the
honestly bounded propagation of "the operator's next command" — planes
pull nothing, so no sub-tick guarantee is claimed. The transport design
(G18) stays box-lane; the plane layer does not pretend to have a channel
it never built.

## Residuals — explicitly not this turn's gaps

- Box-estate wave assignment + operator tooling: #1630, #1632, #1633
  (fresh owners in the 2026-10-17 gate-channel analysis), #1649 (filed
  by the 2026-10-17 rollout-alert-stack analysis); #1634
  (hosted S3). Untouched here.
- #1557 remains the post-#777 remainders tracker.
- First live tenant-plane rollout (the D-MT5 trigger's first real
  measurement) is an operational milestone on the hosted side.

## New backlog items filed by this analysis

None. The lane converged; the two open lane trackers close on decisions
D-FC-1 and D-FC-2, and the residuals have owners. One docs correction
ships alongside: the operator-guide `stale`/`retire` prose now names the
real promotion gate.
