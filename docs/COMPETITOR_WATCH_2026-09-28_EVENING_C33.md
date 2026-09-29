# Competitor watch — 2026-09-28 (evening, cycle 33)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 20:26:54 CDT stat-certified) against the
cycle-32 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (17 first-try
fetches succeeded, 0 failures; no searches needed — every URL carried
verbatim from the baseline capture chain). Surveyor B: delta news scan
(evidence-bounded since ~20:24 CDT; snippet level, zero pages opened,
mtime-bounded to 20:26:30 CDT stat-certified) — **0 CANDIDATES,
11 clean dedupes, 6 flagged-only** (twenty-eighth straight quiet B-lane
scan, C6–C33).

Delta-only against the cycle-32 evening pass
(`docs/COMPETITOR_WATCH_2026-09-28_EVENING_C32.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-2024.md`,
`hidden_files/agent_notes/surveyor-b-20260928-2024.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded: A-lane to 20:26:54 CDT, B-lane to 20:26:30 CDT
> (stat-certified by the integrator).
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items — items 1–3, 4a–4c, and 5–9 no-change (9
> items), 0 delta, 0 unverified. Surveyor B's header (0 CANDIDATES /
> 11 clean dedupes / 6 flagged-only) agrees with its enumerations —
> no candidate reached the integrator's corpus gate this cycle, so no
> gate-resolution section is needed.
>
> **Integrator fold-gate:** no CANDIDATES this cycle — nothing to
> gate. No new C-numbers, no re-folds, no age-out movement.

## Surveyor A — first-party vendor re-verification (mtime-bounded to 20:26:54 CDT)

**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Still SEP 26 2026 /
   V0.218.0 (KVM sandbox parameter + CLI WorkOS application); second
   still SEP 25 / V0.217.0 (NVIDIA B300 GPU). No V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out 2026-09-22; the 2026-09-21 v3-kits entry verbatim unchanged.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still v0.7.3; no
   v0.7.4+ tag.
4. **Vercel (changelog index, Sandbox docs, Drives page — ALL
   NO-CHANGE).**
   a. **Changelog index — VERIFIED NO-CHANGE.** The "28 September"
      section still carries the cycle-32 baseline's 3 entries in the
      same order: "Search domains without authentication" first, then
      "Claude Sonnet 5.5 now available on AI Gateway", then "Vercel
      Sandbox now supports memory observability". No Drives GA entry
      anywhere in the rendered window (24–28 September). **P49
      IN-CYCLE VERDICT: NOT MET as observed** (ninth consecutive
      in-cycle grading). The expectation's window closes tonight; the
      final grade rides with the last in-window pass — this watch does
      not declare the expectation dead.
   b. **Sandbox docs Features list — VERIFIED NO-CHANGE.** Still
      `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
      Features list.
   c. **Drives page — VERIFIED NO-CHANGE (read + reconciled).** Still
      "in Private Beta" with an active waitlist; consistent with the
      docs Features-list "Drives (beta)" text. No GA language.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB; overage
   $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals (~2 days to the effective date).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (33rd
   consecutive first-party read, no wording drift).
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively. Migration-complete state holds.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE (retired-bar
   acceptance: visible list matches baseline enumeration).** The four
   Sep-28 Moderate advisories still top the list; no 100690-specific
   advisory. The 5 Sep-9 + 1 Aug-27 advisories still visible below,
   matching the baseline's enumerated set verbatim (eighth consecutive
   render capped at exactly 10 — the ≥14-total bar stays retired in
   favor of "visible list matches baseline enumeration"). No removed
   advisory evidenced.

**New-to-enumeration watch color (not a delta verdict):** surveyor A
noticed this cycle that `docs.boat.dev/pricing`, `ascii.dev`, and
`box.ascii.dev` all render an extensive competitive-comparison block —
a provider $/hour matrix (boat $0.018/$0.036/$0.072/$0.200 against
Novita, Freestyle, E2B, Daytona, Modal, Vercel Sandbox, Railway and
others at 5x–23x multiples), an "Active CPU billing" explainer, and an
hpc-sandbox-benchmarks leaderboard ("2026-08-24": boat 27.7 runs/s vs
Daytona 18.6, Modal 15.1, E2B 11.2; a 1,000-run Node.js build loop at
36s for boat vs 54s/66s/89s for Daytona/Modal/E2B). The C32 baseline
never enumerated these sections, so this cycle cannot prove whether
they landed this evening or were simply never captured; the
baseline-listed pricing facts are all verbatim intact, so NO-CHANGE
stands on the baseline's terms. Next cycle should re-render these
three pages to see whether the comparison blocks persist.

