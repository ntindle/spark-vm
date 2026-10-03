# Waitlist operations spec

**Status: design spec, not the implementation.** This is the operations
manual for the hosted waitlist — the funnel instrument
`docs/LANDING_PAGE_COPY.md` §4 sketches in bullets. It specifies exactly
what happens from "Join the waitlist" to "your box is ready," so the page
(§5's checklist: *"the waitlist capture + confirm flow (§4) is actually
live before the page ships — the page must never typeset atop a dead
form"*) never typeset atop a dead form. Copy blocks are **DRAFTS**, not
published copy.

**Dependency:** every `docs/LANDING_PAGE_COPY.md` citation below refers to
main (merged as PR #61, `fc948a6`; section numbers re-verified against main
2026-09-19). The HTTP method shape of the confirm flow (§4) is decided by
open PR #99 (`docs/FUNNEL_MEASUREMENT.md` §4), which supersedes this doc's
GET language — GET renders the confirm page, POST confirms; merge order is
this → #99.

**Non-overlap map (what this doc is not):**
- The page strategy (conversion job, section order, copy blocks,
  measurement definitions) is `docs/LANDING_PAGE_COPY.md` — this doc
  *implements* its §4, never restates it.
- The funnel this feeds is `docs/FIRST_RUN_ACTIVATION.md` §2 (stage 1
  Discovery → stage 2 Signup). The waitlist is the pre-launch stand-in
  for "starts identity linking."
- Identity linking itself (ed25519 + human fingerprint approval,
  re-link) is the **H3** hosted signup/onboarding design
  (`docs/HOSTED_SIGNUP_ONBOARDING.md` §4) — this doc pre-collects only
  what signup re-verifies.
- Pricing is `docs/PRICING_THINKING.md` — this doc prints no numbers;
  the invite email fills them at send time.
- Voice and safe one-liners are `docs/POSITIONING.md` — the drafts below
  stay inside its anti-claims.
- **H15** is the signup web UI + human dashboard build (from
  `docs/HOSTED_GAP_ANALYSIS.md`); the waitlist retires into it (§8).

## 1. The gap this closes

`LANDING_PAGE_COPY.md` §4 describes one submission path ("the Muse submits
the waitlist request … via AgentMail") but its abuse section prescribes
form defenses ("honeypot + time-trap on the form"). A honeypot does nothing
for an email submission. There are really **two** submission paths with
**different** abuse models, and the spec has to treat them separately —
otherwise the first spam wave finds the seam.

There is also a sequencing trap: the page's only metric (§6) is the
confirmed rate, but "confirmed" is only meaningful if confirmation is a
real gate with a real token, a real reminder cadence, and a real drop
policy. This doc makes each of those concrete.

## 2. Submission paths

### Path A — Muse via email (primary)

The Muse sends an email to the waitlist inbox. Rationale
(`LANDING_PAGE_COPY.md` §4): the Muse is the converting reader; it can act
under its own identity today because AgentMail is operational
(`spark-agent@agentmail.to`, `custom.agentmail` connector, inbound verified
2026-09-18). The Muse learns the inbox address from the landing page's
waitlist copy block (the page prints it alongside the form CTA — no
separate discovery step).

- **To:** a dedicated waitlist inbox, operator-provisioned (a second inbox
  on the existing AgentMail free tier, which allows 3 inboxes).
- **Required:** exactly one owner email address — the human who will
  approve spend and receive the invite. The funnel confirms the right
  human, not the Muse.
- **Optional:** the Muse's ed25519 public key (single line,
  `ssh-ed25519 AAAA…`). Pre-registration only: at signup the H3 flow still
  requires the human to approve the fingerprint; if it matches the
  waitlisted key the UI may show "matches the key your agent submitted" as
  a continuity hint. The waitlist never trusts the key.
- **Optional:** one line on what the Muse wants a box for (stored verbatim,
  max 280 chars; invite-wave context only, never published).
- **Parsing:** the parser extracts email addresses from the body, then
  applies the exclusion list *before* counting: the From address, the
  waitlist inbox's own address, and any `@agentmail.to` address are never
  candidates (signature lines, CCs, and quoted threads routinely contain
  ≥2 addresses — counting them would bounce the primary converting path
  into the ask-again loop). An explicit labeled line `Owner: addr@…`
  overrides extraction when present. Exactly one candidate → proceed;
  zero or ≥2 → the clarification reply below.
- **Clarification reply (DRAFT)** — sent only when the inbound message
  passes SPF/DKIM/DMARC alignment on the From domain (the auth result is
  recorded in the store). Unauthenticated mail is silently dropped into
  an operator triage queue — no outbound reply, ever, so the parser can
  never become a backscatter reflector (§6):

> We couldn't tell which address is the owner. Please reply with exactly
> one owner email address — the human who'll approve spend and receive
> the invite.

### Path B — human via the page form (secondary)

The human buyer clicks "Join the waitlist" and fills the form themselves.

- **Fields:** owner email (required), Muse contact email (optional —
  "where should we reach your agent"), nothing else.
- **Defenses:** honeypot + time-trap per `LANDING_PAGE_COPY.md` §4,
  per-IP rate limit (§6).

Both paths converge on the same confirmation flow (§4) and the same store
(§5). The form path exists because the buyer sometimes converts without
the Muse in the loop; the email path exists because usually the Muse
converts first.

## 3. What the waitlist verifies (and what it doesn't)

**Verified:** that the owner's email address is real and a human there is
reachable — by double opt-in (§4). This is the launch's actual gating
factor: invites are worthless to dead addresses.

**Not verified:** that the submitter is really a Muse, that the From
address belongs to the Muse, that the use-case line is true. The confirm
gate raises the *cost* of spraying — each entry needs a human click from a
reachable inbox — but it does not prevent one human holding many confirmed
entries (plus-tags, multiple inboxes; §6 normalizes the cheap tricks).
Sybil resistance comes from the *confirm gate plus launch capacity*, not
from sender attestation:

- An unconfirmed entry costs one store row and receives nothing — no
  invite, no pricing, no signup link. Flooding the inbox manufactures
  rows, not invites.
- The expensive actions (invite with pricing, signup) happen only after a
  human clicked a signed link from their own inbox.
- One pending entry per normalized owner email (§6): re-submits refresh
  `submitted_at`, never duplicate.
- Residual risk is bounded by the 14-day invite expiry + roll-over (§7):
  even a confirmed farm can't hold launch inventory hostage.

This is stated plainly in the confirm email's honesty line (§4): the
waitlist confirms reachability, not identity. Identity is H3's job.

## 4. Confirmation flow

Double opt-in. Every transactional email in this flow is rate-limited (max
3 sends per address per 24h, counting confirm + reminder + clarification
replies + re-sends together) and follows the rate-limited,
prominent-action pattern `LANDING_PAGE_COPY.md` §4 requires for the
re-link email UX, so the two don't drift. (The H3 doc itself specifies
re-link email only as an alternative approval channel; the
prominent-fingerprint + rate-limits requirement is recorded in the BACKLOG
H3 follow-up.)

