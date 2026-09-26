# Competitor watch — 2026-09-26 (post-midnight)

Targeted delta pass against the 2026-09-25 near-midnight pass
(`docs/COMPETITOR_WATCH_2026-09-25_NEAR_MIDNIGHT.md`). Survey window
**2026-09-26 ~01:24–01:36 CDT** — read-only fetches and searches; no
logins, no writes. The `_POST_MIDNIGHT` suffix follows the slot stacking
convention (… `_POST_POST_PRE_MIDNIGHT` → `_NEAR_MIDNIGHT` → this is the
~01:24 slot).

Scope note: the last full tracked-set pass (post-late-evening, merged as
PR #429) was **9/9 VERIFIED NO-CHANGE** ~16 hours earlier; the fast
movers were re-verified NO-CHANGE ~80–90 minutes before this pass
(00:08 slot). This pass's job is (a) confirming the fastest movers
shipped no new daily-cycle entry in the ~90 minutes since, (b) the
scheduled **direct content read of the `docker/sandbox-kit-spec` repo**
(the Architecture note on the 23:24 pass scheduled it; the 00:08 slot
read the *commits page only* — the "conforming-runtime standard"
corpus claim still rested on unattributed inference), and (c) a narrow
delta news scan. Carried leads C37 + C26 (verified ~22:00 2026-09-25) and
adjacent C57/C58 (filed this window) were not re-surveyed —
re-verification cadence is per-pass rotation, not per-slot repetition.
Vercel Drives not re-checked (P49 — 2026-09-26 morning pass).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read
this run and the item is confirmed not present on it.

## 1. Tracked-set re-verification (targeted — fast movers)

### Daytona changelog — VERIFIED NO-CHANGE

`daytona.io/changelog` read live this run (full page). Newest entries
are still **SEP 26 2026 — V0.218.0** (`kvm` sandbox-creation parameter
in every SDK + CLI login moved to a dedicated WorkOS application) and
**SEP 25 2026 — V0.217.0** (NVIDIA B300 GPU type added to the API
client) — character-identical summaries to the 00:08 baseline. No new
entry since. VERIFIED NO-CHANGE.

### Daytona pricing — VERIFIED NO-CHANGE

`daytona.io/pricing` read live this run (full page). Rate card verbatim:
vCPU $0.0504/h, memory $0.0162/GiB/h, storage $0.000108/GiB/h after
first 5 free, Windows $0.0858/vCPU/h, per-second billing, $200 free
compute. Preemptible GPU ladder verbatim: B300 $4.08/h, B200 $3.59/h,
AMD MI355X $3.44/h, H200 $2.61/h, H100 $2.27/h, RTX PRO 6000 $1.74/h,
RTX 5090 $0.74/h, RTX 4090 $0.57/h. VERIFIED NO-CHANGE.

### Docker Sandboxes release notes — VERIFIED NO-CHANGE

`docs.docker.com/ai/sandboxes/release-notes/` read live this run
(full page). Newest dated heading remains **2026-09-22** (v0.45.1 —
improved sandbox moves + private kit images in cloud sandboxes).
Nothing newer. VERIFIED NO-CHANGE.

### Microsandbox releases — VERIFIED NO-CHANGE

`github.com/superradcompany/microsandbox/releases` read live this run
(full page). Newest release still **v0.7.3** (`chore: release v0.7.3`
via #1646), followed by v0.7.1, v0.7.0, v0.6.x — identical to the 00:08
baseline. No new release since. VERIFIED NO-CHANGE.

## 2. Docker Sandbox Kit Spec — direct content read (CONFIRMED, vendor-attested)

The 23:24 pass's Architecture review scheduled a direct read of
`github.com/docker/sandbox-kit-spec` to confirm or retract the corpus
claim that "the conforming-runtime standard [is] now the
interoperability reference" (C45 fold from the 22:54 pass —
unattributed inference at the time). The 00:08 slot read the repo's
*commits page*; this pass read the *spec content itself*. **Confirmed —
now VENDOR-VERIFIED, not inference:**

- Repo subtitle (vendor-owned, read live this run): *"Docker Sandbox Kit
  Specification v3 — the kit descriptor grammar, the OCI artifact, the
  build frontend, and the **conformance suites**."*
- README §Conformance: *"Two suites judge conformance, and
  `docs/spec/conformance.md` specifies what each one means"* —
  `kit-tck` binaries released per GitHub release; a runtime is tested
  through an adapter ("*does this runtime behave as the pages
  require?*").
- `docs/spec/conformance.md` §2 (Runtime conformance, vendor's own
  spec text, read live this run): *"A runtime demonstrates conformance
  by supplying an **adapter** … so a runtime **conforms by what it
  does, not by how it is written**."* §3 (Reporting conformance):
  *"A runtime claiming conformance **SHOULD** state which capability
  types it implements and publish the suite's output."* Partial
  implementations are conforming for claimed types *"provided it refuses
  what it cannot provide."*
- Docker's own blog ("Authority as Code",
  `docker.com/blog/docker-sandbox-kit-spec/`, VENDOR-VERIFIED via
  search-page full-body read this run): *"every capability type has
  its own page describing what a conforming runtime must implement …
  Two conformance suites ship with it: one judges whether an artifact is
  a conforming Kit, the other whether a runtime behaves as the pages
  say. Every normative statement is covered by a check or a written
  waiver"* — and the portability thesis in Docker's own words: *"Docker
  Sandboxes will be a first-class implementation, not the only one."*

**Corpus impact (C45):** the "conforming-runtime standard now the
interoperability reference" claim upgrades from unattributed inference
to VENDOR-VERIFIED — the spec's own conformance doc defines a formal
runtime-conformance mechanism (adapter verbs, exit-code semantics,
published claim convention), and Docker explicitly positions it as an
interoperability layer beyond a single vendor. The advisory posture
stands ("treat the Kit spec as the interoperability reference, don't
invent a proprietary grant format" for the H11 governance axis).

Design color for the H4 design trail (weight-light, speculative): the
runtime TCK's adapter verbs are a *conformance-visible lifecycle
vocabulary* — `stop`/`start` ("stop without discarding state"),
`recreate` (fresh writable layer, declared volume state preserved),
`status` (host-side `running`/`stopped` observation), and `wait-idle`
(required only for adapters claiming
`com.docker.sandbox/long-running@1`) — i.e. stopped-vs-running and
long-running vs task-scoped are conformance-testable runtime
behaviors, not private vocabulary. That is the same axis as H4's
`suspended`/`waking` + async `dial()` contract; a future H4 adapter
should map this axis rather than invent a proprietary state
vocabulary. No corpus change beyond the C45 garnish; no new C-number.

Repo facts noted: 215 commits, 64 stars, Apache-2.0, created
2026-09-16, current commit `3a70fc2a` at read time; `kit-tck`
release binaries attached per GitHub release.

## 3. Delta news scan — clean, NO-CHANGE

Three narrow queries across the 00:08–01:33 window (launches, pricing
changes, funding, provider releases, news vertical). Nothing genuinely
new in-lane. Near-misses, all out-of-window or out-of-lane:

- Docker Cloud Sandboxes GA + Kit Spec → CNCF (announced Sep 24) →
  dedupe to **C45** (already VENDOR-VERIFIED), no new facts. The
  "Authority as Code" blog read above is the same blog VENDOR-VERIFIED
  at the 22:54 pass; re-read this run only for the conformance
  confirmation quotes.
- OpenAI Agents API public beta (Sep 10) → **C9**; in-lane no-launch
  verdict covers (still beta, no GA).
- Cloudflare Cursor Cloud Agents (Sep 2) → filed corpus; known.
- **Z.ai open-sources ZCode (Sep 21, THIRD-PARTY)** → adjacent /
  out-of-lane: a coding-agent client's Apache-2.0 code drop following a
  telemetry scandal (uploaded encrypted workspace snapshots), not a
  sandbox/runtime product surface. Noted, no C-number.
- VS Code 1.139 remote Dev Container AI-agent support (Sep 23) →
  out-of-lane (IDE feature, not an agent-sandbox product).
- FastGPT Agent Sandbox v4.16 upgrade guidance (Sep 14) → out-of-lane
  (self-hosted LLM-app platform's deployment guidance, not a
  sandbox-for-agents product launch) and out-of-window.
- DigitalOcean Managed Agents explainer (explainx.ai, ~Sep 23) →
  dedupe to **C26**; still no dollar pricing — "pay-per-use CPU"
  positioning with no rate card. C26 stays OPEN, no delta.

**No new launch-verdict change:** in-lane no-launch verdict dated
2026-09-25 stands. **No new C-numbers.**

## 4. Verdict

Tracked set this pass: **4/4 VENDOR-VERIFIED NO-CHANGE** on the
fast-mover cycle (Daytona changelog, Daytona pricing, Docker release
notes, Microsandbox releases) + **one corpus-impacting confirmation**
(the spec-content direct read: C45's "conforming-runtime standard" claim
upgrades from unattributed inference to VENDOR-VERIFIED — the C45 fold
carries the evidence; the scheduled-read BACKLOG item closes). Zero
fetch failures (6 vendor-primary page reads first try; 2 vendor-blog
full-body reads).

**Carried:** C26 (snapshot-pricing discrepancy, OPEN), C37 (OPEN), C57
Baponi, C58 Leap0 (new this window, OPEN) — none re-surveyed this
pass; Vercel Drives not re-checked (P49 — 2026-09-26 morning pass).

## Conventions

Evidence labels per the header block. Dated 2026-09-26. The corpus
fold lives in `docs/COMPETITOR_ANALYSIS.md` under "Watch update —
2026-09-26 (post-midnight)". The scheduled-read BACKLOG item
(direct read of `docker/sandbox-kit-spec`) closes this pass:
CONFIRMED against the spec content itself.
