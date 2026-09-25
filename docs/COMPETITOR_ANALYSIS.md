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
  `docs/COMPETITOR_WATCH_YYYY-MM-DD.md`, with `_EVENING`/`_NIGHT`/`_MORNING`/`_MIDDAY`/`_NOON`/`_EARLY_AFTERNOON`/`_MID_AFTERNOON`
  suffixes for same-day repeats; each is delta-only against the previous
  watch doc. (`_NOON` admitted by the 2026-09-24 noon pass;
  `_EARLY_AFTERNOON` by the 2026-09-24 early-afternoon pass — the
  09:54 pass had already taken `_AFTERNOON`; `_MID_AFTERNOON` by the
  2026-09-24 mid-afternoon pass, following the 2026-09-23
  `_MID_AFTERNOON` precedent.)
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
| **E2B** | Task-scoped sandbox | Firecracker microVM per sandbox, SDK-first, templates-as-code | Hobby $0 + $100 one-time credit (1h sessions, 20 concurrent); Pro **$150/mo** + usage (24h sessions); ~$78/mo usage for one continuous 2vCPU/512MB box; $21M Series A **2025-07-28** (Insight Partners lead; dated sources: PRNewswire wire + SiliconANGLE URL) |
| **Daytona** | Task-scoped sandbox | Containers (+VM/Windows classes), stateful, stop/archive/pause/fork, GPU (ephemeral) | $200 free compute, no plan floor; $0.0504/vCPU-hr + $0.0162/GiB-hr; GPU on request (H100 listed $2.27/hr) |
| **Modal** | Task-scoped sandbox | gVisor, GPU inside sandbox (T4–B300), memory snapshots | Sandbox tier ≈3x standard rate (arithmetic checks out — standard-rate half corroborated only by secondary sources; the pricing page shows the Sandbox+Notebooks tier only); $0.0710/vCPU-hr equiv; free Starter, $250/mo Team; in talks to raise at ~$15B valuation (2026-09-23, Bloomberg/Reuters THIRD-PARTY; $355M May raise at $4.65B) |
| **Vercel Sandbox** | Task-scoped sandbox | Firecracker microVM, 45min/24h sessions, snapshots; **64 GB ephemeral NVMe default** (SDK ≥3.0.0/custom image; 32 GB on deprecated runtimes — C32 resolved, see "Watch update — 2026-09-23"); Drives public beta (persistent, ≤16 TiB/drive, usage-based pricing) | Active-CPU billing ($0.128/vCPU-hr); Hobby allotment; Pro credit |
| **Cloudflare Sandbox** | Task-scoped sandbox | Containers on Workers, sleeps at 10 min idle, disk resets on sleep | Active-CPU billing ($0.072/vCPU-hr); $5/mo Workers Paid floor |
| **Runloop** | Task-scoped sandbox | Devboxes as "isolated, ephemeral virtual machines" (hypervisor unnamed), Network Policies, SWE-bench focus, suspend/resume (Pro) | $0.108/CPU-hr; free Basic; $250/mo Pro |
| **Blaxel** | Task-scoped sandbox | Perpetual sandboxes, scale-to-zero ~5s, hibernate — acquired by Baseten (announced 2026-09-10); Baseten's newest "Hosted Tools" blog names Blaxel as its sandbox foundation ("fast, isolated, persistent sandboxes and storage where developers can run their own agentic workflows and tool execution") | Per-second usage; SOC 2 Type II / ISO 27001; HIPAA via $250/mo BAA add-on |
| **Microsandbox** | Task-scoped sandbox (OSS) | libkrun microVM, network-layer secret injection | Free, self-hosted (YC F26) |
| **Docker Cloud Sandboxes** (launch Sept 24, C45) | Task-scoped sandbox | Same microVM as local Docker Sandboxes, on Docker-managed compute; `sbx move --to cloud` (bidirectional filesystem migration); kits (Claude Code, Codex, Copilot, Antigravity, Open Code, Hermes), MCP gateway, per-agent network policies, secrets proxy-injected per request | **PAYG per-second:** Micro 1vCPU/2GiB $0.07/h → XL 16/32 $1.12/h; paused free; volumes/egress/images free; sessions ≤24h; limited-time $250 free credit; GA-venue garnish 2026-09-24 — onstage launch at WeAreDevelopers North America (Docker president Mark Cavage, THIRD-PARTY), keynote blog "available today with pay-as-you-go pricing" (VENDOR-VERIFIED), Sandbox Kits → standard OCI images + CNCF submission commitment, Hermes first-class Kit demo onstage; Register dated-2026-09-24 corroboration (THIRD-PARTY): named shapes Micro 1vCPU/2GiB $0.07/h → XL 16/32 $1.12/h, per-second, OCI-standard Kits — matches vendor figures value-for-value; pre-midnight garnish: launch availability VENDOR-VERIFIED on docker.com's own Sept-24 posts ("available today", 1–16 vCPUs, one-command laptop-to-cloud move, pay-as-you-go), Kits-as-standard-OCI VENDOR-VERIFIED ("Kits make authority reproducible"), BAND Python Kit for Docker Sandboxes announced Sept 24 (THIRD-PARTY) — first third-party Kit-ecosystem signal; post-mid-evening garnish (VENDOR-VERIFIED): first vendor-sourced price-and-terms package — one-command `sbx move --to cloud`, per-second, Micro $0.07/hr → XL $1.12/hr, paused free, 24h sessions, $250 new-account credit |
| **Docker Sandboxes** (morning pass) | Task-scoped sandbox | Local microVMs for coding agents (`sbx` CLI), workspace bind-mounts, **v3 kits** (OCI-based packages: agent workload + reusable mixins for tools/config/credentials/network/instructions — C34), skills tri-state (`off/readonly/readwrite`, read-only default), host-side credential proxying with consent-default-decline, idle auto-stop; centrally managed network/filesystem/MCP policies + sign-in enforcement + audit logs via paid Docker AI Governance | **Free** — `sbx` CLI, incl. commercial use, no per-seat fee ([vendor FAQ](https://docs.docker.com/ai/sandboxes/faq/)); org governance paid (contact sales) |
| **WSO2 Agent Manager** (evening pass) | Task-scoped sandbox (OSS control plane) | k8s pods + [NetworkPolicy egress](https://github.com/wso2/agent-manager/pull/1496) (runtime class unconfirmed), AgentID (OAuth2) per-agent identity, secret injection via SecretKeyRef, MCP proxy governance, real-time agent suspension | Free, self-hosted (Apache 2.0) or managed SaaS (pricing not published); webinar Sep 29; no independent developer reception found yet |
| **Boat** (tracked set; 2026-09-22 consolidation; **renamed from ASCII ~2026-09-17** — C40 deduped into this row) | Task-scoped sandbox / persistent computer | Sandboxes for coding agents; per-second billing, "a stopped sandbox costs nothing"; xlarge (16 vCPU / 32 GB) is capacity-gated — needs a $100+/mo plan *and* operator allocation (vendor statement). Rename VERIFIED this run: `box.ascii.dev`, `boat.dev`, `ascii.dev` serve byte-identical product pages; YC's company page now `ycombinator.com/companies/boat` (YC F26); yc-oss mirror dates the rename 2026-09-17 (`former_names`: ["Ascii box","Ascii"]); the old YC slug `ycombinator.com/companies/ascii` now serves a **301 → `/companies/boat`** (VERIFIED 2026-09-24 midday — harder rename evidence than the page copy). Hardest evidence yet (VERIFIED 2026-09-24 late midday): the vendor's own API docs at `docs.ascii.dev/box/api/v1` render as **"Boat Public API v1"** — the legacy ASCII domain's developer surface brands the product *Boat* (`/box` path and box.ascii.dev endpoints persist). The documented API covers sandbox lifecycle (provisioning → ready/idle → running → archiving → archived; stop/archive, resume, fork, delete; desktop streaming; Idempotency-Key; per-sandbox API keys; data-retention API) plus a `prompt` endpoint running work through built-in agent harnesses `codex`, `claude-code`, `pi`, `opencode`, `prime-agent`, `kimi` (INFERRED read: Boat bundles coding-agent harnesses as first-class providers). Canonical domain now boat.dev. | **$0.036/h** default (4 vCPU / 8 GB / 50 GB); xlarge $0.200/h; 25 free-hour trial; $20/mo = $20 of time; EU-only DE/FI/FR (FAQ verbatim — Germany, Finland, France; VERIFIED 2026-09-24 midday; folded from the deprecated C40 pointer row). |
| **DigitalOcean Managed Agents** (2026-09-22 consolidation) | Managed agent stack (task-scoped) | Harness Runtime (microVM per session, pause/resume/fork) + Action Gateway (16,000+ tools via one managed MCP endpoint, credentials brokered at execution time) + Inference Engine; runs unmodified Claude Code / Codex / OpenCode / Hermes / LangGraph | **$0.044/vCPU-hour active CPU** (per-second; active-CPU billing coming soon — interim 25% of allocated vCPUs; "zero while waiting" holds only for paused sessions), $0.0095/GB-hour memory, snapshots **$0.005/GiB-month (vendor's 2026-09-22 investor release, evidence-backed)** — 2026-09-24 overnight pass RETIRED the carried $0.05/GiB-month docs figure as current (standalone docs pricing subpage unlocatable 5 consecutive passes as of the 2026-09-24 post-overnight pass — but the docs surface is now re-located and VENDOR-VERIFIED: product index "Last verified 21 Sep 2026", Harness Runtime index "Generated on 25 Sep 2026" (UTC), manage-sessions how-to "Last verified 21 Sep 2026" (sessions auto-pause after 15 min of inactivity — "suspends its compute while preserving the workspace"); the index confirms a Details section ("pricing, availability, limits") exists but exposes no URL — next pass tries doctl-linked docs URLs; current general-snapshot snippets (page last verified 8 May 2024) read $0.06/GB-month Droplets / $0.06/GiB-month volumes; the 10× discrepancy framing is withdrawn — see "Watch update — 2026-09-24 (post overnight)" for the re-location and the prior $0.05 history); $5 new-user credit |
| **Boxd** (2026-09-22 consolidation) | Persistent computer | "Composable computers" — KVM VMs with live memory forking in under 200 ms (vendor claim), snapshots/checkpoints, real SSH, per-machine HTTPS subdomain; self-hosted option ("run the whole platform on your own hardware") | Credit-based: €0.049/vCPU-hour running, €0.015/GiB-hour resident RAM, €0.0001/GiB-hour disk written; €30 free credits (**rate card VERIFIED 2026-09-23** — first own-page fetch, C29) |
| **Upstash Box** (2026-09-22 consolidation; **own-docs VERIFIED 2026-09-24**) | Task-scoped sandbox / persistent computer | **VERIFIED on the vendor's own docs** ([Box quickstart](https://upstash.com/docs/box/overall/quickstart), read 2026-09-24): *"Upstash Box lets you give your AI agents a computer. Every Upstash Box is a **secure, isolated cloud container with an AI Agent built in**. Spin up as many as you want in parallel. Each one includes a full environment with a filesystem, shell, git, and a runtime."* Runtimes default Debian (glibc); keep-alive boxes (`keepAlive: true`) stay on between sessions; SSH access with a Box API key; *"Freeze a box anytime, and continue days or even weeks later with perfect resumability."* Standing datapoints: snapshot/restore API for reusable prepared environments, branching from snapshots, full outbound networking by default, 22.5 Gbps hosts on AWS; pause/resume unavailable with keepAlive enabled | **THIRD-PARTY** (vendor's own comparison blog, snippet-only this run): $0.10/$0.20/$0.40 per active CPU-hour (small/medium/large); free tier 10 boxes, 5 CPU-h/mo, $1 LLM budget, no card required |
| **Freestyle** (2026-09-23 overnight, C37) | Persistent computer | "VMs for AI Agents" — hardware-virtualized Linux microVMs with live cloning, pause/resume, nested virtualization (Docker inside), custom domains, WireGuard tunnels, FUSE/eBPF; boot claim qualified 2026-09-24: vendor headline "65 ms" is marketing, docs give the honest number — **p99 under 400ms** (both VERIFIED on vendor's own pages); "run forever" with idle-timeout disabled (the anti-suspend-on-idle posture) | **Own pricing page VERIFIED 2026-09-24** ([freestyle.sh/pricing](https://www.freestyle.sh/pricing)): vCPU $0.04032/h (200/h included mo), GiB Memory $0.0129/h (400/mo), GiB Storage $0.000086/h (60,000/mo), Data Transfer $0.02/GB (50 GB free / 500 GB paid); Free / **Hobby $50/mo** (FAQ: "$50 on Hobby covers your first $50 of usage") / Pro (+ Enterprise custom); Pro's exact monthly fee not printed (only "monthly fee is a commitment that doubles as usage credit") — carried; 2026-09-24 post-overnight pass re-opened freestyle.sh/pricing VENDOR-VERIFIED — still no Pro dollar amount on the public page; Hobby $50 re-confirmed ("$50 on Hobby covers your first $50 of usage"); dashboard-internal pricing not checked |
| **Tensorlake** (2026-09-23 overnight, C38; **2026-09-24 night, C46**) | Task-scoped sandbox | "Sandboxes for AI Agents" — Firecracker microVMs + versioned POSIX filesystem (`tl fs`: autosave, snapshot/time-travel, restore to any point), live fork/clone, OCI import, ~1 s suspend/resume with meter-stops-on-suspend, auto-suspend idle, SOC 2 Type II + HIPAA; own benchmark blog quotes **$10 per 1k pages** ($0.01/page) (VERIFIED, document-OCR line) | **Pricing page published 2026-09-24** ([tensorlake.ai/pricing](https://tensorlake.ai/pricing), "UPDATED Q3 2026", VERIFIED own-page) — prices the Firecracker-microVM sandbox product, not OCR: Free / Usage Credits ($5–20 packs, $0.01/CU) / **Pro $250/cycle** (25,000 CU) / Enterprise; Active CPU $0.07/core-hr (credits) / $0.042 (Pro); RAM $0.015/GB-hr / $0.009; Disk $0.0002/GB-hr / $0.0001; **snapshot storage $0.07/GB-month** (richest in the corpus); egress free; SOC 2 Type 2 all tiers, HIPAA Pro+ |
| **Simular Sai** (2026-09-24 midnight, C39) | Persistent computer (computer-use fleet) | "Sai turns any computer — a private cloud VM or your own device — into a self-operating machine": persistent Simular-provisioned cloud VMs (Windows/Linux) or BYOD (Mac/Windows/Linux); computer-use agent clicks/types through real interfaces; approval-gated critical actions, encrypted password input, skills + schedulable workflows, live visibility + takeover; fleet up to 100 machines ("less than $1" per run, vendor claim); Agent S framework, OSWorld-first claim | **RESOLVED 2026-09-24 (night pass):** sai.work/pricing exists (structure VERIFIED on sai.work; tier numerals in stripped elements — figures from Simular's own-domain comparison pages, VERIFIED: **Free (Explore, daily credits) / $50/mo (Pay as you go) / $500/mo (Sai Unlimited) / Enterprise (custom)**); dume.ai's $20/$200/$500 = stale private-beta pricing (THIRD-PARTY, superseded) |
| **Boat** (C40, **DEPRECATED ROW — deduped** 2026-09-24 morning) | Persistent computer | ASCII renamed to Boat ~2026-09-17 (same product: three legacy domains box.ascii.dev/boat.dev/ascii.dev serve byte-identical pages; YC F26 company page now ycombinator.com/companies/boat — THIRD-PARTY, YC is the accelerator not the vendor; the old YC slug ycombinator.com/companies/ascii serves a 301 → /companies/boat, VERIFIED 2026-09-24 midday; the vendor's own API docs at docs.ascii.dev/box/api/v1 render as "Boat Public API v1", VERIFIED 2026-09-24 late midday). **Canonical Boat data lives in the tracked-set Boat row above** — this row retained for provenance (historical FAQ datapoints, e.g. EU-only DE/FI/FR, retained here). Pricing VERIFIED on own page pre-dedup: $20/mo plan = $20 sandbox time, $0.036/h for 4 vCPU / 8 GB / 50 GB, billed per second, only while running; 100–2,000 sandboxes by plan; $20 auto-refill packs; EU-only DE/FI/FR (FAQ). | See tracked-set Boat row |
| **Alibaba Cloud FC Agent Sandbox** (2026-09-24 morning, C41) | Task-scoped sandbox (billing corpus) | New pay-as-you-go sandbox billing rolling out from 2026-07-31 (UTC+8), still invite-only preview: per-second billing, hourly settlement; formula = unit price × run duration. Three editions: Eco (cheapest, occasional perf fluctuation, no hibernation — startups/tool-use validation), Std (+hibernation — enterprise copilots), Pro (+deep and shallow hibernation, millions of concurrent requests — RL sampling/high-concurrency agents). Hibernation: active = vCPU+mem+disk (15 GiB disk free); light (Pro only) = mem+disk, vCPU free; deep = vCPU+mem free, billed on (memory×2 + disk) GiB; FAQ: call `kill()` when the task is complete. **Scope (VERIFIED):** applies ONLY to E2B-SDK integration — existing E2B instances auto-upgrade to Pro; Sandbox Functions/AgentRun Sandbox customers must migrate. Lane characterization (INFERRED): task-scoped compute, **not** agent-VM-shaped — no SSH/Desktop surface in the Features index; closer to E2B/Daytona pause semantics than a persistent dev VM. | Eco **0.00936/vCPU-h + 0.004608/GiB-h** (2 vCPU / 4 GiB / 15 GiB ≈ **$0.037/h**); Std 0.01224 / 0.006012; Pro 0.01872 / 0.009360; disk 0.00031896/GiB-h (0.00025308 ex-mainland). **Snapshot pricing:** Snapshot Storage Usage = Memory Specification × 2 + Disk Specification, charged at the Disk Unit Price × storage duration (all VERIFIED on aliyun-fc/fc-docs; the 15 GiB free disk allowance does not apply in deep hibernation, VERIFIED 2026-09-24 late-afternoon pass). Re-verified 2026-09-24 (post overnight): repo HEAD pin 96ff8a8 unchanged, all digits unchanged; the page's preview notice confirms invite-only, allowlisted-in-batches rollout. Re-verified 2026-09-25 (post midnight): repo HEAD pin **REVERTED** — short `39b6c3a2` is the same commit as the pre-overnight full SHA `39b6c3a20ec4597cceda497a4d8badf5384e2022` (2026-09-21), a revert from `96ff8a8`, not a second move (two real positions only; no phantom third). All pricing digits re-read live at HEAD and unchanged (Eco/Std/Pro vCPU+mem+disk), preview still invite-only, allowlisted-in-batches |
| **Namespace Devboxes** (2026-09-24 late midday, C42; **adjacent → in-lane**) | Persistent computer / ephemeral devboxes | *"Devboxes for Coding Agents"*: Linux and macOS machines where a coding agent clones a repository, installs dependencies, runs commands, and returns the result (ephemeral Devboxes); Pool API (`devbox acquire`); `devbox exec` / `logs` / `upload`; egress filtering via `network_policy.egress_domains`; secrets through the Namespace vault; native integrations — **Claude Managed Agents, Cursor Cloud Agents, and Devin all run on Namespace Devboxes**. All VERIFIED on the [vendor's own docs](https://namespace.so/docs/devbox/agents) (read 2026-09-24) — reverses the midnight pass's adjacent verdict. Sizes S→XL (burst 4 vCPU/8 GB → 32 vCPU/64 GB) at the THIRD-PARTY snippet layer | No published pricing in the surveyed docs |
| **Google Gemini Agent Environment** (2026-09-24 afternoon, C43) | Managed agent sandbox (task-scoped compute) | *"Environments are managed Linux sandboxes that give agents an isolated place to execute code and persist files"* — reusable via `environment_id`; sources (git repo mount); network allowlists; env vars / credential references; pre-installed Ubuntu toolchains; current examples use agent string `antigravity-preview-09-2026`. All VERIFIED on the [vendor's own docs](https://ai.google.dev/gemini-api/docs/agent-environment) (read 2026-09-24). Sept-17 detail at the THIRD-PARTY layer: Files API (persistent file upload/list/download into the sandbox); Credentials API (secrets injected as env vars/MCP headers so the model never sees the raw secret — a sixth convergent placeholder-swap datapoint, noted for the secrets turns); vendor-claimed ~40% fewer output tokens on file edits, +8% task completion; preview compute not billed. Sibling of Agent Substrate (C36) — this is the Gemini-API-side managed sandbox surface, not the GKE-side one. | "Environment compute (CPU, memory, sandbox execution) is **not billed** during the preview period" — verbatim VENDOR-VERIFIED 2026-09-24 (ai.google.dev/gemini-api/docs/agent-environment, page "Last updated 2026-09-24 UTC"); fixed allocations 4 CPU cores / 16 GB memory; no published pay-as-you-go pricing in the surveyed docs |
| **Google Gemini Enterprise Agent Platform sandboxes** (2026-09-24 late evening, C44) | Managed agent sandboxes (task-scoped compute, GA) | *VENDOR-VERIFIED on Google's own release notes (read 2026-09-24): "Computer Use and Shell sandboxes in Gemini Enterprise Agent Platform are now generally available (GA)." (Sept 9, 2026)* — Shell sandboxes run untrusted shell commands, install packages, and manipulate files in an isolated Linux container via direct `/exec` API calls (Shell sandbox quickstart linked from the release notes); the same release ships VPC Service Controls & Private Service Connect, CMEK (Cloud KMS, disk + snapshot checkpoints), and **pause/resume for sandboxes** (deschedule compute for idle sandboxes while preserving filesystem state and connection identity; resume in seconds (idle-suspend economics datapoint — INFERRED read, convergent with C36 Agent Substrate's zero-idle posture and DO's 305 ms resume claim)). A third Google agent-sandbox surface alongside C36 (GKE-side open-source runtime) and C43 (Gemini-API-side Environments); the GA is pre-window (Sept 9) but filed now — reach-back per the #82 pattern, explicit queued candidate verified on a primary source. | No published pay-as-you-go pricing in the surveyed release notes |
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

### Boxd — first corpus entry (C29, VERIFIED — watch continues)

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
  plane. 2026-09-25 (post midnight) THIRD-PARTY pricing color: hosted-sandbox
  containers $0.03–$1.92 per 20-min session (1 GB–64 GB); ZDR inapplicable
  even with a self-hosted sandbox (finance.biggo.com) — corroborates the
  no-ZDR characterization above. API still public beta (THIRD-PARTY ×3 this
  pass); GA absence VENDOR-VERIFIED (carried).
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
Daytona, DigitalOcean, E2B, Modal, Oracle, Runloop, and Vercel." (Launch date 2026-09-10 — confirmed on OpenAI's own changelog by the
2026-09-24 noon pass; the launch-post body carries no visible date.)
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
layer moved — C30 precedent). Re-read live 2026-09-24 (post overnight):
full vendor verification — 10x density, zero-trust kernel/network
isolation, snapshots to local disk + GCS, open source portable to any K8s;
availability unchanged (all GKE customers, non-production; production GA
via allowlist); THIRD-PARTY cross-checks (thecloudpod, itbrief) consistent.
See "Watch update — 2026-09-24 (post overnight)".

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

## Watch update — 2026-09-23 (overnight): C29 rate card VERIFIED, C37/C38 new in-lane entries, Automaid lane-drift confirmed

Three corpus actions this pass (primary-source-verification and
new-entry folds per the C32/C31 precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-23_OVERNIGHT.md` §§1–5).

**C29 upgrade — Boxd rate card moves UNVERIFIED → VERIFIED.** The
https://boxd.sh pricing FAQ was fetched and read on the vendor's own
page this pass (first successful own-page fetch — the two prior passes
were UNVERIFIED debt): **€0.049/vCPU-hour** while running,
**€0.015/GiB-hour** resident RAM (running or standby),
**€0.0001/GiB-hour** of disk actually written (never provisioned size),
**€30 free credits** for every new account; no idle-compute charge;
hibernated machines pay disk only. The figures stand as quoted since
the 2026-09-22 filing — this pass upgrades only the provenance layer.
Also VERIFIED on the same page: real KVM VMs (own kernel, not
containers); Ubuntu 24.04 defaults 2 vCPU / 8 GB / 100 GB; sub-200 ms
live memory forks; suspend-to-disk with instant resume; checkpoints,
snapshots; self-host option; per-machine HTTPS subdomains; org-level
secrets/domains; MCP server for Claude Code / Codex / opencode. The
"resume in under a millisecond" marketing figure stays
vendor-published-only, no methodology — NOT a C14 benchmark input.
Competitive read (INFERRED): Boxd is now the most fully vendor-verified
persistent-machine row in the corpus — the pricing is settled, and the
"hibernated machines pay disk only" posture matches spark-vm's
suspend-on-idle thesis (see `docs/PRICING_THINKING.md`) from a
pay-per-use angle.

**C37 new — Freestyle ("VMs for AI Agents", in-lane).** VERIFIED on the
vendor's own page this run (https://freestyle.sh): instant,
hardware-virtualized Linux microVMs for AI agents with live cloning,
pause/resume, nested virtualization (Docker inside), custom domains,
WireGuard tunnels, full-kernel features (FUSE, eBPF); vendor claims 65
ms boot and "run forever" with idle-timeout disabled; SSH / VS Code /
Cursor access. Pricing stays **THIRD-PARTY only** (own pricing page not
read this run; the Upstash 15-provider comparison gives wall-clock
per-second billing, $0.04032/vCPU-h, $0.0129/GiB-h, free tier 200
vCPU-h + 400 GiB-h/month, with a docs-vs-pricing discrepancy on
whether persistent VMs are free — all UNVERIFIED until the own page is
read). Competitive read (INFERRED): the 65 ms boot claim, if honest, is
the fastest boot figure in the corpus (Sprites warm 100–500 ms and DO 305
ms p50 are both vendor-published figures, neither independently measured
— see the §C26 and §C29 sections; Boxd's sub-200 ms fork is a different
mechanic);
treat it as vendor marketing until someone measures it (C14
discipline). The "run forever with idle-timeout disabled" line is the
anti-suspend-on-idle posture — the direct opposite of spark-vm's
suspend-on-idle thesis; both are cost-floor arguments, and the corpus
now holds both.

**C38 new — Tensorlake ("Sandboxes for AI Agents", in-lane).**
VERIFIED on the vendor's own page this run (https://tensorlake.ai):
Firecracker microVM sandboxes for AI agents paired with a versioned
POSIX filesystem (`tl fs`, autosave, snapshot/time-travel),
hosted/mountable Git, and a sandbox-native orchestration runtime.
VERIFIED mechanics (own page): suspend/resume preserving memory +
processes + filesystem (~1 s wake, meter stops on suspend); live VM
fork/clone (memory + filesystem copied whole); `tl fs` autosaves
settled writes to durable storage, snapshot = permanent checkpoint,
restore to any point in time, read-only shared mounts; OCI image import
with high-fidelity ext4 conversion; auto-suspend on idle with
wake-on-request; SSH / VS Code / Cursor / PTY-over-WebSocket remote
dev; Harbor eval integration; SOC 2 Type II + HIPAA; own SQLite
benchmark vs Vercel/E2B/Daytona/Modal (own marketing — take as
marketing). Pricing: not observed on the homepage this run — no
pricing claim made. Competitive read (INFERRED): Tensorlake's
versioned-POSIX-fs-plus-snapshot story is the closest corpus analog to
spark-vm's own snapshot/branch thinking for #47's branching control
plane — and the "meter stops on suspend" line is another suspend-on-idle
data point, this time at per-second granularity. The HIPAA + SOC 2 Type
II badge is the compliance floor spark-vm's hosted product will have to
match to sell into the same customers.

**Automaid — lane-drift CONFIRMED, watch slot closed.** The own-page
fetch succeeded for the first time this pass (https://automaid.it.com):
a recurring-workflow automation SaaS ("AI agents for recurring work",
Zapier-style: WhatsApp scheduler, Stripe invoice follow-ups, form
triage, content-calendar sync, payment review workspaces, 3,000+ app
integrations). Not VM-for-agents infrastructure; not a lane
competitor. It was never a corpus entry — this note closes the
watch-list slot so later passes stop re-attempting it.

## Watch update — 2026-09-24 (midnight): C39 Simular Sai GA, Freestyle boot-claim qualification, E2B Series A dated, Modal valuation color

Four corpus actions this pass (primary-source-verification and
new-entry folds per the C32/C37/C38 precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_MIDNIGHT.md` §§1–5).

**C39 new — Simular "Sai" ("Your First Robosecretary", in-lane,
computer-use fleet).** The 2026-09-23-late-overnight pass's owed
vendor-verification is closed: sai.work fetched and read this run
(VERIFIED); the company press release datelined "Palo Alto,
September 23, 2026" confirms GA from invite-only (VENDOR-ATTESTED
via company-issued release, wire-syndicated). Sai turns "any
computer — a private cloud VM or your own device — into a
self-operating machine": persistent Simular-provisioned cloud VMs
(Windows/Linux) or BYOD (Mac/Windows/Linux); the computer-use agent
reasons and acts inside real interfaces (browsers, desktop apps);
approval-gated critical actions, encrypted password/verification-code
input, skills and schedulable saved workflows, live visibility +
takeover, results via iMessage/SMS/Telegram. Fleet model: up to 100
machines in parallel for "less than $1" (vendor claim); Minecraft
demo ran autonomously 14 hours; neuro-symbolic compile-and-replay
cuts token consumption ≥90% on repeated long-horizon office tasks
(all vendor claims); Agent S framework claims first to outperform
human performance on OSWorld. **Pricing conflict unresolved:**
simular.ai's own SEO comparison page quotes Free (daily credits) /
$50/month pay-as-you-go / $500/month Sai Unlimited / Enterprise,
while dume.ai's THIRD-PARTY comparison attributes $20/$200/$500 tiers
to sai.work — sai.work's fetched pages carry no pricing table, so
all Sai pricing stays UNVERIFIED against the vendor's own pricing
page (corpus field-table row records the conflict explicitly).
Competitive read (INFERRED): Sai is the first in-lane entrant on the
computer-use-fleet archetype — Simular provisions the cloud VMs and
the agent operates them, which overlaps spark-vm's remote-desktop
and 24-7 persistent-machine work (consumer flavor, not dev-sandbox,
so it sits beside the task-scoped rows rather than replacing them).

**C37 qualification — Freestyle boot claim.** The homepage headline
"A full Linux machine, ready in **65 ms**" is the marketing number
(VERIFIED on freestyle.sh); the honest vendor number is in the docs:
"provision in milliseconds, with **p99s under 400ms**" (VERIFIED on
freestyle.sh/docs). Field-table row updated to carry both. Pricing
stays THIRD-PARTY — no own pricing page found (likely behind the
dashboard / talk-to-us flow; dashboard probe is a standing ask).

**E2B row — Series A dated.** The standing owed item is closed:
**2025-07-28**, $21M Series A led by Insight Partners (PRNewswire
wire copy + SiliconANGLE's dated URL; Decibel, Sunflower Capital,
Kaya, Scott Johnston among followers; total $32M per vestbee,
THIRD-PARTY). The date now lives in the corpus E2B row.

**Modal row — valuation color.** In talks to raise at ~$15B
valuation (2026-09-23, Bloomberg via Reuters, THIRD-PARTY; May
raised $355M at $4.65B). Recorded as in-lane-adjacent color for the
sandbox pricing race, not a product move.

Not folded: Ascii Box stays an in-lane *candidate* (persistent
Ubuntu VM for agents, THIRD-PARTY only — own-site verification owed,
EU-only DE/FI/FR caveat); Namespace and Beam vetted as *adjacent*
(dev-compute and serverless-GPU respectively, not VM-for-agents-first);
C38 Tensorlake pricing watch remains open (no published pricing page);
C36 terms re-verified unchanged (allowlist-only production GA).

## Watch update — 2026-09-24 (predawn): C40 ASCII "boat", Sai pricing refined

Four corpus actions this pass (primary-source-verification and
new-entry folds per the C32/C37/C38/C39 precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_PREDAWN.md` §§1–5).

**C40 new — ASCII "boat" ("Cheapest, Most Powerful Sandboxes for
Agents", in-lane, persistent computer).** The midnight pass's owed
own-site verification is closed: box.ascii.dev fetched and read this run
(VERIFIED). The product is branded **"boat"**, not "Ascii Box":
persistent Ubuntu cloud VMs purpose-built for agents — full VMs
(Docker, systemd, databases, cron), 60fps integrated desktop + browser,
`boat` CLI (new/ssh/scp/exec/prompt/host/desktop/stop/resume), API +
SDKs, named snapshots, disk-level forking, port forwarding, secrets,
teams, auto-stop. **Pricing VERIFIED on the own page** (the first VERIFIED own-product
pricing page of the new-entry batch): "$20/mo plan = $20
of sandbox time", billed per second only while running, **$0.036/hour
for 4 vCPU · 8 GB RAM · 50 GB**, 100–2,000 sandboxes by plan, $20
auto-refill packs, stopping snapshots the sandbox and pauses billing.
EU-only DE/FI/FR VERIFIED in the FAQ ("Where do sandboxes run?" —
Germany, Finland, France; "Your data and snapshots stay there").
Vendor-marketing caveat: the own page carries a comparison table
(boat $0.036/h vs Freestyle $0.264/h, E2B/Daytona $0.331/h, Modal
$0.476/h, Vercel Sandbox $0.682/h) — treated as vendor marketing, not
corpus datapoints. **Open question (INFERRED, flagged for the next
pass):** the "boat" branding and the $0.036/h rate card overlap the
tracked-set provider boat.dev, whose tracked rate table also quotes
$0.036/h for its default tier — a possible rebrand/link between ASCII
and boat.dev, not folded as a claim. Competitive read (INFERRED): boat
is the sharpest direct price competitor in the corpus at this tier
(E2B's own pricing page quotes CPU-only rates per second by size —
**4 vCPU $0.000056/s = $0.2016/h**, RAM billed separately, VERIFIED on
the vendor's own page this run — already well above boat's $0.036/h
all-in for 4 vCPU · 8 GB · 50 GB; the 1-vCPU figure $0.000014/s =
$0.0504/h is not a like-for-like comparison against a 4-vCPU machine;
boat's own comparison-table figures like E2B/Daytona $0.331/h are
vendor marketing, not corpus datapoints), and its
persistent-Ubuntu-with-desktop posture overlaps
spark-vm's remote-desktop and 24-7 persistent-machine work.

**C39 update — Sai pricing confidence split refined.** sai.work's own
pages carry **no pricing at all (VERIFIED absent this run)** — no
pricing table, no figures, no pricing link; the CTA routes to
sai.simular.ai. But the $50/$500 figures move UP: they are published on
**simular.ai's own comparison pages** — Simular's own company domain,
VERIFIED this pass (Free Explore daily credits / $50/month pay-as-you-go
/ $500/month Sai Unlimited / Enterprise custom). The $20/$200/$500 tiers
stay **UNVERIFIED** — attributed to sai.work by dume.ai and TechInAsia
(THIRD-PARTY only), visible on no vendor-owned page this run. The
corpus field-table row now carries the three-way split explicitly.
Fresh press color (Sept 23, THIRD-PARTY syndication): SaiFleet at
~$0.01/hour per Sai computer, 100-computer fleet under $1/hour.

**C26 update — dropped (already folded).** DigitalOcean Managed Agents
public preview launched 2026-09-22 is already recorded VERIFIED in the
C26 deep-dive above (vendor press release, Business Wire 2026-09-22 —
paid wire = the vendor's own claims). No corpus action this pass.

**Freestyle pricing — no fold.** freestyle.sh re-read this run
(VERIFIED): still no pricing on the own site; the $50/$500
(Hobby/Pro) figures remain THIRD-PARTY. The dash.freestyle.sh
dashboard probe stays a standing ask.

Not folded: C38 Tensorlake pricing watch answered (no published pricing
page; own benchmark blog quotes $10 per 1k pages, VERIFIED) plus a
**lane-relevance flag** — Tensorlake reads as a document-ingestion API,
not agent-sandbox infra; the fold stands this pass pending a corpus
lane-review. Alibaba Cloud FC Agent Sandbox Eco/Std/Pro billing is
flagged in-lane-adjacent for the next pass (no corpus row yet). C36
terms re-verified unchanged (allowlist-only production GA). wowza.com
returned full homepage content from the runner's fetch path this run —
the interactive-browser confirmation stays owed.

## Watch update — 2026-09-24 (morning): C41 Alibaba FC billing, C40 deduped (ASCII → Boat rename resolved)

Two corpus actions this pass (primary-source-verification and
new-entry folds per the C32/C37/C38/C39/C40 precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_MORNING.md` §§1–6).

**C40 update — dedup: ASCII "boat" IS Boat; the rename is resolved.**
The predawn pass's INFERRED possible rebrand/link between ASCII's
"boat" (C40) and the tracked-set boat.dev is closed: **ASCII renamed
to Boat on ~2026-09-17.** VERIFIED this run: `box.ascii.dev`,
`boat.dev`, and `ascii.dev` serve byte-identical product pages (same
title, same $0.036/h for 4 vCPU / 8 GB / 50 GB, same plans-from-$20/mo,
same FAQ, all linking to `docs.boat.dev`); THIRD-PARTY: YC's own
company page is now `ycombinator.com/companies/boat` (YC F26; the
`ycombinator.com/companies/ascii` slug still live-resolves to the Boat page via **301 → `/companies/boat`** (VERIFIED 2026-09-24 midday — harder rename evidence than the page copy; YC is the accelerator, not the vendor);
THIRD-PARTY (yc-oss community mirror changelog, 2026-09-17):
`name`: Ascii → Boat, `slug`: ascii → boat, `website`:
box.ascii.dev → boat.dev, `former_names`: ["Ascii box","Ascii"].
Caveat: no company-published rename announcement found — the date rests
on the third-party mirror (high confidence on "same product",
medium-high on the date). **Consequence: C40 is NOT a second provider —
the C40 field-table row is renamed to the canonical Boat and collapsed
to a pointer at the tracked-set boat.dev entry, which now carries the
rename provenance.** The corpus sheds a phantom provider rather than
gaining one. Competitive read (INFERRED): Boat remains the sharpest
direct price competitor at this tier ($0.036/h all-in for 4 vCPU ·
8 GB · 50 GB vs E2B's CPU-only 4-vCPU $0.2016/h VERIFIED, RAM billed
separately).

**C41 new — Alibaba Cloud FC Agent Sandbox billing (in-lane,
task-scoped compute).** VERIFIED from aliyun-fc/fc-docs this run: new
pay-as-you-go billing rolling out from 2026-07-31 (UTC+8), still
invite-only preview — unit price × run duration, per-second billing,
hourly settlement. Three editions: **Eco** (cheapest, occasional perf
fluctuation, no hibernation — startups/tool-use validation), **Std**
(+hibernation — enterprise copilots), **Pro** (+deep and shallow
hibernation, millions of concurrent requests — RL sampling/high-concurrency
agents). International-site unit prices (USD): Eco vCPU
**0.00936**/vCPU-h, mem **0.004608**/GiB-h; Std 0.01224 / 0.006012;
Pro 0.01872 / 0.009360; disk 0.00031896/GiB-h (0.00025308 outside
mainland China); worked example — 2 vCPU / 4 GiB / 15 GiB Eco active 1h =
**$0.037152**. Hibernation math (VERIFIED): active = vCPU+mem+disk (15 GiB
disk free); light hibernation (Pro only) = mem+disk, vCPU free; deep
hibernation = vCPU+mem free, disk billed on (memory×2 + disk) GiB with no
free allowance; FAQ: "call `kill()` when the task is complete." **Scope
caveat (VERIFIED):** applies ONLY to E2B-SDK integration — existing E2B
instances auto-upgrade to Pro; "Sandbox Functions"/"AgentRun Sandbox"
customers must migrate. Lane characterization (INFERRED): task-scoped
compute, **not** agent-VM-shaped — no SSH or Desktop surface in the
Features index; closer to E2B/Daytona pause semantics than to a persistent
dev VM. A hyperscaler pricing datapoint (~$0.037/h for a 2vCPU/4GiB box
at Eco rates), not a shape competitor.

**wowza.com owed re-verification — closed.** Homepage loads cleanly this
run (full content, no resets). The host-level link-check exclusion stays
per the in-file rule (runner-egress path condition, not site health);
the interactive-browser confirmation stands as a standing nuance. No
corpus action.

Not folded: news scan found no new in-lane sandbox-infra items for
9/23–24 (adjacent funding color only: Ema $77M Series B, Chamelio $26M
Series A, Snorkel AI $350M at $3.5B — THIRD-PARTY, snippet-only). C36
terms re-verified unchanged (allowlist-only production GA). Vercel
Drives still public beta (20th consecutive no-change pass).

## Watch update — 2026-09-24 (late midday): C42 Namespace Devboxes, Upstash own-docs verification, Ascii candidate retired

Five corpus actions this pass (vetting-driven folds per the
C32/C37/C38/C39/C40 precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_LATE_MIDDAY.md` §§1–5).

**C42 new — Namespace Devboxes (adjacent → in-lane, VERIFIED).**
The midnight pass vetted Namespace as *adjacent* ("dev-compute, not
VM-for-agents-first"); the vendor's own docs contradict that:
[Devboxes for Coding Agents](https://namespace.so/docs/devbox/agents)
(read 2026-09-24) — *"A coding agent needs a machine where it can
clone a repository, install dependencies, run commands, and return the
result. Devboxes provide Linux and macOS machines"* — ephemeral
Devboxes, Pool API (`devbox acquire`), `devbox exec`/`logs`/`upload`,
`network_policy.egress_domains` egress filtering, secrets via the
Namespace vault, and native integrations where **Claude Managed
Agents, Cursor Cloud Agents, and Devin all run on Namespace
Devboxes**. An agent-execution surface on the vendor's own docs is
in-lane, not adjacent: filed as **C42** with a field-table row.
Sizes S→XL (burst 4 vCPU/8 GB → 32 vCPU/64 GB) at the THIRD-PARTY
snippet layer; no published pricing in the surveyed docs.

**Upstash Box — own-docs VERIFIED (row update).** Already a corpus
row (2026-09-22 consolidation, C31 mechanics datapoint); this pass
upgrades it from vendor-docs-not-read to VERIFIED on the
[Box quickstart](https://upstash.com/docs/box/overall/quickstart):
*"Upstash Box lets you give your AI agents a computer. Every Upstash
Box is a **secure, isolated cloud container with an AI Agent built
in**"* — filesystem, shell, git, runtime (Debian default); keep-alive
boxes stay on between sessions; SSH with a Box API key; *"Freeze a
box anytime, and continue days or even weeks later with perfect
resumability."* Pricing THIRD-PARTY (vendor's own comparison blog,
snippet-only this run): $0.10/$0.20/$0.40 per active CPU-hour
(small/medium/large); free tier 10 boxes, 5 CPU-h/mo, $1 LLM budget,
no card required. Lane cell widened to task-scoped sandbox /
persistent computer (freeze/resume + keep-alive semantics).

**Ascii Box vetting — RESOLVED to Boat; unvetted candidate retired.**
The midnight pass left "Ascii Box" as an in-lane candidate needing
own-site verification; the morning pass resolved C40 (ASCII is Boat).
This pass adds the hardest rename evidence yet, VERIFIED on the
vendor's own developer surface:
[docs.ascii.dev/box/api/v1](https://docs.ascii.dev/box/api/v1)
renders as **"Boat Public API v1"** — the legacy ASCII domain's
official API docs brand the product *Boat*. The `/box` path and the
box.ascii.dev endpoints persist; the documented API covers sandbox
lifecycle (provisioning → ready/idle → running → archiving →
archived; stop/archive, resume, fork, delete; desktop streaming;
Idempotency-Key; per-sandbox API keys; data-retention API) and a
`prompt` endpoint running work through built-in agent harnesses named
`codex`, `claude-code`, `pi`, `opencode`, `prime-agent`, `kimi`
(INFERRED read: Boat bundles coding-agent harnesses as first-class
providers — a sharper competitive shape than sandbox-hosting alone).
Folded into the tracked-set Boat row's rename narrative and the C40
provenance note; the standalone "Ascii Box" newcomer candidate is
retired as vetted (it was Boat all along). **Beam** remains the only
unvetted adjacent candidate from the midnight list.

**Vercel Sandbox feature churn — snippet-only, no fold.** An
aggregator of vercel/sandbox releases (releasebot.io, snippet-only)
lists Sep 23–24 entries: Secure Compute network attach
(`--network-id` / SDK `networkId`), binary-unit size labels, fork
now warns when the source is running, API requests tagged with the
detected driving agent (`agent/<name>` user-agent via detect-agent).
Feature churn, no pricing move, no GA — no fold. (Secure Compute
networks were already THIRD-PARTY color from the 2026-09-23
overnight pass.)

Not folded: news scan found no new in-lane sandbox-infra items for
2026-09-24 (in-lane verdict quiet: no launches, pricing moves, GA
moves, or funding). Dropped as out-of-lane/out-of-window: Cursor
Rollouts + Claude Code Projects GA (agent products), Alibaba
AgentCore at Apsara (managed agent platform), Huawei Ascend agent
stack (hardware), Crusoe $3.9B Series F (GPU-cloud exclusion),
Modal $355M (out of window), OpenAI Agents API "opened to all
developers" digest claim (THIRD-PARTY digest only, and an LLM/agent
platform surface — out-of-lane). C36 terms re-verified unchanged
(allowlist-only production GA). C41 billing re-verified unchanged.
Vercel Drives still public beta (22nd consecutive no-change pass —
one THIRD-PARTY snippet calls it "private beta on Pro and
Enterprise plans"; the vendor's own changelog, VERIFIED this run,
says public beta, so the verdict stands with the snippet recorded as
availability color). The deprecated-row sunset convention stays
proposed-not-codified (C40, ~3–4 passes into the proposed 14-pass
retention — no removal either way).

## Watch update — 2026-09-24 (afternoon): C43 Google Gemini Agent Environment, Daytona changelog move

New-entry fold per the C32/C37/C38/C39/C40/C41/C42 precedents; full
pass record in `docs/COMPETITOR_WATCH_2026-09-24_AFTERNOON.md`.

**C43 new — Google Gemini Agent Environment (in-lane, VERIFIED).**
Google's own Gemini API docs
([ai.google.dev/gemini-api/docs/agent-environment](https://ai.google.dev/gemini-api/docs/agent-environment),
read 2026-09-24): *"Environments are managed Linux sandboxes that give
agents an isolated place to execute code and persist files"* —
reusable via `environment_id`; sources (git repo mount); network
allowlists; env vars / credential references; pre-installed Ubuntu
toolchains; current examples use agent string
`antigravity-preview-09-2026`. Sept-17 detail at the THIRD-PARTY
layer: Files API (persistent file upload/list/download); Credentials
API (secrets injected as env vars/MCP headers, model never sees the
raw secret — a sixth convergent placeholder-swap datapoint, noted
for the secrets turns); vendor-claimed ~40% fewer output tokens on
file edits, +8% task completion; preview compute not billed. Sibling
of Agent Substrate (C36): C36 is the GKE-side surface; C43 is the
Gemini-API-side managed sandbox. Filed as **C43** with a field-table
row.

**Daytona tracked-set move — SEP 24 changelog entries, no field-table
change.** V0.216.1 + V0.216.2 (VERIFIED on daytona.io/changelog): CLI
login through WorkOS; API-key organization context; outdated-version
warning fix. CLI/API polish — no pricing move, no sandbox-feature
move. The field table carries Daytona's positioning/pricing, not its
changelog, so no row update per the fold convention. This ends the
eleven-pass full-quiet 8/8 tracked-set streak (this pass: 7/8
VERIFIED NO-CHANGE).

**OpenAI Agents API — availability verdict upgraded to VENDOR-VERIFIED (sourcing only; no GA move).**
2026-09-24 noon pass: the public-beta dating is now confirmed on
OpenAI's own changelog ([developers.openai.com/api/docs/changelog](https://developers.openai.com/api/docs/changelog),
read 2026-09-24): *"Sep 10 — Feature — Released the Agents API in public
beta"* (managed Codex harness; run agents in OpenAI-hosted sandboxes or
connect your own). Still public beta — **no GA move.** It remains an
LLM/agent platform surface (out-of-lane) and not new in-window: watch
color only. Supersedes the midday pass's THIRD-PARTY dating verdict.

**Tencent Cloud DataBuddy (Sept 22 launch) — adjacent watch color;
lane tension recorded, not resolved.** PRNewswire syndication mirrors
(vendor press release not fetched on tencentcloud.com): agent-native
Data + AI workbench after CodeBuddy/WorkBuddy, built on an "Agent
Runtime layer" (governance, auditability, data controls); China /
Thailand / South Korea / Indonesia, EU/NA/SA rollouts ongoing. The
midnight pass recorded DataBuddy as adjacent; this pass's surveyor
characterized it as in-lane. The vendor's own page was not read —
kept as adjacent watch color, tension recorded here rather than the
lane being unilaterally recoded.

Adjacent color, no fold: Alibaba Cloud's agentic-cloud strategy +
AgentCore (Sept 22, Hangzhou Cloud Summit; THIRD-PARTY — managed
agent platform) and GitHub Copilot app opt-in local sandboxing in
public preview (Sept 23, snippet-only — agent product, out-of-lane).
Dropped as stale/out-of-window: Daytona's 2024 PRNewswire
recirculation; Boxd $2M (C29, closed 9/21); Alibaba FC snapshot
billing (Aug 25); Cursor Rollouts + Security Reviewer (Sept 24, agent
product); Darktrace Signal Labs (Sept 24); Zoho Catalyst agentic PaaS
(Sept 24); Modal $355M (2026-05-21).

C36 re-verified unchanged (allowlist-only production GA terms
verbatim). C41 billing re-verified unchanged (HEAD `39b6c3a`). Vercel
Drives still public beta (23rd consecutive no-change pass; pricing
page `last_updated` 2026-09-10). The deprecated-row sunset convention
stays proposed-not-codified (C40, ~4–5 passes into the proposed
14-pass retention — no removal either way).

## Watch update — 2026-09-24 (late evening): C44 Google Gemini Enterprise sandboxes GA, P49 cadence decision

New-entry fold per the C32/C37/C38/C39/C40/C41/C42/C43 precedents; full
pass record in `docs/COMPETITOR_WATCH_2026-09-24_LATE_EVENING.md` (survey
window ~10:56–11:20 CDT).

**C44 new — Google Gemini Enterprise Agent Platform sandboxes
(Computer Use + Shell), GA, VENDOR-VERIFIED, in-lane.** Google's own
release notes
([docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes),
read 2026-09-24), under "September 09, 2026": *"Computer Use and Shell
sandboxes in Gemini Enterprise Agent Platform are now generally
available (GA)."* Shell sandboxes run untrusted shell commands, install
packages, and manipulate files in an isolated Linux container via direct
`/exec` API calls; the same release ships VPC Service Controls &
Private Service Connect, CMEK (Cloud KMS, disk + snapshot checkpoints),
and **pause/resume for sandboxes** — deschedule compute for idle
sandboxes while preserving filesystem state and connection identity,
resume in seconds. The idle-suspend datapoint is filed at the vendor
layer: convergent with C36 Agent Substrate's zero-idle posture and DO's
305 ms resume claim (C26), and with the idle-economics read Google
itself applies to Filestore agent volumes (C36 pricing color). Filed as
**C44** with a field-table row. The GA is pre-window (Sept 9) — reach-back
per the #82 pattern, an explicit queued candidate verified on a primary
source. This is a third Google agent-sandbox surface alongside C36
(GKE-side open-source runtime) and C43 (Gemini-API-side Environments);
the three-surface Google picture now reads as: open-source runtime (C36),
Gemini API surface (C43), enterprise platform with GA sandboxes (C44).

**Evening-pass queue resolved:** the Docker Sandboxes CVEs
CVE-2026-77179 / CVE-2026-79994 are the SAME pair the 2026-09-23 ~11:54
pass closed (numbers, severities, fix 0.42.0 Sep 7, dates all match —
VERIFIED on Docker's own security-announcements page this pass) — no
fold, no new C-number; the corpus already records that the notes name
both CVEs (2026-09-19 evening amendment), so no correction was owed.
The Alibaba "Agent Native Cloud" + Huawei "Open Agentic Cloud"
two-vendor framing trend stays queued and adjacent: Huawei is
VENDOR-VERIFIED on huawei.com (Sept 18 keynote, "open agentic cloud"
commitment), Alibaba remains THIRD-PARTY (Apsara Conference syndication
only) — both are managed-agent-platform framings, neither announces
sandbox execution infra.

**P49 decision (long-quiet carried-ask cadence) — decided this turn:**
the Vercel Drives GA watch (25th consecutive no-change pass, still
public beta, pricing `last_updated` 2026-09-10) moves to **once-daily**
(checked in the morning pass), effective immediately. Tracked-set
re-reads and carried C-item re-verifications stay hourly. Rationale: a
quarterly-cadence vendor lifecycle event re-read hourly is ritual; the
hourly pass keeps its high-signal core. This pass's novel yield (one
corpus move — C44) keeps the F64 advisory untriggered.

**Watch-review nit adoptions (20:54 turn's deferred nits, this pass's
convenience):** (a) checked — every C36 claim in shipped docs already
carries a convention label, no unlabeled sentences found; (b) adopted —
the 2026-09-23 late-night README watch-table row's Upstash Box
"future-vetting candidate" cross-references that it is already filed as
C31; (c) already adopted (YC 301 cited in both Boat rows); (d)
adopted — EU-only DE/FI/FR geography folded from the deprecated C40
pointer row into the tracked-set Boat row's pricing cell; (e)
deliberately NOT adopted — codifying the deprecated-row sunset
convention would be a unilateral rule adoption, it stays
proposed-not-codified pending corpus-owner approval; (f) adopted —
the C40 rename section's YC-slug parenthetical now notes the slug
still live-resolves to the Boat page via 301 (VERIFIED midday).

## Watch update — 2026-09-24 (early afternoon): C45 Docker Cloud Sandboxes, Microsandbox v0.7.2/v0.7.3

New-entry fold per the C32/C37/C38/C39/C40/C41/C42/C43/C44 precedents; full
pass record in `docs/COMPETITOR_WATCH_2026-09-24_EARLY_AFTERNOON.md` (survey
window ~12:56–13:08 CDT).

**C45 new — Docker Cloud Sandboxes, in-lane, VENDOR-VERIFIED.** Docker's own
blog
([docker.com/blog/introducing-cloud-sandboxes-start-on-your-laptop-finish-in-the-cloud](https://www.docker.com/blog/introducing-cloud-sandboxes-start-on-your-laptop-finish-in-the-cloud),
read in full 2026-09-24 — survey-window snippets first, full read in the repair turn): *"Today, we're introducing Cloud Sandboxes: the
same microVM-based sandbox, running on Docker-managed compute, with one
command to move between them."* The isolation model is identical to local
Docker Sandboxes (own kernel, own Docker daemon); the substrate changes.
`sbx move <name> --to cloud` migrates the filesystem bidirectionally; up to
24-hour sessions; kits for Claude Code, Codex, Copilot, Antigravity, Open
Code, Hermes; MCP gateway; per-agent network policies; and **secrets
proxy-injected per request** (agents never see the actual secret — the
**seventh convergent placeholder-swap datapoint** for the secrets turns,
after Daytona, Microsandbox, opencomputer.dev, h-sandbox, DigitalOcean
Managed Agents (C26), and the C43 Credentials API). Pricing is PAYG per-second:
Micro 1 vCPU/2 GiB $0.07/h, Small (default) 2/4 $0.14/h, Medium 4/8
$0.28/h, Large 8/16 $0.56/h, XL 16/32 $1.12/h; *"A paused sandbox costs
nothing"*; volumes, egress, and hosting public images/kits free;
sessions 1h default, up to 24h; limited-time $250 free credit for new
accounts. Sign-up: web console (agentic-platform.docker.com) or
`sbx --cloud run`, sbx ≥ 0.45.1, PAYG plan on Personal/Pro accounts;
local Sandboxes stay free and standalone. Dating caveat: Docker's page
shows no publish date in the fetched text (screenshots 2026-09-23);
surfaced 2026-09-24 via a GlobeNewswire wire dated that day — filed as a
2026-09-24 move with the caveat stated. (The wire names the launch venue
as *WeAreDevelopers North America* — THIRD-PARTY color, folded
2026-09-24 mid-afternoon.) Filed as **C45** with a
field-table row. Read for spark-vm: Docker closed its local-only gap, and
its framing — *"how much you can trust your agent shouldn't depend on
where it happens to be running"* ("one strong isolation model, two
surfaces") — is the direct inverse of spark-vm's pitch (one persistent
computer, mine everywhere). The pricing datum is the load-bearing one:
**$0.07/CPU-hour lands exactly on Fly Sprites' and AgentComputer's
$0.07/CPU-hour** — three vendors now share the entry price point.
spark-vm's self-hosted story still wins on cost-at-idle; the hosted
product's edge has to be continuity + MCP/secret plumbing, where Docker's
kit/secrets-proxy story is converging from above.

**Tracked-set move (not a fold):** Microsandbox releases now top out
v0.7.3 ("chore: release v0.7.3 by @toksdotdev in #1646"), with v0.7.2 and
v0.7.3 new beyond the v0.7.1 baseline — the full-quiet streak ends at
three (7/8 VERIFIED NO-CHANGE otherwise). The corpus field-table row pins
no version, so no row change; release titles were not verified this run,
recorded as a tracked-set move.

**Carried asks:** C36, C41, C43, C44 all re-verified unchanged
(VENDOR-VERIFIED on vendors' own pages). OpenAI Agents API stays public
beta — no GA (changelog's latest entry Sep 22; Sep 10 public-beta entry
unchanged; vendor-issued GA not found). Boat EU-only DE/FI/FR geography
datapoint not re-located for the third consecutive pass (targeted
searches + docs-home scan, no FAQ found) — carried per the retry rule;
the midday verbatim fold stands. **C41 awareness flag (fold candidate,
not folded):** the Alibaba pay-as-you-go page now documents Snapshot
pricing ("Snapshot Storage Usage = Memory Specification × 2 + Disk
Specification") — seen only as a section note, queued for a full re-read
next pass. Vercel Drives GA watch out of scope (P49: once-daily, morning
pass). Deprecated-row sunset convention stays proposed-not-codified.
Agentic-cloud framing stays queued-adjacent (Huawei VENDOR-VERIFIED
unchanged; Alibaba THIRD-PARTY); Tencent DataBuddy stays adjacent-watch
(its trial portal could not be fetched this run — UNVERIFIED).

**Watch-review nit adoptions:** none pending. This pass's novel yield
(one corpus move — C45 — plus one tracked-set move) keeps the F64
advisory untriggered.

## Watch update — 2026-09-24 (mid afternoon): C41 Snapshot pricing, C45 garnish, asks resolved

New-entry and correction fold per the C32/C37/C38/C39/C40/C41/C42/C43/C44
precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_MID_AFTERNOON.md` (survey window
~14:56–15:15 CDT).

**C41 — Snapshot pricing fully specified (VERIFIED).** The early-afternoon
pass's awareness flag is resolved: the Alibaba pay-as-you-go page's
Snapshot section reads *"Snapshot Storage Usage = Memory Specification ×
2 + Disk Specification"*, charged at the Disk Unit Price × storage
duration. Folded into the C41 field-table row above. C41 otherwise
re-verified unchanged value-for-value (pinned HEAD `39b6c3a`).

**C45 — WeAreDevelopers-venue garnish (THIRD-PARTY).** The GlobeNewswire
wire that dated the Docker Cloud Sandboxes launch names the launch venue
as *WeAreDevelopers North America*. Folded as a one-line caveat in the
early-afternoon C45 section; no row change.

**Resolved asks:** Boat EU-only DE/FI/FR geography re-VERIFIED verbatim
on boat.dev's own FAQ (*"In the EU: Germany, Finland, and France. Your
data and snapshots stay there."*) — the three-pass carried retry is
closed; the midday fold stands. OpenAI Agents API Sep-10 public-beta
dating re-confirmed VENDOR-VERIFIED with a fresh read of OpenAI's own
changelog this run (the noon pass's upgrade already stood) — still
public beta, no GA move.

**Tracked set:** 7/8 VERIFIED NO-CHANGE (Daytona, Docker Sandboxes,
Microsandbox v0.7.3, E2B, boat.dev, TermSquad, AgentComputer); one
UNVERIFIED — DigitalOcean Managed Agents pricing docs could not be
fetched this pass, so no no-change claim is made on it. The **"Last
verified 22 Sep 2026"** stamp re-check is owed to the next pass.

**Watch-doc naming convention:** admits `_MID_AFTERNOON` (2026-09-23
precedent; the 09:54 pass had already taken `_AFTERNOON` and the
early-afternoon pass `_EARLY_AFTERNOON`).

C36, C43, C44 all re-verified unchanged; C45 shows no new moves since
the fold. No in-lane launches, pricing moves, or funding dated 9/24.

## Watch update — 2026-09-24 (late afternoon): full-quiet pass, one C41 garnish, DO stamp still owed

Garnish fold per the C32/C37/C38/C39/C40/C41/C42/C43/C44/C45
precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_LATE_AFTERNOON.md` (survey window
~15:56–16:20 CDT).

**C41 — deep-hibernation garnish (VERIFIED).** The vendor page
specifies the 15 GiB free disk allowance does not apply in deep
hibernation. Folded as a one-line caveat in the C41 field-table row
above; C41 otherwise re-verified unchanged value-for-value (pinned
HEAD `39b6c3a`).

**Tracked set:** 7/8 VERIFIED NO-CHANGE (Daytona, Docker Sandboxes,
Microsandbox v0.7.3, E2B, boat.dev, TermSquad, AgentComputer); one
UNVERIFIED — DigitalOcean Managed Agents: the owed "Last verified 22
Sep 2026" pricing-stamp re-check did not close. The vendor product
doc fetched this run (resolving the mid-afternoon fetch failure) and
carries DO's own *"Last verified 21 Sep 2026"* freshness line, but it
carries no pricing, and the vendor pricing subpage fetch failed again.
No no-change is claimed; the stamp re-check is owed to the next
pass.

**Carried asks:** C36, C43, C44 all re-verified unchanged; OpenAI
Agents API Sep-10 public-beta dating re-confirmed VENDOR-VERIFIED on
OpenAI's own changelog (still public beta — GA VERIFIED absent); C45
Docker Cloud Sandboxes no new moves since the fold; Vercel Drives
still public beta (opportunistic re-read — the P49 once-daily morning
cadence stands); "agentic cloud" framing stays queued (adjacent);
Tencent DataBuddy stays adjacent-watch; deprecated-row sunset
convention still proposed-not-codified.

**Watch-doc naming:** `_LATE_AFTERNOON` carries the 2026-09-23
precedent — no convention admission needed.

No in-lane launches, pricing moves, or funding dated 9/24.

## Watch update — 2026-09-24 (mid evening): C45 GA-venue garnish, C26 pricing re-verified, stamp still carried

Garnish fold per the C32/C37/C38/C39/C40/C41/C42/C43/C44/C45
precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_MID_EVENING.md` (survey window
~17:00–17:12 CDT).

**C45 — GA-venue garnish (THIRD-PARTY venue + VENDOR-VERIFIED keynote
blog).** The onstage announcement at WeAreDevelopers North America
(Docker president Mark Cavage, GlobeNewswire wire 12:00 PM EDT;
The Register / ADTmag same-day coverage) anchors the early-afternoon
C45 fold as a launch event, not just a blog introduction. New vendor
facts from Docker's own keynote blog (VENDOR-VERIFIED): *"Docker Cloud
Sandboxes are available today with pay-as-you-go pricing"*; next-gen
Sandbox Kits are now standard OCI images; Docker committed to
submitting the Kits specification to the CNCF; Nous Research demoed
Hermes running as a first-class Kit onstage. Pricing corroboration
(The Register, THIRD-PARTY: Micro 1 vCPU/2 GB $0.07/hr → XL 16/32
$1.12/hr) matches the filed table value-for-value — no row change to
the pricing cells. Folded as a garnish in the C45 field-table row
above. Read for spark-vm: Docker is now marketing the cloud tier
through the developer-conference channel with the framing that *trust
in your agent shouldn't depend on where it runs* — the in-lane bar for
a hosted sandbox announcement just got set higher.

**C26 — pricing re-verified, stamp still carried.** The carried ask
(vendor pricing-page fetch, failed twice) closed via the vendor's own
Sept 22 press release (Business Wire — paid wire, the vendor's own
claims): $0.044/vCPU-hour active CPU (per-second), $0.0095/GB-hour
memory, $5 new-user credit — all matching C26's closed pricing
exactly; public preview opened Sept 22, 2026 (private preview before),
still preview not GA. The $0.05/GiB-month docs snapshot figure stands
against the release's own $0.005/GiB-month — a live 10x docs-vs-release
discrepancy, resolved neither way this run; the carried pricing-subpage
re-fetch must settle it. The pricing subpage's "Last
verified 22 Sep 2026" stamp re-check stays carried one more pass —
the THIRD-PARTY subagentic.ai "September 21, 2026" claim is not a
contradiction (it matches the late-afternoon pass's own read on the
vendor's *product doc*, which carries no pricing; the 22 Sep stamp
belongs to the pricing subpage). C26 otherwise unchanged.

**Tracked set:** 7/8 VERIFIED NO-CHANGE (Daytona, Docker Sandboxes
release-notes page, Microsandbox v0.7.3, E2B, boat.dev pricing,
TermSquad, AgentComputer); DigitalOcean pricing re-verified on the
vendor release (product doc not re-fetched); boat.dev product-news
surface UNVERIFIED (not located this run). The quiet streak continues —
no pricing or feature deltas anywhere in the window.

**Carried asks:** C36, C41, C43, C44 — no new moves (last re-verified
late-afternoon ~16:20 CDT; nothing in the news scan touches them);
OpenAI Agents API Sep-10 public-beta dating re-confirmed VENDOR-VERIFIED
(still public beta — GA VERIFIED absent); Vercel Drives not re-checked
(the P49 once-daily morning cadence stands).

**In-lane dated 2026-09-24:** the Docker Cloud Sandboxes GA-venue
announcement (above); Island $400M at $6.4B (rogue-AI-agent browser
defense — adjacent lane); Modal Labs in ~$15B raise talks (adjacent
lane, reported 2026-09-23); Darktrace Signal Labs launch (agentic-AI
security research — adjacent lane). No in-lane sandbox pricing moves
or new sandbox launches beyond the Docker GA venue.

**Watch-doc naming:** `_MID_EVENING` carries the 2026-09-23 precedent
— no convention admission needed.

## Watch update — 2026-09-24 (night): C46 Tensorlake, C26 confirmed live, C39 resolved, C37 own-priced

Garnish fold per the C32/C37/C38/C39/C40/C41/C42/C43/C44/C45
precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_NIGHT.md` (survey window
~18:55–19:15 CDT).

**C46 new — Tensorlake pricing page (in-lane, VENDOR-VERIFIED).**
tensorlake.ai/pricing ("UPDATED Q3 2026", VERIFIED own-page) prices
Tensorlake's **Firecracker-microVM sandbox product** — a direct
E2B/spark-vm-class competitor ("Every tier runs on the same Firecracker
microVMs"), not the document-OCR line (the $0.01/page figure stays
THIRD-PARTY via saasworthy/slashdot). Tiers: Free ($0 forever, 1
sandbox, 2hr sessions); Usage Credits ($5–$20 prepaid packs, $0.01/CU);
Pro $250/billing cycle (25,000 CU included); Enterprise (custom).
Metered: Active CPU $0.07/core-hr (credits) / $0.042 (Pro); RAM
$0.015/GB-hr / $0.009; Disk $0.0002/GB-hr / $0.0001; **snapshot storage
$0.07/GB-month (both tiers — the richest snapshot line in the
corpus)**; egress free. SOC 2 Type 2 on every tier, HIPAA on Pro+.
Filed as **C46** (the C38 entry keeps its document-ingestion history;
the row carries both numbers). Read for spark-vm: Tensorlake's public
posture has shifted from document-AI to sandbox-provider with
published active-CPU metering — its metered CPU ($0.042–0.07) lands at
the E2B/Daytona/Fly-Sprites cluster, and its snapshot rate is the new
corpus ceiling to benchmark our own tier thinking against (cf. C26's
live 10x dispute and C41's snapshot-storage formula).

**C26 — snapshot discrepancy CONFIRMED LIVE, carried open.** The
mid-evening fold's carried re-fetch closed tonight on *both* vendor
surfaces, read live: the docs pricing subpage
(`docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/`,
**"Last verified 22 Sep 2026"**) prints **$0.05/GiB-month**; DO's own
Sept 22 press release (investor-relations site; identical text on
BusinessWire/Morningstar/forkast) prints **$0.005/GiB-month**. Neither
surface has corrected. This formally supersedes the older corpus
stance ("the 10x discrepancy resolved in favor of the primary
source"): the conflict is live on two current vendor surfaces, both
carrying the vendor's own voice. Internal-consistency read (INFERRED):
$0.05 matches the same page's session-storage/BYOT rates and DO's
longstanding droplet-snapshot rate — the docs figure reads as
platform-normal, the release's $0.005 as the outlier (likely typo).
Kept carried open; the C26 field-table row now prints both figures.
Read for spark-vm: a live case study in why pricing claims get
primary-source re-verified — this is the exact rate a competitor would
copy without checking.

**C39 — pricing RESOLVED.** sai.work/pricing exists and loads (structure
VERIFIED on sai.work: Free daily-credit tier, paid tier with 50,000
credits/month ($50 of usage), Unlimited always-on tier, Enterprise);
exact numerals from Simular's own-domain comparison pages (VERIFIED):
**Free (Explore, daily credits) | $50/mo (Pay as you go) | $500/mo
(Sai Unlimited) | Enterprise (custom)**. dume.ai's $20/$200/$500 =
stale private-beta pricing (THIRD-PARTY, superseded per the June 2026
TechInAsia private-beta figures). The row's "conflict unresolved"
qualifier is retired.

**C37 — own pricing page VERIFIED.** freestyle.sh/pricing (VERIFIED
own-page): vCPU $0.04032/h (200/h included monthly), GiB Memory
$0.0129/h (400/mo), GiB Storage $0.000086/h (60,000/mo), Data Transfer
$0.02/GB (50 GB free / 500 GB paid); Free / **Hobby $50/mo** (FAQ:
"$50 on Hobby covers your first $50 of usage") / Pro (+ Enterprise
custom). Carried sub-item: Pro's exact monthly fee is not printed on
the page (only "monthly fee is a commitment that doubles as usage
credit") — the everydev.ai $49/$499 claim now reads as ~Hobby's own
$50 with Pro's $499 unconfirmed; dashboard-signed-in check owed. The
row's "own pricing page not read — UNVERIFIED" qualifier is retired.

**Tracked set:** 8/8 VERIFIED NO-CHANGE (Daytona, Docker Sandboxes
release-notes page, Microsandbox v0.7.3, E2B, boat.dev pricing,
TermSquad, AgentComputer, DigitalOcean Managed Agents news). The quiet
streak resumes after the mid-evening pass. TermSquad pricing re-read
verbatim matches the 9/18 baseline (Starter/Builder/Power/Ultra
$9/$19/$29/$49 — the mid-evening shorthand dropped the Builder tier, a
reporting nuance, not a delta). boat.dev product-news surface not
located a second time (UNVERIFIED on that sub-item only); OpenAI Agents
API GA check and Vercel Drives (P49 morning cadence) carried; wowza.com
link re-verified live 200 (the previously flagged bot-reset did not
reproduce).

**In-lane dated 2026-09-24:** the C45 Docker Cloud Sandboxes GA venue
only (The Register's Sept 24 coverage corroborates Docker's own blog
pricing value-for-value: $0.07 Micro → $1.12 XL/hr, per-second, paused
free, $250 credit; adds CLI color — `brew install docker/tap/sbx`,
`sbx --cloud run claude`, sbx ≥ 0.45.1, Docker Personal/Pro). No new
in-lane sandbox launches, pricing moves, or funding dated 9/24.

**Carried to the next pass:** Freestyle Pro's exact own-page fee
(dashboard-signed-in check); C26 continued monitoring; OpenAI Agents
API GA check; boat.dev product-news surface (UNVERIFIED ×2).

**Watch-doc naming:** `_NIGHT` carries the 2026-09-23 precedent — the
crowded `_EVENING`/`_LATE_EVENING`/`_MID_EVENING` namespace is left
untouched.

## Watch update — 2026-09-24 (late night): C45 Register corroboration, C26 docs side unlocatable, boat.dev product-news VERIFIED absent

Garnish fold per the C32/C37/C38/C39/C40/C41/C42/C43/C44/C45
precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_LATE_NIGHT.md` (survey window
~20:00–20:20 CDT).

**C45 — Register corroboration garnish (THIRD-PARTY, dated).** The
Register published dated 2026-09-24 coverage of the Docker Cloud
Sandboxes launch (THIRD-PARTY): hosted microVM sandboxes announced at
the WeAreDevelopers Conference, billed by the second, **Micro
(1 vCPU/2 GB) $0.07/hr → XL (16 vCPU/32 GB) $1.12/hr** — matching
Docker's own blog figures value-for-value — plus the Kits spec
becoming standard OCI images. This is dated-press corroboration of
the existing VENDOR-VERIFIED GA-venue garnish, not new claims; the
C45 field-table row carries the corroboration line. Read for
spark-vm: the pricing ladder's endpoints (Micro/XL) are now named
with shapes in press — a useful reference point when we spec our own
sandbox size tiers.

**C26 — press-release side re-VERIFIED, docs side UNVERIFIED, carried
open.** The press-release surface (DO's own Sept 22 release) re-read
VERIFIED this run at **$0.005/GiB-month**. The docs pricing subpage
("Last verified 22 Sep 2026", $0.05/GiB-month) could not be located
this run (3 searches + the Harness Runtime docs page, which carries no
price numbers). The 10x discrepancy is therefore not re-observable
this run — the docs side may have been corrected or the page moved.
No reconciliation attempted; the C26 field-table row carries the
partial re-read note and the discrepancy stays carried open. Next
pass: re-locate the docs pricing surface before re-asserting the
conflict. Read for spark-vm: a pricing URL that vanishes undercuts
any claim built on it — this is why the corpus re-verifies
primary-source URLs each pass rather than caching them.

**boat.dev product-news ask — VERIFIED absent, retry retired.**
Three attempts in, the verdict is firm: the vendor has no
product-news surface on its public site (docs nav carries no
blog/changelog section; homepage has no blog links; `site:` queries
empty). Status moves UNVERIFIED ×2 → VERIFIED absent, and the carried
retry ask is retired — future passes need not re-probe. Recording
this as VERIFIED absent rather than a stale UNVERIFIED matters: a
perpetual UNVERIFIED asks future passes to keep spending surveyor
time on a surface that does not exist.

**Tracked set:** 7/8 VERIFIED NO-CHANGE (Docker Sandboxes
release-notes page, Microsandbox v0.7.3, E2B, boat.dev pricing,
TermSquad, AgentComputer, DigitalOcean Managed Agents news); one
micro-delta — Daytona's changelog now leads with V0.216.1 above
V0.216.2 (both dated SEP 24 2026; no V0.216.3; content of both entries
unchanged from the afternoon fold; no pricing/feature move). C36,
C41, C43, C44 all re-verified unchanged. OpenAI Agents API still
public beta (THIRD-PARTY sources corroborate the VENDOR-VERIFIED
Sep-10 dating). Tensorlake (C46) VERIFIED NO-CHANGE.

**Adjacent color:** beri.net's ~Sept 23 Baseten/Blaxel continuity
analysis (THIRD-PARTY) carries a Sept-24-dated pricing comparison
(~$0.17/hr for 2 vCPU/4 GB across Blaxel/E2B/Daytona); the underlying
acquisition is dated Sept 10 (not new — stays adjacent). No corpus
fold — analysis, not a vendor move.

**In-lane dated 2026-09-24:** the C45 Register coverage above only.
No in-lane launches, pricing moves, or funding beyond it.

**Carried to the next pass:** Freestyle Pro's exact own-page fee
(dashboard-signed-in check); C26 continued monitoring (re-locate the
docs pricing surface first); OpenAI Agents API GA check; Vercel Drives
(P49 morning cadence).

**Watch-doc naming:** `_LATE_NIGHT` admitted per the convention's
"already-taken slot" rule — today's night pass (#373, ~19:21 CDT) had already taken
`_NIGHT`, following the 2026-09-23 `_LATE_NIGHT` precedent (delta-only against `_EARLY_NIGHT`); the crowded
`_EVENING`/`_LATE_EVENING`/`_MID_EVENING` namespace is left untouched.

## Watch update — 2026-09-24 (pre midnight): C45 availability VENDOR-VERIFIED, BAND kit signal, C26 second miss + misattribution hypothesis

Garnish fold per the C32/C37/C38/C39/C40/C41/C42/C43/C44/C45
precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_PRE_MIDNIGHT.md` (survey window
~20:54–21:05 CDT).

**C45 — launch availability VENDOR-VERIFIED (upgrade).** Docker's own
Sept-24 posts (the introducing-cloud-sandboxes blog and the
manufacturing-trust keynote blog, both read this run) confirm: same
microVM isolation as local Docker Sandboxes on Docker-managed compute,
one-command laptop↔cloud move, 1–16 vCPUs, pay-as-you-go, "available
today"; Sandbox Kits are now standard OCI images ("Kits make authority
reproducible"). The C45 launch-availability claim moves THIRD-PARTY
(Register corroboration, late-night fold) → VENDOR-VERIFIED — the
mid-evening fold had already VENDOR-VERIFIED the manufacturing-trust
keynote blog; this pass's delta is the introducing-cloud-sandboxes
post. The C45 field-table row carries the upgrade.

**C45 — BAND Python Kit partnership (THIRD-PARTY, dated).** BAND
announced the "BAND Python Kit for Docker Sandboxes" on Sept 24, 2026
(PR Newswire dateline) — multi-agent collaboration rooms wired to
isolated microVM execution. Not a corpus entry (partnership, not a
sandbox product); recorded on the C45 row as the first third-party
Kit-ecosystem signal on launch day (INFERRED — novelty read on
launch-day coverage). Read for spark-vm: the Kits spec
is attracting builders on day one — if spark-vm ever speaks the Kits
contract, day-one Kit availability is the adoption lever.

**C26 — second consecutive docs-side miss + INFERRED misattribution
hypothesis.** The press-release side re-read VENDOR-VERIFIED this run
at $0.005/GiB-month (investors.digitalocean.com verbatim; Forkast.news
Sept 23 repeats it). Four search angles again failed to locate the
"Last verified 22 Sep 2026" docs pricing subpage ($0.05/GiB-month).
New INFERRED hypothesis this pass: DO's *general* Droplet/Volume
snapshot rate is $0.05/GB-month — the carried $0.05 figure may be
general-product pricing misattributed to Managed Agents. The corpus's
C26 deep-dive entry still records the docs $0.05 as
mid-evening-VERIFIED and is deliberately NOT rewritten on
absence-of-evidence; the next pass should weigh the misattribution
hypothesis against keeping the carried docs figure. Discrepancy
one-sided, carried open.

**Tracked set:** 8/8 VERIFIED NO-CHANGE — the quietest pass of the day,
zero deltas. C36, C41 (repo HEAD pin `39b6c3a` unmoved), C43, C44 all
re-verified unchanged. OpenAI Agents API still public beta
(VENDOR-VERIFIED Sep-10 dating; GA VERIFIED absent). Tensorlake (C46)
VERIFIED NO-CHANGE (no 9/24 news; latest remains the July 2026
beehiiv BYOC post). C37 Freestyle Pro fee still UNVERIFIED
(dashboard-signed-in check owed).

**Watch-doc naming:** `_PRE_MIDNIGHT` admitted per the convention's
already-taken-slot rule — today's `_NIGHT` was taken by the night pass
(#373, ~19:21 CDT) and `_LATE_NIGHT` by the late-night pass (#375,
~20:2x CDT), following the 2026-09-23 `_LATE_NIGHT` /
`_POST_MID_EVENING` precedent family.

## Watch update — 2026-09-24 (post overnight): C43 citation retired, C36 vendor-verified, C26 re-located

Productive pass, not a quiet one (watch doc
`docs/COMPETITOR_WATCH_2026-09-24_POST_OVERNIGHT.md`, delta-only vs the
overnight pass; survey ~23:55–00:20 CDT). Tracked set 8/8 VERIFIED
NO-CHANGE; Daytona's pricing figures ($0.0504/vCPU-h, $0.0162/GiB-h,
$200 free compute, per-second billing) moved from baseline-carried to
VERIFIED on Daytona's own pricing page this run, and the page's full GPU
ladder (B300 $4.08/h preemptible down to RTX 4090 $0.57/h) is now on
record. Corpus folds:

- **C43 — clean citation CAPTURED, debt retired.** VENDOR-VERIFIED
  2026-09-24 on ai.google.dev (page "Last updated 2026-09-24 UTC"):
  "Environment compute (CPU, memory, sandbox execution) is **not billed**
  during the preview period." Fixed allocations: 4 CPU cores, 16 GB
  memory. The field-table row now carries the verbatim quote + the fixed
  allocation.
- **C36 — FULL vendor verification.** VENDOR-VERIFIED 2026-09-24 on
  Google's Cloud Blog: open-source secure-by-default agent execution
  runtime; 10x density; sub-500ms resume at 500+ activations/sec;
  zero-trust kernel/network isolation; Cloud Hypervisor microVMs or
  gVisor; snapshots to local disk + GCS; 1,000+ dormant agents/host;
  portable to any K8s. Availability: open source, all GKE customers,
  non-production; production GA via allowlist. Nous Research (Hermes)
  early design partner. Cross-checked THIRD-PARTY (thecloudpod, itbrief).
- **C26 — docs surface re-located (5th consecutive standalone-pricing
  miss).** The docs index ("Last verified 21 Sep 2026") and Harness
  Runtime index ("Generated on 25 Sep 2026", UTC) both VENDOR-VERIFIED
  this run; the index confirms a Details section ("pricing, availability,
  limits") exists but exposes no URL — the standalone pricing subpage is
  still unlocated. Rates hold: $0.044/vCPU-hr, $0.0095/GB-hr, snapshots
  $0.005/GiB-month (DO's own 2026-09-22 investor release). The $0.05
  stays retired; the misattribution hypothesis stays INFERRED. The
  manage-sessions how-to is VENDOR-VERIFIED: sessions auto-pause after
  15 min of inactivity, "suspends its compute while preserving the
  workspace" (pause-semantics datapoint).
- **C41 — pin 96ff8a8 UNCHANGED, pricing digits re-verified.**
  VENDOR-VERIFIED 2026-09-24 on aliyun-fc/fc-docs commits/HEAD; all
  pricing digits unchanged; the page's preview notice confirms
  invite-only, allowlisted-in-batches rollout.
- **C37 — Hobby $50 re-confirmed, Pro fee UNVERIFIED.** VENDOR-VERIFIED
  2026-09-24 on freestyle.sh/pricing: "$50 on Hobby covers your first $50
  of usage." No Pro dollar amount on the public page; dashboard-signed-in
  check still owed (recorded plainly).
- **C44 — newest heading still September 22, 2026**; the Sep-1 entry
  flags "Session and memory bank compute metering in effect" for the
  Agent Platform compute SKU — pricing-work input.
- News (THIRD-PARTY, watch-doc color, no corpus fold): ByteAsk $1M
  pre-seed (C/C++ coding agents, YC Fall 2026); Ando $20M stealth launch
  (team chat with native agent roles, Codex/Claude support); Darktrace
  Signal Labs (agent behavioral-security research — trust-signals color);
  Clastix €2.9M seed (adjacent infra).
- Carried: OpenAI Agents API GA absence VENDOR-VERIFIED (still public
  beta); Tensorlake no Sep-24 news; Vercel Drives on the P49 morning
  cadence; boat.dev product-news retired.

## Watch update — 2026-09-24 (overnight): C41 pin moved, C26 $0.05 retired + DO billing-model garnish, OpenAI GA absence vendor-verified

Garnish fold per the C32/C37/C38/C39/C40/C41/C42/C43/C44/C45
precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_OVERNIGHT.md` (survey window
~22:55–23:10 CDT).

**C41 — repo HEAD pin MOVED for the first time (VENDOR-VERIFIED on
the official repo's commits/HEAD page).** The corpus HEAD pin is now
`96ff8a80f564271d6c3671a29dfecb6814bd6101` (short `96ff8a8`),
replacing `39b6c3a20ec4597cceda497a4d8badf5384e2022`. Pricing digits
unchanged (repo pricing file snippet-level: Eco 0.00936/0.004608,
Std 0.01224/0.006012, Pro 0.01872/0.009360; disk 0.00031896 mainland
CN / 0.00025308 outside). The pin moving after days of stillness is
the first genuine C41 delta — the docs repo is actively maintained,
not frozen.

**C26 — the carried $0.05 figure is retired; the 10x discrepancy
framing is withdrawn (honest correction).** The evidence-backed
Managed Agents snapshot rate is **$0.005/GiB-month** (vendor's own
investor release, 2026-09-22). The old search-historical $0.05 may
not be re-asserted: current general-snapshot doc snippets (page
last verified 8 May 2024) read
$0.06/GB-month (Droplets) / $0.06/GiB-month (volumes), and the
standalone Managed Agents pricing subpage missed its fourth
consecutive pass. The corpus's C26 deep-dive entry still records the
$0.05 as mid-evening-VERIFIED and is NOT silently rewritten — but on
next touch it must carry the correction: no vendor-read general
figure at $0.05 exists today. The weakened misattribution hypothesis
stands: search material mixed general-product and Managed-Agents
pricing; only $0.005 (vendor release) and $0.06 (current general,
snippet-level) survive this run's reads.
**C26 garnish — DigitalOcean's own billing model (LinkedIn, ~1 day
old, vendor-published):** Harness Runtime bills on **active CPU by
the second** — "$0.126/hr fully allocated" as the vendor's reference,
**~$0.0310/hr for a typical 25%-active agent run**, zero while
waiting. This is now the corpus's sharpest agent-sandbox duty-cycle
pricing comp — held as a reference for spark-vm's own hosted pricing
model.

**OpenAI Agents API — GA absence upgraded to VENDOR-VERIFIED.**
Official platform page + docs guide opened this run: still public
beta (`client.beta.agents`), "working toward GA." This corrects the
two prior passes' fetch failures — no longer search-level. **C37
Freestyle Pro fee: UNVERIFIED-carried, unchanged** (no public Pro
price; FAQ's $50/mo Hobby minimum re-VENDOR-VERIFIED; signed-in check
still owed). **C36 snippet-level** (page not opened — full verify
owed). **C43 VENDOR-VERIFIED in preview** (compute not billed during
preview; clean line citation owed). **C44 unchanged** (newest
release-note heading still Sep 22; Sep 9 GA stands). **Tensorlake no
Sep-24 news** (Jul 28 BYOC post re-fetched).

**Tracked set:** 8/8 VERIFIED NO-CHANGE — zero deltas, zero fetch
failures. Daytona changelog still leads with SEP 24 V0.216.1 above
V0.216.2; Docker Sandboxes release-notes still 2026-09-21;
Microsandbox still v0.7.3; E2B, boat.dev pricing, TermSquad
($9/$19/$29/$49 verbatim), AgentComputer (digit-for-digit),
DigitalOcean still public preview. Daytona pricing not re-fetched
(changelog-only scope; carried as baseline).

**In-lane dated 9/24:** Docker Cloud Sandboxes reconfirmed
(vendor snippet-level this run) — shape
prices filled in (Micro $0.07 / Small $0.14 / Medium $0.28 / Large
$0.56 / XL $1.12; sbx 0.45.1+; 24h max; $250 credit). Baseten×Blaxel
is Sep-24 *commentary* on a Sep-10 deal (acquisition terms
undisclosed; continuity promises lack duration/price/SLA guarantees),
not a launch. A Daytona "announcement" search hit was a stale
OpenHands-era PR — false positive, excluded. No credible Sep-24
vendor announcements across the rest of the scan list. Adjacent
context only: AWS Bedrock AgentCore sandbox DNS egress (~Sep 20,
THIRD-PARTY; AWS calls it intended functionality, no patch —
security-context for the loop); Upstash's 15-provider sandbox
comparison (~Sep 16, vendor-authored) — ready cost-model reference.

**Watch-doc naming:** `_OVERNIGHT` admitted per the 2026-09-23
`_LATE_NIGHT` / `_POST_MID_EVENING` / `_OVERNIGHT` precedent family.

## Watch update — 2026-09-24 (post mid evening): C45 price-and-terms garnish, C26 third miss, C37 fee VENDOR-VERIFIED absent

Garnish fold per the C32/C37/C38/C39/C40/C41/C42/C43/C44/C45
precedents; full pass record in
`docs/COMPETITOR_WATCH_2026-09-24_POST_MID_EVENING.md` (survey window
~21:55–22:05 CDT).

**C45 — first vendor-sourced price-and-terms package (VENDOR-VERIFIED
garnish).** Docker's own Sept-24 launch posts (read this run) now
supply the pricing/terms axis the corpus carried only from The
Register: one-command laptop↔cloud move (`sbx move --to cloud`),
pay-as-you-go **per-second**, Micro 1vCPU/2GiB **$0.07/hr** → XL
16/32 **$1.12/hr**, **paused = free**, 24h max sessions, **$250
new-account credit**, launched Sep 24 at WeAreDevelopers North
America. Folded into the C45 field-table row. Register corroboration
still value-for-value on the figures.

**C26 — third consecutive docs-side miss; INFERRED misattribution
hypothesis strengthened, not confirmed.** DO's own investor
announcement re-VENDOR-VERIFIED: $0.044/vCPU-hour, $0.0095/GB-hour,
snapshots **$0.005/GiB-month**, Managed Agents still public preview.
No page ties the carried $0.05 to Managed Agents; DO's
general-product $0.05/GB-month snapshot rate keeps surfacing near
Managed Agents queries. Both the carried figure and the discrepancy
stay open — deliberately not rewritten on absence-of-evidence.

**C37 — VENDOR-VERIFIED: no monthly-fee line-item on pricing surfaces;
FAQ discloses a $50/mo Hobby minimum-usage commitment** ("$50 on
Hobby covers your first $50 of usage"). freestyle.sh/pricing and related
public surfaces re-read this run. Dashboard-signed-in check still owed
(read-only surveyors can't reach it).

**Honest weakening — OpenAI Agents API GA absence is search-level
only.** No GA announcement dated 2026-09-24 in search, but the
official platform page fetch failed this run — so the absence is NOT
re-confirmed at vendor level this pass. The VENDOR-VERIFIED Sep-10
public-beta dating stands. The next pass owes a vendor-level
re-confirm.

**Re-verified unchanged:** C36 (allowlist-gated production GA,
VENDOR-VERIFIED), C41 (repo HEAD pin `39b6c3a` still unmoved;
pricing re-verified digit-for-digit — Eco/Std/Pro vCPU+mem+disk,
hibernation/snapshot formula), C44 (Sept 9 GA, newest release-note
heading still Sept 22). C43: official surface now identified
(`ai.google.dev/gemini-api/docs/agent-environment`) but not opened
this run — snippet-only, re-open owed. Tensorlake: search-level no
9/24 news (re-open owed; was snippet-only).

**Tracked set:** 8/8 VERIFIED NO-CHANGE — zero deltas. Scope honesty:
Daytona pricing figures were not re-fetched this pass
(changelog-only scope); carried as baseline-only. Vercel Drives not
re-checked (P49 once-daily morning cadence). boat.dev product-news
retry stays RETIRED (VERIFIED absent, 3 attempts). In-lane
no-launch verdict otherwise (search-level evidence).

**Watch-doc naming:** `_POST_MID_EVENING` admitted per the
already-taken-slot rule — today's `_EVENING`, `_LATE_EVENING`,
`_NIGHT`, `_LATE_NIGHT` and `_PRE_MIDNIGHT` were taken by earlier
passes — following the 2026-09-23 `_LATE_NIGHT` /
`_POST_MID_EVENING` precedent family.

## Watch update — 2026-09-25 (post midnight): C41 pin reverted, C9 third-party pricing color, Google AX candidate

Quiet pass with one real corpus correction (watch doc
`docs/COMPETITOR_WATCH_2026-09-25_POST_MIDNIGHT.md`, delta-only vs the
2026-09-24 post-overnight pass; survey window ~00:56–01:05 CDT).

**C41 — repo HEAD pin REVERTED, not moved again; pricing digits
unchanged.** VENDOR-VERIFIED via GitHub API 2026-09-25: the official
repo HEAD is back at the pre-overnight pin — short `39b6c3a2` is the
same commit as the previously recorded
`39b6c3a20ec4597cceda497a4d8badf5384e2022` (2026-09-21) — a revert
from `96ff8a8`, not a second forward move (field-table history keeps
only the two real positions; no phantom third). All digits re-read
live at HEAD and unchanged:
Eco 0.00936/vCPU-h + 0.004608/GiB-h, Std 0.01224 / 0.006012,
Pro 0.01872 / 0.009360, disk 0.00031896 (0.00025308 ex-mainland);
preview still invite-only, allowlisted-in-batches. Read: the docs
velocity continues, but the "second move" was a head-reset, not new
shipped content — priced-side, nothing moved.

**C9 — THIRD-PARTY pricing color (corroboration).** Hosted-sandbox
containers $0.03–$1.92 per 20-min session (1 GB–64 GB);
ZDR inapplicable even with a self-hosted sandbox (finance.biggo.com).
The ZDR line corroborates the corpus's already-filed no-ZDR
characterization. Agents API itself: still public beta (THIRD-PARTY ×3
this pass); GA absence stays VENDOR-VERIFIED (carried).

**New-to-watch candidate, not yet a corpus entry: Google AX v0.3.0.**
THIRD-PARTY (HN-noted): open-source (Apache-2.0) agent orchestrator
on Agent Substrate. Primary-source pass owed before a C-number.
**Grunz — flag only** ($100-once self-hosted coding agent; harness
lane, not sandbox-shaped). A rumored "GKE Agent Migration Tool"
Sep 25 announcement surfaces only on cointime.ai — UNVERIFIED,
single source, deliberately not filed.

**Carried:** C37 Pro fee still UNVERIFIED (public pricing surfaces
re-read, no dollar line-item; Hobby $50 minimum re-confirmed verbatim,
VENDOR-VERIFIED; signed-in dashboard check still owed); C26
standalone docs pricing page — 6th consecutive miss (misattribution
hypothesis stays INFERRED); Tensorlake no Sep-24/25 news (re-open
owed); C44 newest heading still Sept 22 (VENDOR-VERIFIED); C36 and
C43 confirmed unchanged (VENDOR-VERIFIED). Vercel Drives not
re-checked (P49 morning cadence); boat.dev product-news retry stays
RETIRED.

**Tracked set:** 8/8 VERIFIED NO-CHANGE — zero deltas, zero fetch
failures (all 8 surfaces opened directly on vendor-owned pages this
run). In-lane dated 9/25: no launches, no pricing moves, no funding
rounds in-window beyond the AX candidate and the Grunz flag.

**Watch-doc naming:** `_POST_MIDNIGHT` — first 2026-09-25 pass,
admitted per the 2026-09-23 `_LATE_NIGHT` / `_POST_MID_EVENING` /
`_OVERNIGHT` precedent family (verified collision-free against
origin/main's watch-doc list).
