# Competitor watch — 2026-09-23 (late overnight)

Delta-only update against the overnight pass
(`docs/COMPETITOR_WATCH_2026-09-23_OVERNIGHT.md`). Survey window
**2026-09-23 ~23:55–00:10 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set, (B) Vercel Drives GA watch, a Boxd rate-card
re-verification plus quickstart re-read, an Automaid own-page re-read
(VERIFIED this run — the overnight pass's lane-drift closure stands),
a C36 re-check, and an open-web market-news scan. Surveyor
captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260923-2354.md`), not the repo.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) rather than a vendor doc-page assertion — a stricter claim
than VERIFIED, used only when we fetched the thing itself.
**THIRD-PARTY** = reported by press/third-party sources, including
vendor-announcement text read on a syndicated copy (e.g. a Business
Wire release) rather than the vendor's own page.
**snippet-only** = a THIRD-PARTY sub-state: seen only via search
snippet or aggregator digest this run, not fetched and read — no
stronger claim than its source's blurb.
**INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.
**UNVERIFIED** = a public page exists but could not be fetched this
run (never reported as NO-CHANGE).

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

All reads within the survey window (~23:55–23:58 CDT); all values below
VERIFIED on the vendor's own page. Zero fetch failures — nothing labeled
UNVERIFIED. The **sixth full quiet 8/8 re-read pass since the
mid-afternoon fold**; values match the overnight pass exactly.

- **Daytona** — VERIFIED NO-CHANGE: changelog still topped by
  **SEP 23 2026 / V0.216.0** ("Confine Dockerfile COPY sources to the
  build context" — Python, Ruby, TypeScript SDKs); no new entry today.
  (https://www.daytona.io/changelog)
- **Docker Sandboxes** — VERIFIED NO-CHANGE: release notes still top out
  **2026-09-21** (v3 kits: OCI-based packages combining an agent
  workload with reusable mixins for tools, configuration, credentials,
  network access, and agent instructions); nothing dated 09-22/09-23.
  (https://docs.docker.com/ai/sandboxes/release-notes/)
- **Microsandbox** — VERIFIED NO-CHANGE: top release still **v0.7.1**
  (npm provenance + guest filesystem flush-policy patch series).
  (https://github.com/superradcompany/microsandbox/releases)
- **E2B** — VERIFIED NO-CHANGE: pricing tiers unchanged (Hobby free with
  $100 one-time credit / sessions up to 1 hour; Pro $150/month /
  24-hour sessions, 100 concurrent sandboxes expandable to 1,100;
  per-second table $0.000014/s).
  (https://e2b.dev/pricing)
- **boat.dev** — VERIFIED NO-CHANGE: rate table unchanged (small
  $0.018 / default $0.036 / large $0.072 / xlarge $0.200 per sandbox
  hour; per-second billing, stopped sandboxes free; 25 free trial
  hours); comparison table unchanged.
  (https://docs.boat.dev/pricing)
- **TermSquad** — VERIFIED NO-CHANGE: plan table unchanged (Starter
  $9/mo 2 vCPU/4 GB/40 GB … Ultra $49/mo 8 vCPU/24 GB/200 GB; BYOK FAQ
  unchanged).
  (https://termsquad.com/)
- **AgentComputer** — VERIFIED NO-CHANGE: pay-as-you-go table unchanged
  ($0.07/CPU-hour, $0.04375/GB-hour, hot storage $0.000683/GB-hour
  running, cold $0.000027/GB-hour stopped).
  (https://www.agentcomputer.ai/pricing)
- **DigitalOcean Managed Agents** — VERIFIED NO-CHANGE: pricing docs
  sub-page stamp still **"Last verified 22 Sep 2026"**; CPU
  $0.044/vCPU-hour, memory $0.0095/GB-hour, session storage
  $0.05/GiB-month; snapshots/checkpoints $0.05/GiB-month (the
  mid-evening C26 resolution stands — read live again this pass);
  active-CPU-billing footnote intact; BYOT $0.05/GiB-month; egress
  $0.01/GiB; shapes mars-1vcpu-1gb–mars-16vcpu-32gb.
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/)

## 2. Carried asks

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (17th consecutive
  no-change pass).** Pricing page VERIFIED
  (https://vercel.com/docs/sandbox/pricing): `last_updated` still
  **2026-09-10**; all values match baseline (Drive Storage
  $0.05/GB-month; Reads $0.0015/GB; Writes $0.004/GB; up to 4 drives
  per sandbox, 1 TiB default / 1 GiB Hobby, 16 TiB max; downloads free;
  session caps 45min/24h; concurrency 10/10,000). Changelog read this
  run (https://vercel.com/changelog): the "Drives for Vercel Sandbox
  are now in public beta" entry carries a **2026-09-23 date** on the
  changelog — this is, **INFERRED**, the beta announcement surfacing as
  a re-dated entry, consistent with the date-flip/re-publish pattern
  documented across the 09-22→09-23 passes (the overnight pass already
  read the entry as the latest Drives-status statement). **Still public
  beta, NOT GA** — no GA move, no fold. Other 09-23 changelog entries
  are adjacent, not in-lane (unlimited Blob stores, Gemini 3.8 TTS on
  AI Gateway); one 09-24-dated entry (TanStack AI Auth — outside the
  09-23 window; adjacent, not in-lane).
  (https://vercel.com/changelog/drives-for-vercel-sandbox-are-now-in-public-beta)
- **Boxd (C29) — rate card re-verified VERIFIED on boxd.sh this pass.**
  The pricing FAQ fetched clean and confirms the four numbers verbatim:
  **€0.049/vCPU-hour** while running, **€0.015/GiB-hour** of resident
  RAM (running or standby), **€0.0001/GiB-hour** of disk actually
  written, **€30 free credits** for every new account
  (https://boxd.sh). This is a re-verification of the overnight pass's
  fold — the fold stands, no new fold. docs.boxd.sh/quickstart re-read:
  no product changes. Funding datapoint: €2M pre-seed (2026-09-21,
  led by BlueYard Capital, with OVNI, Antler, S20, Script Capital —
  **THIRD-PARTY**) — dedupe, already recorded under C29.
- **C36 Google Agent Substrate — no new vendor or press datapoints
  since the 16:00 CDT vendor-confirm fold; allowlist-only production
  GA stands.**
- **Automaid — own-page read re-confirmed VERIFIED this pass**
  (https://automaid.it.com — "AI agents for recurring work",
  workflow-automation SaaS — NOT an "AI hub"). The overnight pass's
  lane-drift closure stands; off the watch list, no further attempts.

## 3. In-lane news scan

- **New in-window item — Simular "Sai" GA, 2026-09-23
  (THIRD-PARTY, redshiftdaily).** A computer-use agent, GA'd with a
  fleet model (up to 100 machines), running on Simular-provisioned
  cloud VMs or the user's own device, Win/Mac/Linux. This is the
  agent-on-cloud-VM packaging adjacent to the hosted-product thesis —
  watch-list candidate, NOT a corpus entry: vendor verification of the
  GA announcement is owed before any C-number.
- **No other in-window launches, GA moves, funding, or pricing moves
  dated 2026-09-23.** Tencent Cloud DataBuddy stays adjacent:
  confirmed a data-workbench (its "Agent Runtime" is governed data
  agents), not VM-for-agents. No brand-new VM-for-agents entrants.
- Newcomer candidates still unvetted against primary sources: Ascii
  Box, Namespace, Beam.

## 4. Fold decision

None this pass. Per the C35 close-only precedent, the re-verifications
(#322's C29/C37/C38 folds, the Automaid closure, the Drives
date-flip) close or confirm without folding; per the C32
primary-source-verification rule, the Simular Sai item stays out of
the corpus until a vendor page is read. Nothing changed on a primary
source.

## 5. Verdict

**Quiet at the core, one live wire in the margins.** Sixth full quiet
8/8 tracked-set pass since the mid-afternoon fold; 17th consecutive
quiet Vercel Drives pass (beta re-dated on the changelog, not GA);
Boxd's rate card re-verified (the overnight fold stands); C36 and the
Automaid closure unchanged. The one new item is Simular's "Sai"
computer-use agent GA on cloud VMs (THIRD-PARTY — vendor verification
owed). No other in-lane launches, GA moves, funding, or pricing moves
dated 2026-09-23.

## Next-pass asks

- Routine tracked-set re-reads; Vercel Drives GA watch (18th pass).
- Simular Sai: vendor-page verification of the GA announcement
  (C-number decision); watch for pricing.
- Vet the remaining newcomer candidates (Ascii Box, Namespace, Beam)
  against primary sources before any tracked-set consideration.
- Read Freestyle's own pricing page (own-page verification of the
  THIRD-PARTY rates); watch Tensorlake for published pricing.
- C36: vendor-page verification of the GKE offering terms (standing ask).
- Date the E2B $21M Series A (vestbee, Insight Partners lead) if a
  dated source exists.
