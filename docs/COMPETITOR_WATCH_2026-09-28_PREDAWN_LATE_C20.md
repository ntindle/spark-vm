# Competitor watch — 2026-09-28 (pre-dawn late, cycle 20)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads bounded ~05:26 CDT 2026-09-28 — see the
provenance note below) against the cycle-19 (~04:55–~04:56 CDT) baseline —
**8/8 VENDOR-VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 16/16 first-try**
(ninth straight fully-quiet A-lane pass of the nightly series; zero
retries). Surveyor B: delta news scan ~05:25–~05:26 CDT
(evidence-bounded; 12 queries, snippet level, zero pages opened) —
**1 NEW with evidence (CVE-2026-93993 corroborated — folded as C69; a
security CVE, not an in-lane competitor launch), 10 clean dedupes, 1
flagged-only, 0 NEW in-lane** (fifteenth straight quiet B-lane night scan,
C6–C20).

Delta-only against the cycle-19 pre-dawn-late pass
(`docs/COMPETITOR_WATCH_2026-09-28_PREDAWN_LATE_C19.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260928-0524.md`,
`agent_notes/surveyor-b-20260928-0524.md` (under `hidden_files`).

> **Timestamp provenance note:** both surveyor captures carry no
> prospective completion labels this pass — the C15/C17 defect did NOT
> repeat. Surveyor A completed by ~05:26 CDT, file write (mtime)
> stat-certified 05:26:10 CDT; surveyor B's scan window ~05:25–~05:26 CDT
> matches its capture mtime, and its header count (1 NEW / 10 dedupes /
> 1 flagged-only) agrees with its enumeration. All verification claims
> below are bounded to the A-lane window ~05:26 CDT and the B-lane scan
> window ~05:25–~05:26 CDT 2026-09-28.
>
> **Integrator correction (timestamp honesty):** surveyor A's capture
> claims "Expectation window now closed; P49 fails." That claim is NOT
> adopted — at ~05:26 CDT the expectation's final day is only ~23%
> elapsed, so the window is NOT closed. P49 is re-graded below as "NOT
> met as of read time," and the final grade lands on a later in-window
> cycle today (strategy slots run hourly at :24 CDT). Do not cite this
> watch as having declared P49 failed.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~05:26 CDT)

**8/8 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 16/16 first-try.** Ninth
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
   2026-09-28 Drives-GA expectation is NOT met as of ~05:26 CDT** —
   the expectation's final day is ~23% elapsed at read time; the
   A-lane's normal Vercel reads keep re-grading the expectation, and
   the final grade lands on a later in-window cycle today.
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical; the "Last verified 22 Sep 2026" stamp IS
   present this read. Record note: the docs *index* page's "Last
   verified 21 Sep 2026" is a different page — explicitly NOT a delta.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~2.8 days out): allowances verbatim
   Starter **1 TiB** / Team **10 TiB** / Enterprise **100 TiB**;
   overage **$0.04 per GiB**; first bill Nov 1, 2026 — verified on
   Modal's own docs page this pass. No "went live early" chatter in
   either lane; post-effective-date re-confirm stays armed.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, no wording drift anywhere.
   AgentComputer still publishes **no first-party egress pricing
   line — C12 stays OPEN** (20th consecutive first-party read, no
   wording drift).
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; `ycombinator.com/companies/ascii` renders
   the Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. Migration-complete state
   holds; no ASCII-retirement signals.

Standing bar (first-party advisory sweep, cycle-20 check): **Hugo**
— no 100690-specific GHSA on gohugoio/hugo/security/advisories
(listing shows 10 advisories, newest published Sep 9, 2026).
**Counting correction:** the C19 doc said "4 that day" for Sep 9; this
pass's full enumeration shows 5 (5 Sep-9 + 2 Aug-27 + 3 Jun-18 = 10).
The total is unchanged at 10 — this is a **C19 miscount correction,
not a delta**. Newest title verbatim: "Arbitrary file read via
symlinks bypassing the Node.js permission model in css.PostCSS and
other Node.js tools" (GHSA-x3mx-cm49-8m9c). Stays out.

Overall: **8/8 NO-CHANGE, 0 DELTA, 16/16 first-try** — the quiet
streak continues (ninth straight fully-quiet A-lane pass).

