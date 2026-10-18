"""Tests for hosted/push_subscriptions_async.py (#1392 — async plane-port of
the GP2 subscription endpoints).

The async `_D1` shim below is worker-faithful: `prepare(sql)` →
`.bind(*params)` → `await .all()` / `await .first()` / `await .run()`,
rows as dicts, `.run()` reporting `meta` with `changes`. The sqlite3
connection runs in **autocommit** (`isolation_level=None`) so every
statement is individually durable — the worker's D1 has no interactive
transaction across awaits, and the port never calls a commit primitive
(there is none on the worker's `_D1`).

The fixture DDL is verbatim from docs/PUSH_SENDER_SCHEMA_CONTRACT.md
section 1.1 (the #988 contract).

The D45 encrypt-at-rest seam is injected: the tests use a test-only
AES-128-GCM cipher built on `push_crypto` (the production D45
requirement is AES-256-GCM under the operator's Worker-secret data key —
pinned by `test_production_cipher_requirement_pinned`, which asserts the
module docstring carries that requirement). The seam proves the module
encrypts before every write, stamps a fresh nonce per encryption, and
never writes mixed-version rows.

What this proves and what it does not: a green run proves the async
port implements the wire contract's D98-D102 behaviors (validation
taxonomy, upsert/delete semantics, display-only reads, sw.js serving)
against the #988 schema. The private `sparkvm-control` worker is the
conformance target — this module is the reference the plane's
implementation must satisfy, droppable into `worker.py` verbatim.
"""

import asyncio
import base64
import hashlib
import os
import sqlite3
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import push_subscriptions_async as psa
from hosted.push_crypto import (
    _aes_gcm_decrypt,
    _aes_gcm_encrypt,
    _b64url,
    generate_keypair,
)


# --- Worker-faithful async _D1 shim ----------------------------------------

class _RunResult:
    def __init__(self, changes, last_row_id=None):
        self.success = True
        self.meta = {"changes": changes, "last_row_id": last_row_id}


class _Bound:
    def __init__(self, conn, sql, params):
        self._conn = conn
        self._sql = sql
        self._params = params

    async def all(self):
        cur = self._conn.execute(self._sql, self._params)
        return [dict(r) for r in cur.fetchall()]

    async def first(self):
        cur = self._conn.execute(self._sql, self._params)
        row = cur.fetchone()
        return dict(row) if row is not None else None

    async def run(self):
        cur = self._conn.execute(self._sql, self._params)
        return _RunResult(cur.rowcount, cur.lastrowid)


class _Stmt:
    def __init__(self, conn, sql):
        self._conn = conn
        self._sql = sql

    def bind(self, *params):
        return _Bound(self._conn, self._sql, params)


class _AsyncD1:
    def __init__(self, conn):
        conn.row_factory = sqlite3.Row
        self._conn = conn

    def prepare(self, sql):
        return _Stmt(self._conn, sql)


# --- Fixture DDL: verbatim from docs/PUSH_SENDER_SCHEMA_CONTRACT.md §1.1 ---

DDL = """
CREATE TABLE IF NOT EXISTS push_subscriptions (
  owner_principal TEXT NOT NULL,
  box_id          TEXT NOT NULL,
  device          TEXT NOT NULL,
  endpoint        TEXT NOT NULL,
  p256dh          BLOB NOT NULL,
  p256dh_nonce    BLOB NOT NULL,
  auth            BLOB NOT NULL,
  auth_nonce      BLOB NOT NULL,
  data_key_version TEXT NOT NULL DEFAULT 'v1',
  vapid_key_id    TEXT NOT NULL DEFAULT 'v1',
  added_by        TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'live',
  created_at      TEXT NOT NULL,
  last_page_at    TEXT,
  PRIMARY KEY (owner_principal, box_id, device)
);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_fanout
  ON push_subscriptions(owner_principal, box_id, status);
"""


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.executescript(DDL)
    return _AsyncD1(conn)


# --- Test-only D45 seam -----------------------------------------------------

_TEST_DATA_KEY = os.urandom(16)  # test-only; production D45 is AES-256-GCM


