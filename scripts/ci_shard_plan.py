"""Shard inventory for the `python tests` CI gate (#1138).

CI's `python-tests` job fans out into one matrix job per shard (see
`.github/workflows/ci.yml`), so the ~40-minute serial suite runs as 3
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

- shard-integration: muse-job/tests — the named slow integration dir
  (real manager/host round-trips; 653 tests, the largest suite).
- shard-components: proxy, harness, hosted — the other
  process-spawning integration suites. proxy/ also carries the sudo
  root tests (see `root_tests` below).
- shard-unit: confirm, deploy, scripts, cred-ui/tests, cua, jail,
  credlib, fleet, pairing, browser-driver — component suites and the
  fast unit/lint/schema/docs-guard suites.

Pure stdlib, no fixtures: the plan must import cleanly in the CI `plan`
job with nothing installed beyond the runner's Python.
"""

import json

# Shard name -> ordered list of pytest.ini testpaths directories.
# Keep names short and URL/identifier-safe: they appear in check names
# as `python tests (<shard>)`.
SHARDS = {
    "shard-integration": [
        "muse-job/tests",
    ],
    "shard-components": [
        "proxy",
        "harness",
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
    matrix = shard_matrix()
    if not matrix["include"]:
        raise SystemExit("ci_shard_plan: no shards defined")
    print(json.dumps(matrix))


if __name__ == "__main__":
    main()
