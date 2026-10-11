"""Tests for scripts/self_update.py (issue #532, slice S1).

Probes are pure reads, so they are tested with injected fake `which` and
`runner` callables — no real tools, no PATH dependence, no network.
"""

import hashlib
import io
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import self_update  # noqa: E402


def fake_which(mapping):
    def which(binary):
        return mapping.get(binary)
    return which


def fake_runner(responses):
    """responses: {argv_tuple: (rc, stdout, stderr)}.
    Unknown argv -> (127, '', '')."""
    def runner(argv, timeout=10):
        return responses.get(tuple(argv), (127, "", ""))
    return runner


def raising_runner(argv, timeout=10):
    raise OSError("boom")


# --- inventory shape -------------------------------------------------------

def test_status_returns_all_registered_probes():
    records = self_update.status()
    assert len(records) == len(self_update.PROBES)
    assert [r["tool"] for r in records] == [n for n, _, _ in self_update.PROBES]
    for r in records:
        assert set(r) == {"tool", "scope", "installed", "version",
                          "pinned", "drift", "note"}
        assert isinstance(r["installed"], bool)
        assert isinstance(r["drift"], bool)


def test_status_never_raises_even_when_everything_is_missing():
    records = self_update.status()
    assert records  # non-empty even on a bare box


def test_run_probe_catches_probe_exceptions():
    def bad_probe():
        raise RuntimeError("probe exploded")
    r = self_update.run_probe("docker", bad_probe, {})
    assert r["installed"] is False
    assert "probe error" in r["note"]
    assert r["drift"] is False


# --- binary version probes -------------------------------------------------

def test_binary_probe_missing_from_path():
    installed, version, note = self_update.probe_docker(
        which=fake_which({}), runner=fake_runner({}))
    assert installed is False
    assert version is None
    assert "PATH" in note


def test_docker_version_parsed():
    runner = fake_runner({("docker", "--version"):
                          (0, "Docker version 27.5.1, build 9f78933\n", "")})
    installed, version, note = self_update.probe_docker(
        which=fake_which({"docker": "/usr/bin/docker"}), runner=runner)
    assert installed is True
    assert version == "27.5.1"


def test_pattern_fallback_keeps_whole_first_line():
    runner = fake_runner({("gh", "--version"):
                          (0, "some-unexpected-format 1.2\nsecond line\n", "")})
    installed, version, _ = self_update.probe_gh(
        which=fake_which({"gh": "/usr/bin/gh"}), runner=runner)
    assert installed is True
    assert version == "some-unexpected-format 1.2"


def test_version_query_failure_still_counts_as_installed():
    runner = fake_runner({("node", "--version"): (1, "", "")})
    installed, version, note = self_update.probe_node(
        which=fake_which({"node": "/usr/bin/node"}), runner=runner)
    assert installed is True
    assert version is None
    assert "failed" in note


def test_runner_exception_becomes_not_found():
    installed, version, _ = self_update.probe_gh(
        which=fake_which({"gh": "/usr/bin/gh"}), runner=raising_runner)
    assert installed is True  # binary exists; query failed gracefully
    assert version is None


def test_stderr_noise_does_not_pollute_version():
    # B1: warnings merged into the version string must not happen; stdout
    # wins, stderr is only a fallback.
    runner = fake_runner({("gh", "--version"):
                          (0, "gh version 2.101.0\n",
                           "DeprecationWarning: pkg_resources is deprecated\n")})
    installed, version, _ = self_update.probe_gh(
        which=fake_which({"gh": "/usr/bin/gh"}), runner=runner)
    assert installed is True
    assert version == "2.101.0"


def test_stderr_noise_does_not_pollute_patternless_probe_version():
    # B1, second guard: the stdout-first preference must also hold on the
    # pattern-less path (_probe_python_package), where _version_output's
    # choice is NOT rescued by the pattern-scan loop. This test fails if
    # _version_output ever prefers stderr; the pattern-based test above
    # cannot catch that mutation.
    probe_cmd = (sys.executable, "-c",
                 "import importlib.metadata as m; print(m.version('playwright'))")
    runner = fake_runner({probe_cmd:
                          (0, "1.49.1\n",
                           "DeprecationWarning: pkg_resources is deprecated\n")})
    installed, version, _ = self_update.probe_playwright(
        runner=runner, which=fake_which({"python3": sys.executable}))
    assert installed is True
    assert version == "1.49.1"


