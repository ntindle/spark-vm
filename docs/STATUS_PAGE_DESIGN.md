# Status-page design (G22 S2/S3)

Doc-first; the honesty rule is the G17 S1 quoted rule carried forward by
`docs/STATUS_PAGE_FEED_SPEC.md` (the G22 S1 slice): the feed contract —
which journal records become rows, dedup/idempotency, the ack→resolve
lifecycle, what stays operator-only — already exists and is not
re-designed here. This doc is the S2/S3 slice of G22 (tracked on issue
#796): the page itself, staged, and the incident-comms question (#368) —
who tells the user, and in what words. It designs; it builds nothing.
Issue #796 stays open across all slices.

## 1. What the earlier designs already decide (bounds, not repeated)

- **Feed contract** (`docs/STATUS_PAGE_FEED_SPEC.md`): the status-page
  feed is a read-only, read-time-derived projection of the three fleet
  journals (events, alerts, inventory); no feed-local state; row keys are
  journal keys (`alert_id`, `(box_id, event_id)`); every row cites its
  journal source; freshness renders as `data_current_as_of`
  (per-journal, collector clocks); silence renders as "no journaled
  alerts in the window", never "all systems operational"; no synthesized
  availability. Ack is operator-declared and suppresses nothing but
  attention; resolved is journal-derived per rule and never auto-clears.
- **The page is the feed, not the pager.** Who pages the operator is
  G23's intake spec (`docs/ALERT_PUSH_FANOUT_SPEC.md`); a feed that goes
  un-read is a G23 gap, not a G22 bug. Ack stays in the operator CLI
  (`fleet events ack`) until a G21 console surface owns the mutation;
  there is no feed-side ack cache and no ack button through the page.
- **Tenant visibility gates on G24.** Until the tenant read path lands
  (tenant field on the stream + the tenant-scoped read), there are no
  tenant-visible rows, and the page says so; tenant rows prefer the G25
  signed feed, because a tenant disputing a row needs a tamper-evident
  record, not the operator's word (feed spec §8 Q2).
- **The H15 dashboard is owner-facing; the status page is
  tenant/public-facing** (the G21–G26 gap analysis). Separate surfaces —
  the dashboard never embeds the status page, though it may link to the
  tenant's history on it.
- **The tenant-status endpoint is a different question.**
  `docs/TENANT_STATUS_ENDPOINT.md`'s `GET /tenant/status` answers "where
  is my onboarding" (the 13 arc codes, per-tenant, credential-derived);
  the status page answers "what is happening to the fleet right now".
  The page never renders onboarding arc codes; the endpoint never
  renders incident rows. One reader may hold both, but the vocabularies
  never mix.

## 2. The page in one picture

Two stages, one feed contract:

- **S2a — the operator page.** Renders the collector journals (or the
  G21 read API when it exists) for the operator's own estate: the
  self-hosted N-box operator sees their own box ids — no surrogates
  needed; the hosted operator sees the estate. Operator-only rows per
  feed spec §6 (raw `detail`/`note`, raw box ids in the OSS sense,
  inventory facts).
- **S2b — the tenant-scoped history.** Renders the G24 tenant read path:
  a tenant sees their boxes' update history and the incidents that
  touch their tenancy — curated summaries, box-id surrogates, and
  nothing about anyone else. Until S2b lands there are no tenant-visible
  rows, and the page says so.

Both pages share the feed projection semantics (§1): derived at read
time, no local state, freshness stamp, silence-as-missing-evidence.

## 3. S2a — the operator page

Sections, in render order (each a projection of the feed rows):

1. **Firing alerts** — unacknowledged first, then acknowledged-but-
   unresolved (an acked alert that has not resolved stays listed; ack
   suppresses attention, not the row).
2. **Rollout rows** — the active rollout's envelope (`release_id`,
   `wave` from the event journal) or, honestly, "no active rollout";
   freeze flips from `kind: freeze-hold` events as "fleet frozen /
   freeze cleared at `<received_at>`". No per-wave census rows until
   G15 S2 lands (the page does not invent waves).
3. **History window** — resolved rows for the retention window (Q1),
   newest first, each citing the journal records that resolved it
   (the ack→resolve evidence pair).
4. **Freshness** — `data_current_as_of` per journal on every render.

