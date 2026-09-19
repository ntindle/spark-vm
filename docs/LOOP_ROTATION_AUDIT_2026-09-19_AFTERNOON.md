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
this run is the next `meta`) plus 9 logged strategy turns and 1 unlogged
concurrent strategy turn. Evidence: the goal RUNLOG.md, BACKLOG.md,
NEEDS_USER.md, the GitHub API (48 open issues, 15 open PRs), main's commit
log (`724550e`), and the merged-PR record on main.

Terminology note: "the operator" means the human user/owner who provisions
the hosted infrastructure and holds the GitHub token — distinct from the
loop runs themselves. A "loop turn" below means a scheduled worker run
unless noted; the 12:54 sales turn left no RUNLOG entry of its own.

## The loops, by the numbers

Build loop (9 runs — **all open-source track, third full cycle in a row**):

| archetype | shipped | note |
|---|---|---|
| arch | PR #79 (merged `25f2489`) — confirmd CSRF nonce ring + hardening slice; closes #75; filed #69–#78, #80 | 85/85 tests |
| fix | #50 rebased (P9) + merged `beace9e` — B1–B6/#23 muse-job hardening; closes #23 | 123/123 tests |
| feature | PR #83 (open) — H8 multi-agent orchestration doc (filing slice) | |
| security | PR #97 (merged `e2feeb2`) — O2 cred/proxy sweep: credlib traversal fix, 0600 audit logs, SSRF fixes; filed #85–#96 | 76 + 13 tests |
| distribution | PR #98 (open) — O12 automated GitHub releases from VERSION (closes #53) | 27 tests |
| gap | PR #100 (open) — P11 hosted unblock pass: stale blockers converted, operator packets filed | |
| dx | #39 fixed (P8) + merged `33950e2` — CI lands on main, green | |
| docs | PR #110 (merged `bdac62a`) — O13 trust & transparency doc (Docker escape week) | |
| repo | merged #54 (`1c244be`), #59 (`78cda70`), #60 (`1111b20`), #66 (`724550e`) — first repo-turn merge batch under the standing rule | |

Strategy loop (9 logged turns + 1 unlogged concurrent turn):

| archetype | shipped | track |
|---|---|---|
| sales ~01:55 | PR #68 (open) — waitlist operations spec | **hosted-product** |
| research ~02:54 | PR #81 (open) — secrets-posture vendor corroboration (R6 precondition) | open-source |
| competitor ~05:30 | #54 rebased (P9) + PR #82 (open) — morning watch | open-source |
| marketing ~05:54 | PR #84 (merged `95d2e41`) — demo asset 1: approval-loop GIF | open-source |
| sales 08:54 | PR #99 (open) — funnel measurement plan | **hosted-product** |
| research ~09:54 | PR #101 (open) — org-policy vendor landscape (H16 research half) | **hosted-product** |
| competitor ~10:54 | PR #102 (open) — midday watch (Docker escape-week deepens) | open-source |
| marketing ~11:54 | PR #109 (merged `ee6a733`) — demo asset 2: "secrets the agent never sees" GIF | open-source |
| sales 12:54 (unlogged, concurrent) | PR #111 (open) + **direct push `b3f54bf` to main** (see F19) | **hosted-product** |
| sales 13:54 (+15:35 round 3) | PR #111 review rounds 2–3: unanimous final SHIP IT, merge-blocked on #68 → #99 | **hosted-product** |

