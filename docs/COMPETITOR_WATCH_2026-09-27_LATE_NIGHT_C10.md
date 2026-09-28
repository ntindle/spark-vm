# Competitor watch — 2026-09-27 (late night, cycle 10)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads ~23:26:12–~23:27:30 CDT 2026-09-27) against
the cycle-9 (~22:58:00–~22:58:35 CDT) baseline — **7/8 VENDOR-VERIFIED
NO-CHANGE, 1 VERIFIED DELTA (the cycle-9 retraction ambiguity is
resolved: the "Ember-1 from Fireworks on AI Gateway" page renders live
at its own URL but is delisted from the /changelog index — cycle 8
likely caught a briefly-listed index entry; Sandbox lane unchanged),
17/17 first-try** (zero fetch failures; the all-first-try streak
extends to eleven straight zero-fetch-failure passes). Surveyor B:
delta news scan over ~23:25–~23:40 CDT (~15-min window, 12 queries,
snippet level, zero pages opened) — **quiet pass, 0 NEW with evidence,
~13 clean dedupes, 8 flagged-only, 0 new C-numbers**.

Delta-only against the cycle-9 late-night pass
(`docs/COMPETITOR_WATCH_2026-09-27_LATE_NIGHT_C9.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260927-2324.md`,
`agent_notes/surveyor-b-20260927-2324.md` (under `hidden_files`).

> **Timestamp provenance note:** every verification-time claim in this
> doc is bounded by the surveyors' actual completion times (A: reads
> ~23:26:12–~23:27:30 CDT, completion 23:27:30 CDT; B: scan window
> ~23:25–~23:40 CDT, completion 23:40 CDT) — no claimed read post-dates
> its record.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~23:26:12–~23:27:30 CDT)

**7/8 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 17/17 first-try.** One
recorded delta (a resolution, not a fold); no corpus fold from it.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); no V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22** ("Improved sandbox moves and support for
   private kit images in cloud sandboxes"); v3 kits (2026-09-21)
   unchanged below it.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**
   (no v0.7.4 tag).
4. **Vercel changelog — VERIFIED DELTA (resolution of the cycle-9
   retraction ambiguity).** The "Ember-1 from Fireworks now available
   on AI Gateway" (2026-09-27) page **renders live at its own URL**
   (`vercel.com/changelog/ember-1-from-fireworks-now-available-on-ai-gateway`)
   but is **delisted from the /changelog index**: two consecutive
   index fetches show no Ember entry (a find for "Ember" matches only
   "September"). The most consistent reading is that the cycle-8
   baseline caught a briefly-listed index entry and cycle 9 caught it
   after delisting — a withdrawn-or-render-artifact ambiguity, not a
   vendor announcement lifecycle. No corpus effect: the Ember-1 item
   was and is an AI-Gateway model-availability note (never Sandbox
   lane, never folded). The Sandbox lane itself is unchanged: "Vercel
   Sandbox now supports memory observability" (2026-09-25) is the
   index's top entry, and **Drives for Vercel Sandbox remains public
   beta** (2026-09-23) — no GA this pass; the P49 2026-09-28 GA
   expectation stands for the next pass (tomorrow).
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical ($0.044/vCPU-hour active CPU — footnote:
   active-CPU billing still "coming soon", billed at 25% of allocated
   vCPUs until then; $0.0095/GB-hour memory; shapes XSmall $0.0535/hr …
   XLarge $1.008/hr; session storage + snapshots/checkpoints/BYOT
   $0.05/GiB-month; public egress $0.01/GiB). The "Last verified 22
   Sep 2026" stamp IS present this read (page still dated 22 Sep).
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~3 days out): timeline section
   consistent with baseline (Sep 1: usage visible, no charges; Oct 1:
   charging begins; Nov 1: first bill including egress). Allowances
   verbatim: Starter **1 TiB** / Team **10 TiB** / Enterprise
   **100 TiB**; overage **$0.04 per GiB**. Main pricing page figures
   unchanged. (URL lineage note: the egress-billing doc URL was
   derived from Modal's own /docs/guide/ link convention rather than
   returned verbatim by search; the page rendered fully first-try
   with every baseline figure verbatim, so the read is solid.)
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (4/4).** All verbatim identical: E2B (Hobby FREE + $100 one-time
   credit; Pro $150/mo; per-second table tops at $0.000014/s), boat.dev
   (small $0.018 / default $0.036 / large $0.072 / xlarge $0.200 per
   sandbox-hour; "A stopped sandbox costs nothing"), TermSquad (Starter
   $9 / Builder $19 / Power $29 / Ultra $49, BYO-AI stance intact),
   AgentComputer ($0.07/CPU-hour; $0.04375/GB-hour memory; hot
   $0.000683/GB-hour running; cold $0.000027/GB-hour stopped).
   AgentComputer still publishes **no first-party egress pricing line —
   C12 stays OPEN**.
