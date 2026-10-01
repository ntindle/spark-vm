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
import re
import shutil
import subprocess
import tempfile
import time

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
TRUST_SH = os.path.join(REPO_ROOT, "cua", "bin", "cua-trust.sh")


def run_guard(func_body, call, env=None, prelude=""):
    """Run an extracted shell function body + a call expression in a
    throwaway bash. `env` extra vars are exported first; `prelude` is
    shell sourced before the body (used to provide the shared trust
    predicate from cua-trust.sh to functions that call it)."""
    preamble = "".join(f"export {k}={v}\n" for k, v in (env or {}).items())
    script = preamble + prelude + "\n" + func_body + "\n" + call + "\n"
    return subprocess.run(["bash", "-c", script],
                         capture_output=True, text=True, timeout=60)


def trust_prelude():
    return open(TRUST_SH).read()


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

    def test_removes_untrusted_env_plant(self, guard):
        # #493's choke point: a stale plant in the env file (e.g. a
        # symlink left from the pre-fix era) is removed so no consumer
        # can source it; the guard still succeeds.
        with tempfile.TemporaryDirectory() as t:
            d = os.path.join(t, "rundir")
            os.mkdir(d, 0o700)
            evil = os.path.join(t, "evil")
            with open(evil, "w") as f:
                f.write("export CUA_PROBE_SET=yes\n")
            os.symlink(evil, os.path.join(d, "env"))
            r = run_guard(guard, "ensure_private_rundir", env={"RUNDIR": d},
                          prelude=trust_prelude())
            assert r.returncode == 0, r.stderr
            assert "WARNING" in r.stderr
            assert not os.path.lexists(os.path.join(d, "env"))

    def test_keeps_trusted_env(self, guard):
        with tempfile.TemporaryDirectory() as t:
            d = os.path.join(t, "rundir")
            os.mkdir(d, 0o700)
            p = os.path.join(d, "env")
            with open(p, "w") as f:
                f.write("export CUA_PROBE_SET=yes\n")
            os.chmod(p, 0o600)
            r = run_guard(guard, "ensure_private_rundir", env={"RUNDIR": d},
                          prelude=trust_prelude())
            assert r.returncode == 0, r.stderr
            assert os.path.isfile(p)


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
            r = run_guard(guard, f'safe_source_env "{p}" && echo "PROBE=$CUA_PROBE_SET"', prelude=trust_prelude())
            assert r.returncode == 0, r.stderr
            assert "PROBE=yes" in r.stdout

    def test_refuses_group_writable(self, guard):
        with tempfile.TemporaryDirectory() as t:
            p = self._env(t, mode=0o660)
            r = run_guard(guard, f'safe_source_env "{p}" && echo "PROBE=$CUA_PROBE_SET"', prelude=trust_prelude())
            assert r.returncode != 0
            assert "PROBE=yes" not in r.stdout

    def test_refuses_other_writable(self, guard):
        with tempfile.TemporaryDirectory() as t:
            p = self._env(t, mode=0o606)
            r = run_guard(guard, f'safe_source_env "{p}" && echo "PROBE=$CUA_PROBE_SET"', prelude=trust_prelude())
            assert r.returncode != 0
            assert "PROBE=yes" not in r.stdout

    def test_refuses_symlink(self, guard):
        with tempfile.TemporaryDirectory() as t:
            real = self._env(t)
            link = os.path.join(t, "link")
            os.symlink(real, link)
            r = run_guard(guard, f'safe_source_env "{link}" && echo "PROBE=$CUA_PROBE_SET"', prelude=trust_prelude())
            assert r.returncode != 0
            assert "PROBE=yes" not in r.stdout

    def test_refuses_missing(self, guard):
        with tempfile.TemporaryDirectory() as t:
            r = run_guard(guard, f'safe_source_env "{t}/nope"', prelude=trust_prelude())
            assert r.returncode != 0

    def test_refuses_wrong_owner(self, guard):
        with tempfile.TemporaryDirectory() as t:
            p = self._env(t)
            bindir = fake_id_bin(t)
            r = run_guard(
                guard, f'safe_source_env "{p}"',
                env={"PATH": bindir + ":/usr/local/bin:/usr/bin:/bin"},
                prelude=trust_prelude())
            assert r.returncode != 0