Deployment shape: the S2a page renders from the collector journals
through the G21 read API's field-equivalence contract when it exists —
the feed spec's field set *is* the contract, not a second schema. For
air-gapped operators the same projection must remain producible from
the estate dir locally (the feed's read-time derivation makes this a
reader choice, not a second implementation). No new server component
ships in S2a beyond what the read API already owns.

## 4. S2b — tenant-scoped history

- **Gated on G24, not designed around its absence.** The tenant rows
  come from the tenant-scoped read path (`GET /tenant/update-history`
  as designed in `docs/UPDATE_AUDIT_RETENTION_AND_ACCESS.md`), whose
  privacy boundary this page inherits wholesale: *a tenant's history
  never names another tenant*.
- **Row transform, pinned now.** Tenant-visible rows are a curated
  transform of journal rows, never the rows themselves:
  - `detail`/`note` text is never passed through raw — the tenant
    reads a curated summary ("release X failed rollout on N boxes"),
    never the operator journal text;
  - box ids become the surrogate vocabulary the feed spec §6 deferred
    to this design: per-tenant affected-box counts or region/pool
    rollups, never raw box ids;
  - no ack affordances on tenant rows (feed spec §4: ack remains an
    operator action — a tenant-visible page shows acked state, never
    acks through the feed).
- **What the tenant sees.** Their boxes' update history, their
  tenant-attributed alert rows, and the fleet-notice variant of
  platform-wide rows (a fleet freeze, a correlated-failure row) *only
  when the row touches their tenancy*. There is no global fleet feed
  on the tenant surface — a public row set is a separate decision
  (feed spec §8 Q3), not an S2b default.
- **The signed feed.** Tenant-visible rows prefer the G25 signed feed
  when it exists; S2b does not invent a second trust story meanwhile
  (the feed spec §8 Q2 position stands until S2b's build argues
  otherwise).
