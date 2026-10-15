"""Hermetic suite for fleet/update_journal.py (issue #775 S1).

Stdlib only, subprocess-exercised: every behavior test drives the real
CLI in a tmp store, like the other fleet suites. Run with
`python3 -m pytest fleet/test_update_journal.py`.
"""

import base64
import json
import os
import re
import subprocess
import sys

MODULE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "update_journal.py")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FP = "ab" * 32  # 64 lowercase hex chars: the 32-byte digest in hex
# The canonical journal form FP normalizes to.
CANON = "SHA256:" + base64.b64encode(bytes.fromhex(FP)).decode().rstrip("=")
# The same fingerprint in ed25519.fingerprint()'s phone-grouped form.
GROUPED = "SHA256:" + " ".join(
    base64.b64encode(bytes.fromhex(FP)).decode().rstrip("=")[i:i + 4]
    for i in range(0, 43, 4))
BAD_FP = "not-a-fingerprint"


def run(*argv):
    return subprocess.run([sys.executable, MODULE, *argv],
                          capture_output=True, text=True, timeout=60)


def append_ok(tmp_path, record, data, tenant="acme", fp=FP, extra=(),
              store_name="store"):
    store = str(tmp_path / store_name)
    r = run("append", "--store", store, "--tenant", tenant,
            "--actor-fingerprint", fp, "--record", record,
            "--data", json.dumps(data), *extra)
    assert r.returncode == 0, r.stderr
    return store


def register(tmp_path, tenant="acme", release_id="r1", channel="stable",
             policy_ref="p", ts="2026-10-15T06:00:00Z", store_name="store",
             **extra_data):
    data = {"release_id": release_id, "channel": channel,
            "policy_ref": policy_ref}
    data.update(extra_data)
    store = str(tmp_path / store_name)
    r = run("append", "--store", store, "--tenant", tenant,
            "--actor-fingerprint", FP, "--record", "registration",
            "--data", json.dumps(data), "--ts", ts)
    assert r.returncode == 0, r.stderr
    return store, r.stdout.strip()


def read_journal(store):
    path = os.path.join(store, "update-journal.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# --- registration ----------------------------------------------------

def test_registration_appends_wellformed_record(tmp_path):
    data = {"release_id": "sparkvm-box@abc123", "channel": "stable",
            "policy_ref": "docs/UPDATE_CHANNEL_POLICY.md"}
    store = append_ok(tmp_path, "registration", data, extra=("--ts", "2026-10-15T06:00:00Z"))
    rows = read_journal(store)
    assert len(rows) == 1
    row = rows[0]
    assert row["record"] == "registration"
    assert row["tenant_id"] == "acme"
    # The fingerprint journals in canonical form, not as supplied.
    assert row["actor_fingerprint"] == CANON
    assert row["ts"] == "2026-10-15T06:00:00Z"
    assert row["release_id"] == "sparkvm-box@abc123"
    assert re.fullmatch(r"reg-[0-9a-f]{16}", row["registration_ref"])


def test_fingerprint_accepts_real_ed25519_output():
    # Journal with an actual ed25519.fingerprint() output, not a
    # hand-built string (the repo's provisioned-key identity primitive).
    sys.path.insert(0, os.path.join(REPO_ROOT, "pairing"))
    import ed25519
    seed = bytes(range(32))  # deterministic test seed, not a real key
    fp = ed25519.fingerprint(ed25519.publickey_from_seed(seed))
    assert fp.startswith("SHA256:")
    assert " " in fp  # the phone-grouped form
    sys.path.insert(0, os.path.dirname(MODULE))
    import update_journal as uj
    canon = uj._normalize_fingerprint(fp)
    assert canon.startswith("SHA256:") and " " not in canon
    rec, err = uj.build_record("freeze", "acme", fp, {"reason": "x"})
    assert err is None, err
    assert rec["actor_fingerprint"] == canon


def test_fingerprint_normalizes_to_canonical(tmp_path):
    # The repo's real fingerprint form (pairing/ed25519.fingerprint():
    # 'SHA256:' + grouped base64) and the hex form journal identically.
    # The prefix is case-insensitive; the base64 body is not (base64
    # is case-sensitive — lowercasing the body would name a different
    # key, correctly rejected as a different fingerprint... it is
    # still 32 bytes, so it normalizes to its own canonical form).
    body = CANON[len("SHA256:"):]
    for fp_in, expect in ((FP, CANON), (GROUPED, CANON),
                          (CANON, CANON), ("sha256:" + body, CANON)):
        store = append_ok(tmp_path, "freeze", {"reason": "x"}, fp=fp_in,
                          store_name="store-%d" % abs(hash(fp_in)))
        row = read_journal(store)[0]
        assert row["actor_fingerprint"] == expect, fp_in


def test_registration_ref_deterministic(tmp_path):
    data = {"release_id": "r1", "channel": "stable", "policy_ref": "p"}
    ts = "2026-10-15T06:00:00Z"
    s1 = append_ok(tmp_path, "registration", data, extra=("--ts", ts))
    s2 = append_ok(tmp_path, "registration", data, extra=("--ts", ts))
    # ...and distinct across distinct registrations (last row of the
    # shared store — the first two rows are the identical r1 pair).
    s3 = append_ok(tmp_path, "registration",
                   {"release_id": "r2", "channel": "stable",
                    "policy_ref": "p"}, extra=("--ts", ts))
    rows = read_journal(s3)
    assert len(rows) == 3
    assert rows[0]["registration_ref"] == rows[1]["registration_ref"]
    assert rows[2]["registration_ref"] != rows[0]["registration_ref"]


def test_security_channel_requires_advisory_ref(tmp_path):
    store = str(tmp_path / "store")
    data = {"release_id": "r1", "channel": "security", "policy_ref": "p"}
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "registration",
            "--data", json.dumps(data))
    assert r.returncode == 2
    assert "advisory_ref" in r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))
    data["advisory_ref"] = "CVE-2026-00001"
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "registration",
            "--data", json.dumps(data))
    assert r.returncode == 0, r.stderr


