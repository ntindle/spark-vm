"""Tests for issue #1394: the voucher-grant path for live jobs.

`muse-job spawn --trust-workspace` is spawn-time-only, so a job spawned
without it (or before the flag existed) fails closed at the trust gate
forever. `muse-job trust <slug>` flips the manager-side record bit on a
live job instead -- the operator-initiated, manager-side, journaled
ceremony the issue requires, never agent-reachable (the record lives in
METADATA_DIR per #11, the journal in the operator-owned journals dir per
#1130; the prompt preamble names neither).

No tmux, no git, no network: the pane capture / process check / runner
are monkeypatched on the loaded CLI module; HOME points at a tmp dir so
all manager-side state is isolated.
"""
import argparse
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
    """Import bin/muse-job with HOME pointed at an isolated tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_trust_grant", CLI_PATH)


def _args(slug):
    return argparse.Namespace(slug=slug)


def _seed(cli, slug, **fields):
    """Write a manager-side job record for the trust command to find."""
    job = {"slug": slug, "state": "active", "trust_workspace": False}
    job.update(fields)
    cli.save_job(job, slug)
    return job


def _gate_pane():
    """A pane tail showing the full trust-gate shape (question + option)."""
    return "\n".join([
        "some earlier output",
        "Do you trust this workspace?",
        "> 1 Trust and continue",
        "  2 Don't trust",
    ])


def test_parser_registers_trust(cli):
    ap = cli.build_parser()
    args = ap.parse_args(["trust", "s1"])
    assert args.slug == "s1"
    assert args.fn is cli.cmd_trust


def test_trust_unknown_job(cli):
    with pytest.raises(RuntimeError, match="unknown job"):
        cli.cmd_trust(_args("nope"))


def test_trust_holds_per_slug_lock(cli, monkeypatch):
    """The read-modify-write runs under the per-slug flock (the
    cmd_close discipline): a racing close cannot be resurrected by a
    stale save, and racing trusts cannot double-journal the grant."""
    held = []
    real_lock = cli.with_lock

    def recording(slug, fn):
        held.append(slug)
        return real_lock(slug, fn)

    monkeypatch.setattr(cli, "with_lock", recording)
    _seed(cli, "s1")
    cli.cmd_trust(_args("s1"))
    assert held == ["s1"]


def test_trust_flips_record_and_persists(cli, capsys):
    _seed(cli, "s1")
    assert cli.cmd_trust(_args("s1")) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"slug": "s1", "trust_workspace": True,
                   "granted": True, "inert": False}
    # Round-trip through the real load/save path: the grant persisted.
    assert cli.load_job("s1")["trust_workspace"] is True


def test_trust_grants_legacy_record_without_key(cli, capsys):
    """#1394's motivating case: records spawned before the flag carry no
    trust_workspace key at all. The fail-closed read must still be the
    grant path, never the idempotent no-op."""
    cli.save_job({"slug": "s1", "state": "active"}, "s1")
    assert cli.cmd_trust(_args("s1")) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["granted"] is True
    assert cli.load_job("s1")["trust_workspace"] is True


def test_trust_idempotent(cli, capsys):
    """An already-trusted job is a no-op -- and journals nothing."""
    _seed(cli, "s1", trust_workspace=True)
    assert cli.cmd_trust(_args("s1")) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"slug": "s1", "trust_workspace": True, "granted": False,
                   "note": "already trusted", "inert": False}
    assert not os.path.exists(cli._msp_journal_path("s1"))


def test_trust_journaled_with_operator_as_actor(cli):
    """Acceptance: the grant is journaled, operator-initiated."""
    _seed(cli, "s1")
    cli.cmd_trust(_args("s1"))
    path = cli._msp_journal_path("s1")
    assert os.path.isfile(path)
    lines = [json.loads(l) for l in open(path) if l.strip()]
    grants = [l for l in lines if l.get("kind") == "operator_grant"]
    assert len(grants) == 1
    assert grants[0]["method"] == "trust_workspace"
    assert "operator" in grants[0]["detail"]
    assert "s1" in grants[0]["detail"]


def test_trust_grant_never_agent_reachable(cli):
    """The grant touches manager-side paths only: the record in
    METADATA_DIR (#11) and the journal in the operator-owned journals
    dir (#1130) -- neither lives in the agent-visible job dir, and the
    prompt preamble names neither."""
    _seed(cli, "s1")
    cli.cmd_trust(_args("s1"))
    record_path = cli.job_json_path("s1")
    journal_path = cli._msp_journal_path("s1")
    agent_visible = cli.job_dir("s1")
    assert record_path.startswith(cli.METADATA_DIR + os.sep)
    assert journal_path.startswith(cli.JOURNAL_DIR + os.sep)
    assert not os.path.commonpath(
        [os.path.abspath(record_path), os.path.abspath(agent_visible)]
    ) == os.path.abspath(agent_visible)
    assert not journal_path.startswith(
        os.path.abspath(agent_visible) + os.sep)


def test_trust_refused_on_closed_job(cli):
    """A closed job's record is archived: granting is refused, nothing
    is written."""
    _seed(cli, "s1", state="closed")
    with pytest.raises(RuntimeError, match="closed"):
        cli.cmd_trust(_args("s1"))
    assert cli.load_job("s1")["trust_workspace"] is False
    assert not os.path.exists(cli._msp_journal_path("s1"))


def test_trust_warns_but_records_on_killed_job(cli, capsys):
    """A killed job will not be revived by the watchdog: the grant is
    still recorded (honest bookkeeping) but the operator is warned."""
    _seed(cli, "s1", state="killed")
    assert cli.cmd_trust(_args("s1")) == 0
    assert cli.load_job("s1")["trust_workspace"] is True
    err = capsys.readouterr().err
    assert "killed" in err and "watchdog" in err


def test_trust_msp_job_granted_but_inert(cli, capsys):
    """MSP jobs have no auto-answer posture to adopt (trust prompts keep
    their per-answer classification): the grant is recorded for
    bookkeeping, flagged inert, and the journal says so."""
    _seed(cli, "s1", transport="msp", session_uuid="u1")
    cli.cmd_trust(_args("s1"))
    out = json.loads(capsys.readouterr().out)
    assert out == {"slug": "s1", "trust_workspace": True,
                   "granted": True, "inert": True}
    lines = [json.loads(l) for l in open(cli._msp_journal_path("s1"))
             if l.strip()]
    assert any("inert" in l["detail"] for l in lines
               if l.get("kind") == "operator_grant")


def _patch_gate_world(cli, monkeypatch, pane, pane_cwd):
    monkeypatch.setattr(cli, "_capture_pane_state",
                        lambda target: (pane, "muse"))
    monkeypatch.setattr(cli, "_is_tui_process", lambda cmd: True)
    monkeypatch.setattr(cli, "_pane_current_path", lambda target: pane_cwd)
    calls = []
    monkeypatch.setattr(cli, "run",
                        lambda *a, **k: calls.append(a) or (0, "", ""))
    return calls


def test_trust_voucher_takes_effect_end_to_end(cli, monkeypatch):
    """The whole point of #1394: a live job whose gate was failing
    closed (no grant) answers the gate once the operator grants it --
    through the real record read in _answer_trust_prompt."""
    _seed(cli, "s1")  # trust_workspace: False -- the pre-grant world
    vouched = os.path.realpath(os.path.join(cli.job_dir("s1"), "work"))
    calls = _patch_gate_world(cli, monkeypatch, _gate_pane(), vouched)
    assert cli._answer_trust_prompt("s1", timeout=1) is False
    assert calls == []

    cli.cmd_trust(_args("s1"))  # the operator's grant ceremony
    assert cli._answer_trust_prompt("s1", timeout=1) is True
    assert calls, "the granted voucher must reach send-keys on the gate"


def test_trust_grant_does_not_answer_scope_violation(cli, monkeypatch):
    """The grant is a voucher, not a blank check: after granting, a gate
    parked in a directory other than the job's own workdir still fails
    closed (the scope check lives in _answer_trust_prompt, untouched)."""
    _seed(cli, "s1")
    cli.cmd_trust(_args("s1"))
    elsewhere = os.path.realpath(os.path.join(cli.job_dir("s1")))
    calls = _patch_gate_world(cli, monkeypatch, _gate_pane(), elsewhere)
    assert cli._answer_trust_prompt("s1", timeout=1) is False
    assert calls == []
