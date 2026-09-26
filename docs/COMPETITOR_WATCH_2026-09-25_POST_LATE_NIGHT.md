# Competitor watch — 2026-09-25 (post-late-night)

Delta-only pass against the 2026-09-25 late-night pass
(`docs/COMPETITOR_WATCH_2026-09-25_LATE_NIGHT.md`). Survey window
**2026-09-25 ~19:30–19:45 CDT** — read-only fetches and searches; no
logins, no writes.

Scope note: this pass deliberately did NOT re-survey the full tracked
set — the last full pass (post-late-evening, merged as PR #429) was
**9/9 VERIFIED NO-CHANGE** ~2.5 hours earlier. The value this slot is
in (a) re-verifying the two fastest-moving tracked vendors (Daytona
changelog cadence is currently daily; Docker Sandboxes moved two days
ago) and (b) a narrow delta news scan plus the C54 primary-article
read retry.

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **snippet-level** = seen only
via search snippet. **UNVERIFIED** = a public page exists but could
not be fetched this run (never reported as NO-CHANGE). **VERIFIED
absent** = the vendor's own page was read this run and the item is
confirmed not present on it.

## 1. Tracked-set re-verification (targeted)

### Daytona changelog — DELTA (VENDOR-VERIFIED)

`daytona.io/changelog` read live this run (full page, ~155 lines).
Two new entries since the late-evening baseline (which showed the SEP
24 V0.216.1/V0.216.2 pair as newest):

- **SEP 26 2026 — V0.218.0:** "Added a `kvm` parameter to sandbox
  creation in every SDK, and moved CLI login to a dedicated WorkOS
  application." (Source labels it Sep 26; this run is 19:24 CDT
  2026-09-25 = 00:24 UTC 2026-09-26, so the stamp is consistent with
  the run.)
- **SEP 25 2026 — V0.217.0:** "Added the NVIDIA B300 GPU type to the
  API client."

The V0.218.0 `kvm` creation parameter is the more substantive move:
sandbox creation now takes an isolation-backend toggle — a selectable
substrate choice at provision time. It does not change Daytona's
positioning or pricing (no field-table change — per the C32/C45
convention, changelog moves are watch color), but it is tracked as
design-axis color: on the H4 adapter axis, the per-harness contract
gains a "which substrate back-end" dimension — exactly the kind of
provider heterogeneity the ORCA-style adapter contract was designed to
absorb. V0.217.0's B300 GPU type adds GPU-axis color (B300 also
appears in Modal's corpus GPU ladder, C-tracked), with no pricing
attached yet.

### Docker Sandboxes release notes — VERIFIED NO-CHANGE

`docs.docker.com/ai/sandboxes/release-notes/` read live this run
(full page). Newest dated heading remains **2026-09-22** (v0.45.1
sbx-releases — "Improved sandbox moves and support for private kit
images in cloud sandboxes", plus the Sep-22 v3-kits and core entries,
including the egress-policy hardening: reverse-DNS lookups restricted
to policy-authorized destination IPs, trailing-dot hostname
normalization, non-interactive-shell support gated behind opt-out).
No newer entry. VERIFIED NO-CHANGE.

## 2. Carried leads

### C54 — Perplexity "Escaping SPACE" primary-article read (CARRY)

All four read paths attempted again this run; all still blocked or
empty:

1. Direct URL (`perplexity.ai/hub/blog/escaping-space-part-i`) —
   **HTTP 403** again (~19:35 CDT).
2. Wayback closest capture (timestamp 20260924213405, status 204
   "available") — fetch returned an empty response / HTTP 500 path.
3. Wayback CDX metadata fetch — **HTTP 500**.
4. `r.jina.ai` — blocked by runtime policy (no web-scraping-proxy
   exfil path).

A live-browser read of the exact article was attempted this run; its
result had not landed at write time. Verdict stands either way: the
primary-article body read is CARRIED. Any success folds next pass —
this doc does not claim it.

Third-party layer: `dennysentinel.com/blog/2026-09-24-the-kernel-held-the-allowlist-didnt/`
("The Kernel Held, the Allowlist Didn't", published Sep 23, 2026)
read in full this run (~19:37 CDT). It corroborates the detail
already folded 2026-09-25 (216 runs / 9 models, zero VM escapes in
108 attempts, 11/54 partial-network policy bypasses, DNS-spoof +
authority-switch bypass mechanisms, vendor-response table, nftables +
per-request authority-validation remediation, "Closing the hole meant
removing capability"). No new facts vs the folded third-party layer —
no corpus change, no grade change.

### C37, C26(a), C26(b) — carried unchanged

Carried per the late-night pass; not re-verified this pass (last
VERIFIED reads were this same calendar day). Vercel Drives not
re-checked (P49 — next the 2026-09-26 morning pass).

## 3. Narrow delta news scan — in-lane no-launch verdict

Window: in-lane items dated 2026-09-25 (CDT) surfaced this run:

- **Blitzy "sandbox for reverse engineering"** (Sep 25, THIRD-PARTY,
  free tier) — an AI agent tool for reverse-engineering codebases
  (DevOps audience), not agent compute / sandbox infra. Out of lane.
  Not filed.
- **Microsoft Copilot revamp** (Sep 25: Copilot Home, Copilot Code,
  Autopilot) — agent product UX, not sandbox/provider infra. Out of
  lane (C50's Managed Runtime filing remains the in-lane Microsoft
  position). Not filed.
- **Zoho Catalyst agentic PaaS** — PaaS-tier adjacent color; already
  on the adjacent watchlist. No sandbox-infra change. No corpus
  change.
- **Meta Muse explainx piece** ("What Is the Secure VM Behind Muse"),
  2026-09-25 — third-party recap of the primary Meta/Anthropic
  material behind P54-adjacent coverage; no new primary facts. Below
  the C-number bar.
- **Selangor / Google Cloud "Teraju AI sandbox"** — stale recrawl
  ("Last Updated: 550 days ago"), government AI-sandbox program,
  out-of-lane and out-of-window. Dropped.

Nothing in the window is an in-lane provider launch, pricing move, or
primary-source security disclosure. **In-lane no-launch verdict dated
2026-09-25. No new C-numbers.**
