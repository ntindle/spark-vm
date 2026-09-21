# Competitor watch — 2026-09-21

Delta-only update against the 2026-09-20 pass
(`docs/COMPETITOR_WATCH_2026-09-20.md`, live in `docs/`; survey window
~08:00 → ~08:50 CDT). This pass surveyed 2026-09-20 ~23:00 →
2026-09-21 ~03:00 CDT, across the full tracked set via two surveyors.

Summary: **quiet window — zero in-window deltas** across the full tracked
set (no launches, pricing changes, partner moves, or version bumps).
Two non-delta items worth the record: (1) the boat.dev pricing page was
re-read and matches the baseline rate card, but carries an
xlarge capacity-allocation caveat that should be verified as
pre-existing vs new before any sizing decision (§1); (2) a version
resolution — Microsandbox v0.7.1 confirmed on the vendor's releases page
post-window (the survey-window read caught the tag mid-publication); the
corpus record is vindicated, no change (§2).

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo this
run (link inline). **THIRD-PARTY** = reported by press/third-party sources.
**INFERRED** = my characterization, labeled as such.

## 1. boat.dev — pricing re-verified, xlarge allocation caveat flagged

**VERIFIED** ([boat.dev pricing](https://docs.boat.dev/pricing), read this
pass): the baseline rate card holds — $20/mo = 555h of 4vCPU/8GB
`default` ($0.036/h), per-second billing, stopped = free, 25 free-hour
trial, concurrency 100/300/1000/2000 across the $20–$2000 plans. No price
or tier change. Their own comparison table lists E2B and Daytona at
**$0.331/h default** (small column $0.166) — a third-party-vendor table
corroborating no visible price move on either (compare §3).

Two framings on the page merit attention for the provider evaluation:

- The page explicitly works the example "one default sandbox running a
  whole month (730h) is $26."
- **`xlarge` (16 vCPU) requires a $100+ plan *plus operator capacity
  allocation*.**

**INFERRED, flagged not asserted:** the search index shows the pricing
page "updated 2 days ago," but the content matches the known baseline, so
this pass **cannot label the xlarge note as new** — it may be a page
refresh restating pre-existing policy. Do not cite it as a change. The
next watch pass should capture the page and diff it against this read
before the evaluation treats 16-vCPU sizing as capacity-gated.

**Implication:** boat.dev stays the cheapest viable provider candidate —
~1/9th of E2B/Daytona's table-listed default rates ($0.331 ÷ $0.036 ≈
9.2×; boat.dev's own table labels the default column "(9x)"); the EU-only
+ young-company risks from the baseline stand. If
spark-vm's hosted sizing ever needs 16 vCPU, confirm the
capacity-allocation gating first — it could move the Fly-vs-boat math on
the large end.

## 2. Version resolution — Microsandbox v0.7.1 confirmed (corpus vindicated)

Post-window re-read of the vendor's releases page (2026-09-21 ~04:10 CDT,
review-time verification) shows **v0.7.1 as the top release** ("Full
Changelog: v0.7.0...v0.7.1"). Its notes carry exactly the corpus's v0.7.1
bullets — guest filesystem flush policies (#1591/#1595), npm provenance +
ordered SDK publication (#1588), CLI/SDK version separation (#1589) —
plus "fix(release): resume partially published npm releases" (#1585): the
tag was **mid-publication during the survey window**, which is why the
~03:00 read saw only v0.7.0.
(**VERIFIED**: https://github.com/superradcompany/microsandbox/releases)

**Resolution:** the corpus's v0.7.1 record stands as-is — the npm-vs-GitHub
question from the survey-window read is mooted (v0.7.1 exists publicly on
the vendor's own page), and the qualification edits this PR originally
added to `docs/COMPETITOR_ANALYSIS.md` are **reverted in the same PR** (no
corpus change). The doc's "no gap item" conclusion survives intact —
v0.7.1 adds no new networking/egress features beyond what the corpus
already recorded (strict hostname policy, SOCKS egress proxy, v0.7.0).

**Implication:** corpus-first research held up under a transient
vendor-page state; future passes should treat a "latest tag missing"
sighting as a publish-in-flight candidate before recording a corpus
correction.

## 3. The tracked set — quiet since the 2026-09-20 pass

No in-window change detected: no in-window delta vs the corpus record —
the corpus already carried Microsandbox v0.7.1; the vendor page caught up
post-window. The ~08:50 → ~23:00 segment is covered by
this pass's broad market scan (last-~24h window); no deltas found there
either.

- **Docker Sandboxes** — no 0.44; the release-notes page still tops out at
  0.43.0 (Sep 15) (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/). No Docker AI
  Governance news in the window. The ~weekly Sep-7 → Sep-15 cadence makes
  0.44 likely imminent — keep the watch tight.
- **TermSquad** — no public pricing/product change surfaced ($9/$19/$29/$49
  standing, not re-verified this window); their X presence stays
  login-gated, so silence is uninformative.
- **E2B** — no pricing, launch, or suspend/resume semantic change since
  the 2026-09-20 pass; the Sep-11 enterprise egress-resolved-secrets
  design noted then remains the security posture to watch.
- **Daytona** — quiet.
- **AgentComputer** — no egress-posture move (C12 stays egress-only); the
  getcompanion-ai rename trail remains unverifiable in-window.
- **WSO2 Agent Manager** — GA reception still thin (wire syndication + one
  independent restatement, pre-window); nothing new ahead of the Sep 29
  webinar (C10's next trigger).
- **Baseten / Blaxel** — no persistent-sandbox product shipped; the
  "perpetual sandbox + model serving in one org" combo stays the sharpest
  commercial benchmark (C11 stays open).
- **OpenAI Agents API sandbox partners** — still nine (Blaxel, Cloudflare,
  Daytona, DigitalOcean, E2B, Modal, Oracle, Runloop, Vercel), no
  additions or departures (C9 stays open).
- **FastGPT** — no follow-up to the v4.16.0 E2B deprecation; E2B's
  displacement stands as the vendor-dependency cautionary data point.
- **Cloudflare × Cursor** — no new moves; the customer-owned-execution
  trend line holds.
- **Broad market scan** — no new launches, acquisitions, major releases,
  or pricing changes in the agent-sandbox / persistent-computer segment in
  the last ~24h (only adjacent noise: regulatory sandboxes, AI-agent
  news digests).

Adjacent color (pre-window, not a watch item): diggerhq/opencomputer's
docs describe a secret-store egress proxy (keys never enter the sandbox;
real key swapped in-flight, egress-allowlisted to model providers —
**VERIFIED**, ~3 days old,
[opencomputer.dev](https://opencomputer.dev/guides/e2b-alternatives/)) —
the same shape as spark-vm's swapd design,
from an independent project. Worth one line in the secrets-posture
corpus, not a new item.

Proposed from this pass: **C17** (boat.dev xlarge capacity-allocation
verification — new standing item); no other new backlog items. Standing:
C9 (OpenAI
partners), C10 (WSO2 — Sep 29 webinar is the next trigger), C11
(Baseten–Blaxel integration), C12 (AgentComputer egress-only), C14 (#47
resume-latency target — open; needs measured boat.dev/provider baseline;
live-API measurement awaits the operator per-run spend-cap decision —
see H4's unblock pass). **C17 (boat.dev xlarge):** the §1
capacity-allocation caveat must be captured and diffed against this read
on the next pricing-page check before any 16-vCPU sizing decision; stays
open until the pre-existing-vs-new question is resolved. The §1 xlarge
caveat is now a standing item (C17), not a footnote.

---

*Corpus note:* per the reach-back policy, §2 is a post-window primary-source
resolution (no pre-window backfill — the qualification originally added
to `docs/COMPETITOR_ANALYSIS.md` is reverted in this same PR); the
boat.dev framings are flagged, not backfilled as changes.
No other pre-window items added.
