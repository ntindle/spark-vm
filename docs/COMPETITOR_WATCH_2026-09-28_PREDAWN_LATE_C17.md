# Competitor watch — 2026-09-28 (pre-dawn late, cycle 17)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads bounded ~03:55–~03:57 CDT 2026-09-28 — see the
provenance note below) against the cycle-16 (~02:55–~02:56 CDT) baseline —
**8/8 VENDOR-VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 16/16 first-try**
(sixth straight fully-quiet A-lane pass of the nightly series; zero retries
— 8 browser.search calls for URL discovery, no retries anywhere).
Surveyor B: delta news scan ~03:55:24–~03:56:18 CDT (evidence-bounded; 11
queries, snippet level, zero pages opened) — **quiet pass, 0 NEW with
evidence, 7 clean dedupes, 1 flagged-only, 0 new C-numbers** (twelfth
straight quiet B-lane night scan, C6–C17).

Delta-only against the cycle-16 pre-dawn pass
(`docs/COMPETITOR_WATCH_2026-09-28_PREDAWN_C16.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260928-0354.md`,
`agent_notes/surveyor-b-20260928-0354.md` (under `hidden_files`).

> **Timestamp provenance note:** both surveyor captures were written only
> after their surveys completed; completion evidence is each file's mtime
> (B: 03:56:34 CDT, A: 03:57:22 CDT). **Process defect, caught by the
> adversarial review this pass:** surveyor A's capture recorded a
> prospective "Survey completed: 04:11 CDT" label that postdates its own
> file write (03:57:22 CDT) — the C15 prospective-end-labels defect,
> repeated by the surveyor. The write time, not the label, is the
> completion evidence; every A-lane claim in this doc is bounded to the
> write-time window ~03:55–~03:57 CDT. Surveyor B's capture is internally
> consistent (scan completed ~03:56:18 CDT, file written 03:56:34 CDT).
> All verification claims below are bounded to the A-lane window
> ~03:55–~03:57 CDT and the B-lane scan window ~03:55:24–~03:56:34 CDT
> 2026-09-28.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~03:55–~03:57 CDT)

**8/8 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 16/16 first-try.** Sixth
straight fully-quiet A-lane pass of the nightly series; zero retries.

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
   three entries unchanged; 24 September "Vercel Connect now supports
   TanStack AI" section still present (lane-neutral, C13 record note
   stands); **23 September "Drives for Vercel Sandbox are now in public
   beta" unchanged — no GA entry anywhere on the index**; sandbox docs
   Features list still **"Drives (beta)"** (page last_updated
   2026-09-22). **P49's 2026-09-28 Drives-GA expectation is NOT met as of
   ~03:57 CDT** — not yet met (the expectation's final day is ~17%
   elapsed (~83% of the day still remaining) at read time); the A-lane's
   normal Vercel reads keep re-grading the expectation.
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical; the "Last verified 22 Sep 2026" stamp IS
   present this read. Record note: the docs *index* page shows "Last
   verified 21 Sep 2026" — a different page, explicitly NOT a delta.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~2.5 days out): allowances verbatim
   Starter **1 TiB** / Team **10 TiB** / Enterprise **100 TiB**;
   overage **$0.04 per GiB**; first bill Nov 1, 2026 — verified on
   Modal's own docs page this pass.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, no wording drift anywhere.
   AgentComputer still publishes **no first-party egress pricing
   line — C12 stays OPEN** (17th consecutive first-party read, no
   wording drift).
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; `ycombinator.com/companies/ascii` renders
   the Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. Migration-complete state
   holds; no ASCII-retirement signals.

Standing bar (first-party advisory sweep, cycle-17 check): **Hugo**
— no 100690-specific GHSA on gohugoio/hugo/security/advisories
(listing shows 10 advisories, newest published Sep 9, 2026 —
identical set to C16). Stays out.

Overall: **8/8 NO-CHANGE, 0 DELTA, 16/16 first-try** — the quiet
streak continues (sixth straight fully-quiet A-lane pass).

