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
   proxy on the box. Network calls to a mail API from there would couple
   approval latency to mail-delivery latency. The existing push
   integration already separates concerns: `_file_approval` enqueues on
   a daemon thread to a durable journal (`$CONFIRM_DIR/push-queue.jsonl`),
   and a standalone worker delivers with retry. The summons follows the
   same separation — the box records a journal row, the operator plane
   delivers — with one deliberate divergence: the append happens inline
   next to the filing write (same durability, not a weaker one), because
   unlike push's poisoned-queue-file concern there is no reason to defer
   it; see the S1 detail below.

So the design has two halves:

- **Box side (S1):** `_file_approval` appends a filing event to a durable
  local journal (`$APPROVALS_DIR/summons-outbox.jsonl`) **inline, adjacent
  to the `os.replace` that files the pending record** — inside the same
  try block, guarded by the existing `except OSError` (an append failure
  demotes the client to no-signal, the same failure class as the filing's
  own writes). The filing path is already synchronous on the hot path
  (makedirs, a full `listdir` scan, `os.replace`), so the "hot path"
  argument against one locked append collapses — the append shares the
  filing's durability rather than a weaker one. The residual loss window
  is a process crash between the two writes *for a record still
  pending*; a box-side reconciliation sweep (S1-owned cadence,
  minutes-scale — see §7) diffs `pending/` against the journal and
  re-ships anything the inline append missed. Event payload: `aid`,
  `filed_at`, `expires`, the plain-language action summary (credential
  name + host + method — the same text the page already shows; never
  model-authored free text, per the finding-49 discipline), and a tenant
  field carried as an **unverified hint** (see identity, below).
  No secrets, no credential values, no request bodies.
- **Control-plane side (S2):** the box *ships* filing events to the
  control plane over `HOSTED_SIGNUP_ONBOARDING.md` §10's channel — signed,
  append-only batches with per-VM sequence numbers, over a mutually
  authenticated channel (per-VM client cert issued at provision time,
  pinned to the tenant). This is a **box→plane push, never a
  control-plane pull**: §6 pins `spec.network = {public_ingress: false}`
  and forbids inbound paths to the VM, so there is no observer that
  "reads the outbox" from outside. The summons events ride the same
  audit-shipping batches (a dedicated event stream over the same channel
  is S2's call). **This channel is unbuilt** — §10 is a design, not a
  deployment — so it is an explicit S2 sequencing dependency, named
  below. The AgentMail send itself happens on the operator plane with
  the API key installed via `cred set` and referenced in configs as the
  `hsurr:agentmail` placeholder (R2 rule) — the key is never written
  into the repo, the journal, or the box.

**Identity:** the observer keys the `first_summons_sent` flag,
the pending-state mirror, and the recipient lookup off the
**transport-authenticated box→tenant binding** (the per-VM client cert),
treating the journal's tenant field as an unverified hint. A
compromised box can suppress its summons events (per §10, suppression
is detectable — a gap in the sequence numbers is the signal — but the
email then never goes out); it cannot forge another tenant's events
undetectably. Cross-tenant forgery degrades to self-spam or a re-check
miss, never a misdirected summons.

**Recipient:** the recipient is the magic-link account email collected
at signup (funnel stage 2, `FIRST_RUN_ACTIVATION.md` §5), read from the
signup account/identity records — owner: the H9 identity service (the
account-creation UI itself is H15-era). The control plane must be able
to read that address at summons time — whether it is carried in the G3
tenant record (a record-extension question, named in S2's sequencing)
or read from the identity records directly is S2's call; either way the
field is named here so the dependency is visible.

Fail-open throughout: observer, network, or API failure never loses the
filed approval and never blocks the swap path. The observer retries with
backoff; a dead-letter journal holds events that exhausted retries. A
summons that never sends for *send-side* reasons is an observability
event (see §6); a summons suppressed *box-side* shows up as a §10
sequence gap, surfaced by the sentinel-side observer, not as
`summons_failed`. Neither failure mode is silent, and neither touches
the filing.

## 2. What the email contains

Content is constrained, not authored. The spec's §4 fixes the channel's
copy, and this doc pins the assembly rules:

- **Deep link:** the summons body's approval URL is built from the
  `approvals_url` carrier in the tenant record (G3's scope —
  `TENANT_STATUS_ENDPOINT.md` §3) plus the approval id:
  `<approvals_url>/approval/<aid>`. **G8's open question** (who writes
  `approvals_url`, and re-entry rotation) is the one sequencing dependency:
  if the tenant record has no `approvals_url` at summons time, the email
  **omits the deep link entirely** — no fabrication. The human was handed
  the approvals-page URL at signup stage 2 (spec §4 item 1) and already
  holds it, so the email points there with the copy "open your approvals
  page and tap the pending approval." `<base>/approval/<aid>` is not a
  licensed fallback: the carrier contract shows `approvals_url` as
  tenant-scoped, and a probably-broken link trains humans that summons
  links are broken. G8's resolution removes the fallback.
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
  (the journal plus the S1 reconciliation sweep is at-least-once; the flag makes the send idempotent).
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
  control plane has recorded a **push-service-accepted delivery** (201)
  for that tenant. A 410 (dead subscription) does *not* retire email —
  it falls back to email and marks the subscription for re-registration.
  "Push acknowledged" is not a device-ack (push services return 201 from
  the push network, never a human-saw-it); the retirement criterion is
  the service accept, not a human read receipt.
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
But email via an operational AgentMail identity is meaningless without
one, so the sender is **disabled unless a summons channel is configured**
— same shape as push.py's "disabled unless `CONFIRM_VAPID_KEYS` names a
readable keypair" gate. Single-owner deployments (the owner is the
operator; the approval page is local) need no summons channel at all: the
box-side emission still happens (one locked append per filing — the
sender is dormant, not the journal), and costs nothing observable.