def _test_encrypt(plaintext: bytes):
    nonce = os.urandom(12)
    return ("v1", nonce, _aes_gcm_encrypt(_TEST_DATA_KEY, nonce, plaintext))


def _test_decrypt(version, nonce, ciphertext: bytes) -> bytes:
    assert version == "v1"
    return _aes_gcm_decrypt(_TEST_DATA_KEY, nonce, ciphertext)


def _owns(owner, box):
    return True


def _owns_nobody(owner, box):
    return False


def _sub_kwargs(**over):
    priv, pub = generate_keypair()
    kw = dict(
        owner_principal="owner-1",
        box_id="box-a",
        device="pixel-9",
        endpoint="https://fcm.googleapis.com/fcm/send/abc123",
        keys={
            "p256dh": _b64url(pub),
            "auth": _b64url(os.urandom(16)),
        },
        added_by="owner-key-1",
        owns_box=_owns,
        encrypt_at_rest=_test_encrypt,
    )
    kw.update(over)
    return kw


def _run(coro):
    return asyncio.run(coro)


# --- D98-key delivery -------------------------------------------------------

def test_vapid_pubkey_roundtrip():
    _, pub = generate_keypair()
    key = _b64url(pub)
    r = _run(psa.get_vapid_pubkey(vapid_pubkey_b64url=key))
    assert r.status == 200
    assert r.body == {"ok": True, "vapid_pubkey": key}


def test_vapid_pubkey_malformed_is_operator_error():
    r = _run(psa.get_vapid_pubkey(vapid_pubkey_b64url="not-a-key"))
    assert r.status == 500
    assert r.body["ok"] is False


# --- D98 display-only reads -------------------------------------------------

def test_list_display_fields_only(db):
    _run(psa.subscribe(db, **_sub_kwargs()))
    r = _run(psa.list_subscriptions(
        db, owner_principal="owner-1", box_id="box-a", owns_box=_owns))
    assert r.status == 200
    subs = r.body["subscriptions"]
    assert len(subs) == 1
    assert set(subs[0].keys()) == {
        "device", "status", "last_page_at", "created_at"}
    assert subs[0]["device"] == "pixel-9"
    assert subs[0]["status"] == "live"
    assert subs[0]["last_page_at"] is None


def test_list_foreign_box_404(db):
    _run(psa.subscribe(db, **_sub_kwargs()))
    r = _run(psa.list_subscriptions(
        db, owner_principal="owner-1", box_id="box-a",
        owns_box=_owns_nobody))
    assert r.status == 404
    assert r.body["ok"] is False


def test_list_dead_410_row_is_returned(db):
    _run(psa.subscribe(db, **_sub_kwargs()))
    db._conn.execute(
        "UPDATE push_subscriptions SET status = 'dead_410' "
        "WHERE owner_principal = 'owner-1'")
    r = _run(psa.list_subscriptions(
        db, owner_principal="owner-1", box_id="box-a", owns_box=_owns))
    assert r.body["subscriptions"][0]["status"] == "dead_410"
    # The tombstoned row's secrets stay plane-side just the same.
    assert set(r.body["subscriptions"][0].keys()) == {
        "device", "status", "last_page_at", "created_at"}


# --- D99 validation (all 400, loud, before any write) ----------------------

def _count_rows(db):
    return db._conn.execute(
        "SELECT COUNT(*) FROM push_subscriptions").fetchone()[0]


@pytest.mark.parametrize("device", ["", "../evil", "a" * 65, "has space",
                                    "semi;colon", "unicode-✓"])
def test_subscribe_bad_device_400_no_write(db, device):
    r = _run(psa.subscribe(db, **_sub_kwargs(device=device)))
    assert r.status == 400
    assert _count_rows(db) == 0


@pytest.mark.parametrize("endpoint", [
    "http://fcm.googleapis.com/fcm/send/x",   # cleartext
    "https://user:pass@fcm.googleapis.com/",  # userinfo
    "https://",                               # empty authority
    12345,                                    # non-string
])
def test_subscribe_bad_endpoint_400_no_write(db, endpoint):
    r = _run(psa.subscribe(db, **_sub_kwargs(endpoint=endpoint)))
    assert r.status == 400
    assert _count_rows(db) == 0


