# Rollout controller — fleet update orchestration design (G15 / #606)

The per-box updaters are done: `deploy/auto-deploy.sh` converges each box to
the newest merged commit on a 10-minute timer (gated, with per-box rollback),
and the toolset updater (`deploy/toolset-update.sh`, issue #532) keeps the
default toolset pinned on a weekly quiet-hours timer. Every box updates
*itself*. Nothing updates the *fleet*.

This doc designs the fleet layer: a **rollout controller** that takes a
release and delivers it to many boxes in stages — canary, waves, health-gated
promotion, halt on bad signal, and an emergency freeze that actually reaches
the boxes. It is the design behind G15 (#606); it consumes G16 (fleet version
inventory, #607), G17 (update event reporting, #608), and G18 (the fleet→box
release-gating channel, #609) without re-litigating them. It composes with
G11's tenant-box update policy (`UPDATE_CHANNEL_POLICY.md`: rolling reimage +
tenant-state migration, no in-place updater for tenant boxes) and G12's
`maintenance` status code (`TENANT_STATUS_ENDPOINT.md`).

Scope note (both-supported default, per PLAYBOOK): the controller is a repo
component any self-hosted operator with N boxes can run — the operator's own
estate is already a fleet — and the hosted product reuses the same component
for tenant fleets. The per-box updaters stay the enforcement point: the fleet
layer only tells boxes *which versions are deployable* (and *when* their wave
moves) — see §5.

## 1. What the fleet layer must do

Today a bad merge-to-main reaches every box within one 10-minute timer
period. The correlated-failure blast radius is the whole fleet, and per-box
rollback repairs boxes one at a time *after* the damage. The fleet layer
changes that with five primitives:

1. **Wave assignment** — boxes are assigned to waves (canary first, then
   expanding waves); only the current wave's boxes update.
2. **Health-gated promotion** — the controller advances a wave only when the
   previous wave's signal is clean; a bad signal halts the rollout.
3. **Freeze** — an operator flips one switch and all pending updates stop,
   faster than a timer tick.
4. **Expedited security channel** — security releases travel the same waves
   but compressed; expedited, never ungated.
5. **One answer** — the operator can always answer "what % of the fleet is on
   build X?" (G16) and "what happened in the last window?" (G17).

## 2. Component shape

One repo component, `fleet/`:

- **Controller daemon** — owns the rollout state machine: which release is
  rolling, which wave is live, whether the release is halted or the fleet is
  frozen. Runs wherever the operator runs it (a spare box, a container, the
  control plane); the hosted product runs it in the control plane with
  per-tenant wave scoping (pending the H11 audit's confirmation — see open
  question 3).
- **Release registry** — the set of releases the fleet may converge to:
  `(component, version, channel, image_version)`. Channels: `stable`
  (default waves), `security` (expedited waves). Nothing is deployable until
  it is registered; registration is the human decision point.
- **Wave manifest** — the committed assignment: which boxes are in which
  wave, plus canary selection. Default assignment is deterministic
  (`hash(box_id) mod buckets`) so operators can start with zero config;
  the manifest pins explicit assignments where it matters (canary boxes,
  boxes that must never be in wave 1).
- **CLI** — `fleet status` (rollout state + per-wave progress), `fleet
  freeze` / `fleet unfreeze`, `fleet promote` (manual override),
  `fleet halt` (pin the current wave, stop promotion). `fleet promote`
  is the documented escape when the promotion gate cannot converge on its
  own (see §4).

State is a JSONL journal + snapshot, same discipline as the repo's other
components: the controller's decisions are auditable after the fact.

## 3. The rollout state machine

```
draft → canary → wave-2 → … → wave-N → complete
                    │         │
                    └─ halted ┘  (freeze is orthogonal: any live wave +
                                   pending waves pause while frozen)
```

- **canary**: the release goes to the canary wave only (one box, or a small
  fraction for large fleets). The controller soaks it for the soak window
  *and* requires clean health-gate signal before promoting (see §4).
- **wave-N**: each wave expands (e.g. canary box, then 10%, 25%, 50%, 100%
  of the fleet); the manifest may fix wave sizes explicitly. Promotion from
  wave *k* to *k+1* is gated the same way.
- **halted**: the release is pinned at its current wave; boxes already on
  the new build stay on it (per-box rollback per auto-deploy still applies
  locally); no further waves update. Operator un-halts explicitly, or
  registers a fixed release and starts a new rollout.
- **freeze**: a single global controller-state flag, orthogonal to any
  release — freeze is operator-level and release-independent. All pending
  updates stop *fleet-wide*, regardless of wave. Freeze/unfreeze events
  are journaled globally; halt/unhalt events are journaled per rollout.
  The freeze must propagate through the G18 channel **faster than
  auto-deploy's 10-minute tick** — a freeze that cannot reach a box within
  one tick is theater (this is G18's propagation-latency bound, which the
  controller design *assumes* and G18 *delivers*; §5's hook cadence makes
  the pull model meet it).

A halted rollout is not a failed rollout; `fleet status` shows it as
"halted — operator decision required", never as noise.

## 4. Health gates (what promotion reads)

The controller does not decide on vibes. Promotion from wave *k* consumes:

- **G17 events** (update outcomes: started/deferred/succeeded/failed/
  rolled-back) aggregated per wave. Gate: zero failed/rolled-back events in
  the current wave over the soak window.
- **G16 inventory** (what each box is actually running). Gate: wave-*k* boxes
  report the new version before promotion to *k+1* begins — a wave that
  didn't land is not a wave that passed.
- **Baseline comparison**: the controller keeps a short rolling baseline of
  per-wave failure rates. If the canary's failure rate exceeds the baseline
  by a configured margin, the release halts. A box that was already sick
  does not convict the release; a box that got sick *after* the update does.
  The baseline is why N=1 estates can't use gates meaningfully (see §9).

Soak evidence is per **(box, build)**, not per box: only signal gathered
while a box runs the *new* build counts toward that build's soak — a
reimaged tenant box's pre-reimage signal was for the old build (G11: a
reimage is a new session internally), so reimage resets that box's soak
evidence. A freeze **tolls** the soak clock (the window does not run
through a freeze), and the final pre-promotion tail of the window must be
clean *and* unfrozen — a wave never passes on a window with a frozen gap
in its middle.