def test_version_falls_back_to_stderr_when_stdout_empty():
    runner = fake_runner({("gh", "--version"): (0, "", "gh version 2.101.0\n")})
    installed, version, _ = self_update.probe_gh(
        which=fake_which({"gh": "/usr/bin/gh"}), runner=runner)
    assert installed is True
    assert version == "2.101.0"


# --- python package probes -------------------------------------------------

def test_playwright_probe_reports_real_package_or_clean_miss():
    installed, version, note = self_update.probe_playwright()
    # Either is fine on any box; the point is the shape never breaks.
    assert isinstance(installed, bool)
    if installed:
        assert version and version[0].isdigit()


def test_playwright_probe_prefers_managed_venv(tmp_path):
    # F-A1: the probe must target the managed venv's python (the artifact
    # the update plane converges), not the PATH python3. `managed` is the
    # venv dir; the probe runs <venv>/bin/python.
    venv = tmp_path / "pw"
    (venv / "bin").mkdir(parents=True)
    venv_py = venv / "bin" / "python"
    venv_py.write_text("#!/bin/sh\n")
    venv_py.chmod(0o755)
    seen = {}
    def runner(argv, timeout=10):
        seen["argv"] = argv
        return 0, "1.62.0\n", ""
    installed, version, note = self_update.probe_playwright(
        runner=runner, which=fake_which({"python3": "/usr/bin/python3"}),
        managed=str(venv))
    assert seen["argv"][0] == str(venv_py)
    assert installed is True
    assert version == "1.62.0"
    assert str(venv_py) in note


def test_playwright_probe_falls_back_to_path_python3(tmp_path):
    # F-A1: on a box the updater never managed (no venv), the PATH python3
    # probe still reports — the inventory stays useful everywhere.
    seen = {}
    def runner(argv, timeout=10):
        seen["argv"] = argv
        return 0, "1.49.1\n", ""
    installed, version, note = self_update.probe_playwright(
        runner=runner, which=fake_which({"python3": "/usr/bin/python3"}),
        managed=str(tmp_path / "no-such-venv"))
    assert seen["argv"][0] == "/usr/bin/python3"
    assert installed is True
    assert version == "1.49.1"
    assert "/usr/bin/python3" in note


def test_playwright_managed_non_executable_falls_back(tmp_path):
    # A managed target that exists but is not executable is not trusted —
    # fall back to PATH rather than probing a dud.
    venv = tmp_path / "pw"
    (venv / "bin").mkdir(parents=True)
    venv_py = venv / "bin" / "python"
    venv_py.write_text("#!/bin/sh\n")
    venv_py.chmod(0o644)  # exists but not executable
    seen = {}
    def runner(argv, timeout=10):
        seen["argv"] = argv
        return 0, "1.49.1\n", ""
    installed, _, _ = self_update.probe_playwright(
        runner=runner, which=fake_which({"python3": "/usr/bin/python3"}),
        managed=str(venv))
    assert seen["argv"][0] == "/usr/bin/python3"
    assert installed is True


# --- cua-driver probes (managed binary, F-A1) --------------------------------

def test_cua_driver_probe_prefers_managed_binary(tmp_path):
    # F-A1: the probe must target the managed binary (the artifact the
    # update plane converges and the pin holds), never PATH, when it exists.
    managed = tmp_path / "cua-driver"
    managed.write_text("#!/bin/sh\n")
    managed.chmod(0o755)
    runner = fake_runner({(str(managed), "--version"):
                          (0, "cua-driver 0.28.2\n", "")})
    installed, version, note = self_update.probe_cua_driver(
        which=fake_which({"cua-driver": "/usr/bin/cua-driver"}),
        runner=runner, managed=str(managed))
    assert installed is True
    assert version == "0.28.2"
    assert str(managed) in note


