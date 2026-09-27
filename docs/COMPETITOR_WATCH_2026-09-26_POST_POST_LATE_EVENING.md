# Competitor watch — 2026-09-26 (post-post-late-evening)

Two-surveyor pass, delta-only against the post-late-evening pass (#507,
slot 1754, merged as `146d6e95`): (A) fast-mover + pricing
re-verification vs the ~17:55–17:56 CDT baseline (~18:55–19:02 CDT), (B)
delta news scan ~18:02–19:05 CDT. Read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-1854.md`,
`agent_notes/surveyor-b-20260926-1854.md` (under `hidden_files/`).
Suffix `_POST_POST_LATE_EVENING` admitted per the POST_ same-day-repeat
precedent (`_POST_LATE_EVENING`, `_POST_LATE_MORNING`, etc.) — 19:0x CDT
is still evening (sunset ~19:15), so `_NIGHT` would be dishonest.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

All nine vendor fetches succeeded — zero UNVERIFIED grades. The
all-first-try streak **resets to 0** this pass: two fetches needed a
second attempt (`boat.dev/pricing` 404s — the canonical URL is
`docs.boat.dev/pricing`, verified live this pass; the DigitalOcean
Managed Agents `/details/` page 404s — recovered immediately on the known
canonical docs page), so this is not the tenth consecutive all-first-try
pass. The next clean pass starts a new streak at 1.

1. **Daytona changelog** (`daytona.io/changelog`, read ~19:00 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"). Next: SEP 25 V0.217.0 (NVIDIA B300 GPU), SEP 24
   V0.216.1 / V0.216.2 — all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`) — newest dated heading
   still **2026-09-22** ("Improved sandbox moves and support for private
   kit images in cloud sandboxes."); next 2026-09-21 (v3 kits).
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September** (Sandbox memory observability); no 26-Sep entry in any
   lane. Drives not re-checked per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE / $100 one-time usage credit, Pro $150/month,
per-second table top $0.000014/s); boat.dev (small $0.018 / default
$0.036 / large $0.072 / xlarge $0.200 per hour, 25 free trial hours,
"a stopped sandbox costs nothing" — read at `docs.boat.dev/pricing`
after `boat.dev/pricing` 404'd); TermSquad ($9/$19/$29/$49 tiers, BYO-AI
FAQ intact — "AI subscriptions and usage are not included"); DigitalOcean
Managed Agents ("Last verified 22 Sep 2026"; $0.044/vCPU-hour actual-CPU,
$0.0095/GB-hour peak, snapshots $0.05/GiB-month, egress $0.01/GiB — the
standing snapshot-figure discrepancy vs the launch release ($0.05 vs
$0.005) is unresolved but unmoved); AgentComputer ($0.07 CPU-h,
$0.04375 GB-h, hot $0.000683 / stopped $0.000027 storage, still no egress
policy stated — C12 stands).

## Surveyor B — delta news scan: 0 new, 11 clean dedupes, 9 flagged-only

Quiet window. No in-window, in-lane launches, pricing changes, funding
events, or in-lane CVEs. ~10 targeted searches ~18:55–19:05 CDT.

Clean dedupes: Daytona changelog search shows nothing newer than
V0.218.0 (SEP 26); Microsandbox search shows nothing newer than v0.7.3;
Vercel changelog newest entries 25 Sep (VCR GitHub Action, Pixel Canary
on AI Gateway, Sandbox memory observability = tracked Vercel-lane baseline,
not new) — no 26-Sep-lane entries;
Fly.io GPU docs still carry the "deprecated after August 1" banner
(pre-window); Docker Cloud Sandboxes press recrawls (filed row);
Cloudflare sandbox-escape disclosure = **C55** (recrawls only); vm2
CVE-2026-92937/92956/47686/93603/93605 recrawls (already flagged-only);
OpenClaw CVE-2026-100579 (kept separate from C66); GitLab package-proxy
agent-sandbox escape (already in corpus, pre-window, no new facts);
Heapjack/Overpatch recrawls (queued deep-scan items — queue unchanged);
TermSquad launch-week press syndication (filed row, no new facts).

Flagged-only (new to corpus but failing lane/window bars):

- Carried from the #507 pass: **CVE-2026-92940** (vm2 3.10.1–3.11.6,
  fixed 3.11.7 — CVSS 10.0; adjacent JS-sandbox lane + out of window);
  **CVE-2026-100558** (OpenClaw — adjacent harness lane + ~20h
  pre-window); **CVE-2026-100570** (OpenClaw — adjacent harness lane +
  pre-window); two 9/25 OpenClaw VulnCheck advisories (adjacent +
  out of window).
- **CVE-2026-100551** (OpenClaw iOS Gateway TLS-pin bypass, CVSS 8.3;
  published 2026-09-26T02:18Z = Sep 25 21:18 CDT) — NOT filed: adjacent
  harness lane + pre-window.
- **CVE-2026-100555** (Synology Chat SSRF, CVSS 7.1; same publication
  stamp) — NOT filed: adjacent lane + pre-window.
- **CVE-2026-100530** (exec approval directory-context reuse, CVSS 7.3;
  same publication stamp) — NOT filed: adjacent harness lane +
  pre-window.
- **CVE-2026-100541** (Matrix identity case-folding, CVSS 7.5; same
  publication stamp) — NOT filed: adjacent lane + pre-window.
- **GitSpawn git-config RCE advisory cluster** (disclosed Sep 1) — NOT
  filed: adjacent lane + pre-window.

Corpus keeper note: the Sep-25/26 OpenClaw CVE batch now spans seven
CVE IDs (100530, 100541, 100551, 100555, 100558, 100570, 100579); the
two 9/25 VulnCheck advisories belong to the same batch. If the harness
lane is ever consolidated, treat it as one batch item, not seven
C-numbers.

## Carried

- **C37** (Freestyle Pro fee VERIFIED absent — stands); **C55**
  (Cloudflare escape — no new facts); **C57**; **C58** (Leap0 pricing
  vendor-verified — stands); **C62** (no movement); **C66** (OPEN,
  THIRD-PARTY); **C26** CLOSED (DO Managed Agents — no new dollar
  pricing this pass).
- In-lane no-launch verdict dated 2026-09-25 stands — streak extends.
- Deep-scan queue unchanged: Heapjack/Overpatch + GitLab proxy escape.
- P3 marketing gate: contributor-facing assets only; nothing in this
  pass is launch-directed.

No corpus fold (no new C-numbers; no sanctioned-exception item this
pass). Next pass: routine tracked-set re-reads; the all-first-try streak
restarts at 1; boat.dev's canonical URL is now recorded as
`docs.boat.dev/pricing`; watch Vercel changelog for 26-Sep-lane entries;
Vercel Drives GA on the daily morning pass per P49.
