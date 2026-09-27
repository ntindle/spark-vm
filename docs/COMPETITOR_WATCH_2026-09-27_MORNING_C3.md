# Competitor watch — 2026-09-27 (morning, cycle 3)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the predawn cycle-2 pass (#578, merged as
`9903f9f`): (A) fast-mover + pricing re-verification vs the ~15:26–~15:27
CDT (2026-09-27) baseline (vendor reads ~15:55–~15:56 CDT 2026-09-27),
(B) delta news scan ~15:25–~15:55 CDT (~30-min delta window; scan ran
~15:56–~16:02 CDT; 15 search queries, snippet level, zero pages
opened — no genuinely-new first-party claims surfaced). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1554.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1554.md`.

Naming-hygiene note: the cycle-2 rotation is complete — `PREDAWN_C2`
was its ninth and final label. This pass starts cycle 3, so the label
restarts at `MORNING_C3` (mirroring cycle 2's own start, which opened
with `MORNING_C2` after the cycle-1 `NIGHT` per the night doc's "rotates
again rather than reusing or POST_-stacking" rule). The `_C3`
disambiguator is load-bearing (`MORNING` and `MORNING_C2` already name
earlier passes); the label remains a rotation counter, not a wall-clock
claim (this pass ran ~15:55–~16:02 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied
this pass: **C62 (OpenAI offline-sandbox escape / training-pause)
recrawl contact again** (gagadget, tech-insider — adds Sep-27 Business
Times/Economic Times/Rediff follow-ups, same pause-confirmed facts —
intelligibberish, startupfortune, particle.news, deafnews.it,
newsheadlinealert, zubiqo; all outlets already in series/corpus, same
Sep-20 DNS-escape + Sep-25/26 disclosure) — quiet count stays reset
(0/3). **C11 (Baseten/Blaxel) recrawl wave** (beri.net, pulse2,
techdefused, techintelpro — same Sep-10 acquisition facts, already
filed) — quiet stays reset (0/3). **C67 (Huawei CodeArts Agent) recrawl
contact** (pocketnews Sep-27 follow-up, yamchatime, malaysiasme,
scommerce/itbrief Singapore pieces — same Malaysia commercial-launch
facts; no new launch facts) — grade unchanged FIRST-PARTY-CORROBORATED,
0/3. **C45 (Docker Cloud Sandboxes) recrawl contact** (thecybersecguru,
dev.to "Five Docker Sandboxes CVEs", brocker, severitydaily, aratech,
thehackernews — same Sep-15 77179/79994 facts, fixed 0.42.0, no
exploitation) — no movement. **CVE-2026-77179 + CVE-2026-79994 recrawl
contact** (same recrawls); no new CVE in the family.
**CVE-2026-92122 (Jenkins) + CVE-2026-63587 (VMware ESXi)** — recrawls
only (aicybr, securewithumer PoC); no movement; filed, stay filed.
**C29 (Boxd)** — recrawl contact (6ic.com + syndication). Filed.
**C26 (DO Managed Agents, closed)** — no movement; closed, stays
closed. **C56 (DeepSeek Harness CVE-2026-82533) aged-out recrawl contact**
(CSA labs research note — aged-out stays out, not re-folded per P66).
**C12 not sighted in B lane; stays OPEN** — AgentComputer pricing
vendor-verified this pass (still no egress line), so vendor contact, not
a quiet pass. Aged-out stay out: C66 not sighted; Heapjack/Overpatch not
sighted as new movement; GitLab CVE-2026-85706 not sighted. No
age-outs this pass; no re-folds.

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
surveyor: (1) OpenAI DevDay (Tue Sep 29) outcome check — the "agent O"
always-on-agent rumor remains UNCONFIRMED after two full echo waves, all
traces to testingcatalog's Sep-26 report; a DevDay confirmation of a
consumer always-on agent (email identity, long-running tasks) would be
C68-candidate material — the single most in-lane pending event. (2)
Hugo CVE-2026-100690 — TheHackerWire re-ingested again (crawl 10h);
re-folds ONLY on a 100690-specific gohugoio GHSA or an agent-infra nexus
— worth one more gohugoio/security/advisories check next pass. (3)
Mistral Vibe CVE-2026-87983…87988 stays flagged-only as pre-window
marginal-lane product vulns (SecMate blog + stackflag recrawls only).
(4) dev.to alexcloudstar sandbox comparison (resurfaced via
pengen.diewe.workers.dev) + TokenCost 9-provider pricing table
(pre-window, ~Sep-13) — both third-party, lane-adjacent deep-scan
pricing-shape inputs, not corpus folds.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~15:55–~15:56 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **20 passes**.

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
   sixth consecutive pass; capture-gap, not a delta).
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr memory, Hot $0.000683/Cold $0.000027 per GB-hr,
   Enterprise custom tier present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass. Drives not re-checked per the out-of-scope
P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / recrawl contacts / 10 flagged-only

15 search queries (~15:25–~15:55 CDT delta window; scan ran ~15:56–~16:02
CDT; snippet level, zero pages opened — no genuinely-new first-party
claims surfaced); every candidate grepped against the full watch-doc
series + the corpus before classification. No new in-window in-lane
launches, pricing moves, fundings, or sandbox-escape CVEs. No new
C-numbers — **C68 not opened**.

**Recrawl contacts / clean dedupes (all filed, no new facts):** C62
(wave continues — 8 outlets, tech-insider adds Sep-27 BT/ET/Rediff
follow-ups, same facts; quiet stays 0/3); C67 (pocketnews Sep-27
follow-up, yamchatime, malaysiasme, scommerce/itbrief — color only,
grade unchanged FIRST-PARTY-CORROBORATED, 0/3); C11 (beri.net, pulse2,
techdefused, techintelpro — same Sep-10 acquisition facts; quiet stays
reset 0/3); C45 (thecybersecguru, dev.to five-CVEs recap, brocker,
severitydaily, aratech, thehackernews — same Sep-15 77179/79994 facts);
CVE-2026-77179 + CVE-2026-79994 (filed — no new CVE in the family);
CVE-2026-92122 (Jenkins) + CVE-2026-63587 (VMware ESXi) (recrawls only,
no movement); C29 (6ic.com recrawl); Daytona (changelog top entry still
SEP 26 / V0.218.0 — no V0.219+); Microsandbox (v0.7.3 vendor-verified —
B's snippet-level "v0.7.1 newest published" chatter contradicts the
vendor releases page and is discarded per the vendor-authoritative
convention); E2B (no movement); Vercel Sandbox (no Drives beta→GA
movement); TermSquad (Sep-15 syndication recrawls only); C26 (no
movement, closed stays closed); C12 not sighted in-lane (stays OPEN);
C56 (CSA labs recrawl, aged-out, not re-folded).

**Flagged-only (NOT folded):**

1. **CVE-2026-100690 (Hugo symlink permission-model sandbox bypass)** —
   TheHackerWire page re-ingested (crawl 10h, "New CVE Received Sep 26,
   2026 14:16" — same content); STILL no first-party corroboration of
   100690 itself (no 100690-specific gohugoio GHSA; GHSA-vrv5-r5rf-6v4j
   covers the earlier sibling 89258). Stays flagged-only; re-folds only
   on a 100690-specific gohugoio GHSA or an agent-infra nexus.
2. **OpenAI DevDay "agent O" always-on-agent rumor — STILL UNCONFIRMED**
   — alextech.ai (20h), vibingtalk (1d), wccftech recrawls all
   grep-confirmed already in POST_NIGHT_C2, all echoing testingcatalog's
   Sep-26 report. STILL UNCONFIRMED — OpenAI has not confirmed "O".
   Flagged-only — the Sep-29 slots must check the DevDay outcome.
3. **CVE-2026-87983…87988 (Mistral Vibe permission bypasses)** — SecMate
   blog (3d) + stackflag recrawls (2d/1d); CVEs pre-window (Sep-11), no
   new in-window in-lane movement. Stays flagged-only.
4. **dev.to "Sandboxing AI-Generated Code: E2B vs Vercel Sandbox vs
   Modal vs Daytona in 2026"** (alexcloudstar, resurfaced via
   pengen.diewe.workers.dev 20h) — lane-adjacent third-party comparison;
   deep-scan pricing-shape input candidate, not a fold. Flagged-only.
5. **Modal sandbox infra rebuild** (my2cents.ai Sep-24 digest: "Modal
   Rebuilt Sandbox Infrastructure Off Kubernetes to Hit a Million
   Concurrent Sandboxes") — pre-window third-party digest of
   staff-engineer detail; outlet already in corpus. Flagged-only.
6. **TokenCost Agents API sandbox pricing comparison** (tokencost.app,
   ~14d: 9-provider 20-min/2vCPU/4GB table — Cloudflare $0.025–0.073,
   Vercel $0.028–0.114, E2B/Daytona/Blaxel $0.055, Modal $0.079, Runloop
   $0.106 vs OpenAI hosted $0.12) — pre-window (~Sep-13), third-party,
   deep-scan pricing input only; outlet already in series. Flagged-only.
7. **dev.to builder pieces** — Bivack (6d), solon-ai-sandbox (13d),
   AltairAgent (20h), "An AI Escaped Its Sandbox" (64d), "AI Agent
   Containment" (11d) — lane-adjacent, third-party, pre-window or
   out-of-scope. Flagged-only.
8. **Perplexity "Computer"** (vocal.media 1d: multi-agent orchestration
   for Max subscribers) — different product from the tracked
   AgentComputer vendor; lane-adjacent, flagged-only.
9. **Guava "Daytona" voice model** (Sep-23 press release + syndication)
   — name collision; voice-AI product, out of lane.
10. **GhostApproval (Wiz, 80d)** — surfaced again in Hugo query results;
    agent-sandbox-adjacent but pre-window. Flagged-only.

Stale-version rule compliant. In-lane no-launch verdict dated 2026-09-25
stands — streak extends.
