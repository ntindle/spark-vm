# Competitor watch — 2026-09-24 (afternoon)

Delta-only update against the late-midday pass
(`docs/COMPETITOR_WATCH_2026-09-24_LATE_MIDDAY.md`). Survey window
**2026-09-24 ~08:55–09:15 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set plus the Vercel Drives GA watch and the C36/C41
re-verifications; (B) an open-web in-lane news scan plus vetting of the
aiagentstore.ai "Agents API opened to all developers" digest claim.
Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-0854.md`), not the repo.

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

## 1. The tracked set — 7/8 VERIFIED NO-CHANGE (Daytona moves)

All reads within the survey window (~08:56–09:05 CDT); all values below
VERIFIED on the vendor's own page. Zero fetch failures — nothing labeled
UNVERIFIED. The eleven-pass full-quiet 8/8 streak ends here: Daytona
posted two changelog entries today. Everything else matches the
late-midday pass exactly.

- **Daytona — VERIFIED CHANGE (two new entries today).** Changelog
  (https://www.daytona.io/changelog) is now topped by **SEP 24 2026 /
  V0.216.2** ("CLI login through WorkOS" — adds WorkOS as a CLI login
  method when the API advertises it) and, below it, **SEP 24 2026 /
  V0.216.1** ("API key organization ID and CLI update warning fix" —
  organization context in API key listings; stops the CLI's
  outdated-version warning when no newer release is available). The
  late-midday top (SEP 23 / V0.216.0, "Confine Dockerfile COPY sources
  to the build context") is now third. CLI/API polish only — no
  pricing move, no sandbox-feature move.
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
- **boat.dev (Boat) — VERIFIED NO-CHANGE.** Pricing
  (https://docs.boat.dev/pricing): rate table small $0.018 / default
  $0.036 / large $0.072 / xlarge $0.200 per sandbox hour; per-second
  billing; stopped sandboxes free; 25 free trial hours; plan and
  comparison tables unchanged.
- **TermSquad — VERIFIED NO-CHANGE.** Plan table
  (https://termsquad.com/): Starter $9/mo 2 vCPU/4 GB/40 GB SSD NVMe;
  Builder $19/mo 4 vCPU/8 GB/75 GB; Power $29/mo 6 vCPU/12 GB/100 GB;
  Ultra $49/mo 8 vCPU/24 GB/200 GB. All match.
- **AgentComputer — VERIFIED NO-CHANGE.** Pricing
  (https://www.agentcomputer.ai/pricing): $0.07/CPU-hour,
  $0.04375/GB-hour, hot storage $0.000683/GB-hour (running), cold
  storage $0.000027/GB-hour (stopped). All match.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE.** Pricing docs
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/):
  stamp still **"Last verified 22 Sep 2026"**; CPU $0.044/vCPU-hour,
  memory $0.0095/GB-hour, session storage $0.05/GiB-month;
  snapshots/checkpoints $0.05/GiB-month; BYOT $0.05/GiB-month; egress
  $0.01/GiB; shapes mars-1vcpu-1gb–mars-16vcpu-32gb.

## 2. Carried asks

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (23rd consecutive
  no-change pass).** Pricing page VERIFIED
  (https://vercel.com/docs/sandbox/pricing): `last_updated` still
  **2026-09-10**; all values match baseline (Drive Storage
  $0.05/GB-month; Reads $0.0015/GB; Writes $0.004/GB; up to 4 drives
  per sandbox, 1 TiB default / 1 GiB Hobby, 16 TiB max; downloads free;
  session caps 45min/24h; concurrency 10/10,000). The related-pages
  rail on the same page still links "Drives for Vercel Sandbox are now
  in public beta." Changelog (https://vercel.com/changelog): the
  Drives public-beta entry still carries its **2026-09-23 date**; the
  newest 2026-09-24 entry remains adjacent ("Vercel Connect now
  supports TanStack AI"), not in-lane. **Still public beta, NOT GA** —
  no GA move, no fold.
- **C36 Google Agent Substrate — VERIFIED unchanged this pass.** The
  Google Cloud blog
  (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  carries the standing terms verbatim: *"Agent Substrate is open source
  and available to all GKE customers for non-production workloads. GA
  support for production is available via allowlist."* No new
  datapoints.
- **C41 Alibaba FC Agent Sandbox billing — VERIFIED unchanged.**
  The aliyun-fc/fc-docs pay-as-you-go page at HEAD (`39b6c3a`) matches
  the morning fold value-for-value: invite-only preview; active/light/
  deep hibernation states; 15 GiB disk free allowance on active + light
  hibernation; Eco 0.00936/vCPU-h + 0.004608/GiB-h, Std
  0.01224/0.006012, Pro 0.01872/0.009360; disk 0.00031896 mainland /
  0.00025308 outside USD/GiB-h; per-second billing ("usage shorter than
  1 second is billed as 1 second"). HEAD commit is unchanged (`39b6c3a`).
  No re-fold.

## 3. New findings — one new corpus entry, one tracked-set move

- **C43 new — Google Gemini Agent Environment (VERIFIED in-lane).**
  Google's own Gemini API docs
  ([Agent Environment](https://ai.google.dev/gemini-api/docs/agent-environment),
  read this run): *"Environments are managed Linux sandboxes that give
  agents an isolated place to execute code and persist files."*
  Sandboxes are reusable via `environment_id`, support sources (git
  repo mount), network allowlists, env vars / credential references,
  and pre-installed Ubuntu toolchains; the docs' current examples use
  agent string `antigravity-preview-09-2026` (the THIRD-PARTY layer —
  Sept 17 coverage in ai-xblog/omidsaffari/forbesposts — adds: replaces
  `antigravity-preview-05-2026`, which shuts down Oct 5, 2026; new
  Files API for persistent file upload/list/download into the sandbox;
  new Credentials API that injects secrets as env vars/MCP headers so
  the model never sees the raw secret — a sixth convergent data
  point for the placeholder-swap secrets-posture corpus, noted here
  for the secrets turns, not folded into this pass's scope; claimed
  ~40% fewer output tokens on file edits and +8% task completion;
  preview compute not billed). This is a vendor-owned,
  agent-execution-first sandbox surface — in-lane, sibling of Agent
  Substrate (C36). Corpus action: filed as **C43**.
- **Daytona V0.216.1 / V0.216.2 (SEP 24) — tracked-set changelog
  move, no pricing impact.** As §1 details: WorkOS CLI login,
  API-key organization context, outdated-version warning fix. Corpus
  action: watch-doc record only — the field table carries Daytona's
  positioning/pricing, not its changelog entries (per the long-standing
  fold convention), so no field-table change.
- **OpenAI Agents API "opened to all developers" — kept at
  THIRD-PARTY; not a 9/24 development, not GA.** The surveyor verified
  on OpenAI's own docs
  (developers.openai.com/api/docs/guides/agents-api/overview) that the
  Agents API is live and documented ("gives your application access to
  the Codex harness through an OpenAI-managed API": Agent/Environment/
  Session/Events primitives; OpenAI-hosted or self-hosted sandboxes).
  But the canonical announcement page
  (openai.com/index/introducing-the-agents-api) could not be fetched
  this run, and the "public beta" dating lives only on a community
  mirror of the developers changelog ("Released the Agents API ... in
  public beta", Sept 10). Per the evidence rules the availability
  verdict stays THIRD-PARTY: the digest claim is accurate as *"public
  beta opened to all API developers on Sept 10, 2026"*, but it is an
  LLM/agent platform surface — out-of-lane proper — and it is not new
  in-window. Watch color only.
- **Tencent Cloud DataBuddy official launch — THIRD-PARTY, adjacent
  watch color (lane-characterization tension noted, not resolved).**
  PRNewswire syndication mirrors (vendor press release not fetched on
  tencentcloud.com): agent-native Data + AI workbench — the third
  assistant-class product after CodeBuddy/WorkBuddy — built on an
  "Agent Runtime layer" (governance, auditability, data controls);
  dated **Sept 22, 2026**; available in China, Thailand, South Korea,
  Indonesia; EU/NA/SA rollouts ongoing. The midnight pass recorded
  DataBuddy as *adjacent*; this pass's surveyor characterized it as
  in-lane per the scope list. An agent-data-workbench is agent-product
  territory with a runtime layer beneath it, and the vendor's own page
  was not read — so this pass keeps it as adjacent watch color and
  records the tension rather than unilaterally recoding the lane.
- **Adjacent color, no fold:** Alibaba Cloud's agentic-cloud strategy
  + AgentCore (Sept 22, Hangzhou Cloud Summit; THIRD-PARTY — managed
  agent platform, adjacent; FC Agent Sandbox already recorded) and
  GitHub Copilot app opt-in local sandboxing in public preview (Sept
  23, snippet-only via a Medium digest citing the GitHub Changelog:
  per-project sandbox controls for local repo sessions — restrict
  filesystem, outbound/local-network access, Git/GitHub CLI
  credentials; shell fails instead of running unsandboxed if the OS
  can't enforce — an agent product, out-of-lane).
- **Deprecated-row sunset convention — still open, still within
  window.** C40 was deprecated this morning (~4–5 passes ago); under
  the proposed 14-pass retention it stays in the corpus regardless.
  The recommendation remains pending corpus-owner approval — not
  codified unilaterally this pass.

## 4. Corpus actions

1. **C43 new — Google Gemini Agent Environment:** field-table row added
   (in-lane, VERIFIED on the vendor's own docs
   ([ai.google.dev/gemini-api/docs/agent-environment](https://ai.google.dev/gemini-api/docs/agent-environment))):
   *"Environments are managed Linux sandboxes that give agents an
   isolated place to execute code and persist files"* — reusable via
   `environment_id`; sources (git repo mount); network allowlists; env
   vars / credential references; pre-installed Ubuntu toolchains;
   current examples use agent string `antigravity-preview-09-2026`.
   Sept-17 detail at the THIRD-PARTY layer: Files API (persistent file
   upload/list/download), Credentials API (secrets injected as env
   vars/MCP headers, model never sees the raw secret — a sixth
   placeholder-swap data point, noted for the secrets turns);
   vendor-claimed ~40% fewer output tokens on file edits, +8% task
   completion; preview compute not billed. Sibling of Agent Substrate
   (C36).
2. **Daytona changelog move:** watch-doc record only (see §3); no
   field-table change per the fold convention.
3. **Tencent DataBuddy:** adjacent watch color; lane-characterization
   tension (adjacent per the midnight pass vs in-lane per this pass's
   surveyor) recorded in §3 rather than unilaterally resolved — the
   vendor's own page was not read this run.
4. **No other new C-numbers.** No in-lane launches, GA moves, pricing
   moves, or funding dated 2026-09-24 this pass.

## 5. In-lane and adjacent news scan (2026-09-24, THIRD-PARTY unless noted)

**No new in-lane sandbox-infra items dated 2026-09-24.** The Sept
22–23 items above (DataBuddy launch, AgentCore, Copilot sandboxing)
are catch-up, not 9/24 news. Deliberately dropped as out-of-lane or
out-of-window: Daytona "agent-agnostic infrastructure" PRNewswire
recirculation (stale 2024 release — one mirror stamps it ~3,044 days
old, citing a "$5M seed round" — recycled syndication); Boxd $2M
pre-seed (C29, round closed 9/21, no new development); E2B dev.to
pricing explainer (third-party commentary, no vendor action); "Harbor
evals on Vercel Sandbox" (Sept 17, third-party eval content, not
vendor news); Cursor Rollouts + Security Reviewer (Sept 24, agent
product — out of lane); Darktrace Signal Labs launch (Sept 24,
AI-agent security research, not execution infra — out of lane); Zoho
Catalyst agentic PaaS enhancements (Sept 24, managed-agent/PaaS
platform adjacent, no sandbox-infrastructure specifics); Modal $355M
(2026-05-21, out of window); Alibaba FC snapshot billing (announced
Aug 25, already recorded); Cursor Rollouts + Claude Code Projects GA
(from the prior pass — agent products, out of lane); Crusoe $3.9B
Series F (9/17, GPU-cloud exclusion); the Google
"antigravity-preview-09-2026" managed-agents harness digest (out of
window; the sibling sandbox surface is now covered directly as C43).

## 6. Verdict

**7/8 tracked-set quiet; one tracked-set move; one new corpus entry.**
The eleven-pass full-quiet streak ends on a minor note — Daytona's two
SEP 24 changelog entries are CLI/API polish (WorkOS login, API-key org
context, warning fix), not sandbox moves. The Drives beta streak
extends to 23 passes with still no GA. C36 and C41 re-verified
unchanged. The substantive finding is **C43: Google's Gemini Agent
Environment** — a vendor-owned managed-Linux-sandbox surface for
agents, VERIFIED on Google's own docs, with a Sept-17 Files/Credentials
API layer at THIRD-PARTY (the Credentials API is a sixth
placeholder-swap datapoint worth flagging to the secrets turns). No
in-lane launches, GA moves, pricing moves, or funding dated 2026-09-24.
