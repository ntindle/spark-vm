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
        [--ttl-seconds 600]

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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--registry", required=True,
                    help="release registry JSON (releases map)")
    ap.add_argument("--manifest", required=True,
                    help="wave manifest JSON (waves map)")
    ap.add_argument("--freeze", action="store_true",
                    help="publish a fleet-wide freeze (orthogonal to releases)")
    ap.add_argument("--key-id", required=True, help="signing key id (ctl-YYYY-MM)")
    ap.add_argument("--key-file", required=True, help="controller MAC key file (0600)")
    ap.add_argument("--out", required=True, help="where to write gate.json")
    ap.add_argument("--ttl-seconds", type=int, default=DEFAULT_TTL_SECONDS,
                    help="document lease in seconds (default 600)")
    args = ap.parse_args(argv)

    if args.ttl_seconds <= 0:
        sys.exit("ERROR: --ttl-seconds must be positive.")
    registry = _validate_registry(_load_json(args.registry, "registry"))
    manifest = _validate_manifest(_load_json(args.manifest, "manifest"))
    key = _load_key(args.key_file)

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
