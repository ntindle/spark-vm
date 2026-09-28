# Competitor watch — 2026-09-28 (pre-dawn, cycle 16)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads bounded ~02:55–~02:56 CDT 2026-09-28 — see the
provenance note below) against the cycle-15 (~02:25–~02:28 CDT) baseline —
**8/8 VENDOR-VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 17/17 first-try**
(fifth straight fully-quiet A-lane pass of the nightly series; the
all-first-try streak resumes after cycle-15's 16/17 reset — the full Hugo
advisory URL was used up front, no 404 this pass). Surveyor B: delta news
scan ~02:55–~02:56 CDT (evidence-bounded; 12 queries, snippet level, zero
pages opened) — **quiet pass, 0 NEW with evidence, ~10 clean dedupes, 6
flagged-only, 0 new C-numbers** (eleventh straight quiet B-lane night
scan, C6–C16).

Delta-only against the cycle-15 late-night pass
(`docs/COMPETITOR_WATCH_2026-09-28_LATE_NIGHT_C15.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260928-0254.md`,
`agent_notes/surveyor-b-20260928-0254.md` (under `hidden_files`).

> **Timestamp provenance note:** both surveyor captures were written only
> after their surveys completed; completion evidence is each file's mtime
> (02:56:32 CDT). Both captures record actual dispatch/start times, never
> prospective end times (the C15 process defect — prospective "end"
> labels — is not repeated this pass). All verification claims below are
> bounded to the A-lane window ~02:55–~02:56 CDT and the B-lane scan
> window ~02:55–~02:56 CDT 2026-09-28.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~02:55–~02:56 CDT)

**8/8 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 17/17 first-try.** Fifth
straight fully-quiet A-lane pass of the nightly series; zero retries — the
full Hugo advisory URL was used on the first attempt.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); second entry still SEP 25 / V0.217.0 ("NVIDIA B300 GPU
   type"). No V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22**; 2026-09-21 v3-kits entry verbatim unchanged.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3** (Full
   Changelog v0.7.2…v0.7.3 at top); no newer tag.
4. **Vercel changelog + Sandbox docs — VERIFIED NO-CHANGE.** Index
   still top section **"27 September"** with the Ember-1 entry (still
   AI-Gateway lane, never Sandbox lane, never folded); 25 September's
   three entries unchanged; 24 September "Vercel Connect / TanStack
   AI" section still present (lane-neutral, C13 record note stands);
   **23 September "Drives for Vercel Sandbox are now in public beta"
   unchanged — no GA entry anywhere on the index** (sitemap check:
   1371 posts, newest dated 2026-09-27); sandbox docs Features list
   still **"Drives (beta)"** (page last_updated 2026-09-22).
   **P49's 2026-09-28 Drives-GA expectation has NOT been met as of
   ~02:56 CDT** — not yet met (~21h of the expected day remain);
   the A-lane's normal Vercel reads keep re-grading the expectation.
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical; the "Last verified 22 Sep 2026" stamp IS
   present this read. Record note: the docs *index* page shows "Last
   verified 21 Sep 2026" — a different page, explicitly NOT a delta.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~3 days out): allowances verbatim
   Starter **1 TiB** / Team **10 TiB** / Enterprise **100 TiB**;
   overage **$0.04 per GiB**; first bill Nov 1, 2026 — verified on
   Modal's own docs page this pass.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, no wording drift anywhere.
   AgentComputer still publishes **no first-party egress pricing
   line — C12 stays OPEN** (16th consecutive first-party read, no
   wording drift).
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; `ycombinator.com/companies/ascii` renders
   the Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. Migration-complete state
   holds; no ASCII-retirement signals.

Standing bar (first-party advisory sweep, cycle-16 check): **Hugo**
— no 100690-specific GHSA on gohugoio/hugo/security/advisories
(listing shows 10 advisories, newest published Sep 9, 2026 —
identical set to C15). Stays out.

Overall: **8/8 NO-CHANGE, 0 DELTA, 17/17 first-try** — the quiet
streak continues (fifth straight fully-quiet A-lane pass).

