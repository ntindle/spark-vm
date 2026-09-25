# Competitor watch — 2026-09-25 (midday)

Delta-only update against the 2026-09-25 late-morning pass
(`docs/COMPETITOR_WATCH_2026-09-25_LATE_MORNING.md`). Survey window
**2026-09-25 ~05:00–05:20 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set; (B) the carried asks (C26 blast radius,
Prime Sandboxes vendor-primary (C48), C37, C44, google/ax,
Tensorlake) plus an open-web in-lane news scan dated 2026-09-24/25.
Vercel Drives NOT re-checked this pass (P49 once-daily morning
cadence — next the 2026-09-26 morning pass). Surveyor captures live
in the loop's `agent_notes/` workspace
(`surveyor-a-20260925-0454.md`, `surveyor-b-20260925-0454.md`), not
the repo. `_MIDDAY` admitted per the 2026-09-23 `_LATE_MORNING`
precedent — collision-free on origin/main's watch-doc list for this
date.

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run. **THIRD-PARTY** =
press/third-party. **snippet-only** = seen only via search snippet.
**INFERRED** = my characterization. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read this
run and the item is confirmed not present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

Zero pricing/feature deltas across the whole set. **Zero fetch
failures** this pass — all 8 surfaces opened on vendor-owned pages.

