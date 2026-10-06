"""The #967 sender loop: drain the push outbox to devices (D56).

This module is the missing half of the GP1 sender. The crypto is proved
(``hosted/push_crypto.py``, #967 S1), the send path is built
(``hosted/push_sender.py``, #989 — stdlib RFC 8030 POST, per-code result
taxonomy), the schema is contracted (``docs/PUSH_SENDER_SCHEMA_CONTRACT.md``,
#988), the enqueue boundary holds the D10 reservation and the ``'queued'``
outbox work item (``hosted/push_enqueue.py``, #990), and the event mapping
is pinned (``hosted/push_events.py``, #969). What nothing did yet was *drive*
them: this loop claims ``'queued'`` outbox rows and fans them out to the
owner's devices.

Design (the D56 sender-loop contract from ``push_enqueue.py``, restated so
this module reads without it):

- **D56a — claiming.** Exactly one loop instance per D1 store; ``'queued'``
  rows are processed in ``id`` ASC. Two workers SELECTing the same rows
  double-send. The module does not try to elect a leader — the plane runs
  one scheduled sender per store. ``max_claims`` bounds one tick so a tick
  cannot run forever.
- **D56b — terminal transaction.** ``{INSERT the terminal attempt row,
  DELETE the queued work-item row, release the reservation if the outcome
  releases it}`` is **one** transaction: a crash between INSERT and DELETE
  leaves a stale work item, and a stale work item is redelivered. The
  release inlines the two UPDATEs from ``push_enqueue.release_reservation``
  (floored at zero); ``release_reservation()`` itself commits and must not
  be called mid-transaction. The page completes when **every** live device
  has a terminal outcome (accepted | tombstone | dead-letter) — deleting
  the queued row on the first device's terminal outcome would starve the
  other devices. Terminal outcomes resolve the D52/D10 reservation:
  released iff no device accepted (D10 bounds successful pages, so one
  buzz consumes the page's unit); ``retry`` holds the reservation across
  attempts. Page-level suppressions (gate-2 ``suppressed_terminal``) use
  the same one-transaction shape.
- **D56c — fanout multiplicity.** One row per (device x attempt). The
  enqueue row carries ``device=''``; each device delivery attempt is its
  own row carrying the real device label (D48d's compromise audit joins on
  the row's ``vapid_key_id``). The D10 reservation stays per page, not per
  device-row.
- **D56d — gate-2 scope.** The terminal-state re-read applies to aid-keyed
  kinds (``approval_filed``, ``reminder``) — the approval record exists to
  re-read. ``token_expiry_warning`` / ``box_revoked`` / ``heartbeat_stale``
  / ``digest`` are point-in-time facts with no approval record
  (``box_revoked`` is itself terminal); gate-2 is vacuous for them.
- **D56e — ``suppressed_terminal`` shape.** Mirrors ``suppressed_budget``
  (``device=''``, ``http_status``/``latency_ms``/``sent_at``/
  ``vapid_key_id`` NULL) — the sentinel leg's consumer contract. The loop's
  gate-2 audit uses the D61 audit key (page key + U+0000 ``"superseded"``
  suffix): the D57 partial unique index covers ``suppressed_terminal``, so
  an audit written under the page's exact key would collide with the still
  present ``'queued'`` row. A lost INSERT race (a sweep's gate-1 audit won)
  surfaces as IntegrityError — the queued row is still DELETEed and the
  reservation still released; the audit exists, which is the idempotent
  outcome.
- **D56f — retry state.** The #989 backoff attempt number is derived from
  COUNT of existing ``'retry'`` rows for the work item's key — no new
  column; the schema stays frozen per the #988 contract. Crash posture:
  the attempt row is INSERTed immediately after the POST returns; a crash
  in that window under-counts (documented, accepted — the page retries
  once more; Web Push has no idempotency key, so the cost is a possible
  second buzz, never a lost page).

New pins this slice (continuing the global D-series):

- **D78 — digest fanout.** A ``digest`` page (``box_id`` NULL at enqueue,
  ``''`` in the row) fans out to every ``live`` subscription under
  ``(owner_principal, *)``. The digest is owner-scoped (its D13 key is
  owner + window); ``push_digest_state`` carries no per-box contribution,
  so per-box fanout is unimplementable without a schema change. The
  digest body carries a count, never an aid (contract §1.4).
- **D79 — per-kind plaintext.** Every page is sent through
  ``push_payload.build_push_payload``'s exact ``{aid, ttl_s, summary}``
  shape ("go look" payloads, GP decision). ``aid`` is plane-minted, never
  box free text:

  ================  =====================================================
  kind              aid / ttl_s / summary
  ================  =====================================================
  approval_filed,   aid=<aid>, ttl_s=<record ttl_seconds> (the page must
  reminder          never outlive the approval — #989 finding 1),
                    summary=<record summary> (box-controlled, scrubbed by
                    ``build_push_payload``)
  token_expiry_     aid=``"token-expiry:" + token_hash`` (the D13 identity,
  warning          not a secret), ttl_s=300 (the warning is about imminent
                    expiry; a stale page is worse than none),
                    summary=plane-authored fixed string
  box_revoked       aid=``"box-revoked:" + box_id``, ttl_s=3600 (revocation
                    is durable), summary=plane-authored fixed string
  heartbeat_stale   aid=``"heartbeat-stale:" + stale_epoch``, ttl_s=3600,
                    summary=plane-authored fixed string
  digest            aid=``"digest:" + owner_principal + ":" + window_start``,
                    ttl_s=3600 (covers the hour window), summary=the
                    ``push_digest_state`` count rendered by the plane
                    ("N pages coalesced this hour"). A missing digest-state
                    row is corruption: the page dead-letters (fail-closed,
                    operator-visible) rather than sending a count the loop
                    cannot prove. #1064 owns digest content assembly and
                    may refine this body.
  ================  =====================================================

- **D80 — gate-2 fail-safe.** If the approval record is missing at send
  time (deleted, or never written — a bug either way), the page is
  ``suppressed_terminal``, not sent. A page that cannot prove
  non-terminal must not page. Loud in the tick summary.
- **D81 — parked, not dropped.** Zero ``live`` subscriptions: the work
  item stays ``'queued'`` (disposition ``parked``) and keeps its
  reservation. Dropping it would lose the page before the owner ever
  subscribes; the reservation lives in an hour bucket that goes stale
  unread, so the effective budget cost is zero. The outbox is the
  delivery buffer across the cold-start gap #428's email covers.
- **D82 — retry pacing.** Tick-shaped loop; a (work item x device) pair is
  re-attempted only when ``now >= sent_at(latest 'retry' row) +
  backoff_s(retry_count)``, ``retry_count`` = COUNT of its ``'retry'``
  rows, all recomputable from stored rows under the frozen schema. The
  ``retry_after_s`` the sender honors (429 Retry-After, clamped) is
  returned to the plane scheduler in the tick summary as
  ``retry_hint_s``; the persisted pacing is the deterministic backoff.
  Residual, stated honestly: a 429 whose Retry-After exceeds
  ``backoff_s(n)`` may be re-attempted before the asked wait elapses —
  the push service's remedy is another 429, which is absorbed as another
  ``retry``. Never a correctness failure, never a lost page.
- **D83 — retry budget.** Six attempts per (work item x device); the
  seventh would-be attempt dead-letters without sending ("exhausted
  retries" — the taxonomy's dead-letter class). ~8 minutes of backoff
  (2+8+32+128+300) is the approval-TTL order of magnitude, and the D8
  reminder re-pages at TTL/2 anyway, so a dead-lettered page is not a
  lost page — it is a page the retry machinery already replaced.
- **D84 — plaintext serialization.** The #970 mapping is canonical-JSON
  serialized: ``json.dumps(payload, sort_keys=True, separators=(",", ":"),
  ensure_ascii=True).encode("utf-8")``. Deterministic across ticks (a
  retried page encrypts byte-identical plaintext), pure ASCII (the
  scrub already stripped controls).

Plane seams (injected — the module never sees a Worker secret, a data
key, or a box token):

- ``list_subscriptions(owner_principal, box_id)`` -> list of mappings
  with ``owner_principal`` / ``box_id`` / ``device`` / ``endpoint`` /
  ``p256dh`` / ``auth`` (base64url strings, *plaintext* at this seam —
  the plane decrypts the D45 ciphertexts under its Worker-secret data
  key just before calling; the harness stores plaintext rows and
  documents the difference per ``docs/PRODUCTION_DEPLOY_CONTRACT.md``)
  / ``vapid_key_id`` / ``status``. ``box_id`` is None for the digest
  (D78: fanout over ``(owner_principal, *)``).
- ``vapid_keys(vapid_key_id)`` -> ``(private_key, public_key)`` bytes
  (the plane's Worker-secret lookup, D48c rotation discriminator).
- ``vapid_subject`` — the operator ``mailto:`` (D48e; the enqueue
  boundary pins ``mailto:hosted@sparkvm.dev``, D55).
- ``record_reader(box_id, aid)`` -> ``{"ttl_seconds": int, "summary":
  str, "terminal": bool} | None`` — gate-2 (D56d). ``make_record_reader``
  builds one over the #872 ``approvals`` table.
- ``transport`` — passthrough to ``push_sender.send_push`` (the stub in
  tests; the documented difference: the stub speaks plain HTTP on
  localhost, TLS is covered by the sender's own tests).

D1 portability: the tick issues explicit statements + one ``commit()``
per transaction — no BEGIN/COMMIT text, no ``with conn:`` (the D52
precedent: D1's batch model is non-interactive). ``sqlite3.IntegrityError``
is referenced defensively via duck-typing (``__name__`` check) so the
module does not import sqlite3 at all.
"""

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import push_enqueue, push_payload, push_sender

