# Relay-liveness remaining-builds gap analysis (R2/R3/R4)

**SUPERSEDED 2026-10-16 (docs truth repair):** the state claims below
were verified at the 2026-10-13 pin (`db71df38`) and are now stale —
R2a shipped (PR #1512, issue #1414 closed), R2b shipped (PR #1535,
issue #1415 closed), R3 shipped (PR #1562, issue #1416 closed), and
R4 shipped (PR #1582, issue #1417 closed). The R2 decomposition and
decisions D-RL2-1–D-RL2-7 stand as written; current lane state lives
in `docs/RELAY_LIVENESS_R3R4_HANDOFF_2026-10-15.md`.

Vision-vs-state of the #486 relay-liveness lane, pinned to main `db71df38`
(2026-10-13). The lane's design (`docs/RELAY_LIVENESS_DESIGN.md`, shipped as
PR #485) named four build slices (R1–R4). R1 shipped in-repo; R2/R3/R4 have
no code, no owning issues, and no build-path analysis until this doc. This
analysis decomposes the three remaining slices into slot-sized builds,
re-verifies the lane's dependencies, and settles the design's §9 open
questions that have answers.

## 1. State table

| Slice | Vision (design §8 + #486) | State at `db71df38` |
|---|---|---|
| R1 — session journal (passive) | Relay daemon emits §2 frames to a bounded journal + `relay_session_liveness(vm_id)` query | **Shipped** — `hosted/relay_liveness.py` (522 lines) + `hosted/test_relay_liveness.py`; prober-exclusion enforced journal-side; #1082 lock-bound; `RELAY_SESSION_JOURNAL` is a first-boot /data env-interface entry (`docs/DATA_VOLUME_CONTRACT.md` machine-env table) |
| R2 — dial prober (active) | Handshake-only prober, identity-marker discriminator, §3 outcome taxonomy, pinned-fingerprint verification, operator-visible `relay_path_state` surface | **Unbuilt** — no prober code; `relay_path_state` appears nowhere in Python (design-doc-only); the taxonomy table is doc-only |
| R3 — tenant-status wiring | Tenant layer consumes `relay_path_state`: transition rule 6 suspension + live-entry AND-combine | **Unbuilt** — `docs/TENANT_STATUS_ENDPOINT.md` §2 row names the instrument as the producer, but nothing reads it; the detector's relay conjunct is still dropped outright (§8 Q6 interim) |
| R4 — detector conjunct | `docs/STUCK_DETECTOR_DESIGN.md` §4 predicate gains the relay conjunct; closed-world on darkness; S2 calibration note | **Unbuilt** — the §8 Q6 interim text still stands: "R1–R4 unimplemented" |

Until the slices below ship, the instrument exists as a design plus one
channel: the detector's relay conjunct stays unobservable (closed-world),
the tenant layer keeps the placeholder behavior, and S3's automatic-`stuck`
gate stays unreachable on the relay row (G1's row is closed; the H4/H13 rows
are separate — §3 below).

## 2. Findings

- **F-RL2-1 — R2 is not one slice.** The design's R2 bundles three
  buildable units with a hard interface between them: (a) the probe
  mechanism (handshake-only SSH through the splice, taxonomy emission —
  testable against a fake listener), (b) the `relay_path_state` vocabulary
  mapping (ok/degraded/down + sub-code, §5), and (c) the cadence driver
  (when to probe, when to stand down). (a) is mechanism, (b)+(c) are the
  producer contract R3/R4 consume. The analysis splits R2a (mechanism, #1414)
  and R2b (contract + cadence, #1415); R2b ship-gates R3 and R4.
- **F-RL2-2 — the §5 mapping is consumer-contract-first.** `relay_path_state`
  is the interface R3/R4 build against. Pinning the mapping in code (not
  doc-only) before the consumers wire in is the lane's load-bearing order —
  the same boundary-before-consumer pattern the push lane used (#990's
  `enqueue_page` before the sender loop). R2b owns the pin; R3/R4 must not
  invent their own reading of `degraded`.
- **F-RL2-3 — Q1 (cadence) needs a shipped default, not a product decision.**
  The design deliberately leaves cadence as a product call (§7, §9 Q1), but
  R2b cannot ship without one. The stuck-detector's confirmation tick (5-min
  window + margin, detector §4) sets the detection-time budget any cadence
  must fit inside; a 5-minute default fits the budget and mirrors §2's "5
  minutes ... a real cadence-friendly number, not a product promise". Ship
  the default as tunable config; the product call stays open.
- **F-RL2-4 — R2's provider-state read is NOT driver-gated.** R2 must stand
  down when the provider says suspended/destroyed (§7), which reads the H4
  contract's `ProviderState` (`harness/provider_iface.py` L116 — SUSPENDED et
  al. are pinned). The contract is shipped; only the driver (#905) is
  pending. R2 builds against the interface and accepts with a fake driver —
  #905 is not a ship-gate for this lane.
- **F-RL2-5 — §9 Q2 is answered: liveness is per-box, suspension is
  per-tenant.** G7 (resolved 2026-09-26, endpoint §8) decided the 13-code
  vocabulary is per-tenant, with the live-anchor box anchoring `live`. The
  relay instrument reports per `vm_id`; R2b maps the live-anchor box's
  reading to tenant suspension, and non-anchor readings stay on the operator
  surface. No per-box tenant-status sibling is created (G7's duplication
  rule).
- **F-RL2-6 — R4's calibration half is docs, not detector code.** The
  design's §8 R4 includes an "S2-calibration note": the detector soak's
  confusion classes gain a "suspension while measuring" row so
  transition-rule-6 suspensions during calibration don't read as detector
  outcomes. That row is a doc update owned by R4, not a detector-team
  handoff — file it in the same slice or it rots as a "someone should".
- **F-RL2-7 — the H13 dependency is narrower than the design's dependency
  list suggests.** The stuck-detector §7 S3 lists four S3 dependencies (H4
  provider state, this design, H13 suspend contract, G1 terminal records).
  G1 is closed (#511/#546). Of the remaining two, only the detector's own
  `suspended_or_scheduled` conjunct needs the H13 suspend contract
  (research-only today: `docs/SUSPEND_WAKE_RESEARCH.md`). R2's stand-down
  reads the H4 *contract's* suspended/destroyed — satisfiable now (F-RL2-4).
  This lane's slices are not H13-gated; the H13 row stays open independently.
- **F-RL2-8 — R3 is runtime wiring only; the producer pointer is already
  set.** The design turn set the endpoint §2 row's producer pointer. R3's
  risk is the latch semantics (record arc-advancing events against the
  latch, re-evaluate on recovery — never a blind stack-pop), not discovery.

## 3. Decisions

- **D-RL2-1 — build order: R2a → R2b → R3, R4.** R2b ship-gates R3/R4 (F-RL2-2,
  interim honesty: the endpoint never claims a producer it doesn't read).
  R3 and R4 are independent of each other once R2b ships and may run in
  either order; the analysis keeps them as separate slices because their
  consumers (tenant layer vs detector) differ.
- **D-RL2-2 — 5-minute probe cadence default**, tunable, explicitly not the
  Q1 product call (F-RL2-3).
- **D-RL2-3 — re-pin per session.** The prober reads the pinned fingerprint
  from the session's connection bundle and re-pins on session restart; it
  never carries a fingerprint across sessions (endpoint rule 7, design §9
  Q5). A prober config that names a fingerprint is rejected by review.
- **D-RL2-4 — `degraded` never fires transition rule 6.** The rule fires on
  `down` only; `degraded` is operator surface, and the stuck-detector
  conjunct evaluates it as unobservable (`insufficient-observability`),
  never assumed-`ok` (design §5/§6).
- **D-RL2-5 — no new status codes.** Every outcome routes to the existing
  13-code vocabulary; sub-codes (`relay` | `cert` | `box-leg`) ride `detail`
  (design §3/§7).
- **D-RL2-6 — live-anchor mapping for multi-box tenants** (F-RL2-5): the
  live-anchor box's reading drives tenant suspension; other boxes' readings
  are operator-surface only.
- **D-RL2-7 — the prober's own tests cover the marker shape.** R1 drops
  `prober`-marked frames before schema validation (journal-side, by design);
  a broken prober marker would journal silently-journaled nothing and fail
  loudly elsewhere — the module docstring already assigns this test duty to
  the prober's tests, not the journal's.

## 4. Slices (filed)

| Issue | Slice | Ship-gate |
|---|---|---|
| #1414 | R2a: dial prober core — handshake-only SSH through the relay splice, identity-marker discriminator, §3 outcome taxonomy, pinned-fingerprint verification, no-login rule, no tenant credential | — |
| #1415 | R2b: `relay_path_state` surface + cadence driver — ok/degraded/down + sub-code pin (F-RL2-2), 5-min default cadence, stand-down on provider suspended/destroyed, live-anchor mapping | R2a |
| #1416 | R3: tenant-status producer wiring — rule 6 suspension + live-entry AND-combine, latch semantics, sub-code in `detail` | R2b |
| #1417 | R4: stuck-detector relay conjunct observable + S2 calibration row; retires the §8 Q6 interim | R2b |

All p2 / track:hosted-product. #486 stays open until the four close; pointer
comment on #486 records the slice map.

## 5. What this analysis deliberately does not do

- **No relay HA design** — single daemon vs redundant pair with journal
  failover stays an operator/deployment decision (design §7); the bounded
  journal's rotation contract (R1) is what failover must preserve (design §9
  Q3 stays open).
- **No cadence product call** — the 5-minute default is a shipped placeholder
  with a budget, not the Q1 answer (F-RL2-3).
- **No H13 contract** — the suspend contract is research-only; this lane
  doesn't need it (F-RL2-7).
