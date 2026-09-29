# Competitor watch — 2026-09-28 (evening, cycle 37)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 22:26:12 CDT stat-certified) against the
cycle-36 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (18 first-try
browser.open successes — 17 chain URLs plus the DigitalOcean limits
page via the sibling-URL pattern of the chain's own pricing subpage —
0 failures, 0 searches; every URL carried verbatim from the baseline
capture chain). Surveyor B: delta news scan (evidence-bounded since
~22:20 CDT; snippet level, zero pages opened, mtime-bounded to
22:26:35 CDT stat-certified) —
**0 CANDIDATES, 13 clean dedupes, 6 flagged-only** (thirty-second
straight quiet B-lane scan, C6–C37).

Delta-only against the cycle-36 evening pass
(`docs/COMPETITOR_WATCH_2026-09-28_EVENING_C36.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-2224.md`,
`hidden_files/agent_notes/surveyor-b-20260928-2224.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded: A-lane to 22:26:12 CDT, B-lane to 22:26:35 CDT
> (stat-certified by the integrator).
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items — items 1–3, 4a–4c (Vercel trio), and 5–9
> no-change (9 items), 0 delta, 0 unverified. Surveyor B's header (0
> CANDIDATES / 13 clean dedupes / 6 flagged-only) agrees with its
> enumerations — no candidate reached the integrator's corpus gate
> this cycle, so no gate-resolution section is needed.
>
> **Integrator fold-gate:** no CANDIDATES this cycle — nothing to
> gate. No new C-numbers, no re-folds, no age-out movement.

## Surveyor A — first-party vendor re-verification (mtime-bounded to 22:26:12 CDT)

**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still SEP 26
   2026 / V0.218.0 ("KVM sandbox parameter and CLI WorkOS
   application"); second still SEP 25 / V0.217.0 ("NVIDIA B300 GPU
   type"); no V0.219+ on the page.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out 2026-09-22 ("Improved sandbox moves and support for private kit
   images in cloud sandboxes"); the 2026-09-21 v3-kits entry verbatim
   unchanged, followed by the 2026-09-15 entry.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still v0.7.3; no
   v0.7.4+ tag.
4. **Vercel (changelog index, Sandbox docs, Drives page — ALL
   NO-CHANGE).**
   a. **Changelog index — VERIFIED NO-CHANGE.** The "28 September"
      section still carries the cycle-36 baseline's 3 entries in the
      same order: "Search domains without authentication" first, then
      "Claude Sonnet 5.5 now available on AI Gateway", then "Vercel
      Sandbox now supports memory observability". No Drives GA entry
      anywhere in the rendered window (24–28 September).
      **P49 IN-CYCLE VERDICT: NOT MET as observed** (thirteenth
      consecutive in-cycle grading; this pass is still in-window — the
      expectation window closes at the end of tonight, 2026-09-28).
      This watch does not declare the expectation dead — Vercel has
      not cancelled Drives GA; the first-party surfaces simply still
      show Private Beta.
   b. **Sandbox docs Features list — VERIFIED NO-CHANGE.** Still
      `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
      Features list ("Attach persistent filesystem storage to
      sandboxes and reuse data across sandbox runs.").
   c. **Drives Private Beta page — VERIFIED NO-CHANGE (read +
      reconciled).** Still "in Private Beta" with an active waitlist;
      consistent with the docs Features-list "Drives (beta)" text. No
      GA language.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact. The additional
   sections (Custom Sandbox Templates BYOT, Action Gateway Tool
   Calls, Model Inference) match the baseline render — no change to
   the five baseline figures.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB; overage
   $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals (~2.5 days to the effective date).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (37th
   consecutive first-party read, no wording drift). boat.dev's
   comparison/benchmark sections unchanged in render.
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively. Migration-complete state holds.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE (retired-bar
   acceptance: visible list matches baseline enumeration).** The four
   Sep-28 Moderate advisories still top the list; no 100690-specific
   advisory. The render is still capped at exactly 10 (twelfth
   consecutive — the ≥14-total bar stays retired in favor of "visible
   list matches baseline enumeration").

**Re-carried (not a baseline delta verdict):** the DigitalOcean "100
sessions/team" detail remains RESTORED on the first-party limits page
(stamp "Last verified 21 Sep 2026"), verbatim: **"You can run up to
100 sessions at once per team depending on your tier."** A per-team
concurrency cap on the limits page, not a pricing figure.

## Surveyor B — delta news scan (evidence-bounded since ~22:20 CDT, mtime-bounded to 22:26:35 CDT): 0 CANDIDATES / 13 clean dedupes / 6 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; thirty-second straight quiet
B-lane scan (C6–C37). No new sandbox/compute-for-agents provider
product launch, GA, pricing change, or first-party vendor announcement
appeared in-window across any lane.

**Clean dedupes (13):**

1. **Modal "$750M round at $15.75B valuation, led by Accel" — maps to
   standing C11.** TechCrunch (Sept 28) body still frames "nearing";
   fresh syndications (crawled within hours) recycle the same
   talks-level framing → no close signal; FILE ON CLOSE stays armed.
2. **Baseten "~$26B infusion" — maps to standing C11 (Baseten arm).**
   The primary-source report (Bloomberg via Sept-23 reporting) says
   "discussions … have not produced completed rounds, and the amount
   of capital either startup hopes to raise is unclear" → talks-level,
   no close signal.
3. **agent-O / OpenAI DevDay — no OpenAI confirmation in-window —
   maps to C68 gate (standing).** runtimewire (updated Sept 28,
   8:02pm CT) still states explicitly "OpenAI has confirmed no product
   announcements"; a new Sept-28 piece says the agent-O launch "is not
   confirmed, and nobody at OpenAI has labeled it" as an official
   launch. DevDay keynote Tue Sep-29 10am PT / 12pm CT remains the
   confirmation gate; only an actual OpenAI confirmation files C68.
4. **Daytona 2024-era PR Newswire reprint ("Agent-Agnostic
   Infrastructure / OpenHands demo") — recycled, maps to C34 B-8.**
   Still being re-syndicated by local-news mirrors (crawled within
   hours) — timestamp-artifact reprint, not new news.
5. **NVIDIA Open Agent Safety Platform Sept-28 launch coverage —
   maps to already-folded C70.** New in-window syndications (all
   crawled within ~3h) describe the same Sept-28 event (OpenShell
   broadly available + Sentry hardware reference design, 100+
   partners, Apache 2.0). Recirculation/corroboration only; OpenShell
   itself is not new ("announced the software in March"). No new mint.
6. **tech-insider.org "E2B vs Modal vs Daytona: AI Sandbox Pricing
   2026" — below bar, pre-window (2 days) — maps to the C29/C30
   third-party-tooling category.** Vendor/third-party methodology
   comparison, not provider news.
7. **Daytona "$24M Series A" piece — pre-window (Sept 2, 2026),
   funding-round vintage.** No product launch/GA/pricing movement;
   context only.
8. **DigitalOcean Managed Agents — pre-window launch (Sept 21/22) —
   carried standing.** No in-window product movement.
9. **"Vercel Sandbox went GA January 2026" claims — pre-window,
   not the P49 item.** Third-party comparisons date Sandbox GA to
   January 2026; P49 is the Vercel **Drives** GA (public beta Sept
   23) — still no GA evidence in-window; A's lane owns the verdict.
10. **NanoClaw × Docker partnership coverage — March 2026 vintage
    recirculation.** The re-crawled pieces are ~200 days old; no new
    first-party NanoCo sandbox/compute announcement — the re-grade
    bar stays unmet.
11. **Modal network-egress billing effective Oct 1, 2026 — carried
    standing.** Modal's own doc copy confirms the schedule; no
    went-live-early signals in-window (~2.5 days to the effective
    date).
12. **Baseten June 2026 $1.5B Series F at $13B — pre-window closed
    round, context only.** Relevant only as the closed baseline behind
    the C11 Baseten talks arm.
13. **AgentComputer — nothing new in the covered lanes — C12 stays
    OPEN.** No first-party egress pricing line or product movement
    surfaced.

**Flagged-only (6, below bar):**

1. **Alleged Vercel access-keys/source-code dark-web sale —
   UNVERIFIED, watch-only — unchanged.** A second Sept-28 piece
   (crawled ~3h ago) still traces the claim to the Sept-27 SOCRadar
   Dark Web News report + @DailyDarkWeb headline-only post; the
   aggregator itself rates the listing unverified. A separate June
   piece covers the April ShinyHunters-imposter $2M sale — context
   only. Promotion bar NOT met: no first-party word of a NEW
   incident; the sourcing chain is not two independent reputable
   sources with independent verification. Watch only.
2. **GPT-6.1 "Astra" launch cancellation recirculation — below bar.**
   Frontier-lab safety news (subtraction confirmed), not a
   sandbox/compute-for-agents provider product launch. Watch only.
3. **Third-party GitHub PR adding E2B and Daytona sandbox providers
   to an agent repo — third-party integration news, not provider
   news.** Below the candidate bar.
4. **"Best Agent Sandboxes in 2026" benchmark (33 days old) —
   third-party benchmark, pre-window.** Below the candidate bar.
5. **Agent-infrastructure funding roundups / adjacent repricing —
   adjacent, no sandbox/compute-for-agents product movement —
   below bar.** Not filed.
6. **AMD acquiring World Labs $8.2B — not in-lane.** Model/infra
   M&A, no sandbox product movement. Not filed.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** Hugo CVE-2026-100690 (aggregator-only standing item;
bar remains "file on first-party GHSA appearance only"); Plugin4Shell
(still no real CVE — never cite the suspect CVE-2026-92104); Boxd $2M
pre-seed (closed — recirculation does NOT reactivate); Baseten ×
Blaxel Carbon (private preview, GA not tripped); Mistral Vibe (no new
family member); TermSquad (Sept 15 launch) carried standing;
Boat/Ascii and Microsandbox carried; Docker Cloud Sandboxes (Sept ~24,
pre-window) carried. Aged-out stay out (C29, C45, C56, C66, C67, C62,
Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI); C26 closed.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict stands — streak extends (thirty-second straight quiet
  B-lane scan, C6–C37).
- **Corpus movement:** no new mints, no re-folds, no new age-outs
  this cycle (no dedicated aging queries; aged-out items showed no
  in-window movement). **C11 (Modal/Baseten talks-wave) — still
  unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (37th consecutive read).** Aged-out stay out (C29, C45,
  C56, C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **P49:** the Vercel Drives GA-by-2026-09-28 expectation graded
  NOT MET as observed for the thirteenth consecutive in-cycle pass —
  the expectation window closes at the end of tonight (2026-09-28).
  Not declared dead: Vercel has not cancelled Drives GA; the
  first-party surfaces simply still show Private Beta.
- **Watch-outs for the next slot:** ONE more in-window strategy slot
  remains tonight (23:24 CDT) — the FINAL in-cycle P49 grade rides
  with that last in-window pass; once the window closes (00:00 CT
  Sept 29), stop in-cycle grading and watch Drives for GA as a
  standing tracked item instead. C68 confirmation gate — OpenAI
  DevDay keynote Tue Sep-29 10am PT / 12pm CT (only an actual
  OpenAI confirmation files C68); C11 FILE ON CLOSE (both rounds
  still unclosed — a close announcement files immediately); Modal
  egress billing effective Oct 1 (~2.5 days out — re-confirm
  post-effective-date); the alleged Vercel dark-web credential sale
  stays watch-only (promotion bar unmet); NanoCo as NanoClaw's
  vehicle — first-party sandbox/compute announcement from NanoCo
  meets the re-grade bar; surveyor timestamp-honesty rule in force
  (mtimes = completion evidence).
