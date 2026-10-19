#!/usr/bin/env python3
"""Pin fleet/gate_query.py's unit contracts (G18 box-side self-evaluation).

gate_query.py is the tick-time enforcement point of the release-gating
channel: it verifies the estate's gate.json and answers this box's own
release state (state=frozen|live, per-component permitted bits). The
design headline is fail-closed: a missing, malformed, bad-MAC, or
expired document is no-signal -> frozen — the box never releases itself.

fleet/test_gate.py exercises this module only through subprocess E2E
(full publish -> state/permitted round-trips). Everything below pins
the module's own edge behaviors as unit contracts, split by function:

- resolve_box_id: flag > env > file precedence; empty file -> NoSignal.
- resolve_keys: rotation-window parsing, group/other-readable refusal,
  32-byte floor, trailing-CR/LF stripping, env fallback.
- load_gate: structural checks before any MAC work.
- verify_gate: MAC + TTL contract (mismatch, unknown key_id, future skew
  beyond 60s, expiry, rotation-window key selection).
- box_wave / component_permitted: assignment pins vs hash_mod_4 default,
  canary pin-only semantics, live ceilings, never-permitted states.
- answer: the no-signal -> frozen shape and the live/frozen answer shape.

The module is imported (importlib, no sys.path surgery — fleet/ has no
__init__.py by repo convention) and performs no import-time side effects.
All state lives under tmp dirs; no test prints key material.
"""

import hashlib
import hmac
import importlib.util
import json
import os
import stat
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

FLEET = os.path.dirname(os.path.abspath(__file__))
GATE_QUERY = os.path.join(FLEET, "gate_query.py")


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "gate_query_under_test", GATE_QUERY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate_query = _load_module()

KEY_A = b"a" * 32
KEY_B = b"b" * 32


@contextmanager
def _env(**overrides):
    """Set env vars for the block; restore (or delete) afterwards."""
    saved = {k: os.environ.get(k) for k in overrides}
    for k, v in overrides.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class _Args:
    def __init__(self, box_id=None, box_id_file=None, keys=None):
        self.box_id = box_id
        self.box_id_file = box_id_file
        self.keys = keys


def _write(path, data, mode=0o600):
    with open(path, "wb") as fh:
        fh.write(data)
    os.chmod(path, mode)


def _sign(body, key):
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


def _make_gate_doc(key_id="k1", key=KEY_A, freeze=False, waves=None,
                   issued_at=None, ttl_seconds=3600, extra=None):
    body = {
        "schema_version": gate_query.SCHEMA_VERSION,
        "issued_at": issued_at or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "ttl_seconds": ttl_seconds,
        "key_id": key_id,
        "freeze": freeze,
        "releases": {"repo": {"max_permitted_commit": "deadbeef"}},
        "waves": waves or {},
    }
    if extra:
        body.update(extra)
    doc = dict(body)
    doc["hmac"] = _sign(body, key)
    return doc


