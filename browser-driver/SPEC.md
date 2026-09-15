# spark-vm Browser Driver — SPEC v2

A fixed, narrow browser-driving stack for spark-vm. It replaces ad-hoc
"assistant writes Playwright scripts and runs them over SSH" with two
separate components the orchestrator directs but cannot reprogram:

- **`bdrive`** — the *hands*: a fixed driver service that moves the
  mouse and types keys. No judgment, no browsing logic.
- **On-box agent** — the *brain*: a small agent loop on spark-vm that
  takes a task brief, runs observe→decide→act against `bdrive`, and
  reports back. This is the faithful rebuild of the managed browser
  agent (`browser.spawn_task` / `browser.steer_task`).

This spec is written against a full capability inventory obtained by
interviewing the managed browser agent itself (2026-09-14): its action
vocabulary, observation model, credential-fill mechanics, ask-back
protocol, task lifecycle, safety rails, and trust boundaries. Where
spark-vm differs, the difference is named and justified — never
silently dropped.

## 1. Purpose

- Drive Chromium on spark-vm for browser tasks (logins, forms, scraping,
  checkout flows) without the orchestrator executing arbitrary code and
  without the browsing session's step-by-step detail entering the
  orchestrator's transcripts.
- Never handle a real credential value anywhere in the stack: the agent
  and driver only ever see `hsurr:` placeholders. The swap proxy
  substitutes values on egress.
- Keep a persistent browser profile across tasks (logins stick).

Non-goals: replacing the managed browser agent (it can't reach the
tailnet); general code execution; defeating CAPTCHAs/anti-bot without
permission.

## 2. Trust model

