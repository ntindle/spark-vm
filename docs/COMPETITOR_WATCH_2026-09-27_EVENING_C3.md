# Competitor watch — 2026-09-27 (evening, cycle 3)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the afternoon cycle-3 pass (#582, merged as
`9164444`): (A) fast-mover + pricing re-verification vs the
~17:12–~17:13 CDT (2026-09-27) baseline (vendor reads ~18:26–~18:28
CDT 2026-09-27), (B) delta news scan ~17:55–~18:26 CDT (~30-min delta
window; scan ran ~18:27–~18:29 CDT; 20 search queries, snippet level,
zero pages opened — no genuinely-new first-party claims surfaced).
Read-only, no logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1824.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1824.md`.

Naming-hygiene note: rotation continues — `AFTERNOON_C3` →
`EVENING` (cycle 3), `_C3` disambiguator since `EVENING` already
names an earlier 2026-09-27 pass (and `EVENING_C2` a cycle-2 pass);
the label remains a rotation counter, not a wall-clock claim (this pass
ran ~18:26–~18:29 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied
this pass: **C62 (OpenAI offline-sandbox escape / training-pause)** —
RECRAWL CONTACT this pass (7-outlet wave: byteiota, shattered.io,
techspot, gagadget, ianslive, tech-insider.org, particle.news — same
Sep-20 DNS escape / Sep-25 pause facts; misalignment-framework
incident details already filed in the corpus Sep-26); per P63 any
contact resets, so the quiet count **RESETS 2/3 → 0/3** — the prior
three B-lane quiet passes are superseded; watch the wave for a genuine
wind-down before any new aging run. **C11 (Baseten/Blaxel)** recrawl
contact (Modal/Baseten funding-talk recrawls — bytevyte 2h, techflier
4h, radio reprints; same Bloomberg Sep-23 talks; neither round closed)
— quiet stays reset (0/3). **C45 (Docker Cloud Sandboxes)** recrawl
contact (redsecuretech <1h, applethreat 12h, brocker 3h — same Sep-15
77179/79994 facts, fixed 0.42.0, no KEV) — quiet stays reset (0/3).
**C67 (Huawei CodeArts Agent)** recrawl contact (pocketnews.com.my
Sep-27 recap of the filed Sep-7 WAIC launch facts; huawei.com
first-party release recirculating — Sep-18 event facts) — quiet stays
reset (0/3), grade FIRST-PARTY-CORROBORATED unchanged.
**CVE-2026-77179 + CVE-2026-79994** recrawl contact (no new CVE in the
family). **Modal $15B raise talks** recrawl contact (same recrawl
wave as the C11 outlets; neither round closed — filed Sep-23, no new
movement). **Daytona** — changelog top entry still SEP 26 / V0.218.0
(vendor page crawled ~3h by B too — corroborates), no V0.219+; no
movement. **Docker Sandboxes** — release notes still top out
2026-09-22 (v3 kits; sandbox moves + private kit images); no movement.
**Microsandbox** — no new tagged release: v0.7.3 still newest on the
vendor releases page (#1646), vendor-verified this pass;
downstream-consumer sightings only. **E2B / Vercel Sandbox / Runloop /
TermSquad / boat.dev** — no product/pricing movement (Drives still
public beta, no GA; vercel/sandbox CHANGELOG 4.4.0 is 4d-old; Runloop
Devboxes GA PR recirculation only — known old-PR per the
2026-09-25_EVENING anti-chase note; TermSquad Sep-15 launch-press
syndication recrawls only; E2B corpus self-matches + Sep-11 cookbook
summaries; boat.dev corpus self-matches — no boat.dev news).
**C26 (DO Managed Agents, closed)** — Sep-22 public-preview recrawls
only (subagentic.ai 4d, forkast 4d, releasebot 1d, DO blog 5d); stays
closed. **C56 (DeepSeek Harness CVE-2026-82533)** — not sighted this
pass; aged-out stays out, not re-folded per P66. **C66 (OpenClaw
CVE-2026-100589)** — TheHackerWire recrawl (same Sep-26 03:17 content)
— aged-out clean dedupe, not re-folded. **DuneSlide (Cursor
CVE-2026-50548/50549)** — recrawls all pre-window (qpulse 88d,
cybersecuritynews 39d, securityonline.info 83d); no new facts, stays
flagged-only. **C29 (Boxd)** — not surfaced in B lane this window;
carry forward from series. **C12 (AgentComputer)** — not sighted in B
lane (the egress query surfaced no first-party line); stays OPEN.
Vendor-verified pricing contact this pass (still no egress line) — not
a quiet pass. Aged-out stay out: Heapjack/Overpatch not sighted;
GitLab CVE-2026-85706 not sighted. No age-outs this pass; no re-folds.

**Corpus-gap notes carried (NOT folded — pre-window):**
1. CVE-2026-12039 / CVE-2026-12539 / CVE-2026-18171 missing from the
   corpus — pre-window fold line-item for C45's CVE family.
2. **CVE-2026-93993** (Mistral Vibe worktree git-hook RCE, CVSS 8.8,
   Sep-19 disclosure) — new-to-corpus CVE number, disclosure
   pre-window, flagged-only. The whole Mistral Vibe family
   (87983…87988) has never been folded, so a fold changes precedent —
   parent call.
3. **NanoClaw 2.0 / NanoCo** — new-to-corpus entity, lane-adjacent,
   THIRD-PARTY coverage only (VentureBeat). New evidence this pass:
   the venturebeat Slack-integration recrawl (crawl 1h) keeps
   recirculating the NanoCo Slack launch; siliconangle $12M raise is
   May-20 pre-window; no first-party NanoCo announcement — parent
   call on whether to open a watch line-item.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~18:26–~18:28 CDT; every page loaded on
first attempt — 9/9 first-try, zero retries, zero bot-blocks. The
all-first-try streak extends to **24 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP
   26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"). SEP 25 V0.217.0 ("NVIDIA B300 GPU type"), SEP 24
   V0.216.1/V0.216.2, SEP 23 V0.216.0 beneath unchanged. No 27-Sep
   entry.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`) — newest dated
   heading still **2026-09-22** ("improved sandbox moves + private
   kit images in cloud sandboxes"); the 2026-09-21 v3-kits entry
   unchanged.
3. **Microsandbox releases**
   (`github.com/superradcompany/microsandbox/releases`) — newest
   still **v0.7.3** ("chore: release v0.7.3 by @toksdotdev in #1646");
   vendor-authoritative (third-party "v0.7.1 newest" snippet chatter
   remains a discardable conflict).
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header
   still **25 September** (VCR GitHub Action login, Pixel Canary on AI
   Gateway, Sandbox memory observability in dashboard and CLI); 24/23/22
   Sep beneath unchanged; no 26/27-Sep entries. Drives NOT re-checked
   per P49 daily cadence (next due 2026-09-28).
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE (+$100 one-time
   usage credit, sessions up to 1h, 20 concurrent sandboxes), Pro
   $150/mo (+usage, sessions up to 24h, 100 concurrent), Enterprise
   CUSTOM. 1 vCPU = $0.000014/s. Unchanged.
6. **boat.dev pricing** (`docs.boat.dev/pricing`) — small $0.018 /
   default $0.036 / large $0.072 / xlarge $0.200 per hour (2/4/8/16
   vCPU, 4/8/16/32 GB RAM); 25 free trial hours; $20/$100/$500/$2000
   credit plans. Comparison table still lists competitors (incl.
   Vercel Sandbox $0.682 default-hr, "active CPU only" footnote).
   Unchanged.
7. **TermSquad pricing** (`termsquad.com/pricing`) — Starter $9 (2
   vCPU/4GB/40GB NVMe), Builder $19 (4/8/75), Power $29 (6/12/100),
   Ultra $49 (8/24/200). BYO-AI stance intact ("AI subscriptions and
   usage are not included" — bring your own subscriptions/API keys).
   Unchanged.
8. **DigitalOcean harness-runtime pricing**
   (`digitalocean.com/pricing/harness-runtime`) — CPU $0.044/vCPU-hour,
   Memory $0.0095/GB-hour, session volumes $0.05/GiB-month,
   snapshots/checkpoints $0.05/GiB-month, public internet egress
   $0.01/GiB, BYOT templates $0.05/GiB-month; shapes XSmall 1vCPU/1GB
   $0.0535/hr, Small $0.107, Medium (default) $0.126, Large $0.252,
   XLarge 16vCPU/32GB $1.008/hr. The "Last verified 22 Sep 2026"
   stamp is STILL not visible in fetched text — tenth consecutive
   pass, capture-gap, not a delta.
9. **AgentComputer pricing** (`agentcomputer.ai/pricing`) — CPU Time
   $0.07/CPU-hour; Memory $0.04375/GB-hour; Hot Storage
   $0.000683/GB-hour (running); Cold Storage $0.000027/GB-hour
   (stopped). Still no egress line — **C12 stays OPEN**.

## Surveyor B — delta news scan: 0 NEW / recrawl contacts / 12 flagged-only

20 search queries, snippet level, zero pages opened — no
genuinely-new first-party claims surfaced, so no C68. Recrawl
contacts: C62 (7-outlet wave — byteiota, shattered.io, techspot,
gagadget, ianslive, tech-insider.org, particle.news — same Sep-20/25
facts; quiet RESET 2/3 → 0/3), C11 (Modal/Baseten funding-talk
recrawls — bytevyte 2h, techflier 4h, radio reprints — quiet 0/3),
C45 (redsecuretech <1h, applethreat 12h, brocker 3h — same Sep-15
facts — quiet 0/3), C67 (pocketnews Sep-27 recap of filed Sep-7
launch facts; huawei.com first-party release recirculating — quiet
0/3), CVE-2026-77179/79994 (no new family members), Modal $15B raise
talks (neither round closed), Daytona (changelog still SEP 26 /
V0.218.0, no V0.219+), Docker Sandboxes (release notes still
2026-09-22), Microsandbox (no new tagged release; v0.7.3
vendor-verified), E2B / Vercel Sandbox / Runloop / TermSquad /
boat.dev (no product/pricing movement), C26 (Sep-22 public-preview
recrawls only — closed, stays closed), C66 (TheHackerWire recrawl —
aged-out clean dedupe, not re-folded), DuneSlide (pre-window
recrawls only — flagged-only), C12 (no first-party egress line —
OPEN), C29 (not surfaced — carried).

Flagged-only (NOT folded) — numbered, one-line verdicts each:
1. **OpenAI DevDay "agent O" always-on agent rumor — STILL
   UNCONFIRMED** — sixth daily cycle of the echo wave
   (testingcatalog <1h, Medium ai-engineering 1h, YouTube explainer
   7h, KuCoin flash 1h, runtimewire 1h, wisevoter <1h,
   pasqualepillitteri.it 10h — the latter explicitly tabulates
   "Launch of 'o' at DevDay: Hypothesis, no confirmation"); all trace
   to testingcatalog's Sep-26 report. DevDay outcome check remains
   scheduled in the Sep-29 slots.
2. **CVE-2026-100690 (Hugo symlink permission-model bypass)** —
   TheHackerWire (crawl 12h, same content). STILL no gohugoio GHSA on
   100690 itself. Re-folds ONLY on a 100690-specific gohugoio GHSA or
   agent-infra nexus.
3. **Mistral Vibe CVE family 87983…87988 + CVE-2026-93993** —
   recrawls only (RedPacket US-CERT Sep-14 summary 6d, ghostx0x
   vuln-tracker 2d, SecMate mistral-vibe-attack-demo 2d, jimblogic
   cyberdailylog 2d); Sep-11/19 disclosures, pre-window. 93993
   corpus-gap candidacy remains a parent call (whole Vibe family
   never folded — precedent unchanged).
4. **NanoClaw 2.0 / NanoCo** — venturebeat Slack-integration recrawl
   (crawl 1h, third-party); no first-party NanoCo announcement.
   Flagged-only; parent call on watch line-item stands.
5. **Modal network-egress billing** (third-party GitHub doc, 11d
   pre-window: egress charges effective Oct 1 2026, $0.04/GiB over
   plan allowances) — third-party read of a Modal vendor change; not
   a vendor announcement read this pass. Flagged-only; a later slot
   should do a first-party Modal pricing-page verification before
   folding.
6. **Aliyun FC Agent Sandbox new billing/pricing launch** (6d,
   third-party: E2B-SDK integration, auto Pro-tier transition,
   Shallow Hibernation) — third-party (Aliyun), pre-window.
   Lane-adjacent. Flagged-only.
7. **Baseten $1.5B Series F at $13B** (storagenewsletter, reported
   Sep-24; actual close June 2026 per the Baseten blog) — pre-window
   closed round, not the Sep-23 $26B talks. Context only.
   Flagged-only.
8. **Funding lane adjacency** — Crusoe $3.9B Series F (Sep-24,
   closed), DeepSeek $7.45B planned raise — compute-funding noise,
   none are sandbox/agent-compute products. Flagged-only.
9. **secnews.gr OpenClaw/Google-Meet vulnerability advisory**
   (crawl <1h) — different vuln from CVE-2026-100589, third-party
   hardening advisory. Not folded; C66 aged-out stays out.
10. **weeklyclaw-ai episode agenda** (3d, third-party) — podcast
    covering Gemini Spark/OpenClaw/NanoClaw; NanoClaw $12M seed facts
    already known. Lane-adjacent. Flagged-only.
11. **Azure SRE Agent / Google Cloud marketplace pricing models** —
    surfaced by the egress query; out of sandbox lane. Ignored.
12. **Guava "Daytona" voice model** — did not surface this pass;
    name-collision item quiet. Carried.

No corpus fold (C32 precedent: watch docs are delta-only). No new
C-numbers. Sandbox-infrastructure lane stays quiet; the in-lane
no-launch verdict dated 2026-09-25 stands — streak extends.

## Watch-out for the next surveyor

1. OpenAI DevDay (Tue Sep 29) — the "agent O" echo wave is on its
   **sixth** daily cycle (all trace to testingcatalog's Sep-26
   report; still UNCONFIRMED — OpenAI has not confirmed "O");
   pasqualepillitteri.it now explicitly tabulates "Hypothesis, no
   confirmation". Do not re-open the rumor item, only watch for an
   actual confirmation — a DevDay confirmation of a consumer
   always-on agent (VM access, long-horizon tasks) would be
   C68-candidate material — schedule the DevDay-outcome check in the
   Sep-29 slots.
2. **C62 quiet-count restart** — this pass's 7-outlet recrawl wave
   (crawls <1h) RESET the quiet count from 2/3 → 0/3. The prior
   three B-lane quiet passes are superseded — watch the wave for a
   genuine wind-down before any new aging run.
3. CVE-2026-93993 fold decision (see corpus-gap note 2 — parent
   call; whole Vibe family never folded).
4. NanoClaw/NanoCo — venturebeat keeps recirculating the Slack
   launch; if NanoCo ships a sandbox/compute product or a
   first-party announcement surfaces, re-grade from flagged-only.
5. Modal egress billing (Oct 1 2026) — third-party read this pass; a
   later slot should do a first-party Modal pricing-page
   verification before folding.
6. Hugo CVE-2026-100690 — one more gohugoio/security/advisories
   sweep for a 100690-specific GHSA (TheHackerWire page re-ingested
   again this pass; re-folds only on a 100690-specific GHSA or an
   agent-infra nexus).
7. Modal $15B / Baseten $26B rounds — still talks (Bloomberg Sep-23);
   both companies continue to reprint without closing.
8. DuneSlide vs GhostApproval: if DuneSlide is ever ingested,
   merge/tag `duplicate_of` (CVE-2026-50549 shares its fix ID with
   Wiz's GhostApproval), do not double-count.
