# Competitor analysis — agent VM/sandbox offerings, September 2026

## Competitor archetype — 2026-09-18

**Question:** who else offers VMs or sandboxes for agents, what do they charge,
and where does spark-vm win or lag? **Method:** public sources (vendor docs,
pricing pages, launch coverage, third-party benchmarks) surveyed 2026-09-18.
This is a strategy input, not a spec — it feeds the backlog and the gap
analysis. It extends the competitive map in `docs/RESEARCH_AGENT_SANDBOX_ADOPTION.md`
(research archetype, PR #25) with prices, axis scorecards, and a first
TermSquad watch pass (backlog R3).

**Scope note:** the market splits into two segments and spark-vm only plays in
one of them. **Task-scoped sandboxes** (E2B, Daytona, Modal, Vercel, Cloudflare,
Runloop) rent *executions* — fast cold starts, per-second billing, sessions
measured in hours. **Persistent computers** (TermSquad, AgentComputer,
Fly Sprites, Northflank, DIY VPS, spark-vm) rent *a machine that stays yours*.
Comparisons across the split are category errors for pricing and cold start —
but they are fair game on the two load-bearing axes (egress controls,
isolation), because those are where the trust story lives.

## The field at a glance

| Offering | Segment | Model | Price signal (Sep 2026) |
|---|---|---|---|
| **TermSquad** (launched Sep 15) | Persistent computer | Always-on Linux computer per customer; Herdr persistent sessions; Squad multi-agent orchestration; Squad Memory; BYO agent subs/keys | **$9–$49/mo** published (2–8 vCPU, 4–24 GB, 40–200 GB NVMe) |
| **AgentComputer** | Persistent computer | Persistent Ubuntu VMs for coding agents, SSH/API access, 25 GB disk | **$20/mo** (third-party directory claim — see Sources) |
| **Fly.io Sprites** | Persistent computer | Firecracker microVM per user, 100 GB root persists indefinitely, hibernates when idle | Subscription tiers; $0.07/CPU-hr active |
| **Northflank** | Both | microVM/Kata/gVisor, stateful or ephemeral, self-serve BYOC | Lowest published rate: $0.01667/vCPU-hr; free sandbox tier |
| **E2B** | Task-scoped sandbox | Firecracker microVM per sandbox, SDK-first, templates-as-code | Hobby $0 + $100 one-time credit (1h sessions, 20 concurrent); Pro **$150/mo** + usage (24h sessions); ~$78/mo usage for one continuous 2vCPU/512MB box |
| **Daytona** | Task-scoped sandbox | Containers (+VM/Windows classes), stateful, stop/archive/pause/fork, GPU (ephemeral) | $200 free compute, no plan floor; $0.0504/vCPU-hr + $0.0162/GiB-hr; GPU on request (H100 listed $2.27/hr) |
| **Modal** | Task-scoped sandbox | gVisor, GPU inside sandbox (T4–B300), memory snapshots | Sandbox tier ≈3x standard rate; $0.0710/vCPU-hr equiv; free Starter, $250/mo Team |
| **Vercel Sandbox** | Task-scoped sandbox | Firecracker microVM, 45min/24h sessions, snapshots | Active-CPU billing ($0.128/vCPU-hr); Hobby allotment; Pro credit |
| **Cloudflare Sandbox** | Task-scoped sandbox | Containers on Workers, sleeps at 10 min idle, disk resets on sleep | Active-CPU billing ($0.072/vCPU-hr); $5/mo Workers Paid floor |
| **Runloop** | Task-scoped sandbox | Custom hypervisor, SWE-bench focus, suspend/resume (Pro) | $0.108/CPU-hr; free Basic; $250/mo Pro |
| **Blaxel** | Task-scoped sandbox | Perpetual sandboxes, scale-to-zero in 1s, hibernate | Per-second usage; SOC 2 / HIPAA / ISO 27001 |
| **Microsandbox** | Task-scoped sandbox (OSS) | libkrun microVM, network-layer secret injection | Free, self-hosted (YC X26) |
| **DIY floor** | Persistent computer | $5.70/mo droplet + the human does everything | $5.70/mo + labor |
| **spark-vm (this project)** | Persistent computer (OSS + hosted-in-design) | Real VM, per-action human approvals (confirmd), credential proxy (swapd), tailnet-first networking | OSS: provider cost + operator time; hosted: TBD (pricing thinking is an open backlog item) |

## TermSquad watch — first pass (R3)

TermSquad is the closest competitor and the newest (launched three days before
this writing), so it gets the full watch treatment.

**Pricing (verbatim from [termsquad.com/pricing](https://termsquad.com/pricing),
2026-09-18):** Starter $9/mo (2 vCPU / 4 GB / 40 GB NVMe) · Builder $19/mo
(4 / 8 GB / 75 GB) · Power $29/mo (6 / 12 GB / 100 GB) · Ultra $49/mo
(8 / 24 GB / 200 GB). Every plan includes: always-on computer, web terminal,
SSH, persistent agent sessions, any-agent support, Squad, Squad Memory,
managed operations, workload protection, backups/restores. Locations across
America, Europe, Asia/Oceania (stock-dependent).

**Session model:** "Closing a tab or losing your connection does not power it
off. Shutdowns, restarts and billing suspension are separate lifecycle
actions." Sessions are Herdr-managed; agents in a persistent session "can keep
working after you disconnect" (with the honest caveat that unattended
completion isn't guaranteed). Stopping the computer is a power action, not a
subscription cancellation — the environment stays associated with the plan.

**Isolation story (scored):** one dedicated "TermSquad Computer" per customer —
a per-tenant VM boundary, same tier as our per-VM tenant design (signup doc
§9). Public pages say nothing about the hypervisor, the network policy, or
what the managed platform can see inside the box. **Egress controls are not
documented on any public page found** — the highest-priority open question
for the next watch pass.

**Agent-as-customer story (scored): absent.** The account holder is the human
developer: "TermSquad provides the computer. You bring your own agent
accounts, subscriptions and API keys" — and, notably, *"Your credentials stay
in your TermSquad Computer; they do not become a TermSquad AI-credit
balance."* Raw credentials live on the box. There is no agent-owned identity,
no signup flow a Muse could complete alone, no approval loop for agent
actions. The human is the customer; the agent is the tool. Our signup design
inverts this (the Muse as the user, the human as the approver) — that
inversion remains uncontested.

**What they ship that we don't:** Squad (lead agent delegates to parallel
sub-agents), Squad Memory (durable shared project knowledge), a mobile web
terminal, managed backups/restores, and multi-region choice. Each is a product
gap to file, not a reason to panic.

**Watch items for the next pass:** egress-controls documentation (still
unpublished), Herdr session semantics (restart policy after host failure?),
any isolation whitepaper, plan/spec changes, and any signal of an
agent-as-customer offering.

## Axis scorecard 1 — egress controls (scored explicitly, per R3)

Every platform in the benchmark set that documents it can now deny egress by
default; the differences are in granularity, who holds the secrets, and
whether the sandbox can disable the policy.

| Platform | Block-all | Allowlist granularity | Runtime change | Credential injection (agent never holds the secret) |
|---|---|---|---|---|
| **E2B** | `allowInternetAccess: false` | Domains, IPs, CIDRs, wildcards | Yes (`updateNetwork()`) | **Yes (public beta):** per-host request transforms inject headers at the egress proxy, including workload-identity tokens the sandbox never sees |
| **Daytona** | `networkBlockAll` (per MarkTechPost Aug-2026 benchmark) | `domainAllowList` (20 max), `networkAllowList` (10 IPv4 CIDRs) (per MarkTechPost Aug-2026 benchmark) | Tier 3/4 only (third-party — MarkTechPost Aug-2026; unconfirmed in Daytona's own docs) | **Yes (verified, [daytona.io/docs/en/secrets](https://www.daytona.io/docs/en/secrets/)):** opaque `dtn_secret_*` placeholder mounted in the sandbox env; outbound proxy substitutes into HTTPS request headers only (bodies, query params, plain HTTP pass through unchanged); per-secret host allowlist (exact + `*.` wildcards; omitted = unrestricted); response scrubbing rewrites real values back to the placeholder |
| **Modal** | `block_network=True` | CIDR + domain allowlists (beta) | Alpha, only if set at create | Not documented |
| **Vercel** | `deny-all` incl. DNS | Domains via SNI + IP/CIDR fallback | Yes, no restart | **Yes, on every plan:** credential brokering on egress, matchers by path/method/query/headers; firewall runs on the host *outside* the microVM where sandbox code cannot disable it |
| **Cloudflare** | `enableInternet=false` | `allowedHosts`/`deniedHosts`, globs | Yes, live | **Yes:** outbound handlers run in the Workers runtime *outside* the sandbox with binding access; `ctx.containerId` scopes credentials per instance |
| **Runloop** | Per devbox | Yes | Per devbox | Credential Gateway with opaque token injection |
| **Microsandbox** | — | — | — | Network-layer secret injection; **OSS, self-hosted** |
| **TermSquad** | Not published | Not published | Not published | Not published — raw creds live on the box per their FAQ |
| **spark-vm / swapd** | ssrf.allow/ssrf.deny allowlists | Per-host allowlists | Config-driven | **Yes:** placeholder substitution at the egress proxy — request *and response* bodies scrubbed (76-test suite), 5 MB skip cap with durable audit line, TOTP scrub window; real secret values never enter the guest or the agent's view — only opaque `hsurr:` placeholders |

**Reading:** blocking egress is table stakes and the injection half is now a
converging design — E2B, Vercel, Cloudflare, and **Daytona** all ship some form of
"the proxy holds the secret, the sandbox doesn't." Daytona's own docs (verified
2026-09-18) show the posture fully formed: opaque `dtn_secret_*` placeholders,
outbound-proxy substitution into HTTPS request headers, per-secret host
allowlists, and response scrubbing — the same two halves swapd implements.
swapd's remaining edges are narrower now: (1) it is **open source and
self-hostable** (Microsandbox is the only other OSS entry, and it's a sandbox,
not a persistent-box stack); (2) **request-body-scope substitution** — Daytona
substitutes headers only; bodies, query params, and plain HTTP pass through;
(3) the **TOTP scrub window**; (4) **durable per-decision audit lines**; (5)
policy the agent provably cannot disable (sudoers + grant-writer TTL clamps,
adversarially reviewed). The honest caveat, carried from the research doc: this
is an independently re-derived posture, not a proven lead — and Daytona proves
a major incumbent has already shipped the full pattern, so the docs must argue
mechanism-by-mechanism rather than posture-by-posture. This axis feeds the
security-docs repositioning (backlog R6/C3): make the comparison concrete, per
vendor, with links.

Two traps from the benchmark worth stealing for our own docs: E2B and Vercel
resolve allow/deny conflicts in **opposite** directions (E2B: allow wins;
Vercel: deny wins — per the MarkTechPost Aug-2026 benchmark; vendor links to
collect in C3) — a policy ported without rewriting doesn't mean the same
thing; and E2B's blocked TCP connections can *look* successful from inside
the sandbox (the firewall accepts before deciding), so "network is blocked"
must be verified at the application layer, never by `connect()` succeeding.

## Axis scorecard 2 — isolation (scored explicitly, per R3)

| Tier | Who | Boundary |
|---|---|---|
| Dedicated kernel per sandbox | **E2B** (Firecracker microVM) | Hardware-level; strongest in the task-scoped set |
| Per-customer computer | **TermSquad** (dedicated computer), **AgentComputer** (Ubuntu VMs), **Fly Sprites** (Firecracker per user), **spark-vm** (per-VM tenant) | One VM per tenant; cross-tenant attack must escape the hypervisor |
| Syscall-filtered shared kernel | **Modal** (gVisor) | Stronger than containers, weaker than a VM |
| MicroVM per sandbox, ephemeral | **Vercel** | Firecracker, but the box is disposable |
| Containers on shared infra | **Daytona** (default), **Cloudflare** (Workers containers) | Kernel shared with other tenants' workloads |
| Configurable | **Northflank** (Kata/Firecracker/gVisor) | Customer picks the tier |

**Reading:** spark-vm's per-VM tenant boundary sits in the same tier as
TermSquad's and above every shared-kernel sandbox default. E2B's
dedicated-kernel-per-sandbox and the per-customer-computer rows are the same
cross-tenant tier — the difference is granularity and lifetime (per sandbox vs
per customer), not boundary strength. The tractable isolation story (signup doc
§9) survives this comparison. What the table
doesn't show, and what sentinel exists to answer: who watches the *inside* of
the box from the outside. Vercel's firewall and Cloudflare's handlers are
enforced outside the sandbox by construction; our outside observer (sentinel)
is still a design doc, not code. Until it ships, our isolation story is
"good walls, no watchtower" — say so plainly in the security docs.

## Where spark-vm wins

1. **A real computer that stays yours.** Full OS, unattended background jobs,
   cron loops, your own stack — no session clock at all. Matches TermSquad;
   beats every task-scoped sandbox on the no-session-clock axis by design
   (their sessions are measured in hours and their idle billing punishes
   exactly the workloads a persistent box exists for).
2. **Per-action human approvals.** confirmd (mobile-friendly, auto-refreshing,
   two-tap approve, push on the roadmap) — no per-action approval loop found
   in any surveyed vendor's docs or product surface (2026-09-18). The
   incumbents isolate sessions or broker credentials; none gives the human a
   per-action approval loop for what the agent is about to do. (A surveyed
   negative — confirm periodically; see C1.)
3. **The credential-proxy posture, as open source.** The injection half is
   converging — Daytona has shipped the full pattern (verified in their docs).
   swapd remains the only **OSS, self-hostable** implementation with
   request-body-scope substitution, response scrubbing, TOTP window handling,
   and per-decision audit lines — and the only one built for a persistent box
   rather than an ephemeral sandbox. The docs must argue
   mechanism-by-mechanism now, not posture-by-posture.
4. **Agent-as-customer.** The signup design (ed25519 identity + human
   fingerprint approval, re-link for ephemeral Muses) is the only offering
   shaped around a Muse signing itself up. TermSquad's customer is the human
   developer; everyone else's customer is the developer's SDK key.
5. **Self-host economics.** The DIY floor ($5.70/mo droplet) proves the
   hardware is cheap; spark-vm is the managed tooling *on top of* cheap
   hardware, without the $150/mo E2B Pro floor or the per-second meter running
   while the box idles.
6. **Private networking by default.** Tailnet-first, no public ingress, SSH
   relay as primary reachability — the task-scoped vendors don't need this
   story (their boxes are disposable); the persistent-box vendors mostly leave
   it to the customer.

## Where spark-vm lags

1. **GPU.** Modal, Daytona, and Northflank all have a GPU story; E2B and we
   don't. Any agent workload that touches a GPU has no home here. (Long-term
   gap; the Neo provider choice should keep a GPU path open.)
