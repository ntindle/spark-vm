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
    assert patterns == {"hidden_files/", "workspace/goals"}


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


def test_default_path_resolves_to_repo_root():
    """The bare `cd scripts && ./lint-changelog-ritual.py` workflow must work —
    the default changelog resolves relative to the script, not the cwd."""
    lint = _load_lint()
    # The default resolves to <repo>/CHANGELOG.md regardless of cwd.
    assert os.path.basename(lint.CHANGELOG) == "CHANGELOG.md"
    assert os.path.dirname(os.path.dirname(os.path.abspath(_LINT_PATH))) == os.path.dirname(
        os.path.abspath(lint.CHANGELOG)
    )


def test_missing_release_heading_is_a_violation():
    """A changelog with no `## [` heading must not pass vacuously."""
    lint = _load_lint()
    violations = lint.find_violations("# Changelog\n\n- Clean entry. (#1)\n")
    assert len(violations) == 1
    assert "no release heading" in violations[0][2]


def test_heading_without_space_is_recognized():
    lint = _load_lint()
    text = "##[Unreleased]\n\n- Clean entry. (#1)\n"
    assert lint.find_violations(text) == []
    text = "##[Unreleased]\n\n- Entry with `agent_notes/` path. (#1)\n"
    assert len(lint.find_violations(text)) == 1


def test_slashless_workspace_mention_is_flagged():
    """`see the agent_notes workspace` (no trailing slash) is still internal."""
    lint = _load_lint()
    text = _changelog(["- Filed from the agent_notes workspace. (#1)"])
    violations = lint.find_violations(text)
    assert len(violations) == 1
    assert violations[0][1] == "agent_notes"


