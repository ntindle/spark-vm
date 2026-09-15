# Confirmation page (`confirmd`) — design

Owner decision 3 (2026-09-15): swapd or bdrive serves a small page
reachable only over the tailnet, authenticated by Tailscale identity,
where pending approvals and first-use confirmations are answered.
Nothing routes through obox or the orchestrator. This document is the
v1 design. The answer→grant channel (how an approval becomes a scoped
grant inside swapd) is specified here but **not implemented** — it
stops for owner review per the standing instruction.

## Properties (mirrored from the agent's own cell)

- Approvals go to the human directly, "not via their conversation with
  Muse", and the agent cannot answer on the human's behalf. The page
  authenticates the *human's Tailscale identity*; the jail has no
  Tailscale identity and cannot even route to the page (the jail
  firewall drops it).
- Every answer is recorded to the on-box audit trail (owner decision
  5: the audit log stays on the box as the verification aid).

## Serving

- `confirmd.py` (stdlib only: `http.server` + `ssl`), systemd unit
  `confirmd.service`, runs as the **swapd** user (the decision names
  "swapd or bdrive" as the server; swapd keeps the approvals directory
  to one owner).
- Binds **only** the tailnet address: `100.65.241.20:8443`.
- TLS with a real tailnet cert: `tailscale cert
  spark-vm.axolotl-sirius.ts.net` (no browser warnings on the human's
  devices). URL: `https://spark-vm.axolotl-sirius.ts.net:8443/`.
- HTTP (not HTTPS) would also be WireGuard-encrypted on the tailnet,
  but HTTPS is chosen so a human opening the URL sees no downgrade
  risk and bookmarks stay valid if the bind ever changes.

## Authentication

- On every request, the backend takes the peer IP from the socket and
  runs `tailscale whois <ip>`. The JSON `User.LoginName` must equal the
  owner's login (`ntindle@…`); anything else → 403.
- `tailscale whois` runs as swapd; if tailscaled's socket is not
  readable by swapd, a narrow sudoers rule allows exactly
  `tailscale whois *` (no other subcommand).
- No cookies, no passwords, no sessions: identity is re-checked per
  request. There is nothing for the agent to steal or replay — the
  agent has no tailnet identity at all.

## Data

- `/home/swapd/approvals/pending/<id>.json`:
  `{id, created, kind, summary, detail, requester, expires}`.
- `/home/swapd/approvals/answered/<id>.json`: the pending object plus
  `{decision: "approve"|"deny", answered_at, answered_by}` (the
  Tailscale login that answered).
- `confirm-request` helper (swapd/bdrive-only) writes pending files.
  bdrive will call it for first-use confirmations and destructive
  actions; in v1 it is a CLI for testing the page end to end.

## Endpoints

- `GET /` — pending approvals as plain HTML (no JS framework; HTML
  forms).
- `GET /approval/<id>` — detail with Approve / Deny buttons.
- `POST /answer` — `{id, decision}`; validates the id is still
  pending and unexpired, then moves it to `answered/`.
- `GET /answered` — history, newest first.

## v1 boundary (what is NOT built)

Recorded answers are **not consumed as grants**. No component reads
`answered/` to widen a credential's scope, mint a one-time grant, or
tell bdrive to proceed. That wiring is the deferred design below.

## Deferred: answer→grant channel (owner review required)

When the grant machinery is approved, the intended shape is:

1. The page backend (running as swapd) translates an `approve` answer
   into a grant record: `{credential, scope, expires}` appended to the
   registry's `grants` list (the key is already reserved; finding 44).
2. swapd's `_resolve` consults `grants` before the static
   `allowed_*` fields; expired grants are ignored and reaped.
3. Peer authentication between the page backend and the grant writer:
   both run as swapd in v1, so the boundary is the *human's Tailscale
   identity on the HTTP request*, not a socket credential. If a later
   split runs the page as a separate user, the grant writer must check
   `SO_PEERCRED` (finding 33) and accept only the page backend's uid.
4. Every grant lands in the swap audit log as a `grant=` line
   (spec §6: no second log).
5. Default expiry: job end via bdrive's revoke, hard-capped at 24
   hours for anything left unrevoked. One-time grants cover one
   request flow with a short grace window for retries/redirects.

Open question for the owner (from the review): the proposal says the
`cred-grant` writer is "callable only from the confirmation page's
backend", but if the page is served by bdrive and bdrive is not swapd,
the socket and the peer check between them must be specified. The v1
choice (page runs as swapd) sidesteps this; confirm it stays that way
or specify the split.
