# Competitor watch — 2026-09-28 (afternoon, cycle 26)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, mtime-bounded to 16:57:40 CDT stat-certified) against the
cycle-25 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (16 first-try
fetch successes, 0 failures; no searches needed — every URL carried
verbatim from the baseline capture chain). Surveyor B: delta news scan
(evidence-bounded; snippet level, zero pages opened, mtime-bounded to
16:57:51 CDT stat-certified) — **0 NEW with evidence, 11 clean dedupes,
7 flagged-only** (twenty-first straight quiet B-lane scan, C6–C26).

Delta-only against the cycle-25 afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-28_AFTERNOON_C25.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-1654.md`,
`hidden_files/agent_notes/surveyor-b-20260928-1654.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** both surveyors wrote captures with NO
> per-read times in the body this cycle — the standing rule held
> cleanly, with no postdating claims to reject. All verdicts below are
> mtime-bounded: A-lane to 16:57:40 CDT, B-lane to 16:57:51 CDT
> (stat-certified by the integrator).
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items. Surveyor B's header (0 NEW / 9 dedupes /
> 6 flagged-only) agrees with its enumerations (three CANDIDATEs sit
> under "NEW with evidence" as integrator-decision items, not as
> evidence-backed new corpus entries — zero corpus movement resulted).
> The doc below carries 11 clean dedupes / 7 flagged-only: the
> capture's 9 + 6 plus the three resolved CANDIDATEs (Carbon and Crusoe
> → dedupes, Boxd → flagged-only as recirculation), each disclosed at
> its item.
>
> **Coverage disclosure:** surveyor B's capture claims "all 13 carried
> watch-outs were re-scanned" and "not re-queried: none", but four items
> have no enumerated entry in its capture: BAND, and cycle-25's three
> deferred items (OpenAI DNS-escape recaps, OpenAI–Hugging Face
> intrusion commentary, AI-inference funding wave). All four are carried
> below as not-re-queried per precedent — standing, NOT asserted as
> re-verified. (A prior draft of this doc also mis-carried Daytona/E2B
> funding and NanoClaw as not-re-queried although the capture
> enumerated re-scans of both — Product's review caught it; they are
> carried as clean dedupes. The standing note below now covers both
> defect classes: verify enumerated entries before carrying a coverage
> claim, and never reclassify an enumerated item without disclosing
> the change.)
>
> **Integrator fold-gate:** three B-lane CANDIDATEs went through the
> corpus grep. Crusoe $3.9B Series F is already in the corpus as the
> GPU-cloud exclusion — clean dedupe at the gate. The Baseten Carbon
> private-preview blog post is the same Sep-27 first-party update the
> cycle-25 pass already carried — clean dedupe; the Carbon-GA bar is not
> tripped (still private preview). Boxd $2M pre-seed: the corpus already
> records this exact round — C29, "dropped as stale/out-of-window" from
> the Sept-24 watch update (closed 9/21) — so this cycle's snippet is
> recirculation of a known round, not new movement; no re-activation,
> and the aged-out-resurface rule is not tripped. No mint, no
> re-activation. (Correction: the integrator's first draft framed the
> Boxd item as new single-source movement with a corroboration trigger —
> Architecture's review caught that the corpus already knew the round;
> the trigger is withdrawn.)