def test_cua_driver_probe_falls_back_to_path(tmp_path):
    # On a box the updater never managed, the PATH probe still reports.
    runner = fake_runner({("cua-driver", "--version"):
                          (0, "cua-driver 0.28.2\n", "")})
    installed, version, note = self_update.probe_cua_driver(
        which=fake_which({"cua-driver": "/usr/bin/cua-driver"}),
        runner=runner, managed=str(tmp_path / "no-such-binary"))
    assert installed is True
    assert version == "0.28.2"
    assert "cua-driver --version" in note


def test_cua_driver_managed_failure_still_counts_as_installed(tmp_path):
    # A present-but-broken managed binary reports installed with no version
    # (same never-raise contract as the PATH probe).
    managed = tmp_path / "cua-driver"
    managed.write_text("#!/bin/sh\n")
    managed.chmod(0o755)
    runner = fake_runner({})
    installed, version, note = self_update.probe_cua_driver(
        which=fake_which({}), runner=runner, managed=str(managed))
    assert installed is True
    assert version is None
    assert "failed" in note


def test_managed_defaults_honor_env_overrides(monkeypatch):
    # The managed defaults honor the update plane's CUA_DRIVER_BIN /
    # PLAYWRIGHT_VENV overrides so the two planes keep agreeing when the
    # operator relocates the managed locations. The binding is at import
    # time, so this reloads the module under the overridden env.
    import importlib
    monkeypatch.setenv("CUA_DRIVER_BIN", "/opt/custom/cua-driver")
    monkeypatch.setenv("PLAYWRIGHT_VENV", "/opt/custom/pw")
    try:
        reloaded = importlib.reload(self_update)
        assert reloaded._MANAGED_CUA_DRIVER == "/opt/custom/cua-driver"
        assert reloaded._MANAGED_PLAYWRIGHT_VENV == "/opt/custom/pw"
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


# --- playwright browsers ---------------------------------------------------

def test_playwright_browsers_missing_cache(tmp_path):
    installed, version, note = self_update.probe_playwright_browsers(
        home=str(tmp_path))
    assert installed is False
    assert version is None


def test_playwright_browsers_lists_builds(tmp_path):
    cache = tmp_path / ".cache" / "ms-playwright"
    (cache / "chromium-1181").mkdir(parents=True)
    (cache / "firefox-1490").mkdir(parents=True)
    (cache / ".links").mkdir(parents=True)  # Playwright internal, not a build
    installed, version, note = self_update.probe_playwright_browsers(
        home=str(tmp_path))
    assert installed is True
    assert version == "2 build(s)"
    assert "chromium-1181" in note and "firefox-1490" in note


# --- unattended-upgrades ---------------------------------------------------

def _uu_which_runner(conf_dir, version_out=(0, "2.10.2\n", ""), tmp_path=None):
    which = fake_which({"unattended-upgrade": "/usr/bin/unattended-upgrade",
                        "dpkg-query": "/usr/bin/dpkg-query"})
    runner = fake_runner({
        ("dpkg-query", "-W", "-f=${Version}", "unattended-upgrades"):
            version_out})
    return which, runner


def test_unattended_upgrades_enabled(tmp_path):
    conf = tmp_path / "20auto-upgrades"
    conf.write_text('APT::Periodic::Update-Package-Lists "1";\n'
                    'APT::Periodic::Unattended-Upgrade "1";\n')
    which, runner = _uu_which_runner(tmp_path)
    installed, version, note = self_update.probe_unattended_upgrades(
        which=which, runner=runner, conf_paths=(str(conf),))
    assert installed is True
    assert version == "2.10.2"
    assert "ENABLED" in note


def test_unattended_upgrades_disabled(tmp_path):
    conf = tmp_path / "20auto-upgrades"
    conf.write_text('APT::Periodic::Unattended-Upgrade "0";\n')
    which, runner = _uu_which_runner(tmp_path)
    installed, _, note = self_update.probe_unattended_upgrades(
        which=which, runner=runner, conf_paths=(str(conf),))
    assert installed is True
    assert "DISABLED" in note


