# Competitor watch — 2026-09-20

Delta-only update against the 2026-09-19 baseline (consolidated in
`docs/COMPETITOR_ANALYSIS.md`, 2026-09-19 pass; latest watch doc
`docs/archive/competitor-watch/COMPETITOR_WATCH_2026-09-19.md`). Surveyed
2026-09-20 ~08:00 → ~08:45 CDT.

Summary: the four priority-1 items queued from the 2026-09-19 night pass
are all verified into the corpus — **Docker Sandboxes 0.43.0 (Sep 15)
release notes**, the two Docker sandbox CVEs, **GitHub Copilot
enterprise-managed sandbox policies for JetBrains**, **OpenRouter
`openrouter:shell`**, and **Tencent BrowserSkill**. Two date corrections
along the way (see §3, §4, §5). Across the tracked set — TermSquad,
AgentComputer, Fly.io Sprites, Northflank, E2B, Daytona, Modal, Vercel
Sandbox, Cloudflare Sandbox, Runloop, Blaxel/Baseten, Microsandbox, WSO2
Agent Manager, OpenAI Agents API sandbox partners, FastGPT, Cloudflare ×
Cursor — **no new launches, pricing changes, or partner moves** since the
baseline; third-party comparison tables corroborate unchanged baseline
rates. The watch record is quiet otherwise.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo this
run (link inline). **THIRD-PARTY** = reported by press/third-party sources.
**INFERRED** = my characterization, labeled as such.

## 1. Docker Sandboxes 0.43.0 (Sep 15) — VERIFIED

