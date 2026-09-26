# Competitor watch — 2026-09-26 (late morning)

Two-surveyor pass: (A) fast-mover re-verification vs the ~05:24 CDT
baseline, (B) delta news scan ~05:55–06:05 CDT. Survey window
**2026-09-26 ~05:54–06:05 CDT**; read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-0554.md`,
`agent_notes/surveyor-b-20260926-0554.md` (goal-workspace notes, not
in the repo). Suffix `_LATE_MORNING` is admitted (2026-09-25
precedent); MID_MORNING was taken by the 05:24 slot.

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read
this run and the item is confirmed not present on it.

## 1. Tracked-set re-verification (fast movers)

All four read live this run, first try each, vs the ~05:24 baseline:

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
  entry still reads verbatim on the index (23 Sep) — not re-checked
  per P49 daily cadence (2026-09-26 morning pass).

## 2. Delta news scan (B)

The market surveyor's corpus-dedupe discipline holds this pass: one
genuinely new item, eight clean dedupes, remainder quiet or
out-of-lane.

- **NEW — C61: Modal rebuilt its sandbox infrastructure off
  Kubernetes (in-lane, THIRD-PARTY).** Modal staff engineers (Colin
  Weld, Connor Adams) detailed rebuilding Modal's sandbox layer from
  scratch off Kubernetes to support "millions of concurrent
  sandboxes and tens of thousands of creations per second." The
  forcing constraint was **scheduling latency at sandbox creation
  time** — the dominant cost when each agent turn wants its own
  isolated execution environment. Dated 2026-09-24
  (my2cents.ai digest, "AI Architecture Updates: September 24,
  2026") — ~48h old, slightly outside the ~24h window, but absent
  from the corpus (greps for "off Kubernetes", "Weld", "million
  concurrent" returned zero hits), so folded. The corpus Modal row
  covers gVisor/GPU/snapshots and the $15B raise talks but nothing
  on the off-Kubernetes infra rebuild or creation-latency
  economics. **Strategic color (advisory only, not a corpus claim):**
  the economics here are exactly the task-scoped-vs-persistent split
  this doc's Scope note draws — when sandbox creation is the per-turn
  operation, the scheduler IS the product. spark-vm's H4/H13
  suspend/wake work is the persistent-side answer to the same
  latency problem; the lesson travels sideways, not as a spec. The
  author + talk are not directly verified this pass — THIRD-PARTY
  grade stands until a vendor-primary read upgrades it.
- Dedupes (all against already-filed corpus entries, correctly
  skipped): Baseten/Blaxel acquisition-continuity piece = **C11**
  (migration-notice color already folded, prior "no corpus fold"
  decision); Modal ~$15B raise talks = Modal row THIRD-PARTY; DO
  Managed Agents launch PR = **C26 CLOSED** (pricing conflicts
  resolved 2:1 early-morning); Cursor Rollouts + Security Reviewer
  (adjacent lane, not tracked); Vercel Drives public-beta coverage =
  Drives beta row (pricing folded line 976); Vercel $1M Sandbox
  Challenge results (Sep 15, already folded); TermSquad Sep 15 launch
  PR = **C1**; Prime Sandboxes GA = **C48** (VENDOR-VERIFIED
  2026-09-25, with the ~30M counter / 865K dashboard inconsistency
  flagged).
- Out of lane: DockerAsk/DockerDash prompt-injection vuln (Noma
  Labs) — Docker Cloud Sandboxes is filed as **C45**; this is a
  Docker "Ask Gordon" MCP-metadata-injection research disclosure,
  not a sandbox-market move. No fold.
- Remainder quiet: Fly Sprites, Northflank, Runloop, boat.dev,
  Cloudflare containers — no in-window moves surfaced.

## 3. Verdict

- **Fast movers: 4/4 VENDOR-VERIFIED NO-CHANGE.** Delta news scan:
  **one new in-lane item (C61, Modal off-Kubernetes rebuild,
  THIRD-PARTY)**; everything else dedupes, quiet, or out-of-lane.
- In-lane no-launch verdict dated 2026-09-25 stands — **streak
  extends** (no new launches since the 02:24 slot's C59/C60).
- **One new C-number: C61.**
- **Carried:** C37 (Freestyle Pro fee VERIFIED absent), C57
  (Baponi), C58 (Leap0) — all OPEN, not re-surveyed this pass
  (per-pass rotation cadence, not per-slot repetition).
  Vercel Drives not re-checked (P49 — 2026-09-26 morning pass).
- Zero fetch failures.

## Conventions

Evidence labels per the header block. Dated 2026-09-26. The corpus
fold lives in `docs/COMPETITOR_ANALYSIS.md` under "Watch update —
2026-09-26 (late morning)". Surveyor-B corpus-dedupe miss streak
broken: its corpus greps were clean before flagging — the one NEW
item (C61) was genuinely absent from the corpus; the eight dedupes
were verified against corpus lines. Future market-surveyor briefs
keep the corpus-grep-before-NEW rule.