def test_unattended_upgrades_commented_directive_is_not_enabled(tmp_path):
    # B2: `// APT::Periodic::Unattended-Upgrade "1";` must not count.
    conf = tmp_path / "20auto-upgrades"
    conf.write_text('// APT::Periodic::Unattended-Upgrade "1";\n'
                    '# APT::Periodic::Unattended-Upgrade "1";\n')
    which, runner = _uu_which_runner(tmp_path)
    installed, _, note = self_update.probe_unattended_upgrades(
        which=which, runner=runner, conf_paths=(str(conf),))
    assert installed is True
    assert "DISABLED" in note


def test_unattended_upgrades_missing_binary():
    installed, version, _ = self_update.probe_unattended_upgrades(
        which=fake_which({}), runner=fake_runner({}))
    assert installed is False
    assert version is None


def test_unattended_upgrades_dpkg_query_failure(tmp_path):
    conf = tmp_path / "20auto-upgrades"
    conf.write_text('APT::Periodic::Unattended-Upgrade "1";\n')
    which, runner = _uu_which_runner(tmp_path, version_out=(1, "", ""))
    installed, version, note = self_update.probe_unattended_upgrades(
        which=which, runner=runner, conf_paths=(str(conf),))
    assert installed is True
    assert version is None  # package query failed; config still readable
    assert "ENABLED" in note


def test_unattended_upgrades_unreadable_config(tmp_path):
    which, runner = _uu_which_runner(tmp_path)
    installed, _, note = self_update.probe_unattended_upgrades(
        which=which, runner=runner,
        conf_paths=(str(tmp_path / "no-such.conf"),))
    assert installed is True
    assert note == "config unreadable"


def test_unattended_upgrades_first_conf_missing_falls_through(tmp_path):
    conf = tmp_path / "10periodic"
    conf.write_text('APT::Periodic::Unattended-Upgrade "1";\n')
    which, runner = _uu_which_runner(tmp_path)
    installed, _, note = self_update.probe_unattended_upgrades(
        which=which, runner=runner,
        conf_paths=(str(tmp_path / "no-such.conf"), str(conf)))
    assert "ENABLED" in note


# --- snap ------------------------------------------------------------------

def test_snap_list_parsed():
    out = ("Name    Version   Rev   Tracking       Publisher   Notes\n"
           "core22  20250101  1234  latest/stable  canonical✓  base\n"
           "lxd     5.21      5678  latest/stable  canonical✓  -\n")
    runner = fake_runner({("snap", "list"): (0, out, "")})
    installed, version, note = self_update.probe_snap(
        which=fake_which({"snap": "/usr/bin/snap"}), runner=runner)
    assert installed is True
    assert version == "2 snap(s)"
    assert "core22" in note and "lxd" in note


def test_snap_missing():
    installed, version, _ = self_update.probe_snap(
        which=fake_which({}), runner=fake_runner({}))
    assert installed is False


# --- pins / drift ----------------------------------------------------------

def test_load_pins_parses_file(tmp_path):
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text("# comment\n\ncua-driver = 0.28.2\nblender=5.2.2\n"
                         "bad-line-without-equals\n")
    pins = self_update.load_pins(str(pins_file))
    assert pins == {"cua-driver": "0.28.2", "blender": "5.2.2"}


def test_load_pins_missing_file_returns_empty(tmp_path):
    assert self_update.load_pins(str(tmp_path / "nope.conf")) == {}


def test_load_pins_survives_malformed_bytes(tmp_path):
    # B2: a pins file with non-UTF-8 bytes must not crash load_pins — the
    # status inventory's contract is "probes never raise, always exits 0".
    # Non-decodable bytes are replaced (same defensive pattern as
    # probe_unattended_upgrades); the garbage line is skipped and
    # well-formed lines still parse.
    pins_file = tmp_path / "pins.conf"
    pins_file.write_bytes(b"\xff\xfe not-utf8\nplaywright=1.49.1\n")
    pins = self_update.load_pins(str(pins_file))
    assert pins == {"playwright": "1.49.1"}


