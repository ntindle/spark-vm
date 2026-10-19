# Relay-liveness auto-cadence driver gap analysis

Vision-vs-state of the #1711 remainder, pinned to main `94cd024a`
(2026-10-18). The R3 wiring (`hosted/relay_tenant_wiring.py`, shipped
PR #1562, issue #1416 closed) is complete and tested — but the arch
deep-read that filed #1711 found it inert in production: nothing ever
called `drive_tenant`. Slot 20261018-1529 shipped #1711's acceptance
option 2 (operator-driven `--tick` CLI, PR #1717, drive decision
D-RL34-7) and left the auto cadence driver tracked on the issue. This
doc is the design the driver slice builds against: what "automatic"
means here, the decisions already pinned by the lane, and the ones the
build must still make.

## 1. State table

| Piece | Vision | State at `94cd024a` |
|---|---|---|
| Probe cadence (instrument) | `maybe_probe` / `cadence_decision` every 5 min (D-RL2-2 default, tunable), stand-down on suspended/destroyed + no post-`live` arc | **Shipped** — `hosted/relay_path_state.py` (R2b, PR #1535); the cadence is a *decision function*, not a loop |
| Wiring tick | `drive_tenant` consumes the freshest `relay_path_state` reading, plans + applies rule-6/recovery events | **Shipped** — `hosted/relay_tenant_wiring.py` + `--tick TENANT_ID` CLI (D-RL34-7, PR #1717); driven today only by an explicit operator action |
| Auto cadence driver | Something ticks `drive_tenant` on the probe cadence in production, observably, with the single-driver discipline honored | **Unbuilt** — the module docstring is explicit: "No auto cadence driver exists in production" (`relay_tenant_wiring.py:100`) |

The lane reads "fully built" for the wiring while its production half
is a CLI waiting for a human. The gap is not capability — it is
cadence: rule-6 suspensions, the recovery pair, and the stale-`False`
resync only run when an operator remembers to tick.

## 2. Findings

- **F-AC-1 — Two clocks, no rendezvous.** The instrument cadence (probe
  every 5 min, D-RL2-2) and the wiring-tick cadence are independent:
  nothing relates them. The wiring consumes the *freshest* reading, so
  a `down` can sit un-acted-on for up to a full tick interval after the
  probe observes it. Worst-case rule-6 entry latency = probe interval +
  tick interval + read-phase blocking (the probe-history lock waits up
  to 60s, the session-journal lock up to `journal_timeout_s`). The
  stuck-detector's confirmation budget (F-RL2-3: 5-min window + margin)
  constrains the *instrument*; the wiring tick adds a second interval
  on top of it. An auto driver that ticks at a different cadence than
  the probe re-introduces the rendezvous problem the 5-min default was
  meant to kill.
- **F-AC-2 — Bundle supply on the auto path.** D-RL2-3
  (`relay_path_state.py:53`): probe bundles (relay host/port + pinned
  fingerprint) are caller-supplied per probe, never persisted — the
  `--probe-now` CLI reads the bundle from stdin JSON
  (`relay_path_state.py:780`). An auto driver faces a fork: (a)
  **drive-only** — consume existing probe history, in which case
  readings go stale whenever nothing probes (today nobody does, on any
  schedule); or (b) **probe-and-drive** — the driver also probes, which
  needs the bundle from somewhere (tenant record? session state?) plus
  the H4 provider-state stand-down read — i.e. the whole R2b mechanism
  moves onto the driver path. The lane deliberately kept probing and
  wiring separate; the driver must not smuggle them back together
  without a decision.
- **F-AC-3 — Single-driver discipline is documented, not locked.**
  D-RL34-3a (`relay_tenant_wiring.py:52,103-104`): "at most one tick
  per box at a time, whoever starts it" — documented, not locked. The
  good news, verified in the apply phase (`relay_tenant_wiring.py`
  :546-588): the apply re-selects the anchor from the FRESH record and
  re-plans under the store's inter-process `fcntl` exclusive lock
  (`tenant_status.py:968`), so two concurrent ticks *converge* — the
  second re-plans on the already-transitioned record and emits nothing
  observable (the re-plan reduces to an idempotent boolean flip —
  `("relay-down", {})` on an already-suspended arc flips
  `relay_reachable` to the `False` it already holds; the recovery
  pair's guard and the boolean-flip idempotency make the re-plan a
  no-op). The residual is not corruption but waste: two
  drivers (hosted cron + an operator's manual `--tick`, or overlapping
  cron firings) each do full probe-history + journal reads, contend on
  the instrument locks (up to 60s waits each), and emit duplicate
  notes. An auto driver multiplies the double-tick probability from
  "operator error" to "schedule overlap" — the discipline needs a
  mechanism or an explicit overlap-safe design.
- **F-AC-4 — Tick reports have no audience.** The `--tick` CLI prints
  the `drive_tenant` report as JSON on stdout — observable only to
  whoever invoked it. An auto driver's ticks need a durable, queryable
  home: the fleet event journal (G17's consumer contract), the G18
  alert stack for anomalies, or at minimum a per-tenant last-tick
  watermark. Precedent: the D9 sweep's fail-visible gap semantics
  (D-25-3) — a silent driver is a driver that can be dead for a week
  unnoticed.
- **F-AC-5 — Death mode is #1711 again.** If the auto driver dies
  (cron trigger unregistered — the exact failure mode #1069 exists to
  kill — worker redeploy, lock wedged), the lane silently reverts to
  the inert state #1711 diagnosed. The driver slice must ship the
  staleness detector with the driver, not after it: per-tenant
  last-tick watermark + alert when no tick lands within 2× cadence.
  The tenant plane is per-tenant (D-MT1), so on the hosted path the
  watermark lives in the tenant plane's D1; on the self-hosted path it
  is a local sidecar next to the tenant store.
- **F-AC-6 — Placement follows the plane-cron template.**
  `deploy/plane-cron/CRON_TRIGGER_CONTRACT.md` already pins the
  hosted pattern this driver needs: the in-repo sync module is the
  test truth, the plane ships an async port (the F-PP-2 sync/async
  seam — same as the push lane's plane-port analysis, #1566), the
  trigger is declared in `wrangler.toml`, and `verify_plane_cron.py`
  asserts the registered set. The per-minute trigger exists; the
  driver adds its own cron line. Self-hosted needs no new mechanism:
  the `--tick` CLI was designed as "a human, a cron entry, or a
  supervisor loop" (D-RL34-7) — the packaging slice is a cron/systemd
  unit + docs, both-supported by construction.
- **F-AC-7 — "Anchor moved" skips must not feed the watermark.** The
  apply phase skips a tick whose read-phase anchor is no longer the
  anchor (`relay_tenant_wiring.py:576-586`) and converges on the next
  tick. A skip is healthy convergence, not driving — but a tenant
  whose anchor moves every tick is also a signal. The watermark counts
  applied ticks; the staleness rule counts skips separately, and a
  skip storm is its own alert, not a green tick.

## 3. Decisions

- **D-AC-1 — One clock.** The drive cadence IS the probe cadence: the
  same 5-min default, the same `RELAY_PROBE_CADENCE_S` knob (F-AC-1).
  A tick that finds no new reading is a cheap no-op (re-plan on the
  fresh record emits nothing); the rendezvous problem disappears
  because there is only one schedule. This uses the shipped default —
  it does not decide the §9 Q1 product call.
- **D-AC-2 — Drive-only.** The probe cadence driver (R2b) owns probing;
  the wiring driver consumes (F-AC-2). If the probe history is older
  than 2× cadence at tick time, the tick notes it LOUD (fail-visible,
  F-AC-4) instead of probing itself. Revisit trigger: if drive-only
  proves operationally insufficient, the probe-and-drive fork re-opens
  as its own slice — it is not smuggled into the driver build.
  D-AC-2 depends on a probe-loop driver that does not exist at
  `94cd024a`: `maybe_probe`/`cadence_decision` is a decision function,
  not a loop, and `--probe-now` is one-shot. The probe loop (something
  calling `maybe_probe` with caller-supplied bundles on the
  `RELAY_PROBE_CADENCE_S` cadence, honoring the D-RL2-2 stand-down) is
  out of #1711's scope and is tracked on its own issue (#1725, S5);
  until it ships, S1's steady state is loud-stale ticks by design (the
  fail-visible forcing function), not a defect. S4's staleness rule
  distinguishes "driver dead" from "probe loop missing" via the
  watermark's stale-probe notes.
- **D-AC-3 — Overlap-safe, not overlap-prevented.** Follow the D9
  sweep precedent (D66/D69): ticks are bounded and idempotent, and
  overlap is safe, not prevented (F-AC-3). No leader election, no
  per-box flock: the apply phase's re-select + re-plan under the
  inter-process store lock already makes concurrent ticks converge.
  The documented single-driver discipline (D-RL34-3a) stays a
  discipline for the *operator* path (don't run `--tick` in a tight
  loop against the auto driver); the schedule is the mechanism.
- **D-AC-4 — Observability is a watermark + journal, not stdout.**
  Every auto tick writes
  ``{tenant_id, tick_at, applied, skipped, events, stale_probe, failed,
  notes}`` to the per-tenant watermark and appends tick-note events to
  the fleet event journal (F-AC-4, F-AC-7). ``skipped`` counts
  anchor-moved convergence separately from driving (a skip is
  convergence, not driving); ``stale_probe``/``failed`` are the
  fail-visible flags S4's staleness rule reads. Staleness (> 2× cadence
  with no applied tick) raises a G18-style alert (F-AC-5). The
  `--tick` CLI stays the manual/override path — its stdout report is
  unchanged; the auto driver is the new default, not a replacement.
- **D-AC-5 — Placement per the plane-cron template.** In-repo sync
  driver module (the test truth, stdlib-only like the rest of the
  lane) + plane async port + `wrangler.toml` cron line + verifier
  entry (F-AC-6, F-PP-2). The self-hosted packaging (cron/systemd
  unit driving the existing `--tick` CLI) follows the same driver
  design — one design, two deployments, per the both-supported
  default — but ships as its own slice (S3, gated on S1). S1 must
  parameterize `drive_tenant` over a store protocol (read +
  read-modify-write, replacing the direct `store._mutate` private-method
  call — `drive_tenant` today takes a concrete `ts.TenantStore` whose
  `fcntl` file lock does not exist on Workers) so the S2 async port has
  a defined boundary to implement against the worker's async D1; the
  fcntl file lock stays the in-repo implementation of that boundary.
  D-PP-2-style conformance fixtures must replay the apply-phase
  convergence cases (concurrent-tick convergence, anchor-moved skip)
  through the port. The in-repo module remains the test truth; it never
  sees a Worker secret (D-PP-1).
- **D-AC-6 — Self-hosted watermark producer (S1 review, #1721).**
  F-AC-5 requires the per-tenant watermark on the self-hosted path as
  "a local sidecar next to the tenant store" — but the slice map's S3
  (#1723) drives the `--tick` CLI, which writes no watermarks, so
  self-hosted ticks would never produce them and S4's staleness rule
  would be silently hosted-plane-only, contradicting the both-supported
  default. Resolution (option A): S3's self-hosted packaging drives
  `tick_all_tenants` (the S1 module), not `--tick` — the watermark
  sidecar lands next to the tenant store exactly as F-AC-5 requires,
  and the journal notes go to the operator's fleet estate store dir.
  `--tick` stays the per-tenant manual primitive: human-invoked it is
  the override path; it is never the scheduled path. #1723's scope is
  amended accordingly (cron/systemd unit invoking the S1 module).
  Sequencing (F-AC-5 vs the slice map): S4's staleness rule must land
  no later than whichever slice first schedules the driver (S2 or S3)
  — a scheduled driver with no staleness detector re-creates the #1711
  death mode the detector exists to kill.

## 4. Slices (filed)

| Issue | Slice | Ship-gate |
|---|---|---|
| #1721 | S1: in-repo auto-driver module — tick-all-tenants loop on the probe cadence (D-AC-1), drive-only consumption with stale-probe loud notes (D-AC-2), watermark writes + journal tick notes (D-AC-4, F-AC-7), bounded + idempotent (D-AC-3); `drive_tenant` parameterized over a store protocol (read + read-modify-write) so the S2 port has a defined boundary, fcntl file lock as the in-repo implementation; tests against the real wiring with a fake producer | — |
| #1722 | S2: plane async port + `wrangler.toml` cron line + `verify_plane_cron.py` entry (D-AC-5, F-PP-2 seam); extends `deploy/plane-cron/CRON_TRIGGER_CONTRACT.md`; D-PP-2 conformance fixtures replay the apply-phase convergence cases through the port | S1 |
| #1723 | S3: self-hosted packaging — cron/systemd unit driving the `--tick` CLI + operator docs (D-AC-5) | S1 |
| #1724 | S4: staleness alert — G18 alert-stack rule on the watermark (> 2× cadence, no applied tick) + skip-storm signal (F-AC-5, F-AC-7); distinguishes "driver dead" from "probe loop missing" via the stale-probe notes | S1 |
| #1725 | S5: probe-loop driver — call `maybe_probe` with caller-supplied bundles on the `RELAY_PROBE_CADENCE_S` cadence, honoring the D-RL2-2 stand-down; pin the bundle source (D-RL2-3, no persisted bundle store) and the loop's own death-mode observability | — |

All track:hosted-product (the tenant plane is the hosted unit;
self-hosted gets the S3 packaging slice). #1711 stays open as the
tracker — pointer comment records this doc and the slice map; no
Closes keyword until the driver runs in production.

## 5. What this analysis deliberately does not do

- **No probe-and-drive design** — D-AC-2 keeps the driver
  drive-only; the bundle-supply fork (F-AC-2b) re-opens only on the
  revisit trigger, as its own slice.
- **No Q1 product call** — the 5-min default is the shipped
  placeholder (D-RL2-2); the product cadence decision stays open.
- **No tenant-plane D1 schema** — the watermark's exact columns are
  S1's call, reusing the push lane's D1-schema-contract discipline
  (#988's pattern), not this doc's.
