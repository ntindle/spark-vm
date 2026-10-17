"""The D9 sweep's D-PP-2 conformance fixture set (#1566 S2).

The async plane port of the D9 sweep cannot be byte-identical to the
in-repo sync `hosted/push_sweep.py` — the worker's D1 is async-only, so
the port is an async rewrite (F-PP-2), not a copy. Its anti-drift is
conformance, not identity:

- `scenarios.py` defines the scenario fixtures — the dispatch truth.
  Every fixture pins the sweep's clock (`now`), the owner registry,
  and the watcher derivations, so the sweep's outputs are fully
  deterministic.
- `recorded/<scenario>.json` holds the outputs the in-repo sync sweep
  produced for each scenario: the SweepSummary plus the resulting
  database state. Generated FROM the sync module by
  `python3 -m hosted.push_sweep_port.record` — never hand-edited.
- `hosted/test_push_sweep_port_conformance.py` replays every fixture
  against the in-repo sync sweep on every CI run and diffs the outputs
  against the recorded files, failing on divergence.

The in-repo sync module is the evolving harness truth (D-PP-1); the
recorded outputs are the tripwire that forces the port to follow. A
port that reproduces the recorded outputs for every scenario is
conformant; the CI test is what keeps it conformant.

Fixture discipline (pinned, so the async port can trust the records):
- `now` is pinned per scenario (epoch seconds). The sweep threads one
  clock reading through every pass (D73), so every timestamp in the
  outputs is now-derived — nothing wall-clock leaks into the records.
- No fixture sets `tick_interval_s`: the `tick_overrun` note measures
  wall-clock duration and cannot be pinned.
- The D103 time-budget path is covered only in its already-exhausted
  shape (`time_budget_s=0` — deterministically past). Partial-budget
  stops depend on wall-clock interleaving and are not fixture-able.
- The recorded files pin the SHA-256 of the sync module that produced
  them; the conformance test asserts it matches, so a hand-edited
  record or a drifted module fails loudly instead of silently.
"""
