# Competitor watch — 2026-09-28 (evening, cycle 39)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 23:39:02 CDT stat-certified) against the
cycle-38 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (18 first-try
browser.open successes — all 18 chain URLs — 0 retries, 0 failures,
0 searches; every URL carried verbatim from the baseline capture
chain). Surveyor B: delta news scan (evidence-bounded since ~23:30 CDT;
10 search queries, snippet level, zero pages opened, mtime-bounded to
23:39:19 CDT stat-certified) —
**0 CANDIDATES, 14 clean dedupes, 6 flagged-only** (thirty-fourth
straight quiet B-lane scan, C6–C39).

Delta-only against the cycle-38 evening pass
(`docs/COMPETITOR_WATCH_2026-09-28_EVENING_C38.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-2324.md`,
`hidden_files/agent_notes/surveyor-b-20260928-2324.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle; both surveyors produced no
> prospective completion labels — their captures carry only
> real write-completion bounds (stat-certified by the integrator).
> All verdicts below are mtime-bounded: A-lane to 23:39:02 CDT,
> B-lane to 23:39:19 CDT.
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items — items 1–3, 4a–4c (Vercel trio), and 5–9
> no-change (9 items), 0 delta, 0 unverified. Surveyor B's header (0
> CANDIDATES / 14 clean dedupes / 6 flagged-only) agrees with its
> enumerations — no candidate reached the integrator's corpus gate
> this cycle, so no gate-resolution section is needed.
>
> **Integrator fold-gate:** no CANDIDATES this cycle — nothing to
> gate. No new C-numbers, no re-folds, no age-out movement.

## Surveyor A — first-party vendor re-verification (mtime-bounded to 23:39:02 CDT)

**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still SEP 26
   2026 / V0.218.0; second still SEP 25 / V0.217.0; no V0.219+ on the
   page.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out 2026-09-22 ("Improved sandbox moves and support for private kit
   images in cloud sandboxes"); the 2026-09-21 v3-kits entry verbatim
   unchanged.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still v0.7.3; no
   v0.7.4+ tag.
4. **Vercel (changelog index, Sandbox docs, Drives page — ALL
   NO-CHANGE).**
   a. **Changelog index — VERIFIED NO-CHANGE.** The "28 September"
      section still carries the cycle-38 baseline's 3 entries in the
      same order ("Search domains without authentication",
      "Claude Sonnet 5.5 now available on AI Gateway",
      "Vercel Sandbox now supports memory observability"). No Drives
      GA entry anywhere in the rendered window (24–28 September).
      **P49 FINAL IN-CYCLE VERDICT: NOT MET as observed** (fifteenth
      and FINAL consecutive in-cycle grading, C25–C39; the expectation
      window closes at 00:00 CT 2026-09-29). In-cycle grading stops
      here — from the next pass, Drives GA is watched as a standing
      tracked item, not graded. Not declared dead: Vercel has not
      cancelled Drives GA; the first-party surfaces simply still show
      Private Beta.
   b. **Sandbox docs Features list — VERIFIED NO-CHANGE.** Still
      `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
      Features list.
   c. **Drives Private Beta page — VERIFIED NO-CHANGE.** Still "in
      Private Beta" with an active waitlist; no GA language.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact.

**Re-carried (not a baseline delta verdict):** the DigitalOcean "100
sessions/team" detail remains on the first-party limits page (stamp
"Last verified 21 Sep 2026"), verbatim: **"You can run up to
100 sessions at once per team depending on your tier."**