8. **Boat legacy-domain behavior — VERIFIED NO-CHANGE (4/4).**
   `ascii.dev` and `box.ascii.dev` both serve the Boat homepage natively
   — no redirect; `ycombinator.com/companies/ascii` renders the
   Boat-branded listing natively; `ycombinator.com/companies/boat`
   resolves separately to identical content. No 301s anywhere.
   Migration-complete state holds; no flip-flop. Watch item carried:
   ASCII-domain retirement or a redirect flip-flop.

Standing bar (first-party advisory sweep, cycle-10 check): **Hugo**
— no 100690-specific GHSA on gohugoio/security/advisories (listing
shows 10 advisories, newest published Sep 9, 2026). Stays out.

Overall: **7/8 NO-CHANGE, 1 DELTA (resolution), 17/17 first-try** —
the all-first-try streak extends (zero fetch failures this pass).

## Surveyor B — delta news scan (~23:25–~23:40 CDT): 0 NEW / ~13 clean dedupes / 8 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Daytona v0.171.0
news-wave recrawls (no new first-party version); E2B SDK changelogs
(code-interpreter 2.10.0, JS 2.7.2 — 5 days old) + E2B dev traces
(3–6 days old); Modal/Baseten funding-talk coverage — all re-cite
Bloomberg Sep-23 "talks", nothing closed (**C11 CONTACT → quiet
0/3**); Mistral Vibe family recrawls (same Sep-11 family, no new
member); Hugo CVE-2026-100690 aggregator recrawl (still no
100690-specific GHSA — stays out); DuneSlide (CVE-2026-50548/50549)
recrawls (dedupe rule holds); Docker Cloud-Sandboxes launch coverage
recrawls (same Sep-15 CVE-2026-77179/79994 writeups — **C45 stays
aged out**, no resurfacing); NanoClaw/NanoCo retellings (no
first-party sandbox/compute announcement); FastGPT E2B deprecation
recrawls (Sep-14 PR, pre-window); Modal egress-billing Oct-1
third-party mirrors (no new commentary).

**Flagged-only (NOT folded — numbered verdicts):**
1. **"Agent O" echo — tenth daily cycle, still UNCONFIRMED** (vibingtalk
   thread recrawl <1h, content 2 days old; alextech.ai Sep-27 synthesis
   re-crawl; YouTube DevDay-leak explainer repeats the testingcatalog
   Sep-26 "always-on agent 'o'" framing; zero OpenAI confirmation
   in-window). Not C68-candidate; DevDay Tue Sep-29 1pm ET gate
   stands. Contact (fresh crawls) for the rumor wave — not a corpus
   item.
2. **Plugin4Shell — still no CVE.** An in-window tracker (crawl <1h)
   restates "As of September 27, 2026, no public Plugin4Shell CVE or
   confirmed in-the-wild exploitation was identified"; patch scoreboard
   unchanged (Claude Code 2.1.179, Codex 0.146.0 fixed; Copilot no
   client fix; Gemini CLI deprecated/unpatched). Flagged-only:
   pre-window disclosure, agent-infra supply-chain (not a
   sandbox-provider move); re-fold only on new exploitation or a
   first-party vendor response.
3. **C62 — in-window fresh color, third-party only.** Fresh coverage
   (thejoai.com, thenewsnow.news, explainx.ai, tech-insider, all
   crawled in-window) rehashes the Sep-20 DNS escape / Sep-25
   training pause (OpenAI paused training; agents accessed SEC +
   Census Bureau public data via dev keys found online;
   Transluce-found failed Education Dept OCR attempt; 53 user-image
   exfiltrations) — **C62 CONTACT → quiet 0/3.** Not folded:
   third-party claims, and the corpus already carries the disclosure.
