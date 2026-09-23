# Competitor watch — late-evening pass, 2026-09-22

Delta-only update against the evening baseline
(`docs/COMPETITOR_WATCH_2026-09-22_EVENING.md`). Survey window
**2026-09-22 ~18:00 → ~20:10 CDT**; two read-only surveyors
(read-only fetches and searches; no logins, no writes): (A) vendor-page
re-reads of the tracked set (reads ~20:00–20:02 CDT), (B) open-web
market-news scan (~20:00–20:10 CDT) plus the C29 vendor-presence job.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **THIRD-PARTY** = reported by press/third-party
sources. **INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.

## 1. The tracked set — quiet since the evening baseline (8/8 NO-CHANGE, all VERIFIED)

- **Microsandbox** — top release still **v0.7.1** (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~20:00).
- **Daytona** — changelog top entry **SEP 22 2026 / v0.215.0**
  ("Integer API client types and CLI MCP allowlist fixes"); the evening
  doc already recorded this entry at ~17:55 — **not an in-window change**
  (**VERIFIED**: https://www.daytona.io/changelog, ~20:00).
- **E2B** — pricing unchanged: Hobby free + $100 one-time credit,
  Pro $150/mo, Enterprise custom ($3,000/mo minimum); per-second table
  tops $0.000014/s per vCPU (**VERIFIED**: https://e2b.dev/pricing,
  ~20:00).
- **boat.dev** — rate card unchanged: small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h**; stopped free;
  25 free-hour trial (**VERIFIED**: https://docs.boat.dev/pricing,
  ~20:01).
- **Docker Sandboxes** — release notes still top out at **2026-09-15**;
  no 0.44 (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~20:01).
- **TermSquad** — tiers still $9/$19/$29/$49; BYO-AI stance unchanged
  (**VERIFIED**: https://termsquad.com/, ~20:01).
- **DigitalOcean Managed Agents** — product page unchanged (Public
  Preview; Tool Playground, scheduled/webhook triggers, Firecracker
  microVM per session, credential brokering phrasing intact; hero claims
  "under a couple of seconds" / "about 200 milliseconds" unchanged);
  docs index "Last verified 21 Sep 2026", Latest Updates still the
  Sept 21 public-preview entry (**VERIFIED**:
  https://www.digitalocean.com/products/managed-agents and
  https://docs.digitalocean.com/products/managed-agents/, ~20:02).
- **AgentComputer** — pricing unchanged (CPU $0.07/CPU-hour, memory
  $0.04375/GB-hour, hot storage $0.000683/GB-hour, cold
  $0.000027/GB-hour); still **no stated egress policy** — C12 stands
  (**VERIFIED**: https://www.agentcomputer.ai/pricing, ~20:02).

Market-news scan (B, ~20:00–20:10): **zero in-window deltas** — no
launches, pricing changes, funding, releases, or partner moves. Only
verbatim Business Wire syndication of the Sept 21 DO announcement
(pre-window, THIRD-PARTY). No in-window WSO2 pre-webinar news (Sept 29
date unchanged); no new DO hands-on coverage; no Fly response to the DO
benchmark naming; the OpenAI Agents API partner list reconfirms the
same nine partners (Blaxel, Cloudflare, Daytona, DigitalOcean, E2B,
Modal, Oracle, Runloop, Vercel — pre-window; tencentcloud/cubesandbox
docs show E2B-compatible API emulation, THIRD-PARTY, pre-window color).

## 2. Boxd — C29 promoted from third-party-only to vendor-verified (the one real delta)

Boxd has a vendor-owned presence (found via the press site list, read
this pass): homepage https://boxd.sh and docs
https://docs.boxd.sh/quickstart (both **VERIFIED** ~20:03–20:06 CDT).
SDK install surface cited third-party only (PyPI shows vendor-published
`boxd` 0.2.9.dev466; `boxd.sh/downloads/install.sh` seen only
third-party — **not VERIFIED** on vendor pages).

Vendor-verified facts (**VERIFIED**, vendor's own pages):

- Product: "Composable computers" — persistent KVM VMs; default
  **2 vCPU / 8 GB RAM / 100 GB disk**, Ubuntu 24.04; real SSH
  (scp/rsync/Remote-SSH); each machine gets an HTTPS subdomain
  (`<name>.boxd.sh`).
- **Fork:** "Live memory forking of machines, **in under 200 ms**" —
  disk + memory + every running process (nginx on the parent "already
  serving on the fork's URL"); copy-on-write semantics.
- **Snapshots:** freeze and restore a machine "down to the running
  processes" (`boxd snapshots save alice`); **checkpoints** = in-place
  rollback of the same machine (memory + disk restored in place).
- **Pricing** (vendor FAQ): credit-based — **€0.049/vCPU-hour** while
  running; **€0.015/GiB-hour of resident RAM** while running or in
  standby; **€0.0001/GiB-hour of disk actually written**; hibernated
  machines pay disk only; **€30 free credits** for new accounts.
- Idle machines "suspend to disk, **resume in under a millisecond** on
  next connection" (vendor marketing-page figure — no methodology
  published; do NOT cite as a benchmark — C14 input discipline).
- **Self-hosted:** "Run the whole platform on your own hardware."
- MCP server installs into Claude Code, Codex, or opencode;
  integrations for GitHub/Linear/Slack; org env vars/secrets. CLI +
  TypeScript/Python SDKs + API (`boxd m new`); sign-in via
  app.boxd.sh (GitHub or Google).

**Corrections to the evening watch's C29 (now VERIFIED against vendor
sources):**

- Fork speed: vendor says **under 200 ms**, not the press's <100 ms
  headline. The <100 ms figure stays THIRD-PARTY/UNVERIFIED against
  vendor sources.
- **Active-network-connections forking is NOT vendor-attested** — the
  vendor pages say fork carries "every running process"; the press
  claim of forking active connections in <100 ms is not repeated by
  the vendor. The Sprites tension noted in the evening doc
  ("Open TCP connections do not survive a pause") stands as the
  documented behavior on the other side; Boxd's actual claim is
  smaller than the press headline, which weakens the claimed
  contradiction without resolving it.

**Corpus effects:** C29 changes status from "watch, third-party-only"
to **vendor-verified competitor**. The fork-resume mechanism detail
(featherweight: CoW fork of a live machine with running processes in
~200 ms, sub-millisecond idle resume *claim*) sharpens the C14
resume-latency context: the measured figures stay vendor-published
only (Sprites warm 100–500 ms, DO 305 ms p50); Boxd's figures are
marketing-page with no methodology — directionally interesting,
not citable. No spark-vm design change: watch, don't react.

## 3. Standing items / carry-forwards

- **C14 (#47 resume-latency target):** still OPEN — needs our own
  measured provider baseline; the operator per-run Fly spend-cap
  decision is still owed (NEEDS_USER.md). New context this pass: Boxd's
  "under a millisecond" idle-resume is a marketing-page figure with no
  published methodology — not a benchmark input.
- **C29:** vendor-verified (this pass); watch continues at routine
  cadence.
- **C30:** harness↔compute split corroborated (same nine partners;
  pre-window, THIRD-PARTY) — no new datapoint.
- **C31:** no new datapoint this pass.
- **C26 (DO watch):** quiet this pass; product page unchanged.
- **C12, C10:** stand, unchanged.
- **Next pass's ask:** the evening pass's suggested check — verify the
  Vercel Sandbox default-storage 32→64 GB claim against
  vercel.com/changelog (THIRD-PARTY blog claim, never vendor-checked).
  Not covered by either surveyor this pass; keep it on the next
  vendor-page survey.

---

*Corpus note:* per the reach-back policy this pass is delta-only; no
corpus record changed except C29's status promotion above (the C29
vendor-verified detail lives here; the canonical competitor entry, if
any, gets it on the next consolidation pass). The two surveyor captures
are archived verbatim in the loop's `agent_notes/` (workspace-only),
not the repo.
