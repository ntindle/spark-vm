#!/usr/bin/env python3
"""Control-plane update journal, S1 (issue #775 / G13 / TENANT_UPDATE_TRUST_MODEL.md).

Design: docs/TENANT_UPDATE_TRUST_MODEL.md §2 (the audit landing) + §6 build
slice 1 ("S1 — control-plane update journal + schema: the §2 JSONL journal
with the attribution fields, per-tenant scoping, and registration-ref
chaining. The journal exists before the scheduler does — decisions are
auditable from day one"). S2 (the `fleet register` CLI + operator identity)
and S3 (attested event ingestion) are separate issues; this module is the
store they build on.

Key design rules, from the doc (call-site-auditable):

  - **The authoritative record is the control plane's JSONL journal.**
    The tenant holds root inside the guest (H11): any audit line written
    to the box is forgeable. This journal lives on the control plane /
    the operator's machine — never on a tenant box.
  - **Attribution on every line.** Every record carries `tenant_id`
    (per-tenant scoping; the §2 journal is per-tenant by construction),
    `actor_fingerprint` (the pinned provisioned operator key's
    fingerprint — TENANT_UPDATE_TRUST_MODEL.md §2 — never a bare name),
    and `registration_ref` (chaining back to the authorizing
    registration). Unattributed records are rejected loudly, never
    journaled: an unattributed reimage is an unaccountable one.
  - **The fingerprint is structural, not decorative.** The CLI takes
    `--actor-fingerprint` only — there is no `--actor-name` flag, so a
    bare name cannot be journaled by accident. Accepted: the repo's
    `SHA256:` base64 fingerprint form (pairing/ed25519.fingerprint(),
    whitespace/padding tolerant) or the same 32-byte digest as
    lowercase hex; everything normalizes to one canonical
    `SHA256:<base64>` form in the journal. The shape check is the
    enforcement point.
  - **No phantom entries.** A reimage that was deferred, skipped
    (arc-busy, suspended, unhealthy — G11's scheduling constraint), or
    never started gets a `deferred` / `skipped` line with the reason —
    never a silent absence, never an invented success. `deferred` and
    `skipped` are first-class record types, not comments.
  - **registration_ref is generated, never accepted.** On `registration`
    the CLI computes `reg-` + sha256 over the authorization-bearing
    inputs (release_id, channel, policy_ref, advisory_ref, ts, the
    canonical actor fingerprint) and prints it; every other rollout
    record type must *cite* a ref, and the append fails closed unless
    that ref names a registration already journaled for the same
    tenant. Accepting a caller-supplied ref on registration would let
    two distinct registration events share one ref — forking the
    authorization chain.
  - **`freeze`/`unfreeze` carry no registration_ref.** Freeze is
    operator-level and release-independent (ROLLOUT_CONTROLLER_DESIGN.md
    §3); `halt`/`promote` are per-rollout and must chain to the
    rollout's registration.
  - **Writer clock is trusted here.** Unlike the fleet event stream
    (events.py: box clocks are never trusted for ordering), the writer
    of this journal is the control plane / the operator — not a tenant
    box — so the writer-supplied (or auto) `ts` is authoritative.
  - **Schema-exact.** Unknown fields are rejected: a misspelled
    `tenent_id` journaling under a wrong key is an attribution hole,
    and silently dropping it is a different attribution hole.

Store layout and write discipline follow the repo's fleet journal
family (inventory.py `append_journal`, events.py `journal_lock`):

  <store>/update-journal.jsonl   append-only §2 records, one JSON object
                                 per line (this file; distinct from
                                 inventory's journal.jsonl — observation
                                 records must not share provenance with
                                 authorization records)

Writes: one newline-terminated JSON object per single write() syscall
(line buffering), O_APPEND positioning atomicity, fsync before return —
crash-safe: an append that exits 0 survives an OS crash. Appends run
under the store-scoped `events.journal_lock` (the lock is store-scoped,
not journal-scoped; a future S2 registry read-modify-write needs the
same serialization — with the same bounded wait (300s, then a loud
JournalLockError, never a silent wedge; see events.journal_lock).
Readers stay unlocked: a reader racing a writer
may observe a partial last line — it is reported as skipped with a
loud warning, never gate-consumed. The lock is host-local flock: it
serializes processes on this machine only. A store shared over
NFS/multi-host needs its own design (G26's fleet event stream is the
named future); this claims no cross-host exclusion.

Retention and the tenant read path are G19 (#660 / #778's lane) — this
module deliberately has no prune. The read command exists so operators
(and later the read API) can answer "what happened" from the journal
directly; malformed lines are reported as `skipped`, never
gate-consumed — a corrupt line is missing evidence, never evidence.

Both-supported note (per §6): the same primitives serve the
self-hosted operator's N-box estate — registration, the journal, the
freeze — with the operator as the only actor and the estate name as
`--tenant`. The hosted delta is tenant scoping (one journal per tenant
plane) and the attestation requirement (S3).

CLI:

  update_journal.py append --store DIR --tenant T --actor-fingerprint FP \\
      --record registration --data '{"release_id": "...", "channel": "stable", ...}'
  update_journal.py append --store DIR --tenant T --actor-fingerprint FP \\
      --record reimage --data '{"box_id": "...", "image_from": "...", ...,
                                "registration_ref": "reg-..."}'
  update_journal.py read --store DIR [--tenant T] [--record TYPE] [--since TS]

Exit codes: 0 success; 2 usage/validation error (fail-loud — nothing is
journaled on a validation failure); 1 runtime error (store unwritable,
lock failure). Errors go to stderr.

Stdlib only. Exercised through subprocess by the hermetic suite
(test_update_journal.py), like every fleet module.
"""

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

