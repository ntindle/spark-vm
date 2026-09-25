# Competitor watch — 2026-09-24 (overnight)

Delta-only update against the post-mid-evening pass
(`docs/COMPETITOR_WATCH_2026-09-24_POST_MID_EVENING.md`). Survey window
**2026-09-24 ~22:55–23:10 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set (Daytona, Docker Sandboxes release-notes page,
E2B, boat.dev pricing, Microsandbox, TermSquad, AgentComputer,
DigitalOcean Managed Agents — news only); (B) the carried asks (C26
snapshot-rate discrepancy, C37 Freestyle Pro fee, OpenAI Agents API GA
watch, C36/C41/C43/C44, Tensorlake) and an open-web in-lane news scan.
Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-2254.md`), not the repo. `_OVERNIGHT` follows
the 2026-09-23 `_LATE_NIGHT` / `_POST_MID_EVENING` / `_OVERNIGHT`
precedent family.

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

Zero pricing/feature deltas across the whole set. Zero fetch failures
this pass. One honest scope note: Daytona's pricing figures
($0.0504/vCPU-h, $0.0162/GiB-h, $200 free compute, per-second billing)
were not re-fetched this pass (the changelog was the only in-scope
Daytona URL) — carried as baseline-only, not re-asserted.

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
  verified 21 Sep 2026"); the only launch news is the Sep 21/22
  public-preview announcement. No GA announcement dated 2026-09-24.

## 2. Carried asks

- **C26 — DigitalOcean snapshot-rate discrepancy: UNVERIFIED-carried,
  FOURTH consecutive miss on the docs side — and the carried $0.05
  figure is RETIRED as current.** The Harness Runtime docs
  (generated 25 Sep UTC) advertise a pricing Details area covering
  "features, pricing, availability, limits, and data privacy," but the
  standalone pricing subpage again could not be located. The
  **evidence-backed** Managed Agents snapshot rate is
  **$0.005/GiB-month** (vendor's own investor release, dated
  2026-09-22; re-VENDOR-VERIFIED this run). The old search-historical
  $0.05 figure may not be re-asserted: current general-snapshot doc
  snippets (page last verified 8 May 2024) read
  **$0.06/GB-month (Droplets) / $0.06/GiB-month
  (volumes)**. The "10x discrepancy" framing is therefore withdrawn —
  there is no vendor-read general figure at $0.05 today, only a
  search-historical one. The misattribution hypothesis is kept in its
  weakened form: search material mixed general-product and
  Managed-Agents pricing; only the $0.005 (vendor release) and $0.06
  (current general, snippet-level) numbers survive this run's reads.
  **New vendor pricing-model signal** (corpus garnish): DO's own
  LinkedIn repost (~1 day old) quotes Harness Runtime as billed on
  **active CPU by the second** — "$0.126/hr fully allocated" as the
  vendor's reference, **~$0.0310/hr for a typical 25%-active agent
  run**, zero while waiting. This is the sharpest agent-sandbox
  duty-cycle pricing data in the corpus — held as a comp for
  spark-vm's own hosted pricing model.
- **C37 — Freestyle Pro fee: UNVERIFIED-carried, unchanged.**
  freestyle.sh/pricing re-read: no plan-price line-item for
  Free/Hobby/Pro; FAQ's $50/mo Hobby minimum-usage commitment
  re-VENDOR-VERIFIED ("$50 on Hobby covers your first $50 of usage").
  No public Pro dollar amount. Dashboard-signed-in check still owed
  (out of scope for read-only surveyors).
- **OpenAI Agents API GA watch — upgraded to VENDOR-VERIFIED this
  pass.** The official platform page and docs guide both opened this
  run: still **public beta** (`client.beta.agents` in the SDK
  example), "working toward GA," no GA announcement. This corrects the
  prior two passes' fetch failures — GA absence is now vendor-verified,
  not search-level.
- **C36 Google Agent Substrate — vendor snippet-level only this run.**
  Official blog result: open source for all GKE customers,
  non-production; production GA still allowlist-gated. Page itself not
  opened — full verification owed next pass.
- **C41 Alibaba FC Agent Sandbox — PIN MOVED (first movement
  observed).** The official-repo commits/HEAD page read this run
  (VENDOR-VERIFIED): repo HEAD is now short `96ff8a8`, full
  **`96ff8a80f564271d6c3671a29dfecb6814bd6101`** — replacing
  `39b6c3a20ec4597cceda497a4d8badf5384e2022`. Pricing digits unchanged
  (repo pricing file snippet-level: Eco 0.00936 vCPU / 0.004608 GiB,
  Std 0.01224 / 0.006012, Pro 0.01872 / 0.009360; disk 0.00031896
  mainland CN / 0.00025308 outside; hibernation/snapshots =
  (memory×2 + disk) × disk rate). Invitation/preview wording still
  owed on an official announcement page next run.
- **C43 Gemini Agent Environment — VENDOR-VERIFIED in preview.**
  The official doc page opened this run: managed Linux sandboxes,
  fresh/reusable environments, network rules, persistent files; preview
  section locates "compute not billed during preview" ("Environments
  and managed agents are in preview. Features and schemas may
  change."). Clean line citation owed next run.
- **C44 Computer Use + Shell sandboxes GA — VENDOR-VERIFIED
  UNCHANGED.** Release notes latest heading still **September 22,
  2026**; the September 9, 2026 entry still says Computer Use and
  Shell sandboxes are GA. No newer heading.
- **Tensorlake — no Sep-24 news (VENDOR-VERIFIED).** The July 28, 2026
  BYOC post re-fetched this run (BYOC across AWS/GCP/Azure/CoreWeave/
  Nebius/bare metal; pricing from 30% of compute CPU, as low as 10%,
  GPU 5% as low as 2%).
- Vercel Drives not re-checked (P49 once-daily morning cadence stands).

## 3. In-lane news scan (dated 2026-09-24)

- **Docker Cloud Sandboxes — launch reconfirmed, shape prices filled
  in.** The Sep-24 launch post re-read this run (vendor
  snippet-level): per-second compute only; paused free;
  volumes/egress/public images and Kits free; **Micro $0.07/hr,
  Small $0.14, Medium $0.28, Large $0.56, XL $1.12**; default one-hour
  sessions, max 24 hours; sbx 0.45.1+ with a pay-as-you-go plan on
  Personal/Pro; limited-time $250 new-account credit. No later
  pricing/terms change found.
- **Baseten × Blaxel — Sep-24 commentary on a Sep-10 deal, not a
  Sep-24 launch.** The beri.net continuity analysis ("last updated"
  ~Sep 23–24, THIRD-PARTY, opened this run) covers the **September
  10, 2026** acquisition (terms undisclosed; Baseten $13B post Series
  F; Blaxel $7.3M seed) and warns continuity promises lack
  duration/price/SLA guarantees. Reported here as dated commentary,
  not news.
- **No credible Sep-24 vendor announcements** for E2B, Modal,
  Browserbase, Steel.dev, Hyperbrowser, Anchor Browser, Runloop,
  Namespace Devboxes, Fly.io, Cloudflare, TermSquad, AgentComputer,
  boxd.sh, opencomputer.dev, browser-use cloud, Vercel (excl.
  Drives), Freestyle (beyond the pricing-page check), or Google
  Cloud (beyond C44). Results were comparison pages, third-party
  analysis, or older September material.
- **False positive caught:** a search hit on a Daytona "announcement"
  is a stale OpenHands-era PR — excluded, do not report as news.
- **Adjacent context (not Sep-24-dated):** AWS Bedrock AgentCore Code
  Interpreter sandbox DNS egress (~Sep 20, THIRD-PARTY; AWS calls it
  intended functionality, clarified docs, no patch — migrate critical
  workloads to VPC mode) — security context, not news. Upstash's
  15-provider sandbox comparison (~Sep 16, vendor-authored) — a
  ready-made cost-model reference for the loop's pricing work, not
  news.

## 4. Carried to the next pass

- C26: docs pricing subpage re-location stays the first ask; the
  $0.05 figure is no longer repeatable as current — the corpus's C26
  deep-dive entry needs its carried figure corrected on next touch
  (see corpus section). DO's LinkedIn billing model ($0.126 fully
  allocated / $0.0310 typical, active-CPU per-second, zero-when-idle)
  is now the corpus's sharpest agent-pricing comp.
- C37: dashboard-signed-in check for the exact Pro fee (read-only
  surveyors can't reach it).
- C36: open the official blog page (snippet-level this pass).
- C41: open the official repo pricing file + an official
  availability/announcement page for invitation/preview wording; the
  new pin `96ff8a8` is now the corpus HEAD pin.
- C43: capture the clean preview/pricing line citation (~5400–5430).
- Vercel Drives (P49 morning cadence).
- boat.dev product-news retry: RETIRED — VERIFIED absent (3 attempts).
