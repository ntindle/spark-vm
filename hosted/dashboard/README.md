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
  `POST /v1/owner/bootstrap` or the keys endpoints). The key is held in the
  tab's `sessionStorage` only — the page never puts it in a cookie,
  `localStorage`, or a URL. Sign out (or close the tab) drops it.
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
- **Login gating.** Every API call carries the owner key as a
  `Bearer` token; a 401 anywhere returns the UI to the sign-in screen.
  The dashboard only ever shows the signed-in owner's boxes (the plane
  scopes fleet reads by owner key).

## Canonical-copy rule

The Worker deploys as a single file, so it carries this page inline
(between `# --- BEGIN dashboard ---` / `# --- END dashboard ---` markers
in the control-plane `worker.py`). **This file is the canonical copy** —
edit here, then re-inline into `worker.py`; `test_dashboard.py` asserts
the two are byte-identical when the worker source is reachable. The
inlined HTML must not contain a `"""` sequence (it would terminate the
Python string); the test enforces this.
