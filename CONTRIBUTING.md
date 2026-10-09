# Contributing to spark-vm

Thanks for looking at the code — this is a one-human-and-his-robot project
and outside eyes are the highest-leverage help we get (docs first, always).

## Before you write code

**Open an issue first for anything bigger than a typo.** Say what you want
to change and why; the maintainer will confirm the direction before you
spend an afternoon on it. Duplicated work is the main thing we try to
avoid.

Good places to start: issues labeled
[`good first issue`](https://github.com/ntindle/spark-vm/labels/good%20first%20issue)
— if that label looks empty, say so on an issue; seeding it is maintainer
work we sometimes forget.

## Branching and PRs

- Branch from `main`. Name it `feature/<short-slug>` (or `fix/<short-slug>`
  for bug fixes). The `hourly/` and `strategy/` prefixes are the
  maintainer's automation loops — don't use them for manual PRs.
- One improvement per PR. If the change grew teeth, split it.
- PR body: what changed, why, and how you tested it. Link the issue.
- **Add a `CHANGELOG.md` entry**: every PR that changes anything
  user- or operator-visible adds one or two bullets under
  `## [Unreleased]` in the right section — write it for the person
  running spark-vm, not the person who wrote the diff, and link the PR
  number. The ritual (sections, what skips an entry, release-time rollover)
  is documented at the top of `CHANGELOG.md`. Reviewers request changes
  when the entry is missing — it's a merge gate, not a suggestion.
- Every PR gets reviewed adversarially — expect hard questions from
  engineering, security, and product perspectives. That's the norm here, not
  a sign something is wrong with your PR.
- Don't merge your own PR. (The `hourly/` and `strategy/` automation loops
  are the one exception: they merge their own PRs after unanimous
  adversarial sign-off — that's the maintainer's settled process, not a
  shortcut available to manual contributors.)

## Running the tests

One command, from the repo root:

```bash
python3 -m pytest
```

`pytest.ini`'s `testpaths` is the authoritative suite inventory — one
directory per component. Four pins keep it honest:
`scripts/test_pytest_ini_covers_all.py` fails if a `test_*.py` file lands
outside the listed directories (no silently unwired suites),
`scripts/test_contributing_suites.py` fails if the component table below
and `testpaths` disagree in either direction (no drifted contributor docs),
and `scripts/test_deploy_gate_tests_coverage.py` fails if a `test_*.py`
file under a gate-enumerated component directory (`proxy/`, `confirm/`)
is not registered in that component's pre-deploy gate command in
`deploy/components.conf` — or if a registration points at a deleted file
(a new test must be exercised before deploys, not just in CI).
Registrations must be repo-relative paths (no `..` segments or absolute
paths), and each gate-enumerated component's registered-file count is
pinned exactly, so a new gate component has to declare its count before
it counts as covered. Finally, `scripts/test_basename_uniqueness.py`
fails if two `test_*.py` files anywhere in the repo would import under
the same pytest module name (pytest's `prepend` import mode imports
rootless suites by basename; this repo's test trees are rootless (no
`__init__.py`) — except `browser-driver/bdrive/`, the one real package,
which imports as `bdrive.<name>` — see the "Two conventions" paragraph
below), naming every
colliding file and the fix. This pin walks the whole tree, not just the
directories `testpaths` collects, so the uniqueness contract holds even
for test files no suite currently wires in.
All suites pass on `main`; your PR should keep them green.

Install the test dependencies first:

```bash
pip install -r requirements-test.txt
```

To run one component's suite: `python3 -m pytest <dir>` from the repo
root (e.g. `python3 -m pytest proxy`).

Per-component dependency notes — install these (beyond stdlib + pytest)
before running that component's suite:

| Component | Run it | Extra deps beyond stdlib + pytest |
|---|---|---|
| `proxy/` | `python3 -m pytest proxy` | none (mitmproxy is a *deploy*-time dependency — the swap proxy runs under it on the box; no test module imports it) |
| `confirm/` | `python3 -m pytest confirm` | `cryptography` (VAPID / Web Push in `confirm/push.py`) |
| `muse-job/tests/` | `python3 -m pytest muse-job/tests` | none |
| `deploy/` | `python3 -m pytest deploy` | none |
| `scripts/` | `python3 -m pytest scripts` | `pillow` (`test_waitlist_page.py` — og:image dimension/format assertions) |
| `cred-ui/tests/` | `python3 -m pytest cred-ui/tests` | none |
| `harness/` | `python3 -m pytest harness` | none |
| `hosted/` | `python3 -m pytest hosted` | none (stdlib-only by design — the tenant-status layer runs unchanged on the self-hosted box, the hosted control plane, and the operator laptop) |
| `browser-driver/` | `python3 -m pytest browser-driver` | none |
| `cua/` | `python3 -m pytest cua` | none (the bridge's driver calls are stubbed; the `.sh` scripts get `bash -n` syntax + shellcheck-warning gates plus isolated extraction-tests of their security guards — they run with real side effects on spark-vm) |
| `jail/` | `python3 -m pytest jail` | none (`build.sh --help` executes the real script's arg parsing and exits before any side effect; full builds need root + systemd-nspawn on the box) |
| `credlib/` | `python3 -m pytest credlib` | none (name-validation + stdin-cap unit tests only; the `/home/swapd/secrets` store is a string constant, never touched) |
| `fleet/` | `python3 -m pytest fleet` | none (stdlib-only — the operator-estate collector and its hermetic suite) |
| `pairing/` | `python3 -m pytest pairing` | none (stdlib-only by design — pure-Python ed25519 + box client; runs on the box, in the Cloudflare Python Worker, and in CI) |

Two conventions keep the one-liner working: keep every `test_*.py`
basename unique across the repo (pytest imports test modules by basename),
and never leave `sys.path` / `sys.modules` mutations behind in a test —
an order-dependent failure in the full run is a bug in the test, not in
pytest.

Run from the repo root: a bare `pytest` inside a subdirectory (e.g.
`cd proxy && pytest`) silently runs only that subtree. pytest still finds
the root `pytest.ini` from a subdirectory, but with no path args it
collects the invocation dir instead of `pytest.ini`'s `testpaths` — so
you get only the subtree's tests. Always run the suite from the root so
`pytest.ini`'s `testpaths` apply.

### The merge gate, locally

`python3 -m pytest` is most of what CI checks, but not all of it — five
more CI jobs gate the merge, and a PR that is green locally can still go
red on CI if you skip the ones you can run. The five, with their local
form:

```bash
# changelog ritual lint (a required CI check: CHANGELOG entries must not
# reference workspace-internal paths; see the ritual at the top of
# CHANGELOG.md)
python3 scripts/lint-changelog-ritual.py

# docs-index coverage: every docs/*.md file needs a row in docs/README.md.
# It runs inside the full suite, and CI also runs it standalone on every
# PR — including docs-only ones, where the python suite is skipped.
python3 -m pytest scripts/test_docs_index_coverage.py -q
```

The suite carries two shellcheck gates: the warning gate
(`cua/test_shell_scripts.py` covers `cua/bin/*.sh`;
`deploy/test_auto_deploy.py` covers `deploy/auto-deploy.sh` and
`proxy/deploy.sh`) and the one error-severity gate
(`jail/test_build_smoke.py` on `jail/build.sh`). Both skip with a loud
message when shellcheck is not installed — they do not fail. CI installs
shellcheck from apt (unpinned) into the python-tests shards, so install
it locally and the suite exercises the same gates; if CI's and your local
shellcheck versions diverge, the warning sets can too — treat a local
green as necessary but not sufficient.

One CI job has no suite equivalent: the standalone `shellcheck` job runs
`severity=error` over the repo's shell scripts — scripts the suite never
covers (e.g. `harness/`, `fleet/`, `scripts/`). The closest local
approximation for a PR that touches shell scripts:

```bash
git diff --name-only origin/main...HEAD -- '*.sh' | xargs -r shellcheck -S error
```

The PNG smoke test is locally runnable too — CI's own steps are the
recipe: `pip install playwright`, then the one-time
`python3 -m playwright install --with-deps chromium` (installs OS deps,
escalates internally), then `python3 scripts/pw-test.py` and
`python3 scripts/png-check.py`.

The install-safety root tests live *inside* the `python tests` job rather
than as their own job: they self-skip as non-root, so your local pytest
run never executes them — but CI runs them under sudo as part of the
python-tests shard. If your PR touches proxy install/deploy code, prove
it the way the shard does:

```bash
sudo SAFE_INSTALL_ROOT_TESTS=require "$(command -v python3)" -m pytest \
  proxy/test_safe_install.py \
  -k 'unreachable_by_parent_dir_attacker or staging_dir_swap_fails_closed' -q
```

Only the markdown link check has no practical local equivalent: lychee
runs with a long bot-block exclusion list that lives in
`.github/workflows/ci.yml`, and its verdict depends on runner-egress IP
reputation (bot-blocks that don't reproduce from your IP), so the gate's
result genuinely can't be replicated locally. For that one, read the CI
run on your PR instead of trying to replicate it.

## Secrets: the one hard rule

**Never commit real secrets, tokens, credentials, or private keys.**
Configs in this repo use `hsurr:<name>` placeholders; real values are
installed by the operator through the credential store and swapped in at
the proxy. `scripts/push.sh` runs a secret scan before pushing — if it
flags something, fix it before opening the PR. This rule has no exceptions
and no "I'll remove it later."

## Security issues

Don't open a public issue or PR for a vulnerability. See
[SECURITY.md](SECURITY.md) for the responsible-disclosure process.

## Deploying (operators only)

If you're contributing, your job ends at the merged PR. Getting merged
code onto the live box (`git pull`, `./proxy/deploy.sh`) is the operator's
job, not the contributor's — the loop's auto-deploy tooling handles most of
it. Don't include deploy steps in contributor PRs.

## Docs live here too

Docs are a first-class contribution — if a step confused you, the fix is a
PR. Keep new docs under `docs/` and keep them factual: no promises about
unbuilt features (see `docs/POSITIONING.md` for the copy rules).
