# Competitor watch — 2026-09-23 (late evening)

Delta-only update against the evening pass
(`docs/COMPETITOR_WATCH_2026-09-23_EVENING.md`). Survey window
**2026-09-23 ~07:55 → 08:15 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set (reads ~08:01–08:04 CDT), (B) Vercel Drives GA watch plus
open-web market-news scan (~07:55–08:15 CDT). Surveyor captures live in
the loop's `agent_notes/` workspace (`surveyor-a/b-20260923-0754.md`),
not the repo.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) rather than a vendor doc-page assertion — a stricter
claim than VERIFIED, used only when we fetched the thing itself.
**THIRD-PARTY** = reported by press/third-party sources, including
vendor-announcement text read on a syndicated copy (e.g. a Business
Wire release) rather than the vendor's own page.
**snippet-only** = a THIRD-PARTY sub-state: seen only via search
snippet or aggregator digest this run, not fetched and read — no
stronger claim than its source's blurb.
**INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.
**UNVERIFIED** = a public page exists but could not be fetched this
run (never reported as NO-CHANGE).

## 1. The tracked set — fully quiet (8/8 NO-CHANGE, all VERIFIED)

Every baseline value from the ~06:58 CDT pass verified identical on
the vendor's own page, reads ~08:01–08:04 CDT:

