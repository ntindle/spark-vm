# Competitor watch — 2026-09-28 (late night, cycle 14)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads ~01:55–~02:08 CDT 2026-09-28) against the
cycle-13 (~01:05–~01:06 CDT) baseline — **8/8 VENDOR-VERIFIED
NO-CHANGE, 0 VERIFIED DELTA, 17/17 first-try** (zero fetch failures;
third straight fully-quiet A-lane pass of the nightly series).
Surveyor B: delta news scan over ~01:55–~01:57 CDT (~2-min window,
12 queries, snippet level, zero pages opened) — **quiet pass, 0 NEW
with evidence, ~85 clean dedupes, 8 flagged-only, 0 new C-numbers**
(ninth straight quiet B-lane night scan, C6–C14).

Delta-only against the cycle-13 late-night pass
(`docs/COMPETITOR_WATCH_2026-09-28_LATE_NIGHT_C13.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260928-0154.md`,
`agent_notes/surveyor-b-20260928-0154.md` (under `hidden_files`).

> **Timestamp provenance note:** every verification-time claim in this
> doc is bounded by the surveyors' actual completion times (A: reads
> ~01:55–~02:08 CDT, completion 02:08 CDT; B: scan window
> ~01:55–~01:57 CDT, completion 01:57 CDT) — no claimed read post-dates
> its record. Clock arithmetic below was cross-checked against the
> C13 doc's recorded verdicts, not taken from the captures' narrative.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~01:55–~02:08 CDT)

**8/8 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 17/17 first-try.** Third
straight fully-quiet A-lane pass of the nightly series.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); no V0.219+. Second entry still SEP 25 / V0.217.0
   ("NVIDIA B300 GPU type").
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
   unchanged — no GA entry anywhere on the index**; sandbox docs
   Features list still **"Drives (beta)"** (page last_updated
   2026-09-22). **P49's 2026-09-28 Drives-GA expectation has NOT been
   met as of ~02:02 CDT** — not yet met (~22h of the expected day remain);
   the A-lane's normal Vercel reads keep re-grading the expectation.
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical; the "Last verified 22 Sep 2026" stamp IS
   present this read.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~3 days out): allowances verbatim
   Starter **1 TiB** / Team **10 TiB** / Enterprise **100 TiB**;
   overage **$0.04 per GiB**; first bill Nov 1, 2026. Main pricing
   page spot-check unchanged.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (14th
   consecutive first-party read, no wording drift).
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; `ycombinator.com/companies/ascii` renders
   the Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. Migration-complete state
   holds; no ASCII-retirement signals.

Standing bar (first-party advisory sweep, cycle-14 check): **Hugo**
— no 100690-specific GHSA on gohugoio/security/advisories (listing
shows 10 advisories, newest published Sep 9, 2026 — identical set to
C13). Stays out.

Overall: **8/8 NO-CHANGE, 0 DELTA, 17/17 first-try** — the
all-first-try streak continues (zero fetch failures this pass).

## Surveyor B — delta news scan (~01:55–~01:57 CDT): 0 NEW / ~85 clean dedupes / 8 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Modal $15B / Baseten
$26B talks (C11 — talks still unclosed, no close signal; metirai:
"these are valuations under discussion, not closed rounds");
agent-O echo (14th daily cycle — leak-framed YouTube/forum recrawls,
2 days old, zero OpenAI confirmation); Plugin4Shell (aiweekly TL;DR
explicitly states no CVE assigned at publication; patch scoreboard
unchanged: Claude Code 2.1.179 + Codex 0.146.0 patched, Copilot
unpatched, Gemini CLI deprecated without patch); Mistral Vibe family
(3-day-old GitHub scans/guides — elfrost/ai-patchlab scan,
hrabanazviking plundering guide, superset-sh plans; no new family
member, no new first-party advisory beyond MAI-2026-003); Hugo
CVE-2026-100690 (thehackerwire recrawl, 2 days old — third-party
only); Vercel Drives GA (no third-party GA chatter — beta stands);
Modal egress billing Oct-1 (third-party mirror matches first-party
terms — no allowance surprises); FastGPT E2B fallout (old CVE
recrawls only — no fallout content surfaced); NanoClaw/NanoCo
(recrawls only, no first-party sandbox/compute announcement);
Heapjack/Overpatch (Sep 15–21 disclosure-wave recrawls, all 7 days
old — aged-out stays out); Daytona catch-all (PR Newswire recrawls;
flotilla landscape doc notes daytona OSS repo abandoned since Jun
2026, last release v0.190.0 — pre-window color, no in-window launch).