6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB; overage
   $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals (~2 days to the effective date).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (39th
   consecutive first-party read, zero wording drift).
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4).** `ascii.dev`
   and `box.ascii.dev` both serve the Boat homepage natively (no
   redirect); `ycombinator.com/companies/ascii` and
   `/companies/boat` both render the Boat listing natively.
   Migration-complete state holds.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE (retired-bar
   acceptance: visible list matches baseline enumeration).** The four
   Sep-28 Moderate advisories still top the list; no 100690-specific
   advisory. The render is still capped at exactly 10 (fourteenth
   consecutive — the ≥14-total bar stays retired in favor of "visible
   list matches baseline enumeration").

## Surveyor B — delta news scan (evidence-bounded since ~23:30 CDT, mtime-bounded to 23:39:19 CDT): 0 CANDIDATES / 14 clean dedupes / 6 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; thirty-fourth straight quiet
B-lane scan (C6–C39). No new sandbox/compute-for-agents provider
product launch, GA, pricing change, or first-party vendor announcement
appeared in-window across any lane.

**Clean dedupes (14):**

1. **Modal "$750M round at $15.75B valuation" — maps to standing C11.**
   Fresh syndications keep "nearing"/"closing in on" framing →
   no close signal; FILE ON CLOSE stays armed.
2. **Baseten "~$26B infusion" — maps to standing C11 (Baseten arm).**
   Primary-source reporting still says discussions "have not
   produced completed rounds" → talks-level, no close signal.
3. **agent-O / OpenAI DevDay — no OpenAI confirmation in-window —
   maps to C68 gate (standing).** An in-window Sept-28 piece
   explicitly says "OpenAI has confirmed no product announcements" —
   all leak framing. DevDay keynote Tue Sep-29 10am PT / 12pm CT
   remains the confirmation gate; only an actual OpenAI confirmation
   files C68.
4. **NVIDIA Open Agent Safety Platform syndications — maps to
   already-folded C70.** Recirculation/corroboration only; no new mint.
5. **Vercel Sandbox Drives public-beta explainers — pre-window
   context; P49's final grade sits with A-lane above.** Not a GA event.
6. **Modal egress billing Oct 1 — carried standing.** No
   went-live-early signals in-window (~2 days to the effective date).
7. **Docker Cloud Sandboxes launch — pre-window dedupe.** No in-window
   movement.
8. **Daytona 2024-era PR reprints — recycled, maps to C34 B-8.**
   Timestamp-artifact reprints, not new news.
9. **Baseten closed-round pieces (Series F, vintage funding) —
   context only.** No product movement.
10. **Third-party "best agent sandboxes" / pricing-comparison
    roundups — below bar.** Third-party methodology, not provider news.
11. **NanoClaw × Vercel / agent-product feature pieces — below bar.**
    Consumer/agent-UX news, not provider launches; the NanoCo
    re-grade bar (first-party sandbox/compute announcement) stays
    unmet.
12. **AMD/World Labs-type acquisitions — not in-lane.** Not filed.
13. **Frontier-lab safety/model news (GPT-series recirculation,
    Gemini Gems, Meta enterprise AI) — below bar.** Not
    sandbox/compute-for-agents provider movement.
14. **AgentComputer — nothing new in the covered lanes — C12 stays
    OPEN.** No first-party egress pricing line or product movement.

**Flagged-only (6, below bar):**

1. **Alleged Vercel access-keys/source-code dark-web sale —
   UNVERIFIED, watch-only — unchanged.** Fresh Sept-28 pieces still
   trace the claim to the Sept-27 SOCRadar report + @DailyDarkWeb
   post and explicitly rate it unverified, with no Vercel
   confirmation of a NEW incident. Promotion bar NOT met: watch only.
   (SOCRadar's own blog piece is ~83 days old — the April incident —
   a plausible conflation source.)
2. **NanoClaw-to-Slack (venturebeat, pre-window) — agent product
   feature, not a sandbox/compute provider launch.** Not filed.
3. **NanoClaw × Vercel policy-settings/approval-dialogs piece —
   below bar.** Enterprise agent UX feature; not filed.
4. **GPT-6.1 "Astra" cancellation recirculation — below bar.**
   Frontier-lab safety news; watch only.
5. **Adjacent out-of-lane launches — not filed.** Anthropic Sonnet 5.5,
   Meta enterprise AI platform, Google killing Gemini Gems, Shopify
   opening checkout to browser-based AI agents — model/product news
   adjacent to agents, but no sandbox/compute-for-agents provider
   launch, GA, or pricing change.
6. **Shopify agent-checkout / e-commerce agent pieces — below bar.**
   Not provider news.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** Hugo CVE-2026-100690 (bar remains "file on
first-party GHSA appearance only"); Plugin4Shell (still no real CVE —
never cite the suspect CVE-2026-92104); Boxd $2M pre-seed (closed —
recirculation does NOT reactivate); Baseten × Blaxel Carbon (private
preview, GA not tripped); Mistral Vibe (no new family member);
TermSquad (Sept 15 launch) carried standing; Boat/Ascii and
Microsandbox carried; Docker Cloud Sandboxes (Sept ~24, pre-window)
carried; DigitalOcean Managed Agents carried. Aged-out stay out (C29,
C45, C56, C66, C67, C62, Heapjack/Overpatch, GitLab CVE-2026-85706,
Dextr AI); C26 closed.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict stands — streak extends (thirty-fourth straight quiet
  B-lane scan, C6–C39).
- **Corpus movement:** no new mints, no re-folds, no new age-outs
  this cycle. **C11 (Modal/Baseten talks-wave) — still
  unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (39th consecutive read, zero wording drift).** Aged-out
  stay out (C29, C45, C56, C66, C67, C62 — re-fold path on real
  movement; Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI).
  C26 closed.
- **P49 — FINAL in-cycle grade: NOT MET as observed (fifteenth
  consecutive, C25–C39).** The expectation window closes at 00:00 CT
  2026-09-29. Not declared dead: Vercel has not cancelled Drives GA;
  its own surfaces simply still show Private Beta with an active
  waitlist. **In-cycle grading stops here** — from the next pass,
  Drives GA is a standing tracked item (re-verified each pass, no
  numbered grading).
- **Watch-outs for the next slot:** no more in-cycle P49 grading —
  Drives GA tracked as standing; C68 confirmation gate — OpenAI DevDay
  keynote Tue Sep-29 10am PT / 12pm CT (only an actual OpenAI
  confirmation files C68); C11 FILE ON CLOSE (both rounds still
  unclosed — a close announcement files immediately); Modal egress
  billing re-confirm post-effective-date (Oct 1); the alleged Vercel
  dark-web credential sale stays watch-only (promotion bar unmet);
  surveyor timestamp-honesty rule in force (mtimes = completion
  evidence — no prospective labels).
