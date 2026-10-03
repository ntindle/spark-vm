# Toolset update (`deploy/toolset-update.sh`)

**Status: framework + four real layers.** Partial implementation of issue
#532 ("Self-update system: keep the box and its default toolset current").
This ships the framework — trust model, scheduling, audit, idle gate,
opt-out — and four real updater layers: `os-security`
(unattended-upgrades), `cua-driver` (pinned reinstall from the upstream
GitHub release), `apt` (docker / node / gh converged via apt), and
`playwright` (pinned pip package + Chromium browser builds + system
libraries). The remaining #532 slices (snapshots/rollback, failure
freeze, independent backup path) are explicitly follow-ups. Reconciled with
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
  layer does not promise otherwise. The protection is the **idle gate**
  (defer while agent jobs are live) plus the weekly quiet-hours window; the
  gate's known blind spots (per-uid tmux sockets) are now load-bearing for
  this layer, and making the gate uid-aware is the follow-up that tightens
  it.

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

- **Exact pin, never a floating upgrade.** The specifier is always
  `playwright==<pin>`; the pins file is the version authority, not PyPI's
  latest. The pip install is skipped when the venv is already on the pin —
  but the browser and system-library steps still run on every update: both
  are idempotent (`install` skips present builds; the deps step no-ops
  when nothing is missing), so an on-pin pip package with an emptied
  browser cache or missing system libraries still heals.
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
  rationale as the `cua-driver` layer's managed-binary probe).
- **Fail-closed:** a missing pin, an unsafe pin, a missing venv, an
  unparseable installed version, a missing `bin/playwright`, an
  impossible user-switch, or any unexpected `--dry-run` output shape
  (wrong header, count mismatch, unsafe name, garbage) all refuse loudly
  and name `playwright` in the audit line.
- **Trust residual (stated, not hidden):** unlike the `cua-driver` layer's
  SHA-256-verified tarball, the pip install and the browser download are
  TLS-only with no hash pinning — `pip install playwright==<pin>` trusts
  PyPI's index and TLS, `playwright install chromium` trusts the Playwright
  CDN and TLS. Hash-pinning the wheel and the browser archives is the
  follow-up slice that closes this (see "Follow-ups"). What root executes
  is bounded to `apt-get` on validated names — the one new root-executed
  surface this layer adds.

Overrides (environment): `PLAYWRIGHT_VENV`, `PLAYWRIGHT_USER`.

## Trust model

- The systemd **timer runs the installed copy**
  (`/home/ntindle/.sparkvm-toolset/bin/toolset-update.sh`), not the repo
  checkout — a compromised or half-written checkout cannot inject code into
  the update path.
- Updates **defer while any `mjob-*` tmux session exists** (conservative idle
  gate); `--force` bypasses. **Known limitation:** tmux sockets are per-uid,
  so the gate (running as root) only sees root's tmux server — `mjob-*`
  sessions owned by another uid (e.g. `ntindle`) are invisible to it, and a
  missing/broken tmux probe also reads as "no jobs". The blind gate was
  acceptable for the v0 layers (they never restarted services), but the `apt`
  layer can trigger maintainer-script service restarts — the gate plus the
  weekly quiet-hours window are the protection there, so making the gate
  uid-aware is now a real follow-up rather than hygiene (see "Follow-ups").
  The muse-job v2 cutover (issue #228 — jobs move off tmux entirely) will
  blind the tmux-only gate permanently, so the uid-aware/registry-check
  follow-up must land before or with v2.
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
  pinned release fetch**, deliberately and narrowly: exactly two `curl`
  calls (the release's `checksums.txt` and the exact pinned tarball, both
  under `$CUA_RELEASE_BASE/cua-driver-rs-v<pin>/`), with SHA-256 verification
  against the release's own checksums file before anything is executed or
  installed — see "The `cua-driver` layer" for the fail-closed rules. The
  package-manager call sites are the one-time
  `apt-get install -y unattended-upgrades` bootstrap (downloads from the
  box's configured, signature-verified apt sources, only if the package is
  missing) and the `apt` layer's weekly
  `apt-get install --only-upgrade <allowlisted names>` (same sources, never
  installs anything not already present). The `playwright` layer adds one
  `pip install playwright==<pin>` call site (exact pin only, run as the
  venv-owning user), one `playwright install chromium` browser fetch (run
  as the user), and one `apt-get install -y --no-install-recommends
  <validated names>` call site for the missing system libraries — the
  names come from `install-deps --dry-run` (read-only, run as the user)
  and are validated against the Debian package-name pattern before root
  installs them, so root never executes venv code. The pip install and the
  browser fetch are TLS-only, no hash pinning — the documented residual.
  The suite pins exactly that shape — no `wget`/`git clone`/`npm install`,
  three `apt-get` call sites, two `curl` call sites, one exact-pin `pip
  install` call site.

## Component status

`os-security` reports `ok` / `repair-needed`; `cua-driver` is enforced
against the installed pins file (on-pin, absent→install, drift→reinstall);
docker / node / gh are converged via the `apt` layer (installed packages
only); Playwright's pip package is held on the canonical pin while its
Chromium browser builds and system libraries converge every run (both
idempotent) via the `playwright` layer. npm rides with the nodesource
`nodejs` package.

## Follow-ups (issue #532, not in this slice)

- Hash-pin the playwright wheel and browser archives (`--require-hashes`
  / Sigstore) — closes the TLS-only residual of the `playwright` layer's
  pip install and browser fetch
- Make the idle gate uid-aware (it now protects the `apt` layer's
  service-restart surface, not just hygiene); land before/with the muse-job
  v2 cutover (#228), which blinds the tmux-only probe permanently
- Validate `APT_*_PKGS` candidates against the Debian package-name pattern
  (defense in depth against glob expansion / option injection via root-set
  env; currently the only setter with privilege is root, so no boundary is
  crossed today)
- Verify `needrestart`'s behavior under `DEBIAN_FRONTEND=noninteractive` on
  the target box (it can restart services beyond maintainer scripts)
- Status-plane wiring: consult `self_update.py` drift output when deciding
  what to update
- Pre-update snapshots and rollback
- Post-update health checks and machine-readable health
- Repeated-failure freeze and blocking
- Agent recovery runbook
- Independent backup recovery entry point (outside the update system itself)

## Tests

`deploy/test_toolset_update.py` — 70 hermetic tests (stub PATH, real-tool
symlinks, no root assumptions). Wired into CI alongside the deploy tests.
