# Loop rotation audit — 2026-09-20 (fourth cycle, `meta` archetype)

Window: 2026-09-19 ~16:05 CDT → 2026-09-20 ~05:25 CDT (~13.3 h).
Scope: both loops. Build runs: arch, fix, [feature — unlogged], security,
distribution, gap, dx, docs, repo, meta (this turn). Strategy runs: research ×2
(#119 key-auth validation → merged; #127 multitenant isolation → merged),
competitor ×2 (consolidation → merged as #123; evening watch), marketing ×2
(demo asset 5 → #125 merged; persistence pair → #137 merged), sales ×2
(P13 unblock-and-merge chain #68 → #99 → #111; funnel query pack → #141 merged),
plus research PR #140 (Fly.io driver for H4 — CI 4/4 green, open, mergeable
clean) and one merge-execution pass (#130).

Inventory (verified via GitHub API 2026-09-20 ~05:30 CDT): 20 PRs merged in
window (#65, #67, #68, #98, #99, #111, #112, #117, #119, #120, #123, #124,
#125, #127, #129, #130, #131, #136, #139, #141); open queue 3 PRs (#113,
#126, #140); 54 open issues. Track: build loop 7 OSS + 1 hosted-product (gap:
H6 day-one capability analysis) + 1 loop-tooling (dx: P18 push-guard, no
product track consumed); strategy runs carried the hosted-product shipping
(#141 funnel, #127 H11 research, #119 key-auth).

This audit is advisory (per the `meta` archetype): findings are loop-owned or
filed for user decision; nothing here rewrites the rotation unilaterally.

## Findings

### F20 — unlogged feature turn (F19 recurrence), PR #126's trail has a hole

The build-loop `feature` turn ran (~19:24 CDT) and produced real work —
branch `hourly/harness-auth-probe-20260919-1924`, commit `eb8da0a` ("fix:
address P1/QA1-4/EngB1 review blockers + adopted nits" — i.e. adversarial
review happened), PR #126 opened 2026-09-20 01:09 UTC ("R2 slice 1:
harness-auth-probe + gate fixture (feature)"), updated 08:30 UTC — but wrote
no RUNLOG entry. The rotation marker moved fix → security as if the turn had
logged normally.

Consequences: (1) the audit trail has an hour-sized hole in exactly the run
that owns the currently most delicate queue item; (2) #126's PR body claims
round-1 reviewer blockers were fixed, but there is no loop record of the
reviewers, their roles, or the final-code SHIP IT — the loop cannot verify
its own gate on this PR; (3) the 03:25 repo turn correctly flagged the
divergence (see F21) but could not consult a run entry that doesn't exist.

F19 (afternoon audit) recommended a RUNLOG-entry-is-definition-of-done
practice; it was never made loop-owned, and the recurrence proves the
recommendation didn't stick by convention alone. See P19.

### F21 — R2 slice-1 race: two divergent harness-auth-probes, one merged

Two implementations of the same R2 §5 contract now exist. #124
(`harness/harness-auth-probe`, 283 lines) merged as `a631228`; #126
(`provision/`, 463 lines) is still open and its mergeable_state is `dirty`.
The 03:25 repo turn posted a reconcile-before-merge comment on #126 (dedupe
to one canonical location, fold in the gate-fixture installer +
fixture-lifecycle contract, fix its red link check) and assigned it to #126
— but there is no loop-side owner for the reconcile work, so it will rot
until someone adopts it.

The race itself is worth naming: the unlogged feature turn (F20) and the
#124 run worked the same R2 slice concurrently with no coordination, and
both claimed the same contract. Next-race mitigation belongs in the backlog
(one R2-slice coordinator note per slice; see P21), but the immediate need
is an owner for the reconcile.

### F22 — abandoned worktrees accumulate; some nest inside the shared checkout

`git worktree list` (2026-09-20 ~05:30 CDT) shows ~20 local worktrees, many
for branches long since merged (e.g. `repo-h2-push` from 2026-09-18,
`repo-addendum67`, `repo-sales-h15-20260919-1354`). Two worktree containers
(`repo/worktrees/`, `repo/repo-worktrees/`) live INSIDE the shared checkout
as untracked dirs, plus `repo/repo-changelog-20260919/`. The playbook's
shared-checkout-race lesson says trees must live OUTSIDE the checkout the
other runs own; untracked dirs inside `repo/` pollute the one checkout every
run pulls from, and stale trees are where "uncommitted work survived only in
the object DB" incidents start.

Notable: `repo/worktrees/repo-feature-harness-probe` (F20's tree) was never
removed — the unlogged turn tore nothing down.

### F23 — rotation markers advance on faith

No run verifies that the marker it reads matches the turn that actually ran
before it. The security run at 21:24 logged "rotation arch → fix → feature →
security" and advanced to distribution — but the `feature` turn it named
never logged. A marker is only as honest as the RUNLOG, and the RUNLOG
depends on each run writing its entry before teardown. The fix run left
"(next: feature)"; the feature run left nothing; the security run read the
marker, not the log.

### F24 — build-loop OSS tilt continues; F11 ruling still pending

Window track tally: arch, fix, security, distribution, docs, repo →
open-source; dx → loop-tooling (no track consumed); gap → hosted-product
(H6). The build loop is 7:1 OSS with the hosted share arriving through
strategy runs (#141, #127, #119) and hosted-design turns (H15). The
afternoon audit's F11 (all-OSS tilt while H4/H9/H11 sit on partly stale
blockers) remains an accurate description, and its ruling is still with the
user (P12 bundle + F11, NEEDS_USER.md). One honest update to the F11
premise: hosted items are no longer fully stale — H11 research merged (#127),
H4 has a merge-ready research PR (#140), R2 slice 1 half-shipped (#124
merged, #126 open). The tilt is now "OSS-heavy on the build loop, hosted
moves on the strategy loop" rather than "hosted stalled."

### F25 — REST merge flakiness: loop-handled, correctly reclassified

The 02:54 marketing run hit `RemoteDisconnected` ×4 on
`POST /pulls/137/merge` and fell back to the Git Data API manual squash
(merged as `de1d3e7`, audited). NEEDS_USER.md marks the REST-merge item
RESOLVED with the recurrence noted and "nothing needed from the user" —
the correct classification, since the fallback is proven and documented.
#141 then merged normally at 10:24 UTC. No new proposal; record that the
standing procedure worked twice in-window (also #136's earlier 404).

### F26 — PR queue is healthy but the two oldest need owners

15 → 3 open PRs across the window: the repo turn's P2 queue duties are
working. Remaining: #140 (research, CI 4/4 green, clean, mergeable — the
next build run's merge duties can take it); #113 and #126 both carry loop
comments with concrete asks (link-check fix + final-head re-review; R2
reconcile) but no named owner. Queue rule: a comment without an owner is a
note, not a plan.

### F27 — #138 branch-protection decisions are user work, not loop work

The repo turn filed #138 (main-branch protection proposal) with two
maintainer decisions named (trivial-scope exception vs require-PR; admin
enforcement vs loop-token bypass). These are correctly filed as an issue,
not in NEEDS_USER.md — but the loop should not drift: until the user rules,
the standing loop-merges rule (green CI + clean + unanimous SHIP IT)
remains the gate, and no run should cite #138 as authorization to merge on
weaker grounds.

### F28 — the merge loop is the loop's job, and it is working

20 merges in ~13 h, all loop-executed except none (no operator merges this
window). The merge gate held: every merge in-window carried green CI or a
documented vacuous-green precedent, clean mergeable state, and unanimous
final sign-offs. The one procedural scar (H15/#111's post-sign-off README
note) was retrospectively reconciled by the 03:25 repo turn with all four
roles re-reviewing the exact landed tree. The governance question of
conditional-SHIP-IT merges remains with the user (P12 bundle), but this
window produced no new instance of it.

## Proposals (P19–P22)

- [ ] **P19 — RUNLOG entry is the turn's definition of done** (loop-owned,
      adoptable by the next turn directly): the entry goes into
      `hidden_files/RUNLOG.md` BEFORE the worktree is removed and BEFORE
      the branch is pushed away and forgotten. Add a marker-continuity
      check at run start: read `last_build_archetype`/`last_strategy_archetype`,
      confirm the previous run's entry exists and names the expected
      archetype; if it doesn't, the first finding of the turn is the gap
      (this audit is the first exercise of that rule — F20). This closes
      the F19→F20 recurrence class.
- [ ] **P20 — P2 repo duties gain an abandoned-worktree sweep**
      (loop-owned): each `repo` turn drops local worktrees whose branches
      are merged/deleted on remote, and relocates or removes worktree
      containers nested inside the shared checkout (`repo/worktrees/`,
      `repo/repo-worktrees/`). Target after this run: zero worktrees for
      merged branches, zero trees inside `repo/`.
- [ ] **P21 — next `fix` turn owns the #126 reconcile** (loop-owned): per
      the P17 closure floor, the fix turn takes the repo turn's
      reconcile-before-merge comment on #126 (dedupe to one canonical
      probe location, fold in the gate-fixture installer +
      fixture-lifecycle contract, fix the red link check) and either lands
      it or closes #126 with a note. Do not let #126 age past the next
      fix turn.
- [ ] **P22 — F11 ruling input: hosted moves on the strategy loop**
      (advisory, user decision): if the user keeps the build loop
      OSS-primary, the honest framing is "build loop ships the open
      product; strategy loop ships the hosted design" — and the current
      window shows that working. Alternatively set a standing hosted
      share for the build loop. No unilateral change; this stands as
      input to the pending F11 ruling.
