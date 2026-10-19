#!/usr/bin/env python3
"""Hermetic suite for fleet/attest.py (#1516 S3: box-event attestation).

Run with `python3 -m pytest fleet/test_attest.py` from the repo root.
Direct imports (the test_events.py precedent): fleet/ is not a package,
so the module is imported as a sibling after a sys.path insert.
"""

import json
import os
import sys
import tempfile

FLEET = os.path.dirname(os.path.abspath(__file__))
if FLEET not in sys.path:
    sys.path.insert(0, FLEET)
import attest  # noqa: E402
import events  # noqa: E402  (ingest half)
import inventory  # noqa: E402  (CLI wiring)

# Deterministic test seeds — never real keys.
SEED_A = bytes(range(32))
SEED_B = bytes([255 - b for b in range(32)])
BOX = "tower"


def _pub(seed):
    return attest.ed25519.publickey_from_seed(seed)


def _row(**fields):
    row = {"ts": "2026-10-19T07:00:00Z", "event": "deploy",
           "result": "rolled-back", "from": "aaa111", "to": "bbb222"}
    row.update(fields)
    return row


def _keyring(*seeds):
    return {BOX: _pub(seeds[0] if seeds else SEED_A)}


# --- Envelope ---------------------------------------------------------------

def test_envelope_is_deterministic():
    row = _row()
    assert attest.envelope_bytes(BOX, row) == attest.envelope_bytes(BOX, row)


def test_envelope_binds_box_id():
    # The same raw row signs differently per box: a signature lifted
    # from box A must not verify for box B.
    row = _row()
    assert (attest.envelope_bytes("box-a", row)
            != attest.envelope_bytes("box-b", row))
    att = attest.sign_row(SEED_A, "box-a", row)
    assert attest.verify_row(_pub(SEED_A), "box-a", row, att["sig"])
    assert not attest.verify_row(_pub(SEED_A), "box-b", row, att["sig"])


def test_envelope_excludes_attestation_member():
    row = _row()
    att = attest.sign_row(SEED_A, BOX, row)
    with_att = dict(row)
    with_att["attestation"] = att
    assert (attest.envelope_bytes(BOX, with_att)
            == attest.envelope_bytes(BOX, row))


# --- Sign / verify ----------------------------------------------------------

def test_sign_verify_roundtrip():
    row = _row()
    att = attest.sign_row(SEED_A, BOX, row)
    assert att["key_fingerprint"].startswith("SHA256:")
    assert len(att["sig"]) == 128
    int(att["sig"], 16)  # valid hex
    assert attest.verify_row(_pub(SEED_A), BOX, row, att["sig"])


def test_verify_row_rejects_tampered_row():
    row = _row()
    att = attest.sign_row(SEED_A, BOX, row)
    tampered = dict(row, result="ok")  # G15 S6 attack: forge a success
    assert not attest.verify_row(_pub(SEED_A), BOX, tampered, att["sig"])


def test_verify_row_rejects_wrong_key():
    row = _row()
    att = attest.sign_row(SEED_A, BOX, row)
    assert not attest.verify_row(_pub(SEED_B), BOX, row, att["sig"])


def test_verify_row_never_raises():
    row = _row()
    for bad_sig in (None, 123, "", "zz", "00" * 64, "ab" * 63):
        assert attest.verify_row(_pub(SEED_A), BOX, row, bad_sig) is False
    assert attest.verify_row(None, BOX, row, "ab" * 64) is False
    assert attest.verify_row(b"short", BOX, row, "ab" * 64) is False


def test_sign_row_rejects_bad_inputs():
    for bad_seed in (None, b"short", "x" * 32, bytes(33)):
        try:
            attest.sign_row(bad_seed, BOX, _row())
        except ValueError:
            pass
        else:
            raise AssertionError("seed %r accepted" % (bad_seed,))
    for bad_box in (None, "", 123):
        try:
            attest.sign_row(SEED_A, bad_box, _row())
        except ValueError:
            pass
        else:
            raise AssertionError("box_id %r accepted" % (bad_box,))
    already = _row()
    already["attestation"] = {"sig": "x"}
    try:
        attest.sign_row(SEED_A, BOX, already)
    except ValueError:
        pass
    else:
        raise AssertionError("double-sign accepted")


