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
        # cua-driver at the pinned version: the cua-driver layer no-ops
        # (layer-specific tests override the pin/PATH as needed)
        "cua-driver": 'echo "cua-driver 0.28.2"',
    })
    # pins file the updater reads (installed-copy model: tests stage it in
    # the state dir the same way `install` would)
    statedir.mkdir(parents=True, exist_ok=True)
    (statedir / "self_update_pins.conf").write_text(
        "# test pins\ncua-driver = 0.28.2\n"
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
    # Trust-model pin (#532): the script's only network surface is the
    # cua-driver layer's pinned release fetch. apt-get appears exactly once:
    # the unattended-upgrades bootstrap. curl appears exactly twice: the
    # checksums.txt + tarball fetch inside _cua_driver_layer, both against
    # "$base/$tag/..." (base defaults to the single https:// constant
    # CUA_RELEASE_BASE). A future slice adding network or package-manager
    # surface must update this pin and docs/TOOLSET_UPDATE.md.
    # (Matches command invocations only — the "apt-get install failed" log
    # string is not a second call site.)
    import re
    text = open(SCRIPT).read()
    for banned in ("wget ", "git clone", "pip install", "npm install",
                   "http://"):
        assert banned not in text, f"must not contain: {banned}"
    invocations = [l for l in text.splitlines()
                   if re.search(r"^\s*(_sudo\s+)?apt-get\b", l)]
    assert len(invocations) == 1, invocations
    assert "install -y unattended-upgrades" in invocations[0]
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
    # no privilege escalation, private /tmp.
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
    assert "PrivateTmp=true" in svc


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


def cua_env(env, tmp_path, pin="0.28.2", cur_version="0.28.2",
            release_base=None):
    """Env for cua-driver layer tests: pins file, PATH with a cua-driver stub
    reporting cur_version, CUA_DRIVER_BIN under tmp, and (optionally) a
    file:// release base for hermetic downloads."""
    e = dict(env["env"])
    (env["state"] / "self_update_pins.conf").write_text(
        f"# test pins\ncua-driver = {pin}\n")
    bindir = make_stub_bin(tmp_path / "cuabin", {
        "cua-driver": f'echo "cua-driver {cur_version}"',
        "tmux": "exit 1",
    })
    e["PATH"] = bindir + os.pathsep + e["PATH"]
    e["CUA_DRIVER_BIN"] = str(tmp_path / "cua-bin" / "cua-driver")
    e["CUA_DRIVER_OWNER"] = str(os.getuid())
    e["CUA_DRIVER_GROUP"] = str(os.getgid())
    if release_base is not None:
        e["CUA_RELEASE_BASE"] = f"file://{release_base}"
    return e


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
    bindir = make_stub_bin(tmp_path / "verbin", {
        "cua-driver": 'echo "cua-driver 0.28.2 (abc123)"',
    })
    e = dict(env["env"])
    e["PATH"] = bindir + os.pathsep + e["PATH"]
    r = source_and("_cua_driver_current", e)
    assert r.stdout == "0.28.2"
    # No version-like token, or a bare number: version-unknown (fail-closed,
    # never guessed).
    for body in ('echo "no version here"', 'echo "build 12345"'):
        bindir2 = make_stub_bin(tmp_path / "verbin2", {"cua-driver": body})
        e2 = dict(env["env"])
        e2["PATH"] = bindir2 + os.pathsep + os.environ["PATH"]
        r = source_and("_cua_driver_current", e2)
        assert r.stdout == "version-unknown", body
    # Absent binary.
    e3 = dict(env["env"])
    e3["PATH"] = make_realtools(tmp_path / "notools")
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
    target.parent.mkdir(parents=True)
    target.write_bytes(b"OLD-BINARY")
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
        "cua-driver = 0.28.2\n")
    fixture_bin = e["PATH"].split(os.pathsep)[0]
    nobin = tmp_path / "nobin"
    nobin.mkdir()
    for name in os.listdir(fixture_bin):
        if name != "cua-driver":
            (nobin / name).symlink_to(os.path.join(fixture_bin, name))
    e["PATH"] = str(nobin) + os.pathsep + os.environ["PATH"]
    e["CUA_RELEASE_BASE"] = f"file://{base}"
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
    target.parent.mkdir(parents=True)
    target.write_bytes(b"OLD-BINARY")
    r = run_bash("./deploy/toolset-update.sh update", env_extra=e)
    assert r.returncode != 0
    assert target.read_bytes() == b"OLD-BINARY", \
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
    assert not (tmp_path / "cua-bin" / "cua-driver").exists()
    lines = audit_lines(env)
    assert lines and lines[-1]["result"] == "dry-run"


def test_install_copies_pins_file(env):
    r = run_bash("./deploy/toolset-update.sh install", env_extra=env["env"])
    assert r.returncode == 0, r.stderr
    pins = env["state"] / "self_update_pins.conf"
    assert pins.exists()
    assert "cua-driver = 0.28.2" in pins.read_text()
