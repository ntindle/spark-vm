# Competitor watch — 2026-09-25 (morning)

Delta-only update against the 2026-09-25 pre-dawn pass
(`docs/COMPETITOR_WATCH_2026-09-25_PREDAWN.md`). Survey window
**2026-09-25 ~03:55–04:15 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set; (B) the carried asks (C26, C37, C41,
C44, Vercel Drives per the P49 once-daily morning cadence,
Tensorlake, Prime Sandboxes, google/ax), plus an open-web in-lane
news scan dated 2026-09-24/25. Surveyor captures live in the loop's
`agent_notes/` workspace (`surveyor-a-20260925-0354.md`,
`surveyor-b-20260925-0354.md`), not the repo. `_MORNING` admitted
per the nearest precedent (`docs/COMPETITOR_WATCH_2026-09-23_MORNING.md`
family — collision-free on origin/main's watch-doc list for this date).

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
  https://www.daytona.io/pricing). Top 3 still: SEP 24 V0.216.1,
  SEP 24 V0.216.2, SEP 23 V0.216.0 — no new entries; next back is
  SEP 22 V0.215.0. Compute $0.0504/vCPU-h, mem $0.0162/GiB-h,
  storage $0.000108/GiB-h, Windows $0.0858/vCPU/h; GPU ladder
  unchanged (B300 $4.08/h preemptible down to RTX 4090 $0.57/h).
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Still tops
  at **2026-09-21** (v3 kits; `sbx mcp catalog` removed;
  credential-revocation proxy fix; 512 MiB minimum memory); nothing
  dated 09-22 through 09-25.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby
  free + $100 one-time credit / 1h sessions / 20 concurrent; Pro
  $150/mo / 24h sessions / 100 concurrent (expandable to 1,100);
  per-second ladder ($0.000014/s per vCPU) unchanged.
- **boat.dev — VERIFIED NO-CHANGE** (pricing:
  https://docs.boat.dev/pricing). $0.018/$0.036/$0.072/$0.200
  sizes, $20/$100/$500/$2000 plans, $20 never-expire credit packs,
  25h trial (2 sandboxes, small+default only, until first payment);
  "One default sandbox 24/7 = 730 h × $0.036 = $26" verbatim;
  comparison table (E2B/Daytona/Blaxel $0.331 default-hr) unchanged.
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases).
  Latest still **v0.7.3** (release PR #1646).
- **TermSquad — VERIFIED NO-CHANGE**
  (https://termsquad.com/pricing — no 403 this run). $9/$19/$29/$49
  verbatim (2/4/6/8 vCPU, 4/8/12/24 GB, 40/75/100/200 GB NVMe);
  "AI subscriptions and usage are not included." still explicit.
- **AgentComputer — VERIFIED NO-CHANGE, digit-for-digit**
  (https://www.agentcomputer.ai/pricing). $0.07 CPU-hr,
  $0.04375 GB-hr, $0.000683 hot, $0.000027 cold; Enterprise custom.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE**
  (https://docs.digitalocean.com/products/managed-agents/ — "Last
  verified 21 Sep 2026", still public preview for all users; Latest
  Updates still 21 September 2026). Standalone pricing subpage
  stays unlocated — 8th consecutive miss. New THIRD-PARTY color
  (subagentic.ai): $5 new-user credit + 16,000+ tools across 500+
  providers via one MCP Action Gateway — corroborates the filed
  C26 Gateway + credit facts; no pricing change.

## 2. Corpus folds

### 2a. C26 — snapshot-rate attribution RE-OPENED as a vendor-internal conflict (fold)

The mid-evening fold's *"RETIRED in favor of the primary
source"* line (mid-evening §C26 then called the 10×
docs-vs-release gap "live, resolved neither way"; the 9/24 overnight
pass called it "retired as current") is now stale in BOTH
directions — **the vendor disagrees with itself on its own
surfaces.**

New datum this pass (VENDOR-VERIFIED): DigitalOcean's own
investor-relations launch page (investors.digitalocean.com, Sep 22,
2026 — the vendor's own claims, not syndication) states verbatim:
*"Active CPU billing... CPU is billed per second of actual use at
**$0.044 per vCPU-hour** and memory at **$0.0095 per GB-hour**, with
**snapshots at $0.005 per GiB-month**."*

So: the vendor's own launch press names **$0.005/GiB-month as the
Managed Agents snapshot rate**, while the vendor's own pricing
subpage (stamped "Last verified 22 Sep 2026") names
**$0.05/GiB-month**. The two vendor-owned surfaces conflict by 10×
with no correction on either side — i.e. no correction observed on the
IR page this run; the $0.05 figure is carried from the 2026-09-23
mid-evening read (the docs pricing subpage itself stays unlocated,
8th consecutive miss).

Reading (INFERRED): the $0.05 is very likely DO's general-product
(Volumes snapshot) rate bleeding into the Managed Agents pricing
page — the misattribution hypothesis the night passes carried is
now vendor-supported on the $0.005 side. Conservative corpus
handling: the C26 field-table row keeps its `$0.05/GiB-month`
(vendor-pricing-page figure) with the conflict annotated; the
$0.005 attribution to Managed Agents is INFERRED until the pricing
subpage re-check (next pass) settles it. The 8th subpage re-fetch
remains the ask.

**Corpus edit:** new "Watch update — 2026-09-25 (morning)" section
in `docs/COMPETITOR_ANALYSIS.md` carries the full datum +
attribution reading; the C26 entry's *"10× snapshot-rate
discrepancy ... is RETIRED in favor of the primary source"* line
is corrected with a pointer to the morning fold (the primary
sources disagree with each other). Primary-source-verification
fold per the C32 precedent.

### 2b. C44 — release-notes heading MOVED, Sep 22 → Sep 24 (watch color, no fold)

Read https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes
live (VENDOR-VERIFIED). Newest heading: **September 24, 2026** —
two new Feature entries: **Gemini 3.8 Live is generally available**
(voice/model-reliability/orchestration) and **Muse Spark 1.3 from
Meta in Preview** (reasoning model for agentic workflows +
competitive coding, MCP tool calling, 1M-token context). No Sep 23
or Sep 25 entries; Sep-9 "Computer Use and Shell sandboxes GA"
entry still present; Sep-22 heading now renders with an empty
body. Neither new entry is sandbox-shaped — watch color only, no
corpus fold.

### 2c. Retired duplicate candidates

- **google/ax corpus candidate — closed as C47.** Surveyor B's
  recommended new C-number is the already-filed C47: the repo was
  re-opened this run (github.com/google/ax — "Google's open agentic
  orchestration runtime", Apache-2.0 VENDOR-VERIFIED, 10,915 stars /
  529 forks / 633 commits, 6 releases/tags; README's
  "high-throughput, declarative orchestrator ... runs on top of
  **Agent Substrate** for sandboxed execution" re-confirmed). This
  run's releases-page render exposed only v0.1.0 — the v0.3.0
  release specifics (three-service split: ax-server / ax-controller
  / ax-task-runner; task state to Redis Streams; HN top-AI-slot
  ~481 pts) stay THIRD-PARTY-convergent as filed in the pre-dawn
  fold; the quickstart's Redis-first deploy order is consistent
  with the reported state move. Nothing filed.
- **Docker Cloud Sandboxes launch candidate — closed as C45.**
  Surveyor B's THIRD-PARTY launch-facts (The Register 2026/09/24,
  ADTmag, GlobeNewswire wire via financialcontent — same microVM
  isolation as local sandboxes with own kernel; 1–16 vCPUs; boots
  in hundreds of milliseconds; billed by the second; secrets,
  policies, networks, agent config, CloudMCP gateways built in;
  available today) are a second corroboration surface of the
  already-filed C45 event, value-for-value against the filed
  figures. C45's corroboration set is now: vendor blog + keynote
  blog + WeAreDevelopers venue + The Register + ADTmag. Nothing
  filed.

## 3. Carried asks

- **C37 — Pro fee still UNVERIFIED, unchanged.**
  freestyle.sh/pricing re-read (VENDOR-VERIFIED): still no Pro
  dollar line-item (**VERIFIED absent**); the page structurally does
  not publish plan fees — "on paid plans your monthly fee is a
  commitment that doubles as usage credit" + FAQ "$50 on Hobby
  covers your first $50 of usage." Usage rates re-confirmed
  verbatim: $0.04032/vCPU-hr, $0.0129/GiB-hr memory,
  $0.000086/GiB-storage-hr, $0.02/GB transfer; included allowances
  identical on Free/Hobby/Pro (200 vCPU-hr, 400 GiB-hr,
  60,000 GiB-storage-hr/month). Signed-in dashboard check still owed
  (no logins — read-only loop).
- **C26 docs subpage — 8th consecutive miss** (see §2a for the
  attribution re-open; the re-fetch stays the resolving ask —
  the standalone docs page may simply not exist yet for a
  preview product).
- **Tensorlake — no Sep-24/25 news** (stale aggregators only).
  C46 pricing baseline stands.
- **C41 — pin static at `39b6c3a2`.** GitHub API: no new commits
  since 2026-09-21; billing digits stand as pinned (Eco 0.00936
  vCPU-h / 0.004608 GiB-h; Std 0.01224 / 0.006012; Pro 0.01872 /
  0.009360; disk 0.00031896 / 0.00025308 ex-mainland; invite-only,
  allowlisted-in-batches). No action.
- **C43** ("not billed during the preview period" verbatim) and
  **C36** (Cloud Blog text consistent) — confirmed unchanged.
- **C48 Prime Sandboxes — no-op.** No Sep 24–25 Prime news located
  (pre-last-pass THIRD-PARTY items only: prime-agent commit
  976ea108 VM-only `vm=False` hard-fail; Modal roundup 24h timeout,
  CPU-only, GPU on roadmap).
- **boat.dev product-news retry stays RETIRED.**
- **Vercel Drives — still public beta (P49 morning cadence,
  26th consecutive no-change pass).** Read
  https://vercel.com/docs/sandbox/pricing (page stamp
  last_updated 2026-09-10) — "Drives for Vercel Sandbox are now in
  public beta" unchanged; GA not launched. The Drive pricing grid
  ($0.05/GB-month storage, $0.0015/GB reads, $0.004/GB writes
  Pro/Enterprise; Hobby 15 GB storage lifetime / 30 GB-mo
  reads/writes; region-variable, iad1 table; 4 drives/run; default
  1 TiB, 1 GiB Hobby; 16 TiB max quota) is fully specified — these
  digits were already folded VERIFIED at C32 on 2026-09-23; grid
  presence consistent, no fold. Beta terms evolving toward GA shape,
  no GA announcement found.

## 4. Adjacent investor color only (NOT corpus entries)

- **Ando raises $20M** (Sep 24, 2026 — THIRD-PARTY, runtimewire;
  Accel, Index Ventures, Emergence Capital): agent-native team
  messaging (channels/DMs/Jams with agents as participants),
  agent-agnostic (Codex, Claude, Grokbot). Harness-adjacent; flag
  only.
- **Island raises $400M Series F at $6.4B** (Sep 24, 2026 —
  THIRD-PARTY, runtimewire citing Reuters; Evolution Equity
  leading): enterprise browser expanding to AI-agent
  security/governance controls. Adjacent security lane; flag only.
- **Not counted:** Docker Sandboxes CVEs CVE-2026-77179/79994 (host-escape
  research, CVEs published Sep 15 — outside window, fixed in 0.42.0
  Sep 7); Arcade $60M (June 2026 — stale); Cursor Cloud Agents on
  Cloudflare Sandboxes (Sep 2 — outside window); GKE Agent Migration
  Tool (single-source crypto-outlet rumor, UNVERIFIED — not filed).

## 5. What this means for spark-vm

Nothing in this pass moves the tracked pricing floor (8/8 flat for
the sixth consecutive pass). The one substantive move is a
citation-integrity win, not a pricing move: **C26's snapshot rate
is now a vendor-internal conflict** ($0.005 on the vendor's own
investor-relations launch page vs $0.05 on the vendor's own
pricing page) — the corpus's discipline of labeling both and
carrying the conflict explicitly is exactly right, and the 8th
subpage re-fetch stays the resolving ask. Docker's cloud-sandbox
launch is now corroborated on five independent surfaces
(vendor blog + keynote blog + WeAreDevelopers venue + The Register
+ ADTmag) with identical facts — C45 is the corpus's
best-documented competitor launch of the week and anchors the
conference-announcement channel in the launch-playbook read.
Vercel Drives remains beta with the full pricing grid live — when
it GAs, the Drives storage rate ($0.05/GB-month) becomes the first
first-party persistent-storage price in the sandbox lane, worth a
corpus note at GA, not before. Next passes: C26 subpage re-fetch
(8th attempt), C37 signed-in dashboard check, C48 promo-terms
watch.
