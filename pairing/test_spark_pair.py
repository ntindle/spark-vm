"""Tests for pairing/spark_pair.py (pairing-code enrollment client).

The HTTP layer is stubbed; these tests cover the client state machine:
init/request/redeem/approve wiring, key-file permissions, fingerprint
binding, and the "never print secrets" property.
"""
import base64
import io
import json
import os
import stat
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import ed25519
import spark_pair


class Ctx:
    """Fake argparse namespace."""
    def __init__(self, tmp_path, **kw):
        self.dir = str(tmp_path)
        self.control = "https://control.test"
        self.force = False
        self.name = "testbox"
        self.pairing_id = None
        self.owner_key = "svm_owner_test"
        self.bootstrap = False
        for k, v in kw.items():
            setattr(self, k, v)


@pytest.fixture()
def ctx(tmp_path):
    return Ctx(tmp_path)


def _key_paths(ctx):
    d = ctx.dir
    os.makedirs(d, mode=0o700, exist_ok=True)
    return os.path.join(d, "box.key"), os.path.join(d, "box.pub")


def _run_init(ctx):
    assert spark_pair.cmd_init(ctx) == 0
    key_path, pub_path = _key_paths(ctx)
    seed = base64.b64decode(open(key_path, "rb").read())
    pub = base64.b64decode(open(pub_path).read())
    assert ed25519.publickey_from_seed(seed) == pub
    return seed, pub


def test_init_writes_0600_key_and_prints_fingerprint(ctx, capsys):
    seed, pub = _run_init(ctx)
    key_path, _ = _key_paths(ctx)
    mode = stat.S_IMODE(os.stat(key_path).st_mode)
    assert mode == 0o600, f"key file mode {oct(mode)}"
    out = capsys.readouterr().out
    assert ed25519.fingerprint(pub) in out
    assert base64.b64encode(seed).decode() not in out  # never print the seed


def test_init_refuses_to_clobber(ctx):
    _run_init(ctx)
    assert spark_pair.cmd_init(ctx) == 1
    ctx.force = True
    assert spark_pair.cmd_init(ctx) == 0


def test_request_redeem_full_flow(ctx, monkeypatch, capsys):
    seed, pub = _run_init(ctx)
    fp = ed25519.fingerprint(pub)
    challenge = base64.b64encode(b"C" * 32).decode()
    calls = []

    def fake_http(method, url, body=None, headers=None):
        calls.append((method, url, body))
        if url.endswith("/v1/pairing/request"):
            assert body["fingerprint"] == fp
            assert len(base64.b64decode(body["pubkey"])) == 32
            return 201, {"ok": True, "pairing_id": "pair_abc",
                         "code": "ABCD-EFGH", "expires_at": 9999999999}
        if url.endswith("/status"):
            return 200, {"ok": True, "status": "approved",
                         "expires_at": 9999999999, "challenge": challenge}
        if url.endswith("/redeem"):
            sig = base64.b64decode(body["signature"])
            assert ed25519.verify(pub, base64.b64decode(challenge), sig)
            return 201, {"ok": True, "box_id": "box_xyz",
                         "token": "SECRET", "token_expires_at": 9999999999}
        raise AssertionError(url)

    monkeypatch.setattr(spark_pair, "_http", fake_http)
    monkeypatch.setattr(spark_pair.time, "sleep", lambda s: None)

    assert spark_pair.cmd_request(ctx) == 0
    out = capsys.readouterr().out
    assert "ABCD-EFGH" in out
    assert fp in out
    pairing = json.load(open(os.path.join(ctx.dir, "pairing.json")))
    assert pairing["pairing_id"] == "pair_abc"

    assert spark_pair.cmd_redeem(ctx) == 0
    out = capsys.readouterr().out
    assert "SECRET" not in out  # the box token is never printed
    assert "box_xyz" in out
    enroll = json.load(open(os.path.join(ctx.dir, "enrollment.json")))
    assert enroll["token"] == "SECRET"
    mode = stat.S_IMODE(os.stat(os.path.join(ctx.dir, "enrollment.json")).st_mode)
    assert mode == 0o600
    assert not os.path.exists(os.path.join(ctx.dir, "pairing.json"))


