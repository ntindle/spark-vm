# Competitor watch — 2026-09-29 (early-morning, cycle 54)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
against the cycle-53 baseline — **17 VERIFIED NO-CHANGE, 0 VERIFIED
DELTA, 0 UNVERIFIED** (18 first-try browser.open successes, 0 retries,
0 failures, 0 searches; 17 enumerated items plus one standing
re-carry). Surveyor B: delta news scan (snippet level, zero pages
opened) — **0 CANDIDATES, 14 clean dedupes, 5 flagged-only**
(forty-ninth straight quiet B-lane scan, C6–C54). **Fully quiet
cycle — no first-party deltas at all.** Captures:
`hidden_files/agent_notes/surveyor-a-20260929-0724.md`,
`hidden_files/agent_notes/surveyor-b-20260929-0724.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, ~07:27–07:28 CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (17
> VERIFIED NO-CHANGE, 0 DELTA, 0 UNVERIFIED) reconciles exactly with
> its enumeration (items 1, 2, 3, 4a–4c, 5, 6, 7a–7d, 8a–8d, 9 plus
> the standing re-carry (a)) and its fetch stats (18 successes, 0
> retries, 0 failures). Surveyor B's header (0 CANDIDATES / 14 clean
> dedupes / 5 flagged-only) agrees with its 14 dedupe and 5 flagged
> enumerations and its 16 browser_search calls, 0 pages opened.
> (C53's self-report discrepancy does not recur.)
>
> **Integrator fold-gate:** no genuine first-party delta this cycle —
> **no fold**, no mints, no re-folds, no age-out movement. The A-lane
> went fully delta-free again (equally delta-free first-party passes
> in C41–C43 and C45–C54).

Delta-only against the cycle-53 early pass (PR #689's
`docs/COMPETITOR_WATCH_2026-09-29_EARLY_C53.md`). Read-only, no
logins, no writes.

## Surveyor A — first-party vendor re-verification (mtime-bounded)

**17 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still SEP 26
   2026 / V0.218.0 ("KVM sandbox parameter and CLI WorkOS
   application"); then SEP 25 2026 / V0.217.0 ("NVIDIA B300 GPU
   type"); then SEP 24 2026 / V0.216.1 ("API key organization ID and
   CLI update warning fix"); then SEP 24 2026 / V0.216.2 ("CLI login
   through WorkOS"). No V0.219+ on the page.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out 2026-09-22 ("Improved sandbox moves and support for private kit
   images in cloud sandboxes"); the 2026-09-21 v3-kits entry verbatim
   unchanged, followed by the 2026-09-15 entry.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Top release still
   v0.7.4 with its full body intact (Features #1455/#1667; Fixes
   #1653/#1456/#1666/#1668; CI #1659; Maintenance #1652 + #1665);
   v0.7.3 still second. No v0.7.5+ on the page.
4. **Vercel (changelog index, Sandbox docs, Drives page — ALL
   NO-CHANGE).**
   a. **Changelog index — VERIFIED NO-CHANGE.** The "28 September"
      section still carries the baseline's 3 entries in the same order:
      "Search domains without authentication" first, then "Claude
      Sonnet 5.5 now available on AI Gateway", then "Vercel Sandbox
      now supports memory observability". No Drives GA entry anywhere
      in the rendered window (24, 25, 27, 28 September).
      **Drives GA is a standing tracked item (no in-cycle grading).**
      Not declared dead: Vercel has not cancelled Drives GA; the
      first-party surfaces simply still show beta/private-beta. No GA
      language on this read — no mint triggered.
   b. **Sandbox docs Features list — VERIFIED NO-CHANGE.** Still
      `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
      Features list. Render nuance (color, not a verdict change): the
      fetched text's related-page cross-link chrome includes a "Run
      untrusted code with Vercel Sandbox, now generally available"
      related link — page chrome about the Sandbox product itself,
      not a tracked-field change; all tracked fields match verbatim.
   c. **Drives Private Beta changelog page — VERIFIED NO-CHANGE.**
      Title still "Drives for Vercel Sandbox in Private Beta";
      private-beta SDK/CLI; waitlist still live; no GA language — no
      mint candidate triggered.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact. No change to the five
   baseline figures.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start (2 calendar days after the 2026-09-29 survey, stated as
   arithmetic — the intervening calendar day is 2026-09-30, never as
   "tomorrow"); Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB;
   overage $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals.
   **Re-confirm post-effective-date** with first-party reads only.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (7a–7d).** All verbatim identical, zero wording drift. AgentComputer
   still publishes **no first-party egress pricing line — C12 stays
   OPEN** (54th consecutive first-party read).
