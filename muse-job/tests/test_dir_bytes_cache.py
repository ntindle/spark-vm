"""Regression tests for issue #12 item L7 (second half).

The first half pruned build-output/VCS dirs from the walk
(test_dir_size_prune.py); the walk still ran on EVERY status/watch pass
(15s+ per job observed). This half caches the measured size on the job
record with a 15-minute TTL: the only consumer is watch's 20 GB "heavy"
signal, which tolerates a coarse reading. A corrupted, non-numeric, or
future-dated cache fails back to a fresh walk, never to a crash or a
pinned stale value.
"""
import importlib.machinery
import importlib.util
import json
import os
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
    return load_script("muse_job_cli_dircache", CLI_PATH)


def _job_setup(cli, tmp_path, slug="job1", record=None):
    jd = tmp_path / "muse-jobs" / slug
    jd.mkdir(parents=True)
    (jd / "job.json").write_text(json.dumps(record or {"slug": slug}))
    return jd


def _walk_counter(cli, monkeypatch, total=1234):
    calls = []

    def fake(path):
        calls.append(path)
        return total

    monkeypatch.setattr(cli, "dir_size", fake)
    return calls


def test_cold_cache_walks_and_persists(cli, tmp_path, monkeypatch):
    jd = _job_setup(cli, tmp_path)
    calls = _walk_counter(cli, monkeypatch)
    job = json.loads((jd / "job.json").read_text())
    assert cli._cached_dir_bytes(job, "job1") == 1234
    assert len(calls) == 1
    # Persistence goes through save_job, i.e. the metadata dir (issue #11).
    persisted = json.loads(open(cli.job_json_path("job1")).read())
    assert persisted["last_dir_bytes"] == 1234
    assert persisted["last_dir_scan_at"] > 0


def test_warm_cache_serves_without_rewalk(cli, tmp_path, monkeypatch):
    jd = _job_setup(cli, tmp_path)
    calls = _walk_counter(cli, monkeypatch)
    job = json.loads((jd / "job.json").read_text())
    assert cli._cached_dir_bytes(job, "job1") == 1234
    # A second call inside the TTL must not walk again, even though the
    # on-disk tree changed underneath (staleness is the documented tradeoff;
    # the only consumer tolerates a coarse reading).
    (jd / "newfile.bin").write_bytes(b"y" * 99999)
    assert cli._cached_dir_bytes(job, "job1") == 1234
    assert len(calls) == 1


def test_expired_ttl_rewalks(cli, tmp_path, monkeypatch):
    jd = _job_setup(cli, tmp_path, record={
        "slug": "job1",
        "last_dir_bytes": 50,
        "last_dir_scan_at": time.time() - cli._DIR_BYTES_TTL_S - 1,
    })
    calls = _walk_counter(cli, monkeypatch, total=7777)
    job = json.loads((jd / "job.json").read_text())
    assert cli._cached_dir_bytes(job, "job1") == 7777
    assert len(calls) == 1
    # Persistence goes through save_job, i.e. the metadata dir (issue #11).
    persisted = json.loads(open(cli.job_json_path("job1")).read())
    assert persisted["last_dir_bytes"] == 7777


def test_garbage_cache_fails_to_rewalk(cli, tmp_path, monkeypatch):
    # job.json is agent-writable (#11): a non-numeric cached value must fail
    # back to a fresh walk, never to a crash or a served garbage value.
    jd = _job_setup(cli, tmp_path, record={
        "slug": "job1",
        "last_dir_bytes": "definitely-not-a-number",
        "last_dir_scan_at": time.time(),
    })
    calls = _walk_counter(cli, monkeypatch)
    job = json.loads((jd / "job.json").read_text())
    assert cli._cached_dir_bytes(job, "job1") == 1234
    assert len(calls) == 1


def test_future_timestamp_fails_to_rewalk(cli, tmp_path, monkeypatch):
    # A future-dated scan (clock skew or tamper) must not pin a stale
    # cached value indefinitely: fail to a fresh walk.
    jd = _job_setup(cli, tmp_path, record={
        "slug": "job1",
        "last_dir_bytes": 50,
        "last_dir_scan_at": time.time() + 3600,
    })
    calls = _walk_counter(cli, monkeypatch)
    job = json.loads((jd / "job.json").read_text())
    assert cli._cached_dir_bytes(job, "job1") == 1234
    assert len(calls) == 1