| Principal | Can do | Cannot do |
|---|---|---|
| Orchestrator (assistant, off-box) | Submit task briefs; steer jobs; read terminal reports | Run code in the driver or agent; see credential values; bypass the proxy; see the session's step-by-step detail |
| On-box agent | Run the observe→act loop via `bdrive`; type placeholders | See real values (only `hsurr:` strings); reach the network except via the swap proxy; keep working past a `need_info` without an answer |
| Driver service (`bdrive`) | Drive Chromium per the action protocol (§5) | See real values; run anything but the fixed action set |
| Swap proxy (swapd) | Substitute values for allowlisted hosts; audit | Be reconfigured by the orchestrator or agent (hosts.allow is user-managed) |
| LLM provider (agent's brain) | Receive prompts with page content + placeholders | Receive real credential values (they never exist in prompts) |
| User | Watch sessions; edit allowlist; install secrets via `cred set`; approve purchases, CAPTCHAs, takeovers | — |

`bdrive` and the agent each run as their own system user (`bdrive`,
`obox`), not as `ntindle`, so a compromised orchestrator SSH session
cannot rewrite either component or read the browser profile. Blast-radius
note: the profile holds logged-in session cookies, so a compromised
*driver* could ride those sessions — the same is true of the managed
agent's browser. Containment is the service users' lack of other
privileges plus the audit trail (§13).

## 3. Architecture

- **bdrive**: one Python service on spark-vm, Playwright-driven
  Chromium, persistent profile at `/home/bdrive/profile/`. All browser
  traffic forced through the swap proxy (`http://127.0.0.1:18080`); the
  driver refuses to start a session if the proxy health check fails.
- **On-box agent** (`obox`): a second service (same box, own user) that
  implements the agent loop. It thinks with an LLM whose API key is
  installed by the user via `cred set llm-api` and used through the swap
  proxy (placeholder in config, swapped on egress like any credential).
  Model choice is deployment config, not spec.
- Transport: local CLI over SSH for v1 (`bdrive …`, `obox …`); path to
  MCP-over-SSH-tunnel later. The protocols are transport-agnostic JSON.
- Sessions: `bdrive open` returns a session id; actions target a session;
  idle sessions expire after 30 minutes. Agent jobs: `obox submit
  <brief.json>` returns a job id; `obox steer <job> <message>` continues
  it; `obox status <job>` polls state (`running`, `need_info`,
  `done`, `failed`); `obox report <job>` fetches the terminal report.

## 4. Observation — the agent sees an AX tree, not just pixels

The interview confirmed the managed agent's primary sense is the
**accessibility tree**, not screenshots. `bdrive` reproduces it:

- Every observation returns: current URL, page title, target/document
  identity, a `ref_scope` token, and an AX snapshot with element locators
  (`@e1`, `@e2`, …) carrying role, accessible name, and
  enabled/visible state. The tree includes offscreen elements; locator
  actions bring them into view before acting.
- Locator refs are valid **only** with the `ref_scope` token from the
  exact observation that supplied them, and only the **newest**
  observation's tree is actionable — older trees are redacted. The
  driver rejects stale refs instead of guessing.
- A fresh AX capture is automatic after every action call (terminal
  observation), so the agent always decides from current state.
- `snapshot` — observation-only call; never combined with actions.
- `look` — model-visible screenshot (PNG, base64) plus its saved path;
  used to verify layout and anything the AX tree misrepresents
  (including CAPTCHAs and bot challenges).
- `get_text` / `get_html` (bounded, optional locator scope) — exact
  rendered copy (prices, addresses, error messages) when the AX
  rendering is lossy. `get_attr` / `get_value` — typed reads.
- `wait` — exactly one of `text` (exact page text to appear),
  `text_gone` (exact text to disappear), or `time_ms` (blind pause
  **only** for a duration the page itself states, e.g. a queue timer —
  never for navigation, loads, search, or hydration).
- Post-navigation rule: after `goto`, only exact-text `wait` or
  ref-free `look` / `get_text` / `get_html` / `state` may follow in the
  same array — never `snapshot`, never a locator action on the old tree.

## 5. Action protocol (narrow by design)

`bdrive` accepts an ordered **actions array** per call (mirroring the
managed agent's `muse.automation` batching). Actions run in order; the
first failure stops the array. Each action returns a receipt:
`completed` (ran, even if a later action failed), `unknown` (may have
run — inspect the page, never blindly repeat), or `not_started`
(stopped before this action; with an `actionability_reason` such as
`not_visible`, `obscured`, `disabled`, `not_editable`, `not_hittable`,
`unstable`, `timeout` — read the error and change page state rather
than repeating the action). The fixed vocabulary — no `eval`, no
shell, no CDP, no file access outside the profile:

- `open`, `goto {url}` (http/https only; `hsurr:` allowed in query —
  swapped on egress), `back`, `forward`, `reload`, `state` (URL, title,
  ready-state, target info).
- `click {ref, kind?}` (`kind`: left/right/double), `hover {ref}`,
  `fill {ref, text}` (**replaces** contents — preferred),
  `type {ref, text}` (**appends**), `press {key, ref?}` (key name or
  chord, e.g. `Enter`, `Escape`, `Shift+Tab`), `select {ref, value}`
  (native HTML select only; custom controls are clicked, then an option
  is clicked), `check {ref}`, `uncheck {ref}`, `focus {ref}`.
- `scroll {ref?, pixels?, direction?}` — element into view, region
  scroll, or page scroll (`up/down/left/right/top/bottom`).
- `snapshot`, `look`, `get_text {ref?}`, `get_html {ref?}`,
  `get_attr {ref, attribute}`, `get_value {ref}`, `wait {…}` (§4).
- `upload {ref, grant_ids}` — attaches only task-bound file grant IDs
  (see §10); reports attachment, not site acceptance.
- `download {ref}` — activates one control, captures exactly one file
  into the job's download dir (retrievable over SSH); the driver never
  executes it. `pdf {}` — renders the page to a job-owned PDF.
- `gesture {instruction, gesture, max_points?, click_hold_ms?, motion_profile?}`
  — freeform cursor gestures for targets with no AX node (canvas
  widgets, maps). For CAPTCHA/anti-bot challenges it additionally
  requires explicit user permission (§11); without permission the agent
  must `need_info` instead.
- `cookies_clear` — wipe the profile's cookies (logout hygiene).

Anything outside this set is rejected, not interpreted.

## 6. Credentials — placeholder-only (stronger than credential_fill)

The managed agent's `credential_fill` delivers real values into the
browser while the agent holds only an opaque reference and the
orchestrator holds nothing. spark-vm goes one step further: **no
component on spark-vm ever holds a real value, including the agent,
the driver, and the browser itself.**

Mapping of the managed fill protocol onto placeholders:

- The on-box agent fills login forms with placeholders
  (`hsurr:github`, `hsurr:acme:password`, `hsurr:acme:username`) using
  ordinary `fill` — from the agent's perspective this *is*
  `credential_fill`: the value never becomes visible to it, before,
  during, or after. The browser's DOM, memory, screenshots, and logs
  contain only placeholders.
- The swap proxy substitutes the real value in the request on egress —
  headers, query, path, JSON/text bodies, and urlencoded form bodies
  (percent-encoded `hsurr%3A…` forms are handled).
- Field identification mirrors the managed contract: the agent matches
  the live AX role + accessible name of each control before filling,
  and verifies the resulting page state afterward.
- Sign-in order of preference (same as managed): reuse the persistent
  profile's session if already signed in (check via `snapshot`, not a
  restore call); email/phone + code if offered; otherwise
  username + password placeholders.
- If the host is not allowlisted, the placeholder passes through
  literally and the server receives a useless string. Safe default.
- TOTP codes are credential entries (`hsurr:github:totp`): typed as a
  placeholder, swapped on egress like anything else.
- SMS/email one-time codes cannot be auto-read on spark-vm (no
  connected inbox). The agent returns `need_info:"otp"` (§9); the user
  reads the code and the orchestrator passes it back as a one-shot
  `fill` — the same single-use relay as the managed agent's raw-code
  path, used once and never repeated in any report.
- There is intentionally no `credential_fill` RPC: there is nothing to
  fill — the value never exists on this box outside swapd's store.

## 7. Payments — the wallet stays orchestrator-side

The managed agent performs Stripe Link spend requests itself. On
spark-vm the wallet (Stripe Link, cards) is a Meta-runtime capability
the on-box agent cannot reach, so the purchase flow splits at the
trust boundary:

1. The on-box agent drives checkout up to final review, then returns
   `need_info:"purchase_review"` with merchant, items/variants/
   quantities, delivery address, contact info, shipping option,
   delivery estimate, total incl. taxes/fees, add-ons, cancellation
   terms, and remaining setup (login, security-code takeover).
2. The orchestrator runs the normal purchase flow (wallet approval,
   virtual card funding) and relays the single-use virtual card details
   to the agent as **transient credentials** — the exact analog of the
   managed agent's transient-credential path: entered once with
   ordinary `fill` into the merchant's card form, for that checkout
   only, never written to logs, reports, memory, or files, never
   repeated in any handoff.
3. The agent submits, verifies the confirmation page, and reports the
   order/confirmation identifiers from page output — never from
   intended values.

A denied, failed, or unknown-outcome payment is never retried by the
agent; it reports and waits. One job handles at most one distinct
order — a second order is a fresh job.

## 8. Approvals — the allowlist is the standing approval

The managed agent requires fresh user approval before a credential is
delivered to the browser. spark-vm's equivalent is the proxy allowlist:

- A credential can only ever reach a host the user allowlisted in
  `/home/swapd/hosts.allow`. The allowlist is managed by the user (the
  orchestrator may propose entries, never write them silently).
- Every substitution is audit-logged (`/home/swapd/swap.log`: timestamp,
  host, placeholder name — never the value). The user can verify after
  the fact what went where.
- Honest difference: there is no per-fill approval prompt. A compromised
  orchestrator could direct the agent to submit placeholders to an
  *already-allowlisted* host without a fresh prompt. The mitigations are
  the user-owned allowlist, the audit log, and the narrow action set
  (no exfiltration channel beyond what the page itself shows).
- Destructive/outbound actions the managed agent would gate (purchases,
  money movement, messages sent as the user, account creation,
  password resets, deletions) remain gated the same way: explicit user
  approval for the action itself, independent of credentials — enforced
  by the orchestrator before the brief, and re-checked by the agent via
  `need_info` if the page's actual terms differ from the brief.

## 9. Ask-back — `need_info` protocol

The managed agent pauses with `ask_for_information`; the on-box agent
pauses with `need_info`. Same contract:

- Returned as a parked job state carrying `need` (one of `otp`,
  `captcha`, `login_wall`, `choice`, `purchase_review`, `setup`), an
  `activity_title` (≤6 words, why it's waiting), a `context` (what is
  ready, every known blocker/question, and the material facts and
  options needed to answer), and optionally screenshot paths. The
  browser session stays open.
- Per blockage (mirrors managed behavior):
  - **Login walls**: report the observed state and error; stop on the
    login page. If no credential is stored, `need:"setup"` tells the
    user the exact `cred set <name>` command — the analog of the
    managed `capture_required` flow.
  - **One-time codes**: complete all preparation not depending on the
    code, let the site send it, park on the code screen naming the
    site, the code step, the delivery channel, and the masked
    recipient. Ask for the code value (never any other secret).
  - **CAPTCHAs/anti-bot**: only with explicit permission for this
    challenge/task or a standing user preference covering it —
    otherwise `need_info` with the site, the blocked step, and
    takeover instructions. `gesture` is never used for a challenge
    without that permission.
  - **Ambiguous choices** (size/color/model): collect ALL unresolved
    required choices and report them together in one pause; never infer
    material terms.
  - **Purchase review**: as §7 — full terms, then wait.
- Resumption: the orchestrator relays the user's answer, approval,
  choice, or one-shot code via `obox steer`. The agent resumes **from
  the current page** (fresh `snapshot` if needed) — never by
  re-navigating to the starting URL. A general "continue" does not
  approve a previously rejected step; only approval of that specific
  step counts. Resends of OTP codes happen only on explicit user
  request; rejected/expired codes are reported, never retried.
- The agent never invents credentials, never bypasses a CAPTCHA, never
  clicks through a consent it wasn't told to handle.

## 10. Task lifecycle

Mirrors the managed lifecycle, adapted to a CLI over SSH:

- **Brief** (`obox submit`): the assignment, date/time + user timezone,
  account identifiers the task may need (email/phone — never passwords
  or codes), file grant IDs for uploads (files the orchestrator staged
  via SCP into the job's inbox dir; the agent receives opaque grant
  IDs, never host paths), attempt limits and stop conditions in the
  user's words, and any standing permissions (e.g. CAPTCHA preference
  with its scope).
