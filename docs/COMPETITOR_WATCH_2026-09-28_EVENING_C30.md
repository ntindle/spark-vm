# Competitor watch — 2026-09-28 (evening, cycle 30)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 18:56:07 CDT stat-certified) against the
cycle-29 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (16 first-try
fetches succeeded, 0 failures; no searches needed — every URL carried
verbatim from the baseline capture chain). Surveyor B: delta news scan
(evidence-bounded since ~18:24 CDT; snippet level, zero pages opened,
mtime-bounded to 18:57:07 CDT stat-certified) — **0 CANDIDATES,
8 clean dedupes, 5 flagged-only** (twenty-fifth straight quiet B-lane
scan, C6–C30).

Delta-only against the cycle-29 evening pass
(`docs/COMPETITOR_WATCH_2026-09-28_EVENING_C29.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-1854.md`,
`hidden_files/agent_notes/surveyor-b-20260928-1854.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded: A-lane to 18:56:07 CDT, B-lane to 18:57:07 CDT
> (stat-certified by the integrator).
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items. Surveyor B's header (0 CANDIDATES /
> 8 clean dedupes / 5 flagged-only) agrees with its enumerations —
> no candidate reached the integrator's corpus gate this cycle, so no
> gate-resolution section is needed.
>
> **Coverage disclosure:** surveyor B's capture carries several items
> (Modal egress billing effective date, Hugo CVE-2026-100690
> aggregator-only standing item, Plugin4Shell, Boxd, Baseten×Blaxel
> Carbon, NanoClaw, Mistral Vibe, Daytona/E2B funding) as
> not-re-queried with coverage disclosure — carried below as standing,
> NOT asserted as re-verified, per precedent. AgentComputer's C12
> status IS asserted re-verified this cycle (surveyor A lane, 30th
> consecutive first-party read — see item 7).
>
> **Integrator fold-gate:** no CANDIDATES this cycle — nothing to
> gate. The one item that could read as new (the Anthropic × NVIDIA
> OpenShell "Claude Managed Agents" collaboration story in surveyor
> B's dedupe #4) resolves as the **already-folded C70** —
> surveyor B's own capture files it as a clean dedupe, not a
> candidate, so there is no double-fold risk.

## Surveyor A — first-party vendor re-verification (mtime-bounded to 18:56:07 CDT)

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
   NO-CHANGE.** The "28 September" section still has exactly the C29
   two entries (Claude Sonnet 5.5 on AI Gateway; Sandbox memory
   observability) — no Drives GA entry. Sandbox docs still
   `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
   Features list. The dedicated Drives page still says "in Private
   Beta" with an active waitlist — no GA language. **P49 IN-CYCLE
   VERDICT: NOT MET as observed** (sixth consecutive in-cycle
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
   went-live-early signals (~1.9 days to the effective date).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (30th
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
   matching the baseline's enumerated set verbatim (fifth consecutive
   render capped at exactly 10 — the ≥14-total bar stays retired in
   favor of "visible list matches baseline enumeration"). No removed
   advisory evidenced.

## Surveyor B — delta news scan (evidence-bounded since ~18:24 CDT, mtime-bounded to 18:57:07 CDT): 0 CANDIDATES / 8 clean dedupes / 5 flagged-only

**NEW with evidence (0).** No new in-lane items this cycle. The
in-lane no-launch verdict is unchanged; twenty-fifth straight quiet
B-lane scan (C6–C30).

**Clean dedupes (8):**

1. **Modal "$750M round at $15.75B valuation, led by Accel" — maps to
   standing C11.** The Sept-28 TechCrunch piece and its recirculation
   mirrors still use only "nearing"/"closing in" language; Modal
   declined to comment; the round is NOT closed → no C-number minted,
   FILE ON CLOSE stays armed.
2. **Baseten "nearing an infusion of capital at a $26 billion
   valuation" per Bloomberg — maps to standing C11 (Baseten arm).**
   Still "nearing"/"in talks", not closed → no new entry.
3. **agent-O / OpenAI DevDay — no OpenAI confirmation in-window —
   maps to C68 gate (standing).** A Sept-28 report states explicitly
   "OpenAI has confirmed no product announcements"; DevDay keynote
   Tue Sep-29 10am PT / 12pm CT remains the confirmation gate; only an
   actual OpenAI confirmation files C68.
4. **Anthropic × NVIDIA OpenShell collab on Claude Managed Agents —
   maps to already-folded C70.** A Sept-28 report pairs Anthropic's
   Claude Managed Agents with NVIDIA's OpenShell runtime; NVIDIA's
   press release names Anthropic among the 100+ partners. This is the
   same Sept-28 Open Agent Safety Platform story carried as
   flagged-only in C29 (Anthropic already named among partners) —
   corroboration, not a new corpus entry.
5. **Vercel Sandbox Drives — public beta Sept 23 (pre-window); no GA
   evidence in-window — carried, P49 NOT MET.** Nothing newer than
   the Sept-23 public-beta launch; P49 grading is surveyor A's lane.
6. **DigitalOcean Managed Agents public preview (Sept 22, pre-window)
   — carried standing.** Recirculation of the Sept-22 launch; DO's own
   docs still match the C29 VERIFIED NO-CHANGE read. No in-window
   movement.
7. **Cloudflare Dynamic Workers open beta — pre-window, carried.** A
   VentureBeat piece recirculates the March 2026 open beta — not new;
   cloudflare/sandbox-sdk patch entries are pre-window (5 days) and
   folded here as no in-window movement.
8. **Third-party sandbox-integration docs — consumer tooling, below
   bar.** A set of pre-window, third-party-only docs (orbitalab,
   multigent, memroos, betalyra/effect-uai, madarco/agentbox,
   scoutqa-dot-ai) — none is first-party provider news; none re-filed.

**Flagged-only (5, below bar):**

1. **Alleged Vercel access-keys/source-code dark-web sale —
   UNVERIFIED.** A Sept-28 threat-intel post carries an alleged
   dark-web listing; the source's own assessment concludes
   "Unverified — Further Evidence Required" and warns the material
   may be recycled from an earlier third-party incident. Below the
   evidence bar (no first-party word, single unverified lead) —
   watch only.
2. **RunPod enterprise platform expansion — pre-window
   recirculation.** A ~4-day-old release (orgs/governance, SSO/SAML,
   ISO 27001): GPU-cloud enterprise marketing, not sandbox news.
3. **QumulusAI's 616-GPU RunPod deployment — pre-window (Sept 4
   release).** Same lane as item 2; no new movement.
4. **Anthropic enzyme-discovery dispute — safety-adjacent-not-provider.**
   A Sept-28 report: a University of Copenhagen biologist disputes
   Anthropic's ART enzyme-discovery claim. Anthropic research news,
   not provider infrastructure; below bar.
5. **OpenStatus provider-latency benchmark blog (Cloudflare Workers,
   Fly.io, Koyeb, Railway, Render) — pre-window (4 days),
   third-party methodology.** Below bar; no provider announcements
   inside.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** Modal egress billing effective Oct 1, 2026 (no
went-live-early reported); Hugo CVE-2026-100690 (aggregator-only
standing item; bar remains "file on first-party GHSA appearance
only"); Plugin4Shell (still no real CVE — never cite the suspect
CVE-2026-92104); Boxd $2M pre-seed (C29 closed — recirculation does
NOT reactivate); Baseten × Blaxel Carbon (private preview, GA not
tripped); NanoClaw (re-grade only on first-party sandbox/compute
announcement); Mistral Vibe (no new family member); Daytona/E2B
funding (no new rounds; Daytona's $24M Series A remains the last
confirmed raise). NVIDIA OpenShell v0.1.0 GA = already-folded C70.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (twenty-fifth
  straight quiet B-lane scan, C6–C30). The one corpus-adjacent item
  this cycle (the Anthropic × OpenShell Claude Managed Agents story)
  is the already-folded C70 — no corpus movement.
- **Corpus movement (P63):** no new mints, no re-folds, no new
  age-outs this cycle (no dedicated aging queries; aged-out items
  showed no in-window movement). **C11 (Modal/Baseten talks-wave) —
  still unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (30th consecutive read).** Aged-out stay out (C29, C45,
  C56, C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **Watch-outs for the next slot:** P49's final grade rides with the
  last in-window pass tonight (sixth in-cycle NOT-MET recorded this
  cycle); Modal egress billing goes effective Oct 1 (~1.9 days out —
  first-party re-confirm post-effective-date); agent-O DevDay
  confirmation gate Tue Sep-29 10am PT / 12pm CT (only an actual
  OpenAI confirmation files C68); Hugo GHSA sweep (full URL —
  shorthand 404s) — the CVE-2026-100690 bar stays "file on first-party
  GHSA appearance, aggregator-only stays out"; the alleged Vercel
  dark-web credential sale promotes to a corpus item only on
  first-party confirmation or two independent reputable sources;
  NanoClaw/NanoCo re-grade only on first-party sandbox/compute
  announcement; Mistral Vibe re-fold bar; Plugin4Shell real-CVE watch
  (never cite the suspect CVE-2026-92104); Boxd recirculation (C29 —
  do not re-activate on recirculation); Carbon private-preview
  (Baseten×OpenShell cross-lane note); surveyor timestamp-honesty rule
  in force (mtimes = completion evidence).
