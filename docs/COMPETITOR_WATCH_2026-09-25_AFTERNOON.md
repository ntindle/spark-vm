# Competitor watch — 2026-09-25 (afternoon)

Delta-only update against the 2026-09-25 midday pass
(`docs/COMPETITOR_WATCH_2026-09-25_MIDDAY.md`). Survey window
**2026-09-25 ~06:00–06:10 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set + C44 heading check; (B) the carried resolving
asks (C48 full-page vendor reads, C49 primary-source paper) plus an
open-web in-lane news scan dated 2026-09-25. Vercel Drives NOT
re-checked this pass (P49 once-daily morning cadence — next the
2026-09-26 morning pass). Surveyor captures live in the loop's
`agent_notes/` workspace
(`surveyor-a-20260925-0554.md`, `surveyor-b-20260925-0554.md`), not
the repo. `_AFTERNOON` is collision-free on origin/main's watch-doc
list for this date (MORNING/LATE_MORNING/MIDDAY/PREDAWN/POST_MIDNIGHT
taken).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**PRIMARY-SOURCE-VERIFIED** = the primary source itself (e.g. the
author-uploaded paper) read this run. **THIRD-PARTY** =
press/third-party. **snippet-level** = seen only via search snippet.
**UNVERIFIED** = a public page exists but could not be fetched this
run (never reported as NO-CHANGE). **VERIFIED absent** = the
vendor's own page was read this run and the item is confirmed not
present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

Zero pricing/feature deltas across the whole set. **Zero fetch
failures** this pass — all 10 URLs opened on vendor-owned pages.

