"""H4 provider interface: the provider-agnostic contract every sandbox-provider
driver implements.

This module is the executable form of the H4 first slice (BACKLOG.md: "the
provider-agnostic interface draft (provision/status/dial/ssh_info/destroy +
public_ingress: false)"). It reconciles the design corpus into one buildable
contract so the Fly driver (and any later driver) has a fixed target:

- `docs/HOSTED_SIGNUP_ONBOARDING.md` §6 (H3, PR #24): the original five verbs
  (`provision` / `status` / `dial` / `ssh_info` / `destroy`, `snapshot` later),
  `spec.network = {public_ingress: false}` with control-plane post-provision
  verification, the fixed MVP shape (Ubuntu 24.04, 8 vCPU / 15 GB / 250 GB),
  `ssh_info()` returning relay host/port + VM host-key fingerprint for
  pinning in the connection bundle (no blind TOFU).
- `docs/SUSPEND_WAKE_RESEARCH.md` "Recommendations: the H4 contract" (recs
  1-8): the state model, the `suspend()` verb, wake-wait `dial()` semantics
  with first-writer-wins dedup and the resume-failure taxonomy, destroy-wins
  transition rules, the capability flags (`supports_suspend`,
  memory-preservation axis per shape), disk-persistence-only guarantee,
  per-tenant `auto_resume` gate, and control-plane-owned idle detection.
- `docs/FLY_DRIVER_RESEARCH.md` F2: Fly's suspend (memory+rootfs snapshot,
  storage-only billing) vs stop (compute terminated, data volume kept);
  `status()` suspended ↔ Fly `suspended`, and the reference shape's suspend
  degrading to a cold stop under the hood.
- `docs/GPU_PATH_RESEARCH.md` H4 consequences: an **open** `gpu_class`
  shape descriptor (not a closed enum), the suspend-vs-park distinction,
  and `destroy` deleting volumes.
- C14/C15 (competitor deep-scan follow-ups): the control plane must expose
  stopped-state resource retention (disk) to billing — carried here as the
  `retention` descriptor on `BoxStatus`.
- #177 (lifecycle parity audit): pause/resume memory-preservation semantics
  — disk guaranteed, memory resume shape-dependent — carried as the
  `memory_resume` axis, never as a promise in the state name.
- H19 (#134): the provision-time credential-install injector runs *against*
  this interface; the golden-image manifest preflight
  (`harness/generate-image-manifest.sh` / `check-image-manifest.sh`) pins
  `image_version` on the provision spec.

Adjudications this module makes (the research docs defer these to "the H4
design loop" — this is that loop; each is cited so a later turn can amend):

1. **No `parked` state.** `FLY_DRIVER_RESEARCH.md` F2 mapped Fly `stop` to a
   contract-level `parked`. `SUSPEND_WAKE_RESEARCH.md` rec 1's mapping rule
   supersedes it: a driver-requested suspend *always* surfaces as
   `suspended`, regardless of the substrate mechanism (on the Fly reference
   shape that is a cold `stop` under the hood — the caller asked for suspend
   and the box will be woken, so it is `suspended`, not `stopped`).
   Warm-vs-cold is carried by the separate `memory_resume` axis, never by
   the state name. Park-as-idle-economics (terminate compute, keep the data
   volume, re-provision from the golden image on wake) is a control-plane
   composition for H13, not a driver-reported state.
2. **`degraded` is an orthogonal health flag**, not a lifecycle state
   (rec 1). H3 §6's `degraded` and the H15 signup UI's status mapping
   (`creating→provisioning`, `ready→live`) are UI-layer concerns; this
   module defines driver-level states, and documents the migration.
3. **Bounded-blocking `dial()`** (rec 5) over trigger-wake + poll-status:
   `dial()` triggers the wake if needed, blocks (bounded, explicit
   timeout) until `running`, then opens the stream — or raises a
   rec-2-taxonomy error within the timeout. A driver may implement the
   wait internally via trigger+poll, but may not push the poll loop onto
   callers.

What this module is NOT: not a driver (no Fly API calls — dry-run only
until the operator's spend-cap packet, NEEDS_USER.md), not the control
plane (idle detection, wave orchestration, and billing live there), and not
the provision-time injector (it consumes this interface).
"""

from __future__ import annotations

import enum
import typing
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------

