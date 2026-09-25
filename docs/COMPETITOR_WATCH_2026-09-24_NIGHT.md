# Competitor watch — 2026-09-24 (night)

Delta-only update against the mid-evening pass
(`docs/COMPETITOR_WATCH_2026-09-24_MID_EVENING.md`). Survey window
**2026-09-24 ~18:55–19:15 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set (Daytona, Docker Sandboxes release-notes page,
E2B, boat.dev pricing, Microsandbox, TermSquad, AgentComputer,
DigitalOcean Managed Agents — news only) plus a second attempt at
boat.dev's product-news surface; (B) the carried asks (DigitalOcean
docs-vs-release snapshot discrepancy, Simular Sai own pricing,
Freestyle own pricing, Tensorlake pricing page, wowza.com link) and an
open-web in-lane news scan.
Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-1854.md`), not the repo. `_NIGHT`
carries the 2026-09-23 precedent (the crowded `_EVENING` /
`_LATE_EVENING` / `_MID_EVENING` namespace is left untouched).

Evidence labels used by the watch passes: **VERIFIED** = read on a
vendor's own page, doc, or repo this run. **VENDOR-VERIFIED** =
confirmed on the vendor's own page, docs, or changelog read this run
(corpus field-table usage). **THIRD-PARTY** = press/third-party
sources. **snippet-only** = seen only via search snippet. **INFERRED** =
my characterization. **UNVERIFIED** = a public page exists but could not
be fetched this run (never reported as NO-CHANGE). **VERIFIED absent** =
the vendor's own page was read this run and the item is confirmed not
present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

The full quiet streak resumes after the mid-evening pass's one-item
re-verification: all eight tracked surfaces read clean with zero
pricing or feature deltas in the window.

- **Daytona — VERIFIED NO-CHANGE.**
  (https://www.daytona.io/changelog) still tops at **SEP 24
  V0.216.2** (CLI login through WorkOS) / **V0.216.1** (API key
  organization ID + CLI update warning fix), then SEP 23 V0.216.0. No
  V0.216.3+. Pricing page unchanged value-for-value
  ($0.0504/vCPU-h, $0.0162/GiB-h, $200 free credit, per-second). No
  daytona.io product news dated 2026-09-24.
- **Docker Sandboxes — VERIFIED NO-CHANGE (release-notes page).**
  (https://docs.docker.com/ai/sandboxes/release-notes/) still tops at
  **2026-09-21** (v3 kits); nothing dated 09-22/09-23/09-24.
- **Microsandbox — VERIFIED NO-CHANGE.** Releases
  (https://github.com/superradcompany/microsandbox/releases) still top
  out **v0.7.3**; no v0.7.4. Python SDK still 0.6.18 (Sep 9, 2026). No
  24h news.
- **E2B — VERIFIED NO-CHANGE.** https://e2b.dev/pricing and
  /docs/billing match baseline exactly: Hobby FREE + $100 one-time
  credit; Pro $150/mo; 1 vCPU $0.000014/s → 8 vCPU $0.000112/s. No
  product news dated 2026-09-24.
- **boat.dev — VERIFIED NO-CHANGE (pricing).** https://docs.boat.dev/pricing
  read this run (boat.dev/pricing itself terminal for fetchers) matches
  baseline: $0.018/$0.036/$0.072/$0.200 per hour
  (small/default/large/xlarge); plans $20/$100/$500/$2000; trial 25
  free hours, 2 concurrent sandboxes (small/default only) until first
  payment. Product-news surface: **not located a second time**
  (UNVERIFIED on that sub-item only) — docs.boat.dev root shows no
  changelog/blog nav, boat.dev homepage shows no blog link,
  `site:docs.boat.dev changelog` returns zero results, broad web
  search returned only noise.
- **TermSquad — VERIFIED NO-CHANGE.** https://termsquad.com/ — same
  positioning ("Always-On Cloud Computer for AI Agents"); pricing
  matches the 2026-09-18 baseline verbatim: Starter $9/mo (2 vCPU /
  4 GB / 40 GB NVMe), Builder $19/mo (4 / 8 GB / 75 GB), Power $29/mo
  (6 / 12 GB / 100 GB), Ultra $49/mo (8 / 24 GB / 200 GB).
  (Corpus-reporting nuance, not a delta: the mid-evening pass's
  shorthand "$9 entry; $29 mid; $49 Ultra" omitted the Builder tier —
  it is on the page and in the 9/18 baseline.) Only re-syndication of
  the Sept 15 launch release — same content, not a new announcement.
- **AgentComputer — VERIFIED NO-CHANGE.**
  https://www.agentcomputer.ai/pricing matches baseline value-for-value:
  $0.07/CPU-hr, $0.04375/GB-hr memory, $0.000683/GB-hr hot storage,
  **$0.000027/GB-hr cold (stopped)**; Enterprise tier. No 24h news.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE (news).** Nothing
  dated 2026-09-24; only continued re-syndication of the Sept 22
  public-preview launch wire. Still public preview, no GA news. (Pricing
  covered in §2 — Surveyor B's carried-ask beat.)

## 2. C26 — the snapshot discrepancy is REAL and LIVE

The carried pricing-subpage re-fetch from the mid-evening pass closed
tonight on **both surfaces, read live this run**:

- DO's own docs pricing subpage —
  `docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/`
  ("DigitalOcean Harness Runtime Pricing", **Last verified 22 Sep
  2026** — the same day the release went out) prints: *"Snapshots and
  Checkpoints — Billed per GiB stored when you use snapshots or
  checkpoints at **$0.05 per GiB-month**."*
- DO's own Sept 22 press release — on DO's investor-relations site
  (identical text on BusinessWire/Morningstar/forkast) — prints:
  *"CPU is billed per second of actual use at $0.044 per vCPU-hour and
  memory at $0.0095 per GB-hour, with **snapshots at $0.005 per
  GiB-month**."*

Neither surface has corrected the other. The 10x discrepancy stands as
an open live item. Internal-consistency note (INFERRED): the same docs
page prices session-storage volumes and custom sandbox templates at
$0.05/GiB-month too, and $0.05/GiB-month is DigitalOcean's longstanding
droplet-snapshot rate — so the docs figure reads as the platform-normal
rate and the press release's $0.005 as the outlier (likely a typo in
the release). Not resolved; the corpus's earlier "retired in favor of
the primary source" stance is formally superseded by the mid-evening
fold and tonight's dual-read: the conflict is live on two current
vendor surfaces, both carrying the vendor's own voice. Read for
spark-vm: a hosted sandbox's snapshot rate is exactly the kind of
figure a competitor copies without checking — this one is a live
case study in why pricing claims get primary-source re-verified.

## 3. C39 — Simular Sai pricing RESOLVED

- sai.work's own pricing page **exists and loads**:
  `https://sai.work/pricing/` ("Pricing | Sai by Simular AI") — the
  tier numerals render in elements the text fetcher strips (headings /
  images), so the exact numerals came from Simular's own-domain
  comparison pages instead. Feature structure VERIFIED on sai.work:
  Free tier ("Daily credit allowance… limited cloud Windows computer"),
  a paid tier with *"50,000 credits a month ($50 of usage) for AI
  models and computer time"*, an *"Unlimited AI usage… Always-on cloud
  computer"* tier, Enterprise ("Contact Us").