def _write_gate(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


# ---------------------------------------------------------------------------
# resolve_box_id


def test_box_id_flag_beats_env_and_file(tmp_path):
    id_file = tmp_path / "boxid"
    id_file.write_text("file-box\n")
    with _env(SPARKVM_BOX_ID="env-box",
              SPARKVM_BOX_ID_FILE=str(id_file)):
        assert gate_query.resolve_box_id(_Args(box_id="flag-box")) == "flag-box"


def test_box_id_env_beats_file(tmp_path):
    id_file = tmp_path / "boxid"
    id_file.write_text("file-box\n")
    with _env(SPARKVM_BOX_ID="env-box", SPARKVM_BOX_ID_FILE=str(id_file)):
        assert gate_query.resolve_box_id(_Args()) == "env-box"


def test_box_id_flag_file_path(tmp_path):
    id_file = tmp_path / "boxid"
    id_file.write_text("  file-box \n")
    with _env(SPARKVM_BOX_ID=None, SPARKVM_BOX_ID_FILE=None):
        assert gate_query.resolve_box_id(
            _Args(box_id_file=str(id_file))) == "file-box"


def test_box_id_env_file_path(tmp_path):
    id_file = tmp_path / "boxid"
    id_file.write_text("envfile-box")
    with _env(SPARKVM_BOX_ID=None, SPARKVM_BOX_ID_FILE=str(id_file)):
        assert gate_query.resolve_box_id(_Args()) == "envfile-box"


def test_box_id_whitespace_only_file_is_no_signal(tmp_path):
    id_file = tmp_path / "boxid"
    id_file.write_text("  \n \n")
    with _env(SPARKVM_BOX_ID=None, SPARKVM_BOX_ID_FILE=None):
        try:
            gate_query.resolve_box_id(_Args(box_id_file=str(id_file)))
        except gate_query.NoSignal as exc:
            assert "empty" in str(exc)
        else:
            raise AssertionError("expected NoSignal")


def test_box_id_nothing_configured_is_no_signal():
    with _env(SPARKVM_BOX_ID=None, SPARKVM_BOX_ID_FILE=None):
        try:
            gate_query.resolve_box_id(_Args())
        except gate_query.NoSignal as exc:
            assert "no box identity" in str(exc)
        else:
            raise AssertionError("expected NoSignal")


def test_box_id_unreadable_file_is_no_signal(tmp_path):
    with _env(SPARKVM_BOX_ID=None, SPARKVM_BOX_ID_FILE=None):
        try:
            gate_query.resolve_box_id(
                _Args(box_id_file=str(tmp_path / "missing")))
        except gate_query.NoSignal as exc:
            assert "cannot read" in str(exc)
        else:
            raise AssertionError("expected NoSignal")


def test_box_id_non_utf8_file_is_no_signal(tmp_path):
    # The #1543 Engineering-B1 decode-hole class: a non-UTF-8 identity
    # file must be no-signal, not a UnicodeDecodeError traceback.
    id_file = tmp_path / "boxid"
    id_file.write_bytes(b"\xff\xfebox-1")
    with _env(SPARKVM_BOX_ID=None, SPARKVM_BOX_ID_FILE=None):
        try:
            gate_query.resolve_box_id(_Args(box_id_file=str(id_file)))
        except gate_query.NoSignal as exc:
            assert "cannot read" in str(exc)
        else:
            raise AssertionError("expected NoSignal")


# ---------------------------------------------------------------------------
# resolve_keys


def test_keys_rotation_window_parses_two_keys(tmp_path):
    ka = tmp_path / "k1"
    kb = tmp_path / "k2"
    _write(str(ka), KEY_A)
    _write(str(kb), KEY_B)
    with _env(SPARKVM_GATE_KEYS=None):
        keys = gate_query.resolve_keys(_Args(keys=f"k1={ka},k2={kb}"))
    assert keys == {"k1": KEY_A, "k2": KEY_B}


def test_keys_group_readable_refused(tmp_path):
    kf = tmp_path / "k1"
    _write(str(kf), KEY_A, mode=0o640)
    with _env(SPARKVM_GATE_KEYS=None):
        try:
            gate_query.resolve_keys(_Args(keys=f"k1={kf}"))
        except gate_query.NoSignal as exc:
            assert "0600" in str(exc)
        else:
            raise AssertionError("expected NoSignal")


def test_keys_other_readable_refused(tmp_path):
    kf = tmp_path / "k1"
    _write(str(kf), KEY_A, mode=0o604)
    with _env(SPARKVM_GATE_KEYS=None):
        try:
            gate_query.resolve_keys(_Args(keys=f"k1={kf}"))
        except gate_query.NoSignal as exc:
            assert "0600" in str(exc)
        else:
            raise AssertionError("expected NoSignal")


def test_keys_short_key_refused(tmp_path):
    kf = tmp_path / "k1"
    _write(str(kf), b"too-short")
    with _env(SPARKVM_GATE_KEYS=None):
        try:
            gate_query.resolve_keys(_Args(keys=f"k1={kf}"))
        except gate_query.NoSignal as exc:
            assert "32 bytes" in str(exc)
        else:
            raise AssertionError("expected NoSignal")


def test_keys_exactly_32_bytes_accepted(tmp_path):
    kf = tmp_path / "k1"
    _write(str(kf), b"x" * 32)
    with _env(SPARKVM_GATE_KEYS=None):
        assert gate_query.resolve_keys(_Args(keys=f"k1={kf}")) == {
            "k1": b"x" * 32}


def test_keys_trailing_crlf_stripped(tmp_path):
    # rstrip(b"\r\n") strips ALL trailing CR/LF bytes, not just one —
    # the tolerance is "echo-added line endings don't change the MAC".
    kf = tmp_path / "k1"
    _write(str(kf), KEY_A + b"\r\n\r\n\n")
    with _env(SPARKVM_GATE_KEYS=None):
        assert gate_query.resolve_keys(_Args(keys=f"k1={kf}")) == {"k1": KEY_A}


def test_keys_interior_crlf_preserved(tmp_path):
    kf = tmp_path / "k1"
    body = b"c" * 16 + b"\r\n" + b"d" * 16
    _write(str(kf), body + b"\n")
    with _env(SPARKVM_GATE_KEYS=None):
        assert gate_query.resolve_keys(_Args(keys=f"k1={kf}")) == {"k1": body}


def test_keys_malformed_entry_refused(tmp_path):
    kf = tmp_path / "k1"
    _write(str(kf), KEY_A)
    with _env(SPARKVM_GATE_KEYS=None):
        try:
            gate_query.resolve_keys(_Args(keys=f"k1-no-equals-sign"))
        except gate_query.NoSignal as exc:
            assert "key_id=/path" in str(exc)
        else:
            raise AssertionError("expected NoSignal")


def test_keys_env_fallback(tmp_path):
    kf = tmp_path / "k1"
    _write(str(kf), KEY_A)
    with _env(SPARKVM_GATE_KEYS=f"k1={kf}"):
        assert gate_query.resolve_keys(_Args()) == {"k1": KEY_A}


def test_keys_missing_spec_is_no_signal():
    with _env(SPARKVM_GATE_KEYS=None):
        try:
            gate_query.resolve_keys(_Args())
        except gate_query.NoSignal as exc:
            assert "--keys" in str(exc)
        else:
            raise AssertionError("expected NoSignal")


# ---------------------------------------------------------------------------
# load_gate


def test_load_gate_valid_shape(tmp_path):
    doc = _make_gate_doc()
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    loaded = gate_query.load_gate(path)
    assert loaded["doc"] == doc
    assert "hmac" not in loaded["body"]
    assert loaded["mac"] == doc["hmac"]


def test_load_gate_non_dict_is_no_signal(tmp_path):
    path = str(tmp_path / "gate.json")
    with open(path, "w") as fh:
        fh.write("[1, 2]")
    try:
        gate_query.load_gate(path)
    except gate_query.NoSignal as exc:
        assert "not a JSON object" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_load_gate_bad_schema_version_is_no_signal(tmp_path):
    doc = _make_gate_doc(extra={"schema_version": 999})
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    try:
        gate_query.load_gate(path)
    except gate_query.NoSignal as exc:
        assert "schema_version" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_load_gate_missing_hmac_is_no_signal(tmp_path):
    doc = _make_gate_doc()
    del doc["hmac"]
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    try:
        gate_query.load_gate(path)
    except gate_query.NoSignal as exc:
        assert "hmac" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_load_gate_garbage_bytes_is_no_signal(tmp_path):
    path = str(tmp_path / "gate.json")
    with open(path, "wb") as fh:
        fh.write(b"\xff\xfe{{{")
    try:
        gate_query.load_gate(path)
    except gate_query.NoSignal as exc:
        assert "unreadable" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_load_gate_non_ascii_hmac_is_no_signal(tmp_path):
    # compare_digest raises TypeError on non-ASCII str; a non-ASCII hmac
    # must be no-signal, not a traceback (QA B1).
    doc = _make_gate_doc()
    doc["hmac"] = "é" * 64
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    try:
        gate_query.load_gate(path)
    except gate_query.NoSignal as exc:
        assert "ASCII" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


# ---------------------------------------------------------------------------
# verify_gate


def test_verify_gate_valid_returns_key_id(tmp_path):
    doc = _make_gate_doc()
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    gate = gate_query.load_gate(path)
    assert gate_query.verify_gate(gate, {"k1": KEY_A}) == "k1"


def test_verify_gate_rotation_window_selects_next_key(tmp_path):
    doc = _make_gate_doc(key_id="k2", key=KEY_B)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    gate = gate_query.load_gate(path)
    assert gate_query.verify_gate(gate, {"k1": KEY_A, "k2": KEY_B}) == "k2"


def test_verify_gate_unknown_key_id_is_no_signal(tmp_path):
    doc = _make_gate_doc(key_id="k9", key=KEY_A)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    gate = gate_query.load_gate(path)
    try:
        gate_query.verify_gate(gate, {"k1": KEY_A})
    except gate_query.NoSignal as exc:
        assert "no provisioned key" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_verify_gate_mac_mismatch_is_no_signal(tmp_path):
    # Signed with a different key than the one provisioned under key_id.
    doc = _make_gate_doc(key_id="k1", key=KEY_B)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    gate = gate_query.load_gate(path)
    try:
        gate_query.verify_gate(gate, {"k1": KEY_A})
    except gate_query.NoSignal as exc:
        assert "MAC mismatch" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_verify_gate_tampered_body_is_no_signal(tmp_path):
    doc = _make_gate_doc(freeze=False)
    doc["freeze"] = True  # tamper after signing; hmac stays stale
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    gate = gate_query.load_gate(path)
    try:
        gate_query.verify_gate(gate, {"k1": KEY_A})
    except gate_query.NoSignal as exc:
        assert "MAC mismatch" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_verify_gate_future_within_skew_accepts(tmp_path):
    # The 60s clock-skew tolerance is a real contract, pinned on the
    # accept side too (a +30s-future doc verifies OK).
    issued = (datetime.now(timezone.utc) + timedelta(seconds=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    doc = _make_gate_doc(issued_at=issued)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    gate = gate_query.load_gate(path)
    assert gate_query.verify_gate(gate, {"k1": KEY_A}) == "k1"


def test_verify_gate_future_issued_beyond_skew_is_no_signal(tmp_path):
    issued = (datetime.now(timezone.utc) + timedelta(seconds=120)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    doc = _make_gate_doc(issued_at=issued)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    gate = gate_query.load_gate(path)
    try:
        gate_query.verify_gate(gate, {"k1": KEY_A})
    except gate_query.NoSignal as exc:
        assert "future" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_verify_gate_expired_is_no_signal(tmp_path):
    issued = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    doc = _make_gate_doc(issued_at=issued, ttl_seconds=3600)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    gate = gate_query.load_gate(path)
    try:
        gate_query.verify_gate(gate, {"k1": KEY_A})
    except gate_query.NoSignal as exc:
        assert "expired" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_verify_gate_inf_ttl_is_no_signal(tmp_path):
    # int(Infinity) raises OverflowError, not ValueError (Engineering
    # round-3 note) — a non-finite ttl must be no-signal, not a traceback.
    doc = _make_gate_doc()
    doc["ttl_seconds"] = float("inf")
    # Re-sign: the ttl change must be covered by the MAC for this test to
    # exercise the ttl parse rather than the MAC check.
    body = {k: v for k, v in doc.items() if k != "hmac"}
    doc["hmac"] = _sign(body, KEY_A)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    gate = gate_query.load_gate(path)
    try:
        gate_query.verify_gate(gate, {"k1": KEY_A})
    except gate_query.NoSignal as exc:
        assert "ttl_seconds" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


# ---------------------------------------------------------------------------
# box_wave / component_permitted


def test_box_wave_assignment_pin_wins():
    wave = {"assignments": {"box-7": 3}}
    assert gate_query.box_wave("box-7", wave) == 3


def test_box_wave_hash_default_in_range_and_stable():
    for box_id in ("box-1", "box-2", "box-3", "box-99"):
        w = gate_query.box_wave(box_id, {})
        assert 0 <= w <= 3
        assert gate_query.box_wave(box_id, {}) == w


def test_box_wave_hash_default_is_not_constant():
    # The default is a real sha256-mod-4 hash of the box id, not a stub:
    # over 200 distinct ids it must land on more than one cohort (this is
    # deterministic — the inputs are fixed — and a constant neuter fails it).
    waves = {gate_query.box_wave(f"box-{n}", {}) for n in range(200)}
    assert len(waves) > 1


def test_box_wave_malformed_pin_is_no_signal():
    # A non-integer pin is no-signal, not a ValueError traceback (QA B2).
    try:
        gate_query.box_wave("box-7", {"assignments": {"box-7": "abc"}})
    except gate_query.NoSignal as exc:
        assert "not a wave number" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_box_wave_non_dict_wave_is_no_signal():
    # A null per-component wave entry (the _my_wave display path in
    # answer()) must be no-signal, not an AttributeError (Engineering
    # delta note).
    try:
        gate_query.box_wave("box-7", None)
    except gate_query.NoSignal as exc:
        assert "not an object" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_box_wave_non_finite_pin_is_no_signal():
    # json accepts Infinity/NaN as extensions; a non-finite pin is
    # malformed (Security delta note).
    for bad in (float("inf"), float("nan")):
        try:
            gate_query.box_wave("box-7", {"assignments": {"box-7": bad}})
        except gate_query.NoSignal as exc:
            assert "not a wave number" in str(exc)
        else:
            raise AssertionError(f"expected NoSignal for {bad!r}")


def test_box_wave_non_dict_assignments_is_no_signal():
    # A truthy non-dict assignments field (True, 5, a list) would TypeError
    # on the `in` membership test — no honest pin can be read (Security
    # round-3 note).
    for bad in (True, 5, ["box-7"]):
        try:
            gate_query.box_wave("box-7", {"assignments": bad})
        except gate_query.NoSignal as exc:
            assert "not an object" in str(exc)
        else:
            raise AssertionError(f"expected NoSignal for {bad!r}")


def test_component_permitted_non_dict_wave_is_false():
    assert gate_query.component_permitted("box-1", "repo",
                                          {"repo": None}) is False
    assert gate_query.component_permitted("box-1", "repo", {}) is False


def test_component_permitted_never_states_are_false():
    for state in ("draft", "halted", "bogus"):
        waves = {"repo": {"state": state, "live": 4,
                          "assignments": {"box-1": 0}}}
        assert gate_query.component_permitted("box-1", "repo",
                                              waves) is False, state


def test_component_permitted_unhashable_state_is_false():
    # A non-string state (e.g. a list) is unhashable — `in` on the
    # LIVE_STATES set would TypeError. "Not a live state" is already the
    # fail-closed outcome (Security round-3 note).
    waves = {"repo": {"state": ["wave-1"], "live": 4,
                      "assignments": {"box-1": 0}}}
    assert gate_query.component_permitted("box-1", "repo",
                                          waves) is False


def test_component_permitted_canary_is_pin_only_wave_1():
    waves = {"repo": {"state": "canary", "live": 4,
                      "assignments": {"box-1": 1, "box-2": 2}}}
    assert gate_query.component_permitted("box-1", "repo", waves) is True
    assert gate_query.component_permitted("box-2", "repo", waves) is False
    # An unassigned box has no pin (pin-only: `assignments.get(box_id, -1)`)
    # so it is never in the canary.
    assert gate_query.component_permitted("box-9", "repo", waves) is False


def test_component_permitted_malformed_live_is_no_signal():
    # A non-integer live ceiling is no-signal (QA B2).
    waves = {"repo": {"state": "wave-1", "live": "abc",
                      "assignments": {"box-1": 0}}}
    try:
        gate_query.component_permitted("box-1", "repo", waves)
    except gate_query.NoSignal as exc:
        assert "malformed" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_component_permitted_malformed_canary_pin_is_no_signal():
    waves = {"repo": {"state": "canary", "live": 4,
                      "assignments": {"box-1": "abc"}}}
    try:
        gate_query.component_permitted("box-1", "repo", waves)
    except gate_query.NoSignal as exc:
        assert "malformed" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_component_permitted_null_assignments_does_not_crash():
    # A present-but-null assignments field must not AttributeError (QA B2).
    waves = {"repo": {"state": "canary", "live": 4, "assignments": None}}
    assert gate_query.component_permitted("box-1", "repo",
                                          waves) is False


def test_component_permitted_list_assignments_admits_nobody():
    # A truthy non-dict assignments field is not a pin map — canary
    # pin-only semantics mean nobody is admitted (QA round-2 note).
    waves = {"repo": {"state": "canary", "live": 4,
                      "assignments": ["box-1"]}}
    assert gate_query.component_permitted("box-1", "repo",
                                          waves) is False


def test_component_permitted_non_finite_live_is_no_signal():
    waves = {"repo": {"state": "wave-1", "live": float("inf"),
                      "assignments": {"box-1": 0}}}
    try:
        gate_query.component_permitted("box-1", "repo", waves)
    except gate_query.NoSignal as exc:
        assert "malformed" in str(exc)
    else:
        raise AssertionError("expected NoSignal")


def test_component_permitted_live_ceiling():
    waves = {"repo": {"state": "wave-2", "live": 2,
                      "assignments": {"box-a": 2, "box-b": 3}}}
    assert gate_query.component_permitted("box-a", "repo", waves) is True
    assert gate_query.component_permitted("box-b", "repo", waves) is False


def test_component_permitted_missing_live_means_ceiling_zero():
    # int(wave.get("live", 0)): an absent live pins the ceiling at 0 —
    # only wave-0 boxes pass (documented here so a silent change is loud).
    waves = {"repo": {"state": "wave-1",
                      "assignments": {"box-a": 0, "box-b": 1}}}
    assert gate_query.component_permitted("box-a", "repo", waves) is True
    assert gate_query.component_permitted("box-b", "repo", waves) is False


# ---------------------------------------------------------------------------
# answer


def test_answer_no_signal_doc_is_frozen_shape(tmp_path):
    path = str(tmp_path / "missing-gate.json")
    ans = gate_query.answer(path, "box-1", {"k1": KEY_A})
    assert ans["state"] == "frozen"
    assert ans["freeze"] == "true"
    assert ans["answer_age_s"] == "-1"
    assert ans["reason"].startswith("no-signal: ")
    assert ans["key_id"] == ""


def test_answer_bad_mac_is_frozen_shape(tmp_path):
    doc = _make_gate_doc(key_id="k1", key=KEY_B)  # wrong key -> MAC fail
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    ans = gate_query.answer(path, "box-1", {"k1": KEY_A})
    assert ans["state"] == "frozen"
    assert ans["freeze"] == "true"
    assert "MAC mismatch" in ans["reason"]
    assert ans["key_id"] == ""


def test_answer_freeze_flag_freezes_all_components(tmp_path):
    waves = {"repo": {"state": "complete", "live": 4, "assignments": {}}}
    doc = _make_gate_doc(freeze=True, waves=waves)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    ans = gate_query.answer(path, "box-1", {"k1": KEY_A})
    assert ans["state"] == "frozen"
    assert ans["freeze"] == "true"
    assert ans["reason"] == "freeze flag set"
    assert ans["key_id"] == "k1"
    for comp in ("repo", "toolset", "image"):
        assert ans[f"{comp}_permitted"] == "false"
    assert ans["answer_age_s"] != "-1"  # the doc parsed; age is known


def test_answer_live_doc_permits_and_names_wave(tmp_path):
    waves = {"repo": {"state": "wave-3", "live": 3,
                      "assignments": {"box-1": 2}},
             "toolset": {"state": "halted", "live": 4, "assignments": {}}}
    doc = _make_gate_doc(freeze=False, waves=waves)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    ans = gate_query.answer(path, "box-1", {"k1": KEY_A})
    assert ans["state"] == "live"
    assert ans["freeze"] == "false"
    assert ans["reason"] == "gate ok"
    assert ans["repo_permitted"] == "true"
    assert ans["repo_max"] == "deadbeef"
    assert ans["repo_my_wave"] == "2"
    assert ans["toolset_permitted"] == "false"  # halted is never permitted
    assert ans["image_permitted"] == "false"   # missing wave entry
    assert ans["image_max"] == ""


def test_answer_malformed_wave_entry_is_frozen(tmp_path):
    # A MAC-valid doc whose wave entry is malformed must freeze the box,
    # not crash the tick-time query (QA B2 — the _validate_manifest wall
    # makes this unreachable via the real publisher, but the enforcement
    # point must not depend on that).
    waves = {"repo": {"state": "wave-1", "live": "abc",
                      "assignments": {"box-1": 0}}}
    doc = _make_gate_doc(freeze=False, waves=waves)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    ans = gate_query.answer(path, "box-1", {"k1": KEY_A})
    assert ans["state"] == "frozen"
    assert ans["freeze"] == "true"
    assert ans["reason"].startswith("no-signal: ")
    assert "malformed" in ans["reason"]


def test_answer_null_wave_entry_is_frozen(tmp_path):
    # A null per-component wave entry in a MAC-valid doc must freeze the
    # box, not AttributeError on the _my_wave display path (Engineering
    # delta note).
    waves = {"repo": None}
    doc = _make_gate_doc(freeze=False, waves=waves)
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    ans = gate_query.answer(path, "box-1", {"k1": KEY_A})
    assert ans["state"] == "frozen"
    assert ans["freeze"] == "true"
    assert ans["reason"].startswith("no-signal: ")
    assert "not an object" in ans["reason"]


def test_answer_list_waves_section_is_frozen(tmp_path):
    # A truthy non-dict waves section cannot be evaluated honestly —
    # no-signal, not an AttributeError (QA round-2 note).
    doc = _make_gate_doc(freeze=False, waves=["repo"])
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    ans = gate_query.answer(path, "box-1", {"k1": KEY_A})
    assert ans["state"] == "frozen"
    assert ans["reason"].startswith("no-signal: ")
    assert "waves is not an object" in ans["reason"]


def test_answer_list_releases_section_is_frozen(tmp_path):
    doc = _make_gate_doc(freeze=False,
                         waves={"repo": {"state": "complete", "live": 4,
                                         "assignments": {}}},
                         extra={"releases": ["repo"]})
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    ans = gate_query.answer(path, "box-1", {"k1": KEY_A})
    assert ans["state"] == "frozen"
    assert ans["reason"].startswith("no-signal: ")
    assert "releases is not an object" in ans["reason"]


def test_answer_list_release_entry_is_frozen(tmp_path):
    # A truthy non-dict per-component release entry cannot be read honestly
    # (Security round-3 note) — no-signal, not an AttributeError.
    doc = _make_gate_doc(freeze=False,
                         waves={"repo": {"state": "complete", "live": 4,
                                         "assignments": {}}},
                         extra={"releases": {"repo": ["deadbeef"]}})
    path = str(tmp_path / "gate.json")
    _write_gate(path, doc)
    ans = gate_query.answer(path, "box-1", {"k1": KEY_A})
    assert ans["state"] == "frozen"
    assert ans["reason"].startswith("no-signal: ")
    assert "release entry for 'repo' is not an object" in ans["reason"]


# ---------------------------------------------------------------------------
# answer: canary _my_wave is the pin, never the hash cohort (#1718)


def _canary_doc(box_id_to_pin, assignments=None):
    """A gate doc with repo in canary state; other components unstaged."""
    if assignments is None:
        assignments = {"canary-pinned-1": 1, "canary-pinned-2": 2}
    waves = {"repo": {"state": "canary", "live": 0,
                      "assignments": assignments}}
    return _make_gate_doc(freeze=False, waves=waves)


def _canary_answer(tmp_path, box_id, assignments=None):
    path = str(tmp_path / "gate.json")
    _write_gate(path, _canary_doc(None, assignments=assignments))
    return gate_query.answer(path, box_id, {"k1": KEY_A})


def test_answer_canary_my_wave_reports_pin_for_admitted_box(tmp_path):
    # Canary is pin-only: the box pinned to wave 1 is in the canary, and
    # _my_wave must name the actual pin (1) — NOT box_wave()'s hash cohort
    # (sha256("canary-pinned-1") % 4 == 2, pinned below, not recomputed).
    ans = _canary_answer(tmp_path, "canary-pinned-1")
    assert ans["state"] == "live"
    assert ans["repo_permitted"] == "true"
    assert ans["repo_my_wave"] == "1"
    assert ans["repo_my_wave"] != "2"  # the hash cohort it must not show


def test_answer_canary_my_wave_reports_pin_for_denied_box(tmp_path):
    # Pinned to wave 2: not admitted to the canary, but the pin is still
    # the box's actual cohort — "2", not its hash cohort ("0").
    ans = _canary_answer(tmp_path, "canary-pinned-2")
    assert ans["state"] == "live"
    assert ans["repo_permitted"] == "false"
    assert ans["repo_my_wave"] == "2"
    assert ans["repo_my_wave"] != "0"  # the hash cohort it must not show


def test_answer_canary_my_wave_empty_when_unpinned(tmp_path):
    # No pin: no canary cohort. "" (the <comp>_max empty convention) —
    # never the hash cohort "0" the old display path computed (#1718).
    ans = _canary_answer(tmp_path, "canary-unpinned")
    assert ans["state"] == "live"
    assert ans["repo_permitted"] == "false"
    assert ans["repo_my_wave"] == ""


def test_answer_canary_my_wave_empty_when_assignments_not_a_map(tmp_path):
    # A truthy non-dict assignments field is not a pin map: no pins, so
    # nobody is admitted (enforcement) and no cohort is displayed (#1718).
    ans = _canary_answer(tmp_path, "canary-pinned-1", assignments=["nope"])
    assert ans["state"] == "live"
    assert ans["repo_permitted"] == "false"
    assert ans["repo_my_wave"] == ""


def test_answer_canary_malformed_pin_freezes(tmp_path):
    # A malformed pin is no-signal — the whole answer freezes, exactly as
    # the enforcement path does (display must never outrun enforcement).
    ans = _canary_answer(tmp_path, "canary-pinned-1",
                         assignments={"canary-pinned-1": "one"})
    assert ans["state"] == "frozen"
    assert ans["reason"].startswith("no-signal: ")
    assert "malformed" in ans["reason"]


def test_answer_canary_present_none_pin_freezes(tmp_path):
    # Present-but-None pin: enforcement raises NoSignal (int(None)), so
    # display must freeze too — a quiet "" here would lie about a doc the
    # box must freeze on.
    ans = _canary_answer(tmp_path, "canary-pinned-1",
                         assignments={"canary-pinned-1": None})
    assert ans["state"] == "frozen"
    assert "malformed" in ans["reason"]
