# Competitor watch — 2026-09-28 (evening, cycle 35)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 21:27:21 CDT stat-certified) against the
cycle-34 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (18 first-try
fetches succeeded — 17 chain URLs plus the DigitalOcean limits page
located via the sibling-URL pattern of the chain's own pricing subpage —
0 failures; every URL carried verbatim from the baseline capture chain).
Surveyor B: delta news scan (evidence-bounded since ~21:15 CDT; snippet
level, zero pages opened, mtime-bounded to 21:26:53 CDT stat-certified)
— **0 CANDIDATES, 11 clean dedupes, 5 flagged-only** (thirtieth straight
quiet B-lane scan, C6–C35).

Delta-only against the cycle-34 evening pass
(`docs/COMPETITOR_WATCH_2026-09-28_EVENING_C34.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-2124.md`,
`hidden_files/agent_notes/surveyor-b-20260928-2124.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded: A-lane to 21:27:21 CDT, B-lane to 21:26:53 CDT
> (stat-certified by the integrator).
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items — items 1–3, 4a–4c, and 5–9 no-change (9
> items), 0 delta, 0 unverified. Surveyor B's header (0 CANDIDATES /
> 11 clean dedupes / 5 flagged-only) agrees with its enumerations —
> no candidate reached the integrator's corpus gate this cycle, so no
> gate-resolution section is needed.
>
> **Integrator fold-gate:** no CANDIDATES this cycle — nothing to
> gate. No new C-numbers, no re-folds, no age-out movement.

## Surveyor A — first-party vendor re-verification (mtime-bounded to 21:27:21 CDT)

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
      section still carries the cycle-34 baseline's 3 entries in the
      same order: "Search domains without authentication" first, then
      "Claude Sonnet 5.5 now available on AI Gateway", then "Vercel
      Sandbox now supports memory observability". No Drives GA entry
      anywhere in the rendered window (24–28 September). **P49
      IN-CYCLE VERDICT: NOT MET as observed** (eleventh consecutive
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
   first-party egress pricing line — C12 stays OPEN** (35th
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
   matching the baseline's enumerated set verbatim (tenth consecutive
   render capped at exactly 10 — the ≥14-total bar stays retired in
   favor of "visible list matches baseline enumeration"). No removed
   advisory evidenced.

**Restore (not a baseline delta verdict — closes the C34 restore-or-retire watch-out):**
the "100 sessions/team" DigitalOcean Managed Agents detail is **RESTORED**
with a first-party carrier. Surveyor A located the sibling limits page
(`https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/limits/`,
stamp "Last verified 21 Sep 2026"), verbatim: **"You can run up to 100
sessions at once per team depending on your tier."** It is a per-team
concurrency cap on the limits page, not a pricing figure — which is why
the C33→C34 pricing-only chain lost its carrier. Corpus note: if the
detail is ever quoted in the corpus, anchor it to the limits URL and
frame it as a concurrency cap.

## Surveyor B — delta news scan (evidence-bounded since ~21:15 CDT, mtime-bounded to 21:26:53 CDT): 0 CANDIDATES / 11 clean dedupes / 5 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; thirtieth straight quiet
B-lane scan (C6–C35).

**Clean dedupes (11):**

1. **Modal "$750M round at $15.75B valuation, led by Accel" — maps to
   standing C11.** TechCrunch (Sept 28) headline still reads "closing
   in on" and body uses only "nearing"; Modal declined to comment;
   syndications recycle the same framing → no close signal; FILE ON
   CLOSE stays armed.
2. **Baseten "$26 billion valuation infusion" — maps to standing C11
   (Baseten arm).** All coverage still frames it as talks-level
   ("nearing"/"close to finalizing"); last confirmed raise remains the
   June 2026 $1.5B Series F at $13B → no new entry.
3. **agent-O / OpenAI DevDay — no OpenAI confirmation in-window —
   maps to C68 gate (standing).** runtimewire (updated Sept 28, 8:02pm
   CT) still states explicitly "OpenAI has confirmed no product
   announcements"; all other agent-O coverage is leak/speculation
   only. DevDay keynote Tue Sep-29 10am PT / 12pm CT remains the
   confirmation gate; only an actual OpenAI confirmation files C68.
4. **Daytona 2024-era PR Newswire reprint ("Agent-Agnostic
   Infrastructure / OpenHands demo") — recycled, maps to C34 B-8.**
   Still being re-syndicated by local-news mirrors (crawled within the
   last hour) — timestamp-artifact reprint, not new news.
5. **tech-insider.org "E2B vs Modal vs Daytona: AI Sandbox Pricing
   2026" — below bar, pre-window — maps to the C29/C30
   third-party-tooling category.** Vendor/third-party methodology
   comparison, not provider news; none re-filed.
6. **DigitalOcean Managed Agents — pre-window launch (Sept 21/22) —
   carried standing.** Only recirculation of the Business Wire release
   plus a subagentic.ai analysis — no in-window product movement.
7. **Vercel Sandbox Drives — public beta Sept 23 (pre-window); no GA
   evidence in-window — carried, P49 NOT MET.** nandann.com analysis
   (5 days) reconfirms the Sept-23 public-beta launch; nothing newer.
   P49 grading is surveyor A's lane; nothing found to change the
   NOT-MET call.
8. **AgentComputer — no first-party egress pricing line found —
   C12 stays OPEN.** This cycle's search surfaced only the repo's own
   watch docs; the standing no-egress-line observation is unchallenged.
9. **Modal network-egress billing effective Oct 1, 2026 — carried
   standing.** No went-live-early signals in-window (~2 days to the
   effective date).
10. **NanoClaw / NanoCo — no first-party sandbox/compute announcement
    — maps to standing NanoClaw watch item.** No new coverage meeting
    the re-grade bar.
11. **Baseten June 2026 $1.5B Series F at $13B — pre-window closed
    round, context only.** Recent crawls of June reporting are
    backfill, not new news; relevant only as the closed baseline behind
    the C11 Baseten talks arm.

**Flagged-only (5, below bar):**

1. **Alleged Vercel access-keys/source-code dark-web sale —
   UNVERIFIED, plausibly recycled — unchanged.** Newer Sept-28 pieces
   trace the claim to a Sept-27 SOCRadar Dark Web News report + a
   @DailyDarkWeb headline-only post; the aggregator itself rates the
   listing unverified and warns it could be recycled data or buyer-bait.
   Promotion bar NOT met: no first-party word of a NEW incident, and
   the sourcing chain (threat-intel vendor → single X account → one
   aggregator) is not two independent reputable sources with
   independent verification. All substantive coverage still describes
   the confirmed April-2026 Context.ai-OAuth incident. Watch only.
2. **LangChain "Sandboxes for Deep Agents" blog — third-party
   integration news, not provider news.** Announces Deep Agents
   integrations with partner sandboxes (Runloop, Daytona, Modal);
   integration-layer coverage of existing providers, not an in-lane
   provider launch/GA/pricing change. Below the candidate bar; likely
   pre-window anyway.
3. **OpenAI GPT-6.1 "Astra" launch cancellation recirculation (BBC
   Business, Al Jazeera English overnight) — below bar.** Frontier-lab
   safety news (OpenAI scrapped the Astra rollout over safety
   testing), not a sandbox/compute-for-agents provider product
   launch. Watch only.
4. **Modal July customer-data compromise mentioned as funding-story
   context — pre-window, context-only, below bar.** Not a new
   incident and not in-lane provider news.
5. **Agent-infrastructure funding roundups — adjacent, pre-window, no
   sandbox/compute-for-agents product — below bar.** Temporal $550M
   Series E, Composio $25M, Firecrawl $75M, Baseten/Fireworks/Fal
   talks-level items. Not filed.

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
  verdict dated 2026-09-25 stands — streak extends (thirtieth
  straight quiet B-lane scan, C6–C35).
- **Corpus movement:** no new mints, no re-folds, no new age-outs
  this cycle (no dedicated aging queries; aged-out items showed no
  in-window movement). **C11 (Modal/Baseten talks-wave) — still
  unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (35th consecutive read).** The C34 restore-or-retire
  watch-out is closed: the DigitalOcean "100 sessions/team" detail is
  restored as a per-team concurrency cap on the vendor limits page
  (see the A-lane restore note). Aged-out stay out (C29, C45, C56,
  C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **P49:** the Vercel Drives GA-by-2026-09-28 expectation graded
  NOT MET as observed for the eleventh consecutive in-cycle pass —
  the expectation window closes at the end of tonight (2026-09-28).
  Not declared dead: Vercel has not cancelled Drives GA; the
  first-party surfaces simply still show Private Beta.
- **Watch-outs for the next slot:** two more in-window strategy
  slots remain tonight (22:24, 23:24 CDT) — the FINAL in-cycle P49
  grade rides with the last in-window pass; once the window closes
  (00:00 CT Sept 29), stop in-cycle grading and watch Drives for GA
  as a standing tracked item instead. C68 confirmation gate —
  OpenAI DevDay keynote Tue Sep-29 10am PT / 12pm CT (only an actual
  OpenAI confirmation files C68); C11 FILE ON CLOSE (both rounds
  still unclosed — a close announcement files immediately); Modal
  egress billing effective Oct 1 (~2 days out — re-confirm
  post-effective-date); the alleged Vercel dark-web credential sale
  stays watch-only (promotion bar unmet); NanoCo as NanoClaw's
  vehicle — first-party sandbox/compute announcement from NanoCo
  meets the re-grade bar; surveyor timestamp-honesty rule in force
  (mtimes = completion evidence).
