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
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

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


def _note_for(event, result, line):
    """Synthesize the human/alert note from the audit line itself (§2:
    the box-side alert reason lives in $LAST_FAILURE, which the
    collector does not pull — so the note is a one-line synthesis,
    never a debug dump)."""
    phase = line.get("phase")
    to = line.get("to")
    comps = line.get("components") or line.get("component")
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
        base = "audit line result=%s" % result
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
    """Build one standard-shape event (§2) from an audit line."""
    ts = line.get("ts")
    frm = line.get("from")
    to = line.get("to")
    # manual-rollback's `from` is the commit the operator restored away
    # from (the audit line carries it as rolled_back_from).
    if line.get("event") == "rollback" and line.get("result") == \
            "manual-rollback" and frm is None:
        frm = line.get("rolled_back_from")
    trigger = line.get("trigger")
    if trigger not in ("scheduled", "extra-inputs"):
        trigger = "scheduled"
    phase = line.get("phase")
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
        "emitted_at": ts if isinstance(ts, str) and ts else None,
        "received_at": received_at,
        "source": "auto-deploy",
        "component": "repo",
        "subcomponent": subcomponent,
        "subcomponents": subcomponents_verbatim,
        "kind": kind,
        "outcome": outcome,
        "from": frm if frm is not None else None,
        "to": to if to is not None else None,
        "from_version": line.get("from_version"),
        "to_version": line.get("to_version"),
        "phase": phase if phase is not None else None,
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
                         "kept out of the event journal" % (event, result))
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
    (appended, duplicates, error)."""
    try:
        os.makedirs(store_dir, exist_ok=True)
    except OSError as exc:
        return None, None, "cannot create store dir %s: %s" % (store_dir,
                                                                exc)
    existing, err = _load_journal(store_dir, EVENTS_JOURNAL_NAME, None)
    if err:
        return None, None, err
    seen = {(e.get("box_id"), e.get("event_id")) for e in existing
            if isinstance(e.get("box_id"), str)
            and isinstance(e.get("event_id"), str)}
    fresh = [e for e in events
             if (e.get("box_id"), e.get("event_id")) not in seen]
    journal_path = os.path.join(store_dir, EVENTS_JOURNAL_NAME)
    try:
        with open(journal_path, "a", encoding="utf-8", buffering=1) as fh:
            for event in fresh:
                fh.write(json.dumps(event, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        return None, None, "cannot append to event journal: %s" % exc
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
        "box_id": box_id,
        "subcomponent": subcomponent,
        "to": to,
        "detail": detail,
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
                                    to[:12] if to else "(no to)",
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
    (fired_alerts, error)."""
    fired_at = fired_at or _now_iso()
    events, err = load_events(store_dir)
    if err:
        return None, err
    candidates = []
    candidates.extend(_rule_rollback_failed(events, fired_at))
    candidates.extend(_rule_correlated_failure(events, fired_at))
    candidates.extend(_rule_silent_wave(events, fired_at))
    candidates.extend(_rule_stuck_precheck(events, fired_at))

    existing, err = _load_journal(store_dir, ALERTS_JOURNAL_NAME, None)
    if err:
        return None, err
    seen = {a.get("alert_id") for a in existing
            if isinstance(a.get("alert_id"), str)}
    fresh = [a for a in candidates if a["alert_id"] not in seen]
    if fresh:
        try:
            os.makedirs(store_dir, exist_ok=True)
        except OSError as exc:
            return None, "cannot create store dir %s: %s" % (store_dir, exc)
        alerts_path = os.path.join(store_dir, ALERTS_JOURNAL_NAME)
        try:
            with open(alerts_path, "a", encoding="utf-8",
                      buffering=1) as fh:
                for alert in fresh:
                    fh.write(json.dumps(alert, sort_keys=True) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            return None, "cannot append to alert journal: %s" % exc
    return fresh, None


def load_alerts(store_dir):
    """Returns (alerts, error)."""
    return _load_journal(store_dir, ALERTS_JOURNAL_NAME, None)


def ack_alert(store_dir, alert_id):
    """Mark an alert acknowledged. Returns (found, error): the alert
    journal is rewritten atomically (tmp + os.replace) so a crash never
    tears it."""
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
    alerts_path = os.path.join(store_dir, ALERTS_JOURNAL_NAME)
    tmp_path = alerts_path + ".tmp.%d" % os.getpid()
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            for alert in alerts:
                fh.write(json.dumps(alert, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, alerts_path)
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return None, "cannot rewrite alert journal: %s" % exc
    return True, None


# --- CLI readers (called from inventory.py's `events` subcommand) ---------
def _short(value, width=12):
    if not value:
        return "-"
    return str(value)[:width]


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
                (e.get("emitted_at") or "?")[:19],
                e.get("kind") or "?", e.get("outcome") or "?",
                _short(e.get("subcomponent"), 16) or "-",
                "%s->%s" % (frm, to),
                (e.get("note") or "")[:60]))
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
                str(bid)[:24], len(series),
                str(last.get("outcome"))[:13],
                (last.get("emitted_at") or "?")[:19],
                ("%s (%s)" % (summary, (last.get("note") or "")[:40]))))
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
            a.get("rule"), a.get("box_id") or "-",
            a.get("subcomponent") or "-",
            _short(a.get("to")), (a.get("fired_at") or "?")[:19]))
        lines.append("      %s" % (a.get("detail") or ""))
        lines.append("      alert_id=%s (fleet events ack --alert-id <id>)"
                     % a.get("alert_id"))
    print("\n".join(lines))
    return None, 1


def cmd_events_ack(store_dir, alert_id):
    found, err = ack_alert(store_dir, alert_id)
    if err:
        return err
    if not found:
        return "no alert with id %s" % alert_id
    print("acknowledged %s" % alert_id)
    return None


def main(argv=None):
    """Standalone entry (mostly for the hermetic suite): `fleet events`
    is a subcommand of inventory.py; this parser mirrors it so tests
    can exercise the readers directly."""
    parser = argparse.ArgumentParser(
        description="Fleet update-event journal readers (G17/#608 S1).")
    parser.add_argument("--store", required=True)
    parser.add_argument("--box", default=None)
    parser.add_argument("--wave", default=None)
    parser.add_argument("action", nargs="?", default="list",
                        choices=["list", "watch", "ack"])
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
    return 2


if __name__ == "__main__":
    sys.exit(main())
