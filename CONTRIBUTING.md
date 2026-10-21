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

Install the test dependencies first — inside a virtual environment.
On stock Ubuntu 24.04 (and any PEP 668 system) a bare `pip install`
refuses with `externally-managed-environment`, so create and activate
a venv first, then install into it. The commands below are bash on
Unix; Windows uses `.venv\Scripts\Activate.ps1` (PowerShell) instead
of the `source` line, fish uses `source .venv/bin/activate.fish`.

On Debian/Ubuntu, `python3 -m venv` itself needs one package first —
a stock install has no `ensurepip`, so the venv command fails with
`ensurepip is not available` until you install it (once per machine):

```bash
sudo apt install -y python3-venv
```

Then, from the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
```

If a first attempt failed halfway and left a half-created `.venv/`,
remove it and retry: `rm -rf .venv` (PowerShell:
`Remove-Item -Recurse -Force .venv`), then run the block above again.

Keep the venv activated for every `pytest` / `local-gate.sh` run in
this checkout (re-activate with `source .venv/bin/activate` in each new
shell). If `pytest` fails with `ModuleNotFoundError`, you are probably
in a shell where the venv is not activated — re-activate first.
`.venv/` is gitignored, so the checkout stays clean — and the
local gate's changed-paths check keeps reading your tree correctly.

To run one component's suite: `python3 -m pytest <dir>` from the repo
root (e.g. `python3 -m pytest proxy`). To run exactly the selection one of
CI's five `python tests` shards runs — the ~40-minute serial suite is split
into parallel shards, and a shard's selection can span several directories —
ask the shard inventory for the command instead of reconstructing it:

```bash
python3 scripts/ci_shard_plan.py --pytest-cmd <shard>
```

That prints CI's exact pytest selection for the shard (`python3 -m pytest
-q` over the shard's directories, straight from the inventory
`.github/workflows/ci.yml` consumes), so your local run and the CI shard
job prove the same suites. Valid shard names are listed in
`scripts/ci_shard_plan.py` (`shard-unit`, `shard-components`,
`shard-integration`, `shard-harness`, `shard-deploy`).

### Parallel runs

For a faster local loop, run the suite in parallel with
[pytest-xdist](https://pytest-xdist.readthedocs.io/en/stable/) (installed
via `requirements-test.txt`):

```bash
python3 -m pytest -n=auto
```

`-n=auto` starts one worker per CPU and splits individual tests across
workers. Verified against the serial run with identical results:
`scripts/` (667 passed, 1 skipped, 33 subtests) and `hosted/` (404 passed
plus the one pre-existing dashboard inline-copy failure — #1299,
`hosted/dashboard/test_dashboard.py::test_worker_inline_copy_byte_identical`,
which reproduces on a pristine-main serial run and is
environment-dependent: it fails only where the control-plane checkout
resolves) both agree serial vs parallel; on a 2-CPU box the parallel
runs measured ~37s → ~28s (`scripts/`) and ~80s → ~67s (`hosted/`)
(single run; pytest 9.1.1 + pytest-xdist 3.8.0). The full suite has
not yet had a timed parallel run; the serial one-liner above remains
the reference for the full run, and CI sharding is unchanged.

The static audit behind this found no parallel blocker: no `conftest.py`
shared fixtures, real socket binds use ephemeral ports or per-test
temporary sockets, repo-tree writes go to temporary directories, and
`sys.path` / `sys.modules` / environment mutations in tests are
import-time additive inserts or follow save-and-restore / monkeypatch.
A failure that appears only under `-n=auto` is an
order-dependence bug in the test, not in pytest — fix the test (see
the "Two conventions" paragraph above). The conservative variant
`python3 -m pytest -n=auto --dist loadfile` keeps each test file on
one worker instead of splitting tests across workers. If `pytest`
fails with `unrecognized arguments: -n`, pytest-xdist is not
installed — reinstall `requirements-test.txt`.

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

`python3 -m pytest` is most of what CI checks, but not all of it — eight
more CI checks gate the merge, and a PR that is green locally can still go
red on CI if you skip the ones you can run. The one-shot way to run them:

```bash
./scripts/local-gate.sh
```

It runs the shard-plan check, the changelog ritual lint, the changed-paths
evaluation (docs-only diffs skip the python suite, like CI — your
uncommitted changes count as code, so the suite still runs until you
commit them), docs index coverage, the markdown table lint, shellcheck severity=error over the CI
job's shell-file selection on the whole checkout, and then the full python suite — failing on the
first failure.
`./scripts/local-gate.sh --quick` runs only the cheap checks (no suite);
`./scripts/local-gate.sh --plan` prints the steps without running them.
The two checks the script doesn't run — the markdown link check (no
practical local equivalent) and the PNG screenshot smoke test (one
command, see below) — are named in the output, not run.

The seven, with their local form — `local-gate.sh` runs the same checks in
one invocation (its changed-paths evaluator is the script's CI-verbatim
form of the one-liner below; identical except on a zero-change diff, where
the script fails closed and runs the suite, like CI):

<!-- The required-check inventory this section claims. The branch-protection
ruleset (deploy/rulesets/main-branch-protection.json) is the source of
truth; scripts/test_contributing_ci_gates.py fails if this list and the
ruleset disagree, so add the new check here the moment the ruleset grows.
(The block is invisible in GitHub's rendered view, visible in raw/edit
view.) -->
<!-- gate-checks:start -->
python tests
shard plan
shellcheck
markdown link check
PNG screenshot smoke test
changelog ritual lint
changed-paths gate
docs index coverage
markdown table lint
<!-- gate-checks:end -->

```bash
# shard plan (a required CI check: the plan job emits the shard matrix from
# scripts/ci_shard_plan.py and enforces the shard<->testpaths bijection —
# a PR adding a test directory without wiring it into a shard fails here)
python3 scripts/ci_shard_plan.py --check

