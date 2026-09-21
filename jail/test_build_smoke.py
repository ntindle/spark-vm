"""Smoke test for jail/build.sh.

build.sh provisions the agent jail (systemd-nspawn, veth, nftables,
guest packages) and requires root, debootstrap, and the swapd CA — it
cannot execute on a dev box or CI runner. The executable maximum is:

1. `bash build.sh --help` — runs the REAL script through its argument
   parsing and exits 0 before any side effect (the --help branch sits
   above every $SUDO / filesystem / network step). This proves the
   script starts, parses, and renders its usage doc on this machine.
2. `bash -n` syntax + a shellcheck -S warning gate, with an explicit
   skip (not a silent pass) when shellcheck is not installed.

Honest boundary, stated once: nothing here proves the jail builds.
That verification happens on spark-vm by the operator running
build.sh itself.
"""

import os
import re
import subprocess

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_SH = os.path.join(REPO_ROOT, "jail", "build.sh")

# Statement kinds that are provably side-effect-free: anything else above
# the --help branch is treated as a potential side effect and fails
# test_help_branch_precedes_all_side_effects.
# NOTE: every pattern is full-line anchored ($). The earlier prefix-match
# versions let side-effecting statements sail through (e.g. a one-line
# `for` with an arbitrary body, `VAR=val cmd` env-prefix execution, or
# `set -euo pipefail; touch /tmp/pwned` chained after an allowed prefix).
_SIDE_EFFECT_FREE = (
    re.compile(r"^set(?:\s+[a-zA-Z-]+)+\s*$"),
    re.compile(r"^(?:(?:readonly|export|declare|local)\s+)?"
               r"(?:[A-Za-z_][A-Za-z0-9_]*="
               r"(?:\"[^\"]*\"|'[^']*'|[^\s;|&(){}]*)\s*)+$"),
    re.compile(r"^for\s+\w+\s+in\b.*\bdo\s+"
               r"(?:\[.*?\]\s*(?:&&|\|\|)\s*)?"
               r"[A-Za-z_][A-Za-z0-9_]*=\S*\s*;\s*done\s*$"),
    re.compile(r"^\[.*\]\s*(?:&&|\|\|)\s*"
               r"[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S*)\s*$"),
)


def run_bash(*argv, cwd=REPO_ROOT):
    return subprocess.run(
        ["bash", *argv], capture_output=True, text=True, timeout=60, cwd=cwd)


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_exits_zero_with_usage(flag):
    r = run_bash(BUILD_SH, flag)
    assert r.returncode == 0, f"build.sh {flag} failed:\n{r.stderr}"
    # The help path renders the script's header doc: the jail's
    # properties a contributor needs before ever running it as root.
    assert "systemd-nspawn" in r.stdout
    assert "jail" in r.stdout.lower()


def test_help_runs_from_another_cwd():
    # $0 resolution must not depend on being run from the repo root.
    r = subprocess.run(
        ["bash", BUILD_SH, "--help"],
        capture_output=True, text=True, timeout=60, cwd="/tmp")
    assert r.returncode == 0, r.stderr


# Process substitution (<(...) / >(...)) executes a command exactly like
# $(...) does, and neither contains "$(" nor a backtick — so the
# pre-check must name it explicitly (the regexes' .* /\S* slots accept it).
def _assert_side_effect_free(ln):
    # Command or process substitution can run arbitrary commands — never
    # allowed above the --help branch, even inside an assignment.
    assert "$(" not in ln and "`" not in ln and "<(" not in ln and ">(" not in ln, (
        f"command/process substitution above the --help branch: {ln!r}")
    assert any(p.search(ln) for p in _SIDE_EFFECT_FREE), (
        f"statement above the --help branch may have side effects: {ln!r}")


def test_help_branch_precedes_all_side_effects():
    # The --help contract ("exits before any side effect") is enforced
    # structurally: if a future edit inserts a side-effecting statement
    # above the --help branch, this fails even though --help still exits 0.
    lines = open(BUILD_SH).read().splitlines()
    code = [ln.split("#", 1)[0].rstrip() for ln in lines]
    code = [ln for ln in code if ln.strip()]
    idx = next(
        i for i, ln in enumerate(code)
        if re.search(r'\[\s*"\$\{1:-\}"\s*=\s*"--help"\s*\]', ln))
    for ln in code[:idx]:
        _assert_side_effect_free(ln)


@pytest.mark.parametrize("mutant", [
    # Process substitution executes a command without "$(" or a backtick;
    # each of these ran real commands in bash and evaded the old
    # substitution pre-check (the last two were caught by the old
    # pattern check, which is exactly why the pre-check is the fix).
    "for a in <(touch /tmp/pw4); do X=1; done",
    "for a in x <(touch /tmp/pw5); do X=1; done",
    "for a in >(touch /tmp/pw6); do X=1; done",
    "[ -n x ] && Y=<(touch /tmp/pw8)",
    "for a in x; do X=<(touch /tmp/pw9); done",
])
def test_help_tripwire_rejects_process_substitution(mutant):
    # Regression: the per-line gate must reject process substitution the
    # same way it rejects command substitution.
    with pytest.raises(AssertionError, match="substitution"):
        _assert_side_effect_free(mutant)


def test_shell_syntax():
    r = run_bash("-n", BUILD_SH)
    assert r.returncode == 0, f"bash -n failed:\n{r.stderr}"


def test_shellcheck_no_warnings():
    if run_bash("-c", "command -v shellcheck").returncode != 0:
        pytest.skip("shellcheck not installed; syntax-only gate applied")
    r = subprocess.run(
        ["shellcheck", "-S", "warning", BUILD_SH],
        capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"shellcheck warnings in jail/build.sh:\n{r.stdout}"
