#!/usr/bin/env python3
"""Operator identity pin + release registration, S2 (issue #775 /
TENANT_UPDATE_TRUST_MODEL.md §6 build slice 2).

`fleet register` binds the registering operator's identity to the
release record — the second key that narrows merge-to-main (trust
model §1). The identity primitive is §2's attribution rule carried
forward: one provisioned operator key, pinned at provision time, its
fingerprint in every record. No new identity system is invented here.

Design:

  - **The pin, not the flag.** S1's `update_journal.py append` takes
    `--actor-fingerprint` per invocation — self-attestation by
    whoever runs it, acceptable for the controller on the operator's
    own machine. This CLI takes NO `--actor-fingerprint` flag at all:
    `register` reads the fingerprint from the provisioned pin in the
    store, so a bare name — or anyone else's fingerprint — cannot be
    supplied by accident or intent on the human registration path.
    The fingerprint IS the identity (there is still deliberately no
    `--actor-name`); the shape check is S1's normalization, reused
    verbatim so the canonical form cannot drift between the two.
  - **Write-once.** The pin is written by the provisioning ceremony
    (`init`) and never overwritten in place. Re-pinning the same
    digest is idempotent (provisioning scripts converge); re-pinning
    a *different* digest fails closed — a silent identity swap would
    fork the attribution chain (two operators' records under one
    store, indistinguishable after the fact). Key rotation is a
    separate design (issue #1407); this module names it as the
    refusal's reason rather than inventing a half-baked rotation
    scheme.
  - **The pin is read fresh every invocation.** `register` opens and
    parses `<store>/operator-identity.json` on each run; nothing is
    cached in the environment, so a pin change cannot be bypassed by
    a stale handle. The pin write itself runs under the store-scoped
    journal lock (events.journal_lock — the same lock S1 uses for the
    journal, per S1's "a future S2 registry read-modify-write needs
    the same serialization" note), so two racing `init`s serialize:
    the loser sees the winner's pin and either converges (same) or
    fails closed (different). The write is temp-file + os.replace +
    fsync, never a partial in-place rewrite.
  - **Corrupt pin is an integrity failure.** A missing pin is a usage
    error ("run init first"); a corrupt pin means the trust root
    cannot be trusted — fail closed, journal nothing.
  - **Trust boundary (honest).** The pin binds the *provisioned*
    identity: whoever can write the store owns the identity. The
    store (journal, lock, pin) lives on the control plane / the
    operator's machine — never on a tenant box (S1 docstring) — and
    its DAC boundary is the trust root. This module adds no auth of
    its own; it makes the identity unforgeable *within* the trusted
    operator path. The fingerprint is public, non-secret material:
    no permission dance, no secret handling.
  - **Known residual (TOCTOU, nil impact).** `cmd_register` reads the
    pin *outside* the journal lock that `append_records` takes, so a
    pin swap landing mid-`register` journals under the pre-swap
    identity. Under the trust boundary above this has no practical
    impact — a pin swap requires store write access, which already
    owns the identity — but the read is deliberately not re-taken
    under the lock: re-reading would not change who the store's
    writer is, and the honest statement is this sentence, not a
    second read.

Record flow: `register` delegates to S1 — `update_journal.build_record`
validates the registration record (security channel requires
advisory_ref; ref is generated, never accepted) and
`update_journal.append_records` appends under the journal lock with
referential chaining. The generated `registration_ref` prints to
stdout so the next rollout step can chain to it.

Store layout (extends S1's):

  <store>/operator-identity.json  the pin: {"format": 1,
                                            "operator_fingerprint": "SHA256:…",
                                            "pinned_at": "<UTC ISO-8601>"}
  <store>/update-journal.jsonl     the S1 journal (unchanged)

CLI:

  register.py init --store DIR --operator-fingerprint FP
  register.py register --store DIR --tenant T --release-id R \
      --channel {stable,security} --policy-ref P [--advisory-ref A] [--ts TS]
  register.py show-identity --store DIR

Exit codes: 0 success; 2 usage/validation error (bad fingerprint shape,
missing pin, re-pin refusal, S1 record validation — fail-loud, nothing
journaled); 1 runtime/integrity error (store unwritable, lock failure,
corrupt pin file). Errors go to stderr.

Stdlib only. Exercised through subprocess by the hermetic suite
(test_register.py), like the other fleet suites.
"""