# --- attribution fail-closed ------------------------------------------

def test_tenant_required(tmp_path):
    store = str(tmp_path / "store")
    r = run("append", "--store", store, "--actor-fingerprint", FP,
            "--record", "freeze", "--data", '{"reason": "x"}')
    assert r.returncode == 2
    assert "tenant" in r.stderr.lower()
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_actor_fingerprint_required(tmp_path):
    store = str(tmp_path / "store")
    r = run("append", "--store", store, "--tenant", "acme",
            "--record", "freeze", "--data", '{"reason": "x"}')
    assert r.returncode == 2
    assert "fingerprint" in r.stderr.lower()
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_bare_name_rejected(tmp_path):
    # A bare name is not an identity: the shape check is the
    # "never a bare name" enforcement point.
    for name in ("operator", "ntindle", "OP-1",
                 FP.upper(),  # hex, but not lowercase
                 "ab" * 8):   # hex, but too short to be a digest
        store = str(tmp_path / f"store-{name}")
        r = run("append", "--store", store, "--tenant", "acme",
                "--actor-fingerprint", name, "--record", "freeze",
                "--data", '{"reason": "x"}')
        assert r.returncode == 2, name
        assert not os.path.exists(
            os.path.join(store, "update-journal.jsonl")), name


def test_reimage_requires_registration_ref(tmp_path):
    store = str(tmp_path / "store")
    data = {"box_id": "b1", "image_from": "n", "image_to": "n+1",
            "wave": 1, "migration_outcome": "success"}
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "reimage",
            "--data", json.dumps(data))
    assert r.returncode == 2
    assert "registration_ref" in r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))
    # A malformed ref is not a chain.
    data["registration_ref"] = "bogus"
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "reimage",
            "--data", json.dumps(data))
    assert r.returncode == 2
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_freeze_rejects_registration_ref(tmp_path):
    # Freeze is release-independent and global: a registration_ref on
    # one misattributes a fleet-wide operator action to one release.
    store = str(tmp_path / "store")
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "freeze",
            "--data", json.dumps({"reason": "x",
                                  "registration_ref": "reg-0123456789abcdef"}))
    assert r.returncode == 2
    assert "release-independent" in r.stderr
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "freeze",
            "--data", json.dumps({"reason": "x"}))
    assert r.returncode == 0, r.stderr
    rows = read_journal(store)
    assert rows[0]["record"] == "freeze"
    assert "registration_ref" not in rows[0]