8. **Boat legacy domains — VERIFIED NO-CHANGE (8a–8d, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively.
9. **Hugo advisories — VERIFIED NO-CHANGE.** 4 Sep-28 Moderate
   advisories top the list (GHSA-3jfr-vjcq-7jvf, GHSA-r4xx-89rf-5424,
   GHSA-6c8w-mpp8-9w47, GHSA-wcpj-vcvm-j4pg); 5 Sep-9 + 1 Aug-27
   below; render capped at exactly 10; no "100690" anywhere. The CVE
   record appears only on third-party aggregators — below the
   file-on-GHSA-only gate.

**EXTRA (a) — re-carry only, excluded from header totals.** The
DigitalOcean limits page still carries the stamp "Last verified 21 Sep
2026" and verbatim "You can run up to 100 sessions at once per team
depending on your tier."

## Surveyor B — delta news scan (snippet level, mtime-bounded)

**0 CANDIDATES, 14 clean dedupes, 5 flagged-only.** Forty-ninth
straight quiet B-lane scan (C6–C54). Nothing in-window meets any
filing or promotion gate.

Clean dedupes (14): Daytona (syndication only); E2B (no launch/GA/
pricing); Modal funding (still "nearing/closing in on/nearing/
approaching/negotiating/on the verge of/close to finalising" language
across the full syndication tree of the 2026-09-28 $750M piece,
below C11's FILE-ON-CLOSE gate); Baseten ~$26B (still "nearing/in
talks/discussing/seeking" language — bytevyte still on the record
that neither round has closed — below gate); Vercel Drives (Sept-23
public beta recirculation, first-party SDK support stays beta-
labeled; the memory-observability changelog entry is a Sandbox
feature, not Drives GA); DigitalOcean Managed Agents (Sept-21/22
preview + third-party corroboration only; comparison pieces name
only pre-window items — AWS AgentCore V2, Microsoft Foundry GA
(July), Google Agent Runtime rename, Cloudflare Containers GA
(April) — none new); Docker Sandboxes (Sept-24 Cloud Sandboxes
launch + syndication; The Register's pricing detail ($0.07/hr Micro
through $1.12/hr XL) is a garnish on the same announcement); TermSquad
(no in-window mention — only Sept-15 launch syndication);
boat.dev / AgentComputer (search noise + repo's own corpus restating
the pre-window baselines; AgentComputer egress pricing still
absent per the A-lane first-party read); Microsandbox (no v0.7.5
evidence in snippets; docs changelogs still v0.7.2-era, pinned at
msb 0.7.2); NVIDIA Open Agent Safety Platform (Sept-28 launch
already folded — in-window third-party corroboration only, not a
re-file); Modal egress billing (third-party mirror restates the
baseline verbatim: Oct 1 start, 1/10/100 TiB, $0.04/GiB overage,
Volumes excluded; post-effective-date re-confirmation stays
first-party-only, not yet due); Hugo CVE-2026-100690 (third-party
aggregators only — vulncheck entries reference older GHSA items,
not 100690; gate unmet); NanoClaw × Vercel/OneCLI policy partnership
(the C52 VentureBeat piece recrawled — still a policy partnership,
not a sandbox/compute announcement; below the NanoCo re-grade bar).

