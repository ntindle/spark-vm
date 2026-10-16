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
    "resolve_install_version",
    "assert_version_matches",
    "step_deploy",
    "step_muse_job",
    "stamp_provenance",
    "step_plugin",
    "step_cred_ui",
    "step_cua",
    "step_stage_repo",
    "stage_repo_copy",
    "staged_copy_current",
    "derive_agent_repo",
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
    # plain assignments would clobber them (notably --agent-user, --force,
    # and --version).
    code = (
        "export AGENT_USER=alice DRY_RUN=1 FORCE=1 INSTALL_VERSION=v1.2.3; "
        f"source {SCRIPT} >/dev/null 2>&1; "
        '[ "$AGENT_USER" = alice ] || { echo "AGENT_USER clobbered: $AGENT_USER"; exit 1; }; '
        '[ "$DRY_RUN" = 1 ] || { echo "DRY_RUN clobbered: $DRY_RUN"; exit 1; }; '
        '[ "$FORCE" = 1 ] || { echo "FORCE clobbered: $FORCE"; exit 1; }; '
        '[ "$INSTALL_VERSION" = v1.2.3 ] || { echo "INSTALL_VERSION clobbered: $INSTALL_VERSION"; exit 1; }; '
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
        # Pinned-release fake: ls-remote above advertises v9.9.9 at deadbeef
        # and rev-parse answers deadbeef for both HEAD and the tag commit,
        # so the existing-checkout path sees the pin as holding.
        agent_repo.joinpath("VERSION").write_text("9.9.9\n")
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
        git() {{ echo "git $*" >> "$GIT_LOG"; case "$*" in *"symbolic-ref"*) echo main;; *"ls-remote --tags"*) printf 'deadbeef\\trefs/tags/v9.9.9\\ndeadbeef2\\trefs/tags/v9.9.9^{{}}\\n';; *"rev-parse"*) echo deadbeef;; *) return 0;; esac; return 0; }}
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


def test_bootstrap_stages_repo_and_reexecs_staged_copy(tmp_path):
    # QA round-2 B1: the re-exec must target the agent-readable staged
    # copy, never the invoker's checkout (which the agent user frequently
    # cannot read — /root is mode 700, human homes are 750).
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
        export REPO_DIR="/nonexistent/invoker-checkout"
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
        mkdir() {{ log_mut "mkdir $*"; }}; chown() {{ log_mut "chown $*"; }}
        visudo() {{ return 0; }}
        run_bootstrap
        # NOTE: run_bootstrap ends in `exec sudo -iu ...`; the fake sudo
        # exits 0, so the shell exits here — assertions read the log file.
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    mutates = [l for l in call_log.read_text().splitlines() if l.startswith("MUTATE")]
    assert len(mutates) == 4, f"unexpected bootstrap mutations: {mutates}"
    assert mutates[0].startswith("MUTATE mkdir "), mutates
    assert mutates[1].startswith("MUTATE cp -a "), mutates
    assert mutates[2].startswith("MUTATE chown -R "), mutates
    assert mutates[3].startswith("MUTATE sudo -iu ntindle env "), mutates
    staged = f"{agent_home}/spark-vm/scripts/install.sh"
    assert staged in mutates[3], f"re-exec must target the staged copy: {mutates[3]}"
    assert "/nonexistent" not in mutates[3], f"re-exec leaked invoker checkout: {mutates[3]}"
    assert "skip: user ntindle exists" in proc.stdout


