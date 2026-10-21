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
        # The `reason` line's vocabulary is load-bearing: `freeze flag set`
        # (operator-set freeze) is matched verbatim by
        # deploy/auto-deploy.sh's gate verdicts (fleet-freeze), while
        # `no-signal: ...` means the gate is unverifiable and deliberately
        # carries no verdict. Keep both wordings stable or update the
        # consumer in the same change.

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
import errno
import hashlib
import hmac
import json
import os
import re
import stat
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
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError is a ValueError sibling, not an OSError: a
        # non-UTF-8 identity file must be no-signal, not a traceback (the
        # same decode-hole class the publisher's _read_previous_freeze
        # closed in #1543's Engineering B1).
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
        # O_NOFOLLOW + fstat-on-fd (the gate_publish._load_key discipline):
        # a pre-planted symlink at the key path fails loud as no-signal
        # instead of redirecting the read, and the group/other check cannot
        # be raced between stat and open.
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise NoSignal(f"key for {key_id} is a symlink — refusing "
                               "(key files must be real files, mode 0600)")
            raise NoSignal(f"cannot read key for {key_id}: {exc}")
        with os.fdopen(fd, "rb") as fh:
            st = os.fstat(fh.fileno())
            if st.st_mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP |
                             stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH):
                # Same refusal as gate_publish._load_key: the MAC is symmetric,
                # so every box holds the fleet *signing* key — a group/other-
                # readable key file hands minting power to any local user.
                raise NoSignal(f"key file for {key_id} is readable by "
                               "group/other — gate keys must be mode 0600")
            try:
                # Exact bytes are the key; trailing CR/LF bytes are stripped
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
    except (OSError, ValueError) as exc:
        # ValueError covers JSON syntax errors (JSONDecodeError) AND
        # non-UTF-8 bytes (UnicodeDecodeError is a ValueError sibling, not
        # an OSError — the #1543 Engineering-B1 class): a non-UTF-8
        # gate document must be no-signal, not a traceback.
        raise NoSignal(f"gate document unreadable: {exc}")
    if not isinstance(doc, dict):
        raise NoSignal("gate document is not a JSON object")
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise NoSignal(f"unsupported schema_version {doc.get('schema_version')!r}")
    body = {k: v for k, v in doc.items() if k != "hmac"}
    mac = doc.get("hmac")
    if not isinstance(mac, str) or not mac:
        raise NoSignal("gate document carries no hmac")
    if not mac.isascii():
        # hmac.compare_digest rejects non-ASCII str with TypeError; a
        # non-ASCII hmac must be no-signal, not a traceback (QA B1).
        raise NoSignal("gate document hmac is not ASCII")
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
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        # OverflowError: json accepts Infinity as an extension; int(inf)
        # raises OverflowError, not ValueError (Engineering round-3 note).
        raise NoSignal(f"gate document has bad issued_at/ttl_seconds: {exc}")
    age = (datetime.now(timezone.utc) - issued).total_seconds()
    if age < -60:
        raise NoSignal("gate document issued_at is in the future (clock skew?)")
    if age > ttl:
        raise NoSignal(f"gate document expired {age - ttl:.0f}s past ttl={ttl}s")
    return key_id


def box_wave(box_id: str, wave: dict) -> int:
    """This box's wave number: assignment pin, else hash_mod_4 default (§2).

    A malformed assignment pin (non-integer) is no-signal: the wave data
    cannot be trusted, and a guessing box is a fail-open risk — so the box
    freezes instead of evaluating a wave it cannot parse (QA B2)."""
    if not isinstance(wave, dict):
        # The _my_wave display path in answer() hands us the raw per-
        # component entry, which may be null — a non-object wave is not a
        # wave we can evaluate (Engineering delta nit, same class).
        raise NoSignal("wave entry is not an object")
    assignments = wave.get("assignments") or {}
    if not isinstance(assignments, dict):
        # A truthy non-dict assignments field (True, 5, a list) is not a
        # pin map; the `in` membership test below would TypeError on it
        # (Security round-3 note). No honest pin can be read — no-signal.
        # Deliberate asymmetry with the canary path (Engineering round-4):
        # canary is pin-only, so an unreadable pin map means "no pins" and
        # the component is simply denied; here a wave NUMBER must be
        # returned and none can be computed honestly, so the box freezes
        # instead of guessing. Both directions are fail-closed.
        raise NoSignal("wave assignments is not an object")
    if box_id in assignments:
        try:
            return int(assignments[box_id])
        except (TypeError, ValueError, OverflowError):
            # OverflowError: json accepts Infinity/NaN as extensions; a
            # non-finite pin is as malformed as a non-integer one (Security
            # delta note).
            raise NoSignal(f"wave assignment for {box_id!r} is not a wave "
                           f"number: {assignments[box_id]!r}")
    return int(hashlib.sha256(box_id.encode("utf-8")).hexdigest(), 16) % 4


