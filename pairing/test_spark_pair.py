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
import time

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


# ---- #846: token rotation + revocation -------------------------------------

def _enroll(ctx, token="OLDSECRET", expires_at=9999999999, box_id="box_xyz"):
    os.makedirs(ctx.dir, mode=0o700, exist_ok=True)
    enroll_path = os.path.join(ctx.dir, "enrollment.json")
    spark_pair._write_private(enroll_path, json.dumps(
        {"box_id": box_id, "token": token,
         "token_expires_at": expires_at, "control": ctx.control},
        indent=2).encode())
    return enroll_path


def test_rotate_message_format_is_versioned_and_windowed():
    # The contract the plane verifies: b"spark-rotate-v1|<box_id>|<window>".
    msg = spark_pair._rotate_message("box_xyz", 12345)
    assert msg == b"spark-rotate-v1|box_xyz|12345"
    assert spark_pair.ROTATE_WINDOW == 300


def test_rotate_success_saves_new_token_0600(ctx, monkeypatch, capsys):
    seed, pub = _run_init(ctx)
    enroll_path = _enroll(ctx)
    new_exp = int(time.time()) + 24 * 3600
    calls = []

    def fake_http(method, url, body=None, headers=None):
        calls.append((method, url, body, headers))
        assert method == "POST" and url.endswith("/v1/boxes/token/rotate")
        assert headers["Authorization"] == "Bearer OLDSECRET"
        sig = base64.b64decode(body["signature"])
        # the server contract accepts the current 300 s window ± 1; the
        # expected message is spelled out literally here (not via the
        # client's own builder) so the test pins the wire format.
        now_w = int(time.time()) // spark_pair.ROTATE_WINDOW
        ok = any(
            ed25519.verify(pub, b"spark-rotate-v1|box_xyz|" + str(w).encode(),
                           sig)
            for w in (now_w - 1, now_w, now_w + 1))
        assert ok, "server rejects a bad proof-of-possession signature"
        return 200, {"ok": True, "token": "NEWSECRET",
                     "token_expires_at": new_exp, "proof": "ed25519"}

    monkeypatch.setattr(spark_pair, "_http", fake_http)
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 0
    out = capsys.readouterr().out
    assert "NEWSECRET" not in out  # the new token is never printed
    assert "box_xyz" in out
    enroll = json.load(open(enroll_path))
    assert enroll["token"] == "NEWSECRET"
    assert enroll["token_expires_at"] == new_exp
    mode = stat.S_IMODE(os.stat(enroll_path).st_mode)
    assert mode == 0o600
    assert not os.path.exists(enroll_path + ".tmp")  # no temp file left


def test_rotate_auto_skips_when_token_has_life_left(ctx, monkeypatch):
    _run_init(ctx)
    _enroll(ctx, expires_at=int(time.time()) + 20 * 3600)
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("must not call HTTP when --auto skips")))
    ctx.auto = True
    ctx.within = 6 * 3600
    assert spark_pair.cmd_rotate(ctx) == 0  # quiet success, no HTTP


def test_rotate_auto_fires_when_expiry_near_or_missing(ctx, monkeypatch):
    _run_init(ctx)
    calls = []
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda m, u, body=None, headers=None: (
            calls.append(u),
            (200, {"ok": True, "token": "T2",
                   "token_expires_at": int(time.time()) + 24 * 3600,
                   "proof": "ed25519"}))[1])
    ctx.auto = True
    ctx.within = 6 * 3600
    # near expiry -> rotates
    _enroll(ctx, expires_at=int(time.time()) + 3600)
    assert spark_pair.cmd_rotate(ctx) == 0
    assert len(calls) == 1
    # grandfathered (no expiry) -> rotates too: the unbounded case #846 kills
    _enroll(ctx, expires_at=None)
    assert spark_pair.cmd_rotate(ctx) == 0
    assert len(calls) == 2


def test_rotate_rejected_token_says_repair(ctx, monkeypatch, capsys):
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (401, {"ok": False,
                                              "error": "revoked"}))
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 1
    out = capsys.readouterr().out
    assert "re-pair" in out
    # the dead token stays on disk untouched (operator re-pairs deliberately)
    assert json.load(open(os.path.join(ctx.dir, "enrollment.json")))["token"] \
        == "OLDSECRET"


def test_rotate_refuses_bad_server_expiry(ctx, monkeypatch, capsys):
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (200, {"ok": True, "token": "T2",
                                              "token_expires_at": "forever"}))
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 1
    assert "unusable token expiry" in capsys.readouterr().out
    assert json.load(open(os.path.join(ctx.dir, "enrollment.json")))["token"] \
        == "OLDSECRET"


def test_rotate_without_enrollment_refuses(ctx, monkeypatch, capsys):
    _run_init(ctx)
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no HTTP yet")))
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 1
    assert "not enrolled" in capsys.readouterr().out


def test_rotate_without_keypair_sends_null_signature(ctx, monkeypatch):
    # Pre-#844 box: no box.key on disk. The client sends signature:null and
    # lets the server decide (Bearer <redacted>-only rotation for keyless boxes).
    _enroll(ctx)
    seen = {}
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda m, u, body=None, headers=None: (
            seen.update(body=body),
            (200, {"ok": True, "token": "T3",
                   "token_expires_at": int(time.time()) + 24 * 3600,
                   "proof": "Bearer <redacted>", "rekey_recommended": True}))[1])
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 0
    assert seen["body"]["signature"] is None


