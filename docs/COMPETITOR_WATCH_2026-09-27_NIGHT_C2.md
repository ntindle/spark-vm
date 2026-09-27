# Competitor watch — 2026-09-27 (night, cycle 2)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the late-evening cycle-2 pass (#575, merged as
`7fa624b`): (A) fast-mover + pricing re-verification vs the ~13:56–13:59
CDT (2026-09-27) baseline (vendor reads ~14:25–~14:28 CDT 2026-09-27),
(B) delta news scan ~14:02–~14:25 CDT (~23-min delta window; scan ran
~14:26–~14:44 CDT; 14 search queries, snippet level). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1424.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1424.md`.

Naming-hygiene note: label rotation continues — `LATE_EVENING_C2` →
`NIGHT` (cycle 2), per the rotation chains-rotate-don't-stack rule.
`NIGHT` already names an earlier pass (cycle-1), so this file carries the
cycle disambiguator (`_C2`); the label remains a rotation counter, not a
wall-clock claim (this pass ran ~14:25–~14:44 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied this
pass: **C62 (OpenAI offline-sandbox escape / training-pause) recrawl
contact again** (thejoai.com AP-wire color, findarticles.com CNN/AP
recrawl, techxplore, tradingview SeekingAlpha AP wire, particle.news ×2
in-place-canonical updates, thehindubusinessline Bloomberg syndication
Sep-27 10:51 AM, aiunderstanding.org canonical in-place update — all color
from OpenAI's Sep-25/26 disclosure, already filed, not new facts) —
quiet count stays reset (0/3). **C11 (Baseten/Blaxel) not sighted this
window** — quiet pass (1/3). **C67 (Huawei CodeArts Agent) recrawl
contact** (pocketnews.com.my Sep-27-dateline follow-up, yamchatime Sep-7
event color, malaysiasme.com.my new-to-corpus outlet Sep-18 recrawl,
techinasia HarmonyOS CodeArts upgrade — same "16 specialised agents" +
3-month Early Bird facts; no new launch facts) — grade unchanged
FIRST-PARTY-CORROBORATED. **C45 (Docker Cloud Sandboxes) recrawl contact**
(forkast.news Sep-26 analysis, new-to-corpus outlet for C45, same
Sep-24 launch facts — color only); vendor release-notes snippet confirms
newest heading still 2026-09-22 — matches baseline, no movement.
**CVE-2026-80521 recrawl contact** (cyberrecaps.com Sep-23 + Sep-24 daily
digests — filed AF_UNIX UAF container-escape; same DepthFirst Sep-22
exploit facts) — no movement. **CVE-2026-77179 recrawl contact**
(brocker.org 0.42.0 summary + dev.to five-CVE recap — same Sep-15 vendor
facts, fixed 0.42.0) — no movement. **C26 (DO Managed Agents, closed)
vendor-blog contact** (digitalocean.com/blog "The agent-first cloud: why
we built Managed Agents", ~2d old, pre-window — states $0.044/vCPU-hr,
$0.0095/GB-hr, snapshots $0.05/GiB-month — confirms the docs side of the
already-resolved snapshot-rate discrepancy; closed, stays closed).
**C56 (DeepSeek Harness CVE-2026-82533) aged-out recrawl contact**
(dennysentinel.com 12d, CSA lab research note 17d — aged-out stays out,
not re-folded per P66). **C12 not sighted in B lane; stays OPEN** —
AgentComputer pricing vendor-verified this pass (still no egress line),
so vendor contact, not a quiet pass. Aged-out stay out: C66 not sighted;
Heapjack/Overpatch not sighted; GitLab CVE-2026-85706 not sighted. No
age-outs this pass; no re-folds.

**Corpus-lead resolution (Surveyor B §3 lead):** CVE-2026-79994
(Docker Sandboxes guest-to-host AF_UNIX socket relay TOCTOU, CVSS 8.7,
fixed 0.42.0, records published Sep 15) surfaced fresh via the dev.to
"Five Docker Sandboxes CVEs this year" recap and the pranava0x0 advisory
— but the worker's corpus check shows **79994 is already filed**
(`docs/COMPETITOR_ANALYSIS.md` — filed as the 77179/79994 pair, corpus
rows + watch folds naming both) — dedupe, no fold.

No deep-scan leads filed this pass. Watch-out for the next surveyor:
Hugo CVE-2026-100690 (new this window, held flagged-only) re-folds only
if a surveyor finds first-party corroboration or an agent-infra nexus;
Mistral Vibe CVE-2026-87983…87988 (CVSS 9.2–10.0, published Sep 11,
fixed Vibe 2.25.4/2.19.1) stays flagged-only as pre-window marginal-lane
product vulns unless sandbox-infrastructure relevance emerges.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~14:25–~14:28 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **17 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26
   2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS application").
   SEP 25 V0.217.0, SEP 24 V0.216.1/V0.216.2, SEP 23 V0.216.0 beneath
   unchanged. No 27-Sep entry.
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22** ("Improved sandbox moves
   and support for private kit images in cloud sandboxes"); the
   2026-09-21 v3-kits entry unchanged.
3. **Microsandbox releases** (`github.com/superradcompany/microsandbox/releases`)
   — newest still **v0.7.3** (chore: release v0.7.3 #1646); v0.7.2 and
   v0.7.0 beneath unchanged. No v0.7.4.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September** (Container Registry OIDC, Pixel Canary, Sandbox
   memory observability); 24 Sep, 23 Sep (Drives public beta, still
   listed), 22 Sep lanes beneath unchanged. No 26-Sep or 27-Sep entries.
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro **$150/mo**, Enterprise CUSTOM; per-second table tops **$0.000014/s**
   per vCPU; $3,000/mo Enterprise estimator floor intact ("Enterprise
   requires $3,000/mo minimum").
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans; comparison table, active-CPU explainer,
   benchmark, worked examples all present).
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers
   (2/4/6/8 vCPU, 4/8/12/24 GB, 40/75/100/200 GB NVMe) intact; BYO-AI
   stance intact ("AI subscriptions and usage are not included.").
8. **DigitalOcean harness-runtime pricing** (`digitalocean.com/pricing/harness-runtime`)
   — CPU $0.044/vCPU-hr, memory $0.0095/GB-hr, session storage
   $0.05/GiB-month, public internet egress $0.01/GiB,
   snapshots/checkpoints $0.05/GiB-month, BYOT $0.05/GiB-month; 25%-of-
   allocated active-CPU footnote intact. Same capture-gap as baseline (the
   "Last verified 22 Sep 2026" stamp not visible in this read either —
   third consecutive pass; capture-gap, not a delta).
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr memory, Hot $0.000683/Cold $0.000027 per GB-hr,
   Enterprise custom tier present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass. Drives not re-checked per the out-of-scope
P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / recrawl contacts & clean dedupes / 10 flagged-only

14 search queries (~14:02–~14:25 CDT delta window; scan ran ~14:26–14:44
CDT; snippet level, zero pages opened — no genuinely-new first-party
claims surfaced); every candidate grepped against the full watch-doc
series + the corpus before classification. No new in-window in-lane
launches, pricing moves, fundings, or sandbox-escape CVEs. No new
C-numbers — **C68 not opened**.

**Recrawl contacts / clean dedupes (all filed, no new facts):** C62
(thejoai.com AP-wire color, findarticles.com CNN/AP recrawl, techxplore,
tradingview SeekingAlpha AP wire, particle.news ×2 in-place-canonical
updates, thehindubusinessline Bloomberg syndication Sep-27 10:51 AM,
aiunderstanding.org canonical in-place update — all color from OpenAI's
Sep-25/26 disclosure); C67 (pocketnews Sep-27 follow-up, yamchatime,
malaysiasme.com.my new-to-corpus outlet, techinasia HarmonyOS leg —
color only, grade unchanged); C45 (forkast.news Sep-26 analysis,
new-to-corpus outlet, same Sep-24 launch facts); C26 (digitalocean.com/blog
agent-first-cloud explainer, pre-window, confirms the docs side of the
resolved snapshot-rate discrepancy — closed, stays closed);
CVE-2026-80521 (cyberrecaps.com Sep-23 + Sep-24 digests — filed);
CVE-2026-77179 (brocker.org + dev.to five-CVE recap — filed); C56
(dennysentinel.com 12d, CSA lab note 17d — aged-out, not re-folded);
Vercel Sandbox Drives (nandann.com deep-dive — already in corpus;
gustavlrsn/mockintosh + imtiazrayhan/agentscamp third-party docs,
pre-window; changelog "Drives … now in public beta" — no GA movement);
Daytona / Microsandbox / E2B — no version bumps (no V0.219+ chatter, no
v0.7.4, no E2B news).

**Flagged-only (NOT folded):**

1. **CVE-2026-100690 (Hugo symlink permission-model sandbox bypass)** —
   NO first-party corroboration found. Only TheHackerWire automated page
   (already in corpus from the 1354 pass) + CVE aggregators; the
   gohugoio GHSA advisory that surfaced (GHSA-vrv5-r5rf-6v4j) is for the
   *earlier* sibling (CVE-2026-89258 family, fixed v0.165.0), not 100690.
   Stays flagged-only under the CVE-2026-55607 lane-adjacent precedent.
2. **CVE-2026-87983…87988 (Mistral Vibe permission bypasses, CVSS 4.0
   9.2–10.0, published Sep 11, fixed Vibe 2.25.4/2.19.1 per vendor
   advisory MAI-2026-003; HiddenLayer + SecMate researcher writeups)** —
   pre-window coding-agent *product* vulns, not sandbox infrastructure;
   surfacing now only via StackFlag (5d) / vuln-tracker recrawls.
   Marginal-lane precedent holds.
3. **CVE-2026-79994** — surfaced fresh via dev.to five-CVE recap +
   pranava0x0 advisory, but the worker's corpus check shows it is
   already filed (77179/79994 pair) — dedupe, no fold (see Corpus-lead
   resolution above).
4. **OpenAI DevDay "persistent AI agent codenamed O"** (ai-engineering-trend
   Medium 19h, cites TestingCatalog's Shabanov "inside source") —
   unconfirmed speculation. THIRD-PARTY.
5. **explainx.ai "Meta Muse: Personal Agent + Sentinel VM Security" (1d)**
   — third-party explainer of the Sep 8–9 consumer launch; out of lane
   (consumer agent) + pre-window launch. No in-window movement.
6. **Nscale $3.36B pre-IPO convertibles; Delos Data $100M (bitcoinversus
   19h)** — GPU/datacenter iron infra, out of lane.
7. **forkast "$435M enterprise agent security funding" (18d);
   gravity.fast Q3 funding tracker (Sep 21); Raindrop $50M Series A
   (Sep 17)** — adjacent-lane funding recaps, pre-window.
8. **codeongrass Daytona vs AgentBox vs DIY (12d)** — third-party
   comparison, pre-window.
9. **simstudioai/sim PR #7184 (E2B/Daytona billing tracking)** —
   flagged-only precedent from 1335, still open upstream work. No new
   facts.
10. **dev.to metered-sandbox cost-guard; upstash/termsquad pricing
    recaps** — not re-sighted this pass (no new third-party pricing
    chatter).

Stale-version rule compliant. In-lane no-launch verdict dated 2026-09-25
stands — streak extends.