class ProviderState(str, enum.Enum):
    """Driver-level lifecycle states for one tenant box (one lifecycle per
    vm_id).

    Migration from H3 §6's enum: ``creating`` → ``provisioning``,
    ``ready`` → ``running``, ``dead`` splits into ``failed`` (diagnosed,
    possibly retryable) and ``destroyed`` (terminal). ``degraded`` left
    H3's enum entirely — it is the orthogonal ``Health`` flag below.
    (SUSPEND_WAKE_RESEARCH.md rec 1.)
    """

    PROVISIONING = "provisioning"  # provision accepted; box not yet usable
    RUNNING = "running"            # usable; dial() opens a stream directly
    SUSPENDING = "suspending"      # transitional; suspend in flight
    SUSPENDED = "suspended"        # idle; disk guaranteed, memory per axis
    WAKING = "waking"              # transitional; wake in flight
    STOPPING = "stopping"          # transitional; provider-initiated stop
    STOPPED = "stopped"            # provider/operator stopped outside the
                                   # suspend path; dial() wakes via the wake
                                   # path (never an error)
    FAILED = "failed"              # diagnosed failure; driver may decline retry
    DESTROYED = "destroyed"        # terminal; volumes deleted


class Health(str, enum.Enum):
    """Orthogonal health flag. A box can be RUNNING+DEGRADED (usable but
    impaired) — health never masquerades as a lifecycle state."""

    OK = "ok"
    DEGRADED = "degraded"


class MemoryResume(str, enum.Enum):
    """The memory-preservation axis, reported per shape by the driver
    (SUSPEND_WAKE_RESEARCH.md rec 3; #177's memory-preservation semantics).

    This axis documents the *mechanism*, not a durability promise: warm
    resume is best-effort and time-bounded (snapshots age out), disk
    persistence is the only guarantee. The reference Fly shape
    (8 vCPU / 15 GB, over Fly's ≤4 GB suspend cap) is COLD_ONLY.
    """

    FULL = "full"          # memory snapshot restored (E2B-class)
    COLD_ONLY = "cold-only"  # wake is a cold start; disk state survives
    NONE = "none"          # provider has no suspend story at all


class RetentionKind(str, enum.Enum):
    """What survives in a non-running state, for the billing surface
    (C15: the control plane must expose stopped-state resource retention
    — disk — to billing)."""

    VOLUME = "volume"      # data volume retained (suspended/stopped)
    SNAPSHOT = "snapshot"  # snapshot retained (provider-dependent)
    NONE = "none"          # nothing retained (destroyed)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RetentionInfo:
    """Billing-facing retention descriptor for non-running states."""

    disk_gb_retained: int
    kind: RetentionKind
    storage_billable: bool  # suspended/stopped bill storage on Fly Machines


@dataclass(frozen=True)
class ProviderCapabilities:
    """Machine-readable capability flags (rec 3: prose documentation alone
    won't do — H13's idle economics branches on these in code)."""

    supports_suspend: bool
    memory_resume: MemoryResume
    # Provider suspend limits that shape the guarantee, e.g. Fly's ≤4 GB
    # memory-suspend cap. None = no published cap.
    max_suspend_memory_gb: int | None = None
    notes: str = ""  # free-text per-shape documentation


@dataclass(frozen=True)
class ProvisionSpec:
    """What the control plane asks for. Validated at construction: the
    `public_ingress: false` invariant (H3 §6) is fail-closed — a spec that
    asks for public ingress is rejected, not honored."""

    tenant_id: str
    cpus: int = 8
    ram_gb: int = 15
    disk_gb: int = 250
    # Open descriptor, NOT a closed enum (GPU_PATH_RESEARCH.md): any string
    # the driver understands ("none", "runpod-rtx4090", ...). None = CPU-only.
    gpu_class: str | None = None
    region: str = ""  # empty = operator-pinned default
    public_ingress: bool = False
    # Per-tenant gate: may inbound dials wake a suspended box at all?
    # (sandbox0's auto_resume pattern, rec 3; H13 chooses the default.)
    auto_resume: bool = True
    # Golden-image pin the injector preflights against
    # (harness/check-image-manifest.sh).
    image_version: str = ""

    def __post_init__(self) -> None:
        if self.public_ingress:
            raise ValueError(
                "public_ingress=True violates the H3 §6 network invariant: "
                "drivers MUST NOT expose any public inbound path to the VM"
            )
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        for name, value in (("cpus", self.cpus), ("ram_gb", self.ram_gb),
                            ("disk_gb", self.disk_gb)):
            if value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")


@dataclass(frozen=True)
class ProvisionResult:
    vm_id: str
    mgmt_endpoint: str
    capabilities: ProviderCapabilities


