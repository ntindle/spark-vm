# Competitor watch — 2026-09-28 (late night, cycle 12)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads ~00:45–~00:56 CDT 2026-09-28) against the
cycle-11 (~23:56–~00:11 CDT 2026-09-27/28) baseline — **8/8
VENDOR-VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 19/19 first-try** (zero
fetch failures; the all-first-try streak extends to thirteen straight
zero-fetch-failure passes). Surveyor B: delta news scan over
~01:00–~01:20 CDT (~20-min window, 12 queries, snippet level, zero
pages opened) — **quiet pass, 0 NEW with evidence, ~90 clean dedupes,
10 flagged-only, 0 new C-numbers**.

Delta-only against the cycle-11 late-night pass
(`docs/COMPETITOR_WATCH_2026-09-27_LATE_NIGHT_C11.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260928-0024.md`,
`agent_notes/surveyor-b-20260928-0024.md` (under `hidden_files`).

> **Timestamp provenance note:** every verification-time claim in this
> doc is bounded by the surveyors' actual completion times (A: reads
> ~00:45–~00:56 CDT, completion 00:57 CDT; B: scan window
> ~01:00–~01:20 CDT, completion 01:20 CDT) — no claimed read post-dates
> its record.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~00:45–~00:56 CDT)

**8/8 VERIFIED NO-CHANGE, 0 VERIFIED DELTA, 19/19 first-try.** A fully
quiet A-lane pass — zero deltas for the first time since the
nightly series began.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); no V0.219+. Second entry still SEP 25 / V0.217.0.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22** ("Improved sandbox moves and support for
   private kit images in cloud sandboxes"); 2026-09-21 v3-kits entry
   verbatim unchanged below it.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**
   (Full Changelog v0.7.2…v0.7.3 at top); no newer tag.
4. **Vercel changelog + Sandbox docs — VERIFIED NO-CHANGE.** Index
   still top section **"27 September"** with the Ember-1 entry (no
   flip-flop this pass); 25 September's three entries unchanged;
   **23 September "Drives for Vercel Sandbox are now in public beta"
   unchanged — no GA entry anywhere on the index.** The Ember-1
   standalone page renders live and is consistent with the index
   (still AI-Gateway lane, never Sandbox lane, never folded). **The
   P49 2026-09-28 Drives GA expectation has NOT landed as of ~00:47
   CDT:** the sandbox docs Features list grades "Drives (beta)"
   (~00:55) — a related-page link says "Private Beta" while the
   changelog index says "public beta" (pre-existing lane wording
   drift, not a GA signal).
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical ($0.044/vCPU-hour actual CPU consumed; $0.0095/GB-hour
   memory peak; shapes XSmall `mars-1vcpu-1gb` $0.0535/hr … XLarge
   `mars-16vcpu-32gb` $1.008/hr; session storage / snapshots+checkpoints /
   BYOT $0.05/GiB-month; public egress $0.01/GiB). Footnote verbatim:
   "Active CPU billing is coming soon. Until then, you will be billed at
   25% of the vCPUs allocated to your sandbox. Paused sessions incur no
   compute charges." The "Last verified 22 Sep 2026" stamp IS present
   this read.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~3 days out): timeline section
   verbatim (Sep 1: usage visible, no charges; Oct 1: charging begins;
   first bill Nov 1, 2026). Allowances verbatim: Starter **1 TiB** /
   Team **10 TiB** / Enterprise **100 TiB**; overage **$0.04 per GiB**.
   Main pricing page spot-check unchanged (Starter $0 + compute with
   $30/mo free compute; Team $250 + compute; sandbox rates
   $0.00003942/core/sec, $0.00000667/GiB/sec — consistent with corpus).
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical: E2B (Hobby FREE + $100 one-time
   credit; Pro $150/mo; per-second table tops at $0.000014/s), boat.dev
   (small $0.018 / default $0.036 / large $0.072 / xlarge $0.200 per
   sandbox-hour; "A stopped sandbox costs nothing"), TermSquad (Starter
   $9 / Builder $19 / Power $29 / Ultra $49), AgentComputer
   ($0.07/CPU-hour; $0.04375/GB-hour memory; hot $0.000683/GB-hour
   running; cold $0.000027/GB-hour stopped). AgentComputer still
   publishes **no first-party egress pricing line — C12 stays OPEN**
   (carries into C13).
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage natively
   (title "boat: Cheapest, Most Powerful Sandboxes for Agents") — no
   redirect; `ycombinator.com/companies/ascii` renders the
   Boat-branded listing natively ("Boat: The best cloud VMs for
   billions of agents | Y Combinator");
   `ycombinator.com/companies/boat` resolves separately to identical
   content. No 301s anywhere. Migration-complete state holds; no
   ASCII-retirement signals. Watch item carried: ASCII-domain retirement
   or a redirect flip-flop.

Standing bar (first-party advisory sweep, cycle-12 check): **Hugo**
— no 100690-specific GHSA on gohugoio/security/advisories (listing
shows 10 advisories, newest published Sep 9, 2026: GHSA-x3mx-cm49-8m9c,
GHSA-q4xf-287f-98r8, GHSA-797m-7j5g-3rpr, GHSA-pmrv-x7gp-2rjw,
GHSA-pq74-mj4h-cjq2 ("XSS via text/org content files" — counted but
unnamed in the C11 capture, named here for record accuracy) — all
Moderate; Aug 27 pair; Jun 18 trio). Stays out.

Overall: **8/8 NO-CHANGE, 0 DELTA, 19/19 first-try** — the
all-first-try streak extends (zero fetch failures this pass). Note: the
19th fetch was the Vercel Ember-1 page for index-vs-page consistency
(live, consistent, still AI-Gateway lane) — kept in the cycle routine
after the C8–C11 flip-flop.

## Surveyor B — delta news scan (~01:00–~01:20 CDT): 0 NEW / ~90 clean dedupes / 10 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Modal $15B / Baseten
$26B talks (C11 — 10 sources, all Sep 23–26 content; talks still
unclosed; newest color unchanged: techflier Sep 26 — Modal Sandboxes
product + $300M annualized revenue by April); OpenAI DNS-escape /
training pause (C62 — 7 sources; neoteo/tech-insider/shattered.io/
lapaasvoice/ianslive/intelligibberish + thejoai updated ~5h ago; no new
OpenAI first-party development, pause still in effect); Huawei CodeArts
Malaysia (C67 — 7 sources; Sep-27 pocketnews republication recrawled
<1h; huawei.com first-party page recrawled 3h, content Sep 18 — no new
publication since the piece counted at C11); agent-O echo (12th cycle —
6 sources, all third-party rumor/leak; zero OpenAI confirmation);
Plugin4Shell (7 sources — patch scoreboard unchanged; note the
fabricated CVE-2026-92104 claim below, flagged not folded); Mistral
Vibe family (9 sources — unchanged at 87983–87988; SecMate CVE-overlap
table is third-party detail); Hugo CVE-2026-100690 (8 sources —
thehackerwire aggregator recrawl <1h, same Sep-26 14:16 record;
pre-window); Modal egress billing Oct-1 (7 sources — tech-insider piece
updated 1d restates the Oct-1 table verbatim; no allowance surprises);
Vercel Drives GA (7 sources — no GA announcement; gustavlrsn doc (crawl
3d) still says beta; DEV piece published 5h ago covers Vercel Sandbox
GA, not Drives GA; runtimewire Jun-7 claim recrawled, still caveated
unverified X-post); E2B js-sdk 2.51.0 recrawl (routine); Daytona
release wave (6 sources — "Guava Launches Daytona" voice-model
bizwire = NAME COLLISION NOISE, not daytona.io); NanoClaw/NanoCo (7
sources — nanocoai 2.4.0 release notes Sep-23, pre-window).

**Flagged-only (NOT folded — numbered verdicts):**
1. **C62: in-window third-party color** (thejoai piece updated ~5h
   ago + neoteo/tech-insider/shattered.io/lapaasvoice/ianslive/
   intelligibberish, all ~1d). Publications genuinely new in-window →
   **contact, quiet → 0/3** per P63 (content/publication freshness,
   not recrawl freshness). Third-party color never folds.
2. **"Agent O" echo — twelfth daily cycle, still UNCONFIRMED** (Medium
   "Exclusive Leak" Sep 27, testingcatalog Sep 26, runtimewire Sep
   26, wccftech Sep 26, YouTube leak videos, pasqualepillitteri.it
   FAQ updated 2d). Zero OpenAI first-party confirmation in any
   snippet. Not C68-candidate; DevDay Tue Sep-29 1pm ET gate stands.
3. **sh3llc0d3.com claims Plugin4Shell is "tracked as
   CVE-2026-92104" — appears FABRICATED.** An exact-match search for
   CVE-2026-92104 returns zero CVE-db/NVD hits; shattered.io FAQ
   (Sep 23, citing Air Security) and neuralcoretech both state NO CVE
   assigned as of publication. **Do NOT count it as an assigned CVE.**
   Re-fold bar unchanged (assigned CVE, demonstrated exploitation, or
   first-party vendor response). Watch for a real CVE assignment.
4. **"ChatGPT Pro Max $500/mo, powered by Cerebras WSE" rumor**
   (wccftech/testingcatalog, Sep 24) — third-party only, no fold.
5. **"Managed Agents" DevDay platform rumor** (cryptobriefing, 20 days
   old) — third-party only, no fold.
6. **SecMate's own Mistral Vibe CVE-overlap table + public
   attack-demo PoC repo** — new third-party detail on the same
   Sep-11 family (87983–87988); no new member, no first-party
   Mistral advisory beyond MAI-2026-003, no demonstrated
   agent-infra exploitation. No re-fold trigger.
7. **Hugo CVE-2026-100690 aggregator-only** (thehackerwire; VulnCheck
   advisories for older fixed versions) — third-party only, no
   gohugoio GHSA. Flagged-only, stays out.
8. **Vercel Sandbox Drives: still beta in third-party docs; GA
   expected 2026-09-28 (today)** — no chatter yet; prime watch for
   the next pass.
9. **E2B js-sdk 2.51.0 (`secure` deprecated; v2 endpoints)** —
   security-relevant default change, routine vendor release, no fold.
10. **NanoClaw 2.4.0 release notes (pre-window) + venturebeat Slack
    recrawl** — no sandbox/compute first-party announcement, no
    fold.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (seventh straight quiet
  B-lane night scan, C6–C12).
- **P63 aging pipeline — no age-outs this pass.** Contact clocks:
  **C11 → quiet 2/3** (fresh crawls of stale Sep-23–26 talks-wave
  content only — no qualifying contact; one more quiet pass fires
  the threshold); **C62 → 0/3** (in-window third-party publications,
  genuinely new content); **C67 → quiet 2/3** (no new publication
  since the Sep-27 republication last counted as contact at C10 —
  recrawls don't re-count per the ratified content-freshness rule;
  C11's 1/3 carried forward).
  Aged-out stay out: C29 (Boxd), C45 (Docker Cloud Sandboxes
  CVE-family watch — only search-driven recrawls this pass, no fresh
  CVE/launch, per the C9 rule it does not resurface), C56, C66,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI. C26 closed.
  C12 (AgentComputer) stays OPEN — still no first-party egress
  pricing line. No re-folds.
- **Ember-1 index status: STABLE re-listed.** No flip-flop this pass —
  the "27 September" index section carries the entry and the page
  renders live. Still an AI-Gateway model-availability note (never
  Sandbox lane, never folded) — no corpus entry, no further
  follow-up needed.
- Watch-outs for the next surveyor: **Vercel Sandbox Drives GA
  expected 2026-09-28 (today)** — A-lane P49 owns the first-party
  re-grade on the changelog + sandbox docs, B-lane sweeps
  third-party chatter; OpenAI DevDay (Tue Sep-29, 1pm ET SF) is the
  agent-O confirmation gate (twelfth daily cycle; only an actual
  OpenAI confirmation files C68); **Modal egress billing effective
  Oct 1 (~3 days out)** — first-party re-confirm post-effective-date;
  **C12 (AgentComputer)** — still no egress line; the C13 pass is the
  13th consecutive first-party read, so note any wording drift;
  **Plugin4Shell** — watch for a REAL CVE assignment (treat
  sh3llc0d3's CVE-2026-92104 as suspect until CVE-db corroborated);
  **C11 → 2/3** after this pass's stale-content-only contact (file
  on CLOSE regardless of clock state);
  Modal $15B / Baseten $26B — still talks, file on close; Boat legacy
  domains — watch for ASCII-domain retirement or redirect flip-flop;
  Mistral Vibe family — re-fold on a new family member, a first-party
  Mistral advisory, or demonstrated agent-infra exploitation
  (Plugin4Shell stays flagged-only on the same bar — still no CVE);
  Hugo CVE-2026-100690 — direct gohugoio/security/advisories sweep
  continues (A-lane, none found); FastGPT E2B fallout — still no
  fallout content surfaced; NanoClaw/NanoCo — re-grade only on a
  sandbox/compute first-party announcement.

No new corpus entries; no corpus field-table changes. 0 new C-numbers.
