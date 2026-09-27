# Competitor watch — 2026-09-26 (post-post-post-post-late-evening)

Two-surveyor pass, delta-only against the post-post-post-late-evening pass
(#512, slot 1924, merged as `41d92cb`): (A) fast-mover + pricing
re-verification vs the ~19:26–19:31 CDT baseline (~19:56–19:59 CDT),
(B) delta news scan ~19:55–19:58 CDT. Read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-1954.md`,
`agent_notes/surveyor-b-20260926-1954.md` (under `hidden_files/`).
Suffix `_POST_POST_POST_POST_LATE_EVENING` admitted per the POST_
same-day-repeat precedent — the ~19:55–19:59 CDT window is past sunset
(~19:15), so `_NIGHT` would arguably be truer; kept in the LATE_EVENING
chain deliberately so the day's watch series stays one sortable series.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

All nine vendor fetches succeeded first-try — zero UNVERIFIED grades.
The all-first-try streak extends to **2** (this pass and the 1924 pass
both all-first-try).

1. **Daytona changelog** (`daytona.io/changelog`, read ~19:57 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25 V0.217.0 (NVIDIA B300 GPU); SEP 24
   V0.216.1 / V0.216.2 — all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`, read ~19:57 CDT) —
   newest dated heading still **2026-09-22** ("Improved sandbox moves and
   support for private kit images in cloud sandboxes."); next 2026-09-21
   (v3 kits).
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September** (Sandbox memory observability); no 26-Sep entry in
   any lane. Drives not re-checked per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE / $100 one-time usage credit, Pro $150/month,
per-second table top $0.000014/s); boat.dev (small $0.018 / default
$0.036 / large $0.072 / xlarge $0.200 per hour, 25 free trial hours,
"a stopped sandbox costs nothing" — read at `docs.boat.dev/pricing`, the
canonical URL recorded last pass); TermSquad ($9/$19/$29/$49 tiers,
BYO-AI FAQ intact — agent list now includes Claude Code, Codex, OpenCode,
Cursor, Antigravity, Grok Build, Command Code, Pi, Devin, Kimi Code,
GitHub Copilot, Factory Droid); DigitalOcean Managed Agents ("Last
verified 22 Sep 2026"; $0.044/vCPU-hour actual-CPU, $0.0095/GB-hour
peak, snapshots $0.05/GiB-month, egress $0.01/GiB — the standing
snapshot-figure discrepancy vs the launch release ($0.05 vs $0.005) is
unresolved but unmoved); AgentComputer ($0.07 CPU-h, $0.04375 GB-h, hot
$0.000683 / stopped $0.000027 storage, still no egress policy stated —
C12 stands).

## Surveyor B — delta news scan: 0 new, 9 clean dedupes, 7 flagged-only

Quiet window (~19:55–19:58 CDT, 8 searches + 1 verbatim page fetch).
No in-window, in-lane launches, pricing changes, funding events, or
in-lane sandbox-escape CVEs.

Clean dedupes: **OpenAI offline-training-sandbox escape = C62**
(recrawl enrichment — Particle reports OpenAI suspended *all*
tool-using model training/eval/inference pending review, disclosed 53
agent-uploaded ChatGPT images + US DoE/Census/SEC probes; same incident,
no new corpus item); **OpenClaw CVE-2026-100589 = C66** (TheHackerWire
recrawl; its Sep 26 03:17 UTC timestamp = Sep 25 22:17 CDT, pre-window);
**DeepSeek Harness CVE-2026-82533 = C56** (Forkast + OX Security
recrawls, ~16–19 days old); TermSquad Sep-15 launch-wire syndication
(scraper reprints, no new facts); **Modal $15B raise talks** (bytevyte
roundup adds Baseten $26B parallel talks — corpus already holds the
Modal leg); **Factory $200M at $5B** (Sep 15 Reuters — corpus-known);
**Modal off-Kubernetes rebuild = C61** (no in-window development);
**DigitalOcean Managed Agents public preview (Sep 22) = C26 CLOSED,
Prime Intellect Prime Sandboxes GA (C48), Microsoft Copilot Managed
Runtime (C50), Google AX v0.3.0 (C47), Runloop Devboxes GA** (no
in-window news — standing context); Daytona changelog V0.218.0 / Vercel
newest 25 Sep / Microsandbox v0.7.3 (Surveyor A's 19:26–19:31 vendor
reads are the standing baseline).

