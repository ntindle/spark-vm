# Competitor watch — 2026-09-28 (pre-dawn late, cycle 21)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads bounded ~05:55–~05:56 CDT 2026-09-28 — see the
provenance note below) against the cycle-20 (~05:26 CDT) baseline —
**8/8 VENDOR-VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 17/17 first-try**
(tenth straight fully-quiet A-lane pass of the nightly series; zero
retries). Surveyor B: delta news scan ~05:55–~05:56 CDT
(evidence-bounded; 12 queries, snippet level, zero pages opened) —
**0 NEW with evidence, 11 clean dedupes, 2 flagged-only, 0 NEW in-lane**
(sixteenth straight quiet B-lane night scan, C6–C21).

Delta-only against the cycle-20 pre-dawn-late pass
(`docs/COMPETITOR_WATCH_2026-09-28_PREDAWN_LATE_C20.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260928-0554.md`,
`agent_notes/surveyor-b-20260928-0554.md` (under `hidden_files`).

> **Timestamp provenance note:** neither surveyor capture carries a
> prospective completion label this pass — the C15/C17 defect did NOT
> repeat. Surveyor A completed ~05:56 CDT, file write (mtime)
> stat-certified 05:56:24 CDT; surveyor B's scan window ~05:55–~05:56 CDT
> matches its capture mtime, and its verdict counts are as integrated
> below. All verification claims below are bounded to the A-lane window
> ~05:55–~05:56 CDT and the B-lane scan window ~05:55–~05:56 CDT
> 2026-09-28.
>
> **Integrator correction (fold hygiene):** surveyor B's capture labels
> the Baseten × Blaxel acquisition "NEW with evidence" and recommends a
> corpus fold. Corpus grep shows the acquisition is **already filed** —
> C11 is the "Baseten/Blaxel integration watch" and the Sep-10
> acquisition is noted in the corpus vendor row and watch history. The
> item is reclassified as a **clean dedupe** (already in corpus), and
> **no corpus change ships this cycle** — the pulse2/techintelpro/
> techdefused/runtimewire recaps are third-party recaps of an already
> first-party-cited deal (the corpus's sources list has cited Baseten's
> own Business Wire announcement since the filing) and are below the
> fold bar: noted, not folded. **Correction of the integrator's own
> first draft (caught in adversarial review):** an earlier draft of
> this note claimed the Business Wire citation was a new
> "corroboration upgrade" this cycle — false; the citation has been in
> the corpus sources list since the acquisition was filed. The honest
> account is a clean dedupe with no corpus change. No new C-number
> minted.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~05:55–~05:56 CDT)

**8/8 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 17/17 first-try** (16 vendor
URLs + the Vercel changelog sitemap). Tenth straight fully-quiet A-lane
pass of the nightly series; zero retries. Cycles 18, 19, 20, and 21 all
8/8 NO-CHANGE — four consecutive fully-quiet cycles.

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
   2026-09-27; 23 September "Drives for Vercel Sandbox are now in public
   beta" unchanged — no GA entry anywhere on the index; sandbox docs
   Features list still **"Drives (beta)"** (page last_updated
   2026-09-22). **P49's 2026-09-28 Drives-GA expectation is NOT met as of
   ~05:56 CDT** — the expectation's final day is ~25% elapsed at read
   time; the A-lane's normal Vercel reads keep re-grading the
   expectation, and the final grade lands on a later in-window cycle
   today. This watch does NOT declare the expectation failed.
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical; the "Last verified 22 Sep 2026" stamp IS
   present. The docs index page's "Last verified 21 Sep 2026" is a
   different page — explicitly NOT a delta.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~2.75 days out): allowances verbatim
   Starter **1 TiB** / Team **10 TiB** / Enterprise **100 TiB**;
   overage **$0.04 per GiB**; first bill Nov 1, 2026 — verified on
   Modal's own docs page this pass. No "went live early" chatter in
   either lane; post-effective-date re-confirm stays armed.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical, no wording drift anywhere.
   AgentComputer still publishes **no first-party egress pricing
   line — C12 stays OPEN** (21st consecutive first-party read, no
   wording drift).
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage
   natively — no redirect; `ycombinator.com/companies/ascii` renders
   the Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. Migration-complete state
   holds; no ASCII-retirement signals.

Standing bar (first-party advisory sweep, cycle-21 check): **Hugo**
— no 100690-specific GHSA on gohugoio/hugo/security/advisories
(10 advisories: 5 Sep 9 / 2 Aug 27 / 3 Jun 18, newest
GHSA-x3mx-cm49-8m9c verbatim as prior cycle). Stays out.

## Surveyor B — delta news scan (~05:55–~05:56 CDT, evidence-bounded): 0 NEW / 11 clean dedupes / 2 flagged-only

