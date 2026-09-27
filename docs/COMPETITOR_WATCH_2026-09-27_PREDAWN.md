# Competitor watch — 2026-09-27 (pre-dawn)

Two-surveyor pass, delta-only against the post-night pass (#526, slot 2354,
squash-merged as `c91a401`): (A) fast-mover + pricing re-verification vs
the ~23:55–23:57 CDT (2026-09-26) baseline (vendor reads ~00:55–01:00 CDT
2026-09-27),
(B) delta news scan ~00:35–01:15 CDT (~40-min delta window). Read-only, no
logins, no writes. Captures:
`agent_notes/surveyor-a-20260927-0054.md`,
`agent_notes/surveyor-b-20260927-0054.md` (under `hidden_files`).
Suffix `_PREDAWN` admitted per the first-of-day stack precedent
(`2026-09-25_PREDAWN`) — the 00:5x–01:1x CDT window is pre-dawn, and the
09-26 NIGHT → POST_NIGHT series stays on its calendar day.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

The all-first-try streak extends to **9** — all 9 vendor pages succeeded on
first attempt this pass; no web search used, every page read directly from
the vendor URL. Zero fetch failures.

1. **Daytona changelog** (`daytona.io/changelog`, read ~00:55 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25 V0.217.0, SEP 24 V0.216.1 + V0.216.2, SEP 23
   V0.216.0 all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`, read ~00:56 CDT) —
   newest dated heading still **2026-09-22**; next 2026-09-21 (v3 kits),
   then 2026-09-15.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`; body matches
   #1615/#1619/#1396/#1643).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September**; **no 26-Sep entries in any lane**. Drives not re-checked
   per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE / "$100 one-time usage credit", Pro $150/month,
per-second $0.000014/0.000028/0.000056/0.000084/0.000112 for 1/2/4/6/8
vCPU); boat.dev ($0.018/0.036/0.072/0.200 per hour, "A stopped sandbox costs
nothing", 25 free trial hours, $20/$100/$500/$2000 tiers — "Compared to
others" benchmark table and "Active CPU billing" editorial unchanged,
marketing content, no rate change); TermSquad ($9 (2 vCPU/4 GB/40 GB) /
$19 (4/8/75) / $29 (6/12/100) / $49 (8/24/200), "AI subscriptions and usage
are not included" + BYO-AI FAQ intact); DigitalOcean Managed Agents ("Last
verified 22 Sep 2026"; $0.044/vCPU-hour CPU, $0.0095/GB-hour peak memory,
session storage $0.05/GiB-month, egress $0.01/GiB, snapshots
$0.05/GiB-month, custom templates $0.05/GiB-month — the standing
snapshot-figure discrepancy vs the launch release ($0.05 vs $0.005) is
unresolved but unmoved); AgentComputer ($0.07 CPU-hour, $0.04375 GB-hour
memory, Hot Storage $0.000683/GB-hour (running), Cold Storage
$0.000027/GB-hour (stopped) — **still no egress policy stated, C12
stands**).

## Surveyor B — delta news scan: 0 new, 12 clean dedupes, 8 flagged-only

Quiet pre-dawn window (~00:35–01:15 CDT). No in-window, in-lane product
launches, pricing changes, funding events, or in-lane sandbox-escape CVEs.
The in-lane no-launch verdict of 2026-09-25 stands — streak extends. No
corpus fold recommended this pass.

Clean dedupes (12): **Docker Cloud Sandboxes Sep-24 launch** — additional
GlobeNewswire syndications (merge.news, theeveningleader.com,
lifestyle.independent.mk, lifestyle.folsomlocalnews.com,
lifestyle.thepointnews.com — no new development); **Factory $200M / $5B
raise** (Sep 15 — srnnews.com, aibusinessreview.org, wixx.com —
out-of-window); **Boxd $2M pre-seed for AI coding-agent infra** (Sep 16 —
todaysstartupnews.com, 6ic.com — out-of-window); **editorial recrawls**
(StartupHub "Daytona vs E2B vs Modal vs Vercel Sandbox (2026)" 142d old;
DEV "Sandboxing AI-Generated Code" 5h-old mirror).

Flagged-only (new to surveyor B but failing lane/window bars — NOT filed):

- **vm2 CVE-2026-47686 sandbox-escape RCE (CVSS 9.9)** (advisories public
  Aug 17 2026, fix 3.11.6 shipped Aug 14 — in-lane, fails window).
- **vm2 <3.11.8 AggregateError sandbox escape** (Sep 17 advisory —
  in-lane, 10 days old, fails window).
- **DeepSeek Harness CVE-2026-82533 (CVSS 9.4)** (disclosed Sep 8 2026,
  fixed Aug 27 — in-lane, fails window; distinct from aged-out
  Heapjack/Overpatch).
- **Docker Sandboxes CVE-2026-77179 & CVE-2026-79994** (virtio-fs macOS
  host escape — disclosed Sep 15, fixed Sep 7 in 0.42.0 — in-lane, fails
  window).
- **CVE-2026-80521 Ubuntu container escape** (public exploit Sep 22 —
  marginally in-lane, 5 days old, fails window).
- **ByteAsk $1M pre-seed** (Sep 24, YC/EF — secure grounding environment
  for C/C++ coding agents — marginally in-lane, 3 days old, fails window).
- **Meta Muse personal-agent launch** (Sep 8–9 — fails lane).
- **Salesforce/NVIDIA "Koa" CRM reasoning model** (Sep 15–16 — fails lane).

Stale-version rule: compliant this pass — verified vm2 CVE-2026-47686 fix
is 3.11.6 (advisories Aug 17, fix published Aug 14 per npm registry —
matches the 1dayexploit README, not a stale version); no search-result
version numbers for Daytona/Microsandbox/Docker release notes appeared
(second clean pass since the rule was briefed).

## Carried state

Aged out: Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706) — both
stay aged out (recrawls only). Dextr AI stays aged out (out-of-lane).
Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement),
C66 (OPEN, THIRD-PARTY); C26 CLOSED. In-lane no-launch verdict dated
2026-09-25 stands — streak extends.
