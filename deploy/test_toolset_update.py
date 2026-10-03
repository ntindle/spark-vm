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
import pwd
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
              "tr", "ps", "dirname", "basename", "id"):
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
    me = pwd.getpwuid(os.getuid()).pw_name
    # Fake agent-user home: the idle gate resolves homes via getent, so a
    # getent stub answers the invoking user with this dir. Nothing here
    # reads the real $HOME — the registry probe stays hermetic even on a
    # box whose real home holds live muse-job records.
    fakehome = tmp_path / "fakehome"
    fakehome.mkdir(parents=True, exist_ok=True)
    getent_body = (
        f'if [ "$1" = "passwd" ] && [ "$2" = "{me}" ]; then '
        f'echo "{me}:x:{os.getuid()}:{os.getgid()}:{me}:{fakehome}:/bin/sh"; '
        f'exit 0; fi; exit 2'
    )
    bindir = make_stub_bin(tmp_path, {
        # unattended-upgrades "installed" via PATH presence
        "unattended-upgrades": "exit 0",
        # dpkg: package not installed (vacuous), but real dpkg -l parsing
        # paths must still work when the stub is shadowed below
        "dpkg": "exit 1",
        # tmux: no sessions (idle) by default
        "tmux": "exit 1",
        # getent: the invoking user resolves to the fake home above
        "getent": getent_body,
        # sudo stub: fails loudly when invoked (no passwordless sudo in tests)
        "sudo": "echo STUB-SUDO-CALLED >&2; exit 1",
        "apt-get": "echo STUB-APT-GET-CALLED >&2; exit 1",
        # cua-driver at the pinned version: the cua-driver layer no-ops
        # (layer-specific tests override the pin/PATH as needed)
        "cua-driver": 'echo "cua-driver 0.28.2"',
    })
    # pins file the updater reads (installed-copy model: tests stage it in
    # the state dir the same way `install` would)
    statedir.mkdir(parents=True, exist_ok=True)
    (statedir / "self_update_pins.conf").write_text(
        "# test pins\ncua-driver = 0.28.2\nplaywright = 1.62.0\n"
    )
    e = {
        "TOOLSET_STATE_DIR": str(statedir),
        "APT_CONF_DIR": str(aptdir),
        "SYSTEMD_DIR": str(sysdir),
        "OPTOUT_FILE": str(optout),
        "SKIP_SYSTEMCTL": "1",
        "SKIP_SUDO": "1",
        # install -o/-g needs privilege for root; hermetic tests run as
        # whoever invokes pytest (CI runners are non-root), so stage files
        # owned by the current uid/gid. Production default stays root.
        "TOOLSET_INSTALL_OWNER": str(os.getuid()),
        "TOOLSET_INSTALL_GROUP": str(os.getgid()),
        "TMUX_BIN": os.path.join(bindir, "tmux"),
        # The idle gate's agent-user list: pin to the invoking user so the
        # per-uid probes run hermetically (getent stub -> fake home above).
        "TOOLSET_AGENT_USERS": me,
        "PATH": bindir + os.pathsep + os.environ["PATH"],
    }
    # The probe senses the managed binary only (never PATH), so the fixture
    # materializes one at the pin — otherwise every full `update` test would
    # try to download the real release.
    managed = tmp_path / "cua-bin" / "cua-driver"
    managed.parent.mkdir(parents=True, exist_ok=True)
    write_version_stub(managed, "0.28.2")
    e["CUA_DRIVER_BIN"] = str(managed)
    e["CUA_DRIVER_OWNER"] = str(os.getuid())
    e["CUA_DRIVER_GROUP"] = str(os.getgid())
    # The playwright probe senses the managed venv only (never PATH), so the
    # fixture materializes one at the pin — otherwise every full `update`
    # test would refuse fail-closed on the missing pin.
    venv = stage_pw_venv(tmp_path, "1.62.0")
    e["PLAYWRIGHT_VENV"] = str(venv)
    e["PLAYWRIGHT_USER"] = pwd.getpwuid(os.getuid()).pw_name
    return {"env": e, "tmp": tmp_path, "apt": aptdir, "state": statedir,
            "sys": sysdir, "optout": optout, "fakehome": fakehome, "me": me}


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
        # cua-driver at the fixture pin: the new layer must no-op here so
        # this test stays about the os-security install branch.
        "cua-driver": 'echo "cua-driver 0.28.2"',
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
        # cua-driver at the fixture pin: the new layer must no-op here so
        # this test stays about the idle-gate bypass.
        "cua-driver": 'echo "cua-driver 0.28.2"',
    })
    e = dict(env["env"])
    e["PATH"] = bindir + os.pathsep + os.environ["PATH"]
    e["TMUX_BIN"] = os.path.join(bindir, "tmux")
    r = run_bash("./deploy/toolset-update.sh update --force", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert (env["apt"] / "20auto-upgrades").read_text() == GOOD_CONF


def _write_job(home, slug, state):
    d = home / "muse-jobs" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "job.json").write_text(json.dumps({"slug": slug, "state": state}))


def test_idle_gate_skips_agent_user_that_does_not_exist(env):
    # A configured agent user with no passwd entry has no jobs: skipped,
    # logged, never a deferral.
    e = dict(env["env"])
    e["TOOLSET_AGENT_USERS"] = "no-such-user-zzz"
    r = source_and("set +e; _jobs_active; echo rc=$?", env_extra=e)
    assert r.stdout.strip().endswith("rc=1"), r.stdout + r.stderr


def test_idle_gate_rejects_unsafe_agent_user_name(env):
    # Fail-closed: a user name that could smuggle flags into id/getent
    # defers instead of probing.
    e = dict(env["env"])
    e["TOOLSET_AGENT_USERS"] = "-u"
    r = source_and("set +e; _jobs_active; echo rc=$?", env_extra=e)
    assert r.stdout.strip().endswith("rc=0"), r.stdout + r.stderr


def test_registry_busy_detects_active_and_blocked(env):
    home = env["tmp"] / "reghome1"
    _write_job(home, "alpha", "active")
    _write_job(home, "beta", "blocked")
    _write_job(home, "gamma", "closed")
    r = source_and(f"set +e; _registry_busy {home}/muse-jobs; echo rc=$?",
                   env_extra=env["env"])
    assert r.stdout.strip().endswith("rc=0"), r.stdout + r.stderr
    assert "alpha:active" in r.stdout, r.stdout
    assert "beta:blocked" in r.stdout, r.stdout
    assert "gamma" not in r.stdout, r.stdout


def test_registry_busy_idle_when_all_terminal(env):
    home = env["tmp"] / "reghome2"
    _write_job(home, "a", "closed")
    _write_job(home, "b", "killed")
    _write_job(home, "c", "done")
    r = source_and(f"set +e; _registry_busy {home}/muse-jobs; echo rc=$?",
                   env_extra=env["env"])
    assert r.stdout.strip().endswith("rc=1"), r.stdout + r.stderr


def test_registry_busy_fail_closed_on_unknown_state(env):
    # A future/unrecognized job state must defer, never read as idle.
    home = env["tmp"] / "reghome3"
    _write_job(home, "zeta", "migrating")
    r = source_and(f"set +e; _registry_busy {home}/muse-jobs; echo rc=$?",
                   env_extra=env["env"])
    assert r.stdout.strip().endswith("rc=0"), r.stdout + r.stderr
    assert "zeta:migrating" in r.stdout, r.stdout


