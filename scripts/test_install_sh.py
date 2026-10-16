"""Pin tests for scripts/install.sh (issue #1526).

The installer is the machine form of the README "Try it" runbook. These
tests pin its three load-bearing properties without needing a fresh VM:

1. Sourcing safety — the test suite sources install.sh to exercise the
   step functions; sourcing must define the steps and change nothing.
2. Idempotency — each step skips when its end state already holds, and
   performs its mutation exactly once when it does not. External commands
   are stubbed as bash functions (they shadow PATH lookup), so the real
   step logic runs against a fake box.
3. No-drift — the README "Try it" section calls the script instead of
   inlining the runbook, so the two cannot drift.
"""

import os
import shutil
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "install.sh"
README = REPO / "README.md"

STEP_FNS = [
    "step_prereqs",
    "step_agent_user",
    "step_sudoers",
    "step_ssh_key",
    "step_tailscale_install",
    "step_tailscale_up",
    "step_linger",
    "step_repo",
    "step_deploy",
    "step_muse_job",
    "step_plugin",
    "step_cred_ui",
    "step_cua",
    "run_bootstrap",
    "run_agent",
    "main",
]


def run_bash(code, env=None, cwd=None):
    """Run bash code with `set -u` semantics relaxed for the harness."""
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.run(
        ["bash", "-c", code],
        capture_output=True,
        text=True,
        env=merged,
        cwd=cwd or str(REPO),
        timeout=60,
    )


def source_preamble():
    # Source in the CURRENT shell (not a command substitution — defined
    # functions must survive). The script's `set -euo pipefail` stays in
    # effect afterwards, which is also the faithful execution environment.
    # Sourcing must be silent (no output) and side-effect free.
    return (
        "_src_out=$(mktemp); "
        f"source {SCRIPT} >\"$_src_out\" 2>&1; _src_rc=$?; "
        '_src_content=$(cat "$_src_out"); rm -f "$_src_out"; '
        '[ "$_src_rc" = 0 ] || { echo "source failed: $_src_content"; exit 9; }; '
        '[ -z "$_src_content" ] || { echo "sourcing printed: $_src_content"; exit 9; }; '
    )


def test_source_defines_steps_without_side_effects(tmp_path):
    sentinel = tmp_path / "sudoers.d"
    code = source_preamble()
    for fn in STEP_FNS:
        code += f"declare -F {fn} >/dev/null || {{ echo 'missing: {fn}'; exit 1; }}; "
    code += f'[ ! -e "{sentinel}" ] || {{ echo "side effect!"; exit 1; }}; echo OK'
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip() == "OK"


def test_help_and_bad_args():
    proc = run_bash(f"bash {SCRIPT} --help")
    assert proc.returncode == 0
    assert "Usage:" in proc.stdout
    assert "--dry-run" in proc.stdout

    proc = run_bash(f"bash {SCRIPT} --bogus-flag")
    assert proc.returncode != 0
    assert "unknown argument" in proc.stderr

    proc = run_bash(f"bash {SCRIPT} --agent-user 'not a user!'")
    assert proc.returncode != 0
    assert "bad --agent-user name" in proc.stderr


