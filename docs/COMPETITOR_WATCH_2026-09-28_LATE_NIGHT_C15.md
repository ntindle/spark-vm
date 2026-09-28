# Competitor watch — 2026-09-28 (late night, cycle 15)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads bounded ~02:25–~02:28 CDT 2026-09-28 — see
the provenance correction note below) against the cycle-14
(~01:55–~02:08 CDT) baseline — **8/8 VENDOR-VERIFIED NO-CHANGE,
0 VERIFIED DELTA, 16/17 first-try** (one fetch retry: the
shorthand `gohugoio/security/advisories` 404'd, corrected to
`gohugoio/hugo/security/advisories` and retried successfully — the
all-first-try streak resets this pass). Surveyor B: delta news scan ~02:25–~02:26 CDT (evidence-bounded; capture final write 02:26:04 CDT, 12 queries, snippet level, zero pages
opened) — **quiet pass, 0 NEW with evidence, ~85 clean dedupes, 8
flagged-only, 0 new C-numbers** (tenth straight quiet B-lane night scan,
C6–C15).

Delta-only against the cycle-14 late-night pass
(`docs/COMPETITOR_WATCH_2026-09-28_LATE_NIGHT_C14.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260928-0224.md`,
`agent_notes/surveyor-b-20260928-0224.md` (under `hidden_files`).

> **Timestamp provenance note (CORRECTED):** every verification-time
> claim in this doc is bounded by hard filesystem evidence, not by the
> surveyor's budgeted labels. The surveyor-a capture's final write is
> **02:27:24 CDT** and this pass's first commit is **02:28:22 CDT** —
> the per-area labels the capture wrote ("~02:26–~02:38") were
> *prospective* and impossible, a process defect now logged for the
> next slot's brief (record budgeted timelines as planned, never as
> completed). The evidence-backed A-lane window is therefore
> **~02:25–~02:28 CDT** (dispatch to capture final write). B's scan
> window ~02:26–~02:28 CDT (capture final write 02:26:04 CDT; the
> claimed "02:28 completion" was likewise prospective — bounded to
> ~02:26 CDT). Clock arithmetic below was cross-checked against the
> C14 doc's recorded verdicts, not taken from the captures' narrative.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~02:25–~02:28 CDT)

**8/8 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 16/17 first-try.** Fourth
straight fully-quiet A-lane pass of the nightly series (the first-try
streak resets at 16/17 on the Hugo-URL correction).

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); second entry still SEP 25 / V0.217.0
   ("NVIDIA B300 GPU type"). No V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22**; 2026-09-21 v3-kits entry verbatim unchanged.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**
   (Full Changelog v0.7.2…v0.7.3 at top); no newer tag.
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
   ~02:27 CDT** — not yet met (~21.5h of the expected day remain);
   the A-lane's normal Vercel reads keep re-grading the expectation.
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical; the "Last verified 22 Sep 2026" stamp IS
   present this read. Record note: the docs *index* page shows "Last
   verified 21 Sep 2026" — a different page, explicitly NOT a delta.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~3 days out): allowances verbatim
   Starter **1 TiB** / Team **10 TiB** / Enterprise **100 TiB**;
   overage **$0.04 per GiB**; first bill Nov 1, 2026 — verified on
   Modal's own docs page this pass. Main pricing page spot-check
   unchanged.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, no wording drift anywhere.
   AgentComputer still publishes **no first-party egress pricing
   line — C12 stays OPEN** (15th consecutive first-party read, no
   wording drift).
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; `ycombinator.com/companies/ascii` renders
   the Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. Migration-complete state
   holds; no ASCII-retirement signals.

Standing bar (first-party advisory sweep, cycle-15 check): **Hugo**
— no 100690-specific GHSA on gohugoio/hugo/security/advisories
(listing shows 10 advisories, newest published Sep 9, 2026 —
identical set to C14). Stays out.

Overall: **8/8 NO-CHANGE, 0 DELTA, 16/17 first-try** — the quiet
streak continues (fourth straight fully-quiet A-lane pass).

## Surveyor B — delta news scan (~02:25–~02:26 CDT, evidence-bounded): 0 NEW / ~85 clean dedupes / 8 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Modal $15B / Baseten
$26B talks (C11 — talks still unclosed, no close signal; all hits
2–5-day-old "in talks" coverage); agent-O echo (15th daily cycle —
leak-framed YouTube/forum recrawls, zero OpenAI confirmation);
Plugin4Shell (aiweekly TL;DR explicitly states no CVE assigned at
publication; patch scoreboard unchanged: Claude Code 2.1.179 + Codex
0.146.0 patched, Copilot unpatched, Gemini CLI deprecated without
patch); Mistral Vibe family (third-party scans/guides — no new family
member, no new first-party advisory beyond MAI-2026-003); Hugo
CVE-2026-100690 (aggregator recrawls — third-party only); Vercel
Drives GA (no third-party GA chatter — beta stands); Modal egress
billing Oct-1 (third-party mirror matches first-party terms — no
allowance surprises); FastGPT E2B fallout (old CVE recrawls only —
no fallout content surfaced); NanoClaw/NanoCo (competitor doc +
TechTarget recrawls — no first-party sandbox/compute announcement);
Heapjack/Overpatch (Sep 15–21 disclosure-wave recrawls, all aged-out
— stay out); Daytona catch-all (PR Newswire recrawls; flotilla
landscape doc notes daytona OSS repo abandoned since Jun 2026, last
release v0.190.0 — pre-window color, no in-window launch).

