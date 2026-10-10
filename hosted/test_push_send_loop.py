"""Tests for hosted/push_send_loop.py (#967 sender loop — the D56 build slice).

The fixture DDL below is the #988 contract (§§1.1–1.4) plus the D57
partial unique index (``push_enqueue.PAGE_ONCE_INDEX_SQL`` — the shipped
statement, not a copy) plus an ``approvals`` fixture pinning the #872
record shape plus the ``summary`` column the loop's gate-2 reader needs.

Documented harness differences from production
(``docs/PRODUCTION_DEPLOY_CONTRACT.md``): subscription ``p256dh``/``auth``
are stored **plaintext** here — the plane decrypts the D45 ciphertexts
under its Worker-secret data key at the ``list_subscriptions`` seam, which
this harness implements as a plain SELECT; and ``transport`` is an
in-process fake (no sockets), while production speaks TLS to the push
service (covered by the sender's own default-transport tests).
"""

import base64
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import push_crypto, push_enqueue, push_payload, push_send_loop

NOW = datetime(2026, 10, 6, 15, 30, tzinfo=timezone.utc)

DDL_SUBSCRIPTIONS = """
CREATE TABLE IF NOT EXISTS push_subscriptions (
  owner_principal TEXT NOT NULL,
  box_id          TEXT NOT NULL,
  device          TEXT NOT NULL,
  endpoint        TEXT NOT NULL,
  p256dh          BLOB NOT NULL,
  auth            BLOB NOT NULL,
  p256dh_nonce    BLOB NOT NULL,
  auth_nonce      BLOB NOT NULL,
  data_key_version TEXT NOT NULL DEFAULT 'v1',
  vapid_key_id    TEXT NOT NULL DEFAULT 'v1',
  added_by        TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'live',
  created_at      TEXT NOT NULL,
  last_page_at    TEXT,
  PRIMARY KEY (owner_principal, box_id, device)
);
"""

DDL_APPROVALS = """
CREATE TABLE approvals (
  box_id       TEXT NOT NULL,
  aid          TEXT NOT NULL,
  owner_id     TEXT NOT NULL,
  summary      TEXT NOT NULL,
  detail       TEXT,
  status       TEXT NOT NULL,
  decision     TEXT,
  decision_seq INTEGER,
  decided_by   TEXT,
  decided_at   REAL,
  created_at   INTEGER NOT NULL,
  expires_at   INTEGER NOT NULL,
  PRIMARY KEY (box_id, aid)
);
"""

DDL_BUDGET_COUNTERS = """
CREATE TABLE IF NOT EXISTS push_budget_counters (
  scope_type   TEXT NOT NULL,
  scope_id     TEXT NOT NULL,
  window_start TEXT NOT NULL,
  count        INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (scope_type, scope_id, window_start)
);
"""

DDL_SEND_RESULTS = """
CREATE TABLE IF NOT EXISTS push_send_results (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  at              TEXT NOT NULL,
  owner_principal TEXT NOT NULL,
  box_id          TEXT NOT NULL,
  device          TEXT NOT NULL,
  event_kind      TEXT NOT NULL,
  event_key       TEXT NOT NULL,
  outcome         TEXT NOT NULL,
  http_status     INTEGER,
  latency_ms      REAL,
  sent_at         REAL,
  vapid_key_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_send_results_dedup
  ON push_send_results(box_id, event_kind, event_key);
CREATE INDEX IF NOT EXISTS idx_push_send_results_tenant
  ON push_send_results(owner_principal, at);
"""

DDL_DIGEST_STATE = """
CREATE TABLE IF NOT EXISTS push_digest_state (
  owner_principal TEXT NOT NULL,
  window_start    TEXT NOT NULL,
  count           INTEGER NOT NULL DEFAULT 0,
  enqueued_at     TEXT,
  PRIMARY KEY (owner_principal, window_start)
);
"""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in (DDL_SUBSCRIPTIONS, DDL_APPROVALS, DDL_BUDGET_COUNTERS,
                DDL_SEND_RESULTS, DDL_DIGEST_STATE):
        c.executescript(ddl)
    c.execute(push_enqueue.PAGE_ONCE_INDEX_SQL)
    yield c
    c.close()


@pytest.fixture()
def vapid():
    priv, pub = push_crypto.generate_keypair()
    return {"v1": (priv, pub)}


def _vapid_keys(vapid):
    calls = []

    def get(key_id):
        calls.append(key_id)
        return vapid[key_id]

    get.calls = calls
    return get


@pytest.fixture()
def owner():
    return "owner-test-1"


def seed_subscription(conn, owner, box, device, vapid_key_id="v1",
                      status="live"):
    priv, pub = push_crypto.generate_keypair()
    auth = secrets.token_bytes(16)
    conn.execute(
        "INSERT INTO push_subscriptions"
        " (owner_principal, box_id, device, endpoint, p256dh, auth,"
        "  p256dh_nonce, auth_nonce, data_key_version, vapid_key_id,"
        "  added_by, status, created_at, last_page_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'v1', ?, ?, ?, ?, NULL)",
        (owner, box, device, "https://push.example.com/wp/" + device,
         _b64url(pub), _b64url(auth), _b64url(secrets.token_bytes(12)),
         _b64url(secrets.token_bytes(12)), vapid_key_id, owner, status,
         NOW.isoformat()))
    conn.commit()