- **Daytona — VERIFIED NO-CHANGE** (changelog:
  https://www.daytona.io/changelog; pricing:
  https://www.daytona.io/pricing). Top entries still SEP 24 V0.216.1
  ("API key organization ID and CLI update warning fix"), SEP 24
  V0.216.2 ("CLI login through WorkOS"); no new entries. Compute
  $0.0504/h per vCPU, Memory $0.0162/h per GiB, GPU ladder B300
  $4.08/h down to RTX 4090 $0.57/h — unchanged.
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Latest entry
  still *2026-09-21* (v3 OCI kits).
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby
  FREE + $100 one-time credit; Pro $150/mo; per-second ladder
  ($0.000014/s per vCPU) unchanged.
- **boat.dev — VERIFIED NO-CHANGE**
  (https://docs.boat.dev/pricing). Sizes $0.018/$0.036/$0.072/$0.200
  per hour; plans $20/$100/$500/$2000 per month; unchanged.
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases). Latest
  still **v0.7.3**; no new release since.
- **TermSquad — VERIFIED NO-CHANGE**
  (https://termsquad.com/pricing). $9/$19/$29/$49 tiers unchanged.
- **AgentComputer — VERIFIED NO-CHANGE**
  (https://www.agentcomputer.ai/pricing). CPU $0.07/CPU-hour, Memory
  $0.04375/GB-hour, Hot storage $0.000683/GB-hour, Cold storage
  $0.000027/GB-hour — unchanged.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE** (docs page:
  https://docs.digitalocean.com/products/managed-agents/ — "Last
  verified 21 Sep 2026" still shown; public preview).

## 2. Corpus folds

### 2a. C26 — the 10× conflict is SNAPSHOTS-ONLY; a second conflict surfaces on active-CPU billing timing (fold)

The midday pass scoped the blast radius the late-morning pass left
open. The IR launch page
(https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Launches-Managed-Agents-Bringing-Agent-Execution-Tool-Access-and-Inference-Together-on-One-Cloud/default.aspx
— read live this run; no explicit date stamp in fetched text, URL
path `/2026/`, syndicated Business Wire copies timestamped
"September 22, 2026 at 11:00 AM EDT") carries the verbatim line
(VENDOR-VERIFIED): "CPU is billed per second of actual use at $0.044
per vCPU-hour and memory at $0.0095 per GB-hour, with snapshots at
$0.005 per GiB-month." The docs pricing subpage
(https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/
— read live this run; stamp still **"Last verified 22 Sep 2026"**)
names CPU **$0.044 per vCPU-hour**, memory **$0.0095 per GB-hour**,
Session Storage / Volumes **$0.05 per GiB-month**, Snapshots and
Checkpoints **$0.05 per GiB-month**, Custom Sandbox Templates (BYOT)
**$0.05 per GiB-month**, Public Internet Egress **$0.01/GiB**.

**Blast-radius verdict (VENDOR-VERIFIED on both surfaces): the 10×
disagreement is snapshots-only.** Compute and memory rates agree
exactly ($0.044/vCPU-hour, $0.0095/GB-hour). Only snapshots
disagree: IR page "$0.005 per GiB-month" vs docs "Snapshots and
Checkpoints … $0.05 per GiB-month". This NARROWS the conflict: the
misattribution hypothesis (general-product Volumes rate bleeding
into the docs page) now applies specifically to the snapshot line,
not the whole pricing table.

**Second conflict surfaced (footnote-level, VENDOR-VERIFIED on both
sides):** the IR page's present-tense "Active CPU billing charges
developers only for CPU cycles their agents consume" conflicts with
the docs subpage's footnote: "Active CPU billing is coming soon.
Until then, you will be billed at 25% of the vCPUs allocated to
your sandbox." The IR page presents active-CPU billing as live; the
docs say it is not. Both are DO-owned, both current, no correction
on either.

Conservative handling (C32 precedent, unchanged): the C26
field-table row keeps `$0.05/GiB-month` (pricing-page figure) with
the conflict annotated; the $0.005-as-Managed-Agents attribution
stays INFERRED. The standing watch item remains the conflict(s)
themselves — now scoped, not re-verified hourly.

### 2b. C48 — Prime Sandboxes GA is vendor-sourced (snippet-level); launch pricing folded (fold)

Vendor blog (primeintellect.ai: "Prime Sandboxes: MicroVMs for
Agentic RL Training at Scale" —
https://primeintellect.ai/blog/sandboxes): blog index read live this
run, stamped "Announcements **SEP 23RD, 2026**"; post body reached
via search snippet (full-page live read still owed for verbatim
quotes) carrying the vendor's own words: "**Today, Prime Sandboxes
enter general availability.**" and "We are now making Prime
Sandboxes available to everyone, both as standalone infrastructure
through our CLI/SDK and as part of our RL suite." ~30M sandboxes
created during the private rollout. Vendor product page
(primeintellect.ai/sandboxes) showed live counters at crawl time:
20,292 concurrent sandboxes, 865,133 total created, 0.0% error
rate. Hardware-virtualized guest kernels (explicitly not gVisor);
agents get system access for Docker Compose, background services,
filesystem modification, long-running tasks — THIRD-PARTY color
(AlphaSignal, carried from the 2026-09-25 late-morning pass; this
pass did not re-verify these capability details).

Launch pricing (from vendor docs,
docs.primeintellect.ai/sandboxes/overview, "Last Updated: 1 day
ago" — quoted via search snippet; the corpus pricing line is
upgraded from AlphaSignal-THIRD-PARTY to vendor-sourced-but-snippet,
full-page read still owed): CPU **$0.02 per vCPU per hour**, Memory
**$0.0125 per GiB per hour**, Disk **$0.0002 per GiB per hour**;
rates **valid through December 22, 2026** — no post-promo rates
published. Corroborates the C48 corpus numbers ($0.02/$0.0125/
$0.0002). One vCPU/1 GiB/32 GiB ≈ $0.0389/hr. CPU-only at launch —
GPU microVMs, state snapshots, sandbox forking, shared persistent
workspaces on the roadmap. Stale counter-datum: third-party
ecosystem skill notes (prime-agent repo, 22 days old) quote older,
higher rates (CPU $0.05/core/hr) — superseded; vendor docs are
authoritative.

Folding effect: C48's THIRD-PARTY launch report is now
vendor-sourced-but-snippet on both the GA fact (vendor blog —
index read live, post body via snippet) and the launch pricing
(vendor docs, via snippet). VENDOR-VERIFIED is still owed on both
(full-page live reads); the corpus row's "vendor-primary
verification owed" ask stays open.

### 2c. C49 new — DeepSeek DSec "agent training infrastructure" paper (in-lane, THIRD-PARTY)

In-lane item surfaced by the midday news scan: DeepSeek published
a 2026-09-25-dated "agent training infrastructure" paper (the
"DSec" paper, per China AI briefing via kimkj.com — THIRD-PARTY):
"**Operating 3 million experimental sandbox environments
daily**" with documented incidents where agents "overwrote system
files and halted the kernel". This is a scale datapoint (3M
sandbox-envs/day — an order of magnitude above Prime's ~30M
cumulative / 865k-total counters) and failure-mode evidence
(kernel-halting agent escapes) relevant to the sandbox safety
posture. No pricing or product surface — pure scale/safety color.
Full-paper read owed if it becomes verifiable (primary source not
yet located).

## 3. Carried asks

- **C37 — Pro fee still structurally omitted (carry).**
  https://www.freestyle.sh/pricing re-read live this run
  (VENDOR-VERIFIED): still no Pro dollar amount anywhere on the
  public page. Usage rates unchanged ($0.04032/vCPU-hr,
  $0.0129/GiB-hr memory, $0.000086/GiB-storage-hr, $0.02/GB data
  transfer; allowances unchanged). The FAQ still references an
  unpublished fee ("$50 on Hobby covers your first $50 of usage" —
  Hobby example only).
- **C44 — newest heading still September 24, 2026**
  (https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes,
  VENDOR-VERIFIED). Newest heading: **September 24, 2026** with two
  entries ("Gemini 3.8 Live" GA; "Muse Spark 1.3 from Meta" Preview
  — reasoning model for agentic workflows, MCP support, 1M-token
  context). **No September 25 entry exists** (VERIFIED absent). Next
  older headings: September 22 (empty Feature placeholder),
  September 21 (CodeMender v0.9.0).
- **google/ax — watch color (no fold):** 10,969 stars (+27 vs the
  late-morning pass — the identical +27 increment is coincidence),
  532 forks (+1), 633 commits (unchanged), head `e09ed1bc…`,
  Apache-2.0 unchanged; README model pin `gemini-3.8-flash`
  (VENDOR-VERIFIED). Latest-release identity UNVERIFIED this pass
  (count 6 confirmed; rendered text only surfaced v0.1.0 dated
  May 20).
- **Tensorlake — quiet in-window:** no dated news 2026-09-24/25.
  Latest dated items: repo PRs #981 (create_tunnel Python SDK,
  2026-09-21) and #982 (cloud-sdk replay filesystem, 2026-09-20);
  1011 stars. The TowardsAI "AI Sandbox Networking Compared:
  Tensorlake vs E2B vs Daytona vs Fly.io" piece is Sep 2026 but
  undated (~11 days old) — out of window.

## 4. In-lane news scan — Sep 24–25, 2026

- **DeepSeek DSec paper** (Sep 25, THIRD-PARTY briefing): **in-lane**
  — filed as **C49** (§2c): 3M sandbox envs/day, kernel-halt
  incidents. Scale + safety color.
- **Dataiku launches Agent Management** (announced Sep 24 at the
  Succeed conference NYC; GA planned Oct 2026, THIRD-PARTY Business
  Wire) — **adjacent**: standalone product inventorying enterprise
  agents across AWS Bedrock, Databricks Agents, Google Vertex,
  Copilot Studio, Azure Foundry, Agentforce, Snowflake Cortex;
  "priced per instance annually with monitoring metered per agent".
  Agent governance adjacent to sandbox execution, not execution
  itself. Flag only.
- **Ando out of stealth** (Sep 24, THIRD-PARTY aiagentstore.ai) —
  **adjacent**: "AI-native team chat that gives agents real
  identities and inboxes"; $20M pre-seed/seed. Agent
  identity/coordination infra, not sandboxed execution. Flag only.
- **Google Project Suncatcher confirmed** (Sep 24, THIRD-PARTY
  tech-insider.org) — **adjacent**: Google testing TPUs in orbit;
  prototype satellite launches Oct 1. AI infra capacity play.
- **Out of lane / stale exclusions:** GPT-6 Sol + Claude Opus 5.5
  model price cuts (Sep-25 briefing — inference pricing, not
  execution infra). OpenClaw Direct "managed hosting" and Optivian
  sales agents (ABNewswire) are **recrawls of Feb 2026-era releases**
  mislabeled with "Friday - September 25, 2026" headers (Last
  Updated: 212 and 234 days ago) — not fresh news.

**Net:** one corpus fold pair (C26 conflict scoped + second conflict
surfaced; C48 vendor-sourced (snippet-level)) and one new in-lane C-entry (C49
DeepSeek scale/safety color). Otherwise the lane is quiet — no
pricing moves, no new launches.

## Resolving asks for the next pass

- C26: the conflict is now scoped (snapshots-only) — re-verify
  hourly cadence is wasted on a static vendor-internal conflict;
  carry the conflict + second conflict as watched-line items only.
- C48: remaining ask is a full-page live read of the vendor docs
  pricing page (currently snippet-level evidence).
- C49: primary-source paper read owed if locatable.
- C37: stays carried (page structurally omits plan fees).
- C44: next check the Sep 25 heading arrival (Sep 24
  remains newest).
- Vercel Drives: not checked (P49 once-daily morning cadence —
  next the 2026-09-26 morning pass).