2. **Provisioning speed.** MVP provisioning is ~15 minutes of cloud-init
   (signup doc §7); the task-scoped segment measures cold start in
   *milliseconds*, and even the persistent segment (AgentComputer "sub-second"
   per a third-party directory table — same source as its $20/mo row; Fly
   Sprites instant hibernate per the benchmark) treats fast start as the
   product. Golden images (backlog R2) are the fix; until then, don't race them
   on this axis.
3. **Idle economics.** Always-on bills wall-clock. The task-scoped segment has
   answers the persistent segment mostly lacks (E2B pause/resume;
   Vercel/Cloudflare active-CPU billing — roughly 2x cheaper on idle-heavy
   agent loops per the benchmark); in-segment, Fly Sprites hibernates, which is
   VM-native. But suspend needs an explicit idle definition: the headline
   workload is *unattended* background work — cron loops, the same 24/7 loops
   this project's own automation runs — and no platform can distinguish that
   from an abandoned box without a declared policy. The honest shape (see C5):
   define idle as no human-originated session *and* no *registered*
   scheduled-workload activity for N days; wake path is suspend-to-disk +
   wake-on-SSH-dial; and "no session clock" becomes a paid-tier property — the
   free tier trades it for suspend. Without that split, the hosted free tier
   (R4) bleeds money on boxes nobody is watching.