## Surveyor B — delta news scan (~02:55–~02:56 CDT, evidence-bounded): 0 NEW / ~10 clean dedupes / 6 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Modal $15B / Baseten
$26B talks (C11 — talks still unclosed, no close signal; all hits
2–5-day-old "in talks" coverage); agent-O echo (16th daily cycle —
YouTube DevDay-leak video + forum recrawls, zero OpenAI confirmation);
Plugin4Shell (corroborating sources confirm no CVE assigned at
publication — sh3llc0d3's "CVE-2026-92104" remains uncorroborated);
Mistral Vibe (new third-party detail: SecMate blog on Vibe 2.25.0
permission-bypass SECMATE-2026-0038/0039, remediation all pre-window —
BELOW the re-fold bar); Hugo CVE-2026-100690 (aggregator recrawls —
third-party only); Vercel Drives GA (no third-party GA chatter — beta
stands); Modal egress billing Oct-1 (third-party mirror matches
first-party terms — no allowance surprises); FastGPT E2B fallout (old
CVE recrawls only — no fallout content surfaced); NanoClaw/NanoCo
(see flagged-only below); Heapjack/Overpatch and the rest of the
aged-out set (no in-window movement in this scan's snippets; no
dedicated aging queries run this pass).

**Flagged-only (NOT folded — numbered verdicts):**
1. **"Agent O" echo — sixteenth daily cycle, still UNCONFIRMED.**
   Zero OpenAI first-party confirmation in any snippet. Not
   C68-candidate; DevDay Tue Sep-29 1pm ET gate stands (only an
   actual OpenAI confirmation files C68).
2. **Plugin4Shell — still NO real CVE assigned.** Multiple
   corroborating sources (shattered.io, neuralcoretech,
   securityonline.info, aiweekly) confirm no CVE assigned as of
   publication; sh3llc0d3's "CVE-2026-92104" remains **uncorroborated
   — treat as suspect, not assigned.** Patch scoreboard unchanged:
   Claude Code 2.1.179 + Codex 0.146.0 patched, Copilot unpatched,
   Gemini CLI deprecated without patch. Re-fold bar unchanged (real
   CVE assignment, demonstrated exploitation, or first-party vendor
   response).
3. **Mistral Vibe — new third-party detail, below the re-fold bar.**
   SecMate blog (3 days old): Vibe 2.25.0 permission-bypass +
   arbitrary code execution (SECMATE-2026-0038/0039, CVEs
   CVE-2026-87987 / CVE-2026-87984 per the advisory slug; reported to
   Mistral Sep 5; patched in Vibe 2.25.4 released Sep 12) — all
   pre-window, third-party, CLI-level. Re-fold bar (new family
   member / new first-party Mistral advisory beyond MAI-2026-003 /
   demonstrated agent-infra exploitation) NOT met. Vibe family stays
   carried as corpus-gap candidacy.
4. **Vercel Sandbox Drives GA — no third-party GA chatter; beta
   stands.** First-party verdict is Surveyor A's lane (no GA as of
   ~02:56 CDT; P49 expectation not yet met).
5. **Modal egress Oct-1 (~3 days out) — third-party mirrors match
   first-party terms** (visible since Sep 1, charged Oct 1, first
   bill Nov 1; Volumes writes don't count; Cloud Bucket Mount
   uploads do); no allowance surprises — re-confirm
   post-effective-date.
6. **NanoClaw/NanoCo × Vercel × OneCLI partnership ("NanoClaw
   2.0") — agent policy, NOT sandbox/compute.** Infrastructure-level
   approval dialogs across messaging apps via Vercel Chat SDK +
   OneCLI credentials vault (VentureBeat, crawled <1h). Third-party,
   not a first-party announcement, and not a sandbox/compute move —
   does NOT clear the re-grade bar. Noted only.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (eleventh straight quiet
  B-lane night scan, C6–C16).
- **P63 aging pipeline — no new age-outs this pass.** No dedicated
  aging queries run; none of the aged-out items showed in-window
  movement in this scan's snippets.
  - **C11 (Modal/Baseten talks-wave) — still unclosed, no close
    signal this pass** (all hits 2–5-day-old "in talks" coverage).
    Threshold fired at C13; **FILE ON CLOSE regardless of clock state
    stands armed** — the first pass that sees the talks close (or a
    definitive denial) files.
  - Aged-out stay out: C29 (Boxd), C45, C56, C66, C67 (Huawei CodeArts
    Malaysia — re-fold path stands on real movement), C62 (aged out
    at C15 — vendor facts retained as canonical reference; re-fold on
    real movement), Heapjack/Overpatch, GitLab CVE-2026-85706,
    Dextr AI. C26 closed.
  - C12 (AgentComputer) stays OPEN — still no first-party egress
    pricing line (16th consecutive read, no wording drift). No re-folds.
- **P49 (Vercel Drives GA): the 2026-09-28 expectation is NOT met**
  as of ~02:56 CDT. No GA entry on the first-party changelog index,
  no third-party GA chatter, sandbox docs still grade "Drives
  (beta)". The A-lane's normal Vercel reads keep re-grading the
  expectation.
- **Ember-1 index status: STABLE.** No flip-flop this pass — the
  "27 September" index section carries the entry and the page
  renders live (AI-Gateway lane, never folded). The 24 September
  "Vercel Connect / TanStack AI" section remains lane-neutral.
- Watch-outs for the next surveyor: **C11 file-on-close** — the first
  pass that sees the Modal $15B / Baseten $26B talks close (or a
  definitive denial) files regardless of the clock; **Modal egress
  billing effective Oct 1 (~3 days out)** — first-party re-confirm
  post-effective-date; **agent-O DevDay confirmation gate Tue Sep-29
  1pm ET** (only an actual OpenAI confirmation files C68);
  **Plugin4Shell** — watch for a REAL CVE assignment (treat
  sh3llc0d3's CVE-2026-92104 as suspect until CVE-db corroborated);
  **Mistral Vibe family** — re-fold on a new family member,
  a first-party Mistral advisory beyond MAI-2026-003, or demonstrated
  agent-infra exploitation; **Hugo CVE-2026-100690** — direct
  gohugoio/hugo/security/advisories sweep continues (A-lane; use the
  full URL — the shorthand 404s); **NanoClaw/NanoCo** — re-grade
  only on a first-party sandbox/compute announcement; **P49 Drives
  GA** — not yet met (~21h of Sep 28 CDT remain; re-graded by the
  A-lane's normal Vercel reads); aged-out items (C29, C45, C56,
  C66, C67, C62, Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr
  AI) resurface only on real movement.
- **Process (next slot's brief):** this pass used the C15 process
  correction — captures written only after completion, mtime as
  completion evidence, no prospective timeline labels. The rule
  holds: surveyor timestamps recorded from actual completion, never
  budgeted prospectively.
