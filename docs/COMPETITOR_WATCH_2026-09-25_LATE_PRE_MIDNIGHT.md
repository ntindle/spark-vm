# Competitor watch — 2026-09-25 (late pre-midnight)

Targeted delta pass against the 2026-09-25 pre-midnight pass
(`docs/COMPETITOR_WATCH_2026-09-25_PRE_MIDNIGHT.md`). Survey window
**2026-09-25 ~21:25–21:40 CDT** — read-only fetches and searches; no
logins, no writes. The `_LATE_PRE_MIDNIGHT` suffix is admitted this
pass (the 20:54 slot took `_PRE_MIDNIGHT`; this is the ~21:24 slot).

Scope note: this pass deliberately did NOT re-survey the full tracked
set — the last full pass (post-late-evening, merged as PR #429) was
**9/9 VERIFIED NO-CHANGE** ~4 hours earlier, and the pre-midnight pass
re-verified the two fastest-moving tracked vendors ~25 minutes ago.
The value this slot is in (a) confirming the fastest movers haven't
shipped another daily-cycle entry in the ~25–30 minutes since the
last pass, (b) **rotating the mover coverage**: Microsandbox's
release list re-verified this pass (last read in the post-late-evening
full pass (~16:24–17:05 CDT) — a coverage gap the last two Daytona/Docker-only passes left
open), (c) the two standing carried leads C37 + C26, and (d) a
narrow delta news scan.

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read
this run and the item is confirmed not present on it.

## 1. Tracked-set re-verification (targeted)

### Daytona changelog — VERIFIED NO-CHANGE

`daytona.io/changelog` read live this run (full page, 2136 lines).
Newest entry is still **SEP 26 2026 — V0.218.0** (*"Daytona 0.218.0
adds a `kvm` parameter to sandbox creation in every SDK and moves CLI
login to a dedicated WorkOS application"*), followed by **SEP 25
2026 — V0.217.0** (*"Daytona 0.217.0 adds the NVIDIA B300 GPU type to
the API client."*) — both character-for-character identical to the
baseline. No new entry since the pre-midnight pass. VERIFIED
NO-CHANGE this run.

### Docker Sandboxes release notes — VERIFIED NO-CHANGE

`docs.docker.com/ai/sandboxes/release-notes/` read live this run
(full page, 444/444 lines). Newest dated heading remains
**2026-09-22** (v0.45.1 sbx-releases — "Improved sandbox moves and
support for private kit images in cloud sandboxes"). No newer entry.
VERIFIED NO-CHANGE.

### Microsandbox releases — VERIFIED NO-CHANGE

`github.com/superradcompany/microsandbox/releases` read live this
run (full page). Newest release is still **v0.7.3** (the
`chore: release v0.7.3` via #1646 entry), followed by v0.7.1
(full changelog `v0.7.0...v0.7.1`), v0.7.0, and the v0.6.x series —
identical to the post-late-evening full-pass read (~16:24–17:05 CDT). No new release since.
VERIFIED NO-CHANGE.

## 2. Carried-lead re-verification

### C37 — freestyle.sh/pricing (Pro fee) — VERIFIED NO-CHANGE

Read live this run. **Pro fee still NOT printed**: the page names all
three plans (Free, Hobby, Pro) in the limits table but no dollar fee
for Pro appears anywhere. The only plan-fee figure on the page is
Hobby's, given as an example in the FAQ (*"you pay the greater of
your plan fee or your usage, so $50 on Hobby covers your first $50
of usage"*). Rate card unchanged, verbatim:

- `| Hour of vCPU | $0.04032 | 200 per month |`
- `| Hour of GiB Memory | $0.0129 | 400 per month |`
- `| Hour of GiB Storage | $0.000086 | 60,000 per month |`
- `| GB of Data Transfer | $0.02 | 50 free, 500 on paid |`

The structural pattern persists: tiers listed by name and limits,
fees exist only as implied commitments in FAQ prose ("on paid plans
your monthly fee is a commitment that doubles as usage credit").
Lead remains OPEN; watch continues.

### C26 — DigitalOcean Managed Agents docs pricing — VERIFIED NO-CHANGE

`docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/`
read live this run (68 lines, full page). The **$0.05/GiB-month
figure still appears three times**:

- `| Session Storage (Volumes) | $0.05 per GiB-month | Peak storage consumed |`
- "Billed per GiB stored when you use snapshots or checkpoints at
  **$0.05 per GiB-month**."
- "billed per GiB of image size at **$0.05 per GiB-month**"
  (custom sandbox images)

Page stamp: **"Last verified 22 Sep 2026"**. The active-CPU
tension persists verbatim: body copy bills "per second of active
compute based on actual CPU consumption" while the footnote reads
"*Active CPU billing is coming soon. Until then, you will be billed
at 25% of the vCPUs allocated to your sandbox.*" The 10× discrepancy
against DO's own investor-relations launch page ($0.005/GiB-month
for snapshots) stands as the open caveat; no new data to resolve it
this run. Lead remains OPEN; next-watch ask unchanged (re-check if
the docs page is re-dated).

## 3. Delta news scan (narrow 2026-09-25 window)

Two searches; all in-lane candidates dedupe to filed corpus.
**No new C-numbers.**

- **ADTmag — "Docker Launches Cloud Sandboxes" (Sep 24)** and
  **The Register — "Docker's new sandboxes aim to contain AI agents
  for real" (Sep 24)**: THIRD-PARTY recaps of the Sep-24 Cloud
  Sandboxes launch — dedupe to **C45** (already VENDOR-VERIFIED), no
  new facts. The Register piece's Cavage demo of a Claude-in-container
  probing for host secrets via the mounted Docker socket is
  containment-color, not a new vendor surface.
- **GlobeNewswire syndication recrawls** (marketminute.com,
  independent.mk, theantlersamerican, therapybutbetter.com,
  sexaulity.com — all Sep-24-dated): the same Docker launch
  announcement verbatim — dedupe to **C45**, no new facts.
- First search's GitHub-dev-docs results (Daytona field-guide,
  sandbox provider specs, agentbox-sdk): third-party engineering
  notes, all 8–12 days old — out of window, no filings.

In-lane no-launch verdict dated 2026-09-25: no new sandbox/runtime
launches in-window beyond C45/C50/C52.

## 4. Standing notes

- Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass).
- Carried: C37 (OPEN), C26 (OPEN).
- Zero fetch failures this pass: all 5 vendor pages read first-try
  (Daytona, Docker release notes, Microsandbox releases,
  freestyle.sh/pricing, DO docs pricing subpage).
