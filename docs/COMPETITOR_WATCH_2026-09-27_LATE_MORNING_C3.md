# Competitor watch — 2026-09-27 (late morning, cycle 3)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the morning cycle-3 pass (#579, merged as
`97b9a72`): (A) fast-mover + pricing re-verification vs the ~15:55–~15:56
CDT (2026-09-27) baseline (vendor reads ~16:25–~16:26 CDT 2026-09-27),
(B) delta news scan ~15:55–~16:25 CDT (~30-min delta window; scan ran
~16:26–~16:40 CDT; 16 search queries, snippet level, zero pages
opened — no genuinely-new first-party claims surfaced). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1624.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1624.md`.

Naming-hygiene note: rotation continues — `MORNING_C3` →
`LATE_MORNING` (cycle 3), `_C3` disambiguator since `LATE_MORNING`
already names an earlier 2026-09-27 pass; the label remains a rotation
counter, not a wall-clock claim (this pass ran ~16:25–~16:40 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied
this pass: **C11 (Baseten/Blaxel) recrawl contact** (beri.net,
runtimewire, techintelpro, dealroom, webull — same Sep-10 acquisition
facts) — quiet stays reset (0/3). **C67 (Huawei CodeArts Agent) recrawl
contact** (pocketnews Sep-27 follow-up — 16 agents, 30+ skills, Early
Bird 3-mo Professional; yamchatime, malaysiasme, scommerce, itbrief —
same Sep-7 Malaysia commercial-launch facts) — grade unchanged
FIRST-PARTY-CORROBORATED, 0/3. **C45 (Docker Cloud Sandboxes) recrawl
contact** (thecybersecguru, brocker, 4tify, aratech, thehackernews —
same Sep-15 77179/79994 facts, fixed 0.42.0, no exploitation) — no
movement. **CVE-2026-77179 + CVE-2026-79994 recrawl contact** (same
recrawls); no new CVE in the family. **CVE-2026-92122 (Jenkins) +
CVE-2026-63587 (VMware ESXi)** — recrawls only (aicybr, securityonline,
undercodenews, dev.to, OpenCVE, securewithumer PoC); no movement; filed,
stay filed. **Modal $15B raise talks recrawl contact** (bytevyte,
runtimewire, radio-syndication reprints — same Bloomberg Sep-23 talks;
neither round closed — filed Sep-23, no new movement). The bytevyte
piece carries a 4-round valuation-history table (Modal ~$1.1B Sep-25 →
~$15B talks Sep-26; Baseten $2.1B Sep-25 → ~$26B talks) — funding-
trajectory color if the corpus ever wants it. **Daytona** — changelog
top entry still SEP 26 / V0.218.0, no V0.219+; no movement.
**Microsandbox** — v0.7.1 still newest tagged release; v0.7.2 bump PR
#1610 still release-preparation only (downstream inoio/agents-sandbox
v0.3.1 consumes unreleased code) — no new tagged release.
**E2B / Vercel Sandbox / Runloop / TermSquad / boat.dev** — no
product/pricing movement (TermSquad Sep-15 launch-press syndication
recrawls only; Vercel Sandbox Drives still public beta, no GA
movement). **vm2 CVE-2026-47686** — 1dayexploit analysis recrawl;
already filed; no movement. **C56 (DeepSeek Harness CVE-2026-82533)**
aged-out recrawl contact (devops.com, dennysentinel) — aged-out stays
out, not re-folded per P66. **C26 (DO Managed Agents, closed)** — no
movement; closed, stays closed. **C29 (Boxd)** — not surfaced in B lane
this window; carry forward from series. **C62 (OpenAI offline-sandbox
escape / training-pause)** — NOT sighted in B lane this pass; quiet
count HELD at 0/3 (no advance on an ambiguous no-sight — surveyor B
flagged it for parent confirmation rather than folding silently; the
next surveyor applies P63 quiet-pass accounting if C62 goes a second
consecutive pass without contact). **C12 not sighted in B lane; stays
OPEN** — AgentComputer pricing vendor-verified this pass (still no
egress line), so vendor contact, not a quiet pass. Aged-out stay out:
C66 not sighted; Heapjack/Overpatch not sighted as new movement
(cybersecuritynews 6d Overpatch piece = aged-out); GitLab
CVE-2026-85706 not sighted. No age-outs this pass; no re-folds.

**Corpus-gap notes carried (NOT folded — pre-window):**
1. CVE-2026-12039 / CVE-2026-12539 / CVE-2026-18171 missing from the
   corpus — pre-window fold line-item for C45's CVE family.
2. NEW offered candidate this pass: **CVE-2026-93993** (Mistral Vibe
   worktree git-hook RCE, CVSS 8.8, Sep-19 disclosure) — new-to-corpus
   CVE number, disclosure pre-window, flagged-only. The whole Mistral
   Vibe family (87983…87988) has never been folded, so a fold changes
   precedent — parent call.

No other deep-scan leads filed this pass. Watch-out for the next
surveyor: (1) OpenAI DevDay (Tue Sep 29) — the "agent O" echo wave is on
its third daily cycle (YouTube leak videos now joining); a DevDay
confirmation of a consumer always-on agent (email identity,
long-running tasks) would be C68-candidate material — schedule the
DevDay-outcome check in the Sep-29 slots. (2) CVE-2026-93993 fold
decision (see corpus-gap note 2). (3) Hugo CVE-2026-100690 — one more
gohugoio/security/advisories sweep for a 100690-specific GHSA. (4)
DuneSlide vs GhostApproval: if DuneSlide is ever ingested, merge/tag
`duplicate_of` (orca-ai-incident-archive notes CVE-2026-50549 shares its
fix ID with Wiz's GhostApproval), do not double-count. (5) Modal/Baseten
funding-trajectory color (bytevyte valuation table) if the corpus wants
it.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~16:25–~16:26 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **21 passes**.

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
   seventh consecutive pass; capture-gap, not a delta).
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr memory, Hot $0.000683/Cold $0.000027 per GB-hr,
   Enterprise custom tier present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass. Drives not re-checked per the out-of-scope
P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / recrawl contacts / 15 flagged-only

16 search queries (~15:55–~16:25 CDT delta window; scan ran ~16:26–~16:40
CDT; snippet level, zero pages opened — no genuinely-new first-party
claims surfaced); every candidate grepped against the full watch-doc
series + the corpus before classification. No new in-window in-lane
launches, pricing moves, fundings, or sandbox-escape CVEs. No new
C-numbers — **C68 not opened**.

**Recrawl contacts / clean dedupes (all filed, no new facts):** C11
(beri.net, runtimewire, techintelpro, dealroom, webull — same Sep-10
acquisition facts; quiet stays 0/3); C67 (pocketnews Sep-27 follow-up,
yamchatime, malaysiasme, scommerce, itbrief — color only, grade
unchanged FIRST-PARTY-CORROBORATED, 0/3); C45 (thecybersecguru,
brocker, 4tify, aratech, thehackernews — same Sep-15 77179/79994
facts); CVE-2026-77179 + CVE-2026-79994 (filed — no new CVE in the
family); CVE-2026-92122 (Jenkins) + CVE-2026-63587 (VMware ESXi)
(recrawls only, no movement); Modal $15B raise talks (bytevyte,
runtimewire, radio-syndication reprints — filed Sep-23, neither round
closed); Daytona (changelog top entry still SEP 26 / V0.218.0 — no
V0.219+); Microsandbox (v0.7.1 still newest tagged — v0.7.2 bump PR
still release-preparation); E2B / Vercel Sandbox / Runloop / TermSquad /
boat.dev (no product/pricing movement; TermSquad Sep-15 syndication
recrawls only); vm2 CVE-2026-47686 (1dayexploit analysis recrawl, filed);
C26 (no movement, closed stays closed); C56 (devops.com, dennysentinel
recrawls — aged-out, not re-folded); C62 not sighted in B lane (quiet
count held at 0/3, see P63 section); C12 not sighted in-lane (stays
OPEN); C29 not surfaced (carry forward).

**Flagged-only (NOT folded):**

1. **CVE-2026-100690 (Hugo symlink permission-model sandbox bypass)** —
   TheHackerWire re-ingested (crawl 10h, same content); STILL no
   first-party corroboration of 100690 itself (no 100690-specific
   gohugoio GHSA; GHSA-vrv5-r5rf-6v4j covers the earlier sibling 89258).
   Stays flagged-only; re-folds only on a 100690-specific gohugoio GHSA
   or an agent-infra nexus.
2. **OpenAI DevDay "agent O" always-on-agent rumor — STILL UNCONFIRMED**
   — alextech.ai Sep-27 re-synthesis (18h), vibingtalk (2h), YouTube
   "World of AI" DevDay-leak video (1d) — echo wave on its third daily
   cycle, all still echoing testingcatalog's Sep-26 report. STILL
   UNCONFIRMED — OpenAI has not confirmed "O". Flagged-only — the
   Sep-29 slots must check the DevDay outcome.
3. **CVE-2026-87983…87988 (Mistral Vibe permission bypasses)** —
   stackflag + SecMate recrawls; Sep-11 disclosure, pre-window. Stays
   flagged-only.
4. **CVE-2026-93993 (Mistral Vibe worktree git-hook RCE, CVSS 8.8)** —
   new-to-corpus CVE number (Sep-19 disclosure); pre-window.
   Flagged-only per rules; offered as corpus-gap candidate (see above).
5. **Cursor DuneSlide CVE-2026-50548/50549 (zero-click prompt-injection
   sandbox escape, CVSS 9.8)** — not in series/corpus; disclosure
   July 1 / fixed April 2 (Cursor 3.0) — pre-window client-side-sandbox
   research (same lane as aged-out Overpatch/Heapjack/GhostApproval).
   Resurfaced only via lemma + dailysecurityreview re-ingests.
   Flagged-only; if ever ingested, merge/tag `duplicate_of`
   GhostApproval (CVE-2026-50549 shares its fix ID), do not
   double-count.
6. **vm2 CVE-2026-47686 analysis recrawl** (1dayexploit) — already
   filed; vm2 <3.11.8 AggregateError advisory (Sep-17) pre-window.
   Flagged-only. No new in-window agent-sandbox CVE.
7. **Daytona "agent-agnostic infrastructure" PRNewswire reprints** —
   known old-PR recirculation per the 2026-09-25_EVENING anti-chase
   note. Flagged-only.
8. **Guava "Daytona" voice model** (Sep-23 press + syndication, name
   collision) — out of lane. Flagged-only.
9. **TokenCost Agents API sandbox pricing table** (tokencost.app, ~14d)
   — pre-window third-party; deep-scan pricing input only. Flagged-only.
10. **dev.to builder pieces** — Bivack (6d), solon-ai-sandbox (13d),
    "An AI Escaped Its Sandbox" (64d), decodingai-magazine Modal-backend
    wiki (9d) — lane-adjacent, third-party, pre-window. Flagged-only.
11. **Google CC isolated cloud computers** (TechRepublic 13h) — consumer
    multi-agent household product on Google's Antigravity; lane-adjacent
    (different vendor shape from tracked AgentComputer). Flagged-only.
12. **Forcepoint unbound-consumption warning** (techgig Sep-25,
    pre-window) — agent cost runaway, lane-adjacent security economics.
    Flagged-only.
13. **FastGPT v4.16.0 agent-sandbox guidance** (13d) — deprecated E2B
    configs, migration to opensandbox/sealosdevbox; pre-window, adjacent
    self-host lane. Flagged-only.
14. **sec-news.ai VMware vCenter ransomware piece** (11d) — different
    VMware flaw, not 63587; pre-window. Flagged-only.
15. **techinasia: Huawei CodeArts HarmonyOS upgrade** (Sep-21,
    pre-window) — C67-family adjacent, third-party; no new facts beyond
    the Malaysia launch. Flagged-only.

Stale-version rule compliant. In-lane no-launch verdict dated 2026-09-25
stands — streak extends.
