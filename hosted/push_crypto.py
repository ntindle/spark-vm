"""Web Push content-encoding crypto (RFC 8291 ``aes128gcm``), stdlib-only.

This module is the explicit design-hypothesis validation step required by
``docs/HOSTED_PLANE_PUSH_GAP_ANALYSIS.md`` (GP1, issue #967): the plane
worker is Python with stdlib-only imports, and RFC 8291 needs ECDH P-256 +
HKDF + AES-GCM plus ECDSA P-256 for VAPID signing (RFC 8292) -- none of
which the stdlib provides.  This module implements all four in pure
Python and proves them against the RFC 8291 section 5 / Appendix A worked
example, so the S1 sender design can decide *in-worker sender* vs
*a separate sender service* on evidence rather than assumption.

Public API (sender side only -- the plane never decrypts):

- :func:`generate_keypair` -- fresh P-256 keypair (ephemeral sender keys,
  VAPID identity).
- :func:`ecdh_shared_secret` -- RFC 8291 section 3.1 shared secret.
- :func:`derive_push_keys` -- the full RFC 8291 section 3.3/3.4 pipeline:
  shared secret -> PRK_key -> IKM -> PRK -> (CEK, nonce).
- :func:`encrypt_push_message` -- RFC 8188 single-record ``aes128gcm``
  body: 16-octet salt || u32 record size || keyid || AES-GCM ciphertext.
- :func:`vapid_sign` / :func:`vapid_authorization_header` -- RFC 8292
  VAPID JWT (ES256) for the push-service request.
- :func:`validate_peer_public_key` / :func:`validate_private_key` --
  fail-closed public validators for a peer (user-agent) P-256 public key
  (RFC 8291 section 7 curve check) and a P-256 private key, for
  cross-module callers (e.g. :mod:`hosted.push_sender`) that need the
  validation verdict without the decoded coordinates.

Security posture (read before reusing):

- The P-256 scalar multiplication is plain double-and-add and the AES is
  table-driven: **not constant-time**.  Timing side-channels are assessed
  as non-exploitable in the plane's threat model -- the box (the only
  attacker-adjacent party that can trigger sends) gets no timing oracle on
  the crypto itself: signing happens on the plane, and the box observes
  only the eventual delivery to the owner's device through network jitter
  orders of magnitude larger than the operation.  If this module is ever
  reused where an attacker *does* get a local timing oracle, replace the
  field arithmetic with a constant-time implementation first.
- ECDSA uses deterministic nonces (RFC 6979, HMAC-SHA-256): no RNG
  failure can leak the VAPID key through a repeated ``k``.  Ephemeral
  keypairs and salts still need a CSPRNG -- :func:`generate_keypair` and
  the default salt use :mod:`secrets`.
- Peer public keys are validated before use (length, ``0x04`` prefix,
  coordinates in range, on-curve, not infinity), per the RFC 8291 section
  7 requirement -- an unvalidated peer key is an invalid-curve attack.
- ``auth_secret`` values are ``bytes`` in and out; this module never logs
  key material.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct


# ---------------------------------------------------------------------------
# P-256 (FIPS 186-4, section D.2.3)
# ---------------------------------------------------------------------------

_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_A = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC
_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
_GX = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
_GY = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5
# Group order n (FIPS 186-4, D.2.3) -- value verified against
# `openssl ecparam -name prime256v1 -param_enc explicit` on 2026-10-04
# (a hand-transcribed constant failed the RFC 8291 vector test; the
# test caught it).
_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551

_G = (_GX, _GY)
_INFINITY = None  # point-at-infinity sentinel


def _on_curve(x: int, y: int) -> bool:
    return (y * y - (x * x * x + _A * x + _B)) % _P == 0


def _point_add(p, q):
    """Affine point addition; either operand may be the infinity sentinel."""
    if p is _INFINITY:
        return q
    if q is _INFINITY:
        return p
    x1, y1 = p
    x2, y2 = q
    if x1 == x2:
        if (y1 + y2) % _P == 0:
            return _INFINITY
        # point doubling
        lam = (3 * x1 * x1 + _A) * pow(2 * y1, -1, _P) % _P
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, _P) % _P
    x3 = (lam * lam - x1 - x2) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return (x3, y3)


def _scalar_mult(k: int, p: tuple[int, int]) -> tuple[int, int]:
    """Double-and-add scalar multiplication (not constant-time; see module
    docstring for the threat-model assessment)."""
    if not 1 <= k < _N:
        raise ValueError("scalar out of range")
    acc = _INFINITY
    addend = p
    while k:
        if k & 1:
            acc = _point_add(acc, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return acc


def _decode_uncompressed_point(encoded: bytes) -> tuple[int, int]:
    """Parse and validate a 65-octet uncompressed P-256 point (RFC 8291
    section 7: the peer key MUST be verified on the curve)."""
    if len(encoded) != 65:
        raise ValueError(f"uncompressed point must be 65 octets, got {len(encoded)}")
    if encoded[0] != 0x04:
        raise ValueError("uncompressed point must start with 0x04")
    x = int.from_bytes(encoded[1:33], "big")
    y = int.from_bytes(encoded[33:65], "big")
    if not (0 <= x < _P and 0 <= y < _P):
        raise ValueError("point coordinates out of field range")
    if not _on_curve(x, y):
        raise ValueError("point is not on the P-256 curve")
    return (x, y)


def _encode_uncompressed_point(p) -> bytes:
    if p is _INFINITY:
        raise ValueError("cannot encode the point at infinity")
    x, y = p
    return b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")


def _check_private_key(private_key: bytes) -> int:
    if len(private_key) != 32:
        raise ValueError(f"private key must be 32 octets, got {len(private_key)}")
    d = int.from_bytes(private_key, "big")
    if not 1 <= d < _N:
        raise ValueError("private key out of range")
    return d


def validate_peer_public_key(encoded: bytes) -> None:
    """Fail-closed validation of a peer (user-agent) P-256 public key for
    the RFC 8291 KDF: 65-octet uncompressed point, verified on the curve
    (RFC 8291 section 7).

    Public counterpart of :func:`_decode_uncompressed_point` — same
    check, ``None`` return, for callers (e.g. :mod:`hosted.push_sender`)
    that need the validation verdict without the decoded coordinates.
    Anything invalid — non-bytes, wrong shape, off-curve — raises
    :exc:`ValueError` before any crypto touches the value.
    """
    if not isinstance(encoded, bytes):
        raise ValueError("peer public key must be bytes")
    _decode_uncompressed_point(encoded)


def validate_private_key(private_key: bytes) -> None:
    """Fail-closed validation of a P-256 private key: 32 octets,
    ``1 <= d < N``. Public counterpart of :func:`_check_private_key` —
    same check, ``None`` return, for cross-module callers. Anything
    invalid — non-bytes, wrong length, out of range — raises
    :exc:`ValueError`.
    """
    if not isinstance(private_key, bytes):
        raise ValueError("private key must be bytes")
    _check_private_key(private_key)


def generate_keypair() -> tuple[bytes, bytes]:
    """Fresh P-256 keypair: (private_key 32 octets, public_key 65 octets
    uncompressed).  Uses :mod:`secrets` (CSPRNG)."""
    d = secrets.randbelow(_N - 1) + 1
    return d.to_bytes(32, "big"), _encode_uncompressed_point(_scalar_mult(d, _G))


def ecdh_shared_secret(private_key: bytes, peer_public_key: bytes) -> bytes:
    """RFC 8291 section 3.1: x-coordinate of ``d * Q_peer`` as 32 octets.
    The peer key is curve-validated; an invalid key raises ValueError."""
    d = _check_private_key(private_key)
    qx, qy = _decode_uncompressed_point(peer_public_key)
    pt = _scalar_mult(d, (qx, qy))
    if pt is None:  # unreachable: n is prime and 1 <= d < n, so d*Q != O
        raise ValueError("ECDH produced the point at infinity")
    return pt[0].to_bytes(32, "big")


# ---------------------------------------------------------------------------
# HKDF (RFC 5869, SHA-256)
# ---------------------------------------------------------------------------

def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    if not 1 <= length <= 255 * 32:
        raise ValueError("HKDF length out of range")
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


# ---------------------------------------------------------------------------
# AES-128 (FIPS 197) -- S-box computed from the field definition so the
# table itself needs no trusted constant.
# ---------------------------------------------------------------------------

def _xtime(a: int) -> int:
    return (((a << 1) ^ 0x11B) & 0xFF) if (a & 0x80) else ((a << 1) & 0xFF)


def _gf_mul(a: int, b: int) -> int:
    p = 0
    while b:
        if b & 1:
            p ^= a
        a = _xtime(a)
        b >>= 1
    return p


def _gf_inv(a: int) -> int:
    if a == 0:
        return 0
    r = 1
    for _ in range(254):
        r = _gf_mul(r, a)
    return r


def _rotl8(v: int, n: int) -> int:
    return ((v << n) | (v >> (8 - n))) & 0xFF


def _build_sbox() -> bytes:
    out = bytearray(256)
    for i in range(256):
        inv = _gf_inv(i)
        out[i] = inv ^ _rotl8(inv, 1) ^ _rotl8(inv, 2) ^ _rotl8(inv, 3) ^ _rotl8(inv, 4) ^ 0x63
    return bytes(out)


_SBOX = _build_sbox()


def _aes128_key_expansion(key: bytes) -> list[bytes]:
    rcon = [0x01]
    for _ in range(9):
        rcon.append(_xtime(rcon[-1]))
    w = [int.from_bytes(key[i:i + 4], "big") for i in range(0, 16, 4)]
    for i in range(4, 44):
        temp = w[i - 1]
        if i % 4 == 0:
            temp = ((_SBOX[(temp >> 16) & 0xFF] << 24)
                    | (_SBOX[(temp >> 8) & 0xFF] << 16)
                    | (_SBOX[temp & 0xFF] << 8)
                    | _SBOX[(temp >> 24) & 0xFF]) ^ (rcon[i // 4 - 1] << 24)
        w.append(w[i - 4] ^ temp)
    return [b"".join(w[i].to_bytes(4, "big") for i in range(r, r + 4)) for r in range(0, 44, 4)]


def _aes128_encrypt_block(key: bytes, block: bytes) -> bytes:
    if len(key) != 16 or len(block) != 16:
        raise ValueError("AES-128 needs 16-octet key and block")
    rk = _aes128_key_expansion(key)
    # state in column-major order: state[4*col + row]
    s = bytearray(x ^ y for x, y in zip(block, rk[0]))
    for rnd in range(1, 10):
        s = bytearray(_SBOX[b] for b in s)  # SubBytes
        s = bytearray([  # ShiftRows
            s[0], s[5], s[10], s[15],
            s[4], s[9], s[14], s[3],
            s[8], s[13], s[2], s[7],
            s[12], s[1], s[6], s[11],
        ])
        # MixColumns
        for c in range(4):
            a0, a1, a2, a3 = s[4 * c], s[4 * c + 1], s[4 * c + 2], s[4 * c + 3]
            s[4 * c] = _gf_mul(a0, 2) ^ _gf_mul(a1, 3) ^ a2 ^ a3
            s[4 * c + 1] = a0 ^ _gf_mul(a1, 2) ^ _gf_mul(a2, 3) ^ a3
            s[4 * c + 2] = a0 ^ a1 ^ _gf_mul(a2, 2) ^ _gf_mul(a3, 3)
            s[4 * c + 3] = _gf_mul(a0, 3) ^ a1 ^ a2 ^ _gf_mul(a3, 2)
        rk_b = rk[rnd]
        s = bytearray(x ^ y for x, y in zip(s, rk_b))
    s = bytearray(_SBOX[b] for b in s)
    s = bytearray([
        s[0], s[5], s[10], s[15],
        s[4], s[9], s[14], s[3],
        s[8], s[13], s[2], s[7],
        s[12], s[1], s[6], s[11],
    ])
    s = bytearray(x ^ y for x, y in zip(s, rk[10]))
    return bytes(s)


# ---------------------------------------------------------------------------
# AES-GCM (the AEAD_AES_128_GCM of RFC 8291 section 3.4)
# ---------------------------------------------------------------------------

_GCM_R = 0xE1000000000000000000000000000000


def _gf128_mul(x: int, y: int) -> int:
    z = 0
    v = x
    for i in range(128):
        if (y >> (127 - i)) & 1:
            z ^= v
        lsb = v & 1
        v >>= 1
        if lsb:
            v ^= _GCM_R
    return z


def _ghash(h: int, aad: bytes, data: bytes) -> int:
    padded = (
        aad + b"\x00" * (-len(aad) % 16)
        + data + b"\x00" * (-len(data) % 16)
        + (8 * len(aad)).to_bytes(8, "big")
        + (8 * len(data)).to_bytes(8, "big")
    )
    y = 0
    for i in range(0, len(padded), 16):
        y ^= int.from_bytes(padded[i:i + 16], "big")
        y = _gf128_mul(y, h)
    return y


def _gcm_ctr(key: bytes, nonce12: bytes, data: bytes) -> bytes:
    # GCM counter blocks: J0 = nonce || 0x00000001 masks the tag, so the
    # first data block uses counter value 2 (not 1).
    out = bytearray()
    for i in range(0, len(data), 16):
        counter = (i // 16) + 2
        keystream = _aes128_encrypt_block(key, nonce12 + counter.to_bytes(4, "big"))
        blk = data[i:i + 16]
        out += bytes(a ^ b for a, b in zip(blk, keystream))
    return bytes(out)


def _aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Returns ciphertext || 16-octet tag."""
    if len(key) != 16 or len(nonce) != 12:
        raise ValueError("GCM needs a 16-octet key and 12-octet nonce")
    h = int.from_bytes(_aes128_encrypt_block(key, b"\x00" * 16), "big")
    j0 = nonce + b"\x00\x00\x00\x01"
    ciphertext = _gcm_ctr(key, nonce, plaintext)
    s = _ghash(h, aad, ciphertext).to_bytes(16, "big")
    tag = bytes(a ^ b for a, b in zip(_aes128_encrypt_block(key, j0), s))
    return ciphertext + tag


