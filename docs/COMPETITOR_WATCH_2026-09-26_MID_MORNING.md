# Competitor watch — 2026-09-26 (mid morning)

Two-surveyor pass: (A) fast-mover re-verification vs the ~04:24 CDT
baseline, (B) delta news scan ~04:56–05:02 CDT. Survey window
**2026-09-26 ~04:56–05:02 CDT**; read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-0454.md`,
`agent_notes/surveyor-b-20260926-0454.md` (goal-workspace notes, not
in the repo). Suffix `_MID_MORNING` is admitted (2026-09-25
precedent); EARLY_MORNING was taken by the 04:24 slot.

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read
this run and the item is confirmed not present on it.

## 1. Tracked-set re-verification (fast movers)

All four read live this run, first try each, vs the ~04:24 baseline:

- **Daytona changelog** (`daytona.io/changelog`) — VENDOR-VERIFIED
  NO-CHANGE. Newest still **SEP 26 2026 V0.218.0** ("KVM sandbox
  parameter and CLI WorkOS application"), then SEP 25 2026 V0.217.0
  (NVIDIA B300 GPU). Nothing newer.
- **Docker Sandboxes release notes**
  (`docs.docker.com/ai/sandboxes/release-notes/`) — VENDOR-VERIFIED
  NO-CHANGE. Newest dated heading still **2026-09-22** (improved
  sandbox moves + private kit images in cloud sandboxes), then
  2026-09-21 (v3 kits, cloud sbx). Nothing newer.
- **Microsandbox releases**
  (`github.com/superradcompany/microsandbox/releases`) —
  VENDOR-VERIFIED NO-CHANGE. Newest still **v0.7.3** (chore: release
  v0.7.3 by @toksdotdev in #1646), then v0.7.1. Nothing newer.
- **Vercel changelog** (`vercel.com/changelog`, full index) —
  VENDOR-VERIFIED NO-CHANGE. Newest entries still **25 September**
  (vcr-action/login GitHub Action; Pixel Canary stealth on AI
  Gateway; Vercel Sandbox memory observability), then 24 Sep
  (TanStack AI Auth), 23 Sep (Blob stores unlimited; Gemini 3.8 TTS;
  **Drives public beta**). Nothing dated 26 September. The Drives
  entry still reads verbatim on the index (23 Sep) — no Drives
  pricing pages opened (P49: Drives GA watch is daily-morning
  cadence).

## 2. Delta news scan (B)

The market surveyor's three in-window candidates ALL dedupe to
already-filed corpus entries at vendor grade — the corpus is ahead
of the scan:

- The **Cloudflare Containers/Sandboxes cross-tenant disk-residue
  disclosure** (dm-thin `skip_block_zeroing`, disclosed Sep 24/25) =
  **C55**, already VENDOR-VERIFIED on blog.cloudflare.com (2026-09-25
  early-afternoon fold: full vendor timeline, 5,614 testable blocks /
  2,700 distinct foreign inodes, no evidence of exploitation). The
  surveyor carried only third-party coverage; the corpus holds the
  vendor-primary read. No corpus change.
- The **Docker Sandbox Kit Spec open-sourced (Apache 2.0) with CNCF
  submission** = **C52**, already VENDOR-VERIFIED on docker.com/blog
  (2026-09-25 mid-morning fold, ecosystem collaborators named, spec
  repo `docker/sandbox-kit-spec`). No corpus change.
- The **Docker Cloud Sandboxes launch** (Sept 24, Micro 1vCPU/2GiB
  $0.07/h → XL 16/32 $1.12/h, $250 credit) = **C45**, already
  VENDOR-VERIFIED with the full launch garnish chain (press page,
  boot-time quote, WeAreDevelopers onstage). No corpus change.

No novel items; no re-surgery of stale entries. Stale/checked-not-new
items the surveyor logged (Runpod Flash May-2026, Railway $100M,
Fly.io Series D Jul-2026, Fly Sprites, E2B seed, DO Managed Agents
Sept-23) are out-of-window or already corpus — correctly skipped.

## 3. Verdict

- **Fast movers: 4/4 VENDOR-VERIFIED NO-CHANGE.** Delta news scan:
  **NO-CHANGE** — all candidates dedupe to filed corpus (C55/C52/C45).
- In-lane no-launch verdict dated 2026-09-25 stands — **streak
  extends** (no new launches since the 02:24 slot's C59/C60).
- **No new C-numbers.**
- **Carried:** C37 (Freestyle Pro fee VERIFIED absent, folded
  ~04:00 CDT), C57 (Baponi), C58 (Leap0) — all OPEN, not re-surveyed
  this pass (per-pass rotation cadence, not per-slot repetition).
  Vercel Drives not re-checked (P49 — 2026-09-26 morning pass).
- Zero fetch failures.

## Conventions

Evidence labels per the header block. Dated 2026-09-26. The corpus
fold lives in `docs/COMPETITOR_ANALYSIS.md` under "Watch update —
2026-09-26 (mid morning)". Surveyor-B corpus-dedupe miss recorded
honestly: its three "NEW" hits were all in-corpus at vendor grade
(C55, C52, C45) — the miss is a dedupe failure against the corpus,
not missing evidence. Future market-surveyor briefs should require a
corpus grep before flagging an item NEW.
