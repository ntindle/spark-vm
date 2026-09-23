# Competitor watch — 2026-09-23 (evening)

Delta-only update against the afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-23_AFTERNOON.md`). Survey window
**2026-09-23 ~06:58 → 07:15 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set (reads ~06:58 CDT), (B) Vercel Drives GA watch plus
open-web market-news scan (~06:58–07:15 CDT).

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) rather than a vendor doc-page assertion — a stricter
claim than VERIFIED, used only when we fetched the thing itself.
**THIRD-PARTY** = reported by press/third-party sources.
**INFERRED** = my characterization, labeled as such.
**UNVERIFIED** = a page could not be fetched this run (never reported
as NO-CHANGE).

## 1. The tracked set — fully quiet (8/8 NO-CHANGE, all VERIFIED)

Every baseline value from the ~05:56 CDT pass verified identical on
the vendor's own page, reads ~06:58 CDT:

- **Daytona** — changelog top entry still **SEP 23 2026 / V0.216.0 —
  "Confine Dockerfile COPY sources to the build context"** (Python,
  Ruby, TypeScript SDKs); V0.215.0 (SEP 22) still second (**VERIFIED**:
  https://www.daytona.io/changelog, ~06:58).
- **Docker Sandboxes** — release notes still top out **2026-09-21**
  (v3 kits verbatim: `sbx mcp catalog` removal, guest-kernel-crash
  recovery, experimental outbound UDP); next entry still 2026-09-15
  (**VERIFIED**: https://docs.docker.com/ai/sandboxes/release-notes/,
  ~06:58).
- **Microsandbox** — top release still **v0.7.1** (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~06:58).
- **E2B** — pricing unchanged: Hobby **FREE / $100 of usage in
  credits** ("$100 one-time usage credit"), Pro **$150/month**,
  Enterprise **CUSTOM** ($3,000/mo minimum); per-second table still tops
  **$0.000014/s** per vCPU (**VERIFIED**: https://e2b.dev/pricing,
  ~06:58).
- **boat.dev** — rate card unchanged: small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h** (xlarge needs a
  $100 plan or higher); "A stopped sandbox costs nothing"; trial still
  25 free hours, 2 sandboxes at once, small and default only, until
  first payment (**VERIFIED**: https://docs.boat.dev/pricing, ~06:58).
- **TermSquad** — tiers still Starter **$9/month** (2 vCPU / 4 GB),
  Builder **$19/month** (4 / 8), Power **$29/month** (6 / 12), Ultra
  **$49/month** (8 / 24); BYO-AI stance intact (**VERIFIED**:
  https://termsquad.com/, ~06:58).
- **DigitalOcean Managed Agents** — still **Public Preview**; hero
  still "under a couple of seconds" / "about 200 milliseconds"; docs
  index still **"Last verified 21 Sep 2026"**; Latest Updates still the
  21 September 2026 preview entry (**VERIFIED**:
  https://www.digitalocean.com/products/managed-agents and
  https://docs.digitalocean.com/products/managed-agents/, ~06:58).
- **AgentComputer** — pricing table identical (CPU **$0.07**/CPU-hour,
  memory **$0.04375**/GB-hour, hot **$0.000683**/GB-hour, cold
  **$0.000027**/GB-hour; Enterprise Custom); still **no stated egress
  policy** — C12 stands (**VERIFIED**:
  https://www.agentcomputer.ai/pricing, ~06:58).

## 2. Vercel Drives GA watch — NO-CHANGE (third consecutive)

The standing follow-up ask (does Drives move toward GA?) is answered in
the negative for the **third consecutive pass** (morning, afternoon,
evening — 2026-09-23): `vercel.com/docs/sandbox/pricing` still shows
`last_updated: 2026-09-10`, every baseline term verifies identical
(Drive Storage 15 GB lifetime Hobby / $0.05/GB-month Pro+Enterprise;
Reads 30 GB/mo then $0.0015/GB; Writes 30 GB/mo then $0.004/GB; max 4
drives/run; default 1 TiB (1 GiB Hobby); 16 TiB max/drive; 64 GB
ephemeral NVMe on SDK ≥3.0.0/custom image; session caps 45 min / 24 h;
concurrency 10 / 10,000), and the vendor changelog's 22 September
Drives entry still reads verbatim *"…is now in public beta"* — no GA
date, no GA commitment, no wording change (**VERIFIED**, both pages
re-read ~06:58–07:05; the vendor changelog sitemap confirms no entries
dated 2026-09-23 at all). SDK changelogs show Drives support landed in
@vercel/sandbox 3.3.0 / sandbox 4.4.0 (snippet-only, ≥5 days old) —
no new release this window.

## 3. Market news — one material 48h-window item, nothing in-window

### 3a. DigitalOcean Managed Agents public preview (announced 2026-09-22) — THIRD-PARTY vendor-announcement color

Fresh in-window **THIRD-PARTY** detail (DigitalOcean's own
announcement, syndicated via Business Wire, read as a syndicated copy —
not vendor-fetched):
https://www.businesswire.com/news/home/20260922295615/en/DigitalOcean-Launches-Managed-Agents-Bringing-Agent-Execution-Tool-Access-and-Inference-Together-on-One-Cloud

- Per-session architecture: "Every Managed Agents session runs in its
  own isolated harness runtime" — Firecracker microVM with
  pause/resume/checkpoint/fork; bring-your-own harness (Claude Code,
  Codex CLI, OpenCode, Hermes, LangGraph, custom OCI images); governed
  tool access via Action Gateway (16,000+ tools, credentials brokered at
  execution time); Serverless Inference across 75+ models.
- Pricing detail via **THIRD-PARTY** summary
  (https://subagentic.ai/posts/digitalocean-managed-agents-preview/):
  "$0.044 per vCPU-hour and $0.0095 per GB-hour", CPU billed by actual
  consumption per second; DigitalOcean's own social copy
  (**THIRD-PARTY**, vendor social, ~17h old) illustrates: "An hour of
  agent work that bills $0.126 fully allocated costs about $0.0310 with
  us for a typical agent run (25% active). While the agent waits, you pay
  zero." New DigitalOcean users receive a $5 credit.
- **INFERRED assessment:** this is per-session pause/resume agent
  compute with active-CPU billing — adjacent to spark-vm's lane, not the
  same product. DigitalOcean positions itself explicitly as the
  "AI-native cloud" versus the provisioned VM: the press framing is
  "no more provisioning VMs", i.e. anti-always-on as a value
  proposition. It is competitive pressure on hosted agent-infrastructure
  *pricing*, not an always-on persistent-machine announcement. Filed as
  lane color against C26 (DO watch) — not a corpus entry (vendor-facts
  third-party-carried, and it does not shift spark-vm's positioning).
- OpenHands, Qencode, Amplitude are building on it (per the release) —
  third-party ecosystem color.

### 3b. Borderline (pre-window, snippet-only color)

- **Automaid "always-on AI operations hub"** (2026-09-21 aggregator
  digest) — agents keep working beyond a chat session from "their own
  cloud environments"; vendor page not verified this pass —
  snippet-only unless a later pass confirms.
- **Andon Labs Pion** research preview (Sept 14) — persistent agents
  with terminal/email/phone/browser + supervisor agent; waitlist-only;
  snippet-only.
- **Huawei Cloud "Open Agentic Cloud"** (Sept 19) — AICS compute +
  Context Memory Storage + Agentic MaaS; enterprise/training-focused;
  snippet-only.
- **Meta Muse** (Sept 8) — per-user dedicated cloud-hosted VM, no
  change since earlier passes.
- Sandy sandbox-landscape note that "Daytona… core went closed-source
  June 2026" — already known, not news.

### 3c. Quiet in-window

The last ~6 hours: no new launches, raises, pricing changes, or
deprecations surfaced. E2B / Daytona / Modal / AgentSphere — nothing.
**No competitor announced anything resembling always-on persistent
agent machines — the always-on hosted-VM niche (the spark-vm lane) had
no new entrants or pricing pressure this run.**

## 4. Standing items / carry-forwards

- **C14 (#47 resume-latency target):** still OPEN — needs our own
  measured provider baseline; the operator per-run Fly spend-cap
  decision is still owed (NEEDS_USER.md). DO's pause/resume
  Firecracker harness (per-session, not always-on) is not a substitute
  input for a spark-vm always-on baseline.
- **C26 (DO Managed Agents):** launch detail added this pass
  (businesswire syndicated announcement + third-party pricing); watch
  continues at routine cadence — the GA/pricing evolution matters more
  than the launch itself.
- **C29 (Boxd):** quiet this pass; watch continues at routine cadence.
- **C12, C10:** stand, unchanged.
- **Cloudflare Sandbox:** no new signal; deprioritized retained.
- **Next pass's ask:** routine tracked-set re-reads; Vercel Drives GA
  watch continues (still public beta, page last_updated 2026-09-10;
  three consecutive no-change passes).

---

*Corpus note:* per the delta-only convention, watch docs record deltas
against the previous pass and the corpus changes only via
consolidation or primary-source verification. The DO Managed Agents
detail is vendor-facts carried third-party and does not shift
spark-vm's competitive positioning — **no corpus fold** this pass. The
two surveyor captures are archived verbatim in the loop's
`agent_notes/` (workspace-only), not the repo.
