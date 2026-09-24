# Competitor watch — 2026-09-24 (early afternoon)

Delta-only update against the noon pass
(`docs/COMPETITOR_WATCH_2026-09-24_NOON.md`). Survey window
**2026-09-24 ~12:56–13:08 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set; (B) the carried asks (C36/C41/C43/C44 re-verifications
+ OpenAI Agents API GA check), the queued trends, plus an open-web
in-lane news scan. Surveyor captures live in the loop's `agent_notes/`
workspace (`surveyor-a/b-20260924-1254.md`), not the repo.

Evidence labels used by the watch passes: **VERIFIED** = read on a
vendor's own page, doc, or repo this run. **VENDOR-VERIFIED** =
confirmed on the vendor's own page, docs, or changelog read this run
(corpus field-table usage, e.g. C45). **THIRD-PARTY** = press/third-party
sources. **snippet-only** = seen only via search snippet. **INFERRED** =
my characterization. **UNVERIFIED** = a public page exists but could not
be fetched this run (never reported as NO-CHANGE). **VERIFIED absent** =
the vendor's own page was read this run and the item is confirmed not
present on it.

## 1. The tracked set — 7/8 VERIFIED NO-CHANGE, one move

The full-quiet streak, advanced to three by the noon pass, **ends at
three** this pass on a tracked-set move. Seven surfaces match the noon
baseline value-for-value; all reads within the survey window; zero
fetch failures — nothing labeled UNVERIFIED.

