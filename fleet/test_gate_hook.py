"""Tests for the G18 S1b hook loop (issue #777).

fleet/gate_hook.sh runs `gate_query.py state` and atomically writes the
box's self-evaluated answer to the local gate status file — the latency
optimizer + status writer of docs/RELEASE_GATE_CHANNEL_DESIGN.md §3 (NOT
the enforcement point; the update tick's own re-query enforces).

Run from the repo root: python3 -m pytest fleet/test_gate_hook.py -q
"""

import binascii
import configparser
import json
import os
import stat
import subprocess
import time
from datetime import datetime, timezone

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HOOK = os.path.join(REPO, "fleet", "gate_hook.sh")
PUBLISH = os.path.join(REPO, "fleet", "gate_publish.py")

KEY_ID = "ctl-2026-09"
BOX_ID = "box-07"


def run(*argv, env_extra=None, check=False):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(argv, env=env, capture_output=True, text=True,
                          timeout=60, cwd=REPO)


@pytest.fixture()
def keyfile(tmp_path):
    p = tmp_path / "ctl.key"
    p.write_bytes(binascii.hexlify(os.urandom(32)))
    os.chmod(p, 0o600)
    return str(p)


@pytest.fixture()
def registry(tmp_path):
    reg = {
        "repo": {"max_permitted_commit": "a" * 40, "channel": "stable"},
        "toolset": {"max_permitted_pin": "2026.09.27", "channel": "stable"},
        "image": {"max_permitted_image_version": "2026.09.29-0",
                  "channel": "stable"},
    }
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(reg))
    return str(p)


@pytest.fixture()
def manifest(tmp_path):
    man = {
        comp: {"live": 2, "state": "wave-2",
               "assignments": {BOX_ID: 1}, "default": "hash_mod_4"}
        for comp in ("repo", "toolset", "image")
    }
    p = tmp_path / "waves.json"
    p.write_text(json.dumps(man))
    return str(p)


@pytest.fixture()
def hook_env(tmp_path, keyfile):
    """Env for a hermetic hook run: gate + status both under tmp."""
    gate = str(tmp_path / "gate.json")
    status = str(tmp_path / "gate" / "status.json")
    env = {
        "SPARKVM_BOX_ID": BOX_ID,
        "SPARKVM_GATE_KEYS": f"{KEY_ID}={keyfile}",
        "SPARKVM_GATE_JSON": gate,
        "SPARKVM_GATE_STATUS": status,
    }
    return env, gate, status


def publish(registry, manifest, keyfile, out, extra=()):
    r = run("python3", PUBLISH, "--registry", registry, "--manifest", manifest,
            "--key-id", KEY_ID, "--key-file", keyfile, "--out", out, *extra)
    assert r.returncode == 0, r.stderr
    return out


def read_status(status):
    with open(status, encoding="utf-8") as fh:
        return json.load(fh)


def test_hook_writes_live_status(hook_env, registry, manifest, keyfile):
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    doc = read_status(status)
    assert doc["schema_version"] == 1
    assert doc["source"] == "gate_hook"
    generated = datetime.strptime(doc["generated_at"], "%Y-%m-%dT%H:%M:%SZ")
    generated = generated.replace(tzinfo=timezone.utc)
    assert (datetime.now(timezone.utc) - generated).total_seconds() < 120
    ans = doc["answer"]
    assert ans["state"] == "live"
    assert ans["freeze"] == "false"
    assert ans["repo_permitted"] == "true"
    assert ans["repo_max"] == "a" * 40
    assert ans["key_id"] == KEY_ID
    # Atomic-write discipline: no temp residue left behind.
    assert not [p for p in os.listdir(os.path.dirname(status))
                if p.endswith(".tmp")]
    # The journal summary line names the answer.
    assert "gate_hook: state=live" in r.stderr


def test_hook_writes_frozen_on_missing_gate(hook_env):
    env, gate, status = hook_env  # gate.json never published
    r = run("bash", HOOK, env_extra=env)
    # A frozen fleet is the signal, not a hook failure: exit 0, answer kept.
    assert r.returncode == 0, r.stderr
    doc = read_status(status)
    ans = doc["answer"]
    assert ans["state"] == "frozen"
    assert ans["freeze"] == "true"
    assert ans["reason"].startswith("no-signal")
    assert "gate_hook: state=frozen" in r.stderr


def test_hook_writes_frozen_on_expired_gate(hook_env, registry, manifest,
                                            keyfile):
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate, extra=("--ttl-seconds", "1"))
    time.sleep(2)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    ans = read_status(status)["answer"]
    assert ans["state"] == "frozen"
    # gate_query.py's shipped reason vocabulary (S1a): the expiry surfaces
    # as a no-signal with the expiry detail, not the design doc's
    # aspirational `gate-expired` token.
    assert "expired" in ans["reason"] and "ttl=1s" in ans["reason"]


