#!/usr/bin/env python3
"""Per-tenant-plane version inventory + operational-cost ledger, S1 (issue #1261 / F-OP7/D-OP7).

Design: the fleet box inventory (fleet/inventory.py, #607/G16) answers
"what % of the fleet is on build X?" and "which boxes missed the last
update window?" for *boxes*. This module is the same two questions for
the *tenant-plane layer* (D-MT1, one plane per tenant): which template
version each tenant plane runs, and which planes have not converged.
It also keeps the per-plane operational-cost journal that feeds the
D-MT5 revisit trigger — provision + update + rollback events with
duration and cost, so "measured per-tenant-plane operational cost" is a
query, not an estimate.

Scope note (both-supported default, per PLAYBOOK): the inventory is a
repo component any operator with N planes runs against their own
estate; the hosted product runs the same component as the
operator-plane's source for rollout waves. No new daemon, no inbound
port — the operator records observations (register/deploy/cost events)
from wherever they act; S1 is operator-driven, not plane-reported.

Subcommands:
  register --store DIR --plane-id ID --tenant-id ID [--template V] [--channel C]
      Register a tenant plane (status `provisioning`). Fail-closed when
      the plane is already registered: use `deploy` to change state.
  deploy   --store DIR --plane-id ID --template V [--status healthy|degraded] [--notes T]
      Record that a plane is running template V (a rollout wave landing).
      Deploying on a retired plane resurrects it (intentional: a retired
      plane_id may be re-provisioned and rejoin the fleet).
  retire   --store DIR --plane-id ID [--notes T]
      Mark a plane `retired` (kept in the census denominator's exclusion
      set, still visible for cost history).
  cost     --store DIR --plane-id ID --event provision|update|rollback
             [--duration-s N] [--cost-usd X] [--notes T]
      Append one operational-cost event to the journal.
  census   --store DIR [--stale-hours N]
      Print the version table (per-plane template versions + % census).
  stale    --store DIR --expected TEMPLATE [--stale-hours N]
      Planes not running TEMPLATE: wrong version, stale record, or no
      record. The rollout controller reads this before promoting a wave
      (exit 1 when any plane is not converged, 0 when all are).
  cost-summary --store DIR [--plane-id ID]
      D-MT5 input: per-plane and total provision vs update cost, with
      event counts and median durations.

Store layout:
  <store>/planes.json          derived snapshot: latest record per plane_id
  <store>/planes_journal.jsonl append-only observation records
  <store>/costs.jsonl          append-only cost events

Record schema (S1):
  {schema, plane_id, tenant_id, template_version, channel,
   status{provisioning,healthy,degraded,retired}, observed_at,
   reporter, notes}
Cost-event schema (S1):
  {schema, plane_id, event{provision,update,rollback},
   at, duration_s, cost_usd, notes}

Rules the code follows (from the issue, summarized here so the behavior
is auditable at the call site):
  - observed_at/at are collector-side (the operator's clock); nothing
    plane-reported is trusted for ordering, because S1 is
    operator-recorded. A future slice may accept plane-signed heartbeats;
    they must not backfill at — same discipline as the box inventory.
  - The census denominator is eligible planes only: non-retired planes
    whose latest record is fresher than the staleness window. Excluded
    planes are printed alongside the percentage so a 100% census over 1
    of 50 planes is honest (same rule as the box inventory).
  - cost-summary separates provision (one-time) from update/rollback
    (recurring); D-MT5's trigger compares recurring update cost across
    template versions, not all-time totals.
  - Writes serialize on the store-scoped journal lock (events.py):
    journal appends and snapshot publication never race. The snapshot
    is published tmp+os.replace; journal lines are single O_APPEND
    write() calls.
  - The S1 trust root is the operator's box filesystem: neither journal
    has hash chaining and the snapshot is unsigned, so the store is the
    operator's own memory — it must never be treated as evidence *against*
    the operator. A later slice may add journal hash-chaining plus a
    `verify` subcommand.
  - The snapshot is derived and never trusted alone: every read replays
    the planes journal's latest-per-plane records and fails closed
    (exit 2) on any divergence, so a tampered or stale-restored snapshot
    cannot present a diverged fleet as converged to the `stale`
    pre-promotion gate.
  - deploy against an unregistered plane fails closed (exit 2): the
    controller must never silently create a plane row mid-rollout.

Exit 0 on a printed result, 2 on bad input/arguments. An unexpected
internal failure also exits 2 with a one-line message, never a bare
traceback (the operator's contract is the exit code, not the stack).
Stdlib only.
"""

