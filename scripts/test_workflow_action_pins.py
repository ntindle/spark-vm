"""Pin GitHub Actions to commit SHAs across .github/workflows (*.yml + *.yaml).

Tag-pinned actions (`uses: actions/checkout@v4`) resolve a MUTABLE tag: a
compromised action repo can move the tag and silently change what every CI
run executes. SHA-pinned actions resolve an immutable commit. The repo's
supply-chain contract is: every `uses:` step across every workflow file
pins a full 40-hex commit SHA (the tag it tracks rides in a trailing
`# vX, SHA-pinned` comment for readability).

This test fails loudly on drift in either direction:
- a `uses:` step whose ref is not a 40-hex SHA (tag/branch pin),
- a non-SHA `uses:` added to any workflow file (including new files),
- a SHA-pinned line missing the trailing marker comment (`# vX, SHA-pinned`;
  the version is the tag the SHA was taken from — for pins with no tracked
  tag, a bare `# SHA-pinned` with a prose note at the step, e.g. the
  shellcheck action, unmaintained since 2024).

Local `./.github/workflows/*.yml` action lines (the reusable-workflow
`uses: ./.github/workflows/golden-image.yml` reference) are exempt: they
reference a file in this same commit, not a remote action.

Maintenance: SHA pins freeze upstream updates, so when an action ships a
new release the pins must be bumped by hand — resolve the new tag's commit
SHA (e.g. via the git tag-ref API), update every `uses:` line and its
`# vX` marker, and extend `test_known_action_pins_resolve` if the bump
touches a first-party action. No dependabot config exists for
`.github/` today, so this is a manual cadence, not a bot.

Pure stdlib, no fixtures. Run from the repo root:
  python3 -m pytest scripts/test_workflow_action_pins.py -q
"""

import itertools
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# `uses: <owner>/<repo>@<ref>` — ref must be 40 hex. Local reusable-workflow
# refs (`./.github/workflows/...`) are exempt (same-commit reference).
USES_RE = re.compile(r"^\s*(?:-\s+)?uses\s*:\s*(\S+)\s*(?:#\s*(.*))?$", re.M)
SHA_RE = re.compile(r"\A[0-9a-f]{40}\Z")
# The marker is `# vX, SHA-pinned` where vX is the tracked tag; pins with no
# tracked tag carry a bare `# SHA-pinned` (the step's prose comment explains).
COMMENT_RE = re.compile(r"\A(?:v\d+(?:\.\d+)*,\s*)?SHA-pinned\b")


def iter_action_refs(text):
    """Yield (uses_value, comment) for every remote-action `uses:` line."""
    for m in USES_RE.finditer(text):
        uses, comment = m.group(1), (m.group(2) or "").strip()
        if uses.startswith("./"):
            continue
        yield uses, comment


class TestWorkflowActionPins(unittest.TestCase):
    def test_all_workflow_actions_sha_pinned(self):
        # GitHub executes both .yml and .yaml workflow files.
        files = sorted(
            itertools.chain(WORKFLOWS.glob("*.yml"), WORKFLOWS.glob("*.yaml"))
        )
        self.assertTrue(files, "no workflow files found under .github/workflows")
        violations = []
        unpinned = 0
        for f in files:
            for uses, comment in iter_action_refs(f.read_text()):
                unpinned += 1
                if "@" not in uses:
                    violations.append(f"{f.name}: {uses} has no ref")
                    continue
                _, _, ref = uses.rpartition("@")
                if not SHA_RE.match(ref):
                    violations.append(
                        f"{f.name}: {uses} is not SHA-pinned (ref {ref!r})"
                    )
                    continue
                if not COMMENT_RE.match(comment):
                    violations.append(
                        f"{f.name}: {uses} missing '# vX, SHA-pinned' comment"
                    )
        self.assertGreater(unpinned, 0, "no remote-action uses: lines found")
        self.assertEqual([], violations, "\n".join(violations))

    def test_known_action_pins_resolve(self):
        """The two first-party actions pin the SHAs the tags resolve to."""
        ci = (WORKFLOWS / "ci.yml").read_text()
        self.assertIn(
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            ci,
            "checkout v4 pin drifted",
        )
        self.assertIn(
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            ci,
            "setup-python v5 pin drifted",
        )


if __name__ == "__main__":
    unittest.main()
