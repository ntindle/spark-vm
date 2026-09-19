# Funnel measurement plan

**Status: design spec, not the implementation.** This doc makes the three
open follow-ups from the funnel specs concrete and decided, so the page and
the waitlist stop carrying "TBD" on their primary metric:

1. The **privacy-respecting analytics choice** that unblocks the primary
   metric — `LANDING_PAGE_COPY.md` §7 follow-up ("the analytics must match
   the trust story"); `WAITLIST_OPERATIONS.md` §10 checklist item ("Metrics
   wiring: privacy-respecting analytics chosen; interim confirm-rate
   reporting until then").
2. The **GET-vs-POST confirm decision** — `WAITLIST_OPERATIONS.md`
   follow-up from adversarial review (link-prefetcher risk on the confirm
   link).
3. The **OG/social tags spec** — `LANDING_PAGE_COPY.md` §7 follow-up.

**Dependencies:** citations of `docs/LANDING_PAGE_COPY.md` refer to open PR
#61; citations of `docs/WAITLIST_OPERATIONS.md` refer to open PR #68.
Re-verify section numbers when those merge. Merge order: #61 → #68 → this.

**Non-overlap map (what this doc is not):**
- Metric *definitions* (what the primary/secondary/anti-metrics are) are
  `LANDING_PAGE_COPY.md` §6 and `WAITLIST_OPERATIONS.md` §9 — this doc
  *wires* them, never restates or redefines them.
- The confirm token mechanics (HMAC, single-use, 14d expiry, idempotent
  re-click, rate limits, +7d reminder, 14d drop) are
  `WAITLIST_OPERATIONS.md` §4 (retention rules §5; build checklist §10) —
  this doc decides only the HTTP method shape around them, and **supersedes
  §4's "Confirmation is a GET on a signed link"**: the link now renders a
  confirm page on GET and confirms on POST (§4). An implementer reading #68
  alone would otherwise build the scanner-vulnerable flow. (Note for #61's
  typeset pass: `LANDING_PAGE_COPY.md` §4's "reply-to-confirm email with a
  single link" is *refined* by this, not contradicted — the single link
  stays; it opens the confirm page.)
- The page's copy blocks, section order, and honesty rules are
  `LANDING_PAGE_COPY.md` — this doc adds only the `<head>` tags and the
  analytics contract the page must satisfy.
- Positioning one-liners and anti-claims are `docs/POSITIONING.md` — the
  spec below stays inside them (see §8).

## 1. The gap this closes

The landing-page spec defines a primary metric — waitlist-confirmed rate =
confirmed signups / unique page visitors — whose denominator has no
measurement instrument: no analytics choice, no visitor-counting rule, no
event schema. `WAITLIST_OPERATIONS.md` §9 holds the primary ("the primary
is **held**") and substitutes the interim confirm rate, which is a
funnel-health number, not the page-conversion number the page was designed
to optimize. Every day the page ships without this wiring, the only
conversion signal is the interim — and the interim answers a different
question (did the email work) than the primary (did the page work).

The confirm link has a second, subtler gap: a GET link that confirms on
click is a state-changing GET. Mail scanners, link-preview bots, and
corporate URL sandboxes fetch links before the human clicks. If a scanner's
fetch consumes the token, the human's click lands on "you're already
confirmed" — or worse, a scanner *confirms* a stranger's entry it never
should have touched. The follow-up named this "GET-vs-POST confirm
decision"; it is decided in §4.

## 2. Requirements

Any analytics choice must satisfy all four:

1. **No third-party trackers.** The trust story is the brand ("A powerful
   agent, never trusted with the raw materials" — `POSITIONING.md`). A
   Google/Meta pixel on the signup funnel would be the product's first
   public contradiction. This is non-negotiable.
2. **Measures the defined metrics, nothing more.** The defined metrics need:
   unique visitors (primary denominator), CTA clicks per section (secondary),
   and the email-cadence events this doc defines for the §9 metrics.
   Time-on-page, scroll depth, and session replay are explicitly
   anti-metrics — the instrument must not produce them as a side effect.
3. **Cookie-free.** No consent banner, no cookie persistence, nothing to
   audit for cookie law. The instrument works without storing anything on
   the visitor's machine.
4. **Owner-operated, auditable.** The data lives in our logs, computed by
   our scripts, readable by anyone who can read the log format. No
   vendor dashboard whose aggregation we cannot verify.

## 3. Decision: server-side, log-derived, first-party

**Chosen:** count visitors and CTA clicks from the page server's own access
log, with a daily-rotated salt for uniqueness. No client-side JavaScript
analytics at all.

### 3.1 Unique-visitor counting (the primary denominator)

- For each page hit, the build's metrics script computes
  `bucket = HMAC_SHA256(day_salt, client_ip + "|" + user_agent_family)` —
  where `user_agent_family` is a coarse bucket (e.g. `curl-like`,
  `browser`, `bot`) rather than the raw string, so the hash cannot be
  re-identified from the log later.
- `day_salt` rotates every 24h (UTC) and **previous salts are discarded**.
  The metric needs *unique per day*, not *same person across days* — a
  stale salt is a tracking asset, and we delete the asset daily.
- Unique visitors for day D = distinct buckets in D's log window. The
  primary metric for a campaign window = confirmed signups whose
  `submitted_at` falls in the window / unique visitors in the window.
- **One exclusion, load-bearing:** requests classifying as bot/crawler are
  *not* counted in `page_view_day`. The page's whole purpose is to be
  shared, so every share brings Slackbot, Twitterbot, Applebot, Googlebot
  hits — a denominator that counts crawlers inflates exactly when the page
  succeeds. Crawlers roll up separately as `crawler_hits` (a share-signal
  for the operator), never in the primary denominator.
- **Salt mechanism, named.** The salt is date-derived, not stored:
  `day_salt = HMAC_SHA256(operator_secret, date)` where `operator_secret`
  is an operator-held secret that is never committed and never leaves the
  metrics script's host. There is nothing to "discard" daily — and nothing
  to leak. Cross-day joins are impossible by construction, because the day
  keys can't be recomputed without the secret.
- **Per-day double counting, named.** A visitor present on two days counts
  twice across a multi-day window (the sum of daily distincts). That is
  accepted, not fixed later — "fixing" it into a cross-day join would need
  retained salts, which the mechanism above forbids.
- **Privacy ceiling, stated plainly:** this still fingerprints coarsely
  (IP + UA family per day). The script hashes at parse time and keeps no IP
  in the metrics store — but the server's raw access log retains IPs per
  the server's log-retention policy, which the page-build runbook states
  explicitly. The honest claim is "we count visitors without cookies,
  third parties, or retained IPs *in the metrics store*," not "we collect
  nothing." (See §8.)

### 3.2 CTA click-through per section (the secondary metric)

- Each waitlist CTA on the page links to a distinct first-party URL whose
  path or query identifies the section: e.g. `/waitlist?src=hero`,
  `?src=trust`, `?src=faq`, `?src=final` (the final-CTA block —
  `LANDING_PAGE_COPY.md` §2's section 7 gets its own bucket, not folded
  into `hero`), `?src=selfhost`.
- Clicks are counted in the access log — no JS, no redirect service.
- The self-host CTA is a **first-party redirect** (`/go/selfhost?src=selfhost`
  → the repo URL), counted in our log. Appending `?src=` to the bare
  GitHub URL would put the param on a third-party domain and break the
  "src= stays on our domain" rule; the redirect also keeps shared/bookmarked
  URLs tidy. The reader who converts to the repo instead of the waitlist is
  still a win, counted separately per §6's rule.
- No UTM-to-third-party chains: `src=` stays on our domain.

### 3.3 Rejected options

- **Third-party JS (GA, Meta pixel, etc.):** fails requirement 1 outright
  and requirement 3 (consent banner on a trust-brand page).
- **Self-hosted Plausible/Matomo:** cookieless and first-party, but still
  a JS beacon the page doesn't otherwise need, and a whole service to
  operate for two numbers we can derive from logs we already keep. The
  page's analytics need is *below* the threshold where a product is
  justified. Revisit only if the funnel grows a second measurable surface
  (e.g. the H15 signup UI) whose events the log can't see.
- **No analytics until "later":** deferring measurement —
  `WAITLIST_OPERATIONS.md` §9's warning — leaves the interim confirm rate
  as the only conversion signal, and it answers a different question (did
  the email work) than the primary (did the page work). The log-derived
  approach costs one parsing script; ship it with the page.

### 3.4 What the H15 build logs (event schema)

The waitlist store's event trail (the operator-side store,
`WAITLIST_OPERATIONS.md` §5, plus the daily page rollups) gains one table —
`funnel_events` — with exactly these events, each a
`(event, at, ref, attrs)` 4-tuple where `ref` is the waitlist row id or the
day-bucket and `attrs` is a small key-value map:

| event | emitted when | ref | attrs |
|---|---|---|---|
| `page_view_day` | daily rollup from the access log | day-bucket | — |
| `crawler_hits` | daily rollup of bot-classified hits | day-bucket | — |
| `cta_click` | access-log rollup | day-bucket | `src` |
| `waitlist_submitted` | parser writes a validated row (`WAITLIST_OPERATIONS.md` §2, paths A/B) | row id | `path` = `email` (A) or `form` (B); `inbound_auth` = DMARC alignment of the submitting message (`true`/`false` for path A; absent for path B, which has no message to authenticate) |
| `confirm_sent` | confirm email leaves the sender | row id | — |
| `confirmed` | the POST confirm lands (see §4) | row id | `via`: `original` or `reminder` |
| `reminder_sent` | +7d job fires | row id | — |
| `invite_sent` | wave invite leaves | row id | — |
| `claimed` | invite claim completes | row id | — |

The §9 metrics are pure queries over this table plus the daily page
rollups — no other instrumentation is permitted. The day-1 operator query
pack ships with the page build (§7).

## 4. GET-vs-POST confirm decision

**Decision: GET renders, POST confirms. A GET request must never change
waitlist state.**

### 4.1 The threat

The confirm email's link is fetched by things that are not the human:

- Link-preview unfurlers (some messaging clients prefetch on paste).
- Corporate email gateways and AV sandboxes that GET every URL in inbound
  mail.
- Apple Mail / Gmail proxying (image proxies don't fetch HTML links, but
  gateway sandboxes do).

If GET confirmed, three failure modes follow: (a) a scanner *consumes* the
token, so the human's real click hits "already confirmed" — confusing but
recoverable; (b) a scanner confirms an entry whose human never consented —
the FIFO queue gains a phantom that will waste an invite; (c) repeated
scanner fetches become a signal the operator can't distinguish from
human interest. The idempotent re-click `WAITLIST_OPERATIONS.md` §4 specifies
("you're already confirmed") softens (a) but does not fix (b).

### 4.2 The shape

- `GET /waitlist/confirm?token=<hmac>` renders a small page: "Confirm your
  spot — you're joining as `<masked>`" plus one button, "Yes, hold my
  place." **No state change on GET.** `<masked>` is the first 3 characters
  of the owner's local part plus "…" (e.g. `spa…`) — never the full local
  part, never the domain. The confirm page submits via plain form POST, so
  confirmation needs no JavaScript.
- `POST /waitlist/confirm` with the token (form field, not query string)
  performs the confirmation: marks the row confirmed, emits the
  `confirmed` event with `via` = `original` or `reminder` (§3.4).
  Idempotent re-POST returns the already-confirmed rendering (§4.3).
- The confirm page carries `Referrer-Policy: no-referrer` and
  `X-Robots-Tag: noindex, nofollow`, and ships **no OG or Twitter tags** —
  §4.1's threat model says scanners and unfurlers fetch this page, and
  pasting the link into Slack/Discord/Signal must not embed the owner's
  address (masked or not) in a shared preview. Nothing on this page is
  cacheable as preview metadata.
- HEAD/OPTIONS on the confirm path return 200/405 with no side effects;
  scanners that only probe get nothing consumable.
- The `+7d` reminder email re-sends the same link shape (GET page, POST
  button) — one link shape everywhere, no "this time it's different."

### 4.3 Confirm page states

The doc decides the HTTP shape but the page itself has four states — each
gets defined copy, no implementer improvisation:

- **Valid, pending (the happy path):** the button page from §4.2, plus one
  line echoing the page-disclosed 14-day claim window (`WAITLIST_OPERATIONS.md`
  §10): "Invites go out in waitlist order — each invite holds for 14 days."
- **Already confirmed** (GET on a consumed token, or re-POST): no button.
  "You're on the list — invites go out in waitlist order. Watch your
  inbox." This is the idempotent re-click `WAITLIST_OPERATIONS.md` §4
  specifies; the supersession changes only the method — a re-click is never
  an error, and the rendering above is this doc's defined copy for the
  confirm page.
- **POST success (fresh confirmation):** the conversion payoff gets the
  same treatment as already-confirmed, verbatim — one rendering for
  "confirmed," two entry paths.
- **Expired or invalid token:** "This link expired — waitlist links last
  14 days." plus a rejoin link back to `/waitlist`. The +7d reminder
  recipient who clicks the *first* email's link after day 14 walks straight
  into this state; it must read as a rule, not an error.

### 4.4 Non-goals

This does not defend against a human forwarding their link (the token is a
bearer credential for one row — forwarding delegates the confirmation, a
known and accepted property) or against the confirm *page* being fetched by
a scanner (it contains no state-changing affordance for a fetcher, and §4.2
strips its preview metadata).

## 5. OG/social tags spec

When the page ships, its `<head>` carries exactly this tag set — trust
story included in the description, no tracking pixels, no third-party
image hosts:

```html
<meta property="og:url" content="https://<host>/" />
<meta name="description" content="A persistent computer for your AI agent: files, jobs, and desktop still there tomorrow." />
<meta property="og:type" content="website" />
<meta property="og:title" content="spark-vm — a real computer that stays yours" />
<meta property="og:description" content="A persistent computer for your AI agent: files, jobs, and desktop still there tomorrow. No third-party trackers on this page." />
<meta property="og:image" content="https://<host>/assets/og-persistence-pair.png" />
<meta property="og:image:alt" content="The same desktop, today and tomorrow — nothing lost overnight." />
<meta name="twitter:card" content="summary_large_image" />
```

Rules for the build:

- `og:image` is the persistence pair from the demo-assets plan — **reuse,
  don't reshoot** (`LANDING_PAGE_COPY.md` §7). The verifiable location is
  `assets/README.md` (asset 3, currently a follow-up — the PNG does not
  exist in the repo yet). The filename `og-persistence-pair.png` is this
  doc's invention; the page build produces it. First-party hosted; the
  image URL must not carry query-string trackers.
- The `og:description` names the no-trackers property explicitly — scoped
  to *this page*, full stop. The card must not claim "anywhere in the
  product": the decided billing surface (card on file at signup,
  `PRICING_THINKING.md`) requires a payment processor, which is a
  third-party script on a future surface this doc does not govern. A
  product-wide claim needs its own decision doc; this one would be a lie
  the moment signup ships.
- No `fb:app_id`, no Twitter site tags pointing at accounts that don't
  exist yet. Add handles when they exist; don't pre-claim them.
- The page's canonical URL is absolute in `og:url`; no URL shorteners.

## 6. Unconfirmed-row manufacturing (the metrics nuisance, bounded)

`WAITLIST_OPERATIONS.md` §6's abuse model leaves unconfirmed rows cheap to
create (Path-A per-sender rate limit: 3/day, `WAITLIST_OPERATIONS.md` §6;
Path B's equivalent is the per-IP limit). A spray run manufactures rows that
inflate `confirm_sent` without ever confirming — depressing the interim
confirm rate and, at scale, the primary's numerator credibility. The
bounds:

- **The primary denominator never includes unconfirmed rows.** The primary
  is confirmed / unique visitors; manufactured rows touch neither side.
- **The interim confirm rate is reported split:** raw (confirmed /
  confirm_emails sent) and DMARC-aligned-sender-only, where the filter keys
  on `waitlist_submitted.attrs.inbound_auth` — the DMARC alignment of the
  submitting message (path-B rows carry no value and are excluded from the
  aligned split). A widening gap between the two is the spray
  signature, reported as its own line in the §7 query pack's split reports —
  never averaged away.
- Unconfirmed rows stay inert (`WAITLIST_OPERATIONS.md` §3/§5: they confirm
  nothing, unlock nothing, and the 14d drop still applies). Manufacturing them
  buys the attacker nothing but a row in a table nobody reads.

## 7. The day-1 operator query pack

With the page + waitlist live, the operator runs these weekly — all
derivable from `funnel_events` + the daily page rollups, no new
instrumentation:

- **Primary:** confirmed (submitted in window W) / unique visitors (W).
- **Secondary:** `cta_click` by `src` (hero vs trust vs FAQ vs final vs selfhost).
- **Confirm rate (interim, split):** confirmed / confirm_sent — raw and
  `inbound_auth`-aligned-only (path-B rows excluded from the aligned split).
- **Reminder lift:** `confirmed` with `via=reminder` / `reminder_sent` —
  computable because the event carries `via` (§3.4).
- **Invite→claim:** claimed / invite_sent, median hours invite→claim.
- **Submit→confirm latency:** median hours `waitlist_submitted`→`confirmed`.
- **Bridge (post-signup):** signups reaching H3 identity linking /
  confirmed waitlist entries — the waitlist→identity-linked drop-off,
  kept visible, never folded into the page metric.

The pack ships as one script (`scripts/funnel_metrics.py`, reading the
store + access-log rollups) in the page-build PR — metrics that need a
second PR to compute are metrics that never get computed. Status wording,
made exact: the `WAITLIST_OPERATIONS.md` §10 "Metrics wiring" item closes
*when the choice is made* (this doc); the interim confirm rate stays
*labeled* interim *until the page build wires it live*.

## 8. Honesty compliance notes

- `POSITIONING.md` anti-claims hold: no persistence-uniqueness claim, the
  sentinel is unnamed, no hosted pricing/tiers/free-tier wording anywhere
  in the measurement story.
- The analytics claim is the measured one: "no third-party trackers, no
  cookies, no IPs retained in the metrics store" (raw access logs retain
  IPs per the server's log-retention policy, stated in the page-build
  runbook — §3.1). Do not upgrade it to "anonymous" or "we collect
  nothing" — the day-bucket is a coarse fingerprint and the doc says so.
  The trust story survives scrutiny; marketing copy that overclaims
  doesn't.
- The primary metric stays the page's conversion number; the interim
  confirm rate is labeled interim in every report until the analytics
  choice is live — one number, one name, until the wiring exists.
- Anti-metrics stay anti: if the log-derived approach ever starts
  producing scroll-depth or session data as a side effect, that output is
  deleted, not dashboarded.

## 9. Follow-ups (not this run)

- Page build (H15-era): typeset the §5 tags, wire the `src=` CTA URLs,
  ship `scripts/funnel_metrics.py` with the page PR — the §10 "Metrics
  wiring" checklist item closes here, not in a follow-up.
- Bridge metric computation lands with signup; the waitlist→identity-linked
  drop-off query is defined now (§7) so signup's schema can emit into
  `funnel_events` from day one.
- Revisit the analytics product question (§3.3) only when a second
  measurable surface exists.
- A/B candidates (`LANDING_PAGE_COPY.md` §7) become testable once the
  primary has a baseline — no A/B before 4 weeks of baseline traffic.
