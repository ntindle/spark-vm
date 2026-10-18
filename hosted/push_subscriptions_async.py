"""Async plane-port of the #1392 subscription endpoints (GP2 plane half).

`hosted/push_subscriptions_async.py` ships the async counterpart of the four
owner-auth subscription endpoints pinned in
`docs/PUSH_SUBSCRIPTION_WIRE_CONTRACT.md` (decisions D98-D102), against the
#988 D1 ``push_subscriptions`` schema
(`docs/PUSH_SENDER_SCHEMA_CONTRACT.md` section 1.1). Like
`hosted/push_enqueue_async.py`, this file is droppable into `worker.py`
verbatim: stdlib-only, no imports from the sync modules, pure-compute
helpers inlined with source citations (the ed25519 / push_crypto
precedent), and the DB seam as awaited ``_D1`` calls
(``await db.prepare(sql).bind(*args).run()`` / ``.first()`` / ``.all()`` —
F-PP-2; no synchronous D1 exists on the worker).

Endpoint entry points (each returns an :class:`HttpResult`; the worker
wires these behind #843 owner auth):

- ``await get_vapid_pubkey(*, vapid_pubkey_b64url)`` — D98-key delivery.
- ``await list_subscriptions(db, *, owner_principal, box_id, owns_box)`` —
  display fields only (D98), 404 for an unowned box.
- ``await subscribe(db, *, owner_principal, box_id, device, endpoint, keys,
  added_by, owns_box, encrypt_at_rest, data_key_version="v1",
  vapid_key_id="v1", now=None)`` — D99 validation, D100 upsert,
  D45 encrypt-at-rest.
- ``await unsubscribe(db, *, owner_principal, box_id, device, owns_box)`` —
  D101 real delete.
- ``serve_sw_js(*, sw_js_bytes)`` — D102; the plane serves
  ``hosted/dashboard/sw.js`` at ``/sw.js``.

Trust posture (D2): the caller resolves ``box_id -> owner_principal``
from the plane's enrollment registry and passes the resolved principal
in; ``owns_box(owner_principal, box_id)`` is an injected callable the
plane wires to its real ownership check. A hostile box that supplies its
own owner string must be rejected upstream — this module cannot
distinguish it. The obligation travels with this file because it drops
into ``worker.py`` verbatim, ahead of the endpoint wiring.

D45 encrypt-at-rest is an injected seam, not a cipher in this file:
``encrypt_at_rest(plaintext: bytes) -> (data_key_version, nonce,
ciphertext)`` and ``decrypt_at_rest(version, nonce, ciphertext) ->
plaintext``. The production D45 requirement is **AES-256-GCM** with a
fresh 12-octet nonce per encryption, the data key a Cloudflare Worker
secret per tenant plane (D-MT1, vend-lane parity — see the schema
contract section 2). The seam exists here because the private worker's
key material must never cross into the open repo; the module only pins
the *shape* — nonce per encryption, version discriminator, fail-closed
decrypt — and the plane's operator supplies the real cipher at deploy.
The module also never reads back plaintext: D46 write-only-after-set is
enforced by construction (the read path selects display columns only;
``decrypt_at_rest`` is provided for the send path's use, not this
module's).

D98 note: the SELECTs below name their columns explicitly — ``device,
status, last_page_at, created_at`` — so secrets can never leak onto the
read path by column-order drift; the ``_DISPLAY_COLUMNS`` constant is
the single source (feeding both the SELECT and the dict projection),
and the pin test asserts its exact column set — no secret column name
(``endpoint``, ``p256dh``, ``auth``, any ``*_nonce``) can join it
without tripping the suite.

D99 validation is all-400, loud, before any write; the ownership 404
comes *after* validation (a malformed request is the client's bug even
for a foreign box id, and reporting 400 first leaks nothing an
authenticated owner couldn't learn from the 404 path).

D102 serving rule: the plane serves the bytes of
``hosted/dashboard/sw.js`` (the repo file, ``SW_JS_REPO_PATH``) at
``/sw.js`` from the plane bundle, ``Content-Type: application/javascript``.
Per the #1476 downgrade of the wire contract, the byte-pin is a
*deploy-time* check, not a runtime one: ``sw_js_pin_sha256`` computes
the sha256 of bytes the operator embedded at deploy, and the deploy
script asserts it equals the repo file's hash. The module itself never
reads the repo file (droppable-verbatim constraint).
"""