@dataclass(frozen=True)
class SshInfo:
    """The connection bundle. The VM host-key fingerprint is attested over
    the authenticated provisioning channel — the Muse pins it, no blind
    TOFU (H3 §6)."""

    relay_host: str
    relay_port: int
    vm_host_key_fingerprint: str


@dataclass(frozen=True)
class NetworkAttestation:
    """What the driver actually created, for the control plane's
    post-provision verification (H3 §6: the control plane verifies the
    no-public-ingress invariant — it cannot verify what it cannot see)."""

    public_ingress_observed: bool
    observed_ingress: tuple[str, ...] = ()

    def assert_isolated(self) -> None:
        if self.public_ingress_observed:
            raise ProviderError(
                ErrorKind.ATTESTATION_FAILED,
                f"driver attests public ingress {self.observed_ingress!r}: "
                "violates the H3 §6 network invariant",
            )


@dataclass(frozen=True)
class BoxStatus:
    vm_id: str
    state: ProviderState
    health: Health = Health.OK
    capabilities: ProviderCapabilities | None = None
    # Warm-vs-cold, meaningful only post-wake (rec 1). None = unknown / n/a.
    warm_resume: bool | None = None
    # Billing surface (C15). None only while provisioning/running.
    retention: RetentionInfo | None = None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ErrorKind(str, enum.Enum):
    UNSUPPORTED = "unsupported"            # provider has no such story
                                           # (e.g. suspend on TermSquad-class)
    NOT_RUNNABLE = "not-runnable"          # verb valid only on runnable boxes
    WAKE_FAILED = "wake-failed"            # resume attempt ended; box is back
                                           # in SUSPENDED — do NOT treat as
                                           # still in progress (rec 2)
    WAKE_TIMEOUT = "wake-timeout"          # wake accepted, still in flight —
                                           # poll and retry (rec 2)
    TERMINAL = "terminal"                  # verb refused: destroyed (or failed
                                           # where the driver declines retry)
    PROVISION_FAILED = "provision-failed"
    ATTESTATION_FAILED = "attestation-failed"
    INVALID_TRANSITION = "invalid-transition"


