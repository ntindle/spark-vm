"""Tests for scripts/lint-changelog-ritual.py.

Run from the scripts dir, like the rest of this suite:
    cd scripts && python3 -m pytest test_lint_changelog_ritual.py -q
"""

import importlib.util
import os
import subprocess
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LINT_PATH = os.path.join(_HERE, "lint-changelog-ritual.py")


def _load_lint():
    spec = importlib.util.spec_from_file_location("lint_changelog_ritual", _LINT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _changelog(entries, preamble=True):
    head = (
        "# Changelog\n\n## The changelog ritual\n\n"
        "Notes that never land in the repo — e.g. the loop's working notes "
        "in its `agent_notes/` workspace (not part of this repo) — don't get entries.\n\n"
        if preamble
        else "# Changelog\n\n"
    )
    return head + "## [Unreleased]\n\n### Added\n" + "\n".join(entries) + "\n"


def test_clean_changelog_passes():
    lint = _load_lint()
    text = _changelog(
        [
            "- Competitor corpus update: quiet pass — no new findings. (#500)",
            "- H11 multi-tenancy audit: containment mechanism matrix per segment. (#514)",
        ]
    )
    assert lint.find_violations(text) == []


def test_preamble_mention_is_exempt():
    """The ritual preamble names agent_notes/ as its example — not a violation."""
    lint = _load_lint()
    text = _changelog(["- Quiet pass. (#500)"])
    assert "agent_notes/" in text
    assert lint.find_violations(text) == []


def test_agent_notes_capture_in_entry_flagged():
    lint = _load_lint()
    text = _changelog(
        [
            "- Competitor corpus update (two-surveyor pass; captures in "
            "`agent_notes/surveyor-a/b-20260926-2224.md`): quiet pass. (#521)"
        ]
    )
    violations = lint.find_violations(text)
    assert len(violations) == 1
    lineno, pattern, excerpt = violations[0]
    assert lineno == 10
    assert pattern == "agent_notes/"
    assert "surveyor-a" in excerpt


def test_hidden_files_and_workspace_goals_flagged():
    lint = _load_lint()
    text = _changelog(
        [
            "- Reviewed against `hidden_files/RUNLOG.md` before merging. (#520)",
            "- Synced from `workspace/goals/spark-vm/hosted/notes.md`. (#519)",
        ]
    )
    violations = lint.find_violations(text)
    assert len(violations) == 2
    patterns = {v[1] for v in violations}
    assert patterns == {"hidden_files/", "workspace/goals/"}


def test_public_doc_paths_are_allowed():
    """Public repo paths (docs/, scripts/) are fine — the rule targets the
    loop's workspace-internal dirs, not every path."""
    lint = _load_lint()
    text = _changelog(
        [
            "- Field-table row upgraded; see `docs/COMPETITOR_ANALYSIS.md` §2. (#284)",
            "- New `scripts/lint-changelog-ritual.py` enforces the rule. (#525)",
        ]
    )
    assert lint.find_violations(text) == []


def test_cli_exit_codes():
    with tempfile.TemporaryDirectory() as tmp:
        dirty = os.path.join(tmp, "CHANGELOG.md")
        with open(dirty, "w", encoding="utf-8") as fh:
            fh.write(
                _changelog(
                    ["- Update (captures in `agent_notes/x.md`). (#1)"],
                )
            )
        clean = os.path.join(tmp, "CLEAN.md")
        with open(clean, "w", encoding="utf-8") as fh:
            fh.write(_changelog(["- Update. (#1)"]))

        r = subprocess.run(
            [sys.executable, _LINT_PATH, dirty],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 1
        assert "agent_notes/" in r.stdout

        r = subprocess.run(
            [sys.executable, _LINT_PATH, clean],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0
        assert "clean" in r.stdout

        r = subprocess.run(
            [sys.executable, _LINT_PATH, os.path.join(tmp, "MISSING.md")],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 2


def test_lint_is_executable_with_shebang():
    with open(_LINT_PATH, encoding="utf-8") as fh:
        first_line = fh.readline().strip()
    assert first_line == "#!/usr/bin/env python3"
    assert os.access(_LINT_PATH, os.X_OK)