# Re-exported contract vocabulary (single source of truth stays in #990).
PAGING_EVENT_KINDS = push_enqueue.PAGING_EVENT_KINDS

#: D56d — gate-2 applies to aid-keyed kinds only.
AID_KEYED_KINDS = frozenset({"approval_filed", "reminder"})

#: D83 — attempts per (work item x device) before the page dead-letters.
MAX_ATTEMPTS = 6

#: D50/D56 — the outbox work-item outcome the loop claims.
OUTCOME_QUEUED = "queued"

#: D61 — the gate-2 audit key suffix (page key + U+0000 + "superseded").
_AUDIT_SUFFIX = "superseded"

#: D79 — plane-authored fixed summaries for non-approval kinds.
_SUMMARY_TOKEN_EXPIRY = (
    "Box token expiring soon — rotate it from the dashboard.")
_SUMMARY_BOX_REVOKED = (
    "Box revoked — it can no longer reach the plane.")
_SUMMARY_HEARTBEAT_STALE = (
    "Box has not checked in for 4 hours — open the dashboard.")

#: D79 — TTL pins for non-approval kinds (seconds).
_TTL_TOKEN_EXPIRY = 300
_TTL_BOX_REVOKED = 3600
_TTL_HEARTBEAT_STALE = 3600
_TTL_DIGEST = 3600


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _utcnow(now=None):
    """Normalize the loop's single clock reading (the D73 convention).

    Accepts an aware/naive datetime (naive assumed UTC) or epoch seconds.
    Anything else is a ValueError — a tick must never run on an untrusted
    clock reading.
    """
    if now is None:
        return datetime.now(timezone.utc)
    if isinstance(now, bool):
        raise ValueError("now must be a datetime or epoch seconds")
    if isinstance(now, (int, float)):
        return datetime.fromtimestamp(now, tz=timezone.utc)
    if isinstance(now, datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)
    raise ValueError("now must be a datetime or epoch seconds, not %r"
                     % (type(now).__name__,))


