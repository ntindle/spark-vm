"""Shell-script gates for cua/bin/*.sh.

The CUA desktop stack's shell scripts (desktop lifecycle, keepalive,
GUI launchers) run on spark-vm with real side effects, so they cannot
be executed in CI. The executable maximum is what CI itself does for
other host-side scripts (see deploy/test_auto_deploy.py): `bash -n`
syntax plus a shellcheck -S warning gate, with an explicit skip (not a
silent pass) when shellcheck is not installed.

On top of that, the security guards that cannot be run end-to-end
(#493's rundir/env trust checks, #495's flock serialization) are
extracted from the scripts and exercised in isolation: the test pulls
the guard function bodies out of the real files (asserting the
extraction actually found them, so a silently-empty extraction fails
loudly) and runs them against throwaway paths with a fake PATH so the
real daemons can never be touched.
"""

import os
import subprocess
import tempfile

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


def extract_function(script, name):
    """Pull a shell function's body out of a script, from its definition
    line through the first column-0 closing brace. Raises (fail loud) if
    the function is not found — a silent empty extraction would make the
    behavioral tests below pass vacuously."""
    out = subprocess.run(
        ["awk", f"/^{name}\\(\\) \\{{/,/^\\}}$/", script],
        capture_output=True, text=True, timeout=60)
    body = out.stdout
    assert body, f"function {name} not found in {script} (extraction empty)"
    assert body.startswith(f"{name}() {{"), \
        f"extraction for {name} does not start at the definition"
    return body


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


# --------------------------------- behavioral guards (#493 / #495)

DESKTOP_SH = os.path.join(REPO_ROOT, "cua", "bin", "cua-desktop.sh")
KEEPALIVE_SH = os.path.join(REPO_ROOT, "cua", "bin", "cua-keepalive.sh")


def run_guard(func_body, call, env=None):
    """Run an extracted shell function body + a call expression in a
    throwaway bash. `env` extra vars are exported first."""
    preamble = "".join(f"export {k}={v}\n" for k, v in (env or {}).items())
    script = preamble + func_body + "\n" + call + "\n"
    return subprocess.run(["bash", "-c", script],
                         capture_output=True, text=True, timeout=60)


def fake_id_bin(tmpdir, name="attacker"):
    """A fake bin dir whose `id -un` reports a different user — exercises
    the wrong-owner refusal branches without needing a second real user."""
    bindir = os.path.join(tmpdir, "fakebin")
    os.makedirs(bindir, exist_ok=True)
    with open(os.path.join(bindir, "id"), "w") as f:
        f.write("#!/bin/bash\n"
                'if [ "$1" = "-un" ]; then echo "%s"; else /usr/bin/id "$@"; fi\n'
                % name)
    os.chmod(os.path.join(bindir, "id"), 0o755)
    return bindir


class TestEnsurePrivateRundir:
    @pytest.fixture()
    def guard(self):
        return extract_function(DESKTOP_SH, "ensure_private_rundir")

    def test_creates_missing_dir_with_0700(self, guard):
        with tempfile.TemporaryDirectory() as t:
            r = run_guard(guard, "ensure_private_rundir",
                          env={"RUNDIR": os.path.join(t, "rundir")})
            assert r.returncode == 0, r.stderr
            st = os.stat(os.path.join(t, "rundir"))
            assert st.st_mode & 0o777 == 0o700

    def test_repairs_loose_mode_on_own_dir(self, guard):
        with tempfile.TemporaryDirectory() as t:
            d = os.path.join(t, "rundir")
            os.mkdir(d, 0o755)
            r = run_guard(guard, "ensure_private_rundir", env={"RUNDIR": d})
            assert r.returncode == 0, r.stderr
            assert os.stat(d).st_mode & 0o777 == 0o700

    def test_accepts_already_0700_dir(self, guard):
        with tempfile.TemporaryDirectory() as t:
            d = os.path.join(t, "rundir")
            os.mkdir(d, 0o700)
            r = run_guard(guard, "ensure_private_rundir", env={"RUNDIR": d})
            assert r.returncode == 0, r.stderr

    def test_refuses_symlink(self, guard):
        with tempfile.TemporaryDirectory() as t:
            real = os.path.join(t, "real")
            os.mkdir(real)
            link = os.path.join(t, "rundir")
            os.symlink(real, link)
            r = run_guard(guard, "ensure_private_rundir", env={"RUNDIR": link})
            assert r.returncode != 0
            assert "symlink" in r.stderr

    def test_refuses_wrong_owner_dir(self, guard):
        with tempfile.TemporaryDirectory() as t:
            d = os.path.join(t, "rundir")
            os.mkdir(d)
            bindir = fake_id_bin(t)
            r = run_guard(
                guard, "ensure_private_rundir",
                env={"RUNDIR": d,
                     "PATH": bindir + ":/usr/local/bin:/usr/bin:/bin"})
            assert r.returncode != 0
            assert "another user" in r.stderr


