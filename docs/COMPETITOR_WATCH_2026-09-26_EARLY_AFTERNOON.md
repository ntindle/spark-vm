# Competitor watch — 2026-09-26 (early afternoon)

Two-surveyor pass, delta-only against the post-post-post-post-post-post-morning
pass (#490, slot 1254, merged as `e882516` — this write folds from a live
main, not a sibling race): (A) fast-mover re-verification vs the ~12:5x CDT
baseline (~13:57 CDT), (B) delta news scan ~12:55–13:55 CDT.
Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260926-1354.md`,
`agent_notes/surveyor-b-20260926-1354.md` (under `hidden_files/`).
Suffix `_EARLY_AFTERNOON` admitted per the 2026-09-24 early-afternoon-pass
precedent (corpus conventions) — the day's runaway `_POST_<slot>` chain
(seven POSTs deep) retires here; 13:5x CDT is genuinely early afternoon.

## Surveyor A — fast movers: 4/4 VENDOR-VERIFIED NO-CHANGE

All four vendor fetches succeeded first try — zero fetch failures, zero
UNVERIFIED grades (fourth all-first-try pass in a row).

1. **Daytona changelog** — newest still **SEP 26 V0.218.0** "KVM sandbox
   parameter and CLI WorkOS application" (verbatim baseline match); SEP 25
   V0.217.0 "NVIDIA B300 GPU type" next, unchanged.
2. **Docker Sandboxes release notes** — newest dated heading still
   **2026-09-22** ("Improved sandbox moves and support for private kit
   images in cloud sandboxes"); 09-21 entry unchanged.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646); next block
   v0.7.1. (Org header still `superradcompany/microsandbox` — rename note
   only, not a delta.)
4. **Vercel changelog (Sandbox lane)** — newest section still the three 25
   September entries (vcr-action/login, Pixel Canary stealth on AI Gateway,
   Sandbox memory observability); nothing dated 26 Sep; 24 Sep below
   unchanged. Drives not re-checked per P49 (daily-morning cadence).

## Surveyor B — delta news scan: 0 new, 4 clean dedupes, 6 flagged-only

Quiet window. No in-window, in-lane launches or CVEs. Five targeted
searches; every corpus-absent candidate failed the window or lane bar.

Clean dedupes, seed by seed:

1. Docker Cloud Sandboxes press recrawls (docker.com, b2b-asianews,
   financialcontent; launch Sep 24) → **C45** — announcement out of
   window; no new facts.
2. DeepSeek Harness CVE-2026-82533 recrawls (CSA lab note, Denny Sentinel
   piece, ORCA ai-incident-archive page; bubblewrap/Seatbelt detail adds
   color, no new CVE facts) → **C56**.
3. thecybersecguru Docker Sandboxes CVE-2026-77179 / CVE-2026-79994
   recrawl → **filed (Docker Sandboxes row, 77179/79994 pair)** — no new
   facts.
4. SiliconANGLE Perplexity SPACE launch piece (July 15, 2026 vintage) →
   **C54 context** — the red-team substance is filed; the launch snippet
   is stale.

Flagged only (out of window or out of lane per reach-back policy):

- **vm2 CVE-2026-93605** — strongest flag this pass, new to corpus (zero
  corpus hits): NodeVM sandbox escape (CVE received Sep 18, 2026;
  `DANGEROUS_BUILTINS` denylist omits `child_process` despite blocking
  other host-spawning modules; `require('child_process')` → arbitrary host
  commands when NodeVM configured with `builtin:['*']`; EPSS 0.73% LOW).
  Flagged only: (a) out of survey window (Sep 18); (b) marginal lane —
  the corpus precedent for the earlier vm2 escape (CVE-2026-26956) was
  "marginal lane… deliberately not filed" (in-process JS sandbox, not an
  agent-VM). Facts captured in the surveyor-B capture for a future
  review, not filed.
- Jenkins Script Security CVE-2026-92122 cluster (advisory Sep 16; 6
  sandbox-bypass + 2 classpath-approval flaws) — CI-plugin Groovy
  sandbox, out of agent-VM lane; out of window.
- CVE-2026-85880 AppContainer sandbox escape (Microsoft Sep-9 Patch
  Tuesday record) — general-OS sandbox, out of lane and window.
- tokencost.app "OpenAI Agents API Pricing: The Sandbox Is the Fee" (13
  days old) — comparison marketing, no vendor pricing change; out of
  window.
- GitHub research docs (marcus-mok-gh daytona-vs-e2b, pioneeraiacademy
  provider-spec table; sampraszheng wiki "Daytona closed-sourced June
  2026" matches standing corpus/MEMORY) — research docs, not news; out
  of window.
- Codex Heapjack/Overpatch coverage search — all coverage Sep 20–22
  vintage, facts unchanged → remain queued, NOT filed.

## Deep-scan evaluation: no in-window development

- **Codex 'Heapjack' + 'Overpatch'** (Accomplish AI, reported
  2026-09-21): no new coverage. Remain queued, NOT filed.
- **GitLab agent-sandbox escape via allowlisted package proxy** (~Sep 19):
  no new coverage this pass. Remains queued, NOT filed.
- **C66 (CVE-2026-100589)**: no vendor-primary (OpenClaw release-note /
  advisory) evidence yet — stays THIRD-PARTY.

## Sibling-slot coordination

Live sibling slot 20260926-1329 (build arch) pushed
`hourly/cua-arch-20260926-1329` at ~13:4x CDT; no main movement at this
pass's fold time (main still `e882516`). No live merge-queue claim within
60 min at RUN START; merge-time re-check per P23.

## Carried items

C37 (Freestyle fee) / C57 (Baponi) / C58 (Leap0) / C66 (OpenClaw CVE,
grade unchanged) — **no movement**, all remain OPEN, not re-surveyed this
pass. Leap.new stays DATE-UNVERIFIED. vm2 CVE-2026-93605 carried as a
flagged-only capture (window + lane fail).

## Tally

- New C-numbers: **0**
- C-number annotations: **0** (all seeds deduped to existing rows)
- Clean dedupes: **4** (+ 6 flagged-only spots)
- Fast movers: **4/4 VERIFIED NO-CHANGE**, zero fetch failures
- In-lane no-launch verdict 2026-09-25: **stands, streak extends**
- Deep-scan: Heapjack/Overpatch + GitLab proxy escape remain
  queued (no in-window developments); C66 stays THIRD-PARTY
- Carried: C37, C57, C58, C66 OPEN, no movement