class TestTakeRunLock:
    @pytest.fixture()
    def guard(self):
        return extract_function(KEEPALIVE_SH, "take_run_lock")

    def test_acquires_lock(self, guard):
        with tempfile.TemporaryDirectory() as t:
            lock = os.path.join(t, "run.lock")
            r = run_guard(guard, f'take_run_lock "{lock}"; echo "RC=$?"',
                          prelude="")
            assert r.returncode == 0, r.stderr
            assert "RC=0" in r.stdout
            assert os.path.isfile(lock)

    def test_second_holder_gets_contention_not_error(self, guard):
        # A background process holding the lock (the overlapping-cron
        # case) must yield rc 2 — contended, not an error — with a note
        # on stderr.
        if not shutil.which("flock"):
            pytest.skip("flock(1) not installed")
        with tempfile.TemporaryDirectory() as t:
            lock = os.path.join(t, "run.lock")
            holder = subprocess.Popen(["flock", lock, "sleep", "30"])
            try:
                r = run_guard(guard, f'take_run_lock "{lock}"; echo "RC=$?"')
            finally:
                holder.terminate()
                holder.wait(timeout=10)
            assert r.returncode == 0, r.stderr
            assert "RC=2" in r.stdout
            assert "another keepalive run" in r.stderr

    def test_lock_open_failure_is_loud(self, guard):
        # An unopenable lock (here: the parent is a regular file, so the
        # mkdir -p fails) must be rc 1 with a loud message — never a
        # silent exit 0 that disables supervision.
        with tempfile.TemporaryDirectory() as t:
            blocker = os.path.join(t, "blocker")
            with open(blocker, "w") as f:
                f.write("x")
            r = run_guard(guard,
                          f'take_run_lock "{blocker}/run.lock"; echo "RC=$?"')
            assert r.returncode == 0, r.stderr
            assert "RC=1" in r.stdout
            assert "cannot" in r.stderr

    def test_spawned_child_does_not_pin_lock(self, guard):
        # Regression for the fd-inheritance lock-jam (#495): a keepalive
        # run holds the flock on fd 9; long-lived children spawned during
        # the run must NOT inherit fd 9, or the lock stays held after the
        # parent exits and every future cron run silently no-ops.
        if not shutil.which("flock") or not shutil.which("setsid"):
            pytest.skip("flock(1)/setsid not installed")
        for close_fd, expect in ((True, "FREE"), (False, "HELD")):
            with tempfile.TemporaryDirectory() as t:
                lock = os.path.join(t, "run.lock")
                close = "9>&-" if close_fd else ""
                # Probe with the fd form of flock(1) in a subshell: it can
                # take the lock only if the orphaned child did NOT inherit
                # fd 9. The sleep is left to exit on its own (20s); each
                # iteration uses its own lock file, so nothing lingers
                # that a later iteration could observe.
                script = (
                    f'take_run_lock "{lock}" || exit 99\n'
                    f"setsid sleep 20 {close} < /dev/null > /dev/null 2>&1 &\n"
                    "exec 9>&-\n"  # parent exits the run, as the keepalive does
                    'if ( flock -n 200 ) 200>"$LOCKPROBE"; then\n'
                    '  echo "STATE=FREE"\n'
                    "else\n"
                    '  echo "STATE=HELD"\n'
                    "fi\n"
                )
                r = subprocess.run(
                    ["bash", "-c", guard + "\n" + script],
                    capture_output=True, text=True, timeout=60,
                    env={**os.environ, "LOCKPROBE": lock})
                assert r.returncode == 0, r.stderr
                assert f"STATE={expect}" in r.stdout, (
                    f"close_fd={close_fd}: expected {expect}, got {r.stdout!r}")