The gate evaluates **eligible boxes** (reachable ∧ not arc-deferred ∧ not
suspended) with a minimum quorum and a max-wait that pages the operator —
a wave of perpetually arc-busy boxes stalls loudly, never silently; if the
quorum cannot be met, the rollout waits for the operator and `fleet
promote` is the documented manual escape.

Operator-defined gate predicates come first (a YAML file the controller
evaluates); canned gates (rollback-rate, health-check-failure-rate) ship in
S2. Until G17/G16 exist, gates are operator-promote-only — the controller
assigns waves and waits, never auto-promotes. **Auto-promotion without eyes
is just the 10-minute timer with extra steps.**

## 5. The box-side hook (the G15 half of G18)

The controller's hands reach the box through G18's channel. G18 decides the
transport; G15 states the interface the controller needs:

- **Cadence is decoupled from the update tick.** The box-side hook polls
  gate state on a short, cheap interval (60–120s), *independent* of the
  10-minute update tick; the update tick re-checks immediately before any
  deploy. Freeze propagation is then bounded by the gate interval, not the
  update tick — this is what makes the pull model deliver §3's sub-tick
  freeze bound while G18's transport choice stays free.
- **The gate answer carries a max-permitted commit, per channel.** The box
  asks: *for my box_id, what is the newest commit I may converge to, and
  is the fleet frozen?* Boxes in waves not yet reached stay on the old
  release even though the release exists. `auto-deploy.sh`'s
  `pending_range` must cap its target at `min(origin/main head, permitted)` —
  unregistered commits never deploy on fleet-managed boxes. Honest
  corollary: for fleet-managed boxes this *narrows* the
  "anyone who can merge to main can execute code on the box" primitive
  (`auto-deploy.sh:17–18`) to "anyone who can merge to main *and* register
  the release" — the fleet layer does not just tell boxes *when*, it tells
  them *which versions are deployable at all*.
