# Competitor watch — 2026-09-26 (post post morning)

Two-surveyor pass: (A) fast-mover re-verification vs the ~08:40 CDT
baseline, (B) delta news scan ~08:40–09:2x CDT. Survey window
**2026-09-26 ~09:05–09:19 CDT**; read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-0854.md`,
`agent_notes/surveyor-b-20260926-0854.md` (under
`hidden_files/`).

## Surveyor A — fast movers: 4/4 VENDOR-VERIFIED NO-CHANGE

All four vendor fetches succeeded first try — zero fetch failures,
zero UNVERIFIED grades.

1. **Daytona changelog** — newest still **SEP 26 V0.218.0** "KVM
   sandbox parameter and CLI WorkOS application" (verbatim baseline
   match); SEP 25 V0.217.0 next.
2. **Docker Sandboxes release notes** — newest dated heading still
   **2026-09-22** ("Improved sandbox moves and support for private
   kit images in cloud sandboxes"); 09-21 / 09-15 below unchanged.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646);
   next block v0.7.1. (Org header now shows
   `superradcompany/microsandbox`; redirect works — rename note
   only, not a delta.)
4. **Vercel changelog (Sandbox lane)** — newest entries still the
   three 25 Sep entries; nothing dated 26 Sep. Drives not
   re-checked per P49 (daily-morning cadence).

Surveyor-A spot (flagged only): Docker Cloud Sandboxes launch is
getting a wide syndicated press wave — Surveyor B deduped it to
C45 (WebPRONews piece = C45 pricing + CNCF-commitment filing);
momentum note only.

## Surveyor B — delta news scan: 0 new, 11 clean dedupes

**No new C-numbers.** Nothing in-window qualified: no in-lane
product launch, pricing move, funding round, or GA. The in-lane
no-launch verdict dated 2026-09-25 **stands — the streak extends.**

Clean dedupes, seed by seed:

1. PANews / Zubiqo Sep-26 coverage → **C62** (OpenAI offline-sandbox
   escape; no new facts).
2. BAND × Docker Sandboxes kit → **C45** (already in row).
3. WebPRONews Docker Cloud Sandboxes piece → **C45** (pricing +
   CNCF commitment already filed).
4. GitHub Copilot app opt-in local sandboxing → already filed.
5. DeafNews guardrails commentary → C62 watch notes.
6. DEV "900-Link Trick" / SwarmTraces → filed HF-intrusion row.
7. CVE-2026-82533 → already in corpus.
8. Baseten/Blaxel coverage → **clean dedupe to filed corpus** (see
   sibling note below — the 0754 slot's orphaned "C63" claim was a
   dedupe miss: the acquisition is fully filed in the Blaxel vendor
   row + C11 integration watch + source links).
9. Runloop PRNewswire → stale recrawl.
10. Leap0 → **C58**; Leap.new stays DATE-UNVERIFIED/unfiled (no
    visible dateline).
11. (plus carried-item spot checks, no movement)

## Sibling-slot note (0754 capture dedupe correction)

The 07:54 slot never completed (RUN START present, no completion
entry, branch `strategy/competitor-watch-20260926-0754` has no
commits — likely a dead slot per P40; P38 repair does not apply:
no handoff). Its surveyor-b capture proposed "C63 — Baseten
acquires Blaxel". **Corpus grep: already filed** — Blaxel vendor
row records the Sep-10 acquisition, C11 integration watch exists,
businesswire/baseten-blog/pricing links all present. The claim was
a dedupe miss (its grep covered `agent_notes/` only, not the
corpus doc). Recorded here as a clean dedupe; if the 0754 slot
re-surfaces with C63, it must renumber.

## Carried items

C37 (Freestyle fee) / C57 (Baponi) / C58 (Leap0) — **no movement**,
all remain OPEN, not re-surveyed this pass.

## Deep-scan candidates queued (NOT filed — out of window / adjacent)

- **Codex sandbox escapes 'Heapjack' + 'Overpatch'** (Accomplish AI,
  reported 2026-09-21): zero corpus hits, genuinely new facts, but
  out-of-window and adjacent lane — follows the GitLab-escape
  precedent. Full facts in
  `hidden_files/agent_notes/surveyor-b-20260926-0854.md`.
- GitLab agent-sandbox escape via allowlisted package proxy (~Sep 19)
  — still the standing candidate from earlier passes.

## Tally

- New C-numbers: **0**
- Clean dedupes: **11** (+ 1 corrected sibling dedupe)
- Fast movers: **4/4 VERIFIED NO-CHANGE**, zero fetch failures
- In-lane no-launch verdict 2026-09-25: **stands, streak extends**
- Carried: C37, C57, C58 OPEN, no movement
