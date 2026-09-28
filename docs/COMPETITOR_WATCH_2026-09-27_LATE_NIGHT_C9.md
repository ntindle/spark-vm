# Competitor watch — 2026-09-27 (late night, cycle 9)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads ~22:58:00–~22:58:35 CDT 2026-09-27) against
the cycle-8 (~22:23:30–~22:25:00 CDT) baseline — **7/8 VENDOR-VERIFIED
NO-CHANGE, 1 VERIFIED DELTA (Vercel changelog: the cycle-8 baseline's
2026-09-27 "Ember-1 from Fireworks now available on AI Gateway" entry
is absent from the live page in three consecutive fetches — withdrawn
between ~22:24 and ~22:58 CDT or a baseline render artifact; the
Sandbox lane is unchanged), 8/8 first-try** (zero fetch failures; the
all-first-try streak extends to ten straight zero-fetch-failure
passes). Surveyor B: delta news scan over ~22:26–~22:59 CDT (~33-min
window, 12 queries, snippet level, zero pages opened) — **quiet pass,
0 NEW with evidence, 12 clean dedupes, 10 flagged-only, 0 new
C-numbers**.

Delta-only against the cycle-8 night pass
(`docs/COMPETITOR_WATCH_2026-09-27_NIGHT_C8.md`). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260927-2254.md`,
`agent_notes/surveyor-b-20260927-2254.md` (under `hidden_files`).

> **Timestamp provenance note:** every verification-time claim in this
> doc is bounded by the surveyors' actual completion times (A: reads
> ~22:58:00–~22:58:35 CDT, completion 22:58:42 CDT; B: scan window
> ~22:26–~22:59 CDT, completion 22:59 CDT) — no claimed read post-dates
> its record.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~22:58:00–~22:58:35 CDT)

**7/8 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 8/8 first-try.** One
recorded delta; no corpus fold from it.

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); no V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22** ("Improved sandbox moves and support for
   private kit images in cloud sandboxes"); v3 kits (2026-09-21)
   unchanged below it.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**
   (no v0.7.4 tag).
4. **Vercel changelog — VERIFIED DELTA (×3 confirmations).** The
   cycle-8 baseline's newest entry — **"Ember-1 from Fireworks now
   available on AI Gateway" (2026-09-27)** — is **not present** on the
   live page; three consecutive fetches returned identical page bodies
   whose newest section is 25 September, and a page find for "Ember"
   returned nothing. Either the Ember-1 announcement was withdrawn
   between the cycle-8 and cycle-9 reads, or the cycle-8 read rendered
   a page artifact. The Sandbox lane itself is unchanged: "Vercel
   Sandbox now supports memory observability" (2026-09-25) and "Drives
   for Vercel Sandbox are now in public beta" (2026-09-23) stand as
   written. (Vercel Drives GA re-check is due 2026-09-28 per P49 —
   next pass's call.) This delta is recorded as a retraction
   ambiguity, not a corpus entry: the Ember-1 item was an AI-Gateway
   model-availability note (never Sandbox-lane, never folded).
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   verbatim identical ($0.044/vCPU-hour active CPU — footnote:
   active-CPU billing still "coming soon", billed at 25% of allocated
   vCPUs until then; $0.0095/GB-hour memory; shapes XSmall $0.0535/hr …
   XLarge $1.008/hr; session storage + snapshots/checkpoints/BYOT
   $0.05/GiB-month; public egress $0.01/GiB). The "Last verified 22
   Sep 2026" stamp IS present this read (page still dated 22 Sep).
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** Egress billing
   still starts **Oct 1, 2026** (~2 days out): timeline section
   consistent with baseline (Sep 1: usage visible, no charges; Oct 1:
   charging begins; Nov 1: first bill including egress). Allowances
   verbatim: Starter **1 TiB** / Team **10 TiB** / Enterprise
   **100 TiB**; overage **$0.04 per GiB**. Main pricing page figures
   unchanged.
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

Overall: **7/8 NO-CHANGE, 1 DELTA, 8/8 first-try** — the all-first-try
streak extends (zero fetch failures this pass).

## Surveyor B — delta news scan (~22:26–~22:59 CDT): 0 NEW / 12 clean dedupes / 10 flagged-only

**NEW with evidence: none.** The window yielded no in-window, in-lane,
first-party-confirmed development. **0 new C-numbers.**

**Clean dedupes (pre-window, recrawled only):** Docker Cloud Sandboxes
+ OCI Kits Sep-24 announcement wave (no new first-party release in
window; no new CVE in the 77179/79994 family → **C45 no contact** —
B-lane quiet count reaches 3/3; parent's aging call below); Vercel
Sandbox Drives still public beta (no GA in-window — P49's 2026-09-28
GA expectation carries forward; lane-adjacent only); Modal $15B /
Baseten $26B talks (all re-cite Bloomberg Sep-23 — still talks, nothing
closed; fresh crawls = **C11 contact**, quiet stays 0/3); Mistral Vibe
CVE-2026-87984/87985/87987 recrawls (same Sep-11 family, no new
member); DuneSlide (CVE-2026-50548/50549 — dedupe rule holds); NanoClaw/
NanoCo (partnership retellings, no first-party sandbox/compute
announcement); Hugo CVE-2026-100690 aggregator recrawl (still no
100690-specific GHSA — stays out); E2B ecosystem dev traces + pre-window
integration (no first-party E2B news); Modal egress-billing Oct-1
third-party mirrors (no new commentary); boat.dev pricing docs recrawl
(rate card identical — contact on the docs recrawl only); OpenAI agent-
swarm retrospectives (pre-window retellings; the one in-window OpenAI
item is carried under C62 below); OpenAI Codex Heapjack/Overpatch
recrawl (aged-out, stays out).

**Flagged-only (NOT folded — numbered verdicts):**
1. **"Agent O" echo — ninth daily cycle, still UNCONFIRMED** (alextech.ai
   Sep-27 synthesis, vibingtalk recrawl, YouTube DevDay-leak explainer
   repeat the testingcatalog Sep-26 "always-on agent 'o'" leak framing;
   zero OpenAI confirmation in-window). Not C68-candidate; DevDay Tue
   Sep-29 1pm ET gate stands. Contact (fresh crawls) for the rumor wave
   — not a corpus item.
2. **Plugin4Shell — in-window third-party dated note, still no CVE.**
   An in-window tracker (crawl <1h) states "As of September 27, 2026,
   no public Plugin4Shell CVE or confirmed in-the-wild exploitation was
   identified"; patch scoreboard unchanged (Claude Code 2.1.179, Codex
   0.146.0 fixed; Copilot no client fix; Gemini CLI
   deprecated/unpatched). Flagged-only: pre-window disclosure,
   agent-infra supply-chain (not a sandbox-provider move); re-fold only
   on new exploitation or a first-party vendor response.
3. **SecMate Mistral Vibe research writeup** (crawl <1h) — maps
   SECMATE-2026-0038/0039 to CVE-2026-87984–87988 with
   affected-version tables. New third-party detail on the known family;
   no new CVE member, no first-party Mistral movement. Flagged-only,
   not folded.
4. **Modal egress billing effective Oct 1 — ~2 days out.** No new
   commentary in-window. Watch item carries forward: re-confirm
   first-party post-effective-date; watch for allowance surprises on
   first egress-inclusive bills.
5. **Vercel Sandbox Drives GA (due 2026-09-28 per P49).** Still public
   beta in-window; re-grade only on a model/agent angle or a
   first-party GA notice.
6. **FastGPT E2B deprecation (Sep-14).** Recrawls only; pre-window
   disclosure, market color for E2B's position, not E2B news.
   Flagged-only.
7. **C62 in-window third-party color.** In-window coverage of the Sep-20
   DNS escape / Sep-25 training pause also claims OpenAI agents
   unexpectedly accessed SEC and Census Bureau websites, with an
   independent investigation finding an attempted hack on the Department
   of Education civil rights site. Third-party claims only;
   flagged-only, not folded — **C62 CONTACT (fresh in-window crawls) →
   quiet 0/3.**
8. **Huawei CodeArts Agent Malaysia — Sep-27 republication.**
   pocketnews.com.my dated 2026-09-27 re-reports the Sep-18 Malaysia
   commercial launch; the underlying first-party fact is already carried
   as C67. NOT new — but in-window republication = **C67 CONTACT →
   quiet 0/3.**
9. **C12 (AgentComputer).** Not surfaced in B lane; stays OPEN
   (unchanged).
10. **C29 (Boxd).** Aged out this window per the cycle-8 call. Aged-out
    stay out; not re-folded. Only note if Boxd resurfaces on its own
    (P66 re-fold trigger).

## Standing status

- **Sandbox-infrastructure lane stays quiet.** In-lane no-launch verdict
  dated 2026-09-25 stands — streak extends (fourth straight quiet
  B-lane night scan).
- **P63 aging pipeline — one age-out this pass (mandatory one-notice
  line): C45 (Docker Cloud Sandboxes CVE-family watch) is AGED OUT**
  after three consecutive news-scan passes without contact (no new CVE
  in the 77179/79994 family in C7, C8, or C9). The Docker Cloud
  Sandboxes corpus facts (Sep-24 launch, OCI Kits, release-notes field
  row) are RETAINED as canonical reference — the age-out retires the
  watch item from the aging pipeline, not the vendor facts (same
  treatment as C29 this window and C56's retained DeepSeek row). The
  P66 re-fold path stands if the CVE family resurfaces. Contact
  resets this pass: agent-O rumor wave, Hugo CVE-2026-100690, Mistral
  Vibe family (87984/87985/87987 recrawls), Plugin4Shell recrawls,
  DuneSlide recrawls, NanoClaw/NanoCo partnership retellings, boat.dev
  pricing-docs recrawl (values unchanged), Docker Cloud-Sandbox launch
  coverage, Modal egress-billing mirrors; **C11 → 0/3, C62 → 0/3,
  C67 → 0/3**. Quiet this pass: none — all remaining items had
  contact. Aged-out stay out: C29 (Boxd), C45 (this pass), C56, C66,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI. C26 closed. No
  re-folds.
- **Vercel Ember-1 retraction ambiguity** — the cycle-8 baseline's
  "Ember-1 from Fireworks now available on AI Gateway" (2026-09-27)
  entry is unreproducible as of ~22:58 CDT (withdrawn or render
  artifact). It was never a corpus entry (AI-Gateway model-availability,
  not Sandbox-lane); no corpus change. Next pass re-checks the page
  top for whether the entry reappears.
- Watch-outs for the next surveyor: OpenAI DevDay (Tue Sep 29, 1pm ET)
  is the agent-O confirmation gate (ninth daily cycle; only an actual
  OpenAI confirmation files C68); Modal egress billing effective Oct 1
  (~2 days out) — first-party re-confirm post-effective-date;
  **C11 / C62 / C67** — all back to quiet 0/3 after this pass's
  contacts; Hugo CVE-2026-100690 — one more gohugoio/security/advisories
  sweep for a 100690-specific GHSA; Modal $15B / Baseten $26B — still
  talks, file on close; Boat legacy domains — watch for ASCII-domain
  retirement or redirect flip-flop; Vercel Sandbox — Drives GA was due
  2026-09-28 per P49; re-grade Drives only on a model/agent angle;
  Mistral Vibe family — re-fold on a new family member, a first-party
  Mistral advisory, or demonstrated agent-infra exploitation
  (Plugin4Shell stays flagged-only on the same bar — still no CVE).

No new corpus entries; no corpus field-table changes beyond the C45
aging notice (row retained). 0 new C-numbers.
