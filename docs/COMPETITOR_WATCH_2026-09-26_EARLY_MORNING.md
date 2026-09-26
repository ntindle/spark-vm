# Competitor watch — 2026-09-26 (early morning)

Two-surveyor pass: (A) tracked-set re-verification vs the ~02:55 CDT
baseline, (B) open-ask pushes + new-launch scan. Survey window
**2026-09-26 ~03:58–04:15 CDT**; read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-0354.md`,
`agent_notes/surveyor-b-20260926-0354.md` (goal-workspace notes, not
in the repo).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read
this run and the item is confirmed not present on it.

## 1. C26 — DigitalOcean Managed Agents: snapshot-rate conflict resolved 2:1, active-CPU conflict narrowed (in-lane, VENDOR-VERIFIED)

The carried C26 open asks narrowed materially this pass — both toward
resolution.

**A second vendor-owned dollar-pricing surface found**
(`digitalocean.com/pricing/harness-runtime`, VERIFIED full read this
run):

- Billing per second for actual consumption: CPU **$0.044/vCPU-hour**
  ("actual CPU consumed"), memory **$0.0095/GB-hour** ("peak memory
  used"), session storage (volumes) **$0.05/GiB-month**, **snapshots
  and checkpoints $0.05/GiB-month**, custom sandbox templates (BYOT)
  **$0.05/GiB-month**, public internet egress **$0.01/GiB**.
- Shape table at full allocation: XSmall (1 vCPU/1 GB) $0.0535/hr,
  Small (2/2) $0.107/hr, Medium (2/4) $0.126/hr, Large (4/8)
  $0.252/hr, XLarge (16/32) $1.008/hr. Harness Runtime requires a
  positive prepaid account balance.
- **"Active CPU billing is coming soon. Until then, you will be billed
  at 25% of the vCPUs allocated to your sandbox.** Paused sessions
  incur no compute charges."
- Launch blog pricing example (VERIFIED full read,
  `digitalocean.com/blog/managed-agents-public-preview`): "a session
  with two vCPUs averaging 25% CPU utilization and a measured memory
  peak of 4 GB throughout an hour would cost $0.060 in CPU and memory
  charges, compared with $0.126 for a full hour of that allocated
  capacity."

**Conflict (a) — snapshots $0.005 vs $0.05 — resolved 2:1.** Two
vendor-owned surfaces now print $0.05/GiB-month (the docs pricing
subpage, VENDOR-VERIFIED 2026-09-25 late morning, *and* the new
pricing/harness-runtime page); only the 2026-09-22 investor-relations
launch page prints $0.005 (VENDOR-VERIFIED, re-read this run — still
no correction, no new date). The pricing page is the billing surface
of record: treat **$0.05/GiB-month as authoritative** and the IR page's
$0.005 as a release-text typo (INFERRED). The blast-radius scope
stands from the 2026-09-25 midday pass: compute and memory agree
exactly across both surfaces; only Snapshots and Checkpoints disagree.

**Conflict (b) — active-CPU "live" vs "coming soon" — narrowed toward
the docs footnote.** The new pricing page sides with the docs
footnote: active-CPU billing is coming soon; interim billing is 25%
of allocated vCPUs. The investor-relations page's live framing is the
oddity, not the docs.

**The "Details pricing subpage" open ask is superseded.** The product
docs page (`docs.digitalocean.com/products/managed-agents/`, "Last
verified 21 Sep 2026") still carries **no dollar pricing — VERIFIED
absent** — but the dollar-pricing ask is now answered by the
pricing/harness-runtime surface above. C26's two conflicts are closed
with evidence; only DO's own IR-page corrections remain open
(vendor-side, watch-only). **C26 moves to CLOSED-resolved this pass.**

Corpus fold: the DO Managed Agents row's price-signal cell gains the
pricing/harness-runtime facts and the 2:1 resolution (provenance
labeled), and this section records the full read.

## 2. C48 — Prime Intellect Prime Sandboxes: BACKLOG ask is stale, figures hold (no drift)

The BACKLOG ask "C48 GA vendor-sourced at snippet level
(VENDOR-VERIFIED full-page reads still owed)" is **stale** — the
corpus row already records 2026-09-25 afternoon full-page vendor
reads, and this pass re-read the vendor docs live ("Last Updated:
1 day ago"): the filed figures hold verbatim — **CPU $0.02/vCPU-hr,
memory $0.0125/GiB-hr, disk $0.0002/GiB-hr, "valid through December
22, 2026"**, example 1 vCPU / 2 GiB / 5 GiB → $0.046/hr; CPU-only
access today, GPU microVMs / snapshots / forking / shared persistent
workspaces on roadmap. **No drift; no corpus change; the ask closes
in BACKLOG.md this pass.** (THIRD-PARTY color from AlphaSignal: "one
of the largest environment catalogs available from a sandbox
provider", ~one-third of other large providers' rates, 30M
environments claimed, $3.89/hr for 100 of the example config.)

## 3. "Boat DELTA" label: UNVERIFIED as a vendor announcement brand

Boat.dev homepage (VERIFIED full read) and three web searches found
**no DELTA-branded announcement, product, tier, or changelog entry**.
The pricing facts folded from `docs.boat.dev/pricing` in the
2026-09-25 post-pre-midnight pass are vendor-verified pricing facts
and stand on their own; only the *DELTA as a product announcement*
framing is unverifiable. Future passes should cite the Boat facts
without the DELTA banner. (Verbatim homepage vendor-claims captured
for future passes — marketing claims below are vendor-claims, not
evidence: "$20 plan = $20 of sandbox time", "$0.036/hour"
for 4 vCPU / 8 GB / 50 GB, per-second billing while running, EU
regions Germany/Finland/France with data and snapshots staying there,
FAQ "Am I billed when a sandbox is stopped? No. Stopping snapshots
the sandbox and pauses billing", API docs listing harness providers
codex, claude-code, pi, opencode, prime-agent, kimi.)

## 4. Tracked-set re-verification (targeted — fast movers + pricing sweep)

All reads live this run, ~03:58–04:00 CDT, vs the ~02:55 baseline:

- **Daytona changelog** — VERIFIED NO-CHANGE. Top: SEP 26 2026
  V0.218.0 (`kvm` sandbox-creation parameter in every SDK + CLI login
  moved to dedicated WorkOS application), SEP 25 2026 V0.217.0
  (NVIDIA B300 GPU type), SEP 24 2026 V0.216.1.
- **Docker Sandboxes release notes** — VERIFIED NO-CHANGE. Newest
  dated heading still 2026-09-22 (v0.45.1: improved sandbox moves +
  private kit images in cloud sandboxes).
- **Microsandbox releases** — VERIFIED NO-CHANGE. v0.7.3 on top,
  then v0.7.1.
- **Vercel changelog** — VERIFIED NO-CHANGE. Top entries still dated
  25 Sep (vcr-action/login, Pixel Canary on AI Gateway — out-of-lane,
  Sandbox memory observability). **No 26-Sep entries — the
  headline-find slot is empty.**
- **Vercel Sandbox pricing** — VERIFIED NO-CHANGE.
  `last_updated: 2026-09-10`; Drives still **public beta** (GA watch
  NO-CHANGE continues).
- **Pricing sweep — VENDOR-VERIFIED NO-CHANGE**: E2B (Hobby $0 +
  $100 one-time credit, 1h sessions, 20 concurrent; Pro $150/mo, 24h
  sessions), Modal (sandbox tier ≈3× standard — 3.01x CPU
  ($0.00003942 vs $0.0000131/core-sec), 3.00x memory, ratio now
  measured to full precision),
  TermSquad ($9/$19/$29/$49), Fly.io Sprites ($0.07/CPU-hr,
  $0.04375/GB-hr, hot $0.000683/GB-hr, cold $0.000027/GB-hr),
  Northflank ($0.01667/vCPU-hr), Cloudflare Sandbox SDK ($0.072
  vCPU-hr active CPU, $0.009/GiB-hr provisioned).
- **AgentComputer pricing — UNVERIFIED this run** (local worker
  transport error, not retried per policy — no NO-CHANGE claim
  possible).

Fetch failures: 1 upstream 404 on a mistyped Cloudflare path
(recovered to the correct `/containers/platform/pricing/`), 1 local
transport failure (AgentComputer). Zero others.

## 5. Carried and adjacent

- **C37 (Freestyle Pro monthly fee): VERIFIED NO-CHANGE**
  (freestyle.sh/pricing read live ~04:00 CDT — Pro fee still not
  printed; Hobby $50/mo in FAQ: "so $50 on Hobby covers your first
  $50 of usage"; rate card verbatim). Dashboard-signed-in check
  still owed to a future pass. OPEN.
- **C57 (Baponi) / C58 (Leap0): OPEN, not re-surveyed this pass**
  (honest record: this pass's second surveyor carried a mislabeled
  brief — C57 "Boat DELTA", C58 "DO public-preview" — and verified
  neither; the canonical C57/C58 = Baponi/Leap0 stand in the corpus
  from the 2026-09-25 post-pre-midnight fold, still THIRD-PARTY-only).
- **Automaid**: no vendor page found — no-change. **Andon Pion**:
  still THIRD-PARTY-only (explainx.ai, Sep 15: research-preview
  platform handing a persistent AI agent email/phone/banking/browser/
  secure compute; waitlist-only; demo café "currently losing money on
  token costs alone"; HN >300 points) — no-change on vendor presence.
- **Huawei Open Agentic Cloud** (THIRD-PARTY): new color since last
  filing — AICS "commercially available in China on September 30 and
  in markets outside China on November 30"; Context Memory Storage
  "petabyte-scale memory space … 50% higher performance than
  comparable industry products"; AgentArts open-source (openJiuwen)
  "surpassed 50,000 GitHub stars and 3.29 million downloads, serving
  over 3,500 customers"; Industry AI Foundry "1,000+ industry assets
  and deployed over 1,000 projects" + Smart Government / AI Hardware
  zones; MiniMax multimodal demo on MaaS.
- Adjacent watch color: WSO2 Agent Manager announced GA (governance
  control plane with "sandboxed runtime" — mid-Sept); THIRD-PARTY
  E2B pricing color from startupik (Sep 22): "Pro $150/mo +
  per-second CPU/RAM" — corroborates the vendor page, third-party
  only.

## 6. Verdict

- **C26 (in-lane) CLOSED-resolved**: the snapshot-rate conflict
  resolves 2:1 for **$0.05/GiB-month** (docs subpage +
  pricing/harness-runtime vs the IR page's $0.005, treated as a
  release-text typo); the active-CPU conflict narrows toward the docs
  footnote (coming soon; interim 25% of allocated) — the pricing page
  is now the authoritative billing surface. Corpus-folded this pass.
- **C48 stale-ask closed** (no drift). **No new C-numbers.**
- Tracked set this pass: **4/4 fast movers VENDOR-VERIFIED
  NO-CHANGE**; pricing sweep VENDOR-VERIFIED NO-CHANGE (AgentComputer
  UNVERIFIED — transport failure, no claim); Vercel Drives GA watch
  NO-CHANGE (still public beta).
- In-lane no-launch verdict dated 2026-09-25 stands — **streak
  extends** (no new launches since the 02:24 morning pass, whose
  C59/C60 finds shipped in PR #466).
- **Carried:** C37, C57, C58 (all OPEN).

## Conventions

Evidence labels per the header block. Dated 2026-09-26. The corpus
fold lives in `docs/COMPETITOR_ANALYSIS.md` under "Watch update —
2026-09-26 (early morning)". C26 moves from "two conflicts OPEN" to
**RESOLVED-folded**; the C48 writeup-owed BACKLOG ask closes this
pass; the "Boat DELTA" branding is retired from future citations
(the vendor-verified pricing facts stand).