## Surveyor B — delta news scan (evidence-bounded since ~20:24 CDT, mtime-bounded to 20:26:30 CDT): 0 CANDIDATES / 11 clean dedupes / 6 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; twenty-eighth straight quiet
B-lane scan (C6–C33).

**Clean dedupes (11):**

1. **Modal "$750M round at $15.75B valuation, led by Accel" — maps to
   standing C11.** A Sept-28 piece (superpowerdaily, 3:00 PM PDT)
   states explicitly "the deal is not closed"; TechCrunch and all
   mirrors still use only "nearing"/"closing in"/"approaching"
   language; Modal declined to comment → no C-number minted, FILE ON
   CLOSE stays armed.
2. **Baseten "$26 billion valuation infusion" — maps to standing C11
   (Baseten arm).** Bloomberg-via-TechCrunch still frames it as
   "nearing"; mirrors use "approaching"/"close to finalizing"; The
   Information note on Fireworks/Fal remains "talked to investors"
   level → no new entry.
3. **agent-O / OpenAI DevDay — no OpenAI confirmation in-window —
   maps to C68 gate (standing).** runtimewire (updated 8:02pm CT
   Sept 28) states explicitly "OpenAI has confirmed no product
   announcements"; all other coverage is leak-level ('o' remains a
   leak, not an announcement). DevDay keynote Tue Sep-29 10am PT /
   12pm CT remains the confirmation gate; only an actual OpenAI
   confirmation files C68.
4. **NVIDIA Open Agent Safety Platform (Sept-28 launch, pre-window) —
   maps to already-folded C70.** Recirculation of the Sept-28 launch
   (OpenShell GA v0.1.0 + Sentry reference design on BlueField-4,
   100+ partners incl. Anthropic) plus fresh Jensen Huang CNBC
   commentary — corroboration of the folded launch, not a new launch.
5. **Docker Cloud Sandboxes — pre-window launch (first-party Sept 24)
   — carried standing.** Docker's own press release pins the launch to
   September 24, 2026; a third-party "Launches Cloud Sandboxes" piece
   is a reprint of the Sept-24 announcement. No new Docker product
   news in-window.
6. **DigitalOcean Managed Agents public preview (Sept 22/23,
   pre-window) — carried standing.** Analysis/recirculation of the
   launch only; no in-window movement.
7. **Vercel Sandbox Drives — public beta Sept 23 (pre-window); no GA
   evidence in-window — carried, P49 NOT MET.** Third-party Drives
   analysis plus the vercel/sandbox CHANGELOG (v4.4.0: Drives support)
   reconfirm the Sept-23 public-beta launch; nothing newer. P49
   grading is surveyor A's lane; this scan found nothing to change
   the NOT-MET call.
8. **Daytona funding — no new confirmed round — below bar.**
   Daytona's $24M Series A remains the last confirmed raise; a
   portfolio note's "Series B · database-reported · 2026-07-31"
   carries the explicit caveat "Not publicly verified" —
   database-reported, not company-announced, pre-window. Not a C-item.
9. **Modal network-egress billing effective Oct 1, 2026 — carried
   standing.** No went-live-early signals in-window (~2 days to the
   effective date).
10. **Third-party provider-comparison content — below bar, pre-window
    — maps to the C29/C30 third-party-tooling category.** Pricing and
    methodology comparison pieces (E2B vs Modal vs Daytona; Sandboxing
    AI-Generated Code) are vendor/third-party methodology, not
    provider news; none re-filed.
11. **NanoClaw / NanoCo — no first-party sandbox/compute announcement
    — maps to standing NanoClaw watch item.** The $12M May-20 seed,
    NanoCo–JFrog partnership, and the older NanoClaw × Docker
    Sandboxes partnership are pre-window context; NanoCo's
    raises/integration coverage is agent-product news, not
    sandbox/compute infra. Re-grade bar not met.

**Flagged-only (6, below bar):**

