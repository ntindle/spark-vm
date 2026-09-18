# Pricing thinking — hosted spark-vm

**Status: design thinking, not a commitment.** This is the internal pricing
analysis the sales/funnel backlog item ("pricing page thinking") asked for.
It is **not** published pricing and must never be quoted as a promise:
`docs/POSITIONING.md`'s anti-claims forbid promising hosted tiers, prices, or
a free tier before the idle/suspend economics are decided. The pricing *page*
lands after the operator decides the NEEDS_USER.md items (Billing, Abuse
controls, Neo provider); this doc is what informs those decisions.

Strategy input feeding: R4 (free-tier "works immediately" shape),
C2 (competitor pricing inputs), C5 (idle economics for the free tier),
C8 (buyer-vs-user packaging), signup design §11 open questions.
Sources for every number: `docs/COMPETITOR_ANALYSIS.md` (surveyed 2026-09-18;
AgentComputer and DIY figures are third-party claims, flagged where used).

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
  "box N," not "seat." Multiple Muses sharing one box is an identity/approvals
  question (§4 of the signup doc), not a pricing dimension.
- **The conversion trigger is buyer-facing evidence, not user-facing features.**
  The Muse converts when the first-10-minutes aha lands (research Finding 1);
  the human converts when they can *see* what the agent did and *bound* what
  it can spend. The pricing page must carry both halves: the agent's story
  ("a real computer that stays yours") and the buyer's story ("you see every
  approval, you cap the spend, you can kill it").
- **Cost controls are a feature the paid tier sells.** A per-box monthly cap /
  alerts / kill switch is what lets an org buy the thing without a procurement
  fight. Swapd's per-decision audit lines (§10) are the raw material; the
  pricing page promises the *controls*, not the mechanism.

## 2. Cost floor (C2)

What the market charges for persistent computers (Sep 2026):

| Offering | Price signal | Notes |
|---|---|---|
| TermSquad | $9–$49/mo (2–8 vCPU, 4–24 GB, 40–200 GB NVMe) | Always-on, includes Squad orchestration + backups |
| AgentComputer | $20/mo (third-party claim, unconfirmed) | Persistent Ubuntu VM, 25 GB disk |
| E2B Pro | $150/mo floor + usage | Task-scoped; one continuous 2vCPU box ≈ $78/mo usage — a task-scoped unit price for an always-on box |
| DIY floor | $5.70/mo droplet + human labor | The "human does everything" alternative |
| Fly Sprites | $0.07/CPU-hr active | Hibernates when idle — closest to our free-tier shape |

Reading the floor: a hosted persistent box cannot price below its wall-clock
provider cost plus operations margin. TermSquad's $9 starter (2vCPU/4GB/40GB)
sets the visible floor for "always-on computer for your agent." The DIY $5.70
is the anchor the OSS self-host story already wins against — hosted has to
earn its premium with *zero* setup, not with raw compute.

GPU is priced separately everywhere (Daytona H100 $2.27/hr; Modal GPU inside
sandbox at 3x rate). We have no GPU story today (C6) — the tiers below are
CPU-only; GPU, if ever, is a metered add-on, never bundled into the flat
tier (it would blow up the free tier).

## 3. Tier design thinking

### Free tier (R4 + C5): the hard one

The free tier exists to convert, not to serve. Its shape is set by three
constraints:

1. **"Works immediately" (R4):** zero human-credential steps after the key
   approval — the signup design's fingerprint-approval is the last human
   touchpoint; everything after is agent-driven.
2. **Idle economics (C5):** always-on bills wall-clock. "No session clock" is
   a *paid-tier* property; the free tier trades it for suspend. Define before
   the shape hardens:
   - **Idle = no human-originated session *and* no *registered* scheduled
     workload activity for N days.** Background cron loops (the improvement
     loop itself) are the headline workload — "activity" must be defined
     against them, not around them.
   - **Wake path:** suspend-to-disk + wake-on-SSH-dial. Cron jobs do not
     fire while suspended; wake-on-schedule is a session clock by another
     name and belongs on paid.
