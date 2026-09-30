"""Regression tests for issue #12 item L7.

dir_size() walked the entire job dir on every `status`/`watch` pass,
including target/ and node_modules/ — 15s+ per job observed. The fix
prunes build-output and VCS dirs from the walk in bin/muse-job (the
operator-display path). bin/muse-job-sweep's own dir_size intentionally
keeps the full walk: its emergency breaker closes the largest job to
free real disk, so it must measure true on-disk size.
"""
import importlib.machinery
import importlib.util
import os
import sys

import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job")
SWEEP_PATH = os.path.join(os.path.dirname(__file__), "..", "bin",
                          "muse-job-sweep")


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
    return load_script("muse_job_cli_dirsizer", CLI_PATH)


@pytest.fixture()
def sweep(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_sweep_dirsizer", SWEEP_PATH)


def _write(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_dir_size_skips_build_output_and_vcs_dirs(cli, tmp_path):
    root = tmp_path / "jobdir"
    _write(root / "target" / "debug" / "blob", 4096)
    _write(root / "node_modules" / "pkg" / "blob", 4096)
    _write(root / ".git" / "objects" / "blob", 4096)
    _write(root / "prompt.md", 100)
    assert cli.dir_size(str(root)) == 100


def test_dir_size_still_counts_everything_else(cli, tmp_path):
    root = tmp_path / "jobdir"
    _write(root / "events" / "e1.jsonl", 200)
    _write(root / "job.json", 50)
    _write(root / "work" / "src" / "main.rs", 300)
    assert cli.dir_size(str(root)) == 550


def test_sweep_dir_size_keeps_true_on_disk_size(sweep, tmp_path):
    # The emergency breaker frees real disk by closing the largest job;
    # it must see target/ and node_modules/, not the display-pruned size.
    root = tmp_path / "jobdir"
    _write(root / "target" / "debug" / "blob", 4096)
    _write(root / "prompt.md", 100)
    assert sweep.dir_size(str(root)) == 4196
