"""Cross-component E2E for the rollout-controller lane (#1261).

The hermetic suites (test_plane_inventory, test_plane_waves,
test_plane_deploy) each cover one tool. Nothing pinned the SEAM they
share: S2's waves.json writer contract consumed by S4's deploy driver,
and S2's promote consuming S5's operator-observed event journal as its
bad-signal gate. This file walks the full operator loop on a temp store:

  register -> release -> canary-tenants -> assign -> deploy-record ->
  event-landed -> promote (pins + wave advance) -> halt ->
  rollback --dry-run (last_known_good target) -> bad-signal refusal.

Each test gets its own --store temp dir. Non-vacuity: the #1627 display
fix is neuter-pinned (see the inline note in
test_dry_run_gates_honest_without_live_wave); the bad-signal refusal
dies if promote stops reading the S5 journal.
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_INV = os.path.join(_HERE, "plane_inventory.py")
_WAVES = os.path.join(_HERE, "plane_waves.py")
_DEPLOY = os.path.join(_HERE, "plane_deploy.py")

_SHA_A = "aa" * 32
_SHA_B = "bb" * 32


def _run(cli, store, *argv):
    return subprocess.run([sys.executable, cli, "--store", store, *argv],
                          capture_output=True, text=True, timeout=60)


@pytest.fixture()
def store():
    with tempfile.TemporaryDirectory(prefix="plane-rollout-e2e-") as d:
        yield d


def _ok(proc):
    assert proc.returncode == 0, f"exit {proc.returncode}\n{proc.stderr}"
    return json.loads(proc.stdout)


def _setup(store, template="v1", dep="dep-1", sha=_SHA_A):
    """Register 3 planes (t1 x2, t2 x1) and pin a template release."""
    for plane, tenant in (("plane-a", "t1"), ("plane-b", "t2"),
                          ("plane-c", "t1")):
        _ok(_run(_INV, store, "register", "--plane", plane,
                 "--tenant", tenant))
    _ok(_run(_INV, store, "release", "--template", template,
             "--deployment-id", dep, "--worker-sha256", sha))


def _assign(store, template="v1", buckets=2):
    _ok(_run(_WAVES, store, "canary-tenants", "--add", "t1"))
    return _ok(_run(_WAVES, store, "assign", "--template", template,
                    "--buckets", str(buckets)))


def _land(store, plane, template="v1", dep="dep-1", sha=_SHA_A):
    _ok(_run(_INV, store, "deploy", "--plane", plane, "--template",
             template))
    _ok(_run(_INV, store, "event", "--plane-id", plane,
             "--kind", "deploy-landed", "--template", template,
             "--deployment-id", dep, "--worker-sha256", sha))


def test_full_rollout_e2e(store):
    """The whole operator loop composes: S2 assign -> S4 dry-run gate ->
    S5 event journal -> S2 promote reading it -> pins written."""
    _setup(store)
    assigned = _assign(store)
    assert assigned["live_wave"] == 0
    # canary tenant's planes land on wave 0; the rest distribute by hash
    assert assigned["assignments"]["plane-a"] == 0
    assert assigned["assignments"]["plane-c"] == 0

    # S4 reads S2's waves.json writer contract: canary plane is in the
    # live wave, the wave-1 plane is refused.
    dry = _ok(_run(_DEPLOY, store, "deploy", "--plane-id", "plane-a",
                   "--template", "v1", "--dry-run"))
    assert dry["gates"] == {"frozen": False, "live_wave": 0,
                            "in_live_wave": True}
    assert dry["deployment_id"] == "dep-1"
    refused = _run(_DEPLOY, store, "deploy", "--plane-id", "plane-b",
                   "--template", "v1", "--dry-run")
    assert refused.returncode != 0
    assert "not in the live wave" in refused.stderr

    # Land the canary wave on S5's operator-observed journal, then
    # promote: the D-RC-4 gate consumes that journal as good-signal.
    _land(store, "plane-a")
    _land(store, "plane-c")
    promoted = _ok(_run(_WAVES, store, "promote"))
    assert promoted["from_wave"] == 0 and promoted["to_wave"] == 1
    assert sorted(promoted["pins_written"]) == ["plane-a", "plane-c"]

    status = _ok(_run(_WAVES, store, "status"))
    assert status["rollout"]["live_wave"] == 1

    # Wave 1 is now live: the wave-1 plane passes the S4 gate.
    dry2 = _ok(_run(_DEPLOY, store, "deploy", "--plane-id", "plane-b",
                    "--template", "v1", "--dry-run"))
    assert dry2["gates"]["live_wave"] == 1
    assert dry2["gates"]["in_live_wave"] is True


def test_bad_signal_refuses_promote(store):
    """S2's promote must read S5's journal as its bad-signal gate (#1288):
    an unresolved deploy-failed on a live-wave plane refuses promotion."""
    _setup(store, template="v2", dep="dep-2", sha=_SHA_B)
    _assign(store, template="v2")
    _ok(_run(_INV, store, "event", "--plane-id", "plane-a",
             "--kind", "deploy-failed", "--template", "v2"))
    refused = _run(_WAVES, store, "promote")
    assert refused.returncode != 0
    assert "bad-signal" in refused.stderr
    # ...and a fresh landing heals it (the journal is the gate's input).
    _land(store, "plane-a", template="v2", dep="dep-2", sha=_SHA_B)
    _land(store, "plane-c", template="v2", dep="dep-2", sha=_SHA_B)
    promoted = _ok(_run(_WAVES, store, "promote"))
    assert promoted["to_wave"] == 1


def test_dry_run_gates_honest_without_live_wave(store):
    """#1627: with no live rollout the dry-run gates object must not
    claim the plane is in a live wave. Neuter: reverting the
    `live_wave is not None` derivation to the hardcoded True fails
    both asserts."""
    _setup(store)
    # Fresh store: no waves.json at all.
    dry = _ok(_run(_DEPLOY, store, "deploy", "--plane-id", "plane-a",
                   "--template", "v1", "--dry-run"))
    assert dry["gates"]["live_wave"] is None
    assert dry["gates"]["in_live_wave"] is False

    # Halted store: the rollout exists but no wave is live. Land the
    # canary and promote first so plane-a has a last_known_good pin —
    # the real operator sequence is halt-after-landing, then roll back.
    _assign(store)
    _land(store, "plane-a")
    _land(store, "plane-c")
    _ok(_run(_WAVES, store, "promote"))
    _ok(_run(_WAVES, store, "halt", "--reason", "e2e"))
    rb = _ok(_run(_DEPLOY, store, "rollback", "--plane-id", "plane-a",
                  "--dry-run"))
    assert rb["gates"]["live_wave"] is None
    assert rb["gates"]["in_live_wave"] is False


def test_rollback_dry_run_targets_last_known_good(store):
    """After S2's promote writes last_known_good pins, S4's rollback
    --dry-run must resolve the pin (release-record verified), not a
    floating template name."""
    _setup(store)
    _assign(store)
    _land(store, "plane-a")
    _land(store, "plane-c")
    _ok(_run(_WAVES, store, "promote"))
    _ok(_run(_WAVES, store, "halt", "--reason", "e2e"))
    rb = _ok(_run(_DEPLOY, store, "rollback", "--plane-id", "plane-a",
                  "--dry-run"))
    assert rb["deployment_id"] == "dep-1"
    assert rb["worker_sha256"] == _SHA_A
    assert rb["template_version"] == "v1"
    assert rb["gates"]["in_live_wave"] is False
