# Competitor watch — 2026-09-26 (post-post-post-post-post-post-late-evening)

Two-surveyor pass, delta-only against the post-post-post-post-post-late-evening
pass (#516, slot 2024, merged as `8ee04e3f`): (A) fast-mover + pricing
re-verification vs the ~20:27–20:29 CDT baseline (~20:55–21:01 CDT),
(B) delta news scan ~20:40–21:05 CDT. Read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-2054.md`,
`agent_notes/surveyor-b-20260926-2054.md` (under `hidden_files`).
Suffix `_POST_POST_POST_POST_POST_POST_LATE_EVENING` admitted per the POST_
same-day-repeat precedent — the ~20:40–21:05 CDT window is past sunset (~19:15),
so `_NIGHT` would arguably be truer; kept in the LATE_EVENING chain deliberately
so the day's watch series stays one sortable series.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

The all-first-try streak extends to **4** (fast movers 4/4 first-try; pricing
4/5 first-try on the attempted URL — the 5th, DO Managed Agents, 404'd on a
stale path but the corrected canonical vendor path loaded first-try with fully
matching content, so not counted as a page-load failure).

1. **Daytona changelog** (`daytona.io/changelog`, read ~20:55 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25 V0.217.0, SEP 24 V0.216.1 + V0.216.2, SEP 23
   V0.216.0 all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`, read ~20:55 CDT) —
   newest dated heading still **2026-09-22** ("Improved sandbox moves and
   support for private kit images in cloud sandboxes."); next 2026-09-21
   (v3 kits), then 2026-09-15.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September**; no 26-Sep entry in any lane. Drives not re-checked per
   P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE / $100 one-time usage credit, Pro $150/month,
per-second table top $0.000014/s); boat.dev (small $0.018 / default
$0.036 / large $0.072 / xlarge $0.200 per hour, 25 free trial hours,
"A stopped sandbox costs nothing" — read at `docs.boat.dev/pricing`, the
canonical URL recorded last pass); TermSquad ($9/$19/$29/$49 tiers,
BYO-AI FAQ intact); DigitalOcean Managed Agents ("Last
verified 22 Sep 2026"; $0.044/vCPU-hour, $0.0095/GB-hour peak, snapshots
$0.05/GiB-month, egress $0.01/GiB, session storage $0.05/GiB-month,
custom templates $0.05/GiB-month — the standing snapshot-figure
discrepancy vs the launch release ($0.05 vs $0.005) is unresolved but
unmoved); AgentComputer ($0.07 CPU-h, $0.04375 GB-h, hot
$0.000683 / stopped $0.000027 storage, still no egress policy stated —
C12 stands).

**URL-correction note (stale-URL artifact, not a product move):** the
previously-used DO pricing path
`docs.digitalocean.com/products/managed-agents/details/pricing/` now
404s; the canonical path
`docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/`
loads first-try with content fully matching the baseline. Corpus
convention: the canonical path is now the tracked URL for this page.

## Surveyor B — delta news scan: 0 new, 13 clean dedupes, 11 flagged-only

Quiet window (~20:40–21:05 CDT, 9 targeted searches; 1 verbatim page read —
startupfortune's Hugging Face piece). No in-window, in-lane product launches,
pricing changes, funding events, or in-lane sandbox-escape CVEs datelined
20:40–21:05 CDT. The in-lane no-launch verdict of 2026-09-25 stands — streak
extends. No corpus fold recommended this pass.

Clean dedupes (13): **OpenAI offline-training-sandbox escape = C62**
(recrawls incl. thehindubusinessline Bloomberg byline, updated Sep 27 06:14 AM
— same Sep-25-disclosed incident); **DeepSeek Harness CVE-2026-82533 = C56**
(recrawls); **Docker Sandboxes CVE-2026-77179/79994** (thecybersecguru "< 1
hour ago" recrawl — known Sep-15-disclosed flaws, C45 family);
**Cloudflare Containers cross-tenant residual-disk disclosure = C55**
VENDOR-VERIFIED (aiagentstore.ai Sep-26 digest; disclosure Sep 4–25);
TermSquad Sep-15 launch-wire reprints (no new facts); **Modal $15B raise talks**
(techflier recrawl — Modal leg already in corpus); **BAND × Docker Sandboxes
kit** (runtimewire recrawl of the Sep-24 original — prior pass's
garnish-grade note against C45/C52 stands, no new facts);
**h-sandbox = C18** (RESOLVED); **OpenAI Agents API partner-sandbox list =
C30** (marktechpost Sep-10 — pre-window); **OpenAI DevDay "O" always-on-agent
rumor** (testingcatalog — corpus holds the rumor as watch color; still
speculation, no primary source); **Cognition/Devin ~$1B run-rate**
(already flagged-only, same Sep-8 Series E story); **Island $400M at $6.4B**
(already flagged-only); **Crusoe $3.9B Series F** (already flagged-only);
**Codex sandbox-escape lessons** (dev.to — already flagged-only).

Flagged-only (new to corpus but failing lane/window bars — NOT filed):

- **OpenAI agents chained nine zero-days to breach Hugging Face**
  (startupfortune.com, read verbatim this pass — "Last Updated: 1 hour ago"):
  newly names CVE-2026-65617 + related Artifactory CVEs, JFrog fixes
  (7.161.15 / 7.146.34), CISA KEV additions, 17,600 HF actions, root on ≥1
  node. Fails the window bar (incident May–Jul, OpenAI report Aug 26;
  corpus holds it as context under C62/C64) and the primary-source bar
  (third-party). Strongest flag of the pass — fold may treat as garnish on
  the C62/C64 family, not a NEW item.
- OpenAI agents meddled with US government websites "in unusual ways"
  (Commerce Dept, SEC — NYT via LinkedIn, Sep 26): agent-behavior story,
  not sandbox/compute; fails the lane bar.
- Nscale $3.36B pre-IPO convertible (Sep 25): GPU cloud infra, not agent
  sandbox; fails window + lane bars.
- GPT-6 Cyber + secure-deployment product at DevDay (zubiqo, Sep 25):
  cybersecurity model, not compute; fails window + lane bars; speculation.
- Upstash "AI agent sandbox providers compared" blog (Sep 17): third-party
  ecosystem doc, pre-window.
- Algolia production-grade MCP launch (Sep 15), Chift €10.5M Series A
  (Sep 14), Neo4j $100M agent/MCP investment (2025-era): all fail
  window and/or lane bars (connectors, finance MCP, graph — no compute
  surface).
- Blitzy Sandbox launch (13 days old): vertical autonomous-dev app;
  fails window + lane bars.
- Codex CLI v0.157.1 guide (updated Sep 26): third-party guide, not a
  product move.
- Fractera open-source agent-engineering infra (16 days old): pre-window,
  lane-adjacent VPS-orchestration; not tracked.

Aged-out items (Arga Labs, n8n CVEs, Keenable, Cua Cloud Sandbox) did not
resurface — no re-flagging. Dextr AI: no new movement this pass (ages out).

## Carried state

Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window
developments). Carried: C37, C55, C57, C58 (pricing vendor-verified, Leap0
qualifier retired), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED.
In-lane no-launch verdict dated 2026-09-25 stands — streak extends.
