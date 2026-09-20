# Competitor watch — 2026-09-20

Delta-only update against the 2026-09-19 **evening** pass
(`docs/COMPETITOR_WATCH_2026-09-19_EVENING.md`, live in `docs/`; survey
window ~18:00 → ~23:00 CDT). This pass surveyed 2026-09-20 ~08:00 →
~08:50 CDT.

Summary: this pass **re-verified** the five items the 2026-09-19 passes had
already consolidated into `docs/COMPETITOR_ANALYSIS.md` against vendor
primaries (direct reads this run). Beyond re-verification it adds: (1)
itemized config/management notes from the 0.43.0 (Sep 15) and 0.42.0
(Sep 7) sections that the corpus had not recorded (see §1); (2) CVE-record detail extensions (CVSS, affected ranges, disclosure
timing, KEV status — §2); (3) a hardened BrowserSkill license attribution
(THIRD-PARTY/unconfirmed — §5); and (4) a **restored** corroboration caveat
on the GitHub Copilot item that the evening pass carried and this doc's
predecessor draft dropped (§3). Three date attestations (Sep 8 Copilot
changelog, Sep 8 OpenRouter blog, June-2026 BrowserSkill open-sourcing with
Sep-18 coverage) confirm the corpus's dates; they correct nothing. No new
launches, pricing changes, or partner moves across the tracked set.
Proposed from this pass: **R16** (security-turn audit extending the trust
doc's owned-risk tracking) and **R17** (one strategy evaluation note).

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo this
run (link inline). **THIRD-PARTY** = reported by press/third-party sources.
**INFERRED** = my characterization, labeled as such.

## 1. Docker Sandboxes 0.43.0 (Sep 15) — re-verified + new itemized notes

**VERIFIED** ([Docker Sandboxes release notes](https://docs.docker.com/ai/sandboxes/release-notes/), 2026-09-15 section, read directly this
pass). The 0.43.0 items the corpus already consolidated (skills tri-state
— first flagged in the **2026-09-19 morning pass**, consolidated in
`COMPETITOR_ANALYSIS.md:446-448`; MCP OAuth secret rename; sbxenv.yaml
interpolation) re-verify against the vendor page. Newly itemized here —
not previously recorded in the corpus:

- Formerly built-in agents that moved to public kits (kiro, copilot, droid)
  can be launched by name again — `sbx run kiro` resolves the pinned
  replacement kit, and its stored credentials work without extra approval
  steps.
- `sbx run --provider` accepts hosted models.dev providers (served through
  the bundled llmman); `--overflow-provider`/`--overflow-model` pairs a
  local model with a hosted one for oversized requests; `--provider` now
  works with codex for providers lacking the Responses API; codex sandboxes
  no longer spend seconds retrying WebSocket connections to the local model
  server.
- Add, update, list, and remove sandbox skills directly from Git
  repositories with `sbx skills`.
- `sbx env run/create/rm` detect name conflicts with sandboxes created
  outside `sbx env` and give guidance instead of mis-managing them; every
  `sbx env` subcommand accepts `--name`.

Also on the same vendor page, from the **0.42.0 (Sep 7)** section — not
previously itemized in the corpus, and misdated as 0.43.0 in this doc's
first draft (verified against the live page this pass):

- Add, update, list, and remove sandbox skills directly from Git
  repositories with `sbx skills`.
- Read-only `sbx` commands (`secret ls`, `version`, `mcp ls`, `skills ls`,
  `policy inspect`, kit verification) accept `--json`.
- Clipboard commands inside local sandboxes can copy to the host
  clipboard.

**Implication:** Docker keeps converging sandbox skills + MCP secrets into
first-class config surface — the same governance plane as its paid Docker AI
Governance offering. For spark-vm's hosted signup story, the axis to watch
is not the config surface itself but the *governance tier* — centrally
managed network/filesystem/MCP policies + sign-in enforcement + audit logs
(Docker AI Governance offering).
Backlog H16 (hosted org-policy layer) already carries this; no new item.

## 2. Docker Sandboxes CVEs CVE-2026-77179 / CVE-2026-79994 — CVE-record extension

The corpus already consolidated these (`COMPETITOR_ANALYSIS.md:417-445`,
incl. the evening pass's vendor-direct read of the amended 0.42.0 notes).
This pass extends with CVE-record and disclosure-timing details:

- **CVE-2026-77179 — Critical (vendor severity label).** CVSS 9.4 per
  third-party trackers, not vendor-stated. virtio-fs host-server symlink
  race (macOS). Affected: 0.28.0 → before 0.42.0, **macOS only**.
- **CVE-2026-79994 — High (vendor severity label).** CVSS 8.7 per
  third-party trackers, not vendor-stated. guest-to-host Unix-domain-socket
  relay TOCTOU race. Affected: 0.37.0 → before 0.42.0 (no platform stated).
- Fixed in **0.42.0, released 2026-09-07**; CVE records published ~Sep 15;
  security-press disclosure coverage dated Sep 17 (**THIRD-PARTY**).
- No exploitation mentioned in the vendor announcement; neither CVE is in
  the KEV catalog as of the Sep 16, 2026 version (**THIRD-PARTY**, not
  verified against cisa.gov in this pass).

**Implication:** this is the sandbox-category risk signal the 2026-09-19
evening pass carried — both flaws are the same class (path-validation TOCTOU
at the host↔guest boundary). spark-vm has no virtio-fs-class file-sharing
boundary (the canonical doc's implication stands: full VM, no shared host
folders), but `docs/TRUST_TRANSPARENCY.md` §2 already tracks the adjacent
classes as **owned risks** — the D-Bus class and the -79994 relay class —
against the jail's two deliberate host exposures (proxy ports, DNATed +
audited; SSH relay, tailnet only). Proposed backlog item: **R16 — extend
that owned-risk tracking with a concrete path-validation/TOCTOU audit of
the two deliberate exposures plus the `bdrive` jail socket bind-mounts
(`browser-driver/REVIEW.md`)**; routed to a security turn. This is an
extension of the trust doc's tracked risk, not a newly discovered gap.

## 3. GitHub Copilot — enterprise-managed sandbox policies for JetBrains — caveat restored

**VERIFIED** ([GitHub Changelog](https://github.blog/changelog/2026-09-08-enterprise-managed-sandbox-in-copilot-for-jetbrains/), 2026-09-08 entry, read
directly this pass; confirms the corpus's Sep-8 dating): public preview —
enterprise administrators centrally configure sandbox behavior for Copilot
in JetBrains IDEs (sandbox enablement, filesystem/network access, proxy
settings, developer-tool access, macOS Keychain access); managed
restrictions take precedence over user settings ("(managed)" badge).
Ships with enterprise policy diagnostics and a terminal-Copilot-CLI ↔
JetBrains connection. Note: sandbox settings are gated — visible only when
the org enables the `Editor Preview` feature flag or configures a managed
setting.

**Corroboration caveat (restored from the 2026-09-19 evening pass, which
carried it and this pass must not drop):** the changelog's managed-sandbox
claim *conflicts with GitHub's own "Enterprise managed settings reference"
Supported-keys table* (filed as issue #3334 in steveash/hitchhikers-guide,
not independently verified). An H16 design run should verify the
managed-keys list against GitHub's own docs before claiming parity — this
pass makes no parity claim.

**Implication:** governance convergence — GitHub moves sandbox control out
of general MDM and into the agent product's own managed-settings plane.
The enterprise shape spark-vm hosted must eventually match is defined by
H16; this pass adds nothing to H16 beyond the verification the caveat
prescribes.

## 4. OpenRouter `openrouter:shell` — re-verified, date attested

**VERIFIED** ([OpenRouter's own docs blog](https://github.com/openrouterteam/docs/blob/HEAD/content/blog/2026-09-08-shell-tool.md), post dated
2026-09-08, read this pass — confirms the corpus's dating): server tool
`openrouter:shell` on the Responses and Messages APIs gives **any model a
hosted sandboxed shell** — OpenRouter runs commands in an isolated Linux
container, returns stdout/stderr/exit or timeout, keeps produced files,
works with the Files API. Beta. On the Responses API, OpenAI's native
`shell` shape routes to OpenRouter's sandbox on non-OpenAI models. The
"Sep 18" signal was third-party coverage, not the announcement date
(attestation, not correction).

**Implication:** the task-scoped segment commoditizes *execution for any
model* — the routing layer now owns the sandbox, not the model provider.
Stays on the task-scoped side of the scope split; does not contest
persistence; price pressure on the "execution API" abstraction spark-vm's
hosted offering should not try to own. Record only — no gap item.

## 5. Tencent BrowserSkill — license attribution hardened

- **Upstream repo is open source:**
  [github.com/tencent/browserskill](https://github.com/tencent/browserskill/blob/HEAD/README.md) —
  "Let AI agents use your browser without interrupting your work." A `bsk`
  CLI + Chromium extension connects Cursor, Claude Code, Codex, OpenClaw and
  others to the user's already-logged-in browser; agent work runs in a
  separate visible **Agent Window**; tabs are borrowed explicitly and
  returned; human handoff for captchas/logins. Open-sourced June 2026;
  coverage wave Sep 18 (confirms the corpus's dating —
  `COMPETITOR_ANALYSIS.md:519`).
- **Attribution hardening:** the MIT-license claim for the upstream repo is
  **THIRD-PARTY/unconfirmed** — it appears in a third-party fork's privacy
  doc, not on the upstream LICENSE file itself (the corpus's "VERIFIED
  (README + PRIVACY.md)" was looser; the upstream LICENSE file was not
  read in this pass).
- Third-party coverage notes the security trade-off: one extension
  permission grants access to every logged-in site; the borrow rule is
  honor-system; agent actions look like the user's clicks (prompt injection
  undetectable by security tooling).

**Implication:** the "real-browser-with-real-login" pattern converges across
projects (Agent Window, Cloudflare×Cursor's customer-owned execution). For
spark-vm's browser-driver the differentiator remains the headless/server-side
trust model vs "borrow my browser." Proposed backlog item: **R17 — one
strategy working note evaluating BrowserSkill's Agent Window +
tab-borrowing pattern vs spark-vm browser-driver's headless model** (no
build commitment).

## 6. The tracked set — quiet since the evening pass

No change detected since the 2026-09-19 evening pass (~23:00 CDT):

- **TermSquad** — pricing $9/$19/$29/$49 unchanged; no launch coverage.
- **AgentComputer, Fly.io Sprites, Northflank, E2B, Daytona, Modal, Vercel
  Sandbox, Cloudflare Sandbox, Runloop, Baseten/Blaxel, Microsandbox** — no
  launches, pricing changes, or version moves found in this pass.
  Third-party comparison tables corroborate the baseline rate card
  unchanged (Daytona $0.0504/vCPU-hr, E2B same normalized, Modal sandbox
  tier ~3x standard, Vercel $0.128 active-CPU, Cloudflare $0.072,
  Northflank $0.01667, Runloop $0.108).
- **WSO2 Agent Manager** — nothing new; Sep 29 webinar still the next
  milestone (C10 stays open).
- **OpenAI Agents API sandbox partners** — still nine, unchanged (C9).
- **FastGPT** — no follow-up beyond the v4.16.0 E2B deprecation noted last
  pass.
- **Cloudflare × Cursor** — no new moves.

Proposed from this pass: **R16** (security-turn TOCTOU audit extending
`docs/TRUST_TRANSPARENCY.md`'s owned-risk tracking — see §2) and **R17**
(strategy evaluation note — see §5). H16 already carries the
GitHub-managed-sandbox and Docker AI Governance threads; the §3 caveat
prescribes verifying GitHub's managed-keys list before any parity claim.

---

*Corpus note:* per the reach-back policy, this pass adds no pre-window
items; the §4/§5 datings are attestations confirming the canonical
record, not corrections.
