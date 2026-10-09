# scripts/ — operator and contributor tooling

The helper scripts that keep the project running: the local merge gate,
release tooling, repo sync, the self-update probes, governance application,
demo assets, and the CI pin tests that keep the project's contribution
rituals honest.

## The merge gate: `local-gate.sh`

[`CONTRIBUTING.md`](../CONTRIBUTING.md)'s "merge gate, locally" section
points here. One command runs the six locally-replicable CI checks in
order — the shard-plan check, the changelog ritual lint, the changed-paths
evaluation (docs-only diffs skip the test suite like CI does; uncommitted
changes count as code), docs index coverage, shellcheck severity=error on
changed `*.sh` files, then the full test suite — stopping at the first
failure. (CI's merge gate is eight checks; the two the script can't run —
the markdown link check and the PNG screenshot smoke test — are named in
its output, not run.)

The exact step names the gate prints, in run order (the machine-readable
inventory, pinned against `local-gate.sh`'s `step "..."` calls by
`test_readme_inventories.py` — a step renamed in the script must be
renamed here, and order is contractual: the test compares the ordered
list, so a deliberate reorder or a seventh step updates both the block
and the pin):

<!-- gate-steps:start -->
shard plan
changelog ritual lint
changed-paths gate
docs index coverage
shellcheck (severity=error, changed *.sh)
python tests
<!-- gate-steps:end -->

```bash
./scripts/local-gate.sh           # everything
./scripts/local-gate.sh --quick   # cheap checks only, no suite
./scripts/local-gate.sh --plan    # print the steps without running them
```

## Repo sync: `push.sh` / `pull.sh`

`push.sh` stages all changes, scans them for secret-shaped values, commits,
and pushes `origin HEAD` **through the credential-swapping proxy**
([`proxy/`](../proxy/README.md)): `hsurr:github` in the `Authorization`
header is swapped for the real token on the wire, so the token never
appears in the script, the environment, or any log. `pull.sh` is the same
shape for fetches. Both accept `--dry-run`.

## Release: `cut-release.sh` / `sparkvm_version.py`

`sparkvm_version.py` is the single-source version reader: every long-lived
component reports the `VERSION` file's value at startup so an operator can
tell which release is actually deployed. It never raises on a bad `VERSION`
file (yields `0.0.0-unknown` instead of breaking startup); the strict
variant fails loudly for tests and CI. `cut-release.sh` is the operator
half of release automation — the release workflow calls it in `--ci` mode
when `VERSION` changes on main.

## Self-update: `self_update.py`

