"""Pin the local-gate runner against the documented merge gate.

Two contracts, both cheap to break by accident:

1. **Inventory agreement** — CONTRIBUTING.md's `<!-- gate-checks:start -->`
   block is the machine-readable merge-gate inventory (pinned against the
   branch-protection ruleset by test_contributing_ci_gates.py). Every item in
   it must be named in scripts/local-gate.sh: run, or explicitly called out
   as having no local equivalent (the markdown link check).
2. **Changed-paths semantics** — the gate's docs-only/code verdict must match
   CI's changed-paths gate (.github/workflows/ci.yml) exactly, including the
   fail-closed zero-change direction.

Non-vacuity: every test below is sensitive to its contract — neuter the
corresponding script behavior and the test fails (verified by hand during
development).
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "scripts" / "local-gate.sh"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def read_gate_checks_block():
    text = CONTRIBUTING.read_text()
    m = re.search(r"<!-- gate-checks:start -->\n(.*?)\n<!-- gate-checks:end -->",
                  text, re.S)
    assert m, "CONTRIBUTING.md gate-checks inventory block missing"
    return [line.strip() for line in m.group(1).splitlines() if line.strip()]


def test_inventory_every_item_named_in_gate_script():
    """Each merge-gate check is run by local-gate.sh or explicitly excluded
    as having no local equivalent."""
    items = read_gate_checks_block()
    assert len(items) == 8, f"inventory drift: {items}"
    script = GATE.read_text().lower()
    for item in items:
        if item == "markdown link check":
            # The one documented non-local check: must be named *and* the
            # no-local-equivalent reason must be stated (not silently
            # dropped).
            assert item in script, "link check dropped from the script entirely"
            assert "no local equivalent" in script or "no practical local equivalent" in script
            continue
        if item == "PNG screenshot smoke test":
            # Manual-only (needs a browser install): must be named in the
            # plan output with the recipe pointer, never silently dropped.
            assert item.lower() in script, "PNG smoke test dropped from the script"
            assert "manual" in script
            continue
        assert item.lower() in script, (
            f"merge-gate check {item!r} not named in scripts/local-gate.sh — "
            "add it (run or explicitly excluded) or fix the inventory"
        )


def test_shellcheck_step_approximates_ci_job():
    """The script's shellcheck step must use the CONTRIBUTING-documented
    severity and diff base (approximation of the standalone shellcheck job).
    The -z/-0 pair is pinned too: without it, a *.sh filename containing
    whitespace would split into two arguments and fail a diff CI passes."""
    script = GATE.read_text()
    assert "shellcheck -S error" in script
    assert "origin/main...HEAD" in script
    assert "-- '*.sh'" in script
    assert "git diff -z" in script
    assert "xargs -r -0" in script


def test_changed_paths_case_arms_match_ci_yml():
    """The gate's case arms must stay byte-aligned with ci.yml's — a drift
    here silently redefines what 'docs-only' means locally vs on CI."""
    script = GATE.read_text()
    ci = CI_YML.read_text()
    # Both files must carry the same two docs-only arms and the same
    # fail-closed note.
    assert "docs/*|CHANGELOG.md" in ci
    assert "docs/*|CHANGELOG.md" in script
    assert "empty diff feeds the loop one empty line" in ci
    assert "empty diff feeds the loop one empty line" in script


def _eval_in_scratch_repo(commits, base_ref="HEAD~1", extra_args=(), dirty=None,
                         staged=None, rename=None):
    """Build a scratch repo, apply `commits` (list of {path: bytes}),
    optionally leave `dirty` {path: bytes} uncommitted, `staged` {path:
    bytes} staged-but-uncommitted, or perform `rename` (old_path, new_path)
    via git mv as its own commit after the `commits` (base_ref="HEAD~1"
    then covers the rename alone), and return the gate's verdict for
    base_ref...HEAD."""
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="local-gate-test-"))
    env = dict(os.environ, LOCAL_GATE_NO_CD="1",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    def git(*args, **kwargs):
        return subprocess.run(
            ["git", *args], cwd=tmp, env=env, check=True,
            capture_output=True, text=True, **kwargs)
    git("init", "-q")
    (tmp / "a.txt").write_text("base")
    git("add", ".")
    git("commit", "-qm", "base")
    for files in commits:
        for path, content in files.items():
            p = tmp / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        git("add", ".")
        git("commit", "-qm", "change")
    if rename:
        # git mv needs a tracked source, so the rename is its own commit
        # after the file commit above.
        old, new = rename
        (tmp / new).parent.mkdir(parents=True, exist_ok=True)
        git("mv", old, new)
        git("add", ".")
        git("commit", "-qm", "rename")
    if dirty:
        for path, content in dirty.items():
            p = tmp / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
    if staged:
        for path, content in staged.items():
            p = tmp / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        git("add", ".")
    out = subprocess.run(
        ["bash", str(GATE), "--eval-changed-paths", "--base", base_ref,
         "--head", "HEAD", *extra_args],
        cwd=tmp, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_changed_paths_docs_only():
    verdict = _eval_in_scratch_repo([{"docs/guide.md": "words", "CHANGELOG.md": "entry"}])
    assert verdict == "docs-only"


def test_changed_paths_code():
    verdict = _eval_in_scratch_repo([{"docs/guide.md": "words", "proxy/x.py": "code"}])
    assert verdict == "code"


def test_changed_paths_docs_subdir_only():
    verdict = _eval_in_scratch_repo([{"docs/nested/deep.md": "words"}])
    assert verdict == "docs-only"


def test_changed_paths_zero_change_fails_closed():
    """base == head feeds the loop one empty line, which matches *) —
    CI fails closed to code_changed=true; the local gate must too."""
    verdict = _eval_in_scratch_repo([], base_ref="HEAD")
    assert verdict == "code"


def test_changed_paths_changelog_only_is_docs_only():
    verdict = _eval_in_scratch_repo([{"CHANGELOG.md": "entry"}])
    assert verdict == "docs-only"


def test_worktree_uncommitted_code_fails_closed():
    """A docs-only committed diff with uncommitted code changes must read
    as code under --worktree (the main flow's mode) — the verdict must
    never skip the suite over changes the contributor hasn't committed."""
    verdict = _eval_in_scratch_repo(
        [{"docs/guide.md": "words"}],
        extra_args=("--worktree",),
        dirty={"proxy/uncommitted.py": "code"})
    assert verdict == "code"


def test_changed_paths_rename_reports_delete_plus_add():
    """A code file renamed into docs/ must read as code: --no-renames
    reports the rename as delete+add, so the deleted code path trips the
    case. Without the flag, rename detection reports only the docs/
    destination and the verdict would wrongly skip the suite."""
    verdict = _eval_in_scratch_repo(
        [{"scripts/tool.py": "code"}],
        rename=("scripts/tool.py", "docs/tool.md"))
    assert verdict == "code"


def test_worktree_staged_code_fails_closed():
    """Staged-but-uncommitted changes count too (index vs HEAD)."""
    verdict = _eval_in_scratch_repo(
        [{"docs/guide.md": "words"}],
        extra_args=("--worktree",),
        staged={"proxy/staged.py": "code"})
    assert verdict == "code"


def test_eval_no_origin_main_fails_closed():
    """Without --base and no origin/main ref, the evaluator cannot diff —
    it must fail closed to code (the main flow's no-base behavior)."""
    import tempfile, os as _os, subprocess as _sp
    tmp = Path(tempfile.mkdtemp(prefix="local-gate-test-"))
    env = dict(_os.environ, LOCAL_GATE_NO_CD="1",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    def git(*a):
        return _sp.run(["git", *a], cwd=tmp, env=env, check=True,
                       capture_output=True, text=True)
    git("init", "-q")
    (tmp / "docs").mkdir(exist_ok=True)
    (tmp / "docs" / "guide.md").write_text("words")
    git("add", ".")
    git("commit", "-qm", "docs only")
    # No origin/main ref here on purpose.
    out = _sp.run(["bash", str(GATE), "--eval-changed-paths"],
                  cwd=tmp, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "code"


def test_worktree_clean_tree_keeps_docs_only():
    verdict = _eval_in_scratch_repo(
        [{"docs/guide.md": "words"}], extra_args=("--worktree",))
    assert verdict == "docs-only"


def test_eval_without_worktree_ignores_uncommitted():
    """Without --worktree the verdict is pure CI semantics (committed
    range only) — the pin on CI parity lives here."""
    verdict = _eval_in_scratch_repo(
        [{"docs/guide.md": "words"}],
        dirty={"proxy/uncommitted.py": "code"})
    assert verdict == "docs-only"


def test_main_flow_recursion_from_subdirectory_via_relative_path():
    """Regression: step 5 recursed via `bash \"$0\"`, which broke when the
    script was invoked through a relative path from a subdirectory — the
    script cd's to the repo root first, so the relative $0 no longer
    resolved and the || guard swallowed the failure as a wrong "code"
    verdict. The recursion now uses the canonical SCRIPT_DIR. This test
    runs the real main flow (--quick) from a subdirectory via a relative
    path on a docs-only scratch diff and asserts the verdict survives."""
    import tempfile, os as _os, subprocess as _sp, shutil
    tmp = Path(tempfile.mkdtemp(prefix="local-gate-mainflow-"))
    # NB: no LOCAL_GATE_NO_CD here — the point is exercising the script's
    # own cd-to-repo-root plus the SCRIPT_DIR-based recursion.
    env = dict(_os.environ,
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    def git(*a):
        return _sp.run(["git", *a], cwd=tmp, env=env, check=True,
                       capture_output=True, text=True)
    git("init", "-q")
    (tmp / "scripts").mkdir()
    (tmp / "docs").mkdir()
    (tmp / "a.txt").write_text("base")
    # Minimal stubs for the steps before the changed-paths gate.
    (tmp / "scripts" / "ci_shard_plan.py").write_text(
        "import sys\nassert '--check' in sys.argv\nprint('shard inventory OK')\n")
    (tmp / "scripts" / "lint-changelog-ritual.py").write_text(
        "print('clean')\n")
    (tmp / "scripts" / "test_docs_index_coverage.py").write_text(
        "def test_stub_ok():\n    assert True\n")
    shutil.copy(str(GATE), str(tmp / "scripts" / "local-gate.sh"))
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD").stdout.strip()
    git("update-ref", "refs/remotes/origin/main", base)
    (tmp / "docs" / "guide.md").write_text("words")
    git("add", ".")
    git("commit", "-qm", "docs only")
    # Invoke through a relative path from a subdirectory — the exact shape
    # that broke `bash \"$0\"` after the script's cd to the repo root.
    out = _sp.run(["bash", "../scripts/local-gate.sh", "--quick"],
                  cwd=tmp / "docs", env=env,
                  capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "diff is docs-only" in out.stdout, out.stdout
    """Without --worktree the verdict is pure CI semantics (committed
    range only) — the pin on CI parity lives here."""
    verdict = _eval_in_scratch_repo(
        [{"docs/guide.md": "words"}],
        dirty={"proxy/uncommitted.py": "code"})
    assert verdict == "docs-only"


def test_plan_mode_lists_every_step_without_running():
    """--plan must print all eight steps and exit 0 without executing."""
    out = subprocess.run(
        ["bash", str(GATE), "--plan"],
        capture_output=True, text=True, env={**os.environ, "LOCAL_GATE_NO_CD": "1"})
    assert out.returncode == 0, out.stderr
    for step in ("shard plan", "changelog ritual lint", "docs index coverage",
                 "shellcheck", "changed-paths gate", "python tests",
                 "markdown link check", "PNG screenshot smoke"):
        assert step in out.stdout, f"--plan omits step: {step}"
    # Each runnable step's plan line must name the actual command it runs —
    # a plan line that names the step but drops the command (e.g. a stale
    # "REMOVED" placeholder) must fail this test.
    lines = out.stdout.splitlines()
    def plan_line(step):
        return next(l for l in lines if step in l)
    assert "ci_shard_plan.py" in plan_line("shard plan")
    assert "lint-changelog-ritual.py" in plan_line("changelog ritual lint")
    assert "test_docs_index_coverage.py" in plan_line("docs index coverage")
    assert "shellcheck" in plan_line("shellcheck")
    assert "python3 -m pytest" in plan_line("python tests")


def test_gate_script_is_executable_and_strict():
    assert os.access(GATE, os.X_OK)
    head = GATE.read_text().splitlines()[0]
    assert head == "#!/bin/bash"
    assert "set -euo pipefail" in GATE.read_text()
