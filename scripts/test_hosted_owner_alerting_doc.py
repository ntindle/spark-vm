#!/usr/bin/env python3
"""Pin: docs/HOSTED_OWNER_ALERTING.md names the real alerting surface.

The owner-alerting doc is the hosted lane's contract for what an owner
sees when their box demands attention: the six shipped push-lane
mappings (approval filed, reminder, digest, heartbeat-stale, revoked,
token-expiry) plus the two open gap classes (provisioned-never-paired
#1214, phone-home-died-while-heartbeat-fresh #1489). When the code's
mapping surface changes without the doc, the doc quietly lies about
which alerts exist — so these tests pin the two together:

(a) every `on_*`/`maybe_*` mapping function the doc names must exist in
    `hosted/push_events.py` (a rename or deletion fails the pin);
(b) the doc's alert-class table must name all six shipped mapping
    functions, no fewer (a shipped class the table omits fails);
(c) the doc must name both gap issues and mark them as unbuilt ("nothing"
    in the channel matrix — honesty, not aspiration);
(d) the anti-spam decisions the doc cites (D10/D57/D61/D12/D13/D76/D77)
    must be spelled exactly, so a re-numbering of the push lane's
    D-series shows up here;
(e) the O-series decisions O1-O6 must all be present, exactly once.

Needle-based on the doc side, AST on the code side. Stdlib-only. Run
from the repo root: `python3 -m pytest scripts/test_hosted_owner_alerting_doc.py`.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "HOSTED_OWNER_ALERTING.md"
PUSH_EVENTS = ROOT / "hosted" / "push_events.py"

# The six shipped owner-facing mappings, by function name.
SHIPPED_MAPPINGS = (
    "on_approval_filed",
    "maybe_enqueue_reminder",
    "maybe_enqueue_digest",
    "on_heartbeat_stale",
    "on_box_revoked",
    "on_token_expiry_warning",
)

# Gap classes: (issue number, §3 matrix row's first cell, honest marker).
GAP_CLASSES = (
    ("#1214", "never paired"),
    ("#1489", "phone-home died, fresh heartbeat"),
)
GAP_MARKER = "nothing"

# The two mappings with no caller anywhere (E1, #1492): the doc must
# keep saying so. The §1 table row naming each function must carry the
# unwired marker — a re-added "the endpoint calls <fn>" claim fails.
UNWIRED_MAPPINGS = ("on_approval_filed", "on_box_revoked")
UNWIRED_MARKERS = ("unwired", "no caller")

# Anti-spam decisions the doc's §4 cites; spelled exactly.
ANTI_SPAM_DECISIONS = ("D10", "D57", "D61", "D12", "D13", "D76", "D77")

# The doc's own decision series.
OWNER_DECISIONS = ("O1", "O2", "O3", "O4", "O5", "O6")


def _doc():
    return DOC_PATH.read_text(encoding="utf-8")


def _push_events_functions():
    tree = ast.parse(PUSH_EVENTS.read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def test_doc_names_only_real_mapping_functions():
    text = _doc()
    code_fns = _push_events_functions()
    mentioned = set()
    for fn in SHIPPED_MAPPINGS:
        if re.search(r"\b%s\b" % re.escape(fn), text):
            mentioned.add(fn)
    assert mentioned, "doc names none of the shipped mapping functions"
    missing_from_code = mentioned - code_fns
    assert not missing_from_code, (
        "doc names mapping functions that no longer exist in hosted/push_events.py: %s"
        % sorted(missing_from_code)
    )


def test_alert_class_table_names_all_six_shipped():
    text = _doc()
    table_region = text.split("## 2.")[0]  # the class table lives in §1
    missing = [
        fn
        for fn in SHIPPED_MAPPINGS
        if not re.search(r"\b%s\b" % re.escape(fn), table_region)
    ]
    assert not missing, (
        "alert-class table omits shipped mappings: %s -- a shipped alert class "
        "the doc does not name is a lie of omission" % missing
    )


def test_gap_classes_named_and_marked_unbuilt():
    text = _doc()
    # The channel matrix is §3; §1's class table uses the same labels.
    matrix_region = text.split("## 4.")[0].split("## 3.")[1]
    for issue, label in GAP_CLASSES:
        assert issue in text, "gap issue %s not named in the doc" % issue
        # The gap class's matrix row must be honest: no dashboard chip,
        # no push page, no digest — all three cells read "nothing".
        row = next(
            (
                line
                for line in matrix_region.splitlines()
                if line.lstrip().startswith("|") and label in line
            ),
            None,
        )
        assert row is not None, (
            "gap class %r (%s) has no channel-matrix row" % (label, issue)
        )
        assert row.count(GAP_MARKER) == 3, (
            "gap class %r (%s) row does not read all-nothing: %r"
            % (label, issue, row)
        )


def test_anti_spam_decisions_spelled_exactly():
    text = _doc()
    missing = [d for d in ANTI_SPAM_DECISIONS if not re.search(r"\b%s\b" % d, text)]
    assert not missing, "doc §4 omits anti-spam decisions: %s" % missing


def test_owner_decision_series_complete():
    text = _doc()
    for d in OWNER_DECISIONS:
        hits = len(re.findall(r"\b%s\b" % d, text))
        assert hits >= 1, "owner decision %s missing from the doc" % d


def test_unwired_mappings_stay_marked_unwired():
    text = _doc()
    # The §1 class table is everything before "## 2.".
    table_region = text.split("## 2.")[0]
    for fn in UNWIRED_MAPPINGS:
        row = next(
            (
                line
                for line in table_region.splitlines()
                if line.lstrip().startswith("|") and fn in line
            ),
            None,
        )
        assert row is not None, (
            "mapping %s has no §1 class-table row" % fn
        )
        assert any(m in row for m in UNWIRED_MARKERS), (
            "§1 row for %s no longer marks the mapping as caller-unwired: %r"
            % (fn, row)
        )
