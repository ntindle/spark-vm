# Competitor watch — 2026-09-24 (late midday)

Delta-only update against the midday pass
(`docs/COMPETITOR_WATCH_2026-09-24_MIDDAY.md`). Survey window
**2026-09-24 ~06:54–07:12 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set plus the Vercel Drives GA watch and the C36/C41
re-verifications; (B) an open-web in-lane news scan plus vetting of the
midnight pass's remaining unvetted candidates (Ascii Box, Namespace,
Beam). Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-0654.md`), not the repo.

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

All reads within the survey window (~06:56–07:02 CDT); all values below
VERIFIED on the vendor's own page. Zero fetch failures — nothing labeled
UNVERIFIED. The **eleventh full quiet 8/8 re-read pass since the
mid-afternoon fold**; values match the midday pass exactly.

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

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (22nd consecutive
  no-change pass).** Pricing page VERIFIED
  (https://vercel.com/docs/sandbox/pricing): `last_updated` still
  **2026-09-10**; all values match baseline (Drive Storage
  $0.05/GB-month; Reads $0.0015/GB; Writes $0.004/GB; up to 4 drives
  per sandbox, 1 TiB default / 1 GiB Hobby, 16 TiB max; downloads free;
  session caps 45min/24h; concurrency 10/10,000). Changelog read this
  run (https://vercel.com/changelog): the "Drives for Vercel Sandbox
  are now in public beta" entry still carries its **2026-09-23 date**
  (the beta announcement surfacing as a re-dated entry — the INFERRED
  characterization stands across seven passes); the newest 2026-09-24
  entry remains adjacent (Vercel Connect × TanStack AI), not in-lane.
  **Still public beta, NOT GA** — no GA move, no fold. One watch-color
  tension, recorded honestly and not upgraded: a THIRD-PARTY
  snippet-only page (langchain.com resources, "best agent sandboxes")
  describes Drives as "a private beta on Pro and Enterprise plans" —
  the vendor's own changelog (VERIFIED this run) says public beta, so
  the verdict stays **public beta**; the langchain snippet is kept as
  availability color (publicly announced beta, possibly plan-gated
  access), not as a contradiction.
- **C36 Google Agent Substrate — VERIFIED unchanged this pass.**
  The Google Cloud blog (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  carries the standing terms verbatim: *"Agent Substrate is open source
  and available to all GKE customers for non-production workloads. GA
  support for production is available via allowlist."* No new datapoints.
- **C41 Alibaba FC Agent Sandbox billing — VERIFIED unchanged.**
  The aliyun-fc/fc-docs pay-as-you-go page at HEAD (`39b6c3a`) matches
  the morning fold value-for-value: invite-only preview; active/light/
  deep hibernation states; 15 GiB disk free on active + light
  hibernation; Eco 0.00936/vCPU-h + 0.004608/GiB-h, Std 0.01224/0.006012,
  Pro 0.01872/0.009360; disk 0.00031896 mainland / 0.00025308
  outside USD/GiB-h; per-second billing ("usage shorter than 1 second
  is billed as 1 second"). No re-fold.

## 3. New findings — vetting upgrades, not launches

- **C42 new — Namespace Devboxes moves adjacent → in-lane
  (VERIFIED).** The midnight pass vetted Namespace as *adjacent*
  (dev-compute, "not VM-for-agents-first"); the vendor's own docs
  contradict that reading. [Devboxes for Coding Agents —
  Namespace Documentation](https://namespace.so/docs/devbox/agents)
  (read this run): *"A coding agent needs a machine where it can clone
  a repository, install dependencies, run commands, and return the
  result. Devboxes provide Linux and macOS machines"* — ephemeral
  Devboxes, Pool API (`devbox acquire`), `devbox exec` / `logs` /
  `upload`, egress filtering (`network_policy.egress_domains`),
  secrets via the Namespace vault, and native integrations where
  **Claude Managed Agents, Cursor Cloud Agents, and Devin all run on
  Namespace Devboxes**. This is an agent-execution surface on the
  vendor's own docs — in-lane, not adjacent. Corpus action: filed as
  **C42**. (Machine sizes S→XL, burst 4 vCPU/8 GB → 32 vCPU/64 GB,
  came from a docs snippet this run — recorded at the THIRD-PARTY
  layer, not VERIFIED.)
- **Upstash Box — own-docs VERIFIED (row update, no new C-number).**
  Upstash Box is already a corpus row (2026-09-22 consolidation, C31
  mechanics datapoint); this pass upgrades it from vendor-docs-not-read
  to VERIFIED on the vendor's own docs:
  [Upstash Box quickstart](https://upstash.com/docs/box/overall/quickstart)
  — *"Upstash Box lets you give your AI agents a computer. Every
  Upstash Box is a **secure, isolated cloud container with an AI Agent
  built in**. Spin up as many as you want in parallel. Each one
  includes a full environment with a filesystem, shell, git, and a
  runtime."* Runtimes default Debian (glibc); keep-alive boxes
  (`keepAlive: true`) stay on between sessions; SSH access with a Box
  API key; *"Freeze a box anytime, and continue days or even weeks
  later with perfect resumability."* Pricing THIRD-PARTY (vendor's own
  comparison blog, snippet-only this run): $0.10/$0.20/$0.40 per
  active CPU-hour (small/medium/large); free tier 10 boxes, 5 CPU-h/mo,
  $1 LLM budget, no card required. Corpus action: row update.
- **Ascii Box vetting — RESOLVED to Boat; the unvetted candidate is
  retired.** The midnight pass left "Ascii Box" as an in-lane
  candidate needing own-site verification; the morning pass already
  resolved C40 (ASCII is Boat). This pass adds a harder piece of
  rename evidence, VERIFIED on the vendor's own developer surface:
  [docs.ascii.dev/box/api/v1](https://docs.ascii.dev/box/api/v1)
  renders as **"Boat Public API v1"** — the legacy ASCII domain's
  official API docs brand the product *Boat*. The `/box` URL path and
  the box.ascii.dev endpoints persist; the documented API covers the
  sandbox lifecycle (provisioning → ready/idle → running → archiving →
  archived; stop/archive, resume, fork, delete; desktop streaming;
  `Idempotency-Key`; per-sandbox API keys; data-retention API) and a
  `prompt` endpoint that runs work through built-in agent harnesses
  named `codex`, `claude-code`, `pi`, `opencode`, `prime-agent`, `kimi`
  (provider names verbatim; the surveyor's gloss — codex = OpenAI
  Codex/ChatGPT models, kimi = Kimi Code CLI — is INFERRED).
  Competitive read (INFERRED): Boat's API surface is not just a
  sandbox hoster — it bundles coding-agent harnesses as first-class
  providers. Corpus action: folded into the tracked-set Boat row's
  rename narrative and the C40 provenance note; the standalone
  "Ascii Box" newcomer candidate is retired as vetted.
- **Vercel Sandbox feature churn, Sep 23–24 — snippet-only, no fold.**
  An aggregator of vercel/sandbox releases (releasebot.io,
  snippet-only, THIRD-PARTY) lists: `@vercel/[email protected]`
  — attach sandboxes to Secure Compute networks (`--network-id`,
  SDK `networkId`); CLI `sandbox create` binary-unit size labels
  (KiB/MiB/GiB/TiB); fork now looks up the source before forking and
  warns on stderr when it is running; API requests tagged with the
  detected driving agent (`agent/<name>` in the user-agent, via
  detect-agent). Feature churn, no pricing move, no GA — no fold.
  (Secure Compute networks were already recorded at the THIRD-PARTY
  layer by the 2026-09-23 overnight pass.)
- **OpenAI Agents API "opened to all developers" — dropped on
  evidence rules.** A THIRD-PARTY digest (aiagentstore.ai, week of
  2026-09-24) claims the Agents API "has opened its Agents API to all
  developers." Prior passes recorded the 9/10 public beta
  (the-decoder.com, Sep 11). A digest claim is not enough to upgrade
  a beta→broad-opening verdict, and the Agents API is an LLM/agent
  platform surface — out-of-lane proper. Not folded; watch color only.
- **Deprecated-row sunset convention — still open, still within
  window.** C40 was deprecated this morning (~3–4 passes ago); under
  the proposed 14-pass retention it stays in the corpus regardless.
  The recommendation remains pending corpus-owner approval — not
  codified unilaterally this pass.

## 4. Corpus actions

1. **C42 new — Namespace Devboxes:** field-table row added
   (adjacent → in-lane), VERIFIED on vendor docs
   ([namespace.so/docs/devbox/agents](https://namespace.so/docs/devbox/agents)):
   Linux and macOS devboxes for coding agents; ephemeral Devboxes;
   Pool API (`devbox acquire`); `devbox exec`/`logs`/`upload`;
   `network_policy.egress_domains` egress filtering; secrets via the
   Namespace vault; native integrations — Claude Managed Agents,
   Cursor Cloud Agents, Devin run on Namespace Devboxes. Sizes S→XL
   (burst 4 vCPU/8 GB → 32 vCPU/64 GB) at the THIRD-PARTY snippet
   layer. No published pricing in the surveyed docs.
2. **Upstash Box row update:** own-docs VERIFIED (the quickstart quote
   above); pricing THIRD-PARTY from the vendor's own comparison blog
   ($0.10/$0.20/$0.40 per active CPU-hour; free tier 10 boxes, 5
   CPU-h/mo, $1 LLM budget, no card). Lane cell widened to
   task-scoped sandbox / persistent computer (freeze/resume +
   keep-alive semantics).
3. **Boat rename narrative fold:** docs.ascii.dev now renders "Boat
   Public API v1" (VERIFIED) added to the tracked-set Boat row's
   rename narrative and the C40 provenance note; the standalone
   "Ascii Box" newcomer candidate is retired as vetted (it was Boat
   all along).
4. **No other new C-numbers.** No launches, GA moves, pricing moves,
   or in-lane funding dated 2026-09-24 this pass.

## 5. In-lane and adjacent news scan (2026-09-24, all THIRD-PARTY)

**No new in-lane sandbox-infra items this pass.** Targeted searches
(launches/funding/pricing angles across the full in-lane set plus
generic "agent sandbox" news angles) returned nothing genuinely new
for 9/24. Deliberately dropped as out-of-lane or out-of-window:
Cursor Rollouts + Claude Code Projects GA (9/24, agent products —
out of lane); Alibaba AgentCore + "Agent Native Cloud" at the Apsara
Conference (9/24, managed agent platform — adjacent, out of lane);
Huawei Ascend agent stack (hardware/ecosystem, out of lane);
Crusoe $3.9B Series F at $30.9B (9/17, GPU/data-center AI infra —
the lane's GPU-cloud exclusion applies); Modal $355M (2026-05-21 —
out of window; the ~$15B raise talks stay THIRD-PARTY); the Google
"antigravity-preview-09-2026" managed-agents harness (digest's 9/19
section — out of window; Google's sandbox is already tracked).
Already recorded items had no new in-window developments (Simular
"Sai" GA 9/23, DO Managed Agents preview, Daytona v0.216.0, Docker
v3 kits, Google Agent Substrate, Alibaba FC billing, Tencent Cloud
DataBuddy adjacent, Freestyle C37, Tensorlake C38, Boxd C29).

## 6. Verdict

**Eleventh full quiet 8/8 tracked-set pass since the mid-afternoon
fold, plus a vetting-rich quiet pass.** The core is quiet; the Drives
beta streak extends to 22 passes; C36 unchanged; C41 unchanged. The
new work is all vetting, not launches: Namespace Devboxes is VERIFIED
in-lane on its own docs and becomes **C42** (adjacent → in-lane);
Upstash Box is VERIFIED on its own docs (row update, pricing still
THIRD-PARTY); the Ascii Box newcomer candidate is retired — the
vendor's own API docs at docs.ascii.dev now brand the product **Boat**,
the hardest rename evidence yet, and its `prompt` endpoint reveals
built-in coding-agent harnesses (codex, claude-code, pi, opencode,
prime-agent, kimi) as Boat's first-class providers. Nothing else
moved: no launches, no GA moves, no pricing moves dated 2026-09-24.
