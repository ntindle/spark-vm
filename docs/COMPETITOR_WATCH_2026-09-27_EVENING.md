# Competitor watch — 2026-09-27 (evening)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the late-afternoon pass (#558, merged as `4bdb412`): (A)
fast-mover + pricing re-verification vs the ~08:25–08:35 CDT (2026-09-27)
baseline (vendor reads ~08:55–09:05 CDT 2026-09-27), (B) delta news scan
~08:24–08:55 CDT (~31-min delta window; 10 search queries). Read-only, no
logins, no writes. Captures: `agent_notes/surveyor-a-20260927-0854.md`,
`agent_notes/surveyor-b-20260927-0854.md`.

Naming-hygiene note: label rotation continues — `MORNING` → `LATE_MORNING` →
`MIDDAY` → `AFTERNOON` → `LATE_AFTERNOON` → `EVENING` (chains rotate, not
stack; the label is a rotation counter, not a wall-clock claim — this pass ran
~08:55–09:05 CDT). A further same-day pass rotates again rather than reusing or
POST_-stacking.

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: nothing ages out. **C11
(Baseten/Blaxel) drew zero mentions — quiet pass 2 of 3.** C62 (OpenAI
offline-sandbox escape) drew recrawl contact again (7 syndication hits, new
outlets — gagadget, startupfortune recrawls + madrobot.blog, notebookcheck,
intelligibberish, pulseofnations.lol, us-brief.com) — quiet count stays 0
(recrawl contact is not a quiet pass). Recrawl contact this pass (quiet counts
reset / stay reset, NOT quiet passes): C67 (CodeArts Agent Singapore-family
recrawls; grade stays FIRST-PARTY-CORROBORATED), C29 (Boxd 6ic.com recrawl),
C55 (Cloudflare cross-tenant disk-residue flaw, cyberpress.org recrawl).
C56 (DeepSeek Harness CVE-2026-82533) drew zero mentions this window —
**quiet pass 1 of 3**. C12 stays OPEN (AgentComputer still no egress line).
Aged-out items stayed out or silent with no real movement (C66;
Heapjack/Overpatch; GitLab CVE-2026-85706; Dextr AI). Re-fold-path gap still
open: no re-fold path for an aged-out item that resurfaces with real movement
(follow-up proposal from the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~08:55–09:05 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks (the all-first-try
streak extends to **8 passes**). Every verified figure matches the
~08:25–08:35 CDT baseline on substance. No corpus fold (C32 precedent: nothing
changed on a primary source).

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26 2026 /
   V0.218.0** ("KVM sandbox parameter and CLI WorkOS application"); SEP 25
   V0.217.0 ("NVIDIA B300 GPU type") still second; SEP 24 V0.216.1/V0.216.2,
   SEP 23 V0.216.0 unchanged.
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22** (improved sandbox moves, private
   kit images); the 2026-09-21 v3-kits and 2026-09-15 entries unchanged.
3. **Microsandbox releases** (`github.com/superradcompany/microsandbox/releases`)
   — newest still **v0.7.3** (#1646); v0.7.1, v0.7.0, v0.6.17, v0.6.14, v0.6.13
   entries beneath unchanged.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September** (3 entries: VCR GitHub Action, Pixel Canary, Sandbox memory
   observability); no 26-Sep or 27-Sep entries in any lane. The 23-Sep Drives
   public-beta entry still reads beta-only (no GA language — consistent with
   the out-of-scope P49 watch).
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro $150/mo, Enterprise CUSTOM ($3,000/mo estimator floor), per-second
   billing table tops $0.000014/s per vCPU; concurrency tables intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures identical
   ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours; $20/$100/$500/$2000
   plans; xlarge $100+ plan gate); comparison + benchmark + active-CPU-billing
   sections unchanged.
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers (Starter/
   Builder/Power/Ultra, specs 2vCPU/4GB/40GB → 8vCPU/24GB/200GB), BYO-AI FAQ
   ("No. AI subscriptions and usage are not included.") intact.
8. **DigitalOcean harness-runtime pricing** (canonical URL, HTTP 200) — CPU
   $0.044/vCPU-hr, Memory $0.0095/GB-hr, egress $0.01/GiB, snapshots $0.05/
   GiB-month; 25%-of-allocated active-CPU footnote intact; stamp still
   "Last verified 22 Sep 2026"; mars-1vcpu-1gb → mars-16vcpu-32gb shapes
   intact. DO snapshot-figure discrepancy unresolved but unmoved.
9. **AgentComputer.ai pricing** — $0.07/CPU-hr, $0.04375/GB-hr, Hot $0.000683/
   Cold $0.000027, Enterprise custom tier present, still no egress line —
   C12 stays OPEN.

(Vercel Drives not re-checked per P49 daily cadence — next due 2026-09-28.)

## Surveyor B — delta news scan: 0 NEW / 20 clean dedupes / 2 flagged-only

**0 NEW.** All 10 queries returned only pre-window events and recrawls of
already-filed items — no new C-numbers, no grade changes.

**20 clean dedupes** (all filed, no new facts): Docker Cloud Sandboxes
Sep-24/25 launch-wave recrawls (how2shout, ADTmag, webpronews, 3
GlobeNewswire reprints); Daytona third-party SDK bookkeeping (6 items —
wildberries TS SDK changelog, paperclip plugin, lithoscomputer audit,
agentscope-ai docs, osmosis-ai changelog, meridian-flow note); E2B $21M
Series A recrawls (vestbee, SiliconANGLE); Modal $15B raise-talks recrawls
(srnnews, wncy — filed 09-24); Baseten $26B (runtimewire — filed 09-24/09-26);
Baseten-acquires-Blaxel analysis color (beri.net — acquisition filed, no new
facts); **C55** recrawl (cyberpress.org Cloudflare cross-tenant disk-residue
piece — matches the vendor-verified fold) — recrawl contact; **C62**
syndication wave (gagadget, startupfortune recrawls + madrobot.blog,
notebookcheck, intelligibberish, pulseofnations.lol, us-brief.com — all
re-reporting the Sep-25/26 disclosure, no new facts) — recrawl contact,
quiet count stays 0; **C67** family recrawls (fintechnews.sg, scommerce,
itbrief.in, techcoffeehouse, technotime — Singapore-family, ~Aug 31/Sep 1) —
recrawl contact, grade unchanged FIRST-PARTY-CORROBORATED; **C29** recrawl
(6ic.com — filed) — recrawl contact; vm2 CVE-2026-100721 / CVE-2026-47686
dedupe (stackflag, 1dayexploit — filed vm2 flagged-only precedent); n8n
five-CVE batch (mcppedia — filed flagged-only 09-26); Vercel Sandbox Drives
write-up (nandann — filed MIDDAY); Vercel Sandbox 64 GB (ai-cost-estimator —
filed 09-22); Vercel concurrency/port-limit changelog, Herdr plugin notes,
DEV E2B-vs-Vercel-vs-Modal-vs-Daytona comparison (all filed); OpenAI Agents
API partner-list color (filed Sep-10 flagged-only precedent).

**2 flagged-only, NOT folded, no C-number** (both lane-adjacent):
1. **nandann "Vercel Sandbox Routing Got Faster"** (region-local domain
   lookups, 62ms→3.4ms; Sep 8 announcement) — new-to-corpus third-party
   infrastructure-performance analysis, not a sandbox product or pricing
   move. Vercel write-ups flagged-only precedent applies.
2. **CVE-2026-63587 — VMware ESXi SVGA sandbox escape** (disclosed 2026-09-22,
   CVSS 9.8, securewithumer PoC repo) — new-to-corpus; hypervisor-level,
   lane-adjacent security color for the sandbox threat model. vm2
   CVE-2026-100721 flagged-only precedent applies. No C-number.

**Not counted:** CVE-2026-77812 (iOS WebKit 0-day — consumer mobile, not the
agent-VM lane); Modal Sep-4 storage incident (pre-window, resolved); The
Sandbox (SAND token) creator bounty (unrelated game metaverse);
devrohit06 e2b-daytona blog (39d, pre-window).

Stale-version rule compliant; Surveyor B grepped the last 3 watch docs plus
corpus for every candidate before classifying — no false first-sightings.

## Verdict

**No new in-window in-lane launches this window; the sandbox-infrastructure
lane stays quiet.** Vendors: 9/9 unchanged; the all-first-try streak reaches
8 passes. News: 0 new, recrawls only. New-to-corpus sightings are both
flagged-only lane-adjacent items (nandann Vercel routing analysis; VMware ESXi
SVGA escape). The corpus is steady — carried items C37, C55, C57, C58
(pricing vendor-verified), C62 (quiet count 0, recrawl contact), C67
(FIRST-PARTY-CORROBORATED, recrawl contact), C29 (recrawl contact); C26
CLOSED; C12 OPEN (AgentComputer still no egress policy); C11 quiet pass 2 of
3; C56 quiet pass 1 of 3. Aged out (staying out): C66, Heapjack/Overpatch,
GitLab proxy escape (CVE-2026-85706), Dextr AI. Re-fold-path gap still open.
