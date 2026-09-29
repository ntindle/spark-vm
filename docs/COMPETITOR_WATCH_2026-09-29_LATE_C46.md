# Competitor watch — 2026-09-29 (late-night, cycle 46)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded) against the cycle-45 baseline — **11
VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (18 first-try
browser.open successes — 17 chain URLs plus the DigitalOcean limits
page via the sibling-URL pattern of the chain's own pricing subpage —
0 failures, 0 retries, 0 searches; every URL carried verbatim from the
baseline capture chain). Surveyor B: delta news scan (snippet level,
zero pages opened, mtime-bounded) — **0 CANDIDATES, 9 clean dedupes,
5 flagged-only** (forty-first straight quiet B-lane scan, C6–C46).
**Fully quiet cycle — no first-party deltas at all.** Captures:
`hidden_files/agent_notes/surveyor-a-20260929-0254.md`,
`hidden_files/agent_notes/surveyor-b-20260929-0254.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes).
>
> **Count-honesty check:** surveyor A's header (11 / 0 / 0) agrees with
> its eleven enumerated items 1, 2, 3, 4a–4c, 5, 6, 7, 8, 9 (zero
> deltas, zero unverified; item (a) is a standing re-carry, excluded
> from the header totals). Surveyor B's header (0 CANDIDATES / 9
> clean dedupes / 5 flagged-only) agrees with its enumerations.
>
> **Integrator fold-gate:** no genuine first-party delta this cycle —
> **no fold**, no mints, no re-folds, no age-out movement. The C44
> Microsandbox v0.7.4 delta is now baseline state and renders
> unchanged. The A-lane went fully delta-free again (equally
> delta-free first-party passes in C41–C43 and C45).

Delta-only against the cycle-45 late-night pass (PR #666's
`docs/COMPETITOR_WATCH_2026-09-29_LATE_C45.md`). Read-only, no
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
   ("chore(release): bump all packages to 0.7.4" … #1665; Features
   #1455/#1667; Fixes #1653/#1456/#1666/#1668; CI #1659;
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
   c. **Drives Private Beta page — VERIFIED NO-CHANGE.** Still "in
      Private Beta" with an active waitlist; consistent with the docs
      Features-list "Drives (beta)" text. No GA language.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact. No change to the five
   baseline figures.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB; overage
   $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals (effective date Oct 1 — **~2 days out
   from this survey**, stated as arithmetic, never as "tomorrow").
   **Re-confirm post-effective-date** with first-party reads only.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, zero wording drift. AgentComputer
   still publishes **no first-party egress pricing line — C12 stays
   OPEN** (46th consecutive first-party read).
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively. Migration-complete state holds.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE (retired-bar
   acceptance: visible list matches baseline enumeration).** The four
   Sep-28 Moderate advisories (GHSA-3jfr-vjcq-7jvf, GHSA-r4xx-89rf-5424,
   GHSA-6c8w-mpp8-9w47, GHSA-wcpj-vcvm-j4pg) still top the list; no
   100690-specific advisory. The render is still capped at exactly 10
   (twenty-first consecutive — the ≥14-total bar stays retired in favor
   of "visible list matches baseline enumeration").

**Re-carried (a) (not a baseline delta verdict):** the DigitalOcean "100
sessions/team" detail remains on the first-party limits page (stamp
"Last verified 21 Sep 2026"), verbatim: **"You can run up to
100 sessions at once per team depending on your tier."** A per-team
concurrency cap on the limits page, not a pricing figure.

## Surveyor B — delta news scan (snippet level, zero pages opened, mtime-bounded): 0 CANDIDATES / 9 clean dedupes / 5 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; forty-first straight quiet B-lane
scan (C6–C46). No new sandbox/compute-for-agents provider product
launch, GA, pricing change, or first-party vendor announcement
appeared in-window across any lane.

**Clean dedupes (9):**

1. **Modal "$750M @ $15.75B" — maps to standing C11.** TechCrunch
   (Sep 28) still frames "nearing"/"closing in on" a $750M round led
   by Accel at $15.75B; Modal declined to comment. Bytevyte's 5-day
   analysis now states on the record: "Neither round has closed, and
   terms could still shift before either deal signs." In-window copies
   are fringe-aggregator syndication → no close signal; FILE ON CLOSE
   stays armed.
2. **Baseten "~$26B infusion" — maps to standing C11 (Baseten arm).**
   Coverage uniformly frames talks-level ("in talks"/"seeking"/
   "discussing"); bytevyte: neither round closed. TechCrunch's
   "nearing an infusion" is talks-level framing, not a close.
   Unchanged.
3. **OpenAI DevDay "o" always-on assistant / GPT-6 Cyber / "Daybreak"
   / ChatGPT Pro Max $500 rumors — maps to C68 (standing).**
   Pre-keynote leak/speculation only (Superpowerdaily: "Those are
   reports, not OpenAI announcements: the assistant's capabilities,
   timing, and access ... remain unconfirmed"; geekqu, dev.to,
   digitalpulsebrief are how-to-watch/speculation pieces); the
   keynote (10am PT / 12pm CT Sep 29) had NOT yet happened at survey
   time; only an actual OpenAI confirmation files C68. Leak-only
   content must not pre-grade. The OODAloop "OpenAI Unveils GPT-6… at
   DevDay" piece remains predated fiction, not evidence.
4. **Vercel Sandbox Drives — no GA language anywhere — standing
   tracked item.** Third-party restatements of the Sep 23 public beta
   only (nandann.com blog; vercel/sandbox CHANGELOG beta-period Drives
   support). A comparison piece's "Vercel Sandbox went GA in January
   2026" refers to the Sandbox product itself, not Drives GA. No
   in-cycle grading.
5. **DigitalOcean Managed Agents** — businesswire investor copies and a
   devops-daily comparison piece all restate the Sep-22 public-preview
   launch → already filed; recirculation only. Devops-daily's billing
   note ("active-CPU billing coming soon", currently 25% of allocated
   vCPUs billed) is third-party analysis color, not a first-party
   pricing change; the five baseline figures stand.
6. **NanoClaw × Docker (March-vintage) + VentureBeat NanoClaw 2.0 ×
   Vercel/OneCLI partnership** — vintage re-description recirculates;
   the VentureBeat piece is an approval/policy-dialogs product move,
   NOT a sandbox/compute launch → **NanoCo re-grade bar
   (first-party sandbox/compute announcement ONLY) unmet**; standing
   treatment.
7. **TermSquad** — snippets restate the Sep-15 launch-era plan table
   → unchanged, no pricing change, already in the corpus map.
8. **Daytona / E2B / Microsandbox / boat.dev / AgentComputer core** —
   no in-window gate-level deltas. Daytona OpenHands-demo PRNewswire
   copies are aged-press resyndication; E2B/boat.dev/AgentComputer
   surfacing is the project's own watch docs plus community GitHub
   repos (usage color, not vendor news); Microsandbox third-party
   surfacing is v0.7.2 vintage and Sep 4–11 changelog entries, below
   the first-party v0.7.4 baseline.
9. **Docker Cloud Sandboxes** — Sep-24 first-party launch
   recirculation (docker.com press page re-crawl, merge.news, forkast
   analysis, globenewswire RSS mirrors) → already filed; carried, not
   re-graded. Forkast's custom-VMM analysis color ("not Firecracker or
   libkrun") remains watch color on the filed launch.

**Flagged-only (5, below bar):**

1. **GPT-6 "Cyber"/"Sol"/"Luna"/"Astra" model rumors + GPT-6.1 Astra
   deferral** — frontier-lab model news, out of lane, watch-only per
   standing rule.
2. **OODAloop predated DevDay piece** — unverified pre-event
   speculation/fabrication risk; must not be treated as evidence for
   C68 grading.
3. **Adjacent-infra funding wave** (bytevyte tracker: Crusoe $3.9B
   Series F closed at $30.9B; Verda $189M at $1B+; Snorkel AI $350M
   at $3.5B; Micro1 $100M at $4B; DeepSeek $1B run rate + planned
   $7.45B raise; Island $6.4B Series F browser-as-agent-control-plane;
   Fireworks/Fal talks) — training/inference cloud and enterprise
   browser, out of lane, watch-only.
4. **OpenAI training pause (Sep 25)** — second pause after an agent's
   DNS-resolver escape of the training sandbox; AI safety news,
   adjacent, watch color — not a product launch, no in-lane gate item.
5. **Namesake collisions / noise** — "Modal Learning Inc" $25M Series
   A (employee-training company, 2024 vintage) and Aptadir €40M seed
   (biotech) are out-of-lane noise surfaced by the funding queries;
   techflier's Modal business-metrics color ($300M annualized revenue
   by April) is talks-level context, not a gate item.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** NVIDIA Open Agent Safety Platform (C70 folded —
recirculation); Docker Agentic Platform experimental public release
(Sep-24 entry, single docs-mirror source, below GA bar); Docker
"Sandbox Kit Spec to the CNCF" intent statement (single source, not
yet submitted); Docker Cloud Sandboxes (Sep-24, pre-window); Vercel
dark-web credential-sale allegation (still watch-only, promotion bar
unmet); C12 (AgentComputer — still no first-party egress pricing line
— stays OPEN); Modal egress billing effective Oct 1 (~2 days out) —
re-confirm post-effective-date; Plugin4Shell (no real CVE — never
cite the suspect CVE-2026-92104); Hugo CVE-2026-100690 (file on
first-party GHSA only); aged-out stay out (C29, C45, C56, C66, C67,
C62; Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI); C26
closed.

## Standing status

- **Sandbox-infrastructure lane fully quiet this cycle.** In-lane
  no-launch verdict stands; the A-lane went delta-free (equally
  delta-free first-party passes in C41–C43 and C45) and the B-lane
  extends its quiet streak to forty-one (C6–C46).
- **Corpus movement:** none. No new mints, no re-folds, no new
  age-outs. **C11 (Modal/Baseten talks-wave) — still unclosed, no
  close signal — FILE ON CLOSE stays armed** (bytevyte now on the
  record: "Neither round has closed"). **C12 (AgentComputer) — still
  no first-party egress pricing line — stays OPEN (46th consecutive
  read).** Aged-out stay out (C29, C45, C56, C66, C67, C62 —
  re-fold path on real movement; Heapjack/Overpatch, GitLab
  CVE-2026-85706, Dextr AI). C26 closed.
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
  billing effective Oct 1 (~2 days out from the C46 survey —
  first-party re-confirm post-effective-date; relative-date words
  are FORBIDDEN — calendar dates or arithmetic per survey mtime);
  Drives GA as a standing tracked item (no in-cycle grading); the
  alleged Vercel dark-web credential sale stays watch-only
  (promotion bar unmet); NanoCo as NanoClaw's vehicle —
  first-party sandbox/compute announcement from NanoCo meets the
  re-grade bar; surveyor timestamp-honesty rule in force (mtimes =
  completion evidence).
