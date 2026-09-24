# Competitor watch — 2026-09-24 (morning)

Delta-only update against the predawn pass
(`docs/COMPETITOR_WATCH_2026-09-24_PREDAWN.md`). Survey window
**2026-09-24 ~04:00–04:10 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set plus the Vercel Drives GA watch, C36's GKE terms
re-verification, and the wowza.com fetch check; (B) the owed
follow-ups — the ASCII/boat rebrand-link resolution, the Alibaba FC
Agent Sandbox billing verification — plus an open-web in-lane news
scan. Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-0354.md`), not the repo.

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

All reads within the survey window (~04:00–04:08 CDT); all values below
VERIFIED on the vendor's own page. Zero fetch failures — nothing labeled
UNVERIFIED. The **ninth full quiet 8/8 re-read pass since the
mid-afternoon fold**; values match the predawn pass exactly.

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
  (explicit guest filesystem flush policies).
  (https://github.com/superradcompany/microsandbox/releases)
- **E2B** — VERIFIED NO-CHANGE: pricing tiers unchanged (Hobby free with
  $100 one-time credit / sessions up to 1 hour; Pro $150/month /
  24-hour sessions, 100 concurrent sandboxes expandable to 1,100;
  per-second table $0.000014/s).
  (https://e2b.dev/pricing)
- **boat.dev (Boat)** — VERIFIED NO-CHANGE: rate table unchanged (small
  $0.018 / default $0.036 / large $0.072 / xlarge $0.200 per sandbox
  hour; per-second billing, stopped sandboxes free; 25 free trial
  hours). (https://docs.boat.dev/pricing)
- **TermSquad** — VERIFIED NO-CHANGE: plan table unchanged (Starter
  $9/mo 2 vCPU/4 GB/40 GB … Builder … Power … Ultra $49/mo 8 vCPU/24 GB/200 GB).
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

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (20th consecutive
  no-change pass).** Pricing page VERIFIED
  (https://vercel.com/docs/sandbox/pricing): `last_updated` still
  **2026-09-10**; all values match baseline (Drive Storage
  $0.05/GB-month; Reads $0.0015/GB; Writes $0.004/GB; up to 4 drives
  per sandbox, 1 TiB default / 1 GiB Hobby, 16 TiB max; downloads free;
  session caps 45min/24h; concurrency 10/10,000). Changelog read this
  run (https://vercel.com/changelog): the "Drives for Vercel Sandbox
  are now in public beta" entry still carries its **2026-09-23 date**
  (the beta announcement surfacing as a re-dated entry — the INFERRED
  characterization stands across five passes); the newest 2026-09-24
  entry is "Vercel Connect now supports TanStack AI" — adjacent, not
  in-lane. **Still public beta, NOT GA** — no GA move, no fold.
  (https://vercel.com/changelog/drives-for-vercel-sandbox-are-now-in-public-beta)
- **C36 Google Agent Substrate — VERIFIED unchanged this pass.**
  The Google Cloud blog (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  carries the standing terms verbatim: *"Agent Substrate is open source
  and available to all GKE customers for non-production workloads. GA
  support for production is available via allowlist."* No new datapoints.
- **wowza.com owed re-verification — CLOSED.** The homepage loaded
  cleanly this run (~04:08 CDT) — full content (hero, customer
  sections, Streaming Engine detail, G2 badge), no connection resets.
  The exclusion stays in the link-check config per the in-file rule
  (it covers runner-egress bot-blocks, a path condition, not the
  site's health); caveat stands that this is a server-side fetch, not a
  real interactive browser render.

## 3. Resolved: ASCII "boat" and boat.dev are the SAME PRODUCT

The predawn pass's owed item — resolve the INFERRED possible
rebrand/link between ASCII's "boat" (C40) and the tracked-set
boat.dev — is **resolved this pass, high confidence: ASCII renamed to
Boat on ~2026-09-17.** Evidence chain (surveyor B, adversarially checked):

- **VERIFIED (fetched this run):** `box.ascii.dev`, `boat.dev`, and
  `ascii.dev` all serve byte-identical product pages — same title
  "boat: Cheapest, Most Powerful Sandboxes for Agents", same $0.036/h
  (4 vCPU / 8 GB / 50 GB), same plans-from-$20/mo, same FAQ, all
  linking to `docs.boat.dev` (only asset hostnames differ). Three
  domains, one site — legacy aliases, not sister products.
- **THIRD-PARTY:** YC's own company page is now
  `ycombinator.com/companies/boat` ("Boat: The best cloud VMs for
  billions of agents"). (Labeled THIRD-PARTY: YC is the
  vendor's accelerator, not the vendor itself; the slug rename is
  evidenced by the yc-oss mirror below.)
- **THIRD-PARTY:** the yc-oss community mirror's changelog for
  **2026-09-17** records the rename explicitly — `name`: Ascii →
  Boat, `slug`: ascii → boat, `website`: box.ascii.dev → boat.dev,
  `former_names`: ["Ascii box","Ascii"]. The company's own X handle
  @asciidotdev now displays "ascii - boat (YC F26)" (snippet-only).

Adversarial caveat: no company-published blog post announcing the
rename was found this run — the date rests on the third-party YC
mirror. Confidence: **high** on "same product", **medium-high** on
the exact date. Corpus action (§4): C40's row is renamed to the
canonical **Boat**, the dedup is recorded, and the tracked-set
boat.dev row carries the rename provenance.

## 4. Fold decision

Fold this pass, per the primary-source-verification and new-entry
precedents (C32, C37/C38, C39, C40):

1. **C41 new — Alibaba Cloud FC Agent Sandbox billing (in-lane,
   task-scoped compute).** VERIFIED from aliyun-fc/fc-docs this run:
   new pay-as-you-go model rolling out from 2026-07-31 (UTC+8), still
   invite-only preview — formula = unit price × run duration,
   per-second billing, hourly settlement. Three editions: **Eco**
   (cheapest, occasional perf fluctuation, no hibernation —
   startups/tool-use validation), **Std** (+hibernation — enterprise
   copilots), **Pro** (+deep and shallow hibernation, millions of
   concurrent requests — RL sampling/high-concurrency agents).
   International-site unit prices (USD): Eco vCPU **0.00936**/vCPU-h,
   mem **0.004608**/GiB-h; Std 0.01224 / 0.006012; Pro 0.01872 /
   0.009360; disk 0.00031896/GiB-h (0.00025308 outside mainland
   China); worked example — 2 vCPU / 4 GiB / 15 GiB Eco active 1h =
   **$0.037152**. Hibernation math (VERIFIED): active = vCPU+mem+disk
   (15 GiB disk free); light hibernation (Pro only) = mem+disk,
   vCPU free; deep hibernation = vCPU+mem free, disk billed on
   (memory×2 + disk) GiB with no free allowance; FAQ: "call `kill()`
   when the task is complete." **Scope caveat (VERIFIED):** applies
   ONLY to E2B-SDK integration — existing E2B instances auto-upgrade
   to Pro; "Sandbox Functions"/"AgentRun Sandbox" customers must
   migrate. Lane characterization (INFERRED): task-scoped compute,
   **not** agent-VM-shaped — no SSH or Desktop surface in the Features
   index; closer to E2B/Daytona pause semantics than to a persistent
   dev VM.
2. **C40 update — dedup: ASCII "boat" IS Boat (rename resolved).**
   C40's field-table row is renamed to the canonical **Boat**
   (ASCII → Boat ~2026-09-17, YC F26; three legacy domains
   box.ascii.dev/boat.dev/ascii.dev serve one product; canonical
   domain now boat.dev). The C40 entry is **NOT** a second corpus
   provider — the tracked-set boat.dev entry and C40 describe the
   same product. The tracked-set row carries the rename provenance
   and the standing rate table; the field-table row is collapsed to a
   pointer to avoid double-counting. Competitive read unchanged: Boat
   stays the sharpest direct price competitor at this tier ($0.036/h
   all-in for 4 vCPU · 8 GB · 50 GB vs E2B's CPU-only 4-vCPU
   $0.2016/h VERIFIED, RAM billed separately).
3. **wowza.com owed item closed** (§2) — no corpus action beyond the
   note.

No other in-window launches, GA moves, funding, or pricing moves dated
2026-09-24.

## 5. In-lane and adjacent news scan (2026-09-23/24, all THIRD-PARTY)

**No new in-lane sandbox-infra items this pass.** Multiple targeted
searches (news + web, funding/launches/GA/pricing angles) returned
nothing genuinely new in agent-VM/sandbox infra for 9/23–24. The only
fresh funding items are **adjacent, not in-lane** (all THIRD-PARTY,
snippet-only — recorded, not folded): **Ema $77M Series B**
(enterprise agent teams, TechCrunch 9/23), **Chamelio $26M Series A**
(legal agents, 9/23), **Snorkel AI $350M at $3.5B** (agentic data
factory, 9/23). Deliberately dropped as duplicates/stale: DO Managed
Agents (9/22), Claude Code Projects relaunch (9/17), Runable $21M
(Aug), Exaforce $125M (May), OpenAI SandboxAgent memory() how-to
(9/21, not a launch), the dev.to E2B-vs-Daytona comparison (analysis).

## 6. Verdict

**Ninth full quiet 8/8 tracked-set pass since the mid-afternoon fold,
two owed items closed.** The core is quiet; the Drives beta streak
extends to 20 passes; C36 unchanged. The C40 rename question is
settled — ASCII became Boat (~2026-09-17), so the corpus sheds a
phantom second provider instead of gaining one. C41 opens the
in-lane billing corpus for hyperscaler FC-sandbox billing: Alibaba's
Eco tier works out to ~$0.037/h for a 2vCPU/4GiB box, task-scoped and
E2B-SDK-only — a pricing datapoint, not a shape competitor.