**Flagged-only (NOT folded — numbered verdicts):**
1. **"Agent O" echo — fifteenth daily cycle, still UNCONFIRMED.**
   Zero OpenAI first-party confirmation in any snippet. Not
   C68-candidate; DevDay Tue Sep-29 1pm ET gate stands (only an
   actual OpenAI confirmation files C68).
2. **Plugin4Shell — sh3llc0d3's "CVE-2026-92104" still
   uncorroborated** (zero CVE-db/NVD hits; aiweekly confirms no CVE
   assigned at publication). **Treat it as suspect, not assigned.**
   Re-fold bar unchanged (real CVE assignment, demonstrated
   exploitation, or first-party vendor response). Watch for a real
   CVE assignment.
3. **Hugo CVE-2026-100690 aggregator-only** — third-party only, no
   gohugoio GHSA. Pre-window third-party detail stands: Wiz surfaced
   a Wolfi hugo CVE family (CVE-2026-100691 through 100694, Sep 26)
   alongside 100690 — third-party, not a movement. Flagged-only,
   stays out.
4. **Mistral Vibe family — no movement** (no new family member, no
   new first-party advisory beyond MAI-2026-003, no demonstrated
   agent-infra exploitation). Vibe family stays carried as
   corpus-gap candidacy (93993 parent call stands).
5. **Vercel Sandbox Drives GA — no third-party GA chatter; beta
   stands.** First-party verdict is Surveyor A's lane (no GA as of
   ~02:27 CDT; P49 expectation not yet met).
6. **Modal egress Oct-1 (~3 days out) — third-party mirrors match
   first-party terms** (visible since Sep 1, charged Oct 1, first
   bill Nov 1; Volumes writes don't count; Cloud Bucket Mount
   uploads do); no allowance surprises — re-confirm
   post-effective-date.
7. **C62 OpenAI infra wave — AGED OUT.** No in-window publication
   touching the item this pass → **quiet 3/3, threshold fired.**
   Vendor facts retained as canonical reference; re-fold path stands
   on real movement.
8. **NanoClaw/NanoCo — no new first-party sandbox/compute
   announcement;** recrawls only.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (tenth straight quiet
  B-lane night scan, C6–C15).
- **P63 aging pipeline — one age-out this pass, one file-on-close
  stays armed.**
  - **C11 (Modal/Baseten talks-wave) — still unclosed, no close
    signal this pass** (all hits 2–5-day-old "in talks" coverage).
    Threshold fired at C13; **FILE ON CLOSE regardless of clock state
    stands armed** — the first pass that sees the talks close (or a
    definitive denial) files.
  - **C62 (OpenAI infra wave) AGED OUT** — quiet 3/3 (no in-window
    publication this pass). Vendor facts retained as canonical
    reference; re-fold on real movement.
  - Aged-out stay out: C29 (Boxd), C45 (Docker Cloud Sandboxes
    CVE-family watch — only search-driven recrawls this pass, no
    fresh CVE/launch), C56, C66, C67 (Huawei CodeArts Malaysia —
    re-fold path stands on real movement), C62 (this pass),
    Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI. C26 closed.
  - C12 (AgentComputer) stays OPEN — still no first-party egress
    pricing line (15th consecutive read, no wording drift). No re-folds.
- **P49 (Vercel Drives GA): the 2026-09-28 expectation is NOT met**
  as of ~02:27 CDT. No GA entry on the first-party changelog index,
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
  **C12 (AgentComputer)** — 16th consecutive first-party read next
  pass, note any wording drift; **P49 Drives GA** — not yet met
  (re-graded by the A-lane's normal Vercel reads); Boat legacy
  domains — watch for ASCII-domain retirement or redirect
  flip-flop; Mistral Vibe family — re-fold on a new family member,
  a first-party Mistral advisory, or demonstrated agent-infra
  exploitation; Hugo CVE-2026-100690 — direct
  gohugoio/hugo/security/advisories sweep continues (A-lane, none
  found; use the full URL — the shorthand 404s); FastGPT E2B
  fallout — still no fallout content surfaced; NanoClaw/NanoCo —
  re-grade only on a sandbox/compute first-party announcement;
  aged-out items (C29, C45, C56, C66, C67, C62, Heapjack/Overpatch,
  GitLab CVE-2026-85706, Dextr AI) resurface only on real movement.
- **Process (next slot's brief):** this pass's surveyor timeline
  labels were prospective ("~02:26–~02:38" written while the capture
  finalized at 02:27:24 CDT — see the corrected provenance note).
  Next brief must require timestamps recorded from actual completion,
  never budgeted prospectively, plus a post-write
  mtime-vs-claimed-completion sanity check before the provenance
  note is written.

No new corpus entries; no corpus field-table changes. 0 new C-numbers.
