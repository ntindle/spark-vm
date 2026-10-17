# D9 sweep D-PP-2 conformance fixtures (#1566 S2)

The async plane port of the D9 sweep cannot be byte-identical to the
in-repo sync `hosted/push_sweep.py` — the worker's D1 is async-only, so
the port is an async rewrite (F-PP-2), not a copy. This package is the
port's **dispatch truth**: the scenario fixtures the port must satisfy,
and the recorded outputs it must reproduce.

## The mechanism (D-PP-2)

- `scenarios.py` defines 8 deterministic scenarios: each pins the
  sweep's clock (`now`), the owner registry, and the watcher
  derivations, builds a fixture SQLite database, and runs
  `sweep_once`.
- `recorded/<scenario>.json` holds the outputs the sync sweep produced:
  the `SweepSummary` plus the resulting database state
  (`push_send_results`, `push_digest_state`, `push_budget_counters`),
  plus the SHA-256 of the sync module that produced them.
- `hosted/test_push_sweep_port_conformance.py` replays every fixture
  against the in-repo sync sweep on every CI run and diffs against the
  recorded files, failing on divergence.

The in-repo sync module is the evolving harness truth (D-PP-1); the
recorded outputs are the tripwire that forces the port to follow. **A
port that reproduces the recorded outputs for every scenario is
conformant; the CI test is what keeps it conformant.**

## The async port's obligations (S2-b)

The port (the `control-plane/worker.py` async sweep section, per the
`deploy/plane-cron/CRON_TRIGGER_CONTRACT.md` §2 async amendment) must:

1. Reproduce every recorded output byte-for-byte, given the same
   fixture database and the same pinned `now` — the same disposition
   maps, the same row sets, the same `at`/`enqueued_at` timestamps
   (all now-derived; nothing wall-clock may leak into the records).
2. Resolve owners from the plane's enrollment registry via the injected
   resolver — never from a box assertion, never from the approvals row
   (D2).
3. Carry `reminders_enabled` from day one (the D71 retirement rule).
4. Never call the in-repo sync entry points — the worker is async-only;
   the sync modules stay the harness and test truth.

## Regenerating the records

Records are generated from the sync module, never hand-edited:

```bash
python3 -m hosted.push_sweep_port.record   # from the repo root
```

Regenerate after any intentional change to the sync sweep's observable
behavior, review the diff, and ship the regenerated records in the same
PR — the port must then be updated to reproduce the new records. The
conformance test asserts the recorded SHA-256 matches the sync module
under test, so a hand-edited record or a drifted module fails loudly.

## Scenario list

| Scenario | Pins |
|---|---|
| `reminder_due` | One due reminder → exactly one `queued` page. |
| `reminder_terminal_clock` | Clock-terminal pending approval → one idempotent `suppressed_terminal` audit row, no page (D61). |
| `reminder_decided` | Decided approval → never a candidate: zero pages, zero audits. |
| `digest_pending` | Pending digest window → one digest page + `enqueued_at` stamp. |
| `reminders_disabled` | `reminders_enabled=False` → reminder pass skipped, digest unaffected (D71). |
| `watchers_wired` | Both watcher derivations → one stale page + one token-warning page. |
| `poisoned_candidate` | A raising candidate → `poisoned` disposition, pass continues (D78). |
| `budget_already_exhausted` | `time_budget_s=0` → every pass stops pre-candidate, `budget_truncated` (D103). |

Deliberately not fixture-able: partial-budget stops (wall-clock
interleaving) and the `tick_overrun` note (measures wall-clock
duration) — the port must still implement them per D103, but the
records cannot pin them.
