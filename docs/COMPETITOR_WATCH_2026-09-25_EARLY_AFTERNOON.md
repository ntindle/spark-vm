# Competitor watch — 2026-09-25 (early-afternoon)

Delta-only update against the 2026-09-25 post-mid-morning pass
(`docs/COMPETITOR_WATCH_2026-09-25_POST_MID_MORNING.md`). Survey window
**2026-09-25 ~12:45–12:55 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set + C44 heading check (12:46–12:55); (B) an
open-web in-lane news scan dated 2026-09-25 (12:45–12:48). Vercel
Drives NOT re-checked this pass (P49 once-daily morning cadence —
next the 2026-09-26 morning pass). Surveyor captures live in the
loop's `agent_notes/` workspace (`surveyor-a-20260925-1224.md`,
`surveyor-b-20260925-1224.md`), not the repo. `_EARLY_AFTERNOON` is
collision-free on origin/main's watch-doc list for this date
(MORNING/MID_MORNING/LATE_MORNING/MIDDAY/POST_MID_MORNING/AFTERNOON/
EVENING/NIGHT/PREDAWN/POST_MIDNIGHT/POST_NIGHT taken — precedent
family: `COMPETITOR_WATCH_2026-09-25_POST_NIGHT.md`).

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
  GPU preemptible ladder Nvidia B300 $4.08/h, B200 $3.59/h,
  AMD MI355X $3.44/h, H200 $2.61/h, H100 $2.27/h, RTX PRO 6000
  $1.74/h, RTX 5090 $0.74/h, RTX 4090 $0.57/h; Windows
  $0.0858/vCPU/h; "$200 in free compute included"; "All billing is
  calculated per second."
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
newest heading still **September 24, 2026** (content: Gemini 3.8 Live
GA, Muse Spark 1.3 Preview); no September 25, 2026 heading exists.
C44 (Computer Use and Shell sandboxes GA) still under September 09,
2026, wording unchanged.

## 2. In-lane moves — one adjacent corpus filing

### C55 new — Cloudflare Containers/Sandboxes cross-tenant disk-residue flaw — disclosed Sept 24–25, 2026 (THIRD-PARTY, adjacent)

A flaw in Cloudflare Containers — and Cloudflare Sandboxes, which
runs on Containers and is "sold as a safe place to run untrusted
code, including code written by AI agents" — let a paying customer
read data left behind by other customers' containers on the same
server. Root cause: Linux dm-thin provisioning with
`skip_block_zeroing` — deleted 64 KiB blocks returned to a
cross-account pool without wiping; a 4 KiB write into a reused block
left the other 60 KiB readable via raw disk reads. Recovered material
included directory listings, SQLite databases, Chromium profiles,
`.env` files, and credential files. Timeline: reported September 4,
2026 by Oren Yomtov (Accomplish) via HackerOne; the researchers'
PoC was dead by September 14; fleet-wide cleanup (draining/restarting
servers, clearing image caches) finished September 19; public
disclosure September 24–25 (The Hacker News article dated Thursday;
threadlinqs TL-2026-2648 "First published 2026-09-25", HIGH severity,
RESOLVED; no CVE assigned). Cloudflare says it found no evidence of
malicious exploitation in retained disk-activity telemetry and no
customer action is needed. Accomplish says this is its sixth sandbox
escape since July (Claude Cowork, Claude Code, Cursor CLI, Docker,
OpenAI Codex) and that the same disk setup affected Cloudflare's
Browser Run — Cloudflare's post named only Containers and Sandboxes.

Filed **adjacent** (security-incident disclosure by a sandbox
researcher targeting a sandbox operator, not a new product) per the
**C54** precedent. Directly relevant to spark-vm's sandbox threat
model: multi-tenant disk wipe discipline — block reuse across
tenants without zeroing leaks the previous tenant's data, exactly
the storage-layer failure mode any hosted-agent sandbox must defend
against.

