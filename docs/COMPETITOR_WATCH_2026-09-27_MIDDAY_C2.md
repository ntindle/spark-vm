# Competitor watch — 2026-09-27 (midday, cycle 2)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the late-morning cycle-2 pass (#570, merged as
`b0f7f87`): (A) fast-mover + pricing re-verification vs the ~11:58–12:02
CDT (2026-09-27) baseline (vendor reads ~12:27–12:29 CDT 2026-09-27),
(B) delta news scan ~12:20–~12:42 CDT (~22-min delta window; scan ran
~12:27–12:42 CDT; 12 search queries, ~45 results at snippet level).
Read-only, no logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1224.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1224.md`.

Naming-hygiene note: label rotation continues — `LATE_MORNING_C2` →
`MIDDAY` (cycle 2), per the rotation chains-rotate-don't-stack rule.
`MIDDAY` already names an earlier pass, so this file carries the cycle
disambiguator (`_C2`); the label remains a rotation counter, not a
wall-clock claim (this pass ran ~12:27–12:42 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied this
pass: **C62 (OpenAI offline-sandbox escape) recrawl contact again**
(gagadget, forkast.news DNS-loophole piece, deafnews.it,
intelligibberish.com daily roundup, iaexpertos.net, Mansour LinkedIn
pulse piece — all recrawls of the Sep-20 DNS-tunnel escape / Sep-25
training-pause story) — quiet count stays reset (0/3). **C11
(Baseten/Blaxel) recrawl contact** (dealroom.co, runtimewire.com, Business
Wire reprints, wsgr.com — a new outlet carrying the same Sep-10 facts —
pulse2.com, qainsights digest) — stays reset (0). **C67 (Huawei CodeArts
Agent, Malaysia) recrawl contact** (pocketnews.com.my Sep-27-dateline
follow-up with the same "16 specialised agents" + 3-month Early Bird
facts carried from the 1154 pass; yamchatime, malaysiasme, huawei.com
press page) — grade unchanged FIRST-PARTY-CORROBORATED; not a quiet
pass, no new launch facts. **C45 (Docker Cloud Sandboxes) recrawl
contact** (adtmag, webpronews, independent.mk / utv.ie press-release
reprints, merge.news, theregister with the Micro–XL rate card, docker.com
press page — all Sep-24/25 launch-wave recrawls, details already in the
corpus C45 row) — filed item, contact only. **C26 recrawl contact** —
C26 CLOSED; recrawl contact does not reopen. **C12 stays OPEN**:
AgentComputer pricing vendor-verified this pass (still no egress line) —
vendor contact, so not a quiet pass despite zero news mentions in the B
lane. **C56 (DeepSeek Harness CVE-2026-82533) stays aged out:**
dennysentinel and a hermes-tech digest recrawl the aged-out item — per
the P66 draft standard, recrawl contact with no new facts is NOT a
re-fold (real movement only: new vendor action, launch/funding/GA/CVE,
or first-party confirmation). Aged-out stay out: C66 silent,
Heapjack/Overpatch zero mentions, GitLab CVE-2026-85706 zero, Dextr AI
zero. No age-outs this pass; no re-folds.

No deep-scan leads filed this pass.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~12:27–12:29 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **13 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26
   2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"). SEP 25 V0.217.0 ("NVIDIA B300 GPU type") still second;
   SEP 24 V0.216.1/V0.216.2, SEP 23 V0.216.0 unchanged. No 27-Sep entry.
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22** (improved sandbox moves,
   private kit images); the 2026-09-21 v3-kits entry unchanged.
3. **Microsandbox releases** (`github.com/superradcompany/microsandbox/releases`)
   — newest still **v0.7.3** (#1646); entries beneath unchanged.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September**; no 26-Sep or 27-Sep entries in any lane.
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro **$150/mo**, Enterprise CUSTOM; per-second table tops **$0.000014/s**
   per vCPU; $3,000/mo Enterprise estimator floor intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans); comparison-table/benchmark/worked-examples
   sections still present (marketing content, no rate change).
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers
   (2/4/6/8 vCPU, 4/8/12/24 GB, 40/75/100/200 NVMe) intact; BYO-AI stance
   intact ("AI subscriptions and usage are not included").
8. **DigitalOcean harness-runtime pricing** (`digitalocean.com/pricing/harness-runtime`)
   — CPU $0.044/vCPU-hr, memory $0.0095/GB-hr, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots/checkpoints
   $0.05/GiB-month, BYOT $0.05/GiB-month; 25%-of-allocated active-CPU
   footnote intact. Capture-gap note (not a delta): the "Last verified 22
   Sep 2026" stamp noted in the baseline was not visible in this read —
   all figures match, so no movement.
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr memory, Hot $0.000683/Cold $0.000027 per GB-hr,
   Enterprise custom tier present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass. Drives not re-checked per the out-of-scope
P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / 12 clean dedupes & recrawl contacts / 9 flagged-only

12 search queries (~12:20–~12:42 CDT delta window; scan ran ~12:27–12:42
CDT; ~45 results at snippet level); every candidate grepped against the
full watch-doc series + the corpus before classification. No new
in-window in-lane launches, pricing moves, fundings, or sandbox-escape
CVEs. No new C-numbers — **C68 not opened**.

**Recrawl contacts / clean dedupes (all filed, no new facts):** C62
(gagadget, forkast.news, deafnews.it, intelligibberish.com,
iaexpertos.net, Mansour LinkedIn piece — all recrawls of the Sep-25
training-pause / Sep-20 DNS-escape story); C11 (dealroom.co,
runtimewire.com, Business Wire reprints, wsgr.com — new outlet, same
Sep-10 facts — pulse2.com, qainsights digest); C67 (pocketnews.com.my
Sep-27-dateline follow-up, yamchatime, malaysiasme, huawei.com — color
only, grade unchanged); C45 (adtmag, webpronews, independent.mk/utv.ie
reprints, merge.news, theregister Micro–XL rate card, docker.com press
page — Sep-24/25 launch-wave recrawls); C35-era Docker Sandboxes CVE pair
(CVE-2026-77179 / CVE-2026-79994 — thecybersecguru, aratech.ae,
thehackernews, Sep-15 advisory recrawls); CVE-2026-80521 (tech-insider.org
— filed AF_UNIX UAF container-escape, recrawl contact); CVE-2026-47686
(vm2 sandbox-escape RCE — 1dayexploit 1day-archive analysis, already
filed 2026-09-26); C56 (dennysentinel, rozkalnsandris hermes-tech digest —
recrawls of the aged-out item, not re-folded per P66); C26 (subagentic.ai,
forkast.news, releasebot.io, docs.digitalocean.com, bizwire reprints —
contact does not reopen); TermSquad Sep-15 always-on launch
(markets.financialcontent, myMotherLode, lifestyle.* outlets,
business.am-news — EINPresswire reprints, pre-window); Daytona
"agent-agnostic infrastructure" PR syndication
(pr.mysugarhousejournal, pr.millismedwaynews, pr.cottonwoodheightsjournal —
known old-PR recirculation, the 2026-09-25_EVENING anti-chase note
applies); Vercel Sandbox Drives (nandann.com — already deduped in the
1154 pass, filed Sep-23 public beta).

**9 flagged-only, NOT folded, no C-number** (pre-window, out-of-lane, or
no fresh movement): E2B pricing lifecycle recaps (dev.to/yuraoak + GitHub
comparison docs — third-party pricing recaps, no vendor-page change; C32
precedent: no fold); Microsandbox third-party items (orbitalab
rnd-ai-sandboxes security study, betalyra plans/sandbox.md,
wirenboard/agent-vm — third-party, pre-window; nothing newer than filed
v0.7.3); Daytona cost comparisons (codeongrass.com opinion piece, FirstMark
Guilds Summit YouTube interview — third-party, no vendor news);
AgentComputer bradvin/agentfirst.directory GitHub (2d — third-party
directory listing, no egress-policy movement); Forcepoint agent-cost
warning (techgig, Sep-25 — adjacent runaway-agent spend, not a product
story, out-of-lane); Microlink/OpenAI GET-only escape hatch (microlinkhq
blog, Sep-10 — pre-window, third-party vendor blog); Google Home MCP /
Google CC agent (techrepublic — consumer lane, out-of-lane); Daytona
GitHub mission-control doc (agentsystemlabs — third-party internal doc,
pre-window); AlexYedi field-guide spike (GitHub, 2d — third-party, no
vendor news).

Stale-version rule compliant: Surveyor B ran the dedupe against the full
series + COMPETITOR_ANALYSIS.md under the canonical corpus-leg
definition — no false first-sightings.

## Verdict

**No new in-window in-lane launches this window; the
sandbox-infrastructure lane stays quiet.** Vendors: 9/9 unchanged; the
all-first-try streak reaches 13 passes. News: 0 new, 12 recrawl
contacts/clean dedupes, 9 flagged-only. Corpus movement: C62 recrawl
wave continues — quiet count stays reset at 0/3; C11 stays reset (0);
C67 FIRST-PARTY-CORROBORATED, recrawl contact (color only); C26/C45
recrawl contact (no movement; C26 closed); C12 OPEN (vendor-verified
contact, still no egress line); C56 stays aged out (no re-fold —
recrawl of an aged-out item only); aged-out items stay out (C66 silent,
Heapjack/Overpatch zero mentions, GitLab CVE-2026-85706 zero, Dextr AI
zero). C68 not opened. The in-window news cycle was entirely recrawl;
the only hosted-agent launch in the corpus remains C67 (Sept 27,
first-party-corroborated).
