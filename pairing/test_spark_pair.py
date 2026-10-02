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
    # does not implement the endpoint — never "no such box". The stub
    # carries _http's synthesized marker: that is what the real _http
    # returns for this class.
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (404, {"ok": False,
                                              "error": "http=404",
                                              spark_pair._TRANSPORT_404: True}))
    ctx.box_id = "box_xyz"
    assert spark_pair.cmd_revoke(ctx) == 1
    out = capsys.readouterr().out
    assert "does not implement" in out
    assert "no such box" not in out


def test_rotate_endpoint_missing_says_plane_pending(ctx, monkeypatch, capsys):
    _run_init(ctx)
    _enroll(ctx)
    # The stub carries _http's synthesized marker: that is what the real
    # _http returns for the transport-404 class.
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (404, {"ok": False,
                                              "error": "http=404",
                                              spark_pair._TRANSPORT_404: True}))
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


# ---- #864: interim heartbeat sender ----------------------------------------


def test_heartbeat_success_is_quiet_and_records_last_ok(ctx, monkeypatch,
                                                        capsys):
    _run_init(ctx)
    _enroll(ctx)
    seen = {}

    def fake_http(method, url, body=None, headers=None):
        seen["method"] = method
        seen["url"] = url
        seen["body"] = body
        seen["auth"] = (headers or {}).get("Authorization")
        return 200, {"ok": True}

    monkeypatch.setattr(spark_pair, "_http", fake_http)
    capsys.readouterr()  # discard init's own output; heartbeat must add none
    assert spark_pair.cmd_heartbeat(ctx) == 0
    # quiet success: the every-minute cron line stays silent
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    assert seen["method"] == "POST"
    assert seen["url"] == "https://control.test/v1/boxes/box_xyz/heartbeat"
    assert seen["auth"] == "Bearer OLDSECRET"
    body = seen["body"]
    assert body["box_id"] == "box_xyz"
    assert isinstance(body["sent_at"], int)
    assert body["client"] == spark_pair.USER_AGENT
    assert "OLDSECRET" not in json.dumps(body)  # token never in the payload
    last = json.load(open(os.path.join(ctx.dir, "last_heartbeat.json")))
    assert last["box_id"] == "box_xyz" and last["plane_ok"] is True
    assert isinstance(last["last_ok_at"], int)


def test_heartbeat_transport_failure_is_loud(ctx, monkeypatch, capsys):
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (0, {"ok": False,
                                            "error": "transport: boom"}))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    err = capsys.readouterr().err
    assert "heartbeat FAILED" in err and "boom" in err
    log = open(os.path.join(ctx.dir, "heartbeat.log")).read()
    assert "heartbeat FAILED" in log
    # a missed heartbeat never fabricates an ok
    assert not os.path.exists(os.path.join(ctx.dir, "last_heartbeat.json"))


def test_heartbeat_401_says_repair(ctx, monkeypatch, capsys):
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (401, {"ok": False,
                                              "error": "revoked"}))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    err = capsys.readouterr().err
    assert "re-pair" in err
    assert not os.path.exists(os.path.join(ctx.dir, "last_heartbeat.json"))


def test_heartbeat_200_without_ok_is_failure(ctx, monkeypatch, capsys):
    # The plane answered but did not say ok: that is NOT a heartbeat.
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (200, {"ok": False}))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    assert "heartbeat FAILED" in capsys.readouterr().err
    assert not os.path.exists(os.path.join(ctx.dir, "last_heartbeat.json"))


def test_heartbeat_200_non_object_body_is_failure(ctx, monkeypatch, capsys):
    # _http returns json.loads() of ANY 2xx body — a list/string/null must
    # not AttributeError its way to a bare traceback with no log entry.
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (200, ["ok", True]))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    err = capsys.readouterr().err
    assert "heartbeat FAILED" in err and "malformed" in err
    assert "Traceback" not in err
    log = open(os.path.join(ctx.dir, "heartbeat.log")).read()
    assert "malformed" in log
    assert not os.path.exists(os.path.join(ctx.dir, "last_heartbeat.json"))


def test_heartbeat_500_is_loud_and_fabricates_nothing(ctx, monkeypatch,
                                                      capsys):
    _run_init(ctx)
    _enroll(ctx)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (500, {"ok": False,
                                              "error": "http=500"}))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    assert "http=500" in capsys.readouterr().err
    assert not os.path.exists(os.path.join(ctx.dir, "last_heartbeat.json"))


