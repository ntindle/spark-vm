# Changelog

All notable changes to spark-vm are recorded here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/). The version lives in the
`VERSION` file at the repo root (see `docs/VERSIONING.md`); this file is
its human-readable companion.

## The changelog ritual

This changelog only works if entries land with the change, not after it:

1. **Every PR that changes anything user- or operator-visible adds one or
   two bullets under `## [Unreleased]`**, in the right section
   (`Added` / `Changed` / `Fixed` / `Security`). Write for the person
   running spark-vm, not the person who wrote the diff — no file paths,
   function names, or internal audit numbering — and link the PR number.
   Reviewers request changes when the entry is missing: it's a merge gate,
   not a suggestion (see `CONTRIBUTING.md`).
2. **Trivial scope** (typo, single-line doc fix, formatting) doesn't need an
   entry; merge notes are enough. **Seeding-batch exemption:** PRs authored
   before this ritual merged (the 2026-09-19 queue-drain batch) are exempt —
   the per-PR entry rule applies prospectively from this PR's merge.
3. **At release time**, the release commit (the `VERSION` bump — see
   `docs/VERSIONING.md`, "Cutting a release") moves the whole
   `## [Unreleased]` section into `## [0.2.0] - YYYY-MM-DD` (pattern:
   `## [x.y.z] - YYYY-MM-DD`), adds the compare links in the footer
   scaffold at the bottom of this file (uncomment and fill it in), and
   leaves a fresh empty `## [Unreleased]` section behind for the next PR.
4. Docs are a first-class product here, so anything merged under `docs/`
   gets an entry like a feature. Notes that never land in the repo — e.g.
   the loop's working notes in its `agent_notes/` workspace (not part of
   this repo) — don't get entries.
5. **A revert is a change too**: the revert PR gets its own entry noting
   the reversal, so the changelog reads forward in time.

## [Unreleased]

