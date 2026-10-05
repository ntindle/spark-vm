# Toolset update (`deploy/toolset-update.sh`)

**Status: framework + four real layers.** Partial implementation of issue
#532 ("Self-update system: keep the box and its default toolset current").
This ships the framework — trust model, scheduling, audit, idle gate,
opt-out, failure freeze — and four real updater layers: `os-security`
(unattended-upgrades), `cua-driver` (pinned reinstall from the upstream
GitHub release), `apt` (docker / node / gh converged via apt), and
`playwright` (pinned pip package + Chromium browser builds + system
libraries). The remaining #532 slices (snapshots/rollback, independent
backup path) are explicitly follow-ups. Reconciled with
#542's read-only status plane — this script is the *update* plane; see "Two
planes" in `docs/SELF_UPDATE.md` for the canonical architecture.

## What it does

`deploy/toolset-update.sh` keeps a spark-vm box's **default toolset** current:
the OS security pipeline plus status probes for the tools provisioned by
default (docker, node, npm, gh, Playwright, cua-driver). Scope is
deliberately **provisioned defaults, not user-installed tools**.

Commands:

| Command | Effect |
| ------- | ------ |
| `status` | TSV per-component *update state* (`ok` / `repair-needed` for `os-security`; `present` / `absent` per tool, with the managed install's version as detail — the Playwright probe senses the managed venv, not system python); operator-readable, no root needed. For installed-version drift against the pin list, read the status plane instead: `python3 scripts/self_update.py status` (see "Two planes" in `docs/SELF_UPDATE.md`) |
| `update [--force] [--dry-run] [--now]` | Repair `os-security`, enforce the `cua-driver` pin, apt-converge docker / node / gh, and converge Playwright (pip package, Chromium browsers, system libraries) onto the pin (fail-loud, idempotent); `--now` is informational-only — the timer owns the weekly schedule, the flag only logs intent |
| `install` / `uninstall` | Install the systemd units and backfill the installed script copy **plus the installed pins file** / remove the units only (the installed copy and state dir — including audit history — are left in place) |
| `optout` / `optin` | Machine-wide opt-out via `/etc/sparkvm/toolset-update.optout` (or `TOOLSET_UPDATE_OPTOUT=1` in the environment) |
| `version` | Print the framework version |

The `os-security` layer ensures the `unattended-upgrades` package is present
and that `/etc/apt/apt.conf.d/20auto-upgrades` contains exactly the two
required lines (writes atomically via `install`; idempotent; supports
`--dry-run`).

## The `cua-driver` layer (issue #532)

The `cua-driver` layer enforces the version pin in the installed copy of
`scripts/self_update_pins.conf` (the canonical pin file per the
reconciliation contract; currently `cua-driver = 0.28.2`). On every
`update`:

- **No-op** when the installed `cua-driver` binary reports the pinned
  version — the common case, no network. The version probe senses **only**
  the managed binary (`$CUA_DRIVER_BIN --version`) and never `PATH`: the
  timer runs as root, so executing a `PATH`-resolved binary would invite
  `PATH` hijacking, and the layer converges `$CUA_DRIVER_BIN` — probing
  anything else would let a stray `PATH` copy mask drift of (or substitute
  for) the managed binary.
- On absence or drift, downloads the **exact pinned release asset** from
  `https://github.com/trycua/cua/releases/download` and installs it
  **atomically**: the SHA-256 digest is taken from the release's
  `checksums.txt` (exact filename match), `sha256sum -c` must pass, and the
  new binary is written to a staging path alongside the target then
  **renamed** over it — the live binary is never partially written.
- The tarball is **never executed and never extracted wholesale**: the
  member list is screened first — any symlink, hardlink, device, fifo,
  `..`, or absolute-path member refuses the whole update — and only the
  single `cua-driver` member is extracted (a same-channel tarball therefore
  cannot write outside the staging dir even if the release were tampered
  with).
- A missing pin, an unsafe pin (anything outside
  `[A-Za-z0-9._-]`, leading dot/dash, path separators), an unparseable
  installed version, a checksum mismatch, or a missing asset entry in
  `checksums.txt` all **fail closed**: `update` exits non-zero and the audit
  line names `cua-driver` as failed, leaving the existing binary untouched.
- **Never restarts the CUA daemon** — a running driver keeps working; the new
  binary takes effect on the next restart. Safe by default on live boxes.

Network trust boundary: the updater talks to GitHub release artifacts over
HTTPS (CA bundle as curl configures it) and treats `checksums.txt` as a
**corruption/mismatch detector, not publisher authentication** — it detects
a wrong or damaged artifact, it does not prove the release wasn't tampered
with at the source. A future slice can pin Sigstore signatures or
releases.attestation records. The tarball itself is never executed — but
note the installed artifact *is* executed by later runs' version probes
(`$CUA_DRIVER_BIN --version`, as the update user — root on the timer); that
exec lives inside the same accepted release-trust envelope as the install,
not outside it.

Overrides (environment): `PINS_FILE` (installed pins path),
`CUA_DRIVER_BIN` (default `/home/ntindle/cua/bin/cua-driver`),
`CUA_DRIVER_OWNER`/`CUA_DRIVER_GROUP` (default `ntindle`),
`CUA_RELEASE_BASE` (default `https://github.com/trycua/cua/releases/download`).

## The `apt` layer (issue #532)

The `apt` layer converges the toolset's **apt-based** defaults — docker
engine + compose, node/npm (nodesource), gh — to the newest versions the
box's apt sources offer, once a week, behind the idle gate. On every
`update`:

- **Detection is by installed package, never by PATH.** For each tool the
  layer holds a candidate package list (`docker-ce`, `docker-ce-cli`,
  `containerd.io`, `docker-compose-plugin`, `docker.io` for docker —
  covering boxes provisioned from Docker's own repo *and* from Ubuntu's;
  `nodejs` for node/npm; `gh` for gh) and upgrades only the candidates that
  are actually installed (`dpkg -l` status `ii`). A tool the box never
  provisioned simply no-ops — the layer installs nothing new.
- **Only the allowlisted names are passed to apt.** It is always
  `apt-get install --only-upgrade <names>` — never a bare `apt upgrade` —
  so unrelated packages and held packages are untouched.
- **Non-interactive by construction:** `-y`, `DEBIAN_FRONTEND=noninteractive`,
  and conffile `confdef`/`confold` (keep the box's existing config on
  conflicts — this runs unattended). Accepted tradeoff, stated here: `confold`
  silently skips upstream security-hardening conffile *defaults*, so a package
  that ships a tighter default config won't apply it until the operator
  intervenes. `--dry-run` maps to `apt-get -s
  install`, a true simulation that changes nothing.
- **List freshness comes from the `os-security` layer's daily refresh**
  (`unattended-upgrades` runs `apt-get update` daily) — the `apt` layer
  never runs `apt-get update` itself.
- A missing `apt-get`, a missing `dpkg`, or a failed upgrade all
  **fail closed**: `update` exits non-zero and the audit line names `apt`.
- **Service restarts are possible.** Maintainer scripts (e.g. `docker-ce`'s
  `dockerd` restart) may restart services — unlike the v0 layers, the `apt`
  layer does not promise otherwise. The protection is the **uid-aware idle
  gate** (defer while agent jobs are live, across agent uids) plus the
  weekly quiet-hours window.

Overrides (environment): `APT_DOCKER_PKGS` / `APT_NODE_PKGS` / `APT_GH_PKGS`
(space-separated candidate package names per tool).

## The `playwright` layer (issue #532)

The `playwright` layer converges Playwright onto the canonical pin
(`scripts/self_update_pins.conf`, `playwright = …` — the version the agent
smoke tests were validated against). One version governs three artifacts,
all locked together by the `playwright` package version:

1. the `playwright` **pip package** inside the managed venv (`$PLAYWRIGHT_VENV`,
   default `/home/ntindle/.venvs/pw`),
2. the **Chromium browser builds** (`playwright install chromium`),
3. the **system libraries** (apt packages).

- **Hash-pinned wheel, never a floating upgrade.** The layer downloads the
  wheel for the exact pin from the URL listed in the installed
  `playwright_wheel_hashes.txt` (installed/backfilled only by the
  privileged `install` step, next to the pins file — the update plane
  never reads it from the live checkout), SHA-256-verifies the download
  against the installed digest, and pip-installs the verified local file.
  pip performs no version selection at all; the pins file is the version
  authority, not PyPI's latest. The wheel filename is built from the pin
  and the box arch (`playwright-<pin>-py3-none-<platform>.whl`), so a pin
  bumped without its hash lines refuses fail-closed instead of falling
  back to a TLS-only fetch. The pip install is skipped when the venv is
  already on the pin — but the browser and system-library steps still run
  on every update: both are idempotent (`install` skips present builds;
  the deps step no-ops when nothing is missing), so an on-pin pip package
  with an emptied browser cache or missing system libraries still heals.
  Bump discipline: the hashes file is bumped in the same PR as the
  `playwright` pin (hashes recorded from PyPI's JSON API at commit time;
  the suite asserts every linux asset for the pinned version has exactly
  one well-formed hash line).
- **User-space work runs as the user.** The venv and the browser cache are
  owned by `$PLAYWRIGHT_USER` (default `ntindle`), so the pip install, the
  browser install, and the version probe all run as that user (via
  `runuser`/`sudo` when the timer runs as root) — a root-installed venv or
  root-owned `~/.cache/ms-playwright` would break the agent's own
  Playwright use.
- **Root never executes venv code.** The system-library step computes the
  missing-package list as the user (`install-deps --dry-run` — a read-only
  simulation via `apt-get install -s`, verified present in the pinned
  1.62.0 wheel), validates each reported name against the Debian
  package-name pattern (`^[a-z0-9][a-z0-9+.-]*$`), and root installs the
  validated names itself with `apt-get` (non-interactive, conffile
  keep-local, `--no-install-recommends`) from the box's configured,
  signature-verified apt sources — the same pipeline as the `apt` layer.
  List freshness comes from the `os-security` layer's daily refresh, like
  the `apt` layer; this step never runs `apt-get update` itself (note the
  real `install-deps` would — we deliberately don't call it).
- **The probe senses the managed venv only** — never PATH — so a stray
  PATH copy of Playwright cannot mask drift of the managed install (same
  rationale as the `cua-driver` layer's managed-binary probe), and it runs
  as `$PLAYWRIGHT_USER`, never as root: the probe executes the venv
  interpreter, which imports a user-writable package tree, so root must
  never run it directly.
- **Fail-closed:** a missing pin, an unsafe pin, a missing venv, an
  unparseable installed version, a missing `bin/playwright`, an
  impossible user-switch, a missing/stale/ambiguous wheel-hashes entry, a
  wheel hash mismatch, a failed wheel download, or any unexpected
  `--dry-run` output shape (wrong header, count mismatch, unsafe name,
  garbage) all refuse loudly and name `playwright` in the audit line.
- **Trust residual (stated, not hidden):** unlike the `cua-driver` layer's
  SHA-256-verified tarball and the wheel's SHA-256-verified download, the
  browser download is TLS-only with no hash pinning — `playwright install
  chromium` trusts the Playwright CDN and TLS (the build revision it
  fetches is still fully determined by the hash-verified package, so only
  a CDN serving different bytes for the same revision URL is unaddressed).
  pip's transitive dependencies (pyee, greenlet) are TLS-only too.
  Hash-pinning the browser archives is the remaining follow-up (see
  "Follow-ups"). What root executes is bounded to `apt-get` on validated
  names — the one new root-executed surface this layer adds.

Overrides (environment): `PLAYWRIGHT_VENV`, `PLAYWRIGHT_USER`.

## Trust model

- The systemd **timer runs the installed copy**
  (`/home/ntindle/.sparkvm-toolset/bin/toolset-update.sh`), not the repo
  checkout — a compromised or half-written checkout cannot inject code into
  the update path.
- Updates **defer while any agent job is live** (conservative idle gate);
  `--force` bypasses. The gate is uid-aware: for every user in
  `TOOLSET_AGENT_USERS` (default: `ntindle`) it probes that user's own tmux
  server for live `mjob-*` sessions *and* scans their muse-job registry
  (`~/muse-jobs/*/job.json`) for non-terminal job records
  (`active`/`blocked`; unrecognized states fail closed as busy). Both probes
  are read-only — tmux is asked only for session names, job records are
  parsed as data and never executed. An identity-switch failure defers
  loudly (fail-closed); a tmux probe that fails for other reasons (missing
  binary, broken server) reads as no-sessions for that half, with the
  registry probe as the independent backstop. The registry half is the
  v2-proof half: when the muse-job v2 cutover (issue #228) moves jobs off
  tmux, the registry keeps the same state contract and the gate keeps
  working. Residual: the gate is point-in-time — a job starting after the
  gate passes, or during the `apt` layer before a maintainer-script
  restart, is unprotected; the weekly quiet-hours window bounds this, and
  the service unit must not set `PrivateTmp=true` (the gate needs the real
  `/tmp` to see per-uid tmux sockets).
- The `os-security` repair **overwrites** `/etc/apt/apt.conf.d/20auto-upgrades`
  with exactly the two required lines. Any operator tuning in that file
  (e.g. `Unattended-Upgrade::Allowed-Origins`) is discarded on repair — on a
  fresh box the file holds exactly those lines, so this is normally a no-op.
  Merge-in-place of operator tuning is a follow-up slice; until then, put
  custom apt tuning in a separate file under `/etc/apt/apt.conf.d/`.
- Single-flight `flock`, `umask 077`, JSONL audit log plus a stable run log.
- Weekly Sunday 03:00 local quiet-hours schedule with a 30-minute randomized
  delay (`sparkvm-toolset-update.timer`, `Persistent=false`).
- Root-required operations fail loudly instead of silently skipping.
- **The only code fetched over the network is the `cua-driver` layer's
  pinned release fetch and the `playwright` layer's hash-pinned wheel
  download**, deliberately and narrowly: exactly three `curl` calls — the
  release's `checksums.txt` and the exact pinned tarball (both under
  `$CUA_RELEASE_BASE/cua-driver-rs-v<pin>/`), with SHA-256 verification
  against the release's own checksums file before anything is executed or
  installed (see "The `cua-driver` layer" for the fail-closed rules), and
  the playwright wheel (the URL listed for the pinned version + box arch
  in the installed `playwright_wheel_hashes.txt`), with SHA-256
  verification against the installed hash before pip ever sees the file
  (see "The `playwright` layer"). The package-manager call sites are the
  one-time `apt-get install -y unattended-upgrades` bootstrap (downloads
  from the box's configured, signature-verified apt sources, only if the
  package is missing) and the `apt` layer's weekly
  `apt-get install --only-upgrade <allowlisted names>` (same sources,
  never installs anything not already present). The `playwright` layer
  adds one `pip install <hash-verified local wheel>` call site (run as the
  venv-owning user; pip performs no version selection — no floating
  upgrade — and the wheel filename is built from the exact pin, so the
  pins file stays the version authority), one `playwright install
  chromium` browser fetch (run as the user), and one `apt-get install -y
  --no-install-recommends <validated names>` call site for the missing
  system libraries — the names come from `install-deps --dry-run`
  (read-only, run as the user) and are validated against the Debian
  package-name pattern before root installs them, so root never executes
  venv code. The browser fetch is TLS-only, no hash pinning — the
  documented residual; pip's transitive dependencies are TLS-only too.
  The suite pins exactly that shape — no `wget`/`git clone`/`npm
  install`, three `apt-get` call sites, three `curl` call sites, one
  hash-pinned-wheel `pip install` call site.

## Component status

`os-security` reports `ok` / `repair-needed`; `cua-driver` is enforced
against the installed pins file (on-pin, absent→install, drift→reinstall);
docker / node / gh are converged via the `apt` layer (installed packages
only); Playwright's pip package is held on the canonical pin while its
Chromium browser builds and system libraries converge every run (both
idempotent) via the `playwright` layer. npm rides with the nodesource
`nodejs` package.

## Failure freeze (issue #532)

**Status: shipped.** The toolset updater ships with the "freeze on
repeated failure" half of #532's Recovery section.

- Every **real** `update` run that fails (any layer returns nonzero,
  plus pre-layer hard failures like a missing `flock`) increments a
  consecutive-failure counter in `$TOOLSET_STATE_DIR/freeze.state`.
  After `TOOLSET_FREEZE_AFTER` consecutive failures (default: 3;
  non-numeric or zero values fall back to 3 with a loud log line) the
  box **freezes**: `update` refuses to run (exit 1, a loud log line, and
  an audit event) until an operator runs `toolset-update.sh unfreeze`
  after investigating — and `unfreeze` itself fails loudly (exit 1) if
  the state can't be persisted, so it never reports a recovery that
  didn't happen. No layer work runs while frozen — the box surfaces one
  "box needs attention" state instead of churning through doomed updates.
- The counter is fair: idle-gate and lock deferrals, `--dry-run` runs,
  and opt-outs never move it; a successful run resets it to 0. A corrupt
  or missing state file reads as clean (loudly) — the counter is
  availability bookkeeping, never a trust boundary, so it can never
  brick updates or freeze the box spuriously.
- `update --dry-run` is still permitted while frozen as a diagnostic: it
  changes nothing and never touches the counter.
- The freeze is machine-readable: `status` prints a `freeze` row
  (`frozen` with the since/reason detail, or `ok` with the current
  streak), so the future `spark-vm health` report inherits the signal.
  (Post-update health checks, when they land, feed the same counter —
  today the counter keys off update-run failures.)

## Snapshots and rollback (issue #532)

**Status: shipped.** No change without a rollback target.

- Before any layer changes the box, `update` takes one **pre-update
  snapshot** of everything the run will touch, under
  `$TOOLSET_STATE_DIR/snapshots/<UTC-timestamp>-<pid>-<random>/` with a per-layer
  `MANIFEST` (`FILE`/`ABSENT` lines mirroring
  `deploy/auto-deploy.sh`'s pattern, plus `STATE` lines carrying a
  pre-update package-version inventory). A failed snapshot fails the run
  loudly *before* anything changes — it feeds the failure-freeze counter
  like any infra failure. The newest `$TOOLSET_SNAPSHOT_KEEP` snapshots
  are retained (default 5).
- When a layer fails, its snapshot is **restored automatically** and the
  layer is **marked blocked** in `$TOOLSET_STATE_DIR/blocked.state`: the
  next tick skips that layer (loudly, with an audit event) instead of
  retry-looping the same failing convergence. The block key is what the
  layer was converging (the pin for pin-driven layers), so bumping the
  pin unblocks implicitly; `toolset-update.sh unblock [layer]` is the
  operator override. Other layers still run — layers are independent, so a
  failed `cua-driver` download never reverts a good `os-security` repair.
- `toolset-update.sh rollback [--layer <name>]` restores the newest
  snapshot by hand — the recovery-runbook entry point: read the `status`
  report, identify the bad layer, roll it back, verify, report.
- `status` gains two rows: `blocked` (`blocked` with layer/key/at
  detail, or `ok`) and `snapshots` (retained count + newest name), so the
  future `spark-vm health` report inherits both signals.
- Honest scope boundary: the `apt` and `playwright` layers converge
  dpkg/pip-owned package state that cannot be restored by copying files
  back. Their snapshot contribution is the pre-update version inventory
  (`STATE` lines) for the operator and the audit log — not a restore
  path. Recovering a bad `apt` upgrade is the operator's
  `apt-get install --only-upgrade` downgrade / `apt-get install -f`
  repair with the `STATE` inventory as the "what changed" record;
  recovering a bad `playwright` converge is
  `pip install playwright==<previous-pin>` (from the `STATE` line) as the
  venv-owning user, then `playwright install chromium`.

## Follow-ups (issue #532, not in this slice)

- Hash-pin the playwright browser archives — the remaining half of the
  TLS-only residual (the wheel half is hash-pinned: the layer downloads
  the pinned wheel from its hash-pinned URL and SHA-256-verifies it before
  pip installs the local file)
- Validate `APT_*_PKGS` candidates against the Debian package-name pattern
  (defense in depth against glob expansion / option injection via root-set
  env; currently the only setter with privilege is root, so no boundary is
  crossed today)
- Verify `needrestart`'s behavior under `DEBIAN_FRONTEND=noninteractive` on
  the target box (it can restart services beyond maintainer scripts)
- Status-plane wiring: consult `self_update.py` drift output when deciding
  what to update
- Post-update health checks and machine-readable health
- Agent recovery runbook
- Independent backup recovery entry point (outside the update system itself)

## Tests

`deploy/test_toolset_update.py` — 71 hermetic tests (stub PATH, real-tool
symlinks, no root assumptions). Wired into CI alongside the deploy tests.
