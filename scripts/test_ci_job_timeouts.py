"""Every CI workflow job must carry an explicit timeout-minutes.

A wedged job with no bound burns GitHub's 6-hour default: the
python-tests-shard shard-integration hang at 47+ min on 2026-10-11 and the
pre-shard python-tests hang at ~40 min on 2026-10-03 both had to be noticed
and cancelled by a human. The policy (documented in ci.yml's header comment):
15 min for fast deterministic jobs, 30 for network/browser-bound jobs, 60
for the test shards and image builds — every bound far above the job's
observed healthy duration and far below the default, so a hung job fails
fast. When a job's healthy duration grows, bump its bound with a comment
citing the new observation — never delete the bound, and never set it at
or above the 360-minute GitHub maximum (a bound the platform would enforce
anyway is no bound at all).

Pure stdlib, no fixtures (mirrors test_workflow_action_pins.py — PyYAML is
not a test dependency, so jobs are split on their 2-space-indented keys and
each block is scanned for a 4-space-indented timeout-minutes line; a
step-level timeout at 6 spaces must NOT satisfy this). Run from the repo
root: python3 -m pytest scripts/test_ci_job_timeouts.py -q
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# The workflows whose jobs this pins (the full CI + release surface).
WORKFLOW_FILES = ["ci.yml", "golden-image.yml", "release.yml"]

# A job block starts at a 2-space-indented key and runs to the next such
# key or end of file (job keys are the only 2-space-indented mappings in
# these files; everything under a job is deeper).
JOB_KEY_RE = re.compile(r"^  ([a-zA-Z0-9_-]+):$", re.M)
# Job-level timeout-minutes: exactly 4 spaces (a 6-space step-level entry
# is a different scope and must not count).
TIMEOUT_RE = re.compile(r"^    timeout-minutes:\s*(\d+)\s*(?:#.*)?$", re.M)

# GitHub's hard ceiling for timeout-minutes; a bound at or above it is
# vacuous — the platform enforces the ceiling first.
GHA_MAX_TIMEOUT_MINUTES = 360


def _jobs(path):
    """Yield (job_name, job_block_text) for every job in a workflow file.

    Only the `jobs:` mapping is scanned — 2-space-indented keys also appear
    under `on:` and `concurrency:`, which are not jobs.
    """
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^jobs:$", text, re.M)
    assert m, "no jobs: section in %s" % path.name
    jobs_text = text[m.end():]
    keys = list(JOB_KEY_RE.finditer(jobs_text))
    assert keys, "no job keys found in %s — parser drift?" % path.name
    for i, km in enumerate(keys):
        end = keys[i + 1].start() if i + 1 < len(keys) else len(jobs_text)
        yield km.group(1), jobs_text[km.start():end]


def _timeout_minutes(block):
    m = TIMEOUT_RE.search(block)
    return int(m.group(1)) if m else None


def test_every_job_has_timeout_minutes():
    unbound = []
    for name in WORKFLOW_FILES:
        path = WORKFLOWS / name
        assert path.is_file(), "workflow file missing: %s" % name
        for job, block in _jobs(path):
            if _timeout_minutes(block) is None:
                unbound.append("%s:%s" % (name, job))
    assert not unbound, (
        "jobs without an explicit timeout-minutes (a hung job burns the "
        "6-hour GitHub default):\n  " + "\n  ".join(sorted(unbound)))


def test_timeout_bounds_are_sane():
    bad = []
    for name in WORKFLOW_FILES:
        for job, block in _jobs(WORKFLOWS / name):
            minutes = _timeout_minutes(block)
            if minutes is None:
                continue  # covered by test_every_job_has_timeout_minutes
            if not 1 <= minutes < GHA_MAX_TIMEOUT_MINUTES:
                bad.append("%s:%s=%d" % (name, job, minutes))
    assert not bad, (
        "timeout-minutes outside (0, 360) — a non-positive bound is "
        "nonsense and a bound >= 360 is vacuous (the platform ceiling "
        "applies first):\n  " + "\n  ".join(sorted(bad)))
