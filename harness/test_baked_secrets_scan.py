"""Tests for harness/scan-baked-secrets.sh (GitHub #154).

Hermetic: every test builds its own scratch tree under tmp_path and scans
it — the real image root is never touched. Refusal tests are inherently
non-vacuous: each asserts exit 1, which a no-op or broken scan cannot
produce.
"""

import os
import subprocess

HARNESS = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(HARNESS, "scan-baked-secrets.sh")
DUMMY = "GATE-FIXTURE-DUMMY-NOT-A-SECRET"  # public by design, must stay allowed


def run_scan(target, *extra):
    return subprocess.run(
        [SCAN, str(target), *extra],
        capture_output=True, text=True, timeout=120,
    )


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# --- clean trees -----------------------------------------------------------

def test_clean_tree_passes(tmp_path):
    write(tmp_path / "etc" / "motd", "welcome to the box\n")
    write(tmp_path / "opt" / "app" / "config.yaml",
          "inference_key: hsurr:llm-api\n")  # placeholders are the sanctioned shape
    (tmp_path / "home" / "swapd" / "secrets").mkdir(parents=True)
    p = run_scan(tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "clean" in p.stdout


def test_secrets_dir_fixture_dummy_allowed(tmp_path):
    d = tmp_path / "home" / "swapd" / "inference-secrets"
    d.mkdir(parents=True)
    (d / "llm-api").write_text(DUMMY)  # exact bytes, no trailing newline
    p = run_scan(tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr


def test_secrets_dir_empty_file_allowed(tmp_path):
    d = tmp_path / "home" / "swapd" / "secrets"
    d.mkdir(parents=True)
    (d / "placeholder").write_text("")
    p = run_scan(tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr


def test_pseudo_filesystems_excluded(tmp_path):
    # At gate time the target is the image root (/); /proc, /sys, /dev
    # must not be scanned (unreadable entries, device nodes).
    write(tmp_path / "proc" / "evil",
          "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n")
    p = run_scan(tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr


# --- content patterns ------------------------------------------------------

def test_pem_private_key_refused(tmp_path):
    write(tmp_path / "home" / "swapd" / "ca-key.pem",
          "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT pem-private-key" in p.stdout


def test_pkcs8_private_key_refused(tmp_path):
    write(tmp_path / "etc" / "skel" / "key",
          "-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2Vw...\n-----END PRIVATE KEY-----\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT pem-private-key" in p.stdout


def test_aws_access_key_refused(tmp_path):
    write(tmp_path / "root" / "notes.txt", "deploy with AKIAIOSFODNN7EXAMPLE\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT aws-access-key-id" in p.stdout


def test_github_token_refused(tmp_path):
    write(tmp_path / "root" / ".bash_history", "export GH=" + "ghp_" + "a" * 36 + "\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT github-token" in p.stdout


def test_openai_key_refused(tmp_path):
    write(tmp_path / "opt" / "app" / "config.yaml", "api_key: " + "sk-" + "b" * 24 + "\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT openai-api-key" in p.stdout


def test_anthropic_key_refused(tmp_path):
    write(tmp_path / "opt" / "app" / "config.yaml",
          "anthropic_key: " + "sk-ant-" + "c" * 24 + "\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT anthropic-api-key" in p.stdout


# --- filename globs --------------------------------------------------------

def test_ssh_private_key_filename_refused(tmp_path):
    write(tmp_path / "home" / "agent" / ".ssh" / "id_ed25519", "whatever\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT ssh-private-key" in p.stdout


def test_dotenv_filename_refused(tmp_path):
    write(tmp_path / "srv" / "app" / ".env", "DB_PASSWORD=hunter2\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT dotenv-file" in p.stdout


def test_auth_json_filename_refused(tmp_path):
    write(tmp_path / "home" / "agent" / "auth.json", "{}\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT auth-json" in p.stdout


# --- secrets-dir rule ------------------------------------------------------

def test_secrets_dir_real_value_refused(tmp_path):
    d = tmp_path / "home" / "swapd" / "secrets"
    d.mkdir(parents=True)
    (d / "db-password").write_text("s3cr3t-real-value\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT secret-store-value" in p.stdout


def test_secrets_dir_dummy_with_newline_refused(tmp_path):
    # The fixture installs the dummy with no trailing newline; a
    # newline-suffixed copy is not the allowlisted value — fail closed.
    d = tmp_path / "home" / "swapd" / "inference-secrets"
    d.mkdir(parents=True)
    (d / "llm-api").write_text(DUMMY + "\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT secret-store-value" in p.stdout


def test_secrets_dir_symlink_refused(tmp_path):
    d = tmp_path / "home" / "swapd" / "secrets"
    d.mkdir(parents=True)
    (tmp_path / "elsewhere").write_text("x\n")
    (d / "link").symlink_to(tmp_path / "elsewhere")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT secret-store-symlink" in p.stdout


def test_secrets_dir_subdir_refused(tmp_path):
    d = tmp_path / "home" / "swapd" / "secrets"
    (d / "nested").mkdir(parents=True)
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT secret-store-unexpected" in p.stdout


def test_binary_secret_value_refused(tmp_path):
    # Byte-exact compare: binary values cannot slip past a text check.
    d = tmp_path / "home" / "swapd" / "secrets"
    d.mkdir(parents=True)
    (d / "blob").write_bytes(b"\x00\x01\x02binary-secret")
    p = run_scan(tmp_path)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "HIT secret-store-value" in p.stdout


# --- invocation / parser ---------------------------------------------------

def test_no_args_exit_2():
    p = subprocess.run([SCAN], capture_output=True, text=True, timeout=30)
    assert p.returncode == 2


def test_missing_target_exit_2(tmp_path):
    p = run_scan(tmp_path / "does-not-exist")
    assert p.returncode == 2


def test_malformed_patterns_exit_2(tmp_path):
    bad = tmp_path / "bad-patterns.txt"
    bad.write_text("this line has no kind delimiter\n")
    p = run_scan(tmp_path, "--patterns", str(bad))
    assert p.returncode == 2


def test_unknown_kind_exit_2(tmp_path):
    bad = tmp_path / "bad-patterns.txt"
    bad.write_text("bogus: some-id: whatever\n")
    p = run_scan(tmp_path, "--patterns", str(bad))
    assert p.returncode == 2


def test_patterns_file_self_exclusion(tmp_path):
    # A patterns file living inside the target tree must not flag its
    # own definitions: the canary rule matches this file's own comment.
    pat = tmp_path / "patterns.txt"
    pat.write_text(
        "# canary: the rule below matches this very comment line;\n"
        "# without self-exclusion the scan would flag its own patterns.\n"
        "content: canary: CANARY-BAIT-STRING\n"
        "# CANARY-BAIT-STRING appears here on purpose\n"
    )
    p = run_scan(tmp_path, "--patterns", str(pat))
    assert p.returncode == 0, p.stdout + p.stderr
    assert "clean" in p.stdout


def test_refusal_report_shape(tmp_path):
    write(tmp_path / "leak.txt", "key: " + "AKIAIOSFODNN7EXAMPLE" + "\n")
    p = run_scan(tmp_path)
    assert p.returncode == 1
    assert "baked-secrets-scan: HIT aws-access-key-id" in p.stdout
    assert "REFUSED" in p.stderr
