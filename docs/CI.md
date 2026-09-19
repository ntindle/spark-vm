# CI

`.github/workflows/ci.yml` runs on every push to `main`, every pull request
against `main`, and on manual `workflow_dispatch` runs.

| Job | What it runs |
|---|---|
| `python-tests` | pytest suites: `proxy/` (swap addon incl. `test_round6.py`, grant writer), `confirm/` (confirmd), `deploy/` (auto-deploy), `muse-job/tests` (event trust). Installs `shellcheck` via apt first — `test_auto_deploy.py::test_scripts_syntax` gates on shellcheck *warnings* and must not depend on whatever the runner image happens to carry. |
| `shellcheck` | shellcheck at `--severity=error` over every `*.sh` (gates on real breakage, not style) |
| `markdown-links` | lychee checks every link in every `*.md` (`--exclude-loopback`: docs reference localhost service addresses that can never resolve on a runner). Mail links are excluded by lychee's default in current versions — do not pass `--exclude-mail`; the flag was removed upstream and fails the step. |
| `png-check` | Playwright screenshots example.com (`scripts/pw-test.py`) and `scripts/png-check.py` validates the PNG signature/dimensions |

# replicate the CI jobs locally before opening a PR:

```sh
# pytest suites (same invocations CI runs)
cd proxy   && python3 -m pytest test_swap_addon.py test_grant_writer.py test_round6.py
cd confirm && python3 -m pytest test_confirmd.py
cd deploy  && python3 -m pytest test_auto_deploy.py
cd muse-job && python3 -m pytest tests/test_event_trust.py

# shellcheck (same --severity=error gate as CI)
shellcheck --severity=error $(git ls-files '*.sh')

# markdown links (same args as CI; lychee installable from
# https://github.com/lycheeverse/lychee/releases)
# NOTE: --exclude-mail does NOT exist in current lychee (removed upstream;
# mail links are excluded by default). --exclude-loopback keeps docs'
# localhost service references (cred-ui, proxy) from failing the run.
lychee --no-progress --exclude-loopback '**/*.md'

# PNG smoke test (same scripts CI runs; --with-deps handles OS deps)
pip install playwright && python3 -m playwright install --with-deps chromium
rm -f /tmp/pw-test.png  # stale screenshot must not mask a pw-test failure
python3 scripts/pw-test.py && python3 scripts/png-check.py
```

Only pytest is required; everything else is stdlib. Adding a new test suite:
drop a `test_*.py` next to its component and add one `pytest` step to the
`python-tests` job — the suite must be green on the branch before the PR is
opened.
