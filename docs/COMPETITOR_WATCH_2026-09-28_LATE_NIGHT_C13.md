# Competitor watch — 2026-09-28 (late night, cycle 13)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads ~01:05–~01:06 CDT 2026-09-28) against the
cycle-12 (~00:45–~00:56 CDT) baseline — **8/8 VENDOR-VERIFIED
NO-CHANGE, 0 VERIFIED DELTA, 18/18 first-try** (zero fetch failures;
the all-first-try streak extends to fourteen straight
zero-fetch-failure passes). Surveyor B: delta news scan over
~01:05–~01:30 CDT (~25-min window, 12 queries, snippet level, zero
pages opened) — **quiet pass, 0 NEW with evidence, ~80 clean dedupes,
9 flagged-only, 0 new C-numbers**.

Delta-only against the cycle-12 late-night pass
(`docs/COMPETITOR_WATCH_2026-09-28_LATE_NIGHT_C12.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260928-0054.md`,
`agent_notes/surveyor-b-20260928-0054.md` (under `hidden_files`).

> **Timestamp provenance note:** every verification-time claim in this
> doc is bounded by the surveyors' actual completion times (A: reads
> ~01:05–~01:06 CDT, completion 01:06 CDT; B: scan window
> ~01:05–~01:30 CDT, completion 01:30 CDT) — no claimed read post-dates
> its record. Clock arithmetic below was cross-checked against the
> C12 doc's recorded verdicts, not taken from the captures' narrative.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~01:05–~01:06 CDT)

**8/8 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 18/18 first-try.** Second
straight fully-quiet A-lane pass of the nightly series.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); no V0.219+. Second entry still SEP 25 / V0.217.0.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22**; 2026-09-21 v3-kits entry verbatim unchanged
   below it.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**
   (Full Changelog v0.7.2…v0.7.3 at top); no newer tag.
4. **Vercel changelog + Sandbox docs — VERIFIED NO-CHANGE.** Index
   still top section **"27 September"** with the Ember-1 entry (still
   AI-Gateway lane, never Sandbox lane, never folded); 25 September's
   three entries unchanged; **23 September "Drives for Vercel Sandbox
   are now in public beta" unchanged — no GA entry anywhere on the
   index**; sandbox docs Features list still grades **"Drives (beta)"**.
   **The P49 2026-09-28 Drives-GA expectation has NOT landed as of
   ~01:05 CDT** (the C12 ~00:47 CDT daily re-check satisfied P49's
   daily cadence; this pass's normal lane read re-grades the same
   outcome). Record-accuracy note: a 24 September "Vercel Connect /
   TanStack AI" index section appears that C11/C12 captures never
   called out — lane-neutral (model/connectivity announcement, not
   Sandbox), no verdict impact.
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
   first-party egress pricing line — C12 stays OPEN** (13th
   consecutive first-party read, no wording drift).
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; `ycombinator.com/companies/ascii` renders
   the Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. Migration-complete state
   holds; no ASCII-retirement signals.

Standing bar (first-party advisory sweep, cycle-13 check): **Hugo**
— no 100690-specific GHSA on gohugoio/security/advisories (listing
shows 10 advisories, newest published Sep 9, 2026 — identical set to
C12). Stays out.

Overall: **8/8 NO-CHANGE, 0 DELTA, 18/18 first-try** — the
all-first-try streak extends (zero fetch failures this pass).

## Surveyor B — delta news scan (~01:05–~01:30 CDT): 0 NEW / ~80 clean dedupes / 9 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Modal $15B / Baseten
$26B talks (C11 — talks still unclosed, no close signal); OpenAI
DNS-escape / training pause (C62 — the thejoai UN-GA piece
("OpenAI, Anthropic CEOs Warn UN of AI Risks", ~19:15 CDT Sep-27
update) newly surfaced but same-evening-wave pre-window content as
C12's counted coverage — not an in-window publication, so not a P63
contact); agent-O echo (13th daily cycle — 6+
sources, all third-party rumor/leak, zero OpenAI confirmation);
Plugin4Shell (patch scoreboard unchanged; sh3llc0d3's
"CVE-2026-92104" claim still uncorroborated — zero CVE-db/NVD hits);
Mistral Vibe family (no new family member; see flagged-only #3);
Hugo CVE-2026-100690 (thehackerwire aggregator recrawl — third-party
only); Vercel Drives GA (no third-party GA chatter — beta stands);
Modal egress billing Oct-1 (third-party mirrors match first-party
terms — no allowance surprises); Boat ASCII legacy domains (quiet);
NanoClaw/NanoCo (recrawls only, no first-party sandbox/compute
announcement).

**Flagged-only (NOT folded — numbered verdicts):**
1. **"Agent O" echo — thirteenth daily cycle, still UNCONFIRMED.**
   Zero OpenAI first-party confirmation in any snippet. Not
   C68-candidate; DevDay Tue Sep-29 1pm ET gate stands.
2. **Plugin4Shell — sh3llc0d3's "CVE-2026-92104" still
   uncorroborated** (zero CVE-db/NVD hits; shattered.io +
   neuralcoretech both state no CVE assigned). **Do NOT count it as
   an assigned CVE.** Re-fold bar unchanged (assigned CVE,
   demonstrated exploitation, or first-party vendor response).
   Watch for a real CVE assignment.
3. **Mistral CVE-2026-93993 surfaced via RedPacket US-CERT summary**
   (worktree git-hooks RCE, mistral-vibe <2.25.5, CVSS 8.8, dated Sep
   19) — pre-window publication, third-party only, no first-party
   Mistral advisory beyond MAI-2026-003, no demonstrated
   agent-infra exploitation. New third-party detail on the same
   pre-window disclosure — NOT folded; the Vibe family stays carried
   as corpus-gap candidacy (93993 parent call stands).
4. **Hugo CVE-2026-100690 aggregator-only** (thehackerwire recrawl) —
   third-party only, no gohugoio GHSA. Flagged-only, stays out.
5. **Vercel Sandbox Drives GA — no third-party GA chatter; beta
   stands.** First-party verdict is Surveyor A's lane (no GA as of
   ~01:05 CDT).
