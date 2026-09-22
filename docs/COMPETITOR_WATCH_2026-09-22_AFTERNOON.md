# Competitor watch — afternoon pass, 2026-09-22

Delta-only update against the morning baseline
(`docs/COMPETITOR_WATCH_2026-09-22_MORNING.md`). Survey window
**2026-09-22 ~11:35 → ~16:10 CDT**; two read-only surveyors
(read-only fetches and searches; no logins, no writes): (A) vendor-page
re-reads of the tracked set (reads ~15:58–16:10 CDT), (B) open-web
market-news scan (~11:30–16:05 CDT). The morning pass was
press-release-only for the DigitalOcean launch; this pass adds the vendor
launch blog and product docs, which carry the day's real mechanism detail.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **THIRD-PARTY** = reported by press/third-party
sources. **INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.

## 1. DigitalOcean Managed Agents — launch blog adds the missing mechanism detail

**VERIFIED** (vendor launch blog read ~16:05 CDT:
https://www.digitalocean.com/blog/managed-agents-public-preview).
The morning watch (Business Wire press release only) had no mechanism
detail beyond the release's claims; the blog fills in substantial
technical shape:

- **Harness Runtime is Firecracker microVMs** — confirmed by name: one
  microVM per session, each with its own filesystem.
- **Exec + Access APIs** include security-hardened port forwarding.
- **Pause semantics made precise:** pause captures files, processes, and
  context; CPU + memory billing stops while paused, storage stays
  billable; **auto-pause is defined precisely as "no outgoing LLM or tool
  calls"** — the cleanest public definition of an idle trigger seen in
  the corpus so far (competitive input for #179, filed as **C28**).
- **Session-management APIs packaged as skills per supported harness**,
  so agents spawn subagents / run map-reduce themselves; structured
  observability events (tool calls, model requests, file ops), token
  usage + approval activity, session logs/metrics.
- **Bring-Your-Own-Template (BYOT):** custom agents ship as OCI images
  turned into reusable environment templates ("bringing your own
  harness"); the docs index mentions a **YAML environment spec**.
- **Action Gateway mechanics:** API keys, shared OAuth apps,
  **per-user OAuth**; a mid-workflow sign-in-link flow that **resumes the
  call after authorization**; model-backed tool search now quantified as
  **99.3% intent-match accuracy**; Action Gateway is **usable standalone**
  from any MCP-compatible app (not tied to the Harness Runtime);
  first-party tools that need a sandbox bill at Harness Runtime rates,
  third-party tools at published per-use pricing.
- **First concrete active-CPU worked example:** 2 vCPU at 25% average
  utilization + 4 GB peak for 1 h = **$0.060** vs $0.126 wall-clock.
- **Self-published benchmark** (internal, Sept 21, Codex CLI vs gpt-5.5,
  public API, RIC1, p50): create→ready **886 ms**, first response 3.3 s,
  resume **305 ms**, resumed-session response 2.43 s ≈ 2.47 s
  already-running. The candid part: **exec round trip 189 ms vs Fly.io
  Sprites 79 ms — 110 ms slower via edge/control-plane routing, named as
  a "performance priority"**. The comparator is named openly: **Fly.io
  Sprites** — DO is benchmarking against the very substrate behind the
  hosted product's chosen provider. (Competitive input for #47, filed as
  **C27**; context for the open C14 target.)

**VERIFIED** (https://docs.digitalocean.com/llms.txt read this run):
product docs are **live** at
`/products/managed-agents/`,
`/products/managed-agents/action-gateway/`, and
`/products/managed-agents/agent-harness-runtime/`. Billing docs confirm a
**prepaid-balance model**: Serverless Inference + Managed Agents require
a positive prepaid balance and are the only products DO suspends at $0
balance — prepaid-only consumption semantics (a first in the corpus;
worth noting against the hosted pricing-thinking's no-free-tier stance —
a prepaid wallet is DO's abuse lever, not a card-gated trial).

**VERIFIED** (https://docs.digitalocean.com/release-notes/ crawled ~1h
ago): Sept 21 release-notes entry — public preview for all users, BYOT
custom OCI sandbox templates. **No independent hands-on coverage exists
yet**: all third-party coverage found (TradingView, Market Newsdesk,
lifestyle syndication sites) is verbatim press-release reprints.

## 2. The tracked set — quiet (surveyor A, VERIFIED re-reads ~15:58–16:10 CDT)

No in-window change detected across the full tracked set:

- **Microsandbox** — top release still v0.7.1 (no new release since the
  morning read).
- **Docker Sandboxes** — release notes still top out at the 2026-09-15
  block (skills tri-state, MCP OAuth renames, git-kit hardening,
  credential-proxy fixes); no 0.44 yet.
- **Daytona** — changelog still tops at SEP 22 2026 / v0.215.0 ("Integer
  API client types and CLI MCP allowlist fixes") — the same entry the
  morning pass recorded; nothing newer.
- **E2B** — pricing unchanged (Hobby free + $100 one-time credit, Pro
  $150/mo + per-second usage, Enterprise custom; per-second table and
  the $3,000/mo Enterprise floor unchanged).
- **boat.dev** — pricing unchanged (small $0.018/h, default $0.036/h,
  large $0.072/h, xlarge $0.200/h; xlarge capacity-allocation caveat
  still present; trial 25 free hours; comparison table unchanged).
- **TermSquad** — tiers unchanged at $9/$19/$29/$49; BYO-AI stance
  unchanged.
- **DigitalOcean Managed Agents product page** (digitalocean.com) —
  **UNVERIFIABLE** this pass: the page failed to fetch twice; no second
  source consulted per the two-retry rule. The launch blog + docs reads
  above stand in as the verified mechanism source.

## 3. Adjacent color

- **Nutanix acquires Ryax** — THIRD-PARTY (blocksandfiles.com, dated
  2026-09-22): French agentic-AI infra company, bought for GPU
  utilization / smart scheduling, integrated into Nutanix Kubernetes
  Platform + Nutanix Enterprise AI. Adjacent, not sandbox infra — color
  only, no backlog item.

## 4. Pre-window color, new to the baseline

- **Active-CPU metering is now a four-vendor pattern, not a DO
  innovation.** VERIFIED (Vercel's own KB guide,
  https://vercel.com/kb/guide/vercel-sandbox-vs-e2b, crawled 1d ago):
  Active CPU billing $0.128/vCPU-hr active + wall-clock memory, claiming
  "up to 95% cost reduction" on bursty/I/O-bound patterns. THIRD-PARTY
  (marktechpost.com, Aug 27): Cloudflare Sandbox $0.072/vCPU-hr active-CPU
  + provisioned memory; Fly Sprites "active use only, sleeps when idle."
  No new vendor adopted active-CPU billing in-window; the pattern
  (DO/Vercel/Cloudflare/Fly) strengthens the C26 pricing-shape data
  point — active-CPU is the metering direction of travel across the
  corpus's serverless-sandbox segment.
- **Vercel KB claims "E2B passes secrets as environment variables visible
  inside the sandbox"** — THIRD-PARTY (a competitor's claim on its own
  page, not E2B-verified): recorded here as contrast color for H5, not a
  corpus edit — the secrets-posture corpus scores vendor-verified
  mechanism claims only.
- **Vercel announced a Herdr plugin ~Sept 17** — THIRD-PARTY (via a GitHub
  research note): each terminal agent runs in its own persistent Vercel
  Sandbox, orchestrated from Herdr's pane manager; credential-never-leaves-
  sandbox design; docs reveal a **second isolation model — multiple
  agents as separate Linux users in one shared sandbox**. Two isolation
  models in one product is a data point for the H11 multi-tenancy audit
  when it reads the corpus.
- **DO private-preview M.A.R.S. blog** (~Aug) — **VERIFIED** (DO's own
  vendor blog, https://www.digitalocean.com/blog/managed-agents-runtime-services-private-preview, read this run ~16:15 CDT): OAuth
  credentials **brokered through Secrets Manager**, exposed to neither
  the model nor the execution environment. Sharpens the fifth
  placeholder-swap data point (C26): DO's mechanism is brokered-at-
  execution through their secrets service — the placeholder-swap
  pattern in its brokered form.

## 5. Open threads / inputs filed

- **C27 (NEW, competitor → #47):** DO's self-published benchmark names
  Fly.io Sprites and quantifies the gap — create→ready 886 ms, exec RTT
  189 ms (Sprites 79 ms), resume 305 ms. Two uses: (a) candidate reference
  numbers for the corpus pricing/latency comparison tables until
  spark-vm has its own measurements — caveat: the benchmark is
  self-published (internal, Sept 21, p50), and the Sprites "resume" leg
  is derived (Sprites has no resume API — DO's own footnote); (b) the
  110 ms edge/control-plane routing tax is a design datapoint for #47's
  stream/edge shape — DO calls closing it a "performance priority."
- **C28 (NEW, competitor → #179):** DO defines auto-pause precisely as
  "no outgoing LLM or tool calls" — a concrete, public idle-trigger
  definition for #179's idle-lifecycle policy model. CPU+memory stops,
  storage billable, state (files/processes/context) preserved.
- **C14 (#47 resume-latency target):** still OPEN (needs our own measured
  provider baseline — the user's per-run Fly spend-cap decision is still
  owed). Sharpened context: DO's resumed-session response (2.43 s)
  ≈ already-running (2.47 s) — resume itself is amortized; the measured
  gap vs a warm box is create→ready (886 ms) and exec RTT (189 ms).
- **C26 (DO watch):** continues — product page unreadable this pass;
  re-read the launch blog against the shipped docs on the next pass.
- **C12, C10, C19/C20:** stand, unchanged.

## 6. Method note

Afternoon windows (~4.5 h since the morning baseline) are quiet on
release cadence but not on vendor-content: the morning's press-release-
only launch gained a full mechanism blog + live docs within the same
day. Watch passes on launch days should schedule the vendor-page re-read
second (it changed out from under the morning surveyor), not just news.