def _aes_gcm_decrypt(key: bytes, nonce: bytes, ciphertext_and_tag: bytes,
                     aad: bytes = b"") -> bytes:
    """Verifies the tag (constant-time compare) then decrypts.  Used by the
    test suite and any future receiver-side self-tests; the plane's send
    path never calls it."""
    if len(ciphertext_and_tag) < 16:
        raise ValueError("ciphertext shorter than the GCM tag")
    ciphertext, tag = ciphertext_and_tag[:-16], ciphertext_and_tag[-16:]
    if len(key) != 16 or len(nonce) != 12:
        raise ValueError("GCM needs a 16-octet key and 12-octet nonce")
    h = int.from_bytes(_aes128_encrypt_block(key, b"\x00" * 16), "big")
    j0 = nonce + b"\x00\x00\x00\x01"
    s = _ghash(h, aad, ciphertext).to_bytes(16, "big")
    expected = bytes(a ^ b for a, b in zip(_aes128_encrypt_block(key, j0), s))
    if not hmac.compare_digest(tag, expected):
        raise ValueError("GCM authentication failed")
    return _gcm_ctr(key, nonce, ciphertext)


# ---------------------------------------------------------------------------
# RFC 8291 section 3.3 / 3.4 key derivation + RFC 8188 record framing
# ---------------------------------------------------------------------------

