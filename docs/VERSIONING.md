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
goes wrong — the import is wrapped in a broad `except Exception` because the
stamp is explicitly best-effort and must never break a component's startup.

Limitation: `muse-job --version` reports the real version only when run from a
repo checkout. A copy installed elsewhere (e.g. `~/bin/muse-job`) has neither
`scripts/` nor a sibling `VERSION` to resolve, so it prints `0.0.0-unknown`.
The daemons and the updater — the parts the version story is for — are
unaffected.

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
by the `proxy` AND `cred-ui` components as an exact-file path (`"VERSION"`
in `proxy_paths` and `cred_ui_paths`). Bare (non-`/`-suffixed) entries match
exactly — `docs/VERSIONING.md` does **not** match — so the updater redeploys
the proxy-confirm unit plus cred-ui and the new version takes effect
everywhere. (Exact-file entries may be claimed by more than one component;
directory prefixes still must not overlap — see `test_manifest_no_path_overlap`.)
When cred-ui's checkout subtree is synced, the root `VERSION` file travels
with it, and rollback snapshots cover it: a rollback restores the old
VERSION alongside the old code, so cred-ui never reports a version newer
than its own checkout. `muse-job --version` reads the repo file.

## Cutting a release

1. Bump `VERSION` on `main` (one commit, message like `release: bump VERSION
   to 0.2.0`). Keep the change version-only so the auto-deployer treats it as
   a version bump and nothing else — except `CHANGELOG.md`, when it exists
   (the changelog ritual): in the same commit, move the `## [Unreleased]`
   section into `## [0.2.0] - YYYY-MM-DD` (pattern: `## [x.y.z] -
   YYYY-MM-DD`), add the tag-compare link at the bottom of the changelog,
   and leave a fresh empty `## [Unreleased]` section behind for the next PR
   (the ritual is documented at the top of `CHANGELOG.md`). The release
   script uses the changelog section when present and falls back to the
   merged-PR list when it isn't.
2. Push to `main`. The release workflow (`.github/workflows/release.yml`)
   fires on any push that touches `VERSION` and cuts the release
   automatically: it runs `scripts/cut-release.sh --ci`, which preflights
   (on main, clean tree, strict semver, HEAD == origin/main, tag `vX.Y.Z`
   absent everywhere, and VERSION newer than every existing release tag),
   assembles the release notes from the changelog section plus the
   merged-PR list since the previous tag, creates the annotated tag (tags
   are never moved or re-cut), and publishes the GitHub release. Semver
   prereleases (`-rc.1`) are marked prerelease on GitHub. Merging to main
   is the release authorization — treat VERSION bumps like releases in
   review, and consider a GitHub tag-protection ruleset for `v*` so only
   the workflow can create release tags. Note: if two VERSION bumps land
   in quick succession, the superseded run fails its in-sync preflight by
   design — only the latest VERSION gets a release.
3. Manual path: `scripts/cut-release.sh` (dry-run by default — prints the
   plan and the notes draft, changes nothing); `cut-release.sh --execute
   --yes` cuts it by hand. It publishes via `gh`, or the GitHub API with
   `$GITHUB_TOKEN` when `gh` is unavailable. If `--execute` pushes the tag
   but publishing fails, recover with `cut-release.sh --publish-only
   --yes` — it regenerates the notes and publishes the release for the
   existing tag (refuses when the tag is missing or a release already
   exists).
4. The auto-deployer's next tick sees the `VERSION` change, redeploys the
   proxy-confirm unit plus cred-ui, and records `to_version` in its audit log.
   The deployed version now maps to a release tag: the release notes carry
   the full commit SHA, so `auto-deploy.sh status` output can be matched to
   a release in one hop.
5. Verify: `auto-deploy.sh status` shows the new version; `confirmd`'s journal
   and `/api/version`, and cred-ui's `/api/version`, all agree.

Never hand-edit `/home/swapd/VERSION` or the deployed copies — they are
deployment outputs. If they disagree with the updater's `deployed-version`
state, the updater's audit log is the record of what happened; fix the
process, not the files.