import argparse
import json
import os
import sys

FLEET = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FLEET)
import events  # noqa: E402  (fleet/ is not a package; same-dir import)
import update_journal  # noqa: E402  (S1: owns the canonical fingerprint form)

PIN_NAME = "operator-identity.json"
PIN_FORMAT = 1

# Rotation is deliberately not designed here: a silent identity swap
# forks the attribution chain. Issue #1407 owns the rotation design;
# this message points at it so a confused operator finds the right
# thread instead of working around the refusal.
_REPIN_REFUSAL = (
    "refusing to re-pin: the store already pins operator identity %s, "
    "which differs from the supplied %s. The pin is write-once by design "
    "(silent identity swaps fork the attribution chain); key rotation is "
    "tracked in issue #1407."
)


def _utcnow():
    # Same wire form as S1's timestamps (%Y-%m-%dT%H:%M:%SZ), via S1's
    # helper — the pin's pinned_at must sort/compare against journal ts.
    return update_journal._utcnow()  # noqa: SLF001 (fleet-internal reuse)


def _pin_path(store_dir):
    return os.path.join(store_dir, PIN_NAME)


def _ensure_store(store_dir):
    try:
        os.makedirs(store_dir, exist_ok=True)
    except OSError as exc:
        return "cannot create store dir %s: %s" % (store_dir, exc)
    return None


def read_pin(store_dir):
    """Read the pinned operator identity. Returns (pin, error).

    `pin` is the parsed dict with `operator_fingerprint` (canonical
    form) and `pinned_at`. Error shapes are returned, not raised, so
    the CLI can map "missing" (usage, exit 2) and "corrupt"
    (integrity, exit 1) to different exit codes.
    """
    path = _pin_path(store_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            pin = json.load(fh)
    except FileNotFoundError:
        return None, ("missing", "no pinned operator identity in %s: run "
                      "`register.py init` to pin the provisioned operator "
                      "key first" % store_dir)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return None, ("corrupt", "pinned operator identity %s is unreadable "
                      "(%s): refusing to journal under an untrusted identity"
                      % (path, exc))
    if not isinstance(pin, dict):
        return None, ("corrupt", "pinned operator identity %s is not a "
                      "JSON object: refusing to journal under an untrusted "
                      "identity" % path)
    if pin.get("format") != PIN_FORMAT:
        return None, ("corrupt", "pinned operator identity %s has "
                      "unsupported format %r (expected %d): refusing to "
                      "journal under an untrusted identity"
                      % (path, pin.get("format"), PIN_FORMAT))
    fp = pin.get("operator_fingerprint")
    try:
        canonical = update_journal._normalize_fingerprint(fp)  # noqa: SLF001
    except (ValueError, AttributeError, TypeError) as exc:
        return None, ("corrupt", "pinned operator identity %s carries an "
                      "invalid fingerprint (%s): refusing to journal under "
                      "an untrusted identity" % (path, exc))
    pin = dict(pin)
    pin["operator_fingerprint"] = canonical
    return pin, None


def pin_operator(store_dir, fingerprint):
    """Pin the provisioned operator key. Returns (pin, error).

    Write-once under the store-scoped journal lock: same digest is
    idempotent (returns the existing pin), a different digest fails
    closed, a corrupt existing pin fails closed (its integrity is
    already suspect — do not pave over it).

    `error` is None on success, else (kind, message) with kind
    "usage" (exit 2) or "runtime" (exit 1) — threaded from the
    read_pin kinds and the lock/IO paths, never re-derived by
    string-matching message text.
    """
    try:
        canonical = update_journal._normalize_fingerprint(fingerprint)
    except (ValueError, AttributeError, TypeError) as exc:
        return None, ("usage",
                      "operator fingerprint %r rejected: %s" % (fingerprint, exc))
    err = _ensure_store(store_dir)
    if err:
        return None, ("runtime", err)
    path = _pin_path(store_dir)
    try:
        with events.journal_lock(store_dir):
            existing = None
            if os.path.exists(path):
                pin, perr = read_pin(store_dir)
                if perr:
                    kind, msg = perr
                    return None, ({"missing": "usage",
                                   "corrupt": "runtime"}[kind], msg)
                existing = pin
            if existing is not None:
                if existing["operator_fingerprint"] == canonical:
                    return existing, None
                return None, ("usage", _REPIN_REFUSAL % (
                    existing["operator_fingerprint"], canonical))
            pin = {"format": PIN_FORMAT,
                   "operator_fingerprint": canonical,
                   "pinned_at": _utcnow()}
            tmp = path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(pin, sort_keys=True) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, path)
            except OSError as exc:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                return None, ("runtime",
                              "cannot write pin file %s: %s" % (path, exc))
            return pin, None
    except events.JournalLockError as exc:
        return None, ("runtime", str(exc))