def _kdf_chain(*, ua_public_key: bytes, as_public_key: bytes,
               ecdh_secret: bytes, auth_secret: bytes,
               salt: bytes) -> tuple[bytes, bytes]:
    """RFC 8291 sections 3.3/3.4 after the ECDH step: shared secret ->
    PRK_key -> IKM -> PRK -> (CEK, nonce).  Shared by the sender path and
    the test's receiver emulation (a real user agent runs this same chain
    with ``ECDH(ua_private, as_public)`` as the secret)."""
    if len(auth_secret) != 16:  # RFC 8291 section 3.2: exactly 16 octets
        raise ValueError(f"auth_secret must be 16 octets, got {len(auth_secret)}")
    if len(salt) != 16:
        raise ValueError(f"salt must be 16 octets, got {len(salt)}")
    prk_key = _hkdf_extract(auth_secret, ecdh_secret)
    key_info = b"WebPush: info\x00" + ua_public_key + as_public_key
    ikm = _hkdf_expand(prk_key, key_info, 32)
    prk = _hkdf_extract(salt, ikm)
    cek = _hkdf_expand(prk, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf_expand(prk, b"Content-Encoding: nonce\x00", 12)
    return cek, nonce


def derive_push_keys(*, ua_public_key: bytes, as_public_key: bytes,
                     as_private_key: bytes, auth_secret: bytes,
                     salt: bytes) -> tuple[bytes, bytes]:
    """Run the RFC 8291 key schedule (sender side).  Returns
    (content-encryption key 16 octets, nonce 12 octets)."""
    ecdh = ecdh_shared_secret(as_private_key, ua_public_key)
    return _kdf_chain(ua_public_key=ua_public_key, as_public_key=as_public_key,
                      ecdh_secret=ecdh, auth_secret=auth_secret, salt=salt)


def encrypt_push_message(*, plaintext: bytes, ua_public_key: bytes,
                         auth_secret: bytes, as_private_key: bytes | None = None,
                         salt: bytes | None = None,
                         record_size: int = 4096) -> bytes:
    """Encrypt one push message as an RFC 8188 single-record ``aes128gcm``
    body: ``salt(16) || rs(u32be) || 0x41 || as_public(65) || ciphertext``.

    RFC 8291 section 4: the record size MUST exceed plaintext + padding
    delimiter (1 octet) + tag (16 octets), i.e. rs > len(plaintext) + 17.
    A fresh ephemeral sender keypair and salt are generated when not
    supplied.  A caller-supplied salt MUST be unique per message (test
    vectors only) — reusing a (key, salt) pair across messages reuses a
    GCM (key, nonce) pair and destroys confidentiality.
    """
    overhead = len(plaintext) + 1 + 16
    if not overhead < record_size <= 0xFFFFFFFF:
        raise ValueError(
            f"record_size {record_size} must strictly exceed plaintext+delimiter+tag "
            f"({overhead}) and fit in u32"
        )
    if as_private_key is None:
        as_private_key, gen_pub = generate_keypair()
    else:
        _check_private_key(as_private_key)
        gen_pub = _encode_uncompressed_point(
            _scalar_mult(int.from_bytes(as_private_key, "big"), _G))
    if salt is None:
        salt = secrets.token_bytes(16)
    if len(salt) != 16:
        raise ValueError("salt must be 16 octets")
    _decode_uncompressed_point(ua_public_key)  # validate the subscription key
    cek, nonce = derive_push_keys(
        ua_public_key=ua_public_key, as_public_key=gen_pub,
        as_private_key=as_private_key, auth_secret=auth_secret, salt=salt)
    ciphertext = _aes_gcm_encrypt(cek, nonce, plaintext + b"\x02")
    header = salt + struct.pack(">I", record_size) + b"\x41" + gen_pub
    return header + ciphertext


# ---------------------------------------------------------------------------
# ECDSA P-256 + RFC 6979 (for VAPID, RFC 8292)
# ---------------------------------------------------------------------------

def _rfc6979_nonce(private_int: int, hashed: bytes) -> int:
    """Deterministic ECDSA nonce (RFC 6979, HMAC-SHA-256).  ``hashed`` is
    the 32-octet message hash (qlen == 256, so bits2octets is a plain
    reduction)."""
    x = private_int.to_bytes(32, "big")
    z = int.from_bytes(hashed, "big")
    if z > _N:
        z -= _N
    bx = z.to_bytes(32, "big")
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + x + bx, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + x + bx, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        t = b""
        while len(t) < 32:
            v = hmac.new(k, v, hashlib.sha256).digest()
            t += v
        cand = int.from_bytes(t[:32], "big")
        if 1 <= cand < _N:
            return cand
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def ecdsa_sign(private_key: bytes, message: bytes) -> bytes:
    """ES256 signature of ``message``: 64 octets ``r || s``."""
    d = _check_private_key(private_key)
    digest = hashlib.sha256(message).digest()
    e = int.from_bytes(digest, "big")
    k = _rfc6979_nonce(d, digest)
    r = _scalar_mult(k, _G)[0] % _N
    if r == 0:
        raise ValueError("degenerate ECDSA nonce")
    s = (pow(k, -1, _N) * (e + r * d)) % _N
    if s == 0:
        raise ValueError("degenerate ECDSA signature")
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def ecdsa_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify an ES256 ``r || s`` signature.  Returns False (never raises)
    for any malformed input."""
    try:
        if len(signature) != 64:
            return False
        qx, qy = _decode_uncompressed_point(public_key)
        r = int.from_bytes(signature[:32], "big")
        s = int.from_bytes(signature[32:], "big")
        if not (1 <= r < _N and 1 <= s < _N):
            return False
        e = int.from_bytes(hashlib.sha256(message).digest(), "big")
        w = pow(s, -1, _N)
        u1 = (e * w) % _N
        u2 = (r * w) % _N
        pt = _point_add(_scalar_mult(u1, _G), _scalar_mult(u2, (qx, qy)))
        if pt is _INFINITY:
            return False
        return pt[0] % _N == r
    except (ValueError, TypeError):
        return False


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def vapid_sign(*, vapid_private_key: bytes, audience: str, expires_at: int,
               subject: str | None = None) -> str:
    """Build a VAPID JWT (RFC 8292 section 2): ES256 over
    ``b64(header) + "." + b64(claims)``.  ``audience`` is the push service
    origin (scheme + host); ``expires_at`` is a unix timestamp.  RFC 8292
    asks that ``exp`` be at most 24h in the future — the caller sets it;
    this function does not second-guess the clock."""
    header = {"typ": "JWT", "alg": "ES256"}
    claims: dict = {"aud": audience, "exp": expires_at}
    if subject is not None:
        claims["sub"] = subject
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "." + _b64url(json.dumps(claims, separators=(",", ":")).encode())
    ).encode()
    sig = ecdsa_sign(vapid_private_key, signing_input)
    return signing_input.decode() + "." + _b64url(sig)


def vapid_authorization_header(*, vapid_private_key: bytes, vapid_public_key: bytes,
                               audience: str, expires_at: int,
                               subject: str | None = None) -> str:
    """The ``Authorization`` header value for a push request:
    ``vapid t=<jwt>, k=<uncompressed VAPID public key, base64url>``."""
    _decode_uncompressed_point(vapid_public_key)  # fail fast on a bad key
    jwt = vapid_sign(vapid_private_key=vapid_private_key, audience=audience,
                     expires_at=expires_at, subject=subject)
    return f"vapid t={jwt}, k={_b64url(vapid_public_key)}"