- **Signed answers; provisioned trust root.** The answer is signed/pinned
  to the controller's identity — an unsigned "update now" is a
  remote-code-execution primitive, and the fleet layer must not widen the
  merge-to-main trust to anyone who can answer a query. The box learns the
  controller's identity at install/provision time (pinned in
  operator-deployed config).
- **Fail-closed, with attributed cause.** Boxes that cannot reach the
  controller behave as **frozen by default**: no signal, no update. This is
  the fail-closed direction — a partitioned box drifting forward is how
  correlated failures hide. The tradeoff is explicit: the controller is a
  single point of *update* failure — controller down means the whole fleet
  holds, including the security channel. The hook reports gate-answer
  age/source to the box's local status, so `fleet status` shows a stale box
  as "gate-stale (last good answer T ago)" rather than an unexplained
  freeze — degraded operation is visible freeze-with-cause, never silent
  drift.

For tenant boxes (G11): the wave gate applies to *reimage approval*, not to
an in-place update — the controller authorizes the reimage to the new
image_version for wave-*k* boxes. The G15 scheduler (never the box itself)
owns the `maintenance` code's enter/exit writes during the reimage window,
per `UPDATE_CHANNEL_POLICY.md`'s producer rule. Rollback stays "reimage to
the previous gate-checked image + state migration", as G11 decided.

**Second enforcement point — the toolset updater.** The registry is
per-component, and the weekly toolset updater (`Sun 03:00 box-local + 30min
jitter`) gates on the same hook: the gate answer carries a max-permitted
toolset pin, and a wave's boxes converge their pins at their next scheduled
tick — waves never force a mid-week run. A frozen fleet holds toolset pins
exactly like repo commits.

## 6. Tenant-fleet instantiations and their constraints

The operator estate can run this today (once G16–G18 exist). The tenant-fleet
instantiation additionally waits on G13 and H11 — and the design has to say
why, or someone will wire it up early:

- **Event authenticity (G13):** canary gates consume self-reported events,
  and G13's threat model is "a tenant Muse with shell on the box" — a
  tenant can forge `succeeded` events to promote a bad release, or forged
  `failed` events to halt a good one. Tenant-fleet gates require box-identity
  attestation on every event the gate consumes. The operator estate (trusted
  boxes, one operator) starts without it.
- **Never interrupt an arc:** scheduled updates do not interrupt running
  tenant arcs and the session clock is unaffected by updates (decided for
  G11/G12). The controller must schedule around arcs: wave membership is
  consulted at tick time, and a box with an active arc defers its wave
  update until the arc ends. The canary box is preferentially an *idle* box;
  a canary that is always busy is a canary that never soaks.
- **Per-tenant waves (H11):** when H11 lands, waves are scoped per tenant —
  one tenant's halted rollout never pins another tenant's fleet.
- **Suspended boxes (G14, still open):** a box asleep through its wave does
  not "fail" the wave — wave progress counts only boxes that were reachable.
  On wake, the box reads its *current* permitted version and converges
  forward. Whether wake-for-update is a thing at all is G14's decision.

## 7. The security channel

Security releases use the same state machine with compressed parameters —
never a bypass:

- Soak window shrinks (minutes, not hours); canary still exists, even for
  critical CVEs. A security patch that bricks the fleet is the disaster the
  fleet layer exists to prevent.
- Registration to the `security` channel is itself gated: the release must
  carry its advisory reference, and `fleet status` shows the advisory so the
  operator can audit why this release jumped the queue.
- Expedited does **not** mean arc-interrupting: a tenant box mid-arc defers
  even a critical CVE until the arc ends (never-interrupt-an-arc holds on the
  security channel too); the arc-deferral makes security waves land on arc
  boundaries, not mid-arc.
