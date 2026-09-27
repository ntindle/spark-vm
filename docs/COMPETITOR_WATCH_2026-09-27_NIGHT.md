# Competitor watch — 2026-09-27 (night)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the late-evening pass (#561, merged as `b6b8b5b`): (A)
fast-mover + pricing re-verification vs the ~09:24–09:27 CDT (2026-09-27)
baseline (vendor reads ~10:55–10:59 CDT 2026-09-27), (B) delta news scan
~09:29–~11:10 CDT (~100-min delta window; scan ran ~10:56–11:09 CDT; 8
search queries). Read-only, no logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1054.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1054.md`.

Naming-hygiene note: label rotation continues — `MORNING` → `LATE_MORNING` →
`MIDDAY` → `AFTERNOON` → `LATE_AFTERNOON` → `EVENING` → `LATE_EVENING` →
`NIGHT` (chains rotate, not stack; the label is a rotation counter, not a
wall-clock claim — this pass ran ~10:55–11:09 CDT). A further same-day
pass rotates again rather than reusing or POST_-stacking.

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: **C56 (DeepSeek Harness
CVE-2026-82533) drew zero mentions — quiet pass 3 of 3 — AGED OUT**
(one-notice line, per the pipeline). **C11 (Baseten/Blaxel) recrawl
contact — quiet count resets (not a quiet pass):** Surveyor B surfaced the
beri.net "Keeps Running pledge has no end date" acquisition commentary
(content dated Sept 24, pre-window; crawled ~06:00 CDT, pre-window) in this
pass's scan — a recrawl-mention of C11's subject, counted as contact under
the corrected-lineage standard (the late-evening review rejected treating
recrawl-mentions as quiet; what is in-window here is the surfacing, and the
discipline stays consistent). **C62 (OpenAI offline-sandbox escape) drew no
movement and no recrawl contact — quiet pass 1 of 3.** **C67 (Huawei Cloud
CodeArts Agent, Malaysia) drew in-window recrawl contact** (pocketnews.com.my
fresh details, yamchatime.com) — grade unchanged FIRST-PARTY-CORROBORATED;
not a quiet pass. C12 stays OPEN (AgentComputer still no egress line;
surveyor A vendor-verified, surveyor B zero mentions). Aged-out items:
**C66 silent** — stays out; Heapjack/Overpatch pre-window recaps only
(Sept 15–21), no in-window movement — stays out; GitLab CVE-2026-85706
zero mentions — stays out; Dextr AI zero mentions — stays out.

**P63 re-fold path (P66, drafted this pass — proposal, not yet adopted):**
an aged-out item returns to the corpus only on *real movement* — a new
vendor action, new launch/funding/GA/CVE, or a first-party confirmation —
never on recrawl of already-filed facts (recrawl with no new facts is
logged as "recrawl contact, no movement"; the item stays out). The pass
that observes real movement files a re-fold: reopens the C-number with a
one-line lineage note ("re-folded <date> after <movement>"), resets the
quiet count to 0, and treats it as OPEN going forward. This pass exercised
the "stays out" half for all five aged-out items; C56's age-out is the
first item the re-fold path will govern if it resurfaces. A future
strategy turn may adopt this draft into the P63 pipeline.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~10:55–10:59 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **10 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26
   2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS application").
   SEP 25 V0.217.0 ("NVIDIA B300 GPU type") still second; SEP 24
   V0.216.1/V0.216.2, SEP 23 V0.216.0 unchanged.
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22** (improved sandbox moves,
   private kit images); the 2026-09-21 v3-kits entry unchanged; 2026-09-15
   entry still present.
3. **Microsandbox releases** (`github.com/superradcompany/microsandbox/releases`)
   — newest still **v0.7.3** (#1646); full changelog v0.7.2...v0.7.3;
   v0.7.1, v0.7.0, v0.6.17, v0.6.14, v0.6.13 entries beneath unchanged.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September** (3 entries: VCR GitHub Action, Pixel Canary, Sandbox
   memory observability); no 26-Sep or 27-Sep entries in any lane.
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro $150/mo, Enterprise CUSTOM ($3,000/mo estimator floor), per-second
   billing table tops $0.000014/s per vCPU; concurrency tables intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans; xlarge $100+ plan gate); comparison +
   benchmark + active-CPU-billing sections unchanged.
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers
   (Starter/Builder/Power/Ultra, specs 2vCPU/4GB/40GB → 8vCPU/24GB/200GB),
   BYO-AI FAQ ("No. AI subscriptions and usage are not included.") intact.
8. **DigitalOcean harness-runtime pricing**
   (`digitalocean.com/pricing/harness-runtime`) — CPU $0.044/vCPU-hr,
   Memory $0.0095/GB-hr, egress $0.01/GiB, snapshots $0.05/GiB-month;
   25%-of-allocated active-CPU footnote intact.
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr, Hot $0.000683/Cold $0.000027, Enterprise custom tier
   present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass. Drives not re-checked per the out-of-scope
P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / 8 clean dedupes / 6 flagged-only

8 search queries (~09:29–~11:10 CDT delta window; scan ran ~10:56–11:09
CDT); every candidate grepped against the full watch-doc series (the new
canonical corpus leg — see the stale-version rule note below) + the corpus
before classification. No new in-window in-lane launches, pricing moves,
or fundings. No new C-numbers.

**Recrawl contact (existing item mentioned again, no new facts):** C67
(Huawei Cloud CodeArts Agent — pocketnews.com.my in-window recrawl with
fresh details: 16 specialized agents, 30+ reusable engineering skills,
3-month Early Bird Professional access; yamchatime.com Sept 25 — grade
unchanged, FIRST-PARTY-CORROBORATED); beri.net Baseten/Blaxel acquisition
commentary — counted as C11 recrawl contact in the aging section (see the
nuance there).

**8 clean dedupes** (all filed, no new facts): CVE-2026-100721 (vm2
<3.12.2, stackflag ~15h); CVE-2026-92937 (vm2 3.11.6, stackflag 1d);
CVE-2026-93603 (vm2 <3.12.1, stackflag 2d); BAND × Docker Sandboxes
integration (runtimewire, Sept 26); Docker Cloud Sandboxes launch (Sept
24/25, incl. Kits → CNCF Apache 2.0 handoff); Modal Labs $15B raise talks
(Sept 23); Perplexity "Escaping SPACE" Part I (Firecracker egress-policy
findings); CVE-2026-92940 stayed silent (no resurface — remains filed
flagged-only, never folded).

**6 flagged-only, NOT folded, no C-number** (new-to-corpus lane-adjacent or
pre-window):
1. **CVE-2026-53362 "Frag Gap"** (Linux kernel IPv6 OOB write, CVSS 7.8,
   CISA KEV — disclosure Aug 27, pre-window; fresher signal only a PoC
   README refresh ~Sept 25, still pre-window). Kernel-layer, in-lane-adjacent
   — noted as a corpus gap for the loop, not filed as new.
2. CVE-2026-21962 (Oracle WebLogic, CVSS 10.0) — out-of-lane, pre-window.
3. CVE-2026-60004 (Gitea <1.27.1 RCE, CVSS 9.8) — out-of-lane, pre-window.
4. CVE-2026-66384 (Docker cache path) — out-of-lane, pre-window.
5. Northflank vs Blaxel comparison blog (crawled ~5h ago) — marketing-grade
   comparison, pre-window; comparison write-up = flagged-only precedent.
6. dev.to/sourcetrail AI-exploitation recap pieces — recaps of older
   events, no new facts.

**Not counted:** CVE-2026-92937/92956/93605 vm2 series dedupes listed
above; own-corpus self-hits excluded.

Stale-version rule compliant: Surveyor B ran the dedupe against the FULL
120-doc series + COMPETITOR_ANALYSIS.md this pass — the first pass under
the new canonical corpus-leg definition (declared in COMPETITOR_ANALYSIS.md
Corpus conventions this PR). No false first-sightings.

## Corpus-health note for the series

This PR carries three of the review-filed hygiene items from #561's
advisories and the watch-series consolidation backlog entry:
1. **docs/README.md index rows lag closed** — the MIDDAY / LATE_AFTERNOON /
   EVENING / LATE_EVENING passes now have index rows (they were previously
   reachable only via the changelog or directory listing).
2. **Stale-version rule's corpus leg defined canonically** — the definition
   (every watch-pass doc + COMPETITOR_ANALYSIS.md + CHANGELOG.md; the
   README index is a map, not evidence) now lives in COMPETITOR_ANALYSIS.md
   "Corpus conventions" as the canonical home of the watch-process rules.
3. **P63 re-fold path drafted** in the aging section above (P66 clock
   fires this turn).

Remaining for a future strategy/meta turn per the consolidation item:
weekly-digest rows vs per-pass rows in the README, archiving quiet-pass
docs, committing the surveyor captures (they remain loop-workspace
working notes, referenced by path), and the third-party comparison
write-up section question.

## Verdict

**No new in-window in-lane launches this window; the sandbox-infrastructure
lane stays quiet.** Vendors: 9/9 unchanged; the all-first-try streak reaches
10 passes. News: 0 new, 8 clean dedupes, 6 flagged-only. New-to-corpus
sightings are all flagged-only lane-adjacent or pre-window items (kernel
"Frag Gap" CVE-2026-53362 noted as a corpus gap; WebLogic/Gitea/Docker
CVEs; Northflank-vs-Blaxel comparison; exploitation recaps). Corpus
movement: **C56 AGED OUT** (DeepSeek Harness CVE-2026-82533 — quiet pass 3
of 3, one-notice line above); C11 recrawl contact (count 0 — beri.net
acquisition commentary, counted under the corrected-lineage standard);
C62 quiet pass 1 of 3; C67 FIRST-PARTY-CORROBORATED, recrawl contact;
C12 OPEN; aged-out stay out (C66 silent; Heapjack/Overpatch pre-window
recaps only; GitLab CVE-2026-85706 zero; Dextr AI zero). C68 not opened.
