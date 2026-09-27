"""Tests for deploy/toolset-update.sh (#532, v0 slice).

Run from the repo root:  python3 -m pytest deploy/test_toolset_update.py -q

Hermetic: every test overrides TOOLSET_STATE_DIR, APT_CONF_DIR, SYSTEMD_DIR,
OPTOUT_FILE and PATH (stub bin dir), with SKIP_SYSTEMCTL=1 / SKIP_SUDO=1
unless the test's point is privilege behavior. The script's own package
install path uses a stubbed apt-get; nothing here touches the real apt,
systemd, or /etc.
"""

import json
import os
import shutil
import stat
import subprocess

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO, "deploy", "toolset-update.sh")
SRC_PREFIX = "export TOOLSET_UPDATE_NO_MAIN=1; source ./deploy/toolset-update.sh; "

GOOD_CONF = (
    'APT::Periodic::Update-Package-Lists "1";\n'
    'APT::Periodic::Unattended-Upgrade "1";\n'
)


_stub_counter = [0]


def make_realtools(tmp_path):
    """Symlink dir of the real system tools the script needs (grep, flock,
    ...). Lets package-absent tests build a PATH that provably lacks
    unattended-upgrades regardless of what is installed on the test box."""
    _stub_counter[0] += 1
    d = tmp_path / f"realtools-{_stub_counter[0]}"
    d.mkdir(parents=True, exist_ok=True)
    for t in ("bash", "sh", "grep", "mktemp", "install", "rm", "flock", "date", "mkdir",
              "wc", "tail", "mv", "chmod", "touch", "cat", "head", "cut",
              "tr", "ps", "dirname", "basename"):
        p = shutil.which(t)
        if p:
            (d / t).symlink_to(p)
    return str(d)


def make_stub_bin(tmp_path, files):
    """Create a stub bin dir; files maps name -> script body (exit code via body)."""
    _stub_counter[0] += 1
    bindir = tmp_path / f"stubbin-{_stub_counter[0]}"
    bindir.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        p = bindir / name
        p.write_text("#!/bin/sh\n" + body + "\n")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(bindir)


def run_bash(code, env_extra=None, cwd=REPO):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        ["bash", "-c", code], cwd=cwd, env=env,
        capture_output=True, text=True, timeout=60,
    )


def source_and(code, env_extra=None):
    return run_bash(SRC_PREFIX + code, env_extra=env_extra)


@pytest.fixture()
def env(tmp_path):
    """Hermetic env: all state dirs under tmp; stub bin with quiet tools."""
    statedir = tmp_path / "state"
    aptdir = tmp_path / "aptconf"
    sysdir = tmp_path / "systemd"
    aptdir.mkdir()
    optout = tmp_path / "optout"
    bindir = make_stub_bin(tmp_path, {
        # unattended-upgrades "installed" via PATH presence
        "unattended-upgrades": "exit 0",
        # dpkg: package not installed (vacuous), but real dpkg -l parsing
        # paths must still work when the stub is shadowed below
        "dpkg": "exit 1",
        # tmux: no sessions (idle) by default
        "tmux": "exit 1",
        # sudo stub: fails loudly when invoked (no passwordless sudo in tests)
        "sudo": "echo STUB-SUDO-CALLED >&2; exit 1",
        "apt-get": "echo STUB-APT-GET-CALLED >&2; exit 1",
    })
    e = {
        "TOOLSET_STATE_DIR": str(statedir),
        "APT_CONF_DIR": str(aptdir),
        "SYSTEMD_DIR": str(sysdir),
        "OPTOUT_FILE": str(optout),
        "SKIP_SYSTEMCTL": "1",
        "SKIP_SUDO": "1",
        "TMUX_BIN": os.path.join(bindir, "tmux"),
        "PATH": bindir + os.pathsep + os.environ["PATH"],
    }
    return {"env": e, "tmp": tmp_path, "apt": aptdir, "state": statedir,
            "sys": sysdir, "optout": optout}


def audit_lines(env):
    p = env["state"] / "audit.log"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


# --- os-security state -------------------------------------------------------

def test_state_ok_when_config_correct(env):
    (env["apt"] / "20auto-upgrades").write_text(GOOD_CONF)
    r = source_and('_os_security_state', env["env"])
    assert r.stdout.strip() == "ok"


