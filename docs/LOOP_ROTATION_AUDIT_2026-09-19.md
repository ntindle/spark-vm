# spark-vm improvement loop — rotation audit (2026-09-19)

The `meta` archetype is the rotation auditor: it reviews both loops, names
what is starved, over-served, or missing, and proposes concrete rotation
changes. It never rewrites the rotation unilaterally — proposals below are
filed for the loops (and the user) to adopt.

Scope of this audit: both loops' runs from 2026-09-18 ~14:24 through
2026-09-19 ~01:25 CDT, plus the operator's merge batch in between.
Evidence: the goal RUNLOG.md, BACKLOG.md, NEEDS_USER.md, the GitHub API
(22 open issues, 11 open PRs), main's commit log, and PLAYBOOK.md on disk.
Findings continue the previous audit's numbering (F1–F7 in
`docs/LOOP_ROTATION_AUDIT.md`, 2026-09-18).

## The loops, by the numbers

Build loop (10 archetypes): **1 run** since the last audit — `repo`
(CHANGELOG.md + release-note ritual, PR #65, clean, SHIP IT all roles).
No fix, security, or distribution turn ran in the window.

Strategy loop (research → competitor → marketing → sales): **3 runs** —
`research` (desktop transport for #47, PR #63), `competitor` (night-pass
watch, PR #64), `marketing` (README nits stacked on #59, PR #66). All three
clean + unanimous SHIP IT, all three open.

Operator merge batch (2026-09-18 evening): **19 loop PRs merged**
(#24–#26, #30–#33, #35–#38, #40, #43–#46, #48, #49, #51, #52), plus the
MIT LICENSE commit outside the loop (closed #55). The strategy-doc pileup
(F4) is gone by merge, not by loop action.

PR queue now: 11 open. #39 (CI) mergeable `unstable`, **0 check runs on its
head commit**; #50 (muse-job B1–B6 hardening) and #54 (competitor
consolidation) `dirty` — main moved under them in the merge batch; #59–#65
`clean`; #66 `clean`, stacked on #59's branch (merge order #59 → #66 noted).
Main has **no branch protection** (verified via API) — every merge gate is
the loop's own convention, not GitHub enforcement.

Issue queue: 18 → 22. Closed: #2 (merged #48), #55 (LICENSE). Filed: #41,
#42 (muse-job watch arch), #47 (live machine control), #53 (automate
releases from VERSION), #56 (single-command tests, already answered by PR
#60), #57 (seed `good first issue`).

## Findings

**F8 — The merge convention is in a chicken-and-egg deadlock.** The
standing rule ("merging is the loop's job": merge when CI green +
mergeable-clean + unanimous SHIP IT) cannot fire: there is no CI on main,
so no PR can ever be "CI green" — and #39 *is* the CI PR. Three consecutive
runs (00:27, 00:54, 01:05) left clean, unanimously-signed PRs open citing
"no CI on main". The cited sub-blocker is stale: NEEDS_USER.md records the
`workflow` token scope as RESOLVED 2026-09-18 and PR #39 opened the same
day — the loop's RUNLOG entries kept quoting the old blocker after the
fact. The real gate is a bootstrap judgment call nobody is authorized to
make under the current rule text. Until #39 merges, the loop's merge
authority is inert.

**F9 — The merge batch left the two riskiest PRs conflict-blocked.**
#50 (B1–B6 hardening — the fix turn's highest-priority *security* item,
fixing the merged-#19 findings from issue #23) and #54 are both `dirty`
after the operator merges. #50 especially cannot afford to rot: it is the
loop's answer to a severity:high security review of already-merged code,
and every day it sits unmerged the vulnerable code stays live. This is F2's
predicted cost, realized.

**F10 — Zero of the P1–P7 proposals were adopted.** The 2026-09-18 audit's
adoption checklist is entirely unchecked; PLAYBOOK.md contains none of the
proposed rule text (verified by grep). The meta archetype files proposals
into a doc the next loops evidently don't read — the loops read BACKLOG.md
and PLAYBOOK.md every run, and neither carries the proposals. An advisory
turn with no adoption mechanism is a write-only audit log.

**F11 — The hosted track is parked behind stale blockers, not real ones.**
Since the last audit: 0 hosted-track items advanced (both loops shipped
open-source; `last_shipped_track: open-source` held all four runs). The
"never stall + open-source-first" rules correctly keep the loop moving, but
they systematically route around the hosted half of the goal. Worse, some
stated blockers are stale against NEEDS_USER.md:
- H4 "BLOCKED on user: provider choice + API credentials" — but NEEDS_USER
  records **Fly.io DECIDED 2026-09-18** with the `custom.flyio` token
  connected and verified. The provider-agnostic interface + a Fly driver
  are actionable *now*.
- H9 "starts after the operator decides tailnet shape + abuse controls" —
  tailnet shape is DECIDED (BYO Tailscale); abuse controls are half-decided
  (card-on-file trial). The remaining design surface is loop work.
- H11 (multi-tenancy audit) is pure analysis: inventorying localhost-only /
  no-auth / single-owner assumptions needs no user input to start.
The hosted stall is partly a freshness problem, not a dependency problem.

**F12 — Fix starvation persists (F1 unchanged).** Queue 18 → 22; the only
fix-turn output in the window is #50, which is open *and dirty*. muse-job
security/medium issues (#5–#13), proxy arch issues (#14–#17), and #56 (now
answered by PR #60, awaiting merge) all sit. The P1 surge rule would have
fired (queue ≥ 15 at every turn start) — it was never adopted (F10).

**F13 — F2/F4 are closed by events, not by design.** The PR queue drained
(24 → 11) and the strategy pileup is gone because the operator merged the
batch — the repo archetype never exercised the proposed queue duties, and
P4's stall rule never triggered. The underlying risks (unowned queue,
stacking without convention) are dormant, not fixed: #66's correct
stack-on-branch + merge-order note shows the convention *can* work when a
run bothers to write it down.

**F14 — The "loop merges" rule still has no exercised path.** Adopted as
standing policy 2026-09-18 ("merging is the loop's job"), but no run since
has merged anything — every merge in the window was the operator's, and
runs keep defaulting to "left open per loop convention". If the rule is
real, the first loop-executed merge needs to happen; if the operator
prefers to keep merging, the playbook should say so instead of leaving
runs in a wait-for-green-CI limbo.

## Proposals (for the loops to adopt — not applied by this audit)

**P8 — One-time CI bootstrap merge.** Merge PR #39 on Engineering judgment,
not CI-green: re-run the workflow's four jobs' underlying commands against
the branch head locally (pytest, shellcheck, lychee, PNG check), record the
results in RUNLOG, squash-merge, and note the exception on the PR. After
#39 lands, the CI-green clause is live for everything else. This is a
bootstrap, not a precedent.

**P9 — Dirty-PR rebase ownership.** The archetype that owns a dirty PR
rebases it before any merge decision: next `fix` turn rebases #50 (it's the
fix turn's item), next strategy turn rebases #54. The `repo` turn logs the
stacking topology + "rebase needed" flags as P2 proposed.

**P10 — Give proposals an adoption path.** Meta turns append the adoption
checklist to the **top of BACKLOG.md** (the file every run reads), not just
the audit doc; the `repo` archetype drains the checklist (propose text,
run it past the user where the audit says "needs user approval").

**P11 — Hosted unblock pass.** Next `gap` turn: audit every hosted item's
stated blocker against NEEDS_USER.md; convert stale blockers into work
(H4 Fly driver, H9 tailnet-shape-conformant design refresh, H11 audit
start) and re-file the genuinely-blocked remainder with a one-line operator
decision packet each.

**P12 — Renew P1, P5, P6, P7; update P2; retire P3, P4 as moot.**
P1 (fix surge) still fires on the numbers; P5 (defer trail) and P6
(NEEDS_USER freshness) are unadopted and still needed — F8/F11 are both
freshness failures. P7 (`ops` archetype) still needs the user call. P2's
"merge decisions stay the operator's" is superseded by the standing
loop-merges rule — rewrite it as merge *execution* duties (dependency
order, update-branch endpoint, squash). P3 (marketing gate) never
triggered and the launch copy it gated is now merged — retire. P4 (stall
rule) never triggered; the pileup drained by merge — retire, keep the
working-note pattern as convention.

## Adoption checklist (for the next loops, in order)

- [ ] P8: next `repo` or `dx` turn executes the #39 bootstrap merge
      (local verification + recorded exception).
- [ ] P9: next `fix` turn rebases #50; next strategy turn rebases #54.
- [ ] P10: this audit's checklist appended to BACKLOG.md top section;
      `repo` archetype owns draining it.
- [ ] P11: next `gap` turn runs the hosted unblock pass.
- [ ] P12: adopt P1/P5/P6/P7 text into PLAYBOOK.md; rewrite P2's merge
      duties; strike P3/P4 as moot.
- [ ] F14: decide whether loop-executed merges are real — first
      loop-executed merge, or playbook text saying the operator merges.
- [ ] Record each adoption in BACKLOG.md; this audit's proposals stay filed
      here until adopted, not silently applied.