def test_redeem_aborts_when_fingerprint_would_mismatch(ctx, monkeypatch):
    # If the on-disk pubkey doesn't match the seed, request must refuse:
    # the fingerprint the owner verifies would be for a different key.
    _run_init(ctx)
    key_path, pub_path = _key_paths(ctx)
    other = base64.b64encode(ed25519.generate_keypair()[1]).decode()
    open(pub_path, "w").write(other)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("must not call HTTP")))
    assert spark_pair.cmd_request(ctx) == 1


def test_approve_requires_code_match(ctx, monkeypatch, capsys):
    # The server NEVER returns the pairing code (stored as a hash); the
    # client must POST the human-typed code and let the server compare.
    fp = "SHA256:abcd efgh"
    seen = {}

    def fake_http(method, url, body=None, headers=None):
        assert headers.get("Authorization") == "Bearer svm_owner_test"
        if url.endswith("/pair_1") and method == "GET":
            payload = {"ok": True, "pairing": {
                "id": "pair_1", "box_name": "b1", "fingerprint": fp,
                "status": "pending"}}
            assert "code" not in json.dumps(payload)  # real contract
            return 200, payload
        if url.endswith("/approve"):
            seen["code"] = (body or {}).get("code")
            # the real server normalizes case/spacing/dashes before hashing
            norm = "".join(c for c in (seen["code"] or "").upper()
                           if c in "ABCDEFGHJKMNPQRSTUVWXYZ23456789")
            if norm == "ABCDEFGH":
                return 200, {"ok": True, "approved": "pair_1"}
            return 403, {"ok": False, "error": "code mismatch"}
        raise AssertionError(url)

    monkeypatch.setattr(spark_pair, "_http", fake_http)
    ctx.pairing_id = "pair_1"

    monkeypatch.setattr("builtins.input", lambda *a: "WRONGCODE")
    assert spark_pair.cmd_approve(ctx) == 1
    assert seen.get("code") == "WRONGCODE"  # typed code reaches the server
    out = capsys.readouterr().out
    assert fp in out  # the fingerprint is shown for verification

    monkeypatch.setattr("builtins.input", lambda *a: "abcd efgh")
    assert spark_pair.cmd_approve(ctx) == 0
    assert seen.get("code") == "abcd efgh"


def test_approve_bootstrap_sends_no_auth_header(ctx, monkeypatch, capsys):
    fp = "SHA256:abcd efgh"
    seen = {}

    def fake_http(method, url, body=None, headers=None):
        seen["auth"] = (headers or {}).get("Authorization")
        if url.endswith("/pair_1") and method == "GET":
            return 200, {"ok": True, "pairing": {
                "id": "pair_1", "box_name": "b1", "fingerprint": fp,
                "status": "pending"}}
        if url.endswith("/approve"):
            return 200, {"ok": True, "approved": "pair_1"}
        raise AssertionError(url)

    monkeypatch.setattr(spark_pair, "_http", fake_http)
    ctx.pairing_id = "pair_1"
    ctx.bootstrap = True
    monkeypatch.setattr("builtins.input", lambda *a: "ABCD-EFGH")
    assert spark_pair.cmd_approve(ctx) == 0
    assert seen["auth"] is None  # no Authorization header on bootstrap


def test_approve_bootstrap_requires_pairing_id(ctx, monkeypatch, capsys):
    ctx.pairing_id = None
    ctx.bootstrap = True
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no HTTP yet")))
    assert spark_pair.cmd_approve(ctx) == 1
    assert "requires --pairing-id" in capsys.readouterr().out


def test_approve_lists_pending_when_no_id(ctx, monkeypatch, capsys):
    def fake_http(method, url, body=None, headers=None):
        if url.endswith("/v1/pairing"):
            payload = {"ok": True, "pairings": [
                {"id": "pair_9", "box_name": "b1",
                 "fingerprint": "SHA256:x", "status": "pending"}]}
            assert "code" not in json.dumps(payload)  # real contract
            return 200, payload
        raise AssertionError(url)

    monkeypatch.setattr(spark_pair, "_http", fake_http)
    inputs = iter(["pair_9"])
    monkeypatch.setattr("builtins.input", lambda *a: next(inputs))
    ctx.pairing_id = None
    try:
        spark_pair.cmd_approve(ctx)
    except AssertionError:
        pass  # detail fetch not stubbed; list display is what we assert
    out = capsys.readouterr().out
    assert "pair_9" in out and "b1" in out and "SHA256:x" in out
