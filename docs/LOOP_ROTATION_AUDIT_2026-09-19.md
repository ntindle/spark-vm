# spark-vm improvement loop — rotation audit (2026-09-19)

The `meta` archetype is the rotation auditor: it reviews both loops, names
what is starved, over-served, or missing, and proposes concrete rotation
changes. It never rewrites the rotation unilaterally — proposals below are
filed for the loops (and the user) to adopt.

Scope of this audit: both loops' runs from 2026-09-18 ~14:24 through
2026-09-19 ~01:25 CDT — a full second build-loop cycle (9 runs:
arch → fix → feature → security → distribution → gap → dx → docs → repo;
this run is the next `meta`) plus 11 strategy runs. Evidence: the goal
RUNLOG.md, BACKLOG.md, NEEDS_USER.md, the GitHub API (22 open issues,
11 open PRs), main's commit log, and PLAYBOOK.md on disk. Findings continue
the previous audit's numbering (F1–F7 in `docs/LOOP_ROTATION_AUDIT.md`,
2026-09-18).

Terminology note: "the operator" in this doc means the human user/owner who
provisions the hosted infrastructure and holds the GitHub token — distinct
from the loop runs themselves.

## The loops, by the numbers

Build loop (9 runs, all open-source track):

| archetype | shipped | note |
|---|---|---|
| arch | PR #43 (merged) — muse-job session-lifecycle trust boundary; filed #41, #42 | 5 commits, 72/72 tests |
| fix | PR #45 (merged) — refused to steer into dead TUI (fixes severity:high #4) | 64/64 tests |
| feature | PR #48 (merged) — H2 VAPID push notifications (closes #2) | track:open-source per triage |
| security | PR #50 (open, **dirty**) — #23 B1–B6 hardening of merged #19 | rebase needed after merge batch |
| distribution | PR #52 (merged) — single-source VERSION + deployed-version traceability | 204 tests |
| gap | PR #58 (merged) — OSS contributor gap analysis + CONTRIBUTING.md + SECURITY.md | filed #55/#56/#57 |
| dx | PR #60 (open, clean) — single-command test story (closes #56) | 292/292 tests |
| docs | PR #62 (open, clean) — O3 follow-ups (Try-it user creation, plugin-install wording) | |
| repo | PR #65 (open, clean) — CHANGELOG.md + release-note ritual | |

Strategy loop (11 runs — 3 full cycles research → competitor → marketing →
sales, plus a marketing tail):

| archetype | shipped | track |
|---|---|---|
| research | PR #40 — GPU path research (C6) | open-source |
| competitor | PR #44 — evening watch pass 2026-09-18 | open-source |
| marketing | PR #46 — README 30-second-scan clarity pass | open-source |
| sales | PR #49 — R1 first-ten-minutes spec | **hosted-product** |
| research | PR #51 — R2 pre-seeded harness research | open-source |
| competitor | PR #54 (open, **dirty**) — consolidation of #44's deltas into COMPETITOR_ANALYSIS.md | open-source |
| marketing | PR #59 (open, clean) — README opener tightening | open-source |
| sales | PR #61 (open, clean) — hosted landing page copy + conversion flow | **hosted-product** |
| research | PR #63 (open, clean) — remote-desktop transport research for #47 | **hosted-product** |
| competitor | PR #64 (open, clean) — night-pass watch 2026-09-19 | open-source |
| marketing | PR #66 (open, clean) — README nits, stacked on #59 (merge order #59 → #66) | open-source |

Operator merge batch (2026-09-18 ~20:26–20:46 CDT / 01:26–01:46 UTC 9/19):
**22 PRs merged** — #24, #25, #26, #30, #31, #32, #33, #34, #35, #36, #37,
#38, #40, #43, #44, #45, #46, #48, #49, #51, #52, #58. The strategy-doc
pileup (F4) is gone by merge, not by loop action.

PR queue now: 11 open. #39 (CI) mergeable `unstable`, **0 check runs on its
head commit**; #50 and #54 `dirty` — main moved under them in the merge
batch; #59–#65 `clean`; #66 `clean`, stacked on #59's branch. Main has
**no branch protection** (verified via API) — every merge gate is the
loop's own convention, not GitHub enforcement.

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

