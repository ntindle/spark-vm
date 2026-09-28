# Self-update system (issue #532)

Every spark-vm — self-hosted or hosted — should keep itself and its default
toolset current without manual intervention. Today a fresh box updates OS
security packages via `unattended-upgrades`, but nothing updates the default
toolset and nothing ever pulls spark-vm's own agent components forward. Boxes
rot. This page is the design for the toolset self-update — the missing half
alongside repo-component auto-deploy (`deploy/auto-deploy.sh` + timer, which
already covers `proxy`, `confirm`, `cred-ui`). This design integrates with /
sits alongside auto-deploy; it does not duplicate it.

Scope is the **spark-vm-provisioned defaults only** (the install inventory in
`SETUP.md` plus the CUA stack). Explicitly out of scope: user-installed tools
— Tailscale, KiCad/KiKit, Muse CLI (the user's, not spark-vm's; Muse CLI
already self-updates hourly anyway), Blender, and user workloads. Opt-in
support for user tools can come later.

## Scope

| Area | Mechanism | S1 probe |
|---|---|---|
| OS security packages | Keep `unattended-upgrades` correctly configured (security auto-install); verify on every run, repair if disabled. `apt-daily` list refresh. | `unattended-upgrades` |
| CUA stack (Xvfb/XFCE session, `cua-driver`, localhost bridge) | Dedicated updater that knows the pinned install; `cua-driver` held on a known-good pin unless the pin is deliberately bumped. Restart only when idle. | `cua-driver` |
| docker engine + compose (apt), node/npm (nodesource), gh (apt) | `apt` upgrades scoped to the toolset's repos. | `docker`, `node`, `gh` |
| Playwright (pip) + `playwright install` browsers + `install-deps` system libs | pip upgrade + browser reinstall. | `playwright`, `playwright-browsers` |
| snap packages | `snap refresh`. | `snap` |
| `cred`/`swapd` and other spark-vm agent components (`muse-job`, keepalive scripts) | Version-pinned, updated from the repo. | `cred`, `swapd`, `muse-job` |
| spark-vm's own release | Repo `VERSION`. | `spark-vm` |

Not in scope: user workloads and user-installed tools (Tailscale, KiCad/KiKit,
Muse CLI, Blender) — opt-in later.

Per-component *health* checks (CUA bridge answers, docker hello-world,
Playwright screenshot smoke, `cred` round-trips) belong to S2's recovery work,
not to S1's inventory.

## Using S1 today

From the repo root:

```bash
python3 scripts/self_update.py status          # human table, always exits 0
python3 scripts/self_update.py status --json  # machine-readable
python3 scripts/self_update.py status --pins /path/to/pins.conf
```

No install, no timer, no writes — safe to run on any box, including one that
was never provisioned by spark-vm (missing tools just report `no`).

## Behavior requirements

(These describe the finished system. Items marked S2/S3 arrive in later
slices — see "Build slices" below; S1 ships the inventory only.)

- **Runs on a systemd timer** *(S3)* (default: weekly, in a quiet-hours window,
  configurable) with `--now` and `--dry-run` flags.
- **Never disrupts running agent work** *(S2)*: no service restarts while jobs are
  active. Updates apply at idle or defer to the next window — agent jobs must
  survive an update run. The updater checks for live `muse-job` sessions
  (and any operator-declared busy signal) before touching anything.
- **Per-tool version pinning** where breaking changes matter: the updater
  holds the tool on the pin in `scripts/self_update_pins.conf` until the pin
  is deliberately bumped (with a changelog note). *(S1 reports drift; S2
  enforces the hold.)*
- **Everything logged** *(S2)* to a stable location (`/var/log/sparkvm-self-update/`
  on the box, mirrored to the operator's journal); failures are loud (log +
  status flag), successes are quiet.
- **Idempotent and re-runnable** *(S2)*; safe to run on an already-current box
  (no-op).
- **Installed by provisioning** *(S3)* (cloud-init / setup path) **and backfillable**
  onto existing boxes with one command (`self-update install`).
- **Opt-out supported** *(S2)* (`self-update disable`), manual mode supported
  (`self-update run --now`).

## Acceptance (from #532)

- Fresh box + 30 days of simulated drift → a self-update run brings every
  in-scope tool to current/pinned without breaking: CUA bridge still answers,
  Playwright screenshot smoke test passes, docker hello-world runs, `cred`
  round-trips.
- An update run during an active agent job does not kill or corrupt the job.
- This page documents schedule, scope, pinning, opt-out, and log locations.

## Build slices

