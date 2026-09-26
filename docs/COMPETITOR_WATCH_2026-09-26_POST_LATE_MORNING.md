# Competitor watch — 2026-09-26 (post late morning)

Two-surveyor pass: (A) fast-mover re-verification vs the ~06:24 CDT
baseline, (B) delta news scan ~06:40–07:30 CDT. Survey window
**2026-09-26 ~07:24–07:38 CDT**; read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-0724.md`,
`agent_notes/surveyor-b-20260926-0724.md` (goal-workspace notes, not
in the repo). Suffix `_POST_LATE_MORNING` is admitted (2026-09-24
precedent); LATE_MORNING was taken by the 05:54 slot.

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read
this run and the item is confirmed not present on it.

## 1. Tracked-set re-verification (fast movers)

All four read live this run, vs the ~06:24 baseline:

- **Daytona changelog** (`daytona.io/changelog`) — VENDOR-VERIFIED
  NO-CHANGE. Newest still **SEP 26 2026 V0.218.0** ("KVM sandbox
  parameter and CLI WorkOS application"), then SEP 25 V0.217.0
  (NVIDIA B300 GPU), SEP 24 V0.216.1 + V0.216.2 — verbatim match
  against the baseline. (Surveyor A's `browser.open` failed on URL
  parsing; the worker re-read the live page directly this run.)
- **Docker Sandboxes release notes**
  (`docs.docker.com/ai/sandboxes/release-notes/`) — VENDOR-VERIFIED
  NO-CHANGE (full page read live, lines 0–237 of 444). Newest dated
  heading still **\*2026-09-22\*** ("Improved sandbox moves and
  support for private kit images in cloud sandboxes"), then
  \*2026-09-21\* (v3 kits). Nothing dated 2026-09-26.
- **Microsandbox releases**
  (`github.com/superradcompany/microsandbox/releases`) —
  VENDOR-VERIFIED NO-CHANGE (full page read live, all 292 lines).
  Newest still **v0.7.3** ("chore: release v0.7.3 by @toksdotdev in
  #1646"), then v0.7.1. Nothing newer.
- **Vercel changelog** (`vercel.com/changelog/sitemap.md` — the
  vendor's own full index in markdown format "for AI agents", 1370
  posts, read live) — VENDOR-VERIFIED NO-CHANGE. Newest entries
  still **2026-09-25** (vcr-action/login GitHub Action; Pixel Canary
  stealth on AI Gateway; Vercel Sandbox memory observability), then
  09-24, 09-23 (**Drives public beta** — still on the index). Nothing
  dated 2026-09-26. (Surveyor A's HTML-index fetch failed; the
  worker read the vendor's own machine-readable full index instead —
  same ordering as the baseline's full-index read.)

## 2. Delta news scan (B)

Corpus-dedupe discipline holds: every candidate grepped against the
corpus (C-max C62) before flagging — **11 clean dedupes, 0 NEW**:

- Docker Cloud Sandboxes third-party recrawls (adtmag 9/24,
  GlobeNewswire syndication) = **C45** (launch + pricing + press
  page all filed; recrawls add no facts);
- BAND Python Kit for Docker Sandboxes (runtimewire, Sep 26
  pre-window) = **C45** (the Sept-24 Kit-ecosystem signal is already
  in the C45 row);
- OpenAI "offline sandbox" escape third-party coverage (panews.io,
  zubiqo.com, ~12h old) = **C62** (already filed as adjacent; no new
  facts);
- Microsoft Copilot new Code feature (analyticsinsight, pre-window)
  = **C50** (Copilot Managed Runtime VENDOR-VERIFIED in corpus);
- Docker Sandboxes macOS virtio-fs escape (applethreat.com, 7 days
  old — CVE-2026-77179/CVE-2026-79994, fixed 0.42.0 Sep 7) = the
  corpus **Docker Sandboxes row** (vendor security announcements
  VERIFIED);
- DeafNews "AI Sandbox Escapes: The Paradox of Guardrails" (Sep 25)
  = adjacent commentary, no new facts (already noted in the C62
  watch section);
- Boxd $2M pre-seed recrawl (6ic.com) = **C29** (already filed);
- ByteAsk $1M pre-seed (finsmes, Sep 24) = corpus watch-doc color
  ("out of window");
- Factory $200M at $5B (Reuters Sep 15) = corpus adjacent demand
  signal;
- Daytona sweep = no in-window items (SEP 26 V0.218.0 already filed).
- Remainder quiet: Fly Sprites, Northflank, boat.dev, Runloop,
  Daytona, Docker, Vercel, Modal, Microsandbox, Cloudflare — no
  in-window moves beyond the deduped items.

**Noted for a future deep-scan — NOT folded this pass** (out of the
watch window per the reach-back policy): GitLab agent-sandbox escape
via allowlisted package proxy (omniline.app writeup, ~7 days old;
GitLab blog ~Sep 19: SSRF in package proxy + unsigned
refresh-token escalation, ~1h to open internet). In-lane adjacent
(vendor security research, not a product).

## 3. Verdict

- **Fast movers: 4/4 VENDOR-VERIFIED NO-CHANGE.** Delta news scan:
  **NO-CHANGE — 11 clean dedupes, 0 new C-numbers.**
- In-lane no-launch verdict dated 2026-09-25 stands — **streak
  extends** (no new launches since the 02:24 slot's C59/C60).
- **One out-of-window adjacent item noted for a future deep-scan**
  (GitLab package-proxy SSRF, not folded per reach-back).
- **Carried:** C37 (Freestyle Pro fee VERIFIED absent), C57
  (Baponi), C58 (Leap0) — all OPEN, not re-surveyed this pass
  (per-pass rotation cadence, not per-slot repetition).
  Vercel Drives not re-checked (P49 — 2026-09-26 morning pass).
- Two fetch failures this pass, both recovered by worker re-reads
  this run (Daytona HTML page; Vercel HTML index → vendor's own
  machine-readable full index) — **zero standing fetch failures**.

## Conventions

Evidence labels per the header block. Dated 2026-09-26. The corpus
fold lives in `docs/COMPETITOR_ANALYSIS.md` under "Watch update —
2026-09-26 (post late morning)". Surveyor-B corpus-dedupe discipline
continues to hold: every candidate grepped against the corpus (C-max
C62) before flagging — the zero-NEW verdict is earned, not
default. Surveyor-A fetch-failure honesty preserved: the two
failures were reported UNVERIFIED, never NO-CHANGE, and re-verified
live by the worker this run. Future market-surveyor briefs keep the
corpus-grep-before-NEW rule.
