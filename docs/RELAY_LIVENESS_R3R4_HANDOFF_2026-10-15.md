# Relay-liveness R3/R4 handoff convergence (2026-10-15, #486)

## Addendum (2026-10-16): R4 shipped — the stuck detector gains the conjunct

R4 landed the same morning as R3's wiring verification: the §4
predicate of `docs/STUCK_DETECTOR_DESIGN.md` carries the relay conjunct
(`relay_path_state(S) == ok`), the §8 Q6 "relay conjunct dropped
outright" interim is retired, and the calibration soak's confusion
classes gain the "suspension while measuring" row — PR #1582, issue
#1417 **closed**. The relay row of the detector's S3 gate is closed
(instrument shipped R2b, wired R3, conjunct observable); H4 provider
state, H13 suspend contract, and G1 terminal records remain the S3
gate's unshipped dependencies. F-RL34-7 is consumed.

The relay-liveness lane is now fully built: the instrument touches the
tenant layer for `down` readings (R3) AND the stuck detector for the
`ok`/`degraded` conjunct (R4). As of this addendum, nothing in the R1–R4
decomposition remains open.

## Addendum (2026-10-16): R3 shipped — this doc's R3 rows are stale in-place below

R3 landed the morning after this pin: `hosted/relay_tenant_wiring.py`
(572 lines) + `hosted/test_relay_tenant_wiring.py` (728 lines), PR
#1562 squash-merged `e3f8c6d1`; issue #1416 **closed**. The three build
constraints this doc recorded (F-RL34-2–F-RL34-4) are consumed:

- **Anchor selection (F-RL34-2):** `select_live_anchor` — the earliest-created
  among live-reached candidates (earliest `created_at` as the stable
  proxy for first-to-live); an active rule-6 suspension keeps the anchor until
  its suspension exits (suspended-anchor stickiness; no orphaned
  recovery pairs).
- **Nested-suspension emit rule (F-RL34-3):** `drive_box` is the per-box
  single ordered emitter; the `relay-down` boolean flip fires only on codes
  where rule-6 entry does not apply (not just latch-holding states) — never
  `relay-failure`. A nested `down` whose
  sub-code differs from the headline `detail` is noted LOUD in
  `plan_events` (both legs named).
- **Recovery protocol (F-RL34-4):** `relay-reachable` before
  `relay-recovered` from the single ordered emitter, with stateless
  re-drive (next `ok` reading re-drives the pair) and stale-`False`
  resync. Crash-between-events interleaving is safe (pre-tick whole-tick
  loss is re-driven; `plan_events` is pure).
