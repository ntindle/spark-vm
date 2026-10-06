#!/usr/bin/env python3
"""fleet/gate_publish.py — controller side of the G18 release-gating channel.

Reads the release registry (max-permitted versions per component), the wave
manifest (live waves + assignments), and the freeze flag, and emits the
signed `gate.json` the operator sync loop distributes to the estate.

Design: docs/RELEASE_GATE_CHANNEL_DESIGN.md (G18 / #609). This is the S1a
acceptance sketch's controller half: registry + manifest + freeze -> signed
gate.json. No daemons, no inbound ports, no control plane.

The document is a lease, not a decree: HMAC-SHA256 over the canonical body
(keys sorted, UTF-8, compact separators) with the controller key. The key is
provisioned to boxes at install time (0600, root-owned); boxes verify, never
sign. `key_id` names the signing key so rotation is a document field (§5):
during a rotation window the box config holds current + next and the box
accepts either, logging which verified.

Usage:
    python3 fleet/gate_publish.py \
        --registry registry.json \
        --manifest waves.json \
        [--freeze] \
        --key-id ctl-2026-09 \
        --key-file /path/to/controller.key \
        --out gate.json \
        [--ttl-seconds 600] \
        [--rotation-log PATH] [--rotation-stale-days 14]

Rotation reminders (issue #1008): the publisher keeps a controller-side
ledger of key rotations (gate_rotation_log.json next to the registry by
default; key_ids + timestamps only, never key material). Publishing with a
new --key-id opens a rotation window and says so loudly; every later publish
reports still-open windows and warns loudly once a window reaches
--rotation-stale-days (default 14). After runbook step 4 (retire the old key from every
box), close the window with:
    python3 fleet/gate_publish.py --rotation-complete ctl-2026-09
An un-closed window is a permanent second signing key — the ledger makes it
visible instead of silent.

registry.json: {"repo": {"max_permitted_commit": "<40hex>", "channel": "stable"},
                "toolset": {"max_permitted_pin": "2026.09.27", "channel": "stable"},
                "image": {"max_permitted_image_version": "2026.09.29-0", "channel": "stable"}}
waves.json:    {"repo": {"live": 2, "state": "wave-2",
                         "assignments": {"box-07": 1}, "default": "hash_mod_4"}, ...}

Stdlib only. Never prints key material (not even a prefix).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import stat
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = 1
DEFAULT_TTL_SECONDS = 600
COMPONENTS = ("repo", "toolset", "image")
WAVE_STATES = ("draft", "canary", "wave-1", "wave-2", "wave-3", "wave-4",
               "complete", "halted")
REPO_COMMIT_RE = set("0123456789abcdef")
ROTATION_LOG_NAME = "gate_rotation_log.json"
# A rotation window the operator never closes becomes a permanent second
# signing key (issue #1008). The ledger below makes an open window visible:
# each publish either opens a new window (new --key-id) or reports the age
# of the still-open one, warning loudly once it exceeds --rotation-stale-days.
DEFAULT_ROTATION_STALE_DAYS = 14
ROTATION_LEDGER_VERSION = 1


def canonical_body(body: dict) -> bytes:
    """Canonical encoding the MAC covers: sorted keys, UTF-8, compact."""
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _load_key(key_file: str) -> bytes:
    """Load the controller MAC key. Refuses keys readable by group/other."""
    st = os.stat(key_file)
    if st.st_mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP |
                     stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH):
        sys.exit(f"ERROR: key file {key_file} is readable by group/other — "
                 "controller keys must be mode 0600 (see design §5).")
    with open(key_file, "rb") as fh:
        # Exact bytes are the key; one trailing newline is tolerated so an
        # operator's `echo $KEY > file` doesn't silently change the MAC.
        key = fh.read().rstrip(b"\r\n")
    if len(key) < 32:
        sys.exit("ERROR: controller key must be at least 32 bytes.")
    return key


def _load_json(path: str, what: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"ERROR: cannot read {what} {path}: {exc}")
    if not isinstance(data, dict):
        sys.exit(f"ERROR: {what} {path} must be a JSON object.")
    return data


def _validate_registry(registry: dict) -> dict:
    out = {}
    for comp in COMPONENTS:
        entry = registry.get(comp)
        if not isinstance(entry, dict):
            sys.exit(f"ERROR: registry missing component '{comp}'.")
        out[comp] = entry
        if comp == "repo":
            commit = entry.get("max_permitted_commit", "")
            if (not isinstance(commit, str) or len(commit) != 40
                    or any(c not in REPO_COMMIT_RE for c in commit)):
                sys.exit("ERROR: registry repo.max_permitted_commit must be "
                         "a 40-char lowercase hex commit SHA.")
        if entry.get("channel") != "stable":
            sys.exit(f"ERROR: registry {comp}.channel must be 'stable' in S1.")
    extra = set(registry) - set(COMPONENTS)
    if extra:
        sys.exit(f"ERROR: registry has unknown components: {sorted(extra)}")
    return out


def _validate_manifest(manifest: dict) -> dict:
    out = {}
    for comp in COMPONENTS:
        wave = manifest.get(comp)
        if not isinstance(wave, dict):
            sys.exit(f"ERROR: manifest missing waves for '{comp}'.")
        state = wave.get("state")
        if state not in WAVE_STATES:
            sys.exit(f"ERROR: manifest {comp}.state must be one of "
                     f"{WAVE_STATES}, got {state!r}.")
        live = wave.get("live")
        if not isinstance(live, int) or live < 0:
            sys.exit(f"ERROR: manifest {comp}.live must be a non-negative int.")
        assignments = wave.get("assignments", {})
        if (not isinstance(assignments, dict)
                or any(not isinstance(k, str) or type(v) is not int
                       for k, v in assignments.items())):
            sys.exit(f"ERROR: manifest {comp}.assignments must be "
                     "{box_id: wave_number} (plain ints — true/false are not "
                     "wave numbers).")
        if wave.get("default", "hash_mod_4") != "hash_mod_4":
            sys.exit(f"ERROR: manifest {comp}.default must be 'hash_mod_4' "
                     "in S1 (the only supported default).")
        out[comp] = {"live": live, "state": state,
                     "assignments": assignments, "default": "hash_mod_4"}
    extra = set(manifest) - set(COMPONENTS)
    if extra:
        sys.exit(f"ERROR: manifest has unknown components: {sorted(extra)}")
    return out


def build_gate_document(registry: dict, manifest: dict, freeze: bool,
                        key_id: str, ttl_seconds: int) -> dict:
    """Build the unsigned gate document body (§2). Pure; no I/O."""
    return {
        "schema_version": SCHEMA_VERSION,
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ttl_seconds": ttl_seconds,
        "key_id": key_id,
        "freeze": bool(freeze),
        "releases": registry,
        "waves": manifest,
    }


def sign_document(body: dict, key: bytes) -> dict:
    """Return body + 'hmac' (hex HMAC-SHA256 of the canonical body)."""
    doc = dict(body)
    doc["hmac"] = hmac.new(key, canonical_body(body),
                           hashlib.sha256).hexdigest()
    return doc


def _rotation_log_path(args) -> str:
    """Controller-side ledger path. Explicit --rotation-log wins; otherwise
    it sits next to the operator-managed registry (operator-local state,
    key_ids + timestamps only — never key material). In --rotation-complete
    mode without --registry, the current directory is the fallback."""
    if args.rotation_log:
        return args.rotation_log
    if args.registry:
        return os.path.join(os.path.dirname(os.path.abspath(args.registry)),
                            ROTATION_LOG_NAME)
    return ROTATION_LOG_NAME


def _parse_ledger_ts(value):
    """Parse a ledger timestamp ("%Y-%m-%dT%H:%M:%SZ"); None if unparseable."""
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _load_rotation_log(path: str) -> dict:
    """Load the rotation ledger. A missing ledger is a first run (empty).
    A corrupt ledger is LOUD on stderr but never blocks publishing the gate
    document — the ledger is advisory; the document is the release channel.
    Malformed events (wrong shape, unparseable timestamps) are dropped with
    the same loud warning rather than crashing the publish path."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {"ledger_version": ROTATION_LEDGER_VERSION, "rotations": []}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARNING: rotation ledger {path} unreadable ({exc}); "
              "treating as empty. Fix or delete the file to restore "
              "rotation reminders.", file=sys.stderr)
        return {"ledger_version": ROTATION_LEDGER_VERSION, "rotations": []}
    if (not isinstance(data, dict)
            or not isinstance(data.get("rotations"), list)):
        print(f"WARNING: rotation ledger {path} has an unexpected shape; "
              "treating as empty.", file=sys.stderr)
        return {"ledger_version": ROTATION_LEDGER_VERSION, "rotations": []}
    kept = []
    for ev in data["rotations"]:
        if (_parse_ledger_ts(ev.get("opened_at")) is not None
                and isinstance(ev.get("to_key_id"), str)
                and (ev.get("from_key_id") is None
                     or isinstance(ev.get("from_key_id"), str))
                and (ev.get("closed_at") is None
                     or _parse_ledger_ts(ev.get("closed_at")) is not None)):
            kept.append(ev)
        else:
            print(f"WARNING: rotation ledger {path} has a malformed "
                  "rotation event; dropping it. The gate document still "
                  "publishes; fix or delete the file to restore rotation "
                  "reminders.", file=sys.stderr)
    data["rotations"] = kept
    return data


