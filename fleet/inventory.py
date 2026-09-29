#!/usr/bin/env python3
"""Fleet version inventory, S1 (issue #607 / G16).

Design: docs/FLEET_VERSION_INVENTORY_DESIGN.md. S1 is the local,
pull-from-existing-artifacts slice: the operator's estate already has
per-box signals (`self_update.py status --json`, the auto-deploy audit
log) and this component collects them into one fleet version table.
No new box-side daemon, no new inbound port — the collector reads files
the updaters already maintain, from a directory per box (rsync/scp them
together, or point --estate at a mounted tree). Live SSH pull is a
later slice; the record schema and the store are unchanged either way.

Subcommands:
  collect   --estate DIR --store DIR [--box-id-map FILE]
      Read per-box artifacts and append one inventory record per box to
      the store's journal, then rebuild the snapshot.
  inventory --store DIR [--staleness-hours N] [--box ID]
      Print the fleet version table (per-box versions + % census). With
      --box, print that box's version history instead.
  drift     --store DIR --expected COMMIT [--staleness-hours N]
      Raw disagreement between reported versions and the expected
      version: policy-held, arc-deferred, suspect, and unexplained rows.
      Without --expected, the fleet-majority commit is used as the
      expected version and labeled as such.
  rebuild   --store DIR
      Rebuild the snapshot from the journal (the snapshot is derived;
      the journal is the source of truth).

Per-box directory layout (each subdir of --estate is one box; the dir
name is the box_id unless --box-id-map remaps it):
  <box>/status.json        self_update.py status --json output
  <box>/audit-tail.jsonl   tail of the box's auto-deploy audit log
  <box>/snapshot.json      fleet/box_snapshot.py output

Store layout:
  <store>/journal.jsonl    append-only observation records
  <store>/snapshot.json    derived: latest record per box + census inputs

Record schema (S1 subset of the design's section 4):
  {schema, box_id, observed_at, reporter, versions{repo_commit,
   toolset_pins, image_version}, last_tick_at{deploy, toolset, image},
   gate{permitted_commit, permitted_toolset_pin, frozen, answer_age_s},
   arc, wave, suspect, suspect_reason, attested, notes}

Rules the code follows (from the design, summarized here so the behavior
is auditable at the call site):
  - observed_at is collector-side; box-side generated_at is kept in the
    payload but never trusted for ordering. A generated_at more than 5
    min in the future is flagged in notes, not dropped.
  - On audit-vs-snapshot disagreement about repo_commit, the box-side
    snapshot is authoritative; the box is marked suspect (flagged, not
    convicted) with the audit's claim kept in suspect_reason.
  - The census denominator is eligible boxes only: boxes whose latest
    record is fresher than the staleness window. Excluded boxes are
    printed alongside the percentage so a 100% census over 2 of 50
    boxes is honest.
  - image_version null means "not applicable" (in-place updater), never
    "unknown". Missing artifacts produce null fields plus notes, never
    a skipped box.

Exit 0 on a printed result, 2 on bad input/arguments. Stdlib only.
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

RECORD_SCHEMA = "fleet-inventory-record/1"
SNAPSHOT_SCHEMA = "fleet-inventory-snapshot/1"
JOURNAL_NAME = "journal.jsonl"
SNAPSHOT_NAME = "snapshot.json"

# Box-side generated_at may be this far in the future before the record is
# flagged (design section 4 open question 4: flag, don't drop).
FUTURE_SKEW_TOLERANCE_S = 300

# Audit events whose timestamp counts as the box's deploy/update tick
# (the "what happened" side of the deploy dimension, design section 2).
_TICK_EVENTS = {"deploy", "check", "rollback"}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value):
    """Parse a timestamp to an aware datetime, or None.

    Accepts ISO-8601 strings (the auto-deploy audit log's `date -u
    +%FT%TZ` shape) and epoch int/float (the real `self_update.py
    status --json` emits `"generated_at": int(time.time())`). Never
    raises; unparseable values are None so the record carries nulls,
    not crashes.
    """
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


def _read_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), None
    except FileNotFoundError:
        return None, "missing"
    except (OSError, ValueError) as exc:
        return None, "unreadable: %s" % exc


def _read_jsonl_file(path):
    """Read a JSONL file; returns (rows, skipped, error). Malformed lines
    are counted in skipped, never fatal to the rest of the file."""
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


# A `to` commit is a usable *state claim* only when the event says the
# box actually landed there. A failed deploy's `to` is an attempt, not a
# state claim — treating it as one flags honest boxes suspect. The set is
# named _STATE_CLAIM_RESULTS (not _SUCCESS_...) because two members are
# not "success" in the colloquial sense, while their `to` genuinely
# reflects box state (verified against deploy/auto-deploy.sh's audit
# calls):
#   - ok / rolled-back / manual-rollback: landed or restored commits.
#   - pull-only: watermark + VERSION advanced to `to`, no components to
#     install because none changed — the box is genuinely at `to`
#     (e.g. a docs-only release).
#   - rollback-unhealthy: the restore landed and the watermark was
#     rewound to `to`; component health degraded separately (the operator
#     was already alerted). The box's files are at `to`.
# Everything else (deploy-fail, precheck-fail, gate-fail, snapshot-fail,
# rollback-failed, checkout-dirty) is an attempt: its `to` says nothing
# about current state.
_STATE_CLAIM_RESULTS = {"ok", "rolled-back", "manual-rollback",
                        "pull-only", "rollback-unhealthy"}


def _newest_tick_ts(audit_rows):
    """Newest timestamp across all tick events (the liveness datum for
    the design's 'whose last update tick ran after the wave's promotion
    timestamp'). `check` events count: a box that only ever checks is
    alive but not converging."""
    latest = None
    for row in audit_rows or []:
        if not isinstance(row, dict) or row.get("event") not in _TICK_EVENTS:
            continue
        ts = _parse_ts(row.get("ts"))
        if ts is not None and (latest is None or ts > latest):
            latest = ts
    return latest


def _latest_claim_event(audit_rows):
    """Newest *successful* claim-bearing event.

    Only deploy/rollback events whose result is in
    _STATE_CLAIM_RESULTS carry a usable `to` claim. A failed attempt
    must not shadow an older successful claim (the same shadowing the
    `check` events were fixed for), so failed claim-bearing events are
    skipped — but the newest skipped failure is reported so the record
    stays honest about what the audit tail said.

    Returns (to, result, skipped_failed): the newest successful claim's
    `to`/result, plus the result of the newest *failed* claim-bearing
    event newer than that claim (None when no such failure exists).
    """
    best_to, best_result, best_ts = None, None, None
    failed_ts, failed_result = None, None
    for row in audit_rows or []:
        if not isinstance(row, dict) or row.get("event") not in (
                "deploy", "rollback"):
            continue
        to = row.get("to")
        if not to:
            continue
        ts = _parse_ts(row.get("ts"))
        if ts is None:
            continue
        result = row.get("result")
        if result in _STATE_CLAIM_RESULTS:
            if best_ts is None or ts > best_ts:
                best_ts, best_to, best_result = ts, to, result
        elif failed_ts is None or ts > failed_ts:
            failed_ts, failed_result = ts, result
    skipped = None
    if failed_ts is not None and (best_ts is None or failed_ts > best_ts):
        skipped = failed_result
    return best_to, best_result, skipped


def _has_tick_events(audit_rows):
    return any(isinstance(r, dict) and r.get("event") in _TICK_EVENTS
               for r in audit_rows or [])


def collect_box(box_dir, box_id, observed_at):
    """Build one inventory record from a per-box artifact directory.

    Never raises for bad artifacts: they become null fields + notes.
    Returns the record.
    """
    notes = []

    status, status_err = _read_json_file(os.path.join(box_dir, "status.json"))
    if status_err:
        notes.append("status.json %s" % status_err)
    audit_rows, audit_skipped, audit_err = _read_jsonl_file(
        os.path.join(box_dir, "audit-tail.jsonl"))
    if audit_err:
        notes.append("audit-tail.jsonl %s" % audit_err)
    elif audit_skipped:
        # Corrupt audit lines are a trust-relevant input: surface the
        # count in the record instead of silently dropping it (the
        # tick-selection below already ignores non-tick rows).
        notes.append("audit tail had %d malformed line(s) skipped"
                     % audit_skipped)
    snapshot, snapshot_err = _read_json_file(
        os.path.join(box_dir, "snapshot.json"))
    if snapshot_err:
        notes.append("snapshot.json %s" % snapshot_err)

    versions = {"repo_commit": None, "toolset_pins": None,
                "image_version": None}
    last_tick = {"deploy": None, "toolset": None, "image": None}
    gate = {"permitted_commit": None, "permitted_toolset_pin": None,
            "frozen": None, "answer_age_s": None}
    arc = None
    suspect = False
    suspect_reason = None

    # Toolset dimension: the status payload is carried as-is (design
    # section 4 — the collector does not re-interpret pin warnings).
    if isinstance(status, dict):
        versions["toolset_pins"] = status
        generated_at = _parse_ts(status.get("generated_at"))
        if generated_at is not None:
            last_tick["toolset"] = generated_at.isoformat()
            observed_dt = _parse_ts(observed_at)
            if observed_dt is not None and (
                    generated_at - observed_dt).total_seconds() > (
                    FUTURE_SKEW_TOLERANCE_S):
                # Flag, don't drop: clock skew poisons nothing because
                # ordering uses observed_at (design open question 4).
                notes.append(
                    "status generated_at is %.0fs in the future; kept as-is"
                    % (generated_at - observed_dt).total_seconds())
        else:
            notes.append("status.json has no parseable generated_at")
    elif status is not None:
        notes.append("status.json is not an object; ignored")

    # Deploy dimension, split into two concepts the S1 design's cross-check
    # needs separately (design section 7):
    #   - liveness: when did the box last tick (all tick events count);
    #   - claim: what should the box be on (only a *successful* deploy or
    #     rollback's `to`; a failed deploy's `to` is an attempt, and a
    #     `check` carries no `to` at all, so neither can shadow a claim).
    newest_tick = _newest_tick_ts(audit_rows)
    if newest_tick is not None:
        last_tick["deploy"] = newest_tick.isoformat()
    elif audit_rows is not None and not _has_tick_events(audit_rows):
        notes.append("audit tail has no deploy/check/rollback events")
    claim_to, claim_result, skipped_failed = _latest_claim_event(audit_rows)
    if skipped_failed is not None and claim_to is not None:
        notes.append(
            "newer deploy attempt failed (result=%s); the cross-check used "
            "the newest successful claim (result=%s) instead"
            % (skipped_failed, claim_result))

    # Box-side snapshot: repo_commit, gate state, arc, image version.
    # On disagreement with a successful audit claim, the snapshot wins
    # (it is a point-in-time read of deployed state; the tail is a
    # history of claims) and the box is marked suspect — flagged, not
    # convicted (design section 7).
    snapshot_commit = None
    if isinstance(snapshot, dict):
        snapshot_commit = snapshot.get("repo_commit")
        versions["image_version"] = snapshot.get("image_version")
        gate_state = snapshot.get("gate")
        if isinstance(gate_state, dict):
            gate["frozen"] = gate_state.get("frozen")
            gate["answer_age_s"] = gate_state.get("answer_age_s")
        # The box-side snapshot sketch (design section 5) calls this
        # field arc_active; the record schema (section 4) calls it arc.
        arc = snapshot.get("arc_active")
        snap_note = snapshot.get("note")
        if snap_note:
            notes.append("box snapshot note: %s" % snap_note)
    elif snapshot is not None:
        notes.append("snapshot.json is not an object; ignored")

    if snapshot_commit:
        versions["repo_commit"] = snapshot_commit
        if claim_to and claim_to != snapshot_commit:
            suspect = True
            suspect_reason = (
                "audit tail's newest successful deploy claims to=%s but "
                "the box snapshot reports repo_commit=%s; snapshot "
                "authoritative" % (claim_to, snapshot_commit))
    elif claim_to:
        # No box snapshot: fall back to the newest successful claim, loudly.
        versions["repo_commit"] = claim_to
        notes.append(
            "repo_commit taken from audit tail (no box snapshot); newest "
            "successful claim result: %s" % (claim_result,))
    elif skipped_failed is not None:
        # The newest claim-bearing event failed and no earlier successful
        # claim exists: nothing to infer, said loudly.
        notes.append(
            "newest deploy claim failed (result=%s) with no earlier "
            "successful claim; no box snapshot, repo_commit unknown"
            % (skipped_failed,))

    record = {
        "schema": RECORD_SCHEMA,
        "box_id": box_id,
        "observed_at": observed_at,
        # S1 value; design section 4's enum predates the pull collector —
        # the design doc's S1 note documents the deviation.
        "reporter": "estate-collector-s1",
        "versions": versions,
        "last_tick_at": last_tick,
        "gate": gate,
        "arc": arc,
        "wave": None,          # wave manifests are the G15 controller's
                               # slice (design section 6); S1 has none.
        "suspect": suspect,
        "suspect_reason": suspect_reason,
        "attested": False,     # self-reported, unweighted in S1
        "notes": notes,
    }
    return record


def _ensure_store(store_dir):
    try:
        os.makedirs(store_dir, exist_ok=True)
    except OSError as exc:
        return "cannot create store dir %s: %s" % (store_dir, exc)
    return None


def append_journal(store_dir, records):
    """Append records to the journal. Returns (line_count, error)."""
    err = _ensure_store(store_dir)
    if err:
        return None, err
    journal_path = os.path.join(store_dir, JOURNAL_NAME)
    try:
        with open(journal_path, "a", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
            fh.flush()
    except OSError as exc:
        return None, "cannot append to journal: %s" % exc
    return rebuild_snapshot(store_dir)


def rebuild_snapshot(store_dir):
    """Rebuild snapshot.json from journal.jsonl. Returns (count, error)."""
    err = _ensure_store(store_dir)
    if err:
        return None, err
    journal_path = os.path.join(store_dir, JOURNAL_NAME)
    boxes = {}
    total = 0
    malformed = 0
    try:
        with open(journal_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    malformed += 1
                    continue
                if not isinstance(record, dict) or "box_id" not in record:
                    malformed += 1
                    continue
                if not isinstance(record["box_id"], str) or not record[
                        "box_id"]:
                    # A non-string box_id (hand-poisoned journal, or a
                    # record written before the collect-time validation)
                    # cannot key the snapshot: count it malformed rather
                    # than crashing every rebuild forever.
                    malformed += 1
                    continue
                for field in ("versions", "last_tick_at", "gate"):
                    value = record.get(field)
                    if value is not None and not isinstance(value, dict):
                        record = None
                        break
                if record is None:
                    malformed += 1
                    continue
                total += 1
                boxes[record["box_id"]] = record
    except FileNotFoundError:
        total = 0  # empty store: snapshot with zero boxes
    except OSError as exc:
        return None, "cannot read journal: %s" % exc

    snapshot = {
        "schema": SNAPSHOT_SCHEMA,
        "generated_at": _now_iso(),
        "records_replayed": total,
        "malformed_lines_skipped": malformed,
        "boxes": boxes,
    }
    snapshot_path = os.path.join(store_dir, SNAPSHOT_NAME)
    tmp_path = snapshot_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, indent=2, sort_keys=True)
            fh.write("\n")
        # Atomic publish: a crash mid-write leaves the previous good
        # snapshot in place instead of a torn file that reads as "no
        # snapshot" to every consumer.
        os.replace(tmp_path, snapshot_path)
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return None, "cannot write snapshot: %s" % exc
    return total, None


def load_snapshot(store_dir):
    """Returns (snapshot, error)."""
    snapshot_path = os.path.join(store_dir, SNAPSHOT_NAME)
    data, err = _read_json_file(snapshot_path)
    if err:
        return None, "no snapshot at %s (%s); run collect first" % (
            snapshot_path, err)
    if not isinstance(data, dict) or data.get("schema") != SNAPSHOT_SCHEMA:
        return None, "snapshot at %s is not a fleet inventory snapshot" % (
            snapshot_path,)
    return data, None


def _is_eligible(record, cutoff_dt):
    """Eligible = latest record fresher than the staleness window. S1
    eligibility (design section 6) without wave manifests: freshness is
    the stand-in; the excluded counts are printed with the census."""
    observed = _parse_ts(record.get("observed_at"))
    return observed is not None and observed >= cutoff_dt


def _short_commit(commit):
    if not commit:
        return "(no report)"
    return str(commit)[:12]


def cmd_inventory(store_dir, staleness_hours, box_id):
    snapshot, err = load_snapshot(store_dir)
    if err:
        return err
    boxes = snapshot.get("boxes", {})

    if box_id:
        return _print_box_history(store_dir, box_id)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=staleness_hours)
    eligible = {}
    stale = []
    for bid, record in sorted(boxes.items()):
        if _is_eligible(record, cutoff):
            eligible[bid] = record
        else:
            stale.append(bid)

    lines = []
    lines.append("fleet version table (snapshot %s)" % snapshot.get(
        "generated_at", "unknown"))
    lines.append("")

    # Per-box rows.
    lines.append("%-24s %-14s %-12s %-8s %s" % (
        "box", "repo_commit", "toolset_tick", "frozen", "flags"))
    for bid, record in sorted(boxes.items()):
        ver = record.get("versions", {}) or {}
        tick = record.get("last_tick_at", {}) or {}
        gate = record.get("gate", {}) or {}
        flags = []
        if bid not in eligible:
            flags.append("stale")
        if record.get("suspect"):
            flags.append("suspect")
        frozen = gate.get("frozen")
        lines.append("%-24s %-14s %-12s %-8s %s" % (
            bid,
            _short_commit(ver.get("repo_commit")),
            (tick.get("toolset") or "n/a")[:10],
            "yes" if frozen else ("no" if frozen is False else "n/a"),
            ",".join(flags) or "-",
        ))

    # Census: % of eligible boxes per repo_commit, with the denominator
    # and exclusions printed so the percentage is honest.
    lines.append("")
    census = {}
    for record in eligible.values():
        ver = record.get("versions", {}) or {}
        key = _short_commit(ver.get("repo_commit"))
        census[key] = census.get(key, 0) + 1
    denom = len(eligible)
    lines.append("census (eligible %d of %d boxes; %d stale, excluded):"
                 % (denom, len(boxes), len(stale)))
    if denom:
        for commit, count in sorted(census.items(),
                                    key=lambda kv: kv[1], reverse=True):
            lines.append("  %s: %d/%d boxes (%.1f%%)" % (
                commit, count, denom, 100.0 * count / denom))
    else:
        lines.append("  no eligible boxes in the staleness window "
                     "(--staleness-hours %s)" % staleness_hours)
    if stale:
        lines.append("stale boxes: %s" % ", ".join(sorted(stale)))
    print("\n".join(lines))
    return None


def _print_box_history(store_dir, box_id):
    journal_path = os.path.join(store_dir, JOURNAL_NAME)
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
        return "no journal at %s; run collect first" % journal_path
    except OSError as exc:
        return "cannot read journal: %s" % exc
    if not history:
        return "box %s has no records in the journal" % box_id
    lines = ["version history for box %s (%d observations, newest first):"
             % (box_id, len(history))]
    for record in reversed(history):
        ver = record.get("versions", {}) or {}
        tick = record.get("last_tick_at", {}) or {}
        lines.append("  %s  repo=%s  toolset_tick=%s  suspect=%s" % (
            record.get("observed_at", "?"),
            _short_commit(ver.get("repo_commit")),
            (tick.get("deploy") or tick.get("toolset") or "n/a")[:19],
            "yes" if record.get("suspect") else "no",
        ))
    print("\n".join(lines))
    return None


def cmd_drift(store_dir, expected, staleness_hours):
    snapshot, err = load_snapshot(store_dir)
    if err:
        return err
    boxes = snapshot.get("boxes", {})
    cutoff = datetime.now(timezone.utc) - timedelta(hours=staleness_hours)
    eligible = {bid: r for bid, r in boxes.items()
                if _is_eligible(r, cutoff)}

    expected_source = "--expected"
    if not expected:
        # Majority commit among eligible boxes is the S1 stand-in for a
        # wave's permitted version (design section 6: drift is the raw
        # disagreement list; the actionable "missed the window" subset
        # needs wave manifests, which are G15's slice).
        counts = {}
        for record in eligible.values():
            ver = record.get("versions", {}) or {}
            commit = ver.get("repo_commit")
            counts[commit] = counts.get(commit, 0) + 1
        if counts:
            top = max(counts.values())
            winners = [c for c in counts if counts[c] == top]
            expected = max(winners, key=str)  # deterministic pick
            if len(winners) == 1:
                expected_source = "fleet majority"
            else:
                # No majority exists: say so explicitly rather than
                # anointing one side of the tie (the tiebreak stays
                # deterministic so output is stable run to run).
                expected_source = ("tie for majority (picked %s "
                                   "deterministically)" % _short_commit(
                                       expected))
        else:
            expected = None
            expected_source = "none (no eligible boxes)"

    rows = []
    for bid, record in sorted(eligible.items()):
        ver = record.get("versions", {}) or {}
        gate = record.get("gate", {}) or {}
        commit = ver.get("repo_commit")
        # Compare short forms: the inventory table only displays 12-char
        # prefixes, so an operator copying the expected commit from the
        # table must match the box on it. A 48-bit prefix collision is
        # negligible at fleet scale, and this is consistent with how the
        # census buckets commits.
        if _short_commit(commit) == _short_commit(expected):
            continue
        if gate.get("frozen"):
            reason = "policy-held (frozen)"
        elif record.get("arc"):
            reason = "deferred (active tenant arc)"
        elif record.get("suspect"):
            reason = "suspect report (%s)" % (
                record.get("suspect_reason") or "see record")
        else:
            reason = "unexplained"
        rows.append((bid, _short_commit(commit), reason))

    lines = ["fleet drift: %d of %d eligible boxes differ from expected "
             "%s (%s)" % (
                 len(rows), len(eligible), _short_commit(expected),
                 expected_source)]
    for bid, commit, reason in rows:
        lines.append("  %-24s %-14s %s" % (bid, commit, reason))
    if not rows:
        lines.append("  none")
    print("\n".join(lines))
    return None


def cmd_collect(estate_dir, store_dir, box_id_map):
    if not os.path.isdir(estate_dir):
        return "estate dir %s does not exist or is not a directory" % estate_dir
    mapping = {}
    if box_id_map:
        mapping, map_err = _read_json_file(box_id_map)
        if map_err:
            return "box-id-map %s: %s" % (box_id_map, map_err)
        if not isinstance(mapping, dict):
            return "box-id-map %s is not an object" % box_id_map

    try:
        entries = sorted(os.listdir(estate_dir))
    except OSError as exc:
        return "cannot list estate dir %s: %s" % (estate_dir, exc)
    box_dirs = [e for e in entries
                if os.path.isdir(os.path.join(estate_dir, e))]
    if not box_dirs:
        return "no per-box directories found in %s" % estate_dir

    observed_at = _now_iso()
    records = []
    failed = []
    for dirname in box_dirs:
        box_id = mapping.get(dirname, dirname)
        if not isinstance(box_id, str) or not box_id:
            # A non-string box_id would poison the journal (JSON allows
            # it, but the snapshot is keyed on it) and brick every later
            # collect/rebuild — skip the box loudly instead.
            failed.append("%s: box_id map produced non-string box_id %r; "
                          "skipped" % (dirname, box_id))
            continue
        try:
            records.append(collect_box(os.path.join(estate_dir, dirname),
                                       box_id, observed_at))
        except Exception as exc:  # one bad box must not sink the collect
            failed.append("%s: %s" % (dirname, exc))

    total, err = append_journal(store_dir, records)
    if err:
        return err
    print("collected %d boxes into %s (%s journal lines replayed)"
          % (len(records), store_dir, total))
    for f in failed:
        print("warning: collect failed for %s" % f, file=sys.stderr)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fleet version inventory, S1 (G16/#607): aggregate "
                    "per-box version reports into one fleet version table.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect",
                               help="collect per-box artifacts into the store")
    p_collect.add_argument("--estate", required=True,
                           help="dir with one subdir per box")
    p_collect.add_argument("--store", required=True,
                           help="store dir (journal.jsonl + snapshot.json)")
    p_collect.add_argument("--box-id-map", default=None,
                           help="JSON object mapping estate dir names to "
                                "box_ids (default: dir name is the box_id)")

    p_inv = sub.add_parser("inventory", help="print the fleet version table")
    p_inv.add_argument("--store", required=True)
    p_inv.add_argument("--staleness-hours", type=float, default=24)
    p_inv.add_argument("--box", default=None,
                       help="print this box's version history instead")

    p_drift = sub.add_parser("drift", help="boxes disagreeing with the "
                                          "expected version")
    p_drift.add_argument("--store", required=True)
    p_drift.add_argument("--expected", default=None,
                         help="expected repo commit — full or the 12-char "
                              "prefix from the inventory table (default: "
                              "fleet majority among eligible boxes)")
    p_drift.add_argument("--staleness-hours", type=float, default=24)

    p_rebuild = sub.add_parser("rebuild",
                               help="rebuild the snapshot from the journal")
    p_rebuild.add_argument("--store", required=True)

    args = parser.parse_args(argv)
    if args.command in ("inventory", "drift"):
        # timedelta(hours=...) blows up on nan/inf; reject non-finite or
        # negative windows at the boundary with a clean exit 2 instead.
        window = args.staleness_hours
        if not math.isfinite(window) or window < 0:
            print("error: --staleness-hours must be a finite number >= 0, "
                  "got %r" % (window,), file=sys.stderr)
            return 2
    if args.command == "collect":
        err = cmd_collect(args.estate, args.store, args.box_id_map)
    elif args.command == "inventory":
        err = cmd_inventory(args.store, args.staleness_hours, args.box)
    elif args.command == "drift":
        err = cmd_drift(args.store, args.expected, args.staleness_hours)
    elif args.command == "rebuild":
        total, err = rebuild_snapshot(args.store)
        if err is None:
            print("rebuilt snapshot from %s journal lines" % total)
    else:
        err = "unknown command %s" % args.command
    if err:
        print("error: %s" % err, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