def make_list_subscriptions(conn):
    """Harness fanout: D3 for boxes, D78 (owner-wide) for the digest."""

    def list_subscriptions(owner_principal, box_id):
        if box_id is None:
            rows = conn.execute(
                "SELECT owner_principal, box_id, device, endpoint, p256dh,"
                " auth, vapid_key_id, status FROM push_subscriptions"
                " WHERE owner_principal = ? AND status = 'live'",
                (owner_principal,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT owner_principal, box_id, device, endpoint, p256dh,"
                " auth, vapid_key_id, status FROM push_subscriptions"
                " WHERE owner_principal = ? AND box_id = ?"
                " AND status = 'live'",
                (owner_principal, box_id)).fetchall()
        cols = ("owner_principal", "box_id", "device", "endpoint", "p256dh",
                "auth", "vapid_key_id", "status")
        return [dict(zip(cols, r)) for r in rows]

    return list_subscriptions


def seed_approval(conn, box, aid, owner, status="pending", decision=None,
                  summary="approve the deploy"):
    created = int((NOW - timedelta(minutes=5)).timestamp())
    conn.execute(
        "INSERT INTO approvals (box_id, aid, owner_id, summary, detail,"
        " status, decision, decision_seq, decided_by, decided_at,"
        " created_at, expires_at)"
        " VALUES (?, ?, ?, ?, NULL, ?, ?, NULL, NULL, NULL, ?, ?)",
        (box, aid, owner, summary, status, decision, created,
         created + 600))
    conn.commit()


def enqueue(conn, kind, owner, box, key_material, at=NOW):
    r = push_enqueue.enqueue_page(
        conn, event_kind=kind, owner_principal=owner, box_id=box,
        key_material=key_material, now=at)
    assert r.disposition == "queued", r
    return r


class FakePushService:
    """In-process stub for the transport seam: no sockets.

    ``script`` is a list of (status, headers) consumed in call order;
    anything beyond the script answers 201.
    """

    def __init__(self, script=None):
        self.script = list(script or [])
        self.calls = []

    def transport(self, *, host, port, path, headers, body):
        self.calls.append({"host": host, "port": port, "path": path,
                           "headers": dict(headers),
                           "body": body})
        if self.script:
            status, resp_headers = self.script.pop(0)
        else:
            status, resp_headers = 201, {}
        return status, resp_headers, b""


def make_tick(conn, owner, vapid, service=None, record_reader="auto"):
    service = service or FakePushService()
    if record_reader == "auto":
        record_reader = push_send_loop.make_record_reader(conn, NOW)

    def tick(now=NOW, **kw):
        return push_send_loop.send_loop(
            conn,
            list_subscriptions=make_list_subscriptions(conn),
            vapid_keys=_vapid_keys(vapid),
            vapid_subject="mailto:hosted@sparkvm.dev",
            record_reader=record_reader,
            transport=service.transport,
            now=now, **kw)

    tick.service = service
    return tick


def rows(conn, where="1=1"):
    return conn.execute(
        "SELECT id, owner_principal, box_id, device, event_kind, event_key,"
        " outcome, http_status, sent_at, vapid_key_id"
        " FROM push_send_results WHERE %s ORDER BY id" % where).fetchall()


def outcomes(conn):
    return [r[6] for r in rows(conn)]


def budget(conn, scope_type, scope_id, window):
    r = conn.execute(
        "SELECT count FROM push_budget_counters"
        " WHERE scope_type = ? AND scope_id = ? AND window_start = ?",
        (scope_type, scope_id, window)).fetchone()
    return r[0] if r else 0


WINDOW = "2026-10-06T15"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_two_devices_accepted_keeps_budget_and_stamps_last_page(conn, owner,
                                                                vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_subscription(conn, owner, "box-1", "laptop")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")

    summary = make_tick(conn, owner, vapid)()

    assert outcomes(conn) == ["accepted", "accepted"]
    devices = sorted(r[3] for r in rows(conn))
    assert devices == ["laptop", "phone"]
    # The queued work item is gone; the D10 reservation is KEPT (accepted
    # consumes the page's budget unit — counted once, not per device).
    assert "queued" not in outcomes(conn)
    assert budget(conn, "box", "box-1", WINDOW) == 1
    assert budget(conn, "owner", owner, WINDOW) == 1
    # Contract §1.1: last_page_at stamped by the send path.
    stamped = conn.execute(
        "SELECT device, last_page_at FROM push_subscriptions").fetchall()
    assert all(ts is not None for _, ts in stamped)
    assert summary.dispositions["accepted"] == 2
    assert summary.dispositions["completed"] == 1
    assert summary.attempts == 2
    # D48d: the per-send vapid_key_id rides the attempt row.
    assert {r[9] for r in rows(conn)} == {"v1"}


def test_claim_order_is_id_asc(conn, owner, vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    seed_approval(conn, "box-1", "aid-2", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1",
            at=NOW - timedelta(seconds=10))
    enqueue(conn, "approval_filed", owner, "box-1", "aid-2")

    make_tick(conn, owner, vapid)()

    keys = [r[5] for r in rows(conn) if r[6] == "accepted"]
    assert keys == ["box-1\x00aid-1", "box-1\x00aid-2"]


def test_max_claims_bounds_a_tick(conn, owner, vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    for i in ("aid-1", "aid-2", "aid-3"):
        seed_approval(conn, "box-1", i, owner)
        enqueue(conn, "approval_filed", owner, "box-1", i)

    summary = make_tick(conn, owner, vapid)(max_claims=1)

    assert summary.dispositions["completed"] == 1
    assert outcomes(conn).count("queued") == 2


# ---------------------------------------------------------------------------
# Retry / pacing / budget
# ---------------------------------------------------------------------------

def test_retry_then_accepted_holds_reservation(conn, owner, vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    tick = make_tick(conn, owner, vapid,
                     service=FakePushService(script=[(500, {})]))

    s1 = tick()
    assert outcomes(conn) == ["queued", "retry"]
    assert budget(conn, "box", "box-1", WINDOW) == 1  # held, not consumed
    assert s1.dispositions["retry"] == 1
    assert "completed" not in s1.dispositions

    # Too early: D82 pacing skips the not-due device, nothing is sent.
    s2 = tick(now=NOW + timedelta(seconds=1))
    assert s2.dispositions["retry_pending"] == 1
    assert len(tick.service.calls) == 1

    # Past backoff_s(1) = 2 s: the retry fires and lands accepted.
    s3 = tick(now=NOW + timedelta(seconds=3))
    assert outcomes(conn) == ["retry", "accepted"]
    assert budget(conn, "box", "box-1", WINDOW) == 1  # consumed exactly once
    assert s3.dispositions["completed"] == 1


def test_retry_hint_surfaces_for_the_scheduler(conn, owner, vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    tick = make_tick(conn, owner, vapid,
                     service=FakePushService(
                         script=[(429, {"retry-after": "120"})]))

    summary = tick()

    assert summary.retry_hint_s == 120
    assert summary.dispositions["retry"] == 1


def test_exhausted_retry_budget_dead_letters_without_sending(conn, owner,
                                                             vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    r = enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    key = "box-1\x00aid-1"
    # Six prior attempts already burned the D83 budget.
    for _ in range(6):
        conn.execute(
            "INSERT INTO push_send_results (at, owner_principal, box_id,"
            " device, event_kind, event_key, outcome, http_status,"
            " latency_ms, sent_at, vapid_key_id)"
            " VALUES (?, ?, 'box-1', 'phone', 'approval_filed', ?, 'retry',"
            " 500, 1.0, ?, 'v1')",
            (NOW.isoformat(), owner, key, NOW.timestamp()))
    conn.commit()
    tick = make_tick(conn, owner, vapid)

    summary = tick()

    assert tick.service.calls == []  # nothing sent on the 7th would-be try
    got = rows(conn)
    assert [x[6] for x in got] == ["retry"] * 6 + ["dead-letter"]
    dead = got[-1]
    # D56c per-device shape (real device label), NOT the D56e page-level
    # device='' shape: the per-device terminal scan must see this row,
    # or the next tick dead-letters the same device again.
    assert dead[3] == "phone"
    assert dead[7] is None  # never sent
    assert "queued" not in [x[6] for x in rows(conn)]
    assert budget(conn, "box", "box-1", WINDOW) == 0  # released
    assert summary.dispositions["dead-letter"] == 1


def test_exhausted_retry_budget_multi_device_no_duplicate_dead_letter(
        conn, owner, vapid):
    # Device A has burned its D83 budget; device B has one fresh retry
    # row that is not yet due (pacing holds it). Tick 1 dead-letters A
    # and parks B. Tick 2 must NOT dead-letter A again: the per-device
    # dead-letter row is visible to the terminal scan. (With the old
    # device='' page-level row, A looked pending again and every tick
    # added another dead-letter row.)
    seed_subscription(conn, owner, "box-1", "phone-a")
    seed_subscription(conn, owner, "box-1", "phone-b")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    key = "box-1\x00aid-1"
    for _ in range(6):
        conn.execute(
            "INSERT INTO push_send_results (at, owner_principal, box_id,"
            " device, event_kind, event_key, outcome, http_status,"
            " latency_ms, sent_at, vapid_key_id)"
            " VALUES (?, ?, 'box-1', 'phone-a', 'approval_filed', ?, 'retry',"
            " 500, 1.0, ?, 'v1')",
            (NOW.isoformat(), owner, key,
             (NOW - timedelta(hours=1)).timestamp()))
    conn.execute(
        "INSERT INTO push_send_results (at, owner_principal, box_id,"
        " device, event_kind, event_key, outcome, http_status,"
        " latency_ms, sent_at, vapid_key_id)"
        " VALUES (?, ?, 'box-1', 'phone-b', 'approval_filed', ?, 'retry',"
        " 500, 1.0, ?, 'v1')",
        (NOW.isoformat(), owner, key, NOW.timestamp()))
    conn.commit()
    tick = make_tick(conn, owner, vapid)

    tick()
    dead_a = [r for r in rows(conn)
              if r[6] == "dead-letter" and r[3] == "phone-a"]
    assert len(dead_a) == 1
    assert "queued" in outcomes(conn)  # B still pending, page not complete

    tick()
    dead_a = [r for r in rows(conn)
              if r[6] == "dead-letter" and r[3] == "phone-a"]
    assert len(dead_a) == 1  # no duplicate dead-letter for A
    assert [r for r in rows(conn) if r[6] == "dead-letter"
            and r[3] == ""] == []


# ---------------------------------------------------------------------------
# Tombstone / dead-letter
# ---------------------------------------------------------------------------

def test_tombstone_marks_subscription_dead_and_releases(conn, owner, vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    tick = make_tick(conn, owner, vapid,
                     service=FakePushService(script=[(410, {})]))

    summary = tick()

    assert outcomes(conn) == ["tombstone"]
    status = conn.execute(
        "SELECT status FROM push_subscriptions").fetchone()[0]
    assert status == "dead_410"
    assert budget(conn, "box", "box-1", WINDOW) == 0
    assert summary.dispositions["tombstone"] == 1
    assert summary.dispositions["completed"] == 1


def test_dead_letter_on_400_releases_and_is_operator_visible(conn, owner,
                                                             vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    tick = make_tick(conn, owner, vapid,
                     service=FakePushService(script=[(400, {})]))

    summary = tick()

    assert outcomes(conn) == ["dead-letter"]
    assert budget(conn, "owner", owner, WINDOW) == 0
    assert any("dead-letter" in a for a in summary.anomalies)


def test_mixed_outcomes_keep_budget_when_any_device_accepted(conn, owner,
                                                             vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_subscription(conn, owner, "box-1", "laptop")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    # phone: 410 (tombstone), laptop: 201 (accepted) — one buzz happened.
    tick = make_tick(conn, owner, vapid,
                     service=FakePushService(script=[(410, {}), (201, {})]))

    summary = tick()

    got = sorted((r[3], r[6]) for r in rows(conn))
    # One device tombstoned, the other accepted — order-independent.
    assert sorted(o for _, o in got) == ["accepted", "tombstone"]
    tombstoned = [d for d, o in got if o == "tombstone"][0]
    assert budget(conn, "box", "box-1", WINDOW) == 1  # kept: a page buzzed
    assert summary.dispositions["completed"] == 1
    # The tombstoned device is dead for future pages.
    dead = conn.execute(
        "SELECT status FROM push_subscriptions WHERE device = ?",
        (tombstoned,)).fetchone()[0]
    assert dead == "dead_410"


# ---------------------------------------------------------------------------
# Gate-2 (D56d, D80)
# ---------------------------------------------------------------------------

def test_unsubscribe_after_accept_keeps_the_budget(conn, owner, vapid):
    # Engineering B1: "accepted" is read from the DB across all devices
    # for the page, not from the live-scoped terminal dict — a device
    # that accepted and then unsubscribed before the last device
    # terminated must still count, or the D10 unit is released for a
    # page that buzzed.
    seed_subscription(conn, owner, "box-1", "phone")
    seed_subscription(conn, owner, "box-1", "laptop")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    # Tick 1: first device 201 (accepted), second 500 (retry). Order of
    # the two live devices is the seam's; read it back from the rows.
    tick1 = make_tick(conn, owner, vapid,
                      service=FakePushService(script=[(201, {}), (500, {})]))
    tick1()

    acc = conn.execute(
        "SELECT device FROM push_send_results"
        " WHERE event_kind = 'approval_filed' AND outcome = 'accepted'"
        ).fetchone()[0]
    retried = conn.execute(
        "SELECT device FROM push_send_results"
        " WHERE event_kind = 'approval_filed' AND outcome = 'retry'"
        ).fetchone()[0]
    assert {acc, retried} == {"phone", "laptop"}
    # The accepted device unsubscribes before the next tick.
    conn.execute(
        "DELETE FROM push_subscriptions"
        " WHERE owner_principal = ? AND box_id = ? AND device = ?",
        (owner, "box-1", acc))
    conn.commit()

    # Tick 2: the retried device is due again (backoff expired) and the
    # push service tombstones it. The page completes with the accepted
    # device no longer live.
    tick2 = make_tick(conn, owner, vapid,
                      service=FakePushService(script=[(410, {})]))
    summary = tick2(now=NOW + timedelta(hours=2))

    assert summary.dispositions["completed"] == 1
    # The page buzzed — the D10 unit is KEPT, not released for a device
    # the terminal dict no longer sees.
    assert budget(conn, "box", "box-1", WINDOW) == 1
    assert budget(conn, "owner", owner, WINDOW) == 1


def test_digest_same_device_label_across_boxes_is_per_box(conn, owner,
                                                         vapid):
    # QA B1: digest attempt/terminal rows are keyed per (box, device) —
    # the subscription's own box — not per device alone. Two boxes with
    # the same "phone" label must not share a retry budget or terminal
    # state: box-a's burned retries must not dead-letter box-b's phone.
    seed_subscription(conn, owner, "box-a", "phone")
    seed_subscription(conn, owner, "box-b", "phone")
    window = "2026-10-06T15"
    conn.execute(
        "INSERT INTO push_digest_state (owner_principal, window_start,"
        " count, enqueued_at) VALUES (?, ?, 3, ?)",
        (owner, window, NOW.isoformat()))
    enqueue(conn, "digest", owner, None, window)
    queued_key = conn.execute(
        "SELECT event_key FROM push_send_results"
        " WHERE outcome = 'queued'").fetchone()[0]
    # Burn box-a's phone retry budget directly, the way the loop writes
    # digest attempt rows (per-box, never box_id='').
    for _ in range(6):
        conn.execute(
            "INSERT INTO push_send_results (at, owner_principal, box_id,"
            " device, event_kind, event_key, outcome, http_status,"
            " latency_ms, sent_at, vapid_key_id)"
            " VALUES (?, ?, 'box-a', 'phone', 'digest', ?, 'retry', 500,"
            " 10.0, NULL, 'v1')",
            (NOW.isoformat(), owner, queued_key))
    conn.commit()

    tick = make_tick(conn, owner, vapid)
    summary = tick()

    # box-a's phone dead-letters on its exhausted budget; box-b's phone
    # is untouched by it — exactly one POST, to box-b's device.
    assert len(tick.service.calls) == 1
    got = sorted((r[2], r[3], r[6]) for r in rows(conn))
    assert ("box-a", "phone", "dead-letter") in got
    assert ("box-b", "phone", "accepted") in got
    assert [g for g in got if g[2] == "dead-letter"] == [
        ("box-a", "phone", "dead-letter")]
    assert budget(conn, "owner", owner, WINDOW) == 1  # kept: a page buzzed
    assert summary.dispositions["completed"] == 1


def test_gate2_terminal_decision_suppresses(conn, owner, vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner, status="approved",
                  decision="approve")
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    tick = make_tick(conn, owner, vapid)

    summary = tick()

    assert tick.service.calls == []  # nothing sent
    got = rows(conn)
    assert [r[6] for r in got] == ["suppressed_terminal"]
    audit = got[0]
    assert audit[3] == "" and audit[7] is None  # D56e shape
    # D61 audit key: the page key + U+0000 "superseded" — never collides
    # with the queued row under the D57 partial unique index.
    assert audit[5] == "box-1\x00aid-1\x00superseded"
    assert budget(conn, "box", "box-1", WINDOW) == 0  # released
    assert summary.dispositions["suppressed_terminal"] == 1


def test_gate2_missing_record_fails_safe(conn, owner, vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    # No approval row at all — the page cannot prove non-terminal (D80).
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    tick = make_tick(conn, owner, vapid)

    summary = tick()

    assert tick.service.calls == []
    assert [r[6] for r in rows(conn)] == ["suppressed_terminal"]
    assert budget(conn, "box", "box-1", WINDOW) == 0
    assert any("fail-safe" in a for a in summary.anomalies)


def test_gate2_vacuous_for_point_in_time_kinds(conn, owner, vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    enqueue(conn, "box_revoked", owner, "box-1", "2026-10-06T15:00:00Z")

    summary = make_tick(conn, owner, vapid)()

    assert summary.dispositions["accepted"] == 1
    assert summary.dispositions["completed"] == 1


# ---------------------------------------------------------------------------
# D78/D79/D81/D84
# ---------------------------------------------------------------------------

def test_digest_fans_out_owner_wide(conn, owner, vapid):
    seed_subscription(conn, owner, "box-a", "phone")
    seed_subscription(conn, owner, "box-b", "laptop")
    window = "2026-10-06T15"
    conn.execute(
        "INSERT INTO push_digest_state (owner_principal, window_start,"
        " count, enqueued_at) VALUES (?, ?, 3, ?)",
        (owner, window, NOW.isoformat()))
    conn.commit()
    enqueue(conn, "digest", owner, None, window)

    summary = make_tick(conn, owner, vapid)()

    got = sorted((r[3], r[6]) for r in rows(conn))
    # D78: the digest reaches every live subscription under (owner, *),
    # not just one box's devices.
    assert got == [("laptop", "accepted"), ("phone", "accepted")]
    assert summary.dispositions["completed"] == 1


def test_digest_missing_state_dead_letters(conn, owner, vapid):
    seed_subscription(conn, owner, "box-a", "phone")
    enqueue(conn, "digest", owner, None, "2026-10-06T15")
    tick = make_tick(conn, owner, vapid)

    summary = tick()

    assert tick.service.calls == []
    assert [r[6] for r in rows(conn)] == ["dead-letter"]
    assert budget(conn, "owner", owner, WINDOW) == 0
    assert summary.dispositions["dead-letter"] == 1


def test_no_live_subscriptions_parks_the_page(conn, owner, vapid):
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")

    summary = make_tick(conn, owner, vapid)()

    # D81: parked, not dropped — the row and its reservation stay.
    assert outcomes(conn) == ["queued"]
    assert budget(conn, "box", "box-1", WINDOW) == 1
    assert summary.dispositions["parked"] == 1


def test_parked_page_sends_once_subscribed(conn, owner, vapid):
    # D81's cold-start story: the parked page is the delivery buffer —
    # subscribing later must deliver it on the next tick.
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    tick = make_tick(conn, owner, vapid)

    assert tick().dispositions["parked"] == 1
    assert tick.service.calls == []

    seed_subscription(conn, owner, "box-1", "phone")
    summary = tick()
    assert tick.service.calls != []
    assert "queued" not in outcomes(conn)
    assert summary.dispositions["completed"] == 1


def test_plaintext_mapping_d79():
    record = {"ttl_seconds": 600, "summary": "s", "terminal": False}
    aid, ttl, text = push_send_loop._plaintext_for(
        "approval_filed", key_material="aid-9", owner_principal="o",
        record=record, digest_count=None)
    assert (aid, ttl, text) == ("aid-9", 600, "s")

    aid, ttl, text = push_send_loop._plaintext_for(
        "reminder", key_material="aid-9", owner_principal="o",
        record=record, digest_count=None)
    assert aid == "aid-9" and ttl == 600

    aid, ttl, text = push_send_loop._plaintext_for(
        "token_expiry_warning", key_material="tokhash", owner_principal="o",
        record=None, digest_count=None)
    assert aid == "token-expiry:tokhash" and ttl == 300 and text

    aid, ttl, text = push_send_loop._plaintext_for(
        "box_revoked", key_material="box-1", owner_principal="o",
        record=None, digest_count=None)
    assert aid == "box-revoked:box-1" and ttl == 3600 and text

    aid, ttl, text = push_send_loop._plaintext_for(
        "heartbeat_stale", key_material="epoch-7", owner_principal="o",
        record=None, digest_count=None)
    assert aid == "heartbeat-stale:epoch-7" and ttl == 3600 and text

    aid, ttl, text = push_send_loop._plaintext_for(
        "digest", key_material="2026-10-06T15", owner_principal="o",
        record=None, digest_count=3)
    assert aid == "digest:o:2026-10-06T15" and ttl == 3600
    assert "3 pages" in text
    # The digest body carries a count, never an aid (contract §1.4).
    assert "aid-9" not in text

    with pytest.raises(ValueError):
        push_send_loop._plaintext_for(
            "bogus", key_material="x", owner_principal="o", record=None,
            digest_count=None)


def test_serialize_plaintext_d84_is_canonical():
    payload = push_send_loop.serialize_plaintext(
        {"ttl_s": 600, "summary": "hi", "aid": "a1"})
    assert payload == b'{"aid":"a1","summary":"hi","ttl_s":600}'
    # Deterministic across ticks: the same page encrypts byte-identical
    # plaintext on retry.
    assert push_send_loop.serialize_plaintext(
        {"aid": "a1", "summary": "hi", "ttl_s": 600}) == payload


def test_aid_control_chars_scrubbed_at_choke_point():
    # The event key rejects only U+0000; an aid carrying ANSI escapes
    # must not reach the signed payload raw. build_push_payload scrubs
    # only the summary, so _plaintext_for is the aid's single choke
    # point. Plane-minted aids are unaffected (no-op).
    record = {"ttl_seconds": 600, "summary": "s", "terminal": False}
    aid, ttl, text = push_send_loop._plaintext_for(
        "approval_filed", key_material="aid-\x1b[2J",
        owner_principal="o", record=record, digest_count=None)
    assert "\x1b" not in aid and aid.startswith("aid-")
    assert (ttl, text) == (600, "s")

    aid, _, _ = push_send_loop._plaintext_for(
        "token_expiry_warning", key_material="tok\x07",
        owner_principal="o", record=None, digest_count=None)
    assert "\x07" not in aid and aid.startswith("token-expiry:tok")

    # Clean aids pass through byte-identical.
    aid, _, _ = push_send_loop._plaintext_for(
        "approval_filed", key_material="aid-9", owner_principal="o",
        record=record, digest_count=None)
    assert aid == "aid-9"


def test_plaintext_for_is_tick_stable():
    # D84's "a retried page encrypts byte-identical plaintext" rests on
    # _plaintext_for being pure in its tick-stable inputs (the
    # serializer's canonicity is pinned by
    # test_serialize_plaintext_d84_is_canonical).
    record = {"ttl_seconds": 600, "summary": "s", "terminal": False}
    kw = dict(key_material="aid-9", owner_principal="o", record=record,
              digest_count=None)
    first = push_send_loop._plaintext_for("approval_filed", **kw)
    second = push_send_loop._plaintext_for("approval_filed", **kw)
    assert first == second
    assert (push_send_loop.serialize_plaintext(
                push_payload.build_push_payload(*first))
            == push_send_loop.serialize_plaintext(
                push_payload.build_push_payload(*second)))


def test_vapid_key_id_is_per_subscription(conn, owner, vapid):
    priv2, pub2 = push_crypto.generate_keypair()
    vapid["v2"] = (priv2, pub2)
    seed_subscription(conn, owner, "box-1", "phone", vapid_key_id="v1")
    seed_subscription(conn, owner, "box-1", "laptop", vapid_key_id="v2")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")

    keys = _vapid_keys(vapid)
    push_send_loop.send_loop(
        conn,
        list_subscriptions=make_list_subscriptions(conn),
        vapid_keys=keys,
        vapid_subject="mailto:hosted@sparkvm.dev",
        record_reader=push_send_loop.make_record_reader(conn, NOW),
        transport=FakePushService().transport,
        now=NOW)

    # D48c: each subscription's sends sign under its own row's key id.
    assert sorted(keys.calls) == ["v1", "v2"]
    assert {r[9] for r in rows(conn)} == {"v1", "v2"}


def test_hostile_subscription_seam_fails_closed(conn, owner, vapid):
    # A buggy or compromised list_subscriptions seam returning another
    # owner's row (or another box's row) must not page this owner's
    # approval summary to a foreign device — fail closed, no send, the
    # work item survives for the next tick.
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")

    def evil_row(evil_owner, evil_box):
        return [{"owner_principal": evil_owner, "box_id": evil_box,
                 "device": "evil-phone",
                 "endpoint": "https://push.example.com/wp/evil",
                 "p256dh": "eA", "auth": "eQ", "vapid_key_id": "v1",
                 "status": "live"}]

    service = FakePushService()
    kw = dict(vapid_keys=_vapid_keys(vapid),
              vapid_subject="mailto:hosted@sparkvm.dev",
              record_reader=push_send_loop.make_record_reader(conn, NOW),
              transport=service.transport, now=NOW)

    # Foreign owner.
    summary = push_send_loop.send_loop(
        conn,
        list_subscriptions=lambda op, bid: evil_row("owner-evil", "box-1"),
        **kw)
    assert service.calls == []
    assert summary.dispositions["error"] == 1
    assert any("owner_principal mismatch" in a
               for a in summary.anomalies)

    # Right owner, foreign box.
    summary = push_send_loop.send_loop(
        conn,
        list_subscriptions=lambda op, bid: evil_row(owner, "box-9"),
        **kw)
    assert service.calls == []
    assert summary.dispositions["error"] == 1
    assert any("box_id mismatch" in a for a in summary.anomalies)

    # The work item survives both failures for the next tick.
    assert "queued" in outcomes(conn)


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

def test_tick_survives_one_bad_item(conn, owner, vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    # A corrupt row the boundary could never have written (bad kind):
    # loud, not fatal.
    conn.execute(
        "INSERT INTO push_send_results (at, owner_principal, box_id,"
        " device, event_kind, event_key, outcome)"
        " VALUES (?, ?, 'box-1', '', 'bogus-kind', 'x', 'queued')",
        (NOW.isoformat(), owner))
    conn.commit()

    summary = make_tick(conn, owner, vapid)()

    assert summary.dispositions["error"] == 1
    assert summary.dispositions["completed"] == 1  # the good page delivered
    assert any("error" in a for a in summary.anomalies)


def test_crash_between_last_attempt_and_delete_recovers(conn, owner, vapid):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    r = enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    key = "box-1\x00aid-1"
    # Simulate the crashed tick: the terminal attempt row landed, the
    # DELETE + commit never ran.
    conn.execute(
        "INSERT INTO push_send_results (at, owner_principal, box_id,"
        " device, event_kind, event_key, outcome, http_status, latency_ms,"
        " sent_at, vapid_key_id)"
        " VALUES (?, ?, 'box-1', 'phone', 'approval_filed', ?, 'accepted',"
        " 201, 5.0, ?, 'v1')",
        (NOW.isoformat(), owner, key, NOW.timestamp()))
    conn.commit()

    summary = make_tick(conn, owner, vapid)()

    # No second send: the device is already terminal for this page.
    assert summary.attempts == 0
    assert summary.dispositions["completed"] == 1
    assert "queued" not in outcomes(conn)
    assert budget(conn, "box", "box-1", WINDOW) == 1  # kept: it was accepted


# ---------------------------------------------------------------------------
# Non-vacuity (neutering): each neuter must fail its test
# ---------------------------------------------------------------------------

def test_neuter_no_delete_leaves_the_work_item(conn, owner, vapid,
                                               monkeypatch):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    monkeypatch.setattr(push_send_loop, "_delete_queued",
                        lambda conn, row_id: None)

    make_tick(conn, owner, vapid)()

    # Without the DELETE the work item survives its own terminal outcome.
    assert "queued" in outcomes(conn)


def test_neuter_no_gate2_sends_the_decided_page(conn, owner, vapid,
                                               monkeypatch):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner, status="approved",
                  decision="approve")
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    # D85: gate-2 is the ``_gate2_suppresses`` predicate — neutering the
    # kind set instead would neuter the record reader too and crash in
    # ``_plaintext_for`` rather than paging (the inconsistency this test
    # used to pin). The gate alone neutered away: the decided page pages,
    # so the neuter is caught.
    monkeypatch.setattr(push_send_loop, "_gate2_suppresses",
                        lambda record: False)
    tick = make_tick(conn, owner, vapid)

    tick()

    assert tick.service.calls != []


def test_neuter_no_completion_leaves_the_work_item(conn, owner, vapid,
                                                 monkeypatch):
    seed_subscription(conn, owner, "box-1", "phone")
    seed_approval(conn, "box-1", "aid-1", owner)
    enqueue(conn, "approval_filed", owner, "box-1", "aid-1")
    monkeypatch.setattr(push_send_loop, "_maybe_complete",
                        lambda *a: False)

    make_tick(conn, owner, vapid)()

    # Completion neutered away: the accepted page's work item survives
    # (``_maybe_complete`` never fires, so the DELETE never runs) — the
    # neuter is caught. (The assertion used to contradict this premise;
    # fixed per the 20261006-1659 repair.)
    assert "queued" in outcomes(conn)


# ---------------------------------------------------------------------------
# D87 — digest reset on delivery
# ---------------------------------------------------------------------------

def _seed_digest_state(conn, owner, window, count=3):
    conn.execute(
        "INSERT INTO push_digest_state (owner_principal, window_start,"
        " count, enqueued_at) VALUES (?, ?, ?, ?)",
        (owner, window, count, NOW.isoformat()))
    conn.commit()


def _digest_state_row(conn, owner, window):
    return conn.execute(
        "SELECT count, enqueued_at FROM push_digest_state"
        " WHERE owner_principal = ? AND window_start = ?",
        (owner, window)).fetchone()


def _burn_digest_retry_budget(conn, owner, device_box="box-a",
                              device="phone"):
    # Burn one device's retry budget directly, the way the loop writes
    # digest attempt rows (per-box, never box_id='') — the next tick
    # dead-letters that device without sending.
    queued_key = conn.execute(
        "SELECT event_key FROM push_send_results"
        " WHERE outcome = 'queued'").fetchone()[0]
    for _ in range(6):
        conn.execute(
            "INSERT INTO push_send_results (at, owner_principal, box_id,"
            " device, event_kind, event_key, outcome, http_status,"
            " latency_ms, sent_at, vapid_key_id)"
            " VALUES (?, ?, ?, ?, 'digest', ?, 'retry', 500,"
            " 10.0, NULL, 'v1')",
            (NOW.isoformat(), owner, device_box, device, queued_key))
    conn.commit()


def _coalesce_one(conn, owner, window):
    # The exact two statements the enqueue path runs when a page
    # coalesces into the digest (D54): INSERT OR IGNORE then count+1.
    conn.execute(
        "INSERT OR IGNORE INTO push_digest_state"
        " (owner_principal, window_start, count) VALUES (?, ?, 0)",
        (owner, window))
    conn.execute(
        "UPDATE push_digest_state SET count = count + 1"
        " WHERE owner_principal = ? AND window_start = ?",
        (owner, window))
    conn.commit()


def test_digest_completion_zeroes_state_count(conn, owner, vapid):
    # D87: the digest's delivery consumes the window's coalescing — the
    # count zeroes in the terminal transaction. The row (and its
    # enqueued_at fired-marker) survives so the sweep's never-refired
    # pin holds.
    seed_subscription(conn, owner, "box-a", "phone")
    window = "2026-10-06T15"
    _seed_digest_state(conn, owner, window)
    enqueue(conn, "digest", owner, None, window)

    summary = make_tick(conn, owner, vapid)()

    assert summary.dispositions["completed"] == 1
    row = _digest_state_row(conn, owner, window)
    assert row is not None and row[0] == 0  # reset, not deleted
    assert row[1] is not None  # enqueued_at fired-marker survives
    assert "queued" not in outcomes(conn)
    assert budget(conn, "owner", owner, WINDOW) == 1  # buzzed -> kept


def test_digest_dead_letter_completion_zeroes_state_count(conn, owner,
                                                          vapid):
    # D87 covers every terminal outcome, not just accepts: an exhausted
    # retry budget still consumes the window's coalescing.
    seed_subscription(conn, owner, "box-a", "phone")
    window = "2026-10-06T15"
    _seed_digest_state(conn, owner, window)
    enqueue(conn, "digest", owner, None, window)
    _burn_digest_retry_budget(conn, owner)

    summary = make_tick(conn, owner, vapid)()

    assert summary.dispositions["completed"] == 1
    assert summary.dispositions["dead-letter"] == 1
    row = _digest_state_row(conn, owner, window)
    assert row is not None and row[0] == 0
    assert row[1] is not None
    assert budget(conn, "owner", owner, WINDOW) == 0  # nothing buzzed


def test_digest_completion_is_idempotent_no_double_digest(conn, owner,
                                                          vapid):
    # D87 + D57 page-once: after a completed digest, a second tick sends
    # nothing and cannot resurrect the count.
    seed_subscription(conn, owner, "box-a", "phone")
    window = "2026-10-06T15"
    _seed_digest_state(conn, owner, window)
    enqueue(conn, "digest", owner, None, window)
    tick = make_tick(conn, owner, vapid)

    summary1 = tick()
    summary2 = tick(now=NOW + timedelta(minutes=5))

    assert summary1.dispositions["completed"] == 1
    assert len(tick.service.calls) == 1  # exactly one buzz, ever
    assert summary2.dispositions.get("completed", 0) == 0
    row = _digest_state_row(conn, owner, window)
    assert row is not None and row[0] == 0


def test_digest_post_fire_coalescing_does_not_refire(conn, owner, vapid):
    # The D67 accepted drift: coalescing that lands after the digest
    # fired increments the count from zero on the fired row, and the
    # sweep's pending scan (count>0 AND enqueued_at NULL) still skips
    # the window — the digest is never refired.
    from hosted import push_sweep
    seed_subscription(conn, owner, "box-a", "phone")
    window = "2026-10-06T15"
    _seed_digest_state(conn, owner, window)
    enqueue(conn, "digest", owner, None, window)
    tick = make_tick(conn, owner, vapid)
    assert tick().dispositions["completed"] == 1

    _coalesce_one(conn, owner, window)  # a late page coalesces post-fire

    row = _digest_state_row(conn, owner, window)
    assert row[0] == 1 and row[1] is not None  # drift, not a refire
    assert push_sweep.sweep_digests(conn, now=NOW) == {}
    assert len(tick.service.calls) == 1  # still exactly one buzz
