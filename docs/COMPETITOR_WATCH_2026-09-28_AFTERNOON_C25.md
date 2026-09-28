# Competitor watch — 2026-09-28 (afternoon, cycle 25)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads completed by the 16:27:01 CDT stat-certified
mtime) against the cycle-24 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (16 first-try
fetch successes, 0 failures; no searches needed — every URL carried
verbatim from the baseline capture chain). Surveyor B: delta news scan
(evidence-bounded; snippet level, zero pages opened, completed by the
16:26:48 CDT stat-certified mtime) — **0 NEW with evidence, 15 clean
dedupes, 2 flagged-only, 0 new in-lane launches** (twentieth straight
quiet B-lane scan, C6–C25).

Delta-only against the cycle-24 afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-28_AFTERNOON_C24.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-1624.md`,
`hidden_files/agent_notes/surveyor-b-20260928-1624.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** both surveyors wrote captures with NO
> per-read times in the body this cycle — the standing rule held
> cleanly, with no postdating claims to reject. All verdicts below are
> mtime-bounded: A-lane to 16:27:01 CDT, B-lane to 16:26:48 CDT.
>
> **Count-honesty check:** surveyor B's Plugin4Shell line enumerates
> seven "no CVE assigned" sources (shattered.io, neuralcoretech.com,
> deafnews.it, aiweekly.co, xkef/swe-digest, securityonline.info,
> pranava0x0) — the enumeration rules; seven is carried below. The
> header counts (0 NEW / 15 dedupes / 2 flagged-only) agree with the
> enumerations, and surveyor A's header (9 / 0 / 0) agrees with its
> nine enumerated items.
>
> **Integrator fold-gate:** no fold candidates this pass — no mint
> recommended, so no corpus grep was needed and no corroboration pass
> ran. Surveyor B's extra NVIDIA Open Agent Safety Platform outlet
> mentions (tech-insider.org, explainx.ai, techstartups.com) are
> corroboration color on the already-folded C70, not a new fold. The
> Baseten × Blaxel acquisition stays deduped at the C11 gate — no mint
> recommended, fifth cycle running.

## Surveyor A — fast-mover + pricing re-verification (first-party, completed by 16:27:01 CDT mtime)

**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Still SEP 26 2026 /
   V0.218.0 (KVM sandbox parameter + CLI WorkOS application); second
   still SEP 25 / V0.217.0 (NVIDIA B300 GPU). No V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out 2026-09-22; the 2026-09-21 v3-kits entry verbatim unchanged.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still v0.7.3; no
   v0.7.4+ tag.
