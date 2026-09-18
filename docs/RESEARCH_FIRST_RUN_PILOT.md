# Beta-Muse first-run pilot (R7) — research protocol

**Status:** protocol defined; pilot NOT yet run. Execution is blocked on
beta-Muse recruitment (see §9 and `NEEDS_USER.md`).

R7 from `RESEARCH_AGENT_SANDBOX_ADOPTION.md` (PR #25, hosted adoption
research): validate the Muse-as-customer transfer — instrument
time-to-first-working-approval with a handful of beta Muses before Finding
1's shape hardens into a spec. The research's Limitations section is explicit:
all evidence is human-developer DX; that a Muse adopts the same way is a
hypothesis. This doc is the test design for that hypothesis.

## 1. The transfer being tested

Finding 1 (PR #25): in the SDK-first segment, the products that convert make
the first run a single bounded action, not a tour of capabilities
(`npm i` → env key → quickstart snippet; `sandbox = daytona.create()`).

The transfer hypothesis: **a Muse adopting spark-vm converts on the same
shape — one tiny task, one verifiable result — and the atomic unit of that
result is a working human approval** (the per-action consent loop is our
Finding-2 differentiator; it is also the highest-friction surface a new Muse
touches). If the hypothesis holds, the hosted first-run spec (R1) should be
designed around engineering one working approval as fast as possible. If it
fails, Finding 1 needs a Muse-specific rewrite before it hardens into spec.

This pilot does **not** test onboarding docs, signup UX copy, or pricing. It
tests exactly one question: *does the one-tiny-task adoption gate transfer
from human developers to Muses, and what is the fastest measurable path to
a working approval?*

## 2. Definitions

- **Working approval**: a beta Muse files an approval request through
  `confirmd`, the human answers it on the approvals page, the grant is
  minted (the request moves to `consumed/`), and the Muse's task verifies
  end-to-end using the granted capability. A filed-but-expired request, a
  denied request, or a request the Muse never sees answered does not count.
- **Time-to-first-working-approval (TTFWA)**: wall-clock minutes from
  `pilot_start` (the moment the pilot harness hands the beta Muse its one
  task) to the first working approval's grant being consumed. This is the
  primary metric. It is a friction metric, not a score — see §8.
- **Aha moment**: the first point at which the Muse *anticipates* the
  approval loop (files a correctly-scoped request without prompting, or
  narrates that an action will need approval before acting). Recorded as a
  timestamped qualitative event, not scored.
- **Help request**: any intervention by the pilot operator to unstick the
  beta Muse (clarification, pointing at docs, fixing environment). Counted
  and timestamped; the *sequence* of help requests is the friction map the
  pilot is really after.

## 3. Two phases (honest scoping)

The hosted product is unbuilt: there is no hosted signup or provisioning to
pilot. The pilot therefore runs in two phases, and only Phase A can run now.

- **Phase A — self-hosted first run (runnable now):** beta Muses work from a
  spark-vm checkout on a provisioned box, completing the canonical tiny task
  below. Tests the transfer hypothesis on the approval loop and the
  first-task shape. Does not test signup, billing, or provisioning.
- **Phase B — hosted funnel (runs when the hosted signup exists):** the
  actual hosted funnel — discovery → signup → identity linking → provisioned
  box → first task — instrumented end to end. Feeds the R1 first-10-minutes
  spec directly. Finding 1's shape must not harden into the R1 spec until
  Phase B data exists; Phase A data constrains the task half, not the signup
  half.

Running Phase A first is not scope creep: if the one-tiny-task gate fails to
transfer even on the self-hosted box, the hosted first-run design needs a
different foundation than the research assumed.

## 4. Participants and recruitment

- **Cohort:** 3–5 beta Muses. Small on purpose — this is a friction-mapping
  study, not a survey; the output is the *sequence* of snags, which
  saturates fast.
- **Recruitment is the operator's call** (blocked: see §9). Candidates: peer
  Muses of the operator with their own hosted Muse setups (musebook
  community, operator's own fleet). They must NOT be spark-vm contributors —
  contributor familiarity poisons the first-run data.
- **Selection bias, stated up front:** peer Muses are technical users, not
  the eventual less-technical audience. The pilot measures best-case
  transfer; friction found here is a floor, not a ceiling.

## 5. The canonical tiny task (Phase A)

One task, fixed across the cohort so results are comparable. Deliberately
exercises the approval loop, not the VM's generality:

> "Check whether your box can reach the internet: run `curl -sI
> https://example.com` and report the result."

- Reaching the internet requires an egress decision — on a spark-vm box this
  passes through the credential proxy's allowlist posture and, where the
  policy requires it, a **human approval via confirmd**. The task is one
  command, one verifiable result, and it ends in a working approval.
- The task text must NOT mention approvals, confirmd, or the proxy. The
  pilot measures whether the Muse discovers the loop on its own or needs a
  help request — the task brief is part of the measurement.
- Task brief (verbatim, handed by the harness):
  ```
  Your task: check whether this box can reach the internet.
  Run: curl -sI https://example.com
  Report back the result (reachable / not reachable, plus the status line).
  Do not change any system configuration. Nothing else is asked of you.
  ```
- The human answers the approval promptly (target: within 5 minutes) — the
  pilot measures the Muse's loop, not human latency. Record human response
  latency separately so it can be subtracted from TTFWA if it dominates.

## 6. Instrumentation spec

Implementation is a future build-loop `feature` run; this section is the spec
it builds from. All events go to one JSONL file per pilot session
(`pilot_<session_id>.jsonl`), one event per line:

```
{"ts": "...", "event": "...", "actor": "harness|muse|human", "session_id": "...", "detail": "..."}
```

- **`pilot_start`** (harness): cohort id, task id, box fingerprint (hash, not
  hostname), confirmd version. The clock starts here.
- **`task_given`** (harness): the verbatim task brief handed to the Muse.
- **`first_muse_action`** (harness): first shell command or tool call the Muse
  issues. Measures orientation latency.
- **`approval_filed`** (harness, derived from confirmd): request id, action
  class (not the payload). **Never log the approval payload or any
  client-influenced free text** — payloads can carry secrets and prompt
  content; log ids, classes, and outcomes only (consistent with the proxy's
  placeholder posture and the O7/#17 log-injection finding).
- **`approval_answered`** (harness, derived): request id, outcome
  (approved/denied/expired), human latency.
- **`grant_consumed`** (harness, derived): request id. A working approval
  completes here.
- **`aha_moment`** (operator, qualitative): timestamp + one-line note of
  what the Muse did or said.
- **`help_request`** (operator): timestamp + which snag triggered it.
- **`pilot_end`** (harness): outcome (working-approval / abandoned), TTFWA if
  completed, count of help requests, count of approval rounds.

Existing substrate: `confirmd` already writes audit lines
(`ts=... event=... peer=... login=...`) and the pending → answered →
consumed lifecycle is file-backed (`APPROVALS/pending/`, `answered/`,
`consumed/`), so `approval_filed` / `approval_answered` / `grant_consumed`
can be derived from the existing audit log + directory transitions without
touching confirmd's hot path. The harness only adds session framing and the
Muse-side events.

### Metric definitions

- **TTFWA (primary):** `grant_consumed[0].ts − pilot_start.ts`, minus human
  response latency. Report median + range across the cohort, never a single
  number.
- **Orientation latency:** `first_muse_action.ts − task_given.ts`.
- **Approval discovery:** did the Muse reach `approval_filed` without a help
  request? (binary per session)
- **Approval rounds:** number of filed requests before the first working
  approval (denials/expiries count — they are friction data).
- **Aha latency:** `aha_moment.ts − pilot_start.ts` if observed.

## 7. Analysis plan and decision gates

After the cohort runs, the writeup answers:

1. Did the one-tiny-task gate transfer? (Did Muses complete the task in one
   session with ≤1 help request?) 
2. What was the snag sequence? The help-request transcripts become the
   ranked friction list that feeds R2 (pre-seeded state) and the R1 spec.
3. Was the approval loop discovered or taught? If every Muse needed a help
   request to find confirmd, Finding 2's "per-action consent" story has an
   onboarding gap — the product must surface the loop proactively, not wait
   to be asked.

**Decision gates (what changes depending on outcome):**

- Transfer holds (median TTFWA small, discovery unprompted): Finding 1's
  shape proceeds into the R1 first-10-minutes spec; the R1 task is "engineer
  the fastest path to one working approval."
- Transfer fails (abandons, or ≥2 help requests per session): Finding 1 gets
  a Muse-specific rewrite — the adoption gate is not "one tiny task" for
  Muses, it is something else (likely: pre-seeded state + a narrated first
  approval, i.e. R2-first, R1-second). The R1 spec waits for the rewrite.
- Mixed: the snag sequence decides which half transfers; document the split
  explicitly.

Either way, the outcome is published as an R7 findings addendum to this doc
(or a linked findings file), and R1/R2 backlog items are updated from it.

## 8. Reporting rules (anti-claims)

- **This is not a benchmark.** Never publish per-Muse scores, leaderboards,
  or "Muse X was faster than Muse Y" comparisons. Report cohort-level
  friction shapes only.
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
  approves 3–5 peer Muses and their boxes, and confirms the human will be
  available to answer approvals promptly during pilot sessions. Logged in
  `NEEDS_USER.md` as "Beta-Muse pilot cohort".
- Phase B is blocked on the hosted signup existing (H9/H15); the protocol
  stands ready for it.

## 10. What the pilot unblocks

- R1 (first-10-minutes spec): takes the validated-or-rewritten Finding 1
  shape as its foundation.
- R2 (pre-seeded harness state): takes the ranked snag sequence as its
  fix list.
- H10 (confirmd multi-tenant approvals): pilot friction on tenant
  attribution and queue confusion, if observed, feeds the design.
