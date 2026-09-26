# Competitor watch — 2026-09-25 (post pre-midnight)

Targeted delta pass against the 2026-09-25 late pre-midnight pass
(`docs/COMPETITOR_WATCH_2026-09-25_LATE_PRE_MIDNIGHT.md`). Survey window
**2026-09-25 ~22:28–22:40 CDT** — read-only fetches and searches; no
logins, no writes. The `_POST_PRE_MIDNIGHT` suffix follows the slot
stacking convention (20:54 → `_PRE_MIDNIGHT`, 21:54 →
`_LATE_PRE_MIDNIGHT`, this is the ~22:24 slot).

Scope note: this pass deliberately did NOT re-survey the full tracked
set — the last full pass (post-late-evening, merged as PR #429) was
**9/9 VERIFIED NO-CHANGE** ~6 hours earlier, and the last two passes
re-verified the fastest-moving tracked vendors (Daytona, Docker
Sandboxes, Microsandbox) plus the two standing carried leads C37 +
C26 ~25–40 minutes ago. The value this slot is in **rotating the mover
coverage** to the slower-moving half of the tracked set not re-read
since the full pass: **E2B, Modal, Runloop, Cloudflare Sandbox, Boat
(tracked-set member), and DO Managed Agents** — plus a narrow delta
news scan. Vercel Drives not re-checked (P49 — next the 2026-09-26
morning pass).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**PR-PRIMARY** = the vendor's own claims carried on a paid
newswire/PR-syndication surface (vendor copy, third-party pipe).
**THIRD-PARTY** = press/third-party. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read
this run and the item is confirmed not present on it.

## 1. Tracked-set re-verification (targeted)

### E2B pricing — VENDOR-VERIFIED NO-CHANGE

`e2b.dev/pricing` read live this run (full page). Tiers verbatim
unchanged: **Hobby FREE** + $100 one-time usage credit, sessions up to
1 hour, 20 concurrent sandboxes, default CPU/RAM; **Pro $150/mo** +
usage, sessions up to 24 hours, 100 concurrent (expandable to 1,100),
custom CPU/RAM; Enterprise custom (committed usage, multi-day and
persistent sessions, BYOC). Rate card unchanged: $0.000014/s per vCPU
(2 vCPU default = $0.000028/s), per-second billing of running
sandboxes. No pricing delta since the post-late-evening full pass.
VERIFIED NO-CHANGE.

### Modal pricing — VENDOR-VERIFIED NO-CHANGE

`modal.com/pricing` read live this run (full page). Standard CPU
$0.0000131/core/sec (physical core = 2 vCPU) and Sandbox+Notebooks tier
$0.00003942/core/sec both verbatim — the ≈3× sandbox ratio holds
exactly ($0.00003942 ÷ $0.0000131 ≈ 3.009). Sandbox memory
$0.00000667/GiB/sec verbatim. GPU ladder verbatim: B300
$0.001972/s, B200 $0.001736/s, H200 SXM $0.001261/s, H100 SXM5
$0.001097/s, RTX PRO 6000 $0.000842/s, A100 80GB $0.000694/s, A100 40GB
$0.000583/s, L40S $0.000542/s, A10 $0.000306/s, L4 $0.000222/s, T4
$0.000164/s. Plans verbatim: Starter $0 + $30/mo free compute (100
containers + 10 GPU concurrency), Team $250 + $100/mo free compute
(5000 containers + 50 GPU), Enterprise custom. No pricing or
positioning delta. VERIFIED NO-CHANGE.

### Cloudflare Sandbox SDK pricing — VENDOR-VERIFIED NO-CHANGE

`developers.cloudflare.com/sandbox/platform/pricing/` read live this
run (full page; page stamps "Last updated Aug 28, 2026"). Sandbox SDK
pricing is still inherited from the underlying Containers platform;
Workers (incoming requests), Durable Objects (each sandbox instance),
and optional Workers Logs are billed alongside — all verbatim against
the corpus. Cross-checked against the Containers pricing page
(developers.cloudflare.com/containers/platform/pricing/, crawled
today): Workers Paid $5/mo includes 25 GiB-hours memory
(+$0.0000025/GiB-s), 375 vCPU-minutes (+$0.000020/vCPU-s =
$0.072/vCPU-hr — the corpus's active-CPU figure), 200 GB-hours disk
(+$0.00000007/GB-s); instance types lite → standard-4 verbatim. No
delta. VERIFIED NO-CHANGE.

### Runloop — THIRD-PARTY-corroborated, vendor-primary UNREAD this pass

No vendor pricing page was located this pass (Runloop's rates are not
on the public landing page — consistent with the corpus note). The
Upstash comparison blog (upstash.com, 9 days old) corroborates the
corpus rate card: **$0.108/CPU-h, $0.0252/GB-h, free Basic; $250/mo
Pro** — verbatim-consistent. New third-party detail: **$50 trial
credit**; suspended = storage-only (Pro-only). Adjacent product
surface (THIRD-PARTY, PRNewswire syndication): **Runloop Public
Benchmarks launched** — on-demand standardized agent testing (SWE-Bench
Verified 500 + specialized libraries), **$25 base tier + pay-as-you-go
usage** scaling. Benchmarking is a new lane for Runloop, not a devbox
pricing change. Rate card: NO-CHANGE (third-party corroboration only).

### Boat (tracked-set member) — DELTA (vendor-primary)

`docs.boat.dev/pricing` (crawled 1 day ago — vendor docs surface) shows
a materially expanded product surface vs the corpus baseline:

- **New machine sizes:** `small` $0.018/hr (2 vCPU / 4 GB / 12 GB disk)
  and `large` $0.072/hr (8 vCPU / 16 GB / 125 GB disk) join `default`
  $0.036/hr (4 vCPU / 8 GB / 50 GB) and `xlarge` $0.200/hr
  (16 vCPU / 32 GB / 251 GB — still needs a $100+ plan + operator
  allocation). The corpus knew only default + xlarge.
- **New plan structure:** $20/$100/$500/$2,000-mo plans set
  concurrency (100 / 300 / 1,000 / 2,000 sandboxes at once) and start
  limits (12/60/200, 30/210/840, 65/420/1,680, 90/600/2,400 starts per
  min/hour/day). Plan price is not a fee: every dollar is sandbox time
  at the machine rates ($20 = 555 hours of `default`); time granted
  monthly and expires; **$20 credit packs** (never expire) +
  auto-refill for overage.
- Trial still 25 free hours (small + default only, 2 sandboxes at once,
  until first payment).
- New docs surface (`docs.boat.dev`): machine-capabilities page,
  snapshots page (incremental snapshots **every minute** while ready or
  idle + a final one on stop; failed snapshot refuses the stop and the
  meter pauses — billing pauses by itself), and a sandbox-usage API
  endpoint (`/api/v1/sandboxes/{id}/usage`) with a per-size
  `billingMultiplier` (0.5 small / 1 default / 2 large).
- The `boat.dev/compare` page (crawled 2 days ago) now carries a
  vendor-computed price table ("public list prices verified
  2026-09-18"): boat $0.036/h vs Novita $0.233/h, **Freestyle
  $0.264/h**, exe.dev $0.280/h, E2B/Daytona/Blaxel $0.331/h,
  Codespaces/Cloudflare $0.360/h, Modal $0.476/h, **Islo $0.600/h**,
  Runloop $0.634/h, Vercel Sandbox $0.682/h — all at 4 vCPU / 8 GB
  wall-clock hour (active-CPU-only providers computed at full use).
  Novita, exe.dev, and Islo are new-to-corpus names on a vendor's own
  comparison page (adjacent leads, not filed as C-numbers this pass).

**Corpus impact:** the Boat field-table row needs a refresh (sizes,
plans, docs surface); competitor-name sightings noted as adjacent.
**DELTA** — filed in the fold.

### DigitalOcean Managed Agents — DELTA (public preview launch)

The consolidation-row baseline ("announced 2026-09-22") has advanced
to **public preview open to all users**:

- `investors.digitalocean.com` news release (Business Wire, 4 days ago,
  PR-PRIMARY): "Managed Agents is now available to everyone" after a
  private preview; early builders named: **OpenHands, Qencode,
  Amplitude**.
- DO product docs (docs.digitalocean.com/products/managed-agents/,
  "Latest Updates — 21 September 2026", VENDOR-VERIFIED): Harness
  Runtime + Action Gateway as two independently scaling services;
  **Bring-Your-Own-Template** (custom OCI images as sandbox templates);
  16,000+ tools; BYOT custom templates billed at $0.05/GiB-month.
- Vendor latency measurements (subagentic.ai, THIRD-PARTY, citing DO's
  own Sept 21 benchmark): **~886 ms session-ready, ~305 ms
  resume-from-pause** — treat as vendor measurements (C14 input
  discipline).
- Pricing (PR-PRIMARY, Business Wire copy via Market Newsdesk
  syndication): active-CPU billing — **$0.044/vCPU-hr, $0.0095/GB-hr
  memory, snapshots $0.005/GiB-month**; "up to 37% lower monthly TCO"
  vs the leading independent sandbox provider (vendor claim; INFERRED:
  E2B).
- Inference Engine surface (vendor release copy): 75+ models incl.
  Nemotron 3 Ultra, Kimi K3, GLM 5.3, Claude Fable 5.1, GPT 6 Astra.

**C26 evidence update:** the launch release is now a SECOND
vendor-owned surface printing **$0.005/GiB-month** for snapshots (IR
launch page was the first; the docs pricing subpage still prints
$0.05, stamp "Last verified 22 Sep 2026"). The vendor's own weight of
evidence is 2:1 for $0.005; the docs subpage remains the unreconciled
oddity (misattribution hypothesis: DO's general-product Volumes
snapshot rate bleeding into the Managed Agents page). C26 stays OPEN
with the lean noted.

## 2. Delta news scan

Two searches + the vendor reads above. Candidates dedupe as follows:

- **DO Managed Agents public-preview launch** → filed as DELTA above
  (was the 2026-09-22 consolidation row; now live for all users).
- **Runloop Public Benchmarks** ($25 base + PAYG) → adjacent new
  product surface, THIRD-PARTY, noted under Runloop above.
- **C57 — Baponi** (baponi.ai, NEW TO CORPUS): "Sandboxes for AI
  agents billed only when code runs" — nsjail + Linux namespace
  isolation, seccomp-bpf syscall allowlist, zero Linux capabilities;
  sessions persist days/weeks at zero idle cost; per-execution billing
  (not per-second); Free $0 (1,000 credits/mo), Pro $97/mo (10,000
  credits, then $1.00 per additional 1K), Enterprise custom BYOC.
  THIRD-PARTY (tizkovatereza/awesome-ai-sandboxes, 19 days old).
  **OPEN — new C-number.**
- **C58 — Leap0** (NEW TO CORPUS): Firecracker microVM per sandbox,
  vendor claims ~100 ms boots; Jailer hardening (chroot, cgroup v2,
  seccomp, unique UID/GID — vendor statement); firewall modes
  allow-all/deny-all/custom with host-side per-domain credential
  injection (TLS MITM); full XFCE desktop; SDKs open-source
  (Apache-2.0, github.com/leap0-dev); public preview, US-only, no
  published pricing. THIRD-PARTY (msyvr/awesome-agent-sandboxes, 22
  days old). **OPEN — new C-number.**
- Vercel Drives not re-checked (P49 — 2026-09-26 morning pass).
- All other in-lane hits dedupe to filed corpus (E2B/Modal/Cloudflare
  third-party corroborations of the vendor-primary reads; Daytona GPU
  rate chatter → known corpus figures).

**No new launch-verdict change:** in-lane no-launch verdict dated
2026-09-25 stands (DO Managed Agents was already launched; the news is
the public-preview opening, not a launch).

## 3. Verdict

Tracked set this pass: **3/3 VENDOR-VERIFIED NO-CHANGE** (E2B, Modal,
Cloudflare Sandbox SDK) + Runloop third-party-corroborated NO-CHANGE
(vendor-primary unread) + **two DELTAs** (Boat product-surface
expansion; DO Managed Agents public preview + pricing corroboration)
+ **two new adjacent C-numbers** (C57 Baponi, C58 Leap0). Carried
leads C37/C26 not re-surveyed (verified ~25 min ago; C26 evidence
updated from the launch PR, not a page re-read). Zero fetch failures
(4 vendor-primary page reads first-try).

**Carried:** C37, C26 (both OPEN); C57, C58 (new, OPEN).

## Conventions

Evidence labels per the header block. Dated 2026-09-25. The corpus
fold lives in `docs/COMPETITOR_ANALYSIS.md` under "Watch update —
2026-09-25 (post pre-midnight)".