class ProviderError(Exception):
    def __init__(self, kind: ErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

# Every legal driver-reported transition. Absence = the driver must never
# report it (checked by check_transition; drivers map provider-native
# states onto this table, never extend it silently).
_TRANSITIONS: dict[ProviderState, frozenset[ProviderState]] = {
    ProviderState.PROVISIONING: frozenset({
        ProviderState.RUNNING, ProviderState.FAILED, ProviderState.DESTROYED,
    }),
    ProviderState.RUNNING: frozenset({
        ProviderState.SUSPENDING, ProviderState.STOPPING,
        ProviderState.FAILED, ProviderState.DESTROYED,
    }),
    ProviderState.SUSPENDING: frozenset({
        ProviderState.SUSPENDED, ProviderState.FAILED, ProviderState.DESTROYED,
    }),
    ProviderState.SUSPENDED: frozenset({
        ProviderState.WAKING, ProviderState.DESTROYED,
    }),
    ProviderState.WAKING: frozenset({
        # Resume failure returns to SUSPENDED (never terminal FAILED) —
        # the error surfaces on the failed dial(), rec 2.
        ProviderState.RUNNING, ProviderState.SUSPENDED,
        ProviderState.FAILED, ProviderState.DESTROYED,
    }),
    ProviderState.STOPPING: frozenset({
        ProviderState.STOPPED, ProviderState.FAILED, ProviderState.DESTROYED,
    }),
    ProviderState.STOPPED: frozenset({
        # dial() on a stopped box starts it through the wake path (rec 1).
        ProviderState.WAKING, ProviderState.DESTROYED,
    }),
    ProviderState.FAILED: frozenset({
        # Diagnosed, possibly retryable: the driver may retry the provision
        # sequence. Otherwise the only exit is destroy.
        ProviderState.PROVISIONING, ProviderState.DESTROYED,
    }),
    ProviderState.DESTROYED: frozenset(),  # terminal: no exits
}


def check_transition(old: ProviderState, new: ProviderState) -> None:
    """Raise ProviderError(INVALID_TRANSITION) unless old -> new is legal."""
    if new not in _TRANSITIONS[old]:
        raise ProviderError(
            ErrorKind.INVALID_TRANSITION,
            f"illegal provider state transition: {old.value} -> {new.value}",
        )


class DialAction(str, enum.Enum):
    OPEN = "open"                  # stream opens directly
    WAKE_THEN_OPEN = "wake-then-open"  # wake (bounded) then open
    REFUSE = "refuse"              # terminal: raise ProviderError(TERMINAL)


def dial_action(state: ProviderState) -> DialAction:
    """What dial() does for each state (rec 1 + rec 5).

    - provisioning: the deploy stream (H3 §6 provisioning sequence).
    - running: direct open.
    - suspended/waking: wake-wait (join an in-flight wake; first-writer-wins
      dedup is the driver's job, OpenKruise pattern).
    - suspending/stopping: a dial racing a transition queues behind it via
      the same dedup — never an error, never a second transition.
    - stopped: start through the wake path (never an error).
    - failed/destroyed: refuse (failed where the driver declines retry is
      terminal for dial; retry is a re-provision).
    """
    if state in (ProviderState.PROVISIONING, ProviderState.RUNNING):
        return DialAction.OPEN
    if state in (ProviderState.SUSPENDING, ProviderState.SUSPENDED,
                 ProviderState.WAKING, ProviderState.STOPPING,
                 ProviderState.STOPPED):
        return DialAction.WAKE_THEN_OPEN
    return DialAction.REFUSE


def suspend_allowed(state: ProviderState) -> bool:
    """suspend() is valid only on a runnable box (rec 2: suspend of a
    non-runnable box is an explicit driver error — silent no-ops hide
    broken idle detectors)."""
    return state == ProviderState.RUNNING


# ---------------------------------------------------------------------------
# Driver interface
# ---------------------------------------------------------------------------

class ProviderDriver(typing.Protocol):
    """The contract every provider driver implements.

    Threading/blocking: dial() and suspend() block bounded by their
    timeout_s; everything else returns promptly. Drivers must be safe to
    abandon in-flight transitions (destroy always wins, rec 2).
    """

    def provision(self, spec: ProvisionSpec) -> ProvisionResult:
        """Create the box. Returns once the box exists and is entering
        PROVISIONING (not once it is running — the control plane drives
        deploy over dial() and polls status())."""
        ...

    def status(self, vm_id: str) -> BoxStatus:
        """Current driver-level state. `warm_resume` is meaningful only
        post-wake; `retention` must be set for every non-running state
        (C15 billing surface)."""
        ...

    def suspend(self, vm_id: str, timeout_s: float = 120.0) -> None:
        """Idle primitive (H13's). Maps to the provider's best suspend
        (memory snapshot where supported, cold stop where not) and always
        surfaces as SUSPENDED per the mapping rule. Raises
        UNSUPPORTED where the provider has no suspend story (never a
        silent no-op) and NOT_RUNNABLE off RUNNING."""
        ...

    def dial(self, vm_id: str, timeout_s: float = 300.0) -> typing.BinaryIO:
        """Bounded-blocking wake-wait dial (rec 5): triggers the wake if
        the box needs one, blocks until RUNNING, then returns the
        bidirectional stream the control plane uses for the provisioning
        deploy and the ssh-gateway uses for tenant attach. Concurrent
        dials collapse to one wake (first-writer-wins). Raises
        WAKE_TIMEOUT while the wake is still in flight (poll and retry),
        WAKE_FAILED when the attempt ended (box back in SUSPENDED),
        TERMINAL on destroyed / declined-retry failed."""
        ...

    def ssh_info(self, vm_id: str) -> SshInfo:
        """The connection bundle: relay endpoint + attested VM host-key
        fingerprint."""
        ...

    def destroy(self, vm_id: str) -> None:
        """Terminal cleanup. Deletes the data volumes (GPU_PATH_RESEARCH:
        destroy must delete the network volume). Cancels any in-flight
        wake/suspend (destroy always wins; on Fly, stop-on-suspended
        discards the snapshot). Idempotent: destroying DESTROYED is a
        no-op success."""
        ...

    def attest_network_isolation(self, vm_id: str) -> NetworkAttestation:
        """What the driver actually created. The control plane calls
        attestation.assert_isolated() post-provision (H3 §6)."""
        ...

    def snapshot(self, vm_id: str, label: str) -> str:
        """Later verb (H3 §6; #47's verb list). The default raises
        UNSUPPORTED — a driver without a snapshot story must say so
        loudly, never silently no-op. Explicit subclasses inherit this
        default; structural implementers must define it (or the same)."""
        raise ProviderError(ErrorKind.UNSUPPORTED,
                            "driver has no snapshot story")