def _canary_pin(box_id: str, wave: dict) -> int | None:
    """This box's canary assignment pin, or None when the box has no pin.

    Shared by the canary enforcement path (component_permitted) and the
    canary `_my_wave` display path (answer): one pin reader, so display
    can never disagree with enforcement about which cohort the box is in
    (#1718). A truthy non-dict assignments field (e.g. a list) is not a
    pin map at all — treat it as no pins, so nobody is admitted (the
    fail-closed direction for canary; QA round-2 note). A malformed pin
    is no-signal (same fail-closed reasoning as box_wave).
    """
    assign = wave.get("assignments")
    pin_src = assign if isinstance(assign, dict) else {}
    if box_id not in pin_src:
        return None
    try:
        return int(pin_src[box_id])
    except (TypeError, ValueError, OverflowError):
        raise NoSignal(f"canary assignment for {box_id!r} is malformed")


def component_permitted(box_id: str, comp: str, waves: dict) -> bool:
    """May this box converge to the component's max-permitted version?"""
    wave = waves.get(comp)
    if not isinstance(wave, dict):
        return False
    state = wave.get("state")
    if not isinstance(state, str) or state not in LIVE_STATES:
        # A non-string state (e.g. a list) is unhashable — `in` on the
        # LIVE_STATES set would TypeError. "Not a live state" is already
        # the fail-closed outcome, so no freeze is needed (Security
        # round-3 note).
        return False
    if state == "canary":
        # Canary is pin-only: only boxes assigned wave 1 are in the canary.
        # The None case is the not-pinned direction — a box with no pin is
        # simply denied (QA round-2 note); a malformed pin raises NoSignal
        # from _canary_pin, freezing the whole answer.
        return _canary_pin(box_id, wave) == 1
    try:
        ceiling = int(wave.get("live", 0))
    except (TypeError, ValueError, OverflowError):
        # A malformed live ceiling names no real cohort — no-signal rather
        # than a ValueError traceback (QA B2).
        raise NoSignal(f"wave live ceiling for {comp!r} is malformed")
    return box_wave(box_id, wave) <= ceiling


def _canary_wave_display(box_id: str, wave: dict) -> str:
    """Honest `_my_wave` for a canary component: the pin, not the hash cohort.

    Canary admission is pin-only, so the hash_mod_4 cohort that box_wave()
    computes names a cohort the box is not actually in (#1718). Report the
    box's own assignment pin instead (the admission decision itself lives
    in `<comp>_permitted`; a denied box's pin is still the pin, not a
    cohort it belongs to). A box with no pin has no canary cohort: reported
    as "" (the same empty convention as `<comp>_max` when no release is
    named), never the hash cohort. A malformed pin raises NoSignal — the
    whole answer freezes, matching the enforcement path.
    """
    pin = _canary_pin(box_id, wave)
    return "" if pin is None else str(pin)