def test_sudoers_write_is_idempotent(tmp_path):
    sudoers_d = tmp_path / "sudoers.d"
    sudoers_d.mkdir()
    code = source_preamble()
    code += textwrap.dedent(
        f"""\
        SUDOERS_DIR="{sudoers_d}"; AGENT_USER=ntindle
        visudo() {{ echo "visudo $*"; return 0; }}
        step_sudoers
        f="{sudoers_d}/ntindle"
        [ -f "$f" ] || {{ echo "not written"; exit 1; }}
        [ "$(cat "$f")" = "ntindle ALL=(ALL) NOPASSWD: ALL" ] || {{ echo "bad content"; exit 1; }}
        [ "$(stat -c %a "$f")" = "440" ] || {{ echo "bad mode"; exit 1; }}
        before=$(stat -c %Y "$f")
        sleep 1
        out=$(step_sudoers 2>&1)
        after=$(stat -c %Y "$f")
        [ "$before" = "$after" ] || {{ echo "rewritten on second run"; exit 1; }}
        echo "$out" | grep -q "skip:" || {{ echo "no skip note: $out"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_agent_user_skips_when_present_and_creates_when_missing(tmp_path):
    code = source_preamble()
    code += textwrap.dedent(
        """\
        AGENT_USER=ntindle
        USER_EXISTS=1
        id() { case "$1" in -u) [ "$USER_EXISTS" = 1 ];; -nG) echo "ntindle sudo";; *) return 0;; esac; }
        getent() { return 0; }
        adduser() { echo "MUTATE adduser $*"; }
        usermod() { echo "MUTATE usermod $*"; }
        out=$(step_agent_user 2>&1)
        echo "$out" | grep -q "skip: user ntindle exists" || { echo "no skip: $out"; exit 1; }
        echo "$out" | grep -q MUTATE && { echo "mutated on no-op: $out"; exit 1; }
        USER_EXISTS=0
        out=$(step_agent_user 2>&1)
        echo "$out" | grep -q "MUTATE adduser" || { echo "did not create: $out"; exit 1; }
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_tailscale_up_skips_when_already_up(tmp_path):
    state = tmp_path / "ts-up"
    code = source_preamble()
    code += textwrap.dedent(
        f"""\
        AGENT_USER=ntindle
        TS_STATE="{state}"
        tailscale() {{
          if [ "$1" = "status" ]; then [ -f "$TS_STATE" ]; else return 1; fi
        }}
        sudo() {{ echo "MUTATE sudo $*"; "$@"; }}
        # already up -> skip, no `up` call
        touch "$TS_STATE"
        out=$(step_tailscale_up 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "failed when up: $out"; exit 1; }}
        echo "$out" | grep -q "skip: tailscale already up" || {{ echo "no skip: $out"; exit 1; }}
        # down -> joins, then the verify probe passes
        rm -f "$TS_STATE"
        tailscale() {{
          if [ "$1" = "status" ]; then [ -f "$TS_STATE" ];
          elif [ "$1" = "up" ]; then touch "$TS_STATE"; return 0; fi
        }}
        out=$(step_tailscale_up 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "failed to join: $out"; exit 1; }}
        echo "$out" | grep -q "MUTATE sudo tailscale up" || {{ echo "no up call: $out"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def _noop_harness(tmp_path):
    """Build a sandbox HOME + stub overrides where every step already holds.

    Returns the bash preamble defining the overrides. Every override logs
    mutating invocations as MUTATE lines; the test then asserts the only
    MUTATE is the (self-idempotent) cua-desktop start.
    """
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    (home / ".config" / "systemd" / "user").mkdir(parents=True)
    # ~/bin/muse-job and the cred-ui unit already match the repo copies.
    (home / "bin" / "muse-job").write_bytes((REPO / "muse-job" / "bin" / "muse-job").read_bytes())
    (home / ".config" / "systemd" / "user" / "cred-ui.service").write_bytes(
        (REPO / "cred-ui" / "cred-ui.service").read_bytes()
    )
    sudoers_d = tmp_path / "sudoers.d"
    sudoers_d.mkdir()
    (sudoers_d / "ntindle").write_text("ntindle ALL=(ALL) NOPASSWD: ALL\n")
    call_log = tmp_path / "calls.log"
    call_log.write_text("")
    return home, sudoers_d, call_log, textwrap.dedent(
        f"""\
        CALL_LOG="{call_log}"
        log_mut() {{ echo "MUTATE $*" >> "$CALL_LOG"; }}
        id() {{ case "$1" in -u) echo 1001;; -un) echo "ntindle";; -nG) echo "ntindle sudo";; *) return 0;; esac; }}
        getent() {{ echo "ntindle:x:1001:1001::{home}:/bin/bash"; return 0; }}
        tailscale() {{ [ "$1" = "status" ] && return 0 || return 1; }}
        loginctl() {{ case "$1" in show-user) echo "Linger=yes";; *) log_mut "loginctl $*";; esac; return 0; }}
        git() {{ return 0; }}
        systemctl() {{
          [ "$1" = "--user" ] && shift
          case "$1 $2" in
            "is-active --quiet"|"is-enabled --quiet") return 0;;
            *) log_mut "systemctl $*";;
          esac
          return 0
        }}
        muse() {{ if [ "$1 $2" = "plugins list" ]; then echo "muse-job"; else log_mut "muse $*"; fi; return 0; }}
        sudo() {{ log_mut "sudo $*"; return 0; }}
        adduser() {{ log_mut "adduser $*"; }}; usermod() {{ log_mut "usermod $*"; }}
        apt-get() {{ log_mut "apt-get $*"; }}; curl() {{ log_mut "curl $*"; }}
        cp() {{ log_mut "cp $*"; }}; install() {{ log_mut "install $*"; }}
        visudo() {{ return 0; }}
        tailscale_install_cmd() {{ log_mut "tailscale-install"; }}
        env() {{ if [ "$1" = "-C" ]; then log_mut "env $*"; return 0; fi; command env "$@"; }}
        command() {{
          if [ "$1" = "-v" ]; then
            case "$2" in tailscale|muse) return 0;; *) builtin command "$@"; return $?;; esac
          fi
          builtin command "$@"
        }}
        """
    )


def test_noop_second_run_only_touches_self_idempotent_cua(tmp_path):
    home, sudoers_d, call_log, harness = _noop_harness(tmp_path)
    code = source_preamble() + harness
    code += textwrap.dedent(
        f"""\
        export HOME="{home}" SUDOERS_DIR="{sudoers_d}" AGENT_USER=ntindle REPO_DIR="{REPO}"
        run_agent
        echo "---CALLS---"; cat "{call_log}"
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    calls = proc.stdout.split("---CALLS---")[1]
    mutates = [line for line in calls.splitlines() if line.startswith("MUTATE")]
    # Every step skips except step_cua, which shells out to cua-desktop.sh
    # start — itself idempotent (skips running components).
    assert len(mutates) == 1, f"unexpected mutations on no-op run: {mutates}"
    assert mutates[0].startswith("MUTATE env -C "), mutates
    assert mutates[0].endswith("./cua/bin/cua-desktop.sh start"), mutates
    assert "skip: tailscale already up" in proc.stdout
    assert "skip: linger already enabled" in proc.stdout
    assert "skip: ~/bin/muse-job already matches" in proc.stdout


def test_readme_try_it_calls_installer_not_inline():
    text = README.read_text()
    start = text.index("## Try it")
    try:
        end = text.index("\n## ", start + 1)
    except ValueError:
        end = len(text)
    section = text[start:end]
    assert "scripts/install.sh" in section, "Try-it must call the installer script"
    assert "sudo tee /etc/sudoers.d/ntindle" not in section, (
        "Try-it must not inline the sudoers drop — that lives in install.sh now"
    )
    assert "curl -fsSL https://tailscale.com/install.sh | sh" not in section, (
        "Try-it must not inline the tailscale install — that lives in install.sh now"
    )
    assert "adduser ntindle" not in section, (
        "Try-it must not inline user creation — that lives in install.sh now"
    )


def test_shellcheck_error_clean():
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck not installed")
    proc = subprocess.run(
        ["shellcheck", "--severity=error", str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
