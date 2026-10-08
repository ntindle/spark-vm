"""Shard inventory for the `python tests` CI gate (#1138).

CI's `python-tests` job fans out into one matrix job per shard (see
`.github/workflows/ci.yml`), so the ~40-minute serial suite runs as 4
parallel shards and the slowest shard becomes the new pole. This file is
the single source of the shard inventory:

- ci.yml's `plan` job runs `python3 scripts/ci_shard_plan.py`, which emits
  the Actions matrix JSON (`{"include": [{"shard": ..., "dirs": ...}]}`).
- `scripts/test_ci_shard_plan.py` pins the inventory: every `pytest.ini`
  `testpaths` directory runs in exactly one shard, so a new suite can
  never land unwired (the same drift class
  `scripts/test_pytest_ini_covers_all.py` guards for the one-liner).

Grouping (issue #1138: shard by testpaths-dir grouping, slow integration
dirs isolated from the fast unit dirs). Basis: per-dir timing probes on
the loop's 2-vCPU VM (three parallel `timeout 90 pytest <dir>` groups —
noisy under contention, so the ordering is the signal, not the absolute
seconds). Three dirs blew the 90s probe budget — muse-job/tests,
harness, deploy — so the grouping spreads those three one per shard
(the minimax-robust choice when their true magnitudes are unknown);
muse-job/tests is additionally the slow integration dir the issue names.
The PR's own CI run measures the real per-shard wall times — rebalance
by editing SHARDS below (the pin test keeps the bijection honest).

Rebalance 2026-10-08 (follow-up turn): the first sharded CI run
(PR #1149) measured the pole at shard-components 5m50s vs 3m14s
(shard-integration) and 3m12s (shard-unit), and full per-dir local
timings on the loop VM pinned the driver: harness/ alone is ~278s
local — ~1.5x the next-heaviest dir (muse-job/tests ~188s local, deploy
~123s) and ~70% of shard-components' whole wall time. The minimax move is to
extract harness/ into its own shard: the pole becomes the harness
shard itself at ~4m (estimated from the CI/local ratio of the old
shard-components), vs the old 5m50s. If the suite grows past this
again, the same playbook applies — split the new pole dir into its own
shard; the aggregate `python tests` gate, the ruleset anchor, and the
workflow all stay untouched (per-shard check names are deliberately
never required status checks).

- shard-integration: muse-job/tests — the named slow integration dir
  (real manager/host round-trips; 685 tests, the largest suite).
- shard-harness: harness — the measured pole driver (~278s local;
  real-worker process-spawning harness, ~1.5x any other dir).
- shard-components: proxy, hosted — the remaining process-spawning
  integration suites. proxy/ also carries the sudo root tests (see
  `root_tests` below).
- shard-unit: confirm, deploy, scripts, cred-ui/tests, cua, jail,
  credlib, fleet, pairing, browser-driver — component suites and the
  fast unit/lint/schema/docs-guard suites.

Pure stdlib, no fixtures: the plan must import cleanly in the CI `plan`
job with nothing installed beyond the runner's Python.
"""

import json
import sys

# Shard name -> ordered list of pytest.ini testpaths directories.
# Keep names short and URL/identifier-safe: they appear in check names
# as `python tests (<shard>)`.
SHARDS = {
    "shard-integration": [
        "muse-job/tests",
    ],
    "shard-harness": [
        "harness",
    ],
    "shard-components": [
        "proxy",
        "hosted",
    ],
    "shard-unit": [
        "confirm",
        "deploy",
        "scripts",
        "cred-ui/tests",
        "cua",
        "jail",
        "credlib",
        "fleet",
        "pairing",
        "browser-driver",
    ],
}


def get_testpaths():
    """The pytest.ini testpaths inventory (same source the pin test uses)."""
    import configparser
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    parser = configparser.ConfigParser()
    parser.read(root / "pytest.ini")
    raw = parser.get("pytest", "testpaths")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def check_bijection(testpaths):
    """The shard<->testpaths bijection as a list of problem strings.

    Empty means sound. Single implementation shared by `--check` (CI) and
    the pin test — the inventory must not be enforceable only by a test
    that runs inside the inventory it guards (a PR dropping scripts/
    from SHARDS would unwire the pin from its own CI run; the plan job's
    --check cannot be unwired that way).
    """
    counts = {}
    for shard, dirs in SHARDS.items():
        for d in dirs:
            counts[d] = counts.get(d, 0) + 1
    problems = []
    for p in testpaths:
        n = counts.get(p, 0)
        if n == 0:
            problems.append(
                f"testpaths dir {p!r} is in no shard (would never run in CI)"
            )
        elif n > 1:
            problems.append(f"dir {p!r} is in {n} shards (would run twice)")
    for d in counts:
        if d not in testpaths:
            problems.append(
                f"shard dir {d!r} is not in pytest.ini testpaths "
                "(pytest would fail 'file or directory not found')"
            )
    return problems


def shard_matrix():
    """The Actions matrix payload: one entry per shard.

    `dirs` is space-joined so the workflow step can pass it straight to
    `python3 -m pytest -q ${{ matrix.dirs }}` with no extra parsing.
    `root_tests` flags the shard that runs the sudo root tests
    (proxy/test_safe_install.py's self-skipping substitution guards —
    see the workflow): it is exactly the shard holding `proxy/`, derived
    from the inventory rather than hardcoded, so renaming a shard can
    never silently drop those tests. `scripts/test_ci_shard_plan.py`
    pins the exactly-one-true invariant.
    """
    return {
        "include": [
            {
                "shard": name,
                "dirs": " ".join(dirs),
                "root_tests": "proxy" in dirs,
            }
            for name, dirs in SHARDS.items()
        ]
    }


def main():
    if "--check" in sys.argv[1:]:
        # Bijection enforcement for the CI plan job: fails the job (and
        # therefore the aggregate gate) if the inventory drifts. Must stay
        # stdlib-only — the plan job runs it with nothing installed.
        problems = check_bijection(get_testpaths())
        for p in problems:
            print(f"ci_shard_plan --check: {p}", file=sys.stderr)
        if problems:
            raise SystemExit(1)
        print("ci_shard_plan --check: shard inventory OK")
        return
    matrix = shard_matrix()
    if not matrix["include"]:
        raise SystemExit("ci_shard_plan: no shards defined")
    print(json.dumps(matrix))


if __name__ == "__main__":
    main()