def test_format_attested_row_line_roundtrip():
    # The exact emitted line must parse and verify: the canonical form
    # is byte-stable through the collector's loads->dumps — probed
    # across unicode, floats, nesting, and big ints, not just ASCII.
    variants = [
        _row(),
        _row(note="déploié ✓ — naïve café"),
        _row(load_avg=1.5, uptime_s=1e6),
        _row(detail={"nested": [1, "two", None, True],
                     "big": 10 ** 40}),
        _row(empty_obj={}, empty_list=[]),
    ]
    for row in variants:
        line = attest.format_attested_row(SEED_A, BOX, row)
        assert line.endswith("\n") and "\n" not in line.strip()
        parsed = json.loads(line)
        att = parsed["attestation"]
        assert attest.verify_row(_pub(SEED_A), BOX, parsed, att["sig"])
        # Re-serializing the parsed row reproduces the signed envelope.
        assert (attest.envelope_bytes(BOX, parsed)
                == attest.envelope_bytes(BOX, row))


# --- Registry ---------------------------------------------------------------

def _store():
    tmp = tempfile.TemporaryDirectory()
    store = os.path.join(tmp.name, "store")
    os.makedirs(store)
    return tmp, store


def test_pin_box_key_write_once():
    tmp, store = _store()
    try:
        fp, err = attest.pin_box_key(store, BOX, _pub(SEED_A).hex())
        assert err is None, err
        assert fp.startswith("SHA256:")
        # Idempotent re-pin of the same key.
        fp2, err = attest.pin_box_key(store, BOX, _pub(SEED_A).hex())
        assert err is None, err
        assert fp2 == fp
        # A different key for the same box fails closed.
        fp3, err = attest.pin_box_key(store, BOX, _pub(SEED_B).hex())
        assert fp3 is None
        assert err is not None and "different key" in err
        # The failed pin did not clobber the original.
        pub, err = attest.read_box_key(store, BOX)
        assert err is None and pub == _pub(SEED_A)
        # Unknown box: no key, no error (legacy path).
        pub, err = attest.read_box_key(store, "nope")
        assert err is None and pub is None
    finally:
        tmp.cleanup()


def test_pin_box_key_rejects_bad_inputs():
    tmp, store = _store()
    try:
        for bad_hex in (None, "", "zz", "ab" * 31, "ab" * 33):
            fp, err = attest.pin_box_key(store, BOX, bad_hex)
            assert fp is None and err is not None, bad_hex
        # Case/whitespace tolerant (the fingerprint-normalization
        # precedent): accepted, pinned in canonical lowercase form.
        fp, err = attest.pin_box_key(store, "casebox", "AB" * 32 + " ")
        assert err is None, err
        pub, err = attest.read_box_key(store, "casebox")
        assert err is None and pub == bytes.fromhex("ab" * 32)
        for bad_box in (None, "", 123):
            fp, err = attest.pin_box_key(store, bad_box,
                                         _pub(SEED_A).hex())
            assert fp is None and err is not None, bad_box
        fp, err = attest.pin_box_key(os.path.join(store, "missing"),
                                     BOX, _pub(SEED_A).hex())
        assert fp is None and err is not None
    finally:
        tmp.cleanup()


def test_registry_missing_is_legacy_not_error():
    tmp, store = _store()
    try:
        keys, err = attest.load_box_keys(store)
        assert err is None and keys == {}
    finally:
        tmp.cleanup()


def test_registry_corrupt_fails_closed():
    tmp, store = _store()
    try:
        path = os.path.join(store, attest.BOX_KEYS_NAME)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        keys, err = attest.load_box_keys(store)
        assert keys is None and err is not None
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"x": {"pubkey": "zz"}}))
        keys, err = attest.load_box_keys(store)
        assert keys is None and err is not None
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(["not", "an", "object"]))
        keys, err = attest.load_box_keys(store)
        assert keys is None and err is not None
    finally:
        tmp.cleanup()


# --- verify_attestation -----------------------------------------------------

def _signed_row(seed=SEED_A, box=BOX, **fields):
    row = _row(**fields)
    row["attestation"] = attest.sign_row(seed, box, row)
    return row


def test_verify_attestation_non_dict_row_never_raises():
    # The "never raises" contract holds even for non-dict rows (the
    # ingest filters these first; the guard is for future callers).
    attested, note = attest.verify_attestation(_keyring(), BOX,
                                               "not-a-dict")
    assert attested is False
    assert note is not None


def test_verify_attestation_legacy_row_is_silent():
    attested, note = attest.verify_attestation(_keyring(), BOX, _row())
    assert attested is False
    assert note is None  # legacy rows stay quiet


def test_verify_attestation_malformed_claim():
    row = _row()
    row["attestation"] = "not-a-dict"
    attested, note = attest.verify_attestation(_keyring(), BOX, row)
    assert attested is False and note is not None
    row["attestation"] = {"key_fingerprint": "SHA256:x"}  # no sig
    attested, note = attest.verify_attestation(_keyring(), BOX, row)
    assert attested is False and note is not None


