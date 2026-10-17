"""Run one fixture scenario and serialize the sweep's outputs (#1566 S2).

Shared by the recorder (`record.py`) and the CI conformance test
(`hosted/test_push_sweep_port_conformance.py`) so the two can never
disagree on what "the outputs" are.

The serialization contract (pinned — the async port must reproduce it
exactly):
- The SweepSummary's four disposition maps with sorted keys; the three
  truncation booleans; `reminders_enabled`; `notes` as [key, message]
  pairs.
- The database state after the sweep: every row of `push_send_results`
  (id order), `push_digest_state` ((owner, window) order), and
  `push_budget_counters` ((scope_type, scope_id, window) order).
  Timestamps in the rows are now-derived (D73), so the records are
  deterministic — nothing wall-clock leaks in.
- The SHA-256 of the sync module that produced the outputs, so a
  hand-edited record or a drifted module fails the provenance check
  instead of silently passing.
"""

import hashlib
import json
import os

from hosted import push_sweep
from hosted.push_sweep_port import scenarios

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDED_DIR = os.path.join(_PACKAGE_DIR, "recorded")


def sweep_module_sha256():
    """SHA-256 of the sync sweep module under test (provenance pin)."""
    path = os.path.abspath(push_sweep.__file__)
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def serialize_summary(summary):
    """A SweepSummary as a canonical JSON-able dict."""
    return {
        "reminders": dict(sorted(summary.reminders.items())),
        "digests": dict(sorted(summary.digests.items())),
        "stale_watchers": dict(sorted(summary.stale_watchers.items())),
        "token_warnings": dict(sorted(summary.token_warnings.items())),
        "candidates_seen": summary.candidates_seen,
        "pages_truncated": summary.pages_truncated,
        "reminders_enabled": summary.reminders_enabled,
        "notes": [list(note) for note in summary.notes],
        "budget_truncated": summary.budget_truncated,
        "digests_truncated": summary.digests_truncated,
    }


def serialize_db(conn):
    """The post-sweep database state as a canonical JSON-able dict."""
    send_results = [
        list(row) for row in conn.execute(
            "SELECT id, at, owner_principal, box_id, device, event_kind,"
            " event_key, outcome, http_status, latency_ms, sent_at,"
            " vapid_key_id FROM push_send_results ORDER BY id").fetchall()
    ]
    digest_state = [
        list(row) for row in conn.execute(
            "SELECT owner_principal, window_start, count, enqueued_at"
            " FROM push_digest_state"
            " ORDER BY owner_principal, window_start").fetchall()
    ]
    budget_counters = [
        list(row) for row in conn.execute(
            "SELECT scope_type, scope_id, window_start, count"
            " FROM push_budget_counters"
            " ORDER BY scope_type, scope_id, window_start").fetchall()
    ]
    return {
        "push_send_results": send_results,
        "push_digest_state": digest_state,
        "push_budget_counters": budget_counters,
    }


def run_scenario(scenario):
    """Build the fixture DB, run the sync sweep, return the record dict."""
    conn = scenarios.new_db()
    try:
        spec = scenario["build"](conn)
        kwargs = dict(spec["sweep_kwargs"])
        kwargs["now"] = spec["now_epoch"]
        kwargs["resolve_owner"] = scenarios.registry(spec["registry"])
        if spec["derive_stale"] is not None:
            kwargs["derive_stale"] = scenarios.derive(
                spec["derive_stale"])
        if spec["derive_token_warnings"] is not None:
            kwargs["derive_token_warnings"] = scenarios.derive(
                spec["derive_token_warnings"])
        if spec["record_adapter"] is not None:
            kwargs["record_adapter"] = spec["record_adapter"]
        summary = push_sweep.sweep_once(conn, **kwargs)
        conn.commit()
        return {
            "scenario": scenario["name"],
            "doc": scenario["doc"],
            "sweep_module_sha256": sweep_module_sha256(),
            "summary": serialize_summary(summary),
            "db": serialize_db(conn),
        }
    finally:
        conn.close()


def recorded_path(name):
    """The checked-in record file for a scenario."""
    return os.path.join(RECORDED_DIR, name + ".json")


def load_recorded(name):
    """Read a checked-in record file."""
    with open(recorded_path(name), "r", encoding="utf-8") as fh:
        return json.load(fh)