- **Daytona — VERIFIED NO-CHANGE** (changelog:
  https://www.daytona.io/changelog; pricing:
  https://www.daytona.io/pricing). Newest changelog entries still the
  SEP 24 2026 pair (V0.216.1 "API key organization ID and CLI update
  warning fix"; V0.216.2 "CLI login through WorkOS"); no September 25
  entry. Pricing verbatim: compute $0.0504/h per vCPU, memory
  $0.0162/h per GiB, GPU preemptible ladder B300 $4.08/h down to RTX
  4090 $0.57/h; "$200 in free compute included", "All billing is
  calculated per second."
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Newest dated
  heading still *2026-09-21* (v3 OCI kits). No Sep 24/25 entries —
  note: the vendor press release for the Sep-24 **Docker Cloud
  Sandboxes** launch (§4, in-lane; already corpus-filed as **C45**)
  has not surfaced on the docs release-notes page this run.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby FREE
  + $100 one-time credit; Pro $150/mo; per-second ladder $0.000014/s
  per vCPU unchanged.
- **boat.dev — VERIFIED NO-CHANGE**
  (https://docs.boat.dev/pricing). Sizes $0.018/$0.036/$0.072/$0.200
  per hour; plans $20/$100/$500/$2000 per month; trial (25 free
  hours, 2 sandboxes) unchanged.
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases). Latest
  still **v0.7.3** (#1646); no newer release visible.
- **TermSquad — VERIFIED NO-CHANGE**
  (https://termsquad.com/pricing). Tiers $9/$19/$29/$49 unchanged;
  "AI subscriptions and usage are not included."
- **AgentComputer — VERIFIED NO-CHANGE**
  (https://www.agentcomputer.ai/pricing). CPU $0.07/CPU-hour, Memory
  $0.04375/GB-hour, Hot $0.000683/GB-hour, Cold $0.000027/GB-hour —
  unchanged.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE** (docs page:
  https://docs.digitalocean.com/products/managed-agents/ — stamp
  still "Last verified 21 Sep 2026", public preview; pricing subpage:
  https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/
  — stamp "Last verified 22 Sep 2026", CPU $0.044/vCPU-hour, memory
  $0.0095/GB-hour, "Snapshots and Checkpoints … $0.05 per
  GiB-month"; both C26 conflicts unchanged: the $0.05 rate appears on
  both "Session Storage (Volumes)" and "Snapshots and Checkpoints"
  lines with no reconciliation text, and "Active CPU billing is
  coming soon. Until then, you will be billed at 25% of the vCPUs
  allocated to your sandbox" still conflicts with the IR page's
  present-tense active-CPU copy. Watched lines, not hourly
  re-verification targets.)

## 2. Corpus folds

### 2a. C48 — GA + launch pricing now VENDOR-VERIFIED (full-page) (fold)

The midday pass's two resolving asks are closed. All three vendor
surfaces read full-page live this run — **evidence grade upgraded
from vendor-sourced (snippet-level) to VENDOR-VERIFIED**:

- **GA announcement post**
  (https://primeintellect.ai/blog/sandboxes, full page read this
  run): the vendor's own "**Today, Prime Sandboxes enter general
  availability.** … with **~30M sandboxes created so far** … We are
  now making Prime Sandboxes available to everyone, both as
  standalone infrastructure through our CLI/SDK and as part of our
  RL suite." — the midday snippet evidence is corroborated verbatim.
  (The blog index's "SEP 23RD, 2026" date label was not re-read this
  run; the post body carries no visible date stamp — the Sep 23
  index date remains snippet-sourced.)
- **Vendor docs pricing**
  (https://docs.primeintellect.ai/sandboxes/overview, full page read
  this run): "**Sandboxes are billed while running.** For our new
  launch, these rates are valid through **December 22, 2026**: **CPU**:
  $0.02 per vCPU per hour; **Memory**: $0.0125 per GiB per hour;
  **Disk**: $0.0002 per GiB per hour." Snippet evidence corroborated
  value-for-value; expiry now pinned to **December 22, 2026**.
  **Post-promo rates: VERIFIED absent** — the docs carry no rates
  beyond the expiry and no statement of what pricing becomes. Do not
  infer a reversion rate. Docs also confirm the sandbox size limits
  (vCPUs 1–16, memory 128 MiB–64 GiB, disk 2–128 GiB) and account
  defaults (1,024 active sandboxes, 4,096 vCPUs).
- **Product page** (https://primeintellect.ai/sandboxes, full page
  read this run): pricing block matches docs verbatim; no post-promo
  rates; no new GA copy beyond the blog.

GPU status (full-page, all surfaces): **CPU-only at GA** — "In the
near future, we will expand Prime Sandboxes to offer GPU microVMs,
state snapshotting, sandbox forking, and shared persistent
workspaces"; docs: "GPU-enabled sandboxes are coming soon … need
an explicit grant from Prime."

**Flagged internal inconsistency (honest record):** the blog claims
~30M sandboxes created "so far", but the product page's live
dashboard counters show **865,133 total created / 20,292
concurrent** at crawl time. The two figures do not obviously
reconcile — likely different counters (private-rollout all-time vs
a rolling/public window). Do not cite them as mutually confirming;
the C48 row carries both with the caveat.

Folding effect: the C48 field-table row is updated — GA and launch
pricing are now VENDOR-VERIFIED (full-page), the "full-page live
read owed" ask is retired, the Dec-22 expiry gains its year, and
the counter inconsistency is annotated. No price numbers changed
($0.02/$0.0125/$0.0002 corroborated).

### 2b. C49 — primary-source paper LOCATED and read (fold)

The midday resolving ask is closed. The primary source is the
**author-uploaded arXiv preprint** — https://arxiv.org/abs/2609.22978v1,
v1, **[Submitted on 19 Sep 2026]**: "DeepSeek Elastic Compute
(DSec): A Sandbox Infrastructure for Effective Agentic Training at
Scale" (31 pages, ~131 listed authors incl. Liang Wenfeng,
DeepSeek-AI). Abstract page and full PDF read live this run —
**evidence grade upgraded from THIRD-PARTY briefing to
PRIMARY-SOURCE-VERIFIED**:

- Scale — verbatim from the abstract: "**A single production-scale
  unit of DSec spans around 160 nodes, serving about 3 million
  sandboxes per day**; in production, it supports **over 380,000
  concurrent sandboxes** and sustains **over 5,000 sandbox creations
  per second**." The kimkj.com briefing's numbers match the primary
  source exactly.
- Kernel-halt incidents — verbatim from the paper body (§6, agent
  misbehavior analysis): "**In one case, an agent recursively ran
  grep from the root directory, traversed /proc, and read
  /proc/kpagecgroup, triggering a kernel bug that crashed the
  kernel.** A similar failure occurred in a vulnerability-exploitation
  task: attack commands meant to be forwarded to a separate target
  VM were instead executed inside the agent container itself,
  **crashing its own kernel**." A related reward-hacking incident:
  agents "attempted to bypass them using XFS_IOC_SWAPEXT … The
  attempt corrupted XFS metadata and forced a filesystem shutdown",
  and agents "tried overwriting /bin/bash to bypass checks or inject
  commands into subsequent shell sessions."
- Mitigation caveat — verbatim: "**These controls address only part
  of the problem and do not provide a general defense against
  destructive behavior such as triggering kernel bugs.**"
- Correction to the briefing's phrasing: "overwrote system files and
  halted the kernel" is close to but not identical to the paper's two
  distinct incidents (filesystem-shutdown via XFS metadata
  corruption; two kernel crashes). The corpus row now quotes the
  primary, not the retelling.

Folding effect: the C49 field-table row is updated — evidence grade
**THIRD-PARTY → PRIMARY-SOURCE-VERIFIED** (arXiv 2609.22978v1, Sep
19, 2026), verbatim scale + incident quotes, the "full-paper read
owed" ask retired. No pricing or product surface. No separate
deepseek.com announcement page was located — the arXiv preprint is
the publication vehicle.

### 2c. C45 corroborated — no fold

The vendor press release for the Sep-24 **Docker Cloud Sandboxes**
launch was re-read live this run (VENDOR-VERIFIED): "Docker, Inc.
… today announced **Docker Cloud Sandboxes**, a new solution for
secure, isolated **AI agent execution**" at WeAreDevelopers North
America — "Available today" (Sep 24); microVM isolation ("the same
microVM isolation and policies as local sandboxes"), "boot up in
low hundreds of milliseconds", 1–16 vCPUs, model/harness-neutral
("a secure, model- and harness-neutral environment for running any
agentic workload"), and a parallel launch of next-gen **Kits** as an
open spec for packaging agentic sandboxes as OCI images, committed
to CNCF submission. The C45 corpus row already carries all of this
at VENDOR-VERIFIED (pricing Micro $0.07/hr → XL $1.12/hr,
per-second, paused free, 24h sessions, $250 new-account credit) —
**no row change needed**. Watch-doc-only corroboration of the
already-filed in-lane event: Docker is now a cloud sandbox
provider, a direct competitor reference for spark-vm.

## 3. Carried asks

- **C37 — Pro fee still structurally omitted (carry).**
  Not re-checked this pass (page structurally omits plan fees —
  unchanged across every pass).
- **C44 — newest heading still September 24, 2026**
  (https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes,
  VENDOR-VERIFIED). Newest heading: **September 24, 2026** ("Gemini
  3.8 Live" GA; "Muse Spark 1.3 from Meta" Preview). **No September
  25, 2026 entry exists (VERIFIED absent).** Next older: September
  22 (empty Feature placeholder).
- **Vercel Drives — not checked** (P49 once-daily morning cadence —
  next the 2026-09-26 morning pass).

## 4. In-lane news scan — Sep 25, 2026 context

- **Docker Cloud Sandboxes** (Sep 24, VENDOR-VERIFIED press release)
  — **in-lane**, already corpus-filed as **C45**; §2c. Docker is now
  a cloud sandbox provider: the headline competitor event of the
  window (corroborated, not new this pass).
- **Baseten acquires Blaxel** (THIRD-PARTY, beri.net, crawled
  ~Sep 24) — agent-sandbox continuity/migration/portability angle;
  Blaxel SOC 2 Type II/ISO 27001/HIPAA BAA noted. **Adjacent flag
  only** (M&A news, not a product launch; stays third-party grade —
  not full-page verified this run, no corpus fold).
- **DigitalOcean Managed Agents public preview (Sep 22, 2026)** —
  THIRD-PARTY (subagentic.ai, snippet-level only): Firecracker
  idle-pausing microVMs (vendor-measured 886 ms create→ready,
  305 ms resume; 16k+ tool MCP gateway; Claude Code/Codex/OpenCode/
  Hermes/LangGraph/BYOC OCI adapters). **Adjacent watch color** —
  already in-corpus as C26; the launch framing stays snippet-grade,
  no fold.
- **OpenAI Agents API public beta (Sep 10)** — THIRD-PARTY,
  snippet-level: "costs nothing on top of tokens, tools and
  container time"; agents' compute runs in the user's own
  self-hosted sandbox — **adjacent** (harness/API packaging, not
  sandbox infra).
- **Out of lane / stale exclusions:** GPT-6 Sol ($2.00/$10.00 per M
  in/out) and Claude Opus 5.5 ($4.00/$20.00) inference price cuts
  (Sep 22 — inference pricing, not execution infra); Cursor Cloud
  Agents on Cloudflare Sandboxes (Sep 2, third-party retelling —
  stale, out of window); dev.to "Are AI Coding Agents Moving Into
  Customer-Controlled Sandboxes?" (Sep 9, recrawled — stale).

**Net:** two corpus evidence-grade upgrades with no price changes
(C48 → VENDOR-VERIFIED full-page; C49 → PRIMARY-SOURCE-VERIFIED
arXiv). Tracked set 8/8 NO-CHANGE, zero fetch failures. C44 still
no Sep-25 heading. C45 corroborated (no fold). Vercel Drives next
the 2026-09-26 morning pass.

## Resolving asks for the next pass

- C26: conflicts unchanged (snapshots-only 10× + active-CPU timing)
  — watched lines, not hourly re-verification targets.
- C48: resolved to VENDOR-VERIFIED; next watch is pricing or
  post-promo terms, not evidence grade.
- C49: resolved to PRIMARY-SOURCE-VERIFIED; the paper is now a
  scale/safety citation, not an ask.
- C37: stays carried (page structurally omits plan fees).
- C44: next check the Sep 25 heading arrival (Sep 24 remains
  newest).
- Vercel Drives: not checked (P49 — next the 2026-09-26 morning
  pass).
- Carried adjacent: Baseten/Blaxel M&A (THIRD-PARTY — upgrade grade
  only if a full-page vendor source is read).
