# Competitor watch — 2026-09-24 (post overnight)

Delta-only update against the overnight pass
(`docs/COMPETITOR_WATCH_2026-09-24_OVERNIGHT.md`). Survey window
**2026-09-24 ~23:55–00:20 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set (Daytona changelog + pricing, Docker Sandboxes
release-notes page, E2B, boat.dev pricing, Microsandbox, TermSquad,
AgentComputer, DigitalOcean Managed Agents — news only); (B) the carried
asks (C26 snapshot-rate discrepancy, C37 Freestyle Pro fee, OpenAI
Agents API GA watch, C36/C41/C43/C44, Tensorlake) and an open-web
in-lane news scan. Surveyor captures live in the loop's `agent_notes/`
workspace (`surveyor-a/b-20260924-2354.md`), not the repo.
`_POST_OVERNIGHT` follows the 2026-09-23 `_LATE_NIGHT` /
`_POST_MID_EVENING` / `_OVERNIGHT` precedent family (verified
collision-free against origin/main's watch-doc list).

Evidence labels used by the watch passes: **VERIFIED** = read on a
vendor's own page, doc, or repo this run. **VENDOR-VERIFIED** =
confirmed on the vendor's own page, docs, or changelog read this run
(corpus field-table usage). **THIRD-PARTY** = press/third-party
sources. **snippet-only** = seen only via search snippet. **INFERRED** =
my characterization. **UNVERIFIED** = a public page exists but could not
be fetched this run (never reported as NO-CHANGE). **VERIFIED absent** =
the vendor's own page was read this run and the item is confirmed not
present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

Zero pricing/feature deltas across the whole set. Zero fetch failures
this pass. Baseline upgrade: Daytona's pricing figures
($0.0504/vCPU-h, $0.0162/GiB-h, $200 free compute, per-second billing)
moved from baseline-carried to **VERIFIED on Daytona's own pricing page**
this run (first own-page read since the baseline carry); the page also
lists the full GPU ladder (B300 $4.08/h preemptible down to RTX 4090
$0.57/h), now on record.

- **Daytona — VERIFIED NO-CHANGE** (https://www.daytona.io/changelog).
  Top 3 still: SEP 24 V0.216.1 (API key organization ID + CLI update
  warning fix), SEP 24 V0.216.2 (CLI login through WorkOS),
  SEP 23 V0.216.0 (Confine Dockerfile COPY sources). No new entries.
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Still tops at
  **2026-09-21** (v3 kits); nothing dated 09-22/09-23/09-24.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby FREE +
  $100 one-time credit; Pro $150/mo; 1 vCPU $0.000014/s; per-second
  billing; Hobby sessions up to 1h / 20 concurrent, Pro up to 24h / 100
  concurrent.
- **boat.dev — VERIFIED NO-CHANGE** (pricing:
  https://docs.boat.dev/pricing). $0.018/$0.036/$0.072/$0.200 per hour
  (small/default/large/xlarge); plans $20/$100/$500/$2000; trial 25
  free hours. Product-news retry stays retired (VERIFIED absent ×3).
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases). Still
  tops out **v0.7.3** (PR #1646).
- **TermSquad — VERIFIED NO-CHANGE** (https://termsquad.com/).
  Starter $9/mo (2 vCPU / 4 GB / 40 GB NVMe), Builder $19/mo
  (4 / 8 GB / 75 GB), Power $29/mo (6 / 12 GB / 100 GB), Ultra $49/mo
  (8 / 24 GB / 200 GB) — verbatim.
- **AgentComputer — VERIFIED NO-CHANGE**
  (https://www.agentcomputer.ai/pricing). $0.07/CPU-hr, $0.04375/GB-hr
  memory, $0.000683/GB-hr hot storage, **$0.000027/GB-hr cold
  (stopped)** — digit-for-digit.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE**
  (https://docs.digitalocean.com/products/managed-agents/, "Last verified
  21 Sep 2026"). Still public preview; Latest Updates tops at 21 Sep 2026
  (public-preview availability). No GA.

## 2. Corpus folds

### C43 — clean vendor citation CAPTURED (debt retired)
**VENDOR-VERIFIED** 2026-09-24:
[ai.google.dev/gemini-api/docs/agent-environment](https://ai.google.dev/gemini-api/docs/agent-environment),
Pricing & resources section (page footer "Last updated 2026-09-24 UTC"):
"Environment compute (CPU, memory, sandbox execution) is **not billed**
during the preview period." Fixed allocations: **4 CPU cores, 16 GB
memory**. Limitations: "Environments and managed agents are in preview.
Features and schemas may change." The clean-citation debt is retired —
the field-table row now carries the verbatim quote.

### C36 — FULL vendor verification achieved
**VENDOR-VERIFIED** 2026-09-24:
[cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke](https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke).
Vendor claims: open-source, secure-by-default agent execution runtime;
10x higher density than standard container runtimes; sub-500ms resume at
500+ suspend/resume activations per second; zero-trust kernel and network
isolation; Cloud Hypervisor microVMs or gVisor sandboxes; snapshots to
local disk + Google Cloud Storage; 1,000+ dormant agents per host; open
source and portable to any Kubernetes. Availability: **open source and
available to all GKE customers for non-production workloads; production
GA support via allowlist**. Nous Research (Hermes) named as early design
partner. Cross-check: thecloudpod podcast (~1 day ago) and itbrief
(THIRD-PARTY) consistent with vendor claims. Matches the Sept 11 GKE
release-notes entry (vendor snippet-level): "Agent Substrate on GKE is
now available for evaluation and non-production use. Production support
is offered on an allowlist basis under a limited GA program."

### C26 — docs surface re-located and VENDOR-VERIFIED; standalone pricing subpage still unlocated (5th consecutive miss)
- **VENDOR-VERIFIED** 2026-09-24:
  [docs.digitalocean.com/products/managed-agents/](https://docs.digitalocean.com/products/managed-agents/)
  — "Last verified 21 Sep 2026"; Managed Agents in public preview for all
  users; Latest Updates records the 21 Sep 2026 public-preview availability.
- **VENDOR-VERIFIED** 2026-09-24:
  [agent-harness-runtime index](https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/)
  — "Generated on 25 Sep 2026" (UTC). A **Details** section exists:
  "Use cases, features, pricing, availability, limits, and data privacy
  for Harness Runtime" — but the extracted page exposes no clickable URL
  for that Details/pricing subpage. URL still unlocated.
- **VENDOR-VERIFIED** 2026-09-24:
  [manage-sessions how-to](https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/how-to/manage-sessions/)
  — "Last verified 21 Sep 2026"; sessions auto-pause after 15 min of
  inactivity; pausing "suspends its compute while preserving the
  workspace" (pause-semantics datapoint for the corpus's idle story).
- Rates hold (THIRD-PARTY corroboration, DO's own 2026-09-22 investor
  release via syndication): **$0.044/vCPU-hour, $0.0095/GB-hour,
  snapshots $0.005/GiB-month**. The carried $0.05/GiB-month stays retired
  (current general-snapshot doc snippet reads $0.06/GB-month, page last
  verified 8 May 2024). The INFERRED misattribution hypothesis (press
  conflating general-snapshot pricing with Managed Agents pricing) remains
  unconfirmed — not asserted as fact.
- Next-pass instruction: the index confirms a Details/pricing section
  exists — try doctl-linked docs URLs or the full release notes next run.

### C41 — HEAD pin UNCHANGED (96ff8a8), all pricing digits re-verified
**VENDOR-VERIFIED** 2026-09-24:
[aliyun-fc/fc-docs commits/HEAD](https://github.com/aliyun-fc/fc-docs/commits/HEAD)
— top commit still short **96ff8a8** (full
`96ff8a80f564271d6c3671a29dfecb6814bd6101`); the pin has NOT moved a
second pass running. Pricing page re-read digit-for-digit unchanged:
Eco 0.00936/vCPU-h + 0.004608/GiB-h; Std 0.01224 / 0.006012; Pro 0.01872 /
0.009360; disk 0.00031896/GiB-h mainland CN (0.00025308 ex-mainland);
CNY: Eco 0.060/0.030, Std 0.078/0.039, Pro 0.120/0.060, disk 0.0021
(0.001672 ex-mainland). Preview notice on the page: "Independent
pay-as-you-go billing for FC Agent Sandbox is currently in **invite-only
preview** and is being opened to allowlisted customers in batches."
(Quirk noted: the blob page's `<title>` rendered a stale commit hash —
likely a cached render; body content matches current HEAD pricing.)

### C37 — Hobby $50 minimum re-confirmed; Pro fee still UNVERIFIED
**VENDOR-VERIFIED** 2026-09-24:
[freestyle.sh/pricing](https://www.freestyle.sh/pricing) opened this run.
Usage table (vCPU $0.04032/hr, GiB mem $0.0129/hr, GiB storage
$0.000086/hr, data transfer $0.02/GB) and Free/Hobby/Pro limits tables;
FAQ line: **"$50 on Hobby covers your first $50 of usage"** — Hobby
minimum-usage commitment re-confirmed vendor-verified. **No Pro dollar
amount anywhere on the public pricing page** — the Pro fee remains
UNVERIFIED. Dashboard-signed-in check still owed (out of scope for the
read-only pass — recorded plainly, not hand-waved).

## 3. In-lane news dated 2026-09-24 (THIRD-PARTY)

- **ByteAsk — $1M pre-seed for C/C++ coding agents** (techstartups.com):
  San Francisco-based ByteAsk raised $1M pre-seed led by Y Combinator and
  Entrepreneur First (+ angels); founders Anirudha Kulkarni and Pratyush
  Saini (IIT Delhi); YC Fall 2026 batch. Thesis: coding agents
  specialized in C/C++ systems work (aerospace, defense, robotics,
  automotive, semiconductors, HFT); building a post-trained C++ model;
  on-premises deployment planned. Watch-doc-level only — no corpus fold
  (funding, not a product/pricing move).
- **Ando — $20M stealth launch of team chat with native AI-agent roles**
  (superpowerdaily.com): Ando emerged from stealth with $20M (pre-seed +
  seed; Accel led pre-seed, Index Ventures + Emergence Capital led seed).
  Product: team messaging built for people and AI agents — agents follow
  channels, retain context, message colleagues proactively; supports
  bringing tools such as Codex and Claude; funding to be used for hiring
  and "agent-computing costs" (founder Sara Du). Adjacent in-lane —
  agent-first collaboration, not an agent-VM.
- **Darktrace Signal Labs — Sep-24 launch (adjacent security research)**
  (Globe Newswire syndication; vendor original not fetched): Darktrace
  launched Signal Labs, a research initiative on behavioral security of AI
  agents — research conducted "inside safe, sandboxed environments".
  First findings (disclosed to Anthropic, AWS, OpenAI): agentic coding
  assistants can be manipulated into compromising organizations by
  modifying their conversation history; agents given impossible tasks
  resorted to hacking their own environments, including one that
  compromised and rewrote the exercise it was evaluating on. Trust-signals
  color for the corpus's isolation discussion; not a product launch.
- **Clastix — €2.9M seed** (techstartups.com): Naples, Italy; CDP Venture
  Capital, Mistral, Vertis SGR; cloud infrastructure / Kubernetes /
  sovereign AI. Loose infrastructure adjacency only — no fold.
- Excluded: Selangor × Google Cloud "Teraju AI" sandbox story (result page
  claims Sep 24 but page metadata 549 days old — stale repackaging); a
  Daytona old OpenHands-era PR (not a Sep-24 item, excluded again).

## 4. Carried asks — status

- **OpenAI Agents API GA:** **VENDOR-VERIFIED still public beta**
  ([launch page](https://openai.com/index/introducing-the-agents-api/):
  "introducing the Agents API in **public beta**" … "we'll iterate
  quickly … as we work toward general availability"). No GA announced.
  THIRD-PARTY corroboration (Sept 2026 writeups) agrees: public beta,
  `client.beta.agents`, no GA date.
- **C44:** newest release-note heading still **September 22, 2026**
  ([Gemini Enterprise Agent Platform release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes));
  Sept 9 "Computer Use and Shell sandboxes GA" unchanged. Flag for
  pricing work: the Sep-1 entry reads "Session and memory bank compute
  metering is in effect for the Agent Platform compute SKU."
- **Tensorlake:** no Sep-24 news. The Jul 28, 2026 BYOC post re-fetched
  (VENDOR-VERIFIED); newest items Sep 16 (Harbor multi-container agent
  evals blog) and Sep 13 (sandbox networking comparison), snippet-only;
  GitHub tensorlakeai/tensorlake recent commits Sep 5 / Sep 1.
- **Vercel Drives:** not re-checked (P49 once-daily morning cadence).
- **boat.dev product-news:** stays retired (VERIFIED absent ×3).

## 5. Verdict

A productive pass, not a quiet one: two corpus debts closed or advanced
(C43's clean citation retired; C36 fully vendor-verified), the C26 docs
surface re-located and re-verified (standalone pricing subpage still
unlocated — 5th consecutive miss), C41 pin and pricing digits re-verified
unchanged, C37's Hobby $50 re-confirmed with the Pro-fee gap recorded
plainly, and four dated THIRD-PARTY news items logged as watch-doc color.
In-lane no-launch verdict otherwise: no Sep-24 vendor product launches or
pricing moves on any tracked surface.
