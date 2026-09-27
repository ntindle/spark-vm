# Competitor watch — 2026-09-27 (post-night, cycle 2)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the night cycle-2 pass (#576, merged as
`3b652b3`): (A) fast-mover + pricing re-verification vs the ~14:25–~14:28
CDT (2026-09-27) baseline (vendor reads ~14:55–~14:57 CDT 2026-09-27),
(B) delta news scan ~14:25–~14:55 CDT (~30-min delta window; scan ran
~14:56–~14:59 CDT; 16 search queries, snippet level, zero pages
opened — no genuinely-new first-party claims surfaced). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1454.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1454.md`.

Naming-hygiene note: label rotation continues — `NIGHT_C2` →
`POST_NIGHT` (cycle 2), per the rotation chains-rotate-don't-stack rule.
`POST_NIGHT` already names a 2026-09-26 pass, so this file carries the
cycle disambiguator (`_C2`); the label remains a rotation counter, not a
wall-clock claim (this pass ran ~14:55–~14:59 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied this
pass: **C62 (OpenAI offline-sandbox escape / training-pause) recrawl
contact again** (intelligibberish.com 19h, gagadget.com 19h,
tech-insider.org 19h, startupfortune.com 1d, deafnews.it 1d,
jbiznews.com 1d, particle.news — all same Sep-20 DNS-escape + Sep-25/26
disclosure, already filed, not new facts) — quiet count stays reset
(0/3). **C11 (Baseten/Blaxel) recrawl contact** (beri.net crawl 4h,
pulse2 crawl 1h — Sep-10 acquisition facts, already filed) — quiet
resets **1/3 → 0/3**. **C67 (Huawei CodeArts Agent) recrawl contact**
(pocketnews.com.my Sep-27 follow-up, yamchatime, malaysiasme,
techinasia HarmonyOS leg — same "16 specialised agents" + 3-month Early
Bird facts; no new launch facts) — grade unchanged
FIRST-PARTY-CORROBORATED. **C45 (Docker Cloud Sandboxes) recrawl
contact** (pranava0x0 vibe-coding-security advisory, aratech.ae,
thecybersecguru, dev.to "Five Docker Sandboxes CVEs" recap, THN,
severitydaily — same Sep-15 77179/79994 facts, fixed 0.42.0) — no
movement. **CVE-2026-77179 + CVE-2026-79994 recrawl contact** (same
recrawls); corpus check CLOSED — 79994 appears in 38 corpus files (counted at the 1424 pass's base) (the
1424 pass's "surfaced fresh" worry was moot; already filed, dedupe
confirmed). **CVE-2026-92122 (Jenkins) + CVE-2026-63587 (VMware ESXi)
recrawl contact** — already filed (pre-window/out-of-lane), no
movement. **Daytona V0.218.0 top entry already filed** (no V0.219+
chatter). **Microsandbox v0.7.3 vendor-verified** (snippet-level "v0.7.1
newest" chatter contradicts the vendor releases page — vendor page
authoritative). **C26 (DO Managed Agents, closed)** — no movement
(OpenAI Agents API partner-list mentions only, pre-window); closed,
stays closed. **C56 (DeepSeek Harness CVE-2026-82533) aged-out recrawl
contact** (CSA labs research note, devops.com FAQ — aged-out stays out,
not re-folded per P66). **C12 not sighted in B lane; stays OPEN** —
AgentComputer pricing vendor-verified this pass (still no egress line),
so vendor contact, not a quiet pass. Aged-out stay out: C66 not
sighted; Heapjack/Overpatch not sighted; GitLab CVE-2026-85706 not
sighted. No age-outs this pass; no re-folds.

**Corpus-gap note (Surveyor B deep-scan lead, NOT folded — pre-window):**
dev.to's "Five Docker Sandboxes CVEs this year" recap surfaces three
Docker Sandboxes CVEs missing from the corpus — CVE-2026-12039,
CVE-2026-12539 (June 2026), CVE-2026-18171 (August 2026), per the
dev.to recap all in Docker's README-sold controls (embedded DNS server,
ICMP egress authorizer, virtio-fs host server; 79994 is the socket-relay
TOCTOU sibling). Pre-window, so flagged-only under the NEW rule — but
in-lane, vendor-disclosed agent-sandbox CVEs; natural pre-window fold
line-item for C45's CVE family if a future surveyor wants corpus
completeness.

No other deep-scan leads filed this pass. Watch-out for the next
surveyor: (1) Hugo CVE-2026-100690 — TheHackerWire's automated page
re-ingested Sep 26 14:16; re-folds ONLY on a gohugoio GHSA for 100690
specifically (the surfaced GHSA-vrv5-r5rf-6v4j covers the earlier sibling
89258) or an agent-infra nexus — worth one more first-party check.
(2) Mistral Vibe CVE-2026-87983…87988 stays flagged-only as pre-window
marginal-lane product vulns. (3) dev.to 2026 sandbox comparison
(E2B/Daytona/Modal/Vercel per-vCPU table, new-to-corpus outlet,
third-party, pre-window facts) — possible deep-scan pricing-shape input,
lane-adjacent only.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~14:55–~14:57 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **18 passes**.

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
   fourth consecutive pass; capture-gap, not a delta).
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr memory, Hot $0.000683/Cold $0.000027 per GB-hr,
   Enterprise custom tier present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass. Drives not re-checked per the out-of-scope
P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / 15 recrawl contacts / 8 flagged-only

16 search queries (~14:25–~14:55 CDT delta window; scan ran ~14:56–~14:59
CDT; snippet level, zero pages opened — no genuinely-new first-party
claims surfaced); every candidate grepped against the full watch-doc
series + the corpus before classification. No new in-window in-lane
launches, pricing moves, fundings, or sandbox-escape CVEs. No new
C-numbers — **C68 not opened**.

**Recrawl contacts / clean dedupes (all filed, no new facts):** C62
(continued wave — intelligibberish, gagadget, tech-insider, startupfortune,
deafnews, jbiznews, particle.news; quiet stays 0/3); C67 (pocketnews
Sep-27 follow-up, yamchatime, malaysiasme, techinasia HarmonyOS leg —
color only, grade unchanged); C11 (beri.net crawl 4h, pulse2 crawl 1h —
Sep-10 acquisition recrawls; quiet RESET 1/3 → 0/3); C45 (pranava0x0,
aratech, thecybersecguru, dev.to five-CVEs recap, THN, severitydaily —
same Sep-15 77179/79994 facts); CVE-2026-77179 + CVE-2026-79994 (filed —
79994 in 38 corpus files (counted at the 1424 pass's base), corpus check closed); CVE-2026-92122
(Jenkins, filed); CVE-2026-63587 (VMware ESXi, filed, out-of-lane);
Daytona (V0.218.0 top entry filed, no V0.219+); Microsandbox (v0.7.3
vendor-verified, bump PRs pre-window/filed); E2B (no movement); Vercel
Sandbox (no Drives beta→GA movement); TermSquad (Sep-15 EINPresswire
syndication recrawls only); C26 (partner-list mentions only, closed
stays closed); C12 not sighted in-lane (stays OPEN); C56 (CSA labs +
devops.com recrawls, aged-out, not re-folded).

**Flagged-only (NOT folded):**

1. **CVE-2026-100690 (Hugo symlink permission-model sandbox bypass)** —
   TheHackerWire automated page recrawled (crawl 9h); NO first-party
   corroboration found (the gohugoio GHSA that surfaced covers the
   *earlier* sibling 89258, fixed v0.165.0). Stays flagged-only under
   the CVE-2026-55607 lane-adjacent precedent; re-folds only on a 100690-
   specific GHSA or an agent-infra nexus.
2. **OpenAI DevDay "agent O" rumor** (alextech.ai 19h, vibingtalk 1d,
   YouTube leak video 1d) — unconfirmed speculation ahead of DevDay
   (Sep 29). THIRD-PARTY.
3. **Guava "Daytona" voice model** (Sep 23 press release) — name
   collision; voice-AI product, out of lane.
4. **GhostApproval (Wiz, ~July)** — symlink attacks on Claude Code /
   Cursor / Copilot-style coding agents; agent-sandbox-adjacent but
   pre-window (80d), not new. Flagged-only.
5. **CVE-2026-87983…87988 (Mistral Vibe permission bypasses)** — in
   corpus; no in-window movement. Pre-window marginal-lane product vulns.
6. **dev.to builder pieces** (Bivack 6d, solon-ai-sandbox 13d, AltairAgent
   19h) — lane-adjacent, third-party, pre-window or out-of-scope.
7. **dev.to "Sandboxing AI-Generated Code: E2B vs Vercel Sandbox vs Modal
   vs Daytona in 2026" (19h)** — new-to-corpus outlet but third-party
   comparison over pre-window facts. Flagged-only.
8. **Chrome/VMware/Jenkins CVE clusters** — already filed or out-of-lane.

Stale-version rule compliant. In-lane no-launch verdict dated 2026-09-25
stands — streak extends.
