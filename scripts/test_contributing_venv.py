"""Pin CONTRIBUTING's venv-first install instructions.

CONTRIBUTING used to say bare `pip install -r requirements-test.txt`.
On stock Ubuntu 24.04 (and any PEP 668 system) that refuses with
`externally-managed-environment` — the verbatim contributor path failed
on the first command. The doc now prescribes the `python3-venv`
prerequisite, then creating + activating a venv before installing, and
`.gitignore` covers `.venv/` so the checkout stays clean (an untracked
`.venv/` would also trip the local gate's changed-paths `--worktree`
guard into a false "code" verdict).

The assertions are scoped to the fenced install block, not the whole
document: a prose mention of venv elsewhere must not satisfy the pin
while the install block itself regresses to bare `pip install`. The
two whole-tree walker pins (`test_pytest_ini_covers_all.py`,
`test_basename_uniqueness.py`) skip `.venv/`, so a contributor venv
that ships a `test_*.py` inside an installed wheel can never trip them.

Run from the repo root:  python3 -m pytest scripts/test_contributing_venv.py -q
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
GITIGNORE = ROOT / ".gitignore"
COVERS_ALL = ROOT / "scripts" / "test_pytest_ini_covers_all.py"
UNIQUENESS = ROOT / "scripts" / "test_basename_uniqueness.py"

FENCE = re.compile(r"```[a-zA-Z0-9_-]*[ \t]*\n(.*?)```[ \t]*", re.DOTALL)
INSTALL_MARKER = "pip install -r requirements-test.txt"
ACTIVATION_LINES = ("source .venv/bin/activate", ". .venv/bin/activate")
# Covered pip-invocation forms (see _pip_invocation): optional `sudo`
# (valueless short flags, value-taking short flags -u/-g/-C/-D/-R/-T/-U/-p/-r/-t,
# long --flag / --flag=value), optional `python[3][.x] -m` / `py [-3[.x]] -m`,
# then `pip` / `pip3` / `pip3.x` / `uv pip`, then `install`.
# Deliberately NOT covered (implausible in this doc; extending the matcher
# toward a shell parser): `command`/`time`/`nice` prefixes, subshells and
# command substitution, absolute paths (`/usr/bin/pip3`), `python3 -u -m`,
# backslash continuations, single `&` / `|` separators, space-separated
# long sudo-flag values (`sudo --user root pip`), tilde/indented fences.
# Sudo long flags take `--flag=value` only: a space-separated value would
# let `--flag` swallow the following `pip` token.
_SUDO_FLAGS = (
    r"(?:\s+(?:-[uUgGCDRUTprt]\s+\S+|-[A-Za-z]+"
    r"|--[A-Za-z][A-Za-z0-9_-]*(?:=\S+)?))*"
)
PIP_SEGMENT = re.compile(
    r"(sudo" + _SUDO_FLAGS + r"\s+)?"
    r"((python3?(\.\d+)?|py( -3(\.\d+)?)?)\s+-m\s+)?"
    r"(pip3?(\.\d+)?|uv\s+pip)\s+install\b"
)
ENV_ASSIGN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S+)\s*"
)


def _pip_invocation(line):
    """True if an uncommented line invokes pip install in a covered form.

    Splits on shell chain operators (`&&`, `;`, `||`) so `cd /tmp &&
    pip install` cannot hide the pip behind a prefix; strips a `$`
    prompt, a leading `env` command, and leading `VAR=val` assignments
    (values may be double/single-quoted); matches each segment against
    PIP_SEGMENT (see the comment above it for the covered forms and the
    named limitations).
    """
    stripped = line.strip()
    if stripped.startswith("#"):
        return False
    for segment in re.split(r"&&|;|\|\|", stripped):
        seg = segment.strip().removeprefix("$").strip()
        if seg == "env" or seg.startswith("env ") or seg.startswith("env\t"):
            seg = seg[3:].strip()
        while ENV_ASSIGN.match(seg):
            seg = ENV_ASSIGN.sub("", seg, count=1)
        if PIP_SEGMENT.match(seg):
            return True
    return False


def fenced_blocks(text):
    return FENCE.findall(text)


def install_block(text):
    """The install block: the fenced block carrying the venv prescription.

    A second fenced block may quote the marker as a commented negative
    example ("do NOT run this bare form") — the exactly-1 rule banned
    that. Prefer the marker block that actually creates + activates the
    venv; fall back to the first marker block with an uncommented marker
    line, then to the first marker block at all.
    """
    marker_blocks = [b for b in fenced_blocks(text) if INSTALL_MARKER in b]
    assert marker_blocks, "expected a fenced install block, found none"
    for block in marker_blocks:
        stripped = [ln.strip() for ln in block.splitlines()]
        if "python3 -m venv .venv" in stripped and any(
            act in stripped for act in ACTIVATION_LINES
        ):
            return block
    for block in marker_blocks:
        if any(
            not ln.strip().startswith("#") and INSTALL_MARKER in ln
            for ln in block.splitlines()
        ):
            return block
    return marker_blocks[0]


def lines_before(block, needle):
    """Lines of block strictly before the first line containing needle."""
    out = []
    for line in block.splitlines():
        if needle in line:
            break
        out.append(line)
    return out


class TestContributingVenv(unittest.TestCase):
    def test_install_block_is_venv_first(self):
        text = CONTRIBUTING.read_text(encoding="utf-8")
        block = install_block(text)
        # Whole-line matches: a commented-out venv line ("# python3 -m venv")
        # must NOT satisfy the pin.
        stripped = [ln.strip() for ln in block.splitlines()]
        self.assertIn(
            "python3 -m venv .venv",
            stripped,
            "install block must create the venv as .venv (uncommented)",
        )
        activation = next(
            (act for act in ACTIVATION_LINES if act in stripped),
            None,
        )
        self.assertIsNotNone(
            activation,
            "install block must activate the venv (uncommented, "
            "`source` or POSIX `.` form)",
        )
        create_at = stripped.index("python3 -m venv .venv")
        activate_at = stripped.index(activation)
        # Skip commented-out marker lines: a `# pip install ... # old way`
        # comment above activation must not break the ordering assertion.
        pip_at = next(
            i
            for i, ln in enumerate(stripped)
            if not ln.startswith("#") and INSTALL_MARKER in ln
        )
        self.assertLess(create_at, activate_at, "venv creation must precede activation")
        self.assertLess(activate_at, pip_at, "venv activation must precede the pip install")
        # Every pip-install line in the block must come after activation.
        for i, ln in enumerate(stripped):
            if ln.startswith("#"):
                continue
            if _pip_invocation(ln):
                self.assertLess(
                    activate_at,
                    i,
                    f"pip line must follow activation in the install block: {ln!r}",
                )

    def test_no_other_fenced_block_prescribes_bare_pip(self):
        text = CONTRIBUTING.read_text(encoding="utf-8")
        install = install_block(text)
        skipped_install = False
        for block in fenced_blocks(text):
            # Skip only the selected install block, once: any other
            # marker block (e.g. a second quoted example) is checked.
            if not skipped_install and block == install:
                skipped_install = True
                continue
            for ln in block.splitlines():
                if ln.strip().startswith("#"):
                    continue
                if _pip_invocation(ln):
                    # Whole-line, uncommented activation must precede the
                    # pip line: a commented-out "# source ..." does not count.
                    prior = [
                        prior_ln.strip()
                        for prior_ln in lines_before(block, ln)
                    ]
                    self.assertTrue(
                        any(act in prior for act in ACTIVATION_LINES),
                        f"fenced block prescribes bare pip without activation: {ln!r}",
                    )

    def test_prerequisite_recovery_and_platform_notes_named(self):
        text = CONTRIBUTING.read_text(encoding="utf-8")
        block_start = text.find(install_block(text))
        self.assertNotEqual(block_start, -1, "install block not found")
        prose = text[max(0, block_start - 2000) : block_start]
        self.assertIn(
            "externally-managed",
            prose,
            "prose before the install block must name the PEP 668 failure",
        )
        self.assertIn(
            "python3-venv",
            text,
            "CONTRIBUTING must name the python3-venv prerequisite",
        )
        # The prerequisite must be a copy-pasteable command in a fenced
        # block, not prose mentioning the package name ("You need the
        # python3-venv package" would satisfy a bare substring check
        # while the verbatim path is gone).
        self.assertTrue(
            any(
                not ln.strip().startswith("#")
                and ("apt install" in ln or "apt-get install" in ln)
                and "python3-venv" in ln
                for block in fenced_blocks(text)
                for ln in block.splitlines()
            ),
            "a fenced block must carry an `apt[ -get] install ... python3-venv` command",
        )
        self.assertIn(
            "ensurepip",
            text,
            "CONTRIBUTING must name the ensurepip symptom",
        )
        self.assertIn(
            "rm -rf .venv",
            text,
            "CONTRIBUTING must give half-created-venv recovery",
        )
        self.assertIn(
            ".venv\\Scripts\\Activate.ps1",
            text,
            "CONTRIBUTING must give the Windows activation path",
        )

    def test_gitignore_covers_venv(self):
        lines = [
            line.strip()
            for line in GITIGNORE.read_text(encoding="utf-8").splitlines()
        ]
        self.assertIn(
            ".venv/",
            lines,
            ".gitignore must cover .venv/ so a contributor venv stays untracked",
        )
        self.assertNotIn(
            "!.venv/",
            lines,
            ".gitignore must not re-include .venv/ via a negation",
        )

    def test_tree_walkers_skip_venv(self):
        for path in (COVERS_ALL, UNIQUENESS):
            text = path.read_text(encoding="utf-8")
            # A real walk-filter expression, not a comment mentioning the
            # directory: strip any trailing comment, then require the
            # skip to live in code carrying the filter.
            self.assertTrue(
                any(
                    '".venv"' in ln.split("#", 1)[0]
                    and (
                        "dirnames" in ln.split("#", 1)[0]
                        or "not in" in ln.split("#", 1)[0]
                    )
                    for ln in text.splitlines()
                    if not ln.strip().startswith("#")
                ),
                f"{path.name} must exclude .venv in its tree-walk filter",
            )


class TestPipInvocation(unittest.TestCase):
    """Direct unit tests pinning _pip_invocation's claimed breadth.

    The doc-driven tests above only exercise the matcher against the
    doc's actual lines, so a future edit could silently narrow the
    matcher back to the round-3 holes with the suite still green.
    These tests pin every covered form plus the true negatives.
    """

    def test_covered_forms(self):
        covered = [
            "pip install foo",
            "pip3 install foo",
            "pip3.11 install foo",
            "pip3.12 install foo",
            "python -m pip install foo",
            "python3 -m pip install foo",
            "python3.11 -m pip install foo",
            "py -m pip install foo",
            "py -3 -m pip install foo",
            "py -3.11 -m pip install foo",
            "uv pip install foo",
            "sudo pip install foo",
            "sudo -E -H pip install foo",
            "sudo -u root pip install foo",
            "sudo -g staff pip install foo",
            "sudo --preserve-env pip install foo",
            "sudo --user=root pip install foo",
            "FOO=bar pip install foo",
            'PIP_CONFIG_FILE="my cfg.toml" pip install foo',
            "PIP_CONFIG_FILE='my cfg.toml' pip install foo",
            "env pip install foo",
            "env FOO=bar pip install foo",
            "cd /tmp && pip install foo",
            "cd /tmp; pip install foo",
            "true || pip install foo",
            "$ pip install foo",
            "$ FOO=bar pip install foo",
            "pip install -r requirements-test.txt",
        ]
        for line in covered:
            with self.subTest(line=line):
                self.assertTrue(_pip_invocation(line), f"must detect: {line!r}")

    def test_true_negatives(self):
        negatives = [
            "pipx install foo",
            "sudo apt install -y python3-venv",
            "sudo apt-get install -y python3-venv",
            "# pip install foo",
            'echo "pip install foo"',
        ]
        for line in negatives:
            with self.subTest(line=line):
                self.assertFalse(_pip_invocation(line), f"must not detect: {line!r}")


if __name__ == "__main__":
    unittest.main()
