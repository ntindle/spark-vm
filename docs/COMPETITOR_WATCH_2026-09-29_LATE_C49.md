# Competitor watch — 2026-09-29 (late-night, cycle 49)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded) against the cycle-48 baseline — **11
VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (18 first-try
browser.open successes — 17 chain URLs plus the DigitalOcean limits
page via the sibling-URL pattern of the chain's own pricing subpage —
0 failures, 0 retries, 0 searches; every URL carried verbatim from the
baseline capture chain). Surveyor B: delta news scan (snippet level,
zero pages opened, mtime-bounded) — **0 CANDIDATES, 14 clean dedupes,
4 flagged-only** (forty-fourth straight quiet B-lane scan, C6–C49).
**Fully quiet cycle — no first-party deltas at all.** Captures:
`hidden_files/agent_notes/surveyor-a-20260929-0424.md`,
`hidden_files/agent_notes/surveyor-b-20260929-0424.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, ~04:25 CDT).
>
> **Count-honesty check:** surveyor A's header (11 / 0 / 0) agrees with
> its eleven enumerated items 1, 2, 3, 4a–4c, 5, 6, 7, 8, 9 (zero
> deltas, zero unverified; item (a) is a standing re-carry, excluded
> from the header totals). Surveyor B's header (0 CANDIDATES / 14
> clean dedupes / 4 flagged-only) agrees with its enumerations.
>
> **Integrator fold-gate:** no genuine first-party delta this cycle —
> **no fold**, no mints, no re-folds, no age-out movement. The C44
> Microsandbox v0.7.4 delta is now baseline state and renders
> unchanged. The A-lane went fully delta-free again (equally
> delta-free first-party passes in C41–C43 and C45–C48).

Delta-only against the cycle-48 late-night pass (PR #673's
`docs/COMPETITOR_WATCH_2026-09-29_LATE_C48.md`). Read-only, no
logins, no writes.

## Surveyor A — first-party vendor re-verification (mtime-bounded)

**11 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still SEP 26
   2026 / V0.218.0 ("KVM sandbox parameter and CLI WorkOS
   application"); second still SEP 25 / V0.217.0 ("NVIDIA B300 GPU
   type"); third SEP 24 / V0.216.1; fourth SEP 24 / V0.216.2. No
   V0.219+ on the page.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out 2026-09-22 ("Improved sandbox moves and support for private kit
   images in cloud sandboxes"); the 2026-09-21 v3-kits entry verbatim
   unchanged, followed by the 2026-09-15 entry.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Top release still
   v0.7.4 (the C44 delta, now baseline) with its full body intact
   (Features #1455/#1667; Fixes #1653/#1456/#1666/#1668; CI #1659;
   Maintenance #1652); v0.7.3 still second. No v0.7.5+ on the page.
4. **Vercel (changelog index, Sandbox docs, Drives page — ALL
   NO-CHANGE).**
   a. **Changelog index — VERIFIED NO-CHANGE.** The "28 September"
      section still carries the baseline's 3 entries in the same order:
      "Search domains without authentication" first, then "Claude
      Sonnet 5.5 now available on AI Gateway", then "Vercel Sandbox
      now supports memory observability". No Drives GA entry anywhere
      in the rendered window (24–28 September). The 27 Sep
      "Ember-1 from Fireworks now available on AI Gateway" entry
      unchanged below.
      **Drives GA is a standing tracked item (no in-cycle grading).**
      Not declared dead: Vercel has not cancelled Drives GA; the
      first-party surfaces simply still show beta/private-beta. No GA
      language on this read — no mint triggered.
   b. **Sandbox docs Features list — VERIFIED NO-CHANGE.** Still
      `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
      Features list ("Attach persistent filesystem storage to
      sandboxes and reuse data across sandbox runs.").
   c. **Drives Private Beta changelog page — VERIFIED NO-CHANGE.**
      Title still "Drives for Vercel Sandbox in Private Beta";
      private-beta SDK/CLI (`@vercel/sandbox@beta`); waitlist still
      live ("Sign up here to join the waitlist"); "During the private
      beta, a drive can be mounted read-write by one sandbox at a
      time." plus "Sandbox drives should not be used for production
      data while in private beta." No GA language — no mint candidate
      triggered.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact. No change to the five
   baseline figures.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB; overage
   $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals (effective date Oct 1 — **2 calendar days
   after this survey**, stated as arithmetic, never as "tomorrow").
   **Re-confirm post-effective-date** with first-party reads only.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, zero wording drift. AgentComputer
   still publishes **no first-party egress pricing line — C12 stays
   OPEN** (49th consecutive first-party read).
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively. Migration-complete state holds.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE (retired-bar
   acceptance: visible list matches baseline enumeration).** The four
   Sep-28 Moderate advisories (GHSA-3jfr-vjcq-7jvf, GHSA-r4xx-89rf-5424,
   GHSA-6c8w-mpp8-9w47, GHSA-wcpj-vcvm-j4pg) still top the list; no
   100690-specific advisory. The 5 Sep-9 + 1 Aug-27 advisories still
   visible below, matching the baseline's enumerated set. The render is
   still capped at exactly 10 (twenty-fourth consecutive — the
   ≥14-total bar stays retired in favor of "visible list matches
   baseline enumeration").

**Re-carried (a) (not a baseline delta verdict):** the DigitalOcean "100
sessions/team" detail remains on the first-party limits page (stamp
"Last verified 21 Sep 2026"), verbatim: **"You can run up to
100 sessions at once per team depending on your tier."** A per-team
concurrency cap on the limits page, not a pricing figure.

## Surveyor B — delta news scan (snippet level, zero pages opened, mtime-bounded): 0 CANDIDATES / 14 clean dedupes / 4 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; forty-fourth straight quiet B-lane
scan (C6–C49). No new sandbox/compute-for-agents provider product
launch, GA, pricing change, or first-party vendor announcement
appeared in-window across any lane.

**Clean dedupes (14):**

1. **Daytona** — no in-window first-party launch/GA/pricing/funding
   announcement; undated PR-syndication reprints of the older OpenHands
   agent-agnostic announcement plus community integration docs → no
   delta.
2. **E2B** — no new launch, GA, pricing change, or funding in window;
   only third-party comparisons, evergreen integration docs, and
   community proposal files.
3. **Modal "$750M @ $15.75B" — maps to standing C11.** TechCrunch
   (Sep 28) and syndication still frame "nearing"/"closing in on" a
   $750M Accel-led round at $15.75B; Modal declined to comment. No
   first-party close announcement → below the FILE-ON-CLOSE gate.
4. **Baseten "~$26B infusion" — maps to standing C11 (Baseten arm).**
   Bloomberg-derived "nearing"/"in talks" language unchanged; no
   first-party close announcement → below gate.
5. **Vercel Sandbox Drives — no GA language anywhere — standing
   tracked item.** Third-party architecture analysis of the Sep-23
   public beta only; beta terms unchanged. No in-cycle grading.
6. **DigitalOcean Managed Agents / Harness** — the Sep-21/22 filed
   preview event restated by in-window syndication (market-wire) and
   third-party analysis. Still public preview → no delta.
7. **Docker Sandboxes** — the Sep-24 first-party Cloud Sandboxes launch
   is pre-window (already filed); the Sep-24 BAND Python Kit
   announcement (PR Newswire via morningstar + syndication) is
   third-party integration, also pre-window. No new first-party delta.
8. **TermSquad** — Sep-15 launch materials only (pre-window); tier data
   unchanged → no delta.
9. **boat.dev / AgentComputer** — no in-window announcements; search
   noise only.
10. **Microsandbox** — no new launch/GA/pricing; only community
    comparison matrices and integration docs (managed cloud still
    private beta, "cloud pricing out post private beta").
11. **NVIDIA OpenShell** — folded as C70 (GA v0.1.0). The in-window
    marktechpost piece (Sep 28) is corroboration of the folded launch,
    not a new product change.
12. **Modal egress billing (B-lane standing)** — effective date remains
    Oct 1, 2026 (1 TiB/10 TiB/100 TiB allowances, $0.04/GiB overage)
    per docs-mirrored pricing; no first-party went-live-early signal
    surfaced this pass.
13. **Hugo CVE-2026-100690** — no first-party gohugoio/hugo GHSA
    advisory found; only third-party aggregator records (offseq
    CVE-2026-89259 is a different, Sep-11-published CVE — also below
    gate and pre-window) → below the file-on-GHSA-only gate — no
    filing. Suspect CVE-2026-92104 not cited.
14. **Encore × E2B integration post** — third-party vendor integration
    guidance, not an E2B first-party launch → out of gate.

**Flagged-only (4, below bar):**

1. **OpenAI DevDay pre-keynote leaks (C68 gate).** "O" always-on-agent
   coverage and GPT-6 Sol/Luna/Astra roundups are all pre-keynote
   leak/speculation; "Managed Agents expected" pieces remain rumor.
   The keynote (10am PT / 12pm CT, 2026-09-29) had NOT happened at
   survey time. Per instruction: no file until an actual OpenAI
   announcement. Watch the post-keynote pass.
2. **Vercel dark-web credential-sale allegation (Sep 27–28,
   SOCRadar/@DailyDarkWeb via undercodenews, carried from C48)** — the
   pieces themselves state the listing is UNVERIFIED and Vercel has not
   confirmed any compromise. Promotion bar unmet; watch-only.
3. **NanoClaw/NanoCo × Vercel policy partnership (VentureBeat)** —
   infrastructure-level approval dialogs across messaging apps via Chat
   SDK + OneCLI vault; below the NanoCo re-grade bar (first-party
   sandbox/compute announcement ONLY), not a compute/sandbox launch.
   Flagged only.
4. **Docker Sandboxes ecosystem analysis (webpronews, ~Sep 25)** —
   notes 24h session cap and that the Kit spec is open; single
   third-party source. The CNCF-handoff aspect is C26 watch-only;
   nothing new to file.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** C12 (AgentComputer — still no first-party egress pricing
line — surveyor A's lane, stays OPEN); aged-out stay out (C29, C45,
C56, C66, C67, C62; Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr
AI); C26 closed (Docker Sandbox Kit Spec CNCF handoff —
single-third-party-source, watch-only); Modal egress billing effective
2026-10-01 — re-confirm post-effective-date (2 calendar days after the
Sep-29 survey date; relative-date words FORBIDDEN); NanoCo re-grade
bar — first-party sandbox/compute announcement from NanoCo only.

## Standing status

- **Sandbox-infrastructure lane fully quiet this cycle.** In-lane
  no-launch verdict stands; the A-lane went delta-free (equally
  delta-free first-party passes in C41–C43 and C45–C48) and the
  B-lane extends its quiet streak to forty-four (C6–C49).
- **Corpus movement:** none. No new mints, no re-folds, no new
  age-outs. **C11 (Modal/Baseten talks-wave) — still unclosed, no
  close signal — FILE ON CLOSE stays armed.** **C12
  (AgentComputer) — still no first-party egress pricing line — stays
  OPEN (49th consecutive read).** Aged-out stay out (C29, C45, C56,
  C66, C67, C62 — re-fold path on real movement; Heapjack/Overpatch,
  GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **Drives GA post-window:** standing tracked item, watched as an
  open expectation (no in-cycle grading). Not declared dead: Vercel
  has not cancelled Drives GA; its own surfaces simply still show
  beta/private-beta.
- **Watch-outs for the next slot:** C68 resolution window is Sep 29
  ~12pm CT (OpenAI DevDay keynote 10am PT — the next B-slot will
  likely grade the actual keynote against C68; only an actual OpenAI
  confirmation files; the predated OODAloop piece must not be
  confused for a confirmation); C11 FILE ON CLOSE (both rounds still
  unclosed — a close announcement files immediately); Modal egress
  billing effective 2026-10-01 — re-confirm with first-party reads
  post-effective-date (relative-date words FORBIDDEN — calendar dates
  or arithmetic per survey mtime); Drives GA as a standing tracked
  item (no in-cycle grading); the alleged Vercel dark-web credential
  sale stays watch-only (promotion bar unmet); Hugo CVE-2026-100690
  third-party-only (file on first-party GHSA only); NanoCo as
  NanoClaw's vehicle — first-party sandbox/compute announcement from
  NanoCo meets the re-grade bar; surveyor timestamp-honesty rule in
  force (mtimes = completion evidence).