# --- schema-exact -------------------------------------------------------

def test_unknown_record_type_rejected(tmp_path):
    store = str(tmp_path / "store")
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "bogus",
            "--data", "{}")
    assert r.returncode == 2
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_unknown_field_rejected(tmp_path):
    # A misspelled tenent_id journaling under a wrong key is an
    # attribution hole; silently dropping it is a different one.
    store = str(tmp_path / "store")
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "freeze",
            "--data", json.dumps({"reason": "x", "reasno": "y"}))
    assert r.returncode == 2
    assert "unknown field" in r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_missing_required_field_rejected(tmp_path):
    store = str(tmp_path / "store")
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "wave_assignment",
            "--data", json.dumps({"box_id": "b1", "wave": 1,
                                  "canary": False,
                                  "registration_ref": "reg-0123456789abcdef"}))
    assert r.returncode == 2
    assert "manifest_version" in r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_wrong_field_type_rejected(tmp_path):
    store = str(tmp_path / "store")
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "wave_assignment",
            "--data", json.dumps({"box_id": "b1", "wave": "two",
                                  "canary": False,
                                  "manifest_version": "m1",
                                  "registration_ref": "reg-0123456789abcdef"}))
    assert r.returncode == 2
    assert "wave" in r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_bool_not_accepted_as_int(tmp_path):
    # Python bool is an int subclass; canary=true where an int is
    # expected must still fail the schema.
    store = str(tmp_path / "store")
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "wave_assignment",
            "--data", json.dumps({"box_id": "b1", "wave": True,
                                  "canary": False,
                                  "manifest_version": "m1",
                                  "registration_ref": "reg-0123456789abcdef"}))
    assert r.returncode == 2
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


# --- referential chaining -----------------------------------------------

def test_chained_record_accepted_after_registration(tmp_path):
    store, ref = register(tmp_path)
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "reimage",
            "--data", json.dumps({"box_id": "b1", "image_from": "n",
                                  "image_to": "n+1", "wave": 1,
                                  "migration_outcome": "success",
                                  "registration_ref": ref}))
    assert r.returncode == 0, r.stderr
    rows = read_journal(store)
    assert rows[1]["registration_ref"] == ref


def test_chained_record_dangling_ref_rejected(tmp_path):
    # A reimage citing a never-registered ref is the unaccountable
    # reimage the design exists to prevent: fail closed, journal
    # nothing.
    store = str(tmp_path / "store")
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "reimage",
            "--data", json.dumps({"box_id": "b1", "image_from": "n",
                                  "image_to": "n+1", "wave": 1,
                                  "migration_outcome": "success",
                                  "registration_ref": "reg-0123456789abcdef"}))
    assert r.returncode == 2
    assert "not registered" in r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_chained_record_ref_is_tenant_scoped(tmp_path):
    # A ref registered under another tenant does not authorize this
    # tenant's reimage.
    store, ref = register(tmp_path, tenant="t1")
    r = run("append", "--store", store, "--tenant", "t2",
            "--actor-fingerprint", FP, "--record", "reimage",
            "--data", json.dumps({"box_id": "b1", "image_from": "n",
                                  "image_to": "n+1", "wave": 1,
                                  "migration_outcome": "success",
                                  "registration_ref": ref}))
    assert r.returncode == 2
    assert "not registered" in r.stderr
    assert len(read_journal(store)) == 1  # only the registration