from __future__ import annotations

import base64
import hashlib
import inspect
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# HTTP result shape
# ---------------------------------------------------------------------------


@dataclass
class HttpResult:
    """What a plane endpoint returns to the worker's response writer.

    JSON endpoints carry ``body`` (a dict); ``serve_sw_js`` carries
    ``raw`` bytes instead. ``content_type`` overrides the default
    ``application/json`` for the raw case.
    """

    status: int
    body: dict | None = None
    raw: bytes | None = None
    content_type: str | None = None
    headers: dict = field(default_factory=dict)


def _ok(status: int, body: dict) -> HttpResult:
    return HttpResult(status=status, body={"ok": True, **body})


def _err(status: int, message: str) -> HttpResult:
    return HttpResult(status=status, body={"ok": False, "error": message})


# ---------------------------------------------------------------------------
# D99 validators (pure compute; inlined, stdlib-only)
# ---------------------------------------------------------------------------

_DEVICE_RE = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
# Wire contract D99: the aid charset precedent from the #988 schema.
# Full-match with \Z (not $ — "$" would let a trailing newline through).


def validate_device(device) -> str:
    """D99: device label 1-64 chars of [A-Za-z0-9._-]. Raises ValueError."""
    if not isinstance(device, str) or not _DEVICE_RE.fullmatch(device):
        raise ValueError(
            "device must be 1-64 chars of [A-Za-z0-9._-]"
        )
    return device


def validate_endpoint_url(endpoint) -> str:
    """D99: https only, no userinfo (push_sender.py's send-attempt
    discipline, applied at write time). Raises ValueError."""
    if not isinstance(endpoint, str):
        raise ValueError("endpoint must be a string")
    if not endpoint.startswith("https://"):
        raise ValueError("endpoint must be an https:// URL")
    authority = endpoint[len("https://"):].split("/", 1)[0]
    if "@" in authority:
        raise ValueError("endpoint must not carry userinfo")
    if not authority:
        raise ValueError("endpoint has an empty authority")
    return endpoint


def _b64url_decode(text: str) -> bytes:
    """urlsafe base64 without padding (the push_crypto._b64url inverse)."""
    if not isinstance(text, str):
        raise ValueError("expected a base64url string")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except Exception as exc:
        raise ValueError("not valid base64url") from exc


# P-256 field constants, inlined from hosted/push_crypto.py (FIPS 186-4,
# section D.2.3) — the RFC 8291 section 7 curve check the wire contract's
# D99 names ("push_crypto already implements it — reuse it"; inlined here
# because the async port may not import the sync modules).
_PC_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_PC_A = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC
_PC_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B


def _pc_on_curve(x: int, y: int) -> bool:
    return (y * y - (x * x * x + _PC_A * x + _PC_B)) % _PC_P == 0


def validate_p256dh(b64: str) -> bytes:
    """D99: keys.p256dh — exactly 65 raw bytes, first byte 0x04, and the
    point MUST pass the RFC 8291 section 7 on-curve check. Raises
    ValueError."""
    raw = _b64url_decode(b64)
    if len(raw) != 65:
        raise ValueError("keys.p256dh must decode to exactly 65 bytes")
    if raw[0] != 0x04:
        raise ValueError("keys.p256dh must start with 0x04 (uncompressed point)")
    x = int.from_bytes(raw[1:33], "big")
    y = int.from_bytes(raw[33:65], "big")
    if not (0 <= x < _PC_P and 0 <= y < _PC_P):
        raise ValueError("keys.p256dh coordinates out of field range")
    if not _pc_on_curve(x, y):
        raise ValueError("keys.p256dh is not on the P-256 curve")
    return raw