def _require_str(name, value):
    if isinstance(value, bool) or not isinstance(value, str) or not value:
        raise ValueError("%s must be a non-empty str" % name)
    if "\x00" in value:
        raise ValueError("%s must not contain U+0000" % name)
    return value


def _is_integrity_error(exc):
    """Duck-typed IntegrityError check — the module never imports sqlite3."""
    return type(exc).__name__ == "IntegrityError"


def _split_event_key(event_key):
    """Split a §1.3a event key into (scope, key_material), fail-closed."""
    if not isinstance(event_key, str) or not event_key:
        raise ValueError("event_key must be a non-empty str")
    parts = event_key.split("\x00")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("event_key must be scope + U+0000 + key_material")
    return parts[0], parts[1]


def _window_start_of(at):
    """Recover the D10 hour bucket from a queued row's ``at`` (ISO UTC)."""
    try:
        moment = datetime.fromisoformat(at)
    except (TypeError, ValueError):
        raise ValueError("queued row 'at' is not ISO-8601: %r" % (at,))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


# ---------------------------------------------------------------------------
# Gate-2 record reader (the #872 approvals table)
# ---------------------------------------------------------------------------

def make_record_reader(conn, now):
    """Build the gate-2 record reader over the #872 ``approvals`` table.

    Returns ``get_record(box_id, aid)`` -> ``{"ttl_seconds": int,
    "summary": str, "terminal": bool}`` or ``None`` when the row is absent.
    Shape mirrors ``push_sweep.make_record_adapter`` plus the ``summary``
    column the loop needs for the D79 payload; the terminal derivation is
    identical (decision set, status terminal, or clock-expired). A corrupt
    row is a ValueError — a tick must never page on timing it cannot
    trust (the sweep's D59 rule, inherited).
    """
    moment = _utcnow(now)
    moment_epoch = moment.timestamp()

    def get_record(box_id, aid):
        _require_str("box_id", box_id)
        _require_str("aid", aid)
        row = conn.execute(
            "SELECT created_at, expires_at, decision, status, summary"
            " FROM approvals WHERE box_id = ? AND aid = ?",
            (box_id, aid)).fetchone()
        if row is None:
            return None
        created_at, expires_at, decision, status, summary = row
        for name, value in (("created_at", created_at),
                            ("expires_at", expires_at)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    "approvals %s for (%r, %r) must be an epoch int, not %r"
                    % (name, box_id, aid, value))
        if decision is not None and not isinstance(decision, str):
            raise ValueError(
                "approvals decision for (%r, %r) must be a str or null"
                % (box_id, aid))
        if status not in ("pending", "approved", "denied", "expired"):
            raise ValueError(
                "approvals status for (%r, %r) must be pending|approved|"
                "denied|expired, not %r" % (box_id, aid, status))
        if not isinstance(summary, str):
            raise ValueError(
                "approvals summary for (%r, %r) must be a str, not %r"
                % (box_id, aid, summary))
        ttl = expires_at - created_at
        if not isinstance(ttl, int) or ttl <= 0:
            raise ValueError(
                "approvals ttl for (%r, %r) must be a positive int, not %r"
                % (box_id, aid, ttl))
        terminal = (
            decision is not None
            or status in ("approved", "denied", "expired")
            or (status == "pending" and moment_epoch >= expires_at))
        return {"ttl_seconds": ttl, "summary": summary, "terminal": terminal}

    return get_record