3. **Abuse (§11 Q7):** signup rate limits + identity-verification level for
   the free tier, decided before launch. Email-only signup invites spam VMs.
   The agentmail-owned-inbox signup (identity linking) raises the bar
   relative to email, but the rate limit is the real control.

Proposed shape (thinking, not committed): one small box (2 vCPU / 4 GB —
TermSquad-parity at the entry), suspend after N idle days, wake on SSH dial,
disk persists across suspend (persistence is the headline — losing the box
would contradict the entire positioning). Suspend loses *uptime*, never
*files*. What converts off the free tier: the session-clock difference
("your cron jobs only run while you're awake" → paid "no session clock"),
and disk/compute upgrades — never the persistence itself.

### Paid tiers

- **Tier 1 — the always-on box:** flat monthly, ~TermSquad-starter-parity
  compute, no session clock, registered cron workloads run 24/7. This is the
  core product: "your computer never sleeps." Price anchor: $9–$19 band.
- **Tier 2 — the workhorse:** more vCPU/RAM/disk for heavier agents
  (browser driving, builds, Blender renders). Price anchor: $29–$49 band,
  matching TermSquad's Power/Ultra spread.
- **Every paid tier includes the buyer story:** per-box spend cap, audit-log
  access (approval decisions + swapd lines), kill switch, cost alerts. These
  are not add-ons; they are why a human approves the purchase.
- **What we do NOT do:** per-second metering (that's the task-scoped
  segment's game; our headline is the opposite), GPU bundling, per-seat
  pricing, or usage credits that surprise the buyer.

### What converts (funnel reading)

Research Finding 1: adoption gates on the *first tiny task* succeeding.
The pricing page's job is to get the Muse to that aha (the approval loop:
"approve this once, watch it work") inside 10 minutes. Conversion levers,
in order:

1. Free tier with zero human-credential friction after key approval (R4).
2. The approval-loop aha in the first session — engineered by the
   first-10-minutes spec (R1), not by copy.
3. The human sees the audit trail + spend cap on the pricing page and
   approves Tier 1.
4. Upgrades sell compute, never persistence.

## 4. What the pricing page will say (copy thinking, not copy)

- Lead with the agent's headline ("A real computer that stays yours."), then
  the buyer's reassurance in the same viewport: "You approve what it does.
  You cap what it spends. You can turn it off."
- Tiers named by the job, not the spec: e.g. a starter/always-on/workhorse
  ladder — never "Basic/Pro/Enterprise" and never raw vCPU numbers as the
  headline (the buyer is not sizing VMs; the Muse doesn't care).
- Free tier row must state the suspend honestly: "Sleeps when idle, wakes on
  SSH — your files are always there." Hiding the suspend creates the exact
  trust wound the positioning doc is built to avoid.
- No promises today: the page stays a thinking item until Billing + Abuse +
  Neo provider are decided (NEEDS_USER.md).

## 5. Open decisions (feeds NEEDS_USER.md; nothing new asked here)

- **Billing item (refine):** this doc's open shape is the input to "whether
  hosted signups need payments, and which provider" — the free-tier suspend
  definition and the paid "no session clock" property need to land in that
  decision.
- **Abuse item (refine):** identity-verification level for the free tier now
  has a concrete design to check against (agentmail-owned inbox + enrollment
  tokens + fingerprint approval); rate limits still undecided.
- **Neo provider (feeds cost floor):** the tier anchors above assume a
  provider cost basis near TermSquad's visible floor. The H4 driver choice
  should carry a GPU-price criterion (C6) so a future GPU add-on is
  provider-agnostic.

## Limitations

- All competitor prices are September-2026 survey snapshots; the watch
  (R3/C1) re-confirms periodically. TermSquad is three days old — its pricing
  is the least battle-tested anchor here.
- AgentComputer's $20 is a third-party directory claim, unconfirmed against
  the vendor.
- Cost-basis math against the actual Neo provider is blocked on the user
  picking the provider — the tier anchors above are market-relative, not
  costed.