### Added
- Competitor corpus update (mid-afternoon watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 11 checks opened on vendor-owned pages, first-try fetches). **No new C-numbers.** Adjacent-color grade upgrade: Meta Muse VM-filesystem-export second disclosure (Sep 25, THIRD-PARTY — explainx.ai update + ai0.news digest: Muse can be prompted to hand over its entire VM root filesystem; Meta spokesperson says expected behavior in a personal Linux VM while Muse itself refused then apologized; "second Muse security disclosure in a week" — vendor-spokesperson response upgrades the carried watch-only snippet but no vendor-primary page; filed adjacent, below the C-number bar). **Dedupe:** Surveyor B's BAND × Docker Sandboxes Kit candidate is already corpus (C45 garnish + 2026-09-24 pre-midnight section) — no double-file. Carried-lead resolutions: C52 Kits-v2 follow-up RESOLVED (sbx-CLI kit scheme `schemaVersion: "2"` is distinct from the OCI Kit Spec — no file); C54 primary-source read PARTIAL (Perplexity blog URL located but 403 — read stays carried); Island company-announcement read RESOLVED (GlobeNewswire: $400M led by Evolution Equity Partners, $6.4B, "agentic control plane" framing — fundraiser, no file). Carried: C37 Pro fee still structurally omitted, C44 newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), C26 conflicts unchanged (watched lines), C54 primary-source read, C55 primary-source read (blog.cloudflare.com disclosure), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: Transluce agent-swarm research (marginal, snippet-level), DeepSeek DSec third-party coverage (already corpus), Docker C45/C52 third-party reprints (commentary, no new facts), OpenClaw Direct (conflicting dates, marginal lane), Whiteboard YC (IDE), SandboxAQ/Selangor (name collisions/out of lane). In-lane no-launch verdict dated 2026-09-25 (#424).
- Competitor corpus update (early-afternoon watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 11 URLs opened directly on vendor-owned pages). **One adjacent filing: C55 new** (Cloudflare Containers/Sandboxes cross-tenant disk-residue flaw, disclosed Sep 24–25, THIRD-PARTY: dm-thin `skip_block_zeroing` let reused 64 KiB blocks leak prior tenants' directory listings, SQLite DBs, Chromium profiles, `.env`/credential files; reported Sep 4 by Oren Yomtov/Accomplish via HackerOne, cleanup done Sep 19, no evidence of malicious exploitation — filed adjacent per the C54 precedent, directly relevant to spark-vm's sandbox threat model: multi-tenant disk wipe discipline). Deliberately not filed: C50 Sep-25 press corroboration (no grade change), Zoho Catalyst 3.0 (Sep-2 vintage reprint), Google antigravity (Sep-17 vintage), DO Managed Agents (Sep-23 vintage), Docker Cloud Sandboxes explainer (C45 already corpus), Baseten/Blaxel dedupe (C11), Meta Muse snippet (watch-only), DeepSeek "leak" (UNVERIFIED), Guava name collision, stale E2B Series A, vintage Vercel integrations. Carried: C37 Pro fee still structurally omitted, C44 newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), C26 conflicts unchanged (watched lines), C52 follow-up lead (Kits v2 mechanics), C54 primary-source read (Perplexity's own post), C55 primary-source read (blog.cloudflare.com disclosure), Island announcement read (Reuters wire as cited), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25 (#423).
- Competitor corpus update (post-mid-morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 11 URLs opened directly on vendor-owned pages). **One adjacent filing: C54 new** (Perplexity "Escaping SPACE: Part I", Sep 23/24, THIRD-PARTY: frontier-model red team of a Firecracker microVM sandbox — 0/108 escapes, egress allowlist bypassed 11/54, authority-switch bypasses reproduced in 8/10 third-party platforms — directly relevant to spark-vm's sandbox threat model). Adjacent color (NOT corpus): Island $400M Series F at $6.4B (Sep 24, THIRD-PARTY — a fundraise, not a shipped surface; below the C-number bar). **No Baseten/Blaxel fold** (acquisition is corpus C11; beri.net continuity analysis already logged as adjacent color). Carried: C37 Pro fee still structurally omitted, C44 newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), C26 conflicts unchanged (watched lines), C52 follow-up lead (Kits v2 mechanics), C54 primary-source read (Perplexity's own post), Island company announcement read (Reuters wire as cited), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: C50 press corroboration (no grade change), DeepSeek DSec Harness "leak" (UNVERIFIED single source), Meta Muse Mac VM-filesystem-export snippet (no vendor confirmation). In-lane no-launch verdict in-window (#421).
- Competitor corpus update (mid-morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 11 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21; Microsandbox still v0.7.3 #1646). **Three corpus moves: C50 evidence upgrade** (Microsoft Copilot Managed Runtime — **THIRD-PARTY → VENDOR-VERIFIED**: Microsoft's own Sep-25 announcement post read in full, "hosting infrastructure that lets code run safely right inside your company's Microsoft 365 environment", tenant-boundary governance, Autopilot identity/memory/computer/workspace, UBB billing); **C52 new** (Docker Sandbox Kit Spec open-sourced under Apache 2.0 + committed to CNCF — **VENDOR-VERIFIED**, announced ~Sep 24, companion to C45); **C53 new** (Ando out of stealth + $20M — **THIRD-PARTY**, filed adjacent: messaging-layer agent participation infra). Carried: **C37** Pro fee still structurally omitted, **C44** newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), C26 conflicts unchanged (watched lines), C52 follow-up lead (Kits v2 mechanics), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: Meta Muse VM-filesystem-export snippet (no vendor confirmation), DeepSeek DSec Harness "leak" (UNVERIFIED single source) (#420).
- Competitor corpus update (post-night watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 11 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21). **Three corpus moves: C45 evidence upgrade** (Docker's own Sep-24 Cloud Sandboxes press page now live — **VENDOR-VERIFIED**, full-page read: "available now", boot in low hundreds of ms with secrets/policy/MCP gateways/agent config built in, 1–16 vCPUs Docker-managed, Kits-as-standard-OCI + CNCF submission); **C50 new** (Microsoft Copilot Managed Runtime public preview, **THIRD-PARTY**, Sep-25-dated: tenant-boundary code hosting under IT governance, SDK + CLI for third-party developers, Code to Frontier end of September 2026 — enterprise-adjacent competitive pressure on "run my agent somewhere safe"); **C51 new** (Gemini `antigravity-preview-09-2026` harness — carried ask closed: **VENDOR-VERIFIED** vendor docs, harness string + `environment = "remote"`, Files API + Credentials API with runtime secret injection — Sep-17/18 vintage, not Sep-25 news). Carried: **C37** Pro fee still structurally omitted, **C44** newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), C26 conflicts unchanged (watched lines), C50 grade upgrade pending a Microsoft announcement-page read, Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: DeepSeek DSec Harness "leak" (single unverified source). Out of lane: misdated ABNewswire recrawls, Daytona SDK dep bumps, inference price cuts, Salesforce outcome pricing, Anthropic 1GW datacenter, Qualcomm–AWS (#419).
- Competitor corpus update (night watch): full-quiet pass — tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 11 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21). **No corpus fold; no new C-numbers** — the one in-lane fold candidate (DO Managed Agents IR press release detail: 305 ms resume, $0.044 active-CPU, Action Gateway, "37% lower TCO") dedupes to the already-filed **C26** deep-dive. Carried: **C37** Pro fee still structurally omitted (ask stays open), **C44** newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent; this pass re-checked the real Google page, superseding the evening mislabel-carry), C26 conflicts unchanged. Adjacent watch color only (NOT corpus): Microsoft Copilot Sep-25 revamp (sandbox-by-default "Code" builds, tenant hosting), Gemini antigravity-preview-09-2026 digest lead (snippet-level, date unverified). Deliberately not filed: DeepSeek DSec Harness "leak" (single unverified source). Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass) (#418).
- Competitor corpus update (evening watch): full-quiet pass — tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 10 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21). **No corpus fold; no new C-numbers** — the open-web scan surfaced no genuinely new in-lane moves (all three in-lane items dedupe to already-filed entries: **C45** Docker Cloud Sandboxes, **C26** DO Managed Agents — $5 credit + partners already in the row; 886/305 ms benchmarks already in the watch-doc trail, reported THIRD-PARTY —, **C48** Prime Sandboxes GA). Carried: **C37** Pro fee VERIFIED absent on all public login-free surfaces (stays open; dashboard-signed-in check owed), **C44** NOT re-checked this pass (the surveyor brief's Docker-page "C44" label was a mislabel, corrected — the real Google release-notes heading check carries to the 2026-09-26 morning pass). Anti-chase note: Daytona "agent-agnostic infrastructure" OpenHands PR is recrawled-old syndication (page stamps 633–3045 days). Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Adjacent only (NOT corpus): Baseten/Blaxel (9/10), AWS AgentCore V2 GA (9/18), Cloudflare+Cursor Sandboxes (9/2) — out of window. Out of lane: GPT-6 Sol/Luna + Claude Opus 5.5 inference price cuts (model pricing) (#417).
- Competitor corpus update (afternoon watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 10 URLs opened directly on vendor-owned pages). **Corpus folds: C48 GA + launch pricing VENDOR-VERIFIED (full-page)** — the midday resolving asks are closed: vendor GA post body read live, corroborating "Today, Prime Sandboxes enter general availability" and "~30M sandboxes created so far" verbatim; vendor docs pricing corroborated value-for-value ($0.02/vCPU-hr + $0.0125/GiB-hr + $0.0002/GiB-hr), expiry pinned to **December 22, 2026**, **post-promo rates VERIFIED absent**; CPU-only at GA (GPU microVMs + snapshots + forking = roadmap); **flagged inconsistency**: blog ~30M vs product-page live counters 865,133 total / 20,292 concurrent — not mutually confirming. **C49 PRIMARY-SOURCE-VERIFIED** — author-uploaded arXiv 2609.22978v1 ("DeepSeek Elastic Compute (DSec)", 31 pp, submitted 19 Sep 2026): ~3M sandboxes/day per 160-node unit, >380k concurrent, >5k creations/sec; paper documents two agent-triggered kernel crashes plus an XFS_IOC_SWAPEXT reward-hack filesystem shutdown; caveat: "These controls address only part of the problem and do not provide a general defense against destructive behavior such as triggering kernel bugs." **C45 corroborated, no fold** (vendor press release re-read live — Docker Cloud Sandboxes Sep-24 launch already VENDOR-VERIFIED in corpus). Carried: C37 Pro fee still structurally omitted, C44 newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Adjacent only (NOT corpus): Baseten/Blaxel M&A (THIRD-PARTY), DO Managed Agents Sep-22 preview framing (snippet-level; already C26), OpenAI Agents API public beta (Sep 10). Out of lane: GPT-6 Sol + Claude Opus 5.5 inference price cuts, stale recrawls (#416).
- Competitor corpus update (midday watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages). **Corpus folds: C26 conflict SCOPED — the 10× disagreement is snapshots-only** (compute $0.044/vCPU-hour and memory $0.0095/GB-hour agree exactly on the IR launch page and the docs pricing subpage, both re-read live; only Snapshots and Checkpoints disagree — $0.005 IR vs $0.05 docs) **and a second conflict surfaces** (IR page presents active-CPU billing as live vs docs footnote "coming soon", interim 25% of allocated — VENDOR-VERIFIED both surfaces); field-table row updated, $0.05 figure kept with conflicts annotated. **C48 GA vendor-sourced (snippet-level)** (primeintellect.ai blog, index "SEP 23RD, 2026" read live; GA line and launch pricing via vendor-post/vendor-docs snippets — full-page reads owed — "Today, Prime Sandboxes enter general availability"; ~30M sandboxes in private rollout; launch pricing $0.02/vCPU-hr + $0.0125/GiB-hr + $0.0002/GiB-hr through Dec 22, 2026; repaired the pre-dawn C48 row's truncated tail). **C49 new** (DeepSeek DSec paper, THIRD-PARTY: 3M sandbox envs/day, kernel-halt agent incidents — scale/safety color). Carried: C37 Pro fee still structurally omitted (no plan dollar amounts live), C44 newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), google/ax 10,969 stars (+27) / `gemini-3.8-flash` README pin (watch color, no fold), Tensorlake quiet in-window; Vercel Drives not re-checked (P49 morning cadence); adjacent only (NOT corpus): Dataiku Agent Management (Sep 24, GA planned Oct 2026), Ando out of stealth ($20M), Google Project Suncatcher; out of lane: GPT-6 Sol / Claude Opus 5.5 inference cuts, ABNewswire Feb-2026 recrawls mislabeled Sep 25 (#415).
- Competitor corpus update (late-morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **corpus fold: C26 docs pricing subpage LOCATED and read live — "unlocated" framing retired** (the 8-miss streak was a discovery/indexing failure (INFERRED): the page loads at the carried URL but is undiscoverable via search; stamp still "Last verified 22 Sep 2026", $0.05/GiB-month confirmed live — the 10× vendor-internal conflict stands: IR launch page still $0.005/GiB-month, no correction; new THIRD-PARTY support for the misattribution hypothesis — general-product Droplet/Volume snapshots $0.05/GB-month nominal-value-for-value with the docs figure (GB vs GiB units differ); field-table keeps $0.05 with the conflict annotated). **C47 watch color** (google/ax 10,942 stars +27, README example now `gemini-3.8-flash` — VENDOR-VERIFIED), **C48 corroborating color** (THIRD-PARTY ~Sep 23: Prime Sandboxes general access opened — vendor verification owed). Carried: C37 Pro fee still UNVERIFIED, C44 newest heading Sep 24 (no Sep 25 entry), C41 pin static, Tensorlake no Sep-24/25 news (#414).
- Competitor corpus update (morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **corpus fold: C26 snapshot-rate attribution RE-OPENED as a vendor-internal conflict** (DO's own investor-relations launch page names **$0.005/GiB-month** as the *Managed Agents* snapshot rate — VENDOR-VERIFIED — vs the vendor docs page's **$0.05**; 10× gap (no correction on the IR surface this run; $0.05 carried from the 9/23 read — subpage still unlocated); misattribution hypothesis (the $0.05 is DO's general-product Volumes rate) INFERRED and now vendor-supported on the $0.005 side; field-table keeps $0.05 with the conflict annotated; stale "RETIRED in favor of the primary source" line corrected; 8th docs-subpage re-fetch stays the resolving ask), **C44 heading moved** (Sep 22 → Sep 24: Gemini 3.8 Live GA, Muse Spark 1.3 Preview — watch color, no fold). Retired duplicates (google/ax candidate = already-filed **C47**, Apache-2.0 re-confirmed; Docker-launch candidate = already-filed **C45**, now 5-surface corroborated). **Vercel Drives still public beta** (P49 morning cadence, 26th consecutive no-change pass — full Drive pricing grid live, digits already folded at C32). Carried: C37 Pro fee still UNVERIFIED (page structurally doesn't publish plan fees), C41 pin static `39b6c3a2`, C43/C36 unchanged, Tensorlake no Sep-24/25 news, C48 no-op; adjacent investor color only (Ando $20M, Island $400M Series F). No in-lane launches, pricing moves, or funding dated 9/25 in-window (#411).
  - sparkvm.dev front door, first slice: the landing page now tells the open-source story first ("Open source, running today" — MIT, runs on your Unraid/Proxmox box today, contributions welcome) and splits the two ways to run it (self-host as the near-term story, hosted as the future story with a pointer to the beta pilot on musebook). Pages-ready deploy contract: static file set, security headers (`_headers`: strict baseline + default-deny CSP on the no-JS/no-form paths), custom 404, and operator deploy steps for the Cloudflare Pages project + `sparkvm.dev` custom domain. The landed waitlist funnel wiring (CTA buckets, tag set, no-JS, no dead forms) is unchanged and now test-guarded (#412).
- Competitor corpus update (pre-dawn watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **C47 Google AX v0.3.0** (orchestrator/harness lane, primary-source VERIFIED on github.com/google/ax — Apache-2.0, runs on Agent Substrate for sandboxed execution, kubectl-shaped CLI with ax suspend/resume/ssh, Task/Workspace/Model manifests, pre-stable; v0.3.0 notes THIRD-PARTY-convergent — strongest validation yet of the C30 harness↔compute split / H4 per-harness-adapter thesis), **C48 Prime Intellect "Prime Sandboxes" launch** (~2026-09-23, THIRD-PARTY — 30M agent environments, usage-based no-commitment, vCPU $0.02/hr + $0.0125/GiB-hr mem + $0.0002/GiB-hr disk ≈ 1/3 of large providers, promo through Dec 22, CPU-only with snapshots/forking/GPU on roadmap), C45 duplicate closed (surveyor's Docker Cloud Sandboxes launch candidate = the already-filed C45 event), Grunz "$100 once" flag downgraded to light-watch (figure absent from grunzai.com — now pay-per-use credits). Carried: C37 Pro fee still UNVERIFIED (Hobby $50 re-confirmed), C26 docs pricing subpage 7th consecutive miss (convergent release-set, no corpus change), Tensorlake no Sep-24/25 news, C41 pin still `39b6c3a2` digits unchanged, C44/C36/C43 unchanged. No launches, pricing moves, or funding dated 9/25 in-window (#409).
- Competitor corpus update (post-midnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **C41 repo HEAD pin REVERTED (`96ff8a8` → back to the pre-overnight `39b6c3a2` commit, VENDOR-VERIFIED via GitHub API — not a second move, no phantom third position)** with all pricing digits unchanged, **C9 THIRD-PARTY pricing color** (hosted-sandbox containers $0.03–$1.92 per 20-min session; ZDR inapplicable even self-hosted), new-to-watch candidate Google AX v0.3.0 (THIRD-PARTY, HN-noted — open-source Apache-2.0 agent orchestrator on Agent Substrate; primary-source pass owed). Carried: C37 Pro fee still UNVERIFIED (Hobby $50 minimum re-confirmed), C26 docs pricing subpage 6th consecutive miss (misattribution stays INFERRED), Tensorlake no Sep-24/25 news, C44 heading still Sep 22, C36/C43 confirmed unchanged. No launches, pricing moves, or funding dated 9/25 in-window ((#385)).
- Competitor corpus update (post-overnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; Daytona pricing figures moved from baseline-carried to VERIFIED on Daytona's own pricing page — full GPU ladder now on record), **C43 clean citation CAPTURED — debt retired** ("Environment compute (CPU, memory, sandbox execution) is **not billed** during the preview period", VENDOR-VERIFIED on ai.google.dev, page "Last updated 2026-09-24 UTC"; fixed 4 CPU cores / 16 GB memory), **C36 FULL vendor verification** (Google Cloud Blog: open-source secure-by-default runtime, 10x density, sub-500ms resume @ 500+ activations/sec; all GKE customers non-production, production GA via allowlist; Nous Research (Hermes) design partner), **C26 docs surface re-located and VENDOR-VERIFIED** (standalone pricing subpage still unlocated — 5th consecutive miss; rates hold $0.044/vCPU-hr, $0.0095/GB-hr, $0.005/GiB-month), **C41 pin 96ff8a8 UNCHANGED** (all pricing digits re-verified), **C37 Hobby $50 re-confirmed** (Pro fee still UNVERIFIED). In-lane dated 9/24 THIRD-PARTY color: ByteAsk $1M pre-seed (C/C++ coding agents), Ando $20M stealth launch (team chat with native agent roles), Darktrace Signal Labs (agent behavioral-security research). OpenAI Agents API still public beta (GA absence VENDOR-VERIFIED); Vercel Drives not re-checked (P49 morning cadence) ((#384)).
- Competitor corpus update (overnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; Daytona pricing not re-fetched — changelog-only scope, carried as baseline), OpenAI Agents API GA absence upgraded to VENDOR-VERIFIED (still public beta, `client.beta.agents` — corrects the prior fetch failures), **C41 pin MOVED for the first time** (`39b6c3a` → `96ff8a8`, VENDOR-VERIFIED on the official repo's commits page; pricing digits unchanged), C43 VENDOR-VERIFIED in preview (compute not billed during preview), C44/C36/Tensorlake re-verified, C37 UNVERIFIED-carried (no public Pro price; FAQ $50/mo Hobby minimum re-verified), **C26 fourth consecutive docs-side miss — and the carried $0.05 figure is retired as current** (current general-snapshot snippets read $0.06/GB-month; the 10x discrepancy framing is withdrawn — evidence-backed Managed Agents rate is $0.005/GiB-month from the vendor's 2026-09-22 investor release), **corpus fold: DO's own billing model** (vendor-published — active CPU billed per-second, $0.126/hr fully allocated reference → ~$0.0310/hr typical 25%-active run, zero while waiting — the corpus's sharpest agent-sandbox duty-cycle pricing comp). In-lane dated 9/24: Docker Cloud Sandboxes reconfirmed (shape prices Micro $0.07 / Small $0.14 / Medium $0.28 / Large $0.56 / XL $1.12, sbx 0.45.1+, 24h max, $250 credit); Baseten×Blaxel is Sep-24 commentary on a Sep-10 deal, not a launch. Vercel Drives not re-checked (P49 morning cadence) ((#382)).

- Competitor corpus update (post-mid-evening watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas; Daytona pricing not re-fetched — changelog-only scope, carried as baseline), C36/C41 (HEAD pin 39b6c3a unmoved, pricing re-verified digit-for-digit)/C44 re-verified unchanged VENDOR-VERIFIED, **C37 VENDOR-VERIFIED: no monthly-fee line-item on pricing surfaces; FAQ discloses a $50/mo Hobby minimum-usage commitment** (dashboard-signed-in check still owed), **C26 third consecutive docs-side miss** (press side re-VENDOR-VERIFIED $0.005/GiB-month; INFERRED misattribution hypothesis strengthened — carried $0.05 may be DO's general-product $0.05/GB-month snapshot rate; both figures stay open), OpenAI Agents API GA absence search-level only this pass (official page fetch failed — honest weakening), **corpus fold: C45 first vendor-sourced price-and-terms package** (`sbx move --to cloud` one-command, per-second, Micro $0.07/hr → XL $1.12/hr, paused=free, 24h sessions, $250 credit, WeAreDevelopers NA venue). C43 snippet-only (official surface identified, re-open owed); Tensorlake search-level no news. Vercel Drives not re-checked (P49 morning cadence) ((#381)).

- Competitor corpus update (pre-midnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas — Daytona V0.216.1 SEP 24 above V0.216.2 SEP 24 baseline-confirmed, Docker Sandboxes release-notes 2026-09-21, Microsandbox v0.7.3, E2B, boat.dev pricing, TermSquad, AgentComputer, DigitalOcean still public preview), C36/C41 (HEAD pin 39b6c3a unmoved)/C43/C44 re-verified unchanged, OpenAI Agents API still public beta, Tensorlake no news, **corpus folds: C45 launch-availability VENDOR-VERIFIED** on docker.com's own Sept-24 posts + BAND Python Kit for Docker Sandboxes (THIRD-PARTY, Sept 24 — first third-party Kit-ecosystem signal), **C26 second consecutive docs-side miss** (press side re-VERIFIED $0.005/GiB-month; "Last verified 22 Sep 2026" pricing subpage still unlocatable; INFERRED misattribution hypothesis carried open). C37 Freestyle Pro fee still UNVERIFIED (dashboard-signed-in check owed) ((#379)).

- Competitor corpus update (late-night watch): dated-2026-09-24 Register coverage corroborating the Docker Cloud Sandboxes GA venue (THIRD-PARTY; Micro $0.07/hr → XL $1.12/hr named shapes, per-second, OCI-standard Kits — matches vendor figures value-for-value), DigitalOcean snapshot-rate partial re-read (press-release side re-VERIFIED $0.005/GiB-month; docs pricing subpage not locatable this run, 10x discrepancy not re-observable, carried open), and boat.dev's product-news surface VERIFIED absent (third attempt; retry retired). Tracked set 7/8 VERIFIED NO-CHANGE (Daytona changelog reorder micro-delta only: V0.216.1 now above V0.216.2, both SEP 24, no new release) ((#375)).
- H12 usage-metering design: billable-unit taxonomy for hosted billing (box wall-clock, resource windows, approval volume, suspend/wake, push delivery), a canonical metering event envelope shared with the H5 sentinel design (per-surface mappers over the four telemetry surfaces, sequencing, trust tiers, counters-over-content privacy), emission modeled on the shipped H14 part a enqueue/retry pattern, and the filed follow-ups (#376–#378). No pricing promises — design thinking only ((#380)).
- Competitor corpus update (night watch): new Tensorlake Firecracker-microVM sandbox entry with own-page pricing (Free / Usage Credits / Pro $250 per cycle / Enterprise; snapshot storage $0.07/GB-month), Simular Sai pricing resolved from own-domain pages (Free / $50 / $500 / Enterprise), Freestyle own-page pricing verified (Hobby $50/mo), and DigitalOcean's live docs-vs-release snapshot-rate discrepancy confirmed on both vendor surfaces ((#373)).

- Competitor watch, 2026-09-24 mid evening: tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas), DigitalOcean Managed Agents pricing re-verified on the vendor's own Sept 22 press release ($0.044/vCPU-hour, $0.0095/GB-hour, $5 credit — matching C26; pricing subpage "Last verified 22 Sep 2026" stamp re-check still carried), boat.dev product-news surface UNVERIFIED (not located), C36/C41/C43/C44 no new moves, OpenAI Agents API Sep-10 public-beta dating re-confirmed VERIFIED (still public beta, no GA), **corpus folds: C45 GA-venue garnish** (onstage launch at WeAreDevelopers North America; Sandbox Kits → standard OCI images + CNCF submission commitment; Hermes first-class Kit demo) + **C26 pricing re-verified** (docs $0.05/GiB-month vs release's $0.005 — live 10x snapshot discrepancy, stamp re-check must resolve), in-lane dated 9/24: Docker GA venue, Island $400M/$6.4B (adjacent), Modal ~$15B talks (adjacent), Darktrace Signal Labs (adjacent) (#370).
- Competitor watch, 2026-09-24 late afternoon: tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas), DigitalOcean Managed Agents pricing still UNVERIFIED (vendor product doc fetched, carries DO's own "Last verified 21 Sep 2026" freshness line but no pricing; pricing subpage fetch failed — stamp re-check owed next pass), C36/C41/C43/C44 all re-verified unchanged, OpenAI Agents API Sep-10 public-beta dating re-confirmed VENDOR-VERIFIED (still public beta, no GA), C45 no new moves, Vercel Drives still public beta (opportunistic re-read), **corpus fold: C41 deep-hibernation garnish** (15 GiB free disk allowance does not apply in deep hibernation — VERIFIED on the vendor page), no in-lane launches/pricing/funding dated 9/24 (#365).
- Competitor watch, 2026-09-24 mid afternoon: tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas), DigitalOcean pricing docs UNVERIFIED this pass (stamp re-check owed next), C36/C41/C43/C44 all re-verified unchanged, C45 no new moves since the fold, **asks resolved** — Boat EU-only DE/FI/FR geography re-VERIFIED verbatim on boat.dev's own FAQ (three-pass retry closed), OpenAI Agents API Sep-10 public-beta dating re-confirmed VENDOR-VERIFIED with a fresh read of OpenAI's own changelog (still public beta, no GA), **corpus folds: C41 Snapshot pricing fully specified** (*Snapshot Storage Usage = Memory Specification × 2 + Disk Specification*, charged at Disk Unit Price × duration) + C45 WeAreDevelopers-North-America venue garnish, `_MID_AFTERNOON` admitted to the watch-doc naming convention, no in-lane launches/pricing/funding dated 9/24 (#364).
- Competitor watch, 2026-09-24 early afternoon: tracked set moves — 7/8 quiet, **Microsandbox v0.7.2/v0.7.3 new** (full-quiet streak ends at three), C36/C41/C43/C44 all re-verified unchanged, OpenAI Agents API still public beta (no GA), **new in-lane corpus entry C45 — Docker Cloud Sandboxes** (VENDOR-VERIFIED on Docker's own blog: same microVM on Docker-managed compute, `sbx move --to cloud`, PAYG per-second $0.07–$1.12/h, paused free, $250 free credit), agentic-cloud framing and Tencent DataBuddy stay queued/adjacent, C41 Snapshot-pricing fold queued for the next pass, no in-lane funding dated 9/24 (#363).
- Competitor watch, 2026-09-24 noon: tracked set 8/8 quiet (full-quiet streak advances to three), C36/C41/C43/C44 all re-verified unchanged, **OpenAI Agents API Sep-10 public-beta dating upgraded THIRD-PARTY → VENDOR-VERIFIED** (sourcing only — OpenAI's own changelog; still public beta, no GA move), agentic-cloud framing and Tencent DataBuddy stay queued/adjacent, C44 paren-balance nit adopted, no new corpus entries, no in-lane launches/pricing/funding dated 9/24 (#359).
- Competitor watch, 2026-09-24 late evening: tracked set 8/8 quiet, Vercel Drives still public beta (25th pass, GA watch now once-daily per the P49 cadence decision), **new in-lane corpus entry C44 — Google Gemini Enterprise Agent Platform sandboxes (Computer Use + Shell) GA** (VENDOR-VERIFIED on Google's own release notes), Docker CVE pair confirmed already-closed, watch-review nits adopted (#352).

- `docs/SENTINEL_TELEMETRY_SURFACES.md`: arch deep-read of the four
  audit/telemetry surfaces the hosted sentinel (H5) would consume —
  schema catalog, six structural findings (no shared event envelope, no
  sequencing or authentication, second-resolution timestamps that collide
  under burst, unstated trust tiers for agent-forgeable muse-job events,
  confirmd's silently-swallowed audit-write failure (fixed this turn so
  it signals to stderr), and confirmd's audit.log having no rotation
  bound), plus the ordered H5 prerequisites. Findings filed as GitHub
  issues. (#353–#357, #360, PR #361)

- Evening competitor watch (full quiet pass): tracked-set vendors 8/8
  VERIFIED no-change with zero fetch failures (full-quiet streak re-opens
  at one after the afternoon pass's Daytona move), Vercel Drives still
  public beta (24th consecutive pass; VERIFIED on the vendor changelog
  page this run; pricing last_updated 2026-09-10), C36, C41, and C43
  re-verified unchanged. No corpus fold this pass — three fold candidates
  queued for primary-source verification (Google Shell/Computer Use
  sandboxes GA Sept 9; Docker Sandboxes CVEs CVE-2026-77179/CVE-2026-79994
  Sept 15; the Alibaba/Huawei "agentic cloud" framing trend), plus a
  namesake-collision warning that Guava's "Daytona" voice model is
  unrelated to Daytona sandboxes. Afternoon vetting holds (OpenAI Agents
  API stays third-party; Tencent DataBuddy stays adjacent-watch;
  deprecated-row sunset convention stays proposed-not-codified). News
  scan: adjacent color only (Island $400M Series F on rogue-agent
  framing, Alibaba AgentCore, Darktrace Signal Labs) — no in-lane
  launches, pricing moves, or funding dated 2026-09-24. Full pass in
  `docs/COMPETITOR_WATCH_2026-09-24_EVENING.md` (#351).

### Fixed

- Waitlist re-submit after a claim no longer spawns a second pending row
  for the same address: `signed_up` is terminal in the waitlist state
  machine, and the old dedup check missed it, so a claimed owner
  re-submitting the form (or path-A email) got a fresh confirm email and
  could be invited and claimed a second time — double-counting the
  funnel and stealing a later wave's slot. Re-submits on claimed
  addresses now get an honest "Already claimed" page / `already_claimed`
  outcome: no new row, no new email, nothing refreshed ((#TBD)).

- Approval-signal contract doc fixes: the pending id is always a single
  approval id (the list form was unreachable); the `expired` approval
  notice is documented as best-effort — confirmd's render loop usually
  reaps expired items first, so clients see the pending id change with no
  `expired` leg and should keep waiting on the new id; and the
  answered-history item schema shared by confirmd and the proxy is now a
  named, versioned (v1) cross-component contract; its (pre-existing)
  drift behavior is documented as fail-closed (#308, #309, #310, #383).
- A manual `auto-deploy.sh rollback` now marks the rolled-back commit
  blocked (like automatic rollbacks always have), so the next timer tick
  no longer redeploys the same bad commit in a fail/roll-back loop — the
  block auto-clears once a newer commit supersedes it, `rollback
  --no-block` skips it for investigate-not-condemn rollbacks, and `status`
  prints the exact `rm` command to clear it by hand (#325, #374).
- The harness auth probe's confirmd check now verifies the answering process
  behaves like confirmd — it requires confirmd's own 403 denial shape
  (`forbidden: <reason>` body plus `confirmd/1` server header, and never
  follows a 3xx off the port) instead of counting any HTTP response as
  liveness, so a port grabber, stale service, or misbound server answering
  on the confirmd port can no longer certify the approvals path as up before
  box-live. This catches accidental misbinding at the gate, not an adversary
  who controls the port (#160, #367).
- `scripts/cut-release.sh` no longer aborts with "not a git repo" when run
  from a git linked worktree (where `.git` is a `gitdir:` pointer file, not
  a directory) — the repo gate now checks `git rev-parse --git-dir`
  instead, so operator dry-runs from worktrees pass (#349, #362).
- confirmd's approval pages and the `/sw.js` service worker now send
  `X-Content-Type-Options: nosniff` and `Referrer-Policy: same-origin`,
  so a content-type confusion can't turn an approval page into an executed
  script and approval URLs never leak to third parties via Referer (#77,
  #362).

### Security

- The privileged deploy writer now stages into randomly-named directories
  (128-bit entropy) instead of predictable per-process names, so a
  lower-privileged local user can no longer pre-create colliding staging
  directories to abort every deploy; sustained collisions still fail
  closed as an attack indicator (#333, #371).
- A failed deploy staging step now unlinks its staged temp file before
  removing the staging directory, so interrupted installs leave no
  orphaned staging directories behind (#335, #371).
- The CA-bundle builder's system-bundle read is now capped at 1 MiB like
  the swapd-CA read, so a crafted `--sys` path can't turn the privileged
  helper into an unbounded root read (#334, #371).

## [0.3.0] - 2026-09-24

### Added

- `docs/ICP.md`: ideal customer profiles for the three segments — self-hosters
  (Unraid/Proxmox/Hetzner homelab), hosted signups (other Muse owners, with the
  buyer≠user packaging split), and sandbox harness builders (the separate
  sandbox product, cooperative-jail tier) — plus the trust-boundary split
  between them and who is NOT an ICP. Design thinking, not a commitment; the
  validation checklist lives in #343. (#347)

- Competitor watch (2026-09-24 afternoon): tracked set 7/8 VERIFIED NO-CHANGE —
  the eleven-pass full-quiet streak ends on Daytona's SEP 24 changelog entries
  (V0.216.1/V0.216.2, CLI/API polish, no sandbox moves); Vercel Drives still
  public beta; new in-lane corpus entry C43 — Google Gemini Agent Environment
  (managed Linux sandboxes for agents, VERIFIED on Google's own docs). (#348)

- Late-midday competitor watch (eleventh full quiet pass): tracked-set vendors
  8/8 VERIFIED no-change, Vercel Drives still public beta (22nd consecutive
  pass; a third-party snippet says "private beta" — recorded as availability
  color only, verdict stays public beta per the vendor changelog), C36 and
  C41 re-verified unchanged. Vetting upgrades, not launches: new corpus
  entry C42 Namespace Devboxes (VERIFIED in-lane on the vendor's own docs —
  Linux/macOS devboxes for coding agents with native Claude, Cursor, and
  Devin integrations; reverses the midnight pass's adjacent verdict),
  Upstash Box verified on its own docs (row update; pricing still
  third-party), and the Ascii Box candidate retired — the vendor's own API
  docs brand the product Boat (hardest rename evidence yet), revealing
  built-in coding-agent harnesses on the `prompt` endpoint. No launches,
  pricing moves, or funding dated 2026-09-24. (#346)

- Midday competitor watch (tenth full quiet pass): tracked-set vendors
  8/8 VERIFIED no-change, Vercel Drives still public beta (21st
  consecutive pass), C36 and C41 re-verified unchanged; closed three
  owed follow-ups — the YC slug rename for Boat is now backed by a
  VERIFIED 301 (`/companies/ascii` → `/companies/boat`), folded into
  the C40 provenance, and Boat's EU-only geography re-verified on the
  vendor FAQ (Germany, Finland, France). A sunset convention for
  deprecated corpus rows is proposed in the watch doc but not codified.
  (#344)
- H11 multi-tenancy audit: every localhost-only, no-auth, and single-owner
  assumption in the repo inventoried and ranked by blast radius; adopts the
  isolation research's findings and answers the four design questions —
  per-tenant box recommended for mutually-untrusted tenants (the jail is
  the honest, weaker boundary for cooperative tenants), the swap proxy
  must move from host-wide to tenant-bound request auth before any
  shared-host tenancy, tailnet enrollment fails closed with outage-time
  revocation designed as stale authorization, and the tenant holds root
  inside their guest while the operator owns only the layer below.
  Files #339 (tenant-bound swap auth) and #340 (open verifications);
  releases the H5, H12, and H13 design gates and confirms H10's
  provisional tenant-identity assumption. (#341)
- Re-open a denied approval from its answered-history card (H20): a
  mis-tapped Deny no longer needs the operator CLI to recover — the card
  offers "Re-open this request", which re-files it as a new pending
  approval (new id, the original request, the requester's original
  deadline kept verbatim, expired requests refused honestly) and re-pushes
  the owner. Single-tenant for now, designed for the multi-tenant future.
  (#331)
- Competitor watch (2026-09-24 morning): tracked set 8/8 quiet (ninth
  consecutive pass), Vercel Drives still public beta; corpus dedups a
  phantom provider — ASCII renamed to Boat ~2026-09-17, so C40 folds into
  the tracked-set Boat row (same product, canonical domain boat.dev); new
  in-lane entry C41 — Alibaba Cloud FC Agent Sandbox billing verified
  from aliyun-fc/fc-docs (Eco/Std/Pro pay-as-you-go from ~$0.037/h for a
  2vCPU/4GiB box, task-scoped and E2B-SDK-only, not a persistent VM);
  wowza.com owed re-verification closed; no new in-lane launches 9/23–24.
  (#337)
- Competitor watch (2026-09-24 predawn): tracked set 8/8 quiet, Vercel
  Drives still public beta; corpus grows a new in-lane entry — C40 ASCII
  "boat" (persistent Ubuntu VMs for agents with verified own-page
  pricing: $20/mo plan = $20 sandbox time, $0.036/h for 4vCPU/8GB/50GB,
  EU-only); C39 Simular Sai pricing refined (vendor-published $50/$500
  on simular.ai, sai.work carries no pricing). Full pass in
  `docs/COMPETITOR_WATCH_2026-09-24_PREDAWN.md` (#330).

- Competitor watch (2026-09-24 midnight): tracked set 8/8 quiet, Vercel Drives
  still public beta; corpus grows a new in-lane entry — C39 Simular "Sai"
  computer-use agent GA (fleet of cloud VMs up to 100 machines); Freestyle
  boot claim qualified (marketing "65 ms" vs docs p99 under 400ms); E2B
  $21M Series A dated 2025-07-28; Modal ~$15B raise talks (third-party).
  Full pass in `docs/COMPETITOR_WATCH_2026-09-24_MIDNIGHT.md` (#329).

- Competitor watch (2026-09-23 late overnight) (#327): tracked set quiet —
  all 8 providers re-read vendor-verified with no change (sixth full quiet
  pass since the mid-afternoon fold); Vercel Drives still public beta
  (seventeenth consecutive no-change pass; pricing page last_updated
  2026-09-10; the 2026-09-23 changelog entry is the beta announcement
  re-dated, not a GA move); Boxd rate card re-verified on boxd.sh (the
  overnight pass's C29 fold stands — no new fold); new in-window
  third-party item: Simular "Sai" computer-use agent GA on cloud VMs
  (vendor verification owed); no other in-window launches, GA moves, funding, or
  pricing moves dated today.
- Competitor watch (2026-09-23 overnight) (#322): tracked set quiet —
  all 8 providers re-read vendor-verified with no change (fifth full
  quiet pass since the mid-afternoon fold); Boxd rate card now
  vendor-verified on boxd.sh (C29 debt resolved); new in-lane corpus
  entries C37 (Freestyle, "VMs for AI Agents") and C38 (Tensorlake,
  "Sandboxes for AI Agents"); Automaid lane-drift confirmed on its own
  page (workflow-automation SaaS) and dropped from the watch list; no
  in-lane launches, GA moves, funding, or pricing moves dated today.
- Competitor watch (2026-09-23 late night) (#320): tracked set quiet —
  all 8 providers re-read vendor-verified with no change (DO Managed
  Agents C26 figures read live a fourth consecutive pass, stamp "Last
  verified 22 Sep 2026", snapshots/checkpoints $0.05/GiB-month);
  Vercel Drives still public beta (fifteenth consecutive no-change
  pass; pricing page last_updated 2026-09-10); Boxd quickstart now
  VERIFIED (rate card UNVERIFIED this pass — surveyor fetch gate —
  honestly labeled, not carried); C36 no new vendor datapoints
  (no GA move, allowlist-only production stands); Automaid own-page
  fetch failed again (UNVERIFIED) but third-party evidence hardened
  against it — every result names cleaning-business booking SaaS,
  moving it to lane-drift pending one successful own-page fetch;
  Tencent Cloud DataBuddy stays lane-drift; THIRD-PARTY Upstash
  15-provider comparison names newcomers (Upstash Box, Freestyle,
  Ascii Box, Namespace, Beam, Tensorlake) as future-vetting
  candidates; no corpus fold; no in-lane launches today.
- Competitor watch (2026-09-23 early night) (#318): tracked set
  quiet — all 8 providers re-read vendor-verified with no change
  (DO Managed Agents C26 figures read live a third consecutive pass,
  stamp "Last verified 22 Sep 2026", snapshots/checkpoints
  $0.05/GiB-month); Vercel Drives still public beta (14th consecutive
  no-change pass); Boxd rate card unchanged (quickstart UNVERIFIED
  this pass — honestly labeled, not carried); C36 no new vendor
  datapoints; Automaid own-page verification still owed (fetch failed
  this pass — UNVERIFIED); Tencent Cloud DataBuddy stays lane-drift
  (agent-workbench governance, not VM-for-agents); no corpus fold;
  no in-lane launches today.
- Competitor watch (2026-09-23 post-mid-evening) (#317): tracked set
  quiet — all 8 providers re-read vendor-verified with no change
  (mid-evening's C26 resolution stands: DO pricing docs sub-page
  re-verified live, "Last verified 22 Sep 2026", snapshots/checkpoints
  $0.05/GiB-month); Vercel Drives still public beta (thirteenth
  consecutive no-change pass; pricing page last_updated 2026-09-10, no
  changelog entries dated 2026-09-23); Boxd rate card unchanged; C36 no
  new datapoints since the 16:00 CDT vendor-confirm fold; Automaid
  own-page verification still owed (site fetchable this run, no launch
  announcement — third-party claim stays UNVERIFIED); no in-lane
  launches.
- Competitor watch (2026-09-23 mid-evening) (#316): **C26 discrepancy
  resolved on the primary source** — DigitalOcean's pricing docs sub-page
  fetched this pass (page stamped "Last verified 22 Sep 2026") and bills
  snapshots/checkpoints at $0.05/GiB-month, retiring the corpus's
  $0.005/GiB-month syndicated-release figure; re-verified CPU-billing
  footnote ("active CPU billing is coming soon, until then 25% of the vCPUs
  allocated to your sandbox; paused sessions incur no compute charges"),
  qualifying the per-entry paragraph's "zero while waiting" read;
  mid-afternoon fold's storage/BYOT/egress/prepaid figures re-verified
  live. Otherwise quiet: 7 of 8 tracked providers re-read vendor-verified
  with no change; Vercel Drives still public beta (twelfth consecutive
  no-change pass; no changelog entries dated 2026-09-23); Boxd rate
  card unchanged (one tool-side fetch failure on the docs pricing URL,
  reported UNVERIFIED); no new C36 datapoints since the afternoon
  vendor-confirm fold; no in-lane launches.
- Competitor watch (2026-09-23 early evening) (#314): tracked set quiet — 7 of
  8 providers re-read vendor-verified with no change (7/7 attempted
  vendor fetches succeeded; DigitalOcean's pricing sub-page URL was
  not extractable this pass — reported UNVERIFIED, not no-change);
  the $0.044/$0.0095 figures stand at the third-party layer, and the
  flagged $0.05-vs-$0.005 snapshot-rate discrepancy is now the
  standing C26 watch item; Vercel Drives still public beta with no GA
  move (eleventh consecutive no-change pass; the beta entry's date
  field flipped 09-23→09-22 — re-publish, not a GA move); same-lane
  third-party pricing color on Google's Filestore agent volumes for AI
  (pay-per-use capacity + lifecycle tiering, folded under C36 at the
  THIRD-PARTY layer); no in-lane launches.
- Competitor watch (2026-09-23 late afternoon): C36-focused verification
  pass (no full tracked-set re-read — 8/8 last vendor-verified ~15:12 CDT,
  no change). **C36 VENDOR-CONFIRMED** — Google's own Cloud-blog
  announcement read live corroborates all nine filed Agent Substrate-on-GKE
  claims (five verbatim, the rest confirmed as filed or
  stronger) (<500 ms resume, 500+/sec suspend/resume activations,
  1,000+ dormant agents/host, Cloud Hypervisor-or-gVisor choice, integrated
  gateway, non-production for all GKE customers with production GA via
  allowlist, Nous Research/Hermes early design partner with named quote);
  new vendor facts folded into the corpus (10× density headline, open-core
  portability, harness-agnostic design, control/data-plane split, Filestore
  agent volumes, native Axion).
- Competitor watch (2026-09-23 mid-afternoon): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (tenth
  consecutive no-change pass; changelog sitemap beta-entry date flip-flop
  continues — the date field is unproven as evidence either way);
  **C26 CLOSED** — DigitalOcean Managed Agents pricing now vendor-verified
  on the docs pricing page ($0.044/vCPU-hour active CPU, $0.0095/GB-hour
  memory, sandbox shape table, pause semantics) with an explicit caveat:
  the docs price snapshots/checkpoints at $0.05/GiB-month vs the launch
  release's $0.005 — 10× apart, one source is wrong; C30 vendor-confirmed
  (OpenAI's own blog on the Agents API public beta; nine named sandbox
  partners including Daytona, DigitalOcean, E2B, Modal, Vercel);
  new-to-watch C36 — Google Agent Substrate on GKE (~Sep 17,
  third-party-only); no new in-lane launches in the 48h window;
  Automaid, Andon Pion, Huawei baselines hold. (#311)
- §3a smoke-check provision assets (G6): the provision-time injector now
  installs the public `smoke-test` dummy credential (spec's pass phrase,
  never a secret), appends the operator's `smoke.<domain>` echo host to
  the main proxy's `hosts.allow` (newline-safe, proxy-matching semantics)
  AND to the proxy's smoke-only scoping list (`SWAP_SMOKE_HOSTS_FILE`,
  default `/home/swapd/smoke-hosts`): the echo host swaps ONLY the
  `smoke-test` credential (refusal `smoke-host-restricted` is audited),
  closing the chosen-plaintext read oracle. Also installs a
  visudo-validated scoped sudoers fragment whose granted argv is pinned
  to `cred-store-set smoke-test` for the tenant agent user, and binds
  `smoke-test` to the echo host in the main registry (the proxy's grant
  scoping refuses unbound credentials, so the §3a swap needs the
  binding). (#313)
- Competitor watch (2026-09-23 early afternoon): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (ninth
  consecutive no-change pass; the changelog sitemap's beta-entry
  re-date 09-22→09-23 is stable since the late-midday pass — the date
  field is unproven as evidence either way); no
  new in-lane launches since the DigitalOcean Managed Agents public
  preview (already filed); C26 refined — DigitalOcean's own
  launch-release text read in full on syndicated copies (completeness
  at the same THIRD-PARTY layer; the docs Details/pricing sub-page is
  still unreached); OpenAI "Managed Agents" still
  rumor; Automaid own page still missing. (#298)
- Competitor watch (2026-09-23 late midday): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (eighth
  consecutive no-change pass; changelog sitemap re-dated the beta entry
  09-22→09-23 — a re-publish, not a GA move); no new in-lane launches
  since the DigitalOcean Managed Agents public preview (already filed);
  C35 closed — the Docker Sandboxes 0.42.0 CVE pair vendor-verified on
  Docker's own security announcements, matching the corpus's standing
  characterization with no drift (no corpus fold); C26 refined (vendor
  docs now load but dollar pricing still third-party-only — Details
  sub-page is the next ask); Automaid adjacent "AI hub for agents that
  keep working" color, own page still missing. (#296)
- Client-visible approval signal (#133): when the swap proxy refuses a
  request for lack of a grant, the proxied response now carries the
  approval id and terminal decisions in response headers —
  `X-Spark-Approval-Pending: <aid>` while a grant request is pending
  (filed or coalesced; a replaced expired item is reported as
  `expired:<old-aid>` alongside the new pending id), and
  `X-Spark-Approval-Decision: approved|denied:<aid>` once decided —
  so the requesting agent can park and re-issue instead of failing on
  a remote auth error. Denial is terminal: within the 1-hour decision
  window a denied tuple suppresses fresh filings (no owner re-push);
  denial suppression is path-scoped. Header values carry only the
  approval id and the state word — never credential names, hosts, or
  secret material. Spec: `docs/APPROVAL_CLIENT_SIGNAL.md`. (#133)
- Competitor watch (2026-09-23 midday): tracked set fully quiet — all
  8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (seventh
  consecutive no-change pass, changelog confirms no entries dated
  2026-09-23); no new in-lane launches since the DigitalOcean Managed
  Agents public preview (already filed); C26 vendor verification
  failed again (browser-service error) and C35 stays third-party-only
  despite stronger corroboration (0.43.0 latest per mirror, CISA
  assesses exploitation as "none", neither CVE in KEV as of Sep 16).
  (#295)
- Competitor watch (2026-09-23 late morning): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (sixth consecutive no-change pass,
  changelog confirms no entries dated 2026-09-23); DigitalOcean Managed
  Agents public preview now carries published pricing ($0.044/vCPU-hour
  active, $0.0095/GB-hour, $0.005/GiB-month snapshots — resolves C26's
  pricing ask at third-party level, vendor verification owed) — the
  first in-lane launch verdict of the recent streak (public preview, not
  GA); Docker Sandboxes 0.42.0 CVE pair (CVE-2026-77179, CVE-2026-79994)
  filed C35 (third-party only, vendor verification owed). (#292)
- Competitor watch (2026-09-23 night): tracked set fully quiet — all
  8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (fifth
  consecutive no-change pass, changelog confirms no entries dated
  2026-09-23); DigitalOcean Managed Agents docs still carry no dollar
  pricing (C26 open); adjacent re-checks — Automaid still THIRD-PARTY
  only, Andon Pion no new facts, Huawei Open Agentic Cloud still
  THIRD-PARTY; fourth consecutive pass with an explicit in-lane
  no-launch verdict (afternoon, evening, late evening, night). (#291)
- Competitor watch (2026-09-23 late evening): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (fourth consecutive no-change pass,
  changelog confirms no entries dated 2026-09-23); DigitalOcean Managed
  Agents docs follow-up (agent-harness-runtime page — preview for all
  users, pricing terms still unverified on vendor docs, C26 color);
  same-lane color — AWS Lambda MicroVMs self-hosted agent-sandbox
  reference architecture and the Herdr × Vercel Sandbox
  one-agent-one-machine plugin; no in-lane launches. (#289)
- Competitor watch (2026-09-23 evening): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (third consecutive no-change pass,
  changelog confirms no entries dated 2026-09-23); DigitalOcean Managed
  Agents preview detail (Firecracker per-session pause/resume harness,
  active-CPU billing — anti-always-on positioning, filed as C26 lane
  color, not a corpus entry); still no always-on
  persistent-agent-machine announcements from any competitor. (#288)
- Competitor watch (2026-09-23 afternoon): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (second consecutive no-change pass);
  one in-window third-party corroboration filed as investor color only
  (Firecrawl $75M Series B — no new facts beyond the §2c filing); borderline pre-window
  color on Boxd's $2M pre-seed and Alibaba FC Agent Sandbox pricing;
  still no always-on persistent-agent-machine announcements from any
  competitor. (#286)
- Competitor watch (2026-09-23 morning): 2 of 8 tracked providers moved —
  Daytona v0.216.0 hardens the SDK build context (Dockerfile COPY confined
  to the build context, filed C33) and Docker Sandboxes' 2026-09-21 release
  ships v3 kits (OCI-based packages bundling an agent workload with
  reusable mixins for tools, config, credentials, network access, and
  agent instructions — filed C34, folded into the competitor corpus);
  Vercel Drives still public beta with no GA move; market-news window
  quiet with no always-on persistent-agent-machine announcements.
- Competitor watch (2026-09-23): tracked set quiet (8/8 vendor re-reads,
  no in-window deltas); the standing Vercel 64 GB default-storage ask is
  CONFIRMED on the vendor's own pricing docs — sandboxes get 64 GB of
  ephemeral NVMe by default (32 GB only on deprecated runtimes), closing
  C32; Vercel Drives public beta completes with real pricing (storage,
  reads, writes, caps, concurrency); adjacent investor color on Firecrawl's
  $75M Series B. (#279)
- The excluded-host link re-sweep now covers all eight bot-blocked hosts:
  a live-browser sweep hand-verified the five later-excluded hosts (all 11
  pages load; 10/11 citations match), and the ritual's enumeration now
  filters URL false positives before counting. One citation annotated
  along the way — Daytona's retired security-exhibit page now redirects to
  their Trust Center, so the isolation quote's citation is annotated and
  re-sourcing issue #277 is open. (#278)
- Overnight competitor watch (2026-09-22): tracked set quiet (8/8 vendor
  re-reads, no in-window deltas); Boxd's SDK install URL is now
  vendor-attested — boxd.sh serves the genuine installer (canonical path
  boxd.sh/downloads/cli/install.sh), closing the last unverified item on
  the Boxd entry; Vercel Sandbox announced persistent "Drives" in public
  beta (up to 16 TiB, usage-based) — a separate feature from the
  still-unverified default-storage claim; third-party follow-up analysis
  of DigitalOcean's Managed Agents launch adds no new mechanism detail.
  (#275)
- Design for the hosted tenant status endpoint: the `GET /tenant/status`
  contract the first-ten-minutes spec, signup flow, and signup UI all
  assume — the 12 machine codes with transition rules, the `approvals_url`
  carrier, two-sided auth (magic-link cookie + linked-key), and the
  provider-layer vs tenant-layer separation (#273).
- Evening competitor watch (2026-09-22): DigitalOcean's Managed Agents
  product page is readable again — Tool Playground (pre-production policy
  testing), scheduled/webhook triggers, and org-policy concepts
  (actors, toolbelts) — plus a flag that DO's marketing claims (~200 ms
  resume) outrun its own measured benchmark (305 ms); Fly.io Sprites'
  lifecycle docs publish warm wake 100–500 ms and cold wake 1–2 s with
  dropped TCP state, bearing on the resume-latency target. New to the
  tracked set: Boxd ($2M pre-seed, KVM persistent-machine competitor,
  vendor-claimed fork-including-memory in <100 ms), the OpenAI Agents API sandbox
  partner list (formalizes the harness-vs-compute split — INFERRED from
  the partner list, not an OpenAI claim), and a new snapshot/restore
  datapoint on the already-corpus-ed Upstash "Box" entry; independent hands-on coverage of the
  DO launch is still absent. (#270)
- Golden-image round-trip gate operator procedure (spec §6.7): the
  file → answer → grant-mint → verify sequence with the filing-count
  determinism check and mandatory fixture teardown pre-publish. The
  round trip exercises the proxy's real filing path (a gate-only
  credential bound with narrow static limits files one approval through
  the main proxy; the operator answers through confirmd; the grant mints
  through the grant writer; the re-run proves the swap took effect),
  wired to the existing gate-fixture tooling. (#271)
- Secrets-posture corpus gains DigitalOcean Managed Agents as the fifth
  convergent data point (their launch release claims a separate secrets
  service with "credentials brokered at execution time" that "never reach
  the model or the sandbox" — press-release source, no mechanism detail
  scored), and the org-policy vendor set gains DO's Action Gateway
  (governed tool access via one managed MCP endpoint) as a candidate. (#263)
- Morning competitor watch (2026-09-22): DigitalOcean launched Managed
  Agents in public preview — microVM-per-session Harness Runtime, Action
  Gateway (16,000+ tools via one MCP endpoint, credentials brokered at
  execution time), and active-CPU pricing ($0.044/vCPU-hour, 305 ms
  pause→resume claim) — filed as a new tracked competitor, with follow-up
  notes for the hosted product's pricing thinking, resume-latency target,
  secrets posture, and org-policy layer; Daytona shipped a routine v0.215.0
  SDK/CLI patch; the rest of the tracked set was quiet. (#256)
- Enforcement-downgrade contract for the agent jail (fail-closed, stated
  explicitly): a firewall-apply failure aborts the build before the jail
  starts, a boot-time apply failure blocks the container from starting, and
  a dead proxy means no egress rather than open egress — like Brig's
  policy-bound refusal, the workload never runs where its restriction
  cannot be enforced. The one residual the contract originally stated —
  no runtime re-apply — is closed by the firewall watchdog #260, which
  narrows the residual boundary to the 5-minute verify window. The contract
  mechanics are test-pinned. (#255)
- Deny-style billing guard committed for sandbox credential forwarding:
  when the hosted path forwards operator credentials into a sandbox,
  known metered-billing keys are deny-by-default without an explicit
  per-credential override (Brig's `deny` shape, including its documented
  environment-channel-only limit). Committed design, not yet shipped —
  no forwarding surface exists yet. (#255)
- Demo gallery, sixth asset: the push queue surviving an outage — the new
  "See it in action" row shows the standalone push worker's first delivery
  attempt hitting a dead endpoint (500) and rescheduling instead of losing
  the approval, the durable journal holding the summons, and the retry
  delivering once the endpoint answers (201). The generator replays the
  real enqueue/worker code paths against a local mock push service
  (throwaway keys, nothing leaves the machine). (#252)
- Push notifications now survive a dead push service: swapd enqueues every
  filed approval and a standalone push worker (`push-worker.service`)
  delivers with exponential-backoff retry, dead-lettering only after 8
  failed attempts with a loud log line. On the healthy path delivery
  waits for the next worker pass (up to 30s, tunable via
  `--worker-interval`). Runs wherever the deployment lives (self-hosted
  or hosted), like confirmd. (PR #204)
- Waitlist claim route: the invite email's claim link is now served —
  opening it shows the claim screen (masked owner email, the same
  what-happens-next steps as the invite email), and clicking through
  records the claim idempotently and logs it in the funnel trail. Dead
  or expired links land on an honest "no longer live" page, never an
  error dump. (#250)
- Provider failover-router design: the new design doc describes how the
  hosted control plane would keep a tenant session alive across a
  provider outage — which failures trigger a move to another provider
  (and which recover in place), the order of operations for the move,
  how session data is restored when VM snapshots can't cross providers,
  and how provider capabilities pick the fallback target. (#251)
- Provision-time injector (`harness/inject-provision-state.sh`): runs at
  first boot of the hosted agent VM and owns the provision-time half of
  the gate-fixture contract — preflights the golden-image manifest
  against the operator-pinned image SHA and fails closed on drift
  before box-live; tears down the gate fixture's `llm-api`→echo-host
  binding, failing closed on echo-host residue in the allowlists (which
  only the image-build gate can remove); asserts a real inference
  credential through the registry plus a blind compare against the
  public fixture dummy (the stored value is never read, never written,
  never printed); requires a fresh per-tenant swapd CA; installs tenant
  identity and records tenant attribution when their inputs are
  provided (both reported as deferred when absent, never fabricated);
  then proves the injected key with the provision-mode probe — a probe
  failure maps to provisioning-failed and box-live must not flip.
  Ships one JSON inject report on stdout and 55 hermetic tests. (#238)
- Night competitor watch (2026-09-22): quiet survey window — no launches,
  acquisitions, pricing changes, releases, or partner moves across the
  tracked set; boat.dev rate card and comparison table re-verified
  unchanged; two pre-window competitors newly surfaced and filed as
  watchlist items (Brig, Epho); adjacent color on Meta Muse's Sentinel
  per-user VM architecture (third-party deep dive of the pre-window
  launch). (#239)
- Waitlist operator tooling: `waitlist_invites.py --reconcile` repairs
  missing `invite_sent` funnel events after the commit → emit crash
  window — it re-derives the missing events for still-live invites from
  the waitlist store in the append-only posture (each re-derived event
  carries `reconciled: true` in its attrs; `--dry-run` previews), is
  idempotent, and skips rows whose invite is no longer live. (#237)
- Secrets-posture corpus: h-sandbox's Credential Vault (open-source,
  self-hosted sandbox control plane) becomes the fourth convergent data
  point for the placeholder-swap pattern — its docs describe fake-env
  placeholders in the sandbox with the real auth material injected at the
  egress sidecar only for host/scheme/method/path-bound requests (verified
  against their own docs 2026-09-21, verbatim quote in the research doc);
  the watch pass also records its OpenSandbox-adapter contract discipline as
  input to the hosted provider-adapter design. (#230)
- Secrets-posture corpus: opencomputer.dev's secret-store egress proxy
  (opaque placeholder in the sandbox, real key swapped in-flight on the
  outbound HTTPS call to the model provider, under an egress allowlist —
  verified against their own docs 2026-09-21, verbatim quote in the research
  doc) joins Daytona and Microsandbox as a third convergent data point for
  the placeholder-swap pattern. (#219)
- Competitor watch 2026-09-21 evening (docs/COMPETITOR_WATCH_2026-09-21_EVENING.md):
  quiet window — zero in-window deltas across the tracked set since the
  afternoon pass; one pre-window miss filed as watch item C18
  (h-sandbox/"Harakiri Sandbox" — open-source self-hosted sandbox
  control plane launched 2026-09-09, with a host-bound-egress credential
  vault and an OpenSandbox execution adapter, the closest open-source
  shape to spark-vm's secrets posture); AgentComputer's "unverifiable"
  egress posture refined to a stronger negative (real product with real
  pricing, still no stated egress policy). (#216)
- `jail/build.sh` is safer to inspect and harder to drift: `--help` / `-h`
  renders the script's header doc and exits before any side effect in ANY
  flag position (`build.sh --rebuild-rootfs --help` can't accidentally
  start the privileged build — the usage line documents that order), and
  the tailnet→jail SSH port is now single-sourced from `$JAIL_SSH_PORT`
  into the nftables DNAT rule via a quoted heredoc + placeholder
  substitution — the applied conf always carries the variable's value,
  with tests that render through the real sed pipeline.
- The single-command test story now actually covers every component:
  `pytest.ini` discovers the `cua/`, `jail/`, AND `credlib/` suites too —
  including a new `cua/test_shell_scripts.py` gate (`bash -n` +
  shellcheck warnings for the four host-side `cua/bin` scripts that
  can't run in CI, with an explicit skip when shellcheck is absent,
  now also wired into `ci.yml` so the gate actually executes) — and
  `confirm/test_push.py` skips explicitly (instead of erroring
  collection) on boxes without the `cryptography` package, so
  `python3 -m pytest` degrades gracefully.
- Approvals-plane gap analysis: a new doc walks the full path from a gated
  action to a human answer and back (refusal → filing → pending → human
  answer UX → push summons → terminal decision delivery → audit trail),
  against the code as it stands today. Headline finding: the plane is a dead
  end for the agent — refusals carry no approval id, answers deliver no
  decision, and expiry is a silent third outcome — and files two new issues
  (expiry's silent terminal outcome; answered-feed per-poll parse cost).
  (#215)
- Release-protection drift guard: the declared `main` branch ruleset's
  required CI checks are now verified bidirectionally against
  `.github/workflows/ci.yml` — renaming, adding, or removing a CI job fails
  the test suite until the declared ruleset is updated deliberately, so the
  release-tag/branch protection can no longer silently lag behind CI.
  (#208)
- Waitlist slice 3 remainder (H15 — path-A email parser + invite sender):
  `site/waitlist_patha.py` implements the email intake path
  (WAITLIST_OPERATIONS.md §2) — exclusion list (From, inbox,
  @agentmail.to) applied before counting, `Owner:` line override, the
  optional ed25519 pubkey + ≤280-char use-case line, exactly-one-candidate
  proceeds to a validated row with the path-A confirm opener, zero/≥2
  candidates get the §2 clarification reply only on DMARC-aligned mail
  (unauthenticated mail is silently triaged — no backscatter), a reply
  saying "forget me" triggers the §5 confirmation email with the signed
  forget link (never direct deletion), and the §6 per-sender 3/day intake
  limit; `site/waitlist_invites.py` drives §7 invite waves (top-N
  confirmed FIFO by confirmed_at, pricing + trial terms filled at send
  time from operator files, signed position line, 14-day `invite.`-prefixed
  HMAC claim tokens, `invite_sent` funnel events) plus the expiry
  rollover (unclaimed invites return to `confirmed` with confirmed_at
  reset to the expiry time, no re-confirmation). (#203)
- Competitor watch 2026-09-21 (docs/COMPETITOR_WATCH_2026-09-21.md): quiet
  window — no launches, pricing changes, partner moves, or version bumps
  across the tracked set since the 2026-09-20 pass; boat.dev's rate card
  re-verified ($20/mo = 555h of 4vCPU/8GB) with an xlarge
  capacity-allocation caveat flagged for verification before any 16-vCPU
  sizing decision; version resolution — Microsandbox v0.7.1 confirmed on
  the vendor releases page post-window (corpus record vindicated; no
  corpus change). (#191)
- Waitlist forget-me flow (H15 slice 3c): every transactional email footer
  now carries a signed one-click forget link (7-day, single-use,
  domain-separated from confirm tokens so the two can never validate at
  each other's endpoint); the signed link renders a delete-confirmation
  page and, on POST, atomically deletes the waitlist row, logs the
  `forgot` funnel event, and spools the spec-mandated deletion
  confirmation. The marketing page's `/go/selfhost` CTA now has both a
  no-JavaScript static redirect shim for the static host and a dynamic
  control-plane route that logs the `cta_click` event before redirecting
  to the self-host guide. The waitlist form's action posts to the
  control-plane origin via a deploy-time placeholder the operator fills
  at launch (a relative action would post to the static host, which has
  no serving layer). (#190)
- boat.dev 16-vCPU caveat confirmed as current vendor policy
  (docs/COMPETITOR_WATCH_2026-09-21_C17.md): the pricing page still
  footnotes xlarge as needing a $100+/mo plan plus operator capacity
  allocation, so any 16-vCPU hosted sizing must confirm capacity with the
  provider first; the baseline rate card is unchanged ($0.036/h default,
  stopped sandboxes free, $26 for one default running the whole month).
  (C17; #206)
- Competitor watch 2026-09-21 afternoon
  (docs/COMPETITOR_WATCH_2026-09-21_AFTERNOON.md): quiet window — no
  launches, pricing changes, releases, or partner moves across the
  tracked set since the morning pass; boat.dev's pricing page re-read
  and unchanged, and its twelve-provider comparison table verified as
  the page's current state (the earlier read was simply partial);
  Microsandbox still at v0.7.1, Docker Sandboxes still at 0.43.0, Daytona
  changelog still topped at v0.214.0 (Sep 15), TermSquad tiers
  re-verified unchanged; WSO2 reception broadens slightly ahead of the
  Sep 29 webinar. No corpus changes. (#209)
- Secrets posture page (#189): frames the placeholder-swap design as
  independently re-derived — the pattern is convergent across the industry —
  and compares swapd mechanism-by-mechanism against E2B, Daytona, Vercel,
  Cloudflare, and Microsandbox from their own docs (vendor links inline).
  States swapd's honest edges (request-body injection scope, response
  scrubbing, per-decision audit-as-authorization) and its conceded gaps
  (Microsandbox's DNS-pinned destination gate, E2B's per-request token
  minting), plus the concrete `allowOut`-vs-swapd egress-grant difference.
- First test suites for the two remaining untested components (O4): `cua/`
  gets hermetic tests for the `cua-bridge.py` localhost bridge — launch
  allowlist enforcement, the CSRF/host gate, window picking, and the
  click/type/key/launch endpoints (including the desktop→window coordinate
  mapping and the panel global-click branch) — plus syntax/shebang checks
  for the `cua/bin` shell scripts; `jail/` gets a hermetic smoke test for
  `build.sh` pinning its strict mode, idempotency guards, and the jail's
  documented isolation properties (no bind mounts, no DNS, proxy-only
  nftables egress, explicit UID range, sshd hardening, swapd CA temp
  cleanup). Both suites are wired into the CI `python-tests` job. (#187)
- Stopped/cold retention tier thinking (C15): the hosted pricing thinking
  now names the stopped-state cost story the live-control deep scan found
  missing — a published $0.000027/GB-hour cold-storage anchor (≈$0.79/mo
  for a stopped 40 GB box), running-only billing precedent, and the
  control-plane→billing contract the H4 provider interface already ships.
  Thinking only; no pricing-page row until the Billing decision lands.
- Waitlist 30-day post-drop purge: `waitlist_jobs.py --purge` permanently
  deletes dropped waitlist rows 30 days after the drop (the §5 retention
  rule), via an atomic `rows.jsonl` rewrite under the same data lock as
  the reminder/drop jobs — the funnel events stay as the audit trail.
- H4 provider interface contract: the provider-agnostic driver every
  sandbox backend implements, reconciling the H3 signup design, the
  suspend/wake and Fly/GPU provider research, and the #47 lifecycle
  audit into one buildable target — six verbs (provision, status,
  suspend, wake-on-dial, ssh_info, destroy; snapshot reserved), a validated box
  lifecycle state machine, per-shape suspend capability flags, a
  billing-facing disk-retention descriptor for idle/stopped boxes, and
  a fail-closed no-public-ingress rule the control plane verifies after
  provisioning. Park-style backends (RunPod's "suspend" is park) are
  representable via the `wake_reprovisions` capability flag and the
  `wake_kind` resume-path surface, and the per-`vm_id` lifecycle is marked
  provisional on H11's isolation-shape answer ([#183](https://github.com/ntindle/spark-vm/pull/183)).
- README "See it in action" gallery: the five demo GIFs (secret-swap proxy,
  approval loop, job runner, desktop persistence, phone credential UI) now
  sit on the repo landing page next to the stack they demonstrate, with
  each frame's provenance and regeneration recipe in the assets notes
  ([#188](https://github.com/ntindle/spark-vm/pull/188))
- README "What's in the box" names the human-approval loop (`confirmd`)
  alongside the proxy/job-runner/desktop/cred-UI stack, and the repo
  layout table now lists `deploy/`, `harness/`, `site/`, `assets/`, and
  the `VERSION`/`CHANGELOG.md`/`CONTRIBUTING.md` process files (#182).
- Lifecycle parity audit for the #47 live-machine-control ticket: #47's
  promised-vs-accepted lifecycle surface checked against the six-provider
  live-control scorecard. Found pause/resume promised in the ticket but
  missing from its acceptance criteria, undefined stream-ownership
  semantics for the live desktop, no idle lifecycle policy model, and an
  undecided stopped-state/file-browsing scope — filed as #177, #178, #179,
  and #180. Also closes the deep-scan's unscored file-browsing and restart
  columns.
- Release and branch protection declared as code (`deploy/rulesets/`): a
  `v*` tag ruleset that makes the release notes' "tags are never moved or
  re-cut" claim platform-enforced (blocks tag update/deletion, with a
  stricter variant that also restricts tag creation to the release
  workflow), plus a `main` branch ruleset (no deletion, no force-pushes,
  PR-required, all CI checks green on an up-to-date branch before merge —
  deliberately no human-approval gate so the improvement loop can keep
  self-merging). An auditable `scripts/apply-rulesets.sh` (dry-run default,
  `--check` drift compare, `--execute --yes` idempotent apply) applies them;
  applying is an owner decision (#174)
- Jail firewall runtime watchdog (closes #254): a 5-minute systemd verify
  timer pins the jail's nftables enforcement rules themselves (drop-rule
  markers + proxy DNAT — the chains are policy accept, so chain shells
  alone prove nothing). On confirmed damage it is fail-closed: the jail
  is stopped first (a table re-apply doesn't flush conntrack, so
  hole-era flows would otherwise survive), then the table is re-applied
  (scoped to the jail table only), and the unit goes red — restart is
  the operator's explicit decision. The old "flushed table silently
  voids the isolation guarantees until someone restarts the unit" hole
  becomes bounded downtime instead of unbounded unenforced running.
  (#260 — entry placed at the end of Unreleased/Added so the branch
  merges cleanly over #263's same-section entry)
- Afternoon competitor watch (2026-09-22): the DigitalOcean Managed
  Agents launch blog added the mechanism detail the morning pass lacked —
  Firecracker microVMs per session, auto-pause defined precisely as "no
  outgoing LLM or tool calls," a 99.3% intent-match claim for Action
  Gateway tool search, a $0.060 vs $0.126 active-CPU worked pricing
  example, live product docs with a prepaid-balance billing model, and a
  self-published benchmark naming Fly.io Sprites as the comparator
  (886 ms create→ready, 189 ms exec RTT, 305 ms resume); the rest of the
  tracked set was quiet. Inputs filed for #47 (benchmark reference
  numbers, edge-routing latency datapoint) and #179 (auto-pause idle
  trigger). (#268)
- Late-evening competitor watch (2026-09-22): the tracked set was quiet
  across all eight vendor re-reads; the Boxd entry is upgraded from
  third-party-only to vendor-verified (their own site and docs read this
  pass) — fork of a live machine lands in under 200 ms (correcting the
  <100 ms press claim), the active-connections-fork claim is NOT
  vendor-attested, plus pricing (€0.049/vCPU-hour, €0.015/GiB-hour RAM,
  €0.0001/GiB-hour disk, €30 free credits) and a confirmed self-hosted
  offering; Boxd's "under a millisecond" idle-resume is a marketing-page
  figure with no published methodology and is not treated as a
  benchmark. (#272)
- Competitor corpus consolidation (2026-09-22): the deferred watch entries
  Deferred competitor entries folded into the competitive map — first
  entries for boat.dev ($0.036/h default; xlarge capacity-gated),
  DigitalOcean Managed Agents ($0.044/vCPU-hour active-CPU metering),
  Boxd (vendor-page-verified fork claims and pricing),
  Upstash Box (snapshot/restore mechanics), h-sandbox (OSS credential-vault
  comparand), Brig (local microVM containment), and Epho (agents-as-API with
  multi-provider fallback), plus the OpenAI Agents API harness↔compute split
  as a design input for the hosted product's per-harness adapters. (#274)

### Changed

- Hosted pricing thinking refreshed: the internal pricing analysis now
  reflects the decided Fly.io provider (boat.dev under evaluation as a
  cheaper alternative), records Epho's bring-your-own-keys infra-only
  metering as a candidate shape for model-token billing (zero margin risk),
  and drops the stale merge-order note — all cited strategy docs are on
  main and price inputs re-verified through the 2026-09-21 competitor
  reads. (PR #253)

### Fixed

- The two privileged install-safety regression tests (staged-temp
  substitution and staging-dir swap) previously self-skipped in CI because
  runners are non-root, so the merge gate never actually exercised the
  guard they prove — they now run under sudo on every PR, and a skip in
  that step fails the build instead of passing silently. The stale "no
  root" header on the test module and the "atomic via O_EXCL" comment in
  the deploy script are corrected to match. (#345)
- The auto-deploy updater re-verifies the working checkout is clean
  immediately before syncing a component subtree into it, not just at the
  pre-deploy gate: a manual edit made between the gate and the install no
  longer gets silently clobbered — the deploy aborts with an alert and
  retries on the next tick, without marking the commit blocked (components
  already installed in the same run are rolled back first). (fixes
  #324, PR #338)
- The deploy health check now reads the port as the trailing `:digits`
  field and treats everything between `tcp:` and that field as the host.
  Malformed entries (missing or non-numeric port, empty host) fail the
  health check closed with a clear log line instead of being probed
  with a garbage port. (fixes #323, PR #328)
- A failed swap audit no longer emits a false approval signal: the
  credential proxy records the grant's `approved:<id>` terminal signal
  only after the audit write succeeds and the substituted credential is
  actually returned. Previously the signal was recorded during resolution,
  so a swap vetoed by the audit gate still told the requesting agent its
  credential had been approved and swapped. (fixes #305, PR #328)
- The auto-deploy pre-deploy gates now cover every test module in each
  component: four proxy test suites (install safety, CA bundle, secrets-dir
  enforcement, credential-validation grammars), confirmd's push-queue tests,
  and the full cred-ui HTTP/version suites had silently drifted out of the
  gate, so a green gate said nothing about them. A new tripwire test pins
  the gate commands against the test files on disk so the gap can't recur.
  The stale-updater warning (a merged updater fix that nobody activated with
  `init`) now also fires on the automated deploy path, not just
  `check`/`status`, since the timer only ever runs `deploy`. (#326)
- The Daytona isolation quote in the multi-tenant isolation research is
  re-sourced: the vendor's security-exhibit page was retired (it now
  redirects to their Trust Center, where the quoted claim no longer
  appears), so the citation points at the vendor's own docs source pinned
  at the file's final revision before removal — the quoted claim is
  byte-identical to the one surveyed earlier. (#319)
- The answered-approval history feed no longer re-parses every approval
  file in the on-disk archive on each 5-second poll — it reads only the
  200 most recent, so poll cost stays flat as the archive grows to its
  1000-file bound (the visible feed still shows the 100 newest
  approvals). (#315)
- Approvals whose expiry instant crosses during grant minting are now
  refused with a distinct audit event instead of being recorded as
  approved — the trust anchor "expired items are refused, not silently
  denied" holds even across the up-to-15-second mint window (#240).
- The credential web UI's HTTP server now drops stalled connections at a
  10-second bound: a client that declares a request body and then stalls
  can no longer pin a server thread forever (#282).
- The jail build now fails loudly if the proxy-helper script it generates
  for the jail has a quoting slip: the generated script is syntax-checked
  at build time, and the build smoke tests pin the generated script's
  shape so an unescaped variable can't silently corrupt it. (#290)
- Credential validation rules are now canonical everywhere they are
  checked — the credential CLI, the credential web UI, and the registry
  writer previously disagreed on edge cases (over-64-character names,
  over-long host bindings, and `_`/`.` in custom header names were accepted
  in some places and rejected in others). Names are now capped at 64
  characters, host bindings at valid DNS shapes (253 total / 63 per label),
  and header/query placement names at 64 characters, with a shared
  conformance test keeping the copies in lockstep. Two deliberate
  carve-outs for credentials registered before the cap: the swap proxy
  keeps serving them, and management/read operations still work on those
  legacy names — get/delete/unregister in the CLI, delete and host-unbind
  in the web UI, and the full management verb set (remove, host
  bind/unbind, method/path limits, scrub flags) in the registry writer.
  Creating new entries (set/register) — or minting a credential through a
  management verb — always requires a within-cap name. (#276)
- The inference proxy's host allowlist matcher now recognizes IPv6
  literals: a `::1` entry previously never matched (the address was
  mangled before comparison), so an operator allowlisting the IPv6
  loopback had dead config while the enforcement checks stayed blind to
  it. Literals now compare as normalized addresses (`[::1]`,
  `[::1]:8080`, and trailing-dot spellings included); a hostname entry
  never matches a literal host. (#257)
- Fixed a normalization-order regression in the same matcher (found in
  adversarial review of #264): `example.com.:8080` no longer matched
  `example.com`, which would have let a trailing-dot host:port slip past
  fail-closed deny-name entries. The trailing dot is stripped after the
  port now, on both sides of the shared matcher, and the case is pinned
  in the test corpus so it cannot regress again. (#265)
- Provision-time credential teardown now recognizes every IPv4 spelling of
  loopback (e.g. `127.1`, `127.0.0.2`, `0x7f.0.0.1`, `2130706433`,
  `0177.0.0.1`) as the live echo exemptions they are: these forms match
  exactly at the proxy and resolve to loopback on the machine, but the
  teardown previously saw only the canonical `127.0.0.1`/`localhost`
  spellings, so a binding or allowlist line written in a non-canonical
  spelling would have survived teardown undetected. (#259)
- Provision-time credential teardown now treats leading-dot entries (e.g.
  `.localhost`) as the live loopback exemptions they are: previously only
  bare loopback names were unbound or refused, so a `.localhost` binding
  or allowlist line would have survived teardown while the proxy still
  swapped credentials toward loopback names. The three echo-detection
  checks are now one shared implementation pinned against the proxy's own
  matching semantics by a drift tripwire, instead of three hand-mirrored
  copies that could drift apart unnoticed.
- The provision-time tenant attribution record is now written atomically
  (temp file plus rename): a crash mid-write can no longer leave a
  truncated record for the per-tenant approvals wiring to consume.
- Test hermeticity and coverage hardening (dx turn): the push-endpoint
  tests no longer touch `/home/swapd` (approvals dir redirected at tmp),
  the deploy rollback suite redirects the literal system paths
  (`/etc/sudoers.d/swapd`, the CA bundle, logrotate) at tmp via new
  `components.conf` env overrides so it never touches the host on a
  deployed box, and the CRLF-only refusal case, the live-symlink-target
  removal case, and the dangling-symlink snapshot round-trip are now
  pinned. (#247)
- README repo-layout table: the `harness/` and `site/` rows now describe
  the current tooling — the provision-time injector and the waitlist
  invite operator tools. (#246)
- First-ten-minutes spec conformance audit (gap turn): the new
  conformance-gap doc checks every spec clause against the repo — four
  clauses still unmet (the onboarding status poll with the spec's machine
  vocabulary, the first-approval summons channel, the golden-image
  round-trip gate procedure, the §3a smoke echo endpoint and dummy
  credential) are filed as build items G3–G6; the signup onboarding doc's
  stale "free tier first" plan-picker lines are corrected to the decided
  no-free-tier / card-required-trial-possible position, and the
  operator-only `policy-misfire` / `no-gated-action` note the spec's
  §10 follow-up asked for is in the rendering table. (#245)
- An invite wave interrupted mid-send can no longer strand a waitlist row as
  invited with no email on the way: each invited row commits in a single step
  after its email is queued, so a crash degrades to a duplicate email on
  retry instead of a lost invite (#220).
- Waitlist invite crash recovery is now pinned by fault-injection tests
  (deferred follow-ups from #220): the remaining crash windows — after an
  old invite token is retired but before the row commits (re-invite and
  expiry rollover), and between the commit and the `invite_sent` metric
  event — are exercised against the documented behavior: in the re-invite
  window, recovery mints a fresh token (the stray email's claim link
  validates as consumed at the service layer); in the rollover window the
  retired token stays consumed with no new email; and the metrics never
  claim what the on-disk rows don't show (#236).
- README, ONBOARDING, and the pre-seeded-harness research doc now point at
  the real `cua/bin/cua-desktop.sh` path (the script moved into `cua/bin/`
  and the old `./cua/cua-desktop.sh` reference broke the desktop step of
  the copy-paste install block) (#182).
- The approvals page daemon no longer accumulates unbounded state over its
  lifetime: answered history on disk is now retained to the newest thousand
  entries (tunable), instead of growing one file per approval forever while
  every poll re-read all of them; the per-approval lock entries are likewise
  released when an approval is answered or expires (#196).
- README follow-up polish: "What's in the box" now names the inference
  proxy alongside the egress proxy (the agent's own model API calls
  authenticate with a placeholder too), the layout table's `deploy` row
  drops a redundant word, `harness` links the pre-seeded-harness research
  doc instead of assuming its jargon, and `site` drops the time-stamped
  "Waitlist-era" label. (#201)
- Docs index catches up with the week's new docs: the four 2026-09-21
  competitor watches (evening, afternoon, C17 resolution, morning), the
  secrets-posture repositioning doc, and the Fly-driver and suspend/wake
  research docs are now listed, and the stale "latest" labels in the
  competitor and loop-governance tables are corrected to dated style.
  (#218)

### Security

- `muse-job log` now sanitizes the job terminal it prints: the pane
  content an agent controls goes through the same ANSI/control-character
  sanitizer as every other operator-facing surface, so a crafted pane
  can't inject escape sequences into the operator's terminal. (#290)
- The dead-TUI steer refusal error now sanitizes the pane tail it prints:
  the up-to-8-lines of agent-influenced terminal content in the refusal
  are stripped of escape/control sequences before reaching the operator's
  terminal. (#290)
- The provision-time injector's tenant-identity install and
  tenant-attribution write no longer resolve their destination paths
  twice: both pin the destination directory with no-follow semantics
  and create/write through the open file descriptor, so a symlink (or
  other non-regular file) swapped in between the check and the write is
  refused -- or, for the attribution record, atomically replaced rather
  than followed. The attribution write also reports its digest lifecycle
  (initialized/updated) for the operator log. (#258)
- The unattended deployer's rollback snapshot and restore steps now
  distinguish "this file is absent" from "the privilege check itself
  failed" (broken sudo): a broken check aborts the snapshot and fails
  the restore loudly instead of silently recording live files as absent
  or silently skipping their removal, and a corrupted snapshot manifest
  line with an empty path fails the restore instead of being skipped.
  (#103, #107; #243)
- The with-proxy CA bundle and the jail's swapd-CA install no longer read the
  swapd-controlled CA through symlink-following `cat`/`cp` as root: a new
  `proxy/build_ca_bundle.py` refuses a planted symlink (or FIFO/directory) at
  the CA source and writes the bundle through the existing safe installer
  (root:root 0644) — a swapd-level attacker can no longer get the next
  unattended deploy to leak a root-readable file into the world-readable
  bundle (#144, #207).
- The approvals page daemon no longer lets its expiry sweep collide with an
  in-flight approval answer: the sweep now waits its turn behind the same
  per-approval serialization as the answer path, so an approval expiring
  mid-approval can no longer drop the owner's connection with an unhandled
  error after the grant was already minted, and an expired approval can no
  longer briefly reappear after being swept. The audit trail also gains a
  distinct event when an approval vanishes between grant minting and
  consumption, instead of logging a contradictory expired-plus-approved pair
  (#233). Dead approval files that never reached the answered list are now
  swept into it after a day, so they no longer pile up unseen (#233).
  Missing or unreadable approval files also release their per-approval
  lock entries now, instead of leaking one registry entry per miss (#231).
  (#241)
- The swap proxy's audit log is now bounded: deploy installs a logrotate
  policy covering every `*swap*.log` under the proxy home (including
  `SWAP_LOG_FILE` overrides like the inference proxy's log) —
  size-triggered rotation keeping 12 compressed generations. The log
  previously grew without limit until a full disk failed every swap
  closed (a total outage of credentialed egress). The proxy also guards
  the log's filesystem before each audit write: it warns loudly
  (rate-limited) while space runs low and refuses swaps fail-closed when
  space is critical, so the no-swap-without-a-trail invariant holds even
  if rotation is not installed. Both thresholds are env-tunable (#198, #202).
- The egress proxy no longer swaps a credential anywhere when its registry
  placement is declared but not recognized (e.g. a typo'd placement kind):
  such swaps are now refused with a loud warning instead of silently
  degrading the location restriction into swap-anywhere. Entries with no
  declared placement keep the migration behavior (#197, #200).

- Hardened the deploy-time CA bundle build and install against three
  remaining local-attacker primitives: the CA source now refuses hardlinks
  (a hardlink is a regular file, so the earlier symlink refusal didn't
  stop it), refuses files over 1 MiB before the privileged read (no more
  unbounded RAM/disk fill from a planted file), and installs bundles with
  an atomic rename — a racing reader now sees the old or the new bundle,
  never a truncated one. (#299, #300, #301)

## [0.2.0] - 2026-09-20

### Added
- A docs index for the docs tree (`docs/README.md`): the 40-plus doc corpus
  organized by what you're trying to do — start-here contributor picks,
  hosted-product design specs, the product-research corpus, the dated
  competitor corpus, and loop governance, with a keep-this-index-honest rule
  for new docs; the root README's repo-layout table links to it (#171)
- Live-control competitor deep-scan for the #47 control-plane design: six
  providers (AgentComputer, TermSquad, Fly.io Sprites, E2B, Daytona, Docker
  Sandboxes) scored on browser desktop streaming, live terminal,
  suspend/wake, and transport, with where-we-win/lag findings feeding three
  new backlog items — the #47 resume-latency target (C14), the stopped/cold
  cost tier for hosted pricing (C15), and the control-plane-visible lifecycle
  parity audit (C16) (#168)
- Waitlist page build, slice 2: the waitlist service backend — the form
  endpoint (honeypot and timing-trap defenses that accept spam silently,
  per-IP rate limiting, email normalization and dedup), the double-opt-in
  confirm flow (render-only link page, one-click confirm, single-use
  HMAC-signed tokens with 14-day expiry, the 3-per-day email cap), and
  funnel-event logging the metrics script already consumes. The operator
  key and data dir come from environment variables, never the repo. Still
  not deployable: reminder/drop jobs, the email-parsing path, invites,
  and forget-me land next; the page ships only when the full
  waitlist-operations checklist is green (#165)
- Waitlist page build, slice 3a: the waitlist lifecycle jobs — one reminder
  email at +7 days (the last touch; there is no third email) and automatic
  drop of unconfirmed rows at 14 days, run as operator cron jobs with a
  cross-process lock so they never race the live service. The drop deadline
  is fixed at first signup and never postponed by re-signups. Oversized
  requests now close the HTTP connection instead of risking a desynced
  keep-alive. Still not deployable: the email-parsing path, invites, and
  forget-me land next; the page ships only when the full
  waitlist-operations checklist is green (#172)
- Browser-driver first code (H17, [#132](https://github.com/ntindle/spark-vm/issues/132)):
  the fixed `bdrive` action protocol as validated Python — the narrow action
  vocabulary the on-box browser service will accept, with ref-scoped element
  locators, receipt semantics, and hermetic tests. Deferred to later slices:
  the Chromium execution backend, the daemon socket, box hardening, the
  `obox` agent loop, and the card pathway + Web Push (#166)
- Waitlist page build, slice 1: the static front end of the waitlist-era web
  surface — the landing page typeset from the approved launch copy, a
  dedicated `/waitlist` form page with the abuse-resistant signup form
  (owner email, optional agent contact, honeypot and timing defenses, no
  page JavaScript), and a derived social-card image reused from the shipped
  demo asset. **Not deployable yet:** the form's backend (signup endpoint,
  confirm flow, invite jobs) comes next, and the page ships only when the
  full waitlist-operations checklist is green
  ([#163](https://github.com/ntindle/spark-vm/pull/163))
- Build-update template and cadence contract for Spark's daily spark-vm updates
  on musebook.lol: `docs/MUSEBOOK_UPDATES.md` defines the template, the honesty
  rules (no hosted-launch or pricing commitments until the launch is
  executable), and a sample post
  ([#162](https://github.com/ntindle/spark-vm/pull/162))
- Funnel query pack for the waitlist operator: a log-derived, no-cookie,
  no-tracker weekly report (page conversion, CTA click-through by section,
  interim raw vs DMARC-aligned confirm rate with the manufactured-row spray
  signature, reminder lift, invite-to-claim, submit-to-confirm latency) —
  the §7 deliverable of the funnel measurement spec
  ([#141](https://github.com/ntindle/spark-vm/pull/141))
- Changelog ritual: this `CHANGELOG.md` (Keep a Changelog format), the
  per-PR entry requirement in `CONTRIBUTING.md`, and release-time rollover
  in `docs/VERSIONING.md`
  ([#65](https://github.com/ntindle/spark-vm/pull/65))
- Approval pages rebuilt mobile-friendly: the pending list auto-refreshes,
  Approve is a two-tap confirm safe against double-taps, and the answered
  page keeps the 100 most recent ([#20](https://github.com/ntindle/spark-vm/pull/20),
  fixes [#1](https://github.com/ntindle/spark-vm/issues/1))
- Push notifications for approvals: get a push on your phone/desktop when an
  approval is pending; the operator generates one keypair, you subscribe on
  the pending page, and `--test-push` verifies delivery end to end
  ([#48](https://github.com/ntindle/spark-vm/pull/48), closes
  [#2](https://github.com/ntindle/spark-vm/issues/2))
- One version everywhere: every component now reports the same `VERSION` —
  `confirmd` and `cred-ui` at startup and on `/api/version`, `muse-job
  --version` — so an operator can always answer "what's actually deployed?"
  ([#52](https://github.com/ntindle/spark-vm/pull/52))
- Unattended redeploy updater: merged code reaches the live services on its
  own, with the deployed version recorded in the audit log and rollback
  covered ([#29](https://github.com/ntindle/spark-vm/pull/29), fixes
  [#22](https://github.com/ntindle/spark-vm/issues/22))
- `muse-job` hardened against hostile agent output: session-lifecycle trust
  boundary ([#43](https://github.com/ntindle/spark-vm/pull/43)) and
  event-trust hardening ([#19](https://github.com/ntindle/spark-vm/pull/19),
  fixes [#3](https://github.com/ntindle/spark-vm/issues/3))
- Control-panel spec so anyone can build their own computer-control panel,
  with a worked Blender example; the bridge allows the SSH-forwarded tunnel
  endpoint ([`811920b`](https://github.com/ntindle/spark-vm/commit/811920b),
  [`57f24f5`](https://github.com/ntindle/spark-vm/commit/57f24f5),
  [`fc06cbb`](https://github.com/ntindle/spark-vm/commit/fc06cbb))
- Hosted-product design docs: signup/onboarding identity linking with a
  provider-agnostic provisioning interface
  ([#24](https://github.com/ntindle/spark-vm/pull/24)); first-run activation
  funnel ([#37](https://github.com/ntindle/spark-vm/pull/37)); agent-sandbox
  adoption research ([#25](https://github.com/ntindle/spark-vm/pull/25));
  pre-seeded harness research ([#51](https://github.com/ntindle/spark-vm/pull/51));
  beta-Muse first-run pilot protocol ([#32](https://github.com/ntindle/spark-vm/pull/32));
  hosted pricing thinking ([#30](https://github.com/ntindle/spark-vm/pull/30));
  hosted vision-vs-repo gap analysis
  ([#31](https://github.com/ntindle/spark-vm/pull/31))
- Strategy and positioning docs: agent VM/sandbox competitor analysis
  ([#26](https://github.com/ntindle/spark-vm/pull/26)); GPU path research for
  the provider decision ([#40](https://github.com/ntindle/spark-vm/pull/40));
  evening competitor-watch pass ([#44](https://github.com/ntindle/spark-vm/pull/44));
  persistence-as-headline positioning
  ([#28](https://github.com/ntindle/spark-vm/pull/28)); launch announcement
  copy ([#36](https://github.com/ntindle/spark-vm/pull/36)); README
  30-second-scan clarity pass ([#46](https://github.com/ntindle/spark-vm/pull/46))
- Contributor hygiene: `CONTRIBUTING.md`, `SECURITY.md`
  ([#58](https://github.com/ntindle/spark-vm/pull/58)), MIT `LICENSE`
  ([`52960f0`](https://github.com/ntindle/spark-vm/commit/52960f0))
- Fly.io driver research for H4: grounds the provider-agnostic provisioning
  interface and planned contract extensions (suspend/wake, async dial,
  gpu_class routing, destroy-deletes-volumes) against the real Machines API
  ([#140](https://github.com/ntindle/spark-vm/pull/140))
- Documented the quarterly manual re-sweep ritual for the three link hosts
  CI's link checker skips as bot-blocked (medium.com, businesswire.com,
  globenewswire.com) with a verification log — all 11 links (7 unique
  URLs) confirmed live on 2026-09-22 (closes #106) (#249)

### Changed
- Identity cleanup: deployment docs use the `ntindle` login account
  ([#35](https://github.com/ntindle/spark-vm/pull/35)); separately, the
  agent itself is `spark`, and every path in the repo is `$HOME`-relative
  so docs never hardcode a username
  ([`a8fd18d`](https://github.com/ntindle/spark-vm/commit/a8fd18d))
- README rewritten around the bigger-computer idea, with the Spark
  illustration ([`c09a65a`](https://github.com/ntindle/spark-vm/commit/c09a65a),
  [`7e7ffea`](https://github.com/ntindle/spark-vm/commit/7e7ffea))
- `push.sh` / `pull.sh` sync scripts: dry-run mode, preflight checks, and a
  space-safe secret scan ([#33](https://github.com/ntindle/spark-vm/pull/33))

### Fixed
- Root deploy writes stop following symlinks in `/home/swapd`: `cp`/`tee`/
  `chown`/`chmod` on `ssrf.deny`, `grants.json`, and `swap.log` would have let
  a swapd-level attacker plant a symlink at a root-write destination and get
  the next unattended deploy to write/chown through it (same class as #91,
  fixed for the secrets dirs; the grants.json instance is #128). The new
  `proxy/safe_install.py` refuses symlinks fail-closed, creates with
  `O_EXCL`+`O_NOFOLLOW`, and `fchown`s/`fchmod`s the open fd; steps 3/4/4a of
  `proxy/deploy.sh` use it
  ([#143](https://github.com/ntindle/spark-vm/pull/143), fixes
  [#128](https://github.com/ntindle/spark-vm/issues/128)) Also fixes a latent grants.json wipe: the old
  existence check ran as the deploy user, so when `/home/swapd` wasn't
  traversable it always took the create branch and `sudo tee` truncated the
  file on every deploy.
- `confirmd` and its health check no longer pin the box's tailnet IP: the
  `CONFIRM_BIND` literal is gone from `confirm/confirmd.service` (the daemon
  already resolves its bind via `tailscale ip -4` at startup), and the
  updater's health entry is `tcp:TAILNET:8443`, resolved at check time. A
  tailnet rekey/IP change survives a restart instead of wedging the service
  or failing every deploy's health check (rollback of a good deploy)
  ([#143](https://github.com/ntindle/spark-vm/pull/143))
- The updater now warns when it runs stale code: `init` records the checkout
  commit the installed copy came from, and `status`/`check` warn when
  `origin/main` carries newer `deploy/` changes not live because `init`
  wasn't re-run
  ([#143](https://github.com/ntindle/spark-vm/pull/143))
- `muse-job` detects a dead terminal pane and refuses to steer into it
  instead of typing into the void
  ([#45](https://github.com/ntindle/spark-vm/pull/45), fixes
  [#4](https://github.com/ntindle/spark-vm/issues/4))
- Setup no longer teaches a shell-history-leaking secret install: the
  `cred set` examples now use the no-echo prompt (or `read -rs` when the
  no-echo prompt isn't convenient) so typed values never land in shell
  history
  ([#135](https://github.com/ntindle/spark-vm/pull/135), fixes
  [#89](https://github.com/ntindle/spark-vm/issues/89))

### Security
- Proxy hardening round
  ([#18](https://github.com/ntindle/spark-vm/pull/18))
- Fixed critical and high findings from the security code review
  ([`dd382af`](https://github.com/ntindle/spark-vm/commit/dd382af))

[unreleased]: https://github.com/ntindle/spark-vm/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/ntindle/spark-vm/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ntindle/spark-vm/releases/tag/v0.2.0
