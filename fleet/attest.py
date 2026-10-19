#!/usr/bin/env python3
"""Box-event attestation for the fleet update-event stream (#1516 S3).

The trust model (docs/TENANT_UPDATE_TRUST_MODEL.md, S3 of the build
slices) promises: box-identity attestation gates what consuming gates
may read (S3 T2 — "unattested events may be logged, never
gate-consumed"). Until this module, `fleet/events.py` stamped every
ingested row `"attested": False,  # S1/S2: false, always`, and the
attestation the trust doc names was design work with no owner. This
module is the mechanism.

Design (pinned):

  - **Primitive: the box's ed25519 identity key — held BELOW the
    tenant.** No new identity system is invented (the trust doc's S2
    precedent), but the key's *custody* is the load-bearing decision of
    this slice, not a wiring detail: under the trust model's §3 frame
    ("the tenant holds root inside the guest"), any guest-readable key
    is tenant-readable, so a hosted tenant box MUST sign with a key
    held in the layer below (the provisioner / host agent). The #844
    pairing key is explicitly disqualified as a signing key: it lives
    at `~sparkpair/.config/spark-pair/enrollment.json` inside the guest
    filesystem, so a root tenant could exfiltrate the seed and mint
    *attested* forgeries — a forgery-laundering mechanism wearing T2's
    clothes. An operator-estate box signs with its provisioned key.
    The mechanism itself is key-agnostic — it verifies against whatever
    pubkey the store pins for the box_id — so selecting and
    provisioning the layer-below key is the producer lane's acceptance
    criterion.
  - **What is signed: the raw row, bound to box_id.** The signature
    covers the canonical bytes of ``{"box_id": box_id, "row":
    <row minus the attestation member>}``. Raw audit rows do not carry
    box_id (the collector supplies it from the estate layout), so the
    envelope binds it explicitly — a signature lifted from box A never
    verifies for box B. The envelope covers the *raw row*, not the
    collector's translated event: the translation is a pure function
    of signed inputs (`event_id` is derived from signed fields;
    `note`/`received_at` are collector-local), so any forgery of an
    outcome, kind, or version field breaks the signature, and the box
    never has to replicate collector logic. The `attestation` member
    itself is outside the envelope (it carries the signature).
  - **Canonical form.** `json.dumps(..., sort_keys=True,
    separators=(",", ":"), ensure_ascii=False)` over the envelope dict.
    The signer signs these exact bytes; the collector re-serializes the
    parsed row the same way. JSON round-trips are value-stable under
    this form (numbers/strings/bools/null survive loads->dumps
    identically), and verification re-canonicalizes the parsed *values*
    — so key order, whitespace, and indentation of the written line
    are irrelevant; only value-changing serializers break
    verification. `format_attested_row` is the box-side contract: use
    it rather than hand-rolling the line.
  - **Registry: write-once `<store>/box-keys.json`.** `pin_box_key`
    pins box_id -> 32-byte ed25519 pubkey with the operator-pin
    discipline from fleet/register.py: idempotent re-pin of the same
    key, fail-closed on a different key (a silent key swap would fork
    the attribution chain — rotation is a separate design, like the
    operator key's #1407), corrupt registry = integrity failure, temp
    file + os.replace + fsync under the store's journal lock so two
    racing pins serialize.
  - **Fail-closed verification.** `verify_attestation` never raises:
    malformed attestation, missing pinned key, or bad signature all
    yield `attested=False`. A bad signature on a row that *claims*
    attestation is the forgery signal — it is journaled with the
    loudest note. A row with no `attestation` member is the legacy
    path: silently `attested=False` (the schema still represents both).
  - **The T2 rule as code.** `gate_consumable_events` is the pinned
    acceptance for the first gate builder (G15 controller): consume
    only `attested is True` rows. Until the controller exists, the
    rule lives here and in the ingest, documented — not enforced
    against a gate that does not exist yet.

Box-side emission (the producer half) is one call:
`format_attested_row(seed, box_id, row)` returns the canonical journal
line to append (the `attestation` member included). Wiring the deploy
agent to sign rows at emit time is the G18/producer lane's follow-up —
this slice ships the mechanism, the registry, and the ingest half.
"""

import base64
import hashlib
import json
import os
import sys
import tempfile

_FLEET = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_FLEET)
_PAIRING = os.path.join(_REPO_ROOT, "pairing")
if _PAIRING not in sys.path:
    sys.path.insert(0, _PAIRING)
import ed25519  # noqa: E402  (stdlib-only RFC 8032, pairing/ed25519.py)

BOX_KEYS_NAME = "box-keys.json"
ATTESTATION_MEMBER = "attestation"

# Lengths, pinned: ed25519 pubkey 32 bytes (64 hex), signature 64 bytes
# (128 hex). Shape-checked at every boundary, never assumed.
_PUBKEY_HEX_LEN = 64
_SIG_HEX_LEN = 128


# --- Envelope ---------------------------------------------------------------

