# Competitor watch — 2026-09-28 (pre-dawn late, cycle 18)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads bounded ~04:25–~04:26 CDT 2026-09-28 — see the
provenance note below) against the cycle-17 (~03:55–~03:57 CDT) baseline —
**8/8 VENDOR-VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 16/16 first-try**
(seventh straight fully-quiet A-lane pass of the nightly series; zero
retries). Surveyor B: delta news scan ~04:24:10–~04:26:11 CDT
(evidence-bounded; 11 queries, snippet level, zero pages opened) —
**quiet pass, 0 NEW with evidence, 13 clean dedupes, 1 flagged-only, 0
new C-numbers** (thirteenth straight quiet B-lane night scan, C6–C18).

Delta-only against the cycle-17 pre-dawn-late pass
(`docs/COMPETITOR_WATCH_2026-09-28_PREDAWN_LATE_C17.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260928-0424.md`,
`agent_notes/surveyor-b-20260928-0424.md` (under `hidden_files`).

> **Timestamp provenance note:** both surveyor captures carry no
> prospective completion labels this pass — the C15/C17 defect did NOT
> repeat. Surveyor A completed ~04:25 CDT, file write (mtime) 04:25:49
> CDT; surveyor B's scan window ~04:24:10–~04:26:11 CDT matches its mtime
> 04:26:36 CDT. Minor wobble flagged in review: surveyor A's capture
> labels the P49 re-grade "as of ~04:30 CDT", ~4 minutes past its own
> file write — this doc bounds all A-lane claims to the write window
> ~04:25–~04:26 CDT instead. Also flagged: surveyor B's capture header
> claims "11 clean dedupes" but enumerates 13 items — this doc uses the
> enumeration (13). All verification claims below are bounded to the
> A-lane window ~04:25–~04:26 CDT and the B-lane scan window
> ~04:24:10–~04:26:36 CDT 2026-09-28.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~04:25–~04:26 CDT)

**8/8 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 16/16 first-try.** Seventh
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
   TanStack AI" still present (lane-neutral, C13 record note stands);
   **23 September "Drives for Vercel Sandbox are now in public beta"
   unchanged — no GA entry anywhere on the index**; sandbox docs
   Features list still **"Drives (beta)"** (page last_updated
   2026-09-22). **P49's 2026-09-28 Drives-GA expectation is NOT met as
   of ~04:26 CDT** — the expectation's final day is ~17–20% elapsed at
   read time (~83% of the day still remaining); the A-lane's normal
   Vercel reads keep re-grading the expectation.
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical; the "Last verified 22 Sep 2026" stamp IS
   present this read. Record note: the docs *index* page's "Last
   verified 21 Sep 2026" is a different page — explicitly NOT a delta.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~2.5 days out): allowances verbatim
   Starter **1 TiB** / Team **10 TiB** / Enterprise **100 TiB**;
   overage **$0.04 per GiB**; first bill Nov 1, 2026 — verified on
   Modal's own docs page this pass.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, no wording drift anywhere.
   AgentComputer still publishes **no first-party egress pricing
   line — C12 stays OPEN** (18th consecutive first-party read, no
   wording drift).
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; `ycombinator.com/companies/ascii` renders
   the Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. Migration-complete state
   holds; no ASCII-retirement signals.

Standing bar (first-party advisory sweep, cycle-18 check): **Hugo**
— no 100690-specific GHSA on gohugoio/hugo/security/advisories
(listing shows 10 advisories, newest published Sep 9, 2026 —
identical set to C16/C17). Stays out.

Overall: **8/8 NO-CHANGE, 0 DELTA, 16/16 first-try** — the quiet
streak continues (seventh straight fully-quiet A-lane pass).

