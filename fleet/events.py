#!/usr/bin/env python3
"""Fleet update-event reporting, S1 (issue #779 / G17 / #608).

Design: docs/UPDATE_EVENT_REPORTING.md. S1 is the fleet-side-only slice:
no box-side change, no new port. The canonicalizer translates the
auto-deploy audit lines the G16 S1 collector already pulls
(<estate>/<box>/audit-tail.jsonl) into the standard event shape at
collect time, appends them to the store's event journal with
(box_id, event_id) dedup, and evaluates the four S1 alert rules on
every collect. Alert transport at S1 is the operator's fleet journal
(alerts.jsonl in the store) plus `fleet events watch` exiting nonzero
on unacknowledged alerts.

This module is a deliberate sibling script, not an import of
inventory.py: like every fleet module it is stdlib-only and is exercised
through subprocess by the hermetic suite. The small parsing helpers
(_parse_ts, _read_jsonl_file) mirror inventory.py's; see the module
docstring there for the shared rationale.

Per-box directory layout and the store layout follow inventory.py; this
module adds:
  <store>/events.jsonl   standard-shape events, one per line
  <store>/alerts.jsonl   fired alerts, one per line (acked flags live here)

Key design rules, from the doc (call-site-auditable):
  - Fail-closed on malformed input: box-side audit() interpolates raw
    variables into JSON, so the canonicalizer parses forgivingly and
    records unparseable lines as a collector note, never as events.
  - A gap in the audit tail is missing evidence, never evidence of
    success: the collector never infers noop from silence.
  - Noise discipline: check-noop events stay local-only at S1 (a
    10-minute check cadence x N boxes carries zero fleet signal).
  - Event ids are deterministic (UUIDv5 over
    box_id|ts|event|result|from|to, per-subcomponent suffix on the
    plural-`components` success line), so re-collection is a no-op.
  - Consumers order by (emitted_at, event_id); box clocks are never
    trusted for ordering (received_at is the collect clock).
  - Rule 3 (silent wave) is DISARMED at S1: the rollout envelope is null
    on every event and no max-wait is armed, so a literal reading would
    page every healthy idle estate. The rule exists in code, short-
    circuits, and writes nothing.
"""

import argparse
import contextlib
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

try:
    import fcntl
except ImportError:  # non-Linux platforms; the fleet estate is Linux
    fcntl = None

EVENT_SCHEMA = "fleet-event/1"
ALERT_SCHEMA = "fleet-alert/1"
EVENTS_JOURNAL_NAME = "events.jsonl"
ALERTS_JOURNAL_NAME = "alerts.jsonl"

# Deterministic namespaces for the synthesized ids (UUIDv5). Both are
# derived once from fixed URIs so every collector computes the same ids
# for the same inputs — the property that makes re-collection a no-op.
_EVENT_NS = uuid.uuid5(uuid.NAMESPACE_URL,
                       "https://github.com/ntindle/spark-vm/fleet/events")
_ALERT_NS = uuid.uuid5(uuid.NAMESPACE_URL,
                       "https://github.com/ntindle/spark-vm/fleet/alerts")

# --- Alert-rule tuning (operator-tunable constants, §4) -------------------
# Rule 2: correlated failure window — the "bad release" shape.
_CORRELATED_FAILURE_WINDOW_S = 30 * 60
# Rule 4: stuck precheck — ≥N precheck-fail events on one box inside the
# window. The precheck class (gate-fail, snapshot-fail, retired
# checkout-dirty) emits non-noop events forever, so no other rule catches
# a box stuck failing pre-deployment.
_STUCK_PRECHECK_THRESHOLD = 3
_STUCK_PRECHECK_WINDOW_S = 6 * 3600
# Rule 3: silent-wave max-wait. None = disarmed (S1: every rollout
# envelope is null and no max-wait exists, so the rule cannot fire).
_SILENT_WAVE_MAX_WAIT_S = None

