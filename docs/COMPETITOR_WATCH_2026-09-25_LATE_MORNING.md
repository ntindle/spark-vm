# Competitor watch — 2026-09-25 (late morning)

Delta-only update against the 2026-09-25 morning pass
(`docs/COMPETITOR_WATCH_2026-09-25_MORNING.md`). Survey window
**2026-09-25 ~04:25–04:55 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set; (B) the carried asks (C26, C37, C41, C44,
google/ax, Tensorlake, Prime Sandboxes) plus an open-web in-lane
news scan dated 2026-09-24/25. Surveyor captures live in the loop's
`agent_notes/` workspace (`surveyor-a-20260925-0424.md`,
`surveyor-b-20260925-0424.md`), not the repo. `_LATE_MORNING`
admitted per the 2026-09-23 `_LATE_MORNING` precedent — collision-free
on origin/main's watch-doc list for this date.

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
  V0.216.2 ("CLI login through WorkOS"), SEP 23 V0.216.0 ("Confine
  Dockerfile COPY sources to the build context"); no new entries.
  Compute $0.0504/h per vCPU, Memory $0.0162/h per GiB, Storage
  $0.000108/h per GiB (after first 5 free), Windows $0.0858/vCPU/h;
  preemptible GPU ladder top→bottom unchanged (B300 $4.08/h down to
  RTX 4090 $0.57/h); "$200 in free compute included"; per-second
  billing.
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Latest entry
  still *2026-09-21* (v3 OCI kits; `sbx mcp catalog` removed;
  credential-revocation proxy fix; sandbox minimum memory 512 MiB).
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby FREE
  + $100 one-time credit / 1h sessions / 20 concurrent; Pro $150/mo /
  24h sessions / 100 concurrent (expandable to 1,100); per-second
  ladder ($0.000014/s per vCPU) unchanged.
- **boat.dev — VERIFIED NO-CHANGE**
  (https://docs.boat.dev/pricing). Sizes $0.018/$0.036/$0.072/$0.200
  per hour; plans $20/$100/$500/$2000 per month; $20 credit packs
  never expire; Trial 25 free hours, 2 sandboxes, small+default only,
  until first payment. Verbatim line present: "One `default` sandbox
  24/7 | 730 h × $0.036 = $26". Comparison table (E2B/Daytona/Blaxel
  $0.331 default-hour) unchanged.
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases). Latest
  still **v0.7.3** (release PR #1646); no new release since.
- **TermSquad — VERIFIED NO-CHANGE**
  (https://termsquad.com/pricing). $9/$19/$29/$49 per month:
  2/4/6/8 vCPU, 4/8/12/24 GB RAM, 40/75/100/200 GB SSD NVMe. Verbatim
  "AI subscriptions and usage are not included." still present.
- **AgentComputer — VERIFIED NO-CHANGE**
  (https://www.agentcomputer.ai/pricing). CPU $0.07/CPU-hour, Memory
  $0.04375/GB-hour, Hot storage $0.000683/GB-hour (running), Cold
  storage $0.000027/GB-hour (stopped). Enterprise = custom.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE** (docs page:
  https://docs.digitalocean.com/products/managed-agents/ — "Last
  verified 21 Sep 2026" still shown; public preview; Latest Updates
  section top entry still 21 September 2026).

## 2. Corpus folds

### 2a. C26 — the docs pricing subpage is LOCATED and read live; the "unlocated" framing is retired (fold)

The morning pass's *\"subpage still unlocated, 8th consecutive miss\"*
line is dead — the 8-miss streak was (INFERRED) a **discovery failure, not an
availability failure**: two search data points (`site:docs.digitalocean.com` queries for the pricing subpage
returned **zero results**; a general web search for the subpage surfaced nothing) alongside a successful direct fetch
of the corpus-carried URL — the page is reachable but effectively undiscoverable via search, which best explains
the whole miss streak. This run's surveyor reached the docs pricing
subpage live at the corpus-carried URL
https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/
(VENDOR-VERIFIED): title "DigitalOcean Harness Runtime Pricing",
stamp still **"Last verified 22 Sep 2026"** (no re-date), and it still
names **$0.05 per GiB-month** under "Snapshots and Checkpoints" (same
$0.05 also on Session Storage / Volumes and Custom Sandbox
Templates / BYOT). Compute rates unchanged: CPU $0.044/vCPU-hour
(active CPU "coming soon"; billed 25% of allocated until then),
memory $0.0095/GB-hour peak.

The discovery angle is diagnosed: `site:docs.digitalocean.com`
queries for the pricing subpage returned **zero results**, and a
general "Harness Runtime pricing docs.digitalocean.com" search
surfaced nothing from the docs subpage either — the page is
**reachable but effectively undiscoverable via search**, which
explains the whole miss streak.

The vendor-internal conflict **stands unchanged on both surfaces**:
the IR launch page re-read live this run (VENDOR-VERIFIED) still
names **$0.005/GiB-month** snapshots in the Sep 22, 2026 press
release — no correction, no new date. So the vendor's own docs
($0.05) and the vendor's own IR launch ($0.005) conflict by 10×
with no correction on either side.

Supporting datum for the misattribution hypothesis (THIRD-PARTY,
digitalocean/navigators-guide PDF): general-product Droplet/Volume
snapshot storage is billed at **$0.05 per gigabyte each month** —
nominal-value-for-value with the docs subpage's $0.05 figure (GB vs GiB units differ) and consistent with the
INFERRED "general-product rate bleeding into the Managed Agents
pricing page" attribution for the docs line vs the
Managed-Agents-specific $0.005 in the IR release. The misattribution hypothesis now has THIRD-PARTY support for the docs-side ($0.05 = general-product rate)
attribution; the $0.005 side remains VENDOR-VERIFIED on the IR launch page.

Conservative handling (per the C32 verification-fold precedent):
the C26 field-table row keeps `$0.05/GiB-month` (pricing-page
figure) with the conflict annotated; the $0.005-as-Managed-Agents
attribution stays INFERRED — but the $0.005 side now sits on a
vendor launch page while the $0.05 side sits on a search-invisible
docs subpage whose figure matches the general-product rate. The
"8th docs-subpage re-fetch" resolving ask is **resolved**; the
standing watch item is the 10× vendor-internal conflict itself.

### 2b. C47 watch color — google/ax (no fold)

Repo re-read live this run (VENDOR-VERIFIED): 10,942 stars (+27 vs
the morning pass), 531 forks (+2), 633 commits (unchanged), head
`e09ed1bc…`, Apache-2.0 unchanged. README quickstart now shows the
default Model example as `gemini-3.8-flash` (VENDOR-VERIFIED —
previously rendered an example without this pin). Still 6
releases / 6 tags in this render; v0.3.0 three-service-split
specifics remain THIRD-PARTY (aiweekly.co, ai-tldr.dev). Already
filed as C47 — watch color only.

## 3. Carried asks

- **C37 — Pro fee still UNVERIFIED (carry).** https://www.freestyle.sh/pricing
  re-read live ~04:35 CDT (VENDOR-VERIFIED): still no Pro dollar
  amount anywhere on the public page. Plan-fee language unchanged
  (monthly fee on paid plans is a commitment that doubles as usage
  credit; FAQ example "$50 on Hobby covers your first $50 of usage"
  — Hobby example only). Usage rates unchanged: $0.04032/vCPU-hr,
  $0.0129/GiB-hr memory, $0.000086/GiB-storage-hr, $0.02/GB data
  transfer; allowances unchanged (200 vCPU-hr, 400 GiB-hr,
  60,000 GiB-storage-hr/month, same on all plans). The page
  structurally does not publish plan fees.
- **C44 — heading still September 24, 2026**
  (https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes,
  VENDOR-VERIFIED). Newest heading: **September 24, 2026** (Gemini
  3.8 Live GA; Muse Spark 1.3 from Meta in Preview). **No September
  25 entry exists** (VERIFIED absent). Sep 22 heading still renders
  with an empty body — no correction posted. Sep-9 Computer Use and
  Shell sandboxes GA entry still present.
- **C41 — pin static** `39b6c3a2` (carried, digits unchanged).
- **C43/C36** — unchanged (the Sep-25 aggregator's "managed agents
  harness + Files/Credentials APIs" item (§4) is already-filed C43
  territory; primary-source verification owed).
- **Tensorlake** — no Sep 24–25 news found (re-opened this run,
  still nothing). The Sep-13 "Cloud Volumes persistent state"
  writeup remains the newest item.

## 4. In-lane news scan — Sep 24–25, 2026

- **Prime Intellect opens Prime Sandboxes to general access**
  (~Sep 23, THIRD-PARTY AlphaSignal) — **in-lane** (managed Linux
  microVM fleet for agent RL rollouts; hardware-virtualized guest
  kernels, explicitly not gVisor; ~30M sandboxes created during the
  private rollout; agents get system access for Docker Compose,
  background services, filesystem modification, long-running tasks;
  GA via CLI, SDK, or Prime's RL stack). **New vs the morning
  pass** — reads as corroborating color for the already-filed
  **C48** launch entry; vendor-primary verification owed before any
  corpus fold.
- **Google Gemini API managed-agents update + Files/Credentials
  APIs** (Sep 25, THIRD-PARTY aiagentstore.ai weekly digest) —
  **in-lane-adjacent**: new `antigravity-preview-09-2026` harness in
  AI Studio/Interactions API on Gemini 3.8 Flash, plus Files and
  Credentials APIs for moving data in/out of an agent sandbox and
  calling GitHub/Slack without exposing tokens to the model.
  Aggregator-reported; primary-source (Google blog/docs)
  verification owed. Substantially already-filed C43 territory —
  no new C-number this pass.
- **Akamai $11.6B multi-year cloud commitment with Anthropic**
  (Sep 24, THIRD-PARTY GlobeNewswire press release) — **adjacent**
  (AI infra capacity demand; Akamai issued ~5% equity warrant).
  Flag only.
- **Baselayer $35M Series A (M13-led)** for "Know Your Agent"
  identity infra for agentic commerce (THIRD-PARTY cvj.ai) —
  **adjacent** (identity/trust layer, not execution). Flag only.
- **webAI $30M Forge strategic deal** (Sep 24, THIRD-PARTY PR
  Newswire via Morningstar) — **adjacent** (enterprise AI services
  deployment). Flag only.
- **Island $400M Series F / Ando $20M** (Sep 24) — **adjacent**,
  already in corpus from the morning pass; no new facts.
- **Out of lane** (not counted): Unryo agentic RAN/K8s (Sep 25,
  EINPresswire — network observability), Axya $12M Series A (Sep
  24, PYMNTS — AI procurement/manufacturing).

**Net:** no pricing moves, no in-lane launches beyond last pass's
already-filed items; the one material new fact is the C26
discovery-resolution (fold §2a).

## Resolving asks for the next pass

- C26: the vendor-internal 10× conflict ($0.005 IR vs $0.05 docs)
  stands unresolved on both vendor surfaces; re-check both stamps
  for any correction or re-date. Scope the conflict's blast radius:
  cross-check the IR launch page's *other* rate lines (compute
  $0.044/vCPU-hour, memory $0.0095/GB-hour) against the docs subpage
  — is the 10× disagreement snapshots-only or broader?
- Prime Sandboxes (C48): vendor-primary (primeintellect.ai)
  verification of general access owed.
- C37: stays carried (page structurally omits plan fees — a
  periodic re-read, not a hard ask).
- Vercel Drives: not re-checked (P49 once-daily morning cadence —
  next check the 2026-09-26 morning pass).
