# Research: browser control models — BrowserSkill vs spark-vm browser-driver

Evaluation note comparing Tencent BrowserSkill's **Agent Window + tab-borrowing**
pattern against spark-vm's `browser-driver` headless/server-side trust model
(spec: `browser-driver/SPEC.md`, reviewed in `browser-driver/REVIEW.md`).

**No build commitment.** These findings inform H17 (browser-driver
implementation, GitHub #132), the live-machine-control ticket (#47), and the
borrow/consent UX — none of them commit spark-vm to a tab-borrowing
implementation.

**Correction to the existing corpus:** `docs/COMPETITOR_ANALYSIS.md`
(describing this item as R17) calls tab-borrowing "per-tab borrow/return
consent" and the earlier watch note characterized it as an honor-system borrow
rule. The primary-source read below shows the borrow gate is **enforced and
fail-closed**, not honor-system: browser-side settings are authoritative over
CLI flags, and the maintainers fixed three fail-open paths in Sep 2026
(PRs #3/#5/#16).

## 1. The two models, side by side

| Dimension | BrowserSkill (Tencent) | spark-vm browser-driver (spec) |
|---|---|---|
| Where the browser runs | On the **user's own machine**, inside their real logged-in Chromium/Edge profile | On **spark-vm** (hosted) or the user's self-hosted box — a server-side browser under service account `bdrive` |
| Whose login state it rides | The user's real profile: cookies, extensions, saved sessions — "no separate test accounts, no credential handoff" | A dedicated `bdrive` profile at `/home/bdrive/profile/` — deliberately NOT the user's everyday profile |
| Agent control surface | Rust `bsk` CLI/daemon + Chrome/Edge extension; agent talks to the CLI over shell, never to the browser directly; extension drives tabs via CDP (`debugger` permission), DOM snapshots + `@e` refs | Fixed `bdrive` action protocol (SPEC §5) + on-box agent loop `obox` (observe→decide→act) |
| Visibility to the human | **Separate, visible Agent Window** — the user watches the agent work in a window of its own while keeping their own windows | Headless service; the orchestrator gets terminal reports, not a live window (live machine control ticket #47 may add desktop streaming later) |
| Credential story | Reuses the user's existing logged-in sessions; extension "does not read or transmit cookies, browsing history, bookmarks, downloads, saved passwords, or autofill data" (PRIVACY.md); skill rules forbid extracting tokens/secrets from pages | Nobody sees real values anywhere in the stack: the agent types `hsurr:` placeholders; the swap proxy substitutes values at egress for allowlisted hosts |
| Concurrency with the human | Explicit borrow/return: the agent must borrow a user tab explicitly, return it when done, and "leave the rest of your browser alone" | No human on the box's browser at all — tabs are agent-only (SPEC §3: one browser process, one persistent context, tabs as sessions) |
| Trust anchor | The user's own machine: extension talks only to a local daemon ("communicates exclusively with a local daemon running on your own computer"; no remote servers, no telemetry) | The box: orchestrator submits briefs; driver executes a fixed action set; swap proxy enforces egress; nspawn jail enforces process isolation |

## 2. BrowserSkill's borrow/return consent model — the details worth stealing

Primary sources: README + SKILL.md + PRIVACY.md + PRs, all at
`https://github.com/Tencent/BrowserSkill` (Tencent org; **MIT license**,
verified by reading the LICENSE file — this settles the R17 attribution
note: standard MIT text, no special terms).

- **The rule is enforced, not honor-system.** Extension popup holds two
  automation settings (both on by default): "Confirm before borrowing tabs"
  and "Allow requests for human help". Since v0.3.0, **browser-side saved
  settings are authoritative** — CLI flags like `--unattended` or
  `tab borrow --no-confirm` cannot override them ("a command-line flag is a
  terrible place for a consent decision"). Opting into unattended mode is a
  deliberate browser-side choice by the user.
- **Fail-closed by design, with the failures on record.** Borrows auto-*deny*
  on confirmation timeout (raised 5s → 60s in Sep 2026 because the Agent
  Window stole focus and users missed the overlay). The maintainers found and
  fixed three fail-open paths: PR #16 (borrow confirmation overlay auto-
  *allowed* on countdown; background coordinator returned `true` on
  missing/timeout/malformed replies — fixed so a user who did nothing could
  not lose a tab), PR #5 (transient `chrome.tabs.get` error returned
  approve — fixed to show the confirmation UI with a generic title), PR #3
  (borrowed tab returned into *another session's* Agent Window — a
  cross-session sandbox break — now excluded). This is the fail-open taxonomy
  to avoid if spark-vm ever builds a borrow gate.
- **Session-scoped isolation.** Sessions own tabs; borrowed tabs are tracked
  per session with auto-return on `session stop`; per-session Agent Windows
  are isolated from each other (`enforceAgentWindow` in write tools).
- **Human-in-the-loop for the hard parts.** `browser_assist request-help` for
  captcha/login/OTP/payment/consent — "the agent can ask you to take over and
  then continue afterwards." Mirrors spark-vm's `obox` `need_info` state, but
  surfaces it in the visible window instead of a report.
- **Remote mode exists** (agent on a server paired with the user's local
  browser over authenticated WSS), but remote upload/download is unsupported
  in this version — a noted limitation.
- **Status:** actively developed (borrow-confirmation UX commits Sep 2,
  2026; PRIVACY.md updated Sep 15, 2026; README ~mid-Sep 2026). ~1,969 stars
  early July 2026 (repo-sourced); current exact count unverified. Release
  number unverified.

## 3. Where each model wins

**BrowserSkill wins on:**
- **Zero credential logistics.** The agent inherits the user's real sessions.
  For a local-first user driving their own box, this deletes an entire class
  of work (credential install, placeholder swaps, session-cookie plumbing).
- **Ambient trust through visibility.** The user literally watches the agent
  in its own window. Surprising behavior is caught by eyeballs, not audit
  logs — cheaper for casual users.
- **No harness lock-in.** Any shell-capable agent drives `bsk`; Cursor,
  Claude Code, Codex, OpenClaw, and others are listed.

**spark-vm browser-driver wins on:**
- **True remote operation.** spark-vm's browser runs on the box, reachable
  over the tailnet; the user doesn't need a browser open locally, and the
  agent works when the user's laptop is asleep. BrowserSkill's model assumes
  the user's machine is on with the browser running.
- **Provable isolation.** Enforcement split (fixed action protocol, nftables
  uid egress, swap proxy, nspawn jail) vs. BrowserSkill's window-level
  isolation on the user's own profile, where a confused-deputy extension bug
  (see PR #3) touches the user's real sessions.
- **Secret compartmentalization.** The `hsurr:` placeholder model means the
  browsing stack never holds a real value; BrowserSkill never exposes
  secrets to the agent either, but it *does* run inside the profile that
  holds them.
- **Multi-tenant story.** spark-vm's model extends to hosted tenants (#47,
  H11); BrowserSkill is single-user-local by design.

## 4. Implications for spark-vm (H17 / #47 / #132)

1. **Borrow-gate as the trust pattern for #47's live machine control.**
   BrowserSkill's enforced, fail-closed, browser-side-authoritative borrow
   consent is directly reusable as the confirmation pattern for anything the
   hosted control plane lets an operator (or agent) touch on a live box:
   the gate must live where the CLI cannot override it, default to deny on
   timeout, and treat every fail-open as a bug. PRs #3/#5/#16 are the
   anti-patterns to test against.
2. **Visible-window principle for the H17 UX.** spark-vm's driver is
   headless-by-spec; when #47 adds desktop streaming, the BrowserSkill
   precedent says the agent's browser should be a *visibly distinct
   surface* (dedicated window/context), not just another tab — casual users
   trust what they can see.
3. **"Return borrowed tabs immediately" as session-hygiene policy.**
   BrowserSkill's per-session tab tracking with auto-return on session stop
   is a good template for `bdrive`'s session model (SPEC §3) and for
   `obox`'s `need_info` parking: state that the agent borrows should be
   released, not leaked, when a job parks or dies.
4. **Do not adopt the ride-the-user's-profile model.** It trades away
   spark-vm's core differentiator (provable server-side isolation and the
   placeholder credential story) for convenience. The borrow/consent
   *mechanics* are stealable; the *trust topology* is not.
5. **License note:** MIT upstream — if spark-vm ever wants to borrow (pun
   intended) code or protocol ideas, the license permits it with the usual
   attribution. This supersedes the R17 note's "MIT attribution is
   THIRD-PARTY (upstream LICENSE not read)": upstream LICENSE **has now
   been read** — standard MIT text.

## 5. Open questions (unverified or out of scope)

- Exact current star count and latest release version (crawl gap; not needed
  for the evaluation).
- Named individual maintainers (org-owned by Tencent; no individuals
  verified).
- Whether BrowserSkill's remote WSS pairing would survive spark-vm's swap
  proxy egress rules — interesting only if a remote-mode integration were
  ever considered (out of scope per §4.4).

---
*Research turn: strategy/research, 2026-09-20. Upstream sources read directly
(README, LICENSE, SKILL.md, PRIVACY.md, PRs #3/#5/#16) at
https://github.com/Tencent/BrowserSkill. spark-vm claims code-verified
against repo at commit 13f258e (SPEC.md, REVIEW.md).*
