# Competitor watch — evening pass, 2026-09-22

Delta-only update against the afternoon baseline
(`docs/COMPETITOR_WATCH_2026-09-22_AFTERNOON.md`). Survey window
**2026-09-22 ~16:10 → ~18:00 CDT**; two read-only surveyors
(read-only fetches and searches; no logins, no writes): (A) vendor-page
re-reads of the tracked set (reads ~17:55–17:58 CDT), (B) open-web
market-news scan (~16:00–18:00 CDT).

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **THIRD-PARTY** = reported by press/third-party
sources. **INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.

## 1. DigitalOcean Managed Agents — product page unlocked (C26 continuation, VERIFIED)

The product page (https://www.digitalocean.com/products/managed-agents)
fetched cleanly first try this pass (it failed twice in the afternoon
pass) — the C26 continuation is resolved. New mechanism nouns beyond
the launch blog:

- **Tool Playground:** "Tool Playground for testing configurations,
  permissions, and policies before production" — a pre-production
  policy-testing UX, not named in the blog. Competitive input for #47
  (filed this turn).
- **Scheduled and webhook triggers** for automated runs — triggers shape
  the page names but the blog's mechanism summary did not.
- Credential brokering phrasing adds a third party: "tokens resolve at
  execution time and never reach the model, the agent prompt, or the
  sandbox" (blog: "never reach the model or the sandbox"; M.A.R.S. note:
  "neither the model nor the execution environment").
- "Checkpoint a session and fork a new, independent session from it" —
  matches the blog.
- Active-CPU line: "CPU billing follows actual consumption per second,
  so an idle agent's charge falls to zero instead of paying for allocated
  capacity."
- Per-session access controls; subagent/map-reduce parallel sessions;
  16,000+ tools / 500+ providers.

**VERIFIED** (DO product docs, all read this pass; indexes "Generated on
22 Sep 2026"):

- https://docs.digitalocean.com/products/managed-agents/ — architecture
  note: tool calls pass between Harness Runtime and Action Gateway, both
  emit events to Signals; also connects outward to Inference Engine,
  Storage, and Data services. Sept 21 public-preview + BYOT release
  notes entry confirmed.
- https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/
  — concept index names **runs** as a distinct entity and **adapters**
  (harness adapters) as a concept.
- https://docs.digitalocean.com/products/managed-agents/action-gateway/
  — concept index names **actors** (authorization actor model) and
  **toolbelts** (curated tool packages — likely the packaging name for
  the "session-management APIs packaged as skills per supported harness"
  the blog described). Actors/toolbelts are recorded for H16 in
  `docs/ORG_POLICY_RESEARCH.md` §2 (vendor-sourced, promote to full
  entry on controls-level docs).

No contradictions found between the blog and the docs — the afternoon
doc's "re-read the launch blog against the shipped docs" ask is
satisfied.

## 2. Vendor-claim tension: DO's marketing numbers vs its own benchmark

The product page says "Sessions go from creation to a first response in
**under a couple of seconds**, and resume paused work in **about 200
milliseconds**." The vendor's own self-published benchmark (Sept 21,
internal, p50) says create→ready **886 ms**, first response **3.3 s**,
resume **305 ms**; the morning press release also claims 305 ms. Both
are vendor claims; the marketing page is faster than the measured
numbers. The corpus (C14's "305 ms bar", C27's filed benchmark input)
should carry the footnote: **~200 ms is the aspirational marketing
figure; 305 ms is the measured p50.** Anyone citing the benchmark must
cite the benchmark, not the landing page.

## 3. Fly.io Sprites lifecycle figures — VERIFIED for the first time

**VERIFIED** (https://docs.sprites.dev/concepts/lifecycle/, read this
pass — vendor's own docs):

- "When the activity stops, a short idle window passes (**about 30
  seconds** today) and the Sprite pauses."
- Warm: "The VM is suspended with everything in memory frozen in place.
  Compute billing stops. The next request resumes it in **100–500ms**,
  and processes pick up mid-thought, exactly where they were."
- Cold: "If the Sprite stays idle long enough, the VM is fully stopped
  and in-memory state is dropped. The next wake takes **1–2s** and starts
  processes fresh."
