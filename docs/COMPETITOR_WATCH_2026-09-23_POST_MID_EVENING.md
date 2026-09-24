# Competitor watch — 2026-09-23 (post-mid-evening)

Delta-only update against the mid-evening pass
(`docs/COMPETITOR_WATCH_2026-09-23_MID_EVENING.md`). Survey window
**2026-09-23 ~18:56–19:15 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set, (B) Vercel Drives GA watch plus Boxd/C36/Automaid checks
plus an open-web market-news scan. Surveyor captures live in the loop's
`agent_notes/` workspace (`surveyor-a/b-20260923-1854.md`), not the repo.

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

All reads within the survey window; all values below VERIFIED on the
vendor's own page. No fetch failures this pass — nothing labeled
UNVERIFIED. Mid-evening's C26 figures carry forward unchanged (DO page
stamp still "Last verified 22 Sep 2026"; snapshots/checkpoints
$0.05/GiB-month; active-CPU-billing footnote intact).

- **Daytona** — VERIFIED NO-CHANGE: changelog still topped by
  **SEP 23 2026 / V0.216.0** ("Confine Dockerfile COPY sources to the
  build context" — Python, Ruby, TypeScript SDKs); no new entry today.
  (https://www.daytona.io/changelog)
- **Docker Sandboxes** — VERIFIED NO-CHANGE: release notes still top out
  **2026-09-21** (v3 kits: OCI-based packages combining an agent
  workload with reusable mixins for tools, configuration, credentials,
  network access, and agent instructions).
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
  hour (INFERRED phrasing — the vendor states per-second machine-time
  billing: "A stopped sandbox costs nothing"); 25 free trial hours).
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
  sub-page stamp still "Last verified 22 Sep 2026"; rate table
  unchanged (CPU $0.044/vCPU-hour, memory $0.0095/GB-hour, session
  storage $0.05/GiB-month; snapshots/checkpoints $0.05/GiB-month;
  active-CPU footnote: "Until then, you will be billed at 25% of the
  vCPUs allocated … Paused sessions incur no compute charges");
  BYOT $0.05/GiB-month; egress $0.01/GiB; shapes
  mars-1vcpu-1gb–mars-16vcpu-32gb.
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/)

## 2. Vercel Drives GA watch — NO-CHANGE (13th consecutive pass)

Pricing page VERIFIED (https://vercel.com/docs/sandbox/pricing):
`last_updated: 2026-09-10` (unchanged); the related-links block still
carries the entry title "Drives for Vercel Sandbox are now in public
beta" — no GA language anywhere on the page; rates and limits identical
to baseline. Changelog VERIFIED (https://vercel.com/changelog, full
read): newest entries dated **2026-09-22** (GPT-6 Sol/Luna and Claude
Opus 5.5 on AI Gateway); **no entries dated 2026-09-23**; nothing
mentioning Drives or Sandbox GA. Drives remain public beta.

## 3. Carried asks — all held

- **Boxd (C29)** — VERIFIED rate card unchanged on the vendor FAQ
  (verbatim): "€0.049 per vCPU-hour while a machine runs, €0.015 per
  GiB-hour of RAM it actually has resident while running or in standby,
  and €0.0001 per GiB-hour of disk you have written to" — "Every new
  account starts with €30 of free credits." (https://boxd.sh)
  docs.boxd.sh/quickstart re-read clean this pass — per the baseline
  doc's standing description (machines, forks in under 200 ms,
  snapshots, checkpoints, MCP server install, self-hosted), judged
  consistent with prior folds; no product changes visible this pass.
  No new funding or product announcements
  (`since=2026-09-01` — today's search surfaced only re-reportings of
  the €2M pre-seed, not new news).
- **Google Agent Substrate on GKE (C36)** — no new vendor or press
  datapoints since the 16:00 CDT vendor-confirm fold; the
  `since=2026-09-23` search surfaced only already-known items
  (itbrief.co.uk launch piece ~6 days old; a pre-window YouTube
  walkthrough of Google AX v0.3.0).
- **Automaid own-page verification — still owed, status hardened**: the
  domain is fetchable this run (first successful own-page fetch —
  https://automaid.it.com, "AI agents for recurring work"), but the
  site carries no launch announcement for the third-party-reported "AI
  hub" claim (itbrief.asia, aiagentstore.ai digest, afritechbizhub.com)
  and no press/blog section; `site:automaid.it.com` returned zero
  results. The third-party launch claim stays **UNVERIFIED** — the gap
  is now confirmed on a fetchable site rather than on a fetch failure,
  not a contradiction.

## 4. In-lane news scan — no launch / GA / funding / pricing move in-window

Open-web scan over ~18:00–19:20 CDT (`since=2026-09-23`): nothing new
in-lane. Results were all pre-window or already folded — DO Managed
Agents public preview (2026-09-22, already folded), Baseten × Blaxel
(already folded), OpenAI Agents API beta (already known), Cloudflare
× Cursor Cloud Agents (2026-09-02, pre-window). No tracked vendor
moved today.

One adjacent datapoint, pre-window (~1 day old, not in-lane):
**Tencent Cloud DataBuddy** (PRNewswire ~2026-09-22) — a fully-managed
agent-native Data + AI workbench with an "Agent Runtime layer" for
governance/auditability, marketed at data teams (Data Engineering /
Governance / Analytics / Data Science scenarios). Adjacent context
only — not VM-for-agents/sandbox infrastructure; not a corpus entry.

## Corpus fold

None this pass. Per the C32 primary-source-verification precedent,
corpus folds require a primary-source-verified change; per the C35
close-only precedent, no-drift verifications close without a fold. All
mid-evening folds stand unmodified.

## Next-pass asks

Routine tracked-set re-reads; Vercel Drives GA watch (14th pass);
Boxd (C29) watch; C36 datapoint scan; Automaid own-page verification;
Tencent DataBuddy lane-drift watch (any move toward
sandbox/VM-for-agents positioning would warrant a C-number).
