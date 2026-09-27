# Competitor watch — 2026-09-26 (post-night)

Two-surveyor pass, delta-only against the night pass (#524, slot 2324,
squash-merged as `484b586f`): (A) fast-mover + pricing re-verification vs
the ~23:26 CDT baseline (vendor reads ~23:55–23:57 CDT), (B) delta news scan
~23:55–00:35 CDT (~40-min delta window). Read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-2354.md`,
`agent_notes/surveyor-b-20260926-2354.md` (under `hidden_files`).
Suffix `_POST_NIGHT` admitted per the POST_ same-day-repeat precedent —
#524's `_NIGHT` broke the POST_×8 LATE_EVENING chain deliberately, and this
is the NIGHT series' second entry, extending it past midnight's approach.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

The all-first-try streak extends to **8** — all 9 vendor pages succeeded on
first attempt this pass. Zero fetch failures, zero search fallbacks; every
page read directly from the vendor URL.

1. **Daytona changelog** (`daytona.io/changelog`, read ~23:56 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25/24/23 entries match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`, read ~23:56 CDT) —
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
nothing", 25 free trial hours, $20/$100/$500/$2000 tiers); TermSquad ($9
(2 vCPU/4 GB/40 GB) / $19 (4/8/75) / $29 (6/12/100) / $49 (8/24/200),
BYO-AI FAQ intact); DigitalOcean Managed Agents ("Last verified 22 Sep
2026"; $0.044/vCPU-hour CPU, $0.0095/GB-hour peak memory, session storage
$0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month, custom
templates $0.05/GiB-month — the standing snapshot-figure discrepancy vs the
launch release ($0.05 vs $0.005) is unresolved but unmoved); AgentComputer
($0.07 CPU-hour, $0.04375 GB-hour memory, Hot Storage $0.000683/GB-hour
(running), Cold Storage $0.000027/GB-hour (stopped) — **still no egress
policy stated, C12 stands**).

## Surveyor B — delta news scan: 0 new, 4 clean dedupes, 5 flagged-only

Quiet window (~23:55–00:35 CDT). No in-window, in-lane product launches,
pricing changes, funding events, or in-lane sandbox-escape CVEs. The in-lane
no-launch verdict of 2026-09-25 stands — streak extends. No corpus fold
recommended this pass.

Clean dedupes (4): **Daytona $24M-raise recrawls** (ancient OpenHands-demo
PR Newswire syndication, one copy showing "3047 days ago" — stale);
**Docker Cloud Sandboxes Sep-24 launch recrawls** (Register/how2shout/
webpronews — no new development); **Vercel Sandbox Drives Sep-23 beta
editorial recrawl** (nandann.com); **Daytona pitch-deck field-guide recrawl**
(Feb-2026 Series A restatement).

Flagged-only (new to surveyor B but failing lane/window bars — NOT filed):

- **Dextr AI $6.7M seed** (Sep 26, Elevation Capital-led; hotel-hospitality
  agents, not sandbox infra).
- **Nscale $3.36B convertible financing** (Sep 26; neocloud GPU compute, not
  in-lane).
- **0G "Compute Finance"** (tokenized compute, not in-lane).
- **Okta internal "Dex" agent** (name collision, not in-lane).
- **Upstash 15-provider comparison** (10 days old, editorial, fails window).

Stale-version rule: compliant this pass — no search-result version numbers
for Daytona/Microsandbox/Docker-notes appeared, so nothing to correct
(first pass without a stale-version recurrence since the rule was briefed).

Aging verdicts (this was the verdict pass): **Heapjack/Overpatch —
AGED OUT** (all hits recrawls of the Sep-15 disclosure, fixed Aug-20, no
CVE). **GitLab proxy escape (CVE-2026-85706) — AGED OUT** (recrawls only;
in-the-wild probes date to Sep 11). Dextr AI: stays aged out (seed funding
is out-of-lane).

## Carried state

Aged out this pass: Heapjack/Overpatch, GitLab proxy escape
(CVE-2026-85706). Dextr AI stays aged out. Carried: C37, C55, C57, C58
(pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY);
C26 CLOSED. In-lane no-launch verdict dated 2026-09-25 stands — streak
extends.