def test_registration_rejects_supplied_ref(tmp_path):
    store = str(tmp_path / "store")
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "registration",
            "--data", json.dumps({"release_id": "r1", "channel": "stable",
                                  "policy_ref": "p",
                                  "registration_ref": "reg-0123456789abcdef"}))
    assert r.returncode == 2
    assert "never supplied" in r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_registration_ref_covers_policy(tmp_path):
    # Two registrations differing only in policy_ref must not share a
    # ref — the chained reimage would be ambiguous about which policy
    # authorized it.
    _, ref1 = register(tmp_path, policy_ref="p1", store_name="s1")
    _, ref2 = register(tmp_path, policy_ref="p2", store_name="s2")
    assert ref1 != ref2
    _, ref3 = register(tmp_path, policy_ref="p1", store_name="s3")
    assert ref1 == ref3  # identical inputs stay idempotent


def test_batch_registration_then_chain(tmp_path):
    # In-process: append_records walks the batch in order, so a
    # registration earlier in the same batch authorizes a later chain.
    sys.path.insert(0, os.path.dirname(MODULE))
    import update_journal as uj
    store = str(tmp_path / "store")
    reg, err = uj.build_record("registration", "acme", FP,
                               {"release_id": "r1", "channel": "stable",
                                "policy_ref": "p"})
    assert err is None
    rei, err = uj.build_record("reimage", "acme", FP,
                               {"box_id": "b1", "image_from": "n",
                                "image_to": "n+1", "wave": 1,
                                "migration_outcome": "success",
                                "registration_ref": reg["registration_ref"]})
    assert err is None
    count, err = uj.append_records(store, [reg, rei])
    assert err is None, err
    assert count == 2
    # Reversed: the chain cites a ref not yet journaled -> fail closed.
    count, err = uj.append_records(str(tmp_path / "store2"), [rei, reg])
    assert count is None
    assert "not registered" in err


# --- no-phantom discipline ----------------------------------------------

def test_deferred_and_skipped_write_with_reason(tmp_path):
    store, ref = register(tmp_path)
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "deferred",
            "--data", json.dumps({"box_id": "b1", "reason": "arc-busy",
                                  "registration_ref": ref}))
    assert r.returncode == 0, r.stderr
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "skipped",
            "--data", json.dumps({"box_id": "b2", "reason": "suspended",
                                  "registration_ref": ref}))
    assert r.returncode == 0, r.stderr
    rows = read_journal(store)
    kinds = [r["record"] for r in rows]
    assert kinds == ["registration", "deferred", "skipped"]
    assert rows[1]["reason"] == "arc-busy"


# --- read ---------------------------------------------------------------

def test_read_reports_malformed_as_skipped(tmp_path):
    store = append_ok(tmp_path, "freeze", {"reason": "drill"})
    with open(os.path.join(store, "update-journal.jsonl"), "a",
              encoding="utf-8") as fh:
        fh.write("not json at all\n")
        fh.write('{"record": "bogus", "tenant_id": "acme"}\n')
    r = run("read", "--store", store)
    assert r.returncode == 0, r.stderr
    rows = [json.loads(line) for line in r.stdout.splitlines()]
    assert len(rows) == 1
    assert rows[0]["record"] == "freeze"
    assert "2 malformed" in r.stderr
    assert "never gate-consumed" in r.stderr


def test_read_filters(tmp_path):
    store = append_ok(tmp_path, "freeze", {"reason": "a"}, tenant="t1")
    append_ok(tmp_path, "freeze", {"reason": "b"}, tenant="t2")
    r = run("read", "--store", store, "--tenant", "t1")
    assert r.returncode == 0, r.stderr
    rows = [json.loads(line) for line in r.stdout.splitlines()]
    assert len(rows) == 1
    assert rows[0]["tenant_id"] == "t1"
    r = run("read", "--store", store, "--record", "freeze", "--tenant",
            "t2")
    rows = [json.loads(line) for line in r.stdout.splitlines()]
    assert len(rows) == 1
    assert rows[0]["reason"] == "b"


def test_ts_defaults_to_utc_now(tmp_path):
    store = append_ok(tmp_path, "freeze", {"reason": "x"})
    row = read_journal(store)[0]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row["ts"])
    r = run("append", "--store", store, "--tenant", "acme",
            "--actor-fingerprint", FP, "--record", "freeze",
            "--data", '{"reason": "x"}', "--ts", "not-a-ts")
    assert r.returncode == 2
    assert len(read_journal(store)) == 1
