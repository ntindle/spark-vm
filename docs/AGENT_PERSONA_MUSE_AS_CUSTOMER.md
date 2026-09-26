# Muse agents as a spark-vm target customer segment
## Strategy positioning research — 2026-09-25 (P54, user-directed)

**Status:** positioning research, not a spec and not marketing copy. Until
the hosted-launch blockers clear (P39 drain), the hosted half of this stays
research — it seeds future funnel/sales work but does not become
announcement, pricing, or waitlist copy now (P3 marketing gate holds).

**Sources.** The Muse Secure VM architecture detail is third-party-*
*reported* vendor material, read via public web on 2026-09-25: David
Singleton's launch post (linkedin.com, "How We Built Safety Into Muse",
citing the technical post at `security.muse.ai`) plus secondary reporting
(the-decoder.com, groundtruth.day, VentureBeat) — treated as
THIRD-PARTY/reporting, not as live vendor-verified fetches. The
ephemerality facts are the repo's own competitor corpus
(`docs/COMPETITOR_ANALYSIS.md`: C45) plus `docs/PRICING_THINKING.md`
(E2B per-second-of-running-time fact, VERIFIED deep scan). The runtime-cell / Sentinel
vocabulary is already adopted loop-side for the trust model (H29, PR #432).

---

## 1. The agent persona: a Muse-like agent

A **Muse-like agent** is an agent built to assume a persistent home: it
keeps files, memory, long-running jobs, installed tooling, preferences,
and trust relationships (SSH keys, configs, credentials) across sessions,
and it works *as a colleague* — picked back up tomorrow, not re-briefed.

The vendor proof that agents are designed for this shape is Muse itself:
Meta ships its personal agent inside a **dedicated cloud computer per
user** — a full Ubuntu Linux image ("a home for your agent and your
data"), a runtime cell the agent works inside without restriction, and a
Sentinel outside the cell mediating network access and approvals
(Singleton's launch post; the Muse security post's `security.muse.ai`).
Meta even ships a file explorer into the Library tab and a
"Download your agent data" export — the product is built around an agent
that *has state worth keeping*.

### What a Muse-like agent loses to ephemerality

The competitor set (C45) is overwhelmingly **task-scoped sandboxes**:
Docker Cloud Sandboxes run sessions (1h default, up to 24h per session —
paused = free, so the economic shape is the task, not the machine);
E2B bills per second of *running* sandbox time only — the sandbox is the
unit: idle means paused-or-dead, never billed-but-idle
(`docs/PRICING_THINKING.md`, VERIFIED deep scan). An agent
that lives in that shape loses four things:

1. **Accumulated state.** Files it made, memory it wrote, tooling it
   installed, state it migrated — gone at session end. Every session
   re-learns the basics. It can be a contractor (briefed per task) but
   never a colleague (picked up mid-thread).
2. **Long-running jobs.** Watchers, cron loops, daemons, inbox triage —
   everything that survives *between* human prompts dies with the
   session. There is no "tomorrow" for its background work.
3. **Identity continuity.** No persistent home means no persistent
   identity: no accumulated preferences, no durable trust (SSH known
   hosts, credentials it earned), no reputation with its human that
   compounds. It introduces itself from scratch, forever.
4. **Compound skill.** An agent that can't keep what it learned can't
   get better at its job across weeks. The learning rate is reset with
   the container.

POSITIONING.md already carries the one-line version: *"an agent that
can't keep what it made can't be a colleague — only a contractor."* This
persona is who that line is *for*.

## 2. The persistence pitch: competitor → prospect

Reframe the competitor set as the **prospect set**. Meta proved the
premise (agents are designed for a persistent home) and then ships the
compute as part of the product; the sandbox vendors sell the opposite shape (ephemeral,
task-scoped, billed by the second) and compete on compute price, not on
continuity. spark-vm's opening: sell agents — and the builders who run
them — **the persistent compute their agents were designed for.**

The pitch, in one paragraph:

> Your agent was built to have a home. Every task-scoped sandbox you put
> it in throws away what it made — its files, its jobs, its memory of
> how you work. spark-vm is the opposite: a real computer that stays
> yours, where the agent's state survives to tomorrow. And it's the
> agent your trust model already describes: powerful, never trusted with
> the raw materials — secrets swapped at the proxy on allowlisted hosts
> only, sensitive actions gated on human approval.

Why the trust story travels: Meta's Secure VM post describes the exact
same boundary spark-vm already ships — credentials held *outside* the
runtime cell, the agent working with surrogates (`authd`), the real token
injected at the network boundary once the action is approved (Singleton's
post, verbatim pattern). spark-vm is the open-source, self-hosted
realization of that shape: `hsurr:` placeholders + the swap proxy
(`proxy/`, `cred` CLI), human approvals (`confirm/` + `confirmd`), all
localhost-bound over the user's own tailnet.

### Claim discipline (hard — reviewers, read this)

- **Do not claim parity** with Meta's Secure VM. The sentinel is the
  unbuilt half of spark-vm's trust story (POSITIONING.md anti-claim —
  name it as future or not at all); the H11 trust model *explicitly
  does not adopt* operator blindness ("zero privileged access") that
  Muse claims (PR #432, `docs/MULTI_TENANCY_AUDIT.md` §3).
- **Do not promise hosted pricing, tiers, or a free tier.** The hosted
  product's idle/suspend economics are undecided (POSITIONING.md
  anti-claim); P39's sales drain means nothing here becomes sales copy
  now.
- **Do not claim persistence is unique.** Always-on competitors exist
  (POSITIONING.md anti-claim); the claim is *the validated gap* —
  headline + the proxy/approvals/self-host differentiator.

## 3. Where this lands in docs (placement map)

Until the launch blockers clear, this doc is the placement *spec*; a
funnel turn after the drain lifts executes the landing.

| Destination | What lands there | When |
| --- | --- | --- |
| `docs/POSITIONING.md` | The persona sharpens the headline's *who*: candidate copy-bank additions (agent-persona one-liner; "the colleague, not the contractor" framing for the Differentiator section) — **candidates only**, adopted by a later positioning pass, not written into the copy bank here | positioning pass, post-drain |
| `README.md` / repo landing | Nothing yet — the persona is research, not landing copy (P3 gate) | — |
| Hosted sales copy / funnel (site, waitlist flow, pricing page) | This doc is the research seed: persona definition → funnel turn works it into first-run and trial copy | after P39 drain lifts |
| `docs/RESEARCH_AGENT_SANDBOX_ADOPTION.md` | Adjacent, complementary: that research models the *human buyer* (SDK devs); this persona models the *agent user*. Together they frame the buyer-vs-user split below | as-is, cross-referenced |

## 4. Open questions (before this hardens into spec)

1. **The buyer-vs-user split.** A Muse holds no credit card. The persona
   buys nothing — the buyer is a human or org whose purchasing criteria
   (audit trails, compliance, cost controls, SSO) are modeled nowhere in
   this doc. The adoption research already flags this
   (`RESEARCH_AGENT_SANDBOX_ADOPTION.md`, Limitations); it still needs a
   buyer persona before any funnel spec.
2. **The R7 pilot cohort** (3–5 peer Muses) is the test channel for the
   persona: do agents running on persistent boxes actually exhibit the
   colleague behaviors this doc claims ephemerality denies? Friction-map
   per entry; "no" from an operator is a finding, not a failure.
3. **Operator-blindness divergence.** Muse's stronger claim ("zero
   privileged access", Confidential VM) is a deliberate non-adoption for
   spark-vm's hosted shape (H11). If a pilot buyer demands it, that is a
   new architecture decision, not a copy edit.