FLEET = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FLEET)
import events  # noqa: E402  (fleet/ is not a package; same-dir import)

JOURNAL_NAME = "update-journal.jsonl"

# Fingerprint normalization: the provisioned operator key's fingerprint
# is pairing/ed25519.fingerprint()'s form — 'SHA256:' + base64 of the
# 32-byte SHA-256 digest, grouped in fours for phone read-back
# (e.g. 'SHA256:ab12 cd34 ...'). The journal stores ONE canonical form
# so the cross-restart identity the trust model requires (§2: "one key,
# pinned at provision time, fingerprint in every record ... stable
# across restarts") is comparable byte-for-byte: 'SHA256:' +
# unpadded base64 of the 32-byte digest, no whitespace.
#
# Accepted inputs: (a) the SHA256: form (prefix case-insensitive,
# whitespace/padding tolerant — mirroring ed25519.parse_fingerprint,
# which is the authority; this module mirrors its logic rather than
# importing across components, per the fleet modules' small-helper
# mirroring convention), and (b) lowercase hex of exactly 64 chars
# (the same 32-byte digest in hex). A bare name ("operator",
# "ntindle") matches neither shape — the "never a bare name" rule is
# enforced by the shape, and there is deliberately no --actor-name
# flag for it to sneak through.
import base64 as _b64


def _normalize_fingerprint(text):
    """Return the canonical journal form, or raise ValueError."""
    if not isinstance(text, str):
        raise ValueError("not a fingerprint")
    t = text.strip()
    if t.upper().startswith("SHA256:"):
        t = t[len("SHA256:"):]
    t = "".join(t.split())
    # Hex form: exactly 64 lowercase hex chars = the 32-byte digest.
    if re.fullmatch(r"[0-9a-f]{64}", t):
        raw = bytes.fromhex(t)
    else:
        t += "=" * (-len(t) % 4)
        try:
            raw = _b64.b64decode(t, validate=True)
        except Exception:
            raise ValueError("not a valid fingerprint")
    if len(raw) != 32:
        raise ValueError("fingerprint is not a 32-byte SHA-256 digest")
    return "SHA256:" + _b64.b64encode(raw).decode().rstrip("=")

