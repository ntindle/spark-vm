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


# --- managed-targets record (issue #1310) ----------------------------------

def _reload_with_record_env(monkeypatch, tmp_path, record_text=None,
                            extra_env=None, set_targets_file=True):
    # Helper: point MANAGED_TARGETS_FILE at an optional record (unless
    # set_targets_file=False, for testing the MANAGED_TARGETS_DIR
    # derivation), apply extra env, reload the module, return it. Caller
    # undoes via the yielded monkeypatch/finally pattern below.
    import importlib
    target = tmp_path / "managed_targets"
    if record_text is not None:
        target.write_text(record_text)
    if set_targets_file:
        monkeypatch.setenv("MANAGED_TARGETS_FILE", str(target))
    for k, v in (extra_env or {}).items():
        monkeypatch.setenv(k, v)
    return importlib.reload(self_update)


def test_managed_targets_record_preferred_over_env(monkeypatch, tmp_path):
    # #1310 core: the update plane publishes the targets it converges; the
    # status plane must prefer the record over the invoker's shell env —
    # otherwise an override set in only one environment silently retargets
    # S1 away from the artifacts the updater holds. (Vacuity: without the
    # record preference, the env values win and this fails.)
    import importlib
    try:
        reloaded = _reload_with_record_env(
            monkeypatch, tmp_path,
            "CUA_DRIVER_BIN=/srv/updater/cua-driver\n"
            "PLAYWRIGHT_VENV=/srv/updater/pw\n",
            extra_env={"CUA_DRIVER_BIN": "/opt/custom/cua-driver",
                       "PLAYWRIGHT_VENV": "/opt/custom/pw"})
        assert reloaded._MANAGED_CUA_DRIVER == "/srv/updater/cua-driver"
        assert reloaded._MANAGED_PLAYWRIGHT_VENV == "/srv/updater/pw"
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


def test_managed_targets_env_fallback_without_record(monkeypatch, tmp_path):
    # No record yet (pre-#1310 install): the env override still applies.
    import importlib
    try:
        reloaded = _reload_with_record_env(
            monkeypatch, tmp_path, record_text=None,
            extra_env={"CUA_DRIVER_BIN": "/opt/custom/cua-driver",
                       "PLAYWRIGHT_VENV": "/opt/custom/pw"})
        assert reloaded._MANAGED_CUA_DRIVER == "/opt/custom/cua-driver"
        assert reloaded._MANAGED_PLAYWRIGHT_VENV == "/opt/custom/pw"
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


