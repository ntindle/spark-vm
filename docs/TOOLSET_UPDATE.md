# Toolset update (`deploy/toolset-update.sh`)

**Status: v0 framework.** Partial implementation of issue #532 ("Self-update
system: keep the box and its default toolset current"). This slice ships the
framework — trust model, scheduling, audit, idle gate, opt-out — and one
real updater layer (`os-security`: unattended-upgrades). The remaining
#532 slices (component updaters, snapshots/rollback, failure freeze,
independent backup path) are explicitly follow-ups.

## What it does

`deploy/toolset-update.sh` keeps a spark-vm box's **default toolset** current:
the OS security pipeline plus status probes for the tools provisioned by
default (docker, node, npm, gh, Playwright, cua-driver). Scope is
deliberately **provisioned defaults, not user-installed tools**.

Commands:

| Command | Effect |
| ------- | ------ |
| `status` | TSV per-component state (`ok` / `repair-needed` / `probe-only` / `unknown`); operator-readable, no root needed |
| `update [--force] [--dry-run] [--now]` | Repair `os-security`, then report component states; no actual component updates yet (v0) |
| `install` / `uninstall` | Install the systemd units and backfill the installed script copy |
| `optout` / `optin` | Machine-wide opt-out via `/etc/sparkvm/toolset-update.optout` |
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
  gate); `--force` bypasses.
- Single-flight `flock`, `umask 077`, JSONL audit log plus a stable run log.
- Weekly Sunday 03:00 local quiet-hours schedule with a 30-minute randomized
  delay (`sparkvm-toolset-update.timer`, `Persistent=false`).
- Root-required operations fail loudly instead of silently skipping.
- **v0 makes no network fetch or download calls** — the suite pins this.

## Component status (v0)

Only `os-security` reports `ok` / `repair-needed`. Docker, node, npm, gh,
playwright, and cua-driver are **status probes only** (`probe-only`) until
their updater layers land.

## Follow-ups (issue #532, not in this slice)

- Real updater layers for docker / node / npm / gh / Playwright / cua-driver
- Pre-update snapshots and rollback
- Post-update health checks and machine-readable health
- Repeated-failure freeze and blocking
- Agent recovery runbook
- Independent backup recovery entry point (outside the update system itself)

## Tests

`deploy/test_toolset_update.py` — 19 hermetic tests (stub PATH, real-tool
symlinks, no root assumptions). Wired into CI alongside the deploy tests.