def test_state_repair_needed_when_conf_missing(env):
    r = source_and('_os_security_state', env["env"])
    assert r.stdout.strip() == "repair-needed"


def test_state_repair_needed_when_values_wrong(env):
    (env["apt"] / "20auto-upgrades").write_text(
        'APT::Periodic::Update-Package-Lists "0";\n'
        'APT::Periodic::Unattended-Upgrade "1";\n'
    )
    r = source_and('_os_security_state', env["env"])
    assert r.stdout.strip() == "repair-needed"


def test_state_repair_needed_when_package_absent(env):
    # Hermetic PATH: stub dpkg/tmux + real tools, provably no
    # unattended-upgrades regardless of the test box.
    e = dict(env["env"])
    nobin = make_stub_bin(env["tmp"], {"dpkg": "exit 1", "tmux": "exit 1"})
    e["PATH"] = nobin + os.pathsep + make_realtools(env["tmp"])
    (env["apt"] / "20auto-upgrades").write_text(GOOD_CONF)
    r = source_and('_os_security_state', e)
    assert r.stdout.strip() == "repair-needed"


# --- update ------------------------------------------------------------------

def test_update_repairs_broken_config(env):
    r = run_bash("./deploy/toolset-update.sh update", env_extra=env["env"])
    assert r.returncode == 0, r.stderr
    assert (env["apt"] / "20auto-upgrades").read_text() == GOOD_CONF
    lines = audit_lines(env)
    assert lines and lines[-1]["event"] == "toolset-update"
    assert lines[-1]["result"] == "ok"


def test_update_is_idempotent(env):
    (env["apt"] / "20auto-upgrades").write_text(GOOD_CONF)
    before = (env["apt"] / "20auto-upgrades").read_text()
    r = run_bash("./deploy/toolset-update.sh update", env_extra=env["env"])
    assert r.returncode == 0, r.stderr
    assert (env["apt"] / "20auto-upgrades").read_text() == before


def test_dry_run_changes_nothing(env):
    r = run_bash("./deploy/toolset-update.sh update --dry-run", env_extra=env["env"])
    assert r.returncode == 0, r.stderr
    assert not (env["apt"] / "20auto-upgrades").exists()
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "dry-run"


def test_update_installs_missing_package(env):
    # apt-get stub records the install call; package absent from PATH/dpkg.
    aptlog = env["tmp"] / "apt-calls.log"
    bindir = make_stub_bin(env["tmp"] / "aptbin", {
        # Hermetic PATH: no unattended-upgrades anywhere (realtools has no
        # symlink for it), and the dpkg stub reports not-installed, so the
        # install branch must fire and call the apt-get stub.
        "dpkg": "exit 1",
        "tmux": "exit 1",
        "sudo": "echo STUB-SUDO-CALLED >&2; exit 1",
        "apt-get": f"echo \"$@\" >> {aptlog}; exit 0",
    })
    e = dict(env["env"])
    e["PATH"] = bindir + os.pathsep + make_realtools(env["tmp"])
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert "install -y unattended-upgrades" in aptlog.read_text()
    assert (env["apt"] / "20auto-upgrades").read_text() == GOOD_CONF


def test_idle_gate_defers_when_jobs_active(env):
    bindir = make_stub_bin(env["tmp"] / "busybin", {
        "unattended-upgrades": "exit 0",
        "dpkg": "exit 1",
        "tmux": 'echo "mjob-builder-1"; exit 0',
        "sudo": "exit 1",
        "apt-get": "exit 1",
    })
    e = dict(env["env"])
    e["PATH"] = bindir + os.pathsep + os.environ["PATH"]
    e["TMUX_BIN"] = os.path.join(bindir, "tmux")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr  # deferral is quiet, not a failure
    assert not (env["apt"] / "20auto-upgrades").exists()  # nothing repaired
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "deferred"
    assert lines[-1]["reason"] == "jobs-active"


def test_force_bypasses_idle_gate(env):
    bindir = make_stub_bin(env["tmp"] / "busybin2", {
        "unattended-upgrades": "exit 0",
        "dpkg": "exit 1",
        "tmux": 'echo "mjob-builder-1"; exit 0',
        "sudo": "exit 1",
        "apt-get": "exit 1",
    })
    e = dict(env["env"])
    e["PATH"] = bindir + os.pathsep + os.environ["PATH"]
    e["TMUX_BIN"] = os.path.join(bindir, "tmux")
    r = run_bash("./deploy/toolset-update.sh update --force", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert (env["apt"] / "20auto-upgrades").read_text() == GOOD_CONF


def test_optout_is_noop(env):
    env["optout"].write_text("")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=env["env"])
    assert r.returncode == 0, r.stderr
    assert not (env["apt"] / "20auto-upgrades").exists()
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "opted-out"