- **F-RL34-5 / D-RL34-4** (sub-code in `detail`, `down`-only): held in the
  wiring — a `down` reading with a missing/foreign sub-code is treated
  as a broken producer: rule 6 still fires on the `down` evidence, but
  the wiring passes no classification (the entry falls back to the
  tenant layer's unclassified default — no fabricated `detail`), and
  the anomaly rides the notes loud.
- **D-RL34-5** (cross-process lock gap, #1540 p3) is also done — fixed by PR
  #1546 (`f63eb8cb`, probe-history cross-process lock); issue closed.
  Not folded into R3, as decided.

Remaining after the R3 addendum was **R4** (#1417 — detector conjunct +
retirement of the `STUCK_DETECTOR_DESIGN.md` §8 Q6 "R1–R4 unimplemented"
clause per F-RL34-7); see the R4 addendum above — it is now shipped and
closed.

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `164d0f7` (2026-10-15; PR
#1539's merge). Issue/PR numbers are GitHub references as of
2026-10-15 (not code-verifiable from the tree). Honesty rules apply
(`docs/POSITIONING.md`): this describes current state and work to do,
not promises. As of the 2026-10-16 addendum the relay instrument is
wired to the tenant layer for `down` readings (R3); the R4 addendum above
retires the "does not touch the stuck detector" clause — the conjunct is
now in the detector's §4 predicate.

**Non-overlap map (what this doc is not):**
- `docs/RELAY_LIVENESS_DESIGN.md` — the lane's design (R1–R4, §5
  producer contract, §9 open questions). This doc consumes it; it does
  not re-decide it. One one-line reconciliation lands in this PR
  (F-RL34-5).
- `docs/RELAY_LIVENESS_REMAINING_BUILDS_GAP_ANALYSIS.md` (2026-10-13,
  pinned to `db71df38`) — the R2 decomposition (R2a/R2b) and the
  D-RL2-1–D-RL2-7 decisions. This doc **supersedes it for state**
  (R2a/R2b shipped at pin time; R3 and R4 shipped 2026-10-16 — see the
  2026-10-16 addenda); the decomposition and decisions stand and are
  not re-derived here.
- `docs/TENANT_STATUS_ENDPOINT.md` §2/§4/§7 — the tenant-layer
  contract R3 wires into (rule 6, live-entry AND-combine, #1463
  nested-suspension pins). This doc carries three R3 build constraints
  from it and the issue comments (F-RL34-2–F-RL34-4); it does not
  restate the endpoint.
- `docs/STUCK_DETECTOR_DESIGN.md` §8 Q6 — the R4 interim target. This
  doc verifies the interim is still current (it is, modulo one stale
  clause — F-RL34-7); R4 retires it.

## 1. What moved since the 10-13 pin

| Slice | 10-13 state (`db71df38`) | State at `164d0f7` |
|---|---|---|
| R2a — dial prober core (#1414) | Unbuilt | **Shipped** — `hosted/relay_dial_prober.py` + `hosted/test_relay_dial_prober.py`; PR #1512 merged `e7d63294`; issue #1414 closed |
| R2b — `relay_path_state` surface + cadence (#1415) | Unbuilt | **Shipped** — `hosted/relay_path_state.py` (726 lines) + `hosted/test_relay_path_state.py` (867); PR #1535 squash-merged `c2de261a`; issue #1415 closed |
| R2b hardening (#1536, #1537) | — | **Shipped** — PR #1538 squash-merged `a0d1f07`: probe bundles via stdin (argv exposure gone), probe-history store 0o700/0o600 + O_NOFOLLOW creation (#1537); issues closed |
| R3 — tenant-status wiring (#1416) | Unbuilt, ship-gated on R2b | **Shipped 2026-10-16** — `hosted/relay_tenant_wiring.py` + `hosted/test_relay_tenant_wiring.py`; PR #1562 squash-merged `e3f8c6d1`; issue #1416 closed (see the 2026-10-16 addendum) |
| R4 — detector conjunct (#1417) | Unbuilt, ship-gated on R2b | **Shipped 2026-10-16** — the §4 predicate carries the relay conjunct (`relay_path_state(S) == ok`); `down` readings route to `connection-unreachable` via transition rule 6 (never `stuck`); `degraded` reads as insufficient observability; §8 Q6's "relay conjunct dropped outright" interim retired; PR #1582 squash-merged `5d33e99f`; issue #1417 closed (see the 2026-10-16 R4 addendum) |

## 2. The R3/R4 consumer surface (shipped, verified at `164d0f7`)

R3 and R4 both build against one function:

```
hosted/relay_path_state.py::relay_path_state(vm_id, *, now=None,
        history=None, journal_timeout_s=None)
→ {"vm_id", "state", "sub_code", "reason", "probe", "journal"}
```

- `state` ∈ `ok | degraded | down`; `sub_code` ∈ `relay | cert |
  box-leg` on `down` only (degraded readings carry `None` — F-RL34-5).
- Flapping (last two liveness-bearing outcomes disagree, including on
  sub-code) reads `degraded` — suspect, never `down` (rule 6 cannot
  fire on a suspect reading).
- Never-probed and `provider_not_running` read `degraded` — the
  instrument never assumes `ok` from darkness, and provider state is
  never a liveness question.
- `probe` is the latest raw outcome; `journal` is the R1 passive
  reading (`active | idle | closed`, or None on darkness). A wedged
  journal lock raises `JournalLockError` through `relay_path_state`
  (a broken instrument, never darkness) — plane-facing callers pass a
  request-scoped `journal_timeout_s`.
- Cadence: `maybe_probe` / `cadence_decision` — 5-min default,
  tunable (param / `RELAY_PROBE_CADENCE_S`), stands down on
  `suspended`/`destroyed` and on no post-`live` arc
  (`has_post_live_arc` is the tenant layer's answer — the prober's job
  starts at `live`). Probe bundles are caller-supplied per probe,
  never persisted (D-RL2-3).
- Stdlib only — runs unchanged on the control plane.

**Probe-history store (the R2b state R3/R4 inherit):** JSONL,
outcomes + timing only (never fingerprints), 4 MiB + 2-rotations
bounded; creation-hardened 0o700 parent / 0o600 O_NOFOLLOW file
(#1537). **No cross-process lock** — the R1 session journal
(`relay_liveness.py`) takes an exclusive `flock` on a sidecar lock
(#1082); the probe-history store takes none. Two concurrent cadence
drivers for one box double-probe and interleave flapping memory.
(Stale as of 2026-10-16 — the cross-process lock shipped in PR #1546;
see the addendum.)
No data corruption (O_APPEND + corrupt-line skip), so the residual is
a p3 (filed this turn — §4).

## 3. Findings

- **F-RL34-1 — The 10-13 analysis's R2 half is superseded; the R3/R4
  half stands.** R2a/R2b shipped with the decomposition intact (R2b
  still the boundary-before-consumer pin: `relay_path_state` in code
  before the consumers wire in). R3 (#1416) and R4 (#1417) keep their
  issues; nothing about their vision changed — but three R3 build
  constraints postdate the analysis.

- **F-RL34-2 — Anchor selection falls between the slices.** #1415
  documents the policy (D-RL2-6: the live-anchor box's reading is the
  tenant-driving one; other boxes' readings stay operator-surface) but
  cannot select the anchor — no tenant-layer knowledge. #1416's slice
  row ("rule 6 + live-entry AND-combine + latch semantics") does not
  name anchor selection. The user's pointer comment (id 6204845321,
  on #1416) recommends the acceptance include "select the live-anchor
  box's reading as the tenant-driving one" so the mechanism does not
  fall between the slices — **not yet incorporated into the issue
  body.** This turn amends #1416's acceptance (provenance in §4).

- **F-RL34-3 — The #1463 nested-suspension constraint is an R3 build
  constraint.** `tenant_status.py`: `relay-failure` (the suspension-entry
  event) raises `TransitionError` in latch-holding states (`stuck`,
  `maintenance` — mutually exclusive per #1463); `relay-down` is the
  boolean flip (`_suspend_on_relay_down`: already-suspended /
  provisioning / terminal / `stuck` / `maintenance` → flip only).
  R3's wiring for outages discovered during latch-holding states
  **must emit `relay-down`, never `relay-failure`** — recorded on
  #1416 by the user's comment (id 6192069640) but absent from the
  issue body. Carried into the amended acceptance.

- **F-RL34-4 — The producer-disagreement question is pinned in code,
  not in #1416's scope.** `tenant_status.py`'s `relay-recovered`
  handler carries the pin: "a stale `relay_reachable=False` at
  recovery is a producer-disagreement question for the R3 wiring
  (#1416), not a demotion trigger." The tenant layer deliberately
  does not re-check the relay input at recovery (the instrument is
  authoritative for its own layer), which makes the R3 wiring's
  recovery-event protocol load-bearing: the order and pairing of the
  events it emits is what makes a stale `False` coherent or not.
  Carried into the amended acceptance as a named acceptance item.

- **F-RL34-5 — Design §5's sub-code language diverged from the shipped
  contract.** The design doc said "`degraded | down`, with the §3
  sub-code (`relay` | `cert` | `box-leg`) on non-`ok` readings" — which
  reads as sub-codes on every non-ok reading. The shipped R2b contract
  emits sub-codes on `down` only; `degraded` readings (flapping,
  never-probed, stand-down) carry `sub_code: None`. Fixed in this PR:
  the design doc now pins sub-codes as `down`-only (the §3 sub-code is
  a property of defect evidence; a suspect reading carries none).
  R3's "sub-code in `detail`" acceptance matches the fixed contract.

- **F-RL34-6 — Probe-history store has no cross-process lock**
  (§2). Single-driver is fine today; a second cadence driver for the
  same box double-probes and interleaves flapping memory. Filed as a
  p3 this turn (§4). Deliberately not folded into R3 — the R3 builder
  should not inherit a locking design question.

- **F-RL34-7 — The Q6 interim text is stale in one clause.** The
  closed-world interim rule in `docs/STUCK_DETECTOR_DESIGN.md`
  (§8 Q6) still says "R1–R4 unimplemented" — R2a/R2b are shipped.
  The interim's *behavior* (relay conjunct dropped outright,
  unobservable ⇒ no stall) is unchanged and still current; R4's
  acceptance already carries "Q6 interim text updated, not left
  stale", so no new issue. R4 fixes the clause when it retires the
  interim.
  **Retired 2026-10-16** — R4 (PR #1582) retired the §8 Q6 interim; the
  "R1–R4 unimplemented" clause is gone from the tree, so this finding
  is consumed (see the 2026-10-16 R4 addendum).

## 4. What this turn changed

1. This doc (the R3/R4 handoff pin).
2. `docs/RELAY_LIVENESS_DESIGN.md` §5 — the sub-code reconciliation
   (F-RL34-5): sub-codes on `down` readings only.
3. #1416's acceptance amended (issue body PATCH, provenance: the
   user's pointer comments 6192069640 / 6204845321, extended by the
   gap turn's Architecture review): adds the anchor selection item
   (F-RL34-2), the nested-suspension emit rule (F-RL34-3), and the
   recovery-event protocol item with its open delivery-semantics
   acceptance sub-items (F-RL34-4, D-RL34-3: single-ordered-emitter,
   idempotency contract, lost-event reconciliation). A pointer comment
   on #1416 records the amendment.
4. New p3 issue filed for the probe-history cross-process lock
   (F-RL34-6).
5. Pointer comment on #1417 (this doc; F-RL34-7 carried — no new
   issue).

## 5. Decisions

- **D-RL34-1** — The 10-13 remaining-builds analysis stays the record
  for the R2 decomposition; this doc is the R3/R4 handoff and
  supersedes the 10-13 doc's R2 state table only.
- **D-RL34-2** — Anchor selection stays in #1416's acceptance (per the
  user's pointer), not in a new issue. If the R3 builder finds the
  slice too big for one slot, they split with a pointer comment —
  the mechanism must not fall between the slices, whatever the split.
- **D-RL34-3** — The producer-disagreement question (F-RL34-4) is
  answered by the R3 wiring's event protocol, not by the tenant layer:
  ordering is pinned — the prober's recovery reading emits
  `relay-reachable` (boolean restore) *before* `relay-recovered`
  (suspension exit), in that order. Ordering alone is not the
  resolution: delivery semantics remain open and ride with #1416 as
  acceptance items — (a) a single-ordered-emitter requirement per box,
  or the protocol proved interleaving-safe (coupled to the F-RL34-6 p3
  — either serialize the wiring or make recovery pair atomically);
  (b) a per-event idempotency contract — the wiring never blind-retries
  `relay-recovered` (re-emit after a successful recovery raises
  `TransitionError`) or the handler tolerates the duplicate; (c) a
  lost-event reconciliation rule — a re-drive for a lost
  `relay-recovered` (a lost recovery wedges `connection-unreachable`
  indefinitely) and a resync rule for `relay_reachable` (a stale
  `False` poisons `_re_evaluate_latch_on_exit`'s exit-time backstop).
  Alternative protocols stay fine — what is not fine is leaving the
  case unhandled.
- **D-RL34-4** — R3's "sub-code in `detail`" means the detail carries
  the `down` reading's sub-code; `degraded` readings never produce
  suspensions, so there is no sub-code to carry (follows F-RL34-5).
- **D-RL34-5** — The lock gap (F-RL34-6) is p3 and out of R3's scope:
  no data-corruption path exists (O_APPEND + corrupt-line skip); the
  follow-up owns the design question (flock sidecar like #1082, or
  single-driver documentation).

## 6. Remaining builds after this turn

| Slice | Issue | State | This turn |
|---|---|---|---|
| R3 — tenant-status wiring (rule 6, live-entry AND-combine, latch) + anchor selection + nested-suspension emit rule + recovery protocol | #1416 | **Shipped + closed** (PR #1562, `e3f8c6d1`; see the 2026-10-16 addendum) |
| R4 — detector conjunct becomes observable + Q6 interim retirement + S2 calibration row | #1417 | **Shipped + closed** (PR #1582; see the 2026-10-16 addendum) | Conjunct added to the §4 predicate; Q6 interim retired; S2 "suspension while measuring" row added — docs-only slice |
| Probe-history cross-process lock | #1540 | **Shipped + closed** — PR #1546 merged `f63eb8cb`; see the 2026-10-16 addendum |

Out of scope (unchanged): G1's relay row is closed; H4/H13 rows are
separate lanes; the Q1 5-min-cadence product call stays open
(explicitly not decided here).

## Addendum (2026-10-18): the R3 wiring is operator/CLI-driven (#1711, acceptance option 2)

#1711 found the R3 wiring inert in production: nothing ever called
`drive_tenant`, and the cadence driver the module docstring promised
as a "future caller" was nobody's slice. The wiring now ships its own
production driver: a `--tick TENANT_ID` CLI on the wiring module that
runs one tick per tenant (human run, cron entry, or supervisor loop)
and prints the tick report as JSON. The drive posture is pinned in
the module docstring as **D-RL34-7**: the wiring never self-drives;
driving is an explicit operator action; the single-driver-per-box
discipline (D-RL34-3a) binds any driver. The stale "fully built"
lane-read is corrected: an auto cadence driver was explicitly NOT
built, and #1711 stays open to track it.

Out of scope (unchanged): G1's relay row is closed; H4/H13 rows are
separate lanes; the Q1 5-min-cadence product call stays open
(explicitly not decided here).
