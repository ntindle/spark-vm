#!/bin/bash
# local-gate.sh — run the merge gate's locally-replicable checks in one shot.
#
# CI gates every merge on eight checks (see the `<!-- gate-checks:start -->`
# inventory in CONTRIBUTING.md, pinned against the branch-protection ruleset
# by scripts/test_contributing_ci_gates.py). Six of the eight run in this
# script in order; it fails on the first failure. The other two are named
# in the output, not run: the markdown link check has no practical local
# equivalent, and the PNG screenshot smoke test is a manual recipe
# (see CONTRIBUTING.md).
#
# Usage:
#   ./scripts/local-gate.sh            # full gate: cheap checks + python suite
#   ./scripts/local-gate.sh --quick    # cheap checks only, skips the python suite
#   ./scripts/local-gate.sh --plan     # print the steps without running anything
#   ./scripts/local-gate.sh --eval-changed-paths [--base <ref> --head <ref> [--worktree]]
#                                      # print `docs-only` or `code` for the diff
#                                      # (CI's changed-paths semantics, verbatim;
#                                      #  --worktree also fails closed on
#                                      #  uncommitted changes — the main flow's mode)
#
# Steps (mirroring CONTRIBUTING.md "The merge gate, locally"):
#   1. shard plan            (python3 scripts/ci_shard_plan.py --check)
#   2. changelog ritual lint (python3 scripts/lint-changelog-ritual.py)
#   3. changed-paths gate    (docs-only diffs skip the python suite, exactly
#                             like CI's changed-paths gate — evaluated BEFORE
#                             any step that writes to the tree, so the gate's
#                             own pytest __pycache__ can never trip the
#                             --worktree guard into a false "code")
#   4. docs index coverage   (pytest scripts/test_docs_index_coverage.py —
#                             runs on every PR like CI, docs-only included)
#   5. shellcheck            (severity=error on changed *.sh — approximates
#                             the standalone shellcheck CI job; the suite's
#                             own shellcheck gates live inside the python suite)
#   6. python tests          (python3 -m pytest, unless docs-only or --quick)
#   7. markdown link check   (no local equivalent — named, not run)
#   8. PNG screenshot smoke  (manual — recipe named, not run; needs a browser install)
#
# Environment:
#   LOCAL_GATE_NO_CD=1  — do not cd to the repo root first (tests use this
#                         to point the changed-paths evaluator at a scratch
#                         git repo).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ "${LOCAL_GATE_NO_CD:-0}" != "1" ]]; then
  cd "$SCRIPT_DIR/.."
fi

