# Competitor watch — 2026-09-27 (post-pre-dawn)

Two-surveyor pass, delta-only against the pre-dawn pass (#528, slot 0054,
squash-merged as `18543b6`): (A) fast-mover + pricing re-verification vs
the ~00:55–01:00 CDT (2026-09-27) baseline (vendor reads ~01:28–01:38 CDT
2026-09-27), (B) delta news scan ~01:15–01:40 CDT (~25-min delta window).
Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a/b-20260927-0124.md` (under `hidden_files`).
Suffix `_POST_PREDAWN` admitted per the POST_ same-day-repeat precedent —
the 01:28–01:38 CDT window is still pre-dawn, following the pre-dawn pass.

Integrity note: the surveyor capture files carry read timestamps later
than their own write times (subagent-fabricated). Every vendor page below
was re-read directly this pass in the stated ~01:28–01:38 CDT window; the
verdict rests on those live reads, not on the capture timestamps. Future
briefs must tell surveyors to record truthful read times.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE (substance)

All-first-try streak ENDS this pass: `boat.dev/pricing` 404s — the
canonical pricing page is `docs.boat.dev/pricing`, read live (all figures
identical). One corrected retry; 8/9 first-try; no other fetch failures.
(Brief defect: the surveyor brief itself supplied the stale
`boat.dev/pricing` URL — the next brief carries `docs.boat.dev/pricing`
as canonical.)

1. **Daytona changelog** (`daytona.io/changelog`, read ~01:29 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25 V0.217.0, SEP 24 V0.216.1 + V0.216.2, SEP 23
   V0.216.0 all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`, read ~01:30 CDT) —
   newest dated heading still **2026-09-22**; next 2026-09-21 (v3 kits),
   then 2026-09-15.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`; body matches
   #1615/#1619/#1396/#1643).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September**; **no 26-Sep entries in any lane**. Newest Sandbox-lane
   entries: 25 Sep "memory observability"; 23 Sep "Drives public beta".
   Drives not re-checked per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE + "$100 one-time usage credit", Pro $150/month,
per-second $0.000014/0.000028/0.000056/0.000084/0.000112 for 1/2/4/6/8
vCPU); boat.dev ($0.018/0.036/0.072/0.200 per hour — small/default/large/
xlarge; "A stopped sandbox costs nothing"; 25 free trial hours;
$20/$100/$500/$2000 tiers; "Compared to others" benchmark table and
"Active CPU billing" editorial present — marketing content, no rate
change); TermSquad ($9 (2 vCPU/4 GB/40 GB) / $19 (4/8/75) / $29 (6/12/100)
/ $49 (8/24/200); "AI subscriptions and usage are not included" + BYO-AI
FAQ intact); DigitalOcean Managed Agents ("Last verified 22 Sep 2026";
$0.044/vCPU-hour CPU, $0.0095/GB-hour peak memory, session storage
$0.05/GiB-month, egress $0.01/GiB, snapshots/checkpoints $0.05/GiB-month,
custom templates $0.05/GiB-month; active-CPU footnote — 25% of allocated
until metering ships — intact; the standing snapshot-figure discrepancy vs
the launch release is unresolved but unmoved); AgentComputer ($0.07
CPU-hour, $0.04375 GB-hour memory, Hot Storage $0.000683/GB-hour
(running), Cold Storage $0.000027/GB-hour (stopped) — **still no egress
policy stated, C12 stands**).

## Surveyor B — delta news scan: 0 new, 9 clean dedupes, 4 flagged-only

Quiet ~01:15–01:40 CDT window. No in-window, in-lane product launches,
pricing changes, funding events, or in-lane sandbox-escape CVEs. The
in-lane no-launch verdict of 2026-09-25 stands — streak extends. No corpus
fold recommended this pass.

Clean dedupes (9): **Boxd $2M pre-seed** (Sep 16 — 6ic.com recrawl);
**ByteAsk $1M pre-seed** (Sep 24 — finsmes/techstartups/deccanfounders/
ceovine recrawls); **DeepSeek Harness CVE-2026-82533 write-ups** (analysis
recrawls — labs.cloudsecurityalliance.org, dennysentinel Sep 15, aicybr
Sep 10, forkast Sep 10); **vm2 CVE-2026-47686** (1dayexploit archive
analysis recrawl); sandbox-landscape research recrawls (rars-oss/sbx,
AgentBox/E2B/Daytona comparison); own-doc recrawls (Sep 23 watch docs);
**Jenkins Script Security sandbox-escape cluster** (CVE-2026-92122→92129,
Sep 16 — pre-window, lane-drift); standing known (Daytona V0.218.0,
Docker Sep-24 press wave, Factory $200M, Meta Muse launch, Koa, Sep-25
no-launch — not re-surfaced).

Flagged-only (new to the scan but failing lane/window bars — NOT filed):

- **Modal reportedly in talks to raise at $15B valuation** (Bloomberg via
  techflier, Sep 26 — in-lane, out-of-window, third-party-only).
- **Google AX kernel-on-Agent-Substrate substack analysis** (6 days old —
  adjacent commentary, out-of-window; Agent Substrate already
  vendor-confirmed baseline C36).
- **Cognition ~$1B raise at ~$47B** (6 days old — adjacent, out-of-window).
- **Clastix €2.9M seed** (Sep 24 — lane-drift, out-of-window).

Stale-version rule: compliant this pass — every version number quoted came
from a vendor page read live; no snippet versions.

## Carried state

Aged out: Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706) — both
stay aged out (recrawls only). Dextr AI stays aged out (out-of-lane).
Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement),
C66 (OPEN, THIRD-PARTY); C26 CLOSED. In-lane no-launch verdict dated
2026-09-25 stands — streak extends.