_TS_FORMATS = ("%Y-%m-%dT%H:%M:%SZ",)

# Record vocabulary: TENANT_UPDATE_TRUST_MODEL.md §2. Each entry is
# (required type-specific fields, optional type-specific fields,
#  field-type constraints {field: kind}, enum constraints {field: set}).
#
# Common fields (every record, enforced separately):
#   ts, record, tenant_id, actor_fingerprint,
#   registration_ref (all types except registration and freeze/unfreeze)
_RECORD_SCHEMA = {
    "registration": (
        {"release_id", "channel", "policy_ref"},
        {"advisory_ref"},
        {"release_id": "str", "channel": "str", "policy_ref": "str",
         "advisory_ref": "str"},
        {"channel": {"stable", "security"}},
    ),
    "wave_assignment": (
        {"box_id", "wave", "canary", "manifest_version"},
        set(),
        {"box_id": "str", "wave": "int", "canary": "bool",
         "manifest_version": "str"},
        {},
    ),
    "promotion": (
        {"from_wave", "to_wave", "gate_evidence_refs"},
        set(),
        {"from_wave": "int", "to_wave": "int",
         "gate_evidence_refs": "list[str]"},
        {},
    ),
    "reimage": (
        {"box_id", "image_from", "image_to", "wave",
         "migration_outcome"},
        {"g17_outcome_ref"},
        {"box_id": "str", "image_from": "str", "image_to": "str",
         "wave": "int", "migration_outcome": "str",
         "g17_outcome_ref": "str"},
        {"migration_outcome": {"success", "failed"}},
    ),
    "maintenance": (
        {"box_id", "transition", "arc"},
        set(),
        {"box_id": "str", "transition": "str", "arc": "str"},
        {"transition": {"enter", "exit"}},
    ),
    "freeze": (
        {"reason"},
        set(),
        {"reason": "str"},
        {},
    ),
    "unfreeze": (
        {"reason"},
        set(),
        {"reason": "str"},
        {},
    ),
    "halt": (
        {"release_id", "wave", "reason"},
        set(),
        {"release_id": "str", "wave": "int", "reason": "str"},
        {},
    ),
    "promote": (
        {"release_id", "to_wave", "reason"},
        set(),
        {"release_id": "str", "to_wave": "int", "reason": "str"},
        {},
    ),
    "deferred": (
        {"box_id", "reason"},
        set(),
        {"box_id": "str", "reason": "str"},
        {},
    ),
    "skipped": (
        {"box_id", "reason"},
        set(),
        {"box_id": "str", "reason": "str"},
        {},
    ),
}

# freeze/unfreeze are release-independent (operator-level, global):
# they carry no registration_ref. Every other type except registration
# chains to the authorizing registration.
_NO_REGISTRATION_REF = {"freeze", "unfreeze"}

_COMMON_FIELDS = {"ts", "record", "tenant_id", "actor_fingerprint",
                  "registration_ref"}


def _utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(ts):
    for fmt in _TS_FORMATS:
        try:
            datetime.strptime(ts, fmt)
            return True
        except (ValueError, TypeError):
            continue
    return False


def _check_value(field, kind, value):
    if kind == "str":
        return isinstance(value, str) and len(value) > 0
    if kind == "int":
        # bool is a subclass of int — a canary=true where an int is
        # expected is a schema violation, not a truthy int.
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "list[str]":
        return (isinstance(value, list) and len(value) > 0
                and all(isinstance(v, str) and len(v) > 0
                        for v in value))
    return False


