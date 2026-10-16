"""Pin tests for scripts/install.sh (issue #1526).

The installer is the machine form of the README "Try it" runbook. These
tests pin its load-bearing properties without needing a fresh VM:

1. Sourcing safety — the test suite sources install.sh to exercise the
   step functions; sourcing must define the steps and change nothing.
2. Idempotency — each step skips when its end state already holds, and the
   mutation paths that are pinned perform exactly once when it does not.
   External commands are stubbed as bash functions (they shadow PATH
   lookup), so the real step logic runs against a fake box.
3. Flag contracts — env-passed flags survive sourcing (the bootstrap ->
   agent re-exec passes flags via environment); --dry-run prints the plan,
   exits 0, and mutates nothing on a fresh box.
4. Agent-owned checkout — the agent phase never touches the invoker's
   checkout; it derives $AGENT_REPO from the agent user's passwd entry.
5. No-drift — the README "Try it" section calls the script instead of
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
    "parse_args",
    "main",
]


def run_bash(code, env=None, cwd=None):
    """Run bash code in a fresh shell."""
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


def test_env_flags_survive_sourcing():
    # The bootstrap -> agent re-exec passes flags via environment (env(1));
    # plain assignments would clobber them (notably --agent-user and --force).
    code = (
        "export AGENT_USER=alice DRY_RUN=1 FORCE=1; "
        f"source {SCRIPT} >/dev/null 2>&1; "
        '[ "$AGENT_USER" = alice ] || { echo "AGENT_USER clobbered: $AGENT_USER"; exit 1; }; '
        '[ "$DRY_RUN" = 1 ] || { echo "DRY_RUN clobbered: $DRY_RUN"; exit 1; }; '
        '[ "$FORCE" = 1 ] || { echo "FORCE clobbered: $FORCE"; exit 1; }; '
        "echo OK"
    )
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

    proc = run_bash(f"bash {SCRIPT} --agent-user root")
    assert proc.returncode != 0
    assert "--agent-user root" in proc.stderr


def test_sudoers_write_is_idempotent_and_atomic(tmp_path):
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


def test_sudoers_visudo_failure_writes_nothing(tmp_path):
    sudoers_d = tmp_path / "sudoers.d"
    sudoers_d.mkdir()
    code = source_preamble()
    code += textwrap.dedent(
        f"""\
        SUDOERS_DIR="{sudoers_d}"; AGENT_USER=ntindle
        visudo() {{ return 1; }}
        if ( step_sudoers ) 2>/dev/null; then echo "did not die on visudo failure"; exit 1; fi
        [ ! -e "{sudoers_d}/ntindle" ] || {{ echo "broken drop left behind"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_agent_user_skips_when_present_and_creates_when_missing():
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


def test_tailscale_up_skips_when_already_up_and_dies_when_join_fails(tmp_path):
    state = tmp_path / "ts-up"
    code = source_preamble()
    code += textwrap.dedent(
        f"""\
        AGENT_USER=ntindle; DRY_RUN=0
        TS_STATE="{state}"
        TS_UP_FAIL=0
        tailscale() {{
          if [ "$1" = "status" ]; then [ -f "$TS_STATE" ];
          elif [ "$1" = "up" ]; then [ "$TS_UP_FAIL" = 1 ] && return 1; touch "$TS_STATE";
          fi
        }}
        sudo() {{ "$@"; }}
        touch "$TS_STATE"
        out=$(step_tailscale_up 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "failed when up: $out"; exit 1; }}
        echo "$out" | grep -q "skip: tailscale already up" || {{ echo "no skip: $out"; exit 1; }}
        rm -f "$TS_STATE"
        out=$(step_tailscale_up 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "failed to join: $out"; exit 1; }}
        echo "$out" | grep -q "tailscale is up" || {{ echo "no up note: $out"; exit 1; }}
        rm -f "$TS_STATE"; TS_UP_FAIL=1
        if ( step_tailscale_up ) 2>/dev/null; then echo "did not die when join failed"; exit 1; fi
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def _agent_harness(tmp_path, fresh):
    """Sandbox agent HOME + stub overrides for the agent phase.

    fresh=True: nothing installed yet (for the dry-run test).
    fresh=False: every step already holds (for the no-op test).
    Returns (bash_code_prefix, call_log_path, agent_home, agent_repo).
    """
    agent_home = tmp_path / "agent-home"
    agent_home.mkdir(parents=True)
    agent_repo = agent_home / "spark-vm"
    if not fresh:
        repo_muse_job = agent_repo / "muse-job" / "bin"
        repo_muse_job.mkdir(parents=True)
        repo_muse_job.joinpath("muse-job").write_bytes(
            (REPO / "muse-job" / "bin" / "muse-job").read_bytes()
        )
        (agent_repo / ".git").mkdir()
        repo_unit = agent_repo / "cred-ui"
        repo_unit.mkdir()
        repo_unit.joinpath("cred-ui.service").write_bytes(
            (REPO / "cred-ui" / "cred-ui.service").read_bytes()
        )
        (agent_home / "bin").mkdir()
        (agent_home / "bin" / "muse-job").write_bytes(
            (REPO / "muse-job" / "bin" / "muse-job").read_bytes()
        )
        unit_dir = agent_home / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)
        unit_dir.joinpath("cred-ui.service").write_bytes(
            (REPO / "cred-ui" / "cred-ui.service").read_bytes()
        )
    sudoers_d = tmp_path / "sudoers.d"
    sudoers_d.mkdir(exist_ok=True)
    if not fresh:
        sudoers_d.joinpath("ntindle").write_text("ntindle ALL=(ALL) NOPASSWD: ALL\n")
    call_log = tmp_path / "calls.log"
    call_log.write_text("")
    git_log = tmp_path / "git.log"
    git_log.write_text("")
    # In the no-op case tailscale/muse exist; in the fresh case they don't.
    have_tailscale = "return 0" if not fresh else "return 1"
    have_muse = "return 0" if not fresh else "return 1"
    ts_status = "return 0" if not fresh else "return 1"
    linger = 'echo "Linger=yes"' if not fresh else "return 1"
    harness = textwrap.dedent(
        f"""\
        CALL_LOG="{call_log}"; GIT_LOG="{git_log}"
        AGENT_HOME="{agent_home}"
        log_mut() {{ echo "MUTATE $*" >> "$CALL_LOG"; }}
        id() {{ case "$1" in -u) echo 1001;; -un) echo "ntindle";; -nG) echo "ntindle sudo";; *) return 0;; esac; }}
        getent() {{ case "$1 $2" in "passwd ntindle") echo "ntindle:x:1001:1001:Agent User:$AGENT_HOME:/bin/bash";; "group sudo") echo "sudo:x:27:";; *) return 1;; esac; }}
        tailscale() {{ case "$1" in status) {ts_status};; up) echo "tailscale up"; return 0;; esac; }}
        loginctl() {{ case "$1" in show-user) {linger};; *) log_mut "loginctl $*";; esac; return 0; }}
        git() {{ echo "git $*" >> "$GIT_LOG"; case "$*" in *"symbolic-ref"*) echo main;; *"pull"*) return 0;; esac; return 0; }}
        systemctl() {{
          [ "$1" = "--user" ] && shift
          case "${1:-} ${2:-}" in
            "is-active --quiet"|"is-enabled --quiet") {"return 0" if not fresh else "return 1"};;
            *) log_mut "systemctl $*";;
          esac
          return 0
        }}
        muse() {{ if [ "$1 $2" = "plugins list" ]; then {"echo muse-job" if not fresh else ":"}; else log_mut "muse $*"; fi; return 0; }}
        sudo() {{ log_mut "sudo $*"; return 0; }}
        curl() {{ log_mut "curl $*"; }}
        cp() {{ log_mut "cp $*"; }}
        apt-get() {{ log_mut "apt-get $*"; }}
        env() {{ if [ "$1" = "-C" ]; then log_mut "env $*"; return 0; fi; command env "$@"; }}
        command() {{
          if [ "$1" = "-v" ]; then
            case "$2" in tailscale) {have_tailscale};; muse) {have_muse};; *) builtin command "$@"; return $?;; esac
          fi
          builtin command "$@"
        }}
        """
    )
    return harness, call_log, git_log, agent_home, agent_repo, sudoers_d


def test_noop_second_run_only_touches_self_idempotent_cua(tmp_path):
    # The agent phase must never touch the invoker's checkout: REPO_DIR
    # points at a nonexistent path to prove the split (QA1's bug class).
    harness, call_log, git_log, agent_home, agent_repo, sudoers_d = _agent_harness(
        tmp_path, fresh=False
    )
    code = source_preamble() + harness
    code += textwrap.dedent(
        f"""\
        export HOME="{agent_home}" SUDOERS_DIR="{sudoers_d}" AGENT_USER=ntindle DRY_RUN=0
        export REPO_DIR="/nonexistent/invoker-checkout" AGENT_REPO="{agent_repo}"
        run_agent
        echo "---CALLS---"; cat "{call_log}"
        echo "---GIT---"; cat "{git_log}"
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    calls = proc.stdout.split("---CALLS---")[1].split("---GIT---")[0]
    mutates = [line for line in calls.splitlines() if line.startswith("MUTATE")]
    # Every step skips except step_cua, which shells out to cua-desktop.sh
    # start — itself idempotent (skips running components).
    assert len(mutates) == 1, f"unexpected mutations on no-op run: {mutates}"
    assert mutates[0].startswith("MUTATE env -C "), mutates
    assert mutates[0].endswith("./cua/bin/cua-desktop.sh start"), mutates
    assert str(agent_repo) in mutates[0], "cua start must run from the AGENT checkout"
    git_calls = proc.stdout.split("---GIT---")[1]
    assert "/nonexistent" not in git_calls, f"agent phase touched invoker checkout: {git_calls}"
    assert "skip: tailscale already up" in proc.stdout
    assert "skip: linger already enabled" in proc.stdout
    assert "skip: ~/bin/muse-job already matches" in proc.stdout


