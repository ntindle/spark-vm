# Competitor watch — 2026-09-27 (late-evening, cycle 7)

**Two-surveyor pass.** Surveyor A: fast-mover + pricing re-verification
(first-party, vendor reads ~21:26–21:29 CDT 2026-09-27) against the
cycle-3 (~18:26–~18:55 CDT) baseline — 6/8 VENDOR-VERIFIED NO-CHANGE,
2/8 VERIFIED CHANGED, 8/8 first-try (zero fetch failures). Surveyor B:
delta news scan over ~18:55–~21:28 CDT (~2.5h window, 9 queries,
snippet level, zero pages opened) — quiet pass, 2 NEW with evidence,
12 clean dedupes, 13 flagged-only, **0 new C-numbers**.

Delta-only against the cycle-6 consolidation pass
(`docs/COMPETITOR_WATCH_2026-09-27_LATE_EVENING_C6.md`). Read-only, no
logins, no writes.

> **Timestamp provenance note (round-2 review):** the surveyors' initial reports carried
> forward-projected read windows (A: "~21:30–21:47"; B: "~21:25–21:40"). Every verification-time
> claim in this doc is bounded by the surveyors' actual completion times (A: 21:28:55 CDT,
> B: 21:27:42 CDT) — no claimed read post-dates its record.

