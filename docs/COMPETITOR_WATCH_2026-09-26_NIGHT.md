# Competitor watch — 2026-09-26 (night)

Two-surveyor pass, delta-only against the post-post-post-post-post-post-post-post-late-evening
pass (#521, slot 2224, squash-merged as `cfabecf19`): (A) fast-mover + pricing
re-verification vs the ~22:25–22:35 CDT baseline (vendor reads ~23:26 CDT),
(B) delta news scan ~22:25–23:55 CDT (~90-min delta window). Read-only, no
logins, no writes. Captures: `agent_notes/surveyor-a-20260926-2324.md`,
`agent_notes/surveyor-b-20260926-2324.md` (under `hidden_files`).
Suffix `_NIGHT` admitted per the 2026-09-23 `_NIGHT` precedent — the
~23:26–23:42 CDT window is past 23:00, so `_LATE_EVENING` would be dishonest;
this deliberately breaks the POST_×8 LATE_EVENING sortable chain and starts the
2026-09-26 NIGHT series.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

The all-first-try streak extends to **7** — all 9 vendor pages succeeded on
first attempt this pass. Zero fetch failures, zero search fallbacks; every
page read directly from the vendor URL.

1. **Daytona changelog** (`daytona.io/changelog`, read ~23:26 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25 V0.217.0, SEP 24 V0.216.1 + V0.216.2, SEP 23
   V0.216.0 all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`, read ~23:26 CDT) —
   newest dated heading still **2026-09-22** ("Improved sandbox moves and
   support for private kit images in cloud sandboxes."); next 2026-09-21,
   then 2026-09-15.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`; body matches —
   managed admin overrides, sandbox wait command, snapshot command
   simplification, strict hostname policy default).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September** (Push images to Vercel Container Registry + Pixel Canary
   on AI Gateway + Vercel Sandbox memory observability); only 25/24/23/22
   Sep headers — **no 26-Sep entries in any lane**. Drives not re-checked per
   P49 (daily cadence).

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
memory, Hot Storage $0.000683/GB-hour (running), Cold Storage
$0.000027/GB-hour (stopped) — **still no egress policy stated, C12 stands**).

## Surveyor B — delta news scan: 0 new, 9 clean dedupes, 2 flagged-only

Quiet window (~22:25–23:55 CDT, 4 targeted search passes + 2 aging-candidate
passes). No in-window, in-lane product launches, pricing changes, funding
events, or in-lane sandbox-escape CVEs. The in-lane no-launch verdict of
2026-09-25 stands — streak extends. No corpus fold recommended this pass.

Clean dedupes (9): **OpenAI offline-training-sandbox escape recrawls = C62**;
**HF nine-zero-days re-report (C62/C64 family)**; **DeepSeek DSec/
CVE-2026-82533 recrawls = C56**; **Docker CVE-2026-77179/79994 recrawl =
C45 family**; **Vercel Sandbox Drives Sep-23 public beta** (already in
baseline, not a new event); **Daytona $24M raise recrawl** (stale);
**E2B $21M raise recrawl** (stale); **TermSquad quiet** (no new moves);
**Modal quiet** (no new moves).

Flagged-only (new to surveyor B but failing lane/window bars — NOT filed):

- **Docker Cloud Sandboxes launch** (GlobeNewswire, Sep 24 2026 12:00 PM EDT,
  launched at WeAreDevelopers North America): in-lane but out-of-window; and
  — correcting the surveyor's "not seen in prior B passes" note — the launch
  is already the filed Docker row in the corpus, so this is a recrawl, NOT a
  backfill candidate.
- **ComputeSDK 1.0.0** (E2B/Vercel/Daytona wrapper SDK): fails the lane bar
  — third-party SDK, not a sandbox product.

Corpus-hygiene note (recurrence): surveyor B's capture again carried stale
search-result versions (Daytona V0.216.0 Sep 23, Microsandbox v0.7.1, Docker
release notes top out 2026-09-21) — **superseded by surveyor A's
vendor-verified baselines this pass** (Daytona V0.218.0 Sep 26, Microsandbox
v0.7.3, Docker 2026-09-22); search-result fuzz is not folded. Second
consecutive pass needing this correction — the B-brief should state the
stale-version rule explicitly going forward.

Aging verdicts: **Heapjack/Overpatch** — no in-window development (all
Sep-15-disclosure recrawls); **ages out next pass if still quiet**. **GitLab
proxy escape (CVE-2026-85706)** — no in-window development (latest recrawl
~Sep 24; in-the-wild probes date to Sep 11); **ages out next pass if still
quiet**. Dextr AI: no new movement (stays aged out).

## Carried state

Aged-out-next-pass if quiet: Heapjack/Overpatch, GitLab proxy escape
(CVE-2026-85706). Carried: C37, C55, C57, C58 (pricing vendor-verified), C62
(no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. In-lane no-launch verdict
dated 2026-09-25 stands — streak extends.