def test_dry_run_mutates_nothing_and_exits_zero(tmp_path):
    harness, call_log, git_log, agent_home, agent_repo, sudoers_d = _agent_harness(
        tmp_path, fresh=True
    )
    code = source_preamble() + harness
    code += textwrap.dedent(
        f"""\
        export HOME="{agent_home}" SUDOERS_DIR="{sudoers_d}" AGENT_USER=ntindle DRY_RUN=1
        export REPO_DIR="/nonexistent/invoker-checkout" AGENT_REPO="{agent_home}/spark-vm"
        run_agent
        echo "---CALLS---"; cat "{call_log}"
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "would " in proc.stdout, "dry-run must describe the plan"
    calls = proc.stdout.split("---CALLS---")[1]
    mutates = [line for line in calls.splitlines() if line.startswith("MUTATE")]
    assert mutates == [], f"dry-run mutated: {mutates}"
    assert "would join the tailnet" in proc.stdout
    assert "muse CLI not present yet" in proc.stdout


def test_bootstrap_noop_only_reexecs(tmp_path):
    harness, call_log, git_log, agent_home, agent_repo, sudoers_d = _agent_harness(
        tmp_path, fresh=False
    )
    invoker_home = tmp_path / "invoker-home"
    (invoker_home / ".ssh").mkdir(parents=True)
    key = "ssh-ed25519 AAAAtestkey invoker@box"
    (invoker_home / ".ssh" / "authorized_keys").write_text(key + "\n")
    (agent_home / ".ssh").mkdir(parents=True)
    (agent_home / ".ssh" / "authorized_keys").write_text(key + "\n")
    # `exec` does PATH lookup, bypassing shell-function overrides — the fake
    # sudo must be a real executable on PATH to intercept the re-exec.
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    (fakebin / "sudo").write_text(
        '#!/bin/bash\necho "MUTATE sudo $*" >> "%s"\nexit 0\n' % call_log
    )
    (fakebin / "sudo").chmod(0o755)
    code = source_preamble() + harness
    code += textwrap.dedent(
        f"""\
        export PATH="{fakebin}:$PATH"
        export SUDOERS_DIR="{sudoers_d}" AGENT_USER=ntindle DRY_RUN=0 SUDO_USER=testinvoker
        id() {{ case "$1" in -u) echo 0;; -un) echo root;; -nG) echo "root sudo";; *) return 0;; esac; }}
        getent() {{
          case "$1 $2" in
            "passwd ntindle") echo "ntindle:x:1001:1001:Agent User:{agent_home}:/bin/bash";;
            "passwd testinvoker") echo "testinvoker:x:1002:1002:Invoker:{invoker_home}:/bin/bash";;
            "group sudo") echo "sudo:x:27:";;
            *) return 1;;
          esac
        }}
        adduser() {{ log_mut "adduser $*"; }}; usermod() {{ log_mut "usermod $*"; }}
        install() {{ log_mut "install $*"; return 0; }}
        visudo() {{ return 0; }}
        run_bootstrap
        # NOTE: run_bootstrap ends in `exec sudo -iu ...`; the stubbed sudo
        # returns 0, so the shell exits here — assertions read the log file.
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    mutates = [l for l in call_log.read_text().splitlines() if l.startswith("MUTATE")]
    # Everything holds; the only action is the login-shell re-exec into the
    # agent phase (sudo itself is stubbed, so it cannot actually exec).
    assert len(mutates) == 1, f"unexpected bootstrap mutations: {mutates}"
    assert mutates[0].startswith("MUTATE sudo -iu ntindle env "), mutates
    assert "--agent-phase-internal" in mutates[0]
    assert "skip: user ntindle exists" in proc.stdout
    assert "passwordless sudo for ntindle" in proc.stdout


def test_agent_phase_ignores_unreadable_delivery_checkout(tmp_path):
    # Option B: the invoker's checkout lives under /root (mode 700) — the
    # agent phase works only in the agent-owned checkout, so main() must
    # not gate the re-exec on the delivery checkout's readability.
    harness, call_log, git_log, agent_home, agent_repo, sudoers_d = _agent_harness(
        tmp_path, fresh=False
    )
    code = source_preamble() + harness
    code += textwrap.dedent(
        f"""\
        export HOME="{agent_home}" SUDOERS_DIR="{sudoers_d}" AGENT_USER=ntindle DRY_RUN=0
        export REPO_DIR="/nonexistent/invoker-checkout" AGENT_REPO="{agent_repo}"
        main --agent-phase-internal
        echo "---CALLS---"; cat "{call_log}"
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    calls = proc.stdout.split("---CALLS---")[1]
    mutates = [line for line in calls.splitlines() if line.startswith("MUTATE")]
    assert len(mutates) == 1 and "cua-desktop.sh start" in mutates[0], mutates


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
