# First-approval summons — design (G4)

**Status:** design; not implemented. Closes the design half of backlog item
G4 ("first-approval summons channel — the chicken-and-egg").

**The gap:** three layers agree the first approval must actively reach the
human, and none of them can send it. `FIRST_TEN_MINUTES_SPEC.md` §4 makes
email via the operational AgentMail identity the default summons channel on
filing, retiring when H14 ships. `TEN_MINUTE_SPEC_CONFORMANCE_GAP_2026-09-22.md`
§4 ("Partial, with a new finding") verifies: no email sender is wired into
`_file_approval` (`proxy/swap_addon.py`), and the shipped H14 component
(`confirm/push.py`, VAPID Web Push) requires a browser subscription created
by a human who has *opened the page* — which, in the hosted first run, only
happens *after* the first summons arrives. Push can't reach a human who
hasn't subscribed; email was never built. The first approval's summons has
no channel at all.

**Scope discipline:** this doc specifies the control plane's summons surface
only — who observes the filing event, where the credential lives, what the
email contains, when the reminder fires, and when email retires. It does not
redesign confirmd (H10), the filing record (`_file_approval`'s shape is taken
as-is), the tenant-status endpoint (G3 — the reader of the carrier this doc
writes to), or push (H14). Those components are *producers* or *consumers* of
this contract, not its subject.

## 1. The architecture decision: observe, don't extend the swap path

The tenant box's swap path must never send email and must never hold the
AgentMail credential. Two reasons, both load-bearing:

1. **Trust boundary.** The tenant box is tenant-adjacent compute (per H11's
   audit: tenant holds root-equivalent inside the guest; the operator owns
   only the layer below). The operational AgentMail identity is an
   operator-plane credential. Installing it on the tenant box would put a
   shared operator secret inside every tenant's reach — the same class of
   mistake as the IMDSv1 host-wide grants H11 flagged (§3, swap-proxy
   trust boundary).
2. **Blast radius.** The filing path (`_file_approval`) runs inside the
   proxy's hot path on the box. Network calls to a mail API from there
   would couple approval latency to mail-delivery latency. The existing
   push integration already follows the right pattern: `_file_approval`
   enqueues on a daemon thread to a durable journal
   (`$CONFIRM_DIR/push-queue.jsonl`), never on the hot path, and a
   standalone worker delivers with retry. The summons follows the same
   pattern — on the box it is one locked append, nothing more.

So the design has two halves:

- **Box side (S1):** `_file_approval` appends a filing event to a durable
  local outbox journal (`$APPROVALS_DIR/summons-outbox.jsonl`) on a daemon
  thread, exactly like the push enqueue. Event payload: `aid`,
  `filed_at`, `expires`, the plain-language action summary (credential
  name + host + method — the same text the page already shows; never
  model-authored free text, per the finding-49 discipline), and the
  tenant identity. No secrets, no credential values, no request bodies.
- **Control-plane side (S2):** an observer on the operator plane reads the
  outbox (the H4 relay is the natural carrier for this read — the same
  tailnet channel that already lets the control plane reach the box), and
  sends the email via the operational AgentMail identity. The AgentMail
  API key is installed only on the operator plane via `cred set` and
  referenced in configs as the `hsurr:agentmail` placeholder (R2 rule) —
  it is never written into the repo, the journal, or the box.

Fail-open throughout: observer, network, or API failure never loses the
filed approval and never blocks the swap path. The journal is the durable
record; the observer retries with backoff; a dead-letter journal holds
events that exhausted retries. A summons that never sends is an
observability event (see §6), not a filing failure.

## 2. What the email contains

Content is constrained, not authored. The spec's §4 fixes the channel's
copy, and this doc pins the assembly rules:

- **Deep link:** the summons body's approval URL is built from the
  `approvals_url` carrier in the tenant record (G3's scope —
  `TENANT_STATUS_ENDPOINT.md` §3) plus the approval id:
  `<approvals_url>/approval/<aid>`. **G8's open question** (who writes
  `approvals_url`, and re-entry rotation) is the one sequencing dependency:
  if the tenant record has no `approvals_url` at summons time, the email
  may not fabricate one — it sends with the approvals-page base URL from
  operator config and notes the carrier as unresolved. G8's resolution
  removes the fallback.
