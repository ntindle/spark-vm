# CI

`.github/workflows/ci.yml` runs on every push to `main` and every pull request.

| Job | What it runs |
|---|---|
| `python-tests` | pytest suites: `proxy/` (swap addon, grant writer), `confirm/` (confirmd), `deploy/` (auto-deploy), `muse-job/tests` (event trust) |
| `shellcheck` | shellcheck at `--severity=error` over every `*.sh` (gates on real breakage, not style) |
| `markdown-links` | lychee checks every link in every `*.md` |
| `png-check` | Playwright screenshots example.com (`scripts/pw-test.py`) and `scripts/png-check.py` validates the PNG signature/dimensions |

Run the same checks locally before opening a PR:

```sh
cd proxy   && python3 -m pytest test_swap_addon.py test_grant_writer.py test_round6.py
cd confirm && python3 -m pytest test_confirmd.py
cd deploy  && python3 -m pytest test_auto_deploy.py
cd muse-job && python3 -m pytest tests/test_event_trust.py
```

Only pytest is required; everything else is stdlib. Adding a new test suite:
drop a `test_*.py` next to its component and add one `pytest` step to the
`python-tests` job — the suite must be green on the branch before the PR is
opened.