def test_managed_targets_default_without_record_or_env(monkeypatch, tmp_path):
    # Neither record nor env: the compiled-in defaults (a box the updater
    # never managed).
    import importlib
    monkeypatch.delenv("CUA_DRIVER_BIN", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_VENV", raising=False)
    try:
        reloaded = _reload_with_record_env(monkeypatch, tmp_path)
        assert (reloaded._MANAGED_CUA_DRIVER ==
                "/home/ntindle/cua/bin/cua-driver")
        assert (reloaded._MANAGED_PLAYWRIGHT_VENV ==
                "/home/ntindle/.venvs/pw")
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


def test_managed_targets_malformed_record_ignored(monkeypatch, tmp_path):
    # Fail-closed: a record with relative values, unknown keys, and garbage
    # is ignored WHOLESALE — the parser requires the exact two-key set the
    # publisher always writes together, so a corrupt/torn record can never
    # contribute a half-trusted half. Both bindings fall back (env, then
    # default) as if no record existed. (Vacuity: if the parser accepted
    # partial records, the absolute PLAYWRIGHT_VENV line would win and this
    # fails.)
    import importlib
    try:
        reloaded = _reload_with_record_env(
            monkeypatch, tmp_path,
            "# comment\n"
            "\n"
            "CUA_DRIVER_BIN=relative/cua-driver\n"
            "PLAYWRIGHT_VENV=/srv/updater/pw\n"
            "SOME_OTHER_KEY=/whatever\n"
            "garbage without equals\n",
            extra_env={"CUA_DRIVER_BIN": "/opt/custom/cua-driver"})
        # cua-driver: record ignored -> env wins.
        assert reloaded._MANAGED_CUA_DRIVER == "/opt/custom/cua-driver"
        # playwright: record ignored wholesale (not partially trusted) ->
        # env unset -> default.
        assert (reloaded._MANAGED_PLAYWRIGHT_VENV ==
                "/home/ntindle/.venvs/pw")
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


def test_managed_targets_dir_derivation(monkeypatch, tmp_path):
    # The status plane mirrors the shell's derivation: MANAGED_TARGETS_FILE
    # unset + MANAGED_TARGETS_DIR set -> <dir>/managed_targets. (Vacuity:
    # without the derivation the hardcoded default wins and this fails.)
    import importlib
    monkeypatch.delenv("MANAGED_TARGETS_FILE", raising=False)
    try:
        reloaded = _reload_with_record_env(
            monkeypatch, tmp_path,
            "CUA_DRIVER_BIN=/srv/dir/cua-driver\n"
            "PLAYWRIGHT_VENV=/srv/dir/pw\n",
            extra_env={"MANAGED_TARGETS_DIR": str(tmp_path)},
            set_targets_file=False)
        assert reloaded._MANAGED_CUA_DRIVER == "/srv/dir/cua-driver"
        assert reloaded._MANAGED_PLAYWRIGHT_VENV == "/srv/dir/pw"
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


def test_managed_targets_partial_record_ignored(tmp_path):
    # A record with only one of the two keys (torn write, hand edit) is
    # ignored wholesale — the surviving half may itself be truncated.
    p = tmp_path / "managed_targets"
    p.write_text("CUA_DRIVER_BIN=/srv/updater/cua-driver\n")
    assert self_update._read_managed_targets_record(str(p)) == {}


def test_read_managed_targets_record_missing_file(tmp_path):
    # A missing record is not an error — it is the pre-#1310 state.
    assert (self_update._read_managed_targets_record(
        str(tmp_path / "no-such-file")) == {})


def test_read_managed_targets_record_non_utf8_ignored(tmp_path):
    # Non-UTF8 bytes must fail closed ({}), not raise UnicodeDecodeError
    # out of the import-time call and kill the whole status tool.
    # (Vacuity: with the OSError-only catch, this raises and the test
    # errors.)
    p = tmp_path / "managed_targets"
    p.write_bytes(b"CUA_DRIVER_BIN=/x\xff\nPLAYWRIGHT_VENV=/y\n")
    assert self_update._read_managed_targets_record(str(p)) == {}


def test_read_managed_targets_record_empty_and_directory(tmp_path):
    # Empty record and directory-as-record both read as {} (fail-closed
    # to env/default), pinning the IsADirectoryError path too.
    p = tmp_path / "managed_targets"
    p.write_text("")
    assert self_update._read_managed_targets_record(str(p)) == {}
    d = tmp_path / "dirrecord"
    d.mkdir()
    assert self_update._read_managed_targets_record(str(d)) == {}


def test_managed_targets_single_reader_registry():
    """Issue #1432: the `_publish_managed_targets` guard's exactness is
    DERIVED from the one and only runtime reader of the record —
    this module's `_read_managed_targets_record` (UTF-8 +
    `str.splitlines()`). The multi-byte-boundary matching (exact C2 85 /
    E2 80 A8 / E2 80 A9 sequences) and the lone-0x85 fail-closed
    argument hold only for that parser: a second reader with different
    splitting (e.g. a shell `while read` loop, which splits on `\\n`
    only) would silently invalidate the guard. This test is the
    registry: it fails when any new runtime file starts reading the
    record, forcing the guard to be re-derived for that reader before
    the new reader lands."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    readers = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        if rel.startswith(".git/"):
            continue
        if path.suffix not in {".py", ".sh"}:
            continue
        stem = path.name
        if (stem.startswith("test_") or stem.endswith("_test.py")
                or "/tests/" in rel):
            continue  # tests read fixtures, not the live record
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError):
            continue
        if ("_read_managed_targets_record" in text
                or "_MANAGED_TARGETS_FILE" in text):
            readers.add(rel)
    assert readers == {"scripts/self_update.py"}, readers


# --- managed-targets override note (issue #1412) -----------------------------

def _reload_with_disagreeing_env(monkeypatch, tmp_path, key, record_value,
                                 env_value):
    # Helper for the #1412 note tests: a record naming record_value for
    # `key` while the invoker's env names a different env_value. Returns the
    # reloaded module; caller undoes via monkeypatch/finally like the #1310
    # tests.
    other = ("PLAYWRIGHT_VENV" if key == "CUA_DRIVER_BIN"
             else "CUA_DRIVER_BIN")
    lines = {key: record_value, other: "/srv/updater/other"}
    record_text = "".join("%s=%s\n" % (k, v) for k, v in lines.items())
    return _reload_with_record_env(monkeypatch, tmp_path, record_text,
                                   extra_env={key: env_value})


def test_managed_override_note_fires_on_record_beating_disagreeing_env(
        monkeypatch, tmp_path):
    # #1412 item 2: the record wins over an explicitly-set, disagreeing env
    # var — the operator who set CUA_DRIVER_BIN in their shell sees S1 probe
    # a different artifact with no explanation. The probe note now names the
    # winning source. (Vacuity: without the note wiring, the note is the
    # plain "via <path> --version" and this fails.)
    import importlib
    driver = tmp_path / "cua-driver"
    driver.write_text("#!/bin/sh\necho 0.28.2\n")
    driver.chmod(0o755)
    runner = fake_runner({(str(driver), "--version"): (0, "0.28.2\n", "")})
    try:
        reloaded = _reload_with_disagreeing_env(
            monkeypatch, tmp_path, "CUA_DRIVER_BIN", str(driver),
            "/opt/custom/cua-driver")
        installed, version, note = reloaded.probe_cua_driver(runner=runner)
        assert installed is True
        assert "overridden by managed-targets record" in note
        assert "CUA_DRIVER_BIN=/opt/custom/cua-driver" in note
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


def test_managed_override_note_playwright(monkeypatch, tmp_path):
    # The PLAYWRIGHT_VENV half: the managed venv's python is probed while
    # the env names somewhere else, so the note names the override too.
    # (Vacuity: without the wiring, the note is "python package via ..."
    # with no override mention and this fails.)
    import importlib
    venv = tmp_path / "venv"
    bindir = venv / "bin"
    bindir.mkdir(parents=True)
    python = bindir / "python"
    python.write_text("#!/bin/sh\necho 1.62.0\n")
    python.chmod(0o755)
    runner = fake_runner({
        (str(python), "-c",
         "import importlib.metadata as m; print(m.version('playwright'))"):
        (0, "1.62.0\n", ""),
    })
    try:
        reloaded = _reload_with_disagreeing_env(
            monkeypatch, tmp_path, "PLAYWRIGHT_VENV", str(venv),
            "/opt/custom/pw")
        installed, version, note = reloaded.probe_playwright(runner=runner)
        assert installed is True
        assert "overridden by managed-targets record" in note
        assert "PLAYWRIGHT_VENV=/opt/custom/pw" in note
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


def test_managed_override_note_silent_when_env_agrees_with_record(
        monkeypatch, tmp_path):
    # No surprise, no note: the env names exactly what the record names.
    import importlib
    driver = tmp_path / "cua-driver"
    driver.write_text("#!/bin/sh\necho 0.28.2\n")
    driver.chmod(0o755)
    runner = fake_runner({(str(driver), "--version"): (0, "0.28.2\n", "")})
    try:
        reloaded = _reload_with_record_env(
            monkeypatch, tmp_path,
            "CUA_DRIVER_BIN=%s\nPLAYWRIGHT_VENV=/srv/updater/pw\n" % driver,
            extra_env={"CUA_DRIVER_BIN": str(driver)})
        _, _, note = reloaded.probe_cua_driver(runner=runner)
        assert "overridden" not in note
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


def test_managed_override_note_silent_without_record(monkeypatch, tmp_path):
    # Env set but no record: the env is the winner, nothing is overridden.
    # Uses the default resolution path (managed=None) for fidelity.
    import importlib
    driver = tmp_path / "cua-driver"
    driver.write_text("#!/bin/sh\necho 0.28.2\n")
    driver.chmod(0o755)
    runner = fake_runner({(str(driver), "--version"): (0, "0.28.2\n", "")})
    try:
        reloaded = _reload_with_record_env(
            monkeypatch, tmp_path, record_text=None,
            extra_env={"CUA_DRIVER_BIN": str(driver)})
        # Without a record the env value IS the managed target.
        _, _, note = reloaded.probe_cua_driver(runner=runner)
        assert "overridden" not in note
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


def test_managed_override_note_silent_on_path_fallback(monkeypatch, tmp_path):
    # #1412 edge: the record names a venv and the env disagrees, but the
    # record's venv has no executable python — the probe falls back to the
    # PATH python3, so the record's artifact was never probed and no
    # override note may fire.
    import importlib
    runner = fake_runner({
        (sys.executable, "-c",
         "import importlib.metadata as m; print(m.version('playwright'))"):
        (0, "1.62.0\n", ""),
    })
    try:
        reloaded = _reload_with_disagreeing_env(
            monkeypatch, tmp_path, "PLAYWRIGHT_VENV",
            str(tmp_path / "no-such-venv"), "/opt/custom/pw")
        installed, version, note = reloaded.probe_playwright(
            runner=runner, which=fake_which({"python3": sys.executable}))
        assert installed is True
        assert "overridden" not in note
    finally:
        monkeypatch.undo()
        importlib.reload(self_update)


def test_managed_override_note_silent_when_env_unset(monkeypatch, tmp_path):
    # Record present, env var absent: the record wins by default, nothing
    # was overridden — the operator set nothing to be surprised about.
    import importlib
    driver = tmp_path / "cua-driver"
    driver.write_text("#!/bin/sh\necho 0.28.2\n")
    driver.chmod(0o755)
    runner = fake_runner({(str(driver), "--version"): (0, "0.28.2\n", "")})
    try:
        monkeypatch.delenv("CUA_DRIVER_BIN", raising=False)
        reloaded = _reload_with_record_env(
            monkeypatch, tmp_path,
            "CUA_DRIVER_BIN=%s\nPLAYWRIGHT_VENV=/srv/updater/pw\n" % driver)
        _, _, note = reloaded.probe_cua_driver(runner=runner)
        assert "overridden" not in note
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


class _FakePwEnt:
    def __init__(self, pw_dir):
        self.pw_dir = pw_dir


class _FakePwd:
    def __init__(self, by_name=None, by_uid=None):
        self._by_name = by_name or {}
        self._by_uid = by_uid or {}

    def getpwnam(self, name):
        return self._by_name[name]

    def getpwuid(self, uid):
        return self._by_uid[uid]


def test_playwright_browsers_env_var_wins(monkeypatch, tmp_path):
    cache = tmp_path / "custom-cache"
    (cache / "chromium-1181").mkdir(parents=True)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(cache))
    monkeypatch.delenv("PLAYWRIGHT_USER", raising=False)
    installed, version, note = self_update.probe_playwright_browsers()
    assert installed is True
    assert version == "1 build(s)"
    assert "chromium-1181" in note and "PLAYWRIGHT_BROWSERS_PATH" in note


def test_playwright_browsers_playwright_user_home(monkeypatch, tmp_path):
    cache = tmp_path / ".cache" / "ms-playwright"
    (cache / "chromium-1181").mkdir(parents=True)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_USER", "pwuser")
    fake = _FakePwd(by_name={"pwuser": _FakePwEnt(str(tmp_path))})
    installed, version, note = self_update.probe_playwright_browsers(
        pwd_module=fake)
    assert installed is True
    assert "chromium-1181" in note
    assert "PLAYWRIGHT_USER=pwuser" in note


def test_playwright_browsers_numeric_playwright_user(monkeypatch, tmp_path):
    cache = tmp_path / ".cache" / "ms-playwright"
    (cache / "chromium-1181").mkdir(parents=True)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_USER", "1000")
    fake = _FakePwd(by_uid={1000: _FakePwEnt(str(tmp_path))})
    installed, version, note = self_update.probe_playwright_browsers(
        pwd_module=fake)
    assert installed is True
    assert "PLAYWRIGHT_USER=1000" in note


def test_playwright_browsers_unresolvable_user_falls_back_to_invoker(
        monkeypatch, tmp_path):
    cache = tmp_path / ".cache" / "ms-playwright"
    (cache / "chromium-1181").mkdir(parents=True)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_USER", "no-such-user")
    monkeypatch.setenv("HOME", str(tmp_path))
    installed, version, note = self_update.probe_playwright_browsers(
        pwd_module=_FakePwd())
    assert installed is True
    assert "chromium-1181" in note
    assert "unresolvable" in note


def test_playwright_browsers_explicit_home_beats_env_var(
        monkeypatch, tmp_path):
    home_cache = tmp_path / "home" / ".cache" / "ms-playwright"
    (home_cache / "chromium-1181").mkdir(parents=True)
    other_cache = tmp_path / "other"
    (other_cache / "firefox-1490").mkdir(parents=True)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(other_cache))
    installed, version, note = self_update.probe_playwright_browsers(
        home=str(tmp_path / "home"))
    assert installed is True
    assert "chromium-1181" in note
    assert "firefox-1490" not in note
    assert "explicit home override" in note


def test_playwright_browsers_blank_env_var_treated_as_unset(
        monkeypatch, tmp_path):
    cache = tmp_path / ".cache" / "ms-playwright"
    (cache / "chromium-1181").mkdir(parents=True)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "   ")
    monkeypatch.setenv("PLAYWRIGHT_USER", "pwuser")
    fake = _FakePwd(by_name={"pwuser": _FakePwEnt(str(tmp_path))})
    installed, version, note = self_update.probe_playwright_browsers(
        pwd_module=fake)
    assert installed is True
    assert "PLAYWRIGHT_USER=pwuser" in note


def test_playwright_browsers_default_playwright_user(monkeypatch, tmp_path):
    # PLAYWRIGHT_USER unset -> the default ntindle (the update plane's
    # default): the production path when the timer env sets no user.
    cache = tmp_path / ".cache" / "ms-playwright"
    (cache / "chromium-1181").mkdir(parents=True)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_USER", raising=False)
    fake = _FakePwd(by_name={"ntindle": _FakePwEnt(str(tmp_path))})
    installed, version, note = self_update.probe_playwright_browsers(
        pwd_module=fake)
    assert installed is True
    assert "chromium-1181" in note
    assert "PLAYWRIGHT_USER=ntindle" in note


def test_playwright_browsers_empty_playwright_user_means_default(
        monkeypatch, tmp_path):
    cache = tmp_path / ".cache" / "ms-playwright"
    (cache / "chromium-1181").mkdir(parents=True)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_USER", "")
    fake = _FakePwd(by_name={"ntindle": _FakePwEnt(str(tmp_path))})
    installed, version, note = self_update.probe_playwright_browsers(
        pwd_module=fake)
    assert installed is True
    assert "PLAYWRIGHT_USER=ntindle" in note


def test_playwright_browsers_pwd_none_falls_back_to_invoker(
        monkeypatch, tmp_path):
    # Non-POSIX: no pwd module at all -> invoker-home fallback, never raise.
    cache = tmp_path / ".cache" / "ms-playwright"
    (cache / "chromium-1181").mkdir(parents=True)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_USER", "pwuser")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(self_update, "pwd", None)
    installed, version, note = self_update.probe_playwright_browsers()
    assert installed is True
    assert "chromium-1181" in note
    assert "unresolvable" in note


class _OverflowPwd:
    def getpwnam(self, name):
        raise KeyError(name)

    def getpwuid(self, uid):
        raise OverflowError("uid too large")


def test_playwright_browsers_huge_numeric_user_falls_back(
        monkeypatch, tmp_path):
    cache = tmp_path / ".cache" / "ms-playwright"
    (cache / "chromium-1181").mkdir(parents=True)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_USER", "99999999999999999999999999")
    monkeypatch.setenv("HOME", str(tmp_path))
    installed, version, note = self_update.probe_playwright_browsers(
        pwd_module=_OverflowPwd())
    assert installed is True
    assert "chromium-1181" in note
    assert "unresolvable" in note


def test_playwright_browsers_unicode_digit_user_falls_back(
        monkeypatch, tmp_path):
    # "²".isdigit() is True but int() raises ValueError -> fallback.
    cache = tmp_path / ".cache" / "ms-playwright"
    (cache / "chromium-1181").mkdir(parents=True)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_USER", "²")
    monkeypatch.setenv("HOME", str(tmp_path))
    installed, version, note = self_update.probe_playwright_browsers(
        pwd_module=_FakePwd())
    assert installed is True
    assert "chromium-1181" in note
    assert "unresolvable" in note


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