def validate_auth(b64: str) -> bytes:
    """D99: keys.auth — exactly 16 raw bytes. Raises ValueError."""
    raw = _b64url_decode(b64)
    if len(raw) != 16:
        raise ValueError("keys.auth must decode to exactly 16 bytes")
    return raw


def validate_vapid_pubkey(b64: str) -> bytes:
    """D98-key delivery: the plane's VAPID public key, same serialization
    push_crypto uses for ``k`` — base64url of the 65-byte uncompressed
    point. Raises ValueError on malformed keys."""
    raw = _b64url_decode(b64)
    if len(raw) != 65 or raw[0] != 0x04:
        raise ValueError("vapid_pubkey must be base64url of a 65-byte uncompressed P-256 point")
    return raw


# ---------------------------------------------------------------------------
# Display column contract (D98 / D46)
# ---------------------------------------------------------------------------

# The ONLY columns the read path may return. Secrets (endpoint, p256dh,
# auth, nonces) are never selected — write-only-after-set (D46).
_DISPLAY_COLUMNS = "device, status, last_page_at, created_at"


async def _owns(owns_box, owner_principal: str, box_id: str) -> bool:
    # inspect.isawaitable covers coroutines, asyncio.Futures, and
    # __await__ objects — asyncio.iscoroutine alone would fail-OPEN on a
    # Future (bool(Future()) is True) and silently grant ownership. On
    # the D2 trust seam the failure direction must be fail-closed.
    owns = owns_box(owner_principal, box_id)
    if inspect.isawaitable(owns):
        owns = await owns
    return bool(owns)


