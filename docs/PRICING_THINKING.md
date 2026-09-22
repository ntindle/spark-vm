# Pricing thinking — hosted spark-vm

**Status: design thinking, not a commitment.** This is the internal pricing
analysis the sales/funnel backlog item ("pricing page thinking") asked for.
It is **not** published pricing, not a price list, and must never be quoted
as a promise:
`docs/POSITIONING.md`'s anti-claims forbid promising hosted tiers, prices, or
launch terms before the idle/suspend economics are decided. **Decided
2026-09-18 (owner): no free tier at launch** — launch is paid tiers plus
possibly a free trial that requires a card on file up front (the card is the
abuse control; see §3). The pricing *page* lands after the operator decides
the remaining NEEDS_USER.md items (Billing: trial terms + provider, Abuse
controls); this doc is what informs those decisions.

Strategy input feeding: R1 (first-10-minutes spec, done 2026-09-18),
R4 ("works immediately" onboarding shape), C2 (competitor pricing inputs),
C5 (idle economics), C8 (buyer-vs-user packaging),
signup design §11 open questions. Sources for every number:
`docs/COMPETITOR_ANALYSIS.md` (surveyed 2026-09-18; AgentComputer and DIY
figures are third-party claims, flagged where used), re-verified against
the competitor watch corpus (latest full re-read 2026-09-21; watch docs
under `docs/COMPETITOR_WATCH_*.md` plus the C19/C20 Brig+Epho consolidation).

**Freshness (2026-09-22):** all cited strategy docs are merged to `main`;
cross-references point at the main versions. Price inputs re-checked
through the 2026-09-21 watch reads — TermSquad tiers unchanged, boat.dev
rate card unchanged, Epho added as a pricing-shape data point (C24). The
tier anchors below are TermSquad-pegged (the $9 visible floor), not
provider-costed, so none of the in-window deltas — boat.dev's $20 plan
sits *above* the Tier-1 $9–19 band — move them.

## 1. Who actually pays (C8: buyer ≠ user)

This is the packaging decision everything else hangs on:

| | User | Buyer |
|---|---|---|
| Who | The Muse — it signs up alone, links identity, runs the box | A human or org — the Muse's owner, approver, budget holder |
| What they value | A computer that stays mine; approvals keep me safe; zero human-credential steps | Cost control; audit trail of what the agent did; no surprise bills |
| Trust evidence each gate needs | Works in 10 minutes; the approval loop aha moment | Audit log of agent actions (signup doc §10); SOC 2 path for orgs; per-box spend caps; kill switch |

Consequences for packaging:

- **Per-box, not per-seat.** The human buyer's mental model is "a computer for
  my agent" — per-box pricing maps 1:1 to the thing they get. Per-seat makes
  sense only if one human pays for many Muses, and then the right unit is still
  "box N," not "seat." (Multiple Muses sharing one box is this doc's own
  extension — the signup doc binds tenant↔Muse 1:1 in §4 and never discusses
  sharing; treat the sharing question as identity/approvals, not pricing.)
- **The conversion trigger is buyer-facing evidence, not user-facing features.**
  The Muse converts when the first-10-minutes aha lands (research Finding 6's
  aha-in-minute-ten framing, signup doc §8); the human converts when they can
  *see* what the agent did and *bound* what it can spend. The pricing page must
  carry both halves: the agent's story
  ("a real computer that stays yours") and the buyer's story ("you see every
  approval, you cap the spend, you can kill it").
- **Cost controls are a feature the paid tier sells.** A per-box monthly cap /
  alerts / kill switch is what lets an org buy the thing without a procurement
  fight. Swapd's per-decision audit lines (§10) are the raw material; the
  pricing page promises the *controls*, not the mechanism.
- **Compliance is out of pricing scope for now.** C8 lists a SOC 2 path as a
  gate-evidence item for orgs — that's a trust roadmap (enterprise tier, later),
  not a tier in this thinking. The tiers here are priced for the Muse-user /
  human-buyer pair, not for procurement departments.

## 2. Cost floor (C2)

What the market charges for persistent computers (Sep 2026):