def test_repo_divergence_dies_loud(tmp_path):
    harness, call_log, git_log, agent_home, agent_repo, sudoers_d = _agent_harness(
        tmp_path, fresh=False
    )
    code = source_preamble() + harness
    code += textwrap.dedent(
        f"""\
        export AGENT_USER=ntindle DRY_RUN=0 AGENT_REPO="{agent_repo}"
        git() {{
          case "$*" in
            *"symbolic-ref"*) echo main;;
            *"remote get-url"*) return 0;;
            *"pull"*) return 1;;
          esac
          return 0
        }}
        if ( step_repo ) 2>/dev/null; then echo "did not die on divergence"; exit 1; fi
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


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


def test_stage_repo_freshness_skip_and_restage(tmp_path):
    # The staged copy must track the WHOLE invoker tree, not just
    # install.sh: a re-run after any invoker edit must re-stage, or the
    # agent phase would silently deploy stale content.
    invoker = tmp_path / "invoker-repo"
    (invoker / "scripts").mkdir(parents=True)
    for cmd in (
        ["git", "init", "-q", str(invoker)],
        ["git", "-C", str(invoker), "config", "user.email", "t@t"],
        ["git", "-C", str(invoker), "config", "user.name", "t"],
    ):
        subprocess.run(cmd, check=True, capture_output=True)
    (invoker / "scripts" / "install.sh").write_text("#!/bin/bash\necho hi\n")
    (invoker / "other.txt").write_text("v1\n")
    subprocess.run(["git", "-C", str(invoker), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(invoker), "commit", "-qm", "init"], check=True, capture_output=True)
    staged = tmp_path / "staged-repo"
    me = subprocess.run(["id", "-un"], capture_output=True, text=True, check=True).stdout.strip()
    code = source_preamble()
    code += textwrap.dedent(
        f"""\
        export AGENT_USER="{me}" REPO_DIR="{invoker}" AGENT_REPO="{staged}" DRY_RUN=0 FORCE=0
        step_stage_repo
        [ -f "{staged}/scripts/install.sh" ] || {{ echo "not staged"; exit 1; }}
        [ "$(stat -c %U "{staged}")" = "{me}" ] || {{ echo "bad owner"; exit 1; }}
        out=$(step_stage_repo 2>&1)
        echo "$out" | grep -q "already staged" || {{ echo "no skip when current: $out"; exit 1; }}
        # invoker edits an unrelated file and commits -> must re-stage
        # (live staging is quiet; assert the skip note is absent and the
        # staged tree converges)
        echo "v2" > "{invoker}/other.txt"
        git -C "{invoker}" commit -qam v2
        out=$(step_stage_repo 2>&1)
        echo "$out" | grep -q "already staged" && {{ echo "wrongly skipped on move"; exit 1; }}
        [ "$(cat "{staged}/other.txt")" = "v2" ] || {{ echo "stale staged copy"; exit 1; }}
        # dirty invoker tree -> must re-stage
        echo "dirty" >> "{invoker}/other.txt"
        out=$(step_stage_repo 2>&1)
        echo "$out" | grep -q "already staged" && {{ echo "wrongly skipped on dirty"; exit 1; }}
        grep -q "dirty" "{staged}/other.txt" || {{ echo "dirty edit not staged"; exit 1; }}
        # FORCE re-stages even when current
        git -C "{invoker}" checkout -q -- "{invoker}/other.txt"
        out=$(FORCE=1 step_stage_repo 2>&1)
        echo "$out" | grep -q "already staged" && {{ echo "force did not restage"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


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


# ---------------------------------------------------------------------------
# #1527 — version-pinned install
# ---------------------------------------------------------------------------


def test_version_flag_parsing_and_grammar():
    code = source_preamble()
    code += textwrap.dedent(
        """\
        parse_args --version v1.2.3
        [ "$INSTALL_VERSION" = v1.2.3 ] || { echo "space form failed: $INSTALL_VERSION"; exit 1; }
        parse_args --version=v2.0.0-rc.1
        [ "$INSTALL_VERSION" = v2.0.0-rc.1 ] || { echo "equals form failed: $INSTALL_VERSION"; exit 1; }
        for bad in main v1.2 v1 v1.2.3.4.5 --upload-pack=x 'v1.2.3;rm -rf /' 'v 1.2.3' 'v1.2.3
        x'; do
          if ( parse_args --version "$bad" ) 2>/dev/null; then echo "accepted bad ref: $bad"; exit 1; fi
        done
        # env-provided value is validated too (the re-exec passes --version by env)
        INSTALL_VERSION=main
        if ( parse_args ) 2>/dev/null; then echo "env bad ref accepted"; exit 1; fi
        # empty is the default (latest tag), not an error
        INSTALL_VERSION=
        parse_args || { echo "empty default rejected"; exit 1; }
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_version_flag_missing_arg_dies():
    code = source_preamble()
    code += '( parse_args --version ) 2>/dev/null && { echo "missing arg accepted"; exit 1; }; echo OK\n'
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_resolve_install_version_picks_latest_tag():
    code = source_preamble()
    code += textwrap.dedent(
        """\
        git() {
          case "$*" in
            # zzz sorts ABOVE v0.10.0 under sort -V and must not win;
            # notaversion sorts below and was never the catch case.
            *"ls-remote --tags"*) printf 'aaa\\trefs/tags/v0.8.0\\naaa2\\trefs/tags/v0.8.0^{}\\nbbb\\trefs/tags/v0.10.0\\nbbb2\\trefs/tags/v0.10.0^{}\\nccc\\trefs/tags/v0.9.0\\nddd\\trefs/tags/notaversion\\neee\\trefs/tags/zzz\\nfff\\trefs/tags/ghost/20261002-2129\\n';;
          esac
        }
        INSTALL_VERSION=
        v=$(resolve_install_version)
        [ "$v" = v0.10.0 ] || { echo "wrong latest: $v"; exit 1; }
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_resolve_install_version_explicit_tag_checked_and_missing_dies():
    code = source_preamble()
    code += textwrap.dedent(
        """\
        git() {
          case "$*" in
            *"ls-remote --tags"*"refs/tags/v1.2.3") printf 'aaa\\trefs/tags/v1.2.3\\n';;
          esac
        }
        INSTALL_VERSION=v1.2.3
        v=$(resolve_install_version)
        [ "$v" = v1.2.3 ] || { echo "explicit tag not echoed: $v"; exit 1; }
        if ( INSTALL_VERSION=v9.9.9 resolve_install_version ) 2>/dev/null; then echo "missing tag accepted"; exit 1; fi
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def _repo_harness_git(clone_args_file, clone_version_plant):
    # git stub for step_repo tests: ls-remote advertises v0.8.0; clone
    # fakes the checkout by planting the given VERSION content and logs its
    # argv to a file (the step runs in a command-substitution subshell, so
    # plain variable assignments would be lost).
    return textwrap.dedent(
        f"""\
        git() {{
          case "$*" in
            *"ls-remote --tags"*) printf 'aaa\\trefs/tags/v0.8.0\\n';;
            *"remote get-url"*) return 0;;
            *"rev-parse"*) echo deadbeef;;
            *"clone"*) echo "$*" >> "{clone_args_file}"; mkdir -p "$AGENT_REPO"; printf '%s\\n' "{clone_version_plant}" > "$AGENT_REPO/VERSION";;
          esac
          return 0
        }}
        """
    )


def test_step_repo_fresh_clone_pins_branch_and_verifies_version(tmp_path):
    repo = tmp_path / "agent-repo"
    clone_args = tmp_path / "clone-args"
    clone_args.write_text("")
    code = source_preamble()
    code += _repo_harness_git(str(clone_args), "0.8.0")
    code += textwrap.dedent(
        f"""\
        AGENT_REPO="{repo}"; REPO_URL="https://example.invalid/spark-vm.git"
        DRY_RUN=0; INSTALL_VERSION=v0.8.0
        out=$(step_repo 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "failed on matching VERSION: $out"; exit 1; }}
        args=$(cat "{clone_args}")
        case "$args" in *"--branch v0.8.0"*) ;; *) echo "no --branch in: $args"; exit 1;; esac
        case "$args" in *"$REPO_URL $AGENT_REPO"*) ;; *) echo "bad clone dest: $args"; exit 1;; esac
        echo "$out" | grep -q "installing release v0.8.0" || {{ echo "no pin note: $out"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_step_repo_fresh_clone_version_mismatch_dies(tmp_path):
    repo = tmp_path / "agent-repo"
    clone_args = tmp_path / "clone-args"
    clone_args.write_text("")
    code = source_preamble()
    code += _repo_harness_git(str(clone_args), "0.7.0")  # hand-edited tree
    code += textwrap.dedent(
        f"""\
        AGENT_REPO="{repo}"; REPO_URL="https://example.invalid/spark-vm.git"
        DRY_RUN=0; INSTALL_VERSION=v0.8.0
        if ( step_repo ) 2>/dev/null; then echo "mismatched tree accepted"; exit 1; fi
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_step_repo_existing_pin_holds_skips_without_pull(tmp_path):
    repo = tmp_path / "agent-repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "VERSION").write_text("0.8.0\n")
    git_seen = tmp_path / "git-seen"
    git_seen.write_text("")
    code = source_preamble()
    code += textwrap.dedent(
        f"""\
        git() {{
          echo "$*" >> "{git_seen}"
          case "$*" in
            *"ls-remote --tags"*) printf 'aaa\\trefs/tags/v0.8.0\\n';;
            *"remote get-url"*) return 0;;
            *"rev-parse"*) echo deadbeef;;
          esac
          return 0
        }}
        AGENT_REPO="{repo}"; REPO_URL="https://example.invalid/spark-vm.git"
        DRY_RUN=0; INSTALL_VERSION=v0.8.0
        out=$(step_repo 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "failed on held pin: $out"; exit 1; }}
        echo "$out" | grep -q "already at release v0.8.0" || {{ echo "no skip note: $out"; exit 1; }}
        seen=$(cat "{git_seen}")
        case "$seen" in *"pull"*|*"clone"*) echo "mutating git op on pinned run: $seen"; exit 1;; esac
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_step_repo_existing_pin_mismatch_dies_loud(tmp_path):
    # The checkout is at a different commit than the pinned tag: tag-to-tag
    # updates are out of scope (F-PKG-6) — die loud, don't half-upgrade.
    repo = tmp_path / "agent-repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "VERSION").write_text("0.7.0\n")
    code = source_preamble()
    code += textwrap.dedent(
        f"""\
        git() {{
          case "$*" in
            *"ls-remote --tags"*) printf 'aaa\\trefs/tags/v0.8.0\\n';;
            *"remote get-url"*) return 0;;
            *"rev-parse"*) case "$*" in *"HEAD"*) echo deadbeef-old;; *) echo deadbeef-new;; esac;;
          esac
          return 0
        }}
        AGENT_REPO="{repo}"; REPO_URL="https://example.invalid/spark-vm.git"
        DRY_RUN=0; INSTALL_VERSION=v0.8.0
        if ( step_repo ) 2>/dev/null; then echo "diverged checkout accepted"; exit 1; fi
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_dry_run_names_version_pin(tmp_path):
    harness, call_log, git_log, agent_home, agent_repo, sudoers_d = _agent_harness(
        tmp_path, fresh=True
    )
    code = source_preamble() + harness
    code += textwrap.dedent(
        f"""\
        export HOME="{agent_home}" SUDOERS_DIR="{sudoers_d}" AGENT_USER=ntindle DRY_RUN=1
        export REPO_DIR="/nonexistent/invoker-checkout" AGENT_REPO="{agent_home}/spark-vm"
        out=$(run_agent 2>&1); rc=$?
        [ $rc = 0 ] || {{ echo "dry-run failed: $out"; exit 1; }}
        echo "$out" | grep -q "installing release v9.9.9" || {{ echo "no pin note: $out"; exit 1; }}
        echo "$out" | grep -q "would clone .*--branch v9.9.9" || {{ echo "no branch in plan: $out"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_step_repo_fresh_clone_shadowed_branch_refused(tmp_path):
    # A same-named branch shadows the tag at clone time: git clone
    # --branch <tag> checks out the branch, not the tag. The VERSION check
    # alone would pass if the branch tree carries the same VERSION string,
    # so the post-clone commit pin must refuse. (Engineering round-1 B2.)
    repo = tmp_path / "agent-repo"
    code = source_preamble()
    code += textwrap.dedent(
        f"""\
        git() {{
          case "$*" in
            *"ls-remote --tags"*) printf 'aaa\\trefs/tags/v0.8.0\\n';;
            *"remote get-url"*) return 0;;
            *"rev-parse"*HEAD*) echo deadbeef-branch;;   # clone landed on the shadowing branch tip
            *"rev-parse"*) echo deadbeef-tag;;             # the tag's own commit
            *"clone"*) mkdir -p "$AGENT_REPO"; printf '0.8.0\\n' > "$AGENT_REPO/VERSION";;
          esac
          return 0
        }}
        AGENT_REPO="{repo}"; REPO_URL="https://example.invalid/spark-vm.git"
        DRY_RUN=0; INSTALL_VERSION=v0.8.0
        if ( step_repo ) 2>/dev/null; then echo "shadowed ref accepted"; exit 1; fi
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def _provenance_harness(tmp_path):
    """Fake agent repo + fake HOME for provenance tests.

    Returns (code_prefix, agent_home, agent_repo, manifest) where
    code_prefix exports the env and stubs git to a fixed commit SHA.
    """
    agent_home = tmp_path / "agent-home"
    agent_repo = tmp_path / "agent-repo"
    (agent_repo / "muse-job" / "bin").mkdir(parents=True)
    (agent_repo / "cred-ui").mkdir(parents=True)
    (agent_repo / "VERSION").write_text("0.9.1\n")
    # The manifest nests under a not-yet-existing dir: since #1551 the
    # writer only tightens a parent it created (or the default state dir),
    # so a pre-existing override parent is a refuse-loud case — the
    # harness must mirror a supported layout.
    manifest = tmp_path / "state" / "provenance-manifest.json"
    prefix = textwrap.dedent(
        f"""\
        export HOME="{agent_home}" AGENT_REPO="{agent_repo}" DRY_RUN=0
        export PROVENANCE_MANIFEST="{manifest}"
        git() {{ echo "0123456789abcdef0123456789abcdef01234567"; }}
        """
    )
    return prefix, agent_home, agent_repo, manifest


def test_stamp_provenance_writes_one_json_line(tmp_path):
    prefix, agent_home, agent_repo, manifest = _provenance_harness(tmp_path)
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"#!/bin/sh\necho muse-job\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        stamp_provenance "{placed}" "muse-job/bin/muse-job"
        [ -f "{manifest}" ] || {{ echo "no manifest"; exit 1; }}
        echo "---MANIFEST---"; cat "{manifest}"
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    body = proc.stdout.split("---MANIFEST---")[1]
    lines = [line for line in body.strip().splitlines() if line.startswith("{")]
    assert len(lines) == 1, lines
    import json, hashlib

    record = json.loads(lines[0])
    assert record["installed"] == str(placed)
    assert record["source"] == "muse-job/bin/muse-job"
    assert record["sha256"] == hashlib.sha256(placed.read_bytes()).hexdigest()
    assert record["source_commit"] == "0123456789abcdef0123456789abcdef01234567"
    assert record["version"] == "0.9.1"
    assert isinstance(record["stamped_at"], int)


def test_stamp_provenance_restamp_updates_record(tmp_path):
    # The manifest is append-only JSONL; the reader takes the last line per
    # path, so re-stamping must update rather than confuse.
    prefix, agent_home, agent_repo, manifest = _provenance_harness(tmp_path)
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        stamp_provenance "{placed}" "muse-job/bin/muse-job" >/dev/null
        printf 'v2\\n' > "{placed}"
        stamp_provenance "{placed}" "muse-job/bin/muse-job" >/dev/null
        wc -l < "{manifest}"
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("2"), proc.stdout
    import json, hashlib

    records = [
        json.loads(line)
        for line in manifest.read_text().splitlines()
        if line.startswith("{")
    ]
    assert len(records) == 2
    assert records[1]["sha256"] == hashlib.sha256(b"v2\n").hexdigest()
    assert records[0]["sha256"] != records[1]["sha256"]


def test_stamp_provenance_fails_loud_when_commit_unreadable(tmp_path):
    # A stamp the inventory cannot trust is worse than no stamp: fail loud.
    prefix, agent_home, agent_repo, manifest = _provenance_harness(tmp_path)
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        git() {{ return 1; }}
        if ( stamp_provenance "{placed}" "muse-job/bin/muse-job" ) 2>/dev/null; then
          echo "did not die on unreadable commit"; exit 1
        fi
        [ ! -e "{manifest}" ] || {{ echo "manifest written despite failure"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def _provenance_harness_nested(tmp_path):
    """Like _provenance_harness, but the manifest lives under a nested,
    not-yet-existing parent (mirroring the real ~/.local/state/spark-vm
    layout) and the shell umask is pinned to 022 so creation-mode
    assertions are deterministic and the pre-fix code fails them.
    """
    agent_home = tmp_path / "agent-home"
    agent_repo = tmp_path / "agent-repo"
    (agent_repo / "muse-job" / "bin").mkdir(parents=True)
    (agent_repo / "cred-ui").mkdir(parents=True)
    (agent_repo / "VERSION").write_text("0.9.1\n")
    manifest = tmp_path / "state" / "spark-vm" / "provenance-manifest.json"
    prefix = textwrap.dedent(
        f"""\
        export HOME="{agent_home}" AGENT_REPO="{agent_repo}" DRY_RUN=0
        export PROVENANCE_MANIFEST="{manifest}"
        umask 022
        git() {{ echo "0123456789abcdef0123456789abcdef01234567"; }}
        """
    )
    return prefix, agent_home, agent_repo, manifest


def test_stamp_provenance_creates_manifest_0600(tmp_path):
    # #1548: the manifest is the S1 integrity inventory; it must be created
    # owner-only so another local user cannot read the stamped records.
    prefix, agent_home, agent_repo, manifest = _provenance_harness_nested(tmp_path)
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"#!/bin/sh\necho muse-job\n")
    code = source_preamble() + prefix
    code += f'stamp_provenance "{placed}" "muse-job/bin/muse-job" >/dev/null && echo OK'
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")
    mode = stat.S_IMODE(manifest.stat().st_mode)
    assert mode == 0o600, f"manifest mode {oct(mode)}, want 0o600"


def test_stamp_provenance_pins_parent_dir_0700(tmp_path):
    # #1548: the parent dir must not be group/other-writable either — a 0755
    # parent lets another local user *replace* the manifest via rename(2)
    # (directory write permission suffices) and re-stamp a tampered copy.
    prefix, agent_home, agent_repo, manifest = _provenance_harness_nested(tmp_path)
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += f'stamp_provenance "{placed}" "muse-job/bin/muse-job" >/dev/null && echo OK'
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")
    mode = stat.S_IMODE(manifest.parent.stat().st_mode)
    assert mode == 0o700, f"manifest parent mode {oct(mode)}, want 0o700"


def test_stamp_provenance_tightens_preexisting_default_dir(tmp_path):
    # #1551: a pre-existing *default* state dir (0755, left by a pre-#1548
    # installer) still gets tightened on the next stamp — and the new line
    # is appended, not lost. Pre-existing non-default parents are refused
    # (see test_stamp_provenance_refuses_preexisting_nondefault_parent).
    prefix, agent_home, agent_repo, manifest = _provenance_harness_nested(tmp_path)
    default_manifest = (
        agent_home / ".local" / "state" / "spark-vm" / "provenance-manifest.json"
    )
    default_manifest.parent.mkdir(parents=True)
    default_manifest.write_text('{"installed": "legacy", "stamped_at": 0}\n')
    os.chmod(default_manifest, 0o644)
    os.chmod(default_manifest.parent, 0o755)
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        export PROVENANCE_MANIFEST="{default_manifest}"
        stamp_provenance "{placed}" "muse-job/bin/muse-job" >/dev/null && echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")
    mode = stat.S_IMODE(default_manifest.stat().st_mode)
    assert mode == 0o600, f"pre-existing manifest mode {oct(mode)}, want 0o600"
    dmode = stat.S_IMODE(default_manifest.parent.stat().st_mode)
    assert dmode == 0o700, f"default parent mode {oct(dmode)}, want 0o700"
    import json

    lines = [
        line for line in default_manifest.read_text().splitlines()
        if line.startswith("{")
    ]
    assert len(lines) == 2, lines
    assert json.loads(lines[0])["installed"] == "legacy"
    assert json.loads(lines[1])["installed"] == str(placed)


def test_stamp_provenance_refuses_preexisting_nondefault_parent(tmp_path):
    # #1551: PROVENANCE_MANIFEST pointing under a pre-existing non-default
    # dir (the /tmp/x.json case) must die loud instead of chmod'ing that
    # dir — the dir stays untouched and nothing is written.
    prefix, agent_home, agent_repo, manifest = _provenance_harness_nested(tmp_path)
    predir = tmp_path / "preexisting"
    predir.mkdir()
    os.chmod(predir, 0o755)
    exotic = predir / "provenance-manifest.json"
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        export PROVENANCE_MANIFEST="{exotic}"
        if ( stamp_provenance "{placed}" "muse-job/bin/muse-job" ) 2>/dev/null; then
          echo "did not die on pre-existing non-default parent"; exit 1
        fi
        [ ! -e "{exotic}" ] || {{ echo "manifest written despite refusal"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")
    assert stat.S_IMODE(predir.stat().st_mode) == 0o755


def test_stamp_provenance_honors_manifest_file_env_name(tmp_path):
    # #1550: the writer shares the reader's lookup chain
    # (PROVENANCE_MANIFEST_FILE > PROVENANCE_MANIFEST) — setting the
    # historic reader-side name must retarget the writer too.
    prefix, agent_home, agent_repo, _manifest = _provenance_harness(tmp_path)
    file_manifest = tmp_path / "file-env" / "provenance-manifest.json"
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        export PROVENANCE_MANIFEST_FILE="{file_manifest}"
        stamp_provenance "{placed}" "muse-job/bin/muse-job" >/dev/null && echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")
    assert file_manifest.is_file(), "writer did not honor PROVENANCE_MANIFEST_FILE"


def test_stamp_provenance_manifest_file_wins_when_both_set(tmp_path):
    # #1550: both names set to different values converge to
    # PROVENANCE_MANIFEST_FILE on the writer, mirroring the reader —
    # the PROVENANCE_MANIFEST path must stay untouched.
    prefix, agent_home, agent_repo, manifest = _provenance_harness(tmp_path)
    file_manifest = tmp_path / "file-env" / "provenance-manifest.json"
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        export PROVENANCE_MANIFEST_FILE="{file_manifest}"
        stamp_provenance "{placed}" "muse-job/bin/muse-job" >/dev/null && echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")
    assert file_manifest.is_file()
    assert not manifest.exists(), "writer stamped the PROVENANCE_MANIFEST path too"


def test_stamp_provenance_refuses_manifest_owned_by_another_user(tmp_path):
    # #1551 (Arch review B2): a manifest file planted by another local
    # user must refuse loud — silently appending would convert the
    # first-stamp refusal into a quiet downgrade of the parent pin.
    # (Vacuity: without the ownership check the stamp appends into the
    # planted file.) Needs root to chown the plant.
    if os.geteuid() != 0:
        pytest.skip("needs root to chown the planted manifest")
    prefix, agent_home, agent_repo, manifest = _provenance_harness_nested(tmp_path)
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"installed": "planted", "stamped_at": 0}\n')
    os.chmod(manifest, 0o644)
    os.chown(manifest, 65534, 65534)  # nobody
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        if ( stamp_provenance "{placed}" "muse-job/bin/muse-job" ) 2>/dev/null; then
          echo "did not die on other-owned manifest"; exit 1
        fi
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")
    # The planted file is untouched: no append, no re-permission.
    assert manifest.read_text() == '{"installed": "planted", "stamped_at": 0}\n'
    assert stat.S_IMODE(manifest.stat().st_mode) == 0o644


def test_stamp_provenance_refuses_relative_manifest_path(tmp_path):
    # A relative PROVENANCE_MANIFEST override would resolve to the process
    # CWD; the fix must die loud instead of chmod'ing the CWD to 0700.
    prefix, agent_home, agent_repo, manifest = _provenance_harness_nested(tmp_path)
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        export PROVENANCE_MANIFEST="relative-manifest.json"
        if ( stamp_provenance "{placed}" "muse-job/bin/muse-job" ) 2>/dev/null; then
          echo "did not die on relative manifest path"; exit 1
        fi
        [ ! -e "relative-manifest.json" ] || {{ echo "manifest created in CWD"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_stamp_provenance_refuses_symlinked_manifest(tmp_path):
    # #1548 (Security round-1 blocker): a pre-planted symlink at the
    # manifest path must fail loud (ELOOP) — never append into the
    # symlink's target, and never re-permission the target.
    prefix, agent_home, agent_repo, manifest = _provenance_harness_nested(tmp_path)
    target = tmp_path / "victim.txt"
    target.write_text("attacker records\n")
    os.chmod(target, 0o644)
    manifest.parent.mkdir(parents=True)
    os.symlink(target, manifest)
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        if ( stamp_provenance "{placed}" "muse-job/bin/muse-job" ) 2>/dev/null; then
          echo "did not die on symlinked manifest"; exit 1
        fi
        [ -L "{manifest}" ] || {{ echo "symlink removed"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")
    assert target.read_text() == "attacker records\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_stamp_provenance_dies_loud_when_parent_blocked(tmp_path):
    # The python stage must fail loud too (not just the pre-python
    # commit/VERSION/hash checks): a regular file blocking the manifest's
    # parent dir must exit non-zero with no manifest written.
    prefix, agent_home, agent_repo, manifest = _provenance_harness_nested(tmp_path)
    blocker = manifest.parent.parent / "spark-vm"
    blocker.parent.mkdir(parents=True)
    blocker.write_text("not a dir\n")
    placed = tmp_path / "placed-bin"
    placed.write_bytes(b"v1\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        if ( stamp_provenance "{placed}" "muse-job/bin/muse-job" ) 2>/dev/null; then
          echo "did not die on blocked parent dir"; exit 1
        fi
        [ ! -e "{manifest}" ] || {{ echo "manifest written despite failure"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_step_muse_job_stamps_provenance_on_skip_path(tmp_path):
    # Idempotent re-run: the copy already matches (skip), but the manifest
    # must still be stamped — this is how pre-#1528 installs get backfilled.
    prefix, agent_home, agent_repo, manifest = _provenance_harness(tmp_path)
    src = agent_repo / "muse-job" / "bin" / "muse-job"
    src.write_bytes(b"#!/bin/sh\necho muse-job\n")
    (agent_home / "bin").mkdir(parents=True)
    (agent_home / "bin" / "muse-job").write_bytes(src.read_bytes())
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        step_muse_job
        [ -f "{manifest}" ] || {{ echo "no manifest on skip path"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "skip: ~/bin/muse-job already matches the repo copy" in proc.stdout
    assert proc.stdout.strip().endswith("OK")
    import json

    record = json.loads(manifest.read_text().splitlines()[0])
    assert record["installed"] == str(agent_home / "bin" / "muse-job")
    assert record["source"] == "muse-job/bin/muse-job"


def test_step_muse_job_stamps_provenance_after_copy(tmp_path):
    prefix, agent_home, agent_repo, manifest = _provenance_harness(tmp_path)
    src = agent_repo / "muse-job" / "bin" / "muse-job"
    src.write_bytes(b"#!/bin/sh\necho muse-job\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        step_muse_job
        cmp -s "{src}" "{agent_home}/bin/muse-job" || {{ echo "not copied"; exit 1; }}
        [ -f "{manifest}" ] || {{ echo "no manifest after copy"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_step_muse_job_dry_run_stamps_nothing(tmp_path):
    prefix, agent_home, agent_repo, manifest = _provenance_harness(tmp_path)
    src = agent_repo / "muse-job" / "bin" / "muse-job"
    src.write_bytes(b"#!/bin/sh\necho muse-job\n")
    code = source_preamble() + prefix.replace("DRY_RUN=0", "DRY_RUN=1")
    code += textwrap.dedent(
        f"""\
        step_muse_job
        [ ! -e "{manifest}" ] || {{ echo "manifest written on dry run"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "would stamp provenance for" in proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_step_cred_ui_dry_run_stamps_nothing(tmp_path):
    # Parity with the muse-job dry-run test: the cred-ui step must stamp
    # through exec_if_live only, so --dry-run writes no manifest.
    prefix, agent_home, agent_repo, manifest = _provenance_harness(tmp_path)
    (agent_repo / "cred-ui" / "cred-ui.service").write_text("[Unit]\n")
    code = source_preamble() + prefix.replace("DRY_RUN=0", "DRY_RUN=1")
    code += textwrap.dedent(
        f"""\
        systemctl() {{ echo "STUBBED systemctl $*"; return 0; }}
        step_cred_ui
        [ ! -e "{manifest}" ] || {{ echo "manifest written on dry run"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "would stamp provenance for the cred-ui unit" in proc.stdout
    assert proc.stdout.strip().endswith("OK")


def test_step_cred_ui_stamps_provenance_after_install(tmp_path):
    prefix, agent_home, agent_repo, manifest = _provenance_harness(tmp_path)
    (agent_repo / "cred-ui" / "cred-ui.service").write_text("[Unit]\n")
    code = source_preamble() + prefix
    code += textwrap.dedent(
        f"""\
        systemctl() {{ return 0; }}
        step_cred_ui
        unit="{agent_home}/.config/systemd/user/cred-ui.service"
        [ -f "$unit" ] || {{ echo "unit not installed"; exit 1; }}
        [ -f "{manifest}" ] || {{ echo "no manifest after cred-ui install"; exit 1; }}
        echo OK
        """
    )
    proc = run_bash(code)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip().endswith("OK")
    import json

    record = json.loads(manifest.read_text().splitlines()[0])
    assert record["installed"] == str(
        agent_home / ".config" / "systemd" / "user" / "cred-ui.service")
    assert record["source"] == "cred-ui/cred-ui.service"