def test_drift_true_when_version_differs_from_pin():
    def probe():
        return True, "27.5.1", "ok"
    r = self_update.run_probe("docker", probe, {"docker": "99.0"})
    assert r["drift"] is True
    assert r["pinned"] == "99.0"


def test_no_drift_when_versions_match():
    def probe():
        return True, "0.28.2", "ok"
    r = self_update.run_probe("cua-driver", probe, {"cua-driver": "0.28.2"})
    assert r["drift"] is False


def test_drift_fires_when_version_unverifiable_against_pin():
    # B3: a pin naming a presence-only probe (cred/swapd report version None)
    # must be loud, not silently ignored.
    def probe():
        return True, None, "installed at /x (no version flag)"
    r = self_update.run_probe("cred", probe, {"cred": "1.0"})
    assert r["drift"] is True
    assert "unverifiable" in r["note"]


def test_no_drift_without_pin_or_when_missing():
    def probe():
        return True, "1.0", "ok"
    assert self_update.run_probe("docker", probe, {})["drift"] is False

    def missing():
        return False, None, "nope"
    r = self_update.run_probe("docker", missing, {"docker": "1.0"})
    assert r["drift"] is False


# --- spark-vm agent components ----------------------------------------------

def test_cred_probe_presence_only():
    installed, version, note = self_update.probe_cred(
        which=fake_which({"cred": "/usr/local/bin/cred"}))
    assert installed is True
    assert version is None
    assert "no version flag" in note


def test_cred_probe_missing():
    installed, version, _ = self_update.probe_cred(which=fake_which({}))
    assert installed is False
    assert version is None


def test_swapd_probe_user_present():
    runner = fake_runner({("id", "-u", "swapd"): (0, "999\n", "")})
    installed, version, note = self_update.probe_swapd(
        which=fake_which({"id": "/usr/bin/id"}), runner=runner)
    assert installed is True
    assert version is None
    assert "swapd system user present" in note


def test_swapd_probe_user_absent():
    runner = fake_runner({("id", "-u", "swapd"): (1, "", "")})
    installed, version, _ = self_update.probe_swapd(
        which=fake_which({"id": "/usr/bin/id"}), runner=runner)
    assert installed is False


def test_muse_job_version():
    runner = fake_runner({("muse-job", "--version"): (0, "0.4.0\n", "")})
    installed, version, _ = self_update.probe_muse_job(
        which=fake_which({"muse-job": "/usr/local/bin/muse-job"}),
        runner=runner)
    assert installed is True
    assert version == "0.4.0"


# --- spark-vm own version --------------------------------------------------

def test_probe_sparkvm_reads_repo_version():
    installed, version, note = self_update.probe_sparkvm()
    assert installed is True
    assert version and version[0].isdigit()  # real semver from VERSION


# --- CLI -------------------------------------------------------------------