def test_verify_attestation_no_key_pinned():
    row = _signed_row()
    attested, note = attest.verify_attestation({}, BOX, row)
    assert attested is False
    assert note is not None and "no box key pinned" in note
    attested, note = attest.verify_attestation(None, BOX, row)
    assert attested is False and note is not None


def test_verify_attestation_bad_signature_is_loud():
    row = _signed_row()
    row["attestation"] = dict(row["attestation"])
    row["attestation"]["sig"] = "00" * 64  # well-formed, wrong
    attested, note = attest.verify_attestation(_keyring(), BOX, row)
    assert attested is False
    assert note is not None and "ATTESTATION SIGNATURE INVALID" in note


def test_verify_attestation_valid():
    row = _signed_row()
    attested, note = attest.verify_attestation(_keyring(), BOX, row)
    assert attested is True
    assert note is None


def test_verify_attestation_fingerprint_mismatch_noted():
    # The signature is authoritative; a wrong fingerprint label is
    # metadata wrongness — loud note, still attested.
    row = _signed_row()
    row["attestation"] = dict(row["attestation"])
    row["attestation"]["key_fingerprint"] = "SHA256:AAAA"
    attested, note = attest.verify_attestation(_keyring(), BOX, row)
    assert attested is True
    assert note is not None and "fingerprint" in note


# --- Ingest half ------------------------------------------------------------

def test_ingest_marks_attested_events():
    signed = _signed_row()
    legacy = _row(result="deploy-fail")
    forged = _signed_row(result="deploy-fail")
    forged["attestation"] = dict(forged["attestation"])
    forged["attestation"]["sig"] = "ff" * 64
    evs, _, notes = events.canonicalize_audit_rows(
        [signed, legacy, forged], BOX, "2026-10-19T07:05:00Z",
        keyring=_keyring())
    assert len(evs) == 3
    assert evs[0]["attested"] is True
    assert evs[0]["outcome"] == "rolled-back"
    assert evs[1]["attested"] is False
    assert evs[2]["attested"] is False
    assert any("ATTESTATION SIGNATURE INVALID" in n for n in notes)


def test_ingest_fanout_shares_row_verdict():
    # The deploy-ok fan-out inherits one attestation verdict per row.
    row = _row(event="deploy", result="ok", **{"components": "proxy confirm",
                                               "from": "a", "to": "b"})
    row["attestation"] = attest.sign_row(SEED_A, BOX, row)
    evs, _, _ = events.canonicalize_audit_rows(
        [row], BOX, "2026-10-19T07:05:00Z", keyring=_keyring())
    assert len(evs) == 2
    assert all(e["attested"] is True for e in evs)
    assert sorted(e["subcomponent"] for e in evs) == ["confirm", "proxy"]


def test_ingest_without_keyring_stays_legacy():
    evs, _, notes = events.canonicalize_audit_rows(
        [_signed_row()], BOX, "2026-10-19T07:05:00Z")
    assert len(evs) == 1
    assert evs[0]["attested"] is False
    assert any("no box key pinned" in n for n in notes)


def test_ingest_verifies_attestation_before_shape_gate():
    # A forged signature on a row the shape gate drops is STILL the
    # forgery signal: verification runs before the shape gates, so the
    # loud note lands even though no event is journaled.
    row = _row(event="bogus", result="nonsense")
    row["attestation"] = attest.sign_row(SEED_A, BOX, row)
    row["attestation"]["sig"] = "ff" * 64  # well-formed, wrong
    evs, noops, notes = events.canonicalize_audit_rows(
        [row], BOX, "2026-10-19T07:05:00Z", keyring=_keyring())
    assert evs == [] and noops == 0
    assert any("ATTESTATION SIGNATURE INVALID" in n for n in notes)


def test_ingest_local_only_row_with_forged_sig_still_noted():
    # Local-only rows (check/noop) stay local — but a forged
    # attestation claim on one is still journaled loudly.
    row = {"ts": "2026-10-19T07:00:00Z", "event": "check",
           "result": "noop"}
    row["attestation"] = attest.sign_row(SEED_A, BOX, row)
    row["attestation"]["sig"] = "ff" * 64
    evs, noops, notes = events.canonicalize_audit_rows(
        [row], BOX, "2026-10-19T07:05:00Z", keyring=_keyring())
    assert evs == [] and noops == 1  # still local-only
    assert any("ATTESTATION SIGNATURE INVALID" in n for n in notes)


def test_ingest_valid_sig_on_unknown_shape_is_quiet_but_eventless():
    # The mirror case: a VALID signature on a dropped shape verifies
    # silently — no forgery note, still no event.
    row = _row(event="bogus", result="nonsense")
    row["attestation"] = attest.sign_row(SEED_A, BOX, row)
    evs, noops, notes = events.canonicalize_audit_rows(
        [row], BOX, "2026-10-19T07:05:00Z", keyring=_keyring())
    assert evs == [] and noops == 0
    assert not any("ATTESTATION" in n for n in notes)


