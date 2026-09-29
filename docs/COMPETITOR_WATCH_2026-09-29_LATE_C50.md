# Competitor watch — 2026-09-29 (late-night, cycle 50)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded) against the cycle-49 baseline — **17
VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (18 first-try
browser.open successes — 17 chain URLs plus the DigitalOcean limits
page via the sibling-URL pattern of the chain's own pricing subpage —
0 failures, 0 retries, 0 searches; every URL carried verbatim from the
baseline capture chain). Surveyor B: delta news scan (snippet level,
zero pages opened, mtime-bounded) — **0 CANDIDATES, 14 clean dedupes,
3 flagged-only** (forty-fifth straight quiet B-lane scan, C6–C50).
**Fully quiet cycle — no first-party deltas at all.** Captures:
`hidden_files/agent_notes/surveyor-a-20260929-0454.md`,
`hidden_files/agent_notes/surveyor-b-20260929-0454.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, ~05:21 CDT).
>
> **Count-honesty check:** surveyor A's header (17 / 0 / 0) agrees with
> its seventeen enumerated items 1, 2, 3, 4a–4c, 5, 6, 7a–7d, 8a–8d, 9
> (zero deltas, zero unverified; item (a) is a standing re-carry,
> excluded from the header totals). **Numbering note:** this cycle's
> capture counts sub-items individually (17) where prior cycles used
> top-level item counts (11) — the underlying 18-URL chain is identical,
> so this is a counting-convention change, not a coverage change.
> Surveyor B's header (0 CANDIDATES / 14 clean dedupes / 3 flagged-only)
> agrees with its enumerations.
>
> **Integrator fold-gate:** no genuine first-party delta this cycle —
> **no fold**, no mints, no re-folds, no age-out movement. The C44
> Microsandbox v0.7.4 delta is now baseline state and renders
> unchanged. The A-lane went fully delta-free again (equally
> delta-free first-party passes in C41–C43 and C45–C49).

Delta-only against the cycle-49 late-night pass (PR #674's
`docs/COMPETITOR_WATCH_2026-09-29_LATE_C49.md`). Read-only, no
logins, no writes.

## Surveyor A — first-party vendor re-verification (mtime-bounded)

**17 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED.** Zero
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
      in the rendered window (24–28 September).
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
      live; "Sandbox drives should not be used for production
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
   (7a–7d).** All verbatim identical, zero wording drift. AgentComputer
   still publishes **no first-party egress pricing line — C12 stays
   OPEN** (50th consecutive first-party read).
8. **Boat legacy domains — VERIFIED NO-CHANGE (8a–8d, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively.
9. **Hugo advisories — VERIFIED NO-CHANGE.** 4 Sep-28 Moderate
   advisories top the list (GHSA-3jfr-vjcq-7jvf, GHSA-r4xx-89rf-5424,
   GHSA-6c8w-mpp8-9w47, GHSA-wcpj-vcvm-j4pg); 5 Sep-9 + 1 Aug-27
   below; render capped at exactly 10 (25th consecutive); no "100690"
   anywhere. The CVE record appears only on third-party aggregators —
   below the file-on-GHSA-only gate.

**EXTRA (a) — re-carry only, excluded from header totals.** The
DigitalOcean limits page still carries the stamp "Last verified 21 Sep
2026" and verbatim "You can run up to 100 sessions at once per team
depending on your tier."

## Surveyor B — delta news scan (snippet level, mtime-bounded)

**0 CANDIDATES, 14 clean dedupes, 3 flagged-only.** Forty-fifth
straight quiet B-lane scan (C6–C50). Nothing in-window meets any
filing or promotion gate.

Clean dedupes (14): Daytona (syndication reprints only); E2B (no
launch/GA/pricing move); Modal funding (TechCrunch 2026-09-28
"closing in on $750M @ $15.75B", Modal declined comment — still
"nearing" language, below C11's FILE-ON-CLOSE gate); Baseten ~$26B
(same "in talks" language, below gate); Vercel Drives (no GA language;
the nandann.com piece is third-party analysis of the 2026-09-23
public beta); DigitalOcean Managed Agents (pre-window first-party
release + syndication only); Docker Sandboxes (Sept 24 first-party
announcement pre-window; BAND Python Kit integration is
third-party, pre-window); TermSquad (Sept 15 launch wire-syndication
only); boat.dev / AgentComputer (search noise only); Microsandbox
(community matrices and routine changelogs, no launch); NVIDIA Open
Agent Safety Platform (in-window third-party coverage corroborates
the folded Sept-28 launch — corroboration only, no re-file);
Modal egress billing (nothing new; effective 2026-10-01 —
post-effective-date re-confirmation only); Hugo CVE-2026-100690 (no
first-party GHSA — gate unmet); Encore × E2B integration (pre-window
third-party guidance, out-of-gate).

Flagged but not filed (3): OpenAI DevDay pre-keynote speculation
("'o' always-on-agent leak roundups, GPT-6 Sol/Luna/Astra + "Managed
Agents expected" roundups, a DevDay-bingo joke — keynote Sep 29 ~12pm
CT had not happened at survey time; only an actual OpenAI
confirmation files C68 — watch the post-keynote pass); an alleged
Vercel dark-web credential sale (UNVERIFIED — Vercel unconfirmed,
watch only); a NanoClaw × Vercel policy partnership (carried,
below the NanoCo re-grade bar — first-party sandbox/compute
announcement only).

**Integrator note on C70:** this cycle's fuller in-window record
(NVIDIA's own Sept 28 blog + Huang CNBC interview, 100+ launch
partners — Anthropic, Arm, Microsoft, Oracle, SpaceX; OpenAI not
listed) scopes the folded Sept-28 event as a platform launch
(OpenShell open-source runtime + Sentry BlueField-4 hardware
watchdog), not just OpenShell GA v0.1.0. The corpus is append-only:
no retro-edit to the C70 filing — this note stands as the
corrected scope. A future mint only on a genuinely new first-party
move.

## Standing-item state (cycle 50)

- **C11 FILE ON CLOSE — armed.** Modal $750M @ $15.75B still
  "nearing/closing in on"; Baseten ~$26B still "in talks". No
  first-party close announcement — the gate stays armed.
- **C12 — OPEN (50th consecutive first-party read).** AgentComputer
  still publishes no egress pricing line.
- **C68 — NOT filed.** OpenAI DevDay keynote (~12pm CT 2026-09-29) had not
  happened at survey time (~05:21 CDT); all coverage is pre-keynote
  leak/speculation. The post-keynote passes (later on 2026-09-29) grade the
  actual keynote.
- **Modal egress billing — effective Oct 1, 2026** (2 calendar days
  after the 2026-09-29 survey). Re-confirm with first-party reads
  post-effective-date; relative-date words forbidden in captures.
- **Drives GA — standing tracked item** (no in-cycle grading; not
  declared dead).
- **NanoCo re-grade bar — unmet.** First-party sandbox/compute
  announcement only.
- **Aged-out stay out:** C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI. **C26 closed.**
- **Namesake noise:** Guava "Daytona" voice model (voice AI, different
  company); Perplexity "Computer" agent (AgentComputer-lane namesake);
  boAt Lifestyle India breach (~1000 days old, boat.dev-lane
  namesake). None promoted.
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