def test_registry_busy_fail_closed_on_unparseable_record(env):
    # A corrupt job.json must defer, never read as idle.
    home = env["tmp"] / "reghome4"
    d = home / "muse-jobs" / "corrupt"
    d.mkdir(parents=True)
    (d / "job.json").write_text("{not json")
    r = source_and(f"set +e; _registry_busy {home}/muse-jobs; echo rc=$?",
                   env_extra=env["env"])
    assert r.stdout.strip().endswith("rc=0"), r.stdout + r.stderr
    assert "corrupt:unparseable" in r.stdout, r.stdout


def test_as_user_fail_closed_when_switch_impossible(env):
    # Non-root, target is another uid, no runuser/sudo on PATH: _as_user
    # must return 2 (switch impossible -> defer upstream).
    tbin = make_stub_bin(env["tmp"] / "asuserbin", {
        "id": "if [ $# -eq 1 ]; then echo 1000; else echo 1001; fi",
    })
    realtools = make_realtools(env["tmp"])
    e = dict(env["env"])
    # Deliberately no system PATH: runuser/sudo must be unresolvable here.
    e["PATH"] = tbin + os.pathsep + realtools
    r = source_and("set +e; _as_user someuser -- true; echo rc=$?",
                   env_extra=e)
    assert r.stdout.strip().endswith("rc=2"), r.stdout + r.stderr


def test_as_user_remaps_command_exit_2(env):
    # Same-uid shortcut: a command exiting 2 must be reported as 3 so it is
    # never confused with the switch-impossible code.
    tbin = make_stub_bin(env["tmp"] / "asuserbin2", {
        "id": "echo 1000",
    })
    realtools = make_realtools(env["tmp"])
    e = dict(env["env"])
    e["PATH"] = tbin + os.pathsep + realtools
    r = source_and("set +e; _as_user anyuser -- sh -c 'exit 2'; echo rc=$?",
                   env_extra=e)
    assert r.stdout.strip().endswith("rc=3"), r.stdout + r.stderr


def test_log_sanitizes_control_characters(env):
    # Terminal-escape injection: control bytes interpolated into log lines
    # (user names, job slugs, job states) must not reach the journal/run
    # log raw.
    code = ("log \"job $(printf '\\033[2J\\033[31m') done\"; "
            "log \"forged$(printf '\\r')clean\"; "
            "cat \"$TOOLSET_STATE_DIR/toolset-update.log\"")
    r = source_and(code, env_extra=env["env"])
    out = r.stdout
    assert "\x1b" not in out, repr(out)
    assert "\r" not in out, repr(out)
    # ESC is stripped; the inert CSI parameter text remains visible.
    assert "job [2J[31m done" in out, repr(out)
    # CR becomes a space: no line-overwrite forgery in terminal viewers.
    assert "forged clean" in out, repr(out)


def test_registry_busy_fallback_fail_closed_on_unparseable(env):
    # No python3 on PATH: the grep fallback must still fail closed on a
    # corrupt job.json (busy, never idle).
    home = env["tmp"] / "reghome5"
    d = home / "muse-jobs" / "corrupt"
    d.mkdir(parents=True)
    (d / "job.json").write_text("{not json")
    tbin = make_stub_bin(env["tmp"] / "nopybin", {})
    realtools = make_realtools(env["tmp"])
    e = dict(env["env"])
    # Deliberately no system PATH: python3 must be unresolvable here.
    e["PATH"] = tbin + os.pathsep + realtools
    r = source_and(f"set +e; _registry_busy {home}/muse-jobs; echo rc=$?",
                   env_extra=e)
    assert r.stdout.strip().endswith("rc=0"), r.stdout + r.stderr
    assert "corrupt:unparseable" in r.stdout, r.stdout


def test_registry_busy_fallback_busy_on_any_nonterminal(env):
    # No python3 on PATH: a nested "done" must not mask a live top-level
    # state in the grep fallback.
    home = env["tmp"] / "reghome6"
    d = home / "muse-jobs" / "mixed"
    d.mkdir(parents=True)
    (d / "job.json").write_text('{"history": [{"state": "done"}], "state": "active"}')
    tbin = make_stub_bin(env["tmp"] / "nopybin2", {})
    realtools = make_realtools(env["tmp"])
    e = dict(env["env"])
    e["PATH"] = tbin + os.pathsep + realtools
    r = source_and(f"set +e; _registry_busy {home}/muse-jobs; echo rc=$?",
                   env_extra=e)
    assert r.stdout.strip().endswith("rc=0"), r.stdout + r.stderr
    assert "mixed:active" in r.stdout, r.stdout


def test_registry_busy_missing_dir_is_idle(env):
    r = source_and(f"set +e; _registry_busy {env['tmp']}/nope; echo rc=$?",
                   env_extra=env["env"])
    assert r.stdout.strip().endswith("rc=1"), r.stdout + r.stderr


def test_idle_gate_empty_agent_users_is_open_but_loud(env):
    # An explicitly empty agent-user list opens the gate (operator's
    # choice), but it must say so loudly in the run log.
    e = dict(env["env"])
    e["TOOLSET_AGENT_USERS"] = ""
    r = source_and("set +e; _jobs_active >/dev/null; echo rc=$?", env_extra=e)
    assert r.stdout.strip().endswith("rc=1"), r.stdout + r.stderr
    logtext = (env["state"] / "toolset-update.log").read_text()
    assert "gate is open" in logtext, logtext


def test_idle_gate_tmux_missing_degrades_to_registry(env):
    # No tmux binary at all: the tmux half reads idle, the registry half
    # still defers on a live record.
    _write_job(env["fakehome"], "live-two", "blocked")
    e = dict(env["env"])
    e["TMUX_BIN"] = "/nonexistent/tmux"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert not (env["apt"] / "20auto-upgrades").exists()  # nothing repaired
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "deferred"
    assert lines[-1]["reason"] == "jobs-active"