- Staged rollout *delays* security patches to later waves — that tradeoff is
  explicit in the design, and the compressed channel is the answer, not an
  afterthought.

## 8. Data the controller keeps

- `box_id` — stable box identity (provisioned at install; MUST survive
  reimage — a requirement on the provisioner's per-box record, per G11).
- Wave manifest — box → wave, canary pinning, channel per box.
- Release record — component, version/commit, image_version, channel,
  advisory reference (security channel), registered_by/at.
- Rollout record — release, current wave, state (per §3), gate snapshots
  per promotion decision (what the controller saw when it promoted —
  auditability), per-rollout halt journal (freeze/unfreeze events live in the
  global journal, §3).
- What it reads, never owns: G16 inventory, G17 events, tenant arcs (for
  never-interrupt scheduling), H11 tenancy.

## 9. Deliberately out of scope

- **N=1 estates**: the per-box updaters suffice; the fleet layer pays off at
  N>1. Nothing in this design changes single-box behavior.
- **What a tenant-box update is** (G11–G14): decided elsewhere; this decides
  *when*.
- **How wave/freeze state reaches the box** (G18): the controller states its
  interface (§5); G18 picks the transport.
- **Provisioning new boxes mid-rollout**: a new box provisions at the latest
  *completed* release, never into a live wave.

## Build slices

- **S1 — waves + registry (ship first):** `fleet/` skeleton: release
  registry, wave manifest (hash-default + explicit pins), `fleet status`,
  `fleet freeze`/`unfreeze`/`promote`/`halt` CLI; the box-side gate query
  interface (§5) that the per-box updaters call before each tick; operator
  manual promotion only. The S1 interim transport *is* the local mirror
  the operator's cron syncs — it is the first instantiation of the G18
  channel, not a gap before it: the mirror is controller-signed with an
  issuance timestamp and short TTL, and the box-side hook treats a
  missing, expired, or bad-signature mirror as no-signal → frozen
  (§5 fail-closed).
- **S2 — gates:** G17 event aggregation per wave, G16 inventory checks,
  baseline comparison, soak windows, canned gates, YAML predicate support;
  auto-promote behind gates; halt journaling with gate snapshots.
- **S3 — hosted + security:** security channel with advisory references and
  compressed waves; tenant-fleet instantiation behind G13 attestation +
  H11 per-tenant waves; never-interrupt-arc scheduling; suspended-box
  semantics after G14 decides.

## Open questions

1. **Concurrent releases**: can two releases roll at once (stable wave-2
   while security canary soaks)? S1 says no; S3 may need it.
2. **Canary size for tiny fleets**: N=3 estates can't spare a box — is
   canary-of-1 real signal or ritual? The baseline math (§4) needs a
   minimum fleet size; name it in S2.
3. **Controller ownership in hosted**: the design presumes the tenant-fleet
   controller runs in the control plane with per-tenant wave scoping (§2);
   H11 audit should confirm before any tenant-fleet instantiation.
4. **Reimage + wave assignment**: a reimaged tenant box is a new session
   internally (G11) — it inherits its wave (a box that came back healthy
   is still that box), but soak evidence is per (box, build) (§4), so its
   soak evidence for the new build starts at zero.
5. **Freeze vs auto-deploy's blocked-commit**: a fleet-halted release that
   later resumes — does the local blocked-commit marker (auto-deploy's
   "don't retry-loop") interact with wave re-entry? Proposed: fleet halt
   clears nothing; the blocked marker is per-box failure memory and stands.

---
*Design for G15 (#606), from the 2026-09-28 fleet-rollout gap analysis
(`FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md`). Implementation (S1–S3) remains —
tracked on #606. Related: G16 (#607), G17 (#608), G18 (#609), G11/G12
(UPDATE_CHANNEL_POLICY.md), G13 (#555), G14 (#556), H11.*
