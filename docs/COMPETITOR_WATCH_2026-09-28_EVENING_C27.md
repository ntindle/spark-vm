# Competitor watch — 2026-09-28 (evening, cycle 27)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, mtime-bounded to 17:28:02 CDT stat-certified) against the
cycle-26 baseline —
**9 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED** (16 first-try
fetch successes, 0 failures; no searches needed — every URL carried
verbatim from the baseline capture chain). Surveyor B: delta news scan
(evidence-bounded; snippet level, zero pages opened, mtime-bounded to
17:27:52 CDT stat-certified) — **1 CANDIDATE resolved at the corpus
gate as an update on the already-folded C70 (no new corpus entry), 13
clean dedupes, 5 flagged-only** (twenty-second straight quiet B-lane
scan, C6–C27).

Delta-only against the cycle-26 afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-28_AFTERNOON_C26.md`). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260928-1724.md`,
`hidden_files/agent_notes/surveyor-b-20260928-1724.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** both surveyors wrote captures with NO
> per-read times in the body this cycle — the standing rule held
> cleanly, with no postdating claims to reject. All verdicts below are
> mtime-bounded: A-lane to 17:28:02 CDT, B-lane to 17:27:52 CDT
> (stat-certified by the integrator).
>
> **Count-honesty check:** surveyor A's header (9 / 0 / 0) agrees with
> its nine enumerated items. Surveyor B's header (1 NEW-candidate /
> 13 dedupes / 5 flagged-only) agrees with its enumerations — the 1
> CANDIDATE resolved at the integrator's corpus gate as an update on
> the already-folded C70 (carried below as a tracked-item update, not
> a new entry); the doc enumerates 13 clean dedupes / 5 flagged-only
> plus the C70-update line.
>
> **Coverage disclosure:** surveyor B's capture carries C25's three
> deferred items (OpenAI DNS-escape recaps, OpenAI–Hugging Face
> intrusion commentary, AI-inference funding wave) as not-re-queried
> with coverage disclosure — carried below as standing, NOT asserted
> as re-verified, per precedent. All other carried watch-outs were
> re-scanned this cycle.
>
> **Integrator fold-gate:** surveyor B's 1 CANDIDATE (NVIDIA Open Agent
> Safety Platform — OpenShell open-source sandbox now broadly
> available at v0.1.0, first-party Sept 28, corroborated across five
> outlets) went through the corpus grep. It is NOT a new fold: the
> corpus chain already holds C70 ("NVIDIA Open Agent Safety Platform
> (OpenShell + Sentry)", minted in the cycle-23 watch doc, disclosed
> as adjacent-lane safety infrastructure, not an in-lane launch).
> The new texture — OpenShell broadly available at v0.1.0 today per
> five corroborating outlets — is an update on the tracked C70 item:
> no new C-number, recorded below as a tracked-item update. Baseten's
> blog tying Carbon's snapshot/fork story to OpenShell is adjacent
> color for the C11 Carbon watch — not GA evidence; the Carbon-GA bar
> stays untripped.

## Surveyor A — fast-mover + pricing re-verification (first-party, mtime-bounded to 17:28:02 CDT)

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
   NO-CHANGE.** The "28 September" section still has exactly the C26
   two entries (Claude Sonnet 5.5 on AI Gateway; Sandbox memory
   observability) — no Drives GA entry. Sandbox docs still
   `last_updated: 2026-09-22` with "Drives (beta)" verbatim in the
   Features list. The dedicated Drives page still says "in Private
   Beta" with an active waitlist — no GA language. **P49 IN-CYCLE
   VERDICT: NOT MET as observed** (third consecutive in-cycle
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
   went-live-early signals (~2.4 days to the effective date).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical. AgentComputer still publishes **no
   first-party egress pricing line — C12 stays OPEN** (27th
   consecutive first-party read, no wording drift).
8. **Boat legacy domains — VERIFIED NO-CHANGE (4/4, canonical set:
   2 domains + 2 YC paths).** `ascii.dev` and `box.ascii.dev` both
   serve the Boat homepage natively (no redirect);
   `ycombinator.com/companies/ascii` and `/companies/boat` both render
   the Boat listing natively. Migration-complete state holds.
9. **Hugo advisories (full URL) — VERIFIED NO-CHANGE (bar retired).**
   The four Sep-28 Moderate advisories still top the list; no
   100690-specific advisory. Bar change, disclosed: the standing
   "≥14 advisories total" bar could not be confirmed in two
   consecutive single-page renders (exactly 10 shown each time — the
   baseline's enumerated 10: 4 Sep-28 + 5 Sep-9 + 1 Aug-27 — no
   removed advisory evidenced). Per the cycle-26 doc's "next pass:
   verify the count or drop the bar" authorization, the bar is retired
   and replaced with "visible list matches baseline enumeration" —
   which holds this cycle. Substance (top four + no 100690) is clean
   no-change.

## Surveyor B — delta news scan (evidence-bounded, mtime-bounded to 17:27:52 CDT): 1 candidate resolved (C70 update) / 13 clean dedupes / 5 flagged-only

**NEW with evidence (1 candidate — resolved, not folded).** Surveyor
B's CANDIDATE (NVIDIA Open Agent Safety Platform — OpenShell now
broadly available at v0.1.0, Apache 2.0, first-party Sept 28 launch,
corroborated across five outlets) resolved at the integrator's
corpus-grep gate: C70 already folded in the cycle-23 watch doc
(adjacent-lane, disclosed). No new C-number. Tracked-item update on
C70: OpenShell is now broadly available at v0.1.0 today (the C23 mint
covered the platform announcement; today's movement is the open-source
sandbox's GA). Adjacent-lane disclosure stands — safety
infrastructure, not an in-lane sandbox/compute launch; the in-lane
no-launch verdict is unchanged. Cross-lane note: Baseten's blog
("Securing the open frontier with NVIDIA OpenShell and Blaxel
sandboxes", snippet level) explicitly ties Carbon's snapshot/fork
story to OpenShell — adjacent signal for the C11 Carbon watch, not GA
evidence.

**Clean dedupes (13):**

1. **Modal/Baseten mega-rounds — still unclosed, no denial.** A Sept
   28 report has Modal "nearing" a $750M round at $15.75B — nearing is
   not closed ("The new financing has not been completed");
   valuations "under discussion, not closed rounds". C11 stays OPEN;
   FILE ON CLOSE stays armed.
2. **Baseten × Blaxel Carbon — still private preview, no GA**
   ("currently in private preview and rolling out progressively").
   C11 Carbon-GA watch NOT tripped.
3. **Modal egress billing — still "Starting October 1, 2026"**
   ($0.04/GiB, allowances 1/10/100 TiB). No went-live-early chatter.
4. **Plugin4Shell — still no real CVE assigned** ("No public
   Plugin4Shell CVE was identified ... as of September 27, 2026";
   "no CVE has been assigned"). The fringe "CVE-2026-92104" claim —
   do not cite.
5. **Mistral Vibe — no new family member, no first-party
   sandbox/compute announcement.** A CLI permission-bypass write-up
   (SECMATE-2026-0038/-0039, Vibe 2.25.4 patch Sep 12) is a CLI
   security fix, not a sandbox launch. Re-fold bar not tripped.
6. **NanoClaw — no first-party sandbox/compute announcement.**
   Retrospective coverage only. Re-grade bar not tripped.
7. **Daytona/E2B funding — no new rounds.** Daytona $24M Series A
   (Feb-2026) line stale; no fresh E2B raise.
8. **Vercel Drives — still public beta, no GA** ("Drives: beta,
   available on all plans"; public beta announced 23 Sep 2026). No
   third-party GA claim; P49 NOT-MET-in-cycle confirmed.
9. **Hugo GHSA sweep — no new advisory.** Newest visible items are
   the known follow-ups (CVE-2026-89258, CVE-2026-44301,
   CVE-2026-35166, CVE-2026-50133, CVE-2026-50134). Nothing newer
   than the folded baseline.
10. **Crusoe — still the Sept-17-announced $3.9B Series F initial
    close at $30.9B post-money.** No new movement; borderline
    lane-adjacent, corpus-fit call stands.
11. **Boxd $2M pre-seed — recirculation only.** Same mid-September
    raise, recirculation coverage; NOT new movement — no
    re-activation (stays closed per the 9/21 stale-drop).
12. **agent-O — leak-only (twenty-seventh daily cycle).**
    "no confirmation that any are coming"; "'o' remains a leak, not
    an announcement." DevDay Sep-29 1pm ET gate stands; C68 not filed.
13. **AgentComputer (C12) — no new funding/launch.** Product page
    as-is (persistent cloud computers, resource-based billing). No
    delta.

**Flagged-only (5, below bar):**

1. **Anthropic Claude Marketplace** — still the Sept-23 launch; new
   texture only ($250 free Claude Code credits for cloud sessions).
   Adjacent-lane (directory/marketplace, MCP-based); no
   sandbox/compute lane change.
2. **Instinct $1B Series C at $10B** (Sept 28, Reuters) — consumer
   personal agent; sandboxes appear only as a privacy feature. No
   infra entry.
3. **Base44 "Base Code" launch** (Sept 28) — cloud dev environment
   with agent chat, not a sandbox primitive vendor. Adjacent.
4. **Momentic "Mo" launch** (Sept 28) — scriptless QA agent for app
   testing. Agent product, not sandbox infra.
5. **Vertical agent-funding seeds** — Dextr AI $6.7M seed, AI
   Hospitality Group $7.5M seed. Domain-vertical, no infra lane
   entry.

**Not re-queried this cycle (carried as standing, not asserted
re-verified):** OpenAI Sep 20 DNS-escape recaps, OpenAI–Hugging Face
July intrusion commentary, AI-inference funding wave. No in-window
movement asserted for these items.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch
  verdict dated 2026-09-25 stands — streak extends (twenty-second
  straight quiet B-lane scan, C6–C27). The one corpus-adjacent item
  this cycle (C70 update) is adjacent-lane safety infrastructure, not
  an in-lane launch.
- **Corpus movement (P63):** no new mints, no re-folds, no new
  age-outs this cycle (no dedicated aging queries; aged-out items
  showed no in-window movement). **C11 (Modal/Baseten talks-wave) —
  still unclosed, no close signal — FILE ON CLOSE stays armed.**
  **C12 (AgentComputer) — still no first-party egress pricing line —
  stays OPEN (27th consecutive read).** Aged-out stay out (C29, C45,
  C56, C66, C67, C62 — re-fold path on real movement; Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI). C26 closed.
- **Watch-outs for the next slot:** P49's final grade rides with the
  last in-window pass tonight; Modal egress billing goes effective
  Oct 1 (~2.4 days out — first-party re-confirm post-effective-date);
  agent-O DevDay confirmation gate Tue Sep-29 1pm ET (only an actual
  OpenAI confirmation files C68); Hugo GHSA sweep (full URL —
  shorthand 404s); NanoClaw/NanoCo re-grade only on first-party
  sandbox/compute announcement; Mistral Vibe re-fold bar; Plugin4Shell
  real-CVE watch (never cite the suspect CVE-2026-92104); Boxd
  recirculation (C29 — do not re-activate on recirculation); Carbon
  private-preview (Baseten×OpenShell cross-lane note); surveyor
  timestamp-honesty rule in force (mtimes = completion evidence).
