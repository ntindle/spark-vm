"""Tests for issue #1372 slice 3: the standing trust-policy opt-in.

`muse-job spawn --trust-workspace` records the operator's per-job voucher
for the job's own workdir in the job record. `_answer_trust_prompt` (the
funnel every auto-answer path uses: spawn, resume, watchdog recovery)
refuses without it -- fail-closed per the #211 decision.

No tmux, no git, no network: the pane capture / process check / runner
are monkeypatched on the loaded CLI module.
"""
import importlib.machinery
import importlib.util
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
    """Import bin/muse-job with HOME pointed at an isolated tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_trust_optin", CLI_PATH)


def _gate_pane(cli):
    """A pane tail showing the full trust-gate shape (question + option)."""
    return "\n".join([
        "some earlier output",
        "Do you trust this workspace?",
        "> 1 Trust and continue",
        "  2 Don't trust",
    ])


def _patch_gate_world(cli, monkeypatch, job_record, pane, pane_cwd=None):
    """Point the answer path at a fake world: controlled job record,
    controlled pane, TUI-looking process, a recording runner, and a
    controlled pane cwd (defaults to the job's own workdir -- the
    vouched directory)."""
    monkeypatch.setattr(cli, "load_job", lambda slug: job_record)
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: (pane, "muse --yolo"))
    monkeypatch.setattr(cli, "_is_tui_process", lambda cmd: True)
    if pane_cwd is None:
        pane_cwd = os.path.join(cli.job_dir("s1"), "work")
    monkeypatch.setattr(cli, "_pane_current_path", lambda target: pane_cwd)
    calls = []
    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: calls.append(a) or (0, "", ""))
    return calls


def test_spawn_flag_defaults_off(cli):
    ap = cli.build_parser()
    args = ap.parse_args(["spawn", "s1", "--repo", "https://x/y.git",
                          "--prompt-file", "p.md"])
    assert args.trust_workspace is False


def test_spawn_flag_opt_in(cli):
    ap = cli.build_parser()
    args = ap.parse_args(["spawn", "s1", "--repo", "https://x/y.git",
                          "--prompt-file", "p.md", "--trust-workspace"])
    assert args.trust_workspace is True


def test_answer_refused_without_opt_in(cli, monkeypatch):
    """Fail-closed default: no flag on the record -> no answer, even with
    the gate plainly showing."""
    calls = _patch_gate_world(cli, monkeypatch,
                              {"slug": "s1", "trust_workspace": False},
                              _gate_pane(cli))
    assert cli._answer_trust_prompt("s1", timeout=1) is False
    assert calls == []


def test_answer_refused_when_key_missing(cli, monkeypatch):
    """Records predating the flag read as opt-out (fail-closed)."""
    calls = _patch_gate_world(cli, monkeypatch,
                              {"slug": "s1"}, _gate_pane(cli))
    assert cli._answer_trust_prompt("s1", timeout=1) is False
    assert calls == []


def test_answer_refused_when_record_unreadable(cli, monkeypatch):
    """A missing/corrupt job record must not be answered into."""
    def boom(slug):
        raise RuntimeError("unknown job: nope")
    monkeypatch.setattr(cli, "load_job", boom)
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: (_gate_pane(cli), "muse --yolo"))
    calls = []
    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: calls.append(a) or (0, "", ""))
    assert cli._answer_trust_prompt("nope", timeout=1) is False
    assert calls == []


def test_answer_allowed_with_opt_in(cli, monkeypatch):
    """With the opt-in, the standing behavior is unchanged: the gate is
    answered with text + Enter as separate send-keys."""
    calls = _patch_gate_world(cli, monkeypatch,
                              {"slug": "s1", "trust_workspace": True},
                              _gate_pane(cli))
    assert cli._answer_trust_prompt("s1", timeout=1) is True
    sent = [a[4] for a in calls if a[0] == "tmux" and a[1] == "send-keys"]
    assert sent == ["1", "Enter"]


def test_no_gate_no_answer_with_opt_in(cli, monkeypatch):
    """The opt-in does not invent answers: no gate showing -> no keys,
    even opted in (the pane reports a live TUI instead)."""
    monkeypatch.setattr(cli, "load_job",
                        lambda slug: {"slug": "s1", "trust_workspace": True})
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: ("some live tui output", "muse --yolo"))
    monkeypatch.setattr(cli, "_pane_shows_live_tui", lambda p, c: True)
    calls = []
    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: calls.append(a) or (0, "", ""))
    assert cli._answer_trust_prompt("s1", timeout=1) is False
    assert calls == []


def test_answer_refused_when_gate_in_foreign_dir(cli, monkeypatch):
    """Scope enforcement: the voucher covers the job's own workdir only.
    A full-shape gate parked in another directory (the agent cd'd
    elsewhere) must NOT be answered, even opted in."""
    calls = _patch_gate_world(cli, monkeypatch,
                              {"slug": "s1", "trust_workspace": True},
                              _gate_pane(cli), pane_cwd="/tmp/elsewhere")
    assert cli._answer_trust_prompt("s1", timeout=1) is False
    assert calls == []


def test_answer_refused_when_cwd_unavailable(cli, monkeypatch):
    """Fail closed on cwd capture failure: an unknown pane directory is
    not the vouched one."""
    calls = _patch_gate_world(cli, monkeypatch,
                              {"slug": "s1", "trust_workspace": True},
                              _gate_pane(cli))
    monkeypatch.setattr(cli, "_pane_current_path", lambda target: None)
    assert cli._answer_trust_prompt("s1", timeout=1) is False
    assert calls == []


def _spawn_prepare_args(cli, tmp_path, slug, extra=()):
    prompt = tmp_path / ("%s-prompt.md" % slug)
    prompt.write_text("a perfectly innocent prompt with no secrets in it")
    argv = (["spawn", slug, "--repo", "https://example.com/Org/Repo.git",
             "--prompt-file", str(prompt)] + list(extra))
    return cli.build_parser().parse_args(argv)


def _fake_git_run(monkeypatch, cli):
    """Fake the CLI's `run` so _spawn_prepare's git calls succeed without
    a real repo (mirrors test_pristine_namespacing.py)."""
    import subprocess

    def fake_run(*argv, **kwargs):
        return subprocess.CompletedProcess(
            args=list(argv), returncode=0, stdout=b"deadbeef\n", stderr=b"")

    monkeypatch.setattr(cli, "run", fake_run)


def test_spawn_prepare_records_opt_in(cli, monkeypatch, tmp_path):
    """The flag->record wiring (the feature's core contract): a real
    --trust-workspace parse through _spawn_prepare lands
    trust_workspace=true in the saved job record."""
    _fake_git_run(monkeypatch, cli)
    args = _spawn_prepare_args(cli, tmp_path, "trustjob", ["--trust-workspace"])
    job, work, jd = cli._spawn_prepare(args.slug, args, cli.PREAMBLE_MSP, None)
    assert job["trust_workspace"] is True
    assert cli.load_job(args.slug)["trust_workspace"] is True


def test_spawn_prepare_records_opt_out_default(cli, monkeypatch, tmp_path):
    """No flag -> the record reads False (fail-closed default), both on
    the returned dict and the re-read record."""
    _fake_git_run(monkeypatch, cli)
    args = _spawn_prepare_args(cli, tmp_path, "notrustjob")
    job, work, jd = cli._spawn_prepare(args.slug, args, cli.PREAMBLE_MSP, None)
    assert job["trust_workspace"] is False
    assert cli.load_job(args.slug)["trust_workspace"] is False
