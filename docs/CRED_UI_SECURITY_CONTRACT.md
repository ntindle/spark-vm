# cred-ui security contract (#281)

**Decision (2026-10-13):** until the hosted front door (the user-facing entry
point of the hosted product) exists, cred-ui stays a
**localhost-only single-operator tool by explicit contract**. This document pins
what authenticates a cred-ui session today, what it deliberately does not do,
and where the line is drawn for hosted multi-tenancy. The per-tenant session
identity story — the other half of #281 — stays open and deferred to the hosted
front door plus H11's session model (the hosted multi-tenancy session/auth
design tracked in `docs/MULTI_TENANCY_AUDIT.md`); this contract is the "or" fork
the issue named, made explicit.

## What authenticates a session today

- A **per-install 256-bit Bearer <redacted>** (issues #86, #964), required on every
  `/api/*` endpoint except the public `/api/version` (service name + version
  only). The token authenticates the *operator's browser session* — the human's
  paste once per browser session (kept in the tab's sessionStorage; never a
  cookie, never a URL) — not a user identity. There is no identity, no per-user
  account, and no session beyond the tab that holds the token.
- The `X-Cred-UI: 1` header plus the Host-header check are a **CSRF gate**, not
  authentication: they stop malicious web pages from driving the API through
  the operator's browser. Any local process can set the header; the Bearer <redacted>
  is what stops other-uid local processes, sandboxed agents, and containers
  with loopback reach.
- The token is generated once (first start), stored swapd-owned at
  `/home/swapd/ui-token` (mode `0600`), read at startup through the pinned
  `sudo -n -u swapd /usr/bin/cat /home/swapd/ui-token` sudoers entry and
  written through the narrow `/usr/local/bin/cred-ui-token-set` writer. A
  process running as the operator's own uid can no longer read it straight off
  the filesystem; the server refuses to start if the token is missing-and-
  unwritable, malformed, or unreadable through the pinned reader. **Honest
  residual:** sudo matches the invoking *user*, not the process, so a same-uid
  process can still reach the token through those pinned sudo entries — and
  already holds equivalent power through the NOPASSWD writers. Every token read
  now crosses sudo's audit trail; the silent direct-file-read path is closed.
  The `CRED_UI_TOKEN_FILE` override is dev/CI/test-only: it must never be set
  in production, where it re-exposes the token to the operator uid. A
  localhost peer that dribbles just under the 10 s handler timeout can still
  hold a thread — accepted as a localhost-only residual (the code documents
  it); the bounded pool keeps it from growing without bound.

## Structural localhost-only

- cred-ui binds `127.0.0.1:18740` from hardcoded constants (`BIND`, `PORT` in
  `cred-ui.py`) — there is no env var, flag, or config file that changes the
  bind. The **SSH tunnel is the access control**. Changing the bind to
  `0.0.0.0` (or any non-loopback address) violates this contract; there is no
  supported configuration that does it.
- Defense in depth around the listener: Host-header allowlist (derived from
  `BIND`/`PORT`, never hand-maintained), bounded thread pool, 10 s handler
  timeout, 1 MB request-body cap, auth checked before the body is read,
  `X-Frame-Options: DENY` / `nosniff` / `no-referrer` / `no-store` on every
  response.

## What it deliberately does not do

- **No WHO.** Management actions are not attributed to a person: no login, no
  audit of who added/list/removed a credential. Credential *values* are never
  displayed in the UI and never logged by the server (only names, placements,
  hosts, and a has-value flag cross the API). This is deliberate for the
  single-operator box — the operator is the box owner — and it is exactly why
  this contract does not extend to multi-user hosts.
- **No per-tenant isolation.** The credential store is flat (#280) and the
  management API's authority is per-install, not per-tenant. Anyone who holds
  the token and can reach the loopback listener manages *every* credential.

## Deployment constraints (the contract)

1. Run cred-ui only on a **single-operator host** — one human, their own box.
2. Never bind it to a non-loopback address; never expose it except over the
   operator's own SSH tunnel.
3. Never deploy it on a shared or multi-tenant host. On such a host cred-ui
   is a credential dispenser to anyone with loopback reach plus the token —
   the per-tenant auth it would need does not exist yet.
4. Treat `--print-token` output like a password: show once, paste once, clear
   the terminal. Rotate with `--rotate-token` if the token may have leaked.

## Deferred (still #281's open half)

Per-tenant session auth tied to H11's session model — real identity for
credential management under hosted multi-tenancy — is not designed here and is
not cred-ui's job to invent. It belongs to the hosted front door build, with
#280's tenant dimension in the credential stack as the prerequisite. #281 stays
open for that half; this document is the explicit contract for the half that
ships today.

## Sweep verification (2026-10-13, main `2909c46`)

Every claim in §§1–4 was re-verified against `cred-ui/cred-ui.py` (and
`cred-ui/index.html` for the sessionStorage discipline) this turn:
hardcoded `BIND`/`PORT` (no override surface — the only env var in the file is
the dev/CI/test-only `CRED_UI_TOKEN_FILE`), token gate placement (all
`/api/*` except `/api/version`; auth before body read on POST), Host-header +
`X-Cred-UI` CSRF discipline, response headers, fail-fast startup token
validation, bounded pool/timeout/body cap, `compare_digest` comparison with a
fail-closed exception path, generic (non-disclosing) error on read failures,
no secret values in any response or log line. No new code holes found. The
#281 issue body's "zero user authentication / CSRF-only" description is stale:
the token auth shipped via #86/#964 and the response hardening via the #281
re-sweep; the stale body is corrected by pointer comment, not rewritten.
