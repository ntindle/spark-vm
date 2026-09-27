# Competitor watch — 2026-09-27 (predawn, cycle 2)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the post-night cycle-2 pass (#577, merged as
`c17047f`): (A) fast-mover + pricing re-verification vs the ~14:55–~14:57
CDT (2026-09-27) baseline (vendor reads ~15:26–~15:27 CDT 2026-09-27),
(B) delta news scan ~14:55–~15:25 CDT (~30-min delta window; scan ran
~15:26–~15:37 CDT; 16 search queries, snippet level, zero pages
opened — no genuinely-new first-party claims surfaced). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1524.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1524.md`.

Naming-hygiene note: label rotation continues — `POST_NIGHT_C2` →
`PREDAWN` (cycle 2), mirroring cycle 1 (the 2026-09-26 series closed with
`POST_NIGHT`, and the 2026-09-27 series opened with `PREDAWN`).
`PREDAWN` already names a 2026-09-27 pass, so this file carries the
cycle disambiguator (`_C2`); the label remains a rotation counter, not a
wall-clock claim (this pass ran ~15:26–~15:37 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied this
pass: **C62 (OpenAI offline-sandbox escape / training-pause) recrawl
contact again** (gagadget 20h, tech-insider 20h, intelligibberish 20h,
particle.news 1d, startupfortune 1d, the420.in — new outlet, same Sep-20
DNS-escape + Sep-25/26 disclosure, already filed, no new facts) — quiet
count stays reset (0/3). **C11 (Baseten/Blaxel) recrawl wave** (beri.net
crawl <1h, pulse2 crawl 1h, techdefused 2h, techintelpro 3h, runtimewire
2h, morningstar BusinessWire syndication — same Sep-10 acquisition
facts, already filed) — quiet stays reset (0/3). **C67 (Huawei CodeArts
Agent) recrawl contact** (pocketnews.com.my Sep-27 follow-up crawl <1h,
yamchatime 3h, malaysiasme 2h, itbrief.asia <1h — same Malaysia
commercial-launch facts; no new launch facts) — grade unchanged
FIRST-PARTY-CORROBORATED, 0/3. **C45 (Docker Cloud Sandboxes) recrawl
contact** (pranava0x0 vibe-coding-security advisory — color: the same
0.42.0 advisory also shipped two non-CVE fixes, host D-Bus command exec
and sandbox OAuth-login hijack, already filed; thecybersecguru 10h,
dev.to "Five Docker Sandboxes CVEs" 2d, brocker.org, docs.docker.com
release notes — same Sep-15 77179/79994 facts, fixed 0.42.0, no
exploitation) — no movement. **CVE-2026-77179 + CVE-2026-79994 recrawl
contact** (same recrawls); no new CVE in the family. **CVE-2026-92122
(Jenkins) + CVE-2026-63587 (VMware ESXi)** — no movement this window;
filed, stay filed. **Daytona V0.218.0 top entry already filed** (no
V0.219+ chatter). **Microsandbox v0.7.3 vendor-verified** (snippet-level
"v0.7.1 newest" chatter contradicts the vendor releases page — vendor
page authoritative, per prior convention). **Vercel Sandbox** — no Drives
beta→GA movement. **TermSquad** — launch-press recrawls only (Sep-15
syndication); pricing tiers unchanged in prior VERIFIED reads.
**E2B** — no version/pricing movement. **C26 (DO Managed Agents,
closed)** — no movement; closed, stays closed. **C56 (DeepSeek Harness
CVE-2026-82533) aged-out recrawl contact** (CSA labs research note,
dennysentinel, devops.com FAQ, techtimes DSec reward-hacking recap —
aged-out stays out, not re-folded per P66). **C12 not sighted in B
lane; stays OPEN** — AgentComputer pricing vendor-verified this pass
(still no egress line), so vendor contact, not a quiet pass. Aged-out
stay out: C66 not sighted; Heapjack/Overpatch not sighted as new
movement; GitLab CVE-2026-85706 not sighted. No age-outs this pass; no
re-folds.

**Corpus-gap note (carried from prior passes, NOT folded —
pre-window):** dev.to's "Five Docker Sandboxes CVEs this year" recap
surfaces three Docker Sandboxes CVEs missing from the corpus —
CVE-2026-12039, CVE-2026-12539 (June 2026), CVE-2026-18171 (August 2026),
all in Docker's README-sold controls (embedded DNS server, ICMP egress
authorizer, virtio-fs host server; 79994 is the socket-relay TOCTOU
sibling). Pre-window, so flagged-only under the NEW rule — but in-lane,
vendor-disclosed agent-sandbox CVEs; natural pre-window fold line-item
for C45's CVE family if a future surveyor wants corpus completeness.

No other deep-scan leads filed this pass. Watch-out for the next
surveyor: (1) Hugo CVE-2026-100690 — TheHackerWire's page re-ingested
Sep 26 14:16 again this pass; re-folds ONLY on a gohugoio GHSA for
100690 specifically (GHSA-vrv5-r5rf-6v4j covers the earlier sibling
89258; GHSA-8j34-9876-pvfq seen for an even-older CVE — neither is
100690) or an agent-infra nexus — worth one more
gohugoio/security/advisories check next pass. (2) OpenAI DevDay "agent
O" always-on-agent rumor is INTENSIFYING across new-to-corpus outlets
(Medium ai-engineering, wccftech, kucoin, tokenpost, siliconsnark —
all echoing testingcatalog's Sep-26 report); still UNCONFIRMED
(OpenAI has not confirmed). DevDay is Tue Sep 29 — the next-turn
surveyors should check the DevDay outcome; a confirmed always-on OpenAI
agent with email identity and long-running tasks would be C68-candidate
material (most in-lane event of the week, directly adjacent to
spark-vm's always-on positioning). (3) Mistral Vibe CVE-2026-87983…87988
stays flagged-only as pre-window marginal-lane product vulns. (4) dev.to
2026 sandbox comparison (E2B/Daytona/Modal/Vercel per-vCPU table,
new-to-corpus outlet, third-party, pre-window facts) — possible
deep-scan pricing-shape input, lane-adjacent only.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~15:26–~15:27 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **19 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26
   2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"). SEP 25 V0.217.0, SEP 24 V0.216.1/V0.216.2, SEP 23
   V0.216.0 beneath unchanged. No 27-Sep entry.
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
   per vCPU.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans; credit-based, non-expiring $20 packs).
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers
   (2/4/6/8 vCPU, 4/8/12/24 GB, 40/75/100/200 GB NVMe) intact; BYO-AI
   stance intact ("AI subscriptions and usage are not included.").
8. **DigitalOcean harness-runtime pricing** (`digitalocean.com/pricing/harness-runtime`)
   — CPU $0.044/vCPU-hr, memory $0.0095/GB-hr, session storage
   $0.05/GiB-month, public internet egress $0.01/GiB,
   snapshots/checkpoints $0.05/GiB-month, BYOT $0.05/GiB-month; 25%-of-
   allocated active-CPU footnote intact. Same capture-gap as baseline (the
   "Last verified 22 Sep 2026" stamp not visible in this read either —
   fifth consecutive pass; capture-gap, not a delta).
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr memory, Hot $0.000683/Cold $0.000027 per GB-hr,
   Enterprise custom tier present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass. Drives not re-checked per the out-of-scope
P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / 15 recrawl contacts / 9 flagged-only

16 search queries (~14:55–~15:25 CDT delta window; scan ran ~15:26–~15:37
CDT; snippet level, zero pages opened — no genuinely-new first-party
claims surfaced); every candidate grepped against the full watch-doc
series + the corpus before classification. No new in-window in-lane
launches, pricing moves, fundings, or sandbox-escape CVEs. No new
C-numbers — **C68 not opened**.

**Recrawl contacts / clean dedupes (all filed, no new facts):** C62
(continued wave — gagadget, tech-insider, intelligibberish,
particle.news, startupfortune, the420.in new outlet; quiet stays 0/3);
C67 (pocketnews Sep-27 follow-up, yamchatime, malaysiasme, itbrief.asia —
color only, grade unchanged FIRST-PARTY-CORROBORATED, 0/3); C11 (beri.net,
pulse2, techdefused, techintelpro, runtimewire, morningstar BusinessWire
syndication — same Sep-10 acquisition facts; quiet stays reset 0/3); C45
(pranava0x0 same-advisory color, thecybersecguru, dev.to five-CVEs
recap, brocker.org, docs.docker.com release notes — same Sep-15
77179/79994 facts); CVE-2026-77179 + CVE-2026-79994 (filed — no new CVE
in the family); CVE-2026-92122 (Jenkins, filed, no movement);
CVE-2026-63587 (VMware ESXi, filed, out-of-lane, no movement); Daytona
(V0.218.0 top entry filed, no V0.219+); Microsandbox (v0.7.3
vendor-verified); E2B (no movement); Vercel Sandbox (no Drives beta→GA
movement); TermSquad (Sep-15 syndication recrawls only); C26 (no
movement, closed stays closed); C12 not sighted in-lane (stays OPEN);
C56 (CSA labs + dennysentinel + devops.com + techtimes recrawls,
aged-out, not re-folded); Docker Cloud Sandboxes pricing (how2shout
recrawl, in 7 corpus files — $250 free credit, no movement).

**Flagged-only (NOT folded):**

1. **CVE-2026-100690 (Hugo symlink permission-model sandbox bypass)** —
   TheHackerWire page re-ingested (crawl 9h, "New CVE Received Sep 26,
   2026 14:16" — same content); STILL no first-party corroboration of
   100690 itself (GHSA-vrv5-r5rf-6v4j covers the earlier sibling 89258;
   GHSA-8j34-9876-pvfq covers an even-older CVE). Stays flagged-only;
   re-folds only on a 100690-specific gohugoio GHSA or an agent-infra
   nexus.
2. **OpenAI DevDay "agent O" always-on-agent rumor — INTENSIFYING** —
   new-to-corpus outlets this window (Medium ai-engineering 20h, wccftech
   1d, kucoin 20h, tokenpost 20h, siliconsnark 18h, YouTube leak video)
   all echoing testingcatalog's Sep-26 report (Tibo "o yes… we're back"
   quote, Pro-page "o, your always-on assistant" sighting, Aeon =
   Gpt-6-Astra-variant speculation, $500 Pro Max rumor). Corpus already
   holds the rumor (testingcatalog, NIGHT_C2). STILL UNCONFIRMED — OpenAI
   has not confirmed "O" or Aeon; DevDay Sep 29 (Tue). Flagged-only —
   the Sep-29 slots should check the DevDay outcome.
3. **Guava "Daytona" voice model launch** (Sep 23 press release,
   businesswire + syndication) — name collision; voice-AI product, out
   of lane.
4. **GhostApproval (Wiz, ~80d)** — surfaced again in Hugo query results;
   agent-sandbox-adjacent but pre-window. Flagged-only.
5. **OpenAI Codex Overpatch/Heapjack** (cybersecuritynews.com, 6d) —
   surfaced in Hugo query; filed/corpus precedent, pre-window
   (Aug-12 report). Flagged-only.
6. **CVE-2026-87983…87988 (Mistral Vibe permission bypasses)** — no
   in-window movement. Pre-window marginal-lane product vulns.
7. **dev.to builder pieces** (Bivack 6d, solon-ai-sandbox 13d) —
   lane-adjacent, third-party, pre-window or out-of-scope.
8. **Chrome/VMware/Jenkins CVE clusters** — already filed or out-of-lane.
9. **Lane-adjacent security thought-leadership** — Medium ActionDock
   egress-control piece (Sep-17), epixelsoft agent-sandboxing guide,
   Golem "rise of the agent runtime" blog (3d, per-agent
   SQLite/CozoDB + capability-card egress design), Google VPC Service
   Controls agent-identity rules (92d) — third-party design color, no
   in-lane product moves.

Stale-version rule compliant. In-lane no-launch verdict dated 2026-09-25
stands — streak extends.
