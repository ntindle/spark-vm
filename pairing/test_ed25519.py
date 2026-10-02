"""Tests for pairing/ed25519.py (pure-Python Ed25519, RFC 8032).

Vectors are cross-checked against an independent implementation: each
(seed, pubkey, signature) triple below was produced by the `cryptography`
package and verified to match this module's keygen/sign/verify in both
directions before being hardcoded (ed25519 signatures are deterministic,
so the vectors are stable).
"""
import base64
import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import ed25519

# (seed_hex, pubkey_hex, sig_hex over b"pairing-challenge", message)
VECTORS = [
    ("0000000000000000000000000000000000000000000000000000000000000000",
     "3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29",
     "7f01b65a6ea35b8d505ad13ddd3022df5c4152c8f30c6e70f1ece133801b1e10b"
     "7b0429edc6e98ba1d16b0af1cd6ab421809d6abe5d6b20b928b80cbd3a20107",
     b"pairing-challenge"),
    ("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
     "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8",
     "eada9c4ccab294217f47e5b361d52d6d2b4ef6c9fe00ced3ce745f114825e32c8"
     "aac2de8dfff07bba728ee94257e4f91c8da6c4a2e1cbe4bcfe08dd4efbb5002",
     b"pairing-challenge"),
    ("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
     "76a1592044a6e4f511265bca73a604d90b0529d1df602be30a19a9257660d1f5",
     "544798b9483f09f9d292c523319258a749d152c797861e5fea638ae33c6e6a4b5"
     "20b216a6c5eae106507e154c331cafbd2723ef262f5f79bbcf60ddc89de9907",
     b"pairing-challenge"),
]


@pytest.mark.parametrize("seed_hex,pub_hex,sig_hex,msg", VECTORS)
def test_vector_pubkey(seed_hex, pub_hex, sig_hex, msg):
    assert ed25519.publickey_from_seed(bytes.fromhex(seed_hex)).hex() == pub_hex


@pytest.mark.parametrize("seed_hex,pub_hex,sig_hex,msg", VECTORS)
def test_vector_sign(seed_hex, pub_hex, sig_hex, msg):
    assert ed25519.sign(bytes.fromhex(seed_hex), msg).hex() == sig_hex


@pytest.mark.parametrize("seed_hex,pub_hex,sig_hex,msg", VECTORS)
def test_vector_verify(seed_hex, pub_hex, sig_hex, msg):
    assert ed25519.verify(bytes.fromhex(pub_hex), msg, bytes.fromhex(sig_hex))


def test_roundtrip_and_tamper():
    seed, pub = ed25519.generate_keypair()
    assert len(seed) == 32 and len(pub) == 32
    msg = b"server-issued challenge bytes"
    sig = ed25519.sign(seed, msg)
    assert ed25519.verify(pub, msg, sig)
    # tampered message
    assert not ed25519.verify(pub, msg + b"x", sig)
    # tampered signature
    bad = bytearray(sig)
    bad[17] ^= 4
    assert not ed25519.verify(pub, msg, bytes(bad))
    # wrong key
    _, pub2 = ed25519.generate_keypair()
    assert not ed25519.verify(pub2, msg, sig)
    # truncated / empty
    assert not ed25519.verify(pub, msg, sig[:63])
    assert not ed25519.verify(pub, msg, b"\x00" * 64)


def test_verify_rejects_malformed_without_raising():
    seed, pub = ed25519.generate_keypair()
    sig = ed25519.sign(seed, b"m")
    assert not ed25519.verify(b"short", b"m", sig)
    assert not ed25519.verify(pub, b"m", b"short")
    assert not ed25519.verify(bytes(32), b"m", sig)  # identity point
    # s >= L must fail
    bad = sig[:32] + b"\xff" * 32
    assert not ed25519.verify(pub, b"m", bad)


def test_publickey_from_seed_rejects_bad_length():
    with pytest.raises(ValueError):
        ed25519.publickey_from_seed(b"short")
    with pytest.raises(ValueError):
        ed25519.sign(b"short", b"m")


def test_fingerprint_roundtrip():
    _, pub = ed25519.generate_keypair()
    fp = ed25519.fingerprint(pub)
    assert fp.startswith("SHA256:")
    canon = base64.b64encode(hashlib.sha256(pub).digest()).decode().rstrip("=")
    assert ed25519.parse_fingerprint(fp) == canon
    # whitespace + prefix case tolerated; body case preserved
    assert ed25519.parse_fingerprint("  sha256:" + fp[7:].replace(" ", "")) == canon
    for bad in ("garbage!!", "SHA256:abcd", "", "SHA256:" + "A" * 43 + "!"):
        with pytest.raises(ValueError):
            ed25519.parse_fingerprint(bad)


def test_worker_inline_copy_byte_identical():
    """The control-plane Worker inlines this module; the copies must match.

    Skipped when the worker source is not reachable (e.g. CI on a fork
    without the deployment workspace).
    """
    worker = ("/home/hatch/workspace/goals/"
              "sparkvm-dev-website-v2-cloudflare-management-infra/"
              "control-plane/worker.py")
    if not os.path.exists(worker):
        pytest.skip("worker source not reachable here")
    src = open(worker).read()
    marker = "# --- BEGIN ed25519 (#844 pairing-code enrollment) ---"
    assert marker in src, "ed25519 block missing from worker.py"
    inline = src.split(marker)[1].split("# --- END ed25519 ---")[0].lstrip("\n")
    lines = inline.splitlines(keepends=True)
    i = 0
    while i < len(lines) and lines[i].startswith("#"):
        i += 1
    body = "".join(lines[i:]).lstrip("\n")
    if body.startswith("#!"):
        body = body.split("\n", 1)[1]
    orig = open(os.path.join(os.path.dirname(__file__), "ed25519.py")).read()
    if orig.startswith("#!"):
        orig = orig.split("\n", 1)[1]
    assert body == orig, "worker.py's inlined ed25519.py has drifted"