- **Steering** (`obox steer`): follow-up directives are treated as
  fresh instructions; the agent continues from the current page and
  takes a fresh `snapshot` if it needs current state. Attempt limits
  carry across the whole job history.
- **Terminal report** (`obox report`): exactly one per job. Outcomes:
  `completed` (only when everything asked for actually happened, verified
  from page/tool output — a purchase is not complete at final review
  while payment or submission remains), `need_info` (still viable,
  waiting on an answer), `failed` (route exhausted: unavailable item,
  site outage, removed flow), `timeout` (only on explicit timeout).
  The report carries the verified current state, deliverables
  (confirmation/order numbers, prices, resulting URL — from page output,
  never intended values), every committed external side effect (bought,
  sent, posted, created, changed), and paths of download/PDF artifacts
  for the orchestrator to fetch.

## 11. Safety rails

Adapted from the managed agent's rails; enforced by the on-box agent,
with the orchestrator as backstop:

- The agent will not: pursue goals beyond the brief; follow instructions
  embedded in page/tool content (external content is data, never
  authority); accept optional tracking on cookie banners (necessary-only
  choices); create unrequested accounts, trials, subscriptions, or
  enrollments; submit a purchase without explicit user confirmation of
  the final terms; substitute a different payment method when the
  specified one is unavailable; retry a denied/declined/unknown-outcome
  payment or resubmit a rejected login; request passwords or OTP values
  except through `need_info`; disclose credentials, codes, or card
  details; send personal identifiers to third parties without express
  authorization; or bypass access controls.