def _now_iso(now=None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


async def get_vapid_pubkey(*, vapid_pubkey_b64url: str) -> HttpResult:
    """D98-key delivery: GET /v1/push/vapid-pubkey → 200 {ok, vapid_pubkey}.

    The browser needs this as ``applicationServerKey`` in
    ``PushManager.subscribe()``. A public key is public; the private half
    never leaves the plane (D3 custody). ``vapid_key_id`` rides the send
    path's D48c discriminator — the UI does not need it and does not
    receive it. The key is validated as a 65-byte ``0x04``-prefixed point
    but deliberately NOT on-curve checked (unlike ``validate_p256dh``):
    this is operator key material, the browser re-validates at
    ``PushManager.subscribe()``, and the deploy-time byte pin catches
    rotation.
    """
    try:
        validate_vapid_pubkey(vapid_pubkey_b64url)
    except ValueError as exc:
        # Operator misconfiguration, not a client bug — but a 500 with
        # the key in it would leak the key's shape; fail loud and generic.
        return _err(500, f"plane VAPID key misconfigured: {exc}")
    return _ok(200, {"vapid_pubkey": vapid_pubkey_b64url})


async def list_subscriptions(
    db, *, owner_principal: str, box_id: str, owns_box
) -> HttpResult:
    """GET /v1/push/subscriptions?box_id= → 200 {ok, subscriptions: [...]}.

    D98: display fields only — the SELECT names ``_DISPLAY_COLUMNS``
    explicitly. 404 for a box the owner does not own (an owner never
    learns whether a foreign box id exists). A ``dead_410`` row is
    returned so the UI can tell "subscription died" from "never
    subscribed" (D100's re-subscribe path).
    """
    if not await _owns(owns_box, owner_principal, box_id):
        return _err(404, "unknown box")
    rows = await db.prepare(
        f"SELECT {_DISPLAY_COLUMNS} FROM push_subscriptions "
        "WHERE owner_principal = ? AND box_id = ? ORDER BY created_at"
    ).bind(owner_principal, box_id).all()
    return _ok(200, {"subscriptions": [
        {
            "device": r["device"],
            "status": r["status"],
            "last_page_at": r["last_page_at"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]})


async def subscribe(
    db,
    *,
    owner_principal: str,
    box_id: str,
    device: str,
    endpoint: str,
    keys: dict,
    added_by: str,
    owns_box,
    encrypt_at_rest,
    data_key_version: str = "v1",
    vapid_key_id: str = "v1",
    now=None,
) -> HttpResult:
    """POST /v1/push/subscriptions → 201 created / 200 updated.

    D99: all validation is 400, loud, before any write — in this order:
    device, endpoint, keys shape, p256dh, auth. Anything else in the body
    is ignored, never echoed (the endpoint takes named params, so extra
    fields never reach it — the anti-echo rule is structural).

    D100: upsert on the D3 key ``(owner_principal, box_id, device)`` —
    one ``INSERT ... ON CONFLICT ... DO UPDATE`` statement: fresh
    endpoint, fresh key material, ``status`` reset to ``'live'``,
    ``added_by`` = the owner-key id that made the call (forensics, per
    the schema), ``last_page_at`` cleared (the resurrected row's fresh
    key material has never been paged), ``created_at`` refreshed. This
    is also the 410 recovery path: a dead row's device re-registers and
    comes back live. Returns 201 when the triple did not exist, 200 when
    it replaced an existing row. (Race note: two concurrent subscribes
    can both pre-read "not exists" and both return 201 — cosmetic only;
    the upsert itself is one atomic statement, so the final row is
    correct and last-write-wins.)

    D45: plaintext exists only for the duration of the write — both key
    blobs are encrypted through the injected ``encrypt_at_rest``
    seam (production: AES-256-GCM, fresh 12-octet nonce per encryption,
    Worker-secret data key) before the single upsert statement.

    The ownership 404 comes after validation per the module docstring.
    """
    # --- D99: validate everything before any write ---
    try:
        device = validate_device(device)
    except ValueError as exc:
        return _err(400, str(exc))
    try:
        endpoint = validate_endpoint_url(endpoint)
    except ValueError as exc:
        return _err(400, str(exc))
    if not isinstance(keys, dict):
        return _err(400, "keys must be an object with p256dh and auth")
    if "p256dh" not in keys or "auth" not in keys:
        return _err(400, "keys must carry p256dh and auth")
    try:
        p256dh_raw = validate_p256dh(keys["p256dh"])
    except ValueError as exc:
        return _err(400, str(exc))
    try:
        auth_raw = validate_auth(keys["auth"])
    except ValueError as exc:
        return _err(400, str(exc))

    if not await _owns(owns_box, owner_principal, box_id):
        return _err(404, "unknown box")

    # --- D45: encrypt under the operator's data key; nonce fresh per call ---
    version_p, nonce_p, ct_p = encrypt_at_rest(p256dh_raw)
    version_a, nonce_a, ct_a = encrypt_at_rest(auth_raw)
    # The seam returns its own version discriminator; the caller pins
    # data_key_version for the row, and a seam-version mismatch is the
    # operator's rotation bug — fail loud, never write mixed-version rows.
    if version_p != data_key_version or version_a != data_key_version:
        return _err(
            500,
            "encrypt_at_rest version mismatch with data_key_version",
        )

    existing = await db.prepare(
        "SELECT 1 AS one FROM push_subscriptions "
        "WHERE owner_principal = ? AND box_id = ? AND device = ?"
    ).bind(owner_principal, box_id, device).first()

    stamped = _now_iso(now)
    await db.prepare(
        "INSERT INTO push_subscriptions "
        "(owner_principal, box_id, device, endpoint, p256dh, p256dh_nonce, "
        "auth, auth_nonce, data_key_version, vapid_key_id, added_by, "
        "status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'live', ?) "
        "ON CONFLICT(owner_principal, box_id, device) DO UPDATE SET "
        "endpoint = excluded.endpoint, "
        "p256dh = excluded.p256dh, p256dh_nonce = excluded.p256dh_nonce, "
        "auth = excluded.auth, auth_nonce = excluded.auth_nonce, "
        "data_key_version = excluded.data_key_version, "
        "vapid_key_id = excluded.vapid_key_id, "
        "added_by = excluded.added_by, status = 'live', "
        "last_page_at = NULL, "  # the resurrected row's fresh key material
                                 # has never been paged; "last paged"
                                 # belongs to the retired keys
        "created_at = excluded.created_at"
    ).bind(
        owner_principal, box_id, device, endpoint,
        ct_p, nonce_p, ct_a, nonce_a,
        data_key_version, vapid_key_id, added_by, stamped,
    ).run()

    return _ok(201 if existing is None else 200, {"device": device})


async def unsubscribe(
    db, *, owner_principal: str, box_id: str, device: str, owns_box
) -> HttpResult:
    """DELETE /v1/push/subscriptions/{box_id}/{device} → 200 {ok, deleted}.

    D101: a real delete — no tombstone (the ``dead_410`` status already
    serves the "subscription died" distinction; an explicit unsubscribe
    is the owner saying "never subscribed this device"). 404 when no
    such row exists for this owner (no existence oracle for foreign
    rows — same rule as the list endpoint). The device charset is
    validated *before* the lookup (400 on a charset violation, never a
    lookup), so the path segment can never widen the query.
    """
    try:
        device = validate_device(device)
    except ValueError as exc:
        return _err(400, str(exc))
    if not await _owns(owns_box, owner_principal, box_id):
        return _err(404, "unknown box")
    meta = await db.prepare(
        "DELETE FROM push_subscriptions "
        "WHERE owner_principal = ? AND box_id = ? AND device = ?"
    ).bind(owner_principal, box_id, device).run()
    # The worker's D1 .run() reports meta.changes; the in-repo _AsyncD1
    # test shim reports it as a dict — accept both shapes.
    raw_meta = getattr(meta, "meta", meta)
    if isinstance(raw_meta, dict):
        changes = raw_meta.get("changes", 0)
    else:
        changes = getattr(raw_meta, "changes", 0)
    if not changes:
        return _err(404, "no such subscription")
    return _ok(200, {"deleted": True})


# ---------------------------------------------------------------------------
# D102: serve the reference service worker
# ---------------------------------------------------------------------------

SW_JS_REPO_PATH = "hosted/dashboard/sw.js"
SW_JS_CONTENT_TYPE = "application/javascript"


def sw_js_pin_sha256(sw_js_bytes: bytes) -> str:
    """D102 deploy-time pin: sha256 of the ``/sw.js`` bytes the plane
    serves. The plane's deploy script MUST assert this equals the sha256
    of the repo file at ``SW_JS_REPO_PATH`` — the #1476 byte-pin
    enforcement, moved to deploy time because the loop cannot verify
    what the private plane serves at runtime."""
    return hashlib.sha256(sw_js_bytes).hexdigest()


def serve_sw_js(*, sw_js_bytes: bytes) -> HttpResult:
    """GET /sw.js → 200, the reference service worker bytes.

    The worker is a pure renderer — it shows the signed "go look"
    payload's summary (``{aid, ttl_s, summary}``, D4) with
    ``requireInteraction: true`` and opens ``/`` on tap; it holds no
    keys and sees no credentials. The plane embeds the bytes at deploy
    (redeploy the plane to pick up dashboard changes); the module never
    reads the repo file (droppable-verbatim constraint).
    """
    if not isinstance(sw_js_bytes, bytes) or not sw_js_bytes:
        return _err(500, "service worker bytes not embedded at deploy")
    return HttpResult(
        status=200,
        raw=sw_js_bytes,
        content_type=SW_JS_CONTENT_TYPE,
        headers={"Cache-Control": "public, max-age=600"},
    )
