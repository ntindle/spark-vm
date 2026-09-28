# Competitor watch — 2026-09-28 (afternoon, cycle 23)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads completed by the 15:43:04 CDT stat-certified
mtime 2026-09-28 — see the provenance note below) against the cycle-22
(~06:27 CDT) baseline —
**7 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED** (both transport
gaps from cycle 22 are closed this cycle: the DigitalOcean page on the
current first-party URL, the Modal egress page on the first-party docs
page). Surveyor B: delta news scan (evidence-bounded; 13 queries,
snippet level, zero pages opened, completed by the 15:41:46 CDT
stat-certified mtime) — **1 NEW with evidence
(folded), 10 clean dedupes, 2 flagged-only, 0 new in-lane launches**
(eighteenth straight quiet B-lane scan, C6–C23 — the one fold is
adjacent-lane safety infrastructure, not an in-lane launch).

Delta-only against the cycle-22 pre-dawn-late pass
(`docs/COMPETITOR_WATCH_2026-09-28_PREDAWN_LATE_C22.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-1524.md`,
`hidden_files/agent_notes/surveyor-b-20260928-1524.md`.

> **Timestamp provenance note:** surveyor A's capture is stat-certified
> mtime **15:43:04 CDT**; all A-lane verification claims below are
> re-bounded to the mtime (reads completed by 15:43:04). The capture
> body's per-read times (15:50–15:58) **postdate the mtime and are
> rejected as unreliable** per the standing rule — no A-lane verdict
> below depends on them. Surveyor B's capture is stat-certified mtime
> **15:41:46 CDT**; its header's "~15:40–15:55" end label postdates the
> mtime and is likewise rejected — B-lane claims below are re-bounded
> to the mtime (~15:3x–~15:41 CDT). Lesson: verify timestamp claims
> against the capture file itself, never against the surveyor's report.
>
> **Integrator fold-gate (third cycle running):** surveyor B again
> recommended minting a corpus ID for the Baseten × Blaxel acquisition.
> Corpus grep rejects it again — the acquisition has been filed since
> 2026-09-18 (C11 "Baseten/Blaxel integration watch", vendor row, and
> the sources list has cited Baseten's own Business Wire announcement
> since the filing). "New to the lane" ≠ new to the corpus: clean
> dedupe, **no corpus change on this item**.
>
> **Integrator corroboration check:** the surveyor-B fold candidate
> (NVIDIA's platform launch) was corroborated by the integrator with an
> independent search — six independent outlets (Fast Company,
> TechCrunch, HCNTimes, Cybernews, fellowpress, madhyamamonline) report
> the same announcement, same components, same partner list, all
> dated today. It clears the corroboration bar.

## Surveyor A — fast-mover + pricing re-verification (first-party, completed by 15:43:04 CDT mtime)

**7 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED.** Fetches: 17
first-try successes; 1 first-try failure from the surveyor's own wrong
URL (`/docs/sandbox/features` 404'd, corrected to `/docs/sandbox`,
retry succeeded); 0 unresolved failures; 6/6 searches succeeded. One
outlink navigation from the Vercel changelog mislanded on vercel.com/ai
— the entry text was already captured in the index read, so no verdict
depends on it. Zero fabrications.

**DELTA 1 — Vercel changelog index.** New top section "28 September"
with two entries: *"Claude Sonnet 5.5 now available on AI Gateway —
Access Claude Sonnet 5.5 through Vercel AI Gateway with the AI SDK,
compatible APIs, or coding agents…"* (AI-Gateway lane, never folded)
and *"Vercel Sandbox now supports memory observability — Vercel
sandbox memory usage data can now be accessed in the dashboard and
CLI."* (memory observability has been a known sandbox-lane fact since
9/25 — this is a re-list, not a new capability). **No Drives GA
entry** — the latest Drives statement is still the public-beta one.
P49's 2026-09-28 Drives-GA expectation is **NOT met as of ~15:42 CDT**
(the expectation's final day is ~65% elapsed at read time; this watch
grades as observed and does NOT declare the expectation failed — the
final grade lands on a later in-window cycle today). Sandbox docs
sub-check: `last_updated: 2026-09-22` and **"Drives (beta)"** both
intact (NO-CHANGE).

**DELTA 2 — Hugo advisories (full URL used).** FOUR new advisories
published **Sep 28, 2026**, all Moderate:
GHSA-3jfr-vjcq-7jvf ("css.Sass allowed themes to read files outside
the project via the Sass compiler's import fallback"),
GHSA-r4xx-89rf-5424 ("js.Build allowed themes to read files outside
the project via ESBuild's fallback resolver"),
GHSA-6c8w-mpp8-9w47 ("Symlink in nested-mount ancestor directory of a
theme exposes files outside the module"), GHSA-wcpj-vcvm-j4pg
("Stored XSS via unescaped heading ID in Table of Contents HTML").
Total known advisories now **≥14** (baseline 10 + 4 new). No
100690-specific GHSA observed. Standing bar holds (no 100690-specific
GHSA); the four new advisories are adjacent-lane (static-site-generator
theme CVEs, Moderate) — below the fold bar, recorded as standing-bar
color.

**NO-CHANGE items:**
1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   SEP 26 2026 / V0.218.0; second still SEP 25 / V0.217.0. No V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at 2026-09-22; the 2026-09-21 v3-kits entry verbatim unchanged.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**;
   no newer tag.
4. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE (first
   party, current URL — the cycle-22 transport gap is closed).** The
   page opens on the current first-party URL; all five figures
   ($0.044/vCPU-hour, $0.0095/GB-hour, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month) and
   the "Last verified 22 Sep 2026" stamp intact.
5. **Modal network-egress billing — VERIFIED NO-CHANGE (first-party
   page — the cycle-22 mirror gap is closed).** Verified on Modal's
   own docs page (modal.com/docs/guide/network-egress-billing):
   billing starts **Oct 1, 2026** (~2.5 days out); allowances verbatim
   Starter **1 TiB** / Team **10 TiB** / Enterprise **100 TiB**;
   overage **$0.04 per GiB**; first bill Nov 1, 2026; Volumes
   reads/writes excluded. No "went live early" signals; the
   post-effective-date re-confirm stays armed.
6. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, no wording drift. AgentComputer
   still publishes **no first-party egress pricing line — C12 stays
   OPEN** (23rd consecutive first-party read, no wording drift).
7. **Boat legacy domains — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; both YC paths render Boat branding
   natively. Migration-complete state holds.

## Surveyor B — delta news scan (evidence-bounded, completed by 15:41:46 CDT mtime): 1 NEW (folded) / 10 clean dedupes / 2 flagged-only

**NEW with evidence (1 — folded):**

1. **C70 — NVIDIA Open Agent Safety Platform: folded.** Announced
   2026-09-28 (Jensen Huang launch): the platform pairs **OpenShell**
   (open-source, Apache 2.0 — sandboxed agent-policy runtime with
   kernel-level isolation, runs on Nvidia's Vera CPUs; OpenShell
   itself was first announced in March — the new thing today is the
   combined platform) with **Sentry** (out-of-band monitor/quarantine
   on BlueField-4 data processing units via DOCA, independent of the
   agent's CPU/GPU, millisecond-scale containment; not open source).
   100+ named partners (Anthropic, Microsoft, Salesforce, SpaceXAI,
   Cisco, Oracle, CoreWeave, Dell, HPE, Lenovo, Arm, Intel); OpenAI
   notably not included. **Bar transparency:** this is adjacent-lane
   (safety infrastructure for agent runtimes), not an in-lane
   sandbox/compute launch — folded in the C69 family (adjacent-lane
   security item, disclosed as such). The mint rests on the
   corroboration criterion: six independent outlets report the same
   announcement, components, and partner list, all dated today. The
   corpus gate clears it — "OpenShell" appears in the corpus only as
   a C54 research reference (Perplexity SPACE tested it), "Sentry"
   has zero hits, and the platform as a launched product is nowhere
   in the corpus. The mint does not change the in-lane no-launch
   verdict. Vendor framing (not folded as fact): Nvidia claims the
   platform could have prevented the OpenAI/Hugging Face July breach.

**Clean dedupes (pre-window, re-queried — 10, header count agrees):**
Modal $15B / Baseten $26B talks (C11 — recaps only, no close signal;
FILE ON CLOSE stays armed); agent-O echo (twenty-third daily cycle —
leak/speculation only, zero OpenAI confirmation; DevDay Tue Sep-29
1pm ET gate stands — only an actual OpenAI confirmation files C68;
the C68 reservation stands); Mistral Vibe family (no new member, no
first-party advisory beyond MAI-2026-003, no demonstrated agent-infra
exploitation — below the re-fold bar); Plugin4Shell (the suspect
"CVE-2026-92104" stays suspect — independent Sep-23 and Sep-27 "no
CVE assigned" statements contradict the single fringe aggregator;
do not cite); Vercel Drives GA (no GA anywhere — public beta stands;
P49 NOT met as of read time, never declared dead before EOD);
Hugo CVE-2026-100690 (aggregator-only, no GHSA; A-lane re-sweeps the
advisory page directly — stays out); NanoClaw/NanoCo (no first-party
sandbox/compute announcement — below the re-grade bar); BAND ×
Docker Sandboxes (ecosystem activity only — already folded as C45
garnish); Daytona/E2B funding (stale — no new company announcements);
Modal egress billing (in-corpus; Oct-1 start not yet reached, no
"went live early" chatter — standing).

**Flagged-only (NOT folded — numbered verdicts):**
1. **Baseten "Carbon" private preview** (first-party baseten.co blog,
   ~20h old) — real in-window C11 movement, but a private preview
   marked "coming soon" is below the SHIPPED-product bar. Do not
   fold; re-grade on GA.
2. **Instinct $1B Series C at $10B** — in-window funding, but a
   consumer agent app, not sandbox/compute infra. Below the fold bar.

**Not re-queried this cycle (carried as standing, NOT asserted as
re-verified):** OpenAI Sep 20 DNS-escape recaps, OpenAI–Hugging Face
July intrusion commentary, AI-inference funding wave. No in-window
movement was asserted for these items; the next surveyor re-checks.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (eighteenth
  straight quiet B-lane scan, C6–C23). The one fold this cycle (C70)
  is adjacent-lane safety infrastructure, not an in-lane launch.
- **Corpus movement (P63): C70 minted** — NVIDIA Open Agent Safety
  Platform (OpenShell + Sentry), adjacent-lane, disclosed. The mint
  lives in this watch doc (the C69 precedent for adjacent-lane
  items); no vendor field-table row in the corpus — it is not a
  sandbox provider's product row. C69 stands as the previous mint.
- **P63 aging pipeline — no new age-outs this pass.** No dedicated
  aging queries run; none of the aged-out items showed in-window
  movement in this scan's snippets.
  - **C11 (Baseten/Blaxel integration watch) — stays open, nothing
    shipped.** Baseten's "Carbon" is a private preview, below the
    shipped-product bar. The Modal $15B / Baseten $26B talks are
    still unclosed — FILE ON CLOSE stays armed. The × Blaxel
    acquisition stays cleanly deduped (third cycle the mint
    recommendation was rejected at the corpus-grep gate).
  - Aged-out stay out: C29 (Boxd), C45, C56, C66, C67 (Huawei
    CodeArts Malaysia — re-fold path stands on real movement), C62
    (OpenAI infra wave — aged out at C15; vendor facts retained as
    canonical reference; re-fold on real movement), Heapjack/
    Overpatch, GitLab CVE-2026-85706, Dextr AI. C26 closed.
  - C12 (AgentComputer) stays OPEN — still no first-party egress
    pricing line (23rd consecutive read, no wording drift). No
    re-folds.
- **P49 (Vercel Drives GA): the 2026-09-28 expectation is NOT met**
  as of ~15:42 CDT. No GA entry on the first-party changelog index
  or sandbox docs; no third-party GA chatter. The expectation's
  final day is ~65% elapsed at read time — **the final grade lands
  on a later in-window cycle today; this watch does NOT declare the
  expectation failed.**
- **Ember-1 index status: STABLE.** No flip-flop this pass — the new
  "28 September" section carries the Sonnet 5.5 AI-Gateway entry
  (never folded) alongside the memory-observability re-list.
- Watch-outs for the next surveyor: **P49 final grade** — the
  expectation's window closes tonight; a later in-window cycle today
  delivers the final grade; **C11 file-on-close** — the first pass
  that sees the Modal $15B / Baseten $26B talks close (or a
  definitive denial) files regardless of the clock; **C11
  integration watch** — Baseten's "Carbon" GA or a shipped sandbox
  product on Blaxel's primitives; **Modal egress billing effective
  Oct 1 (~2.5 days out)** — post-effective-date re-confirm (the
  first-party gap is now closed, so the re-confirm rides the normal
  read); **agent-O DevDay confirmation gate Tue Sep-29 1pm ET**
  (only an actual OpenAI confirmation files C68 — the C68 reservation
  stands); **Plugin4Shell** — watch for a REAL CVE assignment
  (treat "CVE-2026-92104" as suspect until CVE-db corroborated);
  **Mistral Vibe family** — re-fold on an additional new family
  member, a first-party Mistral advisory beyond MAI-2026-003, or
  demonstrated agent-infra exploitation (the 87984–88 cluster and
  CVE-2026-67623 stay below bar); **Hugo advisories** — the full-URL
  sweep continues (four new Sep-28 Moderate advisories this cycle;
  total ≥14); **NanoClaw/NanoCo** — re-grade only on a first-party
  sandbox/compute announcement; **BAND × Docker Sandboxes** —
  ecosystem activity only, re-grade only if BAND ships a
  hosted/compute product; **Instinct** — consumer agent app, below
  the bar unless it enters infra; aged-out items (C29, C45, C56,
  C66, C67, C62, Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr
  AI) resurface only on real movement.
- **Process (next slot's brief):** the standing review gate fired
  this cycle and the doc carries the correction, not the defect:
  surveyor A's capture body lists per-read times (15:50–15:58) that
  postdate its own 15:43:04 mtime, and surveyor B's header labels a
  "~15:40–15:55" window that postdates its 15:41:46 mtime — both
  rejected per the standing rule; only mtime-bounded claims are
  asserted. Keep the gate: treat each
  capture file's mtime as completion evidence, reject any claimed
  time later than the mtime (including times inside the capture body
  itself), count surveyor-B dedupes from the enumeration when the
  header count disagrees, never declare an expectation dead before
  its window closes, grep the corpus for the fold candidate before
  minting ("new to the lane" ≠ new to the corpus), verify
  first-party pages directly when a mirror stands in, and verify
  timestamp claims against the capture file itself — never against
  the surveyor's report.