**Token:** HMAC-signed (operator key, never in the repo), payload
`{owner_email, entry_id, issued_at}`, single-use, 14-day expiry (7 days to
the reminder + 7 days grace, then the entry drops per §5 retention).
Confirmation is a GET on a signed link — no account, no password.
*Note: the HTTP method shape is decided by open PR #99
(`docs/FUNNEL_MEASUREMENT.md` §4), which supersedes this section's GET
language — GET renders the confirm page, POST confirms.*
Re-clicking a consumed token renders "you're already confirmed," not an
error. Re-submitting while pending re-sends the confirm email with a
fresh token (counts toward the 3/24h limit).

**Confirm email (DRAFT)** — opener split by submission path:

Path A (Muse submitted):

> Subject: Confirm your spark-vm waitlist spot
>
> Your agent asked to join the spark-vm hosted waitlist with this address
> as the owner contact.
>
> [ Confirm this address ]
>
> What this means: we'll email you when hosted boxes open up — with real
> pricing before we ask for anything else.
>
> No card is required for the waitlist, and this confirmation doesn't
> commit you to anything.
>
> What this doesn't mean: this confirms we can reach you. It doesn't
> verify your agent's identity — linking your agent's identity happens
> when you claim your box.
>
> Didn't ask for this? Ignore this email — unconfirmed addresses are
> dropped automatically.

