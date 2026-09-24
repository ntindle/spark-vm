# Competitor watch — 2026-09-24 (midday)

Delta-only update against the morning pass
(`docs/COMPETITOR_WATCH_2026-09-24_MORNING.md`). Survey window
**2026-09-24 ~05:54–06:10 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set plus the Vercel Drives GA watch and C36's GKE terms
re-verification; (B) the owed follow-ups — the YC 301-redirect
citation, the Boat EU-only geography re-check, the deprecated-row
sunset-convention question — plus an open-web in-lane news scan.
Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-0554.md`), not the repo.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) or company-issued announcement — a stricter claim than
VERIFIED, used only when we fetched the thing itself. **THIRD-PARTY** =
reported by press/third-party sources, including vendor-announcement text
read on a syndicated copy rather than the vendor's own page.
**snippet-only** = a THIRD-PARTY sub-state: seen only via search
snippet or aggregator digest this run, not fetched and read — no
stronger claim than its source's blurb. **INFERRED** = my
characterization, labeled as such. **UNVERIFIABLE** = no public source
exists to check against. **UNVERIFIED** = a public page exists but
could not be fetched this run (never reported as NO-CHANGE).
**VERIFIED absent** = the vendor's own page was read this run and the
item is confirmed not present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

All reads within the survey window (~05:56–06:02 CDT); all values below
VERIFIED on the vendor's own page. Zero fetch failures — nothing labeled
UNVERIFIED. The **tenth full quiet 8/8 re-read pass since the
mid-afternoon fold**; values match the morning pass exactly.

- **Daytona** — VERIFIED NO-CHANGE: changelog still topped by
  **SEP 23 2026 / V0.216.0** ("Confine Dockerfile COPY sources to the
  build context" — Python, Ruby, TypeScript SDKs); next entry below is
  SEP 22 / V0.215.0. No new entry today.
  (https://www.daytona.io/changelog)
- **Docker Sandboxes** — VERIFIED NO-CHANGE: release notes still top out
  **2026-09-21** (v3 kits: OCI-based packages combining an agent
  workload with reusable mixins for tools, configuration, credentials,
  network access, and agent instructions); nothing dated 09-22/09-23/09-24.
  (https://docs.docker.com/ai/sandboxes/release-notes/)
- **Microsandbox** — VERIFIED NO-CHANGE: top release still **v0.7.1**
  ("chore(release): bump microsandbox to 0.7.1", #1597; explicit guest
  filesystem flush policies); next release below is v0.7.0.
  (https://github.com/superradcompany/microsandbox/releases)
- **E2B** — VERIFIED NO-CHANGE: tiers unchanged (Hobby free with $100
  one-time credit / sessions up to 1 hour / 20 concurrent sandboxes;
  Pro $150/month / 24-hour sessions, 100 concurrent sandboxes
  expandable to 1,100; per-second table $0.000014/s for 1 vCPU).
  (https://e2b.dev/pricing)
- **boat.dev (Boat)** — VERIFIED NO-CHANGE: rate table unchanged (small
  $0.018 / default $0.036 / large $0.072 / xlarge $0.200 per sandbox
  hour; per-second billing, stopped sandboxes free; 25 free trial
  hours); comparison and plan tables unchanged.
  (https://docs.boat.dev/pricing)
- **TermSquad** — VERIFIED NO-CHANGE: plan table unchanged (Starter
  $9/mo 2 vCPU/4 GB/40 GB NVMe; Builder $19/mo 4 vCPU/8 GB/75 GB;
  Power $29/mo 6 vCPU/12 GB/100 GB; Ultra $49/mo 8 vCPU/24 GB/200 GB).
  (https://termsquad.com/)
- **AgentComputer** — VERIFIED NO-CHANGE: pay-as-you-go table unchanged
  ($0.07/CPU-hour, $0.04375/GB-hour, hot storage $0.000683/GB-hour
  running, cold storage $0.000027/GB-hour stopped).
  (https://www.agentcomputer.ai/pricing)
- **DigitalOcean Managed Agents** — VERIFIED NO-CHANGE: pricing docs
  sub-page stamp still **"Last verified 22 Sep 2026"**; CPU
  $0.044/vCPU-hour, memory $0.0095/GB-hour, session storage
  $0.05/GiB-month; snapshots/checkpoints $0.05/GiB-month; BYOT
  $0.05/GiB-month; egress $0.01/GiB; shapes mars-1vcpu-1gb–mars-16vcpu-32gb.
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/)

## 2. Carried asks

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (21st consecutive
  no-change pass).** Pricing page VERIFIED
  (https://vercel.com/docs/sandbox/pricing): `last_updated` still
  **2026-09-10**; all values match baseline (Drive Storage
  $0.05/GB-month; Reads $0.0015/GB; Writes $0.004/GB; up to 4 drives
  per sandbox, 1 TiB default / 1 GiB Hobby, 16 TiB max; downloads free;
  session caps 45min/24h; concurrency 10/10,000). Changelog read this
  run (https://vercel.com/changelog): the "Drives for Vercel Sandbox
  are now in public beta" entry still carries its **2026-09-23 date**
  (the beta announcement surfacing as a re-dated entry — the INFERRED
  characterization stands across six passes); the newest 2026-09-24
  entry remains adjacent, not in-lane. **Still public beta, NOT GA** —
  no GA move, no fold.
- **C36 Google Agent Substrate — VERIFIED unchanged this pass.**
  The Google Cloud blog (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  carries the standing terms verbatim: *"Agent Substrate is open source
  and available to all GKE customers for non-production workloads. GA
  support for production is available via allowlist."* No new datapoints.
- **C41 Alibaba FC Agent Sandbox billing — VERIFIED unchanged.**
  Both aliyun-fc/fc-docs pages re-read at HEAD this run: the
  announcement (Eco/Std/Pro pay-as-you-go from 2026-07-31 00:00
  UTC+8; three editions; existing E2B-SDK instances auto-transitioned
  to Pro) and the pay-as-you-go pricing (invite-only preview;
  active/light/deep hibernation states; 15 GiB disk free allowance on
  active + light hibernation; Eco 0.00936/vCPU-h + 0.004608/GiB-h,
  Std 0.01224/0.006012, Pro 0.01872/0.009360; disk 0.00031896
  mainland / 0.00025308 outside USD/GiB-h; 2 vCPU / 4 GiB / 15 GiB Eco
  active 1h = $0.037152) all match the morning fold value-for-value.
  No re-fold.

## 3. Owed follow-ups — closed this pass

- **YC 301-redirect citation — CLOSED.** VERIFIED via curl HEAD this
  run: `ycombinator.com/companies/ascii` → **301** →
  `ycombinator.com/companies/boat` (200, live Boat page titled "Boat:
  The best cloud VMs for billions of agents | Y Combinator"; body
  carries Ascii/ascii mentions consistent with a recorded former
  name). This is close to VENDOR-ATTESTED for the slug-rename claim
  (YC's own redirect infrastructure), so the 301 joins the C40
  provenance as a harder citation for "ASCII is Boat"; the exact
  2026-09-17 date still rests on the yc-oss mirror changelog, so the
  morning's medium-high confidence on the date stands. Corpus action:
  the 301 is added to the C40 provenance note in
  `docs/COMPETITOR_ANALYSIS.md` (see §4 of this pass for the corpus
  action: both Boat rows).
- **Boat EU-only geography — VERIFIED still EU-only.**
  https://docs.boat.dev/faq.md, "Regions and trust" → "Where do
  sandboxes run?": *"In the EU: Germany, Finland, and France. Your
  data and snapshots stay there."* The corpus's tracked-set Boat row
  annotation "EU-only DE/FI/FR (FAQ)" remains accurate; no change to
  fold. (`docs.boat.dev/regions` is a 404 — the FAQ is the canonical
  region statement. The adjacent "Is EU latency a problem from the US
  or Latin America?" accordion — 100–200 ms round trips — confirms
  EU-only is an intentional, advertised posture.)
- **Deprecated-row sunset convention — recommendation recorded,
  NOT codified.** The corpus's only deprecated row is C40 (created
  this morning); no prior-removal precedent exists and no sunset rule
  is written anywhere. Proposed codification, pending corpus-owner
  approval (not adopted unilaterally): a dedup-marked row is retained
  for 14 watch passes (~2 days at hourly cadence) after its
  deprecation date for provenance, then removed with the removal noted
  in that day's watch doc. Seeded as an open item for the next watch
  pass or a corpus owner.

## 4. Corpus actions

1. **C40 provenance hardening (folded):** the YC 301
   (`/companies/ascii` → 301 → `/companies/boat`) is added to both
   the tracked-set Boat row's rename narrative and the C40
   DEPRECATED ROW provenance note in `docs/COMPETITOR_ANALYSIS.md` —
   harder evidence for the rename than the YC page copy alone. No
   other corpus rows touched this pass.
2. **No new C-numbers.** No launches, GA moves, pricing moves, or
   funding dated 2026-09-23/24 in-lane this pass.

No other in-window launches, GA moves, funding, or pricing moves dated
2026-09-24.

## 5. In-lane and adjacent news scan (2026-09-23/24, all THIRD-PARTY)

**No new in-lane sandbox-infra items this pass.** Four targeted
searches (news + web, launches/funding/pricing angles across the full
in-lane set plus generic "agent sandbox announced this week" and
"sandbox startup raises series A") returned nothing genuinely new in
agent-VM/sandbox infra for 9/23–24. Deliberately dropped as
out-of-window, out-of-lane, or stale: DO Managed Agents syndicated
launch coverage (dated 9/22, already dropped by the predawn pass);
OpenAI Agents API public beta (9/10) + billing explainer (9/19);
openma-ai / Open Managed Agents (GitHub, ~9/18, adjacent OSS agent
platform); agentOS / Rivet (31 days old); gpu-cli/vz
agent-sandbox-api-landscape (10 days old); Upstash "AI Agent Sandboxes
Compared" (9/17, comparison piece — its THIRD-PARTY
snippet-only claim that Daytona's OSS repo is "unmaintained since
June 2026" is recorded here, not verified); funding adjacency —
Geordie AI $30M Series A (agent cybersecurity, not sandbox infra),
Arga $10M seed (sandbox testing/twins, 28 days old), E2B $21M (Jul
2025), Workato Developer Sandbox (2025), Linq $20M Series A. None
in-lane, none in-window.

## 6. Verdict

**Tenth full quiet 8/8 tracked-set pass since the mid-afternoon fold,
three owed follow-ups closed.** The core is quiet; the Drives beta
streak extends to 21 passes; C36 unchanged; C41 unchanged. The YC
301 — `/companies/ascii` redirecting to `/companies/boat` — hardens
the C40 rename provenance from THIRD-PARTY company-page copy to a
redirect the vendor's accelerator serves itself. The sunset
convention for deprecated rows is proposed but deliberately not
codified unilaterally. Nothing else moved: no launches, no GA moves,
no pricing moves dated 2026-09-24.
