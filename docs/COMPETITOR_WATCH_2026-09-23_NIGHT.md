# Competitor watch — 2026-09-23 (night)

Delta-only update against the late-evening pass
(`docs/COMPETITOR_WATCH_2026-09-23_LATE_EVENING.md`). Survey window
**2026-09-23 ~08:54 → 09:15 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the tracked set (reads ~08:57–08:59 CDT), (B) Vercel Drives GA
watch plus open-web market-news scan (~08:54–09:15 CDT). Surveyor
captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260923-0854.md`), not the repo.

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

Every baseline value from the ~08:01 CDT pass verified identical on
the vendor's own page, reads ~08:57–08:59 CDT. No fetch failures this
pass — all 9 vendor pages (DO = product + docs pages) fetched
successfully:

- **Daytona** — changelog top entry still **SEP 23 2026 / V0.216.0 —
  "Confine Dockerfile COPY sources to the build context"** (Python,
  Ruby, TypeScript SDKs); SEP 22 / V0.215.0 still second
  (**VERIFIED**: https://www.daytona.io/changelog, ~08:57).
- **Docker Sandboxes** — release notes still top out **2026-09-21**
  (v3 kits verbatim: `sbx mcp catalog` removal, guest-kernel-crash
  recovery, experimental outbound UDP); next entry still 2026-09-15
  (**VERIFIED**: https://docs.docker.com/ai/sandboxes/release-notes/,
  ~08:57).
- **Microsandbox** — top release still **v0.7.1** (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~08:57).
- **E2B** — pricing unchanged: Hobby **FREE / $100 one-time usage
  credit**, Pro **$150/month**, Enterprise **CUSTOM** ($3,000/mo
  minimum); per-second table still tops **$0.000014/s** per vCPU
  (**VERIFIED**: https://e2b.dev/pricing, ~08:58).
- **boat.dev** — rate card unchanged: small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h** (xlarge needs a
  $100 plan or higher); "A stopped sandbox costs nothing"; trial still
  25 free hours (**VERIFIED**: https://docs.boat.dev/pricing, ~08:58).
- **TermSquad** — tiers still Starter **$9/month** (2 vCPU / 4 GB),
  Builder **$19/month** (4 / 8), Power **$29/month** (6 / 12), Ultra
  **$49/month** (8 / 24); BYO-AI stance intact (**VERIFIED**:
  https://termsquad.com/, ~08:58).
- **DigitalOcean Managed Agents** — still **Public Preview**; hero
  still "under a couple of seconds" / "about 200 milliseconds"; docs
  index still **"Last verified 21 Sep 2026"**; Latest Updates still the
  21 September 2026 preview entry (**VERIFIED**:
  https://www.digitalocean.com/products/managed-agents and
  https://docs.digitalocean.com/products/managed-agents/, ~08:59).
- **AgentComputer** — pricing table identical (CPU **$0.07**/CPU-hour,
  memory **$0.04375**/GB-hour, hot **$0.000683**/GB-hour, cold
  **$0.000027**/GB-hour; Enterprise Custom); still **no stated egress
  policy** — C12 stands (**VERIFIED**:
  https://www.agentcomputer.ai/pricing, ~08:59).

## 2. Vercel Drives GA watch — NO-CHANGE (fifth consecutive)

The standing follow-up ask (does Drives move toward GA?) is answered
in the negative for the **fifth consecutive pass** (morning,
afternoon, evening, late evening, night — 2026-09-23):
`vercel.com/docs/sandbox/pricing` still shows `last_updated:
2026-09-10`, every baseline term verifies identical (Drive Storage 15
GB lifetime Hobby / $0.05/GB-month Pro+Enterprise; Reads 30 GB/mo then
$0.0015/GB; Writes 30 GB/mo then $0.004/GB; max 4 drives/run; default
1 TiB (1 GiB Hobby); 16 TiB max/drive; 64 GB ephemeral NVMe on SDK
≥3.0.0/custom image; session caps 45 min / 24 h; concurrency 10 /
10,000), the related-pages list still shows "Drives for Vercel Sandbox
are now in public beta" — no GA entry, no SLA terms — and the vendor
changelog's latest date bucket is still 22 September, with the 22
September Drives entry reading verbatim *"Drives for Vercel Sandbox
are now in public beta — Vercel Sandbox Drives, persistent storage you
mount into a sandbox, is now in public beta with drives up to 16 TiB
and usage-based pricing."* — no GA language (**VERIFIED**, pricing +
changelog re-read ~08:54–09:05; the vendor changelog confirms zero
entries dated 2026-09-23).

## 3. Market news — adjacent re-checks, nothing in-lane-launched

### 3a. DigitalOcean Managed Agents pricing re-check (C26 continuation)

The vendor docs index re-fetched this pass (**VERIFIED**:
https://docs.digitalocean.com/products/managed-agents/) carries **no
dollar pricing** — no $ figures, still "public preview", latest update
stamped **21 September 2026** (Managed Agents GA-in-public-preview for
all users, with Harness Runtime + Action Gateway). C26 stays open: the
pricing terms remain unverified on the vendor's own docs. Filed as C26
watch color, not a corpus entry (no new primary-source-verified fact
that shifts positioning).

### 3b. Adjacent re-checks (no new vendor-verified facts)

- **Automaid "always-on AI operations hub"** (2026-09-21 — still
  vendor-unconfirmed: coverage this run is aggregator-only —
  aiagentstore.ai news digests, "AI Agents News — Week of September
  23, 2026"; **THIRD-PARTY**, snippet-level). Same facts as prior
  passes: persistent agents, external triggers (Gmail/Slack), thousands
  of built-in integrations, own cloud environments, MCP/HTTP
  APIs/webhooks. (**INFERRED** lane judgment) Adjacent — a
  workflow-automation product with hosted agent runtimes, not a
  sandbox/VM SKU.
- **Andon Labs Pion research preview** (Sept 14 — **VERIFIED** on the
  vendor's own blog (https://andonlabs.com/blog/why-we-built-pion,
  confirmed in the late-evening pass, not re-read this run), and the
  Sept 15 adityas-tech-report adds only **THIRD-PARTY** color:
  managing agent "Andonos"; Andon Market (SF) on Claude Fable 5.1,
  Andon Café (Stockholm) on GPT-6 Astra, four radio stations on
  Gemini/Claude/GPT-5.6 Sol/Grok; seed tokens + revenue share for
  selected ideas; HN thread at 300+ points). No new in-window facts
  verified on Andon's own pages this run. (**INFERRED** lane judgment)
  Adjacent — a persistent-agent *ops platform* with its own compute,
  not a sandbox you provision.
- **Huawei Cloud "Open Agentic Cloud"** (Sept 18 — still
  **THIRD-PARTY** / press copies of vendor-announcement text; no
  Huawei vendor page available in search results this run): HUAWEI
  CONNECT 2026 coverage adds AI Cluster Service (AICS) global launch
  (five-level fast recovery, 40+ days stable training, 10-minute fault
  recovery, 20% higher token throughput — commercial availability China
  Sept 30, outside China Nov 30), Context Memory Storage
  (petabyte-scale, "twice the storage capacity of comparable industry
  products"), Agentic MaaS + AgentArts (5,000+ general / 1,000+
  industry MCP assets, 100+ customers, commercial outside China Dec
  30) / openJiuwen open source (>50,000 stars / 3.29M downloads).
  (**INFERRED** lane judgment) Adjacent — enterprise training/MaaS
  platform + infra, not a sandbox/compute-box product.
- **Borderline context (not new, THIRD-PARTY):** cryptobriefing.com
  reports OpenAI plans to unveil "Managed Agents" at DevDay 2026 (Sept
  29, San Francisco) — unified create/deploy-agent system with
  self-hosting options. The article is ~16 days old, so this is
  previously-visible context, not an in-window event; filed as watch
  color only.

### 3c. In-lane launches

No new launches found from E2B, Daytona, Docker, Vercel, boat.dev,
TermSquad, AgentComputer, Upstash Box, Boxd, Microsandbox, or Fly.io
Sprites in this window. **No always-on persistent-agent-machine
announcements — the fourth consecutive pass making the explicit
in-lane no-launch verdict (afternoon → evening → late evening →
night).**
(Search note: boat.dev queries this run returned only Indian
audio-company boAt "Crest AI" results — a different company; nothing
in the sandbox lane.)

## 4. No corpus fold this pass

Nothing primary-source-verified this pass shifts spark-vm's
positioning: the DO docs-page re-check is C26 watch color, the Andon /
Automaid / Huawei items stay THIRD-PARTY-adjacent color, and the
OpenAI DevDay note is out-of-window THIRD-PARTY context — none are new
competitors to add to the canonical corpus. No new C-numbers filed.
Next pass's ask: routine tracked-set re-reads; Vercel Drives GA watch
continues (sixth no-change pass incoming if quiet); re-check the DO
Managed Agents docs for published pricing terms when they appear.