# Outcome vocabulary closed by the design (§2). The S1 producer emits
# only the subset with a legacy producer; started/superseded/deferred-arc/
# skipped-frozen are S2/S3-forward outcomes with no legacy producer.
_KIND_OUTCOME = ("check", "deploy", "rollback")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value):
    """Parse a timestamp to an aware datetime, or None. Mirrors
    inventory.py's helper: accepts ISO-8601 strings and epoch
    int/float, never raises."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value < 0:
            return None
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _read_jsonl_file(path):
    """Read a JSONL file; returns (rows, skipped, error). Mirrors
    inventory.py's helper: malformed lines are counted in skipped,
    never fatal to the rest of the file."""
    rows = []
    skipped = 0
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    skipped += 1
    except FileNotFoundError:
        return None, 0, "missing"
    except OSError as exc:
        return None, 0, "unreadable: %s" % exc
    return rows, skipped, None


# --- Translation table (§3) ----------------------------------------------
# (audit event, audit result) -> (kind, outcome). Verified against the
# actual audit() calls in deploy/auto-deploy.sh. The retired
# checkout-dirty result maps like its siblings — historical audit tails
# may still carry it.
_TRANSLATE = {
    ("check", "noop"): ("check", "noop"),
    ("check", "precheck-fail"): ("check", "precheck-fail"),
    ("deploy", "precheck-fail"): ("deploy", "precheck-fail"),
    ("deploy", "gate-fail"): ("deploy", "precheck-fail"),
    ("deploy", "snapshot-fail"): ("deploy", "precheck-fail"),
    ("deploy", "checkout-dirty"): ("deploy", "precheck-fail"),
    ("deploy", "deploy-fail"): ("deploy", "failed"),
    ("deploy", "reload-fail"): ("deploy", "failed"),
    ("deploy", "rollback-failed"): ("deploy", "rollback-failed"),
    ("deploy", "rolled-back"): ("deploy", "rolled-back"),
    ("deploy", "pull-only"): ("deploy", "succeeded"),
    ("deploy", "ok"): ("deploy", "succeeded"),
    ("rollback", "rollback-failed"): ("rollback", "rollback-failed"),
    ("rollback", "manual-rollback"): ("rollback", "rolled-back"),
    ("rollback", "rollback-unhealthy"): ("rollback", "rolled-back"),
}

# Audit results the S1 producer never turns into journal events. Only
# check/noop: the noise discipline keeps tick-heartbeats local.
_LOCAL_ONLY = {("check", "noop")}


def _clean_text(value):
    """Strip ASCII control characters from a string.

    Audit lines are box-emitted and may carry attacker-influenced bytes
    (audit() interpolates raw variables into JSON). Raw control bytes
    must never reach operator-facing output: a newline in an audit field
    would forge extra lines in cron logs and the alert transport, and
    escape sequences would inject terminal control codes into the CLI
    tables. Tab is kept (it cannot break a line); everything else below
    0x20 plus DEL is dropped. Non-strings pass through unchanged so
    callers can apply it uniformly at synthesis and display.
    """
    if not isinstance(value, str):
        return value
    return "".join(ch for ch in value
                   if ch == "\t" or not (ord(ch) < 0x20 or ord(ch) == 0x7f))


def _str_or_none(value):
    """Coerce a free-form audit field to str-or-None (Engineering B1,
    PR #794: a type-confused-but-valid audit line like `"to":12345`
    would otherwise journal a non-string that crashes alert evaluation
    on every future collect). Mirrors the subcomponent pattern."""
    return value if isinstance(value, str) else None


def _note_for(event, result, line):
    """Synthesize the human/alert note from the audit line itself (§2:
    the box-side alert reason lives in $LAST_FAILURE, which the
    collector does not pull — so the note is a one-line synthesis,
    never a debug dump)."""
    phase = _clean_text(line.get("phase"))
    to = _clean_text(line.get("to"))
    comps = _clean_text(line.get("components") or line.get("component"))
    if result == "precheck-fail":
        base = "pre-deployment gates refused before any mutation"
    elif result == "gate-fail":
        base = "pre-deploy gates refused before any mutation"
    elif result == "snapshot-fail":
        base = "pre-mutation snapshot failed"
    elif result == "checkout-dirty":
        base = ("retired result: the checkout-sync guard aborted the "
                "deploy (historical line)")
    elif result == "deploy-fail":
        base = "deploy failed during %s" % (phase or "unknown phase")
    elif result == "reload-fail":
        base = "daemon reload failed after install; rollback follows"
    elif result == "rollback-failed":
        base = "rollback failed; box may be on a known-bad build"
    elif result == "rolled-back":
        base = "rolled back to %s" % (to or "unknown commit")
    elif result == "pull-only":
        base = "watermark advanced to %s; no components to install" % (
            to or "unknown commit")
    elif result == "ok":
        base = "installed %s; health checks passed" % (
            comps or "unknown components")
    elif result == "manual-rollback":
        base = "operator-initiated rollback to %s" % (to or "unknown")
    elif result == "rollback-unhealthy":
        base = "restored %s but post-restore health failed" % (
            to or "unknown")
    else:
        base = "audit line result=%s" % _clean_text(result)
    if event == "check" and result == "precheck-fail":
        base = "scheduled check: " + base
    return base


def _event_id_for(box_id, ts, event, result, frm, to, subcomponent=None):
    """Deterministic dedup id (§4 S1): UUIDv5 over
    box_id|ts|event|result|from|to, with a per-subcomponent suffix on
    the plural-`components` success line so each fanned event dedups
    independently."""
    key = "|".join([
        str(box_id or ""),
        str(ts if ts is not None else ""),
        str(event or ""),
        str(result or ""),
        str(frm if frm is not None else ""),
        str(to if to is not None else ""),
    ])
    if subcomponent is not None:
        key += "|" + str(subcomponent)
    return str(uuid.uuid5(_EVENT_NS, key))


def _build_event(box_id, received_at, line, kind, outcome,
                 subcomponent=None, subcomponents_verbatim=None):
    """Build one standard-shape event (§2) from an audit line.

    Free-form audit fields are coerced to str-or-None up front: a
    type-confused-but-valid line (e.g. `"to":12345`) would otherwise
    journal a non-string that crashes alert evaluation on every future
    collect (Engineering B1, PR #794)."""
    ts = _str_or_none(line.get("ts"))
    frm = _str_or_none(line.get("from"))
    to = _str_or_none(line.get("to"))
    # manual-rollback's `from` is the commit the operator restored away
    # from (the audit line carries it as rolled_back_from).
    if line.get("event") == "rollback" and line.get("result") == \
            "manual-rollback" and frm is None:
        frm = _str_or_none(line.get("rolled_back_from"))
    trigger = line.get("trigger")
    if trigger not in ("scheduled", "extra-inputs"):
        trigger = "scheduled"
    phase = _str_or_none(line.get("phase"))
    if (line.get("event"), line.get("result")) == ("deploy", "reload-fail"):
        # The reload-fail line carries no component or phase (§3); the
        # phase is synthesized as "reload" — noted in the note, not
        # presented as box-emitted.
        phase = "reload"
    event = {
        "schema": EVENT_SCHEMA,
        "event_id": _event_id_for(box_id, ts, line.get("event"),
                                  line.get("result"), frm, to,
                                  subcomponent),
        "box_id": box_id,
        "session_epoch": None,      # S1: no provisioner box record (OQ3)
        "emitted_at": _clean_text(ts) if isinstance(ts, str) and ts
        else None,
        "received_at": received_at,
        "source": "auto-deploy",
        "component": "repo",
        "subcomponent": _clean_text(_str_or_none(subcomponent)),
        "subcomponents": _clean_text(_str_or_none(subcomponents_verbatim)),
        "kind": kind,
        "outcome": outcome,
        "from": _clean_text(frm) if frm is not None else None,
        "to": _clean_text(to) if to is not None else None,
        "from_version": _clean_text(_str_or_none(line.get("from_version"))),
        "to_version": _clean_text(_str_or_none(line.get("to_version"))),
        "phase": _clean_text(phase) if phase is not None else None,
        "window": None,            # G14 maintenance windows are future
        "rollout": None,           # G15 S2 assigns waves
        "trigger": trigger,
        "attested": False,         # S1/S2: false, always
        "note": _note_for(line.get("event"), line.get("result"), line),
    }
    if (line.get("event"), line.get("result")) == ("deploy", "reload-fail"):
        event["note"] += " (phase synthesized by the collector)"
    return event


def canonicalize_audit_rows(rows, box_id, received_at):
    """Translate audit-tail rows into standard-shape events (§3).

    Returns (events, local_noops, notes). Fail-closed: unparseable
    lines, non-dict lines, and (event, result) pairs with no translation
    are recorded in notes, never emitted as events. check-noop events
    are counted in local_noops and stay local per the noise discipline.
    Never raises for bad input rows.
    """
    events = []
    local_noops = 0
    notes = []
    if rows is None:
        return events, local_noops, notes
    for row in rows:
        if not isinstance(row, dict):
            notes.append("skipped non-object audit line")
            continue
        event, result = row.get("event"), row.get("result")
        if not isinstance(event, str) or not isinstance(result, str):
            notes.append("skipped audit line with non-string event/result")
            continue
        shape = (event, result)
        if shape in _LOCAL_ONLY:
            local_noops += 1
            continue
        translated = _TRANSLATE.get(shape)
        if translated is None:
            notes.append("no translation for audit shape %s/%s; "
                         "kept out of the event journal"
                         % (_clean_text(event), _clean_text(result)))
            continue
        kind, outcome = translated
        if shape == ("deploy", "ok"):
            # Fan-out: one event per component in the plural `components`
            # value; the verbatim plural rides along as `subcomponents`
            # for readers that need the un-fanned form.
            comps_raw = row.get("components")
            if isinstance(comps_raw, str) and comps_raw.split():
                comps = comps_raw.split()
            else:
                notes.append("ok line with empty/non-string components; "
                             "emitted as one un-fanned event")
                comps = [None]
            for comp in comps:
                events.append(_build_event(
                    box_id, received_at, row, kind, outcome,
                    subcomponent=comp,
                    subcomponents_verbatim=comps_raw
                    if isinstance(comps_raw, str) else None))
        else:
            events.append(_build_event(
                box_id, received_at, row, kind, outcome,
                subcomponent=row.get("component")
                if isinstance(row.get("component"), str) else None))
    return events, local_noops, notes


def collect_box_events(box_dir, box_id, received_at):
    """Read one box's audit-tail.jsonl and canonicalize it. Returns
    (events, local_noops, notes); never raises for bad artifacts."""
    rows, skipped, err = _read_jsonl_file(
        os.path.join(box_dir, "audit-tail.jsonl"))
    if err:
        return [], 0, ["audit-tail.jsonl %s" % err]
    events, local_noops, notes = canonicalize_audit_rows(rows, box_id,
                                                         received_at)
    if skipped:
        notes.append("audit tail had %d malformed line(s) skipped" % skipped)
    if local_noops:
        notes.append("%d check-noop event(s) kept local (noise discipline)"
                     % local_noops)
    return events, local_noops, notes


# --- Store-scoped journal lock --------------------------------------------
# append_events / evaluate_alerts / ack_alert each run a load -> dedup ->
# write sequence on the event/alert journals. Two overlapping collects
# (or a collect racing an operator `fleet events ack`) would otherwise
# duplicate event rows, duplicate alert rows, or lose an ack to a
# clobbering os.replace (issue #813). inventory.py's journal path got the
# same class of hardening in #716 (per-process snapshot tmps + stale
# sweep); here the fix is a store-scoped exclusive flock, stdlib-only,
# on the same Linux estate.
#
# Scope: only the journal read-modify-write paths take the lock. Pure
# readers (load_events, load_alerts, the CLI list/watch commands) stay
# unlocked — a reader racing a writer sees whole lines or not (line-
# atomic O_APPEND appends), never a torn JSON object, so unlocked reads
# stay honest. The lock is host-local: it serializes processes on this
# machine only. A multi-host shared store (G26's fleet event stream)
# needs its own design; this claims no cross-host exclusion.
#
# Blocking, not try-lock: an overlapping collect waits its turn rather
# than silently skipping work — the dedup/no-op claims depend on every
# collect seeing every prior collect's rows. flock releases on process
# death, so there is no stale-lock state to sweep (unlike #716's tmp
# files); a crashed holder can only delay, never wedge, the next run.
_JOURNAL_LOCK_NAME = "journal.lock"


class JournalLockError(Exception):
    """The store-scoped journal lock could not be acquired."""


def _ensure_store_dir(store_dir):
    try:
        os.makedirs(store_dir, exist_ok=True)
    except OSError as exc:
        return "cannot create store dir %s: %s" % (store_dir, exc)
    return None


@contextlib.contextmanager
def journal_lock(store_dir):
    """Hold an exclusive flock on <store>/journal.lock.

    Fail-closed: if fcntl is unavailable (non-Linux) or the lock file
    cannot be opened/locked, raise JournalLockError instead of
    proceeding unsynchronized. Callers translate that into their error
    return shape so a collect fails loudly instead of journaling
    duplicates or losing acks.
    """
    if fcntl is None:
        raise JournalLockError(
            "journal lock unavailable: this platform lacks fcntl")
    err = _ensure_store_dir(store_dir)
    if err:
        raise JournalLockError(err)
    lock_path = os.path.join(store_dir, _JOURNAL_LOCK_NAME)
    try:
        fh = open(lock_path, "a", encoding="utf-8")
    except OSError as exc:
        raise JournalLockError(
            "cannot open journal lock %s: %s" % (lock_path, exc))
    with fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            raise JournalLockError("cannot lock journal: %s" % exc)
        try:
            yield
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


# --- Event journal --------------------------------------------------------
def _load_journal(store_dir, name, key_fields):
    """Load a JSONL journal; returns (lines, error). Malformed lines are
    skipped (counted in the caller's domain via len check)."""
    path = os.path.join(store_dir, name)
    lines = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    lines.append(obj)
    except FileNotFoundError:
        return [], None
    except OSError as exc:
        return None, "cannot read %s: %s" % (name, exc)
    return lines, None


def append_events(store_dir, events):
    """Append events to the store's event journal with (box_id,
    event_id) dedup (§4 S1): a re-pulled tail re-canonicalizes to
    identical ids, so double-collection is a no-op. Returns
    (appended, duplicates, error).

    The load -> dedup -> append sequence runs under the store-scoped
    journal lock: two overlapping collects both seeing a missing id and
    both appending it would break the no-op claim with duplicate rows.
    """
    try:
        with journal_lock(store_dir):
            existing, err = _load_journal(store_dir, EVENTS_JOURNAL_NAME,
                                         None)
            if err:
                return None, None, err
            seen = {(e.get("box_id"), e.get("event_id"))
                    for e in existing
                    if isinstance(e.get("box_id"), str)
                    and isinstance(e.get("event_id"), str)}
            fresh = [e for e in events
                     if (e.get("box_id"), e.get("event_id")) not in seen]
            journal_path = os.path.join(store_dir, EVENTS_JOURNAL_NAME)
            try:
                with open(journal_path, "a", encoding="utf-8",
                          buffering=1) as fh:
                    for event in fresh:
                        fh.write(json.dumps(event, sort_keys=True) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
            except OSError as exc:
                return None, None, "cannot append to event journal: %s" \
                    % exc
    except JournalLockError as exc:
        return None, None, str(exc)
    return len(fresh), len(events) - len(fresh), None


def load_events(store_dir):
    """Returns (events, error)."""
    return _load_journal(store_dir, EVENTS_JOURNAL_NAME, None)


# --- Alert rules (§4 S1) ----------------------------------------------------
def _alert(rule, fired_at, detail, box_id=None, subcomponent=None,
           to=None, dedup_key=""):
    alert_id = str(uuid.uuid5(
        _ALERT_NS, "|".join([rule, str(box_id or ""), str(subcomponent or ""),
                             str(to or ""), str(dedup_key)])))
    return {
        "schema": ALERT_SCHEMA,
        "alert_id": alert_id,
        "rule": rule,
        "fired_at": fired_at,
        # Alert fields ride the S1 alert transport (cron logs, paging):
        # control chars are stripped at synthesis so a crafted audit line
        # can never forge an alert row.
        "box_id": _clean_text(box_id),
        "subcomponent": _clean_text(subcomponent),
        "to": _clean_text(to),
        "detail": _clean_text(detail),
        "acked": False,
    }


def _rule_rollback_failed(events, fired_at):
    """Rule 1: any rollback-failed -> immediate alert (a box stuck on a
    known-bad build). One alert per rollback-failed event."""
    alerts = []
    for e in events:
        if e.get("outcome") == "rollback-failed":
            alerts.append(_alert(
                "rollback-failed", fired_at,
                "box %s reported %s/%s (%s)" % (
                    e.get("box_id"), e.get("kind"), e.get("outcome"),
                    e.get("note") or "no note"),
                box_id=e.get("box_id"),
                subcomponent=e.get("subcomponent"),
                to=e.get("to"),
                dedup_key=e.get("event_id") or ""))
    return alerts


def _rule_correlated_failure(events, fired_at):
    """Rule 2: >=2 boxes reporting failed/rolled-back for the same
    (subcomponent, to) within a 30-minute window -> fleet alert (the
    bad-release shape). Lines that carry no component correlate on (to)
    alone, labeled subcomponent: unknown."""
    groups = {}
    for e in events:
        if e.get("outcome") not in ("failed", "rolled-back"):
            continue
        ts = _parse_ts(e.get("emitted_at"))
        if ts is None:
            continue  # cannot place it in time; excluded from windows
        key = (e.get("subcomponent") or "unknown", e.get("to") or "")
        groups.setdefault(key, []).append((ts, e))
    alerts = []
    for (subcomp, to), members in groups.items():
        members.sort(key=lambda m: m[0])
        # Sliding 30-minute window: any window covering >=2 distinct
        # boxes fires. The anchor is the window's earliest event, so a
        # genuinely new cluster (new anchor) re-fires while the same
        # cluster dedups.
        n = len(members)
        for i in range(n):
            window_boxes = {members[i][1].get("box_id")}
            anchor = members[i][0]
            for j in range(i + 1, n):
                if (members[j][0] - anchor).total_seconds() > \
                        _CORRELATED_FAILURE_WINDOW_S:
                    break
                window_boxes.add(members[j][1].get("box_id"))
            if len(window_boxes) >= 2:
                boxes = sorted(b for b in window_boxes if b)
                alerts.append(_alert(
                    "correlated-failure", fired_at,
                    "%d boxes failed/rolled-back on (%s, to=%s) within "
                    "30 min: %s" % (len(boxes), subcomp,
                                    str(to)[:12] if to else "(no to)",
                                    ", ".join(boxes)),
                    subcomponent=subcomp,
                    to=to or None,
                    dedup_key=anchor.isoformat()))
                break  # one alert per (subcomponent, to) cluster
    return alerts


def _rule_silent_wave(events, fired_at):
    """Rule 3: boxes with a non-null rollout envelope and zero non-noop
    events over the armed max-wait window -> operator alert. DISARMED at
    S1 (_SILENT_WAVE_MAX_WAIT_S is None): every envelope is null, so a
    literal reading would page every healthy idle estate. Short-circuits
    and writes nothing."""
    if _SILENT_WAVE_MAX_WAIT_S is None:
        return []
    cutoff = _parse_ts(fired_at)
    if cutoff is None:
        return []
    cutoff = cutoff - timedelta(seconds=_SILENT_WAVE_MAX_WAIT_S)
    by_box = {}
    for e in events:
        rollout = e.get("rollout")
        if not isinstance(rollout, dict):
            continue
        by_box.setdefault(e.get("box_id"), []).append(e)
    alerts = []
    for box_id, box_events in by_box.items():
        recent = [e for e in box_events
                  if e.get("outcome") != "noop"
                  and (_parse_ts(e.get("emitted_at")) or cutoff) >= cutoff]
        if not recent:
            alerts.append(_alert(
                "silent-wave", fired_at,
                "box %s has a rollout envelope but zero non-noop events "
                "in the armed window" % box_id,
                box_id=box_id,
                dedup_key=cutoff.isoformat()))
    return alerts


def _rule_stuck_precheck(events, fired_at):
    """Rule 4: >=N precheck-fail events on one box inside the window ->
    operator alert (a perpetually un-updated box no other rule catches).
    The anchor is the window's earliest qualifying event, so a
    persistent condition re-fires only when the window's anchor moves."""
    cutoff = _parse_ts(fired_at)
    if cutoff is None:
        return []
    cutoff = cutoff - timedelta(seconds=_STUCK_PRECHECK_WINDOW_S)
    by_box = {}
    for e in events:
        if e.get("outcome") != "precheck-fail":
            continue
        ts = _parse_ts(e.get("emitted_at"))
        if ts is None or ts < cutoff:
            continue
        by_box.setdefault(e.get("box_id"), []).append(ts)
    alerts = []
    for box_id, stamps in by_box.items():
        if len(stamps) >= _STUCK_PRECHECK_THRESHOLD:
            anchor = min(stamps)
            alerts.append(_alert(
                "stuck-precheck", fired_at,
                "box %s reported %d precheck-fail events in the last %dh" %
                (box_id, len(stamps),
                 _STUCK_PRECHECK_WINDOW_S // 3600),
                box_id=box_id,
                dedup_key=anchor.isoformat()))
    return alerts


def evaluate_alerts(store_dir, fired_at=None):
    """Run the four S1 alert rules over the store's event journal and
    append newly fired alerts (deduped on alert_id — re-firing an
    already-journaled alert, acked or not, is a no-op). Returns
    (fired_alerts, error).

    Rule evaluation reads the event journal unlocked (a snapshot is
    fine — rules reason about what was true when they ran); the
    load-alerts -> dedup -> append sequence runs under the store-scoped
    journal lock so two overlapping evaluators cannot append the same
    alert twice. The store dir is created when any rule fires (the lock
    needs a home), even if every candidate then dedups.
    """
    fired_at = fired_at or _now_iso()
    events, err = load_events(store_dir)
    if err:
        return None, err
    candidates = []
    candidates.extend(_rule_rollback_failed(events, fired_at))
    candidates.extend(_rule_correlated_failure(events, fired_at))
    candidates.extend(_rule_silent_wave(events, fired_at))
    candidates.extend(_rule_stuck_precheck(events, fired_at))
    if not candidates:
        return [], None
    try:
        with journal_lock(store_dir):
            existing, err = _load_journal(store_dir, ALERTS_JOURNAL_NAME,
                                          None)
            if err:
                return None, err
            seen = {a.get("alert_id") for a in existing
                    if isinstance(a.get("alert_id"), str)}
            fresh = [a for a in candidates if a["alert_id"] not in seen]
            if fresh:
                alerts_path = os.path.join(store_dir, ALERTS_JOURNAL_NAME)
                try:
                    with open(alerts_path, "a", encoding="utf-8",
                              buffering=1) as fh:
                        for alert in fresh:
                            fh.write(json.dumps(alert, sort_keys=True)
                                     + "\n")
                        fh.flush()
                        os.fsync(fh.fileno())
                except OSError as exc:
                    return None, "cannot append to alert journal: %s" % exc
    except JournalLockError as exc:
        return None, str(exc)
    return fresh, None


def load_alerts(store_dir):
    """Returns (alerts, error)."""
    return _load_journal(store_dir, ALERTS_JOURNAL_NAME, None)


def ack_alert(store_dir, alert_id):
    """Mark an alert acknowledged. Returns (found, error): the alert
    journal is rewritten atomically (tmp + os.replace) so a crash never
    tears it.

    The load -> rewrite sequence runs under the store-scoped journal
    lock: two concurrent acks would otherwise both load the same rows
    and the second os.replace would clobber the first's ack. A missing
    store dir short-circuits to (False, None) without creating it; a
    store path that exists but is not a directory fails loudly.
    """
    if os.path.lexists(store_dir) and not os.path.isdir(store_dir):
        return None, "store path is not a directory: %s" % store_dir
    if not os.path.isdir(store_dir):
        return False, None
    try:
        with journal_lock(store_dir):
            alerts, err = load_alerts(store_dir)
            if err:
                return None, err
            found = False
            for alert in alerts:
                if alert.get("alert_id") == alert_id:
                    alert["acked"] = True
                    found = True
            if not found:
                return False, None
            err = rewrite_journal_atomic(
                os.path.join(store_dir, ALERTS_JOURNAL_NAME),
                [json.dumps(alert, sort_keys=True) for alert in alerts])
            if err:
                return None, err
    except JournalLockError as exc:
        return None, str(exc)
    return True, None


# --- Journal retention (§4 S2) -------------------------------------------------
# The event journal keeps 90 days of per-event records per box; records
# older than 30 days are compacted into per-day outcome histograms keyed
# (box, component, build); records older than 90 days are dropped. Age
# is measured on emitted_at (when the event happened), never on
# received_at (when the collector saw it): a late-collected event is as
# old as it is, and box clocks are never trusted for ordering either
# (§2). Rows whose emitted_at is missing, unparseable, or in the future
# are kept and counted — prune never drops what it cannot date, and
# never prunes the future.
#
# Compaction lands in <store>/events_histograms.jsonl, a separate file
# so the raw journal's readers (list, watch, crosscheck) never see
# histogram rows. Histogram buckets merge across prunes: two prunes
# folding different raw rows from the same (day, box_id, component,
# build) bucket add to its counts rather than appending a second bucket.
# Non-string outcomes (None for precheck-fail rows) fold under the
# "unknown" sentinel, because raw None keys would crash the next merge
# and JSON coerces them to "null" anyway. Only rows carrying our schema
# are merged; verbatim (blank/malformed) and foreign-schema histogram
# lines pass through byte-identical. Only buckets that gain counts in a
# fold are re-stamped folded_at; carried buckets keep their own, and a
# drop-only prune leaves the histograms file byte-identical.
# Build is the target build the event is about: the `to` commit, else
# `to_version`, else null (precheck-fail rows may name no target — the
# bucket keeps the null honestly rather than inventing one). Day is the
# UTC calendar day of emitted_at.
#
# Bands (age A vs the prune's now):
#   A < 30d          raw rows kept
#   30d <= A < 90d   folded into histograms; raw rows dropped
#   A >= 90d         raw rows dropped (outside the retention window)
# The exact-boundary behavior is pinned by tests. Rows with a missing
# or unparseable emitted_at are kept and counted as skipped_undatable;
# future-dated rows are kept (never prune the future) and counted as
# kept. Malformed journal lines are preserved verbatim and counted in
# neither bucket.
#
# Alerts: prune drops only acknowledged alerts whose fired_at is >= 90d
# old. Unacknowledged alerts are NEVER dropped — a prune that silently
# deletes pending pages is a lie. Acked alerts with missing/
# unparseable/future fired_at are kept.
#
# Both journals are rewritten atomically (tmp sibling + fsync +
# os.replace) under the store-scoped journal lock; files whose content
# would not change are left untouched (byte-identical, mtime preserved)
# so a no-op prune is observable as one. Commit order inside a folding
# prune is journal-first, histograms-second: a journal-rewrite failure
# leaves nothing folded (a retry is clean), and a histogram-rewrite
# failure after a successful journal rewrite returns a LOUD error —
# the fold is lost in that window (under-count, never re-folded),
# which beats the silent double-count the reverse order produced.
HISTOGRAM_SCHEMA = "fleet-event-histogram/1"
HISTOGRAMS_JOURNAL_NAME = "events_histograms.jsonl"
RETENTION_RAW_DAYS = 30
RETENTION_HISTOGRAM_DAYS = 90


def rewrite_journal_atomic(path, row_texts):
    """Replace the file at path with row_texts (each a full line; the
    writer newline-terminates any line missing its "\n") atomically:
    tmp sibling on the same fs, fsync, os.replace. Returns an error
    string or None. A crash leaves the old file or the tmp behind,
    never a torn journal."""
    tmp_path = path + ".tmp.%d" % os.getpid()
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            for text in row_texts:
                fh.write(text if text.endswith("\n") else text + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return "cannot rewrite %s: %s" % (os.path.basename(path), exc)
    return None


def read_journal_raw(path):
    """Read a JSONL journal as raw lines. Returns (items, error) where
    each item is (text, obj, verbatim): text is the line without its
    trailing newline, obj the parsed dict, verbatim True for blank
    lines and malformed/non-dict lines. Callers that rewrite must keep
    verbatim items byte-identical — they cannot be dated, so they
    cannot be pruned; they are never counted or banded."""
    items = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                text = line.rstrip("\n")
                if not text.strip():
                    items.append((text, None, True))
                    continue
                try:
                    obj = json.loads(text)
                except ValueError:
                    obj = None
                if not isinstance(obj, dict):
                    items.append((text, None, True))
                    continue
                items.append((text, obj, False))
    except FileNotFoundError:
        return [], None
    except OSError as exc:
        return None, "cannot read %s: %s" % (os.path.basename(path), exc)
    return items, None


def _retention_band(emitted_dt, now):
    """The retention band for one event time: "keep", "compact", or
    "drop". Undatable (None) and future times return "keep": prune never
    drops what it cannot date and never prunes the future."""
    if emitted_dt is None or emitted_dt > now:
        return "keep"
    if emitted_dt > now - timedelta(days=RETENTION_RAW_DAYS):
        return "keep"
    if emitted_dt > now - timedelta(days=RETENTION_HISTOGRAM_DAYS):
        return "compact"
    return "drop"


def _histogram_key(event):
    """The (day, box_id, component, build) bucket for one event. Day is
    the UTC calendar day of emitted_at; the caller guarantees a
    parseable, non-future emitted_at."""
    day = _parse_ts(event.get("emitted_at")).astimezone(
        timezone.utc).date().isoformat()
    to = event.get("to")
    build = to if isinstance(to, str) else None
    if build is None:
        ver = event.get("to_version")
        build = ver if isinstance(ver, str) else None
    return (day, event.get("box_id"), event.get("component"), build)


def _histogram_outcome_key(outcome):
    """The counts key for one event outcome. Outcomes are keyed by
    string; a non-string outcome (None for precheck-fail rows, or
    anything else hand-fed) folds under the "unknown" sentinel. Raw
    None keys are forbidden: dict(sorted(...)) raises TypeError
    comparing None with str on the next prune's merge, and JSON would
    coerce the key to the string "null" anyway — a collision, not a
    category."""
    return outcome if isinstance(outcome, str) else "unknown"


def _fold_histograms(existing, events_to_fold, folded_at):
    """Merge existing histogram rows with newly compacted events.
    Returns the full bucket list sorted by
    (day, box_id, component, build) for a deterministic file layout.

    Only rows carrying our schema are merged — foreign-schema rows are
    not understood and must never be absorbed (the caller passes them
    through byte-identical). Non-string outcomes fold under "unknown"
    (see _histogram_outcome_key). Only buckets that gained counts in
    this fold are stamped folded_at=now; carried buckets keep their own
    folded_at so an unrelated prune never rewrites their evidence."""
    buckets = {}

    def _acc(key):
        return buckets.setdefault(
            key, {"counts": {}, "folded_at": None, "touched": False})

    for row in existing:
        if not isinstance(row, dict) or row.get("schema") != HISTOGRAM_SCHEMA:
            continue
        key = (row.get("day"), row.get("box_id"), row.get("component"),
               row.get("build"))
        counts = row.get("counts")
        if not isinstance(counts, dict):
            counts = {}
        acc = _acc(key)
        if acc["folded_at"] is None:
            acc["folded_at"] = row.get("folded_at")
        for outcome, n in counts.items():
            if isinstance(n, int) and n > 0:
                okey = _histogram_outcome_key(outcome)
                acc["counts"][okey] = acc["counts"].get(okey, 0) + n
    for event in events_to_fold:
        key = _histogram_key(event)
        acc = _acc(key)
        okey = _histogram_outcome_key(event.get("outcome"))
        acc["counts"][okey] = acc["counts"].get(okey, 0) + 1
        acc["touched"] = True
        acc["folded_at"] = folded_at
    rows = []
    for (day, box_id, component, build), acc in sorted(
            buckets.items(), key=lambda kv: tuple(
                "" if v is None else str(v) for v in kv[0])):
        rows.append({
            "schema": HISTOGRAM_SCHEMA,
            "day": day,
            "box_id": box_id,
            "component": component,
            "build": build,
            "counts": dict(sorted(acc["counts"].items())),
            "folded_at": acc["folded_at"],
        })
    return rows


def _count_histogram_buckets(hist_items):
    """Count our-schema histogram bucket rows among raw journal items
    (verbatim, foreign-schema, and non-dict lines are not buckets)."""
    return sum(
        1 for _, obj, verb in hist_items
        if (obj and not verb and isinstance(obj, dict)
            and obj.get("schema") == HISTOGRAM_SCHEMA))


def prune_events(store_dir, now=None):
    """Apply the §4 S2 retention policy to the event + alert journals.
    Returns (summary, error); summary is a dict with kept / compacted /
    dropped / skipped_undatable (event rows), histogram_buckets (total
    buckets after the fold), and alerts_dropped / alerts_kept.

    The whole prune runs under the store-scoped journal lock: the
    load -> rewrite sequences would otherwise race an overlapping
    collect's appends or acks (the same class #813 closed). `now`
    defaults to the current UTC time and exists so tests pin the
    banding deterministically.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    folded_at = now.isoformat()
    try:
        with journal_lock(store_dir):
            items, err = read_journal_raw(
                os.path.join(store_dir, EVENTS_JOURNAL_NAME))
            if err:
                return None, err
            kept_texts = []
            to_fold = []
            summary = {"kept": 0, "compacted": 0, "dropped": 0,
                       "skipped_undatable": 0, "histogram_buckets": 0,
                       "alerts_dropped": 0, "alerts_kept": 0}
            for text, obj, verbatim in items:
                if verbatim:
                    kept_texts.append(text)
                    continue
                emitted = _parse_ts(obj.get("emitted_at"))
                if emitted is None:
                    kept_texts.append(text)
                    summary["skipped_undatable"] += 1
                    continue
                band = _retention_band(emitted, now)
                if band == "keep":
                    kept_texts.append(text)
                    summary["kept"] += 1
                elif band == "compact":
                    to_fold.append(obj)
                    summary["compacted"] += 1
                else:
                    summary["dropped"] += 1
            if to_fold:
                # The journal is rewritten FIRST (before the histogram
                # fold). If the journal rewrite raises, nothing has been
                # folded and a retry is clean. If instead the histogram
                # rewrite fails after the journal was rewritten, the
                # error is returned LOUDLY: the folded rows are already
                # gone from the journal, so the fold is lost in that
                # window — a loud under-count a retry cannot heal, and
                # that beats the silent double-count the old
                # histogram-first order produced.
                err = rewrite_journal_atomic(
                    os.path.join(store_dir, EVENTS_JOURNAL_NAME),
                    kept_texts)
                if err:
                    return None, err
                hist_items, err = read_journal_raw(
                    os.path.join(store_dir, HISTOGRAMS_JOURNAL_NAME))
                if err:
                    return None, err
                existing = []
                passthrough = []
                for text, obj, verb in hist_items:
                    # Verbatim lines (blank/malformed) and foreign-schema
                    # rows are not understood — they pass through
                    # byte-identical after the bucket rows, never
                    # absorbed into a fold.
                    if (verb or not isinstance(obj, dict)
                            or obj.get("schema") != HISTOGRAM_SCHEMA):
                        passthrough.append(text)
                    else:
                        existing.append(obj)
                buckets = _fold_histograms(existing, to_fold, folded_at)
                summary["histogram_buckets"] = len(buckets)
                hist_rows = [json.dumps(b, sort_keys=True)
                             for b in buckets] + passthrough
                err = rewrite_journal_atomic(
                    os.path.join(store_dir, HISTOGRAMS_JOURNAL_NAME),
                    hist_rows)
                if err:
                    return None, (
                        "cannot rewrite %s: %s (the %d compacted row(s) "
                        "were already dropped from the event journal; "
                        "the fold is lost — a loud under-count, never "
                        "re-folded)"
                        % (HISTOGRAMS_JOURNAL_NAME, err,
                           summary["compacted"]))
            elif summary["dropped"]:
                # Drop-only prune: nothing was folded, so the histograms
                # file is left byte-identical (mtime preserved) — a
                # prune that folds nothing must not rewrite it.
                err = rewrite_journal_atomic(
                    os.path.join(store_dir, EVENTS_JOURNAL_NAME),
                    kept_texts)
                if err:
                    return None, err
                hist_items, err = read_journal_raw(
                    os.path.join(store_dir, HISTOGRAMS_JOURNAL_NAME))
                if err:
                    return None, err
                summary["histogram_buckets"] = \
                    _count_histogram_buckets(hist_items)
            else:
                hist_items, err = read_journal_raw(
                    os.path.join(store_dir, HISTOGRAMS_JOURNAL_NAME))
                if err:
                    return None, err
                summary["histogram_buckets"] = \
                    _count_histogram_buckets(hist_items)
            alert_items, err = read_journal_raw(
                os.path.join(store_dir, ALERTS_JOURNAL_NAME))
            if err:
                return None, err
            alert_cutoff = now - timedelta(days=RETENTION_HISTOGRAM_DAYS)
            kept_alerts = []
            drop_alerts = False
            for text, obj, verbatim in alert_items:
                fired = _parse_ts(obj.get("fired_at")) \
                    if obj and not verbatim else None
                if (obj and not verbatim and obj.get("acked") is True
                        and fired is not None and fired <= alert_cutoff):
                    summary["alerts_dropped"] += 1
                    drop_alerts = True
                else:
                    kept_alerts.append(text)
                    summary["alerts_kept"] += 1
            if drop_alerts:
                err = rewrite_journal_atomic(
                    os.path.join(store_dir, ALERTS_JOURNAL_NAME),
                    kept_alerts)
                if err:
                    return None, err
    except JournalLockError as exc:
        return None, str(exc)
    return summary, None


def cmd_events_prune(store_dir):
    """Prune the event journal per the §4 S2 retention policy; prints a
    one-line summary. Returns an error string or None (exit-2 class)."""
    if os.path.lexists(store_dir) and not os.path.isdir(store_dir):
        return "store path is not a directory: %s" % store_dir
    if not os.path.isdir(store_dir):
        return "store not found: %s" % store_dir
    summary, err = prune_events(store_dir)
    if err:
        return err
    print("fleet events: pruned %d event row(s) (%d compacted into "
          "%d histogram bucket(s), %d dropped at 90+ days); "
          "%d kept, %d undatable kept; %d acked alert(s) older than "
          "%d days dropped, %d alert(s) kept"
          % (summary["compacted"] + summary["dropped"],
             summary["compacted"],
             summary["histogram_buckets"], summary["dropped"],
             summary["kept"], summary["skipped_undatable"],
             summary["alerts_dropped"], RETENTION_HISTOGRAM_DAYS,
             summary["alerts_kept"]))
    return None


# --- CLI readers (called from inventory.py's `events` subcommand) ---------
def _short(value, width=12):
    if not value:
        return "-"
    # Display path: never emit control characters into the operator's
    # terminal, even from a journal written by an older build.
    return _clean_text(str(value))[:width]


def _sort_key(event):
    # Consumers order by (emitted_at, event_id) (§2); box clocks are
    # never trusted for ordering, and the dedup id is the tiebreak that
    # keeps re-collection from reordering history.
    return (str(event.get("emitted_at") or ""),
            str(event.get("event_id") or ""))


def cmd_events_list(store_dir, box_id, wave):
    events, err = load_events(store_dir)
    if err:
        return err
    if box_id:
        events = [e for e in events if e.get("box_id") == box_id]
    if wave:
        events = [e for e in events
                  if isinstance(e.get("rollout"), dict)
                  and e["rollout"].get("wave") == wave]
    events.sort(key=_sort_key)
    if box_id and not events:
        return "box %s has no events in the journal" % box_id

    if box_id:
        lines = ["update events for box %s (%d events, oldest first):"
                 % (box_id, len(events))]
        fmt = "  %-20s %-8s %-13s %-16s %-25s %s"
        lines.append(fmt % ("emitted_at", "kind", "outcome", "subcomponent",
                            "from->to", "note"))
        for e in events:
            frm, to = _short(e.get("from")), _short(e.get("to"))
            lines.append(fmt % (
                _clean_text((_str_or_none(e.get("emitted_at")) or "?")[:19]),
                e.get("kind") or "?", e.get("outcome") or "?",
                _short(e.get("subcomponent"), 16) or "-",
                "%s->%s" % (frm, to),
                _clean_text((_str_or_none(e.get("note")) or "")[:60])))
    else:
        # Per-box outcome series.
        by_box = {}
        for e in events:
            by_box.setdefault(e.get("box_id"), []).append(e)
        lines = ["fleet update events (%d events, %d boxes):"
                 % (len(events), len(by_box))]
        fmt = "  %-24s %6s  %-13s %-20s %s"
        lines.append(fmt % ("box", "events", "last outcome",
                            "last emitted_at", "last note"))
        for bid in sorted(by_box, key=str):
            series = sorted(by_box[bid], key=_sort_key)
            last = series[-1]
            outcomes = {}
            for e in series:
                outcomes[e.get("outcome")] = \
                    outcomes.get(e.get("outcome"), 0) + 1
            summary = ",".join("%s=%d" % (o, c)
                               for o, c in sorted(outcomes.items(),
                                                  key=lambda kv: str(kv[0])))
            lines.append(fmt % (
                _clean_text(str(bid))[:24], len(series),
                str(last.get("outcome"))[:13],
                _clean_text((_str_or_none(last.get("emitted_at")) or "?")[:19]),
                _clean_text("%s (%s)" % (summary, (_str_or_none(
                    last.get("note")) or "")[:40]))))
    print("\n".join(lines))
    return None


def cmd_events_watch(store_dir):
    """Exit 1 with the unacknowledged alerts listed, 0 when the queue
    is clear — the S1 alert transport a cron or the operator's existing
    paging consumes."""
    alerts, err = load_alerts(store_dir)
    if err:
        return err, 0
    pending = [a for a in alerts if not a.get("acked")]
    if not pending:
        print("no unacknowledged alerts")
        return None, 0
    lines = ["UNACKNOWLEDGED ALERTS (%d):" % len(pending)]
    for a in sorted(pending, key=lambda x: str(x.get("fired_at") or "")):
        lines.append("  [%s] box=%s subcomponent=%s to=%s fired=%s" % (
            _clean_text(a.get("rule")), _clean_text(a.get("box_id")) or "-",
            _clean_text(a.get("subcomponent")) or "-",
            _short(a.get("to")),
            _clean_text((_str_or_none(a.get("fired_at")) or "?")[:19])))
        lines.append("      %s" % _clean_text(a.get("detail") or ""))
        lines.append("      alert_id=%s (fleet events ack --alert-id <id>)"
                     % _clean_text(a.get("alert_id")))
    print("\n".join(lines))
    return None, 1


def cmd_events_ack(store_dir, alert_id):
    found, err = ack_alert(store_dir, alert_id)
    if err:
        return err
    if not found:
        return "no alert with id %s" % _clean_text(alert_id)
    print("acknowledged %s" % _clean_text(alert_id))
    return None


# --- Event<->inventory cross-check (G17 S2, #779) ---------------------------
#
# The fleet-side half of the design's claim-vs-ground-truth rule
# (docs/UPDATE_EVENT_REPORTING.md §2): a `deploy/succeeded/repo` event is a
# *claim* about what is running ("to=X"); the inventory journal is ground
# truth (point-in-time reads). For each claim the cross-check finds
# inventory records for the same box observed at-or-after the claim's
# `received_at` — collector clocks on both sides, because box clocks are
# never trusted for ordering:
#   - any later record showing the claimed commit  -> confirmed;
#   - later records exist but none shows the claim -> VIOLATION (flagged,
#     not convicted: the inventory wins the tie, the event keeps its
#     journal row, nothing is marked suspect automatically);
#   - no later record, or later records report no commit -> inconclusive
#     (missing evidence is never a violation).
#
# Read-only: this consumes the store's two journals and prints a report.
# Only `deploy/succeeded/repo` claims are checkable at this slice — the
# doc defines only `succeeded` as a claim (rolled-back/restored claims are
# a follow-up), and the toolset/image components have no S1 producers.
# The journals are trusted append-only input: (box_id, event_id) dedup
# happens at collect time (append_events), not here — a corrupted journal
# with duplicate claim rows double-counts, honestly.

# inventory.py's journal file, read here for the ground-truth side.
_INVENTORY_JOURNAL_NAME = "journal.jsonl"

_VERDICT_CONFIRMED = "confirmed"
_VERDICT_VIOLATION = "violation"
_VERDICT_INCONCLUSIVE = "inconclusive"


def _is_checkable_claim(event):
    return (isinstance(event, dict)
            and event.get("kind") == "deploy"
            and event.get("outcome") == "succeeded"
            and event.get("component") == "repo")


def _inventory_commits_by_box(store_dir):
    """Load the inventory journal's per-box (observed_at, repo_commit)
    series. Returns (dict, error). Malformed lines are skipped by the
    journal loader; records with unparseable observed_at are kept with
    observed_at=None (they can never confirm or contradict — see
    crosscheck_events). Never raises."""
    rows, err = _load_journal(store_dir, _INVENTORY_JOURNAL_NAME, None)
    if err:
        return None, err
    by_box = {}
    for row in rows:
        box_id = row.get("box_id")
        if not isinstance(box_id, str) or not box_id:
            continue
        commit = None
        versions = row.get("versions")
        if isinstance(versions, dict):
            candidate = versions.get("repo_commit")
            if isinstance(candidate, str) and candidate:
                commit = candidate
        by_box.setdefault(box_id, []).append(
            (_parse_ts(row.get("observed_at")), commit))
    return by_box, None


def crosscheck_events(events, commits_by_box):
    """Evaluate every checkable claim against the inventory series.

    Returns (rows, counts). Each row is a dict {box_id, event_id,
    received_at, claim_to, verdict, detail}; verdict is one of
    "confirmed", "violation", "inconclusive". Never raises for bad
    *event* input (commits_by_box must be a dict); non-claim events are
    ignored."""
    rows = []
    counts = {_VERDICT_CONFIRMED: 0, _VERDICT_VIOLATION: 0,
              _VERDICT_INCONCLUSIVE: 0}
    if not isinstance(events, list):
        return rows, counts
    for event in events:
        if not _is_checkable_claim(event):
            continue
        box_id = event.get("box_id")
        to = event.get("to")
        event_id = event.get("event_id")
        received_at = event.get("received_at")
        if not isinstance(event_id, str):
            event_id = None
        row = {"box_id": box_id, "event_id": event_id,
               "received_at": received_at,
               "claim_to": to if isinstance(to, str) else None,
               "verdict": None, "detail": ""}
        if not isinstance(box_id, str) or not box_id:
            row["verdict"] = _VERDICT_INCONCLUSIVE
            row["detail"] = ("claim is unattributable (no box_id) — "
                             "cannot be checked")
        elif not isinstance(to, str) or not to:
            row["verdict"] = _VERDICT_INCONCLUSIVE
            row["detail"] = "claim carries no to version — nothing to check"
        else:
            received = _parse_ts(received_at)
            if received is None:
                row["verdict"] = _VERDICT_INCONCLUSIVE
                row["detail"] = ("claim has no parseable received_at — "
                                 "cannot be ordered against inventory")
            else:
                series = commits_by_box.get(box_id, [])
                later = [(obs, commit) for (obs, commit) in series
                         if obs is not None and obs >= received]
                observed = [commit for (_, commit) in later
                            if commit is not None]
                if not later:
                    row["verdict"] = _VERDICT_INCONCLUSIVE
                    row["detail"] = ("no inventory observation at-or-after "
                                     "the claim — missing evidence, not a "
                                     "contradiction")
                elif not observed:
                    row["verdict"] = _VERDICT_INCONCLUSIVE
                    row["detail"] = ("later observations report no commit "
                                     "(not reported, never 'unknown') — "
                                     "missing evidence, not a contradiction")
                elif any(commit == to for commit in observed):
                    row["verdict"] = _VERDICT_CONFIRMED
                    row["detail"] = ("inventory shows the claimed commit "
                                     "in a later observation")
                else:
                    latest = max(later, key=lambda pair: pair[0])
                    shown = latest[1] if latest[1] else \
                        "(no commit reported)"
                    row["verdict"] = _VERDICT_VIOLATION
                    row["detail"] = ("claimed succeeded-to=%s but no later "
                                     "inventory shows it; latest observation "
                                     "at %s shows %s — flagged, not "
                                     "convicted" % (_short(to),
                                                    latest[0].isoformat(),
                                                    _short(shown)))
        rows.append(row)
        counts[row["verdict"]] += 1
    rows.sort(key=lambda r: (str(r["box_id"]),
                             str(r["received_at"] or "")))
    return rows, counts


def cmd_events_crosscheck(store_dir, box_id):
    """Print the claim-vs-inventory verdict series for the store's event
    journal. Exit 1 iff any claim is a violation (cron-consumable, like
    `events watch`); 0 when clean or inconclusive-only. Returns
    (error, exit_code)."""
    if not os.path.isdir(store_dir):
        return "store directory %r not found" % (store_dir,), 2
    events, err = load_events(store_dir)
    if err:
        return err, 2
    commits_by_box, err = _inventory_commits_by_box(store_dir)
    if err:
        return err, 2
    rows, _ = crosscheck_events(events, commits_by_box)
    if box_id:
        rows = [r for r in rows if r["box_id"] == box_id]
    total = len(rows)
    n_conf = sum(1 for r in rows if r["verdict"] == _VERDICT_CONFIRMED)
    n_viol = sum(1 for r in rows if r["verdict"] == _VERDICT_VIOLATION)
    n_incon = sum(1 for r in rows if r["verdict"] == _VERDICT_INCONCLUSIVE)
    title = "event<->inventory cross-check"
    if box_id:
        title += " for box %s" % _clean_text(box_id)
    lines = ["%s (%d claims checked):" % (title, total)]
    if not rows:
        lines.append("  no checkable claims "
                     "(deploy/succeeded/repo events) in the journal")
    else:
        fmt = "  %-24s %-12s %-12s %-19s %s"
        lines.append(fmt % ("box", "verdict", "claim to", "received_at",
                            "detail"))
        for r in rows:
            lines.append(fmt % (
                _clean_text(str(r["box_id"]))[:24],
                r["verdict"] or "?",
                _short(r["claim_to"]) or "-",
                _clean_text((_str_or_none(r["received_at"]) or "?")[:19]),
                _clean_text(r["detail"])[:100]))
    lines.append("summary: %d checked — %d confirmed, %d violation(s), "
                 "%d inconclusive (missing evidence)" % (
                     total, n_conf, n_viol, n_incon))
    if n_viol:
        lines.append("VIOLATIONS are flags, not convictions: the inventory "
                     "(point-in-time read) wins the tie; the event keeps "
                     "its journal row. Investigate on the box before "
                     "treating a violation as a lie.")
    print("\n".join(lines))
    return None, (1 if n_viol else 0)


def main(argv=None):
    """Standalone entry (mostly for the hermetic suite): `fleet events`
    is a subcommand of inventory.py; this parser mirrors it so tests
    can exercise the readers directly."""
    parser = argparse.ArgumentParser(
        description="Fleet update-event journal readers (G17/#608: S1 "
                    "journal, S2 cross-check, S2 retention prune).")
    parser.add_argument("--store", required=True)
    parser.add_argument("--box", default=None)
    parser.add_argument("--wave", default=None)
    parser.add_argument("action", nargs="?", default="list",
                        choices=["list", "watch", "ack", "crosscheck",
                                 "prune"])
    parser.add_argument("--alert-id", default=None)
    args = parser.parse_args(argv)
    if args.action == "list":
        err = cmd_events_list(args.store, args.box, args.wave)
        if err:
            print("error: %s" % err, file=sys.stderr)
            return 2
        return 0
    if args.action == "watch":
        err, code = cmd_events_watch(args.store)
        if err:
            print("error: %s" % err, file=sys.stderr)
            return 2
        return code
    if args.action == "ack":
        if not args.alert_id:
            print("error: ack requires --alert-id", file=sys.stderr)
            return 2
        err = cmd_events_ack(args.store, args.alert_id)
        if err:
            print("error: %s" % err, file=sys.stderr)
            return 2
        return 0
    if args.action == "crosscheck":
        err, code = cmd_events_crosscheck(args.store, args.box)
        if err:
            print("error: %s" % err, file=sys.stderr)
            return 2
        return code
    if args.action == "prune":
        err = cmd_events_prune(args.store)
        if err:
            print("error: %s" % err, file=sys.stderr)
            return 2
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
