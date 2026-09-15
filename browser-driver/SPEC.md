# spark-vm Browser Driver — SPEC

The single spec file for the browser-driver stack (the former repo-root
`SPEC.md` was merged here 2026-09-15; git history has the original).
Incorporates the owner decisions of 2026-09-15 recorded in
`browser-driver/REVIEW.md` ("Owner decisions").

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
| On-box agent (`obox`) | Run the observe→act loop via `bdrive`; type placeholders | See real values (only `hsurr:` strings); reach the network except via the swap proxy; keep working past a `need_info` without an answer |
| Driver service (`bdrive`) | Drive Chromium per the action protocol (§5) | See real values; run anything but the fixed action set |
| Swap proxy (swapd) | Substitute values for allowlisted hosts; audit | Be reconfigured by the orchestrator or agent (hosts.allow is user-managed) |
| Inference proxy (swapd) | Swap the `llm-api` key into obox's model calls, header-only | Swap any other credential; touch request bodies |
| LLM provider (agent's brain) | Receive prompts with page content + placeholders | Receive real credential values (they never exist in prompts) |
| User | Watch sessions; edit allowlist; install secrets via `cred set`; answer approvals on the tailnet page | — |

**Enforcement status (review finding 2 — decided 2026-09-15).** The
agent login becomes a **systemd-nspawn jail mirroring the agent's own
runtime cell** (see `jail/cell-mirror.md` for the interview): rootful
inside (guest root is not host root), its own rootfs, package installs
free inside, a veth whose only egress is the swap proxy on the host,
and no host secrets, swapd state, bdrive state, or audit log inside.
swapd, bdrive, the audit log, and the confirmation page live on the
host. Docker inside the jail is rootless/podman or nothing — never the
host socket. Until the jail lands, ENVIRONMENT.md's rule stands: the
implementer logs in as `ntindle` with passwordless sudo and *can*
become root, so read every orchestrator "cannot" above as "must not"
until then.

`bdrive` and `obox` each run as their own system user (`bdrive`,
`obox`), not as the agent login, so a compromised orchestrator SSH
session cannot rewrite either component or read the browser profile.
Blast-radius note: the profile holds logged-in session cookies, so a
compromised *driver* could ride those sessions — the same is true of
the managed agent's browser. Containment is the service users' lack of
other privileges plus the audit trail (§13).

## 3. Architecture

- **bdrive**: one Python service on spark-vm, Playwright-driven
  Chromium, persistent profile at `/home/bdrive/profile/`. All browser
  traffic forced through the swap proxy (`http://127.0.0.1:18080`); the
  driver refuses to start a session if the proxy health check fails.
- **obox**: the on-box agent (own user, `obox`) implementing the agent
  loop. Its `submit` / `steer` / `status` / `report` interface is the
  orchestrator-facing contract (owner decision, round 7): the
  orchestrator is replaceable without changing `bdrive`, swapd or the
  confirmation page. Muse drives it today; anything that can submit a
  brief and read a report can drive it tomorrow. It thinks with an LLM whose API key the user installs via
  `cred set llm-api`. The key is used through a **separate inference
  proxy** (review finding 31) — a second mitmdump instance on
  `127.0.0.1:18081` with its own secrets directory holding only
  `llm-api`, header-only placement, and the provider as its only host.
  The provider is never in the main proxy's `hosts.allow`, so page
  content in prompts never traverses credential insertion for other
  secrets. Model choice is deployment config, not spec.
- The orchestrator's SSH login lands in the **nspawn jail** (§2); its
  veth's only egress is the swap proxy on the host. swapd, bdrive, the
  audit log, and the confirmation page live on the host, outside the
  jail.
- Transport: local CLI over SSH for v1 (`bdrive …`, `obox …`); path to
  MCP-over-SSH-tunnel later. The protocols are transport-agnostic JSON.
- **IPC (review finding 15).** The driver daemon listens on a unix
  socket (`/run/bdrive/bdrive.sock`, owned by `bdrive`, group
  `bdrive-clients`, mode 0770); the orchestrator's login is a member
  of `bdrive-clients`. The `bdrive` CLI speaks JSON over the socket —
  no sudo on the driver path. **Peer verification (finding 33):** the
  daemons additionally check `SO_PEERCRED` and accept only the `obox`
  uid and the orchestrator login — group membership alone is not the
  check.
- **Session model (review finding 14).** One browser process with one
  persistent context; a "session" is a page (tab) inside it.
  Concurrent sessions are tabs sharing the profile's cookies — never
  two browser launches on the same profile dir (Playwright locks it).
- **Egress enforcement (review finding 10).** "All traffic via the
  proxy" must be a network rule, not a Chromium flag: an nftables rule
  confines the `bdrive`/`obox` uids to `127.0.0.1:18080` outbound. The
  proxy health-check gate is belt and braces.
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

- Refs may address elements inside iframes (SSO and payment forms live
  there); the snapshot's AX tree includes frame boundaries and every
  ref is frame-scoped. Every action takes an optional `timeout_ms`.
  `look` screenshots are size-capped (bounded viewport; full-page on
  explicit request). The job's download dir is group-readable by the
  orchestrator's login so artifacts can be fetched over SSH. (Review
  finding 17.)

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
- TOTP: the stored `totp` entry is the base32 **seed**; at swap time
  the proxy computes the current RFC 6238 six-digit code (30s step,
  SHA-1, stdlib only) and substitutes the code — never the seed.
  (Review finding 23; implemented.)