def test_idle_gate_defers_on_registry_record_with_idle_tmux(env):
    # The v2-proof half: tmux shows no sessions, but the muse-job registry
    # holds a live record — the update must still defer. (Against the v0
    # tmux-only gate this test fails: the update proceeds and repairs.)
    _write_job(env["fakehome"], "live-one", "active")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=env["env"])
    assert r.returncode == 0, r.stderr  # deferral is quiet, not a failure
    assert not (env["apt"] / "20auto-upgrades").exists()  # nothing repaired
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "deferred"
    assert lines[-1]["reason"] == "jobs-active"


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
    # Trust-model pin (#532): the script's network surface is the
    # cua-driver layer's pinned release fetch, the apt layer's weekly
    # --only-upgrade, and the playwright layer's pinned pip + browser
    # fetch. apt-get appears exactly three times: the unattended-upgrades
    # bootstrap, the apt layer's `install --only-upgrade` (simulate in
    # dry-run), and the playwright layer's validated-names system-deps
    # install. curl appears exactly twice: the checksums.txt + tarball fetch
    # inside _cua_driver_layer, both against "$base/$tag/..." (base defaults
    # to the single https:// constant CUA_RELEASE_BASE). `pip install`
    # appears exactly once: the playwright layer's exact-pin
    # `"playwright==$pin"` (never a floating upgrade). A future slice
    # adding network or package-manager surface must update this pin and
    # docs/TOOLSET_UPDATE.md. (Matches command invocations only — the
    # "apt-get install failed" log strings are not call sites; the
    # DEBIAN_FRONTEND= prefix on the apt-layer calls is part of the
    # non-interactive contract.)
    import re
    text = open(SCRIPT).read()
    for banned in ("wget ", "git clone", "npm install",
                   "http://"):
        assert banned not in text, f"must not contain: {banned}"
    invocation_re = re.compile(
        r"^\s*(?!#)(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*"
        r"(?:_sudo\s+|sudo\s+|command\s+|env\s+)?"
        r"(?:/usr/bin/|/bin/)?apt-get\b")
    # Bare `apt` (the interactive frontend) must never be used — it would
    # evade the apt-get-only assertions above. `apt-get` is excluded via
    # lookahead; the comment guard keeps prose/docs out of the match.
    bare_apt_re = re.compile(
        r"^\s*(?!#)(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*"
        r"(?:_sudo\s+|sudo\s+|command\s+|env\s+)?"
        r"(?:/usr/bin/|/bin/)?apt(?![-\w])")
    # Join backslash continuations: the apt-layer flags (--only-upgrade,
    # -o Dpkg::Options) live on the invocation's continuation lines.
    logical = re.sub(r"\\\n\s*", " ", text).splitlines()
    for l in logical:
        assert not bare_apt_re.search(l), f"bare `apt` binary must not be used: {l}"
    invocations = [l for l in logical if invocation_re.search(l)]
    assert len(invocations) == 3, invocations
    bootstrap = [l for l in invocations if "install -y unattended-upgrades" in l]
    assert len(bootstrap) == 1, invocations
    apt_layer = [l for l in invocations if "--only-upgrade" in l]
    assert len(apt_layer) == 1, invocations
    line = apt_layer[0]
    assert "--only-upgrade" in line, line
    assert '-o Dpkg::Options::="--force-confdef"' in line, line
    assert '-o Dpkg::Options::="--force-confold"' in line, line
    # One call site serves both modes via $mode (-y real, -s dry-run).
    assert 'apt-get "$mode" install' in line, line
    assert 'mode="-y"' in text and 'mode="-s"' in text, "dry/real modes"
    # The playwright layer's system-deps install: validated names only —
    # never --only-upgrade (these are fresh installs, not upgrades), never
    # a bare `apt upgrade`, same non-interactive flags as the apt layer.
    pw_deps = [l for l in invocations
               if l not in bootstrap and l not in apt_layer]
    assert len(pw_deps) == 1, invocations
    line = pw_deps[0]
    assert "--no-install-recommends" in line, line
    assert "--only-upgrade" not in line, line
    assert '-o Dpkg::Options::="--force-confdef"' in line, line
    assert '-o Dpkg::Options::="--force-confold"' in line, line
    # The playwright layer is the single `pip install` call site: exact pin
    # only (`"playwright==$pin"`), never a floating upgrade. Matched on the
    # `-m pip install` invocation shape so the log strings mentioning
    # "pip install" are not counted as call sites.
    pip_invocations = [l for l in logical
                       if re.search(r"-m\s+pip\s+install\b", l)
                       and not l.lstrip().startswith("#")]
    assert len(pip_invocations) == 1, pip_invocations
    pip_line = pip_invocations[0]
    assert '"playwright==$pin"' in pip_line, pip_line
    assert "--upgrade" not in pip_line, pip_line
    assert "-U" not in pip_line.split(), pip_line
    # Never a bare `apt upgrade` / `apt-get upgrade` (would touch everything).
    for l in logical:
        if invocation_re.search(l):
            assert ("--only-upgrade" in l or "unattended-upgrades" in l
                    or "--no-install-recommends" in l), l
    curls = [l for l in text.splitlines() if "curl -fsSL" in l]
    assert len(curls) == 2, curls
    for line in curls:
        assert "$base/$tag/" in line, line
    # No other curl call sites (the remaining "curl" mentions are the
    # presence check and the missing-curl log string, not invocations).
    other_curl = [l for l in text.splitlines()
                  if re.search(r"\bcurl\b", l) and "curl -fsSL" not in l
                  and "command -v curl" not in l
                  and "curl not found" not in l]
    assert not other_curl, other_curl
    https = [l for l in text.splitlines() if "https://" in l]
    assert len(https) == 1, https
    assert 'CUA_RELEASE_BASE:=' in https[0] and 'github.com/trycua/cua' in https[0]


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
    # and targets must match docs/TOOLSET_UPDATE.md. Security pins: no
    # environment injection surface (systemd gives the service a clean env),
    # no privilege escalation. PrivateTmp must stay OFF: the idle gate
    # observes per-uid tmux sockets under the real /tmp, and a private /tmp
    # would blind the tmux half of the gate under the production timer.
    svc = open(os.path.join(REPO, "deploy", "sparkvm-toolset-update.service")).read()
    tmr = open(os.path.join(REPO, "deploy", "sparkvm-toolset-update.timer")).read()
    assert "ExecStart=/home/ntindle/.sparkvm-toolset/bin/toolset-update.sh update" in svc
    assert "OnCalendar=Sun *-*-* 03:00:00" in tmr
    assert "RandomizedDelaySec=30min" in tmr
    assert "Persistent=false" in tmr
    assert "WantedBy=timers.target" in tmr
    assert "WantedBy=multi-user.target" in svc
    for directive in ("EnvironmentFile=", "PassEnvironment=", "Environment="):
        assert directive not in svc, directive
    assert "NoNewPrivileges=true" in svc
    # No PrivateTmp directive (the word may appear in comments): the gate
    # needs the real /tmp for per-uid tmux sockets.
    assert all(not l.strip().startswith("PrivateTmp")
               for l in svc.splitlines()), \
        "PrivateTmp directive would blind the gate's tmux probe"


def test_optout_env_var_is_noop(env):
    e = dict(env["env"])
    e["TOOLSET_UPDATE_OPTOUT"] = "1"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0
    assert not (env["apt"] / "20auto-upgrades").exists()
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "opted-out"


# --- cua-driver layer (#532) -----------------------------------------------------

import hashlib
import platform


def _release_arch():
    return "linux-x86_64" if platform.machine() == "x86_64" else "linux-arm64"


def make_pinned_release(tmp_path, pin, binary_body, digest=None):
    """Stage a fake cua-driver release tree: <base>/cua-driver-rs-v<pin>/
    with the binary tarball + checksums.txt. Returns the base dir."""
    base = tmp_path / "release"
    tagdir = base / f"cua-driver-rs-v{pin}"
    tagdir.mkdir(parents=True, exist_ok=True)
    staged = tmp_path / "stage"
    staged.mkdir(exist_ok=True)
    (staged / "cua-driver").write_bytes(binary_body)
    asset = f"cua-driver-rs-{pin}-{_release_arch()}-binary.tar.gz"
    subprocess.run(
        ["tar", "-czf", str(tagdir / asset), "-C", str(staged), "cua-driver"],
        check=True)
    want = digest if digest is not None else hashlib.sha256(
        (tagdir / asset).read_bytes()).hexdigest()
    (tagdir / "checksums.txt").write_text(f"{want}  {asset}\n")
    return str(base)


def write_version_stub(path, version):
    """Executable cua-driver stub reporting `version` — the managed-binary
    shape the probe senses in production."""
    path.write_text(f'#!/bin/sh\necho "cua-driver {version}"\n')
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
               | stat.S_IXOTH)


