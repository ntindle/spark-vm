# Competitor watch — 2026-09-29 (early-morning, cycle 52)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded) against the cycle-51 baseline — **17
VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (18 first-try
browser.open successes, 0 retries, 0 failures, 0 searches). Surveyor B:
delta news scan (snippet level, zero pages opened, mtime-bounded to
the post-C51 window) — **0 CANDIDATES, 14 clean dedupes, 4
flagged-only** (forty-seventh straight quiet B-lane scan, C6–C52).
**Fully quiet cycle — no first-party deltas at all.** Captures:
`hidden_files/agent_notes/surveyor-a-20260929-0624.md`,
`hidden_files/agent_notes/surveyor-b-20260929-0624.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, ~06:26 CDT).
>
> **Count-honesty check:** surveyor A's header (17 / 0 / 0) agrees with
> its seventeen enumerated items 1, 2, 3, 4a–4c, 5, 6, 7a–7d, 8a–8d, 9
> (zero deltas, zero unverified; item (a) is a standing re-carry,
> excluded from the header totals). Surveyor B's header (0 CANDIDATES
> / 14 clean dedupes / 4 flagged-only) agrees with its enumerations.
>
> **Integrator fold-gate:** no genuine first-party delta this cycle —
> **no fold**, no mints, no re-folds, no age-out movement. The A-lane
> went fully delta-free again (equally delta-free first-party passes
> in C41–C43 and C45–C52).

Delta-only against the cycle-51 early pass (PR #684's
`docs/COMPETITOR_WATCH_2026-09-29_LATE_C51.md`). Read-only, no
logins, no writes.

## Surveyor A — first-party vendor re-verification (mtime-bounded)

**17 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still SEP 26
   2026 / V0.218.0; second still SEP 25 / V0.217.0; third SEP 24 /
   V0.216.1; fourth SEP 24 / V0.216.2. No V0.219+ on the page.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out 2026-09-22 ("Improved sandbox moves and support for private kit
   images in cloud sandboxes"); the 2026-09-21 v3-kits entry verbatim
   unchanged, followed by the 2026-09-15 entry.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Top release still
   v0.7.4 with its full body intact (Features #1455/#1667; Fixes
   #1653/#1456/#1666/#1668; CI #1659; Maintenance #1652); v0.7.3 still
   second. No v0.7.5+ on the page.
4. **Vercel (changelog index, Sandbox docs, Drives page — ALL
   NO-CHANGE).**
   a. **Changelog index — VERIFIED NO-CHANGE.** The "28 September"
      section still carries the baseline's 3 entries in the same order:
      "Search domains without authentication" first, then "Claude
      Sonnet 5.5 now available on AI Gateway", then "Vercel Sandbox
      now supports memory observability". No Drives GA entry anywhere
      in the rendered window (24–29 September).
      **Drives GA is a standing tracked item (no in-cycle grading).**
      Not declared dead: Vercel has not cancelled Drives GA; the
      first-party surfaces simply still show beta/private-beta. No GA
      language on this read — no mint triggered.
   b. **Sandbox docs Features list — VERIFIED NO-CHANGE.** Still
      `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
      Features list.
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
   arithmetic, never as "tomorrow"); Starter 1 TiB / Team 10 TiB /
   Enterprise 100 TiB; overage $0.04/GiB; first bill Nov 1, 2026;
   Volumes excluded. No went-live-early signals.
   **Re-confirm post-effective-date** with first-party reads only.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (7a–7d).** All verbatim identical, zero wording drift. AgentComputer
   still publishes **no first-party egress pricing line — C12 stays
   OPEN** (52nd consecutive first-party read).
