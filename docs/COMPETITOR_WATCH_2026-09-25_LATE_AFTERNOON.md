# Competitor watch — 2026-09-25 (late afternoon)

Delta-only update against the 2026-09-25 mid-afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-25_MID_AFTERNOON.md`). Survey window
**2026-09-25 ~14:28–14:40 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set + C44 heading check (14:28–14:40); (B) an
open-web in-lane news scan dated 2026-09-25 (14:29–14:40). Vercel
Drives NOT re-checked this pass (P49 once-daily morning cadence —
next the 2026-09-26 morning pass). Surveyor captures live in the
loop's `agent_notes/` workspace (`surveyor-a-20260925-1424.md`,
`surveyor-b-20260925-1424.md`), not the repo. `_LATE_AFTERNOON` is
collision-free on origin/main's watch-doc list for this date
(MORNING/MID_MORNING/LATE_MORNING/MIDDAY/POST_MID_MORNING/AFTERNOON/
EVENING/NIGHT/POST_NIGHT/EARLY_AFTERNOON/MID_AFTERNOON taken —
precedent family: the 2026-09-23/24 `_LATE_AFTERNOON` passes).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **snippet-level** = seen only
via search snippet. **UNVERIFIED** = a public page exists but could
not be fetched this run (never reported as NO-CHANGE). **VERIFIED
absent** = the vendor's own page was read this run and the item is
confirmed not present on it.

## 1. The tracked set — 7/8 VERIFIED NO-CHANGE, one DELTA (Docker Sandboxes)

Zero pricing/feature deltas across the set except the Docker
release-notes heading move below. **Zero fetch failures** this pass —
all 11 vendor fetches succeeded first try (Surveyor A, no retries).

- **Daytona — VERIFIED NO-CHANGE** (changelog:
  https://www.daytona.io/changelog; pricing:
  https://www.daytona.io/pricing). Newest changelog entries still the
  SEP 24 2026 pair (V0.216.1 "API key organization ID and CLI update
  warning fix"; V0.216.2 "CLI login through WorkOS"); no September 25
  entry. Pricing watched lines verbatim, unchanged (compute $0.0504/h
  per vCPU, memory $0.0162/h per GiB, storage $0.000108/h per GiB;
  GPU preemptible ladder; Windows $0.0858/vCPU/h; "$200 in free
  compute included"; "All billing is calculated per second.").
- **Docker Sandboxes — VERIFIED DELTA** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/, full-page
  read, 444 lines). Newest dated heading is now **`*2026-09-22*`**
  (was `*2026-09-21*` at the ~13:15 pass). New entry, verbatim:

  > *2026-09-22*
  > [GitHub release →
  > https://github.com/docker/sbx-releases/releases/tag/v0.45.1]
  > - Improved sandbox moves and support for private kit images in
  >   cloud sandboxes.

  The linked GitHub release is **VENDOR-VERIFIED** (read this run):
  "Release v0.45.1 · docker/sbx-releases", marked `Latest`,
  released by `docker-read-write` **22 Sep 18:28**, commit
  `cf6fa41`, body "Fixes and improvements — Improved sandbox moves
  and support for private kit images in cloud sandboxes." Remaining
  dated headings unchanged (`*2026-09-21*` v3-kits entry verbatim,
  incl. "Cloud support is experimental and requires an active Docker
  Agentic Platform subscription"; `*2026-09-15*`; two
  `*2026-09-07*` entries). Case-insensitive find for "Cloud
  Sandboxes" on the full page now returns **2 hits** (was 0 at the
  ~13:15 pass — VERIFIED absent then): the new v0.45.1 bullet
  ("private kit images in **cloud sandboxes**") and the 2026-09-21
  entry's link text ("Get started with **cloud sandboxes**"). The
  exact-case proper name `Cloud Sandboxes` appears nowhere — the
  Sep-24 launch still has **no distinct launch note** on this docs
  page; it is referenced only incidentally via the v0.45.1 changelog
  bullet (which predates the launch).
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby FREE
  + "$100 one-time usage credit"; Pro $150/month; per-second ladder
  1 vCPU = $0.000014/s through 8 vCPU = $0.000112/s — all watched
  lines verbatim.
- **boat.dev — VERIFIED NO-CHANGE** (https://docs.boat.dev/pricing).
  Sizes $0.018 / $0.036 / $0.072 / $0.200 per hour; plans
  $20/$100/$500/$2000 per month; Trial "25 free hours, 2 sandboxes
  at once"; "You pay for machine time, per second, only while a
  sandbox runs. A stopped sandbox costs nothing." Comparison table
  unchanged.
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases).
  Latest release still v0.7.3 ("chore: release v0.7.3 by
  @toksdotdev in #1646").
- **TermSquad — VERIFIED NO-CHANGE**
  (https://termsquad.com/pricing). Tiers Starter $9 / Builder $19 /
  Power $29 / Ultra $49 USD per month; "AI subscriptions and usage
  are not included."
- **AgentComputer — VERIFIED NO-CHANGE**
  (https://www.agentcomputer.ai/pricing). CPU Time $0.07 per
  CPU-hour; Memory $0.04375 per GB-hour; Hot Storage $0.000683 per
  GB-hour (running); Cold Storage $0.000027 per GB-hour (stopped).
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE**
  (https://docs.digitalocean.com/products/managed-agents/; pricing
  subpage
  https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/).
  Stamps still "Last verified 21 Sep 2026" and "Last verified 22 Sep
  2026". Watched lines unchanged: CPU "$0.044 per vCPU-hour",
  Memory "$0.0095 per GB-hour", egress $0.01/GiB; footnote "*Active
  CPU billing is coming soon. Until then, you will be billed at 25%
  of the vCPUs allocated to your sandbox.*"

**C44 check — VERIFIED NO-CHANGE (separate from the tracked set):**
Google Gemini Enterprise Agent Platform release notes
(https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
newest heading still **September 24, 2026** (verbatim content:
Gemini 3.8 Live GA; Muse Spark 1.3 Preview); no September 25, 2026
heading exists. C44 (Computer Use and Shell sandboxes GA) still
under September 09, 2026, wording unchanged.

## 2. In-lane moves — corpus folds: C55 grade upgrade; no new C-numbers

### Corpus fold — C55 evidence upgrade: THIRD-PARTY → VENDOR-VERIFIED

The carried primary-source ask is **RESOLVED**: Cloudflare's own
disclosure post was read in full this run —
https://blog.cloudflare.com/containers-cross-tenant-vulnerability/
("How Cloudflare addressed a cross-tenant data exposure
vulnerability in Containers"), **VENDOR-VERIFIED** (full-page read on
blog.cloudflare.com, all 162 lines).

Vendor-exact facts (from the vendor page, not third-party framing):
- "On September 4, 2026, Oren Yomtov, a security researcher from
  Accomplish, responsibly reported a vulnerability affecting
  Cloudflare Containers and Cloudflare Sandboxes (which is built on
  Containers), through Cloudflare's bug bounty program."
- Root cause: Linux device-mapper thin provisioning (dm-thin) for
  writable root disks; each container in a dedicated Firecracker VM,
  disk presented as `/dev/vdc`. Affected pools used a 64 KiB
  thin-block size plus the pool option `skip_block_zeroing` — "With
  this option configured, dm-thin skips zeroing newly allocated
  blocks before making them accessible."
- Vendor validation across six production placements: 5,614 testable
  directory blocks, 2,700 distinct foreign directory inodes;
  residual material on 18 of 24 placements and 20 of 22 underlying
  nodes across four continents; recovered block types: "directory
  structures, database pages, and structurally complete SQLite
  databases."
- Impact (vendor): "would potentially have allowed for a customer
  with a Workers Paid account to recover residual data from storage
  blocks previously used by other customers' Containers on the same
  underlying host." Attacker "could not select a particular victim
  or access an actively attached disk."
- Timeline (vendor, verbatim): Sep 4 15:26 UTC report via HackerOne;
  18:45 UTC incident opened; 21:27 UTC runtime fix merged; 22:03 UTC
  new/live pool changes merged; 23:15 UTC rollout started; Sep 7
  06:13 UTC rollout complete + old-pool data clearing began; Sep 14
  researchers confirmed the PoC stopped; **Sep 19 15:03 UTC cleanup
  of all pre-mitigation cached snapshots completed.** "We identified
  no evidence of malicious exploitation." No customer-side
  configuration changes required.
- Clarification vs third-party framing: this is a **storage-layer
  cross-tenant residual-data exposure, not a VM/container escape**
  in the code-execution sense. "Cloudflare Sandboxes" is confirmed
  affected (built on Containers); the vendor notes Browser
  Rendering's Browser Run service ran on the same disk
  implementation.

No new C-number: C55 already exists as the corpus disclosure entry;
this pass upgrades its evidence grade and adds the vendor-exact
timeline + numbers. The threat-model relevance stands (and
sharpens): multi-tenant disk-wipe discipline — the exact failure
mode the C55 filing warned about is now vendor-confirmed as a
fleet-wide default.

### Carried — C54 full article-body read: BLOCKED, not read this run

- `browser.open` on
  https://www.perplexity.ai/hub/blog/escaping-space-part-i →
  **HTTP 403** (upstream bot-block), single attempt per runtime
  instruction. No article-body content is reported — nothing was
  read this run.
- The page's headline/date/author metadata were already
  real-browser-verified by the 13:54 pass (headline "Escaping SPACE:
  Part I", subtitle "Red-teaming VM isolation and network
  confinement for AI agents", date SEP 23, 2026, author Perplexity
  Secure Intelligence Institute). Dated Sep 23 — outside today's
  window regardless. Full-body read stays carried for a future
  pass.

### Adjacent color only (NOT corpus) — Kontext Security public launch + $4M seed

- THIRD-PARTY (SecurityWeek, tech.eu, undercodenews — snippet-level
  and full snippets): "Kontext Security today launched publicly with
  $4 million raised in a funding round led by 42CAP, with additional
  support from a16z CSX and HTGF." Munich; co-founded by Jens
  Ernstberger (CEO) and Michel Osswald. "Deployed between the AI
  agents and the systems and tools they access, Kontext's runtime
  enforcement platform evaluates the agents in real time against
  security policies and risks." Dated **September 24, 2026**.
- NOT a C-number: fundraise + public launch of an agent
  **runtime-control/security** startup — not a sandbox/runtime/VM
  provider per se (observes/enforces between agents and tools).
  Precedent: Island $400M Series F filed below the C-number bar as
  fundraise-only. Adjacent color (threat-model adjacent:
  in-environment policy enforcement). Dated Sep 24 — outside
  today's window.

### Dedupe — third-party recaps of corpus-covered items: no new facts

- Docker Cloud Sandboxes recaps — how2shout.com pricing table
  (Micro 1 vCPU/2 GiB $0.07 … XL 16 vCPU/32 GiB $1.12, per-second,
  paused = free, $250 free credit, 1h default / 24h max) and The
  Register + rozeepk reprint + WebProNews — recaps/commentary on
  **C45** + **C52**, no new product facts.
- explainx.ai DigitalOcean Managed Agents launch writeup (launch
  dated September 23, 2026, "~16,000 pre-built tools") — third-party
  commentary; DO Managed Agents already in the tracked set; launch
  outside window.

### Searched, nothing in-lane surfaced

- Daytona changelog/release, E2B launch/update, Modal/Runloop/
  Northflank launch/pricing, Vercel Sandbox announcement,
  Microsandbox/TermSquad/AgentComputer/Firecrawl launch-pricing —
  all dated Sep 25: no results (search noise only). Vercel Drives
  stays on the P49 once-daily morning cadence.

### Deliberately not filed

- techmaniacs.com Sep-25 cyber briefing defensive-action line
  ("Review Cloudflare and similar IaaS environments for evidence of
  cross-tenant data persistence") — defensive-action line referencing
  the C55 disclosure; no new facts.
- CVE-2026-26956 vm2 sandbox escape (Node.js 25): third-party PDF
  writeup via obstracts, undated/crawled ~106 days ago; js-library
  sandbox escape, marginal lane fit, no Sep-25 date — not filed.
- Modern Treasury / Robocorp pingoru incident pages dated Sep 25:
  unrelated products (payments SaaS sandbox-environment incident,
  not agent-VM infra) — not filed.

**Carried:** C54 full article-body read (Perplexity "Escaping
SPACE" — automated fetches 403, real-browser verified live
2026-09-25 ~14:10 CDT); C37 Pro fee still structurally omitted
(watched lines); C44 newest heading still Sep 24 (no Sep-25 entry —
VERIFIED absent); C26 conflicts unchanged (watched lines); Vercel
Drives NOT re-checked (P49 once-daily morning cadence — next the
2026-09-26 morning pass).

**In-lane no-launch verdict dated 2026-09-25:** no new
sandbox/runtime launches or pricing changes dated 2026-09-25
surfaced in this pass. The in-lane dated items were the C55
vendor-primary read (Sep-4 disclosure, blog published ~Sep 24–25)
and third-party recaps of corpus-covered C45/C52.