def _die(msg):
    sys.stderr.write("register: error: %s\n" % msg)
    return 2


def cmd_init(args):
    pin, err = pin_operator(args.store, args.operator_fingerprint)
    if err:
        kind, msg = err
        sys.stderr.write("register: error: %s\n" % msg)
        return 1 if kind == "runtime" else 2
    sys.stdout.write("pinned %s\n" % pin["operator_fingerprint"])
    return 0


def cmd_register(args):
    pin, perr = read_pin(args.store)
    if perr:
        kind, msg = perr
        sys.stderr.write("register: error: %s\n" % msg)
        # Missing pin: the operator has not provisioned this store
        # (usage); corrupt pin: the trust root is untrustworthy
        # (integrity) — different failures, different exit codes.
        return 2 if kind == "missing" else 1
    data = {"release_id": args.release_id, "channel": args.channel,
            "policy_ref": args.policy_ref}
    if args.advisory_ref is not None:
        data["advisory_ref"] = args.advisory_ref
    record, err = update_journal.build_record(
        "registration", args.tenant, pin["operator_fingerprint"], data,
        ts=args.ts)
    if err:
        return _die(err)
    count, err = update_journal.append_records(args.store, [record])
    if err:
        # A registration never cites a ref, so append_records can only
        # fail here on I/O or lock — runtime, exit 1.
        sys.stderr.write("register: error: %s\n" % err)
        return 1
    sys.stdout.write("%s\n" % record["registration_ref"])
    return 0


def cmd_show_identity(args):
    pin, perr = read_pin(args.store)
    if perr:
        kind, msg = perr
        sys.stderr.write("register: error: %s\n" % msg)
        return 2 if kind == "missing" else 1
    sys.stdout.write(json.dumps(pin, sort_keys=True) + "\n")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="register.py",
        description="Operator identity pin + release registration, "
                    "S2 (issue #775).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser(
        "init",
        help="pin the provisioned operator key for this store (write-once)")
    p_init.add_argument("--store", required=True,
                        help="store dir (holds operator-identity.json)")
    p_init.add_argument("--operator-fingerprint", required=True,
                        help="provisioned operator key fingerprint "
                             "(SHA256: form or 64-char hex; never a name)")
    p_init.set_defaults(func=cmd_init)

    p_register = sub.add_parser(
        "register",
        help="register a release in the update journal under the pinned "
             "operator identity")
    p_register.add_argument("--store", required=True,
                            help="store dir (must hold the pinned identity)")
    p_register.add_argument("--tenant", required=True,
                            help="tenant id (per-tenant scoping; no default)")
    p_register.add_argument("--release-id", required=True)
    p_register.add_argument("--channel", required=True,
                            choices=("stable", "security"))
    p_register.add_argument("--policy-ref", required=True,
                            help="policy document reference (e.g. "
                                 "docs/UPDATE_CHANNEL_POLICY.md)")
    p_register.add_argument("--advisory-ref",
                            help="required on the security channel")
    p_register.add_argument("--ts",
                            help="UTC ISO-8601 timestamp (default: now)")
    p_register.set_defaults(func=cmd_register)

    p_show = sub.add_parser(
        "show-identity",
        help="print the pinned operator identity (read-only)")
    p_show.add_argument("--store", required=True,
                        help="store dir")
    p_show.set_defaults(func=cmd_show_identity)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
