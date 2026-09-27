# Competitor watch — 2026-09-27 (late-evening)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the evening pass (#560, merged as `a8bc757`): (A)
fast-mover + pricing re-verification vs the ~08:55–09:05 CDT (2026-09-27)
baseline (vendor reads ~09:24–09:27 CDT 2026-09-27), (B) delta news scan
~09:05–~09:29 CDT (~24-min delta window since the evening pass; scan ran
~09:24–09:29 CDT; 8 search queries). Read-only, no
logins, no writes. Captures: `agent_notes/surveyor-a-20260927-0924.md`,
`agent_notes/surveyor-b-20260927-0924.md`.

Naming-hygiene note: label rotation continues — `MORNING` → `LATE_MORNING` →
`MIDDAY` → `AFTERNOON` → `LATE_AFTERNOON` → `EVENING` → `LATE_EVENING`
(chains rotate, not stack; the label is a rotation counter, not a wall-clock
claim — this pass ran ~09:24–09:29 CDT). A further same-day pass rotates
again (`NIGHT`) rather than reusing or POST_-stacking.

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: **C11 (Baseten/Blaxel) drew
zero mentions for the third consecutive pass — C11 AGES OUT this pass**
(the mandatory one-notice line; aged items stay out pending real movement
per the open re-fold-path gap). **C56 (DeepSeek Harness CVE-2026-82533)
drew zero mentions — quiet pass 2 of 3.** C62 (OpenAI offline-sandbox
escape) drew recrawl contact (aiagentsdirectory AI Agents News Brief,
teknowire Kontext piece) — quiet count stays 0. C12 stays OPEN
(AgentComputer still no egress line; no movement). Aged-out items stayed
out or silent with no real movement (C66; Heapjack/Overpatch; GitLab
CVE-2026-85706; Dextr AI). Re-fold-path gap still open: no re-fold path
for an aged-out item that resurfaces with real movement (follow-up proposal
from the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~09:24–09:27 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **9 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26
   2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS application").
   SEP 25 V0.217.0 ("NVIDIA B300 GPU type") still second; SEP 24
   V0.216.1/V0.216.2, SEP 23 V0.216.0 unchanged.
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22** (improved sandbox moves,
   private kit images); the 2026-09-21 v3-kits entry unchanged; 2026-09-15
   entry still present.
3. **Microsandbox releases** (`github.com/superradcompany/microsandbox/releases`)
   — newest still **v0.7.3** (#1646); full changelog v0.7.2...v0.7.3;
   v0.7.1, v0.7.0, v0.6.17, v0.6.14, v0.6.13 entries beneath unchanged.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September** (3 entries: VCR GitHub Action, Pixel Canary, Sandbox
   memory observability); no 26-Sep or 27-Sep entries in any lane. The
   23-Sep Drives public-beta entry still reads beta-only (no GA language —
   consistent with the out-of-scope P49 watch, next due 2026-09-28).
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro $150/mo, Enterprise CUSTOM ($3,000/mo estimator floor), per-second
   billing table tops $0.000014/s per vCPU; concurrency tables intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans; xlarge $100+ plan gate); comparison +
   benchmark + active-CPU-billing sections unchanged.
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers
   (Starter/Builder/Power/Ultra, specs 2vCPU/4GB/40GB → 8vCPU/24GB/200GB),
   BYO-AI FAQ ("No. AI subscriptions and usage are not included.") intact.
8. **DigitalOcean harness-runtime pricing**
   (`docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/`)
   — CPU $0.044/vCPU-hr, Memory $0.0095/GB-hr, egress $0.01/GiB, snapshots
   $0.05/GiB-month; 25%-of-allocated active-CPU footnote intact; stamp
   still "Last verified 22 Sep 2026". Shapes mars-1vcpu-1gb → mars-16vcpu-32gb
   intact.
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr, Hot $0.000683/Cold $0.000027, Enterprise custom tier
   present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass.

## Surveyor B — delta news scan: 0 NEW / 22 clean dedupes / 7 flagged-only

8 search queries (~09:05–~09:29 CDT delta window; scan ran ~09:24–09:29
CDT); every candidate grepped against the last 3 watch docs + the corpus
before classification — with one exception caught at review:
CVE-2026-92940 was already flagged-only in the 2026-09-26
post-late-evening pass (outside the 3-doc window; never folded into
COMPETITOR_ANALYSIS.md, so the corpus leg missed it). Moved to
recrawl-contact below; see the stale-version rule note. No new in-window
in-lane launches, pricing moves, or fundings. No new C-numbers.

**Recrawl contact (existing item mentioned again, no new facts):** CVE-2026-92940
(vm2 https.globalAgent leak, CVSS 10.0) — first flagged-only in the
2026-09-26 post-late-evening pass; re-surfaced this pass via the vm2
advisory-wave recrawl — recrawl contact of a filed flagged-only item, no
new facts. C29
(Boxd $2M pre-seed, 6ic.com recrawl); C62 (OpenAI offline-sandbox escape —
aiagentsdirectory brief + teknowire); CVE-2026-80521 (Ubuntu AF_UNIX UAF
container escape — thehackernews + cyberrecaps + tech-insider + realhacker.news);
vm2 series CVE-2026-100721/CVE-2026-47686 (stackflag, 1dayexploit) and
CVE-2026-92956/CVE-2026-93603/CVE-2026-93605 (stackflag, thehackerwire,
cvefeed.io); Kontext $4M seed (teknowire recrawl); Baselayer $35M Series A
(letsdatascience + aiagentsdirectory reprints — lane-adjacent agent identity,
not sandbox VM); Google open-sourced AX (aiagentsdirectory brief reprint —
filed under Agent Substrate); OpenAI Agents API beta color (EponaLab +
seduerr91 reprints — Sep-10 flagged-only precedent); Tokencost OpenAI Agents
API pricing analysis (14d recrawl); effect-uai/plans/sandbox.md (capability
matrix matches filed state); computesdk provider table + CHANGELOG (25
providers, no new facts).

**7 flagged-only, NOT folded, no C-number** (new-to-corpus lane-adjacent or
third-party analysis):
1. **CVE-2026-71443 — Docker Engine container escape / privilege escalation**
   (disclosed 2026-09-22, CVSS 8.8; runc exec-handler fd leak →
   `/proc/self/exe` exploitation; Snyk Security Research; securewithumer PoC
   repo). CVE-2026-63587 (VMware ESXi SVGA escape) flagged-only precedent
   applies — runtime-level, lane-adjacent security color. No C-number.
2. **ryanalberts/best-of-agent-harnesses — comparisons/sandboxed-code-execution.md**
   (updated 3 days ago) — third-party comparison (E2B, Modal, Daytona,
   Vercel Sandbox, Cloudflare, AgentCore, GKE, kubernetes-sigs agent-sandbox,
   Docker Sandboxes, microsandbox); reproduces the "Daytona public repo
   unmaintained since June 2026" line; prices Vercel Sandbox by active CPU.
   Comparison write-up = flagged-only (Alex Yedi field-guide precedent), no
   product/pricing move.
3. **pioneeraiacademy/cowork-genealogy — docs/specs/sandbox-provider-spec.md**
   (updated ~6 days ago) — third-party E2B-vs-Daytona provider spec (egress
   gated Tier-3 $500 prepaid top-up on Daytona, compliance status contested).
   Comparison write-up = flagged-only, no C-number.
4. **kuanpak/enterprise-harness-agents — research/sandbox-mgmt.md** (updated
   ~5 days ago) — engineering research: Daytona lifecycle automation survey
   (autoStop 15 min default, autoPause, warm pools exact-match claiming) +
   "steal E2B's data-plane design" (snapshot-as-template, UFFD lazy memory,
   per-slot nftables egress). Third-party analysis = flagged-only.
5. **colemurray/background-agents — docs/VERCEL_SANDBOX_PROVIDER.md** (updated
   3 days ago) — third-party engineering doc (Vercel repo-image builds inside
   sandboxes, snapshot precedence, shutdown lifecycle). Vercel write-ups
   flagged-only precedent applies.
6. **proagentstore/platform — docs/cloudflare-agent-stack-2026.md** (updated
   3 days ago; content as-of 2026-08-06, pre-window) — third-party
   Cloudflare Sandbox SDK analysis (unproven for persistent interactive
   sessions). Third-party analysis = flagged-only.
7. **dev.to/yuraoak — "E2B sandboxes: pricing, lifecycle and alternatives"**
   (Sep 23) — third-party pricing analysis; figures cited match
   vendor-verified corpus — no new pricing move. Flagged-only.

**Not counted:** Firecrawl $75M Series B (Sep 22, pre-window; web-data layer,
not sandbox VM infra); Bird.com $450M debt financing (comms infra, out of
lane); Factory $200M/$5B valuation (Sep 15, pre-window; coding-agent app);
CVE-2025-39964 (2025 kernel AF_ALG UAF, pre-window); Lokahi Therapeutics
"E2B" partnership + Veeva Falcon Safety "E2B systems" (pharma hits on the E2B
name); helgesverre/glue (Apr 2026), rars-oss/sbx (Sep 12), agentsystemlabs
mission-control removal plan (pre-window) — all pre-window or out of lane.

Stale-version rule mostly compliant with one review-caught exception:
Surveyor B grepped the last 3 watch docs + COMPETITOR_ANALYSIS.md for every
candidate, but CVE-2026-92940 (flagged-only on 2026-09-26, never folded into
the corpus) fell outside that window and was misfiled as new — corrected
above. Lesson for future passes: the corpus leg of the rule must cover the
full watch-doc series (or the docs/README.md index) for never-folded
flagged-only candidates, since COMPETITOR_ANALYSIS.md alone cannot catch
them.

**Corpus-health note for a future pass:** third-party comparison/analytics
content keeps accumulating in the lane (ryanalberts, cowork-genealogy,
kuanpak, colemurray, proagentstore) — all correctly flagged-only per
precedent, but a future pass could consider whether comparison write-ups
warrant their own section in COMPETITOR_ANALYSIS.md rather than per-item
flags. Not actioned this pass (doc-only delta scope).

## Verdict

**No new in-window in-lane launches this window; the sandbox-infrastructure
lane stays quiet.** Vendors: 9/9 unchanged; the all-first-try streak reaches
9 passes. News: 0 new, recrawls only. New-to-corpus sightings are all
flagged-only lane-adjacent items (Docker Engine escape CVE-2026-71443; six
third-party comparison/engineering write-ups; yuraoak E2B pricing analysis). Corpus
movement: **C11 (Baseten/Blaxel) ages out** (quiet pass 3 of 3 — one-notice
line above; no silent drop); C56 quiet pass 2 of 3; C62 recrawl contact
(count 0); C12 OPEN (AgentComputer still no egress line); aged-out stay out;
re-fold-path gap still open.
