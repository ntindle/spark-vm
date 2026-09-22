# Approvals-plane gap analysis: from gated action to human answer and back

**Status: analysis, not a commitment.** Code-state claims below were verified
against the repo tree at `5b8f773` (2026-09-21 ~16:24 CDT); issue/PR numbers
are GitHub references as of 2026-09-21 (not code-verifiable from the tree).
Honesty rules apply (`docs/POSITIONING.md`): this describes current
state and work to do, not promises. Claims stay on the self-hosted reality
until the hosted product exists.

**Non-overlap map (what this doc is not):**
- The pipeline stages (discover → signup → identity → provision → box →
  sentinel → push → app) are `docs/HOSTED_GAP_ANALYSIS.md`. This doc walks
  one plane inside the "box" stage: the full approvals path.
- The five day-one surfaces (browser, creds, jobs, approvals, push) are
  `docs/DAY_ONE_GAP_ANALYSIS.md`. Its approvals surface (§4) asked "can the
  Muse file a request, park, and get an answer" — this doc answers it
  mechanism by mechanism, against the code as it stands today.
- The command-level first-run script is `docs/FIRST_TEN_MINUTES_SPEC.md`
  (§6.6 names the client-visible pending signal this plane still lacks).
- Contributor-side gaps are `docs/OSS_CONTRIBUTOR_GAP_ANALYSIS.md`.

**The plane.** An agent's gated action travels: request → proxy refusal →
filing → pending queue → human answer UX → push summons → terminal decision
delivery → audit trail. Each leg: need, state, gaps.

Gap classes (shared with the day-one doc): `[BUILD]` exists nowhere, build
it; `[HOSTED]` the single-user OSS substrate needs a tenant dimension for
hosted; `[DESIGN]` design exists, code does not; `[POLICY]` needs an
operator (user) decision first.

## 1. Request → refusal: the agent sees a dead end, not a signal

**Need.** When the proxy refuses a swap, the agent must learn *what happened*
and *what to do*: which approval this refusal became, and where to park.

**State (5b8f773).** `proxy/swap_addon.py::_resolve`: on refusal the swap
returns `None` — the placeholder goes upstream untouched (→ remote auth
failure) — or, for egress refusals, the connection is killed. The approval
id minted moments later in `_file_approval` is never returned to the
refused request. Verified: the refusal path calls `_audit_refused` and
conditionally `_file_approval`, then returns `None`; no response channel
carries the id.

