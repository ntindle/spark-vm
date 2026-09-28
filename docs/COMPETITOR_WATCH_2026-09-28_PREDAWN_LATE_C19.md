# Competitor watch — 2026-09-28 (pre-dawn late, cycle 19)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads bounded ~04:55–~04:56 CDT 2026-09-28 — see the
provenance note below) against the cycle-18 (~04:25–~04:26 CDT) baseline —
**8/8 VENDOR-VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 16/16 first-try**
(eighth straight fully-quiet A-lane pass of the nightly series; zero
retries). Surveyor B: delta news scan ~04:55–~04:58 CDT
(evidence-bounded; 12 queries, snippet level, zero pages opened) —
**quiet pass, 0 NEW with evidence, 12 clean dedupes, 2 flagged-only, 0
new C-numbers** (fourteenth straight quiet B-lane night scan, C6–C19).

Delta-only against the cycle-18 pre-dawn-late pass
(`docs/COMPETITOR_WATCH_2026-09-28_PREDAWN_LATE_C18.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260928-0554.md`,
`agent_notes/surveyor-b-20260928-0554.md` (under `hidden_files`).

> **Timestamp provenance note:** both surveyor captures carry no
> prospective completion labels this pass — the C15/C17 defect did NOT
> repeat. Surveyor A completed ~04:56 CDT, file write (mtime) stat-certified
> 04:56:13 CDT; surveyor B's scan window ~04:55–~04:58 CDT matches its
> capture mtime, and its header count (12 dedupes) agrees with the
> enumeration. All verification claims below are bounded to the
> A-lane window ~04:55–~04:56 CDT and the B-lane scan window
> ~04:55–~04:58 CDT 2026-09-28.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~04:55–~04:56 CDT)

**8/8 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 16/16 first-try.** Eighth
straight fully-quiet A-lane pass of the nightly series; zero retries.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); second entry still SEP 25 / V0.217.0 ("NVIDIA B300 GPU
   type"). No V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22**; the 2026-09-21 v3-kits entry verbatim
   unchanged.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**
   ("Full Changelog: v0.7.2…v0.7.3"); no newer tag.
4. **Vercel changelog + Sandbox docs — VERIFIED NO-CHANGE.** Index
   still top section **"27 September"** with the Ember-1 entry (still
   AI-Gateway lane, never Sandbox lane, never folded); 25 September's
   three entries unchanged; 24 September "Vercel Connect now supports
   TanStack AI" still present (lane-neutral); **23 September "Drives
   for Vercel Sandbox are now in public beta" unchanged — no GA entry
   anywhere on the index**; sandbox docs Features list still
   **"Drives (beta)"** (page last_updated 2026-09-22). **P49's
   2026-09-28 Drives-GA expectation is NOT met as of ~04:56 CDT** —
   the expectation's final day is ~20% elapsed at read time; the
   A-lane's normal Vercel reads keep re-grading the expectation.
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical; the "Last verified 22 Sep 2026" stamp IS
   present this read. Record note: the docs *index* page's "Last
   verified 21 Sep 2026" is a different page — explicitly NOT a delta.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~2.8 days out): allowances verbatim
   Starter **1 TiB** / Team **10 TiB** / Enterprise **100 TiB**;
   overage **$0.04 per GiB**; first bill Nov 1, 2026 — verified on
   Modal's own docs page this pass.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, no wording drift anywhere.
   AgentComputer still publishes **no first-party egress pricing
   line — C12 stays OPEN** (19th consecutive first-party read, no
   wording drift).
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; `ycombinator.com/companies/ascii` renders
   the Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. Migration-complete state
   holds; no ASCII-retirement signals.

Standing bar (first-party advisory sweep, cycle-19 check): **Hugo**
— no 100690-specific GHSA on gohugoio/hugo/security/advisories
(listing shows 10 advisories, newest published Sep 9, 2026 —
identical set to C16–C18). Stays out.

Overall: **8/8 NO-CHANGE, 0 DELTA, 16/16 first-try** — the quiet
streak continues (eighth straight fully-quiet A-lane pass).

## Surveyor B — delta news scan (~04:55–~04:58 CDT, evidence-bounded): 0 NEW / 12 clean dedupes / 2 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Modal $15B / Baseten
$26B talks (C11 — talks still unclosed, no close signal; third-party
recaps of the Sep 23 Bloomberg report; FILE ON CLOSE stays armed);
agent-O echo (nineteenth daily cycle — leak/speculation only, zero
OpenAI confirmation; DevDay Tue Sep-29 1pm ET gate stands, only an
actual OpenAI confirmation files C68); OpenAI Sep 20 DNS-escape
disclosure (recaps of the incident disclosed Sep 25–26 — OpenAI's own
incident, not a competitor launch, no C-number; reports note training
still paused); OpenAI–Hugging Face July intrusion commentary
(pre-window recaps, incl. the METR + Redwood independent assessment
published Aug); Mistral Vibe 87984/87985/86/87/88 family (Sep 11
vintage — HiddenLayer advisories, SecMate blog, dependency scans —
no new in-window family member, no first-party advisory beyond
MAI-2026-003, no demonstrated agent-infra exploitation; below the
re-fold bar); Hugo CVE-2026-100690 (aggregator-only — thehackerwire
record received Sep 26, Wiz Wolfi 100690–100694 cluster; no
first-party movement); NanoClaw/NanoCo (recaps only — March Docker
Sandboxes partnership, May $12M seed, Slack announcement; no new
first-party sandbox/compute announcement); Vercel Drives GA — no GA
anywhere, still public beta since Sep 23 (third-party deep-dive only —
corroborates the A-lane verdict); Modal egress billing (third-party
GitHub skill mirror matches baseline exactly — no allowance
surprises); Docker Cloud Sandboxes Sep-24 launch + BAND × Docker
Sandboxes integration (Sep 24 PR Newswire via morningstar +
syndication — ecosystem activity, BAND ships a Python kit/
coordination layer, not a hosted/compute product — below the fold
bar); Daytona/E2B funding pieces (stale — Daytona $24M Series A Feb
2026, E2B $21M Series A Jul 2025; one database claims an unverified
Daytona Series B 2026-07-31, no company announcement — not folded);
AI-inference funding wave (Crusoe $3.9B closed, Island $6.4B,
DeepSeek raise planned, Snorkel $350M — Sep 23–25 vintage, adjacent
lane, not agent-sandbox launches).

**Flagged-only (NOT folded — numbered verdicts):**
1. **Plugin4Shell — still NO real CVE assigned.** shattered.io FAQ
   (updated ~4 days ago): "as of September 23, 2026, no CVE
   identifier has been assigned"; community GitHub advisory file
   tagged `no-cve`; sh3llc0d3's CVE-2026-92104 remains
   uncorroborated, treat as suspect. Not foldable — keep watching.
2. **Mistral Vibe — CVE-2026-93993 (worktree git-hook RCE,
   Vibe <2.25.5, CVSS 8.8, US-CERT weekly Sep 14–19).** Published
   ~Sep 19 — **pre-window**. No new in-window family member, no
   first-party Mistral advisory beyond MAI-2026-003, no demonstrated
   agent-infra exploitation. Below the re-fold bar — stays
   flagged-only, Vibe family stays corpus-gap candidacy.

Note on categorization: Plugin4Shell was a clean dedupe at C18; this
pass's surveyor promoted it to flagged-only item #1 — a ranking
change, not a substance change (still no real CVE). The doc follows
the surveyor's enumeration.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (fourteenth straight quiet
  B-lane night scan, C6–C19).
