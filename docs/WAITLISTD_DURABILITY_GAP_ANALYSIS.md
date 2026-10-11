# waitlistd durability gap analysis

**Pinned to main `f4c7c74` (2026-10-11).** Scope: the `site/` waitlist
component (`site/waitlistd.py`, 4092 lines; `site/waitlist_jobs.py`,
`site/waitlist_invites.py`, `site/waitlist_patha.py`) — vision-vs-state
for the crash-recovery / persistence / erasure story. This doc
consolidates the arch-finding cluster #386–#406 (all open, all
`track:open-source`); every claim below was re-verified against the
pinned tree before the disposition in §5 was assigned.

## 1. Vision

The waitlist store is a small, append-heavy, crash-safe operator store:

1. **Every commit has a repair path.** A kill between a row commit and
   its funnel emit is re-derivable by an operator tool (the
   `--reconcile` pattern, proven for `invite_sent`).
2. **Every lock is bounded.** No single request or CLI run can stall the
   daemon indefinitely; a wedged run fails loudly.
3. **Erasure is total or honestly scoped.** The §5 forget promise covers
   exactly the live stores, and the spec says in one place which rows
   can use it.
4. **Failure modes are uniform.** The same class of failure (spool write
   refuses, token ordering, emit/commit order) behaves the same way in
   every flow — one policy, documented once.

## 2. Findings (new this turn — verification deltas)

- **F-WL-1 — #387 is answered; close recommended.** The issue demanded
  "a deployment-contract decision" for the proxy-blind `_ip_limited`.
  The 20261002-2359 turn shipped exactly that: `WAITLIST_TRUSTED_PROXY`
  + `resolve_client_ip` (waitlistd.py:574–603, rightmost-XFF-wins
  across all repeated header instances), `_Handler._client_ip`
  (waitlistd.py:3922) feeding `submit_form(fields, self._client_ip())`
  (waitlistd.py:3944), and `_ip_limited(client_ip)` (waitlistd.py:1628)
  now keys off the resolved client IP, not the socket peer. The
  contract is documented in `site/README.md:81–96` (declare your proxy
  hops; when in doubt leave it unset). Nothing in #387's body is still
  true of the pinned tree.
- **F-WL-2 — #397 narrows; the tree shows six kinds.** `reconcile_claimed_events`
  (waitlistd.py:3223) + `--reconcile-claimed` (waitlist_invites.py:37–41,
  "the claimed half of --reconcile", issue #898) shipped since the
  finding was filed. Covered: `invite_sent`, `claimed`. Still
  unrepairable: commit→`confirmed` emit, commit→`dropped` emit,
  commit→`reminder_sent` emit, commit→`forgot` emit — plus two
  more in the same commit→emit class that #397's body never scoped:
  commit→`confirm_sent` (waitlistd.py:1270 — the §9 interim primary's
  denominator: confirm rate = confirmed / confirm-emails-sent, so the
  most metrically load-bearing of the six) and commit→
  `waitlist_submitted` (waitlistd.py:1738). `drop_expired`
  (waitlistd.py:1400–1421) still commits (`_save_row`) then emits with
  no re-derivation tool; `_queue_reminder_email` (def waitlistd.py:1325)
  still self-seals — `reminder_sent_at` + `_save_row` at :1383–1388,
  then `_emit` with no retry after a crash.
- **F-WL-3 — #386's trade-off is now deliberate prose, not an accident.**
  `confirm_get` (:2064), `forget_get` (:2153), and `claim_get`
  (:2580) all carry docstrings stating the render runs "under the data
  lock with a fresh view" because "a job (or racing POST) may have
  consumed/re-minted the token or dropped the row since the daemon's
  view was loaded" — the scanner threat model (§4.3) and wave races
  make stale renders user-visible lies. The structural cost is an
  exclusive cross-process lock per GET plus a full reload that is now
  conditional — skipped when the store is unchanged on disk since the
  #404 snapshot cache (the in-memory index is *not* discarded per
  request in the common case). The cost that remains is the lock
  itself; the implicit mitigation is store size, and it is never
  stated. Pinned explicitly as D-WL-1 below.
