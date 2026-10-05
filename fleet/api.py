#!/usr/bin/env python3
"""Fleet read API (G21 S1, issue #795). Implements docs/FLEET_READ_API_SPEC.md.

A read-only stdlib-only HTTP projection of the fleet estate store: every
endpoint computes its response at request time from the G16 inventory
journal/snapshot and the G17 event/alert journals. No mutable server-side
state, no new producer, no box-side change, no writes to the store —
the API takes the same read-only, unlocked posture as the inventory and
event journal readers (pure readers stay unlocked per the #817 flock
discipline).

Endpoints (each names its `fleet` CLI counterpart):

- ``GET /fleet/boxes?staleness_hours=N`` — ``inventory --store``
- ``GET /fleet/boxes/<id>`` — ``inventory --store --box <id>``
- ``GET /fleet/drift?expected=<commit>&staleness_hours=N`` — ``drift``
- ``GET /fleet/events?box=&wave=`` — ``events list [--box] [--wave]``
  (the per-box shape refuses with 413 past the S1 response bound, #1033)
- ``GET /fleet/alerts`` — ``events watch`` (refuses with 413 past the S1
  response bound, #1033)
- ``GET /fleet/crosscheck?box=`` — ``events crosscheck [--box]``
- ``GET /fleet/waves`` — reserved shape (G15 S2 unlanded)

Equivalence (spec §4): field-equivalence, not byte-equivalence. Every
field the CLI renders appears with the same value and the same ordering;
fields the CLI truncates for display travel BOTH truncated (the CLI's
display rule, documented in the schema) and full (machine use). The
per-endpoint conformance tests in ``fleet/test_api.py`` pin this: they
run the real CLI renderers against a fixture store and assert the API's
display fields match the rendered output exactly.

Transport (spec §5): stdlib ``http.server`` only; binds 127.0.0.1
hardcoded — there is deliberately no ``--bind`` flag, so a non-loopback
bind is impossible on this API. ``--port`` stays configurable (default
18760). No auth in S1: the operator's own box is the trust boundary,
same as the CLI. Errors never leak box-controlled bytes raw: box-
controlled free text (event ``note``, alert ``detail``) passes through
``_clean_text`` (control-char strip) exactly like the CLI's display
path; a crafted audit line can never forge an API row. The access log
is scrubbed the same way at write time (``_clean_log_line``): the
request line is client-controlled and reaches the operator's terminal
raw, so control bytes are stripped before logging.
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, unquote

import inventory
import events

# ---------------------------------------------------------------------------
# Response builders (pure: store_dir in, (http_status, body_dict) out).
# Each mirrors its CLI renderer's value rules exactly — the renderer and
# the builder share the reader helpers, so field-equivalence holds by
# construction, and the conformance tests prove it end to end.

_NO_DATA_NOTE = "no journaled records; run collect first"
_WAVES_UNAVAILABLE = ("unavailable until G15 S2 (rollout envelope null on "
                      "all journaled events)")

# ---------------------------------------------------------------------------
# S1 response-size bound (#1033).
#
# The server is single-threaded stdlib http.server: every response is
# built in memory and written on the one thread, so a multi-hundred-MB
# JSON response from a runaway journal wedges the API for every other
# local client (any local uid can query — spec §5 — so this is a
# local-availability note, not a data leak). These caps bound the two
# canonical-row lists that can grow without bound; anything past the
# cap fails closed with 413 instead of being built, serialized, and
# written. The check runs before row-mapping and serialization, so the
# over-cap path pays only the (retention-bounded) journal loads and
# sort — never row-mapping, serialization, or the write.
#
# 50,000 is a guardrail, not a quota: the journals are 90-day
# retention-bounded (events.prune_events). A busy estate (100 boxes x
# 100 events/day x 90 days) lands ~9,000 events per box against the
# 50,000 per-box events cap (~5x of headroom); alerts are
# operator-fired and sit far below the journal-wide alerts cap. The
# bound exists to stop a runaway journal from wedging the server, not
# to ration legitimate estates. If a legitimate estate ever trips it,
# that is the signal to land S2 paging (#795 OQ5), not to raise the
# cap quietly.
#
# Residuals, named not punted: per-row free-text length (event ``note``,
# alert ``detail``) is unbounded, so the cap bounds rows, not bytes —
# a byte-level guard is a follow-up slice. The per-box series shape of
# /fleet/events and /fleet/crosscheck's verdict list are out of this
# slice's scope (#1033 names events/alerts; the series shape is bounded
# by box count).
_MAX_EVENT_ROWS = 50000
_MAX_ALERT_ROWS = 50000


def _over_cap_body(endpoint, total, cap, hint):
    """413 body for the #1033 response bound.

    Deliberately no Retry-After header: waiting never shrinks the
    journal, so a retry-after would be a lie. The hint names the real
    remedies — prune the journal or land S2 paging.
    """
    return {
        "error": ("too many %s rows (%d) for one S1 response "
                  "(cap %d rows)" % (endpoint, total, cap)),
        "cap_rows": cap,
        "total_rows": total,
        "hint": hint,
    }


_EVENT_OVER_CAP_HINT = ("prune the journal with the retention policy "
                        "(fleet/events.py: prune_events), or land S2 "
                        "paging (#795 OQ5)")
_ALERT_OVER_CAP_HINT = ("prune the alert journal with the retention policy "
                        "(fleet/events.py: prune_events), or land S2 paging "
                        "(#795 OQ5)")


def _clean_log_line(value):
    """Strip control characters from one access-log line.

    The access log is a raw-bytes-to-terminal channel: unlike the JSON
    responses (where ``json.dumps`` escapes everything), whatever lands
    here reaches the operator's terminal or cron log verbatim. The
    request line is client-controlled and ``http.server`` logs it raw,
    so a local client can inject terminal escape sequences
    (``ESC[31m``) or forge extra log lines (``\\n``) unless the line is
    scrubbed. Strip C0 controls, DEL, and C1 (``\\x80``–``\\x9f`` —
    ``\\x9b`` is a live CSI introducer), the same rule the pairing
    client's display path uses (``pairing/spark_pair.py::_plane_text``).
    Non-strings pass through unchanged.
    """
    if not isinstance(value, str):
        return value
    return "".join(ch for ch in value
                   if not (ord(ch) < 0x20 or 0x7f <= ord(ch) <= 0x9f))


def _store_check(store_dir):
    """Missing store dir -> 404 (the CLI exits 2: ``store directory %r not
    found`` — the crosscheck wording, as JSON)."""
    if not os.path.isdir(store_dir):
        return {"error": "store directory %r not found" % (store_dir,)}
    return None


def _parse_staleness(value):
    """Mirror inventory.py's boundary: finite number >= 0, else 400."""
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return None, "staleness_hours must be a finite number >= 0"
    if not math.isfinite(hours) or hours < 0:
        return None, "staleness_hours must be a finite number >= 0"
    return hours, None


def _box_row(bid, record, eligible_ids):
    """One box row for /fleet/boxes — the cmd_inventory row rule."""
    ver = record.get("versions", {}) or {}
    tick = record.get("last_tick_at", {}) or {}
    gate = record.get("gate", {}) or {}
    commit_full = ver.get("repo_commit")
    tick_full = tick.get("toolset")
    frozen = gate.get("frozen")
    flags = []
    if bid not in eligible_ids:
        flags.append("stale")
    if record.get("suspect"):
        flags.append("suspect")
    return {
        "box_id": bid,
        "repo_commit": inventory._short_commit(commit_full),
        "repo_commit_full": (events._clean_text(commit_full)
        if isinstance(commit_full, str) else None),
        "toolset_tick": (tick_full or "n/a")[:10],
        "toolset_tick_full": tick_full if isinstance(tick_full, str)
        else None,
        "frozen": True if frozen else (False if frozen is False else None),
        "flags": flags,
        "eligible": bid in eligible_ids,
    }


def api_boxes(store_dir, staleness_hours):
    """GET /fleet/boxes — mirrors cmd_inventory's table + census."""
    err_body = _store_check(store_dir)
    if err_body:
        return 404, err_body
    snapshot, err = inventory.load_snapshot(store_dir)
    if err:
        return 404, {"error": err}
    boxes = snapshot.get("boxes", {})

    cutoff = datetime.now(timezone.utc) - timedelta(hours=staleness_hours)
    eligible_ids = {bid for bid, record in boxes.items()
                    if inventory._is_eligible(record, cutoff)}
    stale = sorted(bid for bid in boxes if bid not in eligible_ids)

    rows = [(_box_row(bid, record, eligible_ids))
            for bid, record in sorted(boxes.items(),
                                      key=inventory._box_sort_key)]

    census = {}
    for bid, record in sorted(boxes.items(),
                              key=inventory._box_sort_key):
        if bid in eligible_ids:
            ver = record.get("versions", {}) or {}
            key = inventory._short_commit(ver.get("repo_commit"))
            census[key] = census.get(key, 0) + 1
    denom = len(eligible_ids)
    per_commit = [{"commit": commit, "count": count,
                   "pct": (100.0 * count / denom) if denom else 0.0}
                  for commit, count in sorted(census.items(),
                                              key=lambda kv: kv[1],
                                              reverse=True)]

    body = {
        "boxes": rows,
        "census": {
            "eligible": denom,
            "total": len(boxes),
            "stale": len(stale),
            "stale_boxes": stale,
            "per_commit": per_commit,
        },
        "snapshot_generated_at": snapshot.get("generated_at"),
        "staleness_hours": staleness_hours,
        "data_current_as_of": snapshot.get("generated_at"),
    }
    if not boxes:
        body["note"] = _NO_DATA_NOTE
    return 200, body


def _history_row(record):
    """One history row for /fleet/boxes/<id> — the _print_box_history rule.

    The CLI's tick column uses the deploy-first rule (deploy, falling
    back to toolset, 19-char truncation); the inventory table shape uses
    toolset-only 10-char — the two shapes name their rules separately
    (spec §2), so this row carries the rule in ``tick_source``.
    """
    ver = record.get("versions", {}) or {}
    tick = record.get("last_tick_at", {}) or {}
    commit_full = ver.get("repo_commit")
    deploy = tick.get("deploy")
    toolset = tick.get("toolset")
    tick_value = deploy or toolset
    return {
        "observed_at": record.get("observed_at", "?"),
        "repo_commit": inventory._short_commit(commit_full),
        "repo_commit_full": (events._clean_text(commit_full)
        if isinstance(commit_full, str) else None),
        "tick": (tick_value or "n/a")[:19],
        "tick_source": ("deploy" if deploy else
                        "toolset" if toolset else "none"),
        "suspect": bool(record.get("suspect")),
    }


def api_box_history(store_dir, box_id):
    """GET /fleet/boxes/<id> — mirrors _print_box_history (newest first)."""
    err_body = _store_check(store_dir)
    if err_body:
        return 404, err_body
    journal_path = os.path.join(store_dir, inventory.JOURNAL_NAME)
    history = []
    try:
        with open(journal_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict) and record.get("box_id") == box_id:
                    history.append(record)
    except FileNotFoundError:
        return 404, {"error": "no journal at %s; run collect first"
                              % journal_path}
    except OSError as exc:
        return 500, {"error": "cannot read journal: %s" % exc}
    if not history:
        # The CLI's message verbatim, as JSON (spec §2).
        return 404, {"error": "box %s has no records in the journal" % box_id}

    rows = [_history_row(record) for record in reversed(history)]
    newest = None
    for record in history:
        parsed = inventory._parse_ts(record.get("observed_at"))
        if parsed is not None and (newest is None or parsed > newest):
            newest = parsed
    body = {
        "box_id": box_id,
        "observations": len(history),
        "history": rows,
        "data_current_as_of": newest.isoformat() if newest else None,
    }
    return 200, body


def _resolve_expected(eligible, expected):
    """The cmd_drift expected-commit resolution, verbatim."""
    expected_source = "--expected"
    if not expected:
        counts = {}
        for record in eligible.values():
            ver = record.get("versions", {}) or {}
            commit = ver.get("repo_commit")
            counts[commit] = counts.get(commit, 0) + 1
        if counts:
            top = max(counts.values())
            winners = [c for c in counts if counts[c] == top]
            expected = max(winners, key=str)
            if len(winners) == 1:
                expected_source = "fleet majority"
            else:
                expected_source = ("tie for majority (picked %s "
                                   "deterministically)"
                                   % inventory._short_commit(expected))
        else:
            expected = None
            expected_source = "none (no eligible boxes)"
    return expected, expected_source


def api_drift(store_dir, expected, staleness_hours):
    """GET /fleet/drift — mirrors cmd_drift's disagreement list."""
    err_body = _store_check(store_dir)
    if err_body:
        return 404, err_body
    snapshot, err = inventory.load_snapshot(store_dir)
    if err:
        return 404, {"error": err}
    boxes = snapshot.get("boxes", {})
    cutoff = datetime.now(timezone.utc) - timedelta(hours=staleness_hours)
    eligible = {bid: r for bid, r in boxes.items()
                if inventory._is_eligible(r, cutoff)}

    expected, expected_source = _resolve_expected(eligible, expected)

    rows = []
    for bid, record in sorted(eligible.items(),
                              key=inventory._box_sort_key):
        ver = record.get("versions", {}) or {}
        gate = record.get("gate", {}) or {}
        commit = ver.get("repo_commit")
        if inventory._short_commit(commit) == \
                inventory._short_commit(expected):
            continue
        if gate.get("frozen"):
            reason = "policy-held (frozen)"
        elif record.get("arc"):
            reason = "deferred (active tenant arc)"
        elif record.get("suspect"):
            # suspect_reason is box-sourced (interpolates raw audit claims
            # at collect time) — strip control chars like every other
            # operator-facing surface.
            reason = "suspect report (%s)" % events._clean_text(
                record.get("suspect_reason") or "see record")
        else:
            reason = "unexplained"
        rows.append({
            "box_id": bid,
            "repo_commit": inventory._short_commit(commit),
            "repo_commit_full": (events._clean_text(commit)
            if isinstance(commit, str) else None),
            "reason": reason,
        })

    body = {
        "rows": rows,
        "differing": len(rows),
        "eligible": len(eligible),
        "expected": {
            "commit": inventory._short_commit(expected),
            "commit_input": expected,
            "source": expected_source,
        },
        "commit_matching": "12-char prefix, same as the inventory census",
        "snapshot_generated_at": snapshot.get("generated_at"),
        "staleness_hours": staleness_hours,
        "data_current_as_of": snapshot.get("generated_at"),
    }
    if not boxes:
        body["note"] = _NO_DATA_NOTE
    return 200, body


def _event_rows_for(events_list):
    """Full canonical journal records, (emitted_at, event_id) ascending.

    A superset of what the CLI's event printer renders (spec §2): every
    journal field travels, not just the rendered subset. The box-
    controlled ``note`` field goes through the same control-char
    stripping as the CLI's display path (spec §5).
    """
    rows = []
    for e in sorted(events_list, key=events._sort_key):
        row = dict(e)
        if "note" in row:
            row["note"] = events._clean_text(row["note"])
        rows.append(row)
    return rows


def _journal_freshness(store_dir):
    """Newest received_at across the event and alert journals (spec §2).

    Alert rows carry no received_at field (the alert schema is
    alert_id/rule/fired_at/... — see _alert), so in practice the stamp
    comes from the event journal; both journals are read because the
    spec names both, and a future alert schema with received_at must
    not silently change the stamp's meaning.
    """
    all_events, err = events.load_events(store_dir)
    if err:
        return None, err
    all_alerts, err = events.load_alerts(store_dir)
    if err:
        return None, err
    newest = None
    for row in list(all_events) + list(all_alerts):
        parsed = events._parse_ts(row.get("received_at"))
        if parsed is not None and (newest is None or parsed > newest):
            newest = parsed
    return (newest.isoformat() if newest else None), None


def api_events(store_dir, box_id, wave):
    """GET /fleet/events — mirrors cmd_events_list's two shapes."""
    err_body = _store_check(store_dir)
    if err_body:
        return 404, err_body
    all_events, err = events.load_events(store_dir)
    if err:
        return 500, {"error": err}
    data_as_of, err = _journal_freshness(store_dir)
    if err:
        return 500, {"error": err}

    filtered = list(all_events)
    if wave:
        # Honest filter: while the rollout envelope is null (G15 S2
        # unlanded) the filter is unsatisfiable — answer 200 with the
        # empty shape plus the named reason, exactly what the journal
        # contains for that filter. Returning everything would be
        # fail-dangerous for the named S2 consumers.
        has_rollout = any(isinstance(e.get("rollout"), dict)
                          for e in filtered)
        if not has_rollout:
            reason = ("unavailable until G15 S2 "
                      "(rollout envelope null)")
            if box_id:
                return 200, {
                    "box_id": box_id,
                    "event_count": 0,
                    "events": [],
                    "wave_filter": reason,
                    "data_current_as_of": data_as_of,
                }
            return 200, {
                "event_count": 0,
                "box_count": 0,
                "series": [],
                "wave_filter": reason,
                "data_current_as_of": data_as_of,
            }
        filtered = [e for e in filtered
                    if isinstance(e.get("rollout"), dict)
                    and e["rollout"].get("wave") == wave]
    if box_id:
        filtered = [e for e in filtered if e.get("box_id") == box_id]

    if box_id:
        if not filtered:
            return 404, {"error": "box %s has no events in the journal"
                                  % box_id}
        # #1033: fail closed before row-mapping/serialization — the
        # single-threaded server must never build a giant response.
        if len(filtered) > _MAX_EVENT_ROWS:
            return 413, _over_cap_body("event", len(filtered),
                                       _MAX_EVENT_ROWS,
                                       _EVENT_OVER_CAP_HINT)
        body = {
            "box_id": box_id,
            "event_count": len(filtered),
            "events": _event_rows_for(filtered),
            "data_current_as_of": data_as_of,
        }
        if wave:
            body["wave_filter"] = wave
        return 200, body

    by_box = {}
    for e in filtered:
        by_box.setdefault(e.get("box_id"), []).append(e)
    series = []
    for bid in sorted(by_box, key=str):
        ordered = sorted(by_box[bid], key=events._sort_key)
        last = ordered[-1]
        outcomes = {}
        for e in ordered:
            outcomes[e.get("outcome")] = \
                outcomes.get(e.get("outcome"), 0) + 1
        last_outcome_full = last.get("outcome")
        last_emitted_full = events._str_or_none(last.get("emitted_at"))
        last_note_full = events._str_or_none(last.get("note"))
        series.append({
            "box_id": bid,
            # Display-parity truncations (the CLI's column widths), with
            # the full values alongside per the §4 no-hidden-truncation
            # rule.
            "event_count": len(ordered),
            "last_outcome": str(last_outcome_full)[:13],
            "last_outcome_full": last_outcome_full,
            "last_emitted_at": (events._clean_text(
                last_emitted_full) or "?")[:19],
            "last_emitted_at_full": events._clean_text(
                last_emitted_full),
            "outcome_histogram": {str(o): c
                                  for o, c in sorted(
                                      outcomes.items(),
                                      key=lambda kv: str(kv[0]))},
            "last_note": events._clean_text(
                "%s (%s)" % (",".join(
                    "%s=%d" % (o, c)
                    for o, c in sorted(outcomes.items(),
                                       key=lambda kv: str(kv[0]))),
                    (last_note_full or "")[:40])),
            "last_note_full": events._clean_text(last_note_full),
        })
    body = {
        "event_count": len(filtered),
        "box_count": len(by_box),
        "series": series,
        "data_current_as_of": data_as_of,
    }
    if wave:
        body["wave_filter"] = wave
    if not all_events:
        body["note"] = _NO_DATA_NOTE
    return 200, body


def _alert_row(alert):
    """Full canonical alert record; box-controlled ``detail`` is
    control-char stripped like the CLI's display path (spec §5)."""
    row = dict(alert)
    if "detail" in row:
        row["detail"] = events._clean_text(row["detail"])
    return row


def api_alerts(store_dir):
    """GET /fleet/alerts — mirrors cmd_events_watch (exit 1 <=> pending)."""
    err_body = _store_check(store_dir)
    if err_body:
        return 404, err_body
    all_alerts, err = events.load_alerts(store_dir)
    if err:
        return 500, {"error": err}
    pending = [a for a in all_alerts if not a.get("acked")]
    acked = [a for a in all_alerts if a.get("acked")]
    # Pending rows follow the CLI's fired_at-ascending order; the acked
    # tail is outside the CLI's baseline (the CLI omits acked alerts) —
    # ordered the same way but marked as such in the conformance test.
    ordered = (sorted(pending, key=lambda x: str(x.get("fired_at") or ""))
               + sorted(acked, key=lambda x: str(x.get("fired_at") or "")))
    # #1033: fail closed before freshness/row-mapping — the over-cap
    # path pays only the (retention-bounded) journal load and sort.
    if len(ordered) > _MAX_ALERT_ROWS:
        return 413, _over_cap_body("alert", len(ordered),
                                   _MAX_ALERT_ROWS,
                                   _ALERT_OVER_CAP_HINT)
    data_as_of, err = _journal_freshness(store_dir)
    if err:
        return 500, {"error": err}
    body = {
        "status": "pending" if pending else "clear",
        "pending_count": len(pending),
        "acked_count": len(acked),
        "alerts": [_alert_row(a) for a in ordered],
        "data_current_as_of": data_as_of,
    }
    if not all_alerts:
        body["note"] = _NO_DATA_NOTE
    return 200, body


def _verdict_row(row):
    """One crosscheck verdict row — the CLI's field names and ordering,
    display-parity truncations plus full values (spec §4)."""
    received_full = events._str_or_none(row["received_at"])
    claim_full = row["claim_to"] if isinstance(row["claim_to"], str) \
        else None
    detail_full = row["detail"]
    return {
        "box_id": row["box_id"],
        "event_id": row["event_id"],
        "received_at": (events._clean_text(received_full) or "?")[:19],
        "received_at_full": events._clean_text(received_full),
        "claim_to": events._short(claim_full) if claim_full else "-",
        "claim_to_full": claim_full,
        "verdict": row["verdict"],
        "detail": events._clean_text(detail_full)[:100],
        "detail_full": events._clean_text(detail_full),
    }


def api_crosscheck(store_dir, box_id):
    """GET /fleet/crosscheck — mirrors cmd_events_crosscheck."""
    err_body = _store_check(store_dir)
    if err_body:
        return 404, err_body
    all_events, err = events.load_events(store_dir)
    if err:
        return 500, {"error": err}
    commits_by_box, err = events._inventory_commits_by_box(store_dir)
    if err:
        return 500, {"error": err}
    data_as_of, err = _journal_freshness(store_dir)
    if err:
        return 500, {"error": err}

    rows, counts = events.crosscheck_events(all_events, commits_by_box)
    if box_id:
        rows = [r for r in rows if r["box_id"] == box_id]

    n_conf = sum(1 for r in rows if r["verdict"] == "confirmed")
    n_viol = sum(1 for r in rows if r["verdict"] == "violation")
    n_incon = sum(1 for r in rows if r["verdict"] == "inconclusive")
    body = {
        "status": "violations" if n_viol else "no-violations",
        "checked": len(rows),
        "confirmed": n_conf,
        "violations": n_viol,
        "inconclusive": n_incon,
        "verdicts": [_verdict_row(r) for r in rows],
        "data_current_as_of": data_as_of,
    }
    if box_id:
        body["box_id"] = box_id
    if not rows:
        body["note"] = "no checkable claims (deploy/succeeded/repo events) " \
                       "in the journal"
    return 200, body


def api_waves():
    """GET /fleet/waves — reserved shape until G15 S2 lands (spec §2)."""
    return 200, {"waves": [], "wave_assignments": _WAVES_UNAVAILABLE}


# ---------------------------------------------------------------------------
# HTTP dispatch

def dispatch(method, path, query, store_dir):
    """Route one request. Returns (http_status, body_dict)."""
    if method != "GET":
        return 405, {"error": "method not allowed; this API is read-only"}
    route = path.rstrip("/") or "/"
    if route == "/fleet/boxes":
        hours, qerr = _parse_staleness(
            query.get("staleness_hours", ["24"])[0])
        if qerr:
            return 400, {"error": qerr}
        return api_boxes(store_dir, hours)
    if route.startswith("/fleet/boxes/"):
        box_id = unquote(route[len("/fleet/boxes/"):])
        if not box_id or "/" in box_id:
            return 404, {"error": "unknown endpoint"}
        return api_box_history(store_dir, box_id)
    if route == "/fleet/drift":
        hours, qerr = _parse_staleness(
            query.get("staleness_hours", ["24"])[0])
        if qerr:
            return 400, {"error": qerr}
        expected = query.get("expected", [None])[0]
        return api_drift(store_dir, expected, hours)
    if route == "/fleet/events":
        box_id = query.get("box", [None])[0]
        wave = query.get("wave", [None])[0]
        return api_events(store_dir, box_id, wave)
    if route == "/fleet/alerts":
        return api_alerts(store_dir)
    if route == "/fleet/crosscheck":
        box_id = query.get("box", [None])[0]
        return api_crosscheck(store_dir, box_id)
    if route == "/fleet/waves":
        return api_waves()
    return 404, {"error": "unknown endpoint"}


class FleetAPIHandler(BaseHTTPRequestHandler):
    """GET-only JSON handler. ``store_dir`` is set on the class by serve()."""
    store_dir = None
    server_version = "fleet-api/1"

    def _send(self, status, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            status, body = dispatch("GET", parsed.path, query,
                                    self.store_dir)
        except Exception as exc:
            # Never leak a traceback: the API's contract is JSON errors.
            status, body = 500, {"error": "internal error: %s" % exc}
        self._send(status, body)

    def _method_not_allowed(self):
        self._send(405, {"error": "method not allowed; "
                                 "this API is read-only"})

    def send_error(self, code, message=None, explain=None):
        # Keep the JSON-only contract: stdlib's default error page is
        # HTML. Every response this API speaks is JSON, listed verbs
        # and unlisted ones alike.
        self._send(code, {"error": message
                          or self.responses.get(code, ("?",))[0]})

    do_POST = _method_not_allowed
    do_PUT = _method_not_allowed
    do_DELETE = _method_not_allowed
    do_PATCH = _method_not_allowed
    # Listed verbs get a JSON 405. Verbs not listed here get stdlib's
    # 501 via the send_error override above — still JSON, never HTML.
    do_HEAD = _method_not_allowed
    do_OPTIONS = _method_not_allowed
    do_TRACE = _method_not_allowed
    do_CONNECT = _method_not_allowed

    def log_message(self, fmt, *args):
        # Access log to stderr, one line per request — same as the
        # fleet collector's loud-logging discipline, never silent.
        # The request line is client-controlled and http.server would
        # log it raw: scrub control characters (incl. C1) so a local
        # client cannot inject terminal escapes or forge log lines.
        sys.stderr.write("fleet-api %s - %s\n" %
                         (_clean_log_line(self.address_string()),
                          _clean_log_line(fmt % args)))


def serve(store_dir, port):
    """Bind 127.0.0.1 hardcoded (spec §5: no --bind flag exists) and serve."""
    FleetAPIHandler.store_dir = store_dir
    server = HTTPServer(("127.0.0.1", port), FleetAPIHandler)
    sys.stderr.write("fleet-api: serving %s on 127.0.0.1:%d\n" %
                     (store_dir, server.server_address[1]))
    server.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fleet read API (G21 S1, issue #795): read-only HTTP "
                    "projection of the fleet estate store. Binds 127.0.0.1 "
                    "only; no auth in S1 — the operator's own box is the "
                    "trust boundary, same as the CLI.")
    parser.add_argument("--store", required=True,
                        help="store dir (journal.jsonl + snapshot.json); "
                             "never written")
    parser.add_argument("--port", type=int, default=18760,
                        help="localhost port (default 18760)")
    args = parser.parse_args(argv)
    if not (0 < args.port < 65536):
        print("error: --port must be 1-65535, got %r" % (args.port,),
              file=sys.stderr)
        return 2
    if not os.path.isdir(args.store):
        print("error: store directory %r not found" % (args.store,),
              file=sys.stderr)
        return 2
    try:
        serve(args.store, args.port)
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print("error: cannot serve: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
