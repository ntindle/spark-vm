# Competitor watch — 2026-09-28 (evening, cycle 34)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 20:57:01 CDT stat-certified) against the
cycle-33 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (17 first-try
fetches succeeded, 0 failures; no searches needed — every URL carried
verbatim from the baseline capture chain). Surveyor B: delta news scan
(evidence-bounded since ~20:54 CDT; snippet level, zero pages opened,
mtime-bounded to 20:56:09 CDT stat-certified) — **0 CANDIDATES,
11 clean dedupes, 7 flagged-only** (twenty-ninth straight quiet B-lane
scan, C6–C34).

Delta-only against the cycle-33 evening pass
(`docs/COMPETITOR_WATCH_2026-09-28_EVENING_C33.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-2054.md`,
`hidden_files/agent_notes/surveyor-b-20260928-2054.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded: A-lane to 20:57:01 CDT, B-lane to 20:56:09 CDT
> (stat-certified by the integrator).
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items — items 1–3, 4a–4c, and 5–9 no-change (9
> items), 0 delta, 0 unverified. Surveyor B's header (0 CANDIDATES /
> 11 clean dedupes / 7 flagged-only) agrees with its enumerations —
> no candidate reached the integrator's corpus gate this cycle, so no
> gate-resolution section is needed.
>
> **Integrator fold-gate:** no CANDIDATES this cycle — nothing to
> gate. No new C-numbers, no re-folds, no age-out movement.

## Surveyor A — first-party vendor re-verification (mtime-bounded to 20:57:01 CDT)

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
      section still carries the cycle-33 baseline's 3 entries in the
      same order: "Search domains without authentication" first, then
      "Claude Sonnet 5.5 now available on AI Gateway", then "Vercel
      Sandbox now supports memory observability". No Drives GA entry
      anywhere in the rendered window (24–28 September). **P49
      IN-CYCLE VERDICT: NOT MET as observed** (tenth consecutive
      in-cycle grading; the expectation window closes at the end of
      tonight, 2026-09-28). This watch does not declare the
      expectation dead — Vercel has not cancelled Drives GA; the
      first-party surfaces simply still show Private Beta.
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
   first-party egress pricing line — C12 stays OPEN** (34th
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
   matching the baseline's enumerated set verbatim (ninth consecutive
   render capped at exactly 10 — the ≥14-total bar stays retired in
   favor of "visible list matches baseline enumeration"). No removed
   advisory evidenced.

**Color (not a baseline delta verdict):** surveyor A re-rendered
`docs.boat.dev/pricing`, `ascii.dev`, and `box.ascii.dev` per the
cycle-33 ask. The competitive-comparison blocks persist on all three
pages, unchanged in substance from the cycle-33 capture: the
"Compared to others" provider $/hour matrix (boat $0.018/$0.036/
$0.072/$0.200 vs Novita, Freestyle, E2B, Daytona, Modal, Vercel
Sandbox, Railway and others at 5x–23x multiples), the "Active CPU"
billing explainer, and the hpc-sandbox-benchmarks leaderboard
("2026-08-24": boat 27.7 runs/s vs Daytona 18.6, Modal 15.1, E2B
11.2; a 1,000-run Node.js build loop at 36s for boat vs 54s/66s/89s
for Daytona/Modal/E2B). Color only — the baseline-enumerated pricing
facts on all three pages are verbatim intact, so NO-CHANGE stands on
the baseline's terms.

## Surveyor B — delta news scan (evidence-bounded since ~20:54 CDT, mtime-bounded to 20:56:09 CDT): 0 CANDIDATES / 11 clean dedupes / 7 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; twenty-ninth straight quiet
B-lane scan (C6–C34).

**Clean dedupes (11):**

1. **Modal "$750M round at $15.75B valuation, led by Accel" — maps to
   standing C11.** A Sept-28 piece states explicitly "Neither round
   has closed"; TechCrunch headline still reads "closing in on" and
   article text uses only "nearing"; Modal declined to comment → no
   C-number minted, FILE ON CLOSE stays armed.
2. **Baseten "$26 billion valuation infusion" — maps to standing C11
   (Baseten arm).** Bloomberg-via-TechCrunch and mirrors still frame
   it as "nearing"/"close to finalizing" → no new entry.
3. **agent-O / OpenAI DevDay — no OpenAI confirmation in-window —
   maps to C68 gate (standing).** runtimewire (updated Sept 28,
   8:02pm CT — unchanged since cycle 33) states explicitly "OpenAI
   has confirmed no product announcements"; 'o' remains a leak, not
   an announcement. DevDay keynote Tue Sep-29 10am PT / 12pm CT
   remains the confirmation gate; only an actual OpenAI confirmation
   files C68.
4. **NVIDIA Open Agent Safety Platform (Sept-28 launch, pre-window) —
   maps to already-folded C70.** Continued recirculation (Jensen
   Huang CNBC commentary, 100+ partners, OpenShell GA v0.1.0 + Sentry)
   — corroboration of the folded launch, not a new launch.
5. **Docker Cloud Sandboxes — pre-window launch (first-party Sept 24)
   — carried standing.** No new Docker product news in-window.
6. **DigitalOcean Managed Agents public preview (Sept 22/23,
   pre-window) — carried standing.** No in-window movement.
7. **Vercel Sandbox Drives — public beta Sept 23 (pre-window); no GA
   evidence in-window — carried, P49 NOT MET.** Third-party
   Drives analysis plus the vercel/sandbox CHANGELOG (v4.4.0)
   reconfirm the Sept-23 public-beta launch; nothing newer. P49
   grading is surveyor A's lane; this scan found nothing to change
   the NOT-MET call.
8. **Daytona funding — no new confirmed round; old PR reprint
   circulating — below bar.** Daytona's $24M Series A remains the
   last confirmed raise; a 2024-era PR Newswire "Agent-Agnostic
   Infrastructure / OpenHands demo" piece being re-syndicated by
   local-news mirrors is a timestamp-artifact reprint, not new news.
   Not a C-item.
9. **Modal network-egress billing effective Oct 1, 2026 — carried
   standing.** No went-live-early signals in-window (~2 days to the
   effective date).
10. **Third-party provider-comparison content — below bar, pre-window
    — maps to the C29/C30 third-party-tooling category.** Pricing and
    methodology comparison pieces (E2B vs Modal vs Daytona; Sandboxing
    AI-Generated Code) are vendor/third-party methodology, not
    provider news; none re-filed.
11. **NanoClaw / NanoCo — no first-party sandbox/compute announcement
    — maps to standing NanoClaw watch item.** NanoCo coverage is
    agent-product news, not sandbox/compute infra. Re-grade bar not
    met.

**Flagged-only (7, below bar):**

1. **Alleged Vercel access-keys/source-code dark-web sale —
   UNVERIFIED, plausibly recycled — unchanged.** A newer Sept-28
   piece flags a DailyDarkWeb post with headline-only detail; the
   assessment still self-rates as "Unverified — Further Evidence
   Required" and warns of recycled material. All substantive coverage
   describes the confirmed April-2026 Context.ai-OAuth incident.
   Watch only.
2. **NanoClaw × Slack "persistent agent teams" integration — consumer
   agent-product news, not sandbox/compute infra.** Below the
   re-grade bar.
3. **Vercel rebuilt v0 (GA) — consumer product news, not sandbox
   infra.** Below the in-lane bar.
4. **OpenAI training-sandbox DNS-escape coverage — agent-safety
   research, not in-lane provider news.** OpenAI's own incident
   report, not a sandbox-for-agents provider product.
5. **Perplexity "Escaping SPACE: Part I" red-team report (published
   Sept 23, pre-window) — sandbox safety research, not provider
   news.** Static-test research, outside the lane.
6. **Agent-infrastructure funding roundups — adjacent, pre-window, no
   sandbox/compute-for-agents product — below bar.** Temporal $550M
   Series E, Composio $25M, Firecrawl $75M, Baseten/Fireworks/Fal
   talks-level items, Granite €4M "agentic cloud". Not filed.
7. **OpenAI GPT-6.1 "Astra" launch cancellation (in-window weekend
   safety news) — below bar.** Frontier-lab safety news (OpenAI
   scrapped the Astra rollout over safety testing), not a
   sandbox/compute-for-agents provider product launch. Watch only.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** Hugo CVE-2026-100690 (aggregator-only standing item;
bar remains "file on first-party GHSA appearance only"); Plugin4Shell
(still no real CVE — never cite the suspect CVE-2026-92104); Boxd $2M
pre-seed (closed — recirculation does NOT reactivate); Baseten ×
Blaxel Carbon (private preview, GA not tripped); Mistral Vibe (no new
family member); AgentComputer (no first-party egress line; C12 stays
OPEN); NVIDIA OpenShell v0.1.0 GA = already-folded C70; TermSquad
(Sept 15 launch) carried standing; Scalepoint ClaimsCORE/HUB 45-min
sandbox disruption (Sept 28, resolved) is an insurance-vendor
incident, not compute-for-agents infra — below bar. Aged-out stay
out (C29, C45, C56, C66, C67, C62, Heapjack/Overpatch, GitLab
CVE-2026-85706, Dextr AI); C26 closed.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (twenty-ninth
  straight quiet B-lane scan, C6–C34).
- **Corpus movement:** no new mints, no re-folds, no new age-outs
  this cycle (no dedicated aging queries; aged-out items showed no
  in-window movement). **C11 (Modal/Baseten talks-wave) — still
  unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (34th consecutive read).** Aged-out stay out (C29, C45,
  C56, C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **P49:** the Vercel Drives GA-by-2026-09-28 expectation graded
  NOT MET as observed for the tenth consecutive in-cycle pass — the
  expectation window closes at the end of tonight (2026-09-28). Not
  declared dead: Vercel has not cancelled Drives GA; the first-party
  surfaces simply still show Private Beta.
- **Watch-outs for the next slot:** C68 confirmation gate — OpenAI
  DevDay keynote Tue Sep-29 10am PT / 12pm CT (only an actual OpenAI
  confirmation files C68); C11 FILE ON CLOSE (both rounds still
  unclosed — a close announcement files immediately); Modal egress
  billing effective Oct 1 (~2 days out — re-confirm
  post-effective-date); P49's expectation window closes at the end of
  tonight (2026-09-28) — while any in-window pass remains tonight,
  continue in-cycle grading; once the window closes (00:00 CT
  Sept 29), stop in-cycle grading and watch Drives for GA as a
  standing tracked item instead (a cycle-35 pass later tonight
  ~21:25–21:30 CDT would still be in-window); the alleged Vercel dark-web credential sale
  is plausibly recycled from the confirmed April-2026 incident —
  promote only on first-party word of a NEW incident or two
  independent reputable sources; NanoCo as NanoClaw's vehicle —
  first-party sandbox/compute announcement from NanoCo meets the
  re-grade bar; surveyor timestamp-honesty rule in force (mtimes =
  completion evidence).
