# Competitor watch — 2026-09-26 (post-late-evening)

Two-surveyor pass, delta-only against the late-evening pass (#505,
slot 1724, merged as `2020967`): (A) fast-mover + pricing
re-verification vs the ~16:24 CDT baseline (~17:55–17:56 CDT), (B) delta
news scan ~17:30–18:02 CDT. Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260926-1754.md`,
`agent_notes/surveyor-b-20260926-1754.md` (under `hidden_files/`).
Suffix `_POST_LATE_EVENING` admitted per the POST_ same-day-repeat
precedent (`_POST_LATE_MORNING`, `_POST_MID_MORNING`, etc.) — 17:5x CDT
is still evening (sunset ~19:15), so `_NIGHT` would be dishonest.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

All nine vendor fetches succeeded first try — zero fetch failures, zero
UNVERIFIED grades (ninth consecutive all-first-try pass for this set;
~26 min after the #505 baseline).

1. **Daytona changelog** (`daytona.io/changelog`, read ~17:55 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"). Next: SEP 25 V0.217.0 (NVIDIA B300 GPU), SEP 24
   V0.216.1 / V0.216.2 — all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`) — newest dated heading
   still **2026-09-22**.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September** (memory observability); Drives entry still "public beta"
   (23 Sep), not GA; no 2026-09-26 entry in any lane. Drives not re-checked
   per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE / $100 one-time usage credit, Pro $150/month,
per-second table top $0.000014/s); boat.dev (small $0.018 / default
$0.036 / large $0.072 / xlarge $0.200 per hour, 25 free trial hours,
stopped sandbox costs nothing); TermSquad ($9/$19/$29/$49 tiers, BYO-AI
intact); DigitalOcean Managed Agents (per-second billing; $0.044/vCPU-hour
actual-CPU, $0.0095/GB-hour peak, snapshots $0.05/GiB-month, egress
$0.01/GiB — **no new dollar pricing**; the standing snapshot-figure
discrepancy vs the launch release is unresolved but unmoved); AgentComputer
($0.07 CPU-h, $0.04375 GB-h, hot $0.000683 / stopped $0.000027 storage,
still no egress policy stated — C12 stands).

## Surveyor B — delta news scan: 0 new, 10 clean dedupes, 4 flagged-only

Quiet window. No in-window, in-lane launches, pricing changes, funding
events, or in-lane CVEs. 10 targeted searches ~17:56–18:02 CDT.

Clean dedupes: Docker Cloud Sandboxes press recrawls (filed row — Sep 24
WeAreDevelopers launch, Micro $0.07/h → XL $1.12/h, no new facts);
Cloudflare sandbox-escape disclosure = **C55** (dm-thin
`skip_block_zeroing` root cause, disclosed ~Sep 24, recrawls only);
vm2 CVE-2026-93603 + CVE-2026-93605 (fixed 3.12.1, already flagged-only);
vm2 CVE-2026-92937 (Promise call/apply bypass, fixed 3.11.7 — already
flagged-only, stackflag recrawl); vm2 CVE-2026-92956 (WebAssembly
compileStreaming, fixed 3.11.7 — already flagged-only, stackflag recrawl);
vm2 CVE-2026-47686 (Error.cause, fixed 3.11.6, CVSS 9.9 — already
flagged-only, 1day-archive PoC recrawl); OpenClaw CVE-2026-100579
(kept separate from C66); GitLab package-proxy agent-sandbox escape
(already in corpus, pre-window, no new facts); Heapjack/Overpatch
recrawls (queued deep-scan items, coverage all Sep 15–21 — queue
unchanged). Corroborating color: Daytona changelog search shows nothing
newer than V0.218.0; Microsandbox search shows nothing newer than v0.7.3;
Fly.io GPU docs still carry the "deprecated after August 1" banner
(pre-window).

Flagged-only (new to corpus but failing lane/window bars):

1. **CVE-2026-92940** (vm2 3.10.1–3.11.6, fixed 3.11.7 — host
   `https.globalAgent` singleton exposed to sandbox; cross-tenant
   credential/headers theft; CVSS 10.0; VulnCheck CVE'd 2026-09-17,
   advisory updated 2026-09-20) — NOT filed: adjacent JS-sandbox lane and
   outside the window. Distinct from 92937/92956/47686/93603/93605; worth
   a name-check if vm2 CVEs are ever consolidated.
2. **CVE-2026-100558** (OpenClaw < 2026.8.1 — unauthenticated Gateway
   listener resource exhaustion via malformed WebSocket upgrade, CWE-400,
   CVSS 7.5; published 2026-09-26T02:18Z) — NOT filed: adjacent harness
   lane + ~20h pre-window.
3. **CVE-2026-100570** (OpenClaw 2026.3.28–2026.8.1 — untrusted workspace
   `.env` sets `CLOUDSDK_PYTHON_ARGS` → code execution on operator-run
   Gmail setup, CWE-88) — NOT filed: adjacent harness lane + pre-window
   receipt (2026-09-25 22:17 CDT).
4. **OpenClaw VulnCheck advisories dated 9/25/2026** (MCP-channel
   authentication bypass, CVSS 8.6; CSV formula injection via attendance
   export, CVSS 5.3) — NOT filed: adjacent harness lane + out of window.

## Carried

- **C37** (Freestyle Pro fee VERIFIED absent — stands); **C55**
  (Cloudflare escape — no new facts); **C57**; **C58** (Leap0 pricing
  vendor-verified — stands, #505 fold); **C62** (no movement); **C66**
  (OPEN, THIRD-PARTY); **C26** CLOSED (DO Managed Agents — no new dollar
  pricing this pass).
- In-lane no-launch verdict dated 2026-09-25 stands — streak extends.
- Deep-scan queue unchanged: Heapjack/Overpatch + GitLab proxy escape.
- P3 marketing gate: contributor-facing assets only; nothing in this
  pass is launch-directed.

No corpus fold (no new C-numbers; no sanctioned-exception item this
pass). Next pass: routine tracked-set re-reads; watch Vercel changelog
for 26-Sep-lane entries; Vercel Drives GA on the daily morning pass per
P49.