def build_record(record_type, tenant_id, actor_fingerprint, data, ts=None):
    """Validate and build a journal record. Returns (record, error).

    `data` is the type-specific payload (a dict). On any validation
    failure returns (None, <human-readable reason>) — the caller must
    journal nothing.
    """
    if record_type not in _RECORD_SCHEMA:
        return None, "unknown record type %r (expected one of: %s)" % (
            record_type, ", ".join(sorted(_RECORD_SCHEMA)))
    if not isinstance(data, dict):
        return None, "--data must be a JSON object, got %s" % type(
            data).__name__
    if not tenant_id or not isinstance(tenant_id, str):
        return None, "tenant_id is required (per-tenant scoping is " \
            "structural — pass --tenant; there is no default)"
    if not actor_fingerprint or not isinstance(actor_fingerprint, str):
        return None, "actor_fingerprint is required (the pinned " \
            "provisioned operator key's fingerprint — never a bare name)"
    try:
        actor_fingerprint = _normalize_fingerprint(actor_fingerprint)
    except ValueError as exc:
        return None, "actor_fingerprint %r rejected: %s — a bare name " \
            "cannot be journaled as an identity" % (actor_fingerprint, exc)
    if ts is None:
        ts = _utcnow()
    elif not _parse_ts(ts):
        return None, "ts %r is not UTC ISO-8601 (%%Y-%%m-%%dT%%H:%%M:%%SZ)" % ts

    required, optional, kinds, enums = _RECORD_SCHEMA[record_type]

    # Common fields live at the CLI level (args), never inside --data:
    # a data-level tenant_id would silently shadow (or be shadowed by)
    # the CLI one — both directions are attribution hazards.
    # registration_ref is excluded: it is a common field handled by the
    # chaining logic below (required on most types, generated on
    # registration, forbidden on freeze/unfreeze) — excluded here, not
    # accepted.
    bad_common = set(data) & (_COMMON_FIELDS - {"registration_ref"})
    if bad_common:
        return None, "field(s) %s are CLI-level, not --data fields" % (
            ", ".join(sorted(bad_common)))
    # Schema-exact: unknown fields are rejected, not dropped.
    # registration_ref is a common field handled by the chaining
    # logic below (required on most types, generated on registration,
    # forbidden on freeze/unfreeze) — excluded here, not accepted.
    unknown = set(data) - required - optional - {"registration_ref"}
    if unknown:
        return None, "unknown field(s) for record %r: %s" % (
            record_type, ", ".join(sorted(unknown)))
    missing = required - set(data)
    if missing:
        return None, "missing required field(s) for record %r: %s" % (
            record_type, ", ".join(sorted(missing)))
    for field in required | optional:
        if field not in data:
            continue
        kind = kinds[field]
        if not _check_value(field, kind, data[field]):
            return None, "field %r must be %s, got %r" % (
                field, kind, data[field])
    for field, allowed in enums.items():
        if field in data and data[field] not in allowed:
            return None, "field %r must be one of %s, got %r" % (
                field, sorted(allowed), data[field])

    # Security channel registration must carry the advisory reference
    # (§1: "On the security channel, registration must carry the
    # advisory reference").
    if (record_type == "registration"
            and data.get("channel") == "security"
            and "advisory_ref" not in data):
        return None, "registration on the security channel requires " \
            "advisory_ref"

    record = {
        "ts": ts,
        "record": record_type,
        "tenant_id": tenant_id,
        "actor_fingerprint": actor_fingerprint,
    }
    if record_type == "registration":
        # A caller-supplied ref on registration would fork the chain
        # (two distinct registration events sharing one ref): rejected,
        # not ignored — schema-exact applies to common fields too.
        if "registration_ref" in data:
            return None, "registration_ref is generated on registration, " \
                "never supplied"
        # The ref names this specific registration event. The hash covers
        # every authorization-bearing input — release, channel, policy,
        # advisory, moment, actor — so two registrations that differ in
        # any of them can never share a ref (a re-registration with
        # identical inputs is idempotent by design: same ref).
        hash_input = [data["release_id"], data["channel"],
                      data["policy_ref"], data.get("advisory_ref", ""),
                      ts, actor_fingerprint]
        digest = hashlib.sha256(
            "|".join(hash_input).encode("utf-8")).hexdigest()[:16]
        record["registration_ref"] = "reg-" + digest
    elif record_type in _NO_REGISTRATION_REF:
        # freeze/unfreeze: release-independent, operator-level. A
        # registration_ref on one would misattribute a global operator
        # action to a single release — rejected, not ignored.
        if "registration_ref" in data:
            return None, "record %r is release-independent and must " \
                "not carry registration_ref" % record_type
    else:
        if "registration_ref" not in data:
            return None, "record %r must chain to its authorizing " \
                "registration via registration_ref" % record_type
        ref = data["registration_ref"]
        if not (isinstance(ref, str) and ref.startswith("reg-")
                and len(ref) > 4):
            return None, "registration_ref %r is not a generated " \
                "registration ref" % (ref,)
        record["registration_ref"] = ref

    for field in sorted(required | optional):
        if field in data:
            record[field] = data[field]
    return record, None


