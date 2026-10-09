# Fleet dashboard (#845)

Web dashboard for the spark-vm control plane: the owner's fleet at a glance.

## What it is

A single self-contained HTML page (`dashboard.html` — no build step, no
dependencies, vanilla JS). The control-plane Worker serves it at `GET /`
(hosted: `https://api.sparkvm.dev/`; self-hosted: your own plane's root —
the page calls the plane that served it, so both deployments work
unchanged).

## Features

- **Owner sign-in.** Paste an owner API key (`svm_…`, minted via
  `POST /v1/owner/bootstrap` — the only minting path; the `/v1/owner/keys`
  endpoints list and revoke, they cannot mint). The key is held in the
  tab's `sessionStorage` only — the page never puts it in a cookie,
  `localStorage`, or a URL. Sign out (or close the tab) drops it.
- **Agent sign-in (AgentID).** Standard OIDC public client + PKCE S256
  against `https://auth.agentid.com` — a separate sign-in path for
  agents owned by the fleet owner. Agent sessions are read-only by
  policy (pairing approvals and action-approval taps stay human-only)
  and are held in `sessionStorage` only. Fleet API access for agents
  needs the control-plane follow-up (`POST /v1/agent/exchange`); see
  the Agent sign-in section below.
- **Fleet list.** Box name, id, status, and last-heartbeat age. Boxes with
  no heartbeat in the last **5 minutes** are marked **STALE** (boxes
  heartbeat every ~60s by default, so 5 minutes is ~5 missed beats);
  boxes that never heartbeated show "no heartbeat". Auto-refreshes every
  30 seconds.
- **Box detail.** Hostname, uptime, per-service up/down, key fingerprint,
  token expiry, and the raw last-status JSON behind a toggle. All
  box-controlled strings are HTML-escaped before rendering.
- **Pairing approvals.** Pending pairings with the server-computed
  fingerprint — compare it with the fingerprint on the box screen, then
  type the pairing code the box shows. This is the human side of the
  pairing-code enrollment flow (`pairing/` in this repo). Note: on a fresh
  database with no owner keys yet, the very first approval is CLI-only
  (`spark_pair.py approve --bootstrap`) — the dashboard can't sign in
  until the first owner key exists.
- **Action approvals.** Pending agent actions for the open box, with
  approve/deny taps. Each tap is write-once (the plane rejects a
  conflicting re-tap, a replay confirms the recorded decision, and an
  expired approval reads as expired, never pending). All box-controlled
  strings are HTML-escaped and control characters neutralized before
  rendering. This is the human side of the phone-approval flow
  (`docs/APPROVALS_PLANE_GAP_ANALYSIS.md`).
- **Login gating.** Every API call carries the owner key as a
  `Bearer` token; a 401 anywhere returns the UI to the sign-in screen.
  The dashboard only ever shows the signed-in owner's boxes (the plane
  scopes fleet reads by owner key).

## Agent sign-in (AgentID)

Agents owned by the fleet owner can sign in with
[AgentID](https://www.agentid.com/llms-full.txt) — a standard OpenID
Connect identity provider for agents (`iss https://auth.agentid.com`,
ES256 id_tokens, PKCE S256). The dashboard registers as a **public**
OIDC client (`token_endpoint_auth_method: "none"`): the browser flow
uses a S256 code challenge, and there is **no client secret anywhere**
(`test_no_client_secret_anywhere` pins this).

**Auth model (explicit):** the page has two actor types.

- `actor_type: "human"` — the existing owner API key (`svm_…`). Full
  owner powers, including pairing approvals and action-approval taps.
- `actor_type: "agent"` — the AgentID OIDC session. **Read-only by
  policy.** Agents never approve pairings and never tap action-approval
  decisions; those stay human-only.

**Current status:** the client-side flow is complete (sign-in button →
PKCE authorize redirect → callback code exchange → id_token claim
validation → agent identity card, all client-side, session in
`sessionStorage` only). Fleet API access for agent sessions is **not
yet enabled on the control plane**: the agent id_token is never sent to
the plane as a Bearer (the plane would 401 it), and the agent view says
so. Enabling it is a control-plane follow-up: `POST
/v1/agent/exchange`, validating the ES256 id_token signature against
the AgentID JWKS, checking `iss`/`aud`/`exp`/`actor_type`, and minting
a short-lived read-only session scoped to the `owner_sub`'s fleet.

**Finishing the setup (needs the owner):**

1. Register the app in the AgentID console as a **public** client
   (browser-authenticated; neither RFC 7591 dynamic registration —
   401 without an account — nor `agentid-cli init --name`, which only
   registers confidential `client_secret_basic`/`client_secret_post`
   clients and wants to store the secret in `.env.local`, can produce
   the public client this page needs).
2. Redirect URIs: every plane origin that serves this page — at minimum
   the hosted plane's root (`https://api.sparkvm.dev/`); add each
   self-hosted plane origin too, or the IdP refuses the redirect.
3. Request scopes `openid` + `owner_email` (the owner's email arrives as
   the `owner_email` id_token claim).
4. Paste the issued `client_id` into the `AGENTID` config block in
   `dashboard.html` (the `client_id: ""` field just below the
   "AgentID (agent) sign-in" comment — public client ids are not
   secrets), then run `./sync_dashboard.py` to re-inline the page
   into the worker.

## Canonical-copy rule

The Worker deploys as a single file, so it carries this page inline
(between `# --- BEGIN dashboard (#845 authenticated fleet dashboard) ---`
/ `# --- END dashboard ---` markers in the control-plane `worker.py`).
**This file is the canonical copy** —
edit here, then run `./sync_dashboard.py` to re-inline it into
`worker.py`; `test_dashboard.py` asserts the two are byte-identical when
the worker source is reachable. The inlined HTML must not contain a
`"""` sequence (it would terminate the Python string); the test and
the sync script both enforce this.

## Syncing the worker copy

`sync_dashboard.py` mechanically rewrites the inlined block between the
BEGIN/END markers — no manual copy-paste. It only touches the marked
region, writes atomically, keeps the END marker line byte-for-byte
(indentation included), and refuses loudly on missing or duplicated
markers, a BEGIN marker stranded on the file's last line, a `"""`
sequence in the HTML, or an odd number of trailing backslashes in the
HTML (either would break the inlined Python string). It is idempotent
(a second run changes nothing).

    ./sync_dashboard.py                          # default worker checkout
    SPARKVM_WORKER_PATH=/path/to/worker.py ./sync_dashboard.py
    ./sync_dashboard.py --worker /path/to/worker.py
    ./sync_dashboard.py --check                  # verify only, no write

The worker path resolves as `SPARKVM_WORKER_PATH`, defaulting to the
loop VM's control-plane checkout
(`.../sparkvm-dev-website-v2-cloudflare-management-infra/control-plane/worker.py`).
`test_dashboard.py` shares the same resolution, so the byte-identity
test runs for real instead of skipping wherever the env points at a
worker — on the loop VM that means the control-plane checkout; on CI
(forks) the test still skips.
