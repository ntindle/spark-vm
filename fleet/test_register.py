"""Hermetic suite for fleet/register.py (issue #775 S2).

Stdlib only, subprocess-exercised: every behavior test drives the real
CLI in a tmp store, like the other fleet suites. Run with
`python3 -m pytest fleet/test_register.py`.
"""

import base64
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "register.py")
JOURNAL = os.path.join(HERE, "update_journal.py")

FP_A = "ab" * 32  # 64 lowercase hex chars: a 32-byte digest in hex
FP_B = "cd" * 32  # a different 32-byte digest


def _canon(fp_hex):
    return "SHA256:" + base64.b64encode(
        bytes.fromhex(fp_hex)).decode().rstrip("=")


CANON_A = _canon(FP_A)
# The same fingerprint in ed25519.fingerprint()'s phone-grouped form.
GROUPED_A = "SHA256:" + " ".join(
    base64.b64encode(bytes.fromhex(FP_A)).decode().rstrip("=")[i:i + 4]
    for i in range(0, 43, 4))


def run(*argv):
    # timeout=60 bounds every subprocess call. The journal lock's own
    # bounded wait is 300s, so a wedged lock surfaces here as
    # TimeoutExpired (a loud, attributable failure), never a hang —
    # but the failure would be confusing: if you see it, suspect the
    # lock holder, not this harness.
    return subprocess.run([sys.executable, MODULE, *argv],
                          capture_output=True, text=True, timeout=60)


def init_ok(tmp_path, fp=FP_A, store_name="store"):
    store = str(tmp_path / store_name)
    r = run("init", "--store", store, "--operator-fingerprint", fp)
    assert r.returncode == 0, r.stderr
    return store


