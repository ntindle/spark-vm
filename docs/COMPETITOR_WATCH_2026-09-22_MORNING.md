# Competitor watch — 2026-09-22 morning

**Survey window:** 2026-09-22 ~01:05 → ~11:25 CDT (surveyor reads; author
re-read of the DigitalOcean launch release ~11:35 CDT).
**Method:** two read-only surveyors — (A) vendor-page re-reads of the tracked
set (primary sources: vendor docs, pricing pages, GitHub releases,
changelogs), (B) open-web market-news scan for launches, acquisitions,
funding, pricing changes, releases, and partner moves. No logins, no writes.
**Labels:** VERIFIED (read on the vendor's own page/doc/repo or vendor press
release this run, URL given), THIRD-PARTY (press/other sources, named),
INFERRED (author characterization), UNVERIFIABLE (no public source exists).

## 1. In-window deltas

### DigitalOcean Managed Agents — public preview (the move of the morning)

**VERIFIED** (vendor press release, Business Wire, dated 2026-09-22:
https://www.businesswire.com/news/home/20260922295615/en/DigitalOcean-Launches-Managed-Agents-Bringing-Agent-Execution-Tool-Access-and-Inference-Together-on-One-Cloud).
Paid wire = the vendor's own claims, not independent editorial coverage —
same labeling the corpus applies to the TermSquad launch release.

What it is — two vertically integrated services plus inference, sharing one
security model and one billing model:

- **Harness Runtime** — "lightweight microVM" per session, "isolated at the
  hardware layer", "a separate secrets management service", built-in
  Chromium + coding sandbox, pause/resume/fork semantics, lifecycle APIs
  that persist conversational history and working state across sessions.
- **Action Gateway** — governed access to 16,000+ tools from 500+ providers
  through one managed MCP endpoint (GitHub, Jira, Stripe, PagerDuty,
  Supabase, web search/fetch, browser automation, a team's own MCP
  servers). "Credentials are brokered at execution time and never reach the
  model or the sandbox." Centralized permissions, model-backed tool
  search, human-in-the-loop approval for sensitive actions.
- **Inference Engine** — serverless inference on hosted open-weight models
  (Nemotron 3 Ultra, Kimi K3, GLM 5.3) and proprietary ones (Claude Fable
  5.1, GPT 6 Astra), or the customer's own endpoint; an Inference Router
  picks by intent/cost/latency/quality.

Runs unmodified: Claude Code, Codex CLI, OpenCode, Hermes, LangGraph
agents; custom agents packaged as OCI images/templates. Collaborative
sessions (start on a laptop, resume from any device, hand the live session
to a teammate; multi-user/agent shared sessions — "a capability unique
among major cloud providers" per the release). Customers quoted: OpenHands
(Agent Canvas), Qencode, Amplitude (Wave). Available today via Cloud
Console / doctl; $5 credit for new users.

Pricing (in the release):

- **$0.044/vCPU-hour active CPU** (per-second; zero charge while waiting on
  model/tool responses), $0.0095/GB-hour memory, $0.005/GiB-month
  snapshots. Auto-pause stops CPU+memory charges while state is preserved.
- Performance claims: **305 ms resume-from-pause** ("46% faster than other
  leading offerings"), 31% faster microVM-creation-to-agent-response, tool
  search "42% more accurate than conventional methods".
- TCO claim: "up to 37% lower monthly TCO" vs "the leading independent
  sandbox provider" — unnamed; **INFERRED** to be E2B (the release never
  names them).

**Why it matters for spark-vm (INFERRED):** the first major-cloud,
full-stack managed agent-computer product with published sandbox pricing —
squarely in the #47 hosted-product lane. Four competitive inputs:

1. **Metering shape** — active-CPU billing (pay only for cycles consumed)
   vs spark-vm's flat-$20/mo-with-suspend-on-idle. Both attack idle waste
   from opposite sides: DO's is finer-grained, ours is more predictable.
   Filed as a pricing-shape data point (C26) in `docs/PRICING_THINKING.md`.
2. **Resume latency** — 305 ms pause→resume is the number to beat for the
   #47 resume-latency target (C14, still open).
3. **Secrets posture** — "credentials brokered at execution time and never
   reach the model or the sandbox" plus a separate secrets service: a
   **fifth convergent data point** for the placeholder-swap pattern in the
   secrets-posture corpus (joins Daytona, Microsandbox, opencomputer.dev,
   h-sandbox). Input to H5.
4. **Org policy** — Action Gateway's governed tool access (centralized
   permissions, brokered credentials, human-in-the-loop approvals, audit
   logs) is a vendor candidate for the H16 org-policy layer design.

Filed as **C26** (§5).

### Daytona v0.215.0 — routine SDK/CLI patch

**VERIFIED** (https://www.daytona.io/changelog, read ~11:17 CDT): "Integer
API client types and CLI MCP allowlist fixes" — syncs integer OpenAPI types
across generated Go and Java clients **as a breaking change**, corrects CLI
MCP allowlist handling, fixes CLI profile propagation and Ruby SDK archive
uploads. Routine patch cadence (v0.214.0 → v0.215.0 in 7 days), no new
capability — not a backlog item. Watch note only: if the corpus ever tracks
Daytona API compatibility for the provider-adapter question (H4), the
integer type-sync churn is a data point.

## 2. Adjacent color — Baselayer "Know Your Agent" ($35M Series A)

**THIRD-PARTY** (SiliconANGLE coverage via letsdatascience.com, reported
2026-09-22; M13 led — no vendor page fetched, news-only): Baselayer
(Osiris Ratings) raised $35M and launched an "Agentic Identity Suite" /
"Know Your Agent" — an agent identity/verification layer for agentic
commerce (who deployed the agent, who it represents, authorization for the
task). Adjacent, not sandbox infra. Relevance is **INFERRED**: the hosted
product's multi-tenancy audit (H11) needs an agent-identity story (who owns
a session, delegation, credential brokering) — Baselayer's launch is
evidence the market is pricing that story separately. Not a backlog item on
third-party evidence alone; recorded here as input to H11.

## 3. The tracked set — quiet

VERIFIED re-reads this run (times CDT):

- **Microsandbox** — still v0.7.1
  (https://github.com/superradcompany/microsandbox/releases, ~11:14);
  v0.7.0 next in line. Tagged ~Sep 17 (pre-window).
- **Docker Sandboxes** — release notes still top out at the 2026-09-15
  block; no 0.44 (https://docs.docker.com/ai/sandboxes/release-notes/,
  ~11:16). The "0.44 imminent" note from earlier baselines still hasn't
  materialized.
- **E2B** — pricing unchanged (https://e2b.dev/pricing, ~11:18): Hobby free
  + $100 one-time credit, Pro $150/mo + per-second usage, Enterprise
  custom. No Sep-22 SDK release visible.
- **boat.dev** — pricing unchanged (https://docs.boat.dev/pricing, ~11:14):
  small $0.018/h, default $0.036/h, large $0.072/h, xlarge $0.200/h
  (xlarge: $100+ plan + operator capacity allocation); plans $20/100/500/
  2000; stopped = free; 25-hour trial. Comparison-table anchors unchanged.
  The xlarge capacity-allocation caveat remains current vendor policy.
- **TermSquad** — tiers unchanged (https://termsquad.com/, ~11:19):
  $9/$19/$29/$49 (Starter 2vCPU/4GB/40GB … Ultra 8vCPU/24GB/200GB);
  BYO-AI stance unchanged.
- **AgentComputer** — unchanged (https://agentcomputer.ai and
  https://www.agentcomputer.ai/pricing, ~11:20): usage-based CPU
  $0.07/CPU-hr, memory $0.04375/GB-hr, hot storage $0.000683/GB-hr, cold
  $0.000027/GB-hr; Firecracker on bare metal; ~1GB/s network, ~3GB/s
  NVMe. **C12 stands** — still no stated network-egress policy anywhere on
  their pages → UNVERIFIABLE (no public source exists).
- **WSO2 Agent Manager** — no new vendor announcement; **C10 stands** (Sep
  29 webinar trigger). In-window third-party coverage is syndication of the
  same GA press release.

## 4. Pre-window items newly surfaced (not deltas)

- **Docker Sandboxes 0.42.0 notes (2026-09-07)** — VERIFIED
  (https://docs.docker.com/ai/sandboxes/release-notes/): the notes now name
  CVE-2026-77179 (virtio-fs symlink escape on macOS) and CVE-2026-79994
  (guest-to-host unix-socket relay race) in the local-sandbox trust
  boundary. Already in the corpus via C13 (sandbox-escape-week
  positioning); this read confirms the CVE names against the vendor's own
  notes. The virtio-fs and unix-socket escape classes remain worth
  cross-checking against spark-vm's own sandbox sharing/architecture notes
  when that hardening pass happens — no new item.
- **Raindrop $35M Series A + "Simulations" (Sep 17)** — THIRD-PARTY
  (runtimewire.com): agent pre-release failure testing; adjacent, not
  sandbox infra.
- **Vercel v0 rebuilt for production (Feb 2026 vendor blog)** —
  THIRD-PARTY (InfoWorld): sandbox-based runtime, GitHub repo import,
  Snowflake/AWS DB integrations, git workflows. (A re-surfaced VentureBeat
  "GA" piece misdates it; InfoWorld pins the vendor announcement to Feb
  2026.)
- **Perplexity SPACE sandbox (Jul 15)** and **Cursor Cloud Agents on
  Cloudflare Sandboxes (Sep 2)** — pre-window background, re-surfaced in
  passing.

## 5. Standing items

- **C26 — DigitalOcean Managed Agents watch** (competitor, morning pass):
  NEW. Public preview 2026-09-22; microVM-per-session Harness Runtime +
  Action Gateway MCP (16k tools / 500+ providers) + Inference Engine;
  active-CPU pricing ($0.044/vCPU-h, $0.0095/GB-h, $0.005/GiB-mo
  snapshots); 305 ms resume claim; 37% TCO claim vs unnamed "leading
  independent sandbox provider" (INFERRED: E2B). Competitive inputs filed:
  pricing-shape data point (pricing corpus), 305 ms bar for C14, fifth
  placeholder-swap data point for the secrets-posture corpus (H5), Action
  Gateway as H16 org-policy vendor candidate. See §1.
- **C25 — jail firewall re-apply watchdog** (competitor): still OPEN
  (unchanged by this pass).
- **C19 (Brig), C20 (Epho)** watchlist adds: unchanged (pre-window items
  from the night pass).
- **C14 (#47 resume-latency target)**: still OPEN — the DO 305 ms claim is
  now the competitive bar to beat.
- **C12 (AgentComputer egress)**: stands — UNVERIFIABLE (no public
  egress-policy source).
- **C10 (WSO2)**: stands — Sep 29 webinar trigger.