def test_repair_fails_loud_without_privilege(env):
    # SKIP_SUDO=0, non-root (stubbed id), sudo stub fails: repair must fail,
    # not silently skip. (This box runs as root, so non-root is simulated.)
    e = dict(env["env"])
    e["SKIP_SUDO"] = "0"
    noroot = make_stub_bin(env["tmp"] / "noroot", {
        "id": 'if [ "$1" = "-u" ]; then echo 1000; else /usr/bin/id "$@"; fi',
    })
    e["PATH"] = noroot + os.pathsep + e["PATH"]
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0
    assert not (env["apt"] / "20auto-upgrades").exists()
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"


# --- status --------------------------------------------------------------------

def test_status_is_machine_readable_tsv(env):
    (env["apt"] / "20auto-upgrades").write_text(GOOD_CONF)
    r = run_bash("./deploy/toolset-update.sh status", env_extra=env["env"])
    assert r.returncode == 0, r.stderr
    rows = [line.split("\t") for line in r.stdout.splitlines() if line.strip()]
    assert all(len(cols) == 3 for cols in rows), r.stdout
    by_name = {cols[0]: cols[1] for cols in rows}
    assert by_name["os-security"] == "ok"
    for probe in ("docker", "node", "npm", "gh", "playwright", "cua-driver"):
        assert probe in by_name, r.stdout


# --- install / uninstall ---------------------------------------------------------

def test_install_stages_script_and_units(env):
    r = run_bash("./deploy/toolset-update.sh install", env_extra=env["env"])
    assert r.returncode == 0, r.stderr
    installed = env["state"] / "bin" / "toolset-update.sh"
    assert installed.exists()
    assert installed.stat().st_mode & 0o111  # executable
    assert (env["sys"] / "sparkvm-toolset-update.service").exists()
    assert (env["sys"] / "sparkvm-toolset-update.timer").exists()
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "installed"


def test_uninstall_removes_units(env):
    run_bash("./deploy/toolset-update.sh install", env_extra=env["env"])
    r = run_bash("./deploy/toolset-update.sh uninstall", env_extra=env["env"])
    assert r.returncode == 0, r.stderr
    assert not (env["sys"] / "sparkvm-toolset-update.service").exists()
    assert not (env["sys"] / "sparkvm-toolset-update.timer").exists()


def test_optout_optin_roundtrip(env):
    e = dict(env["env"])
    assert run_bash("./deploy/toolset-update.sh optout", env_extra=e).returncode == 0
    assert env["optout"].exists()
    assert run_bash("./deploy/toolset-update.sh optin", env_extra=e).returncode == 0
    assert not env["optout"].exists()


# --- safety pins ---------------------------------------------------------------

def test_script_never_fetches_code():
    # The v0 trust claim: no network fetch, no package manager of its own.
    # apt-get appears exactly once: the unattended-upgrades bootstrap.
    # A future slice adding a second package-manager call must update this pin.
    # (Matches command invocations only — the "apt-get install failed" log
    # string is not a second call site.)
    import re
    text = open(SCRIPT).read()
    for banned in ("curl ", "wget ", "git clone", "pip install", "npm install",
                   "http://", "https://"):
        assert banned not in text, f"v0 must not contain: {banned}"
    invocations = [l for l in text.splitlines()
                   if re.search(r"^\s*(_sudo\s+)?apt-get\b", l)]
    assert len(invocations) == 1, invocations
    assert "install -y unattended-upgrades" in invocations[0]


def test_umask_is_restrictive():
    text = open(SCRIPT).read()
    assert "umask 077" in text


def test_audit_lines_are_json(env):
    run_bash("./deploy/toolset-update.sh update", env_extra=env["env"])
    lines = audit_lines(env)
    assert lines
    for entry in lines:
        assert "ts" in entry and "event" in entry


# --- reviewer-driven hardening (round 1) -------------------------------------

