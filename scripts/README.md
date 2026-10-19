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
changes count as code), docs index coverage, shellcheck severity=error over
the CI job's shell-file selection on the whole checkout (like CI's
standalone job — no docs-only carve-out), then the full test suite — stopping at the first
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
shellcheck (severity=error, CI job selection)
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

## Demo assets: `demo_confirmd.py` / `generate_demo_assets.py` / `pw-test.py` / `png-smoke.sh`

`generate_demo_assets.py` builds the marketing/demo visuals (needs
Playwright + Chromium; browser versions are pinned in
`playwright_browser_hashes.txt` / `playwright_wheel_hashes.txt`).
`demo_confirmd.py` runs confirmd with demo-only overrides (the
tailnet-identity auth gate is bypassed because the demo camera is
localhost). `pw-test.py` takes a screenshot; `png-check.py` asserts it's
a real PNG. `png-smoke.sh` is the one-command entry point for the
screenshot smoke test: with the CONTRIBUTING.md venv activated it
installs the pinned playwright (`self_update_pins.conf`) into the venv
if needed, installs the Chromium browser, then runs `pw-test.py` +
`png-check.py` — the same scripts CI's `png-check` job runs, against
the same pin (`./scripts/png-smoke.sh --plan` prints the steps;
`--with-deps` forwards to `playwright install` for OS deps).

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
  `test_ci_md_suite_inventory.py` / `test_pytest_ini_covers_all.py` /
  `test_contributing_venv.py` —
  the contributor guide's check list and every test suite stay wired to
  what CI and `pytest.ini` actually enumerate; the venv pin keeps
  CONTRIBUTING's venv-first install instructions from drifting.
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
| `test_ci_job_timeouts.py` | CI workflow job `timeout-minutes` pins (issue #1367) |
| `test_ci_linkcheck_retry.py` | `markdown-links` job retry wiring (`LYCHEE_ARGS` + fail-gate) |
| `test_ci_docs_job_inventory.py` | CI job inventory (`docs/CI.md` job table ↔ `ci.yml` job ids) |
| `test_ci_md_link_excludes.py` | `docs/CI.md` link-check exclusion inventory |
| `test_ci_md_suite_inventory.py` | CI python-tests suite inventory |
| `test_ci_shard_plan.py` | CI shard plan ↔ real suite bijection |
| `test_contributing_ci_gates.py` | `CONTRIBUTING.md` merge-gate check list |
| `test_contributing_suites.py` | `CONTRIBUTING.md` test-suite inventory |
| `test_contributing_venv.py` | `CONTRIBUTING.md` venv-first install instructions |
| `test_credential_vend_contract.py` | CREDENTIAL_VEND_CONTRACT.md security pins (#1401/#1402/#1403) |
| `test_cut_release.py` | `cut-release.sh` release tooling |
| `test_deploy_gate_tests_coverage.py` | `deploy/components.conf` gate test-file registration |
| `test_docs_index_coverage.py` | `docs/` index coverage |
| `test_frontdoor_deploy.py` | sparkvm.dev front-door deploy (H28) |
| `test_funnel_metrics.py` | `funnel_metrics.py` waitlist funnel queries |
| `test_hosted_owner_alerting_doc.py` | HOSTED_OWNER_ALERTING.md alert classes ↔ push-lane mapping surface |
| `test_http_hardening_headers.py` | localhost HTTP hardening-header pin test (issue #1237) |
| `test_install_sh.py` | `install.sh` idempotent box installer: sourcing safety, per-step skip/mutate idempotency, no-op second run, README no-drift (issue #1526) |
| `test_install_sh_update.py` | `install.sh --update` tag-to-tag updater: flag contracts, identity gate, real-git move, fail-closed edges (dirty/downgrade/non-versioned), dry-run (issue #1611) |
| `test_lint_changelog_ritual.py` | changelog ritual linter |
| `test_local_gate.py` | `local-gate.sh` merge-gate runner |
| `test_parallel_runner_docs.py` | CONTRIBUTING.md + docs/CI.md parallel-runner docs + pytest-xdist dependency |
| `test_png_smoke.py` | `png-smoke.sh` PNG smoke runner + CI `png-check` playwright pin |
| `test_pytest_ini_covers_all.py` | `pytest.ini` testpaths reachability |
| `test_pytest_warning_hygiene.py` | test-output hygiene: no invalid escapes / no bytes env writes |
| `test_push_lane_decision_numbers.py` | push-lane D-series decision-number uniqueness |
| `test_push_pull_scan.py` | `push.sh` secret scan + `pull.sh` CLI contract |
| `test_readme_inventories.py` | this README's gate-steps + test inventory (this table) |
| `test_readme_test_count_pins.py` | README/docs "(N tests)" claims ↔ test-file function counts |
| `test_readme_layout_paths.py` | README repo-layout table path existence + file/dir kind |
| `test_relay_wiring_tick_doc.py` | wiring-tick operator doc pins (CLI flags/report keys/exit codes/verbatim notes vs `hosted/relay_tenant_wiring.py`) |
| `test_sentinel_s2_doc.py` | SENTINEL_TELEMETRY_SURFACES.md S2 row ↔ swap.log writer shapes |
| `test_self_update.py` | `self_update.py` read-only toolset inventory |
| `test_site_branding.py` | `site/` brand-logo assets + wiring (issue #852) |
| `test_sparkvm_version.py` | `sparkvm_version.py` version reader |
| `test_waitlist_invites.py` | `site/waitlist_invites.py` + waitlistd invite additions (H15) |
| `test_waitlist_jobs.py` | `site/waitlist_jobs.py` + waitlistd lifecycle additions (H15) |
| `test_waitlist_page.py` | waitlist page build slice (`site/`) |
| `test_waitlist_patha.py` | `site/waitlist_patha.py` + waitlistd path-A additions (H15) |
| `test_waitlistd.py` | `site/waitlistd.py` daemon (H15) |
| `test_workflow_action_pins.py` | GitHub Actions SHA-pin inventory across `.github/workflows/` |