# ---------------------------------------------------------------------------
# D79 — per-kind plaintext
# ---------------------------------------------------------------------------

def _plaintext_for(event_kind, *, key_material, owner_principal, record,
                   digest_count):
    """Return ``(aid, ttl_s, summary)`` for the D79 kind mapping.

    ``key_material`` is the event key's second component; ``record`` is the
    gate-2 reader's dict (aid kinds only — non-None by construction);
    ``digest_count`` is the ``push_digest_state`` count (digest only).
    """
    if event_kind in AID_KEYED_KINDS:
        return key_material, record["ttl_seconds"], record["summary"]
    if event_kind == "token_expiry_warning":
        return ("token-expiry:" + key_material, _TTL_TOKEN_EXPIRY,
                _SUMMARY_TOKEN_EXPIRY)
    if event_kind == "box_revoked":
        return ("box-revoked:" + key_material, _TTL_BOX_REVOKED,
                _SUMMARY_BOX_REVOKED)
    if event_kind == "heartbeat_stale":
        return ("heartbeat-stale:" + key_material, _TTL_HEARTBEAT_STALE,
                _SUMMARY_HEARTBEAT_STALE)
    if event_kind == "digest":
        return ("digest:" + owner_principal + ":" + key_material,
                _TTL_DIGEST,
                "%d page%s coalesced this hour — open the dashboard."
                % (digest_count, "" if digest_count == 1 else "s"))
    raise ValueError("not a paging event kind: %r" % (event_kind,))


def serialize_plaintext(payload):
    """D84 — canonical-JSON serialization of a #970 payload mapping.

    Deterministic across ticks (a retried page encrypts byte-identical
    plaintext), pure ASCII (the scrub already stripped controls). The
    explicit ``dict()`` copy is the one sanctioned place the immutable
    #970 mapping becomes a plain dict — serialization only, never
    mutation.
    """
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


# ---------------------------------------------------------------------------
# Tick summary
# ---------------------------------------------------------------------------