MODE="full"
EVAL_ONLY=0
EVAL_WORKTREE=0
EVAL_BASE=""
EVAL_HEAD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick) MODE="quick"; shift ;;
    --plan)  MODE="plan"; shift ;;
    --eval-changed-paths) EVAL_ONLY=1; shift ;;
    --worktree) EVAL_WORKTREE=1; shift ;;   # with --eval-changed-paths: also
                                           # treat uncommitted changes as code
    --base)
      [[ $# -ge 2 ]] || { echo "local-gate.sh: --base needs a ref argument" >&2; exit 2; }
      EVAL_BASE="$2"; shift 2 ;;
    --head)
      [[ $# -ge 2 ]] || { echo "local-gate.sh: --head needs a ref argument" >&2; exit 2; }
      EVAL_HEAD="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,40p' "$0"
      exit 0 ;;
    *) echo "local-gate.sh: unknown flag: $1 (see --help)" >&2; exit 2 ;;
  esac
done

if [[ $EVAL_ONLY -eq 1 ]]; then
  if [[ -z "$EVAL_BASE" ]]; then
    if git rev-parse --verify --quiet origin/main >/dev/null 2>&1; then
      EVAL_BASE="origin/main"
    else
      # No base to diff against: fail closed — treat as code.
      # (Matches CI's changed-paths gate, which defaults code_changed=true
      # on push/workflow_dispatch where the diff is meaningless.)
      echo "code"
      exit 0
    fi
  fi
  [[ -n "$EVAL_HEAD" ]] || EVAL_HEAD="HEAD"
  # CI-verbatim changed-paths semantics (.github/workflows/ci.yml): docs/*
  # and CHANGELOG.md are docs; everything else is code.
  # NB: an empty diff feeds the loop one empty line, which matches *) — so a
  # zero-change diff fails closed to code_changed=true and the suite runs
  # (the safe direction; keep it). The <<< form is load-bearing: a
  # here-string always feeds the loop one line, so an empty diff arrives as
  # that single empty line instead of zero lines. Set -e note: if `git diff`
  # itself fails, the command substitution still feeds the loop that one
  # empty line instead of aborting the script — the while loop is exempt
  # from set -e's wrath on the redirect, so the failure lands fail-closed,
  # not fatal.
  code_changed=false
  while IFS= read -r f; do
    case "$f" in
      docs/*|CHANGELOG.md) ;;
      # NB: an empty diff feeds the loop one empty line, which matches *) —
      # so a zero-change diff fails closed to code_changed=true and the
      # suite runs. That is the safe direction; keep it.
      *) code_changed=true; break ;;
    esac
  done <<< "$(git diff --no-renames --name-only "$EVAL_BASE...$EVAL_HEAD")"
  if [[ "$EVAL_WORKTREE" == "1" ]] && [[ "$code_changed" != "true" ]]; then
    # The committed range said docs-only, but the contributor may not have
    # committed yet: any uncommitted change (modified, staged, or untracked —
    # git diff is blind to untracked files, so ask status instead) fails the
    # verdict closed to code, so a docs-only verdict never skips the suite
    # over changes the contributor hasn't committed.
    if [[ -n "$(git status --porcelain)" ]]; then
      code_changed=true
    fi
  fi
  if [[ "$code_changed" == "true" ]]; then
    echo "code"
  else
    echo "docs-only"
  fi
  exit 0
fi

step() { echo "=== local-gate: $1 ==="; }

plan_only() {
  cat <<'EOF'
local-gate plan (nothing executed):
  1. shard plan            — python3 scripts/ci_shard_plan.py --check
  2. changelog ritual lint — python3 scripts/lint-changelog-ritual.py
  3. changed-paths gate    — docs-only diffs skip step 6, exactly like CI
                             (evaluated before any step that writes to the
                             tree)
  4. docs index coverage   — python3 -m pytest scripts/test_docs_index_coverage.py -q
                             (runs on every PR like CI, docs-only included)
  5. shellcheck            — severity=error on *.sh files changed vs origin/main
                             (skipped loudly if shellcheck is not installed)
  6. python tests          — python3 -m pytest (skipped on --quick or docs-only)
  7. markdown link check   — no local equivalent (see CONTRIBUTING.md); check
                             the CI run on your PR instead
  8. PNG screenshot smoke test — manual (see CONTRIBUTING.md: pip install
                             playwright, playwright install chromium, then
                             python3 scripts/pw-test.py + png-check.py)
EOF
}

if [[ "$MODE" == "plan" ]]; then
  plan_only
  exit 0
fi

step "shard plan"
python3 scripts/ci_shard_plan.py --check

step "changelog ritual lint"
python3 scripts/lint-changelog-ritual.py

step "changed-paths gate"
# NB: recurse via the canonical SCRIPT_DIR, not $0 — the script cd'd to the
# repo root above, so a relative $0 from the contributor's original cwd
# (e.g. `cd docs && bash ../scripts/local-gate.sh`) no longer resolves.
# Evaluated before any step that writes to the tree: the docs-index pytest
# below leaves __pycache__ behind, and the --worktree guard must judge the
# contributor's tree, not the gate's own residue.
gate_verdict="$(bash "$SCRIPT_DIR/local-gate.sh" --eval-changed-paths --worktree)" || gate_verdict="code"
echo "local-gate: diff is $gate_verdict"

step "docs index coverage"
python3 -m pytest scripts/test_docs_index_coverage.py -q

step "shellcheck (severity=error, changed *.sh)"
if ! command -v shellcheck >/dev/null 2>&1; then
  echo "local-gate: shellcheck not installed — skipping (CI's standalone job does not skip; install it to replicate)"
elif git rev-parse --verify --quiet origin/main >/dev/null 2>&1; then
  # Approximation of the standalone CI job documented in CONTRIBUTING.md
  # (severity=error over the repo's shell scripts, including ones the
  # suite's gates never see).
  # NB: no --no-renames here — unlike the changed-paths gate, rename
  # detection is what we want: a renamed *.sh reports the surviving path,
  # while --no-renames would also list the deleted path and shellcheck
  # would fail on the file that no longer exists.
  # -z/-0: filenames with spaces must survive as single arguments.
  git diff -z --name-only origin/main...HEAD -- '*.sh' \
    | xargs -r -0 shellcheck -S error
else
  echo "local-gate: no origin/main to diff against — skipping changed-file shellcheck"
fi

if [[ "$MODE" == "quick" ]]; then
  step "python tests (skipped: --quick)"
elif [[ "$gate_verdict" == "docs-only" ]]; then
  step "python tests (skipped: docs-only diff — CI's changed-paths gate skips the suite too)"
else
  step "python tests"
  python3 -m pytest
fi

echo "=== local-gate: PASS (markdown link check has no local equivalent; PNG smoke test is manual — see CONTRIBUTING.md; check the CI run on your PR for both) ==="
