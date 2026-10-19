# waitlistd durability convergence (2026-10-19)

**Pinned to main `470ab39a` (2026-10-19).** Convergence pass over the
2026-10-11 `WAITLISTD_DURABILITY_GAP_ANALYSIS.md` (pinned to main
`f4c7c74`): which dispositions held, which forward-work items landed,
and what genuinely remains. Every claim below was re-verified against
the pinned tree; line numbers are current-tree pins.

## 1. Forward-work items 1–4: status

- **Item 1 (close #387 with the F-WL-1 pointer) — DONE.** #387 is
  closed; the `_ip_limited` trusted-proxy contract (`WAITLIST_TRUSTED_PROXY`
  + `resolve_client_ip`) still keys off the resolved client IP on the
  pinned tree.
- **Item 2 (re-scope #397 to its four remaining kinds) — done this
  turn.** #397's title/body were still the original scope. The issue is
  re-scoped to the four unrepaired kinds (`confirmed` / `dropped` /
  `reminder_sent` / `forgot`); the two repaired halves (`invite_sent`
  via `--reconcile`, `claimed` via `--reconcile-claimed`) are struck
  from it; the two extra kinds this analysis found (`confirm_sent`,
  `waitlist_submitted`) move to the new build home in §3. The re-scope
  also corrects the analysis's own stale line: the 2026-10-11 doc said
  the re-scope would be "to the four still-unrepairable commit→emit
  kinds (invite_sent + claimed now have reconcile tools)" — that
  phrasing was accurate at write time; the issue body itself had never
  been edited.
- **Item 3 (small fixes: #406, #401) — DONE, with one residual found
  and fixed this turn.** #406 closed via #1390; #401 closed via #1521
  (collision-proof triage names) + #400 (48h triage retention sweep,
  waitlistd.py:2067). Residual: **#406's parity fix missed the
  deleted-notice path.** `_queue_deleted_email` (waitlistd.py:2765) was
  still a bare `_write_spool` call at #1390's merge and stayed bare
  through #1522's exclusive-publish refactor — a sick spool there
  raised OSError out of `forget_post` *after* the row commit, scrubs,
  and `forgot` emit, so the daemon 500'd an already-successful
  deletion (the user saw an error; a retry saw "invalid" since the
  forget token was consumed). Fixed this turn per the standing D-WL-8
  consensus: the path now catches OSError and returns False — fail
  the email, not the request. The caller still renders 200, because
  the deletion genuinely happened. New pin test
  `test_forget_post_spool_failure_deletion_still_200_notice_lost`
  (neuter-verified: fails on the pristine tree, passes with the fix).
- **Item 4 (docs prose: §5 forget-scope + per-flow ordering note) —
  PARTIAL.** The §5 forget-scope prose landed (D-WL-4 item 1:
  `WAITLIST_OPERATIONS.md` §5 states the forget flow covers live
  funnel rows only, dropped rows wait out the 30-day retention, claimed
  rows are terminal). Two residuals remain: (a) the email footer's
  deletion promise is not yet scope-qualified ("this link works while
  your entry is on the waitlist" — D-WL-4 item 2; the footer copy
  lives in `FORGET_FOOTER`, and changing user-facing mail copy is a
  docs/design-turn slice, not this turn's); (b) post-claim erasure is
  not yet named as unowned-until-H15 (D-WL-4 item 3 — §5 says claimed
  rows are terminal; §8 covers the funnel handoff but names no erasure
  owner). The per-flow ordering note (D-WL-6) lands this turn: §4 gains
  the one-line-per-flow summary so the next reader doesn't re-derive
  the policy block in `site/waitlistd.py:994`.

## 2. Disposition table, re-verified

| Issue | Prior disposition | Today |
|---|---|---|
| #386 GETs take the exclusive lock | D-WL-1, pinned | closed — the store-size mitigation still stands; nothing outgrew it |
| #387 proxy-blind `_ip_limited` | CLOSE per F-WL-1 | closed ✓ |
| #391 wave holds the lock | D-WL-3, KEEP | open — the docstring at :2834 still admits the whole-wave lock; heartbeat still nice-to-have; no mitigation shipped |
| #393 post-claim forget invisibility | D-WL-4, KEEP until prose lands | open — prose landed (item 1) but the footer qualification + unowned-until-H15 naming remain (residuals a/b) |
| #396 CLI whole-run lock holds | D-WL-3 companion, KEEP | open — whole-run LOCK_EX holds unchanged (`waitlist_jobs.py:128`, `waitlist_invites.py:236`) |
| #397 crash windows unrepairable | RE-SCOPE | open, re-scoped this turn to its four kinds |
| #398 token ordering | D-WL-6, KEEP | closed — the policy block (waitlistd.py:994) is the collected, per-flow ordering record; D-WL-6's ops-doc note lands this turn |
| #399 dropped rows not forget-deletable | D-WL-4, KEEP until prose lands | closed — the §5 prose documents the retention-window resolution |
| #401 triage naming/retention | D-WL-7, small fix | closed — names + 48h retention sweep shipped |
| #406 spool-write failure asymmetry | D-WL-8, small fix | closed — three paths fixed by #1390; the fourth (deleted notice) fixed this turn |

## 3. Decisions

- **D-WL-9 (#397 re-scope executed):** #397 covers exactly the four
  unrepaired commit→emit kinds — `confirmed` (waitlistd.py:2391),
  `dropped` (:1614), `reminder_sent` (:1584), `forgot` (:2761). Every
  one was re-verified commit-before-emit on the pinned tree (kill
  window exists; a crash leaves the event permanently unfired with no
  operator recourse). The six-kind reconcile build (this issue's four
  + `confirm_sent` (:1445, the §9 funnel's most metrically
  load-bearing event) + `waitlist_submitted` (:1945)) is forward work
  for a design turn; it does not land here because D-WL-5's accepted
  policy — conservative under-reporting, never over-reporting — still
  holds, and the funnel's accuracy need hasn't changed since
  2026-10-11.
- **D-WL-10 (#406 residual):** the deleted-notice path was genuinely
  out of #406's closed scope, not a regression — it was bare at
  #1390's merge. Fixed per D-WL-8's standing consensus rather than
  re-opening #406: a new issue for a one-line parity fix would have
  cost more process than the fix. The convergence doc records it so
  the close stays honest.

## 4. Remaining gaps (owning archetype)

1. Six unrepaired commit→emit kinds — design turn (D-WL-9), filed as
   a build home this turn.
2. Whole-wave / whole-run exclusive locks (#391, #396) — execution
   backlog; re-check when the store outgrows the purge cadence.
3. Footer-copy scope qualification + post-claim-erasure ownership
   naming (#393) — docs turn.
