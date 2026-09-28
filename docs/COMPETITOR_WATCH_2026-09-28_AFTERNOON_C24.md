# Competitor watch — 2026-09-28 (afternoon, cycle 24)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads completed by the 16:03:01 CDT stat-certified
mtime) against the cycle-23 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (14 first-try
fetch successes, 0 failures; 4/4 searches). Surveyor B: delta news scan
(evidence-bounded; snippet level, zero pages opened, completed by the
16:03:12 CDT stat-certified mtime) — **0 NEW with evidence, 11 clean
dedupes, 2 flagged-only, 0 new in-lane launches** (nineteenth straight
quiet B-lane scan, C6–C24).

Delta-only against the cycle-23 afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-28_AFTERNOON_C23.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-1554.md`,
`hidden_files/agent_notes/surveyor-b-20260928-1554.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** both surveyors wrote captures with NO
> per-read times in the body this cycle — the standing rule held
> cleanly, with no postdating claims to reject. All verdicts below are
> mtime-bounded: A-lane to 16:03:01 CDT, B-lane to 16:03:12 CDT.
>
> **Count-honesty check (one correction):** surveyor B's Plugin4Shell
> line says "six independent sources" but enumerates seven
> (shattered.io, neuralcoretech.com, pranava0x0's vibe-coding-security
> advisory, deafnews.it, dailyaiblog.com, securityonline.info,
> buymeacoffee) — the enumeration rules; seven is carried below. The
> header counts (0 NEW / 11 dedupes / 2 flagged-only) agree with the
> enumerations.
>
> **Integrator fold-gate:** no fold candidates this pass — no mint
> recommended, so no corpus grep was needed and no corroboration pass
> ran. Surveyor B's extra C70 outlet mentions (techrepublic, unite.ai,
> que.com, explainx.ai, tech-insider.org, plus an OpenShell 0.1.0
> release detail) are corroboration color on the already-folded C70,
> not a new fold. The Baseten × Blaxel acquisition stays deduped at the
> C11 gate — no mint recommended, fourth cycle running.