def test_hook_writes_frozen_on_freeze(hook_env, registry, manifest, keyfile):
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate, extra=("--freeze",))
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    ans = read_status(status)["answer"]
    assert ans["state"] == "frozen"
    assert ans["freeze"] == "true"
    assert "freeze" in ans["reason"]


def test_hook_reports_wave_not_live_per_component(hook_env, registry, keyfile,
                                                  tmp_path):
    env, gate, status = hook_env
    man = {"repo": {"live": 0, "state": "halted", "assignments": {},
                    "default": "hash_mod_4"}}
    for comp in ("toolset", "image"):
        man[comp] = {"live": 2, "state": "wave-2", "assignments": {BOX_ID: 1},
                     "default": "hash_mod_4"}
    mp = tmp_path / "halted.json"
    mp.write_text(json.dumps(man))
    publish(registry, str(mp), keyfile, gate)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    ans = read_status(status)["answer"]
    assert ans["state"] == "live"  # document valid, freeze off
    assert ans["repo_permitted"] == "false"
    assert ans["toolset_permitted"] == "true"


def test_hook_overwrites_stale_status(hook_env, registry, manifest, keyfile):
    env, gate, status = hook_env
    os.makedirs(os.path.dirname(status), exist_ok=True)
    with open(status, "w", encoding="utf-8") as fh:
        fh.write('{"stale": "sentinel"}\n')
    publish(registry, manifest, keyfile, gate)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    doc = read_status(status)
    assert "stale" not in doc
    assert doc["source"] == "gate_hook"


def test_hook_fails_loud_when_status_unwritable(hook_env, registry, manifest,
                                                keyfile):
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate)
    env = dict(env, SPARKVM_GATE_STATUS="/proc/1/status.json")
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode != 0
    assert "FAILED to write status file" in r.stderr


def test_hook_journal_line_scrubs_control_characters(hook_env):
    # gate_query.py echoes the key_id raw into its "cannot read key for
    # ..." no-signal reason, so a control-character-bearing key_id reaches
    # the hook's journal summary unescaped. The hook must scrub it (the S1a
    # log-channel rule: operator-controlled strings never reach the journal
    # raw). Non-vacuity: fails on the hook with the scrub removed.
    env, gate, status = hook_env
    env = dict(env, SPARKVM_GATE_KEYS="\x1b[31mRED\x1b[0m=/tmp/definitely-not-here.key")
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "\x1b" not in r.stderr
    # The summary is exactly one line (the trailing newline is the
    # terminator, not content) and still names the frozen answer.
    assert r.stderr.count("\n") == 1
    assert "gate_hook: state=frozen" in r.stderr
    assert read_status(status)["answer"]["state"] == "frozen"


