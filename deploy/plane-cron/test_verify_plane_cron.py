"""Hermetic tests for deploy/plane-cron/verify_plane_cron.py (#1069).

Everything here runs against in-memory fixture payloads — no network,
no token, no Cloudflare account. Fixtures use the Workers API
schedules-list shape: {"result": [{"cron": ...}], "success": true}.
"""

import json
import os
import re
import socket
import sys
from pathlib import Path

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
    assert "ok (fixture): all 2 contract cron triggers registered" in out.out


def test_fixture_api_failure_is_usage_error_not_pass(capsys, tmp_path):
    # A saved failed API response must never greenlight the check —
    # the live path treats success:false as an API error (exit 2).
    fixture = tmp_path / "failed.json"
    fixture.write_text(json.dumps({
        "result": [{"cron": "* * * * *"}, {"cron": "30 3 * * *"}],
        "success": False,
        "errors": [{"message": "boom"}]}), encoding="utf-8")
    code = vpc.main(["--fixture", str(fixture)])
    out = capsys.readouterr()
    assert code == 2
    assert "cannot read fixture" in out.err


def test_fixture_mode_labels_its_provenance(capsys, tmp_path):
    # A fixture pass asserts against a saved snapshot only — the output
    # must never be mistakable for live deploy proof (#1069's whole point).
    code, out = _main_with_fixture(["* * * * *", "30 3 * * *"], capsys, tmp_path)
    assert code == 0
    assert "NOT the live Workers API" in out.out
    code, out = _main_with_fixture([], capsys, tmp_path)
    assert code == 1
    assert "FAIL (fixture):" in out.out
    assert "NOT the live Workers API" in out.out


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
    bad_payloads = [
        {"result": "not-a-list"},
        {"result": [{"cron": None}]},  # null cron must not parse as "None"
        {"result": [{"schedule": "* * * * *"}]},
    ]
    for n, payload in enumerate(bad_payloads):
        fixture = tmp_path / f"bad{n}.json"
        fixture.write_text(json.dumps(payload), encoding="utf-8")
        code = vpc.main(["--fixture", str(fixture)])
        out = capsys.readouterr()
        assert code == 2, payload
        assert "cannot read fixture" in out.err, payload


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
    # The contract doc reprints EXPECTED_TRIGGERS; parse the cron
    # strings out of its [triggers] block and assert they equal the
    # script's table — otherwise the single-sourcing claim is a lie.
    contract = Path(__file__).with_name("CRON_TRIGGER_CONTRACT.md").read_text(
        encoding="utf-8")
    block = re.search(r"crons\s*=\s*\[(.*?)\]", contract, re.S).group(1)
    block = re.sub(r"#.*", "", block)  # drop toml comments before quoting
    doc_crons = {vpc.normalize_cron(m) for m in re.findall(r'"([^"]+)"', block)}
    script_crons = {vpc.normalize_cron(c) for c, _ in vpc.EXPECTED_TRIGGERS}
    assert doc_crons == script_crons
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


# --- fetch_schedules (the live API path): hermetic, no network. ---

class _FakeResp:
    def __init__(self, body):
        self._body = body
        self.exited = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.exited = True
        return False

    def read(self):
        return self._body


def _fake_urlopen_with(body=None, exc=None, read_exc=None):
    def fake(req, timeout=None):
        fake.captured_url = req.full_url
        fake.captured_auth = req.get_header("Authorization")
        fake.captured_timeout = timeout
        if exc is not None:
            raise exc(req.full_url)
        fake.resp = _FakeResp(body)
        if read_exc is not None:
            def boom():
                raise read_exc
            fake.resp.read = boom
        return fake.resp
    return fake


def test_fetch_schedules_hits_the_right_endpoint_with_bearer(monkeypatch):
    fake = _fake_urlopen_with(
        json.dumps({"result": [{"cron": "*  * * * *"}],
                    "success": True}).encode())
    monkeypatch.setattr(vpc.urllib.request, "urlopen", fake)
    got = vpc.fetch_schedules("acct123", "my-worker", "sekrit")
    assert got == {"* * * * *"}
    assert fake.captured_url == (
        "https://api.cloudflare.com/client/v4"
        "/accounts/acct123/workers/scripts/my-worker/schedules")
    assert fake.captured_auth == "Bearer sekrit"
    # The timeout is load-bearing for a deploy-proof script: an
    # unbounded urlopen hangs the operator's post-deploy check.
    assert fake.captured_timeout == 30
    # The response must be closed via the context manager.
    assert fake.resp.exited is True


def test_fetch_schedules_http_error_names_status_not_token(monkeypatch):
    def boom(url):
        return vpc.urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    monkeypatch.setattr(vpc.urllib.request, "urlopen",
                        _fake_urlopen_with(exc=boom))
    with pytest.raises(RuntimeError) as ei:
        vpc.fetch_schedules("acct", "w", "sekrit")
    assert "HTTP 404" in str(ei.value)
    assert "sekrit" not in str(ei.value)


