#!/usr/bin/env python3
"""Rollout-controller deploy driver: the controller's hands (S4, issue #1287 / #1261).

F-RC-2: the loop's plane deploy path was single-plane, operator-run
(docs/PRODUCTION_DEPLOY_CONTRACT.md); nothing could deploy template V to
plane #k, let alone N planes in waves. This module is the hands: given a
plane record (S1 store) + a release record (S3), it pushes the pinned
template through the Cloudflare tooling, records the landing, and emits
the D-MT5 cost event. Planes are request-driven Workers with no pull
loop, so the driver PUSHES each plane's deploy — the box layer's G18
pull-channel has no plane analog.

Design pins (docs/TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md §4):
- D-RC-2(b): the deploy target is ONLY the pinned (deployment_id,
  worker_sha256) from the release record, read through the fail-closed
  release-show path. The driver never deploys a floating "latest", and
  SHA-256-verifies the deployed bytes against the pin before recording
  the landing.
- Rollback-target trust (adversarial-review advisory, #1287 comment
  6107295238): rollback redeploys the plane's last_known_good pin, but
  refuses any pin with no matching release record, and refuses when the
  pin's (deployment_id, worker_sha256) differs from the release record's
  — a rollback target without a pinned manifest is exactly the floating
  identity D-RC-2(b) exists to kill.
- D-RC-5: freeze is a local refusal, honestly bounded. The freeze state
  lives in the controller's store (<store>/freeze.json); while frozen
  the driver refuses ALL deploys and rollbacks. Outside a freeze it
  refuses deploys to planes not in the live wave (<store>/waves.json —
  the S2 wave machine's writer contract, read here; #1285 adopts it).
  The freeze setter and the refusal live in this CLI ("the same CLI");
  the propagation bound is "the operator's next command" — a freeze set
  against one store dir does not bind a driver run against another.
- D-RC-6: every deploy and rollback the driver performs appends a cost
  event (update/rollback, duration, optional cost) — the driver is the
  D-MT5 ledger's first writer. Missing events do not block promotion;
  cost-summary reports coverage (cost_usd_reported vs count) so the
  D-MT5 revisit query stays honest about its inputs.
- Retired planes are never pushed to: deploy/rollback refuse a plane
  whose status is retired (the fleet invariant is "the controller must
  not promote into" retired planes). The S1 inventory `deploy` command
  keeps its intentional resurrect semantics — the operator records the
  rejoin there first, then the driver can push.
- F-RC-10: the driver writes the artifact join — the plane's deploy
  record carries (deployment_id, worker_sha256), so "which bytes landed
  on plane #k" is answerable, not just "which template" (record schema
  plane-inventory-record/3; the divergence check covers both fields).
- Dry-run: --dry-run prints the deploy plan (plane x template) without
  touching the Cloudflare tooling, writing no journal and emitting no
  cost event — the acceptance path for a lane with zero tenant planes
  today. The gates (freeze, wave, pin) still run: dry-run exercises the
  full path.

The Cloudflare push itself is a seam: DEPLOYER is a callable
(plane_id, deployment_id, worker_sha256) ->
{"worker_sha256_observed": <64-hex>, "duration_s": <optional float>}.
The default fails closed — the operator wires the real deployer
(wrangler/Workers API against the tenant plane's worker) or runs
--dry-run. The driver verifies observed == pinned before recording
anything; a mismatch fails closed with no journal write and no cost
event. A deployer exception fails closed the same way.

Subcommands:
  deploy   --store DIR --plane-id ID --template V [--dry-run]
             [--duration-s N] [--cost-usd X] [--status healthy|degraded]
             [--notes T]
      Push the pinned release for V to the plane (D-RC-5 gates apply).
  rollback --store DIR --plane-id ID [--dry-run]
             [--duration-s N] [--cost-usd X] [--notes T]
      Redeploy the plane's last_known_good pin (release-record verified).
  freeze   --store DIR (--on | --off) [--notes T]
      Set or clear the D-RC-5 controller freeze (S2's halt/promotion read
      the same freeze.json contract).

Store files (beyond the S1/S3 stores):
  <store>/freeze.json  {schema: plane-controller-freeze/1, frozen: bool,
                        set_at, reporter, notes}
  <store>/waves.json   {schema: plane-controller-waves/1,
                        live_wave: int|null, assignments: {plane_id: wave},
                        updated_at, reporter, notes}
  waves.json is S2's writer contract (#1285): the S4 driver only reads
  it. Missing file (or live_wave null) means no wave is live — the
  out-of-wave refusal guards in-progress rollouts only. A corrupt file
  fails closed (refuse), never silently unfreezes or unconstrains.

Exit 0 on a printed result, 2 on bad input / refusal / internal error
(one-line message, never a bare traceback). Stdlib only.
"""