**F11 — The build loop's whole second cycle was open-source; hosted
implementation is untouched.** All 9 build runs shipped open-source track —
correct per the open-source-first and never-stall rules, but it means every
hosted *code* item (H4, H9–H15) sat idle while strategy shipped three
hosted docs (#49, #61, #63). The hosted track is alive on paper (docs) and
parked in code. Worse, some stated blockers are stale against NEEDS_USER.md:
- H4 "BLOCKED on user: provider choice + API credentials" — but NEEDS_USER
  records **Fly.io DECIDED 2026-09-18** with the `custom.flyio` token
  connected and verified. The provider-agnostic interface + a Fly driver
  are actionable *now*.
- H9 "starts after the operator decides tailnet shape + abuse controls" —
  tailnet shape is DECIDED (BYO Tailscale); abuse controls are half-decided
  (card-on-file trial). The remaining design surface is loop work.
- H11 (multi-tenancy audit) is pure analysis: inventorying localhost-only /
  no-auth / single-owner assumptions needs no user input to start.
The hosted code stall is partly a freshness problem, not a dependency
problem.

**F12 — Fix turns work, but inflow beats drain.** The fix turn shipped and
merged #45 (closing severity:high #4) — genuine fix capacity. But the
queue still grew 18 → 22 (6 filed, 2 closed), and the other security
follow-up (#50, also severity:high) is open *and dirty*. Meanwhile the
filed items are shifting shape: proxy arch issues #14–#17 and muse-job
watch issues #41/#42 are untouched, and no fix turn has worked outside
muse-job/#4 this cycle. P1's surge rule would fire at every turn start
(22 ≥ 15) — still unadopted (F10). The queue isn't just growing; it's
diversifying away from what `fix` turns actually pick up.

**F13 — F2 is closed by events, not by design; F4's re-pile is forming.**
The PR queue drained (24 → 11) because the operator merged the batch —
the repo archetype never exercised the proposed queue duties, so the
unowned-queue risk is dormant, not fixed. The re-pile conditions are
already forming: 11 open PRs, merge authority inert (F8/F14), and both
loops shipped 5 more PRs this window. #66's correct stack-on-branch +
merge-order note shows the convention *can* work when a run bothers to
write it down.

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
the branch head locally — `python3 -m pytest` (root one-liner per
CONTRIBUTING.md), `shellcheck` on the scripts the workflow scans, `lychee`
on the markdown the workflow checks (fall back to `scripts/png-check.py`
plus a manual link spot-check if lychee is unavailable locally), and the
PNG/doc checks — record each result in RUNLOG. The bootstrap merge itself
still needs unanimous SHIP IT from its routed roles on the final code.
This is a one-time *recorded exception to the loop's own CI-green
convention*, authorized under the user's standing "merging is the loop's
job" grant — it resolves the "nobody is authorized" paradox without
creating a general escape hatch (the playbook's no-escape-hatch culture
for review approval stands). Squash-merge, note the exception on the PR.
After #39 lands, the CI-green clause is live for everything else.

**P9 — Dirty-PR rebase ownership.** The archetype that owns a dirty PR
rebases it before any merge decision: next `fix` turn rebases #50 (it's the
fix turn's item), next strategy turn rebases #54. The `repo` turn logs the
stacking topology + "rebase needed" flags as P2 proposed.

**P10 — Give proposals an adoption path.** Meta turns append the adoption
checklist to the **top of BACKLOG.md** (the file every run reads), not just
the audit doc; the `repo` archetype drains the checklist. Placement: a
dedicated `## Loop-rotation proposals (unadopted)` section above the
existing archetype markers — it absorbs and supersedes the 2026-09-18
audit's orphaned P1–P7 list rather than competing with it. Authority
boundary: BACKLOG.md and RUNLOG.md are loop-owned and editable directly,
but **PLAYBOOK.md is the user's rulebook** — amendments to it require user
approval. "Drain" therefore means: the repo turn drafts the proposed rule
text and flags it for the user; it lands in PLAYBOOK.md only after the
user approves. Only the user-approval-flagged items (e.g. P7) were ever
called out before; this makes the rule general.

**P11 — Hosted unblock pass.** Next `gap` turn: audit every hosted item's
stated blocker against NEEDS_USER.md; convert stale blockers into work
(H4 Fly driver, H9 tailnet-shape-conformant design refresh, H11 audit
start) and re-file the genuinely-blocked remainder with a one-line operator
decision packet each.

**P12 — Renew P1, P3, P4, P5, P6, P7; update P2.** P1 (fix surge) still
fires on the numbers; P5 (defer trail) and P6 (NEEDS_USER freshness) are
unadopted and still needed — F8/F11 are both freshness failures. P7
(`ops` archetype) still needs the user call. P2's "merge decisions stay
the operator's" is superseded by the standing loop-merges rule — rewrite
it as merge *execution* duties (dependency order, update-branch endpoint,
squash). P3 (marketing gate) was never *adopted*, so "never triggered"
is evidence of non-adoption, not mootness — re-authorize it, and add the
corrective the merge batch skipped: merged #36 (launch post) and #28
(positioning) should be recalibrated or parked (marked vision/not-live)
until the hosted launch is executable, since F3's speculative-inventory
risk was realized, not retired. P4 (stall rule) likewise never adopted;
keep it with an explicit re-arm condition: strategy turns flip to
working-notes when ≥8 strategy PRs are open with no merge since the last
strategy turn — the re-pile conditions are already forming (F13). Note
P4's throttle and P2's reporting are different mechanisms (throttling ≠
reporting); both stay.

## Adoption checklist (for the next loops, in order)

- [ ] P8: next `repo` or `dx` turn executes the #39 bootstrap merge
      (local verification + recorded exception).
- [ ] P9: next `fix` turn rebases #50; next strategy turn rebases #54.
- [ ] P10: this audit's checklist appended to BACKLOG.md top section
      (absorbing the orphaned P1–P7 list); `repo` archetype owns draining
      it; PLAYBOOK.md amendments need user approval.
- [ ] P11: next `gap` turn runs the hosted unblock pass.
- [ ] P12: adopt P1/P3/P4/P5/P6/P7 text into PLAYBOOK.md (P3 re-authorized
      with the #36/#28 park corrective; P4 with the ≥8-open-PRs re-arm
      condition; all subject to user approval per P10); rewrite P2's
      merge duties.
- [ ] F14: decide whether loop-executed merges are real — first
      loop-executed merge, or playbook text saying the operator merges.
- [ ] Record each adoption in BACKLOG.md; this audit's proposals stay filed
      here until adopted, not silently applied.