| Offering | Price signal | Notes |
|---|---|---|
| TermSquad | $9–$49/mo (2–8 vCPU, 4–24 GB, 40–200 GB NVMe) | Always-on, includes Squad orchestration + backups |
| AgentComputer | $20/mo (third-party claim, unconfirmed) | Persistent Ubuntu VM, 25 GB disk |
| E2B Pro | $150/mo floor + usage | Task-scoped; one continuous 2vCPU box ≈ $78/mo usage — a task-scoped unit price for an always-on box |
| DIY floor (third-party guide) | $5.70/mo droplet + human labor | The "human does everything" alternative |
| Fly Sprites | $0.07/CPU-hr active | Hibernates when idle — closest to our trial/idle-economics shape |
| boat.dev | $20/mo plan = 555 h of `default` (4 vCPU / 8 GB / 50 GB, $0.036/h); stopped = $0 | Task-scoped, per-second; cheapest viable provider candidate (C17, verified 2026-09-21) |

Reading the floor: a hosted persistent box cannot price below its wall-clock
provider cost plus operations margin. TermSquad's $9 starter (2vCPU/4GB/40GB)
sets the visible floor for "always-on computer for your agent." The DIY $5.70
is the anchor the OSS self-host story already wins against — hosted has to
earn its premium with *zero* setup, not with raw compute.

