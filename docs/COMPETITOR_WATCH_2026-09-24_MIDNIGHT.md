# Competitor watch — 2026-09-24 (midnight)

Delta-only update against the late-overnight pass
(`docs/COMPETITOR_WATCH_2026-09-23_LATE_OVERNIGHT.md`). Survey window
**2026-09-24 ~00:56–01:05 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set plus the Vercel Drives GA watch, (B) the owed Simular
"Sai" vendor verification, newcomer vetting (Ascii Box, Namespace, Beam),
Freestyle's own pricing page, the Tensorlake pricing watch, C36's GKE
terms re-verification, dating the E2B Series A, and an open-web market-news
scan. Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-0054.md`), not the repo.

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

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

All reads within the survey window (~00:56–00:58 CDT); all values below
VERIFIED on the vendor's own page. Zero fetch failures — nothing labeled
UNVERIFIED. The **seventh full quiet 8/8 re-read pass since the
mid-afternoon fold**; values match the late-overnight pass exactly.

- **Daytona** — VERIFIED NO-CHANGE: changelog still topped by
  **SEP 23 2026 / V0.216.0** ("Confine Dockerfile COPY sources to the
  build context" — Python, Ruby, TypeScript SDKs); next entry below is
  SEP 22 / V0.215.0. No new entry today.
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
  hours).
  (https://docs.boat.dev/pricing)
- **TermSquad** — VERIFIED NO-CHANGE: plan table unchanged (Starter
  $9/mo 2 vCPU/4 GB/40 GB … Ultra $49/mo 8 vCPU/24 GB/200 GB).
  (https://termsquad.com/)
- **AgentComputer** — VERIFIED NO-CHANGE: pay-as-you-go table unchanged
  ($0.07/CPU-hour, $0.04375/GB-hour, hot storage $0.000683/GB-hour
  running, cold $0.000027/GB-hour stopped).
  (https://www.agentcomputer.ai/pricing)
- **DigitalOcean Managed Agents** — VERIFIED NO-CHANGE: pricing docs
  sub-page stamp still **"Last verified 22 Sep 2026"**; CPU
  $0.044/vCPU-hour, memory $0.0095/GB-hour, session storage
  $0.05/GiB-month; snapshots/checkpoints $0.05/GiB-month; BYOT
  $0.05/GiB-month; egress $0.01/GiB; shapes mars-1vcpu-1gb–mars-16vcpu-32gb.
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/)

## 2. Carried asks

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (18th consecutive
  no-change pass).** Pricing page VERIFIED
  (https://vercel.com/docs/sandbox/pricing): `last_updated` still
  **2026-09-10**; all values match baseline (Drive Storage
  $0.05/GB-month; Reads $0.0015/GB; Writes $0.004/GB; up to 4 drives
  per sandbox, 1 TiB default / 1 GiB Hobby, 16 TiB max; downloads free;
  session caps 45min/24h; concurrency 10/10,000). Changelog read this
  run (https://vercel.com/changelog): the "Drives for Vercel Sandbox
  are now in public beta" entry still carries its **2026-09-23 date**
  (the beta announcement surfacing as a re-dated entry — the INFERRED
  characterization stands across three passes); the only 2026-09-24
  entry is "TanStack AI Auth on Vercel Connect" — adjacent, not
  in-lane. **Still public beta, NOT GA** — no GA move, no fold.
  (https://vercel.com/changelog/drives-for-vercel-sandbox-are-now-in-public-beta)
- **C36 Google Agent Substrate — VERIFIED unchanged this pass.**
  The Google Cloud blog (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  confirms the standing terms: Agent Substrate is open source and
  available to all GKE customers for non-production workloads;
  **production GA remains allowlist-only**. No new datapoints.
- **Simular "Sai" GA — vendor verification CLOSED, folded as C39**
  (see §4). The 23:54 pass's owed item: own-page read of sai.work
  (VERIFIED) plus the company GA announcement datelined
  **September 23, 2026** (VENDOR-ATTESTED via company-issued release).
- **Freestyle (C37) boot claim — qualified.** The freestyle.sh homepage
  headline "A full Linux machine, ready in **65 ms**" is the marketing
  number (VERIFIED on the vendor homepage); the honest vendor number
  lives in the docs: "**p99s under 400ms**" (VERIFIED on
  freestyle.sh/docs). Corpus row updated; pricing stays THIRD-PARTY
  (own pricing page not found — likely behind dashboard / talk-to-us).
- **Tensorlake (C38) — pricing watch still open.** No published pricing
  page exists; the corpus fold stands.
- **E2B $21M Series A — dated: 2025-07-28**, Insight Partners lead
  (PRNewswire wire copy + SiliconANGLE's dated URL; total $32M per
  vestbee, THIRD-PARTY). Corpus E2B row updated.

## 3. In-lane and adjacent news scan (2026-09-23/24)

- **NEW corpus entry — C39 Simular "Sai" GA, 2026-09-23** (company
  press release; GA'd from invite-only). The computer-use agent turns
  "any computer — a private cloud VM or your own device — into a
  self-operating machine": persistent Simular-provisioned cloud VMs
  (Windows/Linux) or BYOD (Mac/Windows/Linux), autonomous operation of
  real interfaces, approval-gated critical actions, skills and
  schedulable saved workflows, fleet of up to 100 machines
  ("less than $1" per 100-machine run, vendor claim), neuro-symbolic
  compile-and-replay (≥90% token reduction on repeated tasks, vendor
  claim). **Pricing conflict unresolved:** simular.ai's own comparison
  page quotes $50/month pay-as-you-go and $500/month Sai Unlimited;
  dume.ai's THIRD-PARTY comparison attributes $20/$200/$500 tiers to
  sai.work — sai.work's own fetched pages carry no pricing table, so
  all pricing stays UNVERIFIED against the vendor's own pricing page.
  In-lane computer-use flavor (not dev-sandbox). See §4.
- **Modal in talks to raise at ~$15B valuation — Sept 23, 2026**
  (Bloomberg via Reuters, THIRD-PARTY); Modal raised $355M in May at
  $4.65B. In-lane-adjacent color for the sandbox pricing race, not a
  product move — no fold beyond the watch note.
- **Newcomer vetting — Ascii Box: IN-LANE candidate** (persistent
  full-Ubuntu cloud VM for agents: SSH, Docker, dedicated IPv4,
  60fps virtual desktop, disk-level snapshot forking, CLI; ~$500K
  raised; EU-only DE/FI/FR; all THIRD-PARTY — own-site verification
  still owed, not a corpus entry yet). **Namespace: adjacent**
  (development-optimized ephemeral compute, not agent-sandbox-first).
  **Beam: adjacent** (serverless GPU cloud with a sandbox feature —
  gVisor + runc, per-second billing; not VM-for-agents-first).
- **Adjacent only:** Outerlimit $16M pre-seed (9/22, THIRD-PARTY —
  zero-trust "agent action layer" authorization, security not VM);
  HeyBrain GA (9/23, snippet-only — governed knowledge workspace,
  not VM-for-agents). **Context:** OpenAI Agents API public beta
  (Sept 10 — partnership lane: Cloudflare, DigitalOcean, E2B, Modal,
  Oracle, Runloop, Vercel among 9 partner sandboxes).

## 4. Fold decision

Fold this pass, per the primary-source-verification and new-entry
precedents (C32, C37/C38):

1. **C39 new — Simular "Sai" (in-lane, computer-use fleet).**
2. **C37 qualification — Freestyle boot claim:** "65 ms" headline
   (marketing) vs **p99 <400ms** (docs, honest vendor number).
3. **E2B row — Series A dated 2025-07-28**, Insight Partners lead.
4. **Modal row — $15B raise talks (9/23, THIRD-PARTY)**, May $355M at
   $4.65B for context.

The sai.work GA announcement (9/23) is the only in-lane GA dated
today's window; it is folded, not open. No other in-window launches,
GA moves, funding, or pricing moves dated 2026-09-24.

## 5. Verdict

**Seventh full quiet 8/8 tracked-set pass since the mid-afternoon
fold, one overdue item closed.** The core is quiet; the Drives beta
streak extends to 18 passes. The owed Sai verification closed with a
real fold: C39 Simular "Sai" GA (9/23) enters the corpus as the
computer-use fleet archetype, with an unresolved pricing-source
conflict carried as UNVERIFIED debt. C37 gets an honest boot number;
the E2B Series A gets a date; Modal gets a valuation color. Next
pass: Ascii Box own-site verification, Tensorlake/Freestyle pricing
watch, Drives 19th pass.

## Next-pass asks

- Ascii Box: own-site verification of product, pricing, EU-only scope
  (in-lane candidate — corpus decision on verification).
- Tensorlake: published-pricing watch (remains open).
- Freestyle: own pricing page (dashboard path probe).
- Vercel Drives GA watch (19th pass).
- Simular Sai: own pricing page on sai.work (resolve the $50/$500 vs
  $20/$200/$500 conflict).
- C36: GKE production-GA allowlist watch (standing).