- **Daytona** — changelog top entry still **SEP 23 2026 / V0.216.0 —
  "Confine Dockerfile COPY sources to the build context"** (Python,
  Ruby, TypeScript SDKs); V0.215.0 (SEP 22) still second (**VERIFIED**:
  https://www.daytona.io/changelog, ~08:01).
- **Docker Sandboxes** — release notes still top out **2026-09-21**
  (v3 kits verbatim: `sbx mcp catalog` removal, guest-kernel-crash
  recovery, experimental outbound UDP); next entry still 2026-09-15
  (**VERIFIED**: https://docs.docker.com/ai/sandboxes/release-notes/,
  ~08:01).
- **Microsandbox** — top release still **v0.7.1** (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~08:02).
- **E2B** — pricing unchanged: Hobby **FREE / $100 of usage in
  credits** ("$100 one-time usage credit"), Pro **$150/month**,
  Enterprise **CUSTOM** ($3,000/mo minimum); per-second table still tops
  **$0.000014/s** per vCPU (**VERIFIED**: https://e2b.dev/pricing,
  ~08:02).
- **boat.dev** — rate card unchanged: small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h** (xlarge needs a
  $100 plan or higher); "A stopped sandbox costs nothing"; trial still
  25 free hours, 2 sandboxes at once, small and default only, until
  first payment (**VERIFIED**: https://docs.boat.dev/pricing, ~08:02).
- **TermSquad** — tiers still Starter **$9/month** (2 vCPU / 4 GB),
  Builder **$19/month** (4 / 8), Power **$29/month** (6 / 12), Ultra
  **$49/month** (8 / 24); BYO-AI stance intact (**VERIFIED**:
  https://termsquad.com/, ~08:03).
- **DigitalOcean Managed Agents** — still **Public Preview**; hero
  still "under a couple of seconds" / "about 200 milliseconds"; docs
  index still **"Last verified 21 Sep 2026"**; Latest Updates still the
  21 September 2026 preview entry (**VERIFIED**:
  https://www.digitalocean.com/products/managed-agents and
  https://docs.digitalocean.com/products/managed-agents/, ~08:03).
- **AgentComputer** — pricing table identical (CPU **$0.07**/CPU-hour,
  memory **$0.04375**/GB-hour, hot **$0.000683**/GB-hour, cold
  **$0.000027**/GB-hour; Enterprise Custom); still **no stated egress
  policy** — C12 stands (**VERIFIED**:
  https://www.agentcomputer.ai/pricing, ~08:04).

## 2. Vercel Drives GA watch — NO-CHANGE (fourth consecutive)

The standing follow-up ask (does Drives move toward GA?) is answered in
the negative for the **fourth consecutive pass** (morning, afternoon,
evening, late evening — 2026-09-23): `vercel.com/docs/sandbox/pricing`
still shows `last_updated: 2026-09-10`, every baseline term verifies
identical (Drive Storage 15 GB lifetime Hobby / $0.05/GB-month
Pro+Enterprise; Reads 30 GB/mo then $0.0015/GB; Writes 30 GB/mo then
$0.004/GB; max 4 drives/run; default 1 TiB (1 GiB Hobby); 16 TiB
max/drive; 64 GB ephemeral NVMe on SDK ≥3.0.0/custom image; session
caps 45 min / 24 h; concurrency 10 / 10,000), and the vendor
changelog's 22 September Drives entry still reads verbatim *"Drives
for Vercel Sandbox are now available in public beta on Hobby, Pro,
and Enterprise"* — no GA date, no SLA terms, no GA language
(**VERIFIED**, pricing + changelog entry pages re-read ~07:55–08:05;
the vendor changelog confirms zero entries dated 2026-09-23). SDK
changelogs show Drives support landed in @vercel/sandbox 3.3.0 /
sandbox CLI 4.4.0 (snippet-only, ≥5 days old) — no newer release this
window.

## 3. Market news — new same-lane color, nothing in-lane-launched

### 3a. DigitalOcean Managed Agents follow-up (C26 continuation)

The vendor docs' agent-harness-runtime page now renders (**VERIFIED**:
https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/,
fetched this pass): "Generated on 23 Sep 2026"; the preview entry reads
"21 September 2026 — Managed Agents is now available in public preview
for all users"; the details page promises use cases, features, pricing,
availability, and limits. Specific dollar pricing was NOT found in the
docs copy fetched this pass — pricing terms stay unverified on the
vendor's own docs. Filed as C26 watch color, not a corpus entry (no
new primary-source-verified fact that shifts positioning).

### 3b. AWS Lambda MicroVMs for self-hosted AI agent sandboxes — same-lane reference architecture

Newly surfaced to the baseline (pre-window — posted ~5 days ago, not an
in-window launch): the AWS compute blog walks through running
self-hosted AI agent sandboxes on Lambda MicroVMs (**VERIFIED**:
https://aws.amazon.com/blogs/compute/running-self-hosted-ai-agent-sandboxes-with-aws-lambda-microvms/)
— per-session Firecracker isolation, snapshot-based launch,
pay-only-for-active-execution billing, idle policies that terminate the
VM. Not a hosted-always-on SKU (an anti-always-on billing model), but a
same-lane **reference architecture** for serverless agent-sandbox
control planes — worth keeping on the watch list as design color, not
a corpus entry.

### 3c. Herdr × Vercel Sandbox plugin — same-lane validation of one-agent-one-machine

Newly surfaced (Vercel changelog, **VERIFIED**, 2026-09-22 window): the
Herdr plugin runs each terminal coding agent (Claude Code, Codex,
OpenCode) in its own persistent Vercel Sandbox, orchestrated from
Herdr's tmux pane manager — with a reviewed-upload gate,
credential-never-leaves-sandbox, and git-patch apply. This is a
**same-lane** datapoint validating the "one agent, one persistent
machine" model spark-vm's hosted product is betting on — filed as watch
color, not a new tracked provider (it is Vercel Sandbox usage, not a
new sandbox SKU).

### 3d. Adjacent color (not same-lane)

- **Google PM's "Always On Memory Agent"** (open source, ADK + Gemini
  3.1 Flash-Lite, MIT — **THIRD-PARTY**, VentureBeat snippet-only):
  a persistent-memory reference implementation, not a hosted product.
  Signal on long-running agent demand, not infra competition —
  adjacent.
- **Andon Labs Pion research preview** (Sept 14 — **VERIFIED** on the
  vendor's own blog, https://andonlabs.com/blog/why-we-built-pion:
  "Pion is available as a research preview… sign up on our waitlist"):
  persistent agents running real businesses (email, phone, banking,
  browser, secure compute env); YC-backed; grew out of Vending-Bench
  experiments. Adjacent — a persistent-agent *ops platform* with its
  own compute, not a sandbox you provision.
- **Automaid "always-on AI operations hub"** (2026-09-21 — still
  vendor-unconfirmed: own-page confirmation failed this pass; only
  press coverage — https://itbrief.asia/story/automaid-launches-ai-hub-for-agents-that-keep-working,
  **THIRD-PARTY**, plus aggregator digest snippet-only). Adjacent — a
  workflow-automation product with hosted agent runtimes, not a
  sandbox/VM SKU.
- **Huawei Cloud "Open Agentic Cloud"** (announced Sept 18/19 — still
  **THIRD-PARTY** / snippet-only via syndicated rollout copy):
  Agentic MaaS, AgentArts agent platform, openJiuwen open source,
  Context Memory Storage, Industry AI Foundry zones. Adjacent —
  enterprise agent-platform/MaaS play, not a hosted agent-sandbox SKU.

### 3e. In-lane launches

No new launches found from E2B, Daytona, Docker, Vercel, boat.dev,
TermSquad, AgentComputer, Upstash Box, Boxd, Microsandbox, or Fly.io
Sprites in this window.

## 4. No corpus fold this pass

Nothing primary-source-verified this pass shifts spark-vm's
positioning: the DO docs-page read is C26 watch color, and the AWS
Lambda MicroVMs blog plus the Herdr × Vercel plugin are same-lane
*usage/reference-architecture* color — not new competitors to add to
the canonical corpus. Next pass's ask: routine tracked-set re-reads;
Vercel Drives GA watch continues; re-check the DO Managed Agents docs
for published pricing terms when they appear.