## Surveyor B — delta news scan (~05:25–~05:26 CDT, evidence-bounded): 1 NEW / 10 clean dedupes / 1 flagged-only

**NEW with evidence (1 — folded):**

1. **C69 — Mistral Vibe CVE-2026-93993: folded.** Worktree-creation
   git-hook RCE in Mistral Vibe <2.25.5, CVSS 8.8 HIGH. Corroborated
   this cycle by two independent sources: donge/aisec daily 2026-09-23
   (third-party AI-security daily, links the NVD record) and the
   **first-party** mistral-vibe CHANGELOG (HEAD, updated ~4 days ago):
   "Creating or cleaning up a worktree no longer runs the repository's
   own git hooks (such as post-checkout) or its fsmonitor command" —
   the fix line matches the CVE's described behavior exactly.
   **Why now:** cycles C16–C19 carried 93993 as flagged-only /
   corpus-gap candidacy for lack of corroboration (the US-CERT weekly
   mention was third-party only). Corroboration is now present —
   including vendor-acknowledged fix text — so it folds. **Bar
   transparency:** the CVE itself is pre-window (~Sep 19); this fold
   rests on the corroboration criterion (first-party fix text), not
   the in-window criterion. The CVE number is the corpus's stable key.
   Post-93993 re-fold bar for the Vibe family: additional new family
   members, a first-party Mistral advisory beyond MAI-2026-003, or
   demonstrated agent-infra exploitation. (The surveyor's capture
   reads "0 new C-numbers" — superseded: the surveyor deferred the
   minting to the integrator, and this doc mints C69.)

**Clean dedupes (pre-window, re-queried — 10, header count agrees):**
Modal $15B / Baseten $26B talks (C11 — talks still unclosed, no close
signal; third-party recaps of the Sep 23 Bloomberg report; techflier's
recap repeats Modal's self-reported Sandboxes metrics — third-party
recap, not new evidence; FILE ON CLOSE stays armed); agent-O echo
(twentieth daily cycle — leak/speculation only, zero OpenAI
confirmation; the ai.joaoqueiros evidence ladder confirms DevDay
Sep-29 and some product details but the agent-O core claims stay
UNCONFIRMED; DevDay Tue Sep-29 1pm ET gate stands — only an actual
OpenAI confirmation files C68; the C68 reservation stands); Mistral
Vibe 87984/87985/86/87/88 cluster (Sep 11 vintage — HiddenLayer
advisories, SecMate blog, Tenable page — no new member of THIS
cluster, no first-party advisory beyond MAI-2026-003, no demonstrated
agent-infra exploitation; below the re-fold bar); Hugo CVE-2026-100690
(aggregator-only — thehackerwire record received Sep 26 with exploit
status NONE; Wiz/Wolfi-adjacent cluster results; VulnCheck/OpenCVE
entries for OTHER Hugo CVEs; no 100690-specific GHSA; A-lane re-sweeps
the advisory page directly — stays out); Modal egress billing
(third-party GitHub skill mirror matches baseline exactly — Starter
1 TiB / Team 10 TiB / Enterprise 100 TiB, $0.04/GiB, effective Oct 1,
first bill Nov 1; no "went live early" chatter — standing); Daytona/
E2B funding (stale — Daytona $24M Series A Feb 2026, E2B $21M Series A
Jul 2025; AlleyWatch cites $86.3M aggregate for Daytona; forge's
Daytona Series B 2026-07-31 claim remains database-only, no company
announcement — not folded); Vercel Drives GA — no GA anywhere, still
public beta since Sep 23 (third-party deep-dive only — corroborates
the A-lane verdict); NanoClaw/NanoCo (recaps only — March Docker
Sandboxes partnership, May $12M seed; VentureBeat piece on NanoClaw
2.0 + NanoCo × Vercel × OneCLI partnership for a standardized approval
system — an approval/credentials coordination play, NOT a
sandbox/compute announcement — below the re-grade bar); Docker Cloud
Sandboxes Sep-24 launch + BAND × Docker Sandboxes integration (Sep 24
PR Newswire via morningstar + syndication — ecosystem activity; BAND
ships a Python kit/coordination layer, not a hosted/compute product —
below the fold bar); E2B sandbox news scan (lane-quiet — no new E2B
vendor launch; Encore × E2B Sep-15 blog, FastGPT v4.16.0 E2B
deprecation Sep-14, OpenAI Agents API Sep-11 — all pre-window
context).

