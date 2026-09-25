# Competitor watch — 2026-09-24 (pre midnight)

Delta-only update against the late-night pass
(`docs/COMPETITOR_WATCH_2026-09-24_LATE_NIGHT.md`). Survey window
**2026-09-24 ~20:54–21:05 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set (Daytona, Docker Sandboxes release-notes page,
E2B, boat.dev pricing, Microsandbox, TermSquad, AgentComputer,
DigitalOcean Managed Agents — news only); (B) the carried asks
(OpenAI Agents API GA watch, C26 snapshot-rate discrepancy,
C37 Freestyle Pro fee, C36/C41/C43/C44, Tensorlake) and an open-web
in-lane news scan.
Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-2054.md`), not the repo. `_PRE_MIDNIGHT`
is admitted per the convention's "already-taken slot" rule — today's
`_NIGHT` was taken by the night pass (#373, ~19:21 CDT) and
`_LATE_NIGHT` by the late-night pass (#375, ~20:2x CDT) — following
the 2026-09-23 `_LATE_NIGHT` / `_POST_MID_EVENING` precedent family.

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

The quietest pass of the day: zero deltas across the whole set. The
late-night pass's Daytona changelog micro-delta is now the stable
baseline.

- **Daytona — VERIFIED NO-CHANGE** (https://www.daytona.io/changelog).
  Top 3 entries verbatim: **SEP 24 2026 — V0.216.1** ("API key
  organization ID and CLI update warning fix": organization context in
  API key listings, no outdated-version CLI warning when no newer
  release exists); **SEP 24 2026 — V0.216.2** ("CLI login through
  WorkOS"); **SEP 23 2026 — V0.216.0** ("Confine Dockerfile COPY
  sources to the build context"). Order, dates, and content all match
  the late-night baseline. Pricing page unchanged: $0.0504/vCPU-h,
  $0.0162/GiB-h, $200 free compute, per-second billing.
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Still tops at
  **2026-09-21** (v3 kits); nothing dated 09-22/09-23/09-24.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing,
  https://e2b.dev/docs/billing). Hobby FREE + $100 one-time credit;
  Pro $150/mo; 1 vCPU $0.000014/s → 8 vCPU $0.000112/s.
- **boat.dev — VERIFIED NO-CHANGE** (pricing:
  https://docs.boat.dev/pricing). $0.018/$0.036/$0.072/$0.200 per hour
  (small/default/large/xlarge); plans $20/$100/$500/$2000; trial 25
  free hours, 2 concurrent sandboxes (small/default only) until first
  payment.
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases). Still
  tops out **v0.7.3**.
- **TermSquad — VERIFIED NO-CHANGE** (https://termsquad.com/).
  Starter $9/mo (2 vCPU / 4 GB / 40 GB NVMe), Builder $19/mo
  (4 / 8 GB / 75 GB), Power $29/mo (6 / 12 GB / 100 GB), Ultra $49/mo
  (8 / 24 GB / 200 GB) — verbatim.
- **AgentComputer — VERIFIED NO-CHANGE**
  (https://www.agentcomputer.ai/pricing). $0.07/CPU-hr, $0.04375/GB-hr
  memory, $0.000683/GB-hr hot storage, **$0.000027/GB-hr cold
  (stopped)**; Enterprise tier.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE (news).** Still
  public preview; no GA announcement dated 2026-09-24. Vendor docs
  (https://docs.digitalocean.com/products/managed-agents/, "last
  verified 21 Sep 2026") still lead with "available in **public
  preview**"; Latest Updates section still 21 September 2026. Launch
  announcement remains dated 2026-09-22.

## 2. Carried asks

- **OpenAI Agents API GA watch — VERIFIED NO-CHANGE.** Still public
  beta. Five fresh THIRD-PARTY sources (crawls <24h — aicatchup FAQ,
  ai-xblog, chatgptaihub, quasa.io, artificialintelligence.ai) all
  state public beta; aicatchup verbatim: "Is the Agents API generally
  available? A: No." The VENDOR-VERIFIED Sep-10 beta dating stands; GA
  is VERIFIED absent. No announcement dated 2026-09-24 or this week.
  (Side note from ai-xblog: no additional platform fee — tokens/tools/
  execution billed only.)
- **C26 — DigitalOcean snapshot-rate discrepancy: UNVERIFIED-carried,
  second consecutive miss.** The press-release side (DO's own Sept 22
  release) re-read VENDOR-VERIFIED this run at **$0.005/GiB-month**
  (investors.digitalocean.com verbatim "snapshots at $0.005 per
  GiB-month"; Forkast.news Sept 23 repeats it). Four search angles
  (generic, `site:digitalocean.com`, Harness Runtime pricing, exact
  docs path) again failed to locate the "Last verified 22 Sep 2026"
  docs pricing subpage ($0.05/GiB-month). The 10x discrepancy is
  therefore one-sided this run. **INFERRED hypothesis from this pass:**
  DO's *general* Droplet/Volume snapshot rate is $0.05/GB-month
  (surfaced in this run's results) — the carried $0.05 figure may be
  general-product pricing misattributed to Managed Agents. No
  reconciliation attempted; the discrepancy stays carried open.
- **C37 — Freestyle Pro fee: UNVERIFIED, carried.** freestyle.sh/pricing
  re-read: still no dollar monthly fee printed for any plan; FAQ still
  only implies Hobby at $50/mo ("$50 on Hobby covers your first $50 of
  usage"). Pro fee absent on all public surfaces. Dashboard-signed-in
  check still owed.
- **C36 Google Agent Substrate — VERIFIED NO-CHANGE** (baseline
  allowlist sentence verbatim on the cloud.google.com blog).
  **C41 Alibaba FC Agent Sandbox — VERIFIED NO-CHANGE** (repo HEAD pin
  still `39b6c3a20ec4597cceda497a4d8badf5384e2022` — the pin has NOT
  moved; all pricing values match). **C43 Gemini Agent Environment —
  VERIFIED NO-CHANGE** (baseline lead verbatim, still preview).
  **C44 Computer Use + Shell sandboxes GA — VERIFIED NO-CHANGE**
  (Sept 9 GA entry intact, newest release-notes entry Sept 22).
- **Tensorlake (C46) — VERIFIED NO-CHANGE.** No news dated
  2026-09-24; latest remains the July 2026 beehiiv BYOC post. (Anti-confusion:
  the "September Updates" beehiiv post is Sept *2025*.)
- Vercel Drives not re-checked (P49 once-daily morning cadence stands).

## 3. In-lane news scan (dated 2026-09-24)

- **C45 upgrade — Docker Cloud Sandboxes launch availability now
  VENDOR-VERIFIED.** Docker's own posts, read this run:
  https://www.docker.com/blog/introducing-cloud-sandboxes-start-on-your-laptop-finish-in-the-cloud/
  and
  https://www.docker.com/blog/manufacturing-trust-for-ai-agents-keynote/
  confirm: same microVM isolation as local Docker Sandboxes on
  Docker-managed compute, one-command laptop↔cloud move, 1–16 vCPUs,
  pay-as-you-go, **"available today"**; Sandbox Kits are now standard
  OCI images ("Kits make authority reproducible"). Pricing per The
  Register's dated coverage: $0.07/hr Micro → $1.12/hr XL. This moves
  the C45 launch-availability claim from THIRD-PARTY (Register
  corroboration, late-night fold) to VENDOR-VERIFIED — a corpus garnish,
  not a new entry.
- **BAND × Docker partnership (Sept 24, 2026, THIRD-PARTY).** BAND
  announced the "BAND Python Kit for Docker Sandboxes" — multi-agent
  collaboration rooms wired to isolated microVM execution (PR Newswire
  dateline Sept 24, 2026). Adjacent color with a C45 tie: a third-party
  Kit ecosystem is forming around Docker's Kits spec on launch day
  (first such signal on launch day — INFERRED novelty read).
  No corpus entry — partnership, not a sandbox product; the C45
  field-table row carries the signal.
- **In-lane no-launch verdict otherwise:** nothing dated 2026-09-24 for
  Daytona, E2B, Modal, Vercel, AWS, Azure, Google Cloud (beyond C44),
  Cloudflare, Runloop, Fly.io, TermSquad, AgentComputer, boxd.sh, or
  opencomputer.dev.

## 4. Carried to the next pass

- Freestyle Pro's exact own-page fee (dashboard-signed-in check); C26
  continued monitoring — re-locate the docs pricing subpage first, and
  weigh the surveyor's INFERRED misattribution hypothesis (the carried
  $0.05/GiB-month may be DO's general-product snapshot rate) against
  keeping the carried docs figure in the corpus; OpenAI Agents API GA
  check; Vercel Drives (P49 morning cadence).
- boat.dev product-news retry: RETIRED — VERIFIED absent (3 attempts).