- Simular's own comparison pages (simular.ai/alternatives/ai-assistant
  and ai-executive-assistants, VERIFIED own-domain) print in full text:
  **"Free (Explore, daily credits) | $50/month (Pay as you go) |
  $500/month (Sai Unlimited) | Enterprise (custom)"** — consistent with
  the corpus's carried "$50 / $500" own-domain read; tier naming has
  evolved (Pay-as-you-go / Sai Unlimited).
- dume.ai's $20/$200/$500 (dume.ai/blog/dume-vs-simular-sai-2026,
  updated ~76 days ago) matches the OLD private-beta pricing cited by
  TechInAsia (June 2026: $20 plan discounted from $200, Pro $500) —
  **stale third-party, superseded.** Marked RESOLVED in the corpus
  with own-page figures Free / $50 / $500 / Enterprise.

## 4. C37 — Freestyle own pricing page FOUND

- URL: `https://www.freestyle.sh/pricing` ("Pricing - Freestyle") —
  VERIFIED own-page figures, usage-based: **vCPU-hour $0.04032**
  (200 included/mo), **GiB Memory-hour $0.0129** (400/mo), **GiB
  Storage-hour $0.000086** (60,000/mo), **Data Transfer $0.02/GB**
  (50 GB free / 500 GB paid). Plans: Free / Hobby / Pro (+ Enterprise
  custom). The FAQ states *"$50 on Hobby covers your first $50 of
  usage"* → **Hobby = $50/mo VERIFIED**. Pro's exact monthly fee is
  not printed in the fetched text (only "your monthly fee is a
  commitment that doubles as usage credit") — the everydev.ai
  $49/$499 claim was third-party: **$49 ≈ Hobby's own $50 own-page
  figure; Pro's $499 unconfirmed — carried to the next pass** (likely
  in admin.freestyle.sh or Stripe checkout; needs a signed-in check).
  The row's "own pricing page not read — UNVERIFIED" qualifier is
  retired; dashboard-internal pricing stays the one gap.