Path B (human submitted): same body, opener replaced with "You joined the
spark-vm hosted waitlist — one click confirms this address."

**Reminder (DRAFT):** one reminder at +7 days, same link (fresh token if
the old one is within 7 days of expiry). The reminder carries the queue
position (§7) — the nudge is the highest-leverage email in the funnel, so
it gets the full draft. Opener split by path like the confirm email —
Path A: "Your agent put this address on the spark-vm hosted waitlist.";
Path B: "You asked to join the spark-vm hosted waitlist with this
address.":

> Subject: Reminder: your spark-vm waitlist spot is waiting on one click
>
> You asked to join the spark-vm hosted waitlist with this address.
>
> [ Confirm this address ]
>
> You're #N in line — we don't estimate dates. Confirm it so we can email
> you when hosted boxes open up. No card, no commitment.
>
> This is the last reminder; unconfirmed spots are dropped automatically.

**Drop:** unconfirmed 14 days after submission → status `dropped`, row
deleted after 30 days (§5). No third email — the reminder *is* the last
touch.

*Compliance:* no launch date; no pricing numbers; "no card required for
the waitlist" is a waitlist promise, not a trial promise (trial terms TBD,
Billing decision); the "doesn't verify identity" line is the §3 honesty
rule in user-facing form.

## 5. Data model, privacy, retention

Operator-side store only — never the repo, never a gist, never a log the
loop can see. Minimal fields:

| field | notes |
|---|---|
| `owner_email` | the confirmed human; the only required field (normalized: lowercase, plus-tag stripped — §6) |
| `muse_contact` | From address (path A) or the optional form field (path B); a handle, not an identity |
| `muse_pubkey` | optional ed25519, pre-registration hint only (§2) |
| `use_case` | optional, ≤280 chars, verbatim |
| `source` | `email` \| `form` |
| `inbound_auth` | SPF/DKIM/DMARC result for path A (gates the clarification reply) |
| `submitted_at`, `confirmed_at` | |
| `status` | `pending` → `confirmed` → `invited` → (`signed_up` \| `expired`); `dropped` terminal for unconfirmed |
| `invite_wave` | set when invited |