def test_subscribe_missing_keys_400_no_write(db):
    r = _run(psa.subscribe(db, **_sub_kwargs(keys={"p256dh": "x"})))
    assert r.status == 400
    r = _run(psa.subscribe(db, **_sub_kwargs(keys="not-a-dict")))
    assert r.status == 400
    assert _count_rows(db) == 0


def _b64_nopad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@pytest.mark.parametrize("p256dh", [
    _b64_nopad(b"\x04" + b"\x01" * 63),          # 64 bytes, not 65
    _b64_nopad(b"\x05" + b"\x01" * 64),          # wrong prefix
    _b64_nopad(b"\x04" + b"\x01" + b"\x01"       # off-curve point (1, 1)
                + b"\x00" * 62),
    "!!!not-base64url!!!",
])
def test_subscribe_bad_p256dh_400_no_write(db, p256dh):
    kw = _sub_kwargs()
    kw["keys"] = {"p256dh": p256dh, "auth": _b64url(os.urandom(16))}
    r = _run(psa.subscribe(db, **kw))
    assert r.status == 400
    assert _count_rows(db) == 0


@pytest.mark.parametrize("auth", [
    _b64_nopad(os.urandom(15)),
    _b64_nopad(os.urandom(17)),
    "!!!not-base64url!!!",
])
def test_subscribe_bad_auth_400_no_write(db, auth):
    kw = _sub_kwargs()
    _, pub = generate_keypair()
    kw["keys"] = {"p256dh": _b64url(pub), "auth": auth}
    r = _run(psa.subscribe(db, **kw))
    assert r.status == 400
    assert _count_rows(db) == 0


def test_subscribe_extra_key_fields_not_echoed(db):
    kw = _sub_kwargs()
    kw["keys"] = {**kw["keys"], "admin": True, "note": "<script>"}
    r = _run(psa.subscribe(db, **kw))
    assert r.status == 201
    assert set(r.body.keys()) == {"ok", "device"}


def test_subscribe_foreign_box_404_no_write(db):
    r = _run(psa.subscribe(db, **_sub_kwargs(owns_box=_owns_nobody)))
    assert r.status == 404
    assert _count_rows(db) == 0


# --- D100 upsert ------------------------------------------------------------

def test_subscribe_201_then_200_upsert_replaces(db):
    kw = _sub_kwargs()
    r1 = _run(psa.subscribe(db, **kw))
    assert r1.status == 201

    kw2 = _sub_kwargs(endpoint="https://fcm.googleapis.com/fcm/send/NEW",
                      added_by="owner-key-2")
    r2 = _run(psa.subscribe(db, **kw2))
    assert r2.status == 200
    assert _count_rows(db) == 1

    row = db._conn.execute(
        "SELECT endpoint, added_by, status, created_at FROM "
        "push_subscriptions WHERE device = 'pixel-9'").fetchone()
    assert row[0] == "https://fcm.googleapis.com/fcm/send/NEW"
    assert row[1] == "owner-key-2"
    assert row[2] == "live"


def test_subscribe_resurrects_dead_410(db):
    _run(psa.subscribe(db, **_sub_kwargs()))
    db._conn.execute(
        "UPDATE push_subscriptions SET status = 'dead_410' "
        "WHERE owner_principal = 'owner-1'")
    r = _run(psa.subscribe(db, **_sub_kwargs()))
    assert r.status == 200  # the 410 recovery path is an upsert, not an error
    status = db._conn.execute(
        "SELECT status FROM push_subscriptions").fetchone()[0]
    assert status == "live"


def test_subscribe_stamps_created_at(db):
    fixed = datetime(2026, 10, 18, 6, 5, tzinfo=timezone.utc)
    _run(psa.subscribe(db, **_sub_kwargs(now=fixed)))
    created = db._conn.execute(
        "SELECT created_at FROM push_subscriptions").fetchone()[0]
    assert created == "2026-10-18T06:05:00Z"


# --- D101 real delete --------------------------------------------------------