The system lands in reviewable slices; each slice is independently shippable.
Two PRs raced as "first slice" in September 2026 (#542, #551); this doc is the
canonical slice map after their reconciliation — the two implementations are
complementary planes, not competitors (see "Two planes" below).

- **S1 — `status` (shipped, #542):** read-only inventory. `self_update.py status`
  reports each tool's installed version against the pin file, as a human table
  or `--json`. Pure reads, stdlib only, never raises, always exits 0. This is
  the drift-visibility half of the system — it makes "the box rotted" a
  checkable fact before anything is automated.
- **S2 — update execution + recovery (framework shipped, #551):** per-tool
  updaters behind `deploy/toolset-update.sh update`, with `--dry-run`, the idle
  guard (defer while agent jobs are live), per-tool pinning enforcement, and
  structured logging. The v0 framework ships the chassis the behavior
  requirements describe — installed-copy trust model, weekly systemd timer
  (quiet-hours), `install` (provisioning path + one-command backfill onto
  existing boxes), `optout`/`optin`, single-flight lock, JSONL audit — plus the
  first real updater layer (`os-security`: unattended-upgrades presence plus
  `20auto-upgrades` exact). Still to come: per-tool updaters for docker / node /
  npm / gh / Playwright / cua-driver, pre-update snapshots (extending
  `deploy/auto-deploy.sh`'s snapshot/rollback pattern), per-component
  post-update health checks (CUA bridge answers, docker hello-world, Playwright
  screenshot smoke, `cred` round-trips), automatic rollback + blocked marking on
  failure, freeze on repeated failure, the machine-readable `spark-vm health`
  report for agent diagnosis, and the agent recovery runbook.
- **S3 — acceptance + independent entry point (remaining):** the acceptance
  test harness (simulated 30-day drift on a fresh box) and the independent
  backup entry point: a tiny recovery agent (health-check, rollback-to-snapshot,
  report) on a path independent of the primary admin path, refreshed only from
  a known-healthy state as the post-update step of the two-part update ordering.
  (The timer, install/backfill, and opt-out this slice originally named are
  already shipped in the v0 framework — see S2.)

### Two planes

The reconciled architecture has two planes with a clean privilege split:

- **Status plane** — `scripts/self_update.py status`. Unprivileged and
  read-only by construction: no sudo, no writes, no network, probes never
  raise, always exits 0. This is the drift-visibility source — the operator's
  and the agent's way to ask "what rotted?" on any box, including one that was
  never provisioned by spark-vm.
- **Update plane** — `deploy/toolset-update.sh`. Privileged (root), driven by
  the weekly systemd timer, with the idle gate, audit trail, and per-layer
  updaters. Its `status` subcommand reports per-layer *update state*
  (`ok` / `repair-needed` for `os-security`; `present` / `absent` for layers
  without an updater yet) — for installed-version drift, read the status plane
  instead.

**Contract between the planes:** `scripts/self_update_pins.conf` is the single
canonical pin file. The status plane reports drift against it today; each
update-plane layer adopts it for pinning enforcement as it lands (v0's
`os-security` layer predates the contract and is exempt — its guarantee is
config-state, not version pins).

Pin-file placement on a deployed box: the installed-copy trust model exists
because the repo checkout is untrusted-by-design for the update path, and that
rationale extends to pin *data* — a checkout writer with version-selection
authority over what root installs is the data-plane equivalent of the code
injection the model was built to prevent (bounded by signed apt/pip repo
contents, but pin-to-vulnerable-version is still real authority). So future
privileged layers MUST read pins from an installed/backfilled copy refreshed
only via the privileged `install` step (path TBD by the landing slice —
proposed: alongside the installed script under the toolset state dir), never
from the live checkout. Until a layer implements this, the contract is
status-plane-only.

## Recovery (from #532)

Self-update without recovery is just a fancier way to break the box. The
recovery story is designed around one operator: the user's Muse (an agent with
SSH access), not a human at a console. Requirements and their slice mapping:

- **Pre-update snapshots** (S2): extend `deploy/auto-deploy.sh`'s
  snapshot/rollback pattern to the toolset updater — snapshot everything the
  run will touch (package states, configs, service files) before changing
  anything.
- **Post-update health checks per component** (S2): CUA bridge answers on its
  port, `docker run --rm hello-world` passes, Playwright screenshot smoke test
  passes, `cred` round-trips, updater-managed systemd units are active. Any
  failure → automatic rollback to the snapshot, mark that update **blocked**
  (no retry loop into a worse state), and go loud.
- **Freeze on repeated failure** (S2): if health checks fail N consecutive
  runs, stop attempting updates entirely and surface a single "box needs
  attention" state instead of churning.
- **Machine-readable `spark-vm health` report** (S2): one shot for an agent —
  last update run + result, per-component current vs pinned versions, failing
  checks with log pointers, snapshot inventory available for rollback.
  Designed for an agent to diagnose, not a human to squint at.
- **Recovery runbook in docs** (S2): the exact agent playbook — read health
  report → identify failed component → roll back to snapshot (`--rollback`) or
  re-run updater (`--now`) → verify health → report. A competent agent with
  SSH fixes every failure class the updater can cause using only documented
  commands.
- **Audit trail** (S2): every update and rollback writes who/what/when/
  versions to the audit log — the same format auto-deploy already uses for
  repo components.
- **Independent backup entry point** (S3): the recovery story above has a
  shared-fate hole — if the updater breaks the agent's own access path (sshd,
  Tailscale, the shell), "Muse fixes it over SSH" is dead. A deliberately
  tiny recovery agent (health-check, rollback-to-snapshot, report; POSIX
  shell or static binary — no Python/node/docker) reachable over a path
  independent of the primary admin path (separate credentials at minimum;
  ideally dial-out heartbeat to the control plane over outbound HTTPS).
  Two-part update ordering: the main updater updates the toolset, runs health
  checks, and only then — from a known-healthy state — refreshes the backup
  entry point. Failure always lands toward safety.

S2 acceptance: simulated broken update (bad pin) → health check fails →
automatic rollback → box healthy → update marked blocked → health report shows
exactly what happened and what the agent should do; plus an agent-driven
recovery drill from the health report alone. S3 acceptance: deliberately break
the primary access path — the backup entry point still answers, reports, and
the runbook restores primary access; kill the backup entry point mid-refresh
and the previous known-good version still serves.

## Why S1 is read-only first

Automated updaters are easy to write and hard to trust. Shipping the
inventory first gives every later slice something to test against: S2's
updaters are correct exactly when S1's `status` goes from "drift" to "clean",
and the S3 acceptance test asserts on S1's output, not on vibes.
