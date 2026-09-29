# Competitor watch — 2026-09-28 (evening, cycle 31)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 19:26:35 CDT stat-certified) against the
cycle-30 baseline —
**8 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 0 UNVERIFIED** (17 first-try
fetches succeeded, 0 failures; no searches needed — every URL carried
verbatim from the baseline capture chain). Surveyor B: delta news scan
(evidence-bounded since ~18:54 CDT; snippet level, zero pages opened,
mtime-bounded to 19:26:28 CDT stat-certified) — **0 CANDIDATES,
9 clean dedupes, 4 flagged-only** (twenty-sixth straight quiet B-lane
scan, C6–C31).

Delta-only against the cycle-30 evening pass
(`docs/COMPETITOR_WATCH_2026-09-28_EVENING_C30.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-1924.md`,
`hidden_files/agent_notes/surveyor-b-20260928-1924.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded: A-lane to 19:26:35 CDT, B-lane to 19:26:28 CDT
> (stat-certified by the integrator).
>
> **Count-honesty check:** surveyor A's header (8 / 1 / 0) agrees with
> its nine enumerated items — items 1–3 and 5–9 no-change (8 items),
> and item 4 carries the delta (driven by 4a, with 4b–4c verified
> unchanged). Surveyor B's header (0 CANDIDATES / 9 clean dedupes /
> 4 flagged-only) agrees with its enumerations — no candidate reached
> the integrator's corpus gate this cycle, so no gate-resolution
> section is needed.
>
> **URL-chain count note:** surveyor A flags that the cycle-30
> capture's fetch-stats line said "16 first-try successes" while its
> enumerated body carried 17 verbatim URLs (item 8 is explicitly 4/4).
> All 17 were carried verbatim this cycle and all 17 loaded first
> try — no evidence of a dropped check, capture-side miscount only.
>
> **Integrator fold-gate:** no CANDIDATES this cycle — nothing to
> gate. No new C-numbers, no re-folds, no age-out movement.

## Surveyor A — first-party vendor re-verification (mtime-bounded to 19:26:35 CDT)

**8 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Still SEP 26 2026 /
   V0.218.0 (KVM sandbox parameter + CLI WorkOS application); second
   still SEP 25 / V0.217.0 (NVIDIA B300 GPU). No V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out 2026-09-22; the 2026-09-21 v3-kits entry verbatim unchanged.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still v0.7.3; no
   v0.7.4+ tag.
4. **Vercel (changelog index — DELTA; Sandbox docs + Drives page — NO-CHANGE).**
   a. **Changelog index — VERIFIED DELTA (Drives-unrelated).** The "28
      September" section now carries **3 entries**: a NEW first entry
      "Search domains without authentication" (search for domains using
      the Vercel CLI and Domains Registrar API without signing in),
      followed by the baseline's two — "Claude Sonnet 5.5 now available
      on AI Gateway" and "Vercel Sandbox now supports memory
      observability" (verbatim unchanged). No Drives GA entry anywhere
      in the rendered window. The delta is domain-search tooling, not
      sandbox/Drives — P49 substance unchanged. **P49 IN-CYCLE VERDICT:
      NOT MET as observed** (seventh consecutive in-cycle grading). The
      expectation's window closes tonight; the final grade rides with
      the last in-window pass — this watch does not declare the
      expectation dead.
   b. **Sandbox docs Features list — VERIFIED NO-CHANGE.** Still
      `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
      Features list.
   c. **Drives page — VERIFIED NO-CHANGE (read + reconciled).** Still
      "in Private Beta" with an active waitlist — no GA language;
      consistent with the docs Features-list "Drives (beta)" text.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB; overage
   $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals (~1.7 days to the effective date).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (31st
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
   matching the baseline's enumerated set verbatim (sixth consecutive
   render capped at exactly 10 — the ≥14-total bar stays retired in
   favor of "visible list matches baseline enumeration"). No removed
   advisory evidenced.

## Surveyor B — delta news scan (evidence-bounded since ~18:54 CDT, mtime-bounded to 19:26:28 CDT): 0 CANDIDATES / 9 clean dedupes / 4 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; twenty-sixth straight quiet
B-lane scan (C6–C31).

**Clean dedupes (9):**

1. **Modal "$750M round at $15.75B valuation, led by Accel" — maps to
   standing C11.** A Sept-28 piece states explicitly "the deal is not
   closed"; the TechCrunch piece and its mirrors still use only
   "nearing"/"closing in" language; Modal declined to comment; the
   round is NOT closed → no C-number minted, FILE ON CLOSE stays armed.
2. **Baseten "nearing an infusion of capital at a $26 billion
   valuation" per Bloomberg — maps to standing C11 (Baseten arm).**
   Still "nearing"/"in talks"/"discussing", with an analytics piece
   noting explicitly "Neither round has closed" → no new entry.
3. **agent-O / OpenAI DevDay — no OpenAI confirmation in-window —
   maps to C68 gate (standing).** A Sept-28 report states explicitly
   "OpenAI has confirmed no product announcements"; a second concurs
   ("'o' remains a leak, not an announcement"); the Sept-28 OpenAI
   teaser X post names no product. DevDay keynote Tue Sep-29 10am PT /
   12pm CT remains the confirmation gate; only an actual OpenAI
   confirmation files C68.
4. **Anthropic × NVIDIA OpenShell collab on Claude Managed Agents —
   maps to already-folded C70.** A Sept-28 report covers NVIDIA's Open
   Agent Safety Platform launch with Anthropic among partners, working
   on a Claude Managed Agents × OpenShell integration — the same Sept-28
   story as the C30 dedupe, confirmed as the already-folded C70;
   corroboration, not a new corpus entry.
5. **Vercel Sandbox Drives — public beta Sept 23 (pre-window); no GA
   evidence in-window — carried, P49 NOT MET.** The Sept-23
   public-beta launch is reconfirmed (Drives analysis + the
   vercel/sandbox CHANGELOG v4.4.0 entry); nothing newer. P49 grading
   is surveyor A's lane; this scan found nothing to change the NOT-MET
   call.
6. **DigitalOcean Managed Agents public preview (Sept 22, pre-window)
   — carried standing.** DO docs, release notes, and syndication
   recirculate the Sept-22 launch; no in-window movement.
7. **TermSquad (Sept 15 launch, pre-window) — carried standing.**
   Syndication mirrors only recirculate the launch release; no
   in-window movement.
8. **Modal network-egress billing effective Oct 1, 2026 — carried
   standing.** Third-party docs mirror confirms the effective date;
   no went-live-early reported.
9. **Third-party provider-comparison content — below bar, pre-window.**
   A 15-provider sandbox comparison (Sept 16) and a Cursor
   sandbox-providers post (Sept 19) are vendor/third-party
   methodology pieces, not provider news; none re-filed.

**Flagged-only (4, below bar):**

1. **Alleged Vercel access-keys/source-code dark-web sale —
   UNVERIFIED, plausibly recycled.** The Sept-28 threat-intel post
   still self-assesses as unverified and warns the material may be
   recycled. **New nuance this cycle:** the search surfaced the
   CONFIRMED April 2026 Vercel/ShinyHunters incident (April 19 forum
   post, Vercel-confirmed investigation of a limited subset) — the
   Sept-28 listing plausibly recirculates that known incident rather
   than representing a new breach. Watch only; promote only on
   first-party word of a NEW incident or two independent reputable
   sources.
2. **Daytona "Agent-Agnostic Infrastructure" OpenHands demo PR —
   pre-window syndication.** PR-newswire mirrors with no in-window
   date evidence; older-campaign product positioning, not new
   provider news.
3. **Vercel rebuilt v0 (GA) — consumer product news, not sandbox
   infra.** v0 imports GitHub repos and ships production code — an
   app-generation product, not compute-for-agents infrastructure;
   adjacent at best, below the in-lane bar.
4. **OpenAI DevDay teaser post (Sept 28) — supports, does not trip,
   C68.** The post names no product; leak-only coverage stays deduped
   under C68.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** Hugo CVE-2026-100690 (aggregator-only standing item;
bar remains "file on first-party GHSA appearance only"); Plugin4Shell
(still no real CVE — never cite the suspect CVE-2026-92104); Boxd $2M
pre-seed (closed — recirculation does NOT reactivate); Baseten × Blaxel
Carbon (private preview, GA not tripped); NanoClaw (re-grade only on
first-party sandbox/compute announcement); Mistral Vibe (no new family
member); Daytona/E2B funding (no new rounds; Daytona's $24M Series A
remains the last confirmed raise). NVIDIA OpenShell v0.1.0 GA =
already-folded C70.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (twenty-sixth
  straight quiet B-lane scan, C6–C31).
- **Corpus movement:** no new mints, no re-folds, no new age-outs
  this cycle (no dedicated aging queries; aged-out items showed no
  in-window movement). **C11 (Modal/Baseten talks-wave) — still
  unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (31st consecutive read).** Aged-out stay out (C29, C45,
  C56, C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **Watch-outs for the next slot:** P49's final grade rides with the
  last in-window pass tonight (seventh in-cycle NOT-MET recorded this
  cycle); Modal egress billing goes effective Oct 1 (~1.7 days out —
  first-party re-confirm post-effective-date); agent-O DevDay
  confirmation gate Tue Sep-29 10am PT / 12pm CT (only an actual
  OpenAI confirmation files C68); Hugo GHSA sweep (full URL —
  shorthand 404s) — the CVE-2026-100690 bar stays "file on first-party
  GHSA appearance, aggregator-only stays out"; the alleged Vercel
  dark-web credential sale is plausibly recycled from the confirmed
  April-2026 ShinyHunters incident — promote only on first-party word
  of a NEW incident; NanoClaw/NanoCo re-grade only on first-party
  sandbox/compute announcement; Mistral Vibe re-fold bar; Plugin4Shell
  real-CVE watch (never cite the suspect CVE-2026-92104); Boxd
  recirculation (closed — do not re-activate on recirculation);
  Carbon private-preview; surveyor timestamp-honesty rule in force
  (mtimes = completion evidence).
