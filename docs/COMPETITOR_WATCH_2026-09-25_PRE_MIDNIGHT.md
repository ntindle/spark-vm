# Competitor watch — 2026-09-25 (pre-midnight)

Targeted delta pass against the 2026-09-25 post-post-late-night pass
(`docs/COMPETITOR_WATCH_2026-09-25_POST_POST_LATE_NIGHT.md`). Survey window
**2026-09-25 ~20:55–21:10 CDT** — read-only fetches and searches; no
logins, no writes.

Scope note: this pass deliberately did NOT re-survey the full tracked
set — the last full pass (post-late-evening, merged as PR #429) was
**9/9 VERIFIED NO-CHANGE** ~5.5 hours earlier, and the post-post-late-night
pass re-verified the two fastest-moving tracked vendors ~55 minutes ago.
The value this slot is in (a) confirming the two fastest movers haven't
shipped another daily-cycle entry in the ~55–70 minutes since the last
pass, (b) the two standing carried leads C37 + C26 (last re-verified in
the late-night pass), and (c) a narrow delta news scan.

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **snippet-level** = seen only
via search snippet. **UNVERIFIED** = a public page exists but could
not be fetched this run (never reported as NO-CHANGE). **VERIFIED
absent** = the vendor's own page was read this run and the item is
confirmed not present on it.

## 1. Tracked-set re-verification (targeted)

### Daytona changelog — VERIFIED NO-CHANGE

`daytona.io/changelog` read live this run (full page, 2136 lines).
Newest entry is still **SEP 26 2026 — V0.218.0** (*"Daytona 0.218.0
adds a `kvm` parameter to sandbox creation in every SDK and moves
CLI login to a dedicated WorkOS application"*), followed by
**SEP 25 2026 — V0.217.0** (*"Daytona 0.217.0 adds the NVIDIA B300
GPU type to the API client."*) — both character-for-character
identical to the baseline. No new entry since the post-post-late-night
pass. VERIFIED NO-CHANGE this run.

### Docker Sandboxes release notes — VERIFIED NO-CHANGE

`docs.docker.com/ai/sandboxes/release-notes/` read live this run
(full page, 444/444 lines). Newest dated heading remains
**2026-09-22** (v0.45.1 sbx-releases — "Improved sandbox moves and
support for private kit images in cloud sandboxes"). No newer entry.
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
this run. Lead remains OPEN; next-watch ask unchanged (9th subpage
re-fetch already satisfied; re-check if the docs page is re-dated).

## 3. Delta news scan (narrow 2026-09-25 window)

Seven in-lane candidates; all dedupe to filed corpus, out-of-window,
or out-of-lane. **No new C-numbers.**

- **ADTmag — "Docker Launches Cloud Sandboxes" (Sep 24)** and
  **webpronews — "Docker's MicroVM Sandboxes" (Sep 25-dated recap)**:
  THIRD-PARTY recaps of the Sep-24 Cloud Sandboxes launch — dedupe to
  **C45** (already VENDOR-VERIFIED), no new facts. The webpronews piece
  adds one third-party rate datapoint ("pricing starts at seven cents
  per hour for the smallest instance... sessions max out at 24 hours"),
  which matches the corpus-adjacent how2shout rate card already filed —
  not a corpus change.
- **dailyaibrief — BAND × Docker Sandboxes integration**: THIRD-PARTY
  press release recap — dedupe to the C45 BAND-integration garnish
  already corpus, no new facts.
- **techtimes — DeepSeek DSec escape catalog (Sep 25)**: THIRD-PARTY —
  dedupe to **C56** (corpus), no new facts beyond the already-filed
  catalog numbers.
- **explainx.ai — Meta Muse / Sentinel VM security (Sep 9 post, Sep 25
  update)**: the "Muse users can export their own VM filesystem; Meta
  calls it intended" update is the same VM-filesystem-export story
  already filed as adjacent watch-only color in the mid-afternoon pass —
  no vendor confirmation beyond the spokesperson, still below the
  C-number bar.
- **CRN — VMware Explore wrap-up**: 22 days old, out of window.
- **markets.financialcontent — Embedded LLM TokenVisor Spaces for AMD
  (Sep 19 vintage)**: governed agent-workspace software on
  customer-managed infrastructure — enterprise PaaS adjacent, not a
  sandbox-provider launch; out of lane.

In-lane no-launch verdict dated 2026-09-25: no new sandbox/runtime
launches in-window beyond C45/C50/C52.

## 4. Standing notes

- Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass).
- Carried: C37 (OPEN), C26 (OPEN).
- Zero fetch failures this pass: all 4 vendor pages read first-try
  (Daytona, Docker release notes, freestyle.sh/pricing, DO docs
  pricing subpage).
