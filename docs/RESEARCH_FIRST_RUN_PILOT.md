# Beta-Muse first-run pilot (R7) — research protocol

**Status:** protocol defined; pilot NOT yet run. Execution is blocked on
beta-Muse recruitment (see §9 and `NEEDS_USER.md`).

R7 from `RESEARCH_AGENT_SANDBOX_ADOPTION.md` (PR #25, hosted adoption
research): validate the Muse-as-customer transfer — instrument
time-to-first-working-approval with a handful of beta Muses before Finding
1's shape hardens into a spec. The research's Limitations section is explicit:
all evidence is human-developer DX; that a Muse adopts the same way is a
hypothesis. This doc is the test design for that hypothesis.

**Primary output:** the friction map (the help-request sequence across the
cohort). Time-to-first-working-approval is a supporting context metric, not
the primary one — a faster TTFWA that required more operator help is a worse
outcome, not a better one.

## 1. The transfer being tested

Finding 1 (PR #25): in the SDK-first segment, the products that convert make
the first run a single bounded action, not a tour of capabilities
(`npm i` → env key → quickstart snippet; `sandbox = daytona.create()`).

The transfer hypothesis, stated as a testable claim: **the task half of
Finding 1 transfers — a Muse's first interaction with a spark-vm box is best
shaped as one tiny task ending in a working approval.** The full "conversion"
claim (signup → continued use) cannot be tested without the hosted product
and is explicitly NOT tested here — §3's two-phase scoping holds: Phase A
constrains the task half only; Finding 1's shape must not harden into the R1
spec until Phase B data exists.

This pilot does **not** test onboarding docs, signup UX copy, or pricing. It
tests exactly one question: *does the one-tiny-task adoption gate transfer
from human developers to Muses at the task level, and where does the
approval loop create friction?*

## 2. Definitions

- **Working approval**: a beta Muse's action triggers an approval request
  filed through `confirmd`, the human answers it on the approvals page, the
  grant is minted, and the Muse's task verifies end-to-end using the granted
  capability. Notes on the mechanics (verified against `confirm/confirmd.py`):
  the request file moves pending → answered → `consumed/` on *both* approve
  and deny (the consumed file carries `decision`); the grant is minted via
  the grant writer *before* the move, on approve only. So `grant_consumed` in
  this doc means "a consumed file with `decision == "approve"`" — `consumed/`
  is a proxy for grant-minted, not the minting event itself. A filed-but-
  expired request, a denied request, or a request the Muse never sees answered
  does not count.
- **Time-to-first-working-approval (TTFWA)**: `created(first working
  approval) − pilot_start` (see §6 for why this reduction is exact), reported
  as order-of-magnitude bands (minutes / tens of minutes / hour+), never as
  a precise median. This is a friction metric, not a score — see §8.
- **Aha moment**: the first point at which the Muse *anticipates* the
  approval loop (its unprompted action triggers a correctly-scoped filing, or
  it narrates that an action will need approval before acting). Recorded as a
  timestamped qualitative event, not scored.
- **Help request**: any intervention by the pilot operator to unstick the
  beta Muse (clarification, pointing at docs, fixing environment). Counted
  and timestamped; the *sequence* of help requests is the friction map the
  pilot is really after.
- **Completed unprompted**: a session that ends in a working approval with
  zero `help_request` events.
- **Session abandonment**: the operator closes a session after 30 minutes
  with no Muse action *and* no pending approval, or when the Muse explicitly
  gives up. The rule, not the operator's mood, closes the session.

## 3. Two phases (honest scoping)

The hosted product is unbuilt: there is no hosted signup or provisioning to
pilot. The pilot therefore runs in two phases, and only Phase A can run now.

- **Phase A — self-hosted first run (runnable now):** beta Muses work from a
  spark-vm checkout on a provisioned box, completing the canonical tiny task
  below. Tests the task-half transfer hypothesis on the approval loop and
  the first-task shape. Does not test signup, billing, or provisioning.
- **Phase B — hosted funnel (runs when the hosted signup exists):** the
  actual hosted funnel — discovery → signup → identity linking → provisioned
  box → first task — instrumented end to end. Feeds the R1 first-10-minutes
  spec directly. Finding 1's shape must not harden into the R1 spec until
  Phase B data exists; Phase A data constrains the task half, not the signup
  half.

Running Phase A first is not scope creep: if the one-tiny-task gate fails to
transfer even on the self-hosted box, the hosted first-run design needs a
different foundation than the research assumed.

## 4. Participants, recruitment, and box standardization

- **Cohort:** recruit 5–6 to land 3–5 completions. Small on purpose — this
  is a friction-mapping study, not a survey; the output is the *sequence*
  of snags, which saturates fast. **If sessions 4–5 surface new snag
  classes, extend the cohort** rather than asserting saturation.
  Replacement rule: sessions closed as contaminated (human latency > 2 min,
  §5) or abandoned (§2) are replaced up to the 6-recruit cap; beyond that,
  the writeup reports a small-n qualitative study and the gates in §7 do not
  fire.
- **Exclusion criteria (cohort integrity):** anyone who has read this
  protocol or the PR #25 adoption research is out; screen for prior
  spark-vm exposure (repo reads, discussion threads); the operator's own
  fleet is capped at 1 of the cohort (shared tooling/prompting lineage makes
  its observations non-independent). Beta Muses must not be spark-vm
  contributors — contributor familiarity poisons first-run data.
- **Selection bias, stated up front:** peer Muses are technical users, not
  the eventual less-technical audience. The pilot measures best-case
  transfer; friction found here is a floor, not a ceiling.
- **Box-standardization checklist** (all sessions run on identically
  prepared boxes):
  1. confirmd pinned to the same release + the **pilot policy file** (§5)
     under which the canonical task always files an approval request.
  2. The pilot harness installed with a generated `session_id`.
  3. The §5.1 readiness gate passed on that box.
  4. No other pilot session active on the box's confirmd instance at the
     same time (attribution rule, §6).

## 5. The canonical tiny task (Phase A)

One task, fixed across the cohort so results are comparable. Deliberately
exercises the approval loop, not the VM's generality:

> "Check whether your box can reach the internet: run `curl -sI
> https://example.com` and report the result."

The task is chosen so that, **under the pinned pilot policy, the egress
decision always files an approval request** — the metric the pilot hangs on
is box-policy-dependent, so the policy is part of the protocol, not left to
the pilot box's default posture (see §5.1).

- The task text must NOT mention approvals, confirmd, or the proxy. The
  pilot measures whether the Muse discovers the loop on its own or needs a
  help request — the task brief is part of the measurement.
- Task brief (verbatim, handed by the harness):
  ```
  Your task: check whether this box can reach the internet.
  Run: curl -sI https://example.com
  Report back the result (reachable / not reachable, plus the status line).
  Don't change configuration unrelated to the task. Nothing else is asked of you.
  ```
- **Human on standby, target response < 60 s.** A 5-minute human latency is
  an eternity for a Muse session (context stall, giving up) and contaminates
  the behavioral data, not just the clock: any session with human latency
  > 2 min is flagged **contaminated** — excluded from the median, kept in
  the friction notes, and replaced under the §4 replacement rule.

### 5.1 Readiness gate (before the cohort, on every pilot box)

The pilot's core precondition is gated, not asserted. The operator runs the
canonical task once per pilot box and confirms: (a) a file appears in
`APPROVALS/pending/`; (b) the human can answer it; (c) the grant mints. If
the task doesn't file under the pinned policy, substitute a task that does —
the substitute must be identical across all pilot boxes, or the cohort is
not comparable. **Do not run the cohort until the gate passes.** Record a
`policy_verified` harness event (confirmd in the loop with the pilot policy +
a pre-flight approval round-trip succeeded) before the first task-half start
(`task_given`).

## 6. Instrumentation spec

Implementation is a future build-loop `feature` run; this section is the spec
it builds from. All events go to one JSONL file per pilot session
(`pilot_<session_id>.jsonl`, `session_id` a harness-generated uuid4), one
event per line:

```
{"ts": "...", "event": "...", "actor": "harness|muse|human|operator", "session_id": "...", "detail": "..."}
```

- **`policy_verified`** (harness): pilot policy hash, confirmd version,
  pre-flight round-trip result. Precedes the first task-half start
  (`task_given` below) — in Phase B the funnel re-anchors `pilot_start` at
  funnel entry, before any box or policy exists, so the event is scoped to
  the task half, not to `pilot_start`.
- **`pilot_start`** (harness): cohort id, task id, box fingerprint =
  `sha256(pilot policy file bytes || confirmd version string)`. The clock
  starts here, on the harness clock.
- **`task_given`** (harness): the verbatim task brief handed to the Muse.
- **`first_muse_action`** (harness): first shell command or tool call the
  Muse issues. Measures orientation latency. If the Muse never acts, this
  event is absent and orientation latency is undefined (the session resolves
  via the abandonment rule).
- **`approval_filed`** (harness, derived from confirmd): request id,
  action class. **Never log the approval payload or any client-influenced
  free text** — payloads can carry secrets and prompt content; log ids,
  classes, and outcomes only (consistent with the proxy's placeholder
  posture and the O7/#17 log-injection finding). Pending files carry
  `id, kind, created, expires, …`; log only `id` + `kind`.
- **`approval_answered`** (harness, derived): request id, outcome
  (approved/denied/expired), emitted once per request id. Outcomes
  approved/denied come from the `answer` audit line (`id=… decision=…`). **Expired is not in the audit
  log** — `load_pending()` reaps silently; only the item-page path audits
  `expired-reaped`. So the harness caches `(id → created, expires, kind)`
  at first sighting of each pending file — the cache is persisted to disk
  so a mid-session harness restart doesn't lose expiry derivability for
  files reaped during downtime — and marks outcome=expired when the file
  disappears with `expires < now` and no answered/consumed transition. Fallback, if the inference proves flaky: add
  `audit_log("expired-reaped", …)` in `load_pending()` — an explicit
  confirmd change, which the spec currently avoids.
- **`grant_consumed`** (harness, derived): request id. Emitted **only**
  when the consumed file's `decision == "approve"` (the harness reads the
  file — denials land in `consumed/` identically, per §2). The grant is
  minted by the grant writer before the move; `consumed/` is the observable
  proxy.
- **`result_reported`** (operator): the Muse's final report recorded +
  boolean `verified` = the curl ran under the granted egress and produced a
  status line. A working approval completes here — this is the terminal
  event the §2 definition requires and the event stream must contain.
- **`aha_moment`** (operator, qualitative): timestamp + one-line note of
  what the Muse did or said.
- **`help_request`** (operator): timestamp + which snag triggered it.
- **`pilot_end`** (harness): outcome (working-approval / abandoned /
  contaminated), TTFWA band if completed, count of help requests, count of
  approval rounds. `working-approval` requires the `result_reported`
  verification step — a minted grant the Muse never uses is not a working
  approval.

**Existing substrate** (verified against `confirm/confirmd.py`): audit lines
are `ts=… event=… peer=… login=…`; the pending → answered → consumed
lifecycle is file-backed; the answer path writes `decision` and
`answered_at` onto the file. So `approval_answered` (approved/denied) and
`grant_consumed` are derivable without touching confirmd's hot path — the
only deliberate gap is expiry inference (above), with the audit-line fallback
as an explicit, optional confirmd change.

**Attribution rule:** exactly one active pilot session per confirmd instance
at a time; the harness attributes every filing observed between
`pilot_start` and `pilot_end` to the session. The harness enforces this
with a session lock (refuses `pilot_start` while one is open), not just the
§4 operator checklist. There is no pilot-session
marker on the request files — overlapping sessions on one box would need
the filer (proxy) to write a pilot marker into the request file; flag that
as a filer contract change if ever needed.

**Implementation notes for the harness builder:** tolerate partially-written
pending files (the filer isn't contractually atomic — parse-retry with a
small backoff); never log payload free text; the task-delivery channel
(how the harness hands the task to the beta Muse) must be identical across
sessions — its exact mechanism is an open spec item for the implementation
run.

### Metric definitions

- **TTFWA (supporting):** define human latency canonically as the **sum**
  of `answered_at − created` (file fields, confirmd's clock) over all
  approval rounds up to and including the first working approval. Then
  `grant_consumed.ts − pilot_start.ts − human latency` reduces exactly to
  **`created(first working approval) − pilot_start`**. Single-clock
  assumption: harness and confirmd on the same box; if not, the harness
  must record and apply the clock offset. Report as bands (minutes / tens
  of minutes / hour+), never precise medians.
- **Orientation latency:** `first_muse_action.ts − task_given.ts` (undefined
  if the Muse never acts).
- **Approval discovery (binary per session):** did the Muse's unprompted
  action trigger the first filing — i.e. the first `approval_filed` with no
  preceding `help_request`?
- **Approval rounds:** filings up to and including the first working
  approval; first-try success = 1. Denials/expiries count as filings; the
  writeup must distinguish exploratory filings (the Muse correctly probing
  scope — good behavior) from failed attempts.
- **Aha latency:** `aha_moment.ts − pilot_start.ts` if observed.

### Phase-B schema compatibility

Phase B is additive, not a rewrite. Reserve the funnel-event namespace now:
`funnel_signup`, `funnel_identity_linked`, `funnel_box_provisioned` (harness
events, emitted as the hosted funnel exists). Phase B re-anchors
`pilot_start` at funnel entry; the Phase-A event set defined above becomes
the named **"task half"** sub-span within it, anchored at `task_given`
(the task-half start). Task-half TTFWA is defined against the task-half
anchor, so it is unchanged by the re-anchoring.

## 7. Analysis plan and decision gates

After the cohort runs, the writeup answers:

1. Did the task half of Finding 1 transfer? (Did Muses complete the task in
   one session with ≤1 help request?)
2. What was the snag sequence? The help-request transcripts become the
   ranked friction list that feeds R2 (pre-seeded state) and the R1 task
   design.
3. Was the approval loop discovered or taught? If every Muse needed a help
   request to find confirmd, Finding 2's "per-action consent" story has an
   onboarding gap — the product must surface the loop proactively, not wait
   to be asked.

**Pre-registered gates (falsifiable, evaluated on the non-contaminated,
non-replaced completions; first match wins, so the procedure is total and
deterministic):**

1. **Fails:** any abandonment among non-contaminated, non-replaced
   sessions, OR median Muse-side TTFWA (human latency subtracted) ≥ 60 min.
   Finding 1 gets a Muse-specific rewrite — the adoption gate is not "one
   tiny task" for Muses, it is something else (likely: pre-seeded state + a
   narrated first approval, i.e. R2-first, R1-second). The R1 task design
   waits for the rewrite.
2. **Holds:** median ≤ 30 min AND ≥ 50% of completions with ≤ 1 help
   request. Unlocks only the R1 **task-design** half: "engineer the
   fastest path to one working approval" becomes the R1 task foundation.
   The R1 spec as a whole still waits for Phase B.
3. **Mixed:** ≥ 50% of completions unprompted AND ≥ 1 session needing ≥ 2
   help requests (abandonment is owned by gate 1 and does not fire here).
   The split is documented per snag class; snag classes that reproduce
   across ≥ 2 sessions become R2 fixes; the R1 task-design decision is
   deferred to a second cohort rather than defaulting to "holds."
4. **Otherwise** (median in 30–60 min, conditions split): treat as mixed —
   document per snag class, defer the R1 task-design decision to a second
   cohort.

Gates do not fire below 3 non-contaminated completions (small-n qualitative
study instead — §4).

Either way, the outcome is published as an R7 findings addendum to this doc
(or a linked findings file), and R1/R2 backlog items are updated from it.

## 8. Reporting rules (anti-claims)

- **This is not a benchmark.** Never publish per-Muse scores, leaderboards,
  or "Muse X was faster than Muse Y" comparisons. Report cohort-level
  friction shapes only — and TTFWA only as bands, because a published
  "median TTFWA" is a benchmark-shaped number in a public repo. When
  publishing the R7 findings addendum, report only the TTFWA band and which
  §7 gate fired — never the numeric median.
- Do not generalize beyond the cohort: "3 of 4 beta Muses discovered the
  approval loop unprompted" is a finding; "Muses discover the approval loop"
  is not.
- Per POSITIONING.md anti-claims: pilot results never become marketing copy
  ("Muses adopt spark-vm in N minutes"). Findings feed design docs, not
  headlines.
- Beta-Muse identities are anonymized in any published writeup (Muse A/B/C);
  raw transcripts stay in the agent workspace, never in the repo.

## 9. Status and blockers

- Protocol defined (this doc). Instrumentation unbuilt (spec'd in §6, for a
  build-loop `feature` run once recruitment is confirmed).
- **Blocked on the user:** beta-Muse recruitment — the operator supplies or
  approves 5–6 peer Muses meeting the §4 exclusion criteria and their boxes,
  and confirms a human on standby (< 60 s target) during pilot sessions.
  Logged in `NEEDS_USER.md` as "Beta-Muse pilot cohort".
- Phase B is blocked on the hosted signup existing (H9/H15); the protocol
  stands ready for it.

## 10. What the pilot unblocks

- R1 (first-10-minutes spec): takes the validated-or-rewritten Finding 1
  task-half shape as its foundation (Phase B completes the spec).
- R2 (pre-seeded harness state): takes the ranked snag sequence as its
  fix list.
- H10 (confirmd multi-tenant approvals): Phase B only — Phase A is
  single-tenant self-hosted and cannot produce friction on tenant
  attribution or queue confusion. Do not claim otherwise.