# changed-paths gate (a required CI check: skips the python suite on
# docs-only diffs). Local equivalent — exit 0 means CI would RUN the suite
# on your diff, exit 1 means CI would skip it as docs-only. (A zero-change
# diff feeds grep empty input → exit 1; CI fails closed the other way and
# runs the suite — but a real PR never has a zero diff.)
git diff --no-renames --name-only origin/main...HEAD \
  | grep -qvE '^(docs/|CHANGELOG\.md$)'

# changelog ritual lint (a required CI check: CHANGELOG entries must not
# reference workspace-internal paths; see the ritual at the top of
# CHANGELOG.md)
python3 scripts/lint-changelog-ritual.py

# `docs index coverage`: every docs/*.md file needs a row in docs/README.md.
# It runs inside the full suite, and CI also runs it standalone on every
# PR — including docs-only ones, where the python suite is skipped. The
# standalone job also runs the five doc-claim pins (the link-check
# exclusion inventory vs ci.yml; CONTRIBUTING's own gate inventory vs
# ci.yml and the branch-protection ruleset; the CI.md job-table inventory
# vs ci.yml's job ids; the wiring-tick operator doc's flags/report schema
# vs hosted/relay_tenant_wiring.py; the README/docs "(N tests)" suite-size
# claims vs the test files), so the old one-file invocation is NOT
# what CI runs — run all six files to replicate it.
python3 -m pytest scripts/test_docs_index_coverage.py scripts/test_ci_md_link_excludes.py scripts/test_contributing_ci_gates.py scripts/test_ci_docs_job_inventory.py scripts/test_relay_wiring_tick_doc.py scripts/test_readme_test_count_pins.py -q
```

```bash
# `markdown table lint` (same W1 gate as the CI `markdown-tables` job:
# every GFM table row on exactly one line — a wrapped continuation line
# silently kills the rendered table):
python3 scripts/docs_table_lint.py
python3 -m pytest scripts/test_docs_table_lint.py -q
```

The remaining three — `shellcheck`, the PNG screenshot smoke test, and the
markdown link check — are covered in the paragraphs below.

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

One CI job has no suite equivalent on docs-only diffs: the standalone
`shellcheck` job runs `severity=error` over the repo's shell scripts on
every PR (it has no changed-paths carve-out), while the suite's repo-wide
pin is skipped on docs-only verdicts. The exact local form — what
`local-gate.sh` step 5 runs:

```bash
python3 scripts/ci_shellcheck_files.py | xargs -r -0 shellcheck -S error
```

(`scripts/ci_shellcheck_files.py` is the shared selection helper: it
replicates the pinned action's file selection — named shell files plus
extension-less executables with a shell shebang — and is the single
source of truth for both the gate step and the suite's pin.)

The PNG screenshot smoke test is locally runnable too — one command, with the
venv activated (see above):

```bash
./scripts/png-smoke.sh
```

It installs the pinned playwright (`scripts/self_update_pins.conf`) into the
venv only if the installed version differs, installs the Chromium browser
(`./scripts/png-smoke.sh --with-deps` forwards `--with-deps` to
`playwright install`, which installs OS deps and escalates internally), then
runs `scripts/pw-test.py` + `scripts/png-check.py` — the same scripts CI's
`png-check` job runs, against the same pin. `./scripts/png-smoke.sh --plan`
prints the steps without running anything.

Only the markdown link check has no practical local equivalent: lychee
runs with a long bot-block exclusion list that lives in
`.github/workflows/ci.yml`, and its verdict depends on runner-egress IP
reputation (bot-blocks that don't reproduce from your IP), so the gate's
result genuinely can't be replicated locally. For that one, read the CI
run on your PR instead of trying to replicate it.

One more thing that isn't a separate check: the install-safety root tests
live *inside* the `python tests` shard rather than as their own check. They
self-skip as non-root, so your local pytest run never executes them — but
CI runs them under sudo as part of the python-tests shard. If your PR
touches proxy install/deploy code, prove it the way the shard does:

```bash
sudo SAFE_INSTALL_ROOT_TESTS=require "$(command -v python3)" -m pytest \
  proxy/test_safe_install.py \
  -k 'unreachable_by_parent_dir_attacker or staging_dir_swap_fails_closed' -q
