"""Tests for the #1204 host-key attestation half of
deploy/golden-image/sparkvm-sshd-firstboot.sh (D-D3).

The script is exercised as a real subprocess with the test seams pointing
at tmp dirs (never the real /etc/ssh, /data, or /run) and
SPARKVM_FIRSTBOOT_NO_EXEC=1 so the final sshd exec never fires.
`ssh-keygen -A` is stubbed on PATH (it would otherwise write to the real
/etc/ssh); every other ssh-keygen verb delegates to the real binary so the
env-key validation path runs against real crypto.
"""
import base64
import os
import re
import shutil
import stat
import subprocess

import pytest

GOLDEN_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(GOLDEN_DIR, "sparkvm-sshd-firstboot.sh")

REAL_SSH_KEYGEN = shutil.which("ssh-keygen")
NEEDS_SSH_KEYGEN = pytest.mark.skipif(
    REAL_SSH_KEYGEN is None, reason="ssh-keygen not installed"
)

STUB_SSH_KEYGEN = """#!/bin/bash
# -A writes fake key files into the seam dir; everything else delegates.
if [ "$1" = "-A" ]; then
    d="${SPARKVM_SSH_ETC_DIR:?}"
    for t in rsa ecdsa ed25519; do
        printf 'fake-%s-private\\n' "$t" > "$d/ssh_host_${t}_key"
        chmod 600 "$d/ssh_host_${t}_key"
        printf 'fake-%s-public\\n' "$t" > "$d/ssh_host_${t}_key.pub"
    done
    exit 0
fi
exec "__REAL__" "$@"
"""


def _gen_key(tmpdir, keytype, passphrase=""):
    keypath = os.path.join(str(tmpdir), f"mint-{keytype}")
    subprocess.run(
        [REAL_SSH_KEYGEN, "-t", keytype, "-N", passphrase, "-C", "",
         "-f", keypath, "-q"],
        check=True, timeout=60,
    )
    return keypath


@pytest.fixture()
def harness(tmp_path, monkeypatch):
    etc = tmp_path / "etc-ssh"
    etc.mkdir()
    status = tmp_path / "status"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    if REAL_SSH_KEYGEN:
        (bindir / "ssh-keygen").write_text(
            STUB_SSH_KEYGEN.replace("__REAL__", REAL_SSH_KEYGEN)
        )
        (bindir / "ssh-keygen").chmod(0o755)
    env = {
        "SPARKVM_SSH_ETC_DIR": str(etc),
        "SPARKVM_SSH_RUN_DIR": str(tmp_path / "run-sshd"),
        "SPARKVM_SSH_STATUS_DIR": str(status),
        "SPARKVM_DATA_ROOT": str(tmp_path / "no-data"),  # absent -> volume path no-ops
        "SPARKVM_FIRSTBOOT_NO_EXEC": "1",
        "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
    }

    def run(extra_env=None):
        e = dict(env)
        e.update(extra_env or {})
        return subprocess.run(
            ["bash", SCRIPT], env=e, capture_output=True, text=True, timeout=60
        )

    return run, etc, status, tmp_path


