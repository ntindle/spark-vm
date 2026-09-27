# Competitor watch — 2026-09-27 (late evening, cycle 2)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the evening cycle-2 pass (#574, merged as
`4182c39d`): (A) fast-mover + pricing re-verification vs the ~13:31–13:35
CDT (2026-09-27) baseline (vendor reads ~13:56–13:59 CDT 2026-09-27),
(B) delta news scan ~13:40–~14:02 CDT (~22-min delta window; scan ran
~13:56–14:02 CDT; 10 search queries, ~62 results at snippet level).
Read-only, no logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1354.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1354.md`.

Naming-hygiene note: label rotation continues — `EVENING_C2` →
`LATE_EVENING` (cycle 2), per the rotation chains-rotate-don't-stack
rule. `LATE_EVENING` already names an earlier pass, so this file carries
the cycle disambiguator (`_C2`); the label remains a rotation counter,
not a wall-clock claim (this pass ran ~13:56–~14:02 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied this
pass: **C62 (OpenAI offline-sandbox escape / training-pause) recrawl
contact again** (the-decoder explainer, news.ssbcrack, jbiznews Fortune
syndication, technology-in-business.net video page, ianslive Sep-27 IANS
wire, LinkedIn pulse (Alexey Dvoryaninov), gagadget outlet recrawl — all
color from OpenAI's Sep-25 technical report, already filed, not new
facts) — quiet count stays reset (0/3). **C11 (Baseten/Blaxel) recrawl
contact** (beri.net long-form, already in corpus; same $7.3M seed +
25ms resume + 16 regions facts) — stays reset (0). **C67 (Huawei
CodeArts Agent, Malaysia) recrawl contact** (pocketnews.com.my
Sep-27-dateline follow-up, yamchatime.com, huawei.com Malaysia +
Singapore press pages, techedt 23d — same "16 specialised agents" +
3-month Early Bird facts; the Thailand OBT + "Agentic Infrastructure:
Now Available for Thailand" (thailand-business-news PRNewswire
syndication) is a regional-rollout leg of the same story, no new global
facts; tmtpost (GLM-5.0 / DeepSeek-V3.2 / Pangu / "zero data leakage"
claims) is a new-to-corpus outlet carrying the same story — color only)
— grade unchanged FIRST-PARTY-CORROBORATED; no new launch facts.
**C45 (Docker Cloud Sandboxes) recrawl contact** (independent.mk, utv.ie,
theeveningleader, folsomlocalnews, thepointnews, helpnetsecurity —
new-to-corpus outlet, Sep-25 dated, same launch facts — theregister
Micro $0.07/hr → XL $1.12/hr rate card already filed; all Sep-24/25
launch-wave recrawls, details already in the corpus C45 row) — filed
item, contact only. **CVE-2026-80521 recrawl contact** (deafnews.it,
tech-insider.org — filed AF_UNIX UAF container-escape; the Sep-22
DepthFirst exploit already filed) — no movement. **CVE-2026-77179
recrawl contact** (ricomanifesto/grcinsight Sep-18 GRC report —
new-to-corpus outlet, pre-window facts; filed Docker Sandboxes macOS
escape) — no new facts. **CVE-2026-47686 recrawl contact**
(1dayexploit 1day-archive GitHub README — new-to-corpus outlet; same
3.11.6 fix analysis, already filed) — no movement. **C26 not sighted**
(no contact either way this pass; closed, stays closed). **C12 not
sighted in B lane; stays OPEN** — AgentComputer pricing vendor-verified
this pass (still no egress line), so vendor contact, not a quiet pass.
**C56 (DeepSeek Harness CVE-2026-82533) not sighted this window** —
stays aged out. Aged-out stay out: C66 recrawl (thehackerwire automated
threat-intel page — not a re-fold per P66), Heapjack/Overpatch
pre-window recrawls (pranava0x0/vibe-coding-security GitHub advisory
Sep-24 pre-window, devops.com, daily.dev, hendryadrian, fudzilla,
bleepingcomputer, cybersecuritynews.com new-to-corpus outlet with
pre-window facts — all fixed-Aug-disclosure recrawls), GitLab
CVE-2026-85706 pre-window recrawls (cve.tools, cybrmonk,
zarguell/tia-n-list digest, pranava0x0, synthex Medium, core-jmp.org
+ PDF deep dive — same pre-window CVSS-10.0 facts), Dextr AI not
sighted. No age-outs this pass; no re-folds.

No deep-scan leads filed this pass. Watch-out for the next surveyor:
Hugo CVE-2026-100690 (new this window, held flagged-only) re-folds only
if a surveyor finds first-party corroboration or an agent-infra nexus.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~13:56–13:59 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **16 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26
   2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"). SEP 25 V0.217.0, SEP 24 V0.216.1/V0.216.2, SEP 23
   V0.216.0 unchanged. No 27-Sep entry.
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22**; the 2026-09-21 v3-kits
   entry unchanged.
3. **Microsandbox releases** (`github.com/superradcompany/microsandbox/releases`)
   — newest still **v0.7.3** (#1646); v0.7.2/v0.7.0 beneath unchanged.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September** (Container Registry OIDC, Pixel Canary, Sandbox
   memory observability); no 26-Sep or 27-Sep entries in any lane.
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro **$150/mo**, Enterprise CUSTOM; per-second table tops **$0.000014/s**
   per vCPU; $3,000/mo Enterprise estimator floor intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans; comparison table, active-CPU explainer,
   benchmark, worked examples all present).
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

## Surveyor B — delta news scan: 0 NEW / ~19 recrawl contacts & clean dedupes / ~12 flagged-only

10 search queries (~13:40–~14:02 CDT delta window; scan ran ~13:56–14:02
CDT; ~62 results at snippet level); every candidate grepped against the
full watch-doc series + the corpus before classification. No new
in-window in-lane launches, pricing moves, fundings, or sandbox-escape
CVEs. No new C-numbers — **C68 not opened**.

**Recrawl contacts / clean dedupes (all filed, no new facts):** C62
(the-decoder explainer, news.ssbcrack, jbiznews Fortune syndication,
IANS wire, technology-in-business.net video, LinkedIn pulse, gagadget
outlet recrawl — all color from OpenAI's Sep-25 report); C11 (beri.net
long-form — already in corpus, same Sep-10 facts); C67
(pocketnews Sep-27 follow-up, yamchatime, huawei.com Malaysia/Singapore
press pages, techedt; Thailand OBT PRNewswire syndication = regional
rollout leg; tmtpost new-to-corpus outlet, same story — color only,
grade unchanged); C45 (independent.mk, utv.ie, theeveningleader,
folsomlocalnews, thepointnews, helpnetsecurity new-to-corpus outlet,
theregister rate card — Sep-24/25 launch-wave recrawls); CVE-2026-80521
(deafnews.it, tech-insider.org — filed AF_UNIX UAF container-escape
recrawls); CVE-2026-77179 (ricomanifesto/grcinsight Sep-18 GRC report —
filed); CVE-2026-47686 (1dayexploit 1day-archive README — filed);
C66 (thehackerwire automated threat-intel page — aged-out recrawl, not
re-folded per P66); Heapjack/Overpatch pre-window recrawls (devops.com,
daily.dev, hendryadrian, fudzilla, bleepingcomputer,
pranava0x0/vibe-coding-security advisory Sep-24, cybersecuritynews.com
new-to-corpus outlet — all fixed-Aug-disclosure recrawls); GitLab
CVE-2026-85706 pre-window recrawls (cve.tools, cybrmonk,
zarguell/tia-n-list digest, pranava0x0, synthex Medium, core-jmp.org +
PDF deep dive — same pre-window CVSS-10.0 facts); TermSquad Sep-15
always-on launch (financialcontent reprints 1discountbrokerage,
cercescourier, q923radio, houstonnewstoday — pre-window reprints);
Daytona "agent-agnostic infrastructure" PR (pr.millismedwaynews.com +
smb.thepostsearchlight.com reprints, 2h crawl, old content — known
old-PR recirculation, the 2026-09-25 anti-chase note applies); Vercel
Sandbox Drives Sep-23 public-beta (nandann.com deep-dive — already in
corpus); Vercel $1M Sandbox Challenge (securityweek — already in
corpus); sandbox pricing comparisons (tokencost.app Agents-API pricing
table, marktechpost — already in corpus, rates unchanged); Upstash
`ai-agent-sandbox-providers-compared-2026` blog (C32 precedent —
third-party pricing recap, no fold); thomaspark20/actioner-examples
BlueMoon Chrome/Windows summary (adjacent-lane, pre-window);
spark-vm's own watch docs surfacing in search results (self-referential,
no signal).

**~12 flagged-only, NOT folded, no C-number** (pre-window, out-of-lane,
or no fresh movement): CVE-2026-100690 — Hugo symlink permission-model
sandbox bypass (TheHackerWire automated page, Sep 26) — a genuinely new
CVE (Hugo v0.161.0–v0.165.0, fixed v0.166.0, asset symlink → arbitrary
file read in builds), held flagged-only because it is lane-adjacent:
static-site-generator build-tool "sandbox," not agent-VM sandbox
infrastructure — direct precedent CVE-2026-55607 (flagged-only in the
2026-09-27 midday (cycle-1) pass); single automated aggregator, no first-party
Hugo/vendor corroboration in-corpus; CVE-2026-100721 — vm2
custom-resolver auth bypass (StackFlag, 18h) — midday (cycle-1) flagged-only, the
marginal-lane vm2 precedent (47686/92956/93603, all flagged-only)
holds; HarmonyOS-specific CodeArts agent (aibase.com — Huawei adjacent
lane, flagged-only precedent from the 1335 pass);
ryanalberts/best-of-agent-harnesses `sandboxed-code-execution.md`
(GitHub, updated 3d — third-party comparison, flagged-only precedent);
hezo-ai/hezo `.dev/container-backend-cost-comparison.md`
(new-to-corpus, 3d — third-party engineering cost doc; C32 precedent, no
vendor news); marcus-mok-gh/nova-cloud-computer `daytona-vs-e2b.md`
(third-party comparison; no vendor news); alexyedi
empire_state field-guide-spike-daytona (new-to-corpus — third-party
event doc, Feb $24M Series A recap; no vendor news);
benchflow-ai/benchflow integration-tests.md (third-party engineering
doc, Daytona release-gated; no vendor news); bytetitan-star/gameforge
copilot Daytona migration (2026-08-17 — pre-window third-party
engineering); simstudioai/sim PR #7184 (E2B/Daytona billing tracking —
flagged-only precedent from 1335); dev.to metered-sandbox cost-guard
post (flagged-only precedent from 1335); OpenAI Agents SDK sandbox
(sqmagazine, 164d) + Upstash software-factory blog (27d) + qovery blog
(22d, new-to-corpus) — pre-window third-party recaps; no vendor news.

Stale-version rule compliant: Surveyor B ran the dedupe against the full
series + COMPETITOR_ANALYSIS.md under the canonical corpus-leg
definition — no false first-sightings.

## Verdict

**No new in-window in-lane launches this window; the
sandbox-infrastructure lane stays quiet.** Vendors: 9/9 unchanged; the
all-first-try streak reaches 16 passes. News: 0 new, ~19 recrawl
contacts/clean dedupes, ~12 flagged-only. Corpus movement: C62 recrawl
wave continues — quiet count stays reset at 0/3; C11 stays reset (0);
C67 FIRST-PARTY-CORROBORATED, recrawl contact (color only); C45/C35-era
+ CVE-2026-80521 + CVE-2026-77179 + CVE-2026-47686 recrawl contact (no
movement; C26 not sighted, stays closed); C12 OPEN (vendor-verified
contact, still no egress line); C56 not sighted (stays aged out);
aged-out stay out (C66 recrawl not re-folded, Heapjack/Overpatch zero
movement, GitLab CVE-2026-85706 zero movement, Dextr AI zero movement).
C68 not opened. The in-window news cycle was entirely recrawl; the only
hosted-agent launch in the corpus remains C67 (Sept 27,
first-party-corroborated). The in-lane no-launch verdict dated
2026-09-25 stands — streak extends.
