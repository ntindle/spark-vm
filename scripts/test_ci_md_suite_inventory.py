"""Pin docs/CI.md's local pytest instructions to pytest.ini's testpaths.

docs/CI.md's "replicate the CI jobs locally" block once enumerated a
per-directory subset of the suites (7 of 14 testpaths dirs, as
`cd <dir> && python3 -m pytest <files>`) under a "(same invocations CI
runs)" comment while the `python-tests` job ran the repo-root one-liner,
and the "Adding a new test suite" paragraph told contributors to "add one
pytest step to the python-tests job" — a CI model that no longer exists.
The block now leads with the repo-root one-liner and points at
CONTRIBUTING.md's component table (itself pinned to testpaths) for the
per-component inventory. This pin fails if the block ever goes back to
`cd`-scoped pytest invocations, if a per-component invocation names a dir
outside testpaths, or if the stale per-step instruction resurfaces.

Pure stdlib, no fixtures. Run from the repo root:
  python3 -m pytest scripts/test_ci_md_suite_inventory.py -q
"""

import configparser
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_MD = ROOT / "docs" / "CI.md"
PYTEST_INI = ROOT / "pytest.ini"

# The instruction from the per-step CI model. Any resurrection of it —
# however reworded around these tokens — fails the pin.
STALE_PER_STEP_RE = re.compile(r"add one `?pytest`? step", re.IGNORECASE)
# The drifted shape: per-directory invocations instead of the one-liner.
CD_PYTEST_RE = re.compile(r"^\s*cd\s+[^\s&|;]+\s*&&\s*python3\s+-m\s+pytest\b", re.MULTILINE)
# The blessed shape: the repo-root one-liner (flags only, no targets).
ONE_LINER_RE = re.compile(r"^\s*python3\s+-m\s+pytest(?:\s+-[^\s]+)*\s*$", re.MULTILINE)
# Per-component invocations from the repo root: `python3 -m pytest <dir>`.
# NOTE: the arg group is [ \t]-local on purpose: \s would span newlines and
# let the first match gobble the whole block, after which the one-liner skip
# below would swallow every per-component invocation unexamined.
BARE_PYTEST_RE = re.compile(r"^\s*python3\s+-m\s+pytest((?:[ \t]+[^\s]+)+)[ \t]*$", re.MULTILINE)


def get_testpaths():
    parser = configparser.ConfigParser()
    parser.read(PYTEST_INI)
    raw = parser.get("pytest", "testpaths")
    paths = [line.strip().rstrip("/") for line in raw.splitlines() if line.strip()]
    if not paths:
        raise AssertionError("pytest.ini [pytest] testpaths is empty")
    return paths


def get_local_run_block():
    text = CI_MD.read_text(encoding="utf-8")
    anchor = "# replicate the CI jobs locally"
    idx = text.find(anchor)
    if idx < 0:
        raise AssertionError("docs/CI.md lost its 'replicate the CI jobs locally' section")
    fence = text.find("```sh", idx)
    if fence < 0:
        raise AssertionError("docs/CI.md local-run section has no sh fenced block")
    end = text.find("```", fence + 5)
    if end < 0:
        raise AssertionError("docs/CI.md local-run sh block is unterminated")
    return text[fence + 5 : end]


def first_positional_arg(arg_string):
    for tok in arg_string.split():
        if tok.startswith("-"):
            continue
        return tok
    return None


class TestCiMdSuiteInventory(unittest.TestCase):
    def test_no_stale_per_step_instruction(self):
        text = CI_MD.read_text(encoding="utf-8")
        m = STALE_PER_STEP_RE.search(text)
        assert not m, (
            "docs/CI.md resurrects the stale per-step CI model "
            f"({m.group(0)!r}); suites are wired via pytest.ini testpaths now"
        )

    def test_block_leads_with_one_liner(self):
        block = get_local_run_block()
        assert ONE_LINER_RE.search(block), (
            "docs/CI.md's local-run block lost the repo-root one-liner "
            "`python3 -m pytest`; contributors must replicate the exact "
            "invocation the python-tests job runs"
        )

    def test_no_cd_scoped_pytest_invocations(self):
        block = get_local_run_block()
        bad = CD_PYTEST_RE.findall(block)
        assert not bad, (
            "docs/CI.md regressed to cd-scoped pytest invocations — the "
            "drifted shape that once enumerated 7 of 14 testpaths dirs: "
            f"{bad}. Suite runs go through the repo-root one-liner; "
            "single-test checks name the file from the repo root."
        )

    def test_bare_component_invocations_name_real_testpaths(self):
        block = get_local_run_block()
        testpaths = get_testpaths()
        bad = []
        for m in BARE_PYTEST_RE.finditer(block):
            arg = first_positional_arg(m.group(1))
            if arg is not None:
                arg = arg.rstrip("/")  # `pytest proxy/` names the same dir
            if arg is None or arg.endswith(".py") or ONE_LINER_RE.match(m.group(0)):
                continue  # the one-liner, or a file-level invocation
            if arg not in testpaths:
                bad.append(arg)
        assert not bad, (
            "docs/CI.md per-component pytest invocations name dirs outside "
            f"pytest.ini testpaths: {bad}"
        )

    def test_block_still_names_testpaths(self):
        # Anti-vacuity: the doc must keep pointing at the inventory
        # mechanism, so gutting the section can't pass the pin.
        text = CI_MD.read_text(encoding="utf-8")
        assert "testpaths" in text, (
            "docs/CI.md no longer names pytest.ini testpaths as the suite "
            "inventory mechanism"
        )
        assert get_local_run_block().strip(), "docs/CI.md local-run sh block is empty"
