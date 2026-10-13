"""Pin the markdown-links job's retry wiring.

lychee v0.24.2 (bundled in the pinned lychee-action v2.9.0) never retries
5xx: ErrorKind::should_retry (lychee-lib/src/retry.rs) only retries
RejectedStatusCode(429), so a transient upstream 502 fails the step with no
backoff — --max-retries cannot fix this (observed 2026-10-13:
design-reuse.com 502'd the runner 3 min after the same content passed; 200
from independent egress with both browser and lychee UAs).

The job therefore checks twice on failure: the first step is
continue-on-error, a cooldown sleep follows (transient WAF/edge blocks need
minutes, not seconds), the retry step re-runs the identical invocation, and
a gate step fails the job only if both attempts failed. A genuinely broken
link still goes red; a transient 502 clears on the second pass.

This pins the structure so a future edit can't silently drop the retry, or
inline the args on one step and let the two invocations drift — both lychee
steps must reference the single job-level LYCHEE_ARGS env definition, and
the --exclude set itself stays pinned by test_ci_md_link_excludes.py.

Pure stdlib, no fixtures (mirrors test_ci_job_timeouts.py — PyYAML is not a
test dependency, so the job block is split on its 2-space-indented key and
steps on their 6-space `- ` markers). Run from the repo root:
  python3 -m pytest scripts/test_ci_linkcheck_retry.py -q
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"

LYCHEE_ACTION = "lycheeverse/lychee-action@"
ARGS_REF = "args: ${{ env.LYCHEE_ARGS }}"

# A job block starts at a 2-space-indented key and runs to the next such
# key or end of file (mirrors test_ci_job_timeouts.py).
JOB_KEY_RE = re.compile(r"^  ([a-zA-Z0-9_-]+):$", re.M)
# Steps sit at 6 spaces inside the job block.
STEP_RE = re.compile(r"^      - ", re.M)


def _job_block(name):
    text = CI_YML.read_text(encoding="utf-8")
    starts = [(m.group(1), m.start()) for m in JOB_KEY_RE.finditer(text)]
    for i, (job, start) in enumerate(starts):
        if job == name:
            end = starts[i + 1][1] if i + 1 < len(starts) else len(text)
            return text[start:end]
    raise AssertionError(f"job {name!r} not found in ci.yml")


def _steps(block):
    """Split a job block into its step texts (each starts at `      - `)."""
    bounds = [m.start() for m in STEP_RE.finditer(block)]
    assert bounds, "no steps found in the markdown-links job"
    return [block[bounds[i] : bounds[i + 1] if i + 1 < len(bounds) else len(block)]
            for i in range(len(bounds))]


class TestLinkCheckRetryWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.steps = _steps(_job_block("markdown-links"))
        cls.lychee = [s for s in cls.steps if LYCHEE_ACTION in s]

    def test_single_lychee_args_source(self):
        block = _job_block("markdown-links")
        defs = re.findall(r'LYCHEE_ARGS:\s*"[^"]*--no-progress', block)
        self.assertEqual(
            len(defs), 1,
            f"expected exactly one LYCHEE_ARGS definition, found {len(defs)}",
        )

    def test_two_lychee_steps_reference_the_env(self):
        self.assertEqual(
            len(self.lychee), 2,
            f"expected exactly 2 lychee steps, found {len(self.lychee)}",
        )
        for step in self.lychee:
            self.assertIn(
                ARGS_REF, step,
                "lychee step must reference the shared env, not inline args",
            )
            arg_lines = [l.strip() for l in re.findall(r"^ *args:.*$", step, re.M)]
            self.assertEqual(
                arg_lines, [ARGS_REF],
                "lychee step must carry no inline args besides the shared "
                f"env reference (found: {arg_lines})",
            )

    def test_first_step_is_continue_on_error_with_id(self):
        first = self.lychee[0]
        self.assertIn("id: linkcheck\n", first)
        self.assertIn("continue-on-error: true", first)

    def test_cooldown_between_attempts(self):
        first_idx = self.steps.index(self.lychee[0])
        retry_idx = self.steps.index(self.lychee[1])
        between = self.steps[first_idx + 1 : retry_idx]
        sleeps = [s for s in between
                  if "steps.linkcheck.outcome == 'failure'" in s
                  and re.search(r"^ *run:.*sleep", s, re.M)]
        self.assertEqual(
            len(sleeps), 1,
            "expected exactly one failure-gated cooldown sleep between the "
            "two lychee attempts",
        )

    def test_retry_step_wiring(self):
        retry = self.lychee[1]
        self.assertIn("id: linkcheck_retry\n", retry)
        self.assertIn("if: steps.linkcheck.outcome == 'failure'", retry)
        self.assertIn("continue-on-error: true", retry)

    def test_fail_gate_requires_both_failures(self):
        retry_idx = self.steps.index(self.lychee[1])
        gates = [s for s in self.steps[retry_idx + 1 :]
                 if "steps.linkcheck.outcome == 'failure'" in s
                 and "steps.linkcheck_retry.outcome == 'failure'" in s]
        self.assertEqual(
            len(gates), 1,
            "expected exactly one gate step failing the job only when both "
            "attempts failed",
        )
        self.assertIn(
            "if: steps.linkcheck.outcome == 'failure' "
            "&& steps.linkcheck_retry.outcome == 'failure'",
            gates[0],
            "gate must require BOTH attempts to fail (&&, not ||) — || "
            "would fail the job on a transient the retry cleared",
        )
        self.assertNotIn(
            "continue-on-error: true", gates[0],
            "the fail-gate must fail the job; continue-on-error would turn "
            "a double failure green",
        )
        self.assertRegex(gates[0], re.compile(r"^ *run:.*exit 1", re.M | re.S))

    def test_step_order(self):
        order = []
        for s in self.steps:
            if "id: linkcheck\n" in s:
                order.append("first")
            elif "id: linkcheck_retry\n" in s:
                order.append("retry")
            elif ("steps.linkcheck.outcome == 'failure'" in s
                  and "steps.linkcheck_retry.outcome == 'failure'" in s):
                order.append("gate")
        self.assertEqual(order, ["first", "retry", "gate"],
                         f"lychee steps out of order: {order}")


if __name__ == "__main__":
    unittest.main()
