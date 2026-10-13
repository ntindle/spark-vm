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


DEFAULT_GATE_STATUS_FILE = "/var/lib/sparkvm/gate/status.json"


def _parse_generated_at(value):
    """Parse the gate_hook status file's generated_at into an aware datetime.

    Returns (dt_or_none, note_or_none). The hook writes
    "%Y-%m-%dT%H:%M:%SZ"; accept that plus ISO-8601 with offsets.
    Unparseable -> (None, note); the snapshot stays honest (null), not
    invented.
    """
    if not isinstance(value, str) or not value:
        return None, "gate status generated_at missing or not a string"
    text = value.strip()
    # fromisoformat (3.11+) accepts 'Z'; older Pythons need the +00:00 swap.
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        return None, "gate status generated_at unparseable: %r" % (value,)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, None


def _read_gate_status(path):
    """Read the gate_hook status file (S1b, #1325).

    Returns (frozen_or_none, answer_age_s_or_none, note_or_none).
    frozen derives from answer.state ("frozen" -> True, "live" -> False);
    answer_age_s is now - generated_at, floored at 0. The two fields are
    independent: a bad timestamp nulls only the age, a bad state nulls
    only frozen — per-field nulls with notes, never all-or-nothing
    (Engineering review). Anything unreadable -> (None, None, note).
    Never raises.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        return None, None, "gate status file not present: %r" % (path,)
    except (OSError, ValueError, RecursionError) as exc:
        # RecursionError: deeply-nested JSON raises outside (OSError,
        # ValueError); the module contract is "never raises", so it is
        # caught here explicitly (Engineering review).
        return None, None, "gate status file unreadable: %s" % (exc,)
    if not isinstance(payload, dict):
        return None, None, "gate status file is not a JSON object"
    notes = []
    answer = payload.get("answer")
    if isinstance(answer, dict):
        state = answer.get("state")
    else:
        state = None
        notes.append("gate status answer missing or not an object")
    if state == "frozen":
        frozen = True
    elif state == "live":
        frozen = False
    else:
        frozen = None
        notes.append("gate status answer.state not frozen/live: %r" % (state,))
    generated_at, ts_note = _parse_generated_at(payload.get("generated_at"))
    age_s = None
    if generated_at is None:
        notes.append(ts_note)
    else:
        delta_s = (datetime.now(timezone.utc) - generated_at).total_seconds()
        if delta_s < 0:
            # Future timestamp (clock skew): floor at 0 but say so — the
            # module never fabricates an answer silently (Engineering review).
            notes.append("gate status generated_at is in the future; "
                         "answer_age_s floored at 0")
        age_s = int(max(0, delta_s))
    return frozen, age_s, "; ".join(notes) or None


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
                             "unfrozen (default: not reported; overrides "
                             "the gate status file when given)")
    parser.add_argument("--gate-status", default=DEFAULT_GATE_STATUS_FILE,
                        help="gate_hook status file to derive gate.frozen / "
                             "gate.answer_age_s from (default: %s; "
                             "--frozen overrides it)" % DEFAULT_GATE_STATUS_FILE)
    parser.add_argument("--image-version", default=None,
                        help="tenant image version (default: null — "
                             "in-place updater, not applicable)")
    args = parser.parse_args(argv)

    notes = []
    commit, git_note = _git_head(args.checkout)
    if git_note:
        notes.append(git_note)

    frozen = None
    answer_age_s = None
    use_gate_file = True
    if args.frozen is not None:
        value = args.frozen.strip().lower()
        if value in ("frozen", "true", "yes", "1"):
            frozen = True
            use_gate_file = False
        elif value in ("unfrozen", "false", "no", "0"):
            frozen = False
            use_gate_file = False
        else:
            # A typo is not an explicit manual flag — keep the
            # "unrecognized" note but fall through to the gate file so a
            # garbage value cannot silently kill the S1b visibility loop
            # (QA review).
            notes.append("unrecognized --frozen value %r; not reported"
                         % args.frozen)
    if use_gate_file:
        # #1325: the S1b visibility loop — derive from the hook's own
        # status file instead of leaving gate.frozen operator-declared-only.
        frozen, answer_age_s, gate_note = _read_gate_status(args.gate_status)
        if gate_note:
            notes.append(gate_note)

    snapshot = {
        "repo_commit": commit,
        "gate": {"frozen": frozen, "answer_age_s": answer_age_s},
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
