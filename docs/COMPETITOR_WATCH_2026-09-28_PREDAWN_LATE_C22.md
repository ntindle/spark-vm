# Competitor watch — 2026-09-28 (pre-dawn late, cycle 22)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads bounded ~06:26–~06:28 CDT 2026-09-28 — see the
provenance note below) against the cycle-21 (~05:55 CDT) baseline —
**16/17 pages VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 1 UNVERIFIED**
(eleventh straight cycle with zero content deltas; the one unverified
page is a transport failure, not a content change — see provenance).
Surveyor B: delta news scan ~06:26–~06:27 CDT (evidence-bounded;
12 queries, snippet level, zero pages opened) — **1 NEW with evidence
(a flagged-watch delta, NOT a fold), 9 clean dedupes, 2 flagged-only,
0 new C-numbers** (seventeenth straight quiet B-lane night scan,
C6–C22).

Delta-only against the cycle-21 pre-dawn-late pass
(`docs/COMPETITOR_WATCH_2026-09-28_PREDAWN_LATE_C21.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-0624.md`,
`hidden_files/agent_notes/surveyor-b-20260928-0624.md`.

> **Timestamp provenance note:** surveyor A's capture claims a
> "~06:26–06:32 CDT" fetch window, but its file mtime is stat-certified
> **06:27:47 CDT** — the claimed end postdates its own write, the
> C15/C17 prospective-label defect repeated. All A-lane verification
> claims below are re-bounded to **~06:26–~06:28 CDT** (the mtime is the
> completion evidence; the "~06:32" label is superseded). Surveyor B's
> scan window ~06:26–~06:27 CDT matches its 06:27:36 mtime, and its
> verdict counts are as integrated below.
>
> **Integrator fold-hygiene (second cycle running):** surveyor B again
> recommended minting a corpus ID for the Baseten × Blaxel acquisition.
> Corpus grep rejects it again — the acquisition has been filed since
> 2026-09-18 (C11 "Baseten/Blaxel integration watch", vendor row, and
> the sources list has cited Baseten's own Business Wire announcement
> since the filing). "New to the lane" ≠ new to the corpus: clean
> dedupe, **no corpus change this cycle**.
>
> **Integrator transport-gap verification:** the surveyor-A
> DigitalOcean pricing 404 (twice, original + honest retry) is a
> **docs restructure, not a content delta** — the first-party page now
> lives at
> `docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/`
> (the corpus's Sep-23 watches cite this URL). The carry-over URL
> (missing the `agent-harness-runtime` segment) 404s; next cycle's
> surveyor uses the current URL. The baseline statements ("Last
> verified 22 Sep 2026" stamp; CPU $0.044/vCPU-hour; memory
> $0.0095/GB-hour; session storage $0.05/GiB-month; egress $0.01/GiB;
> snapshots $0.05/GiB-month) stand from prior live reads and are NOT
> counted as changed. Modal's egress terms were verified this cycle on
> the verbatim-content GitHub mirror of Modal's own docs page (the
> surveyor lacked the first-party carry-over URL); the terms match the
> baseline verbatim and the B lane independently corroborated the
> mirror — recorded as VERIFIED NO-CHANGE with the caveat that the
> first-party page was not opened; next cycle re-opens it directly.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~06:26–~06:28 CDT)

**16/17 pages VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 1 UNVERIFIED**
(transport failure, not absence — see provenance). Eleventh straight
cycle with zero content deltas. Fetches: 15/17 first-try, 1 search +
1 mirror open (Modal), 2 failed opens (the same DigitalOcean URL,
original + honest retry); zero fabrications.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); second still SEP 25 / V0.217.0 ("NVIDIA B300 GPU
   type"). No V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22**; the 2026-09-21 v3-kits entry verbatim
   unchanged.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**
   ("Full Changelog: v0.7.2…v0.7.3"); no newer tag.
4. **Vercel changelog + Sandbox docs — VERIFIED NO-CHANGE.** Index
   still top section **"27 September"** with the Ember-1 entry (still
   AI-Gateway lane, never Sandbox lane, never folded); sitemap newest
   2026-09-27, 1371 total posts; 23 September "Drives for Vercel
   Sandbox are now in public beta" unchanged — no GA entry anywhere
   on the index or sitemap; sandbox docs Features list still
   **"Drives (beta)"** (page last_updated 2026-09-22). **P49's
   2026-09-28 Drives-GA expectation is NOT met as of ~06:27 CDT** —
   the expectation's final day is ~27% elapsed at read time; the
   A-lane's normal Vercel reads keep re-grading the expectation, and
   the final grade lands on a later in-window cycle today. This watch
   does NOT declare the expectation failed.
5. **DigitalOcean Harness Runtime pricing — UNVERIFIED (transport
   failure, not a content delta).** The carry-over URL 404'd on the
   original open and the honest retry. The integrator's check (see
   provenance) shows the page moved to the `agent-harness-runtime`
   path — docs restructure. Baseline statements stand; re-verify next
   cycle on the current URL.
