# Competitor watch — 2026-09-26 (post-post-post-post-post-post-post-post-late-evening)

Two-surveyor pass, delta-only against the post-post-post-post-post-post-post-late-evening
pass (#519, slot 2124, squash-merged as `f086840d`): (A) fast-mover + pricing
re-verification vs the ~21:27–21:45 CDT baseline (~22:25–22:35 CDT),
(B) delta news scan ~21:45–22:25 CDT (~40-min delta window). Read-only, no
logins, no writes. Captures: `agent_notes/surveyor-a-20260926-2224.md`,
`agent_notes/surveyor-b-20260926-2224.md` (under `hidden_files`).
Suffix `_POST_POST_POST_POST_POST_POST_POST_POST_LATE_EVENING` admitted per the POST_
same-day-repeat precedent — the ~22:25–22:35 CDT window is past sunset (~19:15),
so `_NIGHT` would arguably be truer; kept in the LATE_EVENING chain deliberately
so the day's watch series stays one sortable series.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

The all-first-try streak extends to **6** — all 9 vendor pages plus both
deep-scan searches succeeded on first attempt this pass.

1. **Daytona changelog** (`daytona.io/changelog`, read ~22:26 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25 V0.217.0, SEP 24 V0.216.1 + V0.216.2, SEP 23
   V0.216.0 all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`, read ~22:27 CDT) —
   newest dated heading still **2026-09-22** ("Improved sandbox moves and
   support for private kit images in cloud sandboxes."); next 2026-09-21
   (v3 kits), then 2026-09-15.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`; body matches —
   managed admin overrides, sandbox wait command, snapshot command
   simplification, strict hostname policy default).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September** (25 Sep entries now include Push images to Vercel
   Container Registry + Pixel Canary on AI Gateway + Vercel Sandbox memory
   observability); only 25/24/23/22 Sep headers present — **no 26-Sep entry
   in any lane**. Drives not re-checked per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE / $100 one-time usage credit, Pro $150/month,
per-second table top $0.000014/s — 1 vCPU; $0.000028/s 2 vCPU; $0.000056/s
4; $0.000084/s 6; $0.000112/s 8); boat.dev (small $0.018 / default $0.036 /
large $0.072 / xlarge $0.200 per hour, 25 free trial hours, "A stopped
sandbox costs nothing", $20/$100/$500/$2000 plan tiers — the "Compared to
others" benchmark table and "Active CPU billing" editorial sections still
present; marketing content, **no rate change**); TermSquad ($9 (2 vCPU/4
GB/40 GB) / $19 / $29 / $49 tiers, BYO-AI FAQ intact); DigitalOcean Managed
Agents ("Last verified 22 Sep 2026"; $0.044/vCPU-hour CPU, $0.0095/GB-hour
peak memory, session storage $0.05/GiB-month, egress $0.01/GiB, snapshots
$0.05/GiB-month, custom templates $0.05/GiB-month — the standing
snapshot-figure discrepancy vs the launch release ($0.05 vs $0.005) is
unresolved but unmoved); AgentComputer ($0.07 CPU-hour, $0.04375 GB-hour
memory, Hot Storage $0.000683/GB-hour, Cold Storage $0.000027/GB-hour —
**still no egress policy stated, C12 stands**).

## Surveyor B — delta news scan: 0 new, 7 clean dedupes, 2 flagged-only

Quiet window (~21:45–22:25 CDT, 4 targeted search passes). No in-window,
in-lane product launches, pricing changes, funding events, or in-lane
sandbox-escape CVEs. The in-lane no-launch verdict of 2026-09-25 stands —
streak extends. No corpus fold recommended this pass.

Clean dedupes (7): **OpenAI offline-training-sandbox escape = C62**
(Bloomberg/HinduBusinessLine re-report of the Sep-20 DNS escape and Sep-25
disclosure, updated 2026-09-27 06:14 AM IST ≈ 19:44 CDT Sep 26 — recrawl of
the known incident, no new primary source); **HF nine-zero-days recrawl**
(startupfortune.com re-report of the July incident — #517's strongest flag,
still third-party garnish); **DeepSeek DSec reward-hacking recrawl**
(techtimes Sep-25 piece, CVE-2026-82533 DeepSeek Harness sandbox escape —
pre-window, already-known CVE); **Vercel Sandbox Drives public beta**
(nandann.com analysis confirming the 23 Sep 2026 announcement —
already in baseline, not a new event); **Accomplish sandbox-escape
disclosures** (Sep 12, pre-window); **Guava "Daytona" voice model** (name
collision only — voice AI, out-of-lane); **DevDay "O" always-on-agent rumor**
(still speculation, no primary source).

Flagged-only (new to corpus but failing lane/window bars — NOT filed):

- **dev.to "Copilot joins AI SDK, agents ship on Vercel"** (~Sep 24):
  Vercel wiring OpenAI's Agents API into Sandbox + Queues infrastructure —
  ecosystem/usage color for a tracked vendor, but no sandbox product launch.
- **E2B/DEV comparison + Upstash comparison recrawls** (dev.to pricing
  lifecycle, Upstash comparison blog) — stale/secondary, pre-window.

Corpus-hygiene note: surveyor B's "notes for next pass" carried stale
search-result versions (Daytona V0.216.0, Microsandbox v0.7.1, Docker release
notes 2026-09-21) — **superseded by surveyor A's vendor-verified baselines
this pass** (Daytona V0.218.0 Sep 26, Microsandbox v0.7.3, Docker 2026-09-22);
search-result fuzz is not folded.

Aged-out items did not resurface — no re-flagging. Dextr AI: no new movement
(stays aged out). Aging candidates if still quiet next pass: **Heapjack/
Overpatch** (freshest coverage is 15-Sep-disclosure recaps — DevOps.com,
dev.to, techgig; no new exploits/patches/CVEs; minimums unchanged) and the
**GitLab proxy escape** (CVE-2026-85706 / Eclipse postmortem — all recrawls,
nothing new on the incomplete-proxy-block vector).

## Carried state

Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (both quiet this
pass — aging candidates next pass if still quiet). Carried: C37, C55, C57,
C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY);
C26 CLOSED. In-lane no-launch verdict dated 2026-09-25 stands — streak
extends.
