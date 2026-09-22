# Competitor watch — night pass, 2026-09-22

Delta-only update against the evening baseline
(`docs/COMPETITOR_WATCH_2026-09-21_EVENING.md`). Survey window
**2026-09-21 ~17:54 → 2026-09-22 ~01:05 CDT**; reads ~00:55–01:05 CDT,
two read-only surveyors (read-only fetches and searches; no logins, no
writes).

Summary: **quiet window — zero in-window deltas** across the full
tracked set (no launches, acquisitions, pricing changes, releases, or
partner moves). One piece of adjacent color: a fresh third-party deep
dive on Meta's Muse per-user secure-VM ("Sentinel") security
architecture — about a pre-window launch (Sep 8–9), not a new move —
noted in §2 without a backlog item.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **THIRD-PARTY** = reported by press/third-party
sources. **INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.

## 1. The tracked set — quiet since the 2026-09-21 evening baseline

No in-window change detected across the full tracked set:

- **Microsandbox** — top release still **v0.7.1** (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~00:57).
  Tagged ~Sep 17 (pre-window); v0.7.0 is next in line — no in-window
  release either way.
- **Docker Sandboxes** — release notes still top out at **0.43.0**
  (2026-09-15 block); no 0.44 — the earlier-baseline "0.44 imminent"
  has still not materialized (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~00:58). The
  notes' CVE entries (CVE-2026-77179, CVE-2026-79994, fixed in 0.42.0
  on Sep 7) are page color for pre-window fixes — both CVEs are already
  in the corpus (`docs/COMPETITOR_ANALYSIS.md`).
- **Daytona** — changelog still tops at **SEP 15 2026, v0.214.0**
  (Java SDK build-context uploads, Dockerfile COPY fixes); no
  in-window entries (**VERIFIED**: https://www.daytona.io/changelog,
  ~00:57).
- **E2B** — pricing page unchanged in structure: Hobby free + $100
  one-time credit, Pro $150/mo, per-second billing (**VERIFIED**:
  https://e2b.dev/pricing, ~00:57). Third-party ecosystem notes still
  describe pause/resume as first-class with billing stopped while
  paused — no reported in-window semantic change (C9-era posture
  stands).
- **boat.dev** — rate card re-verified unchanged (**VERIFIED**:
  https://docs.boat.dev/pricing, ~00:57): small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h** ($100+ plan +
  operator capacity allocation), stopped = free, 25 free-hour trial;
  the twelve-provider comparison table holds (E2B/Daytona/Blaxel
  **$0.331/h**, Modal **$0.476/h**, Vercel Sandbox **$0.682/h** — none
  moved).
- **TermSquad** — pricing tiers still $9/$19/$29/$49 (Starter $9 =
  2 vCPU/4GB/40GB; Builder $19 = 4/8/75; Power $29 = 6/12/100; Ultra
  $49 = 8/24/200); no pricing or product change since the Sep 15
  launch coverage (**VERIFIED**: https://termsquad.com/, ~01:00).
- **WSO2 Agent Manager** — no new announcement ahead of the Sep 29
  webinar (C10 trigger unchanged). In-window coverage is syndication of
  the same GA press release plus one Sep 21 Stackademic analysis piece
  adding Forrester/AAIF context (**THIRD-PARTY**: techweez Sep 17,
  systemsdigest/menews247 wires; the analysis adds no product move).
- **Baseten / Blaxel** — Sep 10 acquisition (pre-window); nothing
  in-window beyond rehashes (terms undisclosed, Blaxel keeps operating
  during integration) (**THIRD-PARTY**).
- **OpenAI Agents API sandbox partners** — still nine (Blaxel,
  Cloudflare, Daytona, DigitalOcean, E2B, Modal, Oracle, Runloop,
  Vercel) per third-party writeups verified against the Agents API
  docs as of Sep 11; one blog's 7-item list is that post's own
  omission, not a roster change (**THIRD-PARTY**: official docs not
  re-pulled this pass; C9 stands).
- **FastGPT** — no in-window release or E2B-removal follow-up beyond
  the Sep 14 consolidated guidance (E2B env vars deprecated, mandatory
  migration scripts, cross-origin sandbox deployment recommended)
  (**THIRD-PARTY**).
- **Cloudflare × Cursor** — Sep 2 announcement only; nothing new
  (**THIRD-PARTY**: search surfaces only the original press release
  and syndications).
- **New entrants** — none in the last ~24h across targeted searches
  (general web, HN-angled, Product Hunt-angled, since 2026-09-20).
  Nearby-but-known: **Brig** (Apache 2.0 microVM sandbox for coding
  agents, launched Sep 15; third-party note that Cursor has no
  published profile among its 6 named profiles) and **Epho** (Product
  Hunt ~Sep 7, cloud sandboxes with multi-provider fallback) — both
  pre-window, both already in the corpus.

## 2. Adjacent color — Meta Muse "Sentinel" per-user VM deep dive

A third-party analysis (~5h old at read time) of Meta's Muse personal
agent launch (Sep 8–9, pre-window) goes deep on the per-user secure-VM
"Sentinel" security architecture
(**THIRD-PARTY**: explainx.ai deep dive). This is analysis of a known
launch, not a new product move — no backlog item filed. Its relevance
is adjacent, not actionable: a second vendor (after E2B's pause/billing
posture) building the "one secure VM per agent user" shape that the
hosted product's sentinel half (H5) is designed around. Worth one read
before the next hosted-gap consolidation; not worth a corpus edit on
third-party evidence alone.

## 3. Standing items

- **C18** (h-sandbox watchlist add): **OPEN** — the next corpus
  consolidation pass should evaluate its credential vault +
  host-bound-egress design against the secrets-posture corpus and the
  H4 provider-adapter question.
- **C12** (AgentComputer egress): stands — read this pass, the
  homepage is usage-based pricing + Firecracker on bare metal with no
  public pricing table and no stated network-egress policy; the
  "real product, unverifiable egress posture" negative result is
  unchanged (**UNVERIFIABLE**, and a negative result is a result).
- **C14** (#47 resume-latency target): still **OPEN** — needs a
  measured boat.dev/provider resume baseline; live-API measurement
  awaits the operator per-run spend-cap decision (no movement;
  already in NEEDS_USER.md).
- Carrying forward unchanged: C9 (OpenAI partners), C10 (WSO2 — Sep 29
  webinar is the next trigger), C11 (Baseten–Blaxel integration), C17
  (CLOSED — boat.dev table verified current, xlarge caveat stands as
  current vendor policy).

---

*Corpus note:* per the reach-back policy this pass is delta-only; no
corpus record changed. The two surveyor captures are archived verbatim
in the loop's `agent_notes/` (workspace-only), not the repo.
