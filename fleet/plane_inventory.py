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
  event    --store DIR --plane-id ID
             --kind deploy-landed|deploy-deferred|deploy-failed|rolled-back
             [--template V] [--deployment-id D] [--worker-sha256 S] [--notes T]
      Append one operator-observed update event to the S5 event journal
      (stage-1 producer (a): the operator's own entry — e.g. a deferral
      or an out-of-band failure the operator observed). deploy-started
      is the S4 driver's alone and is not accepted here.
  events   --store DIR [--plane-id ID] [--kind K] [--since-hours H]
      The controller's "what happened in the last window?" read path over
      the event journal — the wave-health signal the S2 promotion gate
      consumes per D-RC-4.
  release --store DIR --template V --channel C --deployment-id D --worker-sha256 S [--notes T]
      Pin a template release (D-RC-2 pick (b), S3 #1286): bind template
      version V to exactly one (deployment_id, worker_sha256) — the pinned
      manifest the S4 deploy driver consumes as its deploy target.
      Re-releasing V fails closed: a template version is immutable once
      pinned; mint a new template version to change the pin.
  release-show --store DIR --template V
      Print the pinned manifest for V (the S4 driver's deploy-target reader).
  releases --store DIR [--channel C]
      List pinned template releases (template identity -> channel).

Store layout:
  <store>/planes.json          derived snapshot: latest record per plane_id
  <store>/planes_journal.jsonl append-only observation records
  <store>/costs.jsonl          append-only cost events
  <store>/plane_events.jsonl   append-only operator-observed update events (S5)
  <store>/releases.json       derived snapshot: pinned release per template
  <store>/releases_journal.jsonl append-only release pins

Record schema (S1, bumped to /2 by S3, to /3 by S4 #1287):
  {schema, plane_id, tenant_id, template_version, channel,
   status{provisioning,healthy,degraded,retired}, observed_at,
   reporter, notes, last_known_good, deployment_id, worker_sha256}
  last_known_good is None or
  {template_version, deployment_id, worker_sha256, recorded_at} — the
  rollback pin the S4 driver redeploys. Writer contract: ONLY the S2
  promotion step writes it (this slice ships no writer); deploy/retire
  preserve it untouched, so it always names the last wave-landed
  template, never the latest recorded observation.
  deployment_id / worker_sha256 are None or the pinned artifact identity
  of the last deploy the S4 driver performed (F-RC-10: "which bytes
  landed on plane #k", not just "which template"). Writer contract: ONLY
  the S4 deploy driver writes them; S1 deploy/retire preserve them
  untouched; /1- and /2-era records normalize to None.
Release-record schema (S3):
  {schema, template_version, channel, deployment_id, worker_sha256,
   released_at, reporter, notes}
  The D-RC-2 (b) pinned manifest: the template artifact's home is the
  production deploy contract's existing pin discipline — deployment id +
  SHA-256 of the deployed worker.py bytes — rather than an in-repo
  artifact. The operator records the pin after the deploy contract's
  verify step; the controller treats template_version as an opaque
  comparable token and the S4 driver redeploys only the pinned bytes
  (SHA-256 verified), never a floating "latest".
Cost-event schema (S1):
  {schema, plane_id, event{provision,update,rollback},
   at, duration_s, cost_usd, notes}
Update-event schema (S5, #1288 — the operator-observed event journal):
  {schema, plane_id, kind{deploy-started,deploy-landed,deploy-deferred,
   deploy-failed,rolled-back}, template_version, deployment_id,
   worker_sha256, observed_at, reporter, notes}
  Stage-1 producers, named explicitly (advisory #1288/6105124730):
  (a) the operator's own entry (`event` subcommand), (b) the S4 deploy
  driver emitting lifecycle events at the operator's command
  (deploy-started before the push, deploy-landed on verified landing,
  deploy-failed on failure, rolled-back on verified rollback), (c) the
  S1 `deploy` subcommand, which records an operator-observed landing and
  emits deploy-landed for it (the operator-correctable path that clears
  an unresolved deploy-failed). All three inherit S1's
  operator-recorded discipline: observed_at is stamped by the writer
  from the operator's clock and is never backfilled from a plane claim;
  nothing plane-self-reported enters the journal in the shipped slices.
  The S2 promotion gate consumes the journal per D-RC-4: a live-wave
  plane whose latest event since the wave went live is an unresolved
  deploy-failed is a bad signal and refuses promotion. Missing journal
  (pre-S5 stores) carries no signal — D-RC-6's "missing events do not
  block promotion" holds. Stage 2 (plane-signed health events) is named
  scope only: the trust story is written in
  docs/PLANE_UPDATE_EVENT_REPORTING.md, with no code.

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
  - A template version pins exactly one artifact (deployment_id,
    worker_sha256). Re-releasing V fails closed even with an identical
    pin — the journal stays append-only and honest, with no silent
    no-ops. To change a pin, mint a new template version.
  - The releases snapshot gets the same journal-as-truth discipline as
    the planes snapshot: every read replays releases_journal.jsonl and
    fails closed (exit 2) on any divergence, because the pinned manifest
    is the rollout's trust root — a tampered pin must never present a
    forged deploy target to the S4 driver.
  - last_known_good is None until the S2 promotion step writes it. deploy
    and retire preserve whatever value the previous record carried; no
    command in this slice writes it (a test pins this).
  - deployment_id / worker_sha256 name the pinned artifact of the last
    S4-driver deploy (F-RC-10). ONLY the S4 driver writes them; deploy
    and retire preserve whatever the previous record carried; the
    snapshot/journal divergence check covers both fields, so a tampered
    artifact identity fails closed exactly like a tampered template
    version.

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
from datetime import datetime, timedelta, timezone

# Sibling module (fleet/events.py): the store-scoped journal lock. Imported
# as a sibling because the fleet modules are script-run (python3
# fleet/plane_inventory.py puts fleet/ on sys.path); the hermetic suite
# exercises the CLIs through subprocess, never through imports.
import events

RECORD_SCHEMA = "plane-inventory-record/3"
SNAPSHOT_SCHEMA = "plane-inventory-snapshot/1"
COST_SCHEMA = "plane-cost-event/1"
RELEASE_SCHEMA = "plane-template-release/1"
RELEASES_SNAPSHOT_SCHEMA = "plane-template-releases-snapshot/1"

PLANES_SNAPSHOT_NAME = "planes.json"
PLANES_JOURNAL_NAME = "planes_journal.jsonl"
COSTS_JOURNAL_NAME = "costs.jsonl"
RELEASES_SNAPSHOT_NAME = "releases.json"
RELEASES_JOURNAL_NAME = "releases_journal.jsonl"

_STATUSES = ("provisioning", "healthy", "degraded", "retired")
_COST_EVENTS = ("provision", "update", "rollback")
# Collector-side observed_at is trusted; records are minted operator-side
# within the same process, so future-skew handling is unnecessary.
DEFAULT_STALE_HOURS = 24

# Python's `$` matches before a trailing newline, which would let a
# newline-poisoned pin through (`"ab"*32 + "\n"` exits 0 and can never
# hex-match the S4 driver's digest). `\A...\Z` anchors to the true
# string ends. A SHA-256 pin is lowercase hex only: one spelling per
# pin, so two records can never carry "the same" hash in different cases.
_ID_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_TEMPLATE_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:+~@-]{0,127}\Z")
_SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")


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


def _check_sha256(value):
    if not value or not _SHA256_RE.match(value):
        _fail(
            f"worker sha256 must be 64 lowercase hex characters, "
            f"got {value!r}"
        )
    return value


def is_sha256_pin(value):
    """Non-raising form of the SHA-256 pin grammar.

    For validating deployer-reported digests (the S4 driver must fail
    closed on a malformed observed digest with its own message, not the
    CLI-input message above).
    """
    return isinstance(value, str) and _SHA256_RE.match(value) is not None


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


# Public aliases for the S4 deploy driver (fleet/plane_deploy.py) and the
# S2 wave machine (fleet/plane_waves.py). The pin grammars, the error
# contract, the clock, the staleness rule, the controller-freeze reader,
# and the store guard are trust-critical: one definition, shared, never
# duplicated — see #21's centralize-trust-validation follow-up (three
# copies of the ANSI regex was the original sin; the plane lane gets one
# copy from the start).
check_id = _check_id
check_template = _check_template
check_sha256 = _check_sha256
check_nonneg_number = _check_nonneg_number
now_iso = _now_iso
ensure_store = _ensure_store
fail = _fail

# Controller-store freeze contract (D-RC-5), read by both the S4 deploy
# driver and the S2 wave machine. The freeze file is written by the S4
# `freeze` command; the constants live here so the reader is defined
# exactly once.
FREEZE_SCHEMA = "plane-controller-freeze/1"
FREEZE_NAME = "freeze.json"


def read_controller_freeze(store_dir):
    """True when the controller store is frozen (D-RC-5).

    Missing file = not frozen (fresh store). Corrupt file, wrong schema,
    or a non-boolean `frozen` fails closed — a tampered freeze file must
    never silently unfreeze the controller. Reports under the
    plane_inventory error name (the shared reader has one spelling).
    """
    path = os.path.join(store_dir, FREEZE_NAME)
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        _fail(f"freeze file at {path} is unreadable ({exc}) — refusing deploys")
    if not isinstance(data, dict) or data.get("schema") != FREEZE_SCHEMA:
        _fail(f"freeze file at {path} has an unexpected schema — refusing deploys")
    frozen = data.get("frozen")
    if not isinstance(frozen, bool):
        _fail(f"freeze file at {path}: 'frozen' is not a boolean — refusing deploys")
    return frozen


def is_record_fresh(record, stale_hours):
    """The S1 staleness rule, shared with the S2 promotion gate (D-RC-4).

    A record the operator has not refreshed within the window is not an
    observation the controller may promote on — same rule the `stale`
    estate-convergence report applies, one definition.

    Corruption fails closed, never launders into "stale": only a missing
    or unparseable timestamp reads as not-fresh. A non-dict record or a
    non-string observed_at raises TypeError, which the caller's exit-2
    contract turns into a loud failure — a corrupt record must never
    present as a routine "wait and re-run" stale refusal.

    The window itself is guarded at the sink: a non-finite stale_hours,
    or one whose hour-window product overflows to non-finite (e.g. 1e308
    x 3600), raises ValueError instead of silently reading every record
    as fresh — a vacuous window must never launder into "fresh".
    """
    if not math.isfinite(stale_hours) or stale_hours <= 0:
        raise ValueError(
            "stale_hours must be a positive finite number, "
            f"got {stale_hours!r}")
    window_s = stale_hours * 3600
    if not math.isfinite(window_s):
        raise ValueError(
            f"stale_hours {stale_hours!r} overflows the freshness window")
    try:
        observed = datetime.fromisoformat(record["observed_at"])
    except (KeyError, ValueError):
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - observed).total_seconds() <= window_s


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
        # A missing snapshot with a non-empty journal is a divergence (a
        # hand-deleted planes.json must not silently re-open registration):
        # fail closed, exactly like the releases store's missing-snapshot
        # path and the planes store's tampered-snapshot path. No-op on a
        # genuinely fresh store.
        _verify_snapshot_consistent(store_dir, {})
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
    false-green for the estate-convergence `stale` report.
    """
    journal = _latest_journal_records(store_dir)
    if set(journal) != set(planes):
        _fail(
            "snapshot/journal divergence: plane sets differ "
            f"(journal={sorted(journal)}, snapshot={sorted(planes)})"
        )
    for plane_id, jrec in journal.items():
        srec = planes[plane_id]
        # last_known_good is covered too: a tampered rollback pin must fail
        # closed exactly like a tampered template version. The S4 /3
        # artifact-identity fields get the same coverage: a tampered
        # deployment_id in the snapshot must never present forged bytes as
        # the landed artifact.
        for field in ("template_version", "status", "observed_at",
                      "last_known_good", "deployment_id", "worker_sha256"):
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
    """Append records as one O_APPEND write() per line, under the store lock.

    #1841: opens with O_NOFOLLOW — a pre-planted symlink at the journal
    path fails loud (ELOOP, surfaced by _fail as exit 2) instead of
    silently redirecting records into an arbitrary file. Same threat
    class as the fleet journal append leg; O_NOFOLLOW covers the final
    path component only."""
    path = os.path.join(store_dir, journal_name)
    lines = [json.dumps(r, sort_keys=True) + "\n" for r in records]
    with events.journal_lock(store_dir):
        try:
            fd = os.open(path,
                         os.O_WRONLY | os.O_CREAT | os.O_APPEND
                         | os.O_NOFOLLOW, 0o600)
        except OSError as exc:
            _fail(f"cannot append to {journal_name}: {exc}")
        # Same fdopen-leak guard as fleet/events.py append_events (#1841),
        # mirroring the #1755 journal_lock pattern in that module.
        try:
            fh = os.fdopen(fd, "a", encoding="utf-8")
        except BaseException:
            os.close(fd)
            raise
        try:
            with fh:
                for line in lines:
                    fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            _fail(f"cannot append to {journal_name}: {exc}")


def read_planes(store_dir):
    """Fail-closed read of the latest plane record per plane_id.

    The S4 deploy driver's plane reader: journal-as-truth with the
    snapshot/divergence discipline, so the driver can never act on a
    tampered or stale-restored inventory.
    """
    return _snapshot(store_dir)["planes"]


def _record_plane_observation_locked(store_dir, record):
    """Append one plane observation record. Caller must hold events.journal_lock.

    The lock-free half of record_plane_observation: lets a caller that
    already holds the store lock (the S2 promotion step, #1345) write
    observations inside its own critical section — journal_lock cannot
    nest (a second flock on a new fd raises JournalLockError), so the
    lock must be acquired once, by the outermost caller.
    """
    plane_id = record.get("plane_id")
    if not plane_id:
        _fail("record_plane_observation: record has no plane_id")
    snap = _snapshot(store_dir)
    if plane_id not in snap["planes"]:
        _fail(f"plane {plane_id!r} is not registered (register first)")
    _append_records_locked(store_dir, [record])
    snap["planes"][plane_id] = record
    _publish_snapshot(store_dir, snap["planes"])


def record_plane_observation(store_dir, record):
    """Append one plane observation record: journal (source of truth) + derived snapshot.

    The shared locked writer for the S1 inventory commands and the S4
    deploy driver (F-RC-10): one path appends, republishes, and
    re-verifies, so the driver cannot drift from the inventory's journal
    discipline. Fails closed when the plane is not registered — the
    controller never silently creates a plane row mid-rollout. Callers
    build the full /3 record (the driver sets the artifact-identity
    fields; S1 commands preserve-and-normalize them).

    Concurrency note: the record is built from a pre-lock read and the
    registration re-check happens under the lock, so two concurrent
    writers serialize on the append with last-writer-wins snapshot
    semantics (the journal stays append-only — no observation is lost).
    This CLI is operator-run (single writer in practice); a future
    multi-writer controller should rebuild the record inside the lock.
    """
    with events.journal_lock(store_dir):
        _record_plane_observation_locked(store_dir, record)


# Public alias for the S2 wave machine (fleet/plane_waves.py): the
# promotion step stamps pins inside its own lock acquisition (the lock
# cannot nest — see _record_plane_observation_locked), so it needs the
# lock-free half directly.
record_plane_observation_locked = _record_plane_observation_locked


def append_cost_event(store_dir, plane_id, event, duration_s=None,
                      cost_usd=None, notes=""):
    """Append one D-MT5 operational-cost event.

    The D-RC-6 writer: the S4 deploy driver calls this for every deploy
    and rollback it performs (event update/rollback). Missing events do
    not block promotion — cost-summary reports coverage
    (cost_usd_reported vs count) so the D-MT5 revisit query stays honest
    about its inputs.
    """
    if event not in _COST_EVENTS:
        _fail(f"event must be one of {','.join(_COST_EVENTS)}, got {event!r}")
    duration_s = _check_nonneg_number(duration_s, "duration_s")
    cost_usd = _check_nonneg_number(cost_usd, "cost_usd")
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
        "notes": notes or "",
    }
    _append_journal(store_dir, COSTS_JOURNAL_NAME, [record])
    return record


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


# --- Plane update-event journal (S5, #1288) ---------------------------------
# Operator-observed update events for the plane layer: the wave-health
# signal the S2 promotion gate consumes per D-RC-4. Stage-1 producers are
# named explicitly (advisory #1288/6105124730):
#   (a) the operator's own entry — the `event` subcommand;
#   (b) the S4 deploy driver emitting lifecycle events at the operator's
#       command (deploy-started before the Cloudflare push, deploy-landed
#       on verified landing, deploy-failed on failure, rolled-back on a
#       verified rollback);
#   (c) the S1 `deploy` subcommand, which records an operator-observed
#       landing and emits deploy-landed for it — the operator-correctable
#       path: re-recording a landing clears an unresolved deploy-failed.
# Nothing plane-self-reported enters the journal in the shipped slices;
# plane-signed health events are the named Stage-2 scope (trust story in
# docs/PLANE_UPDATE_EVENT_REPORTING.md, no code).
#
# Collector-side discipline (S1's trust root, transferred): observed_at is
# stamped by the writer from the operator's clock — there is no flag,
# argument, or code path that backfills it from a plane claim.
PLANE_EVENT_SCHEMA = "plane-event/1"
PLANE_EVENTS_JOURNAL_NAME = "plane_events.jsonl"
# Closed vocabulary from #1288: deploy started/landed/deferred/failed and
# rolled-back. Deferred is the operator's explicit deferral decision (a
# D-RC-5 refusal is not an event — refusals stay local). Started is the
# S4 driver's alone: an operator `event --kind deploy-started` would
# claim a push the driver never made.
PLANE_EVENT_KINDS = ("deploy-started", "deploy-landed", "deploy-deferred",
                     "deploy-failed", "rolled-back")
_PLANE_EVENT_REQUIRED = ("schema", "plane_id", "kind", "observed_at",
                         "reporter")


def append_plane_event(store_dir, plane_id, kind, template_version=None,
                       deployment_id=None, worker_sha256=None, notes=""):
    """Append one operator-observed plane update event (S5).

    The shared event writer for the operator's `event` command, the S4
    deploy driver's lifecycle emission, and the S1 `deploy` landing
    record — one path stamps observed_at and appends, so no producer can
    drift from the collector-side discipline. Fails closed on an unknown
    kind, a malformed field, or an unregistered plane: the journal is the
    wave-health signal's trust root, and an event about a plane the
    controller does not know is exactly the class of thing that must not
    enter it silently.
    """
    plane_id = _check_id(plane_id, "plane_id")
    if kind not in PLANE_EVENT_KINDS:
        _fail(f"kind must be one of {','.join(PLANE_EVENT_KINDS)}, "
              f"got {kind!r}")
    if template_version is not None:
        _check_template(template_version)
    if deployment_id is not None:
        _check_id(deployment_id, "deployment_id")
    if worker_sha256 is not None:
        _check_sha256(worker_sha256)
    with events.journal_lock(store_dir):
        snap = _snapshot(store_dir)
        if plane_id not in snap["planes"]:
            _fail(f"plane {plane_id!r} is not registered (register first)")
    record = {
        "schema": PLANE_EVENT_SCHEMA,
        "plane_id": plane_id,
        "kind": kind,
        "template_version": template_version,
        "deployment_id": deployment_id,
        "worker_sha256": worker_sha256,
        "observed_at": _now_iso(),
        "reporter": "operator",
        "notes": notes or "",
    }
    # _append_journal takes the store lock itself (same discipline as
    # the D-MT5 cost events: the registration check above and the append
    # are separate acquisitions, last-writer-wins).
    _append_journal(store_dir, PLANE_EVENTS_JOURNAL_NAME, [record])
    return record


def read_plane_events(store_dir):
    """Fail-closed read of the operator-observed update-event journal.

    Missing journal = no events (pre-S5 stores; D-RC-6's "missing events
    do not block promotion" makes the S2 gate treat this as no signal).
    Any corrupt line — unparseable JSON, wrong schema, missing field,
    unknown kind — fails closed: the journal is the wave-health signal's
    trust root, so a tampered line must never launder into an empty
    history. Returns the events in journal (append) order.
    """
    path = os.path.join(store_dir, PLANE_EVENTS_JOURNAL_NAME)
    rows = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    rows.append((lineno, json.loads(line)))
        except (OSError, ValueError) as exc:
            _fail(f"cannot read plane event journal at {path}: {exc}")
    events_out = []
    for lineno, row in rows:
        if (not isinstance(row, dict)
                or row.get("schema") != PLANE_EVENT_SCHEMA
                or not all(isinstance(row.get(k), str)
                           for k in _PLANE_EVENT_REQUIRED)
                or row.get("kind") not in PLANE_EVENT_KINDS):
            _fail(f"plane event journal at {path}:{lineno} has a corrupt "
                  f"event — refusing to read the journal")
        events_out.append(row)
    return events_out


def _record_is_fresh(record, stale_hours):
    # One definition: the S2 promotion gate shares this rule via the
    # public is_record_fresh alias above.
    return is_record_fresh(record, stale_hours)


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
        # S3: the rollback pin. None until the S2 promotion step writes it;
        # deploy/retire preserve it (they copy the previous record whole).
        "last_known_good": None,
        # S4 (#1287, F-RC-10): the pinned artifact identity of the last
        # driver deploy. None until the S4 driver writes it; S1 commands
        # preserve it untouched.
        "deployment_id": None,
        "worker_sha256": None,
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

    prev = read_planes(store_dir).get(plane_id)
    if prev is None:
        _fail(f"plane {plane_id!r} is not registered (register first)")
    record = dict(prev)
    # /1-era records carry no last_known_good key: normalize to the /3
    # invariant (None until the S2 promotion step writes it) rather
    # than stamping a /3 record that omits a /3-mandated field.
    record.setdefault("last_known_good", None)
    # /1- and /2-era records carry no artifact-identity keys: normalize
    # to the /3 invariant (None until the S4 driver writes them).
    record.setdefault("deployment_id", None)
    record.setdefault("worker_sha256", None)
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
    record_plane_observation(store_dir, record)
    # S5 producer (c): recording a landing is an operator-observed
    # landing — emit it into the update-event journal with the artifact
    # identity the record carries (None for pre-S4 records). This is the
    # operator-correctable path: a fresh `deploy` here clears an
    # unresolved deploy-failed the S2 gate is refusing on.
    append_plane_event(store_dir, plane_id, "deploy-landed", template,
                       record.get("deployment_id"),
                       record.get("worker_sha256"), args.notes or "")
    print(json.dumps({"ok": True, "plane_id": plane_id, "template_version": template,
                      "status": status}))
    return 0


def cmd_retire(args):
    store_dir = _ensure_store(args.store)
    plane_id = _check_id(args.plane_id, "--plane-id")

    prev = read_planes(store_dir).get(plane_id)
    if prev is None:
        _fail(f"plane {plane_id!r} is not registered")
    record = dict(prev)
    # Same /1 -> /2 normalization as cmd_deploy (see above).
    record.setdefault("last_known_good", None)
    # Same /1,/2 -> /3 normalization as cmd_deploy (F-RC-10).
    record.setdefault("deployment_id", None)
    record.setdefault("worker_sha256", None)
    record.update(
        {
            "schema": RECORD_SCHEMA,
            "status": "retired",
            "observed_at": _now_iso(),
            "reporter": "operator",
            "notes": args.notes or "",
        }
    )
    record_plane_observation(store_dir, record)
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

    append_cost_event(store_dir, plane_id, event, duration_s, cost_usd,
                      args.notes or "")
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


def cmd_event(args):
    """Stage-1 producer (a): the operator's own event entry (S5, #1288)."""
    store_dir = _ensure_store(args.store)
    record = append_plane_event(
        store_dir, args.plane_id, args.kind,
        template_version=args.template,
        deployment_id=args.deployment_id,
        worker_sha256=args.worker_sha256,
        notes=args.notes or "")
    print(json.dumps({"ok": True, "plane_id": record["plane_id"],
                      "kind": record["kind"],
                      "observed_at": record["observed_at"]}))
    return 0


def _parse_event_ts(value, what):
    """Parse an event/journal ISO timestamp; fail closed, never naive."""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        _fail(f"{what} is not a parseable ISO timestamp: {value!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def cmd_events(args):
    """The controller's "what happened in the last window?" read path (S5).

    Queryable event history over the operator-observed update-event
    journal — the wave-health signal the S2 promotion gate consumes per
    D-RC-4. Prints the matching events in journal (append) order.
    """
    store_dir = _ensure_store(args.store)
    if args.kind is not None and args.kind not in PLANE_EVENT_KINDS:
        _fail(f"--kind must be one of {','.join(PLANE_EVENT_KINDS)}, "
              f"got {args.kind!r}")
    plane_filter = args.plane_id
    if plane_filter:
        _check_id(plane_filter, "--plane-id")
    since = None
    if args.since_hours is not None:
        hours = _check_nonneg_number(args.since_hours, "--since-hours")
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = []
    for ev in read_plane_events(store_dir):
        if plane_filter is not None and ev["plane_id"] != plane_filter:
            continue
        if args.kind is not None and ev["kind"] != args.kind:
            continue
        if since is not None and _parse_event_ts(
                ev["observed_at"], "event observed_at") < since:
            continue
        rows.append(ev)
    print(json.dumps({"events": rows, "count": len(rows)}, indent=2))
    return 0


def _latest_release_records(store_dir):
    """Replay releases_journal.jsonl: latest pin per template_version."""
    path = os.path.join(store_dir, RELEASES_JOURNAL_NAME)
    latest = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if not isinstance(rec, dict) or "template_version" not in rec:
                        _fail(f"releases journal at {path} has a malformed record")
                    latest[rec["template_version"]] = rec
        except (OSError, ValueError) as exc:
            _fail(f"cannot replay releases journal at {path}: {exc}")
    return latest


def _verify_releases_consistent(store_dir, releases):
    """Fail closed when the releases snapshot disagrees with the journal.

    Release pins are immutable, so the comparison is whole-record: any
    drift between snapshot and journal is tamper or a stale restore, and
    the pinned manifest is the rollout's trust root — the S4 driver must
    never deploy from a forged pin.
    """
    journal = _latest_release_records(store_dir)
    if set(journal) != set(releases):
        _fail(
            "releases snapshot/journal divergence: template sets differ "
            f"(journal={sorted(journal)}, snapshot={sorted(releases)})"
        )
    for template, jrec in journal.items():
        if jrec != releases[template]:
            _fail(
                f"releases snapshot/journal divergence for template "
                f"{template!r}: pinned record differs"
            )


def _releases_snapshot(store_dir):
    status, data = _load_json(
        os.path.join(store_dir, RELEASES_SNAPSHOT_NAME), "releases snapshot"
    )
    if status == _MISSING:
        # A missing snapshot with a non-empty journal is a divergence (a
        # hand-deleted releases.json must not silently re-open pinning):
        # fail closed, exactly like the planes store's tampered-snapshot
        # path. No-op on a genuinely fresh store.
        _verify_releases_consistent(store_dir, {})
        return {"schema": RELEASES_SNAPSHOT_SCHEMA, "releases": {}}
    # A `null` document is structural corruption, not an empty store —
    # fail closed, never read it as "no releases."
    if not isinstance(data, dict):
        _fail("releases snapshot is corrupt: top-level is not an object")
    releases = data.get("releases")
    if not isinstance(releases, dict):
        _fail("releases snapshot is corrupt: 'releases' is not an object")
    _verify_releases_consistent(store_dir, releases)
    return {"schema": RELEASES_SNAPSHOT_SCHEMA, "releases": releases}


def read_release(store_dir, template):
    """Fail-closed read of the pinned release manifest for a template.

    The S4 deploy driver's deploy-target reader (D-RC-2(b)): the pinned
    (deployment_id, worker_sha256) is the rollout's trust root — read
    through the journal-as-truth path, fail closed when unpinned. The
    driver never deploys a floating "latest".
    """
    template = _check_template(template)
    rec = _releases_snapshot(store_dir)["releases"].get(template)
    if rec is None:
        _fail(f"template {template!r} has no pinned release (release it first)")
    return rec


def _publish_releases_snapshot(store_dir, releases):
    """Atomically replace releases.json (process-unique tmp path, os.replace)."""
    path = os.path.join(store_dir, RELEASES_SNAPSHOT_NAME)
    payload = {"schema": RELEASES_SNAPSHOT_SCHEMA, "releases": releases}
    fd, tmp = tempfile.mkstemp(
        dir=store_dir, prefix=RELEASES_SNAPSHOT_NAME + ".tmp."
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


def _append_release_records_locked(store_dir, records):
    """Append to the releases journal. Caller must hold events.journal_lock."""
    path = os.path.join(store_dir, RELEASES_JOURNAL_NAME)
    lines = [json.dumps(r, sort_keys=True) + "\n" for r in records]
    try:
        with open(path, "a", encoding="utf-8") as fh:
            for line in lines:
                fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        _fail(f"cannot append to {RELEASES_JOURNAL_NAME}: {exc}")


def cmd_release(args):
    store_dir = _ensure_store(args.store)
    template = _check_template(args.template)
    channel = _check_id(args.channel, "--channel") if args.channel else "stable"
    # #1343 item 5: D-RC-7 (S2) keys on the exact spelling "security" —
    # a miscapitalized channel (Security/SECURITY) passes the id grammar
    # but silently travels normal waves, the bad failure direction. Refuse
    # mixed case at release time so the operator fixes the spelling
    # instead of shipping a "security" release that is not one.
    if channel != channel.lower():
        _fail(f"--channel must be lowercase (the expedited channel is "
              f"exactly \"security\" — D-RC-7 keys on the spelling), "
              f"got {channel!r}")
    deployment_id = _check_id(args.deployment_id, "--deployment-id")
    worker_sha256 = _check_sha256(args.worker_sha256)

    record = {
        "schema": RELEASE_SCHEMA,
        "template_version": template,
        "channel": channel,
        "deployment_id": deployment_id,
        "worker_sha256": worker_sha256,
        "released_at": _now_iso(),
        "reporter": "operator",
        "notes": args.notes or "",
    }

    with events.journal_lock(store_dir):
        releases = _releases_snapshot(store_dir)["releases"]
        prev = releases.get(template)
        if prev is not None:
            _fail(
                f"template {template!r} is already released "
                f"(deployment_id={prev['deployment_id']!r}): a template "
                f"version pins exactly one artifact — mint a new template "
                f"version to change the pin"
            )
        _append_release_records_locked(store_dir, [record])
        releases[template] = record
        _publish_releases_snapshot(store_dir, releases)
    print(json.dumps({"ok": True, "template_version": template,
                      "channel": channel, "deployment_id": deployment_id}))
    return 0


def cmd_release_show(args):
    store_dir = _ensure_store(args.store)
    rec = read_release(store_dir, args.template)
    print(json.dumps(rec, indent=2))
    return 0


def cmd_releases(args):
    store_dir = _ensure_store(args.store)
    releases = _releases_snapshot(store_dir)["releases"]
    rows = sorted(
        releases.values(),
        key=lambda r: (r["released_at"], r["template_version"]),
    )
    if args.channel:
        channel = _check_id(args.channel, "--channel")
        rows = [r for r in rows if r["channel"] == channel]
    print(json.dumps({"releases": rows}, indent=2))
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

    p_ev = sub.add_parser("event", help="append an operator-observed update event (S5)")
    p_ev.add_argument("--plane-id", required=True)
    # deploy-started is the S4 driver's alone (it claims a push the
    # driver made): the operator's entry excludes it, so a stray
    # operator-emitted started can never become "latest" and silently
    # clear the S2 gate's bad-signal (M1, #1348 review).
    p_ev.add_argument("--kind", required=True,
                      choices=[k for k in PLANE_EVENT_KINDS
                               if k != "deploy-started"],
                      help="update-event kind (closed vocabulary, #1288; "
                           "deploy-started is emitted by the S4 driver only)")
    p_ev.add_argument("--template", default=None,
                      help="template version the event concerns")
    p_ev.add_argument("--deployment-id", default=None,
                      help="pinned deployment id (S3 grammar)")
    p_ev.add_argument("--worker-sha256", default=None,
                      help="pinned worker sha256 (64 lowercase hex)")
    p_ev.add_argument("--notes", default="")
    p_ev.set_defaults(func=cmd_event)

    p_evs = sub.add_parser("events", help="query the operator-observed update-event journal (S5)")
    p_evs.add_argument("--plane-id", default=None)
    p_evs.add_argument("--kind", default=None,
                       help="filter to one update-event kind")
    p_evs.add_argument("--since-hours", default=None,
                       help="only events observed within the last N hours")
    p_evs.set_defaults(func=cmd_events)

    p_rel = sub.add_parser("release", help="pin a template release (D-RC-2 manifest)")
    p_rel.add_argument("--template", required=True)
    # #1343 item 5: the expedited security channel is the exact spelling
    # "security", lowercase — D-RC-7 keys on it, and mixed case is
    # refused at release time (cmd_release) so a miscapitalized release
    # cannot silently travel normal waves.
    p_rel.add_argument("--channel", default="stable",
                       help="release channel (default stable; the expedited "
                            "security channel is exactly \"security\", "
                            "lowercase)")
    p_rel.add_argument("--deployment-id", required=True)
    p_rel.add_argument("--worker-sha256", required=True)
    p_rel.add_argument("--notes", default="")
    p_rel.set_defaults(func=cmd_release)

    p_rs = sub.add_parser("release-show", help="print the pinned manifest for a template")
    p_rs.add_argument("--template", required=True)
    p_rs.set_defaults(func=cmd_release_show)

    p_rl = sub.add_parser("releases", help="list pinned template releases")
    p_rl.add_argument("--channel", default=None)
    p_rl.set_defaults(func=cmd_releases)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    stale_hours = getattr(args, "stale_hours", None)
    # Non-finite values evade a bare `<= 0` guard: NaN would silently mark
    # every record stale, while +inf would silently mark every record
    # fresh — the dangerous direction, vacating the D-RC-4 freshness bound
    # the S2 promotion gate rests on. Reject at the boundary like any
    # other bad value (the repo's math.isfinite convention).
    if (stale_hours is not None
            and (not math.isfinite(stale_hours) or stale_hours <= 0)):
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