4. **Trust signals.** No SOC 2, no compliance page, no "200M+ sandboxes"
   number. The research doc's Limitations section already flagged the
   buyer-vs-user split: the human/org buyer asks about audit trails and
   compliance, and we have no answers yet.
5. **Multi-agent orchestration.** TermSquad ships Squad; we have muse-job, a
   single-operator job runner. Coordinated parallel agents are a real product
   gap for the hosted vision.
6. **Signup friction.** Our human fingerprint-approval gates provisioning and
   recurs on every re-link; E2B asks for an API key and you're running. The
   R4 free-tier shape has to reckon with this honestly.
7. **Unbuilt halves.** Push notifications (issue #2) and sentinel (the outside
   observer) are the two load-bearing pieces of the trust story that exist
   only as docs. TermSquad launched into our persistence headline three days
   ago; the window for "a real computer that stays yours" *plus* a shipped
   trust story is open but narrowing.
8. **Positioning is unpublished.** The headline, the differentiator, and the
   comparison tables all live in strategy docs on open PRs. Nothing a
   prospective user can read today says why this box over TermSquad's $9/mo
   one. (Feeds R5.)

## Implications → backlog

- **C1 — TermSquad recurring watch** (competitor): egress-controls docs,
  Herdr session semantics (host-failure restart policy), any isolation
  whitepaper, plan/spec changes, agent-as-customer signals. Also watch for any
  vendor shipping a per-action human approval loop — win #2's differentiator
  is a surveyed negative, confirm it periodically. R3's first pass
  is done; the watch continues.
