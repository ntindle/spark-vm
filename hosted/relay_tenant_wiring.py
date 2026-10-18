#!/usr/bin/env python3
"""R3 — relay-liveness tenant-status producer wiring (issue #1416).

Wires the R2b instrument (``hosted/relay_path_state.py`` — the §5
producer contract ``relay_path_state(vm_id) -> ok | degraded | down``,
with the §3 sub-code ``relay | cert | box-leg`` on ``down`` readings
only) into the tenant-status layer (``hosted/tenant_status.py``):
transition rule 6 (relay/cert suspension), the live-entry AND-combine's
post-``live`` maintenance, and the latch semantics.

This module is tenant-layer code: it owns anchor selection (per-tenant
knowledge the instrument cannot have — D-RL2-6) and the event protocol
that answers the producer-disagreement question the tenant layer pins
in code (``relay-recovered`` handler: a stale ``relay_reachable=False``
at recovery is the R3 wiring's question, #1416, not a demotion
trigger). It never invents status codes — every emission routes to the
existing 13-code vocabulary via ``tenant_status.apply_event``.

The wiring protocol, per tick, for the live-anchor box:

- ``down`` reading (sub-code ``relay`` | ``cert`` | ``box-leg``):
  emit ``relay-down``. On a post-``live`` arc (``live``,
  ``waiting-on-approval``, ``approved``) the tenant layer enters the
  rule-6 suspension with the sub-code in ``detail`` (D-RL34-4) and
  latches the arc code; a ``down`` reading with no sub-code is a
  broken-producer signal — rule 6 still fires on the down evidence,
  but the wiring passes no detail, so the tenant layer's generic
  ``relay-down`` default marks the entry unclassified (the wiring
  never invents a classification) and the anomaly is noted loud; in latch-holding states (``stuck``,
  ``maintenance``, already ``connection-unreachable``) — and on every
  other code — the event is the boolean flip only (F-RL34-3: the wiring
  never emits ``relay-failure``; it raises ``TransitionError`` in
  latch-holding states). ``degraded`` readings are never applied to
  arcs — operator surface only (F-RL34-5).
- ``ok`` reading: if a suspension is active, emit the ordered pair
  ``relay-reachable`` (boolean restore) BEFORE ``relay-recovered``
  (suspension exit), in that order, from this box's single ordered
  emitter (D-RL34-3). If no suspension is active but
  ``relay_reachable`` is stale-``False``, emit ``relay-reachable``
  alone (the resync rule — a stale ``False`` would poison
  ``_re_evaluate_latch_on_exit``'s exit-time backstop).
- ``degraded`` reading: no events. A suspect reading is not evidence
  of reachability (no ``relay-reachable``) and not evidence of a
  defect (no rule-6 entry).

Delivery semantics (D-RL34-3, one resolution per pair, no dangling
cases):

(a) Single ordered emitter per box, atomic at the persistence layer:
    the cadence loop — not yet built in production, see issue #1711 —
    must run at most one tick per box at a time (single-driver
    assumption — documented, not locked), and the tick's
    apply phase runs the pair through the store's exclusive lock
    (``TenantStore._mutate``), so no concurrent endpoint or producer
    write can interleave between ``relay-reachable`` and
    ``relay-recovered``. There is no persisted intermediate: ``_emit``
    mutates the record in memory and ``_save_record`` persists once
    after the pair, so a crash mid-pair loses the whole tick — and the
    next ``ok`` reading re-drives the same pair. Convergence comes from
    that stateless re-drive, not from inter-event ordering at the
    persistence layer: the re-drive is safe because ``relay-reachable``
    is idempotent (a bare boolean set — re-emitting it never raises)
    and ``relay-recovered`` is guarded to fire only while a suspension
    is actually active. The persisted post-crash states are therefore
    only pre-tick (whole tick lost, re-driven next ``ok``) or
    post-pair — "suspension exited with a stale False" is unreachable,
    and within the pair the boolean restore still runs FIRST.
(b) Idempotency: the wiring never blind-retries ``relay-recovered`` —
    ``plan_events`` emits it only when ``arc.code ==
    "connection-unreachable"`` with a latch present. After a
    successful recovery the arc no longer satisfies the guard, so a
    later ``ok`` reading plans nothing; a manual re-emit past the
    guard would raise ``TransitionError`` in the tenant layer (the
    guard exists so the wiring never asks for that).
(c) Lost-event reconciliation: the re-drive rule is stateless — every
    tick that observes ``ok`` while a suspension is active re-emits
    the pair, so a lost ``relay-recovered`` cannot wedge
    ``connection-unreachable`` indefinitely. The resync rule above is
    the ``relay_reachable`` counterpart: an ``ok`` reading with a
    stale ``False`` and no suspension restores the boolean, keeping
    ``_re_evaluate_latch_on_exit``'s backstop honest.

The producer-disagreement answer (F-RL34-4): the tenant layer does not
re-check ``relay_reachable`` at ``relay-recovered`` — the instrument is
authoritative for its own layer. Coherence comes from the wiring: at
recovery time the boolean is always fresh-producer state (restored by
the pair's first event, or by the resync rule), never a stale input
the tenant layer must second-guess.

This module never probes: probing is a production cadence driver's
job — not yet built, see issue #1711
(``relay_path_state.maybe_probe`` with caller-supplied bundles —
D-RL2-3, bundles never persisted). The wiring only *reads*
``relay_path_state`` and emits tenant-status events.

Stdlib only — runs on the control plane like the rest of the lane.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from hosted import relay_path_state as rps
from hosted import tenant_status as ts

# ---------------------------------------------------------------------------
# Tenant-layer predicates (R2b names these "the tenant layer's answer").

# Arc codes that imply the box reached ``live`` in its current session.
# (Every one is reachable only via a post-live transition: the rule-6/8
# entries and the stuck entry all require a post-live code, and the
# approval-arc end-states descend from waiting-on-approval/live.)
_POST_LIVE_IMPLIED = frozenset(
    {
        "live",
        "waiting-on-approval",
        "approved",
        "connection-unreachable",
        "stuck",
        "maintenance",
        "human-denied",
        "human-drop-off",
        "no-gated-action",
        "policy-misfire",
    }
)

# The anchor candidacy set: arcs from which a relay ``down`` reading may
# enter the rule-6 suspension — the post-live entry codes plus the
# latch-holding states (a suspended/stuck/in-maintenance box is still the
# tenant's live box; its recovery must keep being driven). ``box-unhealthy``
# is excluded either way: the relay can never suspend it (boolean flips
# only), so anchor choice among unhealthy arcs is behaviorally moot, and a
# dead arc must not hold the anchor while another box carries the live arc.
_ANCHOR_CODES = frozenset(
    {
        "live",
        "waiting-on-approval",
        "approved",
        "connection-unreachable",
        "stuck",
        "maintenance",
    }
)

# Rule-6 suspension entry codes — mirrors
# ``tenant_status._LIVENESS_DEMOTE_CODES`` (the codes from which
# ``_suspend_on_relay_down`` enters the suspension). Kept as a local
# name so the wiring's decision table reads without reaching into the
# tenant module's privates; ``test_wiring_constants_track_tenant_layer``
# pins the equality.
_RULE6_ENTRY_CODES = frozenset({"live", "waiting-on-approval", "approved"})


def has_post_live_arc(arc: ts.BoxArc) -> bool:
    """The tenant layer's post-``live`` answer (R2b ``maybe_probe`` input).

    True when the arc reached ``live`` in its current session — the
    prober's job starts at ``live``. ``box-unhealthy`` is ambiguous
    (rule 1(b) stack-deploy is pre-``live``; rule 2/4 smoke failures are
    post-``live``); the stack-deploy event always sets detail
    ``"stack-deploy:<stage>"``, so that prefix disambiguates by
    contract. Every other code is decided by the transition table.
    """
    if arc.code in _POST_LIVE_IMPLIED:
        return True
    if arc.code == "box-unhealthy":
        return not (arc.detail or "").startswith("stack-deploy:")
    return False


def _anchor_created_key(arc: ts.BoxArc) -> float:
    """Sort key: first-created box (stable proxy for first-to-live).

    ``created_at`` order is NOT ``live``-entry order in general (a
    reprovisioned box keeps its original ``created_at`` — the reclaim
    scenario disproves the identity), but it is the stable proxy the
    record offers: unlike ``status_updated_at`` it never moves on later
    transitions, so the anchor cannot flap when arcs advance.
    Malformed ``created_at`` values sort as newest (``+inf``) — a
    corrupt record never wins the anchor while a healthy candidate
    exists (the #1467 fail-safe, mirrored for the earliest-wins
    direction).
    """
    # Reuse the tenant layer's lenient instant parser (#1467): it never
    # raises, so a hostile timestamp cannot take down selection.
    epoch = ts._created_epoch(arc.created_at)
    return epoch if epoch is not None else float("inf")


def select_live_anchor(arcs: List[ts.BoxArc]) -> Optional[ts.BoxArc]:
    """Select the live-anchor box's arc (TENANT_STATUS_ENDPOINT.md §7/G7).

    The anchor is the first-created box among the anchor candidates —
    the box whose relay reading is the tenant-driving one; every other
    box's reading stays on the operator surface. Operationalized over
    the record's fields: among anchor-candidate arcs (suspension-enterable
    post-``live`` arcs and the latch-holding states entered from them),
    the earliest ``created_at`` wins, tie-broken by box-id lexical —
    deterministic, so the anchor cannot flap between ticks.

    Active rule-6 suspension stickiness (#1416): if any candidate holds
    an active suspension (``connection-unreachable`` with a non-None
    latch), the anchor is the earliest-created among THOSE until the
    suspension exits — reclaiming the anchor for an earlier-created box
    would orphan the suspended box's recovery pair and wedge it
    unreachable forever (delivery-semantics item (c)). Only when no
    latched suspension is active does earliest-created-among-all
    resume. A latchless suspension does not pin the anchor — there is
    no latch whose recovery needs protecting — so with no latched
    suspension active the anchor is earliest-created among ALL
    candidates: a healthy box wins unless the latchless box is itself
    the earliest-created candidate.

    Reprovision carve-out (§7/G7 rule 2): a rule-7 restart leaves the
    anchor's new session at ``provisioning`` — not a candidate — so the
    anchor passes to another post-``live`` box (or to none) without
    pinning the endpoint; if the reprovisioned box reaches ``live``
    again it re-enters candidacy on its (unchanged) ``created_at`` —
    but it does NOT reclaim the anchor from a latched suspension (the
    stickiness rule above wins until the suspension exits).
    Returns None when no box holds a candidate arc — then every reading
    is operator-surface.
    """
    candidates = [a for a in arcs if a.code in _ANCHOR_CODES]
    if not candidates:
        return None
    # Sticky while a latched suspension is up: the suspended box keeps
    # the anchor so its recovery keeps being driven (no wedge).
    suspended = [
        a
        for a in candidates
        if a.code == "connection-unreachable" and a.latched is not None
    ]
    pool = suspended or candidates
    return min(pool, key=lambda a: (_anchor_created_key(a), a.box_id))


# ---------------------------------------------------------------------------
# The event decision table — the single ordered emitter's logic, pure.


def plan_events(
    arc: ts.BoxArc, reading: dict
) -> Tuple[List[Tuple[str, dict]], List[str]]:
    """Decide the ordered tenant-status events for one producer reading.

    Pure function of (arc, reading) — separated from I/O so tests pin
    the event order without a store. Returns ``(events, notes)``:
    ``events`` is ``[(event, kwargs)]`` in emission order (D-RL34-3: the
    recovery pair is always ``relay-reachable`` BEFORE
    ``relay-recovered``); ``notes`` are operator diagnostics.

    ``reading`` is a ``relay_path_state`` result (``state``,
    ``sub_code``, ``reason``, ``probe``, ``journal``). ``degraded``
    readings — and any unrecognized state — plan no events: a suspect
    reading is neither defect evidence (no rule-6 entry) nor
    reachability evidence (no boolean restore).
    """
    events: List[Tuple[str, dict]] = []
    notes: List[str] = []
    state = reading.get("state")
    sub_code = reading.get("sub_code")

    if state == rps.STATE_DOWN:
        # The §5 contract carries the sub-code on down readings
        # (F-RL34-5). A missing/foreign sub-code is a broken-producer
        # signal: the down evidence itself is still real, so rule 6
        # still fires on post-live arcs — but the wiring never invents
        # a classification, so no detail kwarg is passed and the tenant
        # layer's generic "relay-down" default marks the entry as
        # unclassified. The anomaly rides the notes, loud.
        detail_kw = {"detail": sub_code} if sub_code in rps.SUBCODES else {}
        if not detail_kw:
            notes.append(
                "down reading without a §3 sub-code (%r) — rule 6 still "
                "fires on the down evidence; entry detail falls back to "
                "the generic default (unclassified defect)" % (sub_code,)
            )
        if arc.code in _RULE6_ENTRY_CODES:
            # Rule-6 entry with the sub-code in detail (D-RL34-4).
            events.append(("relay-down", detail_kw))
        else:
            # F-RL34-3: latch-holding states (stuck, maintenance,
            # already connection-unreachable) — and every non-post-live
            # code — get the boolean flip only. relay-failure raises
            # TransitionError in the latch-holding states, so the
            # wiring never emits it.
            if sub_code in rps.SUBCODES and arc.detail and arc.detail != sub_code:
                # LOUD: the arc's headline detail names the original
                # defect, but this reading's sub-code is a different
                # leg — the boolean flips on the current evidence while
                # the displayed detail keeps naming the original leg
                # (never refreshed here). The tick report's reading
                # summary carries the current sub-code; note both.
                notes.append(
                    "nested down: headline detail %r names the original "
                    "defect, but the current reading's sub-code is %r "
                    "(different leg) — boolean flipped on the current "
                    "evidence; headline detail not refreshed"
                    % (arc.detail, sub_code)
                )
            events.append(("relay-down", {}))
    elif state == rps.STATE_OK:
        if arc.code == "connection-unreachable":
            if arc.latched is None:
                # Corrupt suspension (no latch): relay-recovered would
                # raise TransitionError — restore the boolean (the
                # reading is positive evidence) and leave the exit to
                # the operator.
                notes.append(
                    "connection-unreachable with no latch for box %r — "
                    "boolean restored, suspension exit left to the "
                    "operator (record needs triage)" % (arc.box_id,)
                )
                events.append(("relay-reachable", {}))
            else:
                # D-RL34-3: boolean restore BEFORE suspension exit.
                events.append(("relay-reachable", {}))
                events.append(("relay-recovered", {}))
        elif not arc.relay_reachable:
            # Resync rule (F-RL34-4): an ok reading with a stale False
            # restores the boolean — the value
            # _re_evaluate_latch_on_exit's backstop reads.
            notes.append(
                "stale relay_reachable=False resynced on ok reading "
                "(no suspension active)"
            )
            events.append(("relay-reachable", {}))
    elif state != rps.STATE_DEGRADED:
        notes.append(
            "unrecognized producer state %r — treated as degraded "
            "(no events)" % (state,)
        )
    # STATE_DEGRADED: operator surface only — no events, never applied.
    return events, notes


def _emit(arc: ts.BoxArc, events: List[Tuple[str, dict]]) -> List[str]:
    """Apply the planned events in order via ``tenant_status.apply_event``.

    Returns the emitted event names in order (kwargs rendered for the
    report). A ``TransitionError`` here is a wiring bug or a corrupt
    arc — it propagates fail-loud rather than skipping silently; the
    plan table guards the known cases so the normal path never raises.
    """
    emitted = []
    for event, kw in events:
        ts.apply_event(arc, event, **kw)
        if kw:
            rendered = ", ".join("%s=%r" % (k, v) for k, v in kw.items())
            emitted.append("%s(%s)" % (event, rendered))
        else:
            emitted.append(event)
    return emitted


def _reading_summary(reading: dict) -> dict:
    """The operator-safe slice of a producer reading (no bundle material —
    ``relay_path_state`` results carry outcome strings only, D-RL2-3)."""
    return {
        "state": reading.get("state"),
        "sub_code": reading.get("sub_code"),
        "reason": reading.get("reason"),
        "probe": reading.get("probe"),
        "journal": reading.get("journal"),
    }


def drive_box(
    arc: ts.BoxArc,
    vm_id: str,
    *,
    read_fn: Callable[[str], dict] = None,
    journal_timeout_s: Optional[float] = None,
) -> dict:
    """Run one wiring tick for a single (anchor) box: read, plan, emit.

    The box's single ordered emitter (D-RL34-3a): the future cadence
    loop — not yet built in production, see issue #1711 — must not run
    two ticks for the same box concurrently. Returns a report
    dict ``{box_id, vm_id, reading, events, notes}``. A broken
    instrument (``JournalLockError`` / ``HistoryLockError`` from the
    read) propagates — a broken instrument is loud, never darkness.

    ``drive_box`` is the per-box single ordered emitter ONLY when
    invoked for the anchor — the anchor-only constraint lives in
    ``drive_tenant``. No production cadence driver exists yet (issue
    #1711): future callers must not drive non-anchor boxes through it.

    ``read_fn`` overrides the producer read (tests): it is called as
    ``read_fn(vm_id)`` — a caller-supplied ``read_fn`` silently ignores
    ``journal_timeout_s`` (the timeout is captured only by the default
    read).
    """
    if read_fn is None:

        def read_fn(vm_id: str, _timeout_s=journal_timeout_s) -> dict:
            return rps.relay_path_state(vm_id, journal_timeout_s=_timeout_s)

    reading = read_fn(vm_id)
    events, notes = plan_events(arc, reading)
    emitted = _emit(arc, events)
    return {
        "box_id": arc.box_id,
        "vm_id": vm_id,
        "reading": _reading_summary(reading),
        "events": emitted,
        "notes": notes,
    }


def drive_tenant(
    store: ts.TenantStore,
    tenant_id: str,
    *,
    read_fn: Callable[[str], dict] = None,
    box_to_vm: Callable[[str], str] = None,
    journal_timeout_s: Optional[float] = None,
) -> dict:
    """Run one R3 wiring tick for a tenant: select the anchor, drive it.

    The live-anchor box's reading is the tenant-driving one; every other
    box's reading is read for the operator surface and never applied to
    an arc.

    The tick is split in two phases. The read phase runs with NO tenant
    lock: it snapshots the record (``store.get``), selects the anchor,
    and reads the producer for the anchor and every other box. Producer
    reads can block on the instrument's own locks (the probe-history
    lock up to 60s, the journal lock up to ``journal_timeout_s``), and
    the store's exclusive lock is a blocking inter-process
    ``fcntl.LOCK_EX`` serializing ALL tenants' writers — per-box I/O
    must never run under it. The apply phase (``TenantStore._mutate``)
    re-selects the anchor from the FRESH record and applies
    ``plan_events`` + ``_emit`` only if the fresh anchor is still the
    box that was read; otherwise the stale reading is skipped and the
    next tick converges (the pair is idempotent, so a skipped tick is
    never a lost tick). The pair still emits atomically through the
    store's lock — the single-ordered-emitter guarantee (D-RL34-3a) is
    unchanged; only the reads moved out from under the lock. A broken
    anchor instrument is loud: its exception propagates from the read
    phase with the record untouched.

    ``box_to_vm`` maps a box id to the instrument's ``vm_id``; the
    default is the identity (the current box-id/vm-id convention).
    ``read_fn(vm_id) -> reading`` overrides the producer read (tests);
    like ``drive_box``, a caller-supplied ``read_fn`` silently ignores
    ``journal_timeout_s``.

    Returns ``{tenant_id, anchor_box_id, boxes: [drive_box-style
    reports]}``. Non-anchor boxes report ``events: []`` with a note —
    their readings were observed, never applied. ``anchor_box_id`` is
    the read-phase anchor (``None`` when no box held a candidate arc).
    """
    if read_fn is None:

        def read_fn(vm_id: str, _timeout_s=journal_timeout_s) -> dict:
            return rps.relay_path_state(vm_id, journal_timeout_s=_timeout_s)

    if box_to_vm is None:

        def box_to_vm(box_id: str) -> str:
            return box_id

    # -- Read phase: no tenant lock -------------------------------------
    # Producer I/O can block on the instrument's locks (probe history up
    # to 60s, journal up to ``journal_timeout_s``), while the store's
    # exclusive lock is a blocking inter-process fcntl LOCK_EX that
    # serializes every tenant's writers. Producer reads and the tenant
    # record come from different stores and are inherently racy anyway —
    # so the read phase snapshots and reads with the lock released, and
    # the apply phase re-checks against the fresh record.
    snap = store.get(tenant_id)
    if snap is None:
        raise ts.TenantStatusError(f"no tenant record: {tenant_id!r}")
    read_anchor = select_live_anchor(list(snap.boxes.values()))
    read_anchor_id = read_anchor.box_id if read_anchor is not None else None

    reports: List[Optional[dict]] = []
    anchor_slot: Optional[int] = None
    anchor_reading: Optional[dict] = None
    anchor_vm_id: Optional[str] = None
    for arc in snap.boxes.values():
        vm_id = box_to_vm(arc.box_id)
        if read_anchor is not None and arc.box_id == read_anchor_id:
            # Anchor read: a broken anchor instrument is loud — the
            # exception propagates and the record is untouched (the
            # apply phase never ran).
            anchor_reading = read_fn(vm_id)
            anchor_vm_id = vm_id
            anchor_slot = len(reports)
            reports.append(None)  # filled by the apply phase
            continue
        try:
            reading = read_fn(vm_id)
            note = (
                "non-anchor box: reading observed for the operator "
                "surface, never applied to the arc"
                if read_anchor_id is not None
                else "no live-anchor box: reading observed for the "
                "operator surface, never applied to the arc"
            )
            reports.append(
                {
                    "box_id": arc.box_id,
                    "vm_id": vm_id,
                    "reading": _reading_summary(reading),
                    "events": [],
                    "notes": [note],
                }
            )
        except Exception as exc:  # noqa: BLE001 — tick must survive
            reports.append(
                {
                    "box_id": arc.box_id,
                    "vm_id": vm_id,
                    "reading": None,
                    "events": [],
                    "notes": [
                        "non-anchor instrument read failed "
                        "(%s: %s) — operator surface only; the "
                        "anchor tick continued"
                        % (type(exc).__name__, exc)
                    ],
                }
            )

    # -- Apply phase: under the store's exclusive lock -------------------
    # Re-select the anchor from the FRESH record: the producer reading
    # is applied only to the box that is STILL the anchor. A stale
    # anchor (moved, reprovisioned, or deleted between the phases) is
    # skipped — the next tick re-selects and converges. The pair emits
    # atomically through the lock: the single-ordered-emitter guarantee
    # (D-RL34-3a) is unchanged; only the reads moved out from under it.
    if read_anchor_id is not None:
        assert anchor_slot is not None
        assert anchor_reading is not None
        assert anchor_vm_id is not None

        def _apply(rec: ts.TenantRecord) -> None:
            fresh_anchor = select_live_anchor(list(rec.boxes.values()))
            fresh_anchor_id = (
                fresh_anchor.box_id if fresh_anchor is not None else None
            )
            if fresh_anchor_id == read_anchor_id:
                arc = rec.boxes[read_anchor_id]
                events, notes = plan_events(arc, anchor_reading)
                emitted = _emit(arc, events)
                reports[anchor_slot] = {
                    "box_id": arc.box_id,
                    "vm_id": anchor_vm_id,
                    "reading": _reading_summary(anchor_reading),
                    "events": emitted,
                    "notes": notes,
                }
            else:
                reports[anchor_slot] = {
                    "box_id": read_anchor_id,
                    "vm_id": anchor_vm_id,
                    "reading": _reading_summary(anchor_reading),
                    "events": [],
                    "notes": [
                        "anchor moved between read and apply (read %r, "
                        "fresh %r) — reading not applied; next tick "
                        "re-selects and converges"
                        % (read_anchor_id, fresh_anchor_id)
                    ],
                }

        store._mutate(tenant_id, _apply)

    assert all(r is not None for r in reports)
    return {
        "tenant_id": tenant_id,
        "anchor_box_id": read_anchor_id,
        "boxes": [r for r in reports if r is not None],
    }