import argparse
import json
import os
import sys
import tempfile

# Sibling modules (fleet/plane_inventory.py, fleet/events.py): script-run
# puts fleet/ on sys.path, so these import as siblings. The pin grammars,
# the error contract, and the store writers are shared with
# plane_inventory (one definition — see its "Public aliases" block and
# #21's centralize-trust-validation follow-up), never duplicated here.
import events
import plane_inventory

FREEZE_SCHEMA = "plane-controller-freeze/1"
FREEZE_NAME = "freeze.json"
WAVES_SCHEMA = "plane-controller-waves/1"
WAVES_NAME = "waves.json"


def _fail(msg):
    """Print a one-line error and exit 2 (the operator's error contract)."""
    print(f"plane_deploy: error: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _default_deployer(plane_id, deployment_id, worker_sha256):
    _fail(
        "no deployer configured: the S4 driver pushes through the Cloudflare "
        "tooling — wire a deployer via plane_deploy.DEPLOYER (a callable "
        "(plane_id, deployment_id, worker_sha256) -> "
        "{'worker_sha256_observed': <64-hex>, 'duration_s': <float>}) "
        "or use --dry-run"
    )


# The Cloudflare push seam. Tests monkeypatch this with a fake; the
# operator wires the real wrangler/Workers-API callable.
DEPLOYER = _default_deployer


def _read_freeze(store_dir):
    """True when the controller store is frozen (D-RC-5).

    Missing file = not frozen (fresh store). Corrupt file, wrong schema,
    or a non-boolean `frozen` fails closed — a tampered freeze file must
    never silently unfreeze the controller.
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


def _read_waves(store_dir):
    """Return (live_wave, assignments) per the S2 writer contract.

    Missing file or live_wave null = no wave live = no wave constraint
    (the out-of-wave refusal guards in-progress rollouts only). Corrupt
    files fail closed.
    """
    path = os.path.join(store_dir, WAVES_NAME)
    if not os.path.exists(path):
        return None, {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        _fail(f"waves file at {path} is unreadable ({exc}) — refusing deploys")
    if not isinstance(data, dict) or data.get("schema") != WAVES_SCHEMA:
        _fail(f"waves file at {path} has an unexpected schema — refusing deploys")
    live_wave = data.get("live_wave")
    assignments = data.get("assignments")
    if live_wave is None:
        return None, {}
    if not isinstance(assignments, dict):
        _fail(f"waves file at {path}: 'assignments' is not an object — refusing deploys")
    # bool is an int subclass; a boolean live_wave is a corrupt wave file,
    # not wave True.
    if isinstance(live_wave, bool) or not isinstance(live_wave, int):
        _fail(f"waves file at {path}: 'live_wave' is not an integer — refusing deploys")
    return live_wave, assignments


def _gates(store_dir, plane_id):
    """D-RC-5 refusals: a frozen store refuses everything; a live wave
    refuses planes outside it. Returns the live wave (or None)."""
    if _read_freeze(store_dir):
        _fail("controller store is frozen — action refused "
              "(D-RC-5; `freeze --off` to resume)")
    live_wave, assignments = _read_waves(store_dir)
    if live_wave is not None:
        assigned = assignments.get(plane_id)
        # The bool trap: JSON true == 1 in Python, so a boolean assignment
        # must not pass as wave 1 — fail closed on a non-integer
        # assignment, per the file's corrupt-waves philosophy.
        if assigned is not None and (isinstance(assigned, bool)
                                     or not isinstance(assigned, int)):
            _fail(f"waves file: assignment for plane {plane_id!r} is not "
                  "an integer — refusing deploys")
        if assigned != live_wave:
            _fail(f"plane {plane_id!r} is not in the live wave {live_wave} — "
                  "action refused (D-RC-5)")
    return live_wave


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


def cmd_freeze(args):
    store_dir = plane_inventory.ensure_store(args.store)
    if bool(args.on) == bool(args.off):
        _fail("specify exactly one of --on / --off")
    frozen = bool(args.on)
    payload = {
        "schema": FREEZE_SCHEMA,
        "frozen": frozen,
        "set_at": plane_inventory.now_iso(),
        "reporter": "operator",
        "notes": args.notes or "",
    }
    # Serialize with the journal lock: the freeze file and the journals
    # are one store, one writer at a time.
    with events.journal_lock(store_dir):
        _atomic_write_json(store_dir, FREEZE_NAME, payload)
    print(json.dumps({"ok": True, "frozen": frozen}))
    return 0


def _run_deployer(plane_id, deployment_id, worker_sha256):
    """Invoke the wired deployer and fail-closed verify the observed bytes.

    Returns the deployer's result dict. Any failure — no deployer, an
    exception, a malformed result, a digest mismatch — fails closed with
    no journal write and no cost event: nothing is recorded that did not
    verifiably land.
    """
    try:
        result = DEPLOYER(plane_id, deployment_id, worker_sha256)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - operator contract: one-line error
        _fail(f"deployer failed for plane {plane_id!r}: {exc}")
    if not isinstance(result, dict):
        _fail(f"deployer for plane {plane_id!r} returned a non-object — "
              "refusing to record the landing")
    observed = result.get("worker_sha256_observed")
    if not plane_inventory.is_sha256_pin(observed):
        _fail(f"deployer for plane {plane_id!r} returned malformed "
              f"worker_sha256_observed {observed!r} — refusing to record "
              "the landing")
    if observed != worker_sha256:
        _fail(f"deployer for plane {plane_id!r} reports worker_sha256 "
              f"{observed} != pinned {worker_sha256} — refusing to record "
              "the landing")
    return result


def _deployer_duration(result, flag_value, what):
    """Duration for the cost event: explicit flag wins, else the deployer's
    reported duration, else None. Garbage from the deployer fails closed."""
    if flag_value is not None:
        return flag_value
    reported = result.get("duration_s")
    if reported is None:
        return None
    return plane_inventory.check_nonneg_number(reported, f"deployer {what}")


def _deploy_record(prev, template, deployment_id, worker_sha256, status, notes):
    """Build the /3 plane record for a driver landing (F-RC-10 artifact join).

    Copies the previous record whole (channel, tenant_id, and the S2-owned
    last_known_good pin are preserved, never written here), then stamps
    the new template + verified artifact identity.
    """
    record = dict(prev)
    # /1- and /2-era normalization (same as the S1 deploy command).
    record.setdefault("last_known_good", None)
    record.setdefault("deployment_id", None)
    record.setdefault("worker_sha256", None)
    record.update(
        {
            "schema": plane_inventory.RECORD_SCHEMA,
            "template_version": template,
            "deployment_id": deployment_id,
            "worker_sha256": worker_sha256,
            "status": status,
            "observed_at": plane_inventory.now_iso(),
            "reporter": "operator",
            "notes": notes or "",
        }
    )
    return record


def cmd_deploy(args):
    store_dir = plane_inventory.ensure_store(args.store)
    plane_id = plane_inventory.check_id(args.plane_id, "--plane-id")
    template = plane_inventory.check_template(args.template)
    duration_s = plane_inventory.check_nonneg_number(args.duration_s, "--duration-s")
    cost_usd = plane_inventory.check_nonneg_number(args.cost_usd, "--cost-usd")
    status = args.status or "healthy"
    if status not in ("healthy", "degraded"):
        _fail("--status must be healthy or degraded, got %r" % (args.status,))

    prev = plane_inventory.read_planes(store_dir).get(plane_id)
    if prev is None:
        _fail(f"plane {plane_id!r} is not registered (register first)")
    if prev.get("status") == "retired":
        _fail(f"plane {plane_id!r} is retired — the driver never pushes to "
              "retired planes (record the rejoin with the inventory "
              "`deploy` command first)")
    # D-RC-5 gates are outermost: a frozen store refuses ALL deploys,
    # before the request's own validity is even examined.
    live_wave = _gates(store_dir, plane_id)
    # D-RC-2(b): the ONLY deploy target is the pinned manifest — read
    # through the fail-closed release reader, never a floating "latest".
    release = plane_inventory.read_release(store_dir, template)
    deployment_id = release["deployment_id"]
    worker_sha256 = release["worker_sha256"]

    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "action": "deploy",
            "plane_id": plane_id,
            "template_version": template,
            "deployment_id": deployment_id,
            "worker_sha256": worker_sha256,
            "gates": {"frozen": False, "live_wave": live_wave,
                      "in_live_wave": True},
        }, indent=2))
        return 0

    result = _run_deployer(plane_id, deployment_id, worker_sha256)
    duration_s = _deployer_duration(result, duration_s, "duration_s")
    record = _deploy_record(prev, template, deployment_id, worker_sha256,
                            status, args.notes)
    plane_inventory.record_plane_observation(store_dir, record)
    # D-RC-6: the driver is the ledger's first writer.
    plane_inventory.append_cost_event(store_dir, plane_id, "update",
                                      duration_s, cost_usd, args.notes or "")
    print(json.dumps({
        "ok": True, "action": "deploy", "plane_id": plane_id,
        "template_version": template, "deployment_id": deployment_id,
        "worker_sha256": worker_sha256, "status": status,
    }))
    return 0


def _rollback_target(store_dir, plane_id):
    """Resolve the rollback target: the plane's last_known_good pin,
    verified against the pinned release record (advisory #1287/6107295238).

    Returns (prev_record, release_record). Fails closed when the pin is
    absent, when no release record matches it, or when the pin's artifact
    identity differs from the release's — a rollback target without a
    pinned manifest is the floating identity D-RC-2(b) exists to kill.
    """
    prev = plane_inventory.read_planes(store_dir).get(plane_id)
    if prev is None:
        _fail(f"plane {plane_id!r} is not registered (register first)")
    pin = prev.get("last_known_good")
    if not pin:
        _fail(f"plane {plane_id!r} has no last_known_good pin — nothing to "
              "roll back to (the S2 promotion step writes the pin on "
              "healthy wave landing)")
    if not isinstance(pin, dict):
        _fail(f"plane {plane_id!r} has a malformed last_known_good pin — "
              "refusing rollback")
    release = plane_inventory.read_release(store_dir, pin.get("template_version"))
    for field in ("deployment_id", "worker_sha256"):
        if pin.get(field) != release[field]:
            _fail(f"plane {plane_id!r}: last_known_good pin {field} "
                  f"{pin.get(field)!r} != pinned release {field} "
                  f"{release[field]!r} — refusing rollback")
    return prev, release


def cmd_rollback(args):
    store_dir = plane_inventory.ensure_store(args.store)
    plane_id = plane_inventory.check_id(args.plane_id, "--plane-id")
    duration_s = plane_inventory.check_nonneg_number(args.duration_s, "--duration-s")
    cost_usd = plane_inventory.check_nonneg_number(args.cost_usd, "--cost-usd")
    status = args.status or "healthy"
    if status not in ("healthy", "degraded"):
        _fail("--status must be healthy or degraded, got %r" % (args.status,))

    # D-RC-5 gates are outermost here too: a frozen store refuses the
    # rollback before the pin is even examined.
    if plane_id not in plane_inventory.read_planes(store_dir):
        _fail(f"plane {plane_id!r} is not registered (register first)")
    live_wave = _gates(store_dir, plane_id)
    prev, release = _rollback_target(store_dir, plane_id)
    if prev.get("status") == "retired":
        _fail(f"plane {plane_id!r} is retired — the driver never pushes to "
              "retired planes (record the rejoin with the inventory "
              "`deploy` command first)")
    template = release["template_version"]
    deployment_id = release["deployment_id"]
    worker_sha256 = release["worker_sha256"]

    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "action": "rollback",
            "plane_id": plane_id,
            "template_version": template,
            "deployment_id": deployment_id,
            "worker_sha256": worker_sha256,
            "gates": {"frozen": False, "live_wave": live_wave,
                      "in_live_wave": True},
        }, indent=2))
        return 0

    result = _run_deployer(plane_id, deployment_id, worker_sha256)
    duration_s = _deployer_duration(result, duration_s, "duration_s")
    record = _deploy_record(prev, template, deployment_id, worker_sha256,
                            status, args.notes)
    plane_inventory.record_plane_observation(store_dir, record)
    plane_inventory.append_cost_event(store_dir, plane_id, "rollback",
                                      duration_s, cost_usd, args.notes or "")
    print(json.dumps({
        "ok": True, "action": "rollback", "plane_id": plane_id,
        "template_version": template, "deployment_id": deployment_id,
        "worker_sha256": worker_sha256, "status": status,
    }))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        description="Rollout-controller deploy driver: the controller's hands "
                    "(S4, #1287). Pushes pinned template releases to tenant "
                    "planes through the Cloudflare tooling."
    )
    p.add_argument("--store", required=True, help="controller store directory")
    sub = p.add_subparsers(dest="command", required=True)

    p_dep = sub.add_parser("deploy", help="deploy a pinned template release to a plane")
    p_dep.add_argument("--plane-id", required=True)
    p_dep.add_argument("--template", required=True,
                       help="template version (must have a pinned release)")
    p_dep.add_argument("--dry-run", action="store_true",
                       help="print the deploy plan; touch nothing")
    p_dep.add_argument("--duration-s", default=None,
                       help="deploy duration for the D-MT5 cost event")
    p_dep.add_argument("--cost-usd", default=None,
                       help="deploy cost for the D-MT5 cost event")
    p_dep.add_argument("--status", default="healthy",
                       choices=("healthy", "degraded"))
    p_dep.add_argument("--notes", default="")
    p_dep.set_defaults(func=cmd_deploy)

    p_rb = sub.add_parser("rollback", help="redeploy the plane's last_known_good pin")
    p_rb.add_argument("--plane-id", required=True)
    p_rb.add_argument("--dry-run", action="store_true",
                      help="print the rollback plan; touch nothing")
    p_rb.add_argument("--duration-s", default=None)
    p_rb.add_argument("--cost-usd", default=None)
    p_rb.add_argument("--status", default="healthy",
                      choices=("healthy", "degraded"))
    p_rb.add_argument("--notes", default="")
    p_rb.set_defaults(func=cmd_rollback)

    p_fr = sub.add_parser("freeze", help="set or clear the D-RC-5 controller freeze")
    p_fr.add_argument("--on", action="store_true", help="freeze: refuse all deploys")
    p_fr.add_argument("--off", action="store_true", help="unfreeze")
    p_fr.add_argument("--notes", default="")
    p_fr.set_defaults(func=cmd_freeze)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - operator contract: one-line error, exit 2
        print(f"plane_deploy: internal error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