import argparse
import json
import math
import os
import re
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone

# Sibling module (fleet/events.py): the store-scoped journal lock. Imported
# as a sibling because the fleet modules are script-run (python3
# fleet/plane_inventory.py puts fleet/ on sys.path); the hermetic suite
# exercises the CLIs through subprocess, never through imports.
import events

RECORD_SCHEMA = "plane-inventory-record/1"
SNAPSHOT_SCHEMA = "plane-inventory-snapshot/1"
COST_SCHEMA = "plane-cost-event/1"

PLANES_SNAPSHOT_NAME = "planes.json"
PLANES_JOURNAL_NAME = "planes_journal.jsonl"
COSTS_JOURNAL_NAME = "costs.jsonl"

_STATUSES = ("provisioning", "healthy", "degraded", "retired")
_COST_EVENTS = ("provision", "update", "rollback")
# Collector-side observed_at is trusted; records are minted operator-side
# within the same process, so future-skew handling is unnecessary.
DEFAULT_STALE_HOURS = 24

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_TEMPLATE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+~@-]{0,127}$")


def _fail(msg):
    """Print a one-line error and exit 2 (the operator's error contract)."""
    print(f"plane_inventory: error: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _check_id(value, what):
    if not value or not _ID_RE.match(value):
        _fail(
            f"{what} must match [A-Za-z0-9][A-Za-z0-9._-]{{0,63}}, "
            f"got {value!r}"
        )
    return value


def _check_template(value):
    if not value or not _TEMPLATE_RE.match(value):
        _fail(
            f"template version must be a non-empty string without whitespace "
            f"or control characters, got {value!r}"
        )
    return value


def _check_nonneg_number(value, what):
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        _fail(f"{what} must be a number, got {value!r}")
    # Non-finite numbers (inf, 1e999) must not enter the D-MT5 ledger:
    # json would emit Infinity (not strict JSON) and the recurring total
    # would be poisoned.
    if not math.isfinite(num) or num < 0:
        _fail(f"{what} must be a finite number >= 0, got {value!r}")
    return num


def _ensure_store(store_dir):
    if not store_dir:
        _fail("--store is required")
    try:
        os.makedirs(store_dir, exist_ok=True)
    except OSError as exc:
        _fail(f"--store is not a usable directory: {exc}")
    return store_dir


_MISSING = "missing"  # sentinel: store file absent (distinct from a `null` document)
_PRESENT = "present"


def _load_json(path, what):
    if not os.path.exists(path):
        return _MISSING, None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return _PRESENT, json.load(fh)
    except (OSError, ValueError) as exc:
        _fail(f"cannot read {what} at {path}: {exc}")


def _snapshot(store_dir):
    status, data = _load_json(os.path.join(store_dir, PLANES_SNAPSHOT_NAME), "planes snapshot")
    if status == _MISSING:
        return {"schema": SNAPSHOT_SCHEMA, "planes": {}}
    # A `null` document is structural corruption, not an empty store —
    # fail closed, never read it as "no planes."
    if not isinstance(data, dict):
        _fail("planes snapshot is corrupt: top-level is not an object")
    planes = data.get("planes")
    if not isinstance(planes, dict):
        _fail("planes snapshot is corrupt: 'planes' is not an object")
    # The snapshot is derived and never trusted alone: every read replays
    # the journal's latest-per-plane records and fails closed on any
    # divergence, so a tampered or stale-restored snapshot cannot present
    # a diverged fleet as converged to the rollout controller.
    _verify_snapshot_consistent(store_dir, planes)
    return {"schema": SNAPSHOT_SCHEMA, "planes": planes}


def _latest_journal_records(store_dir):
    """Replay planes_journal.jsonl: latest observation record per plane_id."""
    path = os.path.join(store_dir, PLANES_JOURNAL_NAME)
    latest = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if not isinstance(rec, dict) or "plane_id" not in rec:
                        _fail(f"planes journal at {path} has a malformed record")
                    latest[rec["plane_id"]] = rec
        except (OSError, ValueError) as exc:
            _fail(f"cannot replay planes journal at {path}: {exc}")
    return latest


def _verify_snapshot_consistent(store_dir, planes):
    """Fail closed when the snapshot disagrees with the journal.

    The journal is the source of truth; the snapshot is derived. A
    divergence means the snapshot was tampered with or restored from a
    stale backup — reading it as if it were current would be a
    false-green for the pre-promotion `stale` gate.
    """
    journal = _latest_journal_records(store_dir)
    if set(journal) != set(planes):
        _fail(
            "snapshot/journal divergence: plane sets differ "
            f"(journal={sorted(journal)}, snapshot={sorted(planes)})"
        )
    for plane_id, jrec in journal.items():
        srec = planes[plane_id]
        for field in ("template_version", "status", "observed_at"):
            if jrec.get(field) != srec.get(field):
                _fail(
                    f"snapshot/journal divergence for plane {plane_id!r}: "
                    f"field {field} differs (journal={jrec.get(field)!r}, "
                    f"snapshot={srec.get(field)!r})"
                )


def _publish_snapshot(store_dir, planes):
    """Atomically replace planes.json (process-unique tmp path, os.replace)."""
    path = os.path.join(store_dir, PLANES_SNAPSHOT_NAME)
    payload = {"schema": SNAPSHOT_SCHEMA, "planes": planes}
    fd, tmp = tempfile.mkstemp(
        dir=store_dir, prefix=PLANES_SNAPSHOT_NAME + ".tmp."
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _append_journal(store_dir, journal_name, records):
    """Append records as one O_APPEND write() per line, under the store lock."""
    path = os.path.join(store_dir, journal_name)
    lines = [json.dumps(r, sort_keys=True) + "\n" for r in records]
    with events.journal_lock(store_dir):
        try:
            with open(path, "a", encoding="utf-8") as fh:
                for line in lines:
                    fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            _fail(f"cannot append to {journal_name}: {exc}")


def _read_costs(store_dir):
    path = os.path.join(store_dir, COSTS_JOURNAL_NAME)
    rows = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        except (OSError, ValueError) as exc:
            _fail(f"cannot read cost journal at {path}: {exc}")
    return rows


def _record_is_fresh(record, stale_hours):
    try:
        observed = datetime.fromisoformat(record["observed_at"])
    except (KeyError, ValueError):
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - observed).total_seconds() <= stale_hours * 3600


def cmd_register(args):
    store_dir = _ensure_store(args.store)
    plane_id = _check_id(args.plane_id, "--plane-id")
    tenant_id = _check_id(args.tenant_id, "--tenant-id")
    template = _check_template(args.template) if args.template else None
    channel = _check_id(args.channel, "--channel") if args.channel else "stable"

    record = {
        "schema": RECORD_SCHEMA,
        "plane_id": plane_id,
        "tenant_id": tenant_id,
        "template_version": template,
        "channel": channel,
        "status": "provisioning",
        "observed_at": _now_iso(),
        "reporter": "operator",
        "notes": args.notes or "",
    }
    notes = []
    record["notes"] = args.notes or ""

    with events.journal_lock(store_dir):
        snap = _snapshot(store_dir)
        if plane_id in snap["planes"]:
            _fail(f"plane {plane_id!r} is already registered (use deploy to change state)")
        _append_records_locked(store_dir, [record])
        snap["planes"][plane_id] = record
        _publish_snapshot(store_dir, snap["planes"])
    print(json.dumps({"ok": True, "plane_id": plane_id, "status": "provisioning"}))
    return 0


def _append_records_locked(store_dir, records):
    """Append to the planes journal. Caller must hold events.journal_lock."""
    path = os.path.join(store_dir, PLANES_JOURNAL_NAME)
    lines = [json.dumps(r, sort_keys=True) + "\n" for r in records]
    try:
        with open(path, "a", encoding="utf-8") as fh:
            for line in lines:
                fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        _fail(f"cannot append to {PLANES_JOURNAL_NAME}: {exc}")


def cmd_deploy(args):
    store_dir = _ensure_store(args.store)
    plane_id = _check_id(args.plane_id, "--plane-id")
    template = _check_template(args.template)
    status = args.status or "healthy"
    if status not in ("healthy", "degraded"):
        _fail("--status must be healthy or degraded, got %r" % (args.status,))

    with events.journal_lock(store_dir):
        snap = _snapshot(store_dir)
        prev = snap["planes"].get(plane_id)
        if prev is None:
            _fail(f"plane {plane_id!r} is not registered (register first)")
        record = dict(prev)
        record.update(
            {
                "schema": RECORD_SCHEMA,
                "template_version": template,
                "status": status,
                "observed_at": _now_iso(),
                "reporter": "operator",
                "notes": args.notes or "",
            }
        )
        _append_records_locked(store_dir, [record])
        snap["planes"][plane_id] = record
        _publish_snapshot(store_dir, snap["planes"])
    print(json.dumps({"ok": True, "plane_id": plane_id, "template_version": template,
                      "status": status}))
    return 0


def cmd_retire(args):
    store_dir = _ensure_store(args.store)
    plane_id = _check_id(args.plane_id, "--plane-id")

    with events.journal_lock(store_dir):
        snap = _snapshot(store_dir)
        prev = snap["planes"].get(plane_id)
        if prev is None:
            _fail(f"plane {plane_id!r} is not registered")
        record = dict(prev)
        record.update(
            {
                "schema": RECORD_SCHEMA,
                "status": "retired",
                "observed_at": _now_iso(),
                "reporter": "operator",
                "notes": args.notes or "",
            }
        )
        _append_records_locked(store_dir, [record])
        snap["planes"][plane_id] = record
        _publish_snapshot(store_dir, snap["planes"])
    print(json.dumps({"ok": True, "plane_id": plane_id, "status": "retired"}))
    return 0


def cmd_cost(args):
    store_dir = _ensure_store(args.store)
    plane_id = _check_id(args.plane_id, "--plane-id")
    event = args.event
    if event not in _COST_EVENTS:
        _fail(f"--event must be one of {','.join(_COST_EVENTS)}, got {event!r}")
    duration_s = _check_nonneg_number(args.duration_s, "--duration-s")
    cost_usd = _check_nonneg_number(args.cost_usd, "--cost-usd")

    with events.journal_lock(store_dir):
        snap = _snapshot(store_dir)
        if plane_id not in snap["planes"]:
            _fail(f"plane {plane_id!r} is not registered (register first)")
    record = {
        "schema": COST_SCHEMA,
        "plane_id": plane_id,
        "event": event,
        "at": _now_iso(),
        "duration_s": duration_s,
        "cost_usd": cost_usd,
        "notes": args.notes or "",
    }
    _append_journal(store_dir, COSTS_JOURNAL_NAME, [record])
    print(json.dumps({"ok": True, "plane_id": plane_id, "event": event}))
    return 0


def _eligible_planes(store_dir, stale_hours):
    snap = _snapshot(store_dir)
    eligible, excluded = [], []
    for plane_id, rec in snap["planes"].items():
        if rec.get("status") == "retired":
            excluded.append((plane_id, "retired"))
        elif not _record_is_fresh(rec, stale_hours):
            excluded.append((plane_id, "stale"))
        else:
            eligible.append((plane_id, rec))
    return eligible, excluded


def cmd_census(args):
    store_dir = _ensure_store(args.store)
    eligible, excluded = _eligible_planes(store_dir, args.stale_hours)
    total = len(eligible)
    versions = {}
    for _plane_id, rec in eligible:
        versions[rec.get("template_version")] = versions.get(rec.get("template_version"), 0) + 1
    table = [
        {
            "template_version": v,
            "planes": n,
            "pct": round(100.0 * n / total, 1) if total else 0.0,
        }
        for v, n in sorted(versions.items(), key=lambda kv: (-kv[1], str(kv[0])))
    ]
    print(json.dumps({
        "eligible": total,
        "excluded": [{"plane_id": pid, "reason": why} for pid, why in sorted(excluded)],
        "census": table,
    }, indent=2))
    return 0


def cmd_stale(args):
    store_dir = _ensure_store(args.store)
    expected = _check_template(args.expected)
    eligible, excluded = _eligible_planes(store_dir, args.stale_hours)
    rows = []
    for plane_id, rec in eligible:
        if rec.get("template_version") != expected:
            rows.append({
                "plane_id": plane_id,
                "reason": "version-mismatch",
                "template_version": rec.get("template_version"),
            })
    for plane_id, why in excluded:
        rows.append({"plane_id": plane_id, "reason": why, "template_version": None})
    print(json.dumps({"expected": expected, "not_converged": sorted(rows, key=lambda r: r["plane_id"]),
                      "count": len(rows)}, indent=2))
    return 1 if rows else 0


def cmd_cost_summary(args):
    store_dir = _ensure_store(args.store)
    plane_filter = args.plane_id
    if plane_filter:
        _check_id(plane_filter, "--plane-id")
    rows = [r for r in _read_costs(store_dir)
            if plane_filter is None or r.get("plane_id") == plane_filter]

    def _agg(events):
        costs = [r["cost_usd"] for r in events if r.get("cost_usd") is not None]
        durs = [r["duration_s"] for r in events if r.get("duration_s") is not None]
        return {
            "count": len(events),
            "cost_usd_total": round(sum(costs), 4) if costs else 0.0,
            "cost_usd_reported": len(costs),
            "duration_s_median": round(statistics.median(durs), 1) if durs else None,
        }

    per_plane = {}
    for r in rows:
        per_plane.setdefault(r["plane_id"], []).append(r)
    by_event = {}
    for ev in _COST_EVENTS:
        by_event[ev] = _agg([r for r in rows if r.get("event") == ev])
    summary = {
        "planes": len(per_plane),
        "by_event": by_event,
        # D-MT5's measurement: recurring update+rollback cost across template
        # versions, separated from one-time provision cost.
        "recurring_cost_usd_total": round(
            by_event["update"]["cost_usd_total"] + by_event["rollback"]["cost_usd_total"], 4),
        "per_plane": {pid: {ev: _agg([r for r in rs if r.get("event") == ev])
                            for ev in _COST_EVENTS}
                      for pid, rs in sorted(per_plane.items())},
    }
    print(json.dumps(summary, indent=2))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        description="Per-tenant-plane version inventory + operational-cost ledger (#1261)."
    )
    p.add_argument("--store", required=True, help="store directory")
    sub = p.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="register a tenant plane")
    p_reg.add_argument("--plane-id", required=True)
    p_reg.add_argument("--tenant-id", required=True)
    p_reg.add_argument("--template", default=None, help="initial template version")
    p_reg.add_argument("--channel", default="stable")
    p_reg.add_argument("--notes", default="")
    p_reg.set_defaults(func=cmd_register)

    p_dep = sub.add_parser("deploy", help="record a template deployment on a plane")
    p_dep.add_argument("--plane-id", required=True)
    p_dep.add_argument("--template", required=True)
    p_dep.add_argument("--status", default="healthy", choices=("healthy", "degraded"))
    p_dep.add_argument("--notes", default="")
    p_dep.set_defaults(func=cmd_deploy)

    p_ret = sub.add_parser("retire", help="mark a plane retired")
    p_ret.add_argument("--plane-id", required=True)
    p_ret.add_argument("--notes", default="")
    p_ret.set_defaults(func=cmd_retire)

    p_cost = sub.add_parser("cost", help="append an operational-cost event")
    p_cost.add_argument("--plane-id", required=True)
    p_cost.add_argument("--event", required=True, choices=_COST_EVENTS)
    p_cost.add_argument("--duration-s", default=None)
    p_cost.add_argument("--cost-usd", default=None)
    p_cost.add_argument("--notes", default="")
    p_cost.set_defaults(func=cmd_cost)

    p_cen = sub.add_parser("census", help="print the version table + pct census")
    p_cen.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    p_cen.set_defaults(func=cmd_census)

    p_stale = sub.add_parser("stale", help="planes not on the expected template")
    p_stale.add_argument("--expected", required=True, help="expected template version")
    p_stale.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    p_stale.set_defaults(func=cmd_stale)

    p_cs = sub.add_parser("cost-summary", help="D-MT5 operational-cost measurement")
    p_cs.add_argument("--plane-id", default=None)
    p_cs.set_defaults(func=cmd_cost_summary)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    stale_hours = getattr(args, "stale_hours", None)
    # NaN evades `<= 0` (nan <= 0 is False) and would silently mark every
    # record stale — reject it at the boundary like any other bad value.
    if stale_hours is not None and (stale_hours <= 0 or math.isnan(stale_hours)):
        _fail("--stale-hours must be a positive number")
    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - operator contract: one-line error, exit 2
        print(f"plane_inventory: internal error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
