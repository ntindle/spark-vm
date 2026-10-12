#!/usr/bin/env python3
"""Tenant-plane rollout controller: wave assignment + promotion (S2, issue #1285 / #1261).

F-RC-2: the plane deploy path was single-plane, operator-run
(docs/PRODUCTION_DEPLOY_CONTRACT.md). S1 shipped the ledger
(fleet/plane_inventory.py — the operator-recorded per-plane inventory),
S3 the pinned template releases (D-RC-2 pick (b): template version ->
(deployment_id, worker_sha256)), S4 the deploy driver
(fleet/plane_deploy.py — the controller's hands). This module is the
brain: given the S1 ledger + a pinned release, it computes wave
assignments, gates wave promotion on the operator-observed state, halts
bad rollouts, and writes the last_known_good rollback pins the S4 driver
redeploys.

Design pins (docs/TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md §4):
- D-RC-3 — Wave assignment is deterministic plus tenant-aware. Wave 0 is
  the canary and holds ONLY planes whose tenants are explicitly
  designated canary tenants (`canary-tenants` records the designation in
  the controller's store — the controller mints no identity; it reads
  plane_id/tenant_id from the S1 store). Non-canary planes use the box
  lane's mechanical rule, transferred: int(sha256(plane_id).hexdigest(),
  16) % buckets + 1. Single-plane estates get no automatic canary: the
  one plane is wave 1 and promotion is an explicit operator command with
  an audit record.
- D-RC-4 — Promotion gates read operator-observed state only. "Did the
  wave land" = every live-wave plane's S1 record is on the target
  template, fresh within the staleness window, and operator-observed
  healthy. The controller never trusts self-reported plane health for
  promotion (plane-signed health events are S5's named later scope). A
  degraded plane in the live wave is a bad wave signal: promotion
  refuses and the operator halts. S5 extends the signal: the
  operator-observed update-event journal is the wave-health signal the
  gates consume — a live-wave plane whose latest event since the wave
  went live is an unresolved deploy-failed refuses promotion as a
  bad-signal; the operator records a fresh landing (or reassigns) to
  clear it. Missing journal (pre-S5 stores) carries no signal: D-RC-6's
  "missing events do not block promotion" holds.
- D-RC-5 — Freeze is a local refusal, honestly bounded. The controller
  reads the same freeze.json the S4 driver reads
  (plane_inventory.read_controller_freeze — one definition, shared);
  promotion and new rollouts refuse while frozen. The propagation bound
  is "the operator's next command" — planes pull nothing, so no
  sub-tick guarantee is claimed.
- D-RC-7 — S2's answer to F-RC-9 (the channel axis S3 added): the
  convergence identity is the template version alone; the expedited
  security channel rides the release record's `channel` field (exact
  "security"), not a separate flag — one spelling, the lane's pin
  discipline. Security releases get compressed waves (canary + one
  wave), never ungated. `stale --expected V` is unchanged
  (template-only).
- Halt: a bad wave signal stops promotion; already-landed waves stay
  (rollback is S4's command). A halted rollout is terminal for the
  controller — the fix ships as a new template version (release pins are
  immutable), and `assign` starts a fresh rollout; the stale gate makes
  re-promoting already-landed waves instant, so a false-alarm halt costs
  one assign + promote round-trip, not a re-landing.
- F-RC-6: the promotion step is the ONLY writer of per-plane
  last_known_good pins (S1/S3/S4 preserve them). The writer never
  invents a pin: the template must have a release record and the pin
  fields match the released record exactly (advisory #1285/6107294719,
  Security); the pin shape (required keys + ISO-8601 recorded_at) is
  validated at write time so a malformed pin cannot detonate in the S4
  driver (advisory #1285/6107294719, QA). Pin writes are idempotent, so a
  crash between the pin writes and the wave advance is safe to re-run.

Subcommands:
  assign         --store DIR --template V [--buckets N] [--dry-run] [--notes T]
      Compute wave assignments for template V and open the rollout at the
      first non-empty wave. The rollout target is ONLY a pinned release
      (D-RC-2(b)) — an unpinned template fails closed. Refuses when a
      rollout is already live or the store is frozen. A halted rollout
      may be superseded by a fresh assign (recorded in the audit).
      --dry-run prints the would-be wave map and writes nothing — no
      waves.json, no journal record — so the operator checks a
      misconfigured canary set before opening a rollout that would need
      a terminal halt to redo. All refusals fire exactly as in a real
      assign. Degraded assigned planes are warned about on stderr (the
      wave cannot promote until they are healthy or re-observed).
  promote        --store DIR [--stale-hours H] [--notes T]
      Advance the live wave when the D-RC-4 gate passes: stamp
      last_known_good on the landed wave's planes, then move live_wave to
      the next assigned wave (or null when the rollout is complete).
      Refuses on a bad wave signal, an unconverged wave, a frozen store,
      or a halted rollout. Re-runnable: pins are idempotent and the
      advance re-verifies the rollout state under the store lock.
      Gate refusals (bad-signal, not-converged) are audited to
      waves_journal.jsonl (action promote_refused, carrying the refusal
      reason, the live wave, and the staleness window) — a refused
      promotion that does not lead to a halt leaves a trace; the
      successful-promote record carries stale_hours as well.
  halt           --store DIR --reason R [--notes T]
      Stop the live rollout (bad wave signal). Already-landed waves stay;
      the halt is recorded with its reason for the audit trail.
  status         --store DIR
      Print the rollout state (read-only): template, channel, waves with
      per-wave convergence, halted/frozen flags, canary designations.
  canary-tenants --store DIR (--add T | --remove T | --list)
      Explicitly designate (or undesignate) a tenant's planes for the
      canary wave (D-RC-3's tenant rule).

Store files (beyond the S1/S3 stores):
  <store>/waves.json          {schema: plane-controller-waves/1,
                               template_version, channel, buckets,
                               live_wave: int|null, halted: null|{...},
                               assignments: {plane_id: wave},
                               updated_at, reporter, notes}
                              S2's writer contract (#1285): the S4 driver
                              only reads it (live_wave + assignments).
                              Missing file (or live_wave null) = no live
                              rollout. Assignments are plain ints >= 0
                              (wave 0 = canary); a boolean is never a wave.
  <store>/canary_tenants.json {schema: plane-controller-canary-tenants/1,
                               tenants: [sorted], updated_at, reporter}
  <store>/waves_journal.jsonl append-only audit records
                              {schema: plane-controller-wave-audit/1, at,
                               reporter, action, ...}. An operator audit
                              trail, not a trust root: no snapshot, no
                              divergence check — the S4 driver never reads
                              it, and the wave file carries its own
                              fail-closed validation on every read.

Exit 0 on a printed result, 2 on bad input / refusal / internal error
(one-line message, never a bare traceback). Stdlib only.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone

# Sibling modules (fleet/plane_inventory.py, fleet/events.py): script-run
# puts fleet/ on sys.path, so these import as siblings. The pin grammars,
# the error contract, the clock, the staleness rule, and the freeze
# reader are shared with plane_inventory (one definition — see its
# "Public aliases" block), never duplicated here.
import events
import plane_inventory

WAVES_SCHEMA = "plane-controller-waves/1"
WAVES_NAME = "waves.json"
CANARY_TENANTS_SCHEMA = "plane-controller-canary-tenants/1"
CANARY_TENANTS_NAME = "canary_tenants.json"
AUDIT_SCHEMA = "plane-controller-wave-audit/1"
AUDIT_JOURNAL_NAME = "waves_journal.jsonl"

CANARY_WAVE = 0
DEFAULT_BUCKETS = 4
MAX_BUCKETS = 8
SECURITY_CHANNEL = "security"

# last_known_good pin shape (S3's schema, F-RC-6; S2 is the pinned writer).
_PIN_FIELDS = ("template_version", "deployment_id", "worker_sha256",
               "recorded_at")


def _fail(msg):
    """Print a one-line error and exit 2 (the operator's error contract)."""
    print(f"plane_waves: error: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _atomic_write_json(store_dir, name, payload):
    """Atomically replace <store>/<name> (process-unique tmp path, os.replace)."""
    path = os.path.join(store_dir, name)
    fd, tmp = tempfile.mkstemp(dir=store_dir, prefix=name + ".tmp.")
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


def _read_waves(store_dir):
    """Read the controller's wave state. None when no rollout file exists.

    Fail closed on any corrupt or unexpected content — a tampered waves
    file must never present a forged live wave to the promotion gate or
    a forged assignment set to the S4 driver.
    """
    path = os.path.join(store_dir, WAVES_NAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        _fail(f"waves file at {path} is unreadable ({exc})")
    if not isinstance(data, dict) or data.get("schema") != WAVES_SCHEMA:
        _fail(f"waves file at {path} has an unexpected schema")
    for key in ("template_version", "channel"):
        if not isinstance(data.get(key), str) or not data[key]:
            _fail(f"waves file at {path}: {key!r} is not a non-empty string")
    buckets = data.get("buckets")
    if isinstance(buckets, bool) or not isinstance(buckets, int) or buckets < 1:
        _fail(f"waves file at {path}: 'buckets' is not a positive integer")
    live_wave = data.get("live_wave")
    if live_wave is not None and (
        isinstance(live_wave, bool) or not isinstance(live_wave, int)
        or live_wave < CANARY_WAVE
    ):
        _fail(f"waves file at {path}: 'live_wave' is not a wave number or null")
    halted = data.get("halted")
    if halted is not None:
        if not isinstance(halted, dict):
            _fail(f"waves file at {path}: 'halted' is not an object or null")
        for key in ("at", "wave", "reason"):
            if key not in halted:
                _fail(f"waves file at {path}: 'halted' is missing {key!r}")
    assignments = data.get("assignments")
    if not isinstance(assignments, dict):
        _fail(f"waves file at {path}: 'assignments' is not an object")
    for plane_id, wave in assignments.items():
        # bool is an int subclass; a boolean assignment is a corrupt wave
        # file, not wave True — the S4 reader fails closed on it, and so
        # does the writer's own reader.
        if (not isinstance(plane_id, str) or isinstance(wave, bool)
                or not isinstance(wave, int) or wave < CANARY_WAVE):
            _fail(f"waves file at {path}: assignment for plane {plane_id!r} "
                  "is not a non-negative integer wave")
    # A live wave that names no assigned wave is a corrupt (or forged)
    # wave file: without this, promote would gate over an empty plane
    # set, stamp nothing, and mark the rollout "complete" — completing a
    # rollout that never landed and lifting the S4 wave constraint.
    if live_wave is not None and live_wave not in set(assignments.values()):
        _fail(f"waves file at {path}: 'live_wave' {live_wave} names no "
              "assigned wave")
    return data


def _read_canary_tenants(store_dir):
    """The D-RC-3 canary designations. Missing file = no designations."""
    path = os.path.join(store_dir, CANARY_TENANTS_NAME)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        _fail(f"canary-tenants file at {path} is unreadable ({exc})")
    if not isinstance(data, dict) or data.get("schema") != CANARY_TENANTS_SCHEMA:
        _fail(f"canary-tenants file at {path} has an unexpected schema")
    tenants = data.get("tenants")
    if not isinstance(tenants, list):
        _fail(f"canary-tenants file at {path}: 'tenants' is not a list")
    # Symmetric with the write path (check_id at --add): a hand-edited
    # designation that is not a valid tenant id fails closed instead of
    # silently never matching.
    for tenant in tenants:
        plane_inventory.check_id(tenant, "canary tenant")
    return set(tenants)


def _audit_locked(store_dir, action, **fields):
    """Append one audit record. Caller must hold events.journal_lock."""
    record = {
        "schema": AUDIT_SCHEMA,
        "at": plane_inventory.now_iso(),
        "reporter": "operator",
        "action": action,
    }
    record.update(fields)
    path = os.path.join(store_dir, AUDIT_JOURNAL_NAME)
    line = json.dumps(record, sort_keys=True) + "\n"
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        _fail(f"cannot append to {AUDIT_JOURNAL_NAME}: {exc}")


def _wave_for_plane(plane_id, buckets):
    """The box lane's mechanical rule, transferred (D-RC-3): wave 0 is the
    canary, so non-canary planes hash into 1..buckets."""
    digest = hashlib.sha256(plane_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % buckets + 1


def _compute_assignments(planes, canary_tenants, buckets):
    """Compute wave assignments from the inventory + canary designations
    (D-RC-3). Pure computation: returns (assignments, eligible,
    single_estate).

    #1346: this runs inside the store lock, over inputs re-read inside
    the same lock acquisition, so a concurrent retire (or
    canary-designation change) landing between the command's start and
    the lock cannot leave stale assignments in waves.json. Never call it
    with pre-lock inputs for anything authoritative.
    """
    eligible = sorted(
        pid for pid, rec in planes.items() if rec.get("status") != "retired"
    )
    single_estate = len(eligible) == 1
    assignments = {}
    for plane_id in eligible:
        # D-RC-3: no automatic canary on a single-plane estate — the
        # designation is ignored and the one plane is wave 1, even when
        # its tenant is canary-designated. A canary of one plane is a
        # canary in name only: zero signal before committing the fleet.
        # The wave is pinned (not hashed): with one plane the bucket
        # count is meaningless, and wave 1 is the least surprise.
        if single_estate:
            assignments[plane_id] = 1
        elif planes[plane_id].get("tenant_id") in canary_tenants:
            assignments[plane_id] = CANARY_WAVE
        else:
            assignments[plane_id] = _wave_for_plane(plane_id, buckets)
    return assignments, eligible, single_estate


def _check_pin_shape(pin):
    """Validate the last_known_good pin at write time (advisory
    #1285/6107294719, QA): required keys + ISO-8601 recorded_at, so a
    malformed pin fails here rather than detonating in the S4 driver at
    rollback time."""
    if not isinstance(pin, dict):
        _fail("refusing to write malformed last_known_good pin: not an object")
    for field in _PIN_FIELDS:
        if field not in pin:
            _fail(f"refusing to write malformed last_known_good pin: "
                  f"missing {field!r}")
    try:
        datetime.fromisoformat(pin["recorded_at"])
    except (TypeError, ValueError):
        _fail("refusing to write malformed last_known_good pin: "
              f"recorded_at {pin.get('recorded_at')!r} is not ISO-8601")
    return pin


def _build_pin(store_dir, template):
    """Build the last_known_good pin for a landed wave — from the release
    record, never invented (advisory #1285/6107294719, Security): the
    template must have a release record and the pin fields match the
    released record exactly."""
    # read_release fails closed when the template is unpinned.
    release = plane_inventory.read_release(store_dir, template)
    # Trust-chain note: deployment_id/worker_sha256 grammars are NOT
    # re-validated here. They were validated at release write time
    # (cmd_release) and the release is re-read through the
    # journal-consistency check on every read_release; the pin copies the
    # release fields verbatim, so re-validating would be a second
    # spelling of the same rule.
    pin = {
        "template_version": release["template_version"],
        "deployment_id": release["deployment_id"],
        "worker_sha256": release["worker_sha256"],
        "recorded_at": plane_inventory.now_iso(),
    }
    return _check_pin_shape(pin)


def _stamp_landed_pins_locked(store_dir, plane_ids, template):
    """Write last_known_good for each landed plane (F-RC-6's writer: ONLY
    the S2 promotion step writes these pins; S1/S3/S4 preserve them).

    Caller must hold events.journal_lock: the stamps are part of the
    promotion's critical section — after the in-lock freeze check and
    re-gate — so a freeze landing mid-promote (#1345) cannot leave pins
    on a refused rollout, and no plane record can change between its
    gate read and its pin write. The lock cannot nest (journal_lock
    raises JournalLockError on re-entry), hence the
    record_plane_observation_locked variant — one lock acquisition, one
    critical section.

    Idempotent: a plane already pinned to this exact (template,
    deployment, sha256) is skipped, so re-running promote after a crash
    between the pin writes and the wave advance never double-stamps.
    The pin write is not an observation: observed_at is preserved so the
    staleness gate keeps reading the operator's last actual observation,
    not the controller's bookkeeping time.

    Returns the plane_ids actually stamped.
    """
    pin = _build_pin(store_dir, template)
    stamped = []
    for plane_id in sorted(plane_ids):
        current = plane_inventory.read_planes(store_dir).get(plane_id)
        if current is None:
            _fail(f"plane {plane_id!r} is not registered (register first)")
        prev_pin = current.get("last_known_good") or {}
        if all(prev_pin.get(f) == pin[f]
               for f in ("template_version", "deployment_id", "worker_sha256")):
            continue
        record = dict(current)
        record["last_known_good"] = pin
        plane_inventory.record_plane_observation_locked(store_dir, record)
        stamped.append(plane_id)
    return stamped


def _wave_gate(store_dir, waves, template, stale_hours):
    """D-RC-4: may the live wave advance? Returns (ok, reason, landed_planes).

    ok=False carries "not-converged: ..." (the wave has not landed — the
    operator waits or investigates) or "bad-signal: ..." (a degraded
    plane in the live wave, or an unresolved deploy-failed event in the
    S5 update-event journal — promotion refuses; the operator halts).
    Structural problems fail closed (raise): a missing record or a
    retired plane in the live wave means the operator must reassign —
    the gate never silently routes around it.
    """
    live_wave = waves["live_wave"]
    planes = plane_inventory.read_planes(store_dir)
    wave_planes = sorted(
        pid for pid, wave in waves["assignments"].items() if wave == live_wave
    )
    not_converged = []
    degraded = []
    for plane_id in wave_planes:
        rec = planes.get(plane_id)
        if rec is None:
            _fail(f"plane {plane_id!r} is assigned to wave {live_wave} but "
                  "has no record — register it or reassign the rollout")
        if rec.get("status") == "retired":
            _fail(f"plane {plane_id!r} retired mid-rollout — reassign the "
                  "rollout (the controller never promotes into retired planes)")
        status = rec.get("status")
        if status == "degraded":
            degraded.append(plane_id)
        elif status != "healthy":
            not_converged.append((plane_id, f"status-{status}"))
        elif rec.get("template_version") != template:
            not_converged.append((plane_id, "version-mismatch"))
        elif not plane_inventory.is_record_fresh(rec, stale_hours):
            not_converged.append((plane_id, "stale-record"))
    if degraded:
        names = ", ".join(repr(p) for p in degraded)
        return (False,
                f"bad-signal: planes {names} degraded on template "
                f"{template!r} — promotion refused; halt the rollout", [])
    # S5 (#1288): the operator-observed update-event journal is the
    # wave-health signal the gates consume. A live-wave plane whose
    # latest event since the wave went live is an unresolved
    # deploy-failed is a bad signal — the wave did not land cleanly even
    # if the records look converged. The operator clears it by recording
    # a fresh landing (S4 deploy / S1 `deploy` / `event --kind
    # deploy-landed`) or by reassigning the rollout (a fresh assign
    # re-baselines the event window). Missing journal = no signal
    # (D-RC-6: missing events do not block promotion).
    failed = _unresolved_deploy_failures(store_dir, wave_planes, waves)
    if failed:
        detail = ", ".join(
            f"{pid} (failed {at})" for pid, at in failed)
        return (False,
                f"bad-signal: planes with unresolved deploy-failed events "
                f"since wave {live_wave} went live: {detail} — promotion "
                f"refused; record a fresh landing or reassign the rollout",
                [])
    if not_converged:
        detail = ", ".join(f"{pid} ({why})" for pid, why in not_converged)
        return (False, f"wave {live_wave} has not landed: {detail}", [])
    return True, "", wave_planes


def _unresolved_deploy_failures(store_dir, wave_planes, waves):
    """Latest update-event per live-wave plane since the wave went live.

    Returns [(plane_id, observed_at)] for planes whose latest event in
    the window is deploy-failed. Events before the wave's updated_at
    belong to an earlier rollout and never block a fresh wave. The
    journal reader fails closed on corruption; a missing journal yields
    no signal.
    """
    try:
        wave_since = datetime.fromisoformat(waves.get("updated_at"))
    except (TypeError, ValueError):
        _fail("waves file: 'updated_at' is missing or unparseable — "
              "refusing to evaluate the update-event gate")
    if wave_since.tzinfo is None:
        wave_since = wave_since.replace(tzinfo=timezone.utc)
    wave_set = set(wave_planes)
    latest = {}
    for ev in plane_inventory.read_plane_events(store_dir):
        if ev["plane_id"] not in wave_set:
            continue
        try:
            at = datetime.fromisoformat(ev["observed_at"])
        except ValueError:
            _fail("plane event journal: unparseable observed_at "
                  f"{ev['observed_at']!r} — refusing to evaluate the "
                  "update-event gate")
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if at < wave_since:
            continue
        prev = latest.get(ev["plane_id"])
        if prev is None or at >= prev[1]:
            latest[ev["plane_id"]] = (ev["kind"], at)
    return sorted(
        (pid, at.isoformat()) for pid, (kind, at) in latest.items()
        if kind == "deploy-failed")


def cmd_assign(args):
    store_dir = plane_inventory.ensure_store(args.store)
    template = plane_inventory.check_template(args.template)
    # The rollout target is ONLY a pinned release (D-RC-2(b)): fail closed
    # on an unpinned template — waves under a version scheme the
    # controller cannot deploy are exactly what S3's gate was for.
    release = plane_inventory.read_release(store_dir, template)
    channel = release["channel"]
    # #1374 round-1 (Security B1): the release-time spelling refusal only
    # guards NEW releases — a record pinned before it (e.g. channel
    # "Security"/"SECURITY") still reads back, misses the D-RC-7 exact
    # match below, and silently travels normal waves: the same
    # bad-failure-direction hole this change claims to close. Fail closed
    # on a non-lowercase stored channel — the recovery path is a
    # re-release with the exact spelling (never silent normalization).
    if channel != channel.lower():
        _fail(f"release channel must be lowercase (got {channel!r}) — "
              f're-release with the exact spelling; D-RC-7 keys on '
              f'"security"')
    buckets = args.buckets
    if channel == SECURITY_CHANNEL:
        # D-RC-7: the expedited security channel rides the release
        # record's channel field — compressed waves (canary + one wave),
        # never ungated. --buckets on a security release is refused: the
        # controller decides the compression, not the invocation.
        if buckets is not None:
            _fail("security releases travel compressed waves (canary + one "
                  "wave) — --buckets is refused (D-RC-7)")
        buckets = 1
    else:
        buckets = DEFAULT_BUCKETS if buckets is None else buckets
        if buckets < 1 or buckets > MAX_BUCKETS:
            _fail(f"--buckets must be 1..{MAX_BUCKETS}, got {buckets}")

    notes = args.notes or ""

    with events.journal_lock(store_dir):
        # #1346: the assignment inputs are read and the assignments
        # computed inside the store lock — there is intentionally no
        # pre-lock computation. The earlier revision read planes +
        # canary designations outside the lock and wrote waves.json from
        # the stale inputs: a retire (or canary-designation change)
        # landing between the reads and the lock was absorbed silently.
        # The freeze and live-rollout checks below were always re-verified
        # in-lock; now the inputs are too.
        planes = plane_inventory.read_planes(store_dir)
        canary_tenants = _read_canary_tenants(store_dir)
        assignments, eligible, single_estate = _compute_assignments(
            planes, canary_tenants, buckets)
        if not eligible:
            _fail("no eligible planes: every plane is retired (or none registered)")
        # Waves with no planes are never live: the empty canary is
        # skipped, not promoted through, and a single-plane estate opens
        # at wave 1.
        live_wave = min(assignments.values())
        if single_estate:
            flag = ("single-plane estate: no automatic canary (D-RC-3); "
                    "promotion is an explicit operator command")
            notes = f"{notes} {flag}".strip()
        if plane_inventory.read_controller_freeze(store_dir):
            _fail("controller store is frozen — unfreeze before starting "
                  "a rollout (D-RC-5)")
        existing = _read_waves(store_dir)
        if existing is not None and existing.get("live_wave") is not None:
            _fail(f"rollout of template {existing['template_version']!r} is "
                  f"live at wave {existing['live_wave']} — halt it before "
                  "assigning a new rollout")
        superseded = existing.get("halted") if existing else None
        # #1343 item 4: a degraded assigned plane is a wave that cannot
        # promote — warn, don't refuse (the plane may recover, and the
        # gate refuses promotion on bad signal anyway). stderr, so the
        # JSON result on stdout stays parseable. Fires in --dry-run too:
        # checking the wave map before opening the rollout is exactly
        # when the operator wants to hear this.
        degraded = sorted(pid for pid in eligible
                          if planes[pid].get("status") == "degraded")
        if degraded:
            names = ", ".join(degraded)
            print(f"plane_waves: warning: {len(degraded)} assigned plane(s) "
                  f"degraded ({names}) — a degraded plane in the live wave "
                  f"refuses promotion now; degraded planes in later waves "
                  f"refuse promotion when their wave goes live. Re-assign "
                  f"or halt if they will not recover.",
                  file=sys.stderr)
        if args.dry_run:
            # #1343 item 3: print the would-be wave map, write nothing —
            # no waves.json, no journal record. Every refusal above fired
            # exactly as in a real assign; the only difference is the
            # side effects are skipped.
            print(json.dumps({
                "ok": True, "action": "assign", "dry_run": True,
                "template_version": template, "channel": channel,
                "buckets": buckets, "live_wave": live_wave,
                "assignments": assignments, "planes": len(eligible),
                "canary_planes": sum(1 for w in assignments.values()
                                     if w == CANARY_WAVE),
                "degraded_planes": degraded,
                "superseded_halt": superseded, "notes": notes,
            }))
            return 0
        state = {
            "schema": WAVES_SCHEMA,
            "template_version": template,
            "channel": channel,
            "buckets": buckets,
            "live_wave": live_wave,
            "halted": None,
            "assignments": assignments,
            "updated_at": plane_inventory.now_iso(),
            "reporter": "operator",
            "notes": notes,
        }
        _atomic_write_json(store_dir, WAVES_NAME, state)
        _audit_locked(
            store_dir, "assign", template_version=template, channel=channel,
            buckets=buckets, live_wave=live_wave, planes=len(eligible),
            canary_planes=sum(1 for w in assignments.values()
                              if w == CANARY_WAVE),
            superseded_halt=superseded, notes=notes,
        )
    print(json.dumps({
        "ok": True, "action": "assign", "template_version": template,
        "channel": channel, "buckets": buckets, "live_wave": live_wave,
        "assignments": assignments,
    }))
    return 0


def cmd_promote(args):
    store_dir = plane_inventory.ensure_store(args.store)
    stale_hours = args.stale_hours
    # NaN evades `<= 0` (nan <= 0 is False) and would silently mark every
    # record stale — reject it at the boundary like S1 does.
    if stale_hours is not None and (stale_hours <= 0 or math.isnan(stale_hours)):
        _fail("--stale-hours must be a positive number")
    if stale_hours is None:
        stale_hours = plane_inventory.DEFAULT_STALE_HOURS

    waves = _read_waves(store_dir)
    # A halted rollout reports itself as halted, not as "no rollout" —
    # the operator's next step differs (assign a new rollout vs assign
    # the first one).
    if (waves is not None and waves.get("halted")
            and waves.get("live_wave") is None):
        # Product blocker (round 1): name BOTH recoveries. The false-alarm
        # path — re-assign the same template, landed waves re-verify
        # instantly — is the case the design optimizes for; steering the
        # operator toward minting a pointless new release here is the
        # 2am misdirection this message must not do.
        _fail("rollout is halted — halted rollouts are terminal: assign "
              "the same template again to resume after a false alarm "
              "(landed waves re-verify instantly), or assign a new "
              "template version carrying the fix")
    if waves is None or waves.get("live_wave") is None:
        _fail("no live rollout — assign one first")
    template = waves["template_version"]
    live_wave = waves["live_wave"]

    # Frozen means nothing changes: refuse before the gate and before any
    # pin write. The in-lock check below stays authoritative against a
    # freeze that lands mid-promote — and the pin stamps now happen inside
    # the same lock acquisition, after it (#1345), so the whole promotion
    # is atomic with respect to the freeze.
    if plane_inventory.read_controller_freeze(store_dir):
        _fail("controller store is frozen — promotion refused (D-RC-5)")

    # #1343 item 1: the gate's refusal is audited, not just printed. The
    # pre-lock gate used to fail here without contending the store lock;
    # the audit record must be written under the lock, so every refusal
    # falls through to the in-lock re-gate below, which audits the
    # refusal before failing. A refused promotion that does not lead to
    # a halt otherwise leaves no trace — and bad-signal/not-converged
    # refusals are exactly the wave-health signals the S5 reporting
    # consumes. The in-lock re-gate is authoritative; its landed-plane
    # list is what the stamps use.
    with events.journal_lock(store_dir):
        fresh = _read_waves(store_dir)
        # The advance is authoritative only on the rollout we gated.
        # Template + assignments are the rollout's identity: the gate's
        # landed-plane list is valid for exactly this rollout, so a
        # concurrent assign (refused while live, but not against a
        # hand-edit) or any wave-file tampering must not be silently
        # absorbed into an advance of a different rollout.
        if (fresh is None or fresh.get("live_wave") != live_wave
                or fresh.get("halted")
                or fresh.get("template_version") != template
                or fresh.get("assignments") != waves["assignments"]):
            _fail("rollout state changed during promotion — re-run promote")
        if plane_inventory.read_controller_freeze(store_dir):
            _fail("controller store is frozen — promotion refused (D-RC-5)")
        ok, reason, landed = _wave_gate(store_dir, fresh, template,
                                       stale_hours)
        if not ok:
            _audit_locked(
                store_dir, "promote_refused",
                template_version=template, from_wave=live_wave,
                reason=reason, stale_hours=stale_hours,
            )
            _fail(f"promotion refused: {reason}")
        # F-RC-6: the promotion step writes each landed plane's
        # last_known_good pin. Idempotent (see _stamp_landed_pins_locked),
        # so a crash between here and the wave advance is safe to re-run.
        stamped = _stamp_landed_pins_locked(store_dir, landed, template)
        remaining = sorted(
            {wave for wave in fresh["assignments"].values()
             if wave > live_wave}
        )
        new_live = remaining[0] if remaining else None
        fresh["live_wave"] = new_live
        fresh["updated_at"] = plane_inventory.now_iso()
        if args.notes:
            # Append, never overwrite: the assign-time notes carry the
            # single-plane D-RC-3 flag, which must survive promotions.
            prev_notes = fresh.get("notes", "")
            fresh["notes"] = (f"{prev_notes} {args.notes}".strip()
                              if prev_notes else args.notes)
        _atomic_write_json(store_dir, WAVES_NAME, fresh)
        _audit_locked(
            store_dir, "promote", template_version=template,
            from_wave=live_wave, to_wave=new_live,
            landed_planes=landed, pins_written=stamped,
            stale_hours=stale_hours, notes=args.notes or "",
        )
    result = {
        "ok": True, "action": "promote", "template_version": template,
        "from_wave": live_wave, "to_wave": new_live,
        "pins_written": stamped,
    }
    if new_live is None:
        result["rollout"] = "complete"
    print(json.dumps(result))
    return 0


def cmd_halt(args):
    store_dir = plane_inventory.ensure_store(args.store)
    reason = (args.reason or "").strip()
    if not reason:
        _fail("--reason is required (a halt without a reason is unauditable)")
    with events.journal_lock(store_dir):
        waves = _read_waves(store_dir)
        if waves is None or waves.get("live_wave") is None:
            _fail("no live rollout to halt")
        wave = waves["live_wave"]
        # Already-landed waves stay (their plane records are untouched);
        # rollback is S4's command. The halt ends this rollout for the
        # controller — the fix ships as a new template version.
        waves["live_wave"] = None
        waves["halted"] = {
            "at": plane_inventory.now_iso(),
            "wave": wave,
            "reason": reason,
            "notes": args.notes or "",
        }
        waves["updated_at"] = plane_inventory.now_iso()
        _atomic_write_json(store_dir, WAVES_NAME, waves)
        _audit_locked(
            store_dir, "halt", template_version=waves["template_version"],
            wave=wave, reason=reason, notes=args.notes or "",
        )
    print(json.dumps({
        "ok": True, "action": "halt",
        "template_version": waves["template_version"],
        "halted_at_wave": wave, "reason": reason,
    }))
    return 0


def cmd_status(args):
    store_dir = plane_inventory.ensure_store(args.store)
    stale_hours = plane_inventory.DEFAULT_STALE_HOURS
    waves = _read_waves(store_dir)
    out = {
        "frozen": plane_inventory.read_controller_freeze(store_dir),
        "canary_tenants": sorted(_read_canary_tenants(store_dir)),
        "rollout": None,
    }
    if waves is not None:
        template = waves["template_version"]
        planes = plane_inventory.read_planes(store_dir)
        wave_info = {}
        for wave in sorted(set(waves["assignments"].values())):
            members = sorted(
                pid for pid, w in waves["assignments"].items() if w == wave
            )
            # Summary convergence (the promotion gate is authoritative;
            # this is the operator's at-a-glance view).
            landed = all(
                (planes.get(pid) or {}).get("template_version") == template
                and (planes.get(pid) or {}).get("status") == "healthy"
                and plane_inventory.is_record_fresh(planes.get(pid) or {},
                                                   stale_hours)
                for pid in members
            )
            wave_info[str(wave)] = {
                "planes": members,
                "landed": landed,
                "live": wave == waves.get("live_wave"),
            }
        out["rollout"] = {
            "template_version": template,
            "channel": waves["channel"],
            "buckets": waves["buckets"],
            "live_wave": waves.get("live_wave"),
            "halted": waves.get("halted"),
            "waves": wave_info,
            "updated_at": waves.get("updated_at"),
        }
    print(json.dumps(out, indent=2))
    return 0


def cmd_canary_tenants(args):
    store_dir = plane_inventory.ensure_store(args.store)
    if args.list:
        print(json.dumps(
            {"canary_tenants": sorted(_read_canary_tenants(store_dir))}))
        return 0
    if bool(args.add) == bool(args.remove):
        _fail("specify exactly one of --add / --remove / --list")
    tenant = plane_inventory.check_id(args.add or args.remove, "--add/--remove")
    action = "canary_add" if args.add else "canary_remove"
    with events.journal_lock(store_dir):
        tenants = _read_canary_tenants(store_dir)
        if args.add:
            tenants.add(tenant)
        else:
            tenants.discard(tenant)
        payload = {
            "schema": CANARY_TENANTS_SCHEMA,
            "tenants": sorted(tenants),
            "updated_at": plane_inventory.now_iso(),
            "reporter": "operator",
        }
        _atomic_write_json(store_dir, CANARY_TENANTS_NAME, payload)
        _audit_locked(store_dir, action, tenant_id=tenant)
    print(json.dumps({"ok": True, "action": action, "tenant_id": tenant,
                      "canary_tenants": sorted(tenants)}))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        description="Tenant-plane rollout controller: wave assignment + "
                    "promotion (S2, #1285). The controller's brain — the "
                    "S4 deploy driver (fleet/plane_deploy.py) is its hands."
    )
    p.add_argument("--store", required=True, help="controller store directory")
    sub = p.add_subparsers(dest="command", required=True)

    p_as = sub.add_parser("assign", help="compute wave assignments, open the rollout")
    p_as.add_argument("--template", required=True,
                      help="template version (must have a pinned release)")
    p_as.add_argument("--buckets", type=int, default=None,
                      help="non-canary wave buckets, 1..8 "
                           f"(default {DEFAULT_BUCKETS}; refused for security releases)")
    p_as.add_argument("--dry-run", action="store_true",
                      help="print the would-be wave map and write nothing "
                           "(#1343): no waves.json, no journal record; "
                           "refusals fire exactly as in a real assign")
    p_as.add_argument("--notes", default="")
    p_as.set_defaults(func=cmd_assign)

    p_pr = sub.add_parser("promote", help="advance the live wave when the gate passes")
    p_pr.add_argument("--stale-hours", type=float, default=None,
                      help="record staleness window "
                           f"(default {plane_inventory.DEFAULT_STALE_HOURS})")
    p_pr.add_argument("--notes", default="")
    p_pr.set_defaults(func=cmd_promote)

    p_ha = sub.add_parser("halt", help="stop the live rollout (bad wave signal); "
                                        "resume by assigning the same template again "
                                        "(false alarm) or a new template carrying the fix")
    p_ha.add_argument("--reason", required=True,
                      help="why the rollout stops (audited)")
    p_ha.add_argument("--notes", default="")
    p_ha.set_defaults(func=cmd_halt)

    p_st = sub.add_parser("status", help="print the rollout state (read-only)")
    p_st.set_defaults(func=cmd_status)

    p_ct = sub.add_parser("canary-tenants",
                          help="designate canary tenants (D-RC-3); "
                               "takes effect on the next assign — a change "
                               "racing an in-flight assign is absorbed by "
                               "it (#1346) — never on a live rollout")
    p_ct.add_argument("--add", default=None, metavar="TENANT",
                      help="designate a tenant's planes for the canary wave")
    p_ct.add_argument("--remove", default=None, metavar="TENANT",
                      help="undesignate a tenant")
    p_ct.add_argument("--list", action="store_true",
                      help="list designated tenants")
    p_ct.set_defaults(func=cmd_canary_tenants)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - operator contract: one-line error, exit 2
        print(f"plane_waves: internal error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