## Surveyor A — fast-mover + pricing re-verification (first-party, completed by 16:03:01 CDT mtime)

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
   The "28 September" section still has exactly the C23 two entries
   (Claude Sonnet 5.5 on AI Gateway; Sandbox memory observability
   re-list) — no Drives GA entry. Sandbox docs still
   `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
   Features list. **P49 (Drives GA by 2026-09-28): NOT met as of this
   read** — the day's window is still open, so no final grade is
   declared; reserved for a later in-window cycle. Out-of-band,
   ungraded: this render's Related-pages list links a "Drives for
   Vercel Sandbox in Private Beta" page — surveyor A did not open
   that entry this cycle; flagged for next cycle to reconcile against
   the "Drives (beta)" Features-list text.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Oct 1, 2026
   start; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB; overage
   $0.04/GiB; first bill Nov 1, 2026; Volumes excluded. No
   went-live-early signals (~2.5 days to the effective date).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (24th
   consecutive first-party read, no wording drift).
8. **Boat legacy domains — VERIFIED NO-CHANGE (2/2).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; migration-complete state holds.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE.** The four
   Sep-28 Moderate advisories still top the list; total ≥14; no
   100690-specific advisory. Standing bar holds.

## Surveyor B — delta news scan (evidence-bounded, completed by 16:03:12 CDT mtime): 0 NEW / 11 clean dedupes / 2 flagged-only

**NEW with evidence (0 — none).** The in-lane launch search surfaced
only the already-folded C70 (additional outlet corroboration) and
out-of-lane model releases (NaiveAI N0.5-Flash open weights, MiniMax
M3.1-Flash-Preview, Meituan LongCat-2.5-Preview) — none in-lane.

**Clean dedupes (11, header count agrees):**
1. Modal $15B / Baseten $26B funding talks (C11) — recaps only
   ("talks"/"discussions" per the Sep-23 Bloomberg reporting); zero
   close signals, zero denials. FILE ON CLOSE stays armed.
2. Baseten "Carbon" (C11) — first-party blog still "private preview ...
   rolling out progressively"; no GA. Below the shipped-product bar.
3. agent-O rumor (C68 reservation) — twenty-fourth daily cycle,
   leak/speculation only; zero OpenAI confirmation. DevDay Tue Sep-29
   1pm ET gate stands.
4. Mistral Vibe family — no new member, no first-party advisory beyond
   MAI-2026-003, no demonstrated agent-infra exploitation. Below the
   re-fold bar.
5. Plugin4Shell — "CVE-2026-92104" stays suspect: seven independent
   sources explicitly state NO CVE assigned as of publication. Do NOT
   cite it as assigned.
6. Hugo CVE-2026-100690 — aggregator-only (TheHackerWire analysis,
   Sep-26; EPSS 0.35% LOW); no GHSA. Stays out.
7. NanoClaw/NanoCo — no first-party sandbox/compute announcement
   (Docker-integration recaps, NanoCo $12M seed, NanoClaw×Vercel/OneCLI
   agent-UX partnership). Below the re-grade bar.
8. BAND × Docker Sandboxes — Sep-24 integration recaps; ecosystem
   activity only (already folded as C45 garnish). BAND has shipped no
   hosted/compute product.
9. Daytona/E2B funding — stale rounds only; a database-reported
   Daytona Series B stays "not publicly verified" — database claims
   don't count.
10. Modal egress billing (Oct-1 start) — no "went live early" chatter.
11. Vercel Drives GA (P49) — all snippets say public beta (announced
    2026-09-23); no third-party GA chatter. NOT met as observed; the
    final grade waits for a later in-window cycle.

**Flagged-only (NOT folded — numbered verdicts):**
1. **Instinct $1B Series C at $10B** — VERDICT: below the fold bar.
   CONFIRMED CLOSED today (Instinct's own Sep-28 press release:
   Sequoia/Benchmark/Coatue; personal AI agent, early access; new
   Concierge and Trusted Person Network features). A consumer agent
   app, not sandbox/compute infra — its "isolated sandboxes" language
   is a privacy-policy feature of the consumer app, not an infra
   product. No fold.
2. **Anthropic Claude Marketplace** — VERDICT: adjacent-lane, below the
   fold bar. Announced today (Sep-28): a public directory of 2,000+
   connectors/plugins (Atlassian, Google, Microsoft, Notion,
   Salesforce, CrowdStrike, Cursor, Harvey, Lovable, Snowflake; MCP +
   Agent Skills). Agent-distribution/marketplace lane, not
   sandbox/compute infra. Recorded as color; no fold.

**Not re-queried this cycle (carried as standing, NOT asserted as
re-verified):** OpenAI Sep 20 DNS-escape recaps, OpenAI–Hugging Face
July intrusion commentary, AI-inference funding wave. The next
surveyor re-checks.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (nineteenth
  straight quiet B-lane scan, C6–C24).
- **Corpus movement (P63): none.** No new C-numbers minted, no
  age-outs. C70 (NVIDIA Open Agent Safety Platform) stands as the
  latest mint. C11 (Baseten/Blaxel integration watch) stays OPEN —
  talks unclosed (FILE ON CLOSE armed), Carbon still private preview.
  C12 (AgentComputer) stays OPEN — 24th consecutive no-egress-line
  read. Aged-out stay out: C29 (Boxd), C45, C56, C66, C67 (Huawei
  CodeArts Malaysia), C62 (OpenAI infra wave), Heapjack/Overpatch,
  GitLab CVE-2026-85706, Dextr AI. C26 closed.
- **P49 (Vercel Drives GA by 2026-09-28): NOT met as of ~16:03 CDT**
  (day's window ~67% elapsed). No GA on the first-party changelog
  index, sandbox docs, or third-party chatter. This watch grades as
  observed and does NOT declare the expectation failed — the final
  grade lands on a later in-window cycle today.
- **Ember-1 index: STABLE.** No flip-flop — the "28 September"
  section carries exactly the C23 two entries.
- Watch-outs for the next surveyor: **P49 final grade** — the window
  closes tonight; a later in-window cycle delivers the final grade;
  **C11 file-on-close** — the first pass that sees the Modal $15B /
  Baseten $26B talks close (or a definitive denial) files regardless
  of the clock; **C11 integration watch** — Carbon GA or a shipped
  sandbox product on Blaxel's primitives; **Modal egress billing
  effective Oct 1 (~2.5 days out)** — post-effective-date re-confirm
  rides the normal read; **agent-O DevDay confirmation gate Tue
  Sep-29 1pm ET** (only an actual OpenAI confirmation files C68);
  **Plugin4Shell** — watch for a REAL CVE assignment (seven "no CVE
  assigned" statements vs one fringe claim); **Mistral Vibe family** —
  re-fold only on a new member, a first-party advisory beyond
  MAI-2026-003, or demonstrated agent-infra exploitation; **Hugo
  advisories** — full-URL sweep continues (four Sep-28 Moderate
  advisories top the list, total ≥14); **NanoClaw/NanoCo** — re-grade
  only on a first-party sandbox/compute announcement; **BAND** —
  re-grade only if it ships a hosted/compute product; **Instinct** —
  below the bar unless it enters infra; **Anthropic Claude
  Marketplace** — below the bar unless it enters infra; **Vercel
  wording** — reconcile the docs' "Drives (beta)" Features-list text
  against the related-link "Drives for Vercel Sandbox in Private
  Beta" title; aged-out items resurface only on real movement.
- **Process (next slot's brief):** the standing gates held cleanly
  this pass — both surveyors omitted per-read times from their
  captures, so no mtime rejections were needed. Keep the gates:
  capture-file mtime as completion evidence, reject any claimed time
  later than the mtime (including times inside the capture body),
  count from enumerations when header counts disagree, never declare
  an expectation dead before its window closes, corpus-grep before
  minting ("new to the lane" ≠ new to the corpus), verify first-party
  pages directly when a mirror stands in, verify timestamp claims
  against the capture file itself.
