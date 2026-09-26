# Competitor watch — 2026-09-25 (near-midnight)

Targeted delta pass against the 2026-09-25 post-post pre-midnight pass
(`docs/COMPETITOR_WATCH_2026-09-25_POST_POST_PRE_MIDNIGHT.md`). Survey window
**2026-09-25 ~23:54–00:02 CDT** — read-only fetches and searches; no
logins, no writes. Two parallel read-only surveyors (fast-mover vendor
re-verifications + narrow delta news scan); full captures at
`hidden_files/agent_notes/surveyor-a/b-20260925-2354.md` (workspace, not
the repo).

Scope note: the last full tracked-set pass (post-late-evening, merged as
PR #429) was **9/9 VERIFIED NO-CHANGE** ~13 hours earlier; the fast movers
were re-verified NO-CHANGE ~20–30 minutes before this pass (23:24 repair
slot). This pass's job is (a) confirming the fastest movers shipped no
new daily-cycle entry in the ~20 minutes since, (b) the scheduled direct
read of the `docker/sandbox-kit-spec` repo (a non-blocking note from the
23:24 pass's Architecture review), and (c) a narrow delta news scan.
Carried leads C37 + C26 (verified ~22:00) and adjacent C57/C58 (filed
this window) were not re-surveyed — re-verification cadence is per-pass
rotation, not per-slot repetition. Vercel Drives not re-checked (P49 —
2026-09-26 morning pass).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read
this run and the item is confirmed not present on it.

## 1. Tracked-set re-verification (targeted — fast movers)

### Daytona changelog — NO NEW ENTRIES since the 23:24 pass

`daytona.io/changelog` read live this run (all 6 vendor fetches first
try, zero retries). Newest entries are still **SEP 26 2026 — V0.218.0**
(`kvm` sandbox-creation parameter in every SDK + CLI login moved to a
dedicated WorkOS application) and **SEP 25 — V0.217.0** (NVIDIA B300 GPU
type added to the API client) — **both already folded** in the
post-late-night pass (PR #442). Surveyor A compared against its 14:24 CDT
baseline and reported these as "new since 14:24"; corrected against the
23:24 baseline: nothing new inside this pass's ~20-minute window.
Color kept, not re-folded: the release details note v0.217.0 was
retagged and sdk-go v0.217.0 retracted — a rapid retag cycle worth
remembering the next time a Daytona changelog entry appears (a same-day
version line does not mean a stable artifact).

### Daytona pricing — VERIFIED NO-CHANGE

`daytona.io/pricing` read live, verbatim unchanged: $0.0504/vCPU-h,
$0.0162/GiB-h, $0.000108/GiB-h storage, Windows $0.0858/vCPU-h, $200
free compute; preemptible GPU ladder intact.

### Docker Sandboxes release notes — VERIFIED NO-CHANGE

`docs.docker.com/ai/sandboxes/release-notes/` read live: newest dated
heading still **2026-09-22** (v0.45.1 — improved sandbox moves + private
kit images in cloud sandboxes); nothing added after 2026-09-21.

### Microsandbox releases — VERIFIED NO-CHANGE

`github.com/superradcompany/microsandbox/releases` read live: newest
still **v0.7.3** (`chore: release v0.7.3` by @toksdotdev in #1646);
nothing published after v0.7.3 in this window.

## 2. Docker Sandbox Kit Spec repo activity (noted, timing unverifiable)

The 23:24 pass's Architecture review scheduled a direct read of
`github.com/docker/sandbox-kit-spec` — done this pass. The commits page
shows **17 commits under "Sep 25"**, led by **PR #63** (spec + TCK: mixins
can request long-running sandboxes; new `long-running-workloads`
capability), plus docs PRs (#62, #60, #58, #54), example-kit fixes, and a
#55 agent-kit bump; 1 commit Sep 24. The commits page exposes no
intra-day timestamps, so none of this can be confirmed as an in-window
(23:24–00:02) delta — treated as **noted activity, not a confirmed
delta**.

Design color (speculative, weight-light): a `long-running-workloads`
capability in the TCK is the spec layer growing an explicit lifecycle
axis — long-running vs task-scoped workloads as a *conformance-visible*
capability. That is the same axis as spark-vm's suspend/wake contract
discussions (H4's `suspended`/`waking` + async `dial()`); if it lands in
the spec, the H4 adapter axis should map it rather than invent a
proprietary state vocabulary. Flagged for the H4 design trail, no corpus
change: C45's row gains a garnish note, no new C-number.

## 3. Delta news scan — clean, NO-CHANGE

Seven narrow queries across the 23:24–23:56 window (launches, pricing
changes, funding, provider releases, news vertical). Nothing genuinely
new in-lane. Near-misses, all out-of-window or out-of-lane:

- Docker Cloud Sandboxes GA + Kit Spec → CNCF (announced Sep 24) → C45
  (already corpus).
- Claude Code Cloud Sessions GA (Sep 24), Opus 5.5 price cut (Sep 22) →
  adjacent / out of lane.
- dev.to sandbox comparison roundup (E2B/Vercel/Modal/Daytona) →
  THIRD-PARTY commentary, ~4h old, no new facts.
- Baponi, Leap0 → C57/C58 carried, no delta.

## 4. Verdict

In-lane no-launch verdict dated 2026-09-25 stands. **No new C-numbers.**
Zero fetch failures (6/6 vendor fetches first try). Carried: C26
(snapshot-pricing discrepancy, OPEN), C37 (OPEN), C57 Baponi, C58 Leap0
(new this window, OPEN) — none re-surveyed this pass; Vercel Drives not
re-checked (P49 — next the 2026-09-26 morning pass).