- **History window.** The tenant history window is the retention window
  (G19's retention design), stated on the page — the page never shows
  more history than the journal keeps, and says how far back it reaches.

## 5. S3 — incident comms (#368): who tells the user, and in what words

This section answers #368's four questions against the design corpus.
Nothing in it re-litigates G23 (the pager) — the page, the RSS, and the
tenant push below are the feed's read surfaces; who pages the operator
is `docs/ALERT_PUSH_FANOUT_SPEC.md`'s intake.

- **What is the free incident channel?** Three layers, in ship order:
  1. **Interim: musebook #sparkvm** — decided 2026-09-24, stays until
     the real design ships. Interim posts follow the same public-row
     discipline as the RSS (fleet-wide rows only, no tenant attribution,
     no box ids) and the no-fiction contract (copy traceable to journaled
     rows).
  2. **$0 by construction: the RSS/Atom feed (public) + the S2a page
     (operator).** Both are renders of the *same* feed projection
     (journal-traceable rows, freshness stamp,
     silence-as-missing-evidence), published as a static render or a
     Workers cron-triggered render on the Cloudflare free tier. The RSS
     is the public free-tier incident channel — fleet-wide rows only,
     per the row-set rule below; the S2a page is the operator's incident
     surface (owner-authed when hosted, per Q4). There is no public HTML
     page in this design: a public page render of the fleet-wide
     projection is a named follow-up, not an implied deliverable.
  3. **The tenant push variant** — G23's S3 (gated on G24 and C4):
     when the H14 push plane's tenant subscriptions exist, tenant-
     visible incidents get a tenant-scoped page — curated summaries,
     surrogates, the G25 signed feed behind the rows. It is an S3
     channel that ships after and independent of the RSS.
  Email is deliberately **not** the free channel: there is no $0 mail
  provider in the posture, and inventing one breaks the cost ceiling.
  Tenants who want email-like integration get a user-configured
  **webhook** on the tenant surface (pointed at their own mailer) —
  the publisher pays nothing; whatever the webhook costs the user is
  the user's bill.
- **Who gets notified for BYO-box incidents vs hosted incidents?**
  BYO-box (self-hosted) incidents notify nobody but the box's
  operator: their own S2a page, their own `fleet events watch`. The
  plane never sees a BYO-box journal and must never be in the loop.
  Hosted incidents notify **only affected tenants** — tenant-scoped
  rows under the G24 privacy boundary. The public RSS carries
  **fleet-wide rows only** (firing rule-1/2 rows carry no tenant
  attribution in the journals, so they are publishable under the
  no-fiction contract) — never per-tenant attribution, never box ids.
- **Does the P7 ops turn feed this, or is it a separate
  control-plane path?** The P7 turn feeds the journals; the page, the
  RSS, and (later) the tenant push are consumers of the same feed
  projection — one contract, several renders. No separate control-
  plane incident path is designed or needed: the incident-comms lane
  is a read surface, not a new pipeline. (The one genuine separate
  path is operator paging — G23's intake, by design, not here.)
- **Cost ceiling.** Stays ~$0 at small fleet: the page and RSS ride the
  existing static/worker surface; the tenant push variant rides the
  H14 push sender already built (#1094 — claim/fanout/retry on the
  plane) rather than a new sender. No new infra line item is licensed
  by this design.
- **The words discipline.** Every channel inherits the no-fiction
  contract: incident copy is a render of journaled rows, never ahead
  of the journal. "We're investigating" is fiction unless an
  acknowledged row with a journaled note says so; a firing row with no
  resolution evidence stays firing on every channel, including the
  push copy. Curated summaries for tenants (S2b §4) reuse the same
  discipline — the summary may hide detail, it may never invent it.

## 6. Cross-lane ordering (no re-litigation)

- **G21:** the S2a page renders from the G21 read API when it exists;
  the read API's field-equivalence contract is the row contract. The
  console's auth story is the prerequisite the page honors, not a
  shortcut around (per the G23 intake spec §7).
- **G24/G25:** S2b's preconditions, named not designed — no second
  tenant-field invention here, no second trust story for the feed.
- **H15:** the owner dashboard and the status page are separate
  surfaces; the dashboard links to the tenant's status-page history,
  never embeds it.
- **#1136 (owner-level pending-approval aggregation):** approvals are
  not incidents — the status page never carries approval rows. The
  approvals surface owns pending views; the status page owns fleet
  truth.
- **G26:** the feed is not metering's source; no coupling.
- **#968 (owner push-subscription management):** the S3 webhook/push
  opt-in rides the #968 subscription surface when it lands — incident
  comms does not invent a second subscription store (Q3).

## 7. Open questions

- **Q1 — History window length.** The operator history window (§3.3)
  and the tenant window (§4) default to the retention window, but is
  one window enough for both? Incident post-mortems may want longer
  than the 30-day-style retention G19 keeps; if so, the retention
  design re-scopes, not this page. Argue with evidence on #796.
- **Q2 — The public RSS row set.** Fleet-wide rows only — but is a
  correlated-failure row on a single tenant's boxes publishable when
  every correlated box is one tenant's? This design's position: yes,
  in the fleet-notice variant (surrogate box counts, no attribution,
  no box ids) — the journals carry no tenant attribution on those
  rows today, so nothing leaks. Argue the other way on #796 with a
  concrete leak scenario.
- **Q3 — Webhook/push opt-in surface.** Rides #968's subscription
  surface per §6, or is incident comms distinct enough (fleet-level
  vs approval-level) to warrant its own opt-in? This design says
  ride #968; the S3 build owns the contrary argument.
- **Q4 — S2a hosted-operator auth.** The hosted operator page rides
  the control-plane owner auth (#843) when it ships hosted; the
  self-hosted S2a is local files. The auth wiring is an S2a build
  decision, not this doc's.

## 8. Build slices (for the feature/distribution track, not this doc)

- **S2 — the page.** Issue #796 stays open across both stages.
  - **S2a — the operator page.** Render from the collector journals /
    G21 read API: firing alerts (ack-attention split per §3), rollout
    and freeze rows, history window, freshness stamp. Ack stays CLI.
    Exit criteria: every row cites its journal source; the empty
    window renders "no journaled alerts", never a green banner.
  - **S2b — tenant-scoped history.** On the G24 read path: curated
    summaries, box-id surrogates, tenant privacy boundary, G25
    signed-feed preference. "No tenant-visible rows until G24" is
    the gate — the page says so and means it.
- **S3 — incident comms (#368).** Interim musebook #sparkvm; the
  RSS render path (same projection, free-tier posture; public rows
  only) — the S2a page remains the operator surface; tenant push
  variant via G23's S3 when gated; webhook opt-in riding #968. Exit
  criteria: the $0 posture holds at small fleet; every channel's copy
  is traceable to journaled rows; no journal/telemetry path from a
  BYO box to the plane is created by this slice.
