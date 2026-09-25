# Competitor watch — 2026-09-25 (pre-dawn)

Delta-only update against the 2026-09-25 post-midnight pass
(`docs/COMPETITOR_WATCH_2026-09-25_POST_MIDNIGHT.md`). Survey window
**2026-09-25 ~02:56–03:01 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set; (B) the carried asks (C26, C37, C41,
Tensorlake, Grunz), the Google AX v0.3.0 primary-source pass, and an
open-web in-lane news scan dated 2026-09-24/25. Surveyor captures live
in the loop's `agent_notes/` workspace
(`surveyor-tracked/a-20260925-0254.md`,
`surveyor-tracked/b-20260925-0254.md`), not the repo. `_PREDAWN`
admitted per the nearest precedent
(`docs/COMPETITOR_WATCH_2026-09-24_PREDAWN.md`, same suffix one day
prior — verified collision-free against origin/main's watch-doc list).

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
  SEP 24 V0.216.2, SEP 23 V0.216.0 — no new entries. GPU ladder
  unchanged (B300 $4.08/h preemptible down to RTX 4090 $0.57/h);
  compute $0.0504/vCPU-h, mem $0.0162/GiB-h.
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Still tops at
  **2026-09-21** (v3 kits); nothing dated 09-22 through 09-25.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby
  free + $100 one-time credit; Pro $150/mo; per-second vCPU ladder
  unchanged.
- **boat.dev — VERIFIED NO-CHANGE** (pricing:
  https://docs.boat.dev/pricing). $0.018/$0.036/$0.072/$0.200 sizes,
  $20/$100/$500/$2000 plans, 25h trial — verbatim. Product-news retry
  stays retired (VERIFIED absent ×4).
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases). Latest
  still **v0.7.3**.
- **TermSquad — VERIFIED NO-CHANGE** (https://termsquad.com/pricing).
  $9/$19/$29/$49 verbatim (2/4/6/8 vCPU, 4/8/12/24 GB,
  40/75/100/200 GB NVMe); "AI subscriptions and usage are not
  included" still explicit.
- **AgentComputer — VERIFIED NO-CHANGE, digit-for-digit**
  (https://agentcomputer.ai/pricing). $0.07 CPU-hr, $0.04375 GB-hr,
  $0.000683 hot, $0.000027 cold; Enterprise custom.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE** (vendor's
  own release-notes page: Managed Agents entry still the Sept 21
  public-preview announcement; newer Sept 22/23 entries are unrelated
  products). Rates THIRD-PARTY/snippet-only: Sept 22 investor release
  $0.044/vCPU-hr, $0.0095/GB-hr, $0.005/GiB-month — no newer rate
  announcement found.

## 2. Corpus folds — two new entries

- **C47 new — Google AX v0.3.0** (orchestrator, harness lane;
  primary-source VERIFIED). The post-midnight pass's hedged
  new-to-watch candidate has now had its primary-source pass: read
  [github.com/google/ax](https://github.com/google/ax) live this
  run — **Apache-2.0** VERIFIED; README: *"AX is a high-throughput,
  declarative orchestrator to run billions of autonomous agent
  workloads in a cluster. It runs on top of [Agent
  Substrate](https://github.com/agent-substrate/substrate) for sandboxed
  execution"*; kubectl-shaped CLI (`ax apply/get/describe/watch`,
  plus `ax suspend` / `ax resume` / `ax ssh`); three primitives
  (`Task` / `Workspace` / `Model` as `ax.io/v1alpha1` manifests);
  pre-stable warning verbatim ("We will likely introduce major
  breaking changes prior to a stable release"); 10,853 stars, 527
  forks. v0.3.0 specifics stay **THIRD-PARTY-convergent** (released
  ~2026-09-20: three-service split, task state to Redis Streams,
  legacy harness removed; third-party teardowns flag ~25 of 56
  manifest fields never reaching the sandbox — kept at third-party).
  Lane characterization (INFERRED): control-plane/harness layer on
  Agent Substrate's sandbox-execution layer — the same two-layer
  split the corpus already recorded at C30/C36; AX is the reference
  ecosystem app on the Substrate repo itself. Folded as **C47**.
- **C48 new — Prime Intellect "Prime Sandboxes" launch** (~2026-09-23;
  **THIRD-PARTY**, in-lane). AlphaSignal: opened to run "30M AI
  agent environments" — "the largest environment catalog available
  from a sandbox provider"; usage-based billing, **no subscription
  tiers or minimum commitments**; vCPU **$0.02/hr**, memory
  **$0.0125/GiB-hr**, disk **$0.0002/GiB-hr**; Prime says launch rates are
  about **one-third of other large sandbox providers**; promo
  pricing through **December 22** (no post-promo rates published).
  Workload positioning: RL training rollouts, synthetic data
  generation, evals, persistent remote agents. Currently CPU-only —
  GPU microVMs, state snapshots, sandbox forking, and shared
  persistent workspaces all on the roadmap. Note: Prime's own older
  community SKILL.md in PrimeIntellect-ai's prime-agent repo (crawled
  ~21 days ago) documents pre-launch sandbox rates (CPU $0.05/core-hr,
  mem $0.01/GB-hr, disk $0.001/GB-hr) — CPU −60% ($0.05→$0.02/core-hr)
  and disk −80% ($0.001/GB-hr → $0.0002/GiB-hr) clear more than half,
  but memory rises ~16% on a GB basis ($0.01/GB-hr → $0.0125/GiB ≈
  $0.0116/GB-hr); the composite 1 vCPU/1 GiB/32 GiB example falls
  ~58% (~$0.092 → $0.0389/hr). Folded as **C48**.

## 3. Carried asks

- **C45 duplicate closed.** Surveyor B surfaced the Docker Cloud
  Sandboxes 2026-09-24 launch (GlobeNewswire) as a corpus-fold
  candidate — it is the same event already filed as **C45** (early-
  afternoon fold + five garnish layers through post-mid-evening,
  including the GlobeNewswire mid-afternoon garnish). No new move;
  candidate retired, nothing filed.
- **C37 — Pro fee still UNVERIFIED, unchanged.** freestyle.sh/pricing
  re-read: still no Pro dollar line-item (**VERIFIED absent**);
  Hobby $50 minimum re-confirmed verbatim (VENDOR-VERIFIED).
  Signed-in dashboard check still owed (no logins — read-only loop).
- **C26 — 7th consecutive docs-pricing-page miss.** The Sep-22
  launch-release rate set surfaced again (convergent, identical to
  the corpus's standing figures: $0.044/vCPU-hr, $0.0095/GB-hr,
  $0.005/GiB-month + $5 new-user credit) — no corpus change. The
  docs page itself stays unlocated.
- **Tensorlake — no Sep-24/25 news** (stale aggregators only).
  C46 pricing baseline stands.
- **C41 — pin re-verified, still `39b6c3a2`.** GitHub API: no new
  commits since 2026-09-21; billing docs re-read at pinned HEAD —
  all digits unchanged (Eco 0.00936/vCPU-h + 0.004608/GiB-h, Std
  0.01224/0.006012, Pro 0.01872/0.009360, disk 0.00031896 /
  0.00025308 ex-mainland; preview invite-only,
  allowlisted-in-batches). No fold.
- **Grunz — "$100 once" flag downgraded.** The last-pass figure
  (maker's dev.to post, THIRD-PARTY) appears **nowhere** on
  [grunzai.com](https://grunzai.com) (VERIFIED): current pricing is
  pay-per-use credits — never expire, $0 base fee, no subscription,
  messages never stored. The "$100 once" line is stale-or-pivot
  **UNVERIFIED**; the flag retires to light-watch only. Not
  sandbox-shaped; no C-number (unchanged).
- **C44** (newest release-note heading still September 22, 2026),
  **C36** (Cloud Blog text consistent), **C43** ("not billed during
  the preview period" verbatim) — all confirmed unchanged.
- **Vercel Drives** not re-checked (P49 once-daily morning cadence).
  **boat.dev product-news** retry stays RETIRED.
- **In-lane dated 9/25: no launches, no pricing moves, no funding
  rounds in-window** (C47/C48 are out-of-window folds — ~9/20 and
  ~9/23 — newly filed this pass).

## 4. What this means for spark-vm

Nothing in this pass moves the tracked pricing floor (8/8 flat).
The two real moves are both at the lane's edges, and both sharpen
the corpus's two-layer read: (1) **Google AX v0.3.0** — the
orchestrator-vs-sandbox split (C30's harness↔compute datapoint) now
has a Google-built, Apache-2.0 reference implementation with a
kubectl-shaped CLI, `suspend`/`resume`/`ssh` verbs, and a pre-stable
warning — the strongest validation yet that the harness layer and
the execution layer want to be separate products, which is exactly
the per-harness-adapter thesis the corpus already carries for H4.
(2) **Prime Sandboxes** — a launch-priced, usage-based, no-commitment
sandbox at ~1/3 of large-provider rates (CPU-only, snapshots/forking
on roadmap) is the first aggressive undercut among public
large-provider task-scoped rates (below E2B/Modal/Daytona's
active-CPU rates — Modal $0.0710/vCPU-hr equiv, Daytona $0.0504/vCPU-h,
E2B ~$0.054/vCPU-hr implied; the corpus's absolute floor remains
Alibaba FC Eco preview pricing at $0.00936/vCPU-h, C41, billing since
2026-07-31) and deserves a row in the
pricing-pressure discussion. Neither changes spark-vm's persistent-
computer lane positioning. Next passes: Vercel Drives morning check,
C37 signed-in dashboard check, C26 docs page (8th attempt).
