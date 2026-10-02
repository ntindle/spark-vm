# Alert fan-out into the H14 push plane (G23 S1)

Doc-first; the honesty rule is G17 S1's, extended by the G21–G26
analysis's no-fiction contract: this doc pins the *intake design* —
how a fleet alert reaches the operator's phone — not a promise that
the paging exists. It designs the intake for S2/S3; nothing here
sends a push. This is the S1 slice of G23 (tracked on issue #797);
S2 builds the enqueue path, S3 the tenant variant.

## 1. What the earlier designs already decide (bounds, not repeated)

- **G17 S1** (`fleet/events.py` + `docs/UPDATE_EVENT_REPORTING.md` §4):
  four alert rules evaluated on every collect, journaled to
  `alerts.jsonl`. Rule 1: any `rollback-failed` → immediate alert, one
  per rollback-failed event. Rule 2: correlated failure — ≥2 boxes
  reporting failed/rolled-back on the same `(subcomponent, to)` within
  a 30-minute window; the anchor is the window's earliest event, so a
  genuinely new cluster (new anchor) re-fires while the same cluster
  dedups. Rule 3: silent wave — **disarmed at S1** (`rollout`
  envelope is null on every event; the rule cannot fire). Rule 4: stuck
  precheck — ≥N `precheck-fail` events on one box inside the window,
  anchored the same way. Alert identity is `alert_id` =
  `uuid5(rule|box_id|subcomponent|to|dedup_key)` — stable across
  collector re-runs; the collector dedups appends on it. The S1
  transport is the journal plus `fleet events watch` exiting nonzero
  on unacknowledged alerts; the scan window is bounded (#832).
- **H14** (`confirm/push.py` + `docs/PUSH_NOTIFICATIONS.md`): the push
  plane — `PushQueue` durable journal + standalone worker with
  claim/lease/backoff (1m → 2m → 4m → 8m → 16m → 30m → 30m, then
  dead-letter), idempotent notified log keyed per approval id,
  fail-open (a queue failure never loses the filed approval), VAPID
  keypair operator-generated, mode-0600 operator-owned files, no narrow
  sudoers grant (operator commands run from a root shell). Payload
  discipline: encrypted payload carries the page-visible text plus the
  id — never secrets, never model-authored free text. Answering an
  approval closes its notification on the device. Subscriptions are
  per-box; per-tenant subscription scoping is follow-up work (H14 part
  b, needs H10/H11's tenant model).
- **G22 S1** (`docs/STATUS_PAGE_FEED_SPEC.md`): the page is the feed,
  not the pager — who pages the operator is this doc's job (§7 of that
  spec). Ack ≠ resolve: acked is operator-declared
  (`fleet events ack` flips `acked` by atomic journal rewrite);
  resolved is journal-derived per rule, never declared. An
  acknowledged-but-unresolved alert stays listed; the page never
  auto-clears what it cannot disprove. The feed holds no dedup set, no
  ack cache, and performs no writes.
- **G21 S1** (`docs/FLEET_READ_API_SPEC.md`): mutations stay CLI-only
  until the S2 console's auth story; the console is the fleet-era
  surface that will eventually own the subscribe UI.
- The G21–G26 analysis (`docs/FLEET_OBSERVABILITY_CONSUMPTION_GAP_ANALYSIS.md`
  §G23) decided: alerts become push-eligible through a *designed
  intake*, not by bolting fleet code onto confirmd's queue. The
  consumer set is the operator, not the tenant — operator push, which
  H14 does not currently model.

## 2. The intake: a second producer class on the same machinery

The decision, stated once: **G23 extends the H14 push plane to a new
producer class (operator paging); the intake is the design, not a
confirmd patch.** What that means concretely:

1. **Separate queue, separate identity, same worker code.** The
   operator intake runs its own `PushQueue` instance — its own queue
   journal, dead-letter file, and notified log — under
   operator-owned, mode-0600 paths on the control-plane host. The
   confirmd approval queue is never touched: different consumer
   (operator vs tenant/owner), different VAPID identity (the operator
   host's own keypair, generated on the box, never committed), and
   different lifecycle (alerts fire/ack/resolve; approvals are
   filed/answered). The worker loop is already generic over queue
   paths; S2 parameterizes it by producer class. One worker process
   serving both queues is operational convenience, decided at S2 —
   the queues themselves never mix (Q3).
2. **Placement mirrors confirmd's deployment.** H14's push runs where
   confirmd is deployed — on the operator's infrastructure, not on the
   tenant box. The fleet intake runs on the operator control-plane
   host against the operator's estate dir (`alerts.jsonl`). The
   operator commands (key generation, test-push, worker runbook)
   follow the same access model: root-shell operator commands, no
   narrow sudoers grant — the H14 rationale transfers verbatim (a
   `python3`-as-secrets-owner grant would be arbitrary code execution
   as the queue owner).
3. **Both-supported by construction.** The push plane is already a
   portable component per the PUSH doc. The self-hosted N-box operator
   runs the same intake against their own estate dir; the hosted
   control plane reuses the identical design. Track: hosted-product
   (the issue's label), but the OSS operator path keeps working.

The intake's job, in one line: observe `alerts.jsonl`, page each
page-eligible (§3) unacknowledged alert **once**, and never page an
alert the operator has acked.

## 3. Paging eligibility: which rules page, and exactly once

The intake reads the alert *journal*, never the alert evaluation
path (the G21–G26 composition rule: consumers read what the
producers journaled).

### 3.1 Which rules page

| Rule | Pages? | Why |
|---|---|---|
| 1 — rollback-failed | **Yes, immediately** | A box stuck on a known-bad build is the highest-value page in the fleet. |
| 2 — correlated failure | **Yes** | The bad-release shape: ≥2 boxes on the same target is precisely what should wake a human. |
| 3 — silent wave | **Not until G15 S2 arms it** | The rule cannot fire while the `rollout` envelope is null. And when it arms: one page per (box, silence episode), never per tick — §3.3. |
| 4 — stuck precheck | **Yes** | Threshold'd at S1 (≥N precheck-fails) — the quieting is already in the rule. |

Freeze flips and gate publishes are *not* page-eligible: they are
operator-initiated state changes with their own journaled records
(freeze-hold events, G18 S1a), rendered on the G22 feed. Paging on a
freeze you just ordered is noise.

### 3.2 Dedup: one page per `alert_id`

The intake's notified log keys on `alert_id` — the same UUIDv5-stable
identity the collector already dedups on, reused per H14's notified
log pattern (H14 keys per approval id; the intake keys per alert id).

- A re-evaluation that re-fires the same `alert_id` never re-pages.
  The collector already dedups journal appends; the intake's notified
  log is the second line of defense for any path that re-sees a
  journaled alert.
- A genuinely **new** `alert_id` pages again — correct, because a new
  id means a new anchor (rule 2's window moved, rule 4's anchor
  moved, rule 1's new rollback-failed event). New condition, new page.
- **No intake-side dedup set beyond the notified log.** Same
  discipline as G22's feed: the journal is the source; the notified
  log is idempotency, not memory.

### 3.3 The rule-3 tick problem (a design constraint for G15 S2)

Rule 3's `dedup_key` is the window cutoff (`cutoff.isoformat()`), so
as the armed cutoff advances, a persistently silent box churns
`alert_id` on every evaluation — one arming would page on every
tick. This is **a producer defect the intake must not paper over**.
The contract this spec pins: when G15 S2 arms rule 3, either the
rule's `dedup_key` stabilizes per silence episode (owned by the
arming design), or the intake never sees the tick churn because the
producer fixed it. The intake is not a coalescing layer; inventing
episode detection in the intake would be a second, divergent dedup
rule — exactly what G22's §4 forbids. Open question Q1 names the
decision site.

### 3.4 Ack suppression (the H14 "close on answer" equivalent)

H14's discipline: answering an approval closes its notification, so
a stale notification can't tap through to an already-answered page.
The fleet equivalent: **an acked alert never pages.**

- The intake's scan reads the *current* journal each pass and skips
  alerts with `acked: True`. No intake-side ack cache — G22's
  discipline transfers: the feed reads the current journal; so does
  the pager.
- **The race.** An ack can land after the intake enqueued a page but
  before the worker delivers it. The worker re-checks the alert's ack
  state at *claim time* (a cheap journal read, local) and silently
  drops entries for acked alerts. A drop is not a dead letter — it is
  logged quietly, not as an operator signal. The journal is the
  record; the page is advisory.
- Resolved alerts never *re*-page (dedup keys on `alert_id`; a
  resolved alert that re-fires is a new alert with a new id, and pages
  as one).
- The intake pages on **fire only**. It never pages on resolve: the
  page is the feed, not the pager (§7 composition). The G22 feed
  renders resolution; the push plane carries only "go look".

### 3.5 No escalation chain in S1

One page per `alert_id`, full stop. A rollback-failed box that sits
for six hours does not get re-paged by the intake. Whether a
long-lived firing alert deserves a second nudge (and at what
cadence, and who configures it) is an S2/S3 question — open
question Q2. S1 pins the simple, honest contract: the operator saw
the first page; the journal and the feed carry the rest.

## 4. Notification content: journal text only

The encrypted payload is assembled from journaled fields only —
`rule`, `box_id`(s), `subcomponent`, `to`, `detail`, `alert_id`,
`fired_at` — plus the intake's routing metadata (producer class,
which queue identity enqueued it). The fields are `_clean_text`-
stripped at synthesis (`fleet/events.py`), so a crafted audit line
can never forge or poison an alert row; the intake re-interprets
nothing.

- **No secrets, no model-authored free text.** H14's security notes
  transfer verbatim: the payload is never model-authored, never
  enriched with fetched context, never carrying key material. The
  alert `detail` may carry internal topology (box-local paths) — it
  is operator-only by definition (§5 of G22 pins exactly which fields
  stay operator-only); the operator opts into lock-screen exposure
  knowing the summary renders on the lock screen, the same informed
  trade H14 names for approval summaries.
- **Tap-through.** Tapping the notification opens the operator's
  fleet surface (the G21 console once it exists; until then the
  intake's subscribe/operator CLI names the journal path), which
  always shows current state — a page delivered seconds before an
  ack is a mild annoyance, never a wrong action (H14's stale-
  notification argument, transferred).

## 5. The operator subscription surface

H14's subscriptions are per-box, human, approval-flow. Operator push
needs a fleet-wide operator subscription store — a different surface
on the control-plane host, operator-owned, mode 0600:

- **Subscribe/unsubscribe validation** follows H14 exactly:
  https-only endpoints, 65-byte uncompressed `p256dh`, 16-byte
  `auth`, operator-authenticated, the same CSRF defenses as the
  approval endpoints, audit-logged (endpoint host only — the full URL
  carries an opaque push-service token).
- **The UI is G21's.** The operator console (G21 S2) owns the
  subscribe button — "notify this operator of fleet pages" — with
  the same iOS home-screen note H14 carries, since the constraint is
  the browser's, not the product's. **Until the console ships, the
  interim surface is an operator CLI** (`fleet alerts
  subscribe`-shaped; auth story lands with the console's per G21's
  "mutations stay CLI-only until S2" rule — subscribing is the one
  operator mutation S2 tolerates, owned by the console design).
- **Confirmd's page never hosts the operator toggle.** The operator
  is not a tenant on every box; bolting an operator subscription onto
  a per-box approval page would silently model the operator as a
  box-local human. Open question Q4 names the interim trade.

`--test-push` survives as `--test-page`: one real push through the
configured operator keys to every stored operator subscription,
reporting how many the push service accepted — the same supported
path as a real page, and the S2 acceptance drill.

## 6. S2 and S3 (sketched here, not designed)

**S2 — the enqueue path from the alert journal.** The intake observer
( tail-follow or periodic scan over `alerts.jsonl`, honoring the
bounded scan window the rules reason about) enqueues each
page-eligible, unacknowledged, not-yet-notified alert onto the
operator queue; the claim-time ack recheck (§3.4) and the
notified-log dedup (§3.2) are the exit criteria. `fleet events
watch`'s nonzero exit stays as the **cron fallback**, not the
primary — the issue's own words — so a push outage never degrades
the S1 transport: cron still catches what the plane misses, and the
dead-letter runbook stays the operator signal for a sick plane.

**S3 — the tenant push variant, gated, never before.** Tenant-visible
incidents (G22 S2b) get a tenant push variant only after G24's
tenant read path exists: per-tenant subscription scoping (H14 part
b's per-tenant work), curated summaries instead of raw `detail`,
box-id surrogates per G22 §6, and — per G22's Q2 — the signed feed
from G25 for tenant-visible rows, since a tenant disputing a page
needs a tamper-evident record, not the operator's word. **Gated on
G24 *and* C4** (the issue's own gate). This section names the
preconditions; it designs nothing.

## 7. Composition with the sibling designs

- **G17:** consumers read what the producers journaled. The intake
  reads `alerts.jsonl`; it never touches the evaluation path and
  changes no rule. Rule-3's tick churn (§3.3) is a producer-side
  fix owned by the arming design.
- **G18:** gate publishes and freeze flips are operator-initiated;
  they ride the event journal and the G22 feed, not the pager. A
  frozen fleet that also fires alerts pages on the alerts — the
  freeze explains the context, not the silence.
- **G21:** the S2 console owns the operator subscribe UI; the read
  API's field-equivalence contract is untouched. The console's auth
  story is the prerequisite the interim CLI honors, not a shortcut
  around.
- **G22:** the page is the feed, not the pager (§7 of the feed
  spec); a feed that goes un-read is a G23 gap, not a G22 bug. The
  ack→resolve lifecycle is inherited wholesale: ack suppresses the
  page, only journaled evidence resolves, and an acked-but-unresolved
  alert stays listed on the feed even though it pages exactly once.
- **G24/G25:** S3's preconditions, named not designed. No second
  tenant-field invention here; no second trust story for the feed.
- **G26:** the intake is not metering's source; G26 reads the event
  stream directly. No coupling.
- **H14:** the push plane gains a producer class (operator paging),
  not a confirmd patch. H14's payload discipline, fail-open posture,
  key storage, lock discipline, and access model all transfer.

## 8. Open questions

- **Q1 — Rule 3's episode key.** Who stabilizes the page-once-per-
  episode contract when G15 S2 arms the silent-wave rule: the
  arming design (stable `dedup_key` per silence episode in the rule)
  or intake-side coalescing? This spec's position: the producer owns
  its dedup_key stability; the intake must not paper over churn.
  Argue the other way in the arming design.
- **Q2 — Escalation.** Is one page per `alert_id` enough for a
  six-hour rollback-failed? A re-page/escalation chain (cadence,
  who configures, which rules) is an S2/S3 question; S1 pins no
  escalation. The feed carries the long tail.
- **Q3 — Worker sharing.** One worker process serving both the
  approval queue and the operator queue, or two? The code is
  parameterized by producer class either way; the S2 design picks
  the deployment shape. The constraint this spec pins: the queues
  never mix (separate stores, separate VAPID identities, separate
  notified logs).
- **Q4 — Interim subscription surface.** CLI-only until the G21
  console S2, or a minimal standalone operator page? The page would
  duplicate the console's auth work; the CLI keeps the one-mutation
  debt honest. Argue for the page in the S2 design.

## 9. Build slices (for the feature/distribution track, not this doc)

- **S1 — this spec.** Issue #797 stays open for S2/S3.
- **S2 — the enqueue path.** The intake observer over `alerts.jsonl`
  (bounded scan window), the parameterized producer class on the
  push worker, operator queue identity + VAPID keypair deployment,
  the claim-time ack recheck, `--test-page` drill, the `fleet
  events watch` exit-code cron fallback. Exit criteria: one page per
  `alert_id`; acked alerts never page, even mid-race; a push outage
  never degrades the S1 transport.
- **S3 — the tenant push variant.** Gated on G24's tenant read path
  and C4: per-tenant subscription scoping, curated summaries,
  box-id surrogates, the G25 signed feed for tenant-visible rows.