def test_collect_box_events_passes_keyring(tmp_path):
    box_dir = tmp_path / "tower"
    box_dir.mkdir()
    line = attest.format_attested_row(SEED_A, BOX, _row())
    (box_dir / "audit-tail.jsonl").write_text(line, encoding="utf-8")
    evs, _, notes = events.collect_box_events(
        str(box_dir), BOX, "2026-10-19T07:05:00Z", keyring=_keyring())
    assert len(evs) == 1
    assert evs[0]["attested"] is True
    assert notes == []


# --- CLI (fleet box-key pin/show) --------------------------------------------

def _cli_store(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    return str(store)


def test_cli_box_key_pin_show_roundtrip(tmp_path, capsys):
    store = _cli_store(tmp_path)
    pub_hex = _pub(SEED_A).hex()
    assert inventory.main(["box-key", "pin", "--store", store,
                           "--box-id", BOX, "--pubkey", pub_hex]) == 0
    out = capsys.readouterr().out
    assert "pinned box key" in out and BOX in out
    assert inventory.main(["box-key", "show", "--store", store,
                           "--box-id", BOX]) == 0
    out = capsys.readouterr().out
    assert out.startswith(BOX + ": SHA256:")
    # Idempotent re-pin converges.
    assert inventory.main(["box-key", "pin", "--store", store,
                           "--box-id", BOX, "--pubkey", pub_hex]) == 0


def test_cli_box_key_pin_different_key_fails_closed(tmp_path):
    store = _cli_store(tmp_path)
    assert inventory.main(["box-key", "pin", "--store", store,
                           "--box-id", BOX,
                           "--pubkey", _pub(SEED_A).hex()]) == 0
    assert inventory.main(["box-key", "pin", "--store", store,
                           "--box-id", BOX,
                           "--pubkey", _pub(SEED_B).hex()]) == 2


def test_cli_box_key_missing_args(tmp_path):
    store = _cli_store(tmp_path)
    # Missing --box-id / --pubkey: clean exit 2, not a traceback.
    assert inventory.main(["box-key", "pin", "--store", store,
                           "--pubkey", _pub(SEED_A).hex()]) == 2
    assert inventory.main(["box-key", "pin", "--store", store,
                           "--box-id", BOX]) == 2
    # Missing --store: argparse itself exits 2.
    import pytest
    with pytest.raises(SystemExit) as exc:
        inventory.main(["box-key", "pin", "--box-id", BOX,
                        "--pubkey", _pub(SEED_A).hex()])
    assert exc.value.code == 2


def test_cli_box_key_show_corrupt_registry(tmp_path):
    store = _cli_store(tmp_path)
    with open(os.path.join(store, attest.BOX_KEYS_NAME), "w",
              encoding="utf-8") as fh:
        fh.write("{corrupt")
    assert inventory.main(["box-key", "show", "--store", store,
                           "--box-id", BOX]) == 2
    # show on an unknown box: exit 0, "no box key pinned".
    store2 = tmp_path / "store2"
    store2.mkdir()
    assert inventory.main(["box-key", "show", "--store", str(store2),
                           "--box-id", BOX]) == 0


def test_collect_fails_closed_on_corrupt_registry(tmp_path):
    # The shipped fail-closed: a corrupt box-key registry fails the
    # whole collect (exit 2) rather than silently journaling every
    # event unattested — and no event lines land.
    estate = tmp_path / "estate" / BOX
    estate.mkdir(parents=True)
    (estate / "audit-tail.jsonl").write_text(
        json.dumps(_row()) + "\n", encoding="utf-8")
    store = tmp_path / "store"
    store.mkdir()
    with open(store / attest.BOX_KEYS_NAME, "w",
              encoding="utf-8") as fh:
        fh.write("{corrupt")
    code = inventory.main(["collect", "--estate", str(tmp_path / "estate"),
                           "--store", str(store)])
    assert code == 2
    events_path = store / "events.jsonl"
    assert (not events_path.exists()
            or events_path.read_text(encoding="utf-8") == "")


# --- T2 rule ----------------------------------------------------------------

def test_gate_consumable_events_filters():
    evs = [{"attested": True, "event_id": "a"},
           {"attested": False, "event_id": "b"},
           {"event_id": "c"},          # missing key: not consumable
           {"attested": "yes"},        # truthy-but-not-True: not consumable
           "not-a-dict"]
    got = attest.gate_consumable_events(evs)
    assert [e["event_id"] for e in got] == ["a"]