- **C2 — Pricing-page inputs** (sales): TermSquad $9–$49, AgentComputer $20/mo
  (third-party claim), E2B Pro $150 floor, DIY $5.70 — feed the pricing-page
  thinking item and R4.
- **C3 — swapd-vs-injection comparators** (docs, feeds R6): E2B per-host
  request transforms (beta), Vercel credential brokering (every plan),
  Cloudflare outbound handlers, Microsandbox network-layer injection (OSS).
  **Daytona verified** via [their secrets docs](https://www.daytona.io/docs/en/secrets/):
  opaque `dtn_secret_*` placeholders + outbound proxy, HTTPS-headers-only
  substitution, per-secret host allowlist, response scrubbing — the full
  pattern; docs must compare mechanism-by-mechanism. Open verification: the
  E2B-vs-Vercel allow/deny conflict-resolution claims and E2B's
  accept-before-decide TCP behavior — collect vendor links (currently sourced
  only to the MarkTechPost benchmark). Make the security-docs comparison
  per-vendor with links.
- **C4 — Orchestration gap** (hosted product): TermSquad Squad vs muse-job
  single-operator — file as a product gap for the hosted vision.
- **C5 — Idle economics for the free tier** (sales, feeds R4): always-on bills
  wall-clock; define the suspend mechanism *before* the free-tier shape
  hardens. Needs: (a) an explicit idle definition (e.g. no human-originated
  session *and* no *registered* scheduled-workload activity for N days —
  background cron loops are the headline workload, so "activity" must be
  defined against them, not around them); (b) the wake path (suspend-to-disk +
  wake-on-SSH-dial; cron jobs don't fire while suspended unless the free tier
  gets wake-on-schedule — which is a session clock by another name); (c) the
  tier split stated plainly: "no session clock" becomes a paid-tier property,
  the free tier trades it for suspend. Without this the item specs the wrong
  mechanism.
- **C6 — GPU path as a Neo provider decision criterion** (hosted product,
  long-term): no GPU story exists today; add an explicit criterion to the Neo
  provider choice — which providers offer GPU shapes, at what price, and
  whether the provisioning interface stays provider-agnostic across CPU/GPU
  shapes.
- **C7 — Positioning defense** (marketing, feeds R5): TermSquad now occupies
  the persistence headline in-market; the "real computer that stays yours" +
  credential-proxy differentiator needs to land publicly before the window
  narrows further.
- **C8 — Buyer-vs-user packaging analysis** (sales/product): the hosted
  product's *user* is the Muse but the *buyer* is a human/org. Map both
  journeys: what trust evidence each gate requires (audit trail,
  compliance/SOC 2 path, cost controls), per-box vs per-seat pricing, and how
  it shapes the pricing-page item, R4, and the free-tier abuse constraints.
  The research doc's Limitations section flagged this; it drives pricing
  packaging and the compliance roadmap, so it gets its own item.

## Sources

Surveyed 2026-09-18; links inline above. Primary: TermSquad pricing and
feature pages (termsquad.com/pricing, /features/always-on-cloud-computer,
/features/any-agent); TermSquad launch coverage (EINPresswire via
lifestyle.independent.mk, Sep 15, 2026); MarkTechPost Aug-2026 sandbox
benchmark (cold start, per-second pricing, network policy, isolation);
StartupHub 2026 sandbox comparison; ralph-playbook sandbox reference;
yuanbop/frugal E2B research notes; rethink-paradigms/mesh E2B internals;
opencolin/agentic-engineering sandbox + infrastructure tables (AgentComputer
price/speed rows — third-party, unconfirmed against the vendor);
[marcus-mok-gh/nova-cloud-computer daytona-vs-e2b](https://github.com/marcus-mok-gh/nova-cloud-computer/blob/HEAD/docs/daytona-vs-e2b.md)
(third-party, used only for pointers); pondero.ai July-2026
comparison; bradvin/agentfirst.directory AgentComputer entry; **Daytona's own
[secrets docs](https://www.daytona.io/docs/en/secrets/) (verified 2026-09-18 —
placeholder design, header-only substitution scope, host allowlists, response
scrubbing)**.
