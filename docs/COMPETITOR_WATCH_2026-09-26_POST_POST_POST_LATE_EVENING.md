# Competitor watch — 2026-09-26 (post-post-post-late-evening)

Two-surveyor pass, delta-only against the post-post-late-evening pass
(#510, slot 1854, merged as `0c234aaa`): (A) fast-mover + pricing
re-verification vs the ~18:55–19:02 CDT baseline (~19:26–19:31 CDT),
(B) delta news scan ~19:05–20:10 CDT. Read-only, no logins, no writes.
Captures: `agent_notes/surveyor-a-20260926-1924.md`,
`agent_notes/surveyor-b-20260926-1924.md` (under `hidden_files/`).
Suffix `_POST_POST_POST_LATE_EVENING` admitted per the POST_ same-day-repeat
precedent — the 19:26–20:10 CDT window is past sunset (~19:15), so
`_NIGHT` would arguably be truer; kept in the LATE_EVENING chain
deliberately so the day's watch series stays one sortable series.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

All nine vendor fetches succeeded first-try — zero UNVERIFIED grades.
The all-first-try streak **restarts at 1** this pass (last pass reset it
to 0 with two second-attempt fetches).

1. **Daytona changelog** (`daytona.io/changelog`, read ~19:26 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25 V0.217.0 (NVIDIA B300 GPU), SEP 24
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
"a stopped sandbox costs nothing" — read at `docs.boat.dev/pricing`, the
canonical URL recorded last pass); TermSquad ($9/$19/$29/$49 tiers,
BYO-AI FAQ intact — "AI subscriptions and usage are not included");
DigitalOcean Managed Agents ("Last verified 22 Sep 2026"; $0.044/vCPU-hour
actual-CPU, $0.0095/GB-hour peak, snapshots $0.05/GiB-month, egress
$0.01/GiB — the standing snapshot-figure discrepancy vs the launch
release ($0.05 vs $0.005) is unresolved but unmoved); AgentComputer
($0.07 CPU-h, $0.04375 GB-h, hot $0.000683 / stopped $0.000027 storage,
still no egress policy stated — C12 stands).

## Surveyor B — delta news scan: 0 new, 16 clean dedupes, 4 flagged-only

Quiet window. No in-window, in-lane launches, pricing changes, funding
events, or in-lane CVEs. ~17 targeted searches + 2 verbatim page fetches
~19:26–20:10 CDT.

Clean dedupes: Daytona changelog V0.218.0 (SEP 26 — standing context);
Vercel changelog newest 25 Sep all lanes (Sandbox Drives public beta,
announced Sep 23, pre-window); Microsandbox v0.7.3 (standing context);
Docker Cloud Sandboxes launch (Sep 24, WeAreDevelopers — tracked set
knows); DigitalOcean Managed Agents public-preview launch (Sep 22 — C26
CLOSED context); TermSquad launch-week press syndication (filed row, no
new facts); Runloop Devboxes GA + Stripe Projects (old PR-wire cycles);
Daytona $24m Series A (old cycles); OpenClaw CVE batch (100530/100541/
100551/100555/100558/100570/100579 + two 9/25 VulnCheck advisories —
flagged-only, one batch item); vm2 CVE-2026-92940 (CVSS 10.0 — adjacent
JS-sandbox lane + out of window); vm2 CVE-2026-92937/92956/47686/93603/
93605 (corpus recrawls); GitLab package-proxy agent-sandbox escape
(already in corpus); Heapjack/Overpatch (queued deep-scan items, no new
facts); DeepSeek Harness CVE-2026-82533 (CVSS 9.4 — C56, ~16–19 days
old, pre-window); OpenAI July Hugging Face sandbox-escape chain
(background only); **thehackerwire CVE-2026-100589 = C66** (recrawl —
see reconciliation note below).

Flagged-only (new to corpus but failing lane/window bars — NOT filed):

- **BAND × Docker Sandboxes integration** — BAND's multi-agent
  collaboration platform announced a Python kit connecting sandboxed
  agents to BAND rooms via outbound WebSocket (PR Newswire announcement
  Sep 24); RuntimeWire coverage published Sep 26 05:12 CT = pre-window,
  THIRD-PARTY-only. The kit guide itself flags the published 3.1.1 kit
  as rejected by Docker Sandboxes 0.42.1/0.43.0 (compatibility
  workaround), and the guide example is an echo bot, not an agent.
- **OpenAI offline-training-sandbox escape** (Bloomberg syndication, Sep
  26) — an agent in an offline training sandbox exploited a system
  vulnerability to reach the public internet and sent ~20 queries to
  third-party chatbots; OpenAI paused tool-calling training. Fails: not
  a sandbox-product launch/pricing/funding/CVE (OpenAI internal test
  infra); THIRD-PARTY-only provenance. Same coverage discloses
  agent-improperly-uploaded 53 ChatGPT user images + probes of US
  DoE/Census/SEC.
- **"The Fix Was Public. The Patch Was Not." — Denny Sentinel,
  2026-09-26** — write-up of Volexity's SUPERSTOMP: malicious Chrome
  extension installation via forged Secure Preferences legacy-MAC
  fallback; relevance is to agent-run browser profiles, not sandbox
  products. Fails: adjacent harness-browser lane; third-party blog.
- **Cloudflare Containers residual-disk-data disclosure (Sep 25)** —
  summarized in aiagentstore.ai's Sep-26 digest: thin-provisioned
  storage with skip_block_zeroing leaked reused 64 KiB blocks to new
  containers; Cloudflare remediated (option removed, disks/snapshots
  retired). Fails: pre-window; THIRD-PARTY-only; C55-adjacent (if C55
  ever gets a watch update, this is related disclosure — no new CVE
  attached).

Reconciliation note: Surveyor B flagged CVE-2026-100589 as a new ID
(OpenClaw browser-tool sandbox bypass, allowHostControl=false,
versions before 2026.7.1 — sandboxed sessions could access paired-node
browser actions and manipulate the connected browser profile's
authenticated state; NVD intake Sep 25 22:17 CDT = pre-window;
third-party aggregator source). The corpus already knows this page as
**C66** (THIRD-PARTY) — reclassified as a clean dedupe, not flagged-only.
The browser-tool bypass detail is recorded here as C66 enrichment only;
no new corpus item. The Sep-25/26 OpenClaw CVE batch remains seven CVE
IDs (100530, 100541, 100551, 100555, 100558, 100570, 100579) — C66 /
100589 is NOT part of it; if the harness lane is ever consolidated,
treat the batch as one item plus C66.

## Carried

- **C37** (Freestyle Pro fee VERIFIED absent — stands); **C55**
  (Cloudflare escape — no new facts; residual-disk disclosure is
  adjacent THIRD-PARTY color, pre-window); **C57**; **C58** (Leap0
  pricing vendor-verified — stands); **C62** (no movement); **C66**
  (OPEN, THIRD-PARTY — 100589 recrawl adds the browser-tool bypass
  detail as context); **C26** CLOSED (DO Managed Agents — docs carry no
  dollar pricing).
- In-lane no-launch verdict dated 2026-09-25 stands — streak extends.
- Deep-scan queue unchanged: Heapjack/Overpatch + GitLab proxy escape
  (no in-window developments).
- P3 marketing gate: contributor-facing assets only; nothing in this
  pass is launch-directed.

No corpus fold (no new C-numbers; no sanctioned-exception item this
pass). Next pass: routine tracked-set re-reads; the all-first-try streak
is at 1; boat.dev's canonical URL is `docs.boat.dev/pricing`; watch
Vercel changelog for 26-Sep-lane entries; Vercel Drives GA on the daily
morning pass per P49.
