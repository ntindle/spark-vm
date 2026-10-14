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
  checkable fact before anything is automated. For the playwright and
  cua-driver probes, the status plane targets the same managed artifacts the
  update plane's pin-driven layers converge (the managed venv's python for
  Playwright, `$CUA_DRIVER_BIN` for cua-driver), falling back to PATH when
  the managed target isn't present — for these pin-driven tools, "drift" in
  S1 is exactly the drift the updater's layers clear. The apt-layer tools
  (docker, node, gh) remain outside that invariant: the apt layer converges
  repo-latest rather than the pins. The Playwright browser builds join the
  invariant for missing builds (issue #1311): the update plane publishes
  the expected build dir names (from the hash-verified package's
  `install --dry-run`) and S1 compares its probed cache against them — a
  missing expected build is drift the next tick clears; an extra dir is
  named in the probe note but never drift, because the updater never
  prunes cache dirs. The browsers probe still targets the same cache directory the update plane converges —
  `PLAYWRIGHT_BROWSERS_PATH` when set, else the Playwright user's cache
  (`PLAYWRIGHT_USER`, default `ntindle`), else the invoker's cache (issue
  #1311) — so a wrong-cache report can no longer fake a clean inventory.
- **S2 — update execution + recovery (framework shipped, #551; cua-driver, apt, and playwright layers shipped; pre-update snapshots + automatic rollback + blocked marking shipped):** per-tool
  updaters behind `deploy/toolset-update.sh update`, with `--dry-run`, the idle
  guard (defer while agent jobs are live), per-tool pinning enforcement, and
  structured logging. The v0 framework ships the chassis the behavior
  requirements describe — installed-copy trust model, weekly systemd timer
  (quiet-hours), `install` (provisioning path + one-command backfill onto
  existing boxes), `optout`/`optin`, single-flight lock, JSONL audit — plus the
  first real updater layer (`os-security`: unattended-upgrades presence plus
  `20auto-upgrades` exact). Pre-update snapshots (extending
  `deploy/auto-deploy.sh`'s snapshot/rollback pattern), automatic rollback,
  and blocked marking on layer failure are shipped: a failed layer is rolled
  back to its snapshot and marked blocked so the next tick skips it instead
  of retry-looping, and `rollback [--layer <name>]` is the manual recovery
  entry point (see `docs/TOOLSET_UPDATE.md` "Snapshots and rollback"). Still
  to come: per-component
  post-update health checks (CUA bridge answers, docker hello-world, Playwright
  screenshot smoke, `cred` round-trips), the machine-readable `spark-vm health`
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
contents, but pin-to-vulnerable-version is still real authority). So
privileged layers MUST read pins from an installed/backfilled copy refreshed
only via the privileged `install` step, never from the live checkout —
implemented: `toolset-update.sh install` installs `self_update_pins.conf`,
`playwright_wheel_hashes.txt`, and `playwright_browser_hashes.txt` into
`$TOOLSET_STATE_DIR` (root-owned; the state dir is mode 700, the files
0644), and the update plane reads them from there (`_read_pin` reads
`$TOOLSET_STATE_DIR/self_update_pins.conf`;
the wheel/browser-hash files likewise). Both planes parse the pins file
with first-wins semantics for duplicated tool names
(`_read_pin` in `toolset-update.sh`, `load_pins` in `self_update.py`), and
the status plane surfaces duplicate pin names as dead config
(`duplicate_pins` in `status --json` and the table footer).

Pin-source split and the installed-pins hash (issue #1313): the
installed-copy trust model means the two planes read *different* pin files
by design — the status plane reads the checkout copy
(`scripts/self_update_pins.conf`), the update plane reads the installed
copy (`$TOOLSET_STATE_DIR/self_update_pins.conf`, root-owned mode 700).
A pin bump without a privileged `install` therefore leaves the status plane
reporting drift the updater can never clear, silently. The privileged
`install` step closes that gap by publishing
`sha256(installed pins)` to a world-readable record,
`/var/lib/sparkvm-toolset/self_update_pins.hash` (root-owned 0755 dir,
0644 file; written only by `install`), and the status plane compares its
checkout pins against it: `match` / `mismatch` / `unknown` (no record yet —
pre-#1313 installs, or an unreadable record; silent by design). A mismatch
renders the loud footer line "installed pins differ from checkout — run
`toolset-update.sh install`" and the `installed_pins_state: "mismatch"`
field in `status --json`. The comparison is byte-exact over the pins file
with no line-ending normalization — a checkout whose line endings differ
from the installed copy would read as a mismatch; unreachable in practice
(`install` byte-copies from the same checkout, and git normalizes to LF on
Linux), recorded here so the behavior is not a surprise. The record
carries no secret (the pins are public in the repo); its only job is
making a checkout/installed split loud. The record path (`PINS_HASH_DIR` /
`PINS_HASH_FILE`) must be a root-controlled path — a non-root-writable
carrier dir would let anyone move the mismatch signal; `install` refuses
relative paths and the filesystem root.

Managed-targets record (issue #1310): the same two-planes split applies to
*where* the managed tools live, not just which versions they hold. The
update plane resolves `CUA_DRIVER_BIN` / `PLAYWRIGHT_VENV` from its own
environment (the systemd unit's, under the timer); the status plane used
to resolve them from the invoker's shell. An operator relocating the
managed locations via the override in one environment but not the other
left the two planes silently targeting different artifacts — the exact
divergence #1308 closed, reintroduced through the override path. The
privileged `install` step now publishes the resolved targets to a
world-readable record, `/var/lib/sparkvm-toolset/managed_targets`
(root-owned 0755 carrier dir, 0644 file; written only by the privileged
update plane), and every `update` tick refreshes it — so the record always
reflects the timer's environment, not just the installer's. The status
plane prefers the record, falling back to its env override, then the
default (a missing or malformed record is silent: pre-#1310 installs never
wrote one). When the record wins over an explicitly-set env var that names
a different value, the cua-driver/playwright probe notes say so ("env
CUA_DRIVER_BIN=/x overridden by managed-targets record") instead of probing
the record's artifact silently (#1412). The tick refresh is log-loud but non-fatal: the record is a
visibility signal, not update safety — a wedged carrier must not block
the weekly converge. `uninstall` removes the record alongside the pins
hash. The record path (`MANAGED_TARGETS_DIR` / `MANAGED_TARGETS_FILE`)
carries the same root-controlled-path discipline as the pins hash
(`install` refuses relative paths, the filesystem root, and relative
target values); a target value containing any line-boundary character
(the full Python `splitlines` set — `\n \r \v \f \x1c-\x1e \x85`
U+2028/2029, not just newline/CR) is refused rather than published, since
the status-plane parser would split it into extra lines and let a later
duplicate key override the real one (#1412).

Expected browser builds (issue #1311): the same two-planes split applies
to *which* browser builds the cache holds. The update plane's playwright
layer installs exactly the archives the hash-verified package's
`install --dry-run` names, but S1 used to report browser builds as a bare
count — no drift signal existed at all. The privileged `install` step now
publishes the expected build dir names (one per line, names only, never
paths) to a world-readable record,
`/var/lib/sparkvm-toolset/expected_playwright_browsers` (root-owned 0755
carrier dir, 0644 file), and every real `update` tick refreshes it from
the installed package's dry-run — whether or not the playwright layer
converged that tick. The record claims SHOULD-BE (what the installed
package would install), not IS: a failed layer still refreshes it, so S1
compares against the fresh expectation instead of a stale record that
would read as a false clean. A blocked layer refreshes it too; the
mismatch hint then persists until the block clears (S1 cannot read
`blocked.state` — mode 700 — so the hint cannot know about the block;
the update plane's `status` shows blocked layers). `--dry-run` publishes
nothing. Residual: if the dry-run itself fails, the record stays stale
until a tick where it succeeds, and the layer failure is loud in the
audit log. Like the pins-hash and managed-targets paths, the record path
is operator-trusted configuration: S1 honors
`EXPECTED_PLAYWRIGHT_BROWSERS_FILE` from its environment. The status
plane compares its probed cache against the record: `match` /
`mismatch` (at least one expected build missing — including a wholly
absent cache dir, which holds zero builds and is updater-clearable
drift) / `unknown` (no record yet — pre-#1311 installs, or an unreadable
record; silent by design). A
mismatch renders the loud footer line "browser builds differ from
expected — run `toolset-update.sh update`" and the
`playwright_browsers_expected_state: "mismatch"` field in
`status --json`. Asymmetric by design: an extra dir in the cache is named
in the probe note but never counts as drift — the updater never prunes
cache dirs (`PLAYWRIGHT_BROWSERS_PATH` may point at a shared cache), so an
extra-build signal must never read as updater-clearable. `uninstall`
removes the record alongside the pins hash and the managed targets.

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
  attention" state instead of churning. **Shipped (partial):**
  `deploy/toolset-update.sh` implements the freeze on update-run failures
  (consecutive-failure counter, refuse-when-frozen, `unfreeze` command,
  machine-readable `status` row) — see `docs/TOOLSET_UPDATE.md`
  "Failure freeze". The health-check feed into the same counter is still
  future work.
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