- **Plain-language action:** the filing record's tuple, rendered as the
  page renders it ("your Muse asked to use `<credential>` for
  `<host>`"). No model-authored text enters the email (finding-49
  discipline, same as push.py's payload).
- **Two-tap instruction:** the spec's exact sentence — "When the email
  arrives, open it and tap Approve — two taps, and your Muse continues."
  The human-facing copy lines in §4 (provisioning, the one required
  action, channel honesty, waiting) are used verbatim — the doc quotes
  the spec, not a paraphrase.
- **Privacy floor:** the email carries only the approval summary, the
  deep link, and the instruction. No credential values, no request
  payloads, no agent conversation content.

## 3. Timing: first filing, one reminder, then expiry

Per spec §4:

- **Trigger:** the first approval request files. "First" is per tenant,
  per onboarding arc — the observer tracks a `first_summons_sent` flag
  in the tenant record so a box restart or journal replay cannot re-summon
  (the journal is at-least-once; the flag makes the send idempotent).
- **Reminder:** one re-send at T+TTL/2 if the approval is still pending.
  Approval TTL is 1 hour (`timedelta(hours=1)` in `_file_approval`), so
  the reminder fires at +30 minutes. Before re-sending, the observer
  re-reads the filing state — an approval that expired or was answered
  gets no reminder (cf. G1 / #213: expiry is a silent third outcome on
  the agent side; the summons must not resurrect it).
- **After expiry:** per spec §8 the unanswered request expires into
  `human-drop-off`. The summons does not chase the drop-off — the
  tenant-status code (`waiting-on-approval` → `human-drop-off`) is the
  re-entry path, not more email.

## 4. Retirement when H14 ships

The spec says the email summons retires when the push service (H14)
ships. The retirement rule, made precise:

- Email remains the default for a tenant's **first** filing until the
  control plane has recorded at least one confirmed push delivery for
  that tenant (subscription created *and* a push acknowledged). Only
  then does push become the primary summons channel for that tenant.
- This is a bootstrap exception, not a contradiction: H14's push can
  only summon a human who has subscribed, and subscription still
  happens after the first summons in the hosted first run. Email is the
  bootstrap channel by necessity; H14 retires it as the *steady-state*
  channel.
- Once retired for a tenant, email becomes the fallback for push
  delivery failures (dead-letter push → email), not the primary. The
  signup page must not imply push exists until H14 ships (spec §4's
  channel-honesty copy stands).

## 5. Self-hosted: portable, off by default

The both-supported default (user-set 2026-09-18) applies: the summons
module is a portable component — the journal emission (S1) ships in the
open-source tree, and the sender driver (S2) is runnable by any operator.
But email via the operational AgentMail identity is meaningless without
an operational identity, so the sender is **disabled unless a summons
channel is configured** — same shape as push.py's "disabled unless
`CONFIRM_VAPID_KEYS` names a readable keypair" gate. Single-owner
deployments (the owner is the operator; the approval page is local)
need no summons channel at all: the box-side journal stays dormant and
costs one locked append per filing at most. Config (env):

- `CONFIRM_SUMMONS_DRIVER` — `agentmail` (default: unset = disabled)
- `CONFIRM_SUMMONS_INBOX` — the operational inbox identity
  (default `spark-agent@agentmail.to`)
- `CONFIRM_SUMMONS_API_KEY` — referenced as `hsurr:agentmail`, installed
  via `cred set` on the operator plane only
- `CONFIRM_SUMMONS_BASE_URL` — approvals-page base URL fallback (used
  only while G8's carrier is unresolved — §2)

## 6. Observability: the funnel must see the summons

A summons that sends into the void is invisible to the funnel. The
observer emits waitlist/funnel events (the `WAITLIST_OPERATIONS.md`
event vocabulary):

- `summons_sent` (aid, channel, tenant) — the trigger fired.
- `summons_reminder_sent` — the +30m reminder fired.
- `summons_failed` (aid, reason, dead-lettered?) — fail-open, but
  visible. A tenant whose first summons dead-letters should surface in
  the operator dashboard: the human is waiting on a channel that is
  broken, and the funnel's "waiting on your approval" stage copy is a
  lie until it's fixed.
- `summons_skipped_expired` — the reminder was suppressed because the
  approval expired (G1's silent outcome, made explicit here for the
  funnel's sake).

## 7. Build slices (for the `feature`/provisioning track)

- **S1 — box-side journal:** `_file_approval` appends the filing event
  to `$APPROVALS_DIR/summons-outbox.jsonl` on a daemon thread (mirrors
  the push enqueue; unit-tested: journal row shape, hot-path
  non-blocking, at-least-once tolerated). No sender, no network.
- **S2 — control-plane observer + AgentMail driver:** the relay (H4)
  reads the journal; the driver sends via AgentMail's REST API
  (`POST /v0/inboxes/{inbox}/messages/send`) using the `hsurr:agentmail`
  placeholder installed via `cred set` on the operator plane only;
  reminder scheduler (+30m, state re-check before re-send); idempotency
  via the tenant record's `first_summons_sent` flag; dead-letter journal.
  Sequencing: needs G8's `approvals_url` write-ownership resolved for
  the deep link (fallback licensed in §2 until then).
- **S3 — retirement + funnel telemetry:** the H14 bootstrap rule (§4),
  the §6 funnel events, and the operator-dashboard surfacing of
  `summons_failed`. Sequencing: needs H14's confirmed-delivery signal.

## 8. Open questions (carried, not decided here)

- **G8 (dependency):** which signup-flow step owns the `approvals_url`
  write, and re-entry rotation. Blocks the deep link's carrier, not the
  design.
- **Magic-link email already exists?** The signup flow already sends
  magic-link emails (`HOSTED_SIGNUP_ONBOARDING.md` §5) — the summons
  should reuse the same operator mail path if one exists rather than
  standing up a second sender. The S2 implementer verifies this against
  the signup implementation before writing a new driver.
- **Per-tenant vs per-box:** G7's multi-box-tenant question applies to
  the summons too — a tenant with two boxes has two onboarding arcs,
  and "first filing" is per arc. S2 reads G7's resolution when it lands.