class TestKeepaliveFlockPin:
    def test_keepalive_serializes_on_flock(self):
        # #495's keepalive-side fix is a structural guarantee: the whole
        # run must hold a non-blocking flock so overlapping invocations
        # cannot both reach the spawn. The lock lives in the user's own
        # ~/.cache — never world-writable /tmp, where a planted symlink
        # would be truncated by the O_TRUNC open and any local user could
        # squat the lock (#493's sibling). The actual exclusion semantics
        # live in the bridge's singleton lock, which is functionally
        # tested in test_cua_bridge.py.
        src = open(KEEPALIVE_SH).read()
        assert "flock -n" in src
        assert "cua-bridge.keepalive.lock" in src
        assert "/tmp/cua-bridge.keepalive.lock" not in src

    def test_spawn_lines_close_lock_fd(self):
        # Every long-lived child spawned while the run lock is held must
        # close fd 9 (see TestTakeRunLock.test_spawned_child_does_not_pin_lock
        # for why this is load-bearing, not cosmetic). The wedge-restart
        # lines in input_probe_check spawn the desktop lifecycle too, so
        # they are covered by the same rule.
        src = open(KEEPALIVE_SH).read()
        spawns = [ln for ln in src.splitlines()
                  if not ln.lstrip().startswith("#")
                  and (("cua-desktop.sh" in ln
                        and ("start" in ln or "stop" in ln))
                       or "cua-bridge.py" in ln)]
        assert len(spawns) == 4, f"expected 4 spawn lines, got: {spawns}"
        for ln in spawns:
            assert "9>&-" in ln, f"spawn line does not close fd 9: {ln}"

    def test_status_failure_is_not_all_up(self):
        # A status probe that fails or prints nothing (e.g. the rundir
        # guard refusing an untrusted stack) must count as DOWN, never as
        # "all up".
        src = open(KEEPALIVE_SH).read()
        assert 'status_out="[down]"' in src or "status_out='[down]'" in src
        assert '[ -z "$status_out" ]' in src

    def test_bridge_liveness_uses_dedicated_endpoint(self):
        # #784: the bridge-liveness curl must probe /api/liveness — the
        # cheap endpoint with no driver subprocess — not /api/status,
        # whose 10s `cua-driver status` budget could false-trip the 5s
        # curl budget into a spurious bridge restart. The probe-fetch curl
        # (15s, ?probe=1) legitimately keeps /api/status for its detail.
        src = open(KEEPALIVE_SH).read()
        liveness = [ln for ln in src.splitlines()
                    if "curl" in ln and "max-time 5" in ln
                    and "18731" in ln
                    and not ln.lstrip().startswith("#")]
        assert len(liveness) == 1, f"expected 1 liveness curl, got: {liveness}"
        assert "/api/liveness" in liveness[0]
        assert "/api/status" not in liveness[0]
        # The liveness curl is the keepalive's ONLY bridge-restart decision:
        # a second restart-branch curl (any budget) hitting /api/status
        # would reintroduce the false-trip through the back door.
        restart_branches = [
            ln for ln in src.splitlines()
            if "curl" in ln and "18731" in ln
            and not ln.lstrip().startswith("#")
            and "probe=1" not in ln]
        assert len(restart_branches) == 1, \
            f"expected 1 restart-decision curl, got: {restart_branches}"


_FAKE_BRIDGE_PY = r'''
import http.server, json, os
STATE_FILE = os.environ["FAKE_BRIDGE_STATE_FILE"]

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            with open(STATE_FILE) as f:
                content = f.read()
        except OSError:
            content = ""
        if content.startswith("RAW:"):
            # Serve the remainder verbatim — garbage for the
            # unparseable-path tests.
            body = content[4:].encode()
        else:
            state = content.strip() or "unknown"
            body = json.dumps({"ok": True, "detail": "driver ok",
                               "input": {"state": state, "detail": "test",
                                         "checked_at": 123,
                                         "driver": "test"}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
print(srv.server_address[1], flush=True)
srv.serve_forever()
'''


@pytest.fixture()
def fake_bridge():
    # Yields (url, set_state); the server reads its verdict from a
    # file on every request so one server serves many verdicts. A state
    # file starting with "RAW:" serves the remainder verbatim instead of
    # JSON (for the unparseable-path tests).
    with tempfile.TemporaryDirectory() as t:
        state_file = os.path.join(t, "verdict")
        with open(state_file, "w") as f:
            f.write("unknown")
        server_py = os.path.join(t, "server.py")
        with open(server_py, "w") as f:
            f.write(_FAKE_BRIDGE_PY)
        proc = subprocess.Popen(
            ["python3", server_py], stdout=subprocess.PIPE, text=True,
            env={**os.environ, "FAKE_BRIDGE_STATE_FILE": state_file})
        try:
            port = proc.stdout.readline().strip()
            assert port.isdigit(), f"fake bridge did not print a port: {port!r}"
            yield (f"http://127.0.0.1:{port}",
                   lambda v: open(state_file, "w").write(v))
        finally:
            proc.terminate()
            proc.wait(timeout=10)