**VERIFIED** ([Docker Sandboxes release notes](https://docs.docker.com/ai/sandboxes/release-notes/), 2026-09-15 section, `v0.43.0`):

- **Breaking:** `shareSkills` in `sbxenv.yaml` (experimental) replaced with
  `skills`; `skills` may be `off|readonly|readwrite` (the tri-state first
  flagged in the corpus's evening pass, now the stable config key).
- **Breaking:** MCP OAuth client secrets renamed to
  `mcp:<server>:client_secret` (was `mcp:<server>.client_secret`), matching
  header-secret naming; old-name secrets are no longer read and must be
  re-set via `sbx secret set`.
- Environment files can reference `${{ env.projectDir }}` and
  `${{ env.fileDir }}`; user-level `~/.sbxenv.yaml` can mount each project's
  own directory via `workspace: ${{ env.projectDir }}`; relative workspace
  paths resolve against the declaring file; every `sbx env` subcommand
  accepts `--name` to override the sandbox name.
- `sbx env run/create/rm` now detect name conflicts with sandboxes created
  outside `sbx env` and give guidance instead of mis-managing them.
- Formerly built-in agents moved to public kits (kiro, copilot, droid) can
  be launched by name again — `sbx run kiro` resolves the pinned replacement
  kit, stored credentials work without extra approval steps.
- `sbx run --provider` accepts hosted models.dev providers (via llmman);
  `--overflow-provider`/`--overflow-model` pairs a local model with a hosted
  one for oversized requests; `--provider` works with codex for providers
  lacking the Responses API.
- Add/update/list/remove sandbox skills directly from Git repositories with
  `sbx skills`; read-only `sbx` commands accept `--json`; local-sandbox
  clipboard can copy to the host clipboard.

**Implication:** Docker keeps converging sandbox skills + MCP secrets into
first-class config surface — the same governance plane as its paid Docker AI
Governance offering. For spark-vm's hosted signup story, the axis to watch
is not the config surface itself but the *paid governance tier* — centrally
managed network/filesystem/MCP policies + sign-in enforcement + audit logs.
Backlog H16 (hosted org-policy layer) already carries this; no new item.

## 2. Docker Sandboxes CVEs CVE-2026-77179 / CVE-2026-79994 — VERIFIED

**VERIFIED** (Docker's own release notes, 2026-09-07 `v0.42.0` section, plus
THIRD-PARTY security coverage for CVE details):

- **CVE-2026-77179 — Critical, CVSS 9.4.** The virtio-fs host server
  (macOS side of Mac↔VM file sharing) followed symlinks when reopening an
  unlinked file from a stored path. A guest could replace a parent directory
  with a symlink after the path was authorized, escape the shared workspace,
  and read/modify arbitrary host files as the VMM user — "potentially
  leading to code execution on the host" (Docker's words). Affected:
  0.28.0 → before 0.42.0, **macOS only**.
- **CVE-2026-79994 — High, CVSS 8.7.** Time-of-check-to-time-of-use race in
  the relay that lets a sandbox connect to Unix domain sockets inside its
  authorized workspace: the relay validated the socket path, then reconnected
  by path name; a guest swapping a directory for a symlink between the two
  steps could make the host connect to any AF_UNIX socket outside the
  workspace. Affected: 0.37.0 → before 0.42.0 (no platform stated).
- Fixed in **0.42.0, released 2026-09-07**; disclosed ~Sep 15–17 (security
  press coverage dated Sep 17). Docker reports **no known exploitation**;
  neither CVE is in CISA's KEV catalog (Sep 16 version).

**Implication:** this is the sandbox-category risk signal the night pass
queued it as — both flaws are the same class (path-validation TOCTOU at the
host↔guest boundary). spark-vm's analogous attack surface is any host-mount
or host-reachable socket path (browser-driver workspace mounts, CUA shared
folders, proxy allowlist paths). Suggested backlog item: **R16 — audit
spark-vm host↔guest file-sharing paths for TOCTOU symlink races
(CVE-2026-77179/79994 class)**, routed to a security turn. The broader
thesis holds: customers who fear their agent's execution layer keep the
sandbox category on probation; spark-vm's consent/allowlist/audit story is
the load-bearing answer.

## 3. GitHub Copilot — enterprise-managed sandbox policies for JetBrains — VERIFIED

**VERIFIED** ([GitHub Changelog](https://github.blog/changelog/2026-09-08-enterprise-managed-sandbox-in-copilot-for-jetbrains/); date
correction: the vendor announcement is dated **2026-09-08**, not Sep 16 —
Sep 16 was third-party coverage):

- Public preview: enterprise administrators can centrally configure sandbox
  behavior for GitHub Copilot in JetBrains IDEs — sandbox enablement,
  filesystem and network access, proxy settings, developer-tool access,
  macOS Keychain access. Managed restrictions take precedence over user
  settings; affected controls show as "(managed)" in the IDE.
- Ships alongside enterprise policy diagnostics (verify policies actually
  reach developer machines) and a terminal-Copilot-CLI ↔ JetBrains
  connection.

**Implication:** governance convergence — GitHub is moving sandbox control
out of MDM/general device management and into the agent product's own
managed-settings plane (same mechanism it introduced in August for plugins,
MCP allowlists, telemetry). This is the enterprise shape spark-vm hosted
must eventually match; backlog H16 (hosted org-policy layer) already
carries it. One new dimension for H16's design: GitHub's **policy
diagnostics** (attestation that a restriction actually landed on the
machine) — a gap item worth noting when H16 is worked.

## 4. OpenRouter `openrouter:shell` — VERIFIED

**VERIFIED** ([OpenRouter's own docs blog](https://github.com/openrouterteam/docs/blob/HEAD/content/blog/2026-09-08-shell-tool.md),
post dated 2026-09-08; date correction: announced **Sep 8** by the vendor —
the Sep 18 signal was third-party coverage):

- Server tool `openrouter:shell` on the Responses and Messages APIs gives
  **any model a hosted sandboxed shell**: OpenRouter runs the model's
  commands in an isolated Linux container, returns stdout/stderr/exit or
  timeout, keeps produced files, works with the Files API. Beta. On the
  Responses API, OpenAI's native `shell` tool shape routes to OpenRouter's
  sandbox on non-OpenAI models automatically.
- Explicitly a sandbox-backed clone of OpenAI's hosted `shell` tool —
  execution-side only, no client-side mode.

**Implication:** the task-scoped segment is commoditizing *execution for any
model* — the routing layer (OpenRouter) now owns the sandbox, not the model
provider. This stays on the task-scoped side of the corpus's scope split and
doesn't contest persistence; it does put price pressure on the "execution
API" abstraction spark-vm's hosted offering should not try to own. No gap
item — record only.

## 5. Tencent BrowserSkill — verified against upstream repo, one correction

- **Upstream repo exists and is open source:**
  [github.com/tencent/browserskill](https://github.com/tencent/browserskill/blob/HEAD/README.md) —
  "Let AI agents use your browser without interrupting your work." A `bsk`
  CLI + Chromium extension connects Cursor, Claude Code, Codex, OpenClaw and
  others to the user's already-logged-in browser; agent work runs in a
  separate visible **Agent Window**; tabs can be borrowed explicitly and
  returned; human handoff for captchas/logins. MIT license claim appears in
  a third-party fork's privacy doc, not read on the upstream LICENSE file
  itself — license attribution is **THIRD-PARTY, unconfirmed**.
- **Date correction:** THIRD-PARTY video coverage (~early September) states
  BrowserSkill was open-sourced in **June 2026** — the Sep 18 signal was
  coverage/adoption, not the initial release. Corpus entry stands, date
  fixed.
- Noted by third-party coverage as security-interesting: a single
  extension permission grants access to every logged-in site; the borrow
  rule is honor-system; actions look like the user's clicks (prompt
  injection undetectable by security tooling).

**Implication:** the "real-browser-with-real-login" pattern is converging
across projects (Tencent's Agent Window, Cloudflare×Cursor's customer-owned
execution). For spark-vm's browser-driver component the differentiator
remains the headless/server-side trust model vs "borrow my browser."
Suggested backlog item: **R17 — evaluate BrowserSkill's Agent Window +
tab-borrowing pattern vs spark-vm browser-driver's headless model** (one
strategy working note, no build commitment).

## 6. The tracked set — quiet

No change detected since the baseline (2026-09-19 ~17:54 CDT):

- **TermSquad** — pricing $9/$19/$29/$49 unchanged on the pricing page
  (no refetch needed for a delta pass; no launch coverage found).
- **AgentComputer, Fly.io Sprites, Northflank, E2B, Daytona, Modal, Vercel
  Sandbox, Cloudflare Sandbox, Runloop, Baseten/Blaxel, Microsandbox** — no
  launches, pricing changes, or version moves found in this pass.
  Third-party comparison tables (marktechpost, vvedantb's provider research)
  corroborate the baseline rate card unchanged (Daytona $0.0504/vCPU-hr,
  E2B same normalized, Modal sandbox tier ~3x standard, Vercel $0.128
  active-CPU, Cloudflare $0.072, Northflank $0.01667, Runloop $0.108).
- **WSO2 Agent Manager** — nothing new; Sep 29 webinar still the next
  milestone (C10 stays open).
- **OpenAI Agents API sandbox partners** — still nine, unchanged (C9).
- **FastGPT** — no follow-up beyond the v4.16.0 E2B deprecation noted last
  pass.
- **Cloudflare × Cursor** — no new moves.

Gap items filed from this pass: **R16** (Docker-CVE-class TOCTOU audit of
host↔guest file-sharing paths) and **R17** (BrowserSkill vs browser-driver
evaluation note). H16 already carries the GitHub-managed-sandbox and Docker
AI Governance thread; add the policy-diagnostics dimension when H16 is
worked.

---

*Corpus note:* per the reach-back policy, this pass adds no pre-window
items beyond the two date corrections above (vendor-date verification of
items the night pass had only as third-party reports).
