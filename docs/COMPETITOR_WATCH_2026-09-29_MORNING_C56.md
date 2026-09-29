# Competitor watch — 2026-09-29 (morning, cycle 56)

**Two-surveyor pass.** Surveyor A: first-party vendor re-verification
against the cycle-55 baseline — **17 VERIFIED NO-CHANGE, 0 VERIFIED
DELTA, 0 UNVERIFIED** (19 first-try browser.open successes, 0 retries,
0 failures, 0 searches; 17 enumerated items, one standing re-carry and
one out-of-list color read excluded from totals). Surveyor B: delta
news scan (snippet level, zero pages opened) — **0 CANDIDATES, 17
clean dedupes, 1 flagged-only** (fifty-first straight quiet B-lane
scan, C6–C56). **Fully quiet cycle — no first-party deltas at all.**
Captures:
`hidden_files/agent_notes/surveyor-a-20260929-0924.md`,
`hidden_files/agent_notes/surveyor-b-20260929-0924.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, ~09:28–09:29 CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (17
> VERIFIED NO-CHANGE, 0 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 17 item enumerations and its fetch stats (19 opens = 17
> enumerated items + 1 standing re-carry + 1 out-of-list read,
> documented separately). Surveyor B's header (1 CANDIDATE / 17
> clean dedupes / 1 flagged-only) was **demoted at fold time**: its
> candidate (Prime Intellect "Prime Sandboxes" GA) resolves against
> the corpus as an already-filed, vendor-verified entry — see the
> integrator note below. Fold-time totals: 0 CANDIDATES / 18 clean
> dedupes / 1 flagged-only.
>
> **Integrator note — Prime Sandboxes was NOT a new filing.** The
> surveyor's candidate classification was checked against
> `docs/COMPETITOR_ANALYSIS.md` and demoted: **C48** ("Prime
> Intellect 'Prime Sandboxes' launch", ~2026-09-23) already carries
> the same GA language and the same pricing as the surveyor's
> evidence, and was upgraded 2026-09-25 (afternoon pass) to
> **VENDOR-VERIFIED** on three full-page vendor reads —
> primeintellect.ai/blog/sandboxes ("Today, Prime Sandboxes enter
> general availability."; ~30M sandboxes created; available to
> everyone via CLI/SDK and RL suite) and
> docs.primeintellect.ai/sandboxes/overview (CPU $0.02/vCPU-hr,
> memory $0.0125/GiB-hr, disk $0.0002/GiB-hr; valid through December
> 22, 2026; limits 1–16 vCPUs, 128 MiB–64 GiB memory, 2–128 GiB
> disk, up to 8 GPUs; 1,024 active sandboxes default). The standing
> "launch recency unconfirmed" watch-out is **retired**: recency is
> pinned — announced ~2026-09-23, vendor-verified 2026-09-25.
>
> **Integrator note — Vercel Drives standing-line correction.** The
> C55 watch doc said "first-party surfaces still show private beta".
> Surveyor A found this cycle that the private-beta changelog page
> **coexists with** a public-beta detail page
> (vercel.com/changelog/drives-for-vercel-sandbox-are-now-in-public-beta:
> "Drives for Vercel Sandbox are now available in public beta on
> Hobby, Pro, and Enterprise", iad1 pricing storage $0.05/GB-month,
> reads $0.0015/GB, writes $0.004/GB; Hobby includes 15 GB storage +
> 30 GB reads/writes per month). The public-beta announcement
> predates 2026-09-24 (absent from the rendered 24–28 September
> changelog window; corroborated by third-party coverage dating it
> 2026-09-23). The corpus row already reflects public beta, so this
> is a watch-doc correction, not a new filing: **Drives is in public
> beta since 2026-09-23; GA remains the standing tracked item, not
> declared dead.** The item-4c page (the private-beta page itself)
> is unchanged.
>
> **Integrator note — severitydaily.com link-check exclusion
> removed.** The 0854-slot exclusion (host-side TLS outage
> 2026-09-29 ~08:2x–~09:0x CDT) is reverted in this pass: the
> flagged Docker CVE-2026-77179 article page was re-opened by the
> integrator 2026-09-29 ~09:30 CDT and renders its full content
> (the macOS virtio-fs host-escape write-up), matching the citation
> in `docs/archive/competitor-watch/COMPETITOR_WATCH_2026-09-19_MIDDAY.md`.
> The exclusion and its evidence comment are removed from
> `.github/workflows/ci.yml`; the link is checked again like any
> other. A re-outage would re-grade per the itbrief.asia precedent.

Delta-only against the cycle-55 morning pass (PR #693's
`docs/COMPETITOR_WATCH_2026-09-29_EARLY_C55.md`). Read-only, no
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
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still
   tops out 2026-09-22 ("Improved sandbox moves and support for
   private kit images in cloud sandboxes"); the 2026-09-21 v3-kits
   entry verbatim unchanged, followed by the 2026-09-15 entry.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Top release still
   v0.7.4 with its full body intact (Features #1455/#1667; Fixes
   #1653/#1456/#1666/#1668; CI #1659; Maintenance #1652 + #1665);
   v0.7.3 still second. No v0.7.5+ on the page.
4. **Vercel — ALL NO-CHANGE.**
   a. **Changelog index — VERIFIED NO-CHANGE.** The "28 September"
      section still carries the baseline's 3 entries in the same
      order: "Search domains without authentication" first, then
      "Claude Sonnet 5.5 now available on AI Gateway", then "Vercel
      Sandbox now supports memory observability". No Drives GA entry
      anywhere in the rendered window (24, 25, 27, 28 September; 26
      September has no entries).
   b. **Sandbox docs — VERIFIED NO-CHANGE.** Still `last_updated:
      2026-09-22` with "Drives (beta)" verbatim in the Features
      list. Related-link chrome carries the "Run untrusted code with
      Vercel Sandbox, now generally available" link (page chrome
      about the Sandbox product itself, same render as C55 — not a
      tracked-field change).
   c. **Drives Private Beta changelog page — VERIFIED NO-CHANGE.**
      Title still "Drives for Vercel Sandbox in Private Beta";
      beta install lines (`@vercel/sandbox@beta`, `sandbox@beta`);
      waitlist sign-up live; no GA language. Reached via the
      sandbox-docs related link (canonical slug
      `drives-for-vercel-sandbox-in-private-beta`). **See the
      integrator note above: this private-beta page coexists with
      a public-beta detail page; Drives is in public beta since
      2026-09-23 — GA remains the standing tracked item.**
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures verbatim ($0.044/vCPU-hour, $0.0095/GB-hour, session
   storage $0.05/GiB-month, egress $0.01/GiB, snapshots
   $0.05/GiB-month); the "Last verified 22 Sep 2026" stamp
   unchanged.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** "Starting
   October 1, 2026, Modal charges for network egress"; Starter 1 TiB
   / Team 10 TiB / Enterprise 100 TiB per billing cycle; overage
   $0.04/GiB; first bill including egress arrives November 1, 2026;
   Volumes excluded ("Reads from and writes to Modal Volumes do not
   count as network egress"). No went-live-early signals.
   **Re-confirm post-effective-date** with first-party reads only
   (effective 2026-10-01, 2 calendar days after the 2026-09-29
   survey).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (7a–7d).**
   a. E2B pricing — Hobby FREE ($100 one-time usage credit), Pro
      $150/month, Enterprise custom; 1 vCPU $0.000014/s, default 2
      vCPU $0.000028/s.
   b. boat.dev pricing — `small` $0.018 / `default` $0.036 /
      `large` $0.072 / `xlarge` $0.200 per hour; plans $20/mo → 100,
      $100/mo → 300, $500/mo → 1,000, $2000/mo → 2,000 sandboxes at
      once; trial 25 free hours; all verbatim unchanged.
   c. TermSquad homepage — tiers unchanged: Starter $9/month,
      Builder $19/month, Power $29/month, Ultra $49/month.
   d. AgentComputer pricing — CPU $0.07/CPU-hour, Memory
      $0.04375/GB-hour, Hot Storage $0.000683/GB-hour (running),
      Cold Storage $0.000027/GB-hour (stopped); still **no
      first-party egress pricing line — C12 stays OPEN (56th
      consecutive first-party read)**.
8. **Boat legacy domains — VERIFIED NO-CHANGE (8a–8d, canonical
   set).** `ascii.dev` and `box.ascii.dev` both serve the Boat
   homepage natively (no redirect); the two Y Combinator company
   pages both render the Boat listing natively.
9. **Hugo advisories — VERIFIED NO-CHANGE.** Top entries still the 4
   Sep-28 Moderate advisories in baseline order; render capped at
   exactly 10; no "100690" anywhere. CVE-2026-100690 remains
   third-party-only — file on first-party GHSA only.

(a) **Standing re-carry, excluded from totals:** DigitalOcean
limits page — still "Last verified 21 Sep 2026" with verbatim
"You can run up to 100 sessions at once per team depending on your
tier."

## Surveyor B — delta news scan (snippet level)

**0 CANDIDATES, 18 clean dedupes, 1 flagged-only** (fifty-first
straight quiet B-lane scan, C6–C56; 18 browser_search calls, 0
pages opened). The surveyor's single candidate (Prime Sandboxes
GA) was demoted at fold time — already filed and vendor-verified
as C48 (see integrator note above); it counts as dedupe item 1
below.

**Clean dedupes (representative):** Prime Sandboxes GA — already
filed and vendor-verified (C48; see above), not a re-file; Daytona
$24M Series A (2026-09-02, pre-window) and OpenHands middleware
syndication (pre-window); Docker Cloud Sandboxes Sept-24 launch +
syndication (recrawl, pre-window); Docker CVE-2026-77179/79994
(pre-window publication and fix, color only); Microsandbox (no
release beyond v0.7.4); Vercel Drives public beta (announced
2026-09-23 — see the integrator correction above; GA gate unmet)
plus $1M sandbox-challenge kernel-flaw coverage (pre-window,
below bar); DigitalOcean Managed Agents Sept-21/22 preview
recrawls (already covered); Modal $750M/@$15.75B and Baseten
~$26B still "nearing"/"closing in on" language — below the C11
FILE-ON-CLOSE gate; E2B third-party color only (no first-party
delta); boat.dev and AgentComputer (no new first-party news; C12
standing); TermSquad Sept-15 launch (pre-window); Fly Sprites
(pre-window); Railway namesake noise; Hyperbolic pre-window;
Cloudflare Sept-24 disk-residue disclosure recrawls (no new
facts — already filed 2026-09-25, vendor-verified); NanoClaw
partnerships (Docker integration, Vercel/OneCLI approval dialogs,
Echo — all below the NanoCo re-grade bar); OpenAI DevDay
pre-keynote press (GPT-6.1 "Astra" cancellation syndication, "o"
always-on-agent leak pieces, what-to-watch guides) — keynote had
not happened at survey time; C68 stays NOT filed, never-file
pre-keynote.

**Flagged-only (1):**

1. **NanoCo $12M seed round for NanoClaw** (third-party repost;
   "rejects $20M acquisition offer"; backers listed include Valley
   Capital Partners, Docker, Vercel, Monday.com, Slow Ventures).
   **Gate unmet:** funding, not a first-party sandbox/compute
   announcement — the NanoCo re-grade bar stays unmet.
   Undated third-party repost; novelty unconfirmed — do not
   conflate with a product launch.

## Standing-item state

- **C11 FILE ON CLOSE — armed.** Modal $750M and Baseten
  ~$26B rounds still "nearing"/"closing in on" language.
- **C12 — OPEN (56th consecutive first-party read).** AgentComputer
  still publishes no egress pricing line.
- **C68 — NOT filed.** The OpenAI DevDay keynote (~12pm CT
  2026-09-29) had not happened at survey time; pre-keynote press is
  NEVER filed; post-keynote passes grade the actual keynote.
- **Modal egress billing — effective 2026-10-01** (2 calendar days
  after the 2026-09-29 survey). First-party re-confirm
  post-effective-date.
- **Vercel Drives GA — standing tracked item** (public beta since
  2026-09-23; no GA language on any first-party page read this
  cycle; not declared dead).
- **Prime Sandboxes — FILED (C48, vendor-verified 2026-09-25
  afternoon).** GA + launch pricing (valid through December 22,
  2026) on vendor surfaces. The "confirm launch recency"
  watch-out is retired.
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
announcement is the re-grade bar; the C68 post-keynote pass grades
the actual keynote, not the pre-keynote speculation; surveyor
timestamp-honesty rule in force.
