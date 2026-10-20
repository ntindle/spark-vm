"""Pin the CI shard inventory's local pytest-command emitter (#1138 dx).

`scripts/ci_shard_plan.py --pytest-cmd <shard>` prints exactly what the
CI `python-tests-shard` job runs for that shard (`python3 -m pytest -q
${{ matrix.dirs }}` in `.github/workflows/ci.yml`, dirs space-joined) —
the contributor-local way to replicate one shard's selection without the
~40-minute serial full suite. The drift class this guards: a contributor
hand-writing a shard's selection (or a stale copy-paste in CONTRIBUTING)
diverging from the single-source SHARDS inventory, so local green and
CI red disagree on which suites ran.

What is pinned (each with an anti-vacuity rationale — a pin that passes
with the feature deleted is a comment, not a test):
- stdout is exactly `python3 -m pytest -q <dirs>` with the shard's dirs
  in SHARDS order, single-space-joined (CI's `${{ matrix.dirs }}` is the
  same join; a reformatted emitter would still "run the same tests" but
  would no longer be the CI-verbatim command the doc promises).
- Unknown shard names and a missing shard argument fail closed (exit 1)
  and name the valid shards on stderr — never print a command.
- The proxy shard (CI's root_tests shard) carries the sudo root-tests
  note on stderr; no other shard does (a dropped note would silently
  let a contributor believe the printed command is the whole shard).
- Every emitted dir exists in the checkout (fail-closed on a stale
  inventory entry — the emitted command must be runnable).
- The plan module stays stdlib-only (the CI plan job runs it with
  nothing installed; the flag must not add a dependency).

Pure stdlib, no fixtures. Plain unittest so it runs even where pytest's
collection is the thing under test.
"""

import ast
import importlib.util
import io
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
_PLAN_PATH = _HERE / "ci_shard_plan.py"

_ROOT_TESTS_RE = re.compile(r"(?=.*\bsudo\b)(?=.*\broot tests\b)", re.IGNORECASE)


def _load_plan():
    spec = importlib.util.spec_from_file_location("ci_shard_plan", _PLAN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCiShardPytestCmd(unittest.TestCase):
    def test_pytest_cmd_is_ci_verbatim_selection(self):
        # The emitted command must be byte-exactly CI's shard selection:
        # `python3 -m pytest -q` + the shard's dirs in SHARDS order joined
        # with single spaces — the same join ci.yml's `${{ matrix.dirs }}`
        # performs on the same inventory.
        plan = _load_plan()
        for shard, dirs in plan.SHARDS.items():
            with self.subTest(shard=shard):
                out = io.StringIO()
                err = io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    plan.pytest_cmd(shard)
                self.assertEqual(
                    out.getvalue(),
                    "python3 -m pytest -q " + " ".join(dirs) + "\n",
                )

    def test_pytest_cmd_flag_matches_function(self):
        # The CLI flag is the contributor's entry point — it must print the
        # same line the function emits (the flag is not allowed its own
        # formatting path).
        plan = _load_plan()
        for shard in plan.SHARDS:
            with self.subTest(shard=shard):
                proc = subprocess.run(
                    [sys.executable, str(_PLAN_PATH), "--pytest-cmd", shard],
                    capture_output=True,
                    text=True,
                    cwd=ROOT,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(
                    proc.stdout,
                    "python3 -m pytest -q " + " ".join(plan.SHARDS[shard]) + "\n",
                )

    def test_unknown_shard_fails_closed(self):
        proc = subprocess.run(
            [sys.executable, str(_PLAN_PATH), "--pytest-cmd", "shard-nope"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("shard-nope", proc.stderr)
        for shard in ("shard-unit", "shard-components", "shard-integration",
                      "shard-harness", "shard-deploy"):
            self.assertIn(shard, proc.stderr)

    def test_missing_shard_arg_fails_closed(self):
        proc = subprocess.run(
            [sys.executable, str(_PLAN_PATH), "--pytest-cmd"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("missing shard name", proc.stderr)

    def test_only_the_proxy_shard_carries_the_root_tests_note(self):
        # CI runs the install-safety root tests under sudo on exactly the
        # shard holding proxy/ (root_tests, derived from the inventory).
        # The note must ride with the command — otherwise the printed
        # command underclaims what the shard proves.
        plan = _load_plan()
        for shard, dirs in plan.SHARDS.items():
            with self.subTest(shard=shard):
                out = io.StringIO()
                err = io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    plan.pytest_cmd(shard)
                if "proxy" in dirs:
                    self.assertRegex(
                        err.getvalue(), _ROOT_TESTS_RE,
                        "proxy shard must carry the sudo root-tests note",
                    )
                else:
                    self.assertNotRegex(
                        err.getvalue(), _ROOT_TESTS_RE,
                        "non-proxy shards must not claim sudo root tests",
                    )

    def test_emitted_dirs_exist_in_the_checkout(self):
        plan = _load_plan()
        for shard, dirs in plan.SHARDS.items():
            for d in dirs:
                with self.subTest(shard=shard, dir=d):
                    self.assertTrue(
                        (ROOT / d).is_dir(),
                        f"shard {shard!r} emits {d!r}, which is not a directory",
                    )

    def test_plan_module_stays_stdlib_only(self):
        # The CI plan job runs ci_shard_plan.py with nothing installed; a
        # third-party import would break the job while passing every local
        # run. Pin the stdlib-only contract at the AST level.
        tree = ast.parse(_PLAN_PATH.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add(node.module.split(".")[0])
        non_stdlib = imported - set(sys.stdlib_module_names)
        self.assertEqual(non_stdlib, set())


if __name__ == "__main__":
    unittest.main()
