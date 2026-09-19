# spark-vm improvement loop — rotation audit, afternoon pass (2026-09-19)

> **Standing note for meta audits:** this turn is advisory. It proposes
> rotation changes as backlog/PR items; it does not rewrite the rotation,
> and per the P10 boundary (PLAYBOOK.md is the user's rulebook) any
> playbook-rule proposals below land only after user approval. The audit
> doc itself is left open for the `repo` turn's merge sweep once CI is
> green — the `meta` turn does not merge its own audit.

The `meta` archetype is the rotation auditor: it reviews both loops, names
what is starved, over-served, or missing, and proposes concrete rotation
changes. Findings continue the numbering of the two previous audits
(F1–F7 in `docs/LOOP_ROTATION_AUDIT.md`, 2026-09-18; F8–F14 in
`docs/LOOP_ROTATION_AUDIT_2026-09-19.md`, 2026-09-19 ~01:25 CDT).

Scope of this audit: both loops' runs from 2026-09-19 ~01:25 CDT (the last
audit) through ~15:25 CDT — a full third build-loop cycle (9 runs:
arch → fix → feature → security → distribution → gap → dx → docs → repo;
this run is the next `meta`) plus 5 strategy runs. Evidence: the goal
RUNLOG.md, BACKLOG.md, NEEDS_USER.md, the GitHub API (48 open issues,
15 open PRs), main's commit log, and the merged-PR record on main.

Terminology note: "the operator" means the human user/owner who provisions
the hosted infrastructure and holds the GitHub token — distinct from the
loop runs themselves.

## The loops, by the numbers

Build loop (9 runs — **all open-source track, third full cycle in a row**):

| archetype | shipped | note |
|---|---|---|
| arch | PR #79 (merged `25f2489`) — confirmd CSRF nonce ring + hardening slice; closes #75; filed #78, #80 | 85/85 tests |
| fix | #50 rebased (P9) + merged `beace9e` — B1–B6/#23 muse-job hardening; closes #23 | 123/123 tests |
| feature | PR #83 (open) — H8 multi-agent orchestration doc (filing slice) | |
| security | PR #97 (merged `e2feeb2`) — O2 cred/proxy sweep: credlib traversal fix, 0600 audit logs, SSRF fixes; filed #85–#96 | 76 + 13 tests |
| distribution | PR #98 (open) — O12 automated GitHub releases from VERSION (closes #53) | 27 tests |
| gap | PR #100 (open) — P11 hosted unblock pass: stale blockers converted, operator packets filed | |
| dx | #39 fixed (P8) + merged `33950e2` — CI lands on main, green | |
| docs | PR #110 (merged `bdac62a`) — O13 trust & transparency doc (Docker escape week) | |
| repo | merged #54 (`1c244be`), #59 (`78cda70`), #60 (`1111b20`), #66 (`724550e`) — first repo-turn merge batch under the standing rule | |

Strategy loop (5 runs this window):

| archetype | shipped | track |
|---|---|---|
| competitor (~05:30) | #54 rebased (P9 second half; later merged by the repo turn) | open-source |
| research | PR #101 (open) — org-policy vendor landscape, H16 research half | **hosted-product** |
| competitor | PR #102 (open) — midday watch (Docker escape-week deepens) | open-source |
| marketing | PR #109 (merged `ee6a733`) — demo asset 2: "secrets the agent never sees" GIF | open-source |
| sales | PR #111 (open) — H15 signup web UI + human dashboard spec; unanimous final SHIP IT, merge-blocked on #68 → #99 dependency order | **hosted-product** |

Merges in window: **11 loop-executed merges under green CI** —
#79, #97, #50, #39, #84, #109, #110 (own turns) + #54, #59, #60, #66
(repo turn). Main advanced to `724550e`; CI (4 jobs: python tests,
shellcheck, markdown link check, PNG smoke) is green on main since
`33950e2` — the first time the merge gate has been a live green signal.

