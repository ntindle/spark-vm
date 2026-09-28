# Competitor watch — 2026-09-28 (evening, cycle 29)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 18:27:00 CDT stat-certified) against the
cycle-28 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (16 first-try
fetches succeeded, 0 failures; no searches needed — every URL carried
verbatim from the baseline capture chain). Surveyor B: delta news scan
(evidence-bounded since ~18:00 CDT; snippet level, zero pages opened,
mtime-bounded to 18:26:45 CDT stat-certified) — **0 CANDIDATES,
5 clean dedupes, 1 flagged-only** (twenty-fourth straight quiet B-lane
scan, C6–C29).

Delta-only against the cycle-28 evening pass
(`docs/COMPETITOR_WATCH_2026-09-28_EVENING_C28.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-1824.md`,
`hidden_files/agent_notes/surveyor-b-20260928-1824.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded: A-lane to 18:27:00 CDT, B-lane to 18:26:45 CDT
> (stat-certified by the integrator).
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items. Surveyor B's header (0 CANDIDATES /
> 5 clean dedupes / 1 flagged-only) agrees with its enumerations —
> no candidate reached the integrator's corpus gate this cycle, so no
> gate-resolution section is needed.
>
> **Coverage disclosure:** surveyor B's capture carries several items
> (Modal egress billing effective date, Hugo CVE-2026-100690
> aggregator-only standing item, Plugin4Shell, Boxd, Baseten×Blaxel
> Carbon, NanoClaw, Mistral Vibe, Daytona/E2B funding) as
> not-re-queried with coverage disclosure — carried below as standing,
> NOT asserted as re-verified, per precedent. AgentComputer's C12
> status IS asserted re-verified this cycle (surveyor A lane, 29th
> consecutive first-party read — see item 7).
>
> **Integrator fold-gate:** no CANDIDATES this cycle — nothing to
> gate. The one item that could read as new (the Sept-28 NVIDIA Open
> Agent Safety Platform / OpenShell v0.1.0 GA coverage in surveyor B's
> flagged-only section) resolves as the **already-folded C70** —
> surveyor B's own capture files it flagged-only, not as a candidate,
> so there is no double-fold risk.

## Surveyor A — first-party vendor re-verification (mtime-bounded to 18:27:00 CDT)

**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Still SEP 26 2026 /
   V0.218.0 (KVM sandbox parameter + CLI WorkOS application); second
   still SEP 25 / V0.217.0 (NVIDIA B300 GPU). No V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out 2026-09-22; the 2026-09-21 v3-kits entry verbatim unchanged.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still v0.7.3; no
   v0.7.4+ tag.
4. **Vercel changelog index + Sandbox docs + Drives page — VERIFIED
   NO-CHANGE.** The "28 September" section still has exactly the C28
   two entries (Claude Sonnet 5.5 on AI Gateway; Sandbox memory
   observability) — no Drives GA entry. Sandbox docs still
   `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
   Features list. The dedicated Drives page still says "in Private
   Beta" with an active waitlist — no GA language. **P49 IN-CYCLE
   VERDICT: NOT MET as observed** (fifth consecutive in-cycle
   grading). The expectation's window closes tonight; the final grade
   rides with the last in-window pass — this watch does not declare
   the expectation dead.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB; overage
   $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals (~2.2 days to the effective date).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (29th
   consecutive first-party read, no wording drift).
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively. Migration-complete state holds.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE (bar retired).**
   The four Sep-28 Moderate advisories still top the list; no
   100690-specific advisory. The 5 Sep-9 + 1 Aug-27 advisories still
   visible below, matching the baseline's enumerated set verbatim.
   Bar status per the cycle-27 disclosure: the standing "≥14
   advisories total" bar was retired in C27 after two consecutive
   single-page renders capped at exactly 10 (the baseline's enumerated
   10: 4 Sep-28 + 5 Sep-9 + 1 Aug-27); the replacement bar "visible
   list matches baseline enumeration" holds this cycle (fourth
   consecutive capped render). No removed advisory evidenced.

## Surveyor B — delta news scan (evidence-bounded since ~18:00 CDT, mtime-bounded to 18:26:45 CDT): 0 CANDIDATES / 5 clean dedupes / 1 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; twenty-fourth straight quiet
B-lane scan (C6–C29).

**Clean dedupes (5):**