**NEW with evidence (0).** Surveyor B surfaced the Baseten × Blaxel
acquisition (announced Sep 10, 2026) as new-to-the-lane — reclassified
by the integrator: **already in corpus (C11)** — see the provenance
note. The third-party recaps (pulse2, techintelpro, techdefused,
runtimewire) are recaps of an already first-party-cited deal — below
the fold bar; noted, not folded. **No corpus change this cycle.**
C11 stays open — nothing shipped (Baseten's beri.net FAQ Sep 24: the
Blaxel platform keeps running during integration; sandbox products are
planned "beginning with its Sandboxes," not shipped). No new C-number.

**Clean dedupes (pre-window, re-queried — 11, header count agrees):**
Modal $15B / Baseten $26B talks (C11 — talks still unclosed, no close
signal; third-party recaps of the Sep 23 Bloomberg report; bytevyte
funding tracker reiterates "Neither round has closed, and terms could
still shift" — FILE ON CLOSE stays armed); agent-O echo (twenty-first
daily cycle — leak/speculation only, zero OpenAI confirmation; DevDay
Tue Sep-29 1pm ET gate stands — only an actual OpenAI confirmation
files C68; the C68 reservation stands); Mistral Vibe 87984–88 cluster
(Sep 11 vintage — HiddenLayer advisories, SecMate SECMATE-2026-0038/39,
ghostx0x vuln-tracker 2026-09-11 daily, stackflag recaps — no new member
of THIS cluster, no first-party advisory beyond MAI-2026-003, no
demonstrated agent-infra exploitation; below the re-fold bar); Hugo
CVE-2026-100690 (aggregator-only — thehackerwire record received Sep 26
with exploit status NONE; VulnCheck/OpenCVE/cve.report entries for OTHER
Hugo CVEs; no 100690-specific GHSA; A-lane re-sweeps the advisory page
directly — stays out); Modal egress billing (third-party GitHub skill
mirror matches baseline exactly — Starter 1 TiB / Team 10 TiB /
Enterprise 100 TiB, $0.04/GiB, effective Oct 1, first bill Nov 1; no
"went live early" chatter — standing); Daytona/E2B funding (stale —
Daytona $24M Series A Feb 2026, E2B $21M Series A Jul 2025;
AlleyWatch cites $86.3M aggregate for Daytona; forge's Daytona Series B
2026-07-31 claim did not surface this pass — database-only, no company
announcement — not folded); Vercel Drives GA — no GA anywhere, still
public beta (third-party deep-dive corroborates the A-lane verdict;
P49 NOT met as of read time — never declared dead before EOD);
NanoClaw/NanoCo (recaps only — March Docker Sandboxes partnership, May
$12M seed; VentureBeat piece on NanoClaw 2.0 + NanoCo × Vercel × OneCLI
partnership for a standardized approval system — an approval/credentials
coordination play, NOT a sandbox/compute announcement — below the
re-grade bar; n0vakovic/nanoclaw README "Now Runs in Docker Sandboxes"
is an integrator, not a hosted product — no re-grade); Docker Cloud
Sandboxes Sep-24 launch + BAND × Docker Sandboxes integration (Sep 24
PR Newswire via morningstar + syndication — already in-corpus (C20);
ecosystem activity; BAND ships a Python kit/coordination layer, not a
hosted/compute product — below the fold bar); E2B sandbox news scan
(lane-quiet — no new E2B vendor launch; Encore × E2B Sep-15 blog,
FastGPT v4.16.0 E2B deprecation Sep-14, OpenAI Agents API Sep-11 — all
pre-window context).

**Flagged-only (NOT folded — numbered verdicts):**
1. **Plugin4Shell — still NO real CVE assigned.** shattered.io FAQ
   (crawled ~2h ago): "As of September 23, 2026, no CVE identifier has
   been assigned, and no official CVSS score has been published";
   securityonline.info, neuralwired, deafnews, thehackernews concur;
   pranava0x0/vibe-coding-security advisory tags it "no-cve"
   (2026-09-18). The purported "CVE-2026-92104" did NOT surface in
   this cycle's snippets at all — stays suspect, uncorroborated.
   Not foldable — keep watching.
2. **CVE-2026-67623 (Mistral Vibe <2.23.3, git fsmonitor-hook RCE, CVSS
   8.8)** — newly surfaced in this lane's snippets but
   **August-vintage** (OffSeq record added 08/05/2026) — below the
   post-93993 re-fold bar (not in-window, no first-party Mistral
   advisory beyond MAI-2026-003, no demonstrated agent-infra
   exploitation). Not folded — left to the next cycle's Mistral watch;
   the lane recommends no corpus note (recorded here as standing
   context).