The spark-vm self-update, currently slice S1 (read-only toolset inventory,
issue #532): `self_update.py status` reports each in-scope tool's installed
version against the known-good pins in `self_update_pins.conf`.
Read-only by construction — probes only run `--version`-style commands and
read config files; no installs, no writes, no sudo, no network. The
roadmap (update execution, systemd timer, backfill installer) is in
[docs/SELF_UPDATE.md](../docs/SELF_UPDATE.md).

## Governance: `apply-rulesets.sh` / `ruleset-normalize.jq`

`apply-rulesets.sh` applies the repo's branch/tag protection rulesets to
the live repo state (see `deploy/rulesets/`). Applying rulesets is an
owner decision; this script just makes the decision, once made, a single
command.

## Demo assets: `demo_confirmd.py` / `generate_demo_assets.py` / `pw-test.py`

`generate_demo_assets.py` builds the marketing/demo visuals (needs
Playwright + Chromium; browser versions are pinned in
`playwright_browser_hashes.txt` / `playwright_wheel_hashes.txt`).
`demo_confirmd.py` runs confirmd with demo-only overrides (the
tailnet-identity auth gate is bypassed because the demo camera is
localhost). `pw-test.py` takes a screenshot; `png-check.py` asserts it's
a real PNG.

## Funnel metrics: `funnel_metrics.py`

Reads a JSONL export of the waitlist operator store's `funnel_events`
table and prints the day-1 operator query pack: the primary
page-conversion metric plus the secondary, interim, and diagnostic
numbers the funnel docs prescribe.

## Bounded HTTP: `bounded_http.py`

`BoundedThreadingHTTPServer` — the bounded variant of
`http.server.ThreadingHTTPServer` used by spark-vm's HTTP daemons
(confirmd, cred-ui, waitlistd). A plain threading server spawns one thread
per connection, so a peer that opens connections and never finishes them
is a resource-exhaustion vector; this one caps it.

## The pin tests: `test_*.py`

These are the regression net for the tooling itself — and the tests that
keep the project's contribution rituals from drifting:

- `test_local_gate.py` — pins the merge-gate script's behavior.
- `test_contributing_ci_gates.py` / `test_contributing_suites.py` /
  `test_ci_md_suite_inventory.py` / `test_pytest_ini_covers_all.py` —
  the contributor guide's check list and every test suite stay wired to
  what CI and `pytest.ini` actually enumerate.
- `test_ci_shard_plan.py` — the shard inventory
  (`ci_shard_plan.py` — the single source CI's `python-tests` matrix
  fans out from) is a bijection with the real suite.
- `test_docs_index_coverage.py` — every doc under `docs/` is linked from
  `docs/README.md`.
- `test_lint_changelog_ritual.py` / `test_ci_md_link_excludes.py` —
  pin the changelog linter and the markdown link-check's exclusion list.
- The rest pin specific scripts (`cut-release`, `self-update`,
  `funnel_metrics`, `sparkvm_version`, the waitlist page/jobs/invites,
  `bounded_http`, the front-door deploy).

Run from the repo root: `python3 -m pytest` (see `pytest.ini` for the
suite inventory — CI runs exactly this).

### Test-file inventory

Every `test_*.py` in this directory, with the subject it pins. This table
is machine-checked by `test_readme_inventories.py`: a new test file must
be added here (contributors), so the README's map of the pin tests can
never drift from what's on disk.

| test file | pins |
|---|---|
| `test_apply_rulesets.py` | rulesets-as-code deliverables (issue #174) |
| `test_basename_uniqueness.py` | repo-wide test-file basename uniqueness (pytest import contract) |
| `test_bounded_http.py` | `bounded_http.py` bounded threading server |
| `test_ci_md_link_excludes.py` | `docs/CI.md` link-check exclusion inventory |
| `test_ci_md_suite_inventory.py` | CI python-tests suite inventory |
| `test_ci_shard_plan.py` | CI shard plan ↔ real suite bijection |
| `test_contributing_ci_gates.py` | `CONTRIBUTING.md` merge-gate check list |
| `test_contributing_suites.py` | `CONTRIBUTING.md` test-suite inventory |
| `test_cut_release.py` | `cut-release.sh` release tooling |
| `test_deploy_gate_tests_coverage.py` | `deploy/components.conf` gate test-file registration |
| `test_docs_index_coverage.py` | `docs/` index coverage |
| `test_frontdoor_deploy.py` | sparkvm.dev front-door deploy (H28) |
| `test_funnel_metrics.py` | `funnel_metrics.py` waitlist funnel queries |
| `test_lint_changelog_ritual.py` | changelog ritual linter |
| `test_local_gate.py` | `local-gate.sh` merge-gate runner |
| `test_pytest_ini_covers_all.py` | `pytest.ini` testpaths reachability |
| `test_readme_inventories.py` | this README's gate-steps + test inventory (this table) |
| `test_self_update.py` | `self_update.py` read-only toolset inventory |
| `test_site_branding.py` | `site/` brand-logo assets + wiring (issue #852) |
| `test_sparkvm_version.py` | `sparkvm_version.py` version reader |
| `test_waitlist_invites.py` | `site/waitlist_invites.py` + waitlistd invite additions (H15) |
| `test_waitlist_jobs.py` | `site/waitlist_jobs.py` + waitlistd lifecycle additions (H15) |
| `test_waitlist_page.py` | waitlist page build slice (`site/`) |
| `test_waitlist_patha.py` | `site/waitlist_patha.py` + waitlistd path-A additions (H15) |
| `test_waitlistd.py` | `site/waitlistd.py` daemon (H15) |
