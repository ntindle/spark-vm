"""Regression tests for issue #11: the job agent can rewrite ../job.json.

The structural fix: management metadata no longer lives in the
agent-visible job dir. `save_job` writes to the manager-side metadata dir
(~/.local/share/muse-job/jobs/<slug>.json), which the prompt preamble
never names; `load_job` lazily migrates legacy in-tree records on first
read; `list`/`watch` enumerate the union of both locations. The agent
loses the known writable path to the management record; the derived-layout
pins and read-side sanitizers stay as defense in depth.
"""
import importlib.machinery
import importlib.util
import json
import os
import sys

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
    return load_script("muse_job_cli_meta", CLI_PATH)


def meta_path(cli, slug):
    return os.path.join(cli.METADATA_DIR, slug + ".json")


def legacy_path(cli, slug):
    return os.path.join(cli.job_dir(slug), "job.json")


def write_legacy(cli, slug, record):
    p = legacy_path(cli, slug)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(record, f)
    return p


def test_save_job_writes_metadata_dir_not_job_dir(cli):
    jd = cli.job_dir("demo")
    os.makedirs(jd, exist_ok=True)
    cli.save_job({"slug": "demo", "state": "active"}, "demo")
    assert os.path.isfile(meta_path(cli, "demo")), \
        "the record must live in the metadata dir"
    assert not os.path.exists(legacy_path(cli, "demo")), \
        "the job dir must hold only agent-visible files"
    assert json.load(open(meta_path(cli, "demo")))["state"] == "active"


def test_save_job_creates_metadata_dir(cli):
    assert not os.path.isdir(cli.METADATA_DIR)
    cli.save_job({"slug": "fresh", "state": "active"}, "fresh")
    assert os.path.isfile(meta_path(cli, "fresh"))


def test_load_job_reads_metadata_location(cli):
    cli.save_job({"slug": "demo", "state": "blocked"}, "demo")
    job = cli.load_job("demo")
    assert job["state"] == "blocked"
    assert job["slug"] == "demo"


def test_load_job_migrates_legacy_record(cli):
    write_legacy(cli, "old", {"slug": "old", "state": "active",
                              "session_uuid": "uuid-1"})
    job = cli.load_job("old")
    assert job["state"] == "active"
    assert job["session_uuid"] == "uuid-1"
    assert os.path.isfile(meta_path(cli, "old")), \
        "the record must move to the metadata dir on first read"
    assert not os.path.exists(legacy_path(cli, "old")), \
        "the in-tree record must not survive the migration"


def test_migration_pins_record_slug(cli):
    # A legacy record with a forged slug migrates under the manager-side
    # slug: the recorded "slug" must never redirect the write.
    write_legacy(cli, "demo", {"slug": "victim", "state": "active"})
    job = cli.load_job("demo")
    assert job["slug"] == "demo"
    assert not os.path.exists(os.path.join(cli.METADATA_DIR, "victim.json"))
    assert not os.path.exists(legacy_path(cli, "demo"))


def test_load_job_unknown_slug_raises(cli):
    with pytest.raises(RuntimeError):
        cli.load_job("nope")


def test_load_job_falls_back_to_legacy_when_migration_fails(cli, monkeypatch):
    # B1: a failed move (unwritable metadata dir) must not make a good
    # legacy record unreadable — the record is served in place and the
    # next read retries the move.
    write_legacy(cli, "stuck", {"slug": "stuck", "state": "active"})
    def boom(slug):
        raise OSError("metadata dir unwritable")
    monkeypatch.setattr(cli, "_migrate_legacy_record", boom)
    job = cli.load_job("stuck")
    assert job["state"] == "active"
    assert job["slug"] == "stuck"
    assert os.path.exists(legacy_path(cli, "stuck")), \
        "the legacy record must survive a failed migration"
    assert not os.path.exists(meta_path(cli, "stuck"))


def test_load_job_rejects_non_dict_record(cli):
    cli.save_job(["not", "a", "dict"], "weird")
    with pytest.raises(ValueError):
        cli.load_job("weird")
    write_legacy(cli, "weirdleg", ["not", "a", "dict"])
    with pytest.raises(ValueError):
        cli.load_job("weirdleg")


def test_migration_never_clobbers_newer_metadata_record(cli):
    # Security review: the migration's bytes are stale (read before any
    # racing save), so they must never overwrite a metadata record a
    # racing manager already migrated or saved. Exercise the racy
    # interleaving directly: legacy present AND metadata already present.
    write_legacy(cli, "race", {"slug": "race", "state": "stale-legacy"})
    cli.save_job({"slug": "race", "state": "fresh-metadata"}, "race")
    cli._migrate_legacy_record("race")
    job = cli.load_job("race")
    assert job["state"] == "fresh-metadata", \
        "the racing record wins; stale legacy bytes must not clobber it"
    assert not os.path.exists(legacy_path(cli, "race")), \
        "the superseded legacy file is still unlinked"


def test_save_job_leaves_no_tmp_files(cli):
    # Security review: concurrent managers must never share a tmp file.
    cli.save_job({"slug": "t1", "state": "active"}, "t1")
    cli.save_job({"slug": "t1", "state": "blocked"}, "t1")
    leftovers = [n for n in os.listdir(cli.METADATA_DIR) if ".tmp." in n]
    assert leftovers == [], f"tmp files leaked: {leftovers}"
    assert json.load(open(meta_path(cli, "t1")))["state"] == "blocked"


def test_job_record_exists_both_locations(cli):
    assert not cli.job_record_exists("ghost")
    write_legacy(cli, "leg", {"slug": "leg", "state": "active"})
    assert cli.job_record_exists("leg"), "legacy in-tree records still count"
    cli.save_job({"slug": "leg", "state": "active"}, "leg")
    assert cli.job_record_exists("leg")


def test_iter_job_slugs_unions_both_locations(cli):
    write_legacy(cli, "legacy-one", {"slug": "legacy-one", "state": "closed"})
    cli.save_job({"slug": "meta-one", "state": "active"}, "meta-one")
    # A job dir with no record anywhere is not a job.
    os.makedirs(cli.job_dir("junk"), exist_ok=True)
    # A non-slug filename in the metadata dir is ignored.
    os.makedirs(cli.METADATA_DIR, exist_ok=True)
    with open(os.path.join(cli.METADATA_DIR, ".hidden.json"), "w") as f:
        json.dump({"slug": ".hidden"}, f)
    with open(os.path.join(cli.METADATA_DIR, "notes.txt"), "w") as f:
        f.write("not a record")
    slugs = cli.iter_job_slugs()
    assert slugs == ["legacy-one", "meta-one"]


def test_cmd_list_sees_both_locations(cli, capsys):
    import argparse
    write_legacy(cli, "legacy-l", {"slug": "legacy-l", "state": "closed",
                                   "started_at": 0})
    cli.save_job({"slug": "meta-l", "state": "active", "started_at": 0},
                 "meta-l")
    rc = cli.cmd_list(argparse.Namespace(json=True))
    assert rc == 0
    listed = {j["slug"] for j in json.loads(capsys.readouterr().out)}
    assert listed == {"legacy-l", "meta-l"}
