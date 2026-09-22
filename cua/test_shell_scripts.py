"""Shell-script gates for cua/bin/*.sh.

The CUA desktop stack's shell scripts (desktop lifecycle, keepalive,
GUI launchers) run on spark-vm with real side effects, so they cannot
be executed in CI. The executable maximum is what CI itself does for
other host-side scripts (see deploy/test_auto_deploy.py): `bash -n`
syntax plus a shellcheck -S warning gate, with an explicit skip (not a
silent pass) when shellcheck is not installed.
"""

import os
import subprocess

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = sorted(
    os.path.join(REPO_ROOT, "cua", "bin", f)
    for f in os.listdir(os.path.join(REPO_ROOT, "cua", "bin"))
    if f.endswith(".sh")
)

# One probe, not one per parametrized script.
_HAS_SHELLCHECK = subprocess.run(
    ["bash", "-c", "command -v shellcheck"],
    capture_output=True, text=True, timeout=60).returncode == 0


def run_bash(*argv):
    return subprocess.run(
        ["bash", *argv], capture_output=True, text=True, timeout=60)


def test_cua_bin_has_shell_scripts():
    # Guards the gate below against silently passing on an empty list
    # (e.g. if the scripts ever move).
    assert SCRIPTS, "no .sh files found under cua/bin"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: os.path.basename(p))
def test_shell_syntax(script):
    r = run_bash("-n", script)
    assert r.returncode == 0, f"bash -n failed for {script}:\n{r.stderr}"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: os.path.basename(p))
def test_shellcheck_no_warnings(script):
    if not _HAS_SHELLCHECK:
        pytest.skip("shellcheck not installed; syntax-only gate applied")
    r = subprocess.run(
        ["shellcheck", "-S", "warning", script],
        capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"shellcheck warnings in {script}:\n{r.stdout}"