## Surveyor A — fast-mover + pricing re-verification (first-party, mtime-bounded to 16:57:40 CDT)

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
   NO-CHANGE.** The "28 September" section still has exactly the C25
   two entries (Claude Sonnet 5.5 on AI Gateway; Sandbox memory
   observability re-list) — no Drives GA entry. Sandbox docs still
   `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
   Features list. The dedicated Drives page still says "in Private
   Beta" with an active waitlist — no GA language. **P49 IN-CYCLE
   VERDICT: NOT MET as observed** (second consecutive in-cycle
   grading). The expectation's window closes tonight; the final grade
   rides with the last in-window pass.
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
   first-party egress pricing line — C12 stays OPEN** (26th
   consecutive first-party read, no wording drift).
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively. Migration-complete state holds.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE (render
   caveat).** The four Sep-28 Moderate advisories still top the list;
   no 100690-specific advisory. Caveat: this single-page render showed
   10 advisories — exactly the baseline's enumerated 10 (4 Sep-28 +
   5 Sep-9 + 1 Aug-27), no removed advisory evidenced — but the
   standing ≥14-total bar could not be confirmed in this render.
   Substance is clean no-change; the count bar is carried as
   unconfirmed-this-render. Next pass: verify the count or drop the
   bar to "visible list matches baseline enumeration".

## Surveyor B — delta news scan (evidence-bounded, mtime-bounded to 16:57:51 CDT): 0 NEW / 9 clean dedupes / 6 flagged-only

**NEW with evidence (0 — none).** The three B-lane CANDIDATEs resolved
at the integrator's corpus-grep gate: Crusoe $3.9B Series F at $30.9B
(already in the corpus as the GPU-cloud exclusion — data-center-scale
AI factories, not agent sandbox — carried below as an
integrator-resolved dedupe); Baseten "Carbon" private-preview blog
post (the same Sep-27 first-party update cycle-25 already carried —
NOT GA, Carbon-GA bar not tripped — carried below as an
integrator-resolved dedupe); Boxd $2M pre-seed for "full computers
for coding agents" (runtimewire: "persistent machines, live memory
forks, hardware isolation and software that can run on
customer-owned infrastructure") — **corpus recirculation, not new
movement**: the corpus already records this exact round (C29,
"dropped as stale/out-of-window" from the Sept-24 watch update,
closed 9/21). **Verdict: not folded** — flagged below as
recirculation; the aged-out-resurface rule requires real movement,
which this is not.

**Clean dedupes (11, header count agrees):** the capture's nine, in
the capture's order, plus two integrator-resolved from B's
CANDIDATEs (items 10–11 — disclosed here, not in the capture's dedupe
enumeration):
1. Modal $15B / Baseten $26B talks — still "in talks", no close.
   Evidence: bytevyte "Neither round has closed, and terms could
   still shift before either deal signs"; runtimewire "have not
   produced completed rounds". Watch-out 1 still untriggered.
2. Baseten × Blaxel sandbox product — planned, not shipped. Evidence
   (beri.net): "Over time, Baseten will add new products based on
   Blaxel's primitives, starting with Sandboxes." No timeline, no
   shipped product. Stays deduped at the C11 gate.
3. Modal egress billing — still "Starting October 1, 2026" per the
   egress-billing docs snippet ("Modal charges for network egress
   ... $0.04 per GiB", allowances 1/10/100 TiB). No "went live early"
   chatter found.
4. Plugin4Shell — still no CVE. Evidence: shattered.io "No. As of
   September 23, 2026, no CVE identifier has been assigned";
   neuralcoretech "AIR's disclosure is explicit that no CVE has been
   assigned". The sh3llc0d3.com page still asserts CVE-2026-92104 —
   fringe claim, NOT cited as assigned.
5. Mistral Vibe family — no new member; no first-party advisory
   beyond MAI-2026-003 (only CLI changelog maintenance). Below the
   re-fold bar.
6. NanoClaw — no first-party sandbox/compute announcement (only
   retrospective coverage of the March Docker-Sandboxes partnership
   and the Vercel approval-dialog integration — orchestration, not
   compute). Below the re-grade bar.
7. Daytona/E2B — no new rounds. Stale lines reconfirmed: Daytona
   $24M Series A (Feb-2026), E2B $21M (Jul-2025). No fresh raise
   surfaced.
8. Vercel Drives — still public beta, no GA. Evidence
   (nandann.com): "Vercel announced the public beta for Sandbox
   Drives on 23 September 2026". No third-party GA claim found; the
   June runtimewire "persistence GA" framing predates this beta and
   remains the known self-flagged-verification piece.
9. Hugo GHSA sweep — no new advisory surfaced. Newest visible items
   are the known TailwindCSS follow-up thread and older CVEs
   (CVE-2026-44301, CVE-2026-35166); nothing newer than the folded
   baseline.
10. Baseten "Carbon" private preview (integrator-resolved from B's
    CANDIDATE-adjacent) — the same Sep-27 first-party baseten.co
    blog update cycle-25 already carried; explicitly private
    preview, NOT GA — Carbon-GA bar not tripped.
11. Crusoe $3.9B Series F at $30.9B (integrator-resolved from B's
    CANDIDATE) — already in the corpus as the GPU-cloud exclusion;
    data-center-scale AI factories, not agent sandbox.

**Flagged-only (NOT folded — numbered verdicts):**
1. **Modal round specifics sharpened, watch-out 1 NOT tripped.**
   TechCrunch (Sep 28) reports Modal "nearing a $750 million funding
   round led by Accel at a $15.75 billion valuation."
   "Nearing"/"closing in on" ≠ closed; no first-party confirmation,
   no definitive denial. Below the close/deny bar.
2. **Boxd $2M pre-seed — VERDICT: corpus recirculation, not filed.**
   The corpus already records this exact round (C29, "dropped as
   stale/out-of-window" from the Sept-24 watch update, closed 9/21);
   this cycle's runtimewire snippet is recirculation of the known
   round, not new movement. The aged-out-resurface rule requires real
   movement — this does not trip it.
3. **agent-O — VERDICT: below the bar.** Leak-only, twenty-sixth
   daily cycle (new Medium/blurbrahlab/pasqualepillitteri.it pieces;
   still no OpenAI confirmation). DevDay Sep-29 1pm ET gate stands;
   C68 not filed.
4. **Anthropic Claude Marketplace — VERDICT: below the bar.**
   Launched Sep 23 (2,000+ connectors/plugins, 15 buyable agents,
   partner tiers per first-party Anthropic blog; self-serve
   submission portal live Sept 25). Adjacent lane (directory/
   marketplace, MCP-based); no sandbox/compute lane change.
5. **Instinct $1B Series C at $10B (Sep 28, Reuters) — VERDICT: below
   the bar.** Consumer personal agent (concierge/bookings); "isolated
   sandboxes" mentioned only as a privacy feature. No infra entry.
6. **Hugo advisory URL GHSA-vrm6-x8vp-mv2r — VERDICT: not new.**
   Snippet carries no date and reads as the known TailwindCSS
   incomplete-fix advisory. Cannot confirm novelty; not treated as
   new.
7. **Infra-context only, below bar:** Crusoe ended its $1.25B Boom
   turbine order (baxtel); Oracle filed force-majeure on the
   Stargate/Jupiter New Mexico campus over a delayed energy pipeline
   (startupfortune). Data-center economics, not the agent-compute
   lane.

**Not re-queried this cycle (carried as standing, NOT asserted as
re-verified):** BAND × Docker Sandboxes (ecosystem activity only —
re-grade only if it ships a hosted/compute product); OpenAI Sep-20
DNS-escape recaps; OpenAI–Hugging Face July intrusion commentary;
AI-inference funding wave (the last three carried forward from
cycle-25's deferred list, which said "the next surveyor re-checks").
(Surveyor B's capture claims "all 13 carried watch-outs were
re-scanned" and "not re-queried: none", but none of these four items
has an enumerated entry in its capture — see the coverage disclosure
above. Daytona/E2B funding and NanoClaw were both re-scanned this
cycle and are carried as clean dedupes in the section above.)

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (twenty-first
  straight quiet B-lane scan, C6–C26).
- **Corpus movement (P63): none.** No new C-numbers minted, no
  age-outs. C70 (NVIDIA Open Agent Safety Platform) stands as the
  latest mint. C11 (Modal/Baseten talks) stays OPEN — talks unclosed
  (FILE ON CLOSE armed), Carbon still private preview, Baseten ×
  Blaxel integration still no shipped product. C12 (AgentComputer)
  stays OPEN — 26th consecutive no-egress-line read. Aged-out stay
  out: C29 (Boxd — the $2M pre-seed is corpus-recorded recirculation,
  not new movement), C45, C56,
  C66, C67 (Huawei CodeArts Malaysia), C62 (OpenAI infra wave),
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI. C26 closed.
- **P49 (Vercel Drives GA by 2026-09-28): NOT MET as observed** —
  second consecutive in-cycle grading; all three first-party
  surfaces (changelog index, Sandbox docs, dedicated Drives page)
  agree on beta/private-beta state. The expectation's window closes
  tonight; the final grade rides with the last in-window pass.
- Watch-outs for the next surveyor: **P49 final grade** — the last
  in-window pass confirms it; **C11 file-on-close** — the first pass
  that sees the Modal $15B / Baseten $26B talks close (or a
  definitive denial) files regardless of the clock (watch the
  "nearing $750M/Accel/$15.75B" line for a close); **C11
  integration watch** — Carbon GA or a shipped sandbox product on
  Blaxel's primitives; **Boxd** — the $2M pre-seed is corpus-recorded
  (C29, closed 9/21, dropped as stale from the Sept-24 watch update);
  re-activation needs genuinely new movement, not recirculation;
  **Modal egress billing effective Oct 1 (~2.3 days out)** —
  post-effective-date re-confirm rides the normal read; **agent-O
  DevDay confirmation gate Tue Sep-29 1pm ET** (only an actual
  OpenAI confirmation files C68); **Plugin4Shell** — watch for a REAL
  CVE assignment; **Mistral Vibe family** — re-fold only on a new
  member, a first-party advisory beyond MAI-2026-003, or demonstrated
  agent-infra exploitation; **Hugo advisories** — full-URL sweep
  continues (verify the ≥14 count next pass or drop the bar to
  "visible list matches baseline enumeration"); **NanoClaw/NanoCo**
  — re-grade only on a first-party sandbox/compute announcement;
  **BAND** — re-query next pass (not re-queried this cycle);
  aged-out items resurface only on real movement.
- **Process (next slot's brief):** the standing gates held cleanly
  this pass — both surveyors omitted per-read times from their
  captures, so no mtime rejections were needed; header counts agreed
  with enumerations on both captures. Keep the gates: capture-file
  mtime as completion evidence, reject any claimed time later than
  the mtime (including times inside the capture body), count from
  enumerations when header counts disagree, never declare an
  expectation dead before its window closes (P49 graded in-cycle as
  observed), corpus-grep before minting ("new to the lane" ≠ new to
  the corpus), verify first-party pages directly when a mirror
  stands in, verify timestamp claims against the capture file
  itself. New standing note: when a surveyor claims full watch-out
  coverage, verify each watch-out has an enumerated entry before
  carrying the claim (BAND's coverage claim was not enumerated this
  pass) — and never reclassify an enumerated item (e.g. Daytona/E2B
  funding, NanoClaw) as not-re-queried without disclosing the change.