**Flagged-only (NOT folded — numbered verdicts):**
1. **Plugin4Shell — still NO real CVE assigned.** shattered.io FAQ
   (updated ~4 days ago): "As of September 23, 2026, no CVE
   identifier has been assigned"; securityonline.info, neuralwired,
   deafnews concur. The purported "CVE-2026-92104" did NOT surface in
   this cycle's snippets at all — stays suspect, uncorroborated.
   Not foldable — keep watching.

**Not re-queried this cycle (carried as standing, NOT asserted as
re-verified):** OpenAI Sep 20 DNS-escape recaps, OpenAI–Hugging Face
July intrusion commentary, AI-inference funding wave. No in-window
movement was asserted for these items; the next surveyor re-checks.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (fifteenth straight quiet
  B-lane night scan, C6–C20). The C69 fold is a corroborated security
  CVE in an adjacent lane, not an in-lane competitor launch.
- **Corpus movement (P63): C69 minted** — Mistral Vibe CVE-2026-93993
  folded (see above). Prior calls superseded: cycles C16–C19
  corpus-gap candidacy / flagged-only.
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
    pricing line (20th consecutive read, no wording drift). No re-folds.
- **P49 (Vercel Drives GA): the 2026-09-28 expectation is NOT met**
  as of ~05:26 CDT. No GA entry on the first-party changelog index,
  no third-party GA chatter, sandbox docs still grade "Drives
  (beta)". The A-lane's normal Vercel reads keep re-grading the
  expectation (final day ~23% elapsed at read time); **the final
  grade lands on a later in-window cycle today — this watch does NOT
  declare the expectation failed.**
- **Ember-1 index status: STABLE.** No flip-flop this pass — the
  "27 September" index section carries the entry and the page
  renders live (AI-Gateway lane, never folded). The 24 September
  "Vercel Connect / TanStack AI" section remains lane-neutral.
- Watch-outs for the next surveyor: **C11 file-on-close** — the first
  pass that sees the Modal $15B / Baseten $26B talks close (or a
  definitive denial) files regardless of the clock; **Modal egress
  billing effective Oct 1 (~2.8 days out)** — first-party re-confirm
  post-effective-date (no "went live early" chatter this cycle);
  **agent-O DevDay confirmation gate Tue Sep-29 1pm ET** (only an
  actual OpenAI confirmation files C68 — the C68 reservation stands);
  **Plugin4Shell** — watch for a REAL CVE assignment (treat
  "CVE-2026-92104" as suspect until CVE-db corroborated — it did not
  surface at all this cycle); **Mistral Vibe family** — re-fold on an
  additional new family member, a first-party Mistral advisory beyond
  MAI-2026-003, or demonstrated agent-infra exploitation (the
  87984–88 cluster stays below bar); **Hugo CVE-2026-100690** —
  direct gohugoio/hugo/security/advisories sweep continues (A-lane;
  use the full URL — the shorthand 404s); **NanoClaw/NanoCo** —
  re-grade only on a first-party sandbox/compute announcement (the
  Vercel/OneCLI approval partnership does not meet it); **P49 Drives
  GA** — final grade pending EOD 2026-09-28 (re-graded by the A-lane's
  normal Vercel reads; later in-window cycles today carry it);
  **BAND × Docker Sandboxes** — ecosystem activity only, re-grade
  only if BAND ships a hosted/compute product; **C69** — new corpus
  entry, no follow-up needed unless new Vibe movement surfaces;
  aged-out items (C29, C45, C56, C66, C67, C62, Heapjack/Overpatch,
  GitLab CVE-2026-85706, Dextr AI) resurface only on real movement.
- **Process (next slot's brief):** the standing review gate held this
  pass — neither surveyor wrote prospective completion labels
  (A's 05:26:10 mtime is stat-certified; B's header count agrees with
  its enumeration). New lesson: surveyor A's capture carried a
  premature "window closed; P49 fails" claim — the integrator
  rejected it (final day only ~23% elapsed at read time) and recorded
  the correction in the provenance note above. Keep the gate: treat
  each capture file's mtime as completion evidence, reject any claimed
  time later than the mtime, count surveyor-B dedupes from the
  enumeration when the header count disagrees, and never declare an
  expectation dead before its window closes.
