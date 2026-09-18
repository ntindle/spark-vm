# spark-vm improvement loop — rotation audit (2026-09-18)

The `meta` archetype is the rotation auditor: it reviews both loops, names
what is starved, over-served, or missing, and proposes concrete rotation
changes. It never rewrites the rotation unilaterally — proposals below are
filed for the loops (and the user) to adopt.

Scope of this audit: both loops' runs from 2026-09-18 02:24 through
2026-09-18 14:24 CDT (first full build-loop cycle under the two-loop
structure: arch → fix → feature → security → distribution → gap → dx →
docs → repo, plus two full strategy cycles). Evidence: the goal
RUNLOG.md, the GitHub API (18 open issues, 11 open PRs, 5 merged today),
and PLAYBOOK.md on disk.

## The loops, by the numbers

Build loop (10 archetypes, ~10h per cycle):

| archetype | runs | shipped | note |
|---|---|---|---|
| arch | 1 | PR #18 (merged) + issues #14–#17 filed | |
| fix | 1 | PR #19 (merged; final Security NOT SHIP IT → #23) | 1 deferred follow-up |
| feature | 1 | PR #20 confirmd refresh (merged) | mostly issue-driven work |
| security | 1 | DEFERRED (#23 B1–B6; Architecture blocked) | re-queued for next security turn |
| distribution | 1 | PR #29 (merged; fixes #22) | |
| gap | 1 | PR #31 (open) | H9–H15 filed |
| dx | 1 | PR #33 (open); O1 CI blocked on token scope | pivoted per playbook, not stalled |
| docs | 1 | PR #35 (open) | |
| repo | 1 | triage pass (labels, milestone, PR health) | no code PR — fine |
| meta | 1 | this audit | |

Strategy loop (research → competitor → marketing → sales, 2 full cycles + 1
pending): 8 runs, 8 docs PRs — #25, #26, #28 (merged), #30, #32, #34
(stacked on #26's branch), #36, #37 (open). Next: research.

Issue queue: 18 open (#2, #4–#17, #21, #23, #27). 13 touch `muse-job`;
7 carry the `security` label; severity:high = 2 (#4, #23), medium = 7, low = 1.
Today alone filed 8 new issues (#14–#17, #21, #23, #27, plus the #22 auto-deploy
one now closed by #29). The `fix` archetype drains ~1–2 issues per 10h turn;
the queue is growing.

PR queue: 11 open (#24–#26, #30–#37), all created today. Merge decisions are
the operator's (parent loop); the loops produce ~2 PRs/hr at peak. Stacking
has begun (#34 on #26's branch) without an explicit stacking convention —
merge-conflict risk rises with every unmerged doc PR.

## Findings

**F1 — Fix capacity is starved relative to issue inflow.** One fix turn per
~10h cycle vs 18 open issues and 8 filed today. At current rates the queue
never drains. The `fix` turn correctly works the highest-priority item, but
the rotation gives it no way to surge.

**F2 — The PR queue is a second backlog nobody owns.** 11 open PRs; the
`repo` archetype covers "merge hygiene" in routing but its one turn today
only did issue triage + a report-only health check. Stacked PRs (#34 on #26)
are landing without a documented stacking convention, and docs PRs touch
adjacent files — conflict risk grows every unmerged hour.

**F3 — Marketing is outrunning the product's maturity.** The marketing
archetype has shipped a publish-ready launch post (#36) and positioning copy
(#28) for a hosted product whose launch decision is still in NEEDS_USER.md
(hosting + domain, billing, abuse controls all unresolved). Announcement copy
written before the announcement decision is speculative inventory.

**F4 — Strategy docs are piling onto an unmerged base.** Eight strategy PRs
in ~8h, seven still open. Several cite each other (#36 cites POSITIONING.md
from #28). Docs that depend on other open docs are hard to review in
isolation; every unmerged hour increases the rebase burden.

**F5 — Deferrals leave orphan state.** The 07:24 security deferral never
pushed its WIP branch; the 09:24 distribution run had to discover and adopt
an orphaned branch manually ("completed the orphaned branch from the 08:24
run"). A defer that vanishes from the repo is indistinguishable from a lost
run.

**F6 — NEEDS_USER.md has no freshness owner.** It holds ~8 items (workflow
scope for CI, Neo provider + creds, sentinel endpoint/auth, hosting + domain,
billing, tailnet shape, abuse controls, pilot recruitment). Nothing verifies
whether an item was resolved between turns — e.g. the O1 CI block could be
retested cheaply, but no archetype owns re-probing.

**F7 — PLAYBOOK/RUNLOG discrepancy (06:54 note) is resolved — no file edit
needed.** The earlier note claimed RUNLOG asserted a playbook amendment the
file didn't contain. On disk, PLAYBOOK.md §"Process" already reads:
*"Review continues until the team genuinely approves — autonomous merge
always requires an explicit `SHIP IT` from every routed role on the final
code, no matter how many review rounds it takes. There is no round-count
escape hatch."* The genuine-approval rule the loops are following IS the
file's rule. Recording this here closes the discrepancy.

## Proposals (for the loops to adopt — not applied by this audit)

**P1 — Give `fix` a surge rule.** When open issues ≥ 15 at turn start, the
fix turn works TWO items (the second must be small — severity:low or a
half-hour slice) instead of one. Auto-deactivates when the queue drops below
10. No rotation reorder; just a conditional double-shot.

**P2 — Formalize PR-queue duties in the `repo` archetype.** Each repo turn:
refresh mergeability on the 3 oldest open PRs, note the stacking topology
(which branch stacks on which), and flag any open PR that has drifted from
main with a concrete "rebase needed" note in RUNLOG. Merge decisions stay
the operator's; hygiene becomes someone's job.

**P3 — Gate the marketing archetype on launch-readiness.** Until the
hosted-launch decision items in NEEDS_USER.md (hosting + domain, billing,
abuse controls) are resolved, marketing turns ship contributor-facing assets
only: demo GIFs, README polish, changelog highlights, musebook updates. No
new publish-ready announcement or pricing-as-commitment copy. When the launch
decision lands, the gate lifts automatically.

**P4 — Cap unmerged strategy docs (merge-pressure valve).** If ≥ 8 strategy
PRs are open with no merge since the last strategy turn, the next strategy
turn does NOT open a new PR: it writes a working note to `agent_notes/` and
logs the stall in RUNLOG. The research keeps accumulating; the pile stops
growing until the operator catches up.

**P5 — Defer with a visible trail.** A deferral must push the WIP branch with
a `draft/` prefix and name it in the BACKLOG.md entry for that item, so the
next turn of the same archetype adopts rather than rediscovers. Unpushed
deferrals are lost work, not parked work.

**P6 — NEEDS_USER freshness check rides with `repo`.** Each repo turn
re-probes the cheaply-verifiable items (e.g. retry the workflow-scope API
write for O1; check whether any NEEDS_USER host/account item now has an
operator answer) and re-queues anything unblocked. The audit note for today:
O1 is still blocked (verified by the dx run's API 404).

**P7 (advisory, needs user approval) — consider an `ops` archetype.**
The reference deployment now has live services on the box (confirmd at
100.65.241.20:8443, proxy swapd, deployed copy drift once caused a visible
bug — see #22). Nothing in the rotation owns live-service health checks,
deployed-version drift detection, or incident response. A read-only
monitor-and-report turn fits the current boundaries (no auto-deploy on the
loop's own authority). Filed as a proposal; adding an 11th archetype lengthens
the cycle, so weigh against P1's surge rule first.

## Adoption checklist (for the next loops, in order)

- [ ] Add P1 surge rule text to PLAYBOOK.md `fix` archetype description.
- [ ] Add P2 PR-queue duties to PLAYBOOK.md `repo` archetype description.
- [ ] Add P3 marketing gate to PLAYBOOK.md `marketing` archetype description.
- [ ] Add P4 strategy-stall rule to PLAYBOOK.md strategy-loop setup.
- [ ] Add P5 defer-trail requirement to PLAYBOOK.md `Ship` section.
- [ ] Add P6 freshness duty to PLAYBOOK.md `repo` archetype description.
- [ ] Decide P7 (`ops` archetype) — user call.
- [ ] Record each adoption in BACKLOG.md; this audit's proposals stay filed
      here until adopted, not silently applied.
