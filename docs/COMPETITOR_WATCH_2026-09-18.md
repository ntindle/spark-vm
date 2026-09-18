# Competitor watch — 2026-09-18 (evening pass)

Delta-only update against the ~12:00 CDT baseline (`docs/COMPETITOR_ANALYSIS.md` as of PR #34).
Surveyed 2026-09-18 ~16:00 CDT. One material correction (herdr#3415 was
already fixed upstream), two material new-primary-source findings
(AgentComputer's own Firecracker VM manager; WSO2's k8s-pod sandboxing),
two recycled-date corrections the research notes misdated, and two
confirmed no-change watch items (TermSquad pricing/features unchanged;
Baseten/Blaxel releases minor, no shipped product).

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo today
(link inline). **INFERRED** = third-party characterization, labeled as such.
"No change detected" is reported explicitly.

## 1. AgentComputer re-check (C12) — material new facts, primary-sourced

The pm pass left AgentComputer as the thinnest coverage in the set with an
unverified "built-on/reselling Fly.io Sprites" theory. That theory now needs
revision.

- **Own VM manager (Firecracker-based), VERIFIED (vendor docs + GitHub):**
  [agentcomputer.ai/docs](https://www.agentcomputer.ai/docs) describes
  infrastructure "provisioned on bare metal hosts", running an **own
  open-source Firecracker VM manager** —
  [`AgentComputerAI/computer-host`](https://github.com/AgentComputerAI/computer-host)
  ("a modern vm manager for firecracker… manages tap devices and nftables
  rules for networking, handles SSH key generation, guest identity injection,
  and disk snapshots"; boots Firecracker VMs in under 200ms) — with guest
  images from
  [`AgentComputerAI/computer-guest`](https://github.com/AgentComputerAI/computer-guest)
  ("thin guest vm image"), preconfigured with browser access + SSH. Both
  repos exist (verified via GitHub API today). **Nuance the docs don't give
  you:** each repo has 2 stars and was last updated 2026-04-30 — this is
  "open-source" in the license sense, not in the traction sense. And an OSS
  repo corroborates existence, not deployment: the production fleet may run
  different code at a different version — that gap is unconfirmed either
  way.
- **Sprites theory, downgraded:** still no Sprites acknowledgment anywhere
  (INFERRED, as before), and the vendor now claims its own Firecracker-based
  VM manager on bare metal — so the rate-card parity ($0.07/CPU-hr,
  $0.04375/GB-hr, $0.000683/GB-hr hot, $0.000027/GB-hr cold) stays as
  **unexplained parity, not claimed reselling**. The earlier "$20/mo plan"
  directory claim remains refuted: the pricing page is pure PAYG at those
  four rates (VERIFIED, refetched today).
- **Persistence model, VERIFIED:** hot storage (running) vs **cold storage
  (stopped) at $0.000027/GB-hr** — no published deletion window for
  stopped machines (unlike the OpenAI 1-hour inactive deletion in §3).
  Session model = explicit machines created/stopped via CLI
  (`computer create/ssh/open`), home directory on NVMe. Cold-rate parity with
  hot idle means stopping buys ~25x on storage cost — worth noting in the
  idle-economics comparison (C5).
- **New tier:** an **Enterprise** tier now appears on the pricing page —
  "Custom computer capacity policies, Team billing and managed rollout
  support, Private infrastructure options, Priority operational support"
  (was PAYG-only at the morning check).
- **Egress:** still undocumented on public pages (UNCERTAIN); closest
  primary-source evidence is "Network speeds up to ~1 Gb/s down and
  ~1.2 Gb/s up over shared NAT" plus nftables-managed networking in
  computer-host. No egress policy docs.
- **Scorecard delta:** the baseline's isolation scorecard uses named tiers,
  and AgentComputer was already tentatively placed in the
  **"Per-customer computer" tier** ("Ubuntu VMs"). This pass *confirms* that
  placement on primary evidence (Firecracker microVMs + jailer on bare metal)
  rather than promoting it. On the baseline's egress-controls scorecard,
  AgentComputer's row stays "undocumented" (egress score 0 in the working
  notes). C12's "thinnest coverage" item is now materially covered except
  egress.

## 2. WSO2 Agent Manager (C10) — sandbox runtime details, primary-sourced

The pm pass filed C10 as "watch adoption" with no runtime detail. The
runtime is now pinned down:

- **Isolation tech, VERIFIED (GitHub primary):**
  [wso2/agent-manager PR #1496](https://github.com/wso2/agent-manager/pull/1496)
  (~43 days ago) fixes a bug where "sandboxed agent pods… could not
  mint an AgentID token at all: the sandbox **NetworkPolicy had no egress
  rule** for the environment's Thunder instance on port 8090." So the
  sandboxed runtime is **Kubernetes pods governed by NetworkPolicies**.
  (INFERRED: no evidence of a microVM or gVisor runtime layer — a
  NetworkPolicy bug fix can't rule out Kata/gVisor runtime classes, so the
  container runtime class is unconfirmed. A plain-pod read is the most
  defensible default, but treat it as inference, not vendor fact.)
  Per-agent identity = **AgentID (OAuth2)** with secret injection via
  SecretKeyRef.
- **Deployment/pricing, INFERRED (WSO2's own wire release via
  GlobeNewswire):** Apache 2.0, self-hosted or managed SaaS; GA adds
  "per-agent, per-environment agent identity controls, MCP-level governance
  and a sandboxed runtime"; real-time agent suspension; MCP governance via
  MCP proxy + scopes. Webinar Sep 29.
- **Reception:** nothing found beyond wire syndication — no independent
  developer reaction yet.
- **Implication:** WSO2 is now a *grounded* OSS "sovereign" alternative with
  k8s-pod sandboxing + NetworkPolicy egress + AgentID identity. On the
  baseline's isolation scorecard it lands in the **"Containers on shared
  infra" tier** (pods sharing the cluster kernel, runtime class
  unconfirmed) — weaker than spark-vm's per-VM tenant row, but fully
  self-hostable under Apache 2.0. That is the honest comparison to make when
  it comes up: spark-vm's isolation story (own VM, jail) still outranks
  pod-level sandboxing, but WSO2 now ships the multi-tenant identity + MCP
  governance story we don't.

## 3. OpenAI Agents API beta (C9) — terms details, no new partners

- **Partners, no change:** still the same nine (Blaxel, Cloudflare, Daytona,
  DigitalOcean, E2B, Modal, Oracle, Runloop, Vercel) — confirmed across
  three third-party recaps (INFERRED).
- **Terms detail, INFERRED (third-party characterization of OpenAI's docs):**
  no separate Agents API fee — pay model tokens + tools; OpenAI-hosted
  sandboxes billed at standard container rates. Hosted sandbox specifics:
  network enabled by default (template policy can change), outbound can be
  disabled or allowlisted, files persist across turns while the sandbox
  exists, artifacts downloadable after expiry, inactive sandbox deleted
  after 1 hour.
- **Compliance caveat, INFERRED (third-party):** US-only data residency
  during beta, and **no Zero Data Retention even with a self-hosted
  sandbox** — a material enterprise constraint for anyone benchmarking
  "no session clock" style persistence stories against the platform
  default. Platform defaults set the bar our hosted story must clear (C9's
  point stands, now with terms attached).
- **Background context (Apr 28, 2026 — NOT a Sep move; corrected from a
  misdated research note):** the OpenAI × AWS partnership expansion —
  OpenAI models + Codex on Bedrock, "Amazon Bedrock Managed Agents powered
  by OpenAI" (every agent gets its own identity, full auditability, runs
  inside the customer's environment) — was announced April 28, 2026, one
  day after OpenAI and Microsoft ended the exclusivity agreement (Apr 27).
  Kept here as background corroboration of the agent-infrastructure
  land-grab thesis, not a sandbox launch: identity + audit +
  customer-environment execution are becoming the table stakes.

## 4. TermSquad re-check (C1) — CORRECTION: herdr#3415 is fixed, not open

- **Pricing, VERIFIED (refetched today):** no change — $9/$19/$29/$49 with
  specs identical to baseline (2/4/8 vCPU, 4/8/12/24 GB, 40/75/100/200 GB
  NVMe). "AI subscriptions and usage are not included" still explicit.
- **Features page, VERIFIED:** no change — session-model lines match the
  baseline; still BYO-agents ("You bring compatible Linux agents and your
  own subscriptions or API keys"); no agent-as-customer story; no isolation
  whitepaper.
- **CORRECTION, VERIFIED via GitHub API:** herdrdev/herdr#3415 (the reboot
  race that SIGHUPs panes during server shutdown, triggers `persist.clear`,
  and loses the whole session on next boot) is **closed as of 2026-09-07**
  (labels: bug, p0; the research worker's GitHub-API read shows
  "Implemented on master and queued for the next release" → "Released in
  v0.9.0"). The bug was already fixed and released *before* the baseline
  pass, so the analysis's "open upstream bug" characterization is **stale**.
  Remaining conditional: whether TermSquad ships herdr ≥ 0.9.0 — their
  managed platform version is opaque. The honest line is now: "reboot-loss
  race (herdr#3415) — fixed upstream in v0.9.0 (Sep 7); exposure now hinges
  on TermSquad's unadvertised herdr version," not "open bug."
- **Color, INFERRED (GitHub issue search):** two further open upstream
  session-fragility issues surfaced (WSL2 server-socket drop #2006,
  Windows Local-server disconnect #3858) — herdr's session layer still has
  active stability work, but neither is TermSquad-specific; treat as
  background, not a talking point.

## 5. Baseten/Blaxel (C11) — releases moving, no product; watch stays open

- **Correction (verified via the blaxel-ai/sandbox releases API today):**
  the sandbox repo shipped **v0.2.57 on Sep 9**, **v0.2.58 on Sep 15**, and
  **v0.2.59 today (Sep 18)** — the "latest v0.2.48 (~Aug 19)" line in the
  research notes sourced the docs changelog instead of the sandbox repo.
  The releases are minor (v0.2.59: welcome-response API-link tweak;
  v0.2.58: dep-alert fix + unix-socket export skip), so C11 stays open for
  the acquisition-product watch, but the basis is corrected.
- "Agent Drive" shared filesystem was a ~4-week-ago private-preview
  announcement (INFERRED from LinkedIn recaps), not new. Baseten's newest
  public material remains the Sep 10 acquisition + "Hosted Tools" blog
  (dateless). No shipped code-execution product yet.

## 6. General scan (Sep 15 → today) — nothing material

No new launches, pricing changes, or features found across E2B, Daytona,
Modal, Vercel Sandbox, Cloudflare Sandbox, Northflank, Runloop,
Microsandbox, or FastGPT. Two items excluded as recycled: Cloudflare's
"Dynamic Workers ditch containers" coverage (March/April 2026 launches),
Vercel's $1M sandbox-escape bounty (~Aug 20, pre-window). OpenAI and
Microsoft ended their exclusivity agreement on Apr 27, 2026 (announced
Apr 28) — April-era background, not a September move, and not
sandbox-specific.

## 7. What changes in the strategy docs

Deltas for the next consolidation of `docs/COMPETITOR_ANALYSIS.md`
(PRs #26/#34):

1. **AgentComputer:** replace "built-on-Sprites (uncertain)" with own
   Firecracker-based VM manager facts (Firecracker microVM + jailer on bare
   metal; OSS repos, 2 stars each, last updated 2026-04-30; repo ≠ proven
   deployment); keep in the baseline's **"Per-customer computer"** isolation
   tier (placement confirmed on primary evidence, was tentative); egress row
   stays undocumented; add Enterprise tier; keep rate-card parity
   ($0.07/CPU-hr, $0.04375/GB-hr, $0.000683 hot, $0.000027 cold) as
   unexplained. Note the cold-storage idle-economics detail
   (stopped ≈ $0.000027/GB-hr, ~25x under hot) for C5.
2. **TermSquad:** downgrade herdr#3415 from "open upstream bug" to "fixed
   in herdr v0.9.0 (Sep 7); exposure now hinges on TermSquad's
   unadvertised herdr version." Pricing/features unchanged.
3. **OpenAI Agents API:** add terms (no API fee; tokens + container-time;
   network-on-by-default, outbound allowlistable; 1h inactive deletion;
   US-only, no ZDR even self-hosted). No new partners. Log the
   **Apr 28, 2026** OpenAI×AWS partnership as April-era background
   corroboration of the agent-infrastructure land-grab thesis — not a
   September move, not a sandbox launch.
4. **WSO2:** add runtime details — k8s pod sandboxing w/ NetworkPolicy
   egress (runtime class unconfirmed — do NOT write "not microVMs, not
   gVisor"), AgentID OAuth2 identity, Apache 2.0, self-host or SaaS;
   lands in the baseline's **"Containers on shared infra"** isolation
   tier, **task-scoped** market-split column (execution sandbox for agents,
   not a persistent computer); webinar Sep 29; no independent reception
   yet.
5. **C11 stays open** (Baseten/Blaxel: nothing shipped).
6. **C12 narrows to an egress-only gap** (everything else now covered).

## Sources

Primary: [agentcomputer.ai/docs](https://www.agentcomputer.ai/docs),
[agentcomputer.ai/pricing](https://www.agentcomputer.ai/pricing) (refetched
today);
[AgentComputerAI/computer-host](https://github.com/AgentComputerAI/computer-host)
and
[AgentComputerAI/computer-guest](https://github.com/AgentComputerAI/computer-guest)
(via GitHub API: 2 stars each, updated 2026-04-30);
[herdrdev/herdr#3415](https://github.com/herdrdev/herdr/issues/3415) (via GitHub API:
state closed, closed 2026-09-07, labels bug/p0);
[wso2/agent-manager PR #1496](https://github.com/wso2/agent-manager/pull/1496)
(sandboxed pods + NetworkPolicy egress, AgentID OAuth2).
Third-party (INFERRED, not independently verified): InfoWorld/RuntimeWire/
Greensboro Times/Forkast on Agents API terms; GlobeNewswire on WSO2 GA;
LinkedIn recaps on OpenAI×AWS and Blaxel "Agent Drive"; Blaxel docs
changelog (blaxel-ai/docs) showing no September entries.