8. **Boat legacy domains — VERIFIED NO-CHANGE (8a–8d, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively.
9. **Hugo advisories — VERIFIED NO-CHANGE.** 4 Sep-28 Moderate
   advisories top the list (GHSA-3jfr-vjcq-7jvf, GHSA-r4xx-89rf-5424,
   GHSA-6c8w-mpp8-9w47, GHSA-wcpj-vcvm-j4pg); 5 Sep-9 + 1 Aug-27
   below; render capped at exactly 10 (27th consecutive); no "100690"
   anywhere. The CVE record appears only on third-party aggregators —
   below the file-on-GHSA-only gate.

**EXTRA (a) — re-carry only, excluded from header totals.** The
DigitalOcean limits page still carries the stamp "Last verified 21 Sep
2026" and verbatim "You can run up to 100 sessions at once per team
depending on your tier."

## Surveyor B — delta news scan (snippet level, mtime-bounded)

**0 CANDIDATES, 14 clean dedupes, 4 flagged-only.** Forty-seventh
straight quiet B-lane scan (C6–C52). Nothing in-window meets any
filing or promotion gate.

Clean dedupes (14): Daytona (syndication only); E2B (no launch/GA/
pricing); Modal funding (still "nearing/closing in on/negotiating"
language across the full syndication tree, below C11's FILE-ON-CLOSE
gate); Baseten ~$26B (still "in talks/could value" language, below
gate); Vercel Drives (public beta, no GA language); DigitalOcean
Managed Agents (Sept-22 preview + syndication); Docker Sandboxes
(Sept-24 launch + syndication; the Kits/CNCF coverage is of the same
announcement); TermSquad (Sept-15 wire syndication);
boat.dev / AgentComputer (search noise only); Microsandbox (no v0.7.5);
NVIDIA Open Agent Safety Platform (Sept-28 launch already folded —
in-window third-party corroboration only, not a re-file); Modal egress
billing (nothing new, restates the baseline; effective 2026-10-01 —
post-effective-date re-confirmation only); Hugo CVE-2026-100690
(aggregators only — gate unmet); Encore × E2B (pre-window blog).

Flagged but not filed (4):
1. OpenAI DevDay pre-keynote speculation — the keynote (~12pm CT
   2026-09-29) had not happened at survey time; in-window wrinkle: a
   Barron's piece citing the WSJ (less than an hour old at survey
   time) reports OpenAI canceled GPT-6.1 "Astra" on safety concerns —
   third-party reporting, not an OpenAI confirmation, so C68 stays NOT
   filed. The post-keynote passes grade the actual keynote.
2. An alleged Vercel dark-web credential sale (UNVERIFIED — Vercel
   unconfirmed; the coverage itself states the listing has no
   independent verification — watch only).
3. A NanoClaw × Vercel policy-partnership piece — below the NanoCo
   re-grade bar (no first-party sandbox/compute announcement).
4. DNS-tunneling sandbox-escape commentary (dev.to) — third-party
   analysis of OpenAI's Sept-25 incident report, not an in-scope
   vendor CVE; context only.

## Standing-item state (cycle 52)

- **C11 FILE ON CLOSE — armed.** Modal $750M @ $15.75B still
  "nearing/closing in on/negotiating"; Baseten ~$26B still "in talks/
  could value". No first-party close announcement — the gate stays
  armed.
- **C12 — OPEN (52nd consecutive first-party read).** AgentComputer
  still publishes no egress pricing line.
- **C68 — NOT filed.** OpenAI DevDay keynote (~12pm CT 2026-09-29) had
  not happened at survey time (~06:26 CDT); all coverage is
  pre-keynote leak/speculation. The post-keynote passes (later on
  2026-09-29) grade the actual keynote.
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
- **Watch-outs for the next slot:** C68 resolution window 2026-09-29
  ~12pm CT (the post-keynote passes, not the next B-slot, grade the
  actual keynote; only an actual OpenAI confirmation files); C11 FILE
  ON CLOSE; Modal egress billing effective 2026-10-01 — first-party
  re-confirm post-effective-date; Drives GA as a standing tracked
  item (no in-cycle grading); the alleged Vercel dark-web credential
  sale stays watch-only; Hugo CVE-2026-100690 third-party-only
  (file on first-party GHSA only); NanoCo first-party
  sandbox/compute announcement is the re-grade bar; surveyor
  timestamp-honesty rule in force.
