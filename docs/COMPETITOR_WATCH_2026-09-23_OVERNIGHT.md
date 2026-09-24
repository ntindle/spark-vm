# Competitor watch — 2026-09-23 (overnight)

Delta-only update against the late-night pass
(`docs/COMPETITOR_WATCH_2026-09-23_LATE_NIGHT.md`). Survey window
**2026-09-23 ~21:55–22:00 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set, (B) Vercel Drives GA watch, a Boxd rate-card re-attempt,
an Automaid own-page re-attempt, a C36 re-check, newcomer vetting for two
of the six named candidates, and an open-web market-news scan. Surveyor
captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260923-2154.md`), not the repo.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) rather than a vendor doc-page assertion — a stricter claim
than VERIFIED, used only when we fetched the thing itself.
**THIRD-PARTY** = reported by press/third-party sources, including
vendor-announcement text read on a syndicated copy (e.g. a Business
Wire release) rather than the vendor's own page.
**snippet-only** = a THIRD-PARTY sub-state: seen only via search
snippet or aggregator digest this run, not fetched and read — no
stronger claim than its source's blurb.
**INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.
**UNVERIFIED** = a public page exists but could not be fetched this
run (never reported as NO-CHANGE).

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

All reads within the survey window; all values below VERIFIED on the
vendor's own page. The fifth full quiet 8/8 re-read pass since the
mid-afternoon fold (roughly 3 hours since the late-night pass).

- **Daytona** — VERIFIED NO-CHANGE: changelog still topped by
  **SEP 23 2026 / V0.216.0** ("Confine Dockerfile COPY sources to the
  build context" — Python, Ruby, TypeScript SDKs); no new entry today.
  (https://www.daytona.io/changelog)
- **Docker Sandboxes** — VERIFIED NO-CHANGE: release notes still top out
  **2026-09-21** (v3 kits: OCI-based packages combining an agent
  workload with reusable mixins for tools, configuration, credentials,
  network access, and agent instructions).
  (https://docs.docker.com/ai/sandboxes/release-notes/)
- **Microsandbox** — VERIFIED NO-CHANGE: top release still **v0.7.1**.
  (https://github.com/superradcompany/microsandbox/releases)
- **E2B** — VERIFIED NO-CHANGE: pricing tiers unchanged (Hobby free with
  $100 one-time credit / sessions up to 1 hour; Pro $150/month /
  24-hour sessions, 100 concurrent sandboxes expandable to 1,100;
  per-second table $0.000014/s).
  (https://e2b.dev/pricing)
- **boat.dev** — VERIFIED NO-CHANGE: rate table unchanged (small
  $0.018 / default $0.036 / large $0.072 / xlarge $0.200 per sandbox
  hour; 25 free trial hours). Context-only color (not a change): the
  comparison table boat.dev publishes now quotes Daytona at
  $0.166–$1.32/hr across sizes — same arithmetic as E2B, unchanged
  figures.
  (https://docs.boat.dev/pricing)
- **TermSquad** — VERIFIED NO-CHANGE: plan table unchanged (Starter
  $9/mo 2 vCPU/4 GB/40 GB … Ultra $49/mo 8 vCPU/24 GB/200 GB; BYOK FAQ
  unchanged).
  (https://termsquad.com/)
- **AgentComputer** — VERIFIED NO-CHANGE: pay-as-you-go table unchanged
  ($0.07/CPU-hour, $0.04375/GB-hour, hot storage $0.000683/GB-hour
  running, cold $0.000027/GB-hour stopped).
  (https://www.agentcomputer.ai/pricing)
- **DigitalOcean Managed Agents** — VERIFIED NO-CHANGE: pricing docs
  sub-page stamp still **"Last verified 22 Sep 2026"**; CPU
  $0.044/vCPU-hour, memory $0.0095/GB-hour, session storage
  $0.05/GiB-month; snapshots/checkpoints $0.05/GiB-month (the
  mid-evening C26 resolution stands — read live again this pass, not
  carried); active-CPU-billing footnote intact ("billed at 25% of the
  vCPUs allocated … until Active CPU billing ships"); BYOT
  $0.05/GiB-month; egress $0.01/GiB.
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/)

## 2. Adjacent checks

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (16th consecutive
  no-change pass).** Pricing page `last_updated` still **2026-09-10**;
  the changelog entry the page links — "Drives for Vercel Sandbox are
  now in public beta" — is still the latest Drives-status statement
  (read on the vendor's own changelog this pass); no GA move.
  Drives pricing rows unchanged (Drive Storage $0.05/GB-month; Reads
  $0.0015/GB; Writes $0.004/GB; up to 4 drives per sandbox, 1 TiB
  default / 1 GiB Hobby, 16 TiB max). Adjacent color on the same page:
  "Vercel Sandbox can now run for up to 24 hours" on Pro/Enterprise —
  an anti-always-on easing worth watching, not a product move.
  (https://vercel.com/docs/sandbox/pricing)
- **Boxd (C29) — rate card now VERIFIED (first successful own-page
  fetch).** The https://boxd.sh pricing FAQ fetched clean this run and
  confirms all four numbers: **€0.049/vCPU-hour** while running,
  **€0.015/GiB-hour** resident RAM (running or standby),
  **€0.0001/GiB-hour** of disk actually written (never provisioned
  size), **€30 free credits** for every new account; no idle-compute
  charge, hibernated machines pay disk only. This resolves the two-pass
  UNVERIFIED debt — the figures stand as quoted since filing, and now
  as primary-source-verified. Also VERIFIED on the same page: real KVM
  VMs (own kernel, not containers); Ubuntu 24.04 defaults 2 vCPU / 8
  GB / 100 GB; sub-200 ms live memory forks; suspend-to-disk with
  instant resume; checkpoints, snapshots; self-host option; per-machine
  HTTPS subdomains; org-level secrets/domains; MCP server for Claude
  Code / Codex / opencode. The "resume in under a millisecond"
  marketing figure stays vendor-published-only, no methodology — NOT a
  C14 benchmark input. Corpus fold: yes (C29 rate card moves
  UNVERIFIED → VERIFIED).
- **C36 Google Agent Substrate — no new vendor datapoints; no GA move,
  allowlist-only production stands.** (And: the #320 review's Product
  nit is folded here — the late-night pass's recent-color items now
  carry their provenance: Substrate-on-GKE open-sourced, non-production
  for GKE customers, production support via allowlist only
  (deliberately not full GA) — **VENDOR-CONFIRMED** (2026-09-23 ~16:00
  CDT Cloud-blog read); Nous Research (Hermes) early design partner —
  **VENDOR-CONFIRMED**; Google also open-sourced the AX agent
  orchestrator on K8s (Apache-2.0) — **THIRD-PARTY** (itbrief.co.uk) —
  adjacent tooling, not a competitor move.)
- **Automaid — lane-drift CONFIRMED on the vendor's own page.** The
  own-page fetch SUCCEEDED for the first time (https://automaid.it.com
  fetched clean): "Automaid | AI agents for recurring work" — a
  recurring-workflow automation SaaS (Zapier-style: WhatsApp scheduler,
  Stripe invoice follow-ups, form triage, content-calendar sync,
  payment review workspaces) with 3,000+ app integrations. Nothing
  resembling VM-for-agents infrastructure. The two-pass UNVERIFIED debt
  is closed and the verdict is final: lane-drift, not a lane
  competitor — off the watch list (no further re-attempts needed).

## 3. Newcomer vetting — two more of the six named candidates

From the THIRD-PARTY Upstash 15-provider comparison's newcomer list
(Upstash Box, Freestyle, Ascii Box, Namespace, Beam, Tensorlake). Note
the #320 review's Architecture cross-reference is folded here:
**Upstash Box is already a corpus entry (C31)** — it is not a new
candidate, just a named reference. Two more candidates vetted this
pass (primary-source reads):

- **Freestyle — IN-LANE, VERIFIED (C37).** https://freestyle.sh:
  "Freestyle — VMs for AI Agents": instant, hardware-virtualized Linux
  microVMs for AI agents with live cloning, pause/resume, nested
  virtualization (Docker inside), custom domains, WireGuard tunnels,
  full-kernel features (FUSE, eBPF). Vendor claims 65 ms boot and
  "run forever" with idle-timeout disabled; SSH / VS Code / Cursor
  access. Pricing/snapshot mechanics stay **THIRD-PARTY only** (own
  pricing page not read this run; the Upstash comparison gives
  wall-clock per-second billing, $0.04032/vCPU-h, $0.0129/GiB-h, free
  tier 200 vCPU-h + 400 GiB-h/month, with a docs-vs-pricing discrepancy
  on whether persistent VMs are free). Corpus fold: yes — new C37
  entry.
- **Tensorlake — IN-LANE, VERIFIED (C38).** https://tensorlake.ai:
  "Tensorlake — Sandboxes for AI Agents": Firecracker microVM sandboxes
  paired with a versioned POSIX filesystem (`tl fs`, autosave,
  snapshot/time-travel), hosted/mountable Git, and a sandbox-native
  orchestration runtime. VERIFIED mechanics (own page): suspend/resume
  preserving memory + processes + filesystem (~1 s wake, meter stops on
  suspend); live VM fork/clone (memory + filesystem copied whole);
  `tl fs` autosaves settled writes to durable storage, snapshot =
  permanent checkpoint, restore to any point in time, read-only shared
  mounts; OCI image import with high-fidelity ext4 conversion;
  auto-suspend on idle with wake-on-request; SSH / VS Code / Cursor /
  PTY-over-WebSocket remote dev; Harbor eval integration; SOC 2 Type
  II + HIPAA; own SQLite benchmark vs Vercel/E2B/Daytona/Modal (own
  marketing — take as marketing). Pricing: not observed on the homepage
  this run — no pricing claim made. Corpus fold: yes — new C38 entry.
- Still unvetted from the list: Ascii Box, Namespace, Beam.

## 4. Market-news scan

- **Vercel Sandbox SDK/CLI changelog entries dated 2026-09-23
  (THIRD-PARTY — releasebot.io parsing of Vercel release notes, "date
  parsed from source: Sep 23, 2026"):** sandbox attachment to Secure
  Compute networks (`networkId` in the SDK, `--network-id` in the CLI);
  network-policy response rules (the sandbox proxy can answer trailing
  unmatched requests, restricting allowed domains to paths without a
  custom proxy); agent attribution tagging (the AI-agent driver is
  stamped as `agent/<name>` in the user-agent via detect-agent); patch
  fixes for resuming sessions during stop/snapshot and for
  sandbox-integration test stability. These are developer-ergonomics
  moves, not pricing/GA — not folded (third-party-only), but the
  network-policy response-rules mechanic is one to watch against
  spark-vm's own sandbox-proxy design.
- **No in-lane launch/GA/funding/pricing move dated 2026-09-23** beyond
  the Vercel SDK items above: explicit negative for E2B, Daytona,
  Modal, Runloop, Blaxel, Microsandbox. E2B's $21M Series A
  (THIRD-PARTY, vestbee, Insight Partners lead) surfaced in the
  windowed search but carries no explicit 09-23 date — recent, not
  dated in-window. Adjacent pre-window items (DO Managed Agents launch
  already tracked; Tencent Cloud DataBuddy already lane-drift; the
  Okta-led Blueprint Alliance for agent identity) are adjacent color,
  not in-lane moves.

## 5. Fold decision

Three corpus folds this pass (primary-source-verification / new-entry
per the C32/C31 precedents): (1) **C29 rate card moves UNVERIFIED →
VERIFIED** (own-page fetch this run — the first successful one); (2)
**C37 — Freestyle, new in-lane corpus entry** (own-page VERIFIED
in-lane; pricing stays THIRD-PARTY); (3) **C38 — Tensorlake, new
in-lane corpus entry** (own-page VERIFIED in-lane; no pricing
observed). Automaid's lane-drift confirmation needs no fold (it was
never a corpus entry) — its watch-list slot is closed. The Vercel
SDK/CLI items stay third-party color, not folded. Nothing closes
(other than the Automaid debt).

## 6. Verdict

In-lane: **busy in the margins, quiet at the core.** The tracked set
stays frozen (8/8 VERIFIED NO-CHANGE, fifth full quiet pass since the
mid-afternoon fold); 16th consecutive quiet Vercel Drives pass; C36
unchanged. The action is all in the adjacent tier: Boxd's rate card is
finally vendor-verified (C29 debt resolved), the Automaid watch is
over (own page confirms it's a workflow-automation SaaS — lane-drift),
and two of the six newcomer candidates vet IN-LANE on their own pages
(Freestyle, Tensorlake — C37, C38). No in-lane launches, GA moves,
funding, or pricing moves dated today.

## Next-pass asks

- Routine tracked-set re-reads; Vercel Drives GA watch (17th pass).
- Vet the remaining newcomer candidates (Ascii Box, Namespace, Beam)
  against primary sources before any tracked-set consideration.
- Read Freestyle's own pricing page (own-page verification of the
  THIRD-PARTY rates); watch Tensorlake for published pricing.
- C36: vendor-page verification of the GKE offering terms (standing ask).
