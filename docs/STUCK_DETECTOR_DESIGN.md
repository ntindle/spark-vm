# Stall detector design (`stuck` — G9)

A design for mechanizing the tenant-status vocabulary's `stuck` code
(`docs/TENANT_STATUS_ENDPOINT.md` §2 and `docs/FIRST_TEN_MINUTES_SPEC.md`
§8). Today `stuck` is an operator-set placeholder; this doc designs the
real stall detector — what it measures, where it runs, what keeps it
honest, and the confidence gate it must pass before the code transitions
automatically. Until that gate passes, `stuck` stays operator-set and is
never exposed as automatic.

## 1. The rule being mechanized

`docs/FIRST_TEN_MINUTES_SPEC.md` §8 (failure taxonomy), verbatim:

> `stuck` — session abandonment per the pilot's rule: 30 minutes with no
> Muse action and no pending approval.

Three conjuncts — **(a)** no trusted Muse action for ≥ 30 minutes, **(b)**
no pending approval at the 30-minute mark, **(c)** the session is otherwise
live (not suspended, not unreachable, not already failed — (c) is this
design's operationalization of the taxonomy's other codes, not a third
clause of the spec's rule). All three must hold before the label fires.
The spec's other failure codes are *not* `stuck`; the detector must
actively distinguish them (§3 below), because a stall detector that cries
`stuck` at every quiet box is a funnel-poisoning instrument, not an
observability tool.

Why (b) exists: a Muse waiting 40 minutes on a human's answer is a *slow
trial*, never abandonment (spec §7's async-human rule: "A human who
answers in 30 minutes gets a slower trial"). Why (c) exists: an
unreachable or suspended box is a provider/relay defect
(`box-unhealthy`, `connection-unreachable`, provider `suspended`/`waking`
states) — labeling it `stuck` misattributes the defect to the agent and
corrupts the pilot's drop-off math.

## 2. Signal inventory

Everything the detector can read today, from `docs/USAGE_METERING_DESIGN.md`
§4–§5 and `docs/SENTINEL_TELEMETRY_SURFACES.md` findings:

| Signal | Source surface | What "quiet" means | Trust tier | Available today? |
|---|---|---|---|---|
| Muse action | muse-job JSONL (`job_heartbeat`, `job_started`, `job_ended` → metering mapper S3) | no heartbeat / no job events for N min | `cooperative` — **agent-forgeable**; usable for idle detection, excluded from anything that bills | box-local muse-job ships; the S3 mapper is a design until metering ships |
| Pending approval | confirmd pending state → `approval_filed`/`approval_decided`/`approval_expired` (mapper S1); also `GET /tenant/status`'s G3 contract | an undecided filing exists | control-plane-readable (confirmd is the box-side authority; the detector reads the record, not the Muse's claim) | confirmd ships; S1 mapper design only |
| Idle heartbeat | `meter_agent` `idle_heartbeat` every 60 s when idle | absence is not evidence of stall (the agent may be mid-heartbeat-window on a loaded box) — this signal is H13's, not the detector's; cross-check only | box-local privileged writer, narrow surface like the swap writers | design (ships with metering) |
| Provider state | H4 driver `box_state_transition` (`active`/`suspended`/`waking`/`destroyed`) | box not `active` → detector stands down | control-plane-observed | **unshipped** — no H4 driver PR exists; today the wall clock cannot distinguish suspended from idle |
| Relay session liveness | control-plane relay (SSH/session multiplexor) | session dead/never-established → `connection-unreachable` territory, not `stuck` | control-plane-observed | relay design only |

Two truths follow, and the design is built on both. First: **the
30-minute quiet clock runs on trusted signals only.** `cooperative`
signals — muse-job heartbeats *and* job events (the sentinel surfaces
doc: S3 is "cooperative telemetry (the agent can forge lines — `muse-job`
says so itself)", with forged event lines as a live threat model) — can
never extend the quiet clock. They feed a separate divergence evaluator:
cooperative claims of activity against stale trusted signals produce a
`telemetry-divergence` event (an observability/H5-sentinel concern),
never a suppression of the predicate and never a `stuck` on their own.
Second: **the detector reads only the control-plane-side shipped stream**
(§5) — box-local records become control-plane-observed facts by
*arrival* over the shipped channel, never by asking the box. A detector
that trusts the heartbeat alone lets a misbehaving agent suppress its own
stall detection; a detector that trusts nothing it cannot independently
observe refuses to emit — the closed-world rule (§4).

## 3. Distinguishing `stuck` from its neighbors

The detector evaluates the failure taxonomy *before* emitting, in this
order. The ordering below is the implementation order; the §4 predicate's
conjuncts are what enforce it (the ladder is a consequence of the
predicate, not a separate unenforced procedure):

0. **Telemetry path alive?** If the shipper is dead — no meter_agent
   `resource_window` arrival within 2 periods + batch margin — the session
   is `telemetry-gap`, not a stall candidate. Every downstream input is
   suspect when the observer is down (the metering doc's own #360/#376
   lessons are about exactly this failure class), and misattributing a
   dead shipper to the agent is the most operationally likely false
   positive in the whole design. The detector emits nothing; §4's
   closed-world rule applies.
1. **Provider/relay preconditions first — enforced by the §4 arc-scope
   conjunct.** Box not provisioned-live → `provisioning`/
   `provisioning-failed`. Relay session unreachable →
   `connection-unreachable`. Box failed smoke → `box-unhealthy`. Only
   sessions whose arc code is `live` are eligible at all; the detector
   does not run against these arcs.
2. **Pending approval?** If confirmd holds an undecided filing (or G1's
   terminal-record design, when it ships, shows a filing whose expiry has
   not yet been recorded) → the session is `waiting-on-approval`, *not*
   stuck — even past 30 minutes.
3. **Human delay?** A Muse whose last action was a summons/nudge (G4) or
   whose funnel arc shows a first filing awaiting a human (G4's observer,
   FIRST_APPROVAL_SUMMONS §6) is in the human's hands. `human-drop-off`
   (TTL expiry) and `human-denied` (engaged refusal) have their own codes
   and their own semantics — the arc gate (§4) and the
   `no_first_filing_reached_TTL` conjunct (interim, §8 Q3) make the
   never-relabel guarantee a predicate property, not a policy note.
4. **Policy/gate confusion?** Zero filings for a task that takes the gated
   action, or 2+ filings, is `policy-misfire` — the §6.7 gate owns
   detection, and its verdicts are authoritative for this step: if a gate
   evaluation is in flight when the predicate evaluates, the detector
   defers one tick rather than racing it (§4 `task_engaged` note). No
   gated action attempted at all is `no-gated-action` (discovery
   failure — the pilot's core signal). Neither is abandonment; the
   detector excludes sessions whose session log shows the pilot task was
   never engaged.
5. **Suspended is not stalled.** Suspend-on-idle (H13) makes "30 minutes,
   no Muse action" the product's *designed* idle state. A suspended box is
   never a stall — the §4 `NOT suspended_or_scheduled` conjunct does this
   work once H13's suspend contract ships; until then the conjunct is
   unobservable and the closed-world rule (§4) blocks emission. The
   12-code vocabulary has no `suspended` code (endpoint §4), so nothing
   in the taxonomy accidentally covers this case — the provider-state
   conjunct is the whole story.
6. **Only then, `stuck`.** The arc-scope conjunct (§4) is the hard gate:
   only sessions whose onboarding arc code is `live` are eligible at all —
   terminal arcs (`approved`, `human-drop-off`, `human-denied`) and
   non-`live` health codes (`box-unhealthy`, `connection-unreachable`,
   `provisioning-failed`) can never enter the predicate. The ladder above
   is evaluated before emitting, not instead of the gate. The result:
   30+ minutes of no trusted Muse action, no pending approval, live arc,
   live-and-reachable box, engaged task → stall.

Step 4 is the one that saves the pilot's math: abandonment-of-an-engaged
session and never-engaged discovery failure are different product
problems, and the detector is the place where the confusion would
otherwise harden into data.

## 4. The detection predicate (v1)

```
stall(session S) :=
    arc_code(S)                == live          (hard gate: transition rule 2
                                                licenses `stuck` ONLY from
                                                `live`; terminal arcs —
                                                `approved`, `human-drop-off`,
                                                `human-denied` — and non-`live`
                                                health codes can never enter)
AND shipper_alive(S)                         (last meter_agent
                                                `resource_window` arrival
                                                within 2 periods + batch
                                                margin — the independent
                                                disambiguator of "agent idle"
                                                vs "observer dead"; §3 step 0)
AND now - last_muse_action_trusted(S) >= 30 min
AND pending_approvals(S)       == 0            (confirmd — trusted daemon)
AND no_first_filing_reached_TTL(S)             (interim until G1's terminal
                                                record ships — §8 Q3)
AND provider_state(S)          == active        (control-plane-observed; H4 —
                                                unobservable pre-H4)
AND task_engaged(S)            == true          (a confirmd first-filing
                                                exists — the §6.7 gate owns
                                                `policy-misfire` detection
                                                and its verdicts are
                                                authoritative for §3 step 4:
                                                if a gate evaluation is in
                                                flight, the detector defers
                                                one tick rather than racing
                                                it; the phantom "first gated
                                                attempt" signal is dropped —
                                                it has no producer)
AND NOT suspended_or_scheduled(S)              (H13 suspend contract —
                                                unobservable pre-H13)
```

**Closed-world interim rule.** Every conjunct must be *evaluated*; any
conjunct whose inputs are unobservable blocks emission. Today that is
`provider_state` (no H4 driver), `suspended_or_scheduled` (no H13
contract), and relay-dependent conditions (§8 Q6). The interim is
closed-world, not assume-active: **unobservable ⇒ no `stall_candidate`,
no `stuck`.** What the interim emits instead is
`insufficient-observability` per missing input — the wiring gaps are
visible on the operator surface as gaps, never as stalls. The relay
conjunct is dropped outright (§8 Q6): `connection-unreachable` detection
is owned by the relay-liveness design (`docs/RELAY_LIVENESS_DESIGN.md`;
R1–R4 unimplemented), and the detector does
not fake the signal.

The `arc_code(S) == live` conjunct is what enforces the ladder's
never-relabel promise: the promise is not a policy note but a predicate
gate, so a future implementer cannot reintroduce the confusion by
"forgetting" §3.

**Trusted activity.** `last_muse_action_trusted(S)` is the max
control-plane *arrival* timestamp across trusted activity records —
confirmd-derived agent-activity events (`approval_filed`/`approval_decided`:
a trusted daemon's record that the agent acted) — or the session's entry
into the `live` arc (tenant-layer, G3), whichever is later. The quiet
clock anchors at `live`-entry so a fresh session with no activity yet is
not a stall. `cooperative` signals (muse-job heartbeats and job events)
are never inputs to this clock: they feed the divergence evaluator (§2),
and fresh cooperative claims against stale trusted signals produce
`telemetry-divergence`, never an extension of quiet time and never a
suppression of the predicate.

**Clock discipline.** The 30-minute threshold is the pilot's rule (§1);
it is a policy constant, not a tuned parameter — the design does not move
it. What the detector *does* define is the confirmation window: after the
predicate first holds, the detector waits one additional observation tick
— **one meter_agent `resource_window` period (5 min) + batch margin**, a
real cited cadence (metering §4) — and re-evaluates before emitting.
Two consecutive holds → emit. With arrival timestamps, box clock skew is
out of the picture *by construction*; the window absorbs late batch
arrivals, not skew.

## 5. Trust and placement

- **Control-plane-side service.** The detector lives with the tenant
  record and the G3 status vocabulary — the same service that will serve
  `GET /tenant/status`. It never runs on the tenant box (an agent that can
  stall can also stall a box-local detector — or silence it).
- **Push-only transport, no box reads.** The detector reads **only the
  control-plane-side shipped stream**: `HOSTED_SIGNUP_ONBOARDING.md` §10's
  signed append-only batches and metering §6's MeterQueue (on the H14
  PushQueue pattern) — box→plane push over a mutually-authenticated
  channel, never a control-plane pull. The G4 posture governs here
  verbatim: `spec.network = {public_ingress: false}` forbids inbound
  paths to the VM, so "collectors" in S1a means *stream consumers*, not
  box readers — no new box-read path is created, no privileged channel
  into tenant boxes, no H11-audit-sized hole. The box→plane channel
  itself is honestly labeled unbuilt (same posture as G4 §7); naming it
  is S1a's sequencing dependency, stated there.
- **Agent-forgeable inputs are cross-checked, never trusted alone.** The
  heartbeat's trust tier (`cooperative`, metering §4) means muse-job
  heartbeats *and* job events feed only the divergence evaluator (§2,
  §4): they can produce `telemetry-divergence`, they can never extend the
  quiet clock, and they can never suppress the predicate. Clearing a
  stall requires a *trusted* record (confirmd-derived event) with a
  control-plane arrival timestamp — the threat §2 names is implemented
  away, not scoped out.
- **No secrets, no content.** Detector events carry counters, timestamps,
  and enum classes only — the metering privacy contract (§5 of the
  metering doc) applies verbatim. An AgentMail credential, a
  `hsurr:<name>` placeholder, or any transcript content never enters the
  detector's event stream (cf. the R2 placeholders rule).
- **Until H10 ships, attribution is `tenant: unknown`.** Per #378's
  quarantine policy, detector events for unattributed boxes are
  quarantined from any billing-adjacent aggregate; the detector is a
  *status* instrument, never a billing instrument.
- **The detector never touches the agent's box.** Read-only on the
  shipped stream; no sudoers surface, no new writers on the tenant side
  (the box-local writers it reads — the heartbeat/meter spool, confirmd —
  already exist or are independently designed).

## 6. Confidence staging — the only path to automatic

`stuck` becomes automatic only through this sequence; skipping a stage is
a design violation:

- **S1 — observability wiring + offline evaluation.** The detector's
  stream consumers ship (S1a); the predicate evaluates against whatever
  conjuncts are observable. In the closed-world interim (§4), the honest
  S1 output is the **observability-gap map** (`insufficient-observability`
  per missing input — provider state pre-H4, suspend state pre-H13,
  relay-dependent conditions per §8 Q6), plus `stall_candidate`s for the
  fully-observable subset and `telemetry-divergence` from the divergence
  evaluator. The tenant-status endpoint keeps serving the operator-set
  value; operators see the detector's candidates alongside their own
  judgment. Instrumentation goal: measure the detector's precision on the
  observable subset against operator-set ground truth.
- **S2 — calibration soak.** With S1 data, publish the false-positive
  rate per confusion class (§3). The bar for S3: zero systematic
  confusion of `human-drop-off`, `human-denied`, `no-gated-action`, and
  `policy-misfire` **as `stuck` — and zero systematic confusion of
  suspended boxes and `telemetry-gap` sessions** (the interim's own FP
  classes — S3 must not be reachable while the product's own idle state
  is systematically mislabeled). S2 also owns the #377 dependency:
  idle-heartbeat semantics ("what counts as idle") must be decided
  before S2's data is read, or the soak measures the wrong thing.
- **S3 — automatic transition.** Only after S2's bar is met **and** the
  unobservable conjuncts become observable — H4's provider state shipped,
  the relay-liveness design (§8 Q6) shipped, H13's suspend contract
  shipped, G1's terminal records shipped: the detector may write the
  `stuck` code (licensed by transition rule 2, `live` → `stuck`; exits
  per the `stuck` row — operator/heuristic clears → re-evaluate;
  reprovision restarts the session), with every automatic transition
  carrying an audit trail (predicate inputs, the two confirmation ticks,
  the confusion-class evaluation). The operator override stays: any
  automatic `stuck` is clearable by the operator, and an operator-cleared
  stall feeds back into S2's calibration. No automatic `stuck` while any
  conjunct input is still assumed.

Honesty binding (the endpoint doc's `stuck` row, where "never exposed as
automatic" lives): until S3 ships, no copy, dashboard, or doc presents
the detector as automatic. The funnel's drop-off taxonomy may consume
S1's `stall_candidate` as a *candidate* signal, labeled as such — never
as the `stuck` code.

## 7. Build slices

- **S1a — signal collection (stream consumers, not box readers):** §10
  signed-batch / MeterQueue consumers for the meter_agent spool stream
  (`resource_window`, `idle_heartbeat`), confirmd pending-state + filing
  events, and the cooperative muse-job stream (divergence evaluator
  only). No new box-read path; no control-plane→box pull (§5). The
  box→plane channel itself is unbuilt — naming it is this slice's
  sequencing dependency (same honest posture as G4 §7).
- **S1b — predicate + advisory emission:** the §4 predicate over the
  observable conjuncts, the §3 confusion-class evaluation,
  `stall_candidate` events (vocabulary: the waitlist/funnel event
  vocabulary, `WAITLIST_OPERATIONS.md` — the same surface G4's summons
  observer emits to) to the operator surface and funnel telemetry,
  `telemetry-divergence` from the divergence evaluator, and the
  `insufficient-observability` gap map for the unobservable conjuncts.
  No vocabulary writes.
- **S2 — calibration harness:** operator ground-truth capture (the
  operator-set `stuck` they already record), FP-rate reporting per
  confusion class (incl. suspended-box and telemetry-gap), the #377
  semantics decision as a prerequisite gate, the §6.7-gate race rule.
- **S3 — automatic transition + audit trail:** gated on S2's bar AND the
  dependency shipments (H4 provider state, §8 Q6 relay-liveness design,
  H13 suspend contract, G1 terminal records); transition-rule-2
  conformance; operator override path.

## 8. Open questions (→ backlog)

- **Q1 (#377):** idle-heartbeat semantics — what "idle" means (no traffic?
  no job? no browser?). Decided before S2; the soak cannot be read
  without it.
- **Q2:** multi-box tenants (G7): a tenant with two boxes has two
  sessions — the predicate is per-session, but the 12-code vocabulary is
  per-tenant. G7's decision (per-box status vs newest-box arc) determines
  whether the detector emits per-box candidates or one tenant-level
  stall.
- **Q3:** the summons observer (G4) as a confusion-class input: until the
  S2 sender ships, "human has been nudged" is not a detector-readable
  fact. And until G1's terminal record (#213) ships, the detector cannot
  distinguish post-expiry silence from abandonment — confirmd's expiry
  times are known, but no terminal record is emitted for the detector to
  read. Interim rule (the floor, not an aspiration): **any session with a
  first filing that reached TTL (expired, even without G1's record) is
  excluded from `stuck`** — enforced by the §4 `no_first_filing_reached_TTL`
  conjunct alongside the `live`-arc gate, not merely by the still-pending
  approvals. The G4 summons observer sharpens this further when shipped,
  but the TTL exclusion is the interim guarantee against the exact
  funnel double-count the detector exists to prevent.
- **Q4:** heartbeat frequency vs cost — 60 s idle heartbeats are H13's
  number; the detector's confirmation tick is defined in-doc (§4: one
  meter_agent 5-min period + batch margin, a real cited cadence), so no
  new box-local cadence is needed. Confirm in S1a.
- **Q5:** whether the trial funnel's conversion math consumes S1
  `stall_candidate` at all, or waits for S3 — a product decision for the
  pilot owner, not this design.
- **Q6:** relay-liveness design (new backlog item, no owner yet): the
  `connection-unreachable` code assumes "control-plane/relay defect
  instrumentation" (endpoint doc) that no design names — no relay doc, no
  liveness signal, no producer. The detector's relay-dependent conditions
  stay unobservable until this ships; the predicate drops the relay
  conjunct rather than faking it, and S3's gate includes it.
  **DESIGN SHIPPED 2026-09-26 ~10:32 CDT gap turn:** `docs/RELAY_LIVENESS_DESIGN.md`
  (session frames + two-channel liveness — passive relay journal and
  handshake-only synthetic dial prober, no-inbound observation discipline,
  `relay_path_state` producer contract for the tenant-status layer, the
  predicate's relay conjunct, R1–R4 build slices). Implementation
  (R1–R4) remains as a tracked issue.

## Cross-references

- `docs/TENANT_STATUS_ENDPOINT.md` §2 (`stuck` row), §7 Q3 — this design
  answers Q3; the Q3 line now points here.
- `docs/FIRST_TEN_MINUTES_SPEC.md` §8 — the failure taxonomy being
  mechanized; §9 — the honesty binding.
- `docs/USAGE_METERING_DESIGN.md` §4–§5 — signal inventory + trust tiers
  + privacy contract; #376/#377/#378.
- `docs/FIRST_APPROVAL_SUMMONS.md` §6 — summons-observation as a
  confusion-class input (Q3).
- `docs/SENTINEL_TELEMETRY_SURFACES.md` + #356 — agent-forgeable events
  are not ground truth.
- H11 `docs/MULTI_TENANCY_AUDIT.md` — the tenant record the detector
  reads; G7/G8 — vocabulary/schema decisions the detector inherits.
- G1 (#213) — expiry terminal records; the detector's pending-approval
  conjunct reads G1's terminal record when it ships, instead of inferring
  expiry from absence.
