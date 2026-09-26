# Competitor watch — 2026-09-26 (morning)

Owes-writeup pass: the 02:24 slot's P49 morning pass VENDOR-VERIFIED two
new 2026-09-25 Vercel changelog datapoints (in-lane C59, adjacent C60)
and captured them in
`agent_notes/surveyor-vercel-20260926-0224.md`; this pass writes them up
(no re-survey needed) and folds them into the corpus. Survey window
**2026-09-26 ~02:55–03:00 CDT** — the four fast movers were re-read
live this run; the C59/C60 detail reads date to ~02:4x CDT (same
session, same vendor pages, VENDOR-VERIFIED). Read-only; no logins, no
writes.

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read
this run and the item is confirmed not present on it.

## 1. C59 — Vercel Sandbox memory observability (in-lane, VENDOR-VERIFIED)

Vercel's 2026-09-25 changelog entry *"Vercel Sandbox now supports
memory observability"* (detail page
`vercel.com/changelog/vercel-sandbox-now-supports-memory-observability`,
read in full ~02:4x CDT). What shipped, vendor's own words:

- **Memory Usage card** in the sandbox observability dashboard:
  average, P75, and P95 memory usage across sandboxes.
- **Per-sandbox detail page**: the memory chart auto-scales its y-axis
  to the sandbox's memory *limit*, with a **dashed 85% reference
  line** — an explicit "you are at 85% of your limit" visual.
- **`memoryUsedBytes` measure** in the Observability query builder —
  custom queries and **alerts** on sandbox memory.
- **CLI**: `vercel metrics` under `vercel.sandbox.memory_used_bytes`
  (linked project or `--all`).

First *memory*-observability surface among the tracked vendors
recorded in the corpus. (Comparative note — advisory only: the corpus
records Daytona's sessions auto-pause but no memory-usage dashboard;
Docker's `sbx ls --json` CPU/memory-limits reporting is a vendor
release-notes fact read this run (`docs.docker.com/ai/sandboxes/release-notes/`,
2026-09-21 section) not yet recorded in this corpus — and it reports
limits, not usage.) The 85% reference line + alertable
`memoryUsedBytes` is a cost-control and capacity UX move: agent
workloads are long-lived and memory-leaky, and this is the first
tracked vendor to ship a first-class "your sandbox is about to OOM"
surface.

Design color for the spark-vm trail (weight-light, speculative —
advisory only, not a corpus claim): the H5 sentinel consumes
audit/telemetry surfaces (`docs/SENTINEL_TELEMETRY_SURFACES.md`); when
that surface grows a per-box resource dimension, the 85%-of-limit
reference-line convention is worth mirroring — it matches Vercel's
shipped convention for agent workloads. No corpus claim beyond
the vendor move itself; no pricing attached (observability surfaces
rarely carry one).

## 2. C60 — vercel/vcr-action/login GitHub Action (adjacent, VENDOR-VERIFIED)

Vercel's 2026-09-25 changelog entry *"Push images to Vercel Container
Registry from GitHub Actions"* (detail page
`vercel.com/changelog/vcr-login-github-action`, read in full ~02:4x
CDT):

- A GitHub Action (`vercel/vcr-action/login`) that logs workflows in
  to Vercel Container Registry **with GitHub OIDC** — "removing
  long-lived registry credentials from secrets."
- Short-lived token, revoked at job end; the changelog example builds
  linux/amd64 with zstd compression.
- **After VCR prepares the image it can be used as a custom Vercel
  Sandbox image** (`<repository>:<tag>` within the same project).

Lane: adjacent — VCR is the registry backing sandbox custom images,
not a sandbox product launch itself. The move that matters is the
closed loop: **CI-built image → sandbox custom image**, with the
credential hygiene (OIDC short-lived tokens, no long-lived registry
secrets) as the headline. This corroborates the direction spark-vm's
own stack takes: the `hsurr:` placeholder-swap posture and the golden
image workflow (`docs/GOLDEN_IMAGE_GATE_PROCEDURE.md`) both treat
long-lived image credentials as the thing to eliminate — Vercel is now
shipping the same conviction as a product feature for its custom-image
flow. Advisory color only; no C-number promotion.

## 3. Tracked-set re-verification (targeted — fast movers)

### Daytona changelog — VENDOR-VERIFIED NO-CHANGE

`daytona.io/changelog` read live this run (full page). Newest entries
still **SEP 26 2026 — V0.218.0** (`kvm` sandbox-creation parameter in
every SDK + CLI login moved to a dedicated WorkOS application) and
**SEP 25 2026 — V0.217.0** (NVIDIA B300 GPU type in the API client) —
character-identical to the 01:24 baseline. No new entry since.

### Docker Sandboxes release notes — VENDOR-VERIFIED NO-CHANGE

`docs.docker.com/ai/sandboxes/release-notes/` read live this run
(full page). Newest dated heading remains **2026-09-22** (v0.45.1 —
improved sandbox moves + private kit images in cloud sandboxes).
Nothing newer.

### Microsandbox releases — VENDOR-VERIFIED NO-CHANGE

`github.com/superradcompany/microsandbox/releases` read live this run
(full page). Newest release still **v0.7.3** (`chore: release v0.7.3`
via #1646), followed by v0.7.1, v0.7.0, v0.6.x — identical to the
01:24 baseline. No new release since.

### Vercel changelog — VENDOR-VERIFIED NO-CHANGE

`vercel.com/changelog` read live this run (full page). Newest entries
still **25 Sep** — the vcr-action/login entry, Pixel Canary on AI
Gateway (out-of-lane), and the memory-observability entry; then 24
Sep TanStack AI Auth, 23 Sep Blob stores / Gemini 3.8 TTS / **Drives
public beta**, 22 Sep GPT-6 Sol/Luna. No 26-Sep entries. **Vercel
Drives GA watch: NO-CHANGE** — still public beta, pricing page
`last_updated: 2026-09-10` unchanged per the 02:24 capture.

## 4. Verdict

- **C59 (in-lane) and C60 (adjacent) VENDOR-VERIFIED** and folded into
  the corpus this pass — genuinely new datapoints, neither present in
  any 2026-09-25/26 watch doc or the corpus before the 02:24 capture.
  (The capturing slot labeled them C50/C51; those identifiers were
  already taken — C50 = Microsoft Copilot Managed Runtime, C51 =
  Gemini antigravity-preview-09-2026 harness — so this pass renumbered
  them C59/C60.)
- Tracked set this pass: **4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona
  changelog, Docker release notes, Microsandbox releases, Vercel
  changelog).
- In-lane no-launch verdict dated 2026-09-25 stands. **Two new
  C-numbers this pass: C59 + C60** (see the renumbering note above).
- **Carried:** C26, C37, C57, C58 (all OPEN — not re-surveyed this
  pass; re-verification cadence is per-pass rotation, not per-slot
  repetition). Zero fetch failures (4 vendor-primary page reads
  first try).

## Conventions

Evidence labels per the header block. Dated 2026-09-26. The corpus
fold lives in `docs/COMPETITOR_ANALYSIS.md` under "Watch update —
2026-09-26 (morning)". C59/C60 move from "surveyed, writeup owed" to
**WRITTEN + FOLDED**; the writeup-owed BACKLOG items close this pass.