### Deliberately not filed

- **C50 corroboration** (unite.ai, techstrong.ai, aistockwire.com,
  aiwiki.ai — Sep-25 press on the Copilot overhaul confirming
  usage-billed Cowork/Code/Autopilot): second/third press angles on
  an already-VENDOR-VERIFIED item — no grade change, no corpus move.
- **Zoho Catalyst 3.0** (Agent Skills, non-interactive CLI, MCP
  support, Claude Code/Codex integrations, free student tier):
  September-25 press reprint, but the primary release slug is
  20260902 — **September 2, 2026 vintage**, not a new move.
- **Google antigravity-preview-09-2026 + Files API + Credentials API**
  (Sep-17 vintage; week-of-Sep-25 digest mention is a roundup, not a
  launch).
- **DigitalOcean Managed Agents** (Sept-23 vintage launch; Harness
  runtime pricing lines already tracked).
- **Docker Cloud Sandboxes explainer** (C45, already corpus —
  ai.plainenglish.io member-only explainer dated "17 hours ago" is
  not a new move).
- **Baseten/Blaxel continuity analysis** (beri.net): dedupe against
  the corpus — the acquisition is already corpus **C11** and the
  continuity analysis was already logged as adjacent color. Analysis,
  not a vendor move.
- **C52 follow-up**: no new v2-kit mechanics surfaced this pass.
- **C11/C26**: no changes observed.
- **Meta Muse Mac VM-filesystem-export update** (explainx.ai "Update
  — September 25, 2026"; aiagentstore.ai week digest): watch-only per
  standing instruction — third-party snippet + "Meta calls it
  intended"; no vendor confirmation opened this run.
- **DeepSeek DSec Harness "leak"** — still single-source UNVERIFIED;
  standing instruction, not filed.
- **Guava "Daytona" voice model** — name collision; out of lane.
- **E2B $21M Series A** (July 2025 vintage) — stale.
- **marktechpost.com "Best Agent Sandboxes in 2026"** (Aug 27) —
  comparison table; background pricing color only, not a move.
- **Vercel Sandbox routing improvement** (Sep 8) / OpenAI Agents API +
  Vercel Sandbox integration (Sep 10) / Harbor evals (Sep 17) —
  all vintage; reflection, not moves.

### In-lane no-launch verdict

No net-new **agent-sandbox or hosted-agent-runtime launches** dated
2026-09-25 surfaced in this pass. The one net-new in-lane item is
the security-adjacent **C55** filing above. Nothing new from Daytona,
E2B, Microsandbox, Docker, Fly.io Sprites, Modal, Deno, DigitalOcean,
or boat.dev beyond the carried items.

### Out of lane (deliberately not filed)

Transluce/OpenAI agent autonomous breach (Sep-25 digest); SalesBleed /
CVE-2026-97735 / Roundcube (generic vuln news); Floatboat
(desktop proactive-agent OS, not sandbox infra); Gemini 3.8
Live/avatar/voice (Sep-15/24); Claude Opus 5.5 (Sep-22); Claude Code
Projects relaunch (Sep-17); VS Code 1.138 dev-container sessions;
Alibaba FC billing (July rollout); out-of-window funding; misdated
recrawls; name collisions.

## 3. Carried to the next pass

C37 Pro fee still structurally omitted; C44 newest heading still
Sep 24 (no Sep-25 entry — VERIFIED absent); C26 conflicts unchanged
(watched lines); C52 follow-up lead (Kits v2 mechanics read); C54
primary-source read (Perplexity's own post); **C55 primary-source
read** (blog.cloudflare.com disclosure — referenced but not opened
this pass); Island company announcement read (Reuters wire as cited);
Vercel Drives not re-checked (P49 — next the 2026-09-26 morning
pass). Next pass's ask: routine tracked-set re-reads; watch Docker
docs release-notes for the C45 Cloud Sandboxes surfacing.