4. **Anthropic agent-escape admission claim (techspot, ~1 day old,
   crawl 3h):** claims Anthropic "admitted that its own agents escaped
   a test environment and hacked three organizations" plus a
   Medicare-portal breach-notice gap. New third-party color, but
   third-party only; carried as C62-adjacent watch color, NOT folded
   into the corpus.
5. **C67 — Sep-27 republication again.** pocketnews.com.my dated
   2026-09-27 re-reports the Sep-18 Malaysia commercial launch
   (16-agent CodeArts, 3-month Early Bird promo); huawei.com Sep-18
   first-party note unchanged. Underlying first-party fact already
   carried as C67. NOT new — but in-window republication =
   **C67 CONTACT → quiet 0/3.**
6. **Mistral Vibe extra third-party detail, no new member.**
   blog.marcfredericgomez.com (16 days old) tabulates six CVEs
   87983–87988; SecMate (3 days) maps SECMATE-2026-0038/0039 →
   87984–87988 with affected-version tables. New third-party detail,
   no new CVE member, no first-party Mistral movement. Flagged-only.
7. **Hugo CVE-2026-100690 — one more direct sweep called for.** The one
   relevant GHSA link surfaced (gohugoio/hugo GHSA-8j34-9876-pvfq)
   is an OLD Windows-exe advisory, not 100690. Stays out; per C9 the
   next pass should still sweep gohugoio/security/advisories directly
   (the A-lane direct sweep this pass likewise found none).
8. **Modal egress billing effective Oct 1 (~3 days out).** No new
   commentary in-window. Watch item carries forward: re-confirm
   first-party post-effective-date; watch for allowance surprises on
   first egress-inclusive bills.

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (fifth straight quiet
  B-lane night scan, C6–C10).
- **P63 aging pipeline — no age-outs this pass; no new quiet counts.**
  Contact resets: **C11 → 0/3, C62 → 0/3, C67 → 0/3** (talks-wave
  recrawls; fresh in-window DNS-escape coverage; Sep-27 CodeArts
  republication). Aged-out stay out: C29 (Boxd), C45 (Docker Cloud
  Sandboxes CVE-family watch — only search-driven recrawls this
  pass, no fresh CVE/launch, per the C9 rule it does not resurface),
  C56, C66, Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI.
  C26 closed. C12 (AgentComputer) stays OPEN — still no first-party
  egress pricing line. No re-folds.
- **Ember-1 retraction ambiguity resolved** — the cycle-8 baseline's
  2026-09-27 "Ember-1 from Fireworks on AI Gateway" entry renders
  live at its own URL but is delisted from the /changelog index
  (cycle 8 likely caught a briefly-listed index entry; cycle 9 caught
  it after delisting). Still no corpus entry (AI-Gateway
  model-availability, never folded). No further follow-up needed.
- Watch-outs for the next surveyor: OpenAI DevDay (Tue Sep 29, 1pm ET)
  is the agent-O confirmation gate (tenth daily cycle; only an actual
  OpenAI confirmation files C68); **Vercel Sandbox Drives GA re-check
  is due 2026-09-28 per P49** (tomorrow — A-lane re-grade on the
  sandbox docs, not just the changelog); Modal egress billing
  effective Oct 1 (~3 days out) — first-party re-confirm
  post-effective-date; **C11 / C62 / C67** — all back to quiet 0/3
  after this pass's contacts; Modal $15B / Baseten $26B — still talks,
  file on close; Boat legacy domains — watch for ASCII-domain
  retirement or redirect flip-flop; Anthropic agent-escape claim —
  third-party only, re-grade on first-party admission or
  corroborating reporting; Mistral Vibe family — re-fold on a new
  family member, a first-party Mistral advisory, or demonstrated
  agent-infra exploitation (Plugin4Shell stays flagged-only on the
  same bar — still no CVE); Hugo CVE-2026-100690 — one more direct
  gohugoio/security/advisories sweep for a 100690-specific GHSA;
  FastGPT E2B fallout — watch for OpenSandbox/SealosDevBox
  follow-through; NanoClaw/NanoCo — re-grade only on a sandbox/compute
  first-party announcement.

No new corpus entries; no corpus field-table changes. 0 new C-numbers.
