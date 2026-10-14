"""Pin the documented parallel local test path to its dependency and docs.

CONTRIBUTING.md "Parallel runs" tells contributors to run the suite with
`python3 -m pytest -n auto` (pytest-xdist). That advice is only true if
pytest-xdist is actually installed by requirements-test.txt and the
parallel path is documented in both contributor entry points
(CONTRIBUTING.md and docs/CI.md). This pin fails loudly if any leg of
that tripod drifts — a documented command with a missing dependency, or
a dependency with no documented command, both strand the contributor.

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
    """Return the CONTRIBUTING "Parallel runs" section body."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "### Parallel runs":
            return "\n".join(lines[i : i + 40])
    raise AssertionError('CONTRIBUTING.md has no "### Parallel runs" section')


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

    def test_ci_doc_documents_parallel_path(self):
        text = CI_DOC.read_text(encoding="utf-8")
        self.assertIn("-n auto", text, "docs/CI.md must show the -n auto parallel invocation")
        self.assertIn("pytest-xdist", text, "docs/CI.md must name pytest-xdist as the mechanism")


if __name__ == "__main__":
    unittest.main()
