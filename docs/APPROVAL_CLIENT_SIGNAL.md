# Client-visible approval signal (proxy/confirmd track)

**Status: implemented** — `proxy/swap_addon.py` (H18, GitHub #133).

## Problem

When the swap proxy refuses a request for lack of a grant, it files a
confirmd approval for the human — but the agent that made the request
learns nothing machine-readable. The request goes upstream with the
placeholder intact and fails as a remote auth error, which is not
parkable: the agent cannot tell "waiting on your approval" from "wrong
credentials". `confirmd`'s `/api/pending` is the human page's poller
(owner-auth gated); the missing leg was the agent-client one. This doc
specifies it. It is the §6.6 leg of `docs/FIRST_TEN_MINUTES_SPEC.md`.

## The channel

The proxy's only channel back to its client is the proxied response, so
the signal rides response headers, set in the `responseheaders` hook
(which fires before the body finishes — the signal also rides streaming
responses):

- `X-Spark-Approval-Pending: <aid>` — a grant request for
  this request's `(credential, host, method)` tuple is filed (or already
  pending). `<aid>` is the approval id (16 random hex chars) — always a
  single id: the proxy coalesces to one pending approval per tuple (the
  first live match; a fresh filing returns exactly one), so the
  comma-joined list form never holds two ids in practice. Park the
  task and re-issue the gated request to poll.
- `X-Spark-Approval-Decision: <state>:<aid>[, <state>:<aid>...]` —
  terminal decision(s) for the tuple, `state` in: a single response can
  carry more than one — one request that swaps two credentials under
  two grants records `approved` for each aid, and a filing scan can
  reap several expired tuple matches in one pass. Clients must tolerate
  the comma-joined list and act on each leg.
  - `approved:<aid>` — the owner approved; the request that carries this
    header was swapped under the grant minted from `<aid>`.
  - `denied:<aid>` — the owner denied within the decision window. A
    denial is terminal *for the parked task*: the agent must not expect
    a fresh approval on its own. Escape hatch: the owner can re-open the
    denied request from its answered-history card, which files a NEW
    pending approval (new aid) and re-pushes the owner — but the agent
    is never told about it. After the owner approves the re-opened
    request, re-issue the gated request; it then succeeds with
    `approved:<new-aid>`. Surface as `human-denied`.
  - `expired:<aid>` — the pending approval the client was waiting on
    expired unanswered. **Best-effort, not a guarantee**: the proxy
    reports this leg only when its own filing scan observed the stale
    item in pending/ at scan time (the actual delete may still be won
    by confirmd's render reap — the leg is appended before the proxy's
    own delete attempt). `confirmd`'s pending renderer reaps expired
    items independently (plain delete — they never reach the answered
    history), so when the owner has the pending page open between the
    expiry instant and the agent's next poll, confirmd usually wins the
    race: the proxy then files the replacement *silently*, and the
    client sees only a changed `X-Spark-Approval-Pending: <new-aid>`
    with no decision header at all. Treat a changed pending id exactly
    like an explicit `expired:<old>` — keep waiting on the newest id.
    When the proxy *is* the reaper, the same response normally carries
    a fresh `X-Spark-Approval-Pending: <new-aid>` so the client keeps
    waiting on the new id. (If no fresh pending id accompanies it, the
    replacement filing was suppressed — the per-credential flood cap or
    the 60s filing rate limit is active — so keep polling; the
    replacement files once the window clears.)

Header values carry only the approval id and the state word — never
credential names, hosts, or secret material. Ids are validated against
`\A[A-Za-z0-9_-]{1,64}\Z` (anchored at string ends, not line ends, so
a newline-bearing id can never enter a header) before being echoed;
anything else is dropped, never emitted. The proxy also strips any
upstream `X-Spark-Approval-Pending` / `X-Spark-Approval-Decision`
headers before rendering its own — the
agent treats these headers as the proxy's word, so a hostile origin
must not be able to forge them.

## Contract: the `consumed/` item schema (v1)

The proxy's terminal-denial lookup and confirmd's answered history agree
on one on-disk contract: `consumed/<aid>.json`. It is the pending item
as the proxy filed it, plus confirmd's answer stamp:

- Filed by the proxy: `id` (16 random hex chars), `created`,
  `expires`, `kind` (`grant-request`), `credential`, `host`, `method`,
  `path_prefix`, `scope`, `amount`, `job`, `detail`, `summary`.
- Stamped by confirmd at answer time: `decision` (`approve` or `deny`),
  `answered_at` (UTC ISO8601), `answered_by` (the answering owner's
  tailnet login name), `requester` (the filing process's owner name —
  `bdrive` or `swapd`).

Two independent processes read and write it — confirmd writes on answer
(via the answered→consumed move; strays via the answered sweep), the
proxy reads the `credential, host, method, path_prefix, decision,
answered_at, id` subset in its denial lookup — so the schema is named
and versioned here rather than left implicit. The **v1** version lives
in this doc only: there is no `schema_version` field in the file (adding
one is the obvious v2 step if the field set ever changes). Writers may
ADD new fields freely — readers ignore fields they don't know. Changing
or removing a field, or redefining what any field means, requires
bumping the version label in this doc (v1 → v2) and a reader check on
both sides.

Drift is fail-closed: the proxy skips consumed/ items it cannot parse
or whose fields fail its checks, so a drifted file degrades to "no
terminal-denial signal" — the client keeps polling and the owner gets a
fresh push — never to a wrong signal.

## Decision-window semantics

