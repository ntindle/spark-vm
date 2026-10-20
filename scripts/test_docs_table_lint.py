#!/usr/bin/env python3
"""Pin scripts/docs_table_lint.py's W1 wrapped-table-row rule.

Non-vacuity (all verified by neutering, then reverted): dropping the
fragment-detection branch makes the positive tests fail; removing the
fence tracker makes the fenced test fail; requiring delimiter-adjacency
removed makes the prose-pipe test fail.

Run from the repo root: `python3 -m pytest scripts/test_docs_table_lint.py -q`
"""

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docs_table_lint as lint

ROOT = Path(__file__).resolve().parent.parent


def findings_of(text):
    return list(lint.lint_lines(text.splitlines()))


class TestW1WrappedRows(unittest.TestCase):
    def test_flags_wrapped_row_fragment(self):
        text = (
            "| A | B |\n"
            "|---|---|\n"
            "| one | two |\n"
            "| three | four\n"  # row wrapped...
            "  continued here |\n"  # ...fragment line
            "\n"
        )
        findings = findings_of(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][0], 5)  # the fragment line
        self.assertIn("W1", findings[0][1])

    def test_healthy_table_is_clean(self):
        text = (
            "| A | B | C |\n"
            "|---|---|---|\n"
            "| one | two | three |\n"
            "| `code | pipe` | **bold** | [link](https://example.com) |\n"
            "|:--|--:|:-:|\n"  # alignment variant still a delimiter row
            "\n"
        )
        self.assertEqual(findings_of(text), [])

    def test_fenced_code_is_skipped(self):
        # A wrapped-looking fragment inside a fenced code block is code,
        # not prose — the fence tracker must skip it entirely.
        text = (
            "```\n"
            "| A | B |\n"
            "|---|---|\n"
            "| one | two |\n"
            "wrapped fragment |\n"
            "```\n"
        )
        self.assertEqual(findings_of(text), [])

    def test_prose_pipe_lines_are_not_tables(self):
        # A `|`-line with no delimiter row after it is prose (observed in
        # docs/COMPETITOR_ANALYSIS.md's pricing transcriptions), not a
        # table — the lint must not invent a table around it.
        text = (
            "| **Vendor** | claim |\n"
            "in PrimeIntellect-ai's prime-agent repo: CPU $0.05/core-hr\n"
            "$0.01/GB-hr): the composite falls ~58%\n"
            "\n"
        )
        self.assertEqual(findings_of(text), [])

    def test_new_block_after_table_is_not_a_fragment(self):
        text = (
            "| A | B |\n"
            "|---|---|\n"
            "| one | two |\n"
            "\n"
            "## Next section\n"
            "\n"
            "- a list item\n"
            "> a quote\n"
        )
        self.assertEqual(findings_of(text), [])

    def test_heading_directly_after_table_ends_it(self):
        text = (
            "| A | B |\n"
            "|---|---|\n"
            "| one | two |\n"
            "# Heading with no blank line\n"
        )
        self.assertEqual(findings_of(text), [])

    def test_blank_line_ends_table(self):
        text = (
            "| A | B |\n"
            "|---|---|\n"
            "| one | two |\n"
            "\n"
            "plain paragraph after the table\n"
        )
        self.assertEqual(findings_of(text), [])

    def test_row_ending_mid_table_resumes(self):
        # A wrapped row ends the region, but a later real table is still
        # linted — one bad table must not blind the rest of the file.
        text = (
            "| A | B |\n"
            "|---|---|\n"
            "| bad | row\n"
            "fragment |\n"
            "\n"
            "| C | D |\n"
            "|---|---|\n"
            "| fine | row |\n"
        )
        findings = findings_of(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][0], 4)


class TestCliContract(unittest.TestCase):
    def test_usage_error(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "docs_table_lint.py"), "--bogus"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage", proc.stderr)

    def test_root_flag_works_on_alternate_tree(self):
        # B3 (Docs review, 20261020-0529): --root crashed on any real
        # alternate root because lint_paths relativized against the
        # script's own ROOT. A scratch docs tree must lint relative to
        # the passed root.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            docs.mkdir()
            (docs / "ok.md").write_text(
                "| A | B |\n|---|---|\n| one | two |\n"
            )
            (docs / "bad.md").write_text(
                "| A | B |\n|---|---|\n| one | two\nfrag |\n"
            )
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "docs_table_lint.py"),
                 "--root", tmp],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("docs/bad.md:4: W1", proc.stdout)
            self.assertNotIn("ok.md", proc.stdout)

    def test_clean_tree_exits_zero(self):
        # The tree is lint-clean after the W1 fixes shipped alongside the
        # lint: this is the self-enforcing regression pin.
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "docs_table_lint.py")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"lint found live violations: {proc.stdout}",
        )
        self.assertEqual(proc.stdout, "")


class TestModuleSurface(unittest.TestCase):
    def test_stdlib_only(self):
        import ast

        tree = ast.parse((ROOT / "scripts" / "docs_table_lint.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertLessEqual(imported, {"re", "sys", "pathlib"})

    def test_finding_message_mentions_w1(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = lint.main(["docs_table_lint.py", "--root", "/nonexistent"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