def test_fetch_schedules_url_error_is_runtime_error(monkeypatch):
    def boom(url):
        return vpc.urllib.error.URLError("boom")
    monkeypatch.setattr(vpc.urllib.request, "urlopen",
                        _fake_urlopen_with(exc=boom))
    with pytest.raises(RuntimeError) as ei:
        vpc.fetch_schedules("acct", "w", "sekrit")
    assert "boom" in str(ei.value)


def test_fetch_schedules_non_json_body_is_runtime_error(monkeypatch):
    monkeypatch.setattr(vpc.urllib.request, "urlopen",
                        _fake_urlopen_with(b"not json"))
    with pytest.raises(RuntimeError):
        vpc.fetch_schedules("acct", "w", "sekrit")


def test_fetch_schedules_api_failure_body_is_runtime_error(monkeypatch):
    monkeypatch.setattr(vpc.urllib.request, "urlopen", _fake_urlopen_with(
        json.dumps({"result": [], "success": False,
                    "errors": [{"message": "boom"}]}).encode()))
    with pytest.raises(RuntimeError):
        vpc.fetch_schedules("acct", "w", "sekrit")


def test_fetch_schedules_non_object_json_is_runtime_error(monkeypatch):
    # A valid-JSON scalar payload (e.g. `[1, 2]`) must map to the API
    # error path (exit 2 at the CLI), never an AttributeError traceback.
    monkeypatch.setattr(vpc.urllib.request, "urlopen",
                        _fake_urlopen_with(b"[1, 2]"))
    with pytest.raises(RuntimeError) as ei:
        vpc.fetch_schedules("acct", "w", "sekrit")
    assert "non-object" in str(ei.value)


def test_fetch_schedules_read_error_is_runtime_error(monkeypatch):
    # resp.read() raising mid-read must map to the API error path.
    monkeypatch.setattr(vpc.urllib.request, "urlopen", _fake_urlopen_with(
        b"{}", read_exc=vpc.urllib.error.URLError("reset")))
    with pytest.raises(RuntimeError) as ei:
        vpc.fetch_schedules("acct", "w", "sekrit")
    assert "reset" in str(ei.value)


def test_fetch_schedules_read_timeout_is_runtime_error(monkeypatch):
    # A stalled connection mid-read raises socket.timeout (TimeoutError),
    # which urlopen does NOT wrap in URLError — it must still map to the
    # API error path, never a traceback.
    monkeypatch.setattr(vpc.urllib.request, "urlopen", _fake_urlopen_with(
        b"{}", read_exc=socket.timeout("timed out")))
    with pytest.raises(RuntimeError) as ei:
        vpc.fetch_schedules("acct", "w", "sekrit")
    assert "timed out" in str(ei.value)
    assert "sekrit" not in str(ei.value)


def test_fetch_schedules_read_truncated_body_is_runtime_error(monkeypatch):
    # A truncated response body raises http.client.IncompleteRead,
    # unwrapped — same API-error mapping.
    monkeypatch.setattr(vpc.urllib.request, "urlopen", _fake_urlopen_with(
        b"{}", read_exc=vpc.http.client.IncompleteRead(b"partial", 10)))
    with pytest.raises(RuntimeError) as ei:
        vpc.fetch_schedules("acct", "w", "sekrit")
    assert "IncompleteRead" in str(ei.value)
    assert "sekrit" not in str(ei.value)


def test_fixture_non_object_json_is_usage_error_not_traceback(
        capsys, tmp_path):
    fixture = tmp_path / "list.json"
    fixture.write_text("[1, 2]", encoding="utf-8")
    code = vpc.main(["--fixture", str(fixture)])
    out = capsys.readouterr()
    assert code == 2
    assert "cannot read fixture" in out.err
    assert "Traceback" not in out.out and "Traceback" not in out.err


def test_missing_fixture_file_is_usage_error(capsys, tmp_path):
    code = vpc.main(["--fixture", str(tmp_path / "nope.json")])
    out = capsys.readouterr()
    assert code == 2
    assert "cannot read fixture" in out.err
    assert "Traceback" not in out.err


def test_live_malformed_payload_is_usage_error_not_trigger_missing(
        capsys, monkeypatch, tmp_path):
    # A malformed-but-successful live API payload is a check error
    # (exit 2), never "triggers missing" (exit 1) — and never a
    # traceback on stdout.
    monkeypatch.setattr(vpc.urllib.request, "urlopen", _fake_urlopen_with(
        json.dumps({"result": [{"cron": None}],
                    "success": True}).encode()))
    monkeypatch.setenv("CF_API_TOKEN", "sekrit")
    monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
    code = vpc.main(["--account-id", "acct"])
    out = capsys.readouterr()
    assert code == 2
    assert "cannot read fixture" not in out.out
    assert "Traceback" not in out.out and "Traceback" not in out.err
    assert "sekrit" not in out.out and "sekrit" not in out.err
