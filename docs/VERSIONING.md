# Versioning and releases

spark-vm has one version, and it lives in one place: the `VERSION` file at the
repo root. Everything long-lived reports it, so an operator can always answer
"which release is actually deployed?" — from the journal, the approval page,
or the updater's own audit log.

## The single source of truth

`VERSION` holds a strict semantic version (`MAJOR.MINOR.PATCH`, optional
`-prerelease` / `+build`), e.g. `0.1.0`. The project is pre-1.0: `MINOR`
bumps for new capabilities, `PATCH` bumps for fixes and hardening, `MAJOR`
stays 0 until the hosted product's public contract freezes.

`scripts/sparkvm_version.py` is the only reader:

- `sparkvm_version(start)` — walk up from `start` (a component directory) to
  find a `VERSION` file; return it, or `"0.0.0-unknown"` on any problem. Never
  raises, never breaks a component's startup.
- `sparkvm_version_strict(start)` — same, but raises `ValueError` when VERSION
  is missing or not valid semver. Tests and CI use this.
- `python3 scripts/sparkvm_version.py --check` — exit 0 and print the version,
  or exit 1 on a bad VERSION. Run this in CI gates that touch releases.

## What reports the version

| Component | How it reports |
|---|---|
| `confirm/confirmd.py` | prints `confirmd version=<v>` at startup; `GET /api/version` (same auth gate as the pages) returns `{"service":"confirmd","version":<v>,"handler":"confirmd/1"}` |
| `proxy/swap_addon.py` | logs `swap_addon: spark-vm version <v>` at addon load (journal) |
| `cred-ui/cred-ui.py` | prints `cred-ui version=<v>` at startup; `GET /api/version` returns `{"service":"cred-ui","version":<v>}` |
| `muse-job/bin/muse-job` | `muse-job --version` prints `<v>` |
| `deploy/auto-deploy.sh` | `auto-deploy.sh status` prints the deployed version; every `deploy` audit line carries `to_version` / `from_version`; the deployed version is persisted in `$UPDATER_STATE_DIR/deployed-version` (atomically, like the watermark) |

Each Python component bootstraps the reader with a small snippet (see the top
of `confirm/confirmd.py`): it puts `scripts/` (repo layout) or its own
directory (deployed standalone layout, e.g. `/home/swapd`) on `sys.path`,
imports `sparkvm_version`, and falls back to `"0.0.0-unknown"` if anything
goes wrong.

## How the deployed standalone files get the version

`swap_addon.py` and `confirmd.py` are deployed as standalone copies to
`/home/swapd/` by `proxy/deploy.sh` — they do not see the repo checkout.
`proxy/deploy.sh` therefore also installs:

- `VERSION` → `/home/swapd/VERSION`
- `scripts/sparkvm_version.py` → `/home/swapd/sparkvm_version.py`

Both are listed in `deploy/components.conf` (`proxy_install_paths`), so the
auto-deployer's rollback snapshots cover them: a rollback restores the old
VERSION alongside the old code.

A version-only change (bumping `VERSION` with no component edits) is claimed
by the `proxy` component as an exact-file path (`"VERSION"` in
`proxy_paths`). Bare (non-`/`-suffixed) entries match exactly — `docs/
VERSIONING.md` does **not** match — so the updater redeploys the
proxy-confirm unit and the new version takes effect. `cred-ui` runs from the
working checkout and sees `VERSION` directly; `muse-job --version` reads the
repo file.

## Cutting a release

1. Bump `VERSION` on `main` (one commit, message like `release: bump VERSION
   to 0.2.0`). Keep the change version-only so the auto-deployer treats it as
   a version bump and nothing else.
2. Tag the commit: `git tag v0.2.0 && git push origin v0.2.0`.
3. The auto-deployer's next tick sees the `VERSION` change, redeploys the
   proxy-confirm unit, and records `to_version` in its audit log.
4. Verify: `auto-deploy.sh status` shows the new version; `confirmd`'s journal
   and `/api/version` agree.

Never hand-edit `/home/swapd/VERSION` or the deployed copies — they are
deployment outputs. If they disagree with the updater's `deployed-version`
state, the updater's audit log is the record of what happened; fix the
process, not the files.
