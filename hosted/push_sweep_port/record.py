"""Regenerate the D-PP-2 recorded outputs for the D9 sweep (#1566 S2).

Usage (from the repo root):

    python3 -m hosted.push_sweep_port.record

Replays every scenario in `scenarios.py` against the in-repo sync
`hosted/push_sweep.py` and writes `recorded/<scenario>.json`. The sync
module is the harness truth (D-PP-1): records are generated from it,
never hand-edited — the conformance test pins the producing module's
SHA-256, so a hand-edited record fails loudly.

Run this after any intentional change to the sync sweep's observable
behavior, review the diff, and ship the regenerated records in the same
PR as the behavior change. The async plane port must then be updated to
reproduce the new records.
"""

import json
import os
import sys

from hosted.push_sweep_port import conformance, scenarios


def main():
    os.makedirs(conformance.RECORDED_DIR, exist_ok=True)
    names = scenarios.scenario_names()
    for scenario in scenarios.SCENARIOS:
        record = conformance.run_scenario(scenario)
        path = conformance.recorded_path(scenario["name"])
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, sort_keys=False)
            fh.write("\n")
        print("recorded %s (%d send_result rows, %d digest rows)" % (
            path,
            len(record["db"]["push_send_results"]),
            len(record["db"]["push_digest_state"])))
    # No orphans: every recorded file maps to a live scenario.
    recorded = {f[:-5] for f in os.listdir(conformance.RECORDED_DIR)
                if f.endswith(".json")}
    orphans = recorded - set(names)
    if orphans:
        print("ERROR: orphan recorded files with no scenario: %s"
              % sorted(orphans), file=sys.stderr)
        return 1
    print("ok: %d scenarios recorded" % len(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
