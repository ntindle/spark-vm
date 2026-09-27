"""Tests for scripts/self_update.py (issue #532, slice S1).

Probes are pure reads, so they are tested with injected fake `which` and
`runner` callables — no real tools, no PATH dependence, no network.
"""

import io
import json
import os
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


def test_playwright_probe_uses_path_python3():
    # B4: the probe must target the box's canonical python3, not the
    # interpreter running this script.
    seen = {}
    def runner(argv, timeout=10):
        seen["argv"] = argv
        return 0, "1.49.1\n", ""
    installed, version, _ = self_update.probe_playwright(
        runner=runner, which=fake_which({"python3": "/usr/bin/python3"}))
    assert seen["argv"][0] == "/usr/bin/python3"
    assert installed is True
    assert version == "1.49.1"


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
