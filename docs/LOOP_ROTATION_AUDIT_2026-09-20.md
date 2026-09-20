# Loop rotation audit — 2026-09-20 (fourth cycle, `meta` archetype)

Window: 2026-09-19 ~16:05 CDT → 2026-09-20 ~05:25 CDT (~13.3 h).
Scope: both loops. Build runs: arch, fix, [feature — unlogged], security,
distribution, gap, dx, docs, repo, meta (this turn). Strategy runs: research ×2
(#119 key-auth validation → merged; #127 multitenant isolation → merged),
competitor ×2 (consolidation → merged as #123; evening watch), marketing ×2
(demo asset 5 → #125 merged; persistence pair → #137's work landed as
`de1d3e7` — GitHub records the PR as closed rather than merged, fallback
path), sales ×2
(P13 unblock-and-merge chain #68 → #99 → #111; funnel query pack → #141 merged),
plus research PR #140 (Fly.io driver for H4 — CI 4/4 green, open, mergeable
clean) and one merge-execution pass (#130).

Inventory (verified via GitHub API 2026-09-20 ~05:30 CDT): 20 PRs merged in
window (#65, #67, #68, #98, #99, #111, #112, #117, #119, #120, #123, #124,
#125, #127, #129, #130, #131, #136, #139, #141); open queue 3 PRs (#113,
#126, #140); 54 open issues. Track: build loop 6 OSS + 2 hosted-product (gap:
H6 day-one capability analysis; feature: R2 slice 1, hosted-track per
BACKLOG.md) + 1 loop-tooling (dx: P18 push-guard, no product track
consumed); strategy runs carried the hosted-product research/design
shipping (#141 funnel, #127 H11 research, #119 key-auth).

This audit is advisory (per the `meta` archetype): findings are loop-owned or
filed for user decision; nothing here rewrites the rotation unilaterally.

## Proposal adoption status (P12–P18)

The afternoon audit built adoption tracking into the audit format; this
cycle's check (evidence one line each):

- **P12 — PLAYBOOK amendment bundle: PENDING.** Unchecked in
  NEEDS_USER.md (loop-governance bundle; PLAYBOOK.md amendments need user
  approval).
- **P13 — unblock-and-merge #68 → #99 → #111: DONE.** 2026-09-19 19:54 CDT
  sales turn; chain merged `18f0f0e5` → `c9e859e5` → `e6d1a13`.
- **P14 — reviewer-report completeness: DONE.** AGENTS.md records the
  practice (full report in transcript before next round or sign-off); this
  audit's own review round follows it.
- **P15 — competitor-watch consolidation: DONE.** 2026-09-19 17:54 CDT
  competitor turn; merged as #123 (`7a4cef6`).
- **P16 — hosted-code assignment on its own merits: LIKELY CARRIED,
  intent unconfirmable.** The feature turn worked R2 slice 1, which
  BACKLOG.md records as "(feature archetype, hosted-product track)" — the
  kind of hosted-track code item P16 asked for. But with no RUNLOG entry,
  the turn's item-selection rationale can't be confirmed as a deliberate
  P16 claim. Carried forward: the next turn claiming P16 must say so in
  its RUNLOG entry.
- **P17 — fix-turn closure floor: DONE.** 2026-09-19 17:24 CDT fix turn
  closed #88; RUNLOG records "P17 closure floor met."
- **P18 — push tooling refuses main-branch writes: DONE.** 2026-09-20
  00:24 CDT dx turn; guard + 18/18 tests; 32 legacy ref-writers quarantined.

## Findings

### F20 — unlogged feature turn (F19 recurrence), PR #126's trail has a hole

The build-loop `feature` turn ran (~19:24 CDT) and produced real work —
branch `hourly/harness-auth-probe-20260919-1924`, commits `1643d01` +
`eb8da0a` (pushed head `a3a7ded`, tree byte-identical — metadata-only
rewrite), PR #126 opened 2026-09-20 01:09 UTC ("R2 slice 1:
harness-auth-probe + gate fixture (feature)"), updated 08:30 UTC — but wrote
no RUNLOG entry. The rotation marker moved fix → security as if the turn had
logged normally.

Consequences: (1) the audit trail has an hour-sized hole in exactly the run
that owns the currently most delicate queue item; (2) the review record for
#126 exists — BACKLOG.md's R2 entry records "unanimous round-2 SHIP IT
(Product, Engineering, QA) on the final code" with the six round-1 blockers
fixed — but it lives in the backlog, not in a RUNLOG turn entry, so the
run's timestamps, worktree, and verification detail are unrecoverable from
the loop's own trail; (3) the 03:25 repo turn correctly flagged the
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

`git worktree list` (2026-09-20 ~05:30 CDT) shows 38 entries: 26 at the goal
root, 11 nested inside the shared checkout, plus the checkout itself. Many
are for branches long since merged (e.g. `repo-h2-push` from 2026-09-18,
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
open-source (6); gap → hosted-product (H6); feature → hosted-product (R2
slice 1, per BACKLOG.md); dx → loop-tooling (no track consumed). The build
loop is 6:2 OSS with two hosted-track code/design turns in-window — a
thinner tilt than the afternoon audit measured, but hosted code on the
build loop remains a small share, and the strategy loop carries the rest
(#141 funnel metrics, #127 H11 research, #119 key-auth — research/design
docs, not shipped hosted code). The F11 question in NEEDS_USER.md is
unchanged by this window: no new evidence to change or resolve the pending
ruling, and none is manufactured here.

### F25 — REST merge flakiness: loop-handled, correctly reclassified

The 02:54 marketing run hit `RemoteDisconnected` ×4 on
`POST /pulls/137/merge` and fell back to the Git Data API manual squash
(landed as `de1d3e7`; GitHub records the PR as closed rather than merged —
the loop's fallback-path convention). NEEDS_USER.md marks the REST-merge item
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
note, not a plan (see P21 for the #126 owner).

### F27 — #138 branch-protection decisions are user work, not loop work

The repo turn filed #138 (main-branch protection proposal) with two
maintainer decisions named (trivial-scope exception vs require-PR; admin
enforcement vs loop-token bypass). These are correctly filed as an issue,
not in NEEDS_USER.md — but the loop should not drift: until the user rules,
the standing loop-merges rule (green CI + clean + unanimous SHIP IT)
remains the gate, and no run should cite #138 as authorization to merge on
weaker grounds.

### F28 — the merge loop is the loop's job, and it is working

20 merges in ~13 h, all loop-executed (no operator merges this window, per
the loop's records). Every one of the 20 merges carried 4/4 green CI check
runs on its merge commit — verified merge-commit-by-merge-commit via the
check-runs API this audit (all `success`). Unanimous final sign-offs hold
through the window; the one procedural scar (the post-sign-off 4-line
README note, retrospectively reconciled) belonged to #137, where the 03:25
repo turn had all four roles re-review the exact landed tree `de1d3e7`.
The governance question of conditional-SHIP-IT merges remains with the
user (P12 bundle), but this window produced no new instance of it.

## Proposals (P19–P22)

- [ ] **P19 — RUNLOG entry is the turn's definition of done** (loop-owned,
      adoptable by the next turn directly): the entry goes into
      `hidden_files/RUNLOG.md` BEFORE the worktree is removed and BEFORE
      the branch is pushed away and forgotten. Add a marker-continuity
      check at run start: read `last_build_archetype`/`last_strategy_archetype`,
      confirm the previous run's entry exists and names the expected
      archetype; if it doesn't, the first finding of the turn is the gap
      (this audit is the first exercise of that rule — F20). This converts
      silent gaps into next-turn findings (detection, one turn late — not
      prevention), which is the best a log-only mechanism can do.
- [ ] **P20 — P2 repo duties gain an abandoned-worktree sweep**
      (loop-owned): each `repo` turn drops local worktrees whose branches
      are merged/deleted on remote, and relocates or removes worktree
      containers nested inside the shared checkout (`repo/worktrees/`,
      `repo/repo-worktrees/`). Guard (standing): skip — and flag in the run
      entry — any tree with uncommitted changes or local commits not on the
      remote; remove only clean, fully-pushed trees (a `--force` sweep
      without this guard would recreate the uncommitted-work-loss incident
      class). Target after the next repo turn: zero worktrees for merged
      branches, zero trees inside `repo/`.
- [ ] **P21 — next `fix` turn owns the #126 reconcile** (loop-owned): per
      the P17 closure floor, the fix turn takes the repo turn's
      reconcile-before-merge comment on #126 (dedupe to one canonical
      probe location, fold in the gate-fixture installer +
      fixture-lifecycle contract, fix the red link check) and either lands
      it or closes #126 with a note. Do not let #126 age past the next
      fix turn.
- [ ] **P22 — F11 ruling input: the window adds two hosted-track build
      turns** (advisory, user decision): the build loop shipped hosted-track
      code this window (feature/R2, gap/H6) alongside its OSS turns, and the
      strategy loop shipped hosted research/design docs. That is the
      complete evidence — it neither confirms nor resolves the F11
      question. No unilateral change; this stands as input to the pending
      ruling.
