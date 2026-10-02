#!/usr/bin/env python3
"""fleet/gate_query.py — box side of the G18 release-gating channel.

Verifies the estate's `gate.json` and answers the box's self-evaluated
release state. This is the tick-time query: the enforcement point of the
G15/G18 rollout design (docs/RELEASE_GATE_CHANNEL_DESIGN.md §3 — the
hook-loop timer in S1b is the latency optimizer and status writer, not the
enforcement point).

Fail-closed (§2, §4): a missing, malformed, bad-MAC, or expired document is
**no-signal -> frozen**. The box never releases itself; a broken sync loop
is a visible incident, not a silent rollout.

Verification (§5): HMAC-SHA256 over the canonical body with one of the
provisioned controller keys. During a rotation window the keys config may
hold current + next; either verifies, and the answer logs which `key_id`
verified. The MAC stops on-path tampering and misconfiguration — not a
rooted fleet member (design §5: the cross-box barrier is delivery-path
ownership, stated plainly in the README).

Self-evaluation (§2): the box knows its own `box_id` (provisioned at
install; G18 §5) and reads the document's wave assignment —
`assignments` pins the exceptions, otherwise `hash_mod_4` (sha256(box_id)
mod 4). A component is permitted for this box when the wave state is
live-ish (canary/wave-N/complete) and the box's wave is at or before the
live wave. `halted`/`draft` and `freeze: true` are never permitted.

Usage:
    gate_query.py state --box-id box-07
        # key=value lines: state=frozen|live, freeze=, answer_age_s=, ...

    gate_query.py permitted repo
        # exit 0 if the repo component may converge on this box right now,
        # exit 1 if this box's wave is not live, exit 2 on no-signal (frozen).

Box identity and keys resolve (in order) from flags, then env:
    --box-id / SPARKVM_BOX_ID (or --box-id-file / SPARKVM_BOX_ID_FILE)
    --keys   / SPARKVM_GATE_KEYS : "key_id=/path/to/key,key_id2=/path/to/key2"
    --gate   / SPARKVM_GATE_JSON (default /var/lib/sparkvm/gate/gate.json)

Stdlib only. Never prints key material.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = 1
DEFAULT_GATE_JSON = "/var/lib/sparkvm/gate/gate.json"

# Wave states in which a component may deploy at all (design §2). Everything
# else (draft, halted) is never permitted, whatever the assignment says.
LIVE_STATES = {"canary"} | {f"wave-{n}" for n in (1, 2, 3, 4)} | {"complete"}


class NoSignal(Exception):
    """The document cannot be trusted: missing, malformed, bad-MAC, expired."""


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError as exc:
        raise NoSignal(f"cannot read {path}: {exc}")


def resolve_box_id(args) -> str:
    if args.box_id:
        return args.box_id
    env = os.environ.get("SPARKVM_BOX_ID")
    if env:
        return env
    path = args.box_id_file or os.environ.get("SPARKVM_BOX_ID_FILE")
    if path:
        box_id = _read_file(path)
        if not box_id:
            raise NoSignal(f"box-id file {path} is empty")
        return box_id
    raise NoSignal("no box identity: pass --box-id (provisioned at install, §5)")


def resolve_keys(args) -> dict:
    """key_id -> key bytes. Accepts a rotation window (current + next)."""
    spec = args.keys or os.environ.get("SPARKVM_GATE_KEYS")
    if not spec:
        raise NoSignal("no gate keys configured: pass --keys "
                       "key_id=/path,key_id2=/path2")
    keys = {}
    for item in spec.split(","):
        item = item.strip()
        if "=" not in item:
            raise NoSignal(f"bad --keys entry (want key_id=/path): {item!r}")
        key_id, path = item.split("=", 1)
        key_id, path = key_id.strip(), path.strip()
        try:
            with open(path, "rb") as fh:
                # Exact bytes are the key; one trailing newline is tolerated
                # (matches gate_publish.py's _load_key — same key bytes both
                # sides, or the MACs will never agree).
                key = fh.read().rstrip(b"\r\n")
        except OSError as exc:
            raise NoSignal(f"cannot read key for {key_id}: {exc}")
        if len(key) < 32:
            raise NoSignal(f"key for {key_id} is shorter than 32 bytes")
        keys[key_id] = key
    return keys


def load_gate(gate_path: str) -> dict:
    """Load and structural-check the document. MAC checked separately."""
    try:
        with open(gate_path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise NoSignal(f"gate document unreadable: {exc}")
    if not isinstance(doc, dict):
        raise NoSignal("gate document is not a JSON object")
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise NoSignal(f"unsupported schema_version {doc.get('schema_version')!r}")
    body = {k: v for k, v in doc.items() if k != "hmac"}
    mac = doc.get("hmac")
    if not isinstance(mac, str) or not mac:
        raise NoSignal("gate document carries no hmac")
    return {"doc": doc, "body": body, "mac": mac}


def verify_gate(gate: dict, keys: dict) -> str:
    """Verify MAC + TTL. Returns the key_id that verified. Raises NoSignal."""
    doc, body, mac = gate["doc"], gate["body"], gate["mac"]
    key_id = doc.get("key_id")
    key = keys.get(key_id) if isinstance(key_id, str) else None
    if key is None:
        raise NoSignal(f"no provisioned key for key_id {key_id!r}")
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    expect = hmac.new(key, canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, mac):
        raise NoSignal("gate document MAC mismatch (on-path tamper or wrong key)")
    try:
        issued = datetime.strptime(doc["issued_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        ttl = int(doc["ttl_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NoSignal(f"gate document has bad issued_at/ttl_seconds: {exc}")
    age = (datetime.now(timezone.utc) - issued).total_seconds()
    if age < -60:
        raise NoSignal("gate document issued_at is in the future (clock skew?)")
    if age > ttl:
        raise NoSignal(f"gate document expired {age - ttl:.0f}s past ttl={ttl}s")
    return key_id


def box_wave(box_id: str, wave: dict) -> int:
    """This box's wave number: assignment pin, else hash_mod_4 default (§2)."""
    assignments = wave.get("assignments") or {}
    if box_id in assignments:
        return int(assignments[box_id])
    return int(hashlib.sha256(box_id.encode("utf-8")).hexdigest(), 16) % 4


