# Push event taxonomy + anti-spam bounds gap analysis (GP3 / #969)

**Status: analysis, not a commitment.** Extends the parent's GP3 line
(`docs/HOSTED_PLANE_PUSH_GAP_ANALYSIS.md` §3 — "#969 — event→push
mapping + anti-spam bounds"), which it does not re-litigate: the
parent's decisions D1–D7 stand, and the decision numbers here continue
the series (D8–D13). Code-state claims were verified against the repo
tree at main `3f13ca1` (2026-10-04 ~05:2x CDT) and the plane worker
checkout the #846/#873/#952 plane halves were deployed from (no
`scheduled` handler, no cron trigger support in `deploy_worker.py`, no
wrangler config in the checkout — the plane is request-driven today).
Issue/PR numbers are GitHub references as of 2026-10-04 (not
code-verifiable from the tree). Honesty rules apply
(`docs/POSITIONING.md`): this describes current state and work to do,
not promises. Nothing here sends a push.

**Non-overlap map (what this doc is not):**
- The parent analysis (`docs/HOSTED_PLANE_PUSH_GAP_ANALYSIS.md`) — owns
  D1–D7 (box→plane→device only, plane-originated events, one plane
  VAPID identity, "go look" payloads, tenant/owner consumer only,
  reminders-as-leases, email cold-start) and the GP1/GP2/GP4 slices.
  This doc is GP3's working paper only.
