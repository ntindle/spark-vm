# Competitor watch — 2026-09-28 (evening, cycle 40)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 00:01 CDT 2026-09-29 stat-certified)
against the cycle-39 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (18 first-try
browser.open successes — 17 chain URLs plus the DigitalOcean limits
page via the sibling-URL pattern of the chain's own pricing subpage —
0 failures, 0 searches; every URL carried verbatim from the baseline
capture chain). Surveyor B: delta news scan (evidence-bounded since
~23:40 CDT; snippet level, zero pages opened, mtime-bounded to 00:00
CDT 2026-09-29 stat-certified) —
**0 CANDIDATES, 14 clean dedupes, 6 flagged-only** (thirty-fifth
straight quiet B-lane scan, C6–C40).

Delta-only against the cycle-39 evening pass (PR #650's
`docs/COMPETITOR_WATCH_2026-09-28_EVENING_C39.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-2354.md`,
`hidden_files/agent_notes/surveyor-b-20260928-2354.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded: A-lane to 00:01 CDT 2026-09-29, B-lane to 00:00 CDT
> 2026-09-29 (stat-certified by the integrator).
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

## Surveyor A — first-party vendor re-verification (mtime-bounded to 00:01 CDT 2026-09-29)

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
      section still carries the baseline's 3 entries in the same order:
      "Search domains without authentication" first, then "Claude
      Sonnet 5.5 now available on AI Gateway", then "Vercel Sandbox
      now supports memory observability". No Drives GA entry anywhere
      in the rendered window (24–28 September).
      **P49 POST-WINDOW: the GA-by-2026-09-28 window closed at 00:00
      CT Sept 29 during this pass — the cycle-39 FINAL in-cycle
      grade stands: NOT MET as observed. In-cycle grading is over;
      from this cycle Drives GA is a standing tracked item, not an
      in-window deadline.** Not declared dead: Vercel has not
      cancelled Drives GA; the first-party surfaces simply still show
      beta/private-beta. No GA language on this read — no mint
      triggered.
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
   the "Last verified 22 Sep 2026" stamp intact. No change to the five
   baseline figures.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB; overage
   $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals (effective date now under ~24h out).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (40th
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
   advisory. The render is still capped at exactly 10 (fifteenth
   consecutive — the ≥14-total bar stays retired in favor of "visible
   list matches baseline enumeration").

**Re-carried (not a baseline delta verdict):** the DigitalOcean "100
sessions/team" detail remains RESTORED on the first-party limits page
(stamp "Last verified 21 Sep 2026"), verbatim: **"You can run up to
100 sessions at once per team depending on your tier."** A per-team
concurrency cap on the limits page, not a pricing figure.

## Surveyor B — delta news scan (evidence-bounded since ~23:40 CDT, mtime-bounded to 00:00 CDT 2026-09-29): 0 CANDIDATES / 14 clean dedupes / 6 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; thirty-fifth straight quiet
B-lane scan (C6–C40). No new sandbox/compute-for-agents provider
product launch, GA, pricing change, or first-party vendor announcement
appeared in-window across any lane.

**Clean dedupes (14):**

1. **Modal "$750M round at $15.75B valuation, led by Accel" — maps to
   standing C11.** TechCrunch (Sept 28, pre-window) still frames
   "nearing"/"closing in on"; fresh syndications recycle identical
   talks-level framing; Modal Labs declined to comment → no close
   signal; FILE ON CLOSE stays armed.
2. **Baseten "~$26B infusion" — maps to standing C11 (Baseten arm).**
   Coverage uniformly frames talks-level ("have not produced
   completed rounds") → no close signal.
3. **agent-O / OpenAI DevDay — no OpenAI confirmation in-window —
   maps to C68 gate (standing).** Fresh Sept-27/28 rumor pieces
   ("12+ products tomorrow", leak roundups) all keep leak framing.
   RuntimeWire explicitly: OpenAI has confirmed no product
   announcements. Keynote Tue Sep-29 10am PT / 12pm CT (today) remains
   the confirmation gate; only an actual OpenAI confirmation files
   C68.
4. **Daytona lane — third-party comparison pieces only, below bar.**
   Methodology comparisons on published figures; pre-window funding
   vintage. No new Daytona provider news.
5. **NVIDIA Open Agent Safety Platform — recirculation, maps to
   already-folded C70.** New Sept-28 syndications describe the same
   launch (OpenShell + Sentry, Apache 2.0, 100+ partners). No new mint.
6. **Vercel Sandbox Drives — no GA signal in-window; still public
   beta — standing tracked item from here on.** First-party snippet
   ("Drives for Vercel Sandbox are now in public beta") and the Sept-23
   public-beta explainer confirm Public Beta, not GA. **The in-cycle
   grading window closed at 00:00 CT Sept 29 during this scan** —
   cycle-39's FINAL in-cycle grade stands: NOT MET as observed. Not
   declared dead — Vercel has not cancelled Drives GA; it is now a
   standing tracked item.
7. **Docker Cloud Sandboxes launch (Sept 24) — pre-window, carried.**
   Syndication recirculation; no in-window movement.
8. **DigitalOcean Managed Agents public preview (Sept 21/22) —
   pre-window recirculation, carried.** Recaps of the same event; no
   new movement.
9. **NanoClaw × Docker partnership (March 2026 vintage) —
   recirculation.** Re-described deal pieces; no first-party NanoCo
   sandbox/compute announcement — re-grade bar stays unmet.
10. **NanoClaw-to-Slack (venturebeat, pre-window) — agent product
    feature, not a sandbox/compute provider launch.** Re-grade bar
    unmet. Not filed.
11. **Third-party sandbox pricing comparisons — not provider news.**
    Methodology comparisons on published figures; no provider pricing
    change. Below bar.
12. **TermSquad / AgentComputer / boat.dev — nothing new in-window.**
    AgentComputer still shows no first-party egress pricing line —
    **C12 stays OPEN** (40th consecutive first-party read).
13. **Microsandbox — nothing new provider-side.** Community third-party
    docs only; no release or vendor news. Carried.
14. **E2B — nothing new in any searched lane.** No release or provider
    news surfaced; carried.

**Flagged-only (6, below bar):**

1. **Alleged Vercel access-keys/source-code dark-web sale —
   UNVERIFIED, watch-only — unchanged.** No new confirming evidence
   in-window; promotion bar NOT met: no first-party word of a NEW
   incident; the sourcing chain is not two independent reputable
   sources with independent verification. Watch only.
2. **OpenAI DevDay eve rumor-dump pieces ("12+ products tomorrow") —
   rumor recirculation, not confirmation.** Pre-keynote leak/
   speculation pieces; below the C68 gate bar. Watch only.
3. **Adjacent out-of-lane infra M&A/deals — not filed.** Samsung's
   $1B commitment to the KKR-backed Helix Digital AI buildout, AMD's
   $8.2B all-stock World Labs acquisition, Megaport's $687M
   AI-infrastructure deals — adjacent to AI infrastructure, but no
   sandbox/compute-for-agents provider launch, GA, or pricing change.
   Watch color only.
4. **Modal July customer-data compromise — pre-window recount,
   watch-only.** A Sept-28 third-party syndication recounts a July
   disclosure (client-side code vulnerabilities, not Modal's own
   systems). Not a NEW incident and not first-party; below the
   promotion bar. Watch only.
5. **NanoClaw × JFrog "immune system" (June 2026 vintage) —
   recirculation.** Agent dependency-scanning integration feature;
   agent security, not a sandbox/compute provider launch. Below the
   re-grade bar. Not filed.
6. **Frontier-lab model/subtraction news, carried — out of lane.**
   OpenAI halting AI training, GPT-6.1 "Astra" cancellation
   recirculation — model-lab news, not provider sandbox/compute
   news. Watch only.

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
  verdict stands — streak extends (thirty-fifth straight quiet
  B-lane scan, C6–C40).
- **Corpus movement:** no new mints, no re-folds, no new age-outs
  this cycle. **C11 (Modal/Baseten talks-wave) — still
  unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (40th consecutive read).** Aged-out stay out (C29, C45,
  C56, C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **P49:** the Vercel Drives GA-by-2026-09-28 window closed at 00:00
  CT Sept 29 with the final in-cycle grade NOT MET as observed
  (cycle-39). In-cycle grading is over — Drives GA is now a standing
  tracked item watched as an open expectation. Not declared dead:
  Vercel has not cancelled Drives GA; its own surfaces simply still
  show beta/private-beta.
- **Watch-outs for the next slot:** C68 confirmation gate — OpenAI
  DevDay keynote Tue Sep-29 10am PT / 12pm CT (today; only an actual
  OpenAI confirmation files C68); C11 FILE ON CLOSE (both rounds
  still unclosed — a close announcement files immediately); Modal
  egress billing effective Oct 1 (under ~24h out — re-confirm
  post-effective-date); Drives GA now a standing tracked item (no
  in-cycle grading); the alleged Vercel dark-web credential sale
  stays watch-only (promotion bar unmet); NanoCo as NanoClaw's
  vehicle — first-party sandbox/compute announcement from NanoCo
  meets the re-grade bar; surveyor timestamp-honesty rule in force
  (mtimes = completion evidence).