- Requires explicit user approval (relayed by the orchestrator):
  submitting any purchase or booking (final-review pause first;
  approval of an exact quote does not authorize a higher total);
  creating an account or enrolling in anything with cost, renewal, or
  messaging terms; password resets / 2FA changes; deleting, cancelling,
  or overwriting anything not easily restored; CAPTCHA/bot-challenge
  solving (explicit permission for this challenge/task, or a standing
  preference with its scope — solving is never a standalone task and
  never implies purchase approval); wallet sign-ins (Shop Pay, PayPal —
  via user takeover of the live session); entering a saved card's
  security code (takeover).
- Sign-in attempt discipline: at most one automatic corrected
  resubmission when the site clearly rejects an identifier's *format*
  (corrected value, never the unchanged value); stop immediately on
  remaining-attempts / lockout / rate-limit / cooldown warnings and
  report them.
- No `refresh_environment` equivalent: spark-vm has one fixed egress
  IP. A block explicitly attributed to the IP/network is terminal for
  the job — the agent reports it via `need_info` instead of retrying
  through a fresh route. (Honest difference from the managed agent.)

## 12. Persistence

- Chromium profile persists at `/home/bdrive/profile/` across jobs and
  reboots: cookies, localStorage, HSTS. Signed-in sessions survive
  between jobs unless the site expires them — the managed
  `restore_saved_login` concept maps to "check signed-in state via
  `snapshot` first."