- **P63 aging pipeline — no new age-outs this pass.** No dedicated
  aging queries run; none of the aged-out items showed in-window
  movement in this scan's snippets.
  - **C11 (Modal/Baseten talks-wave) — still unclosed, no close
    signal this pass.** Threshold fired at C13; **FILE ON CLOSE
    regardless of clock state stands armed** — the first pass that
    sees the talks close (or a definitive denial) files.
  - Aged-out stay out: C29 (Boxd), C45, C56, C66, C67 (Huawei CodeArts
    Malaysia — re-fold path stands on real movement), C62 (OpenAI infra
    wave — aged out at C15; vendor facts retained as canonical
    reference; re-fold on real movement), Heapjack/Overpatch, GitLab
    CVE-2026-85706, Dextr AI. C26 closed.
  - C12 (AgentComputer) stays OPEN — still no first-party egress
    pricing line (19th consecutive read, no wording drift). No re-folds.
- **P49 (Vercel Drives GA): the 2026-09-28 expectation is NOT met**
  as of ~04:56 CDT. No GA entry on the first-party changelog index,
  no third-party GA chatter, sandbox docs still grade "Drives
  (beta)". The A-lane's normal Vercel reads keep re-grading the
  expectation (final day ~20% elapsed at read time).
- **Ember-1 index status: STABLE.** No flip-flop this pass — the
  "27 September" index section carries the entry and the page
  renders live (AI-Gateway lane, never folded). The 24 September
  "Vercel Connect / TanStack AI" section remains lane-neutral.
- Watch-outs for the next surveyor: **C11 file-on-close** — the first
  pass that sees the Modal $15B / Baseten $26B talks close (or a
  definitive denial) files regardless of the clock; **Modal egress
  billing effective Oct 1 (~2.8 days out)** — first-party re-confirm
  post-effective-date; **agent-O DevDay confirmation gate Tue Sep-29
  1pm ET** (only an actual OpenAI confirmation files C68);
  **Plugin4Shell** — watch for a REAL CVE assignment (treat
  sh3llc0d3's CVE-2026-92104 as suspect until CVE-db corroborated);
  **Mistral Vibe family** — re-fold on a new in-window family member,
  a first-party Mistral advisory beyond MAI-2026-003, or demonstrated
  agent-infra exploitation (CVE-2026-93993 stays below bar: pre-window);
  **Hugo CVE-2026-100690** — direct gohugoio/hugo/security/advisories
  sweep continues (A-lane; use the full URL — the shorthand 404s);
  **NanoClaw/NanoCo** — re-grade only on a first-party sandbox/compute
  announcement; **P49 Drives GA** — not yet met (the expectation's
  final day is ~20% elapsed at read time; re-graded by the A-lane's
  normal Vercel reads); **BAND × Docker Sandboxes** — ecosystem
  activity only, re-grade only if BAND ships a hosted/compute product;
  aged-out items (C29, C45, C56, C66, C67, C62, Heapjack/Overpatch,
  GitLab CVE-2026-85706, Dextr AI) resurface only on real movement.
- **Process (next slot's brief):** the standing review gate held this
  pass — neither surveyor wrote prospective completion labels
  (A's 04:56:13 mtime is stat-certified; B's scan window 04:55–04:58
  matches its capture), and B's header count agrees with its
  enumeration. Keep the gate: treat each capture file's mtime as
  completion evidence, reject any claimed time later than the mtime,
  and count surveyor-B dedupes from the enumeration when the header
  count disagrees.
