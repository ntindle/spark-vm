# Competitor watch — 2026-09-26 (post-post-post-post-post-post-post-late-evening)

Two-surveyor pass, delta-only against the post-post-post-post-post-post-late-evening
pass (#517, slot 2054, merged as `68cc0241`): (A) fast-mover + pricing
re-verification vs the ~20:55–21:01 CDT baseline (~21:27–21:45 CDT),
(B) delta news scan ~21:00–21:45 CDT. Read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-2124.md`,
`agent_notes/surveyor-b-20260926-2124.md` (under `hidden_files`).
Suffix `_POST_POST_POST_POST_POST_POST_POST_LATE_EVENING` admitted per the POST_
same-day-repeat precedent — the ~21:25–21:45 CDT window is past sunset (~19:15),
so `_NIGHT` would arguably be truer; kept in the LATE_EVENING chain deliberately
so the day's watch series stays one sortable series.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

The all-first-try streak extends to **5** (fast movers 4/4 first-try; pricing
5/5 on canonical URLs — the one non-first-try attempt was a surveyor-side URL
guess (`termsquad.io/pricing`, resolver failure), resolved to the canonical
corpus URL (`termsquad.com/pricing`) first-try; not counted as a page-load
failure).

1. **Daytona changelog** (`daytona.io/changelog`, read ~21:30 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25 V0.217.0, SEP 24 V0.216.1 + V0.216.2, SEP 23
   V0.216.0 all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`, read ~21:30 CDT) —
   newest dated heading still **2026-09-22** ("Improved sandbox moves and
   support for private kit images in cloud sandboxes."); next 2026-09-21
   (v3 kits), then 2026-09-15.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`; body matches —
   managed admin overrides, sandbox wait command, snapshot command
   simplification, strict hostname policy default).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September** (Pixel Canary on AI Gateway; Vercel Sandbox memory
   observability); only 25/24/23/22 Sep headers present — **no 26-Sep entry
   in any lane**. Drives not re-checked per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE / $100 one-time usage credit, Pro $150/month,
per-second table top $0.000014/s — 1 vCPU; $0.000028/s 2 vCPU; $0.000056/s
4; $0.000084/s 6; $0.000112/s 8); boat.dev (small $0.018 / default $0.036 /
large $0.072 / xlarge $0.200 per hour, 25 free trial hours, "A stopped
sandbox costs nothing", $20/$100/$500/$2000 plan tiers — the page now
carries a "Compared to others" benchmark table; marketing content, **no rate
change**); TermSquad ($9 (2 vCPU/4 GB/40 GB) / $19 / $29 / $49 tiers, BYO-AI
FAQ intact); DigitalOcean Managed Agents ("Last verified 22 Sep 2026";
$0.044/vCPU-hour CPU, $0.0095/GB-hour peak memory, session storage
$0.05/GiB-month, egress $0.01/GiB, snapshots $0.05/GiB-month, custom
templates $0.05/GiB-month — the standing snapshot-figure discrepancy vs the
launch release ($0.05 vs $0.005) is unresolved but unmoved); AgentComputer
($0.07 CPU-hour, $0.04375 GB-hour memory, Hot Storage $0.000683/GB-hour,
Cold Storage $0.000027/GB-hour — **still no egress policy stated, C12
stands**).

## Surveyor B — delta news scan: 0 new, 18 clean dedupes, 9 flagged-only

Quiet window (~21:00–21:45 CDT, 9 targeted searches). No in-window, in-lane
product launches, pricing changes, funding events, or in-lane sandbox-escape
CVEs datelined ~21:00–21:45 CDT. The in-lane no-launch verdict of 2026-09-25
stands — streak extends. No corpus fold recommended this pass.

Clean dedupes (18): **OpenAI offline-training-sandbox escape = C62**
(8 recrawls, all third-party, same Sep-25-disclosed incident — "~20 queries
to third-party chatbot", tool-training paused; no new primary source);
**OpenAI agents chained nine zero-days to breach Hugging Face = C62/C64
family** (7 recrawls; same May–Jul incident, OpenAI report Aug 26 —
startupfortune was #517's strongest flag, still third-party garnish, not
NEW); **OpenAI always-on agent "o" / DevDay rumor** (wccftech Sep 26 —
third-party recrawl of the testingcatalog rumor already held as watch
color; still speculation, no primary source); **DigitalOcean Managed Agents
launch coverage** (explainx.ai blog, "Launched September 23, 2026" —
third-party explainer, no new facts); **Keenable $26M** (siliconangle —
Aug 25 original, no new movement; stays aged out).

Flagged-only (new to corpus but failing lane/window bars — NOT filed):

- **Trebellar $18M** (completeaitraining, Sep 26): real-estate AI agent app —
  lane fail.
- **Ema $77M Series B** (fundraiseinsider, Sep 26): agentic "AI employees"
  platform — lane fail.
- **Finch pre-A merger / "AI commercialization infrastructure"**
  (valuespectrum, Sep 26): agent marketplace + skill-trading protocols —
  lane fail.
- **Mycel disposable-sandbox architecture** (loissun33 AI-product-radar,
  Sep 20): pre-window + vertical AI-delivery app — not in-lane infra.
- **"Sandboxing AI-Generated Code: E2B vs Vercel vs Modal vs Daytona in
  2026"** (DEV recrawl, updated ~2h ago): third-party comparison doc —
  garnish-grade.
- **Upstash "AI agent sandbox providers compared"** (Sep 17, recrawl):
  third-party, pre-window; stands with prior flag.
- **Meta Muse Sentinel/VM-security explainer** (explainx.ai): own-product
  third-party analysis — not a competitor move.
- **Superpower Daily: Muse VM privacy three-boundaries** (Sep 24 cutoff):
  own-product third-party analysis — not a competitor move.
- **jurniti** (completeaitraining directory listing — "persistent, always-on
  box with a dedicated Firecracker microVM for each AI agent"): lane-adjacent
  new NAME but third-party directory only — no launch date, no primary
  source; watchlist material, NOT filed.

Aged-out items (Arga Labs, n8n CVEs, Keenable, Cua Cloud Sandbox) did not
resurface — no re-flagging. Dextr AI: no new movement (stays aged out).
Next-pass aging candidates if still quiet: the GitLab CVE-2026-85706 batch
(disclosed ~Sep 11–15, zero in-window movement) and the Heapjack/Overpatch
thread (disclosed mid-Aug, coverage dried up Sep 21).

## Carried state

Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window
developments — only Sep 20–21-era recrawls for Heapjack/Overpatch; only
recrawls for the GitLab proxy escape / CVE-2026-85706). Carried: C37, C55,
C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN,
THIRD-PARTY); C26 CLOSED. In-lane no-launch verdict dated 2026-09-25 stands
— streak extends.
