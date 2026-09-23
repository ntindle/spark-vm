# Competitor watch — overnight pass, 2026-09-22 → 2026-09-23

Delta-only update against the late-evening baseline
(`docs/COMPETITOR_WATCH_2026-09-22_LATE_EVENING.md`). Survey window
**2026-09-22 ~20:10 → 2026-09-23 ~00:10 CDT**; two read-only surveyors
(read-only fetches and searches; no logins, no writes): (A) vendor-page
re-reads of the tracked set (reads ~00:00–00:10 CDT), (B) open-web
market-news scan (~23:55–00:10 CDT) plus the C29 SDK-URL verification job.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **THIRD-PARTY** = reported by press/third-party
sources. **INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.

## 1. The tracked set — quiet since the late-evening baseline (8/8 NO-CHANGE, all VERIFIED)

- **Microsandbox** — top release still **v0.7.1** (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~00:00).
- **Daytona** — changelog top entry still **SEP 22 2026 / v0.215.0**
  ("Integer API client types and CLI MCP allowlist fixes")
  (**VERIFIED**: https://www.daytona.io/changelog, ~00:00).
- **E2B** — pricing unchanged: Hobby free + $100 one-time credit, Pro
  $150/mo, Enterprise custom ($3,000/mo minimum estimator floor);
  per-second table tops $0.000014/s per vCPU (**VERIFIED**:
  https://e2b.dev/pricing, ~00:02).
- **boat.dev** — rate card unchanged: small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h**; stopped free;
  25 free-hour trial (**VERIFIED**: https://docs.boat.dev/pricing,
  ~00:02).
- **Docker Sandboxes** — release notes still top out at **2026-09-15**;
  no 0.44 (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~00:04).
- **TermSquad** — tiers still **$9/$19/$29/$49**; BYO-AI stance intact
  (page marketing refreshed with Squad-orchestration framing;
  pricing/stance unchanged) (**VERIFIED**: https://termsquad.com/,
  ~00:04).
- **DigitalOcean Managed Agents** — product page unchanged (Public
  Preview; hero "under a couple of seconds" / "about 200 milliseconds";
  Tool Playground, scheduled/webhook triggers); docs index still
  "Last verified 21 Sep 2026", Latest Updates = Sept 21 public-preview
  entry (**VERIFIED**:
  https://www.digitalocean.com/products/managed-agents and
  https://docs.digitalocean.com/products/managed-agents/, ~00:06).
- **AgentComputer** — pricing unchanged (CPU $0.07/CPU-hour, memory
  $0.04375/GB-hour, hot storage $0.000683/GB-hour, cold
  $0.000027/GB-hour); still **no stated egress policy** — C12 stands
  (**VERIFIED**: https://www.agentcomputer.ai/pricing, ~00:06).

## 2. Deltas — one verification closed, one new vendor feature, one borderline third-party note

### 2a. C29: Boxd SDK install URL — VENDOR-ATTESTED (verification closed)

`https://boxd.sh/downloads/install.sh` is vendor-attested: fetched
directly from boxd.sh this run (~00:04 CDT) — HTTP 200, a genuine
532-line POSIX shell installer (`# boxd CLI installer`, `set -eu`,
platform detection, sha256-verified binary download via manifest,
installs CLI + Claude Code/Codex/OpenCode skills, PATH and shell
completions). The script's own usage header declares the canonical
path as `https://boxd.sh/downloads/cli/install.sh` (`BASE_URL="https://boxd.sh/downloads/cli"`);
that variant was fetched too (~00:07 CDT) — byte-identical script, so
both paths serve the same genuine installer. This closes the last
unverified item on the C29 entry: the SDK install surface is now fully
vendor-sourced (quickstart's CLI-first onboarding +
`docs.boxd.sh/quickstart` TypeScript/Python SDK docs, re-verified
~00:06 CDT, unchanged). The boxd.sh homepage pricing FAQ was
re-verified against all known C29 facts (fork under 200 ms, €0.049
pricing card, €30 credits, self-hosted) — no changes.

### 2b. Vercel Sandbox: "Drives" public beta — new vendor-verified feature; the 32→64 GB default-storage claim stays UNVERIFIABLE

The vendor changelog (https://vercel.com/changelog, ~00:08 CDT) carries
a Sept 22 Sandbox entry: **"Drives for Vercel Sandbox are now in public
beta"** — persistent storage, up to 16 TiB, usage-based pricing
(**VERIFIED**, vendor's own changelog). This is a *separate feature*
from the evening pass's carried ask: the THIRD-PARTY blog claim that
default storage moved 32→64 GB remains **UNVERIFIABLE** — no vendor
confirmation found. Recorded here as a new datapoint, not a claim
resolution. (Watch-level note: persistent disk as a first-class
sandbox feature is the same direction as Boxd's persistent-machine
thesis and spark-vm's own persistent-VM positioning — color for the
corpus's "where spark-vm wins/lags" framing on the next consolidation,
not a design change.)

### 2c. DigitalOcean Managed Agents: third-party follow-up analysis (borderline in-window)

subagentic.ai published independent analysis of the Sept 22
public-preview launch (THIRD-PARTY, read ~00:06 CDT) — timing is
borderline (published ~19:00–20:00 CDT, just at the window start). It
corroborates the known facts (idle-pausing Firecracker microVMs, pause
stops CPU/memory charges with storage still billed, $5 new-user
credit, vendor's Sept 21 benchmark 886 ms session-ready / 305 ms
resume-to-ready) and adds **no new mechanism detail** beyond the
vendor release. The Business Wire launch release itself is pre-window
(Sept 22 morning ET) and is verbatim wire syndication across
tradingview.com, marketnewsdesk.com, and others — no independent
press coverage in-window. No hands-on coverage anywhere yet.

## 3. Standing items / carry-forwards

- **C14 (#47 resume-latency target):** still OPEN — needs our own
  measured provider baseline; the operator per-run Fly spend-cap
  decision is still owed (NEEDS_USER.md). No new benchmark-grade
  input this pass (Boxd's idle-resume stays a marketing-page figure;
  Vercel Drives has no latency claims at all).
- **C29:** the SDK-URL verification is closed (this pass); watch
  continues at routine cadence.
- **C26 (DO watch):** quiet this pass; vendor pages unchanged.
- **C12, C10:** stand, unchanged.
- **Vercel 32→64 GB claim:** stays UNVERIFIABLE — carried as the next
  pass's ask (vendor changelog watched; the Drives entry is not the
  claim).
- **Cloudflare Sandbox:** no new signal; deprioritized retained.
- **Next pass's ask:** re-check vercel.com/changelog for any
  default-storage vendor confirmation; routine tracked-set re-reads.

---

*Corpus note:* per the delta-only convention, watch docs record deltas
against the previous pass and the corpus changes only via
consolidation or primary-source verification. This pass's
primary-source verification (C29 SDK-URL) corrects the corpus entry's
stale "not VERIFIED" qualifier in this same PR — one sentence,
provenance-labeled, nothing else. Vercel Drives and the DO follow-up
live here until the next consolidation. The two surveyor captures are
archived verbatim in the loop's `agent_notes/` (workspace-only), not
the repo.