def cua_env(env, tmp_path, pin="0.28.2", cur_version="0.28.2",
            release_base=None):
    """Env for cua-driver layer tests: pins file, PATH with a cua-driver stub
    reporting cur_version, CUA_DRIVER_BIN under tmp (materialized as an
    executable stub reporting cur_version, so the probe senses the managed
    binary — the production shape), and (optionally) a file:// release base
    for hermetic downloads."""
    e = dict(env["env"])
    (env["state"] / "self_update_pins.conf").write_text(
        f"# test pins\ncua-driver = {pin}\nplaywright = 1.62.0\n")
    bindir = make_stub_bin(tmp_path / "cuabin", {
        "cua-driver": f'echo "cua-driver {cur_version}"',
        "tmux": "exit 1",
    })
    e["PATH"] = bindir + os.pathsep + e["PATH"]
    managed = tmp_path / "cua-bin" / "cua-driver"
    managed.parent.mkdir(parents=True, exist_ok=True)
    write_version_stub(managed, cur_version)
    e["CUA_DRIVER_BIN"] = str(managed)
    e["CUA_DRIVER_OWNER"] = str(os.getuid())
    e["CUA_DRIVER_GROUP"] = str(os.getgid())
    if release_base is not None:
        e["CUA_RELEASE_BASE"] = f"file://{release_base}"
    return e


def stage_pw_venv(tmp_path, version, piplog=None, pwlog=None, pip_exit=0):
    """Materialize a managed-Playwright-venv stub under tmp.

    bin/python answers the `-c 'import playwright; ...'` probe with
    `version` (silent for the bare import probe) and logs `-m pip ...`
    invocations to piplog (if given), exiting pip_exit for them;
    bin/playwright logs every invocation to pwlog (if given) and answers
    `install-deps --dry-run` with $PW_DRYRUN_TEXT / $PW_DRYRUN_EXIT
    (default: "all installed", exit 0). Returns the venv dir. Production
    shape: the update plane converges exactly these two binaries, never
    PATH.
    """
    venv = tmp_path / "pw-venv"
    bind = venv / "bin"
    bind.mkdir(parents=True, exist_ok=True)
    py = bind / "python"
    py.write_text(
        "#!/bin/sh\n"
        f'VER="{version}"\n'
        f'PIPLOG="{piplog or ""}"\n'
        # The import probe (`-c 'import playwright'`) must stay silent —
        # cmd_status runs it in an `if` condition, whose stdout flows to the
        # script's own stdout; only the version query prints.
        'if [ "$1" = "-c" ]; then\n'
        '  case "$2" in *__version__*) echo "$VER";; esac\n'
        '  exit 0\n'
        'fi\n'
        'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then\n'
        '  [ -n "$PIPLOG" ] && echo "$@" >> "$PIPLOG"\n'
        f'  exit {pip_exit}\n'
        'fi\n'
        'exit 0\n')
    py.chmod(py.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    cli = bind / "playwright"
    cli.write_text(
        "#!/bin/sh\n"
        f'PWLOG="{pwlog or ""}"\n'
        '[ -n "$PWLOG" ] && echo "$@" >> "$PWLOG"\n'
        'if [ "$1" = "install-deps" ] && [ "$2" = "--dry-run" ]; then\n'
        '  printf "%s" "${PW_DRYRUN_TEXT:-All system dependencies are installed.}"\n'
        '  exit "${PW_DRYRUN_EXIT:-0}"\n'
        'fi\n'
        'exit 0\n')
    cli.chmod(cli.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return venv


def pw_env(env, tmp_path, pin="1.62.0", cur_version="1.62.0"):
    """Env for playwright layer tests: pins file, hermetic managed venv at
    cur_version, PLAYWRIGHT_USER = the invoking user (so the user-switch
    runs directly), pip/browser invocation logs, and a succeeding apt-get
    stub (the deps step's validated-names install; the fixture's apt-get
    stub fails loudly, which is not this layer's story)."""
    e = dict(env["env"])
    (env["state"] / "self_update_pins.conf").write_text(
        f"# test pins\ncua-driver = 0.28.2\nplaywright = {pin}\n")
    piplog = tmp_path / "pip.log"
    pwlog = tmp_path / "playwright.log"
    aptlog = tmp_path / "pw-apt.log"
    bindir = make_stub_bin(tmp_path / "pwaptbin", {
        "apt-get": f'echo "argv: $@" >> "{aptlog}"; exit 0',
    })
    e["PATH"] = bindir + os.pathsep + e["PATH"]
    venv = stage_pw_venv(tmp_path, cur_version, piplog=piplog, pwlog=pwlog)
    e["PLAYWRIGHT_VENV"] = str(venv)
    e["PLAYWRIGHT_USER"] = pwd.getpwuid(os.getuid()).pw_name
    return e, piplog, pwlog, aptlog


def test_read_pin_parses_pins_file(env):
    pins = env["tmp"] / "pins.conf"
    pins.write_text("# comment\n\ncua-driver = 0.28.2\ndocker=26.1\nno-equals-line\n")
    r = source_and(f'PINS_FILE={pins} _read_pin cua-driver', env["env"])
    assert r.stdout == "0.28.2"
    r = source_and(f'PINS_FILE={pins} _read_pin docker', env["env"])
    assert r.stdout == "26.1"
    r = source_and(f'PINS_FILE={pins} _read_pin missing-tool', env["env"])
    assert r.returncode == 0 and r.stdout == ""
    r = source_and('PINS_FILE=/nonexistent-pins _read_pin cua-driver',
                   env["env"])
    assert r.returncode == 0 and r.stdout == ""


def test_pin_ok_rejects_unsafe(env):
    for bad in ("", "../x", "/abs", "-x", ".x", "a b", "a;b", "a/b", "0.28.2\n"):
        r = source_and(f'_pin_ok "{bad}"', env["env"])
        assert r.returncode != 0, bad
    r = source_and('_pin_ok "0.28.2"', env["env"])
    assert r.returncode == 0


def test_cua_driver_current_parsing(env, tmp_path):
    # Every subcase points CUA_DRIVER_BIN at an explicit managed stub: the
    # probe senses the managed binary only, never PATH.
    def managed_case(body):
        e = dict(env["env"])
        stub = tmp_path / f"managed-{abs(hash(body)) % 100000}" / "cua-driver"
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text("#!/bin/sh\n" + body + "\n")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                   | stat.S_IXOTH)
        e["CUA_DRIVER_BIN"] = str(stub)
        return e

    e = managed_case('echo "cua-driver 0.28.2 (abc123)"')
    r = source_and("_cua_driver_current", e)
    assert r.stdout == "0.28.2"
    # No version-like token, or a bare number: version-unknown (fail-closed,
    # never guessed).
    for body in ('echo "no version here"', 'echo "build 12345"'):
        r = source_and("_cua_driver_current", managed_case(body))
        assert r.stdout == "version-unknown", body
    # Absent binary.
    e3 = dict(env["env"])
    e3["CUA_DRIVER_BIN"] = str(tmp_path / "no-such-dir" / "cua-driver")
    r = source_and("_cua_driver_current", e3)
    assert r.stdout == "absent"


def test_cua_driver_noop_when_at_pin(env, tmp_path):
    # curl stub records any call: the layer must not fetch when on-pin.
    curlog = tmp_path / "curl.log"
    bindir = make_stub_bin(tmp_path / "curlbin",
                           {"curl": f"echo \"$@\" >> {curlog}; exit 0"})
    e = cua_env(env, tmp_path)
    e["PATH"] = bindir + os.pathsep + e["PATH"]
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert not curlog.exists(), "no download when already on pin"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "ok"
    assert "cua-driver" in lines[-1]["components"]


def test_cua_driver_installs_pinned_on_drift(env, tmp_path):
    new_body = b"FAKE-CUA-DRIVER-0.28.2"
    base = make_pinned_release(tmp_path, "0.28.2", new_body)
    e = cua_env(env, tmp_path, cur_version="0.27.0", release_base=base)
    target = tmp_path / "cua-bin" / "cua-driver"
    target.parent.mkdir(parents=True, exist_ok=True)
    # Drifted managed binary: executable, reports the old version (the probe
    # must sense it via the managed path, not PATH).
    write_version_stub(target, "0.27.0")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert target.read_bytes() == new_body
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "ok"


def test_cua_driver_absent_installs_pin(env, tmp_path):
    # cua-driver missing from PATH entirely: fresh install of the pin.
    # Hermetic PATH: the fixture's stub dir minus the cua-driver stub, plus
    # the real tools the layer needs (curl/tar/sha256sum/...). The os.environ
    # PATH tail is only a fallback for real tools — this box and CI have no
    # real cua-driver (verified), so "absent" is honest.
    new_body = b"FAKE-CUA-DRIVER-FRESH"
    base = make_pinned_release(tmp_path, "0.28.2", new_body)
    e = dict(env["env"])
    (env["state"] / "self_update_pins.conf").write_text(
        "cua-driver = 0.28.2\nplaywright = 1.62.0\n")
    fixture_bin = e["PATH"].split(os.pathsep)[0]
    nobin = tmp_path / "nobin"
    nobin.mkdir()
    for name in os.listdir(fixture_bin):
        if name != "cua-driver":
            (nobin / name).symlink_to(os.path.join(fixture_bin, name))
    e["PATH"] = str(nobin) + os.pathsep + os.environ["PATH"]
    e["CUA_RELEASE_BASE"] = f"file://{base}"
    # The fixture materializes a managed stub at pin; this test needs the
    # managed binary ABSENT.
    (tmp_path / "cua-bin" / "cua-driver").unlink()
    e["CUA_DRIVER_BIN"] = str(tmp_path / "cua-bin" / "cua-driver")
    e["CUA_DRIVER_OWNER"] = str(os.getuid())
    e["CUA_DRIVER_GROUP"] = str(os.getgid())
    r = run_bash("command -v cua-driver || echo ABSENT", env_extra=e)
    assert "ABSENT" in r.stdout, "test setup: cua-driver must be absent"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "cua-bin" / "cua-driver").read_bytes() == new_body


