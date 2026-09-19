# Competitor watch — 2026-09-19 (morning pass)

Delta-only update against the 2026-09-19 ~00:30 CDT night-pass baseline
(PR #64, `docs/COMPETITOR_WATCH_2026-09-19.md`). Surveyed 2026-09-19
~04:57 → ~05:30 CDT.

Summary: **five queued items from the research run's delta report are now
fully verified against primary sources** (they arrived after the night
pass's write-up) — and the live corpus is quiet. No in-window launches,
pricing changes, tier changes, partnerships, or incidents across the
tracked set. The pass's real content is verification + corrections: the
five queued items upgrade from INFERRED/third-party to VERIFIED, with two
factual corrections to the queue's claims.

Conventions: **VERIFIED** = read on a vendor's own page, doc, repo, or
security announcement this run (link inline). **INFERRED** = third-party
characterization, labeled as such. "No change detected" is reported
explicitly.

## 1. Docker Sandboxes v0.43.0 (Sep 15) — verified trust-model tightening

- **VERIFIED (Docker's own release notes, [docker/sbx-releases](https://github.com/docker/sbx-releases),
  latest stable; independent press places v0.43.0 on Sep 15, 2026):**
  - "`shareSkills` in `sbxenv.yaml` (experimental feature) has been
    replaced with `skills`, `skills` may be set to `off|readonly|readwrite`."
  - "MCP OAuth client secrets are renamed to
    `mcp:<server>:client_secret` (was `mcp:<server>.client_secret`),
    matching the header-secret naming; a secret stored under the old name
    is no longer read and must be re-set with
    `sbx secret set mcp:<server>:client_secret`."
  - "Environment files can reference `${{ env.projectDir }}` and
    `${{ env.fileDir }}`, the user-level `~/.sbxenv.yaml` can mount each
    project's own directory by declaring `workspace: ${{ env.projectDir }}`..."
- **Implication:** Docker is actively tightening its sandbox trust story —
  read-only skill sharing by default, host-side credential proxying,
  managed MCP governance. The direct competitor is converging on exactly
  the "agent runs without keys inside" model spark-vm advertises, so
  spark-vm's differentiation must rest on **persistence + hosted sign-up**,
  not isolation hygiene alone. (This also independently validates the
  swapd direction: host-side placeholder substitution at the egress proxy
  is the industry move.)

## 2. Docker Sandboxes CVEs CVE-2026-77179 / CVE-2026-79994 — sandbox-escape week

- **VERIFIED (Docker's own security announcements,
  [docs.docker.com/security/security-announcements](https://docs.docker.com/security/security-announcements/)):**
  "Two vulnerabilities in Docker Sandboxes were fixed on September 7 in the
  0.42.0 release." Both are TOCTOU races: CVE-2026-77179 (vendor tag
  [Critical], macOS only, 0.28.0–<0.42.0; CVSS 9.4 per third-party trackers,
  not vendor-stated) — "the virtio-fs host server on macOS
  followed symlinks when reopening an unlinked file from a stored path. A
  malicious guest could replace a parent directory with a symlink, escape
  the shared workspace, and read or modify arbitrary host files as the VMM
  user, potentially leading to code execution on the host"; CVE-2026-79994
  (High, CVSS 8.7 per third-party trackers, not vendor-stated, 0.37.0–<0.42.0) — "the guest-to-host Unix domain socket
  relay checked that a socket path was inside an authorized workspace but
  reconnected using the path name." No exploitation is mentioned in the
  vendor announcement. Public disclosure Sep 15 (press date; the announcement
  itself is undated in the fetched copy). Caveat (THIRD-PARTY: one secondary
  outlet's disclosure-timeline analysis notes Docker initially mis-listed
  the fix version for CVE-2026-79994 as 0.41.0 and corrected it to 0.42.0) —
  re-check version numbers in any derivative content.
- **CORRECTION to the queue:** the queue tied these to Docker Desktop /
  "guest→macOS-host file access via shared folder" generally — **no
  evidence ties either CVE to Docker Desktop; both are Docker Sandboxes
  only.**
- **Implication:** the shared-workspace boundary is the entire trust story
  of a persistent-VM-for-agents product, and this is the week's
  highest-profile proof that "a microVM + mounted host folder" is a fragile
  model. spark-vm's full-VM-without-host-folder-sharing design can be
  positioned as architecturally safer — good raw material for a
  trust/transparency doc (candidate backlog item).

## 3. GitHub Copilot enterprise-managed sandbox controls for JetBrains IDEs — corrected date

- **VERIFIED (GitHub Changelog, primary,
  [changelog entry](https://github.blog/changelog/2026-09-08-enterprise-managed-sandbox-in-copilot-for-jetbrains/),
  public preview):** "Enterprise administrators can now centrally configure
  sandbox behavior for GitHub Copilot in JetBrains IDEs. Managed policies
  can control sandbox enablement, filesystem and network access, proxy
  settings, developer-tool access, macOS Keychain access, and more."
  "Managed restrictions take precedence over user settings. Copilot locks
  affected controls in the IDE and identifies settings managed by your
  organization, helping administrators enforce consistent development
  environment boundaries." Plus enterprise policy diagnostics to verify
  policies are detected and enforced on devices.
- **CORRECTION to the queue:** the queue dated this Sep 16 — **the
  changelog entry is Sep 8, 2026.**
- **Implication:** GitHub is turning every Copilot install into a
  centrally-governed execution environment — the market is normalizing
  "governed sandbox" as table stakes. The hosted-product pitch needs an
  org-policy layer (per-agent filesystem/network rules, audit) to compete
  with enterprise expectations, not just solo-developer isolation
  (candidate backlog item).

## 4. OpenRouter `openrouter:shell` server tool (beta)

- **VERIFIED (OpenRouter docs, primary,
  [server-tools/shell](https://openrouter.ai/docs/guides/features/server-tools/shell)):**
  "The `openrouter:shell` server tool gives a model a hosted shell: a
  sandbox-backed clone of OpenAI's hosted `shell` tool that works with any
  model." "OpenRouter executes the commands in order, each in its own
  invocation, inside a sandboxed container." Tool-table listing:
  "`openrouter:shell` | Run commands in a hosted, sandboxed shell
  (Responses and Messages APIs)". On the Responses API, OpenAI's native
  `shell` tool shape is automatically routed to OpenRouter's sandbox for
  non-OpenAI models; no client-side execution mode. (Docs window ~Sep 8–10;
  ephemeral-sandbox pricing $0.0001/active-second per third-party roundup —
  THIRD-PARTY.)
- **Implication:** OpenRouter is commoditizing ephemeral hosted sandboxes as
  an API primitive. spark-vm's moat is the opposite direction — persistent,
  stateful VMs with sign-up — so positioning should lean hard into
  persistence and long-lived agent workflows, not compete on ephemeral
  exec. Relevant to the H3 pricing thinking: per-second ephemeral exec is
  the floor, per-computer persistence is the premium.

## 5. Tencent open-sources BrowserSkill — isolated Agent Window

- **VERIFIED (primary repo,
  [github.com/tencent/browserskill](https://github.com/tencent/browserskill),
  README + PRIVACY.md):** "**BrowserSkill** connects Cursor, Claude Code,
  Codex, OpenClaw, CodeBuddy, WorkBuddy, Pi, Hermes Agent, and other
  shell-capable AI agents to your already logged-in browser." "**Keep
  working uninterrupted**: browser tasks run in a separate, visible Agent
  Window, so you can keep using your own browser." Rust `bsk` CLI/daemon +
  Chrome/Edge extension; agents reuse real login state without separate
  test accounts; the agent may only borrow a user's open tab with explicit
  per-tab consent and must return it; human-in-the-loop handoff handles
  captchas/logins. (Open-sourced June 2026 per third-party review; recent
  coverage via itsfoss Local AI Weekly, Sep 18.)
- **Implication:** real-authenticated-browser automation is now a
  mainstream agent capability, not a hack. For the hosted product,
  "agent window"-style isolated-but-logged-in browsing is a feature users
  will expect on spark-vm, and the borrow/return consent model is a good
  pattern to borrow for anything spark-vm does with user credentials.

## 6. In-window surveillance — quiet window, explicitly checked

Nothing new since 2026-09-19 ~00:30 CDT across the tracked set. Each of
the following was searched individually this run (all INFERRED from
search, reported as absence):
TermSquad (no pricing/launch change; last news remains the Sep 15
always-on launch); AgentComputer/getcompanion-ai (no releases; repos ~
150 days quiet); Fly.io Sprites (no pricing/tier news); Northflank;
E2B; Daytona (latest remains the Sep 2 Series A); Vercel; Cloudflare
(no new sandbox news; Cursor-on-Sandboxes remains Sep 2); Modal;
Runloop; Microsandbox; Blaxel/Baseten (nothing since the Sep 10
acquisition); OpenAI (Agents API beta remains Sep 10, same 9 partner
sandbox list: Blaxel, Cloudflare, Daytona, DigitalOcean, E2B, Modal,
Oracle, Runloop, Vercel); OpenRouter (Stripe story remains Aug 19);
GitHub Copilot (nothing new in window); Tencent (only the Sep 18
hackathon article); WSO2 (nothing new in window).

Out-of-window context (not deltas, not new to the corpus): "Plugin4Shell"
0-click RCE reported Sep 17 (Air security startup; Claude Code and Codex
patched, Gemini CLI deprecated, Copilot unpatched — The Register,
THIRD-PARTY) — agent-ecosystem security signal worth a mention in any
trust doc, but pre-window and possibly already tracked by an earlier pass.

## 7. Corrections log (this pass)

- Queue's "Docker Desktop" framing of the Sandboxes CVEs — retracted;
  Sandboxes-only.
- Queue's Sep 16 date for Copilot JetBrains sandbox controls — corrected
  to Sep 8 (GitHub Changelog).
- Queue's "2026-09-15 Docker Sandboxes release notes" — confirmed (press
  places v0.43.0 on Sep 15).

## 8. Watch items for the next pass

- The five items above are still **unconsolidated**: PR #64's night-pass
  doc folded nothing into `docs/COMPETITOR_ANALYSIS.md`; PR #54 (rebased
  onto main this run, head 31d5144) carries the evening-pass
  consolidation. Next consolidation pass should fold both #54 and this
  morning pass into the baseline doc.
- WSO2 webinar Sep 29 (C10) — first real reception signal.
- TermSquad's unadvertised Herdr version (herdr#3415 exposure hinges on it).
- TermSquad's x.com/trytermsquad update channel is login-gated (watch-
  method gap noted in the night pass) — find a non-gated update surface.
- Docker's CVE disclosure-timeline pattern (mis-listed fix version,
  corrected) — verify version numbers against vendor pages only in any
  trust/transparency derivative.
- The corpus still has no declared left edge / reach-back policy (night-
  pass follow-up) — declare one or set a deep-scan cadence.
