#!/usr/bin/env python3
"""`GET /tenant/status` — tenant onboarding status endpoint (G3, implementation slice S1).

Implements the contract in ``docs/TENANT_STATUS_ENDPOINT.md``: the control
plane's tenant-layer status surface that the tenant Muse (linked ed25519 key,
signed requests) and the signup page (magic-link session cookie) poll during
the first-ten-minutes onboarding arc.

Design decisions (all per the design doc, no improvisation):

- Vocabulary: the 13 §2 machine codes, exactly spelled. ``human_key`` is the
  §4 rendering key — equal to the machine code for human-rendered codes and
  *absent* for the operator-only codes (``policy-misfire``,
  ``no-gated-action``); a page receiving those falls back to its last
  server-side human-rendered code.
- Transition engine: §2 rules 1-8, including the no-backwards-moves rule,
  the relay/cert suspension latch (rule 6), the maintenance latch (rule 8),
  and the rule-7 session-restart carve-outs (``box-unhealthy``,
  ``provisioning-failed``, ``live``/``approved``, ``stuck`` →
  ``provisioning`` — the only cross-session moves).
- Per-box arc records internally (G7/§8): the store keeps one arc record
  per box keyed by box id; the response schema stays per-tenant (no
  ``box_id`` field). The reported code is the rule-1 total selection
  preference; box identity rides ``detail`` as ``"<sub-code> @
  box=<box-name>"`` when more than one box is still onboarding.
- ``approvals_url`` carrier (G8/§8): mint-once at signup stage 2, stored
  write-if-absent + re-read (atomic/linearizable — no last-writer-wins),
  funnel re-entry is a read path (never a rewrite), rotation only via an
  explicit operator event. Pre-stage-2 polls get the documented 404.
- Auth (§1): two-sided, no unauthenticated access. Cookie session (signup
  page) or linked-key signed request (tenant Muse, per
  ``HOSTED_SIGNUP_ONBOARDING.md`` §4's link-signing scheme). Identity that
  cannot be established -> 401; a valid credential with no servable tenant
  record (deleted, or pre-stage-2) -> 404 (never 403 — no other-tenant
  existence oracle). No tenant selector — identity is credential-derived.
- GET never changes state; responses carry ``Cache-Control: no-store``.
- Stdlib only, so the module runs unchanged on the self-hosted box, the
  hosted control plane, and the operator laptop (same discipline as
  ``harness/key_identity.py``). ed25519 verification is injected as a
  callable because no crypto library is in the stdlib — the endpoint never
  trusts an unverified signature.

Slice boundaries: S2 wires the H4 driver's ``BoxStatus`` into the tenant
layer (the ``live``-entry AND-combine is the named ``live_entry_ready``
unit below); S3 wires the readers (signup page meta-refresh, Muse
poller). This slice is the endpoint + store + transition engine +
contract fixtures.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# §2 — the machine vocabulary (verbatim; hyphens, exact spelling)

STATUS_CODES = frozenset(
    {
        "provisioning",
        "live",
        "waiting-on-approval",
        "approved",
        "box-unhealthy",
        "connection-unreachable",
        "policy-misfire",
        "no-gated-action",
        "human-denied",
        "human-drop-off",
        "stuck",
        "provisioning-failed",
        "maintenance",
    }
)

# §3 — operator-only codes carry no ``human_key``; the human page falls back
# to the last human-rendered code it holds server-side in the magic-link
# session.
OPERATOR_ONLY = frozenset({"policy-misfire", "no-gated-action"})

# Arc-terminal codes (§8 amendment): participate in the rule-1 selection
# only while no non-terminal candidate exists.
TERMINAL_CODES = frozenset(
    {"approved", "human-denied", "human-drop-off", "provisioning-failed"}
)

# Suspension codes (§8 amendment): compare by their latched underlying arc
# code; the suspension itself neither promotes nor demotes the candidate.
SUSPENSION_CODES = frozenset({"stuck", "connection-unreachable", "maintenance"})

# §8 rule-1 total selection preference (amended 2026-09-27/28), non-terminal
# family only. Lower rank wins.
_SELECTION_RANK = {
    "live": 0,
    "waiting-on-approval": 1,
    "provisioning": 2,
    "box-unhealthy": 3,
    "no-gated-action": 4,
    "policy-misfire": 5,
}

# ---------------------------------------------------------------------------
# Transition engine (§2 rules 1-8)


class TenantStatusError(Exception):
    """Base error for the tenant-status layer."""


class TransitionError(TenantStatusError):
    """Raised when an event would move an arc across an illegal transition."""


class UnknownCodeError(TenantStatusError):
    """Raised when a status code is not in the §2 vocabulary."""


def check_code(code: str) -> str:
    """Assert *code* is exactly one of the 13 §2 machine codes."""
    if code not in STATUS_CODES:
        raise UnknownCodeError(f"not a §2 status code: {code!r}")
    return code


def human_key_for(code: str) -> Optional[str]:
    """The §4 rendering key for *code* — ``None`` for operator-only codes."""
    check_code(code)
    if code in OPERATOR_ONLY:
        return None
    return code


# The legal transition table, derived from §2 rules 1-8. Rule 6's
# suspension entries and rule 8's maintenance entries are operator/relay
# inputs, not arc advances; rule 7's cross-session moves are the only
# legal code regressions.
_LEGAL_MOVES: Dict[str, frozenset] = {
    # rule 1: provisioning -> live | box-unhealthy | provisioning-failed
    # (never backwards; a dead box after live is box-unhealthy)
    "provisioning": frozenset({"live", "box-unhealthy", "provisioning-failed"}),
    # rule 2: live -> waiting-on-approval | box-unhealthy | no-gated-action
    # | stuck  (maintenance entry licensed by rule 8; the operator-only
    # policy-misfire is set by the gate tooling per rule 5)
    "live": frozenset(
        {"waiting-on-approval", "box-unhealthy", "no-gated-action", "policy-misfire", "stuck", "maintenance"}
    ),
    # rule 3: waiting-on-approval -> approved | human-denied |
    # human-drop-off | box-unhealthy  (+ suspension/maintenance/operator
    # inputs per rules 6/8/5)
    "waiting-on-approval": frozenset(
        {
            "approved",
            "human-denied",
            "human-drop-off",
            "box-unhealthy",
            "policy-misfire",
            "stuck",
            "connection-unreachable",
            "maintenance",
        }
    ),
    # rule 4: approved is arc-terminal — the endpoint keeps serving and
    # connection-unreachable/maintenance may still be entered (returning
    # to approved); a failed smoke check may surface as box-unhealthy.
    "approved": frozenset(
        {"connection-unreachable", "box-unhealthy", "maintenance"}
    ),
    # box-unhealthy: operator recovery per the §2 table; the only forward
    # path off it is the rule-7 reprovision (the operator-reprovision
    # event, which resets the session — not a plain table move).
    "box-unhealthy": frozenset(),
    # rule 6: relay/cert suspension — entered from any post-live arc code;
    # on recovery the tenant layer re-evaluates to the latched code. Never
    # entered from provisioning/provisioning-failed.
    "connection-unreachable": frozenset(),
    # rule 5: operator-only end-states — never progressing (ranked below
    # box-unhealthy in rule 1), set by gate/pilot tooling.
    "policy-misfire": frozenset(),
    "no-gated-action": frozenset(),
    "human-denied": frozenset(),
    "human-drop-off": frozenset(),
    # stuck: exits are operator/heuristic clear (re-evaluates to the arc
    # code) or rule-7 reprovision. Until G9's S3 bar is met, stuck stays
    # operator-set and is never exposed as automatic.
    "stuck": frozenset(),
    # provisioning-failed: terminal failure — the only move is the rule-7
    # operator retry (the operator-reprovision event).
    "provisioning-failed": frozenset(),
    # rule 8: maintenance — entered only by the control plane's update
    # scheduler from live/approved; on completion the endpoint returns the
    # latched arc code. Failure during maintenance -> box-unhealthy with
    # detail "maintenance-failed: <check>".
    "maintenance": frozenset({"box-unhealthy"}),
}

# Suspension exit targets are computed from the latch (rule 6:
# re-evaluate, never a blind stack-pop), so "connection-unreachable" and
# "stuck" carry an empty legal-move set above — their only exits are the
# *recovery* events, which restore the latched code rather than naming a
# transition target. Rule 7's "stuck -> provisioning" is licensed as a
# session restart (the old box image is gone), handled by
# ``operator_reprovision``.


@dataclass
class BoxArc:
    """One box's onboarding arc record (G7/§8 — evaluation-internal).

    The suspension codes (rule 6: ``connection-unreachable``; G9:
    ``stuck``) and rule-8 ``maintenance`` latch the arc code held at entry
    in ``latched``; arc-advancing events during a relay suspension update
    the latch and never the displayed code.
    """

    box_id: str
    created_at: str  # ISO-8601 UTC; tie-break: newest wins, then box_id lexical
    code: str = "provisioning"
    status_updated_at: str = ""
    detail: Optional[str] = None
    latched: Optional[str] = None  # arc code at suspension/maintenance entry
    latched_detail: Optional[str] = None  # its detail — restored on recovery
    provider_running: bool = False  # §4 live-entry AND-combine inputs
    relay_reachable: bool = False
    session: int = 1  # onboarding session; rule-7 restarts increment

    def __post_init__(self) -> None:
        check_code(self.code)
        if self.latched is not None:
            check_code(self.latched)


def live_entry_ready(arc: BoxArc) -> bool:
    """§4 ``live``-entry AND-combine: provider running AND relay/cert path
    reachable (the §2 minute-0 criterion: ssh connects, cert accepted).

    The §3 smoke gates are a *persistence* guard, not an entry gate: a box
    that was live and then fails a check becomes box-unhealthy via the
    Muse's report — it is never held at provisioning waiting for smoke.
    S2 wires the H4 driver's ``BoxStatus`` into ``provider_running``; the
    combine rule itself is named here as the S1-tested unit.
    """
    return arc.provider_running and arc.relay_reachable


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _touch(arc: BoxArc, code: str, detail: Optional[str] = None) -> None:
    arc.code = check_code(code)
    arc.status_updated_at = _now_iso()
    arc.detail = detail


def _move(arc: BoxArc, target: str, detail: Optional[str] = None) -> None:
    """Move *arc* to *target* if the §2 table licenses it, else raise."""
    if target not in _LEGAL_MOVES.get(arc.code, frozenset()):
        raise TransitionError(
            f"illegal transition: {arc.code!r} -> {target!r} "
            f"(§2 rules 1-8; no backwards moves)"
        )
    _touch(arc, target, detail)


# ---------------------------------------------------------------------------
# S1 producer events — the event->transition mapping named as a tested
# unit alongside the S2 provider mapping (§4). Producer write paths ride
# the same linked-key auth as the poll (§4: the implementation must not
# invent an unauthenticated report endpoint).

# Arc-advancing events that a relay suspension (rule 6) records into the
# latch instead of displaying: the approval UI rides the magic-link
# session, not the relay, so the human can tap Approve/Deny while the
# suspension is showing.
_SUSPENSION_LATCH_EVENTS = frozenset(
    {"approval-filed", "approval-granted", "approval-denied", "approval-expired"}
)


def apply_event(arc: BoxArc, event: str, **kw) -> BoxArc:
    """Apply a producer *event* to *arc*, enforcing the §2 transition rules.

    Mutates and returns *arc*. Raises :class:`TransitionError` on an
    illegal move, :class:`TenantStatusError` on an unknown event.
    """
    # Rule 6: arc-advancing events during a relay suspension update the
    # latch, never the displayed code, never dropped. The latch carries
    # the arc's (code, detail) pair; the suspension's own detail stays
    # displayed while suspended.
    if arc.code == "connection-unreachable" and event in _SUSPENSION_LATCH_EVENTS:
        if arc.latched is None:
            raise TenantStatusError("connection-unreachable with no latch")
        saved_code, saved_detail = arc.code, arc.detail
        arc.code, arc.detail = arc.latched, arc.latched_detail
        try:
            apply_event(arc, event, **kw)
        finally:
            arc.latched, arc.latched_detail = arc.code, arc.detail
            arc.code, arc.detail = saved_code, saved_detail
        return arc

    if event == "provider-running":
        arc.provider_running = True
    elif event == "relay-reachable":
        arc.relay_reachable = True
    elif event == "provider-dead":
        arc.provider_running = False
    elif event == "relay-down":
        arc.relay_reachable = False
    else:
        _apply_arc_event(arc, event, **kw)

    # §4 AND-combine: provisioning -> live fires when both inputs are true.
    if arc.code == "provisioning" and live_entry_ready(arc):
        _move(arc, "live")
    return arc


def _apply_arc_event(arc: BoxArc, event: str, **kw) -> None:
    if event == "stack-deploy-failed":
        # Rule 1(b): driver succeeded but the control plane's stack
        # install failed on the box, no bundle ever handed out ->
        # box-unhealthy with detail "stack-deploy:<stage>".
        stage = kw.get("stage", "unknown")
        _move(arc, "box-unhealthy", detail=f"stack-deploy:{stage}")
    elif event == "provisioning-terminal-failure":
        # Rule 1(a): reachability failure held at provisioning until the
        # H4 driver reports terminal failure -> provisioning-failed.
        _move(arc, "provisioning-failed")
    elif event == "smoke-report-failed":
        # The Muse's §2 smoke report; rule 2 (post-live) and rule 1
        # (pre-live stack-deploy path is the event above — this one is the
        # post-live report). Detail carries the check name.
        check = kw.get("check", "unknown")
        _move(arc, "box-unhealthy", detail=f"box-unhealthy: {check}")
    elif event == "relay-failure":
        # Rule 6: from any post-live arc code; latches the arc code at
        # suspension entry. Not entered from provisioning /
        # provisioning-failed (no arc to suspend yet).
        if arc.code not in ("live", "waiting-on-approval", "approved"):
            raise TransitionError(
                f"relay suspension has no arc to suspend from {arc.code!r}"
            )
        arc.latched = arc.code
        arc.latched_detail = arc.detail
        _touch(arc, "connection-unreachable", detail=kw.get("detail"))
    elif event == "relay-recovered":
        # Rule 6: re-evaluate from current inputs (returns the updated
        # latch) — never a blind stack-pop of a stale code.
        if arc.code != "connection-unreachable" or arc.latched is None:
            raise TransitionError("relay-recovered with no active suspension")
        _touch(arc, arc.latched, arc.latched_detail)
        arc.latched = None
        arc.latched_detail = None
    elif event == "approval-filed":
        # The approval filing event (proxy/confirmd). Detail carries the
        # minute-bound check name (rule 2).
        check = kw.get("check", "gate-1")
        _move(arc, "waiting-on-approval", detail=f"filed-approval: {check}")
    elif event == "approval-granted":
        _move(arc, "approved")
    elif event == "approval-denied":
        _move(arc, "human-denied")
    elif event == "approval-expired":
        _move(arc, "human-drop-off")
    elif event == "gate-policy-misfire":
        # Rule 5: set by the operator's gate tooling — never by the Muse,
        # never shown to the human.
        _move(arc, "policy-misfire")
    elif event == "pilot-no-gated-action":
        # Rule 5: set by pilot analysis.
        _move(arc, "no-gated-action")
    elif event == "operator-mark-stuck":
        # Operator-set until G9's S3 confidence bar is met; never exposed
        # as automatic. Latches the arc code for the clear path.
        if arc.code != "live":
            raise TransitionError(
                f"stuck is only settable from a live arc, not {arc.code!r}"
            )
        arc.latched = arc.code
        arc.latched_detail = arc.detail
        _touch(arc, "stuck", detail=kw.get("detail"))
    elif event == "stuck-cleared":
        # Operator/heuristic clears -> the tenant layer re-evaluates to
        # the current arc code.
        if arc.code != "stuck" or arc.latched is None:
            raise TransitionError("stuck-cleared with no active stuck state")
        _touch(arc, arc.latched, arc.latched_detail)
        arc.latched = None
        arc.latched_detail = None
    elif event == "maintenance-started":
        # Rule 8: entered only by the control plane's update scheduler /
        # reimage orchestrator (never the provider driver, never the
        # Muse), only from live/approved. Detail: "maintenance:
        # <operation>".
        if arc.code not in ("live", "approved"):
            raise TransitionError(
                f"maintenance has no arc to maintain from {arc.code!r}"
            )
        operation = kw.get("operation", "scheduled-update")
        arc.latched = arc.code
        arc.latched_detail = arc.detail
        _touch(arc, "maintenance", detail=f"maintenance: {operation}")
    elif event == "maintenance-completed":
        # Rule 8: on completion the endpoint returns the latched arc code
        # — the update neither advances nor restarts the arc, and the
        # 10-minute clock is unaffected.
        if arc.code != "maintenance" or arc.latched is None:
            raise TransitionError("maintenance-completed with no active maintenance")
        _touch(arc, arc.latched, arc.latched_detail)
        arc.latched = None
        arc.latched_detail = None
    elif event == "maintenance-failed":
        # Rule 8: failure during maintenance -> box-unhealthy with detail
        # "maintenance-failed: <check>". The maintenance latch is cleared:
        # the arc has exited maintenance, so nothing may restore it.
        if arc.code != "maintenance":
            raise TransitionError("maintenance-failed outside maintenance")
        check = kw.get("check", "unknown")
        _move(arc, "box-unhealthy", detail=f"maintenance-failed: {check}")
        arc.latched = None
        arc.latched_detail = None
    elif event == "operator-reprovision":
        # Rule 7: the only legal cross-session moves — box-unhealthy,
        # provisioning-failed, live/approved, or stuck -> provisioning.
        # The endpoint serves the latest session, status_updated_at
        # resets, and the 10-minute clock restarts at the new session's
        # provisioning -> live transition.
        if arc.code not in (
            "box-unhealthy",
            "provisioning-failed",
            "live",
            "approved",
            "stuck",
        ):
            raise TransitionError(
                f"rule 7 does not license a session restart from {arc.code!r}"
            )
        arc.code = "provisioning"
        arc.status_updated_at = _now_iso()
        arc.detail = None
        arc.latched = None
        arc.latched_detail = None
        arc.provider_running = False
        arc.relay_reachable = False
        arc.session += 1
    else:
        raise TenantStatusError(f"unknown producer event: {event!r}")


# ---------------------------------------------------------------------------
# §8 rule-1 — multi-box selection: per-box arc records are
# evaluation-internal; the response schema is unchanged (per-tenant).


def _effective_rank(arc: BoxArc) -> Tuple[int, int]:
    """Sort key for rule-1 selection: (family, rank). Lower wins.

    Family 0: non-terminal codes (suspension codes compare by their latched
    underlying arc code — the suspension neither promotes nor demotes the
    candidate). Family 1: arc-terminal codes — they participate only while
    no non-terminal candidate exists (a dead box never outranks a
    progressing one).
    """
    code = arc.code
    if code in SUSPENSION_CODES:
        if arc.latched is None:
            raise TenantStatusError(f"suspension code {code!r} with no latch")
        code = arc.latched
    if code in TERMINAL_CODES:
        return (1, 0)
    return (0, _SELECTION_RANK[code])


def select_reported(arcs: List[BoxArc]) -> BoxArc:
    """Pick the box arc the endpoint reports, per §8 rule-1.

    Ties break by newest ``created_at``, then box-id lexical — so the
    reported box identity in ``detail`` cannot flap between polls.
    """
    if not arcs:
        raise TenantStatusError("no box arcs to select from")
    return min(
        arcs,
        key=lambda a: (_effective_rank(a), _neg_created(a), a.box_id),
    )


def _neg_created(arc: BoxArc) -> str:
    """Newest-created_at wins: invert the ISO string for min()."""
    return "".join(chr(0x10FFFF - ord(c)) for c in arc.created_at)


# ---------------------------------------------------------------------------
# Tenant-record store (G8/§8) — write-if-absent + re-read, mint-once.


@dataclass
class TenantRecord:
    tenant_id: str
    stage: int = 1  # signup-funnel stage; the endpoint serves stage >= 2 only
    approvals_url: Optional[str] = None  # minted once at stage 2, G8 rule 1
    session_token: Optional[str] = None  # magic-link session (signup page)
    muse_public_key: Optional[str] = None  # linked ed25519 key (OpenSSH line)
    muse_id: Optional[str] = None
    deleted: bool = False
    boxes: Dict[str, BoxArc] = field(default_factory=dict)
    # §8 G7 rule 1: when the leading box is deleted pre-live with no other
    # candidates, the endpoint holds the last reported code with detail
    # noting the operator event. Refreshed on every store write that sees
    # box arcs (GET itself never writes), so the hold survives box deletion.
    last_reported: Optional[dict] = None


class TenantStore:
    """JSON-file tenant-record store.

    Writes are atomic (temp file + rename) and every read-modify-write
    cycle (``_mutate``, ``save``, ``create``) holds an exclusive
    inter-process lock (``fcntl.flock`` on a ``<store>.lock`` sidecar — the
    control plane targets POSIX), so the G8 ``approvals_url``
    write-if-absent is linearizable: two concurrent read-absent stage-2
    submissions serialize, exactly one mints, and the loser renders the
    winner's stored URL. Readers never observe a torn record.
    """

    VERSION = 1

    def __init__(self, path: str):
        self.path = path

    @contextlib.contextmanager
    def _exclusive(self):
        """Hold the store's exclusive lock for a read-modify-write cycle."""
        with open(self.path + ".lock", "a", encoding="utf-8") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    # -- persistence -----------------------------------------------------
    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {"version": self.VERSION, "tenants": {}}
        with open(self.path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save(self, doc: dict) -> None:
        directory = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tenants-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # -- record access ---------------------------------------------------
    @staticmethod
    def _to_record(tenant_id: str, raw: dict) -> TenantRecord:
        boxes = {
            box_id: BoxArc(box_id=box_id, **b)
            for box_id, b in raw.get("boxes", {}).items()
        }
        return TenantRecord(
            tenant_id=tenant_id,
            stage=raw.get("stage", 1),
            approvals_url=raw.get("approvals_url"),
            session_token=raw.get("session_token"),
            muse_public_key=raw.get("muse_public_key"),
            muse_id=raw.get("muse_id"),
            deleted=raw.get("deleted", False),
            boxes=boxes,
            last_reported=raw.get("last_reported"),
        )

    @staticmethod
    def _from_record(rec: TenantRecord) -> dict:
        return {
            "stage": rec.stage,
            "approvals_url": rec.approvals_url,
            "session_token": rec.session_token,
            "muse_public_key": rec.muse_public_key,
            "muse_id": rec.muse_id,
            "deleted": rec.deleted,
            "last_reported": rec.last_reported,
            "boxes": {
                box_id: {
                    "created_at": a.created_at,
                    "code": a.code,
                    "status_updated_at": a.status_updated_at,
                    "detail": a.detail,
                    "latched": a.latched,
                    "latched_detail": a.latched_detail,
                    "provider_running": a.provider_running,
                    "relay_reachable": a.relay_reachable,
                    "session": a.session,
                }
                for box_id, a in rec.boxes.items()
            },
        }

    def get(self, tenant_id: str) -> Optional[TenantRecord]:
        raw = self._load()["tenants"].get(tenant_id)
        return None if raw is None else self._to_record(tenant_id, raw)

    def find_by_session_token(self, token: str) -> Optional[TenantRecord]:
        for tenant_id, raw in self._load()["tenants"].items():
            stored = raw.get("session_token")
            if stored and hmac.compare_digest(stored, token):
                return self._to_record(tenant_id, raw)
        return None

    def _save_record(self, doc: dict, tenant_id: str, rec: TenantRecord) -> None:
        """Persist *rec*, refreshing the §8 hold snapshot.

        The hold (`last_reported`) is recomputed from the current box arcs
        on every write that sees arcs — so a later box deletion leaves a
        faithful snapshot behind for the endpoint to hold. GET never
        writes, so this refresh can only happen on the producer/operator
        write paths.
        """
        if rec.boxes:
            reported = select_reported(list(rec.boxes.values()))
            detail = reported.detail
            if len(rec.boxes) > 1:
                sub = detail if detail else reported.code
                detail = f"{sub} @ box={reported.box_id}"
            rec.last_reported = {
                "code": reported.code,
                "status_updated_at": reported.status_updated_at,
                "detail": detail,
            }
        doc["tenants"][tenant_id] = self._from_record(rec)
        self._save(doc)

    def _mutate(self, tenant_id: str, fn: Callable[[TenantRecord], None]) -> TenantRecord:
        """Load, apply *fn*, save atomically, re-read and return (G8: the
        hand-over step renders the re-read value, never the minted one).

        The whole load→condition→save→re-read cycle holds the exclusive
        lock, so the write-if-absent in ``ensure_approvals_url`` is
        linearizable across processes.
        """
        with self._exclusive():
            doc = self._load()
            raw = doc["tenants"].get(tenant_id)
            if raw is None:
                raise TenantStatusError(f"no tenant record: {tenant_id!r}")
            rec = self._to_record(tenant_id, raw)
            fn(rec)
            self._save_record(doc, tenant_id, rec)
            reread = self.get(tenant_id)
            assert reread is not None
            return reread

    # -- G8: approvals_url lifecycle --------------------------------------
    def ensure_approvals_url(
        self, tenant_id: str, mint: Callable[[], str]
    ) -> Tuple[TenantRecord, bool]:
        """Stage-2 hand-over: mint-once, write-if-absent + re-read (G8 rule 1).

        Returns ``(record, minted)`` where *minted* is True only when this
        call performed the mint. Concurrent submissions serialize on the
        store lock: exactly one mints, the losers render the winner's
        stored URL — the human never holds a URL the record doesn't.
        Funnel re-entry is a read path: with the field present, no mint
        runs and the stored URL is never reassigned (G8 rule 3) — the
        lock-protected atomic rewrite still happens, carrying identical
        content, so a re-entering call serializes behind concurrent
        writers instead of racing them.

        ``mint`` runs while the store lock is held: keep it fast and
        side-effect-free (never touch the store from inside it).
        """
        minted = False

        def _fn(rec: TenantRecord) -> None:
            nonlocal minted
            if rec.approvals_url is None:
                rec.approvals_url = mint()
                minted = True

        rec = self._mutate(tenant_id, _fn)
        return rec, minted

    def rotate_approvals_url(
        self, tenant_id: str, new_url: str, *, reason: str
    ) -> TenantRecord:
        """Explicit operator rotation (G8 rule 4) — the only rewrite path.

        Rotation is never a funnel side effect; pre-launch the contract is
        mint-once and this path exists for the operator event (suspected
        exposure, domain/path change) with a recorded reason.
        """
        if not reason:
            raise TenantStatusError("approvals_url rotation requires a reason")

        def _fn(rec: TenantRecord) -> None:
            rec.approvals_url = new_url

        return self._mutate(tenant_id, _fn)

    # -- auth material ----------------------------------------------------
    def mint_session_token(self, tenant_id: str) -> str:
        """Issue the magic-link session's opaque token (operator/signup flow)."""
        token = secrets.token_hex(32)

        def _fn(rec: TenantRecord) -> None:
            rec.session_token = token

        self._mutate(tenant_id, _fn)
        return token

    def save(self, rec: TenantRecord) -> None:
        with self._exclusive():
            doc = self._load()
            self._save_record(doc, rec.tenant_id, rec)

    def create(self, rec: TenantRecord) -> None:
        with self._exclusive():
            doc = self._load()
            if rec.tenant_id in doc["tenants"]:
                raise TenantStatusError(f"tenant record exists: {rec.tenant_id!r}")
            self._save_record(doc, rec.tenant_id, rec)


# ---------------------------------------------------------------------------
# §3 — response schema


def status_response(rec: TenantRecord) -> dict:
    """Build the per-tenant §3 response body.

    ``detail`` is present only where a sub-decision exists (§3); when more
    than one box is still onboarding, box identity rides ``detail`` as
    ``"<sub-code> @ box=<box-name>"``. ``human_key`` is absent for the
    operator-only codes. Serves the latest session per rule 7.

    §8 G7 rule 1: with no box candidates (the leading box was deleted
    pre-``live``), the endpoint holds the last reported code, with
    ``detail`` noting the operator event — until a new provisioning or a
    rule-7 restart supplies a candidate.
    """
    arcs = list(rec.boxes.values())
    if not arcs:
        hold = rec.last_reported
        if hold is None:
            raise TenantStatusError("tenant record has no box arcs and no held report")
        body = {
            "tenant_id": rec.tenant_id,
            "status": hold["code"],
            "status_updated_at": hold["status_updated_at"],
            "approvals_url": rec.approvals_url,
        }
        note = "held: box deleted pre-live"
        prior = hold.get("detail")
        body["detail"] = f"{prior} — {note}" if prior else note
        human_key = human_key_for(hold["code"])
        if human_key is not None:
            body["human_key"] = human_key
        return body
    reported = select_reported(arcs)
    body = {
        "tenant_id": rec.tenant_id,
        "status": reported.code,
        "status_updated_at": reported.status_updated_at,
        "approvals_url": rec.approvals_url,
    }
    detail = reported.detail
    if len(arcs) > 1:
        # §3 exception / §8: disambiguate which box the reported arc belongs
        # to whenever more than one box is still onboarding.
        sub = detail if detail else reported.code
        detail = f"{sub} @ box={reported.box_id}"
    if detail is not None:
        body["detail"] = detail
    human_key = human_key_for(reported.code)
    if human_key is not None:
        body["human_key"] = human_key
    return body


# ---------------------------------------------------------------------------
# §1 — the endpoint: two-sided auth, 401/404, GET never changes state.


VerifyFn = Callable[[bytes, bytes, str], bool]
"""``verify(message, signature, public_key_openssh_line) -> bool`` — the
injected ed25519 primitive (stdlib has no ed25519; the endpoint never
trusts an unverified signature)."""

SIGNATURE_WINDOW_S = 300  # signed-request timestamp freshness window

# Dummy linked key used so signature verification always runs, even when the
# tenant id names no record: the 401 latency must not reveal whether a
# tenant exists (contract §1's enumeration-oracle discipline). Every real
# ed25519 implementation returns False (or raises, which also fails closed)
# for a zero key.
_DUMMY_VERIFY_KEY = "ssh-ed25519 AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def _fail_closed_self_test(verify: VerifyFn) -> None:
    """Refuse to serve if *verify* accepts a garbage signature.

    Guards the wiring point: nothing may pass an always-true stub into
    ``serve()`` — the endpoint must fail closed, never trust.
    """
    accepted = False
    try:
        accepted = bool(
            verify(b"tenant-status self-test", b"\x00" * 64, _DUMMY_VERIFY_KEY)
        )
    except Exception:
        accepted = False
    if accepted:
        raise TenantStatusError(
            "refusing to serve: verify() accepts a garbage signature"
        )


def canonical_poll_message(tenant_id: str, ts: str) -> bytes:
    """The exact bytes the tenant Muse signs for a status poll
    (``HOSTED_SIGNUP_ONBOARDING.md`` §4 link-signing scheme)."""
    return f"{tenant_id}\n{ts}\nGET /tenant/status".encode("utf-8")


class TenantStatusService:
    """Auth + response logic for ``GET /tenant/status``, handler-agnostic."""

    def __init__(self, store: TenantStore, verify: VerifyFn):
        self.store = store
        self.verify = verify

    def _authenticate(self, headers: Dict[str, str]) -> Optional[TenantRecord]:
        """Resolve the caller's tenant record from its credential.

        Precedence: a present ``session`` cookie is tried first; only when
        no cookie is present does the signed-request side run. (A stale
        cookie therefore yields 401 even with a valid signature — the
        caller retries without the cookie.)
        """
        # Side 1: magic-link session cookie (signup page).
        cookie = headers.get("cookie", "")
        session = None
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name.strip().lower() == "session" and value.strip():
                session = value.strip()
                break
        if session is not None:
            return self.store.find_by_session_token(session)
        # Side 2: linked-key signed request (tenant Muse). Verification
        # ALWAYS runs — against the dummy key when the tenant id names no
        # record — so 401 latency cannot reveal tenant existence.
        tenant_id = headers.get("x-tenant-id")
        ts = headers.get("x-signature-ts")
        sig_b64 = headers.get("x-signature")
        if not (tenant_id and ts and sig_b64):
            return None
        try:
            ts_int = int(ts)
        except ValueError:
            return None
        if abs(time.time() - ts_int) > SIGNATURE_WINDOW_S:
            return None
        try:
            signature = base64.b64decode(sig_b64, validate=True)
        except (binascii.Error, ValueError):
            return None
        rec = self.store.get(tenant_id)
        key = (
            rec.muse_public_key
            if (rec is not None and rec.muse_public_key)
            else _DUMMY_VERIFY_KEY
        )
        try:
            ok = self.verify(
                canonical_poll_message(tenant_id, ts), signature, key
            )
        except Exception:
            return None
        if not ok or rec is None or rec.muse_public_key is None:
            return None
        return rec

    def handle_get(self, path: str, headers: Dict[str, str]) -> Tuple[int, dict]:
        """Returns ``(http_status, json_body)``. Never writes to the store."""
        if urlparse(path).path != "/tenant/status":
            return 404, {"error": "not_found"}
        rec = self._authenticate(headers)
        if rec is None:
            # §1: the caller's tenant identity could not be established.
            return 401, {"error": "unauthorized"}
        if (
            rec.deleted
            or rec.stage < 2
            or rec.approvals_url is None
            or (not rec.boxes and rec.last_reported is None)
        ):
            # §1/§3: a valid credential with no servable tenant record
            # (deleted, or a pre-stage-2 record this endpoint does not
            # serve) gets 404 — not 403, so the endpoint never confirms the
            # existence of other tenants. The §8 empty-candidate hold keeps
            # serving while last_reported exists.
            return 404, {"error": "no_servable_tenant_record"}
        return 200, status_response(rec)


class TenantStatusHandler(BaseHTTPRequestHandler):
    """Stdlib HTTP handler wiring ``TenantStatusService`` to the socket."""

    service: TenantStatusService  # set by serve()

    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        # §1: both pollers must see the flip within one poll interval.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        headers = {k.lower(): v for k, v in self.headers.items()}
        status, body = self.service.handle_get(self.path, headers)
        self._send_json(status, body)

    def do_POST(self) -> None:  # noqa: N802
        self._send_json(405, {"error": "method_not_allowed"})

    def log_message(self, *args) -> None:  # keep daemon logs quiet
        pass


def serve(store_path: str, bind: str, port: int, verify: VerifyFn) -> None:
    """Run the endpoint daemon (local and ephemeral in tests; the deployed
    control plane binds its own interface)."""
    _fail_closed_self_test(verify)  # never serve with a trusting stub
    service = TenantStatusService(TenantStore(store_path), verify)
    TenantStatusHandler.service = service
    httpd = HTTPServer((bind, port), TenantStatusHandler)
    httpd.serve_forever()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", required=True, help="tenant-record JSON store path")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18750)
    args = parser.parse_args(argv)

    def _unwired(message: bytes, signature: bytes, public_key: str) -> bool:
        # Linked-key verification is wired by the control plane at deploy
        # time; the daemon refuses signed requests until then rather than
        # trusting them. Cookie-session auth works regardless.
        return False

    serve(args.store, args.bind, args.port, _unwired)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