def test_heartbeat_endpoint_missing_says_plane_pending(ctx, monkeypatch,
                                                       capsys):
    _run_init(ctx)
    _enroll(ctx)
    # The stub carries _http's synthesized marker: that is what the real
    # _http returns for the transport-404 class.
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (404, {"ok": False,
                                              "error": "http=404",
                                              spark_pair._TRANSPORT_404: True}))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    err = capsys.readouterr().err
    assert "does not implement" in err
    assert "no such box" not in err


def test_heartbeat_missing_enrollment_is_clean_error(ctx, monkeypatch, capsys):
    _run_init(ctx)
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no HTTP yet")))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    err = capsys.readouterr().err
    assert "heartbeat FAILED" in err and "redeem" in err


def test_heartbeat_lock_open_failure_is_clean_error(ctx, monkeypatch,
                                                        capsys):
    # Lock acquisition failure must fail loud, not traceback. (Root-safe:
    # monkeypatches os.open rather than chmod, since the suite may run as
    # root where chmod-based read-only dirs are still writable.)
    _run_init(ctx)
    _enroll(ctx)
    real_open = os.open

    def fake_open(path, *a, **k):
        if os.path.basename(os.fspath(path)) == ".heartbeat.lock":
            raise OSError(13, "Permission denied")
        return real_open(path, *a, **k)

    monkeypatch.setattr(os, "open", fake_open)
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("no HTTP yet")))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    err = capsys.readouterr().err
    assert "heartbeat FAILED" in err and "lock file" in err
    assert "Traceback" not in err


def test_heartbeat_lock_forces_0600_on_existing_lock(ctx, monkeypatch):
    # 0600 at creation is not enough: a pre-existing lock file keeps its
    # wider mode through os.open (#883). A stale 0644 lock must come out
    # 0600 after acquisition. Non-vacuous: the assertion fails without
    # the os.fchmod fix (verified by reverting the one-liner).
    _run_init(ctx)
    _enroll(ctx)
    lock_path = os.path.join(ctx.dir, ".heartbeat.lock")
    # os.open's mode is masked by the umask; chmod guarantees the
    # pre-existing wide mode this test needs regardless of it.
    open(lock_path, "w").close()
    os.chmod(lock_path, 0o644)
    assert stat.S_IMODE(os.stat(lock_path).st_mode) == 0o644
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (0, {"ok": False,
                                             "error": "transport: down"}))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    assert stat.S_IMODE(os.stat(lock_path).st_mode) == 0o600


def test_rotate_lock_forces_0600_on_existing_lock(ctx, monkeypatch):
    # Same 0600-force class as the heartbeat lock (#883), on rotate's
    # lock path. The transport failure makes _cmd_rotate_locked exit
    # before any state change; the lock was still acquired first.
    _run_init(ctx)
    _enroll(ctx)
    lock_path = os.path.join(ctx.dir, ".rotate.lock")
    open(lock_path, "w").close()
    os.chmod(lock_path, 0o644)
    assert stat.S_IMODE(os.stat(lock_path).st_mode) == 0o644
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (0, {"ok": False,
                                             "error": "transport: down"}))
    ctx.auto = False
    ctx.within = spark_pair.AUTO_ROTATE_WITHIN
    assert spark_pair.cmd_rotate(ctx) == 1
    assert stat.S_IMODE(os.stat(lock_path).st_mode) == 0o600


def test_heartbeat_non_object_enrollment_is_clean_error(ctx, monkeypatch,
                                                          capsys):
    # Valid JSON but not an object: must fail loud, not AttributeError with
    # a bare traceback and no log entry.
    _run_init(ctx)
    os.makedirs(ctx.dir, mode=0o700, exist_ok=True)
    open(os.path.join(ctx.dir, "enrollment.json"), "w").write('["not", "an", "object"]')
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no HTTP yet")))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    err = capsys.readouterr().err
    assert "heartbeat FAILED" in err and "not an object" in err
    assert "Traceback" not in err
    assert "not an object" in \
        open(os.path.join(ctx.dir, "heartbeat.log")).read()


def test_heartbeat_corrupt_enrollment_is_clean_error(ctx, monkeypatch, capsys):
    _run_init(ctx)
    os.makedirs(ctx.dir, mode=0o700, exist_ok=True)
    open(os.path.join(ctx.dir, "enrollment.json"), "w").write("{not json")
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no HTTP yet")))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    assert "unreadable" in capsys.readouterr().err


def test_heartbeat_url_encodes_box_id(ctx, monkeypatch):
    _run_init(ctx)
    _enroll(ctx, box_id="box/a b")
    seen = {}
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda m, u, body=None, headers=None: (
            seen.update(url=u), (200, {"ok": True}))[1])
    assert spark_pair.cmd_heartbeat(ctx) == 0
    assert seen["url"].endswith("/v1/boxes/box%2Fa%20b/heartbeat")