class TestSafeSourceEnv:
    @pytest.fixture()
    def guard(self):
        return extract_function(KEEPALIVE_SH, "safe_source_env")

    def _env(self, tmpdir, mode=0o600, content="export CUA_PROBE_SET=yes\n"):
        p = os.path.join(tmpdir, "env")
        with open(p, "w") as f:
            f.write(content)
        os.chmod(p, mode)
        return p

    def test_sources_trusted_file(self, guard):
        with tempfile.TemporaryDirectory() as t:
            p = self._env(t)
            r = run_guard(guard, f'safe_source_env "{p}" && echo "PROBE=$CUA_PROBE_SET"')
            assert r.returncode == 0, r.stderr
            assert "PROBE=yes" in r.stdout

    def test_refuses_group_writable(self, guard):
        with tempfile.TemporaryDirectory() as t:
            p = self._env(t, mode=0o660)
            r = run_guard(guard, f'safe_source_env "{p}" && echo "PROBE=$CUA_PROBE_SET"')
            assert r.returncode != 0
            assert "PROBE=yes" not in r.stdout

    def test_refuses_other_writable(self, guard):
        with tempfile.TemporaryDirectory() as t:
            p = self._env(t, mode=0o606)
            r = run_guard(guard, f'safe_source_env "{p}" && echo "PROBE=$CUA_PROBE_SET"')
            assert r.returncode != 0
            assert "PROBE=yes" not in r.stdout

    def test_refuses_symlink(self, guard):
        with tempfile.TemporaryDirectory() as t:
            real = self._env(t)
            link = os.path.join(t, "link")
            os.symlink(real, link)
            r = run_guard(guard, f'safe_source_env "{link}" && echo "PROBE=$CUA_PROBE_SET"')
            assert r.returncode != 0
            assert "PROBE=yes" not in r.stdout

    def test_refuses_missing(self, guard):
        with tempfile.TemporaryDirectory() as t:
            r = run_guard(guard, f'safe_source_env "{t}/nope"')
            assert r.returncode != 0

    def test_refuses_wrong_owner(self, guard):
        with tempfile.TemporaryDirectory() as t:
            p = self._env(t)
            bindir = fake_id_bin(t)
            r = run_guard(
                guard, f'safe_source_env "{p}"',
                env={"PATH": bindir + ":/usr/local/bin:/usr/bin:/bin"})
            assert r.returncode != 0


class TestKeepaliveFlockPin:
    def test_keepalive_serializes_on_flock(self):
        # #495's keepalive-side fix is a structural guarantee: the whole
        # run must hold a non-blocking flock so overlapping invocations
        # cannot both reach the spawn. The actual exclusion semantics live
        # in the bridge's singleton lock, which is functionally tested in
        # test_cua_bridge.py.
        src = open(KEEPALIVE_SH).read()
        assert "flock -n" in src
        assert "cua-bridge.keepalive.lock" in src
