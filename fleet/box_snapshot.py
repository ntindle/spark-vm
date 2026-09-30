#!/usr/bin/env python3
"""Box-side snapshot emitter for the fleet version inventory (G16 / #607).

Emits the small `{repo_commit, gate, arc_active, image_version}` snapshot
the S1 collector (`fleet/inventory.py collect`) reads from each box's
artifact directory. Derives everything from state the updaters already
maintain; nothing is invented for the inventory.

    python3 fleet/box_snapshot.py --checkout /home/ntindle/spark-vm \\
        --out /tmp/box-snapshot/snapshot.json

Never raises and never writes outside --out: unknown fields are null
with a note explaining why, not a crash. The collector treats null as
"not reported" — never as "unknown commit". Stdlib only.

Usage from the operator machine (S1 pull pattern): run over SSH,
saving the stdout or --out file into the box's estate directory as
`snapshot.json` before `fleet/inventory.py collect` runs.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def _git_head(checkout):
    """Deployed commit of the box's spark-vm checkout (design section 2:
    from the deployed commit, not a fresh rev-parse of anything else).
    Returns (commit_or_none, note_or_none)."""
    if not checkout or not os.path.isdir(checkout):
        return None, "checkout dir not present: %r" % (checkout,)
    try:
        proc = subprocess.run(
            ["git", "-C", checkout, "rev-parse", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "git rev-parse failed: %s" % exc
    if proc.returncode != 0:
        # First stderr line, or the exit code when git said nothing
        # (FOLLOW-fleet2: the old `or ["exit %d"]` rendered the list repr
        # "['exit 128']" into the note).
        lines = proc.stderr.strip().splitlines()
        detail = lines[0] if lines else "exit %d" % proc.returncode
        return None, "git rev-parse failed: %s" % detail
    return proc.stdout.strip(), None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Emit the box-side snapshot for the fleet version "
                    "inventory (G16/#607 S1).")
    parser.add_argument("--checkout", default=".",
                        help="path to the box's spark-vm checkout "
                             "(default: cwd)")
    parser.add_argument("--out", default=None,
                        help="write JSON to this file instead of stdout")
    parser.add_argument("--frozen", default=None,
                        help="operator-declared gate state: frozen or "
                             "unfrozen (default: not reported)")
    parser.add_argument("--image-version", default=None,
                        help="tenant image version (default: null — "
                             "in-place updater, not applicable)")
    args = parser.parse_args(argv)

    notes = []
    commit, git_note = _git_head(args.checkout)
    if git_note:
        notes.append(git_note)

    frozen = None
    if args.frozen is not None:
        value = args.frozen.strip().lower()
        if value in ("frozen", "true", "yes", "1"):
            frozen = True
        elif value in ("unfrozen", "false", "no", "0"):
            frozen = False
        else:
            notes.append("unrecognized --frozen value %r; not reported"
                         % args.frozen)

    snapshot = {
        "repo_commit": commit,
        "gate": {"frozen": frozen, "answer_age_s": None},
        "arc_active": None,          # the G15 gate hook's slice (not S1)
        "image_version": args.image_version,  # null = not applicable
        "note": "; ".join(notes) or None,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
    }
    payload = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(payload)
        except OSError as exc:
            print("error: cannot write %s: %s" % (args.out, exc),
                  file=sys.stderr)
            return 2
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