def component_permitted(box_id: str, comp: str, waves: dict) -> bool:
    """May this box converge to the component's max-permitted version?"""
    wave = waves.get(comp)
    if not isinstance(wave, dict):
        return False
    if wave.get("state") not in LIVE_STATES:
        return False
    if wave.get("state") == "canary":
        # Canary is pin-only: only boxes assigned wave 1 are in the canary.
        return int(wave.get("assignments", {}).get(box_id, -1)) == 1
    return box_wave(box_id, wave) <= int(wave.get("live", 0))


def answer(gate_path: str, box_id: str, keys: dict) -> dict:
    """Full self-evaluated answer. Never raises NoSignal: no-signal -> frozen."""
    try:
        gate = load_gate(gate_path)
        key_id = verify_gate(gate, keys)
    except NoSignal as exc:
        return {"state": "frozen", "freeze": "true", "reason": f"no-signal: {exc}",
                "key_id": "", "answer_age_s": "-1"}
    doc = gate["doc"]
    try:
        issued = datetime.strptime(doc["issued_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        age = int((datetime.now(timezone.utc) - issued).total_seconds())
    except (KeyError, ValueError):
        age = -1
    freeze = bool(doc.get("freeze"))
    waves = doc.get("waves", {}) or {}
    releases = doc.get("releases", {}) or {}
    out = {"state": "frozen" if freeze else "live",
           "freeze": "true" if freeze else "false",
           "reason": "freeze flag set" if freeze else "gate ok",
           "key_id": key_id, "answer_age_s": str(age)}
    for comp in ("repo", "toolset", "image"):
        permitted = (not freeze) and component_permitted(box_id, comp, waves)
        out[f"{comp}_permitted"] = "true" if permitted else "false"
        rel = releases.get(comp) or {}
        out[f"{comp}_max"] = str(rel.get("max_permitted_commit")
                                 or rel.get("max_permitted_pin")
                                 or rel.get("max_permitted_image_version") or "")
        out[f"{comp}_my_wave"] = str(box_wave(box_id, waves.get(comp, {})))
    return out


def _gate_path(args) -> str:
    return args.gate or os.environ.get("SPARKVM_GATE_JSON") or DEFAULT_GATE_JSON


def cmd_state(args) -> int:
    box_id = resolve_box_id(args)
    keys = resolve_keys(args)
    ans = answer(_gate_path(args), box_id, keys)
    for k, v in ans.items():
        print(f"{k}={v}")
    return 0


def cmd_permitted(args) -> int:
    """Exit 0/1/2: may this box converge <component> at all right now?

    The *which version* question is the updater's: it reads <comp>_max from
    `state` and caps its range by ancestry against its own mirror (the
    pending_range gate cap). The query answers only the permit bit —
    frozen boxes and not-yet-live waves get no version at all.
    """
    comp = args.component
    if comp not in ("repo", "toolset", "image"):
        print("ERROR: component must be repo, toolset, or image", file=sys.stderr)
        return 2
    box_id = resolve_box_id(args)
    keys = resolve_keys(args)
    ans = answer(_gate_path(args), box_id, keys)
    if ans["state"] != "live":
        print(f"frozen: {ans['reason']}", file=sys.stderr)
        return 2
    if ans.get(f"{comp}_permitted") != "true":
        print(f"{comp}: this box's wave is not live", file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--box-id", default=None)
    ap.add_argument("--box-id-file", default=None)
    ap.add_argument("--keys", default=None,
                    help="key_id=/path,key_id2=/path2 (rotation window)")
    ap.add_argument("--gate", default=None, help="gate.json path")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("state", help="print the self-evaluated answer (key=value)")
    p = sub.add_parser("permitted",
                       help="exit 0/1/2: may this box converge <component> now?")
    p.add_argument("component")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "state":
            return cmd_state(args)
        return cmd_permitted(args)
    except NoSignal as exc:
        # Identity/key config failures are also no-signal: without keys or a
        # box id the box cannot evaluate, so it freezes — loudly.
        print(f"state=frozen\nfreeze=true\nreason=no-signal: {exc}",
              file=sys.stdout)
        return 0


if __name__ == "__main__":
    sys.exit(main())
