"""Hermetic tests for deploy/plane-cron/verify_plane_cron.py (#1069).

Everything here runs against in-memory fixture payloads — no network,
no token, no Cloudflare account. Fixtures use the Workers API
schedules-list shape: {"result": [{"cron": ...}], "success": true}.
"""

import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import verify_plane_cron as vpc


def _payload(crons, success=True):
    return {"result": [{"cron": c} for c in crons], "success": success,
            "errors": [], "messages": []}


def _main_with_fixture(crons, capsys, tmp_path):
    fixture = tmp_path / "schedules.json"
    fixture.write_text(json.dumps(_payload(crons)), encoding="utf-8")
    code = vpc.main(["--fixture", str(fixture), "--script-name", "test-worker"])
    return code, capsys.readouterr()


def test_all_contract_triggers_present_passes(capsys, tmp_path):
    code, out = _main_with_fixture(["* * * * *", "30 3 * * *"], capsys, tmp_path)
    assert code == 0
    assert "ok: all 2 contract cron triggers registered" in out.out


def test_missing_sweep_cron_is_the_silently_unwired_failure(capsys, tmp_path):
    # The exact failure mode #1069 exists to catch: handler deployed,
    # trigger never registered, nothing ever ticks.
    code, out = _main_with_fixture(["30 3 * * *"], capsys, tmp_path)
    assert code == 1
    assert "missing '* * * * *'" in out.out
    assert "#1069" in out.out


def test_missing_gc_cron_fails_and_names_1298(capsys, tmp_path):
    code, out = _main_with_fixture(["* * * * *"], capsys, tmp_path)
    assert code == 1
    assert "missing '30 3 * * *'" in out.out
    assert "#1298" in out.out


def test_empty_schedules_list_is_not_an_error_but_a_fail(capsys, tmp_path):
    code, out = _main_with_fixture([], capsys, tmp_path)
    assert code == 1
    assert "2 expected cron trigger(s) not registered" in out.out


def test_wrong_cadence_is_a_missing_expected_trigger(capsys, tmp_path):
    # */2 instead of */1 per minute: the sweep would still run, but not
    # on the contract's cadence — the check must not call that a pass.
    code, out = _main_with_fixture(["*/2 * * * *", "30 3 * * *"],
                                   capsys, tmp_path)
    assert code == 1
    assert "missing '* * * * *'" in out.out
    assert "*/2 * * * *" in out.out  # listed as an extra


def test_extras_are_informational_not_failures(capsys, tmp_path):
    # The plane legitimately carries triggers this contract does not
    # own (e.g. the #1013 phone-home GC): they are listed, not failed.
    code, out = _main_with_fixture(["* * * * *", "30 3 * * *", "0 5 * * *"],
                                   capsys, tmp_path)
    assert code == 0
    assert "extra cron schedule not in the contract: 0 5 * * *" in out.out


def test_whitespace_variants_normalize(capsys, tmp_path):
    code, _ = _main_with_fixture(["*  *\t* * *", "30  3 * * *"],
                                 capsys, tmp_path)
    assert code == 0


def test_malformed_payload_is_a_usage_error_not_a_pass(capsys, tmp_path):
    fixture = tmp_path / "bad.json"
    fixture.write_text(json.dumps({"result": "not-a-list"}), encoding="utf-8")
    code = vpc.main(["--fixture", str(fixture)])
    out = capsys.readouterr()
    assert code == 2
    assert "cannot read fixture" in out.err


def test_missing_token_without_fixture_is_usage_error(capsys, monkeypatch):
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    code = vpc.main(["--account-id", "abc"])
    out = capsys.readouterr()
    assert code == 2
    assert "CF_API_TOKEN" in out.err


def test_missing_account_id_without_fixture_is_usage_error(capsys, monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "sekrit")
    monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
    code = vpc.main([])
    out = capsys.readouterr()
    assert code == 2
    assert "--account-id" in out.err
    # The token must never appear in output, even in an error path.
    assert "sekrit" not in out.err and "sekrit" not in out.out


def test_expected_table_is_single_sourced():
    # The contract doc reprints EXPECTED_TRIGGERS; keep them adjacent
    # here so drift is a test failure, not a silent lie.
    assert len(vpc.EXPECTED_TRIGGERS) == 2
    crons = [c for c, _ in vpc.EXPECTED_TRIGGERS]
    assert crons[0] == "* * * * *"
    assert crons[1] == "30 3 * * *"


def test_check_triggers_unit():
    missing, extras = vpc.check_triggers(
        vpc.EXPECTED_TRIGGERS, {"* * * * *", "30 3 * * *", "0 5 * * *"})
    assert missing == []
    assert extras == ["0 5 * * *"]
    missing, _ = vpc.check_triggers(vpc.EXPECTED_TRIGGERS, set())
    assert [c for c, _ in missing] == ["* * * * *", "30 3 * * *"]