4. **Vercel changelog index + Sandbox docs — VERIFIED NO-CHANGE.**
   The "28 September" section still has exactly the C24 two entries
   (Claude Sonnet 5.5 on AI Gateway; Sandbox memory observability
   re-list) — no Drives GA entry. Sandbox docs still
   `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
   Features list. **P49 IN-CYCLE VERDICT: NOT MET as observed.** All three
   first-party surfaces agree: the changelog index has no GA entry, the
   docs Features list still says "Drives (beta)", and the "Drives for
   Vercel Sandbox in Private Beta" page — read for the first time this
   cycle via the docs page's own outlink (the cycle-24 flag to
   reconcile it) — says private beta with an active waitlist and no GA
   language. It reconciles cleanly against the Features-list text:
   both describe beta/preview-state persistent storage; nothing in
   either surface contradicts or upgrades the other. The expectation
   closes unmet in-cycle, as observed.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB; overage
   $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals (~2.3 days to the effective date).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (25th
   consecutive first-party read, no wording drift).
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4, full set
   reinstated).** The cycle-24 narrowing to 2/2 is reversed: the
   canonical check set is now codified as the **2 legacy domains +
   2 YC paths**. `ascii.dev` and `box.ascii.dev` both serve the Boat
   homepage natively (no redirect); `ycombinator.com/companies/ascii`
   and `/companies/boat` both render the Boat listing natively.
   Migration-complete state holds on all four; the narrowing does not
   recur.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE.** The four
   Sep-28 Moderate advisories still top the list; total ≥14; no
   100690-specific advisory. Standing bar holds.

## Surveyor B — delta news scan (evidence-bounded, completed by 16:26:48 CDT mtime): 0 NEW / 15 clean dedupes / 2 flagged-only

**NEW with evidence (0 — none).** The in-lane search surfaced only
already-folded/corpus items with extra outlet corroboration (NVIDIA
Open Agent Safety Platform, C70) and out-of-lane items (consumer agent
apps, agent-incident stories, devops products) — none in-lane.

**Clean dedupes (15, header count agrees):**
1. Modal $15B funding (C11) — recaps only; analyticsinsight:
   "Neither round has closed." Zero close signals, zero denials. FILE
   ON CLOSE stays armed.
2. Baseten $26B funding (C11) — still talks; no close, no denial.
3. Baseten "Carbon" (C11) — first-party baseten.co blog (updated
   Sep-27) still says "introducing a private preview of Carbon"; no
   GA. Below the shipped-product bar.
4. Baseten × Blaxel acquisition (C11 gate) — recaps only; no new
   shipped sandbox product on Baseten's own platform. Stays deduped
   at the gate.
5. agent-O rumor (C68 reservation) — twenty-fifth daily cycle,
   leak/speculation only; zero OpenAI confirmation (allblogthings:
   "'o' remains a leak, not an announcement"). DevDay Sep-29
   1pm ET gate stands.
6. Mistral Vibe family — no new member; no first-party advisory beyond
   MAI-2026-003. Below the re-fold bar.
7. Plugin4Shell — "CVE-2026-92104" stays suspect: seven independent
   sources explicitly state NO CVE assigned (shattered.io,
   neuralcoretech.com, deafnews.it, aiweekly.co, xkef/swe-digest,
   securityonline.info, pranava0x0); the lone sh3llc0d3.com fringe
   claim is unchanged. Do NOT cite it as assigned.
8. Hugo CVE-2026-100690 / GHSA sweep — no new Hugo advisory surfaced
   (newest surfaced item is the Sep-11 GHSA-vrv5-r5rf-6v4j). Stays out.
9. NanoClaw/NanoCo — no first-party sandbox/compute announcement
   (VentureBeat and TechTarget pieces are recaps). Below the re-grade
   bar.
10. BAND × Docker Sandboxes — Sep-24 integration recaps; ecosystem
    activity only, already folded as C45 garnish. No hosted/compute
    product shipped.
11. Anthropic Claude Marketplace — recorded in C24 as adjacent-lane;
    no lane change, no fold.
12. Instinct $1B Series C at $10B — corroboration now spans seven
    outlets; still a consumer agent app, not sandbox/compute infra.
    No fold.
13. Vercel Drives GA (P49) — all snippets say public beta (one June
    runtimewire piece claims "Sandbox persistence GA" but self-flags
    pricing/limits/docs unverified); no third-party GA chatter. NOT
    met as observed; grade rides with the in-window A-lane; the final
    confirmation rides with the last in-window pass.
14. Daytona/E2B funding — stale rounds only (Daytona $24M Series A
    Feb-2026 recap; pricing-comparison recaps). No new rounds.
15. Modal egress billing (Oct-1 start) — no "went live early" chatter.

**Flagged-only (NOT folded — numbered verdicts):**
1. **Island $400M Series F at $6.4B** — VERDICT: below the fold bar.
   Enterprise browser company repositioning as an "agentic control
   plane" (Evolution Equity Partners lead). Agent-security/policy
   layer, not sandbox/compute infra. No fold.
2. **DataAgent $10M pre-seed** — VERDICT: below the fold bar. Emerged
   from stealth: AI-native autonomous SRE / self-healing infra for
   Kubernetes. DevOps/observability adjacent, not agent-VM/sandbox.
   No fold.

**Not re-queried this cycle (carried as standing, NOT asserted as
re-verified):** OpenAI Sep-20 DNS-escape recaps, OpenAI–Hugging Face
July intrusion commentary, AI-inference funding wave. The next
surveyor re-checks.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (twentieth
  straight quiet B-lane scan, C6–C25).
- **Corpus movement (P63): none.** No new C-numbers minted, no
  age-outs. No dedicated aging queries run this cycle; age-out
  evaluation rides on the lanes already read. C70 (NVIDIA Open Agent
  Safety Platform) stands as the latest mint. C11 (Modal/Baseten
  talks) stays OPEN — talks unclosed (FILE ON CLOSE armed), Carbon
  still private preview, Baseten × Blaxel integration still no
  shipped product. C12 (AgentComputer) stays OPEN — 25th consecutive
  no-egress-line read. Aged-out stay out: C29 (Boxd), C45, C56, C66,
  C67 (Huawei CodeArts Malaysia), C62 (OpenAI infra wave),
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI. C26 closed.
- **P49 (Vercel Drives GA by 2026-09-28): NOT MET as observed** — three
  first-party surfaces (changelog index, Sandbox docs, dedicated Drives
  page) agree on beta/private-beta state. The expectation's window closes
  tonight; the last in-window pass confirms the final grade.
- Watch-outs for the next surveyor: **C11 file-on-close** — the first
  pass that sees the Modal $15B / Baseten $26B talks close (or a
  definitive denial) files regardless of the clock; **C11 integration
  watch** — Carbon GA or a shipped sandbox product on Blaxel's
  primitives; **Modal egress billing effective Oct 1 (~2.3 days
  out)** — post-effective-date re-confirm rides the normal read;
  **agent-O DevDay confirmation gate Tue Sep-29 1pm ET** (only an
  actual OpenAI confirmation files C68); **Plugin4Shell** — watch for
  a REAL CVE assignment (seven "no CVE assigned" statements vs one
  fringe claim); **Mistral Vibe family** — re-fold only on a new
  member, a first-party advisory beyond MAI-2026-003, or demonstrated
  agent-infra exploitation; **Hugo advisories** — full-URL sweep
  continues (four Sep-28 Moderate advisories top the list,
  total ≥14); **NanoClaw/NanoCo** — re-grade only on a first-party
  sandbox/compute announcement; **BAND** — re-grade only if it ships
  a hosted/compute product; **Island / DataAgent** — below the bar
  unless they enter infra; **legacy-domain scope** — the canonical
  set is 2 domains + 2 YC paths (codified this cycle); aged-out
  items resurface only on real movement.
- **Process (next slot's brief):** the standing gates held cleanly
  this pass — both surveyors omitted per-read times from their
  captures, so no mtime rejections were needed. Keep the gates:
  capture-file mtime as completion evidence, reject any claimed time
  later than the mtime (including times inside the capture body),
  count from enumerations when header counts disagree, never declare
  an expectation dead before its window closes (P49 graded in-cycle as
  observed this pass — the window closes tonight; the final grade rides
  with the last in-window pass), corpus-grep before minting ("new to the
  lane" ≠ new to the corpus), verify first-party pages directly when
  a mirror stands in, verify timestamp claims against the capture
  file itself.