class SendLoopSummary:
    """Structured result of one ``send_loop`` tick.

    ``dispositions`` maps disposition -> count; ``anomalies`` is the
    operator-visible list (tombstones, dead-letters, suppressions, parks,
    errors — each a short human string, never an endpoint or secret);
    ``retry_hint_s`` is the minimum ``retry_after_s`` returned this tick
    (D82: informational for the plane scheduler).
    """

    def __init__(self, tick_at):
        self.tick_at = tick_at
        self.dispositions = Counter()
        self.attempts = 0
        self.anomalies = []
        self.retry_hint_s = None

    def note(self, disposition, detail=None):
        self.dispositions[disposition] += 1
        if detail:
            self.anomalies.append("%s: %s" % (disposition, detail))

    def observe_retry_hint(self, retry_after_s):
        if retry_after_s is None:
            return
        if self.retry_hint_s is None or retry_after_s < self.retry_hint_s:
            self.retry_hint_s = retry_after_s

    def as_dict(self):
        return {
            "tick_at": self.tick_at.isoformat(),
            "dispositions": dict(self.dispositions),
            "attempts": self.attempts,
            "anomalies": list(self.anomalies),
            "retry_hint_s": self.retry_hint_s,
        }


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

_RELEASE_SQL = (
    "UPDATE push_budget_counters SET count ="
    " CASE WHEN count > 0 THEN count - 1 ELSE 0 END"
    " WHERE scope_type = ? AND scope_id = ? AND window_start = ?")

_TOMBSTONE_SQL = (
    "UPDATE push_subscriptions SET status = 'dead_410'"
    " WHERE owner_principal = ? AND box_id = ? AND device = ?"
    " AND status = 'live'")


def _insert_attempt_row(conn, at, owner_principal, box_col, device,
                        event_kind, event_key, result, sent_at, vapid_key_id):
    """D56c/D56f — one row per (device x attempt), INSERTed immediately
    after the POST returns (the crash-posture pin)."""
    conn.execute(
        "INSERT INTO push_send_results"
        " (at, owner_principal, box_id, device, event_kind, event_key,"
        "  outcome, http_status, latency_ms, sent_at, vapid_key_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (at, owner_principal, box_col, device, event_kind, event_key,
         result.outcome, result.http_status, result.latency_ms,
         sent_at, vapid_key_id))


def _insert_audit_row(conn, at, owner_principal, box_col, event_kind,
                      event_key, outcome):
    """D56e — a boundary-extension row (``device=''``, all send columns
    NULL; the sentinel leg's consumer contract)."""
    conn.execute(
        "INSERT INTO push_send_results"
        " (at, owner_principal, box_id, device, event_kind, event_key,"
        "  outcome, http_status, latency_ms, sent_at, vapid_key_id)"
        " VALUES (?, ?, ?, '', ?, ?, ?, NULL, NULL, NULL, NULL)",
        (at, owner_principal, box_col, event_kind, event_key, outcome))


def _delete_queued(conn, row_id):
    conn.execute("DELETE FROM push_send_results WHERE id = ?", (row_id,))


def _release_reservation_statements(conn, box_id, owner_principal,
                                    window_start):
    """Inline the two D52 release UPDATEs (D56b — no commit here; the
    caller commits the terminal transaction). Floored at zero."""
    if box_id is not None:
        conn.execute(_RELEASE_SQL, ("box", box_id, window_start))
    conn.execute(_RELEASE_SQL, ("owner", owner_principal, window_start))


def _terminal_transaction(conn, *, release, box_id, owner_principal,
                          window_start):
    """D56b — one transaction: the attempt/audit row is already INSERTed,
    then DELETE the queued work item and (unless the outcome keeps it)
    release the D10 reservation. Explicit statements + one commit: D1's
    non-interactive batch model."""
    if release:
        _release_reservation_statements(conn, box_id, owner_principal,
                                        window_start)
    conn.commit()


def _retry_stats(conn, box_col, event_kind, event_key, device):
    """D56f/D82 — (retry_count, latest sent_at) for one (page x device)."""
    row = conn.execute(
        "SELECT COUNT(*), MAX(sent_at) FROM push_send_results"
        " WHERE box_id = ? AND event_kind = ? AND event_key = ?"
        " AND device = ? AND outcome = 'retry'",
        (box_col, event_kind, event_key, device)).fetchone()
    count = row[0] or 0
    latest = row[1]
    return count, latest