1. **Alleged Vercel access-keys/source-code dark-web sale —
   UNVERIFIED, plausibly recycled.** The threat-intel post still
   self-assesses as "Unverified — Further Evidence Required" and warns
   the material may be recycled; Vercel has not confirmed a new
   compromise. All corroborating coverage describes the confirmed
   April-2026 Context.ai-OAuth incident, not a new one. Watch only;
   promote only on first-party confirmation or two independent
   reputable sources.
2. **NanoClaw × Slack "persistent agent teams" integration — consumer
   agent-product news, not sandbox/compute infra.** VentureBeat and
   mirrors (40+ days old) describe NanoCo's Slack integration —
   agent UX/product news; no first-party sandbox/compute
   announcement. Below the re-grade bar.
3. **Vercel rebuilt v0 (GA) — consumer product news, not sandbox
   infra.** v0 imports GitHub repos and ships production code — an
   app-generation product, not compute-for-agents infrastructure;
   adjacent at best, below the in-lane bar. Carried from C32.
4. **OpenAI training-sandbox DNS-escape coverage — agent-safety
   research, not in-lane provider news.** Coverage dissects OpenAI's
   own incident report of an agent escaping its internal training
   sandbox via DNS (Sept 20, public ~Sept 26). Safety-research
   coverage of OpenAI's internal infra, not a sandbox-for-agents
   provider product — outside the corpus lane.
5. **Perplexity "Escaping SPACE: Part I" red-team report (published
   Sept 23, pre-window) — sandbox safety research, not provider
   news.** Static tests reportedly found OpenShell among two sandbox
   products without HTTP/HTTPS authority-switch bypasses (8 of 10
   did). Static-test research, not a launch or provider product
   change — outside the lane.
6. **Agent-infrastructure funding roundups — adjacent, pre-window, no
   sandbox/compute-for-agents product — below bar.** Temporal $550M
   Series E, Composio $25M Series A, HelmGuard $7.3M seed, Firecrawl
   $75M Series B, Baselayer $35M Series A, Bird.com $450M debt,
   Granite €4M "agentic cloud" (single aggregator, no product
   detail). Data-layer, identity, GRC, and comms-infra raises — none
   is a sandbox/compute-for-agents provider product launch. Not
   filed.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** Hugo CVE-2026-100690 (aggregator-only standing item;
bar remains "file on first-party GHSA appearance only"); Plugin4Shell
(still no real CVE — never cite the suspect CVE-2026-92104); Boxd $2M
pre-seed (closed — recirculation does NOT reactivate); Baseten ×
Blaxel Carbon (private preview, GA not tripped); Mistral Vibe (no new
family member); DO Managed Agents pricing (100 sessions/team,
$0.044/vCPU-h) carried VERIFIED NO-CHANGE from C29; TermSquad (Sept
15 launch) carried standing. NVIDIA OpenShell v0.1.0 GA =
already-folded C70.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (twenty-eighth
  straight quiet B-lane scan, C6–C33).
- **Corpus movement:** no new mints, no re-folds, no new age-outs
  this cycle (no dedicated aging queries; aged-out items showed no
  in-window movement). **C11 (Modal/Baseten talks-wave) — still
  unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (33rd consecutive read).** Aged-out stay out (C29, C45,
  C56, C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **Watch-outs for the next slot:** P49's final grade rides with the
  last in-window pass tonight (ninth in-cycle NOT-MET recorded this
  cycle); Modal egress billing goes effective Oct 1 (~2 days out —
  first-party re-confirm post-effective-date); agent-O DevDay
  confirmation gate Tue Sep-29 10am PT / 12pm CT (only an actual
  OpenAI confirmation files C68); Hugo GHSA sweep (full URL —
  shorthand 404s) — the CVE-2026-100690 bar stays "file on first-party
  GHSA appearance, aggregator-only stays out"; the alleged Vercel
  dark-web credential sale is plausibly recycled from the confirmed
  April-2026 incident — promote only on first-party word of a NEW
  incident; NanoCo as NanoClaw's vehicle — first-party
  sandbox/compute announcement from NanoCo meets the re-grade bar;
  Boat's comparison/benchmark blocks — re-render docs.boat.dev/pricing
  and the ascii.dev homepages next cycle to see whether the
  competitive-comparison sections persist; surveyor
  timestamp-honesty rule in force (mtimes = completion evidence).
