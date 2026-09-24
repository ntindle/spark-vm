# Competitor watch — 2026-09-24 (noon)

Delta-only update against the late-evening pass
(`docs/COMPETITOR_WATCH_2026-09-24_LATE_EVENING.md`). Survey window
**2026-09-24 ~11:56–12:10 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set; (B) the carried asks (C36/C41/C43/C44 re-verifications),
the queued trends, plus an open-web in-lane news scan. Surveyor captures
live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-1154.md`), not the repo.

Evidence labels used by the watch passes: **VERIFIED** = read on a
vendor's own page, doc, or repo this run. **VENDOR-VERIFIED** =
confirmed on the vendor's own page, docs, or changelog read this run
(corpus field-table usage, e.g. C44). **VENDOR-ATTESTED** = confirmed
against the vendor's own served infrastructure (fetched
artifact/installer/API response) or company-issued announcement —
stricter than VERIFIED, as in the other 2026-09-24 watch docs.
**THIRD-PARTY** = press/third-party sources. **snippet-only** = seen
only via search snippet. **INFERRED** = my characterization.
**UNVERIFIED** = a public page exists but could not be fetched this run
(never reported as NO-CHANGE). **VERIFIED absent** = the vendor's own
page was read this run and the item is confirmed not present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

All reads within the survey window (~11:56–12:10 CDT); all values below
VERIFIED on the vendor's own page. Zero fetch failures — nothing labeled
UNVERIFIED. The full-quiet streak, re-opened at one by the evening pass
and advanced to two by the late-evening pass, advances to **three** this
pass.

- **Daytona — VERIFIED NO-CHANGE.** Changelog
  (https://www.daytona.io/changelog) still topped by the SEP 24 entries
  V0.216.1 + V0.216.2, then SEP 23 / V0.216.0 — exactly the
  late-evening baseline. No V0.216.3+ follow-ups. (Cosmetic: the render
  now lists 0.216.1 above 0.216.2 — same entries, ordering only.)
- **Docker Sandboxes — VERIFIED NO-CHANGE.** Release notes
  (https://docs.docker.com/ai/sandboxes/release-notes/) still top out
  **2026-09-21** (v3 kits); next entry 2026-09-15. Nothing dated
  09-22/09-23/09-24.
- **Microsandbox — VERIFIED NO-CHANGE.** Releases
  (https://github.com/superradcompany/microsandbox/releases) still top
  out **v0.7.1**; next release v0.7.0.
- **E2B — VERIFIED NO-CHANGE.** Pricing (https://e2b.dev/pricing):
  Hobby free with $100 one-time credit / 1h sessions / 20 concurrent;
  Pro $150/mo / 24h sessions / 100 concurrent (expandable to 1,100);
  per-second table $0.000014/s for 1 vCPU. All match baseline.
- **boat.dev (Boat) — VERIFIED NO-CHANGE on pricing.**
  (https://docs.boat.dev/pricing): rate table small $0.018 / default
  $0.036 / large $0.072 / xlarge $0.200 per sandbox hour; per-second
  billing; stopped sandboxes free; 25 free trial hours — all match.
  **Caveat:** the folded EU-only DE/FI/FR geography datapoint (FAQ
  verbatim, 2026-09-24 midday pass) could not be re-verified this run —
  the /pricing page carries no FAQ section and a web search returned
  only noise. Not re-confirmed, not refuted: carried to the next pass
  for re-attempt per the retry rule; no corpus change.
- **TermSquad — VERIFIED NO-CHANGE.** Plan table
  (https://termsquad.com/): Starter $9/mo 2 vCPU/4 GB/40 GB SSD NVMe;
  Builder $19/mo 4 vCPU/8 GB/75 GB; Power $29/mo 6 vCPU/12 GB/100 GB;
  Ultra $49/mo 8 vCPU/24 GB/200 GB. All match.
- **AgentComputer — VERIFIED NO-CHANGE.** Pricing
  (https://www.agentcomputer.ai/pricing): $0.07/CPU-hour,
  $0.04375/GB-hour, hot storage $0.000683/GB-hour (running), cold
  storage $0.000027/GB-hour (stopped); Enterprise tier present. All
  match.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE.** Pricing docs
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/):
  stamp still **"Last verified 22 Sep 2026"**; CPU $0.044/vCPU-hour,
  memory $0.0095/GB-hour, session storage $0.05/GiB-month;
  snapshots/checkpoints $0.05/GiB-month; BYOT $0.05/GiB-month. All match.

## 2. Carried asks — C36, C41, C43, C44 all unchanged; one sourcing upgrade

- **C36 Google Agent Substrate — VERIFIED unchanged this pass.** The
  Google Cloud blog
  (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  carries the standing terms verbatim: *"Agent Substrate is open source
  and available to all GKE customers for non-production workloads. GA
  support for production is available via allowlist."* No new
  datapoints on the page.
- **C41 Alibaba FC Agent Sandbox billing — VERIFIED unchanged.** The
  aliyun-fc/fc-docs pay-as-you-go page title confirms the exact pinned
  HEAD `39b6c3a20ec4597cceda497a4d8badf5384e2022` (matches the folded
  `39b6c3a`); all folded values match value-for-value (invite-only
  preview, allowlisted in batches; active/light/deep hibernation; 15 GiB
  disk free allowance on active + light only; Eco 0.00936/vCPU-h +
  0.004608/GiB-h; Std 0.01224/0.006012; Pro 0.01872/0.009360; disk
  0.00031896 mainland / 0.00025308 outside USD/GiB-h; per-second
  billing). No re-fold.
- **C43 Google Gemini Agent Environment — VERIFIED unchanged.** The
  vendor's own Gemini API docs
  (https://ai.google.dev/gemini-api/docs/agent-environment) still show
  the folded surface: *"Environments are managed Linux sandboxes that
  give agents an isolated place to execute code and persist files"*;
  `environment_id` reuse; git sources, network rules, env vars;
  `antigravity-preview-09-2026` strings. Observation, not a change: the
  Go snippet on the page still uses `antigravity-preview-05-2026` while
  other snippets use 09-2026 (stale-example hypothesis; third-party
  guide notes 05-2026 shuts down Oct 5, 2026) — no corpus impact.
- **C44 Google Gemini Enterprise Agent Platform sandboxes GA — VERIFIED
  unchanged.** The vendor's own release notes
  (https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
  still carry the September 09, 2026 entry verbatim: *"Computer Use and
  Shell sandboxes in Gemini Enterprise Agent Platform are now generally
  available (GA)"*, with the same entry shipping VPC Service Controls &
  Private Service Connect, CMEK (Cloud KMS, disk + snapshot
  checkpoints), and pause/resume. Newer Sept 10–22 entries on the page
  are all out-of-lane (Grok 4.6 GA, CodeMender, Gemini Omni Flash
  preview, RL fine-tuning preview, model deprecations, Priority PayGo).
- **OpenAI Agents API availability — sourcing upgrade, THIRD-PARTY →
  VENDOR-VERIFIED (no GA move, no content change).** The Sep 10
  public-beta dating is now confirmed on OpenAI's own changelog
  (https://developers.openai.com/api/docs/changelog, read this run):
  *"Sep 10 — Feature — Released the Agents API in public beta. Build
  agents with a managed Codex harness while OpenAI handles session
  orchestration, context compaction, and recovery. ... Run agents in
  OpenAI-hosted sandboxes or connect a sandbox from your own
  infrastructure or a supported provider."* Still public beta —
  **no GA move.** It remains an LLM/agent platform surface (out-of-lane),
  not new in-window: watch color only. Folded as a one-line sourcing
  upgrade in `docs/COMPETITOR_ANALYSIS.md`; supersedes the midday pass's
  THIRD-PARTY dating verdict.
- **Deprecated-row sunset convention — still proposed-not-codified.**
  No new deprecated-row activity surfaced this run (C40 ~6–7 passes
  into the proposed 14-pass retention). Not codified unilaterally —
  pending corpus-owner approval.
- **Vercel Drives GA watch — out of this pass's scope.** Per the P49
  decision it moved to once-daily (morning pass) after its 25th
  consecutive no-change pass. Next check: tomorrow morning.

## 3. Queued trends — all hold, none move in-lane

- **"Agentic cloud" two-vendor framing — STAYS QUEUED (adjacent).**
  Huawei VENDOR-VERIFIED unchanged on huawei.com
  (https://www.huawei.com/en/news/2026/9/hc-agentic-infra-industry-ai,
  read this run): "open agentic cloud" commitment; AICS commercial China
  Sept 30 / ex-China Nov 30; AgentArts 100+ enterprises; Context Memory
  Storage; "Agentic Infra" serving 3,500 customers claimed. Alibaba
  remains THIRD-PARTY — no vendor-own page found this run (coverage is
  Media OutReach Newswire syndication of the Sept 22 Apsara Conference;
  a third-party detail adds "Agent Native Cloud launched at WAIC July
  18" plus AgentRun/AgentLoop/AgentTeams — still third-party, not
  vendor-issued). Neither announces sandbox execution infra with a
  sign-up surface — adjacent-watch, not in-lane. No C-number.
- **Tencent Cloud DataBuddy (Sept 22) — stays adjacent-watch.** The
  Agent Runtime layer's "engineered to enable enterprises to run their
  AI agents with governance, auditability and data controls built in"
  (THIRD-PARTY PRNewswire syndication) is the closest-to-lane wording
  yet — lane tension stands, recorded not resolved. Still a managed
  data/AI workbench (Data Engineering / Governance / Analytics / Data
  Science), no task-scoped sandbox sign-up surface. No in-lane move.
- Evening-pass vetting holds: OpenAI Agents API availability now
  VENDOR-VERIFIED (§2); deprecated-row sunset convention
  proposed-not-codified. Namesake-collision warning stands: Guava's
  "Daytona" voice model is unrelated to Daytona sandboxes.

## 4. Corpus actions

1. **Sourcing upgrade — OpenAI Agents API availability dating.**
   The midday watch-update section's THIRD-PARTY dating verdict is
   rewritten as VENDOR-VERIFIED with the first-party changelog URL
   (see §2). No new datapoint, no C-number — content unchanged.
2. **C44 paren-balance nit — adopted** (deferred by the late-evening
   pass's reviewer with an explicit no-re-round blessing — recorded in
   the loop's RUNLOG, 2026-09-24 ~11:38 CDT merge-in-flight entry;
   applied in this pass's nit batch): the C44 field-table row's
   idle-suspend economics parenthetical now closes both parens.
3. **No new corpus entries.** No primary-source-ready fold candidates
   this pass.

## 5. News scan — no in-lane moves dated 2026-09-24

No in-lane launches, GA moves, pricing moves, or funding dated
2026-09-24. Today-dated items are all out-of-lane or recirculation:

- Darktrace Signal Labs launch (Sept 24, GlobeNewswire) — AI-agent
  behavioral-security *research* in sandboxed environments (findings
  disclosed to Anthropic/AWS/OpenAI). Out-of-lane: research initiative,
  not a sandbox offering.
- WEXTL public launch (Sept 24, ABNewswire) — AI agent builder + visual
  workflow automation (MAXMEL Tech Ltd). Out-of-lane: workflow
  automation, no sandbox compute.
- Meta Muse coverage update (Sept 24, explainx.ai) — Sept 8–9 consumer
  launch coverage refresh (Sentinel-VM architecture). Out-of-lane:
  consumer agent product.
- SandboxAQ "Switch" recirculation (dated Sept 24, launch was Aug 26)
  — open-source Slack/Teams agent-collab tool. Out-of-lane and
  out-of-window.
- aiagentstore.ai daily digest — Sept 24 recap of the Sept 22 Alibaba
  AgentCore/agentic-cloud news. Recirculation, adjacent.
- ai-xblog "Gemini Managed Agents 2026" (Sept 24, third-party guide) —
  corroborates C43's `antigravity-preview-09-2026`; recirc of known
  items. No in-lane move.
- Funding: Modal $15B / Baseten $26B are Sept 23 talks, already in
  corpus. No new in-lane funding dated 9/24.

## 6. Corpus actions carried forward

- Next passes: routine tracked-set re-reads; C36/C41/C43/C44
  re-verifies; Boat EU-only DE/FI/FR geography re-attempt (retry rule —
  FAQ not located on /pricing this run); the "agentic cloud" framing
  trend stays queued (Huawei half VENDOR-VERIFIED, Alibaba half
  THIRD-PARTY, adjacent); Tencent DataBuddy stays adjacent-watch;
  deprecated-row sunset convention still proposed-not-codified.
- Morning pass: Vercel Drives GA watch (now daily, per P49).
- F64 yield note: this pass yielded zero corpus moves; the last three
  slots carry one move (C44) — ~1 move/~3 slots, still above the
  advisory's 1-per-4 floor. No trigger.

---

Surveyed 2026-09-24 ~11:56–12:10 CDT. Tracked set 8/8 quiet (streak
3). C36/C41/C43/C44 unchanged. **OpenAI Agents API Sep-10 public-beta
dating upgraded THIRD-PARTY → VENDOR-VERIFIED (sourcing only, no GA
move).** Boat geography datapoint carried to next pass (FAQ not
re-located this run). Agentic-cloud trend queued (adjacent). No in-lane
launches, pricing moves, or funding dated 2026-09-24.