def test_hook_passes_args_through_to_query(hook_env, registry, manifest,
                                           keyfile):
    # Flags (not env) for box identity: the hook passes them through.
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate)
    env = {k: v for k, v in env.items()
           if k not in ("SPARKVM_BOX_ID", "SPARKVM_GATE_KEYS",
                        "SPARKVM_GATE_JSON")}
    r = run("bash", HOOK, "--box-id", BOX_ID, "--keys",
            f"{KEY_ID}={keyfile}", "--gate", gate, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert read_status(status)["answer"]["state"] == "live"


def test_hook_status_file_flag_redirects(hook_env, registry, manifest, keyfile):
    """--status-file (space and equals forms) overrides SPARKVM_GATE_STATUS —
    the redirect is documented in usage but was untested."""
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate)
    d = os.path.dirname(status)
    space_target = os.path.join(d, "flag-space.json")
    r = run("bash", HOOK, "--status-file", space_target, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert read_status(space_target)["answer"]["state"] == "live"
    equals_target = os.path.join(d, "flag-equals.json")
    r = run("bash", HOOK, f"--status-file={equals_target}", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert read_status(equals_target)["answer"]["state"] == "live"
    assert not os.path.exists(status), "the env path must stay untouched"


def test_hook_failure_branch_scrubs_and_leaves_status_untouched(hook_env):
    """The query-failure path (rc != 0) scrubs its journal line like the
    success path and never touches a pre-existing status file."""
    env, gate, status = hook_env
    os.makedirs(os.path.dirname(status), exist_ok=True)
    sentinel = b'{"sentinel": true}\n'
    with open(status, "wb") as fh:
        fh.write(sentinel)
    # gate_query argparse-errors on the unknown flag, echoing it raw. The
    # bogus value carries REAL control characters (chr(), not backslash
    # escapes) so the scrub is genuinely exercised.
    bogus = "--bogus=" + chr(0x1B) + "[31mRED" + chr(0x0A) + "INJECTED"
    r = run("bash", HOOK, bogus, env_extra=env)
    assert r.returncode != 0
    assert "\x1b" not in r.stderr
    assert r.stderr.count("\n") == 1
    assert "status file NOT updated" in r.stderr
    with open(status, "rb") as fh:
        assert fh.read() == sentinel, "a failed tick must not rewrite the file"


def test_hook_rejects_empty_status_file(hook_env):
    env, gate, status = hook_env
    r = run("bash", HOOK, "--status-file", "", env_extra=env)
    assert r.returncode != 0
    assert "empty status file path" in r.stderr


def _parse_secs(value):
    value = value.strip()
    assert value.endswith("s"), f"expected seconds value, got {value!r}"
    return int(value[:-1])


def test_timer_cadence_within_design_window():
    # G18 §3: the hook loop runs every 60–120s. The timer expresses that as
    # a 90s base plus a one-sided 0–30s randomized delay (RandomizedDelaySec
    # never shortens the interval).
    cp = configparser.ConfigParser()
    cp.read(os.path.join(REPO, "deploy", "gate-hook.timer"))
    base = _parse_secs(cp["Timer"]["OnUnitActiveSec"])
    jitter = _parse_secs(cp["Timer"].get("RandomizedDelaySec", "0s"))
    assert 60 <= base - jitter, "fastest tick below the 60s design floor"
    assert base + jitter <= 120, "slowest tick above the 120s design ceiling"
    assert cp["Timer"].get("Persistent", "false").lower() == "false"
    assert cp["Timer"]["OnBootSec"] == "1min", \
        "first tick after boot must be pinned (no thundering-herd default)"


def test_service_unit_contract():
    # The hook runs as root (writes the root-owned gate dir), oneshot, from
    # the installed copy — never the checkout — and stays loud in the
    # journal. NoNewPrivileges: the hook gains nothing from root beyond the
    # status-file write.
    cp = configparser.ConfigParser()
    cp.read(os.path.join(REPO, "deploy", "gate-hook.service"))
    svc = cp["Service"]
    assert svc["Type"] == "oneshot"
    assert svc["User"] == "root"
    assert svc["NoNewPrivileges"] == "true"
    assert svc["ExecStart"] == \
        "/home/ntindle/.sparkvm-deploy/bin/gate_hook.sh"
    assert "checkout" not in svc["ExecStart"]
    assert svc["StandardOutput"] == "journal"
    assert svc["StandardError"] == "journal"


# --- #1649 S2 slice 3: the gate-answer journal producer ----------------------
# The hook appends one standard-shape `kind: gate-answer` row to the
# box-local `update-events.jsonl` (next to the status file) on each answer
# transition, plus an anchor row on the first tick. Unchanged answers stay
# journal-silent (the S1 noise discipline).

def read_journal(status):
    journal = os.path.join(os.path.dirname(status), "update-events.jsonl")
    if not os.path.exists(journal):
        return []
    with open(journal, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_hook_emits_anchor_row_on_first_tick(
        hook_env, registry, manifest, keyfile):
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    rows = read_journal(status)
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "gate-hook"
    assert row["component"] == "gate"
    assert row["kind"] == "gate-answer"
    assert row["outcome"] == "succeeded"  # live answer: "permitted"
    assert row["trigger"] == "gate"  # the gate trigger is S2-reserved (§2)
    assert row["reason"] == "gate ok"
    assert row["box_id"] == BOX_ID
    assert row["attested"] is False
    assert row["repo_max"] == "a" * 40
    assert row["toolset_max"] == "2026.09.27"
    assert row["image_max"] == "2026.09.29-0"
    # The journal is 0600 (the updater's state-dir contract).
    mode = stat.S_IMODE(os.stat(
        os.path.join(os.path.dirname(status), "update-events.jsonl")).st_mode)
    assert mode == 0o600


def test_hook_emits_nothing_when_answer_unchanged(
        hook_env, registry, manifest, keyfile):
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert len(read_journal(status)) == 1  # anchor only


def test_hook_emits_skipped_frozen_on_freeze_transition(
        hook_env, registry, manifest, keyfile):
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    publish(registry, manifest, keyfile, gate, extra=("--freeze",))
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    rows = read_journal(status)
    assert len(rows) == 2
    row = rows[1]
    assert row["outcome"] == "skipped-frozen"
    assert row["reason"] == "freeze flag set"
    assert row["trigger"] == "gate"


def test_hook_emits_succeeded_on_unfreeze_transition(
        hook_env, registry, manifest, keyfile):
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate, extra=("--freeze",))
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    rows = read_journal(status)
    assert len(rows) == 1 and rows[0]["outcome"] == "skipped-frozen"
    publish(registry, manifest, keyfile, gate)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    rows = read_journal(status)
    assert len(rows) == 2
    assert rows[1]["outcome"] == "succeeded"
    assert rows[1]["reason"] == "gate ok"


def test_hook_emits_on_reason_change_within_frozen(
        hook_env, registry, manifest, keyfile):
    # A reason change inside the frozen state (operator freeze -> no-signal)
    # is a genuine transition — the fleet must see it.
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate, extra=("--freeze",))
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert len(read_journal(status)) == 1
    # Break the key: the gate no longer verifies -> no-signal, still frozen.
    bad = dict(env)
    bad["SPARKVM_GATE_KEYS"] = f"{KEY_ID}={os.path.join(os.path.dirname(gate), 'nope.key')}"
    r = run("bash", HOOK, env_extra=bad)
    assert r.returncode == 0, r.stderr
    rows = read_journal(status)
    assert len(rows) == 2
    assert rows[1]["outcome"] == "skipped-frozen"
    assert rows[1]["reason"].startswith("no-signal:")


def test_hook_anchor_on_corrupt_previous_status(
        hook_env, registry, manifest, keyfile):
    # An undecodable status file is "no previous answer" -> anchor row.
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate)
    os.makedirs(os.path.dirname(status), exist_ok=True)
    with open(status, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    rows = read_journal(status)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "succeeded"


def test_hook_respects_event_journal_override(
        hook_env, registry, manifest, keyfile, tmp_path):
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate)
    custom = str(tmp_path / "custom-events.jsonl")
    env = dict(env, EVENT_JOURNAL=custom)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert os.path.exists(custom)
    with open(custom, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    assert len(rows) == 1
    assert rows[0]["kind"] == "gate-answer"
    # The default location stays untouched when overridden.
    default = os.path.join(os.path.dirname(status), "update-events.jsonl")
    assert not os.path.exists(default)


def test_hook_no_emit_when_query_fails(
        hook_env, registry, manifest, keyfile):
    # A failed tick writes no status file AND no journal row: the row must
    # always reflect a recorded answer, never a phantom. (A missing gate
    # file is NOT a failure — it yields a no-signal frozen answer, rc 0.)
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert len(read_journal(status)) == 1
    # gate_query argparse-errors on the unknown flag -> rc != 0.
    r = run("bash", HOOK, "--bogus-flag", env_extra=env)
    assert r.returncode != 0
    assert len(read_journal(status)) == 1


def test_hook_sustained_no_signal_emits_once(
        hook_env, registry, manifest, keyfile):
    # B1 (Product review): no-signal reasons embed a tick-growing age
    # counter ("expired 93s past ttl=300s"). The transition key normalizes
    # digit runs, so a sustained no-signal is ONE row, not one per tick.
    # Deterministic: plant a same-class, different-digits reason in the
    # previous status file — without the normalization the next tick would
    # emit (raw strings differ); with it, the tick stays silent.
    import time
    env, gate, status = hook_env
    publish(registry, manifest, keyfile, gate, extra=("--ttl-seconds", "1"))
    time.sleep(2)  # let the 1s-ttl gate expire
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    rows = read_journal(status)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "skipped-frozen"
    assert rows[0]["reason"].startswith("no-signal: gate document expired")
    # Same failure class, wildly different digits.
    doc = read_status(status)
    doc["answer"]["reason"] = \
        "no-signal: gate document expired 99999s past ttl=1s"
    tmp = status + ".plant"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    os.replace(tmp, status)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    assert len(read_journal(status)) == 1, \
        "sustained no-signal must not emit per tick"


def test_hook_row_matches_status_on_trailing_equals_value(
        hook_env, keyfile, tmp_path):
    # QA fidelity defect: the emit-side shell parse must match the python
    # split("=", 1) the transition gate and status writer use — a value
    # ending in `=` is data, not syntax. The row must reflect the recorded
    # answer byte-for-byte.
    env, gate, status = hook_env
    reg = {
        "repo": {"max_permitted_commit": "a" * 40, "channel": "stable"},
        "toolset": {"max_permitted_pin": "2026.09.27", "channel": "stable"},
        "image": {"max_permitted_image_version": "2026.09.29-0=",
                  "channel": "stable"},
    }
    regp = tmp_path / "registry.json"
    regp.write_text(json.dumps(reg))
    man = {
        comp: {"live": 2, "state": "wave-2",
               "assignments": {BOX_ID: 1}, "default": "hash_mod_4"}
        for comp in ("repo", "toolset", "image")
    }
    manp = tmp_path / "waves.json"
    manp.write_text(json.dumps(man))
    publish(str(regp), str(manp), keyfile, gate)
    r = run("bash", HOOK, env_extra=env)
    assert r.returncode == 0, r.stderr
    rows = read_journal(status)
    assert len(rows) == 1
    recorded = read_status(status)["answer"]["image_max"]
    assert recorded == "2026.09.29-0="
    assert rows[0]["image_max"] == recorded, \
        "the journal row must reflect the recorded answer"