_TERMINAL_OUTCOMES = ("accepted", "tombstone", "dead-letter")


def _device_terminal_outcome(conn, box_col, event_kind, event_key, device):
    """The device's terminal outcome for this page, or None.

    ``'queued'`` rows carry ``device=''`` and ``suppressed_*`` rows are
    page-level (D56e), so neither can collide with a device's terminal
    row.
    """
    row = conn.execute(
        "SELECT outcome FROM push_send_results"
        " WHERE box_id = ? AND event_kind = ? AND event_key = ?"
        " AND device = ? AND outcome IN ('accepted', 'tombstone',"
        " 'dead-letter') LIMIT 1",
        (box_col, event_kind, event_key, device)).fetchone()
    return row[0] if row else None


def _complete_page(conn, summary, item, row_id, box_id, owner_principal,
                   window_start, terminal, live_count):
    """DELETE the queued work item and resolve the D10 reservation.

    The reservation is released iff no device accepted — D10 bounds
    successful pages, so one buzz consumes the page's unit. One
    transaction (D56b): the caller's attempt rows are already INSERTed.
    """
    release = "accepted" not in terminal.values()
    _delete_queued(conn, row_id)
    _terminal_transaction(conn, release=release, box_id=box_id,
                          owner_principal=owner_principal,
                          window_start=window_start)
    summary.note("completed",
                 "%s (%d/%d devices terminal; reservation %s)"
                 % (item, len(terminal), live_count,
                    "released" if release else "kept"))


def _maybe_complete(conn, summary, item, row_id, box_id, owner_principal,
                    window_start, terminal, live_count):
    """Complete the page if every live device is terminal; True if so."""
    if len(terminal) == live_count:
        _complete_page(conn, summary, item, row_id, box_id,
                       owner_principal, window_start, terminal, live_count)
        return True
    return False


def send_loop(conn, *, list_subscriptions, vapid_keys, vapid_subject,
              record_reader=None, transport=None, now=None,
              max_claims=100):
    """Run one sender tick: claim ``'queued'`` rows and drive them.

    D56a — exactly one instance per D1 store; rows claimed in ``id`` ASC,
    at most ``max_claims`` per tick. Every injected seam is validated
    fail-closed before the first row is touched.
    """
    if not callable(list_subscriptions):
        raise ValueError("list_subscriptions must be callable")
    if not callable(vapid_keys):
        raise ValueError("vapid_keys must be callable")
    _require_str("vapid_subject", vapid_subject)
    if record_reader is not None and not callable(record_reader):
        raise ValueError("record_reader must be callable or None")
    if not isinstance(max_claims, int) or isinstance(max_claims, bool) \
            or max_claims < 1:
        raise ValueError("max_claims must be a positive int")

    moment = _utcnow(now)
    at = moment.isoformat()
    sent_at = moment.timestamp()
    summary = SendLoopSummary(moment)

    rows = conn.execute(
        "SELECT id, owner_principal, box_id, event_kind, event_key, at"
        " FROM push_send_results WHERE outcome = ?"
        " ORDER BY id ASC LIMIT ?",
        (OUTCOME_QUEUED, max_claims)).fetchall()

    for row in rows:
        row_id, owner_principal, box_col, event_kind, event_key, row_at = row
        item = "id=%s %s/%s" % (row_id, event_kind, event_key)
        try:
            _process_one(conn, summary, moment, at, sent_at, item, row_id,
                         owner_principal, box_col, event_kind, event_key,
                         row_at, list_subscriptions, vapid_keys,
                         vapid_subject, record_reader, transport)
        except Exception as exc:  # noqa: BLE001 — the tick survives one bad item
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001 — rollback itself must not kill the tick
                pass
            summary.note("error", "%s (%s: %s)"
                         % (item, type(exc).__name__, exc))
    return summary