def _save_rotation_log(path: str, log: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(log, fh, sort_keys=True, indent=2, ensure_ascii=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _open_rotations(log: dict):
    """All currently open rotation events, oldest first."""
    return [ev for ev in log["rotations"]
            if ev.get("closed_at") is None and ev.get("from_key_id") is not None]


def _last_key_id(log: dict):
    """Most recent key_id the tool published with, or None (first run)."""
    for ev in reversed(log["rotations"]):
        if ev.get("to_key_id"):
            return ev["to_key_id"]
    return None


def _rotation_age_days(opened_at: str) -> int:
    return (datetime.now(timezone.utc)
            - _parse_ledger_ts(opened_at)).days


def process_rotation(key_id: str, log_path: str, stale_days: int) -> None:
    """Update the rotation ledger for a publish signed with key_id and emit
    reminders. A key change opens a rotation window (loud once, naming the
    old key and the runbook step that closes it); every still-open window is
    reported on every publish, and warned loudly once it goes stale. Chained
    rotations (a new key before the old window closed) keep ALL windows open
    and report each — every un-retired key is a live signing key."""
    log = _load_rotation_log(log_path)
    last = _last_key_id(log)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if last is not None and key_id != last:
        ev = {"from_key_id": last, "to_key_id": key_id, "opened_at": now,
              "closed_at": None}
        log["rotations"].append(ev)
        still_open = [o for o in _open_rotations(log)
                      if o["to_key_id"] != key_id]
        print(f"ROTATION OPEN: documents are now signed with {key_id}; "
              f"{last} is still provisioned on the estate until you finish "
              "runbook step 4 (remove its key_id=/path entry from every "
              "box's SPARKVM_GATE_KEYS), then close the window with: "
              f"gate_publish.py --rotation-complete {last} --rotation-log "
              + log_path, file=sys.stderr)
        for o in still_open:
            print(f"NOTE: an earlier rotation window ({o['from_key_id']} -> "
                  f"{o['to_key_id']}, opened {o['opened_at']}) is STILL "
                  "open; both keys remain valid. Retire each key, then "
                  f"--rotation-complete each.", file=sys.stderr)
    elif last is None:
        # Baseline event on first run (from=None: not a rotation; the
        # ledger starts closed so a plain first publish is quiet).
        log["rotations"].append({"from_key_id": None, "to_key_id": key_id,
                                 "opened_at": now, "closed_at": now})
    else:
        for o in _open_rotations(log):
            age_days = _rotation_age_days(o["opened_at"])
            to_key = o["to_key_id"]
            if age_days >= stale_days:
                print(f"WARNING: key rotation {o['from_key_id']} -> "
                      f"{to_key} has been open for {age_days} days (since "
                      f"{o['opened_at']}) — {o['from_key_id']} is still a "
                      "valid signing key until retired. Finish runbook "
                      "step 4 (remove its key_id=/path entry from every "
                      "box's SPARKVM_GATE_KEYS), then: gate_publish.py "
                      f"--rotation-complete {o['from_key_id']} "
                      "--rotation-log " + log_path, file=sys.stderr)
            else:
                print(f"note: key rotation {o['from_key_id']} -> {to_key} "
                      f"open for {age_days} days (since {o['opened_at']}); "
                      f"retire {o['from_key_id']} per runbook step 4, then "
                      "--rotation-complete.", file=sys.stderr)
    _save_rotation_log(log_path, log)


def close_rotation(old_key_id: str, log_path: str) -> None:
    """Close the open rotation that retired old_key_id (runbook step 4 done).
    Exits non-zero if no such window is open — the operator typed the wrong
    key, or nothing was open to close."""
    log = _load_rotation_log(log_path)
    for ev in reversed(log["rotations"]):
        if (ev.get("from_key_id") == old_key_id
                and ev.get("closed_at") is None):
            ev["closed_at"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            _save_rotation_log(log_path, log)
            print(f"rotation window closed: {old_key_id} retired; "
                  f"{ev['to_key_id']} is the sole signing key.")
            return
    sys.exit(f"ERROR: no open rotation window retiring {old_key_id} "
             f"(ledger: {log_path}).")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--registry",
                    help="release registry JSON (releases map)")
    ap.add_argument("--manifest",
                    help="wave manifest JSON (waves map)")
    ap.add_argument("--freeze", action="store_true",
                    help="publish a fleet-wide freeze (orthogonal to releases)")
    ap.add_argument("--key-id", help="signing key id (ctl-YYYY-MM)")
    ap.add_argument("--key-file", help="controller MAC key file (0600)")
    ap.add_argument("--out", help="where to write gate.json")
    ap.add_argument("--ttl-seconds", type=int, default=DEFAULT_TTL_SECONDS,
                    help="document lease in seconds (default 600)")
    ap.add_argument("--rotation-log", default=None,
                    help="rotation ledger path (default: "
                    "gate_rotation_log.json next to --registry)")
    ap.add_argument("--rotation-stale-days", type=int,
                    default=DEFAULT_ROTATION_STALE_DAYS,
                    help="days an open rotation window may age before the "
                    "publish warns loudly (default "
                    f"{DEFAULT_ROTATION_STALE_DAYS})")
    ap.add_argument("--rotation-complete", metavar="OLD_KEY_ID", default=None,
                    help="close an open rotation window: declare runbook "
                    "step 4 done for OLD_KEY_ID (no document is published). "
                    "The window is located via --rotation-log, else via "
                    "--registry's directory, else ./gate_rotation_log.json "
                    "in the current directory.")
    args = ap.parse_args(argv)

    if args.rotation_complete:
        close_rotation(args.rotation_complete, _rotation_log_path(args))
        return 0

    for flag in ("registry", "manifest", "key_id", "key_file", "out"):
        if not getattr(args, flag):
            sys.exit(f"ERROR: --{flag.replace('_', '-')} is required "
                     "(unless --rotation-complete is used).")
    if args.rotation_stale_days < 0:
        sys.exit("ERROR: --rotation-stale-days must be non-negative.")

    if args.ttl_seconds <= 0:
        sys.exit("ERROR: --ttl-seconds must be positive.")
    registry = _validate_registry(_load_json(args.registry, "registry"))
    manifest = _validate_manifest(_load_json(args.manifest, "manifest"))
    key = _load_key(args.key_file)

    process_rotation(args.key_id, _rotation_log_path(args),
                     args.rotation_stale_days)

    body = build_gate_document(registry, manifest, args.freeze,
                               args.key_id, args.ttl_seconds)
    doc = sign_document(body, key)

    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, sort_keys=True, indent=2, ensure_ascii=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, args.out)
    # The published document is never world-readable: it transits the
    # operator's sync path only (§4), and carries no secrets — but the
    # hmac field is keyed material's output, so 0600 is the honest default.
    os.chmod(args.out, 0o600)
    print(f"wrote {args.out} (freeze={args.freeze} key_id={args.key_id} "
          f"ttl={args.ttl_seconds}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
