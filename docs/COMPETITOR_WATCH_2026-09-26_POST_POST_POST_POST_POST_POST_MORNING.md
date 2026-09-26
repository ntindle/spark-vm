# Competitor watch — 2026-09-26 (post post post post post post morning)

Two-surveyor pass, delta-only against the post-post-post-post-post-morning
pass (#489, slot 1124, merged as `74a00cf` — this write folds from a live
main, not a sibling race): (A) fast-mover re-verification vs the ~11:3x CDT
baseline (~12:5x CDT), (B) delta news scan ~11:35–12:55 CDT.
Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260926-1254.md`,
`agent_notes/surveyor-b-20260926-1254.md` (under `hidden_files/`).
Suffix `_POST_POST_POST_POST_POST_POST_MORNING` admitted per the `_POST_<slot>`
chain (the 1124 pass took `_POST_POST_POST_POST_POST_MORNING`).

## Surveyor A — fast movers: 4/4 VENDOR-VERIFIED NO-CHANGE

All four vendor fetches succeeded first try — zero fetch failures, zero
UNVERIFIED grades (third all-first-try pass in a row).

1. **Daytona changelog** — newest still **SEP 26 V0.218.0** "KVM sandbox
   parameter and CLI WorkOS application" (verbatim baseline match); SEP 25
   V0.217.0 next.
2. **Docker Sandboxes release notes** — newest dated heading still
   **2026-09-22** ("Improved sandbox moves and support for private kit
   images in cloud sandboxes"); 09-21 below unchanged.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646); next block
   v0.7.1. (Org header still `superradcompany/microsandbox` — rename note
   only, not a delta.)
4. **Vercel changelog (Sandbox lane)** — newest section still the three 25
   September entries (vcr-action/login, Pixel Canary stealth on AI Gateway,
   Sandbox memory observability); nothing dated 26 Sep; 24 Sep below
   unchanged. Drives not re-checked per P49 (daily-morning cadence).

## Surveyor B — delta news scan: 0 new, 7 clean dedupes, 4 flagged-only

Quiet window. All seeds are recrawls of already-filed items — corpus greps
confirm each target is present; no in-window CVEs, launches, or pricing
changes.

Clean dedupes, seed by seed:

1. Gate News recrawl: OpenAI offline-sandbox ~20-queries coverage
   (gateiolink.net) → **C62** — filed facts match verbatim; the DNS-tunnel
   mechanism variant is already the C62 annotation.
2. Tech Times recrawl: DeepSeek DSec escape catalog + Forkast recrawl:
   CVE-2026-82533 DeepSeek Harness sandbox escape → **C56** — the Harness
   CVE is VENDOR-VERIFIED filed (2026-09-25 lead-resolution pass);
   DSec catalog facts match the filed row.
3. RocketNews recrawl: German-wiki agent swarm (3,700 agents / 18,000
   messages; METR internal-board follow-up angle) → **C64**.
4. CyberNewsAI recrawl: CVE-2026-77179 Docker Sandboxes macOS host escape
   (virtio-fs path-resolution flaw, 0.28.0–0.41.9, fixed 0.42.0) → **filed
   (Docker Sandboxes row, 77179/79994 pair)** — no new facts.
5. DeafNews recrawl: "paradox of guardrails" (Sep-25; Pillar "Week of
   Sandbox Escapes" coding-agent pattern, forensic-readiness takeaway) →
   **C62 adjacent commentary note** — commentary, no new incident facts.
6. TheHackerWire recrawl: CVE-2026-100589 OpenClaw (CVE received Sep 26
   03:17; browser-tool sandbox bypass, CWE-863, EPSS 0.32% LOW) → **C66**
   — filed in the 1124 pass; no vendor-primary source yet (stays
   THIRD-PARTY).
7. GlobeNewswire syndication recrawls (marketminute, businessinsurance,
   independent.mk): Docker Cloud Sandboxes Sep-24 announcement → **C45** —
   press recrawls; the announcement itself is out of window.

Flagged only (out of window per reach-back policy):

- Upstash "AI Agent Sandboxes Compared" (9-day-old; 15-provider cost
  table incl. E2B/Daytona/Cloudflare/Vercel/Modal/Runloop pricing) —
  comparison marketing, no launch/news.
- GitHub research docs (vvedantb/eva, marcus-mok-gh/nova-cloud-computer,
  rappdw/sandy, betalyra/effect-uai, gemisis/leviath,
  luthercalvinriggs/research, Data-Advantage/VibeReference; 8–12 days
  old) — sandbox provider comparisons, Daytona-vs-E2B decision notes,
  pricing research; betalyra/effect-uai roadmap re-confirmed as
  plan-not-launch per 1124.
- EponaLab ai-news 2026-W37 (11-day-old; Sep 3–4 agent-infra launch wave
  recap, OpenAI Sep 10–11 Data agent + Agents API public beta) —
  historical recap; the sandbox-integration angle is covered context
  elsewhere.
- marktechpost "Best Agent Sandboxes in 2026" (30 days old) — stale,
  no news.

## Deep-scan evaluation: no in-window development

- **Codex 'Heapjack' + 'Overpatch'** (Accomplish AI, reported
  2026-09-21): no new coverage since the Sep-21 vendor statements. Remain
  queued, NOT filed.
- **GitLab agent-sandbox escape via allowlisted package proxy** (~Sep 19):
  no new facts. Remains queued, NOT filed.
- **C66 (CVE-2026-100589)**: no vendor-primary (OpenClaw release-note /
  advisory) evidence yet — stays THIRD-PARTY.

## Sibling-slot coordination

No live sibling: slot 1224's adoption of #489 merged as `74a00cf` before
this pass started, so the corpus (now running to C66) was folded from a
current main — no interleaving or sequence-gap risk this turn.

## Carried items

C37 (Freestyle fee) / C57 (Baponi) / C58 (Leap0) / C66 (OpenClaw CVE,
grade unchanged) — **no movement**, all remain OPEN, not re-surveyed this
pass. Leap.new stays DATE-UNVERIFIED.

## Tally

- New C-numbers: **0**
- C-number annotations: **0** (all seeds deduped to existing rows)
- Clean dedupes: **7** (+ 4 flagged-only spots)
- Fast movers: **4/4 VERIFIED NO-CHANGE**, zero fetch failures
- In-lane no-launch verdict 2026-09-25: **stands, streak extends**
- Deep-scan: Heapjack/Overpatch + GitLab proxy escape remain
  queued (no in-window developments); C66 stays THIRD-PARTY
- Carried: C37, C57, C58, C66 OPEN, no movement
