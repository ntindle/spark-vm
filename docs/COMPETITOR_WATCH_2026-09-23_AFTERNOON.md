# Competitor watch — 2026-09-23 (afternoon)

Delta-only update against the morning pass
(`docs/COMPETITOR_WATCH_2026-09-23_MORNING.md`). Survey window
**2026-09-23 ~05:56 → 06:10 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set (reads ~05:56–06:00 CDT), (B) Vercel Drives GA watch plus
open-web market-news scan (~05:56–06:10 CDT).

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) rather than a vendor doc-page assertion — a stricter
claim than VERIFIED, used only when we fetched the thing itself.
**THIRD-PARTY** = reported by press/third-party sources.
**INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.

## 1. The tracked set — fully quiet (8/8 NO-CHANGE, all VERIFIED)

Every baseline value from the ~04:57 CDT pass verified identical on
the vendor's own page, reads ~05:56–06:00 CDT:

- **Daytona** — changelog top entry still **SEP 23 2026 / V0.216.0 —
  "Confine Dockerfile COPY sources to the build context"** (Python,
  Ruby, TypeScript SDKs); V0.215.0 (SEP 22) still second (**VERIFIED**:
  https://www.daytona.io/changelog, ~05:56).
- **Docker Sandboxes** — release notes still top out **2026-09-21**
  (v3 kits verbatim; `sbx mcp catalog` removal, guest-kernel-crash
  recovery, experimental outbound UDP all still present) (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~05:56).
- **Microsandbox** — top release still **v0.7.1** (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~05:56).
- **E2B** — pricing unchanged: Hobby **FREE / $100 of usage in credits**
  ("$100 one-time usage credit"), Pro **$150/month**, Enterprise
  **CUSTOM** ($3,000/mo minimum); per-second table still tops
  **$0.000014/s** per vCPU (**VERIFIED**: https://e2b.dev/pricing,
  ~05:57).
- **boat.dev** — rate card unchanged: small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h** (xlarge needs a
  $100 plan or higher); "A stopped sandbox costs nothing"; trial still
  25 free hours, 2 sandboxes at once, small and default only, until
  first payment (**VERIFIED**: https://docs.boat.dev/pricing, ~05:57).
- **TermSquad** — tiers still Starter **$9/month** (2 vCPU / 4 GB /
  40 GB), Builder **$19/month** (4 vCPU / 8 GB / 75 GB), Power
  **$29/month** (6 vCPU / 12 GB / 100 GB), Ultra **$49/month**
  (8 vCPU / 24 GB / 200 GB); BYO-AI stance intact (**VERIFIED**:
  https://termsquad.com/, ~05:57).
- **DigitalOcean Managed Agents** — still **Public Preview**; hero
  still "under a couple of seconds" / "about 200 milliseconds"; docs
  index still **"Last verified 21 Sep 2026"**; Latest Updates still the
  21 September 2026 preview entry (**VERIFIED**:
  https://www.digitalocean.com/products/managed-agents and
  https://docs.digitalocean.com/products/managed-agents/, ~05:57).
- **AgentComputer** — pricing table identical (CPU **$0.07**/CPU-hour,
  memory **$0.04375**/GB-hour, hot **$0.000683**/GB-hour, cold
  **$0.000027**/GB-hour; Enterprise Custom); still **no stated egress
  policy** — C12 stands (**VERIFIED**:
  https://www.agentcomputer.ai/pricing, ~05:57).

## 2. Vercel Drives GA watch — NO-CHANGE

The standing follow-up ask (does Drives move toward GA?) is answered in
the negative for the third consecutive pass: `vercel.com/docs/sandbox/pricing`
still shows `last_updated: 2026-09-10`, every baseline term verifies
identical (Drive Storage 15 GB lifetime Hobby / $0.05/GB-month
Pro+Enterprise; Reads 30 GB/mo then $0.0015/GB; Writes 30 GB/mo then
$0.004/GB; max 4 drives/run; default 1 TiB (1 GiB Hobby); 16 TiB
max/drive; 64 GB ephemeral NVMe on SDK ≥3.0.0/custom image; session
caps 45 min / 24 h; concurrency 10 / 10,000), related links still point
to "…are now in public beta", and the vendor changelog's 22 September
Drives entry still reads verbatim *"…is now in public beta"* — no GA
date, no GA commitment, no wording change (**VERIFIED**, both pages
re-read ~05:56–06:10).

## 3. Market news — one in-window THIRD-PARTY delta, otherwise quiet

### 3a. Firecrawl $75M Series B (2026-09-22) — THIRD-PARTY investor color

A VC roundup (techstartups.com, citing Axios, ~3h old) reports
Firecrawl's **$75M Series B**, led by **Smash Capital**, participating:
Altos Ventures, Nexus Venture Partners, Y Combinator, Freestyle,
Offline (**THIRD-PARTY**:
https://techstartups.com/2026/09/22/venture-capital-startup-funding-roundup-september-22-2026-general-catalyst-goldman-sachs-greylock-m13-y-combinator-more/).
Sector: web-data layer for AI agents (crawl/extract/structure open-web
data) — adjacent infrastructure, not sandbox compute per se. This is the
same raise the 2026-09-23 watch already filed as investor color under
C32 (with the $82M SEC Form D anomaly flagged); this pass adds the
lead/participant detail. Filed as context only — NOT a corpus entry
(not vendor-verified, not sandbox-compute positioning).

The broader read stands (INFERRED): agent-infrastructure capital raising
continues at scale, but no capital is moving into spark-vm's
always-on-hosted-VM lane this window.

### 3b. Borderline (just outside the 48h window, lane-relevant)

- **Boxd $2M pre-seed** (announced 2026-09-16; article updated
  2026-09-20) — THIRD-PARTY (todaysstartupnews.com / 6ic.com): Dutch
  startup (founders Michiel Voortman, Laurentiu Ciobanu, Hidde Kehrer),
  led by BlueYard Capital, building persistent fork-in-milliseconds VMs
  for AI coding agents — directly in the spark-vm always-on lane
  (INFERRED relevance), but pre-seed and pre-window. Filed as color
  against C29's routine Boxd watch; no corpus change.
- **Alibaba Cloud FC Agent Sandbox pricing launch** (~5 days old) —
  THIRD-PARTY (aliyun-fc/fc-docs repo): E2B-SDK-compatible agent
  sandbox with new tiered pricing (Pro/Eco/Std) and "Shallow
  Hibernation" (suspend/resume-style persistence). Lane-adjacent,
  China-region; noted, not analyzed this pass.
- **E2B js-sdk 2.40.0** (~5 days old) — routine changelog (removed
  deprecated accessToken auth); no product/pricing move.

### 3c. Quiet in-window

Daytona, E2B (vendor announcements), Fly.io, DigitalOcean, Modal,
CodeSandbox, Railway, Render, Northflank, Runloop — no launches,
pricing changes, raises, or GA moves in-window. **No competitor
announced anything resembling always-on persistent agent machines —
the always-on hosted-VM niche (the spark-vm lane) had no new entrants
or pricing pressure this run.** Adjacent Vercel AI-Gateway model adds
(GPT-6 Sol + Luna, Claude Opus 5.5, Grok 4.7, MiMo V2.6) are model
routing, not compute, moves (VERIFIED, vendor changelog).

## 4. Standing items / carry-forwards

- **C14 (#47 resume-latency target):** still OPEN — needs our own
  measured provider baseline; the operator per-run Fly spend-cap
  decision is still owed (NEEDS_USER.md). No new benchmark-grade input
  this pass.
- **C29 (Boxd):** watch continues at routine cadence; pre-seed funding
  color added this pass, no product signal.
- **C26 (DO watch):** quiet this pass; vendor pages unchanged.
- **C12, C10:** stand, unchanged.
- **Cloudflare Sandbox:** no new signal; deprioritized retained.
- **Next pass's ask:** routine tracked-set re-reads; Vercel Drives GA
  watch continues (still public beta, page last_updated 2026-09-10;
  three consecutive no-change passes).

---

*Corpus note:* per the delta-only convention, watch docs record deltas
against the previous pass and the corpus changes only via
consolidation or primary-source verification. This pass carries no
primary-source-verified item that shifts competitive positioning —
**no corpus fold**. The two surveyor captures are archived verbatim in
the loop's `agent_notes/` (workspace-only), not the repo.
