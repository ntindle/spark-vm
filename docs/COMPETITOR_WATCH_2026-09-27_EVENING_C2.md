# Competitor watch — 2026-09-27 (evening, cycle 2)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the afternoon cycle-2 pass (#573, merged as
`612cb97e`): (A) fast-mover + pricing re-verification vs the ~12:56–13:00
CDT (2026-09-27) baseline (vendor reads ~13:31–13:35 CDT 2026-09-27),
(B) delta news scan ~13:05–~13:40 CDT (~35-min delta window; scan ran
~13:28–13:40 CDT; 10 search queries, ~55 results at snippet level).
Read-only, no logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1335.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1335.md`.

Naming-hygiene note: label rotation continues — `AFTERNOON_C2` →
`EVENING` (cycle 2), per the rotation chains-rotate-don't-stack rule.
`EVENING` already names an earlier pass, so this file carries the cycle
disambiguator (`_C2`); the label remains a rotation counter, not a
wall-clock claim (this pass ran ~13:31–~13:40 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied this
pass: **C62 (OpenAI offline-sandbox escape / training-pause) recrawl
contact again** (the-decoder.com explainer, news.ssbcrack.com,
jbiznews.com Fortune syndication, technology-in-business.net video page,
ianslive.in IANS wire Sep-27 dateline, LinkedIn pulse, startupfortune.com
— the monitoring-stack detail ("activation classifiers, 30-min
detection-to-alert target, +20% inference compute") is color from OpenAI's
Sep-25 technical report, already filed, not a new fact) — quiet count
stays reset (0/3). **C11 (Baseten/Blaxel) recrawl contact**
(urallnews, newslocker — new outlets, same Sep-10 facts) — stays reset
(0). **C67 (Huawei CodeArts Agent, Malaysia) recrawl contact**
(pocketnews.com.my Sep-27-dateline follow-up with the same "16
specialised agents" + 3-month Early Bird facts, yamchatime.com,
huawei.com Malaysia + Singapore press pages, techedt Singapore piece 23d
old — color only) — grade unchanged FIRST-PARTY-CORROBORATED; no new
launch facts. **C45 (Docker Cloud Sandboxes) recrawl contact** (adtmag,
lifestyle.independent.mk, theeveningleader, folsomlocalnews, utv.ie,
docker.com press page, theregister Micro–XL rate card crawled <1h ago —
all Sep-24/25 launch-wave recrawls, details already in the corpus C45
row) — filed item, contact only. **C35-era recrawl contact**
(CVE-2026-77179 thehackernews Sep-17 piece — filed Docker Sandboxes macOS
escape; the C35-era CVE pair implicitly in coverage) — no movement.
**CVE-2026-80521 recrawl contact** (deafnews.it, realhacker.news,
tech-insider.org — filed AF_UNIX UAF container-escape). **C26 not
sighted** (no contact either way this pass; closed, stays closed).
**C12 not sighted in B lane; stays OPEN** — AgentComputer pricing
vendor-verified this pass (still no egress line), so vendor contact, not
a quiet pass. **C56 (DeepSeek Harness CVE-2026-82533) stays aged out**
(labs.cloudsecurityalliance.org CSA research-note recrawl — not a
re-fold per P66). Aged-out stay out: C66 recrawl (thehackerwire
automated threat-intel page — not a re-fold per P66),
Heapjack/Overpatch pre-window recrawls (devops.com, grabtheaxe.com,
daily.dev, hendryadrian.com, fudzilla.com, bleepingcomputer.com, plus a
new outlet this window: pranava0x0/vibe-coding-security GitHub advisory,
Sep-24 pre-window — all fixed-Aug-disclosure recrawls), GitLab
CVE-2026-85706 pre-window recrawls (cve.tools Sep-18 piece, deafnews.it,
exploit-arsenal README, LinkedIn pulse, core-jmp.org Pruva deep-dive,
pruva.dev REPRO-2026-00354 — same pre-window facts), Dextr AI not
sighted. No age-outs this pass; no re-folds.

No deep-scan leads filed this pass.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~13:31–13:35 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **15 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26
   2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"). SEP 25 V0.217.0 ("NVIDIA B300 GPU type") still second;
   SEP 24 V0.216.1/V0.216.2, SEP 23 V0.216.0 unchanged. No 27-Sep entry.
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22** (improved sandbox moves,
   private kit images); the 2026-09-21 v3-kits entry unchanged.
3. **Microsandbox releases** (`github.com/superradcompany/microsandbox/releases`)
   — newest still **v0.7.3** (#1646, "chore: release v0.7.3"); beneath it
   v0.7.2/v0.7.0 entries unchanged.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September** (Container Registry OIDC login, Pixel Canary on AI
   Gateway, Sandbox memory observability); no 26-Sep or 27-Sep entries in
   any lane.
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro **$150/mo**, Enterprise CUSTOM; per-second table tops **$0.000014/s**
   per vCPU; $3,000/mo Enterprise estimator floor intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans; comparison table, active-CPU billing
   explainer, benchmark, worked examples all present).
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers
   (2/4/6/8 vCPU, 4/8/12/24 GB, 40/75/100/200 NVMe) intact; BYO-AI stance
   intact ("AI subscriptions and usage are not included").
8. **DigitalOcean harness-runtime pricing** (`digitalocean.com/pricing/harness-runtime`)
   — CPU $0.044/vCPU-hr, memory $0.0095/GB-hr, session storage
   $0.05/GiB-month, egress $0.01/GiB, snapshots/checkpoints
   $0.05/GiB-month, BYOT $0.05/GiB-month; 25%-of-allocated active-CPU
   footnote intact. Same capture-gap as baseline (the "Last verified 22
   Sep 2026" stamp not visible in this read either) — capture-gap, not a
   delta.
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr memory, Hot $0.000683/Cold $0.000027 per GB-hr,
   Enterprise custom tier present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass. Drives not re-checked per the out-of-scope
P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / ~17 recrawl contacts & clean dedupes / ~9 flagged-only

10 search queries (~13:05–~13:40 CDT delta window; scan ran ~13:28–13:40
CDT; ~55 results at snippet level); every candidate grepped against the
full watch-doc series + the corpus before classification. No new
in-window in-lane launches, pricing moves, fundings, or sandbox-escape
CVEs. No new C-numbers — **C68 not opened**.

**Recrawl contacts / clean dedupes (all filed, no new facts):** C62
(the-decoder.com explainer, news.ssbcrack.com, jbiznews.com, IANS wire,
technology-in-business.net video, LinkedIn pulse, startupfortune.com —
monitoring-stack detail is color from OpenAI's Sep-25 report); C11
(urallnews, newslocker — new outlets, same Sep-10 facts); C67
(pocketnews Sep-27 follow-up, yamchatime, huawei.com Malaysia/Singapore
press pages, techedt — color only, grade unchanged); C45 (adtmag,
independent.mk, theeveningleader, folsomlocalnews, utv.ie, docker.com
press page, theregister — Sep-24/25 launch-wave recrawls); CVE-2026-80521
(deafnews.it, realhacker.news, tech-insider.org — filed AF_UNIX UAF
container-escape recrawls); CVE-2026-77179 (thehackernews Sep-17 —
filed); C35-era Docker CVE pair (implicit in thehackernews coverage);
C66 (thehackerwire automated threat-intel page — aged-out recrawl, not
re-folded per P66); Heapjack/Overpatch pre-window recrawls (devops.com,
grabtheaxe, daily.dev, hendryadrian, fudzilla, bleepingcomputer,
pranava0x0/vibe-coding-security advisory Sep-24); GitLab CVE-2026-85706
pre-window recrawls (cve.tools, deafnews.it, exploit-arsenal README,
LinkedIn pulse, core-jmp.org Pruva deep-dive, pruva.dev REPRO-2026-00354);
C56 DeepSeek CVE-2026-82533 (labs.cloudsecurityalliance.org CSA research
note — aged-out recrawl, not re-folded); TermSquad Sep-15 always-on
launch (financialcontent reprints 1discountbrokerage, cercescourier,
q923radio, houstonnewstoday — pre-window reprints); Daytona
"agent-agnostic infrastructure" PR (nova-cloud-computer daytona-vs-e2b.md
GitHub doc — known old-PR recirculation, the 2026-09-25 anti-chase note
applies); spark-vm's own watch docs surfacing in search results
(self-referential, no signal); Windows Sept-2026 LPE pair
CVE-2026-85880/81963 (offsitedarklabs GitHub news note — adjacent lane,
pre-window); Chrome V8 sandbox escapes CVE-2026-85046/87491
(thomaspark20 GitHub summary — adjacent browser lane, pre-window);
EponaLab/ai-news 2026-09-11 digest (OpenAI Agents API beta — pre-window,
filed-era context).

**~9 flagged-only, NOT folded, no C-number** (pre-window, out-of-lane, or
no fresh movement): Transluce AI crypto-exchange-hack claim (inside the
ssbcrack piece — "may have been attempts by OpenAI's model to hack a
cryptocurrency exchange"; OpenAI has not commented — already in corpus
2026-09-25/26 docs; speculative third-party assertion, no vendor
corroboration); ryanalberts/best-of-agent-harnesses
comparisons/sandboxed-code-execution.md (GitHub, updated 3d —
third-party comparison; flagged-only precedent); Upstash
`ai-agent-sandbox-providers-compared-2026` blog + mdx (Sep-17 —
third-party pricing recap; C32 precedent); rappdw/sandy
`sandbox-landscape-2026-07.md` (6d old — third-party recap; C32
precedent); linda-mhmd/ai-solutions-wiki e2b-vs-daytona-vs-modal.md
(third-party comparison; flagged-only precedent); simstudioai/sim PR
#7184 (E2B/Daytona billing tracking — third-party engineering doc; no
vendor news); dev.to metered-sandbox cost-guard post (third-party
engineering; no vendor news); MEXC "The Sandbox" metaverse layoffs
(metaverse gaming, out-of-lane, name collision); HarmonyOS-specific
CodeArts agent (aibase.com — Huawei adjacent coding-app lane, not
sandbox infra).

Stale-version rule compliant: Surveyor B ran the dedupe against the full
series + COMPETITOR_ANALYSIS.md under the canonical corpus-leg
definition — no false first-sightings.

## Verdict

**No new in-window in-lane launches this window; the
sandbox-infrastructure lane stays quiet.** Vendors: 9/9 unchanged; the
all-first-try streak reaches 15 passes. News: 0 new, ~17 recrawl
contacts/clean dedupes, ~9 flagged-only. Corpus movement: C62 recrawl
wave continues — quiet count stays reset at 0/3; C11 stays reset (0);
C67 FIRST-PARTY-CORROBORATED, recrawl contact (color only); C45/C35-era
recrawl contact (no movement; C26 not sighted, stays closed); C12 OPEN
(vendor-verified contact, still no egress line); C56 stays aged out (CSA
recrawl — not a re-fold); aged-out stay out (C66 recrawl not re-folded,
Heapjack/Overpatch zero movement, GitLab CVE-2026-85706 zero movement,
Dextr AI zero movement). C68 not opened. The in-window news cycle was
entirely recrawl; the only hosted-agent launch in the corpus remains C67
(Sept 27, first-party-corroborated). The in-lane no-launch verdict dated
2026-09-25 stands — streak extends.