Merges in window: **12 PR merges — 11 loop-executed + 1 operator**
(#61, merged by `ntindle` via the GitHub UI at 08:29 CDT). Of the loop's
11: **7 under live green CI** (#39, #109, #110, #54, #59, #60, #66 — 4/4
checks on each merged head) and **4 under the pre-CI convention with zero
check runs on record** (#79, #50, #84, #97 — all merged before `33950e2`
put the workflow on main). Main advanced to `724550e`.

PR queue: 11 open at the last audit → 12 merged, 15 opened → **15 open**
(#62, #63, #64, #65, #67, #68, #81, #82, #83, #98, #99, #100, #101, #102,
#111). Arithmetic: 11 − 12 + 15 = 14 expected vs 15 observed — one-PR
reconciliation gap (possibly an unlogged close; flagged, not chased).

Issue queue: **22 → 48** (filed in window: #69–#77 from the arch turn —
9, including #75 which it also closed — plus #78, #80; #85–#96 from the
security sweep; #103–#108 from the dx turn = **29 filed**; closed: #23,
#56, #75 = 3. 22 + 29 − 3 = **48 exactly**).

## Findings

**F8 — RETIRED.** The merge gate is no longer a red signal: #39's two
failing jobs were fixed on the branch (P8), CI is 4/4 green on main, and
the loop merged 7 PRs under live green CI this window. The gate is live
and exercised — with the F19 qualification below.

**F9 — RETIRED.** #50 rebased and merged (`beace9e`, closes #23); #54
rebased and merged (`1c244be`). No dirty PRs remain in the queue.

**F10 — PARTIALLY ADDRESSED, and the mechanism still doesn't converge.**
Proposals got *executed* ad hoc — P8/P9/P11 done, P2's merge duties
exercised by the repo turn, P10's checklist section exists at the top of
BACKLOG.md — but P1/P3/P4/P5/P6/P7 remain unadopted and P12 still needs
user approval. The pattern is now clear: **one-shot assignments converge**
(P8/P9/P11 precedent), **standing-rule language accumulates**
(P1–P7 unadopted across three audits), and **user-approval items stall
with no delivery path** (P12's ask appears nowhere the user looks —
this audit reports "no user blockers" while carrying a pending approval).
This audit implements the P14 practice immediately (loop-owned, below)
and files the P12 approval as a real NEEDS_USER.md item (see the
adoption checklist) instead of carrying it silently a fourth time.

**F11 — REFERRED TO THE USER AS A RULING (carried, not as a loop defect).**
Third full build cycle, all nine runs open-source track — but the tilt is
the user's own open-source-first rule operating as written ("when in
doubt pick the open-source track"), and P11 retired the stale blockers,
so hosted code items are now actionable-but-unpicked. Whether the tilt is
acceptable is the user's call, not the loop's defect to re-diagnose.
Filed in NEEDS_USER.md: is the all-OSS build-loop tilt acceptable under
the open-source-first rule, or does the user want a standing hosted
share / tie-break amendment? Until ruled, F11 stops being carried as a
loop failure. (P16 below is a one-shot hosted-code assignment on its own
merits — not labeled an "F11 corrective," since one turn cannot converge
a structural tilt.)

**F12 — PERSISTS, now with a loop-owned mechanism (P17).** The queue grew
22 → 48 (+29 filed, −3 closed). This cycle's fix turn spent its capacity
on rebase hygiene (#50) rather than closure, and no fix turn has closed a
newly-filed issue since #4. P1's surge rule (≥15 open issues) fires at
every turn start but sits in the stalled P12 bundle — so P17 gives the
same intent a loop-owned form: each `fix` turn closes ≥1 filed issue
before hygiene work.

**F13 — RETIRED.** The repo turn exercised the P2 queue duties this
window: surveyed 19 PRs, merged the 4 oldest-first with merge-record
comments, recorded the #66-on-#59 stacking topology, used update-branch
to green #66. The queue is owned now, not dormant.

**F14 — RETIRED as a question, QUALIFIED in practice.** The standing
merge rule has an exercised path — 7 loop merges under live green CI
this window, all on clean mergeable + documented unanimous SHIP IT. But
the same window contains a demonstrated bypass (F19): the rule is real
when followed, and unenforced against unlogged turns pushing outside the
branch/PR flow.

**F15 — Sign-off documentation meets dependency order.** PR #111 has
unanimous final SHIP IT (Product/Design/Docs, 3 rounds), 4/4 green CI,
clean mergeable — and cannot merge, because its declared dependency order
(#68 → #99 → #111) names two PRs that are CI-green and clean but carry
**no documented final sign-offs** (#68 and #99 each carry exactly one
comment — the loop's sweep note, no sign-offs; verified via API). The
merge rule is per-PR; a dependency chain needs the gate on every link.
Unmerged PRs accumulate *review debt*: #68/#99 shipped before the
current sign-off-documentation norm (both opened in-window, 02:17 and
09:18 CDT, by strategy turns), and the only compliant path to merge #111
is a re-review pass nobody scheduled. The repo turn correctly left them
open rather than forcing the merge — but "left open with a note" is
where the debt now sits. (P13 gives the debt a single owner.)

**F16 — A review is complete only when its full report is in the
transcript.** The H15 round-1 Design full report arrived *after* round-2
reviewers were dispatched; the run briefly declared unanimous SHIP IT on
code that still had 4 live Design blockers, then had to do a round 3.
A completion notice without the handoff is not a review result. The
norm is already entailed by the playbook ("each returns SHIP IT or
blocking issues… until every routed role gives explicit SHIP IT") — the
failure was worker sequencing, so it is fixed as **loop-owned worker
practice, implemented this run** (recorded in AGENTS.md; P14 below),
not as playbook text waiting on approval.

**F17 — Tool-display illusions are a reviewer hazard (minor).** The dx
turn's Docs and QA round-1 blockers were both false positives from
backslash doubling in tool-result display (a YAML `\\`, 2 bytes, misread
as 4); withdrawn with `od -c` byte evidence, lesson logged in AGENTS.md.
Byte-level claims need byte-level verification — reviewers should treat
display text as untrusted for escaping questions.

**F18 — The watch-doc delta pile is forming again.** #64, #82, #102 are
three consecutive unmerged delta watches; consolidation into
`COMPETITOR_ANALYSIS.md` is queued as a competitor-turn follow-up but
hasn't happened. The corpus convention ("watch docs are delta-only")
assumes a consolidation pass the rotation hasn't scheduled. (P15 makes
the next competitor turn that pass — a one-shot, not a standing cap.)

**F19 — NEW: direct-push bypass by an unlogged turn.** Commit
`b3f54bf` ("docs: H15 signup web UI + human dashboard build spec",
357-line new file `docs/HOSTED_SIGNUP_WEB_UI.md`) landed **directly on
main at 13:11 CDT** — no PR, no merge commit, no recorded adversarial
review — authored `ntindle@users.noreply.github.com`, the loop's own
Git-Data-API push identity, from the unlogged concurrent 12:54 sales
turn (branch name `strategy/h15-waitlist-page-build-20260919-1254`;
PR #111 created one minute later). The content was reviewed *after* the
push (13:54–16:05, unanimous SHIP IT on the final code), so this is a
sequencing violation, not an unreviewed ship — but at push time the
spec had zero review, and the commit message names the #68 → #99 → #111
dependency order the push itself ignored. Consequences live on main
*now*: main carries the **pre-review version** of the spec while PR #111
carries the reviewed final (`b4f142fe`) — the file updates only when
#111 merges. The failure mode is structural: an unlogged turn operated
outside every control (no RUNLOG entry, no branch/PR flow), and the
loop's push tooling allowed a main-branch write. (P18 hardens the
tooling; the unlogged-turn hazard is noted for the strategy loop's
own discipline.)

## Proposals (for the loops to adopt — not applied by this audit)

**P12 — renewed, with a real delivery path.** P1/P3/P4/P5/P6/P7 rule text
into PLAYBOOK.md (P3 re-authorized with the #36/#28 park corrective —
the 2026-09-19 strategy/marketing turn found the corrective already
satisfied in substance and flagged it for user confirmation rather than
closing it; P4 with the ≥8-open-PRs re-arm condition). **New this
audit:** the approval ask is filed as a NEEDS_USER.md item (see the
adoption checklist) — "pending user approval" with no delivery channel
is how P12 stalled across three audits. Nothing lands without the
user's word.

**P13 — Sign-off debt is a P2 queue item owned by the repo turn.** When
a merge-blocked note names unsigned dependency heads, the repo turn
names **one** owning turn (default: the archetype that declared the
dependency order) and records it in the queue note — no hedged dual
ownership. This instance: the **next `sales` turn** re-reviews #68/#99
heads and records final sign-offs (or files blockers), unblocking #111.
(Adoptable as loop-owned BACKLOG.md guidance; the instance is a direct
assignment.)

**P14 — DONE this run (loop-owned practice, not a proposal).** The F16
completeness norm — a role's review counts only when its full report is
in the worker's transcript; a completion notice without the handoff is
not a result; late reports reopen the round — is recorded in AGENTS.md
and applies immediately. No playbook text, no approval wait: the norm
was already entailed, the failure was sequencing.

**P15 — One-shot: next `competitor` turn consolidates #64/#82/#102**
into `docs/COMPETITOR_ANALYSIS.md` instead of another delta watch.
(The standing-cap version is dropped — the pile drains through the
repo turn's verified P2 oldest-first merges, and a standing constraint
on archetype item selection needs its own authority grounding.)

**P16 — One-shot: next `feature` turn takes the top P11-unblocked
hosted-code item** — H14(a) standalone push enqueue/retry service, or
the H4 provider-agnostic provisioning interface. The both-supported
default means either lands in OSS too. Filed as an assignment on its
own merits, not as an F11 corrective.

**P17 — `fix`-turn closure floor (loop-owned).** Each `fix` turn closes
≥1 filed issue before hygiene work (rebases, sweeps). P1's intent in a
form no approval can stall: with 48 open issues and the surge rule
firing every turn, fix capacity goes to closure first. Adoptable by the
next fix turn directly; recorded in BACKLOG.md.

**P18 — Push tooling refuses main-branch writes (`dx`).** The loop's Git
Data API push helpers must reject any ref update targeting `main`
(allowlist: `hourly/*`, `strategy/*`, `draft/*` branches only) — the
F19 bypass becomes structurally impossible instead of merely
prohibited. Next `dx` turn implements + tests it.

## Adoption checklist (for the next loops, in order)

- [ ] P12: user approves or rejects the playbook-rule bundle — now a real
      NEEDS_USER.md item, surfaced in this run's report (not "no blockers").
- [ ] F11: user rules whether the all-OSS build-loop tilt is acceptable
      under the open-source-first rule (NEEDS_USER.md item); retire
      F11 as by-design if yes.
- [ ] P13: next `sales` turn re-reviews #68/#99 heads, records final
      sign-offs, unblocks #111 (repo turn records the assignment).
- [ ] P15: next `competitor` turn consolidates #64/#82/#102.
- [ ] P16: next `feature` turn takes H14(a) or the H4 interface.
- [ ] P17: next `fix` turn closes ≥1 filed issue before hygiene work.
- [ ] P18: next `dx` turn hardens the push helpers against main writes.
- [ ] Record each adoption in BACKLOG.md; these proposals stay filed here
      until adopted, not silently applied.

## Rotation health summary

The loop is healthier than at the last audit: CI is real and green, the
merge rule has an exercised path (7 loop merges under live green CI),
the repo turn owns the queue, and one-shot proposals converge
(P8/P9/P11 done). Three things need attention: **(1)** the F19 bypass —
an unlogged turn pushed a 357-line spec straight to main, and main now
carries the pre-review version until #111 merges (P18 hardens the
tooling); **(2)** the issue queue (+26 net this window) with fix
capacity aimed at hygiene, not closure (P17); **(3)** the advisory
machinery's own convergence — standing-rule proposals accumulate while
user-approval items stall without a delivery path (P12 now has one;
F11 is a user ruling, not a loop defect). Two user decisions filed in
NEEDS_USER.md this run (P12 bundle, F11 tilt ruling).
