#!/bin/bash
# png-smoke.sh — one-command PNG screenshot smoke test.
#
# CI's `png-check` job and the old CONTRIBUTING.md / docs/CI.md recipes were a
# four-step manual recipe (activate venv, `pip install playwright` UNPINNED,
# `playwright install --with-deps chromium`, then `pw-test.py` + `png-check.py`).
# The unpinned install meant CI and contributors floated on whatever
# playwright released most recently — a new upstream release could (and
# eventually will) break the smoke with no repo-side change.
#
# This script runs the same checks hermetically, pinned to the playwright
# version in scripts/self_update_pins.conf — the same pin the toolset
# updater converges boxes onto, so the contributor's browser matches CI and
# the fleet.
#
# Usage:
#   ./scripts/png-smoke.sh            # install (only if needed) + screenshot + PNG check
#   ./scripts/png-smoke.sh --plan     # print the steps without running anything
#   ./scripts/png-smoke.sh --with-deps
#                                     # pass --with-deps to `playwright install`
#                                     # (installs OS deps; escalates internally)
#
# Requires the CONTRIBUTING.md venv to be activated (VIRTUAL_ENV set): the
# playwright package is installed there, never into the system Python.
#
# Env overrides (tests only):
#   PNG_SMOKE_PINS_CONF — alternate pins file (default: scripts/self_update_pins.conf).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

PINS_CONF="${PNG_SMOKE_PINS_CONF:-$SCRIPT_DIR/self_update_pins.conf}"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PINS_DISPLAY="${PINS_CONF#"$REPO_ROOT"/}"  # repo-relative when under the checkout
WITH_DEPS=0
MODE="run"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-deps) WITH_DEPS=1; shift ;;
    --plan) MODE="plan"; shift ;;
    -h|--help)
      # Print the whole header comment (lines 2 through the last #-line):
      # the venv requirement and the test-only env override live at the
      # bottom of the header, and --help truncating them off once hid the
      # script's most important usage constraint.
      awk 'NR==1{next} /^\s*[^#\s]/ {exit} {print}' "$SCRIPT_DIR/png-smoke.sh"
      exit 0 ;;
    *) echo "png-smoke.sh: unknown flag: $1 (see --help)" >&2; exit 2 ;;
  esac
done

# Resolve the playwright pin from the pins conf. Fail closed on a missing or
# malformed pin: running the smoke against an unknown playwright version is
# worse than not running it.
resolve_pin() {
  local line
  line="$(grep -E '^[[:space:]]*playwright[[:space:]]*=' "$PINS_CONF" 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  line="${line%%#*}"  # the conf format allows trailing `#` comments
  line="$(printf '%s' "$line" | tr -d '[:space:]')"
  # Three-part version required: the install-vs-skip check below compares
  # against `playwright.__version__` verbatim, and a two-part pin would
  # reinstall on every run.
  if [[ ! "$line" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "png-smoke.sh: cannot resolve a playwright pin from $PINS_CONF (fail-closed)" >&2
    return 1
  fi
  printf '%s' "$line"
}

PIN="$(resolve_pin)"

if [[ "$MODE" == "plan" ]]; then
  cat <<EOF
png-smoke plan (nothing executed):
  1. playwright pin      — $PIN (from $PINS_DISPLAY)
  2. venv check          — requires the CONTRIBUTING.md venv (VIRTUAL_ENV)
  3. pip install         — playwright==$PIN into the venv (skipped if the
                           installed version already matches)
  4. browser install     — python3 -m playwright install$([[ "$WITH_DEPS" == "1" ]] && printf ' --with-deps') chromium
  5. screenshot          — rm -f /tmp/pw-test.png; python3 scripts/pw-test.py
  6. PNG check           — python3 scripts/png-check.py
EOF
  exit 0
fi

[[ -n "${VIRTUAL_ENV:-}" ]] || {
  echo "png-smoke.sh: no active venv (VIRTUAL_ENV is unset) — activate the" >&2
  echo "CONTRIBUTING.md venv first; playwright is installed there, never into" >&2
  echo "the system Python." >&2
  exit 2
}

installed_version() {
  # Resolved via the venv's bin dir, not PATH: a manually-exported
  # VIRTUAL_ENV without activation must still not touch system Python.
  "$VIRTUAL_ENV/bin/python3" -c 'import playwright; print(playwright.__version__)' 2>/dev/null || true
}

step() { echo "=== png-smoke: $1 ==="; }

step "playwright==$PIN (pins: $PINS_DISPLAY)"
if [[ "$(installed_version)" == "$PIN" ]]; then
  echo "png-smoke: playwright $PIN already installed — skipping pip install"
else
  "$VIRTUAL_ENV/bin/pip" install "playwright==$PIN"
fi

step "playwright install chromium"
if [[ "$WITH_DEPS" == "1" ]]; then
  "$VIRTUAL_ENV/bin/python3" -m playwright install --with-deps chromium
else
  "$VIRTUAL_ENV/bin/python3" -m playwright install chromium
fi

step "screenshot (scripts/pw-test.py)"
rm -f /tmp/pw-test.png  # a stale screenshot must not mask a pw-test failure
"$VIRTUAL_ENV/bin/python3" scripts/pw-test.py

step "PNG check (scripts/png-check.py)"
"$VIRTUAL_ENV/bin/python3" scripts/png-check.py

echo "=== png-smoke: PASS (playwright $PIN) ==="