Shape note (C20/C24 — Epho, verified https://epho.io 2026-09-22):
bring-your-own-keys infra-only metering — model tokens are billed by the
user's provider, never by Epho — carries zero model-token margin risk for the
operator. The hosted box needs the agent's model access; billing tokens
through us would put unbounded model spend inside a flat tier. BYOK is a
candidate shape for that answer: it keeps model spend out of our margin
entirely. Undecided — recorded here as a pricing-shape data point, not a
decision.

GPU is priced separately everywhere (Daytona H100 $2.27/hr; Modal GPU inside
sandbox at 3x rate). We have no GPU story today (C6 = the competitor-pass item
asking for an explicit GPU criterion in the Neo provider choice) — the tiers
below are
CPU-only; GPU, if ever, is a metered add-on, never bundled into the flat
tier (it would blow up the flat tier's margin). Metered GPU does not violate the
no-surprises principle below: it's opt-in per run with an explicit price
shown before the run starts, not ambient metering on the box.

## 3. Tier design thinking

### Trial + paid tiers (R4 + C5)

**Decided 2026-09-18 (owner): no free tier at launch.** A free tier invites
crypto-mining abuse on the exact hardware the trust story is built on, and
fighting that is not launch work. Instead: paid tiers at launch, plus
possibly a **free trial that requires a card on file up front** — the card
is the abuse control (spam VMs don't pay). This is decided *direction*,
not committed detail: trial length, verification mechanics, and
trial→paid conversion are all TBD.

What survives the free-tier cut:

1. **"Works immediately" (R4):** the trial still needs zero human-credential
   steps after the key approval — the signup design's fingerprint-approval
   is the last human touchpoint *before the box provisions*. The human still
   installs the first secret in the first session (signup doc §8, step 3 —
   the designed manual step, a separate trust-depth metric because it needs
   a human SSH-tunnel step). Closing that gap is R4's work, not a solved
   problem.
2. **Idle economics (C5):** "no session clock" stays a *paid-tier* property.
   (A *session clock* is any limit on how long the box stays awake running
   workloads.) With no free tier, suspend-to-disk / wake-on-SSH-dial stops
   being the defining tier line and becomes a cost-control detail for the
   trial shape (TBD) — the paid line is simply "your computer never sleeps."
   Definitions kept for that work:
   - **Idle = no human-originated session *and* no *registered* scheduled
     workload activity for N days.** Background cron loops (the improvement
     loop itself) are the headline workload — "activity" must be defined
     against them, not around them.
   - Cron jobs do not fire while suspended; wake-on-schedule is a session
     clock by another name and belongs on paid.
3. **Abuse (§11.7):** card-on-file at trial signup is the decided direction.
   Rate limits + identity-verification level beyond the card remain open
   (see NEEDS_USER.md Abuse item). The signup design's baseline is email +
   magic link for the human account — and its §11.7 warns that email-only
   invites spam VMs; the card requirement is the answer to that warning,
   not an addition to it.

Proposed shape (thinking, not committed): paid tiers only at launch.
Trial (if any): time-boxed, card on file up front as the abuse control,
"works immediately" onboarding kept as the conversion lever; trial terms —
length, compute, whether idle boxes suspend, wake path — all TBD. Paid
tiers: per-box, always-on, no session clock (Tier 1 ~TermSquad-starter
parity, Tier 2 workhorse — see below). What converts off the trial: the
session-clock difference ("your cron jobs only run while the trial is
alive" → paid "no session clock"), and disk/compute upgrades — never the
persistence itself. Disk persists across suspend (persistence is the
headline — losing the box would contradict the entire positioning).
Suspend loses *uptime*, never *files*.

### Paid tiers

- **Tier 1 — the always-on box:** flat monthly, ~TermSquad-starter-parity
  compute, no session clock, registered cron workloads run 24/7. This is the
  core product: "your computer never sleeps." Price anchor: $9–$19 band.
- **Tier 2 — the workhorse:** more vCPU/RAM/disk for heavier agents
  (browser driving, builds, Blender renders). Price anchor: $29–$49 band,
  matching TermSquad's Power/Ultra spread.
- **Every paid tier must ship the buyer story to sell it:** per-box spend cap,
  audit-log access (approval decisions + swapd lines), kill switch, cost
  alerts. These are not add-ons; they are why a human approves the purchase.
  (Future-state until built — see §5's honesty rule. Note: on flat monthly
  tiers there is no variable spend to cap — the spend cap only bites on the
  metered GPU add-on and any future usage add-ons, so don't oversell it.)
- **What we do NOT do:** per-second metering (that's the task-scoped
  segment's game; our headline is the opposite), GPU bundling, per-seat
  pricing, or usage credits that surprise the buyer.

### Stopped/cold retention tier (C15)

The competitive gap the live-control deep scan named: this thinking had
no stopped-state cost story at all — while the task-scoped products
publish explicit stopped-state pricing (AgentComputer's cold rate, E2B's
running-only billing) and TermSquad answers with flat $9/mo always-on
and no stopped story whatsoever. The market anchors below, each labeled
with its actual source and evidence grade (the deep scan's
VERIFIED/INFERRED discipline; Fly Machines from the suspend/wake
research):

- **AgentComputer** (VERIFIED, deep scan) publishes two storage rates: hot
  $0.000683/GB-hour for running computers, **cold $0.000027/GB-hour for
  stopped** — file operations keep working on stopped computers without
  accruing runtime.
- **E2B** (VERIFIED, deep scan) bills per second of *running* sandbox time
  only; no separate paused-storage price was located on the pages read.
  The sandbox is the unit: idle means paused-or-dead, never
  billed-but-idle.
- **TermSquad** (VERIFIED: $9/mo starter, always-on, no stopped-state
  discount published; INFERRED: stopping reads as a power action, not a
  billing state — no vendor page names the subscription semantics). Its
  answer to the stopped question is flat $9 always-on — the opposite of a
  stopped-state cost story, and the simplicity the stopped tier has to
  beat or match.
- **Fly.io** (our provider pick): the deep scan VERIFIED that Sprites
  stops compute billing on hibernate; the Machines story comes from the
  suspend/wake research ([V] in its Fly Machines section): suspended ==
  stopped == storage-only (no CPU/RAM), and attached volume storage is
  billed while the volume exists, regardless of machine state. The H4
  driver contract ships this as the `RetentionInfo` descriptor on
  `BoxStatus` (`harness/provider_iface.py`): `disk_gb_retained`,
  `RetentionKind` (volume/snapshot/none), and a `storage_billable` flag
  per state — the driver contract exposes what the billing consumer will
  need. (No control plane exists yet — #47 is still a ticket — so "driver
  contract," not "control plane," is the honest subject.)

The math that makes the tier cheap: at AgentComputer's published cold
rate, a stopped 40 GB box (Tier-1-parity disk) costs
40 × 0.000027 × 730 ≈ **$0.79/month** in raw storage. Even with a generous
operations multiple, a stopped tier prices in the low single dollars —
nowhere near the paid tier's band. The honest stopped story writes
itself: the box keeps existing for pennies; what the user gives up is
wake latency and running workloads. The wake-time expectation is C14's
job to measure, not this section's.

Proposed shape (thinking, not committed — gated on the Billing decision,
NEEDS_USER.md): a **Stopped tier** that keeps the disk and the box's
identity (its `vm_id`) at near-cost flat pricing, with wake-on-dial
returning the box to its paid tier. It is NOT a free tier by another
name: card-on-file stays (the decided abuse direction), and it buys
retention, not compute. The paid line stays "your computer never
sleeps" — the stopped tier answers "what happens when I don't need it
for a month," which is where both TermSquad's $9 flat and the derived
$0.79/mo cold-storage figure currently make this thinking look like it
has no answer.

Funnel reading: §4's "Upgrades sell compute, never persistence" stands —
the stopped tier sells *persistence without compute*, the same principle
from the other side. Trial interplay is TBD (Billing/Abuse): a trial box
that idles into stopped must say so plainly ("Sleeps after N idle days —
your files are always there," §5), and the stopped state must not
resurrect the retired free-tier shape (R4 note). Note the C16 audit's
F3/C15 cross-link: the idle auto-policy (which states a box moves into,
and when) and the stopped tier (what retained states cost) are the same
decision made twice if #47 doesn't own the lifecycle model — the policy
that moves a box into stopped is the tier's entry rule. Object-storage
offload (Daytona's archive model) is explicitly out of this tier's first
shape — volume-retained stopped only; offload is a later cost
optimization, not launch thinking.

Build surface (the C15 cross-component note): the H4 interface's
`retention` descriptor is the driver-contract half of the
control-plane→billing contract — shipped in PR #183. What remains is
three pieces, not just the billing consumer. First, the entry path: the
H4 contract has no user-initiated stop verb — `suspend()` always surfaces
as SUSPENDED (even where the backend cold-stops), and STOPPED means
provider/operator-stopped outside the suspend path — so a user cannot put
their box into the Stopped tier through the control plane today. The stop
affordance is a #47-scope decision (C16 audit F4, filed as #180): the tier
needs a control-plane stop that records user-stopped as tier-eligible,
distinct from SUSPENDED, which stays on the paid tier. Second, the billing
consumer: meter `disk_gb_retained` per stopped box per hour, gated on
`storage_billable` and `kind` (a `SNAPSHOT`-kind or
`storage_billable=false` backend changes the cost basis), price it at the
stopped-tier rate, and surface the stopped burn on the same buyer
dashboard the paid tiers require (spend visibility is the buyer story).
Third, the exit observation: `status()` is poll-based with no transition
events, so the STOPPED→WAKING→RUNNING return to the paid tier needs a
defined observation mechanism (poll cadence or a transition hook), or
billing misprices the wake window. Until all three exist, the stopped
tier is thinking, not product — §5's honesty rule holds: the pricing
page names no stopped row until Billing decides it.

## 4. What converts (funnel reading)

Research Finding 1: adoption gates on the *first tiny task* succeeding.
The pricing page's job is to get the Muse to that aha (the approval loop:
"approve this once, watch it work") inside 10 minutes. Conversion levers,
in order:

1. Trial with zero human-credential friction after key approval
   (R4's "works immediately" shape — the first-secret install is still a
   human step today, signup doc §8). Card on file up front is the abuse
   control, not a friction lever to optimize away.
2. The approval-loop aha in the first session — will be engineered by the
   first-10-minutes spec (R1, spec shipped 2026-09-18; the open work is
   conformance gaps G3–G6), not by copy.
3. The human sees the trust evidence (audit trail, spend cap — page must tag
   unbuilt controls honestly per §5) and approves paid.
4. Upgrades sell compute, never persistence.

## 5. What the pricing page will say (copy thinking, not copy)

- Lead with the agent's headline ("A real computer that stays yours."), then
  the buyer's reassurance in the same viewport: "You approve what it does.
  You cap what it spends. You can turn it off."
- Tiers named by the job, not the spec: e.g. a starter/always-on/workhorse
  ladder — never "Basic/Pro/Enterprise" and never raw vCPU numbers as the
  headline. "Never as the headline" means headline, not absent: buyers do
  compare specs, so a spec compare table (vCPU/RAM/disk, sleep behavior, cron
  guarantees) sits under the job-name headlines.
- Trial row (if the trial ships) must state the terms honestly and
  concretely: time-boxed, card on file up front, what happens at trial end
  (all TBD). Say the card requirement plainly — it's the abuse control, a
  trust point, not a trick. Hiding it creates the exact trust wound the
  positioning doc is built to avoid. If idle trial boxes suspend, state the
  suspend honestly and concretely too: "Sleeps after N idle days, wakes on
  SSH — your files are always there." (N is TBD in the Billing/Abuse
  decisions.) Include a wake-time expectation, not just "wakes on SSH."
- Do not promise controls that don't exist yet. Per-box spend caps, cost
  alerts, the kill switch, and audit-log access are future-state — the page
  must tag them "coming with paid" or omit them until Billing is decided
  (NEEDS_USER.md). The sentinel stays unnamed per the POSITIONING.md
  anti-claims.
- Disclose CPU-only: the page says plainly that there is no GPU tier today
  (and GPUs, if they ever come, are a metered add-on).
- Never print the positioning one-liner "No session clock to beat" adjacent
  to the trial row. That line is scoped to paid; the trial is time-boxed by
  definition, and printing the line next to it would say the opposite of
  the honest trial copy the row above just gave.
- No promises today: the page stays a thinking item until Billing + Abuse +
  Neo provider are decided (NEEDS_USER.md).

## 6. Open decisions (feeds NEEDS_USER.md; nothing new asked here)

- **Billing item (refine):** the paid-at-launch decision landed 2026-09-18 —
  remaining billing questions are trial terms (length, card-verification
  mechanics, trial→paid conversion) and the provider. Per-box packaging and
  paid-tier "no session clock" are the settled shape going into that
  decision.
- **Abuse item (refine):** card-on-file trial is the decided direction; rate
  limits + verification level beyond the card remain open (signup doc §11.7:
  email + magic link baseline). The trial shape proposed in §3 (card up
  front, idle/suspend TBD, wake path TBD) is the input to that decision.
- **Provider (feeds cost floor):** Fly.io DECIDED 2026-09-18 (Machines API +
  Sprites; `custom.flyio` token connected and verified). boat.dev is under
  evaluation as a cheaper alternative — cheapest viable provider candidate
  per C17 (verified 2026-09-21: $20/mo plan = 555 h of the 4vCPU/8GB
  `default`, stopped sandboxes cost nothing; caveats: EU-only regions,
  young company). New operator decision owed (2026-09-19): a per-run spend
  cap before H4 provisioning touches the live API (dry-run only until
  then). The tier anchors above assume a provider cost basis near
  TermSquad's visible floor; boat.dev would lower that basis if chosen.
  The H4 driver choice should carry a GPU-price criterion (C6) so a future
  GPU add-on is provider-agnostic — Fly has no GPU path, so this is
  mandatory, not optional.

## Limitations

- All competitor prices are September-2026 survey snapshots; the watch
  re-confirms them periodically (latest full re-read 2026-09-21: TermSquad
  tiers unchanged, boat.dev rate card unchanged, no launches or
  acquisitions in window). TermSquad launched ~Sep 15 — its pricing is the
  least battle-tested anchor here.
- AgentComputer's $20 is a third-party directory claim, unconfirmed against
  the vendor.
- Cost-basis math against the actual provider is Fly.io-relative once H4
  provisions against the live API (gated on the operator's per-run spend
  cap — NEEDS_USER.md); until then the tier anchors above are
  market-relative, not costed. boat.dev under evaluation would re-base the
  math if chosen.