- "**Open TCP connections do not survive a pause**, warm or cold."
- Memory is autoscaled ("not a fixed number to design around"); each
  Sprite has 8 vCPUs and 100 GB storage (fixed); storage is
  TRIM-friendly ("you pay for the bytes you actually write").

Two readings for the corpus: (a) these are now vendor-verified figures
for the C14 resume-latency discussion (Sprites warm wake 100–500 ms,
cold wake 1–2 s) — DO's 305 ms resume claim is competitive against
Sprites' *warm* wake but the comparison is apples-to-oranges (DO resume
preserves the session; Sprites' warm wake is a memory-resume with
dropped TCP state); (b) a caveat for C27: the blog's "exec round trip
189 ms vs Fly.io Sprites 79 ms" names a figure that **Sprites' own docs
do not publish** — no exec-RTT figure exists on docs.sprites.dev — so
the 79 ms leg is unexplained vendor methodology, not a Sprites vendor
claim. Filed context, not a benchmark correction.

## 4. The tracked set — quiet (surveyor A, VERIFIED re-reads ~17:55–17:58 CDT)

No in-window change across the tracked set:

- **Microsandbox** — top release still v0.7.1.
- **Docker Sandboxes** — release notes still top at the 2026-09-15
  block; no 0.44.
- **Daytona** — changelog still tops at SEP 22 2026 / v0.215.0 ("Integer
  API client types and CLI MCP allowlist fixes").
- **E2B** — pricing unchanged (Hobby free + $100 one-time credit, Pro
  $150/mo, per-second table $0.000014/s per vCPU, Enterprise $3,000/mo
  floor).
- **boat.dev** — pricing unchanged ($0.018/$0.036/$0.072/$0.200 per
  hour; trial 25 free hours; comparison table intact).
- **TermSquad** — tiers unchanged ($9/$19/$29/$49); BYO-AI FAQ stance
  unchanged.
- **AgentComputer** — pricing unchanged ($0.07/CPU-hr, $0.04375/GB-hr,
  hot/cold storage). **C12 stands** — still no stated egress policy.
- **Vercel Sandbox** — no in-window vendor changes found (pre-window:
  Sept 17 Harbor-evals changelog entry, Sept 14 SDK v0.5.2, sandbox
  4.4.0).
- **Cloudflare Sandbox** — sandbox-sdk CHANGELOG shows pre-window
  patches only (0.8.2–0.8.4).
- **WSO2/badsignal.ai, M.A.R.S., diggerhq/opencomputer,
  BrowserSkill/Tencent, Vercel Herdr** — outside the afternoon tracked
  set; not re-read this pass. No in-window signals.

## 5. Market news — one-sided benchmark war stands; hands-on coverage still absent

- **Independent hands-on coverage of DO Managed Agents: still absent**
  (confirmed by fresh search). All third-party coverage found is verbatim
  Business Wire syndication plus one TradingView item with an AI-analyst
  disclaimer explicitly summarizing the release. DO's 189 ms-vs-79 ms
  Sprites admission still has no third-party check, and **no Fly response
  to the benchmark naming was found**.
- **No in-window outages** in the sandbox lane (search hits were stale
  or pre-window).
- **No in-window Vercel / Cloudflare / Fly sandbox announcements.**

## 6. Pre-window color, new to the baseline

- **Boxd — $2M pre-seed, new sandbox-infrastructure competitor.**
  THIRD-PARTY (runtimewire.com, 6ic.com, todaysstartupnews — announced
  ~Sept 16; BlueYard Capital lead; OVNI, Antler, S20, Script Capital +
  angels). Product shape (vendor claims, third-party-reported):
  hardware-isolated KVM VMs with dedicated kernels, a stripped
  virtualization engine (CPU/mem/storage/net only, no peripheral
  emulation), **live-fork of a running VM including memory + active
  connections in <100ms**, snapshots, SSH-in for humans, Raft-coordinated
  control plane, "each VM as its own OS process" for supervisor-fault
  survival. Thesis: "every AI coding agent needs a real computer rather
  than a disposable sandbox"; neutral machine layer not owned by a model
  provider. Why it matters: fork-a-VM semantics directly overlap DO
  Harness Runtime's pause/resume/fork and spark-vm's #179 lifecycle +
  #47 branching control plane — a funded, KVM-native competitor in the
  persistent-machine-for-agents lane. Watch, don't react: pre-seed, and
  the speed claims are vendor numbers. Filed as **C29** (watch-level).
- **OpenAI Agents API partner list names DigitalOcean + eight others.**
  THIRD-PARTY (archived OpenAI announcement, third-party repo:
  https://github.com/steel-experiments/internal-agents-map/blob/HEAD/archive/sources/openai-agents-api-post/content.md;
  public beta Sept 10): nine sandbox ecosystem partners with first-class
  integrations — Blaxel, Cloudflare, Daytona, **DigitalOcean**, E2B,
  Modal, Oracle, Runloop, Vercel. Why it matters: (a) DO is an
  OpenAI-endorsed sandbox provider — first-party validation of DO's
  sandbox stack from the harness side, sharpens C26; (b) the architecture
  formalizes the **harness↔compute split** (OpenAI owns the agent loop;
  sandbox is pluggable compute) — directly relevant to spark-vm's
  hosted-product design: the hosted product competes on the
  compute/execution layer while harness choice is BYO. Corroborates the
  "open alternative" positioning against both E2B/Daytona and DO. Filed
  as **C30**.
- **Upstash "Box" — snapshot/restore sandbox entering the corpus's
  vendor set.** Vendor docs (launch date not established — not a corpus
  timing claim):
  https://github.com/upstash/docs/blob/HEAD/box/overall/how-it-works.mdx
  — snapshot/restore API for reusable prepared environments, branching
  from snapshots, full outbound networking by default, 22.5 Gbps hosts,
  on AWS; pause/resume not available when keepAlive enabled. A
  Redis-adjacent vendor now in the sandbox lane. Filed as **C31**
  (watch-level).
- **Vercel Sandbox default storage 32 GB → 64 GB** — THIRD-PARTY
  (ai-cost-estimator cost-analysis blog, ~Sept 14): newly-created
  sandbox defaults doubled; the blog reads it as workspace-cost
  repricing, not capability gain. **Not a corpus entry yet**: needs
  vendor verification — suggested surveyor-A check against
  vercel.com/changelog on the next vendor-page pass.

## 7. Open threads / inputs filed

- **C29 (NEW, competitor — watch):** Boxd $2M pre-seed — funded KVM-native
  persistent-machine competitor, fork semantics overlap #179/#47. Watch,
  no reaction; revisit when there is a measurable product.
- **C30 (NEW, competitor → hosted design):** OpenAI Agents API formalizes
  the harness↔compute split with nine first-class sandbox partners —
  input to the hosted product's compute-layer positioning; DO's presence
  sharpens C26.
- **C31 (NEW, competitor — watch):** Upstash "Box" snapshot/restore
  sandbox joins the tracked set; vendor-docs-sourced, timing unverified.
- **C27 context (competitor → #47):** product-page tension filed in the
  C27 story (marketing ~200 ms vs measured 305 ms resume) and the
  Sprites-79-ms methodology caveat (no exec-RTT figure on
  docs.sprites.dev).
- **C14 (#47 resume-latency target):** still OPEN (needs our own measured
  provider baseline — the user's per-run Fly spend-cap decision is still
  owed). Sharpened context: Sprites vendor-verified warm wake 100–500 ms
  / cold wake 1–2 s with dropped TCP state; DO's ~200 ms is aspirational
  marketing, 305 ms is measured p50.
- **C26 (DO watch):** product page now readable; blog-vs-docs
  cross-check satisfied (no contradictions). Watch continues at routine
  cadence.
- **C12, C10:** stand, unchanged.

## 8. Method note

Short windows (~1.8 h) still pay: the day's signal was the DO product
page flipping from UNVERIFIABLE to VERIFIED plus two vendor-doc sets
(Sprites lifecycle, DO docs index). The product-page delta was the
afternoon pass's one retry-failure; two-retry failures should be
re-attempted on the next pass rather than carried as standing
UNVERIFIABLE.
