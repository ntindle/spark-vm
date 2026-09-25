# Competitor watch — 2026-09-24 (late night)

Delta-only update against the night pass
(`docs/COMPETITOR_WATCH_2026-09-24_NIGHT.md`). Survey window
**2026-09-24 ~20:00–20:20 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set (Daytona, Docker Sandboxes release-notes page,
E2B, boat.dev pricing, Microsandbox, TermSquad, AgentComputer,
DigitalOcean Managed Agents — news only); (B) the carried asks
(OpenAI Agents API GA watch, C26 snapshot-rate discrepancy, C37
Freestyle Pro fee, C36/C41/C43/C44, boat.dev product-news third
attempt, Tensorlake) and an open-web in-lane news scan.
Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-1954.md`), not the repo. `_LATE_NIGHT`
is admitted per the convention's "already-taken slot" rule — today's
night pass (#373, ~19:21 CDT) had already taken `_NIGHT` —
following the 2026-09-23 `_LATE_NIGHT` precedent (delta-only against
`_EARLY_NIGHT`). The crowded `_EVENING` / `_LATE_EVENING` /
`_MID_EVENING` namespace is left untouched.

Evidence labels used by the watch passes: **VERIFIED** = read on a
vendor's own page, doc, or repo this run. **VENDOR-VERIFIED** =
confirmed on the vendor's own page, docs, or changelog read this run
(corpus field-table usage). **THIRD-PARTY** = press/third-party
sources. **snippet-only** = seen only via search snippet. **INFERRED** =
my characterization. **UNVERIFIED** = a public page exists but could not
be fetched this run (never reported as NO-CHANGE). **VERIFIED absent** =
the vendor's own page was read this run and the item is confirmed not
present on it.

## 1. The tracked set — 7/8 VERIFIED NO-CHANGE, one micro-delta

- **Daytona — micro-delta (changelog order, not a new release).**
  (https://www.daytona.io/changelog) now leads with **V0.216.1 (SEP 24
  2026)** — API key organization ID + CLI update-warning fix — above
  **V0.216.2 (SEP 24)**; the night pass read V0.216.2 on top. No
  V0.216.3+. Content of both entries unchanged from the afternoon
  pass's fold. Pricing page unchanged: $0.0504/vCPU-h, $0.0162/GiB-h,
  $200 free compute, per-second billing.
- **Docker Sandboxes — VERIFIED NO-CHANGE (release-notes page).**
  (https://docs.docker.com/ai/sandboxes/release-notes/) still tops at
  **2026-09-21** (v3 kits); nothing dated 09-22/09-23/09-24.
- **Microsandbox — VERIFIED NO-CHANGE.** Releases
  (https://github.com/superradcompany/microsandbox/releases) still top
  out **v0.7.3**.
- **E2B — VERIFIED NO-CHANGE.** https://e2b.dev/pricing and
  /docs/billing match baseline exactly: Hobby FREE + $100 one-time
  credit; Pro $150/mo; 1 vCPU $0.000014/s → 8 vCPU $0.000112/s.
- **boat.dev — VERIFIED NO-CHANGE (pricing).**
  https://docs.boat.dev/pricing matches baseline: $0.018/$0.036/$0.072/
  $0.200 per hour (small/default/large/xlarge); plans
  $20/$100/$500/$2000; trial 25 free hours, 2 concurrent sandboxes
  (small/default only) until first payment.
- **TermSquad — VERIFIED NO-CHANGE.** https://termsquad.com/ —
  pricing from the 2026-09-18 baseline: Starter $9/mo (2 vCPU
  / 4 GB / 40 GB NVMe), Builder $19/mo (4 / 8 GB / 75 GB), Power $29/mo
  (6 / 12 GB / 100 GB), Ultra $49/mo (8 / 24 GB / 200 GB).
- **AgentComputer — VERIFIED NO-CHANGE.**
  https://www.agentcomputer.ai/pricing matches baseline value-for-value:
  $0.07/CPU-hr, $0.04375/GB-hr memory, $0.000683/GB-hr hot storage,
  **$0.000027/GB-hr cold (stopped)**; Enterprise tier.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE (news).** Still
  public preview; no GA announcement dated 2026-09-24. Launch
  announcement remains dated 2026-09-22. Architecture re-confirmed on
  vendor surfaces: Harness Runtime (Firecracker idle-pausing microVMs)
  + Action Gateway (16,000+ tool MCP gateway), pay-per-use CPU billing.

## 2. Carried asks

- **OpenAI Agents API GA watch — VERIFIED NO-CHANGE.** Still public
  beta. Three fresh THIRD-PARTY sources read this run explicitly
  answer "Is the Agents API generally available? No" — corroborating
  the VENDOR-VERIFIED Sep-10 beta dating. No GA announcement dated
  2026-09-24 or this week.
- **C26 — DigitalOcean snapshot-rate discrepancy: partial re-read,
  carried open.** The press-release side (DO's own Sept 22 release,
  businesswire + investors.digitalocean.com) re-read VERIFIED this
  run at **$0.005/GiB-month**. The docs side ($0.05/GiB-month on the
  "Last verified 22 Sep 2026" pricing subpage) is **UNVERIFIED this
  run**: three searches plus the Harness Runtime docs page (which
  carries no price numbers at all) could not locate the pricing
  subpage. The 10x discrepancy is therefore *not re-observable* this
  run — the docs side may have been corrected or the page may have
  moved. No reconciliation attempted. Next pass: re-locate the docs
  pricing surface before re-asserting the conflict.
- **C37 — Freestyle Pro fee: UNVERIFIED, carried.** freestyle.sh/pricing
  shows Free/Hobby/Pro tiers with usage rates and limits but no dollar
  fees; FAQ reveals Hobby = $50/mo commitment example; Pro fee still
  nowhere public. Dashboard-signed-in check still owed.
- **C36 Google Agent Substrate — VERIFIED NO-CHANGE** (baseline
  allowlist sentence verbatim). **C41 Alibaba FC Agent Sandbox —
  VERIFIED NO-CHANGE** (HEAD pin 39b6c3a unchanged, all values match).
  **C43 Gemini Agent Environment — VERIFIED NO-CHANGE** (baseline lead
  verbatim, still preview). **C44 Computer Use + Shell sandboxes GA —
  VERIFIED NO-CHANGE** (Sept 9 GA entry intact, newest release-notes
  entry Sept 22).
- **boat.dev product-news surface — VERIFIED absent; retry retired.**
  Third attempt: docs.boat.dev root has no blog/changelog nav
  (sections: Pricing, Build a platform, Environments, Long-running
  tasks, Accounts & sign-in, API & SDKs); boat.dev homepage has no
  blog links; `site:` queries returned nothing. Status moves
  UNVERIFIED ×2 → **VERIFIED absent**: the vendor simply has no
  product-news surface on its public site. The carried retry ask is
  retired (three attempts exhausted); future passes need not re-probe.
- **Tensorlake (C46) — VERIFIED NO-CHANGE.** No news dated
  2026-09-24; latest remains the July 2026 beehiiv product update.
- Vercel Drives not re-checked (P49 once-daily morning cadence stands).

## 3. In-lane news scan

- **C45 garnish — THIRD-PARTY dated corroboration of the Docker GA
  venue.** The Register published dated **2026-09-24** coverage of the
  Docker Cloud Sandboxes launch (THIRD-PARTY,
  https://www.theregister.com/ai-and-ml/2026/09/24/dockers-new-sandboxes-aim-to-contain-ai-agents-for-real/5298964):
  hosted microVM sandboxes announced at the WeAreDevelopers
  Conference, billed by the second, **Micro (1 vCPU/2 GB) $0.07/hr →
  XL (16 vCPU/32 GB) $1.12/hr** — corroborating Docker's own blog
  figures value-for-value — plus the Kits spec becoming standard OCI
  images. The corpus's C45 venue garnish gets a dated-press
  corroboration line; no new pricing claims (press matches vendor).
- **Adjacent color — Baseten/Blaxel continuity analysis (~Sept 23,
  THIRD-PARTY, beri.net).** The underlying acquisition is dated
  Sept 10 (not new — stays adjacent). The fresh part is beri.net's
  analysis with a Sept-24-dated pricing comparison (~$0.17/hr for
  2 vCPU/4 GB across Blaxel/E2B/Daytona). THIRD-PARTY analysis, not a
  vendor move — recorded as adjacent color, no corpus fold.
- Nothing else dated 2026-09-24 in-lane (Daytona, E2B, Modal, Vercel,
  hyperscalers, TermSquad, AgentComputer — all quiet).

## 4. Carried to the next pass

- Freestyle Pro's exact own-page fee (dashboard-signed-in check); C26
  continued monitoring (re-locate the docs pricing subpage first);
  OpenAI Agents API GA check; Vercel Drives (P49 morning cadence).
- boat.dev product-news retry: RETIRED — VERIFIED absent (3 attempts).