def test_heartbeat_log_never_contains_token(ctx, monkeypatch, capsys):
    # The loud failure path must not leak the Bearer <redacted> into stderr or the
    # log file — even if the plane echoes the token back inside an error
    # string, the sender redacts it rather than logging it.
    _run_init(ctx)
    _enroll(ctx, token="SUPERSECRETT0KEN")
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (0, {"ok": False,
                             "error": "transport: SUPERSECRETT0KEN"}))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    err = capsys.readouterr().err
    assert "SUPERSECRETT0KEN" not in err
    assert "<redacted>" in err  # the class is still reported, not swallowed
    log = open(os.path.join(ctx.dir, "heartbeat.log")).read()
    assert "SUPERSECRETT0KEN" not in log
    assert "<redacted>" in log


# ---- 20261002-1659 arch turn: HTTP-layer hardening ---------------------------
# Redirect auth-strip (Security), cleartext-http refusal (Security),
# _http response-shape normalization (Architecture), redeem pairing.json
# guards (Architecture). Local servers only — no network access.

import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _serve(handler_cls):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


class _Quiet(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass


class _EchoAuth(_Quiet):
    """Answers {"saw_auth": <whether an Authorization header arrived>}."""

    def do_GET(self):
        body = json.dumps(
            {"saw_auth": "Authorization" in self.headers}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _CrossOriginRedirect(_Quiet):
    """302s to a different ORIGIN (different port on the same host)."""
    target = ""

    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", self.target)
        self.send_header("Content-Length", "0")
        self.end_headers()


class _SameOriginRedirectEcho(_EchoAuth):
    """/go 302s to /echo on the SAME origin; every GET echoes auth sight."""

    def do_GET(self):
        if self.path == "/go":
            self.send_response(302)
            self.send_header("Location", "/echo")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        return super().do_GET()


def test_http_strips_authorization_on_cross_origin_redirect():
    # urllib's default opener forwards manually-set Authorization headers
    # across redirects, even cross-origin: on this credential-bearing
    # client that is a token leak. Regression test for the stripper.
    echo = _serve(_EchoAuth)
    redir = _serve(type("R", (_CrossOriginRedirect,), {
        "target": f"http://127.0.0.1:{echo.server_address[1]}/x"}))
    try:
        url = f"http://127.0.0.1:{redir.server_address[1]}/go"
        status, resp = spark_pair._http(
            "GET", url, headers={"Authorization": "Bearer s3cr3t"})
        assert status == 200
        assert resp == {"saw_auth": False}
    finally:
        redir.shutdown()
        echo.shutdown()


def test_http_keeps_authorization_on_same_origin_redirect():
    # Same-origin redirects (e.g. a trailing-slash bounce) must keep
    # working: only the cross-origin strip is new behavior.
    srv = _serve(_SameOriginRedirectEcho)
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/go"
        status, resp = spark_pair._http(
            "GET", url, headers={"Authorization": "Bearer s3cr3t"})
        assert status == 200
        assert resp == {"saw_auth": True}
    finally:
        srv.shutdown()


class _FakeOpener:
    """Stands in for spark_pair._HTTP_OPENER with a canned body."""

    def __init__(self, body):
        self._body = body

    def open(self, req, timeout=None):
        body = self._body

        class _Resp:
            status = 200

            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Resp()


def test_http_normalizes_non_object_body_to_failure(monkeypatch):
    # A 2xx with a JSON list/string/null body used to flow to call sites
    # that all assume dict (AttributeError/KeyError). _http now normalizes
    # at the choke point instead of guarding at each site.
    monkeypatch.setattr(spark_pair, "_HTTP_OPENER",
                        _FakeOpener(b"[1, 2]"))
    status, resp = spark_pair._http("GET", "https://control.test/x")
    assert status == 200
    assert resp == {"ok": False,
                    "error": "malformed plane response (non-object body)"}


def test_http_passes_object_bodies_through(monkeypatch):
    monkeypatch.setattr(spark_pair, "_HTTP_OPENER",
                        _FakeOpener(b'{"ok": true}'))
    status, resp = spark_pair._http("GET", "https://control.test/x")
    assert (status, resp) == (200, {"ok": True})


class _FakeErrorOpener:
    """Stands in for spark_pair._HTTP_OPENER, raising HTTPError with a
    canned body."""

    def __init__(self, code, body):
        self._code = code
        self._body = body

    def open(self, req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, self._code, "err", {},
                                     io.BytesIO(self._body))


def test_http_normalizes_non_object_error_body_to_failure(monkeypatch):
    # The HTTPError branch must mirror the 2xx normalization: a JSON list
    # error body must not AttributeError at the first resp.get(). The
    # http=NNN marker is kept so the 404 endpoint-detection still works.
    monkeypatch.setattr(spark_pair, "_HTTP_OPENER",
                        _FakeErrorOpener(500, b"[1, 2]"))
    status, resp = spark_pair._http("GET", "https://control.test/x")
    assert status == 500
    assert resp == {"ok": False, "error": "http=500"}


def test_http_keeps_dict_error_bodies(monkeypatch):
    monkeypatch.setattr(spark_pair, "_HTTP_OPENER",
                        _FakeErrorOpener(404, b'{"ok": false, "e": 1}'))
    status, resp = spark_pair._http("GET", "https://control.test/x")
    assert (status, resp) == (404, {"ok": False, "e": 1})


def test_http_marks_synthesized_404_fallback(monkeypatch):
    # A 404 with no JSON body is the "endpoint not implemented" class:
    # _http marks the payload it synthesizes itself (#882).
    monkeypatch.setattr(spark_pair, "_HTTP_OPENER",
                        _FakeErrorOpener(404, b"<html>not here</html>"))
    status, resp = spark_pair._http("GET", "https://control.test/x")
    assert status == 404
    assert resp[spark_pair._TRANSPORT_404] is True
    assert spark_pair._plane_missing(resp)


def test_http_does_not_mark_non_404_fallbacks(monkeypatch):
    # The marker is the 404 endpoint-detection class only: a synthesized
    # 500 payload keeps today's exact shape (no marker key).
    monkeypatch.setattr(spark_pair, "_HTTP_OPENER",
                        _FakeErrorOpener(500, b"internal error"))
    status, resp = spark_pair._http("GET", "https://control.test/x")
    assert (status, resp) == (500, {"ok": False, "error": "http=500"})
    assert not spark_pair._plane_missing(resp)


def test_http_plane_json_error_string_is_not_endpoint_missing(monkeypatch):
    # The conflation #882 closes: a JSON plane legitimately returning
    # {"error": "http=404"} for some *other* failure used to be classified
    # as "endpoint not implemented". The string is still there (it is the
    # plane's real error), but the classification now ignores it.
    monkeypatch.setattr(spark_pair, "_HTTP_OPENER",
                        _FakeErrorOpener(
                            404, b'{"ok": false, "error": "http=404"}'))
    status, resp = spark_pair._http("GET", "https://control.test/x")
    assert status == 404
    assert resp.get("error") == "http=404"  # the old rule keyed on this
    assert spark_pair._TRANSPORT_404 not in resp
    assert not spark_pair._plane_missing(resp)


def test_http_strips_forged_marker_from_plane_body(monkeypatch):
    # A hostile or buggy plane cannot forge the fallback marker: _http
    # strips it from plane-returned bodies, so _plane_missing only fires
    # on payloads _http synthesized itself.
    body = json.dumps({"ok": False, "_transport_404": True,
                       "error": "no such box"}).encode()
    monkeypatch.setattr(spark_pair, "_HTTP_OPENER",
                        _FakeErrorOpener(404, body))
    status, resp = spark_pair._http("GET", "https://control.test/x")
    assert status == 404
    assert spark_pair._TRANSPORT_404 not in resp
    assert not spark_pair._plane_missing(resp)
    assert resp.get("error") == "no such box"  # the real error survives


def test_http_strips_marker_from_2xx_dict_body(monkeypatch):
    # The "only _http sets it" invariant is global: a 2xx dict carrying
    # the marker key is cleaned too (it is inert at 2xx, but the plane
    # must not be able to plant it anywhere).
    monkeypatch.setattr(spark_pair, "_HTTP_OPENER",
                        _FakeOpener(b'{"ok": true, "_transport_404": true}'))
    status, resp = spark_pair._http("GET", "https://control.test/x")
    assert (status, resp) == (200, {"ok": True})


def test_plane_missing_rejects_non_dict_and_non_true():
    # The predicate must never fire on anything but the exact marker.
    assert not spark_pair._plane_missing(None)
    assert not spark_pair._plane_missing([1])
    assert not spark_pair._plane_missing("http=404")
    assert not spark_pair._plane_missing({})
    assert not spark_pair._plane_missing({"ok": False, "error": "http=404"})
    assert not spark_pair._plane_missing(
        {spark_pair._TRANSPORT_404: "yes"})  # truthy is not True
    assert spark_pair._plane_missing({spark_pair._TRANSPORT_404: True})


def test_revoke_404_json_error_string_says_no_such_box(ctx, monkeypatch,
                                                       capsys):
    # Behavioral proof of the #882 fix at the call site: a 404 whose body
    # is real JSON (the plane's own error) is "no such box" — the old
    # string-keyed classification said "does not implement".
    monkeypatch.setattr(spark_pair, "_http",
                        lambda *a, **k: (404, {"ok": False,
                                              "error": "http=404"}))
    ctx.box_id = "box_xyz"
    assert spark_pair.cmd_revoke(ctx) == 1
    out = capsys.readouterr().out
    assert "no such box" in out
    assert "does not implement" not in out


def test_check_control_url_matrix(monkeypatch):
    assert spark_pair._check_control_url("https://api.sparkvm.dev") == (
        True, "")
    assert spark_pair._check_control_url("http://127.0.0.1:8080/x")[0]
    assert spark_pair._check_control_url("http://localhost/x")[0]
    ok, msg = spark_pair._check_control_url("http://control.test/x")
    assert not ok and "cleartext" in msg
    ok, msg = spark_pair._check_control_url("ftp://control.test/x")
    assert not ok and "https" in msg
    # Fail-open bypass regression: "127.evil.com" is a public DNS name,
    # not loopback — a prefix test ("127.") would wrongly admit it and
    # send bearer tokens in cleartext to an attacker host.
    assert not spark_pair._check_control_url("http://127.evil.com/x")[0]
    assert not spark_pair._check_control_url("http://127.0.0.1.evil.com/x")[0]
    assert spark_pair._check_control_url("http://[::1]/x")[0]
    # Explicit opt-in unblocks non-loopback http (local dev against a
    # non-loopback test host).
    monkeypatch.setenv("SVM_PAIR_ALLOW_HTTP", "1")
    assert spark_pair._check_control_url("http://control.test/x")[0]


def test_request_refuses_cleartext_control(ctx, monkeypatch, capsys):
    _run_init(ctx)
    ctx.control = "http://control.test"
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no HTTP")))
    assert spark_pair.cmd_request(ctx) == 1
    assert "cleartext" in capsys.readouterr().out
    assert not os.path.exists(os.path.join(ctx.dir, "pairing.json"))


def test_heartbeat_refuses_cleartext_control_loud(ctx, monkeypatch, capsys):
    _run_init(ctx)
    _enroll(ctx)
    ctx.control = "http://control.test"
    monkeypatch.setattr(
        spark_pair, "_http",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no HTTP")))
    assert spark_pair.cmd_heartbeat(ctx) == 1
    err = capsys.readouterr().err
    assert "heartbeat FAILED" in err and "cleartext" in err
    log = open(os.path.join(ctx.dir, "heartbeat.log")).read()
    assert "cleartext" in log


def _write_pairing(ctx, text):
    os.makedirs(ctx.dir, mode=0o700, exist_ok=True)
    with open(os.path.join(ctx.dir, "pairing.json"), "w") as f:
        f.write(text)


def test_redeem_non_object_pairing_json_is_clean_error(ctx, capsys):
    _run_init(ctx)
    _write_pairing(ctx, "[1, 2]")
    assert spark_pair.cmd_redeem(ctx) == 1
    out = capsys.readouterr().out
    assert "run `request` again" in out
    assert "Traceback" not in out


def test_redeem_corrupt_pairing_json_is_clean_error(ctx, capsys):
    _run_init(ctx)
    _write_pairing(ctx, "{not json")
    assert spark_pair.cmd_redeem(ctx) == 1
    out = capsys.readouterr().out
    assert "unreadable" in out and "run `request` again" in out
    assert "Traceback" not in out


def test_redeem_incomplete_pairing_json_is_clean_error(ctx, capsys):
    _run_init(ctx)
    _write_pairing(ctx, json.dumps({"pairing_id": "pair_x"}))
    assert spark_pair.cmd_redeem(ctx) == 1
    out = capsys.readouterr().out
    assert "corrupt or incomplete" in out
    assert "Traceback" not in out


def test_redeem_non_numeric_expiry_is_clean_error(ctx, capsys):
    _run_init(ctx)
    _write_pairing(ctx, json.dumps({"pairing_id": "pair_x",
                                    "expires_at": "soon"}))
    assert spark_pair.cmd_redeem(ctx) == 1
    out = capsys.readouterr().out
    assert "corrupt or incomplete" in out
    assert "Traceback" not in out