def test_status_table_output(capsys):
    rc = self_update.main(["status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "TOOL" in out and "INSTALLED" in out and "VERSION" in out
    for name, _, _ in self_update.PROBES:
        assert name in out


def test_status_json_output(capsys):
    rc = self_update.main(["status", "--json"])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["slice"] == "S1-status"
    assert len(doc["tools"]) == len(self_update.PROBES)
    assert all("tool" in t for t in doc["tools"])


def test_status_uses_custom_pins_file(tmp_path, capsys):
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text("spark-vm = 9.9.9\n")
    rc = self_update.main(["status", "--pins", str(pins_file)])
    assert rc == 0
    assert "DRIFT" in capsys.readouterr().out  # real VERSION != 9.9.9


# --- unknown-pin warnings (dead config must be loud) -------------------------


def test_pin_warnings_flags_unknown_names():
    pins = {"docker": "27.5.1", "doker": "27.5.1", "nobe": "1.0"}
    assert self_update.pin_warnings(pins) == ["doker", "nobe"]


def test_pin_warnings_empty_when_all_known():
    assert self_update.pin_warnings({"docker": "27.5.1"}) == []
    assert self_update.pin_warnings({}) == []


def test_status_table_warns_on_unknown_pin(tmp_path, capsys):
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text("docker = 27.5.1\ndoker = 27.5.1\n")
    rc = self_update.main(["status", "--pins", str(pins_file)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "unmatched pins (no such probe): doker" in out


def test_status_json_warns_on_unknown_pin(tmp_path, capsys):
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text("docker = 27.5.1\ndoker = 27.5.1\n")
    rc = self_update.main(["status", "--json", "--pins", str(pins_file)])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["pin_warnings"] == ["doker"]


def test_status_json_no_warnings_when_all_known(tmp_path, capsys):
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text("docker = 27.5.1\n")
    rc = self_update.main(["status", "--json", "--pins", str(pins_file)])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["pin_warnings"] == []


# --- duplicate pins (F-A2: first-wins must agree across planes) ---------------

def test_load_pins_first_occurrence_wins(tmp_path):
    # _read_pin in deploy/toolset-update.sh is first-wins; load_pins must
    # agree, or the two planes read different pins from the same file.
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text("cua-driver = 0.28.2\ncua-driver = 0.29.0\n")
    assert self_update.load_pins(str(pins_file)) == {"cua-driver": "0.28.2"}


def test_read_pin_agrees_with_load_pins_on_whitespace(tmp_path):
    # Issue #1314 (F-A2): the shell _read_pin deleted ALL whitespace
    # (tr -d ' \t') while load_pins strips only the edges (str.strip()).
    # For every line in the pins file, the shell's parsed value must equal
    # the status plane's — interior whitespace included — so the two planes
    # never report different pins from the same file.
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text(
        "# comment\n"
        "\n"
        "cua-driver = 0.28.2\n"
        "foo = 1.2 beta\n"
        "bar = 0.9.0 \n"
        "\t baz \t = \t 3.3.3 \t\n"
        "   # indented = not-a-pin\n"
    )
    want = self_update.load_pins(str(pins_file))
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env = dict(os.environ, LC_ALL="C")  # pin [[:space:]] to ASCII parity
    for name, value in want.items():
        proc = subprocess.run(
            ["bash", "-c",
             "export TOOLSET_UPDATE_NO_MAIN=1; "
             "source ./deploy/toolset-update.sh; "
             f'PINS_FILE="{pins_file}" _read_pin "{name}"'],
            cwd=repo, capture_output=True, text=True, timeout=60, env=env)
        assert proc.returncode == 0, name
        assert proc.stdout == value, (name, value, proc.stdout)
    assert want == {
        "cua-driver": "0.28.2",
        "foo": "1.2 beta",
        "bar": "0.9.0",
        "baz": "3.3.3",
    }


def test_read_pin_agrees_with_load_pins_on_real_pins_file():
    # Issue #1314 regression anchor: the parity claim must hold on the
    # real operator pins file, not just fixtures. Both planes read the
    # same values — a future _read_pin rewrite that silently diverges
    # from load_pins on real input fails here. Version-agnostic: asserts
    # agreement, not any particular pin.
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    pins_file = os.path.join(repo, "scripts", "self_update_pins.conf")
    want = self_update.load_pins(pins_file)
    assert want, "real pins file must define at least one pin"
    env = dict(os.environ, LC_ALL="C")
    for name, value in want.items():
        proc = subprocess.run(
            ["bash", "-c",
             "export TOOLSET_UPDATE_NO_MAIN=1; "
             "source ./deploy/toolset-update.sh; "
             f'PINS_FILE="{pins_file}" _read_pin "{name}"'],
            cwd=repo, capture_output=True, text=True, timeout=60, env=env)
        assert proc.returncode == 0, name
        assert proc.stdout == value, (name, value, proc.stdout)


def test_pin_duplicates_flags_repeated_names(tmp_path):
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text(
        "cua-driver = 0.28.2\ndocker = 27.5.1\ncua-driver = 0.29.0\n")
    assert self_update.pin_duplicates(str(pins_file)) == ["cua-driver"]


def test_pin_duplicates_empty_when_unique(tmp_path):
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text("cua-driver = 0.28.2\ndocker = 27.5.1\n")
    assert self_update.pin_duplicates(str(pins_file)) == []


def test_pin_duplicates_missing_file_returns_empty(tmp_path):
    assert self_update.pin_duplicates(str(tmp_path / "nope.conf")) == []


def test_status_table_and_json_surface_duplicates(tmp_path, capsys):
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text("docker = 27.5.1\ndocker = 26.1\n")
    rc = self_update.main(["status", "--pins", str(pins_file)])
    assert rc == 0
    assert "duplicate pins (later lines ignored): docker" in \
        capsys.readouterr().out
    rc = self_update.main(["status", "--json", "--pins", str(pins_file)])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["duplicate_pins"] == ["docker"]


def test_status_json_duplicate_pins_empty_when_unique(tmp_path, capsys):
    pins_file = tmp_path / "pins.conf"
    pins_file.write_text("docker = 27.5.1\n")
    rc = self_update.main(["status", "--json", "--pins", str(pins_file)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["duplicate_pins"] == []


# --- banner lines above the version line ------------------------------------


def test_pattern_scans_past_stdout_banner_lines():
    runner = fake_runner({("docker", "--version"):
                          (0, "Using Docker Engine API v1.47\n"
                              "Docker version 27.5.1, build 9f78933\n", "")})
    installed, version, _ = self_update.probe_docker(
        which=fake_which({"docker": "/usr/bin/docker"}), runner=runner)
    assert installed is True
    assert version == "27.5.1"  # banner must not become the version


def test_pattern_fallback_still_whole_first_line_without_any_match():
    runner = fake_runner({("docker", "--version"):
                          (0, "totally unexpected banner\nand more\n", "")})
    installed, version, _ = self_update.probe_docker(
        which=fake_which({"docker": "/usr/bin/docker"}), runner=runner)
    assert installed is True
    assert version == "totally unexpected banner"


# --- real timeout kill path --------------------------------------------------


def test_default_runner_kills_hanging_probe():
    import time
    start = time.monotonic()
    rc, stdout, stderr = self_update.default_runner(
        ["sleep", "30"], timeout=0.5)
    elapsed = time.monotonic() - start
    assert rc == 127  # timeout contract
    assert stdout == "" and stderr == ""
    assert elapsed < 5  # killed promptly, not left hanging


# --- snap edge cases ---------------------------------------------------------


def test_snap_list_failure_still_counts_installed():
    runner = fake_runner({("snap", "list"): (1, "", "boom")})
    installed, version, note = self_update.probe_snap(
        which=fake_which({"snap": "/usr/bin/snap"}), runner=runner)
    assert installed is True
    assert version is None
    assert "failed" in note


def test_snap_header_only_reports_zero():
    out = ("Name    Version   Rev   Tracking       Publisher   Notes\n")
    runner = fake_runner({("snap", "list"): (0, out, "")})
    installed, version, note = self_update.probe_snap(
        which=fake_which({"snap": "/usr/bin/snap"}), runner=runner)
    assert installed is True
    assert version == "0 snaps"


# --- installed-pins hash signal (issue #1313) --------------------------------


def _pins_with_hash(tmp_path, pins_text, hash_text):
    pins = tmp_path / "self_update_pins.conf"
    pins.write_text(pins_text)
    h = tmp_path / "self_update_pins.hash"
    h.write_text(hash_text)
    return str(pins), str(h)


def test_installed_pins_match_is_silent(tmp_path):
    # The privileged install published sha256(installed pins); the checkout
    # pins are identical — no warning.
    pins_text = "cua-driver = 0.28.2\n"
    pins, h = _pins_with_hash(
        tmp_path, pins_text, hashlib.sha256(pins_text.encode()).hexdigest())
    assert self_update.installed_pins_state(
        pins_path=pins, hash_path=h) == "match"


def test_installed_pins_mismatch_detected(tmp_path):
    # Pin bumped in the checkout, privileged install not re-run: the hash
    # (over the OLD installed pins) no longer matches — loud mismatch.
    pins_text = "cua-driver = 0.28.3\n"
    pins, h = _pins_with_hash(
        tmp_path, pins_text, hashlib.sha256(b"old installed pins").hexdigest())
    assert self_update.installed_pins_state(
        pins_path=pins, hash_path=h) == "mismatch"


def test_installed_pins_hash_absent_is_unknown(tmp_path):
    # Pre-#1313 installs publish no hash record: honest no-signal state,
    # silent by design — not an error, not a mismatch.
    pins = tmp_path / "self_update_pins.conf"
    pins.write_text("cua-driver = 0.28.2\n")
    assert self_update.installed_pins_state(
        pins_path=str(pins),
        hash_path=str(tmp_path / "missing.hash")) == "unknown"


def test_installed_pins_malformed_hash_is_unknown(tmp_path):
    # A corrupt authority record is indistinguishable from absent to the
    # unprivileged reader — unknown, not mismatch.
    pins, h = _pins_with_hash(tmp_path, "cua-driver = 0.28.2\n", "not-a-hash\n")
    assert self_update.installed_pins_state(
        pins_path=pins, hash_path=h) == "unknown"


def test_installed_pins_unreadable_is_unknown(tmp_path):
    # A valid hash record but an unreadable pins file (e.g. a directory):
    # unknown, not mismatch — the comparison cannot be computed.
    pins_text = "cua-driver = 0.28.2\n"
    pins, h = _pins_with_hash(
        tmp_path, pins_text, hashlib.sha256(pins_text.encode()).hexdigest())
    assert self_update.installed_pins_state(
        pins_path=str(tmp_path), hash_path=h) == "unknown"


def test_installed_pins_state_never_raises(tmp_path):
    # A hash path that is a directory (read fails) must not break status.
    assert self_update.installed_pins_state(
        pins_path=str(tmp_path), hash_path=str(tmp_path)) == "unknown"


def _status_main_with_hash(tmp_path, monkeypatch, capsys, pins_text,
                           hash_text, argv_extra=()):
    pins, h = _pins_with_hash(tmp_path, pins_text, hash_text)
    monkeypatch.setattr(self_update, "_PINS_HASH_FILE", h)
    rc = self_update.main(["status", "--pins", pins, *argv_extra])
    assert rc == 0
    return capsys.readouterr().out


def test_status_table_emits_mismatch_warning(tmp_path, monkeypatch, capsys):
    out = _status_main_with_hash(
        tmp_path, monkeypatch, capsys,
        "cua-driver = 0.28.3\n", hashlib.sha256(b"old pins").hexdigest())
    # Lock the full canonical wording — a drifted warning must be caught
    # here, not discovered by an operator squinting at output.
    assert self_update._PINS_MISMATCH_WARNING in out


def test_status_table_silent_on_match(tmp_path, monkeypatch, capsys):
    pins_text = "cua-driver = 0.28.2\n"
    out = _status_main_with_hash(
        tmp_path, monkeypatch, capsys, pins_text,
        hashlib.sha256(pins_text.encode()).hexdigest())
    assert "installed pins differ from checkout" not in out


def test_status_table_silent_when_hash_unknown(tmp_path, monkeypatch, capsys):
    # No hash record (pre-#1313 install): no warning — the no-signal state.
    pins = tmp_path / "self_update_pins.conf"
    pins.write_text("cua-driver = 0.28.2\n")
    monkeypatch.setattr(self_update, "_PINS_HASH_FILE",
                        str(tmp_path / "missing.hash"))
    rc = self_update.main(["status", "--pins", str(pins)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "installed pins differ from checkout" not in out


def test_status_json_carries_installed_pins_state(tmp_path, monkeypatch,
                                                  capsys):
    out = _status_main_with_hash(
        tmp_path, monkeypatch, capsys,
        "cua-driver = 0.28.3\n", hashlib.sha256(b"old pins").hexdigest(),
        argv_extra=("--json",))
    doc = json.loads(out)
    assert doc["installed_pins_state"] == "mismatch"
