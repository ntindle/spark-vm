"""Regression tests for issue #1130: the redacted turn-event journal
(msp_signals.jsonl) lived in the agent-visible job dir, so a job's agent
could rewrite or truncate its own turn history -- anti-forensics against
`muse-job log` and the stillborn diagnosis.

The structural fix mirrors #11: the journal now lives in the operator-owned
journals dir (~/.local/share/muse-job/journals/<slug>.jsonl), which the
prompt preamble never names; the appender migrates a legacy in-tree journal
on first append (non-clobbering, cap-bounded read); `muse-job log` prefers
the new location and falls back to the legacy file read-only. The agent
loses the known writable path to the journal; the same-user caveat stands
(it is not a privilege boundary against a determined shell user).
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import types

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
    return load_script("muse_job_cli_journal", CLI_PATH)


class FakeSignal:
    def __init__(self, kind="item", method="item/added", detail="2 added"):
        self.kind = kind
        self.method = method
        self.detail = detail


def journal_path(cli, slug):
    return os.path.join(cli.JOURNAL_DIR, slug + ".jsonl")


def legacy_path(cli, slug):
    return os.path.join(cli.job_dir(slug), "msp_signals.jsonl")


def write_legacy(cli, slug, n, prefix="legacy"):
    p = legacy_path(cli, slug)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        for i in range(n):
            f.write(json.dumps({"t": 1000.0 + i, "kind": "item",
                                "method": "item/added",
                                "detail": f"{prefix}-{i}"}) + "\n")
    return p


def read_details(path):
    with open(path) as f:
        return [json.loads(line)["detail"] for line in f]


def log_args(cli, slug, n=50):
    return types.SimpleNamespace(slug=slug, n=n)


def test_append_writes_operator_dir_not_job_dir(cli):
    os.makedirs(cli.job_dir("demo"), exist_ok=True)
    cli._msp_journal_append("demo", [FakeSignal(detail="hello")])
    assert os.path.isfile(journal_path(cli, "demo")), \
        "the journal must live in the operator-owned journals dir"
    assert not os.path.exists(legacy_path(cli, "demo")), \
        "the job dir must not hold the live journal"
    assert read_details(journal_path(cli, "demo")) == ["hello"]


def test_append_creates_journals_dir(cli):
    assert not os.path.isdir(cli.JOURNAL_DIR)
    cli._msp_journal_append("fresh", [FakeSignal()])
    assert os.path.isfile(journal_path(cli, "fresh"))


def test_append_migrates_legacy_journal_first(cli):
    write_legacy(cli, "old", 3)
    cli._msp_journal_append("old", [FakeSignal(detail="new-0")])
    # Legacy file is gone; history preserved before the new signal.
    assert not os.path.exists(legacy_path(cli, "old")), \
        "the migrated legacy journal must be removed"
    assert read_details(journal_path(cli, "old")) == \
        ["legacy-0", "legacy-1", "legacy-2", "new-0"]


def test_append_migration_bounds_read_at_cap(cli):
    write_legacy(cli, "big", cli._MSP_JOURNAL_CAP + 50)
    cli._msp_journal_append("big", [])
    details = read_details(journal_path(cli, "big"))
    assert len(details) == cli._MSP_JOURNAL_CAP, \
        "the migration must not carry more than the cap"
    assert not os.path.exists(legacy_path(cli, "big"))


def test_log_reads_new_location(cli, capsys):
    os.makedirs(cli.job_dir("demo"), exist_ok=True)
    cli._msp_journal_append("demo", [FakeSignal(detail="visible")])
    assert cli._msp_log(log_args(cli, "demo")) == 0
    assert "visible" in capsys.readouterr().out


def test_log_prefers_new_over_legacy(cli, capsys):
    # The append creates the new journal first; a later legacy file (e.g.
    # a stale leftover whose unlink failed) must never be merged in.
    cli._msp_journal_append("both", [FakeSignal(detail="new-wins")])
    write_legacy(cli, "both", 1, prefix="legacy-should-hide")
    assert cli._msp_log(log_args(cli, "both")) == 0
    out = capsys.readouterr().out
    assert "new-wins" in out
    assert "legacy-should-hide" not in out


def test_log_falls_back_to_legacy_readonly(cli, capsys):
    write_legacy(cli, "stale", 2)
    assert cli._msp_log(log_args(cli, "stale")) == 0
    out = capsys.readouterr().out
    assert "legacy-0" in out and "legacy-1" in out
    # The fallback is read-only: no migration, no new file.
    assert os.path.isfile(legacy_path(cli, "stale"))
    assert not os.path.exists(journal_path(cli, "stale"))


def test_log_errors_when_no_journal(cli):
    with pytest.raises(RuntimeError, match="no MSP signal journal"):
        cli._msp_log(log_args(cli, "ghost"))


def test_cap_rewrite_keeps_tail_in_new_location(cli):
    os.makedirs(cli.job_dir("cap"), exist_ok=True)
    sigs = [FakeSignal(detail=f"sig-{i}")
            for i in range(cli._MSP_JOURNAL_CAP + 5)]
    cli._msp_journal_append("cap", sigs)
    details = read_details(journal_path(cli, "cap"))
    assert len(details) == cli._MSP_JOURNAL_CAP
    assert details[0] == "sig-5", "the cap rewrite keeps the tail"
    assert details[-1] == f"sig-{cli._MSP_JOURNAL_CAP + 4}"
    assert not os.path.exists(legacy_path(cli, "cap"))