def test_cua_driver_refuses_on_checksum_mismatch(env, tmp_path):
    base = make_pinned_release(tmp_path, "0.28.2", b"REAL", digest="0" * 64)
    e = cua_env(env, tmp_path, cur_version="0.27.0", release_base=base)
    target = tmp_path / "cua-bin" / "cua-driver"
    target.parent.mkdir(parents=True, exist_ok=True)
    write_version_stub(target, "0.27.0")
    before = target.read_bytes()
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0
    assert target.read_bytes() == before, \
        "failed verify must not touch the live binary"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert "cua-driver" in lines[-1]["failed"]


def test_cua_driver_fail_closed_without_pin(env, tmp_path):
    e = dict(env["env"])
    (env["state"] / "self_update_pins.conf").write_text(
        "# no cua-driver pin\ndocker = 26.1\n")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert "cua-driver" in lines[-1]["failed"]


def test_cua_driver_dry_run_changes_nothing(env, tmp_path):
    curlog = tmp_path / "curl.log"
    bindir = make_stub_bin(tmp_path / "curlbin2",
                           {"curl": f"echo \"$@\" >> {curlog}; exit 0"})
    e = cua_env(env, tmp_path, cur_version="0.27.0")
    e["PATH"] = bindir + os.pathsep + e["PATH"]
    r = run_bash("./deploy/toolset-update.sh update --dry-run", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert not curlog.exists(), "dry-run must not fetch"
    managed = tmp_path / "cua-bin" / "cua-driver"
    assert managed.read_bytes() == b'#!/bin/sh\necho "cua-driver 0.27.0"\n', \
        "dry-run must not replace the managed binary"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "dry-run"


def test_cua_driver_installs_managed_when_absent_despite_path_at_pin(env, tmp_path):
    # Probe-only regression (review round 1): PATH is never consulted. A
    # PATH cua-driver already at the pin must not substitute for an absent
    # managed binary — the daemon runs $CUA_DRIVER_BIN, so "absent" there is
    # drift that must be repaired, not a no-op.
    new_body = b"FAKE-CUA-DRIVER-FRESH"
    base = make_pinned_release(tmp_path, "0.28.2", new_body)
    e = dict(env["env"])
    (env["state"] / "self_update_pins.conf").write_text("cua-driver = 0.28.2\nplaywright = 1.62.0\n")
    # Hermetic PATH like test_cua_driver_absent_installs_pin (fixture stubs
    # minus cua-driver, plus real tools), with a PATH cua-driver stub at the
    # pin — which the probe must ignore.
    fixture_bin = e["PATH"].split(os.pathsep)[0]
    nobin = tmp_path / "pathbin"
    nobin.mkdir()
    for name in os.listdir(fixture_bin):
        if name != "cua-driver":
            (nobin / name).symlink_to(os.path.join(fixture_bin, name))
    path_stub = nobin / "cua-driver"
    path_stub.write_text('#!/bin/sh\necho "cua-driver 0.28.2"\n')
    path_stub.chmod(path_stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                    | stat.S_IXOTH)
    e["PATH"] = str(nobin) + os.pathsep + os.environ["PATH"]
    e["CUA_RELEASE_BASE"] = f"file://{base}"
    # Absent managed binary — note the fixture materializes tmp_path/cua-bin,
    # so use a sibling dir to keep "absent" honest.
    e["CUA_DRIVER_BIN"] = str(tmp_path / "cua-bin-absent" / "cua-driver")
    e["CUA_DRIVER_OWNER"] = str(os.getuid())
    e["CUA_DRIVER_GROUP"] = str(os.getgid())
    r = run_bash("command -v cua-driver", env_extra=e)
    assert r.returncode == 0, "test setup: PATH must offer cua-driver at pin"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    target = tmp_path / "cua-bin-absent" / "cua-driver"
    assert target.read_bytes() == new_body, \
        "absent managed binary must be installed even when PATH is at pin"
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "ok"
    assert "cua-driver" in lines[-1]["components"]


def test_cua_driver_noop_senses_managed_binary_not_path(env, tmp_path):
    # Regression (review round 1): the probe must sense the managed binary
    # ($CUA_DRIVER_BIN), not PATH. The timer runs as root, whose PATH lacks
    # the daemon user's bindir — a PATH-only probe misreports "absent" in
    # production and re-downloads the pin on every run.
    curlog = tmp_path / "curl.log"
    curlbin = make_stub_bin(tmp_path / "curlbin3",
                            {"curl": f"echo \"$@\" >> {curlog}; exit 0"})
    e = dict(env["env"])
    (env["state"] / "self_update_pins.conf").write_text("cua-driver = 0.28.2\nplaywright = 1.62.0\n")
    fixture_bin = e["PATH"].split(os.pathsep)[0]
    nobin = tmp_path / "nobin1"
    nobin.mkdir()
    for name in os.listdir(fixture_bin):
        if name != "cua-driver":
            (nobin / name).symlink_to(os.path.join(fixture_bin, name))
    (nobin / "curl").symlink_to(os.path.join(curlbin, "curl"))
    e["PATH"] = str(nobin) + os.pathsep + os.environ["PATH"]
    managed = tmp_path / "cua-bin" / "cua-driver"
    managed.parent.mkdir(parents=True, exist_ok=True)
    managed.write_text('#!/bin/sh\necho "cua-driver 0.28.2"\n')
    managed.chmod(managed.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                  | stat.S_IXOTH)
    e["CUA_DRIVER_BIN"] = str(managed)
    e["CUA_DRIVER_OWNER"] = str(os.getuid())
    e["CUA_DRIVER_GROUP"] = str(os.getgid())
    r = run_bash("command -v cua-driver || echo ABSENT", env_extra=e)
    assert "ABSENT" in r.stdout, "test setup: cua-driver must be absent from PATH"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert not curlog.exists(), "no download when the managed binary is on pin"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "ok"


def test_cua_driver_drift_detected_on_managed_binary_despite_path(env, tmp_path):
    # Reverse direction of the probe/target divergence: a PATH cua-driver at
    # the pin must not mask drift of the managed binary.
    new_body = b"FAKE-CUA-DRIVER-PINNED"
    base = make_pinned_release(tmp_path, "0.28.2", new_body)
    e = cua_env(env, tmp_path, cur_version="0.28.2", release_base=base)
    managed = tmp_path / "cua-bin" / "cua-driver"
    managed.write_text('#!/bin/sh\necho "cua-driver 0.27.0"\n')
    managed.chmod(managed.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                  | stat.S_IXOTH)
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert managed.read_bytes() == new_body, \
        "drifted managed binary must be reinstalled despite PATH being at pin"
    assert stat.S_IMODE(managed.stat().st_mode) == 0o755


def _make_evil_release(tmp_path, pin, members):
    """Stage a release whose tarball has exactly the given members.
    members: list of (name, kind, payload); kind is "file" (payload bytes)
    or "symlink" (payload = link target)."""
    import io
    import tarfile
    base = tmp_path / "evilrelease"
    tagdir = base / f"cua-driver-rs-v{pin}"
    tagdir.mkdir(parents=True, exist_ok=True)
    asset = f"cua-driver-rs-{pin}-{_release_arch()}-binary.tar.gz"
    with tarfile.open(str(tagdir / asset), "w:gz") as tf:
        for name, kind, payload in members:
            ti = tarfile.TarInfo(name)
            if kind == "symlink":
                ti.type = tarfile.SYMTYPE
                ti.linkname = payload
                tf.addfile(ti)
            else:
                ti.size = len(payload)
                ti.mode = 0o755
                tf.addfile(ti, io.BytesIO(payload))
    want = hashlib.sha256((tagdir / asset).read_bytes()).hexdigest()
    (tagdir / "checksums.txt").write_text(f"{want}  {asset}\n")
    return str(base)


def test_cua_driver_refuses_tarball_with_symlink_member(env, tmp_path):
    # Attack shape (review round 1): symlink member `link -> <victim>`
    # followed by a regular `link/cua-driver` — a whole-archive `tar -xzf`
    # as root would write through the symlink outside the staging dir. The
    # layer must refuse at member screening and extract nothing.
    victim = tmp_path / "victim"
    victim.mkdir()
    base = _make_evil_release(tmp_path, "0.28.2", [
        ("link", "symlink", str(victim)),
        ("link/cua-driver", "file", b"EVIL-BINARY"),
    ])
    e = cua_env(env, tmp_path, cur_version="0.27.0", release_base=base)
    target = tmp_path / "cua-bin" / "cua-driver"
    write_version_stub(target, "0.27.0")
    before = target.read_bytes()
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0
    assert target.read_bytes() == before, \
        "refused update must not touch the live binary"
    assert not (victim / "cua-driver").exists(), \
        "nothing may be written outside the staging dir"
    # The MEMBER SCREENING must be the refuser (not tar's incidental
    # behavior): the old whole-archive code logs "extract failed" instead.
    runlog = (env["state"] / "toolset-update.log").read_text()
    assert "non-regular members" in runlog, runlog[-2000:]
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert "cua-driver" in lines[-1]["failed"]


def test_cua_driver_refuses_tarball_with_dotdot_member(env, tmp_path):
    base = _make_evil_release(tmp_path, "0.28.2", [
        ("../escape", "file", b"EVIL"),
        ("cua-driver", "file", b"REAL-BINARY"),
    ])
    e = cua_env(env, tmp_path, cur_version="0.27.0", release_base=base)
    target = tmp_path / "cua-bin" / "cua-driver"
    write_version_stub(target, "0.27.0")
    before = target.read_bytes()
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0
    assert target.read_bytes() == before, \
        "refused update must not touch the live binary"
    assert not (tmp_path / "escape").exists()
    # The MEMBER SCREENING must be the refuser: the old whole-archive code
    # lets tar strip the ".." and would install the member.
    runlog = (env["state"] / "toolset-update.log").read_text()
    assert "absolute or dot-dot member paths" in runlog, runlog[-2000:]
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert "cua-driver" in lines[-1]["failed"]


def test_install_copies_pins_file(env):
    r = run_bash("./deploy/toolset-update.sh install", env_extra=env["env"])
    assert r.returncode == 0, r.stderr
    pins = env["state"] / "self_update_pins.conf"
    assert pins.exists()
    assert "cua-driver = 0.28.2" in pins.read_text()


# --- apt layer (issue #532) --------------------------------------------------

def apt_env(env, tmp_path, installed=(), rc_state=(), apt_exit=0):
    """Env for apt-layer tests: dpkg stub answering `ii` for `installed`
    (and `rc` for `rc_state`), apt-get stub recording its argv + DEBIAN_FRONTEND
    and exiting apt_exit. os-security repair is disarmed via GOOD_CONF, and
    the cua-driver layer no-ops at the fixture pin."""
    e = dict(env["env"])
    (env["apt"] / "20auto-upgrades").write_text(GOOD_CONF)
    aptlog = tmp_path / "apt-argv.log"
    e["APT_ARGV_LOG"] = str(aptlog)
    e["APT_INSTALLED"] = " ".join(installed)
    e["APT_RC"] = " ".join(rc_state)
    e["APT_EXIT"] = str(apt_exit)
    bindir = make_stub_bin(tmp_path / "aptlayerbin", {
        "dpkg": (
            'pkg="$2"; '
            'case " $APT_INSTALLED " in'
            ' *" $pkg "*) echo "ii  $pkg  1:99.0-test amd64 fake pkg"; exit 0;;'
            'esac; '
            'case " $APT_RC " in'
            ' *" $pkg "*) echo "rc  $pkg  1:99.0-test amd64 fake pkg"; exit 0;;'
            'esac; '
            'exit 1'
        ),
        "tmux": "exit 1",
        "apt-get": (
            f'echo "argv: $@" >> "{aptlog}"; '
            f'echo "DEBIAN_FRONTEND=$DEBIAN_FRONTEND" >> "{aptlog}"; '
            'exit "$APT_EXIT"'
        ),
        # cua-driver at the pin: the layer no-ops so these tests stay about
        # the apt layer.
        "cua-driver": 'echo "cua-driver 0.28.2"',
    })
    e["PATH"] = bindir + os.pathsep + make_realtools(tmp_path)
    return e, aptlog


def test_apt_layer_noop_when_nothing_installed(env, tmp_path):
    e, aptlog = apt_env(env, tmp_path, installed=())
    r = source_and('_apt_layer 0', e)
    assert r.returncode == 0, r.stderr
    assert not aptlog.exists(), "no installed packages: apt-get must not run"
    assert "no managed apt packages installed" in \
        (env["state"] / "toolset-update.log").read_text()


def test_apt_layer_converges_installed_candidates_only(env, tmp_path):
    e, aptlog = apt_env(env, tmp_path, installed=("docker.io", "gh"))
    r = source_and('_apt_layer 0', e)
    assert r.returncode == 0, r.stderr
    calls = aptlog.read_text()
    assert "argv: -y install" in calls
    assert "--only-upgrade" in calls
    assert "-o Dpkg::Options::=--force-confdef" in calls
    assert "-o Dpkg::Options::=--force-confold" in calls
    # Installed candidates are passed...
    assert "docker.io" in calls and "gh" in calls
    # ...but a candidate that is not installed is never passed — no stray
    # upgrades, no new installs.
    assert "docker-ce" not in calls and "nodejs" not in calls
    # Non-interactive by construction.
    assert "DEBIAN_FRONTEND=noninteractive" in calls


def test_apt_layer_dry_run_simulates(env, tmp_path):
    e, aptlog = apt_env(env, tmp_path, installed=("gh",))
    r = source_and('_apt_layer 1', e)
    assert r.returncode == 0, r.stderr
    calls = aptlog.read_text()
    # Simulate (-s), never the real -y.
    assert "argv: -s install" in calls
    assert "-y" not in calls.replace("DEBIAN_FRONTEND=noninteractive", "")
    assert "--only-upgrade" in calls and "gh" in calls


def test_apt_layer_fail_closed_without_apt_get(env, tmp_path):
    e, _ = apt_env(env, tmp_path, installed=("gh",))
    nobin = make_stub_bin(tmp_path / "noaptget", {"dpkg": "exit 0"})
    e["PATH"] = nobin + os.pathsep + make_realtools(tmp_path)
    r = source_and('_apt_layer 0', e)
    assert r.returncode != 0
    assert "apt-get not found" in \
        (env["state"] / "toolset-update.log").read_text()


def test_apt_layer_fail_closed_without_dpkg(env, tmp_path):
    e, aptlog = apt_env(env, tmp_path, installed=("gh",))
    nobin = make_stub_bin(tmp_path / "nodpkg", {
        "apt-get": f'echo "$@" >> "{aptlog}"; exit 0',
    })
    e["PATH"] = nobin + os.pathsep + make_realtools(tmp_path)
    r = source_and('_apt_layer 0', e)
    assert r.returncode != 0
    assert not aptlog.exists(), "dpkg missing: must refuse before apt-get"


def test_apt_layer_ignores_rc_state_packages(env, tmp_path):
    # A package in `rc` (removed, conffiles left) is not installed — it must
    # not be passed to apt-get, which would reinstall it.
    e, aptlog = apt_env(env, tmp_path, installed=(), rc_state=("docker.io",))
    r = source_and('_apt_layer 0', e)
    assert r.returncode == 0, r.stderr
    assert not aptlog.exists()


def test_apt_layer_candidate_lists_overridable(env, tmp_path):
    e, aptlog = apt_env(env, tmp_path, installed=("fake-docker",))
    e["APT_DOCKER_PKGS"] = "fake-docker"
    r = source_and('_apt_layer 0', e)
    assert r.returncode == 0, r.stderr
    assert "fake-docker" in aptlog.read_text()


def test_update_names_apt_on_layer_failure(env, tmp_path):
    # apt-get stub fails: the full update fails loud and the audit names apt.
    e, _ = apt_env(env, tmp_path, installed=("gh",), apt_exit=1)
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert "apt" in lines[-1]["failed"]


def test_update_audit_lists_apt_when_green(env, tmp_path):
    e, _ = apt_env(env, tmp_path, installed=("gh",))
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "ok"
    assert "apt" in lines[-1]["components"]


def test_update_dry_run_simulates_apt(env, tmp_path):
    e, aptlog = apt_env(env, tmp_path, installed=("gh",))
    r = run_bash("./deploy/toolset-update.sh update --dry-run", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert "argv: -s install" in aptlog.read_text()
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "dry-run"


# --- playwright layer -----------------------------------------------------------

def test_playwright_noop_when_at_pin(env, tmp_path):
    # venv already on pin: no pip — but the browser and system-deps steps
    # still run (idempotent): an on-pin pip package with an emptied browser
    # cache or missing system libs must still heal.
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.62.0")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert not piplog.exists(), "no pip call when already on pin"
    pw_calls = pwlog.read_text().splitlines()
    assert "install chromium" in pw_calls, pw_calls
    assert "install-deps --dry-run chromium" in pw_calls, pw_calls
    # The dry-run stub reports everything installed by default: no apt-get.
    assert not aptlog.exists(), "no apt call when deps are satisfied"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "ok"
    assert "playwright" in lines[-1]["components"]


def test_playwright_on_pin_refuses_when_cli_missing(env, tmp_path):
    # On-pin but the CLI is gone: the venv is corrupt — refuse fail-closed
    # rather than trusting the version probe.
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.62.0")
    (tmp_path / "pw-venv" / "bin" / "playwright").unlink()
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert not piplog.exists(), "no pip call on corrupt venv"
    assert "playwright" in audit_lines(env)[-1]["failed"]


def test_playwright_installs_pin_on_drift(env, tmp_path):
    # Drifted venv: exact-pin pip install, then browsers, then the deps
    # dry-run (satisfied here — the missing-deps install has its own tests).
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.61.0")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    pip_calls = piplog.read_text().splitlines()
    assert len(pip_calls) == 1, pip_calls
    assert "install" in pip_calls[0] and "playwright==1.62.0" in pip_calls[0], \
        pip_calls
    # Never a floating upgrade: the specifier is exactly the pin.
    assert "playwright==" in pip_calls[0]
    pw_calls = pwlog.read_text().splitlines()
    assert "install chromium" in pw_calls, pw_calls
    assert "install-deps --dry-run chromium" in pw_calls, pw_calls
    assert pw_calls.index("install chromium") < pw_calls.index(
        "install-deps --dry-run chromium"), pw_calls
    # The venv CLI is never executed as root for deps: no bare
    # `install-deps` (the mutating form) may appear in the browser log.
    assert not any(c.startswith("install-deps ") and "--dry-run" not in c
                   for c in pw_calls), pw_calls
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "ok"


def test_playwright_install_deps_installs_missing_validated(env, tmp_path):
    # Dry-run reports missing deps: root apt-get installs exactly the
    # validated names (non-interactive, no recommends), nothing else.
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.62.0")
    e["PW_DRYRUN_TEXT"] = ("Missing system dependencies (2):\n"
                           "  libnss3\n  libatk1.0-0\n")
    e["PW_DRYRUN_EXIT"] = "1"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    argv = aptlog.read_text().splitlines()
    assert len(argv) == 1, argv
    assert "install" in argv[0] and "--no-install-recommends" in argv[0], argv
    assert "libnss3" in argv[0] and "libatk1.0-0" in argv[0], argv
    assert "--only-upgrade" not in argv[0], argv
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "ok"


def test_playwright_install_deps_refuses_unsafe_name(env, tmp_path):
    # A dep name outside the Debian package-name pattern: refuse, and root
    # installs nothing.
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.62.0")
    e["PW_DRYRUN_TEXT"] = ("Missing system dependencies (2):\n"
                           "  libnss3\n  libnss3; rm -rf /\n")
    e["PW_DRYRUN_EXIT"] = "1"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert not aptlog.exists(), "no apt call on unsafe dep name"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert "playwright" in lines[-1]["failed"]


def test_playwright_install_deps_refuses_count_mismatch(env, tmp_path):
    # Header says 2, body lists 1: fail-closed, root installs nothing.
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.62.0")
    e["PW_DRYRUN_TEXT"] = "Missing system dependencies (2):\n  libnss3\n"
    e["PW_DRYRUN_EXIT"] = "1"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert not aptlog.exists(), "no apt call on shape mismatch"
    assert "playwright" in audit_lines(env)[-1]["failed"]


def test_playwright_install_deps_refuses_garbage_output(env, tmp_path):
    # Neither the "all installed" message nor the Missing block: refuse.
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.62.0")
    e["PW_DRYRUN_TEXT"] = "something unexpected happened\n"
    e["PW_DRYRUN_EXIT"] = "1"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert not aptlog.exists(), "no apt call on garbage output"
    assert "playwright" in audit_lines(env)[-1]["failed"]


def test_playwright_refuses_when_user_switch_impossible(env, tmp_path):
    # PLAYWRIGHT_USER names a user we can never become: the layer must
    # refuse fail-closed instead of running pip/browsers as the wrong user.
    # Hermetic as root (runuser fails on the bogus user) and non-root
    # (direct refuse without being root).
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.61.0")
    e["PLAYWRIGHT_USER"] = "no-such-user-pw-qa"
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert not piplog.exists(), "no pip call when the user-switch is impossible"
    assert not pwlog.exists(), "no browser call when the user-switch is impossible"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert "playwright" in lines[-1]["failed"]


def test_playwright_refuses_when_venv_absent(env, tmp_path):
    # No managed venv: fail-closed (the venv is provisioned by setup, not
    # this layer) — nothing is fetched.
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path)
    empty = tmp_path / "no-venv"
    empty.mkdir()
    e["PLAYWRIGHT_VENV"] = str(empty)
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert not piplog.exists(), "no pip call on absent venv"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert "playwright" in lines[-1]["failed"]


def test_playwright_fail_closed_without_pin(env, tmp_path):
    e, piplog, _, _ = pw_env(env, tmp_path)
    (env["state"] / "self_update_pins.conf").write_text(
        "# no playwright pin\ncua-driver = 0.28.2\n")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert not piplog.exists(), "no pip call without a pin"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert "playwright" in lines[-1]["failed"]


def test_playwright_refuses_unsafe_pin(env, tmp_path):
    e, piplog, _, _ = pw_env(env, tmp_path, pin="1.62.0;evil")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert not piplog.exists(), "no pip call on unsafe pin"


def test_playwright_version_unknown_refuses(env, tmp_path):
    # Installed but unparseable version: refuse rather than guess.
    e, piplog, _, _ = pw_env(env, tmp_path, cur_version="not-a-version")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert not piplog.exists(), "no pip call on unparseable version"
    lines = audit_lines(env)
    assert "playwright" in lines[-1]["failed"]


def test_playwright_dry_run_changes_nothing(env, tmp_path):
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.61.0")
    r = run_bash("./deploy/toolset-update.sh update --dry-run", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert not piplog.exists(), "dry-run must not pip install"
    assert not pwlog.exists(), "dry-run must not touch browsers/deps"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "dry-run"


def test_playwright_browser_cli_missing_refuses(env, tmp_path):
    # pip succeeded but the venv has no playwright CLI: the browser/deps
    # steps would be meaningless — refuse on the explicit missing-CLI
    # guard (not merely on the incidental exec failure).
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.61.0")
    (tmp_path / "pw-venv" / "bin" / "playwright").unlink()
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert piplog.exists(), "pip runs before the CLI check"
    assert not pwlog.exists(), "no browser/deps install without the CLI"
    run_log = (env["state"] / "toolset-update.log").read_text()
    assert "missing after pip install" in run_log, run_log
    lines = audit_lines(env)
    assert "playwright" in lines[-1]["failed"]


def test_playwright_pip_failure_fails_loud(env, tmp_path):
    e, piplog, pwlog, aptlog = pw_env(env, tmp_path, cur_version="1.61.0")
    # Re-stage the venv with a pip stub that fails.
    shutil.rmtree(tmp_path / "pw-venv")
    stage_pw_venv(tmp_path, "1.61.0", piplog=piplog, pwlog=pwlog, pip_exit=1)
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0, r.stderr
    assert not pwlog.exists(), "no browser/deps install after pip failure"
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "failed"
    assert "playwright" in lines[-1]["failed"]


def test_playwright_senses_managed_venv_not_path(env, tmp_path):
    # A PATH-resolved `python` reporting the pin must not mask drift of the
    # managed venv: the probe senses the venv, never PATH.
    e, piplog, _, _ = pw_env(env, tmp_path, cur_version="1.61.0")
    bindir = make_stub_bin(tmp_path / "pathbin", {
        "python": 'echo "1.62.0"',
        "python3": 'echo "1.62.0"',
    })
    e["PATH"] = bindir + os.pathsep + e["PATH"]
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    assert piplog.exists(), "managed-venv drift must still converge"


def test_status_reports_playwright_from_managed_venv(env, tmp_path):
    # status probes the managed venv (not system python): present + version
    # when the venv has playwright, absent when the venv is gone.
    e, _, _, _ = pw_env(env, tmp_path, cur_version="1.62.0")
    r = run_bash("./deploy/toolset-update.sh status", env_extra=e)
    assert r.returncode == 0, r.stderr
    rows = {line.split("\t")[0]: line.split("\t")
            for line in r.stdout.splitlines() if line.strip()}
    assert rows["playwright"][1] == "present", rows["playwright"]
    assert "1.62.0" in rows["playwright"][2], rows["playwright"]
    empty = tmp_path / "no-venv"
    empty.mkdir()
    e["PLAYWRIGHT_VENV"] = str(empty)
    r = run_bash("./deploy/toolset-update.sh status", env_extra=e)
    rows = {line.split("\t")[0]: line.split("\t")
            for line in r.stdout.splitlines() if line.strip()}
    assert rows["playwright"][1] == "absent", rows["playwright"]


def test_status_probe_runs_as_playwright_user(env, tmp_path):
    # Regression: the status probe executes the venv interpreter, so it
    # must go through the user-switch — with an impossible PLAYWRIGHT_USER
    # the probe refuses and the row reads absent even though the venv is
    # healthy (a direct exec would have reported present).
    e, _, _, _ = pw_env(env, tmp_path, cur_version="1.62.0")
    e["PLAYWRIGHT_USER"] = "no-such-user-pw-qa"
    r = run_bash("./deploy/toolset-update.sh status", env_extra=e)
    assert r.returncode == 0, r.stderr
    rows = {line.split("\t")[0]: line.split("\t")
            for line in r.stdout.splitlines() if line.strip()}
    assert rows["playwright"][1] == "absent", rows["playwright"]


def test_update_audit_lists_playwright_when_green(env, tmp_path):
    e, _, _, _ = pw_env(env, tmp_path)
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode == 0, r.stderr
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "ok"
    assert "playwright" in lines[-1]["components"]
