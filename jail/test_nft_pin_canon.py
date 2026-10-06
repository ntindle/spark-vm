"""Unit tests for jail/nft-pin-canon.py (issue #444, semantic pin).

The canonicalizer is the semantic core of the watchdog pin: build-time
and tick-time captures of the same table must compare equal even when
the nft renderer re-words them (different nft version, different key
order, different kernel handles), while any structural change to the
table must compare different. These tests run the real script as a
subprocess on fixture captures.
"""
import json
import os
import subprocess
import sys

import pytest

CANON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "nft-pin-canon.py")


def run_canon(raw):
    return subprocess.run([sys.executable, CANON], input=raw,
                          capture_output=True, text=True)


def canon(doc):
    p = run_canon(json.dumps(doc))
    assert p.returncode == 0, p.stderr
    return p.stdout


def _reverse_keys(node):
    # Simulate a renderer that emits dict keys in the opposite order.
    if isinstance(node, dict):
        return {k: _reverse_keys(v) for k, v in reversed(list(node.items()))}
    if isinstance(node, list):
        return [_reverse_keys(x) for x in node]
    return node


def table_doc(*, version="1.0.9", handle_base=5, reverse_keys=False,
              counter_reads=(123, 456)):
    objs = [
        {"metainfo": {"version": version, "release_name": "Laotzu",
                      "json_schema_version": 1}},
        {"table": {"family": "inet", "name": "jail"}},
        {"chain": {"family": "inet", "table": "jail", "name": "forward",
                   "type": "filter", "hook": "forward", "prio": -10,
                   "policy": "accept"}},
    ]
    rules = [
        {"match": 'iifname "ve-jail" ct state established,related',
         "verdict": "accept"},
        {"match": 'iifname "ve-jail" limit rate 5/minute burst 10 packets',
         "verdict": 'log prefix "jail-fwd-drop: "'},
        {"match": 'iifname "ve-jail"', "verdict": "drop",
         "counter": {"packets": counter_reads[0],
                     "bytes": counter_reads[1]}},
        {"match": 'iifname "tailscale0" tcp dport 2222',
         "verdict": "dnat ip to 10.99.0.2:22"},
    ]
    for i, rule in enumerate(rules):
        objs.append({"rule": {"family": "inet", "table": "jail",
                              "chain": "forward", "handle": handle_base + i,
                              "expr": [rule]}})
    doc = {"nftables": objs}
    return _reverse_keys(doc) if reverse_keys else doc


class TestRendererVarianceAbsorbed:
    def test_metainfo_version_differs_but_table_same(self):
        a = table_doc(version="1.0.9")
        b = table_doc(version="1.1.0")
        assert json.dumps(a) != json.dumps(b)  # the inputs really differ
        assert canon(a) == canon(b)

    def test_key_order_reversed_but_table_same(self):
        a = table_doc()
        b = table_doc(reverse_keys=True)
        assert json.dumps(a) != json.dumps(b)
        assert canon(a) == canon(b)

    def test_handles_differ_but_table_same(self):
        a = table_doc(handle_base=5)
        b = table_doc(handle_base=900)
        assert json.dumps(a) != json.dumps(b)
        assert canon(a) == canon(b)

    def test_counter_readings_differ_but_table_same(self):
        a = table_doc(counter_reads=(123, 456))
        b = table_doc(counter_reads=(999999, 888888))
        assert canon(a) == canon(b)

    def test_all_variance_combined(self):
        # The #444 case: an nft upgrade re-renders everything at once —
        # new version, reversed key order, new handles, ticked counters.
        a = table_doc(version="1.0.9")
        b = table_doc(version="1.1.0", handle_base=900, reverse_keys=True,
                      counter_reads=(999999, 888888))
        assert canon(a) == canon(b)

    def test_idempotent(self):
        a = canon(table_doc())
        p = run_canon(a)
        assert p.returncode == 0, p.stderr
        assert p.stdout == a


class TestStructuralChangeDetected:
    def test_removed_rule_differs(self):
        a = table_doc()
        b = table_doc()
        b["nftables"].pop()  # last rule (the sshd DNAT) deleted
        assert canon(a) != canon(b)

    def test_added_rule_differs(self):
        a = table_doc()
        b = table_doc()
        b["nftables"].append(
            {"rule": {"family": "inet", "table": "jail", "chain": "forward",
                      "handle": 999,
                      "expr": [{"match": 'iifname "ve-jail"',
                                "verdict": "accept"}]}})
        assert canon(a) != canon(b)

    def test_readdressed_dnat_differs(self):
        a = table_doc()
        b = table_doc()
        expr = b["nftables"][-1]["rule"]["expr"][0]
        expr["verdict"] = "dnat ip to 10.99.0.99:22"
        assert canon(a) != canon(b)

    def test_counter_statement_removed_differs(self):
        # The counter statement's PRESENCE is enforcement-relevant (the
        # rule carries a counter); only its readings are volatile.
        a = table_doc()
        b = table_doc()
        expr = b["nftables"][5]["rule"]["expr"][0]
        del expr["counter"]
        assert canon(a) != canon(b)

    def test_rule_order_swapped_differs(self):
        # Rule order IS enforcement in a policy-accept chain: a drop
        # below an accept is not the same table.
        a = table_doc()
        b = table_doc()
        rules = b["nftables"]
        rules[3], rules[5] = rules[5], rules[3]
        assert canon(a) != canon(b)


class TestFailClosedInputs:
    @pytest.mark.parametrize("raw", [
        "",                      # empty capture (nft failed, pin unreadable)
        "not json at all",       # corrupt capture
        '{"foo": 1}',            # wrong top-level shape
        '{"nftables": {}}',       # nftables is not a list
        '{"nftables": [{"metainfo": {"version": "1.0.9"}}]}',
        # metainfo-only: nothing left to compare
    ])
    def test_invalid_input_exits_nonzero(self, raw):
        p = run_canon(raw)
        assert p.returncode != 0
        assert p.stdout == ""
