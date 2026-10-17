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

## Canonical-copy rule

The Worker deploys as a single file, so it carries this page inline
(between `# --- BEGIN dashboard (#845 authenticated fleet dashboard) ---`
/ `# --- END dashboard ---` markers in the control-plane `worker.py`).
**This file is the canonical copy** —
edit here, then regenerate the snapshot *and* re-inline:

    ./sync_dashboard.py --write-snapshot   # regenerate dashboard.inlined.txt
    ./sync_dashboard.py                    # re-inline into worker.py

`dashboard.inlined.txt` (committed next to this README) is the exact
block the sync writes between the markers, derived from this page.
The test suite asserts the snapshot is byte-identical to what the sync
would write — that assertion needs no worker checkout, so it runs on
GitHub Actions: an edit to the page that skips `--write-snapshot`
fails CI. The byte-identity test against the *live* worker copy still
needs a reachable worker checkout, so it runs wherever one exists (the
loop VM) and skips elsewhere. That split is deliberate, not an
accident: CI guards the repo-side contract, the loop VM guards the
deployed copy. When the byte-identity test fails, its message names the
drift direction and the exact remediation — a stale snapshot points at
`--write-snapshot`; a worker checkout carrying out-of-band edits is
named as unactionable in-repo (see issue #1299) rather than leaving the
contributor to debug the wrong copy.

## Syncing the worker copy

`sync_dashboard.py` mechanically rewrites the inlined block between the
BEGIN/END markers — no manual copy-paste. It only touches the marked
region, writes atomically, keeps the END marker line byte-for-byte
(indentation included), and refuses loudly on missing or duplicated
markers, a BEGIN marker stranded on the file's last line, a `"""`
sequence in the HTML, raw control bytes in the HTML (the page's `\xNN`
escapes must stay escapes — literal bytes mean a hand-paste corrupted
the source), or an odd number of trailing backslashes in the HTML
(either would break the inlined Python string). It is idempotent
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

## Never reverse-sync: the worker copy is never the source of truth

The deployed worker copy is a build artifact. If it was hand-edited
on the plane (as the AgentID surface once was), the repair is
*forensics, not a merge*:

1. `./sync_dashboard.py --extract > /tmp/worker-page.html` — read-only;
   dumps the worker's inlined block exactly as it is.
2. `diff /tmp/worker-page.html dashboard.html` — see what the hand-edit
   actually changed.
3. Hand-port the change into `dashboard.html` (this file), regenerating
   the snapshot and re-running the sync as above.
4. Re-deploy; verify with `--check`.

Do **not** paste the extracted block back into `dashboard.html`. A
hand-pasted block carries the literal-control-byte corruption class
the sync guards refuse (observed 2026-10-11: `\xNN` escapes converted
to raw control bytes, including a NUL inside the inlined Python
string); the sync will reject it loudly, and so will the static tests.
Re-author by hand — the extract path is diagnostics only.
