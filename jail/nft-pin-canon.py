#!/usr/bin/env python3
"""Canonicalize `nft --json list table` output for the jail firewall pin.

Issue #444 (semantic pin): the watchdog pins the LIVE table against a
BUILD-TIME capture, but the comparison must be semantic, not textual —
nft's text renderer re-words rules across versions (e.g.
`ct state established,related` as `ct state { established, related }`)
and the old text pin turned those re-renderings into false fail-closed
storms. Both sides of the comparison go through the same nft binary's
JSON renderer, so canonicalizing the JSON absorbs renderer variance.

Canonicalization (all of it semantic-preserving):
  - drop every `metainfo` object (carries the nftables version string —
    an nft upgrade would otherwise diff the pin),
  - drop `handle` fields (kernel-assigned rule numbers — not
    enforcement),
  - drop volatile counter READINGS (`packets`/`bytes`) but keep the
    counter statement's presence (a rule carrying a counter still
    matches; its live readings do not identify the rule),
  - sort all dict keys (JSON object order is not significant).

Array order is PRESERVED: rule order IS enforcement in a
policy-accept chain (a drop below an accept is not the same table), so
order diffs must fail closed. String/number/bool scalars compare
verbatim.

Reads stdin, writes the canonical JSON to stdout. Exits nonzero on
invalid or empty input — the watchdog treats a failed capture as
unverifiable and fails closed.
"""

import json
import sys


def _scrub(node):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "handle":
                continue  # kernel-assigned, not enforcement
            out[key] = _scrub(value)
        counter = out.get("counter")
        if isinstance(counter, dict):
            # Presence is enforcement-relevant; readings are volatile.
            out["counter"] = {
                k: v for k, v in counter.items()
                if k not in ("packets", "bytes")
            }
        return out
    if isinstance(node, list):
        return [_scrub(item) for item in node]
    return node


def canonicalize(raw):
    doc = json.loads(raw)  # raises on invalid/empty -> nonzero exit
    tables = doc.get("nftables")
    if not isinstance(tables, list):
        raise ValueError("expected top-level {'nftables': [...]}")
    # metainfo carries the nftables version: an upgrade must not diff.
    scrubbed = [
        obj for obj in (_scrub(item) for item in tables)
        if not (isinstance(obj, dict) and "metainfo" in obj)
    ]
    if not scrubbed:
        raise ValueError("no table content after metainfo strip")
    return json.dumps({"nftables": scrubbed}, sort_keys=True,
                      separators=(",", ":")) + "\n"


def main():
    sys.stdout.write(canonicalize(sys.stdin.read()))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - every failure is fail-closed
        sys.stderr.write("nft-pin-canon: %s\n" % exc)
        sys.exit(1)