PR queue: 15 open (#62, #63, #64, #65, #67, #68, #81, #82, #83, #98, #99,
#100, #101, #102, #111) — 11 merged out, 11 shipped in, net +4.

Issue queue: **22 → 48** (filed in window: #69–#74, #76–#78, #80 from the
arch turn; #85–#96 from the security sweep; #103–#108 from the dx turn =
28 filed; closed: #23, #56, #75 = 3. One-issue reconciliation gap vs the
48 observed — likely an operator-filed issue; noted, not investigated).

## Findings

**F8 — RETIRED.** The merge gate is no longer a red signal: #39's two
failing jobs were fixed on the branch (P8), CI is 4/4 green on main, and
the loop merged 11 PRs this window under the standing rule. The gate is
live and exercised.

**F9 — RETIRED.** #50 rebased and merged (`beace9e`, closes #23); #54
rebased and merged (`1c244be`). No dirty PRs remain in the queue.

**F10 — PARTIALLY ADDRESSED.** The proposals got *executed* ad hoc —
P8/P9/P11 done, P2's merge duties exercised by the repo turn (3-oldest
refresh, stacking topology, update-branch, merge-record comments), P10's
checklist section exists at the top of BACKLOG.md — but P1/P3/P4/P5/P6/P7
remain unadopted and P12 still needs user approval. The advisory gap is
narrower but alive: the loops now follow proposals as one-off instructions
rather than as standing rules.

**F11 — PERSISTS.** Third full build cycle, all nine runs open-source
track. The fixable half of F11 is fixed — P11's unblock pass retired the
stale blockers (H4 Fly driver, H9 design refresh, H11/H5 audit start,
H14(a) standalone push service are all actionable now) — but no build run
has taken a hosted *code* item. The open-source-first tie-break keeps
winning every tie; the hosted track stays alive in strategy docs (#101,
#111) and parked in build-loop code. This is now a choice, not a block.

**F12 — PERSISTS.** The queue grew 22 → 48 (+28 filed, −3 closed). The
filing machine (arch/security/dx turns filing 28 issues) outruns the fix
machine: this cycle's fix turn spent its capacity on rebase hygiene (#50)
rather than closing issues, and no fix turn has closed a newly-filed
issue since #4. The queue is also diversifying — confirmd (#69–#74,
#76–#78, #80), cred/proxy (#85–#96), deploy (#103–#108) — away from the
muse-job cluster `fix` turns actually pick up. P1's surge rule (≥15 open
issues) fires at every turn start; still unadopted.

