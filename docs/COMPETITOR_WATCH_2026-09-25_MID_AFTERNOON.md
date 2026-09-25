# Competitor watch — 2026-09-25 (mid-afternoon)

Delta-only update against the 2026-09-25 early-afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-25_EARLY_AFTERNOON.md`). Survey window
**2026-09-25 ~13:15–13:22 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set + C44 heading check (13:15–13:20); (B) an
open-web in-lane news scan dated 2026-09-25 (13:18–13:22). Vercel
Drives NOT re-checked this pass (P49 once-daily morning cadence —
next the 2026-09-26 morning pass). Surveyor captures live in the
loop's `agent_notes/` workspace (`surveyor-a-20260925-1254.md`,
`surveyor-b-20260925-1254.md`), not the repo. `_MID_AFTERNOON` is
collision-free on origin/main's watch-doc list for this date
(MORNING/MID_MORNING/LATE_MORNING/MIDDAY/POST_MID_MORNING/AFTERNOON/
EVENING/NIGHT/PREDAWN/POST_MIDNIGHT/POST_NIGHT/EARLY_AFTERNOON taken —
precedent family: the 2026-09-23/24 `_MID_AFTERNOON` passes).

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
failures** this pass — all 11 checks opened on vendor-owned pages
(Surveyor A: every fetch succeeded first try, no retries needed).

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
  surfaced on the docs release-notes page — VERIFIED absent (find for
  "Cloud Sandboxes" across the full page returned zero hits).
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
  time, per second, only while a sandbox runs. A stopped sandbox
  costs nothing." (Comparison table vs
  Novita/Freestyle/exe.dev/E2B/Daytona/Blaxel/Codespaces/Cloudflare/
  Modal/Islo/Runloop/Vercel Sandbox still present.)
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

## 2. In-lane moves — no new C-numbers; one adjacent-color grade upgrade

### Adjacent — Meta Muse VM-filesystem-export: second disclosure (Sep 25), THIRD-PARTY

- explainx.ai blog update (Sep 25, 2026) + ai0.news daily digest
  (2026-09-25): developers found Meta's Muse can be prompted to hand
  over its entire VM root filesystem (Ubuntu system files, app
  templates, internal docs). Meta's response was contradictory: a
  spokesperson said expected behavior in a personal Linux VM; Muse
  itself first refused, then apologized. ai0 notes this is the second
  Muse security disclosure in a week, following a separate
  agent-hijacking exploit.
- **Grade upgrade vs the carried watch-only snippet:** prior passes
  carried the Meta Muse Mac VM-filesystem-export line as watch-only
  (no vendor confirmation). This pass brings a vendor-spokesperson
  response — still third-party analysis (explainx + ai0; no
  vendor-primary page found), but no longer vendor-unconfirmed. The
  Sep-25 explainx update describes a Linux (Ubuntu) VM root-filesystem
  export — this corrects the earlier "Mac" shorthand, not a second
  variant being dropped.
- Filed **adjacent** — agent-VM execution-surface security intel, no
  product facts (no new product, no pricing, no shipped surface), so
  below the C-number bar. Relevant to spark-vm's threat model only as
  a data point on "agentic VMs that can be talked out of their own
  filesystem".

### Dedupe — BAND × Docker Sandboxes integration: already corpus

- Surveyor B surfaced the BAND (multi-agent collaboration platform)
  × Docker Sandboxes integration — "BAND Python Kit for Docker
  Sandboxes" announced Sep 24 (press release via Morningstar/PR
  Newswire; ecosystem kit corroborated on band-ai/band-sdk-python:
  sandboxed agents connect to shared BAND rooms via outbound
  WebSocket — persistent agent identities, @mention routing, message
  history, tool-execution events) — as a new FILE-adjacent candidate.
- It is **already corpus**: filed in the 2026-09-24 pre-midnight
  pass ("**BAND × Docker partnership (Sept 24, 2026,
  THIRD-PARTY)**", `docs/COMPETITOR_WATCH_2026-09-24_PRE_MIDNIGHT.md`)
  and carried as garnish in the **C45** field-table row ("first
  third-party Kit-ecosystem signal"). No double-file.

### Carried-lead resolutions

- **C52 follow-up (Kits v2 mechanics): RESOLVED — no file.**
  `docs.docker.com/ai/sandboxes/customize/kits-v2/` describes the
  `sbx`-CLI kit scheme: `spec.yaml` with `schemaVersion: "2"`,
  mixins, `--kit` selection ("For new kit development with the
  `sbx` CLI, use v3 kits"). This CLI-scheme v1/v2/v3 is DISTINCT
  from the Sep-24 next-generation Kits (OCI-image-based, Apache 2.0,
  committed to CNCF governance) already filed as **C52** — The
  Register's "Docker has also updated its Kits specification" =
  C52. Corpus note: do not conflate the sbx-CLI kit scheme with the
  OCI Kit Spec.
- **C54 primary-source read (Perplexity's own post): PARTIAL.**
  Vendor-owned index pages (research.perplexity.ai;
  www.perplexity.ai/hub/blog) list "Sep 23, 2026 — Escaping SPACE:
  Part I — Red-teaming VM isolation and network confinement for AI
  agents" at
  https://www.perplexity.ai/hub/blog/escaping-space-part-i — but the
  direct fetch returned HTTP 403 (upstream denied). Dated Sep 23,
  outside today's window regardless. Upgrades the C54-adjacent
  evidence to vendor-primary *listing* once a future pass reads it;
  the read itself stays carried.
- **Island Series F company-announcement read: RESOLVED — no
  file.** Found the company announcement (GlobeNewswire release,
  reprinted via Daily Guardian): "Island Announces $400 Million
  Series F, Bringing Valuation to $6.4 Billion," DALLAS,
  Sept. 24, 2026 — $400M led by Evolution Equity Partners, $6.4B
  valuation, "agentic control plane" framing. A fundraise, not a
  shipped surface — below the C-number bar (C53 precedent); already
  corpus-covered as adjacent color.

**Carried:** C37 Pro fee still structurally omitted (watched lines);
C44 newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent);
C26 conflicts unchanged (watched lines); C54 primary-source read
(the 403'd Perplexity page); C55 primary-source read
(blog.cloudflare.com disclosure); Vercel Drives NOT re-checked (P49
once-daily morning cadence — next the 2026-09-26 morning pass).
Deliberately not filed: BAND dedupe (already corpus C45 — see
§2); Transluce agent-swarm research + OpenAI-agent Australia breach
(ai0.news Sep-25 digest, snippet-level third-party — marginal to
sandbox infra, no product facts); DeepSeek DSec (already corpus —
groundtruth.day/kimkj.com Sep-25 third-party coverage, no new
product facts); Docker Cloud Sandboxes / Kits third-party reprints
(WebProNews, InfoWorld/The Register follow-ups, sharedsapience
Century Report — corpus-covered C45/C52, commentary or recap, no new
product facts); OpenClaw Direct managed-hosting launch (wire reprint
with conflicting dates — page claims Sep 25, crawl metadata ~212
days; marginal lane fit); Daytona "Agent-Agnostic Infrastructure"
PR-wire recrawl (vintage/undated — recap, no new facts); Whiteboard (YC W26 agent IDE recap — IDE,
not agent-VM infra); SandboxAQ Switch / AQtive Guard /
Selangor-Google Cloud "AI sandbox" (name collisions or out of lane).
Out of lane: Chainloop sandbox-kit one-liner (8-day-old repo
artifact, no dated announcement); Meta Muse Mac VM-filesystem-export
watch-only line retired in favor of the §2 adjacent upgrade above.

**In-lane no-launch verdict dated 2026-09-25:** no new
sandbox/runtime launches dated 2026-09-25 (the in-lane items surfaced
in this pass were disclosures, a fundraise-announcement read, and
ecosystem-kit coverage already in corpus).