## Surveyor B — delta news scan (~04:24:10–~04:26:11 CDT, evidence-bounded): 0 NEW / 13 clean dedupes / 1 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Modal $15B / Baseten
$26B talks (C11 — talks still unclosed, no close signal; Sep 23–26
pieces, "have not produced completed rounds" per runtimewire); agent-O
echo (18th daily cycle — TestingCatalog, Medium, YouTube recrawls, zero
OpenAI confirmation; explicit "nothing here is announced"
wording); OpenAI Sep 20 DNS-escape disclosure (pre-window recaps of
the incident disclosed Sep 25–26 — OpenAI's own incident, not a
competitor launch, no C-number); OpenAI–Hugging Face July intrusion
commentary (pre-window recaps); Plugin4Shell (still NO real CVE
assignment — neuralcoretech, shattered.io, securityonline, THN all
concur; sh3llc0d3's CVE-2026-92104 remains uncorroborated, treat as
suspect); Mistral Vibe 8798x family (CVE-2026-87985/86/87/88 — Sep 11–12
vintage, already in corpus, no new first-party Mistral advisory);
Hugo CVE-2026-100690 (aggregator-only — TheHackerWire Sep 26, VulnCheck
~Sep 11 vintage, openCVE Aug 27; no first-party movement); NanoClaw/
NanoCo (no first-party sandbox/compute announcement — recrawls only);
P49 — Vercel Drives GA not met (nandann.com confirms Sep-23 public
beta; no third-party GA chatter — corroborates the A-lane verdict);
Modal egress billing effective Oct-1 (~2.5 days out — third-party
mirrors verbatim: Oct 1 start, Starter 1 TiB / Team 10 TiB /
Enterprise 100 TiB, $0.04/GiB, first bill Nov 1, Volumes I/O excluded —
no allowance surprises); Docker Cloud Sandboxes Sep-24 launch
(recrawls only); Daytona/E2B funding pieces (Feb 2026 / Jul 2025 —
stale, no movement); AI-inference funding wave (Crusoe $3.9B closed,
Island $6.4B, DeepSeek raise planned — Sep 23–25 vintage, adjacent
lane, not agent-sandbox launches). **First-seen-but-pre-window:**
BAND × Docker Sandboxes integration (runtimewire, Sep 26 — multi-agent
coordination layer atop the in-corpus Sep 24 Docker launch; ecosystem
activity, not a new competitor launch — below the fold bar).

**Flagged-only (NOT folded — numbered verdicts):**
1. **Mistral Vibe — CVE-2026-93993 (worktree git-hook RCE,
   Vibe <2.25.5, CVSS 8.8, US-CERT weekly Sep 14–19).** Published
   ~Sep 19 — **pre-window**. No new in-window family member, no
   first-party Mistral advisory beyond MAI-2026-003, no demonstrated
   agent-infra exploitation. Below the re-fold bar — stays
   flagged-only, Vibe family stays corpus-gap candidacy.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (thirteenth straight quiet
  B-lane night scan, C6–C18).
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
    pricing line (18th consecutive read, no wording drift). No re-folds.
- **P49 (Vercel Drives GA): the 2026-09-28 expectation is NOT met**
  as of ~04:26 CDT. No GA entry on the first-party changelog index,
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
  **Mistral Vibe family** — re-fold on a new in-window family member,
  a first-party Mistral advisory beyond MAI-2026-003, or demonstrated
  agent-infra exploitation (CVE-2026-93993 stays below bar: pre-window);
  **Hugo CVE-2026-100690** — direct gohugoio/hugo/security/advisories
  sweep continues (A-lane; use the full URL — the shorthand 404s);
  **NanoClaw/NanoCo** — re-grade only on a first-party sandbox/compute
  announcement; **P49 Drives GA** — not yet met (the expectation's
  final day is ~17–20% elapsed at read time; re-graded by the A-lane's
  normal Vercel reads); **BAND × Docker Sandboxes** — ecosystem
  activity only, re-grade only if BAND ships a hosted/compute product;
  aged-out items (C29, C45, C56, C66, C67, C62, Heapjack/Overpatch,
  GitLab CVE-2026-85706, Dextr AI) resurface only on real movement.
- **Process (next slot's brief):** the standing review gate held this
  pass — surveyor A wrote no prospective completion labels
  (04:25 completion claim vs 04:25:49 mtime: consistent), and the
  ~04:30 P49 label was bounded to the write window in this doc rather
  than repeated. Keep the gate: treat each capture file's mtime as
  completion evidence, reject any claimed time later than the mtime,
  and count surveyor-B dedupes from the enumeration when the header
  count disagrees.