- Secret files: one file per credential name in `/home/swapd/secrets/`.
  The `#hsurr:multi` marker as the file's first non-blank line is the
  SOLE source of file layout (review finding 35): registry entries
  describe placements, never file format, so running `cred register`
  on a bare-value file can never silently break its swaps. A marked
  file holds `entry=value` lines (one per line); non-`k=v` lines are
  dropped with a warning. For a single-value secret an entry suffix
  matches when absent, when `access_token`, or when it is the one
  entry the registry declares for that credential.
- SMS/email one-time codes cannot be auto-read on spark-vm (no
  connected inbox). The agent returns `need_info:"otp"` (§9); the user
  reads the code and the orchestrator passes it back as a one-shot
  `fill` — the same single-use relay as the managed agent's raw-code
  path, used once and never repeated in any report.
- There is intentionally no `credential_fill` RPC: there is nothing to
  fill — the value never exists on this box outside swapd's store.
  `credlib/fill_secret.py` stays as the schema-compatible mirror of
  the cell's `credential_fill` for human-run scripts — it is the
  weaker path on this box (values enter the `ntindle` process) and is
  never used by the driver or the on-box agent. (Review finding 16.)

**Swap-correctness requirements** (the proxy satisfies all of these;
review findings 5–9, each reproduced against the addon before fixing):