## 5. C46 NEW — Tensorlake pricing page (Firecracker-microVM sandbox product)

- URL: `https://tensorlake.ai/pricing` ("Pricing — Tensorlake", header
  *"OUR PRICING · UPDATED Q3 · 2026"*) — previously absent; now a full
  pricing page with tiers, rates, FAQ, and a pricing calculator
  (VERIFIED own-page).
- **Key discovery:** this is NOT document-OCR pricing ($0.01/page was
  third-party, per saasworthy/slashdot) — the page prices Tensorlake's
  **Firecracker-microVM sandbox product**, a direct E2B / spark-vm-class
  competitor ("Every tier runs on the same Firecracker microVMs").
  Tiers: **Free** ($0 forever, 1 sandbox, 2hr sessions); **Usage
  Credits** ($5–$20 prepaid packs, $0.01/CU); **Pro $250/billing
  cycle** (25,000 CU included); **Enterprise** (custom).
- Metered rates (own-page, VERIFIED): Active CPU **$0.07/core-hr**
  (credits) / **$0.042** (Pro); RAM **$0.015/GB-hr** / $0.009; Disk
  **$0.0002/GB-hr** / $0.0001; **snapshot storage $0.07/GB-month**
  (both tiers); network egress **free**. SOC 2 Type 2 on every tier,
  HIPAA on Pro+.
- Corpus relevance: Tensorlake's public posture has shifted from
  "document AI" to sandbox-provider-with-published-active-CPU-metering —
  the active-CPU figure ($0.042–0.07) lands at the E2B/Daytona/Fly
  Sprites cluster, and snapshot storage at $0.07/GB-month is the
  richest snapshot line in the corpus (DO is at $0.05 docs / $0.005
  release). Worth a dedicated field-table row and watch; this materially
  changes its competitor posture vs. the C38 "document-ingestion API,
  marginal in-lane" record. Folded as **C46** per the C32/C37/C38/C39
  precedents (primary-source verification = the sanctioned fold
  exception).

## 6. wowza.com link — VERIFIED live (no reset this pass)

`https://www.wowza.com/blog/av1-codec-aomedia-video-1-explained` loads
cleanly (HTTP 200, full article text): "AV1 Codec: AOMedia Video 1
Explained | Wowza Media Systems", published July 26, 2021 by Jan Ozer
— a genuine AV1-codec article, not a 404. The previously flagged
bot-reset behavior did not reproduce on this pass. The BACKLOG item is
closed (resolved by the morning turn; confirmed again tonight).

## 7. Carried asks + open-web news scan

- **C36, C41, C43, C44** — no new moves in the news scan (last
  re-verified mid-evening ~17:12 CDT; nothing dated 9/24 touches them).
- **OpenAI Agents API** — GA check not re-run this pass (last:
  Sep-10 public-beta dating VENDOR-VERIFIED, GA VERIFIED absent,
  mid-evening); carried.
- **Vercel Drives** — not re-checked (P49 once-daily morning cadence
  stands; last: still public beta, 20th no-change pass, morning turn).
- **In-lane dated 2026-09-24:** only the C45 Docker Cloud Sandboxes
  GA venue (already folded): The Register's Sept 24 coverage confirms
  Docker's own blog pricing ($0.07 Micro → $1.12 XL/hr, pay-as-you-go,
  "we meter compute by the second, and nothing else", paused = free,
  $250 free credit) and adds CLI color (`brew install docker/tap/sbx`,
  `sbx --cloud run claude`, sbx ≥ 0.45.1, Docker Personal/Pro). No
  new in-lane sandbox launches, pricing moves, or funding dated 9/24.

## Night verdict

A resolving pass, not a quiet one: two carried pricing debts retired
(C39 own-page RESOLVED, C37 own-page FOUND with one carried sub-item),
one new in-lane entrant folded (C46 Tensorlake), and the C26
discrepancy formally confirmed live on both vendor surfaces instead of
waved at. Tracked set: 8/8 VERIFIED NO-CHANGE — the quiet streak
resumes. Carried to the next pass: Freestyle Pro's exact own-page fee
(dashboard-signed-in check), C26 continued monitoring, OpenAI Agents
API GA check, boat.dev product-news surface (UNVERIFIED ×2).
