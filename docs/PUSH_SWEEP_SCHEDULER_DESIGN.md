# Push sweep scheduler design (#1063, D9)

First slice of issue #1063 — the design the reminder/digest scheduler
build executes against. Companion docs: the event taxonomy
(`PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md`, decisions D8–D13), the enqueue
boundary (`hosted/push_enqueue.py`, D50–D57, #990), the event→push
mapping (`hosted/push_events.py`, D58–D65, #969/#1062), and the lane
convergence pin (`PUSH_LANE_CONVERGENCE_2026-10-05.md`, §3).

## 1. The problem

The push lane's paging policy exists and is tested
(`hosted/push_events.py`: `maybe_enqueue_reminder`,
`maybe_enqueue_digest`), but nothing calls it. The control-plane Worker
is request-driven — it reacts to HTTP fetch events only — and has no
scheduled/cron path (verified against the deployed worker checkout in
the taxonomy analysis). Reminders ("a due reminder pages exactly once")
and digests ("a digest pages at most once per owner-hour") need a
cadence the request path cannot supply.

## 2. Decisions pinned (continuing the push lane's D-series; D58–D65 are #969's)

- **D66. The scheduler is a Cloudflare Workers cron trigger on the
  control-plane Worker, per-minute.** The sweep is a new `scheduled`
  event handler in the plane Worker, wired via the cron trigger
  (`* * * * *`). Rationale: the D1 database and the enrollment registry
  live on the plane, so the plane is the only place that sees every
  box's pending approvals; a box-side cron would need cross-plane
  credentials it must never hold (D2 — owner identity is resolved from
  the enrollment registry, never from a box assertion), and an
  operator-side cron is a new piece of infrastructure with no owner.
- **D67. Two passes per sweep, reminders first, digests second.** Pass 1
  (reminders): select candidate approvals and call
  `maybe_enqueue_reminder` per candidate. Pass 2 (digests): scan
  `push_digest_state` for rows with `count > 0` in the owner's current
  hour window and call `maybe_enqueue_digest`. Ordering rationale: a
  reminder that tips an owner over budget must coalesce into the digest
  *in the same sweep* (D10 pins the coalescing, not the same-sweep
  timing — the same-sweep consequence is this doc's inference: firing
  the digest after the reminder coalesced in the same sweep is the only
  ordering that cannot strand counts), not after the digest already
  fired. Under overlap the digest carries the count-at-fire-time;
  coalescing that lands after the digest fired is accepted count drift
  for that window (no refire — D54/D57 dedup). The same-sweep coalescing
  guarantee holds only for a non-overlapping sweep.
- **D68. The sweep's candidate SELECT is a hint, not a decision.** The
  reminder pass selects
  `WHERE status = 'pending' AND decision_seq IS NULL`
  `AND created_at + (expires_at - created_at) / 2 <= :now`
  `AND (expires_at - created_at) >= 300`
  (D8 timing, D12 gate-1). Over-selecting is safe; under-selecting is
  the bug — the query must never filter *harder* than the policy.
  Authority order: the policy's gate-1 re-read (D59) is the timing
  decision, the boundary's page-once dedup (D57) is the
  never-double-page guarantee. A candidate the sweep returns but the
  policy rejects is a wasted re-read, not a defect. D12's lease-mark is
  superseded by the D57 page-once index and the D61 idempotent audit —
  the sweep writes no lease rows.
- **D69. Bounded work per sweep; overlap is safe, not prevented.**
  A sweep must normally finish inside the 1-minute cadence, so the
  candidate query pages (`LIMIT`, ordered by `(box_id, aid)`) instead of
  scanning the whole table. If a sweep overruns, the next cron fires
  anyway: the D57 page-once dedup and the idempotent D61
  `suppressed_terminal` audit make overlapping sweeps a no-op, not a
  double-page. No locking, no leader election — idempotency is the
  concurrency plan (same discipline as the #874 box-side ingest).
- **D70. The sweep never pre-checks the D10 budget.** `enqueue_page`
  owns the atomic budget reservation (#990 — a sweep that pre-checked
  and then enqueued would TOCTOU the single-statement reservation).
  The sweep passes every due page through the boundary and lets
  `suppressed_budget` dispositions and digest coalescing do their job.
  A sweep that skips enqueue on its own budget estimate would invent a
  second, racing budget ledger.
- **D71. The DO-alarm retirement rule, made concrete (D9's rule).** When
  #958's per-approval Durable Object alarms land, the same change must
  retire the cron sweep's *reminder* pass — either delete the pass or
  gate it behind a plane-side setting (`PUSH_SWEEP_REMINDERS_ENABLED`,
  default true) that the DO-alarm change flips off. The digest pass is
  unaffected: DO alarms replace reminders, not the D54 digest trigger.
  The #958 slice's acceptance test must name the rule: enabling alarms
  with the reminder sweep on must not double-fire. A "both on in
  staging" overlap window is allowed only with the alarms
  feature-flagged off in production.
- **D72. `deploy_worker.py` cron-trigger support lives in the plane
  workspace.** `deploy_worker.py` is not in this repo; it is the
  deployed plane workspace's deploy script. The #1063 build slice adds
  there: (a) the cron trigger declaration (`wrangler.toml`
  `[triggers] crons = ["* * * * *"]`, or the equivalent scheduled-trigger
  API call if the workspace provisions triggers via API), and (b) a
  post-deploy verification that the trigger *itself* is registered —
  list scheduled triggers via the Workers API/wrangler in staging and
  assert the `* * * * *` entry is present — plus one invoked
  `scheduled` event in staging asserting a clean no-op sweep, or one
  observed live cron tick. A handler that runs proves nothing about the
  trigger registration, which is exactly the silently-unwired failure
  mode: without this check the #1063 acceptance criterion could pass in
  staging while production never ticks.
- **D73. One clock, one read, pure arithmetic.** The sweep takes `now`
  once (epoch seconds, UTC). `created_at`/`expires_at` on the #872
  record are epoch ints, so due-ness is epoch arithmetic — the halved
  TTL `(expires_at - created_at) / 2` is INTEGER division in SQLite
  (verified: `601/2 → 300`), which over-selects by at most half a
  second in the safe direction per D68 — with no ISO parsing in the
  hot path. The D59 adapter's normalization (epoch → ISO) stays in the
  plane-side `get_record` adapter (§3.2) where the #969 docstring
  already places it; the sweep does not duplicate it.
- **D74. The sweep is the D62 quiet-period caller, not its inventor.**
  The heartbeat-stale quiet period (D62, F7, 4h) is the #969 build's
  timing pin; the sweep only invokes it on the schedule D9 provides.
  The stale-epoch derivation is plane-side caller logic per the #969
  docstring's D2 restatement — the sweep's job is the cadence, not the
  derivation. The window is armed by `queued|accepted` rows so the sender
  loop's delete-on-terminal (D50) cannot evaporate it mid-sweep.
- **D75. Truncation is self-healing.** The candidate hint additionally
  anti-joins approvals whose reminder page already exists in
  `push_send_results` — the boundary's outcome-blind dedup fast-path,
  mirrored in SQL on `box_id || char(0) || aid` (the exact page-key
  encoding). The exclusion is precise: only candidates the policy would
  certainly `duplicate` are excluded — a page row exists for the exact
  key, the record is not terminal (`decision IS NULL` and not
  clock-expired, mirroring the adapter's terminal derivation), and the
  record is well-formed (epoch ints). A paged approval that later
  clock-expires stays a candidate, so gate-1 still writes its D61 audit
  (pre-D75 behavior preserved — the terminal check runs before the
  boundary dedup, and the audit uses the suffixed key the page-key
  anti-join never matches); a paged record that corrupts between ticks
  stays a candidate, so the D59 fail-loud still fires. Every excluded
  candidate would have returned `duplicate` — no page, no audit, no
  state change — so the exclusion is behavior-preserving, and a
  truncated sweep's remainder is actually reached on the next tick
  instead of the already-processed rows re-dominating the first pages.
  The `page_size × max_pages` cap stays a capacity assumption (peak
  due-reminders/minute); repeated truncation is an operator alert.

## 3. What the build slice implements (#1063)

1. The sweep logic the plane Worker's `scheduled` handler will drive:
   the three-pass sweep — reminders, then digests (D67), then the
   cadence-driven watchers (D74) — with paged, self-healing candidate
   queries (D69, D75) and a single UTC epoch `now` (D73). The per-minute
   `scheduled` trigger registration itself (D66) is #1069's, not this
   slice's.
2. Plane-side wiring of the policy functions against the live D1
   database (the D49-style adapter from #969's docstring: `get_record`
   translating the #872 epoch-int record shape into the D59 dict).
3. The acceptance test, sliced: a due reminder produces exactly one
   `queued` page; a decided/expired approval is never a candidate, so
   it pages zero times and writes zero audit rows (operator visibility
   is the approvals record itself); a pending approval terminal only
   by the clock reaches gate-1 and writes exactly one idempotent
   `suppressed_terminal` audit row (D61). The "with no human driving
   it" half of #1063's acceptance criterion is owned by #1069 (the
   cron-trigger wiring), which keeps this issue open until it lands.
4. The cadence-driven watcher calls (D74/D63): per sweep, derive
   stale-epoch candidates (missed-heartbeat counting per the #864 1/min
   cadence) and call `on_heartbeat_stale` per candidate box, and derive
   token-warning candidates (2h lead; F6's "no rotation since the last
   window" check against the boxes-row `token_hash`) and call
   `on_token_expiry_warning`. These were not in #1063's original scope
   (reminders and digests only), but D74 and D63 already pin the sweep
   as the caller — the design extends the build scope, recorded in the
   issue's pointer comment. The derivation rules stay caller-side per
   the #969 docstring; the sweep owns the cadence.

## 4. What this does not claim

- The per-minute cron trigger registration on the plane Worker (D66)
  and the `deploy_worker.py` cron-trigger declaration + staging smoke
  (D72) are not this slice's: they are tracked in #1069, which keeps
  #1063 open until the "without a human driving it" half of the
  acceptance criterion lands. A sweep handler that runs proves nothing
  about the trigger registration — the silently-unwired failure mode
  D72 names.
- The sender loop (#967 remainder) is still unbuilt: a sweep-fired page
  lands in the outbox; nothing yet fans it out to devices. The #1063
  acceptance criterion is met when the page exists in the outbox —
  delivery is the sender loop's acceptance, not the sweep's.
- Push subscriptions (#968) are still blocked on the operator-owned
  data key (standing NEEDS_USER entry): the sweep enqueues against
  `owner_principal` resolved from the enrollment registry (D2), and
  fanout happens later when subscriptions exist.
- The D1 tables the sweep reads are the #988 contract tables
  (`push_budget_counters`, `push_digest_state`) plus the #872
  `approvals` record — no new tables in this slice.
- Digest content assembly, delivery through the #967 sender loop, and
  the `push_digest_state` reset contract are #1064's; this slice only
  fires the D54/D64 trigger (`maybe_enqueue_digest`). A digest page
  enqueued here carries no composed body until #1064 lands.
- The DO-alarm future (D71) is a rule for a later change, not work
  this slice performs.