def envelope_bytes(box_id, row):
    """Canonical bytes the box signs and the collector verifies.

    The envelope binds the box identity to the row: raw audit rows do
    not carry box_id (the collector supplies it), so it is pinned into
    the signed structure explicitly. The `attestation` member is
    excluded — it carries the signature, so it cannot be part of what
    is signed.
    """
    claim = {k: v for k, v in row.items() if k != ATTESTATION_MEMBER}
    envelope = {"box_id": box_id, "row": claim}
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _fingerprint_of_pubkey(pubkey_bytes):
    return ed25519.fingerprint(pubkey_bytes)


# --- Signing (box side) ------------------------------------------------------

def sign_row(seed, box_id, row):
    """Sign a journal row with the box's 32-byte ed25519 seed.

    Returns the `attestation` member dict to attach to the row:
    {"key_fingerprint": <SHA256: form>, "sig": <128-hex>}. The
    fingerprint is metadata for the operator (out-of-band key
    confirmation at the pin ceremony); the signature is the binding.
    Raises on bad inputs — the producer half fails loud, never ships a
    half-signed row.
    """
    if not isinstance(seed, (bytes, bytearray)) or len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    if not isinstance(box_id, str) or not box_id:
        raise ValueError("box_id must be a non-empty string")
    if not isinstance(row, dict):
        raise ValueError("row must be a dict")
    if ATTESTATION_MEMBER in row:
        raise ValueError("row already carries an attestation member")
    pub = ed25519.publickey_from_seed(bytes(seed))
    sig = ed25519.sign(bytes(seed), envelope_bytes(box_id, row))
    return {"key_fingerprint": _fingerprint_of_pubkey(pub),
            "sig": bytes(sig).hex()}


def format_attested_row(seed, box_id, row):
    """Return the canonical journal line for a signed row (with newline).

    The line is serialized with the same canonical form the envelope
    uses, so the collector's re-serialization of the parsed row is
    byte-identical to what was signed. This is the box-side producer
    contract: rows written by foreign serializers are out of contract.
    """
    attestation = sign_row(seed, box_id, row)
    full = dict(row)
    full[ATTESTATION_MEMBER] = attestation
    return json.dumps(full, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False) + "\n"


# --- Verification (collector side; never raises) ----------------------------

def _hex_bytes(text, want_len):
    """Parse hex into bytes, or return None (never raises).

    Case- and surrounding-whitespace-tolerant (the fingerprint
    normalization precedent): the canonical pinned form is lowercase.
    """
    if not isinstance(text, str):
        return None
    t = text.strip().lower()
    if len(t) != want_len:
        return None
    try:
        raw = bytes.fromhex(t)
    except ValueError:
        return None
    if len(raw) != want_len // 2:
        return None
    return raw


def verify_row(pubkey_bytes, box_id, row, sig_hex):
    """True iff sig_hex is a valid signature over the row's envelope.

    Never raises: any malformed input is simply not a valid
    attestation.
    """
    if (not isinstance(pubkey_bytes, (bytes, bytearray))
            or len(pubkey_bytes) != 32):
        return False
    sig = _hex_bytes(sig_hex, _SIG_HEX_LEN)
    if sig is None:
        return False
    try:
        return bool(ed25519.verify(bytes(pubkey_bytes),
                                   envelope_bytes(box_id, row), sig))
    except Exception:
        return False


def verify_attestation(keyring, box_id, row):
    """Check a row's attestation claim against the pinned box keys.

    `keyring` maps box_id -> 32-byte pubkey (or None for the legacy
    estate with no keys pinned). Returns (attested: bool, note: str |
    None). Never raises. Semantics:

      - no `attestation` member: legacy row — (False, None), silent.
      - malformed member: (False, loud note).
      - no pinned key for box_id: (False, note — the log-only path).
      - bad signature: (False, LOUDEST note — the forgery signal).
      - valid signature: (True, None), plus a loud note if the row's
        claimed fingerprint disagrees with the pinned key (metadata
        wrongness, not inauthenticity — the signature is authoritative).
    """
    if not isinstance(row, dict):
        return False, ("attestation checked on a non-object row for box "
                        "%r; event logged unattested" % (box_id,))
    att = row.get(ATTESTATION_MEMBER)
    if att is None:
        return False, None
    if not isinstance(att, dict):
        return False, ("attestation member is not an object for box %r; "
                        "event logged unattested" % (box_id,))
    sig_hex = att.get("sig")
    if not isinstance(sig_hex, str):
        return False, ("attestation member has no sig string for box %r; "
                        "event logged unattested" % (box_id,))
    pubkey = keyring.get(box_id) if keyring else None
    if pubkey is None:
        return False, ("no box key pinned for %r; event carries an "
                        "attestation claim but cannot be verified — "
                        "logged unattested (legacy/log-only path)"
                        % (box_id,))
    if not verify_row(pubkey, box_id, row, sig_hex):
        return False, ("ATTESTATION SIGNATURE INVALID for box %r — "
                        "possible event forgery; event logged, never "
                        "gate-consumed" % (box_id,))
    note = None
    claimed_fp = att.get("key_fingerprint")
    if isinstance(claimed_fp, str):
        pinned_fp = _fingerprint_of_pubkey(pubkey)
        if claimed_fp != pinned_fp:
            note = ("row's claimed key fingerprint does not match the "
                    "pinned key for box %r; signature is valid against "
                    "the pinned key, event attested" % (box_id,))
    return True, note