**F13 — RETIRED.** The repo turn exercised the P2 queue duties this
window: refreshed the 3 oldest PRs, recorded the stacking topology
(#66 on #59's branch), used update-branch to green #66, posted
merge-record comments. The queue is owned now, not dormant.

**F14 — RETIRED.** Loop-executed merges are real: 11 this window (see the
merge list above), all on green CI + clean mergeable + documented
unanimous SHIP IT. The standing rule has an exercised path.

**F15 — NEW: the sign-off-documentation gate meets dependency order.**
PR #111 has unanimous final SHIP IT (Product/Design/Docs, 3 rounds), 4/4
green CI, clean mergeable — and cannot merge, because its declared
dependency order (#68 → #99 → #111) names two PRs that are CI-green and
clean but carry **no documented final sign-offs**. The merge rule is
per-PR; a dependency chain needs the gate on every link. Unmerged PRs
accumulate *review debt*: #68 and #99 shipped before the current
sign-off-documentation norm, and the only compliant path to merge #111
is a re-review pass on both — a full turn of work nobody scheduled. The
repo turn correctly left them open rather than forcing the merge, but
"left open with a note" is where the debt now sits.

**F16 — NEW: a review is complete only when its full report is in the
transcript.** The H15 round-1 Design full report arrived *after* round-2
reviewers were dispatched; the run briefly declared unanimous SHIP IT on
code that still had 4 live Design blockers, then had to do a round 3.
A completion notice without the handoff is not a review result. This is
a playbook-rule candidate (P14), not just a lesson — the failure mode is
structural to parallel reviewer dispatch.

**F17 — NEW (minor): tool-display illusions are a reviewer hazard.** The
dx turn's Docs and QA round-1 blockers were both false positives from
backslash doubling in tool-result display (a YAML `\\`, 2 bytes, misread
as 4); withdrawn with `od -c` byte evidence, lesson logged in AGENTS.md.
Byte-level claims need byte-level verification — reviewers should treat
display text as untrusted for escaping questions.

**F18 — NEW: the watch-doc delta pile is forming again.** #64, #82, #102
are three consecutive unmerged delta watches; consolidation into
`COMPETITOR_ANALYSIS.md` is queued as a competitor-turn follow-up but
hasn't happened. This is the F4 pattern at smaller scale: the corpus
convention ("watch docs are delta-only") assumes a consolidation pass
that the rotation hasn't scheduled.

## Proposals (for the loops to adopt — not applied by this audit)

**P13 — Sign-off debt travels with the blocked PR's archetype.** When a
merge-blocked note names dependencies lacking documented final sign-offs
(#68 → #99 → #111), the turn that declared the dependency order owns
clearing it: the next turn of that archetype re-reviews the dependency
heads and records sign-offs (or files the blockers), rather than every
later run re-discovering the block. Concretely: the next `sales` turn
re-reviews #68/#99 — or, if the repo turn prefers, it schedules that
re-review as a P2 queue item with an owner. "Left open with a note" must
name who clears it and when.

**P14 — Reviewer-report completeness** (playbook text — user approval
required per P10). A role's review counts as complete only when its full
report — verdict plus the blockers it claims — is in the worker's
transcript. A completion notice without the handoff is not a result.
Late-arriving reports reopen the round they belonged to; a SHIP IT
declared without the full report is provisional and must be re-confirmed
once the report lands.

**P15 — Consolidation cap for watch docs.** No third consecutive unmerged
delta watch: when two unconsolidated delta watches are open, the next
`competitor` turn runs the consolidation pass into
`COMPETITOR_ANALYSIS.md` instead of another delta. (Concretely: the next
competitor turn consolidates #64/#82/#102 rather than filing #103-style
deltas.)

**P16 — Hosted-code surfacing for the `feature` turn.** F11's corrective:
with P11's stale blockers retired, the next `feature` turn takes the top
P11-unblocked hosted-code item — H14(a) standalone push enqueue/retry
service, or the H4 provider-agnostic provisioning interface — instead of
another doc. The both-supported default means both land in OSS too; this
is an assignment the next feature turn adopts, not a rule change.

**P12 — renewed, still pending user approval.** P1/P3/P4/P5/P6/P7 rule
text into PLAYBOOK.md (P3 re-authorized with the #36/#28 park corrective
— the 2026-09-19 strategy/marketing turn found the corrective already
satisfied in substance and flagged it for user confirmation rather than
closing it; P4 with the ≥8-open-PRs re-arm condition). P14 joins this
bundle as new playbook-rule text. Nothing lands without the user's word.

## Adoption checklist (for the next loops, in order)

- [ ] P12 (+P14): user approves playbook-rule text (or declines with reasons).
- [ ] P13: next `sales` turn (or the repo turn as a P2 queue item) re-reviews
      #68/#99 heads and records final sign-offs, unblocking #111.
- [ ] P15: next `competitor` turn consolidates #64/#82/#102 into
      `COMPETITOR_ANALYSIS.md` instead of another delta watch.
- [ ] P16: next `feature` turn takes H14(a) or the H4 interface.
- [ ] Record each adoption in BACKLOG.md; these proposals stay filed here
      until adopted, not silently applied.

## Rotation health summary

The loop is healthier than at the last audit: CI is real and green, the
merge rule has an exercised path (11 merges), the repo turn owns the
queue, and the advisory proposals are being executed even where not
adopted. The two structural risks are the issue-queue growth rate (F12:
+26 net this window, fix capacity aimed at hygiene not closure) and the
build loop's persistent all-open-source tilt (F11: hosted code is now
unblocked-but-unpicked). Both have concrete next-turn owners in the
checklist above. No user blockers this run.
