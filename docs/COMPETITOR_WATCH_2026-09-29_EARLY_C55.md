# Competitor watch — 2026-09-29 (early-morning, cycle 55)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
against the cycle-54 baseline — **17 VERIFIED NO-CHANGE, 0 VERIFIED
DELTA, 0 UNVERIFIED** (18 first-try browser.open successes, 0 retries,
0 failures, 0 searches; 17 enumerated items plus one standing
re-carry). Surveyor B: delta news scan (snippet level, zero pages
opened) — **0 CANDIDATES, 19 clean dedupes, 5 flagged-only**
(fiftieth straight quiet B-lane scan, C6–C55). **Fully quiet
cycle — no first-party deltas at all.** Captures:
`hidden_files/agent_notes/surveyor-a-20260929-0754.md`,
`hidden_files/agent_notes/surveyor-b-20260929-0754.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, ~07:56 CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (17
> VERIFIED NO-CHANGE, 0 DELTA, 0 UNVERIFIED) reconciles exactly with
> its enumeration (items 1, 2, 3, 4a–4c, 5, 6, 7a–7d, 8a–8d, 9 = 17,
> plus the standing re-carry (a) excluded from totals) and its fetch
> stats (18 successes, 0 retries, 0 failures). Surveyor B's header
> (0 CANDIDATES / 19 clean dedupes / 5 flagged-only) agrees with its
> 19 dedupe and 5 flagged enumerations and its 18 browser_search
> calls, 0 pages opened.
>
> **Integrator fold-gate:** no genuine first-party delta this cycle —
> **no fold**, no mints, no re-folds, no age-out movement. The A-lane
> went fully delta-free again (equally delta-free first-party passes
> in C41–C43 and C45–C55).

Delta-only against the cycle-54 early pass (PR #691's
`docs/COMPETITOR_WATCH_2026-09-29_EARLY_C54.md`). Read-only, no
logins, no writes.

## Surveyor A — first-party vendor re-verification (mtime-bounded)

**17 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still SEP 26
   2026 / V0.218.0 ("KVM sandbox parameter and CLI WorkOS
   application"); then SEP 25 2026 / V0.217.0 ("NVIDIA B300 GPU
   type"); then SEP 24 2026 / V0.216.1 ("API key organization ID and
   CLI update warning fix"); then SEP 24 2026 / V0.216.2 ("CLI login
   through WorkOS"). No V0.219+ on the page.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out 2026-09-22 ("Improved sandbox moves and support for private kit
   images in cloud sandboxes"); the 2026-09-21 v3-kits entry verbatim
   unchanged, followed by the 2026-09-15 entry.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Top release still
   v0.7.4 with its full body intact (Features #1455/#1667; Fixes
   #1653/#1456/#1666/#1668; CI #1659; Maintenance #1652 + #1665);
   v0.7.3 still second. No v0.7.5+ on the page.
4. **Vercel (changelog index, Sandbox docs, Drives page — ALL
   NO-CHANGE).**
   a. **Changelog index — VERIFIED NO-CHANGE.** The "28 September"
      section still carries the baseline's 3 entries in the same order:
      "Search domains without authentication", then "Claude Sonnet 5.5
      now available on AI Gateway", then "Vercel Sandbox now supports
      memory observability". No Drives GA entry anywhere in the
      rendered window (24, 25, 27, 28 September).
   b. **Sandbox docs — VERIFIED NO-CHANGE.** Still `last_updated:
      2026-09-22` with "Drives (beta)" verbatim in the Features list.
      Render nuance (page chrome, not a verdict change): related-page
      chrome includes a "Run untrusted code with Vercel Sandbox, now
      generally available" link — page chrome about the Sandbox product
      itself, not a tracked-field change.
   c. **Drives Private Beta changelog page — VERIFIED NO-CHANGE.**
      Title still "Drives for Vercel Sandbox in Private Beta";
      private-beta SDK/CLI; waitlist still live; no GA language.
      **Drives GA is a standing tracked item (no in-cycle grading).**
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures verbatim ($0.044/vCPU-hour, $0.0095/GB-hour, session
   storage $0.05/GiB-month, egress $0.01/GiB, snapshots
   $0.05/GiB-month); the "Last verified 22 Sep 2026" stamp unchanged.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** "Starting
   October 1, 2026, Modal charges for network egress"; Starter 1 TiB
   / Team 10 TiB / Enterprise 100 TiB; overage $0.04/GiB; first bill
   Nov 1, 2026; Volumes excluded ("Reads from and writes to Modal
   Volumes do not count as network egress"). No went-live-early
   signals. **Re-confirm post-effective-date** with first-party reads
   only.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (7a–7d).**
   a. E2B pricing — Hobby FREE ($100 one-time credit), Pro $150/mo,
      Enterprise custom; per-second rates unchanged.
   b. boat.dev pricing — tiers and sandbox limits verbatim; trial 25
      free hours.
   c. TermSquad homepage — tiers unchanged: Starter $9, Builder $19,
      Power $29, Ultra $49.
   d. AgentComputer pricing — CPU $0.07/CPU-hour, Memory
      $0.04375/GB-hour, Hot Storage $0.000683/GB-hour, Cold Storage
      $0.000027/GB-hour; still **no first-party egress pricing
      line — C12 stays OPEN (55th consecutive first-party read)**.
8. **Boat legacy domains — VERIFIED NO-CHANGE (8a–8d, canonical
   set).** `ascii.dev` and `box.ascii.dev` both serve the Boat
   homepage natively (no redirect); the two Y Combinator company pages
   both render the Boat listing natively.
9. **Hugo advisories — VERIFIED NO-CHANGE.** Top entries still the 4
   Sep-28 Moderate advisories; render capped at exactly 10; no
   "100690" anywhere. CVE-2026-100690 remains third-party-only — file
   on first-party GHSA only.

(a) **Standing re-carry, excluded from totals:** DigitalOcean limits
page — still "Last verified 21 Sep 2026" with verbatim "You can run
up to 100 sessions at once per team depending on your tier."

## Surveyor B — delta news scan (snippet level)

**0 CANDIDATES, 19 clean dedupes, 5 flagged-only** (fiftieth straight
quiet B-lane scan, C6–C55; 18 browser_search calls, 0 pages opened).

**Clean dedupes (representative):** Cloudflare's Sept-24
Containers/Sandboxes cross-tenant disk-residue disclosure — the
in-cycle third-party pieces add no new facts; already in the corpus
(filed 2026-09-25, vendor-verified), not a re-file. Modal $750M
and Baseten ~$26B still "in talks/discussing" language — below
the C11 FILE-ON-CLOSE gate. Alleged Vercel dark-web credential sale —
still UNCONFIRMED, watch-only (do-not-conflate with the April-2026
Mandiant breach, which resurfaced in results). OpenAI DevDay
pre-keynote press (the GPT-6.1 "Astra" cancellation syndication) —
keynote had not happened at survey time, C68 stays NOT filed. Docker
CVE-2026-77179/79994 — pre-window publication and fix, color only.
NanoClaw × Vercel/OneCLI — recrawl of the cycle-52 policy
partnership, still below the NanoCo re-grade bar. DigitalOcean
Managed Agents Sept-21/22 preview — already covered. Railway queries
returned only Indian-railways namesake noise. Agent-adjacent funding
out of lane.

**Flagged-only (5):**

1. **BAND × Docker Sandboxes Sept-24 integration** (PR Newswire via
   third-party syndication) — Python kit connecting sandboxed local
   agents to BAND's collaboration rooms. **Gate unmet:** integration
   announcement by a third party, not a Docker product launch/GA/
   pricing delta; recrawl of the Sept-24 BAND-kit thread already noted
   in the corpus.
2. **Modal sandbox-infrastructure engineering detail** (Sept-24
   third-party digest of a Modal staff engineering blog) — rebuild-off-
   Kubernetes write-up. **Gate unmet:** below the launch/GA bar —
   third-party digest of an engineering post, not a product
   announcement.
3. **NanoClaw × Echo security partnership** (PR Newswire, late Sept) —
   Echo rebuilds the NanoClaw runtime as hardened images; NanoCo-backed
   agent keeps agent-per-sandbox posture. **Gate unmet:** below the
   NanoCo re-grade bar — partnership, not a first-party
   sandbox/compute announcement. (Recrawl of the item flagged in the
   C44 late-night pass — same PRNewswire piece; still below the
   NanoCo re-grade bar).
4. **Prime Intellect "Prime Sandboxes"** — launch recency still
   unconfirmed. **Gate unmet:** first-party confirmation of a launch
   date required before any grading; carried watch-out stands.
5. **Prime Intellect SDK VM-only pivot** (primeintellect-ai/prime
   #891, ~Sept 18) — containers/SSH/port-exposure surface deprecated;
   VM-only. **Gate unmet:** pre-window publication; an SDK direction
   change is below every filing gate. (First observation of this thread
   in the watch corpus; not filed — no corpus entry).

## Standing-item state

- **C11 FILE ON CLOSE — armed.** Modal $750M and Baseten
  ~$26B rounds still "nearing/in talks" language.
- **C12 — OPEN (55th consecutive first-party read).** AgentComputer
  still publishes no egress pricing line.
- **C68 — NOT filed.** The OpenAI DevDay keynote (~12pm CT
  2026-09-29) had not happened at survey time; pre-keynote press is
  NEVER filed; post-keynote passes grade the actual keynote.
- **Modal egress billing — effective 2026-10-01** (2 calendar days
  after the 2026-09-29 survey). First-party re-confirm
  post-effective-date.
- **Vercel Drives GA — standing tracked item** (no in-cycle grading;
  not declared dead — first-party surfaces still show private beta).
- **NanoCo re-grade bar — unmet.** File only on a first-party
  sandbox/compute announcement.
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
- **Hugo CVE-2026-100690 — third-party-only.** File on first-party
  GHSA only.

## Watch-outs for the next slot

C68 resolution at the ~12pm CT keynote (only an actual OpenAI
confirmation files); C11 FILE ON CLOSE; Modal egress billing
effective 2026-10-01 — first-party re-confirm post-effective-date;
Drives GA as a standing tracked item; the alleged Vercel dark-web
credential sale stays watch-only (do-not-conflate with the
April-2026 breach); Hugo CVE-2026-100690 third-party-only (file on
first-party GHSA only); NanoCo first-party sandbox/compute
announcement is the re-grade bar; Prime Intellect Prime Sandboxes —
confirm launch recency before any grading; surveyor
timestamp-honesty rule in force.