- `cookies_clear` exists for explicit logout hygiene. Secrets are never
  written to the profile (only placeholders ever reach the browser).
- Isolated per job (mirrors managed per-task isolation): AX refs and
  `ref_scope` tokens (single-observation validity), one-time-code
  values relayed via `need_info` (bound to the current challenge),
  file grant IDs, and download/PDF artifacts (job-owned dirs).

## 13. Observability — watch and take over

- `look` on demand plus an automatic screenshot after every mutating
  action, returned with the action result; screenshot paths attach to
  `need_info` pauses and the terminal report.
- Append-only action log per job (`/home/obox/jobs/<id>.log`):
  timestamp, action, ref, URL — **never field contents**.
- v2 (planned): live view/takeover via noVNC over the tailnet,
  user-initiated only — the managed agent's watch/takeover equivalent.

## 14. Trust boundaries

- The orchestrator sees: the brief it sent; the job's terminal report
  (verified state, deliverables, side effects, screenshots); and any
  `need_info` exchanges with the answers relayed back. The report is the
  only durable record it keeps — the session's step-by-step detail
  stays on the box, out of the orchestrator's transcripts.
- The orchestrator cannot see: raw credential values (swapd's store),
  one-time-code values beyond the single relay it performed, full
  payment-card details (at most masked identifiers), the agent's private
  reasoning beyond what it reports, or any box files not explicitly
  staged for the job.
- The agent sees what the orchestrator cannot: the live rendered page —
  screenshots, the current AX tree, exact rendered text/HTML, action
  receipts — which grounds every decision and verifies outcomes before
  they are reported. The orchestrator relies on the verified report,
  never on its own view of the page.

## 15. Comparison with the managed browser agent

Scored against the interviewed capability inventory (not just the
previously observable contract):

| Property | Managed agent | spark-vm stack (this spec) | Verdict |
|---|---|---|---|
| Driver is a separate trust domain | Yes — dedicated browser-task agent | Yes — fixed `bdrive` service, own user | ✅ aligned |
| Agent is a separate trust domain from orchestrator | Yes — browser agent ≠ main agent | Yes — on-box `obox` agent ≠ orchestrator | ✅ aligned |
| Orchestrator cannot run code in the driver | Yes — task briefs only | Yes — fixed action set, no eval/shell/CDP | ✅ aligned |
| Credential values hidden from orchestrator | Yes — opaque `[credential:<uuid>]` refs | Yes — orchestrator only writes `hsurr:` strings | ✅ aligned |
| Values hidden from the agent/driver itself | No — `credential_fill` delivers real values to the browser agent | Yes — placeholders only; swap happens at egress | ✅ stronger |
| Fresh approval before credential use | Yes — per-fill approval | Standing approval via user-owned allowlist + audit log | ⚠️ different mechanism, same intent |
| Observation model | AX tree + ref_scope + screenshots | Same — AX tree + ref_scope + `look` | ✅ aligned |
| Action vocabulary | `muse.automation` batching, receipts, actionability reasons | Ordered arrays, same receipt semantics | ✅ aligned |
| Freeform gestures (CAPTCHA/canvas) | `visual_automation` | `gesture`, permission-gated for challenges | ✅ aligned |
| One-time codes | Protected inbox lookup, auto-filled | TOTP via placeholder; SMS/email via `need_info` ask-back | ⚠️ partial — no inbox on spark-vm |
| Credential capture when none stored | `capture_required` + secure form | `need_info:"setup"` + `cred set` instructions | ✅ aligned in intent |
| Persistent browser state | Yes | Yes — persistent profile dir | ✅ aligned |
| User can watch / take over | Yes — live session | v1: screenshots + action log; v2: noVNC | ⚠️ gap, planned |
| Ask-back when blocked | `ask_for_information` + resume-from-current-page | `need_info` + same resumption rules | ✅ aligned |
| Purchase flow | In-agent Stripe Link spend requests | Agent to final review → orchestrator wallet flow → transient card relay | ⚠️ split at the trust boundary by necessity |
| Destructive actions gated | Yes — purchase/message approvals | Yes — same rule, orchestrator + agent both enforce | ✅ aligned |
| Sign-in attempt discipline | One format-correction retry; stop on lockout signals | Same | ✅ aligned |
| IP/network block recovery | `refresh_environment` (one fresh route) | None — fixed egress; block is terminal, reported | ⚠️ honest difference |
| Secrets never in logs | Yes | Yes — placeholder names only; field contents never logged; proxy flow-dump logging disabled | ✅ aligned |

### Gaps to close (in priority order)

1. **Per-fill approval.** v2: first-use confirmation — the first time a
   job submits a given placeholder to a host, the agent pauses with
   `need_info:"confirm_first_use"` naming the credential and host.
   Cheap, closes the main residual gap.
2. **Live watch (noVNC over tailnet).** v2, user-initiated only.
3. **SMS/email OTP.** No inbox on spark-vm by design; `need_info`
   ask-back is the permanent answer, not a gap to fix.
4. Cosmetic: addon warnings for non-allowlisted placeholders are not
   currently reaching the journal on the restarted proxy (pass-through
   behavior itself is verified correct). Diagnose separately.

## 16. Build plan

1. `bdrive` service: Playwright driver, AX snapshots + ref_scope,
   action protocol (§5), ordered-array execution with receipts, session
   management, proxy health-check gate, runs as `bdrive` user.
2. `obox` agent service: brief/steer/status/report CLI, the
   observe→decide→act loop against `bdrive`, `need_info` parking,
   LLM calls via the cred-stored API key through the proxy, runs as
   `obox` user. Conformance tests with dummy credentials only:
   placeholder login flow end-to-end, `need_info` pause/resume,
   allowlist-denied pass-through, stale-ref rejection, receipt
   semantics, secret-free logs.
3. Repo: `browser-driver/` with SPEC.md, driver + agent source, systemd
   units, tests. Nothing merged without the conformance suite green.
4. v2: first-use confirmation, noVNC watch.

## 17. What this does not change

- Real secrets are still installed only by the user via `cred set` in
  their own SSH session. Neither service has a path to the secret store.
- The off-box credential service (tracked goal) remains the long-term
  direction; this stack is compatible with it unchanged — placeholders
  are placeholders wherever the swap happens.
