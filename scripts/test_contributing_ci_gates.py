"""Pin CONTRIBUTING.md's merge-gate inventory to the branch-protection ruleset.

CONTRIBUTING.md's "The merge gate, locally" section once claimed "five more
CI jobs gate the merge" while the branch-protection ruleset already required
eight checks: the shard split (#1138) had added the `shard plan` job and the
`changed-paths gate` without the contributor doc noticing, and neither had a
documented local form. A contributor following the doc could be green locally
and red on CI with no way to see why.

The ruleset JSON (deploy/rulesets/main-branch-protection.json) is the source
of truth. The doc carries its claimed inventory in a
<!-- gate-checks:start --> ... <!-- gate-checks:end --> comment block
(invisible in GitHub's rendered view; visible in raw/edit view) so this pin can compare the two sets exactly. Any
drift fails loudly:
- a required check the doc doesn't name (stale count, missing local form),
- a doc-named check the ruleset no longer requires (dead instruction),
- the "N more CI checks gate the merge" sentence disagreeing with the count,
- a named check with no discussion/local form anywhere in the section.

When the ruleset grows, update the doc's inventory block AND the section
prose (the third test enforces both); the HTML comment above the block says
the same for humans.

Pure stdlib, no fixtures. Run from the repo root:
  python3 -m pytest scripts/test_contributing_ci_gates.py -q
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
RULESET = ROOT / "deploy" / "rulesets" / "main-branch-protection.json"

INVENTORY_RE = re.compile(
    r"<!-- gate-checks:start -->(.*?)<!-- gate-checks:end -->", re.S
)
# The count sentence: "seven more CI checks gate the merge" — more than the
# pytest one-liner, which is the `python tests` check itself. Whitespace is
# normalized before matching so the sentence may wrap across lines.
MORE_SENTENCE_RE = re.compile(r"(\w+)\s+more\s+CI\s+(?:jobs|checks)\s+gate\s+the\s+merge")
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def doc_inventory():
    """The check names the doc claims gate the merge."""
    text = CONTRIBUTING.read_text(encoding="utf-8")
    m = INVENTORY_RE.search(text)
    if not m:
        raise AssertionError(
            "CONTRIBUTING.md lost its <!-- gate-checks:start --> inventory block"
        )
    names = [line.strip() for line in m.group(1).splitlines()]
    names = [n for n in names if n]
    if len(names) != len(set(names)):
        raise AssertionError(
            "duplicate check names in CONTRIBUTING.md's gate inventory"
        )
    return set(names)


def ruleset_contexts():
    """The required status checks the branch-protection ruleset declares."""
    d = json.loads(RULESET.read_text(encoding="utf-8"))
    rules = [r for r in d["rules"] if r["type"] == "required_status_checks"]
    if len(rules) != 1:
        raise AssertionError(
            "expected exactly one required_status_checks rule in the ruleset"
        )
    return {c["context"] for c in rules[0]["parameters"]["required_status_checks"]}


def merge_gate_prose():
    """The merge-gate section with the machine-readable inventory removed.

    Forces the prose to genuinely discuss every check: naming a check only
    in the inventory block does not satisfy this text.
    """
    text = CONTRIBUTING.read_text(encoding="utf-8")
    anchor = "### The merge gate, locally"
    start = text.find(anchor)
    if start < 0:
        raise AssertionError("CONTRIBUTING.md lost its 'The merge gate, locally' section")
    section = text[start:]
    next_h2 = section.find("\n## ", len(anchor))
    if next_h2 >= 0:
        section = section[:next_h2]
    prose, n = INVENTORY_RE.subn("", section)
    if n != 1:
        raise AssertionError("gate-checks inventory block not found inside the merge-gate section")
    return prose


class TestContributingCiGates(unittest.TestCase):
    def test_inventory_matches_ruleset_exactly(self):
        doc = doc_inventory()
        ruleset = ruleset_contexts()
        self.assertEqual(
            doc, ruleset,
            "CONTRIBUTING.md's gate inventory drifted from the branch-protection "
            f"ruleset: doc-only={sorted(doc - ruleset)}, ruleset-only={sorted(ruleset - doc)}",
        )

    def test_more_sentence_agrees_with_count(self):
        prose = merge_gate_prose()
        m = MORE_SENTENCE_RE.search(prose)
        self.assertIsNotNone(
            m, "the 'N more CI jobs/checks gate the merge' sentence is gone from the section"
        )
        word = m.group(1).lower()
        self.assertIn(word, NUMBER_WORDS, f"unexpected number word {m.group(1)!r}")
        # "more" is relative to the pytest one-liner, i.e. the `python tests` check.
        expected = len(ruleset_contexts() - {"python tests"})
        self.assertEqual(
            NUMBER_WORDS[word], expected,
            f"doc says '{word} more' but the ruleset has {expected} checks beyond `python tests`",
        )

    def test_every_check_has_a_local_form_in_prose(self):
        prose = merge_gate_prose().lower()
        for context in sorted(ruleset_contexts()):
            self.assertIn(
                context.lower(), prose,
                f"required check {context!r} is named in the inventory but has no "
                "discussion/local form in the merge-gate prose",
            )


if __name__ == "__main__":
    unittest.main()
