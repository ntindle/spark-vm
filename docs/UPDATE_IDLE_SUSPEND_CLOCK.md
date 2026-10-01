# Update windows vs idle/suspend and the session clock — G14

**Status:** designed. Resolves the design half of backlog item G14
(GitHub #556) from the tenant-box update-channel analysis
(`HOSTED_GAP_ANALYSIS.md` §13). Implementation (S1–S3) remains on #776 (the G14 implementation issue; #556 closed on the design).

**The gap:** H13's suspend/wake and G9's stall detector both assume a
box is either working or stalled. Three questions were unspecified:

1. Is an update window a trusted signal (quiet clock) or does the stall
   detector see a stall?
2. Does a suspended box wake for updates, or update on wake?
3. How do updates and suspend interact with the 10-minute session clock?

This doc answers all three. The decisions are contracts the owning
components (H13's idle/suspend design, G15's rollout controller, the G3
tenant layer, G17's reporting) must honor — not re-litigations of G11's
renewal-model decision.

## 0. What is already decided (inputs, not re-litigated)

- **G11** (`docs/UPDATE_CHANNEL_POLICY.md` §1): reimage-with-migration
  is the single renewal path — no in-place updater for tenant boxes.
  `maintenance` is a trusted signal; the stall detector must treat it
  as a quiet-clock window and never relabel it `stuck`. A scheduled
  wave never interrupts an active arc: the scheduler enters
  `maintenance` only from quiescent codes (`live`, `approved`), and
  boxes in pre-`live` codes, `waiting-on-approval`, any suspension
  code (`stuck`, `connection-unreachable`), or `box-unhealthy` are
  skipped and retried next cycle. The 10-minute clock is neither paused
  nor reset during `maintenance`.
- **G12** (`docs/UPDATE_CHANNEL_POLICY.md` §2,
  `docs/TENANT_STATUS_ENDPOINT.md` §2 + transition rule 8): the 13th
  tenant-status code `maintenance` — entry from `live`/`approved` only,
  exit returns the **latched** arc code, failure during maintenance
  moves the endpoint to `box-unhealthy` with
  `detail: maintenance-failed: <check>`. Producer: the control plane's
  update scheduler / reimage orchestrator — never the provider driver,
  never the Muse. Until the signal exists, updates must not be
  scheduled silently.
- **G9** (`docs/STUCK_DETECTOR_DESIGN.md`): the stall predicate's hard
  gates — `arc_code(S) == live`, `shipper_alive`, the 30-minute quiet
  clock on **trusted signals only** (cooperative signals feed the
  divergence evaluator, never the clock), `NOT suspended_or_scheduled`,
  and the closed-world interim rule (unobservable ⇒ no emission).
- **G13** (`docs/TENANT_UPDATE_TRUST_MODEL.md`): the reimage path's
  reprovision-attribution half — who authorized the reimage, landing
  in the control-plane audit journal with per-tenant attribution.
- **G15** (`docs/ROLLOUT_CONTROLLER_DESIGN.md`): the rollout
  controller's wave assignment, canary, halt, and freeze; suspended-box
  semantics were explicitly deferred to this doc. The scheduler owns
  the `maintenance` enter/exit writes.
- **Suspend research** (`docs/SUSPEND_WAKE_RESEARCH.md`): wake-on-SSH-dial
  is a gateway-layer pattern, not a provider primitive; `dial()` gets
  bounded-blocking wake-wait semantics with first-writer-wins dedup;
  suspend guarantees **disk persistence only**; `suspend()` of a
  non-runnable box is an explicit driver error; idle detection is
  control-plane work (H13). H13 itself still needs H11's isolation
  answer and the H4 provider adapter for suspend primitives; #377
  (idle-heartbeat semantics) is still open.

## 1. Decision D1 — update windows are trusted quiet-clock windows

When `GET /tenant/status` serves `maintenance`, the stall detector
does not evaluate the predicate — full stop.

- The stand-down reads the **served** code, not the latched arc code.
  G9's `arc_code(S) == live` conjunct already gates on the served code;
  this doc pins that reading so no future implementer "fixes" the
  detector by evaluating against the latched `live` underneath the
  `maintenance` and starts relabeling update windows as stalls.
- The 30-minute quiet clock **freezes** during `maintenance`. It does
  not advance (a box under update is not a working box — advancing
  would punish the box for the operator's update) and it does not reset
  (the update is not trusted Muse activity — resetting would let a
  perpetual wave schedule suppress stall detection forever). On exit
  to the latched code, the clock resumes from the freeze point.
- What makes the window trusted: `maintenance` has exactly one
  producer — the control plane's update scheduler (G12's producer
  rule) — and the set/clear writes are **control-plane-local** (the
  scheduler writing the tenant-status store; they never traverse the
  box→plane channel). A tenant Muse with shell on the box has no path
  to the status store's writer and cannot fake, extend, or suppress
  an update window. The freeze accounting uses the control-plane
  timestamps of the set/clear writes, not box time. **Residual:**
  write-authorization enforcement on the status store is unbuilt and
  unnamed in every cited doc — it is the G3 tenant layer's to name,
  and until it exists the single-producer rule is policy, not
  mechanism.
- The detector must never label a maintenance window `stuck` — and
  symmetrically, must never treat "the box was busy updating" as
  evidence of activity. A maintenance that never clears is a scheduler
  defect, and §7's watchdog routes it to `box-unhealthy`, never
  `stuck` (the arc gate already keeps it out: the served code is not
  `live`).

## 2. Decision D2 — suspended boxes update on wake; they are never woken for updates

Suspend is a deliberate cost state: surveyed providers bill ~zero
compute while suspended (`SUSPEND_WAKE_RESEARCH.md`). Waking a box to
run a fleet update burns the cost the suspend earned, and can
resurrect a box the tenant deliberately left idle — a consent problem
as much as a cost problem.

- The wave scheduler's box set is **running and wave-eligible only**.
  Suspended boxes are skipped by the wave — skipped
  silently-but-honestly: the skip lands in the wave journal (G15/G17's
  reporting surface), never in the tenant's view, because a suspended
  tenant has no active view to show it in. (The transparency option —
  surfacing image staleness on the tenant's status view — is weighed
  and rejected for the suspended state: the staleness becomes visible
  at wake anyway, when the wake path serves `maintenance:
  reimage-for-update`; inventing a second tenant-visible signal for a
  sleeping box buys confusion, not honesty.)
- Staleness stages on the box record, not on a wake. G11's
  provisioner-tracked `image_version` field carries the staleness: a
  suspended box whose `image_version` is behind the wave's pinned image
  is simply a box with a stale version — the wave does not chase it.
- **Scheduler-owned wakes** (cron / operator-initiated): on wake,
  the hook first lets the tenant layer re-serve the latched arc code,
  so transition rule 8's entry condition (`live`/`approved`) is met as
  written — no endpoint amendment is needed, and this doc makes no
  claim about what H13 serves during `suspended`/`waking` (Q3). The
  staleness check then evaluates the box's reported `image_version`
  (the box reports; the scheduler hook compares) against the current
  permitted/pinned version (G15's converge-forward language): if
  behind and wave-eligible, the hook enters `maintenance` and runs
  `reimage-for-update`. The tenant-visible path is
  `suspended` → (waking) → latched code re-served →
  `maintenance: reimage-for-update` → latched code. The endpoint must
  never show the latched `live` during the wake-time reimage — the
  same honesty rule G12 applies to in-band updates.
- **Interactive dials** take §3's ordering instead (wake to usable on
  the current image first; the staged update becomes next-cycle wave
  work). D2's "before handover" ordering never applies to the
  interactive branch — the two orderings are per-consumer, not
  per-event, and an implementer following either section alone must
  land on the same behavior.
- **Policy fork (not decided here):** G15's expedited security channel
  may, by operator-declared policy, override the no-wake default for
  security-emergency waves — an operator registration (G13's
  emergency-surface shape), never scheduler discretion. The override
  is tenant-visible through the same `maintenance` signal and lands in
  the audit journal (G13). Until that policy exists and is declared,
  the no-wake default is the contract H13 must honor.

## 3. Decision D3 — dial latency is never hostage to a reimage

On the wake path there are two consumers, and they get different
ordering:

- **Interactive dials** (a human or the tenant Muse dialing in): the
  wake path brings the box to *usable* first — the dial's bounded
  wake-wait (suspend-research rec 5) resolves against the current
  image. The staged update becomes wave work: the now-running box is
  wave-eligible on the next scheduler cycle. Rationale: a reimage has
  its own wave budget and its own failure modes; coupling it to the
  dial turns every dial into update roulette and breaks the
  bounded-blocking contract `dial()` advertises to its callers. (The
  security-emergency override in D2 is the only exception, and it is
  policy-declared, not default behavior.)
- **Scheduled wake-on-schedule** (cron workloads, suspend-research rec
  4): when the wave scheduler owns the wake, the update may run
  *before* the cron payload — the box was woken for work, and the
  operator (via the pinned wave) owns the ordering. The cron payload
  then runs from the new image's tooling (G11's forward-migration
  discipline: the new image migrates old state, never the reverse). If
  a cron payload is operator-pinned to a specific image, the update is
  skipped for that box this cycle.
- **Dial callers see the truth either way.** A dial that arrives while
  a wake-time reimage is in flight observes `maintenance:
  reimage-for-update` on `GET /tenant/status` (D2) — the sandbox0
  failure taxonomy the suspend research recommends ("waking up" vs
  "resume failed", rec 2) applies to the reimage phase too: a reimage
  still in flight is "waking up" (poll and retry), a failed reimage is
  a terminated attempt that surfaces on the dial as an error, never as
  an indefinite wait.

## 4. Decision D4 — the session clock pauses while the box is suspended

The 10-minute onboarding clock measures **available** onboarding time.
A suspended box is not available to the tenant — so the clock pauses.

- Mechanics: the tenant layer records `clock_paused_at` on suspend
  entry and compensates on wake. The timestamps are control-plane
  arrival timestamps, never the box clock (the detector design's §4
  clock-skew rule: box clocks drift, and Fly's post-resume skew is
  documented in the suspend research).
- Contrast with `maintenance` is deliberate: G11's rule stands — the
  clock keeps running during `maintenance`, neither paused nor reset.
  Maintenance is an operator action on an *available* box; suspend is
  unavailability. One is the operator spending the tenant's time; the
  other is the tenant having no time to spend.
- **H13's contract (decided here, designed there):** the idle detector
  must count "waiting on a human" as activity. A pending approval
  filing (confirmd holds an undecided filing) or an unreaped expiry
  (pre-G1) keeps the box out of the suspend candidate set — the
  registered-workload registry H13 designs must include open
  approval/human-wait state. The clock-pause rule is the backstop (a
  box suspended mid-onboarding while its human was slow cannot expire
  on time it never had); the primary fix is the idle detector's,
  because suspending a box whose human is about to answer is a product
  defect regardless of clock math.
- Expiry interplay (with G1): clock expiry is evaluated against
  *available* time. An expiry that would land while the box is
  suspended is evaluated at wake against the paused clock — suspend
  delays expiry by exactly the suspended duration. This follows from
  the pause rule; it is stated here so no implementer re-derives it
  the other way.

## 5. Decision D5 — wake and scheduler events never feed the stall detector's inputs

- Wake-on-schedule (cron) and any control-plane-initiated wake are
  control-plane events, not trusted Muse actions: they must not
  extend or reset the stall detector's 30-minute quiet clock. They
  are the same tier as cooperative signals for this purpose — they
  feed nothing into `last_muse_action_trusted(S)`
  (`STUCK_DETECTOR_DESIGN.md` §4). A box that wakes for cron every
  10 minutes and runs no agent must still be evaluable as a stall
  candidate; a cron wake is not evidence the agent is alive.
- The `maintenance` enter/exit writes are scheduler events
  (control-plane), also not Muse activity. On exit to the latched
  code, the quiet clock resumes from the D1 freeze point — it does not
  restart from the update completion.

## 6. Decision D6 — the idle detector's contract

- `maintenance` counts as activity: a box serving `maintenance` is
  never suspended mid-update. The check reads the **served tenant
  code**, not provider state — provider state may say `active` while
  the box is mid-reimage, and the tenant layer knows better.
- The wave-membership gap: between a wave's assignment of a box and
  the scheduler's `maintenance` entry, the box is neither running-idle
  nor yet in maintenance — an idle detector evaluating in that gap
  could suspend a box the wave is about to update. The scheduler must
  close the gap: wave membership is published as a control-plane event
  (push, not poll — the detector reads the control-plane-side stream
  per its §5 placement rule), and the detector treats wave membership
  as activity. The mechanism is G15's to build; the requirement is
  this doc's.
- `suspend()` on a box in `maintenance` is an explicit driver error —
  the suspend research's rec 2 rule ("`suspend` of a non-runnable box
  is an explicit driver error") generalized: a box under maintenance
  is not runnable for suspend purposes. Silent no-ops hide broken
  idle detectors; the control plane treats the error as log-and-skip.

## 7. Decision D7 — `maintenance` is trusted but time-bounded: the watchdog

A trusted window that never expires is a place to hide. Each
operation class carries a max window — for `reimage-for-update`, the
wave budget from G15's controller; other operation classes define
theirs when they are specified. The bound is a scheduler-owned
constant, not a per-box negotiation.

- On expiry without a scheduler clear, the scheduler itself (or a
  scheduler watchdog in the same trust domain — never the box, never
  the tenant Muse) moves the endpoint to `box-unhealthy` with
  `detail: maintenance-failed: timeout`, extending G12's failure
  contract with the timeout check. A maintenance that never clears is
  an operator defect (a stalled wave), not agent abandonment — it is
  never `stuck` (the arc gate already routes it away from `stuck`;
  this doc pins the timeout half of that routing).
- The watchdog's producer rule matches G12's: the same trust domain
  that sets `maintenance` clears it or fails it. No second writer is
  introduced; the detector reads the served code and stands down
  regardless (D1), so the watchdog cannot race the detector into a
  mislabel.

## 8. Decision D8 — trust and placement

- All G14 state lives in the control plane (tenant layer +
  scheduler), never on the tenant box. The box's only role in these
  decisions is its provider state (`suspended`/`waking`/`active`), read
  by the control plane through the H4 driver as an input to the
  suspend conjuncts — the same placement rule as the stall detector
  (`STUCK_DETECTOR_DESIGN.md` §5): the detector never runs on the
  tenant box, and neither does anything in this doc.
- Producer rules, restated in one place: `maintenance` set/clear/fail
  = the control plane's update scheduler only (G12, extended by D7);
  suspend entry = H13's idle detector via the driver; wake =
  the dial path / scheduled wake (H13); wave-membership events = the
  rollout controller (G15); the stall detector reads the served tenant
  code plus scheduler/controller events (D1, D5, D6). No writer is
  reachable from tenant code. A tenant Muse with shell cannot enter
  `maintenance`, cannot mark wave membership, and cannot pause its own
  session clock by faking a suspend — the trust tiers that make D1's
  window "trusted" are the same tiers that keep the clock honest.
- No secrets, no content: these events carry states, timestamps, and
  enum classes only — the detector design's §5 privacy contract
  applies verbatim. The `auto_resume=false` interplay: a per-tenant
  `auto_resume: false` gate (suspend-research rec 2) means dials do
  not wake the box; updates on such boxes can only apply on
  operator-initiated resume. The scheduler must not queue a silent
  reimage for the next operator resume — the resume is
  operator-initiated, but the update inside it is still a scheduled
  update, so the wake path serves `maintenance` (G12's no-silent-updates
  rule covers this case by the same principle).

## 9. Build slices (for future turns, not this doc)

1. **S1 — wave scheduler suspend-awareness** (G15's controller):
   the wave set excludes suspended boxes; staleness recorded on the
   box record via G11's `image_version` field for the wake path; the
   skip recorded in the wave journal (G17's reporting surface).
2. **S2 — wake-path update hook** (H13's wake path + G15's scheduler):
   on wake, check the box's reported `image_version` against the
   current pinned version; if behind and wave-eligible, enter
   `maintenance` (from the re-served latched code, transition rule 8)
   and run `reimage-for-update`;
   interactive dials wake-to-usable first with the update deferred to
   the next wave cycle (D3); scheduled cron wakes may run the update
   first; wave-membership events published for D6's no-suspend gap.
3. **S3 — tenant-layer clock pause + idle-detector guards** (H13's
   detector + tenant layer): clock pause on suspend entry /
   compensate on wake (control-plane arrival timestamps); pending
   approvals / unreaped expiries as activity in the workload registry;
   `maintenance`-as-activity; the D7 watchdog with per-operation-class
   bounds.

## 10. Open questions (→ backlog / owning turns)

- **Q1 (H13 + G15):** the D7 per-operation-class maintenance bounds —
  the exact windows need the wave budget from G15's controller
  *implementation*, not its design. Until bounded, `maintenance` is
  trusted-but-unbounded; the doc is explicit about that residual.
- **Q2 (H13 + G15):** the D2 security-emergency override policy — who
  declares the emergency, what tenant-visible signaling exists beyond
  `maintenance`, and the audit shape (G13's journal). Policy-owned,
  never scheduler-discretionary.
- **Q3 (H13):** the served code for a suspended box on
  `GET /tenant/status`. This doc deliberately stays silent: the 13-code
  vocabulary has no `suspended` code (the detector design's §3 step 5),
  and the detector's `suspended_or_scheduled` conjunct reads provider
  state (H4), not the served code. H13's suspend contract specifies
  the served representation; this doc's contracts are expressed
  against it, not through it.
- **Q4 (#377):** idle-heartbeat semantics — D5/D6 assume the registry
  can express "waiting on a human"; #377 must define what "idle"
  means before the registry can be built.
- **Q5 (G17):** funnel attribution for wake-applied updates — an
  update applied inside a wake must read as update-churn, never
  provision-churn (G11's attribution rule extended to the wake path),
  and the wake itself must not read as a new session.

## Cross-references

- `docs/UPDATE_CHANNEL_POLICY.md` §1–§2 — G11/G12: the renewal-model
  decision, the `maintenance` code, transition rule 8, funnel
  attribution, never-interrupt-an-arc.
- `docs/TENANT_STATUS_ENDPOINT.md` §2 (13-code vocabulary), §4
  (producers), §8 (multi-box selection) — the served-code contract
  this doc's stand-down reads.
- `docs/STUCK_DETECTOR_DESIGN.md` §2 (trust tiers), §3 (confusion
  ladder), §4 (predicate, closed-world rule, clock discipline), §5
  (trust and placement) — the detector this doc constrains.
- `docs/TENANT_UPDATE_TRUST_MODEL.md` — G13: the audit journal the
  D2 emergency override and D8 producer rules land in.
- `docs/ROLLOUT_CONTROLLER_DESIGN.md` — G15: the wave scheduler that
  owns the `maintenance` writes, the wave set, and the wave budget.
- `docs/SUSPEND_WAKE_RESEARCH.md` — the suspend mechanics research:
  wake-on-dial as gateway, bounded wake-wait `dial()`, disk-only
  persistence, driver error rules, the `auto_resume` gate.
- `docs/FIRST_TEN_MINUTES_SPEC.md` §8 — the failure taxonomy the
  detector mechanizes; the 10-minute clock D4 pauses.
- G17 (#608 — closed on the design) — update event reporting: the wave-journal and Q5 wake-attribution
  questions live on #779 (S2–S3) and #776 (Q5) respectively.
- H13 (backlog) — the suspend/wake design that owns the served-code
  question (Q3), the workload registry, and the exact bounds (Q1);
  #377 — the idle-semantics prerequisite (Q4).