# --- Box-key registry (write-once, the register.py discipline) ---------------

def _box_keys_path(store_dir):
    return os.path.join(store_dir, BOX_KEYS_NAME)


def load_box_keys(store_dir):
    """Load the pinned box keys: (dict box_id -> 32-byte pubkey, error).

    A missing registry is not an error — it is the legacy estate with
    no keys pinned (every event unattested). A corrupt registry is an
    integrity failure: fail closed, verify nothing.
    """
    path = _box_keys_path(store_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}, None
    except (OSError, ValueError) as exc:
        return None, ("box-key registry %s unreadable/corrupt: %s; "
                      "refusing to verify (integrity failure)"
                      % (path, exc))
    if not isinstance(data, dict):
        return None, ("box-key registry %s is not an object (integrity "
                      "failure)" % (path,))
    keys = {}
    for box_id, rec in data.items():
        if not isinstance(box_id, str) or not box_id:
            return None, ("box-key registry %s: non-string box_id "
                          "(integrity failure)" % (path,))
        if not isinstance(rec, dict):
            return None, ("box-key registry %s: record for %r is not an "
                          "object (integrity failure)" % (path, box_id))
        pub = _hex_bytes(rec.get("pubkey"), _PUBKEY_HEX_LEN)
        if pub is None:
            return None, ("box-key registry %s: record for %r has no "
                          "64-hex pubkey (integrity failure)"
                          % (path, box_id))
        keys[box_id] = pub
    return keys, None


def pin_box_key(store_dir, box_id, pubkey_hex):
    """Pin a box's ed25519 pubkey. Returns (fingerprint, error).

    Write-once: re-pinning the *same* key is idempotent (provisioning
    converges); re-pinning a *different* key fails closed — a silent
    key swap would fork the attribution chain (rotation is a separate
    design, like the operator key's #1407). The write is temp-file +
    os.replace + fsync under the store's journal lock so two racing
    pins serialize (the register.py operator-pin precedent).
    """
    if not isinstance(box_id, str) or not box_id:
        return None, "box_id must be a non-empty string"
    pub = _hex_bytes(pubkey_hex, _PUBKEY_HEX_LEN)
    if pub is None:
        return None, ("pubkey must be 64 hex chars (32 bytes; case and "
                       "surrounding whitespace are tolerated and "
                       "normalized)")
    if not os.path.isdir(store_dir):
        return None, "store dir %s does not exist" % (store_dir,)
    from events import journal_lock  # lazy: events.py imports this module
    path = _box_keys_path(store_dir)
    fp = _fingerprint_of_pubkey(pub)
    try:
        with journal_lock(store_dir):
            keys, err = load_box_keys(store_dir)
            if err is not None:
                return None, err
            existing = keys.get(box_id)
            if existing is not None:
                if existing == pub:
                    return fp, None  # idempotent re-pin
                return None, ("box %r already has a different key pinned; "
                              "refusing silent key swap (rotation is a "
                              "separate design)" % (box_id,))
            keys[box_id] = pub
            data = {bid: {"pubkey": k.hex(),
                          "pinned_at": _now_iso(),
                          "fingerprint": _fingerprint_of_pubkey(k)}
                    for bid, k in sorted(keys.items())}
            tmp_fd, tmp_path = tempfile.mkstemp(dir=store_dir,
                                                prefix=".box-keys.",
                                                suffix=".tmp")
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(data, sort_keys=True, indent=2)
                             + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_path, path)
                parent = os.open(store_dir, os.O_RDONLY)
                try:
                    os.fsync(parent)
                finally:
                    os.close(parent)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
    except Exception as exc:
        return None, "pin failed: %s" % (exc,)
    return fp, None


def read_box_key(store_dir, box_id):
    """Read one box's pinned pubkey: (32-byte pubkey | None, error).

    None with no error = no key pinned (legacy path) or unknown box.
    """
    keys, err = load_box_keys(store_dir)
    if err is not None:
        return None, err
    return keys.get(box_id), None


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- The T2 rule -------------------------------------------------------------

def gate_consumable_events(events):
    """Return the events a consuming gate may read.

    This is trust-model S3 T2 as code: "unattested events may be
    logged, never gate-consumed." Every consuming gate filters through
    this function — the first gate builder (G15 controller) inherits
    the attestation requirement instead of rediscovering it. Until a
    gate exists, the rule is pinned here and at the ingest.

    Scope: box-origin G17 events. Controller-origin records (e.g. the
    controller's own freeze-hold events) are the controller's
    authority, not box self-report — a future gate must not apply
    this filter to the whole journal blindly, or it will silently
    drop the controller's own voice.
    """
    return [e for e in events
            if isinstance(e, dict) and e.get("attested") is True]