def answer(gate_path: str, box_id: str, keys: dict) -> dict:
    """Full self-evaluated answer. Never raises NoSignal: no-signal -> frozen.

    The whole evaluation — load, MAC+TTL verify, and wave evaluation —
    sits inside the no-signal net, so a malformed-but-signed document
    freezes the box instead of raising (QA B2: int() on a non-integer wave
    pin or live ceiling raises NoSignal from box_wave/component_permitted,
    and it lands here)."""
    try:
        gate = load_gate(gate_path)
        key_id = verify_gate(gate, keys)
        doc = gate["doc"]
        # The doc reached here through verify_gate, which parsed issued_at
        # identically — the parse cannot fail (QA nit: the old try/except
        # age=-1 fallback was uncoverable dead code).
        issued = datetime.strptime(doc["issued_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        age = int((datetime.now(timezone.utc) - issued).total_seconds())
        freeze = bool(doc.get("freeze"))
        waves = doc.get("waves", {})
        if waves and not isinstance(waves, dict):
            # A truthy non-dict waves section is corrupt — the per-component
            # lookups below cannot evaluate it honestly (QA round-2 note).
            raise NoSignal("gate document waves is not an object")
        waves = waves or {}
        releases = doc.get("releases", {})
        if releases and not isinstance(releases, dict):
            raise NoSignal("gate document releases is not an object")
        releases = releases or {}
        out = {"state": "frozen" if freeze else "live",
               "freeze": "true" if freeze else "false",
               "reason": "freeze flag set" if freeze else "gate ok",
               "key_id": key_id, "answer_age_s": str(age)}
        for comp in ("repo", "toolset", "image"):
            permitted = (not freeze) and component_permitted(box_id, comp,
                                                             waves)
            out[f"{comp}_permitted"] = "true" if permitted else "false"
            rel = releases.get(comp) or {}
            if not isinstance(rel, dict):
                # A truthy non-dict per-component release entry cannot be
                # read honestly (Security round-3 note) — no-signal.
                raise NoSignal(
                    f"release entry for {comp!r} is not an object")
            out[f"{comp}_max"] = str(rel.get("max_permitted_commit")
                                     or rel.get("max_permitted_pin")
                                     or rel.get("max_permitted_image_version")
                                     or "")
            wave_entry = waves.get(comp, {})
            if (isinstance(wave_entry, dict)
                    and wave_entry.get("state") == "canary"):
                # Canary is pin-only: box_wave()'s hash_mod_4 cohort names a
                # cohort the box is not actually in — report the pin (or ""
                # when the box has no pin), never the hash cohort (#1718).
                out[f"{comp}_my_wave"] = _canary_wave_display(box_id,
                                                             wave_entry)
            else:
                out[f"{comp}_my_wave"] = str(box_wave(box_id, wave_entry))
        return out
    except NoSignal as exc:
        return {"state": "frozen", "freeze": "true",
                "reason": f"no-signal: {exc}",
                "key_id": "", "answer_age_s": "-1"}


def _gate_path(args) -> str:
    return args.gate or os.environ.get("SPARKVM_GATE_JSON") or DEFAULT_GATE_JSON


# Every boundary Python's str.splitlines() splits on. The four known
# consumers of this stream split only on \r/\n/\r\n (verified in #1856):
# gate_hook.sh's three line-oriented parses and auto-deploy.sh's sed parse.
# The surplus stripping beyond the known consumers' set is defense-in-depth
# for a future splitlines() consumer (the #1412 precedent). Single registry
# of the line-boundary assumption, mirroring the #1432
# single-reader-registry discipline.
_LINE_BOUNDARIES = re.compile("[\x0b\x0c\x1c-\x1e\x85\u2028\u2029\r\n]")


def _oneline(value) -> str:
    """Collapse a key=value field to one physical line (#1856).

    `gate_query.py state` prints a key=value stream that `gate_hook.sh`
    parses with line-oriented `split("=", 1)` in three places (the
    transition gate, the status-file writer, and the journal emit-side —
    all last-occurrence-wins). A value containing a line boundary would
    let a later phantom line overwrite `state` — so every field is
    collapsed to a single line at the producer, the one choke point all
    three parsers read from. The full splitlines() boundary set is
    stripped (see _LINE_BOUNDARIES), not just \r/\n, so a future
    splitlines()-based consumer is safe too; other control characters
    are left to the consumers' own scrub rules.
    """
    return _LINE_BOUNDARIES.sub("", str(value))


def cmd_state(args) -> int:
    box_id = resolve_box_id(args)
    keys = resolve_keys(args)
    ans = answer(_gate_path(args), box_id, keys)
    for k, v in ans.items():
        print(f"{_oneline(k)}={_oneline(v)}")
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
        # _oneline on the reason: the exception message can carry
        # operator-controlled text (key paths, OSError strings), and this
        # stream is parsed line-wise by gate_hook.sh (#1856).
        print(f"state=frozen\nfreeze=true\nreason=no-signal: {_oneline(exc)}",
              file=sys.stdout)
        return 0


if __name__ == "__main__":
    sys.exit(main())