- JSON bodies: substitute the `json.dumps`-escaped value, never the raw
  string — a `"` or `\` in a password must not break the document.
- `application/x-www-form-urlencoded`: parse with `parse_qsl`, swap
  values, re-encode with `urlencode` — no regex on the raw body, so a
  literal `:` plus `&`/`=` in a value cannot split fields.
- Entry suffixes: for single-value secrets, `hsurr:name:entry` swaps
  only when `entry` is absent or `access_token`; anything else passes
  through rather than swallowing the suffix.
- Headers: never substitute into `Referer` or `Origin` — a placeholder
  placed in a `goto` URL would otherwise return as the real value in
  later requests and land in server logs. Substitute into `Cookie`
  only when a placement says so.
- Paths: swap per path segment; segments whose decoded form did not
  change are left byte-identical, so re-quoting cannot corrupt `%25`/
  `%2F` or escapes like `:`/`@`/`~` in unchanged segments.
- Responses: on allowlisted hosts, replace known secret values in
  response text bodies with their placeholders, so a "review your
  details" page or a key-echoing API cannot hand the value back
  through `text`/`look`. Values shorter than 8 characters are never
  scrubbed (a one-character password must not rewrite "Next"), any
  entry can opt out per-name with `"scrub": false` in the registry
  (usernames, emails), and TOTP codes match as whole digit tokens so
  they collide with neither prices nor IDs. Residual risk, stated not
  solved: images and binary bodies (review finding 4; implemented).
  Screenshots (`look`) can visually contain sensitive field values
  even though AX text observations mask them — masking is not
  screenshot redaction (review nit 78; stated not solved for v1; the
  shots dir is 0750, bdrive-only).
  The hook buffers bodies, so obox cannot depend on streamed provider
  responses — a provider's streaming endpoint arrives at obox only
  after the whole body is in (review finding 40).

**Surrogate note.** The reference architecture mints opaque,
per-use surrogates in authd, so an attacker page cannot contain a
valid one. spark-vm's placeholders are static and documented, so any
page *can* contain a valid `hsurr:` string — which is why the
untrusted-data envelope and `hsurr:` neutralization (§11, findings 26
and 30) are required v1 work here, not optional. A possible later
hardening: per-job aliases (`cred register <alias> --alias-of <name>
--host …`, revoked at job end) giving unguessable placeholders in the
same format. Open question: whether the cell's surrogates are
per-session — worth confirming before choosing between static
placeholders and minted aliases.

### Grant scoping (review finding 28) — owner decision recorded, static half implemented

The reference authorizes each concrete request (method, path, decoded
body) before inserting the credential, and every approval is a scoped
grant (one-time, session, task, time-bounded, perpetual). spark-vm's
allowlist entry was a perpetual, host-wide grant: a bound GitHub token
could be used for any request to `api.github.com`, including deleting
repositories.

**Owner decision (review round 2):** approve the static method and
path limits now; defer session- and task-scoped grants. The proxy
cannot attribute a request to a bdrive session or an obox job —
sessions are tabs in one shared browser context (§3), and the proxy
sees one Chromium connection pool — so a session-scoped grant would
be a time-bounded grant with a misleading name. For v1 keep `one-time`
and `time-bounded` only, with bdrive (trusted, on the host) telling
swapd when a job ends so swapd revokes.

**Implemented:** registry `allowed_methods` / `allowed_paths`, checked
in `_resolve` before swapping. Absent means unrestricted (for
migration); an explicit empty list fails closed (review round 4) —
`cred-registry-set remove-method`/`remove-path` delete the key when a
list empties and print "now unrestricted" so the state is visible.
Managed with `cred-registry-set add-method|add-path` (stored
uppercased for methods). Semantics, per the owner's requirements:

- Paths are compared after percent-decoding to a fixpoint AND
  dot-segment normalization, so `/repos/../admin`,
  `/repos/%2e%2e/admin`, and `/repos/%252e%252e/admin` (double-encoded)
  cannot pass an `/repos/` prefix. A path that still contains `%`,
  `;`, or `\` after fixpoint decoding is refused outright — those
  only reach a path-bound credential as smuggling tricks for lenient
  servers (double decoding, path parameters, backslash separators).
- `allowed_paths` is defense in depth (review round 4): the proxy does
  its best with the path it sees, but the server's own parser has the
  last word on what a path means.
- Prefixes are segment-aligned: `/repos/` matches `/repos` and
  `/repos/x` but not `/repository`.
- Methods are uppercased on both sides.
- A path/method-bound credential never swaps where the method or path
  cannot be verified: CONNECT tunnels and websocket messages fail
  closed (refused + audited).
- The owner binds methods for every write-capable token at install
  time, even though the field is optional.

**Deferred:** `grants` with `session` and `task` scopes, and the
`one-time` / `time-bounded` grant machinery. When they land:
`one-time` means one request flow, not one regex match, with a short
grace window because browsers retry and follow redirects.

**Open questions, answered by the owner:**

- Card pathway (§7): stays as job-scoped placeholder entries, not
  one-time grants — checkout forms re-submit and a one-time grant
  fails on the retry.
- Audit: grants log to the same audit file as `grant=` lines; no
  second log.
- Default expiry: job end via bdrive's revoke, with a hard 24-hour cap
  for anything left unrevoked.

**Open gap (noted in review, still unanswered):** the `cred-grant`
writer is specified as "callable only from the confirmation page's
backend", but the page is served by bdrive and bdrive is not swapd —
the socket between them and the peer check still need specifying
before the deferred half is built.

Registry shape (static half live; `grants` reserved as a structural
key since review round 4, still a proposal for the deferred half):

```jsonc
"github": {
  "allowed_hosts": ["github.com", "api.github.com"],
  "allowed_methods": ["GET", "POST"],
  "allowed_paths": ["/repos/", "/user"],
  "grants": [
    {"scope": "session", "session": "<bdrive session id>",
     "expires": "<utc iso>", "methods": ["POST"], "paths": ["/login"]}
  ]
}
```

## 7. Payments — trusted fill and a single-use issued card

The managed agent performs Stripe Link spend requests itself. On
spark-vm the wallet is not reachable from the box, and two facts rule
out the placeholder mechanism for cards. Card, expiry and CVC fields
are digit-masked and Luhn-checked in the browser, and processors such
as Stripe Elements refuse to tokenize a non-numeric value, so a typed
placeholder never reaches the network. And card data is posted to the
processor's shared hosts, not the merchant's, so a per-merchant host
binding at the proxy cannot exist for cards. The card pathway
therefore mirrors the reference: a **trusted fill by `bdrive`**, and a
card whose own controls carry the merchant and amount binding.

Flow. obox drives, bdrive fills, the confirmation page approves:

1. **Drive to final review.** obox drives checkout up to the review
   step and parks with `need_info:"purchase_review"`: merchant (host
   and display name), items, variants and quantities, delivery
   address, contact, shipping option, delivery estimate, total
   including taxes and fees, add-ons, cancellation terms, and any
   remaining setup (login, security-code takeover). Nothing is
   submitted.
2. **File the approval.** `bdrive` files a structured approval with
   `kind: purchase`, `host` (the merchant), `amount` (total and
   currency), `job`, and the review fields as the labeled purpose.
   The filing names a live `session`; `bdrive` stamps that session's
   current URL and title into the item (finding 76), so the
   confirmation page shows the agent-claimed host next to where the
   browser actually is. Timestamps are ISO strings (finding 77).
   The requester is bdrive by file owner (finding 50). obox cannot
   file it.
3. **The owner approves on the confirmation page (§8).** Never via
   the orchestrator. The approval expires in one hour. Approval of an
   exact total does not authorize a higher one; a changed total is a
   new approval.
4. **A card is issued for that approval.** A swapd-side helper, run
   by confirmd on approve, calls the issuer's API (Stripe Issuing in
   v1) using an issuer secret stored in swapd's store with no host
   binding, so it never swaps and only the helper can use it. The
   card is single-use, capped at the approved amount as a
   per-authorization limit, and expires at job end plus a short
   grace. Its number, expiry and CVC are written as a job-scoped
   multi-entry secret `card-<job>` (`#hsurr:multi`), readable only
   over bdrive's peer-checked socket for that job.