def _process_one(conn, summary, moment, at, sent_at, item, row_id,
                 owner_principal, box_col, event_kind, event_key, row_at,
                 list_subscriptions, vapid_keys, vapid_subject,
                 record_reader, transport):
    _require_str("owner_principal", owner_principal)
    if event_kind not in PAGING_EVENT_KINDS:
        raise ValueError("not a paging event kind: %r" % (event_kind,))
    scope, key_material = _split_event_key(event_key)
    # Digest rows store box_id='' (enqueue D51); every other kind stores
    # the real box id, which must equal the key's scope.
    box_id = box_col if box_col else None
    if event_kind == "digest":
        if box_col != "":
            raise ValueError("digest row must carry box_id=''")
        if scope != owner_principal:
            raise ValueError("digest key scope must be the owner")
    elif box_id != scope:
        raise ValueError("row box_id %r != event-key scope %r"
                         % (box_col, scope))
    window_start = _window_start_of(row_at)

    # -- gate-2 (D56d): aid-keyed kinds re-read the approval record --
    record = None
    if event_kind in AID_KEYED_KINDS:
        if record_reader is None:
            raise ValueError(
                "record_reader is required for aid-keyed kinds")
        record = record_reader(box_id, key_material)
        if record is None or record["terminal"]:
            # D80 — a missing record fails safe: a page that cannot prove
            # non-terminal must not page.
            why = ("record missing at send; fail-safe suppress"
                   if record is None else "record terminal at send")
            audit_key = event_key + "\x00" + _AUDIT_SUFFIX
            try:
                _insert_audit_row(conn, at, owner_principal, box_col,
                                  event_kind, audit_key,
                                  "suppressed_terminal")
            except Exception as exc:
                if not _is_integrity_error(exc):
                    raise
                # D69-style race: a sweep's gate-1 audit won. The audit
                # exists — the idempotent outcome — so continue to the
                # DELETE + release below.
            _delete_queued(conn, row_id)
            _terminal_transaction(conn, release=True, box_id=box_id,
                                  owner_principal=owner_principal,
                                  window_start=window_start)
            summary.note("suppressed_terminal", "%s (%s)" % (item, why))
            return

    # -- D79 plaintext --
    digest_count = None
    if event_kind == "digest":
        drow = conn.execute(
            "SELECT count FROM push_digest_state"
            " WHERE owner_principal = ? AND window_start = ?",
            (owner_principal, key_material)).fetchone()
        if drow is None:
            # Corruption (the sweep only enqueues a digest when count > 0):
            # fail-closed, operator-visible, reservation released.
            _insert_audit_row(conn, at, owner_principal, box_col,
                              event_kind, event_key, "dead-letter")
            _delete_queued(conn, row_id)
            _terminal_transaction(conn, release=True, box_id=box_id,
                                  owner_principal=owner_principal,
                                  window_start=window_start)
            summary.note("dead-letter",
                         "%s (digest state row missing)" % item)
            return
        digest_count = drow[0]
    aid, ttl_s, text = _plaintext_for(
        event_kind, key_material=key_material,
        owner_principal=owner_principal, record=record,
        digest_count=digest_count)
    plaintext = serialize_plaintext(
        push_payload.build_push_payload(aid, ttl_s, text))

    # -- D3/D78 fanout --
    subscriptions = list_subscriptions(owner_principal, box_id)
    if not isinstance(subscriptions, list):
        raise ValueError("list_subscriptions must return a list")
    live = []
    for sub in subscriptions:
        if not isinstance(sub, dict):
            raise ValueError("subscription must be a mapping")
        for field in ("owner_principal", "box_id", "device", "endpoint",
                      "p256dh", "auth", "vapid_key_id", "status"):
            if field not in sub:
                raise ValueError(
                    "subscription missing field %r" % (field,))
        if sub["status"] != "live":
            summary.note("skipped_dead_subscription",
                         "%s device=%r status=%r"
                         % (item, sub.get("device"), sub.get("status")))
            continue
        live.append(sub)
    if not live:
        # D81 — parked, not dropped: the row and its reservation stay.
        summary.note("parked", "%s (no live subscriptions)" % item)
        return

    # -- per-device attempts --
    # D56c: the page completes when EVERY live device has a terminal
    # outcome (accepted | tombstone | dead-letter). Deleting the queued
    # row on the first device's terminal outcome would starve the other
    # devices, so terminal rows accumulate per device and the queued
    # row is DELETEed once — when the last device terminates (or when a
    # tick finds them all already terminal, e.g. after a crash between
    # the last attempt row and the DELETE). The D10 reservation resolves
    # then too: released iff no device accepted (D10 bounds successful
    # pages, not attempts — one buzz consumes the page's unit).
    terminal = {}  # device -> terminal outcome, this page
    pending = []
    for sub in live:
        device = sub["device"]
        _require_str("device", device)
        t = _device_terminal_outcome(conn, box_col, event_kind, event_key,
                                     device)
        if t is None:
            pending.append(sub)
        else:
            terminal[device] = t
    if not pending:
        _complete_page(conn, summary, item, row_id, box_id,
                       owner_principal, window_start, terminal,
                       len(live))
        return

    for sub in pending:
        device = sub["device"]
        retry_count, latest_sent_at = _retry_stats(
            conn, box_col, event_kind, event_key, device)
        attempt_no = retry_count + 1
        if attempt_no > MAX_ATTEMPTS:
            # D83 — the retry budget is spent: dead-letter without
            # sending (the D8 reminder already re-paged, or will).
            _insert_audit_row(conn, at, owner_principal, box_col,
                              event_kind, event_key, "dead-letter")
            summary.note("dead-letter",
                         "%s device=%r (retry budget exhausted)"
                         % (item, device))
            terminal[device] = "dead-letter"
            if _maybe_complete(conn, summary, item, row_id, box_id,
                               owner_principal, window_start, terminal,
                               len(live)):
                return
            conn.commit()
            continue
        # D82 — pacing: not due yet.
        if latest_sent_at is not None:
            due_at = latest_sent_at + push_sender.backoff_s(retry_count)
            if sent_at < due_at:
                summary.note("retry_pending",
                             "%s device=%r (due in %.0fs)"
                             % (item, device, due_at - sent_at))
                continue
        vapid_key_id = sub["vapid_key_id"]
        _require_str("vapid_key_id", vapid_key_id)
        keys = vapid_keys(vapid_key_id)
        if (not isinstance(keys, (tuple, list)) or len(keys) != 2
                or not all(isinstance(k, bytes) for k in keys)):
            raise ValueError(
                "vapid_keys must return (private_key, public_key) bytes")
        vapid_private_key, vapid_public_key = keys
        result = push_sender.send_push(
            subscription={"endpoint": sub["endpoint"],
                          "p256dh": sub["p256dh"],
                          "auth": sub["auth"]},
            plaintext=plaintext,
            vapid_private_key=vapid_private_key,
            vapid_public_key=vapid_public_key,
            vapid_subject=vapid_subject,
            ttl_s=ttl_s, attempt=attempt_no, now=sent_at,
            transport=transport)
        summary.attempts += 1
        summary.observe_retry_hint(result.retry_after_s)
        # D56f — the attempt row lands immediately after the POST.
        _insert_attempt_row(conn, at, owner_principal, box_col, device,
                            event_kind, event_key, result, sent_at,
                            vapid_key_id)
        if result.outcome == "accepted":
            summary.note("accepted", "%s device=%r (%s)"
                         % (item, device, result.http_status))
            terminal[device] = "accepted"
            # Contract §1.1: the send path stamps last_page_at.
            conn.execute(
                "UPDATE push_subscriptions SET last_page_at = ?"
                " WHERE owner_principal = ? AND box_id = ? AND device = ?",
                (at, owner_principal, sub["box_id"], device))
            if _maybe_complete(conn, summary, item, row_id, box_id,
                               owner_principal, window_start, terminal,
                               len(live)):
                return
            conn.commit()
            continue
        if result.outcome == "tombstone":
            # The send path marks the subscription dead (D3).
            conn.execute(_TOMBSTONE_SQL,
                         (owner_principal, sub["box_id"], device))
            summary.note("tombstone",
                         "%s device=%r (%s; subscription marked dead_410)"
                         % (item, device, result.http_status))
            terminal[device] = "tombstone"
            if _maybe_complete(conn, summary, item, row_id, box_id,
                               owner_principal, window_start, terminal,
                               len(live)):
                return
            conn.commit()
            continue
        if result.outcome == "dead-letter":
            summary.note("dead-letter",
                         "%s device=%r (%s; operator-visible)"
                         % (item, device, result.http_status))
            terminal[device] = "dead-letter"
            if _maybe_complete(conn, summary, item, row_id, box_id,
                               owner_principal, window_start, terminal,
                               len(live)):
                return
            conn.commit()
            continue
        # "retry": the attempt row is the whole write; the queued row and
        # the reservation stay for the next tick (D82 pacing, D83 budget).
        conn.commit()
        summary.note("retry", "%s device=%r (%s; next in %.0fs)"
                     % (item, device, result.http_status,
                        result.retry_after_s
                        if result.retry_after_s is not None else 0))