- **F-WL-4 — no genuinely-new gaps.** Spot-verification of #391
  (docstring at :2834 still admits "A large wave holds that lock for
  the whole run"), #398 (reminder `_save_row` → `_consume_token` at
  :1386–1388; drop `_consume_token` → `_save_row` at :1418–1421 — no
  stated ordering policy), #399/#393 (forget live tuple still
  `("pending", "confirmed", "invited")` at :1018), #401
  (`{ts}-{hex(4)}.eml` at :1856; `waitlist_patha.py` still holds no
  lock), #406 (`_queue_confirm_email`'s bare `self._write_spool(name,
  doc)` at :1262 vs `_queue_invite_email`'s try/except OSError →
  `return False` at :2713–2719) all confirm the filings' claims on the
  pinned tree. This doc files no new issues; its value is the
  decisions and the disposition table.

## 3. Decisions

- **D-WL-1 (#386): read-under-exclusive-lock stays.** The freshness
  requirement is load-bearing: these GETs are what mail scanners,
  unfurlers, and humans judge the token links by, and a wave / job /
  racing POST can invalidate a token between the daemon's last load
  and the render. The LOCK_SH alternative is rejected on the honest
  argument: under a proper shared-lock discipline (readers SH, writers
  EX) readers cannot observe torn files — and the tmp+fsync+os.replace
  discipline (#402) is tear-free even lock-free — so torn views are
  not the objection. The objection is that cross-process freshness
  still requires the under-lock re-parse (whose common-case cost the
  #404 snapshot cache already bounds: unchanged-on-disk skips the
  re-parse), so the win is only concurrent-GET interleaving — marginal
  for this store — while a two-mode advisory discipline shared
  between the daemon's threads and the separate CLI process adds
  silent-misuse risk (one mutating caller taking SH corrupts;
  lock-order docs must then cover modes). The mitigation is stated
  explicitly here for the first time: **the store stays small** —
  `drop_expired` (14d), `purge_dropped` (day-44), and the quarantine
  retention bound it; if GET latency becomes an operator problem, the
  lever is purge cadence, never lock weakening. No code change.
- **D-WL-2 (#387): closed by the trusted-proxy contract.**
  Deployment contract (per #896/#900): operators declare proxy hops in
  `WAITLIST_TRUSTED_PROXY`; the daemon keys abuse limits off
  `resolve_client_ip` and refuses to run with a malformed declaration.
  The issue's "document the effective behavior honestly" fallback is
  moot — the contract is the documented behavior.
- **D-WL-3 (#391, #396): whole-wave / whole-run exclusive lock stays.**
  Per-row lock release is rejected on the real mechanism: it does not
  multiply crash windows — each row's spool→commit→emit ordering and the
  reconcile repair hold with or without the whole-wave lock, and a
  mid-wave crash is re-runnable either way. What per-row release
  introduces is cross-process interleaving *between* rows: a reminder
  re-mint, `drop_expired`, or a racing POST mutating rows the wave
  already scanned breaks the wave's FIFO order, the 3/24h email cap
  accounting (waitlistd.py:2815), and the manifest-as-one-consistent-run
  invariant. The lock protects the wave's multi-row transactional
  invariant, not the per-row crash windows. The documented mitigation
  stays "tens of rows" waves. No stuck-wave heartbeat: the operator sees a
  stalled wave in the job's run output; a heartbeat stays a
  nice-to-have, not a design requirement. Issues stay open as the
  execution backlog for any mitigation work.
- **D-WL-4 (#393, #399): forget scope = the pre-claim live set.**
  The forget flow covers rows in `("pending", "confirmed", "invited")`
  — no more, no less. Post-claim (`signed_up`) rows are assigned to the
  signup-era surface — which is H15-future (`WAITLIST_OPERATIONS.md`
  §8, "When signup opens…"); §8 currently covers only the funnel
  handoff (pre-fill, identity linking) with no erasure posture, so
  "owned by the signup-era surface" presently means **unowned**:
  post-claim erasure has no owner until the signup surface ships, and
  the §5 prose must define that ownership rather than imply a
  handoff exists. The waitlist forget flow does not follow
  rows out of the waitlist. Dropped rows keep the §5 30-day retention:
  erasure is unavailable during the retention window, and that must be
  stated honestly rather than implied by dead footer links.
  **Execution (for a docs/fix turn, not this one):** §5 must state the
  scope in one place, qualify the invite footer's deletion promise
  ("this link works while your entry is on the waitlist"), and name
  post-claim erasure as unowned-until-H15. Issues stay open until the
  prose lands.
- **D-WL-5 (#397): accept conservative under-reporting for the six
  remaining kinds — for now.** The re-derivation pattern is proven
  twice (`invite_sent`, `claimed`); extending it to all six
  unrepaired kinds (`confirmed`/`dropped`/`reminder_sent`/`forgot` from
  #397's scope, plus `confirm_sent`/`waitlist_submitted` found this
  turn) is real work, not a drive-by, and the funnel's current
  under-reporting is conservative (never over-reports). #397 is
  re-scoped to its four unrepaired kinds; the two repaired halves are
  struck from it; the two extra kinds are carried by the design turn
  (forward-work item 5).
- **D-WL-6 (#398): no global ordering policy — per-flow orderings stand
  as documented in code.** The flows' orders (reminder: save→consume;
  invite: consume→save; forget: rewrite→consume (auxiliary confirm/invite tokens killed first; the user-facing forget token dies after the row commit — the #394 fail-safe); claim: save→consume;
  drop: consume→save) each have a stated crash-window rationale in
  comments/docstrings. Imposing one policy would trade five
  reasoned orders for one unreasoned one. Recommendation for the
  keeping issue: collect the per-flow ordering note into
  `WAITLIST_OPERATIONS.md` (one line per flow) so the next reader
  doesn't re-derive it.
- **D-WL-7 (#401): small-fix consensus, no design decision.**
  Entry-scoped names (or longer entropy) + a triage retention job.
  Stays open as a small fix-turn item.
- **D-WL-8 (#406): mirror-the-invite-path consensus — all four bare
  paths.** Four `_write_spool` calls have no try/except (verified on
  the pinned tree): :1262 (`_queue_confirm_email`), :1378
  (`_queue_reminder_email` — highest blast radius: an OSError there
  propagates through `send_reminders`' loop and kills the whole +7d
  run, skipping every later due row), :1933 (`_spool_patha_email`),
  :2503 (`_queue_deleted_email` — raising post-commit 500s an
  already-successful deletion). #406's body names only confirm+patha,
  but the fix turn should take all four (fail the email, not the
  request) rather than leave the asymmetry half-fixed. Stays open as
  a small fix-turn item.

## 4. Disposition table

| Issue | Disposition | Rationale |
|---|---|---|
| #386 GETs take the exclusive lock | KEEP | D-WL-1 pins the trade-off; re-check if the store outgrows the purge cadence |
| #387 proxy-blind `_ip_limited` | **CLOSE** | F-WL-1: answered by #896/#900 — contract shipped, `_ip_limited` keys off the resolved client IP |
| #391 wave holds the lock | KEEP | D-WL-3: trade-off pinned; heartbeat stays nice-to-have |
| #393 post-claim forget invisibility | KEEP | D-WL-4: scope pinned; awaits the §5 prose edit |
| #396 CLI whole-run lock holds | KEEP | D-WL-3 (same class as #391); companion kept |
| #397 crash windows unrepairable | RE-SCOPE | F-WL-2: narrow to `confirmed`/`dropped`/`reminder_sent`/`forgot` (the two extra kinds, `confirm_sent`/`waitlist_submitted`, are outside the issue's scope — carried by the design turn); D-WL-5 accepts conservative under-reporting meanwhile |
| #398 token consume-vs-commit ordering | KEEP | D-WL-6: per-flow orders stand; collect into the ops doc |
| #399 dropped rows not forget-deletable | KEEP | D-WL-4: retention window documented honestly; execution = §5 prose. Related: #1162 (tenant-record retention) should unify with this when it executes |
| #401 triage unbounded / name collisions | KEEP | D-WL-7: small-fix consensus |
| #406 spool-write failure asymmetry | KEEP | D-WL-8: mirror-the-invite-path consensus |

## 5. Forward work (for fix/dx/docs turns)

1. Close #387 with the F-WL-1 pointer (this turn's ship does it).
2. Re-scope #397's title/body to its four remaining kinds (D-WL-5; the two extra kinds are not #397's to carry).
3. Small fixes, each a ≤30-min turn: #406 (OSError → False in all
   four bare spool paths — D-WL-8 enumerates them), #401 (triage naming
   + retention job).
4. Docs: the §5 forget-scope prose (D-WL-4) + the per-flow ordering
   note (D-WL-6) — one docs turn, or two small ones.
5. The six remaining reconcile kinds (#397's four as re-scoped, plus `confirm_sent` + `waitlist_submitted`) — a design turn when the funnel's accuracy matters more than it does today.