- The operator fan-out (`docs/ALERT_PUSH_FANOUT_SPEC.md`, G23 / #797) —
  designs operator paging; the consumer here is the tenant owner (D5),
  and this doc does not page the operator.
- The first-approval summons (`docs/FIRST_APPROVAL_SUMMONS.md`, #428) —
  owns the no-subscription-yet bootstrap via email (D7). This doc
  starts *after* a subscription exists (#968); cold start is not its
  problem.
- The sender crypto (`hosted/push_crypto.py`, GP1 S1 — validated) and
  the payload scrub (`hosted/push_payload.py`, GP4 — shipped #980) —
  this doc consumes them; it signs nothing and scrubs nothing.
- The approvals record schema
  (`docs/APPROVALS_PLANE_PROTOCOL.md`, #872) — the record's TTL,
  expiry, and `decision_seq` semantics below are quoted from it, not
  redefined here.

## 1. What GP3's issue body promised vs what exists

GP3's scope names the event set (approval filed; T-15m TTL reminder
per D6; decided → cancel outstanding; token-expiry warning (#846 24h
cadence); box revoked; heartbeat-stale) plus the per-(box, window)
rate bound the hostile-box model requires. Reading the actual state
against that promise:

- **F1. "T-15m" is unsatisfiable under the shipped record.** The #872
  record (`docs/APPROVALS_PLANE_PROTOCOL.md` §"Expiry: server-side
  only") takes `expires_in_secs` default **600 (10 min)**, clamped to
  **[60, 3600]**. GP3 was written against the "60-minute" TTL the
  parent doc assumed — itself a slip: the shipped constants are
  `APPROVAL_TTL = 600` seconds (the 10-minute default) with an
  `APPROVAL_TTL_MIN = 60` *second* floor. A reminder "15 minutes
  before expiry" cannot fire for a 10-minute approval — and the clamp
  means a fixed minute-offset is wrong for *every* TTL except the one
  it was written against. The reminder point must be
  **parameterized on the record's own TTL** (decision D8, below); the
  issue body's "T-15m" language is superseded by it.
- **F2. The T-minus reminder has no scheduler home.** Nothing on the
  plane can fire at T-minus: the worker checkout has no `scheduled`
  handler, no cron trigger support, and no wrangler config — the plane
  is request-driven end to end today. The reminder is the only GP3
  event that is *time*-originated rather than *state*-originated, so
  it is the only one that needs a scheduler. Two homes are possible:
  (a) Durable Object alarms on #958's per-box DO, or (b) a new
  scheduled worker entry sweeping the D1 database for due reminders.
  Home (a) couples GP3's reminder slice to #958's 2+-slot build; home
  (b) is independent. Decision D9 picks (b) first, (a) later.
- **F3. The page/no-page line is not drawn for every event.** The
  parent pins *what causes* a push (plane-observed state, D2) but not
  which derived events *deserve* one. Read through the hostile-box
  lens (the #902 class, applied outward — D1): a box that can file
  approvals at the filing endpoint's admission rate must not be able
  to convert that into pages at the same rate. That forces an
  explicit taxonomy: each event gets a page/no-page verdict, a dedup
  key, and a cancellation rule (§2).
- **F4. "Decided → cancel" has no enforcement point.** The #873
  decision enqueue is the cancellation *signal* (parent D6), but no
  code checks it between the reminder sweep and the send. Without a
  re-check the owner who just decided on the dashboard gets a
  reminder for the approval they answered — the exact failure D6
  exists to prevent. Decision D12 pins the two-gate lease.
- **F5. The anti-spam bound has no shape.** GP3 names "per-(box,
  window) rate bound" and nothing else: no window, no count, no
  behavior on overflow (drop? coalesce? defer?), no relation to the
  reminder (which is plane-scheduled, not box-driven), and no answer
  for whether delivery *failures* (410, dead-letter) consume budget.
  Decision D10 pins the shape.
- **F6. The token-expiry warning's trigger is underspecified.** #846
  ships 24h token expiry with box-side auto-rotation. A healthy box
  rotates before expiry and should never trigger a warning — so the
  event is not "token within X of expiry", it is "token within X of
  expiry AND no successful rotation since the last heartbeat window",
  i.e. auto-rotation has failed (the rotate-401/403 path in
  `docs/PHONE_HOME_WIRE_PROTOCOL.md`). The warning keys on the token
  *generation*, so a successful rotation resets it (decision §2).
- **F7. Heartbeat-stale's page needs a quiet period.** Staleness is
  derived (missed heartbeats per the #864 cadence), not observed —
  a flapping box (brief network loss, reboot) would otherwise page on
  every flap. The taxonomy (§2) pages once per stale-epoch and arms a
  quiet period; the exact multiple of the heartbeat interval is the
  #969 build's call.

## 2. The taxonomy (pinned)

Every row is a plane-originated event (D2). "Page" is the enqueue
verdict; nothing else may enqueue.

| Event | Page | Dedup key | Cancelled / superseded by |
|---|---|---|---|
| approval filed | once | `(box_id, aid)` — the same key the #952 endpoint dedups filings on | decision, expiry (record terminal) |
| reminder (T-minus) | once, at `created_at + TTL/2`, only when `TTL ≥ 300s` (D8) | `(box_id, aid)` | decision, expiry — re-checked at both lease gates (D12) |
| decided (#873 enqueue) | **no page** — this is the cancellation *signal*, not an event (D6/D12) | — | — |
| expired (server-side) | **no page** (D11) | — | — |
| token-expiry warning | once per token generation, at 2h before expiry (recommended lead time; the #969 build adopts-or-records it), only if no rotation since the last window (F6) | `(box_id, token_generation)` where generation := the current `token_hash` in the boxes row (D13) | successful rotation (new hash = new generation = key resets) |
| box revoked | once | `(box_id, revoked_at)` — the key *is* the revocation event's identity (revocation is naturally singular; a timestamp never repeats, so this is identity, not collision-prone dedup) | — |
| heartbeat-stale | once per stale-epoch, with a quiet period (F7) | `(box_id, stale_epoch)` | heartbeat resume (new epoch) |

Notes the table needs to say out loud:

- **Expiry is a no-page terminal (D11).** The filed page plus the
  reminder already covered the approval; paging "expired unanswered"
  buzzes about a dead record. If a future lane wants an expiry
  digest, it is a separate design, not GP3.
- **410 → re-subscribe is a dashboard affordance, not a push (GP2
  caveat).** You cannot push to a dead subscription. When the GP1
  sender taxonomy reports 410, the dashboard box card (#954/#968
  surface) prompts re-subscribe; no page is emitted.
- **Revocation pages; grandfathering does not.** The pre-#844
  keyless-grandfathered path (if it survives past #846) is a
  plane-side state the owner set deliberately — no event, no page.

## 3. Decisions pinned (continuing the parent's D-series)

- **D8. Reminder timing is parameterized, not T-15m.** Reminder at
  `created_at + TTL/2`, fired only when the record's TTL ≥ 300s.
  Rationale: always positive for every legal TTL (600s default →
  T-5m reminder; 3600s → T-30m; 60s → no reminder, correctly, since
  the window is nearly over by the time the reminder sweep runs).
  The issue body's "T-15m" is superseded by this rule; the #969
  build deletes the phrase.
- **D9. Reminders ride a cron-sweep scheduler first; DO alarms
  later.** The reminder slice does not wait for #958's Durable
  Object: a new scheduled worker entry (per-minute cron) scans the
  D1 database for due reminders and enqueues them. One code path,
  no DO dependency; #958's DO may adopt per-approval alarms in a
  later slice without changing the taxonomy — but that slice must
  retire or feature-gate the cron sweep in the same change, or
  reminders double-fire. The deploy path
  (`deploy_worker.py`) needs cron-trigger support for this — that
  support is inside the reminder slice, not a separate item.
- **D10. Page budget: per-(box, hour) ≤ 3, per-(owner, hour) ≤ 10.**
  Overflow does not send — it coalesces into a single hourly digest
  page per owner ("N approvals need you — open the dashboard"), which
  carries the count plus the dashboard deep-link rather than a single
  `aid`, and still counts as one page against the owner's hourly
  budget (it is a buzz, not silence). Reminders **consume** the
  per-(box, hour) budget like any page: they are plane-*scheduled*
  but box-*count-driven* (one per box-filed approval, and the plane
  worker has no per-box filing throttle), so exempting them would
  let a hostile box bypass the bound 1:1 — N filings/hour = N
  exempt buzzes. Over-budget reminders coalesce into the digest
  instead of paging individually. The "one reminder per approval"
  cap (D6/D8) stays as a separate, complementary bound. Delivery
  failures (410, dead-letter) do not consume budget: the budget
  bounds *successful buzzes*, not attempts. Page-once per
  `(box_id, aid)` is enforced by the enqueue dedup key, independent
  of the budget.
- **D11. Expiry pages nothing.** (See §2 notes.) Terminal states
  observed server-side are not paging events.
- **D12. The reminder lease has two gates.** Gate-1 at sweep: select
  records with `status = pending AND decision_seq IS NULL` and mark
  the lease. Gate-2 at send: re-read the record; if decided or
  expired, drop silently (no page) and write an audit row. The audit
  row feeds the sentinel leg (#798–#800), not the phone — a dropped
  reminder is operator-visible, never owner-paged. This is what makes
  "decided → cancel outstanding" enforceable rather than aspirational.
- **D13. Event identity keys are the table's, verbatim — with "token
  generation" defined here.** The #969 build uses these keys for
  dedup; inventing a new key scheme is a re-litigation of this doc.
  "Generation" is not a schema field (#846's boxes row carries
  `token_hash`, `token_expires_at`, `revoked_at`,
  `prev_token_hash` — no generation counter): generation := the
  current `token_hash` value in the boxes row, so a rotation
  (hash change) is definitionally a new generation and resets the
  warning key.

## 4. Backlog reconciliation

No new GitHub issues are filed by this analysis: the sub-slices
(token-expiry warning, heartbeat-stale derivation, cron-sweep
scheduler, digest coalescing) are all inside #969's stated build
scope — they are this doc's working detail, not separate work
streams. The reconciliation lands as a pointer comment on #969
(superseding "T-15m" with D8, recording the D9 scheduler fork, and
adopting the D10–D13 pins), so the issue body no longer promises
what the record schema cannot deliver.

## 5. What this does not claim

- No push machinery exists yet: no sender (GP1 S1 crypto is validated,
  the send path is not built), no subscription store (GP2 #968 open),
  no scheduler (D9 unbuilt). This doc pins GP3's design; it implements
  nothing.
- The digest page ("N approvals need you") is still a page: it
  consumes one unit of the owner's attention budget per hour, not
  zero. D10 bounds the cannon; it does not make paging free.
- The heartbeat-stale quiet period is pinned as a *rule* here; its
  exact duration is the #969 build's call and must be recorded when
  chosen. The token-warning's 2h lead time is the recommended default
  the build adopts-or-records (the rule — warn when auto-rotation
  appears to have failed, keyed on the token hash — is pinned).
- Operator alerting for incidents stays G23's job (D5). A box going
  stale is an owner event (their agent is parked); it is not an
  operator page.
