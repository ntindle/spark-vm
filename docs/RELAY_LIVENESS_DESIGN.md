# Relay session-liveness design (Q6 — `connection-unreachable`'s missing producer)

The tenant-status vocabulary (`docs/TENANT_STATUS_ENDPOINT.md` §2) has a
`connection-unreachable` code — "Relay/cert path failed while the poll
says otherwise" (`docs/FIRST_TEN_MINUTES_SPEC.md` §8) — whose producer
was always a placeholder: "Control-plane/relay defect instrumentation".
No relay doc existed, no liveness signal existed, no producer existed.
`docs/STUCK_DETECTOR_DESIGN.md` §8 Q6 named this the wiring gap and its
predicate drops the relay conjunct rather than faking it. This doc is
the missing design: what a relay session frame is, who emits liveness,
and how the control plane observes the path without any inbound path to
the VM (`spec.network = {public_ingress: false}`, enforced at
`harness/provider_iface.py` `ProvisionSpec.__post_init__`).

## 1. What the relay is

The H4 contract (`harness/provider_iface.py`): `ssh_info()` returns the
relay host/port plus the VM host-key fingerprint for pinning in the
connection bundle (no blind TOFU). The tenant Muse's SSH rides the
**relay** — a control-plane component that splices the tenant-side
session onto the private provider leg to the VM. `public_ingress` is a
hard invariant: no public inbound path to the VM may exist. The relay
listener is the only network surface the tenant ever touches; the
relay→VM leg is the private provider path (the same path `dial()` and
provisioning use).

## 2. Session frames — the observation unit

A **session frame** is one observation record of tenant↔VM SSH traffic at
the relay's splice point. The relay daemon is the only honest emitter:
it owns the splice point, it is control-plane-observed by construction,
and neither the box (no inbound) nor the tenant's Muse (cooperative —
`docs/SENTINEL_TELEMETRY_SURFACES.md` S3: agent-forgeable) can produce a
trusted record.

