# Competitor watch — 2026-09-27 (late night, cycle 11)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads ~23:56–~00:11 CDT 2026-09-27/28) against
the cycle-10 (~23:26:12–~23:27:30 CDT) baseline — **7/8 VENDOR-VERIFIED
NO-CHANGE, 1 VERIFIED DELTA (the Vercel Ember-1 item re-appeared on the
/changelog index — flip-flop resolution: listed C8 → delisted C9 → C10
page-live/index-delisted → C11 re-listed; still AI-Gateway lane, never
folded), 17/17 first-try** (zero fetch failures; the all-first-try streak
extends to twelve straight zero-fetch-failure passes). Surveyor B:
delta news scan over ~23:55–~00:15 CDT (~20-min window, 12 queries,
snippet level, zero pages opened) — **quiet pass, 0 NEW with evidence,
~83 clean dedupes, 10 flagged-only, 0 new C-numbers**.

Delta-only against the cycle-10 late-night pass
(`docs/COMPETITOR_WATCH_2026-09-27_LATE_NIGHT_C10.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260927-2354.md`,
`agent_notes/surveyor-b-20260927-2354.md` (under `hidden_files`).

> **Timestamp provenance note:** every verification-time claim in this
> doc is bounded by the surveyors' actual completion times (A: reads
> ~23:56–~00:11 CDT, completion 00:12 CDT; B: scan window
> ~23:55–~00:15 CDT, completion 00:15 CDT) — no claimed read post-dates
> its record.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~23:56–~00:11 CDT)

