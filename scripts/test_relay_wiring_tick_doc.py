#!/usr/bin/env python3
"""Pin: docs/RELAY_LIVENESS_WIRING_TICK_OPERATOR.md names the real CLI surface.

The wiring-tick operator doc is the hosted lane's contract for how an
operator drives the relay-liveness tenant-status wiring: the `--tick` CLI
flags, the tick-report JSON schema, the exit codes, and the verbatim
operator-surface notes. When the code's CLI surface changes without the
doc, the doc quietly lies about how to drive the wiring — so these tests
pin the two together:

(a) every `--flag` the doc documents must exist as an `add_argument`
    call in `main()` (a renamed or deleted flag fails the pin);
(b) the doc's flag table must name every flag `main()` accepts, no
    fewer (a new flag the table omits fails);
(c) every report key the doc names (top-level, per-box, reading slice)
    must exist in the dict literals `drive_tenant`/`_reading_summary`
    build (a renamed key fails);
(d) the doc's exit-code table must name 0/1/2, and `main()` must carry
    the `return 0` / `return 1` paths the doc describes (argparse owns
    the exit-2 usage path);
(e) the operator-surface notes the doc quotes must appear in the
    module's string constants — the runtime strings the operator sees,
    with the parser's implicit-concatenation folding applied (a
    reworded note fails);
(f) the doc must name the open tracker (#1711) and the five unbuilt
    auto-cadence slices (#1721-#1725) — the doc is honest about what is
    manual today, not aspirational.

Needle-based on the doc side, AST on the code side. Stdlib-only. Run
from the repo root: `python3 -m pytest scripts/test_relay_wiring_tick_doc.py`.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "RELAY_LIVENESS_WIRING_TICK_OPERATOR.md"
MODULE_PATH = ROOT / "hosted" / "relay_tenant_wiring.py"

# The CLI flags, exactly as add_argument registers them in main().
CLI_FLAGS = (
    "--store",
    "--tick",
    "--history",
    "--journal",
    "--journal-timeout-s",
)

# The tick-report keys the doc names, by report level.
TOP_LEVEL_KEYS = ("tenant_id", "anchor_box_id", "boxes")
BOX_KEYS = ("box_id", "vm_id", "reading", "events", "notes")
READING_KEYS = ("state", "sub_code", "reason", "probe", "journal")

# Verbatim operator-surface notes the doc quotes; each must appear in
# the module source word-for-word.
NOTE_FRAGMENTS = (
    "non-anchor box: reading observed for the operator surface, never applied to the arc",
    "non-anchor instrument read failed",
    "operator surface only; the anchor tick continued",
    "no live-anchor box: reading observed for the operator surface, never applied to the arc",
    "anchor moved between read and apply",
    "reading not applied; next tick re-selects and converges",
)

# Open work the doc is honest about: the auto-cadence tracker and its
# five build slices, all unbuilt.
OPEN_TRACKER = "#1711"
OPEN_SLICES = ("#1721", "#1722", "#1723", "#1724", "#1725")


def _doc():
    return DOC_PATH.read_text(encoding="utf-8")


def _module_ast():
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"))


def _main_fn(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("main() not found in relay_tenant_wiring.py")


def _code_flags():
    """The --flags registered via add_argument in main(), AST-based."""
    main = _main_fn(_module_ast())
    flags = set()
    for node in ast.walk(main):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            flags.add(node.args[0].value)
    return flags


def _dict_keys_in(fn_name, tree):
    """All string keys of dict literals inside the named function."""
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Dict):
                    for k in sub.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            keys.add(k.value)
    return keys


def _return_codes(main):
    codes = set()
    for node in ast.walk(main):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant):
            codes.add(node.value.value)
    return codes


def test_doc_flags_match_cli_flags():
    code_flags = _code_flags()
    assert set(CLI_FLAGS) == code_flags, (
        "doc's flag set %s != main()'s add_argument set %s"
        % (sorted(CLI_FLAGS), sorted(code_flags))
    )
    doc = _doc()
    for flag in CLI_FLAGS:
        assert flag in doc, "doc never documents CLI flag %s" % flag


def test_doc_report_keys_match_code():
    tree = _module_ast()
    drive_keys = _dict_keys_in("drive_tenant", tree)
    for key in TOP_LEVEL_KEYS:
        assert key in drive_keys, "doc names top-level key %r not built by drive_tenant" % key
    for key in BOX_KEYS:
        assert key in drive_keys, "doc names per-box key %r not built by drive_tenant" % key
    reading_keys = _dict_keys_in("_reading_summary", tree)
    for key in READING_KEYS:
        assert key in reading_keys, "doc names reading key %r not built by _reading_summary" % key
    doc = _doc()
    for key in TOP_LEVEL_KEYS + BOX_KEYS + READING_KEYS:
        assert '"%s"' % key in doc or "`%s`" % key in doc, (
            "doc claims report key %r but never names it" % key
        )


def test_doc_exit_codes_match_code():
    codes = _return_codes(_main_fn(_module_ast()))
    assert 0 in codes and 1 in codes, (
        "main() must carry the documented return-0 / return-1 paths, found %s" % sorted(codes)
    )
    doc = _doc()
    for row in ("| 0 |", "| 1 |", "| 2 |"):
        assert row in doc, "doc's exit-code table lost row %s" % row


def _string_constants(tree):
    """Every string constant in the module, implicit concatenation folded
    by the parser — i.e. the runtime note strings the operator sees."""
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_doc_notes_are_verbatim():
    consts = _string_constants(_module_ast())
    doc = _doc()
    for frag in NOTE_FRAGMENTS:
        assert any(frag in c for c in consts), (
            "module no longer carries note fragment %r" % frag
        )
        assert frag in doc, "doc quotes a note fragment it does not contain: %r" % frag


def test_doc_names_open_work():
    doc = _doc()
    assert OPEN_TRACKER in doc, "doc lost the open auto-cadence tracker %s" % OPEN_TRACKER
    for sl in OPEN_SLICES:
        assert sl in doc, "doc lost the unbuilt auto-cadence slice %s" % sl
