# Competitor watch — 2026-09-26 (post-post-post-post-post-late-evening)

Two-surveyor pass, delta-only against the post-post-post-post-late-evening
pass (#515, slot 1954, merged as `360efbb`): (A) fast-mover + pricing
re-verification vs the ~19:56–19:59 CDT baseline (~20:27–20:29 CDT),
(B) delta news scan ~20:18–20:26 CDT. Read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-2024.md`,
`agent_notes/surveyor-b-20260926-2024.md` (under `hidden_files`).
Suffix `_POST_POST_POST_POST_POST_LATE_EVENING` admitted per the POST_
same-day-repeat precedent — the ~20:18–20:29 CDT window is past sunset
(~19:15), so `_NIGHT` would arguably be truer; kept in the LATE_EVENING
chain deliberately so the day's watch series stays one sortable series.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

All nine vendor fetches succeeded first-try — zero UNVERIFIED grades.
The all-first-try streak extends to **3** (this pass all-first-try;
the 1954 pass extended it to 2).

1. **Daytona changelog** (`daytona.io/changelog`, read ~20:27 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25 V0.217.0 (NVIDIA B300 GPU); SEP 24
   V0.216.1 (API key org ID) + V0.216.2 (CLI login through WorkOS); SEP 23
   V0.216.0 — all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`, read ~20:27 CDT) —
   newest dated heading still **2026-09-22** ("Improved sandbox moves and
   support for private kit images in cloud sandboxes."); next 2026-09-21
   (v3 kits), then 2026-09-15.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September** (Sandbox memory observability); no 26-Sep entry in
   any lane. Drives not re-checked per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE / $100 one-time usage credit, Pro $150/month,
per-second table top $0.000014/s); boat.dev (small $0.018 / default
$0.036 / large $0.072 / xlarge $0.200 per hour, 25 free trial hours,
"a stopped sandbox costs nothing" — read at `docs.boat.dev/pricing`, the
canonical URL recorded last pass); TermSquad ($9/$19/$29/$49 tiers,
BYO-AI FAQ intact); DigitalOcean Managed Agents ("Last
verified 22 Sep 2026"; $0.044/vCPU-hour actual-CPU, $0.0095/GB-hour
peak, snapshots $0.05/GiB-month, egress $0.01/GiB — the standing
snapshot-figure discrepancy vs the launch release ($0.05 vs $0.005) is
unresolved but unmoved); AgentComputer ($0.07 CPU-h, $0.04375 GB-h, hot
$0.000683 / stopped $0.000027 storage, still no egress policy stated —
C12 stands).

## Surveyor B — delta news scan: 0 new, 11 clean dedupes, 11 flagged-only

Quiet window (~20:18–20:26 CDT, 8 targeted searches; no verbatim page
fetches — nothing in-window surfaced to verify). No in-window, in-lane
product launches, pricing changes, funding events, or in-lane
sandbox-escape CVEs datelined 20:00–20:30 CDT.

Clean dedupes: **OpenAI offline-training-sandbox escape = C62**
(ScoopFeeds syndication of the Bloomberg Sep-26 4:29-AM piece — same
incident, pre-window); **DeepSeek Harness CVE-2026-82533 = C56** (Tech
Times recap, continuum-ai orca-archive markdown, OX Security recrawls —
all Sep 8–25); TermSquad Sep-15 launch-wire reprints (lifestyle
verticals — q923radio, washingtonguardian, epubzone, thriveinsider — no
new facts); **Modal $15B / Baseten $26B raise talks** (runtimewire,
bytevyte, Reuters radio syndication — pre-window; corpus holds the
Modal leg); **Factory $200M at $5B** (aibusinessreview recrawl);
**Docker Cloud Sandboxes launch = C45** (webpronews, how2shout recrawls
of the Sep-24 facts); **BAND × Docker Sandboxes kit (Sep 24)** —
first third-party Kit-ecosystem signal adjacent to C45/C52 (outbound
WebSocket, agent as room participant — garnish-grade, no new corpus
item); **Prime Intellect Prime Sandboxes GA = C48** (AlphaSignal
feature recrawl, Sep-23 GA — 30M environments, container-shaped API);
**DO Managed Agents public preview = C26 CLOSED** (businesswire launch
release recrawl); **Google Antigravity = C51** (startupfortune recrawl,
13 days old); **Docker Sandboxes CVE-2026-77179/79994** (AppleThreat /
aratech / CyberSecGuru recrawls of the Sep-15-disclosed virtio-fs +
socket-relay escapes, fixed 0.42.0 Sep 7 — known against the C45 corpus
line).

Flagged-only (new to corpus but failing lane/window bars — NOT filed):

- **Island raises $400M at $6.4B** (Sep 24, Reuters) — secure enterprise
  browser as AI-agent control plane. Fails **window bar** (Sep 24) and
  **lane bar** (browser security, not sandbox/VM compute).