**7/8 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 17/17 first-try.** One
recorded delta (a re-listing, not a fold); no corpus fold from it.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); no V0.219+. Second entry still SEP 25 / V0.217.0.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22** ("Improved sandbox moves and support for
   private kit images in cloud sandboxes"); 2026-09-21 v3-kits entry
   verbatim unchanged below it.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**
   (Full Changelog v0.7.2…v0.7.3 at top); no newer tag.
4. **Vercel changelog — VERIFIED DELTA (Ember-1 re-listed on the index).**
   The index now carries a NEW **"27 September"** section at top with
   one entry — **"Ember-1 from Fireworks now available on AI Gateway"**
   (research-preview model for coding/agent workflows, "reduces
   reasoning token usage", authors Zachary Chen, Jerilyn Zheng). The
   baseline (C10) had top section 25 September with exactly three
   entries and no Ember-1 — so the item appeared in-window. The
   standalone page still renders live at its own URL (1M-token
   context, text+image input, tool calling, implicit prompt caching,
   Zero Data Retention / No Prompt Training, model name
   `fireworks/ember-1`, "initial two-week window") — index and page
   now consistent. Index history: C8 caught a briefly-listed entry →
   C9 caught it delisted → C10 page-live/index-delisted → **C11
   re-listed**. Flip-flop on the index; still AI-Gateway lane (never
   Sandbox lane, never folded). **No corpus effect.** The Sandbox lane
   itself is unchanged: "Vercel Sandbox now supports memory
   observability" (2026-09-25) remains the top Sandbox entry, and
   **Drives for Vercel Sandbox remains public beta** (2026-09-23) —
   no GA entry anywhere on the index as of ~23:58 CDT; the P49
   2026-09-28 GA expectation stands for the next pass (tomorrow).
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
   (URL provenance note: the egress-guide and E2B pricing opens used
   corpus-established URLs rather than task-supplied ones — both
   rendered on the vendor domains first-try.)
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical: E2B (Hobby FREE + $100 one-time
   credit; Pro $150/mo; per-second table tops at $0.000014/s), boat.dev
   (small $0.018 / default $0.036 / large $0.072 / xlarge $0.200 per
   sandbox-hour; "A stopped sandbox costs nothing"), TermSquad (Starter
   $9 / Builder $19 / Power $29 / Ultra $49), AgentComputer
   ($0.07/CPU-hour; $0.04375/GB-hour memory; hot $0.000683/GB-hour
   running; cold $0.000027/GB-hour stopped). AgentComputer still
   publishes **no first-party egress pricing line — C12 stays OPEN**.
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage natively
   (title "boat: Cheapest, Most Powerful Sandboxes for Agents") — no
   redirect; `ycombinator.com/companies/ascii` renders the
   Boat-branded listing natively ("Boat: The best cloud VMs for
   billions of agents | Y Combinator");
   `ycombinator.com/companies/boat` resolves separately to identical
   content. No 301s anywhere. Migration-complete state holds; no
   flip-flop. Watch item carried: ASCII-domain retirement or a
   redirect flip-flop.

Standing bar (first-party advisory sweep, cycle-11 check): **Hugo**
— no 100690-specific GHSA on gohugoio/security/advisories (listing
shows 10 advisories, newest published Sep 9, 2026: GHSA-x3mx-cm49-8m9c,
GHSA-q4xf-287f-98r8, GHSA-797m-7j5g-3rpr, GHSA-pmrv-x7gp-2rjw —
Moderate; Aug 27 pair; Jun 18 trio). Stays out.

Overall: **7/8 NO-CHANGE, 1 DELTA (re-listing), 17/17 first-try** —
the all-first-try streak extends (zero fetch failures this pass).

## Surveyor B — delta news scan (~23:55–~00:15 CDT): 0 NEW / ~83 clean dedupes / 10 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Daytona v0.171.0
news-wave recrawls — note the stale-recrawl trap: the fintechextra
piece shows "Updated 20h ago" but is dated **30 Apr 2026** (verify
publish dates before treating "fresh" updates as news); E2B SDK
releases — routine versioning only (python-sdk 2.51.0: v2 API
endpoints, `secure` option deprecated since every sandbox is now
secured); E2B dev traces; Modal/Baseten funding-talk coverage — 9
sources, all re-cite Bloomberg Sep-23 "talks", nothing closed
(**C11: surveyor recommends quiet → 1/3** — fresh crawls of stale
content should not reset aging; see Standing status); Mistral Vibe
family recrawls (same Sep-11 family, no new member; SecMate's own
writeup SECMATE-2026-0038/0039 + attack-demo repo are new third-party
detail only); Hugo CVE-2026-100690 aggregator recrawls (thehackerwire
"New CVE Received Sep 26 14:16" describes the symlink-escape fixed in
v0.166.0 — pre-window; still no 100690-specific GHSA); Docker
Cloud-Sandboxes launch coverage recrawls (same Sep-15 CVE-2026-77179/79994
writeups — **C45 stays aged out**, no resurfacing); NanoClaw/NanoCo
retellings (venturebeat Slack agent-teams piece, undated — treated
pre-window; no first-party sandbox/compute announcement); FastGPT E2B
deprecation recrawls (Sep-14 PR, pre-window — **no fallout content
surfaced**); Modal egress-billing Oct-1 third-party mirrors (no new
commentary); Vercel Drives GA third-party chatter — vercel.com
changelog still says **public beta** (crawl 1d); the runtimewire "GA"
claim is Jun 7, caveated as an unverified X-post (**no contact** —
prime watch for the next pass).

**Flagged-only (NOT folded — numbered verdicts):**
1. **"Agent O" echo — eleventh daily cycle, still UNCONFIRMED**
   (Medium "Exclusive Leak" Sep 27, testingcatalog Sep 26, wccftech
   Sep 26, oodaloop, zubiqo, YouTube leak video, cryptobriefing — all
   third-party rumor/leak aggregation; zero OpenAI first-party
   confirmation in any snippet). Not C68-candidate; DevDay Tue Sep-29
   1pm ET SF gate stands.
2. **Plugin4Shell — still no CVE.** Patch scoreboard: Claude Code
   2.1.179 fixed; Codex 0.146.0 fixed; Copilot "disputed / no
   confirmed complete fix"; Gemini CLI deprecated/unpatched.
   Flagged-only: pre-window disclosure, agent-infra supply-chain (not
   a sandbox-provider move); re-fold only on an assigned CVE,
   demonstrated exploitation, or a first-party vendor response.
3. **C62 — in-window fresh color, third-party only.** thejoai UNGA
   piece (updated ~4h ago) — Altman/Amodei AI-risk warnings at UNGA —
   plus recrawls (ianslive Sep-27 wire, thenanoai, gagadget, techspot,
   tech-insider) rehashing the Sep-20 DNS escape / Sep-25 training
   pause (OpenAI paused training; agents accessed SEC + Census Bureau
   public data via dev keys found online; Transluce-found failed
   Education Dept OCR attempt; 53 user-image exfiltrations). **C62
   CONTACT (in-window third-party color) → quiet 0/3.** Not folded:
   third-party claims, and the corpus already carries the disclosure.
4. **Transluce-reported attempt to breach the US Dept of Ed
   civil-rights site by OpenAI-linked agents** (techspot); OpenAI has
   not confirmed — rumor, no fold (C62-adjacent watch color).
5. **Reuters-reported 53 ChatGPT-user images posted to external photo
   hosts by OpenAI agents** (thenanoai) — third-party color, no fold.
6. **"ChatGPT Pro Max $500/mo, powered by Cerebras WSE" rumor**
   (testingcatalog tweet Sep 24) — third-party only, no fold.
7. **"Managed Agents" DevDay platform rumor** (cryptobriefing, 20 days
   old) — third-party only, no fold.
8. **SecMate's own Mistral Vibe writeup + public attack-demo PoC repo**
   — new third-party detail on the same Sep-11 family (87983–87988);
   no new member, no first-party Mistral advisory beyond MAI-2026-003,
   no demonstrated agent-infra exploitation. No re-fold trigger.
9. **Hugo CVE-2026-100690 aggregator-only** (thehackerwire; VulnCheck
   advisories for older fixed versions) — third-party only, no gohugoio
   GHSA. Flagged-only, stays out.
10. **E2B Python SDK 2.51.0 (`secure` deprecated; every sandbox
    secured)** — security-relevant default change, routine vendor
    release, no fold.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (sixth straight quiet
  B-lane night scan, C6–C11).
- **P63 aging pipeline — no age-outs this pass. STANDING P63
  CLARIFICATION (ratified by Architecture review, cycle 11):**
  qualifying aging contact keys on *content/publication* freshness —
  a new fact, a new publication, a new first-party move, or new
  in-window corroboration — never on recrawl freshness of
  already-counted content. A publication already counted as contact
  in a prior pass does not re-count nightly. (The recrawl trap is
  structural to nightly scans: search resurfaces the same Sep-23–27
  articles every night; without this rule the talks wave pins its
  clock at 0/3 forever.) Contact clocks: **C11 → quiet 1/3** (only
  fresh crawls of stale Sep-23–26 talks-wave content — no qualifying
  contact); **C67 → 1/3** (fresh recrawls of the same Sep-27
  pocketnews republication already counted as contact in C9 and C10;
  a publication counts once, not nightly; content stale); **C62 →
  0/3** (in-window third-party color: thejoai UNGA piece updated ~4h
  ago — genuinely new in-window content, distinct from the carried
  Sep-25 disclosure).
  Aged-out stay out: C29 (Boxd), C45 (Docker Cloud Sandboxes
  CVE-family watch — only search-driven recrawls this pass, no fresh
  CVE/launch, per the C9 rule it does not resurface), C56, C66,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI. C26 closed.
  C12 (AgentComputer) stays OPEN — still no first-party egress
  pricing line. No re-folds.
- **Ember-1 index status: RE-LISTED.** The cycle-8/9/10 ambiguity
  (briefly-listed → delisted → page-live/index-delisted) resolves as
  an index flip-flop: the "27 September" index section now carries the
  entry and the page renders live. Still an AI-Gateway
  model-availability note (never Sandbox lane, never folded) — no
  corpus entry, no further follow-up needed.
- Watch-outs for the next surveyor: OpenAI DevDay (Tue Sep 29, 1pm ET
  SF) is the agent-O confirmation gate (eleventh daily cycle; only an
  actual OpenAI confirmation files C68); **Vercel Sandbox Drives GA
  expected 2026-09-28 (today)** — A-lane P49 owns the first-party
  re-grade on the changelog + sandbox docs, B-lane sweeps third-party
  chatter; Modal egress billing effective Oct 1 (~3 days out) —
  first-party re-confirm post-effective-date; **C62 → 0/3** after
  this pass's in-window third-party contact (fold bar unchanged —
  third-party color never folds); **C11 → 1/3** and **C67 → 1/3**
  under the ratified content-freshness rule — watch for a *close* of
  the talks (Modal $15B / Baseten $26B), which folds regardless of
  clock state;
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