1. **Modal "$750M round at $15.75B valuation, led by Accel" — maps to
   standing C11.** A Sept-28 TechCrunch piece uses only
   "nearing"/"closing in" language; Modal declined to comment; the
   round is NOT closed → no C-number minted, gate resolves to the
   standing watch. (techcrunch.com, Sept 28, 2026)
2. **Baseten "nearing an infusion of capital at a $26 billion
   valuation" per Bloomberg (cited in the same TechCrunch piece) —
   maps to standing C11 (Baseten arm).** Still "nearing", not closed
   → no new entry.
3. **Vercel Sandbox Drives — pre-window third-party coverage only.**
   The beta announcement (Sept 23, 2026) and feature detail (Drives in
   beta "until deletion", one read-write mount + read-only snapshots)
   are pre-window; no GA evidence in-window → P49 NOT MET confirmed
   for this cycle.
4. **agent-O / OpenAI DevDay — no OpenAI confirmation in-window.**
   Only third-party leak speculation (YouTube AI-news coverage). C68
   gate stands: DevDay keynote Tue Sep-29 10am PT / 12pm CT is the
   confirmation gate; only an actual OpenAI confirmation files C68.
5. **Third-party sandbox-integration docs — consumer tooling, below
   bar.** A set of pre-window, third-party-only docs (madarco/agentbox,
   twillai/agentbox-sdk, betalyra/effect-uai, zhuyansen/jasonzhu.ai,
   multigent/multigent, brightwave-inc/tidebreak) — none is
   first-party provider news; none re-filed.

**Flagged-only (1, below bar):**

1. **NVIDIA Open Agent Safety Platform (Sept 28, 2026 — in-window).**
   OpenShell (Apache 2.0 agent sandbox runtime, now generally
   available at v0.1.0; gateway + kernel-level sandbox + per-sandbox
   supervisor) paired with Sentry (hardware-backed monitoring
   reference design on BlueField-4 DPUs, not GA, no price); 100+
   partners named (Anthropic, Microsoft, CrowdStrike, Cisco, Palantir,
   SpaceXAI per coverage); framed as a response to the summer agent
   sandbox escapes. Safety-adjacent-but-not-provider per the standing
   rule → flagged-only, below bar, no C-number — and NOT a new corpus
   entry: the GA story is the already-folded C70, so this resolves as
   a carried standing item, not a fold.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** Modal egress billing effective Oct 1, 2026 (no
went-live-early reported); Hugo CVE-2026-100690 (aggregator-only
standing item; no first-party GHSA/advisory in-window); Plugin4Shell
(still no real CVE; never cite the suspect "CVE-2026-92104"); Boxd
$2M pre-seed (C29 closed — recirculation does NOT reactivate);
Baseten × Blaxel Carbon (private preview, GA not tripped); NanoClaw
(re-grade only on first-party sandbox/compute announcement); Mistral
Vibe (no new family member); Daytona/E2B funding (no new rounds;
Daytona's $24M Series A remains the last confirmed raise).

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (twenty-fourth
  straight quiet B-lane scan, C6–C29). The one corpus-adjacent item
  this cycle (NVIDIA OpenShell v0.1.0 GA coverage) is the
  already-folded C70 — no corpus movement.
- **Corpus movement (P63):** no new mints, no re-folds, no new
  age-outs this cycle (no dedicated aging queries; aged-out items
  showed no in-window movement). **C11 (Modal/Baseten talks-wave) —
  still unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (29th consecutive read).** Aged-out stay out (C29, C45,
  C56, C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **Watch-outs for the next slot:** P49's final grade rides with the
  last in-window pass tonight (fifth in-cycle NOT-MET recorded this
  cycle); Modal egress billing goes effective Oct 1 (~2.2 days out —
  first-party re-confirm post-effective-date); agent-O DevDay
  confirmation gate Tue Sep-29 10am PT / 12pm CT (only an actual
  OpenAI confirmation files C68); Hugo GHSA sweep (full URL —
  shorthand 404s) — the CVE-2026-100690 bar stays "file on first-party
  GHSA appearance, aggregator-only stays out"; NanoClaw/NanoCo
  re-grade only on first-party sandbox/compute announcement; Mistral
  Vibe re-fold bar; Plugin4Shell real-CVE watch (never cite the
  suspect CVE-2026-92104); Boxd recirculation (C29 — do not
  re-activate on recirculation); Carbon private-preview
  (Baseten×OpenShell cross-lane note); surveyor timestamp-honesty rule
  in force (mtimes = completion evidence).
