"""Contract tests for harness/provider_iface.py.

These test the CONTRACT, not any provider: the state machine, the dial /
suspend policies, the fail-closed spec validation, and a fake in-memory
driver that implements the full Protocol to prove the lifecycle is
exercisable end to end (provision -> running -> suspend -> suspended ->
dial/wake -> running -> destroy -> destroyed), including the rec-2
failure paths (resume failure returns to SUSPENDED; destroy wins races).
"""

import importlib.util
import io
import os
import sys

import pytest

HARNESS = os.path.dirname(os.path.abspath(__file__))


def load_iface():
    name = "provider_iface"
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(HARNESS, "provider_iface.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses resolves annotations via sys.modules
    spec.loader.exec_module(mod)
    return mod


pi = load_iface()
PS = pi.ProviderState


def make_spec(**kw):
    args = {"tenant_id": "t-1", "claim_id": "c-1", "image_version": "deadbeef"}
    args.update(kw)
    return pi.ProvisionSpec(**args)


# ---------------------------------------------------------------------------
# Spec validation: the public_ingress invariant is fail-closed
# ---------------------------------------------------------------------------

def test_public_ingress_true_rejected():
    with pytest.raises(ValueError, match="public_ingress"):
        make_spec(public_ingress=True)


def test_public_ingress_defaults_false():
    assert make_spec().public_ingress is False


def test_tenant_id_required():
    with pytest.raises(ValueError, match="tenant_id"):
        make_spec(tenant_id="")


def test_nonpositive_shape_rejected():
    with pytest.raises(ValueError):
        make_spec(cpus=0)


def test_gpu_class_is_open_descriptor():
    # Not a closed enum: any driver-understood string passes validation.
    assert make_spec(gpu_class="runpod-rtx4090").gpu_class == "runpod-rtx4090"
    assert make_spec(gpu_class=None).gpu_class is None


def test_auto_resume_gate_defaults_true():
    assert make_spec().auto_resume is True
    assert make_spec(auto_resume=False).auto_resume is False


# ---------------------------------------------------------------------------
# Network attestation: the control plane can verify what the driver made
# ---------------------------------------------------------------------------

def test_attestation_clean_passes():
    pi.NetworkAttestation(public_ingress_observed=False).assert_isolated()


def test_attestation_dirty_raises():
    with pytest.raises(pi.ProviderError) as exc:
        pi.NetworkAttestation(
            public_ingress_observed=True,
            observed_ingress=("0.0.0.0:22",)).assert_isolated()
    assert exc.value.kind == pi.ErrorKind.ATTESTATION_FAILED


def test_attestation_fails_closed_on_reported_endpoint():
    # A driver that reports an ingress endpoint with the flag False is
    # inconsistent — the enforcement point fails closed (QA B5).
    with pytest.raises(pi.ProviderError) as exc:
        pi.NetworkAttestation(
            public_ingress_observed=False,
            observed_ingress=("0.0.0.0:22",)).assert_isolated()
    assert exc.value.kind == pi.ErrorKind.ATTESTATION_FAILED


# ---------------------------------------------------------------------------
# State machine: every tabled transition legal, everything else refused
# ---------------------------------------------------------------------------

def test_all_tabled_transitions_legal():
    for old, news in pi._TRANSITIONS.items():
        for new in news:
            pi.check_transition(old, new)  # must not raise


def test_destroyed_is_terminal():
    assert pi._TRANSITIONS[PS.DESTROYED] == frozenset()
    for new in PS:
        with pytest.raises(pi.ProviderError) as exc:
            pi.check_transition(PS.DESTROYED, new)
        assert exc.value.kind == pi.ErrorKind.INVALID_TRANSITION


def test_no_direct_suspended_to_running():
    # Wake always passes through WAKING (dial) — no teleport.
    with pytest.raises(pi.ProviderError):
        pi.check_transition(PS.SUSPENDED, PS.RUNNING)


def test_resume_failure_returns_to_suspended():
    # Rec 2: a failed wake is not terminal — the box is back in SUSPENDED
    # and the error surfaced on the failed dial().
    pi.check_transition(PS.WAKING, PS.SUSPENDED)


def test_destroy_wins_from_every_live_state():
    for old in PS:
        if old is PS.DESTROYED:
            continue
        pi.check_transition(old, PS.DESTROYED)


def test_stopped_wakes_through_waking():
    pi.check_transition(PS.STOPPED, PS.WAKING)
    with pytest.raises(pi.ProviderError):
        pi.check_transition(PS.STOPPED, PS.RUNNING)


def test_failed_may_retry_provision_or_die():
    pi.check_transition(PS.FAILED, PS.PROVISIONING)
    pi.check_transition(PS.FAILED, PS.DESTROYED)
    with pytest.raises(pi.ProviderError):
        pi.check_transition(PS.FAILED, PS.RUNNING)


# ---------------------------------------------------------------------------
# dial() policy per state
# ---------------------------------------------------------------------------

def test_dial_opens_on_provisioning_and_running():
    # provisioning: the deploy stream (H3 §6 provisioning sequence).
    assert pi.dial_action(PS.PROVISIONING) == pi.DialAction.OPEN
    assert pi.dial_action(PS.RUNNING) == pi.DialAction.OPEN


def test_dial_wake_waits_on_idle_states():
    for s in (PS.SUSPENDING, PS.SUSPENDED, PS.WAKING, PS.STOPPING, PS.STOPPED):
        assert pi.dial_action(s) == pi.DialAction.WAKE_THEN_OPEN, s


def test_dial_refuses_terminal_states():
    assert pi.dial_action(PS.FAILED) == pi.DialAction.REFUSE
    assert pi.dial_action(PS.DESTROYED) == pi.DialAction.REFUSE


# ---------------------------------------------------------------------------
# suspend() policy
# ---------------------------------------------------------------------------

def test_suspend_only_on_running():
    assert pi.suspend_allowed(PS.RUNNING) is True
    for s in PS:
        if s is not PS.RUNNING:
            assert pi.suspend_allowed(s) is False, s


# ---------------------------------------------------------------------------
# A fake driver exercising the whole lifecycle through the Protocol
# ---------------------------------------------------------------------------

class FakeDriver:
    """In-memory driver implementing ProviderDriver. The fake honors the
    contract's transition table on every state change (a driver that
    reports an illegal transition is a contract violation).

    The fake also honors the D-O1 dedupe contract: provision() returns the
    existing box for a repeated idempotency key, and the key->vm_id map
    rides the shared `store` dict — the fake's stand-in for provider-side
    machine metadata. Two FakeDriver instances sharing one store simulate
    a driver process restart: the second instance rebuilds the map by
    listing, exactly as the contract requires."""

    def __init__(self, capabilities=None, store=None):
        self.store = store if store is not None else {}
        # Rebuild the live view from the provider-side store (fresh process
        # sees everything the previous one persisted).
        self.boxes = {vm_id: dict(rec) for vm_id, rec in self.store.items()}
        self.capabilities = capabilities or pi.ProviderCapabilities(
            supports_suspend=True,
            memory_resume=pi.MemoryResume.COLD_ONLY,  # Fly reference shape
            max_suspend_memory_gb=4,
            notes="fake: cold-stop-only like the Fly reference shape",
        )
        self.fail_next_wake = False
        self.stall_wake = False
        self.woke = set()  # vm_ids whose last RUNNING came from a wake

    def _persist(self, vm_id):
        # Write-through: the store is the provider-side truth a restarted
        # driver rebuilds from, so every mutation lands there.
        self.store[vm_id] = dict(self.boxes[vm_id])

    def _set(self, vm_id, new):
        old = self.boxes[vm_id]["state"]
        pi.check_transition(old, new)
        self.boxes[vm_id]["state"] = new
        self._persist(vm_id)

    def _retention_for(self, vm_id):
        """The contract: retention set for every non-running state (C15)."""
        st = self.boxes[vm_id]["state"]
        if st in (PS.PROVISIONING, PS.RUNNING):
            return None
        if st is PS.DESTROYED:
            return pi.RetentionInfo(
                disk_gb_retained=0, kind=pi.RetentionKind.NONE,
                storage_billable=False)
        return pi.RetentionInfo(
            disk_gb_retained=self.boxes[vm_id]["spec"].disk_gb,
            kind=pi.RetentionKind.VOLUME, storage_billable=True)

    def _check_timeout(self, timeout_s):
        if timeout_s <= 0:
            raise pi.ProviderError(pi.ErrorKind.INVALID_ARGUMENT,
                                   "timeout_s must be positive")

    def provision(self, spec):
        # D-O1 dedupe: a retry of the same idempotency key returns the
        # existing box — never a second box, never an error. Destroyed
        # boxes are not returned: a same-key provision after destroy is a
        # fresh provision (the orchestrator only reuses a key for a retry,
        # never across a supersede — that increments attempt_n).
        key = spec.idempotency_key
        for vm_id, box in self.boxes.items():
            old_spec = box.get("spec")
            if (box["state"] is not PS.DESTROYED and old_spec is not None
                    and old_spec.idempotency_key == key):
                return box["result"]
        vm_id = f"vm-{spec.tenant_id}-{spec.claim_id}-a{spec.attempt_n}"
        result = pi.ProvisionResult(
            vm_id=vm_id, mgmt_endpoint="mgmt.example.invalid",
            capabilities=self.capabilities)
        self.boxes[vm_id] = {"state": PS.PROVISIONING, "spec": spec,
                             "result": result}
        self._persist(vm_id)
        # A re-provisioned box has no wake history (Engineering round 2 B1:
        # vm_ids are deterministic, so stale wake_kind would otherwise leak
        # across the destroy/re-provision boundary).
        self.woke.discard(vm_id)
        return result

    def status(self, vm_id):
        st = self.boxes[vm_id]["state"]
        caps = self.capabilities
        # FLY F2: surface which resume path the last wake took.
        wake_kind = None
        if vm_id in self.woke and st is PS.RUNNING:
            if caps.wake_reprovisions:
                wake_kind = pi.WakeKind.REPROVISIONED
            elif caps.memory_resume == pi.MemoryResume.FULL:
                wake_kind = pi.WakeKind.WARM
            else:
                wake_kind = pi.WakeKind.COLD
        return pi.BoxStatus(vm_id=vm_id, state=st,
                            capabilities=caps,
                            retention=self._retention_for(vm_id),
                            wake_kind=wake_kind)

    def suspend(self, vm_id, timeout_s=120.0):
        self._check_timeout(timeout_s)
        if not self.capabilities.supports_suspend:
            raise pi.ProviderError(pi.ErrorKind.UNSUPPORTED,
                                   "no suspend story")
        if not pi.suspend_allowed(self.boxes[vm_id]["state"]):
            raise pi.ProviderError(pi.ErrorKind.NOT_RUNNABLE,
                                   "suspend of non-runnable box")
        self._set(vm_id, PS.SUSPENDING)
        self._set(vm_id, PS.SUSPENDED)

    def dial(self, vm_id, timeout_s=300.0):
        self._check_timeout(timeout_s)
        st = self.boxes[vm_id]["state"]
        # Queue behind an in-flight transition: complete it instantly,
        # then proceed down the wake path — never an error, never a
        # second transition (dial_action contract for racing dials).
        if st is PS.SUSPENDING:
            self._set(vm_id, PS.SUSPENDED)
        elif st is PS.STOPPING:
            self._set(vm_id, PS.STOPPED)
        action = pi.dial_action(self.boxes[vm_id]["state"])
        if action == pi.DialAction.REFUSE:
            raise pi.ProviderError(pi.ErrorKind.TERMINAL,
                                   "dial on terminal box")
        if action == pi.DialAction.WAKE_THEN_OPEN:
            if not self.boxes[vm_id]["spec"].auto_resume:
                raise pi.ProviderError(pi.ErrorKind.TERMINAL,
                                       "auto_resume gate closed")
            # Join or start the wake; first-writer-wins dedup.
            if self.boxes[vm_id]["state"] != PS.WAKING:
                self._set(vm_id, PS.WAKING)
            if self.stall_wake:
                # Wake still in flight: poll and retry (rec 2 taxonomy).
                raise pi.ProviderError(pi.ErrorKind.WAKE_TIMEOUT,
                                       "wake in flight")
            if self.fail_next_wake:
                self.fail_next_wake = False
                # Rec 2: back to SUSPENDED, error on the failed dial().
                self._set(vm_id, PS.SUSPENDED)
                raise pi.ProviderError(pi.ErrorKind.WAKE_FAILED,
                                       "resume attempt ended")
            self._set(vm_id, PS.RUNNING)
            self.woke.add(vm_id)
        return io.BytesIO(b"")

    def ssh_info(self, vm_id):
        return pi.SshInfo(relay_host="relay.example.invalid", relay_port=2222,
                          vm_host_key_fingerprint="SHA256:fake")

    def destroy(self, vm_id):
        # Idempotent; destroy always wins (no transition check — terminal
        # cleanup cancels in-flight transitions by definition). Clears wake
        # history with the box (Engineering round 2 B1).
        if vm_id in self.boxes:
            self.boxes[vm_id]["state"] = PS.DESTROYED
            self._persist(vm_id)
        self.woke.discard(vm_id)

    def list_boxes(self):
        # D-O1: the provider-side listing the orchestrator's startup
        # reconcile matches against. Destroyed boxes no longer exist on the
        # provider, so they are not listed. A record with spec None is a
        # pre-D-O1 box (provider metadata without the claim-bound key) —
        # it lists with idempotency_key None rather than raising or
        # inventing a key, so the reconcile can ignore it honestly.
        out = []
        for vm_id, box in self.boxes.items():
            if box["state"] is PS.DESTROYED:
                continue
            spec = box.get("spec")
            key = spec.idempotency_key if spec is not None else None
            out.append(pi.BoxIdentity(vm_id=vm_id, idempotency_key=key,
                                      state=box["state"]))
        return out

    def attest_network_isolation(self, vm_id):
        return pi.NetworkAttestation(public_ingress_observed=False)

    def snapshot(self, vm_id, label):
        # Structural implementers don't inherit the Protocol default —
        # they define the loud UNSUPPORTED themselves, like a real driver
        # without a snapshot story would.
        raise pi.ProviderError(pi.ErrorKind.UNSUPPORTED,
                               "driver has no snapshot story")


def test_full_lifecycle_fake_driver():
    d = FakeDriver()
    res = d.provision(make_spec())
    assert d.status(res.vm_id).state == PS.PROVISIONING
    # Deploy stream opens during provisioning (H3 §6).
    d.dial(res.vm_id).close()
    d._set(res.vm_id, PS.RUNNING)

    d.suspend(res.vm_id)
    st = d.status(res.vm_id)
    assert st.state == PS.SUSPENDED
    # C15: the billing surface sees the retained disk.
    assert st.retention is not None
    assert st.retention.disk_gb_retained == 250
    assert st.retention.storage_billable is True
    # #177: disk guaranteed; memory resume is the shape's axis, not a promise.
    assert st.capabilities.memory_resume == pi.MemoryResume.COLD_ONLY

    d.dial(res.vm_id).close()  # wake-wait dial
    assert d.status(res.vm_id).state == PS.RUNNING

    d.attest_network_isolation(res.vm_id).assert_isolated()
    info = d.ssh_info(res.vm_id)
    assert info.vm_host_key_fingerprint.startswith("SHA256:")

    d.destroy(res.vm_id)
    assert d.status(res.vm_id).state == PS.DESTROYED
    d.destroy(res.vm_id)  # idempotent
    with pytest.raises(pi.ProviderError) as exc:
        d.dial(res.vm_id)
    assert exc.value.kind == pi.ErrorKind.TERMINAL


def test_destroy_never_provisioned_id_is_noop():
    # Idempotency extends to unknown ids (control-plane retry safety).
    FakeDriver().destroy("vm-nope")


def test_wake_failure_returns_to_suspended_not_terminal():
    d = FakeDriver()
    res = d.provision(make_spec())
    d._set(res.vm_id, PS.RUNNING)
    d.suspend(res.vm_id)
    d.fail_next_wake = True
    with pytest.raises(pi.ProviderError) as exc:
        d.dial(res.vm_id)
    assert exc.value.kind == pi.ErrorKind.WAKE_FAILED
    # Box is back in SUSPENDED — retryable, not dead.
    assert d.status(res.vm_id).state == PS.SUSPENDED
    d.dial(res.vm_id).close()
    assert d.status(res.vm_id).state == PS.RUNNING


def test_suspend_unsupported_driver_raises_not_silent():
    d = FakeDriver(capabilities=pi.ProviderCapabilities(
        supports_suspend=False, memory_resume=pi.MemoryResume.NONE))
    res = d.provision(make_spec())
    d._set(res.vm_id, PS.RUNNING)
    with pytest.raises(pi.ProviderError) as exc:
        d.suspend(res.vm_id)
    assert exc.value.kind == pi.ErrorKind.UNSUPPORTED
    assert d.status(res.vm_id).state == PS.RUNNING  # untouched


def test_suspend_non_runnable_is_driver_error():
    d = FakeDriver()
    res = d.provision(make_spec())
    d._set(res.vm_id, PS.RUNNING)
    d.suspend(res.vm_id)
    with pytest.raises(pi.ProviderError) as exc:
        d.suspend(res.vm_id)  # already suspended: no silent no-op
    assert exc.value.kind == pi.ErrorKind.NOT_RUNNABLE


def test_auto_resume_gate_closed_refuses_dial():
    d = FakeDriver()
    res = d.provision(make_spec(auto_resume=False))
    d._set(res.vm_id, PS.RUNNING)
    d.suspend(res.vm_id)
    with pytest.raises(pi.ProviderError) as exc:
        d.dial(res.vm_id)
    assert exc.value.kind == pi.ErrorKind.TERMINAL
    assert d.status(res.vm_id).state == PS.SUSPENDED


def test_dial_racing_suspend_queues_behind():
    # QA B1: a dial racing the suspend transition queues behind it —
    # never an error, never a second transition.
    d = FakeDriver()
    res = d.provision(make_spec())
    d._set(res.vm_id, PS.RUNNING)
    d._set(res.vm_id, PS.SUSPENDING)  # transition in flight
    d.dial(res.vm_id).close()
    assert d.status(res.vm_id).state == PS.RUNNING


def test_dial_racing_stop_queues_behind():
    d = FakeDriver()
    res = d.provision(make_spec())
    d._set(res.vm_id, PS.RUNNING)
    d._set(res.vm_id, PS.STOPPING)  # transition in flight
    d.dial(res.vm_id).close()
    assert d.status(res.vm_id).state == PS.RUNNING


def test_wake_timeout_poll_and_retry():
    # QA B3: the rec-2 in-flight path — WAKE_TIMEOUT while the wake is
    # still in flight, then poll-and-retry reaches RUNNING.
    d = FakeDriver()
    res = d.provision(make_spec())
    d._set(res.vm_id, PS.RUNNING)
    d.suspend(res.vm_id)
    d.stall_wake = True
    with pytest.raises(pi.ProviderError) as exc:
        d.dial(res.vm_id)
    assert exc.value.kind == pi.ErrorKind.WAKE_TIMEOUT
    assert d.status(res.vm_id).state == PS.WAKING  # still in flight
    d.stall_wake = False
    d.dial(res.vm_id).close()  # the retry joins the same wake
    assert d.status(res.vm_id).state == PS.RUNNING


def test_retention_set_for_every_non_running_state():
    # QA B2: the C15 billing surface — retention present everywhere the
    # box isn't provisioning/running, explicit NONE once destroyed.
    d = FakeDriver()
    res = d.provision(make_spec())
    for st in PS:
        d.boxes[res.vm_id]["state"] = st  # direct set: test the reporter
        got = d.status(res.vm_id).retention
        if st in (PS.PROVISIONING, PS.RUNNING):
            assert got is None, st
        else:
            assert got is not None, st
    destroyed = d.status(res.vm_id).retention
    # (state is DESTROYED from the loop above)
    assert destroyed.kind == pi.RetentionKind.NONE
    assert destroyed.disk_gb_retained == 0
    assert destroyed.storage_billable is False


def test_snapshot_default_is_loud_unsupported():
    d = FakeDriver()
    res = d.provision(make_spec())
    with pytest.raises(pi.ProviderError) as exc:
        d.snapshot(res.vm_id, "pre-upgrade")
    assert exc.value.kind == pi.ErrorKind.UNSUPPORTED


def test_protocol_default_snapshot_raises_unsupported():
    # Explicit subclasses inherit the loud default.
    class BareDriver(pi.ProviderDriver):
        def provision(self, spec): ...
        def status(self, vm_id): ...
        def suspend(self, vm_id, timeout_s=120.0): ...
        def dial(self, vm_id, timeout_s=300.0): ...
        def ssh_info(self, vm_id): ...
        def destroy(self, vm_id): ...
        def attest_network_isolation(self, vm_id): ...

    with pytest.raises(pi.ProviderError) as exc:
        BareDriver().snapshot("vm-x", "label")
    assert exc.value.kind == pi.ErrorKind.UNSUPPORTED


def test_wake_kind_surfaces_resume_path():
    # FLY F2 (Architecture Blocking 1): the driver surfaces which resume
    # path the last wake took, so the control plane can distinguish wake
    # from park-reset.
    cases = [
        # (capabilities, expected wake_kind)
        (pi.ProviderCapabilities(supports_suspend=True,
                                 memory_resume=pi.MemoryResume.COLD_ONLY),
         pi.WakeKind.COLD),
        (pi.ProviderCapabilities(supports_suspend=True,
                                 memory_resume=pi.MemoryResume.FULL),
         pi.WakeKind.WARM),
        (pi.ProviderCapabilities(supports_suspend=True,
                                 memory_resume=pi.MemoryResume.COLD_ONLY,
                                 wake_reprovisions=True),
         pi.WakeKind.REPROVISIONED),  # RunPod-style: suspend is park
    ]
    for i, (caps, expected) in enumerate(cases):
        d = FakeDriver(capabilities=caps)
        res = d.provision(make_spec(tenant_id=f"t-wake-{i}"))
        assert d.status(res.vm_id).wake_kind is None  # no wake yet
        d._set(res.vm_id, PS.RUNNING)
        d.suspend(res.vm_id)
        d.dial(res.vm_id).close()
        got = d.status(res.vm_id)
        assert got.state == PS.RUNNING
        assert got.wake_kind == expected, (caps, expected)
        assert got.capabilities.wake_reprovisions == (expected ==
                                                      pi.WakeKind.REPROVISIONED)


def test_wake_kind_cleared_on_destroy_and_reprovision():
    # Engineering round 2 B1: vm_ids are deterministic, so wake history
    # must not leak across the destroy/re-provision boundary — a
    # control plane trusting a stale REPROVISIONED could wrongly assume
    # (or skip) a bootstrap re-run.
    d = FakeDriver(capabilities=pi.ProviderCapabilities(
        supports_suspend=True, memory_resume=pi.MemoryResume.COLD_ONLY,
        wake_reprovisions=True))
    res = d.provision(make_spec(tenant_id="t-reprov"))
    d._set(res.vm_id, PS.RUNNING)
    d.suspend(res.vm_id)
    d.dial(res.vm_id).close()
    assert d.status(res.vm_id).wake_kind == pi.WakeKind.REPROVISIONED
    d.destroy(res.vm_id)
    assert d.status(res.vm_id).wake_kind is None
    res2 = d.provision(make_spec(tenant_id="t-reprov"))  # same vm_id
    assert res2.vm_id == res.vm_id
    d._set(res2.vm_id, PS.RUNNING)  # deploy, no wake
    assert d.status(res2.vm_id).wake_kind is None


def test_warm_resume_property():
    d = FakeDriver()
    res = d.provision(make_spec())
    st = d.status(res.vm_id)
    assert st.warm_resume is None  # no wake yet
    assert pi.BoxStatus(vm_id="x", state=PS.RUNNING,
                        wake_kind=pi.WakeKind.WARM).warm_resume is True
    assert pi.BoxStatus(vm_id="x", state=PS.RUNNING,
                        wake_kind=pi.WakeKind.COLD).warm_resume is False
    assert pi.BoxStatus(vm_id="x", state=PS.RUNNING,
                        wake_kind=pi.WakeKind.REPROVISIONED).warm_resume is False


def test_illegal_transition_never_reported_even_by_fake():
    d = FakeDriver()
    res = d.provision(make_spec())
    with pytest.raises(pi.ProviderError) as exc:
        d._set(res.vm_id, PS.SUSPENDED)  # provisioning -> suspended: illegal
    assert exc.value.kind == pi.ErrorKind.INVALID_TRANSITION


def test_self_transitions_refused():
    # A driver mapping noisy provider states must not rely on self-loops:
    # the table has no reflexive entries, so refresh-style reports must
    # map to a real transition or be absorbed by the driver.
    for st in PS:
        with pytest.raises(pi.ProviderError) as exc:
            pi.check_transition(st, st)
        assert exc.value.kind == pi.ErrorKind.INVALID_TRANSITION


def test_no_parked_state():
    # Adjudication 1: warm-vs-cold lives on the memory_resume axis, never
    # in the state name — there is no `parked`.
    assert "parked" not in {s.value for s in PS}


def test_degraded_is_health_not_lifecycle():
    # Adjudication 2: `degraded` is an orthogonal health flag, not a
    # lifecycle state — and it carries no dial/lifecycle semantics.
    assert "degraded" not in {s.value for s in PS}
    d = FakeDriver()
    res = d.provision(make_spec())
    st = d.status(res.vm_id)
    assert st.health == pi.Health.OK
    degraded = pi.BoxStatus(
        vm_id=res.vm_id, state=PS.RUNNING, health=pi.Health.DEGRADED,
        capabilities=d.capabilities)
    assert pi.dial_action(degraded.state) == pi.DialAction.OPEN
    assert pi.suspend_allowed(degraded.state) is True


def test_error_taxonomy_pinned():
    # QA N1: the rec-2 taxonomy is the contract's vocabulary — renames
    # break loudly.
    assert {k.name for k in pi.ErrorKind} == {
        "INVALID_TRANSITION", "UNSUPPORTED", "WAKE_FAILED", "WAKE_TIMEOUT",
        "TERMINAL", "NOT_RUNNABLE", "ATTESTATION_FAILED", "INVALID_ARGUMENT", "PROVISION_FAILED",
    }
    # Same rename-breaks-loudly protection for the F2 resume-path surface
    # (QA round-2 discrimination note).
    assert {k.name: k.value for k in pi.WakeKind} == {
        "WARM": "warm", "COLD": "cold", "REPROVISIONED": "reprovisioned",
    }


def test_nonpositive_timeout_rejected():
    d = FakeDriver()
    res = d.provision(make_spec())
    d._set(res.vm_id, PS.RUNNING)
    for bad in (0, -1.5):
        with pytest.raises(pi.ProviderError) as exc:
            d.suspend(res.vm_id, timeout_s=bad)
        assert exc.value.kind == pi.ErrorKind.INVALID_ARGUMENT
        with pytest.raises(pi.ProviderError) as exc:
            d.dial(res.vm_id, timeout_s=bad)
        assert exc.value.kind == pi.ErrorKind.INVALID_ARGUMENT


# ---------------------------------------------------------------------------
# Claim binding: the idempotency key (D-O1, #1107)
# ---------------------------------------------------------------------------

def test_claim_id_required():
    # Like tenant_id: absent -> rejected at construction (TypeError for the
    # missing positional, ValueError for the present-but-empty string).
    with pytest.raises(TypeError):
        pi.ProvisionSpec(tenant_id="t-1")
    with pytest.raises(ValueError):
        make_spec(claim_id="")


def test_attempt_n_must_be_positive():
    assert make_spec().attempt_n == 1  # first attempt is the default
    for bad in (0, -1):
        with pytest.raises(ValueError):
            make_spec(attempt_n=bad)


def test_idempotency_key_shape():
    # The key is the full (tenant_id, claim_id, attempt_n) triple — the
    # attempt is load-bearing: D-O3's re-provision writes attempt_n with a
    # fresh pairing token, so a claim-scoped key would hand back attempt
    # 1's box (whose env holds the superseded token) for attempt n.
    assert make_spec().idempotency_key == ("t-1", "c-1", 1)
    assert make_spec(attempt_n=3).idempotency_key == ("t-1", "c-1", 3)
    assert (make_spec(claim_id="c-2").idempotency_key
            != make_spec(claim_id="c-1").idempotency_key)


def test_provision_dedupe_same_attempt_returns_existing():
    # D-O1: retry of the same attempt returns the existing box — never a
    # second box, never an error (the crash window between provision() and
    # the orchestrator recording the result).
    d = FakeDriver()
    spec = make_spec()
    first = d.provision(spec)
    second = d.provision(make_spec())  # rebuilt spec, same key
    assert second.vm_id == first.vm_id
    assert second.mgmt_endpoint == first.mgmt_endpoint
    assert second is first  # dedupe returns the EXISTING result object —
    # without the dedupe branch the fake would build a second result
    # (same deterministic vm_id, same dict key), and this fails.
    assert len(d.list_boxes()) == 1


def test_provision_new_attempt_new_box():
    # A new attempt_n is a different key -> a different box (D-O3's
    # re-provision with a fresh attestation token).
    d = FakeDriver()
    first = d.provision(make_spec())
    second = d.provision(make_spec(attempt_n=2))
    assert second.vm_id != first.vm_id
    assert len(d.list_boxes()) == 2


def test_provision_dedupe_survives_driver_restart():
    # The key->vm_id map must survive driver restarts: the key rides
    # provider-side metadata, and a fresh driver process rebuilds the map
    # by listing. Two FakeDriver instances over one store simulate the
    # restart; the retry must still dedupe to the one existing box.
    store = {}
    d1 = FakeDriver(store=store)
    spec = make_spec(claim_id="c-restart")
    first = d1.provision(spec)
    # A second, fresh driver process sees the provider-side store.
    d2 = FakeDriver(store=store)
    listed = d2.list_boxes()
    assert [b.vm_id for b in listed] == [first.vm_id]
    assert listed[0].idempotency_key == spec.idempotency_key
    assert listed[0].state == PS.PROVISIONING
    second = d2.provision(make_spec(claim_id="c-restart"))
    assert second.vm_id == first.vm_id
    assert second is first  # the retry deduped to the pre-restart result —
    # without the dedupe branch the fresh driver would build a second
    # result object for the same key, and this fails.
    assert len(d2.list_boxes()) == 1  # still exactly one box for the claim


def test_list_boxes_hides_destroyed():
    d = FakeDriver()
    ra = d.provision(make_spec(claim_id="c-a"))
    rb = d.provision(make_spec(claim_id="c-b"))
    assert {box.vm_id for box in d.list_boxes()} == {ra.vm_id, rb.vm_id}
    d.destroy(ra.vm_id)
    remaining = d.list_boxes()
    assert [box.vm_id for box in remaining] == [rb.vm_id]
    assert remaining[0].idempotency_key == ("t-1", "c-b", 1)


def test_provision_after_destroy_same_key_creates_fresh():
    # Destroyed boxes are not returned by dedupe: a same-key provision
    # after destroy is a fresh provision (deterministic vm_id, no wake
    # history, back in PROVISIONING).
    d = FakeDriver()
    spec = make_spec(claim_id="c-reprov")
    first = d.provision(spec)
    d._set(first.vm_id, PS.RUNNING)
    d.destroy(first.vm_id)
    second = d.provision(make_spec(claim_id="c-reprov"))
    assert second.vm_id == first.vm_id
    assert d.status(second.vm_id).state == PS.PROVISIONING
    assert len(d.list_boxes()) == 1


def test_list_boxes_surfaces_pre_d01_box_with_none_key():
    # BoxIdentity's contract: a box that predates the D-O1 regime lists
    # with idempotency_key None — never raising, never an invented key.
    # A store record with spec None stands in for provider metadata that
    # carries no claim-bound key (what a real driver reads from a machine
    # created before the key existed).
    d = FakeDriver(store={"vm-old": {"state": PS.RUNNING, "spec": None,
                                     "result": None}})
    listed = d.list_boxes()
    assert len(listed) == 1
    assert listed[0].vm_id == "vm-old"
    assert listed[0].idempotency_key is None
    assert listed[0].state == PS.RUNNING
    # And a legacy box never dedupes against a claim-bound retry: a
    # provision with any key creates a fresh box rather than returning it.
    res = d.provision(make_spec(claim_id="c-new"))
    assert res.vm_id != "vm-old"
    assert len(d.list_boxes()) == 2


def test_list_boxes_unsupported_default():
    # Explicit subclasses inherit the loud default (evolution policy:
    # never a silent empty list from a driver that cannot list).
    class BareDriver(pi.ProviderDriver):
        def provision(self, spec): ...
        def status(self, vm_id): ...
        def suspend(self, vm_id, timeout_s=120.0): ...
        def dial(self, vm_id, timeout_s=300.0): ...
        def ssh_info(self, vm_id): ...
        def destroy(self, vm_id): ...
        def attest_network_isolation(self, vm_id): ...

    with pytest.raises(pi.ProviderError) as exc:
        BareDriver().list_boxes()
    assert exc.value.kind == pi.ErrorKind.UNSUPPORTED
