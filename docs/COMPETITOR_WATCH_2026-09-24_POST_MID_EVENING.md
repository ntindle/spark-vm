# Competitor watch — 2026-09-24 (post mid evening)

Delta-only update against the pre-midnight pass
(`docs/COMPETITOR_WATCH_2026-09-24_PRE_MIDNIGHT.md`). Survey window
**2026-09-24 ~21:55–22:05 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set (Daytona, Docker Sandboxes release-notes page,
E2B, boat.dev pricing, Microsandbox, TermSquad, AgentComputer,
DigitalOcean Managed Agents — news only); (B) the carried asks (C26
snapshot-rate discrepancy, C37 Freestyle Pro fee, OpenAI Agents API GA
watch, C36/C41/C43/C44, Tensorlake) and an open-web in-lane news scan.
Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-2154.md`), not the repo. `_POST_MID_EVENING`
is admitted per the convention's "already-taken slot" rule —
today's `_EVENING`, `_LATE_EVENING`, `_NIGHT`, `_LATE_NIGHT` and
`_PRE_MIDNIGHT` were taken by earlier passes — following the
2026-09-23 `_LATE_NIGHT` / `_POST_MID_EVENING` precedent family.

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

Zero pricing/feature deltas across the whole set. One honest scope
note: Daytona's pricing figures ($0.0504/vCPU-h, $0.0162/GiB-h,
$200 free compute, per-second billing) were not re-fetched this pass
(the changelog was the only in-scope Daytona URL) — carried as
baseline-only, not re-asserted.

- **Daytona — VERIFIED NO-CHANGE** (https://www.daytona.io/changelog).
  Top 3 still: SEP 24 V0.216.1 (API key organization ID + CLI update
  warning fix), SEP 24 V0.216.2 (CLI login through WorkOS),
  SEP 23 V0.216.0 (Confine Dockerfile COPY sources). No new entries.
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Still tops at
  **2026-09-21** (v3 kits); nothing dated 09-22/09-23/09-24.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing,
  https://e2b.dev/docs/billing). Hobby FREE + $100 one-time credit;
  Pro $150/mo; 1 vCPU $0.000014/s; per-second billing.
- **boat.dev — VERIFIED NO-CHANGE** (pricing:
  https://docs.boat.dev/pricing). $0.018/$0.036/$0.072/$0.200 per hour
  (small/default/large/xlarge); plans $20/$100/$500/$2000; trial 25
  free hours, 2 concurrent sandboxes (small/default only) until first
  payment. Comparison table and 2026-08-24 benchmark leaderboard
  unchanged.
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases). Still
  tops out **v0.7.3** (PR #1646).
- **TermSquad — VERIFIED NO-CHANGE** (https://termsquad.com/).
  Starter $9/mo (2 vCPU / 4 GB / 40 GB NVMe), Builder $19/mo
  (4 / 8 GB / 75 GB), Power $29/mo (6 / 12 GB / 100 GB), Ultra $49/mo
  (8 / 24 GB / 200 GB) — verbatim.
- **AgentComputer — VERIFIED NO-CHANGE**
  (https://www.agentcomputer.ai/pricing). $0.07/CPU-hr, $0.04375/GB-hr
  memory, $0.000683/GB-hr hot storage, **$0.000027/GB-hr cold
  (stopped)** — exact digit-for-digit match to baseline; Enterprise tier.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE (news).** Still
  public preview per the vendor's own docs
  (https://docs.digitalocean.com/products/managed-agents/, "Last
  verified 21 Sep 2026"); the only launch news in the press wires is
  the Sep 21/22 public-preview announcement. No GA announcement dated
  2026-09-24.

## 2. Carried asks

- **C26 — DigitalOcean snapshot-rate discrepancy: UNVERIFIED-carried,
  THIRD consecutive miss on the docs side.** The "Last verified 22 Sep
  2026" docs pricing subpage ($0.05/GiB-month carried figure) again
  could not be located — three consecutive misses. The press-release
  side was re-VENDOR-VERIFIED this run: DO's own investor announcement
  reads **$0.044/vCPU-hour**, **$0.0095/GB-hour**, snapshots at
  **$0.005/GiB-month**, Managed Agents still public preview.
  The **INFERRED misattribution hypothesis is strengthened, not
  confirmed**: DO's general-product snapshot rate ($0.05/GB-month,
  surfaced in search results) keeps surfacing near Managed Agents
  queries, but no page this run ties the $0.05 to Managed Agents
  specifically. The 10x discrepancy stays carried open; the
  docs-subpage re-location remains the first ask of the next pass.
- **C37 — Freestyle Pro fee: VENDOR-VERIFIED 2026-09-24 (no monthly-fee
  line-item; FAQ discloses $50/mo Hobby commitment).** freestyle.sh/pricing
  and related public surfaces re-read this run: no monthly-fee line-item
  on the pricing surfaces for Free/Hobby/Pro; the FAQ discloses a $50/mo
  Hobby minimum-usage commitment ("$50 on Hobby covers your first $50 of
  usage"). Dashboard-signed-in check still owed (out of scope for
  read-only surveyors).
- **OpenAI Agents API GA watch — search-level only this pass.** No GA
  announcement dated 2026-09-24 found in search results — but the
  official platform page fetch **failed this run**, so the absence is
  search-level, not VERIFIED absent. Baseline (VENDOR-VERIFIED Sep-10
  public beta dating) stands; GA absence is not re-confirmed at vendor
  level this pass. Honest weakening vs the pre-midnight pass's
  VERIFIED-absent claim.
- **C36 Google Agent Substrate — VENDOR-VERIFIED UNCHANGED.** Open
  source on GKE for non-production; production GA still allowlist-gated.
- **C41 Alibaba FC Agent Sandbox — VENDOR-VERIFIED UNCHANGED.** Repo
  HEAD pin still `39b6c3a20ec4597cceda497a4d8badf5384e2022` — the pin
  has NOT moved; invite-only preview; Eco $0.00936/vCPU-hr /
  $0.004608/GiB-hr, Standard $0.01224 / $0.006012, Pro $0.01872 /
  $0.009360; disk $0.00031896 (mainland CN) / $0.00025308 (outside);
  hibernation/snapshots = (memory×2 + disk) × disk rate.
- **C43 Gemini Agent Environment — snippet-only.** The official
  surface was identified (`ai.google.dev/gemini-api/docs/agent-environment`)
  but not opened this run; search signals still preview, no Sep-24 GA.
  No-change verdict not vendor-verified — re-open owed.
- **C44 Computer Use + Shell sandboxes GA — VENDOR-VERIFIED
  UNCHANGED.** Sept 9 GA confirmed; newest release-note heading still
  Sept 22, no newer entry.
- **Tensorlake — search-level no news.** No Sep-24 news in search
  results; the July 2026 BYOC post still present on vendor-owned
  surfaces (snippet-only; re-open remains owed).
- Vercel Drives not re-checked (P49 once-daily morning cadence stands).

## 3. In-lane news scan (dated 2026-09-24)

- **C45 garnish — Docker Cloud Sandboxes launch details VENDOR-VERIFIED.**
  Launched Sep 24 at **WeAreDevelopers North America**, "available
  today" (vendor posts read this run): same microVM isolation as local
  Docker Sandboxes on Docker-managed compute, one-command laptop↔cloud
  move (`sbx move --to cloud`), pay-as-you-go **per-second**,
  Micro 1vCPU/2GiB **$0.07/hr** → XL 16/32 **$1.12/hr**, **paused =
  free**, 24h max sessions, **$250 new-account credit**. This is a
  corpus field-table garnish on the already-VENDOR-VERIFIED C45
  availability (pre-midnight fold), not a new entry — but it is the
  first vendor-sourced price-and-terms package for Cloud Sandboxes,
  which sharpens the pricing axis the pre-midnight pass carried only
  from The Register.
- **In-lane no-launch verdict otherwise:** nothing dated 2026-09-24 for
  Daytona, E2B, Modal, Vercel (excl. Drives), AWS, Azure, Google Cloud
  (beyond C44), Cloudflare, Runloop, Fly.io, TermSquad, AgentComputer,
  boxd.sh, or opencomputer.dev (search-level evidence only for the
  no-news verdict).

## 4. Carried to the next pass

- C26: docs pricing subpage re-location FIRST; the misattribution
  hypothesis is INFERRED-strengthened but unconfirmed — keep the
  carried docs figure and the discrepancy both open until one surface
  confirms or denies the other.
- C37: dashboard-signed-in check for the exact Pro fee (read-only
  surveyors can't reach it).
- OpenAI Agents API GA: vendor-level re-confirm (official page fetch
  failed this pass).
- C43 re-open (official surface now identified); Tensorlake re-open
  (snippet-only no-news); Vercel Drives (P49 morning cadence).
- boat.dev product-news retry: RETIRED — VERIFIED absent (3 attempts).