def test_extra_cli_args_are_an_error():
    r = subprocess.run(
        [sys.executable, _LINT_PATH, "a.md", "b.md"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2
    assert "usage" in r.stderr


def test_unreadable_encoding_is_exit_2_not_traceback():
    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, "CHANGELOG.md")
        with open(bad, "wb") as fh:
            fh.write(b"## [Unreleased]\n\n- \xff\xfe not utf-8\n")
        r = subprocess.run(
            [sys.executable, _LINT_PATH, bad],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 2
        assert "cannot read" in r.stderr


# --- Rule 7: Unreleased section-shape checks (duplicate / order) ---


def _changelog_blocks(blocks):
    """Build a changelog with explicit section headings per release block.

    ``blocks`` is [(heading, [(section, [entries])]), ...].
    """
    parts = ["# Changelog", ""]
    for heading, sections in blocks:
        parts += [heading, ""]
        for section, entries in sections:
            parts += ["### " + section, ""]
            parts += entries
            parts += [""]
    return "\n".join(parts)


def test_duplicate_section_heading_in_unreleased_flagged():
    lint = _load_lint()
    text = _changelog_blocks(
        [
            (
                "## [Unreleased]",
                [
                    ("Added", ["- New thing. (#1)"]),
                    ("Added", ["- Older thing. (#2)"]),
                ],
            )
        ]
    )
    violations = lint.find_violations(text)
    assert len(violations) == 1
    lineno, kind, excerpt = violations[0]
    assert kind == "duplicate section heading"
    assert "### Added" in excerpt
    assert "first at line 5" in excerpt


def test_duplicate_section_heading_is_case_insensitive():
    lint = _load_lint()
    text = _changelog_blocks(
        [
            (
                "## [Unreleased]",
                [
                    ("Added", ["- New thing. (#1)"]),
                    ("added", ["- Older thing. (#2)"]),
                ],
            )
        ]
    )
    violations = lint.find_violations(text)
    assert len(violations) == 1
    assert violations[0][1] == "duplicate section heading"


def test_out_of_order_sections_in_unreleased_flagged():
    lint = _load_lint()
    text = _changelog_blocks(
        [
            (
                "## [Unreleased]",
                [
                    ("Added", ["- New thing. (#1)"]),
                    ("Security", ["- Fix. (#2)"]),
                    ("Fixed", ["- Fix. (#3)"]),
                ],
            )
        ]
    )
    violations = lint.find_violations(text)
    assert len(violations) == 1
    lineno, kind, excerpt = violations[0]
    assert kind == "section heading out of order"
    assert "### Fixed" in excerpt


def test_skipped_section_kinds_are_not_out_of_order():
    """Added, Fixed, Security (no Changed/Deprecated/Removed) is fine."""
    lint = _load_lint()
    text = _changelog_blocks(
        [
            (
                "## [Unreleased]",
                [
                    ("Added", ["- New thing. (#1)"]),
                    ("Fixed", ["- Fix. (#2)"]),
                    ("Security", ["- Hardening. (#3)"]),
                ],
            )
        ]
    )
    assert lint.find_violations(text) == []


def test_full_canonical_order_is_clean():
    lint = _load_lint()
    text = _changelog_blocks(
        [
            (
                "## [Unreleased]",
                [
                    ("Added", ["- New thing. (#1)"]),
                    ("Changed", ["- Change. (#2)"]),
                    ("Deprecated", ["- Deprecation. (#3)"]),
                    ("Removed", ["- Removal. (#4)"]),
                    ("Fixed", ["- Fix. (#5)"]),
                    ("Security", ["- Hardening. (#6)"]),
                ],
            )
        ]
    )
    assert lint.find_violations(text) == []


def test_unrecognized_section_name_is_not_order_checked():
    """A one-off heading like ### Notes is still duplicate-checked but has
    no canonical order position, so it never trips the order rule."""
    lint = _load_lint()
    text = _changelog_blocks(
        [
            (
                "## [Unreleased]",
                [
                    ("Added", ["- New thing. (#1)"]),
                    ("Notes", ["- Note. (#2)"]),
                    ("Fixed", ["- Fix. (#3)"]),
                ],
            )
        ]
    )
    assert lint.find_violations(text) == []
    text2 = _changelog_blocks(
        [
            (
                "## [Unreleased]",
                [
                    ("Notes", ["- Note. (#1)"]),
                    ("Notes", ["- Note. (#2)"]),
                ],
            )
        ]
    )
    violations = lint.find_violations(text2)
    assert len(violations) == 1
    assert violations[0][1] == "duplicate section heading"


def test_section_shape_checks_are_unreleased_scoped():
    """Released blocks are grandfathered: duplicates and disorder below a
    ## [x.y.z] heading are not violations."""
    lint = _load_lint()
    text = _changelog_blocks(
        [
            (
                "## [Unreleased]",
                [
                    ("Added", ["- New thing. (#1)"]),
                    ("Fixed", ["- Fix. (#2)"]),
                ],
            ),
            (
                "## [0.9.0] - 2026-10-18",
                [
                    ("Added", ["- Old thing. (#3)"]),
                    ("Fixed", ["- Old fix. (#4)"]),
                    ("Added", ["- Older thing. (#5)"]),
                ],
            ),
        ]
    )
    assert lint.find_violations(text) == []


def test_no_unreleased_heading_means_no_shape_check():
    lint = _load_lint()
    text = _changelog_blocks(
        [
            (
                "## [0.9.0] - 2026-10-18",
                [
                    ("Added", ["- Old thing. (#3)"]),
                    ("Added", ["- Older thing. (#5)"]),
                ],
            )
        ]
    )
    assert lint.find_violations(text) == []


def test_cli_reports_section_violations_clearly():
    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, "CHANGELOG.md")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write(
                _changelog_blocks(
                    [
                        (
                            "## [Unreleased]",
                            [
                                ("Added", ["- New thing. (#1)"]),
                                ("Added", ["- Older thing. (#2)"]),
                            ],
                        )
                    ]
                )
            )
        r = subprocess.run(
            [sys.executable, _LINT_PATH, bad],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 1
        assert "duplicate section heading" in r.stdout
        assert "workspace-internal path" not in r.stdout


def test_cli_missing_heading_label_is_not_a_path_label():
    """A heading-less changelog must not print as a 'workspace-internal
    path' violation — the label should say what is actually wrong."""
    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, "CHANGELOG.md")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("# Changelog\n\n- Entry with no release heading. (#1)\n")
        r = subprocess.run(
            [sys.executable, _LINT_PATH, bad],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 1
        assert "missing release heading" in r.stdout
        assert "workspace-internal path" not in r.stdout