class TestInputProbeCheck:
    """Behavioral tests for the keepalive's input-probe supervision (#769).

    The guard is extracted from the real cua-keepalive.sh and run against
    a fake bridge (a real local HTTP server serving canned /api/status
    JSON, verdict driven by a file the test rewrites between runs) and a
    fake HOME whose cua-desktop.sh only records its invocations — the
    real daemons are never touched.
    """

    @pytest.fixture()
    def guard(self):
        return extract_function(KEEPALIVE_SH, "input_probe_check")

    @pytest.fixture()
    def fake_home(self):
        # A fake HOME with a recording cua-desktop.sh stand-in.
        with tempfile.TemporaryDirectory() as t:
            bindir = os.path.join(t, "cua", "bin")
            os.makedirs(bindir)
            calls = os.path.join(t, "calls")
            desktop = os.path.join(bindir, "cua-desktop.sh")
            with open(desktop, "w") as f:
                f.write("#!/bin/bash\necho \"$1\" >> \"$CALLS_FILE\"\n")
            os.chmod(desktop, 0o755)
            yield t, calls

    def _run(self, guard, tmpdir, url, env_extra=None, state_dir=None):
        env = {"CUA_KEEPALIVE_PROBE_INTERVAL_S": "0",
               **(env_extra or {})}
        call = (f'input_probe_check "{state_dir or tmpdir}" "{url}"; '
                f'echo "RC=$?"')
        return run_guard(guard, call, env=env)

    @staticmethod
    def _state(tmpdir):
        out = {}
        with open(os.path.join(tmpdir, "cua-input-probe.state")) as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                out[k] = v
        return out

    @staticmethod
    def _history(tmpdir):
        with open(os.path.join(tmpdir, "cua-input-probe.log")) as f:
            return [ln.strip() for ln in f if ln.strip()]

    def test_records_verdict_state_and_history(self, guard, fake_bridge):
        url, set_state = fake_bridge
        set_state("ok")
        with tempfile.TemporaryDirectory() as t:
            r = self._run(guard, t, url)
            assert r.returncode == 0, r.stderr
            assert "RC=0" in r.stdout
            hist = self._history(t)
            assert len(hist) == 1
            assert hist[0].endswith(" ok consecutive=0"), hist
            st = self._state(t)
            assert st["last_state"] == "ok"
            assert st["consecutive_wedged"] == "0"
            assert st["last_check"].isdigit()

    def test_wedged_increments_ok_resets_unknown_holds(self, guard,
                                                       fake_bridge):
        # wedged increments; ok resets; unknown (inconclusive) leaves the
        # counter alone — the fail-safe direction per #492.
        url, set_state = fake_bridge
        with tempfile.TemporaryDirectory() as t:
            set_state("wedged")
            self._run(guard, t, url)
            self._run(guard, t, url)
            assert self._state(t)["consecutive_wedged"] == "2"
            set_state("unknown")
            self._run(guard, t, url)
            assert self._state(t)["consecutive_wedged"] == "2"
            assert self._state(t)["last_state"] == "unknown"
            set_state("ok")
            self._run(guard, t, url)
            assert self._state(t)["consecutive_wedged"] == "0"

    def test_restart_gate_off_by_default(self, guard, fake_bridge,
                                         fake_home):
        # Three consecutive wedges with the gate unset must NOT restart
        # the stack — the probe is new and unproven in production, so the
        # default only builds history (#769).
        home, calls = fake_home
        url, set_state = fake_bridge
        set_state("wedged")
        with tempfile.TemporaryDirectory() as t:
            for _ in range(3):
                r = self._run(guard, t, url, env_extra={"HOME": home,
                                                       "CALLS_FILE": calls})
                assert r.returncode == 0, r.stderr
            assert not os.path.exists(calls), \
                "desktop stack restarted with the gate off"
            assert self._state(t)["consecutive_wedged"] == "3"

    def test_restart_gate_on_restarts_once_with_cooldown(self, guard,
                                                         fake_bridge,
                                                         fake_home):
        # Gate open: the threshold-many-eth consecutive wedge restarts
        # (stop+start); the counter resets, and a further wedge inside
        # the cooldown does NOT restart again (no restart storm on a
        # persistently-wedged Xvfb).
        #
        # Threshold is pinned to 1 here so the second run's restart is
        # blocked by the COOLDOWN check, not the threshold check: with the
        # default threshold=3 the post-restart counter (reset to 0) never
        # reaches the cooldown condition, so a deleted/inverted cooldown
        # would sail through the test unnoticed (found by Engineering's
        # mutation testing on the review).
        home, calls = fake_home
        url, set_state = fake_bridge
        set_state("wedged")
        env = {"HOME": home, "CALLS_FILE": calls,
               "CUA_KEEPALIVE_WEDGE_RESTART": "1",
               "CUA_KEEPALIVE_WEDGE_THRESHOLD": "1"}
        with tempfile.TemporaryDirectory() as t:
            # Run 1: consecutive=1 >= 1, no prior restart -> restart.
            self._run(guard, t, url, env_extra=env)
            with open(calls) as f:
                invocations = [ln.strip() for ln in f if ln.strip()]
            assert invocations == ["stop", "start"], invocations
            st = self._state(t)
            assert st["consecutive_wedged"] == "0"
            assert st["last_restart"].isdigit()
            # Run 2: consecutive=1 >= 1 again, but inside the 1h cooldown
            # since run 1's restart -> no second restart.
            self._run(guard, t, url, env_extra=env)
            with open(calls) as f:
                invocations = [ln.strip() for ln in f if ln.strip()]
            assert invocations == ["stop", "start"], invocations

    def test_probe_throttled_by_interval(self, guard, fake_bridge):
        # With a 1h interval, the second immediate run skips the probe —
        # no second fetch, no second history line.
        url, set_state = fake_bridge
        set_state("ok")
        with tempfile.TemporaryDirectory() as t:
            env = {"CUA_KEEPALIVE_PROBE_INTERVAL_S": "3600"}
            self._run(guard, t, url, env_extra=env)
            self._run(guard, t, url, env_extra=env)
            assert len(self._history(t)) == 1

    def test_bridge_unreachable_is_quiet(self, guard):
        # A down bridge belongs to the liveness block above, not to the
        # probe — the check must fail soft (rc 0, a stderr note, no state
        # corruption, no history line for a probe that never ran).
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        dead_url = f"http://127.0.0.1:{s.getsockname()[1]}"
        s.close()
        with tempfile.TemporaryDirectory() as t:
            r = self._run(guard, t, dead_url)
            assert r.returncode == 0, r.stderr
            assert "RC=0" in r.stdout
            assert "input probe fetch failed" in r.stderr
            assert not os.path.exists(
                os.path.join(t, "cua-input-probe.log"))

    def test_missing_python3_skips_loudly(self, guard, fake_bridge):
        # A minimal box without python3 must skip the check with a note,
        # never crash the keepalive run.
        if not shutil.which("curl"):
            pytest.skip("curl not installed")
        url, _ = fake_bridge
        with tempfile.TemporaryDirectory() as t:
            bindir = os.path.join(t, "nopython")
            os.makedirs(bindir)
            for tool in ("curl", "date", "mktemp", "mv"):
                src = shutil.which(tool)
                assert src, f"{tool} not installed"
                os.symlink(src, os.path.join(bindir, tool))
            env = {"PATH": bindir}
            r = self._run(guard, t, url, env_extra=env)
            assert r.returncode == 0, r.stderr
            assert "RC=0" in r.stdout
            assert "python3 missing" in r.stderr

    def test_unparseable_verdict_is_inconclusive(self, guard, fake_bridge,
                                                fake_home):
        # A bridge that answers with garbage (or a body that dies mid-parse)
        # must classify as "unparseable" — inconclusive, like "unknown": the
        # wedge counter neither increments nor resets, the honest verdict is
        # recorded in state and history, and even with the restart gate open
        # an unparseable verdict must NOT restart the desktop stack.
        home, calls = fake_home
        url, set_state = fake_bridge
        gate_on = {"HOME": home, "CALLS_FILE": calls,
                   "CUA_KEEPALIVE_WEDGE_RESTART": "1",
                   "CUA_KEEPALIVE_WEDGE_THRESHOLD": "1"}
        gate_off = {"HOME": home, "CALLS_FILE": calls}
        with tempfile.TemporaryDirectory() as t:
            # Gate off for the first wedge: build consecutive=1 without
            # triggering the restart the gate-on threshold=1 would fire.
            set_state("wedged")
            self._run(guard, t, url, env_extra=gate_off)
            assert self._state(t)["consecutive_wedged"] == "1"
            # Gate on: an unparseable verdict must still not restart, and
            # must leave the counter alone.
            set_state("RAW:this is not json{{{")
            r = self._run(guard, t, url, env_extra=gate_on)
            assert r.returncode == 0, r.stderr
            assert "RC=0" in r.stdout
            st = self._state(t)
            assert st["consecutive_wedged"] == "1"
            assert st["last_state"] == "unparseable"
            hist = self._history(t)
            assert len(hist) == 2
            assert hist[1].endswith(" unparseable consecutive=1"), hist
            assert not os.path.exists(calls), \
                "desktop stack restarted on an unparseable verdict"

    def test_bare_call_uses_home_cache_defaults(self, guard):
        # The production call site runs input_probe_check with NO args —
        # the defaults ($HOME/.cache for state, the real bridge URL for the
        # probe) must resolve correctly. Prove it behaviorally: a fresh
        # $HOME/.cache/cua-input-probe.state throttles the probe, so a bare
        # call under a temp HOME must never invoke curl — a shim on PATH
        # logs every curl invocation and then delegates to the real one —
        # must exit 0, and must write nothing. If the default state dir
        # broke, the call would miss the state file and reach for the
        # network: the shim log would be non-empty and the test fails.
        src = open(KEEPALIVE_SH).read()
        assert re.search(r"(?m)^input_probe_check$", src), \
            "production call site must invoke input_probe_check with no args"
        with tempfile.TemporaryDirectory() as home:
            cachedir = os.path.join(home, ".cache")
            os.makedirs(cachedir)
            with open(os.path.join(cachedir, "cua-input-probe.state"),
                      "w") as f:
                f.write(f"last_check={int(time.time())}\n")
            with tempfile.TemporaryDirectory() as shimdir:
                curl_log = os.path.join(shimdir, "curl.calls")
                real_curl = shutil.which("curl")
                assert real_curl, "curl not installed"
                with open(os.path.join(shimdir, "curl"), "w") as f:
                    f.write("#!/bin/bash\n"
                            f'echo "curl $*" >> "{curl_log}"\n'
                            f'exec "{real_curl}" "$@"\n')
                os.chmod(os.path.join(shimdir, "curl"), 0o755)
                env = {"HOME": home,
                       "PATH": shimdir + ":" + os.environ["PATH"],
                       "CUA_KEEPALIVE_PROBE_INTERVAL_S": "3600"}
                r = run_guard(guard, 'input_probe_check; echo "RC=$?"',
                              env=env)
                assert r.returncode == 0, r.stderr
                assert "RC=0" in r.stdout
                assert not os.path.exists(curl_log), \
                    "bare call hit the network despite a fresh state file"
                assert not os.path.exists(
                    os.path.join(cachedir, "cua-input-probe.log")), \
                    "bare call wrote history despite being throttled"