Flagged-only (new to corpus but failing lane/window bars — NOT filed):

- **Arga Labs $10M seed** (General Catalyst-led; ~Aug 26, 2026 —
  ~31 days pre-window) — "build sandbox environments for enterprise AI
  agent training"; in-lane-adjacent (convergent with the C49 DSec
  training-sandbox theme) but fails the **window bar** and is
  THIRD-PARTY-only (cryptobriefing).
- **n8n expression-sandbox escapes CVE-2026-86076 + CVE-2026-86083**
  (openveil.app blog, ~Sep 14 — pre-window) — two expression-sandbox
  failures (sanitizer-rebinding constructor exposure; shared-builtin
  tamper) turning workflow-authoring access into code execution as the
  n8n process; fixed in n8n 1.123.76 / 2.37.7 / 2.38.2; no mass
  exploitation claimed. Fails **lane bar** (workflow-editor expression
  sandbox, not agent-VM/compute sandbox) and **window bar**.
- **Cua Cloud Sandbox** (trycua/cua blog, published **May 28, 2025**) —
  remote Linux desktop sandboxes (Xfce/VNC), 3 tiers
  (Small 1vCPU/4GB, Medium 2vCPU/8GB, Large 8vCPU/32GB), pay-per-use,
  BYO API keys, elastic pools + Windows/macOS roadmap. In-lane *shape*
  (computer-use VMs) but 16 months pre-window; the corpus reach-back bar
  (primary-source correction required) is not met. Note: trycua is the
  user's own CUA-driver stack; no action.
- **Cognition/Devin ~$1B annualized revenue** (fresh coverage <1h old) —
  per-seat + Agent Compute Unit billing, $48B valuation Sep raise.
  Fails **lane bar** — demand signal for coding agents, not a
  sandbox/agent-compute product move.
- **Dextr AI leaves stealth, $6.7M seed** (Sep 26, Elevation /
  Foundation Capital) — hotel front-desk agents. In-window but fails
  **lane bar** — vertical agent app, no sandbox/compute surface.
- **Keenable $26M** (Aug 25, Accel/Conviction) — agentic web-search
  infrastructure. Fails **lane bar** and **window bar**.
- **AgentX $23M** (~1 day old) — autonomous-workflow agent platform.
  Fails **lane bar** — no compute/sandbox surface in the coverage.

## Carried

- **C37** (Freestyle Pro fee VERIFIED absent — stands); **C55** (adjacent;
  Cloudflare residual-disk color from the 1924 pass stays C55-adjacent);
  **C57** (Baponi); **C58** (Leap0); **C66** (OPEN, THIRD-PARTY —
  recrawls this pass add remediation/timeline color only);
  **C26** CLOSED (DO Managed Agents).
- In-lane no-launch verdict dated 2026-09-25 stands — streak extends.
- Deep-scan queue unchanged: Heapjack/Overpatch + GitLab package-proxy
  escape (no in-window developments).
- No corpus fold (no new C-numbers; no sanctioned-exception item this
  pass). Stale-24h items (Arga, n8n CVEs) age out of reach-back unless a
  primary-source correction demands otherwise. Watch: Vercel changelog
  for 26-Sep-lane entries; DO pricing snapshot-conflict stands resolved
  at $0.05 (no new movement); Automaid lane-drift confirmed, watch slot
  closed (no re-check needed).

Next pass: routine tracked-set re-reads + the standard news sweep.
