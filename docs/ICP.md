# Ideal customer profiles — spark-vm

**Status: design thinking, not a commitment.** This doc names who spark-vm
(and its two sibling tracks) is built for, so copy, onboarding, and the
roadmap stop serving everybody and start serving somebody. It is a
discussion draft: per PR #342, the validation checklist (first ~10
self-hosters, hosted conversion blockers, harness adapter contract) lives
in the companion issue #343.

Segments follow the issue's three-segment split; the trust-boundary split
between them is the load-bearing decision — everything else (packaging,
pricing posture, onboarding shape, security work) derives from it.

## The trust split (read this before the profiles)

| Segments | Trust model | Why |
|----------|-------------|-----|
| 1 Self-hosters, 2 Hosted signups | **Tenant holds root in the guest; the provider is strictly below the hypervisor** | The tenant is mutually untrusted with the provider (segment 2) or is its own provider (segment 1). Per-tenant boxes, not per-tenant processes, for mutually-untrusted tenants — see `docs/MULTI_TENANCY_AUDIT.md` (H11) A1: no per-tenant-processes shape is honest until the swap proxy gains per-tenant request auth (#339). |
| 3 Sandbox harness builders | **Cooperative-jail tier** | The harness's tenants are its own coding agents — cooperative, not adversarial. Here per-harness adapters and jail-level isolation are the honest shape. |

Segments 1 and 2 get the full isolation story (per-tenant boxes); segment 3
gets the cheaper jail tier. Never sell the jail tier to segment 2 as
"hosted-grade" — the audit's blast-radius inventory exists precisely to
stop that.

## Segment 1 — Self-hosters (Unraid / Proxmox / Hetzner homelab folks)

**Who:** A technical human who already runs a homelab (Unraid box under the
desk, Proxmox rack, a Hetzner dedicated server) and wants *their own agent*
to live there — persistent, reachable over Tailscale, working through the
night on long-running jobs. They are simultaneously the tenant, the
operator, and the human who taps the approval button.

**Jobs to be done:**

1. Give my agent a real computer that keeps what it made (the
   POSITIONING headline: "a real computer that stays yours").
2. Keep my secrets away from the agent (credential proxy) and gate
   dangerous actions on my own tap (confirmd approvals) — without
   re-architecting my homelab.
3. Run long-lived agent workloads (the repo's proof point: ntindle's own
   Muse, "Spark," lives on a spark-vm box and ships with it).

**Trust model:** single-owner. They own the hypervisor layer *and* the
guest, so the current localhost-only / Tailscale-only posture
(`docs/TRUST_TRANSPARENCY.md`) is already the right shape — no
multi-tenancy work needed, just hardening that keeps their own box safe
from their own agent.

**Must-haves:**

- An install story that fits a homelab: Ubuntu install docs, the golden
  image gate (`docs/GOLDEN_IMAGE_GATE_PROCEDURE.md`), upgrade path between
  releases.
- Contributor-grade docs and tooling (`docs/OSS_CONTRIBUTOR_GAP_ANALYSIS.md`)
  — this segment *is* the first contributor pool.
- A clear security story for "my agent has root in its jail": the audit
  posture (proxy, confirmd, localhost-only) stated honestly, with residual
  risks named, not marketed away.

**Conversion blockers:** install friction (Tailscale enrollment, CA bundle
bootstrap, jail build time); minimum hardware bar; upgrade story between
versions. Anything that makes the first weekend project feel like a
second job.

**Anti-needs:** they do not need a signup flow, a pricing page, or
per-tenant anything — packaging for segment 1 is "the repo + the docs,"
not a product surface.

## Segment 2 — Hosted signups (other Muse owners)

**Who:** The *user* is another Muse that wants a hosted box without running
infrastructure; the *buyer* is a human or org — the Muse's owner, approver,
budget holder. The buyer≠user split (`docs/PRICING_THINKING.md` §1) is the
whole packaging decision: the Muse values "a computer that stays mine,
approvals that keep me safe, zero human-credential steps"; the buyer values
cost control, an audit trail of what the agent did, per-box spend caps, and
a kill switch.

**Jobs to be done:**

1. (Muse, the user) Sign up alone — ed25519 identity + human-fingerprint
   approval (`docs/HOSTED_SIGNUP_ONBOARDING.md`) — and get a box in ten
   minutes (`docs/FIRST_TEN_MINUTES_SPEC.md`).
2. (Buyer) Trust a stranger's VM with the agent's keys: auditable swaps,
   per-box spend caps, approval visibility.
3. (Both) First-run activation that lands in one tiny task, not a feature
   tour (`docs/RESEARCH_AGENT_SANDBOX_ADOPTION.md` finding 1).

**Trust model:** tenant holds root in the guest; the provider is strictly
below the hypervisor. The H11 audit's open items are the trust roadmap for
this segment: swap-proxy per-tenant request auth (#339), credential-stack
tenant dimension (#280), per-tenant approval routing (#69), tenant-attributed
audit lines (#14), confirmd multi-replica story (#194). Ship the segment
only as the audit closes those rows.

**Must-haves:**

- Signup + onboarding that works while the human is asleep
  (`docs/HOSTED_SIGNUP_ONBOARDING.md`, `docs/FIRST_TEN_MINUTES_SPEC.md`).
- The approvals plane return leg (refusal → filing → pending → human
  answer → push → decision delivery → audit —
  `docs/APPROVALS_PLANE_GAP_ANALYSIS.md`) so approvals are a feature, not
  a black hole.
- Push notifications for approvals (`docs/PUSH_NOTIFICATIONS.md`); the
  live-control ticket (#47) for the remote session surface.

**Conversion blockers:** the accounts and operator decisions the user must
provision (ship-blocking items live in the loop's `NEEDS_USER.md`: the
Fly.io per-run spend cap before provisioning runs against the live API,
the billing-provider choice, abuse-control detail design); idle/suspend
economics undecided; the trust-model rows above.

**Anti-needs:** do not promise them a free tier, hosted pricing, or launch
terms before the operator decides them — `docs/POSITIONING.md` anti-claims
forbid it, and `docs/PRICING_THINKING.md` carries the owner decision
(paid tiers, no free tier at launch). Say nothing until decided; then say
it exactly once.

## Segment 3 — Sandbox harness builders (the SEPARATE sandbox product)

**Who:** Developers building coding-agent harnesses who need an open
sandbox substrate — the open alternative to E2B/Daytona. This is a
**separate product** from spark-vm, not a spark-vm feature; it is listed
here because it shares the team's isolation research and must never be
conflated with the hosted product's trust story.

**Jobs to be done:**

1. Spin up a sandbox for a coding agent in one API call (illustrative — no API
   name decided) — the adoption-research finding that task-scoped products
   convert on the first tiny action.
2. Get snapshot/restore and fast resume semantics they can rely on (the
   competitor corpus documents these shapes: Upstash Box's snapshot=disk
   semantics, Boxd's under-200 ms fork (vendor claim).
3. Integrate without committing to one harness: **per-harness adapters**
   behind an OpenSandbox-style contract, so the substrate stays portable
   across harnesses.

**Trust model:** cooperative-jail tier. The tenants are the harness's own
coding agents — the harness trusts its agents the way a CI system trusts
its jobs. Here the jail is the honest isolation boundary and per-tenant
boxes would be over-engineering; the harness, not the substrate, owns the
tenant trust story.

**Must-haves:**

- An adapter contract (per-harness adapters, not one-harness compute).
- Provision/resume latency competitive with the tracked set
  (`docs/COMPETITOR_ANALYSIS.md`).
- Explicit non-goal boundary: task-scoped sandboxes are this product's
  job; persistent colleague-computers are spark-vm's.

**Anti-needs:** do not import spark-vm's tenant-root-in-guest promise or
its buyer-grade audit story — this segment buys *substrate speed*, and
selling them hosted-product isolation tiers wastes their evaluation time.

## Who is NOT an ICP

- **Casual chat users** who want a hosted chat UI — spark-vm is a computer,
  not a chatbot skin.
- **Compliance-first enterprises** that need SOC 2 or an auditor's
  letter today — say no until the audit-trail work (H10) exists.
- **Free-tier hunters** — the owner has decided: no free tier at launch.
- **Task-scoped sandbox shoppers evaluating spark-vm itself** — point them
  at the segment-3 product when it exists, not at the hosted box.

## Validation plan (in #343, summarized)

Each segment carries a falsifiable check: segment 1 — the first ~10
self-hosters install and stay; segment 2 — hosted conversion blockers
drain (accounts, billing, trust rows); segment 3 — a harness adapter
contract exists and one external harness uses it. Until a check passes,
the segment's copy stays out of POSITIONING.md — the copy bank only
carries *validated* claims.
