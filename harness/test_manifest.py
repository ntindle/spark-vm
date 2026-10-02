"""Tests for harness/generate-image-manifest.sh and check-image-manifest.sh."""

import json
import os
import shutil
import subprocess

HARNESS = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HARNESS, "generate-image-manifest.sh")
CHECK = os.path.join(HARNESS, "check-image-manifest.sh")
SCHEMA = "sparkvm/golden-image-manifest@1"


def git_head():
    return subprocess.run(
        ["git", "-C", os.path.join(HARNESS, ".."), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=30,
    ).stdout.strip()


def test_generate_emits_valid_manifest(tmp_path):
    out = tmp_path / "manifest.json"
    p = subprocess.run([GEN, "--out", str(out)], capture_output=True,
                       text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    m = json.loads(out.read_text())
    assert m["schema"] == SCHEMA
    assert m["image_version"] == git_head()
    assert m["built_from_version"]
    assert isinstance(m["baked"], list) and len(m["baked"]) >= 5
    for key in ("inference_registry", "inference_hosts", "inference_secrets",
                "main_registry", "grants"):
        assert m["registry_paths"][key].startswith("/home/swapd/"), key
    assert "swap-inference.service" in m["units"]
    assert "confirmd.service" in m["units"]
    assert "push-worker.service" in m["units"]
    assert m["injector_expect"]["probe_path"] == "harness/harness-auth-probe"
    assert m["injector_expect"]["probe_modes"] == ["gate", "provision"]
    # No secret material may ever appear in a manifest.
    blob = out.read_text()
    assert "hsurr:" not in blob or "hsurr:<name>" in blob


def test_check_passes_fresh_manifest(tmp_path):
    out = tmp_path / "manifest.json"
    subprocess.run([GEN, "--out", str(out)], check=True, timeout=30,
                   capture_output=True)
    p = subprocess.run([CHECK, str(out)], capture_output=True, text=True,
                       timeout=30)
    assert p.returncode == 0, p.stderr
    assert "OK" in p.stderr


def test_check_fails_on_version_drift(tmp_path):
    out = tmp_path / "manifest.json"
    subprocess.run([GEN, "--out", str(out)], check=True, timeout=30,
                   capture_output=True)
    m = json.loads(out.read_text())
    m["image_version"] = "0" * 40
    out.write_text(json.dumps(m))
    p = subprocess.run([CHECK, str(out)], capture_output=True, text=True,
                       timeout=30)
    assert p.returncode == 1
    assert "DRIFT" in p.stderr


def test_check_fails_on_expect_version_mismatch(tmp_path):
    out = tmp_path / "manifest.json"
    subprocess.run([GEN, "--out", str(out)], check=True, timeout=30,
                   capture_output=True)
    p = subprocess.run([CHECK, str(out), "--expect-version", "1" * 40],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "DRIFT" in p.stderr


def test_check_fails_on_missing_keys(tmp_path):
    out = tmp_path / "manifest.json"
    subprocess.run([GEN, "--out", str(out)], check=True, timeout=30,
                   capture_output=True)
    m = json.loads(out.read_text())
    del m["units"]
    out.write_text(json.dumps(m))
    p = subprocess.run([CHECK, str(out)], capture_output=True, text=True,
                       timeout=30)
    assert p.returncode == 1
    assert "missing keys" in p.stderr


def test_check_fails_on_schema_mismatch(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "something-else@9"}))
    p = subprocess.run([CHECK, str(bad)], capture_output=True, text=True,
                       timeout=30)
    assert p.returncode == 1
    assert "schema" in p.stderr


def test_check_fails_on_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    p = subprocess.run([CHECK, str(bad)], capture_output=True, text=True,
                       timeout=30)
    assert p.returncode == 1


def test_check_fails_on_missing_file(tmp_path):
    p = subprocess.run([CHECK, str(tmp_path / "nope.json")], capture_output=True,
                       text=True, timeout=30)
    assert p.returncode == 1


def _fresh_manifest(tmp_path):
    out = tmp_path / "manifest.json"
    subprocess.run([GEN, "--out", str(out)], check=True, timeout=30,
                   capture_output=True)
    return out


def test_check_fails_on_nested_missing_subkeys(tmp_path):
    out = _fresh_manifest(tmp_path)
    m = json.loads(out.read_text())
    del m["registry_paths"]["inference_hosts"]
    del m["injector_expect"]["probe_path"]
    out.write_text(json.dumps(m))
    p = subprocess.run([CHECK, str(out)], capture_output=True, text=True,
                       timeout=30)
    assert p.returncode == 1
    assert "missing keys" in p.stderr


def test_check_fails_cleanly_on_non_string_version(tmp_path):
    out = _fresh_manifest(tmp_path)
    m = json.loads(out.read_text())
    m["image_version"] = 12345
    out.write_text(json.dumps(m))
    p = subprocess.run([CHECK, str(out)], capture_output=True, text=True,
                       timeout=30)
    assert p.returncode == 1
    assert "Traceback" not in p.stderr
    assert "non-empty string" in p.stderr


def test_check_usage_errors(tmp_path):
    for argv in ([], ["a", "b", "c"]):
        p = subprocess.run([CHECK, *argv], capture_output=True, text=True,
                           timeout=30)
        assert p.returncode == 2, argv
        assert "usage" in p.stderr


def _scratch_repo_with_generator(tmp_path):
    """Copy the generator into a scratch git repo and return (gen_path, repo).

    The generator stamps the checkout it lives in, so a scratch repo lets us
    exercise the dirty-checkout guard without touching the real checkout.
    """
    scratch = tmp_path / "scratch"
    harness_dir = scratch / "harness"
    harness_dir.mkdir(parents=True)
    gen = harness_dir / "generate-image-manifest.sh"
    shutil.copy(GEN, gen)
    (scratch / "VERSION").write_text("0.0.0-test\n")
    for argv in (["git", "init"], ["git", "config", "user.email", "t@t"],
                 ["git", "config", "user.name", "t"],
                 # Hermetic against ambient gitconfig: a global commit.gpgsign
                 # would make the setup commit fail, and a global
                 # status.showUntrackedFiles=no would hide untracked files.
                 ["git", "config", "commit.gpgsign", "false"],
                 ["git", "config", "status.showUntrackedFiles", "normal"],
                 ["git", "add", "-A"],
                 ["git", "commit", "-m", "x"]):
        subprocess.run(argv, cwd=scratch, check=True, capture_output=True,
                       timeout=30)
    return str(gen), scratch


def test_generate_refuses_dirty_checkout(tmp_path):
    gen, scratch = _scratch_repo_with_generator(tmp_path)
    # Clean checkout: generates fine.
    p = subprocess.run([gen, "--out", str(tmp_path / "m1.json")],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    # Tracked modification: fail closed — a dirty tree must never be stamped
    # with a clean SHA.
    (scratch / "VERSION").write_text("0.0.0-dirty\n")
    p = subprocess.run([gen, "--out", str(tmp_path / "m2.json")],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 2
    assert "uncommitted changes" in p.stderr
    assert not (tmp_path / "m2.json").exists()
    # Untracked file: also a dirty tree (it would be baked too).
    (scratch / "VERSION").write_text("0.0.0-test\n")
    (scratch / "junk.txt").write_text("junk\n")
    p = subprocess.run([gen, "--out", str(tmp_path / "m3.json")],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 2
    assert "uncommitted changes" in p.stderr
    assert not (tmp_path / "m3.json").exists()
    # Staged-but-uncommitted change: still uncommitted, still refused.
    (scratch / "junk.txt").unlink()
    (scratch / "VERSION").write_text("0.0.0-staged\n")
    subprocess.run(["git", "add", "VERSION"], cwd=scratch, check=True,
                   capture_output=True, timeout=30)
    p = subprocess.run([gen, "--out", str(tmp_path / "m4.json")],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 2
    assert "uncommitted changes" in p.stderr
    assert not (tmp_path / "m4.json").exists()


# --- #155: Ed25519 manifest signing ---------------------------------------

SIGN = os.path.join(HARNESS, "sign-image-manifest.sh")


def _gen_keys(tmp_path, name="op"):
    priv = tmp_path / f"{name}.priv.pem"
    pub = tmp_path / f"{name}.pub.pem"
    p = subprocess.run([SIGN, "--gen-key", str(tmp_path / name)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    assert priv.exists() and pub.exists()
    return priv, pub


def _signed_manifest(tmp_path, name="m"):
    out = tmp_path / f"{name}.json"
    subprocess.run([GEN, "--out", str(out)], check=True, timeout=30,
                   capture_output=True)
    priv, pub = _gen_keys(tmp_path)
    p = subprocess.run([SIGN, str(out), "--key", str(priv)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    sig = out.with_suffix(".json.sig")
    assert sig.exists()
    return out, sig, priv, pub


def test_sign_verify_roundtrip(tmp_path):
    out, sig, priv, pub = _signed_manifest(tmp_path)
    p = subprocess.run([CHECK, str(out), "--pubkey", str(pub)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    assert "signature OK" in p.stderr and "check-image-manifest: OK" in p.stderr


def test_verify_fails_on_single_byte_tamper(tmp_path):
    # Non-vacuity pin for the signature gate: one flipped byte must fail,
    # even though image_version and the schema still parse.
    out, sig, priv, pub = _signed_manifest(tmp_path)
    raw = bytearray(out.read_bytes())
    raw[len(raw) // 2] ^= 0x01
    out.write_bytes(bytes(raw))
    p = subprocess.run([CHECK, str(out), "--pubkey", str(pub)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "SIGNATURE MISMATCH" in p.stderr


def test_verify_fails_on_wrong_key(tmp_path):
    # Signed by key A, verified against key B's pubkey: fail closed.
    out, sig, priv, pub = _signed_manifest(tmp_path)
    _, other_pub = _gen_keys(tmp_path, name="other")
    p = subprocess.run([CHECK, str(out), "--pubkey", str(other_pub)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "SIGNATURE MISMATCH" in p.stderr


def test_verify_fails_when_sig_missing(tmp_path):
    # --pubkey with no signature file: fail closed, not "unsigned is fine".
    out, sig, priv, pub = _signed_manifest(tmp_path)
    sig.unlink()
    p = subprocess.run([CHECK, str(out), "--pubkey", str(pub)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "SIGNATURE MISSING" in p.stderr


def test_verify_fails_on_malformed_sig(tmp_path):
    out, sig, priv, pub = _signed_manifest(tmp_path)
    sig.write_text("not-valid-base64!!!\n")
    p = subprocess.run([CHECK, str(out), "--pubkey", str(pub)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "failing closed" in p.stderr
    # Right shape, wrong length: also refused (decodes to 3 bytes, not 64).
    sig.write_text("AAAA\n")
    p = subprocess.run([CHECK, str(out), "--pubkey", str(pub)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "64 bytes" in p.stderr


def test_check_without_pubkey_keeps_legacy_behavior(tmp_path):
    # Backward compat while unsigned images are in service: no --pubkey
    # means the old self-attestation check, sig or no sig.
    out, sig, priv, pub = _signed_manifest(tmp_path)
    p = subprocess.run([CHECK, str(out)], capture_output=True, text=True,
                       timeout=30)
    assert p.returncode == 0, p.stderr
    assert "signature OK" not in p.stderr
    sig.unlink()
    p = subprocess.run([CHECK, str(out)], capture_output=True, text=True,
                       timeout=30)
    assert p.returncode == 0, p.stderr


def test_verify_runs_before_parse(tmp_path):
    # Garbage bytes + --pubkey: the failure is the missing signature, not a
    # JSON error — trust is established on bytes before any parse. An
    # attacker-shaped document never reaches the parser untrusted.
    junk = tmp_path / "junk.json"
    junk.write_text("{not json at all\x00\x01")
    p = subprocess.run([CHECK, str(junk), "--pubkey", str(tmp_path / "k.pub.pem")],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "SIGNATURE MISSING" in p.stderr
    assert "invalid JSON" not in p.stderr


def test_gen_key_refuses_overwrite(tmp_path):
    _gen_keys(tmp_path)
    p = subprocess.run([SIGN, "--gen-key", str(tmp_path / "op")],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "refusing to overwrite" in p.stderr


def test_gen_key_private_is_0600(tmp_path):
    priv, pub = _gen_keys(tmp_path)
    assert (priv.stat().st_mode & 0o777) == 0o600


def test_sign_refuses_group_readable_key(tmp_path):
    # The signing key is a capability: group/other-readable refuses,
    # mirroring fleet/gate_query.py's 0600 key discipline.
    out = tmp_path / "m.json"
    subprocess.run([GEN, "--out", str(out)], check=True, timeout=30,
                   capture_output=True)
    priv, pub = _gen_keys(tmp_path)
    priv.chmod(0o640)
    p = subprocess.run([SIGN, str(out), "--key", str(priv)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "group/other readable" in p.stderr
    assert not out.with_suffix(".json.sig").exists()


def test_sign_refuses_symlink_manifest(tmp_path):
    # TOCTOU discipline: signing through a symlink would bind the signature
    # to bytes the caller didn't name.
    out = tmp_path / "real.json"
    subprocess.run([GEN, "--out", str(out)], check=True, timeout=30,
                   capture_output=True)
    priv, pub = _gen_keys(tmp_path)
    link = tmp_path / "link.json"
    link.symlink_to(out)
    p = subprocess.run([SIGN, str(link), "--key", str(priv)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "symlinks refused" in p.stderr
    p = subprocess.run([CHECK, str(link), "--pubkey", str(pub)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "symlinks refused" in p.stderr


def test_sign_refuses_non_ed25519_key(tmp_path):
    # An RSA key in the same PEM envelope must not silently sign.
    subprocess.run(["openssl", "genrsa", "-out", str(tmp_path / "rsa.pem"),
                    "2048"], capture_output=True, timeout=30)
    (tmp_path / "rsa.pem").chmod(0o600)
    out = tmp_path / "m.json"
    subprocess.run([GEN, "--out", str(out)], check=True, timeout=30,
                   capture_output=True)
    p = subprocess.run([SIGN, str(out), "--key", str(tmp_path / "rsa.pem")],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 1
    assert "not Ed25519" in p.stderr
