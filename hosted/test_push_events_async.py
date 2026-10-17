"""Tests for hosted/push_events_async.py (#1492 async port).

The async boundary (`enqueue_page`) is injected as a fake: these tests
pin the mapping half — fail-closed validation (mirroring the sync
`test_push_events.py` matrices), exact delegation arguments, disposition
passthrough, and `now` passthrough. They do not test the boundary
itself; that is the async-boundary port slice's suite.
"""

import asyncio
from collections import namedtuple
from datetime import datetime, timezone

import pytest

from hosted import push_events_async


FakeResult = namedtuple("FakeResult", ["disposition"])


def run(coro):
    return asyncio.run(coro)


class FakeBoundary:
    """Records enqueue_page calls; returns a canned disposition."""

    def __init__(self, disposition="queued"):
        self.calls = []
        self.disposition = disposition

    async def __call__(self, db, *, event_kind, owner_principal, box_id,
                       key_material, now=None):
        self.calls.append({
            "db": db,
            "event_kind": event_kind,
            "owner_principal": owner_principal,
            "box_id": box_id,
            "key_material": key_material,
            "now": now,
        })
        return FakeResult(self.disposition)


def filed(**kw):
    args = dict(db=object(), box_id="box-1", owner_principal="owner-1",
                aid="aid-1", enqueue_page=FakeBoundary())
    args.update(kw)
    return run(push_events_async.on_approval_filed(**args))


def revoked(**kw):
    args = dict(db=object(), box_id="box-1", owner_principal="owner-1",
                revoked_at="2026-10-05T17:00:00+00:00",
                enqueue_page=FakeBoundary())
    args.update(kw)
    return run(push_events_async.on_box_revoked(**args))


# --- delegation ----------------------------------------------------------

def test_approval_filed_delegates_exact_args():
    db = object()
    boundary = FakeBoundary()
    now = datetime(2026, 10, 17, 0, 30, tzinfo=timezone.utc)
    r = run(push_events_async.on_approval_filed(
        db, box_id="box-1", owner_principal="owner-1", aid="aid-1",
        enqueue_page=boundary, now=now))
    assert r.disposition == "queued"
    assert r.detail.disposition == "queued"
    assert len(boundary.calls) == 1
    call = boundary.calls[0]
    assert call["db"] is db
    assert call["event_kind"] == "approval_filed"
    assert call["owner_principal"] == "owner-1"
    assert call["box_id"] == "box-1"
    assert call["key_material"] == "aid-1"   # key = aid, per taxonomy §2
    assert call["now"] is now


def test_box_revoked_delegates_exact_args():
    db = object()
    boundary = FakeBoundary()
    r = run(push_events_async.on_box_revoked(
        db, box_id="box-1", owner_principal="owner-1",
        revoked_at="2026-10-05T17:00:00+00:00", enqueue_page=boundary))
    assert r.disposition == "queued"
    assert len(boundary.calls) == 1
    call = boundary.calls[0]
    assert call["db"] is db
    assert call["event_kind"] == "box_revoked"
    assert call["key_material"] == "2026-10-05T17:00:00+00:00"
    assert call["now"] is None   # boundary defaults it, like the sync port


def test_disposition_passthrough_verbatim():
    # The mapping never interprets the verdict — the D10/D57/D54 logic
    # lives at the boundary. Every boundary verdict must surface as-is.
    for disposition in ("queued", "duplicate", "suppressed_budget"):
        boundary = FakeBoundary(disposition=disposition)
        r = run(push_events_async.on_approval_filed(
            object(), box_id="box-1", owner_principal="owner-1",
            aid="aid-1", enqueue_page=boundary))
        assert r.disposition == disposition
        assert boundary.calls[0]["event_kind"] == "approval_filed"


# --- fail-closed validation (mirrors the sync matrices) -------------------

@pytest.mark.parametrize("bad_owner", ["", 123, None, True])
def test_approval_filed_rejects_bad_owner(bad_owner):
    boundary = FakeBoundary()
    with pytest.raises(ValueError):
        filed(owner_principal=bad_owner, enqueue_page=boundary)
    assert boundary.calls == []   # never reaches the boundary


@pytest.mark.parametrize("bad_box", ["", 123, None])
def test_approval_filed_rejects_bad_box(bad_box):
    boundary = FakeBoundary()
    with pytest.raises(ValueError):
        filed(box_id=bad_box, enqueue_page=boundary)
    assert boundary.calls == []


@pytest.mark.parametrize("bad_aid", ["", 123, None, "aid\x001"])
def test_approval_filed_rejects_bad_aid(bad_aid):
    # U+0000 in the aid would forge the event-key structure downstream.
    boundary = FakeBoundary()
    with pytest.raises(ValueError):
        filed(aid=bad_aid, enqueue_page=boundary)
    assert boundary.calls == []


@pytest.mark.parametrize("bad_owner", ["owner\x001", ""])
def test_box_revoked_rejects_bad_owner(bad_owner):
    boundary = FakeBoundary()
    with pytest.raises(ValueError):
        revoked(owner_principal=bad_owner, enqueue_page=boundary)
    assert boundary.calls == []


@pytest.mark.parametrize("bad_ts", [
    "not-a-timestamp",
    "2026-10-05",          # bare date: no time component, could repeat
    "1699999999",          # epoch int as string is not ISO-8601
    "2026-10-05T",         # T with no time
    "",
])
def test_box_revoked_rejects_non_timestamp(bad_ts):
    # Mirrors test_box_revoked_rejects_non_timestamp: the identity claim
    # ("a timestamp never repeats") is enforced — a constant or
    # date-only string would silently collapse distinct revocations
    # into one page.
    boundary = FakeBoundary()
    with pytest.raises(ValueError):
        revoked(revoked_at=bad_ts, enqueue_page=boundary)
    assert boundary.calls == []


def test_box_revoked_accepts_naive_as_utc():
    # The #988 convention: naive timestamps are assumed UTC, not
    # rejected — matches the sync validator exactly.
    boundary = FakeBoundary()
    r = revoked(revoked_at="2026-10-05T17:00:00", enqueue_page=boundary)
    assert r.disposition == "queued"
    assert boundary.calls[0]["key_material"] == "2026-10-05T17:00:00"


def test_non_callable_boundary_raises_loud():
    # A non-callable boundary must fail at the call site, never
    # silently drop the page.
    with pytest.raises(ValueError):
        filed(enqueue_page="not-callable")
    with pytest.raises(ValueError):
        revoked(enqueue_page=None)


def test_boundary_exception_propagates():
    # The mapping never swallows boundary failures: a page that did not
    # enqueue must not read as enqueued.
    async def boom(db, **kw):
        raise RuntimeError("D1 down")

    with pytest.raises(RuntimeError):
        filed(enqueue_page=boom)