def test_unsubscribe_real_delete_then_404(db):
    _run(psa.subscribe(db, **_sub_kwargs()))
    r = _run(psa.unsubscribe(
        db, owner_principal="owner-1", box_id="box-a",
        device="pixel-9", owns_box=_owns))
    assert r.status == 200
    assert r.body == {"ok": True, "deleted": True}
    assert _count_rows(db) == 0
    r2 = _run(psa.unsubscribe(
        db, owner_principal="owner-1", box_id="box-a",
        device="pixel-9", owns_box=_owns))
    assert r2.status == 404


def test_unsubscribe_validates_device_before_lookup(db):
    calls = []

    def spy_owns(owner, box):
        calls.append((owner, box))
        return True

    r = _run(psa.unsubscribe(
        db, owner_principal="owner-1", box_id="box-a",
        device="../evil", owns_box=spy_owns))
    assert r.status == 400
    assert calls == []  # charset checked before any ownership lookup


def test_unsubscribe_foreign_box_404(db):
    _run(psa.subscribe(db, **_sub_kwargs()))
    r = _run(psa.unsubscribe(
        db, owner_principal="owner-1", box_id="box-a",
        device="pixel-9", owns_box=_owns_nobody))
    assert r.status == 404
    assert _count_rows(db) == 1  # the foreign box's row is untouched


# --- D45 encrypt-at-rest seam ------------------------------------------------

def test_d45_fresh_nonce_per_encryption_and_roundtrip(db):
    _run(psa.subscribe(db, **_sub_kwargs()))
    _run(psa.subscribe(db, **_sub_kwargs(device="pixel-9b")))
    rows = db._conn.execute(
        "SELECT p256dh_nonce, auth_nonce, p256dh, auth, data_key_version "
        "FROM push_subscriptions ORDER BY device").fetchall()
    assert len(rows) == 2
    nonces = [rows[0][0], rows[0][1], rows[1][0], rows[1][1]]
    assert len({bytes(n) for n in nonces}) == 4  # fresh 12-octet nonce each
    assert all(len(bytes(n)) == 12 for n in nonces)
    for row in rows:
        p = _test_decrypt(row[4], bytes(row[0]), bytes(row[2]))
        a = _test_decrypt(row[4], bytes(row[1]), bytes(row[3]))
        assert len(p) == 65 and p[0] == 0x04
        assert len(a) == 16


def test_d45_version_mismatch_fails_closed_no_write(db):
    def wrong_version(plaintext: bytes):
        nonce = os.urandom(12)
        return ("v2", nonce,
                _aes_gcm_encrypt(_TEST_DATA_KEY, nonce, plaintext))

    r = _run(psa.subscribe(db, **_sub_kwargs(encrypt_at_rest=wrong_version)))
    assert r.status == 500
    assert _count_rows(db) == 0


def test_production_cipher_requirement_pinned():
    # The plane holds the real data key; this module only pins the seam's
    # production requirement in its contract docstring. A silent
    # downgrade of that requirement must trip a test.
    assert "AES-256-GCM" in psa.__doc__
    assert "fresh" in psa.__doc__ and "nonce" in psa.__doc__


# --- D102 service worker -----------------------------------------------------

def test_sw_js_served_with_content_type():
    sw = open(os.path.join(
        os.path.dirname(__file__), "dashboard", "sw.js"), "rb").read()
    r = psa.serve_sw_js(sw_js_bytes=sw)
    assert r.status == 200
    assert r.raw == sw
    assert r.content_type == "application/javascript"
    assert r.headers["Cache-Control"] == "public, max-age=3600"


def test_sw_js_empty_bytes_is_deploy_error():
    r = psa.serve_sw_js(sw_js_bytes=b"")
    assert r.status == 500


def test_sw_js_pin_matches_repo_file():
    sw = open(os.path.join(
        os.path.dirname(__file__), "dashboard", "sw.js"), "rb").read()
    assert psa.sw_js_pin_sha256(sw) == hashlib.sha256(sw).hexdigest()
    assert psa.SW_JS_REPO_PATH == "hosted/dashboard/sw.js"


def test_http_result_json_shape(db):
    r = _run(psa.subscribe(db, **_sub_kwargs()))
    assert r.body["ok"] is True and r.status == 201
    e = _run(psa.unsubscribe(
        db, owner_principal="owner-1", box_id="box-a",
        device="nope", owns_box=_owns))
    assert e.body["ok"] is False and e.status == 404