```

### When the test-count pin fires

The docs-guard's test-count pin (`scripts/test_readme_test_count_pins.py`)
is the one that trips people: READMEs and docs state how many tests a test
file holds ("`test_foo.py` (N tests)"), and the count rots the moment the
suite changes — or is wrong the day it's written. Three tests enforce it:

- `test_readme_test_count_claims_match` — every claim registered in the
  file's `_CLAIMS` registry matches its test file's actual count.
- `test_all_test_count_claims_are_registered` — the anti-drift scanner: any
  `test_*.py (N tests)`-shaped claim in any `*.md` (a test-file mention with
  a `(N tests)`-shaped count in the ~100 characters immediately following
  the mention) must have a `_CLAIMS` entry, or CI fails. A new claim can
  never land unregistered the way `scripts/test_waitlist_jobs.py`'s did.
- `test_confirm_readme_directory_counts_match` — the `confirm/README.md`
  pair is a *directory* total, env-conditional (without vs with the optional
  `cryptography` package): its own pin, not a `_CLAIMS` entry.

When it fires, the failure message names the doc and the test file, and the
fix depends on which test tripped:

1. **Stale count** (`stale test-count claims`): you changed a suite. Update
   the stated count in the doc in the same PR. (The confirm/README pair's
   pin uses the prefix `stale confirm/ test-count claims` — same fix: update
   the doc. Its message names which of its two tripwires fired —
   parametrization landing in the directory, or the gated-file assumption
   breaking — so follow what the message says.)
2. **Unregistered claim** (`unregistered test-count claims`): your doc
   states a suite size nobody registered. Add one `_CLAIMS` entry in the
   same PR — a tuple of `(doc path, test file path, anchor regex)`, all
   paths repo-root-relative, where the anchor regex carries exactly one
   capture group for the stated count and must match **exactly once** in
   the doc (a second mention would shadow the pin). Copy the shape of the
   nearest existing entry, e.g.:

   ```python
   (
       "docs/YOUR_DOC.md",
       "hosted/test_foo.py",
       r"`test_foo\.py` \((\d+) tests\)",
   ),
   ```

The counting convention: the number of `test_*` functions pytest would
collect — module level plus class methods, counted by AST, not regex. A
parametrized test counts once (parametrization doesn't move the number); a
`test_*` def nested inside a function body doesn't count, because pytest
never collects it.

Run it directly — CI bundles it with the other doc-claim pins in one
pytest invocation, but the command below is behaviorally equivalent:

```bash
python3 -m pytest scripts/test_readme_test_count_pins.py -q
```

It also runs on docs-only PRs (the docs-guard job has no changed-paths
carve-out), so a docs PR that states a suite size is pinned exactly like a
code PR — register it before you push, not after CI tells you.

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