def test_revoke_owner_flow(ctx, monkeypatch, capsys):
    seen = {}

    def fake_http(method, url, body=None, headers=None):
        seen["auth"] = (headers or {}).get("Authorization")
        assert method == "POST"
        assert url == "https://control.test/v1/boxes/box_xyz/revoke"
        return 200, {"ok": True, "revoked": "box_xyz"}

    monkeypatch.setattr(spark_pair, "_http", fake_http)
    ctx.box_id = "box_xyz"
    assert spark_pair.cmd_revoke(ctx) == 0
    assert seen["auth"] == "Bearer svm_owner_test"
    assert "rejected immediately" in capsys.readouterr().out


def test_revoke_unknown_box(ctx, monkeypatch, capsys):
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (404, {"ok": False,
                                              "error": "no such box"}))
    ctx.box_id = "box_nope"
    assert spark_pair.cmd_revoke(ctx) == 1
    assert "no such box" in capsys.readouterr().out


def test_revoke_endpoint_missing_says_plane_pending(ctx, monkeypatch, capsys):
    # A bare transport 404 (the _http non-JSON fallback) means the plane
    # does not implement the endpoint — never "no such box".
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (404, {"ok": False,
                                              "error": "http=404"}))
    ctx.box_id = "box_xyz"
    assert spark_pair.cmd_revoke(ctx) == 1
    out = capsys.readouterr().out
    assert "does not implement" in out
    assert "no such box" not in out


def test_rotate_endpoint_missing_says_plane_pending(ctx, monkeypatch, capsys):
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (404, {"ok": False,
                                              "error": "http=404"}))
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 1
    out = capsys.readouterr().out
    assert "does not implement" in out
    assert "nothing was changed locally" in out
    # local state untouched
    assert json.load(open(os.path.join(ctx.dir, "enrollment.json")))["token"] \
        == "OLDSECRET"


def test_rotate_403_does_not_advise_repair(ctx, monkeypatch, capsys):
    # 403 = Bearer <redacted> fine, proof rejected: the enrollment is healthy,
    # re-pairing would nuke it for nothing.
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (403, {"ok": False,
                                              "error": "bad signature"}))
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 1
    out = capsys.readouterr().out
    assert "re-pair" not in out
    assert "untouched" in out


def test_rotate_refuses_when_plane_skips_proof(ctx, monkeypatch, capsys):
    # Fail closed on proof-of-possession: we sent a signature but the plane
    # claims proof="Bearer <redacted>" — do not save the token.
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (200, {"ok": True, "token": "T9",
                               "token_expires_at": int(time.time()) + 3600,
                               "proof": "Bearer <redacted>"}))
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 1
    assert "did not verify" in capsys.readouterr().out
    assert json.load(open(os.path.join(ctx.dir, "enrollment.json")))["token"] \
        == "OLDSECRET"


def test_rotate_refuses_absurd_expiry(ctx, monkeypatch, capsys):
    # A 10-year "short-lived" token defeats #846; the client refuses it.
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (200, {"ok": True, "token": "T9",
                               "token_expires_at": int(time.time()) + 10 * 365 * 24 * 3600,
                               "proof": "ed25519"}))
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 1
    assert "unusable token expiry" in capsys.readouterr().out
    assert json.load(open(os.path.join(ctx.dir, "enrollment.json")))["token"] \
        == "OLDSECRET"


def test_rotate_refuses_past_int_expiry(ctx, monkeypatch, capsys):
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (200, {"ok": True, "token": "T9",
                               "token_expires_at": int(time.time()) - 60,
                               "proof": "ed25519"}))
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 1
    assert json.load(open(os.path.join(ctx.dir, "enrollment.json")))["token"] \
        == "OLDSECRET"


def test_rotate_corrupt_enrollment_is_clean_error(ctx, monkeypatch, capsys):
    _run_init(ctx)
    os.makedirs(ctx.dir, mode=0o700, exist_ok=True)
    open(os.path.join(ctx.dir, "enrollment.json"), "w").write("{not json")
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no HTTP yet")))
    ctx.auto = True  # the cron path must not traceback
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 1
    assert "unreadable" in capsys.readouterr().out


def test_rotate_auto_fires_at_exact_boundary(ctx, monkeypatch):
    # At exactly --within seconds of expiry the conservative direction wins.
    _run_init(ctx)
    calls = []
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda m, u, body=None, headers=None: (
            calls.append(u),
            (200, {"ok": True, "token": "T2",
                   "token_expires_at": int(time.time()) + 24 * 3600,
                   "proof": "ed25519"}))[1])
    ctx.auto = True
    ctx.within = 3600
    _enroll(ctx, expires_at=int(time.time()) + 3600)
    assert spark_pair.cmd_rotate(ctx) == 0
    assert len(calls) == 1


def test_rotate_prints_rekey_note(ctx, monkeypatch, capsys):
    _enroll(ctx)  # no keypair on disk: keyless path
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda m, u, body=None, headers=None: (
            200, {"ok": True, "token": "T3",
                  "token_expires_at": int(time.time()) + 24 * 3600,
                  "proof": "Bearer <redacted>", "rekey_recommended": True}))
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 0
    assert "re-pair" in capsys.readouterr().out


def test_revoke_url_encodes_box_id(ctx, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda m, u, body=None, headers=None: (
            seen.update(url=u), (200, {"ok": True, "revoked": "x"}))[1])
    ctx.box_id = "box/a b"
    assert spark_pair.cmd_revoke(ctx) == 0
    assert seen["url"].endswith("/v1/boxes/box%2Fa%20b/revoke")


def test_write_private_rechmods_existing_file(ctx):
    p = os.path.join(ctx.dir, "t.tmp")
    os.makedirs(ctx.dir, mode=0o700, exist_ok=True)
    open(p, "w").write("x")
    os.chmod(p, 0o644)
    spark_pair._write_private(p, b"y")
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
