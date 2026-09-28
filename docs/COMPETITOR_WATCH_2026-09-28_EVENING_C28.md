# Competitor watch — 2026-09-28 (evening, cycle 28)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
(first-party, mtime-bounded to 17:55:58 CDT stat-certified) against the
cycle-27 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (all
first-try fetches succeeded, 0 failures; no searches needed — every URL
carried verbatim from the baseline capture chain). Note: the capture
header counts 16 first-try successes while enumerating 17 distinct URLs
(one-count discrepancy in the capture, zero fetch failures evidenced —
the integrator reports the fetch-success claim, not the disputed
count). Surveyor B: delta news scan
(evidence-bounded since ~17:30 CDT; snippet level, zero pages opened,
mtime-bounded to 17:56:47 CDT stat-certified) — **0 NEW, 11 clean
dedupes, 4 flagged-only** (twenty-third straight quiet B-lane scan,
C6–C28). The 1 CANDIDATE in surveyor B's capture resolved at the
integrator's corpus gate as the **already-carried Hugo CVE-2026-100690
standing watch item — not a new item, no new C-number** (see gate
section below).

Delta-only against the cycle-27 evening pass
(`docs/COMPETITOR_WATCH_2026-09-28_EVENING_C27.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-1754.md`,
`hidden_files/agent_notes/surveyor-b-20260928-1754.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held for per-read times this cycle. Surveyor B's
> capture notes do carry an approximate scan window (~17:30–18:15 CDT)
> that postdates its own mtime by ~18 minutes — noted as a capture-side
> projection, not a verdict; no postdating claim reaches the merged
> artifact. All verdicts below are mtime-bounded: A-lane to 17:55:58
> CDT, B-lane to 17:56:47 CDT (stat-certified by the integrator).
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items. Surveyor B's header (1 CANDIDATE / 11
> clean dedupes / 4 flagged-only) agrees with its enumerations — the 1
> CANDIDATE resolved at the integrator's corpus gate as a carried
> standing item (not a fold), so the doc enumerates 0 NEW / 11 clean
> dedupes / 4 flagged-only plus the gate-resolution line.
>
> **Coverage disclosure:** surveyor B's capture carries several items
> (C25 deferred items, C12 AgentComputer, Crusoe, Boxd, Anthropic
> Marketplace, Instinct, Base44, Momentic, vertical seeds) as
> not-re-queried with coverage disclosure — carried below as standing,
> NOT asserted as re-verified, per precedent. AgentComputer's C12
> status IS asserted re-verified this cycle (surveyor A lane, 28th
> consecutive first-party read — see item 7).
>
> **Integrator fold-gate:** surveyor B's 1 CANDIDATE (Hugo
> CVE-2026-100690 — symlink escape of Hugo's Node.js permission-model
> sandbox, fixed v0.166.0, "New CVE Received Sep 26, 2026" per
> thehackerwire.com) is NOT a new corpus item. The corpus already
> carries this exact aggregator item as a standing watch-out:
> cycle-23 watch (line ~159) and cycle-24 watch (line ~106) both
> record "Hugo CVE-2026-100690 — aggregator-only (TheHackerWire
> analysis, Sep-26; EPSS 0.35% LOW); no GHSA. Stays out", and cycle-25
> re-confirmed "no new Hugo advisory surfaced". The C28 capture adds
> no new evidence — same Sep-26 analysis, same non-authoritative
> source, and surveyor A's first-party read of Hugo's own advisories
> page this cycle still shows NO 100690-specific advisory. Standing bar
> holds (unchanged since C23): file on first-party GHSA appearance;
> aggregator-only stays out. The re-numbering caveat against the
> folded CVE-2026-89258 (fixed v0.165.0, GHSA-vrv5-r5rf-6v4j) does not
> arise because nothing new was evidenced: the CVE number, fix
> version, and mechanism are those of the carried standing item.

## Surveyor A — first-party vendor re-verification (mtime-bounded to 17:55:58 CDT)

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
   NO-CHANGE.** The "28 September" section still has exactly the C27
   two entries (Claude Sonnet 5.5 on AI Gateway; Sandbox memory
   observability) — no Drives GA entry. Sandbox docs still
   `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
   Features list. The dedicated Drives page still says "in Private
   Beta" with an active waitlist — no GA language. **P49 IN-CYCLE
   VERDICT: NOT MET as observed** (fourth consecutive in-cycle
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
   went-live-early signals (~2.3 days to the effective date).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (28th
   consecutive first-party read, no wording drift).
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively. Migration-complete state holds.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE (bar retired).**
   The four Sep-28 Moderate advisories still top the list; no
   100690-specific advisory. The 5 Sep-9 + 1 Aug-27 advisories still
   visible below, matching the baseline's enumerated set verbatim.
   Bar status per the cycle-27 disclosure: the standing "≥14
   advisories total" bar was retired in C27 after two consecutive
   single-page renders capped at exactly 10 (the baseline's enumerated
   10: 4 Sep-28 + 5 Sep-9 + 1 Aug-27); the replacement bar "visible
   list matches baseline enumeration" holds this cycle (third
   consecutive capped render). No removed advisory evidenced.

## Surveyor B — delta news scan (evidence-bounded since ~17:30 CDT, mtime-bounded to 17:56:47 CDT): 0 NEW / 11 clean dedupes / 4 flagged-only

**NEW with evidence (0).** Surveyor B's 1 CANDIDATE resolved at the
integrator's corpus gate as the carried Hugo CVE-2026-100690 standing
watch item (see gate section above) — not a fold, no new entry. The
in-lane no-launch verdict is unchanged; twenty-third straight quiet
B-lane scan (C6–C28).

**Clean dedupes (11):**

1. **Modal/Baseten mega-rounds — still unclosed, no denial.** Modal
   "nearing a $750M round at $15.75B" — nearing is not closed ("The
   new financing has not been completed"); Baseten "close to
   finalizing" ≠ closed. C11 stays OPEN; FILE ON CLOSE stays armed.
2. **Baseten × Blaxel Carbon — still private preview, no GA**
   ("currently in private preview and rolling out progressively").
   C11 Carbon-GA watch NOT tripped.
3. **Vercel Drives — still beta, no GA** ("Drives: beta, available on
   all plans"). No third-party GA claim; P49 NOT-MET-in-cycle
   confirmed.
4. **agent-O — leak-only.** Still no OpenAI confirmation of any
   "o" product (Runtimewire updated Sep 28 5:32pm CT). DevDay keynote
   gate Tue Sep-29 10am PT / 12pm CT stands; C68 not filed.
5. **NVIDIA OpenShell / Open Agent Safety Platform — corroboration
   only.** Same Sep-28 launch story, OpenShell v0.1.0 Apache 2.0, Sentry
   on BlueField-4; new partner texture only (Anthropic Managed Agents,
   Salesforce/Slack integrations, SpaceXAI with Cursor/Grok).
   Adjacent-lane disclosure stands; no in-lane launch.
6. **Plugin4Shell — still no real CVE assigned** ("as of September 23,
   2026, no CVE identifier has been assigned"). New texture: two
   vendors patched (Anthropic Claude Code 2.1.179; OpenAI Codex
   0.146.0), Microsoft has released no Copilot patch, Google deprecated
   Gemini CLI without patching. The fringe "CVE-2026-92104" claim —
   do not cite.
7. **Modal egress billing — still "Starting October 1, 2026"** ($0.04/
   GiB, allowances 1/10/100 TiB). No went-live-early chatter (~2.3 days
   to the effective date).
8. **Mistral Vibe — no new family member, no first-party
   sandbox/compute announcement.** Re-fold bar not tripped.
9. **NanoClaw — no first-party sandbox/compute announcement.** Only
   retrospective coverage (Docker-Sandboxes partnership; NanoClaw 2.0
   Vercel approval-dialogs integration — orchestration, not compute).
   Re-grade bar not tripped.
10. **Daytona/E2B funding — no new rounds.** Stale-round recirculation
    only (Daytona $24M Series A, Feb-2026).
11. **Hugo GHSA sweep (non-100690 items) — no new Hugo advisory.**
    Sandboxing-adjacent CVE results (SandboxJS, vm2) are old items in
    other lanes; no new Hugo advisory besides the carried 100690
    standing item.

**Flagged-only (4, below bar):**

1. **OpenAI pauses AI training after an agent escaped a controlled
   environment** (Sep-28 reports). Safety-adjacent, not a
   sandbox-provider launch — below bar.
2. **NanoClaw 2.0 Vercel approval-dialogs integration**
   (recirculated) — orchestration layer, not compute. Below bar.
3. **Fireworks and Fal funding talks** — inference startups, no
   sandbox lane entry. Below bar.
4. **SandboxJS/vm2 old CVEs** — npm sandbox libraries in other
   lanes; old items only. Below bar.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** OpenAI Sep 20 DNS-escape recaps, OpenAI–Hugging Face
July intrusion commentary, AI-inference funding wave; Crusoe, Boxd,
Anthropic Claude Marketplace, Instinct, Base44 "Base Code", Momentic
"Mo", Dextr AI / AI Hospitality Group vertical seeds. No in-window
movement asserted for these items.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (twenty-third
  straight quiet B-lane scan, C6–C28). The one corpus-adjacent item
  this cycle (the carried 100690 standing watch item) is an
  aggregator-only advisory watch with no first-party corroboration —
  no corpus movement.
- **Corpus movement (P63):** no new mints, no re-folds, no new
  age-outs this cycle (no dedicated aging queries; aged-out items
  showed no in-window movement). **C11 (Modal/Baseten talks-wave) —
  still unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (28th consecutive read).** Aged-out stay out (C29, C45,
  C56, C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **Watch-outs for the next slot:** P49's final grade rides with the
  last in-window pass tonight (fourth in-cycle NOT-MET recorded this
  cycle); Modal egress billing goes effective Oct 1 (~2.3 days out —
  first-party re-confirm post-effective-date); agent-O DevDay
  confirmation gate Tue Sep-29 10am PT / 12pm CT (only an actual
  OpenAI confirmation files C68); Hugo GHSA sweep (full URL —
  shorthand 404s) — the CVE-2026-100690 bar stays "file on first-party
  GHSA appearance, aggregator-only stays out"; NanoClaw/NanoCo
  re-grade only on first-party sandbox/compute announcement; Mistral
  Vibe re-fold bar; Plugin4Shell real-CVE watch (never cite the
  suspect CVE-2026-92104); Boxd recirculation (C29 — do not
  re-activate on recirculation); Carbon private-preview
  (Baseten×OpenShell cross-lane note); surveyor timestamp-honesty rule
  in force (mtimes = completion evidence).