5. **Trusted fill by `bdrive`.** obox issues one action,
   `fill_card {job}`, carrying no values. bdrive fetches the card
   entries from swapd (SO_PEERCRED, the bdrive uid only), locates the
   processor's fields including inside the processor's cross-origin
   iframe, types the real values itself, and pauses obox for the
   duration: no `snapshot`, `look` or `get_*` is served until the fill
   completes. Afterwards obox sees only the accessibility tree, and
   processor fields are treated as password-class for the read
   restrictions in §11.
6. **Submit and verify.** obox submits. A 3-D Secure or bank
   challenge parks as `need_info:"takeover"`; until live takeover
   exists (§13 v2), the job reports and stops. obox verifies the
   confirmation page and reports order and confirmation identifiers
   from page output, never from intended values.
7. **Job end.** `cred-grant-revoke --job` deletes `card-<job>` and
   the helper cancels the card at the issuer. A denied, failed or
   unknown-outcome payment is never retried; obox reports and waits.
   One job handles one order.

Where the secrets are: the issuer secret and every `card-<job>` value
belong to swapd; obox and the orchestrator never hold them; bdrive
holds them in memory only for the fill. The audit log records
`card=issued job=… amount=… last4=…` and `card=cancelled`, never the
number, expiry or CVC. Response scrubbing (§6) also scrubs the number
and CVC of active job cards from processor and merchant responses.

The **one-time-code relay stays a stated exception**: a code the user
reads out may be relayed once for the current challenge, matching the
reference's own raw-code path.

## 8. Approvals — the allowlist is the standing approval

The managed agent requires fresh user approval before a credential is
delivered to the browser. spark-vm's equivalent is the proxy allowlist:

- A credential can only ever reach a host the user allowlisted in
  `/home/swapd/hosts.allow`. The allowlist is managed by the user (the
  orchestrator may propose entries, never write them silently).
- **Per-credential host binding** (review finding 1; implemented): the
  registry (`credentials.json`, via `cred register <name> --host
  <h>`) holds an `allowed_hosts` list per credential; `_resolve`
  refuses hosts not on the credential's list. `hosts.allow` remains
  the outer gate. A credential with no binding never swaps.