def read_pin_file(store):
    with open(os.path.join(store, "operator-identity.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def read_journal(store):
    path = os.path.join(store, "update-journal.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def register_ok(tmp_path, tenant="acme", release_id="r1", channel="stable",
                policy_ref="p", store_name="store", extra=()):
    store = str(tmp_path / store_name)
    r = run("register", "--store", store, "--tenant", tenant,
            "--release-id", release_id, "--channel", channel,
            "--policy-ref", policy_ref, *extra)
    assert r.returncode == 0, r.stderr
    return store, r.stdout.strip()


# --- init ------------------------------------------------------------

def test_init_writes_pin_canonical_form(tmp_path):
    # A grouped SHA256: input journals in the one canonical form —
    # the canonical form cannot drift from S1's.
    store = str(tmp_path / "store")
    r = run("init", "--store", store, "--operator-fingerprint", GROUPED_A)
    assert r.returncode == 0, r.stderr
    pin = read_pin_file(store)
    assert pin["format"] == 1
    assert pin["operator_fingerprint"] == CANON_A
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                        pin["pinned_at"])


def test_init_idempotent_same_fingerprint(tmp_path):
    store = str(tmp_path / "store")
    r1 = run("init", "--store", store, "--operator-fingerprint", FP_A)
    assert r1.returncode == 0, r1.stderr
    before = read_pin_file(store)
    # Same digest in a different accepted form converges, not fails.
    r2 = run("init", "--store", store, "--operator-fingerprint", GROUPED_A)
    assert r2.returncode == 0, r2.stderr
    assert read_pin_file(store) == before


def test_init_refuses_repin_different_key(tmp_path):
    store = init_ok(tmp_path, FP_A)
    r = run("init", "--store", store, "--operator-fingerprint", FP_B)
    assert r.returncode == 2, r.stderr
    assert "1407" in r.stderr or "rotation" in r.stderr.lower()
    # The original pin is untouched — the refusal paved over nothing.
    assert read_pin_file(store)["operator_fingerprint"] == CANON_A


def test_init_rejects_bad_fingerprint(tmp_path):
    store = str(tmp_path / "store")
    r = run("init", "--store", store, "--operator-fingerprint",
            "not-a-fingerprint")
    assert r.returncode == 2, r.stderr
    assert not os.path.exists(os.path.join(store, "operator-identity.json"))


def test_init_rejects_bare_name(tmp_path):
    # The "never a bare name" rule is structural: a name matches no
    # accepted fingerprint shape.
    store = str(tmp_path / "store")
    r = run("init", "--store", store, "--operator-fingerprint", "operator")
    assert r.returncode == 2, r.stderr
    assert not os.path.exists(os.path.join(store, "operator-identity.json"))


# --- register --------------------------------------------------------

def test_register_without_pin_fails_closed(tmp_path):
    store = str(tmp_path / "store")
    r = run("register", "--store", store, "--tenant", "acme",
            "--release-id", "r1", "--channel", "stable",
            "--policy-ref", "p")
    assert r.returncode == 2, r.stderr
    assert "init" in r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_register_journals_with_pinned_identity(tmp_path):
    store = init_ok(tmp_path, FP_A)
    r = run("register", "--store", store, "--tenant", "acme",
            "--release-id", "sparkvm-box@abc123", "--channel", "stable",
            "--policy-ref", "docs/UPDATE_CHANNEL_POLICY.md",
            "--ts", "2026-10-15T07:00:00Z")
    assert r.returncode == 0, r.stderr
    ref = r.stdout.strip()
    assert re.fullmatch(r"reg-[0-9a-f]{16}", ref)
    rows = read_journal(store)
    assert len(rows) == 1
    row = rows[0]
    assert row["record"] == "registration"
    assert row["tenant_id"] == "acme"
    # The record carries the PINNED identity — not a per-invocation claim.
    assert row["actor_fingerprint"] == CANON_A
    assert row["release_id"] == "sparkvm-box@abc123"
    assert row["ts"] == "2026-10-15T07:00:00Z"
    assert row["registration_ref"] == ref


def test_register_has_no_actor_fingerprint_flag(tmp_path):
    # Structural: the registration path cannot self-attest a different
    # identity — the flag does not exist.
    store = init_ok(tmp_path, FP_A)
    r = run("register", "--store", store, "--tenant", "acme",
            "--release-id", "r1", "--channel", "stable",
            "--policy-ref", "p", "--actor-fingerprint", FP_B)
    assert r.returncode == 2
    assert "unrecognized arguments" in r.stderr


def test_register_has_no_registration_ref_flag(tmp_path):
    # The ref is generated, never accepted (S1's fork-the-chain rule).
    store = init_ok(tmp_path, FP_A)
    r = run("register", "--store", store, "--tenant", "acme",
            "--release-id", "r1", "--channel", "stable",
            "--policy-ref", "p", "--registration-ref", "reg-deadbeef")
    assert r.returncode == 2
    assert "unrecognized arguments" in r.stderr


def test_register_security_channel_requires_advisory_ref(tmp_path):
    store = init_ok(tmp_path, FP_A)
    r = run("register", "--store", store, "--tenant", "acme",
            "--release-id", "r1", "--channel", "security",
            "--policy-ref", "p")
    assert r.returncode == 2, r.stderr
    assert "advisory_ref" in r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_register_security_channel_with_advisory_ref_ok(tmp_path):
    store = init_ok(tmp_path, FP_A)
    store, ref = register_ok(tmp_path, channel="security",
                             extra=("--advisory-ref", "CVE-2026-0001",))
    assert re.fullmatch(r"reg-[0-9a-f]{16}", ref)
    rows = read_journal(store)
    assert rows[0]["advisory_ref"] == "CVE-2026-0001"


def test_register_ref_chains_wave_assignment(tmp_path):
    # The printed ref is chainable through S1's journal: a wave
    # assignment citing it journals, proving S2's registration is the
    # authorizing registration S1's chaining expects.
    store = init_ok(tmp_path, FP_A)
    _, ref = register_ok(tmp_path)
    data = {"box_id": "box-1", "wave": 0, "canary": True,
            "manifest_version": "v1", "registration_ref": ref}
    r = subprocess.run(
        [sys.executable, JOURNAL, "append", "--store", store,
         "--tenant", "acme", "--actor-fingerprint", FP_A,
         "--record", "wave_assignment", "--data", json.dumps(data)],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    rows = read_journal(store)
    assert [row["record"] for row in rows] == ["registration",
                                              "wave_assignment"]
    assert rows[1]["registration_ref"] == ref


def test_register_corrupt_pin_fails_closed(tmp_path):
    # A corrupt trust root is an integrity failure (exit 1), not a
    # usage error — and nothing is journaled under it.
    store = str(tmp_path / "store")
    os.makedirs(store, exist_ok=True)
    with open(os.path.join(store, "operator-identity.json"), "w",
              encoding="utf-8") as fh:
        fh.write("{not json")
    r = run("register", "--store", store, "--tenant", "acme",
            "--release-id", "r1", "--channel", "stable",
            "--policy-ref", "p")
    assert r.returncode == 1, r.stderr
    assert "untrusted" in r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_register_wrong_format_pin_fails_closed(tmp_path):
    store = str(tmp_path / "store")
    os.makedirs(store, exist_ok=True)
    with open(os.path.join(store, "operator-identity.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"format": 2, "operator_fingerprint": CANON_A,
                   "pinned_at": "2026-10-15T07:00:00Z"}, fh)
    r = run("register", "--store", store, "--tenant", "acme",
            "--release-id", "r1", "--channel", "stable",
            "--policy-ref", "p")
    assert r.returncode == 1, r.stderr


def test_register_after_repin_attempt_still_uses_original(tmp_path):
    # The failed re-pin changes nothing downstream: the next register
    # still journals under the original pin.
    store = init_ok(tmp_path, FP_A)
    r = run("init", "--store", store, "--operator-fingerprint", FP_B)
    assert r.returncode == 2
    _, ref = register_ok(tmp_path)
    assert re.fullmatch(r"reg-[0-9a-f]{16}", ref)
    rows = read_journal(store)
    assert rows[0]["actor_fingerprint"] == CANON_A


# --- show-identity ---------------------------------------------------

def test_show_identity_prints_pin(tmp_path):
    store = init_ok(tmp_path, GROUPED_A)
    r = run("show-identity", "--store", store)
    assert r.returncode == 0, r.stderr
    shown = json.loads(r.stdout)
    assert shown["operator_fingerprint"] == CANON_A
    assert shown["format"] == 1


def test_show_identity_without_pin_fails_closed(tmp_path):
    r = run("show-identity", "--store", str(tmp_path / "store"))
    assert r.returncode == 2, r.stderr
    assert "init" in r.stderr


def test_register_canonicalizes_handwritten_pin(tmp_path):
    # A pin written by hand (hex form, not the canonical SHA256: form)
    # still journals in canonical form. Honesty note: this pins the
    # COMPOSED end-to-end invariant (the journal never carries two
    # spellings of one identity) — S1's build_record normalizes the
    # actor fingerprint itself, so this test passes even with read_pin's
    # normalization removed. The read_pin-specific pin is
    # test_show_identity_canonicalizes_handwritten_pin below.
    store = str(tmp_path / "store")
    os.makedirs(store, exist_ok=True)
    with open(os.path.join(store, "operator-identity.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"format": 1, "operator_fingerprint": FP_A,
                   "pinned_at": "2026-10-15T07:00:00Z"}, fh)
    r = run("register", "--store", store, "--tenant", "acme",
            "--release-id", "r1", "--channel", "stable",
            "--policy-ref", "p")
    assert r.returncode == 0, r.stderr
    rows = read_journal(store)
    assert rows[0]["actor_fingerprint"] == CANON_A


def test_init_converges_with_handwritten_hex_pin(tmp_path):
    # A pin written by hand in hex form (not canonical) must not make
    # init with the same key look like a re-pin: read_pin normalizes
    # before the comparison, so provisioning converges.
    store = str(tmp_path / "store")
    os.makedirs(store, exist_ok=True)
    with open(os.path.join(store, "operator-identity.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"format": 1, "operator_fingerprint": FP_A,
                   "pinned_at": "2026-10-15T07:00:00Z"}, fh)
    r = run("init", "--store", store, "--operator-fingerprint",
            GROUPED_A)
    assert r.returncode == 0, r.stderr


def test_init_corrupt_pin_is_integrity_error(tmp_path):
    # A corrupt existing pin is an integrity failure (exit 1) on init
    # too — the kind is threaded, not string-matched.
    store = str(tmp_path / "store")
    os.makedirs(store, exist_ok=True)
    with open(os.path.join(store, "operator-identity.json"), "w",
              encoding="utf-8") as fh:
        fh.write("{not json")
    r = run("init", "--store", store, "--operator-fingerprint", FP_A)
    assert r.returncode == 1, r.stderr
    assert "untrusted" in r.stderr


def test_show_identity_canonicalizes_handwritten_pin(tmp_path):
    # read_pin normalizes the stored fingerprint: a pin written by hand
    # in hex form still reads back canonical. (The register-path test
    # cannot pin this — S1's build_record normalizes the actor
    # fingerprint itself, so it passes even with read_pin's
    # normalization removed.)
    store = str(tmp_path / "store")
    os.makedirs(store, exist_ok=True)
    with open(os.path.join(store, "operator-identity.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"format": 1, "operator_fingerprint": FP_A,
                   "pinned_at": "2026-10-15T07:00:00Z"}, fh)
    r = run("show-identity", "--store", store)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["operator_fingerprint"] == CANON_A


def test_racing_inits_serialize_loser_fails_closed(tmp_path):
    # The docstring's serialization promise, tested: two concurrent
    # inits with different keys — the lock serializes them, the loser
    # sees the winner's pin and fails closed (or converges on same).
    import concurrent.futures
    store = str(tmp_path / "store")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        r1, r2 = [f.result() for f in
                  (ex.submit(run, "init", "--store", store,
                             "--operator-fingerprint", fp)
                   for fp in (FP_A, FP_B))]
    assert sorted([r1.returncode, r2.returncode]) == [0, 2], \
        (r1.stderr, r2.stderr)
    pin = read_pin_file(store)
    assert pin["format"] == 1
    assert pin["operator_fingerprint"] in (CANON_A, _canon(FP_B))


def test_register_malformed_ts_fails_closed(tmp_path):
    # The --ts wiring through to S1's validation is pinned on the
    # register path, not assumed from S1's own suite.
    store = init_ok(tmp_path, FP_A)
    r = run("register", "--store", store, "--tenant", "acme",
            "--release-id", "r1", "--channel", "stable",
            "--policy-ref", "p", "--ts", "bogus")
    assert r.returncode == 2, r.stderr
    assert not os.path.exists(os.path.join(store, "update-journal.jsonl"))


def test_register_stdout_is_exactly_one_line(tmp_path):
    # The stdout contract: exactly the ref + newline. A stray second
    # line would silently corrupt REF=$(register ...) shell capture.
    store = init_ok(tmp_path, FP_A)
    r = run("register", "--store", store, "--tenant", "acme",
            "--release-id", "r1", "--channel", "stable",
            "--policy-ref", "p")
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("\n") == 1
    assert re.fullmatch(r"reg-[0-9a-f]{16}\n", r.stdout)


def test_init_store_path_is_file_fails_closed(tmp_path):
    # init where the store path is an existing file: cannot create the
    # store dir — runtime error (exit 1), nothing written.
    store = str(tmp_path / "store")
    with open(store, "w", encoding="utf-8") as fh:
        fh.write("x")
    r = run("init", "--store", store, "--operator-fingerprint", FP_A)
    assert r.returncode == 1, r.stderr
    assert "cannot create store dir" in r.stderr
