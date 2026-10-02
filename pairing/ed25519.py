#!/usr/bin/env python3
"""Pure-Python Ed25519 (RFC 8032) for spark-vm pairing-code enrollment.

Stdlib only — no third-party crypto dependency, so this runs on the box
(Unraid/Proxmox/self-hosted), in the Cloudflare Python Worker, and in CI.

Used by:
  - pairing/spark-pair.py (box client): keygen, sign
  - the sparkvm-control Worker (inlined copy — see the WORKER COPY note
    below): signature verification of the pairing challenge

Reference: Daniel J. Bernstein's ref10 Python implementation (public
domain), adapted. Validated against the RFC 8032 Section 7 test vectors
in test_ed25519.py.

WORKER COPY: the control-plane Worker is deployed as a single file, so it
carries this same code inline (marked "BEGIN ed25519 / END ed25519").
The two copies MUST stay byte-identical; test_ed25519.py asserts that when
the worker source is reachable.
"""

import hashlib
import os

# ---------------------------------------------------------------------------
# Curve constants (Ed25519 / Curve25519)
# ---------------------------------------------------------------------------

_B = 256
_Q = (1 << 255) - 19
_L = (1 << 252) + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, -1, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y):
    xx = (y * y - 1) * pow(_D * y * y + 1, -1, _Q)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_BY = (4 * pow(5, -1, _Q)) % _Q
_BX = _xrecover(_BY)
_BASE = (_BX % _Q, _BY % _Q, 1, (_BX * _BY) % _Q)
_IDENT = (0, 1, 1, 0)


def _edwards_add(p, q):
    (x1, y1, z1, t1) = p
    (x2, y2, z2, t2) = q
    a = ((y1 - x1) * (y2 - x2)) % _Q
    b = ((y1 + x1) * (y2 + x2)) % _Q
    c = (t1 * 2 * _D * t2) % _Q
    dd = (z1 * 2 * z2) % _Q
    e = (b - a) % _Q
    f = (dd - c) % _Q
    g = (dd + c) % _Q
    h = (b + a) % _Q
    return ((e * f) % _Q, (g * h) % _Q, (f * g) % _Q, (e * h) % _Q)


def _edwards_double(p):
    return _edwards_add(p, p)


def _scalarmult(p, e):
    if e == 0:
        return _IDENT
    q = _scalarmult(p, e // 2)
    q = _edwards_double(q)
    if e & 1:
        q = _edwards_add(q, p)
    return q


def _encodepoint(p):
    (x, y, z, _) = p
    zi = pow(z, -1, _Q)
    x = (x * zi) % _Q
    y = (y * zi) % _Q
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decodepoint(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    sign = (s[31] >> 7) & 1
    if y >= _Q:
        return None
    x = _xrecover(y)
    if (x & 1) != sign:
        x = _Q - x
    p = (x, y, 1, (x * y) % _Q)
    # Reject the point if it is not on the curve's prime-order subgroup.
    # (Compare encoded points: the identity has many (X,Y,Z,T) forms.)
    if _encodepoint(_scalarmult(p, _L)) != _encodepoint(_IDENT):
        return None
    return p


def _hint(m):
    return int.from_bytes(hashlib.sha512(m).digest(), "little") % _L


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def publickey_from_seed(seed):
    """Derive the 32-byte Ed25519 public key from a 32-byte seed."""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    h = hashlib.sha512(seed).digest()
    # Clamp: clear bits 0,1,2 and bit 255; set bit 254.
    a = int.from_bytes(h[:32], "little")
    a &= ~7
    a &= ~(1 << 255)
    a |= (1 << 254)
    return _encodepoint(_scalarmult(_BASE, a))


def generate_keypair():
    """Generate a fresh (private_seed, public_key) pair. Returns bytes."""
    seed = os.urandom(32)
    return seed, publickey_from_seed(seed)


def sign(seed, message):
    """Sign message bytes with the 32-byte private seed. Returns 64 bytes."""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= ~7
    a &= ~(1 << 255)
    a |= (1 << 254)
    prefix = h[32:]
    pub = _encodepoint(_scalarmult(_BASE, a))
    r = _hint(prefix + message)
    big_r = _encodepoint(_scalarmult(_BASE, r))
    s = (_hint(big_r + pub + message) * a + r) % _L
    return big_r + int.to_bytes(s, 32, "little")


def verify(public_key, message, signature):
    """Verify an Ed25519 signature. Returns True/False, never raises on
    malformed inputs (returns False instead)."""
    try:
        if len(public_key) != 32 or len(signature) != 64:
            return False
        a_point = _decodepoint(public_key)
        if a_point is None:
            return False
        r_point = _decodepoint(signature[:32])
        if r_point is None:
            return False
        s = int.from_bytes(signature[32:], "little")
        if s >= _L:
            return False
        h = _hint(signature[:32] + public_key + message)
        # Check [s]B == R + [h]A
        lhs = _scalarmult(_BASE, s)
        rhs = _edwards_add(r_point, _scalarmult(a_point, h))
        return _encodepoint(lhs) == _encodepoint(rhs)
    except Exception:
        return False


def fingerprint(public_key):
    """Human-verifiable fingerprint: 'SHA256:' + base64(sha256(pubkey)),
    grouped for read-back over the phone, e.g.
    'SHA256:ab12 cd34 ...'. The box shows this; the owner compares it at
    approval time."""
    import base64
    digest = hashlib.sha256(bytes(public_key)).digest()
    b64 = base64.b64encode(digest).decode().rstrip("=")
    grouped = " ".join(b64[i:i + 4] for i in range(0, len(b64), 4))
    return "SHA256:" + grouped


def parse_fingerprint(text):
    """Normalize a fingerprint for comparison: strip the SHA256: prefix,
    whitespace, and padding. Returns the canonical base64 body."""
    import base64
    t = text.strip()
    if t.upper().startswith("SHA256:"):
        t = t[7:]
    t = "".join(t.split())
    # re-pad for a canonical form
    t += "=" * (-len(t) % 4)
    try:
        raw = base64.b64decode(t, validate=True)
    except Exception:
        raise ValueError("not a valid fingerprint")
    if len(raw) != 32:
        raise ValueError("fingerprint is not a 32-byte SHA-256 digest")
    return base64.b64encode(raw).decode().rstrip("=")
