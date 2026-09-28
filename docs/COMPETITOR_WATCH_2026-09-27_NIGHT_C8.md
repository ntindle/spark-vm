# Competitor watch — 2026-09-27 (night, cycle 8)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads ~22:23:30–~22:25:00 CDT 2026-09-27) against
the cycle-7 (~21:26–~21:29 CDT) baseline — **8/8 VENDOR-VERIFIED
NO-CHANGE, 8/8 first-try** (zero fetch failures; the all-first-try
streak extends to nine straight zero-fetch-failure passes).
Surveyor B: delta news scan over ~21:28–~22:25 CDT (~57-min window, 12
queries, snippet level, zero pages opened) — **quiet pass, 0 NEW with
evidence, 11 clean dedupes, 14 flagged-only, 0 new C-numbers**.

Delta-only against the cycle-7 late-evening pass
(`docs/COMPETITOR_WATCH_2026-09-27_LATE_EVENING_C7.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260927-2154.md`,
`agent_notes/surveyor-b-20260927-2154.md` (under `hidden_files`).
`_C8` disambiguator since `NIGHT` already names the 2026-09-23 pass
(the MORNING_C2 precedent).

> **Timestamp provenance note:** every verification-time claim in this
> doc is bounded by the surveyors' actual completion times (A: reads
> ~22:23:30–~22:25:00 CDT, completion 22:25:19 CDT; B: scan window
> ~21:28–~22:25 CDT, completion 22:25 CDT) — no claimed read post-dates
> its record. Surveyor B's scan ran ~22 minutes long of the planned
> ~35-min window; the window itself is in-window and valid.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~22:23:30–~22:25:00 CDT)

**8/8 VERIFIED NO-CHANGE, 8/8 first-try.** No deltas to fold.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); no V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22** ("Improved sandbox moves and support for
   private kit images in cloud sandboxes"); v3 kits (2026-09-21)
   unchanged below it.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**
   (no v0.7.4 tag).
4. **Vercel changelog — VERIFIED NO-CHANGE.** Newest entry still the
   2026-09-27 first-party **"Ember-1 from Fireworks now available on AI
   Gateway"** (AI Gateway model-availability, NOT Sandbox). Sandbox-lane
   entries stand as written: "Vercel Sandbox now supports memory
   observability" (2026-09-25), "Drives for Vercel Sandbox are now in
   public beta" (2026-09-23). Nothing newer than Sep 27. (Vercel Drives
   GA not re-checked — daily cadence per P49, next due 2026-09-28.)
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical ($0.044/vCPU-hour active CPU — footnote: active-CPU
   billing still "coming soon", billed at 25% of allocated vCPUs until
   then; $0.0095/GB-hour memory; shapes XSmall $0.0535/hr …
   XLarge $1.008/hr; session storage + snapshots/checkpoints/BYOT
   $0.05/GiB-month; public egress $0.01/GiB). **The "Last verified 22
   Sep 2026" stamp IS present this read** (page still dated 22 Sep; the
   capture-gap reading stays resolved as artifact). Third-party context
   (not a delta): DO's own Sep-22 press release quotes the investor-page
   $0.005 snapshot figure — a different line item from the first-party
   docs' $0.05/GiB-month; the standing 10× snapshots conflict is
   unresolved but unmoved.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~2 days out): the timeline section is
   consistent with the cycle-7 baseline (Sep 1: usage visible, no
   charges; Oct 1: charging begins; Nov 1: first bill including egress).
   Allowances verbatim: Starter **1 TiB** / Team **10 TiB** / Enterprise
   **100 TiB**; overage **$0.04 per GiB** (Volumes read/writes excluded
   from egress; Cloud Bucket Mount uploads count as egress). Main
   pricing page figures unchanged.
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
   ($0.036/h default 4 vCPU / 8 GB) — no redirect;
   `ycombinator.com/companies/ascii` renders the Boat-branded listing
   natively; `ycombinator.com/companies/boat` resolves separately to
   identical content. No 301s anywhere. Migration-complete state holds;
   no flip-flop. Watch item carried: ASCII-domain retirement or a
   redirect flip-flop.

Overall: **8/8 NO-CHANGE, 8/8 first-try** — the all-first-try streak
extends (zero fetch failures this pass).

## Surveyor B — delta news scan (~21:28–~22:25 CDT): 0 NEW / 11 clean dedupes / 14 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Docker Cloud Sandboxes
+ OCI Kits Sep-24/25 announcement wave (release notes still 2026-09-22
— no in-window release); Vercel Sandbox SDK changelogs (pre-window, no
in-window bump); Modal $15B / Baseten $26B talks (all cite Bloomberg
Sep-23 — still talks, nothing closed; fresh crawls are a **C11
(Baseten/Blaxel) contact**); Mistral Vibe CVE-2026-87984/87985/87987
recrawls (same Sep-11 family, no new member); DuneSlide
(CVE-2026-50548/50549 — dedupe rule holds); NanoClaw/NanoCo
(personal-agent runtime news only, no first-party sandbox/compute
announcement); Hugo CVE-2026-100690 aggregator recrawl (still no
100690-specific GHSA — stays out); Guava/"Daytona" name-collision /
sandbox comparison wikis (recrawls only); OpenAI "agent swarm" security
retrospectives (pre-window retellings, no new fact); agent-sandbox
hobbyist repos (lane-adjacent personal tooling, no in-window news);
theregister Docker Cloud Sandboxes Sep-24 (recrawl of known coverage).