For the **hosted** deployment, an unconfigured summons channel is a
**provisioning gate, fail-closed**: a hosted deployment that ships
without one silently degrades the first run to `human-drop-off` while
the funnel copy promises "waiting on your approval." Provisioning must
refuse to complete until a summons channel is configured.

Config (env):

- `CONFIRM_SUMMONS_DRIVER` — `agentmail` (default: unset = disabled)
- `CONFIRM_SUMMONS_INBOX` — the operational inbox identity. **Unset and
  required; the operator provisions a dedicated inbox** (the AgentMail
  free tier allows 3 inboxes — waitlist, spark-agent, summons). No
  default is blessed here: the product must not hard-code an
  operator's identity.
- `CONFIRM_SUMMONS_API_KEY` — referenced as `hsurr:agentmail`, installed
  via `cred set` on the operator plane only

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
  lie until it's fixed. Covers send-side failures; a box-side-suppressed
  summons shows up as a §10 sequence gap instead (see §1), surfaced by
  the sentinel-side observer.
- `summons_skipped_expired` — the reminder was suppressed because the
  approval expired (G1's silent outcome, made explicit here for the
  funnel's sake).

## 7. Build slices (for the `feature`/provisioning track)

- **S1 — box-side journal:** `_file_approval` appends the filing event
  to `$APPROVALS_DIR/summons-outbox.jsonl` inline, adjacent to the
  `os.replace` — inside the same try block, guarded by the existing
  `except OSError` (an append failure demotes the client to no-signal,
  the same failure class as the filing's own writes, which already
  return `[]` on `OSError`). The append shares the filing's durability
  rather than a weaker one. A box-side reconciliation sweep (S1-owned
  cadence, minutes-scale) diffs `pending/` against the journal and
  re-ships anything the inline append missed. The sweep only recovers
  misses for records still in `pending/` at sweep time: a record
  answered or expiry-reaped before the sweep (`confirmd.py` consumes the
  pending file on both) is moot — the human already engaged, or the
  request expired into `human-drop-off`. No stray summons results: the
  observer's pending-state mirror is fed by the box's
  answered/expired lifecycle events over the same channel, so a
  re-shipped event for an already-answered aid meets an answered
  mirror entry and the summons (and its reminder) are suppressed. The
  residual loss window is therefore a process crash between the two
  writes *for a record still pending* — stated, not hand-waved. Unit-tested: journal row shape, adjacency,
  the sweep's diff. Naming note: `$APPROVALS_DIR` is
  `_file_approval`'s tree (`SWAP_APPROVALS_DIR`, default
  `/home/swapd/approvals`); push.py's `CONFIRM_DIR` defaults to the same
  path — the journal lives in the approvals tree either way.
- **S2 — box→plane event stream + AgentMail driver:** filing and
  lifecycle events (filed/answered/expired) ship over §10's
  mutually-authenticated channel; the control plane's driver sends via
  AgentMail's REST API (`POST /v0/inboxes/{inbox}/messages/send`) using
  the `hsurr:agentmail` placeholder installed via `cred set` on the
  operator plane only; reminder scheduler (+30m, state re-check against
  the observer's pending-state mirror — the mirror is fed by the box's
  answered/expired lifecycle events over the same channel, keyed off
  the transport-authenticated box→tenant binding); idempotency via the
  tenant record's `first_summons_sent` flag; dead-letter journal.
  **Sequencing:** (a) the §10 event channel is unbuilt — say so, and
  verify its batch-write/ship capability at implementation; (b) G3's S1
  (the tenant-record store, carrying `first_summons_sent`,
  `approvals_url`, and possibly the recipient) is unbuilt; (c) G8's
  `approvals_url` write-ownership — until it resolves, the email omits
  the deep link per §2; (d) the recipient's read path from the H9
  identity records (record-extension question, §1).
- **S3 — retirement + funnel telemetry:** the §4 retirement rule (201
  accepted = retired; 410 = email fallback + re-registration), the §6
  funnel events, and the operator-dashboard surfacing of
  `summons_failed`. Sequencing: needs H14's push-accept signal.

## 8. Open questions (carried, not decided here)

- **G8 (dependency):** which signup-flow step owns the `approvals_url`
  write, and re-entry rotation. Blocks the deep link's carrier, not the
  design.
- **Operator mail path exists — reuse decision, not greenfield.**
  `site/waitlistd.py` already spools outbound transactional mail
  (`_spool_patha_email`: clarification replies, forget confirmations,
  confirms/reminders/invites, with per-address send caps) under the
  operator identity. S2 decides reuse vs. a second sender; either way,
  verify the credential's *placement* (operator plane only,
  `hsurr:agentmail` via `cred set`), not just the API path.
- **Dedicated vs shared inbox:** the free tier allows 3 inboxes
  (waitlist, spark-agent, +1). Whether the summons gets a dedicated
  inbox or reuses an existing operational one is an operator decision —
  S2 records the choice; §5 licenses only that no default is blessed
  in the design.
- **Per-tenant vs per-box:** G7's multi-box-tenant question applies to
  the summons too — a tenant with two boxes has two onboarding arcs,
  and "first filing" is per arc. S2 reads G7's resolution when it lands.
