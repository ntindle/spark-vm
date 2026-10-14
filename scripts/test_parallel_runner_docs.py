"""Pin the documented parallel local test path to its dependency and docs.

CONTRIBUTING.md "Parallel runs" tells contributors to run the suite with
`python3 -m pytest -n auto` (pytest-xdist). That advice is only true if
pytest-xdist is actually installed by requirements-test.txt and the
parallel path is documented in both contributor entry points
(CONTRIBUTING.md and docs/CI.md). This pin fails loudly if any leg of
that tripod drifts — a documented command with a missing dependency, or
a dependency with no documented command, both strand the contributor.

This test pins the markers that the tripod is present, not the measured
numbers or audit claims in the docs — those are verified by the
investigation behind the PR, not by this test.

Pure stdlib, no fixtures: read the three files and check the markers.

Run from the repo root:  python3 -m pytest scripts/test_parallel_runner_docs.py -q
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
CI_DOC = ROOT / "docs" / "CI.md"
REQUIREMENTS = ROOT / "requirements-test.txt"


def _parallel_section(text):
    """Return the CONTRIBUTING "Parallel runs" section body.

    Scans from the section heading to the next same-level heading, so
    the section can grow without tripping a fixed-window false failure.
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "### Parallel runs":
            start = i
            break
    if start is None:
        raise AssertionError('CONTRIBUTING.md has no "### Parallel runs" section')
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("### "):
            end = j
            break
    return "\n".join(lines[start:end])


def _ci_parallel_block(text):
    """Return the docs/CI.md parallel-runs block.

    The block is the contiguous comment/code lines starting at the
    `# parallel local runs` marker through the next blank line. Scoping
    to the block (not the whole file) means deleting the block fails
    the test even if the marker strings survive elsewhere in the file.
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if "parallel local runs" in line:
            start = i
            break
    if start is None:
        raise AssertionError("docs/CI.md has no parallel local runs block")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if not lines[j].strip():
            end = j
            break
    return "\n".join(lines[start:end])


class TestParallelRunnerDocs(unittest.TestCase):
    def test_requirements_installs_pytest_xdist(self):
        lines = REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        xdist = [ln for ln in lines if ln.startswith("pytest-xdist")]
        self.assertEqual(len(xdist), 1, "requirements-test.txt must name pytest-xdist exactly once")
        self.assertIn("-n auto", xdist[0], "pytest-xdist line must point at the documented -n auto command")

    def test_contributing_documents_parallel_path(self):
        section = _parallel_section(CONTRIBUTING.read_text(encoding="utf-8"))
        self.assertIn("-n auto", section, "Parallel runs section must show the -n auto invocation")
        self.assertIn("loadfile", section, "Parallel runs section must name the conservative --dist loadfile variant")
        self.assertIn("order-dependence", section, "Parallel runs section must state the order-dependence rule")
        self.assertIn("#1299", section, "Parallel runs section must name the known hosted/ failure (#1299)")

    def test_ci_doc_documents_parallel_path(self):
        block = _ci_parallel_block(CI_DOC.read_text(encoding="utf-8"))
        self.assertIn("-n auto", block, "CI.md parallel block must show the -n auto invocation")
        self.assertIn("pytest-xdist", block, "CI.md parallel block must name pytest-xdist as the mechanism")
        self.assertIn("unmeasured", block, "CI.md parallel block must warn the full-suite parallel run is unmeasured")


if __name__ == "__main__":
    unittest.main()