- **Meta Muse ~2,000-server-tray napkin math** (Sep 26, 10:07am CT —
  runtimewire citing Tom's Hardware: user-tested 2 vCPU / ~8GB Muse
  sandboxes, 500k DAU → ~1,953 trays at 256 users/tray). Fails
  **window bar** (morning) and **evidence bar** (third-party napkin math
  — "Meta has not published or guaranteed those specifications"); scale
  color only, not a product move.
- **explainx.ai Meta Muse Sentinel-VM explainer** (base Sep 9; Sep-26
  update = the shipped Plaid read-only bank-linking connector, not a
  sandbox product move). Fails **lane bar**.
- **Pillar Security coding-agent sandbox escapes (~Sep 20)** — four
  repeatable patterns across Cursor, Codex, Gemini CLI, Antigravity
  (agent writes a file a trusted host tool later executes); Cursor
  tracked as **CVE-2026-48124** (fixed v3.0.0), Codex patched v0.95.0,
  Anthropic patched Claude Code v2.1.179, OpenAI Codex v0.146.0,
  Microsoft no Copilot fix, Google classified Antigravity low-severity
  no-patch. Fails **window bar** (~Sep 20); lane-adjacent (coding-agent
  local sandboxes, not agent-VM/compute).
- **Vertical-agent raises, pre-window (all THIRD-PARTY)** — Ema $77M
  Series B (Sep 23, HR/IT/finance agents, outcome pricing), Chamelio
  $26M Series A (Sep 23, legal agents), Augmeta $3M seed (Sep 22,
  agentic KPI ops). Fail **window bar** and **lane bar** (vertical
  agent apps, no sandbox/compute surface).
- **Infra funding color, pre-window (THIRD-PARTY)** — Crusoe $3.9B
  Series F at $30.9B, Snorkel AI $350M at $3.5B, Micro1 $100M at $4B,
  Naive AI $400M → $1.42B (mid-training/RL infra). Fail **window bar**
  (Sep 24–25) and **lane bar** (compute/data infra, not agent sandbox);
  demand-side context only.
- **Cognition/Devin ~$1B annualized revenue** (startupfortune recrawl —
  carried from 1954). Fails **lane bar** — demand signal for coding
  agents, not a sandbox/agent-compute product move.
- **AgentX raises $23M** (aistartupsnews, ~1 day — carried from 1954).
  Fails **lane bar** — no compute/sandbox surface in the coverage.
- **Dextr AI leaves stealth, $6.7M seed** (Sep 26 — carried from 1954;
  aging out next pass). Fails **lane bar** — vertical hotel-agent app.
- **hpc-sandbox-benchmarks leaderboard (~2 days, starslingdev)** —
  independent isolation-detection benchmark across 12 providers
  (Blaxel/firecracker, boat/qemu-kvm, Daytona firecracker, E2B,
  Microsandbox, Modal gVisor/cloud-hypervisor, Namespace, Novita,
  Runloop, Vercel firecracker, run.cloud, tama): cold-install medians
  (Namespace 34.9s fastest, run.cloud 124.3s slowest) + detected
  isolation mechanisms. Fails **window bar** and **product-move bar**
  (benchmark, not a launch/pricing/funding/CVE); lane-adjacent color
  for the isolation axis.
- **Whiteboard (YC W26) open-sourced** — desktop IDE where people and
  AI agents co-design software architecture. Fails **lane bar** —
  desktop IDE, no compute/sandbox surface; THIRD-PARTY mention only.

## Carried (no movement this pass)

- **C37** (Freestyle Pro fee VERIFIED absent — stands); **C55**; **C57**
  (Baponi); **C58** (Leap0 — pricing vendor-verified, "no published pricing" qualifier retired); **C62** (no movement); **C66** (OPEN, THIRD-PARTY — no
  in-window recrawl this pass); **C26** CLOSED (DO Managed Agents).
- In-lane no-launch verdict of 2026-09-25 stands — streak extends.
- Deep-scan queue unchanged: Heapjack/Overpatch + GitLab proxy escape
  (no in-window developments).
- Aged out this pass (stale, no movement): Arga Labs $10M (Aug 26),
  n8n expression-sandbox CVEs (Sep 14), Keenable $26M (Aug 25), Cua
  Cloud Sandbox (May 2025). Dextr ages out next pass unless something
  new develops.
- The Runloop "enterprise sandboxes" smb.harlandaily PR hit is ancient
  syndication junk (prnewswire vintage, "3047 days ago") — ignored, not
  tracked.
- computedsdk changelogs + wasmer-sdk sandbox-comparison doc surfaced
  this pass are third-party ecosystem docs, not vendor product moves —
  not tracked.

No corpus fold (no new C-numbers; no sanctioned-exception item this
pass). Next pass: routine tracked-set re-reads + the standard news
sweep.
