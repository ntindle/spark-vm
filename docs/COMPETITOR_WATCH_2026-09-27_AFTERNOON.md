# Competitor watch — 2026-09-27 (afternoon)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the midday pass (#550, merged as `589cf2d`): (A)
fast-mover + pricing re-verification vs the ~07:16 CDT (2026-09-27) baseline
(vendor reads ~07:55–07:56 CDT 2026-09-27), (B) delta news scan ~07:16–07:55
CDT (~39-min delta window; 10 search queries). Read-only, no logins, no
writes. Captures: `agent_notes/surveyor-a-20260927-0754.md`,
`agent_notes/surveyor-b-20260927-0754.md`.

Naming-hygiene note: label rotation continues — `MORNING` → `LATE_MORNING` →
`MIDDAY` → `AFTERNOON` (chains rotate, not stack; the label is a rotation
counter, not a wall-clock claim — this pass ran ~07:55–07:56 CDT). A further
same-day pass rotates again rather than reusing or POST_-stacking.

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: nothing ages out. C62
(OpenAI offline-sandbox escape) drew zero hits this pass — **quiet pass 1**
of 3. Recrawl contact this pass (all quiet counts reset, NOT quiet passes):
C67 (Malaysia + Singapore family coverage; grade stays
FIRST-PARTY-CORROBORATED), C56 (DeepSeek Harness CVE-2026-82533 CSA note),
C29 (Boxd $2M pre-seed — already C29, no re-promotion), C11 (Baseten/Blaxel).
Aged-out items stayed silent this pass (C66, Heapjack/Overpatch, GitLab
CVE-2026-85706, Dextr AI) — silence is irrelevant for already-aged-out
items. Re-fold-path gap still open: no re-fold path for an aged-out item
that resurfaces with real movement (follow-up proposal from the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~07:55–07:56 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks (the all-first-try
streak restarted at the 0424 pass extends to **6 passes**). Every verified
figure matches the ~07:16 CDT baseline on substance. No corpus fold (C32
precedent: nothing changed on a primary source).

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26 2026 /
   V0.218.0** ("KVM sandbox parameter and CLI WorkOS application").
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22**.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646).
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September**; no 26-Sep or 27-Sep entries in any lane.
   (Vercel Drives not re-checked per P49 daily cadence — next due 2026-09-28.)
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro $150/mo, per-second billing tiers intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans).
7. **TermSquad** — $9/$19/$29/$49 tiers, BYO-AI FAQ intact.
8. **DigitalOcean harness-runtime pricing** (canonical URL 200) — all figures
   + 25%-of-allocated active-CPU footnote intact; still no "Last verified"
   stamp; DO snapshot-figure discrepancy unresolved but unmoved.
9. **AgentComputer.ai pricing** — $0.07/CPU-hr, $0.04375/GB-hr, Hot
   $0.000683/Cold $0.000027, still no egress line — C12 stays OPEN.

## Surveyor B — delta news scan: 0 NEW / 14 clean dedupes / 9 flagged-only

**0 NEW.** All 10 queries returned only pre-window events and recrawls of
already-filed items — no new C-numbers, no grade changes. C67 drew recrawl
contact (Malaysia + Singapore family coverage) — NOT a quiet pass; grade
unchanged at FIRST-PARTY-CORROBORATED.

**14 clean dedupes** (all filed, no new facts): Docker Cloud Sandboxes
launch-wave reprints; Daytona $24M and E2B $21M Series A recrawls; TermSquad
Sep-15 launch reprint; Vercel Sandbox Drives write-up; CVE-2026-80521/93603/
77179 recrawls; the Daytona OpenHands PR-wire reprint (previously ruled out
as new); Microsoft Copilot super-app recrawls (filed 09-25); plus the
already-counted C56/C29/C11 recrawl contacts.

**9 flagged-only, NOT folded, no C-numbers:** lane-adjacent items only —
the notable new sightings were LangChain's "Sandboxes for Deep Agents"
(Runloop/Daytona/Modal integrations — framework-level, not infra), a
CodeArts HarmonyOS update, a Google Cloud AI coding plugin, and the OpenAI
GPT-6 Cyber preview rumor. Nothing in-window, in-lane.

Stale-version rule compliant; Surveyor B grepped the last 3 watch docs for
recrawls before classifying — no false first-sightings.

## Verdict

**No new in-window in-lane launches this window; the sandbox-infrastructure
lane stays quiet.** Vendors: 9/9 unchanged; the all-first-try streak reaches
6 passes. News: 0 new, recrawls only. The corpus is steady — carried items
C37, C55, C57, C58 (pricing vendor-verified), C62 (quiet pass 1 of 3),
C67 (FIRST-PARTY-CORROBORATED, recrawl contact); C26 CLOSED; C12 OPEN
(AgentComputer still no egress policy). Aged out (staying out): C66,
Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI.
Re-fold-path gap still open.
