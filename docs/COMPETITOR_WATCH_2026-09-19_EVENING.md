# Competitor watch — 2026-09-19 (evening)

Delta-only against the 2026-09-19 consolidated market-moves section in
`docs/COMPETITOR_ANALYSIS.md` (folded ~17:54 CDT). Survey window: 2026-09-19
~18:00 → ~23:00 CDT. **VERIFIED** = read on a vendor's own page, doc, repo,
or security announcement in this pass (link inline). **INFERRED** =
third-party characterization, labeled as such.

## Docker Sandboxes — vendor notes direct read + price signal (C13)

- **VERIFIED (Docker's own
  [release notes](https://docs.docker.com/ai/sandboxes/release-notes/), read
  directly 2026-09-19 evening):** the two vulnerability-class entries the
  consolidation flagged as third-party-quoted-from-vendor are now **vendor
  text**: "Fixed a vulnerability where a sandboxed process could get the
  daemon to open a host D-Bus transport and execute an arbitrary command on
  the host" and "Fixed a vulnerability where a malicious sandbox could
  hijack another sandbox's OAuth login by pre-claiming its callback port."
  Still no CVE named for either. **CORRECTION to the consolidation:** the
  two CVEs *are* now named in the 0.42.0 notes — "Fixed
  [CVE-2026-77179](https://www.cve.org), a symlink vulnerability in the
  virtio-fs host server on macOS…" and "Fixed
  [CVE-2026-79994](https://www.cve.org), a symlink race in the guest-to-host
  Unix domain socket relay…" The 2026-09-19 consolidation pass's direct
  read showed no CVE names in these notes; this evening's direct read
  does. **INFERRED (author's inference, not vendor fact):** the notes
  appear to have been amended post-publication, presumably after the CVE
  records were published — the CVE-record publication date itself was not
  re-verified in this pass. The "shipped unlabeled" line was accurate to
  the morning read and is now stale; the disclosure-timeline lesson for
  the trust doc stands (verify version numbers against vendor pages).
- **VERIFIED (same page, 0.43.0 section, Sep 15):** trust-model hardening
  the consolidation hadn't itemized: `sbx create` sandboxes now **stop
  automatically after becoming idle** (idle-economics datapoint for C5);
  credential-binding consent **defaults to decline** and identifies when
  API-key secrets will be sent to new domains; `sbx secret rm --sandbox`
  revokes the credential from the sandbox proxy immediately; the sandbox
  egress proxy no longer forwards a client-supplied credential the proxy
  did not issue to managed provider hosts; minimum sandbox memory dropped
  to 512 MiB ("only suitable for shell use cases"); `sbx env` shows a plan
  of everything the environment file changes on the host and asks before
  applying; blocked-by-org-policy hosts now read "Blocked by org policy"
  instead of suggesting `sbx policy allow`.
- **VERIFIED (Docker's own
  [FAQ](https://docs.docker.com/ai/sandboxes/faq/), "Is Docker Sandboxes
  free? Can I use it commercially?"):** "The `sbx` CLI is free to use,
  including for commercial and professional work, with **no per-seat fee**.
  Install it, sign in with a free Docker account, and run sandboxes at no
  cost. The only paid component is organization governance: centrally
  managed network, filesystem, and MCP policies, sign-in enforcement, and
  audit logs… require a separate paid subscription — contact Docker Sales."
  This closes the corpus note's owed price signal: Docker Sandboxes enters
  "The field at a glance" as a task-scoped entry priced **free for the CLI
  / per-org-paid governance**. Docker's org-governance shape (centrally
  managed network/filesystem/MCP policies, sign-in enforcement, audit
  logs) is a new vendor entry for the H16 org-policy design run — it was
  not in PR #101's vendor set (GitHub, Vercel, Daytona, Runloop, Upstash).
- **Implication:** Docker is converging on host-side credential proxying
  with consent-default-decline — the credential-proxy differentiation (win
  #3) must keep resting on persistence + request-body-scope substitution +
  open source, not on isolation hygiene or "runs without keys" alone.
  Idle auto-stop corroborates the C5 suspend-economics direction (stopped
  boxes bill cold, not wall-clock).

## TermSquad (C1) — no moves; pricing re-verified; watch-method gap still open

- **VERIFIED ([termsquad.com/pricing](https://termsquad.com/pricing), read
  2026-09-19 evening):** $9/$19/$29/$49 tiers unchanged (Starter 2 vCPU / 4
  GB / 40 GB NVMe; Builder 4 / 8 / 75; Power 6 / 12 / 100; Ultra 8 / 24 /
  200); "AI subscriptions and usage are not included" unchanged; locations
  America/Europe/Asia-Oceania (stock-dependent); backup/restore stays
  conditional ("where your current computer and plan support the action").
  The 12-agent roster (Codex, Claude Code, OpenCode, Cursor, Antigravity,
  Grok Build, Command Code, Pi, Devin, Kimi Code, GitHub Copilot, Factory
  Droid) is unchanged from the pm pass.
- **Watch-method gap:** still open. A targeted search found no
  termsquad.com blog/changelog/docs update surface — the only in-window
  items are continued wire-syndication of the Sep 15 launch (no new
  product signal). The "no new announcement" call still covers the open web
  only.

## WSO2 Agent Manager (C10) — reception broadens; still no hands-on developers

- **INFERRED (third-party, Sep 17–18):** reception is no longer thin-wire
  only. [badsignal.ai](https://badsignal.ai/stories/wso2-agent-manager-ga)
  published a substantive editorial piece (dual company primaries — WSO2
  newsroom + Sep 15 GlobeNewswire wire — flagged as company claims; beta
  June 2026, GA adds per-agent/per-environment identity, MCP-level
  governance, sandboxed runtime); [techweez](https://techweez.com/2026/09/17/wso2-agent-manager/)
  and [techgig](https://techgig.com/news/ai/wso2-launches-open-source-agent-manager-for-ai-governance/134337159)
  add product-level detail (40+ built-in policies — PII masking, rate
  limiting — across agent/MCP/LLM layers; Kubernetes-native sandboxed
  runtime; OpenTelemetry tracing; verifiable agent identity with token
  exchange and revocation). Still **no hands-on independent developer
  reaction found**. Next milestone unchanged: Sep 29 webinar.

## Baseten/Blaxel (C11) — nothing shipped

- **VERIFIED (GitHub API,
  [`blaxel-ai/sandbox`](https://github.com/blaxel-ai/sandbox) releases):**
  no new tagged release after v0.2.59 (Sep 18); `main`/`develop` moving
  tags republished (develop, Sep 19). Watch stays open.

## OpenAI Agents API (C9) — nine partners, unchanged

- **INFERRED (third-party roundups, corroborating):** partner roster still
  Blaxel, Cloudflare, Daytona, DigitalOcean, E2B, Modal, Oracle, Runloop,
  Vercel; beta terms unchanged. New color, not corpus fact:
  [cellcog.ai](https://cellcog.ai/blog/openai-agents-api/) notes OpenAI's
  launch quotes eight design partners, incl. a Ciridae CTO quote (eval
  score 0.71→0.85, 4x latency reduction on subagent flows) — vendor-chosen
  quotes, no independent adoption figures. Stays open.

## OpenRouter `openrouter:shell` — vendor-confirmed beta; ecosystem uptake begins

- **VERIFIED (OpenRouter's own
  [docs](http://openrouter.ai/docs/guides/features/server-tools/shell) and
  [blog post](https://github.com/openrouterteam/docs/blob/HEAD/content/blog/2026-09-08-shell-tool.md)
  dated 2026-09-08):** the `openrouter:shell` server tool is in beta on the
  Responses and Messages APIs; commands run "server-side in an isolated
  Linux container," each in its own invocation; files persist per container
  id across requests; on the Responses API, OpenAI's native `shell` tool
  shape routes to the OpenRouter sandbox automatically on non-OpenAI
  models. **Vendor-stated pricing** (docs Pricing section): $0.0001/s
  metered sandbox time (clock starts when a request first runs a sandbox
  command, stops when the response completes); 30-second minimum on
  new/sleeping containers; idle containers not billed. Files persist per
  container id across requests when pinned via `container_reference`
  (the default `container_auto` is ephemeral — sleeps after 5 min idle).
- **INFERRED (third-party, this window):** ecosystem uptake —
  [simonw's llm-openrouter](https://github.com/simonw/simonw/blob/HEAD/repos/simonw/llm-openrouter/README.md)
  now documents a `Shell` option routing to hosted execution, i.e. the
  ephemeral-exec primitive is being composed into third-party harnesses.
  The per-second ephemeral-exec floor thesis (C2) stands.

## GitHub Copilot JetBrains sandbox controls — editorial broadening, one docs-corroboration gap

- **INFERRED (third-party, Sep 12–16):**
  [devops.com](https://devops.com/github-puts-guardrails-on-copilots-sandbox-inside-jetbrains-ides/),
  [tvgreport](https://tvgreport.com/github-copilot-jetbrains-enterprise-sandbox-controls/),
  [musthave.ai](https://musthave.ai/github-copilot-jetbrains-enterprise-sandbox-controls/),
  and a [pondero.ai](https://pondero.ai/news/2026-09-12-github-copilot-jira-integration-ai-scan-api/)
  roundup restate the Sep 8 vendor changelog (enterprise-managed sandbox
  policies in public preview; managed restrictions take precedence over
  user settings; policy diagnostics). No product change beyond the Sep 8
  announcement.
- **INFERRED (third-party OSS research note,
  [steveash/hitchhikers-guide](https://github.com/steveash/hitchhikers-guide-to-ai-native-engineering/blob/HEAD/source-notes/docs-github-copilot-weekly-releases-sept7-2026.md)):**
  that author flags a corroboration gap — the changelog's managed-sandbox
  claim conflicts with the "Enterprise managed settings reference" page's
  own "Supported keys" table (filed as issue #3334 in their repo). Not
  independently verified; an H16 design run should verify the managed-keys
  list against GitHub's own docs before claiming parity.

## Tencent BrowserSkill — no in-window moves

- No new coverage found in this window beyond the Sep 18 launch reporting
  folded in the consolidation.

## Pricing sweep — no changes

- **INFERRED (third-party,
  [MarkTechPost Aug-27 table](https://www.marktechpost.com/2026/08/27/best-agent-sandboxes-2026-cold-start-pricing-network-policy/),
  still corroborating):** E2B $0.0504/vCPU-hr, Daytona $0.0504/vCPU-hr,
  Modal sandbox ≈$0.0710/vCPU-hr equiv, Vercel $0.128 active-CPU-hr,
  Cloudflare $0.072 active-CPU-hr, Runloop $0.108/CPU-hr, Northflank
  $0.01667/vCPU-hr — all consistent with the Sept-2026 baseline. No
  launches, pricing/tier changes, or partner moves found in-window on the
  tracked set.
- **Names on radar (INFERRED, third-party, one line each — candidates for
  a future deep-scan, not this pass):**
  [OpenComputer](https://opencomputer.dev/guides/e2b-alternatives/) —
  real KVM VMs, $0.24/hr flat, always-on with hibernate/wake
  (persistent-computer adjacent); [Freestyle](https://github.com/vvedantb/eva/blob/HEAD/internal/sandbox-providers-research.md)
  — $0.04032/vCPU-hr; Morph Cloud — MCU-based pricing. The third-party
  research also quotes Blaxel tier pricing (XS 2GB $0.0828/hr …
  M 8GB $0.331/hr; standby snapshot $0.000278/GB/hr) — directional C2
  input only.

## Surveillance result

- Otherwise quiet in this window: no launches, pricing/tier changes, or
  partner moves beyond the above (AgentComputer unchanged — no repo
  activity since the consolidation's check; Daytona, Modal, Runloop,
  Northflank, Vercel, Cloudflare, E2B: no product moves found).

## Implications → backlog notes for this pass

- **C13 — direct-read debt CLOSED; one correction issued.** The owed
  vendor read is done; the D-Bus/OAuth quotes are now vendor text. The
  consolidation's "shipped unlabeled" framing is corrected (the CVEs are
  now named in the notes; the morning read showed none — amendment timing
  is inference, not vendor fact). O13 (trust/transparency doc) can now
  quote the vendor verbatim with the correction.
- **C10 — reception status updated:** "thin" → editorial-broad but still
  no independent hands-on coverage; stays open through the Sep 29 webinar.
- **C1 — watch-method gap still open:** no non-login-gated TermSquad
  update surface found; stays open.
- **H16 — add Docker AI Governance to the vendor set:** centrally managed
  network/filesystem/MCP policies + sign-in enforcement + audit logs
  (paid, contact sales) — the design run should verify against Docker's
  own governance docs alongside GitHub/Vercel/Daytona/Runloop/Upstash.
- **C5 — idle-economics input:** Docker's idle auto-stop and
  consent-default-decline credential binding are concrete reference points
  for the suspend-shape thinking.