**Not re-queried this cycle (carried as standing, NOT asserted as
re-verified):** OpenAI Sep 20 DNS-escape recaps, OpenAI–Hugging Face
July intrusion commentary, AI-inference funding wave. No in-window
movement was asserted for these items; the next surveyor re-checks.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (sixteenth straight quiet
  B-lane night scan, C6–C21). The Baseten × Blaxel corroboration
  upgrade is already-corpus context (C11), not an in-lane launch.
- **Corpus movement: none.** No new C-number this pass. C69 (Mistral
  Vibe CVE-2026-93993) stands as the newest corpus entry from C20.
- **P63 aging pipeline — no new age-outs this pass.** No dedicated
  aging queries run; none of the aged-out items showed in-window
  movement in this scan's snippets.
  - **C11 (Baseten/Blaxel integration watch) — stays open, nothing
    shipped.** Surveyor B recommended a corpus fold for the acquisition;
    the corpus-grep gate rejected it — the Sep-10 acquisition is already
    filed (C11 watch, vendor row, and the sources list has cited
    Baseten's own Business Wire announcement since the filing). This
    cycle's recaps (pulse2, techintelpro, techdefused, runtimewire) are
    third-party recaps of an already first-party-cited deal — noted,
    not folded; no corpus change. Blaxel's sandbox repo: no releases
    after v0.2.59 (Sep 18). Baseten's beri.net FAQ (Sep 24): platform
    keeps running during integration; sandbox products planned, not
    shipped. The watch stays open until a shipped product lands.
  - Aged-out stay out: C29 (Boxd), C45, C56, C66, C67 (Huawei CodeArts
    Malaysia — re-fold path stands on real movement), C62 (OpenAI infra
    wave — aged out at C15; vendor facts retained as canonical
    reference; re-fold on real movement), Heapjack/Overpatch, GitLab
    CVE-2026-85706, Dextr AI. C26 closed.
  - C12 (AgentComputer) stays OPEN — still no first-party egress
    pricing line (21st consecutive read, no wording drift). No re-folds.
- **P49 (Vercel Drives GA): the 2026-09-28 expectation is NOT met**
  as of ~05:56 CDT. No GA entry on the first-party changelog index,
  no third-party GA chatter, sandbox docs still grade "Drives
  (beta)". The A-lane's normal Vercel reads keep re-grading the
  expectation (final day ~25% elapsed at read time); **the final
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
  effective Oct 1 (~2.75 days out)** — first-party re-confirm
  post-effective-date (no "went live early" chatter this cycle);
  **agent-O DevDay confirmation gate Tue Sep-29 1pm ET** (only an
  actual OpenAI confirmation files C68 — the C68 reservation stands);
  **Plugin4Shell** — watch for a REAL CVE assignment (treat
  "CVE-2026-92104" as suspect until CVE-db corroborated — it did not
  surface at all this cycle); **Mistral Vibe family** — re-fold on an
  additional new family member, a first-party Mistral advisory beyond
  MAI-2026-003, or demonstrated agent-infra exploitation (the
  87984–88 cluster and CVE-2026-67623 stay below bar); **Hugo
  CVE-2026-100690** — direct gohugoio/hugo/security/advisories sweep
  continues (A-lane; use the full URL — the shorthand 404s);
  **NanoClaw/NanoCo** — re-grade only on a first-party
  sandbox/compute announcement (the Vercel/OneCLI approval
  partnership does not meet it); **P49 Drives GA** — final grade
  pending EOD 2026-09-28 (re-graded by the A-lane's normal Vercel
  reads; later in-window cycles today carry it); **BAND × Docker
  Sandboxes** — ecosystem activity only, re-grade only if BAND ships
  a hosted/compute product; aged-out items (C29, C45, C56, C66, C67,
  C62, Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI)
  resurface only on real movement.
- **Process (next slot's brief):** the standing review gate held this
  pass — neither surveyor wrote prospective completion labels
  (surveyor A's 05:56:24 mtime is stat-certified; B's header counts
  agree with the integrated verdict after the integrator's fold-hygiene
  correction). New lesson: surveyor B recommended a corpus fold for an
  already-corpus item (Baseten × Blaxel, C11) — the integrator's
  corpus grep is the gate for every fold recommendation; "new to the
  lane" ≠ new to the corpus. Keep the gate: treat each capture file's
  mtime as completion evidence, reject any claimed time later than the
  mtime, count surveyor-B dedupes from the enumeration when the header
  count disagrees, never declare an expectation dead before its window
  closes, and grep the corpus for the fold candidate before minting.
  Caught this cycle by adversarial review: the integrator's own
  first draft fabricated a "corroboration upgrade" — claiming the
  first-party Business Wire citation was newly added this cycle when
  corpus grep shows it was cited since the filing. The reclassification
  (surveyor's fold recommendation rejected) was right; the replacement
  contribution was invented. When a surveyor recommendation is
  rejected, the replacement claim must be verified the same way the
  recommendation was — the corrected note above names the rejection
  path honestly (clean dedupe, no corpus change).