**Privacy posture:** collect nothing else — no names, no companies, no
tracking pixels in transactional email (the trust story is the brand;
`LANDING_PAGE_COPY.md` §7). Owner emails are stored encrypted at rest
(operator's call on mechanism; the requirement is the property).
Delete-on-request: the honored path is the signed one-click forget link
in every email footer. A reply saying "forget me" is *not* honored on its
own (Reply From is forgeable — that's a deletion oracle): it triggers a
confirmation email containing the signed forget link, and the row is
deleted only after the link is clicked (proving inbox access), within 7
days, with a confirmation sent.

**Deletion policy — what "forget" erases (#400):** a honored forget makes
the address unrecoverable from the live data stores the daemon manages,
not just the row store. (Backups are outside this guarantee — see
**Backups** below.) On `POST /waitlist/forget`, after the row leaves
`rows.jsonl` via the atomic rewrite, the daemon scrubs, under the same
locks: (1) `patha_events.jsonl` — every ledger line keyed by the address
is dropped (atomic rewrite; the address's rate-limit history dies with
it, so a re-signup starts with fresh caps — that is the honest
post-erasure semantic); (2) `triage/*.eml` — any triage file holding the
address is deleted (this is what removes the triaged "forget me" reply
with no matching row); (3) `rows.jsonl.skipped.*.jsonl` quarantine
sidecars — quarantined lines holding the address are filtered out
(atomically; empty sidecars removed); (4) `spool/` — any *pending* spool
doc addressed to the owner is deleted before the deletion confirmation
is queued, so the confirmation is the last mail ever sent to that
address. Funnel events carry only the pseudonymous `entry_id`, never
the address — nothing to scrub. `consumed_tokens.txt` holds HMAC tokens,
not PII.

**Matching scope (honest residual):** the triage/sidecar scrubs match the
canonical address (lowercased, plus-tag-stripped — the form every writer
records) case-insensitively, *plus* plus-tagged variants
(`local+tag@domain`), because raw inbound mail carries the
un-normalized From and the triaged "forget me" reply is usually
plus-tagged or cased differently. Raw forms a byte scan cannot
attribute — display names without the address, encoded-word splits
across line boundaries — are missed by the targeted scrub: for triage
they are bounded by the 48h retention sweep; for sidecars they are
caught only opportunistically at the operator's hand-review.

**Crash residual and recovery:** a kill between the row commit and the
scrub leaves the row deleted (fail-safe) with auxiliary copies behind.
Each half has its own bound: triage by the 48h sweep, the ledger by its
own 48h prune-on-append, spool by drain latency, sidecars by the
operator's hand-review only. Detection: the row is gone from
`rows.jsonl` but `funnel_events.jsonl` has no matching `forgot` event
and no `deleted`-kind spool doc was queued — while the user sees
"already deleted" and cannot re-trigger the scrub. (Precision: a crash
between the row commit and the forget-token consume leaves the forget
link *live*, not consumed — re-clicking it then runs the full forget
path, scrubs included. Only a crash *after* the consume strands the
scrub.) Recovery, by hand, in the data dir: (1) confirm the row is gone;
(2) delete `patha_events.jsonl` lines whose `"address"` is the forgotten
address (or wait out the ledger's 48h prune); (3) delete `triage/*.eml`
files containing the address (case-insensitive, plus-tag variants
included); (4) filter `rows.jsonl.skipped.*.jsonl` lines containing it;
(5) delete pending `spool/*.json` docs with `"to"` equal to the address;
(6) if no deletion confirmation was ever queued, send one manually —
the user was promised it.

**Backups:** snapshots or backups of the data dir taken *before* the
forget still contain the address, and no code change can erase them.
The forget guarantee covers the live stores only. The operator must
rotate/destroy pre-forget backups under their own backup retention —
until that happens, a restored backup reintroduces the address.

**Retention:** unconfirmed → dropped at 14d, row deleted 30d after drop —
a dropped row with no recorded drop date is never auto-purged (the 30
days cannot be proven); the operator removes it by hand;
confirmed → kept until launch + 90 days (the invite window), then
anonymized to counts; invited-but-expired → returns to `confirmed` with
`confirmed_at` reset to the expiry time (back of the queue, no
re-confirmation needed — the address is already verified);
triage → 48h: every triage write purges files older than 48h (the
daemon-clock timestamp in the filename; non-conforming filenames are
left alone). 48h is the operator's review-cadence bound, not a
borrowed window: unprocessable mail is eyeballed within a day or two
or it never will be, and raw inbound mail is the highest-PII-density
store outside the row store — anything older is either handled or
stale, and keeping it only extends the exposure.
funnel events → 90d hot, archived not deleted (#897): the hot
`funnel_events.jsonl` keeps events newer than 90d plus the
coverage-pinned ones — `invite_sent`/`claimed` events the reconcile
passes still consult for live `invited`/`signed_up` rows, which stay
regardless of age (rotating one would make the next reconcile pass
re-emit a duplicate event). Everything else older than 90d rotates to
`funnel_events-archive-<YYYY-MM>.jsonl`, bucketed by the event's own
`at` month. Archives are the audit trail: the loop never deletes them;
their lifecycle is the operator's backup-retention call, same as
**Backups** above. Unparseable lines and events with no provable `at`
are fail-closed (stay in the hot file — a skip must never become a
silent delete). 90d is ~2x the dropped-row purge horizon (14d drop +
30d purge); pinning, not the horizon, carries reconcile correctness.
The rotation runs as `waitlist_jobs.py --rotate-funnel-events`
(weekly cron; `--dry-run` reports the partition); it holds the data
lock, appends archives before the atomic hot rewrite (a kill between
the two can only duplicate archive lines, and the re-run skips
already-landed lines — the pass is idempotent). The horizon is
overridable via `WAITLIST_FUNNEL_RETENTION_SECONDS` (positive int
seconds; fail loud on garbage). Operator verification: the dry-run
counts, then `ls funnel_events-archive-*.jsonl` against the hot file's
oldest `at`. Funnel metrics keep working: `scripts/funnel_metrics.py`
takes an explicit `--events` export — point it at the hot file plus
whichever archives the query window needs.

**Spool-drain contract (operator's sender):** spool files are drained as
JSON by the operator's external sender; the contract is now stated, not
implied — the sender MUST delete each spool file after a successful
send. A spool file is the only copy of its email; retention is bounded
by drain latency, and a forgotten address's deletion confirmation is
deleted on send like any other. The operator MUST NOT retain spool
files beyond successful delivery.

**Quarantined skipped lines:** when the service finds a torn or malformed
line while loading the waiting list, the unreadable bytes are quarantined
to a `rows.jsonl.skipped.<timestamp>.jsonl` sidecar in the data directory
before any rewrite — never silently destroyed. Those sidecars may contain
`owner_email` PII from lines the loader could not parse; they inherit the
data directory's encrypted-at-rest property. Since #400, a honored forget
automatically filters the forgotten address out of these sidecars (see
Deletion policy above); lines for other addresses keep the operator's
hand-review contract — the operator must review each sidecar and delete
it after hand-repair or deliberate retirement.

## 6. Abuse model

Per path, because the defenses differ:

- **Path A (email):** per-sender rate limit (3 submissions / sender / day
  — a Muse fleet *can* spray; the confirm gate is what makes spraying
  worthless, §3); per-owner-email dedup on the **normalized** address
  (lowercase; strip everything after `+`; one pending entry — re-submits
  refresh the timestamp); confirm-gating (unconfirmed entries are inert);
  clarification replies only on DMARC-aligned mail, otherwise silent
  operator triage (§2 — no backscatter); operator blocklist for obvious
  abuse (same payload × N senders). No CAPTCHA is possible or needed on
  an email path — the human click *is* the CAPTCHA.
- **Path B (form):** honeypot + time-trap + per-IP rate limit
  (`LANDING_PAGE_COPY.md` §4, unchanged).
- **Both:** no card at waitlist stage (Billing decision — said in the
  confirm email so the later card ask is never a surprise);
  transactional-email rate limits (§4, all reply types counted together)
  so the reminder job can't be weaponized into a mail cannon; the store
  is never writable from the public internet — only the two parsers
  write, and they write validated rows; **no unauthenticated position
  lookup** — queue position is disclosed only inside signed emails
  (confirm/reminder/invite footers), never via a query-by-email endpoint
  (that's an enumeration oracle: waitlisted-or-not + queue depth as
  competitive intel).

Feeds the open Abuse-controls item (NEEDS_USER.md): the waitlist-stage
rate limits + verification level are decided here; signup-stage controls
stay open.

## 7. Invite waves

**Order:** waitlist order (FIFO by `confirmed_at`) — this is the promise
`LANDING_PAGE_COPY.md` §4 makes ("invites go in waitlist order") and FAQ
Q6 repeats ("first invites go there"). The R7 beta-Muse pilot cohort is
recruited *separately* by the operator (NEEDS_USER.md) and runs its
validation on the participants' **own boxes, pre-launch** — it consumes no
hosted inventory, so it never jumps the waitlist and the FIFO promise
needs no asterisk. The page's FAQ discloses the pilot as a pre-launch
validation phase (§10 gate), so "first invites go there" is never read as
"nobody touches a box before wave 1."

**Invite email (DRAFT):** sent when the operator opens a wave. Carries the
real pricing numbers *before* any card is asked for (`LANDING_PAGE_COPY.md`
§4's pricing-teaser honesty rule — the numbers are filled at send time
from the decided pricing, never templated in advance):

> Subject: You're off the waitlist — claim your box
>
> You're off the waitlist — hosted boxes are open.
>
> [ Claim your box ]
>
> Pricing first — the exact numbers, before we ask for anything:
> <plan/price lines, filled at send time>. <Trial terms, filled at send
> time — card required up front, per the Billing decision.>
>
> What happens next: you'll link your agent's identity (it proves itself
> with a key, you approve the fingerprint), bring your Tailscale tailnet,
> and put a card on file. Your box is a real computer — files, jobs, and
> the desktop persist.
>
> You held #N in line — this invite expires in 14 days. After that it
> rolls to the next entry in line.

**Expiry:** 14 days; expired invites roll the slot to the next confirmed
entry and the expired entry rejoins `confirmed` at the back of the queue
(§5 — no re-confirmation). The 14-day claim window is disclosed on the
page (FAQ Q6 or how-it-works step 1; §10 gate) — a reader promised "we'll
email you the moment your box is ready" must know the box doesn't wait
forever.

**Commit → emit crash window:** the wave commits the invited row BEFORE
emitting the `invite_sent` funnel event (the `FUNNEL_MEASUREMENT.md` §3.4
taxonomy); a crash in that
window leaves an invited row whose invite email is spooled but whose event
never fired. The funnel reads conservatively until repaired —
invite→claim ratios under-report rather than claim what rows.jsonl
doesn't show. The operator repairs it with:

    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \
        waitlist_invites.py --reconcile   # idempotent; --dry-run to preview

The pass re-derives only the missing events from rows.jsonl (append-only
posture — the event trail is never hand-edited), marks each with
`reconciled: true` + `via: reconcile_invite_events` in its attrs, and
skips rows whose invite is no longer live (expired, consumed, or rolled
back to confirmed): a dead invite can't convert. Rows already rolled
back to confirmed rejoin the queue — the next wave's fresh invite
carries its own event. Rows whose invite expired *without* a rollover
(e.g. the rollover cron was down) stay unrepaired by design: run the
daily `--rollover` first so they rejoin confirmed. Reviving dead invites
is the #235 operator tooling, not this pass. Run it after any suspected
crash; re-running when nothing is missing is a no-op.

**Claim commit → emit crash window (issue #898):** `claim_post` commits
the signed_up row (and consumes the invite token) BEFORE emitting the
`claimed` funnel event; a crash in that window leaves a claimed row
whose event never fired, and the funnel under-reports invite_sent →
claimed conversion until repaired (the signup-era provisioning surface
reads the claim stream). Repair with:

    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \
        waitlist_invites.py --reconcile-claimed   # idempotent; --dry-run to preview

`--reconcile` runs this pass too, after the invite_sent pass. The pass
re-derives only the missing events from rows.jsonl (append-only posture
— the event trail is never hand-edited), marks each with `reconciled:
true` + `via: reconcile_claimed_events` in its attrs, and is simpler
than the invite pass by design: signed_up is terminal, so there is no
wave/reinvite ambiguity and no token-liveness check — every signed_up
row without a `claimed` event at or after its signed_up_at gets one.
Run it after any suspected crash; re-running when nothing is missing is
a no-op.

**Per-invocation wave manifests (issue #405):** every `--send-wave`
invocation writes one JSON manifest to `wave_manifests/` in the data
dir, recording the wave name, invocation time, requested count, the
invited entry IDs in wave order, and the skipped entry IDs
(cap-suppressed or spool-failed rows — still confirmed, retried cleanly
by the next wave). The CLI prints the invited IDs and the manifest path.
This is the audit trail of *what one invocation did*: a crash after 5 of
25 invites followed by a retry reads as two manifests under the same
wave name, not as one wave whose count is ambiguous — re-running
`--wave wave1` invites 20 *more* rows under the same name (the status
gate prevents double-invites), and the two manifests show exactly which
rows each invocation invited.

**Invite-wave recovery (issue #235):** a second crash window lives in the
re-invite path — a crash after `_consume_token(old)` but before the row
commit leaves the on-disk row `invited` with a consumed token. The same
tooling covers operator-initiated re-waves (invite email bounced or lost).
Recover it append-only — never hand-edit `rows.jsonl`:

    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \
        waitlist_invites.py --diagnose   # which stranded state each invited row is in

`--diagnose` is read-only and lists every invited row with its token
state: `ok` (live — nothing to do), `expired` (run the daily `--rollover`
first), `consumed` (crash-suspect — reinstate candidate), `invalid` /
`missing` (hand-damaged — inspect by hand, never auto-repaired). Then:

    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \
        waitlist_invites.py --reinstate-confirmed --entry-id EID \
            --reason "wave2 crashed between consume and commit; re-waving" \
            [--dry-run] [--force]

`--reinstate-confirmed` appends one new rows.jsonl revision per row:
status flips to `confirmed`, the invite keys are popped (the prior
invited revisions and the `invite_sent` funnel event keep the audit
trail), `confirmed_at` is **kept** — this is a crash repair, not an
expiry, so the entry rejoins at its original queue position — and the
revision is stamped with `reinstate_at` + `reinstate_reason`. No email
is sent and no funnel event is emitted (the §3.4 taxonomy has none for
this); the next ordinary `--send-wave` re-invites the row with a fresh
token. `--reason` is required — it is the audit trail. A row whose
invite token is still **live** is refused unless `--force` (reinstating
kills the claim link, so the operator must say so explicitly); `--force`
consumes the live token first so the trail reads `consumed`. An
**expired** invite is refused outright — don't reinstate expired rows,
that's what `--rollover` is for; reinstate keeps the original queue
position, which would silently skip the disclosed 14-day expiry →
back-of-queue rule. `--dry-run` previews the plan (and refuses the same
way the real run does — no preview/reality divergence). Duplicate
`--entry-id` values are collapsed to one revision per row.

If the command itself dies mid-run across multiple `--entry-id`s, the
rows already flipped are `confirmed` and a re-run fails loud on them —
re-run `--diagnose`, drop the already-`confirmed` entries from the list,
and re-run `--reinstate-confirmed` for the remainder. Note the crashed
wave's stray email counted against the §4 3/24h cap when it went out —
if the cap is still full, the re-wave leaves the row confirmed for a
later wave.

*Compliance:* pricing lines are filled at send time from decided pricing —
the template never contains numbers; no "free tier" wording (Billing
decision); no launch-date promises (the invite *is* the launch for that
reader); `POSITIONING.md` anti-claims hold (sentinel unnamed).

## 8. Handoff to signup (H15)

- When signup opens, the waitlist retires as a funnel — no parallel
  funnels. Confirmed entries become the day-1 invite queue.
- Signup pre-fills the owner email from the waitlist entry and **skips
  email re-verification** (reachability already proven); it does not skip
  H3 identity linking (different gate: agent identity + human approval).
- If the waitlisted `muse_pubkey` matches the key presented at signup, the
  UI shows the continuity hint (§2) — convenience, not trust.
- What the waitlist teaches signup: the confirm→invite→claim email cadence
  that worked (measured, §9) becomes the signup's transactional-email
  pattern; the abuse signals (spray sources, blocklist) seed signup's
  controls.

## 9. Metrics

Operationalizing `LANDING_PAGE_COPY.md` §6 (definitions unchanged, wiring
specified):

- **Primary — waitlist-confirmed rate** = confirmed signups / unique page
  visitors. Depends on the privacy-respecting analytics choice
  (`LANDING_PAGE_COPY.md` §7 follow-up — no third-party trackers). Until
  that's chosen, the primary is **held**: report the confirm rate
  (confirmed / confirm-emails sent) as the interim funnel-health number
  rather than showing two names for one number.
- **Bridge — waitlist→identity-linked** = signups reaching H3 identity
  linking / confirmed waitlist entries. Computed once signup exists; never
  folded into the page metric (the drop-off must stay visible).
- **Funnel health:** confirm rate, reminder lift (confirmed via reminder /
  reminded), invite→claim rate, median hours submit→confirm.
- **Anti-metrics (never optimize):** time-on-page, scroll depth —
  restated from §6 because the analytics choice will tempt someone.
- **Operator observability — `GET /waitlist/status` (loopback only):**
  returns spool backlog (`files`, `oldest_age_seconds`, `by_kind`) and
  row counts by status (`rows`). If the operator's sender dies, invites,
  reminders, and confirmations pile up in `spool/` — this endpoint makes
  that pile visible. Off-loopback peers get a 404 even when the daemon
  binds a non-loopback interface; there is no HMAC auth on it because
  loopback is the whole trust story — bind `WAITLIST_BIND` to a
  loopback address and keep it that way. Spool kinds are `confirm`,
  `invite`, `reminder`, `deleted`, and the Path-A signup kinds; spool
  files written before `kind` tagging (pre-existing files) report as
  `unknown` until they drain. `oldest_age_seconds` is null when the
  spool is empty; alert when it exceeds your sender's normal drain
  window. If the spool directory is unreadable the payload carries
  `spool.error: "spool directory unreadable"` — that is an outage,
  not an empty spool.

## 10. Build checklist (the §5 gate, made actionable)

The page must not ship until every item is live — each with its done
criterion:

- [ ] **Waitlist inbox** provisioned (dedicated AgentMail inbox) + inbound
  verified (send→receive round trip).
- [ ] **Inbox address printed on the page**: the waitlist copy block prints
  the dedicated Path-A inbox address alongside the form CTA (§2) — the
  Muse's discovery step. (A printed agent address is not a mailto-link CTA:
  `LANDING_PAGE_COPY.md` §4's "a mailto link is not a funnel" rule stands;
  the address is discovery affordance, the form CTA remains the conversion
  instrument.)
- [ ] **Store** (operator-side, §5 schema) with encrypted-at-rest owner
  emails.
- [ ] **Path-A parser**: email → validated row; exclusion list + `Owner:`
  override; multi/zero-address clarification reply (DMARC-gated, §2);
  per-sender rate limit; normalized per-owner dedup.
- [ ] **Path-B form + endpoint**: honeypot + time-trap + per-IP limit;
  writes validated rows only.
- [ ] **Confirm sender + token signer**: HMAC, single-use, 14d expiry;
  idempotent re-click ("you're already confirmed"); rate-limited
  (all reply types counted); reminder job at +7d; drop job at +14d;
  purge job 30d after drop (atomic rewrite; `purged` funnel events keep
  the counts after the PII is deleted).
  HTTP method shape per the §4 note (open PR #99 supersedes the GET
  language: GET renders the confirm page, POST confirms).
- [ ] **Abuse controls** (§6) live on both paths; no unauthenticated
  position lookup.
- [ ] **Invite sender**: fills pricing + trial terms at send time; 14d
  expiry; signed position line in emails.
- [ ] **Spool-draining sender**: the external sender that drains `spool/`
  deletes each spool file after successful send and never retains them
  (the §5 spool-drain contract — a spool file is the only copy of its
  email, and a forgotten address's deletion confirmation is deleted on
  send like any other).
- [ ] **Forget-me handler**: signed footer link honored ≤7d,
  confirmation sent; reply-"forget me" → confirmation email with the
  signed link (never direct deletion).
- [ ] **Metrics wiring**: privacy-respecting analytics chosen; interim
  confirm-rate reporting until then; bridge + funnel-health queries
  defined.
- [ ] **Page disclosure gates**: the 14-day invite claim window is stated
  on the page (FAQ Q6 or how-it-works step 1) — DRAFT acceptance copy:
  *"Invites are claimed within 14 days — unclaimed spots roll to the next
  reader in line."*; the pre-launch pilot phase is disclosed in the FAQ —
  so the page never promises what this spec doesn't deliver.
- [ ] **Copy review**: the drafts above re-read against
  `POSITIONING.md` anti-claims at send time (docs drift).

## 11. Honesty compliance notes

- The waitlist is a *reachability* list, not a launch promise — no dates
  anywhere, including "soon."
- Pricing appears exactly once before any card ask: in the invite email,
  filled at send time. Nowhere earlier.
- "No card required for the waitlist" ≠ "no card required ever" — the
  confirm email says the first; the invite email says the second (card on
  file at signup, Billing decision).
- FIFO is the order promise; the pilot is pre-launch validation on
  participants' own boxes, disclosed in the FAQ — never a quiet jump.
- The 14-day claim window is a page-disclosed term (§10), not spec
  fine print.
- The page ships only after §10 is green — the dead form
  `LANDING_PAGE_COPY.md` §5's checklist forbids.
