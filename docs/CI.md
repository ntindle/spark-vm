# CI

`.github/workflows/ci.yml` runs on every push to `main`, every pull request
against `main`, and on manual `workflow_dispatch` runs.

| Job | What it runs |
|---|---|
| `changes` | Changed-paths gate: one-step `git diff --no-renames --name-only` against the PR base. `code_changed` is true when any file outside `docs/` + `CHANGELOG.md` changed; on push / `workflow_dispatch` it defaults true. `python-tests` runs only when `code_changed` is true, so docs-only PRs skip the ~40-min suite (the other five jobs are the docs-only merge gate; a skipped required check is neutral and does not block merging). |
| `python-tests` | The repo-root one-liner `python3 -m pytest -q` — `pytest.ini`'s `testpaths` is the authoritative suite inventory (one directory per component; the per-component breakdown with dependency notes lives in CONTRIBUTING.md's "Running the tests" table, which `scripts/test_contributing_suites.py` pins to `testpaths` so it can't drift). Installs `shellcheck` via apt first — `test_auto_deploy.py::test_scripts_syntax` gates on shellcheck *warnings* and must not depend on whatever the runner image happens to carry. |
| `docs-guard` | `scripts/test_docs_index_coverage.py`: every `docs/*.md` file must have an index row in `docs/README.md`. Always runs — including on docs-only PRs where `python-tests` is skipped, since the test lives in that suite. |
| `shellcheck` | shellcheck at `--severity=error` over every `*.sh` (gates on real breakage, not style) |
| `markdown-links` | lychee checks every link in every `*.md` (`--exclude-loopback`: docs reference localhost service addresses that can never resolve on a runner; `--exclude` for the bot-blocking hosts — boat.dev, businesswire.com, daytona.io, fourweekmba.com, globenewswire.com, medium.com, producthunt.com, tvgreport.com, plus the release-compare URL pattern — see the exclusion comments in `.github/workflows/ci.yml`; the local-run block below documents the manual re-sweep ritual for the medium.com / businesswire.com / globenewswire.com subset). Mail links are excluded by lychee's default in current versions — do not pass `--exclude-mail`; the flag was removed upstream and fails the step. |
| `png-check` | Playwright screenshots example.com (`scripts/pw-test.py`) and `scripts/png-check.py` validates the PNG signature/dimensions |
| `changelog-ritual` | `scripts/lint-changelog-ritual.py` enforces the CHANGELOG ritual's rules 1 + 4: entries must not reference workspace-internal paths (`agent_notes/`, `hidden_files/`, `workspace/goals/`) that never exist in a reader's checkout. The ritual preamble documenting the rule is exempt. |

# replicate the CI jobs locally before opening a PR:

```sh
# pytest suites — CI runs exactly this repo-root one-liner
# (`pytest.ini` testpaths is the authoritative suite inventory; a test file
# landing outside the listed directories fails
# scripts/test_pytest_ini_covers_all.py instead of silently never running):
python3 -m pytest -q

# one component's suite only, from the repo root:
python3 -m pytest proxy -q
# (per-component inventory + dependency notes: CONTRIBUTING.md "Running the
# tests" — its component table is pinned to testpaths by
# scripts/test_contributing_suites.py, so unlike the old per-directory list
# that used to live here, it can't drift)

# changelog ritual lint (same check as the CI `changelog-ritual` job):
# entries must not reference the maintainer's internal working-note paths
# (agent_notes/, hidden_files/, workspace/goals/).
python3 scripts/lint-changelog-ritual.py
python3 -m pytest scripts/test_lint_changelog_ritual.py -q

# shellcheck (same --severity=error gate as CI)
shellcheck --severity=error $(git ls-files '*.sh')

# markdown links (lychee installable from
# https://github.com/lycheeverse/lychee/releases)
# NOTE: --exclude-mail does NOT exist in current lychee (removed upstream;
# mail links are excluded by default). --exclude-loopback keeps docs'
# localhost service references (cred-ui, proxy) from failing the run.
# The full --exclude list (bot-blocking hosts, release-compare URL pattern)
# lives in .github/workflows/ci.yml's markdown-links job — copy the args
# from there; the three-host sample below is NOT the full list and must not
# be treated as one. medium.com, businesswire.com, globenewswire.com are
# excluded at host level:
# they block automated fetchers (Medium 403s all bots; the newswires reject
# lychee's HTTP client) — false positives, not broken links. Host-level, not
# per-URL: any new link from these hosts would trip the same bot blocks, so
# the exclusion has to cover the whole host. When ADDING a link from one of
# these hosts, open it in a real browser (they serve browsers fine) and
# confirm the page loads and matches the headline you cite — a browser 404
# means the link is genuinely broken: fix the link, don't extend the
# exclusion. Re-sweep procedure + verification log:
# `docs/EXCLUDED_HOSTS_RESWEEP.md` (quarterly; last sweep 2026-09-22).
# Copy the full args from .github/workflows/ci.yml's markdown-links job, e.g.:
lychee --no-progress --exclude-loopback --exclude 'https?://(www\.)?medium\.com/.*' --exclude 'https?://(www\.)?businesswire\.com/.*' --exclude 'https?://(www\.)?globenewswire\.com/.*' '**/*.md'  # + the rest of ci.yml's --exclude list

# PNG smoke test (same scripts CI runs; --with-deps handles OS deps)
pip install playwright && python3 -m playwright install --with-deps chromium
rm -f /tmp/pw-test.png  # stale screenshot must not mask a pw-test failure
python3 scripts/pw-test.py && python3 scripts/png-check.py
```

The pytest suites need `pip install -r requirements-test.txt` first
(pytest, cryptography, pillow); the lint scripts are stdlib-only; lychee,
shellcheck, and playwright are external binaries.

Adding a new test suite: drop a `test_*.py` next to its component and add
its directory to `pytest.ini`'s `testpaths` — `scripts/test_pytest_ini_covers_all.py`
fails the run if a `test_*.py` file lands outside the listed directories,
and `scripts/test_contributing_suites.py` fails if CONTRIBUTING.md's
component table disagrees with `testpaths` in either direction. (There is
no per-suite CI step to add anymore — the `python-tests` job runs the
repo-root one-liner over the whole `testpaths` inventory.) The suite must
be green on the branch before the PR is opened. (Docs-only PRs skip
`python-tests` via the `changes` gate above; `docs-guard` still enforces
the docs-index invariant on those.)
