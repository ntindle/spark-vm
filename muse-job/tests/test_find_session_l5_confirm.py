"""Issue #12 L5: session discovery must be confirmed via a live `muse`
process, not trusted from the same-user-writable hook registry alone.

find_session binds a spawn/resume to the newest registry record matching
the workdir. The registry is written by the plugin hooks and is
same-user writable, so a planted record can hijack the binding (a forged
session_id steers `muse resume` across the job boundary). The fix pins the
second, OS-level signal: a candidate binds only while a live `muse`
process actually has the workdir as its cwd. No such process -> fail
closed (the caller's poll loop keeps waiting).

Residual, stated plainly (also in the code): consistency enforcement, not
authentication -- a same-user writer that also runs a real muse process
in the workdir still passes.
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import time

import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job")


def load_script(name, path):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


@pytest.fixture()
def cli(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_l5", CLI_PATH)


def _write_session_record(cli, sid, cwd, first_seen=None):
    os.makedirs(cli.SESSIONS_DIR, exist_ok=True)
    with open(os.path.join(cli.SESSIONS_DIR, sid + ".json"), "w") as f:
        json.dump({"session_id": sid, "cwd": cwd,
                   "first_seen": first_seen if first_seen is not None else time.time(),
                   "tools": [{"name": "bash"}]}, f)


def _wait_until(fn, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if fn():
            return True
        time.sleep(0.1)
    return fn()


# --- the corroboration gate ---------------------------------------------------

def test_find_session_fails_closed_without_live_muse(cli, tmp_path):
    # A planted registry record for a workdir with no live muse process
    # must NOT bind: the real _muse_process_in_workdir finds nothing.
    work = str(tmp_path / "work")
    os.makedirs(work, exist_ok=True)
    _write_session_record(cli, "planted-sid", work)
    assert cli.find_session(work, time.time() - 60) is None


def test_find_session_binds_when_muse_live(cli, tmp_path, monkeypatch):
    # Selection logic unchanged once the OS confirms a live muse process.
    work = str(tmp_path / "work")
    os.makedirs(work, exist_ok=True)
    _write_session_record(cli, "real-sid", work)
    monkeypatch.setattr(cli, "_muse_process_in_workdir", lambda w: True)
    assert cli.find_session(work, time.time() - 60) == "real-sid"


def test_find_session_gate_applies_to_exclude_path(cli, tmp_path):
    # The exclude path (resume fallback) gets the same gate.
    work = str(tmp_path / "work")
    os.makedirs(work, exist_ok=True)
    _write_session_record(cli, "planted-sid", work)
    assert cli.find_session(work, time.time() - 60, exclude="other") is None


# --- _muse_process_in_workdir against the real /proc ----------------------------

def test_muse_process_in_workdir_detects_live_process(cli, tmp_path):
    # A real `muse`-named process with cwd=workdir is found; after it
    # exits the workdir reads empty again. (Anti-vacuous: the same test
    # would fail if the scan never matched.)
    if not os.path.isdir("/proc"):
        pytest.skip("no /proc on this platform")
    work = str(tmp_path / "work")
    os.makedirs(work, exist_ok=True)
    assert cli._muse_process_in_workdir(work) is False
    p = subprocess.Popen(
        ["bash", "-c", f"cd {work} && exec -a muse-bin-test sleep 60"])
    try:
        assert _wait_until(lambda: cli._muse_process_in_workdir(work)), \
            "live muse-named process in workdir not detected"
    finally:
        p.terminate()
        p.wait()
    assert _wait_until(lambda: not cli._muse_process_in_workdir(work)), \
        "dead process still reported in workdir"


def test_muse_process_in_workdir_ignores_decoy_name(cli, tmp_path):
    # Same cwd, but the process is not muse-named: no match.
    if not os.path.isdir("/proc"):
        pytest.skip("no /proc on this platform")
    work = str(tmp_path / "work")
    os.makedirs(work, exist_ok=True)
    p = subprocess.Popen(
        ["bash", "-c", f"cd {work} && exec -a notmuse sleep 60"])
    try:
        time.sleep(0.5)  # let it start; a false positive would show here
        assert cli._muse_process_in_workdir(work) is False
    finally:
        p.terminate()
        p.wait()


def test_muse_process_in_workdir_ignores_wrong_cwd(cli, tmp_path):
    # muse-named, but in a different cwd: no match for this workdir.
    if not os.path.isdir("/proc"):
        pytest.skip("no /proc on this platform")
    work = str(tmp_path / "work")
    other = str(tmp_path / "other")
    os.makedirs(work, exist_ok=True)
    os.makedirs(other, exist_ok=True)
    p = subprocess.Popen(
        ["bash", "-c", f"cd {other} && exec -a muse sleep 60"])
    try:
        assert _wait_until(lambda: cli._muse_process_in_workdir(other)), \
            "setup failed: muse-named process not detected in its own cwd"
        assert cli._muse_process_in_workdir(work) is False
    finally:
        p.terminate()
        p.wait()


def test_muse_process_in_workdir_no_proc(cli, monkeypatch, tmp_path):
    monkeypatch.setattr(cli.os.path, "isdir", lambda p: False)
    assert cli._muse_process_in_workdir(str(tmp_path)) is False
