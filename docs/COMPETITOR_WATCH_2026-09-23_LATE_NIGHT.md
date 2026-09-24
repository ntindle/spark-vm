# Competitor watch — 2026-09-23 (late night)

Delta-only update against the early-night pass
(`docs/COMPETITOR_WATCH_2026-09-23_EARLY_NIGHT.md`). Survey window
**2026-09-23 ~20:55–21:00 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set, (B) Vercel Drives GA watch plus Boxd/quickstart checks
plus an Automaid own-page re-attempt, a C36 re-check, a lane-drift check,
and an open-web market-news scan. Surveyor captures live in the loop's
`agent_notes/` workspace
(`surveyor-a/b-20260923-2054.md`), not the repo.

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
vendor's own page. No fetch failures on the tracked set this pass —
nothing labeled UNVERIFIED. The C26 figures carry forward unchanged for
the fourth consecutive pass (DO page stamp still "Last verified 22 Sep
2026"; snapshots/checkpoints $0.05/GiB-month; active-CPU-billing footnote
intact — VERIFIED on the docs pricing sub-page this run, not carried).

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
  sub-page stamp still **"Last verified 22 Sep 2026"**; CPU
  $0.044/vCPU-hour, memory $0.0095/GB-hour, session storage
  $0.05/GiB-month; snapshots/checkpoints $0.05/GiB-month (the
  mid-evening C26 resolution stands — read live again this pass, not
  carried); active-CPU-billing footnote intact ("Active CPU billing is
  coming soon. Until then, you will be billed at 25% of the vCPUs
  allocated … Paused sessions incur no compute charges"); BYOT
  $0.05/GiB-month; egress $0.01/GiB.
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/)

## 2. Adjacent checks

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (15th consecutive
  no-change pass).** Pricing page `last_updated` still **2026-09-10**;
  the related-links section still lists "Drives for Vercel Sandbox are
  now in public beta" (no GA move); Drives pricing rows read live this
  pass (Drive Storage 15 GB lifetime free on Hobby / $0.05/GB-month;
  Reads 30 GB/mo / $0.0015/GB; Writes 30 GB/mo / $0.004/GB; Active CPU
  $0.128/hr; Provisioned Memory $0.0212/GB-hour; Creations $0.60/1M).
  Web search surfaced no Vercel Sandbox changelog entries dated
  2026-09-23.
  (https://vercel.com/docs/sandbox/pricing)
- **Boxd (C29) — quickstart now VERIFIED; rate card UNVERIFIED this
  pass.** The docs quickstart fetched clean this run and matches the
  known boxd product (persistent hardware-isolated Linux machine,
  `boxd new` millisecond boot, SSH as `boxd` user with passwordless
  sudo, public HTTPS URL per machine, CoW fork <200 ms, snapshots and
  checkpoints, VM-to-VM control, org sharing) — last pass's quickstart
  UNVERIFIED debt is resolved. The **rate card** (€0.049/vCPU-hour,
  €0.015/GiB-hour resident RAM while running/standby,
  €0.0001/GiB-hour written disk, €30 new-account credits) could NOT be
  re-checked: the surveyor's fetch tool was gated for the rest of its
  turn after the Automaid fetch failure, and search surfaced no boxd.sh
  pricing content. Prior-pass numbers stand as unverified debt, not
  re-verified — honestly labeled, never NO-CHANGE.
  (https://docs.boxd.sh/quickstart)
- **C36 Google Agent Substrate — VERIFIED NO-CHANGE on the vendor
  axis.** No coverage dated 2026-09-23; no GA move, no production-terms
  change, no new design partners. Recent (non-dated-today) color:
  Substrate on GKE open-sourced, non-production for GKE customers,
  production support via allowlist only (deliberately not full GA);
  design partner Nous Research (Hermes); Google also open-sourced the AX
  agent orchestrator on K8s (Apache-2.0) — adjacent tooling, not a
  competitor move.
- **Automaid — own-page fetch FAILED again; likely a name collision.**
  The required own-page re-attempt at https://automaid.it.com failed
  (browser-service could not fetch) — second consecutive pass with no
  own-page evidence, so it stays **UNVERIFIED**, not NO-CHANGE. But the
  third-party picture has materially hardened: every 2026-09-23 search
  result for "Automaid" describes maid/cleaning-business booking SaaS
  (softwareadvice field-service profile, $75/mo; sourceforge/capterra
  "Automaid alternatives") — **nothing resembling a VM-for-agents
  launch, and the earlier third-party "AI hub" claim now has zero
  third-party support either.** Working verdict (INFERRED, pending the
  own-page fetch that would close it): Automaid is almost certainly a
  name collision, not a lane competitor — it moves to the lane-drift
  bucket, kept on the watch list only until one successful own-page
  fetch settles it. This does not fold into the corpus yet: no
  primary-source read exists to fold.
- **Lane-drift: Tencent Cloud DataBuddy — NOT IN-LANE (confirmed).**
  THIRD-PARTY (PRNewswire, Sept. 23, 2026, syndicated): a fully
  managed, agent-native Data + AI workbench — four agent scenarios
  (Data Engineering, Governance, Analytics, Science) with an "Agent
  Runtime" layer for governance/auditability. Data-platform product
  with embedded agents, alongside CodeBuddy and WorkBuddy. It is not
  VM-for-agents compute. Stays lane-drift.

## 3. Market-news scan

No in-lane launch/GA/funding/pricing move today beyond what is already
tracked. No moves today from E2B, Modal, Cloudflare, Fly.io, Docker,
Microsandbox, Runloop, Blaxel, Oracle, Vercel Sandbox, DigitalOcean, or
Daytona in 2026-09-23 coverage. Adjacent THIRD-PARTY color only: Upstash
published a 15-provider sandbox comparison (upstash.com/blog/
ai-agent-sandbox-providers-compared-2026, updated ~7 days ago, not a
product announcement) naming newcomers Upstash Box, Freestyle, Ascii
Box, Namespace, Beam, and Tensorlake — candidate names for future
vetting, not tracked vendors.

## 4. Fold decision

No corpus fold this pass. The precedent (C32 primary-source-verification
fold, C35 close-only) holds: nothing changed on a primary source, so
there is nothing to fold and nothing to close. The two UNVERIFIED items
(Boxd rate card, Automaid own page) are asks for the next pass, not
findings. The Upstash newcomer list is third-party color, not a fold —
vendors enter the tracked set only after primary-source verification.

## 5. Verdict

In-lane: **quiet.** 15th consecutive pass with no tracked-set vendor-side
change since the morning's Daytona/Docker moves (fourth full 8/8 re-read
quiet pass since the mid-afternoon fold); 15th consecutive quiet Vercel
Drives pass; Boxd quickstart verification debt resolved (rate card still
owed); no GA moves, no pricing moves, no in-lane launches today.
Automaid's standing is revised downward: the third-party "AI hub" claim
has no third-party support anymore and the name resolves to cleaning-
business SaaS everywhere — lane-drift pending one successful own-page
fetch.

## Next-pass asks

- Re-attempt own-page fetch of https://automaid.it.com (failed two
  consecutive passes) and re-check the Boxd rate card at
  https://boxd.sh — both UNVERIFIED for today's pass.
- Routine tracked-set re-reads; Vercel Drives GA watch (16th pass).
- Vet the Upstash 15-provider comparison's newcomer names (Upstash Box,
  Freestyle, Ascii Box, Namespace, Beam, Tensorlake) against primary
  sources before any tracked-set consideration.
