# Toolset update (`deploy/toolset-update.sh`)

**Status: v0 framework.** Partial implementation of issue #532 ("Self-update
system: keep the box and its default toolset current"). This slice ships the
framework — trust model, scheduling, audit, idle gate, opt-out — and one
real updater layer (`os-security`: unattended-upgrades). The remaining
#532 slices (component updaters, snapshots/rollback, failure freeze,
independent backup path) are explicitly follow-ups. Reconciled with #542's
read-only status plane — this script is the *update* plane; see
"Two planes" in `docs/SELF_UPDATE.md` for the canonical architecture.

## What it does

`deploy/toolset-update.sh` keeps a spark-vm box's **default toolset** current:
the OS security pipeline plus status probes for the tools provisioned by
default (docker, node, npm, gh, Playwright, cua-driver). Scope is
deliberately **provisioned defaults, not user-installed tools**.

Commands:

| Command | Effect |
| ------- | ------ |
| `status` | TSV per-component *update state* (`ok` / `repair-needed` for `os-security`; `present` / `absent` for layers without an updater yet); operator-readable, no root needed. For installed-version drift against the pin list, read the status plane instead: `python3 scripts/self_update.py status` (see "Two planes" in `docs/SELF_UPDATE.md`) |
| `update [--force] [--dry-run] [--now]` | Repair `os-security` (fail-loud, idempotent); `--now` is informational-only in v0 — the timer owns the weekly schedule, the flag only logs intent |
| `install` / `uninstall` | Install the systemd units and backfill the installed script copy / remove the units only (the installed copy and state dir — including audit history — are left in place) |
| `optout` / `optin` | Machine-wide opt-out via `/etc/sparkvm/toolset-update.optout` (or `TOOLSET_UPDATE_OPTOUT=1` in the environment) |
| `version` | Print the framework version |

The `os-security` layer is the only real updater in v0. It ensures the
`unattended-upgrades` package is present and that
`/etc/apt/apt.conf.d/20auto-upgrades` contains exactly the two required
lines (writes atomically via `install`; idempotent; supports `--dry-run`).

## Trust model

- The systemd **timer runs the installed copy**
  (`/home/ntindle/.sparkvm-toolset/bin/toolset-update.sh`), not the repo
  checkout — a compromised or half-written checkout cannot inject code into
  the update path.
- Updates **defer while any `mjob-*` tmux session exists** (conservative idle
  gate); `--force` bypasses. **Known limitation:** tmux sockets are per-uid,
  so the gate (running as root) only sees root's tmux server — `mjob-*`
  sessions owned by another uid (e.g. `ntindle`) are invisible to it, and a
  missing/broken tmux probe also reads as "no jobs". In v0 this is acceptable
  because `update` never restarts services or installs packages itself — it
  only rewrites the apt config — but the gate must not be relied on as a hard
  exclusion until it is made uid-aware (follow-up slice).
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
- **v0 makes no network fetch or download calls** — the suite pins this.

## Component status (v0)

Only `os-security` reports `ok` / `repair-needed`. Docker, node, npm, gh,
playwright, and cua-driver are **status probes only** (`present` / `absent`)
until their updater layers land.

## Follow-ups (issue #532, not in this slice)

- Real updater layers for docker / node / npm / gh / Playwright / cua-driver
  (adopt `scripts/self_update_pins.conf` as the canonical pin file per the
  reconciliation contract in `docs/SELF_UPDATE.md` "Two planes")
- Status-plane wiring: consult `self_update.py` drift output when deciding
  what to update
- Pre-update snapshots and rollback
- Post-update health checks and machine-readable health
- Repeated-failure freeze and blocking
- Agent recovery runbook
- Independent backup recovery entry point (outside the update system itself)

## Tests

`deploy/test_toolset_update.py` — 27 hermetic tests (stub PATH, real-tool
symlinks, no root assumptions). Wired into CI alongside the deploy tests.
