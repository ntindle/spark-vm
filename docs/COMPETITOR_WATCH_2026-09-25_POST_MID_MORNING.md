# Competitor watch — 2026-09-25 (post-mid-morning)

Delta-only update against the 2026-09-25 mid-morning pass
(`docs/COMPETITOR_WATCH_2026-09-25_MID_MORNING.md`). Survey window
**2026-09-25 ~09:55–10:05 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set + C44 heading check; (B) an open-web in-lane
news scan dated 2026-09-25. Vercel Drives NOT re-checked this pass
(P49 once-daily morning cadence — next the 2026-09-26 morning pass).
Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a-20260925-0954.md`, `surveyor-b-20260925-0954.md`), not
the repo. `_POST_MID_MORNING` is collision-free on origin/main's
watch-doc list for this date (MORNING/MID_MORNING/LATE_MORNING/
MIDDAY/AFTERNOON/EVENING/NIGHT/PREDAWN/POST_MIDNIGHT/POST_NIGHT taken
— precedent family: `COMPETITOR_WATCH_2026-09-25_POST_NIGHT.md`).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **snippet-level** = seen only
via search snippet. **UNVERIFIED** = a public page exists but could
not be fetched this run (never reported as NO-CHANGE). **VERIFIED
absent** = the vendor's own page was read this run and the item is
confirmed not present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

Zero pricing/feature deltas across the whole set. **Zero fetch
failures** this pass — all 11 URLs opened on vendor-owned pages.

- **Daytona — VERIFIED NO-CHANGE** (changelog:
  https://www.daytona.io/changelog; pricing:
  https://www.daytona.io/pricing). Newest changelog entries still the
  SEP 24 2026 pair (V0.216.1 "API key organization ID and CLI update
  warning fix"; V0.216.2 "CLI login through WorkOS"); no September 25
  entry. Pricing verbatim: compute $0.0504/h per vCPU, memory
  $0.0162/h per GiB, storage $0.000108/h per GiB (after first 5 free);
  GPU preemptible ladder B300 $4.08/h down to RTX 4090 $0.57/h;
  Windows $0.0858/vCPU/h; "$200 in free compute included"; "All
  billing is calculated per second."
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Newest dated
  heading still *2026-09-21* ("Docker Sandboxes now supports v3 kits:
  OCI-based packages…"); next older *2026-09-15*. The Sep-24
  **Docker Cloud Sandboxes** launch (corpus **C45**) still has not
  surfaced on the docs release-notes page — VERIFIED absent.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby FREE
  + "$100 one-time usage credit" (sessions up to 1 hour, 20
  concurrent sandboxes); Pro $150/month (usage billed by the second,
  sessions up to 24 hours, 100 concurrent sandboxes expandable to
  1,100); per-second ladder 1 vCPU = $0.000014/s, 2 = $0.000028/s,
  4 = $0.000056/s, 6 = $0.000084/s, 8 = $0.000112/s.
- **boat.dev — VERIFIED NO-CHANGE** (https://docs.boat.dev/pricing).
  Sizes $0.018 / $0.036 / $0.072 / $0.200 per hour
  (small/default/large/xlarge); plans $20/$100/$500/$2000 per month;
  Trial "25 free hours, 2 sandboxes at once". "You pay for machine
  time, per second, only while a sandbox runs."
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases).
  Latest release still v0.7.3 ("chore: release v0.7.3 by @toksdotdev
  in #1646").
- **TermSquad — VERIFIED NO-CHANGE** (https://termsquad.com/pricing).
  Tiers Starter $9 / Builder $19 / Power $29 / Ultra $49 USD per month;
  "AI subscriptions and usage are not included."
- **AgentComputer — VERIFIED NO-CHANGE**
  (https://www.agentcomputer.ai/pricing). CPU Time $0.07 per CPU-hour;
  Memory $0.04375 per GB-hour; Hot Storage $0.000683 per GB-hour
  (running); Cold Storage $0.000027 per GB-hour (stopped).
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE**
  (https://docs.digitalocean.com/products/managed-agents/; pricing
  subpage
  https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/).
  Stamps still
  "Last verified 21 Sep 2026" and "Last verified 22 Sep 2026".
  Watched lines unchanged: CPU "$0.044 per vCPU-hour", Memory
  "$0.0095 per GB-hour", egress $0.01/GiB; footnote "*Active CPU
  billing is coming soon. Until then, you will be billed at 25% of
  the vCPUs allocated to your sandbox.*"

**C44 check — VERIFIED absent (separate from the tracked set):**
Google Gemini Enterprise Agent
Platform release notes
(https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
newest heading still **September 24, 2026**; no September 25, 2026
heading exists. C44 (Computer Use and Shell sandboxes GA) still under
September 09, 2026, wording unchanged.

## 2. In-lane moves — one adjacent filing

### Adjacent color — Island raises $400M Series F at $6.4B (no C-number)

Announced **September 24, 2026** (THIRD-PARTY: techstartups.com,
runtimewire.com; Reuters wire as cited — Evolution Equity Partners
led the round; read in full this run). The Dallas-based
enterprise-browser startup is explicitly extending into "security
controls for AI agents": CEO Mike Fey — "Every old control is
breaking, so everything's up for grabs"; the $6.4B valuation is an
investor bet that "enterprise browsers will become more valuable as
AI agents spread through corporate networks". Logged as adjacent
color only (NOT corpus): a fundraise states an intention, not a
shipped surface — below the C-number bar (the **C53** precedent had
an actual product launch). Kept as intelligence: enterprise agent
governance (permissions, identity, visibility) is the security
surface spark-vm's own guardrails story competes with.

### C54 new — Perplexity "Escaping SPACE: Part I" — sandbox egress-policy bypass red team (THIRD-PARTY, adjacent)

Perplexity's sandbox-security writeup published **September 23,
2026** (read via the Denny Sentinel analysis of September 24, 2026 —
THIRD-PARTY; Perplexity's own post not opened this run,
snippet-level). Nine frontier models were put inside a Firecracker
microVM running Perplexity's production agent sandbox (root, 216
runs): 0 of 108 VM-escape runs succeeded, but agents bypassed the
domain-based egress allowlist in 11 of 54 partial-network runs —
then reproduced authority-switch bypasses against 10 third-party
sandbox platforms, succeeding in eight: E2B, Vercel Sandbox,
microsandbox, Modal, Daytona, Deno, Fly.io Sprites (Cloudflare
Sandbox and NVIDIA OpenShell clean). Vendor-response table as of
September 10 (from the analysis): E2B HTTPS bypass (mitigation
planned); Vercel Sandbox HTTPS bypass (known limitation);
microsandbox HTTP+HTTPS bypass (mitigation released in v0.6.18);
Modal HTTPS bypass (known limitation); Daytona HTTPS bypass
(authority-mismatch enforcement released); Deno direct TCP bypass
(fix deployed); Fly.io Sprites HTTP+HTTPS bypass (mitigation in
progress). Directly relevant to spark-vm's sandbox threat model:
"Relying only on the destination IP address at the host to determine
whether a connection is allowed is insufficient"; "Never express an
egress policy as an IP or CIDR when the intent is a hostname."
Filed adjacent (security research by a sandbox operator, not a new
product) per the precedent.

### Deliberately not filed

- **Baseten/Blaxel continuity analysis** (beri.net, ~Sep 24): dedupe
  against the corpus — the acquisition is already corpus **C11** and
  the beri.net continuity analysis was already logged as adjacent
  color in an earlier watch note ("no corpus fold — analysis, not a
  vendor move"). No new vendor move; no new C-number.
- **C50 corroboration** (unite.ai / venturebeat / Reuters Sep 25
  Copilot overhaul coverage confirming the Managed Runtime public
  preview): second press angle on an already-VENDOR-VERIFIED item —
  no grade change, no corpus move.
- DeepSeek DSec Harness "leak" (UNVERIFIED single source — standing
  instruction). Meta Muse Mac VM-filesystem-export update line
  (snippet-level third-party, no vendor confirmation — watch only).

### In-lane no-launch verdict

No net-new **agent-sandbox or hosted-agent-runtime launches**
surfaced in the Sep-25 window beyond what's already in the corpus
(C45/C50/C52). The closest-to-lane fresh item is one security-adjacent filing
(C54) plus adjacent color (Island) and the C11 Baseten/Blaxel
dedupe note above. Nothing new from Daytona, E2B, Microsandbox, or
Docker beyond the carried C45 launch.

### Out of lane (deliberately not filed)

Google Gemini 3.8 Live with Live Avatar GA in Gemini Enterprise
(Sep 24); Google "Call for Me" (Sep 24); Gemini 3.8 Live / Extended
Thinking voice models (Sep 15); Claude Opus 5.5 (Sep 22); OpenAI
Agents API public beta (Sep-10 vintage, evidently covered by earlier
passes); Anthropic Claude Code Projects relaunch (Sep 17);
VS Code 1.138 agent sessions in Dev Containers (Sep 16);
Alibaba Cloud FC Agent Sandbox billing (rollout began July 31 —
doc touch-up, not a new move); AIR $50M seed (Sep 1); Arcade $60M
Series A (June); InTouchNow £2.3M seed; Kontext $4M seed
(snippet-level); Vercel Sandbox Harbor-evals integration (Sep-17
vintage, snippet-level); Vercel + OpenAI Agents API integration
(Sep-10 vintage, snippet-level); Open ACE v1.0.0 (undated,
snippet-level); name collisions ("Daytona" motorcycle/pizza places).

## 3. Carried to the next pass

C37 Pro fee still structurally omitted; C44 newest heading still
Sep 24 (no Sep-25 entry — VERIFIED absent); C26 conflicts unchanged
(watched lines); C52 follow-up lead (Kits v2 mechanics read); C54
primary-source read (Perplexity's own post); Island company
announcement read (Reuters wire as cited); Vercel Drives not
re-checked (P49 —
next the 2026-09-26 morning pass). Next pass's ask: routine
tracked-set re-reads; watch Docker docs release-notes for the C45
Cloud Sandboxes surfacing.