## Surveyor A — fast-mover + pricing re-verification (first-party, ~21:26–21:29 CDT)

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still
   **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"); no V0.219+.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still tops
   out at **2026-09-22** ("Improved sandbox moves and support for
   private kit images in cloud sandboxes").
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Still **v0.7.3**
   (no v0.7.4 tag).
4. **Vercel changelog — VERIFIED CHANGED.** The first-party changelog
   sitemap now lists a new entry **"Ember-1 from Fireworks now available
   on AI Gateway" — 2026-09-27**, ahead of the 2026-09-25 trio. This is
   AI Gateway model-availability news, NOT Vercel Sandbox — the Sandbox
   lane is unchanged. Flagged-only, lane-adjacent; no corpus entry.
5. **DigitalOcean canonical pricing — VERIFIED NO-CHANGE.** All figures
   identical ($0.044/vCPU-hour active CPU — footnote: active-CPU billing
   still "coming soon", billed at 25% of allocated vCPUs until then;
   $0.0095/GB-hour memory; shapes XSmall $0.0535/hr … XLarge $1.008/hr;
   session storage + snapshots $0.05/GiB-month; public egress $0.01/GiB).
   **The "Last verified 22 Sep 2026" stamp IS present this read** — the
   11-pass capture gap resolves as a capture artifact, not a page change
   (page still dated 22 Sep).
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** First-party
   docs confirm egress billing still starts **Oct 1, 2026** (~4 days
   out): usage visible since Sep 1, first bill Nov 1; allowances Starter
   **1 TiB** / Team **10 TiB** / Enterprise **100 TiB**; overage
   **$0.04/GiB**. Plans/credits on the main pricing page unchanged.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED
   NO-CHANGE.** E2B (Hobby FREE + $100 one-time credit; Pro $150/mo;
   per-second table $0.000014/s), boat.dev (small $0.018 / default
   $0.036 / large $0.072 / xlarge $0.200 per sandbox-hour; plans
   $20/$100/$500/$2,000), TermSquad (Starter $9 / Builder $19 /
   Power $29 / Ultra $49, identical specs), AgentComputer ($0.07/CPU-hour;
   $0.04375/GB-hour memory; hot $0.000683/GB-hour running; cold
   $0.000027/GB-hour stopped) — all verbatim identical. AgentComputer
   still publishes **no first-party egress line — C12 stays OPEN**.
8. **Boat legacy-domain behavior — VERIFIED CHANGED.** The 301
   redirects recorded by the cycle-6 consolidation pass are **gone**:
   `ycombinator.com/companies/ascii` now renders the Boat-branded
   listing directly ("Boat: The best cloud VMs for billions of agents |
   Y Combinator"); `ycombinator.com/companies/boat` resolves separately
   to identical content; `ascii.dev` and `box.ascii.dev` now serve the
   Boat homepage natively ("boat: Cheapest, Most Powerful Sandboxes for
   Agents", $0.036/h default 4 vCPU/8 GB) — no redirect. Interpretation:
   the ASCII→Boat domain migration is now **complete**; the legacy ASCII
   domains host Boat content natively instead of redirecting. The corpus
   Boat-row rename narrative is updated with this mechanism (supersedes
   the cycle-6 301 mechanism).

Overall: **6/8 NO-CHANGE, 2/8 CHANGED, 8/8 first-try** — the all-first-try
streak extends (zero fetch failures this pass).

## Surveyor B — delta news scan (~18:55–~21:28 CDT): 2 NEW / 12 clean dedupes / 13 flagged-only

**NEW with evidence:**

1. **"Agent O" echo — seventh daily cycle, still UNCONFIRMED.** New
   aggregator batch in-window: Medium "Exclusive Leak" (Sep 27, 10:25
   Beijing), KuCoin Flash (2026/09/27 01:23:16 UTC), wisevoter,
   tokenpost, YouTube explainer — all trace to testingcatalog's Sep-26
   report. Counter-evidence stands: pasqualepillitteri.it still tabulates
   "Launch of 'o' at DevDay — Hypothesis, no confirmation". **No OpenAI
   confirmation anywhere in the delta → NOT C68-candidate.** The DevDay
   keynote (Tue Sep 29, 1pm ET) remains the confirmation gate.
2. **Mistral CVE-2026-93993 substance surfaced.** donge/aisec 2026-09-23
   daily: "Mistral Vibe before 2.25.5 contains RCE in the worktree
   creation process that executes git hooks before trust validation",
   CVSS 8.8 HIGH, cites NVD. The disclosure itself is pre-window
   (Sep-23), but this is the first substance in the corpus — and a
   **distinct mechanism** (pre-trust git-hook execution) from the
   87983–88 read-only/path family. Parent call: **NOT folded this pass**
   (pre-window disclosure; watch docs are delta-only) — the whole Vibe
   family stays carried as corpus-gap candidacy. Re-fold conditions: a
   new family member, a first-party Mistral advisory, or demonstrated
   agent-infra exploitation.

**Clean dedupes (pre-window, already known, recrawled only):** Modal
$15B / Baseten $26B talks recrawls (metirai <1h, bytevyte <1h,
techfundingnews "just now", techflier 2h, wesearch 20h — all cite
Bloomberg Sep-23); Hugo CVE-2026-100690 thehackerwire recrawl (2h);
Mistral 87987 (stackflag 5h) / 87988 (cvefeed 4h); DuneSlide (lemma 3d,
orca-ai-incident-archive 3d, pondera 22h, llm-hacking 2d, THN 5d);
Aliyun FC doc pages (updated 6d, crawled 3d); TermSquad Sep-15 press
(4–5d, one 1d); Azure SRE Agent (159-day-old networkworld piece,
recrawled 3h); sandbox comparison wikis (3–23d); NanoClaw
(docker/sbx-kits-contrib kit 3d, imprnt dossier 6d/3d, glifocat 3d);
OpenRouter 2026-10-05 server-side-exec blog (future-dated, crawled 3d);
Guava "Daytona" (Sep-23 businesswire, crawled 4d); Mistral May-breach
denial (TechRadar Sep-22, crawled 1d).

**Flagged-only (NOT folded) — numbered, one-line verdicts each:**

1. **Agent O** — seventh echo cycle, no OpenAI confirmation → not
   C68-candidate; DevDay Sep-29 gate stands.
2. **Hugo CVE-2026-100690** — gohugoio/security/advisories sweep: NO
   100690-specific GHSA (only pre-existing GHSA-8j34-9876-pvfq,
   GHSA-vrm6-x8vp-mv2r, GHSA-vrv5-r5rf-6v4j). Stays out; re-folds only on
   a 100690-specific GHSA or an agent-infra nexus.
3. **Modal $15B / Baseten $26B** — still talks, not closed (all fresh
   crawls re-cite Bloomberg Sep-23). New third-party color (not folded):
   techflier Sep-26 — Modal Sandboxes ~$300M annualised revenue by April.
4. **NanoClaw/NanoCo** — standing holds: the docker/sbx-kits-contrib
   "nanoclaw" kit (3d) is a Docker Sandbox kit that runs the NanoClaw
   personal-agent runtime inside a sandbox micro-VM — evidence of
   category overlap, NOT a NanoCo sandbox/compute announcement. NanoCo
   remains personal-AI-agent, flagged-only.
5. **Mistral CVE-2026-93993** — parent call: NOT folded (see NEW §2).
6. **Mistral May-leak resurfacing** — lane-adjacent (seller claims fresh
   breach with May-leak-looking code; Mistral denies — TechRadar Sep-22);
   not a sandbox vuln; no agent-infra nexus.
7. **DuneSlide (CVE-2026-50548/50549)** — dedupe rule holds
   (orca-ai-incident-archive re-affirms: 50549 shares Cursor's fix-ID
   with Wiz's GhostApproval 2026-07-09 → merge/`duplicate_of`, never
   double-count).
8. **Aliyun FC Agent Sandbox** — quiet lane (doc pages only; Shallow
   Hibernation still invite-only).
9. **Guava "Daytona" voice model** — name-collision item only (Sep-23);
   voice AI, not sandbox.
10. **Azure SRE Agent** — quiet (only the 159-day-old
    eavesdropping-flaw recrawl).
11. **weeklyclaw-ai podcast** — no signal this sweep.
12. **C12 (AgentComputer)** — not surfaced in B lane; stays OPEN.
13. **C29 (Boxd)** — not surfaced; carried.

No corpus fold (C32 precedent: watch docs are delta-only). No new
C-numbers. Sandbox-infrastructure lane stays quiet; the in-lane
no-launch verdict dated 2026-09-25 stands — streak extends.

## Corpus aging pipeline (P63)

Quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass.

**Contact this pass (quiet count reset / stays 0/3):** the agent-O rumor
wave (fresh crawls <1h–10h); Hugo CVE-2026-100690 (thehackerwire 2h
recrawl); Mistral 87987/87988 (4–5h recrawls); CVE-2026-93993 substance
(3d crawl); **C11 (Baseten/Blaxel)** — fresh Modal/Baseten talks wave
(<1h–20h, still talks) → quiet stays 0/3; Azure SRE (3h recrawl);
DuneSlide pondera review (22h); TermSquad (1d); docker nanoclaw kit (3d);
Guava/"Daytona" (4d); Aliyun FC doc surface (3d); Mistral May-denial
(1d); all 8 first-party re-verification items (the 8 numbered Surveyor-A items — item 7 bundles E2B/boat.dev/TermSquad/AgentComputer — contact, not quiet passes).

**Quiet this pass:** **C45 (Docker Cloud Sandboxes)** — no new CVE in
the 77179/79994 family surfaced; quiet pass 1/3. **C29 (Boxd)** — quiet **2/3** — not
surfaced in B lane, second consecutive news-scan pass without surface
(C4–C6 ran no B lane); carried — no age-out (3-consecutive-quiet
threshold not reached). **C62 (OpenAI offline-sandbox escape)** — no contact this pass; the 7-outlet recrawl wave that reset it to 0/3 at cycle 3 has wound down — quiet **1/3**. **C67 (Huawei CodeArts Agent, Malaysia)** — no contact this pass — quiet **1/3** (grade FIRST-PARTY-CORROBORATED unchanged). Vercel Sandbox lane, Runloop, Cloudflare Sandbox
SDK, boat.dev first-party news, weeklyclaw-ai podcast — no contact.
**C12 (AgentComputer)** — no B-lane surface, but first-party pricing
contact via Surveyor A (still no egress line); not a quiet pass; stays
OPEN.

**Aged-out stay out:** C56 (DeepSeek Harness CVE-2026-82533 — not
sighted; P66); C66 (OpenClaw CVE-2026-100589 — not sighted);
Heapjack/Overpatch; GitLab CVE-2026-85706. **C26** closed, stays closed.

**No age-outs this pass; no re-folds.**

## Corpus edits this pass

- Boat-row rename narrative: the cycle-6 "301 redirect" mechanism is
  superseded — per the ~21:26–21:29 CDT first-party verification, the ASCII→Boat
  domain migration is complete (legacy domains serve Boat natively).
- Watch-update section below in `docs/COMPETITOR_ANALYSIS.md`; index row
  in `docs/README.md`; reader-facing CHANGELOG bullet.

## Watch-out for the next surveyor

1. OpenAI DevDay (Tue Sep 29, 1pm ET) — the "agent O" echo is on its
   seventh daily cycle; only an actual OpenAI confirmation files C68.
2. **C62 quiet-count wind-down** — the 7-outlet recrawl wave that reset C62 to 0/3 at cycle 3 has wound down (no contact this pass, quiet 1/3); watch for a genuine second quiet pass before any new aging run (carries C3 watch-out #2).
3. Modal egress billing effective Oct 1 (~3 days out) — first-party
   re-confirm post-effective-date; watch for allowance surprises on the
   first egress-inclusive bills.
4. Vercel AI Gateway Ember-1 entry — lane-adjacent; re-grade only if
   Vercel Sandbox gains a model/agent angle.
5. Mistral Vibe family — the 93993 parent call stands (NOT folded);
   re-fold on a new family member, a first-party Mistral advisory, or
   demonstrated agent-infra exploitation.
6. Boat legacy domains — native serving now; watch for ASCII-domain
   retirement or any redirect flip-flop.
7. Hugo CVE-2026-100690 — one more gohugoio/security/advisories sweep
   for a 100690-specific GHSA.
8. Modal $15B / Baseten $26B — still talks; file on close.
9. NanoClaw/NanoCo — first-party sandbox/compute announcement only.
10. C29 — third consecutive news-scan pass without surface would reach the
   age-out threshold; watch.
11. DuneSlide dedupe rule (merge/`duplicate_of` on shared fix-IDs);
    C12 (first-party egress line); C45 family (new members).

## Not done this turn

- No other vendor re-checks — the cycle-3 + C4–C6 baselines stand; the
  in-lane no-launch verdict dated 2026-09-25 stands.
- `docs.ascii.dev`'s redirect chain was NOT re-checked this pass; the
  cycle-6 verification stands.
