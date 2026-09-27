# Competitor watch — 2026-09-27 (late afternoon)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the afternoon pass (#552, merged as `da6ac86`): (A)
fast-mover + pricing re-verification vs the ~07:55 CDT (2026-09-27) baseline
(vendor reads ~08:25–08:35 CDT 2026-09-27), (B) delta news scan ~07:55–08:24
CDT (~29-min delta window; 10 search queries). Read-only, no logins, no
writes. Captures: `agent_notes/surveyor-a-20260927-0824.md`,
`agent_notes/surveyor-b-20260927-0824.md`.

Naming-hygiene note: label rotation continues — `MORNING` → `LATE_MORNING` →
`MIDDAY` → `AFTERNOON` → `LATE_AFTERNOON` (chains rotate, not stack; the label
is a rotation counter, not a wall-clock claim — this pass ran ~08:25–08:35
CDT). A further same-day pass rotates again rather than reusing or
POST_-stacking.

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: nothing ages out. C62
(OpenAI offline-sandbox escape) drew recrawl contact this pass (syndication
wave) — **quiet count resets to 0** (was quiet pass 1 of 3 at 0754). Recrawl
contact this pass (all quiet counts reset, NOT quiet passes): C67 (Huawei
CodeArts Agent family coverage; grade stays FIRST-PARTY-CORROBORATED), C56
(DeepSeek Harness CVE-2026-82533), C29 (Boxd pre-seed recrawls). C11
(Baseten/Blaxel) drew zero mentions — **quiet pass 1** of 3. Aged-out items
stayed out or silent with no real movement (C66; Heapjack/Overpatch — a
techgig reprint is pure syndication of the aged-out item, no new movement;
GitLab CVE-2026-85706; Dextr AI). Re-fold-path gap still open: no re-fold
path for an aged-out item that resurfaces with real movement (follow-up
proposal from the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~08:25–08:35 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks (the all-first-try
streak restarted at the 0424 pass extends to **7 passes**). Every verified
figure matches the ~07:55 CDT baseline on substance. No corpus fold (C32
precedent: nothing changed on a primary source).

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26 2026 /
   V0.218.0** ("KVM sandbox parameter and CLI WorkOS application"); SEP 25
   V0.217.0 ("NVIDIA B300 GPU type") still second; SEP 24 V0.216.1/V0.216.2
   unchanged.
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22** (improved sandbox moves, private
   kit images); the 2026-09-21 v3-kits and 2026-09-15 entries unchanged.
3. **Microsandbox releases** (`github.com/superradcompany/microsandbox/releases`)
   — newest still **v0.7.3** (#1646); v0.7.1, v0.7.0, v0.6.17 beneath
   unchanged.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September** (3 entries: VCR GitHub Action, Pixel Canary, Sandbox memory
   observability); no 26-Sep or 27-Sep entries in any lane. The 23-Sep Drives
   public-beta entry still reads beta-only (no GA language — consistent with
   the out-of-scope P49 watch).
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro $150/mo, Enterprise CUSTOM ($3,000/mo estimator floor), per-second
   billing tops $0.000014/s per vCPU; concurrency tables intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures identical
   ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours; $20/$100/$500/$2000
   plans; xlarge $100+ plan gate); comparison + benchmark + active-CPU-billing
   sections unchanged.
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers (Starter/
   Builder/Power/Ultra, specs 2vCPU/4GB/40GB → 8vCPU/24GB/200GB), BYO-AI FAQ
   ("No. AI subscriptions and usage are not included.") intact.
8. **DigitalOcean harness-runtime pricing** (canonical URL, HTTP 200) — CPU
   $0.044/vCPU-hr, Memory $0.0095/GB-hr, egress $0.01/GiB, snapshots $0.05/
   GiB-month; 25%-of-allocated active-CPU footnote intact; stamp still
   "Last verified 22 Sep 2026"; mars-1vcpu-1gb → mars-16vcpu-32gb shapes
   intact. DO snapshot-figure discrepancy unresolved but unmoved.
   Advisory baseline correction: this page's 0754 baseline capture said "no
   stamp"; the direct read this pass finds the stamp present and matching the
   long corpus history — the 0754 line appears to be a transcription slip, not
   a page change. No fold (no substance change on the primary source).
9. **AgentComputer.ai pricing** — $0.07/CPU-hr, $0.04375/GB-hr, Hot $0.000683/
   Cold $0.000027, Enterprise custom tier present, still no egress line —
   C12 stays OPEN.

(Vercel Drives not re-checked per P49 daily cadence — next due 2026-09-28.)

## Surveyor B — delta news scan: 0 NEW / 15 clean dedupes / 1 flagged-only

**0 NEW.** All 10 queries returned only pre-window events and recrawls of
already-filed items — no new C-numbers, no grade changes.

**15 clean dedupes** (all filed, no new facts): Docker Cloud Sandboxes
Sep-24/25 launch-wave recrawls (Docker press page, merge.news, GlobeNewswire
syndication reprints); Daytona third-party SDK changelog bookkeeping
(ex_daytona, computesdk, mastra, langchain-ai/deepagentsjs 0.2.3); E2B $21M
Series A recrawls (SiliconANGLE, vestbee); **C56** recrawls (CSA labs note,
dennysentinel, aicybr, continuum-ai-corp/orca archive, techtimes "escape
catalog") — recrawl contact; Docker CVE-2026-77179/79994 recrawls (aratech.ae,
thecybersecguru — corpus "Not counted" classification stands); **C67**
family recrawls (yamchatime, pocketnews, malaysiasme, fintechnews.sg,
scommerce, itbrief.asia Singapore-family, support.huaweicloud.com CodeArts
Agent "What's New") — recrawl contact, grade unchanged
FIRST-PARTY-CORROBORATED; **C29** recrawls (6ic.com, ai-market-watch,
todaysstartupnews) — recrawl contact; **C62** syndication wave (gagadget,
startupfortune, panews, jbiznews, root-nation, deafnews) re-reporting the
Sep-25/26 alignment-site disclosure, no new facts — recrawl contact, quiet
count resets; Kontext $4M seed recrawls; Raindrop $50M Series A reprint;
ByteAsk $1M pre-seed reprints; Vercel Sandbox write-ups/changelogs
(nandann Drives write-up filed MIDDAY; vercel/sandbox + vercel-py SDK
changelogs, Sep 14 pre-window); jasonzhu.ai OpenAI Agents SDK Evolution
color (7-provider list — filed Sep-10 flagged-only precedent); Pillar
Security sandbox-escape mention (filed in COMPETITOR_ANALYSIS.md + 09-25/
09-26 docs); Heapjack/Overpatch techgig reprint (Sep 21 — aged-out, pure
syndication, stays out).

**1 flagged-only, NOT folded, no C-number:** lane-adjacent only —
`openai/openai-cookbook` self-hosted sandbox examples README (updated ~3 days
ago; Blaxel, Cloudflare, Daytona, DO, Docker, E2B, Modal, OCI, Runloop,
Vercel examples for OpenAI Agents API application-managed/webhook-managed
provisioning). New-to-corpus sighting but framework-level usage color —
first-party example docs, not new sandbox infrastructure. OpenAI Agents API
flagged-only precedent applies.

Stale-version rule compliant; Surveyor B grepped the last 3 watch docs plus
corpus for every candidate before classifying — no false first-sightings.

## Verdict

**No new in-window in-lane launches this window; the sandbox-infrastructure
lane stays quiet.** Vendors: 9/9 unchanged; the all-first-try streak reaches
7 passes. News: 0 new, recrawls only. The corpus is steady — carried items
C37, C55, C57, C58 (pricing vendor-verified), C62 (quiet count reset),
C67 (FIRST-PARTY-CORROBORATED, recrawl contact); C26 CLOSED; C12 OPEN
(AgentComputer still no egress policy); C11 quiet pass 1 of 3. Aged out
(staying out): C66, Heapjack/Overpatch, GitLab proxy escape
(CVE-2026-85706), Dextr AI. Re-fold-path gap still open.
