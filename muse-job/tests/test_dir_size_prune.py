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
import json
import os
import sys
import time

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


def _sweep_job(home, slug, state, legacy_state=None, age_days=8):
    """Seed one job for the prune test: job dir with an old mtime, a
    metadata record, a journals-dir journal, and optionally a legacy
    in-tree record.
    NB: all writes inside the job dir happen BEFORE backdating its mtime
    (creating a file refreshes the dir's mtime)."""
    jd = home / "muse-jobs" / slug
    jd.mkdir(parents=True, exist_ok=True)
    if legacy_state is not None:
        (jd / "job.json").write_text(json.dumps({"slug": slug,
                                                 "state": legacy_state}))
    old = time.time() - age_days * 86400
    os.utime(jd, (old, old))
    meta = home / ".local" / "share" / "muse-job" / "jobs"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / f"{slug}.json").write_text(json.dumps({"slug": slug,
                                                   "state": state}))
    journals = home / ".local" / "share" / "muse-job" / "journals"
    journals.mkdir(parents=True, exist_ok=True)
    (journals / f"{slug}.jsonl").write_text(
        json.dumps({"t": 1700000000, "kind": "item",
                    "method": "item/added", "detail": "seeded"}) + "\n")
    return jd


def test_sweep_prune_removes_metadata_record_with_closed_dir(
        sweep, tmp_path, monkeypatch):
    # Issue #11: the manager-side record lives outside the job dir, so the
    # prune must delete it alongside the dir -- otherwise list/watch would
    # enumerate the pruned job forever.
    # A: closed + old -> dir and metadata record both pruned.
    home = tmp_path
    jd_a = _sweep_job(home, "oldjob", "closed")
    # B: active + old -> both survive.
    jd_b = _sweep_job(home, "livejob", "active")
    # C: legacy-only closed (no metadata file) -> dir pruned, no error.
    # NB: write the record BEFORE backdating the dir mtime -- creating a
    # file inside the dir refreshes the dir's mtime.
    jd_c = home / "muse-jobs" / "legjob"
    jd_c.mkdir(parents=True, exist_ok=True)
    (jd_c / "job.json").write_text(json.dumps({"slug": "legjob",
                                               "state": "closed"}))
    old = time.time() - 8 * 86400
    os.utime(jd_c, (old, old))
    # D: conflict (metadata active + legacy closed) -> metadata wins, kept.
    jd_d = _sweep_job(home, "dupe", "active", legacy_state="closed")
    # WARN_PCT <= 90 < KILL_PCT: the prune branch runs, the emergency
    # breaker loop exits immediately (no subprocesses).
    monkeypatch.setattr(sweep, "disk_pct", lambda p: 90)
    sweep.main()  # exits 0 always; never break the cron
    meta = home / ".local" / "share" / "muse-job" / "jobs"
    assert not jd_a.exists() and not (meta / "oldjob.json").exists()
    assert str(jd_a) in sweep.summary["pruned"]
    assert jd_b.exists() and (meta / "livejob.json").exists()
    assert not jd_c.exists()
    assert jd_d.exists() and (meta / "dupe.json").exists(), \
        "metadata-wins: an active metadata record is not pruned"


def test_sweep_prune_keeps_record_when_dir_survives(
        sweep, tmp_path, monkeypatch):
    # A failed rmtree must not orphan the metadata record while the dir
    # (and any legacy record in it) survives -- the remove is gated on the
    # dir actually being gone.
    home = tmp_path
    jd = _sweep_job(home, "stubborn", "closed")
    monkeypatch.setattr(sweep, "disk_pct", lambda p: 90)
    # Simulate rmtree silently failing (ignore_errors=True swallows).
    monkeypatch.setattr(sweep.shutil, "rmtree", lambda *a, **k: None)
    sweep.main()  # exits 0 always; never break the cron
    meta = home / ".local" / "share" / "muse-job" / "jobs"
    assert jd.exists()
    assert (meta / "stubborn.json").exists(), \
        "the record must survive when the dir was not actually removed"


def test_sweep_prune_removes_journal_with_closed_dir(
        sweep, tmp_path, monkeypatch):
    # Issue #1130: the manager-side journal lives outside the job dir, so
    # the prune must delete it alongside the dir -- otherwise `muse-job
    # log` would render a ghost journal for a swept job.
    home = tmp_path
    jd_a = _sweep_job(home, "oldjob", "closed")
    jd_b = _sweep_job(home, "livejob", "active")
    monkeypatch.setattr(sweep, "disk_pct", lambda p: 90)
    sweep.main()  # exits 0 always; never break the cron
    journals = home / ".local" / "share" / "muse-job" / "journals"
    assert not jd_a.exists() and not (journals / "oldjob.jsonl").exists(), \
        "the closed job's journal must be pruned with its dir"
    assert jd_b.exists() and (journals / "livejob.jsonl").exists(), \
        "an active job's journal must survive the prune"


def test_sweep_prune_keeps_journal_when_dir_survives(
        sweep, tmp_path, monkeypatch):
    # The journal remove shares the dir-gone gate: a failed rmtree must
    # not orphan the journal while the dir survives.
    home = tmp_path
    jd = _sweep_job(home, "stubborn", "closed")
    monkeypatch.setattr(sweep, "disk_pct", lambda p: 90)
    monkeypatch.setattr(sweep.shutil, "rmtree", lambda *a, **k: None)
    sweep.main()  # exits 0 always; never break the cron
    journals = home / ".local" / "share" / "muse-job" / "journals"
    assert jd.exists()
    assert (journals / "stubborn.jsonl").exists(), \
        "the journal must survive when the dir was not actually removed"