**Flagged-only (NOT folded — numbered verdicts):**
1. **"Agent O" echo — eighth daily cycle, still UNCONFIRMED** (vibingtalk
   forum + YouTube explainer repeat the testingcatalog Sep-26 "always-on
   agent 'o'" framing; zero OpenAI confirmation in-window). Not
   C68-candidate; DevDay Sep-29 1pm ET gate stands. Fresh crawls =
   rumor-wave contact.
2. **Plugin4Shell (AIR Security, Sep-17)** — zero-click supply-chain RCE
   across coding-agent CLIs via SHA-pin bypass (pre-window disclosure,
   in-window recrawls only; no new vendor movement). Flagged-only:
   re-fold candidate only on new exploitation or a first-party vendor
   response.
3. **CVE-2026-93993 in US-CERT week-of-Sep-14 summary** — third-party
   mirror, no new substance. Parent call stands: NOT folded.
4. **Mistral Vibe GitPython dep-scan** — third-party scan report;
   reachability analysis says the config-injection path isn't reachable.
   Not a new CVE; no corpus entry.
5. **Modal egress-billing Oct-1 commentary search** — no new
   commentary in-window (third-party mirrors of first-party docs only).
   The ~2-days-out watch item carries forward unchanged.
6. **Vercel Sandbox Drives design review (nandann.com, pre-window)** —
   third-party security analysis of the Sep-23 public beta; adds no new
   first-party fact. Flagged-only, lane-adjacent color.
7. **ai-cost-estimator Vercel Sandbox 64GB piece** — third-party cost
   analysis, pre-window.
8. **FastGPT E2B deprecation (PRNewswire, Sep-14, pre-window)** —
   self-hosted vendor's migration guidance, not E2B news. Flagged-only
   market color for E2B's position.
9. **willemave/newsbuddy E2B sandboxes doc (Sep-1, pre-window)** — no
   new E2B first-party signal.
10. **Daytona developer-side traces** — pre-window usage traces; no
    Daytona first-party news in-window (changelog still V0.218.0 per
    Surveyor A).
11. **boat.dev homepage** — pricing content identical; native domain
    serving confirmed (Surveyor A item 8).
12. **Cloudflare/Cursor sandbox dev.to piece (19d, pre-window)** —
    retelling of the Sep-2 announcement.
13. **C12 (AgentComputer)** — not surfaced in B lane; stays OPEN.
14. **C29 (Boxd)** — not surfaced this pass; **third consecutive
    news-scan pass without surface** (C4–C6 ran no B lane; C7 and C8
    news scans). At the 3-quiet threshold — **AGED OUT this pass per
    P63** (see Standing status).

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (third straight quiet B-lane
  night scan).
- **P63 aging pipeline — one age-out this pass (mandatory one-notice
  line): C29 Boxd is AGED OUT** after three consecutive news-scan passes
  without surface (C7 + C8 news scans; C4–C6 ran no B lane, so no older
  B-lane pass contradicts the count). The Boxd field-table row
  (VERIFIED 2026-09-23 rate card) is RETAINED as canonical reference —
  the age-out retires the watch item from the aging pipeline, not the
  vendor facts (same treatment as C56's retained DeepSeek row). The P66
  re-fold path stands if Boxd resurfaces. Contact resets this pass:
  agent-O rumor wave, Hugo CVE-2026-100690, Mistral Vibe family
  (87984/87985/87987 recrawls), CVE-2026-93993 US-CERT mirror,
  Plugin4Shell recrawls, C11 (Baseten/Blaxel talks wave — fresh crawls,
  quiet stays 0/3). Quiet this pass: C45 (Docker Cloud Sandboxes) 2/3,
  C62 (OpenAI offline-sandbox escape) 2/3, C67 (Huawei CodeArts Agent,
  Malaysia) 2/3 — one more quiet pass each and the age-out threshold
  fires. Aged-out stay out: C56, C66, Heapjack/Overpatch, GitLab
  CVE-2026-85706, Dextr AI, **C29 (this pass)**. C26 closed. No re-folds.
- Watch-outs for the next surveyor: OpenAI DevDay (Tue Sep 29, 1pm ET)
  is the agent-O confirmation gate (only an actual OpenAI confirmation
  files C68); Modal egress billing effective Oct 1 (~2 days out) —
  first-party re-confirm post-effective-date; C45/C62/C67 all at quiet
  2/3; Hugo CVE-2026-100690 — one more gohugoio/security/advisories
  sweep for a 100690-specific GHSA; Modal $15B / Baseten $26B — still
  talks, file on close; Boat legacy domains — watch for ASCII-domain
  retirement or redirect flip-flop; Vercel Sandbox — Drives re-grade
  only on a model/agent angle; Mistral Vibe family — re-fold on a new
  family member, a first-party Mistral advisory, or demonstrated
  agent-infra exploitation (Plugin4Shell stays flagged-only on the same
  bar).

No new corpus entries; no corpus field-table changes beyond the C29
aging notice (row retained). 0 new C-numbers.