6. **Modal network-egress billing — VERIFIED NO-CHANGE (via verbatim
   mirror, first-party page not opened — see provenance).** Egress
   billing still starts **Oct 1, 2026** (~2.7 days out): allowances
   verbatim Starter **1 TiB** / Team **10 TiB** / Enterprise **100
   TiB**; overage **$0.04 per GiB**; first bill Nov 1, 2026; Volumes
   reads/writes excluded. No "went live early" chatter in either
   lane; post-effective-date re-confirm stays armed.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, no wording drift anywhere.
   AgentComputer still publishes **no first-party egress pricing
   line — C12 stays OPEN** (22nd consecutive first-party read, no
   wording drift).
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; `ycombinator.com/companies/ascii` renders
   the Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. Migration-complete state
   holds; no ASCII-retirement signals.

Standing bar (first-party advisory sweep, cycle-22 check): **Hugo**
— no 100690-specific GHSA on gohugoio/hugo/security/advisories
(10 advisories: 5 Sep 9 / 2 Aug 27 / 3 Jun 18, newest
GHSA-x3mx-cm49-8m9c verbatim as prior cycle). Stays out.

## Surveyor B — delta news scan (~06:26–~06:27 CDT, evidence-bounded): 1 NEW (not a fold) / 9 clean dedupes / 2 flagged-only

