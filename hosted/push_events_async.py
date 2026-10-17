"""Async plane-port of the endpoint-driven push mappings (#1492).

`hosted/push_events.py` ships the sync paging policy (one mapping per
taxonomy §2 event, #969/#1062). Four of the six mappings are sweep-driven
(reminders, digests, heartbeat-stale, token-expiry-warning — the D9 sweep
drives them). The other two — `on_approval_filed` and `on_box_revoked` —
are endpoint-driven: they must be called from the plane worker's HTTP
request path (the #952 filing endpoint after the #872 record write; the
revoke endpoint after stamping `revoked_at`). They have no caller anywhere
today (#1492): the "approval filed" page — the core buzz of the #849
phone-approval loop — never fires, and neither does the revocation page.

This module is their async port. The plane worker's D1 is async-only
(F-PP-2: `await db.prepare(...).bind(...).run()` via the `_D1` wrapper;
no synchronous D1 exists), so the sync `conn.execute` modules cannot be
called from the worker. Like `hosted/push_sweep_async.py`, this file is
droppable into `worker.py` verbatim: stdlib-only, no imports from the
sync modules, pure-compute validators inlined with source citations (the
ed25519 precedent), and the async boundary injected.

The async `enqueue_page` contract (provided by the async-boundary port
slice — the async counterpart of `hosted/push_enqueue.py::enqueue_page`):

    await enqueue_page(db, *, event_kind, owner_principal, box_id,
                       key_material, now=None) -> result with .disposition

`db` is the worker's async `_D1`; `now` is an aware UTC datetime or None
(the boundary defaults it, exactly like the sync version). The result's
`.disposition` is the boundary's verdict string (`queued`, `duplicate`,
`suppressed_budget`, ...). This module does not interpret it beyond
passing it through — the D10 budget, D57 page-once dedup, and D54 digest
coalescing all live at the boundary by construction (O6).

Caller obligations (from the sync mappings, restated — the obligations
survive the port because the call sites are what obey them):

- `on_approval_filed`: the #952 filing endpoint must never emit a filing
  event for an aid whose #872 record is already terminal
  (approved/denied/expired). There is no gate-1 re-read on this path by
  design — filing *is* the plane's own write — so the terminal check is
  upstream of the write, and a terminal aid filed here would page
  spuriously. (Sync docstring: `push_events.on_approval_filed`.)
- `on_box_revoked`: D65 — never call this for the pre-#844
  keyless-grandfathered path. Only real revocation events page.

STACKING NOTE: the async `enqueue_page` boundary does not exist yet —
it is the async-boundary port slice's deliverable. This module pins the
mapping half (#1492's in-repo slice); the plane wires the two together
when the boundary lands. Do not merge a worker vendoring before the
boundary exists.
"""

from __future__ import annotations

from collections import namedtuple
from datetime import datetime, timezone

MapResult = namedtuple("MapResult", ["disposition", "detail"])
# disposition is the boundary's verdict string, passed through verbatim;
# detail carries the boundary's result object (or None).


# --- inlined validators (source: hosted/push_events.py) -------------------
# The ed25519 precedent: pure-compute helpers are inlined with source
# citations so this file stays droppable into worker.py verbatim (no
# sibling import). Any behavioral change to the sync validators must be
# mirrored here, and vice versa.

def _require_key_material(name, value):
    # ← push_events._require_key_material: non-empty str, no U+0000 (a
    # U+0000 in owner_principal/box_id would forge the event-key
    # structure downstream).
    if not isinstance(value, str) or not value:
        raise ValueError("%s must be a non-empty str" % name)
    if "\x00" in value:
        raise ValueError("%s must not contain U+0000" % name)


def _require_owner_box(owner_principal, box_id):
    # ← push_events._require_owner_box: D2 restated — the caller resolves
    # these from the enrollment registry, never from a box assertion;
    # the module fail-closes on anything else.
    _require_key_material("owner_principal", owner_principal)
    _require_key_material("box_id", box_id)


def _require_iso_timestamp(name, value):
    # ← push_events._require_iso_timestamp: fail-closed ISO-8601 with a
    # real time component. `datetime.fromisoformat` alone accepts
    # date-only strings ('2026-10-05' → midnight): a date carries no
    # time, so a value whose timing matters must name its time
    # explicitly. Naive values are assumed UTC (the #988 convention).
    _require_key_material(name, value)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("%s must be ISO-8601: %r" % (name, value))
    if "T" not in value and " " not in value:
        raise ValueError(
            "%s must carry a time component, not a bare date: %r"
            % (name, value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _require_enqueue_page(enqueue_page):
    # The async boundary is injected (not imported) so this module never
    # depends on the boundary port's landing order. Fail-loud on a
    # non-callable: silently dropping the page would be worse than
    # raising at the call site.
    if not callable(enqueue_page):
        raise ValueError("enqueue_page must be callable")


# --- endpoint-driven mappings ----------------------------------------------

async def on_approval_filed(db, *, box_id, owner_principal, aid,
                            enqueue_page, now=None):
    """Map the approval-filed event to one page (async port, #1492).

    Async counterpart of `push_events.on_approval_filed`. Called from the
    plane worker's #952 filing endpoint after the #872 record write.

    Caller obligation (no gate-1 re-read by design): the filing endpoint
    must never call this for an aid whose #872 record is already
    terminal — the check is upstream of the write. Page-once per
    (box_id, aid) comes from the boundary's dedup.
    """
    _require_owner_box(owner_principal, box_id)
    _require_key_material("aid", aid)
    _require_enqueue_page(enqueue_page)
    r = await enqueue_page(
        db, event_kind="approval_filed", owner_principal=owner_principal,
        box_id=box_id, key_material=aid, now=now)
    return MapResult(r.disposition, r)


async def on_box_revoked(db, *, box_id, owner_principal, revoked_at,
                        enqueue_page, now=None):
    """Map the box-revoked event to one page (async port, #1492).

    Async counterpart of `push_events.on_box_revoked`. Called from the
    plane worker's revoke endpoint after stamping `revoked_at`.

    `revoked_at` is the revocation event's identity — a timestamp never
    repeats, so this is identity, not collision-prone dedup. It must be
    a full ISO-8601 timestamp (a bare date could repeat across same-day
    revocations and silently collapse them into one page).

    Caller obligation (D65): never call this for the keyless-
    grandfathered path — only real revocation events page.
    """
    _require_owner_box(owner_principal, box_id)
    _require_iso_timestamp("revoked_at", revoked_at)
    _require_enqueue_page(enqueue_page)
    r = await enqueue_page(
        db, event_kind="box_revoked", owner_principal=owner_principal,
        box_id=box_id, key_material=revoked_at, now=now)
    return MapResult(r.disposition, r)
