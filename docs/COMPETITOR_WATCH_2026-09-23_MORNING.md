# Competitor watch — 2026-09-23 (morning)

Delta-only update against the ~02:25 CDT pass
(`docs/COMPETITOR_WATCH_2026-09-23.md`). Survey window
**2026-09-23 ~04:56 → 05:00 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set (reads ~04:56–04:58 CDT), (B) Vercel Drives GA watch plus
open-web market-news scan (~04:56–05:00 CDT).

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) rather than a vendor doc-page assertion — a stricter
claim than VERIFIED, used only when we fetched the thing itself.
**THIRD-PARTY** = reported by press/third-party sources.
**INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.

## 1. Deltas (2 of 8 tracked providers moved)

### 1a. Daytona v0.216.0 — SDK build-context hardening (VERIFIED)

The changelog top entry is now **SEP 23 2026 / V0.216.0 —
"Confine Dockerfile COPY sources to the build context"** (**VERIFIED**:
https://www.daytona.io/changelog, read ~04:57): *"Daytona 0.216.0
restricts Dockerfile COPY sources to the build context in the Python,
Ruby, and TypeScript SDKs."* The V0.215.0 entry (SEP 22) now sits
second.

This is a security-hardening patch, not a feature: COPY escaping the
build context is a classic sandbox-breakout vector (reading host files
into the image at build time), so a provider locking it down in the
SDKs reads as incident-driven hardening of the trust boundary (INFERRED).
Filed
here as routine watch color (filed C33); no corpus-fold — it doesn't
move competitive positioning. Worth the contrast note for the corpus's
trust-signals discussion: Daytona is closing trust-boundary gaps in
public; spark-vm's jail/proxy enforcement-downgrade posture (C22)
should hold to the same "closed boundary by default" bar.

### 1b. Docker Sandboxes 2026-09-21: v3 kits — OCI-packaged agent kits with mixins (VERIFIED)

Release notes now top out at **2026-09-21** (**VERIFIED**:
https://docs.docker.com/ai/sandboxes/release-notes/, read ~04:57):
*"Docker Sandboxes now supports v3 kits: OCI-based packages that
combine an agent workload with reusable mixins for tools,
configuration, credentials, network access, and agent instructions."*
The same release ships `sbx mcp catalog` removal, guest-kernel-crash
recovery, and experimental outbound UDP (noted, not analyzed this
pass).

Why this matters for spark-vm (filed C34): the corpus's sandbox
product thesis is moving toward per-harness adapter packaging — the
same idea as H4's OpenSandbox-style adapter contract (harness code +
compute isolation packaged as a deployable unit). Docker has now
shipped a packaged implementation of that idea (INFERRED): an OCI artifact that
bundles workload + tools + config + credentials + network policy +
agent instructions as one portable unit. The corpus's Docker
Sandboxes field-table row already lists "kits"; this pass upgrades
the entry to v3 semantics (OCI-packaged, mixin composition) and notes
the competitive pressure on the adapter thesis: portability via
standard artifact formats (OCI) beats per-provider custom packaging.
Color for H4's design discussions — the OpenSandbox adapter contract
should keep OCI-shaped packaging on the table. No pricing change and no
change in Docker's own market positioning; this is capability news.

## 2. The tracked set — quiet elsewhere (6/8 NO-CHANGE, all VERIFIED)

- **Microsandbox** — top release still **v0.7.1** (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~04:57).
- **E2B** — pricing unchanged: Hobby free + $100 one-time credit, Pro
  $150/mo, Enterprise custom ($3,000/mo minimum); per-second table tops
  $0.000014/s per vCPU (**VERIFIED**: https://e2b.dev/pricing, ~04:57).
- **boat.dev** — rate card unchanged: small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h**; "A stopped
  sandbox costs nothing"; trial: 25 free hours, 2 sandboxes at once,
  small and default only, until first payment (**VERIFIED**:
  https://docs.boat.dev/pricing, ~04:57).
- **TermSquad** — tiers still Starter **$9** / Builder **$19** / Power
  **$29** / Ultra **$49**; BYO-AI stance intact (**VERIFIED**:
  https://termsquad.com/, ~04:57).
- **DigitalOcean Managed Agents** — product page unchanged (Public
  Preview; hero "under a couple of seconds" / "about 200
  milliseconds"; Tool Playground, scheduled/webhook triggers); docs
  index still "Last verified 21 Sep 2026" (**VERIFIED**:
  https://www.digitalocean.com/products/managed-agents and
  https://docs.digitalocean.com/products/managed-agents/, ~04:57).
- **AgentComputer** — pricing unchanged (CPU $0.07/CPU-hour, memory
  $0.04375/GB-hour, hot storage $0.000683/GB-hour, cold
  $0.000027/GB-hour); still **no stated egress policy** — C12 stands
  (**VERIFIED**: https://www.agentcomputer.ai/pricing, ~04:57).

## 3. Vercel Drives GA watch — NO-CHANGE

The C32 follow-up ask (does Drives move toward GA?) is answered in
the negative this pass: `vercel.com/docs/sandbox/pricing` still shows
page metadata `last_updated: 2026-09-10`, and every baseline term
verifies identical (Drive Storage 15 GB lifetime Hobby /
$0.05/GB-month Pro+Ent; Drive Reads 30 GB/mo then $0.0015/GB; Drive
Writes 30 GB/mo then $0.004/GB; max 4 drives/run; default 1 TiB
(1 GiB Hobby); 16 TiB max/drive; 64 GB ephemeral NVMe on SDK ≥3.0.0 /
custom image; session caps 45 min / 24 h; concurrency 10 / 10,000).
The vendor changelog's latest Drives entry (22 September) still reads
verbatim *"…is now in public beta"* — no GA date, no GA commitment,
no wording change anywhere on either page (**VERIFIED**, both pages
re-read ~04:58).

## 4. Market news — quiet window

Surveyor B's open-web scan (last ~48h across Daytona, E2B, Fly.io,
DigitalOcean, Modal, Vercel, CodeSandbox, Railway, Render, Firecrawl,
Northflank, Runloop, new entrants) surfaced no genuine news deltas —
no launches, pricing changes, raises, or GA moves in the window. The
newest funding event found is Daytona's $24M Series A (FirstMark,
Feb 2026) — ~7 months old, press re-reporting only (THIRD-PARTY). A
THIRD-PARTY op-ed (codeongrass.com blog) argues Daytona's 24/7 cost
math (~$120+/mo for 2 vCPU/4GB) loses to Hetzner-based alternatives
($6–9/mo) — relevant framing for spark-vm's flat-rate ~$20/mo
thesis, but an op-ed, not a vendor-verified fact; filed as context
only. **No competitor announced anything resembling always-on
persistent agent machines — the always-on hosted-VM niche (the
spark-vm lane) had no new entrants or pricing pressure this run.**

## 5. Standing items / carry-forwards

- **C14 (#47 resume-latency target):** still OPEN — needs our own
  measured provider baseline; the operator per-run Fly spend-cap
  decision is still owed (NEEDS_USER.md). No new benchmark-grade input
  this pass.
- **C29 (Boxd):** watch continues at routine cadence; no new signal.
- **C26 (DO watch):** quiet this pass; vendor pages unchanged.
- **C12, C10:** stand, unchanged.
- **Cloudflare Sandbox:** no new signal; deprioritized retained.
- **Next pass's ask:** routine tracked-set re-reads; Vercel Drives GA
  watch continues (still public beta, page last_updated 2026-09-10).

---

*Corpus note:* per the delta-only convention, watch docs record deltas
against the previous pass and the corpus changes only via
consolidation or primary-source verification. This pass carries one
primary-source VERIFIED item that shifts the competitive context for the
adapter thesis (Docker Sandboxes v3 kits — filed C34, corpus-folded in this same PR
into the Docker Sandboxes entry + new "Watch update — 2026-09-23
(morning)" corpus section, provenance-labeled). The Daytona v0.216.0
patch (filed C33) is watch-doc color only — no corpus fold. The two
surveyor captures are archived verbatim in the loop's `agent_notes/`
(workspace-only), not the repo.
