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
      the store's journal, then rebuild the snapshot. Also canonicalizes
      each box's audit tail into the update-event journal (G17/#608 S1)
      and evaluates the fleet alert rules.
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
  prune     --store DIR
      Drop inventory journal rows older than 90 days (G17 S2 retention
      discipline); the snapshot is rebuilt from the pruned journal.
  events    --store DIR [--box ID] [--wave WAVE]
      Print the update-event journal (per-box outcome series; G17 S1).
  events watch --store DIR
      List unacknowledged alerts; exit 1 when any are pending, 0 when
      the queue is clear.
  events ack --store DIR --alert-id ID
      Mark one alert acknowledged.
  events crosscheck --store DIR [--box ID]
      Check deploy/succeeded claims against the inventory journal
      (event<->inventory cross-check, G17 S2): confirmed, violation
      (flagged, not convicted), or inconclusive (missing evidence);
      exit 1 on any violation, 0 otherwise.
  events prune --store DIR
      Apply the event-journal retention policy (G17 S2): rows older
      than 30 days are compacted into per-day outcome histograms in
      events_histograms.jsonl, rows older than 90 days are dropped;
      old acknowledged alerts are dropped, unacknowledged never.

Per-box directory layout (each subdir of --estate is one box; the dir
name is the box_id unless --box-id-map remaps it):
  <box>/status.json        self_update.py status --json output
  <box>/audit-tail.jsonl   tail of the box's auto-deploy audit log
  <box>/update-events.jsonl
      the box's S2 event journal (native standard-shape rows from the
      wired producers, docs/UPDATE_EVENT_REPORTING.md §S2): the
      event-journal leg reads it INSTEAD of translating audit tails
      (collect_box_events's exclusive read switch, #1649) — the audit
      tail still feeds the version-inventory leg above
  <box>/snapshot.json      fleet/box_snapshot.py output

Store layout:
  <store>/journal.jsonl    append-only observation records
  <store>/snapshot.json    derived: latest record per box + census inputs

Record schema (S1 subset of the design's section 4):
  {schema, box_id, observed_at, emitted_at, reporter, versions{repo_commit,
   toolset_pins, image_version}, last_tick_at{deploy, toolset, image},
   gate{permitted_commit, permitted_toolset_pin, frozen, answer_age_s,
   generated_at}, arc, wave, suspect, suspect_reason, attested, notes}

Rules the code follows (from the design, summarized here so the behavior
is auditable at the call site):
  - observed_at is collector-side; box-side generated_at is kept in the
    payload but never trusted for ordering. A generated_at more than 5
    min in the future is flagged in notes, not dropped.
  - emitted_at is the box clock's snapshot-emission time (carried from
    the box snapshot verbatim); observed_at is the collector's receive
    time. observed_at - emitted_at is the transport/collection delay and
    a negative value is clock skew, not an error. A snapshot emitted_at
    more than 5 min in the future (FUTURE_SKEW_TOLERANCE_S) is flagged
    in notes, not dropped — the same flag-don't-drop convention as the
    status generated_at above.
  - answer_age_s is the box-local emit-time convenience: the box froze
    it when the snapshot was emitted, so it only ever grows stale after
    that. Readers recompute the true gate age as
    max(0, now - gate.generated_at) (aware UTC), never from answer_age_s.
    gate.generated_at null means the box couldn't parse the hook's
    timestamp — the age is then uncomputable, not zero.
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

Exit 0 on a printed result, 2 on bad input/arguments. An unexpected
internal failure also exits 2 with a one-line message, never a bare
traceback (the operator's contract is the exit code, not the stack).
Stdlib only.
"""

import argparse
import json
import math
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

# Sibling module (fleet/events.py): the G17 S1 update-event canonicalizer,
# event journal, and alert rules. Imported as a sibling because the fleet
# modules are script-run (python3 fleet/inventory.py puts fleet/ on
# sys.path); the hermetic suite exercises the CLIs through subprocess,
# never through imports.
import events

# Sibling module (fleet/attest.py): the #1516 S3 box-event attestation
# mechanism and write-once box-key registry. Same sibling-import
# convention as events above.
import attest

RECORD_SCHEMA = "fleet-inventory-record/1"
SNAPSHOT_SCHEMA = "fleet-inventory-snapshot/1"
JOURNAL_NAME = "journal.jsonl"
SNAPSHOT_NAME = "snapshot.json"

# Per-rebuild temp-file prefix (issue #716): rebuild_snapshot() publishes
# through a process-unique `snapshot.json.tmp.<random>.<pid>` path so
# concurrent collects never share the tmp name. Crash-orphaned tmps are
# swept by _sweep_stale_snapshot_tmps() once they are older than
# _SNAPSHOT_TMP_MAX_AGE_S.
_SNAPSHOT_TMP_PREFIX = SNAPSHOT_NAME + ".tmp."
_SNAPSHOT_TMP_MAX_AGE_S = 3600

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


def _read_json_file_nofollow(path):
    """Read a JSON file with O_NOFOLLOW; returns (data, err).

    Security (#1860 follow-up): status.json and snapshot.json are
    box-pulled estate artifacts like the audit tail — a symlinked
    plant would resolve operator-side and feed the version record
    (toolset pins carried as-is, repo_commit/suspect determination).
    Goes through events.open_nofollow_read (the shared estate-artifact
    open discipline); a plant is a "refused: ..." err the caller
    treats as fail-closed and loud.
    """
    fh, err = events.open_nofollow_read(path)
    if err:
        return None, err
    try:
        with fh:
            return json.load(fh), None
    except (OSError, ValueError) as exc:
        return None, "unreadable: %s" % exc


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
# rollback-failed) is an attempt: its `to` says nothing
# about current state. (`checkout-dirty` belongs in this class too — it is
# retired and no longer emitted, but may appear in older audit tails.)
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

    status, status_err = _read_json_file_nofollow(
        os.path.join(box_dir, "status.json"))
    if status_err:
        if events.is_symlink_refusal(status_err):
            # Security (#1860 follow-up): the status payload feeds
            # versions.toolset_pins (carried as-is) and
            # last_tick.toolset — a plant is refused fail-closed and
            # loudly; those fields stay null this round.
            notes.append("status.json refused as a symlink plant; "
                         "toolset fields from the status payload are "
                         "null this round")
        else:
            notes.append("status.json %s" % status_err)
    audit_rows, audit_skipped, audit_err = \
        events.read_audit_tail_nofollow(box_dir)
    if audit_err:
        if events.is_symlink_refusal(audit_err):
            # Security (#1860): the audit tail is the only producer of
            # the tick-selection below — a symlink plant is refused
            # fail-closed and loudly; there is no fallback producer.
            notes.append("audit-tail.jsonl refused as a symlink plant; "
                         "version fields from the audit tail are null "
                         "this round")
        else:
            notes.append("audit-tail.jsonl %s" % audit_err)
    elif audit_skipped:
        # Corrupt audit lines are a trust-relevant input: surface the
        # count in the record instead of silently dropping it (the
        # tick-selection below already ignores non-tick rows).
        notes.append("audit tail had %d malformed line(s) skipped"
                     % audit_skipped)
    snapshot, snapshot_err = _read_json_file_nofollow(
        os.path.join(box_dir, "snapshot.json"))
    if snapshot_err:
        if events.is_symlink_refusal(snapshot_err):
            # Security (#1860 follow-up): the snapshot feeds
            # versions.repo_commit/image_version and the gate/arc
            # state — a plant is refused fail-closed and loudly;
            # those fields stay null this round.
            notes.append("snapshot.json refused as a symlink plant; "
                         "snapshot-derived fields are null this round")
        else:
            notes.append("snapshot.json %s" % snapshot_err)

    versions = {"repo_commit": None, "toolset_pins": None,
                "image_version": None}
    last_tick = {"deploy": None, "toolset": None, "image": None}
    gate = {"permitted_commit": None, "permitted_toolset_pin": None,
            "frozen": None, "answer_age_s": None, "generated_at": None}
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
    emitted_at = None
    if isinstance(snapshot, dict):
        snapshot_commit = snapshot.get("repo_commit")
        versions["image_version"] = snapshot.get("image_version")
        gate_state = snapshot.get("gate")
        if isinstance(gate_state, dict):
            gate["frozen"] = gate_state.get("frozen")
            gate["answer_age_s"] = gate_state.get("answer_age_s")
            # D-SC-2 (#1660): the hook's own timestamp, carried verbatim
            # (the box already nulled it when unparseable) so readers can
            # recompute the true gate age instead of trusting the
            # emit-time-frozen answer_age_s.
            gate["generated_at"] = gate_state.get("generated_at")
        # D-SC-1 (#1660): the box's snapshot-emission time (box clock),
        # carried verbatim; observed_at stays the collector's receive
        # time so transport/collection delay is computable.
        emitted_at = snapshot.get("emitted_at")
        # The box-side snapshot sketch (design section 5) calls this
        # field arc_active; the record schema (section 4) calls it arc.
        arc = snapshot.get("arc_active")
        snap_note = snapshot.get("note")
        if snap_note:
            notes.append("box snapshot note: %s" % snap_note)
    elif snapshot is not None:
        notes.append("snapshot.json is not an object; ignored")

    # D-SC-1 skew discipline (#1660): emitted_at - observed_at inherits
    # the FUTURE_SKEW_TOLERANCE_S flag-don't-drop convention. A negative
    # observed_at - emitted_at is clock skew (the box clock runs ahead of
    # the collector), not an error — the record keeps the value as-is.
    emitted_dt = _parse_ts(emitted_at)
    if isinstance(snapshot, dict) and emitted_at is not None \
            and emitted_dt is None:
        notes.append("snapshot has no parseable emitted_at; kept as-is")
    observed_dt = _parse_ts(observed_at)
    if emitted_dt is not None and observed_dt is not None and (
            emitted_dt - observed_dt).total_seconds() > (
            FUTURE_SKEW_TOLERANCE_S):
        notes.append(
            "snapshot emitted_at is %.0fs in the future; kept as-is"
            % (emitted_dt - observed_dt).total_seconds())

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
        "emitted_at": emitted_at,
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
    """Append records to the journal. Returns (line_count, error).

    Each record is one newline-terminated line written as a single
    write() syscall (line buffering), which O_APPEND keeps atomic in
    positioning under concurrent writers (e.g. overlapping collect
    crons). fsync before returning gives the "crash-safe" guarantee
    the design claims: a collect that exits 0 survives an OS crash.

    The append runs under the store-scoped journal lock (events.py):
    `prune` rewrites the journal with os.replace, and an append that
    opened the old inode before the replace would journal into the
    void. The lock serializes the two; a lock failure fails the
    collect loudly instead of journaling unsynchronized.
    """
    err = _ensure_store(store_dir)
    if err:
        return None, err
    try:
        with events.journal_lock(store_dir):
            journal_path = os.path.join(store_dir, JOURNAL_NAME)
            try:
                with open(journal_path, "a", encoding="utf-8",
                          buffering=1) as fh:
                    for record in records:
                        fh.write(json.dumps(record, sort_keys=True) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
            except OSError as exc:
                return None, "cannot append to journal: %s" % exc
    except events.JournalLockError as exc:
        return None, str(exc)
    return rebuild_snapshot(store_dir)


def _sweep_stale_snapshot_tmps(store_dir):
    """Remove crash-orphaned snapshot tmp files older than one hour.

    With per-rebuild unique tmp paths (issue #716), a crash between the
    tmp write and os.replace() leaves a stale `snapshot.json.tmp.*` file
    behind instead of a torn snapshot. Sweep only names carrying the tmp
    prefix (plus the pre-#716 shared `snapshot.json.tmp` legacy name) AND
    older than _SNAPSHOT_TMP_MAX_AGE_S — a rebuild runs in seconds, so
    anything this old cannot be a live writer; the age gate is what makes
    the unlink safe under concurrent collects. Best effort: never fails
    the rebuild.
    """
    cutoff = time.time() - _SNAPSHOT_TMP_MAX_AGE_S
    legacy = SNAPSHOT_NAME + ".tmp"
    try:
        names = os.listdir(store_dir)
    except OSError:
        return
    for name in names:
        if name != legacy and not name.startswith(_SNAPSHOT_TMP_PREFIX):
            continue
        path = os.path.join(store_dir, name)
        try:
            if os.path.isfile(path) and os.stat(path).st_mtime < cutoff:
                os.unlink(path)
        except OSError:
            pass


def rebuild_snapshot(store_dir):
    """Rebuild snapshot.json from journal.jsonl. Returns (count, error)."""
    err = _ensure_store(store_dir)
    if err:
        return None, err
    _sweep_stale_snapshot_tmps(store_dir)
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
    # Issue #716: overlapping `collect` runs share the store, so the tmp
    # file must not be a shared name. Every rebuild writes to a
    # process-unique tmp path (pid is in the name; tempfile adds the
    # random suffix) — two publishers never share the tmp name, so one
    # collect's os.replace() can no longer pull the path out from under
    # another collect's still-open write and fail it with "cannot write
    # snapshot". The atomic-rename publication itself is unchanged.
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=store_dir,
                                         prefix=_SNAPSHOT_TMP_PREFIX,
                                         suffix=".%d" % os.getpid(),
                                         delete=False,
                                         encoding="utf-8") as fh:
            json.dump(snapshot, fh, indent=2, sort_keys=True)
            fh.write("\n")
            tmp_path = fh.name
        # Atomic publish: a crash mid-write leaves the previous good
        # snapshot in place instead of a torn file that reads as "no
        # snapshot" to every consumer.
        os.replace(tmp_path, snapshot_path)
        tmp_path = None  # replaced away; nothing to clean up
    except OSError as exc:
        if tmp_path is not None:
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


def prune_journal(store_dir, now=None):
    """Drop inventory journal rows whose observed_at is >= 90 days old —
    the G17 S2 retention discipline, shared with the event journal
    (events.py's RETENTION_HISTOGRAM_DAYS). Rows with missing/
    unparseable/future observed_at are kept: prune never drops what it
    cannot date and never prunes the future. Malformed lines are
    preserved verbatim.

    The snapshot is rebuilt from the pruned journal so snapshot.json
    stays journal-consistent: a box whose only records expired
    disappears from the snapshot, honestly — expired evidence is not
    evidence. The load -> os.replace sequence runs under the
    store-scoped journal lock (the same lock append_journal takes): it
    would otherwise race an overlapping collect's append, whose rows
    could land in the replaced-away inode and be lost. Returns
    (summary, error); summary holds kept / dropped /
    skipped_undatable counts.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(days=events.RETENTION_HISTOGRAM_DAYS)
    try:
        with events.journal_lock(store_dir):
            items, err = events.read_journal_raw(
                os.path.join(store_dir, JOURNAL_NAME))
            if err:
                return None, err
            kept_texts = []
            summary = {"kept": 0, "dropped": 0, "skipped_undatable": 0}
            for text, record, verbatim in items:
                if verbatim:
                    kept_texts.append(text)
                    continue
                observed = _parse_ts(record.get("observed_at"))
                if observed is None or observed > now:
                    kept_texts.append(text)
                    if observed is None:
                        summary["skipped_undatable"] += 1
                    else:
                        summary["kept"] += 1
                    continue
                if observed <= cutoff:
                    summary["dropped"] += 1
                else:
                    kept_texts.append(text)
                    summary["kept"] += 1
            if summary["dropped"]:
                err = events.rewrite_journal_atomic(
                    os.path.join(store_dir, JOURNAL_NAME), kept_texts)
                if err:
                    return None, err
    except events.JournalLockError as exc:
        return None, str(exc)
    if summary["dropped"]:
        _, err = rebuild_snapshot(store_dir)
        if err:
            return None, err
    return summary, None


def cmd_prune(store_dir):
    """Prune the inventory journal per the retention policy; prints a
    one-line summary. Returns an error string or None (exit-2 class)."""
    if os.path.lexists(store_dir) and not os.path.isdir(store_dir):
        return "store path is not a directory: %s" % store_dir
    if not os.path.isdir(store_dir):
        return "store not found: %s" % store_dir
    summary, err = prune_journal(store_dir)
    if err:
        return err
    print("fleet inventory: pruned %d journal row(s) older than %d days; "
          "%d kept, %d undatable kept"
          % (summary["dropped"], events.RETENTION_HISTOGRAM_DAYS,
             summary["kept"], summary["skipped_undatable"]))
    return None


def _is_eligible(record, cutoff_dt):
    """Eligible = latest record fresher than the staleness window. S1
    eligibility (design section 6) without wave manifests: freshness is
    the stand-in; the excluded counts are printed with the census."""
    observed = _parse_ts(record.get("observed_at"))
    return observed is not None and observed >= cutoff_dt


def _box_sort_key(box_item):
    """Sort key for (box_id, record) snapshot entries.

    Total-order by construction: the str() coercion means a hand-poisoned
    snapshot can never make sorted() raise TypeError here (FOLLOW-fleet1
    from PR #715's review). JSON object keys are always strings, so on
    the real store this is the identity on the key — the coercion is
    belt-and-suspenders, not a behavior change.
    """
    return str(box_item[0])


def _short_commit(commit):
    if not commit:
        return "(no report)"
    return str(commit)[:12]


def _gate_age_s(gate, now):
    """Recomputed gate-answer age in seconds (D-SC-4, #1632).

    Returns (age_s_or_none, emit_time_fallback_bool). Prefers the true
    age recomputed from gate.generated_at (aware UTC, floored at 0 —
    the #1660 fields make this possible); falls back to the box's
    emit-time answer_age_s when generated_at is null or unparseable,
    flagged so the reader knows that number froze at snapshot emission
    and only grows stale afterwards. Uncomputable -> (None, False).
    Never raises.
    """
    generated = _parse_ts(gate.get("generated_at"))
    if generated is not None:
        return max(0, int((now - generated).total_seconds())), False
    age = gate.get("answer_age_s")
    if isinstance(age, bool) or not isinstance(age, (int, float)) \
            or not math.isfinite(age):
        return None, False
    return max(0, int(age)), True


def _format_gate_age(age_s, emit_time_fallback):
    """Render a gate age for the inventory table. A trailing `~` marks
    the emit-time fallback (the box's frozen answer_age_s, not a live
    recomputation) — see the module docstring's answer_age_s rule."""
    if age_s is None:
        return "n/a"
    if age_s < 60:
        text = "%ds" % age_s
    elif age_s < 3600:
        text = "%dm" % (age_s // 60)
    else:
        text = "%dh" % (age_s // 3600)
    return text + "~" if emit_time_fallback else text


# --- Correlated gate-stale fleet alert rule (G18 §7, #1631) -----------------
# The sixth S1 alert rule. A fleet-wide gate-sync outage is invisible in
# the event stream by design (G17 §3: the S1 canonicalizer infers nothing
# from gate silence), so this rule reads the collector's gate answer-age
# field — the same field `fleet inventory` renders per box — and pages
# once per fleet-wide outage instead of once per box.
#
# Trigger: >= _GATE_STALE_QUORUM boxes whose gate answers are stale beyond
# _GATE_STALE_THRESHOLD_S. A single stale box stays a per-box row on the
# inventory table, not a page: it is the box-down or one-off-sync story,
# and the correlation quorum is what makes the alert fleet-scoped.
#
# Evidence discipline: an uncomputable gate age (no generated_at and no
# numeric answer_age_s — e.g. gate-unmanaged boxes) is missing evidence,
# not a stale signal (the G17 §3 discipline, carried over). A box whose
# frozen emit-time answer_age_s already exceeds the threshold still
# counts: the fallback understates the true age, so a stale verdict on it
# is safe — it can only under-fire, never over-fire.
#
# Episode identity (watermark): the alert pages once per outage, not once
# per collect. A watermark file records the currently-firing box set and
# a monotonically increasing episode number; the identical set on the
# next collect stays silent; a grown set (new boxes joined the outage)
# is new evidence and re-pages; a shrunken set (boxes recovered but the
# quorum still holds) updates the watermark silently — the operator was
# already paged on the wider set. When the stale set drops below quorum
# the episode resolves but the counter persists, so a later re-outage
# of the same boxes is a new episode and pages again. This mirrors rule
# 2's #927 cluster-growth discipline; the alert journal's own alert_id
# dedup is the backstop.
#
# The episode number (not the box set alone) rides in the alert's
# dedup key. That is what makes the alert-first-then-watermark ordering
# crash-safe: if the alert appends but the watermark write fails, the
# next collect retries the same episode number, and the alert journal's
# alert_id dedup turns the retry into a no-op instead of a duplicate
# page. A timestamp anchor would not survive that failure direction —
# the retry would mint a new key and page twice for one outage.
_GATE_STALE_THRESHOLD_S = 1200  # 2x the S1 gate TTL (600s, G18 §4): one
# missed sync loop rides out on the TTL's jitter margin; past 2x the box
# has frozen loudly by design and the sync path is down, not late. The
# operator-configured TTL (--ttl-seconds) can differ; the divergence is a
# documented limitation, not a silent one.
_GATE_STALE_QUORUM = 2  # "correlated" is what makes this fleet-scoped.
_GATE_STALE_WATERMARK_NAME = "gate_stale_watermark.json"
_GATE_STALE_WATERMARK_SCHEMA = "fleet-gate-stale-watermark/1"
_GATE_STALE_DETAIL_BOXES = 10  # cap on boxes named in the alert detail


def _gate_stale_candidates(snapshot, now):
    """(box_id, age_s, emit_time_fallback) for stale gate answers.

    Sorted by box_id. Never raises: a malformed boxes map yields no
    candidates rather than failing the collect.
    """
    boxes = snapshot.get("boxes") if isinstance(snapshot, dict) else None
    if not isinstance(boxes, dict):
        return []
    stale = []
    for box_id in sorted(boxes, key=str):
        record = boxes[box_id]
        if not isinstance(record, dict):
            continue
        gate = record.get("gate")
        if not isinstance(gate, dict):
            continue
        age_s, fallback = _gate_age_s(gate, now)
        if age_s is None or age_s < _GATE_STALE_THRESHOLD_S:
            continue
        stale.append((str(box_id), age_s, fallback))
    return stale


def _read_gate_stale_watermark(store_dir):
    """The active episode: (sorted stale-box list, episode number, error).

    Returns (None, last_episode, None) when no episode is active. A
    *missing* file is a fresh counter — fine. A *corrupt* file is a
    loud error, not a silent reset: the episode counter is the rule's
    episode identity, and resetting it to zero would both miss a
    genuine re-outage page (the retried key collides with the
    journaled one) and double-page an ongoing outage (a fresh key for
    the same boxes). Fail-visible, per the #1744 precedent — a paging
    rule must never fail silent on its own state. The caller refuses
    to evaluate (fails the collect) on this error; the operator
    inspects, backs up, and removes or restores the file.
    """
    path = os.path.join(store_dir, _GATE_STALE_WATERMARK_NAME)
    data, err = _read_json_file(path)
    if err == "missing":
        return None, 0, None
    if err is not None:
        return None, None, (
            "gate-stale watermark %s is corrupt (%s); refusing to "
            "evaluate — episode identity cannot be reconstructed. "
            "Inspect, back up, and remove the file to start a fresh "
            "episode counter (or restore it from backup)."
            % (_GATE_STALE_WATERMARK_NAME, err))
    episode = 0
    if isinstance(data, dict) \
            and data.get("schema") == _GATE_STALE_WATERMARK_SCHEMA:
        ep = data.get("episode")
        if isinstance(ep, int) and not isinstance(ep, bool) and ep >= 0:
            episode = ep
        boxes = data.get("stale_boxes")
        if isinstance(boxes, list) \
                and all(isinstance(b, str) for b in boxes):
            # An empty set is a resolved episode: no active incident,
            # but the counter persists for the next one.
            return (sorted(boxes) or None), episode, None
    return None, None, (
        "gate-stale watermark %s has the wrong schema or fields; "
        "refusing to evaluate — episode identity cannot be "
        "reconstructed. Inspect, back up, and remove the file to start "
        "a fresh episode counter (or restore it from backup)."
        % _GATE_STALE_WATERMARK_NAME)


def _write_gate_stale_watermark(store_dir, stale_boxes, episode):
    """Record the episode's box set and number; an empty list resolves
    the episode while keeping the counter for the next one.

    Returns an error string, or None on success.
    """
    path = os.path.join(store_dir, _GATE_STALE_WATERMARK_NAME)
    payload = {"schema": _GATE_STALE_WATERMARK_SCHEMA,
               "stale_boxes": sorted(stale_boxes or []),
               "episode": episode}
    tmp = "%s.tmp.%d" % (path, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        # Don't litter the store with a tmp on failure (mirrors
        # events._save_tail_watermarks).
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return "cannot write gate-stale watermark: %s" % exc
    return None


def _gate_stale_detail(stale):
    """Operator-facing detail for the fleet-scoped alert."""
    named = stale[:_GATE_STALE_DETAIL_BOXES]
    parts = ["%s (%s)" % (box_id, _format_gate_age(age_s, fallback))
             for box_id, age_s, fallback in named]
    if len(stale) > _GATE_STALE_DETAIL_BOXES:
        parts.append("and %d more" % (len(stale) - _GATE_STALE_DETAIL_BOXES))
    return ("fleet gate sync outage: %d boxes with gate answers older "
            "than %s (%s)" % (
                len(stale), _format_gate_age(_GATE_STALE_THRESHOLD_S, False),
                ", ".join(parts)))


def evaluate_gate_stale_alerts(store_dir, observed_at=None):
    """Evaluate the correlated gate-stale rule (G18 §7, #1631) over the
    collector's freshly rebuilt snapshot; journal newly fired alerts.

    Returns (fired_alerts, error). Call after append_journal ->
    rebuild_snapshot so the snapshot is current.

    The watermark read happens before the lock (a corrupt watermark
    refuses the evaluation loudly instead of wedging the collect);
    the alert append and the watermark advance run under the
    store-scoped journal lock, alert-first then watermark — the
    alert_id dedup makes the ordering crash-safe in both directions
    (see check_tail_continuity's failure-ordering comment, which this
    follows). Reaches into events' private alert helpers like the rest
    of this module already does (events._clean_text et al.).
    """
    snapshot, err = load_snapshot(store_dir)
    if err:
        return None, err
    now = _parse_ts(observed_at)
    if now is None:
        now = datetime.now(timezone.utc)
    stale = _gate_stale_candidates(snapshot, now)
    stale_ids = [box_id for box_id, _age_s, _fallback in stale]
    # The watermark read happens BEFORE the lock on purpose: a corrupt
    # watermark refuses the evaluation loudly here (Engineering B1,
    # #1631 review) instead of wedging the collect behind a lock it
    # will never use.
    prev, episode, werr = _read_gate_stale_watermark(store_dir)
    if werr:
        return None, werr
    try:
        with events.journal_lock(store_dir):
            if len(stale_ids) < _GATE_STALE_QUORUM:
                # Below quorum: no page. Resolve any active episode (the
                # counter persists) so a later re-outage of the same
                # boxes is a new episode and pages again.
                if prev is not None:
                    werr = _write_gate_stale_watermark(store_dir, [], episode)
                    if werr:
                        return None, werr
                return [], None
            if prev is not None and set(stale_ids) <= set(prev):
                # Same or shrunken set: the operator was already paged on
                # this episode (shrinkage is good news, not new evidence).
                # Narrow the watermark silently so the episode tracks the
                # current incident set; the episode number is unchanged.
                if stale_ids != prev:
                    werr = _write_gate_stale_watermark(store_dir, stale_ids,
                                                      episode)
                    if werr:
                        return None, werr
                return [], None
            # New episode, or the outage grew: page once for the fleet.
            # The episode number rides in the dedup key (see the episode
            # comment above), so a crashed watermark write retries the
            # same key on the next collect and the journal dedup — not a
            # second page — is the result. Fleet-scoped (box_id=None): no
            # single box owns the outage — the same null-box_id
            # convention as the freeze-hold fleet events in
            # UPDATE_EVENT_REPORTING §3.
            episode += 1
            alert = events._alert(
                "correlated-gate-stale", observed_at,
                _gate_stale_detail(stale),
                box_id=None,
                dedup_key="ep%d|%s" % (episode, "|".join(stale_ids)))
            fired, aerr = events._append_alerts_nolock(store_dir, [alert])
            if aerr:
                return None, aerr
            werr = _write_gate_stale_watermark(store_dir, stale_ids, episode)
            if werr:
                return None, werr
            return fired, None
    except events.JournalLockError as exc:
        return None, str(exc)


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
    for bid, record in sorted(boxes.items(), key=_box_sort_key):
        if _is_eligible(record, cutoff):
            eligible[bid] = record
        else:
            stale.append(bid)

    lines = []
    lines.append("fleet version table (snapshot %s)" % snapshot.get(
        "generated_at", "unknown"))
    lines.append("")

    # Column width follows the longest box id (FOLLOW-fleet4): ids longer
    # than the old fixed 24-char column used to push the rest of the row
    # out of alignment.
    box_w = max(24, max((len(str(bid)) for bid in boxes), default=0))
    row_fmt = "%%-%ds %%-14s %%-12s %%-8s %%-10s %%s" % box_w

    # Per-box rows.
    lines.append(row_fmt % ("box", "repo_commit", "toolset_tick", "frozen",
                            "gate_age", "flags"))
    now = datetime.now(timezone.utc)
    any_emit_fallback = False
    for bid, record in sorted(boxes.items(), key=_box_sort_key):
        ver = record.get("versions", {}) or {}
        tick = record.get("last_tick_at", {}) or {}
        gate = record.get("gate", {}) or {}
        flags = []
        if bid not in eligible:
            flags.append("stale")
        if record.get("suspect"):
            flags.append("suspect")
        frozen = gate.get("frozen")
        # #1632: per-box gate staleness, recomputed from
        # gate.generated_at (#1660); a trailing `~` marks the emit-time
        # answer_age_s fallback.
        age_s, emit_fallback = _gate_age_s(gate, now)
        any_emit_fallback = any_emit_fallback or emit_fallback
        lines.append(row_fmt % (
            bid,
            _short_commit(ver.get("repo_commit")),
            (tick.get("toolset") or "n/a")[:10],
            "yes" if frozen else ("no" if frozen is False else "n/a"),
            _format_gate_age(age_s, emit_fallback),
            ",".join(flags) or "-",
        ))
    if any_emit_fallback:
        # The `~` sigil needs its legend at the point of use (Product
        # review B1): an operator must not have to read the docstring to
        # learn what it means. The blank line keeps the CLI↔API
        # conformance parser (which stops at the first blank) from
        # reading the legend as a data row.
        lines.append("")
        lines.append("~ = gate age is the box's emit-time answer_age_s "
                     "(gate.generated_at unavailable; the value froze at "
                     "snapshot emission, it does not update)")

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
    for bid, record in sorted(eligible.items(), key=_box_sort_key):
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
    box_w = max(24, max((len(str(bid)) for bid, _, _ in rows), default=0))
    drift_fmt = "  %%-%ds %%-14s %%s" % box_w
    for bid, commit, reason in rows:
        lines.append(drift_fmt % (bid, commit, reason))
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
                if os.path.isdir(os.path.join(estate_dir, e))
                # Dot-directories are loop/operator metadata (e.g.
                # gate_sync.sh's .gate_sync_state/), never boxes — the
                # sync loop's own "$ESTATE"/*/ glob already ignores them,
                # so the collector must agree (#1326).
                and not e.startswith(".")]
    if not box_dirs:
        return "no per-box directories found in %s" % estate_dir

    observed_at = _now_iso()
    records = []
    failed = []
    box_contexts = []  # (box_dir, box_id) for the G17 S1 event pass
    for dirname in box_dirs:
        box_id = mapping.get(dirname, dirname)
        if not isinstance(box_id, str) or not box_id:
            # A non-string box_id would poison the journal (JSON allows
            # it, but the snapshot is keyed on it) and brick every later
            # collect/rebuild — skip the box loudly instead.
            failed.append("%s: box_id map produced non-string box_id %r; "
                          "skipped" % (dirname, box_id))
            continue
        box_dir = os.path.join(estate_dir, dirname)
        try:
            records.append(collect_box(box_dir, box_id, observed_at))
        except Exception as exc:  # one bad box must not sink the collect
            failed.append("%s: %s" % (dirname, exc))
            continue
        box_contexts.append((box_dir, box_id))

    total, err = append_journal(store_dir, records)
    if err:
        return err

    # G17 S1: canonicalize each box's event evidence into the
    # update-event journal (the design's S2 sink — the same estate dir
    # the collector already pulls), then evaluate the six fleet alert
    # rules. #1649 S2 read switch: collect_box_events reads the box's
    # native `update-events.jsonl` instead of translating audit tails
    # whenever the estate dir carries it (exclusive per box — no
    # double-journaling under two event_ids). A failed
    # event/alert write fails the collect loudly: the operator's
    # contract is the exit code, and a silently un-journaled event would
    # be missing evidence masquerading as silence.
    #
    # #1516 S3: load the pinned box keys once per collect. A corrupt
    # registry is an integrity failure — fail the collect closed rather
    # than silently journaling everything unattested (that would make
    # the T2 consume-gate rule vacuous by absence).
    keyring, key_err = attest.load_box_keys(store_dir)
    if key_err is not None:
        return "box-key registry: %s" % key_err
    all_events = []
    for box_dir, box_id in box_contexts:
        box_events, _, ev_notes = events.collect_box_events(
            box_dir, box_id, observed_at, keyring=keyring,
            store_dir=store_dir)
        all_events.extend(box_events)
        for note in ev_notes:
            print("fleet events note (%s): %s" % (box_id, note),
                  file=sys.stderr)
    appended, duplicates, ev_err = events.append_events(store_dir,
                                                        all_events)
    if ev_err:
        return "event journal: %s" % ev_err
    fired, alert_err = events.evaluate_alerts(store_dir, observed_at)
    if alert_err:
        return "alert evaluation: %s" % alert_err
    if fired:
        print("fleet events: %d new event(s) journaled, %d duplicate(s) "
              "skipped; %d alert(s) fired" % (appended, duplicates,
                                              len(fired)))
    # Audit-tail continuity (arch 20261004-1359, #1006): the estate pulls
    # only a tail of each box's audit log. When more lines are emitted
    # between pulls than the tail holds, the lost lines never reach the
    # collector and the truncation hides the loss — the failure events
    # the alert rules page on can vanish silently. The per-box tail-head
    # watermark detects the break; each distinct lost window fires the
    # fifth S1 alert rule (`tail-discontinuity`) into the alert journal,
    # page-class (a warning-only signal would be exactly as losable as
    # the events it reports), alongside the stderr warning.
    cont_warnings, cont_fired, cont_err = events.check_tail_continuity(
        store_dir, box_contexts, observed_at)
    if cont_err:
        return "tail continuity: %s" % cont_err
    for warning in cont_warnings:
        print("fleet events WARNING: %s" % warning, file=sys.stderr)
    if cont_fired:
        print("fleet events: %d tail-discontinuity alert(s) fired"
              % len(cont_fired))
    # Correlated gate-stale (G18 §7, #1631): the sixth S1 alert rule. A
    # fleet-wide gate-sync outage is invisible in the event stream by
    # design, so this rule reads the collector's gate answer-age field
    # from the freshly rebuilt snapshot and pages once per outage
    # instead of once per box.
    gate_fired, gate_err = evaluate_gate_stale_alerts(store_dir,
                                                      observed_at)
    if gate_err:
        return "gate-stale evaluation: %s" % gate_err
    if gate_fired:
        print("fleet events: %d correlated-gate-stale alert(s) fired"
              % len(gate_fired))
    print("collected %d %s into %s (%d appended this run; %d journal "
          "lines replayed)"
          % (len(records), "box" if len(records) == 1 else "boxes",
             store_dir, len(records), total))
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

    p_prune = sub.add_parser("prune",
                             help="drop inventory journal rows older than "
                                  "90 days and rebuild the snapshot "
                                  "(G17 S2 retention)")
    p_prune.add_argument("--store", required=True)

    p_events = sub.add_parser("events", help="fleet update-event journal "
                                             "and alerts (G17/#608 S1)")
    p_events.add_argument("--store", required=True)
    p_events.add_argument("--box", default=None,
                          help="with list: this box's event series instead "
                               "of the fleet summary")
    p_events.add_argument("--wave", default=None,
                          help="with list: only events in this rollout "
                               "wave (rollout envelopes are null until "
                               "G15 S2)")
    p_events.add_argument("action", nargs="?", default="list",
                          choices=["list", "watch", "ack", "crosscheck",
                                   "prune"],
                          help="'watch' lists unacknowledged alerts and "
                               "exits 1 when any are pending; 'ack' marks "
                               "one alert acknowledged; 'crosscheck' checks "
                               "update claims against the inventory "
                               "(G17 S2) and exits 1 on any violation; "
                               "'prune' applies the event-journal "
                               "retention policy (G17 S2)")
    p_events.add_argument("--alert-id", default=None,
                          help="with ack: the alert to acknowledge")

    p_boxkey = sub.add_parser("box-key", help="pin/show box ed25519 "
                                              "identity keys for event "
                                              "attestation (#1516 S3)")
    p_boxkey.add_argument("--store", required=True,
                          help="fleet store dir (holds box-keys.json)")
    p_boxkey.add_argument("action", nargs="?", default="show",
                          choices=["pin", "show"],
                          help="'pin' pins a box's 64-hex ed25519 pubkey "
                               "(write-once; re-pinning a different key "
                               "fails closed); 'show' prints the pinned "
                               "fingerprint")
    p_boxkey.add_argument("--box-id", default=None,
                          help="box id to pin/show")
    p_boxkey.add_argument("--pubkey", default=None,
                          help="with pin: the box's 64-hex ed25519 pubkey")

    p_api = sub.add_parser("api", help="read-only HTTP projection of the "
                                      "fleet estate store (G21 S1, #795)")
    p_api.add_argument("--store", required=True,
                       help="store dir (journal.jsonl + snapshot.json); "
                            "never written")
    p_api.add_argument("--port", type=int, default=18760,
                       help="localhost port (default 18760); binds "
                            "127.0.0.1 only — no bind-address flag exists "
                            "by design (spec §5)")

    args = parser.parse_args(argv)
    if args.command in ("inventory", "drift"):
        # timedelta(hours=...) blows up on nan/inf; reject non-finite or
        # negative windows at the boundary with a clean exit 2 instead.
        window = args.staleness_hours
        if not math.isfinite(window) or window < 0:
            print("error: --staleness-hours must be a finite number >= 0, "
                  "got %r" % (window,), file=sys.stderr)
            return 2
    try:
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
        elif args.command == "prune":
            err = cmd_prune(args.store)
            if err:
                print("error: %s" % err, file=sys.stderr)
                return 2
        elif args.command == "events":
            if args.action == "list":
                err = events.cmd_events_list(args.store, args.box,
                                             args.wave)
                if err:
                    print("error: %s" % err, file=sys.stderr)
                    return 2
            elif args.action == "watch":
                err, code = events.cmd_events_watch(args.store)
                if err:
                    print("error: %s" % err, file=sys.stderr)
                    return 2
                return code
            elif args.action == "ack":
                if not args.alert_id:
                    print("error: ack requires --alert-id",
                          file=sys.stderr)
                    return 2
                err = events.cmd_events_ack(args.store, args.alert_id)
                if err:
                    print("error: %s" % err, file=sys.stderr)
                    return 2
            elif args.action == "crosscheck":
                err, code = events.cmd_events_crosscheck(args.store,
                                                         args.box)
                if err:
                    print("error: %s" % err, file=sys.stderr)
                    return 2
                return code
            elif args.action == "prune":
                err = events.cmd_events_prune(args.store)
                if err:
                    print("error: %s" % err, file=sys.stderr)
                    return 2
            else:
                err = "unknown events action %s" % args.action
        elif args.command == "box-key":
            if not args.box_id:
                print("error: box-key requires --box-id", file=sys.stderr)
                return 2
            if args.action == "pin":
                if not args.pubkey:
                    print("error: box-key pin requires --pubkey",
                          file=sys.stderr)
                    return 2
                fp, err = attest.pin_box_key(args.store, args.box_id,
                                             args.pubkey)
                if err:
                    print("error: %s" % err, file=sys.stderr)
                    return 2
                print("pinned box key for %r: %s" % (args.box_id, fp))
            elif args.action == "show":
                pub, err = attest.read_box_key(args.store, args.box_id)
                if err:
                    print("error: %s" % err, file=sys.stderr)
                    return 2
                if pub is None:
                    print("no box key pinned for %r" % (args.box_id,))
                else:
                    print("%s: %s" % (args.box_id,
                                      attest.ed25519.fingerprint(pub)))
            else:
                err = "unknown box-key action %s" % args.action
        elif args.command == "api":
            # G21 S1: the read API lives in fleet/api.py (same-dir import,
            # like the `import events` above). Imported lazily so the
            # plain CLI never pays for http.server, and the api command
            # never runs on import.
            import api as fleet_api
            return fleet_api.main(["--store", args.store,
                                   "--port", str(args.port)])
        else:
            err = "unknown command %s" % args.command
    except Exception as exc:
        # Disciplined failure: the tool's contract is the exit code, so
        # an unexpected internal error reports as exit 2 with a one-line
        # message, never a bare traceback (FOLLOW-fleet1's exit-1 half).
        # KeyboardInterrupt/SystemExit are BaseException and pass through.
        print("error: unexpected failure: %s" % exc, file=sys.stderr)
        return 2
    if err:
        print("error: %s" % err, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