class TestSurfaceInputProbe:
    """Behavioral tests for do_status's input-path surfacing (#769).

    The surfacing logic is extracted as surface_input_probe() from the
    real cua-desktop.sh (extraction fails loudly if the function goes
    missing) and run against the fake bridge: every bridge verdict must
    render in the documented status vocabulary, and a garbage or
    unreachable bridge must stay silent without breaking the status
    command.
    """

    @pytest.fixture()
    def guard(self):
        return extract_function(DESKTOP_SH, "surface_input_probe")

    def _run(self, guard, url):
        return run_guard(guard, f'surface_input_probe "{url}"; echo "RC=$?"')

    def test_maps_verdicts_to_vocabulary(self, guard, fake_bridge):
        url, set_state = fake_bridge
        expected = {
            "ok": "[ok] input path (XTEST probe)",
            "wedged": "[wedged] input path (XTEST probe) \u2014 remediate: "
                      "cua-desktop.sh stop && cua-desktop.sh start",
            "unknown": "[unknown] input path (probe not run yet or "
                       "inconclusive)",
        }
        for verdict, line in expected.items():
            set_state(verdict)
            r = self._run(guard, url)
            assert r.returncode == 0, r.stderr
            assert "RC=0" in r.stdout
            assert line in r.stdout, (verdict, r.stdout)

    def test_garbage_body_prints_nothing(self, guard, fake_bridge):
        url, set_state = fake_bridge
        set_state("RAW:not json at all{{{")
        r = self._run(guard, url)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "RC=0", r.stdout

    def test_unreachable_bridge_prints_nothing(self, guard):
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        dead_url = f"http://127.0.0.1:{s.getsockname()[1]}"
        s.close()
        r = self._run(guard, dead_url)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "RC=0", r.stdout

    def test_do_status_wires_the_surfacing(self):
        # do_status must invoke the surfacing function with no args — the
        # behavioral tests above run against the extracted function, so a
        # deleted call site would otherwise pass them all.
        body = extract_function(DESKTOP_SH, "do_status")
        assert re.search(r"(?m)^\s*surface_input_probe\s*$", body), \
            "do_status no longer calls surface_input_probe"
