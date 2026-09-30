"""Secret scanning on the operator->agent funnel (issue #9).

The spawn prompt and every steer message are typed into the TUI and
persisted in the agent's session store; the "agent never sees real secrets"
property rests on operator discipline at these two chokepoints. These tests
pin the scanner's pattern coverage, the hsurr:-placeholder exemption, the
refusal behavior, and the no-secret-echo guarantee.
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
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_secretscan", CLI_PATH)


@pytest.mark.parametrize("secret,label", [
    ("sk-" + "abcdefghij1234567890XYZ", "OpenAI-style API key"),
    ("sk-ant-" + "abc-def-ghi-jkl-mnop", "Anthropic API key"),
    ("ghp_abcdefghijklmnopqrstuv", "GitHub token"),
    ("github_" + "pat_abcdefghijklmnopqrstuv", "GitHub fine-grained PAT"),
    ("AK" + "IAIOSFODNN7EXAMPLE", "AWS access key id"),
    ("xoxb-123456789012-abcdef123456", "Slack token"),
    ("glpat-abcdefghijklmno12", "GitLab personal access token"),
    ("hf_abcdefghijklmnopqrstuv", "Hugging Face token"),
    ("sk_live_abcdefghijklmnop", "Stripe key"),
    ("-----BEG" + "IN RSA PRIVATE KEY-----", "PEM private key"),
    ("-----BEG" + "IN OPENSSH PRIVATE KEY-----", "PEM private key"),
    ("AIzaSyC0123456789abcdef0123456789abcdef", "Google API key"),
    ("eyJzdWIiOiIxMjM0NTY3ODkwIn0.eyJzdWIiOiIxMjM0In0."
     "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c", "JWT"),
    # Engineering B1: sk-proj- is the current default OpenAI key format
    ("sk-proj-abcdefghij1234567890XYZABCD", "OpenAI-style API key"),
    # Engineering B2: underscore-prefixed env-var paste shapes
    ("db_password=hunter2hunter2", "credential assignment"),
    ("AWS_SECRET_ACCESS_KEY = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
     "credential assignment"),
    # Engineering B3: bare `token` keyword
    ("api_token=abcdef1234567890", "credential assignment"),
    ("token: deadbeef1234567890", "credential assignment"),
    ("github_token = somevalue12345", "credential assignment"),
    # Engineering nit: STS temp creds, xoxe-, lowercase pasted curl
    ("ASIAIOSFODNN7EXAMPLE", "AWS temporary access key id"),
    ("xoxe-123456789012-abcdef123456", "Slack token"),
    ("authorization: bearer abcdefghijklmnop1234", "bearer token"),
    ("postgres://admin:hunter2-secret@db:5432/app",
     "database connection string"),
    ("dGhpcyBpcyBhIHJlYWxseSBsb25nIHNlY3JldCBibG9iIQ==",
     "long base64 credential blob"),
    ("password = hunter2-hunter2", "credential assignment"),
    ("password: change-me-please", "credential assignment"),
    ("API_KEY: abcdefgh", "credential assignment"),
    ("Authorization: Bearer abcdefghijklmnop1234", "bearer token"),
])
def test_secret_patterns_fire(cli, secret, label):
    findings = dict(cli.scan_for_secrets(f"do the thing with {secret} now"))
    assert findings.get(label), f"{label} did not fire on {secret[:8]}..."


@pytest.mark.parametrize("clean", [
    "reset your password regularly",                    # prose, no = or :
    "I like sk-etching the deck",                       # sk- too short
    "the api key was revoked last week",                # no value attached
    "use akia to log in, not the key id",               # lowercase, no value
    "xox means hugs and kisses",                        # xox without dash
    "password: hsurr:rotate-me",                        # placeholder only
    "Bearer capability tokens are issued per session",  # bearer too short
    "Password: must be at least 12 characters",         # value too short
    "api_key = your-key-here",                          # placeholder sentinel
    "secret = none",                                    # value too short
    "https://example.com:8080/docs",                    # URL port, no userinfo
    "passwords = hunter2hunter2",                       # keyword must be exact
    "mytoken=abcdef1234567890",                         # token must be exact
    "the token was revoked",                            # no value attached
])
def test_benign_text_scans_clean(cli, clean):
    assert cli.scan_for_secrets(clean) == []


def test_hsurr_placeholder_assignments_are_exempt(cli):
    assert cli.scan_for_secrets("api_key: hsurr:stripe-prod") == []
    assert cli.scan_for_secrets("password=hsurr:db-root") == []
    assert cli.scan_for_secrets(
        "Authorization: Bearer hsurr:ops-token") == []


def test_secret_shaped_placeholder_names_are_findings(cli):
    # hsurr: is not a smuggling channel: a secret-shaped name would land
    # verbatim in the TUI (unregistered names stay literal), so it fires.
    findings = dict(cli.scan_for_secrets(
        "use hsurr:sk-" + "abcdefghij1234567890XYZ for this"))
    assert findings.get("secret-shaped credential placeholder")
    findings = dict(cli.scan_for_secrets("key hsurr:AK" + "IAIOSFODNN7EXAMPLE"))
    assert findings.get("secret-shaped credential placeholder")
    # A smuggled AWS-style secret whose charset breaks the placeholder name
    # still fires: the invalid tail reattaches to the assignment value.
    findings = dict(cli.scan_for_secrets(
        "api_key = hsurr:wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"))
    assert findings.get("credential assignment")


def test_real_secret_beside_placeholder_still_fires(cli):
    findings = dict(cli.scan_for_secrets(
        "api_key: hsurr:stripe-prod sk-" + "abcdefghij1234567890XYZ"))
    assert "OpenAI-style API key" in findings
    # the placeholder is gone, so `api_key:` now points at the real token --
    # the assignment pattern legitimately fires too
    assert "credential assignment" in findings


def test_findings_never_echo_the_secret(cli):
    secret = "sk-" + "abcdefghij1234567890XYZ"
    findings = cli.scan_for_secrets(f"token {secret} here")
    blob = repr(findings)
    assert secret not in blob


def test_gate_refuses_without_allow(cli):
    with pytest.raises(RuntimeError) as exc:
        cli.require_no_secrets("deploy with ghp_abcdefghijklmnopqrstuv",
                               "steer message", allow=False)
    msg = str(exc.value)
    assert "steer message" in msg
    assert "GitHub token" in msg
    assert "ghp_abcdefghijklmnopqrstuv" not in msg  # never echoed
    assert "--allow-secrets" in msg
    assert "hsurr:" in msg


def test_gate_passes_with_allow(cli, capsys):
    findings = cli.require_no_secrets("deploy with ghp_abcdefghijklmnopqrstuv",
                                      "steer message", allow=True)
    assert findings  # it still reports what it found
    # ... and says so on stderr (stdout must stay a single JSON document),
    # so an accidental --allow-secrets is visible, not silent
    err = capsys.readouterr().err
    assert "muse-job: warning" in err
    assert "--allow-secrets" in err
    assert "ghp_abcdefghijklmnopqrstuv" not in err  # never echoed


def test_gate_passes_clean_text(cli):
    assert cli.require_no_secrets("use tabs instead", "steer message") == []


def test_gate_returns_labelled_counts(cli):
    findings = cli.require_no_secrets(
        "sk-" + "abcdefghij1234567890XYZ and sk-" + "ZYXWVUTSRQPO0987654321", "x",
        allow=True)
    assert dict(findings) == {"OpenAI-style API key": 2}