## Surveyor B — delta news scan (~03:55:24–~03:56:18 CDT, evidence-bounded): 0 NEW / 7 clean dedupes / 1 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Modal $15B / Baseten
$26B talks (C11 — talks still unclosed, no close signal; Sep 23–26
pieces, "have not produced completed rounds" per runtimewire);
agent-O echo (17th daily cycle — TestingCatalog, Medium, wccftech,
YouTube recrawls, zero OpenAI confirmation; explicit "Hypothesis, no
confirmation" wording); Plugin4Shell (aiidelist.com Sep 27: "no public
Plugin4Shell CVE or confirmed in-the-wild exploitation was identified";
securityonline: "No CVE identifiers have been assigned" — sh3llc0d3's
"CVE-2026-92104" remains uncorroborated); Vercel Drives GA
(nandann.com: public beta per Sep 23 — not GA; no third-party GA
chatter — corroborates the A-lane verdict); Modal egress billing Oct-1
(third-party mirror confirms the timeline — visible Sep 1, charged Oct
1, first bill Nov 1, Volumes I/O not egress — pre-window, no allowance
surprises); NanoClaw/NanoCo (no first-party sandbox/compute
announcement — Docker partnership is March, Vercel×OneCLI "NanoClaw
2.0" is agent policy, not sandbox/compute); Hugo CVE-2026-100690
(aggregator-only — TheHackerWire Sep 26, Wiz; sibling CVEs 100691–
100694 also pre-window, no first-party movement). The two catch-all
queries (sandbox launches, agent-infra exploitation) returned only
pre-window items: Docker Cloud Sandboxes Sep 24 coverage, PaperCut
swarm / UNC6780 / SANS ISC / Anthropic abuse disclosures Sep 8–11.

**Flagged-only (NOT folded — numbered verdicts):**
1. **Mistral Vibe — CVE-2026-93993 (worktree git-hook RCE,
   Vibe <2.25.5, CVSS 8.8, US-CERT weekly Sep 14–19).** Published
   ~Sep 19 — **pre-window**. No new family member, no first-party
   Mistral advisory beyond MAI-2026-003, no demonstrated agent-infra
   exploitation. Below the re-fold bar — stays flagged-only, Vibe
   family stays corpus-gap candidacy.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (twelfth straight quiet
  B-lane night scan, C6–C17).
- **P63 aging pipeline — no new age-outs this pass.** No dedicated
  aging queries run; none of the aged-out items showed in-window
  movement in this scan's snippets.
  - **C11 (Modal/Baseten talks-wave) — still unclosed, no close
    signal this pass** (Sep 23–26 "in talks" coverage).
    Threshold fired at C13; **FILE ON CLOSE regardless of clock state
    stands armed** — the first pass that sees the talks close (or a
    definitive denial) files.
  - Aged-out stay out: C29 (Boxd), C45, C56, C66, C67 (Huawei CodeArts
    Malaysia — re-fold path stands on real movement), C62 (OpenAI infra
    wave — aged out at C15; vendor facts retained as canonical
    reference; re-fold on real movement), Heapjack/Overpatch, GitLab
    CVE-2026-85706, Dextr AI. C26 closed.
  - C12 (AgentComputer) stays OPEN — still no first-party egress
    pricing line (17th consecutive read, no wording drift). No re-folds.
- **P49 (Vercel Drives GA): the 2026-09-28 expectation is NOT met**
  as of ~03:57 CDT. No GA entry on the first-party changelog index,
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
  billing effective Oct 1 (~2.5 days out)** — first-party re-confirm
  post-effective-date; **agent-O DevDay confirmation gate Tue Sep-29
  1pm ET** (only an actual OpenAI confirmation files C68);
  **Plugin4Shell** — watch for a REAL CVE assignment (treat
  sh3llc0d3's CVE-2026-92104 as suspect until CVE-db corroborated);
  **Mistral Vibe family** — re-fold on a new family member,
  a first-party Mistral advisory beyond MAI-2026-003, or demonstrated
  agent-infra exploitation (CVE-2026-93993 stays below bar: pre-window);
  **Hugo CVE-2026-100690** — direct gohugoio/hugo/security/advisories
  sweep continues (A-lane; use the full URL — the shorthand 404s);
  **NanoClaw/NanoCo** — re-grade only on a first-party sandbox/compute
  announcement; **P49 Drives GA** — not yet met (the expectation's
  final day is ~17% elapsed at read time; re-graded by the A-lane's
  normal Vercel reads); aged-out items (C29, C45, C56, C66, C67, C62,
  Heapjack/ Overpatch, GitLab CVE-2026-85706, Dextr AI) resurface only
  on real movement.
- **Process (next slot's brief):** the standing process correction is
  now a review gate, not a given — this pass's surveyor A repeated the
  C15 defect (prospective 04:11 CDT completion label, 13+ minutes past
  the actual 03:57:22 CDT file write), and the adversarial review
  caught it. Next slot: do not accept prospective completion labels
  from surveyors — treat each capture file's mtime as completion
  evidence and reject any claimed time later than the mtime. The rule
  holds: surveyor timestamps recorded from actual completion, never
  budgeted prospectively.