6. **Modal egress Oct-1 — third-party mirrors match first-party
   terms** (Oct 1, 1/10/100 TiB, $0.04/GiB); no allowance surprises;
   ~3 days to the effective date — re-confirm post-effective-date.
7. **C62 thejoai UN-GA piece** — "OpenAI, Anthropic CEOs Warn UN of
   AI Risks" (~19:15 CDT Sep-27 update) newly surfaced, but
   same-evening-wave pre-window content as C12's counted coverage —
   not an in-window publication, so not a P63 contact (quiet → 1/3).
8. **Boat ASCII legacy domains — quiet;** migration-complete state
   holds.
9. **NanoClaw/NanoCo — no new first-party sandbox/compute
   announcement;** recrawls only.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (eighth straight quiet
  B-lane night scan, C6–C13).
- **P63 aging pipeline — one age-out this pass, one file-on-close
  armed.**
  - **C67 (Huawei CodeArts Malaysia) AGED OUT** after three
    consecutive quiet passes (contact at C10, 1/3 at C11, quiet 2/3
    at C12, quiet 3/3 this pass — no new publication since the
    Sep-27 republication; recrawls never re-count). Vendor facts
    retained as canonical reference; re-fold path stands on real
    movement (new vendor action, launch, or first-party
    confirmation).
  - **C11 (Modal/Baseten talks-wave) → quiet 3/3 — threshold FIRED.
    FILE ON CLOSE regardless of clock state.** The talks are still
    unclosed this pass (no close signal) — no filing action now, but
    the instruction stands for the pass that sees a close.
  - **C62 → quiet 1/3** (the thejoai UN-GA piece newly surfaced but
    same-evening-wave pre-window content — not an in-window
    publication, so not a P63 contact).
  - Aged-out stay out: C29 (Boxd), C45 (Docker Cloud Sandboxes
    CVE-family watch — only search-driven recrawls this pass, no
    fresh CVE/launch, per the C9 rule it does not resurface), C56,
    C66, Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI,
    **C67 this pass**. C26 closed.
  - C12 (AgentComputer) stays OPEN — still no first-party egress
    pricing line (13th consecutive read). No re-folds.
- **Ember-1 index status: STABLE.** No flip-flop this pass — the
  "27 September" index section carries the entry and the page
  renders live (AI-Gateway lane, never folded). Record-accuracy
  note: the 24 September "Vercel Connect / TanStack AI" section is
  lane-neutral and affects nothing.
- Watch-outs for the next surveyor: **C11 file-on-close** — the first
  pass that sees the Modal $15B / Baseten $26B talks close files
  regardless of the clock; **Modal egress billing effective Oct 1
  (~3 days out)** — first-party re-confirm post-effective-date;
  **agent-O DevDay confirmation gate Tue Sep-29 1pm ET** (fourteenth
  daily cycle; only an actual OpenAI confirmation files C68);
  **Plugin4Shell** — watch for a REAL CVE assignment (treat
  sh3llc0d3's CVE-2026-92104 as suspect until CVE-db corroborated);
  **C12 (AgentComputer)** — 14th consecutive first-party read next
  pass, note any wording drift; **Vercel Sandbox Drives GA expected
  2026-09-28 (today)** — P49's daily re-check was satisfied at C12
  (~00:47 CDT); the A-lane's normal Vercel reads keep re-grading it;
  Boat legacy domains — watch for ASCII-domain retirement or
  redirect flip-flop; Mistral Vibe family — re-fold on a new family
  member, a first-party Mistral advisory, or demonstrated
  agent-infra exploitation; Hugo CVE-2026-100690 — direct
  gohugoio/security/advisories sweep continues (A-lane, none found);
  FastGPT E2B fallout — still no fallout content surfaced;
  NanoClaw/NanoCo — re-grade only on a sandbox/compute first-party
  announcement; aged-out items (C29, C45, C56, C66, C67,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI) resurface
  only on real movement.

No new corpus entries; no corpus field-table changes. 0 new C-numbers.
