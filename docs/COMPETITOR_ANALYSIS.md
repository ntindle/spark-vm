# Competitor analysis — agent VM/sandbox offerings, September 2026

## Competitor archetype — 2026-09-18

**Question:** who else offers VMs or sandboxes for agents, what do they charge,
and where does spark-vm win or lag? **Method:** public sources (vendor docs,
pricing pages, launch coverage, third-party benchmarks) surveyed 2026-09-18
(morning), with a same-day pm watch update (TermSquad re-check, egress/isolation
scorecard fills, market moves) and an evening consolidation pass (AgentComputer
Firecracker VM manager + WSO2 k8s runtime pinned on primary sources, TermSquad
herdr#3415 date correction, OpenAI Agents API terms), plus a 2026-09-19
consolidation pass folding three delta watch updates (night, morning, midday).
This is a strategy input, not a spec — it feeds the backlog and the gap
analysis. It extends the competitive map in `docs/RESEARCH_AGENT_SANDBOX_ADOPTION.md`
(research archetype, PR #25) with prices, axis scorecards, and a first
TermSquad watch pass (backlog R3). The three folded watch docs are archived under `docs/archive/competitor-watch/`
(verbatim content, archival banner prepended); see "Corpus conventions" below
for the left edge / reach-back / cadence rules this consolidation declares.

## Corpus conventions

Declared 2026-09-19 (closes the night pass's watch-methodology follow-up).
This section is the canonical home of the watch-process rules; the
BACKLOG.md block points here.

- **Left edge:** the Sept-2026 competitive map in this doc (PR #26,
  deepened by the #34 pm watch, the #54 evening-pass consolidation, and
  this pass). Watch docs are delta-only against the *previous watch doc*,
  which chains back to this baseline.
- **Watch-doc naming:** watch passes land as
  `docs/COMPETITOR_WATCH_YYYY-MM-DD.md`, with `_EVENING`/`_NIGHT`/`_MORNING`/`_MIDDAY`
  suffixes for same-day repeats; each is delta-only against the previous
  watch doc.
- **Reach-back policy:** a watch pass backfills a pre-window item only
  when a primary-source verification or a factual correction demands it
  (the #82 pattern — the five queued verifications, the CVE date
  corrections); otherwise pre-window items are not re-researched.
- **Retry rule:** a vendor-page fetch that fails the two-retry rule on one
  pass is re-attempted on the next pass rather than carried forward as
  standing UNVERIFIABLE (the 2026-09-22 DO product page flipped from
  UNVERIFIABLE to VERIFIED this way).
- **Deep-scan cadence:** on-demand by review/meta runs, not by the hourly
  loop. The hourly pass stays delta-only.
- **Consolidation queue:** this pass folds #64 (night) → #82 (morning) →
  #102 (midday) → this doc (#54's evening-pass consolidation merged
  separately as 1c244be). Consolidated watch docs are archived under
  `docs/archive/competitor-watch/` (verbatim content, archival banner
  prepended) and superseded. 2026-09-22 night pass: partial fold — the
  deferred C-entries (C17/C18/C19/C20/C26/C29/C30/C31) fold into the field
  table + a "Watch update — 2026-09-22 (night)" section; the 2026-09-22
  watch docs (MORNING/AFTERNOON/EVENING/LATE_EVENING/NIGHT) are NOT
  archived — their other deltas stay live against this baseline.
- **Compaction:** after each consolidation, superseded dated watch-update
  sections in this doc are candidates for summarization by a review/meta
  run — the baseline stays skimmable; the archived watch docs preserve the
  record.

**Scope note:** the market splits into two segments and spark-vm only plays in
one of them. **Task-scoped sandboxes** (E2B, Daytona, Modal, Vercel, Cloudflare,
Runloop) rent *executions* — fast cold starts, the billing unit is compute
time, state is an opt-in snapshot, and the environment has no standing
address/identity between runs. (Blaxel's "perpetual sandboxes" and Baseten's
"persistent sandboxes" are blurring the lifetime edge of this split — see
the pm watch update.) **Persistent computers** (TermSquad, AgentComputer,
Fly Sprites, Northflank, DIY VPS, spark-vm) rent *a machine that stays yours*.
Comparisons across the split are category errors for pricing and cold start —
but they are fair game on the two load-bearing axes (egress controls,
isolation), because those are where the trust story lives.

## The field at a glance

| Offering | Segment | Model | Price signal (Sep 2026) |
|---|---|---|---|
| **TermSquad** (launched Sep 15) | Persistent computer | Always-on Linux computer per customer; Herdr persistent sessions; Squad multi-agent orchestration; Squad Memory; BYO agent subs/keys | **$9–$49/mo** published (2–8 vCPU, 4–24 GB, 40–200 GB NVMe) |
| **AgentComputer** | Persistent computer | Persistent Ubuntu VMs for coding agents, SSH/API access, configurable storage (up to 250 GiB); **own open-source Firecracker-based VM manager on bare metal** ([computer-host](https://github.com/AgentComputerAI/computer-host) — tap devices, nftables networking, SSH keygen, guest identity injection, disk snapshots, <200ms boots; [computer-guest](https://github.com/AgentComputerAI/computer-guest) thin guest images — both public repos, 2 stars each, last updated 2026-04-30, no declared license on GitHub, so the repos corroborate existence, not production deployment) | **Pure PAYG, no flat plan:** $0.07/CPU-hr, $0.04375/GB-hr memory, $0.000683/GB-hr hot storage, **$0.000027/GB-hr cold (stopped)** — no published deletion window for stopped machines; **new Enterprise tier** (custom capacity policies, team billing, private infra, priority support); the rate-card parity with Fly Sprites stays **unexplained, not claimed reselling** (vendor claims its own stack; earlier $20/mo directory claim refuted against the pricing page) |
| **Fly.io Sprites** | Persistent computer | Firecracker microVM per user, 100 GB root persists indefinitely, hibernates when idle | PAYG ($0.07/CPU-hr; up to 3 concurrent sprites) plus exactly one subscription plan — Level 10, $20/mo (10 concurrent, 450 CPU-hrs, 1,800 GB-hrs RAM, 50 GB storage); hibernates after ~30s idle (warm wake 100–500ms, cold 1–2s); storage persists at cold-storage rates; still named Sprites (billing docs still draft, docs.sprites.dev) |
| **Northflank** | Both | microVM/Kata/gVisor, stateful or ephemeral, self-serve BYOC | Lowest published rate: $0.01667/vCPU-hr; free sandbox tier |
| **E2B** | Task-scoped sandbox | Firecracker microVM per sandbox, SDK-first, templates-as-code | Hobby $0 + $100 one-time credit (1h sessions, 20 concurrent); Pro **$150/mo** + usage (24h sessions); ~$78/mo usage for one continuous 2vCPU/512MB box |
| **Daytona** | Task-scoped sandbox | Containers (+VM/Windows classes), stateful, stop/archive/pause/fork, GPU (ephemeral) | $200 free compute, no plan floor; $0.0504/vCPU-hr + $0.0162/GiB-hr; GPU on request (H100 listed $2.27/hr) |
| **Modal** | Task-scoped sandbox | gVisor, GPU inside sandbox (T4–B300), memory snapshots | Sandbox tier ≈3x standard rate (arithmetic checks out — standard-rate half corroborated only by secondary sources; the pricing page shows the Sandbox+Notebooks tier only); $0.0710/vCPU-hr equiv; free Starter, $250/mo Team |
| **Vercel Sandbox** | Task-scoped sandbox | Firecracker microVM, 45min/24h sessions, snapshots; **64 GB ephemeral NVMe default** (SDK ≥3.0.0/custom image; 32 GB on deprecated runtimes — C32 resolved, see "Watch update — 2026-09-23"); Drives public beta (persistent, ≤16 TiB/drive, usage-based pricing) | Active-CPU billing ($0.128/vCPU-hr); Hobby allotment; Pro credit |
| **Cloudflare Sandbox** | Task-scoped sandbox | Containers on Workers, sleeps at 10 min idle, disk resets on sleep | Active-CPU billing ($0.072/vCPU-hr); $5/mo Workers Paid floor |
| **Runloop** | Task-scoped sandbox | Devboxes as "isolated, ephemeral virtual machines" (hypervisor unnamed), Network Policies, SWE-bench focus, suspend/resume (Pro) | $0.108/CPU-hr; free Basic; $250/mo Pro |
| **Blaxel** | Task-scoped sandbox | Perpetual sandboxes, scale-to-zero ~5s, hibernate — acquired by Baseten (announced 2026-09-10); Baseten's newest "Hosted Tools" blog names Blaxel as its sandbox foundation ("fast, isolated, persistent sandboxes and storage where developers can run their own agentic workflows and tool execution") | Per-second usage; SOC 2 Type II / ISO 27001; HIPAA via $250/mo BAA add-on |
| **Microsandbox** | Task-scoped sandbox (OSS) | libkrun microVM, network-layer secret injection | Free, self-hosted (YC F26) |
| **Docker Sandboxes** (morning pass) | Task-scoped sandbox | Local microVMs for coding agents (`sbx` CLI), workspace bind-mounts, **v3 kits** (OCI-based packages: agent workload + reusable mixins for tools/config/credentials/network/instructions — C34), skills tri-state (`off/readonly/readwrite`, read-only default), host-side credential proxying with consent-default-decline, idle auto-stop; centrally managed network/filesystem/MCP policies + sign-in enforcement + audit logs via paid Docker AI Governance | **Free** — `sbx` CLI, incl. commercial use, no per-seat fee ([vendor FAQ](https://docs.docker.com/ai/sandboxes/faq/)); org governance paid (contact sales) |
| **WSO2 Agent Manager** (evening pass) | Task-scoped sandbox (OSS control plane) | k8s pods + [NetworkPolicy egress](https://github.com/wso2/agent-manager/pull/1496) (runtime class unconfirmed), AgentID (OAuth2) per-agent identity, secret injection via SecretKeyRef, MCP proxy governance, real-time agent suspension | Free, self-hosted (Apache 2.0) or managed SaaS (pricing not published); webinar Sep 29; no independent developer reception found yet |
| **boat.dev** (2026-09-22 consolidation) | Task-scoped sandbox | Sandboxes for coding agents; per-second billing, "a stopped sandbox costs nothing"; xlarge (16 vCPU / 32 GB) is capacity-gated — needs a $100+/mo plan *and* operator allocation (vendor statement) | **$0.036/h** default (4 vCPU / 8 GB / 50 GB); xlarge $0.200/h; 25 free-hour trial; $20/mo = $20 of time |
| **DigitalOcean Managed Agents** (2026-09-22 consolidation) | Managed agent stack (task-scoped) | Harness Runtime (microVM per session, pause/resume/fork) + Action Gateway (16,000+ tools via one managed MCP endpoint, credentials brokered at execution time) + Inference Engine; runs unmodified Claude Code / Codex / OpenCode / Hermes / LangGraph | **$0.044/vCPU-hour active CPU** (per-second; active-CPU billing coming soon — interim 25% of allocated vCPUs; "zero while waiting" holds only for paused sessions), $0.0095/GB-hour memory, $0.05/GiB-month snapshots (vendor docs, re-read 2026-09-23 — the 10× discrepancy resolved in favor of the primary source); $5 new-user credit |
| **Boxd** (2026-09-22 consolidation) | Persistent computer | "Composable computers" — KVM VMs with live memory forking in under 200 ms (vendor claim), snapshots/checkpoints, real SSH, per-machine HTTPS subdomain; self-hosted option ("run the whole platform on your own hardware") | Credit-based: €0.049/vCPU-hour running, €0.015/GiB-hour resident RAM, €0.0001/GiB-hour disk written; €30 free credits |
| **Upstash Box** (2026-09-22 consolidation) | Task-scoped sandbox | Snapshot/restore API for reusable prepared environments, branching from snapshots, full outbound networking by default, 22.5 Gbps hosts on AWS; pause/resume unavailable with keepAlive enabled | Pricing not published in the surveyed docs |
| **h-sandbox / Harakiri** (2026-09-22 consolidation) | Task-scoped sandbox (OSS control plane) | Open-source self-hosted sandbox control plane (Apache 2.0); HTTP API / TS SDK / CLI / dashboard; Credential Vault with host-bound egress bindings and fake-env injection (fourth convergent placeholder-swap data point for the secrets-posture corpus) | Free, self-hosted |
| **Brig** (2026-09-22 consolidation) | Local containment (OSS tool) | Local microVM CLI for coding agents — no hosted service; dedicated kernel per sandbox, host-vs-agent trust model, boot-empty credentials with names-only reporting, fail-closed egress-downgrade refusal | Free, local (Apache 2.0) |
| **Epho** (2026-09-22 consolidation) | Task-scoped sandbox | Agents-as-API (claude / codex / opencode harnesses) with automatic multi-provider fallback — the session outlives the machine via session-snapshot restore on replacement boxes | ≈$0.158/h for 2 vCPU / 2 GiB / 10 GiB (computed from per-second rates); $10 starting credit; BYO model keys |
| **DIY floor** | Persistent computer | $4/mo droplet + the human does everything | $4/mo + labor |
| **spark-vm (this project)** | Persistent computer (OSS + hosted-in-design) | Real VM, per-action human approvals (confirmd), credential proxy (swapd), tailnet-first networking | OSS: provider cost + operator time; hosted: TBD (pricing thinking is an open backlog item) |

## TermSquad watch — first pass (R3)

TermSquad is the closest competitor and the newest (launched three days before
this writing), so it gets the full watch treatment.

**Pricing (verbatim from [termsquad.com/pricing](https://termsquad.com/pricing),
2026-09-18):** Starter $9/mo (2 vCPU / 4 GB / 40 GB NVMe) · Builder $19/mo
(4 / 8 GB / 75 GB) · Power $29/mo (6 / 12 GB / 100 GB) · Ultra $49/mo
(8 / 24 GB / 200 GB). Every plan includes: always-on computer, web terminal,
SSH, persistent agent sessions, any-agent support, Squad, Squad Memory,
managed operations, workload protection, backups/restores (the FAQ conditions
this: "where your current computer and plan support the action" — slightly
conditional, not an absolute every-plan feature). Locations across
America, Europe, Asia/Oceania (stock-dependent).

**Session model:** "Closing a tab or losing your connection does not power it
off. Shutdowns, restarts and billing suspension are separate lifecycle
actions." Sessions are Herdr-managed; agents in a persistent session "can keep
working after you disconnect" (with the honest caveat that unattended
completion isn't guaranteed). Stopping the computer is a power action, not a
subscription cancellation — the environment stays associated with the plan.

**Isolation story (scored):** one dedicated "TermSquad Computer" per purchase
— a per-tenant VM boundary, same tier as our per-VM tenant design (signup doc
§9); multiple computers per account are supported, so it's per-computer, not
one-per-customer-max. Public pages say nothing about the hypervisor, the network policy, or
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
sub-agents), Squad Memory (durable shared project knowledge), a
mobile-friendly web terminal, managed backups/restores (conditional — see above), and
multi-region choice. Each is a product
gap to file, not a reason to panic.

**Watch update — 2026-09-18 (pm):** re-checked termsquad.com/pricing and
/features/always-on-cloud-computer — **no change** ($9/$19/$29/$49 stands;
session-model lines match character-for-character). New details from the pm
pass: (1) the FAQ now names a 12-agent roster (Codex, Claude Code, OpenCode,
Cursor, Antigravity, Grok Build, Command Code, Pi, Devin, Kimi Code,
GitHub Copilot, Factory Droid); (2) the launch release confirms TermSquad
uses Herdr for session management — and the upstream reboot-race bug the pm
pass flagged as open ([herdrdev/herdr#3415](https://github.com/herdrdev/herdr/issues/3415):
reboot race that SIGHUPs panes during server shutdown, triggers
`persist.clear`, loses the whole session on next boot) was **already fixed
upstream in herdr v0.9.0 (released 2026-09-07, before the morning survey)** —
the "open upstream bug" characterization is stale (evening-pass correction,
verified via GitHub API). TermSquad's own FAQ
only promises persistence "through *normal* disconnects and reconnects", so
their session persistence rides on Herdr's persist path; whether TermSquad is
exposed now hinges on their **unadvertised Herdr version** (unconfirmed), and host-reboot survival is
unpromised and undocumented;
(3) host-failure restart policy is still undocumented; (4) still no
isolation/security whitepaper, and egress controls are still undocumented on
any public page.

**Watch items for the next pass:** egress-controls documentation (still
unpublished), Herdr session semantics (host-failure restart policy; plus
TermSquad's Herdr version — herdr#3415's reboot-race fix ships in v0.9.0,
so exposure now hinges on their opaque platform version), any isolation
whitepaper, plan/spec changes, any signal of an agent-as-customer offering.

## Axis scorecard 1 — egress controls (scored explicitly, per R3)

Every platform in the benchmark set that documents it can now deny egress by
default; the differences are in granularity, who holds the secrets, and
whether the sandbox can disable the policy.

| Platform | Block-all | Allowlist granularity | Runtime change | Credential injection (agent never holds the secret) |
|---|---|---|---|---|
| **E2B** | `allowInternetAccess: false` | Domains, IPs, CIDRs, wildcards | Yes (`updateNetwork()`) | **Yes (public beta):** per-host request transforms inject headers at the egress proxy, including workload-identity tokens the sandbox never sees |
| **Daytona** | `networkBlockAll` (per MarkTechPost Aug-2026 benchmark) | `domainAllowList` (20 max), `networkAllowList` (10 IPv4 CIDRs) (per MarkTechPost Aug-2026 benchmark) | Tier 3/4 only (confirmed in Daytona's own docs — Tier 3–4 orgs can change outbound policy post-create; Tier 1–2 cannot) | **Yes (verified, [daytona.io/docs/en/secrets](https://www.daytona.io/docs/en/secrets/)):** opaque `dtn_secret_*` placeholder mounted in the sandbox env; outbound proxy substitutes into HTTPS request headers only (bodies, query params, plain HTTP pass through unchanged); per-secret host allowlist (exact + `*.` wildcards; omitted = unrestricted); response scrubbing rewrites real values back to the placeholder |
| **Modal** | `block_network=True` | CIDR + domain allowlists (beta) | Yes, replaceable post-create via `Sandbox._experimental_set_outbound_network_policy` | **Yes:** `secrets=` env-var injection on `Sandbox.create`/`exec` (plus inline secrets and OIDC) — documented; what Modal does *not* document is egress-time credential *brokering* (Vercel/Cloudflare-style), which remains swapd's edge, not the existence of injection itself |
| **Vercel** | `deny-all` incl. DNS | Domains via SNI + IP/CIDR fallback | Yes, no restart | **Yes, on every plan:** credential brokering on egress, matchers by path/method/query/headers; the firewall/broker sits in front of the sandbox with TLS terminated in the proxy — secrets never enter the sandbox |
| **Cloudflare** | `enableInternet=false` | `allowedHosts`/`deniedHosts`, globs | Yes, live | **Yes:** outbound handlers run in the Workers runtime *outside* the sandbox with binding access; `ctx.containerId` scopes credentials per instance |
| **Runloop** | "Network Policies" per devbox (granularity not detailed in docs) | Per devbox, not detailed | Per devbox | Opaque token injection via the account-level Secrets API (raw secret values never exposed to agent code or the Devbox shell, referenced by name) — "Credential Gateway" is not a name Runloop uses in its public docs |
| **Microsandbox** | First-match-wins policy, default-deny | Rules by direction/destination/protocol/ports; DNS interception; `--no-net` lockdown ([networking overview](https://github.com/superradcompany/microsandbox/blob/HEAD/docs/networking/overview.mdx)) | Not documented | Network-layer destination-bound secret injection (substituted host-side, allow-listed destinations only); **OSS, self-hosted** |
| **Northflank** | Deny-all toggle | Allow by workload tags/projects, external IP/CIDR/FQDN; dedicated static egress IPs ([network policies docs](https://northflank.com/docs/v1/application/network/configure-network-policies)) | Config change | Not published |
| **TermSquad** | Not published | Not published | Not published | Not published — raw creds live on the box per their FAQ |
| **AgentComputer** (evening pass) | Not published | Not published | Not published | Not published — egress undocumented on all public pages found; closest evidence is nftables-managed networking in computer-host |
| **spark-vm / swapd** | ssrf.allow/ssrf.deny allowlists | Per-host allowlists | Config-driven | **Yes:** placeholder substitution at the egress proxy — request *and response* bodies scrubbed (76-test suite), 5 MB skip cap with durable audit line, TOTP scrub window; real secret values never enter the guest or the agent's view — only opaque `hsurr:` placeholders |

**Reading:** blocking egress is table stakes and the injection half is now a
converging design — E2B, Vercel, Cloudflare, and **Daytona** all ship some form of
"the proxy holds the secret, the sandbox doesn't." Daytona's own docs (verified
2026-09-18) show the posture fully formed: opaque `dtn_secret_*` placeholders,
outbound-proxy substitution into HTTPS request headers, per-secret host
allowlists, and response scrubbing — the same two halves swapd implements.
swapd's remaining edges are narrower now: (1) it is **open source and
self-hostable** (Microsandbox is the only other OSS entry — a sandbox, not a persistent-box
stack — and its first-match-wins egress policy is now documented, so the
comparison there is mechanism-vs-mechanism, not posture-vs-posture); (2) **request-body-scope substitution** — Daytona
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
resolve allow/deny conflicts in **opposite** directions (E2B: allow wins per the MarkTechPost Aug-2026 benchmark — vendor link to collect in C3; Vercel: deny wins per Vercel's own firewall docs — "Denied ranges take precedence over allowed domains and address ranges") — a policy ported without rewriting doesn't mean the same
thing; and E2B's blocked TCP connections can *look* successful from inside
the sandbox (the firewall accepts before deciding — E2B documents this itself, per MarkTechPost's reporting), so "network is blocked"
must be verified at the application layer, never by `connect()` succeeding.

## Axis scorecard 2 — isolation (scored explicitly, per R3)

| Tier | Who | Boundary |
|---|---|---|
| Dedicated kernel per sandbox | **E2B** (Firecracker microVM) | Hardware-level; strongest in the task-scoped set |
| Per-customer computer | **TermSquad** (dedicated computer), **AgentComputer** (Ubuntu VMs), **Fly Sprites** (Firecracker per user), **spark-vm** (per-VM tenant) | One VM per tenant; cross-tenant attack must escape the hypervisor |
| Syscall-filtered shared kernel | **Modal** (gVisor on the default path; a VM-sandbox alpha now exists) | Stronger than containers, weaker than a VM |
| MicroVM per sandbox, ephemeral | **Vercel** | Firecracker, but the box is disposable |
| Containers on shared infra | **Daytona** (default), **Cloudflare** (Workers containers), **WSO2 Agent Manager** (k8s pods governed by NetworkPolicies — runtime class unconfirmed, could be Kata/gVisor, but the default read is plain pods; self-hosted: same kernel, operator's own workloads) | Kernel shared with other tenants' workloads |
| Configurable | **Northflank** (Kata/Firecracker/gVisor) | Customer picks the tier |

**Reading:** spark-vm's per-VM tenant boundary sits in the same tier as
TermSquad's and above every shared-kernel sandbox default. E2B's
dedicated-kernel-per-sandbox and the per-customer-computer rows are the same
cross-tenant tier — the difference is granularity and lifetime (per sandbox vs
per customer), not boundary strength. The tractable isolation story (signup doc
§9) survives this comparison. What the table
doesn't show, and what sentinel exists to answer: who watches the *inside* of
the box from the outside. Cloudflare's outbound handlers run in the Workers runtime outside the sandbox; Vercel's firewall/broker sits in front of the sandbox with TLS termination in the proxy; our outside observer (sentinel)
is still a design doc, not code. Until it ships, our isolation story is
"good walls, no watchtower" — say so plainly in the security docs.
Evening-pass entry: **WSO2 Agent Manager** now sits in the containers row on
primary evidence (k8s pods + NetworkPolicy egress, runtime class unconfirmed).
The honest comparison when it comes up: our isolation story (own VM, jail)
still outranks pod-level sandboxing, but WSO2 now ships the multi-tenant
identity (AgentID OAuth2) + MCP-governance story we don't — file that gap,
don't minimize it.

## Where spark-vm wins

1. **A real computer that stays yours.** Full OS, unattended background jobs,
   cron loops, your own stack — no session clock at all. Matches TermSquad;
   beats every task-scoped sandbox on the no-session-clock axis by design
   (their billing unit is executions and state is opt-in snapshot/resume, not
   a standing box — the idle economics still punish exactly the workloads a
   persistent box exists for).
2. **Per-action human approvals.** confirmd (mobile-friendly, auto-refreshing,
   two-tap approve, push on the roadmap) — no per-action approval loop found
   in any surveyed **sandbox or computer offering's** docs or product surface
   (2026-09-18). The incumbents isolate sessions or broker credentials; none
   gives the human a per-action approval loop for what the agent is about to
   do. **Caveat (pm watch):** Vercel's `eve` agent *framework* — a separate
   product from the Vercel Sandbox SKU — ships a genuine per-action human
   approval loop ([eve.dev/docs/human-in-the-loop](https://eve.dev/docs/human-in-the-loop);
   per-tool `approval` property, `always()/once()/never()/auto()` policies,
   native approve/cancel across channels (Slack, Discord, Teams, Telegram,
   Twilio, GitHub, Linear per the launch announcement)). So the differentiator holds
   scoped to sandbox/computer *offerings* but is **broken scoped to the
   vendor Vercel** — scope the claim that way in all outward copy (a surveyed
   negative — confirm periodically; see C1).
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
5. **Self-host economics.** The DIY floor ($4/mo droplet) proves the
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
   per a third-party directory table — that table's $20/mo AgentComputer row
   was refuted against the vendor, so treat its speed claims as unverified;
   evening pass: their own OSS repo claims <200ms Firecracker boots — repo ≠
   proven deployment, so still treat production speed as unverified; Fly Sprites
   hibernates after ~30s idle with 100–500ms warm wakes)
   treats fast start as the
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

## Watch update — 2026-09-18 (pm + evening): market moves

Items from the pm watch pass, flagged against the morning survey, with the
evening consolidation's deltas folded in (marked "Evening pass").

- **OpenAI Agents API public beta (Sep 10)** — managed Codex harness with
  first-class sandbox integrations: **Blaxel, Cloudflare, Daytona,
  DigitalOcean, E2B, Modal, Oracle, Runloop, Vercel**; no API fee, pay tokens
  + container time. Evening-pass terms detail (INFERRED, third-party
  characterization of OpenAI's docs): network enabled by default (template
  policy can change), outbound can be disabled or allowlisted, files persist
  across turns while the sandbox exists, artifacts downloadable after expiry,
  **inactive sandbox deleted after 1 hour**; compliance caveat — **US-only
  data residency during beta, no Zero Data Retention even with a self-hosted
  sandbox** (a material enterprise constraint for anyone benchmarking
  "no session clock" stories against the platform default). The biggest
  sandbox-space validation event this month — and Blaxel was named a launch
  partner days after the Baseten acquisition. Platform-shaping; track what
  the default sandbox surface converges on.
- **OpenAI × AWS partnership expansion (announced Apr 28, 2026 — NOT a Sep
  move; evening-pass date correction, INFERRED third-party coverage,
  e.g. [the-decoder](https://the-decoder.com/openai-lands-on-aws-one-day-after-microsoft-deal-restructuring/))** — OpenAI models + Codex on Bedrock,
  "Amazon Bedrock Managed Agents powered by OpenAI" (every agent gets its own
  identity, full auditability, runs inside the customer's environment) — one
  day after OpenAI and Microsoft ended the exclusivity agreement (Apr 27).
  Kept here as background corroboration of the agent-infrastructure
  land-grab thesis, not a sandbox launch: identity + audit +
  customer-environment execution are becoming table stakes.
- **WSO2 Agent Manager GA (Sep 15)** — open-source agent control plane with a
  built-in sandboxed runtime, per-agent identity, and MCP governance. Evening
  pass pins the runtime (VERIFIED, GitHub primary): the sandbox runs as
  **k8s pods governed by NetworkPolicies** ([wso2/agent-manager#1496](https://github.com/wso2/agent-manager/pull/1496)
  — sandboxed pods couldn't mint an AgentID token because the NetworkPolicy
  had no egress rule for the Thunder instance on port 8090), with per-agent
  identity via **AgentID (OAuth2)** and secret injection via SecretKeyRef;
  runtime class unconfirmed (a NetworkPolicy bug fix can't rule out
  Kata/gVisor layers — treat as unconfirmed, not absent). A grounded "sovereign" OSS alternative — Apache 2.0,
  self-host or SaaS; GA adds per-agent per-environment identity controls,
  MCP-level governance, sandboxed runtime, real-time agent suspension.
  Watch adoption; the direct OSS-competitor framing stands, now with a pinned
  runtime.
- **Baseten "Hosted Tools"** — no integration blog/changelog/docs since the
  Sep 10 acquisition, but Baseten's newest blog post explicitly names Blaxel
  as the sandbox foundation: *"Our acquisition of Blaxel accelerates the
  complementary foundation: fast, isolated, persistent sandboxes and storage
  where developers can run their own agentic workflows and tool execution."*
  Evening pass (C11 stays open): the
  [blaxel-ai/sandbox releases API](https://github.com/blaxel-ai/sandbox/releases)
  shows **v0.2.57 (Sep 9), v0.2.58 (Sep 15), v0.2.59 (Sep 18)** — minor
  (v0.2.59: welcome-response API-link tweak; v0.2.58: dep-alert fix +
  unix-socket export skip), correcting the research notes' "latest v0.2.48
  (~Aug 19)" which sourced the docs changelog instead of the repo; "Agent
  Drive" shared filesystem was a ~4-week-ago private-preview announcement
  (LinkedIn recaps), not new. No shipped code-execution product yet; the
  watch stays open for the acquisition-turned-sandbox-product.
- **Microsandbox v0.7.1** — guest filesystem flush policies for snapshots,
  npm provenance, CLI/SDK version separation; weekly changelog cadence
  continues. Egress policy docs now detailed (see scorecard 1).
- **Northflank Network Policies** — now documented: deny-all toggle, allow by
  workload tags/projects and external IP/CIDR/FQDN, dedicated static egress
  IPs. A configurable-Kata/Firecracker/gVisor vendor with documented network
  policy is worth a full pass next time.
- **Runloop re-framing** — docs now call Devboxes "isolated, ephemeral
  virtual machines" (hypervisor still unnamed) and promise "Network Policies"
  for egress. Watch for doc upgrades; Runloop is unscored in scorecard 2
  until the hypervisor is named — its "ephemeral virtual machines" claim would
  place it alongside Vercel's "MicroVM per sandbox, ephemeral" row, not the
  per-customer-computer row.
- **Factory $200M at $5B** (Blackstone, Khosla, Sequoia, NEA) — coding-agent
  infra, adjacent demand signal, not a sandbox move. (Factory Droid is on
  TermSquad's agent roster.)
- **AgentComputer** — evening pass covers it on primary sources (see the
  at-a-glance table): own open-source Firecracker-based VM manager
  ([computer-host](https://github.com/AgentComputerAI/computer-host) +
  [computer-guest](https://github.com/AgentComputerAI/computer-guest), 2 stars
  each, updated 2026-04-30), Firecracker microVMs + jailer on bare metal,
  SSH/browser access, NVMe home, hot vs cold (stopped) storage, new
  Enterprise tier. Confirmed in the "Per-customer computer" isolation tier
  (placement stands; the evening pass confirms the mechanism — own
  open-source Firecracker stack on bare metal, not Sprites resale). The
  Sprites-reselling theory is downgraded to unexplained
  rate-card parity. **Egress stays the only thin spot** — undocumented on all
  public pages (C12 narrows to egress-only).

## Watch update — 2026-09-19 (night + morning + midday): market moves and verifications

Three delta watch passes (night ~23:57–00:30 CDT, morning ~04:57–05:30, midday
~10:55–11:35), each delta-only against the previous pass, folded here. The
morning pass closed the research run's five queued verification items against
primary sources, with two factual corrections to the queue. **VERIFIED** = read
on a vendor's own page, doc, repo, or security announcement in a watch pass
(link inline). **INFERRED** = third-party characterization, labeled as such.

- **Docker Sandboxes — sandbox-escape week (four vulnerabilities, one release).**
  **VERIFIED (Docker's own
  [security announcements](https://docs.docker.com/security/security-announcements),
  fix shipped in 0.42.0 on Sep 7, records published Sep 15):** CVE-2026-77179
  (Critical, macOS only, 0.28.0–<0.42.0; CVSS 9.4 per third-party trackers, not
  vendor-stated) — "the virtio-fs host server on macOS followed symlinks when
  reopening an unlinked file from a stored path. A malicious guest could replace
  a parent directory with a symlink, escape the shared workspace, and read or
  modify arbitrary host files as the VMM user, potentially leading to code
  execution on the host"; CVE-2026-79994 (High, CVSS 8.7 per third-party
  trackers, not vendor-stated, 0.37.0–<0.42.0) — "the guest-to-host Unix domain
  socket relay checked that a socket path was inside an authorized workspace
  but reconnected using the path name." No exploitation mentioned in the
  vendor announcement. **CORRECTION to the queue:** the queue tied these to
  Docker Desktop — **no evidence ties either CVE to Docker Desktop; both are
  Docker Sandboxes only.** **INFERRED (Severity Daily, quoting Docker's own
  release notes):** the same 0.42.0 release notes (roughly thirty bug-fix
  entries) contain two more *explicitly-described-as-vulnerabilities* entries —
  host D-Bus transport opened by a sandboxed process to "execute an arbitrary
  command on the host", and cross-sandbox OAuth login hijack by pre-claiming
  the callback port — neither CVE named in the notes at all; the critical
  virtio-fs fix shipped unlabeled, eight days before the CVE records. Docker
  has not connected the D-Bus fix to either CVE. The D-Bus/OAuth quotes are
  third-party-quoted-from-vendor, not yet read directly on the vendor's
  release-notes page — a direct read is owed before any derivative publishes
  them. Docker's stated remediation (third-party press roundup): upgrade to
  0.42.0+, or use `--clone` mode — with Docker's own caveat that clone mode
  mounts the repo read-only at `/run/sandbox/source` but **does not prevent
  reads** (untracked files such as `.env` stay readable inside the sandbox).
  CVE-2026-79994's record initially listed a never-published 0.41.0 as the fix
  version, corrected to 0.42.0 ~1h after publication. Credits: Oren Yomtov of
  accomplish.ai (CVE-2026-77179), Jurre van Bergen of ThreatNotify
  (CVE-2026-79994). **v0.43.0 (Sep 15) trust-model tightening, VERIFIED in
  Docker's own release notes:** `shareSkills` in `sbxenv.yaml` replaced with
  `skills` (`off|readonly|readwrite`); MCP OAuth client secrets renamed to
  `mcp:<server>:client_secret` (old name no longer read); env files can
  reference `${{ env.projectDir }}` / `${{ env.fileDir }}`. **Implication:**
  the shared-workspace boundary is the trust story of a persistent-VM-for-agents
  product, and this is the loudest object lesson that "a microVM + mounted
  host folder" is a fragile model. spark-vm's full-VM-without-host-folder-sharing
  design is outside the shared-workspace guest→host sub-class both CVEs broke
  (win #3 adjacent), while the D-Bus daemon-boundary and OAuth port-claim
  classes are owned-risk categories any managed product retains — including a
  hosted spark-vm — so treat them as owned risks, not solved-by-architecture.
  Docker is actively converging on "agent runs without keys inside"
  (read-only skill sharing by default, host-side credential proxying), so the
  credential-proxy differentiation (win #3) must rest on persistence +
  request-body-scope substitution + open source, not isolation hygiene alone.
  Strong raw material for the O13 trust/transparency doc, with the honest
  scoping above. **Corpus note:** Docker Sandboxes enters the watch corpus
  via this event (security event, not a full profile yet). **2026-09-19
  evening pass: at-a-glance row added with the vendor-verified price
  signal (`sbx` CLI free; org governance paid); the D-Bus/OAuth
  vendor-quote debt closed — both quotes are now vendor text from the
  release notes, and the notes now name CVE-2026-77179/79994 (the
  consolidation's morning read showed no CVE names; the amendment timing
  is the author's inference, not vendor fact; see
  `docs/COMPETITOR_WATCH_2026-09-19_EVENING.md`).
- **Cloudflare × Cursor (Sep 2) — new to the corpus, pre-window.** **VERIFIED
  (Cloudflare's own
  [press release](https://www.cloudflare.com/press/press-releases/2026/cloudflare-expands-support-for-ai-coding-agents-with-cursor-cloud-agents-on-cloudflare-sandboxes/),
  Sep 2, 2026):** Cursor Cloud Agents' tool work (terminal, filesystem,
  browser) can execute inside **Cloudflare Sandboxes in the customer's own
  Cloudflare account**, while Cursor keeps the agent loop (inference,
  planning, orchestration) via Cursor Self-Hosted Machines; outbound HTTPS
  from the worker to Cursor's backend; no inbound access into the customer
  network. Framed as a pattern, "builds on Cloudflare's work with other
  leading AI agent platforms, including Devin Outposts and Claude Managed
  Agents." **Implication:** the customer-controlled-execution thesis now has
  a big-vendor execution-layer play — execution inside the customer's own
  Cloudflare account rhymes uncomfortably with "your own computer", so do not
  pitch control as the differentiator. The axes this move does not contest are
  **persistence** and the **approval loop**. Note the mirror for the hosted
  vision: spark-vm hosted is also converging toward provider-infra,
  customer-scoped execution, so the hosted differentiation story cannot rest
  on account-scoping either. Candidate one-line note for
  `docs/POSITIONING.md`, reworded around persistence + approval loop.
- **GitHub Copilot — enterprise-managed sandbox controls (JetBrains IDEs,
  public preview).** **VERIFIED (GitHub Changelog,
  [Sep 8, 2026 entry](https://github.blog/changelog/2026-09-08-enterprise-managed-sandbox-in-copilot-for-jetbrains/);
  CORRECTION to the queue, which dated this Sep 16):** "Enterprise
  administrators can now centrally configure sandbox behavior for GitHub
  Copilot in JetBrains IDEs. Managed policies can control sandbox
  enablement, filesystem and network access, proxy settings, developer-tool
  access, macOS Keychain access, and more." "Managed restrictions take
  precedence over user settings. Copilot locks affected controls in the IDE
  and identifies settings managed by your organization" — plus enterprise
  policy diagnostics. **Implication:** GitHub is turning every Copilot
  install into a centrally-governed execution environment; "governed sandbox"
  is becoming enterprise table stakes. The hosted-product pitch needs an
  org-policy layer to compete with enterprise expectations, not just
  solo-developer isolation (H16; the org-policy research pass already folded
  this, PR #101).
- **OpenRouter `openrouter:shell` (beta) — VERIFIED
  ([server-tools docs](https://openrouter.ai/docs/guides/features/server-tools/shell)):**
  "The `openrouter:shell` server tool gives a model a hosted shell: a
  sandbox-backed clone of OpenAI's hosted `shell` tool that works with any
  model." "OpenRouter executes the commands in order, each in its own
  invocation, inside a sandboxed container." Ephemeral-sandbox pricing
  $0.0001/active-second (THIRD-PARTY roundup). **Implication:** ephemeral
  hosted sandboxes are being commoditized as an API primitive. spark-vm's
  moat is the opposite direction — persistent, stateful VMs with sign-up —
  so positioning should lean hard into persistence and long-lived agent
  workflows, not compete on ephemeral exec. Per-second ephemeral exec is the
  pricing floor; per-computer persistence is the premium (C2).
- **Tencent BrowserSkill — open-sourced (June 2026, coverage Sep 18).**
  **VERIFIED ([github.com/tencent/browserskill](https://github.com/tencent/browserskill)
  README + PRIVACY.md):** "BrowserSkill connects Cursor, Claude Code, Codex,
  OpenClaw, CodeBuddy, WorkBuddy, Pi, Hermes Agent, and other shell-capable
  AI agents to your already logged-in browser." Browser tasks run in a
  separate, visible Agent Window; Rust `bsk` CLI/daemon + Chrome/Edge
  extension; agents reuse real login state; per-tab borrow/return consent;
  human-in-the-loop handoff for captchas/logins. **Implication:**
  real-authenticated-browser automation is now mainstream agent capability,
  not a hack — an "agent window"-style isolated-but-logged-in browsing
  surface is a feature users will expect on spark-vm, and the
  borrow/return consent model is a good pattern to reuse for anything
  spark-vm does with user credentials.
- **TermSquad (C1) — no in-window moves; spec completed, watch-method gap.**
  **VERIFIED (termsquad.com/pricing, refetched 2026-09-19):** $9/$19/$29/$49
  unchanged — Starter $9 (2 vCPU / 4 GB / 40 GB), Builder $19 (4 / 8 / 75),
  **Power $29 = 6 vCPU / 12 GB / 100 GB**, Ultra $49 (8 / 24 / 200 NVMe).
  FAQ reorganization
  (stop-behavior, backup/restore, multi-region America/Europe/Asia-Oceania) —
  doc depth, not a product signal; session model and agent-as-customer
  absence unchanged. **Watch-method gap:** TermSquad routes product updates
  to x.com/trytermsquad, which is login-gated for read-only fetches — the
  "no new announcement" call covers the open web only; find a non-gated
  update surface (C1).
- **WSO2 Agent Manager (C10) — reception: thin; stays open.**
  INFERRED (wire republication, Sep 16–18): GA coverage remains
  wire-syndication of the Sep 15 announcement, plus a badsignal.ai editorial
  take (third-party, from the midday pass); no broad independent developer
  reaction beyond that. Wire-claimed traction details (INFERRED, vendor-sourced —
  claims to corroborate, not adoption evidence): Forrester Agent Control
  Plane Landscape Q2 2026 inclusion; AI Tech Awards 2026 "Best Innovation in
  Open Source AI"; Agentic AI Foundation membership; OpenID Foundation
  whitepaper co-authorship. Technical corroboration (VERIFIED,
  [wso2/agent-manager#1390](https://github.com/wso2/agent-manager/pull/1390),
  OTel ingestion on VM installs): the sandbox NetworkPolicy `except` list
  exists in the wild — consistent with the k8s-pod + NetworkPolicy egress
  pinning. Next milestone: Sep 29 webinar.
- **Baseten/Blaxel (C11) — nothing shipped; stays open.** VERIFIED (GitHub
  releases): no `blaxel-ai/sandbox` releases after v0.2.59 (Sep 18);
  v0.2.59 = sandbox-welcome-response API-link tweak, v0.2.58 = dependabot
  patches + unix-socket export skip — maintenance, no capability or pricing
  change. The `deepseek-harness-blaxel-sandbox` IDE plugin shipped 0.1.2
  (Sep 3); 0.1.3 unreleased. INFERRED: Baseten's only post-acquisition
  product news is a Google Cloud Marketplace launch + Hybrid Mode early
  access — not a code-execution offering.
- **OpenAI Agents API (C9) — nine partners, unchanged; stays open.**
  INFERRED (third-party roundups): still Blaxel, Cloudflare, Daytona,
  DigitalOcean, E2B, Modal, Oracle, Runloop, Vercel; beta terms unchanged
  (1h inactive deletion, US-only residency, no ZDR even self-hosted). No
  adoption figures disclosed. Third-party ephemeral-exec pricing datapoint
  ([aicraftjournal](https://aicraftjournal.com/articles/openai-agents-api-public-beta-no-extra-fee-hosted-sandbox-1gb-003),
  unverified against OpenAI's own pricing page): OpenAI-hosted sandbox 1 GB
  at **$0.03/20min** — directional floor for C2, not corpus fact.
  Observation: the Agents API separates the harness (OpenAI runs the loop,
  sessions, compaction) from execution (your infra / partner sandbox / VPC),
  normalizing bring-your-own-sandbox as a first-class shape — which supports
  the hosted spark-vm pitch: a *persistent, full-VM, sign-up-and-use*
  computer where the platform operates the loop and the tenant's box is the
  execution plane, positioned against the ephemeral-exec pricing floor rather
  than competing with it.
- **AgentComputer (C12) — egress-only, confirmed.** VERIFIED (GitHub API):
  `AgentComputerAI/computer-host` and `-computer-guest` untouched since
  2026-04-30, no releases, pricing/docs unchanged; egress still undocumented
  on all public pages. The org was formerly getcompanion-ai ("Companion") —
  search color for future passes. The narrowed C12 stands.
- **FastGPT v4.16.0 (Sep 14) — small provider-switch signal.** INFERRED (PR
  Newswire recap): v4.16.0 deprecates the E2B sandbox-provider config;
  existing E2B users must switch to `opensandbox` or `sealosdevbox`
  providers (new sandbox tuning vars: CPU, memory 2048 MiB, storage 1 GiB,
  auto-suspend 60 min, auto-archive 7 days). One line, not a backlog item:
  an OSS agent-platform deprecating E2B as a sandbox provider suggests the
  task-scoped sandbox defaults are less sticky than their partner logos
  imply.
- **Surveillance result:** otherwise quiet across the tracked set in all
  three windows — no launches, pricing/tier changes, or partner moves
  (E2B, Daytona, Modal, Runloop, Northflank, Vercel, Cloudflare, GitHub
  Copilot, OpenRouter, Tencent, WSO2 beyond the above). Out-of-window
  context: "Plugin4Shell" 0-click RCE (Sep 17, Air security startup; Claude
  Code and Codex patched, Gemini CLI deprecated, Copilot unpatched —
  third-party) — an agent-ecosystem security signal for any trust doc, but
  pre-window.

## Watch update — 2026-09-22 (night): deferred-entry consolidation

This pass folds the deferred C-entries (C17/C18/C19/C20/C26/C29/C30/C31) —
watch items whose "canonical competitor-entry fold" was explicitly deferred
to the next corpus consolidation — into the field table above. No new
vendor-page reads this pass: every figure below carries the verification
provenance of the pass that produced it (see the linked watch docs). The
2026-09-22 watch docs' other deltas are not folded and stay live — this
includes the NIGHT pass's (Sentinel deep-dive and standing items), which
is why it appears in the not-archived list below.

### boat.dev — first corpus entry (C17, RESOLVED)

Task-scoped sandboxes for coding agents.
**VERIFIED** (vendor pricing page [docs.boat.dev/pricing](https://docs.boat.dev/pricing),
read 2026-09-21 ~13:00 CDT; resolves C17 — see
`docs/COMPETITOR_WATCH_2026-09-21_C17.md`): default 4 vCPU / 8 GB / 50 GB at
**$0.036/h**, per-second billing, "a stopped sandbox costs nothing"; $20/mo
plan = $20 of time (≈555 h of `default`); concurrency 100/300/1,000/2,000
across the $20–$2000 plans; 25 free-hour trial (`small`/`default` only).

The xlarge caveat (16 vCPU / 32 GB / 251 GB, $0.200/h): needs a $100+/mo
plan *and an operator to allocate the capacity* (vendor's own footnote,
"ask us" on X). Two reads ~9h apart cannot date the note against the
~Sept-19 page refresh, so the temporal question is settled at "current
policy" — but 16-vCPU is **capacity-gated today** by vendor statement.
Any Fly-vs-boat sizing math must carry the capacity-allocation
contingency. Their comparison table still lists E2B/Daytona at $0.331/h
default ($0.166/h small) — boat.dev remains the cheapest viable provider
candidate on the published rate card.

### h-sandbox / "Harakiri Sandbox" — first corpus entry (C18, RESOLVED)

Open-source self-hosted sandbox control plane (Apache 2.0,
[github.com/nabilblk/h-sandbox](https://github.com/nabilblk/h-sandbox) @
`79d1151`, docs current to 2026-09-14; **VERIFIED** against the project's
own docs 2026-09-21 ~21:00 CDT — see
`docs/COMPETITOR_WATCH_2026-09-21_C18.md`). HTTP API, TS SDK, CLI,
dashboard; environments/templates/workspaces; Credential Vault with
host-bound egress bindings and fake-env injection; OpenSandbox as the
execution adapter. Public source launch 2026-09-09 (pre-window).

Credential Vault = the **fourth convergent data point for the
placeholder-swap pattern** (after Daytona, Microsandbox, opencomputer.dev —
joined 2026-09-22 by DigitalOcean Managed Agents as the fifth, C26):
opaque placeholder in the sandbox, real value substituted at the
provider-side egress boundary, destination-scoped. Their own trust-model
words: "The sandbox sees only fake environment variables or no variables
at all. The provider injects the real auth material only for outbound
requests that match the binding." Mechanistic notes for the corpus: the
substitute is the provider-side egress sidecar (experimental transparent
mitmproxy, per upstream OpenSandbox docs) — a *layering* difference from
swapd, which owns and operates its intercepting proxy; the injection
surface is narrower (auth material only — no body/query/path substitution
claim found); **no response scrubbing documented** (the threat model
admits the residual: "a malicious allowed destination can reflect received
credentials in its response"); fail-closed enforcement ("Harakiri does not
fall back to open outbound access … when enforcement is unavailable").
Feeds R6 (vault comparand) and H4 (OpenSandbox-adapter data).

### Brig — first corpus entry (C19, CLOSED by the C19/C20 consolidation)

Local microVM containment CLI for coding agents, by NOFire AI, Apache 2.0,
prerelease `0.1.0-rc` (**VERIFIED**: [github.com/brig-sh/brig](https://github.com/brig-sh/brig),
surveyed 2026-09-22 ~02:55–03:10 CDT — see
`docs/COMPETITOR_C19_C20_BRIG_EPHO.md` §1). No hosted service, no pricing
page, no multi-tenant story: Brig is a single-user local containment tool.
Its comparable surface is the self-hosted / jail track.

Substrate: dedicated kernel per sandbox (macOS 15+ uses the `hvi` backend
of the `hull` runtime; macOS 14 uses `vz`; Linux x86-64/arm64 uses the
`urunc` shim over KVM via nerdctl/containerd; Intel Macs unsupported) —
same isolation tier as E2B's Firecracker microVMs, but the trust model is
**host-vs-agent containment**, not tenant-vs-tenant. It does not belong in
the multi-tenant scorecard rows; it is a new entry in the local-containment
column alongside our jail.

Credential handling (bars for our own surfaces): the guest boots with
**zero credentials** — credentials reach it only by per-exec delivery
through profile bindings; `brig info` reports binding *names* only (a test
fails their build if a value ever reaches the output); a `deny` billing
guard refuses to forward e.g. `ANTHROPIC_API_KEY` when doing so would
silently move the sandbox off a subscription onto metered billing.

Egress: policy enforced **only** on hull's `hvi` backend — and Brig
**refuses a policy-bound run on any other backend rather than run it
unenforced** (the fail-closed downgrade pattern: never silently run a
restricted workload on a substrate that cannot enforce the restriction).
`shell`/`gui` profiles cannot carry a policy at all (parse-time refusal).
Image verification, by contrast, defaults to `warn` (boots unverifiable
images unless `BRIG_VERIFY=require`) — a documented tradeoff ours should
answer explicitly rather than imply parity.

Profiles: eight built in — six `kind: agent` (`claude-code`, `codex`,
`cursor`, `gemini`, `grok`, `opencode`), one `kind: gui`
(`claude-desktop`), one `kind: shell` (`ubuntu`). Precision point:
`cursor` declares `unpublished: true` (so `brig run` refuses it before the
registry), but the profile's own `desc:` labels it an "example profile" —
a launch-list vs shipped-state mismatch documented in-repo, minor
severity, not a broken launch promise.

Competitive read: Brig answers none of the hosted questions (no
provisioning, no multi-tenant boundary, no approvals plane, no outside
observer, no provider abstraction). A complement to the self-hosted track,
not a substitute for the hosted vision.

### Epho — first corpus entry (C20, CLOSED by the C19/C20 consolidation)

Agents-as-API by Bruin Data Limited, launched ~Sep 7
(**THIRD-PARTY**: Product Hunt launch post; epho.io VERIFIED for the
mechanics below — see `docs/COMPETITOR_C19_C20_BRIG_EPHO.md` §2).
`POST /api/v1/chat` with a harness, model, prompt, provider key, and repos
spins up a sandbox, configures the chosen harness (claude / codex /
opencode), clones repos, wires MCP servers, and streams the agent's work
back as server-sent events. Task-scoped, session-clocked — the shape the
hosted thesis rejects ("a real computer that stays yours"). Its
*reliability* engineering is the thing to learn from, not its product
shape.

Multi-provider fallback (VERIFIED): "the run re-queues on a fallback
sandbox backend," and a durable chat's "conversation outlives the machine
it ran on" via session-snapshot restore — automatic fallbacks across
providers when one fails (underlying provider identities are
UNVERIFIABLE publicly — not named). This validates the layer **above**
H4's provider-agnostic interface: a failover router that keeps a session
alive across provider failures. H4's capability axes are exactly what such
a router needs to pick a fallback target; the router itself is not
designed. The honest boundary: `provider_iface` already ships `snapshot()`,
so the missing design is the **cross-provider session-state restore
contract** (which verbs the router drives, how a session survives a
provider failure when VM-snapshot restore is not portable across
providers) — an open H4 follow-up.

Pricing (VERIFIED: epho.io): per-second meter, boot to teardown — "nothing
idles, nothing is stored, nothing keeps billing." $0.0000164/vCPU-s,
$0.0000053/GiB-s, $0.000000036/GiB-s; the default 2 vCPU / 2 GiB / 10 GiB
instance is ≈ **$0.158/h** (computed) — within ~5% of E2B's first tier
(**INFERRED**, with a shape caveat; the E2B figure is from boat.dev's
published comparison table) — so Epho's differentiator is reliability,
not price. BYOK: model tokens billed
by your provider, never by Epho; $10 starting credit; a turn is refused
with 402 at zero balance.

### DigitalOcean Managed Agents — first corpus entry (C26, CLOSED 2026-09-23 — vendor-docs pricing verified)

Public preview launched 2026-09-22 (**VERIFIED**: vendor press release,
Business Wire 2026-09-22 — paid wire = the vendor's own claims; product
page read VERIFIED in the 2026-09-22 evening pass — see
`docs/COMPETITOR_WATCH_2026-09-22_MORNING.md` §1 and
`docs/COMPETITOR_WATCH_2026-09-22_EVENING.md` §§1–2). The first
major-cloud, full-stack managed agent-computer product with published
sandbox pricing (INFERRED — the morning watch's characterization) —
squarely in the #47 hosted-product lane.

Two vertically integrated services plus inference, one security model, one
billing model: **Harness Runtime** — microVM per session, hardware-layer
isolation, separate secrets service, Chromium + coding sandbox,
pause/resume/fork, conversational-history persistence; **Action Gateway** —
governed access to 16,000+ tools from 500+ providers through one managed
MCP endpoint, "credentials are brokered at execution time and never reach
the model or the sandbox" (the **fifth convergent placeholder-swap data
point** for the secrets-posture corpus), centralized permissions,
human-in-the-loop approval for sensitive actions; **Inference Engine** —
serverless inference on open + proprietary models, intent/cost/latency
router. Runs unmodified Claude Code / Codex CLI / OpenCode / Hermes /
LangGraph; custom agents as OCI images; customers quoted: OpenHands
(Agent Canvas), Qencode, Amplitude (Wave); $5 new-user credit.

Pricing: **$0.044/vCPU-hour active CPU** (per-second on actual CPU
consumed — docs footnote: "Active CPU billing is coming soon. Until then,
you will be billed at 25% of the vCPUs allocated to your sandbox"),
$0.0095/GB-hour peak memory, **$0.05/GiB-month snapshots** — all VERIFIED
on the vendor docs page (re-read 2026-09-23 mid-evening; page stamped
"Last verified 22 Sep 2026"). The corpus's earlier $0.005/GiB-month
figure came from the syndicated release, not the docs; the 10×
snapshot-rate discrepancy (C26 watch item, carried as caveat in the
mid-afternoon fold) is RETIRED in favor of the primary source. So the
"zero while waiting" read of the headline rate is qualified: it holds
only for paused sessions; a waiting-but-live sandbox costs 25% of
allocation until active-CPU metering ships. Sandbox shapes
(full-allocation hourly): XSmall `mars-1vcpu-1gb` $0.0535/hr; Small
`mars-2vcpu-2gb` $0.107/hr; Medium (default) `mars-2vcpu-4gb` $0.126/hr;
Large `mars-4vcpu-8gb` $0.252/hr; XLarge `mars-16vcpu-32gb` $1.008/hr.
Also VERIFIED on the docs page: session storage (volumes) $0.05/GiB-month
(peak storage consumed), custom sandbox templates (BYOT) $0.05/GiB-month,
public internet egress $0.01/GiB; paused sessions incur no compute
charges; retained checkpoints keep accruing storage charges while paused
(including at $0 prepaid balance); the runtime requires a positive
prepaid balance with no per-product spend limit. Auto-pause stops
CPU+memory charges (paused = no compute charges; the 25% interim figure
applies to waiting-but-live sandboxes).
(vendor, not measured): **305 ms resume-from-pause** ("46% faster than
other leading offerings" — also their own measured p50; the product page
says "about 200 milliseconds" — treat both as vendor claims, C14 input
discipline), 37% lower TCO vs an unnamed "leading independent sandbox
provider" (INFERRED: E2B).

Competitive inputs: active-CPU metering vs spark-vm's flat-monthly Tier 1
thinking (filed in `docs/PRICING_THINKING.md` §2); 305 ms as the number to
beat for C14; Action Gateway as an H16 org-policy vendor candidate; DO's
OpenAI partner status (C30 below) sharpens C26.

### Boxd — first corpus entry (C29, VENDOR-VERIFIED — watch continues)

$2M pre-seed (~Sept 16, **THIRD-PARTY**: BlueYard Capital lead; OVNI,
Antler, S20, Script Capital + angels — runtimewire.com, 6ic.com,
todaysstartupnews). Product: "Composable computers" — persistent KVM VMs
(default 2 vCPU / 8 GB RAM / 100 GB disk, Ubuntu 24.04), real SSH
(scp/rsync/Remote-SSH), each machine gets an HTTPS subdomain
(`<name>.boxd.sh`), MCP server for Claude Code / Codex / opencode, CLI +
TypeScript/Python SDKs + API (**VERIFIED**: boxd.sh +
docs.boxd.sh/quickstart read 2026-09-22 ~20:03–20:06 CDT — see
`docs/COMPETITOR_WATCH_2026-09-22_LATE_EVENING.md` §2; the SDK install URL
is VENDOR-ATTESTED as of the 2026-09-22 overnight pass
(`docs/COMPETITOR_WATCH_2026-09-22_OVERNIGHT.md` §2a: boxd.sh serves the
genuine 532-line installer; canonical path `boxd.sh/downloads/cli/install.sh`,
byte-identical content).

Fork: "Live memory forking of machines, **in under 200 ms**" — disk +
memory + every running process (vendor's own pages); the press's <100 ms
headline stays THIRD-PARTY/UNVERIFIED. **Active-network-connections forking
is NOT vendor-attested** — the vendor says fork carries "every running
process"; process-state preservation and TCP-connection preservation are
orthogonal (Sprites' own docs exhibit exactly this split: processes "pick
up mid-thought" while "open TCP connections do not survive a pause"). No
vendor claims connection-preserving fork — treat the mechanism as
unproven, not contradictory.

Snapshots freeze and restore a machine "down to the running processes";
checkpoints are in-place rollback of the same machine. Pricing (vendor
FAQ): credit-based — **€0.049/vCPU-hour** while running, **€0.015/GiB-hour**
resident RAM (running or standby), **€0.0001/GiB-hour** of disk actually
written; hibernated machines pay disk only; **€30 free credits**. Idle
machines "suspend to disk, resume in under a millisecond on next
connection" — marketing-page figure, no methodology published; NOT a C14
benchmark input. Self-hosted: "Run the whole platform on your own
hardware." (VERIFIED).

Competitive read: funded, KVM-native persistent-machine competitor whose
fork/resume semantics overlap #179's lifecycle and #47's branching
control plane. The measured figures stay vendor-published only (Sprites
warm 100–500 ms, DO 305 ms p50); Boxd's are marketing with no methodology —
directionally interesting, not citable. Watch, don't react.

### OpenAI Agents API — harness↔compute split (C30, datapoint on the existing C9 tracked item)

The Sept-10 public beta's nine first-class sandbox partners (Blaxel,
Cloudflare, Daytona, **DigitalOcean**, E2B, Modal, Oracle, Runloop, Vercel —
the vendor's own launch post, VERIFIED on openai.com this run — see the
2026-09-23 mid-afternoon watch update below) formalize the **harness↔compute
split** (INFERRED from the partner list, not an OpenAI claim): model
providers ship harness code while compute platforms own isolation.

Design implication for the hosted product: spark-vm competes on the
compute/execution layer while harness choice is BYO — per-harness adapters
(OpenSandbox-style contract) keep the hosted product portable across
harnesses rather than building compute around one harness. Feeds H4's
provider-adapter discussions. DigitalOcean's partner presence sharpens
C26 above.

### Upstash Box — first corpus entry (C31, mechanics datapoint)

First competitor-corpus entry for Upstash (previously corpus-ed only as a
per-box-policy datapoint in `docs/ORG_POLICY_RESEARCH.md` §2). Mechanics
from the vendor's own docs ([how-it-works.mdx](https://github.com/upstash/docs/blob/HEAD/box/overall/how-it-works.mdx),
launch date not established — not a corpus timing claim): snapshot/restore
API for reusable prepared environments, branching from snapshots, full
outbound networking by default, 22.5 Gbps hosts, on AWS; pause/resume not
available when keepAlive enabled. Pricing not published in the surveyed
docs.

## Watch update — 2026-09-23: C32 resolution + Vercel storage pricing

Two primary-source VERIFIED items this pass (both read on
[vercel.com/docs/sandbox/pricing](https://vercel.com/docs/sandbox/pricing),
page metadata `last_updated: 2026-09-10`, read 2026-09-23 ~02:05–02:15 CDT
by two independent surveyors; watch doc
`docs/COMPETITOR_WATCH_2026-09-23.md`).

**C32 resolved — 64 GB default confirmed.** The overnight pass's carried
ask (whether the THIRD-PARTY blog claim of default storage moving 32→64 GB
had any vendor confirmation) is answered: *"Each sandbox created with
Sandbox SDK 3.0.0 or above, or from a custom image, is automatically
provisioned **64 GB of ephemeral NVMe storage**. Sandboxes created with
**runtimes (deprecated) receive 32 GB**."* Per-plan quota table: Disk
size **64 GB** on Hobby/Pro/Enterprise. The claim was real; 32 GB survives
only on the deprecated runtime path. The UNVERIFIABLE qualifier is retired.

**Drives pricing datapoint (completes the Sept 22 public-beta entry).**
Drive Storage $0.05/GB-month (Pro/Enterprise; Hobby 15 GB lifetime);
Drive Reads $0.0015/GB (Hobby 30 GB/mo); Drive Writes $0.004/GB (Hobby
30 GB/mo); max 4 drives per run; default drive 1 TiB (1 GiB Hobby);
16 TiB max per drive; sandbox downloads free (outbound + exposed-port
traffic billable); Pro sandbox usage charges against the $20/month
credit; session caps 45 min Hobby / 24 h Pro+Ent; concurrency 10 /
10,000. Persistent disk as a metered first-class sandbox feature is now
price-anchored — the same direction as Boxd's persistent-machine thesis
and spark-vm's persistent-VM positioning; feed the "where spark-vm
wins/lags" framing on the next full consolidation.

## Watch update — 2026-09-23 (morning): Daytona v0.216.0, Docker v3 kits

Two primary-source VERIFIED items this pass (vendor pages re-read
2026-09-23 ~04:56–04:58 CDT by independent surveyors; watch doc
`docs/COMPETITOR_WATCH_2026-09-23_MORNING.md`). Tracked set otherwise
quiet (6/8 NO-CHANGE); Vercel Drives still public beta
(`last_updated: 2026-09-10`, no GA move); market news window quiet.

**C33 — Daytona v0.216.0 (watch-doc color only).** The changelog top
entry (SEP 23) hardens the SDK build context: *"Daytona 0.216.0
restricts Dockerfile COPY sources to the build context in the Python,
Ruby, and TypeScript SDKs"* — incident-driven trust-boundary
hardening of a classic breakout vector (INFERRED). Filed as routine watch color;
no corpus fold, no positioning change.

**C34 — Docker Sandboxes v3 kits: OCI-packaged agent kits with mixins.**
Release notes (2026-09-21): *"Docker Sandboxes now supports v3 kits:
OCI-based packages that combine an agent workload with reusable mixins
for tools, configuration, credentials, network access, and agent
instructions."* The corpus's sandbox thesis has been moving toward
per-harness adapter packaging (H4's OpenSandbox-style adapter contract:
harness code + compute isolation as a deployable unit); Docker has now
shipped a packaged implementation of that idea (INFERRED), as an OCI
artifact. Keep
OCI-shaped packaging on the table in H4's adapter-design discussions.

## Implications → backlog

- **C1 — TermSquad recurring watch** (competitor): egress-controls docs,
  Herdr session semantics (host-failure restart policy; plus TermSquad's
  unadvertised Herdr version — herdr#3415's reboot-race fix shipped in v0.9.0
  (2026-09-07), so exposure now hinges on their opaque platform version
  (evening pass)),
  any isolation whitepaper, plan/spec
  changes, agent-as-customer signals. Also watch for any vendor shipping a
  per-action human approval loop — win #2's differentiator is a surveyed
  negative, confirm it periodically, and **survey agent frameworks too**
  (Vercel `eve` ships one as a separate product from the Sandbox SKU). R3's
  first pass is done; the pm watch pass is done; the evening consolidation is
  done (this doc); the watch continues. 2026-09-19 pass adds: find a non-login-gated TermSquad update surface (x.com/trytermsquad is login-gated; the "no new announcement" call covers the open web only).
- **C2 — Pricing-page inputs** (sales): TermSquad $9–$49, AgentComputer
  usage-based PAYG (no flat plan published — earlier $20/mo directory claim
  refuted; new Enterprise tier observed 2026-09-18, absent from the morning
  survey, pricing unpublished), E2B Pro $150 floor, DIY $4/mo — feed the
  pricing-page thinking item and R4. 2026-09-19 pass adds the ephemeral-exec
  floor: OpenRouter `openrouter:shell` ~$0.0001/active-second (third-party
  roundup) and OpenAI-hosted sandbox 1 GB at ~$0.03/20min (third-party,
  unverified) — directional, not corpus fact.
- **C3 — swapd-vs-injection comparators** (docs, feeds R6): E2B per-host
  request transforms (beta), Vercel credential brokering (every plan),
  Cloudflare outbound handlers, Microsandbox network-layer injection (OSS).
  **Daytona verified** via [their secrets docs](https://www.daytona.io/docs/en/secrets/):
  opaque `dtn_secret_*` placeholders + outbound proxy, HTTPS-headers-only
  substitution, per-secret host allowlist, response scrubbing — the full
  pattern; docs must compare mechanism-by-mechanism. Open verification: the
  E2B allow/deny conflict-resolution claim (currently sourced only to the
  MarkTechPost benchmark — vendor link still to collect; Vercel's deny-wins
  half is now confirmed by Vercel's own firewall docs); E2B's
  accept-before-decide TCP behavior is attributed by MarkTechPost to E2B's own
  docs. Make the security-docs comparison
  per-vendor with links. 2026-09-19 (out-of-band corroboration, not a watch
  delta): Vercel's "every plan" half is now vendor-verified — Vercel's own
  [KB](https://vercel.com/kb/guide/vercel-sandbox-vs-e2b) (published
  2026-03-20, updated 2026-09-04) states credential-brokering transformation
  rules are "available on all plans, including Hobby", quoted verbatim in
  the open H16 org-policy research (PR #101); the E2B vendor links stay open
  for the docs run.
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
  mechanism. In-segment reference point (evening pass): AgentComputer's cold
  (stopped) storage ≈ $0.000027/GB-hr, ~25x under hot — stopping a box is
  cheap, so the free tier's suspend shape should lean on cold-storage math,
  not on wall-clock VM billing.
- **C6 — GPU path as a Neo provider decision criterion** (hosted product,
  long-term): no GPU story exists today; add an explicit criterion to the Neo
  provider choice — which providers offer GPU shapes, at what price, and
  whether the provisioning interface stays provider-agnostic across CPU/GPU
  shapes.
- **C7 — Positioning defense** (marketing, feeds R5): TermSquad now occupies
  the persistence headline in-market; the "real computer that stays yours" +
  credential-proxy differentiator needs to land publicly before the window
  narrows further. 2026-09-19: three more moves narrow the claimable axes —
  Cloudflare × Cursor plays customer-controlled execution (do not pitch
  control), Docker v0.43.0 converges on "agent runs without keys inside"
  (credential-proxy claims must argue mechanism + OSS, not posture), and
  VMware Private AI Cloud (deny-by-default Tanzu sandboxes + isolated
  credential store, VMware Explore 2026 ~Sep 1 — INFERRED, third-party) is a
  third enterprise-governance corroborator; the surviving axes are
  persistence + approval loop + OSS. Add the one-line note to
  `docs/POSITIONING.md` (candidate, from the night pass).
- **C8 — Buyer-vs-user packaging analysis** (sales/product): the hosted
  product's *user* is the Muse but the *buyer* is a human/org. Map both
  journeys: what trust evidence each gate requires (audit trail,
  compliance/SOC 2 path, cost controls), per-box vs per-seat pricing, and how
  it shapes the pricing-page item, R4, and the free-tier abuse constraints.
  The research doc's Limitations section flagged this; it drives pricing
  packaging and the compliance roadmap, so it gets its own item.
- **C9 — OpenAI Agents API partnership watch** (competitor): Sep 10 public
  beta names Blaxel/Cloudflare/Daytona/DigitalOcean/E2B/Modal/Oracle/Runloop/
  Vercel as sandbox partners (no new partners at the evening pass). Terms
  reported (evening pass, third-party characterization of OpenAI's docs):
  network-on-by-default w/ template policy, outbound disable/allowlist,
  1h inactive deletion, US-only beta, no ZDR even self-hosted. Track what the
  default sandbox surface converges on — platform defaults set the bar our
  hosted story must clear. 2026-09-19 observation: the Agents API normalizes
  bring-your-own-sandbox (harness from OpenAI, execution from you) as a
  first-class shape — supports the hosted pitch of a persistent full-VM
  where the platform operates the loop and the tenant's box is the execution
  plane.
- **C10 — WSO2 Agent Manager watch** (competitor, evening pass): GA Sep 15;
  runtime pinned on primary evidence (k8s pods +
  [NetworkPolicy egress](https://github.com/wso2/agent-manager/pull/1496),
  AgentID OAuth2, SecretKeyRef injection; runtime class unconfirmed) — lands
  in the "Containers on shared infra" tier, task-scoped column. Watch
  adoption; webinar Sep 29.
- **C11 — Baseten/Blaxel integration watch** (competitor): "Hosted Tools"
  blog names Blaxel as the sandbox foundation (direction: code execution +
  browser). Sandbox repo releases v0.2.57/58/59 (Sep 9/15/18, minor, evening
  pass) — nothing shipped; the watch stays open. An acquisition-turned-sandbox-product
  changes the task-scoped landscape.
- **C12 — AgentComputer egress watch** (competitor): narrowed to egress-only
  (evening pass) — coverage is now material on primary sources (own
  Firecracker VM manager, computer-host/guest repos, pricing, cold-storage
  model, Enterprise tier). Remaining gap: egress posture is undocumented on
  every public page.
- **C13 — Sandbox-escape-week competitive positioning** (marketing, feeds
  O13): Docker Sandboxes closed four sandbox-boundary vulns in one release,
  with the critical virtio-fs fix shipping unlabeled. The trust/transparency
  doc's negative-example material is strong but partially sourced
  (D-Bus/OAuth quotes need a direct vendor release-notes read first); honest
  scoping holds spark-vm outside the shared-workspace guest→host sub-class
  but inside the D-Bus-daemon/OAuth-port owned-risk classes. Also: a usable
  contrast — the two shared-workspace guest→host breaks are outside the
  full-VM sub-class, which is consistent with (not proof of) the
  no-host-folder-sharing architecture choice; the D-Bus-daemon and
  OAuth-port classes are owned risks for a hosted spark-vm too, and the doc
  must not claim the full-VM model is clear of them. Disclosure-timeline
  guidance: verify all version numbers against vendor pages only in any
  trust/transparency derivative (Docker mis-listed a fix version once).
  **2026-09-19 evening pass:** the D-Bus/OAuth direct-read debt is closed —
  both quotes are now vendor text from Docker's own release notes, and the
  notes now name CVE-2026-77179/79994 (the consolidation's morning read
  showed no CVE names; the amendment timing is the author's inference, not
  vendor fact — the "shipped unlabeled" framing above is time-bounded to
  ship time and the morning read, corrected-by-amendment in the current
  notes); the at-a-glance row
  carries the vendor-verified price signal (`sbx` CLI free; org governance
  paid). Docker AI Governance (central network/filesystem/MCP policies,
  sign-in enforcement, audit logs) added as an H16 vendor candidate.
  See `docs/COMPETITOR_WATCH_2026-09-19_EVENING.md`.

## Sources

Surveyed 2026-09-18; links inline above. Primary: TermSquad pricing and
feature pages (termsquad.com/pricing, /features/always-on-cloud-computer,
/features/any-agent); TermSquad launch release (EINPresswire, Sep 15, 2026 —
paid wire release, not independent editorial coverage); MarkTechPost Aug-2026
sandbox benchmark (cold start, per-second pricing, network policy, isolation);
StartupHub 2026 sandbox comparison; ralph-playbook sandbox reference;
yuanbop/frugal E2B research notes; rethink-paradigms/mesh E2B internals;
opencolin/agentic-engineering sandbox + infrastructure tables (third-party;
the $20/mo AgentComputer row was refuted against the vendor's own pricing page);
[marcus-mok-gh/nova-cloud-computer daytona-vs-e2b](https://github.com/marcus-mok-gh/nova-cloud-computer/blob/HEAD/docs/daytona-vs-e2b.md)
(third-party, used only for pointers); pondero.ai July-2026
comparison; bradvin/agentfirst.directory AgentComputer entry; **Daytona's own
[secrets docs](https://www.daytona.io/docs/en/secrets/) (verified 2026-09-18 —
placeholder design, header-only substitution scope, host allowlists, response
scrubbing)**; [agentcomputer.ai/pricing](https://www.agentcomputer.ai/pricing)
+ [agentcomputer.ai/docs](https://www.agentcomputer.ai/docs) (pure PAYG,
configurable up to 250 GiB storage; rate card identical to Fly Sprites);
Blaxel acquisition (announced 2026-09-10):
[businesswire](https://www.businesswire.com/news/home/20260910783896/en/Baseten-Acquires-Blaxel-to-Build-the-Infrastructure-for-AI-Agents-in-Production),
[baseten.co/blog](https://www.baseten.co/blog/blaxel-is-joining-baseten-to-build-the-future-of-agentic-cloud/),
[blaxel.ai/pricing](https://blaxel.ai/pricing) (~5s scale-to-zero per FAQ,
$250/mo BAA add-on); [modal.com/docs/sdk/py/latest/Sandbox](https://modal.com/docs/sdk/py/latest/Sandbox)
(`secrets=` injection, `Sandbox._experimental_set_outbound_network_policy`)
+ [modal.com/docs/guide/sandboxes](https://modal.com/docs/guide/sandboxes);
Daytona's own network-limits skill docs
([daytona/skills network-limits.md](https://github.com/daytona/skills/blob/HEAD/skills/daytona/references/typescript-sdk/network-limits.md),
Tier 3/4 post-create policy changes); [docs.sprites.dev](https://docs.sprites.dev)
(Fly Sprites PAYG + one Level 10 $20/mo plan, ~30s hibernate); Vercel
[firewall docs](https://vercel.com/docs/sandbox/concepts/firewall)
(DENY-wins precedence).

**Pm watch (2026-09-18):** [eve.dev/docs/human-in-the-loop](https://eve.dev/docs/human-in-the-loop)
and [vercel.com/blog/introducing-eve](https://vercel.com/blog/introducing-eve)
(Vercel `eve` per-action human approvals — a separate product from the Sandbox
SKU); [Northflank network policies docs](https://northflank.com/docs/v1/application/network/configure-network-policies);
[Runloop Devboxes overview](https://docs.runloop.ai/docs/devboxes/overview)
("isolated, ephemeral virtual machines", Network Policies);
[Microsandbox networking overview](https://github.com/superradcompany/microsandbox/blob/HEAD/docs/networking/overview.mdx)
(first-match-wins egress policy); [herdrdev/herdr#3415](https://github.com/herdrdev/herdr/issues/3415)
(reboot-race session loss); [InfoWorld: OpenAI Agents API public beta](https://www.infoworld.com/article/4221163/openai-launches-managed-agents-api-to-simplify-enterprise-ai-agent-development.html);
[GlobeNewswire: WSO2 Agent Manager GA](https://www.globenewswire.com/news-release/2026/09/15/3362114/0/en/wso2-agent-manager-brings-sovereign-ai-governance-to-enterprise-agent-sprawl.html);
[Baseten blog: Introducing Baseten Hosted Tools](https://www.baseten.co/blog/introducing-baseten-hosted-tools/);
[Microsandbox releases](https://github.com/superradcompany/microsandbox/releases)
(v0.7.1); [WebProNews: Factory $200M at $5B](https://www.webpronews.com/factorys-5-billion-leap-ai-agents-take-over-enterprise-software-factories/).

**Evening watch (2026-09-18):** [agentcomputer.ai/docs](https://www.agentcomputer.ai/docs)
and [agentcomputer.ai/pricing](https://www.agentcomputer.ai/pricing) (refetched;
own Firecracker VM manager on bare metal, hot/cold storage rates, Enterprise
tier); [AgentComputerAI/computer-host](https://github.com/AgentComputerAI/computer-host)
and [AgentComputerAI/computer-guest](https://github.com/AgentComputerAI/computer-guest)
(verified via GitHub API: 2 stars each, updated 2026-04-30);
[herdrdev/herdr#3415](https://github.com/herdrdev/herdr/issues/3415) (verified
via GitHub API: state closed, closed 2026-09-07 — pm-pass "open bug" line was
stale); [wso2/agent-manager#1496](https://github.com/wso2/agent-manager/pull/1496)
(sandboxed pods + NetworkPolicy egress, AgentID OAuth2);
[blaxel-ai/sandbox releases](https://github.com/blaxel-ai/sandbox/releases)
(v0.2.57/58/59, Sep 9/15/18 — correcting the research notes' v0.2.48 line).
Third-party (INFERRED, not independently verified): OpenAI Agents API terms
details (network-on-by-default, 1h inactive deletion, US-only beta, no ZDR
even self-hosted); Apr 28, 2026 OpenAI×AWS partnership + Apr 27
MS-exclusivity end (date corrections, were misdated as September in research
notes — independently corroborated by
[the-decoder](https://the-decoder.com/openai-lands-on-aws-one-day-after-microsoft-deal-restructuring/)
coverage of the Apr 28 AWS event).

**2026-09-19 consolidation pass (night + morning + midday watches):** primary:
[Docker security announcements](https://docs.docker.com/security/security-announcements)
(CVE-2026-77179/79994, fixed 0.42.0 Sep 7, records published Sep 15);
[docker/sbx-releases](https://github.com/docker/sbx-releases) (v0.43.0 trust-model
tightening, Sep 15); [Cloudflare press release: Cursor Cloud Agents on Cloudflare
Sandboxes](https://www.cloudflare.com/press/press-releases/2026/cloudflare-expands-support-for-ai-coding-agents-with-cursor-cloud-agents-on-cloudflare-sandboxes/)
(Sep 2, 2026); [GitHub Changelog: enterprise-managed sandbox in Copilot for
JetBrains](https://github.blog/changelog/2026-09-08-enterprise-managed-sandbox-in-copilot-for-jetbrains/)
(Sep 8, 2026); [OpenRouter server-tools/shell](https://openrouter.ai/docs/guides/features/server-tools/shell)
(`openrouter:shell` beta); [tencent/browserskill](https://github.com/tencent/browserskill)
(BrowserSkill README + PRIVACY.md); termsquad.com/pricing (refetched 2026-09-19 —
Power tier 6 vCPU, $9/$19/$29/$49 unchanged);
[wso2/agent-manager#1390](https://github.com/wso2/agent-manager/pull/1390) (OTel
ingestion on VM installs, NetworkPolicy `except` list in the wild);
[blaxel-ai/sandbox releases](https://github.com/blaxel-ai/sandbox/releases/tag/v0.2.59)
(v0.2.59/v0.2.58, maintenance); [AgentComputerAI/computer-host](https://github.com/AgentComputerAI/computer-host)
and [computer-guest](https://github.com/AgentComputerAI/computer-guest)
(untouched since 2026-04-30). Third-party (INFERRED): Severity Daily on the
Docker 0.42.0 D-Bus/OAuth vuln entries; thehackernews / realhacker.news /
hacklido Docker CVE press roundup; TechGig / arabianbusinessweek / menews247 /
uaenews247 / channelpostmea on WSO2 GA reception; runtimewire, cellcog,
aicraftjournal on Agents API terms (+ OpenAI-hosted sandbox $0.03/20min per
1 GB, unverified); fourweekmba on the unchanged nine-partner set;
aicraftjournal/OpenRouter third-party roundup on `$0.0001/active-second`
ephemeral pricing; morningstar PR Newswire on FastGPT v4.16.0; itsfoss Local
AI Weekly on BrowserSkill (Sep 18).

## Watch update — 2026-09-23 (mid-afternoon): C26 closed, C30 vendor-confirmed, C36 new-to-watch

Three corpus actions this pass (primary-source-verification folds per the
C32 precedent; full pass record in
`docs/COMPETITOR_WATCH_2026-09-23_MID_AFTERNOON.md` §§3a–3c).

**C26 CLOSED.** DigitalOcean Managed Agents pricing is now vendor-verified
on the vendor's own docs pricing page
(https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/,
read live this run, "Last verified 22 Sep 2026"): **$0.044/vCPU-hour**
(per-second on actual CPU consumed — footnote: "Active CPU billing is
coming soon. Until then, you will be billed at 25% of the vCPUs allocated
to your sandbox"), **$0.0095/GB-hour** on peak memory, session-storage
volumes $0.05/GiB-month (peak), public internet egress $0.01/GiB,
snapshots/checkpoints $0.05/GiB-month, custom sandbox templates (BYOT)
$0.05/GiB-month. Sandbox shapes (full-allocation hourly): XSmall
`mars-1vcpu-1gb` $0.0535/hr; Small `mars-2vcpu-2gb` $0.107/hr; Medium
(default) `mars-2vcpu-4gb` $0.126/hr; Large `mars-4vcpu-8gb` $0.252/hr;
XLarge `mars-16vcpu-32gb` $1.008/hr. Paused sessions incur no compute
charges; retained checkpoints keep accruing storage charges while paused
(including at $0 prepaid balance). Positive prepaid balance required; no
per-session spend limit. Action Gateway tool calls (incl. Exa web
search/fetch) need prepayment and draw the shared balance.

Material caveat, carried as a caveat (not folded as fact): the vendor
docs price snapshots/checkpoints at **$0.05/GiB-month** while the launch
press release (syndicated Business Wire) says **$0.005/GiB-month** — 10×
apart, one of the two is wrong. CPU ($0.044) and memory ($0.0095) agree
across both sources. Next watch ask: re-check the snapshot rate if the
docs page is re-dated. Competitive read (INFERRED): DO is the first
cloud managed-agent stack in the corpus to *announce* per-second
active-CPU metered sandbox pricing (interim rate 25%-of-allocated
until active billing ships) —
the active-CPU metering leg vs spark-vm's flat-monthly Tier 1 thinking
(see `docs/PRICING_THINKING.md` §2) now has real numbers on both sides of
the ledger.

**C30 vendor-confirmation upgrade.** The OpenAI Agents API public beta is
now confirmed on OpenAI's own launch post — **VERIFIED** read on the
vendor's own blog this run (https://openai.com/index/introducing-the-agents-api/,
~14:15 CDT): "Today, we're introducing the Agents API in public beta,"
naming nine partners with first-class integrations: "Blaxel, Cloudflare,
Daytona, DigitalOcean, E2B, Modal, Oracle, Runloop, and Vercel." (Launch
date 2026-09-10 per third-party coverage of the vendor launch — the post
body carries no visible date; the standing corpus "Sept-10" date is kept.)
No new C-number: the filing existed, only the provenance layer moved. The
rumored "Managed Agents" unveil at DevDay 2026 (Sep 29) remains
press/rumor with no OpenAI vendor confirmation; AWS Bedrock "Managed
Agents, powered by OpenAI" is an April 28 limited preview — separate and
older. Competitive read for spark-vm: the hyperscaler sandbox is not yet
purchasable for production (non-production for all GKE customers,
production GA via allowlist) — potential pressure, not live production
competition; the zero-idle economics and the K8s-machines /
data-plane-activations split are the shapes to watch.

**C36 new — Google Agent Substrate on GKE (corpus-adjacent new-to-watch).**
Previously unfiled, ~Sep 17: Google's open-source agent-sandbox runtime
(Cloud Hypervisor microVMs or gVisor; <500 ms resume; 500+ suspend/resume
activations/sec; 1,000+ dormant agents/host; network gateway) is now
offered to GKE customers for non-production workloads, with production GA
support via allowlist; early design partner Nous Research (Hermes). Filed
as corpus-adjacent new-to-watch, not a tracked-provider row — a
hyperscaler offering a sandbox runtime on its own substrate is a different
shape than a standalone agent-VM product. **Vendor-confirmed 2026-09-23
(late-afternoon pass)** — the late-afternoon watch read Google's own
announcement on the Cloud blog and corroborated all nine filed claims
(five verbatim, the rest confirmed as filed or stronger) (<500 ms resume,
500+/sec activations, 1,000+ dormant agents/host,
Cloud Hypervisor-or-gVisor choice, integrated gateway, non-production for
all GKE customers with production GA via allowlist, Nous Research (Hermes)
as early design partner with named quote); see "Watch update — 2026-09-23
(late-afternoon)" at the bottom. New vendor facts not in the filing: 10×
density headline, open-core portability ("runs on any Kubernetes
infrastructure and is optimized for GKE"), harness-agnostic by design
(Claude Code, OpenClaw, Hermes — another harness↔compute-split datapoint),
K8s-machines / data-plane-activations control split, optional Filestore
agent volumes (NFS, RWX, POSIX locking, ms attach), native Axion (claimed
30% better price-performance for sandbox workloads).

## Watch update — 2026-09-23 (late-afternoon): C36 vendor-confirmed

One corpus action this pass (primary-source-verification fold per the C32
precedent; full pass record in
`docs/COMPETITOR_WATCH_2026-09-23_LATE_AFTERNOON.md` §1).

**C36 VENDOR-CONFIRMED.** Google's own Cloud-blog announcement
("Agent Substrate available on GKE",
https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke,
read live ~16:00 CDT 2026-09-23; post dated ~Sep 15, 2026 — two days before
the itbrief.co.uk piece that filed C36) corroborates every filed claim:
open-source secure-by-default agent execution runtime on GKE; sub-500 ms
resume at over 500 suspend/resume activations/sec; "over 1,000 dormant
agents per host" via the zero-idle suspend model; Cloud Hypervisor
microVMs-or-gVisor choice; integrated gateway managing egress/ingress with
granular policies plus egress proxies injecting credentials outside agents'
reach; available to all GKE customers for non-production workloads with
production GA support via allowlist; Nous Research (Hermes) as early design
partner with a named CBO quote. The itbrief.co.uk piece stands as the
discovery source; no new C-number (the filing existed, only the provenance
layer moved — C30 precedent).

## Watch update — 2026-09-23 (early-evening): C36 THIRD-PARTY pricing color

One corpus action this pass (THIRD-PARTY-layer fold; full pass record
in `docs/COMPETITOR_WATCH_2026-09-23_EARLY_EVENING.md` §3a).

**C36 — Filestore agent volumes pricing model (THIRD-PARTY).**
Google's Filestore agent volumes for AI (per-agent persistent
workspaces auto-allocated/attached in milliseconds at GKE sandbox
start; works with Agent Substrate on GKE and GKE Agent Sandbox;
RW-many + POSIX locking; non-production now, production via
allowlist) carries a **pay-per-use pricing model based on storage
capacity consumed, with automatic lifecycle tiering for inactive
workspace data** — framed in the launch coverage as an
idle-capacity-economics play for short-lived/intermittent agent
sessions. Source: itbrief.com.au (~Sep 19),
https://itbrief.com.au/story/google-cloud-launches-filestore-agent-volumes-for-ai
(THIRD-PARTY — press account; no vendor dollar figure exists). The
mechanics were already VENDOR-CONFIRMED at the vendor layer from
Google's own Cloud-blog announcement (above); only the pricing-model
color is new, and only at the THIRD-PARTY layer. Competitive read:
Google is pricing the storage leg of the agent stack against idle
waste — the same axis spark-vm's persistence story must win on
(total-cost-of-always-on, not just resume latency).
## Watch update — 2026-09-23 (mid-evening): C26 discrepancy resolved on vendor docs

One corpus action this pass (primary-source-verification fold, C32
precedent; full pass record in
`docs/COMPETITOR_WATCH_2026-09-23_MID_EVENING.md` §1b).

**C26 — DigitalOcean Managed Agents pricing, discrepancy retired.**
The docs pricing page (unfetchable last pass) was re-read live this pass
(VENDOR layer: the vendor's own docs). The standing 10× snapshot-rate
discrepancy (docs $0.05/GiB-month vs syndicated release $0.005/GiB-month)
resolves against the primary source: **$0.05/GiB-month is the docs
figure**; the $0.005 figure belonged to the syndicated release copy and
is retired from the corpus. The C26 field-table row and the C26 entry's
pricing paragraph above now carry the docs figure with provenance.

**CPU-billing footnote re-verified** (already folded at mid-afternoon):
"Active CPU billing is coming soon. Until then, you will be billed at 25%
of the vCPUs allocated to your sandbox. Paused sessions incur no compute
charges." The per-entry paragraph's "zero while waiting" read of DO's
$0.044/vCPU-hour rate is now explicitly qualified there: it holds only
for paused sessions; a waiting-but-live sandbox costs 25% of its
allocation until active-CPU metering ships. C14 input discipline: DO's
headline active-CPU rate is aspirational until the metering arrives —
it is not today's measured cost to beat.

**Re-verified live this pass** (already folded at mid-afternoon; confirmed
again on the page): session storage (volumes) $0.05/GiB-month (peak
storage consumed), custom sandbox templates (BYOT) $0.05/GiB-month,
public internet egress $0.01/GiB, sandbox shapes mars-1vcpu-1gb …
mars-16vcpu-32gb, positive prepaid balance required, no per-product
spend limit.
