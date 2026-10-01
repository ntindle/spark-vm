"""Tests for the TUI auto-update deferral policy (issue #699).

#699 decides the deferred half of #212's policy question: while a job is
active, its TUI must not stage a launcher auto-update mid-turn. The
mechanism is the launcher's own documented-by-source switch -- the bash
launcher at ~/.local/bin/muse gates its hourly check+download on
`MUSE_NO_AUTO_UPDATE=1` (verified in the launcher source on a provisioned
box: `[[ "${MUSE_NO_AUTO_UPDATE:-0}" != 1 ]] && should_check_for_update
...`, and a missing binary fails loud instead of self-healing).

These tests pin:
1. The builder produces exactly the launcher's switch, in the shell
   position where it applies to the `muse` invocation (env-prefix before
   the command word).
2. The switch actually reaches the invoked process (executed through
   bash, non-vacuous: stripping the prefix fails the assertion).
3. Every TUI launch site in the CLI routes through the builder, so a
   future fourth launch site cannot silently skip the policy.
"""
import importlib.machinery
import importlib.util
import os
import re
import subprocess
import sys

import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job")


def load_script(name, path):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


@pytest.fixture()
def cli(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_tui_update_policy", CLI_PATH)


def test_prefix_is_the_launcher_switch(cli):
    """The policy mechanism is exactly the launcher's no-auto-update env
    var, as a shell env-prefix (trailing space). A bare different name or
    a malformed assignment (space inside, missing =) would not suppress
    the launcher's check, so the exact shape is pinned."""
    prefix = cli._tui_launch_prefix()
    assert prefix == "MUSE_NO_AUTO_UPDATE=1 "
    name, _, value = prefix.strip().partition("=")
    assert name == "MUSE_NO_AUTO_UPDATE" and value == "1"
    assert " " not in prefix.strip(), "env assignment must be one word"


def test_launch_cmd_applies_switch_to_muse_invocation(cli):
    """The env prefix sits before the `muse` command word, so the shell
    applies it to the muse process (and everything it re-execs)."""
    cmd = cli._tui_launch_cmd("--yolo", "'/tmp/prompt.md'")
    assert cmd == "MUSE_NO_AUTO_UPDATE=1 muse --yolo '/tmp/prompt.md'"
    cmd = cli._tui_launch_cmd("resume", "'some-uuid'")
    assert cmd == "MUSE_NO_AUTO_UPDATE=1 muse resume 'some-uuid'"


def test_switch_reaches_the_invoked_process(cli):
    """Non-vacuous: run the built command through bash with a stub and
    prove the env var lands in the launched process's environment. If the
    prefix were moved after the command word or mangled, the value would
    not arrive."""
    # Build a probe through the real builder, then swap the `muse printenv`
    # command words for plain `printenv` (case-sensitive: the VAR name's
    # MUSE is uppercase and does not match).
    probe = cli._tui_launch_cmd("printenv", "MUSE_NO_AUTO_UPDATE")
    probe = probe.replace("muse printenv", "printenv", 1)
    r = subprocess.run(["bash", "-c", probe], capture_output=True, text=True,
                       timeout=30)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "1"


def test_switch_absent_means_no_suppression(cli):
    """Control for the non-vacuity claim above: the same probe WITHOUT the
    policy prefix must NOT deliver the variable (guards against a test
    that passes because the parent env leaks it in)."""
    assert "MUSE_NO_AUTO_UPDATE" not in os.environ
    r = subprocess.run(["bash", "-c", "printenv MUSE_NO_AUTO_UPDATE"],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 1
    assert r.stdout.strip() == ""


def test_all_tui_launch_sites_use_the_builder(cli):
    """Every `muse --yolo` / `muse resume` TUI launch in the CLI must be
    constructed by _tui_launch_cmd (the policy lives there). Skips comments,
    docstrings, and the builder's own definition."""
    src = open(CLI_PATH, encoding="utf-8").read()
    offenders = []
    in_def = None
    in_docstring = False
    for lineno, line in enumerate(src.splitlines(), 1):
        stripped = line.strip()
        m = re.match(r"def (\w+)\(", stripped)
        if m:
            in_def = m.group(1)
            in_docstring = False
        if stripped.startswith('"""') or stripped.startswith("'''"):
            # crude docstring toggle; good enough for launch-line scanning
            if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                pass
            else:
                in_docstring = not in_docstring
            continue
        if in_docstring or stripped.startswith("#"):
            continue
        if in_def == "_tui_launch_cmd":
            continue
        if re.search(r"\bmuse (--yolo|resume)\b", line) and \
                "_tui_launch_cmd" not in line:
            offenders.append((lineno, line.strip()))
    assert not offenders, \
        "TUI launch sites bypassing _tui_launch_cmd (missing #699 deferral): %r" % (
            offenders,)
