# Competitor watch — 2026-09-29 (late-night, cycle 42)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 01:08 CDT 2026-09-29 stat-certified)
against the cycle-41 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (18 first-try
browser.open successes — 17 chain URLs plus the DigitalOcean limits
page via the sibling-URL pattern of the chain's own pricing subpage —
0 failures, 0 searches; every URL carried verbatim from the baseline
capture chain). Surveyor B: delta news scan (snippet level, zero
pages opened, mtime-bounded to 01:08 CDT 2026-09-29 stat-certified) —
**0 CANDIDATES, 9 clean dedupes, 5 flagged-only** (thirty-seventh
straight quiet B-lane scan, C6–C42).

Delta-only against the cycle-41 late-night pass (PR #653's
`docs/COMPETITOR_WATCH_2026-09-29_LATE_C41.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260929-0054.md`,
`hidden_files/agent_notes/surveyor-b-20260929-0054.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded: A-lane to 01:08 CDT 2026-09-29, B-lane to 01:08 CDT
> 2026-09-29 (stat-certified by the integrator from the capture
> mtimes). The B capture's internal "~01:25 CDT" evidence bound is
> inconsistent with its 01:08:27 mtime and is superseded by the
> mtime bound.
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items — items 1–3, 4a–4c (Vercel trio), and 5–9
> no-change (9 items), 0 delta, 0 unverified. Surveyor B's header (0
> CANDIDATES / 9 clean dedupes / 5 flagged-only) agrees with its
> enumerations — no candidate reached the integrator's corpus gate
> this cycle, so no gate-resolution section is needed.
>
> **Fetch-count correction (integrator):** the A-capture's own header
> miscounts "19 first-try successes (18 chain URLs … plus 1 EXTRA)"
> — the limits page is double-counted. Its enumeration governs: 17
> chain URLs + 1 EXTRA re-carry = 18 reads, matching the C41 doc's
> "18 first-try successes — 17 chain URLs plus the DigitalOcean
> limits page". The doc header above carries the corrected count.
> **Integrator fold-gate:** no CANDIDATES this cycle — nothing to
> gate. No new C-numbers, no re-folds, no age-out movement.

## Surveyor A — first-party vendor re-verification (mtime-bounded to 01:08 CDT 2026-09-29)

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
      **Drives GA is a standing tracked item (no in-cycle grading).**
      Not declared dead: Vercel has not cancelled Drives GA; the
      first-party surfaces simply still show beta/private-beta. No GA
      language on this read — no mint triggered.
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
   went-live-early signals (effective date Oct 1, ~2 days out).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (42nd
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
   advisory. The render is still capped at exactly 10 (seventeenth
   consecutive — the ≥14-total bar stays retired in favor of "visible
   list matches baseline enumeration").

**Re-carried (not a baseline delta verdict):** the DigitalOcean "100
sessions/team" detail remains RESTORED on the first-party limits page
(stamp "Last verified 21 Sep 2026"), verbatim: **"You can run up to
100 sessions at once per team depending on your tier."** A per-team
concurrency cap on the limits page, not a pricing figure.

## Surveyor B — delta news scan (snippet level, zero pages opened, mtime-bounded to 01:08 CDT 2026-09-29): 0 CANDIDATES / 9 clean dedupes / 5 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; thirty-seventh straight quiet
B-lane scan (C6–C42). No new sandbox/compute-for-agents provider
product launch, GA, pricing change, or first-party vendor announcement
appeared in-window across any lane.

**Clean dedupes (9):**

1. **Modal "$750M round at $15.75B valuation, led by Accel" — maps to
   standing C11.** TechCrunch (Sept 28, pre-window) still frames
   "closing in on"/"nearing"; Modal declined to comment → no close
   signal; FILE ON CLOSE stays armed.
2. **Baseten "~$26B infusion" — maps to standing C11 (Baseten arm).**
   Coverage uniformly frames talks-level ("discussions"/"in talks") →
   no close signal.
3. **agent-O / OpenAI DevDay — no OpenAI confirmation in-window —
   maps to C68 gate (standing).** Leak/speculation wave only
   ("OpenAI has confirmed no product announcements"). Keynote Tue
   Sep-29 10am PT / 12pm CT (later today — NOT yet happened at survey
   time); only an actual OpenAI confirmation files C68.
4. **NVIDIA Open Agent Safety Platform — recirculation, maps to
   already-folded C70.** Reuters + TechCrunch coverage of the Sept-28
   release (OpenShell v0.1.0 + Sentry on BlueField-4); OpenShell itself
   is March-vintage — the combination layer is the new note, not a new
   provider launch. Recirculation does not re-mint.
5. **Vercel Sandbox Drives — no GA signal in-window — standing tracked
   item.** Snippets restate the Sep 23 public beta; an aged June
   "persistence GA" piece (114 days old, single unverified X post) is
   recirculation, still unverified. No in-cycle grading.
6. **NanoClaw × Docker partnership (March 2026 vintage) —
   recirculation.** All vintage re-description; no first-party NanoCo
   sandbox/compute announcement — re-grade bar stays unmet.
7. **TermSquad Sep-15 launch press recirculation — carried.** Nothing
   new.
8. **Daytona / E2B / AgentComputer / boat.dev / Microsandbox core —
   nothing new in-window.** Boxd "$2M raised" in a comparison table is
   recirculation of a closed round — does NOT reactivate.
9. **Baseten × Blaxel "Carbon" — no fresh movement; private preview,
   GA bar unmet.**

**Flagged-only (5, below bar):**

1. **Docker Agentic Platform experimental public release (Sep 24
   entry, single docs-mirror source) — experimental, below the GA
   bar; single-source, watch-only.**
2. **Docker "commits to bringing the Sandbox Kit Spec to the CNCF" —
   intent statement, single source, not yet submitted — flagged,
   watch-only.**
3. **GPT-6.1 "Astra" cancellation recirculation — frontier-lab model
   news, out of lane, watch-only.**
4. **A-lane reconciliation note (integrator):** two of B's flagged
   items carried stale comparison text from older cycles — the Docker
   release-notes "2026-09-22" topping and Microsandbox's "0.7.2" patch
   evidence are both superseded by this cycle's A-lane first-party
   reads (Docker tops 2026-09-22 as the verified baseline, no change;
   Microsandbox v0.7.3 tops first-party releases, no change). Neither
   is a genuine delta; both stay below bar. First-party reads
   supersede snippet-level framing.
5. **Vercel dark-web credential-sale allegation — carried watch-only.**
   Promotion bar still unmet (no two independent reputable sources,
   no first-party word of a new incident).

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** Hugo CVE-2026-100690 (bar remains "file on
first-party GHSA appearance only"); Plugin4Shell (still no real CVE —
never cite the suspect CVE-2026-92104); Boxd $2M pre-seed (closed —
recirculation does NOT reactivate); Baseten × Blaxel Carbon (private
preview, GA not tripped); Mistral Vibe (no new family member);
TermSquad (Sept 15 launch) carried standing; Boat/Ascii and
Microsandbox carried; Docker Cloud Sandboxes (Sept ~24, pre-window)
carried; DigitalOcean Managed Agents carried; Modal egress billing
effective Oct 1 (~2 days out — re-confirm post-effective-date).
Aged-out stay out (C29, C45, C56, C66, C67, C62 — re-fold path on real
movement; Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI); C26
closed.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict stands — streak extends (thirty-seventh straight quiet
  B-lane scan, C6–C42).
- **Corpus movement:** no new mints, no re-folds, no new age-outs
  this cycle. **C11 (Modal/Baseten talks-wave) — still
  unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (42nd consecutive read).** Aged-out stay out (C29, C45,
  C56, C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **Drives GA post-window:** standing tracked item, watched as an
  open expectation (no in-cycle grading). Not declared dead: Vercel
  has not cancelled Drives GA; its own surfaces simply still show
  beta/private-beta.
- **Watch-outs for the next slot:** C68 confirmation gate — OpenAI
  DevDay keynote Tue Sep-29 10am PT / 12pm CT (TODAY ~12pm CT; only
  an actual OpenAI confirmation files C68 — the next B-slot will
  likely grade the actual keynote against C68); C11 FILE ON CLOSE
  (both rounds still unclosed — a close announcement files
  immediately); Modal egress billing effective Oct 1 (~2 days out —
  re-confirm post-effective-date); Drives GA as a standing tracked
  item (no in-cycle grading); the alleged Vercel dark-web credential
  sale stays watch-only (promotion bar unmet); NanoCo as NanoClaw's
  vehicle — first-party sandbox/compute announcement from NanoCo
  meets the re-grade bar; surveyor timestamp-honesty rule in force
  (mtimes = completion evidence).