def _b64_of_private(keypath):
    with open(keypath, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _fingerprint(keypath):
    out = subprocess.run(
        [REAL_SSH_KEYGEN, "-lf", keypath, "-E", "sha256"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return out.stdout.split()[1]


def _read_status(status):
    p = status / "ssh_host_key.status"
    assert p.exists(), "status receipt missing"
    kv = {}
    for line in p.read_text().splitlines():
        k, _, v = line.partition("=")
        kv[k] = v
    return kv


@NEEDS_SSH_KEYGEN
def test_env_key_installed_with_precedence(harness):
    run, etc, status, tmp_path = harness
    # Pre-existing self-generated keys (the reimaged-rootfs hazard): the
    # attested key must win.
    (etc / "ssh_host_ed25519_key").write_text("stale-self-generated-private\n")
    (etc / "ssh_host_ed25519_key.pub").write_text("stale-self-generated-public\n")
    (etc / "ssh_host_rsa_key").write_text("stale-rsa\n")
    (etc / "ssh_host_rsa_key.pub").write_text("stale-rsa-pub\n")
    (etc / "ssh_host_ecdsa_key").write_text("stale-ecdsa\n")
    (etc / "ssh_host_ecdsa_key.pub").write_text("stale-ecdsa-pub\n")
    keypath = _gen_key(tmp_path, "ed25519")
    b64 = _b64_of_private(keypath)
    fp = _fingerprint(keypath)

    proc = run({"SPARKVM_SSH_HOST_KEYS": b64})
    assert proc.returncode == 0, proc.stderr
    dest = etc / "ssh_host_ed25519_key"
    with open(keypath, "rb") as f:
        assert dest.read_bytes() == f.read(), "attested key content not installed"
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    pub = etc / "ssh_host_ed25519_key.pub"
    assert stat.S_IMODE(pub.stat().st_mode) == 0o644
    out = subprocess.run(
        [REAL_SSH_KEYGEN, "-y", "-f", str(dest)],
        capture_output=True, text=True, check=True, timeout=30,
    )
    assert pub.read_text().strip() == out.stdout.strip()
    # Non-attested key pairs are gone; ssh-keygen -A must not have run.
    assert not (etc / "ssh_host_rsa_key").exists()
    assert not (etc / "ssh_host_rsa_key.pub").exists()
    assert not (etc / "ssh_host_ecdsa_key").exists()
    assert not (etc / "ssh_host_ecdsa_key.pub").exists()
    assert "installed attested ed25519 host key" in proc.stderr
    assert fp in proc.stderr
    kv = _read_status(status)
    assert kv["source"] == "env"
    assert kv["key_type"] == "ed25519"
    assert kv["fingerprint_sha256"] == fp


@NEEDS_SSH_KEYGEN
def test_env_key_idempotent(harness):
    run, etc, status, tmp_path = harness
    keypath = _gen_key(tmp_path, "ed25519")
    b64 = _b64_of_private(keypath)
    env = {"SPARKVM_SSH_HOST_KEYS": b64}
    first = run(env)
    assert first.returncode == 0, first.stderr
    dest = etc / "ssh_host_ed25519_key"
    mtime = dest.stat().st_mtime_ns
    second = run(env)
    assert second.returncode == 0, second.stderr
    assert dest.stat().st_mtime_ns == mtime, "reinstall rewrote an identical key"
    assert "already installed" in second.stderr


@NEEDS_SSH_KEYGEN
def test_env_invalid_base64_fails_closed(harness):
    run, etc, status, tmp_path = harness
    # A stale self-generated key must be left untouched — no fallback.
    (etc / "ssh_host_ed25519_key").write_text("stale\n")
    proc = run({"SPARKVM_SSH_HOST_KEYS": "!!!not-base64!!!"})
    assert proc.returncode != 0
    assert "FATAL" in proc.stderr
    assert "unattested" in proc.stderr
    assert (etc / "ssh_host_ed25519_key").read_text() == "stale\n"
    assert not (status / "ssh_host_key.status").exists()


@NEEDS_SSH_KEYGEN
def test_env_non_pem_fails_closed(harness):
    run, etc, status, tmp_path = harness
    b64 = base64.b64encode(b"definitely not a private key").decode("ascii")
    proc = run({"SPARKVM_SSH_HOST_KEYS": b64})
    assert proc.returncode != 0
    assert "not an OpenSSH private key" in proc.stderr
    assert not (etc / "ssh_host_ed25519_key").exists()


@NEEDS_SSH_KEYGEN
def test_env_non_ed25519_rejected(harness):
    run, etc, status, tmp_path = harness
    keypath = _gen_key(tmp_path, "rsa")
    proc = run({"SPARKVM_SSH_HOST_KEYS": _b64_of_private(keypath)})
    assert proc.returncode != 0
    assert "not an ed25519 key" in proc.stderr
    assert not (etc / "ssh_host_ed25519_key").exists()


@NEEDS_SSH_KEYGEN
def test_env_passphrase_key_rejected_without_prompt(harness):
    # The </dev/null guard: a passphrase key must fail, never hang on a prompt.
    run, etc, status, tmp_path = harness
    keypath = _gen_key(tmp_path, "ed25519", passphrase="secret")
    proc = run({"SPARKVM_SSH_HOST_KEYS": _b64_of_private(keypath)})
    assert proc.returncode != 0
    assert "not a usable private key" in proc.stderr


@NEEDS_SSH_KEYGEN
def test_env_empty_string_fails_closed(harness):
    # Set-but-empty is present-but-invalid: it must fail closed, never
    # silently fall back to self-generation.
    run, etc, status, tmp_path = harness
    proc = run({"SPARKVM_SSH_HOST_KEYS": ""})
    assert proc.returncode != 0
    assert "FATAL" in proc.stderr
    assert "generating missing" not in proc.stderr
    assert list(etc.iterdir()) == [], "no keys may be generated on this path"
    assert not (status / "ssh_host_key.status").exists()


@NEEDS_SSH_KEYGEN
def test_env_install_through_dangling_volume_symlinks(harness):
    # The fresh-provisioned D-V3 layout: /etc/ssh holds DANGLING symlinks
    # into /data/ssh (targets don't exist yet). GNU cp refuses to write
    # through a dangling symlink — the install must resolve the real path.
    run, etc, status, tmp_path = harness
    data_ssh = tmp_path / "data-ssh"
    data_ssh.mkdir()
    for t in ("rsa", "ecdsa", "ed25519"):
        (etc / f"ssh_host_{t}_key").symlink_to(data_ssh / f"ssh_host_{t}_key")
        (etc / f"ssh_host_{t}_key.pub").symlink_to(
            data_ssh / f"ssh_host_{t}_key.pub")
    keypath = _gen_key(tmp_path, "ed25519")
    b64 = _b64_of_private(keypath)
    fp = _fingerprint(keypath)
    proc = run({"SPARKVM_SSH_HOST_KEYS": b64})
    assert proc.returncode == 0, proc.stderr
    assert "installed attested ed25519 host key" in proc.stderr
    # The key material landed at the symlink TARGET (on the "volume").
    target = data_ssh / "ssh_host_ed25519_key"
    assert target.exists(), "attested key never reached the volume"
    with open(keypath, "rb") as f:
        assert target.read_bytes() == f.read()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert (data_ssh / "ssh_host_ed25519_key.pub").exists()
    kv = _read_status(status)
    assert kv["source"] == "env"
    assert kv["fingerprint_sha256"] == fp
    # The other pairs' links are gone (attested ed25519 is the whole
    # serving identity on this path).
    assert not (etc / "ssh_host_rsa_key").exists()
    assert not (etc / "ssh_host_rsa_key").is_symlink()


@NEEDS_SSH_KEYGEN
def test_env_install_failure_is_fatal(harness):
    # The install tail runs with set -e disabled (OR-list call context):
    # an operational failure must still be loud and nonzero, never a
    # false "installed" claim with a lying receipt.
    run, etc, status, tmp_path = harness
    bad = tmp_path / "no-such-dir"  # dangling target, unresolvable parent
    (etc / "ssh_host_ed25519_key").symlink_to(bad / "ssh_host_ed25519_key")
    (etc / "ssh_host_ed25519_key.pub").symlink_to(
        bad / "ssh_host_ed25519_key.pub")
    keypath = _gen_key(tmp_path, "ed25519")
    proc = run({"SPARKVM_SSH_HOST_KEYS": _b64_of_private(keypath)})
    assert proc.returncode != 0
    assert "FATAL" in proc.stderr
    assert "installed attested" not in proc.stderr
    assert not (status / "ssh_host_key.status").exists()


@NEEDS_SSH_KEYGEN
def test_env_key_material_never_logged(harness):
    run, etc, status, tmp_path = harness
    keypath = _gen_key(tmp_path, "ed25519")
    b64 = _b64_of_private(keypath)
    with open(keypath, "rb") as f:
        raw_b64_tail = base64.b64encode(f.read()).decode("ascii")[40:80]
    proc = run({"SPARKVM_SSH_HOST_KEYS": b64})
    assert proc.returncode == 0, proc.stderr
    combined = proc.stdout + proc.stderr
    assert b64 not in combined
    assert raw_b64_tail not in combined
    assert "PRIVATE KEY" not in combined


@NEEDS_SSH_KEYGEN
def test_absent_env_generates_missing(harness):
    run, etc, status, tmp_path = harness
    proc = run()
    assert proc.returncode == 0, proc.stderr
    assert "generating missing sshd host keys" in proc.stderr
    assert (etc / "ssh_host_ed25519_key").read_text().startswith("fake-ed25519")
    kv = _read_status(status)
    assert kv["source"] == "self-generated"


@NEEDS_SSH_KEYGEN
def test_absent_env_existing_keys_untouched(harness):
    run, etc, status, tmp_path = harness
    (etc / "ssh_host_ed25519_key").write_text("keepme\n")
    (etc / "ssh_host_rsa_key").write_text("keepme\n")
    (etc / "ssh_host_ecdsa_key").write_text("keepme\n")
    proc = run()
    assert proc.returncode == 0, proc.stderr
    assert "generating missing" not in proc.stderr
    assert (etc / "ssh_host_ed25519_key").read_text() == "keepme\n"


def test_status_dir_is_a_seam_and_host_keys_is_not():
    text = open(SCRIPT).read()
    m = re.search(r"_SEAMS=\(([^)]*)\)", text)
    assert m, "_SEAMS declaration not found"
    seams = m.group(1).split()
    assert "SPARKVM_SSH_STATUS_DIR" in seams
    # SPARKVM_SSH_HOST_KEYS is a production driver-injected var: listing it
    # as a seam would fire the loud root-run WARNING on every provisioned box.
    assert "SPARKVM_SSH_HOST_KEYS" not in seams
    # ...but it must be classified in _PROD_ENV (never unclassified).
    pm = re.search(r"_PROD_ENV=\(([^)]*)\)", text)
    assert pm, "_PROD_ENV declaration not found"
    assert "SPARKVM_SSH_HOST_KEYS" in pm.group(1).split()
