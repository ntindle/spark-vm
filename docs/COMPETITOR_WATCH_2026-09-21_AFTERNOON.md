# Competitor watch — afternoon pass, 2026-09-21

Delta-only update against the 2026-09-21 baseline
(`docs/COMPETITOR_WATCH_2026-09-21.md`) and the C17 resolution
(`docs/COMPETITOR_WATCH_2026-09-21_C17.md`). Survey window **2026-09-21
~04:54 → ~14:54 CDT**; reads ~15:00–15:15 CDT, two read-only surveyors.

Summary: **quiet window — zero in-window deltas** across the full
tracked set (no launches, acquisitions, pricing changes, releases, or
partner moves). One standing-item resolution: the twelve-provider
comparison table C17 flagged as needing a third read is verified as the
boat.dev pricing page's current state — the earlier baseline read was
simply partial (§1). Raw captures in the loop's `agent_notes/`
(workspace-only), not the repo.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **THIRD-PARTY** = reported by press/third-party
sources. **INFERRED** = my characterization, labeled as such.

## 1. C17 follow-up — twelve-provider comparison table verified current

**VERIFIED** ([boat.dev pricing](https://docs.boat.dev/pricing), read
~15:02 CDT — page fetches cleanly from non-runner fetchers; the
GitHub-runner bot-block behavior stands per the baseline):

- The baseline rate card holds unchanged: `default` 4 vCPU / 8 GB /
  50 GB disk at **$0.036/h**, per-second billing, "A stopped sandbox
  costs nothing," 25 free-hour trial (`small`/`default` only),
  concurrency 100/300/1,000/2,000 across the $20–$2,000 plans, "one
  `default` sandbox running a whole month (730 h) is $26." No "updated"
  timestamp visible this read.
- The xlarge footnote holds with the same substance: `xlarge` (16 vCPU /
  32 GB / 251 GB, **$0.200/h**) "needs a $100 plan or higher and an
  operator to allocate the capacity."
- **The twelve-provider comparison table is the page's current state:**
  Novita, Freestyle, exe.dev, E2B, Daytona, Blaxel, Codespaces,
  Cloudflare, Modal, Islo, Runloop, Vercel Sandbox — E2B and Daytona
  still **$0.331/h default**, no price move on either. The 2026-08-24
  "Performance" benchmark section (boat $0.36 vs E2B $8.19/23x per million
  runs) and the "For the API" billing section are also present today;
  flagged, NOT asserted as new, since earlier reads were proven partial.

**Resolution:** C17's temporal question is closed from the vendor's own
page — the baseline's two-provider read was partial; the twelve-provider
table is current policy, and the xlarge capacity-allocation caveat
remains a current vendor statement (see §3).

**Implication:** boat.dev remains the cheapest viable provider candidate
($0.036/h vs E2B/Daytona's listed $0.331/h), with the standing
capacity-allocation contingency on the 16-vCPU end unchanged.

## 2. The tracked set — quiet since the 2026-09-21 baseline

No in-window change detected across the full tracked set:

- **Microsandbox** — top release still **v0.7.1**, no v0.7.2
  (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~15:04).
- **Docker Sandboxes** — release notes still top out at **0.43.0** (Sep
  15); no 0.44 (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~15:05). The
  ~weekly Sep-7 → Sep-15 cadence keeps 0.44 likely imminent — watch
  stays tight. (Pre-window adjacent, already in corpus: CVE-2026-77179 /
  CVE-2026-79994 are recorded in `docs/COMPETITOR_ANALYSIS.md`; no new
  corpus line needed.)
- **E2B** — no pricing, launch, or suspend/resume semantic change; boat.dev's
  own table (read today) still shows E2B $0.331/h default —
  **INFERRED** corroboration of no price move (e2b.dev's own pricing
  page not read directly this pass). Search index shows latest SDK
  entries ~Sep 17 (2.51.0, v2 API endpoints; cli 2.20.0 sandbox fork) —
  pre-window.
- **Daytona** — changelog still tops at **SEP 15 2026, v0.214.0**; no
  in-window entries (**VERIFIED**: https://www.daytona.io/changelog,
  ~15:07).
- **AgentComputer** — egress posture remains UNVERIFIABLE this pass
  (agentcomputer.ai is a single-line landing with no network policy
  stated; getcompanion-ai GitHub org stale, nothing on egress). C12
  (egress-only) stands; no confirmable move either way.
- **TermSquad** — pricing re-verified against baseline ($9/$19/$29/$49
  tiers; $29 = 6 vCPU/12 GB/100 GB; $49 Ultra = 8 vCPU/24 GB/200 GB) —
  **THIRD-PARTY**; no change. Their X presence stays login-gated, so
  silence is uninformative.
- **WSO2 Agent Manager** — **THIRD-PARTY** in-window-ish blip: a new
  independent Stackademic recap published ~Sept 20–21 broadens GA
  reception (vs the prior "thin" note); no new product move. Sep 29
  webinar stays the trigger (C10).
- **Baseten / Blaxel** — no persistent-sandbox product shipped; the
  "perpetual sandbox + model serving in one org" combo stays the
  sharpest commercial benchmark (C11 stands).
- **OpenAI Agents API sandbox partners** — still nine (Blaxel,
  Cloudflare, Daytona, DigitalOcean, E2B, Modal, Oracle, Runloop,
  Vercel), no additions or departures (C9 stands).
- **FastGPT** — no follow-up to the v4.16.0 E2B deprecation.
- **Cloudflare × Cursor** — no new moves.
- **New entrants** — none found. TencentCloud CubeSandbox checked as a
  candidate: pre-existing (open-source since April 2026, v0.7.0 Aug 28),
  not new.

Adjacent color (pre-window, not a watch item): Marktechpost's Aug-27
per-second pricing table corroborates E2B/Daytona at $0.0504/vCPU-hr +
$0.0162/GiB-hr, consistent with boat.dev's ~9x-cheaper framing.

## 3. Standing items

- **C17** (boat.dev xlarge comparison-table verification): stays
  **CLOSED** — this pass verifies the table as current page state; the
  §1 caveat on 16-vCPU capacity allocation carries forward as vendor
  policy, not as a temporal question.
- No new backlog items from this pass (the Docker CVE color is already
  in the corpus; the Stackademic WSO2 recap changes nothing ahead of
  the Sep 29 webinar; D-FOLLOW — the one-line secrets-posture corpus
  note for diggerhq/opencomputer — stays with the build loop's docs
  turn).
- Carrying forward unchanged: C9 (OpenAI partners), C10 (WSO2 — Sep 29
  webinar is the next trigger), C11 (Baseten–Blaxel integration), C12
  (AgentComputer egress-only), C14 (#47 resume-latency target — open;
  needs measured boat.dev/provider baseline; live-API measurement awaits
  the operator per-run spend-cap decision).

---

*Corpus note:* per the reach-back policy this pass is delta-only; no
corpus record changed. Raw page captures live in the loop's
`agent_notes/` (workspace-only), not the repo.
