# spark-vm Browser Driver — SPEC v1

A fixed, narrow browser-driving service for spark-vm. It replaces ad-hoc
"assistant writes Playwright scripts and runs them over SSH" with a
separate driver the assistant orchestrates but cannot reprogram.

This spec is written against the observable trust contract of the
managed browser agent (the `browser.spawn_task` / `browser.steer_task`
driver): separate driver, opaque credentials, approvals, persistence,
observability, narrow interface, ask-back. Where spark-vm differs, the
difference is named and justified — never silently dropped.

## 1. Purpose

- Drive Chromium on spark-vm for browser tasks (logins, forms, scraping,
  checkout flows) without the orchestrator executing arbitrary code.
- Never handle a real credential value: the driver only ever sees
  `hsurr:` placeholders. The swap proxy substitutes values on egress.
- Keep a persistent browser profile across tasks (logins stick).

Non-goals: replacing the managed browser agent (it can't reach the
tailnet); general code execution; defeating CAPTCHAs/anti-bot.

## 2. Trust model

| Principal | Can do | Cannot do |
|---|---|---|
| Orchestrator (assistant) | Send narrow actions; read results/screenshots | Run code in the driver; see credential values; bypass the proxy |
| Driver service | Drive Chromium per the action protocol; type placeholders | See real values (only `hsurr:` strings); reach the network except via the swap proxy |
| Swap proxy (swapd) | Substitute values for allowlisted hosts; audit | Be reconfigured by the orchestrator (hosts.allow is user-managed) |
| User | Watch sessions; edit allowlist; install secrets via `cred set` | — |

The driver runs as its own system user (`bdrive`), not as `ntindle`,
so a compromised orchestrator session cannot rewrite the driver or read
its profile. Blast-radius note: the profile holds logged-in session
cookies, so a compromised *driver* could ride those sessions — the same
is true of the managed agent's browser. Containment is the `bdrive`
user's lack of other privileges plus the audit trail (§9).

## 3. Architecture

- One Python service on spark-vm (`bdrive`), Playwright-driven Chromium,
  persistent profile at `/home/bdrive/profile/`.
- All browser traffic forced through the swap proxy
  (`http://127.0.0.1:18080`); the driver refuses to start a session if
  the proxy health check fails.
- Transport: local CLI over SSH today (`bdrive <session> <action-json>`);
  path to MCP-over-SSH-tunnel later. The protocol is transport-agnostic
  JSON either way.
- Sessions: `bdrive open` returns a session id; actions target a session;
  `bdrive close` ends it. Idle sessions expire after 30 minutes.

## 4. Action protocol (narrow by design)

The driver accepts exactly these actions — no `eval`, no shell, no file
access outside the profile:

- `goto {url}` — navigate (http/https only; no file://). URLs may contain
  `hsurr:` placeholders (e.g. a token query param); the proxy swaps them.
- `fill {selector, text}` — type into a field. `text` may contain
  `hsurr:` placeholders; they are typed literally and swapped on egress.
  One-shot user-supplied codes (SMS/email OTP relayed via `need_info`)
  are typed here too — same single-use relay as the managed agent.
- `click {selector}`, `select {selector, value}`, `check {selector}`,
  `press {key}`.
- `shot` — screenshot (PNG bytes, base64).
- `text` — visible text of the page; `state` — URL, title, ready-state.
- `wait {for: selector|timeout}`.
- `back`, `forward`, `reload`.
- `download {selector}` — click-and-capture a download into the session's
  download dir (retrievable over SSH); the driver never executes it.
- `cookies_clear` — wipe the profile's cookies (logout hygiene).

Selectors: CSS only. Every action returns `{ok, session, …}` or
`{ok:false, error}`. Anything outside this set is rejected, not
interpreted.

## 5. Credentials — placeholder-only (stronger than credential_fill)

The managed agent's `credential_fill` delivers real values into the
browser while the orchestrator holds only an opaque reference. spark-vm
goes one step further: **no component on spark-vm ever holds a real
value, including the driver and the browser itself.**

- Login flows are driven with placeholders (`hsurr:github`,
  `hsurr:aws:access_token`). The browser's DOM, memory, screenshots, and
  logs contain only placeholders.
- The swap proxy substitutes the real value in the request on egress —
  headers, query, path, JSON/text bodies, and urlencoded form bodies
  (percent-encoded `hsurr%3A…` forms are handled).
- If the host is not allowlisted, the placeholder passes through
  literally and the server receives a useless string. Safe default.
- TOTP codes are credential entries (`hsurr:github:totp`): typed as a
  placeholder, swapped on egress like anything else.
- SMS/email one-time codes cannot be auto-read on spark-vm (no connected
  inbox). The driver returns `need_info` (see §7); the user reads the
  code and the orchestrator passes it back as a one-shot `fill`.

There is intentionally no `credential_fill` equivalent: there is nothing
to fill — the value never exists on this box outside swapd's store.

## 6. Approvals — the allowlist is the standing approval

The managed agent requires fresh user approval before a credential is
delivered to the browser. spark-vm's equivalent is the proxy allowlist:

- A credential can only ever reach a host the user allowlisted in
  `/home/swapd/hosts.allow`. The allowlist is managed by the user (the
  orchestrator may propose entries, never write them silently).
- Every substitution is audit-logged (`/home/swapd/swap.log`: timestamp,
  host, placeholder name — never the value). The user can verify after
  the fact what went where.
- Honest difference: there is no per-fill approval prompt. A compromised
  orchestrator could direct the driver to submit placeholders to an
  *already-allowlisted* host without a fresh prompt. The mitigations are
  the user-owned allowlist, the audit log, and the narrow action set
  (no exfiltration channel beyond what the page itself shows).
- Destructive/outbound actions the managed agent would gate (purchases,
  money movement, messages sent as the user) remain gated here the same
  way: orchestrator must have explicit user approval for the action
  itself, independent of credentials.

## 7. Ask-back — `need_info`

Like the managed agent's `ask_for_information`, the driver can pause
instead of guessing:

- Returned as `{ok:false, need_info:"otp"|"captcha"|"login_wall"|"choice",
  detail:…}`. The session stays open; the orchestrator relays to the
  user and resumes with a normal action.
- The driver never invents credentials, never bypasses a CAPTCHA, never
  clicks through a consent it wasn't told to handle.

## 8. Persistence

- Chromium profile persists at `/home/bdrive/profile/` across sessions
  and reboots: cookies, localStorage, HSTS. Mirrors the managed agent's
  persistent browser state.
- `cookies_clear` exists for explicit logout hygiene. Secrets are never
  written to the profile (only placeholders ever reach the browser).

## 9. Observability — watch and take over

The managed agent lets the user watch/take over a live session. v1:

- `shot` on demand plus an automatic screenshot after every mutating
  action, returned with the action result.
- Append-only action log per session (`/home/bdrive/sessions/<id>.log`):
  timestamp, action, selector, URL — never field contents.
- v2 (planned): live view via noVNC over the tailnet, user-initiated.

## 10. Comparison with the managed browser agent

Scored against the managed agent's observable trust contract:

| Property | Managed agent | spark-vm driver (this spec) | Verdict |
|---|---|---|---|
| Driver is a separate trust domain | Yes — dedicated browser-task agent | Yes — fixed `bdrive` service, own user | ✅ aligned |
| Orchestrator cannot run code in the driver | Yes — task briefs only | Yes — fixed action set, no eval/shell | ✅ aligned |
| Credential values hidden from orchestrator | Yes — opaque `[credential:<uuid>]` refs | Yes — orchestrator only writes `hsurr:` strings | ✅ aligned |
| Values hidden from the driver itself | No — `credential_fill` delivers real values to the browser agent | Yes — placeholders only; swap happens at egress | ✅ stronger |
| Fresh approval before credential use | Yes — per-fill approval | Standing approval via user-owned allowlist + audit log | ⚠️ different mechanism, same intent |
| One-time codes | Protected inbox lookup, auto-filled | TOTP via placeholder; SMS/email via `need_info` ask-back | ⚠️ partial — no inbox on spark-vm |
| Persistent browser state | Yes | Yes — persistent profile dir | ✅ aligned |
| User can watch / take over | Yes — live session | v1: screenshots + action log; v2: noVNC | ⚠️ gap, planned |
| Ask-back when blocked | `ask_for_information` | `need_info` states, session stays open | ✅ aligned |
| Destructive actions gated | Yes — purchase/message approvals | Yes — same rule, enforced on the orchestrator | ✅ aligned |
| Secrets never in logs | Yes | Yes — swap.log records placeholder names only; proxy flow-dump logging disabled | ✅ aligned |

### Gaps to close (in priority order)

1. **Per-fill approval.** v2: driver-side first-use confirmation — the
   first time a session submits a given placeholder to a host, the
   driver pauses with `need_info:"confirm_first_use"` naming the
   credential and host. Cheap, closes the main residual gap.
2. **Live watch (noVNC over tailnet).** v2, user-initiated only.
3. **SMS/email OTP.** No inbox on spark-vm by design; `need_info`
   ask-back is the permanent answer, not a gap to fix.
4. Cosmetic: addon warnings for non-allowlisted placeholders are not
   currently reaching the journal on the restarted proxy (pass-through
   behavior itself is verified correct). Diagnose separately.

## 11. Build plan

1. `bdrive` service: Playwright driver, action protocol (§4), session
   management, proxy health-check gate, runs as `bdrive` user.
2. Conformance tests (dummies only): login-form placeholder flow through
   the proxy (pattern already proven manually), `need_info` paths,
   allowlist-denied pass-through, profile persistence across restarts.
3. Repo: `browser-driver/` with SPEC.md, driver source, systemd unit,
   tests. Nothing merged without the conformance suite green.
4. v2: first-use confirmation, noVNC watch.

## 12. What this does not change

- Real secrets are still installed only by the user via `cred set` in
  their own SSH session. The driver has no path to the secret store.
- The off-box credential service (tracked goal) remains the long-term
  direction; this driver is compatible with it unchanged — placeholders
  are placeholders wherever the swap happens.