Frame fields (metadata only — timing and counters, never payload,
mirroring `docs/USAGE_METERING_DESIGN.md`'s counters-over-content rule):

| Field | Meaning |
|---|---|
| `session_id` | Opaque, control-plane-minted per SSH session |
| `tenant_id` / `vm_id` | Ownership (per-box; see §9 Q2 for the G7 follow-up) |
| `opened_at` | SSH transport handshake completed through the relay |
| `last_bytes_at` | Last observed byte in either direction |
| `closed_at` / `close_cause` | `client_closed` \| `relay_closed` \| `idle_timeout` \| `box_leg_lost` \| `handshake_failed` |
| `hostkey_verified` | Pinned fingerprint matched at handshake (bool) |
| `bytes_in` / `bytes_out` | Counters only |

Frames are appended to a **bounded local journal** on the relay host
(#376's lesson — no unbounded spool; rotation is the journal's own
contract, not a later fix), exposed on a control-plane query surface:
`relay_session_liveness(vm_id) → {session_id, state: active|idle|closed,
last_bytes_at, hostkey_verified}`. Idle threshold: 5 minutes without
bytes (a real cadence-friendly number, not a product promise — §9 Q1).

## 3. Two-channel liveness

**Channel A — passive (the journal).** Session frames make "a session was
alive at T" a control-plane fact with no VM contact at all. This is the
primary instrument for the tenant-facing question "is the path working
right now": an `active` session with fresh `last_bytes_at` and
`hostkey_verified` is positive evidence.

**Channel B — active (the synthetic dial prober).** Passive frames only
speak for sessions that exist; a box with no open session still needs its
*path* verified (the `live`-entry AND-combine needs "relay/cert path
reachable" as a fact, not as an absence). A control-plane prober dials
the tenant's path exactly as the tenant would, on a cadence (§9 Q1):
resolve relay host → TCP to the relay listener → SSH transport handshake
through to the VM's private leg → verify the host key against the pinned
fingerprint → **close cleanly before authentication**. The probe is
handshake-only: it never holds a tenant credential, never logs into the
box, never touches the VM's auth surface (the no-login rule is
load-bearing — §9 Q4).

Outcome taxonomy (every outcome maps to the existing status vocabulary,
no new codes):

| Outcome | Meaning | Status mapping |
|---|---|---|
| `path_ok` | Full path works, host key verified | No transition; path evidence for §5 |
| `relay_defect` | The relay daemon/listener itself not responding | Control-plane defect → `connection-unreachable` suspension (endpoint rule 6), pages the operator |
| `cert_defect` | Handshake completes but host-key verification fails (rotation, MITM, reprovision drift) | Cert-path failure → `connection-unreachable` (the spec §8 relay/cert family), sub-code `cert` |
| `box_leg_defect` | Relay answers, private leg to the box fails, provider still reports `running` | Relay-path failure while the poll says otherwise → `connection-unreachable`, sub-code `box-leg` |
| `provider_not_running` | Provider state is suspended/waking/destroyed | Prober stands down — provider state is the authority (endpoint §4 AND-combine); not a liveness question |

The distinction the taxonomy exists to make: **who is blamed.**
`relay_defect`/`cert_defect`/`box_leg_defect` are never the Muse's fault
(spec §8: "control-plane/relay defect") — they suspend the arc without
advancing or resetting it (endpoint rule 6's latch semantics). The box's
own stack failing is `box-unhealthy`, decided by smoke/harness checks —
this instrument does not emit that code; the taxonomy keeps the two
families apart exactly as the endpoint's §4 rules do.

## 4. The no-inbound discipline

Why both channels observe the path without any inbound path to the VM:

- **Passive channel** never contacts the VM — it is the relay's own
  journal. `public_ingress: false` is untouched.
- **Active channel** dials *outbound* from the control plane to the
  relay's listener — the same listener tenants use — and the relay
  speaks to the box over the private provider leg. The ban is on public
  ingress *to the VM*; the probe traverses no path a tenant couldn't use
  and opens no new one. It uses exactly the tenant's connection bundle
  (relay host/port + pinned fingerprint), so the probe is also the
  continuous verification of the bundle itself.
- **No new trust root.** Host-key verification reuses the pinned
  fingerprint; no TOFU, no prober-held credentials, no unauthenticated
  report endpoint (a box-forgeable health report would violate the
  endpoint doc's §4 linked-key rule by other means).

## 5. Producer contract — wiring into the tenant-status layer

The instrument's shipped output is `relay_path_state(vm_id) → ok |
degraded | down`, with the §3 sub-code (`relay` | `cert` | `box-leg`).
The tenant layer consumes it as the `connection-unreachable` producer:

- The **`live`-entry AND-combine** (endpoint §4: "provider running **and**
  relay/cert path reachable") gets its second input. At provision, (a)
  reachability failure (no bundle ever handed out) still holds at
  `provisioning` per the existing rule — the instrument's job starts at
  `live`.
- **Transition rule 6** (relay/cert suspension) fires on a non-`ok`
  reading while the arc is post-`live`: latch the arc code, serve
  `connection-unreachable` with the sub-code in `detail`, record
  arc-advancing events against the latch, re-evaluate on recovery —
  never a blind stack-pop.
- **Interim honesty:** until the R3 wiring ships, the instrument exposes
  `relay_path_state` on the operator surface only. The endpoint must not
  claim `connection-unreachable` from a producer that isn't wired — the
  same "don't fake the signal" discipline the stuck detector's
  closed-world rule enforces. A design that silently claims more than it
  measures is a funnel-poisoning instrument.

## 6. Closing the stuck-detector's gap (Q6 resolved)

`docs/STUCK_DETECTOR_DESIGN.md` §4's predicate drops the relay conjunct
today. With this instrument, the conjunct becomes observable:

```
AND relay_path_ok(S) == true       (this doc's relay_path_state(S) == ok;
                                    sub-codes route to
                                    connection-unreachable, never stuck)
```

The closed-world rule survives: if the instrument itself is dark (prober
down, journal stale past the §2 idle threshold + margin), the conjunct
is **unobservable** → `insufficient-observability`, never assumed-`ok`.
This design joins the S3 gate's dependency list (H4 provider state, this
relay-liveness design, H13 suspend contract, G1 terminal records) — S3
remains unreachable until all four ship.

## 7. What this design deliberately does not do

- **No end-to-end login probe.** The handshake-only rule stands; a
  logged-in probe would need a credential with box access and would turn
  the prober into a privileged writer — rejected.
- **No relay HA design.** Single relay daemon vs redundant pair with
  journal failover is an operator/deployment decision (H4/hosting), not
  a liveness-semantics decision. The journal's bounded rotation is
  specified here because an unbounded one is a design defect (#376); how
  many relay hosts run the daemon is not.
- **No cadence decision.** Probe frequency is a cost-vs-detection-time
  tradeoff (compute per probe × boxes × cadence) — §9 Q1, a product call,
  not this design. The doc's only binding recommendation: probe while a
  post-`live` arc exists on the box, stand down when the provider says
  suspended/destroyed (the prober reads provider state first).
- **No new status codes.** Every outcome routes to the existing 12-code
  vocabulary. If a future turn wants a `relay-degraded` nuance, that's a
  vocabulary change with its own design, not a silent addition.

## 8. Build slices

- **R1 — session journal (passive instrument):** the relay daemon emits
  §2 frames to a bounded local journal + `relay_session_liveness(vm_id)`
  query. Rotation bound is part of R1's acceptance (unbounded = fail).
- **R2 — dial prober (active instrument):** control-plane prober,
  §3 cadence and outcome taxonomy, handshake-only, pinned-fingerprint
  verification. Ships with an operator-visible `relay_path_state`
  surface — no tenant-status wiring yet (§5 interim honesty).
- **R3 — tenant-status producer wiring:** the tenant layer consumes
  `relay_path_state` — transition rule 6 suspension + the live-entry
  AND-combine. Updates `docs/TENANT_STATUS_ENDPOINT.md` §2's
  `connection-unreachable` row from "instrumentation" to this producer.
- **R4 — stuck-detector conjunct:** §6's predicate change; closed-world
  on instrument darkness; S2-calibration note that the soak's confusion
  classes gain a "suspension while measuring" row.

## 9. Open questions (→ backlog)

- **Q1 (cadence vs cost):** probe cadence while post-`live` arcs are
  active (2 min? 5 min?) vs control-plane compute spend. Product call;
  the detector's confirmation tick (stuck-detector §4: 5-min window +
  margin) sets the detection-time budget the cadence must fit inside.
- **Q2 (G7 multi-box):** liveness is per-session → per-box. G7's
  per-box-status vs newest-box-arc decision determines whether a tenant
  with two boxes gets per-box `connection-unreachable` or one
  tenant-level suspension.
- **Q3 (relay HA):** journal failover across relay hosts; the bounded
  journal's rotation contract must survive failover without double-
  counting frames.
- **Q4 (probe depth):** handshake-only stands; anyone proposing
  end-to-end must answer the credential question (no — the prober holds
  no tenant credential, by design).
- **Q5 (cert rotation):** reprovision creates a new session with a new
  bundle (endpoint rule 7) — the prober must re-pin on session restart,
  never carry a fingerprint across sessions. The pinned-fingerprint
  source of truth is the session's connection bundle, not the prober's
  config.

## Cross-references

- `docs/TENANT_STATUS_ENDPOINT.md` §2 (`connection-unreachable` row),
  §4 (live-entry AND-combine, rule 6 relay/cert suspension) — R3 wires
  this design in as the named producer.
- `docs/STUCK_DETECTOR_DESIGN.md` §4 (predicate), §7 S3, §8 Q6 — Q6's
  answer; S3's dependency list.
- `docs/FIRST_TEN_MINUTES_SPEC.md` §2 (minute-0 relay criterion), §8
  (failure taxonomy) — the spec the instrument serves.
- `harness/provider_iface.py` (`ProvisionSpec.public_ingress` invariant,
  `ssh_info()`, `dial()` verb) — the contract the relay implements and
  the §4 discipline it must not violate.
- `docs/USAGE_METERING_DESIGN.md` §4–§5 (counters-over-content privacy,
  #376 rotation lesson) — frame and journal constraints.
- `docs/SENTINEL_TELEMETRY_SURFACES.md` S3 — why the emitter is the relay
  daemon, never the tenant's Muse.
