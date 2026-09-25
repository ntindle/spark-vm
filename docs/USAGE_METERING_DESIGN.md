# Usage metering design (H12)

**Status: design thinking, not a commitment.** Per `docs/POSITIONING.md`'s
anti-claims: the hosted product is not live, nothing here is published
pricing, and per-box price numbers in this doc are *cost-recovery inputs* for
an operator decision, not a price list. Claims stay on the self-hosted reality
until the hosted product exists. Gap classes (shared with
`APPROVALS_PLANE_GAP_ANALYSIS.md`): `[BUILD]` exists nowhere, build it;
`[HOSTED]` the single-user OSS substrate needs a tenant dimension for hosted;
`[DESIGN]` design exists, code does not; `[POLICY]` needs an operator
decision first.

**Why this doc.** Billing is downstream of metering: the hosted product cannot
charge for a box, cap spend, or detect abuse without a trusted record of what
each tenant used. H11 (multi-tenancy audit, PR #341) released this design by
defining the tenant key. This doc is H12's answer to "what data, keyed by
whom, flowing where" — the data source the pricing/billing decisions in
`docs/PRICING_THINKING.md` will need.

**Non-overlap map (what this doc is not):**
- The sentinel's telemetry census is `docs/SENTINEL_TELEMETRY_SURFACES.md`
  (the four audit surfaces, six structural findings). This doc consumes those
  surfaces as metering *sources* where they fit; it is not another census.
- Pricing thinking lives in `docs/PRICING_THINKING.md` (per-box, not per-seat;
  wall-clock as the pricing floor). This doc names the *meters*, not the
  *prices* — per-box-per-hour is a billing unit, not a dollar figure.
- The push-delivery service (H14 part a, `confirm/push.py`'s durable enqueue/retry
  `PushQueue`) is the delivery pattern this doc reuses for emission, not its
  subject. Free-tier suspend/wake (H13) is the primary *consumer* of the
  idle-heartbeat meter defined here.

## 1. Tenant dimension: H11's answer, applied

H11's audit released the H12 design gate with the tenant key: **BYO
per-tenant tailnet identity**. For metering this means:

- The metering event's `tenant` field is the tenant's tailnet identity
  (Tailscale LoginName / stable node identity) — the same attribution H10
  will put on approval/audit lines. No new tenant-id scheme: one identity,
  shared by approvals (H10), metering (this doc), and sentinel (H5).
- Per-tenant *box* (H11's isolation recommendation for mutually-untrusted
  tenants) makes metering attribution simple: on a per-tenant box, box-local
  meters need only one tenant key, assigned at provision time from the tenant
  record — the box is its own billable unit.

`[HOSTED]` until H10 lands: the S1/S2/S4 surfaces carry no tenant field today
(A7 in the H11 audit). The mappers in §4 must emit `tenant: unknown` until
H10 ships attribution — and the billing pipeline must treat `unknown` as
unbillable, not as billable-to-nobody. This is H10's scope; the mapping table
below just names the dependency.

## 2. Billable-unit taxonomy

Per-box pricing (`PRICING_THINKING.md`: "a computer for my agent", per-seat
only if one human pays for many Muses) needs wall-clock first and usage
counters second. Five meters, each with its source and its billing purpose:

| Meter | What it measures | Primary source | Purpose |
|-------|------------------|----------------|---------|
| `box_wall_clock` | Provisioned seconds, by lifecycle state (`active` / `suspended` / `waking` / `destroyed`) | Provider layer (H4 Fly driver; today: auto-deploy's S4 audit + provision records) | Base billing unit; free-tier suspend accounting (H13) |
| `resource_window` | Aggregate CPU-seconds, peak RSS, disk bytes-written per 5-minute window | Host agent scraping `/proc` + cgroup on the tenant box | Cost control, abuse detection, plan-fit guidance |
| `approval_volume` | Approvals filed / approved / refused / expired, per day | S1 confirmd audit.log, S2 swap.log refusal lines | "Swapd's per-decision audit lines are the raw material" — the §10 in that sentence is the signup doc's, quoted via PRICING_THINKING.md: usage reporting for the human buyer |
| `suspend_wake` | Suspend entries/exits + wake-on-dial events | Provider `suspended`/`waking` states (H4 contract extensions, unshipped) + box idle heartbeats | H13's idle-policy input; distinguishes paid idle from free suspended |
| `push_delivery` | Push notifications enqueued / delivered / failed-retry-exhausted, per day | H14 part a `PushQueue` records | Operational cost ledger (VAPID sends are not free at scale) |

What is **deliberately not metered**: request payloads, full URLs, secret
names and values, browser contents, anything the agent typed into a job. The
privacy rule (§5) is *counters over content* — a meter that needs content is a
metering design defect, not a pricing feature.

## 3. Canonical metering event envelope

`SENTINEL_TELEMETRY_SURFACES.md` finding A1 (filed as #353): the four audit
surfaces share no event envelope — logfmt vs JSONL, different field names for
the same concepts, event type sometimes encoded in field presence. The
sentinel's H5 design will need a canonical envelope; the metering pipeline
needs one first, so this doc defines it (shared adoption by H5 is intended —
one envelope, two consumers):

```json
{
  "v": 1,
  "seq": 42,
  "epoch": 7,
  "ts_ns": 1780000000000000000,
  "tenant": "user@github",
  "source": "swap_addon",
  "event": "swap_refused",
  "trust": "daemon",
  "attrs": {"host": "api.example.com", "aid": "a1b2c3"}
}
```

- `v`: envelope version. `seq`: per-source monotonic counter;
  `epoch`: source restart generation (process-local counters + restart epochs
  are the H5 prerequisite per the telemetry doc — cross-source global ordering
  is explicitly not required). Together they answer #354 (no sequencing) for
  the metering consumer: a gap in `seq` within an `epoch` is a detectable
  drop, not silence.
- `ts_ns`: nanosecond epoch. Supersedes the second-resolution collision (A3,
  #355) — the mapper stamps `ts_ns`; order within a burst is
  seq-then-timestamp, never timestamp alone.
- `source`: writer identity (`confirmd`, `swap_addon`, `muse_job`,
  `auto_deploy`, `meter_agent`, `provider`). `trust`: daemon /
  operator / cooperative — the explicit trust-tier label from A4 (#356).
  Rule, restated from the telemetry doc: **cooperative sources (muse-job)
  inform liveness dashboards, never billing or authorization decisions.**
  A meter that bills on cooperative telemetry is a billing-integrity defect.
- `attrs`: source-specific counters only — fields are allowlisted per event
  (§5). No free-form text from agent-influenced inputs (cf. #17's log-injection
  finding).
- `mac`: **reserved.** This envelope does NOT answer A2's authentication half
  (#354) or `APPROVALS_PLANE_GAP_ANALYSIS.md` §8's signed-shipping promise.
  A `mac` field (or authenticated transport) is a named extension point for
  the H5 design — it must adopt, not re-derive, this envelope — not a later
  redesign. One envelope, two consumers only works if the signing story
  lands here.

## 4. Source mappers (per-surface, not writer rewrites)

The telemetry doc's fix direction for A1 was per-surface mappers, not writer
rewrites — metering adopts it. Each mapper reads its surface and emits
metering-envelope events; the writers stay untouched:

- **S1 (confirmd audit.log)** → `approval_filed`, `approval_decided`
  (approved/denied/refused variants), `approval_expired`. Attribution today:
  none — `[HOSTED]` mapper emits `tenant: unknown` until H10 ships.
- **S2 (swap.log)** → `swap_performed`, `swap_refused`. `host` survives into
  attrs only if allowlisted (it is, by construction); the matched token is
  reduced to a *class* (`placeholder`, `approval-filed`, `authority-mismatch`),
  never the raw token. S2's field-presence type encoding stays inside the
  mapper — the envelope always carries an explicit `event` name.
- **S3 (muse-job JSONL)** → liveness only: `job_started`, `job_heartbeat`,
  `job_ended`. Trust tier `cooperative`: usable for idle detection and the
  human's activity view, **excluded** from anything that prices or bills.
- **S4 (auto-deploy audit)** → `deploy_completed`, `deploy_rolled_back`
  (the #374 rollback-block write is a source here: rolled-back commits are
  deployment events with billing consequences — a rollback does not stop the
  wall clock).
- **`meter_agent` (new, box-local)** → `resource_window` every 5 minutes,
  `idle_heartbeat` every 60 s when the box is idle. Small, privileged like
  the swap proxy's narrow writers: it reads `/proc` and writes the spool;
  it never sees secrets.
- **`provider`** → `box_state_transition` (`active` → `suspended` →
  `waking` → `active`, `destroyed`). `[HOSTED]` until the H4 driver ships
  the planned `suspended`/`waking` + async `dial()` contract extensions —
  no H4 driver PR exists yet, so today the wall clock cannot distinguish
  suspended from idle. The design does not fake the distinction.

## 5. Privacy: counters over content

1. **Counters only.** Metering attrs are counters, timestamps, and enum
   classes. The allowlist per event is part of the mapper spec; a field not
   on the allowlist is dropped, not logged-and-redacted.
2. **No secrets, no secret metadata beyond classes.** `hsurr:<name>` names
   are not emitted (they reveal which credentials a tenant uses); the swap
   token class is. A meter must be auditable without ever containing a
   credential.
3. **No agent content.** Prompts, shell commands, browser DOM, file contents,
   chat transcripts — never in a metering event. The idle heartbeat carries
   *that* the box is idle, not *what* it was doing.
4. **Tenant identity stays control-plane-side.** The `tenant` field travels
   with the event because billing needs it, but the events at rest on the
   tenant box are the tenant's own — on a per-tenant box provisioned per
   H11's isolation recommendation, no cross-tenant data ever sits in a
   tenant-visible spool.

## 6. Emission: a MeterQueue on the H14 part a pattern

H14 part a shipped `PushQueue`: durable enqueue, exponential-backoff retry, a
systemd worker, fail-open semantics (a queue failure never breaks the box).
The metering emission path copies the pattern, not the code:

- Box-local spool directory, per-event files, bounded size
  (**rotation bound required before any meter daemon ships** — the S1
  unbounded-growth lesson from #360 applies to metering too; see §8's filed
  issue).
- The worker ships envelopes to the control plane in batch windows (e.g.
  every 5 minutes or N events), authenticating as the tenant box
  (tailnet-identity auth — Tailscale node identity / `tailscale cert`
  identity headers, not X.509 mTLS; the mechanism choice is deferred —
  the same identity as the tenant key, so no second credential to manage).
- **Self-hosted: nothing ships.** With no control-plane endpoint
  configured, the `meter_agent` still spools locally under the #376
  rotation bound and the worker simply has nowhere to send — the meter
  data stays useful on a single box (the human's own cost view). The
  both-supported default holds; metering is not hosted-only.
- **Fail-open.** A full spool, a dead worker, or a control-plane outage never
  blocks the box, never fails a swap, never loses an approval. Metering that
  breaks the product is worse than a metering gap — gaps are detectable
  (`seq` discontinuities), breakage is not.
- Control-plane ingestion dedupes on `(source, epoch, seq)`; the sender is
  at-least-once by design.

## 7. Retention and the operator's open questions `[POLICY]`

- **Local spool:** bounded, rotated, sized for ~7 days of metering at worst
  case (the box is the cache, not the archive).
- **Control plane:** retention is an operator decision — billing needs
  (chargeback windows) vs minimization (a per-decision ledger is a behavioral
  record of the tenant's agent). This doc proposes, the operator disposes:
  raw envelopes 90 days, derived billing aggregates for the account lifetime,
  `tenant` → pseudonymized after the chargeback window closes.
- **Free tier:** suspend/wake accounting (H13) needs the `suspend_wake`
  meter; the free-tier boundary (what's free, what flips to paid) is the
  operator's call in `PRICING_THINKING.md`'s open questions.

## 8. Open gaps filed as issues this turn

- **#376** — metering spool rotation bound (§6): the meter daemon is not
  shippable without it (the #360 lesson).
- **#377** — idle-heartbeat semantics: what "idle" means for H13's detector
  (no traffic? no job? no browser?) — filed as H13 input.
- **#378** — mapper `tenant: unknown` quarantine policy: until H10 ships
  attribution, unbillable events must be quarantined from the billing
  aggregates, not silently dropped — a billing-integrity gap if the default
  ever drifts.

## Cross-reference provenance

- Tenant key: `docs/MULTI_TENANCY_AUDIT.md` (H11, PR #341).
- Telemetry surfaces + findings #353–#357, #360:
  `docs/SENTINEL_TELEMETRY_SURFACES.md`.
- Per-box pricing mental model: `docs/PRICING_THINKING.md`.
- Envelope/se sequencing prerequisite: `docs/APPROVALS_PLANE_GAP_ANALYSIS.md`
  §8 (signed/sequenced audit-log shipping).
- Emission pattern: `confirm/push.py` `PushQueue` (H14 part a).
- Consumers: H13 (free-tier suspend/wake), H5 (hosted sentinel), billing
  (operator).