- **Grant scoping** (review finding 28): proposed, not implemented —
  see the proposal in §6. When it lands, first-use confirmation
  becomes a session-scoped grant that swapd records itself.
- Every substitution is audit-logged (`/home/swapd/swap.log`: timestamp,
  host, placeholder name — never the value); refused swaps are logged
  too (`refused=`), so the safe default is evidenced, not assumed. The
  user can verify after the fact what went where. The log stays on the
  box by owner decision (review finding 12): it is a verification aid,
  and the long-term direction (§17) makes it a control later without
  interim work.
- Honest difference: there is no per-fill approval prompt. A compromised
  orchestrator could direct the agent to submit placeholders to an
  already-allowlisted host without a fresh prompt. The mitigations are
  the per-credential binding above, the audit log, and the narrow
  action set.
- **Confirmation channel: a tailnet page (owner decision 3, review
  finding 3).** swapd or bdrive serves a small page reachable only over
  the tailnet, authenticated by Tailscale identity, where pending
  approvals and first-use confirmations are answered. Nothing routes
  through obox or the orchestrator — a confirmation only counts if the
  user signals the driver/swapd directly, so a compromised
  orchestrator cannot answer itself. The page is part of bdrive v1.
- Destructive/outbound actions the managed agent would gate (purchases,
  money movement, messages sent as the user, account creation,
  password resets, deletions) remain gated the same way: explicit user
  approval for the action itself on the tailnet page, independent of
  credentials — enforced by the orchestrator before the brief, and
  re-checked by the agent via `need_info` if the page's actual terms
  differ from the brief.

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
- Resumption: for information questions (`choice`, `setup`, `otp`
  code values), the orchestrator relays the user's answer via `obox
  steer`. For **approvals** (`purchase_review`, `confirm_first_use`,
  destructive-gate pauses), the user answers on the tailnet
  confirmation page (§8) — the answer routes directly to swapd/bdrive,
  never through the orchestrator or obox. The agent resumes **from
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
- Destructive-gate triggers (heuristic, review finding 18): a click or
  submit whose target's AX role/name matches buy, purchase, pay,
  submit-order, send, post, publish, delete, cancel, or
  account-security patterns pauses with `need_info` naming the action
  and its terms — even mid-task. The pause is answered on the tailnet
  confirmation page (§8), never via the orchestrator.
- **Untrusted content (review findings 26 and 30 — required v1).**
  obox wraps every page or tool block in an explicit untrusted-data
  envelope and neutralizes `hsurr:` strings inside it, so a page that
  contains a valid-looking placeholder cannot trick the agent into
  submitting it somewhere it should not go. (Static documented
  placeholders are guessable by any page — unlike the reference's
  minted surrogates — which is why this is required here.) v2: a
  classifier pass over page text and downloaded files, run outside
  obox.
- **Read restrictions (review finding 32; finding 75 removes the
  caller flag).** `get_html`, `get_value`, and `get_attr` are refused
  on password-type inputs and on any field `bdrive` typed in the
  current job — the `sensitive` flag used to be caller-supplied, so a
  prompt-injected agent could omit it and read a relayed value back
  through `get_text` or the snapshot. `bdrive` now treats every value
  it typed as unreadable for the rest of the job; the agent already
  knows what it typed. They are a read-back path for the one real
  value that may transiently sit in the DOM.
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
- **Egress guard (review findings 29, 37, 38).** The swap proxy's
  `server_connect` hook resolves each upstream host BEFORE the TCP
  connect — a refused host never gets even a SYN — and kills the
  connection via the hook's error channel. Refused ranges: RFC 1918,
  loopback, link-local, CGNAT/tailnet space, `0.0.0.0/8`, IETF
  assignments, benchmarking and reserved space, and the v6
  equivalents; IPv4-mapped IPv6 (`::ffff:127.0.0.1`) is unwrapped
  before judging. Refused egress is audited. A host on the explicit
  allow list (`/home/swapd/ssrf.allow`, hostnames or CIDRs) may
  proceed; default-deny on a fresh install; the tailnet is on the list
  for now. On allow, the server address is pinned to the resolved IP,
  so the check and the connect use the same answer (no DNS-rebind
  race). DNS failure fails open — the connect fails on its own
  anyway. Redirects are separate connections and get the same check.
- **CA trust (owner decision 5).** The swapd CA goes system-wide inside
  the jail's own rootfs only — everything in the jail is meant to go
  through the proxy. `with-proxy` keeps setting `NODE_EXTRA_CA_CERTS`,
  `REQUESTS_CA_BUNDLE`, and `SSL_CERT_FILE` regardless (Node, Python
  `requests`, and Java ignore the system store). Chromium reads its
  NSS database, so the `certutil` step in the login recipe stays.
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
| Credential values hidden from orchestrator | Yes — opaque `[credential:<uuid>]` refs | Yes — orchestrator only writes `hsurr:` strings | ✅ aligned under the jail (§2); policy, not mechanism, until it lands |
| Values hidden from the agent/driver itself | No — `credential_fill` delivers real values to the browser agent | Yes — placeholders only; swap happens at egress (response-echo scrubbing implemented, finding 4) | ✅ aligned; marginal gain for a large correctness surface (findings 5–9) |
| Fresh approval before credential use | Yes — per-fill approval | Standing approval via per-credential host binding + user-owned allowlist + audit log; first-use confirmation as session-scoped grants (§6 proposal); approvals answered on the tailnet page, never via the orchestrator | ⚠️ different mechanism, same intent — grants proposed, not built |
| Swap correctness (encoding, headers, paths) | n/a — runtime-owned | Behaviors in §6 implemented and conformance-tested; refused swaps audited (finding 22) | ✅ implemented |
| Egress actually forced through the proxy | n/a — runtime-owned | Chromium flag today; nftables uid rule required (finding 10); jail veth has no other route (§2) | ⚠️ pending |
| Private-range / SSRF guard | Yes — resolved-IP validation | Pre-connect `server_connect` guard, pinned IP, completed ranges (37–38); allow list (`/home/swapd/ssrf.allow`), tailnet allowed for now (finding 29) | ✅ implemented |
| Inference transport separated from credential insertion | Yes — separate inference proxy | Separate mitmdump instance, header-only, own secrets dir (finding 31) | ✅ implemented |
| Untrusted-content labeling | Yes — harness labels + classifier ensemble | Untrusted-data envelope + `hsurr:` neutralization required v1 (findings 26, 30); classifier pass v2 | ⚠️ v1 mechanism specified, not built |
| Observation model | AX tree + ref_scope + screenshots | Same — AX tree + ref_scope + `look` | ✅ aligned |
| Action vocabulary | `muse.automation` batching, receipts, actionability reasons | Ordered arrays, same receipt semantics | ✅ aligned |
| Freeform gestures (CAPTCHA/canvas) | `visual_automation` | `gesture`, permission-gated for challenges | ✅ aligned |
| One-time codes | Protected inbox lookup, auto-filled | TOTP via placeholder; SMS/email via `need_info` ask-back | ⚠️ partial — no inbox on spark-vm |
| Credential capture when none stored | `capture_required` + secure form | `need_info:"setup"` + `cred set` instructions | ✅ aligned in intent |
| Persistent browser state | Yes | Yes — persistent profile dir | ✅ aligned |
| User can watch / take over | Yes — live session | v1: screenshots + action log; v2: noVNC | ⚠️ gap, planned |
| Ask-back when blocked | `ask_for_information` + resume-from-current-page | `need_info` + same resumption rules | ✅ aligned |
| Purchase flow | In-agent Stripe Link spend requests | Agent to final review → user approves exact terms on the tailnet page → orchestrator wallet flow → job-scoped card placeholder relay | ⚠️ split at the trust boundary by necessity |
| Destructive actions gated | Yes — purchase/message approvals | Same rule; confirmations answered on the tailnet page, never via the orchestrator (finding 3 decided) | ✅ aligned |
| Sign-in attempt discipline | One format-correction retry; stop on lockout signals | Same | ✅ aligned |
| IP/network block recovery | `refresh_environment` (one fresh route) | None — fixed egress; block is terminal, reported | ⚠️ honest difference |
| Secrets never in logs | Yes | Yes — placeholder names only; field contents never logged; proxy flow-dump logging disabled | ✅ aligned |

### Gaps to close (in priority order)

1. **Grant scoping (finding 28).** Proposal in §6; awaiting owner
   review before implementation.
2. **obox proper (findings 26, 30).** Untrusted-data envelope and
   `hsurr:` neutralization are required v1 work; the inference proxy
   (finding 31) must exist before obox's first model call.
3. **The jail (§2) and the tailnet confirmation page (§8).** Until
   they land, the "cannot" rows are policy and confirmations have no
   unforgeable channel.
4. **Live watch (noVNC over tailnet).** v2, user-initiated only.
5. **Egress as a network rule (finding 10).** nftables uid confinement
   for `bdrive`/`obox` to `127.0.0.1:18080`.
6. Cosmetic: addon warnings for non-allowlisted placeholders are now
   also audit-logged (finding 22); if journal lines are still missing,
   diagnose the service's log plumbing separately.

## 16. Build plan

0. **Review findings first** (`browser-driver/REVIEW.md`). Proxy work
   landed: per-credential `allowed_hosts` + `_resolve` enforcement (1),
   swap-correctness fixes 5–9, TOTP-as-code (23), response scrubbing
   (4), refused-swap warning + audit (22), registry/marker multi-entry
   (25), private-range guard (29), inference proxy (31), path-byte
   preservation and registry-set hardening (34), marker-only file
   layout (35), scrub minimum length + opt-outs (36), guard range
   completions (37), pre-connect `server_connect` guard + DNS pinning
   (38), inference registry writer (39), audit/warn/size-cap nits
   (40), and the approved half of grant scoping — static
   `allowed_methods`/`allowed_paths` (28). One conformance test per
   finding. Owner decisions 2026-09-15 settled the jail (§2,
   finding 2), the tailnet confirmation page (§8, finding 3), the audit
   log staying on the box (12), CA in the jail only (13), the card
   pathway + one-time-code exception (27), and the default-deny guard
   (29). Session/task grant scopes stay deferred. Repo hygiene still
   open: `.gitignore` (20), `proxy/install.sh`
   rebuild instructions (19), `flow_detail=0` + error-line URL check
   (21).
1. **`bdrive` v1 (round 8).** Playwright driver as the `bdrive`
   user with the persistent profile; AX snapshots with `ref_scope`;
   the v1 action set (`open`, `goto`, `snapshot`, `click`, `fill`,
   `type`, `press`, `select`, `check`, `look`, `get_text`, `wait`,
   `back`, `reload`, `state`, `cookies_clear`) with receipts; socket
   bind-mounted into the jail, SO_PEERCRED accepting the jail's
   mapped agent uid and `obox`; proxy health gate; nftables uid rule
   confining `bdrive`'s egress to the proxy (finding 10); password
   read restrictions (32); driver enablement through the confirmation
   page (finding 74 — a one-time human acknowledgement that the
   persistent profile is in use, not the grant channel's first-use
   confirmation, which already covers first use of credentials via
   refused swaps). Driven by the orchestrator from the jail
   until obox exists. v1.1: `gesture`, `upload`, `download`, `pdf`,
   `hover`, `scroll`, `fill_card`.
2. **`obox` (round 9).** The stable orchestrator-facing interface:
   `submit` / `steer` / `status` / `report`; the observe-decide-act
   loop against `bdrive`; `need_info` parking; the untrusted-data
   envelope and `hsurr:` neutralization (26, 30); model calls
   through the inference proxy with `stream: false`, `store: false`
   and an explicit reasoning effort; runs as `obox`. Conformance
   tests with dummy credentials: placeholder login end to end,
   pause and resume, allowlist-denied pass-through, stale-ref
   rejection, receipt semantics, secret-free logs.
3. **Round 10.** The card pathway (§7): issuer helper, `card-<job>`
   entries, `fill_card`, cancellation at job end. Web Push for the
   confirmation page (manifest, service worker, VAPID, owner-only
   subscribe, minimal payload).
4. **Done:** the jail (§2), the confirmation page (§8), the proxy
   work in item 0.
5. **v2:** noVNC watch and takeover; classifier pass over page text
   and downloads outside obox (finding 30).

## 17. What this does not change

- Real secrets are still installed only by the user via `cred set` in
  their own SSH session. Neither service has a path to the secret store.
- The off-box credential service (tracked goal) remains the long-term
  direction; this stack is compatible with it unchanged — placeholders
  are placeholders wherever the swap happens.