- **Daytona — VERIFIED NO-CHANGE.** Changelog
  (https://www.daytona.io/changelog) still topped by the SEP 24 entries
  V0.216.1 (API key organization ID + CLI update warning fix) +
  V0.216.2 (CLI login through WorkOS), then SEP 23 / V0.216.0. No
  V0.216.3+ follow-ups.
- **Docker Sandboxes — VERIFIED NO-CHANGE.** Release notes
  (https://docs.docker.com/ai/sandboxes/release-notes/) still top out
  **2026-09-21** (v3 kits); next entry 2026-09-15. Nothing dated
  09-22/09-23/09-24. **Note:** Docker did move this pass — the *cloud*
  launch in §3 — but the local-Sandboxes release notes (the tracked
  surface) are unchanged.
- **Microsandbox — CHANGED.** Releases
  (https://github.com/superradcompany/microsandbox/releases) now top
  out **v0.7.3** (changelog "v0.7.2...v0.7.3"; "chore: release v0.7.3
  by @toksdotdev in #1646"), with v0.7.1 immediately below —
  **v0.7.2 and v0.7.3 are new beyond the v0.7.1 baseline.** Release
  titles/version headers were not visible in the rendered text; recorded
  as a tracked-set move (patch releases), not a feature fold — the
  corpus field-table row pins no version, so no row change.
- **E2B — VERIFIED NO-CHANGE.** Pricing (https://e2b.dev/pricing):
  Hobby FREE $100 one-time credit / 1h sessions / 20 concurrent; Pro
  $150/mo / 24h sessions / 100 concurrent (expandable to 1,100);
  per-second table $0.000014/s for 1 vCPU. All match.
- **boat.dev (Boat) — VERIFIED NO-CHANGE on pricing.**
  (https://docs.boat.dev/pricing): small $0.018 / default $0.036 /
  large $0.072 / xlarge $0.200 per sandbox hour; per-second billing;
  stopped sandboxes free; 25 free trial hours — all match.
  **Caveat:** the folded EU-only DE/FI/FR geography datapoint (FAQ
  verbatim, midday pass) was **not re-located for the third consecutive
  pass** — targeted searches plus a scan of the docs home page found no
  FAQ entry. Not re-confirmed, not refuted: carried to the next pass
  per the retry rule; no corpus change (the midday verbatim fold stands).
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
  stamp still **"Last verified 22 Sep 2026"** (not moved); CPU
  $0.044/vCPU-hour, memory $0.0095/GB-hour, session storage
  $0.05/GiB-month; snapshots/checkpoints $0.05/GiB-month; BYOT
  $0.05/GiB-month. All match.

## 2. Carried asks — C36, C41, C43, C44 all unchanged; no OpenAI GA

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
  preview, allowlisted in batches; active/light/deep hibernation; 15
  GiB disk free allowance on active + light only; Eco 0.00936/vCPU-h +
  0.004608/GiB-h; Std 0.01224/0.006012; Pro 0.01872/0.009360; disk
  0.00031896 mainland / 0.00025308 outside USD/GiB-h; per-second
  billing). No re-fold. **Awareness flag (not folded):** the page now
  also documents Snapshot pricing ("Snapshot Storage Usage = Memory
  Specification × 2 + Disk Specification") — a new datapoint on the
  C41 page that is not part of the carried baseline. Queued as an
  explicit fold candidate for the next pass; not folded here because it
  was seen only as a section note, not a full re-read.
- **C43 Google Gemini Agent Environment — VERIFIED unchanged.** The
  vendor's own Gemini API docs
  (https://ai.google.dev/gemini-api/docs/agent-environment) still show
  the folded surface verbatim: *"Environments are managed Linux
  sandboxes that give agents an isolated place to execute code and
  persist files"*; `environment_id` reuse; git sources, network rules,
  env vars; `antigravity-preview-09-2026` strings. Footer still: *"Preview
  status: Environments and managed agents are in preview."* No GA move.
- **C44 Google Gemini Enterprise Agent Platform sandboxes GA —
  VERIFIED unchanged.** The vendor's own release notes
  (https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
  show latest entry September 22, 2026 (Feature, no body rendered); the
  September 09, 2026 GA entry stands verbatim. No new in-lane sandbox
  entries dated Sep 23–24.
- **OpenAI Agents API — still public beta, no GA.** The changelog's
  latest entry is Sep 22 (GPT-6 Sol / GPT-6 Luna); the Sep 10 entry
  still reads *"Released the Agents API in public beta."* No
  vendor-issued GA announcement found (this run read a third-party
  mirror of the changelog; the noon pass's VENDOR-VERIFIED dating on
  OpenAI's own changelog stands).
- **Deprecated-row sunset convention — still proposed-not-codified.**
  No new deprecated-row activity surfaced this run (C40 ~7–8 passes
  into the proposed 14-pass retention). Not codified unilaterally —
  pending corpus-owner approval.
- **Vercel Drives GA watch — out of this pass's scope.** Per the P49
  decision it moved to once-daily (morning pass) after its 25th
  consecutive no-change pass. Next check: tomorrow morning.

## 3. C45 new — Docker launches Cloud Sandboxes (in-lane, VENDOR-VERIFIED)

**Fold:** `docs/COMPETITOR_ANALYSIS.md` gains a C45 field-table row and
a watch-update section per the C32/C37/C38/C39/C40/C41/C42/C43/C44
precedents.

Docker's own blog
(https://www.docker.com/blog/introducing-cloud-sandboxes-start-on-your-laptop-finish-in-the-cloud/,
identified via search snippets in the survey window, read in full 2026-09-24 in the repair turn — **VENDOR-VERIFIED**): *"Today, we're introducing
Cloud Sandboxes: the same microVM-based sandbox, running on
Docker-managed compute, with one command to move between them."* The
offering:

- **Same microVM, two surfaces.** The isolation model is identical to
  local Docker Sandboxes (own kernel, own Docker daemon); the
  differentiation is the compute substrate — *"Close your laptop and
  keep the work going"* and *"Run 100 tasks in parallel with nothing
  to provision."*
- **`sbx move <name> --to cloud`:** one command migrates a sandbox's
  filesystem to the cloud (bidirectional); work carries over.
- **Agent kit:** kits for Claude Code, Codex, Copilot, Antigravity,
  Open Code, and Hermes; MCP gateway connecting the agent's servers
  once; **secrets proxy-injected per request** (agents never see the
  actual secret — the placeholder-swap pattern, same family as C34
  host-side credential proxying and Microsandbox's network-layer
  injection); network policies per agent; per-sandbox secrets.
- **Pricing (PAYG, per-second metering):** Micro 1 vCPU/2 GiB $0.07/h;
  Small (default) 2/4 $0.14/h; Medium 4/8 $0.28/h; Large 8/16 $0.56/h;
  XL 16/32 $1.12/h. *"A paused sandbox costs nothing."* Volumes, egress,
  and hosting public images/kits are free. Sessions run 1 hour by
  default, up to 24 hours. **Limited-time $250 free Cloud Sandboxes
  credit for new accounts.**
- **Sign-up surface:** web console (agentic-platform.docker.com) or
  `sbx --cloud run`, sbx ≥ 0.45.1, pay-as-you-go plan on Docker
  Personal and Pro accounts; local Sandboxes stay free and standalone.
- **Dating caveat:** Docker's own page shows no publish date in the
  fetched text (screenshots dated 2026-09-23); surfaced 2026-09-24 via
  a GlobeNewswire wire
  (https://www.financialcontent.com/article/gnwcq-2026-9-24-docker-launches-cloud-sandboxes-extending-secure-ai-agent-isolation-beyond-the-laptop)
  dated 2026-09-24. Filed as a 2026-09-24 move with the caveat stated.

**Read for spark-vm:** Docker's cloud surface is the move Docker had
to make — local-only was the gap in their lane — and its framing is
notable: *"how much you can trust your agent shouldn't depend on where
it happens to be running"* ("one strong isolation model, two
surfaces"). That is the direct inverse of spark-vm's pitch (one
persistent computer, mine everywhere), but the pricing table is the
competitive datum: **$0.07/CPU-hour lands exactly on Fly Sprites' and
AgentComputer's $0.07/CPU-hour** — three vendors now share the entry
price point. spark-vm's self-hosted story still wins on cost-at-idle
(zero when idle on own hardware); the hosted product's edge has to be
continuity + MCP/secret plumbing, where Docker's kit/secrets-proxy
story is converging from above. The per-agent secrets proxy-injection
is the **seventh** placeholder-swap datapoint for the secrets turns
(after Daytona, Microsandbox, opencomputer.dev, h-sandbox, DigitalOcean
Managed Agents (C26), and the C43 Credentials API).

## 4. Queued trends — all hold, none move in-lane

- **"Agentic cloud" two-vendor framing — STAYS QUEUED (adjacent).**
  Huawei VENDOR-VERIFIED unchanged on huawei.com
  (https://www.huawei.com/en/news/2026/9/hc-agentic-infra-industry-ai,
  read this run): AICS commercial in China Sept 30 / ex-China Nov 30 —
  no new sandbox or task-scoped sign-up surface on the page.
  Alibaba stays THIRD-PARTY: Apsara Conference (Sep 22–24, Hangzhou)
  press coverage reports a "purpose-built agentic cloud" plus Qwen 4 in
  training and proprietary AI chips — no alibaba.com/alibabacloud.com
  vendor-issued page for an "Agent Native Cloud" or sandbox sign-up
  surface surfaced in search. Framing-level only; nothing task-scoped.
  No C-number.
- **Tencent Cloud DataBuddy (Sept 22) — stays adjacent-watch.** Coverage
  stays THIRD-PARTY (PRNewswire reposts): "fully managed, agent-native
  Data + AI workbench," Agent Runtime layer, available China/Thailand/
  South Korea/Indonesia. The official trial portal
  (https://databuddy.tencentcloud.com/website) **could not be fetched
  this run — UNVERIFIED** (a "trial registration" page is not a
  confirmed task-scoped sandbox sign-up surface). Lane tension stands,
  recorded not resolved.
- Evening-pass vetting holds: namesake-collision warning stands
  (Guava's "Daytona" voice model is unrelated to Daytona sandboxes).

## 5. Corpus actions

1. **New entry C45 — Docker Cloud Sandboxes** (VENDOR-VERIFIED
   in-lane launch, surfaced 2026-09-24; field-table row + watch-update
   section in `docs/COMPETITOR_ANALYSIS.md`, per the C32/C37/C38/C39/
   C40/C41/C42/C43 precedent).
2. **Microsandbox v0.7.2/v0.7.3 — recorded as a tracked-set move, not
   a fold.** The corpus field-table row pins no version, so no row
   change; release titles were not verified this run. If a later pass
   reads the v0.7.3 notes, that pass owns any feature-level fold.
3. **C41 Snapshot-pricing awareness flag queued** (see §2) — fold
   candidate for the next pass, not folded here.
4. **Watch-doc naming convention admits `_EARLY_AFTERNOON`.** The
   09:54 pass's `_AFTERNOON` was already taken; this 12:54-slot pass
   reads honestly as early afternoon. The canonical suffix list in
   `docs/COMPETITOR_ANALYSIS.md` gains `_EARLY_AFTERNOON` (same
   amendment practice as the noon pass's `_NOON` admission).
5. **No other corpus changes.** C36/C41/C43/C44 re-verified unchanged;
   OpenAI Agents API stays public beta; deprecated-row sunset
   convention still proposed-not-codified.

## 6. News scan — one in-lane move dated 2026-09-24

- **Docker Cloud Sandboxes (Sept 24) — in-lane, folded as C45** (§3).
- SandboxAQ "AQtive Guard" GA (Sept 24, nexttechtoday) — AI
  agent/NHI security platform. Adjacent: security tooling, not sandbox
  compute.
- Dataiku Agent Management launch (Sept 24, BusinessWire) — agent
  inventory/governance, GA in October. Adjacent: governance, not
  compute.
- Island raises $400M at $6.4B (Sept 24, techstartups) — browser
  security vs rogue agents. Out-of-lane.
- Bird.com $450M debt financing (Sept 23) — comms infra for AI
  agents. Adjacent.
- DigitalOcean Managed Agents GA (Sept 22, BusinessWire) — managed
  agent execution, "AI-Native Cloud" framing, hardware-isolated
  sessions. Adjacent (managed agents, not a sandbox sign-up surface);
  the harness-runtime pricing is already in the tracked set.
- WSO2 Agent Manager GA (~Sept 20, itnewsafrica) — K8s-native
  sandboxed agent runtime, governance. Adjacent.
- Funding in-lane: none dated 9/24. Modal $15B / Baseten $26B are
  Sept 23 talks, already in corpus.

## 7. Corpus actions carried forward

- Next passes: routine tracked-set re-reads; C36/C41/C43/C44
  re-verifies; Boat EU-only DE/FI/FR geography re-attempt (retry rule —
  FAQ not located for three consecutive passes); the "agentic cloud"
  framing trend stays queued (Huawei half VENDOR-VERIFIED, Alibaba half
  THIRD-PARTY, adjacent); Tencent DataBuddy stays adjacent-watch (portal
  re-attempt); deprecated-row sunset convention still proposed-not-
  codified; **C41 Snapshot pricing fold candidate** (see §2).
- Morning pass: Vercel Drives GA watch (now daily, per P49).
- F64 yield note: this pass yielded **one new in-lane corpus entry
  (C45)** plus one tracked-set move (Microsandbox patch releases) —
  novel yield well above the advisory's 1-per-4 floor. No trigger.

---

Surveyed 2026-09-24 ~12:56–13:08 CDT. Tracked set 7/8 quiet (the
full-quiet streak of three ends on Microsandbox v0.7.2/v0.7.3).
C36/C41/C43/C44 unchanged; OpenAI Agents API still public beta. **New
in-lane launch: C45 Docker Cloud Sandboxes (VENDOR-VERIFIED on Docker's
own blog — same microVM, two surfaces; PAYG $0.07–$1.12/h; paused
free; $250 free credit).** Boat geography datapoint carried (FAQ not
re-located, third consecutive pass). Agentic-cloud trend queued
(adjacent). No in-lane funding dated 2026-09-24.