A `denied` decision ends the parked task instance: once the client
stops re-issuing, no new approval is filed and the owner is not
re-pushed — **a denial is terminal for that task**. The 1-hour window
(measured from `answered_at`) only bounds how long the proxy keeps
delivering `denied:<aid>` to clients that keep polling anyway; after
the window, a fresh refusal files a new approval — an old denial does
not veto future requests forever. Denial suppression is scoped to the
denied normalized path: a denial for `/a` does not suppress filings
for `/b` on the same `(credential, host, method)` tuple — identical
retries of the denied request stay suppressed (anti-nag), other paths
file and push normally. `approved` is delivered on every
request swapped under the owner-minted grant (the grant carries the
approval id), so a client that retries its gated request after the
human approves sees both the successful swap and the explicit
`approved:<aid>` confirmation.

### Recovery after a mistaken denial

The proxy never re-files or re-pushes for a denied tuple inside the
window, so a mis-tapped Deny has no in-band recovery — but the owner
can always fix it out of band by minting a grant directly:

```sh
proxy/grant-writer add --credential NAME --host HOST \
  --method METHOD --path-prefix PREFIX --approval-id <new-id>
```

The agent's next re-issued request then swaps successfully and carries
`approved:<new-id>`. For a minutes-scale first-run flow, treat this as
the escape hatch for a mistaken denial.

## Client flow (first-run script, §6.6)

1. Issue the gated request through the proxy.
2. If the response has no approval headers, proceed (or handle the
   upstream error as before — nothing changed for non-gated traffic).
3. If `X-Spark-Approval-Pending: <aid>` is present, park the task and
   report `waiting-on-approval`; re-issue the gated request
   periodically (recommended cadence: 30–60s — the 5–8 minute first-run
   window needs a few polls, not a busy loop) and read
   `X-Spark-Approval-Decision`. **Polls are real upstream requests
   carrying the placeholder credential**: pre-approval polls fail
   upstream as remote auth errors — harmless for side effects, but
   noisy against provider rate limits, so keep the cadence modest.
   Re-issuing the same `(credential, host, method)` tuple never files
   a second approval — it coalesces onto the existing pending item
   (no re-push) — so polling does not violate §6.6's single-approval
   constraint, and same-tuple polls always report the tuple's pending
   id, even inside the ~60s filing rate window. Note: a poll on a
   *different* tuple arriving within ~60s of the original filing (or
   while the per-credential flood cap holds) may carry **no** approval
   headers at all — that means "wait and retry", not "no approval
   pending"; the next poll outside the window reports the correct
   pending id for your tuple.
4. `denied:<aid>` → report `human-denied`, stop refiling. `approved:<aid>`
   → continue the task. `expired:<old>` → keep waiting on the new
   `X-Spark-Approval-Pending` id from the same response — if none
   accompanies it, keep polling; the replacement files once the
   filing window clears. Note that `expired:<old>` is best-effort:
   confirmd's render loop usually reaps expired items first, so there
   is often NO `expired` leg — the client simply sees the pending id
   change (`X-Spark-Approval-Pending: <new-aid>`, no decision header).
   Treat a changed pending id exactly like an explicit `expired:<old>`:
   keep waiting on the new id. A client MAY also stop after repeated
   expiries and report `human-drop-off` (per
   `docs/TENANT_STATUS_ENDPOINT.md` §2) rather than waiting forever.

## What this is not

- Not a push channel: the client learns the decision when it re-issues
  the same `(credential, host, method)`; there is no lighter-weight
  poll — a method-gated action can only be polled with that method.
  The owner's push/email summons is the H2/H14 surface.
- Not an authentication surface: the aid is a correlation id, not a
  capability. `confirmd` stays owner-auth gated; the aid alone grants
  nothing.
- Refusals that must not file approvals (unbound host, path-not-verifiable
  on CONNECT, placement mismatch, unknown credential, unknown entry,
  bad totp, inference mode, approvals-disabled) emit no signal — a
  missing header means "not a grantable refusal", not "no approval".
- Not a poll endpoint: the signal rides only the proxied response of the
  gated request itself. The websocket *handshake* response rides
  `responseheaders`, but per-message signals are discarded (no header
  channel exists on websocket frames); CONNECT tunnels get no signal
  (`path-not-verifiable` is not grantable), though the inner
  TLS-intercepted request's response carries it — which is what the
  agent's HTTP client actually reads.
- Coalescing is tuple-wide `(credential, host, method)` while grants are
  path-scoped: two agents on different paths of one credential trigger
  sequential approvals (and sequential owner pushes). It converges
  correctly — each path's approval carries its own path-scoped grant —
  but don't be surprised by the second push.

## Security notes

- The aid is 64 bits of random hex — not a secret, but not enumerable
  either; leaking it to the agent reveals nothing the agent didn't
  already know (it made the request).
- A denial reveals that the owner denied *this tuple* — information the
  requesting agent already held. No cross-tenant signal: tuples are
  scoped to the requesting agent's own credentials, and denial
  suppression is further scoped to the denied path, so one planted
  denial cannot silence filings for other paths on the same tuple.
- The proxy never invents approvals: signals are only emitted for
  refusals on the method/path grant path that already filed (or would
  file) a real approval item.
- Multi-tenancy (H10): this signal is keyed without a tenant dimension
  (single-tenant deployment). H10 must scope it per tenant — extend the
  tuple with the tenant id or run the approvals dir per tenant. Do not
  share one approvals dir across tenants without scoping: under a shared
  proxy, one tenant's denial would suppress another tenant's filings
  and leak approval ids across tenants.
- Cross-agent denial DoS (inherent to the design, narrow): any agent
  that can trigger a filing for credential C's exact
  `(credential, host, method, path)` can cause the owner's denial to
  suppress filings for that tuple+path for 1h. Every suppression
  traces to a genuine owner denial of that exact tuple+path (agents
  cannot forge `consumed/` entries) and path-scoping bounds the blast
  radius — this is the documented "denial is terminal" trade-off, not
  a code bug.