def _ensure_store(store_dir):
    try:
        os.makedirs(store_dir, exist_ok=True)
    except OSError as exc:
        return "cannot create store dir %s: %s" % (store_dir, exc)
    return None


def _known_registration_refs(store_dir):
    """(tenant_id, registration_ref) pairs already journaled.

    Malformed lines are skipped, never treated as registrations — a
    corrupt line is missing evidence, never evidence.
    """
    journal_path = os.path.join(store_dir, JOURNAL_NAME)
    known = set()
    try:
        fh = open(journal_path, "r", encoding="utf-8")
    except FileNotFoundError:
        return known
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if (isinstance(obj, dict)
                    and obj.get("record") == "registration"
                    and isinstance(obj.get("tenant_id"), str)
                    and isinstance(obj.get("registration_ref"), str)):
                known.add((obj["tenant_id"], obj["registration_ref"]))
    return known


def append_records(store_dir, records):
    """Append validated records to the journal. Returns (count, error).

    Same write discipline as inventory.append_journal: one
    newline-terminated line per single write() (line buffering),
    O_APPEND positioning atomicity, fsync before returning. The append
    runs under the store-scoped journal lock (events.journal_lock) —
    the lock is store-scoped, and a future S2 registry
    read-modify-write needs the same serialization.

    Referential chaining (fail-closed): every record that cites a
    registration_ref must cite a registration already in this store
    under the same tenant — a reimage citing a never-registered ref
    journals nothing. Registrations earlier in the same batch count
    (the batch is walked in order), so a register-then-chain sequence
    in one call works.
    """
    err = _ensure_store(store_dir)
    if err:
        return None, err
    try:
        with events.journal_lock(store_dir):
            known = _known_registration_refs(store_dir)
            for record in records:
                # Library contract: records come from build_record. A
                # non-record dict is a caller bug — fail closed, never
                # journal half a batch.
                if (not isinstance(record, dict)
                        or record.get("record") not in _RECORD_SCHEMA
                        or not isinstance(record.get("tenant_id"), str)):
                    return None, "append_records takes validated records " \
                        "from build_record; got %r" % (record,)
                ref = record.get("registration_ref")
                if record["record"] == "registration":
                    known.add((record["tenant_id"], ref))
                elif record["record"] not in _NO_REGISTRATION_REF:
                    if (record["tenant_id"], ref) not in known:
                        return None, "registration_ref %r is not " \
                            "registered for tenant %r: nothing journaled" \
                            % (ref, record["tenant_id"])
            journal_path = os.path.join(store_dir, JOURNAL_NAME)
            try:
                with open(journal_path, "a", encoding="utf-8",
                          buffering=1) as fh:
                    for record in records:
                        fh.write(json.dumps(record, sort_keys=True)
                                 + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
            except OSError as exc:
                return None, "cannot append to update journal: %s" % exc
    except events.JournalLockError as exc:
        return None, str(exc)
    return len(records), None


def read_records(store_dir, tenant=None, record=None, since=None):
    """Read the journal. Returns (rows, skipped, error).

    Readers stay unlocked. A reader racing a writer may observe a
    partial last line — it lands in `skipped` with the rest. Malformed
    lines are counted in `skipped` and never returned — a corrupt line
    is missing evidence, never evidence, and is never gate-consumed.
    """
    journal_path = os.path.join(store_dir, JOURNAL_NAME)
    rows = []
    skipped = 0
    try:
        fh = open(journal_path, "r", encoding="utf-8")
    except FileNotFoundError:
        return [], 0, None
    except OSError as exc:
        return None, None, "cannot read update journal: %s" % exc
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                skipped += 1
                continue
            if not isinstance(obj, dict) or obj.get("record") not in _RECORD_SCHEMA:
                skipped += 1
                continue
            if tenant is not None and obj.get("tenant_id") != tenant:
                continue
            if record is not None and obj.get("record") != record:
                continue
            if since is not None and obj.get("ts", "") < since:
                continue
            rows.append(obj)
    return rows, skipped, None


def _die(msg):
    sys.stderr.write("update_journal: error: %s\n" % msg)
    return 2


def cmd_append(args):
    try:
        data = json.loads(args.data)
    except (ValueError, UnicodeDecodeError) as exc:
        return _die("--data is not valid JSON: %s" % exc)
    record, err = build_record(args.record_type, args.tenant,
                               args.actor_fingerprint, data, ts=args.ts)
    if err:
        return _die(err)
    count, err = append_records(args.store, [record])
    if err:
        # A dangling registration_ref is an input/authorization problem
        # (wrong ref — fix the command, don't retry), not an
        # environment problem: exit 2 like any other validation
        # failure. Nothing is journaled either way.
        if "is not registered for tenant" in err:
            return _die(err)
        sys.stderr.write("update_journal: error: %s\n" % err)
        return 1
    if args.record_type == "registration":
        sys.stdout.write("%s\n" % record["registration_ref"])
    return 0


def cmd_read(args):
    if args.since is not None and not _parse_ts(args.since):
        return _die("--since %r is not UTC ISO-8601 "
                    "(%%Y-%%m-%%dT%%H:%%M:%%SZ)" % args.since)
    rows, skipped, err = read_records(args.store, tenant=args.tenant,
                                      record=args.record_type,
                                      since=args.since)
    if err:
        sys.stderr.write("update_journal: error: %s\n" % err)
        return 1
    for row in rows:
        sys.stdout.write(json.dumps(row, sort_keys=True) + "\n")
    if skipped:
        sys.stderr.write("update_journal: warning: %d malformed "
                         "line(s) skipped (never gate-consumed)\n" % skipped)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="update_journal.py",
        description="Control-plane update journal, S1 (issue #775).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_append = sub.add_parser("append", help="validate and journal a record")
    p_append.add_argument("--store", required=True,
                          help="store dir (holds update-journal.jsonl)")
    p_append.add_argument("--tenant", required=True,
                          help="tenant id (per-tenant scoping; no default)")
    p_append.add_argument("--actor-fingerprint", required=True,
                          help="pinned provisioned operator key fingerprint "
                               "(lowercase hex 32-128 chars; never a name)")
    p_append.add_argument("--record", dest="record_type", required=True,
                          choices=sorted(_RECORD_SCHEMA),
                          help="§2 record type")
    p_append.add_argument("--data", required=True,
                          help="JSON object with the type-specific fields")
    p_append.add_argument("--ts",
                          help="UTC ISO-8601 timestamp (default: now)")
    p_append.set_defaults(func=cmd_append)

    p_read = sub.add_parser("read", help="read the journal")
    p_read.add_argument("--store", required=True,
                        help="store dir (holds update-journal.jsonl)")
    p_read.add_argument("--tenant",
                        help="filter to one tenant id")
    p_read.add_argument("--record", dest="record_type",
                        choices=sorted(_RECORD_SCHEMA),
                        help="filter to one record type")
    p_read.add_argument("--since",
                        help="UTC ISO-8601 lower bound on ts")
    p_read.set_defaults(func=cmd_read)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