**NEW with evidence (1 — a flagged-watch delta, NOT a fold).** The
purported **"CVE-2026-92104" (Plugin4Shell) has begun circulating on
one fringe aggregator** (sh3llc0d3.com titles its piece "tracked as
CVE-2026-92104") — but five independent sources say the opposite,
explicitly, the freshest dated Sep 27 (aiidelist.com: "No public
Plugin4Shell CVE was identified in the sources reviewed ... as of
September 27, 2026", warning security teams not to invent
`CVE-2026-XXXX` identifiers). The verdict stays **suspect — do not
cite**; no fold, no C-number. New color on the same watch: vendor
patch state — Claude Code patched (2.1.179), Codex patched (0.146.0),
Copilot unpatched, Gemini CLI will-not-fix (retiring toward
Antigravity).

**Clean dedupes (pre-window, re-queried — 9, header count agrees):**
Modal $15B / Baseten $26B talks (C11 — still "in talks", both
declined to comment; third-party recaps of the Sep 23 Bloomberg
report; bytevyte tracker reiterates "Neither round has closed, and
terms could still shift" — FILE ON CLOSE stays armed); agent-O echo
(twenty-second daily cycle — leak/speculation only, zero OpenAI
confirmation; DevDay Tue Sep-29 1pm ET gate stands ~30h out — only an
actual OpenAI confirmation files C68; the C68 reservation stands);
Mistral Vibe 87984–88 cluster (recaps only — a new SecMate blog post
mapping SECMATE-2026-0038/39 is a recap, not a new cluster member; no
first-party Mistral advisory beyond MAI-2026-003; no demonstrated
agent-infra exploitation — below the re-fold bar); Hugo
CVE-2026-100690 (aggregator-only — thehackerwire record received Sep
26, EPSS 0.35% low, no exploit; other entries are for OTHER Hugo
CVEs; no 100690-specific GHSA; A-lane re-sweeps the advisory page
directly — stays out); Modal egress billing (third-party GitHub
skill mirror matches baseline exactly; no "went live early" chatter
— standing); Vercel Drives GA — no GA anywhere, still public beta
(third-party deep-dives corroborate the A-lane verdict; P49 NOT met
as of read time — never declared dead before EOD); NanoClaw/NanoCo
(recaps only — March Docker Sandboxes partnership, NanoCo × Vercel
× OneCLI approval/credentials partnership is NOT a sandbox/compute
announcement; an unverified syndicated snippet about a NanoCo $12M
seed raise stays below the corroboration bar — no re-grade); Docker
Cloud Sandboxes Sep-24 launch + BAND × Docker Sandboxes integration
(ecosystem activity, already in-corpus; new corroborating color:
Docker's president says containers aren't sufficient for agent
isolation, Cloud Sandboxes run on a custom cross-platform VMM, up
to 16 vCPUs, per-second billing — BAND ships a coordination layer,
not a hosted/compute product — below the fold bar); Daytona/E2B
funding + lane news (stale — Daytona $24M Series A Feb 2026, E2B
$21M Series A Jul 2025; no new company announcements — not folded).

**Flagged-only (NOT folded — numbered verdicts):**
1. **Plugin4Shell — still NO real CVE assigned.** The one attribution
   (sh3llc0d3.com's "CVE-2026-92104") is fringe and contradicted by
   five independent "no CVE" statements. The NEW delta this cycle is
   only that the suspect ID has started circulating — verdict stays
   suspect; do not cite. Not foldable — keep watching.
2. **CVE-2026-67623 (Mistral Vibe <2.23.3, git fsmonitor-hook RCE,
   August vintage)** — did not surface in this cycle's snippets at
   all. Below the post-93993 re-fold bar as before; carried as
   standing context.

**Not re-queried this cycle (carried as standing, NOT asserted as
re-verified):** OpenAI Sep 20 DNS-escape recaps, OpenAI–Hugging Face
July intrusion commentary, AI-inference funding wave. No in-window
movement was asserted for these items; the next surveyor re-checks.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (seventeenth straight quiet
  B-lane night scan, C6–C22). No new corpus entries this pass.
- **Corpus movement: none.** No new C-number this pass. C69 (Mistral
  Vibe CVE-2026-93993) stands as the newest corpus entry from C20.
  Surveyor B's Baseten × Blaxel mint recommendation was rejected at
  the corpus-grep gate (already C11 — second cycle running).
- **P63 aging pipeline — no new age-outs this pass.** No dedicated
  aging queries run; none of the aged-out items showed in-window
  movement in this scan's snippets.
  - **C11 (Baseten/Blaxel integration watch) — stays open, nothing
    shipped.** The acquisition is already filed (C11 watch, vendor
    row, first-party Business Wire citation since filing); this
    cycle's materials add nothing new (beri.net FAQ is the same
    Sep-24-vintage doc). The watch stays open until a shipped product
    lands.
  - Aged-out stay out: C29 (Boxd), C45, C56, C66, C67 (Huawei CodeArts
    Malaysia — re-fold path stands on real movement), C62 (OpenAI infra
    wave — aged out at C15; vendor facts retained as canonical
    reference; re-fold on real movement), Heapjack/Overpatch, GitLab
    CVE-2026-85706, Dextr AI. C26 closed.
  - C12 (AgentComputer) stays OPEN — still no first-party egress
    pricing line (22nd consecutive read, no wording drift). No re-folds.
- **P49 (Vercel Drives GA): the 2026-09-28 expectation is NOT met**
  as of ~06:27 CDT. No GA entry on the first-party changelog index or
  sitemap, no third-party GA chatter, sandbox docs still grade "Drives
  (beta)". The A-lane's normal Vercel reads keep re-grading the
  expectation (final day ~27% elapsed at read time); **the final
  grade lands on a later in-window cycle today — this watch does NOT
  declare the expectation failed.**
- **Ember-1 index status: STABLE.** No flip-flop this pass — the
  "27 September" index section carries the entry (AI-Gateway lane,
  never folded).
- Watch-outs for the next surveyor: **C11 file-on-close** — the first
  pass that sees the Modal $15B / Baseten $26B talks close (or a
  definitive denial) files regardless of the clock; **C11 integration
  watch** — Baseten's "Hosted Tools" blog/changelog/docs for a shipped
  sandbox product on Blaxel's primitives; **Modal egress billing
  effective Oct 1 (~2.7 days out)** — re-open the FIRST-PARTY Modal
  docs page directly this cycle's mirror left a gap (the mirror
  matched baseline verbatim and B corroborated it, but the
  first-party read is owed); **DigitalOcean pricing** — re-verify on
  the CURRENT first-party URL
  (`.../products/managed-agents/agent-harness-runtime/details/pricing/`;
  the old URL 404s after a docs restructure); **agent-O DevDay
  confirmation gate Tue Sep-29 1pm ET** (only an actual OpenAI
  confirmation files C68 — the C68 reservation stands);
  **Plugin4Shell** — watch for a REAL CVE assignment (treat
  "CVE-2026-92104" as suspect until CVE-db corroborated — it now
  circulates on one fringe aggregator, still contradicted by five
  independent "no CVE" statements); **Mistral Vibe family** — re-fold
  on an additional new family member, a first-party Mistral advisory
  beyond MAI-2026-003, or demonstrated agent-infra exploitation (the
  87984–88 cluster and CVE-2026-67623 stay below bar); **Hugo
  CVE-2026-100690** — direct gohugoio/hugo/security/advisories sweep
  continues (A-lane; use the full URL — the shorthand 404s);
  **NanoClaw/NanoCo** — re-grade only on a first-party
  sandbox/compute announcement (the Vercel/OneCLI approval
  partnership does not meet it; the weedoany $12M-seed snippet is
  unverified); **P49 Drives GA** — final grade pending EOD
  2026-09-28 (re-graded by the A-lane's normal Vercel reads; later
  in-window cycles today carry it); **BAND × Docker Sandboxes** —
  ecosystem activity only, re-grade only if BAND ships a
  hosted/compute product; aged-out items (C29, C45, C56, C66, C67,
  C62, Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI)
  resurface only on real movement.
- **Process (next slot's brief):** the standing review gate held
  except for one repeat: surveyor A again wrote a prospective window
  label ("~06:26–06:32") postdating its own 06:27:47 mtime — the
  integrator re-bounded all A-lane claims to the mtime (see
  provenance). New lesson: when the carry-over URL 404s, the surveyor
  should check for a docs restructure (the path segment moved) rather
  than only retrying the dead URL — the integrator closed that gap
  this cycle via a targeted search. Keep the gate: treat each capture
  file's mtime as completion evidence, reject any claimed time later
  than the mtime, count surveyor-B dedupes from the enumeration when
  the header count disagrees, never declare an expectation dead
  before its window closes, grep the corpus for the fold candidate
  before minting ("new to the lane" ≠ new to the corpus), and verify
  first-party pages directly when a mirror stands in.