**Flagged-only (NOT folded — numbered verdicts):**
1. **"Agent O" echo — fourteenth daily cycle, still UNCONFIRMED.**
   Zero OpenAI first-party confirmation in any snippet. Not
   C68-candidate; DevDay Tue Sep-29 1pm ET gate stands (only an
   actual OpenAI confirmation files C68).
2. **Plugin4Shell — sh3llc0d3's "CVE-2026-92104" still
   uncorroborated** (zero CVE-db/NVD hits; aiweekly confirms no CVE
   assigned at publication). **Treat it as suspect, not assigned.**
   Re-fold bar unchanged (real CVE assignment, demonstrated
   exploitation, or first-party vendor response). Watch for a real
   CVE assignment.
3. **Hugo CVE-2026-100690 aggregator-only** (thehackerwire recrawl)
   — third-party only, no gohugoio GHSA. New pre-window third-party
   detail: Wiz surfaced a Wolfi hugo CVE family (CVE-2026-100691
   through 100694, Sep 26) alongside 100690 — third-party, not a
   movement. Flagged-only, stays out.
4. **Mistral Vibe family — no movement** (no new family member, no
   new first-party advisory beyond MAI-2026-003, no demonstrated
   agent-infra exploitation). Vibe family stays carried as
   corpus-gap candidacy (93993 parent call stands).
5. **Vercel Sandbox Drives GA — no third-party GA chatter; beta
   stands.** First-party verdict is Surveyor A's lane (no GA as of
   ~02:02 CDT; P49 expectation not yet met).
6. **Modal egress Oct-1 (~3 days out) — third-party mirrors match
   first-party terms** (visible since Sep 1, charged Oct 1, first
   bill Nov 1; Volumes writes don't count; Cloud Bucket Mount
   uploads do); no allowance surprises — re-confirm post-effective-date.
7. **C62 OpenAI infra wave — CLEAN DEDUPE.** All hits pre-window
   (webpronews Nvidia chief 3 days, DCD GPT-5 GPUs 5 days, older
   partnership pieces) — **no in-window publication → quiet 2/3.**
8. **NanoClaw/NanoCo — no new first-party sandbox/compute
   announcement;** recrawls only.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (ninth straight quiet
  B-lane night scan, C6–C14).
- **P63 aging pipeline — no age-outs this pass, one file-on-close
  stays armed.**
  - **C11 (Modal/Baseten talks-wave) — still unclosed, no close
    signal this pass.** Threshold fired at C13; **FILE ON CLOSE
    regardless of clock state stands armed** — the first pass that
    sees the talks close (or a definitive denial) files.
  - **C62 → quiet 2/3** (no in-window publication touching the item;
    all hits pre-window). One more quiet pass fires the age-out
    threshold.
  - Aged-out stay out: C29 (Boxd), C45 (Docker Cloud Sandboxes
    CVE-family watch — only search-driven recrawls this pass, no
    fresh CVE/launch), C56, C66, C67 (Huawei CodeArts Malaysia —
    aged out at C13; re-fold path stands on real movement),
    Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI. C26 closed.
  - C12 (AgentComputer) stays OPEN — still no first-party egress
    pricing line (14th consecutive read, no wording drift). No re-folds.
- **P49 (Vercel Drives GA): the 2026-09-28 expectation is NOT met** as
  of ~02:02 CDT. No GA entry on the first-party changelog index,
  no third-party GA chatter, sandbox docs still grade "Drives
  (beta)". The A-lane's normal Vercel reads keep re-grading the expectation.
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
  **C12 (AgentComputer)** — 15th consecutive first-party read next
  pass, note any wording drift; **C62 → third consecutive quiet pass
  ages it out**; P49 Drives GA — not yet met (re-graded by the A-lane's
  normal Vercel reads); Boat legacy domains — watch for ASCII-domain
  retirement or redirect flip-flop; Mistral Vibe family — re-fold on
  a new family member, a first-party Mistral advisory, or
  demonstrated agent-infra exploitation; Hugo CVE-2026-100690 —
  direct gohugoio/security/advisories sweep continues (A-lane, none
  found); FastGPT E2B fallout — still no fallout content surfaced;
  NanoClaw/NanoCo — re-grade only on a sandbox/compute first-party
  announcement; aged-out items (C29, C45, C56, C66, C67,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI) resurface
  only on real movement.

No new corpus entries; no corpus field-table changes. 0 new C-numbers.
