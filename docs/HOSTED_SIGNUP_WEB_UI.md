# Hosted signup web UI + human dashboard — build spec (H15)

**Status: design spec, not the implementation.** This is the build spec for
**H15** — the signup web UI + human dashboard (from `docs/HOSTED_GAP_ANALYSIS.md`
§7 / the H15 backlog item: "account/boxes/approvals/usage surface"). It answers
the funnel's last unbuilt question: when the page exists (front door) and the
waitlist works (instrument), what does the human actually click through —
and what gets built in what order. Copy blocks are **DRAFTS**, not published
copy.

**Dependencies:** citations of `docs/LANDING_PAGE_COPY.md` refer to the merged
version on main (PR #61 landed). Citations of `docs/WAITLIST_OPERATIONS.md`
refer to the merged version on main (PR #68, `18f0f0e5`) and of
`docs/FUNNEL_MEASUREMENT.md` to the merged version on main (PR #99, `c9e859e5`)
— section numbers re-verified against main 2026-09-20. Merge order satisfied:
#61 (done) → #68 → #99 → this.

**Non-overlap map (what this doc is not):**
- The front-door strategy (conversion job, section order, copy blocks, page
  honesty rules, metric *definitions*) is `docs/LANDING_PAGE_COPY.md` — this
  doc *typesets* its §2/§3 into a buildable page, never restates the strategy.
- The waitlist instrument (submission paths, confirm flow, data model, abuse
  model, invite waves, build checklist) is `docs/WAITLIST_OPERATIONS.md`
  (PR #68) — this doc *hosts* its endpoints and pages, never redefines the
  instrument.
- The measurement wiring (analytics decision, GET/POST confirm shape, OG
  tags, event schema, query pack) is `docs/FUNNEL_MEASUREMENT.md` (PR #99) —
  this doc *implements* its build-side rules, never re-decides them.
- Identity linking (ed25519 + human fingerprint approval, re-link) is the H3
  hosted signup/onboarding design (`docs/HOSTED_SIGNUP_ONBOARDING.md` §4) —
  this doc renders its signup flow (§5) as screens, never re-specifies the
  cryptography.
- The funnel this serves is `docs/FIRST_RUN_ACTIVATION.md` §2; the funnel's
  honesty rules (§7) bind every screen below.
- Positioning one-liners and anti-claims are `docs/POSITIONING.md` — the
  spec below stays inside them (see §9).

## 1. The gap this closes

Three funnel docs describe a funnel with no surfaces. `LANDING_PAGE_COPY.md`
§7 defers the page build to H15; `WAITLIST_OPERATIONS.md` §10 gates the page
on a live build checklist with no host; `FUNNEL_MEASUREMENT.md` §9 names
`scripts/funnel_metrics.py` "shipped with the page PR" — but nobody has said
where the page lives, what the confirm page renders on, which endpoints the
control plane exposes, or what the signup UI and dashboard contain when they
arrive. An implementer reading the three docs has strategy, instrument, and
wiring — and nowhere to put them.

This doc closes the gap in **three staged surfaces**, because the three docs
themselves stage the product: the waitlist era (page + instrument, live
pre-launch), the signup era (account + identity linking + provisioning,
gated on the hosted launch), and the dashboard era (the owner's ongoing
surface). Building them as one artifact ships a dashboard with nothing to
dashboard.

## 2. Staging (three surfaces, in order)

### Surface 1 — waitlist era (pre-launch; the only live funnel)

The front door: the landing page + the waitlist form + the confirm page.
Everything `LANDING_PAGE_COPY.md` §2's flow map specifies, plus the two
waitlist submission paths (`WAITLIST_OPERATIONS.md` §2, PR #68) and the
measurement wiring (`FUNNEL_MEASUREMENT.md` §§3–5, PR #99). **There is no
account, no dashboard, no signup UI in this era** — the page must never link
a surface that doesn't exist yet (the dead-form rule, `LANDING_PAGE_COPY.md`
§5 checklist item 11, applies to navigation too).

The waitlist retires as a funnel when signup opens (`WAITLIST_OPERATIONS.md`
§8, PR #68): confirmed entries become the day-1 invite queue; no parallel
funnels. The waitlist pages stay live (confirm/forget links keep resolving
through their claim windows — `WAITLIST_OPERATIONS.md` §8 designs no
post-launch waitlist and forbids parallel funnels) but the CTA job changes
from "join the list" to the signup flow below.

### Surface 2 — signup era (hosted launch)

The signup web UI: account creation (email + magic link), plan + card on
file, enrollment-token handoff, pending-key approval (fingerprint), tenant
status polling. This is `HOSTED_SIGNUP_ONBOARDING.md` §5 rendered as the
screens in §5. Gated on the operator packet (§10): control-plane
Fly machine + sparkvm.dev front door live, billing provider chosen.

### Surface 3 — dashboard era (post first-box)

The human dashboard: account/boxes/approvals/usage (§6). Ships after the
first boxes are provisionable — a dashboard with no boxes is the dead-form
rule wearing a nicer hat.

## 3. Hosting shape (decided infrastructure)

Per NEEDS_USER.md (all decided 2026-09-18): static site on **Cloudflare
Pages (free)**; control-plane API + sentinel + push sender on **one small
Fly machine (~$3–6/mo)**; domain **sparkvm.dev purchased** (Cloudflare
zone active). H15's surfaces land on this shape:

- **Marketing page + waitlist form + OG head** — static, on Pages
  (`sparkvm.dev/`). First-party, no JS analytics (`FUNNEL_MEASUREMENT.md`
  §3: no client JS at all).
- **Confirm page** — the one dynamic page, rendered by the control-plane
  API (`GET /waitlist/confirm?token=`). Rationale: the page renders
  `<masked>` (first 3 chars of the owner's local part —
  `FUNNEL_MEASUREMENT.md` §4.2, PR #99), which derives from the
  HMAC-signed token payload the static host cannot verify. A static Pages
  render would either expose the token payload to client JS (defeating the
  masking) or confirm without the masking rule at all. The control plane
  renders server-side and applies the page's unfurl-hygiene headers
  (`Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex, nofollow`, no OG
  or Twitter tags — `FUNNEL_MEASUREMENT.md` §4.2, PR #99). The confirm
  *action* is a plain form POST to the same host — no JS, per the same
  section.
- **Waitlist API + store + senders + jobs** — on the Fly control plane,
  operator-side only. The store is never writable from the public
  internet (`WAITLIST_OPERATIONS.md` §6, PR #68): only the two parsers
  (AgentMail-inbound for path A, the form endpoint for path B) write
  validated rows.
- **Metrics** — `scripts/funnel_metrics.py` runs on the control-plane
  host, reading the access-log rollups + the store (`FUNNEL_MEASUREMENT.md`
  §7, PR #99). The rollups' log source, named: a first-party Cloudflare
  Worker in front of the Pages assets records method/path/query + hashed
  IP to the control plane per hit (no client JS — the Worker, not a
  beacon), because Pages' free tier exposes no raw request logs for "the
  page server's own access log" (`FUNNEL_MEASUREMENT.md` §3, PR #99) to
  read. Log retention: the page-build runbook states the raw-log retention
  policy explicitly (FUNNEL §3.1) — the honest claim is "no IPs retained
  in the metrics store," never "we collect nothing." The day-1 query pack
  ships with the page-build PR.

## 4. Surface 1 build spec — the waitlist page

### 4.1 Page structure (typesets `LANDING_PAGE_COPY.md` §2/§3)

Section order and copy are `LANDING_PAGE_COPY.md` §§2–3 as merged — this
doc specifies only the build-side additions:

- `<head>`: exactly the tag set from `FUNNEL_MEASUREMENT.md` §5 (PR #99) —
  the `<meta name="description">` (non-OG), `og:url`, `og:type`, `og:title`,
  `og:description` (scoped to *this
  page*, no product-wide trackers claim), `og:image` (the persistence pair
  from the demo-assets plan — `assets/README.md` asset 3, currently a
  follow-up; the page build produces `og-persistence-pair.png`,
  first-party hosted, no query-string trackers), `og:image:alt`,
  `twitter:card`. No `fb:app_id`, no pre-claimed handles.
- The two CTAs from the flow map: primary "Join the waitlist"
  (the form, §4.2), secondary quiet "Self-host today" text link —
  exactly twice (under the hero button, in the FAQ), via a first-party
  redirect (`/go/selfhost?src=selfhost` → the repo README's Try-it section,
  per `LANDING_PAGE_COPY.md` §5 checklist item 9) so `src=` stays
  on our domain (`FUNNEL_MEASUREMENT.md` §3.2, PR #99).
- Each waitlist CTA is a distinct first-party URL with its section bucket:
  `/waitlist?src=hero`, `?src=trust`, `?src=faq`, `?src=final`
  (`FUNNEL_MEASUREMENT.md` §3.2, PR #99 — the final-CTA block gets its own
  bucket, not folded into `hero`).
- The launch-state strip sits directly under the hero, per
  `LANDING_PAGE_COPY.md` §2 — placement is the honesty.
- The 14-day invite claim window is stated on the page (FAQ Q6 or
  how-it-works step 1 — `WAITLIST_OPERATIONS.md` §10, PR #68) and the
  pre-launch pilot phase is disclosed in the FAQ (same checklist item),
  so the page never promises what the spec doesn't deliver.
- The form itself (§4.2) is the only interactive element on the `/waitlist`
  page.
- **`/waitlist` is a dedicated minimal page** (every CTA links there; it is
  not an anchor on the landing page). It carries the same `<head>` tag set
  as the landing page (`og:url` points at the marketing page — this spec's
  choice, since the share target is the product, not the form;
  `FUNNEL_MEASUREMENT.md` §5 defines the tag set for the landing page), `<title>` "Join the waitlist —
  spark-vm", a heading plus one line of the `LANDING_PAGE_COPY.md` §3 hero
  microcopy for context, the §4.2 form, the path-A inbox line (the Muse
  reader's entry point, no separate discovery), and a back-to-`/` link.
  No OG identity of its own — a share of the form unfurls as the product.

### 4.2 The waitlist form (path B) + the email path (path A)

- **Form fields:** owner email (required), Muse contact email (optional —
  "where should we reach your agent"), nothing else
  (`WAITLIST_OPERATIONS.md` §2, PR #68). Visible `<label>`s,
  `autocomplete="email"` and `inputmode="email"` on the owner-email input;
  `autocomplete="off"` and `inputmode="email"` on the optional Muse-contact
  field (so browser autofill doesn't misfire the owner's address there);
  honeypot + time-trap + per-IP rate limit, per `LANDING_PAGE_COPY.md` §4.
- **Form endpoint:** `POST /waitlist/form` on the control plane —
  validates, writes a validated row only, returns a static "check your
  inbox" page (never JSON the page JS would parse — there is no page JS).
  The page echoes the full self-submitted owner address (it came from the
  reader's own form — no privacy cost) with a "wrong address? go back"
  link, so a typo'd submission can be caught. Honeypot trips are
  *accepted silently* (200, same rendering) — the spam learns nothing.
- **Email path (path A):** the page prints the waitlist inbox address
  alongside the form CTA ("Your agent can start the signup — the
  confirmation email goes to your owner," `LANDING_PAGE_COPY.md` §3 hero
  microcopy). The inbox is the dedicated AgentMail inbox from
  `WAITLIST_OPERATIONS.md` §2 (PR #68) — a second inbox on the existing
  free tier. The path-A parser (exclusion list, `Owner:` override,
  DMARC-gated clarification reply, per-sender rate limit, normalized
  dedup) is `WAITLIST_OPERATIONS.md` §§2/6 (PR #68), unchanged here.
- Both paths converge on the confirm flow (§4.3) and the same store.

### 4.3 Confirm flow (HTTP shape from `FUNNEL_MEASUREMENT.md` §4, PR #99)

- `GET /waitlist/confirm?token=<hmac>` renders only — **never changes
  state**. Four states with the defined copy from `FUNNEL_MEASUREMENT.md`
  §4.3 (PR #99): valid-pending (button page + the 14-day claim-window
  line), already-confirmed, POST-success (same rendering as
  already-confirmed, verbatim), expired/invalid (rule, not error, +
  rejoin link). Masked owner line: first 3 chars of the local part + "…".
- `POST /waitlist/confirm` (token as form field, not query string)
  performs the confirmation: row → `confirmed`, `confirmed` event with
  `via` = `original`/`reminder`, idempotent re-POST. This **supersedes**
  `WAITLIST_OPERATIONS.md` §4's "Confirmation is a GET on a signed link"
  (PR #68) — the mail-scanner threat (`FUNNEL_MEASUREMENT.md` §4.1, PR
  #99) is the reason.
- Token mechanics stay `WAITLIST_OPERATIONS.md` §4 (PR #68): HMAC-signed,
  operator key never in the repo, `{owner_email, entry_id, issued_at}`,
  single-use, 14-day expiry, +7d reminder, 14d drop, all-reply-types
  3/24h rate limit.
- The +7d reminder re-sends the same link shape (GET page, POST button) —
  one link shape everywhere.

### 4.4 What "page ships" means (the §10 gate, build-side)

The page ships only when every `WAITLIST_OPERATIONS.md` §10 (PR #68)
checklist item is live — each with the done criterion that section
states — **plus** the measurement items from `FUNNEL_MEASUREMENT.md` §9
(PR #99): the §5 tags typeset, the `src=` CTA URLs wired, and
`scripts/funnel_metrics.py` shipped in the page-build PR ("metrics that
need a second PR to compute are metrics that never get computed").

## 5. Surface 2 build spec — the signup web UI

This renders `HOSTED_SIGNUP_ONBOARDING.md` §5's MVP flow as screens. The
flow's crypto and provisioning contracts are H3's; this doc specifies the
screens and their honesty constraints.

**Stale-line flag (typeset-time correction):** H3 §5 was written before
the Billing decision. Two of its lines are stale and must NOT be rendered:
"pick plan (free tier first; paid later — operator decision)" and
"Plan/pricing summary (operator decision; free tier recommended for
adoption)." The decided shape is
**no free tier at launch; card-required trial possible, trial terms TBD**
(NEEDS_USER.md Billing). The plan screen shows the trial on the decided
terms and never prints "free tier" (`FIRST_RUN_ACTIVATION.md` §7).

Screens, in order:

0. **Claim (the invite gate)** — the launch is wave-gated
   (`WAITLIST_OPERATIONS.md` §7, PR #68): invites go in FIFO order, the
   invite email carries a "Claim your box" link, the invite expires in 14
   days and the slot rolls over. The signup URL is invite-claimed: a signed
   invite link lands the reader on claim, which pre-fills the owner email
   from the waitlist entry and skips email re-verification (reachability
   already proven — `WAITLIST_OPERATIONS.md` §8, PR #68). A non-invited
   visitor sees a plain holding page — "your invite hasn't arrived yet"
   with the FIFO/wave explainer (invites go in waitlist order; yours
   arrives by email when your wave opens) and at most a link back to `/`,
   never a link back to the waitlist page and never an open signup. (The
   signup-era waitlist page's CTA points at the signup flow below, which
   rejects the non-invited visitor — a back-link would loop
   claim → holding → /waitlist → claim.) An open page would admit
   out-of-wave tenants and break both the FIFO promise and the capacity
   gate. An expired-invite click
   renders the roll-over rule from `WAITLIST_OPERATIONS.md` §7 (PR #68) —
   back of the confirmed queue, no re-confirmation needed — never "your
   invite expired, start over."
1. **Account** — email + magic link (no password to phish — H3 §5; the
   magic link establishes the session, it is not a re-verification).
   Signup pre-fills the owner email from the waitlist entry and **skips
   email re-verification** (reachability already proven —
   `WAITLIST_OPERATIONS.md` §8, PR #68); it does not skip identity linking.
2. **Plan + card on file** — the decided billing shape. The exact tiers
   come from the decided-pricing source the invite email uses ("filled at
   send time from the decided pricing" — `WAITLIST_OPERATIONS.md` §7,
   PR #68); the signup UI names that same source so the email and the
   screen cannot drift.
3. **Link identity** — name the box; the enrollment token (H3 §5:
   single-use, 15-minute TTL, shown in the signup UI after magic-link
   auth — the signup UI is its only channel). "Copy for your Muse" is a
   real affordance, not a line of copy: the no-client-JS rule
   (`FUNNEL_MEASUREMENT.md` §3) binds the marketing/waitlist/status
   surfaces, not this screen, so the token screen may carry minimal
   first-party JS for the copy button, with a selectable token block as
   the no-JS fallback. Re-display rule (server-derived from tenant
   state, matching the abandonment rule): the *current unspent* token
   re-renders while the identity is still unlinked and the token is
   unexpired; once linked or expired it is never re-rendered. A
   lost/expired token is a *fresh* token, not a re-display — the H3 §4
   re-link path (the Muse requests with its `muse_id`, the human approves
   with one click); the funnel re-enters at screen 3 in that case. The
   pending-key approval UI: the key
   fingerprint rendered **prominently** with the H3 re-link email UX
   requirement (prominent new fingerprint + rate limits — recorded in the
   loop's BACKLOG H3 follow-up; `WAITLIST_OPERATIONS.md` §4, PR #68,
   defers it there). If the waitlisted
   `muse_pubkey` matches the presented key, the UI shows the continuity
   hint ("matches the key your agent submitted" — convenience, not trust —
   `WAITLIST_OPERATIONS.md` §8, PR #68). The waitlist→identity-linked
   bridge metric (`FUNNEL_MEASUREMENT.md` §7, PR #99 —
   waitlist→identity-linked, kept visible, never folded into the page
   metric) starts emitting here: the signup backend emits an
   `identity_linked` event into `funnel_events` with `ref` = the waitlist
   row id and no attrs, on **entering** the link-identity step (the §7
   numerator is "signups *reaching* H3 identity linking" — reaching, not
   approval completion). This is PR 2's one extension to the
   `FUNNEL_MEASUREMENT.md` §3.4 event table, per §9's "emit into
   `funnel_events` from day one" — the "no other instrumentation" line
   scopes §9's waitlist-era metrics, not the signup era.
4. **Bring your tailnet** — BYO Tailscale link step (decided, NEEDS_USER.md
   Tailnet). H3 §11.2's open tailnet-shape question is closed; the signup
   UI renders the decided shape, not the question.
5. **Status** — the page and the Muse both poll `GET /tenant/status`;
   when it flips to `live`, both see "your box is ready" (H3 §5). The
   human's page is no-JS (`FUNNEL_MEASUREMENT.md` §3, PR #99): refresh is
   `<meta http-equiv="refresh">` plus a manual "Check status" plain-form
   POST. The first-10-minutes clock starts at box-ready, not at signup
   (H3 §5) — the signup page says so plainly, so nobody stares at a spinner.
   The no-JS rule is status-screen-only: screen 2's card screen needs the
   payment processor's third-party script, which `FUNNEL_MEASUREMENT.md` §5
   already anticipates in its no-trackers caveat — the signup flow never
   claims the no-trackers property past the marketing page.
6. **Connection bundle** — the Muse's relay hostname + short-lived cert;
   the human's one-command cred-ui tunnel script (H3 §5). The human's
   first-credential install via cred-ui stays the one designed-manual step.

**Abandonment / re-entry:** the funnel re-enters at the first incomplete
screen, server-derived from tenant state — it never restarts, and it never
re-asks for the card. An account without a box renders the funnel, never
the dashboard (the dashboard "ships after the first boxes are
provisionable" — §2 — and an empty one would be dead navigation wearing a
nicer hat).

**Scope discipline:** the signup UI is a funnel, not a dashboard
(H3 §5: "It is a funnel, not a dashboard"). Account management beyond the
flow (key rotation, plan changes) waits for surface 3.

## 6. Surface 3 build spec — the human dashboard

The owner's ongoing surface: **account / boxes / approvals / usage**
(the H15 backlog item). Each panel's gating is named — the dashboard must
never render a panel whose substrate doesn't exist.

- **Account** — owner email (magic-link session), linked agent keys with
  fingerprint history (incl. re-link events), tailnet link state,
  card-on-file state. Never full PAN — the processor owns the card; the
  dashboard shows the decided billing surface's last-four/expiry only.
- **Boxes** — the tenant's boxes: name, status, connection-bundle
  re-issue, destroy. The status shown maps onto the H3 §6 provider
  contract (`status(vm_id) -> creating | ready | degraded | dead`):
  `creating` renders as `provisioning`, `ready` as `live`, and
  `degraded` / `dead` render as-is with their remediation guidance
  (H3 §6) — the panel never hides a human-facing failure state. Status
  states beyond `live` (`suspended` / `waking`) require the H4 driver —
  itself gated on the operator's spend-cap packet (NEEDS_USER.md) — to
  ship the planned extensions to that contract; until then the panel
  shows `provisioning`/`live` only and says nothing about suspend.
  (Earlier notes cited "PR #40" for these extensions — that number is
  the GPU-research deliverable; the extensions are unshipped H4 work.)
  Connection-bundle re-issue is **gated on H3 §4's re-link/rotation path
  and H9's cert issuance** — the re-issue flow renders the new key
  fingerprint for human approval before it activates, exactly like the
  signup link step (§5 screen 3). Destroy is two-step: an explicit
  "Destroy this box" confirmation screen (typed box name or a second
  rendering's confirm button) — a consequential action gets a
  consequential interaction.
- **Approvals** — the per-tenant pending/answered feed: the confirmd
  approvals UX the owner's phone already answers (two-tap, from
  `docs/FIRST_TEN_MINUTES_SPEC.md`). **Gated on H10/H11:** per-tenant
  queues and tenant attribution are the H10/H11 substrate; the dashboard
  renders the single-tenant feed only until that substrate exists, and
  never implies multi-box approval routing it doesn't have.
- **Usage** — metering panels (compute, approvals, suspend cycles).
  **Gated on H12** (metering hooks): no fabricated usage numbers, no
  estimated bars — the panel ships when the data source ships. The
  suspend-cycles meter carries the *same* gate as the Boxes panel's
  `suspended`/`waking` states — the H4 suspend/wake contract extensions
  (unshipped H4 work, gated on the operator spend-cap packet): until then
  the dashboard renders compute/approvals only and says nothing about
  suspend, mirroring the Boxes panel's "provisioning/live only" rule.
- **Explicitly not v1:** org-policy controls (**H16** — design/implementation
  open; the dashboard never promises centrally-governed policy before it
  ships), cross-tenant views (H11 audit pending), push-subscription
  management (H14 per-tenant scoping gated on H10/H11).

## 7. Endpoint surface (control plane, public set)

The control plane exposes exactly these public endpoints; everything else
is operator-side. The waitlist era needs only the first table; the signup
era (PR 2) adds the second. The GET-never-changes-state rule (§4.3)
applies to every signed-link endpoint in both tables.

### Waitlist era (PR 1)

| endpoint | method | notes |
|---|---|---|
| `/waitlist/form` | POST | path-B form intake; honeypot/time-trap; per-IP limit; validated rows only (§4.2) |
| `/waitlist/confirm` | GET / POST | GET renders, POST confirms; token as form field on POST (§4.3) |
| `/waitlist/forget` | GET / POST | signed forget-me link from every email footer; honored ≤7d with confirmation sent (`WAITLIST_OPERATIONS.md` §5, PR #68). GET renders only — **never changes state**; POST performs the deletion. See below. |
| `/go/selfhost` | GET | first-party redirect to the repo README's Try-it section, `src=selfhost` counted in our log (§4.1) |

**`/waitlist/forget` GET/POST split** (the §4.3 pattern, with the same
mail-scanner threat model — a scanner fetching the forget link must not
delete data): this **supersedes** `WAITLIST_OPERATIONS.md` §5's
"one-click forget link" wording — the link renders a forget-confirmation
page on GET and deletes on POST. GET renders the page with the masked owner
line (same first-3-chars rule as §4.3), a plain "this deletes your waitlist
entry" line, and a confirm button; POST performs the deletion and renders
"forgotten"; a re-click after deletion renders the already-forgotten
rendering verbatim. No state change on GET.

**Not exposed:** no unauthenticated position lookup (enumeration oracle —
`WAITLIST_OPERATIONS.md` §6, PR #68); queue position is disclosed only
inside signed emails. The store is never writable from the public
internet.

### Signup era (PR 2)

| endpoint | method | notes |
|---|---|---|
| `/signup/claim` | GET / POST | signed invite link. GET renders the claim screen (pre-filled owner email from the waitlist entry, plan/card summary) — never changes state, so a scanner fetching the link cannot claim anything. POST performs the claim: token as form field, idempotent, emits the `claimed` event (`FUNNEL_MEASUREMENT.md` §3.4, PR #99) with `ref` = the waitlist row id, creates the tenant shell, proceeds to §5 screen 1. |
| `/signup/magic` | GET / POST | magic-link callback (screen 1). GET renders a "Continue as `<owner>`" button page — never changes state (the mail-scanner threat: a scanner must not consume the single-use token). POST consumes the token, opens the magic-link session, proceeds to screen 2. |
| `/tenant/status` | GET | H3 §5: the Muse polls with its linked (approved) ed25519 key, signing requests per H3 §4; the signup page polls the same endpoint. Auth: human side = the magic-link session cookie (the status page meta-refreshes inside it); Muse side = its linked key (m2m). Renders the §6 status mapping (`provisioning` / `live`, later `suspended` / `waking`), never the raw H3 enum without the mapping. |

## 8. Phased build plan

1. **PR 1 — the waitlist page build** (surface 1, §4): static page on
   Pages per §4.1 (copy from `LANDING_PAGE_COPY.md` §3, tags from
   `FUNNEL_MEASUREMENT.md` §5 — PR #99), the form endpoint + path-A
   parser + confirm sender/token signer + reminder/drop jobs + invite
   sender + forget-me handler (all per `WAITLIST_OPERATIONS.md` §§2/4–7 —
   PR #68), the §4.3 confirm page on the control plane, the §7 waitlist-era
   endpoint surface (the §7 signup-era table lands with PR 2),
   `scripts/funnel_metrics.py` + the §7 query pack
   (`FUNNEL_MEASUREMENT.md` §7 — PR #99). Closes the
   `WAITLIST_OPERATIONS.md` §10 checklist (PR #68) and the
   `FUNNEL_MEASUREMENT.md` §9 follow-up (PR #99). The page ships only
   when the checklist is green — the dead-form rule.
2. **PR 2 — signup UI** (surface 2, §5): gated on the operator packet
   (§10). Account + magic link, plan + card, enrollment token + pending-key
   approval UI, BYO-tailnet step, status polling, connection bundle.
3. **PR 3 — dashboard v1** (surface 3, §6): account + boxes + the
   single-tenant approvals feed; usage + multi-tenant panels land with
   their H10/H11/H12 substrates.

Each PR ships its own honesty re-verification (`LANDING_PAGE_COPY.md` §5
checklist, re-run at build time — docs drift).

## 9. Honesty compliance notes

- `POSITIONING.md` anti-claims hold on every surface: no
  persistence-uniqueness claim, the sentinel is never presented as shipped
  (named as future or not at all — the §3 hosting line is infra-spec, not
  customer copy), no hosted
  pricing/tiers/free-tier wording anywhere — including the dashboard's
  plan panel (tiers land with the launch; until then the panel shows the
  decided shape, not numbers).
- The waitlist-era page never links surface 2 or 3; the signup UI never
  promises the dashboard; the dashboard never promises org policy,
  suspend/wake, or usage data before their substrates ship (§6 gates).
- The no-trackers claim stays scoped to the page (`FUNNEL_MEASUREMENT.md`
  §8, PR #99): "no third-party trackers, no cookies, no IPs retained in
  the metrics store" — never "anonymous," never "we collect nothing."
- No launch dates anywhere, including "soon"
  (`WAITLIST_OPERATIONS.md` §11, PR #68). The invite *is* the launch for
  that reader.
- "No card required for the waitlist" ≠ "no card required ever" — the
  confirm email says the first; the invite email and the signup UI say
  the second (card on file at signup, Billing decision).

## 10. Operator packet (preconditions, not loop work)

Surface 1 needs: the AgentMail waitlist inbox provisioned (operator,
`WAITLIST_OPERATIONS.md` §10 — PR #68), the operator-held HMAC/token and
metrics secrets (never in the repo), and the Pages↔Fly deployment itself.
Surfaces 2–3 need: the control-plane Fly machine + sparkvm.dev front door
live, the billing provider chosen, and the H4 driver's spend-cap packet
(NEEDS_USER.md). The beta-Muse pilot cohort (R7) stays the separate
operator item it is.

## 11. Follow-ups (not this run)

- Demo-assets plan asset 3 (the persistence pair PNG — `assets/README.md`):
  the OG image build produces it; reuse, don't reshoot
  (`FUNNEL_MEASUREMENT.md` §5, PR #99).
- A/B candidates (`LANDING_PAGE_COPY.md` §7) become testable after 4 weeks
  of baseline primary traffic (`FUNNEL_MEASUREMENT.md` §9, PR #99).
- The H3 §11 open questions the signup UI inherits (re-verify the list at
  PR-2 build time — tailnet shape is now decided, the rest may have moved).
- H16 org-policy and H12 metering panels land with their substrates (§6).
