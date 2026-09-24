# Competitor watch — 2026-09-24 (late afternoon)

Delta-only update against the mid-afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-24_MID_AFTERNOON.md`). Survey window
**2026-09-24 ~15:56–16:20 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set; (B) the carried asks (C36/C41/C43/C44 re-verifications
+ OpenAI Agents API GA check + C45 follow-ups + Vercel Drives
opportunistic re-read), the queued trends, plus an open-web in-lane
news scan. Surveyor captures live in the loop's `agent_notes/`
workspace (`surveyor-a/b-20260924-1554.md`), not the repo.

Evidence labels used by the watch passes: **VERIFIED** = read on a
vendor's own page, doc, or repo this run. **VENDOR-VERIFIED** =
confirmed on the vendor's own page, docs, or changelog read this run
(corpus field-table usage). **THIRD-PARTY** = press/third-party
sources. **snippet-only** = seen only via search snippet. **INFERRED** =
my characterization. **UNVERIFIED** = a public page exists but could not
be fetched this run (never reported as NO-CHANGE). **VERIFIED absent** =
the vendor's own page was read this run and the item is confirmed not
present on it.

## 1. The tracked set — 7/8 VERIFIED NO-CHANGE, one UNVERIFIED

No tracked surface moved this pass: zero pricing or feature deltas in
the window. Seven of eight read clean on the vendors' own pages;
DigitalOcean's pricing page could not be fetched, so it is not claimed
as no-change.

- **Daytona — VERIFIED NO-CHANGE.** Changelog
  (https://www.daytona.io/changelog) still topped by the SEP 24 entries
  V0.216.1 (API key organization ID + CLI update warning fix) +
  V0.216.2 (CLI login through WorkOS), then SEP 23 / V0.216.0. No
  V0.216.3+ follow-ups.
- **Docker Sandboxes — VERIFIED NO-CHANGE.** Release notes
  (https://docs.docker.com/ai/sandboxes/release-notes/) still top out
  **2026-09-21** (v3 kits); next entry 2026-09-15. Nothing dated
  09-22/09-23/09-24.
- **Microsandbox — VERIFIED NO-CHANGE.** Releases
  (https://github.com/superradcompany/microsandbox/releases) still top
  out **v0.7.3** ("chore: release v0.7.3 by @toksdotdev in #1646";
  changelog "v0.7.2...v0.7.3"), with v0.7.1 immediately below. No
  v0.7.4+.
- **E2B — VERIFIED NO-CHANGE.** Pricing (https://e2b.dev/pricing):
  Hobby FREE $100 one-time credit / 1h sessions / 20 concurrent; Pro
  $150/mo / 24h sessions / 100 concurrent (expandable to 1,100);
  per-second table $0.000014/s for 1 vCPU. All match.
- **boat.dev (Boat) — VERIFIED NO-CHANGE.** Pricing
  (https://docs.boat.dev/pricing): small $0.018 / default $0.036 /
  large $0.072 / xlarge $0.200 per sandbox hour; per-second billing;
  stopped sandboxes free; 25 free trial hours — all match. EU geography
  line re-VERIFIED verbatim on https://boat.dev/ ("Germany, Finland,
  and France").
- **TermSquad — VERIFIED NO-CHANGE.** Plan table
  (https://termsquad.com/): Starter $9/mo 2 vCPU/4 GB/40 GB SSD NVMe;
  Builder $19/mo 4 vCPU/8 GB/75 GB; Power $29/mo 6 vCPU/12 GB/100 GB;
  Ultra $49/mo 8 vCPU/24 GB/200 GB. All match.
- **AgentComputer — VERIFIED NO-CHANGE.** Pricing
  (https://www.agentcomputer.ai/pricing): $0.07/CPU-hour,
  $0.04375/GB-hour, hot storage $0.000683/GB-hour (running), cold
  storage $0.000027/GB-hour (stopped); Enterprise tier present. All
  match.
- **DigitalOcean Managed Agents — UNVERIFIED this pass.** The owed
  re-check of the vendor pricing stamp ("Last verified 22 Sep 2026":
  $0.044/vCPU-hour active CPU, $0.0095/GB-hour memory,
  $0.005/GiB-month snapshots) could not close: the vendor product doc
  (docs.digitalocean.com/products/managed-agents/) **did** fetch this
  run — resolving the mid-afternoon fetch failure — and carries DO's
  own *"Last verified 21 Sep 2026"* freshness line, but it carries no
  pricing, and the vendor pricing subpage fetch failed again this run.
  DO's own 9/22 investor release (THIRD-PARTY under the corpus rules)
  still lists the same values — no move indicated, but no-change is
  not claimed per the evidence rules. **The stamp re-check carries to
  the next pass.**

## 2. Carried asks — C36, C41, C43, C44 all unchanged; no OpenAI GA

- **C36 Google Agent Substrate — VERIFIED unchanged.** The Google
  Cloud blog
  (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  carries the standing terms verbatim: *"Agent Substrate is open source
  and available to all GKE customers for non-production workloads. GA
  support for production is available via allowlist."*
- **C41 Alibaba FC Agent Sandbox — VERIFIED unchanged.** Pinned HEAD
  `39b6c3a` matches; every folded value matches value-for-value; the
  snapshot-pricing formula re-specified verbatim (*Snapshot Storage
  Usage = Memory Specification × 2 + Disk Specification*, charged at
  Disk Unit Price × storage duration). One garnish this pass: the
  vendor page specifies that the **15 GiB free disk allowance does not
  apply in deep hibernation** (VERIFIED on the vendor page) — folded
  into the C41 field-table row (see §5, corpus action 1).
- **C43 Google Gemini Agent Environment — VERIFIED unchanged.** The
  vendor's own Gemini API docs
  (https://ai.google.dev/gemini-api/docs/agent-environment) still
  carry the folded surface verbatim; footer still: *"Preview status:
  Environments and managed agents are in preview."* No GA move.
- **C44 Google Gemini Enterprise Agent Platform — VERIFIED
  unchanged.** The vendor's own release notes still top September 22,
  2026; the September 09, 2026 GA entry stands verbatim. No Sept
  23–24 entries.
- **OpenAI Agents API — still public beta, no GA (VENDOR-VERIFIED,
  GA VERIFIED absent).** Direct read of OpenAI's own changelog: the
  Sep 10 entry still reads *"Released the Agents API in public beta"*.
  Still no GA move.
- **C45 Docker Cloud Sandboxes — no new moves since the fold.** The
  local release notes still top 2026-09-21; the vendor launch blog
  corroborates all folded values (PAYG per-second billing, paused
  free, $250 limited-time credit, sbx 0.45.1+, sessions 1h default /
  24h max, separate local/cloud secrets & policies). Launch-day press
  (GlobeNewswire, adtmag, The Register) adds nothing beyond the
  folded launch.
- **Vercel Drives — opportunistic re-check: still public beta
  (VERIFIED, no-change).** The pricing page's `last_updated:
  2026-09-10` has not moved; Drives still public beta. Per the P49
  decision the GA watch proper stays once-daily on the morning pass;
  this read was opportunistic, not the daily check.

## 3. Queued trends — all hold, none move in-lane

- **"Agentic cloud" two-vendor framing — STAYS QUEUED (adjacent).**
  No new vendor-issued sandbox sign-up surfaces for Alibaba "Agent
  Native Cloud" or Huawei "Open Agentic Cloud" surfaced this run.
  Framing-level only; no C-number.
- **Tencent Cloud DataBuddy (Sept 22) — stays adjacent-watch.** No
  new vendor-issued sandbox sign-up surface confirmed.
- **Deprecated-row sunset convention — still proposed-not-codified.**
  No new deprecated-row activity (C40 ~9 passes into the proposed
  14-pass retention). Not codified unilaterally — pending corpus-owner
  approval.
- Evening-pass vetting holds: namesake-collision warning stands
  (Guava's "Daytona" voice model is unrelated to Daytona sandboxes).

## 4. News scan — no in-lane launches dated 2026-09-24

No new agent-VM / sandbox / hosted-agent-infra launches, pricing
moves, or funding dated 2026-09-24. Adjacent color only, no folds:
Darktrace Signal Labs launch (9/24), DeepSeek DSec training-infra
paper coverage (9/24), Baz Planner + $17M extended seed (agentic
code review, not a provider). Name-collision noise (vm2 CVEs,
OpenShift docs, "megh" self-hosted repo) declined — no verifiable
vendor surface.

## 5. Corpus actions

1. **C41 deep-hibernation garnish.** The vendor page specifies the 15
   GiB free disk allowance does not apply in deep hibernation
   (VERIFIED on the vendor page this run). Folded as a one-line
   caveat in the C41 field-table row; no other row change. Recorded in
   the "Watch update — 2026-09-24 (late afternoon)" corpus section
   per the C32/C37/C38/C39/C40/C41/C42/C43/C44/C45 precedents.
2. **No other corpus changes.** Tracked set 7/8 quiet + 1
   UNVERIFIED; C36/C43/C44 unchanged; OpenAI Agents API stays public
   beta (VENDOR-VERIFIED); C45 no new moves; deprecated-row sunset
   convention still proposed-not-codified.

## 6. Corpus actions carried forward

- Next passes: routine tracked-set re-reads; C36/C41/C43/C44
  re-verify; **DigitalOcean "Last verified 22 Sep 2026" pricing-stamp
  re-check** (vendor product doc fetched this run but carries no
  pricing; pricing subpage fetch failed — owed, not carried on a
  streak); the "agentic cloud" framing trend stays queued; Tencent
  DataBuddy stays adjacent-watch; deprecated-row sunset convention
  still proposed-not-codified.
- Morning pass: Vercel Drives GA watch (daily, per P49).

---

Surveyed 2026-09-24 ~15:56–16:20 CDT. Tracked set: 7/8 VERIFIED
NO-CHANGE, one UNVERIFIED (DigitalOcean pricing — vendor product doc
fetched but carries no pricing; stamp re-check owed next pass).
**Corpus fold:** one C41 garnish (15 GiB free disk allowance does not
apply in deep hibernation — VERIFIED on the vendor page). C36/C43/C44
unchanged; OpenAI Agents API still public beta (VENDOR-VERIFIED, GA
VERIFIED absent); C45 Docker Cloud Sandboxes no new moves; Vercel
Drives still public beta (opportunistic re-check — daily watch stays
on the morning pass). News scan: no in-lane launches, pricing moves,
or funding dated 9/24.