**Gaps.**
- `[BUILD]` **#133 / H18 — no machine-readable pending signal.** The proxy
  cannot tell the agent "your request became approval `<id>`, park here."
  `/api/pending` exists but is the *human-page* poller behind the owner
  auth gate — the missing leg is the agent-client one. Pre-launch
  (the first-run script's minute 5–8 depends on it).
- `[HOSTED]` The signal design must be tenant-aware: the pending id must
  be scoped to the requesting tenant's identity, which does not exist in
  the plane yet (H10).

## 2. Filing: the proxy files for the agent — flood-controlled

**Need.** A refused request must become exactly one human-actionable item,
no matter how chatty the agent is.

**State.** `proxy/swap_addon.py::_file_approval` (Findings 49/55/58):
swapd files a structured approval itself; the tuple (credential, host,
method, path prefix) comes from the real request — no model-authored text.
Filed only when the host is bound and the refusal is about method or path
(Finding 55: an unbound-host refusal must not produce an approval item).
Anti-flood: coalesced by (credential, host, method), capped at 5 pending
per credential, rate-limited to one filing per credential per 60 s.
Items carry a 1 h expiry (`expires`); the filing scan reaps expired items
as it goes (Finding 58). Inference proxy has no approvals directory at
all (Finding 60) — it reads grants, never files.

**Gaps.** No new gaps on this leg: the filing discipline is the plane's
strongest link. Two watch items:
- `[HOSTED]` the 5-per-cred cap and 60 s rate limit are single-owner
  tuned; a tenant with bursty-but-legitimate traffic shares the cap with
  nothing today — fine now, revisit when H10 adds tenants.
- The filing-time full-directory scan is O(pending); bounded today by the
  cap + 1 h expiry. Fine at this scale.

## 3. Pending: file-per-approval, and expiry is a silent third outcome

**Need.** Pending must be cheap to list, cheap to answer, and every item
must end in a *knowable* outcome: approved, denied, or expired — for both
the human and any agent parked on it.

**State.** `confirm/confirmd.py`: one JSON file per approval under
`pending/`; expired items are reaped when the list is rendered
(`load_pending`, Finding 58), at filing scan time, and on the GET/POST
expired paths (all audit-logged as `expired-reaped`; the *human* rendering
the page sees a 410 "expired and was removed"). The 2026-09-21 arch turn
(#196, merged) closed the daemon-lifetime growth issues: `consumed/`
answered history is now retention-bounded (`CONFIRM_CONSUMED_KEEP`,
default 1000, floored at the 100-item feed cap) and per-aid lock entries
are evicted when an item leaves pending (#192, #193 closed).

**Gaps.**
- `[BUILD]` **Expired is a silent third outcome for the agent.** The human
  gets a 410; the audit log gets `expired-reaped`; but no terminal record
  is left for an agent-side waiter to read — and none can be, because #133
  means the agent was never told the id in the first place. Even after
  #133 lands, expiry needs an explicit terminal outcome: a parked waiter
  must be able to distinguish *approved* / *denied* / *expired*, not just
  *gone*. New item **G1** (filed as a GitHub issue this turn).
- `[BUILD]` **#195 (open, severity:medium)** — `load_pending()`'s
  Finding-58 reap removes the pending file without the per-aid lock while
  `_answer_locked`'s consume path removes it after an exists-check: a
  reap landing in that window raises uncaught `FileNotFoundError` → 500
  on a legitimate in-flight answer. Fix direction in the issue (guard the
  consume-path remove like the two reap paths do; treat vanished as 404).
- `[BUILD]` **Poll cost is O(retention), not O(feed).** `_load_answered()`
  re-lists, re-parses, and re-sorts up to `CONFIRM_CONSUMED_KEEP` (1000)
  files on every `/api/answered` poll (5 s) and every `/answered` render —
  the retention bound fixed the *growth*, not the *per-poll parse cost*.
  New item **G2** (low; follow-up to #192/#196).

## 4. Human answer UX: the strongest leg

**Need.** The human must see what's pending, answer in two taps, and never
double-answer.

**State.** confirmd serves a tailnet-only page (Finding 47: refuses
self/foreign peers; Finding 48: per-item CSRF nonce ring + Sec-Fetch
checks). Shipped and verified: H1 auto-refreshing pending/answered pages
(#1), the 100-newest answered feed, per-approval in-process locks against
the double-answer race (#71), CSRF ring for multi-tab (#75). Finding 50:
the requester is the file's owner, never an argument; only `bdrive`/`swapd`
may file.

**Gaps.** No new gaps. The remaining UX work is the per-tenant attribution
(H10) — whose approval is whose — not the page itself.

## 5. Push summons: reaches the phone, but the send is fire-and-log

**Need.** A new approval must reach the human's phone even if they never
open the page; transient delivery failures must be retried, not lost.

**State.** H2 shipped: RFC 8030/8292/8291 VAPID push in
`confirm/push.py` (keygen, ES256 JWT, aes128gcm, subscription store,
notified log, sender), confirmd endpoints (`/sw.js`,
`/api/push/config`, subscribe/unsubscribe), push controls on the pending
and approval pages, and the swap_addon approval-created hook firing on a
daemon thread. Disabled unless the operator generated a keypair
(fail-closed; the page is unaffected).

**Gaps.**
- `[BUILD]` **H14a — standalone push service with enqueue/retry
  (unblocked).** Today `_push_notify` runs on a daemon thread and
  transient failures log only. A push that fails to send is a push that
  never happened — the approval sits pending until the human happens to
  open the page. The unblock pass cleared this for building (operator-
  generated VAPID keys, portable component, both-supported).
- `[HOSTED]` **H14b — per-tenant subscription scoping (gated on
  H10/H11).** Subscriptions live in one store under the approvals dir;
  nothing attributes a subscription to a tenant or an approval to a
  tenant's devices.

## 6. Terminal decision delivery: the missing return leg

**Need.** When the human answers, the parked agent must learn the outcome —
approved (retry now, the grant is minted), denied, or expired — without
polling a human-page endpoint it cannot authenticate to.

**State.** On approve, confirmd mints the grant via the single writer
*before* moving the item to `consumed/` (Findings 60/64); on deny, the
item moves to `consumed/` with `decision: denied`. Either way, the
decision lives in a file the agent cannot read and no signal goes back
to the original request. The agent's only recourse is to retry the
request and hope the grant is there now.

**Gaps.**
- `[BUILD]` **#133 / H18, restated from the agent's side.** The pending
  signal (id → refused request) and the terminal delivery (decision →
  parked waiter) are one build: a machine-readable channel the agent can
  park on. The first-run spec's §6.6 requires both the pending id on
  refusal *and* terminal decision delivery. Until it exists, the "park"
  step of the plane is a human fiction — the agent spins or gives up.
- `[HOSTED]` Delivery must be tenant-scoped and must not become a
  cross-tenant oracle: a waiter may learn the outcome of *its own*
  approval and nothing else. Design this with H10, not before it.

## 7. Multi-tenancy and scale-out: single-user assumptions, honestly marked

**Need.** The hosted plane serves N tenants on shared infrastructure
without cross-tenant reads, double-grants, or lost nonces.

**State.** One confirmd serves one tenant on one box; the code is honest
about it. Per-aid locks and the CSRF nonce ring are in-process state
(the comment says so: "a multi-replica confirmd would need the atomicity
story redone (flock on the item file)").

**Gaps.**
- `[HOSTED]` **H10 — confirmd multi-tenant approvals (open).**
  Per-tenant pending queues, tenant attribution on every approval and
  audit line, roles beyond the single `CONFIRM_OWNER`. Parallelizable
  with H11 on the provisional tailnet-identity attribution (the unblock
  pass's call); H11's audit validates or corrects the substrate.
- `[HOSTED]` **#194 (open, severity:medium)** — in-process atomicity has
  no multi-replica story. Child of the H10 axis: two confirmds against
  shared approval dirs could interleave the GET load→mint→write-back and
  POST check→mint→consume sequences (lost nonces, cross-process double
  entry into the grant path — the #71 race resurrected). Fix direction in
  the issue (flock on the item file as the atomicity domain); do with
  H10's tenant dimension, not before — no second replica exists until
  multi-tenancy lands.
- `[HOSTED]` Finding 60 (inference proxy files no approvals) is correct
  for single-user and needs a tenant story later: whose refusal becomes
  whose approval on a shared inference plane.

## 8. Audit trail → sentinel: the trail exists; the shipping does not

**Need.** Every refusal, filing, answer, and expiry leaves a durable,
attributable trail — and in the hosted product that trail ships to the
sentinel the human watches.

**State.** The trail exists: `refused=` lines for deliberately unswapped
placeholders (Finding 22), `approval-filed:<id>` on filing, answer/
expired-reaped/grant events in the confirmd audit log, CSRF violations
distinguished from stale nonces (#75/B1). swap.log itself is now
rotation-bounded with a disk-space guard (#202).

**Gaps.**
- `[DESIGN]` **H5 — hosted sentinel integration (open).** The audit log
  is written locally; the signed/sequenced audit-log shipping the signup
  doc promises is still a design, not code. The plane's trail is
  sentinel-ready (structured, attributable) — the shipping is the gap.
- `[HOSTED]` Tenant attribution on every audit line is H10's work; until
  then the trail answers "what happened" but not "for whom."

## New items this turn

| Item | Gap | Class |
|---|---|---|
| **G1** — expired approvals are a silent third outcome for the agent; expiry needs an explicit terminal record distinguishable from approved/denied (pairs with #133's pending signal) | §3 | BUILD (+HOSTED tenant scope) |
| **G2** — `_load_answered()` re-parses up to `CONFIRM_CONSUMED_KEEP` files on every 5 s poll; per-poll cost is O(retention), not O(feed) | §3 | BUILD (low) |

Both filed as GitHub issues this turn; the backlog carries the same items.

## What's closed since the last plane-level looks

- #192/#193 → #196 (consumed retention + aid-lock eviction, merged).
- swap.log rotation + disk-space guard (#202, merged) — the audit trail
  can no longer be killed by its own growth.
- The day-one doc's "no bdrive code" line is stale: H17 slice 1 shipped
  the `bdrive` action protocol (83 hermetic tests, #166 merged) — the
  plane's future filing path (browser-driven requests) has its hands.

## Honesty check

This plane is the most build-complete part of the hosted vision: filing,
pending, human answer, push, and audit all exist as real code with real
tests. The honest gap is the **return leg**: the plane is a dead end for
the agent. Refusal produces no signal, answers produce no delivery, and
expiry produces no record the waiter can read. #133/H18 names the build;
G1 names its expiry-shaped sibling. Everything else is the tenant
dimension (H10/H11) or retry plumbing (H14a).