Flagged but not filed (5):
1. OpenAI DevDay pre-keynote (C68) — the keynote (10am PT / ~12pm CT
   2026-09-29) had not happened at survey time (~07:24 CDT, 5:24am
   PT). In-window evolution: OpenAI's Sept-28 @OpenAI post "Get
   ready." ("1 day. 20+ launches."); Barron's Tuesday story now runs
   the GPT-6.1 "Astra" cancellation directly, quoting head of
   safety systems Saachi Jain in an emailed statement; Reuters/NYT/
   WSJ and others carry the same confirmed-company statement (the
   October debut was scrapped after internal tests "didn't quite
   meet the bar" on deception and scope/authorization). This is still
   pre-keynote press reporting, not the keynote itself — and the
   gate explicitly names the Astra-cancellation item as never-file
   pre-keynote. C68 stays NOT filed. The post-keynote passes grade
   the actual keynote. Other leak items ("o" always-on assistant —
   remains a leak; Friday training halt) all stay pre-keynote or
   third-party.
2. An alleged Vercel dark-web credential sale (UNVERIFIED — Vercel
   unconfirmed). New in-window attribution: Sept-28 undercodenews
   pieces cite a SOCRadar Sept-27 report plus a @DailyDarkWeb
   highlight (alleged access keys, source code, employee tokens, $2M
   ask). One coverage piece ships its own fact-checker — breach NOT
   confirmed (FALSE), credential validity NOT confirmed (FALSE),
   source-code authenticity NOT confirmed (FALSE) — watch only.
   Do-not-conflate note: the socradar.io Vercel-breach page in
   results is the OLDER April-2026 breach write-up (83 days old,
   Mandiant, Context.ai upstream compromise), not this listing.
3. Prime Intellect "Prime Sandboxes" — first-party blog (MicroVMs
   for agentic RL training) with published pricing (vCPU $0.02/hr,
   memory $0.0125/GiB/hr, disk $0.0002/GiB/hr, launch promo through
   Dec 22); docs page mirrors the pricing and adds the December-22
   date; a third-party piece says "opened general access... 30M
   sandboxes during private rollout". Still no explicit launch date
   anywhere in the snippets — launch recency NOT confirmed.
   Flagged, not filed. **Confirm the date before any grading** (the
   carried watch-out stands).
4. Docker Sandboxes CVE-2026-77179 (pre-window — ~Sept 16 piece) —
   macOS virtio-fs symlink host escape, CVSS 9.4, fixed in v0.42.0
   (shipped Sept 7) whose release notes never name the CVE; Docker
   is its own CNA. Pre-window publication AND fix, no in-window
   development — below every filing gate; flagged for color only.
5. Agent-adjacent funding, out of lane — Crusoe $3.9B Series F closed
   at $30.9B (bytevyte funding tracker); DeepSeek $7.45B raise
   flagged; AMD agreed to buy World Labs for ~$8.2B in stock (deal
   needs regulatory approval). Compute infra and lab-level M&A, not
   sandbox/agent-VM vendors — lane-adjacent context only, no filing.

## Standing-item state (cycle 54)

- **C11 FILE ON CLOSE — armed.** Modal $750M @ $15.75B still
  "nearing/closing in on/approaching/negotiating"; Baseten ~$26B still
  "nearing/in talks/discussing/seeking". No first-party close
  announcement — the gate stays armed.
- **C12 — OPEN (54th consecutive first-party read).** AgentComputer
  still publishes no egress pricing line.
- **C68 — NOT filed.** OpenAI DevDay keynote (10am PT / ~12pm CT
  2026-09-29) had not happened at survey time; the post-keynote
  passes grade the actual keynote.
- **Modal egress billing — effective Oct 1, 2026** (2 calendar days
  after the 2026-09-29 survey). Re-confirm with first-party reads
  post-effective-date; relative-date words forbidden in captures.
- **Drives GA — standing tracked item** (no in-cycle grading; not
  declared dead).
- **NanoCo re-grade bar — unmet.** First-party sandbox/compute
  announcement only.
- **Aged-out stay out:** C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI. **C26 closed.**
- **Namesake noise:** Perplexity "Computer" agent (AgentComputer-lane
  namesake); boAt audio-company hits (boat.dev-lane namesake). None
  promoted.
- **Watch-outs for the next slot:** C68 resolution at the ~12pm CT
  keynote (post-keynote passes grade the actual keynote; only an
  actual OpenAI confirmation files); C11 FILE ON CLOSE; Modal egress
  billing effective 2026-10-01 — first-party re-confirm
  post-effective-date; Drives GA as a standing tracked item; the
  alleged Vercel dark-web credential sale stays watch-only (do not
  conflate with the older April-2026 Vercel breach); Hugo
  CVE-2026-100690 third-party-only (file on first-party GHSA only);
  NanoCo first-party sandbox/compute announcement is the re-grade
  bar; Prime Intellect Prime Sandboxes — confirm launch recency
  before any grading; surveyor timestamp-honesty rule in force.