def test_update_fails_loud_when_apt_get_fails(env):
    # Package absent + apt-get stub exits 1: the install branch must fail
    # loud (audit failed), not silently skip.
    bindir = make_stub_bin(env["tmp"], {
        "dpkg": "exit 1",
        "tmux": "exit 1",
        "apt-get": "exit 1",
    })
    e = dict(env["env"])
    e["PATH"] = bindir + os.pathsep + make_realtools(env["tmp"])
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0
    assert not (env["apt"] / "20auto-upgrades").exists()
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"


def test_update_fails_loud_when_flock_missing(env):
    # No flock on PATH: must fail loud with an honest reason, never degrade
    # into a silent perpetual no-op that keeps the timer green.
    bindir = make_stub_bin(env["tmp"], {"dpkg": "exit 1", "tmux": "exit 1"})
    tools = env["tmp"] / "flocklesstools"
    tools.mkdir(exist_ok=True)
    for t in ("bash", "mkdir", "date", "wc", "tail", "mv", "dirname"):
        p = shutil.which(t)
        if p:
            (tools / t).symlink_to(p)
    e = dict(env["env"])
    e["PATH"] = f"{bindir}{os.pathsep}{tools}"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert lines[-1].get("reason") == "flock-missing"


def test_unknown_command_exits_2(env):
    r = run_bash("./deploy/toolset-update.sh frobnicate", env_extra=env["env"])
    assert r.returncode == 2


def test_now_flag_is_informational(env):
    # --now changes nothing in v0 except a log line (the timer owns the
    # schedule); it must still succeed and repair normally.
    e = dict(env["env"])
    r = run_bash("./deploy/toolset-update.sh update --now", env_extra=e)
    assert r.returncode == 0
    logtext = (env["state"] / "toolset-update.log").read_text()
    assert "--now: informational only in v0" in logtext
    assert (env["apt"] / "20auto-upgrades").read_text() == GOOD_CONF


def test_install_enables_timer_via_systemctl(env):
    syscalls = env["tmp"] / "systemctl-calls.log"
    bindir = make_stub_bin(env["tmp"] / "sysctl", {
        "systemctl": f"echo \"$@\" >> {syscalls}; exit 0",
    })
    e = dict(env["env"])
    e["SKIP_SYSTEMCTL"] = "0"
    e["PATH"] = bindir + os.pathsep + os.environ["PATH"]
    r = run_bash("./deploy/toolset-update.sh install", env_extra=e)
    assert r.returncode == 0, r.stderr
    calls = syscalls.read_text()
    assert "daemon-reload" in calls
    assert "enable sparkvm-toolset-update.timer" in calls


def test_uninstall_disables_timer_via_systemctl(env):
    syscalls = env["tmp"] / "systemctl-calls.log"
    bindir = make_stub_bin(env["tmp"] / "sysctl2", {
        "systemctl": f"echo \"$@\" >> {syscalls}; exit 0",
    })
    e = dict(env["env"])
    e["SKIP_SYSTEMCTL"] = "0"
    e["PATH"] = bindir + os.pathsep + os.environ["PATH"]
    r = run_bash("./deploy/toolset-update.sh install", env_extra=e)
    assert r.returncode == 0, r.stderr
    r = run_bash("./deploy/toolset-update.sh uninstall", env_extra=e)
    assert r.returncode == 0, r.stderr
    calls = syscalls.read_text()
    assert "disable --now sparkvm-toolset-update.timer" in calls
    assert "daemon-reload" in calls


def test_unit_files_content_fidelity():
    # The timer must drive the INSTALLED copy, not the checkout; schedule
    # and targets must match docs/TOOLSET_UPDATE.md.
    svc = open(os.path.join(REPO, "deploy", "sparkvm-toolset-update.service")).read()
    tmr = open(os.path.join(REPO, "deploy", "sparkvm-toolset-update.timer")).read()
    assert "ExecStart=/home/ntindle/.sparkvm-toolset/bin/toolset-update.sh update" in svc
    assert "OnCalendar=Sun *-*-* 03:00:00" in tmr
    assert "RandomizedDelaySec=30min" in tmr
    assert "Persistent=false" in tmr
    assert "WantedBy=timers.target" in tmr
    assert "WantedBy=multi-user.target" in svc


def test_optout_env_var_is_noop(env):
    e = dict(env["env"])
    e["TOOLSET_UPDATE_OPTOUT"] = "1"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0
    assert not (env["apt"] / "20auto-upgrades").exists()
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "opted-out"
