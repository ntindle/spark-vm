"""Tests for hosted/push_crypto.py -- the #967 S1 design-hypothesis validation.

Every RFC 8291 intermediate value is pinned against the section 5 /
Appendix A worked example (public test vectors), so a neutered
implementation fails loudly rather than vacuously.  Run from the repo
root: ``python3 -m pytest hosted/``.
"""

import base64
import json
import time

import pytest

from hosted.push_crypto import (
    _N,
    _P,
    _on_curve,
    _aes_gcm_decrypt,
    _aes_gcm_encrypt,
    derive_push_keys,
    ecdh_shared_secret,
    ecdsa_sign,
    ecdsa_verify,
    encrypt_push_message,
    generate_keypair,
    validate_peer_public_key,
    validate_private_key,
    vapid_authorization_header,
    vapid_sign,
)


def b64url(s: str) -> bytes:
    s = "".join(s.split())  # the RFC wraps values across lines
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def b64url_decode_nopad(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# RFC 8291 section 5 / Appendix A worked example (public test vectors).
PLAINTEXT = b64url("V2hlbiBJIGdyb3cgdXAsIEkgd2FudCB0byBiZSBhIHdhdGVybWVsb24")
AS_PUBLIC = b64url("BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
                   "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8")
AS_PRIVATE = b64url("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw")
UA_PUBLIC = b64url("BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-"
                   "JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4")
UA_PRIVATE = b64url("q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94")
SALT = b64url("DGv6ra1nlYgDCS1FRnbzlw")
AUTH_SECRET = b64url("BTBZMqHH6r4Tts7J_aSIgg")

EXP_ECDH_SECRET = b64url("kyrL1jIIOHEzg3sM2ZWRHDRB62YACZhhSlknJ672kSs")
EXP_PRK_KEY = b64url("Snr3JMxaHVDXHWJn5wdC52WjpCtd2EIEGBykDcZW32k")
EXP_IKM = b64url("S4lYMb_L0FxCeq0WhDx813KgSYqU26kOyzWUdsXYyrg")
EXP_PRK = b64url("09_eUZGrsvxChDCGRCdkLiDXrReGOEVeSCdCcPBSJSc")
EXP_CEK = b64url("oIhVW04MRdy2XN9CiKLxTg")
EXP_NONCE = b64url("4h_95klXJ5E_qnoN")
EXP_CIPHERTEXT = b64url("8pfeW0KbunFT06SuDKoJH9Ql87S1QUrd"
                        "irN6GcG7sFz1y1sqLgVi1VhjVkHsUoEsbI_0LpXMuGvnzQ")
EXP_BODY = b64url("DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
                  "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT"
                  "pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")


def test_vector_lengths():
    assert PLAINTEXT == b"When I grow up, I want to be a watermelon"
    assert len(AS_PUBLIC) == len(UA_PUBLIC) == 65
    assert len(AS_PRIVATE) == len(UA_PRIVATE) == 32
    assert len(SALT) == 16 and len(AUTH_SECRET) == 16
    assert len(EXP_BODY) == 86 + len(EXP_CIPHERTEXT)


def test_rfc8291_ecdh_secret():
    # Both directions of the key agreement must land on the same secret.
    assert ecdh_shared_secret(AS_PRIVATE, UA_PUBLIC) == EXP_ECDH_SECRET
    assert ecdh_shared_secret(UA_PRIVATE, AS_PUBLIC) == EXP_ECDH_SECRET


def test_rfc8291_key_schedule_intermediates():
    cek, nonce = derive_push_keys(
        ua_public_key=UA_PUBLIC, as_public_key=AS_PUBLIC,
        as_private_key=AS_PRIVATE, auth_secret=AUTH_SECRET, salt=SALT)
    assert cek == EXP_CEK
    assert nonce == EXP_NONCE
    # The intermediates are not returned by derive_push_keys; recompute the
    # chain stepwise here so each Appendix A value pins its own stage.
    import hashlib
    import hmac as hmac_mod

    def H(k, m):
        return hmac_mod.new(k, m, hashlib.sha256).digest()

    ecdh = ecdh_shared_secret(AS_PRIVATE, UA_PUBLIC)
    assert ecdh == EXP_ECDH_SECRET
    prk_key = H(AUTH_SECRET, ecdh)
    assert prk_key == EXP_PRK_KEY
    key_info = b"WebPush: info\x00" + UA_PUBLIC + AS_PUBLIC
    ikm = H(prk_key, key_info + b"\x01")
    assert ikm == EXP_IKM
    prk = H(SALT, ikm)
    assert prk == EXP_PRK
    assert H(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16] == EXP_CEK
    assert H(prk, b"Content-Encoding: nonce\x00\x01")[:12] == EXP_NONCE


def test_rfc8291_full_body():
    body = encrypt_push_message(
        plaintext=PLAINTEXT, ua_public_key=UA_PUBLIC, auth_secret=AUTH_SECRET,
        as_private_key=AS_PRIVATE, salt=SALT, record_size=4096)
    assert body == EXP_BODY


def test_rfc8291_header_layout():
    header = EXP_BODY[:86]
    assert header[:16] == SALT
    assert int.from_bytes(header[16:20], "big") == 4096
    assert header[20] == 65
    assert header[21:] == AS_PUBLIC


def test_rfc8291_ciphertext_only():
    body = encrypt_push_message(
        plaintext=PLAINTEXT, ua_public_key=UA_PUBLIC, auth_secret=AUTH_SECRET,
        as_private_key=AS_PRIVATE, salt=SALT)
    assert body[86:] == EXP_CIPHERTEXT
    # Authenticated decryption of the RFC ciphertext recovers plaintext+0x02.
    assert _aes_gcm_decrypt(EXP_CEK, EXP_NONCE, EXP_CIPHERTEXT) == PLAINTEXT + b"\x02"


def test_aes_gcm_nist_all_zero_vector():
    # NIST GCMVS test case 1 (AES-GCM, 128-bit key): empty PT/AAD under
    # the zero key/IV. (For the empty input GHASH is empty, so the tag is
    # exactly AES_K(J0) — confirmed independently via `openssl enc
    # -aes-128-ecb` on the zero key.)
    out = _aes_gcm_encrypt(b"\x00" * 16, b"\x00" * 12, b"")
    assert out.hex() == "58e2fccefa7e3061367f1d57a4e7455a"


def test_aes_gcm_tamper_rejected():
    bad = bytearray(EXP_CIPHERTEXT)
    bad[10] ^= 0x01
    with pytest.raises(ValueError, match="authentication failed"):
        _aes_gcm_decrypt(EXP_CEK, EXP_NONCE, bytes(bad))
    bad_tag = bytearray(EXP_CIPHERTEXT)
    bad_tag[-1] ^= 0x01
    with pytest.raises(ValueError, match="authentication failed"):
        _aes_gcm_decrypt(EXP_CEK, EXP_NONCE, bytes(bad_tag))


def test_aes_gcm_wrong_key_rejected():
    with pytest.raises(ValueError, match="authentication failed"):
        _aes_gcm_decrypt(b"\x01" + EXP_CEK[1:], EXP_NONCE, EXP_CIPHERTEXT)


def test_ecdh_wrong_private_key_diverges():
    other_priv = (int.from_bytes(AS_PRIVATE, "big") ^ 0xFF).to_bytes(32, "big")
    assert ecdh_shared_secret(other_priv, UA_PUBLIC) != EXP_ECDH_SECRET


def test_auth_secret_actually_mixes_in():
    cek_a, _ = derive_push_keys(
        ua_public_key=UA_PUBLIC, as_public_key=AS_PUBLIC,
        as_private_key=AS_PRIVATE, auth_secret=AUTH_SECRET, salt=SALT)
    cek_b, _ = derive_push_keys(
        ua_public_key=UA_PUBLIC, as_public_key=AS_PUBLIC,
        as_private_key=AS_PRIVATE, auth_secret=b"\x00" * 16, salt=SALT)
    assert cek_a != cek_b


def test_peer_key_validation():
    with pytest.raises(ValueError):
        ecdh_shared_secret(AS_PRIVATE, b"\x04" + b"\x00" * 64)  # (0,0) not on curve
    with pytest.raises(ValueError):
        ecdh_shared_secret(AS_PRIVATE, b"\x03" + UA_PUBLIC[1:])  # bad prefix
    with pytest.raises(ValueError):
        ecdh_shared_secret(AS_PRIVATE, UA_PUBLIC[:40])  # truncated
    # (1, 1) is not on P-256: 1 != 1 + a + b (mod p).
    not_on_curve = b"\x04" + (1).to_bytes(32, "big") + (1).to_bytes(32, "big")
    with pytest.raises(ValueError):
        ecdh_shared_secret(AS_PRIVATE, not_on_curve)


def test_private_key_validation():
    with pytest.raises(ValueError):
        ecdh_shared_secret(b"\x00" * 32, UA_PUBLIC)  # zero is not a key
    with pytest.raises(ValueError):
        ecdh_shared_secret(b"\x01" * 16, UA_PUBLIC)  # wrong length


def test_keygen_roundtrip():
    priv, pub = generate_keypair()
    assert len(priv) == 32 and pub[:1] == b"\x04" and len(pub) == 65
    # The public key is really d*G: ECDH against a second keypair agrees.
    priv2, pub2 = generate_keypair()
    assert ecdh_shared_secret(priv, pub2) == ecdh_shared_secret(priv2, pub)


def test_record_size_bounds():
    # RFC 8291 section 4: rs MUST *strictly exceed* plaintext + delimiter
    # (1) + tag (16). Both pt+16 and pt+17 are rejected.
    for bad_rs in (len(PLAINTEXT) + 16, len(PLAINTEXT) + 17):
        with pytest.raises(ValueError, match="record_size"):
            encrypt_push_message(
                plaintext=PLAINTEXT, ua_public_key=UA_PUBLIC, auth_secret=AUTH_SECRET,
                as_private_key=AS_PRIVATE, salt=SALT, record_size=bad_rs)
    # The minimum legal rs is pt+18.
    body = encrypt_push_message(
        plaintext=PLAINTEXT, ua_public_key=UA_PUBLIC, auth_secret=AUTH_SECRET,
        as_private_key=AS_PRIVATE, salt=SALT, record_size=len(PLAINTEXT) + 18)
    assert int.from_bytes(body[16:20], "big") == len(PLAINTEXT) + 18
    # Default record size works and round-trips through the header.
    body = encrypt_push_message(
        plaintext=b"ping", ua_public_key=UA_PUBLIC, auth_secret=AUTH_SECRET)
    assert int.from_bytes(body[16:20], "big") == 4096
    assert len(body) == 86 + 4 + 1 + 16


def test_ephemeral_send_decrypts_with_receiver_keys():
    # A fresh ephemeral send must be openable by the subscription holder:
    # the receiver runs ECDH(ua_private, as_public-from-header) and the
    # same KDF chain, then the tag verifies.
    from hosted.push_crypto import _kdf_chain
    body = encrypt_push_message(
        plaintext=b"approval filed", ua_public_key=UA_PUBLIC,
        auth_secret=AUTH_SECRET)
    salt, as_public, ct = body[:16], body[21:86], body[86:]
    ecdh = ecdh_shared_secret(UA_PRIVATE, as_public)
    cek, nonce = _kdf_chain(
        ua_public_key=UA_PUBLIC, as_public_key=as_public,
        ecdh_secret=ecdh, auth_secret=AUTH_SECRET, salt=salt)
    assert _aes_gcm_decrypt(cek, nonce, ct) == b"approval filed\x02"


def test_vapid_jwt_roundtrip():
    priv, pub = generate_keypair()
    jwt = vapid_sign(vapid_private_key=priv, audience="https://push.example.net",
                     expires_at=1893456000, subject="mailto:ops@example.com")
    header_b64, claims_b64, sig_b64 = jwt.split(".")
    header = json.loads(b64url_decode_nopad(header_b64))
    claims = json.loads(b64url_decode_nopad(claims_b64))
    assert header == {"typ": "JWT", "alg": "ES256"}
    assert claims == {"aud": "https://push.example.net", "exp": 1893456000,
                      "sub": "mailto:ops@example.com"}
    signing_input = (header_b64 + "." + claims_b64).encode()
    sig = b64url_decode_nopad(sig_b64)
    assert ecdsa_verify(pub, signing_input, sig)


def test_vapid_tamper_rejected():
    priv, pub = generate_keypair()
    jwt = vapid_sign(vapid_private_key=priv, audience="https://push.example.net",
                     expires_at=1893456000)
    h, c, s = jwt.split(".")
    tampered = h + "." + ("A" if c[0] != "A" else "B") + c[1:] + "." + s
    th, tc, ts = tampered.split(".")
    sig = b64url_decode_nopad(ts)
    assert not ecdsa_verify(pub, (th + "." + tc).encode(), sig)


def test_vapid_wrong_key_rejected():
    priv, _pub = generate_keypair()
    _priv2, pub2 = generate_keypair()
    jwt = vapid_sign(vapid_private_key=priv, audience="https://push.example.net",
                     expires_at=1893456000)
    h, c, s = jwt.split(".")
    sig = b64url_decode_nopad(s)
    assert not ecdsa_verify(pub2, (h + "." + c).encode(), sig)


def test_vapid_authorization_header_shape():
    priv, pub = generate_keypair()
    value = vapid_authorization_header(
        vapid_private_key=priv, vapid_public_key=pub,
        audience="https://push.example.net", expires_at=1893456000)
    assert value.startswith("vapid t=")
    assert ", k=" in value
    _t, k = value[len("vapid t="):].split(", k=")
    assert b64url_decode_nopad(k) == pub


def test_ecdsa_sign_verify_vectors():
    # Determinism (RFC 6979): the same key+message signs identically twice,
    # and a known-answer check via verify.
    priv, pub = generate_keypair()
    assert ecdsa_sign(priv, b"hello") == ecdsa_sign(priv, b"hello")
    assert ecdsa_verify(pub, b"hello", ecdsa_sign(priv, b"hello"))
    assert not ecdsa_verify(pub, b"hellp", ecdsa_sign(priv, b"hello"))


def _hex(s: str) -> bytes:
    return bytes.fromhex("".join(s.split()))


def test_rfc6979_a25_kat():
    # Independent anchor for the ECDSA/VAPID path (QA B1): the RFC 6979
    # Appendix A.2.5 known-answer test (P-256, SHA-256, message "sample").
    # Pins the deterministic nonce, the signing math, AND the verifier —
    # a systematically wrong-but-self-consistent implementation cannot
    # survive this.
    priv = _hex("C9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721")
    pub = (b"\x04"
           + _hex("60FED4BA255A9D31C961EB74C6356D68C049B8923B61FA6CE669622E60F29FB6")
           + _hex("7903FE1008B8BC99A41AE9E95628BC64F2F1B20C2D7E9F5177A3C294D4462299"))
    exp_r = _hex("EFD48B2AACB6A8FD1140DD9CD45E81D69D2C877B56AAF991C34D0EA84EAF3716")
    exp_s = _hex("F7CB1C942D657C41D436C7A1B6E29F65F3E900DBB9AFF4064DC4AB2F843ACDA8")
    sig = ecdsa_sign(priv, b"sample")
    assert sig == exp_r + exp_s, "RFC 6979 A.2.5 KAT mismatch"
    assert ecdsa_verify(pub, b"sample", sig)
    bad = bytearray(sig)
    bad[5] ^= 0x01
    assert not ecdsa_verify(pub, b"sample", bytes(bad))
    assert not ecdsa_verify(pub, b"tampered", sig)
    # Malformed inputs never raise, per the documented contract.
    for malformed in (b"", b"\x00" * 63, b"\x00" * 65, b"\x00" * 64):
        assert not ecdsa_verify(pub, b"sample", malformed)
    assert not ecdsa_verify(b"\x04" + b"\x00" * 64, b"sample", sig)


def test_golden_ephemeral_vector():
    # Independent anchor for the ephemeral production path (QA B2): fixed
    # scalar + fixed salt (arbitrary test constants, not secrets), full
    # body pinned byte-for-byte. The golden body was verified during
    # authoring to decrypt under the independent `cryptography` library
    # via receiver-side re-derivation — the committed test needs no new
    # dependencies but the interop claim is auditable from the constant.
    fixed_scalar = bytes(range(1, 33))
    fixed_salt = bytes(range(0xA0, 0xB0))
    body = encrypt_push_message(
        plaintext=b"golden vector probe", ua_public_key=UA_PUBLIC,
        auth_secret=AUTH_SECRET, as_private_key=fixed_scalar, salt=fixed_salt)
    assert b64url(
        "oKGio6SlpqeoqaqrrK2urwAAEABBBFFcPW6545a5BNP-yn9U_c0MwemXvzddylFa0KbDtANfRTa-OlDzGPv5pUdZAqIhUCvvDVfgjFOyzApW8X2fk1QMqLwjlGKQzrb055GZsUzmZ-_RT7zuuGZbYX49C7EpeQZj7_w"
    ) == body


def test_full_send_timing_recorded():
    # Not a perf gate (CI machines vary) -- records the wall-clock cost of
    # one in-worker send for the S1 design decision, and fails only on an
    # absurd regression.
    priv, pub = generate_keypair()
    start = time.perf_counter()
    body = encrypt_push_message(plaintext=b"x" * 200, ua_public_key=pub,
                                auth_secret=b"\x11" * 16)
    jwt = vapid_sign(vapid_private_key=priv, audience="https://push.example.net",
                     expires_at=1893456000)
    elapsed = time.perf_counter() - start
    assert len(body) > 86 and jwt.count(".") == 2
    assert elapsed < 30, f"one send took {elapsed:.1f}s -- investigate before S1"
    print(f"\none pure-Python send (200B payload): {elapsed * 1000:.0f} ms")


def _valid_range_off_curve_point(pub: bytes) -> bytes:
    """A 65-octet point whose coordinates are in field range but which is
    NOT on the P-256 curve: flip low bits of a valid point's x until the
    curve equation fails (a random (x, y) lands on the curve with
    probability ~1/2 per try, so this terminates in a flip or two, and
    deterministically for the given key). Only the on-curve check can
    fire on the result — the exact attack the RFC 8291 section 7 gate
    exists for."""
    x = int.from_bytes(pub[1:33], "big")
    y = int.from_bytes(pub[33:65], "big")
    assert _on_curve(x, y), "premise: the source point is on the curve"
    for bit in range(64):
        x2 = x ^ (1 << bit)
        if x2 < _P and not _on_curve(x2, y):
            return b"\x04" + x2.to_bytes(32, "big") + y.to_bytes(32, "big")
    raise AssertionError("unreachable: 64 x-flips all stayed on-curve")


def test_public_key_validators():
    # The public validation API push_sender (and future cross-module
    # callers) must use instead of push_crypto's underscore helpers.
    priv, pub = generate_keypair()
    validate_peer_public_key(pub)
    validate_private_key(priv)
    # Fail-closed: non-bytes never raise TypeError, always ValueError.
    for bad in ("not-bytes", None, 123, b"\x04" + b"\x00" * 63,
                b"\x04" + b"\x00" * 65, b"\x05" + b"\x00" * 64,
                # 0xff..ff exceeds the field prime, so this is rejected
                # by the field-range check, not the curve check:
                b"\x04" + b"\xff" * 64):
        with pytest.raises(ValueError):
            validate_peer_public_key(bad)
    # The true invalid-curve path: coordinates in field range, point not
    # on the curve. Pins that the curve check fires (not the range check).
    with pytest.raises(ValueError, match="not on the P-256 curve"):
        validate_peer_public_key(_valid_range_off_curve_point(pub))
    n_bytes = _N.to_bytes(32, "big")
    for bad in ("not-bytes", None, b"short", b"\x00" * 32,
                b"\xff" * 32, n_bytes):  # 0, 2^256-1, and N itself
        with pytest.raises(ValueError):
            validate_private_key(bad)
